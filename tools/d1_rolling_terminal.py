"""Common-time terminal AP/state constraint on the frozen rolling prefix.

The calibrated model has g=0: future workloads do not drive h. No coefficient
is added. Terminal h remains visible in the audit but is not an independent
workload-memory signal in this model. Same-input continuation is conditional.
"""
import math,time
from tools import d1_rolling_prefix_guard as prefix
old=prefix.old;p=old.p;CONTEXTS=old.core.CONTEXTS;EPS=old.EPS
POLICY='IE_ROLLING_PREFIX_COMMON_TERMINAL_AP_V3'

def terminal_state(controller,jobs,now_ns,end_s):
    start=now_ns/1e9
    if not math.isfinite(end_s) or end_s<start or any(j['end']>end_s+EPS for j in jobs):raise ValueError('incomplete common terminal window')
    t,h=controller.t,controller.h;slopes=controller.frozen['ap']['parameters']['ap_slope_at_30_c_per_s']
    for s in p.segments(jobs,start,end_s):
        label='resident_idle' if s['state']=='idle' else s['state']
        if label not in slopes:raise old.ProjectionUnavailable('unsupported_terminal_state')
        t,h=p.thermal_step(t,h,slopes[label]-slopes['resident_idle'],controller.init['reference_c'],controller.frozen['ap'],s['end_s']-s['start_s'])
    return dict(ap_c=t,h_c_per_s=h)

def terminal_pair(controller,queue,lanes,now,plan,context):
    if controller.execution_deadline is not None and time.monotonic()>=controller.execution_deadline:raise TimeoutError('terminal save boundary')
    try:
        reference=old.fast.project(controller.estimates,controller.profiles,queue,lanes,now,dict(jobs=[]),context,controller.band)
        candidate=old.project_plan(controller.estimates,controller.profiles,queue,lanes,now,plan,context,controller.band)
        end=max(reference['lane_end_s'],candidate['lane_end_s'])
        if end>120.+EPS:return dict(valid=False,reason='common_terminal_beyond_horizon')
        a=terminal_state(controller,reference['jobs'],now,end);b=terminal_state(controller,candidate['jobs'],now,end)
        dt=b['ap_c']-a['ap_c'];dh=b['h_c_per_s']-a['h_c_per_s']
        return dict(valid=True,common_end_s=end,baseline_lane_end_s=reference['lane_end_s'],candidate_lane_end_s=candidate['lane_end_s'],
            baseline=a,candidate=b,delta_ap_c=dt,delta_h_c_per_s=dh,passed=dt<=EPS and dh<=EPS)
    except old.ProjectionUnavailable as e:return dict(valid=False,reason=str(e))

def assess(controller,queue,lanes,now,plan,first,references,first_guard_pass):
    pairs={c:terminal_pair(controller,queue,lanes,now,plan,c) for c in CONTEXTS}
    valid=all(f.get('valid',False) and references[c].get('valid',False) for c,f in first.items())
    delta_ap=max(first[c]['peak_ap_c']-references[c]['peak_ap_c'] for c in CONTEXTS) if valid else None
    delta_j=max(first[c]['remaining_increment_j']-references[c]['remaining_increment_j'] for c in CONTEXTS) if valid else None
    strict=valid and (delta_ap<-EPS or delta_j<-EPS)
    terminal_pass=all(r.get('valid',False) and r.get('passed',False) for r in pairs.values())
    return dict(first_guard_pass=first_guard_pass,terminal_pass=terminal_pass,first_prefix_strict_gain=strict,
        useful=first_guard_pass and terminal_pass and strict,worst_first_AP_delta_c=delta_ap,worst_first_J_delta=delta_j,
        contexts=pairs,unchanged_g=controller.frozen['ap']['g'])

class Controller(prefix.Controller):
    """One extra terminal guard; no new rule for weights, routing or workload."""
    def __init__(self,frozen,initial):
        super().__init__(frozen,initial);self.public_policy=POLICY;self.terminal_records=[];self.terminal_blocks=0
    def decide(self,config,queue,lanes,now,settings,thermal_model,current_ap):
        count=len(self.prefix_guard_records);reply=super().decide(config,queue,lanes,now,settings,thermal_model,current_ap)
        if count==len(self.prefix_guard_records) or not self.prefix_guard_records[-1]['passed']:return reply
        record=self.prefix_guard_records[-1];pairs={c:terminal_pair(self,queue,lanes,now,record['actual_prefix'],c) for c in CONTEXTS}
        passed=all(r.get('valid',False) and r.get('passed',False) for r in pairs.values());self.terminal_records.append(dict(now_ns=now,passed=passed,contexts=pairs))
        if passed:return reply
        self.pending=None;self.hold=None;self.cool_since=None;self.terminal_blocks+=1
        base=self.band.decide(config,queue,lanes,now,settings,thermal_model,current_ap)
        return dict(base,public_policy=self.public_policy,terminal_guard_blocked=True)
