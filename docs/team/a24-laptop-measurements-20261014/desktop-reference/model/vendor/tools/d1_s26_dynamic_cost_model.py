"""Current dispatch, reservation duty, startup pulses and separate initial heat."""
import math
import numpy as np
from tools.d1_s26_cost_refine_model import current_vector, amplitude

ABI='s26-dispatch-duty-cost-v4'
G,W=np.polynomial.legendre.leggauss(8)
NODES=(G+1)/2;WEIGHTS=W/2


def validate(p):
    if p.get('abi')!=ABI or p.get('strict_eligible') is not False or p.get('experiment_ready') is not False:raise ValueError('dynamic cost ABI/eligibility')
    if p['alpha'] not in (0,1,4) or p['pulse'] not in (False,True) or p['tau_h_s'] not in (.5,5,15):raise ValueError('dynamic setting')
    if p['initial_power_ratio_threshold']!=2:raise ValueError('initial power rule')
    if set(p['thermal'])!={'AP','SKIN'}:raise ValueError('thermal sensors')
    for k,m,bounds in [('power',p['power'],[10]*5+[2]),*[(k,m,[60]*6+[3]) for k,m in p['thermal'].items()]]:
        v=np.asarray(m['coefficients']);bound=np.asarray(bounds)
        if v.shape!=bound.shape or v.dtype.kind not in 'fi' or not np.isfinite(v).all() or (v<0).any() or (v>bound).any():raise ValueError('coefficient ABI/range')
        if not p['pulse'] and v[5]!=0:raise ValueError('disabled startup coefficient')
        if k!='power':
            if m['beta_per_s'] not in (.03,.06,.12,.25) or m['mix'] not in (1,.6) or m['initial_mode'] not in ('legacy','trend'):raise ValueError('thermal setting')
            if m['initial_mode']=='legacy' and v[6]!=0:raise ValueError('legacy initial coefficient')
            if m['initial_mode']=='trend' and m['initial_beta_per_s'] not in (.03,.12,.5):raise ValueError('initial kernel')
    return p


def initial_power(mean30,median10):
    if not all(math.isfinite(x) and x>0 for x in (mean30,median10)):raise ValueError('initial power statistics')
    unstable=mean30>2*median10
    return (median10 if unstable else mean30),unstable


def box_fit(x,y,ridge,bounds):
    """Strictly convex bounded least squares active-set; frozen nonnegative bounds."""
    x=np.asarray(x,float);y=np.asarray(y,float);upper=np.asarray(bounds,float);d=len(upper)
    if x.shape!=(len(y),d) or not np.isfinite(x).all() or not np.isfinite(y).all() or not np.isfinite(upper).all() or (upper<0).any() or ridge<=0:raise ValueError('BVLS input')
    n=max(1,int(np.sum(upper>0)));penalty=np.where(upper>0,ridge/n/np.maximum(upper,1e-12)**2,1.)
    q=x.T@x+np.diag(penalty);rhs=x.T@y;v=np.zeros(d);free=set();fixed=set(np.flatnonzero(upper==0));tol=1e-9
    for iteration in range(500):
        grad=q@v-rhs
        violation=np.where(v<=1e-10,np.minimum(grad,0),np.where(v>=upper-1e-10,np.maximum(grad,0),grad));violation[list(fixed)]=0
        if np.max(abs(violation))<tol:return v
        candidates=[i for i in range(d) if i not in free and i not in fixed and abs(violation[i])>tol]
        if candidates:free.add(max(candidates,key=lambda i:abs(violation[i])))
        if not free:raise ValueError('BVLS empty active set')
        for _ in range(d+2):
            ix=sorted(free);other=[i for i in range(d) if i not in free];target=v.copy()
            target[ix]=np.linalg.solve(q[np.ix_(ix,ix)],rhs[ix]-q[np.ix_(ix,other)]@v[other])
            bad=[i for i in ix if target[i]<-1e-12 or target[i]>upper[i]+1e-12]
            if not bad:v=np.clip(target,0,upper);break
            steps=[((0-v[i])/(target[i]-v[i]) if target[i]<0 else (upper[i]-v[i])/(target[i]-v[i]),i) for i in bad]
            step,hit=min(steps);v=np.clip(v+step*(target-v),0,upper);v[hit]=0 if target[hit]<0 else upper[hit];free.remove(hit)
        else:raise ValueError('BVLS inner iteration cap')
    raise ValueError('BVLS KKT/iteration cap')


class Basis:
    def __init__(self,alpha,tau,beta=.06,mix=1):
        self.alpha=alpha;self.tau=tau;self.beta=beta;self.mix=mix;self.now=0.;self.q=0.;self.h=0.;self.r=0.
        self.fast=np.zeros(6);self.slow=np.zeros(6);self.area=np.zeros(6);self.heat_area=np.zeros(6)

    def dispatch(self):self.r+=1.

    def _step(self,dt,u):
        cpu=u[0]+u[1];busy=bool(np.any(u));h0=1. if busy else self.h;t=NODES*dt
        q=cpu+(self.q-cpu)*np.exp(-t/5);phi=np.tile(np.r_[u,0.,0.],(8,1))
        phi[:,:2]/=(1+self.alpha*q[:,None]);phi[:,4]=1. if busy else h0*np.exp(-t/self.tau);phi[:,5]=self.r*np.exp(-t)
        area=dt*(WEIGHTS@phi);integrals=[]
        for name,beta in [('fast',self.beta),('slow',self.beta/10)]:
            previous=getattr(self,name);eb=math.exp(-beta*dt)
            after=previous*eb+beta*dt*((WEIGHTS*np.exp(-beta*(dt-t)))@phi)
            integrals.append(area-(after-previous)/beta);setattr(self,name,after)
        self.area+=area;self.heat_area+=self.mix*integrals[0]+(1-self.mix)*integrals[1]
        self.q=cpu+(self.q-cpu)*math.exp(-dt/5);self.h=1. if busy else h0*math.exp(-dt/self.tau);self.r*=math.exp(-dt);self.now+=dt

    def advance(self,to,u):
        if to<self.now or not math.isfinite(to):raise ValueError('basis clock')
        while self.now<to:
            nxt=min(to,self.now+.25);self._step(nxt-self.now,u);self.now=nxt
        return self.mix*self.fast+(1-self.mix)*self.slow

    def current(self,u):
        v=np.r_[u,1. if np.any(u) else self.h,self.r];v[:2]/=1+self.alpha*self.q;return v


def features(intervals,dispatches,times,alpha,tau,beta=.06,mix=1):
    ts=np.asarray(times,float)
    if ts.ndim!=1 or not np.isfinite(ts).all() or (ts<0).any():raise ValueError('feature timestamps')
    b=Basis(alpha,tau,beta,mix);events=[]
    for start,end,u in intervals:
        if start<0 or end<start:raise ValueError('interval clock')
        from tools.d1_s26_cost_refine_model import vector
        v=vector(u,'task');events.extend(((start,1,v),(end,0,np.zeros(4))))
    for at in dispatches:
        if at<0 or not math.isfinite(at):raise ValueError('dispatch clock')
        events.append((at,2,None))
    events.sort(key=lambda x:(x[0],x[1]));u=np.zeros(4);j=0;v=np.zeros((len(ts),6));area=v.copy();ha=v.copy()
    for i in np.argsort(ts,kind='stable'):
        while j<len(events) and events[j][0]<=ts[i]:
            at,kind,next_u=events[j];b.advance(at,u)
            if kind==2:b.dispatch()
            else:u=next_u
            j+=1
        v[i]=b.advance(ts[i],u);area[i]=b.area;ha[i]=b.heat_area
    return v,area,ha


def initial_path(model,ts,reference,initial,slope):
    ts=np.asarray(ts,float)
    if not all(math.isfinite(x) for x in (reference,initial,slope)):raise ValueError('initial thermal values')
    if model['initial_mode']=='legacy':
        beta=model['beta_per_s'];base=reference+(initial-reference)*np.exp(-beta*ts);signal=np.zeros(len(ts));signal_area=signal.copy()
        base_area=reference*ts+(initial-reference)*(1-np.exp(-beta*ts))/beta
    else:
        beta=model['initial_beta_per_s'];amp=float(np.clip(slope/beta,-5,5));z=1-np.exp(-beta*ts)
        base=np.full(len(ts),initial);signal=amp*z;signal_area=amp*(ts-z/beta);base_area=initial*ts
    return base,signal,base_area,signal_area


class CostState:
    def __init__(self,p,mean30,median10,reference,initial,slopes):
        self.profile=validate(p);self.baseline,self.unstable_initial_power=initial_power(mean30,median10)
        self.reference=dict(reference);self.initial=dict(initial);self.slopes=dict(slopes)
        for k,m in p['thermal'].items():initial_path(m,[0.],reference[k],initial[k],slopes[k])
        self.basis={k:Basis(p['alpha'],p['tau_h_s'],m['beta_per_s'],m['mix']) for k,m in p['thermal'].items()}
        self.owners={};self.now=0.;self.energy=0.;self.temperature_area={k:0. for k in ('AP','SKIN')};self.area_at35=None
        self.peaks=dict(initial);self.peaks_after35={k:None for k in self.peaks};self.grid=[];self._record()

    def temperature(self,k):
        m=self.profile['thermal'][k];b=self.basis[k];base,init,_,_=initial_path(m,[self.now],self.reference[k],self.initial[k],self.slopes[k])
        return float(base[0]+(m['mix']*b.fast+(1-m['mix'])*b.slow)@m['coefficients'][:6]+init[0]*m['coefficients'][6])

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
        u=current_vector(self.owners,'task');coeff=np.asarray(self.profile['power']['coefficients'])
        while self.now<to:
            nxt=min(to,self.now+.25,math.floor(self.now+1e-9)+1)
            if self.now<35<nxt:nxt=35.
            old=self.now;before=self.basis['AP'].area.copy()
            for b in self.basis.values():b.advance(nxt,u)
            self.energy+=self.baseline*(nxt-old)+float((self.basis['AP'].area-before)@coeff);self.now=nxt
            for k,b in self.basis.items():
                m=self.profile['thermal'][k];_,_,base,init=initial_path(m,[nxt],self.reference[k],self.initial[k],self.slopes[k])
                self.temperature_area[k]=float(base[0]+b.heat_area@m['coefficients'][:6]+init[0]*m['coefficients'][6])
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
        u=current_vector(self.owners,'task');phi=self.basis['AP'].current(u)
        return dict(time_s=self.now,energy_window_j=self.energy,power_w=self.baseline+float(phi@self.profile['power']['coefficients']),
            temperature_c={k:self.temperature(k) for k in self.peaks},peak_c=dict(self.peaks),peak_after35_c=dict(self.peaks_after35),
            mean_c={k:self.temperature_area[k]/self.now if self.now else self.initial[k] for k in self.peaks},
            mean_after35_c={k:(self.temperature_area[k]-self.area_at35[k])/(self.now-35) if self.area_at35 is not None and self.now>35 else None for k in self.peaks},
            unstable_initial_power=self.unstable_initial_power,cpu_duty_state=self.basis['AP'].q,dispatch_rate_state=self.basis['AP'].r,
            strict_eligible=False,experiment_ready=False,status='exploratory_dynamic05')
