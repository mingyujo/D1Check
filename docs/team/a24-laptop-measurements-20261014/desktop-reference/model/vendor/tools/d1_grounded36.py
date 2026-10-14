"""Power-coupled, evidence-graded exploration. No fitted hardware DVFS claim."""
import copy,math
import numpy as np
from tools import d1_sched_dynamics_plant as base
from tools import d1_sim_complete33 as contract
from tools import d1_measured35 as measured
from tools import d1_sched_dynamics_policy as policy
from tools import d1_dual_trend27_runtime as trend

VERSION='grounded-range-current-event-v36'
def initial_background(profile,t):
    if profile['device']=='A24':
        c=profile['trend27_anchor'];pub=c['public_boundary'];p=trend.initialize_a24(pub['pre'],pub['beta']);dt=t-p['anchor_s']
        init=(p['reference_c']-p['initial_c'])*(-math.expm1(-pub['beta']*dt))+p['h_last']*trend.convolution(pub['beta'],30.,dt)
        return p['initial_c']+c['thermal']['AP']['coefficients'][-1]*init
    c=profile['trend27_anchor']['thermal']['AP']['initial_thermal'];p=profile['trend27_anchor']['preserved23_initial']
    if c['initial_mode']!='legacy':raise ValueError('explicit inherited legacy AP observation background')
    return p['reference_c']['AP']+(p['initial_c']['AP']-p['reference_c']['AP'])*math.exp(-c['beta_per_s']*t)

def relative_rate(ap,cfg):
    delta=max(ap-cfg['throttle_on_c'],0.)
    return max(cfg['rate_min'],1.-cfg['slope_per_c']*delta)

class CoupledCost:
    def __init__(self,profile):
        self.profile=profile;self.cfg=profile['grounded36'];self.now=0.;self.energy=0.;self.owners={};self.activity=np.zeros(6);self.work={};self.rates={};self.q=0.
        self.tau=np.asarray(self.cfg['tau_s']);self.gain=np.asarray(self.cfg['gain_c_per_w']);self.fractions=np.array([.5,.5]);self.R=self.gain/self.fractions;self.C=self.tau/self.R
        self.baseline=self.cfg['baseline_w'];self.equilibrium=self.gain*self.baseline;self.theta=self.equilibrium+self.cfg.get('warm_c',0.)/2
        self.initial_storage=float(self.theta@self.C);self.loss=0.;self.last_power=self.baseline;self.parts={k:0. for k in ('baseline','active','parallel')};self.rate_occ_s=0.;self.low_rate_occ_s=0.;self.pair_s=0.
        self.init_params=None
        if profile['device']=='A24':
            c=profile['trend27_anchor'];pub=c['public_boundary'];self.init_params=trend.initialize_a24(pub['pre'],pub['beta'])
    def background(self,t):
        if self.init_params is None:return initial_background(self.profile,t)
        p=self.init_params;cfg=self.profile['trend27_anchor'];pub=cfg['public_boundary'];dt=t-p['anchor_s'];z=(p['reference_c']-p['initial_c'])*(-math.expm1(-pub['beta']*dt))+p['h_last']*trend.convolution(pub['beta'],30.,dt)
        return p['initial_c']+cfg['thermal']['AP']['coefficients'][-1]*z
    def dispatch(self,rid,task,b):
        if b in self.owners or rid in [r[0]for r in self.owners.values()]:raise ValueError('duplicate owner')
        self.owners[b]=(rid,task)
    def available(self,rid,b):
        if b not in self.owners or self.owners[b][0]!=rid:raise ValueError('actualAVAILABLE identity')
        del self.owners[b]
    def sync(self,work,rates):self.work=work;self.rates=rates
    def set_activity(self,u):self.activity=np.asarray(u,float).copy()
    def factor(self,b):
        r=self.rates.get(b,1.);return self.cfg['static_fraction']+(1-self.cfg['static_fraction'])*r**self.cfg['power_exponent']
    def advance(self,to):
        dt=to-self.now
        if dt<0:raise ValueError('monotonic physical clock')
        if not dt:return self.snapshot()
        executing=[b for b,w in self.work.items()if w['stage']==1];pair=len(executing)==2
        if self.profile['device']=='A24':
            key='+'.join(sorted(task+'_'+b for b,(rid,task)in self.owners.items()))
            active=self.cfg['increments_w'].get(key,0.)
            factors=[self.factor(b)if b in executing else 1. for b in self.owners]
            active*=sum(factors)/len(factors)if factors else 1.
            cpu=float('CPU'in executing)
        else:
            c=self.cfg['power_coefficients'];u=self.activity;cpu=min(u[0]+u[1]+u[4],1.)
            a=1+4*cpu;b=4*(self.q-cpu)
            # Exact area of causal 1/(1+4*recentCPU); stable for small dt.
            ratio=5/a*math.log1p(a*math.expm1(dt/5)/(a+b))/dt
            components=u*np.asarray(c[4:10]);components[:2]*=ratio
            for j,bk in enumerate(('CPU','CPU','GPU','NPU')):components[j]*=self.factor(bk)
            common=[self.factor(bk)for bk in executing]
            components[4]*=sum(common)/len(common)if common else 1.
            active=float(components.sum())+(c[10]if self.owners else 0.)
        cross=self.cfg['parallel_power_fraction']*active if pair else 0.
        constant=self.baseline+active+cross;tail=self.cfg.get('initial_tail_w',0.)*math.exp(-self.now/30)
        energy=constant*dt+tail*30*(-math.expm1(-dt/30));old=float(self.theta@self.C)
        for i,(gain,tau)in enumerate(zip(self.gain,self.tau)):
            decay=math.exp(-dt/tau);self.theta[i]=self.theta[i]*decay+gain*constant*(1-decay)+gain*tail/tau*trend.convolution(1/tau,30.,dt)
        self.energy+=energy;self.loss+=energy-(float(self.theta@self.C)-old);self.q=cpu+(self.q-cpu)*math.exp(-dt/5)
        self.parts['baseline']+=self.baseline*dt+tail*30*(-math.expm1(-dt/30));self.parts['active']+=active*dt;self.parts['parallel']+=cross*dt
        self.rate_occ_s+=len(executing)*dt;self.low_rate_occ_s+=sum(self.rates.get(b,1.)<.999 for b in executing)*dt;self.pair_s+=pair*dt
        self.now=to;self.last_power=constant+tail*math.exp(-dt/30);return self.snapshot()
    def snapshot(self):
        ap=self.background(self.now)+float(np.sum(self.theta-self.equilibrium))
        return dict(time_s=self.now,power_w=self.last_power,energy_window_j=self.energy,temperature_c={'AP':ap,'SKIN':self.cfg['skin_placeholder_c']},evidence='empirical initial AP observation + passive work heat; exploration not device identification',thermal_energy_balance_error_j=self.energy-(float(self.theta@self.C)-self.initial_storage)-self.loss,energy_component_sum_error_j=self.energy-sum(self.parts.values()),components_j=copy.deepcopy(self.parts),pair_occupancy_s=self.pair_s,throttled_execution_fraction=self.low_rate_occ_s/self.rate_occ_s if self.rate_occ_s else 0.)

class Device(base.Device):
    def __init__(self,profile,*a,**kw):
        super().__init__(profile,*a,**kw);self._anchor=CoupledCost(profile);self.reference_ap_c=profile['grounded36']['reference_ap_c'];snap=self._anchor.snapshot()
        self.initial.update(ap_c=snap['temperature_c']['AP'],skin_c=snap['temperature_c']['SKIN'],baseline_w=profile['grounded36']['baseline_w']);self._observed=None;self._history.clear();self.cost_trace.clear();self.learning_cost_trace.clear();self._peak_ap=snap['temperature_c']['AP'];self._record(force=True)
    def _slowdown(self,b,jobs=(),observed=False):
        cfg=self.profile['grounded36'];params=cfg['policy_estimate']if observed else cfg
        ap=self._observed['ap_c']if observed else self._anchor.snapshot()['temperature_c']['AP']
        rate=relative_rate(ap,params);delay=params['parallel_delay']if self._parallel(b,jobs)else 0.
        return (1+delay)/rate
    def _integrate(self,dt_ns,rates):
        # S26 subphase timing is the existing fixed M6 envelope approximation.
        remaining=dt_ns
        while remaining:
            part=remaining
            if self.device=='S26':
                for b,w in self._work.items():
                    if w['stage']!=1:continue
                    rr=self.records[self._owners[b]['request']['id']];ratios=self.profile['refine26_anchor']['execution_subphase_ratios'][rr['context']];elapsed=w['durations'][1]-w['left']
                    for frac in ratios:
                        distance=frac*w['durations'][1]-elapsed
                        if distance>.500001:part=min(part,max(1,math.ceil(distance/rates[b]-.000001)))
                u=np.zeros(6)
                for b,w in self._work.items():
                    rr=self.records[self._owners[b]['request']['id']]
                    if w['stage']==1:
                        ratios=self.profile['refine26_anchor']['execution_subphase_ratios'][rr['context']];center=(w['durations'][1]-w['left']+part*rates[b]/2)/w['durations'][1]
                        if center<ratios[0]:u[4]+=1
                        elif center<ratios[1]:u[{('classification','CPU'):0,('detection','CPU'):1,('classification','GPU'):2,('classification','NPU'):3}[rr['task'],b]]+=1
                    elif w['stage']>=2:u[5]+=1
                self._anchor.set_activity(u)
            self._anchor.sync(self._work,rates);base.Device._integrate(self,part,rates);remaining-=part
    def current_cost(self):
        r=super().current_cost();r.update({k:v for k,v in self._anchor.snapshot().items()if k in ('thermal_energy_balance_error_j','energy_component_sum_error_j','components_j','pair_occupancy_s','throttled_execution_fraction')});return r
    def estimate(self,q,b,jobs=()):return super().estimate(q,b,jobs)

class Timer:
    def __init__(self,device):self.dev=device;self.deadline=None;self.wait_start=None;self.wait_used=0;self.wait_events=[];self.revision=0
    def __getattr__(self,name):return getattr(self.dev,name)
    @property
    def decision_revision(self):return self.dev.decision_revision+self.revision
    def cancel(self,reason):
        if self.deadline is not None:
            elapsed=max(0,self.now-self.wait_start);self.wait_used+=elapsed;self.wait_events.append(dict(time_ns=self.now,event='WAIT_END',elapsed_ns=elapsed,reason=reason));self.deadline=None;self.wait_start=None;self.revision+=1
    def reserve(self,quantum):
        if self.deadline is not None:raise ValueError('double WAIT')
        self.wait_start=self.now;self.deadline=self.now+quantum;self.wait_events.append(dict(time_ns=self.now,event='WAIT_START',quantum_ns=quantum));self.revision+=1
    def advance(self,to):
        self.dev.advance(to)
        if self.deadline is not None and self.now>=self.deadline:self.cancel('timer')
    def next_event(self):
        values=[self.dev.next_event(),self.deadline]
        if self.deadline is not None:values +=[self.dev._next_power_ns,self.dev._next_thermal_ns]
        return min(v for v in values if v is not None and v>self.now)if any(v is not None and v>self.now for v in values)else None

class Controller:
    def __init__(self,inner,wait_kind=None):self.inner=inner;self.wait_kind=wait_kind;self.audit=[];self.decisions=[];self.errors=[]
    def choose(self,dev,waiting):
        dev.cancel('event_redecision');bank=policy.build(dev,waiting);legal=[i for i,m in enumerate(bank['mask'])if m];quantum=0;allowed=False
        if self.wait_kind and waiting and all(q['priority']=='normal'for q in waiting)and any(bank['actions'][i]for i in legal):
            quantum=100_000_000 if self.wait_kind=='short'else 500_000_000
            if dev.device=='S26':quantum//=2
            cfg=dev.profile.get('grounded36',{});reference=cfg.get('policy_estimate',{}).get('throttle_on_c',dev.reference_ap_c+4)
            public=dev.public();slacks=[q['arrival_ns']+q['deadline_offset_ns']-dev.now-min(policy.response(ds,q)for (rid,b),ds in bank['paths'].items()if rid==q['id'])for q in waiting]
            maximum=5_000_000_000 if dev.device=='A24'else 3_000_000_000
            allowed=public['ap_c']>=reference and dev.wait_used+quantum<=maximum and min(slacks)>=quantum+50_000_000 and dev.now+quantum<=base.HORIZON_NS
        if allowed:jobs=None;dev.reserve(quantum);idx=None
        else:
            jobs=self.inner.choose(dev,waiting);key=[(q['id'],b)for q,b in jobs or []];idx=next((i for i in legal if [(q['id'],b)for q,b in bank['actions'][i]]==key),None)
            if idx is None:raise ValueError('controller outside legal non-delay mask')
        self.audit.append(dict(time_ns=dev.now,waiting=[q['id']for q in waiting],legal_indices=legal,chosen_index=idx,chosen=[(q['id'],b)for q,b in jobs or []],optional_WAIT=allowed,wait_quantum_ns=quantum if allowed else 0,physical_feasible=dev.feasible(jobs)if jobs else True,future_input=False))
        decision=dict(bank['diagnostics']);decision.update(now_ns=dev.now,wait=allowed,queue=len(waiting));self.decisions.append(decision);return jobs

def simulate(profile,requests,controller,environment_seed=0,step_s=None,deterministic=False):
    for q in requests:
        contract.validate(q)
        if q.get('work_units',1)!=1:raise ValueError('unit1 only')
    cls=Device if 'grounded36'in profile else measured.A24Device if profile['device']=='A24'else measured.S26Device
    dev=Timer(cls(profile,split='confirm',environment_seed=environment_seed,npu=True,step_s=step_s,deterministic=deterministic));pending=sorted(copy.deepcopy(requests),key=lambda q:(q['arrival_ns'],q['ordinal'],q['id']));waiting=[];cursor=0;last_revision=None
    while dev.now<base.HORIZON_NS:
        dev.advance(dev.now);arrived=False
        while cursor<len(pending)and pending[cursor]['arrival_ns']<=dev.now:waiting.append(pending[cursor]);cursor+=1;arrived=True
        if waiting and(arrived or last_revision!=dev.decision_revision):
            last_revision=dev.decision_revision;jobs=controller.choose(dev,waiting)
            if jobs:
                dev.dispatch(jobs);ids={q['id']for q,b in jobs};waiting=[q for q in waiting if q['id']not in ids];continue
        if cursor==len(pending)and not waiting and not dev._work:break
        times=[base.HORIZON_NS]
        if cursor<len(pending):times.append(pending[cursor]['arrival_ns'])
        event=dev.next_event()
        if event is not None:times.append(event)
        dev.advance(min(t for t in times if t>dev.now))
    service_end=dev.now;dev.advance(base.HORIZON_NS);dev.cancel('horizon');ledger=[]
    for q in requests:
        r=copy.deepcopy(dev.records.get(q['id'],dict(q,status='unfinished')))
        if r['status']=='running':r['status']='unfinished'
        ledger.append(r)
    metrics=contract.active_metrics(ledger,base.old.metrics(ledger),base.HORIZON_NS);cost=copy.deepcopy(dev.current_cost());trace=copy.deepcopy(dev.cost_trace);complete=metrics['incomplete']==0;cool=copy.deepcopy(dev.observe_cooling())if not any(dev._owners.values())else None
    metrics.update(energy_j=cost['energy_window_j']if complete else None,energy_prefix_j=cost['energy_window_j'],mean_ap_0_120_c=cost['mean_ap_c'],peak_ap_0_120_c=cost['peak_ap_c'],mean_ap_c=cool['mean_after35_c']if complete and cool else None,peak_ap_c=cool['peak_after35_c']if complete and cool else None,energy_180_j=cool['energy_window_j']if complete and cool else None,normal70=metrics['normal_on_time']*10>=metrics['normal_planned']*7 if metrics['normal_planned']else None)
    return dict(schema=VERSION,device=dev.device,npu=dev.npu,split='confirm',profile=profile['name'],metrics=metrics,ledger=ledger,events=dev.events,service_end_ns=service_end,end_ns=base.HORIZON_NS,cost_120=cost,cooling_180=cool,prefix_trace120=trace,cost_trace=dev.cost_trace,wait_events=dev.wait_events,wait_used_ns=dev.wait_used,environment_seed=environment_seed,audit=controller.audit,decisions=controller.decisions,online_learning=False,hardware_validated=False,strict_eligible=False,experiment_ready=False)
