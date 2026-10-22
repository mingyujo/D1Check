"""Bounded observable wall-demand proxies; not identified core utilization."""
import math
import numpy as np


def steps(intervals,start=-30.):
    events={start:np.zeros(8)}
    for j,xs in enumerate(intervals[:8]):
        for a,b,w in xs:
            a=max(a,start)
            if b<=a:continue
            events.setdefault(a,np.zeros(8))[j]+=w
            events.setdefault(b,np.zeros(8))[j]-=w
    current=np.zeros(8);result=[];previous=None
    for t,d in sorted(events.items()):
        current+=d
        assert min(current)>-1e-7
        f=np.array([float(any(current[j]>1e-9 for j in (0,1,4,5))),float(current[1]>1e-9),
                    float(current[2]>1e-9),float(current[3]>1e-9),float(any(current>1e-9))])
        if previous is None or np.any(f!=previous):result.append((float(t),f));previous=f
    return result


def features(step,times,baseline,start=-30.):
    times=np.asarray(times);assert min(times)-.5>=start and np.all(np.diff(times)>0)
    changes={t:v for t,v in step}
    grid=np.unique(np.r_[start,[t for t,v in step if t<=times[-1]],times,times-.5])
    current=np.zeros(5);area=np.zeros(5);tails=np.zeros((3,5));areas={};states={};previous=start
    for t in grid:
        dt=t-previous;decay=np.exp(-dt/np.array([1.,10.,60.]))[:,None]
        area=area+dt*current;tails=decay*tails+(1-decay)*current
        areas[float(t)]=area.copy();states[float(t)]=tails.copy()
        if t in changes:current=changes[t]
        previous=t
    X=np.asarray([np.r_[1.,baseline,(areas[float(t)]-areas[float(t-.5)])/.5,states[float(t)].ravel()] for t in times])
    assert np.isfinite(X).all() and np.min(X[:,2:])>=-1e-9 and np.max(X[:,2:])<=1+1e-9
    return X


def fit(X,y,w):
    scale=np.maximum(np.sqrt(np.sum(w[:,None]*X**2,axis=0)),1e-6);scale[0]=1.
    Z=X/scale;H=Z.T@(w[:,None]*Z)+np.eye(X.shape[1])/X.shape[1];b=Z.T@(w*y)
    c=np.maximum(0,np.linalg.solve(H,b))
    for iteration in range(20000):
        old=c.copy()
        for j in range(len(c)):c[j]=max(0,c[j]+(b[j]-H[j]@c)/H[j,j])
        if max(abs(c-old))<1e-11:
            grad=H@c-b;free=c>1e-9;kkt=max(float(max(abs(grad[free]))) if any(free) else 0.,float(max(0.,-min(grad))))
            assert kkt<1e-7
            return dict(mode='CAPACITY_BOUNDED_WALL_DEMAND_API',coef=c.tolist(),scale=scale.tolist(),ridge=1.,iterations=iteration+1,KKT=kkt,
                        core_utilization_identified=False,absolute_W_verified=False)
    raise ValueError('Registered coordinate solver nonconvergence; preserve fit')


def predict(X,model):return X/np.asarray(model['scale'])@np.asarray(model['coef'])


def coupled(step,times,baseline,anchor,AP0,skin,power,thermal,start=-30.):
    """Exact linear-system cascade: box ramp + power tails -> two thermal filters."""
    times=np.asarray(times);assert times[0]>=anchor>=start and np.all(np.diff(times)>0)
    change={t:v for t,v in step};delay={t+.5:v for t,v in step}
    grid=np.unique(np.r_[start,anchor,times,[t for t in change if t<=times[-1]],[t for t in delay if t<=times[-1]]])
    c=np.asarray(power['coef'])/np.asarray(power['scale']);B0=c[0]+baseline*c[1];cb=c[2:7];ct=c[7:].reshape(3,5)
    taus=np.array([1.,10.,60.]);heat_taus=[thermal['tau_fast_s'],thermal['tau_slow_s']]
    v=np.zeros(5);vd=np.zeros(5);z=np.zeros((3,5));box=0.;heat=np.zeros(2);area=0.;previous=start;values={}
    for t in grid:
        dt=t-previous;slope=2*float(cb@(v-vd));A=np.sum(ct*(z-v),axis=1)
        constant=B0+box+float(np.sum(ct*v));q=-np.expm1(-dt/taus)
        if previous>=anchor and dt>0:
            for j,ht in enumerate(heat_taus):
                decay=math.exp(-dt/ht);qq=-math.expm1(-dt/ht)
                kernels=np.array([(dt/ht)*decay if pt==ht else (math.exp(-dt/pt)-decay)/(1-ht/pt) for pt in taus])
                heat[j]=decay*heat[j]+(constant-baseline)*qq+slope*(dt-ht*qq)+float(A@kernels)
        area+=constant*dt+.5*slope*dt*dt+float((A*taus)@q)
        z=(1-q[:,None])*z+q[:,None]*v;box+=slope*dt
        idle=skin+thermal['delta_C'];age=t-anchor
        if t>=anchor:
            decay=thermal['w_fast']*math.exp(-age/heat_taus[0])+(1-thermal['w_fast'])*math.exp(-age/heat_taus[1])
            AP=idle+(AP0-idle)*decay+thermal['gain_fast']*heat[0]+thermal['gain_slow']*heat[1]
            P=B0+box+float(np.sum(ct*z));values[float(t)]=(P,AP,area)
        if t in change:v=change[t]
        if t in delay:vd=delay[t]
        previous=t
    result=np.asarray([values[float(t)] for t in times]);assert np.isfinite(result).all()
    return result
