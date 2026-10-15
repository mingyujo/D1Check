"""Continue only unused extra4 IDs; repair the pre-APP upper-bound predicate.

MAIN admission, reference bytes, APK and inference lifecycle remain unchanged.
The shared original extra4 registry counts the first WAIT and the pending3.
"""
import argparse
import copy
import datetime as dt
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

import d1_a24_extra4_runner as original
from d1_a24_extra4_contract import validate_extra4_plan
from d1_a24_laptop_validator import load_json, sha256, NS
from d1_a24_revision02_suite import require
from d1_a24_suite_dev_continue import cold_enough_to_prepare

control=original.control;ROOT=original.ROOT


def stable_enough_to_prepare(samples,gate):
    """Preparation only: a stable AP at or below the MAIN upper band may prepare."""
    require(gate['tref_tolerance_c']==0.5,'MAIN tolerance must remain unchanged')
    return cold_enough_to_prepare(samples,gate['Tref_c']+gate['tref_tolerance_c'])


def passive_before_APP(client,gate,evidence):
    require(not evidence.exists(),'write-once preparation evidence')
    evidence.parent.mkdir(exist_ok=True);samples=[]
    while True:
        client.check_window('NEW_SESSION')
        require(sha256(Path(gate['block_reference_path']))==gate['block_reference_sha256'],'fixed reference changed')
        x=control.read_hal(client)
        with evidence.open('a',encoding='utf-8') as f:f.write(json.dumps(x)+'\n')
        ap=[s['value_c'] for s in x['sensors'] if s['sensor_name']=='AP' and s['sensor_type']==0]
        samples.append({'before_ns':x['device_elapsed_before_ns'],'after_ns':x['device_elapsed_after_ns'],
                        'AP_c':ap[0] if len(ap)==1 else None})
        if stable_enough_to_prepare(samples,gate):
            control.atomic_json(evidence.with_suffix('.ready.json'),{'status':'PREPARATION_ONLY_STABLE_BELOW_MAIN_UPPER',
                'MAIN_admitted':False,'post_warmup_MAIN_rules_unchanged':True,'last_AP_c':ap[0],
                'Tref_c':gate['Tref_c'],'preparation_upper_c':gate['Tref_c']+gate['tref_tolerance_c'],
                'reference_sha256':gate['block_reference_sha256'],'samples':len(samples),
                'observed_device_elapsed_s':(samples[-1]['after_ns']-samples[0]['before_ns'])/NS})
            return
        require(samples[-1]['after_ns']-samples[0]['before_ns']<=600*NS,'PRE_APP_STABLE_UPPER_TIMEOUT_APP0')
        client.sleep_ns(5*NS)


def previous_evidence(job):
    oldroot=Path(job['previous_extra4_root']);globalroot=Path(job['extra4_global_root'])
    require(not (globalroot/'ACTIVE_OWNER.json').exists(),'extra4 owner active')
    stop=load_json(oldroot/'WINDOW_STOPPED.json');rows=validate_extra4_plan(load_json(Path(job['plan'])))
    require(stop['new_APP_intents']==1 and len(stop['outcomes'])==1
            and stop['outcomes'][0]['session_id']==rows[0]['session_id']
            and stop['outcomes'][0]['status']=='COMPLETE_TRACE_RECOVERED','only closed first WAIT can be carried')
    require(sha256(oldroot/'WINDOW_STOPPED.json')==job['previous_extra4_stop_sha256'],'old extra4 stop changed')
    used=rows[0]['session_id'];raw=oldroot/'raw'/used
    require(load_json(raw/'journal_closed.json')['status']=='SYNCED_AND_CLOSED','old WAIT not closed')
    require(sha256(raw/'events.jsonl')==job['previous_WAIT_events_sha256']
            and sha256(raw/'journal_closed.json')==job['previous_WAIT_closed_sha256'],'old WAIT raw changed')
    reserved=list((globalroot/'reservations').iterdir())
    require([p.name for p in reserved]==[used] and (reserved[0]/'APP_LAUNCH_INTENT.json').exists(),
            'extra4 used IDs differ; never replay')
    for row in rows[1:]:
        sid=row['session_id']
        require(not any(p.exists() for p in [oldroot/'raw'/sid,oldroot/(sid+'.outcome.json'),
                    oldroot/'registry'/'a24-laptop-measurement-v1'/row['plan_id']/sid]),'pending extra4 has actual/unknown execution')
    ref=oldroot/'references'/(rows[0]['gate_block_id']+'.json')
    require(sha256(ref)==job['carry_reference_sha256'],'old fixed reference changed')
    require(load_json(ref)['Tref_c']==27.6 and load_json(ref)['outcome_inputs_used'] is False,
            'old reference was reselected')
    return rows[1:],ref


def prepare(oldfile,folder):
    require(not folder.exists(),'new continuation folder required')
    job=load_json(oldfile);oldroot=Path(job['run_root']);oldcontract=load_json(Path(job['revision_contract_file']))
    rows=validate_extra4_plan(load_json(Path(job['plan'])));raw=oldroot/'raw'/rows[0]['session_id']
    job.update(previous_extra4_root=str(oldroot),previous_extra4_stop_sha256=sha256(oldroot/'WINDOW_STOPPED.json'),
               previous_WAIT_events_sha256=sha256(raw/'events.jsonl'),previous_WAIT_closed_sha256=sha256(raw/'journal_closed.json'),
               carry_reference_sha256=sha256(oldroot/'references'/(rows[0]['gate_block_id']+'.json')))
    pending,ref=previous_evidence(job);folder.mkdir(parents=True);(folder/'prepared_manifests').mkdir()
    source=load_json(Path(job['source_manifest']));source.update(measurement_revision='Extra4 APP0 continuation: pre-APP stable MAIN-upper predicate; MAIN lifecycle unchanged')
    for name in ['tools/d1_a24_extra4_continue.py','tools/test_d1_a24_extra4_continue.py']:
        p=ROOT/name;source['files'].append({'path':name,'bytes':p.stat().st_size,'sha256':sha256(p)})
    control.atomic_json(folder/'SOURCE_SHA256.json',source)
    for row in rows:
        m=load_json(Path(job['prepared_manifests'])/(row['session_id']+'.json'))
        if row in pending:m.update(source_manifest_sha256=sha256(folder/'SOURCE_SHA256.json'),host_preparation_revision='MAIN_UPPER_PREAPP_ONLY')
        control.atomic_json(folder/'prepared_manifests'/(row['session_id']+'.json'),m)
    # Original full4 registration window/budget/analysis remain byte-identical.
    contract=copy.deepcopy(oldcontract);contract.update(source_sha256=sha256(folder/'SOURCE_SHA256.json'),
        continuation_sha256=sha256(Path(__file__)),continuation_tests_sha256=sha256(ROOT/'tools/test_d1_a24_extra4_continue.py'),
        visit_session_ids=[r['session_id'] for r in pending],previous_extra4_stop_sha256=job['previous_extra4_stop_sha256'],
        carry_reference_sha256=job['carry_reference_sha256'],MAIN_gate_changed=False,
        preAPP_only_change='Stable <= Tref+0.5 may prepare; full post-warmup60s MAIN gate unchanged; preAPP max600s')
    control.atomic_json(folder/'EXECUTION_CONTRACT.json',contract)
    job.update(source_manifest=str(folder/'SOURCE_SHA256.json'),prepared_manifests=str(folder/'prepared_manifests'),
               revision_contract_file=str(folder/'EXECUTION_CONTRACT.json'),run_root=str(oldroot.parent/folder.name),
               continuation_session_ids=[r['session_id'] for r in pending],continuation_PC_verification=str(folder/'PC_VERIFICATION.json'))
    control.atomic_json(folder/'job.json',job)
    with tempfile.TemporaryDirectory(prefix='PC_only_',dir=folder) as tmp:
        scratch=Path(tmp);(scratch/'references').mkdir();shutil.copyfile(ref,scratch/'references'/ref.name)
        cases=[]
        for row in pending:
            _,c,_,_=original.assemble(job,row,scratch);cases.append({'session_id':row['session_id'],'manifest_sha256':c['manifest_sha256'],'PASS_PC_ONLY':True})
    proof={'status':'PASS_PC_ONLY','authorization_contexts_PASS':3,'cases':cases,'device_commands':0,'APP_MAIN_claim_sessions':0,
           'already_completed_WAIT_not_replayed':True,'reference_sha256_unchanged':job['carry_reference_sha256'],
           'contract_sha256':sha256(folder/'EXECUTION_CONTRACT.json'),'continuation_sha256':sha256(Path(__file__))}
    control.atomic_json(folder/'PC_VERIFICATION.json',proof);inspect(job)


def inspect(job):
    pending,ref=previous_evidence(job);contract=load_json(Path(job['revision_contract_file']))
    require(contract['continuation_sha256']==sha256(Path(__file__))
            and contract['continuation_tests_sha256']==sha256(ROOT/'tools/test_d1_a24_extra4_continue.py'),'continuation source changed')
    require(contract['visit_session_ids']==job['continuation_session_ids']==[r['session_id'] for r in pending],
            'continuation not exact unused3')
    require(contract['MAIN_gate_changed'] is False,'MAIN gate may not change')
    pc=load_json(Path(job['continuation_PC_verification']))
    require(pc['status']=='PASS_PC_ONLY' and pc['authorization_contexts_PASS']==3
            and pc['contract_sha256']==sha256(Path(job['revision_contract_file'])),'exact continuation PC proof missing')
    original.lifecycle_identity();control.verify_source_entries(load_json(Path(job['source_manifest'])),ROOT,controller_file=control.CONTROLLER_SOURCE_FILE)
    require(not Path(job['run_root']).exists(),'continuation root exists; never replay')
    return pending,ref


def execute(job):
    pending,ref=inspect(job);root=Path(job['run_root']);globalroot=Path(job['extra4_global_root'])
    window=load_json(Path(job['window_file']));original.check_deadline(window,'NEW_SESSION')
    control.atomic_json(globalroot/'ACTIVE_OWNER.json',{'pid':os.getpid(),'run_root':str(root),'pending_extra4_only':3})
    root.mkdir();(root/'references').mkdir();shutil.copyfile(ref,root/'references'/ref.name)
    control.atomic_json(root/'OWNER_WINDOW.json',{'pid':os.getpid(),'window':window,'continuation_sha256':sha256(Path(__file__))})
    client=None;outcomes=[];reason='UNUSED_EXTRA4_3_FINISHED'
    try:
        target=load_json(Path(job['device_registration']))
        client=original.ExtraClient(job,target,window,globalroot,{'total_consumed':62,'cap':85});client.job_run_root=str(root);client.reconnect()
        for row in pending:
            client.check_window('NEW_SESSION');sid=row['session_id']
            require(not (globalroot/'reservations'/sid).exists(),'globally used extra4 ID; never replay')
            m,c,a,g=original.assemble(job,row,root)
            print(json.dumps({'status':'PREPARING_UNUSED_EXTRA4','arm':row['arm'],'session_id':sid}),flush=True)
            try:passive_before_APP(client,g,root/'pre_app_cooldown_v2'/(sid+'.jsonl'))
            except Exception as error:
                control.atomic_json(root/(sid+'.preapp_stop.json'),{'APP':0,'binding_created':True,'reason':str(error)})
                reason='PRE_APP_STOP_PRESERVED';break
            reservation=globalroot/'reservations'/sid;reservation.mkdir(parents=True,exist_ok=False)
            control.atomic_json(reservation/'RESERVED.json',{'session_id':sid,'unused_extra4_only':True});client.active_sid=sid
            logfile=root/'logcat'/(sid+'.txt');logfile.parent.mkdir(exist_ok=True)
            with logfile.open('xb') as stream:
                collector=subprocess.Popen(client.prefix+['logcat','-v','epoch','-T','1','tflite:V','D1A24PREP:V','*:S'],stdout=stream,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                try:
                    result=control.run_one(m,c,a,g,execute_authorized=True,client=client)
                    if result['status']=='COMPLETE_TRACE_RECOVERED':
                        require(original.finish_only_closed_owned_process(client,root/'raw'/sid,sid,package=c['package_name']),'empty process cleanup unproved')
                    outcome={**row,'status':result['status']}
                except Exception as error:outcome={**row,'status':'FAILED_PRESERVED','reason':str(error)}
                finally:collector.terminate();collector.wait(timeout=10)
            outcome['APP_launch_intent']=(reservation/'APP_LAUNCH_INTENT.json').exists()
            control.atomic_json(root/(sid+'.outcome.json'),outcome);control.atomic_json(reservation/'OUTCOME.json',outcome);outcomes.append(outcome)
            print(json.dumps(outcome),flush=True)
            if outcome['status']!='COMPLETE_TRACE_RECOVERED':reason='FAILED_ATTEMPT_PRESERVED';break
    except Exception as error:reason='CONTINUATION_STOP_PRESERVED: '+str(error)
    finally:
        total=len(list((globalroot/'reservations').glob('*/APP_LAUNCH_INTENT.json')))
        control.atomic_json(root/'WINDOW_STOPPED.json',{'outcomes':outcomes,'reason':reason,'actual_stop_UTC':dt.datetime.now(dt.timezone.utc).isoformat(),
            'new_APP_intents':total-1,'cumulative_extra4_APP_intents':total,'actual_ADB_calls':client.actual_calls if client else 0,
            'already_closed_WAIT_preserved':True,'MAIN_gate_changed':False,'no_retry_or_replacement':True})
        require(load_json(globalroot/'ACTIVE_OWNER.json')['pid']==os.getpid(),'foreign extra4 owner');(globalroot/'ACTIVE_OWNER.json').unlink()


def main():
    parser=argparse.ArgumentParser(description=__doc__);s=parser.add_subparsers(dest='action',required=True)
    p=s.add_parser('prepare');p.add_argument('oldjob',type=Path);p.add_argument('folder',type=Path)
    for name in ['inspect','execute']:
        p=s.add_parser(name);p.add_argument('job',type=Path)
        if name=='execute':p.add_argument('--execute-authorized',action='store_true')
    a=parser.parse_args()
    if a.action=='prepare':prepare(a.oldjob,a.folder.resolve());print(json.dumps({'status':'UNUSED_EXTRA4_3_PC_READY','APP':0}))
    elif a.action=='inspect':inspect(load_json(a.job));print(json.dumps({'status':'UNUSED_EXTRA4_3_PC_READY','device_commands':0}))
    else:require(a.execute_authorized,'explicit execution flag absent');execute(load_json(a.job))


if __name__=='__main__':main()
