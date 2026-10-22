"""Load-conditioned effective thermal relaxation, causal to the current owners."""
import importlib.util,math
from pathlib import Path
import numpy as np
P=Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location('_mode_tail',P/'a24_thermal_tail_20261022/thermal_model.py');previous=importlib.util.module_from_spec(s);s.loader.exec_module(previous)
segments,convolution,window_pairs,STATES=previous.segments,previous.convolution,previous.window_pairs,previous.STATES
SCHEMA='A24-load-conditioned-two-thermal-states-v1'

def slow_basis(case,slow,lag,ratio):
    """Vector basis propagation: coefficients remain linear, schedule changes tau."""
    segs=segments(case);core=np.zeros(4);sensor=np.zeros(4);t=35.;k=0;out=[]
    for obs in case['observations']:
        target=obs['t']
        while t<target-1e-11:
            while k<len(segs)-1 and segs[k]['end_s']<=t+1e-11:k+=1
            row=segs[k];end=min(target,row['end_s']);dt=end-t;assert dt>0
            u=np.zeros(4)
            if row['state'] is not None:u[STATES.index(row['state'])]=1.
            tau=slow*(ratio if row['state'] is None else 1.);e=math.exp(-dt/tau);nextcore=u+(core-u)*e
            if not lag:sensor=nextcore.copy()
            else:
                q=math.exp(-dt/lag)
                if abs(tau-lag)<1e-9:sensor=u+(sensor-u)*q+(core-u)*(dt/tau)*e
                else:sensor=u+(sensor-u)*q+(core-u)*tau/(tau-lag)*(e-q)
            core=nextcore;t=end
        out.append(sensor.copy())
    return np.array(out)

def matrix(case,conv,model):
    if model['schema']!=SCHEMA:return previous.matrix(case,conv,model)
    tf,ts,lag=model['tau_fast_s'],model['tau_slow_s'],model['transport_s'];elapsed=np.array([o['t']-35 for o in case['observations']]);ef=np.exp(-elapsed/tf);es=np.exp(-elapsed/ts)
    heat=conv[tf] if not lag else (tf*conv[tf]-lag*conv[lag])/(tf-lag)
    context=-(case['initial_c']-28)*(-np.expm1(-elapsed/ts)) if model.get('context_enabled',True) else np.zeros(len(elapsed))
    return np.column_stack((-np.expm1(-elapsed/ts),case['pre_slope_C_s']*60*(es-ef),context,heat,slow_basis(case,ts,lag,model['idle_tau_ratio'])))

def pair(core,sensor,u,tau,lag,dt):
    """Scalar independent state and area; also covers lag=0 and equal taus."""
    e=math.exp(-dt/tau);one=-math.expm1(-dt/tau);n=u+(core-u)*e
    if not lag:return n,n,core*tau*one+u*(dt-tau*one)
    q=math.exp(-dt/lag);oq=-math.expm1(-dt/lag)
    if abs(tau-lag)<1e-9:return n,u+(sensor-u)*q+(core-u)*(dt/tau)*e,u*dt+(sensor-u)*tau*one+(core-u)*tau*(1-(1+dt/tau)*e)
    k=(core-u)*tau/(tau-lag)
    return n,u+(sensor-u)*q+k*(e-q),u*dt+(sensor-u)*lag*oq+k*(tau*one-lag*oq)

def scalar_replay(case,model):
    b=model['coefficients'];tf=model['tau_fast_s'];ts=model['tau_slow_s'];lag=model['transport_s'];bg=b[0]-b[2]*(case['initial_c']-28);segs=segments(case);t=35.;k=0;f=sf=z=sz=area=0.;out=[]
    for obs in case['observations']:
        target=obs['t']
        while t<target-1e-11:
            while k<len(segs)-1 and segs[k]['end_s']<=t+1e-11:k+=1
            row=segs[k];end=min(target,row['end_s']);dt=end-t;s=t-35;state=row['state'];j=STATES.index(state) if state is not None else None
            f,sf,af=pair(f,sf,b[3+j] if j is not None else 0.,tf,lag,dt);z,sz,az=pair(z,sz,b[7+j] if j is not None else 0.,ts*(model['idle_tau_ratio'] if j is None else 1.),lag,dt)
            os=-math.expm1(-dt/ts);of=-math.expm1(-dt/tf);es=math.exp(-s/ts);ef=math.exp(-s/tf)
            area+=case['initial_c']*dt+bg*(dt-ts*es*os)+b[1]*case['pre_slope_C_s']*60*(ts*es*os-tf*ef*of)+af+az;t=end
        s=target-35;out.append(case['initial_c']+bg*(-math.expm1(-s/ts))+b[1]*case['pre_slope_C_s']*60*(math.exp(-s/ts)-math.exp(-s/tf))+sf+sz)
    return out,area
def direct(case,model):return scalar_replay(case,model)[0] if model['schema']==SCHEMA else previous.direct(case,model)
def integrated(case,model,end):
    if model['schema']!=SCHEMA:return previous.integrated(case,model,end)
    temp=dict(case);temp['observations']=[o for o in case['observations'] if o['t']<end]+[{'t':end}];return scalar_replay(temp,model)[1]
