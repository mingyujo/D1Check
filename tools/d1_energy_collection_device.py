"""One approved bundle only. Imported only by explicit run. No recovery/retry loop."""
from pathlib import Path
import io
import json
import re
import statistics
import tarfile
import time
from tools import d1_energy_collection as c
from tools import d1_arrival_device as legacy
from tools import d1_arrival_timing_calibration_device as shared
from tools import d1_apk_identity as apk
from tools import d1_collection_recovery as install
from tools import d1_logger_v4 as logger
from tools.d1_adb_observed_client import ObservedDevice
from tools import d1_energy_screen as screen

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

def recover(d,remote,folder):
    """Identity/progress first, then one bounded archive command; no per-file870-call loop."""
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    # Partial progress can change until shutdown: preserve this snapshot separately.
    prefix=folder.parent/'recovery_prefix';prefix.mkdir(exist_ok=True)
    for name in ('manifest.json','progress.jsonl','cleanup.json'):
        pull_file(d,remote,name,prefix)
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
    return dict(status='recovered',files=len(list(folder.iterdir())),archive_sha256=c.p.digest(folder.parent/'artifacts.tar'))

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

def poll(d,remote,folder,m,plan,baseline_anchor=None):
    start=time.monotonic();end=min(d.deadline,start+1220);armed=set();index=0;last_thermal=last_screen=0;last_sensor=None;heartbeat_index=-1
    while time.monotonic()<end:
        now=time.monotonic()
        if now-last_thermal>=2:
            last_sensor=thermal(d,folder,index);index+=1;last_thermal=time.monotonic()
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
        for gate in ('warmup','probe','baseline'):
            if gate in armed or gate+'.ready.json' not in listing:continue
            target=Path(folder)/('gate_'+gate)
            ready=c.p.read(pull_file(d,remote,gate+'.ready.json',target))
            c.require(ready['manifest_sha256']==c.p.digest(Path(folder)/'input_manifest.json'),'gate manifest')
            if gate=='warmup':
                rows=c.p.read(pull_file(d,remote,'warmup.json',target));c.require(len(rows)==8,'warmup budget')
                c.require(all(sum(x['key']==k for x in rows)==2 for k in c.KEYS),'warmup coverage')
                for r in rows:c.quality(c.p.read(plan['references'][r['key']]['path']),r['result'])
                pid=d.call('shell','pidof',legacy.PACKAGE+':model_probe',timeout=3).stdout.decode().strip()
                c.require(re.fullmatch(r'\d+',pid),'single process')
                logs=d.call('logcat','-d','-v','threadtime','--pid='+pid,'-s','D1ENERGY:I','tflite:I',timeout=5).stdout
                (target/'delegate_log.txt').write_bytes(logs);save(target/'gpu.json',gpu_proof(logs.decode(errors='replace'),m['session_id']))
            elif gate=='probe':
                c.require('warmup' in armed,'probe before warmup gate')
                rows=c.p.read(pull_file(d,remote,'eligibility_probe.requests.json',target))
                c.validate_rows(rows,m['pair'],m['mode'],[1,1])
                for row in rows:
                    result=c.p.read(pull_file(d,remote,row['id']+'.result.json',target))
                    c.quality(c.p.read(plan['references'][row['key']]['path']),result)
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
                save(target/'baseline.json',dict(ap_median_c=median,anchor_c=baseline_anchor,tolerance_c=.5,unit='degC',role='environment matching not effect margin'))
            arm(d,'files/arrival-scheduler-inputs/'+m['session_id'],gate,ready['manifest_sha256'])
            save(target/'arm_receipt.json',dict(gate=gate,utc=legacy.utc(),manifest_sha256=ready['manifest_sha256']))
            armed.add(gate)
        time.sleep(.25)
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
            remote='/data/local/tmp/d1check-'+c.EXPERIMENT.lower()+'.apk'
            probe=d.call('shell','test','-e',remote,check=False,timeout=3)
            c.require(probe.returncode==1 and not probe.stderr.strip(),'remote install output already exists')
            state['apk_transfer_attempts']=1;save(root/'apk_transfer_attempt.json',dict(utc=legacy.utc()))
            d.call('push',plan['apk_path'],remote,timeout=120)
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

def run(plan_file,adb,serial,expected_sha,approved):
    c.require(approved and c.p.digest(plan_file)==expected_sha,'new explicit approval/hash required')
    c.check(plan_file);plan=c.p.read(plan_file);root=Path(plan['output_root']);registry=Path(plan['registry'])
    # Single-use claim BEFORE any preflight/transfer. A failed gate does not allow silent resume.
    registry.mkdir(parents=True,exist_ok=False);root.mkdir(parents=True,exist_ok=False)
    start=time.monotonic();hard=start+c.BUDGET['total_seconds']
    save(registry/'claimed.json',dict(plan_sha256=expected_sha,utc=legacy.utc(),budget=c.BUDGET))
    d=ObservedDevice(adb,serial,root/'host_commands');d.deadline=hard
    results=[];current=None;remote=None;identified=False;install_result=None
    try:
        install_root=root/'installation';install_root.mkdir();install_result=installation(d,plan,plan_file,install_root,hard);identified=True
        frozen=None
        for e in plan['entries']:
            if e['index']==4:
                freeze_start=time.monotonic();frozen={r['condition']:r for r in results}
                c.require(len(frozen)==4 and all(r['status']=='eligible_descriptive_only' for r in results),'development freeze eligibility')
                save(root/'development_freeze.json',dict(plan_sha256=expected_sha,conditions=frozen,source='development_only',accuracy_pass=None))
                save(root/'freeze_receipt.json',dict(sha256=c.p.digest(root/'development_freeze.json'),utc=legacy.utc()))
                c.require(time.monotonic()-freeze_start<600,'freeze time exceeded')
            c.require(hard-time.monotonic()>=1500,'insufficient whole session reserve; stop')
            current=root/f"{e['index']:02d}_{e['session_id']}";current.mkdir();remote=None
            session_start=time.monotonic();session_end=min(session_start+1500,hard);d.deadline=min(session_start+120,session_end-105)
            gates(d,plan,current,'before_session')
            c.require(install.installed_hash(d,plan['apk_preflight']['candidate'])==plan['apk_sha256'],'installed APK changed')
            if e['mode']=='parallel':
                serial_key=e['pair']+'_serial'
                c.require(any(r['condition']==serial_key and r['status']=='eligible_descriptive_only' for r in results if r['phase']==e['phase']),'same-stage serial prerequisite')
            save(current/'attempt.json',dict(entry=e,utc=legacy.utc(),plan_sha256=expected_sha))
            manifest=Path(plan_file).parent/e['manifest'];m=c.p.read(manifest)
            (current/'input_manifest.json').write_bytes(manifest.read_bytes())
            remote=shared.stage_inputs(d,e['session_id'],manifest,{k:v['path'] for k,v in plan['source_files'].items()},c.PROTOCOL)
            c.require(session_end-time.monotonic()>=1220+105,'launch reserve')
            d.deadline=session_end-105
            save(current/'launch_attempt.json',dict(utc=legacy.utc()))
            d.call('shell','am','start','-W','-n',legacy.PACKAGE+'/'+ACTIVITY,'-a',ACTION,'--es','session_id',e['session_id'],timeout=20)
            anchor=next((r['phases']['resident_baseline']['ap_median_c'] for r in results if r['condition']==e['pair']+'_serial'),None)
            poll(d,remote,current,m,plan,anchor)
            d.deadline=min(time.monotonic()+60,session_end-45)
            save(current/'recovery.json',recover(d,remote,current/'artifacts'))
            # Cleanup is reserved BEFORE PC validation; validation cannot prolong active device work.
            save(current/'host_cleanup.json',shared.cleanup(d,session_end))
            stats=c.summarize_session(current/'artifacts',manifest,plan);stats['phase']=e['phase']
            c.require(time.monotonic()<=session_end,'session PC validation exhausted reservation; no next session')
            stats['elapsed_seconds']=time.monotonic()-session_start
            if frozen is not None:
                fr=frozen[stats['condition']]
                stats['confirmation_errors']={phase:dict(power_w=values['energy']['mean_power_w']-fr['phases'][phase]['energy']['mean_power_w'],
                    ap_end_c=values['ap_end_c']-fr['phases'][phase]['ap_end_c']) for phase,values in stats['phases'].items()}
                c.require(c.p.digest(root/'development_freeze.json')==c.p.read(root/'freeze_receipt.json')['sha256'],'freeze changed')
            save(current/'validated.json',stats);results.append(stats)
        result=dict(status='completed_descriptive_only',sessions=8,diagnostic_requests=6976,warmup=64,explicit_inference=7040,
            installation=install_result,elapsed_seconds=time.monotonic()-start,accuracy_pass=None,experiment_ready=False)
        save(root/'FINAL_RECEIPT.json',result);save(registry/'completed.json',result);return result
    except BaseException as exc:
        failure=dict(status='stopped_no_resume',error=repr(exc),completed_sessions=len(results),
            session_attempts=len(list(root.glob('*/attempt.json'))),launch_attempts=len(list(root.glob('*/launch_attempt.json'))),
            consumption='only durable start/return pairs confirm counts; absent logs remain unknown',elapsed_seconds=time.monotonic()-start,
            installation=install_result,experiment_ready=False)
        if identified and remote and current:
            d.deadline=min(hard-45,time.monotonic()+15)
            prefix=current/'failure_prefix'
            for name in ('manifest.json','progress.jsonl','cleanup.json'):
                try:pull_file(d,remote,name,prefix)
                except BaseException as err:save(current/(name+'.recovery_error.json'),dict(error=repr(err)))
        if identified:
            try:save((current or root)/'failure_host_cleanup.json',shared.cleanup(d,hard))
            except BaseException as err:failure['host_cleanup_error']=repr(err)
        prefix=current/'failure_prefix/progress.jsonl' if current else None
        failure['last_session_progress']=c.progress_consumption(prefix.read_bytes() if prefix and prefix.is_file() else b'',
            bool(current and (current/'launch_attempt.json').exists()))
        save(root/'FINAL_RECEIPT.json',failure);save(registry/'stopped.json',failure)
        raise
