"""Public history restoration and conditional executed-action projections.

No native environment/learning/device starts. Future arrival probes are not
accepted. Wait actions resume Band after their timer/first lane AVAILABLE,
never force the request named by a discarded whole plan.
"""
import copy,math
from tools import d1_rolling_joint_thermal as old
from tools import d1_rolling_prefix_guard as previous
from tools import d1_rolling_prefix_selection as selection
p=old.p;EPS=old.EPS
FIELDS=('execution_start_ns','output_ready_ns','persist_complete_ns','worker_release_ns','lane_available_ns')
LABELS=('EXECUTING','OUTPUT_READY','PERSISTED','WORKER_RELEASED','AVAILABLE')
TICKET_KEYS=('id','ordinal','task','priority','arrival_ns','deadline_offset_ns')

class PublicTape:
    """Consume past recorded public events; no service vectors/remaining times.

    Rounded transition ns use an exactly recorded callback time where present;
    otherwise keep the recorded integer and report that loss of precision.
    """
    def __init__(self,item):
        self.item=item;self.decisions=item['result']['decisions'];self.events={};self.arrivals={}
        self.lanes={b:dict(request=None,phase='AVAILABLE',since=0.,dispatch=None) for b in ('CPU','GPU')}
        self.queue=[];self.callback_index=0;self.rounded_only=0
        callbacks={}
        for d in self.decisions:callbacks.setdefault(round(d['now_ns']),set()).add(d['now_ns'])
        for event in item['result']['transitions']:
            possible=callbacks.get(event['at_ns'],set())
            at=next(iter(possible)) if len(possible)==1 else float(event['at_ns'])
            if len(possible)!=1:self.rounded_only+=1
            self.events.setdefault(at,[]).append(event)
        for q in item['result']['ledger']:
            ticket={k:q[k] for k in TICKET_KEYS};self.arrivals.setdefault(float(q['arrival_ns']),[]).append(ticket)
    def restore(self,controller,index):
        target=self.decisions[index]['now_ns'];frames={0.,target}
        frames.update(t for t in self.events if t<=target)
        frames.update(t for t in self.arrivals if t<=target)
        frames.update(d['now_ns'] for d in self.decisions[:index+1])
        frames.update(d['wait_until_ns'] for d in self.decisions[:index] if d.get('wait_until_ns') is not None and d['wait_until_ns']<=target)
        for now in sorted(frames):
            events=sorted(self.events.get(now,[]),key=lambda e:(e['backend']!='CPU',FIELDS.index(e['event'])))
            for event in events:
                lane=self.lanes[event['backend']]
                if lane['request'] is None or lane['request']['id']!=event['request_id']:raise ValueError('public phase has no matching owner')
                if event['event']=='lane_available_ns':self.lanes[event['backend']]=dict(request=None,phase='AVAILABLE',since=now,dispatch=None)
                else:lane.update(phase=LABELS[FIELDS.index(event['event'])],since=now)
            self.queue.extend(sorted(self.arrivals.get(now,[]),key=lambda q:(q['ordinal'],q['id'])))
            controller.observe(now,copy.deepcopy(self.lanes))
            while self.callback_index<=index and self.decisions[self.callback_index]['now_ns']==now:
                if self.callback_index==index:
                    return copy.deepcopy(self.queue),copy.deepcopy(self.lanes),now
                reply=self.decisions[self.callback_index];self.callback_index+=1
                # Replay recorded choices only. Never call the original planner.
                if reply.get('prefix_guard_blocked'):
                    controller.pending=None;controller.hold=None;controller.cool_since=None
                elif reply.get('action_kind')=='cool_wait':
                    controller.cool_since=now;controller.hold=dict(signature=controller.signature(self.queue,self.lanes),until_ns=reply['wait_until_ns'])
                elif reply.get('reason')=='rolling_selected_resource_wait':
                    controller.hold=dict(signature=controller.signature(self.queue,self.lanes))
                else:controller.hold=None
                if reply.get('selected'):
                    chosen=reply['selected'];q=next(q for q in self.queue if q['id']==chosen['request_id'])
                    if self.lanes[chosen['backend']]['request'] is not None:raise ValueError('public tape dispatch on occupied lane')
                    self.queue.remove(q);self.lanes[chosen['backend']]=dict(request=q,phase='ASSIGNED',since=now,dispatch=now)
                    controller.observe(now,copy.deepcopy(self.lanes))
        raise ValueError('callback not reached')

def actual_action(controller,plan,queue,lanes,now):
    if not plan:return None
    first=plan[0]
    if first.get('delay_ns',0)>0:
        if any(l['request'] for l in lanes.values()) or any(q['priority']=='urgent' for q in queue):return None
        if first['delay_ns']/1e9>controller.credit+EPS:return None
        return dict(kind='cool_wait',until_ns=now+first['delay_ns'],hold_signature=controller.signature(queue,lanes))
    immediate=selection.immediate_action(plan,queue,lanes,now)
    if immediate:return immediate
    return dict(kind='resource_wait',until_ns=None,hold_signature=controller.signature(queue,lanes))

def project(controller,queue,lanes,now_ns,action,context):
    """Conditional current-queue drain; no unknown future arrivals assumed.

    Public running phases use the original mean/long residual convention.
    Only lane AVAILABLE ends a resource hold; phase callbacks do not end it.
    """
    queue=copy.deepcopy(queue);now=float(now_ns);virtual={b:None for b in lanes};jobs={};responses={};dispatches=[]
    for b,lane in lanes.items():
        if lane['request'] is None:continue
        q=copy.deepcopy(lane['request']);ds=controller.profiles['long_context' if context=='long_context' else 'mean'][p.key(q,b)]
        stage=old.PHASES.index(lane['phase']);end=lane['dispatch']+sum(ds[:stage+1])
        if end<=now+.0001:raise old.ProjectionUnavailable('observed_phase_residual_unavailable')
        virtual[b]=dict(ticket=q,stage=stage,since=lane['since'],dispatch=lane['dispatch'],durations=ds,next_at=end)
        jobs[q['id']]=dict(id=q['id'],state=q['task']+'_'+b,backend=b,start=now/1e9,
            already_responded=stage>=(2 if q['priority']=='urgent' else 3),deadline=(q['arrival_ns']+q['deadline_offset_ns'])/1e9)
    delegate=old.LightBand(controller.band,controller.estimates);prefix=list(action.get('jobs',[]));timer=action.get('until_ns')
    holding=action['kind']=='resource_wait';wake=None
    if holding and not any(virtual.values()):raise old.ProjectionUnavailable('resource_hold_without_running_lane')
    if action['kind']=='cool_wait' and (any(virtual.values()) or any(q['priority']=='urgent' for q in queue)):
        raise old.ProjectionUnavailable('cooling_not_executable')
    def public():return {b:dict(request=x['ticket'] if x else None,phase=old.PHASES[x['stage']] if x else 'AVAILABLE',since=x['since'] if x else now,dispatch=x['dispatch'] if x else None) for b,x in virtual.items()}
    def dispatch(selected):
        b=selected['backend'];q=next(q for q in queue if q['id']==selected['request_id'])
        if virtual[b] is not None:raise ValueError('projection double lane assignment')
        p.state([v['ticket']['task']+'_'+backend for backend,v in virtual.items() if v]+[q['task']+'_'+b])
        queue.remove(q);ds=controller.profiles[context][p.key(q,b)]
        virtual[b]=dict(ticket=q,stage=0,since=now,dispatch=now,durations=ds,next_at=now+ds[0])
        jobs[q['id']]=dict(id=q['id'],state=q['task']+'_'+b,backend=b,start=now/1e9,already_responded=False,deadline=(q['arrival_ns']+q['deadline_offset_ns'])/1e9)
        dispatches.append(dict(request_id=q['id'],backend=b,at_ns=round(now)))
    for _ in range(10000):
        released=False
        for b in ('CPU','GPU'):
            v=virtual[b]
            while v and v['next_at']<=now+.0001:
                stage,q=v['stage'],v['ticket']
                if stage==(1 if q['priority']=='urgent' else 2) and not jobs[q['id']]['already_responded']:responses[q['id']]=round(now)/1e9
                if stage==4:jobs[q['id']]['end']=now/1e9;virtual[b]=None;v=None;released=True
                else:v['stage']+=1;v['since']=now;v['next_at']=now+v['durations'][v['stage']]
        delegate.observe(now,public())
        if released:holding=False;timer=None
        if timer is not None and timer<=now:timer=None
        if wake is not None and wake<=now:wake=None
        if prefix:dispatch(prefix.pop(0));continue
        if queue and not holding and timer is None:
            reply=delegate.decide(None,queue,public(),now,{},None,None);wake=reply.get('wait_until_ns')
            if reply['selected']:dispatch(reply['selected']);continue
        if not queue and not any(virtual.values()):break
        events=[v['next_at'] for v in virtual.values() if v]
        if timer is not None:events.append(timer)
        if wake is not None:events.append(wake)
        if not events:raise old.ProjectionUnavailable('no_public_progress_event')
        nxt=min(events)
        if nxt<=now or not math.isfinite(nxt):raise old.ProjectionUnavailable('nonpositive_time_progress')
        now=nxt
    else:raise old.ProjectionUnavailable('projection_event_bound')
    for rid,response in responses.items():jobs[rid]['response']=response
    pending=[j for j in jobs.values() if not j['already_responded']]
    if any('response' not in j or 'end' not in j for j in pending):raise old.ProjectionUnavailable('incomplete_projection')
    return dict(jobs=list(jobs.values()),dispatches=dispatches,lane_end_s=max((j['end'] for j in jobs.values()),default=now_ns/1e9))

def forecast(controller,queue,lanes,now,action,context,state_key):
    try:
        out=project(controller,queue,lanes,now,action,context);value=old.fast.costs(controller,out['jobs'],now)
        known={q['id']:q for q in list(queue)+[l['request'] for l in lanes.values() if l['request']]}
        pending=[j for j in out['jobs'] if not j['already_responded']]
        urg=sorted([r['response_ms'] for r in controller.observed_responses.values() if r['priority']=='urgent']+[(j['response']-known[j['id']]['arrival_ns']/1e9)*1000 for j in pending if known[j['id']]['priority']=='urgent'])
        return dict(valid=True,state_key=state_key,**value,lane_end_s=out['lane_end_s'],
            urgent_misses=sum(j['response']>j['deadline']+EPS for j in pending if known[j['id']]['priority']=='urgent'),
            normal_misses=sum(j['response']>j['deadline']+EPS for j in pending if known[j['id']]['priority']=='normal'),
            urgent_p95_ms=urg[math.ceil(.95*len(urg))-1] if urg else None,dispatches=out['dispatches'])
    except old.ProjectionUnavailable as error:return dict(valid=False,state_key=state_key,reason=str(error))
