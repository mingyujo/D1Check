"""Separate, write-once synthetic CPU/GPU current-response pilot; not CONFIRM/J calibration."""
import argparse
import base64
import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import time

from d1_a24_laptop_validator import load_json, sha256, ValidationError
from d1_a24_laptop_control import atomic_json
from d1_a24_revision02_window import BoundedClient, check_deadline
from d1_a24_revision02_suite_control import read_battery

PACKAGE='com.example.d1check.currentdiagnostic'
ACTIVITY=PACKAGE+'/.CurrentDiagnosticActivity'


class DiagnosticClient(BoundedClient):
    def command(self,*args,**kwargs):
        # Frozen reconnect code intentionally recognizes only the old app.
        # Repeat only these new-app reads after its same-phone handshake.
        read = (args[:4]==('exec-out','run-as',PACKAGE,'cat') or
                args[:4]==('shell','run-as',PACKAGE,'ls'))
        try:return super().command(*args,**kwargs)
        except ValidationError as error:
            if read and 'connection recovered after ambiguous mutation' in str(error):
                return super().command(*args,**kwargs)
            raise


def validate_plan(p):
    assert p['schema']=='a24-current-response-diagnostic-plan-v1'
    assert p['maximum_APP_attempts']==1 and p['replay_or_replacement']==0
    assert p['idle_control_periods_ms']==[900,200,100,100,200,900]
    assert p['idle_control_seconds']==20 and p['settle_seconds']==30 and p['final_tail_seconds']==30
    expected=[('CPU',100,'DEVELOPMENT'),('GPU',200,'DEVELOPMENT'),('GPU',100,'DEVELOPMENT'),('CPU',200,'DEVELOPMENT'),('CPU',200,'HELD_OUT'),('GPU',200,'HELD_OUT')]
    assert [(x['resource'],x['period_ms'],x['split']) for x in p['pulses']]==expected
    assert [x['pre_seconds'] for x in p['pulses']]==[20,23,18,22,19,21]
    assert all(x['on_seconds']==10 and x['post_seconds']==30 for x in p['pulses'])
    assert p['apply_time_correction_to_CONFIRM'] is False and p['physical_J_validation'] is False
    duration=p['settle_seconds']+len(p['idle_control_periods_ms'])*p['idle_control_seconds']+sum(x['pre_seconds']+x['on_seconds']+x['post_seconds'] for x in p['pulses'])+p['final_tail_seconds']
    assert duration==543
    return duration


def inspect(job):
    p=load_json(Path(job['plan']));validate_plan(p)
    assert sha256(Path(job['plan']))==job['plan_sha256']
    assert sha256(Path(job['apk']))==job['apk_sha256']
    for x in job['source_files']:
        assert sha256(Path(x['path']))==x['sha256'],x['path']
    for x in job['confirmation_visits']:
        assert sha256(Path(x['root'])/'WINDOW_STOPPED.json')==x['stop_sha256']
    assert not Path(job['confirmation_owner_lock']).exists(),'active CONFIRM owner'
    assert sha256(Path(job['PC_verification']))==job['PC_verification_sha256']
    proof=load_json(Path(job['PC_verification']));assert proof['status']=='PASS_PC_ONLY'
    assert proof['host_source_sha256']==sha256(Path(__file__))
    return p


def execute(job):
    p=inspect(job);window=load_json(Path(job['window_file']))
    # One543s schedule plus setup/recovery margin, with the original20:02 hard stop.
    assert datetime.datetime.fromisoformat(window['hard_stop_UTC']).timestamp()-time.time()>=900
    root=Path(job['run_root']);assert not root.exists(),'write-once diagnostic root; no replay'
    root.mkdir(parents=True)
    target=load_json(Path(job['device_registration']));client=DiagnosticClient(job,target,window)
    started=False
    try:
        client.reconnect()
        for name in ['com.example.d1check.benchmarkrunner.a24measurement', 'com.example.d1check.benchmarkrunner.a24measurement:a24_preparation',PACKAGE]:
            assert not client.command('shell','pidof',name,accepted_codes=(0,1),reject_stderr=True).strip(),'foreign/active measurement process'
        b=read_battery(client);assert b['SOC_percent']>=10 and b['plugged'] is False
        assert client.command('shell','settings','get','system','screen_brightness').decode().strip()=='81'
        assert client.command('shell','settings','get','system','screen_brightness_mode').decode().strip()=='0'
        assert 'mWakefulness=Awake' in client.command('shell','dumpsys','power').decode()
        assert sha256(Path(job['confirmation_apk']))==job['confirmation_apk_sha256']
        original_path=client.command('shell','pm','path','com.example.d1check.benchmarkrunner.a24measurement').decode().strip().split('package:')[-1]
        assert client.command('shell','sha256sum',original_path).decode().split()[0]==job['confirmation_apk_sha256']
        atomic_json(root/'PRESTART.json',{'battery':b,'same_registered_device':True,'confirmation_APK_unchanged':True,'diagnostic_APP_budget':1,'CONFIRM_slots_consumed':0})
        installed=client.command('install','-r',str(Path(job['apk']).resolve()))
        assert b'Success' in installed
        apkpath=client.command('shell','pm','path',PACKAGE).decode().strip().split('package:')[-1]
        assert client.command('shell','sha256sum',apkpath).decode().split()[0]==job['apk_sha256']
        config={k:p[k] for k in ['idle_control_periods_ms','idle_control_seconds','settle_seconds','final_tail_seconds','pulses']}
        config.update(schema='a24-current-response-diagnostic-v1',session_id=p['session_id'],fingerprint=target['build_fingerprint'],apk_sha256=job['apk_sha256'],hard_stop_wall_ms=int(datetime.datetime.fromisoformat(window['hard_stop_UTC']).timestamp()*1000),plan_sha256=job['plan_sha256'])
        atomic_json(root/'CONFIG_PRIVATE.json',config)
        payload=base64.b64encode(json.dumps(config,separators=(',',':')).encode()).decode()
        atomic_json(root/'APP_LAUNCH_INTENT.json',{'UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'session_id':p['session_id'],'no_automatic_replay':True,'additional_diagnostic_budget':1,'formal81_budget_consumed':0})
        started=True
        client.command('shell','am','start','-n',ACTIVITY,'--ez','execute_authorized','true','--es','session_id',p['session_id'],'--es','config_base64',payload)
        remote='files/diagnostics/'+p['session_id']+'/'
        deadline=min(time.monotonic()+900,time.monotonic()+datetime.datetime.fromisoformat(window['hard_stop_UTC']).timestamp()-time.time()-2)
        while time.monotonic()<deadline:
            data=client.command('shell','run-as',PACKAGE,'ls',remote+'journal_closed.json',accepted_codes=(0,1))
            if b'journal_closed.json' in data:
                for name in ['events.jsonl','config.json','identity.json','summary.json','journal_closed.json']:
                    raw=client.command('exec-out','run-as',PACKAGE,'cat',remote+name)
                    with (root/name).open('xb') as f:f.write(raw)
                closure=load_json(root/'journal_closed.json');summary=load_json(root/'summary.json')
                assert closure['status']=='SYNCED_AND_CLOSED' and closure['sampler_terminated']
                assert closure['events_sha256']==sha256(root/'events.jsonl')
                # Only our newly installed, drained diagnostic app is stopped.
                client.command('shell','am','force-stop',PACKAGE)
                assert not client.command('shell','pidof',PACKAGE,accepted_codes=(0,1),reject_stderr=True).strip()
                original_path=client.command('shell','pm','path','com.example.d1check.benchmarkrunner.a24measurement').decode().strip().split('package:')[-1]
                assert client.command('shell','sha256sum',original_path).decode().split()[0]==job['confirmation_apk_sha256']
                atomic_json(root/'HOST_RECOVERY.json',{'status':'RECOVERED_CLOSED_DIAGNOSTIC','summary_status':summary['status'],'completed_pulses':summary['completed_pulses'],'source_sha256':sha256(Path(__file__)),'events_sha256':sha256(root/'events.jsonl'),'confirmation_APK_unchanged':True,'actual_ADB_calls':client.actual_calls,'additional_diagnostic_APP_attempts':1,'formal81_budget_consumed':0})
                print(json.dumps({'status':summary['status'],'completed_pulses':summary['completed_pulses'],'root':str(root)}),flush=True)
                return
            print(json.dumps({'status':'CURRENT_DIAGNOSTIC_RUNNING','elapsed_s':round(900-(deadline-time.monotonic()),1)}),flush=True)
            time.sleep(15)
        raise ValidationError('diagnostic closure not recovered before deadline; preserve and inspect, never replay')
    except Exception as e:
        atomic_json(root/'HOST_STOP_PRESERVED.json',{'reason':str(e),'APP_intent':started,'automatic_replay':False,'actual_ADB_calls':client.actual_calls})
        raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('job',type=Path);parser.add_argument('--execute-authorized',action='store_true')
    args=parser.parse_args();job=load_json(args.job)
    if args.execute_authorized:execute(job)
    else:inspect(job);print(json.dumps({'status':'PC_INSPECT_ONLY','device_commands':0}))
