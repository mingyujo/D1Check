"""Eight-session opt-in preparation. Check never constructs a device or a claim."""
import argparse
import copy
import hashlib
import json
import math
import shutil
import uuid
from pathlib import Path
from tools import d1_energy_collection as old
from tools import d1_arrival_timing_calibration as cal
from tools import d1_apk_identity as apk
from tools import d1_joint_model_refinement as j
from tools import d1_resident_identification_analysis as analysis

VERSION='resident-identification-regimen-v1'
PROTOCOL='energy-ap-resident-identification-v1'
NAME='ENERGY-AP-RESIDENT-IDENTIFICATION-02'
FOLDER='energy_ap_resident_identification_plan_v3'
PROFILES=('DEV_A','DEV_B','DEV_B','DEV_A','CONF_A','CONF_B','ARRIVAL_SEPARATED96','ARRIVAL_SUSTAINED192')
PUBLIC=cal.ROOT/'docs/results/resident_identification_prep_01'
CONTRACT=PUBLIC/'analysis_contract_v2.json'


def blocks(profile):
    if profile in ('CONF_MIX_A','CONF_MIX_B'):
        result=[];singles=(0,1,2) if profile=='CONF_MIX_A' else (2,1,0)
        for cycle in range(4):
            for key in singles:
                result.extend([dict(id=f'cycle{cycle}_solo{key}',lane_indices=[key],seconds=4 if key==2 else 3),dict(id=f'cycle{cycle}_idle{key}',lane_indices=[],seconds=2)])
            result.extend([dict(id=f'cycle{cycle}_pair',lane_indices=[1,2],seconds=6),dict(id=f'cycle{cycle}_tail',lane_indices=[],seconds=8)])
        return result
    orders={'DEV_A':[[0],[2],[1],[1,2]],'DEV_B':[[1,2],[1],[2],[0]],'CONF_A':[[1],[0],[1,2],[2]],'CONF_B':[[2],[1,2],[0],[1]]}
    if profile not in orders:raise ValueError('profile')
    duration=60 if profile.startswith('DEV_') else 30;result=[]
    for i,keys in enumerate(orders[profile]):
        result.append(dict(id=f'state_{i}',lane_indices=keys,seconds=duration))
        if i<3:result.append(dict(id=f'idle_{i}',lane_indices=[],seconds=90))
    return result


def profile_budget(profile):
    if profile.startswith('ARRIVAL_'):
        count={'ARRIVAL_SEPARATED96':96,'ARRIVAL_SUSTAINED192':192}[profile]
        return dict(profile=profile,family='arrival',work_requests=count,common_work_seconds=120,baseline_seconds=30,cooling_seconds=60,
                    fixed_observation_seconds=210,preparation_fixed_seconds=0,runtime_creations=4,warmup=8,eligibility_requests=0,
                    explicit_inference=count+8,session_seconds=2080,host_poll_seconds=485,stage_gate_seconds=120,recovery_seconds=60,cleanup_seconds=45,launch_seconds=20,validation_slack_seconds=35)
    b=blocks(profile);common=sum(x['seconds'] for x in b)+90
    work=sum(len(x['lane_indices'])*x['seconds']*4 for x in b)
    return dict(profile=profile,family='regimen',work_requests=work,common_work_seconds=common,baseline_seconds=120,cooling_seconds=180,
                fixed_observation_seconds=common+300,preparation_fixed_seconds=120,runtime_creations=4,warmup=8,eligibility_requests=4,
                explicit_inference=work+12,session_seconds=2080,host_poll_seconds=1800,stage_gate_seconds=120,recovery_seconds=60,cleanup_seconds=45,
                launch_seconds=20,validation_slack_seconds=35)


def budget():
    entries=[profile_budget(p) for p in PROFILES];poll=1800
    # Sleep is >=2s after the prior iteration; no success-generating retries.
    listing=math.ceil(poll/2)+1;thermal=3*(math.ceil(poll/2)+1);screen=math.ceil(poll/10)+1;heartbeat=math.ceil(poll/10)+1
    gate_stage_archive_reserve=300;per=listing+thermal+screen+heartbeat+gate_stage_archive_reserve
    return dict(sessions=8,development=4,confirmation=4,diagnostic=8,
        work_requests=sum(x['work_requests'] for x in entries),eligibility_requests=24,diagnostic_requests=sum(x['work_requests'] for x in entries)+24,
        warmup=64,explicit_inference=sum(x['explicit_inference'] for x in entries),runtime_creations=32,
        staging=8,staged_files=56,installed_host_pulls=1,apk_transfers=1,installs=1,retry=0,replacement=0,additional=0,
        fixed_observation_seconds=sum(x['fixed_observation_seconds'] for x in entries),preparation_fixed_seconds=720,
        intersession_cooling_seconds=90,fixed_intersession_seconds=630,installation_seconds=600,installed_preflight_seconds=600,
        stage_gate_seconds=120,host_poll_seconds=1800,recovery_seconds=60,cleanup_seconds=45,launch_seconds=20,validation_slack_seconds=35,
        session_seconds=2080,freeze_seconds=600,analysis_seconds=600,total_seconds=600+8*2080+630+600+600,
        preparation_max_wait_seconds=360,apk_push_timeout_seconds=180,adb_command_slots=200+8*(per+50),pre_cleanup_command_slots=200+8*per,
        adb_calculation=dict(listing=listing,thermal=thermal,screen=screen,heartbeat=heartbeat,gate_stage_archive_reserve=gate_stage_archive_reserve,per_session_normal=per,per_session_cleanup=50,installation_reserve=200),
        baseline_seconds=120,cooling_seconds=180,normal_duration_seconds=None,profiles=entries)


def identity():
    files=[Path(__file__),Path(analysis.__file__),cal.ROOT/'tools/d1_energy_collection_device.py',cal.ROOT/'tools/d1_arrival_energy_collection_device.py',cal.ROOT/'tools/d1_arrival_start_ap.py',CONTRACT,j.m.MODEL]
    return cal.code_identity()|{p.relative_to(cal.ROOT).as_posix():old.p.digest(p) for p in files}


def script_text():
    from tools import d1_energy_state_collection as previous
    text=previous.render_run_script('PLAN_EXPECTED_SHA256')
    text=text.replace('[string]$Serial)', '[string]$Serial,[string]$ExpectedPlanSha256)')
    text=text.replace("if (!$Approved)","if (!$Approved -or !$Serial -or !$ExpectedPlanSha256)")
    text=text.replace("'PLAN_EXPECTED_SHA256'",'$ExpectedPlanSha256').replace('--expected-sha PLAN_EXPECTED_SHA256','--expected-sha $ExpectedPlanSha256')
    text=text.replace('tools.d1_energy_state_collection','tools.d1_resident_identification_plan')
    text=text.replace('python -B',"& 'C:/Users/LG/AppData/Local/Programs/Python/Python311/python.exe' -B")
    text=text.replace("--approved --adb",'--approved --serial $Serial --adb')
    return text


def expected(source,build,output):
    sourcefile=Path(source);source=old.p.read(sourcefile);receipt=old.p.read(build);output=Path(output)
    candidate=apk.inspect(receipt['apk_path'],source['apk_preflight']['toolchain'])
    old.require(candidate['signer_sha256']==source['apk_preflight']['candidate']['signer_sha256'],'existing project signer required')
    plan=copy.deepcopy(source)
    for k in list(plan):
        if k.startswith(('previous_','prior_','stopped_')):plan.pop(k)
    plan.update(protocol=PROTOCOL,experiment_id=NAME,plan_file=str((output/'collection_plan.json').resolve()),approval='not_approved',
        resident_identification=True,state_model_calibration=True,diagnostic_only=True,autonomous_diagnostic_only=True,
        state_model_followup=False,short_transition_diagnostic_only=False,operational_only=True,experiment_ready=False,
        status='PC_READY_DEVICE_UNVERIFIED_NOT_APPROVED',budget=budget(),source_code=identity(),
        source_plan=dict(path=str(sourcefile.resolve()),sha256=old.p.digest(sourcefile)),
        build_receipt=str(Path(build).resolve()),build_receipt_sha256=old.p.digest(build),apk_path=receipt['apk_path'],apk_sha256=receipt['apk_sha256'],
        apk_preflight=dict(source['apk_preflight'],candidate=candidate),
        analysis_contract=dict(path=str(CONTRACT),sha256=old.p.digest(CONTRACT)),
        original_model=dict(path=str(j.m.MODEL),sha256=j.m.MODEL_SHA),
        analysis=dict(version='resident-identification-analysis-v1',purpose='energy/AP model identification and frozen conditional validation',
                      original_model_sha256=j.m.MODEL_SHA,common120_separate_from_long_registered_window=True,strict_adoption=False),
        output_root=str(output.parent/'energy_ap_resident_identification_run_v3'),registry=str(output.parent/'resident_identification_registry'/NAME),
        minimum_host_free_bytes=4*2**30,temperature_preparation=copy.deepcopy(old.operational_rules.PREPARATION),
        collection_semantics='six registered state-regimen sessions plus two fresh96/192 arrival sessions; model costs conditional on actual schedules, not policy ranking',
        measurement_protocol_change='same four resident runtimes; new signed APK/protocol; 900ms sampler; 2s progress listing; one fresh numeric AP approval after baseline; no in-load host arm',entries=[])
    template=old.p.read(sourcefile.parent/source['entries'][0]['manifest']);manifests=[]
    for i,profile in enumerate(PROFILES):
        m=copy.deepcopy(template);sid=str(uuid.uuid5(uuid.NAMESPACE_URL,NAME+'/'+str(i)))
        role='development' if i<4 else 'confirmation';b=profile_budget(profile)
        if b['family']=='arrival':
            for k in ('state_model_calibration','calibration_version','blocks','pair','mode','baseline_seconds','common_work_seconds','cadence_ms','work_call_cap','probe_counts','temperature_preparation','session_control','autonomous_diagnostic_only','device_screen_contract','short_transition_diagnostic_only'):
                m.pop(k,None)
            count=b['work_requests'];sustained=count==192;policy='B2_PARALLEL_ONLINE_V1' if sustained else 'CPU_URGENT_ONLINE_V1'
            requests=[dict(request_id=str(uuid.uuid5(uuid.NAMESPACE_URL,sid+'/'+str(n))),ordinal=n,task_id='classification' if n%2==0 else 'detection',priority='urgent' if n%2==0 else 'normal',offset_ms=35000+n*(400 if sustained else 350),deadline_ms=1500 if n%2==0 else 6000) for n in range(count)]
            m.update(protocol='arrival-energy-synthetic-v1',experiment_id=NAME,session_id=sid,phase=f'{role}_{i}_{profile}',
                     identification_profile=profile,identification_role=role,policy=policy,policy_study_version='online-policy-model-study-v1',policy_study_role='confirmation',
                     scenario='separated_power',power_identification_version='sustained-confirmation-v1' if sustained else 'separated-power-input-v1',
                     maximum_duration_ms=480000,common_window_seconds=120,resident_baseline_seconds=30,cooling_seconds=60,
                     maximum_concurrency=2,memory_contract='android-low-memory-resident-v1',thermal_gate=0,requests=requests,
                     power_sampling_version='online-power-phase-audit-v1',power_sample_period_ms=900,start_ap_gate='numeric-ap-observe-v2',
                     apk_sha256=receipt['apk_sha256'],experiment_ready=False)
        else:
            m.update(protocol=PROTOCOL,experiment_id=NAME,session_id=sid,phase=f'{role}_{i}_{profile}',pair='CG_DC',mode='calibration',
            state_model_calibration=True,calibration_version=VERSION,resident_identification_version=VERSION,identification_profile=profile,identification_role=role,
            session_control='device-after-probe-diagnostic-v1',autonomous_diagnostic_only=True,operational_only=True,short_transition_diagnostic_only=False,
            maximum_duration_ms=1800000,common_work_seconds=b['common_work_seconds'],baseline_seconds=120,cooling_seconds=180,
            work_call_cap=b['work_requests'],cadence_ms=250,warmup_count=8,probe_counts=dict(classification=2,detection=2),
            start_ap_gate='numeric-ap-observe-v2',power_sampling_version='resident-identification-power-v1',power_sample_period_ms=900,
            blocks=blocks(profile),temperature_preparation=copy.deepcopy(old.operational_rules.PREPARATION),apk_sha256=receipt['apk_sha256'],experiment_ready=False)
        for spec in m['models'].values():spec['identity']['session_id']=sid;spec['target']['apk_sha256']=receipt['apk_sha256']
        name=f'manifests/{sid}.json';manifests.append(m)
        plan['entries'].append(dict(index=i,phase=m['phase'],role=role,profile=profile,pair='CG_DC',mode='calibration',session_id=sid,manifest=name,
                                    family=b['family'],protocol=m['protocol'],manifest_sha256=hashlib.sha256(old.p.canonical(m)).hexdigest(),work_requests=b['work_requests'],runtime_creations=4,warmup=8,eligibility_requests=b['eligibility_requests']))
    plan['run_script_sha256']=hashlib.sha256(script_text().encode('utf8')).hexdigest()
    return plan,manifests


def prepare(source,build,output):
    output=Path(output);old.require(output.name==FOLDER and not output.exists(),'new namespace only')
    plan,manifests=expected(source,build,output)
    old.require(not Path(plan['registry']).exists() and not Path(plan['output_root']).exists(),'unconsumed path')
    output.mkdir();(output/'manifests').mkdir()
    for e,m in zip(plan['entries'],manifests):cal.write_new(output/e['manifest'],m)
    (output/'RUN_AFTER_APPROVAL.ps1').write_text(script_text(),encoding='utf8')
    cal.write_new(output/'collection_plan.json',plan)
    return check(output/'collection_plan.json')


def check(file):
    file=Path(file);plan=old.p.read(file)
    old.require(plan['experiment_id']==NAME and plan['resident_identification'] and plan['approval']=='not_approved','registered experiment')
    old.require(not Path(plan['registry']).exists() and not Path(plan['output_root']).exists(),'consumed/occupied; never resume')
    expected_plan,manifests=expected(plan['source_plan']['path'],plan['build_receipt'],file.parent)
    old.require(plan==expected_plan and (file.parent/'RUN_AFTER_APPROVAL.ps1').read_text(encoding='utf8')==script_text(),'plan/script/code identity')
    for e,m in zip(plan['entries'],manifests):old.require(old.p.digest(file.parent/e['manifest'])==e['manifest_sha256'] and old.p.read(file.parent/e['manifest'])==m,'manifest identity')
    for x in [*plan['source_files'].values(),*plan['references'].values()]:old.require(old.p.digest(x['path'])==x['sha256'],'input/reference identity')
    old.require(old.p.digest(plan['apk_path'])==plan['apk_sha256'] and old.p.digest(j.m.MODEL)==j.m.MODEL_SHA,'APK/model identity')
    build=old.p.read(plan['build_receipt']);old.require(cal.apk_sources(build['source_code'])==cal.apk_sources(cal.code_identity()),'APK source drift')
    old.require(shutil.disk_usage(file.parent).free>=plan['minimum_host_free_bytes'],'4GiB reserve')
    return dict(status=plan['status'],plan_sha256=old.p.digest(file),budget=budget(),device_commands=0,consumed=False,analysis_frozen_before_confirmation=True)


def summarize_session(folder,manifest,plan):
    m=old.p.read(manifest)
    if m['protocol']=='arrival-energy-synthetic-v1':
        from tools import d1_arrival_energy_collection_device as arrival
        scoped=dict(plan,online_policy_study=True,sustained_confirmation=len(m['requests'])==192)
        stats=arrival.validate(Path(folder).parent,m,scoped)
        if stats['common_unfinished']:raise ValueError('arrival full work exceeds common window')
        portable=analysis.arrival_case(folder,m)
        return dict(stats,condition=m['phase'],work_calls=len(m['requests']),eligibility_calls=0,warmup_calls=8,analysis_case=portable)
    _,stats=analysis.read_case(folder,manifest,plan);return stats


def freeze(results,plan,root):
    cases=[r['analysis_case'] for r in results]
    inventory={f"{e['index']:02d}_{e['session_id']}/validated.json":old.p.digest(Path(root)/f"{e['index']:02d}_{e['session_id']}/validated.json") for e in plan['entries'][:4]}
    cal.write_new(Path(root)/'development_input_inventory.json',dict(files=inventory,contract_sha256=plan['analysis_contract']['sha256'],source='development only'))
    result=analysis.freeze(cases,old.p.read(plan['original_model']['path']))
    return dict(result,development_validated_sha256=inventory,analysis_contract_sha256=plan['analysis_contract']['sha256'],original_model_sha256=j.m.MODEL_SHA)


def evaluate(stats,frozen,plan):
    return analysis.assess(stats['analysis_case'],frozen['model'],old.p.read(plan['original_model']['path']))


def progress_consumption(raw,launched,load_cap=1200,eligibility_cap=4):
    rows,partial=old.progress_prefix(raw);out={}
    for name,cap,phases in [('runtime',4,None),('warmup',8,None),('eligibility',eligibility_cap,{'eligibility_serial_probe','eligibility_parallel_probe'}),('load',load_cap,{'load','common_window'})]:
        starts=[r for r in rows if r['kind']==(name+'_start' if phases is None else 'request_start') and (phases is None or r['phase'] in phases)]
        ends=[r for r in rows if r['kind']==(name+'_return' if phases is None else 'lane_available') and (phases is None or r['phase'] in phases)]
        key=lambda r:r.get('id',r.get('key'));count=len({key(r) for r in starts+ends})
        if count>cap:raise ValueError('recorded consumption exceeds maximum')
        out[name]=dict(confirmed_started_at_least=count,confirmed_returned=len({key(r) for r in ends}),actual_started_upper=cap if launched else 0,missing_completion_is_not_success=True)
    return dict(records=len(rows),partial_lines=partial,counts=out)


if __name__=='__main__':
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest='action',required=True)
    q=sub.add_parser('prepare');q.add_argument('--source',required=True);q.add_argument('--build',required=True);q.add_argument('--output',required=True)
    q=sub.add_parser('check');q.add_argument('--plan',required=True)
    q=sub.add_parser('run');q.add_argument('--plan',required=True);q.add_argument('--approved',action='store_true');q.add_argument('--serial',required=True);q.add_argument('--expected-sha',required=True);q.add_argument('--adb',required=True)
    a=p.parse_args()
    if a.action=='prepare':r=prepare(a.source,a.build,a.output)
    elif a.action=='check':r=check(a.plan)
    else:
        from tools.d1_energy_collection_device import run
        r=run(a.plan,a.adb,a.serial,a.expected_sha,a.approved)
    print(json.dumps(r,ensure_ascii=False,indent=2))
