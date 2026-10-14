"""Explicit hypothetical power-coupled thermal reservoirs; current events only."""
import copy,math,types
from tools import d1_sched_dynamics_plant as base
from tools import d1_s26_refine28_runtime as measured
class RC:
    def __init__(self,cfg):
        if cfg['device']not in ('A24','S26')or abs(sum(cfg['fractions'])-1)>1e-12 or any(v<=0 for v in cfg['R']+cfg['tau_s']+cfg['fractions'])or cfg['baseline_w']<=0 or cfg['tail_tau_s']<=0:raise ValueError('positive normalized thermal profile')
        self.cfg=copy.deepcopy(cfg);self.now=0.;self.energy=0.;self.owners={};self.executing=set();self.last_release={};self.last_task={}
        self.theta=[w*r*cfg['baseline_w'] for w,r in zip(cfg['fractions'],cfg['R'])]
        self.initial_storage=sum(t*tau/r for t,tau,r in zip(self.theta,cfg['tau_s'],cfg['R']))
        self.loss=0.;self.parts={k:0. for k in ('baseline','active','parallel','tail','startup')}
    def storage(self):return sum(t*tau/r for t,tau,r in zip(self.theta,self.cfg['tau_s'],self.cfg['R']))
    def dispatch(self,rid,task,b):
        if b in self.owners:raise ValueError('duplicate owner')
        if task=='detection' and b!='CPU':raise ValueError('unsupported detector')
        if b=='NPU' and self.cfg['device']!='S26':raise ValueError('unsupported NPU')
        labels={(v[1],k)for k,v in self.owners.items()}|{(task,b)}
        if len(labels)>2 or len(labels)==2 and labels not in ({('classification','GPU'),('detection','CPU')},{('classification','NPU'),('detection','CPU')}):raise ValueError('unsupported pair')
        warm=math.exp(-(self.now-self.last_release[b])/self.cfg['tail_tau_s'])if b in self.last_release else 0.
        e=self.cfg['startup_j'][b]*(1-warm)+(self.cfg['switch_j']if b in self.last_task and self.last_task[b]!=task else 0.)
        self.energy+=e;self.parts['startup']+=e
        for i,(w,r,tau)in enumerate(zip(self.cfg['fractions'],self.cfg['R'],self.cfg['tau_s'])):self.theta[i]+=w*e*r/tau
        self.owners[b]=(rid,task);self.last_task[b]=task
    def available(self,rid,b):
        if b not in self.owners or self.owners[b][0]!=rid:raise ValueError('AVAILABLE identity')
        del self.owners[b];self.executing.discard(b);self.last_release[b]=self.now
    def sync(self,work):self.executing={b for b,w in work.items()if w['stage']==1}
    def components(self):
        active=sum(self.cfg['route_w'][task+'|'+b]*(1. if b in self.executing else self.cfg['nonexecution_fraction'])for b,(rid,task)in self.owners.items())
        cross=self.cfg['parallel_w']if len(self.executing)==2 else 0.
        tail=sum(self.cfg['tail_w'][b]*math.exp(-(self.now-t)/self.cfg['tail_tau_s'])for b,t in self.last_release.items()if b not in self.owners)
        return self.cfg['baseline_w'],active,cross,tail
    def advance(self,to):
        dt=to-self.now
        if dt<0 or not math.isfinite(to):raise ValueError('clock')
        if dt==0:return self.snapshot()
        baseline,active,cross,tail=self.components();constant=baseline+active+cross;tt=self.cfg['tail_tau_s'];old=self.storage()
        tail_j=tail*tt*(-math.expm1(-dt/tt));added=constant*dt+tail_j
        for i,(w,r,tau)in enumerate(zip(self.cfg['fractions'],self.cfg['R'],self.cfg['tau_s'])):
            decay=math.exp(-dt/tau);den=1/tau-1/tt
            conv=dt*decay if abs(den)<1e-12 else(math.exp(-dt/tt)-decay)/den
            self.theta[i]=self.theta[i]*decay+w*r*constant*(1-decay)+w*r*tail/tau*conv
        self.energy+=added;self.loss+=added-(self.storage()-old)
        for k,v in zip(('baseline','active','parallel','tail'),(baseline*dt,active*dt,cross*dt,tail_j)):self.parts[k]+=v
        self.now=to;return self.snapshot()
    def snapshot(self):
        return dict(time_s=self.now,power_w=sum(self.components()),energy_window_j=self.energy,temperature_c={'AP':self.cfg['reference_c']+sum(self.theta),'SKIN':self.cfg['reference_c']+self.theta[-1]},thermal_energy_balance_error_j=self.energy-(self.storage()-self.initial_storage)-self.loss,components_j=copy.deepcopy(self.parts),evidence='hypothetical two-reservoir temperature proxies; not measured sensors')
class Device(base.Device):
    def __init__(self,profile,*a,**kw):
        super().__init__(profile,*a,**kw);self._anchor=RC(profile['exploration31']);self.reference_ap_c=profile['exploration31']['reference_c'];snap=self._anchor.snapshot()
        self.initial.update(ap_c=snap['temperature_c']['AP'],skin_c=snap['temperature_c']['SKIN'],baseline_w=profile['exploration31']['baseline_w'])
        self._observed=None;self._history.clear();self.cost_trace.clear();self.learning_cost_trace.clear();self._peak_ap=snap['temperature_c']['AP'];self._record(force=True)
    def _record(self,force=False):
        if isinstance(self._anchor,RC):self._anchor.sync(self._work)
        return super()._record(force)
    def _integrate(self,dt,rates):
        self._anchor.sync(self._work);super()._integrate(dt,rates)
    def current_cost(self):
        r=super().current_cost()
        if isinstance(self._anchor,RC):
            s=self._anchor.snapshot();r.update(thermal_energy_balance_error_j=s['thermal_energy_balance_error_j'],exploration_components_j=s['components_j'])
        return r
def simulate(profile,requests,controller,**kwargs):
    if 'exploration31'not in profile:return measured.simulate(profile,requests,controller,**kwargs)
    scope=dict(base.simulate.__globals__);scope['Device']=Device
    fn=types.FunctionType(base.simulate.__code__,scope,'exploration31',base.simulate.__defaults__);r=fn(profile,requests,controller,**kwargs)
    r.update(schema='hypothetical-power-coupled31',physical_claim='exploration only; synthetic AP/SKIN proxies',online_learning=False)
    r['metrics'].update(hardware_validated=False,strict_eligible=False,experiment_ready=False)
    return r
