"""Explicit DEV-only continuation after a proved host pause before APP2.

Preserve the original 177 files. Only pre-APP cooling changes: a stable colder
phone may prepare. The existing post-warmup MAIN gate is called unchanged.
No failed/started session, no CONFIRM and no additional slot is replayed.
"""
import argparse
import copy
import datetime
import json
import os
from pathlib import Path
import subprocess

from d1_a24_laptop_validator import load_json, sha256, PROTOCOL, NS
from d1_a24_laptop_plan import encode
from d1_a24_revision02_design import first_reference
from d1_a24_revision02_suite import RULES, require, validate_plan, gate_for_registered_row
from d1_a24_revision02_suite_control import (atomic_json, check_authorization,
    verify_source_entries, CONTROLLER_SOURCE_FILE, read_hal, read_battery, run_one)
from d1_a24_revision02_window import BoundedClient, check_deadline
from d1_a24_measurement_batch import finish_only_closed_owned_process

ROOT = Path(__file__).resolve().parents[1]
OLD = ROOT/'output/a24_suite_dev_window01_20261015'
META = ROOT/'output/a24_suite_dev_window01_continuation_20261015'


def cold_enough_to_prepare(samples, tref):
    """Offline predicate, NOT MAIN admission; no lower temperature bound."""
    if len(samples) < 2:
        return False
    cutoff = samples[-1]['before_ns'] - RULES['history_ns']
    starts = [i for i, s in enumerate(samples) if s['before_ns'] <= cutoff]
    if not starts:
        return False
    recent = samples[starts[-1]:]
    stable = first_reference(recent, recent[0]['before_ns'], RULES)
    return stable is not None and all(s['AP_c'] <= tref for s in recent)


def passive_v2(client, gate, evidence):
    if gate['reference_role'] == 'SELECT_FIRST':
        return
    require(not evidence.exists(), 'write-once continuation cooldown evidence')
    evidence.parent.mkdir(exist_ok=True)
    reference = Path(gate['block_reference_path'])
    samples = []
    while True:
        client.check_window('NEW_SESSION')
        require(sha256(reference) == gate['block_reference_sha256'], 'reference changed')
        x = read_hal(client)
        with evidence.open('a', encoding='utf-8') as f:
            f.write(json.dumps(x)+'\n')
        ap = [s['value_c'] for s in x['sensors'] if s['sensor_name']=='AP' and s['sensor_type']==0]
        samples.append({'before_ns':x['device_elapsed_before_ns'], 'after_ns':x['device_elapsed_after_ns'],
                        'AP_c':ap[0] if len(ap)==1 else None})
        if cold_enough_to_prepare(samples, gate['Tref_c']):
            atomic_json(evidence.with_suffix('.ready.json'), {
                'status':'COLD_ENOUGH_TO_PREPARE_ONLY', 'MAIN_admitted':False,
                'post_warmup_MAIN_rules_unchanged':True, 'last_AP_c':ap[0],
                'reference_sha256':sha256(reference), 'samples':len(samples),
                'observed_device_elapsed_s':(samples[-1]['after_ns']-samples[0]['before_ns'])/NS,
                'idle_energy_assumed_zero':False})
            return
        client.sleep_ns(5*NS)


def prepare():
    require(not META.exists(), 'write-once continuation preparation')
    old_job=load_json(OLD/'job.json'); root=Path(old_job['run_root'])
    pause=load_json(root/'HOST_PAUSE_BEFORE_SECOND_APP.json')
    require(pause['actual_app_launches']==1 and pause['cpu_app_started'] is False, 'pause proof differs')
    plan=load_json(Path(old_job['plan'])); rows=validate_plan(plan)
    require(len(rows)==8 and plan['stage']=='DEV', 'DEV8 only')
    source=load_json(Path(old_job['source_manifest']))
    for f in source['files']:
        require(sha256(ROOT/f['path'])==f['sha256'], 'original177 source changed')
    META.mkdir()
    for name in ['tools/d1_a24_suite_dev_continue.py','tools/test_d1_a24_suite_dev_continue.py']:
        p=ROOT/name;source['files'].append({'path':name,'bytes':p.stat().st_size,'sha256':sha256(p)})
    source.update(measurement_revision='DEV8 continuation v2; pre-APP cold lower-bound repair',
        source_uncommitted=True, UTC=datetime.datetime.now(datetime.timezone.utc).isoformat())
    atomic_json(META/'SOURCE_SHA256.json',source)
    budget=load_json(OLD/'BUDGET.json');budget.update(cap=81,no_confirmation_budget_increase=False,
        approval='USER_EXPLICIT_81: prior33 + DEV8 + new CONFIRM40; current DEV plan includes already completed GPU1',
        already_consumed_within_this_plan=1,remaining_in_this_plan=7,confirmation_reserved_after_DEV=40)
    atomic_json(META/'BUDGET.json',budget)
    window=load_json(OLD/'USER_WINDOW.json');window['scope']='same original150minute window, remaining7 unstarted DEV arms; total budget81 approved; no CONFIRM in this driver'
    atomic_json(META/'USER_WINDOW.json',window)
    contract=load_json(OLD/'EXECUTION_CONTRACT.json')
    contract.update(source_sha256=sha256(META/'SOURCE_SHA256.json'),budget_sha256=sha256(META/'BUDGET.json'),
        window_sha256=sha256(META/'USER_WINDOW.json'),scope='DEV8 carry-over: GPU1 preserved, remaining7 only',
        preparation_amendment='v2: stable60s at AP<=Tref may prepare even if colder than Tref-0.5; never MAIN admission',
        main_admission_changed=False,original177_source_sha256=sha256(OLD/'SOURCE_SHA256.json'),
        original_GPU_host_revision_preserved=True,policy_or_requests_changed=False,
        formal_confirmation_not_started=True)
    atomic_json(META/'EXECUTION_CONTRACT.json',contract)
    (META/'prepared_manifests').mkdir()
    for row in rows:
        m=load_json(Path(old_job['prepared_manifests'])/(row['session_id']+'.json'))
        if row['plan_ordinal']>0:
            m.update(source_manifest_sha256=sha256(META/'SOURCE_SHA256.json'),
                     source_commit='ae5345ace9950a556214d0eff40cb70320cf9fb7',
                     host_continuation='PRE_APP_COOLING_V2_MAIN_UNCHANGED')
        (META/'prepared_manifests'/(row['session_id']+'.json')).write_bytes(encode(m))
    job=copy.deepcopy(old_job)
    job.update(source_manifest=str(META/'SOURCE_SHA256.json'),prepared_manifests=str(META/'prepared_manifests'),
               window_file=str(META/'USER_WINDOW.json'),budget_file=str(META/'BUDGET.json'),
               revision_contract_file=str(META/'EXECUTION_CONTRACT.json'),
               quality_references=str(ROOT/'output/a24_measurement_20261015_v1/quality_references_v1.json'))
    atomic_json(META/'job.json',job)
    atomic_json(META/'ANALYSIS_CONTRACT.json',load_json(OLD/'ANALYSIS_CONTRACT.json'))
    print(json.dumps({'status':'PREPARED_NOT_STARTED','preserved_GPU':1,'unstarted_DEV':7,'source_files':len(source['files']),'device_commands':0}))


def assemble(job,row,root):
    m=load_json(Path(job['prepared_manifests'])/(row['session_id']+'.json'))
    directory=root/'bindings_v2'/row['session_id'];directory.mkdir(parents=True,exist_ok=False)
    for name in job['input_filenames']:os.link(Path(job['input_root'])/name,directory/name)
    (directory/'session_manifest.json').write_bytes(encode(m))
    g=gate_for_registered_row(row,load_json(Path(job['gate'])),root);atomic_json(directory/'gate.json',g)
    identity=load_json(Path(job['apk_identity']));target=load_json(Path(job['device_registration']))
    c={'manifest_bytes':(directory/'session_manifest.json').read_bytes(),'manifest_sha256':sha256(directory/'session_manifest.json'),
       'gate_bytes':(directory/'gate.json').read_bytes(),'gate_sha256':sha256(directory/'gate.json'),
       'apk':{'path':job['apk'],'sha256':identity['apk_sha256']},'adb':{'path':job['adb'],'sha256':sha256(Path(job['adb']))},
       'apk_identity':identity,'bundle_root':str(directory),
       'files':[{'path':p.name,'bytes':p.stat().st_size,'sha256':sha256(p)} for p in sorted(directory.iterdir()) if p.is_file() and p.name!='gate.json'],
       'source_root':str(ROOT),'source_code_manifest':job['source_manifest'],'source_code_sha256':sha256(Path(job['source_manifest'])),
       'host_dependency_lock':job['host_dependency_lock'],'host_dependency_lock_sha256':sha256(Path(job['host_dependency_lock'])),
       'registry_root':str(root/'registry'/PROTOCOL/m['plan_id']),'output_root':str(root/'raw'),
       'reuse_verified_installed_APK':True,'package_name':identity['package'],'require_journal_closed_before_recovery':True}
    for key,sha_key in [('suite_plan_file','suite_plan_sha256'),('window_file','window_sha256'),
                        ('revision_contract_file','revision_contract_sha256'),('budget_file','budget_sha256')]:
        path=job['plan'] if key=='suite_plan_file' else job[key]
        c[key]=path;c[sha_key]=sha256(Path(path))
    a={'schema':'a24-laptop-control-authorization-v1','authorization':'USER_EXPLICIT_FUTURE_A24_MEASUREMENT',
       'scope':'one_new_session','session_id':m['session_id'],'plan_sha256':m['plan_sha256'],
       'serial':target['adb_serial'],'fingerprint':target['build_fingerprint'],'expected_model':'SM-A245N',
       'api_level':target['api_level'],'ram_bytes':target['ram_bytes'],'package_name':identity['package'],
       'apk_sha256':identity['apk_sha256'],'control_source_sha256':sha256(CONTROLLER_SOURCE_FILE)}
    for key in ['manifest_sha256','gate_sha256','source_code_sha256','host_dependency_lock_sha256',
                'suite_plan_sha256','window_sha256','revision_contract_sha256','budget_sha256']:a[key]=c[key]
    atomic_json(directory/'authorization.json',a)
    atomic_json(directory/'config.json',{k:v for k,v in c.items() if not isinstance(v,bytes)})
    check_authorization(m,c,a,g,execute_authorized=True)
    return m,c,a,g


def execute():
    job=load_json(META/'job.json');root=Path(job['run_root']);window=load_json(Path(job['window_file']))
    pc=load_json(META/'PC_VERIFIED.json');require(pc['status']=='PASS_PC_ONLY' and pc['source_sha256']==sha256(Path(job['source_manifest'])),'PC proof absent/changed')
    verify_source_entries(load_json(Path(job['source_manifest'])),ROOT,controller_file=CONTROLLER_SOURCE_FILE)
    rows=validate_plan(load_json(Path(job['plan'])));require(len(rows)==8 and rows[0]['arm']=='GPU','DEV scope differs')
    completed=load_json(root/(rows[0]['session_id']+'.outcome.json'))
    require(completed['status']=='COMPLETE_TRACE_RECOVERED','first GPU not recovered')
    require(not (root/'OWNER_CONTINUATION_V2.json').exists(),'continuation already attempted')
    atomic_json(root/'OWNER_CONTINUATION_V2.json',{'pid':os.getpid(),'window':window,'GPU_not_replayed':True,'maximum_remaining_APP':7})
    target=load_json(Path(job['device_registration']));client=BoundedClient(job,target,window)
    require(client.command('shell','getprop','ro.serialno').decode().strip()==target['hardware_serial'],'physical target differs')
    require(client.command('shell','getprop','ro.build.fingerprint').decode().strip()==target['build_fingerprint'],'fingerprint differs')
    b=read_battery(client);require(b['SOC_percent']>=10 and b['plugged'] is False,'battery/charging differs')
    require(client.command('shell','settings','get','system','screen_brightness').decode().strip()=='81','brightness differs')
    require(client.command('shell','settings','get','system','screen_brightness_mode').decode().strip()=='0','brightness mode differs')
    require('mWakefulness=Awake' in client.command('shell','dumpsys','power').decode(),'not awake')
    outcomes=[]
    try:
        for row in rows[1:]:
            check_deadline(window,'NEW_SESSION')
            sid=row['session_id']
            require(not (root/(sid+'.outcome.json')).exists() and not (root/'registry'/PROTOCOL/row['plan_id']/sid).exists() and not (root/'raw'/sid).exists(),'already attempted; no replay')
            m,c,a,g=assemble(job,row,root)
            print(json.dumps({'status':'PREPARING_CONTINUATION_V2','recipe':row['recipe'],'arm':row['arm'],'session_id':sid}),flush=True)
            logpath=root/'logcat'/(sid+'.v2.txt')
            with logpath.open('xb') as log:
                collector=subprocess.Popen(client.prefix+['logcat','-v','epoch','-T','1','tflite:V','D1A24PREP:V','*:S'],stdout=log,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                try:
                    passive_v2(client,g,root/'pre_app_cooldown_v2'/(sid+'.jsonl'))
                    result=run_one(m,c,a,g,execute_authorized=True,client=client)
                    if result['status']=='COMPLETE_TRACE_RECOVERED':
                        require(finish_only_closed_owned_process(client,root/'raw'/sid,sid,package=c['package_name']),'closed empty process not proved')
                    outcome={**row,'status':result['status'],'host_continuation':'V2','actual_ADB_calls_continuation':client.actual_calls}
                except Exception as error:
                    outcome={**row,'status':'FAILED_PRESERVED','reason':str(error),'host_continuation':'V2'}
                finally:collector.terminate();collector.wait(timeout=10)
            # Keep old aborted pre-APP collector evidence; canonical analysis log is this actual attempt.
            canonical=root/'logcat'/(sid+'.txt')
            if canonical.exists():canonical.rename(root/'logcat'/(sid+'.pre_app_aborted_v1.txt'))
            canonical.write_bytes(logpath.read_bytes())
            atomic_json(root/(sid+'.outcome.json'),outcome);outcomes.append(outcome);print(json.dumps(outcome),flush=True)
            if outcome['status']!='COMPLETE_TRACE_RECOVERED':
                finish_only_closed_owned_process(client,root/'raw'/sid,sid,package=c['package_name']);break
    finally:
        atomic_json(root/'WINDOW_CONTINUATION_V2_STOPPED.json',{'outcomes':outcomes,'preserved_GPU1':True,
            'no_confirmation_started':True,'actual_stop_UTC':datetime.datetime.now(datetime.timezone.utc).isoformat()})


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--prepare',action='store_true');p.add_argument('--execute-authorized',action='store_true');a=p.parse_args()
    if a.prepare and not a.execute_authorized:prepare()
    elif a.execute_authorized and not a.prepare:execute()
    else:p.error('choose offline preparation or explicitly authorized continuation')
