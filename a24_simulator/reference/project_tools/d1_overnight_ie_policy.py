"""Two conservative list-selector variants; old rule/PPO source is untouched.

R1 refuses cooling under unknown observed CPU-only arrival load. R2 also
refuses any current-request predicted response delay versus the same L0
continuation in all three calibrated profile contexts. This is a separately
identified conservative action restriction, not a future deadline guarantee.
"""
from tools import d1_rolling_list_rl as r

R1='IE_ROLLING_OBSERVED_LOAD_COOLING_V1'
R2='IE_ROLLING_CURRENT_RESPONSE_PRESERVE_V1'


class Controller(r.Controller):
    def __init__(self,frozen,initial,variant=R1):
        if variant not in (R1,R2):raise ValueError('unknown variant')
        super().__init__(frozen,initial,r.RULE)
        self.variant=variant;self.public_policy=variant

    def admission(self,action,forecasts,refs,queue,now,risk):
        allowed,reason=super().admission(action,forecasts,refs,queue,now,risk)
        if not allowed:return allowed,reason
        if action['kind']=='cool_wait' and not risk['known']:
            return False,'unknown_observed_CPU_load_no_cooling'
        if self.variant==R2:
            for f,ref in zip(forecasts,refs):
                for q in queue:
                    if f['responses'][q['id']]>ref['responses'][q['id']]+1e-9:
                        return False,'current_response_preservation'
        return True,'conservative_current_state_prediction_not_guarantee'
