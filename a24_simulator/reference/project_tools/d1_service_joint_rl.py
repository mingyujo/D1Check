"""Fresh semantic PPO on the new JointList service envelope, not old extension."""
import copy
from tools import d1_rolling_list_rl as r
from tools import d1_service_joint_rl_cost as objective
from tools import d1_service_envelope_policy as e

SCHEMA=r.c.digest(dict(parent_policy_schema=e.SCHEMA,objective=objective.OBJECTIVE,costs=objective.COST_CHANNELS,architecture='same56/8x28/critic6',fresh=True))
POLICY='JOINT_SERVICE_ENVELOPE_ABSOLUTE_MASKED_PPO_V2'

class Controller(e.Controller):
    def __init__(self,frozen,initial,network=None,deterministic=True):
        super().__init__(frozen,initial,r.PPO,network,deterministic)
        self.schema_id=SCHEMA;self.public_policy=POLICY
    def encode(self,*args,**kwargs):
        out=super().encode(*args,**kwargs);out['schema_id']=SCHEMA;return out

class Learner(r.training.Learner):
    def fresh_controller(self,frozen,initial):return Controller(frozen,initial,self.network,False)
