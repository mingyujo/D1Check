"""Resume frozen CONFIRM40 after a closed, separately recorded current diagnostic.

The core179 and first-visit coordinator are imported without editing their bytes.
Default mode is PC inspection. A global exclusive reservation is recorded before
run_one; a separate APP intent is written before sending am start. Uncertain APP
delivery consumes the budget conservatively and is never automatically retried.
"""
import argparse
import datetime
import json
import os
from pathlib import Path
import subprocess

import d1_a24_confirm_registered_window as first
from d1_a24_laptop_validator import load_json, sha256, PROTOCOL, ValidationError
from d1_a24_revision02_suite import require
from d1_a24_revision02_suite_control import atomic_json, read_battery, run_one
from d1_a24_revision02_window import BoundedClient, check_deadline
from d1_a24_suite_dev_continue import passive_v2
from d1_a24_measurement_batch import finish_only_closed_owned_process


def select_remaining(plan, window, ledger):
    rows = first.scoped_rows(plan, window)
    records = ledger['records']
    require(len(records)==40 and len({r['session_id'] for r in records})==40,'global ledger identity count')
    require([r['session_id'] for r in records]==[r['session_id'] for r in plan['sessions']],'ledger plan order differs')
    consumed = [r for r in records if r['APP_launches'] > 0]
    require(ledger['cap']==81 and ledger['consumed_before_new_confirm']==41,'budget lineage differs')
    require(ledger['total_consumed']==41+len(consumed) and ledger['remaining']==81-ledger['total_consumed'],'global count inconsistent')
    untouched=[r['session_id'] for r in records if r['APP_launches']==0 and r['outcome']=='NOT_ATTEMPTED' and r['START'] is False]
    require(window['registered_session_ids']==untouched[:len(rows)],'visit is not first untouched prefix')
    require(len(rows)<=ledger['remaining'],'visit exceeds remaining budget')
    return rows


def check_history(job, binding, ledger):
    for item in binding['previous_visits']:
        root=Path(item['root'])
        require(sha256(root/'WINDOW_STOPPED.json')==item['stop_sha256'],'previous visit not closed/changed')
    for record in ledger['records']:
        sid=record['session_id']
        hits=[]
        for item in binding['previous_visits']:
            root=Path(item['root'])
            paths=[root/(sid+'.outcome.json'),root/'raw'/sid,root/'bindings'/sid,
                   root/'registry'/PROTOCOL/load_json(Path(job['plan']))['plan_id']/sid]
            if any(p.exists() for p in paths):hits.append(root)
        if record['APP_launches']:
            require(len(hits)==1,'consumed session evidence missing/duplicated')
            raw=hits[0]/'raw'/sid
            require(sha256(raw/'events.jsonl')==record['events_sha256'] and
                    sha256(raw/'journal_closed.json')==record['closed_sha256'],'prior raw/closure changed')
        else:
            evidence=binding.get('unstarted_preAPP_bindings',{}).get(sid)
            if evidence is None:
                require(not hits,'untouched global ID has earlier local artifacts')
            else:
                require(len(hits)==1 and str(hits[0])==evidence['visit_root'],'preAPP provenance differs')
                root=hits[0]
                stop=load_json(root/'WINDOW_STOPPED.json')
                require(stop.get('external_host_stop') is True and stop.get('active_APPs_at_stop')==0 and
                        stop['reason']=='USER_PAUSE_AFTER_CLOSED_BEFORE_CURRENT_RESPONSE_DIAGNOSTIC','unproved preAPP stop')
                require(not (root/(sid+'.outcome.json')).exists() and not (root/'raw'/sid).exists() and
                        not (root/'registry'/PROTOCOL/load_json(Path(job['plan']))['plan_id']/sid).exists(),'preAPP ID already has execution evidence')
                for old_global in binding['previous_global_reservation_roots']:
                    require(not (Path(old_global)/'reservations'/sid).exists(),'preAPP ID has a global reservation/APP intent')
                actual={str(p.relative_to(root/'bindings'/sid)).replace('\\','/'):sha256(p)
                        for p in (root/'bindings'/sid).rglob('*') if p.is_file()}
                require(actual==evidence['binding_file_sha256'],'preserved preAPP binding changed')


def inspect(job, require_pc=True):
    contract=load_json(Path(job['revision_contract_file']))
    binding=load_json(Path(job['global_binding']))
    require(contract['followup_coordinator_sha256']==sha256(Path(__file__)),'followup code differs')
    require(contract['coordinator_sha256']==sha256(Path(first.__file__)),'first coordinator differs')
    require(contract['global_binding_sha256']==sha256(Path(job['global_binding'])),'global binding differs')
    require(binding['ledger_sha256']==sha256(Path(binding['ledger_path'])),'global ledger snapshot differs')
    require(binding['window_sha256']==sha256(Path(job['window_file'])),'new time window differs')
    ledger=load_json(Path(binding['ledger_path']))
    require(ledger['plan_sha256']==sha256(Path(job['plan']))==binding['plan_sha256'],'plan changed')
    window=load_json(Path(job['window_file']));plan=load_json(Path(job['plan']))
    rows=select_remaining(plan,window,ledger)
    require(contract['visit_session_ids']==window['registered_session_ids'],'visit scope differs')
    diagnostic=Path(binding['diagnostic_recovery'])
    require(sha256(diagnostic)==binding['diagnostic_recovery_sha256'],'diagnostic recovery differs')
    recovered=load_json(diagnostic)
    require(recovered['status']=='RECOVERED_CLOSED_DIAGNOSTIC' and recovered['summary_status']=='COMPLETE_DIAGNOSTIC' and
            recovered['completed_pulses']==6 and recovered['confirmation_APK_unchanged'] is True,'diagnostic not completed and drained')
    first.verify_source_entries(load_json(Path(job['source_manifest'])),first.ROOT,controller_file=first.CONTROLLER_SOURCE_FILE)
    require(contract['core_source_sha256']==sha256(Path(job['source_manifest'])),'frozen core differs')
    check_history(job,binding,ledger)
    for name,expected in binding['job_inputs_sha256'].items():
        require(sha256(Path(job[name]))==expected,'bound job input differs: '+name)
    if require_pc:
        proof=load_json(Path(job['followup_PC_verification']))
        require(proof['status']=='PASS_PC_ONLY' and proof['followup_sha256']==sha256(Path(__file__)) and
                proof['contract_sha256']==sha256(Path(job['revision_contract_file'])) and
                proof['authorization_contexts_PASS']==len(rows),'matching followup PC evidence absent')
    return rows,window,ledger,binding


class FollowupClient(BoundedClient):
    def __init__(self,job,target,window,global_root,ledger):
        super().__init__(job,target,window)
        self.global_root=global_root;self.ledger=ledger;self.active_sid=None

    def check_window(self,phase):
        if phase in {'NEW_SESSION','APP_CREATE'}:
            require(not (Path(self.job_run_root)/'STOP_AFTER_CURRENT.json').exists(),'USER_STOP_AFTER_CURRENT')
        return super().check_window(phase)

    def command(self,*args,**kwargs):
        if args[:3]==('shell','am','start'):
            sid=args[args.index('session_id')+1]
            require(sid==self.active_sid,'APP does not match reserved session')
            prior_intents=list((self.global_root/'reservations').glob('*/APP_LAUNCH_INTENT.json'))
            require(self.ledger['total_consumed']+len(prior_intents)<self.ledger['cap'],'global APP cap reached')
            self.check_window('APP_CREATE')
            atomic_json(self.global_root/'reservations'/sid/'APP_LAUNCH_INTENT.json',
                        {'session_id':sid,'UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),
                         'budget_consumed_if_delivery_uncertain':True,'automatic_replay':False})
        return super().command(*args,**kwargs)


def execute(job):
    rows,window,ledger,binding=inspect(job);check_deadline(window,'NEW_SESSION')
    root=Path(job['run_root']);global_root=Path(binding['global_reservation_root'])
    require(not root.exists(),'write-once visit root already exists')
    global_root.mkdir(parents=True,exist_ok=True)
    anchor=global_root/'BASE_LEDGER.json'
    if not anchor.exists():atomic_json(anchor,ledger)
    require(load_json(anchor)==ledger,'global reservation lineage differs')
    lock=global_root/'ACTIVE_OWNER.json'
    atomic_json(lock,{'pid':os.getpid(),'run_root':str(root),'window_sha256':sha256(Path(job['window_file']))})
    root.mkdir()
    atomic_json(root/'OWNER_WINDOW.json',{'pid':os.getpid(),'window':window,'followup_sha256':sha256(Path(__file__))})
    outcomes=[];client=None;stop_reason='REGISTERED_SCOPE_FINISHED'
    try:
        # References for a split comparison group are copied byte-for-byte only.
        for carry in binding.get('carry_references',[]):
            source=Path(carry['path']);require(sha256(source)==carry['sha256'],'reference changed')
            destination=root/'references'/source.name;destination.parent.mkdir(exist_ok=True)
            with destination.open('xb') as stream:stream.write(source.read_bytes())
        target=load_json(Path(job['device_registration']))
        client=FollowupClient(job,target,window,global_root,ledger)
        client.job_run_root=str(root)
        # Preserve the frozen registration/manifest transport identity. The
        # existing recovery path resolves its current endpoint by physical
        # serial + fingerprint, exactly as after an in-session disconnect.
        client.reconnect()
        require(not client.command('shell','pidof','com.example.d1check.currentdiagnostic',accepted_codes=(0,1),reject_stderr=True).strip(),'diagnostic still active')
        require(client.command('shell','getprop','ro.serialno').decode().strip()==target['hardware_serial'],'target differs')
        require(client.command('shell','getprop','ro.build.fingerprint').decode().strip()==target['build_fingerprint'],'fingerprint differs')
        battery=read_battery(client);require(battery['SOC_percent']>=10 and battery['plugged'] is False,'SOC/charging differs')
        require(client.command('shell','settings','get','system','screen_brightness').decode().strip()=='81','brightness differs')
        require(client.command('shell','settings','get','system','screen_brightness_mode').decode().strip()=='0','screen mode differs')
        require('mWakefulness=Awake' in client.command('shell','dumpsys','power').decode(),'screen asleep')
        atomic_json(root/'DEVICE_WINDOW_PREFLIGHT.json',{'identity_match':True,'battery':battery,'settings_changed':False})
        for row in rows:
            if (root/'STOP_AFTER_CURRENT.json').exists():
                stop_reason='USER_STOP_AFTER_CURRENT';break
            try:check_deadline(window,'NEW_SESSION')
            except ValidationError:
                stop_reason='TIME_REMAINING_NO_NEW_APP';break
            sid=row['session_id'];reservation=global_root/'reservations'/sid
            require(not reservation.exists(),'globally reserved ID; no automatic replay')
            m,c,a,g=first.assemble(job,row,root)
            print(json.dumps({'status':'PREPARING_FOLLOWUP_CONFIRM','recipe':row['recipe'],'arm':row['arm'],'session_id':sid}),flush=True)
            # A cooldown timeout has consumed no APP; it remains explicit.
            try:passive_v2(client,g,root/'pre_app_cooldown_v2'/(sid+'.jsonl'))
            except ValidationError as error:
                atomic_json(root/(sid+'.preapp_stop.json'),{'APP':0,'reason':str(error),'binding_created':True})
                stop_reason='PRE_APP_COOLDOWN_STOP';break
            check_deadline(window,'NEW_SESSION')
            reservation.mkdir(parents=True,exist_ok=False)
            atomic_json(reservation/'RESERVED.json',{'session_id':sid,'run_root':str(root),'window_sha256':sha256(Path(job['window_file']))})
            client.active_sid=sid
            logpath=root/'logcat'/(sid+'.txt');logpath.parent.mkdir(exist_ok=True)
            with logpath.open('xb') as log:
                collector=subprocess.Popen(client.prefix+['logcat','-v','epoch','-T','1','tflite:V','D1A24PREP:V','*:S'],stdout=log,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                try:
                    result=run_one(m,c,a,g,execute_authorized=True,client=client)
                    if result['status']=='COMPLETE_TRACE_RECOVERED':
                        require(finish_only_closed_owned_process(client,root/'raw'/sid,sid,package=c['package_name']),'closed process cleanup unproved')
                    outcome={**row,'status':result['status']}
                except Exception as error:outcome={**row,'status':'FAILED_PRESERVED','reason':str(error)}
                finally:collector.terminate();collector.wait(timeout=10)
            outcome['APP_launch_intent']=(reservation/'APP_LAUNCH_INTENT.json').exists()
            atomic_json(root/(sid+'.outcome.json'),outcome)
            atomic_json(reservation/'OUTCOME.json',outcome)
            outcomes.append(outcome);print(json.dumps(outcome),flush=True)
            if outcome['status']!='COMPLETE_TRACE_RECOVERED':
                stop_reason='FAILED_ATTEMPT_PRESERVED';break
    except Exception as error:
        stop_reason='ERROR_PRESERVED: '+str(error)
        print(json.dumps({'status':'FOLLOWUP_STOP','reason':str(error)}),flush=True)
    finally:
        atomic_json(root/'WINDOW_STOPPED.json',{'outcomes':outcomes,'reason':stop_reason,
            'actual_stop_UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'registered_this_visit':len(rows),'prior_consumed':ledger['total_consumed'],
            'new_APP_intents':len(list((global_root/'reservations').glob('*/APP_LAUNCH_INTENT.json'))),
            'actual_ADB_calls':client.actual_calls if client else 0,'no_retry_or_replacement':True})
        require(load_json(lock)['pid']==os.getpid(),'foreign owner lock; preserve')
        lock.unlink()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('job',type=Path);parser.add_argument('--execute-authorized',action='store_true')
    args=parser.parse_args();job=load_json(args.job)
    if args.execute_authorized:execute(job)
    else:
        rows,*_=inspect(job)
        print(json.dumps({'status':'PC_INSPECT_ONLY','remaining_scope':len(rows),'device_commands':0}))
