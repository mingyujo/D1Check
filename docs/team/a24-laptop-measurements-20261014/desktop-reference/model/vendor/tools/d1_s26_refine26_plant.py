"""New26 cost/phase adapter; existing17 service, mask and event loop unchanged."""
import copy,math
import numpy as np
from tools import d1_sched_dynamics_plant as base
from tools import d1_s26_refine26_runtime as runtime

ABI='s26-refine26-event-adapter-v1'
HORIZON_NS=base.HORIZON_NS

class Device(base.Device):
    def __init__(self,profile,*args,**kwargs):
        if profile['device']!='S26' or 'refine26_anchor'not in profile:raise ValueError('explicit S26 refine26 profile')
        # The neutral profile forbids introducing unmeasured dynamics during
        # calibration transfer. The frozen23 anchor is initialization scaffolding.
        for key in ('thermal_slowdown_per_c','recent_slowdown','parallel_extra_slowdown','startup_s','startup_j','idle_tail_w'):
            if any(profile[key].values()):raise ValueError('neutral service required')
        if any(profile[key]for key in ('parallel_extra_w','switch_s','switch_j')):raise ValueError('neutral event transfer required')
        self.gauge_observations=[]
        super().__init__(profile,*args,**kwargs)
        public=copy.deepcopy(profile['refine26_anchor']['public_boundary'])
        if kwargs.get('initial'):
            public['initial_c'].update(AP=self.initial['ap_c'],SKIN=self.initial['skin_c'])
            public.update(median5_w=self.initial['baseline_w'],median10_w=self.initial['baseline_w'],mean30_w=self.initial['baseline_w'])
        self._anchor=runtime.CostState(profile['refine26_anchor']['model'],public)
        self.initial.update(ap_c=public['initial_c']['AP'],skin_c=public['initial_c']['SKIN'],baseline_w=self._anchor.baseline)
        self._observed=None;self._history.clear();self.gauge_observations=[];self._record(force=True)
    def _integrate(self,dt_ns,rates):
        remaining=dt_ns
        while remaining:
            part=remaining
            for b,w in self._work.items():
                if w['stage']!=1:continue
                r=self.records[self._owners[b]['request']['id']];ratio=self.profile['refine26_anchor']['execution_subphase_ratios'][r['context']]
                elapsed=w['durations'][1]-w['left']
                for fraction in ratio:
                    distance=fraction*w['durations'][1]-elapsed
                    if distance>.500001:part=min(part,max(1,math.ceil(distance/rates[b]-.000001)))
            u=np.zeros(6)
            for b,w in self._work.items():
                r=self.records[self._owners[b]['request']['id']]
                if w['stage']==1:
                    fractions=self.profile['refine26_anchor']['execution_subphase_ratios'][r['context']]
                    center=(w['durations'][1]-w['left']+part*rates[b]/2)/w['durations'][1]
                    if center<fractions[0]:u[4]+=1
                    elif center<fractions[1]:u[runtime.ROUTES.index((r['task'],b))]+=1
                elif w['stage']>=2:u[5]+=1
            self._anchor.set_activity(u)
            super()._integrate(part,rates);remaining-=part
    def _record(self,force=False):
        super()._record(force)
        if isinstance(self._anchor,runtime.CostState):
            stamp=self._observed['power_observed_at_ns'];point=(stamp/1e9,self._observed['power_w'])
            if not self.gauge_observations or point[0]!=self.gauge_observations[-1][0]:self.gauge_observations.append(point)
    def current_cost(self):
        result=super().current_cost()
        if isinstance(self._anchor,runtime.CostState):
            result.update(continuous_power_w=self._anchor.snapshot()['continuous_power_w'],energy_status='continuous effective-power hypothesis',cost_abi=runtime.ABI)
        return result

def simulate(profile,requests,controller,split='confirm',environment_seed=0,npu=True,deterministic=False,initial=None,step_s=None):
    # Reuse the frozen event loop without a mutable global Device replacement.
    # A private function object gets its own global namespace.
    import types
    made=[]
    def build(*a,**kw):
        device=Device(*a,**kw);made.append(device);return device
    scope=dict(base.simulate.__globals__);scope['Device']=build
    fn=types.FunctionType(base.simulate.__code__,scope,'refine26_simulate',base.simulate.__defaults__)
    result=fn(profile,requests,controller,split,environment_seed,npu,deterministic,initial,step_s)
    observations=[point for point in made[0].gauge_observations if point[0]<=120]
    # Interpolate only between completed synthetic reads, just as in recorded
    # gauge evaluation. The cooling tail has already supplied a read past120.
    times=np.asarray([p[0]for p in made[0].gauge_observations]);values=np.asarray([p[1]for p in made[0].gauge_observations])
    reported_j=None
    if times[-1]>=120:
        inside=(times>0)&(times<120);ts=np.r_[0,times[inside],120];ps=np.r_[np.interp(0,times,values),values[inside],np.interp(120,times,values)]
        reported_j=float(np.sum(np.diff(ts)*(ps[1:]+ps[:-1])/2))
    result.update(predicted_gauge_observations=made[0].gauge_observations,predicted_reported_J0_120=reported_j,
                  gauge_window_note='0.36s past average sampled every0.9s; this is a hypothesis, not confirmed gauge calibration')
    result.update(schema=ABI,cost_abi=runtime.ABI,policy_learning=False,new_independent_confirmation=False)
    result['metrics'].update(cost_model_status='refine26_seen_development',energy_quantity='continuous effective-power hypothesis, not an independent meter result')
    return result
