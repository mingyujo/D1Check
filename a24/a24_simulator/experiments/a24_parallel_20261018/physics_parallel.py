"""Explicit A24 virtual slots; positive per-job dynamic power, shared once."""
import math
from common_transfer import B
from dynamics import label

class ParallelPhysics(B.Physics):
    def __init__(self,model,config,cpu_slots=1,beta=0.):
        super().__init__(model,config);self.cpu_slots=cpu_slots;self.beta=beta
        assert cpu_slots in (1,2,3) and beta>=0
    def rates(self,T,active):
        n=sum(r['route']=='CPU' and r['stage']==1 for r in active)
        return {r['request_id']:self.speed(T,r['route'],r['stage'])/(1+self.beta*max(0,n-1) if r['route']=='CPU' and r['stage']==1 else 1) for r in active}
    def transition(self,state,active,dt):
        assert math.isfinite(dt) and dt>=0
        assert sum(r['route']=='CPU' for r in active)<=self.cpu_slots and sum(r['route']=='GPU' for r in active)<=1
        assert len({r['request_id'] for r in active})==len(active)
        # Retain the original closed-form RC solution and per-request rates.
        T,z=state['temperature_c'],state['shared_z'];c=self.c
        assert math.isfinite(T+z) and 0<=z<=1
        speeds=self.rates(T,active);dynamic=0.
        leak=math.exp(min(math.log(3.),max(-math.log(3.),c.strength*c.leakage_per_c*(T-c.reference_c))))
        for r in active:
            # Contention slows progress but is not a voltage/frequency saving.
            # Power keeps the original thermal DVFS rate for every active job.
            f=self.speed(T,r['route'],r['stage'])
            dynamic+=(self.solo[label(r['task'],r['route'])]-self.shared)*((1-c.leakage_fraction)*f**3+c.leakage_fraction*leak)
        decay=math.exp(-dt/c.thermal_tau_s);one=-math.expm1(-dt/c.thermal_tau_s)
        shared_energy=0.;forcing_end=forcing_area=0.
        if active:
            z1=1.;shared_energy=self.shared*dt
            forcing_end=c.thermal_resistance*(dynamic+self.shared)*one
            forcing_area=c.thermal_resistance*(dynamic+self.shared)*(dt-c.thermal_tau_s*one)
        else:
            z1=z*math.exp(-dt/c.idle_tail_s) if c.idle_tail_s else 0.
            if c.idle_tail_s:
                tz=c.idle_tail_s;tt=c.thermal_tau_s;oz=-math.expm1(-dt/tz)
                shared_energy=self.shared*z*tz*oz
                if abs(tz-tt)<1e-9:
                    forcing_end=c.thermal_resistance*self.shared*z*(dt/tt)*decay
                    forcing_area=c.thermal_resistance*self.shared*z*tt*(1-(1+dt/tt)*decay)
                else:
                    factor=c.thermal_resistance*self.shared*z*tz/(tz-tt)
                    forcing_end=factor*(math.exp(-dt/tz)-decay)
                    forcing_area=factor*(tz*oz-tt*one)
        T1=c.idle_c+(T-c.idle_c)*decay+forcing_end
        area=c.idle_c*dt+(T-c.idle_c)*c.thermal_tau_s*one+forcing_area
        inc=dynamic*dt+shared_energy
        assert min(inc,T1-c.idle_c)>=-1e-8
        return dict(temperature_c=T1,shared_z=z1),dict(increment=inc,baseline=c.baseline*dt,dynamic=dynamic*dt,shared=shared_energy,temperature_area=area,peak=max(T,T1),speeds=speeds,dt=dt)

def advance_jobs(physics,state,jobs,dt):
    active=[{k:j[k] for k in ('request_id','task','route','stage')} for j in jobs]
    st,terms=physics.transition(state,active,dt)
    for j in jobs:j['remaining']=max(0.,j['remaining']-dt*terms['speeds'][j['request_id']])
    return st,terms
