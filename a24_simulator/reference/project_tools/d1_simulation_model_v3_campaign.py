"""Four new fixed arrival confirmations of a previously frozen numerical model."""
import argparse
import copy
import hashlib
import json
import math
import time
from pathlib import Path
import os
import uuid

from tools import d1_arrival_plan as p
from tools import d1_simulation_model_v2_campaign as old
from tools import d1_simulation_model_v3 as model
from tools import d1_arrival_timing_calibration as calibration
from tools import d1_separated_power_protocol as separated

ROOT=model.ROOT
NAME='SIM-MODEL-V3-EXPERT-CONFIRM-01'
POLICIES=('CPU_URGENT_ONLINE_V1','B2_PARALLEL_ONLINE_V1','B2_PARALLEL_ONLINE_V1','CPU_URGENT_ONLINE_V1')
progress_consumption=old.progress_consumption


def budget(low_battery=False):
    per=4*(math.ceil(485/2)+1)+2*(math.ceil(485/10)+1)+300
    result=dict(sessions=4,development=0,confirmation=4,work_requests=384,eligibility_requests=0,
        diagnostic_requests=384,warmup=32,explicit_inference=416,runtime_creations=16,
        staging=4,staged_files=28,installed_host_pulls=1,apk_transfers=0,installs=0,
        retry=0,replacement=0,additional=0,fixed_observation_seconds=840,
        installed_preflight_seconds=600,installation_seconds=0,intersession_cooling_seconds=90,
        stage_gate_seconds=120,launch_seconds=20,host_poll_seconds=485,recovery_seconds=60,
        cleanup_seconds=45,validation_slack_seconds=35,session_seconds=765,
        freeze_seconds=0,analysis_seconds=600,total_seconds=4530,
        pre_cleanup_command_slots=200+4*per,adb_command_slots=200+4*(per+50),adb_commands=200+4*per)
    if low_battery:result.update(apk_transfers=1,installs=1,installation_seconds=600,total_seconds=5130,apk_push_timeout_seconds=180)
    return result


def sources():
    return calibration.code_identity()|model.source_identity()|{name:p.digest(ROOT/name) for name in (
        'tools/d1_simulation_model_v3_campaign.py','tools/d1_simulation_model_v3_prediction.py','tools/d1_energy_collection_device.py',
        'docs/SIMULATION_MODEL_V3_LOW_BATTERY_20261010.md','docs/SIMULATION_MODEL_V3_OBSERVATION_REPAIR_20261010.md',
        'docs/SIMULATION_MODEL_V3_HYBRID_20261010.md')}


def hybrid_budget():
    b=budget(False);b.update(sessions=2,confirmation=2,work_requests=192,diagnostic_requests=192,
        warmup=16,explicit_inference=208,runtime_creations=8,staging=2,staged_files=14,
        fixed_observation_seconds=420,total_seconds=2820,pre_cleanup_command_slots=2952,
        adb_command_slots=3052,adb_commands=2952)
    return b


def prepare_hybrid(folder,parent_run):
    folder=Path(folder).resolve();parent_run=Path(parent_run).resolve()
    if folder.exists():raise ValueError('new posthoc hybrid plan only')
    parent_plan=p.read(parent_run.parent/'plan/collection_plan.json');terminal=p.read(parent_run/'FINAL_RECEIPT.json')
    if terminal['sessions']!=4 or not terminal['status'].startswith('completed_'):raise ValueError('completed first experiment required')
    parent=Path(parent_plan['prior_freeze']['path']);frozen=p.read(parent)
    if p.digest(parent)!=parent_plan['prior_freeze']['sha256']:raise ValueError('parent thermal freeze changed')
    candidate=copy.deepcopy(frozen['model']);original=p.read(model.v2.prior.MODEL)
    candidate['energy']=model.baseline_head(original,'energy')|dict(energy_mode='frozen_original_exact',energy_fit_calls=0,
        ridge_not_applied=True,original_sha256=model.v2.prior.MODEL_SHA)
    candidate.update(variant='thermal_only_hybrid_v1',parent_model_sha256=p.digest(parent.parent/'model.json'),
        composition_is_posthoc=True,energy_decrease_claim=False,service_decrease_claim=False)
    hybrid=copy.deepcopy(frozen);hybrid.update(model=candidate,fit_calls=0,parent_fit_calls=frozen['fit_calls'],
        parent_candidate_freeze=dict(path=str(parent),sha256=p.digest(parent)),
        composition_scope='posthoc energy rejection; thermal unchanged from preregistered candidate; new2 confirmation follows',
        source_code=model.source_identity(),nested=[r for r in frozen['nested'] if r['head']=='thermal'],
        selection=dict(thermal=frozen['selection']['thermal'],energy=dict(selected=dict(choice=dict(lambda_=100.,gain=0.)),
            fit_performed=False,mode='frozen_original_exact',profiles=[])))
    development=folder.parent/'hybrid_development';development.mkdir(parents=True)
    old.write(development/'development_freeze.json',hybrid);old.write(development/'model.json',candidate)
    old.write(development/'freeze_receipt.json',dict(sha256=p.digest(development/'development_freeze.json'),fit_calls=0,
        parent_candidate_sha256=p.digest(parent),thermal_exact_equal=True,energy_exact_original=True))
    # Registration preserves the exact v2 control and the original source inventory.
    old.write(development/'registration.json',p.read(parent.parent/'registration.json'))
    plan=copy.deepcopy(parent_plan)
    for key in ('model_v3_observation_repair','original_deadline_monotonic','original_confirmation_run','cumulative_amendment'):
        plan.pop(key,None)
    name=NAME+'-THERMAL-HYBRID-01';contract=ROOT/'docs/SIMULATION_MODEL_V3_HYBRID_20261010.md'
    plan.update(experiment_id=name,model_v3_hybrid=True,source_code=sources(),budget=hybrid_budget(),autonomous_diagnostic_only=False,
        output_root=str(folder.parent/'run'),registry=str(folder.parent/'registry'),plan_file=str(folder/'collection_plan.json'),
        prior_freeze=dict(path=str(development/'development_freeze.json'),sha256=p.digest(development/'development_freeze.json')),
        hybrid_contract=dict(path=str(contract),sha256=p.digest(contract)),
        parent_completed_experiment=dict(path=str(parent_run/'FINAL_RECEIPT.json'),sha256=p.digest(parent_run/'FINAL_RECEIPT.json')),
        parent_candidate_freeze=hybrid['parent_candidate_freeze'])
    original_entries=plan['entries'];plan['entries']=[];manifests=[]
    old_folder=parent_run.parent/'plan'
    for i in range(2):
        entry=copy.deepcopy(original_entries[i]);m=p.read(old_folder/entry['manifest'])
        sid=str(uuid.uuid5(uuid.NAMESPACE_URL,name+'/'+str(i)));phase=f'hybrid_confirmation_{i}_'+entry['profile']
        entry.update(index=i,session_id=sid,phase=phase,manifest='manifests/'+sid+'.json')
        m.update(experiment_id=name,session_id=sid,phase=phase)
        for r in m['requests']:r['request_id']=str(uuid.uuid5(uuid.NAMESPACE_URL,sid+'/'+str(r['ordinal'])))
        for spec in m['models'].values():spec['identity']['session_id']=sid
        entry['manifest_sha256']=hashlib.sha256(p.canonical(m)).hexdigest();plan['entries'].append(entry);manifests.append(m)
    folder.mkdir(parents=True)
    for e,m in zip(plan['entries'],manifests):old.write(folder/e['manifest'],m)
    old.write(folder/'collection_plan.json',plan)
    return check(folder/'collection_plan.json')


def observation_repair_budget():
    b=budget(False);b['adb_command_slots']=5785
    return b


def prepare_observation_repair(folder,previous):
    folder=Path(folder).resolve();previous=Path(previous).resolve()
    if folder.exists():raise ValueError('new repaired observation plan only')
    plan=copy.deepcopy(p.read(previous.parent/'plan/collection_plan.json'));failed=p.read(previous/'FINAL_RECEIPT.json')
    if failed['status']!='stopped_no_resume' or failed['completed_sessions']!=0 or failed['adb_command_slots']!=119 or failed['host_cleanup']['status']!='completed':
        raise ValueError('exact preserved premeasurement failure required')
    if 'status=timeout' not in failed['error'] or 'thermalservice' not in failed['exception_stack']:raise ValueError('different failure; no generic retry')
    clock=p.read(previous/'host_checkpoints/0000.json')
    deadline=clock['monotonic']+plan['budget']['total_seconds']-1
    if deadline-time.monotonic()<4530:raise ValueError('original full-session reservation exhausted')
    name=NAME+'-LOW-BATTERY-01-OBSERVATION-REPAIR-01';contract=ROOT/'docs/SIMULATION_MODEL_V3_OBSERVATION_REPAIR_20261010.md'
    plan.update(experiment_id=name,model_v3_observation_repair=True,thermal_timeout_seconds=3,
        source_code=sources(),budget=observation_repair_budget(),autonomous_diagnostic_only=False,
        output_root=str(folder.parent/'run'),registry=str(folder.parent/'registry'),plan_file=str(folder/'collection_plan.json'),
        original_deadline_monotonic=deadline,original_confirmation_run=str(previous),
        observation_repair_contract=dict(path=str(contract),sha256=p.digest(contract)),
        prior_failure_receipt=dict(path=str(previous/'FINAL_RECEIPT.json'),sha256=p.digest(previous/'FINAL_RECEIPT.json')),
        cumulative_amendment=dict(physical_attempts_upper=5,runtime_creations_upper=20,explicit_inference_upper=520,
            prior_adb_slots=119,global_adb_slots=5904,staged_files_upper=35,installs_total=1))
    manifests=[]
    old_parent=previous.parent/'plan'
    for e in plan['entries']:
        m=p.read(old_parent/e['manifest']);sid=str(uuid.uuid5(uuid.NAMESPACE_URL,name+'/'+str(e['index'])))
        e.update(session_id=sid,manifest='manifests/'+sid+'.json');m.update(session_id=sid,experiment_id=name)
        for row in m['requests']:row['request_id']=str(uuid.uuid5(uuid.NAMESPACE_URL,sid+'/'+str(row['ordinal'])))
        for spec in m['models'].values():spec['identity']['session_id']=sid
        e['manifest_sha256']=hashlib.sha256(p.canonical(m)).hexdigest();manifests.append(m)
    folder.mkdir(parents=True)
    for e,m in zip(plan['entries'],manifests):old.write(folder/e['manifest'],m)
    old.write(folder/'collection_plan.json',plan)
    return check(folder/'collection_plan.json')


def prepare(folder,development,build_receipt=None,low_battery=False):
    folder=Path(folder).resolve();development=Path(development).resolve()
    if folder.exists():raise ValueError('new model-v3 confirmation plan only')
    frozen=development/'development_freeze.json';receipt=p.read(development/'freeze_receipt.json');fr=p.read(frozen)
    if p.digest(frozen)!=receipt['sha256'] or fr['source_code']!=model.source_identity():raise ValueError('frozen candidate/source drift')
    prior_plan=ROOT/'output/model_v2_20261010_v1/user_resume/plan/collection_plan.json'
    prior=p.read(prior_plan);plan=copy.deepcopy(prior)
    for key in list(plan):
        if key.startswith(('model_v2_','original_deadline_','original_clock_','original_run_','user_pause_','physical_attempt_','prior_stopped_')):plan.pop(key)
    name=NAME+'-LOW-BATTERY-01' if low_battery else NAME
    plan.update(experiment_id=name,simulation_model_v2=False,simulation_model_v3=True,
        budget=budget(low_battery),source_code=sources(),entries=[],autonomous_diagnostic_only=low_battery,
        output_root=str(folder.parent/'run'),registry=str(folder.parent/'registry'),plan_file=str(folder/'collection_plan.json'),
        prior_freeze=dict(path=str(frozen),sha256=p.digest(frozen)),
        analysis_contract=dict(path=str(model.PLAN),sha256=p.digest(model.PLAN)),
        prior_completed_task=dict(path=str(prior_plan),sha256=p.digest(prior_plan),reuse_data=False),
        diagnostic_only=True,experiment_ready=False,
        measurement_protocol_change='new task/four independent arrival confirmations; unchanged APK/runtime/96 alternate350ms/clock/quality gates',
        analysis=dict(version=model.VERSION,post_confirmation_fit_calls=0,accuracy_pass=None))
    if low_battery:
        if build_receipt is None:raise ValueError('new native gate needs build receipt')
        receipt_path=Path(build_receipt).resolve();built=p.read(receipt_path)
        from tools import d1_apk_identity as apk
        candidate=apk.inspect(built['apk_path'],plan['apk_preflight']['toolchain'])
        if candidate['signer_sha256']!=plan['apk_preflight']['candidate']['signer_sha256']:raise ValueError('project signer changed')
        amendment=ROOT/'docs/SIMULATION_MODEL_V3_LOW_BATTERY_20261010.md'
        plan.update(model_v3_low_battery=True,battery_start_percent=6,battery_min_percent=6,
            measurement_amendment=dict(path=str(amendment),sha256=p.digest(amendment)),
            apk_path=built['apk_path'],apk_sha256=built['apk_sha256'],build_receipt=str(receipt_path),build_receipt_sha256=p.digest(receipt_path),
            apk_preflight=dict(plan['apk_preflight'],candidate=candidate))
    build=p.read(plan['build_receipt'])
    if calibration.apk_sources(build['source_code'])!=calibration.apk_sources(calibration.code_identity()):raise ValueError('installed APK compiled source changed')
    manifests=[]
    for i,policy in enumerate(POLICIES):
        template=prior['entries'][6 if policy=='CPU_URGENT_ONLINE_V1' else 7]
        m=p.read(prior_plan.parent/template['manifest']);sid=str(uuid.uuid5(uuid.NAMESPACE_URL,name+'/'+str(i)))
        profile='ARRIVAL_CPU96' if policy=='CPU_URGENT_ONLINE_V1' else 'ARRIVAL_PAR96'
        phase=f'blind_confirmation_{i}_{profile}'
        m.update(experiment_id=name,session_id=sid,phase=phase,identification_role='confirmation',identification_profile=profile,
            model_v3_confirmation_version='frozen-cost-confirmation-v1',policy_study_role='confirmation',apk_sha256=plan['apk_sha256'])
        if low_battery:m.update(battery_min_percent=6,low_battery_diagnostic_version='model-v3-arrival-low-battery-v1')
        for row in m['requests']:row['request_id']=str(uuid.uuid5(uuid.NAMESPACE_URL,sid+'/'+str(row['ordinal'])))
        for spec in m['models'].values():spec['identity']['session_id']=sid;spec['target']['apk_sha256']=plan['apk_sha256']
        relative='manifests/'+sid+'.json';manifests.append(m)
        plan['entries'].append(dict(index=i,role='confirmation',phase=phase,profile=profile,family='arrival',
            protocol=m['protocol'],pair='CG_DC',mode='calibration',session_id=sid,manifest=relative,
            manifest_sha256=hashlib.sha256(p.canonical(m)).hexdigest(),work_requests=96,eligibility_requests=0,warmup=8,runtime_creations=4))
    folder.mkdir(parents=True)
    for e,m in zip(plan['entries'],manifests):old.write(folder/e['manifest'],m)
    old.write(folder/'collection_plan.json',plan)
    return check(folder/'collection_plan.json')


def check(file):
    file=Path(file);plan=p.read(file)
    low=bool(plan.get('model_v3_low_battery'));repair=bool(plan.get('model_v3_observation_repair'));hybrid=bool(plan.get('model_v3_hybrid'))
    name=NAME+'-THERMAL-HYBRID-01' if hybrid else NAME+'-LOW-BATTERY-01-OBSERVATION-REPAIR-01' if repair else NAME+'-LOW-BATTERY-01' if low else NAME
    expected=hybrid_budget() if hybrid else observation_repair_budget() if repair else budget(low)
    if plan['experiment_id']!=name or not plan.get('simulation_model_v3') or plan['budget']!=expected:raise ValueError('confirmation identity/budget')
    if Path(plan['registry']).exists() or Path(plan['output_root']).exists():raise ValueError('single-use plan consumed; no retry')
    if plan['source_code']!=sources():raise ValueError('confirmation source drift')
    for spec in (plan['prior_freeze'],plan['analysis_contract'],plan['original_model'],plan['prior_completed_task']):
        if p.digest(spec['path'])!=spec['sha256']:raise ValueError('frozen artifact/reference changed')
    fr=p.read(plan['prior_freeze']['path'])
    if fr['source_code']!=model.source_identity() or fr['plan_sha256']!=plan['analysis_contract']['sha256']:raise ValueError('development source contract changed')
    for path,h in fr['source_inventory']['files'].items():
        if p.digest(path)!=h:raise ValueError('development source evidence changed')
    if p.digest(plan['apk_path'])!=plan['apk_sha256'] or p.digest(plan['build_receipt'])!=plan['build_receipt_sha256']:raise ValueError('installed candidate artifact drift')
    if low:
        spec=plan['measurement_amendment']
        if p.digest(spec['path'])!=spec['sha256'] or plan['battery_start_percent']!=6 or plan['battery_min_percent']!=6:raise ValueError('user low battery contract drift')
    if repair:
        for spec in (plan['prior_failure_receipt'],plan['observation_repair_contract']):
            if p.digest(spec['path'])!=spec['sha256']:raise ValueError('original failure/repair contract changed')
        if plan['thermal_timeout_seconds']!=3 or expected['adb_command_slots']+119!=5904:raise ValueError('observation-only timeout/global cap drift')
    count=2 if hybrid else 4
    if len(plan['entries'])!=count:raise ValueError('new confirmation denominator')
    if hybrid:
        for spec in (plan['hybrid_contract'],plan['parent_completed_experiment'],plan['parent_candidate_freeze']):
            if p.digest(spec['path'])!=spec['sha256']:raise ValueError('hybrid parent/contract drift')
        if fr['model']['thermal']!=p.read(plan['parent_candidate_freeze']['path'])['model']['thermal']:
            raise ValueError('posthoc thermal refitting forbidden')
        original=p.read(plan['original_model']['path'])
        if fr['model']['energy']['increments']!=original['energy_increment_w'] or fr['model']['energy']['gain']!=0:
            raise ValueError('hybrid energy must exactly preserve original')
    for e,policy in zip(plan['entries'],POLICIES[:count]):
        path=file.parent/e['manifest'];m=p.read(path)
        if p.digest(path)!=e['manifest_sha256'] or m['policy']!=policy or e['role']!='confirmation' or e.get('completed_reuse'):
            raise ValueError('fixed CPU/PAR/PAR/CPU manifest/role')
        separated.validate('confirmation',m['requests'])
        if (len(m['requests']),m['resident_baseline_seconds'],m['common_window_seconds'],m['cooling_seconds'],m['power_sample_period_ms'])!=(96,30,120,60,900):
            raise ValueError('native measurement contract changed')
        if low and (m.get('battery_min_percent'),m.get('low_battery_diagnostic_version'))!=(6,'model-v3-arrival-low-battery-v1'):
            raise ValueError('missing native opt-in low battery gate')
    for spec in [*plan['source_files'].values(),*plan['references'].values()]:
        if p.digest(spec['path'])!=spec['sha256']:raise ValueError('native input/quality reference changed')
    return dict(status='READY_NEW_INDEPENDENT_CONFIRMATION',plan_sha256=p.digest(file),budget=expected,device_commands=0,experiment_ready=False)


def summarize_session(folder,manifest,plan):
    result=old.summarize_session(folder,manifest,plan)
    events,_=old.resident.old.progress_prefix((Path(folder)/'progress.jsonl').read_bytes())
    samples=[r for r in events if r['kind']=='power_sample']
    if plan.get('model_v3_low_battery'):
        if not samples or any(r.get('battery_min_percent')!=6 or r.get('low_battery_diagnostic_version')!='model-v3-arrival-low-battery-v1'
            or not isinstance(r.get('battery_level'),int) or not 6<=r['battery_level']<=100 or r.get('battery_scale')!=100 or not isinstance(r.get('power_save_mode'),bool) for r in samples):
            raise ValueError('native low battery sample/version missing')
    result['battery_scope']=dict(minimum_observed_percent=min(r['battery_level'] for r in samples),
        any_below20=any(r['battery_level']<20 for r in samples),power_save_mode_observed=any(r.get('power_save_mode',False) for r in samples),
        admitted_minimum=6 if plan.get('model_v3_low_battery') else 20)
    return result


def evaluate(stats,frozen,plan):
    original=p.read(plan['original_model']['path'])
    return model.cost_assessment(stats['analysis_case'],frozen['model'],original)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','check','run'])
    parser.add_argument('--output');parser.add_argument('--development');parser.add_argument('--plan');parser.add_argument('--serial');parser.add_argument('--receipt');parser.add_argument('--low-battery',action='store_true');parser.add_argument('--observation-repair-source');parser.add_argument('--hybrid-parent-run');a=parser.parse_args()
    if a.action=='prepare':result=prepare_hybrid(a.output,a.hybrid_parent_run) if a.hybrid_parent_run else prepare_observation_repair(a.output,a.observation_repair_source) if a.observation_repair_source else prepare(a.output,a.development,a.receipt,a.low_battery)
    elif a.action=='check':result=check(a.plan)
    else:
        from tools import d1_energy_collection_device as device
        result=device.run(a.plan,os.environ.get('D1CHECK_ADB','adb'),a.serial,p.digest(a.plan),True)
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
