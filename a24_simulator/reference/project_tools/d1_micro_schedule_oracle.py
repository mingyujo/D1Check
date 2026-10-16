"""Exhaustive finite-calendar oracle, not an online scheduler or continuous optimum.

Whole-request compatibility and original five-phase costs remain unchanged.
Pulse accounting is the closed-form solution of the original linear AP model.
"""
from __future__ import annotations
import itertools,math,time
import numpy as np
from tools import d1_external_rules as external

p=external.p
SLACK='IE_RESPONSE_SLACK_ECT_MICRO_V1'
FLEX='IE_RESPONSE_SLACK_CPU_FLEX_MICRO_V1'
ORACLE='IE_FINITE_CALENDAR_OFFLINE_ORACLE_V1'
EPS=1e-9


def conv(beta,dt):
    difference=beta-1/30.
    return dt*np.exp(-beta*dt) if abs(difference)<1e-10 else (np.exp(-dt/30.)-np.exp(-beta*dt))/difference


class PulseModel:
    def __init__(self,frozen,initial):
        self.frozen=frozen;self.initial=initial;self.ap=frozen['ap'];self.times=np.arange(35.,181.)
        self.init=p.memory.initialize(initial['preload'],self.ap['beta'],30.)
        dt=self.times-self.init['anchor_s'];beta=self.ap['beta']
        self.idle=(self.init['reference_c']+(self.init['anchor_ap_c']-self.init['reference_c'])*np.exp(-beta*dt)+
                   self.init['h_last_c_per_s']*conv(beta,dt))
        self.slopes=self.ap['parameters']['ap_slope_at_30_c_per_s'];self.watts=frozen['energy_increment_w']
        self.background=initial['preload_power_w']*120
        self.corr_w=self.watts['classification_GPU+detection_CPU']-self.watts['classification_GPU']-self.watts['detection_CPU']
        self.corr_u=self.slopes['classification_GPU+detection_CPU']-self.slopes['classification_GPU']-self.slopes['detection_CPU']+self.slopes['resident_idle']

    def kernel(self,dt):
        dt=np.maximum(0.,dt);beta=self.ap['beta']
        return (self.ap['k']+self.ap['g'])*(-np.expm1(-beta*dt))/beta-self.ap['g']*conv(beta,dt)

    def pulse(self,starts,ends):
        return self.kernel(self.times[None,:]-np.asarray(starts)[:,None])-self.kernel(self.times[None,:]-np.asarray(ends)[:,None])

    def costs(self,starts_ns,ends_ns,labels):
        starts=np.rint(starts_ns)/1e9;ends=np.rint(ends_ns)/1e9
        paths=np.broadcast_to(self.idle,(len(starts),146)).copy();energy=np.full(len(starts),self.background)
        for i,label in enumerate(labels):
            paths+=(self.slopes[label]-self.slopes['resident_idle'])*self.pulse(starts[:,i],ends[:,i])
            energy+=self.watts[label]*(ends[:,i]-starts[:,i])
        for i,label in enumerate(labels):
            if label!='classification_GPU':continue
            for j,other in enumerate(labels):
                if other!='detection_CPU':continue
                a=np.maximum(starts[:,i],starts[:,j]);b=np.maximum(a,np.minimum(ends[:,i],ends[:,j]))
                paths+=self.corr_u*self.pulse(a,b);energy+=self.corr_w*(b-a)
        return energy,paths.max(axis=1),paths


def plan_arrays(tickets,assignment,profile,starts):
    ends=starts.copy();responses=starts.copy()
    for i,(q,b) in enumerate(zip(tickets,assignment)):
        ds=profile[p.key(q,b)]
        # Repeat phase additions in native ns, then expose the same rounded ledger.
        for phase,duration in enumerate(ds):
            ends[:,i]+=duration
            if phase<(2 if q['priority']=='urgent' else 3):responses[:,i]+=duration
    return ends,np.rint(responses-np.array([q['arrival_ns'] for q in tickets]))


def capacity(starts,ends,labels):
    start=np.rint(starts);end=np.rint(ends);good=np.ones(len(starts),dtype=bool)
    for i in range(len(labels)):
        for j in range(i):
            pair='+'.join(sorted((labels[i],labels[j])))
            if labels[i].split('_')[-1]==labels[j].split('_')[-1] or pair not in p.STATES:
                good&=(end[:,i]<=start[:,j])|(end[:,j]<=start[:,i])
    return good


def lower_bound(tickets,profile,model):
    values=[]
    for assignment in itertools.product(*(p.backends(q) for q in tickets)):
        times=[sum(profile[p.key(q,b)])/1e9 for q,b in zip(tickets,assignment)]
        solo=sum(model.watts[q['task']+'_'+b]*d for q,b,d in zip(tickets,assignment,times))
        gpu=sum(d for q,b,d in zip(tickets,assignment,times) if q['task']=='classification' and b=='GPU')
        dc=sum(d for q,b,d in zip(tickets,assignment,times) if q['task']=='detection')
        # Relax all release/deadline/AP/order constraints; never exceed lane overlap.
        rounding=(len(tickets)+2*len(tickets)**2)*1e-9*max(model.watts.values())
        values.append(model.background+solo+min(0.,model.corr_w)*min(gpu,dc)-rounding)
    return min(values)


def extract_calendar(result):
    return [dict(request_id=d['selected']['request_id'],backend=d['selected']['backend'],start_ns=d['now_ns'])
            for d in result['decisions'] if d.get('selected')]


def enumerate_calendars(tickets,profile,model,references,band_calendar,*,grid_ns=100_000_000,delay_ns=3_000_000_000,
                        chunk_size=8192,deadline=None,stop=None):
    by={j['request_id']:j for j in band_calendar}
    domains=[np.array(sorted(set([float(q['arrival_ns']+k*grid_ns) for k in range(delay_ns//grid_ns+1)]+[float(by[q['id']]['start_ns'])]))) for q in tickets]
    assignments=list(itertools.product(*(p.backends(q) for q in tickets)))
    raw=sum(math.prod(len(d) for d in domains) for _ in assignments)
    if raw>20_000_000:raise ValueError('registered per-case raw calendar cap')
    limit_p95=min(r['urgent_p95_ms'] for r in references)*1e6
    limit_j=min(r['energy_j'] for r in references);limit_ap=min(r['peak_ap_c'] for r in references)
    fail_u=min(r['urgent_service_failure'] for r in references);fail_n=min(r['normal_service_failure'] for r in references)
    arrival=np.array([q['arrival_ns'] for q in tickets]);due=np.array([q['deadline_offset_ns'] for q in tickets])
    urgent=np.array([q['priority']=='urgent' for q in tickets]);normal=~urgent
    counts=dict(raw=raw,pruned=0,visited=0,capacity_valid=0,service_valid=0,ap_cap_valid=0,j_cap_valid=0,joint_gain=0,normal_mean_guard_joint_gain=0)
    best_j=best_ap=best_joint=best_normal_guard=None;began=time.perf_counter()
    norm_cap=min(r['normal_mean_ms'] for r in references)
    def witness(index,starts,ends,response,assignment,energy,peak):
        return dict(calendar=[dict(request_id=q['id'],backend=b,start_ns=float(starts[index,i])) for i,(q,b) in enumerate(zip(tickets,assignment))],
            energy_j=float(energy[index]),peak_ap_c=float(peak[index]),urgent_p95_ms=float(response[index,urgent].max()/1e6),
            normal_mean_ms=float(response[index,normal].mean()/1e6),max_lane_ns=float(ends[index].max()),offline_future_information=True)
    for assignment in assignments:
        labels=[q['task']+'_'+b for q,b in zip(tickets,assignment)]
        allowed=[]
        for i,(q,b,domain) in enumerate(zip(tickets,assignment,domains)):
            ds=profile[p.key(q,b)];resp=sum(ds[:2 if q['priority']=='urgent' else 3])
            mask=np.ones(len(domain),dtype=bool)
            if q['priority']=='urgent' and fail_u==0:
                # One-ns OUTER pruning allowance only; qualification below is exact.
                mask&=(domain+resp-q['arrival_ns']<=min(limit_p95,q['deadline_offset_ns'])+1.)
            if q['priority']=='normal' and fail_n==0:mask&=(domain+resp-q['arrival_ns']<=q['deadline_offset_ns']+1.)
            allowed.append(domain[mask])
        possible=math.prod(len(d) for d in allowed);counts['pruned']+=math.prod(len(d) for d in domains)-possible
        if not possible:continue
        radix=[len(d) for d in allowed]
        for offset in range(0,possible,chunk_size):
            if (deadline is not None and time.monotonic()>=deadline) or (stop and stop()):raise TimeoutError('oracle save/stop boundary; no incomplete certificate')
            number=np.arange(offset,min(possible,offset+chunk_size),dtype=np.int64);indices=[]
            for size in reversed(radix):indices.append(number%size);number=number//size
            starts=np.column_stack([d[idx] for d,idx in zip(allowed,reversed(indices))]);counts['visited']+=len(starts)
            ends,response=plan_arrays(tickets,assignment,profile,starts)
            physical=capacity(starts,ends,labels);counts['capacity_valid']+=int(physical.sum())
            service=(physical & (ends.max(axis=1)<=120e9) & ((response[:,urgent]>due[urgent]).sum(axis=1)<=fail_u) &
                ((response[:,normal]>due[normal]).sum(axis=1)<=fail_n) & (response[:,urgent].max(axis=1)<=limit_p95+0.001))
            counts['service_valid']+=int(service.sum())
            if not service.any():continue
            starts=starts[service];ends=ends[service];response=response[service]
            energy,peak,_=model.costs(starts,ends,labels)
            ap_ok=peak<=limit_ap+EPS;j_ok=energy<=limit_j+EPS
            joint=ap_ok&j_ok&(peak<limit_ap-EPS)&(energy<limit_j-EPS)
            normal_ok=joint&(response[:,normal].mean(axis=1)/1e6<=norm_cap+EPS)
            counts['ap_cap_valid']+=int(ap_ok.sum());counts['j_cap_valid']+=int(j_ok.sum());counts['joint_gain']+=int(joint.sum());counts['normal_mean_guard_joint_gain']+=int(normal_ok.sum())
            for kind,mask in [('J',ap_ok),('AP',j_ok),('joint',joint),('normal',normal_ok)]:
                if not mask.any():continue
                ids=np.flatnonzero(mask)
                order=np.lexsort((peak[ids],energy[ids])) if kind!='AP' else np.lexsort((energy[ids],peak[ids]))
                w=witness(int(ids[order[0]]),starts,ends,response,assignment,energy,peak)
                current={'J':best_j,'AP':best_ap,'joint':best_joint,'normal':best_normal_guard}[kind]
                key=lambda v:(v['peak_ap_c'],v['energy_j']) if kind=='AP' else (v['energy_j'],v['peak_ap_c'])
                if current is None or key(w)<key(current):
                    if kind=='J':best_j=w
                    elif kind=='AP':best_ap=w
                    elif kind=='joint':best_joint=w
                    else:best_normal_guard=w
    if counts['visited']+counts['pruned']!=counts['raw']:raise AssertionError('enumeration conservation')
    return dict(status='exhaustive_complete',counts=counts,energy_min_ap_cap=best_j,ap_min_energy_cap=best_ap,
        joint_witness=best_joint,normal_mean_guard_witness=best_normal_guard,energy_relaxation_lower_bound_j=lower_bound(tickets,profile,model),
        host_wall_s=time.perf_counter()-began,domains_ns=[d.tolist() for d in domains],
        certificate_scope='all backend assignments and arrival-anchored 100ms/3s calendars augmented with native Band starts; canonical ns ledger cost model, not continuous-time or online optimum')


class CalendarController(external.Timed):
    """Offline-derived plan replay, rechecked against actual lane ownership."""
    def __init__(self,frozen,initial,calendar):
        super().__init__(frozen,initial);self.public_policy=ORACLE
        self.calendar=sorted(enumerate(calendar),key=lambda pair:(pair[1]['start_ns'],pair[0]));self.started=set()

    def decide(self,config,queue,lanes,now_ns,settings,thermal_model,current_ap):
        self.validate_public(queue,lanes,now_ns)
        for index,j in self.calendar:
            if j['request_id'] in self.started:continue
            q=next((q for q in queue if q['id']==j['request_id']),None)
            if q is None:return dict(now_ns=now_ns,selected=None,reason='offline_plan_wait_for_arrival')
            if j['start_ns']>now_ns+.0001:return dict(now_ns=now_ns,selected=None,wait_until_ns=j['start_ns'],reason='offline_plan_start_timer')
            b=j['backend'];members=[l['request']['task']+'_'+backend for backend,l in lanes.items() if l['request']]
            if lanes[b]['request'] is not None:return dict(now_ns=now_ns,selected=None,reason='offline_plan_actual_lane_owned')
            try:p.state(members+[q['task']+'_'+b])
            except ValueError:return dict(now_ns=now_ns,selected=None,reason='offline_plan_compatibility_wait')
            self.started.add(q['id']);return dict(now_ns=now_ns,selected=dict(request_id=q['id'],backend=b),reason=ORACLE)
        return dict(now_ns=now_ns,selected=None,reason='offline_plan_done')


class SlackController(external.Timed):
    def __init__(self,frozen,initial,flex=False):
        super().__init__(frozen,initial);self.flex=flex;self.public_policy=FLEX if flex else SLACK

    def decide(self,config,queue,lanes,now_ns,settings,thermal_model,current_ap):
        self.validate_public(queue,lanes,now_ns);now=now_ns/1e9;active=self.active_jobs(lanes,now)
        if not queue or active is None:return dict(now_ns=now_ns,selected=None,reason='empty_or_unknown_residual')
        choices=[]
        for q in queue:
            options=[self.place(q,b,now,active) for b in p.backends(q)]
            chosen=min(options,key=lambda j:(j['end'],j['backend']!='CPU'))
            slack=(q['arrival_ns']+q['deadline_offset_ns'])/1e9-chosen['response']
            choices.append((slack,q['arrival_ns']+q['deadline_offset_ns'],q['ordinal'],q['id'],q,chosen,options))
        _,_,_,_,q,chosen,options=min(choices,key=lambda v:v[:4]);reason=self.public_policy
        if self.flex and q['task']=='classification' and chosen['backend']=='CPU':
            gpu=next(j for j in options if j['backend']=='GPU');protected=[]
            for d in queue:
                if len(p.backends(d))!=1 or d['id']==q['id']:continue
                before=self.place(d,'CPU',now,active);after=self.place(d,'CPU',now,active+[chosen])
                if before['response']<=before['deadline']+EPS and after['response']>after['deadline']+EPS:protected.append(d['id'])
            if protected and gpu['response']<=gpu['deadline']+EPS:chosen=gpu;reason='protect_arrived_cpu_only_deadline'
        out=dict(now_ns=now_ns,selected=None,reason=reason,response_slack_s=(q['arrival_ns']+q['deadline_offset_ns'])/1e9-chosen['response'],
            cpu_flex_considered=self.flex,predicted_response_s=chosen['response'])
        if chosen['start']>now+EPS:return dict(out,wait_until_ns=max(now_ns+1.,chosen['start']*1e9))
        b=chosen['backend']
        if lanes[b]['request'] is not None:return out
        p.state([l['request']['task']+'_'+backend for backend,l in lanes.items() if l['request']]+[q['task']+'_'+b])
        return dict(out,selected=dict(request_id=q['id'],backend=b))


def simulate(frozen,initial,tickets,context,policy,calendar=None):
    if policy==external.BAND:return external.simulate(frozen,initial,tickets,context,policy)
    if policy.startswith('TRITON_'):
        from tools import d1_triton_rules as triton
        c=triton.Controller(frozen,initial,policy)
    elif policy.startswith('IE_EDD_'):
        from tools import d1_ie_dispatch as ie
        c=ie.Controller(frozen,initial,policy)
    elif calendar is not None:c=CalendarController(frozen,initial,calendar)
    else:c=SlackController(frozen,initial,policy==FLEX)
    actual=p.profile(frozen,context)
    vectors=dict(cells={key:[dict(source_request_id='shared_development_context_'+context,durations_ns=v) for _ in range(4)] for key,v in actual.items()})
    result=external.old.engine.simulate(dict(protocol=p.VERSION,cells=p.profile(frozen)),vectors,tickets,
        policy=c.policy,settings=external.settings(),seed=201,decision_provider=c)
    return result,c
