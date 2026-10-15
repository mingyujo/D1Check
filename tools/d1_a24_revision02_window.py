"""Bounded REV02 C252 development pair. Default mode is offline preparation only."""
from __future__ import annotations
import argparse,copy,datetime,hashlib,json,os,random,subprocess,sys,time,uuid
from pathlib import Path
from d1_a24_laptop_validator import load_json,sha256,ValidationError
from d1_a24_laptop_control import atomic_json
from d1_a24_measurement_connection import ReconnectingAdbClient
from d1_a24_measurement_batch import TARGET_KEYS,finish_only_closed_owned_process
from d1_a24_revision02_control import run_one,verify_source_entries,CONTROLLER_SOURCE_FILE,read_battery,read_hal
from d1_a24_revision02_design import matches_fixed_reference,NS

REVISION='A24-BLOCKED-INITIAL-STATE-REV02-20261015'
PLAN_ID='A24R02-W01-20261015-C252-PILOT'
ROOT=Path(__file__).resolve().parents[1]
META=ROOT/'output/a24_revision02_window01_20261015'
OLD=ROOT/'output/a24_measurement_20261015_v1'
NAMESPACE=uuid.UUID('9f59cb8a-4b33-4d6a-82c9-6136539c7a11')

def encode(x):return (json.dumps(x,sort_keys=True,indent=2)+'\n').encode()
def utc_epoch(x):return datetime.datetime.fromisoformat(x).timestamp()

def check_deadline(window,phase,now=None):
    now=time.time() if now is None else now
    seconds=utc_epoch(window['hard_stop_UTC'])-now
    reserve={'APP_CREATE':1260,'MAIN_START':300,'NEW_SESSION':1260,'RPC':1}.get(phase)
    if reserve is None or seconds<reserve:raise ValidationError('bounded window does not admit '+phase)
    return seconds

class BoundedClient(ReconnectingAdbClient):
    bounded_window_authorized=True
    def __init__(self,job,target,window):
        self.window=window
        def runner(argv,**kwargs):
            remaining=check_deadline(window,'RPC')
            kwargs['timeout']=min(kwargs.get('timeout',30),max(.1,remaining-1))
            return subprocess.run(argv,**kwargs)
        super().__init__(job['adb'],target['adb_serial'],target['hardware_serial'],target['build_fingerprint'],Path(job['run_root'])/'adb_commands.jsonl',wait_seconds=max(0,min(1200,utc_epoch(window['hard_stop_UTC'])-time.time()-2)),runner=runner)
    def check_window(self,phase):return check_deadline(self.window,phase)

def prepare():
    window=load_json(META/'USER_WINDOW.json');check_deadline(window,'NEW_SESSION')
    job=load_json(OLD/'job_confirm_v10.json');old_plan=load_json(Path(job['plan']))
    old_target=load_json(Path(job['device_registration']));identity=load_json(Path(job['apk_identity']))
    # All original161 scientific/runtime source bytes remain immutable.
    old_source=load_json(Path(job['source_manifest']))
    for f in old_source['files']:
        p=ROOT/f['path'];assert p.stat().st_size==f['bytes'] and sha256(p)==f['sha256'],f['path']
    new_names=['tools/d1_a24_revision02_control.py','tools/d1_a24_revision02_window.py','tools/d1_a24_revision02_design.py','tools/test_d1_a24_revision02_window.py','benchmark-runner/src/testModelProbe/java/com/example/d1check/benchmarkrunner/A24Revision02ManifestPreflightTest.kt']
    entries={f['path']:f for f in old_source['files']}
    for name in new_names:
        p=ROOT/name;entries[name]={'path':name,'bytes':p.stat().st_size,'sha256':sha256(p)}
    source=copy.deepcopy(old_source);source.update(measurement_revision='REV02-WINDOW01-PILOT',source_base_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),source_uncommitted=True,files=list(entries.values()))
    atomic_json(META/'SOURCE_SHA256.json',source)
    remaining=[r for r in old_plan['sessions'] if r['stage']=='CONFIRM' and not (Path(job['run_root'])/(r['session_id']+'.outcome.json')).exists()]
    assert len(remaining)==36
    transfer={'old_cap':64,'old_attempts_preserved':28,'old_unattempted_before':36,'reserved_new_pilot':2,'old_unused_retired_from_original_plan':[r['session_id'] for r in remaining[:2]],'old_remaining_unallocated_after_reservation':34,'failed_or_stopped_replacements':0,'new_user_time_window_SHA':sha256(META/'USER_WINDOW.json'),'future32_proposal_not_executed':True}
    atomic_json(META/'BUDGET_TRANSFER.json',transfer)
    arms=['CPU','GPU'];random.Random(2026101508).shuffle(arms)
    rows=[]
    for index,arm in enumerate(arms):
        sid=str(uuid.uuid5(NAMESPACE,PLAN_ID+':SESSION:'+arm))
        rows.append({'session_id':sid,'stage':'DEV','block':'R02W01_C252','recipe':'C252','arm':arm,'policy_id':'R02_C252_'+arm,'plan_ordinal':index,'reference_role':'SELECT_FIRST' if index==0 else 'MATCH_FIXED','request_count':252})
    plan={'schema':'a24-revision02-bounded-pilot-plan-v1','plan_id':PLAN_ID,'revision_id':REVISION,'status':'AUTHORIZED_BOUNDED_DEVELOPMENT_PILOT','session_count':2,'independent_pairs':1,'sessions':rows,'window_sha256':sha256(META/'USER_WINDOW.json'),'source_sha256':sha256(META/'SOURCE_SHA256.json'),'old_plan_sha256':job['plan_sha256'],'budget_transfer_sha256':sha256(META/'BUDGET_TRANSFER.json'),'pool_with_old_revision':False,'stage':'DEV','input_seed':2026101507,'order_seed':2026101508,'energy_J_supported':False,'surface_temperature_verified':False,'model_accuracy_PASS':False,'no_numeric_forecaster':True}
    atomic_json(META/'plan.json',plan)
    contract={'revision_id':REVISION,'pilot_plan_sha256':sha256(META/'plan.json'),'execution_authorized':True,'scope':'C252 CPU/GPU one development pair, maximum2 attempts, no replacement','window_sha256':sha256(META/'USER_WINDOW.json'),'reference_algorithm':'first eligible common-post-ready60s AP median, frozen before first main request and shared by both arms','history_ns':60000000000,'maximum_gap_ns':10000000000,'tolerance_c':.5,'maximum_abs_slope_c_per_min':.1,'maximum_wait_ns':600000000000,'service_window_s':[0,120],'AP_window_s':[35,180],'logging_end_s':210,'no_reanchor':True,'code_sha256':sha256(META/'SOURCE_SHA256.json'),'energy_J':None,'sensor_cache_age_verified':False,'not_final_confirm':True}
    atomic_json(META/'EXECUTION_CONTRACT.json',contract)
    manifests=META/'prepared_manifests';manifests.mkdir()
    banks=META/'request_banks';banks.mkdir()
    old_sids={r['session_id'] for r in old_plan['sessions']}
    old_request_ids=set()
    for r in old_plan['sessions']:
        old_request_ids.update(q['request_id'] for q in load_json(Path(job['prepared_manifests'])/(r['session_id']+'.json'))['requests'])
    for row in rows:
        original=next(r for r in old_plan['sessions'] if r['recipe']=='C252' and r['arm']==row['arm'])
        manifest=copy.deepcopy(load_json(Path(job['prepared_manifests'])/(original['session_id']+'.json')))
        manifest.update(**row,plan_id=PLAN_ID,plan_sha256=sha256(META/'plan.json'),revision_id=REVISION,execution_authorized=True,authorization='USER_AUTHORIZED_BOUNDED_REV02_20261015',device_status='DEVICE_APPROVED_FOR_NEW_CONTRACT',device_fingerprint=old_target['build_fingerprint'],target_model=old_target['model'],apk_sha256=identity['apk_sha256'],source_commit=source['source_base_commit'],source_manifest_sha256=sha256(META/'SOURCE_SHA256.json'),experiment_ready=False,preparation_counters_are_historical=True,soc_contract='USER_SOC_GE10_20261015',minimum_battery_percent=10,input_seed=2026101507)
        sid=row['session_id'];assert sid not in old_sids
        for spec in manifest['models'].values():
            spec['identity']['session_id']=sid
            spec['identity']['created_utc']=datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
            spec['target']={k:old_target[k] for k in TARGET_KEYS}
            spec['target'].update(apk_sha256=identity['apk_sha256'],package_name=identity['package'])
        for q in manifest['requests']:
            q['request_id']=str(uuid.uuid5(NAMESPACE,PLAN_ID+':REQUEST:'+str(q['ordinal'])))
            assert q['request_id'] not in old_request_ids
        bank={'schema':'a24-revision02-request-bank-v1','plan_id':PLAN_ID,'recipe':'C252','input_seed':2026101507,'requests':manifest['requests']}
        bank_path=banks/'C252.json'
        if not bank_path.exists():atomic_json(bank_path,bank)
        else:assert load_json(bank_path)==bank
        manifest.update(bank_file='request_banks/C252.json',bank_sha256=sha256(bank_path))
        atomic_json(manifests/(sid+'.json'),manifest)
    job.update(plan=str(META/'plan.json'),plan_sha256=sha256(META/'plan.json'),source_manifest=str(META/'SOURCE_SHA256.json'),source_base_commit=source['source_base_commit'],run_root=str(Path(job['run_root']).parent/'A24R02W1'),prepared_manifests=str(manifests),window_file=str(META/'USER_WINDOW.json'),revision_contract_file=str(META/'EXECUTION_CONTRACT.json'),maximum_registered_sessions=2,old_measurement_not_restarted=True)
    for obsolete in ('confirm_freeze','prior_failed_slots_file','skip_failed_slot_ids'):
        job.pop(obsolete,None)
    atomic_json(META/'job.json',job)
    print(json.dumps({'offline_prepared_sessions':2,'reference_arm':arms[0],'device_commands':0,'old_slots_reserved':2,'old_attempts_preserved':28}),flush=True)

def assemble(job,row,root):
    window=load_json(Path(job['window_file']));check_deadline(window,'NEW_SESSION')
    directory=root/'bindings'/row['session_id'];directory.mkdir(parents=True,exist_ok=False)
    manifest=load_json(Path(job['prepared_manifests'])/(row['session_id']+'.json'));identity=load_json(Path(job['apk_identity']));target=load_json(Path(job['device_registration']))
    for name in job['input_filenames']:os.link(Path(job['input_root'])/name,directory/name)
    atomic_json(directory/'session_manifest.json',manifest)
    gate=load_json(Path(job['gate']));reference=root/'block_reference.json'
    for historical in ('Tref_method','Tref_source_attempt','Tref_source_sha256','prior_gate_sha256','polling_evidence_max_gap_s'):
        gate.pop(historical,None)
    gate.update(gate_revision='REV02_FIRST_ELIGIBLE_BLOCK_REFERENCE',registration_scope='bounded development pair only; not CONFIRM',schema='a24-revision02-blocked-gate-v1',reference_role=row['reference_role'],block_id=row['block'],Tref_c=None,block_reference_path=str(reference),screen_contract='manual81/255; interactive; unplugged; actual timeout and environment recorded at this window preflight; no settings changed')
    if row['reference_role']=='MATCH_FIXED':
        anchor=load_json(reference);gate.update(Tref_c=anchor['Tref_c'],block_reference_sha256=sha256(reference))
    gate_bytes=encode(gate);atomic_json(directory/'gate.json',gate)
    files=[{'path':p.name,'bytes':p.stat().st_size,'sha256':sha256(p)} for p in directory.iterdir() if p.is_file() and p.name!='gate.json']
    config={'manifest_bytes':(directory/'session_manifest.json').read_bytes(),'manifest_sha256':sha256(directory/'session_manifest.json'),'gate_bytes':(directory/'gate.json').read_bytes(),'gate_sha256':sha256(directory/'gate.json'),'apk':{'path':job['apk'],'sha256':identity['apk_sha256']},'adb':{'path':job['adb'],'sha256':sha256(Path(job['adb']))},'apk_identity':identity,'bundle_root':str(directory),'files':files,'source_root':str(ROOT),'source_code_manifest':job['source_manifest'],'source_code_sha256':sha256(Path(job['source_manifest'])),'host_dependency_lock':job['host_dependency_lock'],'host_dependency_lock_sha256':sha256(Path(job['host_dependency_lock'])),'registry_root':str(root/'registry'/manifest['protocol']/manifest['plan_id']),'output_root':str(root/'raw'),'reuse_verified_installed_APK':True,'package_name':identity['package'],'require_journal_closed_before_recovery':True,'window_file':job['window_file'],'window_sha256':sha256(Path(job['window_file'])),'revision_contract_file':job['revision_contract_file'],'revision_contract_sha256':sha256(Path(job['revision_contract_file']))}
    auth={'schema':'a24-laptop-control-authorization-v1','authorization':'USER_EXPLICIT_FUTURE_A24_MEASUREMENT','scope':'one_new_session','session_id':row['session_id'],'plan_sha256':job['plan_sha256'],'manifest_sha256':config['manifest_sha256'],'gate_sha256':config['gate_sha256'],'apk_sha256':identity['apk_sha256'],'serial':target['adb_serial'],'fingerprint':target['build_fingerprint'],'expected_model':'SM-A245N','api_level':target['api_level'],'ram_bytes':target['ram_bytes'],'source_code_sha256':config['source_code_sha256'],'host_dependency_lock_sha256':config['host_dependency_lock_sha256'],'control_source_sha256':sha256(Path(__file__).parent/'d1_a24_revision02_control.py'),'package_name':identity['package'],'window_sha256':config['window_sha256'],'revision_contract_sha256':config['revision_contract_sha256']}
    atomic_json(directory/'authorization.json',auth);atomic_json(directory/'config.json',{k:v for k,v in config.items() if not isinstance(v,bytes)})
    return manifest,config,auth,gate

def passive_before_next_app(job,client,row,root,window):
    reference=load_json(root/'block_reference.json')
    directory=root/'pre_app_cooldown';directory.mkdir(exist_ok=True)
    readings=[];rules={'history_ns':60*NS,'maximum_wait_ns':3600*NS,'maximum_gap_ns':10*NS,'tolerance_c':.5,'maximum_abs_slope_c_per_min':.1}
    with (directory/(row['session_id']+'.jsonl')).open('x',encoding='utf8') as stream:
        while True:
            check_deadline(window,'NEW_SESSION')
            sample=read_hal(client);stream.write(json.dumps(sample)+'\n');stream.flush()
            ap=[v['value_c'] for v in sample['sensors'] if v['sensor_name']=='AP' and v['sensor_type']==0]
            readings.append({'before_ns':sample['device_elapsed_before_ns'],'after_ns':sample['device_elapsed_after_ns'],'AP_c':ap[0] if len(ap)==1 else None})
            cutoff=readings[-1]['before_ns']-60*NS
            starts=[i for i,r in enumerate(readings) if r['before_ns']<=cutoff]
            recent=readings[starts[-1]:] if starts else readings
            ready=bool(starts) and len(ap)==1 and ap[0]<=reference['Tref_c'] and matches_fixed_reference(recent,recent[0]['before_ns'],reference,rules)
            if len(readings)%12==1 or ready:print(json.dumps({'status':'PASSIVE_COOL_BEFORE_CPU_APP','AP_c':ap,'Tref_c':reference['Tref_c'],'ready':ready,'new_app_started':False}),flush=True)
            if ready:
                atomic_json(directory/(row['session_id']+'.ready.json'),{'source_reference_sha256':sha256(root/'block_reference.json'),'samples':len(readings),'last_AP_c':ap[0],'new_app_started':False,'post_warmup_gate_still_required':True});return
            time.sleep(5)


def execute():
    job=load_json(META/'job.json');window=load_json(Path(job['window_file']));check_deadline(window,'NEW_SESSION')
    proof=load_json(META/'PC_VERIFIED.json')
    assert proof['status']=='PASS_PC_ONLY' and proof['source_sha256']==sha256(Path(job['source_manifest']))
    verify_source_entries(load_json(Path(job['source_manifest'])),ROOT,controller_file=CONTROLLER_SOURCE_FILE)
    plan=load_json(Path(job['plan']));assert sha256(Path(job['plan']))==job['plan_sha256']
    root=Path(job['run_root']);root.mkdir(exist_ok=False)
    if job.get('initial_reference_file'):
        atomic_json(root/'block_reference.json',load_json(Path(job['initial_reference_file'])))
    atomic_json(root/'OWNER_WINDOW.json',{'pid':os.getpid(),'window':window,'max_sessions':2})
    target=load_json(Path(job['device_registration']));client=BoundedClient(job,target,window)
    # Explicit identity handshake is read-only; no old job or old owner is resumed.
    assert client.command('shell','getprop','ro.serialno').decode().strip()==target['hardware_serial']
    assert client.command('shell','getprop','ro.build.fingerprint').decode().strip()==target['build_fingerprint']
    battery=read_battery(client)
    assert isinstance(battery['SOC_percent'],(int,float)) and battery['SOC_percent']>=10 and battery['plugged'] is False,'battery/unplugged contract not met'
    screen={}
    for key in ('screen_brightness','screen_brightness_mode','screen_off_timeout'):
        screen[key]=client.command('shell','settings','get','system',key).decode().strip()
    power=client.command('shell','dumpsys','power').decode()
    assert screen['screen_brightness']=='81' and screen['screen_brightness_mode']=='0' and 'mWakefulness=Awake' in power,'screen setup changed; no automatic setting change'
    atomic_json(root/'DEVICE_WINDOW_PREFLIGHT.json',{'battery':battery,'screen_settings':screen,'physical_environment_measured':False,'settings_changed':False,'identity_match':True,'UTC':datetime.datetime.now(datetime.timezone.utc).isoformat()})
    outcomes=[]
    for row in plan['sessions']:
        try:
            if outcomes and job.get('passive_cool_before_next_app'):
                passive_before_next_app(job,client,row,root,window)
            check_deadline(window,'NEW_SESSION')
        except ValidationError:
            print(json.dumps({'status':'WINDOW_STOP_NO_NEW_SESSION','unstarted_session':row['session_id']}),flush=True);break
        m,c,a,g=assemble(job,row,root)
        logpath=root/'logcat'/f"{row['session_id']}.txt";logpath.parent.mkdir(exist_ok=True)
        print(json.dumps({'status':'PREPARING_NEW_REV02_PILOT','arm':row['arm'],'reference_role':row['reference_role'],'session_id':row['session_id']}),flush=True)
        with logpath.open('xb') as log:
            collector=subprocess.Popen(client.prefix+['logcat','-v','epoch','-T','1','tflite:V','D1A24PREP:V','*:S'],stdout=log,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            try:
                result=run_one(m,c,a,g,execute_authorized=True,client=client)
                outcome={'session_id':row['session_id'],'arm':row['arm'],'revision_id':REVISION,'status':result['status'],'reference_role':row['reference_role'],'actual_ADB_calls_cumulative':client.actual_calls}
            except Exception as error:outcome={'session_id':row['session_id'],'arm':row['arm'],'status':'FAILED_PRESERVED','reason':str(error)}
            finally:collector.terminate();collector.wait(timeout=10)
        atomic_json(root/(row['session_id']+'.outcome.json'),outcome);outcomes.append(outcome);print(json.dumps(outcome),flush=True)
        raw=root/'raw'/row['session_id']
        if outcome['status']!='COMPLETE_TRACE_RECOVERED' or not finish_only_closed_owned_process(client,raw,row['session_id'],package=c['package_name']):break
        if len(outcomes)<2:
            remaining_idle=job.get('inter_arm_idle_seconds',90)
            while remaining_idle>0:
                check_deadline(window,'RPC');duration=min(30,remaining_idle);time.sleep(duration);remaining_idle-=duration
    atomic_json(root/'WINDOW_STOPPED.json',{'outcomes':outcomes,'no_additional_sessions':True,'hard_stop_UTC':window['hard_stop_UTC'],'actual_stop_UTC':datetime.datetime.now(datetime.timezone.utc).isoformat()})
    print(json.dumps({'status':'BOUNDED_PILOT_STOPPED','terminal_outcomes':len(outcomes),'maximum2_sessions':True}),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--prepare',action='store_true');p.add_argument('--execute-authorized',action='store_true');a=p.parse_args()
    if a.prepare and not a.execute_authorized:prepare()
    elif a.execute_authorized and not a.prepare:execute()
    else:p.error('choose offline --prepare or explicit --execute-authorized')
