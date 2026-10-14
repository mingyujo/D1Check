"""Task-aware current-event cost model; no policy or future schedule inputs."""
import itertools
import math
import numpy as np
from tools.d1_s26_cost_model import checked_busy, filtered_step

ABI='s26-task-activity-cost-v3'
TAUS=(.1,.5,2,5,15)
BETAS=(.01,.03,.06,.12,.25)


def validate(p):
    if p.get('abi')!=ABI or p.get('strict_eligible') is not False or p.get('experiment_ready') is not False:raise ValueError('refine ABI/eligibility')
    if p.get('basis') not in ('lane','task'):raise ValueError('basis')
    d=4 if p['basis']=='lane' else 5
    if p['power']['tau_s'] not in TAUS or p['power']['baseline_mode'] not in ('mean30','median10'):raise ValueError('power setting')
    for name,m,bound in [('power',p['power'],10),*[ (k,p['thermal'][k],60) for k in ('AP','SKIN') ]]:
        key='coeff_w' if name=='power' else 'gains_c';v=np.asarray(m[key])
        if v.shape!=(d,) or v.dtype.kind not in 'fi' or not np.isfinite(v).all() or (v<0).any() or (v>bound).any():raise ValueError('coefficient ABI/bounds')
        if name!='power' and (m['beta_per_s'] not in BETAS or m['mix'] not in (1,.6) or m['initial_mode'] not in ('legacy','past_trend')):raise ValueError('thermal setting')
    return p


def vector(task_u,basis):
    v=np.asarray(task_u,float)
    if v.shape!=(4,) or not np.isfinite(v).all():raise ValueError('task occupancy vector')
    if not np.isin(v,(0,1)).all() or v[0]+v[1]>1:raise ValueError('task occupancy values')
    busy={}
    if v[0] or v[1]:busy['CPU']='classification' if v[0] else 'detection'
    if v[2]:busy['GPU']='classification'
    if v[3]:busy['NPU']='classification'
    checked_busy(busy)
    return np.array([v[0]+v[1],v[2],v[3]]) if basis=='lane' else v


def current_vector(owners,basis):
    checked_busy({b:v[1] for b,v in owners.items()})
    v=[float(any(b=='CPU' and q[1]==task for b,q in owners.items())) for task in ('classification','detection')]
    return vector(v+[float(b in owners) for b in ('GPU','NPU')],basis)


class Basis:
    def __init__(self,d,tau,beta=.06,mix=1):
        self.tau=tau;self.beta=beta;self.mix=mix;self.h=0.;self.now=0.
        self.fast=np.zeros(d);self.slow=np.zeros(d);self.area=np.zeros(d);self.heat_area=np.zeros(d)

    def advance(self,to,u):
        if to<self.now or not math.isfinite(to):raise ValueError('basis clock')
        dt=to-self.now;busy=bool(np.any(u));h0=1. if busy else self.h
        alpha=1/self.tau;ea=math.exp(-alpha*dt);h=1. if busy else h0*ea
        ha=dt if busy else h0*self.tau*(1-ea)
        areas=[]
        for name,beta in (('fast',self.beta),('slow',self.beta/10)):
            y=getattr(self,name);z,area=filtered_step(y[:-1],u,dt,1/beta);eb=math.exp(-beta*dt)
            term=dt*eb if abs(beta-alpha)<1e-10 else (ea-eb)/(beta-alpha)
            hz=1+(y[-1]-1)*eb if busy else y[-1]*eb+beta*h0*term
            h_area=ha-(hz-y[-1])/beta
            setattr(self,name,np.r_[z,hz]);areas.append(np.r_[area,h_area])
        self.area+=np.r_[u*dt,ha];self.heat_area+=self.mix*areas[0]+(1-self.mix)*areas[1];self.h=h;self.now=to
        return self.mix*self.fast+(1-self.mix)*self.slow


def features(intervals,times,basis,tau,beta=.06,mix=1):
    ts=np.asarray(times,float)
    if ts.ndim!=1 or not np.isfinite(ts).all() or (ts<0).any():raise ValueError('feature timestamps')
    d=4 if basis=='lane' else 5;b=Basis(d,tau,beta,mix);events=[]
    for a,z,u in intervals:
        if a<0 or z<a:raise ValueError('interval clock')
        events.extend(((a,1,vector(u,basis)),(z,0,np.zeros(d-1))))
    events.sort(key=lambda t:(t[0],t[1]));u=np.zeros(d-1);j=0;v=np.zeros((len(ts),d));area=v.copy();ha=v.copy()
    for i in np.argsort(ts,kind='stable'):
        while j<len(events) and events[j][0]<=ts[i]:
            at,_,nu=events[j];b.advance(at,u);u=nu;j+=1
        v[i]=b.advance(ts[i],u);area[i]=b.area;ha[i]=b.heat_area
    return v,area,ha


def box_fit(x,y,ridge,bound):
    x=np.asarray(x,float);y=np.asarray(y,float);d=x.shape[1]
    if d not in (4,5) or x.shape!=(len(y),d) or not len(y) or not np.isfinite(x).all() or not np.isfinite(y).all():raise ValueError('fit inputs')
    a=np.vstack((x,np.eye(d)*math.sqrt(ridge/d)/bound));b=np.r_[y,np.zeros(d)];best=None
    for face in itertools.product((-1,0,1),repeat=d):
        free=[i for i,f in enumerate(face) if not f];v=np.array([bound if f==1 else 0. for f in face])
        if free:v[free]=np.linalg.lstsq(a[:,free],b-a@v,rcond=None)[0]
        if (v< -1e-8).any() or (v>bound+1e-8).any():continue
        v=np.clip(v,0,bound);loss=float(np.sum((a@v-b)**2))
        if best is None or loss<best[0]:best=loss,v
    v=best[1];g=a.T@(a@v-b);viol=np.where(v<=1e-7,np.minimum(g,0),np.where(v>=bound-1e-7,np.maximum(g,0),g))
    if np.max(abs(viol))>1e-6:raise ValueError('box fit KKT')
    return v


def amplitude(model,reference,initial,slope):
    if not all(math.isfinite(z) for z in (reference,initial,slope)):raise ValueError('initial thermal input')
    return reference-initial if model['initial_mode']=='legacy' else float(np.clip(slope/model['beta_per_s'],-5,5))


class CostState:
    def __init__(self,p,baseline,reference,initial,slopes):
        self.profile=validate(p)
        if not math.isfinite(baseline) or baseline<0:raise ValueError('initial power')
        self.baseline=baseline;self.reference=dict(reference);self.initial=dict(initial);self.slopes=dict(slopes)
        self.amplitudes={k:amplitude(m,reference[k],initial[k],slopes[k]) for k,m in p['thermal'].items()}
        d=4 if p['basis']=='lane' else 5
        self.basis={k:Basis(d,p['power']['tau_s'],m['beta_per_s'],m['mix']) for k,m in p['thermal'].items()}
        self.owners={};self.now=0.;self.energy=0.;self.temperature_area={k:0. for k in ('AP','SKIN')};self.area_at35=None
        self.peaks=dict(initial);self.peaks_after35={k:None for k in initial};self.grid=[];self._record()

    def temperature(self,k):
        m=self.profile['thermal'][k];b=self.basis[k]
        return self.initial[k]+self.amplitudes[k]*(1-math.exp(-m['beta_per_s']*self.now))+float((m['mix']*b.fast+(1-m['mix'])*b.slow)@m['gains_c'])

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
        u=current_vector(self.owners,self.profile['basis']);g=np.asarray(self.profile['power']['coeff_w'])
        while self.now<to:
            nxt=min(to,self.now+.25,math.floor(self.now+1e-9)+1)
            if self.now<35<nxt:nxt=35.
            old=self.now;before=self.basis['AP'].area.copy()
            for b in self.basis.values():b.advance(nxt,u)
            self.energy+=self.baseline*(nxt-old)+float((self.basis['AP'].area-before)@g);self.now=nxt
            for k,b in self.basis.items():
                beta=self.profile['thermal'][k]['beta_per_s'];initial_area=self.initial[k]*nxt+self.amplitudes[k]*(nxt-(1-math.exp(-beta*nxt))/beta)
                self.temperature_area[k]=initial_area+float(b.heat_area@self.profile['thermal'][k]['gains_c'])
            if self.now==35:self.area_at35=dict(self.temperature_area)
            self._record()
        return self.snapshot()

    def dispatch(self,rid,task,backend):
        if backend in self.owners or any(q[0]==rid for q in self.owners.values()):raise ValueError('duplicate/occupied')
        proposed=dict(self.owners);proposed[backend]=(rid,task);current_vector(proposed,self.profile['basis']);self.owners=proposed
        for b in self.basis.values():b.h=1.

    def available(self,rid,backend):
        if backend not in self.owners or self.owners[backend][0]!=rid:raise ValueError('release mismatch')
        del self.owners[backend]

    def snapshot(self):
        u=current_vector(self.owners,self.profile['basis']);h=1. if np.any(u) else self.basis['AP'].h
        return dict(time_s=self.now,energy_window_j=self.energy,power_w=self.baseline+float(np.r_[u,h]@self.profile['power']['coeff_w']),
            temperature_c={k:self.temperature(k) for k in self.peaks},peak_c=dict(self.peaks),peak_after35_c=dict(self.peaks_after35),
            mean_c={k:self.temperature_area[k]/self.now if self.now else self.initial[k] for k in self.peaks},
            mean_after35_c={k:(self.temperature_area[k]-self.area_at35[k])/(self.now-35) if self.area_at35 is not None and self.now>35 else None for k in self.peaks},
            strict_eligible=False,experiment_ready=False,status='exploratory_refine04')


def predict(ep,p,end=120,observations=None):
    validate(p);mode=p['power']['baseline_mode'];points=np.array(ep['power_points'])
    baseline=ep['baseline_w'] if mode=='mean30' else float(np.median(points[(points[:,0]>=-10)&(points[:,0]<=0),1]))
    _,area,_=features(ep['task_intervals'],[end],p['basis'],p['power']['tau_s'])
    out=dict(energy_j=baseline*end+float(area[0]@p['power']['coeff_w']),baseline_w=baseline)
    for k,m in p['thermal'].items():
        h=ep['thermal'][k];ts=np.arange(0,end+.000001,.25) if observations is None else np.asarray(observations[k],float)
        v,_,ha=features(ep['task_intervals'],ts,p['basis'],p['power']['tau_s'],m['beta_per_s'],m['mix'])
        amp=amplitude(m,h['reference_c'],h['initial_c'],ep['past_slope_c_per_s'][k]);z=1-np.exp(-m['beta_per_s']*ts)
        path=h['initial_c']+amp*z+v@m['gains_c'];area=h['initial_c']*ts+amp*(ts-z/m['beta_per_s'])+ha@m['gains_c']
        out[k]=dict(times=ts,temperatures=path,integral=area,peak=float(path.max()))
    return out
