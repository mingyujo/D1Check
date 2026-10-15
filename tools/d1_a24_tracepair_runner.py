"""Fresh bounded OFF/ON path repair; no replay of the old failed ON session."""
import argparse
import copy
import datetime as dt
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

import d1_a24_tracepair_control as control
from d1_a24_tracepair_contract import PLAN_ID,ROLE,KEYS,validate_plan
from d1_a24_laptop_plan import identity
from d1_a24_laptop_validator import PROTOCOL,load_json,manifest_requests,sha256
from d1_a24_revision02_suite import RULES,gate_for_registered_row,require
from d1_a24_revision02_window import check_deadline
from d1_a24_confirm_after_diagnostic import FollowupClient
from d1_a24_measurement_batch import finish_only_closed_owned_process
from d1_a24_supplement_runner import passive_before_APP,require_no_prior_owners

ROOT=Path(__file__).resolve().parents[1]
DOCS=[('window_file','window_sha256'),('revision_contract_file','revision_contract_sha256'),
      ('budget_file','budget_sha256'),('analysis_contract','analysis_contract_sha256')]
SOURCE_FILES=['tools/d1_a24_tracepair_contract.py','tools/d1_a24_tracepair_control.py',
              'tools/d1_a24_tracepair_runner.py','tools/test_d1_a24_tracepair.py']


def lifecycle_identity():
    old=(ROOT/'tools/d1_a24_revision02_suite_control.py').read_text(encoding='utf-8')
    expected=old.replace('from d1_a24_revision02_suite import validate_suite_registration',
        'from d1_a24_tracepair_contract import validate_registration as validate_suite_registration').replace(
        'tools/d1_a24_revision02_suite_control.py','tools/d1_a24_tracepair_control.py').replace(
        'REV02 eight-arm suite controller; preserved pilot lifecycle with separate guards.',
        'Matched OFF/ON path repair; original scheduling lifecycle and trace profile preserved.')
    expected=expected.replace('/data/local/tmp/a24-{session_id}-perfetto.pbtxt','/data/misc/perfetto-configs/a24-{session_id}-perfetto.pbtxt')
    require(control.CONTROLLER_SOURCE_FILE.read_text(encoding='utf-8')==expected,'common lifecycle changed')
    return {'status':'PASS_ORIGINAL_RUNTIME_WITH_TRACE_CONFIG_PATH_FIX','only_import_self_path_docstring_and_config_directory_differ':True}


def assemble(job,row,root):
    m=load_json(Path(job['prepared_manifests'])/(row['session_id']+'.json'))
    directory=root/'bindings'/row['session_id'];directory.mkdir(parents=True,exist_ok=False)
    for name in job['input_filenames']:os.link(Path(job['input_root'])/name,directory/name)
    control.atomic_json(directory/'session_manifest.json',m)
    g=gate_for_registered_row(row,load_json(Path(job['gate'])),root);control.atomic_json(directory/'gate.json',g)
    ident=load_json(Path(job['apk_identity']));target=load_json(Path(job['device_registration']))
    c={'manifest_bytes':(directory/'session_manifest.json').read_bytes(),'manifest_sha256':sha256(directory/'session_manifest.json'),
       'gate_bytes':(directory/'gate.json').read_bytes(),'gate_sha256':sha256(directory/'gate.json'),
       'apk':{'path':job['apk'],'sha256':ident['apk_sha256']},'adb':{'path':job['adb'],'sha256':sha256(Path(job['adb']))},
       'apk_identity':ident,'bundle_root':str(directory),'files':[{'path':p.name,'bytes':p.stat().st_size,'sha256':sha256(p)}
           for p in sorted(directory.iterdir()) if p.is_file() and p.name!='gate.json'],
       'source_root':str(ROOT),'source_code_manifest':job['source_manifest'],'source_code_sha256':sha256(Path(job['source_manifest'])),
       'host_dependency_lock':job['host_dependency_lock'],'host_dependency_lock_sha256':sha256(Path(job['host_dependency_lock'])),
       'registry_root':str(root/'registry'/PROTOCOL/PLAN_ID),'output_root':str(root/'raw'),
       'reuse_verified_installed_APK':True,'package_name':ident['package'],'require_journal_closed_before_recovery':True,
       'suite_plan_file':job['plan'],'suite_plan_sha256':sha256(Path(job['plan'])),'perfetto':job['perfetto']}
    for key,digest in DOCS:c[key]=job[key];c[digest]=sha256(Path(job[key]))
    a={'schema':'a24-laptop-control-authorization-v1','authorization':'USER_EXPLICIT_FUTURE_A24_MEASUREMENT',
       'scope':'one_new_session','session_id':m['session_id'],'plan_sha256':m['plan_sha256'],
       'serial':target['adb_serial'],'fingerprint':target['build_fingerprint'],'expected_model':'SM-A245N',
       'api_level':target['api_level'],'ram_bytes':target['ram_bytes'],'package_name':ident['package'],
       'apk_sha256':ident['apk_sha256'],'control_source_sha256':sha256(control.CONTROLLER_SOURCE_FILE)}
    for k in ['manifest_sha256','gate_sha256','source_code_sha256','host_dependency_lock_sha256','suite_plan_sha256']+[v for _,v in DOCS]:a[k]=c[k]
    if m['perfetto']=='ON':a.update(perfetto_profile_sha256=c['perfetto']['profile_sha256'],perfetto_device_version=c['perfetto']['device_version'])
    control.atomic_json(directory/'authorization.json',a)
    control.atomic_json(directory/'config.json',{k:v for k,v in c.items() if not isinstance(v,bytes)})
    control.check_authorization(m,c,a,g,execute_authorized=True)
    return m,c,a,g


def execute(job):
    rows=inspect(job);window=load_json(Path(job['window_file']));check_deadline(window,'NEW_SESSION')
    root=Path(job['run_root']);globalroot=Path(job['tracepair_global_root']);require_no_prior_owners(root.parent)
    globalroot.mkdir();control.atomic_json(globalroot/'ACTIVE_OWNER.json',{'pid':os.getpid(),'trace_path_repair_pair':True})
    root.mkdir();control.atomic_json(root/'OWNER_WINDOW.json',{'pid':os.getpid(),'window':window,'runner_sha256':sha256(Path(__file__))})
    client=None;outcomes=[];reason='TRACEPAIR2_FINISHED'
    try:
        client=FollowupClient(job,load_json(Path(job['device_registration'])),window,globalroot,{'total_consumed':103,'cap':105})
        client.job_run_root=str(root);client.reconnect()
        for row in rows:
            sid=row['session_id'];client.check_window('NEW_SESSION');m,c,a,g=assemble(job,row,root)
            print(json.dumps({'status':'PREPARING_MATCHED_TRACE_PATH_PAIR','session_id':sid,'prescription':row['prescription_id']}),flush=True)
            if row['reference_role']=='MATCH_FIXED':
                try:passive_before_APP(client,g,root/'pre_app_cooldown_v2'/(sid+'.jsonl'))
                except Exception as error:
                    control.atomic_json(root/(sid+'.preapp_stop.json'),{'APP':0,'reason':str(error),'binding_created':True})
                    reason='PRE_APP_STOP_PRESERVED';break
            reservation=globalroot/'reservations'/sid;reservation.mkdir(parents=True,exist_ok=False)
            control.atomic_json(reservation/'RESERVED.json',{'session_id':sid,'matched_group':row['recipe']});client.active_sid=sid
            logfile=root/'logcat'/(sid+'.txt');logfile.parent.mkdir(exist_ok=True)
            with logfile.open('xb') as stream:
                collector=subprocess.Popen(client.prefix+['logcat','-v','epoch','-T','1','tflite:V','D1A24PREP:V','*:S'],
                    stdout=stream,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                try:
                    result=control.run_one(m,c,a,g,execute_authorized=True,client=client)
                    if result['status']=='COMPLETE_TRACE_RECOVERED':
                        require(finish_only_closed_owned_process(client,root/'raw'/sid,sid,package=c['package_name']),'closed cleanup unproved')
                    outcome={**row,'status':result['status']}
                except Exception as error:outcome={**row,'status':'FAILED_PRESERVED','reason':str(error)}
                finally:collector.terminate();collector.wait(timeout=10)
            outcome['APP_launch_intent']=(reservation/'APP_LAUNCH_INTENT.json').exists()
            control.atomic_json(root/(sid+'.outcome.json'),outcome);control.atomic_json(reservation/'OUTCOME.json',outcome);outcomes.append(outcome)
            print(json.dumps(outcome),flush=True)
            if outcome['status']!='COMPLETE_TRACE_RECOVERED':reason='FAILED_NEW_COHORT_PRESERVED';break
    except Exception as error:reason='MATCHED_COHORT_STOP_PRESERVED: '+str(error)
    finally:
        control.atomic_json(root/'WINDOW_STOPPED.json',{'outcomes':outcomes,'reason':reason,'actual_stop_UTC':dt.datetime.now(dt.timezone.utc).isoformat(),
            'new_APP_intents':len(list((globalroot/'reservations').glob('*/APP_LAUNCH_INTENT.json'))),
            'actual_ADB_calls':client.actual_calls if client else 0,'additional_cap':2,'old_failures_replaced':False})
        require(load_json(globalroot/'ACTIVE_OWNER.json')['pid']==os.getpid(),'foreign owner');(globalroot/'ACTIVE_OWNER.json').unlink()


def prepare(template,folder,device_stop,work_stop):
    require(not folder.exists(),'fresh metadata required');job=load_json(template);oldplan=load_json(Path(job['plan']))
    core=ROOT/'output/a24_suite_dev_window01_continuation_20261015/SOURCE_SHA256.json'
    source=load_json(Path(job['source_manifest']));require(len(source['files'])==183,'use preserved original supplement183')
    for x in source['files']:
        p=ROOT/x['path'];require(p.stat().st_size==x['bytes'] and sha256(p)==x['sha256'],'preserved source changed')
    for name in SOURCE_FILES:
        p=ROOT/name;require(name not in {x['path'] for x in source['files']},'duplicate source')
        source['files'].append({'path':name,'bytes':p.stat().st_size,'sha256':sha256(p)})
    folder.mkdir(parents=True);(folder/'banks').mkdir();(folder/'prepared_manifests').mkdir()
    control.atomic_json(folder/'SOURCE_SHA256.json',source);rows=[];bodies=[]
    for i,key in enumerate(KEYS):
        old=oldplan['sessions'][2+i];require(old['prescription_id']==key,'wrong original trace pair')
        m=load_json(Path(job['prepared_manifests'])/(old['session_id']+'.json'));bank=Path(job['plan']).parent/old['bank_file']
        require(sha256(bank)==old['bank_sha256'],'original bank changed');dest=folder/'banks/TRACE.json'
        if dest.exists():require(sha256(dest)==sha256(bank),'paired input differs')
        else:shutil.copyfile(bank,dest)
        row=copy.deepcopy(old);sid=identity(PLAN_ID,key)
        row.update(session_id=sid,plan_id=PLAN_ID,plan_ordinal=i,stage='DEV',block='TRACE_REPAIR',policy_id='TRACE_PATH_REPAIR_'+key,
            bank_file='banks/TRACE.json',gate_block_id=PLAN_ID+'-TRACE',reference_owner_session_id=identity(PLAN_ID,KEYS[0]),
            reference_role='SELECT_FIRST' if i==0 else 'MATCH_FIXED')
        m.update(row);m.update(source_manifest_sha256=sha256(folder/'SOURCE_SHA256.json'),
            source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip(),
            execution_authorized=True,mock=False,device_status='DEVICE_APPROVED_FOR_NEW_CONTRACT',experiment_ready=False)
        for spec in m['models'].values():spec['identity']['session_id']=sid
        rows.append(row);bodies.append(m)
    plan={'schema':'a24-trace-config-path-repair2-v1','plan_id':PLAN_ID,'analysis_role':ROLE,'session_count':2,'sessions':rows,
        'status':'FROZEN_EXECUTION_PLAN','execution_authorized':True,'reference_rules':RULES,
        'pooled_with_original_confirm':False,'old_failures_preserved':True,
        'repair_of_failed_session_id':'cdab3ce2-79b8-5704-8e79-298a8c322f4b','maximum_attempts_per_new_ID':1}
    validate_plan(plan);control.atomic_json(folder/'plan.json',plan)
    for m in bodies:
        m['plan_sha256']=sha256(folder/'plan.json');manifest_requests(m,require_materials=True)
        control.atomic_json(folder/'prepared_manifests'/(m['session_id']+'.json'),m)
    device=dt.datetime.fromisoformat(device_stop);work=dt.datetime.fromisoformat(work_stop)
    require((work-device).total_seconds()>=300,'reserve final5min')
    window={'execution_authorized':True,'hard_stop_UTC':device.isoformat(),'work_stop_UTC':work.isoformat(),
        'registered_session_ids':[r['session_id'] for r in rows],'plan_sha256':sha256(folder/'plan.json'),
        'reserved_final_minutes':5,'maximum_attempts_this_window':2,'scope':ROLE}
    check_deadline(window,'NEW_SESSION');control.atomic_json(folder/'USER_WINDOW.json',window)
    budget={'authorized':True,'previous103_preserved':True,'additional_cap':2,'reserved_for_plan':2,
        'combined_accounting_ceiling':105,'plan_sha256':sha256(folder/'plan.json'),
        'authority':'Latest user explicitly requested autonomous error resolution and completion; bounded fresh matched control plus corrected ON, not directly user-specified105 or unlimited retry.'}
    control.atomic_json(folder/'BUDGET.json',budget)
    analysis={'frozen':True,'analysis_role':ROLE,'pooled_with_original_confirm':False,'energy_J':None,
        'AP_window_seconds':[35,180],'maximum_AP_gap_seconds':10,'service_window_seconds':[0,120],
        'surface_temperature_verified':False,'all_planned_and_failed_requests_reported':True,
        'trace_sources_and_loss_not_assumed_valid':'Capture bytes and source/loss validation are separate',
        'same_profile_SHA_and210s64MiB_bound':True,'first_OFF_reference_shared_with_ON':True}
    control.atomic_json(folder/'ANALYSIS_CONTRACT.json',analysis);life=lifecycle_identity()
    control.atomic_json(folder/'LIFECYCLE_IDENTITY.json',life)
    contract={'status':'FROZEN_EXECUTION_CONTRACT','plan_sha256':sha256(folder/'plan.json'),'reference_rules':RULES,
        'energy_J':None,'surface_temperature_verified':False,'original_core179_unchanged':True,'original_core179_sha256':sha256(core),
        'only_runtime_difference':'Perfetto config directory: documented Android12+ path',
        'controller_sha256':sha256(control.CONTROLLER_SOURCE_FILE),'source_sha256':sha256(folder/'SOURCE_SHA256.json'),
        'runner_sha256':sha256(Path(__file__)),'budget_sha256':sha256(folder/'BUDGET.json'),
        'window_sha256':sha256(folder/'USER_WINDOW.json'),'analysis_sha256':sha256(folder/'ANALYSIS_CONTRACT.json')}
    control.atomic_json(folder/'EXECUTION_CONTRACT.json',contract)
    job.update(plan=str(folder/'plan.json'),prepared_manifests=str(folder/'prepared_manifests'),source_manifest=str(folder/'SOURCE_SHA256.json'),
        plan_sha256=sha256(folder/'plan.json'),window_file=str(folder/'USER_WINDOW.json'),budget_file=str(folder/'BUDGET.json'),
        analysis_contract=str(folder/'ANALYSIS_CONTRACT.json'),revision_contract_file=str(folder/'EXECUTION_CONTRACT.json'),
        run_root=str(Path(job['run_root']).parent/'A24TRACE2'),tracepair_global_root=str(Path(job['run_root']).parent/'A24TRACE2_GLOBAL'),
        tracepair_PC_verification=str(folder/'PC_VERIFICATION.json'))
    control.atomic_json(folder/'job.json',job)
    with tempfile.TemporaryDirectory(prefix='PC_ONLY_',dir=folder) as tmp:
        scratch=Path(tmp);cases=[]
        for row in rows:
            _,c,_,_=assemble(job,row,scratch);cases.append({'session_id':row['session_id'],'manifest_sha256':c['manifest_sha256']})
            if row['reference_role']=='SELECT_FIRST':
                ref=scratch/'references'/(row['gate_block_id']+'.json');ref.parent.mkdir(exist_ok=True)
                control.atomic_json(ref,{'block_id':row['gate_block_id'],'reference_session_id':row['session_id'],
                    'Tref_c':28.5,'frozen_before_any_main_request':True,'PC_MOCK_ONLY':True})
    control.atomic_json(folder/'PC_VERIFICATION.json',{'status':'PASS_PC_ONLY','authorization_contexts_PASS':2,'cases':cases,
        'device_commands':0,'APP_MAIN_claim_sessions':0,'mock_references_removed':True,'contract_sha256':sha256(folder/'EXECUTION_CONTRACT.json')})
    inspect(job)


def inspect(job):
    rows=validate_plan(load_json(Path(job['plan'])));contract=load_json(Path(job['revision_contract_file']))
    require(contract['runner_sha256']==sha256(Path(__file__)),'runner changed')
    pc=load_json(Path(job['tracepair_PC_verification']))
    require(pc['status']=='PASS_PC_ONLY' and pc['authorization_contexts_PASS']==2
        and pc['contract_sha256']==sha256(Path(job['revision_contract_file'])),'exact PC proof absent')
    lifecycle_identity();control.verify_source_entries(load_json(Path(job['source_manifest'])),ROOT,controller_file=control.CONTROLLER_SOURCE_FILE)
    require(not Path(job['run_root']).exists() and not Path(job['tracepair_global_root']).exists(),'already attempted; never replay')
    return rows


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);subs=p.add_subparsers(dest='action',required=True)
    a=subs.add_parser('prepare');a.add_argument('template',type=Path);a.add_argument('folder',type=Path)
    a.add_argument('--device-stop',required=True);a.add_argument('--work-stop',required=True)
    for name in ['inspect','execute']:
        a=subs.add_parser(name);a.add_argument('job',type=Path)
        if name=='execute':a.add_argument('--execute-authorized',action='store_true')
    a=p.parse_args()
    if a.action=='prepare':prepare(a.template,a.folder.resolve(),a.device_stop,a.work_stop);print(json.dumps({'status':'TRACEPAIR2_PC_READY','device_commands':0}))
    elif a.action=='inspect':inspect(load_json(a.job));print(json.dumps({'status':'TRACEPAIR2_PC_READY','device_commands':0}))
    else:require(a.execute_authorized,'explicit execution flag absent');execute(load_json(a.job))
