"""Two thermal states with causal contextual baseline. No import-time fitting."""
import math
import numpy as np

STATES=('C_CPU','C_GPU','D_CPU','C_GPU+D_CPU')

def segments(case):
    events=sorted([(o[k],kind,o['id'],o) for o in case['owners'] for k,kind in [('start_s',1),('end_s',0)]],key=lambda x:(x[0],x[1],x[2]))
    active={};i=0;t=35.;end=case['observations'][-1]['t'];out=[]
    while t<end-1e-10:
        while i<len(events) and events[i][0]<=t+1e-10:
            _,kind,key,owner=events[i];i+=1
            if kind:active[key]=owner
            else:active.pop(key,None)
        nxt=min(end,events[i][0] if i<len(events) else end)
        assert nxt>t
        labels=sorted(o['task']+'_'+o['route'] for o in active.values())
        state='+'.join(labels) if labels else None
        assert state is None or state in STATES,(case['session'],state)
        if out and out[-1]['state']==state and abs(out[-1]['end_s']-t)<1e-8:out[-1]['end_s']=nxt
        else:out.append({'start_s':t,'end_s':nxt,'state':state})
        t=nxt
    return out

def convolution(case,segs,tau):
    times=np.array([o['t'] for o in case['observations']],float);out=np.zeros((len(times),4))
    # Exact integral of each recorded constant state; no tick approximation.
    for row in segs:
        if row['state'] is None:continue
        i=STATES.index(row['state']);a=row['start_s'];b=row['end_s']
        # Stable expression avoids subtracting two nearly equal exponentials.
        duration=np.maximum(0.,np.minimum(times,b)-a)
        age=np.maximum(0.,times-b)
        out[:,i]+=np.exp(-age/tau)*(-np.expm1(-duration/tau))
    return out

def matrix(case,conv,fast,slow):
    elapsed=np.array([o['t']-35 for o in case['observations']],float)
    ef=np.exp(-elapsed/fast);es=np.exp(-elapsed/slow)
    return np.column_stack((-np.expm1(-elapsed/slow),case['pre_slope_C_s']*60*(es-ef),conv[fast],conv[slow]))

def window_pairs(obs,width=20):
    import bisect
    ts=[o['t'] for o in obs];pairs=[];i=0
    while i<len(ts)-1:
        j=bisect.bisect_left(ts,ts[i]+width,lo=i+1)
        if j>=len(ts):break
        if max(ts[k+1]-ts[k] for k in range(i,j))<=10:pairs.append((i,j))
        i=j
    return pairs

def direct(case,model):
    """Independent closed-form scalar evaluation, used in final audit."""
    segs=segments(case);coef=model['coefficients'];tf=model['tau_fast_s'];ts=model['tau_slow_s'];values=[]
    for obs in case['observations']:
        t=obs['t'];elapsed=t-35
        base=case['initial_c']+coef[0]*(-math.expm1(-elapsed/ts))+coef[1]*case['pre_slope_C_s']*60*(math.exp(-elapsed/ts)-math.exp(-elapsed/tf))
        for seg in segs:
            if seg['state'] is None or t<=seg['start_s']:continue
            j=STATES.index(seg['state']);duration=min(t,seg['end_s'])-seg['start_s'];age=max(0,t-seg['end_s'])
            base+=coef[2+j]*math.exp(-age/tf)*(-math.expm1(-duration/tf))+coef[6+j]*math.exp(-age/ts)*(-math.expm1(-duration/ts))
        values.append(base)
    return values
