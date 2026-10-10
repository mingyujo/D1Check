"""Online CPU/GPU adapter selecting the actually executed prefix, not a full plan.

Original window4/shortlist8, measured coefficients and support remain intact.
Only a single action/same-time pair or an interruptible hold is committed.
"""
import copy,time
from tools import d1_rolling_prefix_opportunity as project
from tools import d1_rolling_prefix_selection as selector
from tools.d1_rolling_prefix_opportunity_study import state_key
old=project.old;p=old.p
POLICY='IE_ROLLING_EXECUTION_PREFIX_GLOBAL_KPI_WAIT025_V1'
class Controller(old.Controller):
    def __init__(self,frozen,initial):
        super().__init__(frozen,initial,old.WAIT);self.public_policy=POLICY
        self.prefix_choices=[];self.execution_prefix_projection_calls=0;self.execution_prefix_projection_seconds=0.
        self.interrupted_holds=0
    def _prefix_forecast(self,queue,lanes,now,action,context,key):
        if self.execution_deadline is not None and time.monotonic()>=self.execution_deadline:raise TimeoutError('prefix planner save boundary')
        began=time.perf_counter();self.execution_prefix_projection_calls+=1
        try:return project.forecast(self,queue,lanes,now,action,context,key)
        finally:self.execution_prefix_projection_seconds+=time.perf_counter()-began
    def choose_prefix(self,queue,lanes,now,base):
        if not queue or not self.response_counters_valid or self.active_jobs(lanes,now/1e9) is None:return None
        members=[l['request']['task']+'_'+b for b,l in lanes.items() if l['request']]
        legal=False
        for q in queue:
            for b in p.backends(q):
                if lanes[b]['request'] is not None:continue
                try:p.state(members+[q['task']+'_'+b]);legal=True
                except ValueError:pass
        if not legal:return None
        key=state_key(self,queue,lanes,now)
        references={c:old.fast.forecast(self,queue,lanes,now,dict(jobs=[]),c) for c in selector.CONTEXTS}
        if not all(f['valid'] for f in references.values()):return None
        for f in references.values():f['state_key']=key
        window=old.window_requests(self,queue,lanes,now);plans=old.candidate_plans(window,self.credit,True);screened=[]
        for index,plan in enumerate(plans):
            f=old.forecast_plan(self,window,lanes,now,plan,'mean')
            if f['valid']:
                score=(f['urgent_misses'],f['normal_misses'],f['remaining_increment_j'],f['peak_ap_c'],f['urgent_p95_ms'] or 0.,index)
                first=(plan[0]['request_id'],plan[0]['backend'],plan[0]['delay_ns']);screened.append((score,first,index,plan))
        seen={};short=[]
        for _,first,index,plan in sorted(screened,key=lambda r:r[0]):
            if seen.get(first,0)>=2:continue
            seen[first]=seen.get(first,0)+1;short.append((index,plan))
            if len(short)==8:break
        unique={}
        for index,plan in short:
            action=project.actual_action(self,plan,queue,lanes,now)
            if action is not None:unique.setdefault(selector.signature(action),(index,action))
        candidates=[]
        for index,action in unique.values():
            forecasts={c:self._prefix_forecast(queue,lanes,now,action,c,key) for c in selector.CONTEXTS}
            candidates.append(dict(ordinal=index,action=action,state_key=key,forecasts=forecasts,
                semantics=selector.DISPATCH if action['kind'] in ('single','bundle') else selector.WAIT))
        band=dict(kind='single',jobs=[base['selected']]) if base['selected'] else dict(kind='band_event_wait')
        selected=selector.select(candidates,references,band,past_peak_c=max(self.grid.values(),default=self.t),state_key=key,now_ns=now)
        self.prefix_choices.append(dict(now_ns=now,state_key=key,window_ids=[q['id'] for q in window],
            candidate_count=len(plans),screen_valid=len(screened),shortlist_count=len(short),unique_prefixes=len(unique),
            chosen=selected['chosen'],score=selected.get('score'),reason=selected['reason'],admissible=selected['admissible'],
            future_only=selected['future_only'],rejected=selected.get('rejected',[]),predicted_service_guarantee=False))
        return copy.deepcopy(selected['chosen']['action']) if selected['chosen'] else None
    def apply_prefix(self,action,queue,lanes,now,base):
        kind=action['kind'];signature=self.signature(queue,lanes)
        if kind=='cool_wait':
            until=action['until_ns']
            if (until<=now or (until-now)/1e9>self.credit+selector.EPS or any(l['request'] for l in lanes.values())
                or any(q['priority']=='urgent' for q in queue)):
                return dict(base,public_policy=POLICY,prefix_application_rejected=True)
            self.cool_since=now;self.hold=dict(signature=signature,until_ns=until)
            return dict(now_ns=now,selected=None,wait_until_ns=until,reason=POLICY,action_kind='cool_wait')
        if kind=='resource_wait':
            if not any(l['request'] for l in lanes.values()):return dict(base,public_policy=POLICY,prefix_application_rejected=True)
            self.hold=dict(signature=signature)
            return dict(now_ns=now,selected=None,reason='execution_prefix_resource_hold',action_kind='resource_wait')
        if kind not in ('single','bundle'):return dict(base,public_policy=POLICY,prefix_application_rejected=True)
        by={q['id']:q for q in queue};members=[l['request']['task']+'_'+b for b,l in lanes.items() if l['request']]
        for job in action['jobs']:
            q=by.get(job['request_id']);b=job['backend']
            if q is None or b not in p.backends(q) or lanes[b]['request'] is not None:
                return dict(base,public_policy=POLICY,prefix_application_rejected=True)
            members.append(q['task']+'_'+b)
        try:p.state(members)
        except ValueError:return dict(base,public_policy=POLICY,prefix_application_rejected=True)
        return self._reply(dict(kind=kind,jobs=copy.deepcopy(action['jobs']),base=False),now)
    def decide(self,config,queue,lanes,now,settings,thermal_model,current_ap):
        self.validate_public(queue,lanes,now)
        if self.pending:
            pending,self.pending=self.pending,None;first,second=pending['first'],pending['second']
            owner=lanes[first['backend']]['request']
            valid=(now==pending['now_ns'] and owner and owner['id']==first['request_id'] and lanes[second['backend']]['request'] is None
                and any(q['id']==second['request_id'] for q in queue))
            if valid:
                members=[l['request']['task']+'_'+b for b,l in lanes.items() if l['request']]
                try:p.state(members+[next(q['task'] for q in queue if q['id']==second['request_id'])+'_'+second['backend']])
                except ValueError:valid=False
            if valid:return dict(now_ns=now,selected=second,reason='execution_prefix_bundle_commit',action_kind='bundle_commit')
            self.cancelled_bundles+=1
        signature=self.signature(queue,lanes)
        if self.hold and self.hold['signature']==signature:
            until=self.hold.get('until_ns')
            if until is None or now<until:
                return dict(now_ns=now,selected=None,reason='execution_prefix_hold_until_arrival_or_available',
                    **({'wait_until_ns':until} if until is not None else {}))
        if self.hold:self.interrupted_holds+=1
        self.hold=None
        base=self.band.decide(config,queue,lanes,now,settings,thermal_model,current_ap)
        action=self.choose_prefix(queue,lanes,now,base)
        return self.apply_prefix(action,queue,lanes,now,base) if action else dict(base,public_policy=POLICY)
