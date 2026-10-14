"""Execute registered, distinct A24 slots; preserve failures; no session reruns."""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
import os
import re
import shutil
import time
from pathlib import Path
from d1_a24_laptop_control import PACKAGE, APP_PROCESS_NAMES, ValidationError, atomic_json, run_one, read_battery
from d1_a24_laptop_validator import load_json, sha256
from d1_a24_measurement_connection import ReconnectingAdbClient

TARGET_KEYS = frozenset({'device_id','package_name','apk_sha256','adb_serial','manufacturer','model',
    'soc','abi','ram_bytes','android_release','api_level','build_fingerprint','cpu_abi','cpu_features',
    'gpu_vendor','gpu_renderer','gpu_driver','thermal_capability'})


def assemble(job: dict, row: dict, root: Path) -> tuple[dict,dict,dict,dict]:
    sid=row['session_id'];directory=root/'bindings'/sid
    source=Path(job['prepared_manifests'])/(sid+'.json');manifest=copy.deepcopy(load_json(source))
    identity=load_json(Path(job['apk_identity']));target=load_json(Path(job['device_registration']))
    # The app's logical identifier is lowercase. Physical reconnect identity
    # remains a separate case-sensitive hardware_serial and is never normalized.
    if not re.fullmatch(r'[a-z0-9][a-z0-9._-]{0,63}',str(target.get('device_id',''))):
        raise ValidationError('logical device_id is incompatible with the actual app parser')
    target['apk_sha256']=identity['apk_sha256'];target['package_name']=identity['package']
    if not TARGET_KEYS.issubset(target): raise ValidationError('exact app target keys are missing')
    if any(set(spec['target'])!=TARGET_KEYS for spec in manifest['models'].values()):
        raise ValidationError('prepared runtime target shape differs from the actual app contract')
    directory.mkdir(parents=True,exist_ok=False)
    manifest.update(execution_authorized=True,authorization='USER_AUTHORIZED_ACTUAL_MEASUREMENT_20261015',
      device_status='DEVICE_APPROVED_FOR_NEW_CONTRACT',device_binding='ACTUAL_INVENTORY_BOUND_RUNTIME_PENDING',
      device_fingerprint=target['build_fingerprint'],target_model=target['model'],apk_sha256=identity['apk_sha256'],
      soc_contract='USER_SOC_GE10_20261015',minimum_battery_percent=10,
      source_commit=job['source_base_commit'],source_manifest_sha256=sha256(Path(job['source_manifest'])),
      evidence_level='AUTHORIZED_DEVICE_ATTEMPT_NOT_YET_VALIDATED',experiment_ready=False,
      preparation_counters_are_historical=True)
    target['apk_sha256']=identity['apk_sha256']
    target['package_name']=identity['package']
    for model in manifest['models'].values():
        model['target']={key:copy.deepcopy(target[key]) for key in model['target']}
    for name in job['input_filenames']:
        original=Path(job['input_root'])/name
        # Immutable private input bytes; no per-slot 33MB host copies.
        os.link(original,directory/name)
    atomic_json(directory/'session_manifest.json',manifest)
    files=[{'path':p.name,'bytes':p.stat().st_size,'sha256':sha256(p)} for p in sorted(directory.iterdir()) if p.is_file()]
    gate=load_json(Path(job['gate']));gate_bytes=Path(job['gate']).read_bytes()
    config={'manifest_bytes':(directory/'session_manifest.json').read_bytes(),'manifest_sha256':sha256(directory/'session_manifest.json'),
      'gate_bytes':gate_bytes,'gate_sha256':sha256(Path(job['gate'])),'apk':{'path':job['apk'],'sha256':identity['apk_sha256']},
      'adb':{'path':job['adb'],'sha256':sha256(Path(job['adb']))},'apk_identity':identity,'bundle_root':str(directory),'files':files,
      'source_root':job['repo'],'source_code_manifest':job['source_manifest'],'source_code_sha256':sha256(Path(job['source_manifest'])),
      'host_dependency_lock':job['host_dependency_lock'],'host_dependency_lock_sha256':sha256(Path(job['host_dependency_lock'])),
      'registry_root':str(Path(job.get('registry_base',root/'registry'))/manifest['protocol']/manifest['plan_id']),'output_root':str(root/'raw'),
      'reuse_verified_installed_APK':True,'package_name':identity['package'],
      'require_journal_closed_before_recovery':True,
      'perfetto':job.get('perfetto',{})}
    auth={'schema':'a24-laptop-control-authorization-v1','authorization':'USER_EXPLICIT_FUTURE_A24_MEASUREMENT',
      'scope':'one_new_session','session_id':sid,'plan_sha256':manifest['plan_sha256'],'manifest_sha256':config['manifest_sha256'],
      'gate_sha256':config['gate_sha256'],'apk_sha256':identity['apk_sha256'],'serial':target['adb_serial'],
      'fingerprint':target['build_fingerprint'],'expected_model':target['model'],'api_level':target['api_level'],'ram_bytes':target['ram_bytes'],
      'source_code_sha256':config['source_code_sha256'],'host_dependency_lock_sha256':config['host_dependency_lock_sha256'],
      'control_source_sha256':sha256(Path(job['repo'])/'tools/d1_a24_laptop_control.py'),
      'package_name':identity['package'],
      'user_directive':'start; SOC>=10; reconnect<=1200s; solve software errors; never repeat an ambiguous started slot'}
    if manifest.get('perfetto')=='ON':
        auth.update(perfetto_profile_sha256=config['perfetto']['profile_sha256'],perfetto_device_version=config['perfetto']['device_version'])
    if manifest['stage']=='CONFIRM':
        freeze=Path(job['confirm_freeze']);config['confirm_freeze']=str(freeze);auth['confirm_freeze_sha256']=sha256(freeze)
    atomic_json(directory/'authorization.json',auth)
    atomic_json(directory/'execution_config.json',{k:v for k,v in config.items() if not isinstance(v,bytes)})
    return manifest,config,auth,gate


def finish_only_closed_owned_process(client, raw: Path, sid: str, *, package: str = PACKAGE) -> bool:
    if not raw.exists(): return False
    for name in ['identity.json','journal_closed.json','cleanup.json']:
        if not (raw/name).exists(): return False
    identity,closed,cleanup=[load_json(raw/n) for n in ['identity.json','journal_closed.json','cleanup.json']]
    pid=identity.get('process_id')
    if identity.get('session_id')!=sid or closed.get('session_id')!=sid or closed.get('process_id')!=pid or \
       closed.get('status')!='SYNCED_AND_CLOSED' or cleanup.get('status')!='DRAINED' or cleanup.get('actual_return_confirmed') is not True:
        return False
    names=APP_PROCESS_NAMES if package==PACKAGE else (*APP_PROCESS_NAMES,package,package+':model_probe',package+':a24_preparation')
    pids={name:client.command('shell','pidof',name,accepted_codes=(0,1),reject_stderr=True).decode().strip() for name in names}
    for name,present in pids.items():
        if present and (name!=package+':a24_preparation' or present!=str(pid)):
            raise ValidationError('foreign or active process owner; cannot clean up')
    if pids[package+':a24_preparation']:
        client.command('shell','am','force-stop',package)  # Only our proved closed, empty session process.
    return True


def run_batch(job_file: Path, limit: int) -> None:
    job=load_json(job_file);root=Path(job['run_root']);root.mkdir(exist_ok=True)
    plan=load_json(Path(job['plan']));assert sha256(Path(job['plan']))==job['plan_sha256']
    target=load_json(Path(job['device_registration']))
    client=ReconnectingAdbClient(job['adb'],target['adb_serial'],target.get('hardware_serial',target['device_id']),target['build_fingerprint'],root/'measurement_adb_commands.jsonl')
    outcomes=[]
    for row in plan['sessions'][:limit]:
        if row['session_id'] in job.get('skip_failed_slot_ids',[]):
            print(json.dumps({'status':'PRESERVED_FAILED_SLOT_NOT_RETRIED','session_id':row['session_id']}),flush=True);continue
        sid=row['session_id'];state=Path(job.get('registry_base',root/'registry'))/row['protocol']/row['plan_id']/sid
        if state.exists():
            print(json.dumps({'status':'SKIP_EXISTING_ATTEMPT_NO_RERUN','session_id':sid}),flush=True);continue
        if shutil.disk_usage(root).free<1024**3: raise ValidationError('less than1GiB free; preserve all data and stop')
        battery=read_battery(client)
        if battery['SOC_percent'] is None or battery['SOC_percent']<10: raise ValidationError('SOC below10 or unknown; no next slot')
        if row['stage']=='CONFIRM' and not job.get('confirm_freeze'):raise ValidationError('CONFIRM requires actual prior-stage analysis/freeze')
        print(json.dumps({'status':'SLOT_PREPARATION','stage':row['stage'],'arm':row['arm'],'session_id':sid,'SOC_percent':battery['SOC_percent']}),flush=True)
        m,c,a,g=assemble(job,row,root)
        log_file=root/'logcat'/f'{sid}.txt';log_file.parent.mkdir(exist_ok=True)
        import subprocess
        with log_file.open('xb') as log:
            process=subprocess.Popen(client.prefix+['logcat','-v','epoch','-T','1','tflite:V','D1A24PREP:V','*:S'],stdout=log,stderr=subprocess.STDOUT)
            try:
                result=run_one(m,c,a,g,execute_authorized=True,client=client)
                outcome={'session_id':sid,'stage':row['stage'],'arm':row['arm'],'status':result['status'],
                  'actual_adb_calls_cumulative':client.actual_calls,'disconnects':client.disconnects}
            except Exception as error:
                outcome={'session_id':sid,'stage':row['stage'],'arm':row['arm'],'status':'FAILED_OR_REJECTED_PRESERVED','reason':str(error),
                         'actual_adb_calls_cumulative':client.actual_calls,'disconnects':client.disconnects}
            finally:
                process.terminate();process.wait(timeout=10)  # Stop our host logcat collector; never stop a running phone task.
        atomic_json(root/f'{sid}.outcome.json',outcome);outcomes.append(outcome)
        print(json.dumps(outcome),flush=True)
        raw=root/'raw'/sid
        closed=finish_only_closed_owned_process(client,raw,sid,package=c['package_name'])
        if not closed: raise ValidationError('current slot closure unproved; stop rather than kill or relaunch')
        if outcome['status']!='COMPLETE_TRACE_RECOVERED':
            raise ValidationError('slot failed; retain attempt and diagnose before any next registered slot')
        time.sleep(90)  # Planned reservation; next slot still applies full60s observed AP gate.
    atomic_json(root/f'batch_{limit}_completed_{time.time_ns()}.json',{'outcomes':outcomes,'registered_plan_not_rewritten':True})

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('job',type=Path);p.add_argument('--limit',type=int,default=4)
    args=p.parse_args();run_batch(args.job,args.limit)
