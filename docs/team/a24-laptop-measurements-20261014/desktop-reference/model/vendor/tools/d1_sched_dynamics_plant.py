"""Nonpreemptive current-state mobile dynamics, isolated from frozen engines.

Only this environment owns remaining work and sampled vectors. Public estimates
are current-condition estimates; they never simulate waiting/future requests.
"""
from __future__ import annotations
import copy
import hashlib
import math
from collections import deque
from tools import d1_sched_dynamics_profiles as p
from tools import d1_s26_npu_engine as old

ABI='d1-sched-dynamics-event-plant-v1'
BACKENDS=('CPU','GPU','NPU')
FIELDS=old.FIELDS
PHASES=('ASSIGNED','EXECUTING','OUTPUT_READY','PERSISTED','WORKER_RELEASED')
HORIZON_NS=120_000_000_000
PUBLIC_FIELDS=old.REQUEST_FIELDS|{'work_units'}

def digest(value): return old.digest(value)

def routes(q, device='S26', npu=True):
    if q['task']=='detection': return ('CPU',)
    if q['task']=='classification': return BACKENDS if device=='S26' and npu else BACKENDS[:2]
    raise ValueError('unsupported task')

def validate_request(q):
    if set(q) not in (old.REQUEST_FIELDS,PUBLIC_FIELDS): raise ValueError('public request ABI')
    if not isinstance(q['id'],str) or not q['id'] or q['priority'] not in ('urgent','normal'): raise ValueError('ticket id/priority')
    if any(type(q[k]) is not int for k in ('ordinal','arrival_ns','deadline_offset_ns')): raise ValueError('integer public time')
    if not 0<=q['arrival_ns']<HORIZON_NS or q['ordinal']<0: raise ValueError('arrival/ordinal')
    declared_cap=2_500_000_000 if q['priority']=='urgent' else 9_000_000_000
    if not 0<q['deadline_offset_ns']<=declared_cap: raise ValueError('registered declared deadline range')
    if type(q.get('work_units',1)) is not int or not 1<=q.get('work_units',1)<=3: raise ValueError('declared work1..3')
    routes(q)

def _positive_exp_area(start,target,beta,dt):
    """Exact integral max(target+(start-target)exp(-beta*t),0)."""
    end=target+(start-target)*math.exp(-beta*dt)
    def area(a,b): return target*(b-a)+(start-target)*(math.exp(-beta*a)-math.exp(-beta*b))/beta
    if start>=0 and end>=0: return max(area(0,dt),0.)
    if start<=0 and end<=0: return 0.
    cross=-math.log(-target/(start-target))/beta
    return max(area(0,cross) if start>0 else area(cross,dt),0.)

class _A24Anchor:
    """Frozen coefficients, explicit simple initial-state transfer hypothesis."""
    def __init__(self,profile,initial):
        self.model=profile['cost_anchor']; self.now=0.; self.energy=0.; self.area=0.; self.peak=initial['ap_c']
        self.baseline=initial['baseline_w']; self.ap=initial['ap_c']; self.ref=initial['reference_ap_c']; self.skin=initial['skin_c']; self.owners={}
    def key(self):
        labels=sorted(f'{task}_{b}' for rid,task,b in self.owners.values())
        return '+'.join(labels) if labels else 'resident_idle'
    def snapshot(self):
        key=self.key(); inc=0. if key=='resident_idle' else self.model['energy_increment_w'][key]
        return dict(power_w=self.baseline+inc, temperature_c={'AP':self.ap,'SKIN':self.skin},energy_window_j=self.energy)
    def advance(self,to):
        dt=to-self.now
        if dt<0: raise ValueError('anchor clock')
        if dt:
            snap=self.snapshot(); ap=self.model['ap']; beta=ap['beta']; slope=ap['k']*ap['parameters']['ap_slope_at_30_c_per_s'][self.key()]
            # Frozen original model reference is30C; boundary state is supplied separately.
            target=30.+slope/beta; decay=math.exp(-beta*dt)
            self.area+=target*dt+(self.ap-target)*(1-decay)/beta
            self.energy+=snap['power_w']*dt; self.ap=target+(self.ap-target)*decay; self.peak=max(self.peak,self.ap)
            self.now=to
        return self.snapshot()
    def dispatch(self,rid,task,b):
        if b in self.owners: raise ValueError('cost lane occupied')
        self.owners[b]=(rid,task,b)
    def available(self,rid,b):
        if self.owners[b][0]!=rid: raise ValueError('cost owner identity')
        del self.owners[b]

class Device:
    def __init__(self,profile,service_source=None,device=None,split='train',environment_seed=0,npu=True,deterministic=False,initial=None,step_s=None):
        self.profile=copy.deepcopy(p.validate(profile)); self.device=device or profile['device']
        if self.device!=profile['device']: raise ValueError('device coefficient mixing')
        if split not in ('train','dev','confirm'): raise ValueError('split')
        self.model=copy.deepcopy(service_source if service_source is not None else profile['service_anchor'])
        if 'service' in self.model: self.model=self.model['service']
        if self.device=='A24' and self.model.get('schema')!='a24-dynamics-service-anchor-v1': self.model=p.normalize_service('A24',self.model)
        self.split=split; self.seed=int(environment_seed); self.npu=bool(npu and self.device=='S26'); self.deterministic=bool(deterministic)
        self.step_ns=round((step_s if step_s is not None else profile['step_s'])*1e9)
        if self.step_ns not in (25_000_000,50_000_000): raise ValueError('registered step')
        self.now=0; self._owners={b:None for b in BACKENDS}; self._work={}; self.records={}; self.events=[]
        self._recent={b:0. for b in BACKENDS}; self._activation={b:0. for b in BACKENDS}; self._last_task={b:None for b in BACKENDS}
        self._extra_energy=0.; self._extra_ap=0.; self._energy_startup=0.; self._energy_parallel=0.; self._energy_idle=0.
        self._ap_area=0.; self._ap_excess_area=0.; self._peak_ap=-math.inf; self._history=deque(maxlen=21)
        self._area_at35=None; self._peak_after35=None
        self.learning_cost_trace=[]; self.cost_trace=[]; self.integration_segments=0
        self.decision_revision=0; self._observed=None
        self._next_thermal_ns=profile['thermal_observation_period_ns']; self._next_power_ns=profile['power_observation_period_ns']
        init=self._initial(initial)
        self.reference_ap_c=init['reference_ap_c']; self.initial=init
        if self.device=='S26':
            from tools.d1_s26_observer_separate_heat import CostState
            boundary=copy.deepcopy(self.profile['cost_anchor']['default_initial_assumption'])
            boundary.update(anchor_s=0,mode='START0',owners={},energy_prefix_estimate_j=0.,baseline_w=init['baseline_w'],evidence='research_scenario_boundary_assumption')
            boundary['initial_c']={'AP':init['ap_c'],'SKIN':init['skin_c']}; boundary['reference_c']={'AP':init['reference_ap_c'],'SKIN':init['reference_skin_c']}
            boundary['temperature_prefix_area']={'AP':0.,'SKIN':0.}; boundary['temperature_prefix_peak']=copy.deepcopy(boundary['initial_c'])
            self._anchor=CostState(self.profile['cost_anchor'],boundary)
        else: self._anchor=_A24Anchor(self.profile,init)
        self._record(force=True)

    def _initial(self,initial):
        if self.device=='S26':
            d=self.profile['cost_anchor']['default_initial_assumption']
            result=dict(baseline_w=d['baseline_w'],ap_c=d['initial_c']['AP'],skin_c=d['initial_c']['SKIN'],reference_ap_c=d['reference_c']['AP'],reference_skin_c=d['reference_c']['SKIN'])
        else: result=dict(baseline_w=1.2,ap_c=31.,skin_c=29.,reference_ap_c=30.,reference_skin_c=29.)
        if initial:
            if set(initial)-set(result): raise ValueError('flat explicit initial boundary ABI')
            result.update(initial)
        if not all(math.isfinite(v) for v in result.values()) or result['baseline_w']<=0: raise ValueError('finite initial boundary')
        return result

    def routes(self,q): return routes(q,self.device,self.npu)

    def _key(self,q,b,jobs=()):
        if b not in self.routes(q): raise ValueError('unsupported task/backend')
        if self.device=='A24': return f"{q['task']}|{b}"
        labels=[(v['request']['task'],bb) for bb,v in self._owners.items() if v]+[(r['task'],bb) for r,bb in jobs]
        if b=='GPU' or q['task']=='detection' and ('classification','GPU') in labels: context='B2_PARALLEL'
        elif b=='NPU' or q['task']=='detection' and ('classification','NPU') in labels: context='NPU_PARALLEL'
        else: context='CPU_URGENT'
        return f"{context}|{q['task']}|{b}"

    def feasible(self,jobs):
        if not 1<=len(jobs)<=2 or len({q['id'] for q,b in jobs})!=len(jobs) or len({b for q,b in jobs})!=len(jobs): return False
        labels=[(v['request']['task'],b) for b,v in self._owners.items() if v]
        for q,b in jobs:
            if b not in BACKENDS or self._owners[b] or b not in self.routes(q) or q['id'] in self.records or q['arrival_ns']>self.now: return False
            labels.append((q['task'],b))
        allowed=[{('classification','GPU'),('detection','CPU')}]
        if self.npu: allowed.append({('classification','NPU'),('detection','CPU')})
        return len(labels)==1 or len(labels)==2 and set(labels) in allowed

    def _parallel(self,b,jobs=()):
        labels=[(v['request']['id'],bb,v['phase']) for bb,v in self._owners.items() if v]
        labels += [(q['id'],bb,'EXECUTING') for q,bb in jobs if not any(v[0]==q['id'] for v in labels)]
        return any(bb!=b and phase=='EXECUTING' for rid,bb,phase in labels)

    def _slowdown(self,b,jobs=(),observed=False):
        ap=self._observed['ap_c'] if observed else self._anchor.snapshot()['temperature_c']['AP']+self._extra_ap
        thermal=max(ap-self.reference_ap_c-self.profile['thermal_threshold_offset_c'],0.)*self.profile['thermal_slowdown_per_c'][b]
        recent=self._recent[b]*self.profile['recent_slowdown'][b]
        parallel=self.profile['parallel_extra_slowdown'][b] if self._parallel(b,jobs) else 0.
        return min(self.profile['max_slowdown'],1.+thermal+recent+parallel)

    def estimate(self,q,b,jobs=()):
        ds=[float(v) for v in self.model['means'][self._key(q,b,jobs)]]
        ds[1]*=q.get('work_units',1)*self._slowdown(b,jobs,observed=True)
        warm=1.-self._activation[b]
        switch=self._last_task[b] not in (None,q['task'])
        ds[0]+=(self.profile['startup_s'][b]*warm+self.profile['switch_s']*switch)*1e9
        return ds

    def public(self):
        return dict(now_ns=self.now,lanes=copy.deepcopy(self._owners),npu_enabled=self.npu,device=self.device,
            observed_responses=sum('response_ns' in r for r in self.records.values()),ap_c=self._observed['ap_c'],
            skin_c=self._observed['skin_c'],reference_ap_c=self.reference_ap_c,
            ambient_c=self.reference_ap_c,ambient_is_measured=False,power_w=self._observed['power_w'],
            thermal_observation_age_s=(self.now-self._observed['thermal_observed_at_ns'])/1e9,
            power_observation_age_s=(self.now-self._observed['power_observed_at_ns'])/1e9,
            observation_status='synthetic_periodic_last_completed_value; device sensor cache and acquisition delay uncalibrated',
            recent_activity=copy.deepcopy(self._recent),recent_load=copy.deepcopy(self._recent),activation_memory=copy.deepcopy(self._activation),
            observed_history=copy.deepcopy(list(self._history)))

    def _sample(self,q,b,key):
        if self.deterministic: return [float(round(v)) for v in self.model['means'][key]],None
        rows=self.model['pools'][self.split][key]
        # Policy-independent random number; context changes select another pool with the same quantile index.
        h=int.from_bytes(hashlib.sha256(f'{self.seed}/{q["id"]}/{b}'.encode()).digest()[:8],'big')
        row=rows[h%len(rows)]
        return [float(v) for v in row['durations_ns']],copy.deepcopy(row)

    def dispatch(self,jobs):
        for q,b in jobs: validate_request(q)
        if not self.feasible(jobs): raise ValueError('infeasible/duplicate dispatch')
        prepared=[]
        for q,b in jobs:
            key=self._key(q,b,jobs); ds,origin=self._sample(q,b,key); ds[1]*=q.get('work_units',1)
            warm=1.-self._activation[b]; switch=self._last_task[b] not in (None,q['task'])
            startup=self.profile['startup_j'][b]*warm+self.profile['switch_j']*switch
            ds[0]+=(self.profile['startup_s'][b]*warm+self.profile['switch_s']*switch)*1e9
            prepared.append((q,b,key,ds,origin,startup,self.estimate(q,b,jobs)))
        for q,b,key,ds,origin,startup,estimate in prepared:
            self._extra_energy+=startup; self._energy_startup+=startup
            self._work[b]=dict(durations=ds,left=ds[0],stage=0)
            self.records[q['id']]=dict(copy.deepcopy(q),backend=b,context=key,dispatch_ns=self.now,status='running',
                realized_work_ns=ds,sample_origin=origin,activation_energy_j=startup)
            self._owners[b]=dict(request=copy.deepcopy(q),phase='ASSIGNED',since=self.now,dispatch=self.now,estimate_ns=estimate)
            self._last_task[b]=q['task']; self._activation[b]=1.
            self._anchor.dispatch(q['id'],q['task'],b)
            self.events.append(dict(time_ns=self.now,id=q['id'],backend=b,phase='ASSIGNED'))
            self.decision_revision+=1
        self._settle(); self._record(force=True)

    def _settle(self):
        for b in BACKENDS:
            while self._owners[b] and self._work[b]['left']<=.500001:
                x=self._work[b]; owner=self._owners[b]; rid=owner['request']['id']; r=self.records[rid]; stage=x['stage']
                r[FIELDS[stage]]=self.now
                if stage==(1 if r['priority']=='urgent' else 2): r.update(response_ns=self.now-r['arrival_ns'],response_at_ns=self.now)
                if stage==4:
                    self._anchor.available(rid,b); self._owners[b]=None; del self._work[b]; r['status']='succeeded'; phase='AVAILABLE'
                else:
                    x['stage']+=1; x['left']=x['durations'][x['stage']]; phase=PHASES[x['stage']]; owner.update(phase=phase,since=self.now)
                self.events.append(dict(time_ns=self.now,id=rid,backend=b,phase=phase))
                self.decision_revision+=1

    def _rates(self): return {b:1./self._slowdown(b) if x['stage']==1 else 1. for b,x in self._work.items()}
    def next_event(self):
        if not self._work: return None
        rates=self._rates()
        roots=[max(1,math.ceil(x['left']/rates[b]-.000001)) for b,x in self._work.items()]
        next_grid=((self.now//self.step_ns)+1)*self.step_ns
        return min(HORIZON_NS,next_grid,self.now+min(roots),self._next_thermal_ns,self._next_power_ns)

    def _extra_power(self):
        executing=sum(x['stage']==1 for x in self._work.values())
        cross=self.profile['parallel_extra_w'] if executing==2 else 0.
        tail=sum(self.profile['idle_tail_w'][b]*self._activation[b] for b in BACKENDS if not self._owners[b])
        return cross,tail

    def _integrate(self,dt_ns,rates):
        dt=dt_ns/1e9; before_ap=self._anchor.snapshot()['temperature_c']['AP']; extra0=self._extra_ap
        cross,tail=self._extra_power()
        # Tail memory decays analytically, rather than a rectangular power overestimate.
        tau=self.profile['activation_tau_s']; tail_j=tail*tau*(-math.expm1(-dt/tau)); extra_j=cross*dt+tail_j
        avg_extra=extra_j/dt if dt else 0.
        self._extra_energy+=extra_j; self._energy_parallel+=cross*dt; self._energy_idle+=tail_j
        beta=self.profile['extra_heat_beta_per_s']; target=avg_extra*self.profile['extra_heat_gain_c_per_w']
        self._extra_ap=target+(extra0-target)*math.exp(-beta*dt)
        self._anchor.advance((self.now+dt_ns)/1e9); after_ap=self._anchor.snapshot()['temperature_c']['AP']
        # Temperature area uses a segment trapezoid for compound two-pole anchor; step convergence is tested separately.
        t0=before_ap+extra0; t1=after_ap+self._extra_ap
        self._ap_area+=(t0+t1)*dt/2
        # Integrate positive part of the linear segment exactly at its crossing.
        a=t0-self.reference_ap_c; z=t1-self.reference_ap_c
        if a>=0 and z>=0: area=(a+z)*dt/2
        elif a<=0 and z<=0: area=0.
        elif a>0: area=a*a*dt/(2*(a-z))
        else: area=z*z*dt/(2*(z-a))
        self._ap_excess_area+=area; self._peak_ap=max(self._peak_ap,t0,t1)
        for b in BACKENDS:
            u=float(b in self._work and self._work[b]['stage']==1)
            self._recent[b]=u+(self._recent[b]-u)*math.exp(-dt/self.profile['recent_tau_s'])
            self._activation[b]=1. if self._owners[b] else self._activation[b]*math.exp(-dt/tau)
        for b,x in self._work.items(): x['left']-=dt_ns*rates[b]
        self.now+=dt_ns; self.integration_segments+=1

    def advance(self,to):
        if type(to) is not int or not self.now<=to<=HORIZON_NS: raise ValueError('integer ns clock within120s')
        return self._advance_internal(to)

    def observe_cooling(self,to=180_000_000_000):
        """Private evaluation tail; never runs unfinished work or dispatches."""
        if type(to) is not int or not HORIZON_NS<=self.now<=to<=180_000_000_000 or any(self._owners.values()):
            raise ValueError('cooling requires all actual AVAILABLE at120')
        return self._advance_internal(to)

    def _advance_internal(self,to):
        self._settle()
        while self.now<to:
            rates=self._rates(); next_grid=((self.now//self.step_ns)+1)*self.step_ns
            roots=[max(1,math.ceil(x['left']/rates[b]-.000001)) for b,x in self._work.items()]
            nxt=min(to,next_grid,self.now+min(roots) if roots else to,self._next_thermal_ns,self._next_power_ns)
            self._integrate(nxt-self.now,rates); self._settle(); self._record()
        return self.current_cost()

    def _record(self,force=False):
        ap=self._anchor.snapshot()['temperature_c']['AP']+self._extra_ap; self._peak_ap=max(self._peak_ap,ap)
        if self.now==35_000_000_000 and self._area_at35 is None: self._area_at35=self._ap_area
        if self.now>=35_000_000_000: self._peak_after35=ap if self._peak_after35 is None else max(self._peak_after35,ap)
        row=dict(time_ns=self.now,energy_j=self._anchor.snapshot()['energy_window_j']+self._extra_energy,ap_excess_area_c_s=self._ap_excess_area)
        if self.now<=HORIZON_NS:
            if self.learning_cost_trace and self.learning_cost_trace[-1]['time_ns']==self.now: self.learning_cost_trace[-1]=row
            else: self.learning_cost_trace.append(row)
        observation_update=self._observed is None or self.now>=self._next_thermal_ns or self.now>=self._next_power_ns
        if observation_update:
            if self._observed is None:
                self._observed=dict(ap_c=ap,skin_c=self._anchor.snapshot()['temperature_c']['SKIN'],power_w=self.current_cost()['power_w'],thermal_observed_at_ns=self.now,power_observed_at_ns=self.now)
            if self.now>=self._next_thermal_ns:
                self._observed.update(ap_c=ap,skin_c=self._anchor.snapshot()['temperature_c']['SKIN'],thermal_observed_at_ns=self.now)
                self._next_thermal_ns+=self.profile['thermal_observation_period_ns']
            if self.now>=self._next_power_ns:
                self._observed.update(power_w=self.current_cost()['power_w'],power_observed_at_ns=self.now)
                self._next_power_ns+=self.profile['power_observation_period_ns']
            observed=dict(time_ns=self.now,**copy.deepcopy(self._observed))
            self._history.append(observed); self.decision_revision+=1
        if force or self.now%1_000_000_000==0:
            snap=dict(time_s=self.now/1e9,AP_c=ap,SKIN_c=self._anchor.snapshot()['temperature_c']['SKIN'],energy_j=row['energy_j'])
            if self.cost_trace and self.cost_trace[-1]['time_s']==snap['time_s']: self.cost_trace[-1]=snap
            else: self.cost_trace.append(snap)

    def current_cost(self):
        snap=self._anchor.snapshot(); cross,tail=self._extra_power()
        return dict(time_ns=self.now,energy_window_j=snap['energy_window_j']+self._extra_energy,
            anchor_energy_j=snap['energy_window_j'],additional_energy_j=self._extra_energy,
            activation_energy_j=self._energy_startup,parallel_extra_energy_j=self._energy_parallel,idle_tail_energy_j=self._energy_idle,
            power_w=snap['power_w']+cross+tail,ap_c=snap['temperature_c']['AP']+self._extra_ap,
            mean_ap_c=self._ap_area/(self.now/1e9) if self.now else snap['temperature_c']['AP'],peak_ap_c=self._peak_ap,
            mean_after35_c=(self._ap_area-self._area_at35)/(self.now/1e9-35.) if self._area_at35 is not None and self.now>35_000_000_000 else None,
            peak_after35_c=self._peak_after35,
            ap_excess_area_c_s=self._ap_excess_area,reference_ap_c=self.reference_ap_c,
            profile=self.profile['name'],evidence='hypothesis_only',hardware_validated=False,strict_eligible=False,experiment_ready=False)

class FrozenS26ServiceDevice(old.Device):
    """Actual frozen engine delegate, separate from v17 neutral dynamics.

    This is a service-contract check adapter, not a new thermal baseline.
    The existing frozen simulator remains the source of baseline J/temperature.
    """
    def __init__(self,source,split='train',environment_seed=0,npu=True,deterministic=False):
        super().__init__(source.get('service',source),split,environment_seed,npu,deterministic)

def simulate(profile,requests,controller,split='confirm',environment_seed=0,npu=True,deterministic=False,initial=None,step_s=None):
    if not requests or len(requests)>1200 or len({q['id'] for q in requests})!=len(requests): raise ValueError('bounded distinct roster')
    for q in requests: validate_request(q)
    dev=Device(profile,split=split,environment_seed=environment_seed,npu=npu,deterministic=deterministic,initial=initial,step_s=step_s)
    pending=sorted(copy.deepcopy(requests),key=lambda q:(q['arrival_ns'],q['ordinal'],q['id'])); waiting=[]; cursor=0; last_revision=None
    while dev.now<HORIZON_NS:
        dev.advance(dev.now)
        new_arrival=False
        while cursor<len(pending) and pending[cursor]['arrival_ns']<=dev.now: waiting.append(pending[cursor]); cursor+=1; new_arrival=True
        if waiting and (new_arrival or dev.decision_revision!=last_revision):
            last_revision=dev.decision_revision
            jobs=controller.choose(dev,waiting)
            if jobs:
                dev.dispatch(jobs); ids={q['id'] for q,b in jobs}; waiting=[q for q in waiting if q['id'] not in ids]; continue
        if cursor==len(pending) and not waiting and not dev._work: break
        times=[HORIZON_NS]
        if cursor<len(pending): times.append(pending[cursor]['arrival_ns'])
        if dev.next_event() is not None: times.append(dev.next_event())
        dev.advance(min(t for t in times if t>dev.now))
    service_end=dev.now; dev.advance(HORIZON_NS); ledger=[]
    for q in requests:
        row=copy.deepcopy(dev.records.get(q['id'],dict(q,status='unfinished')))
        if row['status']=='running': row['status']='unfinished'
        ledger.append(row)
    metrics=old.metrics(ledger); costs=copy.deepcopy(dev.current_cost()); complete=metrics['incomplete']==0
    learning_trace=copy.deepcopy(dev.learning_cost_trace); trace120=copy.deepcopy(dev.cost_trace)
    all_available=not any(dev._owners.values())
    cooling=copy.deepcopy(dev.observe_cooling()) if all_available else None
    metrics.update(energy_j=costs['energy_window_j'] if complete else None,energy_prefix_j=costs['energy_window_j'],
        resident_baseline_j=dev.initial['baseline_w']*120.,
        planned_work_units=sum(q.get('work_units',1) for q in requests),
        completed_work_units=sum(r.get('work_units',1) for r in ledger if r['status']=='succeeded'),
        mean_ap_c=cooling['mean_after35_c'] if complete and cooling else None,
        peak_ap_c=cooling['peak_after35_c'] if complete and cooling else None,
        mean_ap_0_120_c=costs['mean_ap_c'],peak_ap_0_120_c=costs['peak_ap_c'],ap_excess_area_c_s=costs['ap_excess_area_c_s'],
        cost_model_status='hypothesis_only',hardware_validated=False,strict_eligible=False,experiment_ready=False)
    return dict(schema=ABI,device=dev.device,profile=profile['name'],metrics=metrics,ledger=ledger,events=dev.events,
        service_end_ns=service_end,end_ns=HORIZON_NS,environment_seed=environment_seed,split=split,npu=dev.npu,
        cost_120=costs,cooling_180=cooling,cost_trace=dev.cost_trace,prefix_trace120=trace120,learning_cost_trace=learning_trace,
        cooling_status='provided; all actual AVAILABLE at120' if all_available else 'UNAVAILABLE; unfinished owner at120',
        integration_segments=dev.integration_segments,policy_cost_learning=False,hardware_validated=False,strict_eligible=False,experiment_ready=False)
