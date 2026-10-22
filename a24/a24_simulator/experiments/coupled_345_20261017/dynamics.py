"""Explicit research hypotheses: shared activation, thermal RC and DVFS.

Every real/nominal transition and reward uses this module. Parameters describe
a stress scenario, not identified A24 junction temperatures or calibrated W/J.
"""
from dataclasses import dataclass, asdict
import math

NS=1_000_000_000
ROUTES=('CPU','GPU')


@dataclass(frozen=True)
class Config:
    baseline:float=1.204399931712509
    idle_c:float=26.
    reference_c:float=26.
    thermal_tau_s:float=25.
    thermal_resistance:float=12.
    idle_tail_s:float=.9
    onset_c:float=32.
    cpu_slope:float=.07
    gpu_slope:float=.045
    minimum_speed:float=.45
    leakage_fraction:float=.20
    leakage_per_c:float=.025
    strength:float=1.
    tick_s:float=.1


def validate(c):
    if any(not math.isfinite(v) for v in asdict(c).values()):raise ValueError('Nonfinite configuration')
    if not (c.baseline>0 and c.thermal_tau_s>0 and c.thermal_resistance>=0 and c.idle_tail_s>=0 and
            0<c.minimum_speed<=1 and 0<=c.leakage_fraction<=1 and c.strength>=0 and c.tick_s>0):
        raise ValueError('Invalid coupled configuration')


def label(task,route):return ('classification' if task=='C' else 'detection')+'_'+route


class Physics:
    def __init__(self,model,config=Config()):
        validate(config);self.c=config
        self.solo=dict(zip(model['supported_states'],model['coefficients_W_proxy']))
        pair=self.solo.pop('classification_GPU+detection_CPU')
        self.solo['detection_GPU']=.6013808404579677
        self.shared=self.solo['classification_GPU']+self.solo['detection_CPU']-pair
        if not 0<=self.shared<=min(self.solo.values()):raise ValueError('Nonnegative shared/dynamic components required')

    def speed(self,temperature,route,stage):
        if route not in ROUTES or stage not in range(5):raise ValueError('Unsupported resource/phase')
        if stage!=1:return 1.  # Only execution work is frequency sensitive.
        slope=self.c.cpu_slope if route=='CPU' else self.c.gpu_slope
        return max(self.c.minimum_speed,1/(1+self.c.strength*slope*max(0.,temperature-self.c.onset_c)))

    def transition(self,state,active,dt):
        if not math.isfinite(dt) or dt<0:raise ValueError('Invalid duration')
        if len(active)>2 or len({r['route'] for r in active})!=len(active):raise ValueError('One CPU and one GPU only')
        if any(r['task'] not in ('C','D') or r['route'] not in ROUTES or r['stage'] not in range(5) for r in active):
            raise ValueError('Invalid active job')
        T,z=state['temperature_c'],state['shared_z']
        if not math.isfinite(T+z) or not 0<=z<=1:raise ValueError('Invalid current state')
        c=self.c;dynamic=0.;speeds={}
        leak=math.exp(min(math.log(3.),max(-math.log(3.),c.strength*c.leakage_per_c*(T-c.reference_c))))
        for r in active:
            f=self.speed(T,r['route'],r['stage']);speeds[r['route']]=f
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
        if min(inc,T1-c.idle_c)<-1e-8:raise ValueError('Nonphysical energy/thermal state')
        return dict(temperature_c=T1,shared_z=z1),dict(increment=inc,baseline=c.baseline*dt,
            dynamic=dynamic*dt,shared=shared_energy,temperature_area=area,
            peak=max(T,T1),speeds=speeds,dt=dt)


def advance_jobs(physics,state,jobs,dt):
    """Common progress/energy/thermal operator, frozen at the left step state."""
    active=[dict(task=j['task'],route=j['route'],stage=j['stage']) for j in jobs]
    nextstate,terms=physics.transition(state,active,dt)
    for j in jobs:
        j['remaining']=max(0.,j['remaining']-dt*terms['speeds'][j['route']])
    return nextstate,terms


WEIGHTS=(.5,.5,8.,4.,30.)
FEATURE_SCALE_ENERGY=.35


def deadline_cost(rows,normalizer=None):
    costs=[]
    for priority in ('U','N'):
        role=[r for r in rows if r['priority']==priority]
        loss=0.
        for r in role:
            response=r.get('response_s')
            if response is None:continue
            late=max(0.,response-r['deadline_s'])
            loss+=float(late>1e-9)+.2*min(5.,late/max(.05,r['deadline_s']-r['arrival_s']))
        costs.append(loss/max(1,len(rows) if normalizer is None else normalizer))
    return costs


def objectives(increment,heat_area,peak,rows,n):
    return [increment/(n*FEATURE_SCALE_ENERGY),heat_area/(n*3.)+.1*max(0.,peak-32.)/5.,
            *deadline_cost(rows,n),sum(r.get('response_s') is None for r in rows)/n]


def weighted(costs):return sum(a*b for a,b in zip(costs,WEIGHTS))
