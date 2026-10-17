"""Same protected/coalesced action set, choose by the new exact nominal cost."""
from pathlib import Path
import sys
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'experiments/choice_opportunities_20261017'))
from run import L
from observer_v2 import CoalescingObserver
shared=L.load_module('shared_activation_for_candidate',ROOT/'experiments/shared_activation_20261017/shared_cost.py')


def minimum_legal(bank, costs):
    legal=[int(i) for i in np.flatnonzero(bank['mask'][:72])]
    if set(legal)!=set(costs):raise ValueError('Exactly every legal candidate must be costed')
    # Original prior is only a deterministic tie-breaker; same final mask.
    return min(legal,key=lambda i:(round(costs[i]['marginal_full_episode_J_proxy'],12),-bank['prior_logits'][i],i))


class SharedCostPolicy(CoalescingObserver):
    def __init__(self,model,public,thermal,profile,mode):
        super().__init__(model,public,thermal,profile,mode)
        self.new_cost=shared.SharedActivationCost(L.read(ROOT/'results/STATE_COST_IDENTIFICATION_20261017_01/MODEL.json'))
        self.marginal_audits=[]

    def choose(self,bank,now,collect=False):
        if self.mode!='SHARED_COST':return super().choose(bank,now,collect)
        self.mode='COALESCED_COST'
        try:original=super().choose(bank,now,collect)
        finally:self.mode='SHARED_COST'
        if original>=72:return original  # Identical protected coalescing/required wait.
        state=self.public_call_state;ts=now/1e9
        if any(r['end_s']>ts for r in state['past_activity']):raise ValueError('Future actual activity')
        public={q['request_id']:q for q in [*state['queue'],*state['owners']]}
        def duration(q,route):
            src=self.model.contexts[q['request_id']]
            ctx,_=L.context_of(src,src['_requests_by_id'][q['request_id']],True)
            e=self.model.nominal(L.context_for_route(ctx,q['task'],route),q['task'],route,state=state)
            return e['occupancy_ns']/1e9
        reserves=[]
        for q in state['owners']:
            remaining=max(.02,1.2*duration(q,q['route'])-(now-q['dispatch_ns'])/1e9)
            reserves.append(dict(start_s=ts,end_s=ts+remaining,task=q['task'],route=q['route']))
        costs={};candidates={}
        for index in np.flatnonzero(bank['mask'][:72]):
            i=int(index);a=bank['actions'][i];q=public[a['request_id']]
            candidate=dict(start_s=ts,end_s=ts+duration(q,a['route']),task=q['task'],route=a['route'])
            horizon=max([candidate['end_s'],*[r['end_s'] for r in reserves]])+30.
            costs[i]=self.new_cost.marginal(state['past_activity'],reserves,candidate,ts,horizon)
            candidates[i]=candidate
        chosen=minimum_legal(bank,costs)
        self.marginal_audits.append(dict(time_ns=now,chosen=chosen,original_prior_choice=original,
            nominal_reservations=reserves,nominal_candidates=candidates,costs=costs,
            uses_future_actual_duration=False,uses_future_arrival=False,
            current_cost_state=next(iter(costs.values()))['initial_shared_activation_state']))
        return chosen
