"""Causal thermal spectrum with initial-state recovery. No fitting on import."""
import importlib.util,math
from pathlib import Path
import numpy as np
P=Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location('_tail_previous',P/'a24_thermal_direction_v2_20261021/thermal_model.py');previous=importlib.util.module_from_spec(s);s.loader.exec_module(previous)
segments,convolution,window_pairs,STATES=previous.segments,previous.convolution,previous.window_pairs,previous.STATES

def matrix(case,conv,model):
    tf,ts,lag=model['tau_fast_s'],model['tau_slow_s'],model['transport_s']
    if model['schema']!='A24-initial-context-three-thermal-states-v1':return previous.matrix(case,conv,tf,ts,lag)
    elapsed=np.array([o['t']-35 for o in case['observations']]);ef=np.exp(-elapsed/tf);es=np.exp(-elapsed/ts)
    def heat(tau):return conv[tau] if not lag else (tau*conv[tau]-lag*conv[lag])/(tau-lag)
    mid=heat(model['tau_middle_s']) if model.get('middle_enabled',True) else np.zeros_like(conv[tf])
    context=-(case['initial_c']-28)*(-np.expm1(-elapsed/ts)) if model.get('context_enabled',True) else np.zeros(len(elapsed))
    return np.column_stack((-np.expm1(-elapsed/ts),case['pre_slope_C_s']*60*(es-ef),context,heat(tf),mid,heat(ts)))

def direct(case,model):
    if model['schema']!='A24-initial-context-three-thermal-states-v1':return previous.direct(case,model)
    b=model['coefficients'];tf=model['tau_fast_s'];ts=model['tau_slow_s'];lag=model['transport_s'];out=[];segs=segments(case)
    for o in case['observations']:
        t=o['t'];s=t-35;v=case['initial_c']+(b[0]-(case['initial_c']-28)*b[2])*(-math.expm1(-s/ts))+b[1]*case['pre_slope_C_s']*60*(math.exp(-s/ts)-math.exp(-s/tf))
        for row in segs:
            if row['state'] is None or t<=row['start_s']:continue
            k=STATES.index(row['state']);duration=min(t,row['end_s'])-row['start_s'];age=max(0,t-row['end_s'])
            def h(tau):return math.exp(-age/tau)*(-math.expm1(-duration/tau))
            for tau,offset in [(tf,3),(model['tau_middle_s'],7),(ts,11)]:
                v+=b[offset+k]*(h(tau) if not lag else (tau*h(tau)-lag*h(lag))/(tau-lag))
        out.append(v)
    return out

def integrated(case,model,end):
    if model['schema']!='A24-initial-context-three-thermal-states-v1':return previous.integrated(case,model,end)
    b=model['coefficients'];tf=model['tau_fast_s'];ts=model['tau_slow_s'];lag=model['transport_s'];s=end-35
    v=case['initial_c']*s+(b[0]-b[2]*(case['initial_c']-28))*(s-ts*(-math.expm1(-s/ts)))+b[1]*case['pre_slope_C_s']*60*(ts*(-math.expm1(-s/ts))-tf*(-math.expm1(-s/tf)))
    for row in segments(case):
        if row['state'] is None or end<=row['start_s']:continue
        k=STATES.index(row['state']);duration=min(end,row['end_s'])-row['start_s'];age=max(0,end-row['end_s'])
        def area(tau):
            one=-math.expm1(-duration/tau)
            return duration-tau*one+one*tau*(-math.expm1(-age/tau))
        for tau,offset in [(tf,3),(model['tau_middle_s'],7),(ts,11)]:v+=b[offset+k]*(area(tau) if not lag else (tau*area(tau)-lag*area(lag))/(tau-lag))
    return v
