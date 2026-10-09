"""Bounded joint rolling plans with original measured plant and exact AP cost.

EDD within each task, <=4 request prefix, legal routing and <=one normal idle
slot. A deterministic mean screen chooses8 plans for full3-context evaluation.
This is a finite list-restricted heuristic, not a global scheduling optimum.
"""
import copy,itertools,math,time
from tools import d1_fast_thermal_forecast as fast
p=fast.p;core=fast.old.core;PHASES=fast.PHASES;EPS=fast.EPS
LightBand=fast.LightBand;ProjectionUnavailable=fast.ProjectionUnavailable
WAIT='IE_ROLLING_JOINT_THERMAL_PLAN4_WAIT025_V1'
NOWAIT='IE_ROLLING_JOINT_THERMAL_PLAN4_NOWAIT_V1'
def project_plan(estimates, profiles, queue, public_lanes, now_ns, plan, context, band):
    """Hypothetical Band suffix against one declared possible plant context.

    Running phases use mean residuals on mean/short paths and long on long.
    An already elapsed predicted phase end is unavailable, never a fake zero.
    The observed phase cannot be moved backwards or progressed retroactively.
    """
    qlist = copy.deepcopy(queue)
    now = float(now_ns)
    virtual = {'CPU': None, 'GPU': None}
    jobs, responses, transitions, dispatches = {}, {}, [], []
    for b, lane in public_lanes.items():
        if lane['request'] is None:
            continue
        q = copy.deepcopy(lane['request'])
        ds = profiles['long_context' if context == 'long_context' else 'mean'][p.key(q, b)]
        stage = PHASES.index(lane['phase'])
        next_at = lane['dispatch'] + sum(ds[:stage+1])
        if next_at <= now + .0001:
            raise ProjectionUnavailable('observed_phase_residual_unavailable')
        virtual[b] = dict(ticket=q, stage=stage, since=lane['since'], dispatch=lane['dispatch'],
                          durations=ds, next_at=next_at)
        responded = stage >= (2 if q['priority'] == 'urgent' else 3)
        jobs[q['id']] = dict(id=q['id'], state=q['task']+'_'+b, backend=b, start=now/1e9,
                             already_responded=responded, deadline=(q['arrival_ns']+q['deadline_offset_ns'])/1e9)

    delegate = LightBand(band, estimates)
    prefix = copy.deepcopy(plan)
    plan_timer = None
    if len({j['request_id'] for j in prefix})!=len(prefix) or any(j['request_id'] not in {q['id'] for q in qlist} for j in prefix):raise ProjectionUnavailable('invalid_plan_requests')
    wake = None

    def public():
        return {b: dict(request=x['ticket'] if x else None,
                        phase=PHASES[x['stage']] if x else 'AVAILABLE',
                        since=x['since'] if x else now, dispatch=x['dispatch'] if x else None)
                for b, x in virtual.items()}

    def dispatch(selected):
        nonlocal qlist
        b = selected['backend']
        if virtual[b] is not None:
            raise ValueError('projection double lane assignment')
        q = next(q for q in qlist if q['id'] == selected['request_id'])
        p.state([x['ticket']['task']+'_'+lane for lane, x in virtual.items() if x] + [q['task']+'_'+b])
        qlist = [x for x in qlist if x['id'] != q['id']]
        ds = profiles[context][p.key(q, b)]
        virtual[b] = dict(ticket=q, stage=0, since=now, dispatch=now, durations=ds, next_at=now+ds[0])
        jobs[q['id']] = dict(id=q['id'], state=q['task']+'_'+b, backend=b, start=now/1e9,
                             already_responded=False, deadline=(q['arrival_ns']+q['deadline_offset_ns'])/1e9)
        dispatches.append(dict(request_id=q['id'], backend=b, at_ns=round(now)))

    for _ in range(10000):
        progressed = False
        for b in ('CPU', 'GPU'):
            x = virtual[b]
            while x and x['next_at'] <= now+.0001:
                stage, q = x['stage'], x['ticket']
                transitions.append(dict(request_id=q['id'], backend=b, stage=stage, at_ns=round(now)))
                if stage == (1 if q['priority'] == 'urgent' else 2) and not jobs[q['id']]['already_responded']:
                    responses[q['id']] = round(now)/1e9
                if stage == 4:
                    jobs[q['id']]['end'] = now/1e9
                    virtual[b] = None
                    x = None
                else:
                    x['stage'] += 1
                    x['since'] = now
                    x['next_at'] = now+x['durations'][x['stage']]
                progressed = True
        delegate.observe(now, public())
        if wake is not None and wake <= now:wake=None
        if prefix:
            step=prefix[0];b=step['backend'];q=next(q for q in qlist if q['id']==step['request_id'])
            legal=virtual[b] is None
            try:p.state([v['ticket']['task']+'_'+backend for backend,v in virtual.items() if v]+[q['task']+'_'+b])
            except ValueError:legal=False
            if legal:
                delay=step.get('delay_ns',0.)
                if delay and plan_timer is None:
                    if any(virtual.values()) or any(q['priority']=='urgent' for q in qlist):raise ProjectionUnavailable('cooling_not_executable_in_declared_space')
                    plan_timer=now+delay
                if plan_timer is None or plan_timer<=now+.0001:
                    dispatch(prefix.pop(0));plan_timer=None;continue
        elif qlist:
            out=delegate.decide(None,qlist,public(),now,{},None,None);wake=out.get('wait_until_ns')
            if out['selected']:dispatch(out['selected']);continue
        if not qlist and not any(virtual.values()):
            break
        events = [x['next_at'] for x in virtual.values() if x]
        if plan_timer is not None and plan_timer>now:events.append(plan_timer)
        if wake is not None:
            events.append(wake)
        if not events:
            raise ProjectionUnavailable('projection_has_no_progress_event')
        nxt = min(events)
        if nxt <= now or not math.isfinite(nxt):
            raise ProjectionUnavailable('projection_nonpositive_time_progress')
        now = nxt
    else:
        raise ProjectionUnavailable('projection_event_bound')
    if any('end' not in j for j in jobs.values()):
        raise ProjectionUnavailable('projection_incomplete')
    for rid, response in responses.items():
        jobs[rid]['response'] = response
    pending = [j for j in jobs.values() if not j['already_responded']]
    if any('response' not in j for j in pending):
        raise ProjectionUnavailable('projection_missing_response')
    return dict(jobs=list(jobs.values()), dispatches=dispatches, transitions=transitions,
                deadline_misses=sum(j['response'] > j['deadline']+EPS for j in pending),
                lane_end_s=max((j['end'] for j in jobs.values()), default=now_ns/1e9))

def window_requests(controller,queue,lanes,now):
    ordered=sorted(queue,key=core.due);window=ordered[:4];active=controller.active_jobs(lanes,now/1e9)
    only=[q for q in ordered if len(p.backends(q))==1]
    if only and active is not None:
        protected=min(only,key=lambda q:((q['arrival_ns']+q['deadline_offset_ns'])/1e9-controller.place(q,'CPU',now/1e9,active)['response'],core.due(q)))
        if protected not in window:window[-1]=protected
    return sorted(window,key=core.due)

def candidate_plans(window,credit,allow_wait):
    groups=[sorted([q for q in window if q['task']==task],key=core.due) for task in ('classification','detection')]
    orders=[]
    def merge(a,b,current):
        if not a and not b:orders.append(current);return
        if a:merge(a[1:],b,current+[a[0]])
        if b:merge(a,b[1:],current+[b[0]])
    merge(*groups,[]);plans=[]
    for order in orders:
        for assignment in itertools.product(*(p.backends(q) for q in order)):
            plain=[dict(request_id=q['id'],backend=b,delay_ns=0.) for q,b in zip(order,assignment)];plans.append(plain)
            if allow_wait:
                for i,q in enumerate(order):
                    if q['priority']!='normal':continue
                    delayed=copy.deepcopy(plain);delay=credit if i==0 else .25
                    if delay>EPS:delayed[i]['delay_ns']=delay*1e9;plans.append(delayed)
    assert len(plans)<=72
    return plans

def forecast_plan(controller,queue,lanes,now,plan,context):
    if controller.execution_deadline is not None and time.monotonic()>=controller.execution_deadline:raise TimeoutError('rolling planner save boundary')
    controller.projection_calls+=1;started=time.perf_counter()
    try:
        result=project_plan(controller.estimates,controller.profiles,queue,lanes,now,plan,context,controller.band)
        value=fast.costs(controller,result['jobs'],now);by={q['id']:q for q in list(queue)+[l['request'] for l in lanes.values() if l['request']]}
        pending=[j for j in result['jobs'] if not j['already_responded']];urgent=sorted([r['response_ms'] for r in controller.observed_responses.values() if r['priority']=='urgent']+[(j['response']-by[j['id']]['arrival_ns']/1e9)*1000 for j in pending if by[j['id']]['priority']=='urgent'])
        normals=[(j['response']-by[j['id']]['arrival_ns']/1e9)*1000 for j in pending if by[j['id']]['priority']=='normal']
        return dict(valid=True,**value,lane_end_s=result['lane_end_s'],deadline_misses=result['deadline_misses'],
            urgent_misses=sum(j['response']>j['deadline']+EPS for j in pending if by[j['id']]['priority']=='urgent'),normal_misses=sum(j['response']>j['deadline']+EPS for j in pending if by[j['id']]['priority']=='normal'),
            urgent_p95_ms=urgent[math.ceil(.95*len(urgent))-1] if urgent else None,normal_mean_ms=sum(normals)/len(normals) if normals else None,dispatches=result['dispatches'])
    except ProjectionUnavailable as error:return dict(valid=False,reason=str(error))
    finally:controller.projection_seconds+=time.perf_counter()-started

def acceptable(f,r):
    if not f['valid'] or not r['valid']:return False
    return (f['lane_end_s']<=120.+EPS and f['urgent_misses']<=r['urgent_misses'] and f['normal_misses']<=r['normal_misses'] and
        (f['urgent_p95_ms'] is None or r['urgent_p95_ms'] is None or f['urgent_p95_ms']<=r['urgent_p95_ms']+EPS) and
        f['remaining_increment_j']<=r['remaining_increment_j']+EPS and f['global_peak_ap_c']<=r['global_peak_ap_c']+EPS)

class Controller(fast.old.Controller):
    def __init__(self,frozen,initial,policy):
        if policy not in (WAIT,NOWAIT):raise ValueError('unknown rolling policy')
        super().__init__(frozen,initial,fast.old.SHORT);self.public_policy=policy;self.allow_wait=policy==WAIT
        self.plan_records=[];self.hold=None

    def signature(self,queue,lanes):return (tuple(sorted(q['id'] for q in queue)),tuple((b,l['request']['id'] if l['request'] else None) for b,l in lanes.items()))

    def decide(self,config,queue,lanes,now,settings,thermal_model,current_ap):
        self.validate_public(queue,lanes,now)
        if self.pending:
            pending,self.pending=self.pending,None;first,second=pending['first'],pending['second']
            if now==pending['now_ns'] and lanes[first['backend']]['request'] and lanes[first['backend']]['request']['id']==first['request_id'] and lanes[second['backend']]['request'] is None and any(q['id']==second['request_id'] for q in queue):
                p.state([l['request']['task']+'_'+b for b,l in lanes.items() if l['request']]+[next(q['task'] for q in queue if q['id']==second['request_id'])+'_'+second['backend']])
                return dict(now_ns=now,selected=second,reason='rolling_bundle_commit',action_kind='bundle_commit')
        signature=self.signature(queue,lanes)
        if self.hold and self.hold['signature']==signature:
            until=self.hold.get('until_ns')
            if until is None or now<until:return dict(now_ns=now,selected=None,reason='rolling_hold_until_arrival_or_lane_release',**({'wait_until_ns':until} if until is not None else {}))
        self.hold=None;base=self.band.decide(config,queue,lanes,now,settings,thermal_model,current_ap)
        if not queue or not self.response_counters_valid or self.active_jobs(lanes,now/1e9) is None:return dict(base,public_policy=self.public_policy,forced=True)
        members=[l['request']['task']+'_'+b for b,l in lanes.items() if l['request']];legal=False
        for q in queue:
            for b in p.backends(q):
                if lanes[b]['request'] is not None:continue
                try:p.state(members+[q['task']+'_'+b]);legal=True
                except ValueError:pass
        if not legal:return dict(base,public_policy=self.public_policy)
        references={ctx:fast.forecast(self,queue,lanes,now,dict(jobs=[]),ctx) for ctx in core.CONTEXTS}
        if not all(f['valid'] for f in references.values()):return dict(base,public_policy=self.public_policy,forced=True)
        window=window_requests(self,queue,lanes,now);plans=candidate_plans(window,self.credit,self.allow_wait);screened=[]
        for i,plan in enumerate(plans):
            f=forecast_plan(self,window,lanes,now,plan,'mean')
            if not f['valid']:continue
            first=(plan[0]['request_id'],plan[0]['backend'],plan[0]['delay_ns'])
            screened.append(((f['urgent_misses'],f['normal_misses'],f['remaining_increment_j'],f['peak_ap_c'],f['urgent_p95_ms'] or 0.,i),first,plan))
        screened.sort(key=lambda item:item[0]);shortlist=[];per_first={}
        for _,first,plan in screened:
            if per_first.get(first,0)>=2:continue
            shortlist.append(plan);per_first[first]=per_first.get(first,0)+1
            if len(shortlist)==8:break
        chosen=None;best=None;chosen_forecasts=None
        for index,plan in enumerate(shortlist):
            forecasts={ctx:forecast_plan(self,queue,lanes,now,plan,ctx) for ctx in core.CONTEXTS}
            if not all(acceptable(forecasts[ctx],references[ctx]) for ctx in core.CONTEXTS):continue
            delta=max(forecasts[ctx]['peak_ap_c']-references[ctx]['peak_ap_c'] for ctx in core.CONTEXTS)
            j=max(forecasts[ctx]['remaining_increment_j']-references[ctx]['remaining_increment_j'] for ctx in core.CONTEXTS)
            if delta>=-EPS and j>=-EPS:continue
            key=(delta,j,max(f['normal_mean_ms'] or 0. for f in forecasts.values()),index)
            if best is None or key<best:best=key;chosen=plan;chosen_forecasts=forecasts
        record=dict(now_ns=now,window_ids=[q['id'] for q in window],candidate_count=len(plans),screen_valid=len(screened),full_plan_count=len(shortlist),selected_plan=chosen,
            score=list(best) if best else None,forecast_metrics={ctx:{k:f[k] for k in ('peak_ap_c','global_peak_ap_c','remaining_increment_j','urgent_misses','normal_misses','urgent_p95_ms')} for ctx,f in (chosen_forecasts or references).items()})
        self.plan_records.append(record)
        if chosen is None:return dict(base,public_policy=self.public_policy)
        first=chosen[0];q=next(q for q in queue if q['id']==first['request_id']);b=first['backend']
        if first['delay_ns']:
            until=now+first['delay_ns'];self.cool_since=now;self.hold=dict(signature=signature,until_ns=until)
            return dict(now_ns=now,selected=None,wait_until_ns=until,reason=self.public_policy,action_kind='cool_wait')
        try:
            if lanes[b]['request'] is not None:raise ValueError('owned')
            p.state(members+[q['task']+'_'+b])
        except ValueError:
            self.hold=dict(signature=signature);return dict(now_ns=now,selected=None,reason='rolling_selected_resource_wait')
        jobs=[dict(request_id=q['id'],backend=b)]
        if len(chosen)>1 and not chosen[1]['delay_ns']:
            second=chosen[1];other=next(q for q in queue if q['id']==second['request_id']);ob=second['backend']
            if lanes[ob]['request'] is None and ob!=b:
                try:p.state(members+[q['task']+'_'+b,other['task']+'_'+ob]);jobs.append(dict(request_id=other['id'],backend=ob))
                except ValueError:pass
        return self._reply(dict(kind='bundle' if len(jobs)==2 else 'single',jobs=jobs,base=False),now)
