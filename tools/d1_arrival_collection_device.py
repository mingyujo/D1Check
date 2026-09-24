"""Explicitly approved collection runner. Shared bounded ADB/gates/pull/cleanup.
No resume: claim each phase before preflight; any failure closes the entire plan.
"""
from pathlib import Path
import re
import time
from tools import d1_arrival_collection as c
from tools import d1_arrival_device as legacy
from tools import d1_arrival_timing_calibration_device as shared
from tools import d1_apk_identity as apk
from tools import d1_arrival_failure_evidence as evidence


def claim(plan_path, phase, freeze):
    plan=c.p.read(plan_path);registry=Path(plan['registry']);out=Path(plan['output_root'])/phase
    c.v.require(not (registry/'stopped.json').exists() and not (registry/f'{phase}_consumed.json').exists() and not out.exists(), 'consumed/stopped; no resume')
    if phase=='confirmation':
        c.v.require(freeze is not None and (registry/'development_complete.json').is_file(),'development and freeze required')
        f=c.p.read(freeze)
        # Re-derive the descriptive freeze from immutable development only; a made-up acceptance or confirmation refit cannot unlock.
        c.v.require(f==c.summarize(plan_path,'development'),'freeze rules/data mismatch')
        for name,digest in f['input_hashes'].items():c.v.require(c.p.digest(name)==digest,'development changed')
    registry.mkdir(parents=True,exist_ok=True)
    c.cal.write_new(registry/f'{phase}_consumed.json',dict(plan_sha256=c.p.digest(plan_path),output=str(out),
        freeze_sha256=c.p.digest(freeze) if freeze else None,utc=legacy.utc(),status='claimed_no_retry'))
    out.mkdir(parents=True)
    return plan,registry,out


def run(plan_path,phase,adb,serial,approved_cap,expected_sha,freeze=None,overall_deadline=None):
    c.v.require(phase in ('development','confirmation') and approved_cap==12 and c.p.digest(plan_path)==expected_sha,'explicit approval budget/plan')
    c.check(plan_path)
    prepared=c.p.read(plan_path)
    recovery_only=prepared.get('installation_contract')=='recovery-verified-only-v1'
    if recovery_only:
        c.v.require(overall_deadline is not None and
                    (Path(prepared['workflow_root'])/'claim.json').is_file() and
                    not (Path(prepared['workflow_root'])/'stopped.json').exists(),
                    'recovery collection requires active bounded bundle; direct phase run prohibited')
        from tools.d1_collection_recovery import require_receipt
        require_receipt(prepared,expected_sha)
    plan,registry,out=claim(plan_path,phase,freeze)
    started=time.monotonic();work_end=started+plan['host_phase_wall_seconds'];hard_end=work_end+45
    if overall_deadline is not None:
        hard_end=min(hard_end,overall_deadline);work_end=min(work_end,hard_end-45)
    device=legacy.Device(adb,serial);device.deadline=work_end-10
    completed=0;identified=False;current=None;pid=None;stage='signature_preflight'
    try:
        pre=apk.preflight(device,dict(plan,_plan_file=str(plan_path)),out/'preflight')
        identified=True
        identity=pre['device']
        # Gates before installation; no wake/unlock/settings write and no clear/uninstall.
        legacy.require_stopped(device)
        battery=device.call('shell','dumpsys','battery').stdout.decode();legacy.battery_gate(plan,battery,True)
        (out/'before_install_battery.txt').write_text(battery,encoding='utf-8')
        thermal=device.call('shell','dumpsys','thermalservice').stdout
        (out/'before_install_thermal.txt').write_bytes(thermal)
        c.v.require(re.search(rb'Thermal Status:\s*0\b',thermal),'thermal pre-install')
        shared.screen_snapshot(device,out,'before_install',plan['screen_contract'],settings=True)
        c.v.require(device.deadline-time.monotonic()>=120+120+165,'insufficient install/cool/launch/poll/recovery budget')
        if recovery_only:
            c.v.require(pre['installed']==pre['candidate'],'exact installed APK gate; collection cannot install')
            c.cal.write_new(out/'installation_gate.json',dict(status='exact_installed_no_install',
                recovery_receipt_sha256=c.p.digest(plan['recovery_receipt']),identity=pre['installed']))
        else:
            stage='install';c.cal.write_new(out/'install_attempt.json',dict(utc=legacy.utc(),apk_sha256=plan['apk_sha256']))
            installed=device.call('install','-r',plan['apk_path'],timeout=120)
            c.cal.write_new(out/'install_result.json',dict(status='installed',stdout=installed.stdout.decode(errors='replace')))
            apk.preflight(device,dict(plan,_plan_file=str(plan_path)),out/'post_install_identity')
        shared.legacy.bounded_cool(device,plan['initial_cool_seconds'])
        entries=[e for e in plan['entries'] if e['phase']==phase]
        for position,e in enumerate(entries):
            current=out/f"{e['index']:02d}_{e['session_id']}";current.mkdir();pid=None;stage='gate'
            c.cal.write_new(current/'attempt.json',dict(entry=e,utc=legacy.utc(),plan_sha256=expected_sha,device=identity))
            if e['condition'].endswith('lanes'):
                c.v.require(completed==5 and all((out/f"{a['index']:02d}_{a['session_id']}"/'validated.json').is_file() for a in entries[:5]), 'parallel stage prerequisites')
            device.identify(plan['device_fingerprint']);legacy.require_stopped(device)
            battery=device.call('shell','dumpsys','battery').stdout.decode();(current/'before_battery.txt').write_text(battery,encoding='utf-8')
            legacy.battery_gate(plan,battery,position==0)
            thermal=device.call('shell','dumpsys','thermalservice').stdout;(current/'before_thermal.txt').write_bytes(thermal)
            c.v.require(re.search(rb'Thermal Status:\s*0\b',thermal),'thermal gate')
            (current/'before_memory.txt').write_bytes(device.call('shell','cat','/proc/meminfo').stdout)
            shared.awake_gate(device,plan,current)
            c.v.require(device.deadline-time.monotonic()>=165,'reserve launch30/poll125/recovery10')
            manifest=Path(plan_path).parent/e['manifest'];stage='stage_inputs'
            remote=shared.stage_inputs(device,e['session_id'],manifest,{k:v['path'] for k,v in plan['source_files'].items()},c.PROTOCOL)
            c.v.require(device.deadline-time.monotonic()>=165,'post-staging launch reserve')
            stage='launch';c.cal.write_new(current/'launch_attempt.json',dict(utc=legacy.utc(),session_id=e['session_id']))
            launch=device.call('shell','am','start','-W','-n',legacy.PACKAGE+'/'+legacy.ACTIVITY,'-a',legacy.ACTION,'--es','session_id',e['session_id'],timeout=30)
            (current/'launch_stdout.txt').write_bytes(launch.stdout)
            pid=device.call('shell','pidof',legacy.PACKAGE+':model_probe').stdout.decode().strip()
            c.v.require(re.fullmatch(r'\d+',pid),'process PID missing')
            stage='poll';previous=device.deadline;device.deadline=min(previous,time.monotonic()+125)
            try:shared.wait_for_cleanup(device,remote,125,plan['screen_contract'],current)
            finally:device.deadline=previous
            stage='recovery';recovery=shared.pull(device,e['session_id'],current/'artifacts',c.PROTOCOL)
            shared.screen_snapshot(device,current,'after_recovery',plan['screen_contract'],settings=True)
            stage='validation';artifacts=current/'artifacts'
            c.v.require(c.p.digest(artifacts/'manifest.json')==e['manifest_sha256'],'manifest changed')
            validated=c.validate_artifacts(artifacts,c.p.read(plan['source_files']['collection_estimates.json']['path']))
            summary,rows,env=(c.p.read(artifacts/(n+'.json')) for n in ('summary','requests','environment'))
            legacy.quality_gate(summary,rows,env)
            for row in rows:
                shared.backend_gate(row,row['selected_backend'])
                c.v.require(c.p.digest(artifacts/f"{row['request_id']}.result.json")==row['result_sha256'],'result hash')
            logs=device.call('logcat','-d','-v','threadtime','--pid='+pid,'-s','D1ARRIVAL:I','tflite:I').stdout
            (current/'delegate_log.txt').write_bytes(logs)
            proof=legacy.delegate_proof(c.p.read(manifest),logs.decode(errors='replace'))
            c.cal.write_new(current/'validated.json',dict(status='valid',recovery=recovery,gpu=proof,collection=validated))
            c.cal.write_new(current/'host_cleanup.json',shared.cleanup(device,hard_end));device.deadline=work_end-10
            completed+=1
            if position<len(entries)-1:legacy.bounded_cool(device,plan['cool_down_seconds'])
        result=dict(status='completed',phase=phase,plan_sha256=expected_sha,sessions=completed,requests=completed*4,warmup=completed*8,
                    host_elapsed_seconds=time.monotonic()-started,experiment_ready=False)
        c.cal.write_new(out/'complete.json',result);c.cal.write_new(registry/f'{phase}_complete.json',result)
        return result
    except BaseException as error:
        # At most 10 seconds for partial evidence, then the remaining hard cleanup budget.
        failure=dict(status='stopped_no_retry',stage=stage,error=repr(error),utc=legacy.utc(),completed=completed,
                     attempts=len(list(out.glob('*/attempt.json'))),launch_attempts=len(list(out.glob('*/launch_attempt.json'))),
                     install_attempts=int((out/'install_attempt.json').exists()),requests_actual='unknown unless artifacts prove count',
                     plan_sha256=expected_sha,app_failure='unknown unless app evidence confirms')
        c.cal.write_new(out/'stopped.json',failure);c.cal.write_new(registry/'stopped.json',failure)
        if current and identified:
            device.deadline=min(work_end,time.monotonic()+10)
            for label,operation in [('partial_recovery',lambda:shared.pull(device,c.p.read(current/'attempt.json')['entry']['session_id'],current/'artifacts',c.PROTOCOL)),
                                    ('process_evidence',lambda:evidence.collect_failure(device,current/'host_evidence',pid))]:
                try:c.cal.write_new(current/(label+'.json'),operation())
                except BaseException as exc:c.cal.write_new(current/(label+'_error.json'),dict(error=repr(exc)))
        if identified:
            try:c.cal.write_new((current or out)/'failure_host_cleanup.json',shared.cleanup(device,hard_end))
            except BaseException as exc:c.cal.write_new((current or out)/'failure_cleanup_error.json',dict(error=repr(exc)))
        raise
