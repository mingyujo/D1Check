"""PC-only preparation/Check for two prespecified AP idle-response sessions.

The installed ArrivalEnergyActivity already supports manifest-specified recorded
release gates.  This plan moves the releases into pre-registered idle/pulse
windows without changing request count, model, backend, APK, or Android code.
It is an AP diagnostic, not a replay of the original online B2 policy.
"""
from __future__ import annotations

import argparse
import copy
import json
import math
import uuid
from pathlib import Path

from tools import d1_arrival_plan as p
from tools import d1_arrival_timing_calibration as cal
from tools import d1_arrival_energy_collection as old
from tools import d1_arrival_recorded_replay as replay
from tools import d1_arrival_ap_confirmation as prior
from tools import d1_apk_identity as apk
from tools import d1_ap_idle_response as model

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = 'ENERGY-AP-IDLE-RESPONSE-01'
PLAN_FOLDER = 'energy_ap_idle_response_plan_v1'
RUN_FOLDER = 'energy_ap_idle_response_run_v1'
ROLES = ('development', 'confirmation')
FROZEN_SHA = replay.FROZEN_SHA
SOURCE_BUNDLE = replay.BUNDLE
MODEL_CONTRACT = ROOT/'docs/results/energy_ap_idle_response_01/analysis_contract.json'

# Old one-session reservation is 600 installation + 120 stage/gate + 485 poll
# + 50 recovery + 45 cleanup.  The same APK/runner is used twice.  A separate
# 30 s freeze and 90 s observed intersession wait are additional reservations.
BUDGET = dict(sessions=2, development=1, confirmation=1, requests=48,
    warmup=16, eligibility_inferences=0, explicit_inference=64,
    runtime_creations=8, staging=2, staging_files=14,
    installed_host_pulls=1, apk_transfers=1, installs=1,
    retry=0, replacement=0, additional=0, common_window_seconds=120,
    resident_baseline_seconds=30, start_ap_wait_seconds=30,
    app_cooling_seconds=60, app_drain_seconds=30,
    installation_seconds=600, stage_gate_seconds=120,
    host_poll_seconds=485, recovery_seconds=50, cleanup_seconds=45,
    session_seconds=700, development_freeze_seconds=30,
    intersession_observation_seconds=90, total_seconds=2120,
    adb_commands=6600, adb_recovery_cleanup_reserve=100,
    apk_push_timeout_seconds=120)


def budget_check(b):
    old.require(b == BUDGET and b['requests'] == 2*24 and
        b['explicit_inference'] == b['requests']+b['warmup']+b['eligibility_inferences'] and
        b['total_seconds'] == b['installation_seconds']+2*b['session_seconds']+
        b['development_freeze_seconds']+b['intersession_observation_seconds'] and
        b['session_seconds'] == sum(b[k] for k in ('stage_gate_seconds','host_poll_seconds',
            'recovery_seconds','cleanup_seconds')) and
        b['retry'] == b['replacement'] == b['additional'] == 0, 'idle-response budget')


def source_identity():
    return old.identity() | {'tools/d1_arrival_recorded_replay.py':p.digest(replay.__file__),
        'tools/d1_ap_idle_response.py':p.digest(model.__file__),
        'tools/d1_ap_idle_response_plan.py':p.digest(__file__),
        MODEL_CONTRACT.relative_to(ROOT).as_posix():p.digest(MODEL_CONTRACT),
        SOURCE_BUNDLE.relative_to(ROOT).as_posix():p.digest(SOURCE_BUNDLE)}


def transformed_requests(role):
    """Arrival times stay at 0..4.6 s; release gates create measured idle.

    Development: one short pulse at +35 s.  Confirmation: two pulses, first
    half +35 s and second half +60 s.  This is intentionally NOT the saved B2
    online timing; the long waiting times are an AP identification input.
    """
    old.require(role in ROLES, 'unknown role')
    source = replay.source_check()
    sid = str(uuid.uuid5(uuid.NAMESPACE_URL, EXPERIMENT+'/'+role+'/CG_DC'))
    rows = []
    for q in source['requests']:
        r = {k:v for k,v in q.items() if not k.startswith('pc_')}
        r['request_id'] = str(uuid.uuid5(uuid.NAMESPACE_URL,sid+'/'+str(q['ordinal'])))
        shift = 35 if role == 'development' or q['ordinal'] < 12 else 60
        r['release_offset_ns'] = q['release_offset_ns']+shift*1_000_000_000
        old.require(r['release_offset_ns'] < 120_000_000_000 and
                    r['release_offset_ns'] >= r['offset_ms']*1_000_000,
                    'release outside 120 s common window')
        rows.append(r)
    return sid, rows


def expected_manifest(source_file, source, candidate_sha, role, schedule_sha):
    template = p.read(Path(source_file).parent/source['entries'][0]['manifest'])
    sid, rows = transformed_requests(role)
    manifest = copy.deepcopy(template)
    manifest.update(experiment_id=EXPERIMENT,session_id=sid,phase=role,
        apk_sha256=candidate_sha,replay_source_sha256=schedule_sha,
        ap_idle_response_version=model.VERSION,
        ap_schedule_role=role,requests=rows)
    for spec in manifest['models'].values():
        spec['identity']['session_id'] = sid
        spec['target']['apk_sha256'] = candidate_sha
    return manifest


def script_text():
    return prior.script_text({}).replace('d1_arrival_ap_confirmation',
                                         'd1_ap_idle_response_plan')


def prepare(source_file, build_file, frozen_file, output):
    source_file,build_file,frozen_file,output=map(Path,(source_file,build_file,frozen_file,output))
    old.require(not output.exists() and output.name==PLAN_FOLDER,'fresh dedicated plan folder')
    source,build=p.read(source_file),p.read(build_file)
    budget_check(BUDGET);replay.source_check()
    old.require(source['experiment_id']==replay.EXPERIMENT and
                p.digest(frozen_file)==FROZEN_SHA and
                old.apk_sources(build['source_code'])==old.apk_sources(cal.code_identity()) and
                p.digest(build['apk_path'])==build['apk_sha256'],'source/APK/freeze identity')
    candidate=apk.inspect(build['apk_path'],source['apk_preflight']['toolchain'])
    old.require(candidate['signer_sha256']==source['apk_preflight']['candidate']['signer_sha256'],
                'project signer')
    output.mkdir();(output/'manifests').mkdir()
    schedule=dict(version='ap-idle-release-schedule-v1',source_sha256=p.digest(SOURCE_BUNDLE),
        rationale='pre-load resident idle then one pulse; confirmation has two separated pulses',
        model_keys=['classification_GPU','detection_CPU'],
        roles={role:dict(session_id=transformed_requests(role)[0],
                         requests=transformed_requests(role)[1]) for role in ROLES})
    schedule_file=output/'schedule.json';cal.write_new(schedule_file,schedule)
    plan=dict(protocol=old.PROTOCOL,experiment_id=EXPERIMENT,
        status='PC_READY_DEVICE_UNVERIFIED_NOT_APPROVED',approval='not_approved',
        experiment_ready=False,ap_idle_pulse_followup=True,recorded_replay_confirmation=True,
        budget=copy.deepcopy(BUDGET),source_code=source_identity(),
        build_receipt=str(build_file.resolve()),build_receipt_sha256=p.digest(build_file),
        source_plan=dict(path=str(source_file.resolve()),sha256=p.digest(source_file)),
        input_bundle=dict(path=str(SOURCE_BUNDLE.resolve()),sha256=p.digest(SOURCE_BUNDLE)),
        schedule=dict(path=str(schedule_file.resolve()),sha256=p.digest(schedule_file)),
        analysis_contract=dict(path=str(MODEL_CONTRACT.resolve()),sha256=p.digest(MODEL_CONTRACT)),
        frozen_model=dict(path=str(frozen_file.resolve()),sha256=FROZEN_SHA),
        apk_path=build['apk_path'],apk_sha256=build['apk_sha256'],
        apk_preflight=dict(source['apk_preflight'],candidate=candidate),
        device_fingerprint=source['device_fingerprint'],device_hardware_serial=source['device_hardware_serial'],
        output_root=str(output.parent/RUN_FOLDER),
        registry=str(output.parent/'ap_idle_response_registry'/EXPERIMENT),
        battery_start_percent=source['battery_start_percent'],
        battery_min_percent=source['battery_min_percent'],
        battery_max_temperature_tenths_c=source['battery_max_temperature_tenths_c'],
        require_unplugged=source['require_unplugged'],screen_contract=source['screen_contract'],
        source_files=source['source_files'],references=source['references'],
        measurement_protocol_change='same signed APK and sensors; two new release-gate patterns; not original B2 timing',
        analysis_scope='fixed-beta pre-load idle-reference AP diagnostic; no policy/energy coefficient fit',entries=[])
    for index,role in enumerate(ROLES):
        m=expected_manifest(source_file,source,build['apk_sha256'],role,p.digest(schedule_file))
        rel=f"manifests/{m['session_id']}.json";cal.write_new(output/rel,m)
        plan['entries'].append(dict(index=index,phase=role,scenario='queue',
            policy=replay.POLICY,session_id=m['session_id'],manifest=rel,
            manifest_sha256=p.digest(output/rel),requests=24,warmup=8,runtime_creations=4))
    script=output/'RUN_AFTER_APPROVAL.ps1';script.write_text(script_text(),encoding='utf-8')
    plan['run_script_sha256']=p.digest(script)
    cal.write_new(output/'collection_plan.json',plan)
    return check(output/'collection_plan.json')


def check(file):
    file=Path(file);plan=p.read(file);budget_check(plan['budget'])
    old.require(file.name=='collection_plan.json' and file.parent.name==PLAN_FOLDER and
        plan['experiment_id']==EXPERIMENT and plan['status']=='PC_READY_DEVICE_UNVERIFIED_NOT_APPROVED' and
        plan['approval']=='not_approved' and not plan['experiment_ready'] and
        plan['ap_idle_pulse_followup'] and plan['recorded_replay_confirmation'] and
        len(plan['entries'])==2 and [e['phase'] for e in plan['entries']]==list(ROLES),
        'idle-response plan identity')
    old.require(Path(plan['output_root'])==file.parent.parent/RUN_FOLDER and
        Path(plan['registry'])==file.parent.parent/'ap_idle_response_registry'/EXPERIMENT and
        not Path(plan['output_root']).exists() and not Path(plan['registry']).exists(),
        'unconsumed dedicated output')
    old.require(plan['source_code']==source_identity() and
        p.digest(file.parent/'RUN_AFTER_APPROVAL.ps1')==plan['run_script_sha256'] and
        p.digest(plan['build_receipt'])==plan['build_receipt_sha256'] and
        p.digest(plan['source_plan']['path'])==plan['source_plan']['sha256'] and
        p.digest(plan['input_bundle']['path'])==plan['input_bundle']['sha256'] and
        p.digest(plan['schedule']['path'])==plan['schedule']['sha256'] and
        p.digest(plan['analysis_contract']['path'])==plan['analysis_contract']['sha256'] and
        p.digest(plan['frozen_model']['path'])==FROZEN_SHA,'fixed source/model hashes')
    source=p.read(plan['source_plan']['path']);build=p.read(plan['build_receipt'])
    old.require(old.apk_sources(build['source_code'])==old.apk_sources(cal.code_identity()) and
        p.digest(plan['apk_path'])==plan['apk_sha256'] and
        apk.inspect(plan['apk_path'],plan['apk_preflight']['toolchain'])==plan['apk_preflight']['candidate'] and
        plan['apk_preflight']['candidate']['signer_sha256']==source['apk_preflight']['candidate']['signer_sha256'],
        'signed APK/source identity')
    for item in [*plan['source_files'].values(),*plan['references'].values()]:
        old.require(p.digest(item['path'])==item['sha256'],'staging/reference changed')
    for index,role in enumerate(ROLES):
        entry=plan['entries'][index];mf=file.parent/entry['manifest'];m=p.read(mf)
        old.require(entry['index']==index and entry['phase']==role and
            entry['session_id']==m['session_id'] and
            p.digest(mf)==entry['manifest_sha256'] and
            m==expected_manifest(plan['source_plan']['path'],source,plan['apk_sha256'],role,plan['schedule']['sha256']),
            'session manifest or release schedule changed')
    return dict(status=plan['status'],plan_sha256=p.digest(file),budget=BUDGET,device_commands=0)


def development_evidence(session_folder, frozen_file):
    """Technical fit eligibility only; no post-load AP is used to fit."""
    from tools import d1_arrival_energy_collection as c
    folder=Path(session_folder)
    events,partial=c.old.progress_prefix((folder/'artifacts/progress.jsonl').read_bytes())
    old.require(partial==0,'partial progress before AP development freeze')
    baseline=[e['mono_ns'] for e in events if e.get('phase')=='resident_baseline' and
              e.get('kind')=='phase_start']
    rows=p.read(folder/'artifacts/requests.json')
    first=min(r['dispatch_ns'] for r in rows)
    old.require(len(baseline)==1 and baseline[0]<first,'missing pre-load baseline boundary')
    thermal=[json.loads(x) for x in (folder/'thermal.jsonl').read_text(encoding='utf-8').splitlines()]
    points=[((x['mono_ns']-baseline[0])/1e9,float(x['AP'])) for x in thermal
            if baseline[0]<=x['mono_ns']<first and x.get('AP') not in ('',None) and
            x.get('thermal_status')=='0']
    frozen=p.read(frozen_file)
    fit=model.preload_reference(points,frozen['ap_cooling_rate_per_s'])
    fit.update(first_dispatch_ns=first, baseline_start_ns=baseline[0],
               data_role='development_technical_identifiability_not_independent_accuracy')
    return fit


def main():
    cli=argparse.ArgumentParser();sub=cli.add_subparsers(dest='action',required=True)
    q=sub.add_parser('prepare')
    for name in ('source-plan','build-receipt','frozen','output'):q.add_argument('--'+name,required=True)
    q=sub.add_parser('check');q.add_argument('--plan',required=True)
    q=sub.add_parser('run')
    for name in ('plan','adb','serial','expected-sha'):q.add_argument('--'+name,required=True)
    q.add_argument('--approved',action='store_true')
    a=cli.parse_args()
    if a.action=='prepare':result=prepare(a.source_plan,a.build_receipt,a.frozen,a.output)
    elif a.action=='check':result=check(a.plan)
    else:
        from tools.d1_arrival_energy_collection_device import run
        result=run(a.plan,a.adb,a.serial,a.expected_sha,a.approved)
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
