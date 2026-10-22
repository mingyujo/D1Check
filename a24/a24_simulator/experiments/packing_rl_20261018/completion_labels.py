"""Completion total energy aligned with the 1.32% witness accounting window."""
import bisect,numpy as np
from common import B
def labels(result,frames,case,physics,metrics,H,reference,joint):
    costs,original=B.repaired_labels(result,frames,case,physics,metrics,H)
    finish=max(q['available_ns'] for q in result['requests']) if all(q['available_ns'] is not None for q in result['requests']) else round(case['drain_stop_s']*1e9)
    E0=reference['completion_total_J_proxy'];Q0=(reference['mean_AP_c']-physics.c.idle_c)*(H/1e9-35.)
    if E0<=0 or Q0<=0:raise ValueError('Positive frozen reference normalizers')
    trace=result['trace'];starts=[t['start_ns'] for t in trace];energy=[0.];heat=[0.]
    for t in trace:
        energy.append(energy[-1]+t['increment']);heat.append(heat[-1]+t['temperature_area']-physics.c.idle_c*t['dt'])
    def prefix(t):
        if t<=35_000_000_000:return 0.,0.
        i=bisect.bisect_right(starts,t)-1
        if t>=trace[-1]['end_ns']:return energy[-1],heat[-1]
        _,part=physics.transition(trace[i]['state'],trace[i]['active'],(t-trace[i]['start_ns'])/1e9)
        return energy[i]+part['increment'],heat[i]+part['temperature_area']-physics.c.idle_c*(t-trace[i]['start_ns'])/1e9
    costs=np.array(costs,dtype=np.float64,copy=True);costs[:,1]=0.;previous=0.;records=[]
    for i,f in enumerate(frames):
        end=frames[i+1]['time_ns'] if i+1<len(frames) else max(finish,H);e_end=min(end,finish);q_end=min(end,H)
        E=prefix(e_end)[0]+physics.c.baseline*(e_end/1e9-35.);Q=max(0.,prefix(q_end)[1]);value=max(E/E0,Q/Q0) if joint else E/E0
        costs[i,0]=2*(value-previous);records.append(dict(end_ns=end,completion_energy_prefix_J_proxy=E,heat_excess_prefix_Cs=Q,value=value,cost0=float(costs[i,0])));previous=value
    return costs,dict(reward_kind='PACKING_JOINT_COMPLETION' if joint else 'PACKING_COMPLETION_ENERGY',cost_sum=costs.sum(0).tolist(),prefix_records=records,finish_ns=finish,reference_end_ns=H,reference=reference,reference_heat_excess_Cs=Q0,original_repaired_cost_sum=original['cost_sum'],deadline_costs_unchanged=True,energy_includes_completion_baseline=True,common_window_energy_still_reported=True)
