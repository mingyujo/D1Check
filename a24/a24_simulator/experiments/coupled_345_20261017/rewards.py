"""Allocate the actual common dynamics integrals to actual neural decision times."""
import math
import numpy as np
from dynamics import NS


def labels(result,frames,case,physics,metrics):
    if not frames:raise ValueError('Empty learning episode')
    times=np.array([f['time_ns'] for f in frames]);cost=np.zeros((len(frames),5),np.float64)
    if (np.diff(times)<0).any():raise ValueError('Decision order')
    c=physics.c;n=case['n'];drain=case['drain_stop_s'];initial=case['temperature_c']
    def index(t):return max(0,min(len(frames)-1,int(np.searchsorted(times,t,side='right'))-1))
    for trace in result['trace']:
        a,b=trace['start_ns']/NS,trace['end_ns']/NS
        if a<35-1e-9 or b>drain+1e-9:continue
        i=index(trace['start_ns']);cost[i,0]+=trace['increment']/(n*.35)
        passive=c.idle_c*(b-a)+(initial-c.idle_c)*c.thermal_tau_s*(math.exp(-(a-35)/c.thermal_tau_s)-math.exp(-(b-35)/c.thermal_tau_s))
        heat=trace['temperature_area']-passive
        if heat< -1e-7:raise ValueError('Unexpected negative heat relative to passive cooling')
        cost[i,1]+=max(0.,heat)/(n*3.)
    at_drain=next(t['next_state'] for t in result['trace'] if t['end_ns']==round(drain*NS))
    cost[-1,0]+=physics.shared*c.idle_tail_s*at_drain['shared_z']/(n*.35)
    cost[-1,1]+=.1*max(0.,metrics['peak_AP_c']-32.)/5.
    for r in result['requests']:
        response=r['response_ns']/NS if r['response_ns'] is not None and r['response_ns']/NS<=drain else None
        if response is None:cost[-1,4]+=1/n;continue
        late=max(0.,response-r['deadline_ns']/NS)
        loss=float(late>1e-9)+.2*min(5.,late/max(.05,(r['deadline_ns']-r['scheduled_arrival_ns'])/NS))
        cost[index(r['response_ns']),2 if r['priority']=='U' else 3]+=loss/n
    error=float(np.max(abs(cost.sum(0)-np.array(metrics['cost_vector']))))
    if error>1e-6 or not np.isfinite(cost).all():raise ValueError('Reward/final objective telescope: '+str(error))
    return cost,dict(max_telescope_error=error,cost_sum=cost.sum(0).tolist(),future_labels_in_inputs=False)
