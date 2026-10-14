"""Separate continuous route-call power, gauge observations and initial heat.

Only past-history summaries initialize this model. No queue plan or policy name
is a model feature. Host-call envelopes include preprocessing; they are not core
power measurements. The observation filter is a hypothesis, not a sensor spec.
"""
import math
import numpy as np

VERSION = 's26-phase-observer-initialheat-v26'
DT = .005
POWER_FIELDS = ('past_median5', 'past_median10', 'past_mean30', 'initial_power_tail',
                'classification_CPU_call', 'detection_CPU_call',
                'classification_GPU_call', 'classification_NPU_call',
                'shared_admission', 'shared_persist_release', 'activity_tail')


def bounded_fit(x, y, ridge, lower, upper, prior=None, anchors=None):
    """Mixed-sign BVLS active set with a strictly positive ridge diagonal."""
    x, y = np.asarray(x,float), np.asarray(y,float)
    low, high = np.asarray(lower,float), np.asarray(upper,float)
    d = len(low)
    if x.shape != (len(y),d) or high.shape != low.shape or not np.isfinite(x).all() or not np.isfinite(y).all() or (low>high).any() or ridge<=0:
        raise ValueError('bounded regression input')
    center = np.zeros(d) if prior is None else np.asarray(prior,float)
    scale = np.maximum(high-low,1.)
    penalty = ridge/d/scale**2 + 1e-9
    q, rhs = x.T@x + np.diag(penalty), x.T@y + penalty*center
    if anchors:
        for row, target, weight in anchors:
            row=np.asarray(row,float)
            q += weight*np.outer(row,row)
            rhs += weight*row*target
    v = np.clip(center,low,high)
    fixed = set(np.flatnonzero(low==high))
    free = set(i for i in range(d) if low[i]<v[i]<high[i])
    tolerance = 1e-8
    for iteration in range(1000):
        gradient=q@v-rhs
        violation=np.where(v<=low+1e-10,np.minimum(gradient,0),np.where(v>=high-1e-10,np.maximum(gradient,0),gradient))
        if fixed:
            violation[list(fixed)]=0
        if np.max(abs(violation))<tolerance:
            return v
        candidates=[i for i in range(d) if i not in free and i not in fixed and abs(violation[i])>tolerance]
        if candidates:
            free.add(max(candidates,key=lambda i:abs(violation[i])))
        if not free:
            raise ValueError('empty BVLS active set')
        for inner in range(d+2):
            ix=sorted(free)
            other=[i for i in range(d) if i not in free]
            target=v.copy()
            target[ix]=np.linalg.solve(q[np.ix_(ix,ix)],rhs[ix]-q[np.ix_(ix,other)]@v[other])
            bad=[i for i in ix if target[i]<low[i]-1e-12 or target[i]>high[i]+1e-12]
            if not bad:
                v=np.clip(target,low,high)
                break
            steps=[(((low[i] if target[i]<low[i] else high[i])-v[i])/(target[i]-v[i]),i) for i in bad]
            step,hit=min(steps)
            v=np.clip(v+step*(target-v),low,high)
            v[hit]=low[hit] if target[hit]<low[hit] else high[hit]
            free.remove(hit)
        else:
            raise ValueError('BVLS inner limit')
    raise ValueError('BVLS convergence limit')


def fill_interval(values,a,z,column,weight=1.):
    end=len(values)*DT
    a,z=max(0.,a),min(end,z)
    if z<=a:
        return
    lo=int(math.floor(a/DT))
    hi=min(len(values),int(math.ceil(z/DT)))
    left=np.arange(lo,hi)*DT
    values[lo:hi,column] += weight*np.maximum(0,np.minimum(z,left+DT)-np.maximum(a,left))/DT


def grid_episode(ep):
    n=int(math.ceil(ep['end_s']/DT))
    u=np.zeros((n,6))
    for a,z,field in ep['intervals']:
        fill_interval(u,a,z,field)
    events=[]
    for a,z in ep['owners']:
        events.extend(((a,1),(z,-1)))
    events.sort(key=lambda r:(r[0],r[1]))
    occupied=np.zeros((n,1));count=0;last=0.;pieces=[]
    for at,delta in events:
        if at>last:
            pieces.append((last,at,count>0))
            if count:
                fill_interval(occupied,last,at,0)
            last=at
        count+=delta
    if last<ep['end_s']:
        pieces.append((last,ep['end_s'],count>0))
        if count:
            fill_interval(occupied,last,ep['end_s'],0)
    # Exponential duty is an effective recent-work feature, not a claimed DVFS law.
    cpu=np.minimum(u[:,0]+u[:,1]+u[:,4],1.)
    decay=math.exp(-DT/5)
    q=np.zeros(n);state=0.
    for i in range(n):
        q[i]=cpu[i]+(state-cpu[i])*math.exp(-DT/10)
        state=cpu[i]+(state-cpu[i])*decay
    return dict(u=u,occupied=occupied[:,0],pieces=pieces,recent_cpu=q)


def tail_grid(base,tau):
    if tau==0:
        return base['occupied'].copy()
    result=np.zeros((len(base['u']),1));h=0.
    for a,z,busy in base['pieces']:
        if busy:
            fill_interval(result,a,z,0)
            h=1.
        elif h:
            lo=max(0,int(math.floor(a/DT)));hi=min(len(result),int(math.ceil(z/DT)))
            left=np.arange(lo,hi)*DT;start=np.maximum(a,left);end=np.minimum(z,left+DT)
            result[lo:hi,0]+=h*tau*(np.exp(-(start-a)/tau)-np.exp(-(end-a)/tau))/DT
            h*=math.exp(-(z-a)/tau)
    return result[:,0]


def physical_grid(ep,base,setting):
    p=ep['public'];n=len(base['u']);t=(np.arange(n)+.5)*DT
    result=np.zeros((n,11))
    result[:,0]=p['median5_w'];result[:,1]=p['median10_w'];result[:,2]=p['mean30_w']
    result[:,3]=max(p['mean30_w']-p['median10_w'],0)*np.exp(-t/30)
    result[:,4:10]=base['u']
    result[:,4:6]/=1+setting['alpha']*base['recent_cpu'][:,None]
    result[:,10]=tail_grid(base,setting['tail_s'])
    return result


def integral_matrix(grid,times,prefix=None):
    values=np.asarray(times,float)
    if prefix is None:
        prefix=np.vstack((np.zeros((1,grid.shape[1])),np.cumsum(grid,axis=0)*DT))
    position=np.clip(values/DT,0,len(grid))
    lo=np.minimum(np.floor(position).astype(int),len(grid))
    fraction=position-lo
    result=prefix[lo].copy()
    mask=lo<len(grid)
    result[mask]+=grid[lo[mask]]*(fraction[mask]*DT)[:,None]
    # Before-boundary cache values only use the completed past baseline vector.
    neg=values<0
    if neg.any():
        past=np.zeros(grid.shape[1]);past[:3]=grid[0,:3]
        result[neg]=values[neg,None]*past
    return result


def instantaneous_matrix(grid,times):
    values=np.asarray(times,float)
    idx=np.clip(np.floor(values/DT).astype(int),0,len(grid)-1)
    result=grid[idx].copy()
    result[values<0,3:]=0
    return result


def observer_matrix(ep,grid,times,setting,prefix=None):
    times=np.asarray(times,float)
    query=times-setting['lag_s']
    if setting['cache_s']:
        period=setting['cache_s']
        query=np.floor((ep['start_s']+query)/period)*period-ep['start_s']
    width=setting['window_s']
    if width:
        return (integral_matrix(grid,query,prefix)-integral_matrix(grid,query-width,prefix))/width
    return instantaneous_matrix(grid,query)


def observed_integral_vector(times,matrix,left,right):
    t=np.asarray(times,float);x=np.asarray(matrix,float)
    if t[0]>left or t[-1]<right:
        raise ValueError('observed energy coverage')
    inside=(t>left)&(t<right)
    tt=np.r_[left,t[inside],right]
    columns=[np.r_[np.interp(left,t,x[:,i]),x[inside,i],np.interp(right,t,x[:,i])] for i in range(x.shape[1])]
    xx=np.stack(columns,axis=1)
    return np.sum(np.diff(tt)[:,None]*(xx[1:]+xx[:-1])/2,axis=0)


def heating_grid(power_components,beta):
    n,d=power_components.shape
    result=np.zeros((n+1,d));decay=math.exp(-beta*DT)
    for i in range(n):
        result[i+1]=decay*result[i]+(1-decay)*power_components[i]
    return result


def at_heat(grid,times):
    position=np.clip(np.asarray(times,float)/DT,0,len(grid)-1)
    lo=np.floor(position).astype(int);hi=np.minimum(lo+1,len(grid)-1);fraction=position-lo
    return grid[lo]*(1-fraction[:,None])+grid[hi]*fraction[:,None]


def history_vector(public,sensor,extended=True):
    other='SKIN' if sensor=='AP' else 'AP';t0=public['initial_c'][sensor]
    v=[1.,(t0-30)/5,(public['initial_c'][other]-t0)/5,(public['battery_c']-t0)/5]
    if extended:
        v += [np.clip(public['slopes20'][sensor]*20/5,-2,2),np.clip(public['slopes20'][other]*20/5,-2,2),
              public['ranges30'][sensor]/10,(public['mean30_w']-public['median10_w'])/3,
              public['past_cpu_duty600'],public['past_accelerator_duty600'],(public['resident_count']-4)/2]
    return np.asarray(v,float)


def thermal_matrix(ep,sensor,heat,times,setting):
    times=np.asarray(times,float);f=history_vector(ep['public'],sensor,setting['extended'])
    initial=np.column_stack(((1-np.exp(-setting['initial_fast']*times))[:,None]*f,
                             (1-np.exp(-setting['initial_slow']*times))[:,None]*f))
    return np.column_stack((at_heat(heat,np.maximum(0,times-setting['delay_s'])),initial))


def thermal_predict(ep,sensor,heat,times,setting,coefficients):
    f=history_vector(ep['public'],sensor,setting['extended']);d=heat.shape[1];k=len(f)
    c=np.asarray(coefficients)
    fast=float(np.clip(f@c[d:d+k],-8,8));slow=float(np.clip(f@c[d+k:d+2*k],-8,8))
    times=np.asarray(times,float)
    return ep['public']['initial_c'][sensor]+at_heat(heat,np.maximum(0,times-setting['delay_s']))@c[:d]+fast*(1-np.exp(-setting['initial_fast']*times))+slow*(1-np.exp(-setting['initial_slow']*times))
