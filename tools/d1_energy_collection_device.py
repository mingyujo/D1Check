"""One approved bundle only. Imported only by explicit run. No recovery/retry loop."""
from pathlib import Path
import io
import json
import os
import re
import statistics
import tarfile
import time
import traceback
import threading
from tools import d1_energy_collection as c
from tools import d1_arrival_device as legacy
from tools import d1_arrival_timing_calibration_device as shared
from tools import d1_apk_identity as apk
from tools import d1_collection_recovery as install
from tools import d1_logger_v4 as logger
from tools.d1_adb_observed_client import ObservedDevice
from tools import d1_energy_host_checkpoints as checkpoints
from tools import d1_energy_host_lifecycle as lifecycle
from tools import d1_energy_screen as screen
from tools import d1_energy_temperature as temperature

ACTIVITY='com.example.d1check.benchmarkrunner.EnergyCollectionActivity'
ACTION='com.example.d1check.benchmarkrunner.action.ENERGY_COLLECTION'

def save(path,value):c.cal.write_new(Path(path),value)

def pull_file(d,remote,name,folder):
    c.require(re.fullmatch(r'[A-Za-z0-9._-]+',name),'unsafe file')
    result=d.call('exec-out','run-as',legacy.PACKAGE,'cat',remote+'/'+name,timeout=10)
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    target=folder/name
    if name.endswith('.json'):
        try:json.loads(result.stdout)
        except (ValueError,UnicodeError):
            (folder/(name+'.invalid.bin')).write_bytes(result.stdout)
            raise ValueError('artifact retrieval returned non-JSON: '+name)
    if target.exists():c.require(target.read_bytes()==result.stdout,'output conflict')
    else:target.write_bytes(result.stdout)
    return target

def recover(d,remote,folder,best_effort_prefix=False):
    """Identity/progress first, then one bounded archive command; no per-file870-call loop."""
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    # Partial progress can change until shutdown: preserve this snapshot separately.
    prefix=folder.parent/'recovery_prefix';prefix.mkdir(exist_ok=True)
    prefix_errors=[]
    for name in ('manifest.json','progress.jsonl','cleanup.json'):
        try:pull_file(d,remote,name,prefix)
        except Exception as exc:
            if not best_effort_prefix:raise
            error=dict(file=name,error=repr(exc),role='recovery_failure_not_app_completion')
            save(prefix/(name+'.recovery_error.json'),error);prefix_errors.append(error)
    # The ObservedDevice deadline still bounds the entire recovery. Missing cleanup
    # must not suppress the single archive attempt; it never implies app success.
    raw=d.call('exec-out','run-as',legacy.PACKAGE,'tar','-cf','-','-C',remote,'.',timeout=35).stdout
    (folder.parent/'artifacts.tar').write_bytes(raw)
    with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
        for item in archive:
            if item.isdir():continue
            name=item.name.removeprefix('./')
            c.require(item.isfile() and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,126}',name),'unsafe archive entry')
            c.require(item.size<=(64_000_000 if name=='progress.jsonl' else 4_000_000),'artifact size bound')
            data=archive.extractfile(item).read();target=folder/name
            c.require(not target.exists(),'duplicate archive member');target.write_bytes(data)
    return dict(status='recovered_with_prefix_errors' if prefix_errors else 'recovered',
                prefix_errors=prefix_errors,files=len(list(folder.iterdir())),archive_sha256=c.p.digest(folder.parent/'artifacts.tar'))

def thermal(d,folder,index):
    before=logger.parse_uptime(d.call('exec-out','cat','/proc/uptime',timeout=2).stdout.decode())
    raw=d.call('shell','dumpsys','thermalservice',timeout=2).stdout.decode()
    after=logger.parse_uptime(d.call('exec-out','cat','/proc/uptime',timeout=2).stdout.decode())
    c.require(after>=before and after-before<=4e9,'thermal bracket clock')
    values=logger.parse_thermalservice(raw)
    c.require(values['thermal_status']=='0','host thermal gate')
    values.update(mono_ns=(before+after)//2,sampling_uncertainty_ns=(after-before)//2,
        before_ns=before,after_ns=after,host_monotonic=time.monotonic(),raw=raw,index=index)
    with (Path(folder)/'thermal.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(values)+'\n');f.flush()
    return values

def gpu_proof(text,sid):
    lines=text.splitlines();starts=[i for i,l in enumerate(lines) if 'runtime_scope_start='+sid in l]
    ends=[i for i,l in enumerate(lines) if 'runtime_scope_end='+sid in l]
    c.require(len(starts)==len(ends)==1 and starts[0]<ends[0],'runtime GPU evidence scope')
    pid=lines[starts[0]].split()[2]
    scoped='\n'.join(l for l in lines[starts[0]:ends[0]+1] if len(l.split())>2 and l.split()[2]==pid)
    replacements=re.findall(r'Replacing (\d+) out of (\d+) node\(s\) with delegate \(TfLiteGpuDelegateV2\)',scoped)
    kernels=re.findall(r'Created (\d+) GPU delegate kernels',scoped)
    c.require(len(replacements)==len(kernels)==2 and all(int(a)>0 and a==b for a,b in replacements) and all(int(k)>0 for k in kernels),'both GPU runtimes not fully evidenced')
    c.require(not re.search(r'fallback|failed|unsupported op|restor\w*.*plan',scoped,re.I),'GPU failure/fallback')
    return dict(status='full_delegate_evidence',instances=2,evidence='runtime log, not GPU kernel overlap')

def arm(d,remote_input,name,sha):
    # Fixed safe hash and path from manifest; no shell interpolation of user text.
    c.require(re.fullmatch('[a-f0-9]{64}',sha),'arm hash')
    d.call('shell','run-as',legacy.PACKAGE,'sh','-c',f'"echo {sha} > {remote_input}/{name}.arm"',timeout=5)

def same_stage_serial_anchor(results, phase, pair, mode):
    if mode=='serial':return None
    matches=[r for r in results if r['phase']==phase and r['condition']==pair+'_serial' and
             r['status']=='eligible_descriptive_only']
    c.require(len(matches)==1,'one eligible same-stage serial anchor required')
    return matches[0]['phases']['resident_baseline']['ap_median_c']

def poll(d,remote,folder,m,plan,baseline_anchor=None,checkpoint=None,
         diagnostic_stop_after_preparation=False):
    autonomous=m.get('session_control')=='device-after-probe-diagnostic-v1'
    c.require(not autonomous or (plan.get('autonomous_diagnostic_only') and
              m.get('autonomous_diagnostic_only') and plan.get('diagnostic_only') and
              not plan.get('state_model_followup')), 'autonomous segment requires isolated diagnostic plan')
    conditioned=plan.get('temperature_preparation') is not None
    operational=plan.get('operational_only',False)
    start=time.monotonic();end=min(d.deadline,start+plan['budget']['host_poll_seconds'])
    armed=set();index=0;last_thermal=last_screen=0;last_sensor=None;heartbeat_index=-1
    observations=[];probe_ready=None;probe_verified=False;last_checkpoint=start;preparation_marked=False
    while time.monotonic()<end:
        now=time.monotonic()
        if checkpoint and now-last_checkpoint>=30:
            checkpoint('poll_alive',session_id=m['session_id'],armed=sorted(armed))
            last_checkpoint=now
        if now-last_thermal>=2:
            last_sensor=thermal(d,folder,index);observations.append(last_sensor);index+=1;last_thermal=time.monotonic()
        if now-last_screen>=10:
            screen.snapshot(d,folder,f'poll_{index:04d}',plan['screen_contract']);last_screen=time.monotonic()
        listing=d.call('shell','run-as',legacy.PACKAGE,'ls',remote,timeout=3).stdout.decode().splitlines()
        if 'cleanup.json' in listing:return
        if time.monotonic()-start>15 and index%5==0 and index!=heartbeat_index:
            line=d.call('exec-out','run-as',legacy.PACKAGE,'tail','-n','1',remote+'/progress.jsonl',timeout=3).stdout
            heartbeat=json.loads(line)
            save(Path(folder)/f'heartbeat_{index:04d}.json',heartbeat)
            heartbeat_index=index
            c.require(heartbeat['session_id']==m['session_id'] and last_sensor['after_ns']-heartbeat['mono_ns']<15e9,'progress heartbeat stale; stop, no retry')
        for gate in (('warmup','serial_probe','probe','baseline') if operational else ('warmup','probe','baseline')):
            if gate in armed or gate+'.ready.json' not in listing:continue
            target=Path(folder)/('gate_'+gate)
            ready=(probe_ready if gate=='probe' and probe_verified else
                   c.p.read(pull_file(d,remote,gate+'.ready.json',target)))
            c.require(ready['manifest_sha256']==c.p.digest(Path(folder)/'input_manifest.json'),'gate manifest')
            if gate=='warmup':
                rows=c.p.read(pull_file(d,remote,'warmup.json',target));c.require(len(rows)==8,'warmup budget')
                c.require(all(sum(x['key']==k for x in rows)==2 for k in c.KEYS),'warmup coverage')
                for r in rows:c.quality(c.p.read(plan['references'][r['key']]['path']),r['result'])
                pid=d.call('shell','pidof',legacy.PACKAGE+':model_probe',timeout=3).stdout.decode().strip()
                c.require(re.fullmatch(r'\d+',pid),'single process')
                logs=d.call('logcat','-d','-v','threadtime','--pid='+pid,'-s','D1ENERGY:I','tflite:I',timeout=5).stdout
                (target/'delegate_log.txt').write_bytes(logs);save(target/'gpu.json',gpu_proof(logs.decode(errors='replace'),m['session_id']))
            elif gate in ('serial_probe','probe'):
                c.require('warmup' in armed,'probe before warmup gate')
                if operational and gate=='probe':c.require('serial_probe' in armed,'parallel before serial technical evidence')
                if not probe_verified:
                    rows=[]
                    specs=([('eligibility_serial_probe','serial')] if gate=='serial_probe' else
                           c.operational_rules.probe_specs(operational,m['mode']))
                    for label,mode in specs:
                        rr=c.p.read(pull_file(d,remote,label+'.requests.json',target))
                        c.validate_rows(rr,m['pair'],mode,[1,1]);rows.extend(rr)
                    for row in rows:
                        result=c.p.read(pull_file(d,remote,row['id']+'.result.json',target))
                        c.quality(c.p.read(plan['references'][row['key']]['path']),result)
                    if gate=='probe':probe_verified=True;probe_ready=ready
                if conditioned and gate=='probe':
                    if checkpoint and not preparation_marked:
                        checkpoint('temperature_preparation_waiting',session_id=m['session_id'])
                        preparation_marked=True
                    contract=plan['temperature_preparation']
                    assessment=(c.operational_rules.assess(observations,ready['mono_ns'],contract) if operational else
                                temperature.assess(observations,ready['mono_ns'],baseline_anchor,contract))
                    waited_s=(last_sensor['mono_ns']-ready['mono_ns'])/1e9
                    if not assessment['ready']:
                        if assessment['reason']=='invalid_sensor_or_thermal':
                            save(target/'temperature_preparation_failure.json',dict(
                                status='invalid_sensor_before_official_baseline',waited_seconds=waited_s,
                                assessment=assessment,anchor_c=baseline_anchor))
                            raise ValueError('resident AP observation invalid; no baseline or load arm')
                        if temperature.expired(last_sensor['mono_ns'],ready['mono_ns'],contract):
                            save(target/'temperature_preparation_failure.json',dict(
                                status='timed_out_before_official_baseline',waited_seconds=waited_s,
                                assessment=assessment,anchor_c=baseline_anchor))
                            raise TimeoutError('resident AP preparation timeout; no baseline or load arm')
                        continue
                    save(target/'temperature_preparation.json',dict(status='ready_before_one_official_baseline',
                        waited_seconds=waited_s,assessment=assessment,anchor_c=baseline_anchor))
                    if checkpoint:checkpoint('temperature_preparation_ready',session_id=m['session_id'])
                    if diagnostic_stop_after_preparation:
                        # The installed APK has no normal pre-baseline exit command.
                        # Leave probe unarmed; caller performs one host stop. Never
                        # claim app cleanup or a completed collection session.
                        return dict(status='preparation_observed_host_stop_required',
                                    assessment=assessment,probe_armed=False)
            else:
                c.require('probe' in armed,'baseline before eligibility gate')
                progress=pull_file(d,remote,'progress.jsonl',target)
                events,incomplete=c.progress_prefix(progress.read_bytes())
                bounds=[r['mono_ns'] for r in events if r['phase']=='resident_baseline' and r['kind'] in ('phase_start','phase_end')]
                c.require(len(bounds)==2,'resident baseline boundaries not durable')
                readings=[json.loads(line) for line in (Path(folder)/'thermal.jsonl').read_text(encoding='utf-8').splitlines()]
                values=[float(r['AP']) for r in readings if bounds[0]<=r['mono_ns']<=bounds[1] and r['AP']!='']
                c.require(len(values)>=20,'baseline AP not observed')
                median=statistics.median(values)
                if baseline_anchor is not None:c.require(abs(median-baseline_anchor)<=.5,'paired baseline AP mismatch; no extra cooling/retry')
                save(target/'baseline.json',dict(ap_median_c=median,anchor_c=baseline_anchor,
                    tolerance_c=None if operational else .5,unit='degC',
                    role='recorded initial covariate; no thermal equivalence claim' if operational else 'environment matching not effect margin'))
            if autonomous and gate=='baseline':
                # Observe the single official baseline when ADB is available, but
                # the app has already continued. Never imply this was an arm gate.
                save(target/'observation_receipt.json',dict(gate=gate,utc=legacy.utc(),
                    meaning='posthoc_only_not_a_host_arm'))
                armed.add(gate)
                continue
            if autonomous and gate=='probe':
                # Ambiguous delivery must be treated as potentially active. The
                # failure path will not force-stop this bounded device segment.
                save(Path(folder)/'autonomous_segment_arm_intent.json',dict(
                    session_id=m['session_id'],utc=legacy.utc(),manifest_sha256=ready['manifest_sha256']))
            arm(d,'files/arrival-scheduler-inputs/'+m['session_id'],gate,ready['manifest_sha256'])
            save(target/'arm_receipt.json',dict(gate=gate,utc=legacy.utc(),manifest_sha256=ready['manifest_sha256']))
            armed.add(gate)
            if checkpoint:checkpoint('gate_armed',session_id=m['session_id'],gate=gate)
        time.sleep(1 if diagnostic_stop_after_preparation else .25)
    raise TimeoutError('host completion bound; do not infer zero calls')

def gates(d,plan,folder,label):
    identity=d.identify(plan['device_fingerprint'])
    hardware=d.call('shell','getprop','ro.serialno',timeout=3).stdout.decode().strip()
    c.require(hardware==plan['device_hardware_serial'],'hardware serial')
    legacy.require_stopped(d)
    battery=d.call('shell','dumpsys','battery',timeout=5).stdout.decode()
    (Path(folder)/(label+'_battery.txt')).write_text(battery,encoding='utf-8');legacy.battery_gate(plan,battery,True)
    thermal(d,folder,0)
    screen.snapshot(d,folder,label,plan['screen_contract'],settings=True)
    (Path(folder)/(label+'_memory.txt')).write_bytes(d.call('shell','cat','/proc/meminfo',timeout=3).stdout)
    save(Path(folder)/(label+'_identity.json'),identity)
    return identity

def installation(d,plan,plan_file,root,hard):
    start=time.monotonic();end=min(start+600,hard);d.deadline=end-45
    state=dict(status='failed',apk_transfer_attempts=0,install_attempts=0)
    identified=False
    try:
        # preflight proves model/fingerprint before any modifying command.
        pre=apk.preflight(d,dict(plan,_plan_file=str(plan_file)),root/'preflight');identified=True
        gates(d,plan,root,'install_gate')
        if pre['installed']!=pre['candidate']:
            c.require(end-time.monotonic()>=330,'transfer/install/identity/cleanup reserve')
            remote='/data/local/tmp/d1check-'+plan.get('experiment_id',c.EXPERIMENT).lower()+'.apk'
            probe=d.call('shell','test','-e',remote,check=False,timeout=3)
            c.require(probe.returncode==1 and not probe.stderr.strip(),'remote install output already exists')
            state['apk_transfer_attempts']=1;save(root/'apk_transfer_attempt.json',dict(utc=legacy.utc()))
            d.call('push',plan['apk_path'],remote,timeout=plan['budget'].get('apk_push_timeout_seconds',120))
            actual=d.call('shell','sha256sum',remote,timeout=5).stdout.decode().split()[0]
            c.require(actual==plan['apk_sha256'],'remote APK hash');save(root/'apk_transferred.json',dict(sha256=actual))
            state['install_attempts']=1;save(root/'install_attempt.json',dict(utc=legacy.utc()))
            response=d.call('shell','pm','install','-r',remote,timeout=120)
            c.require(re.search(rb'(?m)^Success\s*$',response.stdout),'installation not confirmed')
        state['installed_sha256']=install.installed_hash(d,pre['candidate'])
        c.require(state['installed_sha256']==plan['apk_sha256'],'exact installed APK required')
        state['status']='verified'
    finally:
        if identified:
            try:state['cleanup']=shared.cleanup(d,end)
            except BaseException as exc:state.update(status='failed',cleanup={'error':repr(exc)})
        state['elapsed_seconds']=time.monotonic()-start;save(root/'installation_receipt.json',state)
    c.require(state['status']=='verified','installation failed; no sessions')
    return state

def installed_preflight(d,plan,plan_file,root,hard):
    """Read the current installed APK once; never transfer or install an APK."""
    start=time.monotonic();end=min(start+plan['budget']['installed_preflight_seconds'],hard)
    d.deadline=end-45
    state=dict(status='failed',apk_transfer_attempts=0,install_attempts=0,
               installed_host_pull_limit=1,app_launch_attempts=0)
    try:
        pre=apk.preflight(d,dict(plan,_plan_file=str(plan_file)),root/'preflight')
        c.require(pre['installed']==pre['candidate'],'installed APK differs; no deploy fallback')
        gates(d,plan,root,'installed_gate')
        state['installed_sha256']=install.installed_hash(d,pre['candidate'])
        c.require(state['installed_sha256']==plan['apk_sha256'],'installed APK hash changed')
        state['status']='verified'
    except BaseException as exc:
        state['error']=repr(exc)
        raise
    finally:
        state['elapsed_seconds']=time.monotonic()-start
        state['cleanup']=dict(status='not_applicable_no_app_launch',
                              host_clients='recorded_per_command')
        save(root/'installed_preflight_receipt.json',state)
    return state

def run(plan_file,adb,serial,expected_sha,approved):
    c.require(approved and c.p.digest(plan_file)==expected_sha,'new explicit approval/hash required')
    try:plan=c.p.read(plan_file)
    except FileNotFoundError:
        c.check(plan_file)
        raise
    if plan.get('short_transition_diagnostic_only'):
        from tools import d1_energy_ap_short_transition as short_transition
        from tools import d1_energy_state_collection as state
        short_transition.check(plan_file)
        c.require(serial is None,'short transition selects the current transport itself')
    elif plan.get('autonomous_diagnostic_only'):
        from tools import d1_energy_ap_autonomous_diag as autonomous
        from tools import d1_energy_state_collection as state
        autonomous.check(plan_file)
        c.require(serial is None,'autonomous diagnostic selects the current transport itself')
    elif plan.get('state_model_followup'):
        from tools import d1_energy_state_collection as state
        from tools import d1_energy_ap_followup as followup
        followup.check(plan_file)
        c.require(serial is None,'new state followup selects the current transport itself')
    elif plan.get('state_model_calibration'):
        from tools import d1_energy_state_collection as state
        state.check(plan_file)
        c.require(serial is None,'new state plan selects the current transport itself')
    else:
        state=None;c.check(plan_file)
    root=Path(plan['output_root']);registry=Path(plan['registry'])
    # Single-use claim BEFORE any preflight/transfer. A failed gate does not allow silent resume.
    registry.mkdir(parents=True,exist_ok=False);root.mkdir(parents=True,exist_ok=False)
    budget=plan['budget']
    start=time.monotonic();hard=start+budget['total_seconds']
    state_model=bool(plan.get('state_model_calibration'))
    host_run_id=os.environ.get('D1_ENERGY_HOST_RUN_ID') or __import__('uuid').uuid4().hex
    host_identity=lifecycle.host_identity() if state_model else None
    save(registry/'claimed.json',dict(plan_sha256=expected_sha,utc=legacy.utc(),budget=budget,
                                      host_run_id=host_run_id,host_identity=host_identity))
    results=[];current=None;remote=None;identified=False;install_result=None;d=None;journal=None
    cleanup_attempted=False;cleanup_result=None
    def mark(stage,**details):
        if journal:journal.mark(stage,**details)
    try:
        if state_model:
            journal=checkpoints.Checkpoints(root/'host_checkpoints',expected_sha,host_run_id,host_identity)
            mark('claimed')
        d=(ObservedDevice(adb,serial,root/'host_commands',allow_select=True,
                          forbid_apk_deploy=not plan.get('autonomous_diagnostic_only',False))
           if state_model else ObservedDevice(adb,serial,root/'host_commands'))
        if state_model:d.command_limit=budget['pre_cleanup_command_slots']
        d.deadline=hard
        install_root=root/('installed_preflight' if state_model and not plan.get('autonomous_diagnostic_only') else 'installation');install_root.mkdir()
        mark('installed_preflight_start')
        install_result=(installation(d,plan,plan_file,install_root,hard)
                        if plan.get('autonomous_diagnostic_only') else
                        installed_preflight(d,plan,plan_file,install_root,hard) if state_model else
                        installation(d,plan,plan_file,install_root,hard));identified=True
        mark('installed_preflight_verified')
        frozen=None
        if plan.get('state_model_followup') or plan.get('short_transition_diagnostic_only'):
            # Preserve the exact development artifact. No re-fit, no confirmation-derived edits.
            source=Path(plan['prior_freeze']['path'])
            c.require(c.p.digest(source)==plan['prior_freeze']['sha256'],'prior freeze changed')
            (root/'development_freeze.json').write_bytes(source.read_bytes())
            save(root/'freeze_receipt.json',dict(sha256=plan['prior_freeze']['sha256'],
                source='COLLECT-05 development only',utc=legacy.utc()))
            frozen=c.p.read(root/'development_freeze.json')
            mark('prior_development_freeze_loaded',sha256=plan['prior_freeze']['sha256'])
        for e in plan['entries']:
            if e['index']==budget['development'] and not plan.get('diagnostic_only') and not plan.get('state_model_followup'):
                mark('development_freeze_start')
                freeze_start=time.monotonic();frozen={r['condition']:r for r in results}
                expected_status='eligible_regimen_only' if state else 'eligible_descriptive_only'
                c.require(len(frozen)==budget['development'] and all(r['status']==expected_status for r in results),'development freeze eligibility')
                if state:
                    frozen=state.freeze(results,plan,root)
                    artifact=frozen
                else:
                    artifact=dict(plan_sha256=expected_sha,conditions=frozen,source='development_only',accuracy_pass=None)
                save(root/'development_freeze.json',artifact)
                save(root/'freeze_receipt.json',dict(sha256=c.p.digest(root/'development_freeze.json'),utc=legacy.utc()))
                c.require(time.monotonic()-freeze_start<600,'freeze time exceeded')
                mark('development_frozen')
            c.require(hard-time.monotonic()>=budget['session_seconds'],'insufficient whole session reserve; stop')
            current=root/f"{e['index']:02d}_{e['session_id']}";current.mkdir();remote=None
            cleanup_attempted=False;cleanup_result=None
            mark('session_reserved',session_index=e['index'],session_id=e['session_id'],phase=e['phase'])
            session_start=time.monotonic();session_end=min(session_start+budget['session_seconds'],hard);d.deadline=min(session_start+120,session_end-105)
            gates(d,plan,current,'before_session')
            c.require(install.installed_hash(d,plan['apk_preflight']['candidate'])==plan['apk_sha256'],'installed APK changed')
            mark('session_gate_passed',session_index=e['index'],session_id=e['session_id'])
            if e['mode']=='parallel' and not plan.get('operational_only'):
                serial_key=e['pair']+'_serial'
                c.require(any(r['condition']==serial_key and r['status']=='eligible_descriptive_only' for r in results if r['phase']==e['phase']),'same-stage serial prerequisite')
            save(current/'attempt.json',dict(entry=e,utc=legacy.utc(),plan_sha256=expected_sha))
            manifest=Path(plan_file).parent/e['manifest'];m=c.p.read(manifest)
            c.require((m.get('session_control')=='device-after-probe-diagnostic-v1') ==
                      bool(plan.get('autonomous_diagnostic_only')), 'session-control/plan mismatch')
            (current/'input_manifest.json').write_bytes(manifest.read_bytes())
            remote=shared.stage_inputs(d,e['session_id'],manifest,{k:v['path'] for k,v in plan['source_files'].items()},plan.get('protocol',c.PROTOCOL))
            mark('inputs_staged',session_index=e['index'],session_id=e['session_id'])
            c.require(session_end-time.monotonic()>=budget['host_poll_seconds']+105,'launch reserve')
            d.deadline=session_end-105
            save(current/'launch_attempt.json',dict(utc=legacy.utc()))
            mark('launch_intent',session_index=e['index'],session_id=e['session_id'])
            d.call('shell','am','start','-W','-n',legacy.PACKAGE+'/'+ACTIVITY,'-a',ACTION,'--es','session_id',e['session_id'],timeout=20)
            mark('launch_returned',session_index=e['index'],session_id=e['session_id'])
            anchor=None if state or plan.get('operational_only') else same_stage_serial_anchor(results,e['phase'],e['pair'],e['mode'])
            poll(d,remote,current,m,plan,anchor,checkpoint=mark if state_model else None)
            mark('poll_completed',session_index=e['index'],session_id=e['session_id'])
            d.deadline=min(time.monotonic()+60,session_end-45)
            mark('recovery_start',session_index=e['index'],session_id=e['session_id'])
            save(current/'recovery.json',recover(d,remote,current/'artifacts',plan.get('operational_only',False)))
            # Cleanup is reserved BEFORE PC validation; validation cannot prolong active device work.
            mark('host_cleanup_start',session_index=e['index'],session_id=e['session_id'])
            cleanup_attempted=True
            cleanup_result=shared.cleanup(d,session_end)
            save(current/'host_cleanup.json',cleanup_result)
            mark('host_cleanup_returned',session_index=e['index'],session_id=e['session_id'])
            stats=(state.summarize_session if state else c.summarize_session)(current/'artifacts',manifest,plan);stats['phase']=e['phase']
            if plan.get('autonomous_diagnostic_only'):
                stats['formal_confirmation']=False
                stats['diagnostic_scope']=('short_transition_schedule_conditional_protocol_transfer_only'
                    if plan.get('short_transition_diagnostic_only') else
                    'device_segment_normal_completion_and_host_observation_coverage_only')
            c.require(time.monotonic()<=session_end,'session PC validation exhausted reservation; no next session')
            stats['elapsed_seconds']=time.monotonic()-session_start
            if frozen is not None:
                if state:
                    errors=state.evaluate(stats,frozen,plan)
                    if plan.get('short_transition_diagnostic_only'):
                        errors['meaning']='short-transition diagnostic on changed APK/protocol; not formal confirmation or arrival-policy validation'
                        errors['accuracy_pass']=None
                        stats['transition_errors']=errors
                    else: stats['confirmation_errors']=errors
                else:
                    fr=frozen[stats['condition']]
                    stats['confirmation_errors']={phase:dict(power_w=values['energy']['mean_power_w']-fr['phases'][phase]['energy']['mean_power_w'],
                        ap_end_c=values['ap_end_c']-fr['phases'][phase]['ap_end_c']) for phase,values in stats['phases'].items()}
                c.require(c.p.digest(root/'development_freeze.json')==c.p.read(root/'freeze_receipt.json')['sha256'],'freeze changed')
            save(current/'validated.json',stats);results.append(stats)
            mark('session_validated',session_index=e['index'],session_id=e['session_id'])
        result=dict(status='completed_short_transition_protocol_diagnostic_only' if plan.get('short_transition_diagnostic_only') else 'completed_followup_confirmation_only' if plan.get('state_model_followup') else 'completed_regimen_diagnostic_only' if state else 'completed_diagnostic_only' if plan.get('diagnostic_only') else 'completed_descriptive_only',
            sessions=len(results),diagnostic_requests=(sum(r['work_calls']+r['eligibility_calls'] for r in results) if state else budget['diagnostic_requests']),
            warmup=(sum(r['warmup_calls'] for r in results) if state else budget['warmup']),
            explicit_inference=(sum(r['work_calls']+r['eligibility_calls']+r['warmup_calls'] for r in results) if state else budget['explicit_inference']),
            installation=install_result if (not state_model or plan.get('autonomous_diagnostic_only')) else None,
            installed_preflight=install_result if (state_model and not plan.get('autonomous_diagnostic_only')) else None,
            elapsed_seconds=time.monotonic()-start,adb_command_slots=d.sequence,
            accuracy_pass=None,experiment_ready=False)
        mark('completion_receipt_intent')
        checkpoints.atomic_new(root/'FINAL_RECEIPT.json',result)
        checkpoints.atomic_new(registry/'completed.json',result)
        # Publication is already complete; a final checkpoint failure cannot
        # turn a completed run into a stopped run with conflicting receipts.
        try:mark('completed')
        except BaseException:pass
        return result
    except BaseException as exc:
        if state_model and d is not None:d.command_limit=budget['adb_command_slots']
        failure=dict(status='stopped_no_resume',error=repr(exc),completed_sessions=len(results),
            exception_type=type(exc).__name__,exception_stack=traceback.format_exc(),
            exception_thread=threading.current_thread().name,utc_failure=legacy.utc(),
            session_attempts=len(list(root.glob('*/attempt.json'))),launch_attempts=len(list(root.glob('*/launch_attempt.json'))),
            consumption='only durable start/return pairs confirm counts; absent logs remain unknown',elapsed_seconds=time.monotonic()-start,
            installation=install_result if (not state_model or plan.get('autonomous_diagnostic_only')) else None,
            installed_preflight=install_result if (state_model and not plan.get('autonomous_diagnostic_only')) else None,
            experiment_ready=False)
        try:mark('failure_detected',error_type=type(exc).__name__,session_id=current.name if current else None)
        except BaseException as err:failure['failure_checkpoint_error']=repr(err)
        if identified and remote and current and d is not None:
            d.deadline=min(hard-45,time.monotonic()+15)
            prefix=current/'failure_prefix'
            for name in ('manifest.json','progress.jsonl','cleanup.json','sampler_failure.json','session_failure.json'):
                try:pull_file(d,remote,name,prefix)
                except BaseException as err:
                    failure.setdefault('recovery_errors',{})[name]=repr(err)
                    try:save(current/(name+'.recovery_error.json'),dict(error=repr(err)))
                    except BaseException as write_error:failure.setdefault('recovery_record_errors',{})[name]=repr(write_error)
        if current:
            for name in ('cleanup.json','session_failure.json'):
                artifact=current/'artifacts'/name
                if not artifact.is_file():artifact=current/'failure_prefix'/name
                if artifact.is_file():
                    try:failure.setdefault('app_terminal_evidence',{})[name]=c.p.read(artifact)
                    except BaseException as err:failure.setdefault('app_terminal_read_errors',{})[name]=repr(err)
        autonomous_may_be_active=bool(plan.get('autonomous_diagnostic_only') and current and
            (current/'autonomous_segment_arm_intent.json').exists())
        if identified and d is not None:
            if cleanup_attempted:
                # Validation or receipt failure after cleanup must not issue a
                # second force-stop. A raised cleanup has an unknown partial
                # outcome; retrying it would also exceed the single attempt.
                failure['host_cleanup']=(cleanup_result if cleanup_result is not None else
                    dict(status='attempted_outcome_unknown_no_retry'))
            elif autonomous_may_be_active:
                failure['host_cleanup']=dict(status='deferred_device_segment_may_be_active',
                    reason='probe arm delivery or app completion unconfirmed; no automatic transport switch/force-stop')
            else:
                cleanup_attempted=True
                try:
                    cleanup_result=shared.cleanup(d,hard)
                    save((current or root)/'failure_host_cleanup.json',cleanup_result)
                    failure['host_cleanup']=cleanup_result
                except BaseException as err:
                    failure['host_cleanup']=cleanup_result or dict(status='attempted_outcome_unknown_no_retry')
                    failure['host_cleanup_error']=repr(err)
        prefix=current/'failure_prefix/progress.jsonl' if current else None
        try:
            failure['last_session_progress']=(state.progress_consumption(prefix.read_bytes() if prefix and prefix.is_file() else b'',
                bool(current and (current/'launch_attempt.json').exists())) if state else
                c.progress_consumption(prefix.read_bytes() if prefix and prefix.is_file() else b'',
                bool(current and (current/'launch_attempt.json').exists()),plan.get('operational_only',False)))
        except BaseException as err:failure['progress_summary_error']=repr(err)
        failure['failure_detected_elapsed_seconds']=failure['elapsed_seconds']
        failure['elapsed_seconds']=time.monotonic()-start
        failure['adb_command_slots']=d.sequence if d is not None else 0
        try:mark('failure_receipt_intent',session_id=current.name if current else None)
        except BaseException as err:failure['receipt_checkpoint_error']=repr(err)
        try:checkpoints.atomic_new(root/'FINAL_RECEIPT.json',failure)
        except BaseException as err:
            failure['final_receipt_write_error']=repr(err)
            try:checkpoints.atomic_new(root/'FAILURE_RECEIPT_FALLBACK.json',failure)
            except BaseException as fallback_error:failure['fallback_receipt_write_error']=repr(fallback_error)
        try:checkpoints.atomic_new(registry/'stopped.json',failure)
        except BaseException as err:failure['registry_stop_write_error']=repr(err)
        try:mark('stopped',session_id=current.name if current else None)
        except BaseException:pass
        raise
