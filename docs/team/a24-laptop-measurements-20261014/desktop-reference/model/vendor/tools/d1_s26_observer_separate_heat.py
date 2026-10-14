"""Separate thermal basis correction; parent power stays byte-for-byte frozen."""
import copy
import math
from tools import d1_s26_pair_observer_model as c
from tools import d1_s26_pair_observer_runtime as parent
from tools import d1_s26_integrated as service
from tools import d1_s26_npu_engine as e
from tools.d1_s26_cost_refine_model import current_vector

ABI='s26-paired-observed-separated-heat-v6'
SCHEMA='s26-pair-observer-separated-heat-v2'


def validate(p):
    if p['abi']!=ABI:raise ValueError('separate heat ABI')
    old=copy.deepcopy(p);old['abi']=c.ABI;c.validate(old)
    for m in p['thermal'].values():
        if m.get('alpha',p['alpha']) not in (0,1,4) or m.get('q_threshold',p['q_threshold']) not in (0,.25,.5) or m.get('tau_h_s',p['tau_h_s']) not in (.5,5,15):raise ValueError('per-sensor structural settings')
    return p


class CostState(c.CostState):
    def __init__(self,p,init):
        validate(p);old=copy.deepcopy(p);old['abi']=c.ABI;super().__init__(old,init);self.profile=p
        self.power_basis=c.Basis(p['alpha'],p['q_threshold'],p['tau_h_s'])
        self.basis={k:c.Basis(m.get('alpha',p['alpha']),m.get('q_threshold',p['q_threshold']),m.get('tau_h_s',p['tau_h_s']),m['beta_per_s'],m['mix']) for k,m in p['thermal'].items()}

    def advance(self,to):
        if not math.isfinite(to) or to<self.now:raise ValueError('cost boundary clock')
        u=current_vector(self.owners,'task')
        while self.now<to:
            nxt=min(to,(math.floor((self.now-self.anchor)*4+1e-9)+1)/4+self.anchor);elapsed=nxt-self.anchor
            self.power_basis.advance(elapsed,u)
            for b in self.basis.values():b.advance(elapsed,u)
            self.now=nxt;self.hist_times.append(elapsed)
            for k,b in self.basis.items():self.hist[k].append(((b.mix*b.fast+(1-b.mix)*b.slow).copy(),b.heat_area.copy()))
            self.energy=self.init['energy_prefix_estimate_j']+self.init['baseline_w']*elapsed+float(self.power_basis.area@self.profile['power']['coefficients'])
            for k,m in self.profile['thermal'].items():
                _,ha=self._history(k,max(0,elapsed-m['delay_s']));_,_,base,init=c.initial_terms(m,self.init,k,[elapsed])
                self.temperature_area[k]=self.init['temperature_prefix_area'][k]+float(base[0]+ha@m['coefficients'][:6]+init[0]@m['coefficients'][6:])
            if self.now==35:self.area_at35=dict(self.temperature_area)
            self._record()
        return self.snapshot()

    def dispatch(self,rid,task,backend):
        super().dispatch(rid,task,backend);self.power_basis.dispatch();self.power_basis.h=1.

    def snapshot(self):
        result=super().snapshot();phi=self.power_basis.current(current_vector(self.owners,'task'));result['power_w']=self.init['baseline_w']+float(phi@self.profile['power']['coefficients']);result['separate_thermal_structure']=True;return result


class Device(service.IntegratedDevice):
    def __init__(self,bundle,split='confirm',environment_seed=0,npu=True,deterministic=False,initial=None):
        if bundle['schema']!=SCHEMA or bundle.get('strict_eligible') is not False or bundle.get('experiment_ready') is not False:raise ValueError('separate heat runtime schema')
        validate(bundle['cost']);e.Device.__init__(self,bundle['service'],split,environment_seed,npu,deterministic)
        init=copy.deepcopy(initial or bundle['cost']['default_initial_assumption']);c.validate_initial(init,bundle['cost']);self.now=int(init['anchor_s']*1e9);self.cost=CostState(bundle['cost'],init)


def simulate(bundle,requests,controller,split='confirm',environment_seed=0,npu=True,deterministic=False,initial=None):
    parent.validate_boundary_requests(requests,bundle['cost']['mode']);pending=sorted(copy.deepcopy(requests),key=lambda q:(q['arrival_ns'],q['ordinal'],q['id']))
    dev=Device(bundle,split,environment_seed,npu,deterministic,initial);waiting=[];cursor=0
    while dev.now<e.HORIZON:
        dev.advance(dev.now)
        while cursor<len(pending) and pending[cursor]['arrival_ns']<=dev.now:waiting.append(pending[cursor]);cursor+=1
        if waiting:
            jobs=controller.choose(dev,waiting)
            if jobs:
                dev.dispatch(jobs);ids={q['id'] for q,b in jobs};waiting=[q for q in waiting if q['id'] not in ids];continue
        if cursor==len(pending) and not waiting and dev.next_event() is None:break
        future=[e.HORIZON]
        if cursor<len(pending):future.append(pending[cursor]['arrival_ns'])
        if dev.next_event() is not None:future.append(dev.next_event())
        dev.advance(min(t for t in future if t>dev.now))
    service_end=dev.now;dev.advance(e.HORIZON);ledger=[]
    for q in requests:
        r=copy.deepcopy(dev.records.get(q['id'],dict(q,status='unfinished')))
        if r['status']=='running':r['status']='unfinished'
        ledger.append(r)
    metrics=e.metrics(ledger);prefix=copy.deepcopy(dev.current_cost());all_available=not dev.cost.owners
    if all_available:dev.cost.advance(180);cool=dev.current_cost()
    else:cool=None
    complete=metrics['incomplete']==0;metrics.update(energy_j=prefix['energy_window_j'] if complete else None,peak_ap_c=cool['peak_after35_c']['AP'] if complete and cool else None,mean_ap_c=cool['mean_after35_c']['AP'] if complete and cool else None,cost_model_status='separated_thermal_observer06',strict_eligible=False,experiment_ready=False)
    return dict(schema=SCHEMA,metrics=metrics,ledger=ledger,events=dev.events,service_end_ns=service_end,end_ns=e.HORIZON,environment_seed=environment_seed,npu=npu,cost_120=prefix,cooling_180=cool,cost_trace=dev.cost.grid,initialization_mode=bundle['cost']['mode'],initialization_evidence=dev.cost.init['evidence'],policy_cost_learning=False,strict_eligible=False,experiment_ready=False)
