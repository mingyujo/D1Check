"""A separately bound coordinator for an already frozen40-session core contract.

Default CLI is read-only PC inspection. A visit executes only the exact session
prefix named in its frozen window. Core179, this coordinator and PC evidence are
separately hashed: adding a coordinator is not eight new device validations.
"""
import argparse
import datetime
import json
import os
from pathlib import Path
import subprocess

from d1_a24_laptop_validator import load_json, sha256, PROTOCOL
from d1_a24_laptop_plan import encode
from d1_a24_revision02_suite import require, validate_plan, gate_for_registered_row
from d1_a24_revision02_suite_control import (atomic_json, check_authorization,
    verify_source_entries, CONTROLLER_SOURCE_FILE, read_battery, run_one)
from d1_a24_revision02_window import BoundedClient, check_deadline
from d1_a24_suite_dev_continue import passive_v2
from d1_a24_measurement_batch import finish_only_closed_owned_process

ROOT=Path(__file__).resolve().parents[1]
DOCUMENTS=[('suite_plan_file','suite_plan_sha256'),('window_file','window_sha256'),
 ('revision_contract_file','revision_contract_sha256'),('budget_file','budget_sha256'),
 ('confirm_freeze','confirm_freeze_sha256'),('analysis_contract','analysis_contract_sha256'),
 ('pre_measurement_predictions','pre_measurement_predictions_sha256'),
 ('prior_stage_ledger','prior_stage_ledger_sha256'),
 ('new_protocol_functional_evidence','new_protocol_functional_evidence_sha256')]


def scoped_rows(plan, window):
    rows=validate_plan(plan)
    require(plan['stage']=='CONFIRM' and len(rows)==40,'full independent40 plan required')
    ids=window.get('registered_session_ids',[])
    require(ids and len(ids)==len(set(ids)),'nonempty exact visit scope required')
    selected=[r for r in rows if r['session_id'] in ids]
    require([r['session_id'] for r in selected]==ids,'unknown/unordered window session')
    require([r['plan_ordinal'] for r in selected]==list(range(selected[0]['plan_ordinal'],selected[0]['plan_ordinal']+len(selected))),'noncontiguous window scope')
    return selected


def assemble(job,row,root):
    m=load_json(Path(job['prepared_manifests'])/(row['session_id']+'.json'))
    directory=root/'bindings'/row['session_id'];directory.mkdir(parents=True,exist_ok=False)
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
    for key,sha_key in DOCUMENTS:
        path=job['plan'] if key=='suite_plan_file' else job[key]
        c[key]=path;c[sha_key]=sha256(Path(path))
    a={'schema':'a24-laptop-control-authorization-v1','authorization':'USER_EXPLICIT_FUTURE_A24_MEASUREMENT',
       'scope':'one_new_session','session_id':m['session_id'],'plan_sha256':m['plan_sha256'],
       'serial':target['adb_serial'],'fingerprint':target['build_fingerprint'],'expected_model':'SM-A245N',
       'api_level':target['api_level'],'ram_bytes':target['ram_bytes'],'package_name':identity['package'],
       'apk_sha256':identity['apk_sha256'],'control_source_sha256':sha256(CONTROLLER_SOURCE_FILE)}
    for key in ['manifest_sha256','gate_sha256','source_code_sha256','host_dependency_lock_sha256']+[s for _,s in DOCUMENTS]:a[key]=c[key]
    atomic_json(directory/'authorization.json',a)
    atomic_json(directory/'config.json',{k:v for k,v in c.items() if not isinstance(v,bytes)})
    check_authorization(m,c,a,g,execute_authorized=True)
    return m,c,a,g


def inspect(job):
    window=load_json(Path(job['window_file']));plan=load_json(Path(job['plan']));rows=scoped_rows(plan,window)
    contract=load_json(Path(job['revision_contract_file']))
    require(contract.get('coordinator_sha256')==sha256(Path(__file__)),'coordinator bytes not frozen')
    pc=load_json(Path(job['coordinator_PC_verification']))
    require(pc.get('status')=='PASS_PC_ONLY' and pc.get('coordinator_sha256')==sha256(Path(__file__)) and pc.get('plan_sha256')==sha256(Path(job['plan'])),'exact coordinator PC proof missing')
    require(pc.get('full40_authorization_contexts_PASS')==40,'not all40 bindings checked')
    verify_source_entries(load_json(Path(job['source_manifest'])),ROOT,controller_file=CONTROLLER_SOURCE_FILE)
    require(contract.get('core_source_sha256')==sha256(Path(job['source_manifest'])),'core source differs')
    require(contract.get('visit_session_ids')==window['registered_session_ids'],'window scope differs')
    return rows,window


def execute(job):
    rows,window=inspect(job);check_deadline(window,'NEW_SESSION');root=Path(job['run_root'])
    # The first visit is write-once. Future visits require a separately registered
    # window/owner, not rerunning this first-visit root or a completed session.
    require(not root.exists(),'visit root already exists; never replay this visit')
    root.mkdir()
    atomic_json(root/'OWNER_WINDOW.json',{'pid':os.getpid(),'window':window,'coordinator_sha256':sha256(Path(__file__))})
    target=load_json(Path(job['device_registration']));client=BoundedClient(job,target,window)
    require(client.command('shell','getprop','ro.serialno').decode().strip()==target['hardware_serial'],'physical target differs')
    require(client.command('shell','getprop','ro.build.fingerprint').decode().strip()==target['build_fingerprint'],'fingerprint differs')
    b=read_battery(client);require(b['SOC_percent']>=10 and b['plugged'] is False,'battery/charging differs')
    require(client.command('shell','settings','get','system','screen_brightness').decode().strip()=='81','brightness differs')
    require(client.command('shell','settings','get','system','screen_brightness_mode').decode().strip()=='0','brightness mode differs')
    require('mWakefulness=Awake' in client.command('shell','dumpsys','power').decode(),'not awake')
    outcomes=[]
    try:
        for row in rows:
            check_deadline(window,'NEW_SESSION');sid=row['session_id']
            require(not (root/'registry'/PROTOCOL/row['plan_id']/sid).exists() and not (root/'raw'/sid).exists(),'already attempted')
            m,c,a,g=assemble(job,row,root)
            print(json.dumps({'status':'PREPARING_NEW_CONFIRM','recipe':row['recipe'],'arm':row['arm'],'session_id':sid}),flush=True)
            logpath=root/'logcat'/(sid+'.txt');logpath.parent.mkdir(exist_ok=True)
            with logpath.open('xb') as log:
                collector=subprocess.Popen(client.prefix+['logcat','-v','epoch','-T','1','tflite:V','D1A24PREP:V','*:S'],stdout=log,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                try:
                    passive_v2(client,g,root/'pre_app_cooldown_v2'/(sid+'.jsonl'))
                    result=run_one(m,c,a,g,execute_authorized=True,client=client)
                    if result['status']=='COMPLETE_TRACE_RECOVERED':
                        require(finish_only_closed_owned_process(client,root/'raw'/sid,sid,package=c['package_name']),'closed empty process not proved')
                    outcome={**row,'status':result['status'],'actual_ADB_calls_this_visit':client.actual_calls}
                except Exception as error:outcome={**row,'status':'FAILED_PRESERVED','reason':str(error)}
                finally:collector.terminate();collector.wait(timeout=10)
            atomic_json(root/(sid+'.outcome.json'),outcome);outcomes.append(outcome);print(json.dumps(outcome),flush=True)
            if outcome['status']!='COMPLETE_TRACE_RECOVERED':
                finish_only_closed_owned_process(client,root/'raw'/sid,sid,package=c['package_name']);break
    finally:
        atomic_json(root/'WINDOW_STOPPED.json',{'outcomes':outcomes,'full_confirmation_plan':40,
            'registered_this_visit':len(rows),'confirmation_complete_not_assumed':True,
            'actual_stop_UTC':datetime.datetime.now(datetime.timezone.utc).isoformat()})


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('job',type=Path);p.add_argument('--execute-authorized',action='store_true');a=p.parse_args()
    job=load_json(a.job)
    if a.execute_authorized:execute(job)
    else:
        rows,_=inspect(job);print(json.dumps({'status':'PC_INSPECT_ONLY','registered_visit':len(rows),'full_confirmation':40,'device_commands':0}))
