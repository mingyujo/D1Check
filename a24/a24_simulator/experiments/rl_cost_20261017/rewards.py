"""Labels may use completed outcomes; policy observations may not.

Exact state-cost integrals are assigned to the actual actor-call intervals.
Cost response memory starts at time0, so it cannot be reset at each action.
"""
import math
import numpy as np
import state_cost as C
from relative_drain import exclusive

SPEC = dict(alpha=.95, heat_weight=.5, energy_J_per_planned_request=.3,
            AP_rise_scale_c=.5, heat_peak_weight=.1, heat_endpoint_weight=.1,
            energy_model='fixed causal state cost .9s plus explicit additive transfer',
            policy_information='current/past only; future outcomes are training labels',
            reward_dimensions=['work_increment','AP_rise','urgent_deadline_harm',
                               'normal_deadline_harm','missing_response'])


def interval_energy(owners, windows, model, end):
    seg=exclusive(owners,0.,end)
    known=[dict(q,state=q['state'] if C.state_key(q['state']) in C.STATES else 'idle') for q in seg]
    windows=[(a,b) for a,b in windows]
    positive=[(a,b) for a,b in windows if b>a]
    if not positive:return np.zeros(len(windows))
    coefficients=model['coefficients_W_proxy']
    supported=iter(C.exposures(known,positive,model['tau_s']))
    lookup=dict(zip(C.STATES,coefficients));lookup['detection_GPU']=.6013808404579677
    ans=[]
    for a,b in windows:
        if b<=a: ans.append(0.);continue
        fitted=sum(x*w for x,w in zip(next(supported),coefficients))*(b-a)
        transfer=sum(max(0.,min(b,q['end_s'])-max(a,q['start_s']))*
                     sum(lookup[t] for t in C.state_key(q['state']).split('+'))
                     for q in seg if C.state_key(q['state']) not in (*C.STATES,'idle','resident_idle'))
        ans.append(fitted+transfer)
    return np.array(ans)


def make_costs(summary,frames,case,costmodel,initial_ap):
    if not frames:raise ValueError('Empty actor episode')
    times=[f['time_ns']/1e9 for f in frames]+[case['observation_end_s']]
    if any(b<a for a,b in zip(times,times[1:])):raise ValueError('Clock order')
    lo,hi=case['work_window'];n=case['n'];rows=summary['requests']
    windows=[(max(lo,min(hi,a)),max(lo,min(hi,b))) for a,b in zip(times,times[1:])]
    costs=np.zeros((len(frames),5),dtype=np.float64)
    energy=interval_energy(summary['gantt'],windows,costmodel,case['observation_end_s'])
    costs[:,0]=energy/(n*SPEC['energy_J_per_planned_request'])
    ap=summary['AP'];t=np.array(ap['t_s']);v=np.array(ap['ap_c'])
    counts={p:sum(q['priority']==p for q in rows) for p in ('U','N')}
    for i,((a,b),(wa,wb)) in enumerate(zip(zip(times,times[1:]),windows)):
        if wb>wa:
            x=np.r_[wa,t[(t>wa)&(t<wb)],wb]
            costs[i,1]=np.trapezoid(np.maximum(0,np.interp(x,t,v)-initial_ap),x)/((hi-lo)*SPEC['AP_rise_scale_c'])
        for j,p in enumerate(('U','N')):
            for q in rows:
                if q['priority']!=p:continue
                due=q['deadline_ns']/1e9
                response=q['response_ns']/1e9 if q['response_ns'] is not None else times[-1]
                if response>due and a<due<=b:costs[i,j+2]+=1/max(1,counts[p])
                costs[i,j+2]+=max(0,min(b,response)-max(a,due))/max(1e-9,(due-q['scheduled_arrival_ns']/1e9))/max(1,counts[p])
    x=np.r_[lo,t[(t>lo)&(t<hi)],hi];y=np.interp(x,t,v)
    costs[-1,1]+=(SPEC['heat_peak_weight']*max(0,float(y.max())-initial_ap)+SPEC['heat_endpoint_weight']*max(0,float(y[-1])-initial_ap))/SPEC['AP_rise_scale_c']
    costs[-1,4]=sum(q['response_ns'] is None for q in rows)/n
    expected=C.observe(exclusive(summary['gantt'],0.,case['observation_end_s']),lo,hi,costmodel)['increment_J_proxy']
    error=abs(float(energy.sum())-expected)
    if error>1e-7 or not np.isfinite(costs).all():raise ValueError('Causal energy telescope/nonfinite')
    return costs,counts,dict(energy_telescope_error_J_proxy=error,total_cost=costs.sum(0).tolist(),
                            future_labels_in_policy_inputs=False,planned=n,counts=counts)
