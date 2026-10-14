"""Causal phase power/initial HAL heat, new26 only; no policy-specific physics."""
import bisect,copy,math
import numpy as np
from tools import d1_s26_refine26_model as m

ABI='s26-phase-observer-initialheat-runtime-v26'
ROUTES=(('classification','CPU'),('detection','CPU'),('classification','GPU'),('classification','NPU'))

def validate(model,public):
    if model.get('schema')!=m.VERSION or tuple(model['power_fields'])!=m.POWER_FIELDS or model['strict_eligible']is not False or model['experiment_ready']is not False:
        raise ValueError('explicit26 development ABI')
    p=model['power'];c=np.asarray(p['coefficients'],float)
    if c.shape!=(11,)or not np.isfinite(c).all()or(c<0).any():raise ValueError('power coefficients')
    if p['cache_s']!=0 or p['lag_s']not in (0,.18) or p['window_s']!=.36 or p['tail_s']not in (0,3) or p['alpha']!=4:
        raise ValueError('this runtime implements selected26 and risk26 settings only')
    for sensor,tm in model['thermal'].items():
        v=m.history_vector(public,sensor,tm['extended']);tc=np.asarray(tm['coefficients'],float)
        if tc.shape!=(7+2*len(v),)or not np.isfinite(tc).all()or tm['delay_s']!=0:raise ValueError('selected thermal settings')
        if not np.isfinite(v).all():raise ValueError('past boundary finite')
    vals=[public[k]for k in ('median5_w','median10_w','mean30_w','battery_c','past_cpu_duty600','past_accelerator_duty600','resident_count')]
    if not all(math.isfinite(v)for v in vals)or min(vals[:3])<0:raise ValueError('past power boundary')
    if any(not math.isfinite(public['initial_c'][k])or not 0<=public['thermal_age_s'][k]<=5 for k in ('AP','SKIN')):raise ValueError('fresh initial thermal')

def public_from_past(power,thermal,resident_count,work_history=(),*,battery_samples):
    """Reject unfinished/future reads and history; no later idle reference."""
    p=np.asarray(power,float)
    if p.ndim!=2 or p.shape[1]!=3 or len(p)<15 or not np.isfinite(p).all()or(p[:,1]>0).any()or(p[:,0]>p[:,1]).any()or(p[:,2]<0).any():raise ValueError('completed past power only')
    p=p[p[:,0]>=-30]
    if len(p)<15 or max(p[:,0])< -2.5:raise ValueError('past power coverage')
    med={w:float(np.median(p[p[:,0]>=-w,2]))for w in (5,10)}
    if not all(np.isfinite(list(med.values()))):raise ValueError('past recent power')
    initial={};slopes={};ranges={};age={}
    for sensor in ('AP','SKIN','BAT'):
        rows=np.asarray(thermal[sensor],float)
        if rows.ndim!=2 or rows.shape[1]!=2 or len(rows)<3 or not np.isfinite(rows).all()or(rows[:,0]>0).any():raise ValueError('completed past thermal only')
        rows=rows[np.argsort(rows[:,0])];initial[sensor]=float(rows[-1,1]);age[sensor]=float(-rows[-1,0]);recent=rows[rows[:,0]>=-20]
        if len(recent)<3 or age[sensor]>5:raise ValueError('stale thermal history')
        x=recent[:,0]-recent[:,0].mean();y=recent[:,1]-recent[:,1].mean();slopes[sensor]=float(x@y/(x@x))if x@x else 0.
        ranges[sensor]=float(np.ptp(rows[rows[:,0]>=-30,1]))
    cpu=accelerator=0.
    for a,z,field in work_history:
        if not math.isfinite(a)or not math.isfinite(z)or z>0 or a>=z or field not in range(6):raise ValueError('completed past work only')
        if z< -1800:continue
        weight=math.exp(z/600)-math.exp(a/600)
        if field in (0,1,4):cpu+=weight
        elif field in (2,3):accelerator+=weight
    # Match preparation: BatterySampler deci-C converted to C, with completed
    # read time. HAL BAT is retained in initial_c, never substituted here.
    battery=np.asarray(battery_samples,float)
    if battery.ndim!=2 or battery.shape[1]!=2 or len(battery)<1 or not np.isfinite(battery).all()or(battery[:,0]>0).any():raise ValueError('completed BatterySampler temperatures required')
    battery=battery[np.argsort(battery[:,0])]
    if battery[-1,0]< -2.5:raise ValueError('stale BatterySampler temperature')
    return dict(median5_w=med[5],median10_w=med[10],mean30_w=float(p[:,2].mean()),initial_c=initial,
        slopes20=slopes,ranges30=ranges,thermal_age_s=age,battery_c=float(battery[-1,1]),resident_count=resident_count,
        past_cpu_duty600=min(cpu,2.),past_accelerator_duty600=min(accelerator,1.))

class CostState:
    """Integrates current phases only; owners are retained until AVAILABLE."""
    def __init__(self,model,public):
        validate(model,public);self.model=copy.deepcopy(model);self.public=copy.deepcopy(public)
        self.now=0.;self.energy=0.;self.q=0.;self.tail=0.;self.owners={};self.activity=np.zeros(6)
        self.heat={s:np.zeros(7)for s in ('AP','SKIN')};self.amplitudes={}
        self.times=[0.];self.areas=[0.];self.powers=[];self.last_power=self.baseline
        for sensor,tm in self.model['thermal'].items():
            v=m.history_vector(public,sensor,tm['extended']);c=np.asarray(tm['coefficients']);k=len(v)
            self.amplitudes[sensor]=[float(np.clip(v@c[7:7+k],-8,8)),float(np.clip(v@c[7+k:7+2*k],-8,8))]
    @property
    def baseline(self):return float(np.asarray(self.model['power']['coefficients'][:3])@np.asarray([self.public['median5_w'],self.public['median10_w'],self.public['mean30_w']]))
    def dispatch(self,rid,task,b):
        if(task,b)not in ROUTES or b in self.owners or rid in [r[0]for r in self.owners.values()]:raise ValueError('unsupported or duplicate owner')
        labels={(task,b)}|{(r[1],lane)for lane,r in self.owners.items()}
        if len(labels)>2 or len(labels)==2 and labels not in ({('classification','GPU'),('detection','CPU')},{('classification','NPU'),('detection','CPU')}):raise ValueError('unsupported concurrency')
        self.owners[b]=(rid,task)
    def available(self,rid,b):
        if b not in self.owners or self.owners[b][0]!=rid:raise ValueError('AVAILABLE owner mismatch')
        del self.owners[b]
    def set_activity(self,values):
        v=np.asarray(values,float)
        if v.shape!=(6,)or not np.isfinite(v).all()or(v<0).any()or(v>2).any():raise ValueError('phase activity')
        for i,(task,b)in enumerate(ROUTES):
            if v[i]and(b not in self.owners or self.owners[b][1]!=task):raise ValueError('unowned call')
        if v.sum()>len(self.owners)+1e-9:raise ValueError('duplicate phases')
        self.activity=v.copy()
    def advance(self,to):
        if not math.isfinite(to)or to<self.now-1e-10:raise ValueError('cost monotonic clock')
        while self.now<to-1e-12:
            end=min(to,(math.floor(self.now/m.DT+1e-8)+1)*m.DT);dt=end-self.now
            u=self.activity.copy();cpu=min(u[0]+u[1]+u[4],1.)
            recent=cpu+(self.q-cpu)*math.exp(-dt/10)
            phi=np.zeros(11);phi[:3]=[self.public['median5_w'],self.public['median10_w'],self.public['mean30_w']]
            phi[3]=max(self.public['mean30_w']-self.public['median10_w'],0)*math.exp(-(self.now+dt/2)/30)
            phi[4:10]=u;phi[4:6]/=1+4*recent
            tau=self.model['power']['tail_s']
            phi[10]=1. if self.owners else self.tail*tau*(-math.expm1(-dt/tau))/dt if tau else 0.
            components=phi[4:]*np.asarray(self.model['power']['coefficients'][4:]);power=float(phi@self.model['power']['coefficients'])
            self.energy+=power*dt;self.last_power=power
            for sensor,tm in self.model['thermal'].items():
                decay=math.exp(-tm['beta']*dt);self.heat[sensor]=self.heat[sensor]*decay+components*(1-decay)
            self.q=cpu+(self.q-cpu)*math.exp(-dt/5);self.tail=1. if self.owners else self.tail*math.exp(-dt/tau)if tau else 0.
            self.now=end;self.times.append(end);self.areas.append(self.energy);self.powers.append(power)
        return self.snapshot()
    def integral(self,t):
        if t<0:return t*self.baseline
        if t>self.now+1e-8:raise ValueError('no future gauge query')
        i=min(bisect.bisect_right(self.times,t)-1,len(self.powers)-1)
        if i<0:return 0.
        return self.areas[i]+(t-self.times[i])*self.powers[i]
    def temperature(self,sensor):
        tm=self.model['thermal'][sensor];a,z=self.amplitudes[sensor]
        return float(self.public['initial_c'][sensor]+self.heat[sensor]@np.asarray(tm['coefficients'][:7])+a*(-math.expm1(-tm['initial_fast']*self.now))+z*(-math.expm1(-tm['initial_slow']*self.now)))
    def snapshot(self):
        query=self.now-self.model['power']['lag_s']
        gauge=(self.integral(query)-self.integral(query-.36))/.36
        return dict(time_s=self.now,energy_window_j=self.energy,continuous_energy_j=self.energy,
            power_w=gauge,continuous_power_w=self.last_power,temperature_c={s:self.temperature(s)for s in self.heat},
            energy_status='unidentified continuous-power hypothesis; reported gauge prediction kept separate',
            initial_amplitudes_c=copy.deepcopy(self.amplitudes),abi=ABI)
