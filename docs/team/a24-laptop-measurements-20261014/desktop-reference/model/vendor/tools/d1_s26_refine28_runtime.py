"""Energy-only development correction with independently preserved27 heat."""
import copy,types
from tools import d1_dual_trend27_runtime as prior
from tools import d1_s26_refine26_runtime as power
class SplitCost:
    def __init__(self,thermal,energy):self.thermal=thermal;self.energy=energy
    @property
    def now(self):return self.thermal.now
    @property
    def owners(self):return self.thermal.owners
    def dispatch(self,*a):self.thermal.dispatch(*a);self.energy.dispatch(*a)
    def available(self,*a):self.thermal.available(*a);self.energy.available(*a)
    def set_activity(self,*a):self.thermal.set_activity(*a);self.energy.set_activity(*a)
    def advance(self,t):self.thermal.advance(t);self.energy.advance(t);return self.snapshot()
    def snapshot(self):
        v=self.energy.snapshot();v['temperature_c']=self.thermal.snapshot()['temperature_c'];v['abi']='s26-energy28-thermal27';return v
class Device(prior.S26Device):
    def __init__(self,profile,*a,**kw):
        super().__init__(profile,*a,**kw);p=profile['refine26_anchor'];model=copy.deepcopy(p['model']);model['power']['coefficients']=profile['refine28_power']['coefficients'];prior.install(self,SplitCost(self._anchor,power.CostState(model,p['public_boundary'])))
def simulate(profile,requests,controller,split='confirm',environment_seed=0,npu=True,deterministic=False):
    scope=dict(prior.base.simulate.__globals__);scope['Device']=Device if profile['device']=='S26'else prior.A24Device
    fn=types.FunctionType(prior.base.simulate.__code__,scope,'refine28',prior.base.simulate.__defaults__)
    result=fn(profile,requests,controller,split,environment_seed,npu,deterministic)
    result.update(schema='energy28-thermal27',new_independent_confirmation=False)
    result['metrics'].update(hardware_validated=False,strict_eligible=False,experiment_ready=False,power_profile='M6 development shrinkage28',thermal_profile='unchanged27')
    return result
