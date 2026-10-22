"""Expand public forecast context; keep the eight dispatch candidates unchanged."""
import math
from public_controller import PublicController,NS,tie

class QueueContextController(PublicController):
    CONTEXT_CAP=24

    def context(self,public,chosen,vectors):
        queue=public['queue'];free=[r for r in ('CPU','GPU') if r not in {o['route'] for o in public['owners']}]
        now=public['now_ns']/NS
        def occurrence(q,r):return sum(vectors[q['request_id'],r])/self.physics.speed(public['sensor']['temperature_c'],r,1)
        mean=sum(occurrence(q,r) for q in queue for r in free)/(len(queue)*len(free))
        def atc(q):
            return max(math.log((2 if q['priority']=='U' else 1)/max(.001,occurrence(q,r)))-max(0.,q['deadline_ns']/NS-now-occurrence(q,r))/max(.2,2*mean) for r in free)
        edf=sorted(queue,key=lambda q:(q['deadline_ns'],*tie(q)))
        ranked=sorted(queue,key=lambda q:(-atc(q),*tie(q)))
        # The same context is used for every first-action counterfactual.
        selected={q['request_id']:q for q in [*chosen,*edf[:8],*ranked[:8]]}
        if len(selected)>self.CONTEXT_CAP:raise ValueError('Public forecast context bound')
        for q in edf:
            if len(selected)>=self.CONTEXT_CAP:break
            selected[q['request_id']]=q
        return sorted(selected.values(),key=lambda q:(q['deadline_ns'],*tie(q)))

    def preview(self,public,ready,initial_owners,vectors,first):
        expanded=self.context(public,ready,vectors)
        self._last_context=expanded
        return super().preview(public,expanded,initial_owners,vectors,first)

    def __call__(self,state):
        self._last_context=None
        action=super().__call__(state)
        if self._last_context is not None:
            call=self.calls[-1]
            call['action_candidates']=call['nominal_ready']
            call['nominal_ready']=self._last_context
            call['forecast_context_cap']=self.CONTEXT_CAP
            call['full_public_queue_size']=len(state['queue'])
        return action
