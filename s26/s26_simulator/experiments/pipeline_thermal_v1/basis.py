"""Exact LP of every bounded-power basis. No fitting or policy information."""
import numpy as np


def thermal_basis(step,times,baseline,anchor,taus,start=-30.):
    times=np.asarray(times);taus=np.asarray(taus,dtype=float)
    change={t:v for t,v in step};delay={t+.5:v for t,v in step}
    grid=np.unique(np.r_[start,anchor,times,[t for t in change if t<=times[-1]],[t for t in delay if t<=times[-1]]])
    pt=np.array([1.,10.,60.]);denom=1-taus[:,None]/pt;equal=abs(denom)<1e-12
    v=np.zeros(5);vd=np.zeros(5);z=np.zeros((3,5));box=np.zeros(5);B=np.zeros((len(taus),22));previous=start;values={}
    query=set(float(t) for t in times)
    for t in grid:
        dt=t-previous;pd=np.exp(-dt/pt);hd=np.exp(-dt/taus);pq=-np.expm1(-dt/pt);hq=-np.expm1(-dt/taus)
        slope=np.r_[0.,0.,2*(v-vd),np.zeros(15)]
        const=np.r_[1.,baseline,box,np.tile(v,3)]
        A=np.zeros((3,22))
        for j in range(3):A[j,7+5*j:12+5*j]=z[j]-v
        if previous>=anchor and dt>0:
            K=np.divide(pd[None,:]-hd[:,None],denom,out=np.zeros_like(denom),where=~equal)
            for i,j in zip(*np.nonzero(equal)):K[i,j]=(dt/taus[i])*hd[i]
            B=hd[:,None]*B+hq[:,None]*const+(dt-taus*hq)[:,None]*slope+K@A
        z=pd[:,None]*z+pq[:,None]*v;box+=2*dt*(v-vd)
        assert min(box)>-1e-7 and max(box)<1+1e-7
        if float(t) in query:values[float(t)]=B.copy()
        if t in change:v=change[t]
        if t in delay:vd=delay[t]
        previous=t
    result=np.asarray([values[float(t)] for t in times]);assert np.isfinite(result).all()
    return result


def design(ep,pair,power,indices):
    age=ep['times']-ep['anchor_s'];ef=np.exp(-age/pair[0]);es=np.exp(-age/pair[1]);c=np.asarray(power['coef'])/np.asarray(power['scale'])
    xf=ep['B'][:,indices[pair[0]],:]@c-ep['baseline']*(1-ef)
    xs=ep['B'][:,indices[pair[1]],:]@c-ep['baseline']*(1-es)
    base=ep['skin']+(ep['anchor_AP']-ep['skin'])*es
    return base,np.column_stack((1-es,(ep['anchor_AP']-ep['skin'])*(ef-es),-(ef-es),xf,xs))
