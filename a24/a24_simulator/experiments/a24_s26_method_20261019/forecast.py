"""Visible-only 32-job CPU3 nominal rollout, including 20/50ms/event WAIT."""
import copy,math
from common_transfer import NS,tie

def predict(s,first,jobs,vectors,physics,case):
    now=s['now_ns']/NS;start=now
    state={k:copy.deepcopy(v) for k,v in s['sensor'].items() if k not in ('peak_c','increment_so_far')}
    queue={q['request_id']:q for q in jobs};owners=[];responses={};finished=set();deadline={};priority={}
    for q in jobs+s['owners']:deadline[q['request_id']]=q['deadline_ns']/NS;priority[q['request_id']]=q['priority']
    for o in s['owners']:
        vec=vectors[o['request_id'],o['route']]
        owners.append(dict(request_id=o['request_id'],task=o['task'],route=o['route'],stage=o['stage'],remaining=max(0.,vec[o['stage']]-o['public_progress_s']),vec=vec))
        if o['response_ns'] is not None:responses[o['request_id']]=o['response_ns']/NS
    work=sum(min(sum(vectors[q['request_id'],r]) for r in ('CPU','GPU')) for q in jobs)
    H=min(case['service_stop_s'],now+max(10.,3*work+3*len(owners)));H=max(H,now+1e-6)
    wait=0.;pending=copy.deepcopy(first);J=heat=0.;peak=state['temperature_c'];steps=0
    def free(route):return sum(o['route']==route for o in owners)<(3 if route=='CPU' else 1)
    def dispatch(q,route):
        queue.pop(q['request_id']);vec=vectors[q['request_id'],route];owners.append(dict(request_id=q['request_id'],task=q['task'],route=route,stage=0,remaining=vec[0],vec=vec))
    while now<H-1e-10:
        steps+=1
        if steps>800:break
        for o in owners.copy():
            while o['remaining']<=1e-10:
                if (o['task']=='C' and o['stage']==1) or (o['task']=='D' and o['stage']==2):responses[o['request_id']]=now
                o['stage']+=1
                if o['stage']==5:owners.remove(o);finished.add(o['request_id']);break
                o['remaining']=o['vec'][o['stage']]
        if pending:
            a=pending;pending=None
            if a['kind']=='DISPATCH':dispatch(queue[a['request_id']],a['route'])
            elif a['kind']=='WAIT':wait=now+a['wait_ns']/NS
            else:wait=min(H,now+.5,now+min((sum(o['vec'][o['stage']:])-o['vec'][o['stage']]+o['remaining'] for o in owners),default=.5))
        if now>=wait-1e-10 and queue:
            # Same causal continuation for every alternative: EDF request,
            # cheapest public route that can meet its deadline, otherwise best
            # response. A busy cheaper route may be awaited if still feasible.
            while queue:
                q=min(queue.values(),key=lambda q:(q['deadline_ns'],*tie(q)));opts=[]
                for route in ('CPU','GPU'):
                    vec=vectors[q['request_id'],route];load=sorted(sum(o['vec'][o['stage']:])-o['vec'][o['stage']]+o['remaining'] for o in owners if o['route']==route)
                    release=load[0] if not free(route) else 0.
                    f=physics.speed(state['temperature_c'],route,1,q['task']);resp=sum(vec[:2 if q['task']=='C' else 3])-vec[1]+vec[1]/f
                    power=physics.solo[('classification' if q['task']=='C' else 'detection')+'_'+route]
                    score=power*sum(vec)/.35+12*max(0,now+release+resp-q['deadline_ns']/NS)/max(.05,(q['deadline_ns']-q['scheduled_arrival_ns'])/NS)
                    opts.append((score,release,route))
                _,release,route=min(opts)
                if release>1e-10:break
                dispatch(q,route)
        if not owners:
            dt=H-now if not queue else min(H-now,max(.001,wait-now))
        else:
            rates=physics.rates(state['temperature_c'],owners)
            dt=min(H-now,.5,min(max(1e-9,o['remaining']/rates[o['request_id']]) for o in owners))
            if wait>now+1e-10:dt=min(dt,wait-now)
        state,terms=physics.transition(state,owners,dt)
        for o in owners:o['remaining']=max(0.,o['remaining']-dt*terms['speeds'][o['request_id']])
        J+=terms['increment'];heat+=terms['temperature_area']-physics.c.idle_c*dt;peak=max(peak,terms['peak']);now+=dt
    n=max(1,len(deadline));cost=[J/n,max(0.,heat)/(H-start)/10,0.,0.,len(set(deadline)-finished)/n]
    for rid,due in deadline.items():
        q=next((x for x in jobs if x['request_id']==rid),None);ttl=max(.05,(due-q['scheduled_arrival_ns']/NS) if q else 1.);late=max(0.,responses.get(rid,H)-due)
        g=2 if priority[rid]=='U' else 3;den=max(1,sum(p==priority[rid] for p in priority.values()));cost[g]+=(float(rid not in responses or late>1e-8)+.02*min(5,late/ttl))/den
    return dict(cost=cost,AP_end=state['temperature_c'],peak=peak,H_s=H,steps=steps,capped=steps>800,visible_ids=sorted(deadline),no_future_arrivals=True,no_future_latents=True)
