"""Post-episode labels only; no online access to reference/future outcomes."""
import numpy as np
from tools import d1_atc_delta_targets as previous
from tools import d1_atc_repair_targets as original
from tools import d1_list_candidate_rl as native
END=120e9

def urgent_area(raw,t):
    qs=[q for q in raw['result']['ledger'] if q['priority']=='urgent']
    if not qs:raise ValueError('urgent denominator missing')
    return sum(max(0.,min(END,q['arrival_ns']+q['response_ns'] if 'response_ns' in q else END)-max(t,q['arrival_ns'])) for q in qs)/(len(qs)*1.5e9)

def future_tail(raw,t,threshold_ms):
    qs=[q for q in raw['result']['ledger'] if q['priority']=='urgent']
    if not qs:raise ValueError('urgent denominator missing')
    total=0.
    for q in qs:
        response=q['arrival_ns']+q['response_ns'] if 'response_ns' in q else END
        # Dense unresponded area beyond fixed threshold, only after current t.
        total+=max(0.,min(response,END)-max(t,q['arrival_ns']+threshold_ms*1e6))/(len(qs)*100e6)
    return total

def running_phi(raw,t,threshold_ms):
    observed=[q['response_ns']/1e6 for q in raw['result']['ledger'] if q['priority']=='urgent'
        and 'response_ns' in q and q['arrival_ns']+q['response_ns']<=min(t,END)]
    return max(0.,(native.rank95(observed)-threshold_ms)/100.) if observed else 0.

def targets(controller,raw,resident_baseline_j,arm,reference):
    if arm not in ('BASE_DELTA','URGENT_HOLD','TAIL_EXCESS'):raise ValueError('unregistered objective')
    if previous.signature(raw)!=previous.signature(reference):raise ValueError('teacher case differs')
    if reference['row']['completed']!=reference['row']['planned']:raise ValueError('reference incomplete')
    actual_q,ref_q=raw['row']['urgent_p95_ms'],reference['row']['urgent_p95_ms']
    if actual_q is None or ref_q is None:raise ValueError('P95 missing, no zero imputation')
    frames,costs,valid,_=original.targets(controller,raw,resident_baseline_j,'CAUSAL')
    steps=[s for s in controller.snapshots if 'model_error' not in s]
    for frame,step in zip(frames,steps):
        t=step['now_ns']
        ar,ae,ap=previous.trajectory_suffix(raw,t,controller.frozen)
        rr,ee,aa=previous.trajectory_suffix(reference,t,controller.frozen)
        frame['target'][0]=ar-rr-(0. if arm=='BASE_DELTA' else urgent_area(raw,t))
        frame['target'][1]=(ae-ee)/(1. if arm=='BASE_DELTA' else 10.)
        frame['target'][2]=(ap-aa)/.1
        frame['target'][9]=(max(0.,(actual_q-ref_q)/1500.) if arm=='BASE_DELTA' else
            max(0.,(actual_q-ref_q)/100.)-running_phi(raw,t,ref_q)+running_phi(reference,t,ref_q) if arm=='URGENT_HOLD' else
            future_tail(raw,t,ref_q)-future_tail(reference,t,ref_q))
        if not np.isfinite(frame['target']).all():raise ValueError('nonfinite target')
    costs=costs.copy();costs[0]=frames[0]['target'][1];costs[1]=frames[0]['target'][2];costs[8]=frames[0]['target'][9]
    returns=np.asarray([f['target'][0] for f in frames],dtype=np.float64)
    reward=np.concatenate((returns[:-1]-returns[1:],returns[-1:])).astype(np.float32)
    return frames,costs,valid,reward
