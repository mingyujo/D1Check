"""One-shot, serial queue: existing C10 -> unused ORDER -> failed-case12.

Waiting on local closure creates no device commands. Every new execution has
its own immutable settings/registry; no live-source edits or concurrent runs.
"""
import argparse
import ctypes
import datetime as dt
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

from d1_a24_laptop_validator import load_json, sha256
from d1_a24_revision02_suite import require
from d1_a24_revision02_suite_control import atomic_json, safe_extract, read_battery
from d1_a24_revision02_window import check_deadline
from d1_a24_measurement_connection import ReconnectingAdbClient
from d1_a24_measurement_batch import finish_only_closed_owned_process
from d1_a24_failed_prestart_evidence import verify_failed_prestart
from d1_a24_confirm_remaining import ReadOnlyClient

ROOT=Path(__file__).resolve().parents[1]


def parser_proved(path, expected_sha):
    require(sha256(path)==expected_sha,'actual parser receipt changed')
    x=ET.parse(path).getroot()
    require(x.get('tests')=='1' and all(x.get(k)=='0' for k in ['failures','errors','skipped']),
            'new actual-manifest parser test did not pass')
    require(any(t.get('name')=='twelveFreshSupplementManifestsUseTheUnchangedActualParser' for t in x.findall('testcase')),
            'wrong actual-manifest parser test')


def owner_absent(job):
    parent=Path(job['run_root']).parent
    return not any((p/'ACTIVE_OWNER.json').exists() for p in parent.glob('A24*') if p.is_dir())


def closed_before_followon(job):
    root=Path(job['run_root'])
    return (root/'WINDOW_STOPPED.json').is_file() and owner_absent(job)


def recover_closed_rejection(job, row):
    """No APP/START/replay. Recover only the already stopped exact session."""
    root=Path(job['run_root']);sid=row['session_id'];plan=load_json(Path(job['plan']))
    require(closed_before_followon(job),'previous worker still active')
    out=root/'read_only_recovery'/sid
    if (out/'CLOSED_FAILURE_RECOVERY.json').exists():
        actual=verify_failed_prestart(root,plan,row,out/'recovered_app',plan_sha256=sha256(Path(job['plan'])))
        proof=load_json(out/'CLOSED_FAILURE_RECOVERY.json')
        require(all(proof[k]==v for k,v in actual.items()) and proof['own_device_process_absent'] is True,'bad saved recovery')
        return
    require(not out.exists(),'partial recovery exists; never overwrite')
    out.mkdir(parents=True)
    target=load_json(Path(job['device_registration']));ident=load_json(Path(job['apk_identity']));package=ident['package']
    client=ReconnectingAdbClient(job['adb'],target['adb_serial'],target['hardware_serial'],target['build_fingerprint'],
        out/'readonly_recovery_and_closed_cleanup_commands.jsonl',wait_seconds=1200)
    client.reconnect();remote='files/a24_laptop_results/'+sid
    closed=None
    for _ in range(12):
        try:
            value=json.loads(client.command('exec-out','run-as',package,'cat',remote+'/journal_closed.json'))
            if value.get('session_id')==sid and value.get('status')=='SYNCED_AND_CLOSED':closed=value;break
        except (ValueError,UnicodeError):pass
        time.sleep(5)
    require(closed is not None,'old APP closure unproved; do not stop live process')
    payload=client.command('exec-out','run-as',package,'tar','-cf','-',remote)
    recovered=out/'recovered_app'
    safe_extract(payload,recovered,session_id=sid,maximum_bytes=load_json(Path(job['gate']))['maximum_raw_bytes'])
    proof=verify_failed_prestart(root,plan,row,recovered,plan_sha256=sha256(Path(job['plan'])))
    require(finish_only_closed_owned_process(client,recovered,sid,package=package),'closed process cleanup unproved')
    pids=[client.command('shell','pidof',n,accepted_codes=(0,1),reject_stderr=True).strip()
          for n in [package,package+':model_probe',package+':a24_preparation']]
    require(not any(pids),'previous device process still active')
    proof.update(own_device_process_absent=True,new_APP=0,new_MAIN=0,replayed_session=0,
        actual_recovery_and_closed_cleanup_ADB_calls=client.actual_calls,checked_UTC=dt.datetime.now(dt.timezone.utc).isoformat())
    atomic_json(out/'CLOSED_FAILURE_RECOVERY.json',proof)


def previous_safely_closed(job):
    require(closed_before_followon(job),'previous root not closed/owner present')
    stop=load_json(Path(job['run_root'])/'WINDOW_STOPPED.json')
    for row in stop['outcomes']:
        if row['status']=='COMPLETE_TRACE_RECOVERED':
            raw=Path(job['run_root'])/'raw'/row['session_id']
            require(load_json(raw/'journal_closed.json')['status']=='SYNCED_AND_CLOSED'
                    and load_json(raw/'cleanup.json')['actual_return_confirmed'] is True,'previous normal APP not closed')
        elif row['status']=='PRESTART_REJECT' and row.get('APP_launch_intent') is True:recover_closed_rejection(job,row)
        else:require(row.get('APP_launch_intent') is False,'ambiguous previous APP failure; hold queue')
    return stop


def readiness(job,rows,folder):
    require(owner_absent(job),'another worker active before read-only check')
    require(not folder.exists(),'fresh readonly receipt required');folder.mkdir()
    t=load_json(Path(job['device_registration']));ident=load_json(Path(job['apk_identity']));package=ident['package']
    client=ReadOnlyClient(job['adb'],t['adb_serial'],t['hardware_serial'],t['build_fingerprint'],folder/'commands.jsonl',wait_seconds=1200)
    client.reconnect()
    require(client.command('shell','getprop','ro.serialno').decode().strip()==t['hardware_serial'],'different phone')
    require(client.command('shell','getprop','ro.build.fingerprint').decode().strip()==t['build_fingerprint'],'firmware changed')
    for n in [package,package+':model_probe',package+':a24_preparation','com.example.d1check.currentdiagnostic']:
        require(not client.command('shell','pidof',n,accepted_codes=(0,1),reject_stderr=True).strip(),'previous app process active')
    paths=client.command('shell','pm','path',package).decode().splitlines()
    require(len(paths)==1 and paths[0].startswith('package:/data/app/'),'unexpected APK path')
    require(client.command('shell','sha256sum',paths[0][8:]).decode().split()[0]==ident['apk_sha256'],'APK changed')
    battery=read_battery(client);require(battery['SOC_percent'] is not None and battery['SOC_percent']>=10
        and battery['plugged'] is False,'battery/charging not admitted')
    require(client.command('shell','settings','get','system','screen_brightness').decode().strip()=='81','brightness changed')
    require(client.command('shell','settings','get','system','screen_brightness_mode').decode().strip()=='0','screen mode changed')
    require('mWakefulness=Awake' in client.command('shell','dumpsys','power').decode(),'phone asleep')
    listing=client.command('shell','run-as',package,'find','files/a24_laptop_inputs','files/a24_laptop_results','-mindepth','1','-maxdepth','1','-type','d').decode().splitlines()
    require(not ({Path(x).name for x in listing}&{r['session_id'] for r in rows}),'new ID already exists on device')
    proof={'status':'PASS_READONLY_PREFLIGHT_NOT_MAIN_ADMISSION','checked_UTC':dt.datetime.now(dt.timezone.utc).isoformat(),
        'battery':battery,'APK_sha256':ident['apk_sha256'],'identity_screen_paths_processes_match':True,
        'actual_ADB_calls':client.actual_calls,'new_APP_MAIN_claim':0,'settings_changed':False,'APK_installed':False}
    atomic_json(folder/'PROOF.json',proof)


def run(configfile):
    cfg=load_json(configfile);meta=configfile.parent
    require(cfg['queue_source_sha256']==sha256(Path(__file__)),'queue code changed')
    for name,digest in cfg['guard_source_sha256s'].items():
        require(sha256(ROOT/name)==digest,'queued guard dependency changed: '+name)
    parser_proved(Path(cfg['actual_parser_receipt']),cfg['actual_parser_receipt_sha256'])
    require(not (meta/'OWNER.json').exists(),'queue was already armed')
    for entry in cfg['stages']:
        require(sha256(Path(entry['job']))==entry['job_sha256'],'queued job changed')
        require(sha256(ROOT/entry['script'])==entry['script_sha256'],'queued runner changed')
    atomic_json(meta/'OWNER.json',{'pid':os.getpid(),'armed_UTC':dt.datetime.now(dt.timezone.utc).isoformat(),
        'config_sha256':sha256(configfile),'measurement_device_commands_while_waiting':0})
    keep=ctypes.windll.kernel32.SetThreadExecutionState;keep.restype=ctypes.c_uint32
    require(keep(0x80000001)!=0,'scoped sleep inhibition failed')
    prior=load_json(Path(cfg['current_job']));reason='REGISTERED_FOLLOWON_FINISHED';completed=[]
    try:
        while not closed_before_followon(prior):
            require(not (meta/'STOP_AFTER_CURRENT.json').exists(),'USER_STOP_FOLLOWON')
            check_deadline(load_json(Path(prior['window_file'])),'NEW_SESSION')
            (meta/'LIVE_STATUS.json').write_text(json.dumps({'status':'WAITING_EXISTING_C10_NO_DEVICE_COMMANDS',
                'checked_UTC':dt.datetime.now(dt.timezone.utc).isoformat()}),encoding='utf-8')
            time.sleep(15)
        previous_safely_closed(prior)
        for stage in cfg['stages']:
            require(not (meta/'STOP_AFTER_CURRENT.json').exists(),'USER_STOP_FOLLOWON')
            job=load_json(Path(stage['job']));check_deadline(load_json(Path(job['window_file'])),'NEW_SESSION')
            if stage['label']=='UNUSED_EXTRA4_ORDER':
                from d1_a24_extra4_tail import inspect
                row,_=inspect(job);rows=[row]
            else:
                from d1_a24_supplement_runner import inspect
                rows=inspect(job)
            readiness(job,rows,meta/(stage['label']+'_readonly'))
            context={'actual_start_UTC':dt.datetime.now(dt.timezone.utc).isoformat(),
                'source_HEAD':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip(),
                'uncommitted_changes':bool(subprocess.check_output(['git','status','--porcelain'],cwd=ROOT).strip()),
                'script_sha256':sha256(ROOT/stage['script']),'job_sha256':sha256(Path(stage['job']))}
            atomic_json(meta/(stage['label']+'_RUNTIME_CONTEXT.json'),context)
            with (meta/(stage['label']+'.log')).open('xb') as log:
                child=subprocess.Popen([sys.executable,'-u','-B',str(ROOT/stage['script']),'execute',stage['job'],'--execute-authorized'],
                    cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                atomic_json(meta/(stage['label']+'_STARTED.json'),{'pid':child.pid,'first_only':True,**context})
                while child.poll() is None:
                    if (meta/'STOP_AFTER_CURRENT.json').exists():
                        stop=Path(job['run_root'])/'STOP_AFTER_CURRENT.json'
                        if stop.parent.exists() and not stop.exists():atomic_json(stop,{'reason':'USER_STOP_FOLLOWON_NO_NEW_APP'})
                    time.sleep(10)
            require(child.returncode==0,'queued runner errored; preserve and hold')
            stop=previous_safely_closed(job)
            completed.append({'label':stage['label'],'new_APP':stop['new_APP_intents'],'stop_reason':stop['reason']})
            atomic_json(meta/(stage['label']+'_STOPPED.json'),completed[-1])
            if stage['label']=='FAILED_CASE12':break
    except Exception as error:reason='FOLLOWON_HELD: '+str(error)
    finally:
        atomic_json(meta/'QUEUE_STOPPED.json',{'reason':reason,'completed_stages':completed,'stop_UTC':dt.datetime.now(dt.timezone.utc).isoformat(),
            'old_failures_replaced':False,'infinite_retry':False})
        keep(0x80000000)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('config',type=Path);p.add_argument('--execute-authorized',action='store_true')
    a=p.parse_args();require(a.execute_authorized,'explicit followon execution flag absent');run(a.config.resolve())
