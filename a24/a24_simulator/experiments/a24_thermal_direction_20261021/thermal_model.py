"""Continuous two-state heat model plus a causal AP response state."""
import importlib.util,math
from pathlib import Path
import numpy as np
spec=importlib.util.spec_from_file_location('_a24_thermal_v1_core',Path(__file__).resolve().parents[1]/'a24_thermal_calibration_20261021/thermal_model.py')
core=importlib.util.module_from_spec(spec);spec.loader.exec_module(core)
segments,convolution,window_pairs,STATES=core.segments,core.convolution,core.window_pairs,core.STATES

def matrix(case,conv,fast,slow,transport):
    elapsed=np.array([o['t']-35 for o in case['observations']],float);ef=np.exp(-elapsed/fast);es=np.exp(-elapsed/slow)
    def heat(tau):return conv[tau] if not transport else (tau*conv[tau]-transport*conv[transport])/(tau-transport)
    return np.column_stack((-np.expm1(-elapsed/slow),case['pre_slope_C_s']*60*(es-ef),heat(fast),heat(slow)))

def direct(case,model):
    b=model['coefficients'];tf=model['tau_fast_s'];ts=model['tau_slow_s'];lag=model['transport_s'];segs=segments(case);values=[]
    for obs in case['observations']:
        t=obs['t'];s=t-35;v=case['initial_c']+b[0]*(-math.expm1(-s/ts))+b[1]*case['pre_slope_C_s']*60*(math.exp(-s/ts)-math.exp(-s/tf))
        for row in segs:
            if row['state'] is None or t<=row['start_s']:continue
            k=STATES.index(row['state']);duration=min(t,row['end_s'])-row['start_s'];age=max(0,t-row['end_s'])
            def h(tau):return math.exp(-age/tau)*(-math.expm1(-duration/tau))
            for tau,g in [(tf,b[2+k]),(ts,b[6+k])]:v+=g*(h(tau) if not lag else (tau*h(tau)-lag*h(lag))/(tau-lag))
        values.append(v)
    return values

def integrated(case,model,end):
    tf=model['tau_fast_s'];ts=model['tau_slow_s'];lag=model['transport_s'];b=model['coefficients'];s=end-35
    value=case['initial_c']*s+b[0]*(s-ts*(-math.expm1(-s/ts)))+b[1]*case['pre_slope_C_s']*60*(ts*(-math.expm1(-s/ts))-tf*(-math.expm1(-s/tf)))
    for row in segments(case):
        if row['state'] is None or end<=row['start_s']:continue
        k=STATES.index(row['state']);duration=min(end,row['end_s'])-row['start_s'];age=max(0,end-row['end_s'])
        def area(tau):
            one=-math.expm1(-duration/tau)
            return duration-tau*one+one*tau*(-math.expm1(-age/tau))
        for tau,g in [(tf,b[2+k]),(ts,b[6+k])]:value+=g*(area(tau) if not lag else (tau*area(tau)-lag*area(lag))/(tau-lag))
    return value
