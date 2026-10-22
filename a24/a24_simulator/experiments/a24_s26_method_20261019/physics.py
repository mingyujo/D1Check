"""A24-anchored virtual port of S26 activity filters and passive RC cascade.

No S26 absolute watts, NPU, or base inference durations are substituted.
CPU-union power and the imported dimensionless thermal shape are assumptions.
"""
import math,copy
from physics_parallel import ParallelPhysics

class Physics(ParallelPhysics):
    def __init__(self,model,config,profile,shape):
        super().__init__(model,config,3,.25)
        self.profile=profile;self.shape=shape
        self.wait_limit_ns=10**15
    def initial(self,T):
        if self.profile=='ORIGINAL':return dict(temperature_c=T,shared_z=0.)
        return dict(temperature_c=T,shared_z=0.,time_s=0.,v=[0.]*3,vd=[0.]*3,z=[0.]*3,box=0.,pending=[],heat=[0.,0.],initial_c=T)
    def speed(self,T,route,stage,task='D'):
        if self.profile!='S26_STYLE':return super().speed(T,route,stage)
        if stage!=1:return 1.
        k=self.shape['slopes_per_c'][(task+'_'+route)]
        # Same log-linear temperature response as S26, anchored to A24 26 C.
        # No claim that its signed slopes were identified on A24.
        return min(1.2,max(.45,math.exp(-k*(T-self.c.reference_c))))
    def rates(self,T,active):
        n=sum(j['route']=='CPU' and j['stage']==1 for j in active)
        return {j['request_id']:self.speed(T,j['route'],j['stage'],j['task'])/(1+self.beta*max(0,n-1) if j['route']=='CPU' and j['stage']==1 else 1) for j in active}
    def transition(self,state,active,dt):
        if self.profile=='ORIGINAL':return super().transition(state,active,dt)
        assert dt>=0 and math.isfinite(dt)
        assert sum(j['route']=='CPU' for j in active)<=3 and sum(j['route']=='GPU' for j in active)<=1
        s=copy.deepcopy(state);T=s['temperature_c'];rates=self.rates(T,active)
        # Same-task CPU packing costs one active channel, as in S26's Boolean
        # CPU activity regressor. Max preserves A24 C/D solo anchors.
        v=[max([self.solo[('classification' if j['task']=='C' else 'detection')+'_CPU']-self.shared for j in active if j['route']=='CPU'] or [0.]),
           max([self.solo[('classification' if j['task']=='C' else 'detection')+'_GPU']-self.shared for j in active if j['route']=='GPU'] or [0.]),self.shared if active else 0.]
        if v!=s['v']:s['v']=v;s['pending'].append([s['time_s']+.5,v.copy()])
        # S26 uses a .5 s moving box plus exp(1/10/60 s) activity filters.
        # Its only nonzero tail is GPU tau=1. Normalize channel DC gain to A24.
        ratio=self.shape['gpu_box_fraction'];cb=[1.,ratio,1.];ct=[0.,1-ratio,0.]
        end=s['time_s']+dt;J=area=0.;peak=T
        while s['time_s']<end-1e-12:
            while s['pending'] and s['pending'][0][0]<=s['time_s']+1e-12:s['vd']=s['pending'].pop(0)[1]
            h=min(end,s['pending'][0][0] if s['pending'] else end)-s['time_s']
            slope=2*sum(cb[i]*(s['v'][i]-s['vd'][i]) for i in range(3))
            constant=s['box']+sum(ct[i]*s['v'][i] for i in range(3))
            A=sum(ct[i]*(s['z'][i]-s['v'][i]) for i in range(3));q=-math.expm1(-h)
            energy=constant*h+.5*slope*h*h+A*q
            if self.profile=='S26_STYLE':
                taus=self.shape['thermal_taus_s'];gains=self.shape['thermal_gains'];nextheat=[];H=self.c.idle_c*h
                # Initial passive state uses the S26 fast/slow weight.
                age=s['time_s'];w=self.shape['initial_fast_weight']
                H+=(s['initial_c']-self.c.idle_c)*sum(ww*tau*math.exp(-age/tau)*(-math.expm1(-h/tau)) for ww,tau in zip((w,1-w),taus))
                for old,tau,gain in zip(s['heat'],taus,gains):
                    decay=math.exp(-h/tau);one=-math.expm1(-h/tau)
                    kernel=(h/tau)*decay if tau==1 else (math.exp(-h)-decay)/(1-tau)
                    new=old*decay+constant*one+slope*(h-tau*one)+A*kernel
                    H+=gain*(energy-tau*(new-old));nextheat.append(new)
                s['heat']=nextheat
                tnew=self.c.idle_c+(s['initial_c']-self.c.idle_c)*sum(ww*math.exp(-(age+h)/tau) for ww,tau in zip((w,1-w),taus))+sum(g*x for g,x in zip(gains,nextheat))
            else:
                tau=self.c.thermal_tau_s;R=self.c.thermal_resistance;old=T-self.c.idle_c;decay=math.exp(-h/tau);one=-math.expm1(-h/tau);kernel=(math.exp(-h)-decay)/(1-tau)
                new=old*decay+R*(constant*one+slope*(h-tau*one)+A*kernel)
                H=self.c.idle_c*h+tau*(old-new)+R*energy;tnew=self.c.idle_c+new
            s['z']=[v+(z-v)*math.exp(-h) for z,v in zip(s['z'],s['v'])];s['box']+=slope*h;s['time_s']+=h
            J+=energy;area+=H;peak=max(peak,tnew);T=tnew
        while s['pending'] and s['pending'][0][0]<=end+1e-12:s['vd']=s['pending'].pop(0)[1]
        s['temperature_c']=T;s['shared_z']=float(bool(active))
        assert J>=-1e-8 and T>=self.c.idle_c-1e-8
        return s,dict(increment=max(0.,J),baseline=self.c.baseline*dt,dynamic=max(0.,J),shared=0.,temperature_area=area,peak=peak,speeds=rates,dt=dt)
