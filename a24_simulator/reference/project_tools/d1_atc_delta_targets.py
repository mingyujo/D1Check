"""Paired ATC post-episode control variates. Never imported by online policy."""
import numpy as np
from tools import d1_atc_repair_targets as original

END=120e9

def signature(raw):
    return [(q['id'],q['task'],q['priority'],q['ordinal'],q['arrival_ns'],q['deadline_offset_ns'],q['work_units']) for q in raw['result']['ledger']]

def trajectory_suffix(reference,t,frozen):
    ledger=reference['result']['ledger'];units=sum(q['work_units'] for q in ledger)
    ret=sum(q['work_units']/units for q in ledger if q['status']=='succeeded' and t<q['lane_available_ns']<=END)
    for q in ledger:
        reply=q['arrival_ns']+q['response_ns'] if 'response_ns' in q else END
        holding=max(0,min(reply,END)-max(t,q['arrival_ns']))
        ret-=q['work_units']*holding/(units*85e9)
    energy=sum(max(0,min(120.,s['end_s'])-max(t/1e9,s['start_s']))*frozen['energy_increment_w'].get(s['state'],0.) for s in reference['segments'])
    curve=[(time*1e9,value) for time,value in reference['curve'] if time<=120]
    if not curve or curve[0][0]!=35e9 or curve[-1][0]!=END:raise ValueError('reference APprefixcoverage')
    before=max(v for time,v in curve if time<=max(t,35e9));final=max(v for _,v in curve)
    return ret,energy,final-before

def targets(controller,raw,resident_baseline_j,arm,reference):
    if arm not in ('JP05_CAUSAL','JP05_DELTA','ATC_SCORE_DELTA'):raise ValueError('unknown09objective')
    if signature(raw)!=signature(reference):raise ValueError('teacher case differs')
    if reference['row']['completed']!=reference['row']['planned']:raise ValueError('reference unfinished; stop rather than treating cost unavailable as0')
    actual_q,reference_q=raw['row']['urgent_p95_ms'],reference['row']['urgent_p95_ms']
    if actual_q is None or reference_q is None:raise ValueError('P95 unavailable; no zero-imputation')
    frames,costs,valid,rewards=original.targets(controller,raw,resident_baseline_j,'CAUSAL')
    if arm=='JP05_CAUSAL':return frames,costs,valid,rewards
    p95_excess=max(0.,(actual_q-reference_q)/1500.)  #ms/1500ms;teacher-relative, not cap excess
    steps=[q for q in controller.snapshots if 'model_error' not in q]
    for frame,step in zip(frames,steps):
        ar,ae,ap=trajectory_suffix(raw,step['now_ns'],controller.frozen)
        rr,ee,aa=trajectory_suffix(reference,step['now_ns'],controller.frozen)
        frame['target'][0]=ar-rr
        frame['target'][1]=ae-ee                    # E1J instead of100J
        frame['target'][2]=(ap-aa)/.1               # AP0.1C instead of1C
        frame['target'][9]=p95_excess               # replace absoluteUholding channel
        if not np.isfinite(frame['target']).all():raise ValueError('nonfinite pairedtarget')
    ar,ae,ap=trajectory_suffix(raw,steps[0]['now_ns'],controller.frozen)
    rr,ee,aa=trajectory_suffix(reference,steps[0]['now_ns'],controller.frozen)
    costs=costs.copy();costs[0]=ae-ee;costs[1]=(ap-aa)/.1;costs[8]=p95_excess
    returns=np.asarray([f['target'][0] for f in frames],dtype=np.float64)
    delta_rewards=np.concatenate((returns[:-1]-returns[1:],returns[-1:])).astype(np.float32)
    return frames,costs,valid,delta_rewards
