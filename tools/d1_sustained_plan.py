"""One bounded CPU/PAR transfer block, using the existing single-use collector."""
import argparse
import copy
import hashlib
import json
import shutil
import uuid
from pathlib import Path
from tools import d1_arrival_plan as p
from tools import d1_arrival_timing_calibration as cal
from tools import d1_arrival_energy_collection as old
from tools import d1_arrival_ap_confirmation as prior
from tools import d1_online_policy_study as scripts
from tools import d1_sustained_protocol as inputs
from tools import d1_apk_identity as apk

ROOT=old.ROOT
NAME='SUSTAINED-CPU-PAR-CONFIRM-01'
FOLDER='sustained_confirmation_plan_v1'
ORDER=(inputs.POLICIES[0],inputs.POLICIES[1],inputs.POLICIES[1],inputs.POLICIES[0],
       inputs.POLICIES[1],inputs.POLICIES[0],inputs.POLICIES[0],inputs.POLICIES[1])
MODEL=ROOT/'docs/results/online_policy_study_01/separated_power_final/model.json'
MODEL_SHA='5682082a936b7c83efeee747ceeb64fd0c64f0bef8765bbf1b90b807db872db2'
CONTRACT=ROOT/'docs/results/online_policy_study_01/overnight_sustained_pc_v1/analysis_contract.json'
PREVIEW=ROOT/'docs/results/online_policy_study_01/overnight_sustained_pc_v1/preview_complete/summary.json'
require=old.require


def budget():
    n=len(ORDER)
    return dict(prior.BUDGET,sessions=n,requests=n*192,warmup=n*8,explicit_inference=n*200,
        runtime_creations=n*4,staging=n,staging_files=n*7,installed_host_pulls=1,
        apk_transfers=1,installs=1,fixed_observation_seconds=n*210,
        total_seconds=600+n*700+(n-1)*90,adb_commands=n*3200+200,
        per_session_adb_commands=3200,adb_recovery_cleanup_reserve=100,
        installed_preflight_seconds=600,intersession_cooling_seconds=90)


def identity():
    return old.identity() | {f.relative_to(ROOT).as_posix():p.digest(f) for f in
        (Path(__file__),Path(inputs.__file__),CONTRACT,PREVIEW,MODEL,
         ROOT/'tools/d1_online_policy_model.py',ROOT/'tools/d1_arrival_explore.py')}


def script_text():
    return scripts.block_script().replace('d1_online_policy_study','d1_sustained_plan').replace('check-block','check').replace('run-block','run')


def specification(source_file,build_file,output):
    source_file,build_file,output=map(Path,(source_file,build_file,output))
    source,build=p.read(source_file),p.read(build_file)
    require(p.digest(MODEL)==MODEL_SHA,'frozen model drift')
    require(p.read(PREVIEW)['deadline_and_window_gate'],'fixed input preview not eligible')
    require(old.apk_sources(build['source_code'])==old.apk_sources(cal.code_identity()),'APK source mismatch')
    require(p.digest(build['apk_path'])==build['apk_sha256'],'APK drift')
    candidate=apk.inspect(build['apk_path'],source['apk_preflight']['toolchain'])
    require(candidate['signer_sha256']==source['apk_preflight']['candidate']['signer_sha256'],'project signer mismatch')
    plan=copy.deepcopy(source)
    for k in list(plan):
        if k.startswith(('separated_','ap_','resident_','recorded_','online_','study_')):plan.pop(k)
    plan.update(sustained_confirmation=True,online_policy_study=True,online_configuration_owner_v1=True,
        installed_only=False,study_phase='confirmation',study_freeze=dict(path=str(MODEL),sha256=MODEL_SHA),
        experiment_id=NAME,status='PC_READY_DEVICE_UNVERIFIED',approval='user_overnight_execute_20261004',
        experiment_ready=False,budget=budget(),source_code=identity(),minimum_host_free_bytes=2**31,
        source_plan=dict(path=str(source_file.resolve()),sha256=p.digest(source_file)),
        build_receipt=str(build_file.resolve()),build_receipt_sha256=p.digest(build_file),
        apk_path=build['apk_path'],apk_sha256=build['apk_sha256'],
        apk_preflight=dict(source['apk_preflight'],candidate=candidate),
        input_bundle=dict(path=str(CONTRACT),sha256=p.digest(CONTRACT)),
        analysis_contract=dict(path=str(CONTRACT),sha256=p.digest(CONTRACT)),
        activity_model=dict(path=str(MODEL),sha256=MODEL_SHA),
        output_root=str(output.parent/'sustained_confirmation_run_v1'),
        registry=str(output.parent/'sustained_confirmation_registry'/NAME),entries=[],
        measurement_protocol_change='opt-in192/400ms input; same 900ms sampler, host polling and numeric-ap-observe-v2; APK input validator only',
        analysis_scope='input/protocol transfer, same frozen coefficients; no strict promotion or accuracy PASS',
        campaign_limit=dict(sessions=10,requests=1920,warmup=80,explicit_inference=2000,
            runtime_creations=40,staging=10,staging_files=70,execution_plans=3,
            adb_commands=32600,device_seconds=10800,reserved_commands=32600,reserved_seconds=9610),
        prewarmup_observation='precommon-observation-gap-v3')
    template=p.read(source_file.parent/source['entries'][0]['manifest']);ms=[]
    for i,policy in enumerate(ORDER):
        m=copy.deepcopy(template)
        for k in list(m):
            if k.startswith(('policy_study','power_identification','replay_','source_','resident_control')):m.pop(k)
        sid=str(uuid.uuid5(uuid.NAMESPACE_URL,NAME+'/'+str(i)))
        rows=inputs.requests(sid)
        for r in rows:r['request_id']=str(uuid.uuid5(uuid.NAMESPACE_URL,sid+'/'+str(r['ordinal'])))
        inputs.validate(rows,policy)
        m.update(experiment_id=NAME,session_id=sid,phase=f'confirmation_{i}_{policy}',
            scenario='separated_power',policy=policy,policy_study_version='online-policy-model-study-v1',
            policy_study_role='confirmation',power_identification_version=inputs.VERSION,
            power_sampling_version='online-power-phase-audit-v1',power_sample_period_ms=900,
            start_ap_gate='numeric-ap-observe-v2',apk_sha256=build['apk_sha256'],requests=rows)
        for spec in m['models'].values():spec['identity']['session_id']=sid;spec['target']['apk_sha256']=build['apk_sha256']
        rel='manifests/'+sid+'.json';ms.append(m)
        plan['entries'].append(dict(index=i,phase=m['phase'],condition=policy,scenario=m['scenario'],policy=policy,
            session_id=sid,manifest=rel,manifest_sha256=hashlib.sha256(p.canonical(m)).hexdigest(),
            requests=192,warmup=8,runtime_creations=4,pair=i//2))
    plan['run_script_sha256']=hashlib.sha256(script_text().encode('utf8')).hexdigest()
    return plan,ms


def prepare(source,build,output):
    output=Path(output)
    require(output.name==FOLDER and not output.exists(),'fresh plan only')
    plan,ms=specification(source,build,output)
    require(not Path(plan['registry']).exists() and not Path(plan['output_root']).exists(),'occupied')
    output.mkdir();(output/'manifests').mkdir()
    for e,m in zip(plan['entries'],ms):cal.write_new(output/e['manifest'],m)
    (output/'RUN_AFTER_APPROVAL.ps1').write_text(script_text(),encoding='utf8',newline='\n')
    cal.write_new(output/'collection_plan.json',plan)
    return check(output/'collection_plan.json')


def check(file):
    file=Path(file);plan=p.read(file)
    require(file.parent.name==FOLDER and not Path(plan['registry']).exists() and not Path(plan['output_root']).exists(),'consumed/occupied')
    require(shutil.disk_usage(file.parent).free>=plan['minimum_host_free_bytes'],'host disk reserve')
    expected,ms=specification(plan['source_plan']['path'],plan['build_receipt'],file.parent)
    require(plan==expected and (file.parent/'RUN_AFTER_APPROVAL.ps1').read_text(encoding='utf8')==script_text(),'frozen drift')
    for item in [plan['frozen_model'],plan['activity_model'],*plan['source_files'].values(),*plan['references'].values()]:
        require(p.digest(item['path'])==item['sha256'],'input/model binding drift')
    for e,m in zip(plan['entries'],ms):
        require(p.digest(file.parent/e['manifest'])==e['manifest_sha256'] and p.read(file.parent/e['manifest'])==m,'manifest drift')
    b=plan['budget']
    require(b['session_seconds']==b['stage_gate_seconds']+b['host_poll_seconds']+b['recovery_seconds']+b['cleanup_seconds'],'session reserve')
    require(b['total_seconds']==6830 and b['adb_commands']==25800 and b['explicit_inference']==1600,'approval cap')
    return dict(status=plan['status'],plan_sha256=p.digest(file),budget=b,device_commands=0)


def main():
    a=argparse.ArgumentParser();a.add_argument('action',choices=['prepare','check','run'])
    for key in ('source-plan','build-receipt','output','plan','adb','serial','expected-sha'):a.add_argument('--'+key)
    a.add_argument('--approved',action='store_true');q=a.parse_args()
    if q.action=='prepare':result=prepare(q.source_plan,q.build_receipt,q.output)
    elif q.action=='check':result=check(q.plan)
    else:
        from tools.d1_arrival_energy_collection_device import run
        result=run(q.plan,q.adb,q.serial or '',q.expected_sha,q.approved)
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
