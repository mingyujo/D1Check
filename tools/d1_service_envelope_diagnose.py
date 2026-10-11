"""Stored-forecast guard attribution only; new simulation/training zero."""
import gzip,json
from collections import Counter
from tools import d1_service_envelope_run as d

def components(f,known):
    late={k:max(0.,v-d.x.r.c.due(known[k])/1e9) for k,v in f['responses'].items()}
    return (f['urgent_misses'],f['normal_misses'],sum(v for k,v in late.items() if known[k]['priority']=='urgent'),sum(v for k,v in late.items() if known[k]['priority']=='normal'))
def run():
    d.check();inputs=d.read(d.LOCAL/'inputs.json');counts=Counter();witnesses=[];mismatch=[]
    for case in inputs['confirmation']:
        item=json.loads(gzip.decompress((d.LOCAL/'items'/f'confirmation_JointList_{case["condition"]:02d}.json.gz').read_bytes()))
        known={q['id']:q for q in case['tickets']}
        for snap in item['snapshots']:
            refs=snap['forecasts'][0]
            for i,fs in enumerate(snap['forecasts']):
                if not snap['physical_mask'][i] or not all(f['valid'] and ref['valid'] for f,ref in zip(fs,refs)):continue
                safe=all(f['global_peak_ap_c']<=ref['global_peak_ap_c']+1e-9 and f['remaining_increment_j']<=ref['remaining_increment_j']+1e-9 for f,ref in zip(fs,refs))
                strict=any(f['global_peak_ap_c']<ref['global_peak_ap_c']-1e-9 or f['remaining_increment_j']<ref['remaining_increment_j']-1e-9 for f,ref in zip(fs,refs))
                if not (safe and strict):continue
                counts['physical_known_cost_improver_slots']+=1
                flags=dict(miss_lateness=not all(components(f,known)==components(ref,known) for f,ref in zip(fs,refs)),urgentP95=not all((f['urgent_p95_ms'] or 0)<=(ref['urgent_p95_ms'] or 0)+1e-9 for f,ref in zip(fs,refs)),CPU_only_response=any(f['responses'][k]>ref['responses'][k]+1e-9 for f,ref in zip(fs,refs) for k in f['responses'] if len(d.x.r.p.backends(known[k]))==1))
                reason=snap['admissions'][i];early=reason not in ('Joint_service_envelope','Joint_service_envelope_rejected','JointList_reference')
                flags['fixed_wait_or_window_guard']=early
                active=tuple(k for k,v in flags.items() if v);counts['intersection_'+('+'.join(active) or 'none')]+=1
                for k,v in flags.items():counts['violates_'+k]+=v
                counts['admitted_cost_improver_slots']+=bool(snap['mask'][i])
                if active==('CPU_only_response',):
                    counts['CPU_only_alone_removes_cost_improver']+=1
                    if len(witnesses)<12:
                        keys=('urgent_misses','normal_misses','urgent_p95_ms','lane_end_s','global_peak_ap_c','peak_ap_c','remaining_increment_j','responses')
                        future=[q['id'] for q in case['tickets'] if q['arrival_ns']>snap['now_ns']]
                        observed_late=[q['id'] for q in item['result']['ledger'] if q.get('output_ready_ns' if q['priority']=='urgent' else 'persist_complete_ns',float('inf'))<=snap['now_ns'] and q.get('late_success')]
                        witnesses.append(dict(condition=case['condition'],arrival_seed=case['seed'],family=case['family'],realization_context=case['context'],now_ns=snap['now_ns'],slot=i,action=snap['actions'][i],reason=reason,physical=True,flags=flags,current_pending_ids=sorted(fs[0]['responses']),remaining_unarrived_requests=len(future),all_current_pending_deadlines_predicted_met=all(f['urgent_misses']==f['normal_misses']==0 for f in fs),observed_completed_late_count=len(observed_late),L0_individual_urgent_guard_removed=True,reference=[{k:f[k] for k in keys} for f in refs],alternative=[{k:f[k] for k in keys} for f in fs],current_queued_due_ns={k:d.x.r.c.due(known[k]) for k in fs[0]['responses']},original_state=snap['state'],original_candidates=snap['candidates'],physical_mask=snap['physical_mask'],performance_mask=snap['mask'],future_trace_service_guaranteed=False))
                if not active and not snap['mask'][i]:mismatch.append(dict(condition=case['condition'],now_ns=snap['now_ns'],slot=i,reason=reason))
    out=dict(status='completed_stored_forecast_diagnosis',counts=dict(counts),CPU_only_alone_witnesses=witnesses,unexplained_mask_mismatches=mismatch,native_starts=0,new_learning=0,device_commands=0,model_fit_calls=0,guard_is_stronger_than_final_general_deadline_KPI=True,whole_trace_final_KPI_not_proved_by_current_queue_forecast=True,not_independent_trials=True,interpretation='same V1 evidence; removing a guard is a new hypothesis requiring separately registered development and fresh confirmation, not a repaired V1 PASS')
    d.write(d.PUBLIC/'guard_attribution.json',out)
    return dict(counts=counts,witnesses=len(witnesses),unexplained=len(mismatch),native_starts=0)
if __name__=='__main__':print(json.dumps(d.serial(run()),ensure_ascii=False),flush=True)
