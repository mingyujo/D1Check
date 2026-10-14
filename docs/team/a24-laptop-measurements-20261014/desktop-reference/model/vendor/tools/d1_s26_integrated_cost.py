"""S26 current-activity cost state, exact energy/temperature integrals."""
import itertools
import math
import numpy as np
from tools.d1_s26_cost_model import checked_busy, resource_intervals, filtered_step

ABI='s26-activity-cost-v2'
TAUS=(0,.1,.5,2,5)
BETAS=(.01,.03,.06,.12,.25)


def validate(profile):
    if profile.get('abi')!=ABI or profile.get('strict_eligible') is not False or profile.get('experiment_ready') is not False:
        raise ValueError('exploratory cost ABI/eligibility mismatch')
    if profile['power']['tau_s'] not in TAUS:raise ValueError('activity memory tau')
    for name,model,bound in [('power',profile['power'],10),*[ (k,profile['thermal'][k],60) for k in ('AP','SKIN') ]]:
        key='coeff_w' if name=='power' else 'gains_c'
        v=np.asarray(model[key])
        if v.shape!=(4,) or v.dtype.kind not in 'fi' or not np.isfinite(v).all() or (v<0).any() or (v>bound).any():raise ValueError('4-coefficient ABI/range')
        if name!='power' and (model['beta_per_s'] not in BETAS or model['mix'] not in (1,.6)):raise ValueError('thermal kernel')
    return profile


def thermal_step(y,u,h0,dt,tau,beta):
    """4 feature filters and their exact integrals. h is reset-on-busy memory."""
    z,area=filtered_step(y[:3],u,dt,1/beta)
    busy=bool(np.any(u));eb=math.exp(-beta*dt)
    if busy:
        hz=1.;harea=dt
        fourth=1+(y[3]-1)*eb
    elif tau==0:
        hz=0.;harea=0.;fourth=y[3]*eb
    else:
        alpha=1/tau;ea=math.exp(-alpha*dt);hz=h0*ea;harea=h0*tau*(1-ea)
        term=dt*eb if abs(beta-alpha)<1e-10 else (ea-eb)/(beta-alpha)
        fourth=y[3]*eb+beta*h0*term
    # Integral identity dy/dt=beta(input-y) avoids subtracting close exponentials.
    fourth_area=harea-(fourth-y[3])/beta
    return np.r_[z,fourth],np.r_[area,fourth_area],hz,harea


class Basis:
    def __init__(self,tau,beta=.06,mix=1):
        self.tau=tau;self.beta=beta;self.mix=mix;self.h=0.;self.now=0.
        self.fast=np.zeros(4);self.slow=np.zeros(4);self.area=np.zeros(4);self.heat_area=np.zeros(4)

    def advance(self,to,u):
        if to<self.now or not math.isfinite(to):raise ValueError('basis clock')
        dt=to-self.now;busy=bool(np.any(u));h0=1. if busy else self.h
        f,fa,h,harea=thermal_step(self.fast,u,h0,dt,self.tau,self.beta)
        slow,sa,_,_=thermal_step(self.slow,u,h0,dt,self.tau,self.beta/10)
        self.fast=f;self.slow=slow;self.h=h
        self.area+=np.r_[u*dt,harea];self.heat_area+=self.mix*fa+(1-self.mix)*sa;self.now=to
        return self.mix*f+(1-self.mix)*slow


def features(intervals,times,tau,beta=.06,mix=1):
    ts=np.asarray(times,float)
    if ts.ndim!=1 or not np.isfinite(ts).all() or (ts<0).any():raise ValueError('feature times')
    events=[]
    for a,b,u in intervals:
        if a<0:raise ValueError('unknown past busy initialization')
        events.extend(((a,1,np.array(u,float)),(b,0,np.zeros(3))))
    events.sort(key=lambda x:(x[0],x[1]));basis=Basis(tau,beta,mix);u=np.zeros(3);j=0
    values=np.zeros((len(ts),4));areas=values.copy();heat_areas=values.copy()
    for i in np.argsort(ts,kind='stable'):
        target=ts[i]
        while j<len(events) and events[j][0]<=target:
            at,_,next_u=events[j];basis.advance(at,u);u=next_u;j+=1
        values[i]=basis.advance(target,u);areas[i]=basis.area;heat_areas[i]=basis.heat_area
    return values,areas,heat_areas


def box_fit(x,y,ridge,bound):
    """Exact convex solution over 81 active faces; four coefficients, no SciPy."""
    x=np.asarray(x,float);y=np.asarray(y,float)
    if x.shape!=(len(y),4) or not len(y) or not np.isfinite(x).all() or not np.isfinite(y).all():raise ValueError('fit inputs')
    a=np.vstack((x,np.eye(4)*math.sqrt(ridge/4)/bound));b=np.r_[y,np.zeros(4)]
    best=None
    for faces in itertools.product((-1,0,1),repeat=4):
        free=[i for i,f in enumerate(faces) if not f];v=np.array([bound if f==1 else 0. for f in faces])
        if free:v[free]=np.linalg.lstsq(a[:,free],b-a@v,rcond=None)[0]
        if (v< -1e-8).any() or (v>bound+1e-8).any():continue
        v=np.clip(v,0,bound);loss=float(np.sum((a@v-b)**2))
        if best is None or loss<best[0]:best=loss,v
    return best[1]


class CostState:
    """Only current dispatch/AVAILABLE events; no duration or future release input."""
    def __init__(self,profile,baseline_w,reference_c,initial_c):
        self.profile=validate(profile)
        if not math.isfinite(baseline_w) or baseline_w<0 or any(not math.isfinite(d[k]) for d in (reference_c,initial_c) for k in ('AP','SKIN')):raise ValueError('cost initialization')
        self.baseline=baseline_w;self.reference=dict(reference_c);self.initial=dict(initial_c);self.owners={};self.now=0.
        self.basis={k:Basis(profile['power']['tau_s'],v['beta_per_s'],v['mix']) for k,v in profile['thermal'].items()}
        self.energy=0.;self.temperature_area={k:0. for k in ('AP','SKIN')};self.area_at35=None
        self.peaks=dict(initial_c);self.peaks_after35={k:None for k in ('AP','SKIN')};self.grid=[]
        self._record()

    def temperature(self,k):
        h=self.profile['thermal'][k];b=self.basis[k]
        return self.reference[k]+(self.initial[k]-self.reference[k])*math.exp(-h['beta_per_s']*self.now)+float((h['mix']*b.fast+(1-h['mix'])*b.slow)@h['gains_c'])

    def _record(self):
        for k in self.peaks:
            t=self.temperature(k);self.peaks[k]=max(self.peaks[k],t)
            if self.now>=35:self.peaks_after35[k]=t if self.peaks_after35[k] is None else max(self.peaks_after35[k],t)
        if abs(self.now-round(self.now))<1e-9:
            row=dict(time_s=self.now,AP_c=self.temperature('AP'),SKIN_c=self.temperature('SKIN'),energy_j=self.energy)
            if self.grid and self.grid[-1]['time_s']==self.now:self.grid[-1]=row
            else:self.grid.append(row)

    def advance(self,to):
        if not math.isfinite(to) or to<self.now:raise ValueError('cost clock')
        u=checked_busy({b:v[1] for b,v in self.owners.items()});g=np.asarray(self.profile['power']['coeff_w'])
        while self.now<to:
            nxt=min(to,self.now+.25,math.floor(self.now+1e-9)+1)
            if self.now<35<nxt:nxt=35.
            old=self.now;before=self.basis['AP'].area.copy()
            for k,basis in self.basis.items():basis.advance(nxt,u)
            self.energy+=self.baseline*(nxt-old)+float((self.basis['AP'].area-before)@g)
            self.now=nxt
            for k,basis in self.basis.items():
                h=self.profile['thermal'][k];beta=h['beta_per_s']
                residual=(self.initial[k]-self.reference[k])*(1-math.exp(-beta*nxt))/beta
                self.temperature_area[k]=self.reference[k]*nxt+residual+float(basis.heat_area@h['gains_c'])
            if self.now==35:self.area_at35=dict(self.temperature_area)
            self._record()
        return self.snapshot()

    def dispatch(self,rid,task,backend):
        if backend in self.owners or any(v[0]==rid for v in self.owners.values()):raise ValueError('duplicate/occupied owner')
        proposed={b:v[1] for b,v in self.owners.items()};proposed[backend]=task;checked_busy(proposed)
        self.owners[backend]=(rid,task)
        for basis in self.basis.values():basis.h=1.

    def available(self,rid,backend):
        if backend not in self.owners or self.owners[backend][0]!=rid:raise ValueError('AVAILABLE owner mismatch')
        del self.owners[backend]
        if not self.owners and self.profile['power']['tau_s']==0:
            for b in self.basis.values():b.h=0.

    def snapshot(self):
        u=checked_busy({b:v[1] for b,v in self.owners.items()});memory=1. if np.any(u) else self.basis['AP'].h
        return dict(time_s=self.now,energy_window_j=self.energy,power_w=self.baseline+float(np.r_[u,memory]@self.profile['power']['coeff_w']),
            temperature_c={k:self.temperature(k) for k in self.peaks},peak_c=dict(self.peaks),peak_after35_c=dict(self.peaks_after35),
            mean_c={k:self.temperature_area[k]/self.now if self.now else self.initial[k] for k in self.peaks},
            mean_after35_c={k:(self.temperature_area[k]-self.area_at35[k])/(self.now-35) if self.area_at35 is not None and self.now>35 else None for k in self.peaks},
            strict_eligible=False,experiment_ready=False,status='exploratory_cost_model')


def predict(intervals,profile,baseline,reference,initial,end=120,observations=None):
    """Saved observations only. Separate from current-event policy interface."""
    validate(profile);tau=profile['power']['tau_s'];_,area,_=features(intervals,[end],tau)
    result=dict(energy_j=baseline*end+float(area[0]@profile['power']['coeff_w']))
    for k,h in profile['thermal'].items():
        ts=np.arange(0,end+.000001,.25) if observations is None else np.asarray(observations[k],float)
        values,_,heat_area=features(intervals,ts,tau,h['beta_per_s'],h['mix'])
        path=reference[k]+(initial[k]-reference[k])*np.exp(-h['beta_per_s']*ts)+values@h['gains_c']
        integ=reference[k]*ts+(initial[k]-reference[k])*(1-np.exp(-h['beta_per_s']*ts))/h['beta_per_s']+heat_area@h['gains_c']
        result[k]=dict(times=ts,temperatures=path,integral=integ,peak=float(path.max()))
    return result
