"""Opt-in, single-use device runner. Import only for an explicitly approved run."""
from __future__ import annotations

import json
import math
import re
import time
from pathlib import Path

from tools import d1_arrival_energy_collection as c
from tools import d1_arrival_plan as p
from tools import d1_arrival_device as legacy
from tools import d1_arrival_timing_calibration_device as shared
from tools import d1_energy_collection_device as energy_device
from tools import d1_collection_recovery as install
from tools.d1_adb_observed_client import ObservedDevice
from tools import d1_energy_screen as screen
from tools import d1_energy_thermal as energy
from tools import d1_arrival_start_ap

ACTIVITY='com.example.d1check.benchmarkrunner.ArrivalEnergyActivity'
ACTION='com.example.d1check.benchmarkrunner.action.ARRIVAL_ENERGY'


def write(path,value):c.cal.write_new(path,value)


def poll(d,remote,folder,manifest,plan):
    start=time.monotonic();end=min(d.deadline,start+plan.get('budget',c.BUDGET)['host_poll_seconds'])
    last_thermal=last_screen=0;armed=False;index=0;start_ap_sent=False
    while time.monotonic()<end:
        if (plan.get('single_arrival_confirmation') or plan.get('recorded_replay_confirmation')) and d.sequence>=plan['budget']['adb_commands']-20:
            raise RuntimeError('ADB observation cap reserve reached; preserve recovery/cleanup slots')
        now=time.monotonic()
        if now-last_thermal>=2:
            energy_device.thermal(d,folder,index);index+=1;last_thermal=time.monotonic()
        if now-last_screen>=10:
            screen.snapshot(d,folder,f'poll_{index:04d}',plan['screen_contract']);last_screen=time.monotonic()
        listing=d.call('shell','run-as',legacy.PACKAGE,'ls',remote,timeout=3).stdout.decode().splitlines()
        if 'cleanup.json' in listing:return
        if manifest.get('start_ap_gate') in (d1_arrival_start_ap.VERSION,d1_arrival_start_ap.DIAGNOSTIC_VERSION) and not start_ap_sent and 'start_ap.ready.json' in listing:
            c.require(armed, 'start AP before warmup approval')
            d1_arrival_start_ap.approve(d,remote,folder,manifest)
            start_ap_sent=True
            last_thermal=time.monotonic()
        if not armed and 'warmup.ready.json' in listing:
            gate=Path(folder)/'warmup_gate';gate.mkdir()
            ready=p.read(energy_device.pull_file(d,remote,'warmup.ready.json',gate))
            c.require(ready['manifest_sha256']==p.digest(folder/'input_manifest.json'),'warmup manifest mismatch')
            rows=p.read(energy_device.pull_file(d,remote,'warmup.json',gate))
            c.require(len(rows)==8 and all(sum(r['key']==k for r in rows)==2 for k in c.old.KEYS),'warmup incomplete')
            for r in rows:
                ref=plan['references'][r['key']]
                c.require(p.digest(ref['path'])==ref['sha256'],'quality reference changed')
                c.old.quality(p.read(ref['path']),r['result'])
            pid=d.call('shell','pidof',legacy.PACKAGE+':model_probe',timeout=3).stdout.decode().strip()
            c.require(re.fullmatch(r'\d+',pid),'single app process')
            logs=d.call('logcat','-d','-v','threadtime','--pid='+pid,'-s','D1ENERGY:I','tflite:I',timeout=5).stdout
            (gate/'delegate_log.txt').write_bytes(logs)
            write(gate/'gpu.json',energy_device.gpu_proof(logs.decode(errors='replace'),manifest['session_id']))
            energy_device.arm(d,'files/arrival-scheduler-inputs/'+manifest['session_id'],'warmup',ready['manifest_sha256'])
            write(gate/'arm_receipt.json',dict(utc=legacy.utc(),manifest_sha256=ready['manifest_sha256']))
            armed=True
        time.sleep(.25)
    raise TimeoutError('host poll elapsed; later calls are unknown, never retry')


def validate(folder,manifest,plan):
    artifacts=Path(folder)/'artifacts'
    c.require(p.digest(artifacts/'manifest.json')==p.digest(folder/'input_manifest.json'),'output manifest')
    cleanup=p.read(artifacts/'cleanup.json')
    if cleanup['status']!='completed':
        failure_file=artifacts/'session_failure.json'
        failure=p.read(failure_file) if failure_file.is_file() else {}
        raise RuntimeError('app did not complete: '+str(failure.get('message') or cleanup.get('error') or
                                               cleanup['status']))
    summary=p.read(artifacts/'summary.json')
    c.require(cleanup['status']=='completed' and summary['status']=='completed','app completion')
    boundary=p.read(artifacts/'common_boundary.json');rows=p.read(artifacts/'requests.json')
    if manifest.get('start_ap_gate') in (d1_arrival_start_ap.VERSION,d1_arrival_start_ap.DIAGNOSTIC_VERSION):
        approval=p.read(artifacts/'start_ap.accepted.json')
        c.require(approval['common_start_ns']==boundary['start_ns'] and
                  (manifest['start_ap_gate']!=d1_arrival_start_ap.DIAGNOSTIC_VERSION or
                   approval.get('gate_mode')==d1_arrival_start_ap.DIAGNOSTIC_VERSION) and
                  (manifest['start_ap_gate']==d1_arrival_start_ap.DIAGNOSTIC_VERSION or 32.5 <= approval['ap_c'] <= 34.0) and
                  math.isfinite(float(approval['ap_c'])) and
                  approval['read_before_ns'] <= approval['read_after_ns'] <= boundary['start_ns'] and
                  boundary['start_ns']-approval['read_before_ns'] <= 3_000_000_000,
                  'missing/invalid AP approval at actual start')
    c.require(len(rows)==len(boundary['rows'])==24 and summary['planned']==24,'request denominator')
    c.require({r['request_id'] for r in rows}=={r['request_id'] for r in manifest['requests']},'request identity')
    c.require(boundary['end_ns']-boundary['start_ns']>=120_000_000_000,'common window incomplete')
    for r in rows:
        fields=('actual_arrival_ns','dispatch_ns','execution_start_ns','output_ready_ns',
                'persist_complete_ns','worker_release_ns','lane_available_ns')
        if plan.get('recorded_replay_confirmation'):
            fields+=('host_inference_start_ns','host_inference_return_ns')
        c.require(r['terminal_status']=='succeeded' and all(r.get(field) is not None for field in fields),
                  'unfinished/request boundary')
        c.require(r['scheduled_arrival_ns']<=r['actual_arrival_ns']<=r['dispatch_ns']<=
                  r['execution_start_ns']<=r['output_ready_ns']<=r['persist_complete_ns']<=
                  r['worker_release_ns']<=r['lane_available_ns'],'time order')
        if plan.get('recorded_replay_confirmation'):
            c.require(r['execution_start_ns']<=r['host_inference_start_ns']<=
                      r['host_inference_return_ns']<=r['output_ready_ns'], 'host inference bracket')
        key=r['task_id']+'_'+r['selected_backend']
        if plan.get('recorded_replay_confirmation'):
            source=next(q for q in manifest['requests'] if q['request_id']==r['request_id'])
            c.require(r['selected_backend']==source['recorded_backend'] and
                      r['source_request_id']==source['source_request_id'] and
                      r['dispatch_ns']>=boundary['start_ns']+source['release_offset_ns'] and
                      r['recorded_release_ns']==boundary['start_ns']+source['release_offset_ns'],
                      'recorded replay allocation/release gate')
        else:
            c.require(r['selected_backend']==('CPU' if manifest['policy']=='CPU_URGENT' or r['priority']=='urgent' else 'GPU'),'policy allocation')
        result=p.read(artifacts/(r['request_id']+'.result.json'))
        c.old.quality(p.read(plan['references'][key]['path']),result)
    if plan.get('recorded_replay_confirmation'):
        for backend in ('CPU','GPU'):
            ordered=sorted((r for r in rows if r['selected_backend']==backend),
                           key=lambda r:r['dispatch_ns'])
            c.require(all(a['lane_available_ns']<=b['dispatch_ns'] for a,b in zip(ordered,ordered[1:])),
                      'busy lane overwritten before actual callback')
    events,partial=c.old.progress_prefix((artifacts/'progress.jsonl').read_bytes())
    c.require(partial==0 and sum(e.get('kind')=='warmup_return' for e in events)==8 and
              sum(e.get('kind')=='runtime_return' for e in events)==4 and
              sum(e.get('kind')=='lane_available' for e in events)==24,'progress count')
    thermal=[json.loads(x) for x in (Path(folder)/'thermal.jsonl').read_text(encoding='utf-8').splitlines()]
    c.require(len(thermal)>=30 and all(t['thermal_status']=='0' for t in thermal),'AP/thermal coverage')
    samples=[]
    for e in events:
        if e.get('kind')!='power_sample':continue
        c.require(e['snapshot_start_ns']<=e['sensor_read_end_ns']<=e['state_snapshot_ns']<=e['mono_ns'] and
                  e['sensor_read_end_ns']-e['snapshot_start_ns']<=2e9,'sensor clock bracket')
        s=dict(e);s['mono_ns']=(e['snapshot_start_ns']+e['sensor_read_end_ns'])//2;samples.append(s)
    begin=boundary['start_ns'];end=boundary['planned_end_ns']
    c.require(energy.integrate(samples,begin,end,1000)['full_energy_j'] is not None,'common energy coverage')
    ap=[t for t in thermal if begin<=t['mono_ns']<=end and t['AP']!='']
    c.require(len(ap)>=2 and max([ap[0]['mono_ns']-begin,end-ap[-1]['mono_ns']]+[
        b['mono_ns']-a['mono_ns'] for a,b in zip(ap,ap[1:])])<=10e9,'common AP coverage')
    return dict(status='eligible_descriptive_only',phase=manifest['phase'],policy=manifest['policy'],
                scenario=manifest['scenario'],requests=24,warmup=8,runtimes=4,
                common_start_ns=boundary['start_ns'],common_end_ns=boundary['end_ns'],
                common_unfinished=sum(r.get('terminal_status')!='succeeded' or r.get('persist_complete_ns',10**30)>boundary['end_ns'] for r in boundary['rows']),
                terminal_completed=24,device_thermal_samples=len(thermal),
                scope='observed fixed trace; no energy saving/thermal model/independent policy PASS')


def run(plan_file,adb,serial,expected_sha,approved):
    c.require(approved and p.digest(plan_file)==expected_sha,'explicit later approval and exact plan hash required')
    plan=p.read(plan_file)
    single=plan.get('single_arrival_confirmation',False) or plan.get('recorded_replay_confirmation',False)
    if plan.get('recorded_replay_confirmation'):
        from tools import d1_arrival_recorded_replay as confirmation
        confirmation.check(plan_file)
    elif single:
        from tools import d1_arrival_ap_confirmation as confirmation
        confirmation.check(plan_file)
    else:c.check(plan_file)
    budget=plan['budget']
    root=Path(plan['output_root']);registry=Path(plan['registry'])
    registry.mkdir(parents=True,exist_ok=False);root.mkdir(parents=True,exist_ok=False)
    start=time.monotonic();hard=start+budget['total_seconds']
    write(registry/'claimed.json',dict(utc=legacy.utc(),plan_sha256=expected_sha,budget=budget))
    d=ObservedDevice(adb,serial,root/'host_commands');d.deadline=hard
    if single:d.command_limit=budget['adb_commands']
    complete=[];current=None;remote=None;identified=False;installation=None
    cleanup_attempted=False;cleanup_result=None
    try:
        (root/'installation').mkdir()
        installation=energy_device.installation(d,plan,plan_file,root/'installation',hard);identified=True
        for entry in plan['entries']:
            if not single and entry['index']==6:
                freeze_start=time.monotonic()
                c.require(len(complete)==6 and all(x['status']=='eligible_descriptive_only' for x in complete),'development eligibility')
                write(root/'development_freeze.json',dict(plan_sha256=expected_sha,
                    development=[dict(phase=x['phase'],scenario=x['scenario'],policy=x['policy'],
                                      session_sha256=p.digest(root/f"{i:02d}_{plan['entries'][i]['session_id']}"/'validated.json')) for i,x in enumerate(complete)],
                    policy_selection='none',model_fit='none',analysis_rule=plan['confirmation_rule']))
                write(root/'freeze_receipt.json',dict(sha256=p.digest(root/'development_freeze.json'),utc=legacy.utc()))
                c.require(time.monotonic()-freeze_start<=budget['freeze_seconds'],'freeze time')
            if entry['index']:
                c.require(hard-time.monotonic()>=budget['intersession_cooling_seconds']+budget['session_seconds'],'cooldown/session reserve')
                until=time.monotonic()+budget['intersession_cooling_seconds']
                while time.monotonic()<until:time.sleep(min(1,until-time.monotonic()))
            c.require(hard-time.monotonic()>=budget['session_seconds'],'whole session reserve')
            current=root/f"{entry['index']:02d}_{entry['session_id']}";current.mkdir();remote=None
            cleanup_attempted=False;cleanup_result=None
            session_start=time.monotonic();session_end=min(hard,session_start+budget['session_seconds'])
            d.deadline=min(session_start+budget['stage_gate_seconds'],session_end-580)
            energy_device.gates(d,plan,current,'before_session')
            c.require(install.installed_hash(d,plan['apk_preflight']['candidate'])==plan['apk_sha256'],'installed APK changed')
            write(current/'attempt.json',dict(entry=entry,utc=legacy.utc(),plan_sha256=expected_sha))
            manifest_file=Path(plan_file).parent/entry['manifest'];manifest=p.read(manifest_file)
            (current/'input_manifest.json').write_bytes(manifest_file.read_bytes())
            remote=shared.stage_inputs(d,entry['session_id'],manifest_file,
                                       {k:v['path'] for k,v in plan['source_files'].items()},c.PROTOCOL)
            c.require(session_end-time.monotonic()>=580,'poll/recovery/cleanup reserve')
            d.deadline=session_end-95
            write(current/'launch_attempt.json',dict(utc=legacy.utc()))
            d.call('shell','am','start','-W','-n',legacy.PACKAGE+'/'+ACTIVITY,'-a',ACTION,
                   '--es','session_id',entry['session_id'],timeout=20)
            poll(d,remote,current,manifest,plan)
            d.deadline=min(session_end-45,time.monotonic()+budget['recovery_seconds'])
            write(current/'recovery.json',energy_device.recover(d,remote,current/'artifacts'))
            cleanup_attempted=True
            try:
                cleanup_result=shared.cleanup(d,session_end)
            except BaseException as error:
                cleanup_result=dict(error=repr(error),status='failed_or_unknown')
                try:write(current/'host_cleanup_error.json',cleanup_result)
                except BaseException as recording_error:
                    cleanup_result['recording_error']=repr(recording_error)
                raise
            write(current/'host_cleanup.json',cleanup_result)
            stats=validate(current,manifest,plan)
            c.require(time.monotonic()<=session_end,'session exceeded reserve; no next session')
            stats['elapsed_seconds']=time.monotonic()-session_start
            write(current/'validated.json',stats);complete.append(stats)
        if not single:c.require(p.digest(root/'development_freeze.json')==p.read(root/'freeze_receipt.json')['sha256'],'freeze changed')
        outcome=dict(status='completed_descriptive_only',sessions=len(complete),requests=24*len(complete),warmup=8*len(complete),
                     runtime_creations=4*len(complete),adb_commands=d.sequence,elapsed_seconds=time.monotonic()-start,
                     installation=installation,experiment_ready=False)
        write(root/'FINAL_RECEIPT.json',outcome);write(registry/'completed.json',outcome);return outcome
    except BaseException as exc:
        failure=dict(status='stopped_no_resume',error=repr(exc),completed_sessions=len(complete),
                     session_attempts=len(list(root.glob('*/attempt.json'))),
                     launch_attempts=len(list(root.glob('*/launch_attempt.json'))),
                     consumption='confirmed durable event starts/returns only; missing calls remain unknown',
                     installation=installation,experiment_ready=False)
        if identified and remote and current:
            d.deadline=min(hard-45,time.monotonic()+15)
            for name in ('manifest.json','progress.jsonl','cleanup.json','sampler_failure.json','session_failure.json','common_boundary.json','requests.json'):
                try:energy_device.pull_file(d,remote,name,current/'failure_prefix')
                except BaseException as error:write(current/(name+'.recovery_error.json'),dict(error=repr(error)))
        if identified:
            if cleanup_attempted:
                failure['host_cleanup']=cleanup_result or dict(status='unknown_after_attempt')
            else:
                cleanup_attempted=True
                try:
                    cleanup_result=shared.cleanup(d,hard)
                    write((current or root)/'failure_host_cleanup.json',cleanup_result)
                except BaseException as error:failure['host_cleanup_error']=repr(error)
        prefix=current/'failure_prefix/progress.jsonl' if current else None
        records,partial=c.old.progress_prefix(prefix.read_bytes() if prefix and prefix.is_file() else b'')
        failure['last_session_progress']=dict(valid_records=len(records),partial_lines=partial,
            last_event=records[-1] if records else None,
            counts={kind:sum(e.get('kind')==kind for e in records) for kind in
                    ('runtime_start','runtime_return','warmup_start','warmup_return','request_start','output_ready','persist_complete','lane_available')},
            missing_not_zero=True)
        failure['elapsed_seconds']=time.monotonic()-start
        write(root/'FINAL_RECEIPT.json',failure);write(registry/'stopped.json',failure)
        raise
