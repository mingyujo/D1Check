"""Read-only public/optional raw verification. Never starts ADB, learning or a run."""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path
import statistics

from tools import d1_arrival_plan as p

ROOT=Path(__file__).resolve().parents[1]
PUBLIC=ROOT/'docs/results/overnight_device_20261011'


def require(ok,message):
    if not ok:raise ValueError(message)


def main():
    result=p.read(PUBLIC/'summary.json');contract=p.read(PUBLIC/'execution_contract.json')
    manifest_path=PUBLIC/'source_bundle/manifest_v2.json'
    if not manifest_path.exists():manifest_path=PUBLIC/'source_bundle/manifest.json'
    source=p.read(manifest_path);windows=p.read(PUBLIC/'analysis_window_note.json')
    if source.get('archive_manifest_version')==2:
        require(p.digest(PUBLIC/'source_bundle/manifest.json')==source['base_manifest_v1_sha256'],
            'original manifest v1 drift')
    require(result['status']=='completed_descriptive_only','not a completed registered measurement')
    require(len(result['sessions'])==4 and result['physical_sessions']==4 and result['installs']==1 and
        result['additional_inference_consumption']==416,'bounded physical consumption')
    require(contract['budget']['explicit_inference']==416 and contract['budget']['sessions']==4,'contract cap')
    require(result['verdict']['new_data_fit_calls']==0 and result['verdict']['online_policy_superiority'] is None and
        result['verdict']['physical_saving_established'] is False,'scope and fit boundaries')
    require(p.digest(PUBLIC/'source_bundle/portable_prerequisites.patch')==source['patch_sha256'] and
        p.digest(PUBLIC/'frozen_plan_replay_v2.patch')==source['opt_in_patch_sha256'],'portable patch drift')
    require(len(source['prerequisite_files'])==11 and all(x['prerequisite_plus_opt_in_matches_executed_snapshot']
        for x in source['runtime_match']),'source scope/runtime comparison')
    for entry in source['prerequisite_files']:
        file=(PUBLIC/'source_bundle'/entry['archive_path']) if entry.get('archive_path') else (PUBLIC/'source_bundle/prerequisites'/entry['path'])
        require(p.digest(file)==entry['canonical_utf8_lf_sha256'],'canonical prerequisite SHA')
        require(b'\r' not in file.read_bytes(),'canonical LF required')
    require(p.digest(PUBLIC/'temperature_observation_windows.csv')==windows['windows_sha256'],'temperature window drift')
    with (PUBLIC/'requests.csv').open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
    require(len(rows)==384 and len({(int(x['index']),int(x['ordinal'])) for x in rows})==384,'scheduled denominator')
    phases=('actual_arrival_ms','dispatch_ms','execution_start_ms','output_ready_ms','persist_complete_ms','worker_release_ms','lane_available_ms')
    for index in range(4):
        selected=[x for x in rows if int(x['index'])==index]
        require(len(selected)==96 and {int(x['ordinal']) for x in selected}==set(range(96)),'per arm count')
        for x in selected:
            require(x['terminal_status']=='succeeded','missing/failure cannot be removed from denominator')
            require(x['backend'] in ('CPU','GPU') and (x['task_id']!='detection' or x['backend']=='CPU'),'unsupported action')
            times=[float(x[k]) for k in phases]
            require(all(a<=b for a,b in zip(times,times[1:])),'response/lane boundary')
            require(float(x['planned_arrival_ms'])==35000+350*int(x['ordinal']),'fixed common0 trace')
        for lane in ('CPU','GPU'):
            ordered=sorted((x for x in selected if x['backend']==lane),key=lambda x:float(x['dispatch_ms']))
            require(all(float(a['lane_available_ms'])<=float(b['dispatch_ms']) for a,b in zip(ordered,ordered[1:])),
                'lane reused before actual availability')
        urgent=sorted(float(x['response_ms']) for x in selected if x['priority']=='urgent')
        normal=[float(x['response_ms']) for x in selected if x['priority']=='normal']
        require(len(urgent)==len(normal)==48,'priority denominator')
        stats=result['sessions'][index]
        require(stats['completed']==96 and stats['common_unfinished']==stats['urgent_failures']==stats['normal_failures']==0,
            'completion/service mismatch')
        require(abs(stats['urgent_p95_ms']-urgent[math.ceil(.95*len(urgent))-1])<1e-8 and
            abs(stats['normal_mean_response_ms']-statistics.mean(normal))<1e-8,'published response arithmetic')
        require(stats['energy_full_coverage'] and abs(stats['energy_coverage_s']-120)<1e-8,'common energy coverage')
        require(stats['cost_validation_error'].startswith("ValueError('pre-load idle too short") and
            len(stats['cost_validation_v2'])==2,'original readout failure must remain visible')
        for forecast in stats['cost_validation_v2'].values():
            require(forecast['coefficient_fit_calls']==0 and forecast['initial_input_latest_hi']<35 and
                forecast['initial_AP_observed_duration_s']>=55 and forecast['pre_work_or_warmup_included'] is False,
                'coefficient fit/future/initial coverage gate')
    require(len(result['temperature_observation_windows'])==16 and all(x['full_180s_actual_temperature_imputed'] is False and
        x['exact_continuous_window_peak_c'] is None for x in result['temperature_observation_windows']),'temperature edge imputation')
    raw_root=ROOT/'output/overnight_device_20261011_v1/run'
    mode='public_artifact_arithmetic_and_source_PASS';raw_verified=0
    if raw_root.exists():
        require(not (raw_root/'owner.lock').exists(),'measurement still owned')
        require(p.digest(raw_root/'FINAL_RECEIPT.json')==result['terminal_receipt_sha256'] and
            p.digest(raw_root/'frozen_collection_plan.json')==result['plan_sha256'],'raw receipt/plan drift')
        for rel,sha in result['raw_sha256'].items():
            require(p.digest(raw_root/rel)==sha,'raw changed: '+rel);raw_verified+=1
        mode='public_and_raw_SHA_arithmetic_source_PASS'
    print(json.dumps(dict(status=mode,public_requests=384,physical_consumption_recorded=416,
        source_prerequisites=11,raw_files_verified=raw_verified,new_device_commands=0,new_native_environments=0,
        source_archive_version=source.get('archive_manifest_version',1),
        new_training=0,new_coefficient_fit=0,new_session_claim=0),ensure_ascii=False,indent=2))


if __name__=='__main__':main()
