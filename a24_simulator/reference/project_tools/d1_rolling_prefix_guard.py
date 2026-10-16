"""Joint rolling proposal plus three-context guard for the actual first prefix.

Only this guard is new. Old shortlist, window, credit, plant and global KPIs are
unchanged. A local forecast guard does not guarantee future arrivals or SLA.
"""
import copy
from tools import d1_rolling_joint_thermal as old
POLICY='IE_ROLLING_JOINT_ACTUAL_PREFIX_GUARD_WAIT025_V2'

def actual_prefix(plan,reply,pending,now):
    pair=bool(reply.get('selected') and pending and pending['now_ns']==now and pending['first']==reply['selected'])
    return copy.deepcopy(plan[:2 if pair else 1])

class Controller(old.Controller):
    def __init__(self,frozen,initial):
        super().__init__(frozen,initial,old.WAIT);self.public_policy=POLICY
        self.prefix_guard_records=[];self.prefix_blocked_calls=0
    def decide(self,config,queue,lanes,now,settings,thermal_model,current_ap):
        n=len(self.plan_records);reply=super().decide(config,queue,lanes,now,settings,thermal_model,current_ap)
        if len(self.plan_records)==n or self.plan_records[-1]['selected_plan'] is None:return reply
        record=self.plan_records[-1];plan=actual_prefix(record['selected_plan'],reply,self.pending,now)
        refs={c:old.fast.forecast(self,queue,lanes,now,dict(jobs=[]),c) for c in old.core.CONTEXTS}
        first={c:old.forecast_plan(self,queue,lanes,now,plan,c) for c in old.core.CONTEXTS}
        passed=all(old.acceptable(first[c],refs[c]) for c in old.core.CONTEXTS)
        keys=('valid','reason','peak_ap_c','global_peak_ap_c','remaining_increment_j','urgent_misses','normal_misses','urgent_p95_ms','lane_end_s')
        self.prefix_guard_records.append(dict(now_ns=now,actual_prefix=plan,passed=passed,
            references={c:{k:v for k,v in f.items() if k in keys} for c,f in refs.items()},
            first={c:{k:v for k,v in f.items() if k in keys} for c,f in first.items()}))
        record['actual_prefix_guard_pass']=passed
        if passed:return reply
        # Undo a proposed same-time bundle/hold/cooling reservation before Band.
        # No dispatched job is touched; this check runs before returning a reply.
        self.pending=None;self.hold=None;self.cool_since=None;self.prefix_blocked_calls+=1
        base=self.band.decide(config,queue,lanes,now,settings,thermal_model,current_ap)
        return dict(base,public_policy=self.public_policy,prefix_guard_blocked=True)
