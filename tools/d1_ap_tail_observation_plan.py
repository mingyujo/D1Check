"""Separate C0/load tail block. Preparation/Check do not construct a device or claim."""
import argparse
import copy
import hashlib
import json
import math
import shutil
import uuid
from pathlib import Path
from tools import d1_resident_identification_plan as prior
from tools import d1_ap_tail_identification as tail

old,cal,analysis,j=prior.old,prior.cal,prior.analysis,prior.j
VERSION='tail-observation-regimen-v1'
PROTOCOL='energy-ap-tail-observation-v1'
NAME='ENERGY-AP-TAIL-OBSERVATION-01'
FOLDER='energy_ap_tail_observation_plan_v2'
PUBLIC=cal.ROOT/'docs/results/ap_tail_observation_prep_01'
CONTRACT=PUBLIC/'analysis_contract.json'
CANDIDATES=tail.BUNDLE/'run_v2/candidates.json'
PROFILES=('C0_LONG','LOAD_A_LONG')
WATCHDOG_MS=3540000


def blocks(profile):
    if profile=='C0_LONG':return [dict(id='registered_no_work',lane_indices=[],seconds=600)]
    if profile=='LOAD_A_LONG':return prior.blocks('DEV_A')
    raise ValueError('unregistered tail profile')


def budget():
    poll=3600;listing=math.ceil(poll/2)+1;thermal=3*listing
    screen=heartbeat=math.ceil(poll/10)+1;per=listing+thermal+screen+heartbeat+300
    session=120+20+poll+60+45+35
    return dict(sessions=2,development=0,confirmation=2,diagnostic=2,work_requests=1200,
        eligibility_requests=8,diagnostic_requests=1208,warmup=16,explicit_inference=1224,
        runtime_creations=8,staging=2,staged_files=14,installed_host_pulls=1,apk_transfers=1,installs=1,
        retry=0,replacement=0,additional=0,baseline_seconds=120,common_work_seconds=600,cooling_seconds=1920,
        fixed_observation_seconds=5280,preparation_fixed_seconds=240,preparation_max_wait_seconds=360,
        intersession_cooling_seconds=90,fixed_intersession_seconds=90,installation_seconds=600,installed_preflight_seconds=600,
        stage_gate_seconds=120,host_poll_seconds=poll,recovery_seconds=60,cleanup_seconds=45,launch_seconds=20,
        validation_slack_seconds=35,session_seconds=session,freeze_seconds=0,analysis_seconds=600,
        total_seconds=600+2*session+90+600,apk_push_timeout_seconds=180,
        adb_command_slots=200+2*(per+50),pre_cleanup_command_slots=200+2*per,
        adb_calculation=dict(listing=listing,thermal=thermal,screen=screen,heartbeat=heartbeat,
                             gate_stage_archive_reserve=300,per_session_normal=per,per_session_cleanup=50,installation_reserve=200),
        app_stage_timeout_seconds=dict(setup_and_warmup=150,warmup_gate=60,serial_probe=30,serial_gate=60,
            parallel_probe=30,preparation_gate=360,baseline=120,start_ap_gate=30,common=600,cooling=1920,cleanup_reserve=45),
        app_watchdog_seconds=3540,normal_duration_seconds=None,
        profiles=[dict(profile=p,work_requests=sum(len(b['lane_indices'])*b['seconds']*4 for b in blocks(p)),
                       runtime_creations=4,warmup=8,eligibility_requests=4,fixed_observation_seconds=2640) for p in PROFILES])


def validate_manifest(m):
    profile=m['identification_profile'];b=blocks(profile)
    expected=dict(protocol=PROTOCOL,tail_observation_version=VERSION,calibration_version=VERSION,
        maximum_duration_ms=WATCHDOG_MS,baseline_seconds=120,common_work_seconds=600,cooling_seconds=1920,
        work_call_cap=sum(len(x['lane_indices'])*x['seconds']*4 for x in b),cadence_ms=250,
        power_sample_period_ms=900,start_ap_gate='numeric-ap-observe-v2',blocks=b,
        state_model_calibration=True,operational_only=True,autonomous_diagnostic_only=True,experiment_ready=False,
        session_control='device-after-probe-diagnostic-v1',mode='calibration')
    if 'resident_identification_version' in m or any(m.get(k)!=v for k,v in expected.items()):
        raise ValueError('tail protocol/profile/time/call boundary mismatch')
    return profile


def identity():
    files=[Path(__file__),Path(analysis.__file__),Path(tail.__file__),Path(tail.s.__file__),
        cal.ROOT/'tools/d1_energy_collection_device.py',cal.ROOT/'tools/d1_arrival_start_ap.py',
        CONTRACT,CANDIDATES,j.m.MODEL]
    files += [cal.ROOT/name for name in old.HOST_FILES]
    files += [Path(module.__file__) for module in (prior,j,j.m,j.m.thermal,j.m.memory,j.m.base.common)]
    return cal.code_identity()|{p.relative_to(cal.ROOT).as_posix():old.p.digest(p) for p in files}


def script_text():
    return prior.script_text().replace('tools.d1_resident_identification_plan','tools.d1_ap_tail_observation_plan')


def verify_frozen(plan):
    for ref in (plan['analysis_contract'],plan['frozen_candidates'],plan['original_model']):
        old.require(old.p.digest(ref['path'])==ref['sha256'],'pre-execution frozen evidence changed')
    models=old.p.read(plan['frozen_candidates']['path'])
    old.require(set(models)==set(tail.MODES),'registered comparators only')
    for mode,model in models.items():
        old.require(model['mode']==mode and model['original_model_sha256']==j.m.MODEL_SHA,'candidate family drift')
    return models


def expected(source,build,output):
    sourcefile=Path(source);src=old.p.read(sourcefile);receipt=old.p.read(build);output=Path(output)
    candidate=prior.apk.inspect(receipt['apk_path'],src['apk_preflight']['toolchain'])
    old.require(candidate['signer_sha256']==src['apk_preflight']['candidate']['signer_sha256'],'existing project signer required')
    plan=copy.deepcopy(src)
    for k in list(plan):
        if k.startswith(('previous_','prior_','stopped_')) or k in ('cached_installed_apk','recovery'):plan.pop(k)
    plan.update(protocol=PROTOCOL,experiment_id=NAME,plan_file=str((output/'collection_plan.json').resolve()),
        approval='not_approved',status='PC_READY_DEVICE_UNVERIFIED_NOT_APPROVED',tail_observation=True,
        resident_identification=True,state_model_calibration=True,diagnostic_only=True,autonomous_diagnostic_only=True,
        state_model_followup=False,short_transition_diagnostic_only=False,operational_only=True,experiment_ready=False,
        budget=budget(),source_code=identity(),source_plan=dict(path=str(sourcefile.resolve()),sha256=old.p.digest(sourcefile)),
        build_receipt=str(Path(build).resolve()),build_receipt_sha256=old.p.digest(build),
        apk_path=receipt['apk_path'],apk_sha256=receipt['apk_sha256'],apk_preflight=dict(src['apk_preflight'],candidate=candidate),
        analysis_contract=dict(path=str(CONTRACT),sha256=old.p.digest(CONTRACT)),
        frozen_candidates=dict(path=str(CANDIDATES),sha256=old.p.digest(CANDIDATES)),
        original_model=dict(path=str(j.m.MODEL),sha256=j.m.MODEL_SHA),
        analysis=dict(version='tail-observation-confirmation-v1',fit_calls=0,actual_schedule_conditional=True,
                      current_ua_per_raw=1000,current_unit='A24 raw mA conditional; absolute J not certified',
                      strict_adoption=False,accuracy_pass=None),
        output_root=str(output.parent/'energy_ap_tail_observation_run_v2'),
        registry=str(output.parent/'tail_observation_registry'/NAME),minimum_host_free_bytes=4*2**30,
        temperature_preparation=copy.deepcopy(old.operational_rules.PREPARATION),
        collection_semantics='C0 then registered DEV_A load; same resident/preparation,2640s fixed observation each; no automatic refit',
        measurement_protocol_change='new explicit3540s watchdog/1920s cooling/C0 support; same900ms sampler/2s AP+listing/10s screen; long host observation affects whole-device cost',entries=[])
    template=old.p.read(sourcefile.parent/src['entries'][0]['manifest']);manifests=[]
    for i,profile in enumerate(PROFILES):
        m=copy.deepcopy(template);m.pop('resident_identification_version',None)
        sid=str(uuid.uuid5(uuid.NAMESPACE_URL,NAME+'/'+str(i)))
        work=budget()['profiles'][i]['work_requests']
        m.update(protocol=PROTOCOL,experiment_id=NAME,session_id=sid,phase=f'confirmation_{i}_{profile}',
            identification_profile=profile,identification_role='confirmation',tail_observation_version=VERSION,
            calibration_version=VERSION,maximum_duration_ms=WATCHDOG_MS,common_work_seconds=600,cooling_seconds=1920,
            work_call_cap=work,blocks=blocks(profile),apk_sha256=receipt['apk_sha256'],experiment_ready=False)
        for spec in m['models'].values():spec['identity']['session_id']=sid;spec['target']['apk_sha256']=receipt['apk_sha256']
        validate_manifest(m);name=f'manifests/{sid}.json';manifests.append(m)
        plan['entries'].append(dict(index=i,phase=m['phase'],role='confirmation',profile=profile,pair='CG_DC',mode='calibration',
            session_id=sid,manifest=name,family='regimen',protocol=PROTOCOL,manifest_sha256=hashlib.sha256(old.p.canonical(m)).hexdigest(),
            work_requests=work,runtime_creations=4,warmup=8,eligibility_requests=4))
    plan['run_script_sha256']=hashlib.sha256(script_text().encode('utf8')).hexdigest()
    verify_frozen(plan)
    return plan,manifests


def prepare(source,build,output):
    output=Path(output);old.require(output.name==FOLDER and not output.exists(),'new namespace only')
    plan,manifests=expected(source,build,output)
    old.require(not Path(plan['registry']).exists() and not Path(plan['output_root']).exists(),'occupied namespace')
    (output/'manifests').mkdir(parents=True)
    for e,m in zip(plan['entries'],manifests):cal.write_new(output/e['manifest'],m)
    (output/'RUN_AFTER_APPROVAL.ps1').write_text(script_text(),encoding='utf8',newline='\n')
    cal.write_new(output/'collection_plan.json',plan)
    return check(output/'collection_plan.json')


def check(file):
    file=Path(file);plan=old.p.read(file)
    old.require(file.parent.name==FOLDER and plan['experiment_id']==NAME and plan['tail_observation'] and plan['approval']=='not_approved','separate registered final plan')
    old.require(not Path(plan['registry']).exists() and not Path(plan['output_root']).exists(),'consumed/occupied; never resume')
    expected_plan,manifests=expected(plan['source_plan']['path'],plan['build_receipt'],file.parent)
    old.require(plan==expected_plan and (file.parent/'RUN_AFTER_APPROVAL.ps1').read_text(encoding='utf8')==script_text(),'plan/script/code identity')
    old.require(old.p.digest(file.parent/'RUN_AFTER_APPROVAL.ps1')==plan['run_script_sha256'],'raw script byte identity')
    for e,m in zip(plan['entries'],manifests):
        old.require(old.p.digest(file.parent/e['manifest'])==e['manifest_sha256'] and old.p.read(file.parent/e['manifest'])==m,'manifest identity')
    for ref in [*plan['source_files'].values(),*plan['references'].values()]:old.require(old.p.digest(ref['path'])==ref['sha256'],'input/reference identity')
    old.require(len(plan['source_files'])==6 and set(plan['references'])==set(old.KEYS),'six staging sources and four quality references')
    for name,digest in plan['apk_preflight']['tool_sha256'].items():
        old.require(old.p.digest(plan['apk_preflight']['toolchain'][name])==digest,'APK inspection tool identity')
    old.require(old.p.digest(plan['apk_path'])==plan['apk_sha256'],'APK identity')
    receipt=old.p.read(plan['build_receipt'])
    old.require(cal.apk_sources(receipt['source_code'])==cal.apk_sources(cal.code_identity()),'APK source drift')
    old.require(shutil.disk_usage(file.parent).free>=plan['minimum_host_free_bytes'],'4GiB reserve')
    verify_frozen(plan)
    return dict(status=plan['status'],plan_sha256=old.p.digest(file),budget=budget(),device_commands=0,
                consumed=False,automatic_fit=False,original_model_sha256=j.m.MODEL_SHA)


def summarize_session(folder,manifest,plan):
    verify_frozen(plan);m=old.p.read(manifest);validate_manifest(m)
    c,stats=analysis.read_case(folder,manifest,plan)
    q=c['q'];end=c['actual'][-1]['end_s']
    old.require(q and q[0]-35<=10 and end-q[-1]<=10 and 2555<=end<=2560,'full tail AP coverage/end')
    from tools.d1_energy_thermal import integrate
    events,_=old.progress_prefix((Path(folder)/'progress.jsonl').read_bytes())
    samples=[dict(e,mono_ns=(e['snapshot_start_ns']+e['sensor_read_end_ns'])//2) for e in events if e['kind']=='power_sample']
    origin=stats['common_start_ns']
    # The sampler stops at app cleanup. A last sample before cooling_end cannot
    # establish the missing final power interval; preserve coverage, never fill it.
    stats['tail_power_coverage']=integrate(samples,origin+635*10**9,int(origin+end*1e9),1000)
    original=old.p.read(plan['original_model']['path']);models=verify_frozen(plan)
    predictions={'FROZEN':j.m.predict(c,c['actual'],original,dict(name='FROZEN'))[0]}
    for mode,model in models.items():predictions[mode]=tail.predict(c,original,model)[0]
    curves=[dict(t_s=t,observed_ap_c=a,**{name:pred[i] for name,pred in predictions.items()}) for i,(t,a) in enumerate(zip(q,c['ap']))]
    tail.s.csv_write(Path(folder).parent/'diagnostic_ap_curves.csv',curves)
    stats.update(status='eligible_tail_observation_diagnostic_only',formal_confirmation=False,
        comparator_errors={name:j.m.base.common.score(c['ap'],p) for name,p in predictions.items()},
        prediction_inputs='pre-load AP and actual schedule only; post AP is target, no refit',
        prediction_scope='finite-horizon extrapolation diagnostic; not strict support',
        frozen_candidates_sha256=plan['frozen_candidates']['sha256'],fit_calls=0)
    stats['energy_windows']={}
    for label,lo,hi in [('reference120',0.,120.),('registered600',35.,635.),('recovery1920',635.,end)]:
        coverage=integrate(samples,int(origin+lo*1e9),int(origin+hi*1e9),1000)
        observed=coverage['full_energy_j']
        predicted=j.m.energy_prediction(c,c['actual'],original,dict(name='FROZEN'),hi)-j.m.energy_prediction(c,c['actual'],original,dict(name='FROZEN'),lo)
        stats['energy_windows'][label]=dict(start_s=lo,end_s=hi,observed_j=observed,predicted_j=predicted,
            coverage=coverage,signed_error_j=predicted-observed if observed is not None else None,
            absolute_error_j=abs(predicted-observed) if observed is not None else None,
            relative_error=(predicted-observed)/observed if observed else None)
    return stats


progress_consumption=prior.progress_consumption


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
