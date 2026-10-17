"""Training labels only: completion energy, fixed reference mean heat and SLA.

The actual reference endpoint is never passed to the actor or its forecasts.
"""
from pathlib import Path
import importlib.util,math
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('learning_original_reward',ROOT/'experiments/coupled_345_20261017/rewards.py')
old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)

def labels(result,frames,case,physics,metrics,reference_end_ns):
    costs,audit=old.labels(result,frames,case,physics,metrics)
    costs[:,:2]=0.;n=case['n'];times=np.array([f['time_ns'] for f in frames]);c=physics.c
    def index(t):return max(0,min(len(frames)-1,int(np.searchsorted(times,t,side='right'))-1))
    drain=round(case['drain_stop_s']*1e9);H=int(reference_end_ns)
    if not 35e9<H<=drain:raise ValueError('Registered training reference endpoint')
    complete=all(q['available_ns'] is not None and q['available_ns']<=drain for q in result['requests'])
    finish=max(q['available_ns'] for q in result['requests']) if complete else drain
    energy=area=0.;peak=case['temperature_c']
    for t in result['trace']:
        a=t['start_ns'];b=t['end_ns']
        if a<35e9:continue
        for which,endpoint in ((0,finish),(1,H)):
            stop=min(b,endpoint)
            if stop<=a:continue
            dt=(stop-a)/1e9
            _,part=physics.transition(t['state'],t['active'],dt)
            if which==0:
                value=part['increment']+c.baseline*dt;energy+=value;costs[index(a),0]+=value/(n*.35)
            else:
                area+=part['temperature_area'];peak=max(peak,part['peak'])
                # initial26 implies passive26; retain general passive solution.
                left=(a/1e9-35);passive=c.idle_c*dt+(case['temperature_c']-c.idle_c)*c.thermal_tau_s*(math.exp(-left/c.thermal_tau_s)-math.exp(-(left+dt)/c.thermal_tau_s))
                costs[index(a),1]+=(part['temperature_area']-passive)/((H/1e9-35)*10.)
    costs[index(H),1]+=.1*max(0.,peak-32.)/5.
    unfinished=sum(q['available_ns'] is None or q['available_ns']>H for q in result['requests'])
    costs[index(H),4]+=unfinished/n
    expected_energy=energy/(n*.35)
    expected_heat=(area-c.idle_c*(H/1e9-35)-(case['temperature_c']-c.idle_c)*c.thermal_tau_s*(-math.expm1(-(H/1e9-35)/c.thermal_tau_s)))/((H/1e9-35)*10.)+.1*max(0.,peak-32.)/5.
    error=max(abs(costs[:,0].sum()-expected_energy),abs(costs[:,1].sum()-expected_heat))
    if error>1e-7 or not np.isfinite(costs).all():raise ValueError('Repaired label telescope')
    return costs,dict(original_audit=audit,cost_sum=costs.sum(0).tolist(),max_telescope_error=float(error),reference_end_ns=H,reference_is_trainer_label_only=True,completion_end_ns=finish,completion_defined=complete,completion_total_J_proxy=energy,reference_temperature_area=area,reference_peak_c=peak,unfinished_at_reference=unfinished,deadline_weights_retained=[8,4,30],future_labels_in_inputs=False)
