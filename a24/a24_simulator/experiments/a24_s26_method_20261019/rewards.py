"""Five actual-outcome costs; no EDF-completion deadline substitution."""
import bisect
from common_transfer import np,NS
def labels(result,frames,case,physics):
    trace=result['trace'];starts=[t['start_ns'] for t in trace];E=[0.];Q=[0.];H=round((case['supply_stop_s']+30)*NS)
    for t in trace:E.append(E[-1]+t['increment']);Q.append(Q[-1]+t['temperature_area']-physics.c.idle_c*t['dt'])
    def prefix(t):
        if t<=35*NS:return 0.,0.
        i=bisect.bisect_right(starts,t)-1
        if t>=trace[-1]['end_ns']:return E[-1],Q[-1]
        _,part=physics.transition(trace[i]['state'],trace[i]['active'],(t-trace[i]['start_ns'])/NS)
        return E[i]+part['increment'],Q[i]+part['temperature_area']-physics.c.idle_c*(t-trace[i]['start_ns'])/NS
    costs=np.zeros((len(frames),5));previous=np.zeros(5);records=[];requests=result['requests']
    for i,f in enumerate(frames):
        end=frames[i+1]['time_ns'] if i+1<len(frames) else round(case['drain_stop_s']*NS);cut=min(end,H);e,h=prefix(cut);value=np.zeros(5)
        value[0]=(e+physics.c.baseline*max(0,cut/NS-35))/(case['n']*.35);value[1]=max(0.,h)/max(1,H/NS-35)/10
        for q in requests:
            late=max(0.,((min(end,q['response_ns']) if q['response_ns'] is not None else end)-q['deadline_ns'])/NS);idx=2 if q['priority']=='U' else 3;den=max(1,sum(x['priority']==q['priority'] for x in requests));ttl=max(.05,(q['deadline_ns']-q['scheduled_arrival_ns'])/NS)
            value[idx]+=(float(late>1e-9)+.02*min(5,late/ttl))/den
        if i==len(frames)-1:value[4]=sum(q['available_ns'] is None or q['available_ns']>round(case['drain_stop_s']*NS) for q in requests)/case['n']
        costs[i]=value-previous;previous=value;records.append(dict(end_ns=end,cumulative=value.tolist()))
    assert np.isfinite(costs).all() and np.max(abs(costs.sum(0)-previous))<1e-7
    return costs,dict(cost_sum=previous.tolist(),fixed_H_ns=H,energy_includes_baseline=True,deadline_uses_actual_request_deadline=True,unfinished_uses_registered_drain=True,prefix_records=records)
