"""PC preparation and separately time-bound visits of untouched CONFIRM slots.

The 179-file scientific core, APK and C3 executor are imported unchanged.
Preparation writes no device/measurement registry. Only bind-window creates a
future window; execute additionally needs --execute-authorized. Device checking
is a separate read-only operation and never admits a measurement.
"""
import argparse
import copy
import datetime as dt
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

import d1_a24_confirm_after_diagnostic as executor
from d1_a24_confirm_registered_window import assemble, verify_source_entries, CONTROLLER_SOURCE_FILE, ROOT
from d1_a24_laptop_validator import load_json, sha256, PROTOCOL
from d1_a24_revision02_suite import require
from d1_a24_revision02_suite_control import atomic_json, read_battery
from d1_a24_revision02_window import check_deadline
from d1_a24_measurement_connection import ReconnectingAdbClient

INPUT_KEYS=['analysis_contract','apk','apk_identity','budget_file','confirm_freeze','device_registration',
            'gate','host_dependency_lock','new_protocol_functional_evidence','plan','pre_measurement_predictions',
            'prior_stage_ledger','quality_references','source_manifest']


def exact_scope(plan,ledger):
    records=ledger['records'];rows=plan['sessions']
    require(len(rows)==len(records)==40 and [r['session_id'] for r in rows]==[r['session_id'] for r in records],'ledger plan order differs')
    require(ledger['cap']==81 and ledger['consumed_before_new_confirm']==41,'budget lineage changed')
    used=[r for r in records if r['APP_launches']]
    require(all(r['APP_launches']==1 for r in used),'replayed APP in ledger')
    require(ledger['total_consumed']==41+len(used) and ledger['remaining']==40-len(used),'inconsistent remaining budget')
    pending=[r['session_id'] for r in records if r['APP_launches']==0 and r['START'] is False and r['outcome']=='NOT_ATTEMPTED']
    require(len(pending)==ledger['remaining'],'ambiguous unexecuted slot')
    require([r['APP_launches'] for r in records]==[1]*len(used)+[0]*len(pending),'non-prefix execution history')
    return [r for r in rows if r['session_id'] in pending]


def history_inventory(spec,plan,ledger):
    """Validate each visit separately so old preAPP artifacts cannot hide replay."""
    inventory={};app_counts={r['session_id']:0 for r in plan['sessions']};raw_hits={k:[] for k in app_counts}
    def add(p,key):
        if p.is_file():inventory[key]=sha256(p)
    for visit in spec['previous_visits']:
        root=Path(visit['root']);tag=root.name
        stop=root/'WINDOW_STOPPED.json'
        require(stop.is_file() and sha256(stop)==visit['stop_sha256'],'previous visit not closed/changed')
        add(stop,tag+'/WINDOW_STOPPED.json');visit_apps={k:0 for k in app_counts}
        for name in ['adb_commands.jsonl','measurement_adb_commands.jsonl']:
            log=root/name
            if not log.exists():continue
            add(log,tag+'/'+name)
            for line in log.read_bytes().splitlines():
                x=json.loads(line);a=x.get('argv',[])
                if 'am' in a and 'start' in a and 'session_id' in a:
                    sid=a[a.index('session_id')+1];require(sid in app_counts,'foreign APP in visit')
                    app_counts[sid]+=1;visit_apps[sid]+=1
        for record in ledger['records']:
            sid=record['session_id'];raw=root/'raw'/sid;binding=root/'bindings'/sid
            registry=root/'registry'/PROTOCOL/plan['plan_id']/sid;outcome=root/(sid+'.outcome.json')
            for p in [outcome,*[binding/n for n in ['session_manifest.json','authorization.json','config.json','gate.json']]]:
                add(p,tag+'/'+p.relative_to(root).as_posix())
            for p in [root/(sid+'.preapp_stop.json'),root/'STOP_AFTER_CURRENT.json',
                      root/'pre_app_cooldown_v2'/(sid+'.jsonl'),root/'pre_app_cooldown_v2'/(sid+'.ready.json')]:
                add(p,tag+'/'+p.relative_to(root).as_posix())
            for folder in [registry,raw]:
                if folder.exists():
                    for p in folder.iterdir():
                        if p.is_file() and (folder==registry or p.name in {'events.jsonl','journal_closed.json','session_manifest.json','requests.json','summary.json','cleanup.json'}):
                            add(p,tag+'/'+p.relative_to(root).as_posix())
            artifacts=any(p.exists() for p in [raw,binding,registry,outcome])
            if record['APP_launches']==0:
                require(visit_apps[sid]==0,'untouched slot has a prior APP command')
                if artifacts:
                    # A closed passive wait can be rebound to an EARLIER user
                    # deadline. Never excuse uploaded/executed/uncertain runs.
                    paused=load_json(stop);receipt=root/(sid+'.preapp_stop.json')
                    require(binding.is_dir() and not any(p.exists() for p in [raw,registry,outcome])
                            and receipt.is_file(),'untouched slot has execution/unknown artifacts')
                    proof=load_json(receipt)
                    require(paused.get('reason')=='PRE_APP_COOLDOWN_STOP' and paused.get('new_APP_intents')==0
                            and paused.get('outcomes')==[] and proof.get('APP')==0
                            and proof.get('binding_created') is True and proof.get('reason')=='USER_STOP_AFTER_CURRENT'
                            and (root/'STOP_AFTER_CURRENT.json').is_file(),'unproved passive stop')
            elif (raw/'events.jsonl').exists():
                require(visit_apps[sid]==1,'raw execution has no unique APP command')
                require(sha256(raw/'events.jsonl')==record['events_sha256'] and
                        sha256(raw/'journal_closed.json')==record['closed_sha256'],'previous raw/closure changed')
                require(load_json(raw/'journal_closed.json')['status']=='SYNCED_AND_CLOSED','previous APP not drained/closed')
                require(outcome.is_file() and load_json(outcome)['status']==record['outcome'],'previous outcome differs')
                raw_hits[sid].append(root)
            elif artifacts:
                require(visit_apps[sid]==0,'preAPP artifacts have APP delivery')
                require(not (registry/'START.json').exists() and not (registry/'CLAIM.json').exists(),'preAPP has START/claim')
                if raw.exists():
                    require({p.name for p in raw.iterdir()}=={'host_hal_partial.jsonl'} and
                            (raw/'host_hal_partial.jsonl').stat().st_size==0,'preAPP raw contains actual samples')
                if registry.exists():
                    require({p.name for p in registry.iterdir()}=={'PRESTART_REJECT.json','host_hal_partial.jsonl'},'unproved preAPP registry files')
                    reject=load_json(registry/'PRESTART_REJECT.json')
                    require(reject['START'] is False and reject['session_run_consumed'] is False,'preAPP consumed a run')
                    require((registry/'host_hal_partial.jsonl').stat().st_size==0,'preAPP registry contains samples')
                if outcome.exists():require(load_json(outcome).get('APP_launch_intent') is False,'preAPP has APP intent')
                else:
                    paused=load_json(stop)
                    require(paused.get('external_host_stop') is True and paused.get('active_APPs_at_stop')==0,'binding-only pause unproved')
    intent_counts={sid:0 for sid in app_counts}
    for label in spec['previous_global_reservation_roots']:
        root=Path(label);require(not (root/'ACTIVE_OWNER.json').exists(),'previous owner still active')
        for p in root.rglob('*.json'):
            add(p,root.name+'/'+p.relative_to(root).as_posix())
            if p.name=='APP_LAUNCH_INTENT.json':
                sid=p.parent.name;require(sid in intent_counts,'foreign global APP intent');intent_counts[sid]+=1
        for record in ledger['records']:
            if record['APP_launches']==0:require(not (root/'reservations'/record['session_id']).exists(),'untouched ID already reserved')
    for record in ledger['records']:
        sid=record['session_id'];expected=record['APP_launches']
        require(app_counts[sid]==len(raw_hits[sid])==expected,'missing/duplicate prior APP or raw')
        require(intent_counts[sid]<=expected,'duplicate/ambiguous global APP intent')
    return inventory,raw_hits


def carry_references(rows,ledger,raw_hits):
    pending={r['session_id'] for r in rows};used={r['session_id'] for r in ledger['records'] if r['APP_launches']}
    needed={r['gate_block_id']:r for r in rows if r['reference_role']=='MATCH_FIXED' and r['reference_owner_session_id'] not in pending}
    carry=[]
    for block,row in sorted(needed.items()):
        owner=row['reference_owner_session_id'];require(owner in used and len(raw_hits[owner])==1,'reference owner not completed')
        p=raw_hits[owner][0]/'references'/(block+'.json');x=load_json(p)
        require(x['block_id']==block and x['reference_session_id']==owner and x['frozen_before_any_main_request'] is True and x['outcome_inputs_used'] is False,'reference was reselected/unproved')
        carry.append({'path':str(p),'sha256':sha256(p),'Tref_c':x['Tref_c'],'block_id':block,'reference_owner':owner})
    return carry


def validate_time_window(window,preparation_only):
    require(preparation_only is False and window['execution_authorized'] is True and window.get('PC_MOCK_ONLY') is not True,'PREPARATION_ONLY: fresh user time window required')
    device=dt.datetime.fromisoformat(window['hard_stop_UTC']);work=dt.datetime.fromisoformat(window['work_stop_UTC'])
    require(device.utcoffset() is not None and work.utcoffset() is not None and (work-device).total_seconds()>=300,'reserve final5min')
    check_deadline(window,'NEW_SESSION')


def inspect(job,runtime=False,require_pc=True):
    if runtime:validate_time_window(load_json(Path(job['window_file'])),job.get('preparation_only'))
    contract=load_json(Path(job['revision_contract_file']));b=load_json(Path(job['global_binding']))
    require(contract['remaining_coordinator_sha256']==sha256(Path(__file__)),'remaining coordinator changed')
    require(contract['followup_coordinator_sha256']==sha256(Path(executor.__file__)),'frozen C3 executor changed')
    require(contract['global_binding_sha256']==sha256(Path(job['global_binding'])),'binding changed')
    require(b['ledger_sha256']==sha256(Path(b['ledger_path'])) and b['window_sha256']==sha256(Path(job['window_file'])),'ledger/window changed')
    ledger=load_json(Path(b['ledger_path']));plan=load_json(Path(job['plan']));window=load_json(Path(job['window_file']))
    remaining=exact_scope(plan,ledger);ids=window['registered_session_ids']
    require(ids and ids==[r['session_id'] for r in remaining[:len(ids)]],'visit is not first untouched prefix')
    require(contract['visit_session_ids']==ids and window['plan_sha256']==sha256(Path(job['plan']))==ledger['plan_sha256'],'scope/plan differs')
    rows=remaining[:len(ids)];inventory,hits=history_inventory(b,plan,ledger)
    require(inventory==b['history_inventory'],'historical evidence added/removed/changed')
    require(carry_references(remaining,ledger,hits)==b['carry_references'],'carry reference changed')
    for key,digest in b['job_inputs_sha256'].items():require(sha256(Path(job[key]))==digest,'bound input changed: '+key)
    for sid,digest in b['pending_manifests_sha256'].items():require(sha256(Path(job['prepared_manifests'])/(sid+'.json'))==digest,'pending manifest changed')
    verify_source_entries(load_json(Path(job['source_manifest'])),ROOT,controller_file=CONTROLLER_SOURCE_FILE)
    require(not Path(job['run_root']).exists() and not Path(b['global_reservation_root']).exists(),'visit already created; never replay')
    if require_pc:
        pc=load_json(Path(job['followup_PC_verification']))
        require(pc['status']=='PASS_PC_ONLY' and pc['remaining_coordinator_sha256']==sha256(Path(__file__)) and
                pc['contract_sha256']==sha256(Path(job['revision_contract_file'])) and pc['authorization_contexts_PASS']==len(rows),'exact PC proof missing')
    return rows,window,ledger,b


def verify_authorizations(job,rows,carry,folder):
    """Actual validators, scratch-only mock times/references; discard executable fixtures."""
    temp=tempfile.TemporaryDirectory(prefix='pc_mock_',dir=folder)
    scratch=Path(temp.name).resolve();require(scratch.is_relative_to(Path(folder).resolve()),'scratch outside preparation folder')
    summaries=[]
    try:
        mockjob=copy.deepcopy(job);now=dt.datetime.now(dt.timezone.utc)
        w=load_json(Path(job['window_file']));w.update(execution_authorized=True,PC_MOCK_ONLY=True,
            hard_stop_UTC=(now+dt.timedelta(days=1)).isoformat(),work_stop_UTC=(now+dt.timedelta(days=1,minutes=5)).isoformat())
        atomic_json(scratch/'MOCK_WINDOW.json',w);mockjob['window_file']=str(scratch/'MOCK_WINDOW.json')
        refs=scratch/'fixtures'/'references';refs.mkdir(parents=True)
        for item in carry:shutil.copyfile(item['path'],refs/Path(item['path']).name)
        for row in rows:
            m,c,a,g=assemble(mockjob,row,scratch/'fixtures')
            summaries.append({'session_id':row['session_id'],'manifest_sha256':c['manifest_sha256'],
                'gate_sha256':c['gate_sha256'],'PC_MOCK_only':True,'reference_role':row['reference_role']})
            if row['reference_role']=='SELECT_FIRST':
                atomic_json(refs/(row['gate_block_id']+'.json'),{'block_id':row['gate_block_id'],'reference_session_id':row['session_id'],
                    'Tref_c':27.1,'PC_MOCK_REFERENCE_NOT_MEASURED':True})
    finally:
        require(scratch.is_relative_to(Path(folder).resolve()),'scratch cleanup outside workspace')
        temp.cleanup()
    return summaries


def prepare(spec,folder):
    require(not folder.exists(),'write-once preparation folder');folder.mkdir(parents=True)
    job=load_json(Path(spec['template_job']));ledger=load_json(Path(spec['ledger_path']));plan=load_json(Path(job['plan']))
    rows=exact_scope(plan,ledger);inventory,hits=history_inventory(spec,plan,ledger);carry=carry_references(rows,ledger,hits)
    require({r['block_id']:r['sha256'] for r in carry}==spec['required_carry_reference_sha256'],'carry differs from previously published frozen reference')
    window={'schema':'a24-user-execution-window-v1','execution_authorized':False,'hard_stop_UTC':None,'work_stop_UTC':None,
        'reserved_final_minutes':5,'registered_session_ids':[r['session_id'] for r in rows],'maximum_attempts_this_window':len(rows),
        'plan_sha256':sha256(Path(job['plan'])),'scope':'PC preparation only; bind a newly authorized user time window later'}
    atomic_json(folder/'USER_WINDOW_DRAFT.json',window)
    binding={**spec,'ledger_sha256':sha256(Path(spec['ledger_path'])),'history_inventory':inventory,'carry_references':carry,
        'window_sha256':sha256(folder/'USER_WINDOW_DRAFT.json'),'global_reservation_root':spec['new_global_root'],
        'job_inputs_sha256':{k:sha256(Path(job[k])) for k in INPUT_KEYS},
        'pending_manifests_sha256':{r['session_id']:sha256(Path(job['prepared_manifests'])/(r['session_id']+'.json')) for r in rows}}
    atomic_json(folder/'GLOBAL_BINDING.json',binding)
    contract=load_json(Path(job['revision_contract_file']))
    contract.update(remaining_coordinator_sha256=sha256(Path(__file__)),global_binding_sha256=sha256(folder/'GLOBAL_BINDING.json'),
        window_sha256=sha256(folder/'USER_WINDOW_DRAFT.json'),visit_session_ids=window['registered_session_ids'],
        user_scope='prepare untouched remaining slots only; runtime blocked until fresh user time window')
    atomic_json(folder/'EXECUTION_CONTRACT.json',contract)
    job.update(preparation_only=True,run_root=spec['new_run_root'],window_file=str(folder/'USER_WINDOW_DRAFT.json'),
        global_binding=str(folder/'GLOBAL_BINDING.json'),revision_contract_file=str(folder/'EXECUTION_CONTRACT.json'),
        followup_PC_verification=str(folder/'PC_VERIFICATION.json'))
    atomic_json(folder/'job.json',job)
    inspect(job,require_pc=False)
    checks=verify_authorizations(job,rows,carry,folder)
    proof={'status':'PASS_PC_ONLY','remaining_coordinator_sha256':sha256(Path(__file__)),
        'contract_sha256':sha256(folder/'EXECUTION_CONTRACT.json'),'authorization_contexts_PASS':len(checks),
        'device_commands':0,'APP':0,'START':0,'claim':0,'inference':0,'measurement':0,'sessions_consumed':0,
        'Git_HEAD':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip(),'uncommitted_at_verification':True,
        'pending_requests':sum(r['request_count'] for r in rows),'PC_only_cases':checks,'mock_references_not_measurements':True,
        'executable_PC_fixtures_retained':False}
    atomic_json(folder/'PC_VERIFICATION.json',proof);inspect(job)
    return job,proof


def bind_window(job,folder,device_stop,work_stop,max_sessions=None):
    rows,oldwindow,ledger,binding=inspect(job)
    device=dt.datetime.fromisoformat(device_stop);work=dt.datetime.fromisoformat(work_stop)
    require(device.utcoffset() is not None and work.utcoffset() is not None and (work-device).total_seconds()>=300,'reserve final5min with explicit timezone')
    n=len(rows) if max_sessions is None else max_sessions
    require(type(n) is int and 0<n<=len(rows),'invalid visit prefix count')
    window=copy.deepcopy(oldwindow);window.update(execution_authorized=True,hard_stop_UTC=device.isoformat(),work_stop_UTC=work.isoformat(),
        registered_session_ids=[r['session_id'] for r in rows[:n]],maximum_attempts_this_window=n,
        scope='fresh user time window bound separately; unchanged untouched prefix only')
    check_deadline(window,'NEW_SESSION');require(not folder.exists(),'new visit folder required');folder.mkdir(parents=True)
    atomic_json(folder/'USER_WINDOW.json',window)
    binding=copy.deepcopy(binding);binding['window_sha256']=sha256(folder/'USER_WINDOW.json')
    # Runtime roots are selected by this fresh write-once visit name.
    require(re.fullmatch(r'[A-Za-z0-9_-]+',folder.name) is not None,'unsafe visit name')
    binding['global_reservation_root']=str(Path(binding['global_reservation_root']).parent/(folder.name+'_GLOBAL'))
    atomic_json(folder/'GLOBAL_BINDING.json',binding)
    contract=load_json(Path(job['revision_contract_file']));contract.update(global_binding_sha256=sha256(folder/'GLOBAL_BINDING.json'),
        window_sha256=sha256(folder/'USER_WINDOW.json'),visit_session_ids=window['registered_session_ids'])
    atomic_json(folder/'EXECUTION_CONTRACT.json',contract)
    bound=copy.deepcopy(job);bound.update(preparation_only=False,run_root=str(Path(job['run_root']).parent/folder.name),
        window_file=str(folder/'USER_WINDOW.json'),global_binding=str(folder/'GLOBAL_BINDING.json'),
        revision_contract_file=str(folder/'EXECUTION_CONTRACT.json'),followup_PC_verification=str(folder/'PC_VERIFICATION.json'))
    atomic_json(folder/'job.json',bound);inspect(bound,require_pc=False)
    checks=verify_authorizations(bound,rows[:n],binding['carry_references'],folder)
    atomic_json(folder/'PC_VERIFICATION.json',{'status':'PASS_PC_ONLY','remaining_coordinator_sha256':sha256(Path(__file__)),
        'contract_sha256':sha256(folder/'EXECUTION_CONTRACT.json'),'authorization_contexts_PASS':len(checks),
        'device_commands':0,'fresh_time_window_only_no_execution':True,'PC_only_cases':checks})
    inspect(bound,runtime=True);return bound


class ReadOnlyClient(ReconnectingAdbClient):
    def command(self,*args,**kwargs):
        allowed=(args[:2] in {('shell','getprop'),('shell','pidof'),('shell','sha256sum')} or
            args[:3] in {('shell','settings','get'),('shell','pm','path')} or
            (args[:2]==('shell','dumpsys') and args[2:] in [('battery',),('power',)]) or
            (len(args)>3 and args[:2]==('shell','run-as') and args[3:]==
             ('find','files/a24_laptop_inputs','files/a24_laptop_results','-mindepth','1','-maxdepth','1','-type','d')))
        require(allowed,'READ_ONLY: command blocked');return super().command(*args,**kwargs)


def device_check(job,folder,client_factory=ReadOnlyClient):
    rows,*_=inspect(job);require(not folder.exists(),'new read-only receipt folder required');folder.mkdir(parents=True)
    target=load_json(Path(job['device_registration']));identity=load_json(Path(job['apk_identity']))
    client=client_factory(job['adb'],target['adb_serial'],target['hardware_serial'],target['build_fingerprint'],folder/'adb_readonly_commands.jsonl',wait_seconds=30)
    client.reconnect();blockers=[]
    for key,prop in [('hardware_serial','ro.serialno'),('build_fingerprint','ro.build.fingerprint')]:
        require(client.command('shell','getprop',prop).decode().strip()==target[key],'registered phone differs')
    for process in [identity['package'],identity['package']+':model_probe',identity['package']+':a24_preparation','com.example.d1check.currentdiagnostic']:
        if client.command('shell','pidof',process,accepted_codes=(0,1),reject_stderr=True).strip():blockers.append('DEVICE_PROCESS_ACTIVE')
    package=identity['package'];apk_paths=client.command('shell','pm','path',package).decode().splitlines()
    require(len(apk_paths)==1 and apk_paths[0].startswith('package:/data/app/'),'unexpected installed APK path')
    actual=client.command('shell','sha256sum',apk_paths[0][8:]).decode().split()[0]
    require(actual==identity['apk_sha256'],'installed APK differs')
    battery=read_battery(client)
    if battery['SOC_percent'] is None or battery['SOC_percent']<10:blockers.append('SOC_BELOW10_OR_UNKNOWN')
    if battery['plugged'] is not False:blockers.append('CHARGING_OR_UNKNOWN')
    brightness=client.command('shell','settings','get','system','screen_brightness').decode().strip()
    mode=client.command('shell','settings','get','system','screen_brightness_mode').decode().strip()
    awake='mWakefulness=Awake' in client.command('shell','dumpsys','power').decode()
    if brightness!='81' or mode!='0' or not awake:blockers.append('SCREEN_CONTRACT_NOT_READY')
    listing=client.command('shell','run-as',package,'find','files/a24_laptop_inputs','files/a24_laptop_results','-mindepth','1','-maxdepth','1','-type','d').decode().splitlines()
    pending={r['session_id'] for r in rows};collisions=sorted({Path(x).name for x in listing}&pending)
    if collisions:blockers.append('PENDING_REMOTE_PATH_EXISTS')
    proof={'status':'READ_ONLY_DEVICE_CHECK_COMPLETE','checked_UTC':dt.datetime.now(dt.timezone.utc).isoformat(),
        'registered_identity_match':True,'installed_APK_sha256':actual,'SOC_percent':battery['SOC_percent'],'plugged':battery['plugged'],
        'screen_brightness':brightness,'screen_mode':mode,'screen_awake':awake,'pending_path_collisions':collisions,
        'blockers':sorted(set(blockers)),'measurement_admitted':False,'needs_fresh_time_window':True,
        'actual_read_only_ADB_calls':client.actual_calls,'APP':0,'START':0,'claim':0,'inference':0,'instrumentation':0,
        'measurement':0,'sessions_consumed':0,'settings_changed':False,'APK_install':0}
    atomic_json(folder/'DEVICE_READONLY_VERIFICATION.json',proof);return proof


def main():
    p=argparse.ArgumentParser(description=__doc__);subs=p.add_subparsers(dest='action',required=True)
    prep=subs.add_parser('prepare');prep.add_argument('spec',type=Path);prep.add_argument('output',type=Path)
    for action in ['inspect','bind-window','device-check','execute']:
        sub=subs.add_parser(action);sub.add_argument('job',type=Path)
        if action in ['bind-window','device-check']:sub.add_argument('output',type=Path)
        if action=='bind-window':
            sub.add_argument('--device-stop',required=True);sub.add_argument('--work-stop',required=True);sub.add_argument('--max-sessions',type=int)
        if action=='execute':sub.add_argument('--execute-authorized',action='store_true')
    a=p.parse_args()
    if a.action=='prepare':_,proof=prepare(load_json(a.spec),a.output.resolve());print(json.dumps({k:v for k,v in proof.items() if k!='PC_only_cases'}));return
    job=load_json(a.job)
    if a.action=='inspect':rows,*_=inspect(job);print(json.dumps({'status':'PC_READY_NO_TIME_WINDOW' if job['preparation_only'] else 'TIME_BOUND_NOT_STARTED','remaining':len(rows),'device_commands':0}))
    elif a.action=='bind-window':bind_window(job,a.output.resolve(),a.device_stop,a.work_stop,a.max_sessions);print(json.dumps({'status':'TIME_BOUND_NOT_STARTED','device_commands':0}))
    elif a.action=='device-check':print(json.dumps(device_check(job,a.output.resolve())))
    else:
        require(a.execute_authorized,'PREPARATION_ONLY: explicit execution flag absent');inspect(job,runtime=True)
        executor.inspect=lambda j:inspect(j,runtime=True)
        executor.execute(job)


if __name__=='__main__':main()
