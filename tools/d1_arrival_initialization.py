"""Single-use setup-only diagnosis. prepare/check are PC-only; run requires explicit approval."""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
import re
from pathlib import Path
import time
import uuid

from tools import d1_arrival_plan as p
from tools import d1_arrival_timing_calibration as c
from tools import d1_arrival_timing_dev as v
from tools import d1_arrival_device as legacy
from tools import d1_apk_identity as apk
from tools import d1_arrival_failure_evidence as evidence

EXPERIMENT = 'ARRIVAL-INIT-DIAG-01'
PROTOCOL = 'arrival-initialization-plan-v1'
PARENT_SHA = '31558f9c1d3c62b8d1d4e9f0b8713274bee6a1700e4a8c59c2c4ae5aabc5a7a6'
ORDER = ['classification_CPU','classification_GPU','detection_CPU','detection_GPU']
BUDGET = dict(execution_attempts=1,install_attempts=1,session_attempts=1,runtime_creations=4,
              warmup_calls=0,inference_calls=0,retry=0,replacement=0,additional=0,
              total_seconds=600,work_seconds=545,evidence_seconds=10,cleanup_seconds=45,
              runtime_wait_seconds=30,app_watchdog_seconds=120,host_poll_seconds=125,
              initial_cool_seconds=120)


def code_identity():
    return dict(c.code_identity(), **{'tools/d1_arrival_initialization.py':p.digest(__file__)})


def specification(parent_file, apk_file, build_receipt, output):
    parent_file, apk_file, build_receipt, output = map(lambda x:Path(x).resolve(),
                                                    (parent_file,apk_file,build_receipt,output))
    v.require(p.digest(parent_file)==PARENT_SHA,'wrong CAL-02 parent')
    parent=p.read(parent_file); entry=parent['entries'][0]
    original=parent_file.parent/entry['manifest']
    v.require(p.digest(original)==entry['manifest_sha256'],'parent manifest identity')
    receipt=p.read(build_receipt)
    sha=p.digest(apk_file)
    v.require(receipt['apk_sha256']==sha and receipt['status']=='built_not_device_verified'
              and c.apk_sources(receipt['source_code'])==c.apk_sources(code_identity()),'build/source identity')
    sid=str(uuid.uuid5(uuid.NAMESPACE_URL,EXPERIMENT+'/setup-only/1'))
    manifest=copy.deepcopy(p.read(original))
    manifest.update(session_id=sid,experiment_id=EXPERIMENT,collection_phase='initialization_diagnosis',
                    apk_sha256=sha,requests=[],warmup_requests=[],failure_diagnostic_contract=evidence.CONTRACT,
                    failure_diagnostic_scope='setup_only',performance_excluded=True,experiment_ready=False)
    for spec in manifest['models'].values():
        spec['identity']['session_id']=sid;spec['target']['apk_sha256']=sha
    gate=copy.deepcopy(parent['apk_preflight'])
    gate['candidate']=dict(gate['candidate'],apk_sha256=sha)
    plan=dict(protocol=PROTOCOL,experiment_id=EXPERIMENT,status='prepared_not_execution_approved',
              experiment_ready=False,performance_excluded=True,parent_plan=str(parent_file),parent_sha256=PARENT_SHA,
              parent_session=entry['session_id'],parent_state='stopped_no_retry_no_resume',
              apk_path=str(apk_file),apk_sha256=sha,build_receipt=str(build_receipt),build_receipt_sha256=p.digest(build_receipt),
              apk_preflight=gate,source_code=code_identity(),source_files=parent['source_files'],
              device_fingerprint=parent['device_fingerprint'],runtime_order=ORDER,budget=BUDGET,
              manifest='manifest.json',manifest_sha256=hashlib.sha256(p.canonical(manifest)).hexdigest(),
              session_id=sid,output_root=str(output.parent/'runtime_initialization_run_v1'),
              registry=str(output.parent/'runtime_initialization_registry'/EXPERIMENT),
              consumption='claim before device preflight; install before install-r; session before am-start; runtime start intent is not completion; no re-entry after claim')
    for field in ('battery_start_percent','battery_min_percent','battery_max_temperature_tenths_c','require_unplugged'):
        plan[field]=parent[field]
    return plan,manifest


def prepare(parent, apk_file, receipt, output):
    output=Path(output).resolve()
    v.require(not output.exists(),'new preparation root required')
    plan,manifest=specification(parent,apk_file,receipt,output)
    # PC signature verification before publishing an executable candidate.
    v.require(apk.inspect(apk_file,plan['apk_preflight']['toolchain'])==plan['apk_preflight']['candidate'],
              'project signer/package/version mismatch')
    output.mkdir(parents=True)
    c.write_new(output/'manifest.json',manifest)
    c.write_new(output/'initialization_plan.json',plan)
    return check(output/'initialization_plan.json')


def check(path, signature=True):
    path=Path(path).resolve(); plan=p.read(path)
    expected,manifest=specification(plan['parent_plan'],plan['apk_path'],plan['build_receipt'],path.parent)
    v.require(plan==expected,'plan/code/budget/paths changed')
    v.require((path.parent/plan['manifest']).read_bytes()==p.canonical(manifest),'manifest changed')
    for name,info in plan['source_files'].items():
        v.require(Path(info['path']).stat().st_size==info['bytes'] and p.digest(info['path'])==info['sha256'],'input changed: '+name)
    gate=plan['apk_preflight']
    for key,sha in gate['tool_sha256'].items():
        v.require(p.digest(gate['toolchain'][key])==sha,'inspection tool changed')
    if signature:
        v.require(apk.inspect(plan['apk_path'],gate['toolchain'])==gate['candidate'],'APK identity changed')
    return dict(status='PC_READY_NOT_DEVICE_VERIFIED_NOT_APPROVED',plan_sha256=p.digest(path),budget=BUDGET,
                adb_calls=0,install_calls=0,app_launches=0,generated_measurements=0)


def claim(plan, path):
    output=Path(plan['output_root']);registry=Path(plan['registry'])
    v.require(not output.exists() and not registry.exists(),'consumed plan; no retry or replacement')
    registry.mkdir(parents=True,exist_ok=False) # Atomic shared plan identity; changing output cannot re-arm it.
    c.write_new(registry/'execution_claim.json',dict(utc=legacy.utc(),plan_sha256=p.digest(path),output=str(output)))
    output.mkdir(parents=True,exist_ok=False)
    return output


def inspect_artifacts(folder, manifest_sha):
    folder=Path(folder);manifest=p.read(folder/'manifest.json')
    v.require(p.digest(folder/'manifest.json')==manifest_sha,'recovered manifest mismatch')
    v.require(manifest['requests']==[] and manifest['warmup_requests']==[] and
              manifest.get('failure_diagnostic_scope')=='setup_only','not setup-only')
    raw=(folder/'failure_progress.jsonl').read_bytes() if (folder/'failure_progress.jsonl').exists() else b''
    summary=evidence.summarize_journal(raw,manifest,manifest_sha)
    rows=[json.loads(line) for line in raw.splitlines()[:summary['valid_prefix_records']]]
    starts=[r for r in rows if r['stage']=='runtime_create' and r['edge']=='start']
    returns=[r for r in rows if r['stage']=='runtime_create' and r['edge']=='succeeded']
    v.require([r['model_key'] for r in starts]==ORDER[:len(starts)] and len(starts)<=4,
              'runtime start order/cap violation')
    v.require(len({r['model_key'] for r in returns})==len(returns) and
              all(r['model_key'] in {s['model_key'] for s in starts} for r in returns),'orphan/duplicate runtime completion')
    admissions=[r for r in rows if r['stage']=='admission' and r['edge']=='observed']
    valid=(summary['invalid_suffix'] is None and [r['model_key'] for r in starts]==ORDER
           and [r['model_key'] for r in returns]==ORDER
           and [r['model_key'] for r in admissions]==ORDER
           and all('before_runtime_creation/admit:' in r.get('detail','') for r in admissions)
           and any(r['stage']=='setup_only' and r['edge']=='succeeded' for r in rows)
           and any(r['stage']=='cleanup' and r['edge']=='succeeded' for r in rows)
           and not any(r['edge'] in ('failed','timeout','cancelled','stopped') for r in rows))
    for backend in ('CPU','GPU'):
        valid=valid and len({r['thread_id'] for r in starts+returns if r['model_key'].endswith(backend)})==1
    valid=valid and not any(r['stage'] in ('warmup','diagnostic','measured_invocation') for r in rows)
    valid=valid and not list(folder.glob('*.result.json'))
    if (folder/'cleanup.json').exists():
        valid=valid and p.read(folder/'cleanup.json').get('status')=='completed'
    else:
        valid=False
    summary.update(status='SETUP_COMPLETED_NOT_CAUSE_RESOLVED' if valid else 'INCOMPLETE_OR_FAILED',
                   runtime_start_intents=len(starts),runtime_returned=len(returns),
                   runtime_actual_attempt_bounds=[len(returns),4],runtime_events=[r for r in rows if r.get('model_key')],
                   native_gpu_verified=False,performance_eligible=False)
    return summary


def environment_gate(device,plan,output,label):
    thermal=device.call('shell','dumpsys','thermalservice').stdout
    battery=device.call('shell','dumpsys','battery').stdout
    memory=device.call('shell','cat','/proc/meminfo').stdout
    c.write_new(output/(label+'.json'),dict(utc=legacy.utc(),thermal=thermal.decode(errors='replace'),
                 battery=battery.decode(errors='replace'),memory=memory.decode(errors='replace'),
                 runtime_memory_admission='required_inside_app_before_each_constructor'))
    v.require(re.search(rb'Thermal Status:\s*0\b',thermal),'thermal gate')
    legacy.battery_gate(plan,battery.decode(),True)
    legacy.require_stopped(device)


def run(path,adb,serial,expected_sha,approved):
    from tools import d1_arrival_timing_calibration_device as device_tools
    started=time.monotonic(); hard=started+600;work_end=hard-55
    v.require(approved==EXPERIMENT and p.digest(path)==expected_sha,'explicit single-session approval/hash required')
    check(path,signature=False) # No device access; time spent here counts against this invocation.
    plan=p.read(path); output=claim(plan,path);device=legacy.Device(adb,serial);device.deadline=work_end
    counts=dict(execution_attempts=1,install_attempts=0,session_attempts=0,warmup_calls=0,inference_calls=0)
    pid=None; stage='preflight'; cleanup_needed=False; result=None; error=None
    def save(name,data):c.write_new(output/name,data)
    try:
        v.require(time.monotonic()<work_end,'budget exhausted before preflight')
        save('budget_start.json',dict(utc=legacy.utc(),host_monotonic_start=started,hard_deadline=hard,
                                     work_deadline=work_end,cleanup_reserved_seconds=45))
        inspection=dict(plan,_plan_file=str(path))
        apk.preflight(device,inspection,output/'signature_preflight')
        environment_gate(device,plan,output,'before_install')
        stage='install';counts['install_attempts']=1;cleanup_needed=True
        save('install_attempt.json',dict(utc=legacy.utc(),apk_sha256=plan['apk_sha256']))
        response=device.call('install','-r',plan['apk_path'],timeout=120)
        save('install_result.json',dict(utc=legacy.utc(),returncode=response.returncode,stdout=response.stdout.decode(errors='replace')))
        stage='post_install_identity'
        identity=apk.preflight(device,inspection,output/'installed_identity')
        v.require(identity['installed']==plan['apk_preflight']['candidate'],'installed APK not exact candidate')
        stage='cooling';legacy.bounded_cool(device,120)
        environment_gate(device,plan,output,'before_launch')
        stage='staging'
        remote=device_tools.stage_inputs(device,plan['session_id'],Path(path).parent/plan['manifest'],
                                         {k:x['path'] for k,x in plan['source_files'].items()})
        v.require(work_end-time.monotonic()>=155,'insufficient reserved launch30 + poll125; do not launch')
        stage='activity_launch';counts['session_attempts']=1
        save('session_attempt.json',dict(utc=legacy.utc(),session_id=plan['session_id'],runtime_creation_cap=4))
        response=device.call('shell','am','start','-W','-n',legacy.PACKAGE+'/'+legacy.ACTIVITY,
                             '-a',legacy.ACTION,'--es','session_id',plan['session_id'],timeout=30)
        (output/'launch_stdout.txt').write_bytes(response.stdout)
        stage='completion_poll';device.deadline=min(work_end,time.monotonic()+125)
        pid=device.call('shell','pidof',legacy.PACKAGE+':model_probe',check=False).stdout.decode().strip()
        device_tools.wait_for_cleanup(device,remote)
    except BaseException as exc:
        error=repr(exc)
        save('host_error.json',dict(utc=legacy.utc(),host_stage=stage,error=error,
                                   application_failure='unknown_until_app_evidence'))
    finally:
        try:
            if counts['session_attempts']:
                device.deadline=min(hard-45,time.monotonic()+10)
                device_tools.failed_attempt_evidence(device,plan['session_id'],output,pid)
                try:
                    result=inspect_artifacts(output/'partial',plan['manifest_sha256'])
                    save('artifact_assessment.json',result)
                except Exception as exc:
                    save('assessment_error.json',dict(error=repr(exc)))
        finally:
            if cleanup_needed:
                try:save('host_cleanup.json',device_tools.cleanup(device,hard_deadline=hard))
                except BaseException as exc:save('host_cleanup_error.json',dict(error=repr(exc)))
    complete=(error is None and result is not None and result['status']=='SETUP_COMPLETED_NOT_CAUSE_RESOLVED'
              and (output/'host_cleanup.json').exists() and time.monotonic()<=hard)
    receipt=dict(status='complete_not_cause_resolved' if complete else 'stopped_no_retry',counts=counts,
                 runtime_actual_attempt_bounds=result['runtime_actual_attempt_bounds'] if result else
                    ([0,4] if counts['session_attempts'] else [0,0]),
                 runtime_returned=result['runtime_returned'] if result else None,
                 elapsed_seconds=time.monotonic()-started,hard_limit_seconds=600,
                 app_result=result['status'] if result else 'unconfirmed',performance_eligible=False,
                 no_resume=True,utc=legacy.utc())
    save('FINAL_RECEIPT.json',receipt)
    c.write_new(Path(plan['registry'])/'closed.json',receipt)
    return receipt


def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    prep=sub.add_parser('prepare')
    for name in ('parent','apk','build-receipt','output'):prep.add_argument('--'+name,required=True)
    verify=sub.add_parser('check');verify.add_argument('--plan',required=True)
    execute=sub.add_parser('run')
    for name in ('plan','adb','serial','expected-plan-sha256','approved-experiment'):execute.add_argument('--'+name,required=True)
    args=parser.parse_args()
    if args.command=='prepare':result=prepare(args.parent,args.apk,args.build_receipt,args.output)
    elif args.command=='check':result=check(args.plan)
    else:result=run(args.plan,args.adb,args.serial,args.expected_plan_sha256,args.approved_experiment)
    print(json.dumps(result,indent=2))
    if result.get('status')=='stopped_no_retry':raise SystemExit(2)


if __name__=='__main__':main()
