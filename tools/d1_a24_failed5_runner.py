"""Five finite diagnostic followons, using unchanged APK and original MAIN gate."""
import argparse,copy,datetime as dt,json,os,subprocess,tempfile
from pathlib import Path
import d1_a24_failed5_control as control
from d1_a24_failed5_contract import CASES,PLAN_ID,ROLE,validate_plan
from d1_a24_laptop_plan import identity
from d1_a24_laptop_validator import PROTOCOL,ARMS,load_json,manifest_requests,sha256
from d1_a24_revision02_suite import RULES,gate_for_registered_row,require
from d1_a24_revision02_window import check_deadline
from d1_a24_confirm_after_diagnostic import FollowupClient
from d1_a24_measurement_batch import finish_only_closed_owned_process
from d1_a24_supplement_runner import require_no_prior_owners

ROOT=Path(__file__).resolve().parents[1]
DOCS=[('window_file','window_sha256'),('revision_contract_file','revision_contract_sha256'),('budget_file','budget_sha256'),('analysis_contract','analysis_contract_sha256')]
SOURCE_FILES=['tools/d1_a24_failed5_contract.py','tools/d1_a24_failed5_control.py','tools/d1_a24_failed5_runner.py','tools/test_d1_a24_failed5.py','tools/d1_a24_supplement_runner.py','tools/d1_a24_no_main_failure.py']

def lifecycle_identity():
 old=(ROOT/'tools/d1_a24_revision02_suite_control.py').read_text(encoding='utf-8')
 expected=old.replace('from d1_a24_revision02_suite import validate_suite_registration','from d1_a24_failed5_contract import validate_registration as validate_suite_registration').replace('tools/d1_a24_revision02_suite_control.py','tools/d1_a24_failed5_control.py').replace('REV02 eight-arm suite controller; preserved pilot lifecycle with separate guards.','Five finite failed-case followons; original lifecycle and repaired trace config path.').replace('/data/local/tmp/a24-{session_id}-perfetto.pbtxt','/data/misc/perfetto-configs/a24-{session_id}-perfetto.pbtxt')
 require(control.CONTROLLER_SOURCE_FILE.read_text(encoding='utf-8')==expected,'original lifecycle changed')
 return {'status':'PASS_ORIGINAL_LIFECYCLE_WITH_DOCUMENTED_TRACE_PATH_FIX','MAIN_rules_unchanged':True}

def assemble(job,row,root):
 m=load_json(Path(job['prepared_manifests'])/(row['session_id']+'.json'))
 d=root/'bindings'/row['session_id'];d.mkdir(parents=True,exist_ok=False)
 for name in job['input_filenames']:os.link(Path(job['input_root'])/name,d/name)
 control.atomic_json(d/'session_manifest.json',m)
 g=gate_for_registered_row(row,load_json(Path(job['gate'])),root);control.atomic_json(d/'gate.json',g)
 ident=load_json(Path(job['apk_identity']));target=load_json(Path(job['device_registration']))
 c={'manifest_bytes':(d/'session_manifest.json').read_bytes(),'manifest_sha256':sha256(d/'session_manifest.json'),'gate_bytes':(d/'gate.json').read_bytes(),'gate_sha256':sha256(d/'gate.json'),
  'apk':{'path':job['apk'],'sha256':ident['apk_sha256']},'adb':{'path':job['adb'],'sha256':sha256(Path(job['adb']))},'apk_identity':ident,'bundle_root':str(d),
  'files':[{'path':p.name,'bytes':p.stat().st_size,'sha256':sha256(p)} for p in sorted(d.iterdir()) if p.is_file() and p.name!='gate.json'],
  'source_root':str(ROOT),'source_code_manifest':job['source_manifest'],'source_code_sha256':sha256(Path(job['source_manifest'])),
  'host_dependency_lock':job['host_dependency_lock'],'host_dependency_lock_sha256':sha256(Path(job['host_dependency_lock'])),
  'registry_root':str(root/'registry'/PROTOCOL/PLAN_ID),'output_root':str(root/'raw'),'reuse_verified_installed_APK':True,
  'package_name':ident['package'],'require_journal_closed_before_recovery':True,'suite_plan_file':job['plan'],'suite_plan_sha256':sha256(Path(job['plan'])),'perfetto':job['perfetto']}
 for key,digest in DOCS:c[key]=job[key];c[digest]=sha256(Path(job[key]))
 a={'schema':'a24-laptop-control-authorization-v1','authorization':'USER_EXPLICIT_FUTURE_A24_MEASUREMENT','scope':'one_new_session',
  'session_id':m['session_id'],'plan_sha256':m['plan_sha256'],'serial':target['adb_serial'],'fingerprint':target['build_fingerprint'],
  'expected_model':'SM-A245N','api_level':target['api_level'],'ram_bytes':target['ram_bytes'],'package_name':ident['package'],
  'apk_sha256':ident['apk_sha256'],'control_source_sha256':sha256(control.CONTROLLER_SOURCE_FILE)}
 for k in ['manifest_sha256','gate_sha256','source_code_sha256','host_dependency_lock_sha256','suite_plan_sha256']+[v for _,v in DOCS]:a[k]=c[k]
 if m['perfetto']=='ON':a.update(perfetto_profile_sha256=c['perfetto']['profile_sha256'],perfetto_device_version=c['perfetto']['device_version'])
 control.atomic_json(d/'authorization.json',a);control.atomic_json(d/'config.json',{k:v for k,v in c.items() if not isinstance(v,bytes)})
 control.check_authorization(m,c,a,g,execute_authorized=True)
 return m,c,a,g

def original_template(name,sid,key,rootname):
 root=Path.home()/'Documents'/rootname;p=root/(sid+'.outcome.json')
 require(p.is_file(),'original outcome missing');x=load_json(p)
 require(x['status'] in {'PRESTART_REJECT','FAILED_PRESERVED'} and x.get('APP_launch_intent') is True,'not a consumed failed original')
 choices=[root/'raw'/sid/'session_manifest.json',root/'bindings'/sid/'session_manifest.json']
 path=next((p for p in choices if p.is_file()),None);require(path is not None,'exact original manifest missing')
 m=load_json(path)
 require(tuple(m[k] for k in ['recipe','order','route','concurrency','wait_ms'])==ARMS[key],'source prescription differs')
 return m,{'original_failed_session_id':sid,'case_name':name,'outcome_sha256':sha256(p),'original_status':x['status'],'template_sha256':sha256(path)}

def prepare(template,folder,device_stop,work_stop):
 require(not folder.exists(),'fresh write-once metadata required');job=load_json(template)
 core=ROOT/'output/a24_suite_dev_window01_continuation_20261015/SOURCE_SHA256.json';source=load_json(core)
 require(len(source['files'])==179,'original179 missing')
 for x in source['files']:
  p=ROOT/x['path'];require(p.stat().st_size==x['bytes'] and sha256(p)==x['sha256'],'original source changed')
 for name in SOURCE_FILES:
  p=ROOT/name;require(name not in {x['path'] for x in source['files']},'duplicate source');source['files'].append({'path':name,'bytes':p.stat().st_size,'sha256':sha256(p)})
 folder.mkdir(parents=True);(folder/'banks').mkdir();(folder/'prepared_manifests').mkdir()
 control.atomic_json(folder/'SOURCE_SHA256.json',source);rows=[];bodies=[];origins=[]
 for i,(name,old,key,rootname) in enumerate(CASES):
  m,proof=original_template(name,old,key,rootname);sid=identity(PLAN_ID,old);requests=copy.deepcopy(m['requests'])
  for q in requests:q['request_id']=identity(PLAN_ID,name+':REQUEST:'+str(q['ordinal']))
  bank=folder/'banks'/(name+'.json');control.atomic_json(bank,{'requests':requests,'request_count':len(requests)})
  row={k:m[k] for k in ['recipe','arm','order','route','concurrency','wait_ms','resident_mode','perfetto','input_seed','service_cutoff_ns','sensor_end_ns']}
  row.update(protocol=PROTOCOL,session_id=sid,plan_id=PLAN_ID,stage='DEV',block=name,case_name=name,original_failed_session_id=old,prescription_id=key,
   policy_id='FAILED5_'+name,plan_ordinal=i,bank_file='banks/'+name+'.json',bank_sha256=sha256(bank),request_count=len(requests),
   gate_block_id=PLAN_ID+'-'+name,reference_role='SELECT_FIRST',reference_owner_session_id=sid)
  m.update(row);m.update(requests=requests,source_manifest_sha256=sha256(folder/'SOURCE_SHA256.json'),source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip(),
   execution_authorized=True,mock=False,device_status='DEVICE_APPROVED_FOR_NEW_CONTRACT',experiment_ready=False)
  for spec in m['models'].values():spec['identity']['session_id']=sid
  rows.append(row);bodies.append(m);origins.append(proof)
 plan={'schema':'a24-failed5-followon-v1','plan_id':PLAN_ID,'analysis_role':ROLE,'session_count':5,'sessions':rows,'status':'FROZEN_EXECUTION_PLAN',
  'execution_authorized':True,'reference_rules':RULES,'pooled_with_original_confirm':False,'historical_failures_preserved':True,'maximum_new_attempts_per_failed_ID':1}
 validate_plan(plan);control.atomic_json(folder/'plan.json',plan);control.atomic_json(folder/'ORIGINAL_FAILURES.json',origins)
 for m in bodies:
  m['plan_sha256']=sha256(folder/'plan.json');manifest_requests(m,require_materials=True);control.atomic_json(folder/'prepared_manifests'/(m['session_id']+'.json'),m)
 device=dt.datetime.fromisoformat(device_stop);work=dt.datetime.fromisoformat(work_stop)
 require(device.utcoffset() is not None and work.utcoffset() is not None and (work-device).total_seconds()>=300,'reserve final5min')
 window={'execution_authorized':True,'hard_stop_UTC':device.isoformat(),'work_stop_UTC':work.isoformat(),'registered_session_ids':[r['session_id'] for r in rows],
  'plan_sha256':sha256(folder/'plan.json'),'reserved_final_minutes':5,'maximum_attempts_this_window':5,'scope':ROLE}
 check_deadline(window,'NEW_SESSION');control.atomic_json(folder/'USER_WINDOW.json',window)
 budget={'authorized':True,'previous105_preserved':True,'additional_cap':5,'reserved_for_plan':5,'combined_accounting_ceiling':110,'plan_sha256':sha256(folder/'plan.json'),
  'authority':'Latest explicit user: also execute failed cases; finite one fresh ID for each of five failures in final64, not unlimited retry or refunds.'}
 control.atomic_json(folder/'BUDGET.json',budget)
 analysis={'frozen':True,'analysis_role':ROLE,'pooled_with_original_confirm':False,'energy_J':None,'surface_temperature_verified':False,
  'AP_window_seconds':[35,180],'maximum_AP_gap_seconds':10,'service_window_seconds':[0,120],'ON_only_is_not_overhead_comparison':True,
  'reference_rule':'each diagnostic selects its own first stable post-preparation60s; no matched-temperature superiority claim',
  'already_successfully_replicated_elsewhere':['C9_ORDER','R2_PAIR','SUP_ON'],
  'historical_failures_and_all_planned_requests_preserved':True}
 control.atomic_json(folder/'ANALYSIS_CONTRACT.json',analysis);control.atomic_json(folder/'LIFECYCLE_IDENTITY.json',lifecycle_identity())
 contract={'status':'FROZEN_EXECUTION_CONTRACT','plan_sha256':sha256(folder/'plan.json'),'reference_rules':RULES,'energy_J':None,'surface_temperature_verified':False,
  'original_core179_unchanged':True,'original_core179_sha256':sha256(core),'only_runtime_difference':'Perfetto config directory: documented Android12+ path',
  'controller_sha256':sha256(control.CONTROLLER_SOURCE_FILE),'source_sha256':sha256(folder/'SOURCE_SHA256.json'),'runner_sha256':sha256(Path(__file__)),
  'budget_sha256':sha256(folder/'BUDGET.json'),'window_sha256':sha256(folder/'USER_WINDOW.json'),'analysis_sha256':sha256(folder/'ANALYSIS_CONTRACT.json')}
 control.atomic_json(folder/'EXECUTION_CONTRACT.json',contract)
 job.update(plan=str(folder/'plan.json'),prepared_manifests=str(folder/'prepared_manifests'),source_manifest=str(folder/'SOURCE_SHA256.json'),plan_sha256=sha256(folder/'plan.json'),
  window_file=str(folder/'USER_WINDOW.json'),budget_file=str(folder/'BUDGET.json'),analysis_contract=str(folder/'ANALYSIS_CONTRACT.json'),revision_contract_file=str(folder/'EXECUTION_CONTRACT.json'),
  run_root=str(Path(job['run_root']).parent/'A24FAILED5'),failed5_global_root=str(Path(job['run_root']).parent/'A24FAILED5_GLOBAL'),failed5_PC_verification=str(folder/'PC_VERIFICATION.json'))
 control.atomic_json(folder/'job.json',job)
 with tempfile.TemporaryDirectory(prefix='PC_ONLY_',dir=folder) as tmp:
  cases=[]
  for row in rows:
   _,c,_,_=assemble(job,row,Path(tmp));cases.append({'session_id':row['session_id'],'manifest_sha256':c['manifest_sha256']})
 control.atomic_json(folder/'PC_VERIFICATION.json',{'status':'PASS_PC_ONLY','authorization_contexts_PASS':5,'cases':cases,'device_commands':0,'APP_MAIN_claim_sessions':0,
  'mock_references_removed':True,'contract_sha256':sha256(folder/'EXECUTION_CONTRACT.json')});inspect(job)

def inspect(job):
 rows=validate_plan(load_json(Path(job['plan'])));c=load_json(Path(job['revision_contract_file']));pc=load_json(Path(job['failed5_PC_verification']))
 require(c['runner_sha256']==sha256(Path(__file__)) and pc['status']=='PASS_PC_ONLY' and pc['authorization_contexts_PASS']==5
  and pc['contract_sha256']==sha256(Path(job['revision_contract_file'])),'exact PC proof changed')
 lifecycle_identity();control.verify_source_entries(load_json(Path(job['source_manifest'])),ROOT,controller_file=control.CONTROLLER_SOURCE_FILE)
 require(not Path(job['run_root']).exists() and not Path(job['failed5_global_root']).exists(),'already attempted; never replay')
 return rows

def execute(job):
 rows=inspect(job);window=load_json(Path(job['window_file']));check_deadline(window,'NEW_SESSION')
 root=Path(job['run_root']);glob=Path(job['failed5_global_root']);require_no_prior_owners(root.parent)
 glob.mkdir();control.atomic_json(glob/'ACTIVE_OWNER.json',{'pid':os.getpid(),'failed5':True});root.mkdir()
 control.atomic_json(root/'OWNER_WINDOW.json',{'pid':os.getpid(),'window':window,'runner_sha256':sha256(Path(__file__))})
 client=None;outcomes=[];reason='FAILED5_FINISHED'
 try:
  client=FollowupClient(job,load_json(Path(job['device_registration'])),window,glob,{'total_consumed':105,'cap':110});client.job_run_root=str(root);client.reconnect()
  require(client.command('shell','settings','get','system','screen_brightness').decode().strip()=='81','brightness differs')
  require(client.command('shell','settings','get','system','screen_brightness_mode').decode().strip()=='0','mode differs')
  require('mWakefulness=Awake' in client.command('shell','dumpsys','power').decode(),'screen asleep')
  for row in rows:
   sid=row['session_id'];client.check_window('NEW_SESSION');m,c,a,g=assemble(job,row,root)
   reserve=glob/'reservations'/sid;reserve.mkdir(parents=True);control.atomic_json(reserve/'RESERVED.json',{'session_id':sid,'original_failed_id':row['original_failed_session_id']});client.active_sid=sid
   print(json.dumps({'status':'PREPARING_FAILED5','case':row['case_name'],'session_id':sid}),flush=True)
   logfile=root/'logcat'/(sid+'.txt');logfile.parent.mkdir(exist_ok=True)
   with logfile.open('xb') as stream:
    collector=subprocess.Popen(client.prefix+['logcat','-v','epoch','-T','1','tflite:V','D1A24PREP:V','*:S'],stdout=stream,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    try:
     result=control.run_one(m,c,a,g,execute_authorized=True,client=client)
     if result['status']=='COMPLETE_TRACE_RECOVERED':require(finish_only_closed_owned_process(client,root/'raw'/sid,sid,package=c['package_name']),'closed cleanup unproved')
     outcome={**row,'status':result['status']}
    except Exception as error:outcome={**row,'status':'FAILED_PRESERVED','reason':str(error)}
    finally:collector.terminate();collector.wait(timeout=10)
   outcome['APP_launch_intent']=(reserve/'APP_LAUNCH_INTENT.json').exists();control.atomic_json(root/(sid+'.outcome.json'),outcome);control.atomic_json(reserve/'OUTCOME.json',outcome);outcomes.append(outcome)
   print(json.dumps(outcome),flush=True)
   if outcome['status']!='COMPLETE_TRACE_RECOVERED':reason='FAILED_FRESH_ATTEMPT_PRESERVED_NO_REPLAY';break
 except Exception as error:reason='FAILED5_STOP_PRESERVED: '+str(error)
 finally:
  control.atomic_json(root/'WINDOW_STOPPED.json',{'outcomes':outcomes,'reason':reason,'actual_stop_UTC':dt.datetime.now(dt.timezone.utc).isoformat(),
   'new_APP_intents':len(list((glob/'reservations').glob('*/APP_LAUNCH_INTENT.json'))),'actual_ADB_calls':client.actual_calls if client else 0,'additional_cap':5,'old_failures_replaced':False})
  require(load_json(glob/'ACTIVE_OWNER.json')['pid']==os.getpid(),'foreign owner');(glob/'ACTIVE_OWNER.json').unlink()

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='action',required=True)
 a=s.add_parser('prepare');a.add_argument('template',type=Path);a.add_argument('folder',type=Path);a.add_argument('--device-stop',required=True);a.add_argument('--work-stop',required=True)
 for name in ['inspect','execute']:
  a=s.add_parser(name);a.add_argument('job',type=Path)
  if name=='execute':a.add_argument('--execute-authorized',action='store_true')
 a=p.parse_args()
 if a.action=='prepare':prepare(a.template,a.folder.resolve(),a.device_stop,a.work_stop);print(json.dumps({'status':'FAILED5_PC_READY','device_commands':0}))
 elif a.action=='inspect':inspect(load_json(a.job));print(json.dumps({'status':'FAILED5_PC_READY','device_commands':0}))
 else:require(a.execute_authorized,'execution flag missing');execute(load_json(a.job))
