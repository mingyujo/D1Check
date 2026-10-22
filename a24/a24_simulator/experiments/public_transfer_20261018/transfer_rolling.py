"""Bounded visible nominal rollout using the frozen physical transition.

Up to eight EDF-visible requests plus owners; candidate always included.
No future arrivals, sampled work, actual residual or future event time.
"""
import copy,math
from common_transfer import NS,tie,B
from dynamics import advance_jobs
def predict(state,chosen,vectors,physics,first):
    start=state['now_ns']/NS;now=start
    due=lambda q:(q['deadline_ns'],*tie(q))
    subset=sorted(chosen,key=due)[:8]
    if first['kind']=='DISPATCH' and not any(q['request_id']==first['request_id'] for q in subset):subset[-1]=next(q for q in chosen if q['request_id']==first['request_id'])
    pending={q['request_id']:q for q in subset};allrows={q['request_id']:q for q in [*subset,*state['owners']]}
    jobs=[];answers={};energy=heat=0.;st={k:state['sensor'][k] for k in ('temperature_c','shared_z')};initial=st['temperature_c']
    for o in state['owners']:
        v=list(vectors[o['request_id'],o['route']]);stage=o['stage'];v[stage]=max(1e-9,v[stage]-o['public_progress_s'])
        jobs.append(dict(request_id=o['request_id'],task=o['task'],route=o['route'],stage=stage,remaining=v[stage],vector=v))
        if o.get('response_ns') is not None:answers[o['request_id']]=o['response_ns']/NS
    initial_ids={j['request_id'] for j in jobs};wait_event=first['kind']=='WAIT_EVENT';wait_until=start+first.get('wait_ns',0)/NS
    event_cap=start+first.get('max_wait_ns',12*NS)/NS
    def settle():
        for j in list(jobs):
            while j['remaining']<=1e-10:
                if (j['task']=='C' and j['stage']==1) or (j['task']=='D' and j['stage']==2):answers[j['request_id']]=now
                j['stage']+=1
                if j['stage']==5:jobs.remove(j);break
                j['remaining']=j['vector'][j['stage']]
    def dispatch(q,r):
        v=vectors[q['request_id'],r];jobs.append(dict(request_id=q['request_id'],task=q['task'],route=r,stage=0,remaining=v[0],vector=v));pending.pop(q['request_id']);st['shared_z']=1.;settle()
    if first['kind']=='DISPATCH':dispatch(pending[first['request_id']],first['route'])
    # Public common finite window, identical across candidate actions.
    total=sum(max(sum(vectors[q['request_id'],r])/physics.c.minimum_speed for r in ('CPU','GPU')) for q in [*subset,*state['owners']])
    end=start+max(2.,total+2.);steps=0
    while (jobs or pending) and now<end-1e-10:
        settle()
        if wait_event and (any(rid not in {j['request_id'] for j in jobs} for rid in initial_ids) or now>=event_cap-1e-10):wait_event=False
        if not wait_event and now>=wait_until-1e-10:
            while pending and len(jobs)<2:
                free=[r for r in ('CPU','GPU') if r not in {j['route'] for j in jobs}]
                q=min(pending.values(),key=due)
                r=min(free,key=lambda r:(sum(vectors[q['request_id'],r])/physics.speed(st['temperature_c'],r,1),r))
                dispatch(q,r)
        if not jobs and not pending:break
        dt=min(physics.c.tick_s,end-now)
        if now<wait_until:dt=min(dt,wait_until-now)
        if wait_event and now<event_cap:dt=min(dt,event_cap-now)
        for j in jobs:dt=min(dt,max(1e-9,j['remaining']/physics.speed(st['temperature_c'],j['route'],j['stage'])))
        st,terms=advance_jobs(physics,st,jobs,dt);energy+=terms['increment']+terms['baseline'];heat+=terms['temperature_area']-physics.c.idle_c*dt;now+=dt;steps+=1
        if steps>2000:raise ValueError('Registered public rolling step cap')
    settle();duration=now-start
    late=[]
    for p in ('U','N'):
        group=[q for q in allrows.values() if q['priority']==p];loss=0.
        for q in group:
            response=answers.get(q['request_id'],end);d=max(0.,response-q['deadline_ns']/NS);ttl=max(.05,(q['deadline_ns']-q['scheduled_arrival_ns'])/NS)
            loss+=float(d>1e-9)+.02*min(5.,d/ttl)
        late.append(loss/max(1,len(group)))
    return dict(total_J=energy,heat_Cs=max(0.,heat),duration_s=duration,late_U=late[0],late_N=late[1],steps=steps,visible=len(allrows),unfinished=len(jobs)+len(pending),future_information=False)
