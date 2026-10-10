"""Bounded, new-ID ABBA frozen-plan replay; never an online phone scheduler."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import statistics
import time
import traceback
import uuid

from tools import d1_overnight_device_build as build
from tools import d1_arrival_plan as p
from tools import d1_arrival_device as legacy
from tools import d1_arrival_timing_calibration_device as shared
from tools import d1_energy_collection_device as device
from tools import d1_arrival_energy_collection_device as arrival
from tools import d1_collection_recovery as installed
from tools import d1_arrival_start_ap as start_ap
from tools import d1_energy_screen as screen
from tools import d1_energy_thermal as energy
from tools import d1_arrival_energy_analysis as observed
from tools.d1_adb_observed_client import ObservedDevice

ROOT=build.ROOT
BASE=build.BASE
PUBLIC=build.PUBLIC
NAME='OVERNIGHT-FROZEN-PLAN-DEVICE-01'
COUNT=96
POLICY='RECORDED_B2_REPLAY_V1'
BUDGET=dict(sessions=4,work_requests=384,warmup=32,explicit_inference=416,runtime_creations=16,
    staging=4,staged_files=28,installed_host_pulls=1,apk_transfers=1,installs=1,
    retries=0,replacements=0,total_seconds=5400,save_reserve_seconds=600,
    installation_seconds=600,session_seconds=765,stage_gate_seconds=120,launch_seconds=20,
    host_poll_seconds=485,recovery_seconds=60,cleanup_seconds=45,
    intersession_cooling_seconds=90,adb_commands=12000,adb_cleanup_reserve=100)


def require(ok, message):
    if not ok:
        raise ValueError(message)


def write(path, value):
    build.write(path,value)


def shape(rows):
    require(len(rows)==COUNT,'exact 96 requests required')
    for i,q in enumerate(rows):
        urgent=i%2==0
        require(q['ordinal']==i and q['offset_ms']==35000+i*350 and
            q['task_id']==('classification' if urgent else 'detection') and
            q['priority']==('urgent' if urgent else 'normal') and
            q['deadline_ms']==(1500 if urgent else 6000),'periodic input contract')
        require(q['recorded_backend'] in ('CPU','GPU') and
            (q['task_id']!='detection' or q['recorded_backend']=='CPU'),'CPU/GPU supported assignment')
        require(q['offset_ms']*1_000_000<=q['release_offset_ns']<120_000_000_000,'release vs actual arrival')
        require(bool(q['source_request_id']),'source ID')


def sources():
    files=(__file__,build.__file__,arrival.__file__,device.__file__,shared.__file__,start_ap.__file__,
        installed.__file__,energy.__file__,observed.__file__,screen.__file__,
        ROOT/'tools/test_d1_overnight_device_replay.py',ROOT/'tools/d1_overnight_device_report.py',
        ROOT/'tools/d1_simulation_model_v2.py',ROOT/'tools/d1_simulation_model_v3_thermal.py',
        ROOT/'docs/results/overnight_device_20261011/frozen_plan_replay_v2.patch',
        ROOT/'docs/results/overnight_device_20261011/isolated_build.gradle')
    return {Path(x).relative_to(ROOT).as_posix():p.digest(x) for x in files}


def prepare(schedules):
    schedules=Path(schedules).resolve(); data=p.read(schedules)
    require(len(data['policies'])==2,'two frozen policy schedules')
    policies=data['policies']; rows=[x['requests'] for x in policies]
    for seq in rows:shape(seq)
    inputs=lambda seq:[{k:q[k] for k in ('ordinal','source_request_id','task_id','priority','offset_ms','deadline_ms')} for q in seq]
    require(inputs(rows[0])==inputs(rows[1]),'ABBA same input/arrival/deadline')
    for policy in policies:
        require(policy['policy_id'] and policy.get('source_sha256'),'frozen policy identity')
    source_file=ROOT/'output/model_v3_expert_20261010_v1/hybrid/plan/collection_plan.json'
    old=p.read(source_file); built=p.read(BASE/'build_receipt_v2.json')
    require(built['status']=='built_tested_not_installed','validated isolated build required')
    template=p.read(source_file.parent/old['entries'][0]['manifest'])
    require(p.digest(built['apk_path'])==built['apk_sha256'],'built APK drift')
    out=BASE/'plan'; require(not out.exists() and not (BASE/'registry').exists(),'new unconsumed task only')
    plan=dict(experiment_id=NAME,status='prepared_not_run',approval='user_overnight_completion_20261011',
        experiment_ready=False,recorded_replay_confirmation=True,resident_identification=True,
        device_fingerprint=old['device_fingerprint'],device_hardware_serial=old['device_hardware_serial'],
        apk_path=built['apk_path'],apk_sha256=built['apk_sha256'],build_receipt=str(BASE/'build_receipt_v2.json'),
        build_receipt_sha256=p.digest(BASE/'build_receipt_v2.json'),
        apk_preflight=dict(old['apk_preflight'],candidate=built['candidate']),budget=BUDGET,
        battery_start_percent=20,battery_min_percent=20,battery_max_temperature_tenths_c=350,
        require_unplugged=True,screen_contract=old['screen_contract'],thermal_timeout_seconds=3,
        source_files=old['source_files'],references=old['references'],source_code=sources(),
        source_schedules=dict(path=str(schedules),sha256=p.digest(schedules)),
        original_model=old['original_model'],thermal_model=old['prior_freeze'],
        output_root=str(BASE/'run'),registry=str(BASE/'registry'),entries=[],
        comparison_scope='fixed PC schedules on phone; not online Band/RL or actual policy dominance',
        new_data_fit_calls=0,source_plan=dict(path=str(source_file),sha256=p.digest(source_file)),
        pair_initial_ap_tolerance_c=.5,
        pair_initial_ap_basis='existing arrival/resident environment-matching tolerance; descriptive eligibility only, not effect margin',
        pair_battery_requirement='noncharging SOC>=20, BAT<=35, power-save recorded; no SOC normalization',
        automatic_schedule_selection='predefined 96 alternating 350ms trace; no actual result-based selection')
    out.mkdir()
    for i,arm in enumerate((0,1,1,0)):
        sid=str(uuid.uuid5(uuid.NAMESPACE_URL,NAME+'/'+str(i)))
        m=copy.deepcopy(template)
        for key in ('policy_study_version','policy_study_role','power_identification_version','power_sampling_version',
            'power_sample_period_ms','low_battery_diagnostic_version','battery_min_percent'):
            m.pop(key,None)
        req=copy.deepcopy(rows[arm])
        for q in req:q['request_id']=str(uuid.uuid5(uuid.NAMESPACE_URL,sid+'/'+str(q['ordinal'])))
        m.update(experiment_id=NAME,session_id=sid,phase=f'frozen_plan_{i}_arm{arm}',
            scenario='frozen_plan_periodic96',policy=POLICY,source_policy=policies[arm]['policy_id'],
            replay_version=build.VERSION,replay_source_sha256=p.digest(schedules),
            apk_sha256=built['apk_sha256'],requests=req,start_ap_gate='numeric-ap-observe-v2')
        for spec in m['models'].values():
            spec['identity']['session_id']=sid;spec['target']['apk_sha256']=built['apk_sha256']
        rel='manifests/'+sid+'.json';write(out/rel,m)
        plan['entries'].append(dict(index=i,arm=arm,session_id=sid,source_policy=policies[arm]['policy_id'],
            manifest=rel,manifest_sha256=p.digest(out/rel),requests=COUNT,warmup=8,runtime_creations=4))
    write(out/'collection_plan.json',plan)
    contract={k:plan[k] for k in ('experiment_id','status','comparison_scope','new_data_fit_calls','budget',
        'pair_initial_ap_tolerance_c','pair_initial_ap_basis','pair_battery_requirement','automatic_schedule_selection')}
    contract.update(schedules_sha256=p.digest(schedules),policy_ids=[q['policy_id'] for q in policies],
        same_input_seed=data.get('trace_seed'),native_version=build.VERSION,
        current_unit='whole-device current raw interpreted as mA; absolute joule accuracy uncertified',
        AP='same AP channel; not surface temperature',plan_sha256=p.digest(out/'collection_plan.json'),
        physical_sessions_before_registration=0,installation_limit=1,full_request_denominator=384)
    write(PUBLIC/'execution_contract.json',contract)
    return check(out/'collection_plan.json')


def check(plan_file,consumed=False):
    file=Path(plan_file);plan=p.read(file)
    require(plan['experiment_id']==NAME and plan['budget']==BUDGET,'identity/budget drift')
    require(plan['source_code']==sources(),'frozen collector sources changed')
    for spec in [plan['source_schedules'],plan['original_model'],plan['thermal_model'],plan['source_plan']]:
        require(p.digest(spec['path'])==spec['sha256'],'frozen evidence drift')
    require(p.digest(plan['apk_path'])==plan['apk_sha256'] and
        p.digest(plan['build_receipt'])==plan['build_receipt_sha256'],'build bytes drift')
    for spec in [*plan['source_files'].values(),*plan['references'].values()]:
        require(p.digest(spec['path'])==spec['sha256'],'input/reference drift')
    for e in plan['entries']:
        manifest=file.parent/e['manifest'];require(p.digest(manifest)==e['manifest_sha256'],'manifest drift')
        shape(p.read(manifest)['requests'])
    if not consumed:
        require(not Path(plan['registry']).exists() and not Path(plan['output_root']).exists(),'consumed plan; no resume/reset')
    return dict(status='ready_unexecuted' if not consumed else 'consumed_integrity_checked',
        plan_sha256=p.digest(file),sessions=4,explicit_inference_cap=416,device_commands=0)


def validate(folder,manifest,plan):
    a=Path(folder)/'artifacts'; rows=p.read(a/'requests.json'); boundary=p.read(a/'common_boundary.json')
    summary=p.read(a/'summary.json'); cleanup=p.read(a/'cleanup.json')
    require(p.digest(a/'manifest.json')==p.digest(Path(folder)/'input_manifest.json'),'returned manifest drift')
    require(summary['status']==cleanup['status']=='completed','app did not complete')
    require(len(rows)==COUNT==len(boundary['rows'])==summary['planned'],'all-arrival denominator')
    expected={q['request_id']:q for q in manifest['requests']}
    require(set(expected)=={r['request_id'] for r in rows},'missing/duplicate request')
    begin=boundary['start_ns'];end=boundary['planned_end_ns']
    require(end-begin==120_000_000_000 and boundary['end_ns']>=end,'common window')
    approval=p.read(a/'start_ap.accepted.json')
    require(approval['common_start_ns']==begin and approval['gate_mode']=='numeric-ap-observe-v2' and
        approval['read_before_ns']<=approval['read_after_ns']<=begin and
        begin-approval['read_before_ns']<=3_000_000_000,'fresh native AP approval')
    for r in rows:
        q=expected[r['request_id']]
        fields=('scheduled_arrival_ns','actual_arrival_ns','dispatch_ns','execution_start_ns',
            'host_inference_start_ns','host_inference_return_ns','output_ready_ns',
            'persist_complete_ns','worker_release_ns','lane_available_ns')
        require(r['terminal_status']=='succeeded' and all(r.get(k) is not None for k in fields),'unfinished physical request')
        require(all(r[x]<=r[y] for x,y in zip(fields,fields[1:])),'response/release order')
        require(r['scheduled_arrival_ns']==begin+q['offset_ms']*1_000_000 and
            r['deadline_ns']==r['scheduled_arrival_ns']+q['deadline_ms']*1_000_000,'actual scheduled deadline')
        require(r['selected_backend']==q['recorded_backend'] and r['source_request_id']==q['source_request_id'] and
            r['recorded_release_ns']==begin+q['release_offset_ns'] and r['dispatch_ns']>=r['recorded_release_ns'],
            'frozen assignment/release changed')
        key=q['task_id']+'_'+q['recorded_backend']
        arrival.c.old.quality(p.read(plan['references'][key]['path']),p.read(a/(r['request_id']+'.result.json')))
    for backend in ('CPU','GPU'):
        ordered=sorted((r for r in rows if r['selected_backend']==backend),key=lambda r:r['dispatch_ns'])
        require(all(x['lane_available_ns']<=y['dispatch_ns'] for x,y in zip(ordered,ordered[1:])),
            'lane overwritten before actual AVAILABLE')
    for cpu in (r for r in rows if r['selected_backend']=='CPU'):
        for gpu in (r for r in rows if r['selected_backend']=='GPU'):
            if max(cpu['dispatch_ns'],gpu['dispatch_ns'])<min(cpu['lane_available_ns'],gpu['lane_available_ns']):
                require(cpu['task_id']=='detection' and gpu['task_id']=='classification','unverified concurrent pairing')
    events=observed.read_lines(a/'progress.jsonl')
    require([e['sequence'] for e in events]==list(range(len(events))),'durable journal continuity')
    require(sum(e['kind']=='runtime_return' for e in events)==4 and
        sum(e['kind']=='warmup_return' for e in events)==8 and
        sum(e['kind']=='lane_available' for e in events)==COUNT,'runtime/warmup/request ledger')
    samples=[]
    for e in events:
        if e['kind']!='power_sample':continue
        require(e['snapshot_start_ns']<=e['sensor_read_end_ns']<=e['state_snapshot_ns']<=e['mono_ns'] and
            e['sensor_read_end_ns']-e['snapshot_start_ns']<=2e9,'battery sensor bracket')
        require(e['battery_scale']==100 and e['battery_level']>=20 and e['plugged']==0,'battery environment left scope')
        samples.append(dict(e,mono_ns=(e['snapshot_start_ns']+e['sensor_read_end_ns'])//2))
    admissions=[e for e in events if e['kind']=='admission']
    require(admissions and all(e.get('low_memory') is False and e.get('thermal_status')==0 and
        e.get('admission_reason')=='admit' for e in admissions),'native environment admission')
    power=energy.integrate(samples,begin,end,1000)
    thermal=observed.read_lines(Path(folder)/'thermal.jsonl')
    require(all(e['thermal_status']=='0' and e['sampling_uncertainty_ns']<=2e9 for e in thermal),'thermal gate/clock')
    ap=[e for e in thermal if begin<=e['mono_ns']<=end and e['AP']!='']
    gaps=[ap[0]['mono_ns']-begin,end-ap[-1]['mono_ns']]+[y['mono_ns']-x['mono_ns'] for x,y in zip(ap,ap[1:])] if ap else [end-begin]
    require(len(ap)>=2 and max(gaps)<=10e9,'AP coverage missing')
    urgent=[r for r in rows if r['priority']=='urgent'];normal=[r for r in rows if r['priority']=='normal']
    require(len(urgent)==len(normal)==48,'priority denominator')
    response=lambda r:r['output_ready_ns'] if r['priority']=='urgent' else r['persist_complete_ns']
    unfinished=sum(r['persist_complete_ns']>end or r['terminal_status']!='succeeded' for r in rows)
    def missed(r):return r['terminal_status']!='succeeded' or response(r)>min(r['deadline_ns'],end)
    times=sorted((response(r)-r['scheduled_arrival_ns'])/1e6 for r in urgent if response(r)<=end)
    common_j=power['full_energy_j'] if unfinished==0 else None
    return dict(status='completed_frozen_plan_descriptive_only',planned=COUNT,completed=COUNT,
        common_unfinished=unfinished,urgent_denominator=48,normal_denominator=48,
        urgent_failures=sum(missed(r) for r in urgent),normal_failures=sum(missed(r) for r in normal),
        urgent_p95_ms=times[math.ceil(.95*len(times))-1] if times else None,
        normal_mean_response_ms=statistics.mean((response(r)-r['scheduled_arrival_ns'])/1e6 for r in normal),
        energy_j_conditional_mA=common_j,energy_full_coverage=power['full_energy_j'] is not None,
        energy_coverage_s=power['covered_s'],initial_ap_c=float(approval['ap_c']),
        ap_peak_c=max(float(e['AP']) for e in ap) if not unfinished else None,
        ap_end_c=float(ap[-1]['AP']),actual_parallel_s=observed.lane_overlap_s(rows),
        first_battery_percent=samples[0]['battery_level'],last_battery_percent=samples[-1]['battery_level'],
        power_save_mode_observed=any(e.get('power_save_mode',False) for e in samples),
        warmup=8,runtime_creations=4,explicit_inference=104,
        scope='replayed predetermined schedule; actual arrival denominators; not online scheduler performance')


def run(plan_file,adb,serial):
    check(plan_file);plan=p.read(plan_file);root=Path(plan['output_root']);registry=Path(plan['registry'])
    require(shutil.disk_usage(BASE).free>4*1024**3,'host space before claim')
    root.mkdir();registry.mkdir();clock=time.monotonic();hard=clock+5400;active_end=hard-600
    claim=dict(utc=legacy.utc(),plan_sha256=p.digest(plan_file),host_monotonic=clock,hard_deadline_monotonic=hard,
        active_deadline_monotonic=active_end,budget=BUDGET,approval=plan['approval'],new_data_fit_calls=0)
    write(registry/'claimed.json',claim);(root/'frozen_collection_plan.json').write_bytes(Path(plan_file).read_bytes())
    owner=root/'owner.lock';write(owner,dict(pid=__import__('os').getpid(),task=NAME,utc=legacy.utc()))
    d=ObservedDevice(adb,serial,root/'host_commands',allow_other_transports=True)
    d.command_limit=BUDGET['adb_commands']-100;d.deadline=active_end;d.thermal_timeout_seconds=3
    complete=[];current=None;remote=None;identified=False;cleanup_attempted=False;installation=None
    try:
        folder=root/'installation';folder.mkdir()
        installation=device.installation(d,plan,plan_file,folder,active_end);identified=True
        require(installation['install_attempts']<=1,'install cap')
        for e in plan['entries']:
            if e['index']:
                require(active_end-time.monotonic()>=90+765,'intersession reservation')
                until=time.monotonic()+90
                while time.monotonic()<until:time.sleep(min(1,until-time.monotonic()))
            require(active_end-time.monotonic()>=765,'whole session reserved')
            current=root/f"{e['index']:02d}_{e['session_id']}";current.mkdir();remote=None;cleanup_attempted=False
            started=time.monotonic();session_end=min(active_end,started+765);d.deadline=min(started+120,session_end-590)
            device.gates(d,plan,current,'before_session')
            require(installed.installed_hash(d,plan['apk_preflight']['candidate'])==plan['apk_sha256'],'installed hash drift')
            write(current/'attempt.json',dict(entry=e,utc=legacy.utc(),plan_sha256=p.digest(plan_file)))
            mf=Path(plan_file).parent/e['manifest'];m=p.read(mf)
            (current/'input_manifest.json').write_bytes(mf.read_bytes())
            remote=shared.stage_inputs(d,e['session_id'],mf,{k:v['path'] for k,v in plan['source_files'].items()},arrival.c.PROTOCOL)
            d.deadline=session_end-105
            write(current/'launch_attempt.json',dict(utc=legacy.utc(),policy_scope='fixed-plan replay'))
            d.call('shell','am','start','-W','-n',legacy.PACKAGE+'/'+arrival.ACTIVITY,'-a',arrival.ACTION,
                '--es','session_id',e['session_id'],timeout=20)
            arrival.poll(d,remote,current,m,plan)
            d.deadline=min(session_end-45,time.monotonic()+60)
            write(current/'recovery.json',device.recover(d,remote,current/'artifacts'))
            cleanup_attempted=True;write(current/'host_cleanup.json',shared.cleanup(d,session_end))
            stats=validate(current,m,plan);stats.update(index=e['index'],arm=e['arm'],source_policy=e['source_policy'],
                elapsed_seconds=time.monotonic()-started)
            write(current/'validated.json',stats);complete.append(stats)
            write(root/f"checkpoint_{e['index']:02d}.json",dict(completed_sessions=len(complete),adb_commands=d.sequence,
                remaining_active_seconds=active_end-time.monotonic(),statistics=stats))
        pairs=[]
        for a,b in ((0,1),(3,2)):
            matched=abs(complete[a]['initial_ap_c']-complete[b]['initial_ap_c'])<=.5
            pairs.append(dict(band_index=a,candidate_index=b,initial_ap_matched=matched,
                initial_ap_difference_c=complete[b]['initial_ap_c']-complete[a]['initial_ap_c']))
        result=dict(status='completed_descriptive_only',sessions=len(complete),work_requests=384,warmup=32,
            explicit_inference=416,runtime_creations=16,installation=installation,adb_commands=d.sequence,
            elapsed_seconds=time.monotonic()-clock,pairs=pairs,new_data_fit_calls=0,online_policy_runs=0,
            source_schedule_replays=4,experiment_ready=False)
        write(root/'FINAL_RECEIPT.json',result);write(registry/'completed.json',result)
        return result
    except BaseException as exc:
        failure=dict(status='stopped_no_resume',error=repr(exc),traceback=traceback.format_exc(),
            completed_sessions=len(complete),launch_attempts=len(list(root.glob('*/launch_attempt.json'))),
            installation=installation,new_data_fit_calls=0,missing_consumption_not_zero=True)
        if identified and remote and current:
            d.deadline=min(hard-45,time.monotonic()+60)
            try:write(current/'failure_recovery.json',device.recover(d,remote,current/'failure_artifacts',True))
            except BaseException as ex:failure['recovery_error']=repr(ex)
        if identified and not cleanup_attempted:
            d.command_limit=BUDGET['adb_commands'];d.deadline=hard;cleanup_attempted=True
            try:failure['cleanup']=shared.cleanup(d,hard)
            except BaseException as ex:failure['cleanup_error']=repr(ex)
        prefix=current/'failure_artifacts/progress.jsonl' if current else None
        events,partial=arrival.c.old.progress_prefix(prefix.read_bytes() if prefix and prefix.exists() else b'')
        failure.update(adb_commands=d.sequence,elapsed_seconds=time.monotonic()-clock,
            last_session_counts={k:sum(e.get('kind')==k for e in events) for k in
                ('runtime_start','runtime_return','warmup_start','warmup_return','request_start','lane_available')},
            last_session_event=events[-1] if events else None,partial_lines=partial)
        write(root/'FINAL_RECEIPT.json',failure);write(registry/'stopped.json',failure)
        raise
    finally:
        if owner.exists():owner.unlink()


if __name__=='__main__':
    cli=argparse.ArgumentParser();cli.add_argument('action',choices=['prepare','check','run'])
    cli.add_argument('--schedules');cli.add_argument('--plan',default=str(BASE/'plan/collection_plan.json'))
    cli.add_argument('--adb',default='adb');cli.add_argument('--serial');a=cli.parse_args()
    result=prepare(a.schedules) if a.action=='prepare' else check(a.plan) if a.action=='check' else run(a.plan,a.adb,a.serial)
    print(json.dumps(result,ensure_ascii=False,indent=2))
