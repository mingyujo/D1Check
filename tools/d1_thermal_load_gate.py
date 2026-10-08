"""Causal workload/admission guard on the frozen0.25s thermal slack policy.

Recent interarrival gaps are estimates, never knowledge of the next arrival.
All measured contexts and actual capacity boundaries remain the frozen plant.
"""
from tools import d1_thermal_slack_v3 as old
POLICY='IE_BAND_EDD_SLACK_LOAD_GATE_025_V3_1'

class Controller(old.Controller):
    def __init__(self,frozen,initial):
        super().__init__(frozen,initial,old.SHORT);self.public_policy=POLICY
        self.arrival_history={};self.gate_records=[]

    def decide(self,config,queue,lanes,now,settings,thermal_model,current_ap):
        self.validate_public(queue,lanes,now)
        for q in list(queue)+[l['request'] for l in lanes.values() if l['request']]:self.arrival_history.setdefault(q['id'],q['arrival_ns'])
        return super().decide(config,queue,lanes,now,settings,thermal_model,current_ap)

    def physical_candidates(self,queue,lanes,now,base):
        actions=super().physical_candidates(queue,lanes,now,base)
        if not any(a['kind']=='cool_wait' for a in actions):return actions
        times=sorted(self.arrival_history.values());gaps=[(b-a)/1e9 for a,b in zip(times,times[1:])][-8:]
        window=min(gaps)-(now-times[-1])/1e9 if len(times)>=3 else None
        work=sum(max(sum(profile[old.p.key(q,'CPU')])/1e9 for profile in self.profiles.values()) for q in queue if len(old.p.backends(q))==1)
        allowed=window is not None and window>=work+self.credit+old.EPS
        self.gate_records.append(dict(now_ns=now,observed_arrivals=len(times),minimum_recent_gap_s=min(gaps) if gaps else None,remaining_window_s=window,
            queued_cpu_work_long_s=work,cooling_credit_s=self.credit,allowed=allowed))
        return actions if allowed else [a for a in actions if a['kind']!='cool_wait']

    @staticmethod
    def select(actions):
        base=next(a for a in actions if a['base'])
        safe=[a for a in actions if a['kind']!='cool_wait' or all(a['forecasts'][ctx].get('feasible',False) and base['forecasts'][ctx].get('feasible',False) for ctx in old.core.CONTEXTS)]
        return old.Controller.select(safe)
