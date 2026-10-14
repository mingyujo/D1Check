"""Empirical state occupancy and causal recent-duty correction, separate v35.

No hardware time constant or independent chip power is claimed. Failed
development candidates retain the prior. No policy name is a physical input.
"""
import copy,math,types
import numpy as np
from tools import d1_sim_complete33 as prior
from tools import d1_dual_trend27_runtime as trend

VERSION='measured-development-state-memory-v35'
STATES={'A24':('classification_CPU','detection_CPU','classification_GPU','classification_GPU+detection_CPU'),
        'S26':('classification_CPU','detection_CPU','classification_GPU','classification_NPU','classification_GPU+detection_CPU','classification_NPU+detection_CPU')}

def transition(fast,slow,h,index,dt,cfg):
    """Exact current-state integration; future requests never enter."""
    n=len(STATES[cfg['device']]);u=np.zeros(n)
    if index is not None:u[index]=1.
    active=float(index is not None);tau=20.;dec=math.exp(-dt/tau)
    area_h=active*dt+(h-active)*tau*(-math.expm1(-dt/tau))
    if cfg['memory']:
        exposure=np.r_[u*(dt-area_h),u*area_h]
        beta=cfg['beta'];area=(-math.expm1(-beta*dt))/beta
        hot=active*area+(h-active)*trend.convolution(beta,tau,dt)
        forcing=np.r_[u*(area-hot),u*hot]
    else:
        exposure=u*dt;forcing=u*(-math.expm1(-cfg['beta']*dt))/cfg['beta']
    next_fast=fast*math.exp(-cfg['beta']*dt)+forcing
    slow=slow*math.exp(-dt/cfg['slow_tau_s'])+active*cfg['slow_tau_s']*(-math.expm1(-dt/cfg['slow_tau_s']))
    return next_fast,slow,active+(h-active)*dec,exposure

def bases(intervals,times,cfg):
    """Offline current-state replay. Times are target queries, not state inputs."""
    times=np.asarray(times,float);edges=sorted({0.,*times,*[r['start_s']for r in intervals],*[r['end_s']for r in intervals]})
    n=len(STATES[cfg['device']])*(2 if cfg['memory']else 1)
    f=np.zeros(n);s=h=0.;energy=np.zeros(n);thermal={};power={};last=0.;pos=0
    valid=[r for r in intervals if r['end_s']>r['start_s']];valid.sort(key=lambda r:r['start_s'])
    for at in edges:
        if at<0:continue
        mid=(last+at)/2
        while pos<len(valid)and valid[pos]['end_s']<=mid:pos+=1
        label=valid[pos]['state']if pos<len(valid)and valid[pos]['start_s']<=mid<valid[pos]['end_s']else'idle'
        label='+'.join(sorted(label.replace(':','_').split('+')))
        index=STATES[cfg['device']].index(label)if label not in ('idle','resident_idle')else None
        f,s,h,ex=transition(f,s,h,index,at-last,cfg);energy+=ex
        thermal[at]=np.r_[f,s];power[at]=energy.copy();last=at
    return np.stack([power[t]for t in times]),np.stack([thermal[t]for t in times])

class CompactCost:
    def __init__(self,original,profile):
        self.original=original;self.idle=copy.deepcopy(original);self.cfg=copy.deepcopy(profile['measured35']);self.now=0.;self.owners={}
        n=len(STATES[profile['device']]);pc=self.cfg['power'];tc=self.cfg['thermal']
        self.pfast=np.zeros(n*(2 if pc['memory']else 1));self.tfast=np.zeros(n*(2 if tc['memory']else 1))
        self.pslow=self.tslow=self.ph=self.th=0.;self.energy=0.;self.initial_ap=self.idle.snapshot()['temperature_c']['AP']
    def key(self):
        return '+'.join(sorted(task+'_'+b for rid,task,b in self.owners.values()))if self.owners else'idle'
    def dispatch(self,rid,task,b):
        if b in self.owners or rid in [r[0]for r in self.owners.values()]:raise ValueError('duplicate owner')
        self.original.dispatch(rid,task,b);self.owners[b]=(rid,task,b)
        if self.key()not in STATES[self.cfg['device']]:raise ValueError('unsupported state')
    def available(self,rid,b):
        if b not in self.owners or self.owners[b][0]!=rid:raise ValueError('AVAILABLE identity')
        self.original.available(rid,b);del self.owners[b]
    def set_activity(self,v):
        if hasattr(self.original,'set_activity'):self.original.set_activity(v)
    def baseline(self,t):
        if self.cfg['device']=='A24':return self.cfg['baseline_w']
        return self.cfg['baseline_w']+self.cfg['initial_power_tail_w']*math.exp(-t/30)
    def advance(self,to):
        dt=to-self.now
        if dt<0:raise ValueError('monotonic current-state cost')
        key=self.key();index=STATES[self.cfg['device']].index(key)if key!='idle'else None
        self.original.advance(to);self.idle.advance(to)
        self.pfast,self.pslow,self.ph,ex=transition(self.pfast,self.pslow,self.ph,index,dt,self.cfg['power'])
        self.tfast,self.tslow,self.th,_=transition(self.tfast,self.tslow,self.th,index,dt,self.cfg['thermal'])
        self.energy+=self.cfg['baseline_w']*dt+float(ex@self.cfg['power']['coefficients'])
        self.energy+=self.cfg.get('initial_power_tail_w',0.)*30*(math.exp(-self.now/30)-math.exp(-to/30))
        self.now=to;return self.snapshot()
    def snapshot(self):
        v=self.original.snapshot();pc=self.cfg['power'];tc=self.cfg['thermal'];key=self.key()
        if pc['selected']:
            u=np.zeros(len(STATES[self.cfg['device']]))
            if key!='idle':u[STATES[self.cfg['device']].index(key)]=1.
            feature=np.r_[u*(1-self.ph),u*self.ph]if pc['memory']else u
            alpha=pc.get('mix',1.);old_energy=v['energy_window_j'];old_power=v['power_w']
            mixed_energy=(1-alpha)*old_energy+alpha*self.energy
            v.update(power_w=(1-alpha)*old_power+alpha*(self.baseline(self.now)+float(feature@pc['coefficients'])),energy_window_j=mixed_energy,continuous_energy_j=mixed_energy)
        if tc['selected']:
            idle=self.idle.snapshot()['temperature_c']['AP'];coef=tc['coefficients']
            value=self.initial_ap+(idle-self.initial_ap)*coef[-1]+float(np.r_[self.tfast,self.tslow]@coef[:-1])
            alpha=tc.get('mix',1.);v['temperature_c']['AP']=(1-alpha)*v['temperature_c']['AP']+alpha*value
        v.update(abi=VERSION,energy_status='internal-gauge fitted aggregate state cost; component power not identified')
        return v

class A24Device(prior.A24Device):
    def __init__(self,profile,*a,**kw):
        super().__init__(profile,*a,**kw);trend.install(self,CompactCost(self._anchor,profile))
class S26Device(prior.S26Device):
    def __init__(self,profile,*a,**kw):
        super().__init__(profile,*a,**kw);trend.install(self,CompactCost(self._anchor,profile))

def simulate(profile,requests,controller,**kw):
    for q in requests:
        prior.validate(q)
        if q.get('work_units',1)!=1:raise ValueError('unit1 only')
    scope=dict(prior.base.simulate.__globals__);scope['validate_request']=prior.validate
    scope['Device']=A24Device if profile['device']=='A24'else S26Device
    fn=types.FunctionType(prior.base.simulate.__code__,scope,'measured35_event_loop',prior.base.simulate.__defaults__)
    r=fn(profile,requests,controller,**kw);r['metrics']=prior.active_metrics(r['ledger'],r['metrics'],r['end_ns'])
    r.update(schema=VERSION,physical_evidence='seen-data empirical development; new hardware confirmation0',PPO_role='fixed prior transfer; no training',deadline_contract='arrival + declared deadline')
    return r
