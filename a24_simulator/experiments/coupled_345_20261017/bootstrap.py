"""Read-only reuse of frozen A24 profile/latent-data machinery; no execution."""
from pathlib import Path
import sys
import statistics
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'experiments/choice_opportunities_20261017'))
from run import L,G,registration,restore_old_ledger,public_input,save_binary
import four_route_model as F


class Nominal:
    """Only previously measured pool medians, never a current latent draw."""
    def __init__(self,model,public):
        self.model,self.public=model,public;self.cache={};self.contexts={};self.request_cache={}
        for q in public['requests']:
            self.contexts[q['request_id']]=model.request_context(public,q)[0]

    def vector(self,q,route,state):
        local=(q['request_id'],route)
        if local in self.request_cache:return list(self.request_cache[local])
        context=L.context_for_route(self.contexts[q['request_id']],q['task'],route)
        # The frozen registration uses exact_public strata. Cache by the whole
        # public binding, not by request ordinal, outcome or sampled work.
        key=L.digest([context,q['task'],route])
        if key not in self.cache:
            estimate=self.model.nominal(context,q['task'],route,state=state)
            if q['task']=='D' and route=='GPU':
                cpu=self.model._cpu_context(context)
                pool=self.model.inner._pool(self.model.inner.samples,cpu,'D','CPU','SERIAL',state)
                raw=[[s['stages_ns'][i]*r['stages_ratio'][i] for i in range(5)] for s in pool for r in self.model.ratios]
            else:
                pool=self.model.inner._pool(self.model.inner.samples,F.original_context(context),q['task'],route,'SERIAL',state)
                raw=[s['stages_ns'] for s in pool]
            # Mean phase proportions remain defined when some callback-stage
            # medians are zero; scale to the frozen whole-response medians.
            median=[statistics.mean(v[i] for v in raw) for i in range(5)]
            boundary=2 if q['task']=='C' else 3
            target=(estimate['response_ns'],estimate['occupancy_ns']-estimate['response_ns'])
            result=[]
            for section,total in ((median[:boundary],target[0]),(median[boundary:],target[1])):
                if sum(section)<=0 or total<=0:raise ValueError('Positive complete nominal phases required')
                result.extend(total*x/sum(section)/1e9 for x in section)
            self.cache[key]=result
        self.request_cache[local]=self.cache[key]
        return list(self.cache[key])
