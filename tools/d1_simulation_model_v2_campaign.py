"""Single-use model-v2 campaign. No connection changes; existing bounded collectors."""
import argparse
import copy
import csv
import hashlib
import json
import math
import statistics
import subprocess
import sys
import uuid
import shutil
import time
from pathlib import Path
import os
from tools import d1_simulation_model_v2 as model
from tools import d1_resident_identification_plan as resident
from tools import d1_arrival_timing_calibration as calibration
from tools import d1_arrival_plan as p
from tools import d1_apk_identity as apk
from tools import d1_separated_power_protocol as separated

ROOT=model.ROOT
EXTERNAL=Path(os.environ.get('D1CHECK_ARRIVAL_EXTENSION', str(Path.home()/'Documents'/'D1Check_Arrival_Extension')))
NAME='SIM-MODEL-V2-01'
PROFILES=('MODEL2_RECOVERY_A','MODEL2_RECOVERY_B','MODEL2_RECOVERY_B','MODEL2_RECOVERY_A','MODEL2_RECOVERY_A','MODEL2_RECOVERY_B','ARRIVAL_CPU96','ARRIVAL_PAR96')
progress_consumption=resident.progress_consumption


def write(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    calibration.write_new(path,value)


def budget():
    counts=[resident.profile_budget(s)['work_requests'] if not s.startswith('ARRIVAL') else 96 for s in PROFILES]
    poll=1500;per=4*(math.ceil(poll/2)+1)+2*(math.ceil(poll/10)+1)+300
    return dict(sessions=8,development=4,confirmation=4,work_requests=sum(counts),eligibility_requests=24,
        diagnostic_requests=sum(counts)+24,warmup=64,explicit_inference=sum(counts)+88,runtime_creations=32,
        staging=8,staged_files=56,installed_host_pulls=1,apk_transfers=1,installs=1,
        retry=0,replacement=0,additional=0,fixed_observation_seconds=5208,preparation_fixed_seconds=720,
        fixed_intersession_seconds=630,intersession_cooling_seconds=90,installation_seconds=600,
        installed_preflight_seconds=600,stage_gate_seconds=120,host_poll_seconds=poll,recovery_seconds=60,
        cleanup_seconds=45,launch_seconds=20,validation_slack_seconds=35,session_seconds=1780,
        freeze_seconds=600,analysis_seconds=600,total_seconds=16670,preparation_max_wait_seconds=360,
        apk_push_timeout_seconds=180,pre_cleanup_command_slots=200+8*per,
        adb_command_slots=200+8*(per+50),adb_calculation=dict(listing=751,thermal=2253,screen=151,heartbeat=151,stage_archive_reserve=300,per_session_normal=per),
        profiles=[dict(profile=s,work_requests=n) for s,n in zip(PROFILES,counts)])


def sources():
    return calibration.code_identity()|{x:p.digest(ROOT/x) for x in ('tools/d1_simulation_model_v2.py','tools/d1_simulation_model_v2_campaign.py','tools/d1_resident_identification_plan.py','tools/d1_resident_identification_analysis.py','tools/d1_energy_collection_device.py','docs/SIMULATION_MODEL_V2_PLAN_20261010.md','docs/SIMULATION_MODEL_V2_REPAIR_20261010.md','docs/SIMULATION_MODEL_V2_ARRIVAL_REPAIR_20261010.md','docs/SIMULATION_MODEL_V2_RESUME_20261010.md')}


def repair_budget():
    b=budget();b.update(sessions=7,cohort_sessions=8,reused_measured_windows=1,development_fresh=3,
        work_requests=6432,eligibility_requests=20,diagnostic_requests=6452,warmup=56,explicit_inference=6508,
        runtime_creations=28,staging=7,staged_files=49,fixed_observation_seconds=4410,preparation_fixed_seconds=600,
        total_seconds=14890,pre_cleanup_command_slots=200+7*3606,adb_command_slots=200+7*3656)
    return b


def arrival_repair_budget():
    # Two fresh arrivals only. All six completed measured windows are copied byte-for-byte.
    b=budget();per=4*(math.ceil(485/2)+1)+2*(math.ceil(485/10)+1)+300
    b.update(sessions=2,cohort_sessions=8,reused_measured_windows=6,development_fresh=0,
        work_requests=192,eligibility_requests=0,diagnostic_requests=192,warmup=16,explicit_inference=208,
        runtime_creations=8,staging=2,staged_files=14,apk_transfers=0,installs=0,
        fixed_observation_seconds=420,preparation_fixed_seconds=0,host_poll_seconds=485,
        fixed_intersession_seconds=90,session_seconds=765,freeze_seconds=0,total_seconds=2820,
        pre_cleanup_command_slots=200+2*per,adb_command_slots=200+2*(per+50))
    b['adb_commands']=b['pre_cleanup_command_slots']
    return b


def resume_budget():
    b=arrival_repair_budget()
    b.update(sessions=1,reused_measured_windows=7,work_requests=96,diagnostic_requests=96,warmup=8,
        explicit_inference=104,runtime_creations=4,staging=1,staged_files=7,
        fixed_observation_seconds=210,total_seconds=2055,pre_cleanup_command_slots=1576,adb_command_slots=1626)
    b['adb_commands']=b['pre_cleanup_command_slots']
    return b


def prepare_resume(folder,previous):
    folder=Path(folder).resolve();previous=Path(previous).resolve()
    if folder.exists():raise ValueError('new resume plan only')
    old=p.read(previous.parent/'plan/collection_plan.json');paused=previous/'USER_PAUSE_RECEIPT.json';receipt=p.read(paused)
    if receipt['status']!='paused_by_user_no_automatic_resume' or receipt['validated_sessions']!=7 or receipt['application_cleanup']['status']!='completed':
        raise ValueError('requires seven preserved measured windows and completed user-stop cleanup')
    if old['original_deadline_monotonic']-time.monotonic()<resume_budget()['total_seconds']:
        raise ValueError('original wall-clock reserve insufficient; do not reset clock')
    for name,h in receipt['preserved_validated_sha256'].items():
        if p.digest(previous/name)!=h:raise ValueError('paused completed evidence changed')
    freeze=previous/'development_freeze.json'
    if p.digest(freeze)!=receipt['development_freeze_sha256']:raise ValueError('paused freeze changed')
    plan=copy.deepcopy(old);name=NAME+'-USER-RESUME-01';contract=ROOT/'docs/SIMULATION_MODEL_V2_RESUME_20261010.md'
    plan.update(experiment_id=name,model_v2_user_resume=True,budget=resume_budget(),source_code=sources(),
        output_root=str(folder.parent/'run'),registry=str(folder.parent/'registry'),plan_file=str(folder/'collection_plan.json'),
        analysis_contract=dict(path=str(contract),sha256=p.digest(contract)),model_v2_prior_completed=[],
        user_pause_source=dict(path=str(paused),sha256=p.digest(paused)),prior_freeze=dict(path=str(freeze),sha256=p.digest(freeze)))
    manifests=[];completed=0
    for e in plan['entries']:
        m=p.read(previous.parent/'plan'/e['manifest'])
        if e['index']<7:
            source=previous/f"{e['index']:02d}_{e['session_id']}";stats=p.read(source/'validated.json')
            completed+=stats['work_calls']+stats['eligibility_calls']+stats['warmup_calls']
            plan['model_v2_prior_completed'].append(dict(session_id=e['session_id'],source_folder=str(source),
                files={str(f.relative_to(source)):p.digest(f) for f in source.rglob('*') if f.is_file()}))
            e['completed_reuse']=True
        else:
            sid=str(uuid.uuid5(uuid.NAMESPACE_URL,name+'/'+str(e['index'])))
            e.update(session_id=sid,manifest='manifests/'+sid+'.json')
            e.pop('completed_reuse',None);m.update(session_id=sid,experiment_id=name)
            for r in m['requests']:r['request_id']=str(uuid.uuid5(uuid.NAMESPACE_URL,sid+'/'+str(r['ordinal'])))
            for spec in m['models'].values():spec['identity']['session_id']=sid
            e['manifest_sha256']=hashlib.sha256(p.canonical(m)).hexdigest()
        manifests.append(m)
    interrupted_upper=sum(receipt['partial_PAR']['counts'][k]['actual_started_upper'] for k in ('load','warmup','eligibility'))
    # Paused command logs each represent one actual subprocess invocation, including unsuccessful calls.
    command_logs=[f for directory in (previous/'host_commands',previous/'user_pause/host_commands',previous/'user_pause/recovery_commands')
        for f in directory.iterdir() if f.is_dir()]
    amendment=copy.deepcopy(old['physical_attempt_cap_amendment'])
    amendment.update(amended=10,reason='user explicitly resumed after stopping PAR preparation for travel',
        paused_PAR_explicit_inference_upper=interrupted_upper,prior_completed_explicit_inference=completed,
        prior_adb_commands=amendment['prior_adb_commands']+len(command_logs),
        global_explicit_inference_upper=completed+amendment['failed_attempt_explicit_inference_upper']+interrupted_upper+104)
    if amendment['global_explicit_inference_upper']>7768 or amendment['prior_adb_commands']+resume_budget()['adb_command_slots']>29448:
        raise ValueError('original cumulative inference/ADB cap exhausted')
    plan['physical_attempt_cap_amendment']=amendment
    folder.mkdir(parents=True)
    for e,m in zip(plan['entries'],manifests):write(folder/e['manifest'],m)
    write(folder/'collection_plan.json',plan)
    return check(folder/'collection_plan.json')


def prepare_arrival_repair(folder,previous):
    folder=Path(folder).resolve();previous=Path(previous).resolve()
    if folder.exists():raise ValueError('new plan only')
    old=p.read(previous.parent/'plan/collection_plan.json');receipt=p.read(previous/'FINAL_RECEIPT.json')
    if receipt['status']!='stopped_no_resume' or receipt['error']!="KeyError('adb_commands')" or receipt['completed_sessions']!=6 or receipt['host_cleanup']['status']!='completed':
        raise ValueError('requires exact stopped host-mapping failure and completed cleanup')
    plan=copy.deepcopy(old);name=NAME+'-ARRIVAL-HOST-REPAIR-01'
    contract=ROOT/'docs/SIMULATION_MODEL_V2_ARRIVAL_REPAIR_20261010.md'
    freeze=previous/'development_freeze.json'
    if p.digest(freeze)!=p.read(previous/'freeze_receipt.json')['sha256']:raise ValueError('frozen model changed')
    plan.update(experiment_id=name,model_v2_arrival_host_repair=True,source_code=sources(),budget=arrival_repair_budget(),
        autonomous_diagnostic_only=False,output_root=str(folder.parent/'run'),registry=str(folder.parent/'registry'),
        plan_file=str(folder/'collection_plan.json'),analysis_contract=dict(path=str(contract),sha256=p.digest(contract)),
        prior_freeze=dict(path=str(freeze),sha256=p.digest(freeze)),model_v2_prior_completed=[],
        prior_stopped_receipt=dict(path=str(previous/'FINAL_RECEIPT.json'),sha256=p.digest(previous/'FINAL_RECEIPT.json')),
        physical_attempt_cap_amendment=dict(original=8,amended=9,reason='one host budget KeyError before warmup approval; no data-driven rerun',
            previous_failure_consumption=receipt['last_session_progress'],original_explicit_inference_cap=7768,
            original_adb_command_cap=29448,prior_adb_commands=receipt['adb_command_slots']+p.read(Path(old['original_run_root'])/'FINAL_RECEIPT.json')['adb_command_slots']))
    manifests=[]
    prior_explicit=0
    for e in plan['entries']:
        m=p.read(previous.parent/'plan'/e['manifest'])
        if e['index']<6:
            source=previous/f"{e['index']:02d}_{e['session_id']}"
            if not (source/'validated.json').is_file():raise ValueError('missing completed source')
            stats=p.read(source/'validated.json');prior_explicit+=stats['work_calls']+stats['eligibility_calls']+stats['warmup_calls']
            plan['model_v2_prior_completed'].append(dict(session_id=e['session_id'],source_folder=str(source),
                files={str(f.relative_to(source)):p.digest(f) for f in source.rglob('*') if f.is_file()}))
            e['completed_reuse']=True
        else:
            sid=str(uuid.uuid5(uuid.NAMESPACE_URL,name+'/'+str(e['index'])))
            e.update(session_id=sid,manifest='manifests/'+sid+'.json')
            m.update(session_id=sid,experiment_id=name)
            for r in m['requests']:r['request_id']=str(uuid.uuid5(uuid.NAMESPACE_URL,sid+'/'+str(r['ordinal'])))
            for spec in m['models'].values():spec['identity']['session_id']=sid
            e['manifest_sha256']=hashlib.sha256(p.canonical(m)).hexdigest()
        manifests.append(m)
    unknown_upper=sum(receipt['last_session_progress']['counts'][k]['actual_started_upper'] for k in ('load','warmup','eligibility'))
    if prior_explicit+unknown_upper+208>7768:raise ValueError('original global inference cap exhausted')
    if plan['physical_attempt_cap_amendment']['prior_adb_commands']+plan['budget']['adb_command_slots']>29448:raise ValueError('original global ADB cap exhausted')
    plan['physical_attempt_cap_amendment'].update(prior_completed_explicit_inference=prior_explicit,
        failed_attempt_explicit_inference_upper=unknown_upper,global_explicit_inference_upper=prior_explicit+unknown_upper+208)
    folder.mkdir(parents=True)
    for e,m in zip(plan['entries'],manifests):write(folder/e['manifest'],m)
    write(folder/'collection_plan.json',plan)
    return check(folder/'collection_plan.json')


def prepare(folder,receipt,repair_source=None):
    folder=Path(folder).resolve();receipt=Path(receipt).resolve()
    if folder.exists():raise ValueError('new plan only')
    sourcefile=EXTERNAL/'energy_ap_tail_observation_plan_v6/collection_plan.json';source=p.read(sourcefile);build=p.read(receipt)
    if calibration.apk_sources(build['source_code'])!=calibration.apk_sources(calibration.code_identity()):raise ValueError('APK/source mismatch')
    candidate=apk.inspect(build['apk_path'],source['apk_preflight']['toolchain'])
    if candidate['signer_sha256']!=source['apk_preflight']['candidate']['signer_sha256']:raise ValueError('project signature mismatch')
    plan=copy.deepcopy(source)
    for k in list(plan):
        if k.startswith(('tail_','prior_','previous_','stopped_','cached_')):plan.pop(k)
    name=NAME if repair_source is None else NAME+'-CLEANUP-REPAIR-01'
    plan.update(simulation_model_v2=True,tail_observation=False,tail_low_battery=False,
        protocol=resident.PROTOCOL,experiment_id=name,approval='user_instruction_2026-10-10',
        status='PC_READY_NEW_PLAN',budget=budget() if repair_source is None else repair_budget(),source_code=sources(),entries=[],
        original_model=dict(path=str(model.prior.MODEL),sha256=model.prior.MODEL_SHA),
        analysis_contract=dict(path=str(ROOT/'docs/SIMULATION_MODEL_V2_PLAN_20261010.md'),sha256=p.digest(ROOT/'docs/SIMULATION_MODEL_V2_PLAN_20261010.md')),
        source_plan=dict(path=str(sourcefile),sha256=p.digest(sourcefile)),build_receipt=str(receipt),build_receipt_sha256=p.digest(receipt),
        apk_path=build['apk_path'],apk_sha256=build['apk_sha256'],apk_preflight=dict(source['apk_preflight'],candidate=candidate),
        output_root=str(folder.parent/'run'),registry=str(folder.parent/'registry'),plan_file=str(folder/'collection_plan.json'),
        battery_start_percent=20,battery_min_percent=20,battery_max_temperature_tenths_c=350,
        resident_identification=True,state_model_calibration=True,autonomous_diagnostic_only=True,diagnostic_only=True,
        require_unplugged=True,experiment_ready=False,minimum_host_free_bytes=4*2**30,
        candidate_confirmation_rule='frozen descriptive comparison even if development accuracy worsens; no post-confirmation fit',
        analysis=dict(version=model.VERSION,development_fit_passes=5,thermal_service_feedback=None,accuracy_pass=None),
        measurement_protocol_change='same-session matched probes and fixed recovery anchors; six498s regimens plus two96-request arrivals; sampler900ms; no policy deployment',
        source_service_sha256=model.archive_service()['source_sha256'])
    plan.pop('run_script_sha256',None)
    base=p.read(sourcefile.parent/source['entries'][0]['manifest'])
    locations=p.read(ROOT/'docs/results/preboundary_evidence_01/run_v1/source_inventory.json')['source_locations']
    arrival_base=p.read(EXTERNAL/locations['development_30_CPU']/'input_manifest.json')
    manifests=[]
    for i,profile in enumerate(PROFILES):
        sid=str(uuid.uuid5(uuid.NAMESPACE_URL,name+'/'+str(i)));role='development' if i<4 else 'confirmation'
        m=copy.deepcopy(arrival_base if i>=6 else base)
        for k in list(m):
            if k.startswith(('tail_','history_','background_','resident_control','replay_','conditioning_')):m.pop(k)
        m.update(experiment_id=name,session_id=sid,phase=f'{role}_{i}_{profile}',identification_profile=profile,
            identification_role=role,apk_sha256=build['apk_sha256'],experiment_ready=False,model_v2_measurement_version='matched-recovery-and-arrival-v1')
        if i<6:
            m.update(protocol=resident.PROTOCOL,pair='CG_DC',mode='calibration',state_model_calibration=True,
                calibration_version=resident.VERSION,resident_identification_version=resident.VERSION,
                session_control='device-after-probe-diagnostic-v1',autonomous_diagnostic_only=True,operational_only=True,
                short_transition_diagnostic_only=False,maximum_duration_ms=1800000,common_work_seconds=498,
                baseline_seconds=120,cooling_seconds=180,work_call_cap=1248,cadence_ms=250,warmup_count=8,
                probe_counts=dict(classification=2,detection=2),start_ap_gate='numeric-ap-observe-v2',
                power_sampling_version='resident-identification-power-v1',power_sample_period_ms=900,
                blocks=resident.blocks(profile),temperature_preparation=copy.deepcopy(resident.old.operational_rules.PREPARATION))
        else:
            for k in ('state_model_calibration','resident_identification_version','calibration_version','blocks','work_call_cap','session_control','autonomous_diagnostic_only','operational_only','common_work_seconds'):m.pop(k,None)
            rows=separated.requests('confirmation',sid)
            for r in rows:r['request_id']=str(uuid.uuid5(uuid.NAMESPACE_URL,sid+'/'+str(r['ordinal'])))
            m.update(protocol='arrival-energy-synthetic-v1',policy='CPU_URGENT_ONLINE_V1' if i==6 else 'B2_PARALLEL_ONLINE_V1',
                requests=rows,policy_study_version='online-policy-model-study-v1',policy_study_role='confirmation',
                power_identification_version=separated.VERSION,scenario='separated_power',maximum_duration_ms=480000,
                common_window_seconds=120,resident_baseline_seconds=30,cooling_seconds=60,maximum_concurrency=2,
                memory_contract='android-low-memory-resident-v1',thermal_gate=0,start_ap_gate='numeric-ap-observe-v2',
                power_sampling_version='online-power-phase-audit-v1',power_sample_period_ms=900)
        for spec in m['models'].values():spec['identity']['session_id']=sid;spec['target']['apk_sha256']=build['apk_sha256']
        rel='manifests/'+sid+'.json';manifests.append(m)
        plan['entries'].append(dict(index=i,role=role,phase=m['phase'],profile=profile,family='regimen' if i<6 else 'arrival',
            protocol=m['protocol'],pair='CG_DC',mode='calibration',session_id=sid,manifest=rel,manifest_sha256=hashlib.sha256(p.canonical(m)).hexdigest(),
            work_requests=1248 if i<6 else 96,eligibility_requests=4 if i<6 else 0,warmup=8,runtime_creations=4))
    if repair_source is not None:
        previous=Path(repair_source).resolve();old_plan=p.read(previous.parent/'plan/collection_plan.json');old_receipt=p.read(previous/'FINAL_RECEIPT.json')
        if old_receipt['status']!='stopped_no_resume':raise ValueError('repair requires preserved stopped original')
        first=old_plan['entries'][0];source=previous/f"00_{first['session_id']}";old_manifest=p.read(source/'input_manifest.json')
        plan['model_v2_completed_reuse']=dict(session_id=first['session_id'],source_folder=str(source),original_receipt_sha256=p.digest(previous/'FINAL_RECEIPT.json'),
            original_plan_sha256=p.digest(previous.parent/'plan/collection_plan.json'),files={str(f.relative_to(source)):p.digest(f) for f in source.rglob('*') if f.is_file()},
            reason='post-cleanup journal-closed sampler race; original app failure preserved; measured-window descriptive eligibility only')
        clock=p.read(previous/'host_checkpoints/0000.json')
        plan['original_deadline_monotonic']=clock['monotonic']+old_plan['budget']['total_seconds']-1
        plan['original_clock_utc']=clock['utc'];plan['original_run_root']=str(previous)
        contract=ROOT/'docs/SIMULATION_MODEL_V2_REPAIR_20261010.md'
        plan['analysis_contract']=dict(path=str(contract),sha256=p.digest(contract))
        e=copy.deepcopy(first);e['completed_reuse']=True;manifests[0]=old_manifest;plan['entries'][0]=e
    folder.mkdir(parents=True)
    for e,m in zip(plan['entries'],manifests):write(folder/e['manifest'],m)
    write(folder/'collection_plan.json',plan)
    return check(folder/'collection_plan.json')


def check(file):
    file=Path(file);plan=p.read(file)
    expected=resume_budget() if plan.get('model_v2_user_resume') else arrival_repair_budget() if plan.get('model_v2_arrival_host_repair') else repair_budget() if plan.get('model_v2_completed_reuse') else budget()
    if plan['experiment_id'] not in (NAME,NAME+'-CLEANUP-REPAIR-01',NAME+'-ARRIVAL-HOST-REPAIR-01',NAME+'-USER-RESUME-01') or not plan.get('simulation_model_v2') or plan['budget']!=expected:raise ValueError('plan/budget identity')
    if Path(plan['registry']).exists() or Path(plan['output_root']).exists():raise ValueError('consumed; never retry')
    if plan['source_code']!=sources() or p.digest(plan['build_receipt'])!=plan['build_receipt_sha256'] or p.digest(plan['apk_path'])!=plan['apk_sha256']:raise ValueError('frozen source/build drift')
    if model.archive_service()['source_sha256']!=plan['source_service_sha256']:raise ValueError('archived timing drift')
    if sum(e['work_requests'] for e in plan['entries'] if not e.get('completed_reuse'))!=expected['work_requests'] or len(plan['entries'])!=8:raise ValueError('roster arithmetic')
    if plan.get('model_v2_completed_reuse'):
        reuse=plan['model_v2_completed_reuse'];source=Path(reuse['source_folder'])
        for relative,h in reuse['files'].items():
            if p.digest(source/relative)!=h:raise ValueError('reused source changed')
        if p.digest(Path(plan['original_run_root'])/'FINAL_RECEIPT.json')!=reuse['original_receipt_sha256']:raise ValueError('original failure changed')
    if plan.get('model_v2_arrival_host_repair'):
        if len(plan['model_v2_prior_completed'])!=expected['reused_measured_windows']:raise ValueError('completed measured window denominator')
        for reuse in plan['model_v2_prior_completed']:
            for relative,h in reuse['files'].items():
                if p.digest(Path(reuse['source_folder'])/relative)!=h:raise ValueError('prior completed source changed')
        for spec in (plan['prior_freeze'],plan['prior_stopped_receipt'],plan['analysis_contract']):
            if p.digest(spec['path'])!=spec['sha256']:raise ValueError('repair source drift')
        if plan.get('model_v2_user_resume'):
            spec=plan['user_pause_source']
            if p.digest(spec['path'])!=spec['sha256']:raise ValueError('pause receipt changed')
    for e,profile in zip(plan['entries'],PROFILES):
        m=p.read(file.parent/e['manifest'])
        if p.digest(file.parent/e['manifest'])!=e['manifest_sha256'] or m['identification_profile']!=profile or m['identification_role']!=e['role']:raise ValueError('manifest identity')
        if e['family']=='regimen':
            if m['blocks']!=resident.blocks(profile) or m['work_call_cap']!=1248 or m['common_work_seconds']!=498:raise ValueError('matched block drift')
        else:separated.validate('confirmation',m['requests'])
    for info in [*plan['source_files'].values(),*plan['references'].values(),plan['original_model']]:
        if p.digest(info['path'])!=info['sha256']:raise ValueError('input/reference drift')
    return dict(status='READY_FOR_USER_AUTHORIZED_RUN',plan_sha256=p.digest(file),budget=expected,device_commands=0,experiment_ready=False)


def reuse_session(entry,plan,root):
    if plan.get('model_v2_arrival_host_repair'):
        reuse=next(r for r in plan['model_v2_prior_completed'] if r['session_id']==entry['session_id'])
        source=Path(reuse['source_folder']);target=Path(root)/f"{entry['index']:02d}_{entry['session_id']}"
        for relative,h in reuse['files'].items():
            if p.digest(source/relative)!=h:raise ValueError('completed source mutation')
        shutil.copytree(source,target)
        # Keep development validation bytes identical to the original freeze inventory.
        return p.read(target/'validated.json')
    reuse=plan['model_v2_completed_reuse'];source=Path(reuse['source_folder']);target=Path(root)/f"{entry['index']:02d}_{entry['session_id']}"
    for relative,h in reuse['files'].items():
        if p.digest(source/relative)!=h:raise ValueError('source mutation before reuse')
    shutil.copytree(source,target)
    stats=summarize_session(target/'artifacts',Path(plan['plan_file']).parent/entry['manifest'],plan)
    stats.update(reused_evidence=True,new_device_calls=0,original_failure_preserved=True,source_folder=str(source))
    write(target/'validated.json',stats)
    return stats


def summarize_session(folder,manifest,plan):
    folder=Path(folder);m=p.read(manifest)
    if m['protocol']=='arrival-energy-synthetic-v1' and any((folder/name).is_file() for name in ('sampler_failure.json','session_failure.json')):
        raise ValueError('arrival application failure preserved; not a valid confirmation')
    stats=resident.summarize_session(folder,manifest,plan)
    if m['protocol']=='arrival-energy-synthetic-v1':
        stats['application_lifecycle_pass']=True
        stats['analysis_case']['manifest_requests']=m['requests'];stats['analysis_case']['actual_requests']=p.read(folder/'requests.json')
        stats['analysis_case']['origin_ns']=p.read(folder/'common_boundary.json')['start_ns']
    else:
        ev,_=resident.old.progress_prefix((folder/'progress.jsonl').read_bytes())
        rows=[r for r in ev if r['kind']=='lane_available' and r['phase']=='load']
        stats['analysis_case']['probe_rows']=[{k:r[k] for k in ('key','block','dispatch_ns','invocation_start_ns','invocation_end_ns','lane_available_ns')} for r in rows]
        eligibility=[r for r in ev if r['kind']=='lane_available' and r['phase'].startswith('eligibility_')]
        origin=stats['common_start_ns']
        if eligibility:
            relative=[dict(r,dispatch_ns=r['dispatch_ns']-origin,lane_available_ns=r['lane_available_ns']-origin) for r in eligibility]
            stats['analysis_case']['history']=model.occupancy(relative,min(r['dispatch_ns'] for r in relative),0)
            stats['analysis_case']['history_scope']='recorded eligibility probes; earlier warmup not mapped into unsupported states'
    return stats


def recovery_contrasts(cases):
    out=[]
    for c in cases:
        rows=c.get('probe_rows',[])
        if not rows:continue
        pair=[r for r in rows if r['block']=='conditioning_pair'];last=max(r['lane_available_ns'] for r in pair)
        for key in ('classification_CPU','classification_GPU','detection_CPU'):
            stages={label:[r for r in rows if r['key']==key and r['block'].startswith(label+'_solo')] for label in ('before','immediate','after90','after240')}
            if any(len(v)<3 for v in stages.values()):raise ValueError('probe denominator insufficient')
            before=statistics.mean((r['invocation_end_ns']-r['invocation_start_ns'])/1e6 for r in stages['before'])
            immediate=statistics.mean((r['invocation_end_ns']-r['invocation_start_ns'])/1e6 for r in stages['immediate'])
            for label,use in stages.items():
                mean=statistics.mean((r['invocation_end_ns']-r['invocation_start_ns'])/1e6 for r in use)
                out.append(dict(session=c['id'],role=c['role'],key=key,stage=label,n=len(use),invocation_mean_ms=mean,
                    change_from_before_percent=100*(mean/before-1),change_from_immediate_percent=100*(mean/immediate-1),
                    first_dispatch_after_pair_s=(min(r['dispatch_ns'] for r in use)-last)/1e9))
    return out


def freeze(results,plan,root):
    cases=[r['analysis_case'] for r in results]
    if len(cases)!=4 or any(c['role']!='development' for c in cases):raise ValueError('four complete development sessions required')
    original=p.read(plan['original_model']['path']);folds=[]
    for i,c in enumerate(cases):folds.append(dict(id=c['id'],assessment=model.assess(c,model.fit([x for j,x in enumerate(cases) if j!=i],original),original)))
    candidate=model.fit(cases,original);candidate['service']=model.archive_service()
    inventory={f"{e['index']:02d}_{e['session_id']}/validated.json":p.digest(Path(root)/f"{e['index']:02d}_{e['session_id']}/validated.json") for e in plan['entries'][:4]}
    return dict(version='simulation-model-v2-freeze-v1',model=candidate,folds=folds,recovery=recovery_contrasts(cases),
        development_validated_sha256=inventory,analysis_contract_sha256=plan['analysis_contract']['sha256'],
        confirmation_fit_forbidden=True,thermal_service_feedback=None,freeze_selection='fixed family; no holdout selection',experiment_ready=False)


def evaluate(stats,frozen,plan):
    return model.assess(stats['analysis_case'],frozen['model'],p.read(plan['original_model']['path']))


def archive(folder):
    from tools import d1_session_contrast_cost as archived
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=False);cases=archived.cases();original=p.read(model.prior.MODEL)
    candidate=model.fit([c for c in cases if c['role']=='development'],original);candidate['service']=model.archive_service()
    write(folder/'candidate.json',candidate);scores=[]
    for c in cases:scores.append(dict(id=c['id'],role=c['role'],result=model.assess(c,candidate,original)))
    write(folder/'evaluation.json',dict(cases=scores,data_role='already-seen archive; runtime/shape verification and posthoc comparison, not new blind confirmation',device_commands=0))
    return dict(status='ARCHIVE_MODEL_CREATED',cases=len(cases),development=len(candidate['development_ids']),fit_calls=1,device_commands=0)


def main():
    a=argparse.ArgumentParser();a.add_argument('action',choices=['prepare','check','run','archive']);a.add_argument('--output');a.add_argument('--receipt');a.add_argument('--plan');a.add_argument('--serial');a.add_argument('--repair-source');a.add_argument('--arrival-repair-source');a.add_argument('--resume-source');x=a.parse_args()
    if x.action=='prepare':result=prepare_resume(x.output,x.resume_source) if x.resume_source else prepare_arrival_repair(x.output,x.arrival_repair_source) if x.arrival_repair_source else prepare(x.output,x.receipt,x.repair_source)
    elif x.action=='check':result=check(x.plan)
    elif x.action=='archive':result=archive(x.output)
    else:
        from tools import d1_energy_collection_device as device
        result=device.run(x.plan,os.environ.get('D1CHECK_ADB','adb'),x.serial,p.digest(x.plan),True)
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
