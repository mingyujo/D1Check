"""One explicitly authorized eight-arm DEV block, bounded by a new user window.

Default CLI preparation is offline. Never resumes old jobs or repeats a slot.
"""
import argparse
import copy
import datetime
import json
import os
from pathlib import Path
import subprocess

from d1_a24_laptop_validator import load_json, sha256, PROTOCOL
from d1_a24_laptop_plan import encode
from d1_a24_revision02_suite import write_draft, validate_plan, gate_for_registered_row, run_registered_session, RULES
from d1_a24_revision02_suite_control import atomic_json, check_authorization, verify_source_entries, CONTROLLER_SOURCE_FILE, read_battery
from d1_a24_revision02_window import BoundedClient, check_deadline
from d1_a24_measurement_batch import finish_only_closed_owned_process

ROOT = Path(__file__).resolve().parents[1]
META = ROOT / 'output/a24_suite_dev_window01_20261015'
PLAN_ID = 'A24R02-SUITE-DEV-W01-20261015'


def prepare():
    old = load_json(ROOT/'output/a24_revision02_prepared_block04_20261015/job.json')
    summary = write_draft(META/'unapproved_draft', PLAN_ID,
        templates=ROOT/'output/a24_readiness_only_20261015/PC_ONLY_BOUND_MANIFESTS', stage='DEV')
    plan = load_json(META/'unapproved_draft/plan.json')
    plan.update(status='FROZEN_EXECUTION_PLAN', execution_authorized=True,
                user_scope='explicit20261015 new150minute window; DEV8 only within existing64 budget')
    (META/'plan.json').write_bytes(encode(plan))
    plan_sha = sha256(META/'plan.json')
    window = load_json(META/'USER_WINDOW_DRAFT.json');window['plan_sha256'] = plan_sha
    atomic_json(META/'USER_WINDOW.json', window)
    budget = {'authorized':True, 'plan_sha256':plan_sha, 'cap':64, 'spent_before_plan':33,
              'reserved_for_plan':8, 'no_confirmation_budget_increase':True}
    atomic_json(META/'BUDGET.json', budget)
    source = load_json(ROOT/'output/a24_revision02_suite_pc_20261015/SOURCE_SHA256.json')
    for x in source['files']:
        assert sha256(ROOT/x['path']) == x['sha256'], x['path']
    for name in ['tools/d1_a24_suite_dev_window.py',
                 'benchmark-runner/src/testModelProbe/java/com/example/d1check/benchmarkrunner/A24SuiteDeviceManifestPreflightTest.kt']:
        p = ROOT/name
        source['files'].append({'path':name,'bytes':p.stat().st_size,'sha256':sha256(p)})
    source.update(UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  measurement_revision='REV02 suite DEV8 authorized window01',source_uncommitted=True)
    atomic_json(META/'SOURCE_SHA256.json', source)
    source_sha = sha256(META/'SOURCE_SHA256.json')
    contract = {'status':'FROZEN_EXECUTION_CONTRACT','plan_sha256':plan_sha,
        'scope':'one new DEV block8; not independent confirmation','reference_rules':RULES,
        'energy_J':None,'surface_temperature_verified':False,'source_sha256':source_sha,
        'window_sha256':sha256(META/'USER_WINDOW.json'),'budget_sha256':sha256(META/'BUDGET.json'),
        'retry_or_replacement':0,'failure_action':'preserve attempt and stop for diagnosis'}
    atomic_json(META/'EXECUTION_CONTRACT.json', contract)
    gate = load_json(Path(old['gate']))
    gate.update(frozen=True,minimum_SOC_percent=10,maximum_SOC_percent=100,
                soc_contract='USER_SOC_GE10_20261015',require_unplugged=True,
                environment_reviewed=True,screen_contract='manual81/255; awake; unplugged; user supplied new window; no settings mutation')
    atomic_json(META/'BASE_GATE.json', gate)
    (META/'banks').mkdir();(META/'prepared_manifests').mkdir()
    for p in (META/'unapproved_draft/banks').glob('*.json'):
        (META/'banks'/p.name).write_bytes(p.read_bytes())
    for p in (META/'unapproved_draft/manifests').glob('*.json'):
        m = load_json(p)
        m.update(plan_sha256=plan_sha,execution_authorized=True,mock=False,
            authorization='USER_AUTHORIZED_ACTUAL_DEV8_20261015',device_status='DEVICE_APPROVED_FOR_NEW_CONTRACT',
            source_commit='8276115cef062fc59da39c77a2e591ccc0deea4c',source_manifest_sha256=source_sha,
            evidence_level='AUTHORIZED_DEVICE_ATTEMPT_NOT_YET_VALIDATED',created_utc='2026-10-15T05:08:25Z')
        (META/'prepared_manifests'/p.name).write_bytes(encode(m))
    job = copy.deepcopy(old)
    job.update(repo=str(ROOT),plan=str(META/'plan.json'),plan_sha256=plan_sha,
        run_root=str(Path(old['run_root']).parent/'A24R02S1'),prepared_manifests=str(META/'prepared_manifests'),
        source_manifest=str(META/'SOURCE_SHA256.json'),window_file=str(META/'USER_WINDOW.json'),
        revision_contract_file=str(META/'EXECUTION_CONTRACT.json'),budget_file=str(META/'BUDGET.json'),
        gate=str(META/'BASE_GATE.json'),maximum_registered_sessions=8)
    atomic_json(META/'job.json', job)
    atomic_json(META/'ANALYSIS_CONTRACT.json', load_json(ROOT/'output/a24_revision02_prepared_block04_20261015/ANALYSIS_CONTRACT.json'))
    print(json.dumps({'status':'PREPARED_AUTHORIZED_DEV8_NOT_STARTED','sessions':8,'requests':1144,
        'source_files':len(source['files']),'plan_sha256':plan_sha,'device_commands':0,'START':0}))


def assemble(job,row,root):
    m = load_json(Path(job['prepared_manifests'])/(row['session_id']+'.json'))
    directory = root/'bindings'/row['session_id'];directory.mkdir(parents=True,exist_ok=False)
    for name in job['input_filenames']:os.link(Path(job['input_root'])/name,directory/name)
    (directory/'session_manifest.json').write_bytes(encode(m))
    g = gate_for_registered_row(row,load_json(Path(job['gate'])),root)
    atomic_json(directory/'gate.json',g)
    identity=load_json(Path(job['apk_identity']));target=load_json(Path(job['device_registration']))
    c={'manifest_bytes':(directory/'session_manifest.json').read_bytes(),'manifest_sha256':sha256(directory/'session_manifest.json'),
       'gate_bytes':(directory/'gate.json').read_bytes(),'gate_sha256':sha256(directory/'gate.json'),
       'apk':{'path':job['apk'],'sha256':identity['apk_sha256']},'adb':{'path':job['adb'],'sha256':sha256(Path(job['adb']))},
       'apk_identity':identity,'bundle_root':str(directory),
       'files':[{'path':p.name,'bytes':p.stat().st_size,'sha256':sha256(p)} for p in sorted(directory.iterdir()) if p.is_file() and p.name!='gate.json'],
       'source_root':str(ROOT),'source_code_manifest':job['source_manifest'],'source_code_sha256':sha256(Path(job['source_manifest'])),
       'host_dependency_lock':job['host_dependency_lock'],'host_dependency_lock_sha256':sha256(Path(job['host_dependency_lock'])),
       'registry_root':str(root/'registry'/PROTOCOL/PLAN_ID),'output_root':str(root/'raw'),
       'reuse_verified_installed_APK':True,'package_name':identity['package'],'require_journal_closed_before_recovery':True,
       'suite_plan_file':job['plan'],'suite_plan_sha256':job['plan_sha256'],
       'window_file':job['window_file'],'window_sha256':sha256(Path(job['window_file'])),
       'revision_contract_file':job['revision_contract_file'],'revision_contract_sha256':sha256(Path(job['revision_contract_file'])),
       'budget_file':job['budget_file'],'budget_sha256':sha256(Path(job['budget_file']))}
    a={'schema':'a24-laptop-control-authorization-v1','authorization':'USER_EXPLICIT_FUTURE_A24_MEASUREMENT',
       'scope':'one_new_session','session_id':m['session_id'],'plan_sha256':m['plan_sha256'],
       'serial':target['adb_serial'],'fingerprint':target['build_fingerprint'],'expected_model':'SM-A245N',
       'api_level':target['api_level'],'ram_bytes':target['ram_bytes'],'package_name':identity['package'],
       'apk_sha256':identity['apk_sha256'],'control_source_sha256':sha256(CONTROLLER_SOURCE_FILE)}
    for k in ['manifest_sha256','gate_sha256','source_code_sha256','host_dependency_lock_sha256','suite_plan_sha256','window_sha256','revision_contract_sha256','budget_sha256']:a[k]=c[k]
    atomic_json(directory/'authorization.json',a)
    atomic_json(directory/'config.json',{k:v for k,v in c.items() if not isinstance(v,bytes)})
    check_authorization(m,c,a,g,execute_authorized=True)
    return m,c,a,g


def execute():
    job=load_json(META/'job.json');window=load_json(Path(job['window_file']))
    check_deadline(window,'NEW_SESSION')
    pc=load_json(META/'PC_VERIFIED.json')
    assert pc['status']=='PASS_PC_ONLY' and pc['source_sha256']==sha256(Path(job['source_manifest']))
    verify_source_entries(load_json(Path(job['source_manifest'])),ROOT,controller_file=CONTROLLER_SOURCE_FILE)
    plan=load_json(Path(job['plan']));rows=validate_plan(plan);assert len(rows)==8 and plan['stage']=='DEV'
    root=Path(job['run_root']);root.mkdir(exist_ok=False)
    atomic_json(root/'OWNER_WINDOW.json',{'pid':os.getpid(),'window':window,'maximum_attempts':8})
    target=load_json(Path(job['device_registration']));client=BoundedClient(job,target,window)
    assert client.command('shell','getprop','ro.serialno').decode().strip()==target['hardware_serial']
    assert client.command('shell','getprop','ro.build.fingerprint').decode().strip()==target['build_fingerprint']
    battery=read_battery(client);assert battery['SOC_percent']>=10 and battery['plugged'] is False
    screen={k:client.command('shell','settings','get','system',k).decode().strip() for k in ['screen_brightness','screen_brightness_mode','screen_off_timeout']}
    assert screen['screen_brightness']=='81' and screen['screen_brightness_mode']=='0'
    assert 'mWakefulness=Awake' in client.command('shell','dumpsys','power').decode()
    atomic_json(root/'DEVICE_WINDOW_PREFLIGHT.json',{'battery':battery,'screen':screen,'identity_match':True,'settings_changed':False,'physical_environment_measured':False})
    outcomes=[]
    for row in rows:
        try:check_deadline(window,'NEW_SESSION')
        except Exception:break
        m,c,a,g=assemble(job,row,root)
        logpath=root/'logcat'/(row['session_id']+'.txt');logpath.parent.mkdir(exist_ok=True)
        print(json.dumps({'status':'PREPARING_DEV8','recipe':row['recipe'],'arm':row['arm'],'session_id':row['session_id'],'reference_role':row['reference_role']}),flush=True)
        with logpath.open('xb') as log:
            collector=subprocess.Popen(client.prefix+['logcat','-v','epoch','-T','1','tflite:V','D1A24PREP:V','*:S'],stdout=log,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            try:
                result=run_registered_session(m,c,a,g,execute_authorized=True,client=client)
                outcome={**row,'status':result['status'],'actual_ADB_calls_cumulative':client.actual_calls}
            except Exception as error:outcome={**row,'status':'FAILED_PRESERVED','reason':str(error)}
            finally:collector.terminate();collector.wait(timeout=10)
        atomic_json(root/(row['session_id']+'.outcome.json'),outcome);outcomes.append(outcome);print(json.dumps(outcome),flush=True)
        if outcome['status']!='COMPLETE_TRACE_RECOVERED':
            finish_only_closed_owned_process(client,root/'raw'/row['session_id'],row['session_id'],package=c['package_name'])
            break
    atomic_json(root/'WINDOW_STOPPED.json',{'outcomes':outcomes,'maximum8':True,'no_confirmation_started':True,'actual_stop_UTC':datetime.datetime.now(datetime.timezone.utc).isoformat()})
    print(json.dumps({'status':'DEV8_WINDOW_STOPPED','attempts':len(outcomes),'no_confirmation_started':True}),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--prepare',action='store_true');p.add_argument('--execute-authorized',action='store_true');a=p.parse_args()
    if a.prepare and not a.execute_authorized:prepare()
    elif a.execute_authorized and not a.prepare:execute()
    else:p.error('choose offline preparation or explicitly authorized execution')
