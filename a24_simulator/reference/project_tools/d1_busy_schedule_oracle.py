"""Conditional four-job calendar oracle with immutable occupied prefix.

No hot-start reset: native prefix jobs are replayed from their original arrivals.
Online tails receive only public arrived queues, and never the oracle context.
"""
from __future__ import annotations
import itertools,math,time
import numpy as np
from tools import d1_micro_schedule_oracle as micro

p=micro.p;external=micro.external
ORACLE='IE_BUSY_FINITE_CALENDAR_OFFLINE_V1'


def snapshot(tickets,ledger):
    """First arrival/dispatch/release boundary, before dispatches at that instant."""
    by={r['id']:r for r in ledger}
    for now in sorted({q['arrival_ns'] for q in tickets}|{r['dispatch_ns'] for r in ledger}|{r['lane_available_ns'] for r in ledger}):
        waiting=[q for q in tickets if q['arrival_ns']<=now<=by[q['id']]['decision_start_ns']]
        active=[r for r in ledger if r['decision_start_ns']<now<r['lane_available_ns']]
        if not active or any(sum(q['task']==task for q in waiting)<2 for task in ('classification','detection')):continue
        selected={q['id'] for task in ('classification','detection') for q in sorted((q for q in waiting if q['task']==task),key=lambda q:(q['arrival_ns']+q['deadline_offset_ns'],q['ordinal'],q['id']))[:2]}
        prefix=[dict(request_id=r['id'],backend=r['backend'],start_ns=r['decision_start_ns']) for r in ledger if r['decision_start_ns']<now]
        keep=selected|{j['request_id'] for j in prefix}
        return dict(snapshot_ns=now,variable_ids=[q['id'] for q in tickets if q['id'] in selected],prefix_calendar=prefix,
            tickets=[q for q in tickets if q['id'] in keep],active_ids=[r['id'] for r in active],original_requests=len(tickets),
            omitted_ids=[q['id'] for q in tickets if q['id'] not in keep],waiting_original=len(waiting))
    return None


def make_tail(frozen,initial,policy):
    if policy==external.BAND:return external.BandController(frozen,initial)
    if policy.startswith('TRITON_'):
        from tools import d1_triton_rules as t
        return t.Controller(frozen,initial,policy)
    if policy.startswith('IE_EDD_'):
        from tools import d1_ie_dispatch as ie
        return ie.Controller(frozen,initial,policy)
    if policy in (micro.SLACK,micro.FLEX):return micro.SlackController(frozen,initial,policy==micro.FLEX)
    from tools import d1_ie_candidates_v2 as v2
    if policy not in (v2.LIST,v2.ROLL):raise ValueError('unregistered tail')
    return v2.Controller(frozen,initial,policy)


class PrefixController(external.Timed):
    def __init__(self,frozen,initial,case,tail):
        super().__init__(frozen,initial);self.public_policy=getattr(tail,'public_policy',ORACLE)
        self.prefix=micro.CalendarController(frozen,initial,case['prefix_calendar']);self.cut=case['snapshot_ns'];self.tail=tail
        self.prefix_ids={j['request_id'] for j in case['prefix_calendar']};self.pending=None

    def observe(self,now,lanes):
        super().observe(now,lanes)
        if hasattr(self.tail,'rate'):
            # External history was dispatched by Band, including CPU classification.
            # Never release those jobs through Triton's different fixed instances.
            self.tail.rate.clock=round(now)
            for task in ('detection','classification'):
                current=next((l['request']['id'] for l in lanes.values() if l['request'] and l['request']['task']==task and l['request']['id'] in self.tail.seen),None)
                previous=self.tail.previous_live[task]
                if previous is not None and previous!=current:self.tail.rate.release(task,previous)
                self.tail.previous_live[task]=current
            p.Controller.observe(self.tail,now,lanes)
        else:self.tail.observe(now,lanes)

    def decide(self,config,queue,lanes,now,settings,thermal_model,current_ap):
        self.validate_public(queue,lanes,now)
        if len(self.prefix.started)<len(self.prefix.calendar):
            return self.prefix.decide(config,queue,lanes,now,settings,thermal_model,current_ap)
        if now<self.cut:return dict(now_ns=now,selected=None,wait_until_ns=self.cut,reason='fixed_history_to_snapshot')
        if any(q['id'] in self.prefix_ids for q in queue):raise AssertionError('unfinished prefix dispatch at snapshot')
        decision_lanes={b:(dict(request=None,phase='AVAILABLE',since=now,dispatch=None) if l['request'] and l['request']['id'] in self.prefix_ids else l) for b,l in lanes.items()} if hasattr(self.tail,'rate') else lanes
        out=self.pending or self.tail(config,queue,decision_lanes,now,settings,thermal_model,current_ap)
        if out.get('selected'):
            action=out['selected'];q=next(q for q in queue if q['id']==action['request_id']);b=action['backend']
            try:
                if lanes[b]['request'] is not None:raise ValueError('owned lane')
                p.state([l['request']['task']+'_'+backend for backend,l in lanes.items() if l['request']]+[q['task']+'_'+b])
            except ValueError:
                self.pending=out;return dict(now_ns=now,selected=None,reason='conditional_actual_capacity_wait')
            self.pending=None;out=dict(out,now_ns=now)
        out['conditional_snapshot_ns']=self.cut;return out


def simulate(frozen,initial,case,policy,calendar=None):
    tail=micro.CalendarController(frozen,initial,calendar) if calendar is not None else make_tail(frozen,initial,policy)
    c=PrefixController(frozen,initial,case,tail);actual=p.profile(frozen,case['context'])
    vectors=dict(cells={k:[dict(source_request_id='busy_context_'+case['context'],durations_ns=v) for _ in range(4)] for k,v in actual.items()})
    result=external.old.engine.simulate(dict(protocol=p.VERSION,cells=p.profile(frozen)),vectors,case['tickets'],
        policy=c.policy,settings=external.settings(),seed=201,decision_provider=c)
    return result,c


def enumerate_calendars(case,profile,model,references,reference_calendars,*,grid_ns=100000000,delay_ns=3000000000,chunk_size=4096,deadline=None):
    tickets=case['tickets'];by={q['id']:q for q in tickets};variable=[by[i] for i in case['variable_ids']]
    fixed=case['prefix_calendar'];ordered=[by[j['request_id']] for j in fixed]+variable
    fixed_assignment=[j['backend'] for j in fixed];prefix=np.array([j['start_ns'] for j in fixed])
    domains=[np.array(sorted({float(case['snapshot_ns']+k*grid_ns) for k in range(delay_ns//grid_ns+1)}|
        {float(j['start_ns']) for cal in reference_calendars for j in cal if j['request_id']==q['id']})) for q in variable]
    assignments=list(itertools.product(*(p.backends(q) for q in variable)));raw=len(assignments)*math.prod(len(d) for d in domains)
    if raw>20000000:raise ValueError('per-case calendar ceiling')
    caps={k:min(r[k] for r in references) for k in ('energy_j','peak_ap_c','urgent_service_failure','normal_service_failure','urgent_p95_ms','normal_mean_ms')}
    arrival=np.array([q['arrival_ns'] for q in ordered]);due=np.array([q['deadline_offset_ns'] for q in ordered])
    urgent=np.array([q['priority']=='urgent' for q in ordered]);normal=~urgent;rank=math.ceil(.95*sum(urgent))-1
    counts=dict(raw=raw,pruned=0,visited=0,capacity_valid=0,service_valid=0,ap_cap_valid=0,j_cap_valid=0,joint_gain=0,normal_mean_guard_joint_gain=0)
    best={key:None for key in ('min_J','min_AP','joint','normal_guard')};began=time.perf_counter();durations=[]
    def key(w,role):return (w['peak_ap_c'],w['energy_j']) if role=='min_AP' else (w['energy_j'],w['peak_ap_c'])
    for va in assignments:
        assignment=fixed_assignment+list(va);labels=[q['task']+'_'+b for q,b in zip(ordered,assignment)];allowed=[]
        for q,b,domain in zip(variable,va,domains):
            response=sum(profile[p.key(q,b)][:2 if q['priority']=='urgent' else 3]);mask=np.ones(len(domain),dtype=bool)
            failure=caps['urgent_service_failure' if q['priority']=='urgent' else 'normal_service_failure']
            if failure==0:mask&=domain+response-q['arrival_ns']<=q['deadline_offset_ns']+1
            # P95 equals max only when there are <=19 urgent requests. Other cases use exact quantile below.
            if q['priority']=='urgent' and rank==sum(urgent)-1:mask&=domain+response-q['arrival_ns']<=caps['urgent_p95_ms']*1e6+1
            allowed.append(domain[mask])
        possible=math.prod(len(d) for d in allowed);counts['pruned']+=math.prod(len(d) for d in domains)-possible
        if not possible:continue
        for offset in range(0,possible,chunk_size):
            if deadline is not None and time.monotonic()>=deadline:raise TimeoutError('save boundary: incomplete oracle not certified')
            digits=np.arange(offset,min(possible,offset+chunk_size),dtype=np.int64);indices=[]
            for size in reversed([len(d) for d in allowed]):indices.append(digits%size);digits=digits//size
            starts=np.column_stack([np.broadcast_to(prefix,(len(indices[0]),len(prefix)))]+[d[idx] for d,idx in zip(allowed,reversed(indices))])
            counts['visited']+=len(starts);ends,response=micro.plan_arrays(ordered,assignment,profile,starts)
            physical=micro.capacity(starts,ends,labels);counts['capacity_valid']+=int(physical.sum())
            p95=np.partition(response[:,urgent],rank,axis=1)[:,rank]/1e6
            service=physical&(ends.max(axis=1)<=120e9)&((response[:,urgent]>due[urgent]).sum(axis=1)<=caps['urgent_service_failure'])&((response[:,normal]>due[normal]).sum(axis=1)<=caps['normal_service_failure'])&(p95<=caps['urgent_p95_ms']+1e-9)
            counts['service_valid']+=int(service.sum())
            if not service.any():continue
            starts=starts[service];ends=ends[service];response=response[service];p95=p95[service]
            energy,peak,_=model.costs(starts,ends,labels);ap_ok=peak<=caps['peak_ap_c']+1e-9;j_ok=energy<=caps['energy_j']+1e-9
            joint=ap_ok&j_ok&(peak<caps['peak_ap_c']-1e-9)&(energy<caps['energy_j']-1e-9)
            normal_mean=response[:,normal].mean(axis=1)/1e6;normal_ok=joint&(normal_mean<=caps['normal_mean_ms']+1e-9)
            for name,mask in [('ap_cap_valid',ap_ok),('j_cap_valid',j_ok),('joint_gain',joint),('normal_mean_guard_joint_gain',normal_ok)]:counts[name]+=int(mask.sum())
            for role,mask in [('min_J',ap_ok),('min_AP',j_ok),('joint',joint),('normal_guard',normal_ok)]:
                ids=np.flatnonzero(mask)
                if not len(ids):continue
                order=np.lexsort((energy[ids],peak[ids])) if role=='min_AP' else np.lexsort((peak[ids],energy[ids]));i=ids[order[0]]
                w=dict(calendar=[dict(request_id=q['id'],backend=b,start_ns=float(starts[i,j])) for j,(q,b) in enumerate(zip(ordered,assignment)) if j>=len(prefix)],energy_j=float(energy[i]),peak_ap_c=float(peak[i]),urgent_p95_ms=float(p95[i]),normal_mean_ms=float(normal_mean[i]),offline_future_information=True)
                if best[role] is None or key(w,role)<key(best[role],role):best[role]=w
    assert counts['visited']+counts['pruned']==counts['raw']
    return dict(status='exhaustive_complete',counts=counts,witnesses=best,domains_ns=[d.tolist() for d in domains],host_wall_s=time.perf_counter()-began,
        scope='fixed occupied prefix plus four queued jobs; snapshot-anchored finite 100ms/3s calendars plus both reference starts; no continuous/full-arrival/online optimum')
