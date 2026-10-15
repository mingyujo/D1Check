"""New GPU-first block at the user's current stable AP reference; no pooling."""
import argparse,copy,datetime,json,uuid
from pathlib import Path
import d1_a24_revision02_window as w
from d1_a24_revision02_control import atomic_json,check_authorization
from d1_a24_laptop_validator import load_json,sha256
from d1_a24_revision02_design import first_reference,NS

META=w.ROOT/'output/a24_revision02_current_block03_20261015'
OLD=w.ROOT/'output/a24_revision02_window01_20261015'
PLAN='A24R02-W01-CURRENT-BLOCK03-20261015'
IDS=uuid.UUID('9eb936a5-a7c4-4d8b-92dc-e7004fc638e3')

def prepare():
    META.mkdir(exist_ok=False)
    window={'authorization':'USER_CURRENT_AP_REFERENCE_GPU_FIRST_20261015','hard_stop_UTC':'2026-10-15T03:50:00+00:00','maximum_new_sessions':2,
            'app_create_min_remaining_s':1260,'main_start_min_remaining_s':300,'no_extension_past1250':True}
    w.check_deadline(window,'APP_CREATE');atomic_json(META/'USER_WINDOW.json',window)
    records=[json.loads(line) for line in (OLD/'passive_after_failed_CPU/readings.jsonl').read_text().splitlines()]
    recent=[r for r in records if r['device_elapsed_before_ns']>=records[-1]['device_elapsed_before_ns']-66*NS]
    simplified=[]
    for r in recent:
        ap=[s['value_c'] for s in r['sensors'] if s['sensor_name']=='AP' and s['sensor_type']==0]
        simplified.append({'before_ns':r['device_elapsed_before_ns'],'after_ns':r['device_elapsed_after_ns'],'AP_c':ap[0] if len(ap)==1 else None})
    reference=first_reference(simplified,simplified[0]['before_ns'],{'history_ns':60*NS,'maximum_wait_ns':600*NS,'maximum_gap_ns':10*NS,'tolerance_c':.5,'maximum_abs_slope_c_per_min':.1})
    assert reference is not None,'current fixed trailing history is not stable; no favorable older selection'
    reference.update(block_id='R02_CURRENT_BLOCK03',reference_source='latest fixed66s passive readout window at user current-reference instruction; first eligible60s',
                     observation_file_sha256=sha256(OLD/'passive_after_failed_CPU/readings.jsonl'),frozen_before_any_new_main_request=True,
                     user_changed_initial_state_protocol=True,old26_1_reference_and_results_preserved=True)
    atomic_json(META/'block_reference.json',reference)
    oldjob=load_json(OLD/'job.json');oldplan=load_json(Path(oldjob['plan']))
    source=load_json(w.ROOT/'output/a24_revision02_cpu_followup_20261015/SOURCE_SHA256.json')
    names={f['path'] for f in source['files']};names.add('tools/d1_a24_revision02_current_block.py')
    source.update(measurement_revision='REV02_CURRENT_PASSIVE_REFERENCE_BLOCK03',files=[{'path':n,'bytes':(w.ROOT/n).stat().st_size,'sha256':sha256(w.ROOT/n)} for n in sorted(names)])
    atomic_json(META/'SOURCE_SHA256.json',source)
    rows=[{'session_id':str(uuid.uuid5(IDS,PLAN+':'+arm)),'stage':'DEV','block':'R02_CURRENT_BLOCK03','recipe':'C252','arm':arm,
           'policy_id':'R02_V3_C252_'+arm,'plan_ordinal':i,'reference_role':'MATCH_FIXED','request_count':252} for i,arm in enumerate(['GPU','CPU'])]
    plan={'plan_id':PLAN,'revision_id':w.REVISION,'sessions':rows,'maximum_attempts':2,'request_count':504,'user_order':'GPU then CPU',
          'reference_sha256':sha256(META/'block_reference.json'),'pool_with_previous_block':False,'old_attempts_preserved':30,
          'new_two_reserved_from34':2,'unallocated_if_both_attempted':32,'pending_followup_CANCELLED_without_app_or_START':True}
    atomic_json(META/'plan.json',plan)
    atomic_json(META/'EXECUTION_CONTRACT.json',{'scope':'new current-reference development block, GPU then CPU, at most2 attempts','initial_reference_c':reference['Tref_c'],
        'reference_sha256':sha256(META/'block_reference.json'),'prepared_history_ns':60*NS,'prepared_maximum_wait_ns':600*NS,'tolerance_c':.5,
        'maximum_abs_slope_c_per_min':.1,'maximum_observation_gap_ns':10*NS,'no_reanchor_between_arms':True,'inter_arm_extra_idle_s':0,
        'inter_arm_actual_post_ready_gate_required':True,'deadline_UTC':window['hard_stop_UTC'],'new_source_sha256':sha256(META/'SOURCE_SHA256.json'),
        'old_GPU_and_CPU_reject_preserved':True,'existing_APK_unchanged':True,'energy_J':None,'final_CONFIRM':False})
    manifests=META/'prepared_manifests';manifests.mkdir()
    for row in rows:
        oldrow=next(r for r in oldplan['sessions'] if r['arm']==row['arm'])
        m=load_json(Path(oldjob['prepared_manifests'])/(oldrow['session_id']+'.json'))
        m.update(**row,plan_id=PLAN,plan_sha256=sha256(META/'plan.json'),source_manifest_sha256=sha256(META/'SOURCE_SHA256.json'),
                 initial_state_protocol='CURRENT_PASSIVE_REFERENCE_V3',old_results_not_pooled=True)
        for spec in m['models'].values():spec['identity'].update(session_id=row['session_id'],created_utc=datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'))
        for q in m['requests']:q['request_id']=str(uuid.uuid5(IDS,PLAN+':REQUEST:'+str(q['ordinal'])))
        bank={'requests':m['requests'],'plan_id':PLAN}
        if not (META/'request_bank.json').exists():atomic_json(META/'request_bank.json',bank)
        else:assert load_json(META/'request_bank.json')==bank
        m.update(bank_file='request_bank.json',bank_sha256=sha256(META/'request_bank.json'))
        atomic_json(manifests/(row['session_id']+'.json'),m)
    oldjob.update(plan=str(META/'plan.json'),plan_sha256=sha256(META/'plan.json'),source_manifest=str(META/'SOURCE_SHA256.json'),prepared_manifests=str(manifests),
                  window_file=str(META/'USER_WINDOW.json'),revision_contract_file=str(META/'EXECUTION_CONTRACT.json'),
                  run_root=str(Path(oldjob['run_root']).parent/'A24R02W3'),initial_reference_file=str(META/'block_reference.json'),inter_arm_idle_seconds=0,maximum_registered_sessions=2)
    atomic_json(META/'job.json',oldjob)
    fixture=META/'PC_fixture';fixture.mkdir();atomic_json(fixture/'block_reference.json',reference)
    for row in rows:
        m,c,a,g=w.assemble(oldjob,row,fixture);check_authorization(m,c,a,g,execute_authorized=True)
    atomic_json(META/'HOST_AUTH_PC_CHECK.json',{'status':'PASS_PC_ONLY','exact_bundles':2,'source_sha256':sha256(META/'SOURCE_SHA256.json'),'device_commands':0,'START':0})
    print(json.dumps({'current_reference_c':reference['Tref_c'],'new_manifests':2,'source_files':len(names),'device_commands':0}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--prepare',action='store_true');p.add_argument('--execute-authorized',action='store_true');a=p.parse_args()
    if a.prepare and not a.execute_authorized:prepare()
    elif a.execute_authorized and not a.prepare:w.META=META;w.execute()
    else:p.error('choose one explicit mode')
