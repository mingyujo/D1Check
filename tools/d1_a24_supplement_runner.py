"""Finite, prospective failed-case replications with the preserved APK.

No changes to an executing controller, old registry, original source or raw data.
The default commands prepare/inspect on PC. Execution is one-shot, after every
previous owner has closed; failures stop this batch rather than retrying it.
"""
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

import d1_a24_supplement_control as control
from d1_a24_supplement_contract import CASES, PLAN_ID, ROLE, validate_plan
from d1_a24_laptop_plan import encode, identity
from d1_a24_laptop_validator import ARMS, NS, PROTOCOL, load_json, manifest_requests, sha256
from d1_a24_revision02_suite import RULES, gate_for_registered_row, require
from d1_a24_confirm_after_diagnostic import FollowupClient
from d1_a24_measurement_batch import TARGET_KEYS, finish_only_closed_owned_process
from d1_a24_suite_dev_continue import cold_enough_to_prepare
from d1_a24_revision02_window import check_deadline

ROOT = Path(__file__).resolve().parents[1]
DOCS = [('window_file','window_sha256'),('revision_contract_file','revision_contract_sha256'),
        ('budget_file','budget_sha256'),('analysis_contract','analysis_contract_sha256')]


def passive_before_APP(client, gate, evidence):
    """Preparation only; the original post-warmup MAIN gate is still required."""
    require(not evidence.exists(),'write-once passive evidence')
    evidence.parent.mkdir(exist_ok=True);samples=[]
    while True:
        client.check_window('NEW_SESSION')
        require(sha256(Path(gate['block_reference_path']))==gate['block_reference_sha256'],'reference changed')
        x=control.read_hal(client)
        with evidence.open('a',encoding='utf-8') as f:f.write(json.dumps(x)+'\n')
        ap=[s['value_c'] for s in x['sensors'] if s['sensor_name']=='AP' and s['sensor_type']==0]
        samples.append({'before_ns':x['device_elapsed_before_ns'],'after_ns':x['device_elapsed_after_ns'],
                        'AP_c':ap[0] if len(ap)==1 else None})
        if cold_enough_to_prepare(samples,gate['Tref_c']+gate['tref_tolerance_c']):
            control.atomic_json(evidence.with_suffix('.ready.json'),{'status':'PREPARATION_ONLY_STABLE',
                'MAIN_admitted':False,'post_warmup_MAIN_rules_unchanged':True,'reference_sha256':gate['block_reference_sha256']})
            return
        require(samples[-1]['after_ns']-samples[0]['before_ns']<=600*NS,'PRE_APP_TIMEOUT_APP0')
        client.sleep_ns(5*NS)


def lifecycle_identity():
    old = (ROOT/'tools/d1_a24_revision02_suite_control.py').read_text(encoding='utf-8')
    expected = old.replace('from d1_a24_revision02_suite import validate_suite_registration',
        'from d1_a24_supplement_contract import validate_registration as validate_suite_registration').replace(
        'tools/d1_a24_revision02_suite_control.py', 'tools/d1_a24_supplement_control.py').replace(
        'REV02 eight-arm suite controller; preserved pilot lifecycle with separate guards.',
        'User-authorized failed-case supplement; preserved original suite lifecycle.')
    actual = control.CONTROLLER_SOURCE_FILE.read_text(encoding='utf-8')
    require(actual == expected, 'supplement must preserve original control lifecycle')
    a = {x.name:ast.dump(x,include_attributes=False) for x in ast.parse(old).body if isinstance(x,(ast.FunctionDef,ast.ClassDef))}
    b = {x.name:ast.dump(x,include_attributes=False) for x in ast.parse(actual).body if isinstance(x,(ast.FunctionDef,ast.ClassDef))}
    require(all(a[k] == b[k] for k in a if k != 'verify_source_entries'), 'runtime/admission boundaries changed')
    return {'status':'PASS_EXACT_COMMON_LIFECYCLE','same_functions_and_classes':sorted(k for k in a if k != 'verify_source_entries')}


def assemble(job, row, root):
    m = load_json(Path(job['prepared_manifests'])/(row['session_id']+'.json'))
    directory = root/'bindings'/row['session_id'];directory.mkdir(parents=True,exist_ok=False)
    for name in job['input_filenames']:os.link(Path(job['input_root'])/name,directory/name)
    control.atomic_json(directory/'session_manifest.json',m)
    g = gate_for_registered_row(row,load_json(Path(job['gate'])),root)
    control.atomic_json(directory/'gate.json',g)
    ident = load_json(Path(job['apk_identity']));target = load_json(Path(job['device_registration']))
    c = {'manifest_bytes':(directory/'session_manifest.json').read_bytes(),'manifest_sha256':sha256(directory/'session_manifest.json'),
        'gate_bytes':(directory/'gate.json').read_bytes(),'gate_sha256':sha256(directory/'gate.json'),
        'apk':{'path':job['apk'],'sha256':ident['apk_sha256']},'adb':{'path':job['adb'],'sha256':sha256(Path(job['adb']))},
        'apk_identity':ident,'bundle_root':str(directory),'files':[{'path':p.name,'bytes':p.stat().st_size,'sha256':sha256(p)}
            for p in sorted(directory.iterdir()) if p.is_file() and p.name != 'gate.json'],
        'source_root':str(ROOT),'source_code_manifest':job['source_manifest'],'source_code_sha256':sha256(Path(job['source_manifest'])),
        'host_dependency_lock':job['host_dependency_lock'],'host_dependency_lock_sha256':sha256(Path(job['host_dependency_lock'])),
        'registry_root':str(root/'registry'/PROTOCOL/PLAN_ID),'output_root':str(root/'raw'),
        'reuse_verified_installed_APK':True,'package_name':ident['package'],'require_journal_closed_before_recovery':True,
        'suite_plan_file':job['plan'],'suite_plan_sha256':sha256(Path(job['plan'])),'perfetto':job['perfetto']}
    for key,digest in DOCS:c[key]=job[key];c[digest]=sha256(Path(job[key]))
    a = {'schema':'a24-laptop-control-authorization-v1','authorization':'USER_EXPLICIT_FUTURE_A24_MEASUREMENT',
        'scope':'one_new_session','session_id':m['session_id'],'plan_sha256':m['plan_sha256'],
        'serial':target['adb_serial'],'fingerprint':target['build_fingerprint'],'expected_model':'SM-A245N',
        'api_level':target['api_level'],'ram_bytes':target['ram_bytes'],'package_name':ident['package'],
        'apk_sha256':ident['apk_sha256'],'control_source_sha256':sha256(control.CONTROLLER_SOURCE_FILE)}
    for k in ['manifest_sha256','gate_sha256','source_code_sha256','host_dependency_lock_sha256','suite_plan_sha256']+[s for _,s in DOCS]:a[k]=c[k]
    if m['perfetto']=='ON':a.update(perfetto_profile_sha256=c['perfetto']['profile_sha256'],perfetto_device_version=c['perfetto']['device_version'])
    control.atomic_json(directory/'authorization.json',a)
    control.atomic_json(directory/'config.json',{k:v for k,v in c.items() if not isinstance(v,bytes)})
    control.check_authorization(m,c,a,g,execute_authorized=True)
    return m,c,a,g


def original_template(name, sid):
    docs=Path.home()/'Documents'
    root=docs/('A24R02W1' if name=='W1_CPU' else 'A24R02W3' if name=='W3_GPU'
               else 'A24R02C9' if name=='C9_ORDER' else 'A24R02R2' if name=='R2_PAIR' else 'A24M15')
    choices=[root/'raw'/sid/'session_manifest.json',root/'bindings'/sid/'session_manifest.json',
             ROOT/'output/a24_readiness_only_20261015/PC_ONLY_BOUND_MANIFESTS'/(sid+'.json')]
    path=next((p for p in choices if p.is_file()),None)
    require(path is not None,'exact failed-case manifest unavailable: '+name)
    outcome=root/(sid+'.outcome.json')
    if outcome.exists():
        status=load_json(outcome)['status'];require(status!='COMPLETE_TRACE_RECOVERED','successful original must not be repeated')
        proof={'outcome_sha256':sha256(outcome),'original_status':status}
    else:
        require(name=='I_UNRESIDENT','only forensic first failure may lack an outcome')
        proof={'prior_stage_ledger_sha256':sha256(ROOT/'output/a24_confirmation40_frozen_window01_20261015/PRIOR_STAGE_LEDGER.json'),
               'original_status':'PRESERVED_INITIAL_INSTALL_FAILURE'}
    return load_json(path), {'case_name':name,'original_failed_session_id':sid,
        'template_sha256':sha256(path),'template_is_actual_raw':path.parent.name==sid and path.parent.parent.name=='raw',**proof}


def prepare(template, folder, device_stop, work_stop):
    require(not folder.exists(),'write-once supplemental metadata required')
    folder.mkdir(parents=True);(folder/'banks').mkdir();(folder/'prepared_manifests').mkdir()
    job=load_json(template);target=load_json(Path(job['device_registration']));ident=load_json(Path(job['apk_identity']))
    source=load_json(Path(job['source_manifest']));core_sha=sha256(Path(job['source_manifest']))
    require(len(source['files'])==179,'must retain original179 exact source manifest')
    for item in source['files']:
        p=ROOT/item['path'];require(sha256(p)==item['sha256'] and p.stat().st_size==item['bytes'],'original source changed')
    for name in ['tools/d1_a24_supplement_contract.py','tools/d1_a24_supplement_control.py',
                 'tools/d1_a24_supplement_runner.py','tools/test_d1_a24_supplement.py']:
        p=ROOT/name;source['files'].append({'path':name,'bytes':p.stat().st_size,'sha256':sha256(p)})
    control.atomic_json(folder/'SOURCE_SHA256.json',source)
    rows=[];bodies=[];proofs=[];banks={}
    for i,(name,old,key) in enumerate(CASES):
        m,proof=original_template(name,old);proofs.append(proof)
        require(tuple(m[k] for k in ['recipe','order','route','concurrency','wait_ms'])==ARMS[key], 'source failed prescription differs')
        bankkey='TRACE' if i in {2,3} else name
        requests=copy.deepcopy(m['requests'])
        for q in requests:q['request_id']=identity(PLAN_ID,bankkey+':REQUEST:'+str(q['ordinal']))
        b={'schema':'a24-supplement-exact-semantic-request-bank-v1','requests':requests,'request_count':len(requests)}
        if bankkey not in banks:control.atomic_json(folder/'banks'/(bankkey+'.json'),b);banks[bankkey]=b
        else:require(banks[bankkey]==b,'same trace off/on input required')
        sid=identity(PLAN_ID,old)
        row={k:m[k] for k in ['recipe','arm','order','route','concurrency','wait_ms','resident_mode','perfetto','input_seed','service_cutoff_ns','sensor_end_ns']}
        row.update(protocol=PROTOCOL,session_id=sid,plan_id=PLAN_ID,stage='DEV',block=bankkey,case_name=name,
            original_failed_session_id=old,prescription_id=key,policy_id='SUPPLEMENT_'+name,plan_ordinal=i,
            bank_file='banks/'+bankkey+'.json',bank_sha256=sha256(folder/'banks'/(bankkey+'.json')),request_count=len(requests),
            gate_block_id=PLAN_ID+'-'+bankkey,reference_role='MATCH_FIXED' if i==3 else 'SELECT_FIRST',
            reference_owner_session_id=identity(PLAN_ID,CASES[2][1]) if i==3 else sid)
        m.update(row);m['requests']=requests
        m.update(execution_authorized=True,mock=False,device_status='DEVICE_APPROVED_FOR_NEW_CONTRACT',
            authorization='USER_FAILED_CASES_NEW_IDS_20261016',device_fingerprint=target['build_fingerprint'],target_model=target['model'],
            apk_sha256=ident['apk_sha256'],minimum_battery_percent=10,soc_contract='USER_SOC_GE10_20261015',
            experiment_ready=False,source_manifest_sha256=sha256(folder/'SOURCE_SHA256.json'),
            source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip(),
            evidence_level='AUTHORIZED_NEW_DEVICE_ATTEMPT_PENDING_VALIDATION')
        for spec in m['models'].values():
            spec['identity']['session_id']=sid
            spec['target']={k:copy.deepcopy(target[k]) for k in TARGET_KEYS}
            spec['target'].update(apk_sha256=ident['apk_sha256'],package_name=ident['package'])
        rows.append(row);bodies.append(m)
    plan={'schema':'a24-failed-supplement-v1','plan_id':PLAN_ID,'analysis_role':ROLE,'session_count':12,'sessions':rows,
          'status':'FROZEN_EXECUTION_PLAN','execution_authorized':True,'reference_rules':RULES,'pooled_with_original_confirm':False,
          'historical_failures_preserved':True,'maximum_new_attempts_per_failed_ID':1,
          'reference_scope':'TRACE off/on share; other diagnostic replications select own first stable post-preparation window',
          'original40_success_counts_replaced':False,'J_validation_claim':False}
    validate_plan(plan);control.atomic_json(folder/'plan.json',plan);control.atomic_json(folder/'ORIGINAL_FAILURES.json',proofs)
    for m in bodies:
        m['plan_sha256']=sha256(folder/'plan.json');manifest_requests(m,require_materials=True)
        control.atomic_json(folder/'prepared_manifests'/(m['session_id']+'.json'),m)
    device=dt.datetime.fromisoformat(device_stop);work=dt.datetime.fromisoformat(work_stop)
    require((work-device).total_seconds()>=300,'reserve final5min')
    window={'execution_authorized':True,'hard_stop_UTC':device.isoformat(),'work_stop_UTC':work.isoformat(),
            'registered_session_ids':[r['session_id'] for r in rows],'plan_sha256':sha256(folder/'plan.json'),
            'reserved_final_minutes':5,'maximum_attempts_this_window':12,'scope':ROLE}
    check_deadline(window,'NEW_SESSION');control.atomic_json(folder/'USER_WINDOW.json',window)
    budget={'authorized':True,'original_reserved_cap':85,'supplement_cap':12,'reserved_for_plan':12,
            'combined_accounting_ceiling':97,'plan_sha256':sha256(folder/'plan.json'),
            'authority':'Latest user instruction to rerun failed cases; concretized as one new attempt for each of12 recorded failures/incompletions, not unlimited retry.',
            'old85_plan_files_and_consumption_unchanged':True,'old_failed_attempts_refunded':False}
    control.atomic_json(folder/'BUDGET.json',budget)
    analysis={'frozen':True,'analysis_role':ROLE,'pooled_with_original_confirm':False,'energy_J':None,
        'AP_window_seconds':[35,180],'maximum_AP_gap_seconds':10,'service_window_seconds':[0,120],
        'all_planned_and_failed_requests_preserved':True,'surface_temperature_verified':False,
        'idle_own_start_states':'Diagnostic only; unresident/resident start states differ; no causal energy/surface claim',
        'trace_on_off':'Same32 input and shared first OFF reference; actual Perfetto acquisition must be independently checked',
        'other_replications':'New post-observation starts; do not pool with old independent validation or report historical failure as success'}
    control.atomic_json(folder/'ANALYSIS_CONTRACT.json',analysis)
    life=lifecycle_identity();control.atomic_json(folder/'LIFECYCLE_IDENTITY.json',life)
    contract={'status':'FROZEN_EXECUTION_CONTRACT','plan_sha256':sha256(folder/'plan.json'),'reference_rules':RULES,
        'energy_J':None,'surface_temperature_verified':False,'original_core179_unchanged':True,
        'original_core179_sha256':core_sha,'controller_lifecycle_AST_identical':True,
        'controller_sha256':sha256(control.CONTROLLER_SOURCE_FILE),'source_sha256':sha256(folder/'SOURCE_SHA256.json'),
        'runner_sha256':sha256(Path(__file__)),'budget_sha256':sha256(folder/'BUDGET.json'),
        'window_sha256':sha256(folder/'USER_WINDOW.json'),'analysis_sha256':sha256(folder/'ANALYSIS_CONTRACT.json')}
    control.atomic_json(folder/'EXECUTION_CONTRACT.json',contract)
    job.update(plan=str(folder/'plan.json'),plan_sha256=sha256(folder/'plan.json'),source_manifest=str(folder/'SOURCE_SHA256.json'),
        prepared_manifests=str(folder/'prepared_manifests'),window_file=str(folder/'USER_WINDOW.json'),budget_file=str(folder/'BUDGET.json'),
        analysis_contract=str(folder/'ANALYSIS_CONTRACT.json'),revision_contract_file=str(folder/'EXECUTION_CONTRACT.json'),
        run_root=str(Path(job['run_root']).parent/'A24SUP12'),supplement_global_root=str(Path(job['run_root']).parent/'A24SUP12_GLOBAL'),
        supplement_PC_verification=str(folder/'PC_VERIFICATION.json'))
    control.atomic_json(folder/'job.json',job)
    with tempfile.TemporaryDirectory(prefix='PC_ONLY_',dir=folder) as tmp:
        scratch=Path(tmp);cases=[]
        for row in rows:
            m,c,a,g=assemble(job,row,scratch);cases.append({'session_id':row['session_id'],'manifest_sha256':c['manifest_sha256'],'status':'PASS_PC_ONLY'})
            if row['reference_role']=='SELECT_FIRST':
                p=scratch/'references'/(row['gate_block_id']+'.json');p.parent.mkdir(exist_ok=True)
                control.atomic_json(p,{'block_id':row['gate_block_id'],'reference_session_id':row['session_id'],
                    'Tref_c':27.6,'frozen_before_any_main_request':True,'PC_MOCK_ONLY':True})
    proof={'status':'PASS_PC_ONLY','authorization_contexts_PASS':12,'cases':cases,'device_commands':0,
           'APP_MAIN_claim_sessions':0,'mock_references_removed':True,'contract_sha256':sha256(folder/'EXECUTION_CONTRACT.json')}
    control.atomic_json(folder/'PC_VERIFICATION.json',proof);inspect(job)
    return job


def inspect(job):
    rows=validate_plan(load_json(Path(job['plan'])));contract=load_json(Path(job['revision_contract_file']))
    require(contract['runner_sha256']==sha256(Path(__file__)),'supplement runner changed')
    pc=load_json(Path(job['supplement_PC_verification']))
    require(pc['status']=='PASS_PC_ONLY' and pc['authorization_contexts_PASS']==12
            and pc['contract_sha256']==sha256(Path(job['revision_contract_file'])),'exact PC proof missing')
    lifecycle_identity();control.verify_source_entries(load_json(Path(job['source_manifest'])),ROOT,controller_file=control.CONTROLLER_SOURCE_FILE)
    require(not Path(job['run_root']).exists() and not Path(job['supplement_global_root']).exists(),'supplement already attempted; no replay')
    return rows


def require_no_prior_owners(parent):
    owners=[]
    for root in parent.glob('A24*'):
        if root.is_dir():
            for name in ['ACTIVE_OWNER.json','OWNER_WINDOW.json','OWNER_CONTINUATION_V2.json']:
                p=root/name
                if not p.exists():continue
                if name!='ACTIVE_OWNER.json' and any((root/n).exists() for n in ['WINDOW_STOPPED.json','WINDOW_CONTINUATION_V2_STOPPED.json']):continue
                # Old OWNER_WINDOW markers can survive renamed/legacy stop
                # formats. Only an ACTIVE_OWNER is authoritative across roots;
                # app process absence is independently checked by run_one.
                if name=='ACTIVE_OWNER.json':owners.append(str(p))
    require(not owners,'previous measurement worker active')


def execute(job):
    rows=inspect(job);window=load_json(Path(job['window_file']));check_deadline(window,'NEW_SESSION')
    root=Path(job['run_root']);globalroot=Path(job['supplement_global_root'])
    require_no_prior_owners(root.parent)
    # The original85 remains reserved even if not all its attempts occurred.
    globalroot.mkdir();control.atomic_json(globalroot/'ACTIVE_OWNER.json',{'pid':os.getpid(),'supplement_only':True})
    root.mkdir();control.atomic_json(root/'OWNER_WINDOW.json',{'pid':os.getpid(),'window':window,'runner_sha256':sha256(Path(__file__))})
    client=None;outcomes=[];reason='SUPPLEMENT12_FINISHED'
    try:
        target=load_json(Path(job['device_registration']))
        client=FollowupClient(job,target,window,globalroot,{'total_consumed':85,'cap':97});client.job_run_root=str(root);client.reconnect()
        require(client.command('shell','settings','get','system','screen_brightness').decode().strip()=='81','brightness differs')
        require(client.command('shell','settings','get','system','screen_brightness_mode').decode().strip()=='0','screen mode differs')
        require('mWakefulness=Awake' in client.command('shell','dumpsys','power').decode(),'screen asleep')
        for row in rows:
            sid=row['session_id'];client.check_window('NEW_SESSION')
            require(not (globalroot/'reservations'/sid).exists(),'supplement ID already used')
            m,c,a,g=assemble(job,row,root)
            print(json.dumps({'status':'PREPARING_NEW_FAILED_CASE_REPLICATION','case':row['case_name'],'session_id':sid}),flush=True)
            if g['reference_role']=='MATCH_FIXED':
                try:passive_before_APP(client,g,root/'pre_app_cooldown_v2'/(sid+'.jsonl'))
                except Exception as error:
                    control.atomic_json(root/(sid+'.preapp_stop.json'),{'APP':0,'reason':str(error),'binding_created':True})
                    reason='PRE_APP_STOP_PRESERVED';break
            reservation=globalroot/'reservations'/sid;reservation.mkdir(parents=True,exist_ok=False)
            control.atomic_json(reservation/'RESERVED.json',{'session_id':sid,'original_failed_id':row['original_failed_session_id']});client.active_sid=sid
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
            if outcome['status']!='COMPLETE_TRACE_RECOVERED':reason='FAILED_SUPPLEMENT_PRESERVED_NO_AUTO_RETRY';break
    except Exception as error:reason='SUPPLEMENT_STOP_PRESERVED: '+str(error)
    finally:
        control.atomic_json(root/'WINDOW_STOPPED.json',{'outcomes':outcomes,'reason':reason,'actual_stop_UTC':dt.datetime.now(dt.timezone.utc).isoformat(),
            'new_APP_intents':len(list((globalroot/'reservations').glob('*/APP_LAUNCH_INTENT.json'))),
            'actual_ADB_calls':client.actual_calls if client else 0,'supplement_cap':12,'old_failed_results_replaced':False})
        require(load_json(globalroot/'ACTIVE_OWNER.json')['pid']==os.getpid(),'foreign supplement owner');(globalroot/'ACTIVE_OWNER.json').unlink()


def main():
    p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='action',required=True)
    a=s.add_parser('prepare');a.add_argument('template',type=Path);a.add_argument('folder',type=Path)
    a.add_argument('--device-stop',required=True);a.add_argument('--work-stop',required=True)
    for name in ['inspect','execute']:
        a=s.add_parser(name);a.add_argument('job',type=Path)
        if name=='execute':a.add_argument('--execute-authorized',action='store_true')
    args=p.parse_args()
    if args.action=='prepare':prepare(args.template,args.folder.resolve(),args.device_stop,args.work_stop);print(json.dumps({'status':'SUPPLEMENT12_PC_READY','APP':0}))
    elif args.action=='inspect':inspect(load_json(args.job));print(json.dumps({'status':'SUPPLEMENT12_PC_READY','device_commands':0}))
    else:require(args.execute_authorized,'explicit execution flag absent');execute(load_json(args.job))


if __name__=='__main__':main()
