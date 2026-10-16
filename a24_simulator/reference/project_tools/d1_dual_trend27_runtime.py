"""Device-specific, current-event thermal response; fixed power/service priors."""
import copy,math
import numpy as np
from tools import d1_sched_dynamics_plant as base
from tools import d1_s26_refine26_plant as source_s26
from tools import d1_s26_refine26_runtime as risk
from tools import d1_s26_observer_separate_heat as preserved
from tools import d1_s26_pair_observer_model as initial_math

STATES=('classification_CPU','detection_CPU','classification_GPU','classification_GPU+detection_CPU')
ABI='dual-device-current-event-trend-v27'

def initialize_a24(pre,beta,alpha=.5):
    if len(pre)<8 or any(not r['lo']<=r['t']<=r['hi']<=0 for r in pre):raise ValueError('completed past A24 temperature only')
    ts=np.asarray([r['t']for r in pre]);ys=np.asarray([r['ap']for r in pre]);dt=ts-ts[0];eb=np.exp(-beta*dt)
    if not np.isfinite(ts).all()or not np.isfinite(ys).all()or(np.diff(ts)<=0).any()or ts[-1]-ts[0]<20:raise ValueError('A24 past coverage')
    conv=np.array([convolution(beta,30,t)for t in dt]);x=np.column_stack((1-eb,conv));norm=np.linalg.norm(x,axis=0)
    if min(norm)<=0:raise ValueError('unidentified past initial state')
    aug=np.vstack((x/norm,[0,math.sqrt((1-alpha)/alpha)]));coef=np.linalg.lstsq(aug,np.r_[ys-ys[0]*eb,0],rcond=None)[0]/norm
    return dict(reference_c=float(coef[0]),h_last=float(coef[1]*math.exp(-(ts[-1]-ts[0])/30)),anchor_s=float(ts[-1]),initial_c=float(ys[-1]),input_end_s=pre[-1]['hi'])

def convolution(beta,tau,t):
    delta=beta-1/tau
    return t*math.exp(-beta*t)if abs(delta)<1e-10 else(math.exp(-t/tau)-math.exp(-beta*t))/delta

class A24Cost:
    def __init__(self,cost,model,public):
        self.cost=copy.deepcopy(cost);self.model=copy.deepcopy(model);self.public=copy.deepcopy(public);self.beta=public['beta'];self.tau=public['slow_tau_s']
        self.initial=initialize_a24(public['pre'],self.beta);self.now=0.;self.energy=0.;self.owners={};self.fast=np.zeros(4);self.slow=0.;self.coefficients=np.asarray(model['coefficients'])
        if self.coefficients.shape!=(6,)or not np.isfinite(self.coefficients).all()or(self.coefficients<0).any()or public['pre_w']<=0:raise ValueError('A24 trend coefficient/baseline')
    def key(self):
        return '+'.join(sorted(task+'_'+b for rid,task,b in self.owners.values()))if self.owners else'resident_idle'
    def dispatch(self,rid,task,b):
        if b in self.owners or(task,b)not in {('classification','CPU'),('classification','GPU'),('detection','CPU')}:raise ValueError('unsupported A24 owner')
        labels={(task,b)}|{(q[1],lane)for lane,q in self.owners.items()}
        if len(labels)>2 or len(labels)==2 and labels!={('classification','GPU'),('detection','CPU')}:raise ValueError('unsupported A24 pair')
        self.owners[b]=(rid,task,b)
    def available(self,rid,b):
        if b not in self.owners or self.owners[b][0]!=rid:raise ValueError('A24 AVAILABLE identity')
        del self.owners[b]
    def temperature(self):
        p=self.initial;t=self.now-p['anchor_s'];initial=(p['reference_c']-p['initial_c'])*(-math.expm1(-self.beta*t))+p['h_last']*convolution(self.beta,30,t)
        return float(p['initial_c']+self.coefficients[5]*initial+self.fast@self.coefficients[:4]+self.slow*self.coefficients[4])
    def snapshot(self):
        key=self.key();inc=0. if key=='resident_idle'else self.cost['energy_increment_w'][key]
        return dict(time_s=self.now,power_w=self.public['pre_w']+inc,energy_window_j=self.energy,
            temperature_c={'AP':self.temperature(),'SKIN':self.public['skin_placeholder_c']},SKIN_status='unmodeled placeholder')
    def advance(self,to):
        dt=to-self.now
        if dt<0 or not math.isfinite(to):raise ValueError('A24 monotonic clock')
        key=self.key();u=np.zeros(4);power=0.
        if key!='resident_idle':u[STATES.index(key)]=1.;power=self.cost['energy_increment_w'][key]
        self.fast=self.fast*math.exp(-self.beta*dt)+u*(-math.expm1(-self.beta*dt))/self.beta
        self.slow=self.slow*math.exp(-dt/self.tau)+power*self.tau*(-math.expm1(-dt/self.tau));self.energy+=(self.public['pre_w']+power)*dt;self.now=to
        return self.snapshot()

class CalibratedRiskCost(risk.CostState):
    def __init__(self,parent,public,thermal):
        converted=copy.deepcopy(parent);scales={}
        for sensor,new in thermal.items():
            if new['coefficients_family']in ('PRESERVED23_THERMAL','RISK26_WORK_PRESERVED23_INITIAL'):continue
            c=new['coefficients']
            if len(c)==3 and new['coefficients_family']=='S26_M6_SCALAR':
                converted['thermal'][sensor]['coefficients'][:7]=[v*c[0]for v in converted['thermal'][sensor]['coefficients'][:7]];scales[sensor]=c[1:]
            elif len(c)==9:
                converted['thermal'][sensor]['coefficients'][:7]=c[:7];scales[sensor]=c[7:]
            else:raise ValueError('selected M6 scalar3 or phase9 schema')
        super().__init__(converted,public)
        for sensor,g in scales.items():self.amplitudes[sensor]=[a*b for a,b in zip(self.amplitudes[sensor],g)]

class S26Cost:
    def __init__(self,parent,public,thermal,old_cost,old_initial):
        self.risk=CalibratedRiskCost(parent,public,thermal);self.thermal=copy.deepcopy(thermal);self.old_initial=copy.deepcopy(old_initial)
        self.old=preserved.CostState(copy.deepcopy(old_cost),copy.deepcopy(old_initial))if any(c['coefficients_family']=='PRESERVED23_THERMAL'for c in thermal.values())else None
    @property
    def now(self):return self.risk.now
    @property
    def owners(self):return self.risk.owners
    def dispatch(self,*args):
        self.risk.dispatch(*args)
        if self.old:self.old.dispatch(*args)
    def available(self,*args):
        self.risk.available(*args)
        if self.old:self.old.available(*args)
    def set_activity(self,values):self.risk.set_activity(values)
    def advance(self,to):
        self.risk.advance(to)
        if self.old:self.old.advance(to)
        return self.snapshot()
    def snapshot(self):
        value=self.risk.snapshot()
        for sensor,c in self.thermal.items():
            if c['coefficients_family']=='PRESERVED23_THERMAL':value['temperature_c'][sensor]=self.old.temperature(sensor)
            elif c['coefficients_family']=='RISK26_WORK_PRESERVED23_INITIAL':
                tm=self.risk.model['thermal'][sensor];a,z=self.risk.amplitudes[sensor];elapsed=self.now
                previous_initial=self.risk.public['initial_c'][sensor]+a*(-math.expm1(-tm['initial_fast']*elapsed))+z*(-math.expm1(-tm['initial_slow']*elapsed))
                restored,_,_,_=initial_math.initial_terms(c['initial_thermal'],self.old_initial,sensor,[elapsed])
                value['temperature_c'][sensor]=float(value['temperature_c'][sensor]-previous_initial+restored[0])
        value['abi']=ABI;return value

def install(dev,anchor):
    dev._anchor=anchor;temp=anchor.snapshot()['temperature_c'];dev._peak_ap=temp['AP'];dev._observed=None;dev._history.clear()
    dev.initial.update(ap_c=temp['AP'],skin_c=temp['SKIN'],baseline_w=anchor.snapshot()['power_w'])
    dev._record(force=True)

class A24Device(base.Device):
    def __init__(self,profile,*a,**kw):
        super().__init__(profile,*a,**kw);cfg=profile['trend27_anchor'];install(self,A24Cost(profile['cost_anchor'],cfg['thermal']['AP'],cfg['public_boundary']))

class S26Device(source_s26.Device):
    def __init__(self,profile,*a,**kw):
        super().__init__(profile,*a,**kw);cfg=profile['trend27_anchor'];parent=profile['refine26_anchor'];install(self,S26Cost(parent['model'],parent['public_boundary'],cfg['thermal'],cfg['preserved23_cost'],cfg['preserved23_initial']))

def simulate(profile,requests,controller,split='confirm',environment_seed=0,npu=True,deterministic=False):
    import types
    # Private function globals retain frozen event loop, with no shared mutation.
    scope=dict(base.simulate.__globals__);scope['Device']=A24Device if profile['device']=='A24'else S26Device
    fn=types.FunctionType(base.simulate.__code__,scope,'trend27_event_loop',base.simulate.__defaults__)
    result=fn(profile,requests,controller,split,environment_seed,npu,deterministic)
    result.update(schema=ABI,trend_model_status='known-data development; fixed prior conditional validation',new_independent_confirmation=False)
    result['metrics'].update(trend_calibrated=True,power_coefficients_frozen=True,hardware_validated=False,strict_eligible=False,experiment_ready=False)
    return result
