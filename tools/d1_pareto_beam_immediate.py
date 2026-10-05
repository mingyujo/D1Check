"""Minimal response to v1's repeated deferral failure, kept as a separate ID.

Restrict the same queue-calendar search to an immediate legal first dispatch.
Preserve the original v1 and all its failures. No claim of future-service proof.
"""
from tools import d1_pareto_beam as parent
x=parent.x
POLICY=x.p.RECEDING_POLICIES[1]


class Controller(parent.Controller):
    def __init__(self,frozen,initial):
        super().__init__(frozen,initial);self.policy=POLICY

    def finish_plan(self,sequence,queue,active,now,forecaster):
        jobs,first=super().finish_plan(sequence,queue,active,now,forecaster)
        first['_immediate_first']=sequence[0][2]==0. and first['start']<=now+1e-9
        return jobs,first

    def score(self,jobs,now):
        if any(j.get('_immediate_first') is False for j in jobs):return None
        return super().score(jobs,now)

    def __call__(self,*args,**kwargs):
        out=super().__call__(*args,**kwargs)
        if out['reason']==parent.POLICY:out['reason']=POLICY
        return out


def simulate(frozen,initial,tickets,scenario):
    c=Controller(frozen,initial)
    vectors=dict(cells={k:[dict(source_request_id='fixed_context_'+scenario,durations_ns=v) for _ in range(4)]
        for k,v in x.p.profile(frozen,scenario).items()})
    rr=x.old.engine.simulate(dict(protocol=x.p.VERSION,cells=x.p.profile(frozen)),vectors,tickets,
        policy=POLICY,settings=x.settings(),seed=201,decision_provider=c)
    row,ss,cost=x.outcome(rr,initial,frozen)
    row.update(decision_host_total_s=sum(c.callback_times),decision_host_max_ms=1000*max(c.callback_times,default=0),
        expanded_calendars=sum(v['expanded'] for v in c.records),
        local_deviations=sum(d.get('local_deviation',False) for d in rr['decisions']),
        wait_actions=sum(d.get('chosen_explicit_delay_s',0)>0 and d['selected'] is None for d in rr['decisions']))
    return row,rr,c,ss,cost
