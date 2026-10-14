"""Causal observed boundary, paired-duty cost and delayed reported-temperature model."""
import bisect
import math
import numpy as np
from tools import d1_s26_dynamic_cost_model as d
from tools.d1_s26_cost_refine_model import current_vector, vector

ABI='s26-paired-observed-cost-v5'
COOL_BETAS=np.array([.3,.03])
box_fit=d.box_fit


def causal_boundary(power,thermal,anchor,mode,state_estimator=None):
    """All inputs must have completed measurement before the boundary."""
    if mode not in ('START0','OBSERVED35') or anchor!=(0 if mode=='START0' else 35):raise ValueError('boundary mode/time')
    p=np.asarray(power,float)
    if p.ndim!=2 or p.shape[1]!=3 or len(p)<5 or not np.isfinite(p).all() or (p[:,1]>anchor).any() or (p[:,0]>p[:,1]).any() or (p[:,2]<0).any():raise ValueError('power measurement availability')
    p=p[np.argsort(p[:,0])];lo=anchor-30 if anchor==0 else 0.;last=p[-1,0]
    # Do not bracket an endpoint with a not-yet-available future observation.
    left=max(lo,p[0,0]);inside=(p[:,0]>left)&(p[:,0]<last);tt=np.r_[left,p[inside,0],last];vv=np.interp(tt,p[:,0],p[:,2])
    if last-left<5 or np.max(np.diff(tt))>2.5 or anchor-last>2.5:raise ValueError('past power coverage')
    mean=float(np.sum(np.diff(tt)*(vv[1:]+vv[:-1])/2)/(last-left));recent=p[p[:,0]>=anchor-10,2]
    if len(recent)<5:raise ValueError('past recent power')
    median=float(np.median(recent));base,unstable=d.initial_power(mean,median)
    prefix=mean*last+base*(anchor-last) if anchor else 0.
    out=dict(anchor_s=anchor,mode=mode,baseline_w=base,mean_past_w=mean,median10_w=median,unstable_initial_power=unstable,
             energy_prefix_estimate_j=prefix,initial_c={},reference_c={},cooling_amplitudes_c={},temperature_prefix_area={},temperature_prefix_peak={},thermal_age_s={},owners={},evidence='past_sensor_observations')
    for k in ('AP','SKIN'):
        a=np.asarray(thermal[k],float)
        if a.ndim!=2 or a.shape[1]!=2 or len(a)<3 or not np.isfinite(a).all() or (a[:,0]>anchor).any():raise ValueError('thermal measurement availability')
        a=a[np.argsort(a[:,0])];recent=a[a[:,0]>=anchor-20]
        if len(recent)<3:raise ValueError('thermal state history')
        initial=float(a[-1,1]);age=anchor-a[-1,0]
        if age>5:raise ValueError('stale thermal initialization')
        x=np.exp((anchor-recent[:,0,None])*COOL_BETAS)-1.;y=recent[:,1]-initial
        amps=(state_estimator(x,y,k) if state_estimator else box_fit(x/math.sqrt(len(y)),y/math.sqrt(len(y)),.001,[8,8]))
        out['initial_c'][k]=initial;out['reference_c'][k]=float(np.mean(a[a[:,0]>=anchor-10,1]));out['cooling_amplitudes_c'][k]=amps.tolist();out['thermal_age_s'][k]=float(age)
        if anchor:
            if a[0,0]>0:raise ValueError('missing observed thermal prefix')
            end=a[-1,0];mask=(a[:,0]>0)&(a[:,0]<end);ts=np.r_[0,a[mask,0],end,anchor];values=np.r_[np.interp(0,a[:,0],a[:,1]),a[mask,1],a[-1,1],initial]
            out['temperature_prefix_area'][k]=float(np.sum(np.diff(ts)*(values[1:]+values[:-1])/2));out['temperature_prefix_peak'][k]=float(values.max())
        else:out['temperature_prefix_area'][k]=0.;out['temperature_prefix_peak'][k]=initial
    return out


def validate(p):
    if p.get('abi')!=ABI or p.get('strict_eligible') is not False or p.get('experiment_ready') is not False:raise ValueError('observer cost ABI')
    if p['mode'] not in ('START0','OBSERVED35') or p['alpha'] not in (0,1,4) or p['q_threshold'] not in (0,.25,.5) or p['tau_h_s'] not in (.5,5,15):raise ValueError('observer structural settings')
    if set(p['thermal'])!={'AP','SKIN'}:raise ValueError('sensors')
    for kind,m,b in [('power',p['power'],[10]*5+[0]),*[(k,m,[60]*5+[0,3,3]) for k,m in p['thermal'].items()]]:
        v=np.asarray(m['coefficients']);bounds=np.asarray(b)
        if v.shape!=bounds.shape or v.dtype.kind not in 'fi' or not np.isfinite(v).all() or (v<0).any() or (v>bounds).any():raise ValueError('coefficients')
        if kind!='power' and (m['beta_per_s'] not in (.03,.06,.12,.25) or m['mix'] not in (1,.6) or m['delay_s'] not in (0,2,4) or m['initial_mode'] not in ('legacy','cooling2')):raise ValueError('thermal settings')
        if kind!='power' and m['initial_mode']=='legacy' and np.any(v[6:]!=0):raise ValueError('disabled initial states')
    return p


def validate_initial(init,p):
    if init['mode']!=p['mode'] or init['anchor_s']!=(0 if p['mode']=='START0' else 35) or init.get('owners')!={}:raise ValueError('initial boundary/owners')
    if not math.isfinite(init['baseline_w']) or init['baseline_w']<=0 or not math.isfinite(init['energy_prefix_estimate_j']) or init['energy_prefix_estimate_j']<0:raise ValueError('initial power/energy')
    for k in ('AP','SKIN'):
        for key in ('initial_c','reference_c','temperature_prefix_area','temperature_prefix_peak'):
            if not math.isfinite(init[key][k]):raise ValueError('initial temperatures')
        amps=np.asarray(init['cooling_amplitudes_c'][k])
        if amps.shape!=(2,) or not np.isfinite(amps).all() or (amps<0).any() or (amps>8).any():raise ValueError('initial cooling states')


class Basis(d.Basis):
    def __init__(self,alpha,threshold,tau,beta=.06,mix=1):super().__init__(alpha,tau,beta,mix);self.threshold=threshold

    def _piece(self,dt,u):
        cpu=u[0]+u[1];busy=bool(np.any(u));h0=1. if busy else self.h;t=d.NODES*dt
        q=cpu+(self.q-cpu)*np.exp(-t/5);phi=np.tile(np.r_[u,0.,0.],(8,1));phi[:,:2]/=1+self.alpha*np.maximum(q[:,None]-self.threshold,0)
        phi[:,4]=1. if busy else h0*np.exp(-t/self.tau);phi[:,5]=self.r*np.exp(-t);area=dt*(d.WEIGHTS@phi);areas=[]
        for name,beta in [('fast',self.beta),('slow',self.beta/10)]:
            prev=getattr(self,name);after=prev*math.exp(-beta*dt)+beta*dt*((d.WEIGHTS*np.exp(-beta*(dt-t)))@phi)
            areas.append(area-(after-prev)/beta);setattr(self,name,after)
        self.area+=area;self.heat_area+=self.mix*areas[0]+(1-self.mix)*areas[1];self.q=cpu+(self.q-cpu)*math.exp(-dt/5)
        self.h=1. if busy else h0*math.exp(-dt/self.tau);self.r*=math.exp(-dt);self.now+=dt

    def _step(self,dt,u):
        cpu=u[0]+u[1];end=cpu+(self.q-cpu)*math.exp(-dt/5)
        if self.alpha and min(self.q,end)<self.threshold<max(self.q,end):
            cross=-5*math.log((self.threshold-cpu)/(self.q-cpu));self._piece(cross,u);self._piece(dt-cross,u)
        else:self._piece(dt,u)

    def current(self,u):
        v=np.r_[u,1. if np.any(u) else self.h,self.r];v[:2]/=1+self.alpha*max(self.q-self.threshold,0);return v


def features(intervals,dispatches,times,alpha,threshold,tau,beta=.06,mix=1):
    ts=np.asarray(times,float)
    if ts.ndim!=1 or not np.isfinite(ts).all() or (ts<0).any():raise ValueError('feature times')
    b=Basis(alpha,threshold,tau,beta,mix);events=[]
    for a,z,u in intervals:
        if a<0 or z<a:raise ValueError('interval time')
        events.extend(((a,1,vector(u,'task')),(z,0,np.zeros(4))))
    for t in dispatches:
        if not math.isfinite(t) or t<0:raise ValueError('dispatch time')
        events.append((t,2,None))
    events.sort(key=lambda e:(e[0],e[1]));u=np.zeros(4);j=0;v=np.zeros((len(ts),6));area=v.copy();ha=v.copy()
    for i in np.argsort(ts,kind='stable'):
        while j<len(events) and events[j][0]<=ts[i]:
            at,kind,new_u=events[j];b.advance(at,u)
            if kind==2:b.dispatch()
            else:u=new_u
            j+=1
        v[i]=b.advance(ts[i],u);area[i]=b.area;ha[i]=b.heat_area
    return v,area,ha


def initial_terms(m,init,k,ts):
    ts=np.asarray(ts,float);initial=init['initial_c'][k]
    if m['initial_mode']=='legacy':
        ref=init['reference_c'][k];beta=m['beta_per_s'];base=ref+(initial-ref)*np.exp(-beta*ts);base_area=ref*ts+(initial-ref)*(1-np.exp(-beta*ts))/beta
        return base,np.zeros((len(ts),2)),base_area,np.zeros((len(ts),2))
    amps=np.asarray(init['cooling_amplitudes_c'][k]);z=1-np.exp(-ts[:,None]*COOL_BETAS)
    return np.full(len(ts),initial),-amps*z,initial*ts,-amps*(ts[:,None]-z/COOL_BETAS)


class CostState:
    def __init__(self,p,init):
        self.profile=validate(p);validate_initial(init,p);self.init=init;self.anchor=init['anchor_s'];self.now=float(self.anchor);self.owners={}
        self.basis={k:Basis(p['alpha'],p['q_threshold'],p['tau_h_s'],m['beta_per_s'],m['mix']) for k,m in p['thermal'].items()}
        self.hist_times=[0.];self.hist={k:[(np.zeros(6),np.zeros(6))] for k in self.basis}
        self.energy=init['energy_prefix_estimate_j'];self.temperature_area=dict(init['temperature_prefix_area']);self.peaks=dict(init['temperature_prefix_peak'])
        self.area_at35=dict(self.temperature_area) if self.anchor==35 else None;self.peaks_after35={k:init['initial_c'][k] if self.anchor==35 else None for k in self.basis};self.grid=[];self._record()

    def _history(self,k,t):
        if t<=0:return np.zeros(6),np.zeros(6)
        if t>=self.hist_times[-1]:return self.hist[k][-1]
        j=bisect.bisect_left(self.hist_times,t)
        if abs(self.hist_times[j]-t)<1e-10:return self.hist[k][j]
        left,right=self.hist_times[j-1:j+1];f=(t-left)/(right-left)
        return tuple(a+(b-a)*f for a,b in zip(self.hist[k][j-1],self.hist[k][j]))

    def temperature(self,k):
        m=self.profile['thermal'][k];t=self.now-self.anchor;z,_=self._history(k,max(0,t-m['delay_s']));base,init,_,_=initial_terms(m,self.init,k,[t])
        return float(base[0]+z@m['coefficients'][:6]+init[0]@m['coefficients'][6:])

    def _record(self):
        for k in self.peaks:
            temp=self.temperature(k);self.peaks[k]=max(self.peaks[k],temp)
            if self.now>=35:self.peaks_after35[k]=temp if self.peaks_after35[k] is None else max(self.peaks_after35[k],temp)
        if abs(self.now-round(self.now))<1e-9:
            row=dict(time_s=self.now,AP_c=self.temperature('AP'),SKIN_c=self.temperature('SKIN'),energy_j=self.energy)
            if self.grid and self.grid[-1]['time_s']==self.now:self.grid[-1]=row
            else:self.grid.append(row)

    def advance(self,to):
        if not math.isfinite(to) or to<self.now:raise ValueError('cost boundary clock')
        u=current_vector(self.owners,'task')
        while self.now<to:
            nxt=min(to,(math.floor((self.now-self.anchor)*4+1e-9)+1)/4+self.anchor);elapsed=nxt-self.anchor
            for b in self.basis.values():b.advance(elapsed,u)
            self.now=nxt;self.hist_times.append(elapsed)
            for k,b in self.basis.items():self.hist[k].append(((b.mix*b.fast+(1-b.mix)*b.slow).copy(),b.heat_area.copy()))
            self.energy=self.init['energy_prefix_estimate_j']+self.init['baseline_w']*elapsed+float(self.basis['AP'].area@self.profile['power']['coefficients'])
            for k,m in self.profile['thermal'].items():
                _,ha=self._history(k,max(0,elapsed-m['delay_s']));_,_,base,init=initial_terms(m,self.init,k,[elapsed])
                self.temperature_area[k]=self.init['temperature_prefix_area'][k]+float(base[0]+ha@m['coefficients'][:6]+init[0]@m['coefficients'][6:])
            if self.now==35:self.area_at35=dict(self.temperature_area)
            self._record()
        return self.snapshot()

    def dispatch(self,rid,task,backend):
        if backend in self.owners or any(v[0]==rid for v in self.owners.values()):raise ValueError('duplicate/occupied')
        proposed=dict(self.owners);proposed[backend]=(rid,task);current_vector(proposed,'task');self.owners=proposed
        for b in self.basis.values():b.dispatch();b.h=1.

    def available(self,rid,backend):
        if backend not in self.owners or self.owners[backend][0]!=rid:raise ValueError('AVAILABLE owner mismatch')
        del self.owners[backend]

    def snapshot(self):
        phi=self.basis['AP'].current(current_vector(self.owners,'task'))
        return dict(time_s=self.now,energy_window_j=self.energy,power_w=self.init['baseline_w']+float(phi@self.profile['power']['coefficients']),
            temperature_c={k:self.temperature(k) for k in self.peaks},peak_c=dict(self.peaks),peak_after35_c=dict(self.peaks_after35),mean_c={k:self.temperature_area[k]/self.now if self.now else self.init['initial_c'][k] for k in self.peaks},
            mean_after35_c={k:(self.temperature_area[k]-self.area_at35[k])/(self.now-35) if self.area_at35 is not None and self.now>35 else None for k in self.peaks},
            initialization_mode=self.profile['mode'],initialization_evidence=self.init['evidence'],energy_prefix_is_observed_estimate=self.anchor==35,unstable_initial_power=self.init['unstable_initial_power'],strict_eligible=False,experiment_ready=False)
