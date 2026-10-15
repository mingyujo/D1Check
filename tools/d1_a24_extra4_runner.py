"""Prepare or execute only the explicitly approved extra4 stable-reference block."""
import argparse
import ast
import copy
import datetime as dt
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

import d1_a24_extra4_control as control
from d1_a24_extra4_contract import PLAN_ID, ROLE, SCHEMA, ORDER, validate_extra4_plan
from d1_a24_laptop_plan import encode, identity
from d1_a24_laptop_validator import load_json, sha256, PROTOCOL, manifest_requests
from d1_a24_revision02_suite import RULES, require, gate_for_registered_row
from d1_a24_confirm_after_diagnostic import FollowupClient
from d1_a24_measurement_batch import finish_only_closed_owned_process
from d1_a24_revision02_window import check_deadline
from d1_a24_suite_dev_continue import passive_v2

ROOT=Path(__file__).resolve().parents[1]
DOCS=[('window_file','window_sha256'),('revision_contract_file','revision_contract_sha256'),
      ('budget_file','budget_sha256'),('analysis_contract','analysis_contract_sha256'),
      ('new_protocol_functional_evidence','new_protocol_functional_evidence_sha256')]


def lifecycle_identity():
    """Only registration import, filename binding and docstring may differ."""
    old=(ROOT/'tools/d1_a24_revision02_suite_control.py').read_text(encoding='utf-8')
    new=(ROOT/'tools/d1_a24_extra4_control.py').read_text(encoding='utf-8')
    expected=old.replace('from d1_a24_revision02_suite import validate_suite_registration',
        'from d1_a24_extra4_contract import validate_extra4_registration as validate_suite_registration').replace(
        'controller_relative == "tools/d1_a24_revision02_suite_control.py"',
        'controller_relative == "tools/d1_a24_extra4_control.py"').replace(
        'REV02 eight-arm suite controller; preserved pilot lifecycle with separate guards.',
        'User-approved extra4 registration; lifecycle identical to preserved suite core.')
    require(new==expected,'extra4 changed more than registration import/path/docstring')
    a={x.name:ast.dump(x,include_attributes=False) for x in ast.parse(old).body if isinstance(x,(ast.FunctionDef,ast.ClassDef))}
    b={x.name:ast.dump(x,include_attributes=False) for x in ast.parse(new).body if isinstance(x,(ast.FunctionDef,ast.ClassDef))}
    require(all(a[k]==b[k] for k in a if k!='verify_source_entries'),'common control lifecycle changed')
    return {'status':'PASS_EXACT_COMMON_LIFECYCLE','same_functions_and_classes':sorted(k for k in a if k!='verify_source_entries'),
            'allowed_changes':['registration import','exact controller path','module docstring']}


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
       'registry_root':str(root/'registry'/PROTOCOL/m['plan_id']),'output_root':str(root/'raw'),
       'reuse_verified_installed_APK':True,'package_name':ident['package'],'require_journal_closed_before_recovery':True,
       'suite_plan_file':job['plan'],'suite_plan_sha256':sha256(Path(job['plan']))}
    for key,shakey in DOCS:c[key]=job[key];c[shakey]=sha256(Path(job[key]))
    a={'schema':'a24-laptop-control-authorization-v1','authorization':'USER_EXPLICIT_FUTURE_A24_MEASUREMENT',
       'scope':'one_new_session','session_id':m['session_id'],'plan_sha256':m['plan_sha256'],
       'serial':target['adb_serial'],'fingerprint':target['build_fingerprint'],'expected_model':'SM-A245N',
       'api_level':target['api_level'],'ram_bytes':target['ram_bytes'],'package_name':ident['package'],
       'apk_sha256':ident['apk_sha256'],'control_source_sha256':sha256(control.CONTROLLER_SOURCE_FILE)}
    for k in ['manifest_sha256','gate_sha256','source_code_sha256','host_dependency_lock_sha256','suite_plan_sha256']+[s for _,s in DOCS]:a[k]=c[k]
    control.atomic_json(directory/'authorization.json',a)
    control.atomic_json(directory/'config.json',{k:v for k,v in c.items() if not isinstance(v,bytes)})
    control.check_authorization(m,c,a,g,execute_authorized=True)
    return m,c,a,g


def prepare(template,folder,device_stop,work_stop):
    require(not folder.exists(),'new extra4 metadata folder required')
    job=load_json(template);oldplan=load_json(Path(job['plan']));oldrows=[r for r in oldplan['sessions'] if r['block']=='R02CONFIRM03' and r['recipe']=='M128']
    previous_stop=load_json(Path(job['run_root'])/'WINDOW_STOPPED.json')
    previous_binding=load_json(Path(job['global_binding']))
    require(not (Path(previous_binding['global_reservation_root'])/'ACTIVE_OWNER.json').exists(),'previous worker active')
    prior_consumed=load_json(Path(previous_binding['ledger_path']))['total_consumed']+previous_stop['new_APP_intents']
    require(prior_consumed==62 and previous_stop['new_APP_intents']==1,'budget snapshot differs; rebind explicitly')
    require(len(oldrows)==4 and {r['arm'] for r in oldrows}==set(ORDER),'original M128 group differs')
    bank=Path(job['plan']).parent/oldrows[0]['bank_file'];oldbank=load_json(bank)
    require(sha256(bank)==oldrows[0]['bank_sha256'],'original bank changed')
    life=lifecycle_identity();folder.mkdir(parents=True);(folder/'banks').mkdir();(folder/'prepared_manifests').mkdir()
    shutil.copyfile(bank,folder/'banks/M128_same_input.json')
    rows=[]
    for i,arm in enumerate(ORDER):
        row=copy.deepcopy(next(r for r in oldrows if r['arm']==arm))
        row.update(session_id=identity(PLAN_ID,'EXTRA4:'+arm),plan_id=PLAN_ID,stage='DEV',block='REBASE_M128_01',plan_ordinal=i,
            policy_id='R02_REBASE_M128_'+arm,bank_file='banks/M128_same_input.json',gate_block_id=PLAN_ID+'-REBASE_M128_01',
            reference_owner_session_id=identity(PLAN_ID,'EXTRA4:'+ORDER[0]),reference_role='SELECT_FIRST' if i==0 else 'MATCH_FIXED')
        rows.append(row)
    plan={'schema':SCHEMA,'plan_id':PLAN_ID,'analysis_role':ROLE,'stage':'DEV','session_count':4,'sessions':rows,
          'status':'FROZEN_EXECUTION_PLAN','execution_authorized':True,'reference_rules':RULES,'retry_or_replacement':0,
          'original_confirm40_preserved':True,'pooled_with_original_confirm':False,'original_M128_bank_sha256':sha256(bank),
          'original_plan_sha256':sha256(Path(job['plan'])),'original_input_seed':rows[0]['input_seed']}
    validate_extra4_plan(plan);control.atomic_json(folder/'plan.json',plan)
    source=load_json(Path(job['source_manifest']));original_sha=sha256(Path(job['source_manifest']))
    for name in ['tools/d1_a24_extra4_contract.py','tools/d1_a24_extra4_control.py','tools/d1_a24_extra4_runner.py','tools/test_d1_a24_extra4.py']:
        p=ROOT/name;source['files'].append({'path':name,'bytes':p.stat().st_size,'sha256':sha256(p)})
    source.update(measurement_revision='Approved extra4 registration only; original179 and runtime APK unchanged',
        original179_manifest_sha256=original_sha,UTC=dt.datetime.now(dt.timezone.utc).isoformat(),source_uncommitted=True)
    control.atomic_json(folder/'SOURCE_SHA256.json',source)
    for row in rows:
        oldrow=next(r for r in oldrows if r['arm']==row['arm'])
        m=load_json(Path(job['prepared_manifests'])/(oldrow['session_id']+'.json'))
        m.update(row);m.update(plan_sha256=sha256(folder/'plan.json'),requests=oldbank['requests'],
            source_manifest_sha256=sha256(folder/'SOURCE_SHA256.json'),source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip(),
            execution_authorized=True,mock=False,device_status='DEVICE_APPROVED_FOR_NEW_CONTRACT',experiment_ready=False)
        for spec in m['models'].values():spec['identity']['session_id']=row['session_id']
        manifest_requests(m,require_materials=True);control.atomic_json(folder/'prepared_manifests'/(row['session_id']+'.json'),m)
    device=dt.datetime.fromisoformat(device_stop);work=dt.datetime.fromisoformat(work_stop)
    require((work-device).total_seconds()>=300,'reserve final5min')
    window={'schema':'a24-user-execution-window-v1','execution_authorized':True,'hard_stop_UTC':device.isoformat(),
            'work_stop_UTC':work.isoformat(),'reserved_final_minutes':5,'registered_session_ids':[r['session_id'] for r in rows],
            'plan_sha256':sha256(folder/'plan.json'),'maximum_attempts_this_window':4,'scope':ROLE}
    check_deadline(window,'NEW_SESSION');control.atomic_json(folder/'USER_WINDOW.json',window)
    budget={'authorized':True,'project_cap':85,'original_plan_cap':81,'additional_cap':4,'spent_before_plan':62,
            'reserved_original_pending':19,'reserved_for_plan':4,'plan_sha256':sha256(folder/'plan.json'),
            'approval':'USER_EXPLICIT_85: original81 preserved + new stable-reference M1284; no same-ID replay'}
    control.atomic_json(folder/'BUDGET.json',budget)
    analysis={'frozen':True,'analysis_role':ROLE,'original_KPI_and_units_preserved':True,'pooled_with_original_confirm':False,
              'AP_window_seconds':[35,180],'maximum_AP_gap_seconds':10,'service_window_seconds':[0,120],
              'urgent_deadline_s':2.2,'normal_deadline_s':5,'energy_J':None,'surface_temperature_verified':False,
              'all_planned_requests_and_failures_reported':True,'new_posthoc_block_no_independent5block_CI':True}
    control.atomic_json(folder/'ANALYSIS_CONTRACT.json',analysis)
    contract={'status':'FROZEN_EXECUTION_CONTRACT','plan_sha256':sha256(folder/'plan.json'),'reference_rules':RULES,
              'energy_J':None,'surface_temperature_verified':False,'original_core179_unchanged':True,
              'original_core179_sha256':original_sha,'controller_lifecycle_AST_identical':True,
              'controller_sha256':sha256(control.CONTROLLER_SOURCE_FILE),'source_sha256':sha256(folder/'SOURCE_SHA256.json'),
              'runner_sha256':sha256(Path(__file__)),'contract_module_sha256':sha256(ROOT/'tools/d1_a24_extra4_contract.py'),
              'budget_sha256':sha256(folder/'BUDGET.json'),'window_sha256':sha256(folder/'USER_WINDOW.json'),
              'analysis_sha256':sha256(folder/'ANALYSIS_CONTRACT.json'),'original_samples_preserved':True}
    control.atomic_json(folder/'EXECUTION_CONTRACT.json',contract);control.atomic_json(folder/'LIFECYCLE_IDENTITY.json',life)
    job.update(plan=str(folder/'plan.json'),prepared_manifests=str(folder/'prepared_manifests'),source_manifest=str(folder/'SOURCE_SHA256.json'),
               window_file=str(folder/'USER_WINDOW.json'),budget_file=str(folder/'BUDGET.json'),analysis_contract=str(folder/'ANALYSIS_CONTRACT.json'),
               revision_contract_file=str(folder/'EXECUTION_CONTRACT.json'),run_root=str(Path(job['run_root']).parent/folder.name),
               extra4_global_root=str(Path(job['run_root']).parent/(folder.name+'_GLOBAL')),
               followup_PC_verification=str(folder/'PC_VERIFICATION.json'))
    control.atomic_json(folder/'job.json',job)
    with tempfile.TemporaryDirectory(prefix='pc_only_',dir=folder) as tmp:
        scratch=Path(tmp);(scratch/'references').mkdir();cases=[]
        for row in rows:
            m,c,a,g=assemble(job,row,scratch);cases.append({'session_id':row['session_id'],'manifest_sha256':c['manifest_sha256'],'PASS_PC_only':True})
            if row['reference_role']=='SELECT_FIRST':
                control.atomic_json(scratch/'references'/(row['gate_block_id']+'.json'),{'block_id':row['gate_block_id'],
                    'reference_session_id':row['session_id'],'Tref_c':26.2,'frozen_before_any_main_request':True,'PC_MOCK_ONLY':True})
    proof={'status':'PASS_PC_ONLY','authorization_contexts_PASS':4,'cases':cases,'device_commands':0,'APP_MAIN_claim_sessions':0,
           'mock_reference_removed':True,'contract_sha256':sha256(folder/'EXECUTION_CONTRACT.json'),'runner_sha256':sha256(Path(__file__))}
    control.atomic_json(folder/'PC_VERIFICATION.json',proof)
    return job


def inspect(job):
    rows=validate_extra4_plan(load_json(Path(job['plan'])));contract=load_json(Path(job['revision_contract_file']))
    require(contract['runner_sha256']==sha256(Path(__file__)) and contract['contract_module_sha256']==sha256(ROOT/'tools/d1_a24_extra4_contract.py'),'extra4 code changed')
    require(contract['controller_sha256']==sha256(control.CONTROLLER_SOURCE_FILE),'extra4 controller changed')
    pc=load_json(Path(job['followup_PC_verification']))
    require(pc['status']=='PASS_PC_ONLY' and pc['authorization_contexts_PASS']==4
            and pc['contract_sha256']==sha256(Path(job['revision_contract_file'])),'extra4 exact PC proof missing')
    lifecycle_identity();control.verify_source_entries(load_json(Path(job['source_manifest'])),ROOT,controller_file=control.CONTROLLER_SOURCE_FILE)
    window=load_json(Path(job['window_file']))
    require(window.get('execution_authorized') is True and window.get('PC_MOCK_ONLY') is not True
            and contract['window_sha256']==sha256(Path(job['window_file'])),'extra4 runtime time window differs')
    require(not Path(job['run_root']).exists() and not Path(job['extra4_global_root']).exists(),'extra4 already attempted; never replay')
    return rows


class ExtraClient(FollowupClient):
    def command(self,*args,**kwargs):
        if args[:3]==('shell','am','start'):
            require(len(list((self.global_root/'reservations').glob('*/APP_LAUNCH_INTENT.json')))<4,'additional4 cap reached')
        return super().command(*args,**kwargs)


def execute(job):
    rows=inspect(job);window=load_json(Path(job['window_file']));check_deadline(window,'NEW_SESSION')
    root=Path(job['run_root']);globalroot=Path(job['extra4_global_root'])
    require(not any((root.parent/('A24R02C'+str(i)+'_GLOBAL')/'ACTIVE_OWNER.json').exists() for i in range(1,11)), 'original confirmation worker active')
    root.mkdir();globalroot.mkdir();control.atomic_json(globalroot/'ACTIVE_OWNER.json',{'pid':os.getpid(),'extra4_only':True})
    control.atomic_json(root/'OWNER_WINDOW.json',{'pid':os.getpid(),'window':window,'runner_sha256':sha256(Path(__file__))})
    client=None;outcomes=[];reason='REGISTERED_EXTRA4_FINISHED'
    try:
        target=load_json(Path(job['device_registration']))
        client=ExtraClient(job,target,window,globalroot,{'total_consumed':62,'cap':85});client.job_run_root=str(root);client.reconnect()
        require(client.command('shell','settings','get','system','screen_brightness').decode().strip()=='81','brightness differs')
        require(client.command('shell','settings','get','system','screen_brightness_mode').decode().strip()=='0','screen mode differs')
        require('mWakefulness=Awake' in client.command('shell','dumpsys','power').decode(),'screen asleep')
        for row in rows:
            client.check_window('NEW_SESSION');sid=row['session_id']
            m,c,a,g=assemble(job,row,root);print(json.dumps({'status':'PREPARING_EXTRA4','arm':row['arm'],'session_id':sid}),flush=True)
            passive_v2(client,g,root/'pre_app_cooldown_v2'/(sid+'.jsonl'))
            reservation=globalroot/'reservations'/sid;reservation.mkdir(parents=True,exist_ok=False)
            control.atomic_json(reservation/'RESERVED.json',{'session_id':sid,'extra4_only':True});client.active_sid=sid
            logfile=root/'logcat'/(sid+'.txt');logfile.parent.mkdir(exist_ok=True)
            with logfile.open('xb') as stream:
                collector=subprocess.Popen(client.prefix+['logcat','-v','epoch','-T','1','tflite:V','D1A24PREP:V','*:S'],stdout=stream,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                try:
                    result=control.run_one(m,c,a,g,execute_authorized=True,client=client)
                    if result['status']=='COMPLETE_TRACE_RECOVERED':
                        require(finish_only_closed_owned_process(client,root/'raw'/sid,sid,package=c['package_name']),'closed process cleanup unproved')
                    outcome={**row,'status':result['status']}
                except Exception as error:outcome={**row,'status':'FAILED_PRESERVED','reason':str(error)}
                finally:collector.terminate();collector.wait(timeout=10)
            outcome['APP_launch_intent']=(reservation/'APP_LAUNCH_INTENT.json').exists()
            control.atomic_json(root/(sid+'.outcome.json'),outcome);control.atomic_json(reservation/'OUTCOME.json',outcome);outcomes.append(outcome)
            print(json.dumps(outcome),flush=True)
            if outcome['status']!='COMPLETE_TRACE_RECOVERED':reason='FAILED_EXTRA4_ATTEMPT_PRESERVED';break
    except Exception as error:reason='EXTRA4_STOP_PRESERVED: '+str(error)
    finally:
        control.atomic_json(root/'WINDOW_STOPPED.json',{'outcomes':outcomes,'reason':reason,'actual_stop_UTC':dt.datetime.now(dt.timezone.utc).isoformat(),
            'actual_ADB_calls':client.actual_calls if client else 0,'new_APP_intents':len(list((globalroot/'reservations').glob('*/APP_LAUNCH_INTENT.json'))),
            'additional_cap':4,'no_retry_or_replacement':True})
        require(load_json(globalroot/'ACTIVE_OWNER.json')['pid']==os.getpid(),'foreign extra4 owner');(globalroot/'ACTIVE_OWNER.json').unlink()


def main():
    parser=argparse.ArgumentParser(description=__doc__);subs=parser.add_subparsers(dest='action',required=True)
    p=subs.add_parser('prepare');p.add_argument('template',type=Path);p.add_argument('folder',type=Path);p.add_argument('--device-stop',required=True);p.add_argument('--work-stop',required=True)
    for name in ['inspect','execute']:
        p=subs.add_parser(name);p.add_argument('job',type=Path)
        if name=='execute':p.add_argument('--execute-authorized',action='store_true')
    args=parser.parse_args()
    if args.action=='prepare':
        job=prepare(args.template,args.folder.resolve(),args.device_stop,args.work_stop)
        inspect(job);print(json.dumps({'status':'EXTRA4_PC_READY','APP':0}))
    elif args.action=='inspect':inspect(load_json(args.job));print(json.dumps({'status':'EXTRA4_PC_READY','device_commands':0}))
    else:
        require(args.execute_authorized,'explicit execution flag absent');execute(load_json(args.job))


if __name__=='__main__':main()
