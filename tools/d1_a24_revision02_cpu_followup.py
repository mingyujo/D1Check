"""CPU continuation after passive cooling; a new identity preserves the closed reject."""
import argparse,copy,datetime,json,os,subprocess,time,uuid
from pathlib import Path
from d1_a24_laptop_validator import load_json,sha256
from d1_a24_revision02_control import atomic_json,check_authorization,run_one,verify_source_entries,CONTROLLER_SOURCE_FILE
from d1_a24_revision02_window import ROOT,BoundedClient,check_deadline,assemble
from d1_a24_measurement_batch import finish_only_closed_owned_process

META=ROOT/'output/a24_revision02_cpu_followup_20261015'
ORIGINAL=ROOT/'output/a24_revision02_window01_20261015'
PLAN='A24R02-W01-COOLED-CPU-FOLLOWUP-20261015'
NS=uuid.UUID('6c9f69eb-4e18-4ed6-9f69-1f8c3235547f')

def inherited_reference(job):
    anchor=load_json(Path(job['parent_reference']))
    anchor.update(block_id='R02_COOLED_CPU_FOLLOWUP',parent_reference_sha256=sha256(Path(job['parent_reference'])),
                  inherited_without_reanchoring=True,not_a_preregistered_pair_with_parent_GPU=True)
    return anchor

def prepare():
    META.mkdir(exist_ok=False)
    job=load_json(ORIGINAL/'job.json');oldplan=load_json(Path(job['plan']))
    window={'authorization':'USER_WAIT_UNTIL_COOL_THEN_CONTINUE_CPU_20261015','hard_stop_UTC':'2026-10-15T03:50:00+00:00',
            'maximum_new_sessions':1,'main_inference_before_passive_match':0,'old_failure_preserved':True,
            'new_APP_CREATE_requires_seconds_remaining':1260,'main_START_requires_seconds_remaining':300}
    check_deadline(window,'APP_CREATE');atomic_json(META/'USER_WINDOW.json',window)
    source=load_json(ORIGINAL/'SOURCE_SHA256.json')
    names={f['path'] for f in source['files']}
    names.update(['tools/d1_a24_revision02_cpu_followup.py','tools/d1_a24_revision02_cooldown.py',
                 'benchmark-runner/src/testModelProbe/java/com/example/d1check/benchmarkrunner/A24FollowupManifestPreflightTest.kt'])
    original161=load_json(ROOT/'output/a24_measurement_20261015_v1/measurement_source_sha256_v10.json')
    for f in original161['files']:assert sha256(ROOT/f['path'])==f['sha256'],f['path']
    source.update(measurement_revision='REV02_COOLED_CPU_FOLLOWUP',files=[{'path':n,'bytes':(ROOT/n).stat().st_size,'sha256':sha256(ROOT/n)} for n in sorted(names)])
    atomic_json(META/'SOURCE_SHA256.json',source)
    sid=str(uuid.uuid5(NS,PLAN+':SESSION'))
    row={'session_id':sid,'stage':'DEV','block':'R02_COOLED_CPU_FOLLOWUP','recipe':'C252','arm':'CPU',
         'policy_id':'R02_C252_CPU_COOLED_FOLLOWUP','request_count':252,'reference_role':'MATCH_FIXED','plan_ordinal':0}
    plan={'plan_id':PLAN,'revision_id':'A24-BLOCKED-INITIAL-STATE-REV02-20261015','sessions':[row],
          'maximum_attempts':1,'purpose':'user-requested continuation after cooling; preserve failed attempt; separate wait protocol',
          'parent_plan_sha256':job['plan_sha256'],'not_independent_confirm':True,'not_pooled_with_parent_pair':True,
          'old28_plus_window01_two_attempts_preserved':30,'one_additional_reserved_from34':1,'remaining_if_attempted':33}
    atomic_json(META/'plan.json',plan)
    contract={'scope':'one CPU followup only after passive60s match, no additional GPU or failed-slot relabeling',
              'user_instruction':'wait until cooled then continue','parent_reject_preserved':True,
              'parent_reference_Tref_c':26.1,'passive_wait_outside_app':True,'prepared_history_ns':60000000000,
              'prepared_gate_wait_ns':600000000000,'tolerance_c':.5,'maximum_abs_slope_c_per_min':.1,
              'deadline_UTC':window['hard_stop_UTC'],'maximum_sessions':1,'energy_J':None,
              'no_confirmatory_GPU_CPU_superiority_claim':True,'source_sha256':sha256(META/'SOURCE_SHA256.json')}
    atomic_json(META/'EXECUTION_CONTRACT.json',contract)
    oldrow=next(r for r in oldplan['sessions'] if r['arm']=='CPU')
    manifest=load_json(Path(job['prepared_manifests'])/(oldrow['session_id']+'.json'))
    manifest.update(**row,plan_id=PLAN,plan_sha256=sha256(META/'plan.json'),source_manifest_sha256=sha256(META/'SOURCE_SHA256.json'),
                    continuation_of_prestart_failed_session=oldrow['session_id'],wait_protocol='PASSIVE_COOL_BEFORE_APP_THEN_EXISTING_PREPARED_GATE')
    for model in manifest['models'].values():
        model['identity'].update(session_id=sid,created_utc=datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'))
    for q in manifest['requests']:q['request_id']=str(uuid.uuid5(NS,PLAN+':REQUEST:'+str(q['ordinal'])))
    atomic_json(META/'request_bank.json',{'requests':manifest['requests'],'plan_id':PLAN})
    manifest.update(bank_file='request_bank.json',bank_sha256=sha256(META/'request_bank.json'))
    manifests=META/'prepared_manifests';manifests.mkdir();atomic_json(manifests/(sid+'.json'),manifest)
    job.update(plan=str(META/'plan.json'),plan_sha256=sha256(META/'plan.json'),source_manifest=str(META/'SOURCE_SHA256.json'),
               prepared_manifests=str(manifests),run_root=str(Path(job['run_root']).parent/'A24R02W2'),
               parent_reference=str(Path(job['run_root'])/'block_reference.json'),window_file=str(META/'USER_WINDOW.json'),
               revision_contract_file=str(META/'EXECUTION_CONTRACT.json'),maximum_registered_sessions=1,
               passive_receipt=str(ORIGINAL/'passive_after_failed_CPU/PASSIVE_STOPPED.json'))
    atomic_json(META/'job.json',job)
    fixture=META/'PC_fixture';fixture.mkdir();atomic_json(fixture/'block_reference.json',inherited_reference(job))
    m,c,a,g=assemble(job,row,fixture);check_authorization(m,c,a,g,execute_authorized=True)
    atomic_json(META/'HOST_AUTH_PC_CHECK.json',{'status':'PASS_PC_ONLY','manifest_sha256':c['manifest_sha256'],'source_sha256':c['source_code_sha256'],'device_commands':0,'START':0})
    print(json.dumps({'prepared_CPU_followup':sid,'device_commands':0,'source_files':len(source['files'])}))

def execute():
    job=load_json(META/'job.json');window=load_json(Path(job['window_file']));proof=load_json(META/'PC_VERIFIED.json')
    assert proof['status']=='PASS_PC_ONLY' and proof['source_sha256']==sha256(Path(job['source_manifest']))
    verify_source_entries(load_json(Path(job['source_manifest'])),ROOT,controller_file=CONTROLLER_SOURCE_FILE)
    while not Path(job['passive_receipt']).exists():
        try:check_deadline(window,'APP_CREATE')
        except Exception:
            atomic_json(META/'NOT_STARTED_TIME_WINDOW.json',{'new_app_starts':0,'new_warmups':0,'new_main_inference':0,'reason':'no remaining21min for app watchdog/drain before12:50'});return
        time.sleep(5)
    passive=load_json(Path(job['passive_receipt']))
    if passive['passive_60s_match'] is not True:
        atomic_json(META/'NOT_STARTED_COOLDOWN.json',{'new_app_starts':0,'new_warmups':0,'new_main_inference':0,'reason':'passive initial state did not match before deadline'});return
    check_deadline(window,'APP_CREATE');root=Path(job['run_root']);root.mkdir(exist_ok=False)
    atomic_json(root/'block_reference.json',inherited_reference(job));atomic_json(root/'OWNER_WINDOW.json',{'pid':os.getpid(),'window':window,'max_sessions':1})
    target=load_json(Path(job['device_registration']));client=BoundedClient(job,target,window)
    assert client.command('shell','getprop','ro.serialno').decode().strip()==target['hardware_serial']
    assert client.command('shell','getprop','ro.build.fingerprint').decode().strip()==target['build_fingerprint']
    row=load_json(Path(job['plan']))['sessions'][0];m,c,a,g=assemble(job,row,root)
    logdir=root/'logcat';logdir.mkdir()
    with (logdir/(row['session_id']+'.txt')).open('xb') as log:
        collector=subprocess.Popen(client.prefix+['logcat','-v','epoch','-T','1','tflite:V','D1A24PREP:V','*:S'],stdout=log,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        try:
            result=run_one(m,c,a,g,execute_authorized=True,client=client)
            outcome={'session_id':row['session_id'],'arm':'CPU','status':result['status'],'parent_failed_attempt_preserved':True}
        except Exception as error:outcome={'session_id':row['session_id'],'arm':'CPU','status':'FAILED_PRESERVED','reason':str(error)}
        finally:collector.terminate();collector.wait(timeout=10)
    atomic_json(root/(row['session_id']+'.outcome.json'),outcome)
    released=finish_only_closed_owned_process(client,root/'raw'/row['session_id'],row['session_id'],package=c['package_name'])
    atomic_json(root/'WINDOW_STOPPED.json',{'outcome':outcome,'owned_closed_process_released':released,'actual_stop_UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'no_further_sessions':True})
    print(json.dumps(outcome),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--prepare',action='store_true');p.add_argument('--execute-authorized',action='store_true');a=p.parse_args()
    if a.prepare and not a.execute_authorized:prepare()
    elif a.execute_authorized and not a.prepare:execute()
    else:p.error('choose one explicit mode')
