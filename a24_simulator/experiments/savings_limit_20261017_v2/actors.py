"""Offline diagnostic actors; future latent work is intentionally available.

These are feasible-witness heuristics, NOT globally optimal/online policies.
The micro certificate covers exactly the enumerated list-plan class only.
"""
import itertools
from math_bounds import work_energy


class TruthNominal:
    def __init__(self,jobs):self.jobs={j['request_id']:j for j in jobs}
    def vector(self,q,route,state):return [x/1e9 for x in self.jobs[q['request_id']]['routes'][route]['stages_ns']]


def list_plans(ids):
    # Each job is assigned to exactly one lane, then that lane's full list is
    # ordered. There are sum_k C(n,k)k!(n-k)!=(n+1)n! distinct plans.
    for mask in range(1<<len(ids)):
        a=[rid for j,rid in enumerate(ids) if mask>>j&1];b=[rid for j,rid in enumerate(ids) if not (mask>>j&1)]
        for cpu in itertools.permutations(a):
            for gpu in itertools.permutations(b):yield dict(CPU=list(cpu),GPU=list(gpu))


class ListActor:
    def __init__(self,plan,nominal,physics):
        self.plan=plan;self.index=dict(CPU=0,GPU=0);self.nominal=nominal;self.physics=physics
        self.waited=set();self.feasible=True;self.violations=[];self.wait_per_head={}
    def __call__(self,state):
        q=state['queue'];busy={o['route'] for o in state['owners']};free=[r for r in ('CPU','GPU') if r not in busy]
        now=state['now_ns']/1e9;byid={x['request_id']:x for x in q}
        def duration(job,r):return sum(self.nominal.vector(job,r,state))/self.physics.speed(state['sensor']['temperature_c'],r,1)
        head=min(q,key=lambda x:(x['scheduled_arrival_ns'],x['ordinal'],x['request_id']))
        if len(q)==1 and not busy and head['request_id'] not in self.waited and state['wait_used_ns']+50_000_000<=12_000_000_000:
            if min(duration(head,r) for r in free)+.05<head['deadline_ns']/1e9-now:
                self.waited.add(head['request_id']);return dict(kind='WAIT',wait_ns=50_000_000)
        for r in free:
            i=self.index[r]
            if i<len(self.plan[r]) and self.plan[r][i] in byid:
                rid=self.plan[r][i];self.index[r]+=1;return dict(kind='DISPATCH',request_id=rid,route=r)
        # Legal explicit 50ms waits, with the same urgent nominal feasibility
        # test and global12s cap as coupled345. A plan that needs an illegal
        # wait is recorded ineligible, then drained with EDF for raw retention.
        safe=state['wait_used_ns']+50_000_000<=12_000_000_000 and self.wait_per_head.get(head['request_id'],0)<1.5-1e-9 and all(
            x['priority']!='U' or now+.05+min(duration(x,r) for r in ('CPU','GPU'))<=x['deadline_ns']/1e9 for x in q)
        if safe and self.feasible:
            self.wait_per_head[head['request_id']]=self.wait_per_head.get(head['request_id'],0)+.05
            return dict(kind='WAIT',wait_ns=50_000_000)
        self.feasible=False;self.violations.append(dict(time_ns=state['now_ns'],reason='List requires prohibited wait'))
        target=min(q,key=lambda x:(x['deadline_ns'],x['ordinal']))
        return dict(kind='DISPATCH',request_id=target['request_id'],route=free[0])


class EnergyRouteActor:
    def __init__(self,jobs,nominal,physics,coeff):
        self.jobs={j['request_id']:j for j in jobs};self.nominal=nominal;self.physics=physics;self.coeff=coeff;self.waited=set();self.wait_per_head={}
        self.preferred={j['request_id']:min(('CPU','GPU'),key=lambda r:work_energy(j,r,coeff)) for j in jobs}
    def __call__(self,state):
        queue=state['queue'];busy={o['route'] for o in state['owners']};free=[r for r in ('CPU','GPU') if r not in busy]
        now=state['now_ns']/1e9
        def occurrence(q,r):return sum(self.nominal.vector(q,r,state))/self.physics.speed(state['sensor']['temperature_c'],r,1)
        oldest=min(queue,key=lambda q:(q['scheduled_arrival_ns'],q['ordinal']))
        if len(queue)==1 and not busy and oldest['request_id'] not in self.waited and state['wait_used_ns']+50_000_000<=12_000_000_000:
            if min(occurrence(oldest,r) for r in free)+.05<oldest['deadline_ns']/1e9-now:
                self.waited.add(oldest['request_id']);return dict(kind='WAIT',wait_ns=50_000_000)
        urgent=[(q,r) for q in queue for r in free if q['priority']=='U' and now+occurrence(q,r)+.05>=q['deadline_ns']/1e9]
        preferred=[(q,r) for q in queue for r in free if r==self.preferred[q['request_id']]]
        pairs=urgent or preferred
        if pairs:
            q,r=min(pairs,key=lambda x:(x[0]['deadline_ns'],work_energy(self.jobs[x[0]['request_id']],x[1],self.coeff),x[0]['ordinal']))
            return dict(kind='DISPATCH',request_id=q['request_id'],route=r)
        safe=state['wait_used_ns']+50_000_000<=12_000_000_000 and self.wait_per_head.get(oldest['request_id'],0)<1.5-1e-9 and all(q['priority']!='U' or now+.05+min(occurrence(q,r) for r in ('CPU','GPU'))<=q['deadline_ns']/1e9 for q in queue)
        if safe:
            self.wait_per_head[oldest['request_id']]=self.wait_per_head.get(oldest['request_id'],0)+.05
            return dict(kind='WAIT',wait_ns=50_000_000)
        q=min(queue,key=lambda q:(q['deadline_ns'],q['ordinal']));r=min(free,key=lambda r:work_energy(self.jobs[q['request_id']],r,self.coeff))
        return dict(kind='DISPATCH',request_id=q['request_id'],route=r)
