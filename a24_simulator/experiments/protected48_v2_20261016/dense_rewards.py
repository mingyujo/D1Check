"""Post-episode labels only: true interval energy/heat/deadline harm + telescoping potential.

Future outcomes are labels for learning, never policy inputs. Full requested
denominators remain in deadline costs. No baseline or observation is changed.
"""
import numpy as np
from protected_policy import NS,label,state_label

SPEC=dict(energy_scale_J=10.,heat_rise_scale_c=.5,urgent_potential_weight=2.,
          normal_potential_weight=.5,potential_cap=4.,
          deadline_target=1.,heat_window='first arrival to last arrival +15s',
          terminal_heat_peak_weight=.1,terminal_heat_endpoint_weight=.1)

def _heat_integral(ap,lo,hi,initial):
    if hi<=lo:return 0.
    t=np.asarray(ap['t_s']);y=np.asarray(ap['ap_c'])
    x=np.r_[lo,t[(t>lo)&(t<hi)],hi];v=np.maximum(0,np.interp(x,t,y)-initial)
    return float(np.trapezoid(v,x))

def energy_integral(intervals,powers,lo,hi):
    if hi<=lo:return 0.
    marks=sorted({lo,hi,*[min(hi,max(lo,float(q[k]))) for q in intervals for k in ('start_s','end_s')]})
    total=0.
    for a,b in zip(marks,marks[1:]):
        active=[(q['task'],q['route']) for q in intervals if q['start_s']<b and q['end_s']>a]
        if active:total+=(b-a)*powers[state_label(active)]
    return total

def make_costs(result,frames,public,profile,actor_decisions=None):
    pred=result['prediction'];rows=pred['requests']
    # The kernel intentionally omits RESOURCE_WAIT from its applied decisions.
    # Actor calls include it. Use captured causal snapshots in exact call order,
    # including multiple calls at one timestamp; do not approximate by time bins.
    dec=pred['decisions'] if actor_decisions is None else actor_decisions
    if len(frames)!=len(dec):raise ValueError('Every actor frame requires exact public decision')
    if any(f['time_ns']!=d['time_ns'] for f,d in zip(frames,dec)):
        raise ValueError('Actor frame/public snapshot time mismatch')
    for f,d in zip(frames,dec):
        if 'index' in f and d.get('chosen_index')!=f['index']:
            raise ValueError('Actor frame/public action mismatch')
    lo,hi=result['summary']['diagnostics']['common_work_window_s']
    counts={p:sum(q['priority']==p for q in rows) for p in ('U','N')}
    times=[f['time_ns']/NS for f in frames]+[public['drain_stop_ns']/NS]
    costs=np.zeros((len(frames),5),dtype=np.float64)
    potentials=[]
    for d in dec:
        phi=[];now=d['time_ns']
        for p in ('U','N'):
            x=sum(min(SPEC['potential_cap'],((now-q['queue_entry_ns'])/max(1,q['deadline_ns']-q['scheduled_arrival_ns']))**2)
                  for q in d['public_state']['queue'] if q['priority']==p)
            phi.append(x/max(1,counts[p]))
        potentials.append(phi)
    potentials.append([0.,0.])
    powers=profile['cost_anchor']['energy_increment_w']
    for i,(a,b) in enumerate(zip(times,times[1:])):
        aa=max(a,lo);bb=min(b,hi)
        costs[i,0]=energy_integral(result['summary']['gantt'],powers,aa,bb)/SPEC['energy_scale_J']
        costs[i,1]=_heat_integral(result['AP'],aa,bb,public['initial_ap_c'])/((hi-lo)*SPEC['heat_rise_scale_c'])
        for j,p in enumerate(('U','N')):
            for q in rows:
                if q['priority']!=p:continue
                due=q['deadline_ns']/NS;response=q['response_ns']/NS if q['response_ns'] is not None else times[-1]
                if response>due and a<due<=b:costs[i,j+2]+=1/max(1,counts[p])
                delay=max(0,min(b,response)-max(a,due))
                costs[i,j+2]+=delay/max(1e-9,(q['deadline_ns']-q['scheduled_arrival_ns'])/NS)/max(1,counts[p])
            weight=SPEC['urgent_potential_weight' if p=='U' else 'normal_potential_weight']
            costs[i,j+2]+=weight*(potentials[i+1][j]-potentials[i][j])
    costs[-1,4]=sum(q['response_ns'] is None for q in rows)/max(1,len(rows))
    t=np.asarray(result['AP']['t_s']);v=np.asarray(result['AP']['ap_c'])
    q=np.r_[lo,t[(t>lo)&(t<hi)],hi];values=np.interp(q,t,v)
    costs[-1,1]+=(SPEC['terminal_heat_peak_weight']*max(0,float(values.max())-public['initial_ap_c'])
                     +SPEC['terminal_heat_endpoint_weight']*max(0,float(values[-1])-public['initial_ap_c']))/SPEC['heat_rise_scale_c']
    if not np.isfinite(costs).all():raise ValueError('Nonfinite dense costs')
    expected_energy=result['summary']['diagnostics']['work_window_increment_J_proxy']/SPEC['energy_scale_J']
    if abs(costs[:,0].sum()-expected_energy)>1e-8:raise ValueError('Dense energy telescope')
    # Potentials telescope to -initial potential (zero in the first public
    # dispatch state for this experiment), without discarding genuine failures.
    proof=dict(dense_rows=len(frames),nonzero_energy_rows=int(np.count_nonzero(costs[:,0])),
               energy_telescope_error=float(abs(costs[:,0].sum()-expected_energy)),
               initial_potential=potentials[0],terminal_potential=[0.,0.],
               total_cost=costs.sum(0).tolist(),future_labels_in_policy_inputs=False)
    return costs,counts,proof
