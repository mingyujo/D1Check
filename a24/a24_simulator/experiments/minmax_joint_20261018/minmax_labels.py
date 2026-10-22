"""Joint worst-normalized energy/mean-heat reward; same soft deadline costs."""
import bisect
import numpy as np
from common import B

def scalar(energy,heat_excess,reference_energy,reference_heat):
    if reference_energy<=0 or reference_heat<=0:raise ValueError('Positive reference costs required')
    return max(energy/reference_energy,heat_excess/reference_heat)

def labels(result,frames,case,physics,metrics,reference_end_ns,reference):
    costs,original=B.repaired_labels(result,frames,case,physics,metrics,reference_end_ns)
    finish=max(q['available_ns'] for q in result['requests']) if all(q['available_ns'] is not None for q in result['requests']) else round(case['drain_stop_s']*1e9)
    duration=reference_end_ns/1e9-35.;E0=reference['common_increment_J_proxy'];Q0=(reference['mean_AP_c']-physics.c.idle_c)*duration
    trace=result['trace'];starts=[t['start_ns'] for t in trace];energy=[0.];heat=[0.]
    for t in trace:
        _,terms=physics.transition(t['state'],t['active'],t['dt'])
        energy.append(energy[-1]+terms['increment'])
        heat.append(heat[-1]+terms['temperature_area']-physics.c.idle_c*t['dt'])
    def prefix(t):
        if t<=35_000_000_000:return 0.,0.
        i=bisect.bisect_right(starts,t)-1
        if i<0:return 0.,0.
        if t>=trace[-1]['end_ns']:return energy[-1],heat[-1]
        dt=(t-trace[i]['start_ns'])/1e9
        _,part=physics.transition(trace[i]['state'],trace[i]['active'],dt)
        return energy[i]+part['increment'],heat[i]+part['temperature_area']-physics.c.idle_c*dt
    records=[];previous=0.;costs=np.array(costs,dtype=np.float64,copy=True);costs[:,1]=0.
    for i,f in enumerate(frames):
        end=frames[i+1]['time_ns'] if i+1<len(frames) else max(finish,reference_end_ns)
        E=prefix(min(end,reference_end_ns))[0];Q=max(0.,prefix(min(end,reference_end_ns))[1]);value=scalar(E,Q,E0,Q0)
        costs[i,0]=2*(value-previous);records.append(dict(end_ns=end,common_increment_prefix_J_proxy=E,heat_excess_prefix_Cs=Q,normalized_worst=value,cost0=float(costs[i,0])));previous=value
    audit=dict(cost_sum=costs.sum(axis=0).tolist(),reward_kind='MINMAX_JOINT_V1',reference=reference,reference_end_ns=reference_end_ns,reference_heat_excess_Cs=Q0,prefix_records=records,original_repaired_cost_sum=original['cost_sum'],new_NN_observation_features=False,deadline_costs_unchanged=True,explanation='Weights .5*cost0+.5*cost1 equal max(common_increment/common_increment_EDF, heat_excess/heat_excess_EDF); other deadline costs unchanged')
    return costs,audit
