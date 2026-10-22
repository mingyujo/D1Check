"""Nonnegative finite thermal impulse response. Inputs are past occupancy only."""
import importlib.util,math
from pathlib import Path
import numpy as np
s=importlib.util.spec_from_file_location('_kernel_previous',Path(__file__).resolve().parents[1]/'a24_thermal_direction_v2_20261021/thermal_model.py');previous=importlib.util.module_from_spec(s);s.loader.exec_module(previous)
segments,convolution,window_pairs,STATES=previous.segments,previous.convolution,previous.window_pairs,previous.STATES
SCHEMA='A24-nonnegative-finite-thermal-response-v1'
EDGES=[0.,5.,10.,20.,40.,80.,160.,320.,640.,1280.,2560.]
COARSE=[0.,20.,80.,320.,1280.,2560.]
def matrix(case,conv,model):
    if model['schema']!=SCHEMA:return previous.matrix(case,conv,model['tau_fast_s'],model['tau_slow_s'],model['transport_s'])
    edges=model['age_edges_s'];tf,ts=model['tau_fast_s'],model['tau_slow_s'];t=np.array([o['t'] for o in case['observations']]);s=t-35.;out=np.zeros((len(t),len(edges)-1,4))
    for row in segments(case):
        if row['state'] is None:continue
        k=STATES.index(row['state'])
        for j,(a,b) in enumerate(zip(edges,edges[1:])):out[:,j,k]+=np.maximum(0.,np.minimum(row['end_s'],t-a)-np.maximum(row['start_s'],t-b))/(b-a)
    context=-(case['initial_c']-28)*(-np.expm1(-s/ts)) if model.get('context_enabled',True) else np.zeros(len(s))
    return np.column_stack((-np.expm1(-s/ts),case['pre_slope_C_s']*60*(np.exp(-s/ts)-np.exp(-s/tf)),context,out.reshape(len(t),-1)))
def prior_coefficients(old,edges):
    b=old['coefficients'];tf=old['tau_fast_s'];ts=old['tau_slow_s'];lag=old['transport_s'];out=[b[0],b[1],0.]
    def integral(tau,a,z):
        if not lag:return math.exp(-a/tau)-math.exp(-z/tau)
        return (tau*(math.exp(-a/tau)-math.exp(-z/tau))-lag*(math.exp(-a/lag)-math.exp(-z/lag)))/(tau-lag)
    for a,z in zip(edges,edges[1:]):out.extend(b[2+k]*integral(tf,a,z)+b[6+k]*integral(ts,a,z) for k in range(4))
    return np.array(out)
def direct(case,model):
    if model['schema']!=SCHEMA:return previous.direct(case,model)
    b=model['coefficients'];tf,ts=model['tau_fast_s'],model['tau_slow_s'];edges=model['age_edges_s'];segs=segments(case);out=[]
    for obs in case['observations']:
        t=obs['t'];s=t-35;v=case['initial_c']+(b[0]-b[2]*(case['initial_c']-28))*(-math.expm1(-s/ts))+b[1]*case['pre_slope_C_s']*60*(math.exp(-s/ts)-math.exp(-s/tf))
        for row in segs:
            if row['state'] is None:continue
            k=STATES.index(row['state'])
            for j,(a,z) in enumerate(zip(edges,edges[1:])):
                # Independent ramp formulation of an interval's convolution.
                ramp=lambda x:max(0.,x)
                v+=b[3+4*j+k]*(ramp(t-row['start_s']-a)-ramp(t-row['end_s']-a)-ramp(t-row['start_s']-z)+ramp(t-row['end_s']-z))/(z-a)
        out.append(v)
    return out
def integrated(case,model,end):
    if model['schema']!=SCHEMA:return previous.integrated(case,model,end)
    b=model['coefficients'];tf,ts=model['tau_fast_s'],model['tau_slow_s'];edges=model['age_edges_s'];s=end-35
    v=case['initial_c']*s+(b[0]-b[2]*(case['initial_c']-28))*(s-ts*(-math.expm1(-s/ts)))+b[1]*case['pre_slope_C_s']*60*(ts*(-math.expm1(-s/ts))-tf*(-math.expm1(-s/tf)))
    for row in segments(case):
        if row['state'] is None:continue
        k=STATES.index(row['state'])
        for j,(a,z) in enumerate(zip(edges,edges[1:])):
            area=lambda x:.5*max(0.,x)**2
            v+=b[3+4*j+k]*(area(end-row['start_s']-a)-area(end-row['end_s']-a)-area(end-row['start_s']-z)+area(end-row['end_s']-z))/(z-a)
    return v
