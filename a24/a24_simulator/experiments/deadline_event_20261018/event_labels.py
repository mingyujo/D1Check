"""Move the identical missed-deadline cost to its actual deadline crossing.

Only reward timing changes. Goal weights, episode totals, encoder, action
permissions, physics and all energy/thermal labels remain unchanged.
This module is a draft until a completed parent comparison justifies the run.
"""
from pathlib import Path
import sys,numpy as np
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'packing_rl_20261018'))
from completion_labels import labels as completion

def deadline_prefix(requests,t,n,drain):
    result=[0.,0.]
    for q in requests:
        response=q.get('response_ns')
        if response is None or response>drain:continue
        late=max(0.,min(t,response)/1e9-q['deadline_ns']/1e9)
        loss=float(late>1e-9)+.2*min(5.,late/max(.05,(q['deadline_ns']-q['scheduled_arrival_ns'])/1e9))
        result[0 if q['priority']=='U' else 1]+=loss/n
    return np.asarray(result)

def sweep(requests,endpoints,n,drain):
    events=[]
    for q in requests:
        response=q.get('response_ns')
        if response is None or response>drain or response<=q['deadline_ns']:continue
        k=0 if q['priority']=='U' else 1;due=q['deadline_ns'];ttl=max(50_000_000,q['deadline_ns']-q['scheduled_arrival_ns']);stop=min(response,due+5*ttl);rate=.2/(ttl/1e9*n)
        events.extend([(due,k,rate,0.),(stop,k,-rate,0.)])
        crossing=due+1 if (due+1)/1e9-due/1e9>1e-9 else due+2
        if response/1e9-due/1e9>1e-9:events.append((min(response,crossing),k,0.,1/n))
    events.sort(key=lambda x:x[0]);slope=np.zeros(2);value=np.zeros(2);at=0;previous=35_000_000_000;result=[]
    for end in endpoints:
        while at<len(events) and events[at][0]<=end:
            t,k,change,jump=events[at];value+=slope*((t-previous)/1e9);previous=t;slope[k]+=change;value[k]+=jump;at+=1
        value+=slope*((end-previous)/1e9);previous=end;result.append(value.copy())
    return result

def labels(result,frames,case,physics,metrics,H,reference,joint):
    costs,audit=completion(result,frames,case,physics,metrics,H,reference,joint);costs=np.array(costs,copy=True);old_total=costs[:,2:4].sum(0);prior=np.zeros(2);records=[];drain=round(case['drain_stop_s']*1e9)
    endpoints=[min(r['end_ns'],drain) for r in audit['prefix_records']]
    for i,(end,value) in enumerate(zip(endpoints,sweep(result['requests'],endpoints,case['n'],drain))):
        costs[i,2:4]=value-prior;prior=value;records.append(dict(end_ns=end,prefix_cost=value.tolist(),increment=costs[i,2:4].tolist()))
    if np.max(abs(costs[:,2:4].sum(0)-old_total))>2e-7:raise ValueError('Deadline-event redistribution changed the episode objective')
    audit.update(deadline_event_redistribution=True,deadline_event_records=records,original_completion_timed_deadline_total=old_total.tolist(),cost_sum=costs.sum(0).tolist(),actor_uses_no_future_labels=True)
    return costs,audit
