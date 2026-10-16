"""Separate V20 active-route power overlay; frozen V17 physics is preserved.

Added W is charged only during EXECUTING and enters the same extra-heat input.
All prices/rates are explicit exploration hypotheses, independent of policy ID.
"""
from __future__ import annotations
import copy
import math
from tools import d1_sched_dynamics_plant as base
from tools import d1_sched_dynamics_profiles as profiles

PROFILE_ABI='d1-sched-landscape-profile-v1'
ABI='d1-sched-landscape-event-plant-v1'
BACKENDS=base.BACKENDS
HORIZON_NS=base.HORIZON_NS

def _number(value):
    return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value) and value>=0

def validate(profile):
    if profile.get('abi')!=PROFILE_ABI:raise ValueError('explicit landscape profile ABI required')
    route=profile.get('active_route_extra_w',{b:0. for b in BACKENDS})
    if not isinstance(route,dict) or set(route)!=set(BACKENDS) or any(not _number(v) for v in route.values()):
        raise ValueError('active route W requires three finite nonnegative backend values')
    for key in ('switch_s_by_backend','switch_j_by_backend'):
        values=profile.get(key,{})
        if not isinstance(values,dict) or set(values)-set(BACKENDS) or any(not _number(v) for v in values.values()):
            raise ValueError('optional backend task-switch map')
    converted=copy.deepcopy(profile);converted['abi']=profiles.ABI;profiles.validate(converted)
    return profile

class Device(base.Device):
    def __init__(self,profile,*args,**kwargs):
        validate(profile)
        converted=copy.deepcopy(profile);converted['abi']=profiles.ABI
        converted.setdefault('active_route_extra_w',{b:0. for b in BACKENDS})
        self.landscape_abi=PROFILE_ABI
        self._route_energy_j={b:0. for b in BACKENDS}
        self._separate_parallel_j=0.
        super().__init__(converted,*args,**kwargs)

    def _switch_value(self,key,backend):
        return self.profile.get(key+'_by_backend',{}).get(backend,self.profile[key])

    def _route_power(self):
        return {b:self.profile['active_route_extra_w'][b] if b in self._work and self._work[b]['stage']==1 else 0. for b in BACKENDS}

    def _extra_power(self):
        parallel,tail=super()._extra_power()
        return parallel+sum(self._route_power().values()),tail

    def _integrate(self,dt_ns,rates):
        dt=dt_ns/1e9;route=self._route_power();parallel,_=super()._extra_power()
        # The inherited integral receives exactly the same total added power
        # for energy and heat. Its combined counter is split for reporting.
        super()._integrate(dt_ns,rates)
        self._separate_parallel_j+=parallel*dt
        for b,w in route.items():self._route_energy_j[b]+=w*dt

    def estimate(self,q,b,jobs=()):
        ds=super().estimate(q,b,jobs)
        if self._last_task[b] not in (None,q['task']):
            ds[0]+=(self._switch_value('switch_s',b)-self.profile['switch_s'])*1e9
        return ds

    def dispatch(self,jobs):
        if not self.profile.get('switch_s_by_backend') and not self.profile.get('switch_j_by_backend'):
            return super().dispatch(jobs)
        for q,b in jobs:base.validate_request(q)
        if not self.feasible(jobs):raise ValueError('infeasible/duplicate dispatch')
        prepared=[]
        for q,b in jobs:
            key=self._key(q,b,jobs);ds,origin=self._sample(q,b,key);ds[1]*=q.get('work_units',1)
            warm=1.-self._activation[b];switch=self._last_task[b] not in (None,q['task'])
            startup=self.profile['startup_j'][b]*warm+self._switch_value('switch_j',b)*switch
            ds[0]+=(self.profile['startup_s'][b]*warm+self._switch_value('switch_s',b)*switch)*1e9
            prepared.append((q,b,key,ds,origin,startup,self.estimate(q,b,jobs)))
        for q,b,key,ds,origin,startup,estimate in prepared:
            self._extra_energy+=startup;self._energy_startup+=startup
            self._work[b]=dict(durations=ds,left=ds[0],stage=0)
            self.records[q['id']]=dict(copy.deepcopy(q),backend=b,context=key,dispatch_ns=self.now,status='running',realized_work_ns=ds,sample_origin=origin,activation_energy_j=startup)
            self._owners[b]=dict(request=copy.deepcopy(q),phase='ASSIGNED',since=self.now,dispatch=self.now,estimate_ns=estimate)
            self._last_task[b]=q['task'];self._activation[b]=1.
            self._anchor.dispatch(q['id'],q['task'],b)
            self.events.append(dict(time_ns=self.now,id=q['id'],backend=b,phase='ASSIGNED'))
            self.decision_revision+=1
        self._settle();self._record(force=True)

    def current_cost(self):
        result=super().current_cost();power=self._route_power()
        result.update(parallel_extra_energy_j=self._separate_parallel_j,
            active_route_extra_energy_j=sum(self._route_energy_j.values()),
            active_route_extra_energy_by_backend_j=copy.deepcopy(self._route_energy_j),
            active_route_extra_w_current=sum(power.values()),
            active_route_extra_w_by_backend_current=power,
            landscape_abi=self.landscape_abi)
        return result

def simulate(profile,requests,controller,split='confirm',environment_seed=0,npu=True,deterministic=False,initial=None,step_s=None):
    """V17 event-loop contract with an injected V20 Device; no monkey patching."""
    if not requests or len(requests)>1200 or len({q['id'] for q in requests})!=len(requests):raise ValueError('bounded distinct roster')
    for q in requests:base.validate_request(q)
    dev=Device(profile,split=split,environment_seed=environment_seed,npu=npu,deterministic=deterministic,initial=initial,step_s=step_s)
    pending=sorted(copy.deepcopy(requests),key=lambda q:(q['arrival_ns'],q['ordinal'],q['id']));waiting=[];cursor=0;last_revision=None
    while dev.now<HORIZON_NS:
        dev.advance(dev.now);new_arrival=False
        while cursor<len(pending) and pending[cursor]['arrival_ns']<=dev.now:
            waiting.append(pending[cursor]);cursor+=1;new_arrival=True
        if waiting and (new_arrival or dev.decision_revision!=last_revision):
            last_revision=dev.decision_revision;jobs=controller.choose(dev,waiting)
            if jobs:
                dev.dispatch(jobs);ids={q['id'] for q,b in jobs};waiting=[q for q in waiting if q['id'] not in ids];continue
        if cursor==len(pending) and not waiting and not dev._work:break
        times=[HORIZON_NS]
        if cursor<len(pending):times.append(pending[cursor]['arrival_ns'])
        if dev.next_event() is not None:times.append(dev.next_event())
        dev.advance(min(t for t in times if t>dev.now))
    service_end=dev.now;dev.advance(HORIZON_NS);ledger=[]
    for q in requests:
        row=copy.deepcopy(dev.records.get(q['id'],dict(q,status='unfinished')))
        if row['status']=='running':row['status']='unfinished'
        ledger.append(row)
    metrics=base.old.metrics(ledger);costs=copy.deepcopy(dev.current_cost());complete=metrics['incomplete']==0
    learning_trace=copy.deepcopy(dev.learning_cost_trace);trace120=copy.deepcopy(dev.cost_trace)
    all_available=not any(dev._owners.values());cooling=copy.deepcopy(dev.observe_cooling()) if all_available else None
    metrics.update(energy_j=costs['energy_window_j'] if complete else None,energy_prefix_j=costs['energy_window_j'],
        resident_baseline_j=dev.initial['baseline_w']*120.,planned_work_units=sum(q.get('work_units',1) for q in requests),completed_work_units=sum(r.get('work_units',1) for r in ledger if r['status']=='succeeded'),
        mean_ap_c=cooling['mean_after35_c'] if complete and cooling else None,peak_ap_c=cooling['peak_after35_c'] if complete and cooling else None,
        mean_ap_0_120_c=costs['mean_ap_c'],peak_ap_0_120_c=costs['peak_ap_c'],ap_excess_area_c_s=costs['ap_excess_area_c_s'],
        active_route_extra_energy_j=costs['active_route_extra_energy_j'],cost_model_status='hypothesis_only',hardware_validated=False,strict_eligible=False,experiment_ready=False)
    return dict(schema=ABI,device=dev.device,profile=profile['name'],metrics=metrics,ledger=ledger,events=dev.events,
        service_end_ns=service_end,end_ns=HORIZON_NS,environment_seed=environment_seed,split=split,npu=dev.npu,
        cost_120=costs,cooling_180=cooling,cost_trace=dev.cost_trace,prefix_trace120=trace120,learning_cost_trace=learning_trace,
        cooling_status='provided; all actual AVAILABLE at120' if all_available else 'UNAVAILABLE; unfinished owner at120',
        integration_segments=dev.integration_segments,policy_cost_learning=False,hardware_validated=False,strict_eligible=False,experiment_ready=False)
