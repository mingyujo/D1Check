"""Causal stable-filter residual inputs; no observed future AP or power access."""
from pathlib import Path
import sys,math
import numpy as np
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'capacity_power_v1'))
sys.path.insert(0,str(HERE.parent/'pipeline_thermal_v1'))
from power import steps
from basis import thermal_basis
TAUS=np.array([10.,60.,160.,320.]);TINDEX={v:i for i,v in enumerate(TAUS)}

def activity_filters(step,times,anchor,start=-30.):
    times=np.asarray(times,float);assert times[0]>=anchor>=start and np.all(np.diff(times)>0)
    events={t:np.asarray(v,float) for t,v in step};grid=np.unique(np.r_[start,anchor,times,[t for t in events if t<=times[-1]]])
    state=np.zeros((4,5));v=np.zeros(5);prev=start;out={}
    for t in grid:
        dt=t-prev
        if prev>=anchor and dt>0:
            a=np.exp(-dt/TAUS)[:,None];state=a*state+(1-a)*v
        if float(t) in query_set(times):out[float(t)]=state.copy()
        if t in events:v=events[t]
        prev=t
    return np.stack([out[float(t)] for t in times])

def query_set(times):
    # Small helper kept pure; preparation supplies arrays on measured query times.
    return set(float(t) for t in times)

def prepare_input(times,anchor,AP0,skin,BAT,slope,baseline,intervals):
    t=np.asarray(times,float);step=steps(intervals)
    act=activity_filters(step,t,anchor)
    B=thermal_basis(step,t,baseline,anchor,TAUS)
    age=t-anchor;ctx=np.array([1.,(AP0-skin)/10,(BAT-skin)/10,slope*10,baseline])
    drift=np.concatenate([(1-np.exp(-age/tau))[:,None]*ctx for tau in [10.,160.,320.]],axis=1)
    return dict(times=t,anchor=anchor,AP0=AP0,skin=skin,baseline=baseline,B=B,activity=act.reshape(len(t),20),drift=drift)

def design(entry,power_model,thermal_model):
    t=entry['times'];age=t-entry['anchor'];c=np.asarray(power_model['coef'])/np.asarray(power_model['scale'])
    heat=np.einsum('ntf,f->nt',entry['B'],c)-entry['baseline']*(1-np.exp(-age[:,None]/TAUS))
    m=thermal_model;ef=np.exp(-age/m['tau_fast_s']);es=np.exp(-age/m['tau_slow_s']);idle=entry['skin']+m['delta_C']
    base=idle+(entry['AP0']-idle)*(m['w_fast']*ef+(1-m['w_fast'])*es)+m['gain_fast']*heat[:,TINDEX[m['tau_fast_s']]]+m['gain_slow']*heat[:,TINDEX[m['tau_slow_s']]]
    X=np.column_stack((entry['activity'],heat,entry['drift']))
    assert X.shape==(len(t),39) and np.isfinite(X).all() and np.isfinite(base).all()
    return base,X

def predict(entry,power_model,thermal_model,correction):
    base,X=design(entry,power_model,thermal_model)
    return base+(X/np.asarray(correction['scale']))@np.asarray(correction['coef'])

def interpolate(times,values,query):
    values=np.asarray(values);query=np.asarray(query)
    if values.ndim==1:return np.interp(query,times,values)
    return np.column_stack([np.interp(query,times,values[:,j]) for j in range(values.shape[1])])
