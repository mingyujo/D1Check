"""Opt-in, single-use device runner. Import only for an explicitly approved run."""
from __future__ import annotations

import json
import math
import re
import shutil
import time
import traceback
import uuid
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


def tracked_bundle(plan):
    return plan.get('ap_bundled_confirmation') or plan.get('recorded_policy_comparison') or plan.get('online_policy_study')


def require_host_pull_space(plan):
    """Minimum admission only, not a guarantee for the entire run's logs."""
    required=Path(plan['apk_path']).stat().st_size
    free=shutil.disk_usage(Path(plan['output_root']).parent).free
    c.require(free>=required,
              f'insufficient host disk space before claim: free={free}, minimum APK pull bytes={required}; no device command')
    return dict(free_bytes=free,minimum_installed_pull_bytes=required)


def write(path,value):c.cal.write_new(path,value)


def poll(d,remote,folder,manifest,plan):
    from tools import d1_postapproval_observation as postapproval
    postapproval_enabled=postapproval.enabled(plan,manifest)
    environment_enabled=postapproval.environment_enabled(plan)
    c.require(not environment_enabled or postapproval_enabled,'environment lease requires registered history context')
    start=time.monotonic();end=min(d.deadline,start+plan.get('budget',c.BUDGET)['host_poll_seconds'])
    last_thermal=last_screen=0;armed=False;index=0;start_ap_sent=False;last_checkpoint=start
    observation_state={'gaps':0}
    postapproval_state={'gaps':0,'refresh_environment':False}
    last_progress_query=0
    while time.monotonic()<end:
        command_ceiling=(3200 if plan.get('ap_idle_pulse_followup') and
                          manifest.get('phase')=='development' else plan['budget']['adb_commands'])
        if tracked_bundle(plan):
            position=next(e['index'] for e in plan['entries'] if e['session_id']==manifest['session_id'])
            command_ceiling=min(command_ceiling,(position+1)*plan['budget']['per_session_adb_commands'])
        if (plan.get('single_arrival_confirmation') or plan.get('recorded_replay_confirmation') or plan.get('online_policy_study')) and d.sequence>=command_ceiling-plan['budget'].get('adb_recovery_cleanup_reserve',20):
            raise RuntimeError('ADB observation cap reserve reached; preserve recovery/cleanup slots')
        now=time.monotonic()
        if tracked_bundle(plan) and now-last_checkpoint>=30:
            d.bundle_checkpoint.mark('poll_alive',session_id=manifest['session_id'],
                adb_commands=d.sequence,remaining_seconds=d.deadline-now,
                warmup_approved=armed,start_ap_approved=start_ap_sent)
            last_checkpoint=now
        refresh=postapproval_state['refresh_environment']
        lease=postapproval_state.get('environment_lease_deadline')
        if lease is not None and now>=lease:raise TimeoutError('environment lease expired; original gap retained')
        if refresh or now-last_thermal>=2:
            if environment_enabled and armed and start_ap_sent:
                if not postapproval.environment(d,folder,postapproval_state,end,last_thermal,last_screen,'thermal',lambda:energy_device.thermal(d,folder,index)):
                    time.sleep(.25);continue
            elif plan.get('prewarmup_observation') in ('prewarmup-observation-gap-v2','precommon-observation-gap-v3'):
                from tools.d1_preparation_observation import thermal as observe_thermal
                if not observe_thermal(d,folder,index,observation_state,(start_ap_sent if plan.get('prewarmup_observation')=='precommon-observation-gap-v3' else armed),energy_device.thermal,version=plan['prewarmup_observation']):
                    time.sleep(.25)
                    continue
            else:
                energy_device.thermal(d,folder,index)
            index+=1;last_thermal=time.monotonic()
        if refresh or now-last_screen>=10:
            if environment_enabled and armed and start_ap_sent:
                if not postapproval.environment(d,folder,postapproval_state,end,last_thermal,last_screen,'screen',lambda:screen.snapshot(d,folder,f'poll_{index:04d}',plan['screen_contract'])):
                    time.sleep(.25);continue
            else:screen.snapshot(d,folder,f'poll_{index:04d}',plan['screen_contract'])
            last_screen=time.monotonic()
        if lease is not None:
            if time.monotonic()>=lease:raise TimeoutError('fresh environment arrived after lease; original gap retained')
            write(Path(folder)/'postapproval_environment_restored.json',dict(status='fresh_thermal_screen_observed',host_monotonic=time.monotonic(),lease_deadline=lease))
            postapproval_state.pop('environment_lease_deadline')
        if refresh:postapproval_state['refresh_environment']=False
        if postapproval_enabled and armed and start_ap_sent:
            if time.monotonic()-last_progress_query<postapproval.PERIOD_SECONDS:
                time.sleep(.25)
                continue
            listing=postapproval.listing(d,remote,folder,legacy.PACKAGE,postapproval_state,end)
            last_progress_query=time.monotonic()
            if listing is None:
                time.sleep(.25)
                continue
        elif plan.get('prewarmup_observation') in ('prewarmup-listing-gap-v1','prewarmup-observation-gap-v2','precommon-observation-gap-v3'):
            from tools.d1_preparation_observation import listing as observe_listing
            listing=observe_listing(d,remote,folder,legacy.PACKAGE,observation_state,(start_ap_sent if plan.get('prewarmup_observation')=='precommon-observation-gap-v3' else armed),version=plan['prewarmup_observation'])
            if listing is None:
                time.sleep(.25)
                continue
        else:
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
    if plan.get('history_control'):
        from tools.d1_history_control_analysis import validate as history_validate
        return history_validate(folder,manifest,plan)
    expected=96 if plan.get('online_policy_study') else 24
    if plan.get('sustained_confirmation'):
        from tools import d1_sustained_protocol as sustained
        sustained.validate(manifest['requests'],manifest['policy'])
        expected=sustained.COUNT
    if plan.get('background_activity_contrast'):expected=len(manifest['requests'])
    if plan.get('resident_control_pair'):
        from tools import d1_resident_control_plan as control
        expected=control.request_count(manifest)
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
                  (not plan.get('ap_idle_pulse_followup') or approval['ap_c'] < 32.5) and
                  (manifest['start_ap_gate']!=d1_arrival_start_ap.DIAGNOSTIC_VERSION or
                   approval.get('gate_mode')==d1_arrival_start_ap.DIAGNOSTIC_VERSION) and
                  (manifest['start_ap_gate']==d1_arrival_start_ap.DIAGNOSTIC_VERSION or 32.5 <= approval['ap_c'] <= 34.0) and
                  math.isfinite(float(approval['ap_c'])) and
                  approval['read_before_ns'] <= approval['read_after_ns'] <= boundary['start_ns'] and
                  boundary['start_ns']-approval['read_before_ns'] <= 3_000_000_000,
                  'missing/invalid AP approval at actual start')
    c.require(len(rows)==len(boundary['rows'])==expected and summary['planned']==expected,'request denominator')
    if plan.get('resident_control_pair'):
        c.require(summary.get('terminal')==expected and boundary.get('planned')==expected,'control denominator')
    c.require({r['request_id'] for r in rows}=={r['request_id'] for r in manifest['requests']},'request identity')
    c.require(boundary['end_ns']-boundary['start_ns']>=120_000_000_000,'common window incomplete')
    for r in rows:
        fields=('actual_arrival_ns','dispatch_ns','execution_start_ns','output_ready_ns',
                'persist_complete_ns','worker_release_ns','lane_available_ns')
        if plan.get('recorded_replay_confirmation') or plan.get('online_policy_study'):
            fields+=('host_inference_start_ns','host_inference_return_ns')
        c.require(r['terminal_status']=='succeeded' and all(r.get(field) is not None for field in fields),
                  'unfinished/request boundary')
        c.require(r['scheduled_arrival_ns']<=r['actual_arrival_ns']<=r['dispatch_ns']<=
                  r['execution_start_ns']<=r['output_ready_ns']<=r['persist_complete_ns']<=
                  r['worker_release_ns']<=r['lane_available_ns'],'time order')
        if plan.get('recorded_replay_confirmation') or plan.get('online_policy_study'):
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
        elif plan.get('online_policy_study'):
            c.require(r['selected_backend']==('CPU' if manifest['policy']=='CPU_URGENT_ONLINE_V1' or r['task_id']=='detection' else 'GPU'),'online policy allocation')
        else:
            c.require(r['selected_backend']==('CPU' if manifest['policy']=='CPU_URGENT' or r['priority']=='urgent' else 'GPU'),'policy allocation')
        result=p.read(artifacts/(r['request_id']+'.result.json'))
        c.old.quality(p.read(plan['references'][key]['path']),result)
    if plan.get('recorded_replay_confirmation') or plan.get('online_policy_study'):
        for backend in ('CPU','GPU'):
            ordered=sorted((r for r in rows if r['selected_backend']==backend),
                           key=lambda r:r['dispatch_ns'])
            c.require(all(a['lane_available_ns']<=b['dispatch_ns'] for a,b in zip(ordered,ordered[1:])),
                      'busy lane overwritten before actual callback')
    events,partial=c.old.progress_prefix((artifacts/'progress.jsonl').read_bytes())
    c.require(partial==0 and sum(e.get('kind')=='warmup_return' for e in events)==8 and
              sum(e.get('kind')=='runtime_return' for e in events)==4 and
              sum(e.get('kind')=='lane_available' for e in events)==expected,'progress count')
    if expected==0:
        c.require(not any(e.get('kind') in ('arrival','dispatch','request_start','request_return','lane_available')
                          for e in events), 'control unexpectedly ran work')
        c.require(all(not e.get('active') for e in events if e.get('kind')=='power_sample'),
                  'control active snapshot')
    thermal=[json.loads(x) for x in (Path(folder)/'thermal.jsonl').read_text(encoding='utf-8').splitlines()]
    c.require(len(thermal)>=30 and all(t['thermal_status']=='0' for t in thermal),'AP/thermal coverage')
    samples=[]
    for e in events:
        if e.get('kind')!='power_sample':continue
        c.require(e['snapshot_start_ns']<=e['sensor_read_end_ns']<=e['state_snapshot_ns']<=e['mono_ns'] and
                  e['sensor_read_end_ns']-e['snapshot_start_ns']<=2e9,'sensor clock bracket')
        s=dict(e);s['mono_ns']=(e['snapshot_start_ns']+e['sensor_read_end_ns'])//2;samples.append(s)
    begin=boundary['start_ns'];end=boundary['planned_end_ns']
    if plan.get('resident_control_pair') or plan.get('background_activity_contrast'):
        common_samples=[s for s in samples if begin<=s['mono_ns']<=end]
        c.require(bool(common_samples) and all(set(s.get('resident_keys',[]))==set(c.old.KEYS)
                                               for s in common_samples),'resident control snapshot coverage')
    if plan.get('background_activity_contrast'):
        observed_power=[e for e in events if e.get('kind')=='power_sample']
        c.require(all(e.get('activity_observation_version')=='background-activity-contrast-v1' and
            isinstance(e.get('self_cpu_ms'),int) and e['self_cpu_ms']>=0 and
            e['sensor_read_end_ns']<=e.get('past_input_ready_ns',-1)<=e['mono_ns'] for e in observed_power),
            'activity observation publication/CPU record')
        c.require(all(a['self_cpu_ms']<=b['self_cpu_ms'] for a,b in zip(observed_power,observed_power[1:])),
            'process CPU counter regression')
        past=[e for e in events if e.get('kind')=='causal_power_input' and begin<=e['mono_ns']<=end]
        c.require(len(past)>=8 and all(e.get('status')=='available' and e['latest_ready_ns']<=e['issue_ns']<=e['mono_ns'] and
            e['window_end_ns']-e['window_start_ns']==10_000_000_000 and e.get('future_ap_used') is False
            for e in past),'past-only input coverage; no zero fill')
    c.require(energy.integrate(samples,begin,end,1000)['full_energy_j'] is not None,'common energy coverage')
    ap=[t for t in thermal if begin<=t['mono_ns']<=end and t['AP']!='']
    c.require(len(ap)>=2 and max([ap[0]['mono_ns']-begin,end-ap[-1]['mono_ns']]+[
        b['mono_ns']-a['mono_ns'] for a,b in zip(ap,ap[1:])])<=10e9,'common AP coverage')
    return dict(status='eligible_descriptive_only',phase=manifest['phase'],policy=manifest['policy'],
                scenario=manifest['scenario'],requests=expected,warmup=8,runtimes=4,
                common_start_ns=boundary['start_ns'],common_end_ns=boundary['end_ns'],
                common_unfinished=sum(r.get('terminal_status')!='succeeded' or r.get('persist_complete_ns',10**30)>boundary['end_ns'] for r in boundary['rows']),
                terminal_completed=expected,device_thermal_samples=len(thermal),
                scope='observed fixed trace; no energy saving/thermal model/independent policy PASS')


def run(plan_file,adb,serial,expected_sha,approved):
    c.require(approved and p.digest(plan_file)==expected_sha,'explicit later approval and exact plan hash required')
    plan=p.read(plan_file)
    idle_response=plan.get('ap_idle_pulse_followup',False)
    single=plan.get('single_arrival_confirmation',False) or plan.get('recorded_replay_confirmation',False) or plan.get('online_policy_study',False)
    if plan.get('history_control'):
        from tools import d1_history_control_plan as history
        from tools import d1_background_activity_plan as background
        history.check(plan_file)
        if plan.get('history_recovery_child'):
            from tools.d1_history_recovery_campaign import require_admission
            require_admission(plan_file)
    elif plan.get('sustained_confirmation'):
        from tools import d1_sustained_plan as sustained
        sustained.check(plan_file)
    elif plan.get('background_activity_contrast'):
        from tools import d1_background_activity_plan as background
        background.check(plan_file)
    elif plan.get('separated_power_followup'):
        from tools import d1_separated_power_followup as separated
        separated.check_block(plan_file)
    elif plan.get('separated_power_study'):
        from tools import d1_separated_power_study as separated
        separated.check_block(plan_file)
    elif plan.get('online_sampling_audit'):
        from tools import d1_online_sampling_study as confirmation
        confirmation.check(plan_file)
    elif plan.get('online_policy_study'):
        from tools import d1_online_policy_study as confirmation
        confirmation.check_block(plan_file)
        c.require(plan['study_phase']=='development' or plan['study_freeze'] is not None,'confirmation freeze required')
    elif plan.get('ap_completion_study'):
        from tools import d1_ap_completion_study as confirmation
        confirmation.check_block(plan_file)
        c.require(plan['study_phase']=='development' or plan['study_freeze'] is not None,
                  'confirmation requires frozen study model')
    elif plan.get('ap_background_contrast'):
        from tools import d1_ap_background_contrast as confirmation
        confirmation.check(plan_file)
    elif plan.get('ap_memory_confirmation'):
        from tools import d1_ap_memory_confirmation as confirmation
        confirmation.check(plan_file)
    elif plan.get('recorded_policy_comparison'):
        from tools import d1_recorded_policy_comparison as confirmation
        confirmation.check(plan_file)
        c.require(bool(serial),'explicit transport required')
    elif plan.get('ap_bundled_confirmation'):
        from tools import d1_ap_bundle_confirmation as confirmation
        confirmation.check(plan_file)
    elif plan.get('resident_control_pair'):
        from tools import d1_resident_control_plan as confirmation
        confirmation.check(plan_file)
    elif plan.get('ap_transfer_confirmation'):
        from tools import d1_ap_transfer_confirmation as confirmation
        confirmation.check(plan_file)
    elif idle_response:
        from tools import d1_ap_idle_response_plan as confirmation
        confirmation.check(plan_file)
    elif plan.get('recorded_replay_confirmation'):
        from tools import d1_arrival_recorded_replay as confirmation
        confirmation.check(plan_file)
    elif single:
        from tools import d1_arrival_ap_confirmation as confirmation
        confirmation.check(plan_file)
    else:c.check(plan_file)
    budget=plan['budget']
    root=Path(plan['output_root']);registry=Path(plan['registry'])
    if plan.get('resident_control_pair') or tracked_bundle(plan):
        require_host_pull_space(plan)
    registry.mkdir(parents=True,exist_ok=False);root.mkdir(parents=True,exist_ok=False)
    start=time.monotonic();hard=start+budget['total_seconds']-budget.get('transport_selection_seconds',0)
    journal=None
    claim=dict(utc=legacy.utc(),plan_sha256=expected_sha,budget=budget)
    if tracked_bundle(plan):
        from tools import d1_energy_host_lifecycle as lifecycle
        from tools import d1_energy_host_checkpoints as checkpoints
        claim.update(host_run_id=uuid.uuid4().hex,host_identity=lifecycle.host_identity())
        journal=checkpoints.Checkpoints(root/'host_checkpoints',expected_sha,
                                       claim['host_run_id'],claim['host_identity'])
        journal.mark('claimed')
        (root/'frozen_collection_plan.json').write_bytes(Path(plan_file).read_bytes())
        if plan.get('ap_bundled_confirmation'):
            (root/'candidate_procedure_freeze.json').write_bytes(Path(plan['candidate_freeze']['path']).read_bytes())
            if plan.get('ap_memory_confirmation') or plan.get('ap_background_contrast'):
                (root/'memory_candidate_freeze.json').write_bytes(Path(plan['memory_candidate']['path']).read_bytes())
                (root/'memory_analysis_contract.json').write_bytes(Path(plan['analysis_contract']['path']).read_bytes())
                if plan.get('ap_completion_study') and plan['study_freeze'] is not None:
                    (root/'study_model_freeze.json').write_bytes(Path(plan['study_freeze']['path']).read_bytes())
        else:
            (root/'original_model_freeze.json').write_bytes(Path(plan['frozen_model']['path']).read_bytes())
    write(registry/'claimed.json',claim)
    d=(ObservedDevice(adb,serial,root/'host_commands',allow_select=True,
                      forbid_apk_deploy=plan.get('ap_bundled_confirmation',False) or plan.get('installed_only',False),
                      allow_other_transports=plan.get('recorded_policy_comparison',False) or (plan.get('online_policy_study',False) and bool(serial)))
       if plan.get('resident_control_pair') or tracked_bundle(plan) else
       ObservedDevice(adb,serial,root/'host_commands'))
    if journal:d.bundle_checkpoint=journal
    if plan.get('local_server_probe_gap_version'):
        c.require(plan['local_server_probe_gap_version']=='local-server-probe-gap-v1' and plan.get('history_control'),'local server probe protocol mismatch')
        d.local_server_probe_gap_limit=2
    if plan.get('background_activity_contrast') and plan.get('trace_content_audit'):
        d.background_trace_audit=plan['trace_content_audit']
    if plan.get('history_control'):d.history_trace_spec=plan['history_trace']
    d.deadline=hard
    if single:d.command_limit=budget['adb_commands']-budget.get('external_selection_adb_commands',0)
    complete=[];current=None;remote=None;identified=False;installation=None
    cleanup_attempted=False;cleanup_result=None
    candidate_freeze_sha=None
    try:
        (root/'installation').mkdir()
        if journal:journal.mark('installed_preflight_start')
        installation=(energy_device.installed_preflight(d,plan,plan_file,root/'installation',hard)
                      if plan.get('ap_bundled_confirmation') or plan.get('installed_only') else
                      energy_device.installation(d,plan,plan_file,root/'installation',hard));identified=True
        if journal:journal.mark('installed_preflight_verified',adb_commands=d.sequence)
        for entry in plan['entries']:
            reuse_count=plan.get('history_reuse',{}).get('count',1) if plan.get('history_reuse') else 0
            if entry['index']<reuse_count:
                stats=history.reuse_entry(plan,root,entry)
                complete.append(stats)
                if entry['index']==6 and plan.get('original_model_confirmation'):
                    history.pc_stage(plan,root,'freeze',budget['development_freeze_seconds'])
                if journal:journal.mark('historical_evidence_reused',session_id=entry['session_id'],statistics=stats,device_commands=0)
                continue
            if plan.get('history_control'):
                history.before_entry(plan,root,entry,complete,hard)
            if plan.get('online_policy_study') and plan['study_phase']=='confirmation':
                c.require(p.digest(plan['study_freeze']['path'])==plan['study_freeze']['sha256'],'online model freeze drift')
            if plan.get('ap_bundled_confirmation'):
                if plan.get('ap_completion_study') and plan['study_freeze'] is not None:
                    c.require(p.digest(plan['study_freeze']['path'])==plan['study_freeze']['sha256'] and
                              p.digest(root/'study_model_freeze.json')==plan['study_freeze']['sha256'],
                              'study freeze changed; no further confirmation')
                c.require(p.digest(plan['candidate_freeze']['path'])==plan['candidate_freeze']['sha256'] and
                          p.digest(root/'candidate_procedure_freeze.json')==plan['candidate_freeze']['sha256'],
                          'frozen candidate changed; no continuation')
                if plan.get('ap_memory_confirmation') or plan.get('ap_background_contrast'):
                    c.require(p.digest(plan['memory_candidate']['path'])==plan['memory_candidate']['sha256'] and
                              p.digest(root/'memory_candidate_freeze.json')==plan['memory_candidate']['sha256'] and
                              p.digest(root/'memory_analysis_contract.json')==plan['analysis_contract']['sha256'],
                              'memory model/procedure changed; no continuation')
            if idle_response and entry['index']==1:
                from tools import d1_ap_idle_response_plan as ap_plan
                freeze_start=time.monotonic()
                c.require(len(complete)==1 and complete[0]['status']=='eligible_descriptive_only',
                          'AP development session not eligible')
                c.require(hard-freeze_start>=budget['development_freeze_seconds']+
                          budget['intersession_observation_seconds']+budget['session_seconds'],
                          'freeze/intersession/confirmation reserve')
                development=root/f"00_{plan['entries'][0]['session_id']}"
                evidence=ap_plan.development_evidence(development,plan['frozen_model']['path'])
                freeze=dict(version='ap-preload-idle-reference-diagnostic-v1',
                    original_frozen_sha256=plan['frozen_model']['sha256'],
                    structure_sha256=plan['analysis_contract']['sha256'],
                    analysis_code_sha256=p.digest(ap_plan.model.__file__),
                    development_session_id=plan['entries'][0]['session_id'],
                    development_validated_sha256=p.digest(development/'validated.json'),
                    development_preload=evidence,
                    meaning='fixed structure; confirmation fits its own pre-load reference only')
                write(root/'ap_model_freeze.json',freeze)
                candidate_freeze_sha=p.digest(root/'ap_model_freeze.json')
                write(root/'ap_model_freeze_receipt.json',dict(sha256=candidate_freeze_sha,utc=legacy.utc()))
                c.require(time.monotonic()-freeze_start<=budget['development_freeze_seconds'],
                          'development freeze time')
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
                pause=budget['intersession_observation_seconds'] if idle_response else budget['intersession_cooling_seconds']
                c.require(hard-time.monotonic()>=pause+budget['session_seconds'],'cooldown/session reserve')
                until=time.monotonic()+pause
                while time.monotonic()<until:time.sleep(min(1,until-time.monotonic()))
                if idle_response:c.require(p.digest(root/'ap_model_freeze.json')==candidate_freeze_sha,
                                           'AP structure changed before confirmation')
            c.require(hard-time.monotonic()>=budget['session_seconds'],'whole session reserve')
            current=root/f"{entry['index']:02d}_{entry['session_id']}";current.mkdir();remote=None
            if journal:journal.mark('session_preparation',session_id=entry['session_id'],index=entry['index'])
            cleanup_attempted=False;cleanup_result=None
            session_start=time.monotonic();session_end=min(hard,session_start+budget['session_seconds'])
            poll_reserve=budget.get('history_poll_recovery_reserve',580)
            d.deadline=min(session_start+budget['stage_gate_seconds'],session_end-poll_reserve)
            energy_device.gates(d,plan,current,'before_session')
            c.require(install.installed_hash(d,plan['apk_preflight']['candidate'])==plan['apk_sha256'],'installed APK changed')
            write(current/'attempt.json',dict(entry=entry,utc=legacy.utc(),plan_sha256=expected_sha))
            manifest_file=Path(plan_file).parent/entry['manifest'];manifest=p.read(manifest_file)
            (current/'input_manifest.json').write_bytes(manifest_file.read_bytes())
            remote=shared.stage_inputs(d,entry['session_id'],manifest_file,
                                       {k:v['path'] for k,v in plan['source_files'].items()},c.PROTOCOL)
            c.require(session_end-time.monotonic()>=poll_reserve+budget.get('trace_start_seconds',0)+budget.get('trace_recovery_seconds',0),'poll/recovery/cleanup reserve')
            d.deadline=session_end-budget['recovery_seconds']-budget['cleanup_seconds']-budget.get('trace_recovery_seconds',0)
            if plan.get('background_activity_contrast'):
                background.trace_start(d,entry['session_id'],current)
            write(current/'launch_attempt.json',dict(utc=legacy.utc()))
            d.call('shell','am','start','-W','-n',legacy.PACKAGE+'/'+('com.example.d1check.benchmarkrunner.OnlinePolicyStudyActivity' if plan.get('online_configuration_owner_v1') else ACTIVITY),'-a',ACTION,
                   '--es','session_id',entry['session_id'],timeout=20)
            poll(d,remote,current,manifest,plan)
            if journal:journal.mark('app_terminal_seen',session_id=entry['session_id'],adb_commands=d.sequence)
            d.deadline=min(session_end-budget['cleanup_seconds']-budget.get('trace_recovery_seconds',0),time.monotonic()+budget['recovery_seconds'])
            write(current/'recovery.json',energy_device.recover(d,remote,current/'artifacts'))
            cleanup_attempted=True
            try:
                cleanup_result=shared.cleanup(d,session_end-budget.get('trace_recovery_seconds',0))
            except BaseException as error:
                cleanup_result=dict(error=repr(error),status='failed_or_unknown')
                try:write(current/'host_cleanup_error.json',cleanup_result)
                except BaseException as recording_error:
                    cleanup_result['recording_error']=repr(recording_error)
                raise
            write(current/'host_cleanup.json',cleanup_result)
            if plan.get('background_activity_contrast'):
                trace=background.trace_recover(d,session_end)
                c.require(trace and not trace['errors'],'system trace incomplete; no next session')
            stats=validate(current,manifest,plan)
            if plan.get('ap_background_contrast'):
                from tools import d1_ap_background_contrast_readout as contrast_readout
                contrast_case=contrast_readout.case_from_session(plan_file,plan,entry)
                _,contrast_initial=contrast_readout.predict_fixed(contrast_case,plan)
                stats['contrast_input_eligibility']=contrast_initial
            if plan.get('ap_memory_confirmation'):
                from tools import d1_ap_memory_confirmation_readout as memory_readout
                memory_case=memory_readout.case_from_session(plan_file,plan,entry)
                _, memory_initial=memory_readout.predict_fixed(memory_case,plan)
                stats['memory_input_eligibility']=memory_initial
            if idle_response:
                from tools import d1_ap_idle_response_plan as ap_plan
                stats['preload_ap']=ap_plan.development_evidence(current,plan['frozen_model']['path'])
                stats['ap_candidate_freeze_sha256']=candidate_freeze_sha
            c.require(time.monotonic()<=session_end,'session exceeded reserve; no next session')
            stats['elapsed_seconds']=time.monotonic()-session_start
            write(current/'validated.json',stats)
            if idle_response:
                result=ap_plan.model.analyze_session(current,plan['frozen_model']['path'],
                                                     current/'ap_analysis')
                write(current/'ap_analysis_receipt.json',dict(
                    analysis_sha256=p.digest(current/'ap_analysis'/'summary.json'),
                    ap_samples=result['ap_samples'],accuracy_pass=None))
            complete.append(stats)
            if journal:journal.mark('session_validated',session_id=entry['session_id'],statistics=stats)
        if not single:c.require(p.digest(root/'development_freeze.json')==p.read(root/'freeze_receipt.json')['sha256'],'freeze changed')
        if idle_response:c.require(candidate_freeze_sha is not None and
                    p.digest(root/'ap_model_freeze.json')==candidate_freeze_sha,
                    'AP candidate not frozen throughout confirmation')
        if plan.get('history_control'):history.finish_analysis(plan,root)
        outcome=dict(status='completed_descriptive_only',sessions=len(complete),requests=sum(x['requests'] for x in complete),warmup=8*len(complete),
                     runtime_creations=4*len(complete),adb_commands=d.sequence,elapsed_seconds=time.monotonic()-start,
                      installation=installation,experiment_ready=False)
        if plan.get('history_control'):
            outcome.update(conditioning_requests=sum(x['conditioning_requests'] for x in complete),
                explicit_inference=sum(x['requests']+x['conditioning_requests']+8 for x in complete))
            if plan.get('history_reuse'):
                reused=sum(x['requests']+x['conditioning_requests']+8 for x in complete[:reuse_count])
                outcome.update(reused_sessions=reuse_count,new_sessions=len(complete)-reuse_count,reused_inference=reused,
                    new_explicit_inference=outcome['explicit_inference']-reused,new_runtime_creations=4*(len(complete)-reuse_count),
                    new_warmup=8*(len(complete)-reuse_count),accounting='sessions/explicit_inference include immutable historical evidence; new_* are current device consumption')
        if journal:journal.mark('app_sessions_finished_receipt_pending',outcome=outcome)
        write(root/'FINAL_RECEIPT.json',outcome);write(registry/'completed.json',outcome);return outcome
    except BaseException as exc:
        failure=dict(status='stopped_no_resume',error=repr(exc),completed_sessions=len(complete),
                     session_attempts=len(list(root.glob('*/attempt.json'))),
                     launch_attempts=len(list(root.glob('*/launch_attempt.json'))),
                     consumption='confirmed durable event starts/returns only; missing calls remain unknown',
                      installation=installation,experiment_ready=False)
        if journal:
            failure['original_stack']=traceback.format_exc()
            try:journal.mark('original_failure',error=repr(exc),stack=failure['original_stack'],adb_commands=d.sequence)
            except BaseException as recording_error:failure['original_checkpoint_error']=repr(recording_error)
        if identified and remote and current:
            d.deadline=min(hard-45,time.monotonic()+15)
            prefix_names=('manifest.json','progress.jsonl','cleanup.json','sampler_failure.json','session_failure.json','common_boundary.json','requests.json')
            if plan.get('history_control'):
                prefix_names+=('history_boundary.json','conditioning_common_boundary.json','conditioning_requests.json')
            for name in prefix_names:
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
        if plan.get('background_activity_contrast'):
            try:failure['system_trace']=background.trace_recover(d,hard)
            except BaseException as error:failure['system_trace_error']=repr(error)
        prefix=current/'failure_prefix/progress.jsonl' if current else None
        records,partial=c.old.progress_prefix(prefix.read_bytes() if prefix and prefix.is_file() else b'')
        failure['last_session_progress']=dict(valid_records=len(records),partial_lines=partial,
            last_event=records[-1] if records else None,
            counts={kind:sum(e.get('kind')==kind for e in records) for kind in
                    ('runtime_start','runtime_return','warmup_start','warmup_return','request_start','output_ready','persist_complete','lane_available')},
            missing_not_zero=True)
        failure['elapsed_seconds']=time.monotonic()-start
        failure['adb_commands']=d.sequence
        if journal:
            try:journal.mark('stopped_no_resume',failure=failure)
            except BaseException as recording_error:failure['terminal_checkpoint_error']=repr(recording_error)
        write(root/'FINAL_RECEIPT.json',failure);write(registry/'stopped.json',failure)
        raise
