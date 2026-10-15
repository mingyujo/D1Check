"""Continue only the unused eight original supplement IDs after proved closure.

No repeat of failed Perfetto ON, no change to original plan/MAIN/APK/controller.
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

import d1_a24_supplement_runner as original
from d1_a24_supplement_contract import validate_plan
from d1_a24_laptop_validator import load_json,sha256
from d1_a24_revision02_suite import require
from d1_a24_failed_trace_prestart import verify_closed_trace_failure

ROOT=original.ROOT;control=original.control
FILES=['tools/d1_a24_supplement_continue.py','tools/test_d1_a24_supplement_continue.py',
       'tools/d1_a24_failed_trace_prestart.py','tools/test_d1_a24_failed_trace_prestart.py']


def pending_scope(plan,actual):
    rows=validate_plan(plan)
    require(set(actual)=={r['session_id'] for r in rows[:4]},'exact stopped first4 required')
    require(all(actual[r['session_id']]['status']=='COMPLETE_TRACE_RECOVERED' for r in rows[:3])
        and actual[rows[3]['session_id']]['status']=='FAILED_PRESERVED','prior prefix differs')
    return rows[4:]


def previous(job):
    root=Path(job['prior_supplement_root']);globalroot=Path(job['supplement_global_root']);plan=load_json(Path(job['plan']))
    require(not (globalroot/'ACTIVE_OWNER.json').exists(),'supplement active')
    require(sha256(root/'WINDOW_STOPPED.json')==job['prior_stop_sha256'],'prior stop changed')
    stop=load_json(root/'WINDOW_STOPPED.json');actual={r['session_id']:r for r in stop['outcomes']};rows=pending_scope(plan,actual)
    require({p.parent.name for p in (globalroot/'reservations').glob('*/APP_LAUNCH_INTENT.json')}==set(actual),
        'exact stopped first4 APP intents required')
    for row in plan['sessions'][:3]:
        raw=root/'raw'/row['session_id']
        require(load_json(raw/'journal_closed.json')['status']=='SYNCED_AND_CLOSED'
            and load_json(raw/'cleanup.json')['actual_return_confirmed'] is True,'normal prefix not closed')
    failed=plan['sessions'][3];folder=root/'read_only_recovery'/failed['session_id']
    proof=verify_closed_trace_failure(root,plan,failed,folder/'recovered_app',plan_sha256=sha256(Path(job['plan'])))
    receipt=load_json(folder/'CLOSED_FAILURE_RECOVERY.json')
    require(all(receipt[k]==v for k,v in proof.items()) and receipt['own_device_process_absent'] is True,'failed trace not safely closed')
    for row in rows:
        sid=row['session_id'];require(not (globalroot/'reservations'/sid).exists()
            and not (root/(sid+'.outcome.json')).exists(),'pending ID was already attempted')
    return rows


def prepare(oldfile,folder):
    require(not folder.exists(),'fresh continuation metadata required');job=load_json(oldfile)
    root=Path(job['run_root']);job.update(prior_supplement_root=str(root),prior_stop_sha256=sha256(root/'WINDOW_STOPPED.json'))
    rows=previous(job);folder.mkdir(parents=True);(folder/'prepared_manifests').mkdir()
    source=load_json(Path(job['source_manifest']))
    for name in FILES:
        p=ROOT/name;require(name not in {x['path'] for x in source['files']},'duplicate source')
        source['files'].append({'path':name,'bytes':p.stat().st_size,'sha256':sha256(p)})
    control.atomic_json(folder/'SOURCE_SHA256.json',source);ids={r['session_id'] for r in rows}
    for row in load_json(Path(job['plan']))['sessions']:
        m=load_json(Path(job['prepared_manifests'])/(row['session_id']+'.json'))
        if row['session_id'] in ids:m['source_manifest_sha256']=sha256(folder/'SOURCE_SHA256.json')
        control.atomic_json(folder/'prepared_manifests'/(row['session_id']+'.json'),m)
    contract=copy.deepcopy(load_json(Path(job['revision_contract_file'])))
    contract.update(source_sha256=sha256(folder/'SOURCE_SHA256.json'),continuation_runner_sha256=sha256(Path(__file__)),
        continuation_session_ids=[r['session_id'] for r in rows],prior_stop_sha256=job['prior_stop_sha256'],
        original_first4_outcomes_preserved=True,MAIN_and_runtime_changed=False)
    control.atomic_json(folder/'EXECUTION_CONTRACT.json',contract)
    job.update(source_manifest=str(folder/'SOURCE_SHA256.json'),prepared_manifests=str(folder/'prepared_manifests'),
        revision_contract_file=str(folder/'EXECUTION_CONTRACT.json'),run_root=str(root.parent/folder.name),
        supplement_continuation_PC_verification=str(folder/'PC_VERIFICATION.json'))
    control.atomic_json(folder/'job.json',job)
    with tempfile.TemporaryDirectory(prefix='PC_ONLY_',dir=folder) as tmp:
        scratch=Path(tmp);cases=[]
        for row in rows:
            _,c,_,_=original.assemble(job,row,scratch);cases.append({'session_id':row['session_id'],'manifest_sha256':c['manifest_sha256']})
    control.atomic_json(folder/'PC_VERIFICATION.json',{'status':'PASS_PC_ONLY','authorization_contexts_PASS':8,
        'cases':cases,'device_commands':0,'APP_MAIN_claim_sessions':0,'contract_sha256':sha256(folder/'EXECUTION_CONTRACT.json')})
    inspect(job)


def inspect(job):
    rows=previous(job);contract=load_json(Path(job['revision_contract_file']))
    require(contract['continuation_runner_sha256']==sha256(Path(__file__))
        and contract['continuation_session_ids']==[r['session_id'] for r in rows]
        and contract['MAIN_and_runtime_changed'] is False,'continuation changed')
    pc=load_json(Path(job['supplement_continuation_PC_verification']))
    require(pc['status']=='PASS_PC_ONLY' and pc['authorization_contexts_PASS']==8
        and pc['contract_sha256']==sha256(Path(job['revision_contract_file'])),'exact8 PC proof absent')
    original.lifecycle_identity();control.verify_source_entries(load_json(Path(job['source_manifest'])),ROOT,controller_file=control.CONTROLLER_SOURCE_FILE)
    require(not Path(job['run_root']).exists(),'continuation already attempted; never replay')
    return rows


def execute(job):
    rows=inspect(job);window=load_json(Path(job['window_file']));original.check_deadline(window,'NEW_SESSION')
    root=Path(job['run_root']);globalroot=Path(job['supplement_global_root']);original.require_no_prior_owners(root.parent)
    control.atomic_json(globalroot/'ACTIVE_OWNER.json',{'pid':os.getpid(),'unused_supplement8_only':True})
    root.mkdir();control.atomic_json(root/'OWNER_WINDOW.json',{'pid':os.getpid(),'window':window,'continuation_sha256':sha256(Path(__file__))})
    client=None;outcomes=[];reason='UNUSED_SUPPLEMENT8_FINISHED'
    try:
        client=original.FollowupClient(job,load_json(Path(job['device_registration'])),window,globalroot,{'total_consumed':85,'cap':97})
        client.job_run_root=str(root);client.reconnect()
        for row in rows:
            sid=row['session_id'];client.check_window('NEW_SESSION');m,c,a,g=original.assemble(job,row,root)
            require(row['reference_role']=='SELECT_FIRST' and row['perfetto']=='OFF','unused8 scope changed')
            reservation=globalroot/'reservations'/sid;reservation.mkdir(parents=True,exist_ok=False)
            control.atomic_json(reservation/'RESERVED.json',{'session_id':sid,'unused_supplement8_only':True});client.active_sid=sid
            log=root/'logcat'/(sid+'.txt');log.parent.mkdir(exist_ok=True)
            print(json.dumps({'status':'PREPARING_UNUSED_SUPPLEMENT','case':row['case_name'],'session_id':sid}),flush=True)
            with log.open('xb') as stream:
                collector=subprocess.Popen(client.prefix+['logcat','-v','epoch','-T','1','tflite:V','D1A24PREP:V','*:S'],
                    stdout=stream,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                try:
                    result=control.run_one(m,c,a,g,execute_authorized=True,client=client)
                    if result['status']=='COMPLETE_TRACE_RECOVERED':
                        require(original.finish_only_closed_owned_process(client,root/'raw'/sid,sid,package=c['package_name']),'closed cleanup unproved')
                    outcome={**row,'status':result['status']}
                except Exception as e:outcome={**row,'status':'FAILED_PRESERVED','reason':str(e)}
                finally:collector.terminate();collector.wait(timeout=10)
            outcome['APP_launch_intent']=(reservation/'APP_LAUNCH_INTENT.json').exists()
            control.atomic_json(root/(sid+'.outcome.json'),outcome);control.atomic_json(reservation/'OUTCOME.json',outcome);outcomes.append(outcome)
            print(json.dumps(outcome),flush=True)
            if outcome['status']!='COMPLETE_TRACE_RECOVERED':reason='UNUSED_SUPPLEMENT_FAILURE_PRESERVED';break
    except Exception as e:reason='UNUSED_SUPPLEMENT_STOP_PRESERVED: '+str(e)
    finally:
        control.atomic_json(root/'WINDOW_STOPPED.json',{'outcomes':outcomes,'reason':reason,'actual_stop_UTC':dt.datetime.now(dt.timezone.utc).isoformat(),
            'new_APP_intents':len(list((globalroot/'reservations').glob('*/APP_LAUNCH_INTENT.json')))-4,
            'actual_ADB_calls':client.actual_calls if client else 0,'prior_APP4_preserved':True,'failed_trace_replayed':False})
        require(load_json(globalroot/'ACTIVE_OWNER.json')['pid']==os.getpid(),'foreign owner');(globalroot/'ACTIVE_OWNER.json').unlink()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='action',required=True)
    a=s.add_parser('prepare');a.add_argument('oldjob',type=Path);a.add_argument('folder',type=Path)
    for name in ['inspect','execute']:
        a=s.add_parser(name);a.add_argument('job',type=Path)
        if name=='execute':a.add_argument('--execute-authorized',action='store_true')
    a=p.parse_args()
    if a.action=='prepare':prepare(a.oldjob,a.folder.resolve());print(json.dumps({'status':'UNUSED8_PC_READY','device_commands':0}))
    elif a.action=='inspect':inspect(load_json(a.job));print(json.dumps({'status':'UNUSED8_PC_READY','device_commands':0}))
    else:require(a.execute_authorized,'explicit execution flag absent');execute(load_json(a.job))
