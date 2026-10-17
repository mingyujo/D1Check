"""Frozen protection/cost prior plus opportunity census; no NN and no mask edits."""
import copy
from types import SimpleNamespace
import numpy as np
from rl_policy import ProtectedPolicy, protected_bank, FAMILY
from policy import select as select_edf

class Observer(ProtectedPolicy):
    def __init__(self, model, public, thermal, profile, mode):
        # Reuse the complete frozen public observation and bank builder. Only
        # provide the narrow non-learning interface used by its call method.
        helper=SimpleNamespace(torch=None,
            network_digest=lambda net:'NO_NN_FIXED_PRIOR',
            checked_bank=lambda bank,family:bank,
            input_digest=lambda bank:'NOT_A_NETWORK_INPUT_AUDIT')
        controller=SimpleNamespace(frames=[],choose=self.choose)
        holder=SimpleNamespace(net=None,controller=lambda *args:controller)
        super().__init__(model,public,thermal,profile,holder,helper,False,False)
        self.mode=mode;self.opportunities=[]

    def choose(self, bank, now, collect=False):
        initial=np.asarray(bank['physical_mask'],dtype=bool)
        final=bank['mask'];actions=bank['actions']
        dispatch=[int(i) for i in np.flatnonzero(final[:72])]
        if dispatch:
            requests={actions[i]['request_id'] for i in dispatch}
            routes={actions[i]['route'] for i in dispatch}
            before_requests={actions[int(i)]['request_id'] for i in np.flatnonzero(initial[:72])}
            self.opportunities.append(dict(time_ns=now,requests_before=len(before_requests),
                requests_after=len(requests),free_routes=len(routes),
                two_physical_routes=bool(initial[:72:3].any() and initial[1:72:3].any()),
                multiple_dispatch_actions=len(dispatch)>1,
                voluntary_WAIT_allowed=bool(final[72:75].any()),
                removed_actions=bank['diagnostic']['protection']['removed_actions'],
                critical_focus=bank['diagnostic']['protection']['critical_request'] is not None))
        if self.mode=='COST_PRIOR':
            return int(max(np.flatnonzero(final),key=lambda i:bank['prior_logits'][i]))
        # EDF shares the engine/nominal diagnostic observer, but its action is
        # deliberately not constrained by the experimental protection mask.
        # Recover its actual public queue/owners from the call wrapper below.
        chosen=select_edf(self.public_call_state)
        if chosen['kind']=='RESOURCE_WAIT':return 75
        return next(i for i,a in enumerate(actions) if a['kind']=='DISPATCH'
                    and a['request_id']==chosen['request_id'] and a['route']==chosen['route'])

    def __call__(self,state):
        self.public_call_state=state
        action=super().__call__(state)
        return action

    def summary(self):
        v=self.opportunities;n=len(v)
        return dict(decision_opportunities=n,
            multiple_requests_before=sum(q['requests_before']>1 for q in v),
            multiple_requests_after=sum(q['requests_after']>1 for q in v),
            two_free_routes=sum(q['two_physical_routes'] for q in v),
            multiple_dispatch_actions=sum(q['multiple_dispatch_actions'] for q in v),
            WAIT_allowed=sum(q['voluntary_WAIT_allowed'] for q in v),
            removed_actions=sum(q['removed_actions'] for q in v),
            critical_focus=sum(q['critical_focus'] for q in v),
            multiple_request_rate=sum(q['requests_after']>1 for q in v)/max(1,n),
            two_free_rate=sum(q['two_physical_routes'] for q in v)/max(1,n))
