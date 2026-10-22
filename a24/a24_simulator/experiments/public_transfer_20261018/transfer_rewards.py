"""Separate total-completion energy, fixed-reference heat and deadline prefixes."""
import bisect,math
from common_transfer import np,NS
def labels(result,frames,case,physics,reference,balanced,scales):
    requests=result['requests'];finish=max(q['available_ns'] for q in requests) if all(q['available_ns'] is not None for q in requests) else round(case['drain_stop_s']*NS);H=reference['reference_end_ns'];trace=result['trace'];starts=[t['start_ns'] for t in trace];E=[0.];Q=[0.]
    for t in trace:E.append(E[-1]+t['increment']);Q.append(Q[-1]+t['temperature_area']-physics.c.idle_c*t['dt'])
    def prefix(t):
        if t<=35*NS:return 0.,0.
        i=bisect.bisect_right(starts,t)-1
        if t>=trace[-1]['end_ns']:return E[-1],Q[-1]
        _,part=physics.transition(trace[i]['state'],trace[i]['active'],(t-trace[i]['start_ns'])/NS)
        return E[i]+part['increment'],Q[i]+part['temperature_area']-physics.c.idle_c*(t-trace[i]['start_ns'])/NS
    normalizers=[max(1,sum(q['priority']==p for q in requests)) if balanced else case['n'] for p in ('U','N')];cost=np.zeros((len(frames),5));prior=np.zeros(5);records=[];tail=.02 if balanced else .2
    for i,f in enumerate(frames):
        end=frames[i+1]['time_ns'] if i+1<len(frames) else max(finish,H);e_end=min(end,finish);q_end=min(end,H);energy=prefix(e_end)[0]+physics.c.baseline*(e_end/NS-35);heat=max(0.,prefix(q_end)[1]);value=np.zeros(5);value[0]=energy/reference['completion_total_J_proxy'];value[1]=heat/max(1e-9,(reference['mean_AP_c']-physics.c.idle_c)*(H/NS-35))
        for q in requests:
            response=q['response_ns'];late=max(0.,(min(end,response) if response is not None else end)/NS-q['deadline_ns']/NS);j=0 if q['priority']=='U' else 1;value[2+j]+=(float(late>1e-9)+tail*min(5.,late/max(.05,(q['deadline_ns']-q['scheduled_arrival_ns'])/NS)))/normalizers[j]
        if i==len(frames)-1:value[4]=sum(q['available_ns'] is None or q['available_ns']>H for q in requests)/case['n']
        cost[i]=value-prior;prior=value;records.append(dict(end_ns=end,prefix=value.tolist()))
    physical=cost.copy()
    if balanced:cost[:,:2]/=np.asarray(scales)
    assert np.isfinite(cost).all() and np.max(abs(physical.sum(0)-prior))<2e-7
    return cost,dict(cost_sum=cost.sum(0).tolist(),physical_cost_sum=physical.sum(0).tolist(),finish_ns=finish,H_ns=H,balanced=balanced,scales=list(scales),prefix_records=records,deadline_groups=normalizers,tail=tail,energy_includes_baseline=True,peak_still_reported=True)
