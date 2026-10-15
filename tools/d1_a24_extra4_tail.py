"""Execute only the never-started ORDER of extra4; no replay of rejected PAIR."""
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
from d1_a24_extra4_continue import passive_before_APP
from d1_a24_failed_prestart_evidence import verify_failed_prestart
from d1_a24_laptop_validator import load_json, sha256
from d1_a24_revision02_suite import require

ROOT=original.ROOT;control=original.control


def previous(job):
    rows=validate_extra4_plan(load_json(Path(job['plan'])));globalroot=Path(job['extra4_global_root'])
    require(not (globalroot/'ACTIVE_OWNER.json').exists(),'extra4 worker active')
    roots=[Path(job['first_extra4_root']),Path(job['second_extra4_root'])]
    actual={}
    for root,digest in zip(roots,job['previous_stop_sha256s']):
        require(sha256(root/'WINDOW_STOPPED.json')==digest,'old extra4 stop changed')
        for item in load_json(root/'WINDOW_STOPPED.json')['outcomes']:
            require(item['session_id'] not in actual,'duplicate prior extra4 execution')
            actual[item['session_id']]=(root,item)
    require(set(actual)=={r['session_id'] for r in rows[:3]},'exact prior3 required')
    intents=list((globalroot/'reservations').glob('*/APP_LAUNCH_INTENT.json'))
    require({p.parent.name for p in intents}==set(actual),'unknown or missing actual APP intent')
    for row in rows[:3]:
        root,item=actual[row['session_id']]
        if row['arm']=='PAIR_G':
            raw=root/'read_only_recovery'/row['session_id']/'recovered_app'
            proof=verify_failed_prestart(root,load_json(Path(job['plan'])),row,raw,plan_sha256=sha256(Path(job['plan'])))
            closed=load_json(root/'read_only_recovery'/row['session_id']/'CLOSED_FAILURE_RECOVERY.json')
            require(all(closed[k]==v for k,v in proof.items()) and closed['own_device_process_absent'] is True,
                    'previous PAIR not safely closed')
        else:
            require(item['status']=='COMPLETE_TRACE_RECOVERED'
                    and load_json(root/'raw'/row['session_id']/'journal_closed.json')['status']=='SYNCED_AND_CLOSED',
                    'previous successful extra4 not closed')
    tail=rows[-1];sid=tail['session_id']
    require(not (globalroot/'reservations'/sid).exists(),'ORDER already reserved; never replay')
    for root in roots:
        require(not any(p.exists() for p in [root/'raw'/sid,root/(sid+'.outcome.json')]),'ORDER already executed')
    ref=roots[0]/'references'/(rows[0]['gate_block_id']+'.json')
    require(sha256(ref)==job['carry_reference_sha256'] and load_json(ref)['Tref_c']==27.6,'extra4 reference changed')
    return tail,ref


def prepare(oldfile,folder):
    require(not folder.exists(),'new tail metadata required')
    job=load_json(oldfile);first=Path(job['previous_extra4_root']);second=Path(job['run_root'])
    job.update(first_extra4_root=str(first),second_extra4_root=str(second),
        previous_stop_sha256s=[sha256(p/'WINDOW_STOPPED.json') for p in [first,second]])
    tail,ref=previous(job);folder.mkdir(parents=True);(folder/'prepared_manifests').mkdir()
    source=load_json(Path(job['source_manifest']))
    for name in ['tools/d1_a24_extra4_tail.py','tools/test_d1_a24_extra4_tail.py','tools/d1_a24_failed_prestart_evidence.py']:
        p=ROOT/name;require(name not in {x['path'] for x in source['files']},'duplicate source entry')
        source['files'].append({'path':name,'bytes':p.stat().st_size,'sha256':sha256(p)})
    control.atomic_json(folder/'SOURCE_SHA256.json',source)
    for row in load_json(Path(job['plan']))['sessions']:
        m=load_json(Path(job['prepared_manifests'])/(row['session_id']+'.json'))
        if row['session_id']==tail['session_id']:m['source_manifest_sha256']=sha256(folder/'SOURCE_SHA256.json')
        control.atomic_json(folder/'prepared_manifests'/(row['session_id']+'.json'),m)
    contract=copy.deepcopy(load_json(Path(job['revision_contract_file'])))
    contract.update(source_sha256=sha256(folder/'SOURCE_SHA256.json'),tail_runner_sha256=sha256(Path(__file__)),
        tail_tests_sha256=sha256(ROOT/'tools/test_d1_a24_extra4_tail.py'),visit_session_ids=[tail['session_id']],
        previous_stop_sha256s=job['previous_stop_sha256s'],MAIN_gate_changed=False)
    control.atomic_json(folder/'EXECUTION_CONTRACT.json',contract)
    job.update(source_manifest=str(folder/'SOURCE_SHA256.json'),prepared_manifests=str(folder/'prepared_manifests'),
        revision_contract_file=str(folder/'EXECUTION_CONTRACT.json'),run_root=str(second.parent/folder.name),
        tail_PC_verification=str(folder/'PC_VERIFICATION.json'))
    control.atomic_json(folder/'job.json',job)
    with tempfile.TemporaryDirectory(prefix='PC_ONLY_',dir=folder) as tmp:
        root=Path(tmp);(root/'references').mkdir();shutil.copyfile(ref,root/'references'/ref.name)
        _,c,_,_=original.assemble(job,tail,root)
    control.atomic_json(folder/'PC_VERIFICATION.json',{'status':'PASS_PC_ONLY','authorization_contexts_PASS':1,
        'session_id':tail['session_id'],'manifest_sha256':c['manifest_sha256'],'device_commands':0,'APP_MAIN_claim_sessions':0,
        'contract_sha256':sha256(folder/'EXECUTION_CONTRACT.json'),'mock_root_removed':True})
    inspect(job)


def inspect(job):
    tail,ref=previous(job);contract=load_json(Path(job['revision_contract_file']))
    require(contract['tail_runner_sha256']==sha256(Path(__file__))
            and contract['tail_tests_sha256']==sha256(ROOT/'tools/test_d1_a24_extra4_tail.py')
            and contract['visit_session_ids']==[tail['session_id']] and contract['MAIN_gate_changed'] is False,
            'tail source/scope changed')
    pc=load_json(Path(job['tail_PC_verification']))
    require(pc['status']=='PASS_PC_ONLY' and pc['authorization_contexts_PASS']==1
            and pc['contract_sha256']==sha256(Path(job['revision_contract_file'])),'tail exact PC proof absent')
    original.lifecycle_identity();control.verify_source_entries(load_json(Path(job['source_manifest'])),ROOT,controller_file=control.CONTROLLER_SOURCE_FILE)
    require(not Path(job['run_root']).exists(),'tail already attempted; no replay')
    return tail,ref


def execute(job):
    tail,ref=inspect(job);root=Path(job['run_root']);globalroot=Path(job['extra4_global_root'])
    require(not any((p/'ACTIVE_OWNER.json').exists() for p in root.parent.glob('A24*') if p.is_dir()),'previous worker active')
    window=load_json(Path(job['window_file']));original.check_deadline(window,'NEW_SESSION')
    control.atomic_json(globalroot/'ACTIVE_OWNER.json',{'pid':os.getpid(),'unused_ORDER_only':True})
    root.mkdir();(root/'references').mkdir();shutil.copyfile(ref,root/'references'/ref.name)
    control.atomic_json(root/'OWNER_WINDOW.json',{'pid':os.getpid(),'window':window,'tail_runner_sha256':sha256(Path(__file__))})
    client=None;outcomes=[];reason='EXTRA4_ORDER_FINISHED'
    try:
        client=original.ExtraClient(job,load_json(Path(job['device_registration'])),window,globalroot,{'total_consumed':81,'cap':85})
        client.job_run_root=str(root);client.reconnect();sid=tail['session_id']
        m,c,a,g=original.assemble(job,tail,root)
        print(json.dumps({'status':'PREPARING_NEVER_STARTED_EXTRA4_ORDER','session_id':sid}),flush=True)
        passive_before_APP(client,g,root/'pre_app_cooldown_v2'/(sid+'.jsonl'))
        reservation=globalroot/'reservations'/sid;reservation.mkdir(parents=True,exist_ok=False)
        control.atomic_json(reservation/'RESERVED.json',{'session_id':sid,'unused_ORDER_only':True});client.active_sid=sid
        log=root/'logcat'/(sid+'.txt');log.parent.mkdir()
        with log.open('xb') as stream:
            collector=subprocess.Popen(client.prefix+['logcat','-v','epoch','-T','1','tflite:V','D1A24PREP:V','*:S'],stdout=stream,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            try:
                result=control.run_one(m,c,a,g,execute_authorized=True,client=client)
                if result['status']=='COMPLETE_TRACE_RECOVERED':
                    require(original.finish_only_closed_owned_process(client,root/'raw'/sid,sid,package=c['package_name']),'closed process cleanup unproved')
                outcome={**tail,'status':result['status'],'APP_launch_intent':(reservation/'APP_LAUNCH_INTENT.json').exists()}
                control.atomic_json(root/(sid+'.outcome.json'),outcome);control.atomic_json(reservation/'OUTCOME.json',outcome);outcomes.append(outcome)
            finally:collector.terminate();collector.wait(timeout=10)
    except Exception as error:reason='ORDER_STOP_PRESERVED: '+str(error)
    finally:
        total=len(list((globalroot/'reservations').glob('*/APP_LAUNCH_INTENT.json')))
        control.atomic_json(root/'WINDOW_STOPPED.json',{'outcomes':outcomes,'reason':reason,'actual_stop_UTC':dt.datetime.now(dt.timezone.utc).isoformat(),
            'new_APP_intents':total-3,'cumulative_extra4_APP_intents':total,'actual_ADB_calls':client.actual_calls if client else 0,
            'MAIN_gate_changed':False,'old_FAILED_PAIR_replayed':False})
        require(load_json(globalroot/'ACTIVE_OWNER.json')['pid']==os.getpid(),'foreign owner');(globalroot/'ACTIVE_OWNER.json').unlink()


def main():
    p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='action',required=True)
    a=s.add_parser('prepare');a.add_argument('oldjob',type=Path);a.add_argument('folder',type=Path)
    for name in ['inspect','execute']:
        a=s.add_parser(name);a.add_argument('job',type=Path)
        if name=='execute':a.add_argument('--execute-authorized',action='store_true')
    a=p.parse_args()
    if a.action=='prepare':prepare(a.oldjob,a.folder.resolve());print(json.dumps({'status':'TAIL_ORDER_PC_READY','APP':0}))
    elif a.action=='inspect':inspect(load_json(a.job));print(json.dumps({'status':'TAIL_ORDER_PC_READY','device_commands':0}))
    else:require(a.execute_authorized,'execution flag absent');execute(load_json(a.job))


if __name__=='__main__':main()
