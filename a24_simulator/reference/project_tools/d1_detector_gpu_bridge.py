"""Historical CAL03 timing reuse. Never completes the missing current J/AP cell.

No device entry point, new fit, power assumption, or physical profile mutation.
"""
import argparse
import copy
import csv
from datetime import datetime,timezone
import json
from pathlib import Path
import statistics
from tools import d1_method_followup as f
from tools import d1_cal03_connection as base
from tools import d1_arrival_explore_batch as batch

ROOT=f.x.p.ROOT/'docs/results/detector_gpu_bridge_01'
BUNDLE=f.x.p.ROOT/'docs/results/arrival_explore_20260925/input_bundle'
CELLS=('classification_CPU_urgent','classification_GPU_urgent','detection_CPU_normal','detection_GPU_normal')
MAPS={'CPU_URGENT':dict(classification='CPU',detection='CPU'),
      'LEGACY_STATIC_CG_DC':dict(classification='GPU',detection='CPU'),
      'LEGACY_STATIC_CC_DG':dict(classification='CPU',detection='GPU')}


def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))


def phases(row):
    times=[row[k] for k in base.STEPS]
    if any(type(t) is not int for t in times) or times!=sorted(times):raise ValueError('invalid measured five phase/W/L boundary')
    if row['terminal_status']!='succeeded':raise ValueError('failed historical request')
    return [b-a for a,b in zip(times,times[1:])]


def timing_evidence(external):
    external=Path(external);plan=read(external/'timing_cal03_plan_v3/calibration_plan.json')
    fit=read(external/'timing_cal03_fit_v1.json');confirm=read(external/'timing_cal03_confirmation_v1.json')
    if f.x.p.digest(external/'timing_cal03_fit_v1.json')!=confirm['freeze_sha256']:raise ValueError('historical freeze changed')
    config=read(BUNDLE/'estimates.json');vectors=read(BUNDLE/'realizations.json');base.validate_config(config)
    rows=[];provenance={};identities=[]
    for entry in plan['entries']:
        key=f"{entry['task']}_{entry['backend']}_{entry['priority']}"
        if key not in CELLS:continue
        role=entry['phase'];folder=external/'timing_cal03_run_v1'/role/f"{entry['index']:02d}_{entry['session_id']}"
        source=folder/'artifacts/requests.json';validation=read(folder/'validated.json');m=read(folder/'artifacts/manifest.json')
        frozen=fit if role=='development' else confirm
        if frozen['input_hashes'].get(str(source.resolve()))!=f.x.p.digest(source):raise ValueError('historical request bytes mismatch')
        if validation['timing']['session_status']!='completed' or validation['request_count']!=4:raise ValueError('historical session not valid')
        if entry['backend']=='GPU' and validation['gpu']['status']!='verified_full':raise ValueError('historical delegate missing')
        rr=read(source)
        if len(rr)!=4:raise ValueError('historical denominator')
        for r in rr:
            d=phases(r)
            if role=='development':
                reference=next(v for v in vectors['cells'][key] if v['source_request_id']==r['request_id'])
                if reference['durations_ns']!=d:raise ValueError('portable vector does not match original worker split')
            rows.append(dict(role=role,cell=key,ordinal=r['ordinal'],durations_ns=d,
                source_request_id=r['request_id'],input_tensor_sha256=r['input_tensor_sha256'],
                gpu_delegate_verified=entry['backend']=='GPU',independent_sessions_per_cell_role=1,
                evidence='historical fixed solo; four correlated requests, not independent draws'))
        provenance[source.relative_to(external).as_posix()]=f.x.p.digest(source)
        provenance[(folder/'validated.json').relative_to(external).as_posix()]=f.x.p.digest(folder/'validated.json')
        identities.append(dict(role=role,cell=key,apk_sha256=m['apk_sha256'],cpu_threads=m['cpu_threads'],
            maximum_concurrency=m['maximum_concurrency'],resident_keys=sorted(m['models']),
            model_sha256={k:v['model']['sha256'] for k,v in m['models'].items()},
            runtime={k:v['runtime'] for k,v in m['models'].items()}))
    if len(rows)!=32:raise ValueError('missing 4 cells x2 roles x4 paired records')
    newplan=read(external/'sustained_confirmation_plan_v1/collection_plan.json')
    current_manifest=read(external/'sustained_confirmation_plan_v1'/newplan['entries'][0]['manifest'])
    old_manifest=read(external/'timing_cal03_plan_v3'/plan['entries'][0]['manifest'])
    facts=dict(same_recorded_device_fingerprint=old_manifest['device_fingerprint']==current_manifest['device_fingerprint'],
        same_model_sha256={k:old_manifest['models'][k]['model']['sha256']==v['model']['sha256'] for k,v in current_manifest['models'].items()},
        same_runtime={k:old_manifest['models'][k]['runtime']==v['runtime'] for k,v in current_manifest['models'].items()},
        old_apk_sha256=old_manifest['apk_sha256'],current_apk_sha256=current_manifest['apk_sha256'],
        apk_identical=old_manifest['apk_sha256']==current_manifest['apk_sha256'],
        old_resident_keys=sorted(old_manifest['models']),current_resident_keys=sorted(current_manifest['models']),
        old_manifest_sha256=f.x.p.digest(external/'timing_cal03_plan_v3'/plan['entries'][0]['manifest']),
        current_manifest_sha256=f.x.p.digest(external/'sustained_confirmation_plan_v1'/newplan['entries'][0]['manifest']))
    return dict(rows=rows,original_relative_hashes=provenance,identities=identities,comparison=facts,
        current_missing_cell='detection_GPU_normal',current_energy_j=None,current_ap_c=None,
        current_profile_admission=False,current_profile_reason='historical solo timing and old fixed-state power do not identify current short-request DG/CC_DG increments or transition transfer',
        old_power_retained_as_historical_only=True,experiment_ready=False,device_commands=0)


def requirements(evidence):
    """Explicitly prevent old observed W becoming a new request coefficient."""
    return dict(historical_five_phase_records=len(evidence['rows']),historical_timing_reusable=True,
        current_dg_service=None,current_dg_increment_w=None,current_cc_dg_increment_w=None,
        current_ap_dg_transfer=None,current_ap_cc_dg_transfer=None,
        frozen_existing_3_cells_unchanged=True,
        minimal_states=['resident_idle','classification_CPU','detection_GPU','classification_CPU+detection_GPU'],
        unused_states_not_required=['detection_CPU+detection_GPU','classification_CPU+classification_GPU'],
        questions=['does DG offload preserve urgent response and normal completion under the same short-request engine?',
            'what are baseline-separated DG and CC_DG energy costs and AP transition response under the same resident/polling protocol?'],
        independent_confirmation_required_before_device_policy_effect=True,accuracy_pass=None,
        device_plan_created=False,device_claim_created=False)


def study(output,external):
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    evidence=timing_evidence(external);f.x.p.write(output/'timing_evidence.json',evidence)
    f.x.p.write(output/'requirements.json',requirements(evidence))
    config=read(BUNDLE/'estimates.json');vectors=read(BUNDLE/'realizations.json')
    sources=[Path(__file__),Path(batch.__file__),Path(batch.engine.__file__),Path(f.conditions.__file__),
        BUNDLE/'estimates.json',BUNDLE/'realizations.json',f.x.p.BUNDLE/'model.json']
    hashes={p.relative_to(f.x.p.ROOT).as_posix():f.x.p.digest(p) for p in sources}
    f.x.p.write(output/'registered_before_run.json',dict(utc=datetime.now(timezone.utc).isoformat(),
        base_head='865f7617414258951f3289e5efd04f633a3b30c7',dirty=True,hashes=hashes,
        cases=list(f.CASES),seeds=[623001,623002],maps=MAPS,realized_interference=[1.,1.5],
        runs=48,requests=48,role='historical timing transfer exploration, not current J/AP prediction',
        no_power_assumption=True,no_fit=True,device_commands=0,experiment_ready=False))
    rows=[];inputs=[];records=[]
    for env in f.CASES:
        e=next(e for e in f.conditions.envelopes() if e['id']==env)
        for seed in (623001,623002):
            qs=f.conditions.workload(e,seed);inputs.append(dict(envelope=env,seed=seed,tickets=qs))
            for factor in (1.,1.5):
                for name,mapping in MAPS.items():
                    settings=batch.defaults('explore');settings.update(static_map=mapping,static_parallel=True,
                        interference=factor,predicted_interference=factor)
                    policy='CPU_URGENT' if name=='CPU_URGENT' else 'B2_PC'
                    rr=batch.engine.simulate(config,vectors,qs,policy=policy,settings=settings,seed=seed)
                    row=dict(envelope=env,seed=seed,interference=factor,policy=name,original_engine_policy=policy,
                        planned=len(qs),completed=sum(q['status']=='succeeded' for q in rr['ledger']),
                        deadline_met=sum('response_ns' in q and q['response_ns']<=q['deadline_offset_ns'] for q in rr['ledger']),
                        urgent_p95_ms=rr['metrics']['urgent_p95_ms'],normal_mean_ms=rr['metrics']['normal_mean_ms'],
                        energy_j=None,ap_peak_c=None,evidence='historical timing transfer only, not current measured J/AP')
                    rows.append(row);records.append(dict(meta=row,ledger=rr['ledger']))
    if hashes!={p.relative_to(f.x.p.ROOT).as_posix():f.x.p.digest(p) for p in sources}:raise ValueError('registered source changed')
    f.x.old.csv_write(output/'timing_only.csv',rows);f.x.p.write(output/'inputs.json',inputs)
    f.x.p.write(output/'timing_ledgers.json',records)
    f.x.p.write(output/'summary.json',dict(runs=len(rows),requests=len(rows)*48,device_commands=0,
        current_dg_profile_ready=False,current_J_AP_computed=False,frozen_model_unchanged=True,experiment_ready=False))
    return rows


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--output',required=True)
    ap.add_argument('--external',default='C:/Users/LG/Documents/D1Check_Arrival_Extension')
    args=ap.parse_args();study(args.output,args.external)
