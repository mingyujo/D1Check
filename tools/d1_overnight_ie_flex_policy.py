"""Separate P95-constrained execution/resource-wait flexibility experiment.

The old per-urgent-request response guard is stronger than the final P95 KPI.
Replace that internal guard only; keep individual lateness nonworsening for
every current request, urgent-miss count/P95 and J in all3 contexts. Past
observed urgent responses and current arrived/owned unanswered requests are
already combined by the original predictor. No unseen arrivals are added.
"""
from tools import d1_rolling_list_rl as r
from tools import d1_overnight_ie_policy as conservative

FLEX='IE_ROLLING_P95_EXECUTION_RESOURCE_FLEX_V1'
SCHEMA=r.c.digest(dict(parent_features=r.SCHEMA,policy=FLEX,
    admission='observed_and_current_urgent_P95_and_misses_individual_lateness_J_nonworse_3contexts_unknown_cooling_forbidden'))


class Controller(r.Controller):
    def __init__(self,frozen,initial):
        super().__init__(frozen,initial,r.RULE);self.public_policy=FLEX;self.schema_id=SCHEMA
    def admission(self,action,forecasts,refs,queue,now,risk):
        if not all(f['valid'] and ref['valid'] for f,ref in zip(forecasts,refs)):return False,'unknown_forecast'
        if action['kind']=='cool_wait':
            delay=(action['until_ns']-now)/1e9
            if not risk['known']:return False,'unknown_observed_CPU_load_no_cooling'
            if sum(q['task']=='detection' for q in queue)>=2:return False,'D_backlog'
            if risk['rho']>=1.:return False,'observed_CPU_D_pressure'
            if any(self.request_wait.get(q['id'],0.)+delay>.25+1e-9 for q in queue):return False,'request_wait_cap'
        for f,ref in zip(forecasts,refs):
            if f['lane_end_s']>120.+1e-9 or f['remaining_increment_j']>ref['remaining_increment_j']+1e-9:return False,'drain_or_J'
            if (f['urgent_p95_ms'] or 0)>(ref['urgent_p95_ms'] or 0)+1e-9:return False,'current_observed_urgent_P95'
            if f['urgent_misses']>ref['urgent_misses']:return False,'current_urgent_miss_count'
            for q in queue:
                due=r.c.due(q)/1e9
                if max(0.,f['responses'][q['id']]-due)>max(0.,ref['responses'][q['id']]-due)+1e-9:return False,'individual_lateness'
        return True,'P95_current_queue_prediction_not_future_guarantee'
    def encode(self,*args,**kwargs):
        encoded=super().encode(*args,**kwargs);encoded['schema_id']=SCHEMA;return encoded
