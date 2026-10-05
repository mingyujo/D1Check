"""Reuse historical timing controls; add only the existing four-cell EFT reference.

J/AP remain null. Unmeasured classification CPU+GPU concurrency is explicit.
"""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
from tools import d1_detector_gpu_bridge as b


def occupancy(ledger):
    jobs=[dict(start=q['dispatch_ns']/1e9,end=q['lane_available_ns']/1e9,
        state=q['task']+'_'+q['backend']) for q in ledger if q['status']=='succeeded']
    cuts=sorted({0.,120.}|{j[k] for j in jobs for k in ('start','end')})
    known={'idle','classification_CPU','classification_GPU','detection_CPU','detection_GPU',
        'classification_CPU+detection_GPU','classification_GPU+detection_CPU','detection_CPU+detection_GPU'}
    result=[]
    for a,z in zip(cuts,cuts[1:]):
        label='+'.join(sorted(j['state'] for j in jobs if j['start']<=a<j['end'])) or 'idle'
        result.append(dict(start_s=a,end_s=z,state=label,historical_fixed_state_exists=label in known))
    return result


def run(output,parent):
    output=Path(output);output.mkdir(parents=True,exist_ok=False);parent=Path(parent)
    inputs=b.read(parent/'inputs.json');controls=b.read(parent/'timing_ledgers.json')
    config=b.read(b.BUNDLE/'estimates.json');vectors=b.read(b.BUNDLE/'realizations.json')
    files=[Path(__file__),Path(b.batch.engine.__file__),Path(b.batch.__file__),
        b.BUNDLE/'estimates.json',b.BUNDLE/'realizations.json',parent/'inputs.json',parent/'timing_ledgers.json']
    hashes={p.relative_to(b.f.x.p.ROOT).as_posix():b.f.x.p.digest(p) for p in files}
    b.f.x.p.write(output/'registered_before_run.json',dict(utc=datetime.now(timezone.utc).isoformat(),hashes=hashes,
        policy='LEGACY_FOUR_CELL_EFT',actual_engine_policy='B3_SOLO_EFT_PC',requests=48,new_runs=16,
        reused_control_records=48,estimated_and_realized_interference=[1.,1.5],
        use='causal time-only reference with historical paired CAL03 vectors; not current model or device validation',
        unmeasured_same_task_classification_pair_not_hidden=True,energy_j=None,ap_c=None,
        power_assumptions_added=False,device_commands=0,experiment_ready=False))
    rows=[];records=[]
    for item in inputs:
        for factor in (1.,1.5):
            settings=b.batch.defaults('explore');settings.update(interference=factor,predicted_interference=factor)
            rr=b.batch.engine.simulate(config,vectors,item['tickets'],policy='B3_SOLO_EFT_PC',settings=settings,seed=item['seed'])
            ss=occupancy(rr['ledger'])
            if abs(sum(s['end_s']-s['start_s'] for s in ss)-120)>1e-6:raise ValueError('incomplete timing window')
            row=dict(envelope=item['envelope'],seed=item['seed'],interference=factor,policy='LEGACY_FOUR_CELL_EFT',
                planned=48,completed=sum(q['status']=='succeeded' for q in rr['ledger']),
                deadline_met=sum('response_ns' in q and q['response_ns']<=q['deadline_offset_ns'] for q in rr['ledger']),
                urgent_p95_ms=rr['metrics']['urgent_p95_ms'],normal_mean_ms=rr['metrics']['normal_mean_ms'],
                detection_gpu_jobs=sum(q.get('backend')=='GPU' and q['task']=='detection' for q in rr['ledger']),
                unmeasured_concurrency_s=sum(s['end_s']-s['start_s'] for s in ss if not s['historical_fixed_state_exists']),
                energy_j=None,ap_peak_c=None,current_profile_supported=False)
            rows.append(row);records.append(dict(meta=row,ledger=rr['ledger'],segments=ss))
    if hashes!={p.relative_to(b.f.x.p.ROOT).as_posix():b.f.x.p.digest(p) for p in files}:raise ValueError('reference source changed')
    b.f.x.old.csv_write(output/'timing_only.csv',rows);b.f.x.p.write(output/'timing_ledgers.json',records)
    b.f.x.p.write(output/'summary.json',dict(new_runs=16,reused_control_records=48,
        full_service_cases=sum(r['deadline_met']==48 for r in rows),
        measured_state_compatible_cases=sum(r['unmeasured_concurrency_s']==0 for r in rows),
        current_profile_supported=False,energy_AP_computed=False,device_commands=0,experiment_ready=False))


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--output',required=True)
    ap.add_argument('--parent',default=str(b.ROOT/'run_v1'));args=ap.parse_args();run(args.output,args.parent)
