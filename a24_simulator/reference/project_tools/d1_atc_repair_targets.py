"""Post-episode credit labels; never callable from online candidate/dispatch code."""
import numpy as np
from tools import d1_queue_hetero_ppo as old

END=120e9

def targets(controller,raw,resident_baseline_j,arm):
    steps=[s for s in controller.snapshots if 'model_error' not in s]
    if not steps:raise ValueError('no trajectory')
    if arm=='ANCHOR':
        frames,costs,valid,rewards=old.targets(controller,raw['row'],raw['curve'],resident_baseline_j)
        for f in frames:
            f['target']=np.pad(f['target'],(0,4)).astype(np.float32)
            f['valid']=np.pad(f['valid'],(0,4)).astype(bool)
        return frames,np.pad(costs,(0,4)).astype(np.float32),np.pad(valid,(0,4)).astype(bool),rewards
    if arm!='CAUSAL':raise ValueError('unknown label contract')
    ledger=raw['result']['ledger'];n=max(len(ledger),1);nu=max(sum(q['priority']=='urgent' for q in ledger),1);nd=max(sum(q['priority']=='normal' for q in ledger),1);units=max(sum(q['work_units'] for q in ledger),1)
    ts=np.array([s['now_ns'] for s in steps],dtype=float)
    if np.any(ts[1:]<ts[:-1]) or ts[-1]>END:raise ValueError('frame time contract')
    reward=np.zeros(len(steps),dtype=np.float64);cost=np.zeros((len(steps),9),dtype=np.float64)
    coverage=sum(max(0,min(120.,p['end_s'])-max(0,p['start_s'])) for p in raw['segments'])
    if abs(coverage-120)>1e-6:raise ValueError('prefix energy state coverage')
    curve=[(float(t)*1e9,float(v)) for t,v in raw['curve'] if t<=120]
    if not curve or curve[0][0]!=35e9 or curve[-1][0]!=END:raise ValueError('prefix AP coverage')
    frozen=controller.frozen
    def peak(t):return max(v for time,v in curve if time<=max(35e9,t))
    # Emissions at a decision boundary belong to the PRECEDING action.
    # An already incurred breach therefore is absent from a later suffix target.
    def emission_index(t):return max(0,min(len(ts)-1,int(np.searchsorted(ts,t,side='left'))-1))
    for i,start in enumerate(ts):
        end=ts[i+1] if i+1<len(ts) else END
        for seg in raw['segments']:
            dt=max(0,min(end,seg['end_s']*1e9)-max(start,seg['start_s']*1e9))/1e9
            if dt:cost[i,0]+=dt*frozen['energy_increment_w'].get(seg['state'],0.)/100
        cost[i,1]=max(0,peak(end)-peak(start))
        for q in ledger:
            response=q['arrival_ns']+q['response_ns'] if 'response_ns' in q else END
            pending=max(0,min(end,response,END)-max(start,q['arrival_ns']))
            # Unit-weighted unresponded holding; ownership completion is separate.
            reward[i]-=q['work_units']*pending/(units*85e9)
            if q['priority']=='urgent':cost[i,8]+=pending/(nu*1.5e9)
    for q in ledger:
        response=q.get('response_ns')
        cap=1.5e9 if q['priority']=='urgent' else 6e9
        for k,delta in ((2 if q['priority']=='urgent' else 4,q['deadline_offset_ns']),(3 if q['priority']=='urgent' else 5,cap)):
            if response is None or response>delta:
                when=min(END,q['arrival_ns']+delta)
                cost[emission_index(when),k]+=1/(nu if q['priority']=='urgent' else nd)
        if q['status']=='succeeded':
            reward[emission_index(q['lane_available_ns'])]+=q['work_units']/units
        else:
            cost[-1,6]+=q['work_units']/units;cost[-1,7]+=1/n
    returns=np.cumsum(reward[::-1])[::-1].copy();suffix=np.cumsum(cost[::-1],axis=0)[::-1].copy()
    if not np.isfinite(suffix).all() or not np.isfinite(returns).all():raise ValueError('nonfinite causal labels')
    expected=[raw['row'][key]/denom for key,denom in (('urgent_failure',nu),('urgent_original_cap_failure',nu),('normal_failure',nd),('normal_original_cap_failure',nd))]
    np.testing.assert_allclose(cost.sum(0)[2:6],expected,rtol=1e-6,atol=1e-7)
    if raw['row']['completed']==raw['row']['planned']:
        expected_energy=(raw['row']['energy_j']-resident_baseline_j)/100
        if abs(cost[:,0].sum()-expected_energy)>1e-6:raise ValueError('prefix J accounting mismatch')
    frames=[];valid=np.ones(10,dtype=bool)
    for snap,ret,c in zip(steps,returns,suffix):
        frames.append(dict(state=snap['state'].copy(),candidates=snap['candidates'].copy(),mask=snap['mask'].copy(),action=int(snap['chosen']),informative=bool(snap['actor_eligible']),old_value=snap.get('old_value'),logprob=snap.get('logprob'),target=np.array([ret,*c],dtype=np.float32),valid=valid.copy()))
    return frames,cost.sum(0).astype(np.float32),valid,reward.astype(np.float32)
