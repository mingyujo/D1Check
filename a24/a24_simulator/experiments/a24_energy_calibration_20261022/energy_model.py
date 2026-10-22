"""Exact conditional state occupancy response. No sensor target access in prediction."""
import math
import numpy as np
STATES=['C_CPU','C_GPU','D_CPU','C_GPU+D_CPU']
SETTINGS=[{'tau_s':t,'offset_enabled':o} for t in [0.,.9,10.,30.] for o in [False,True]]
SCHEMA='A24-causal-prebaseline-energy-v1'
def schedule(c):
    events=[]
    for o in c['owners']:
        events.extend([(o['start_s'],1,o['id'],o),(o['end_s'],0,o['id'],o)])
    events.sort(key=lambda e:(e[0],e[1],e[2]));active={};segments=[];prev=0.;i=0
    while i<len(events):
        t=events[i][0]
        if t>prev:
            state='+'.join(sorted(v['task']+'_'+v['route'] for v in active.values())) or 'idle'
            if state!='idle' and state not in STATES:raise ValueError('Unsupported state '+state)
            if segments and segments[-1]['state']==state:segments[-1]['end_s']=t
            else:segments.append({'start_s':prev,'end_s':t,'state':state})
        while i<len(events) and abs(events[i][0]-t)<1e-12:
            _,kind,k,o=events[i];i+=1
            if kind:
                assert k not in active;active[k]=o
            else:assert k in active;active.pop(k)
        prev=t
    assert not active
    if prev<c['activity_end_s']:
        if segments and segments[-1]['state']=='idle':segments[-1]['end_s']=c['activity_end_s']
        else:segments.append({'start_s':prev,'end_s':c['activity_end_s'],'state':'idle'})
    if not segments:segments=[{'start_s':0.,'end_s':c['activity_end_s'],'state':'idle'}]
    assert all(s['state']=='idle' for s in segments if s['start_s']<35-1e-8),'Non-idle prehistory needs explicit initial state'
    return segments
def prefix(c,times,tau):
    """Integral from35 to query of four zero-initialized filtered indicators."""
    q=np.asarray(times,dtype=float);assert np.min(q)>=35-1e-9
    out=np.zeros((len(q),4))
    for j,state in enumerate(STATES):
        ss=[s for s in c['segments'] if s['state']==state and s['end_s']>35]
        if not ss:continue
        a=np.array([max(35,s['start_s']) for s in ss]);b=np.array([s['end_s'] for s in ss])
        x=np.maximum(0,q[:,None]-a);y=np.maximum(0,q[:,None]-b)
        if tau:
            out[:,j]=np.sum((x+tau*np.expm1(-x/tau))-(y+tau*np.expm1(-y/tau)),axis=1)
        else:out[:,j]=np.sum(x-y,axis=1)
    return out
def design(c,windows,tau):
    edges=sorted({t for w in windows for t in w});p=prefix(c,edges,tau);lookup={t:p[i] for i,t in enumerate(edges)}
    return np.array([[1.,*((lookup[b]-lookup[a])/(b-a)).tolist()] for a,b in windows])
def predict_mean(c,windows,m):
    if m.get('constant_only'):return np.ones(len(windows))
    return 1+design(c,windows,m['tau_s'])@np.asarray(m['coefficients'])
def energy(c,windows,m):return predict_mean(c,windows,m)*np.array([b-a for a,b in windows])*c['pre_power']
def constant():return {'schema':SCHEMA,'constant_only':True,'coefficients':[0.]*5,'tau_s':0.,'offset_enabled':False,'training_sessions':[],'training_groups':[]}
