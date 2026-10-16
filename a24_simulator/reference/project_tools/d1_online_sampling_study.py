"""One bounded ABBA sampling-period contrast; no coefficient fitting or retries."""
import argparse
import copy
import hashlib
import json
import uuid
from pathlib import Path
from tools import d1_arrival_plan as p
from tools import d1_online_policy_study as study

ROOT=study.ROOT
NAME='ONLINE-POWER-SAMPLING-CONTRAST-01'
FOLDER='online_power_sampling_plan_v1'
RUN='online_power_sampling_run_v1'
FOLLOWUP='online_power_sampling_plan_v2'
CONTRACT=ROOT/'docs/results/online_policy_study_01/power_diagnosis_v1/sampling_contract.json'


def identity():
    return study.identity() | {str(Path(__file__).relative_to(ROOT)).replace('\\','/'):p.digest(__file__),
                               str(CONTRACT.relative_to(ROOT)).replace('\\','/'):p.digest(CONTRACT)}


def script():
    return study.block_script().replace('d1_online_policy_study','d1_online_sampling_study')


def specification(source,build,output):
    source,build,output=map(Path,(source,build,output));old=p.read(source);b=p.read(build)
    study.require(study.old.apk_sources(b['source_code'])==study.old.apk_sources(study.cal.code_identity()),'APK sources')
    candidate=study.apk.inspect(b['apk_path'],old['apk_preflight']['toolchain'])
    study.require(candidate['signer_sha256']==old['apk_preflight']['candidate']['signer_sha256'],'project signer')
    followup=output.name==FOLLOWUP
    contract=p.read(CONTRACT);periods=contract['periods_ms'][2:] if followup else contract['periods_ms']
    n=len(periods);name=NAME+'-REMAINING-02' if followup else NAME
    plan=copy.deepcopy(old);template=p.read(source.parent/old['entries'][0]['manifest'])
    budget=dict(old['budget'],sessions=n,requests=n*96,warmup=n*8,explicit_inference=n*104,runtime_creations=n*4,
        staging=n,staging_files=n*7,total_seconds=600+n*700+(n-1)*90,adb_commands=n*3200+200,apk_transfers=int(not followup),installs=int(not followup),
        fixed_observation_seconds=n*210,intersession_cooling_seconds=90,installed_preflight_seconds=600)
    plan.update(experiment_id=name,online_sampling_audit=True,online_policy_study=True,study_phase='development',
        installed_only=followup,source_code=identity(),budget=budget,output_root=str(output.parent/('online_power_sampling_run_v2' if followup else RUN)),
        registry=str(output.parent/'online_power_sampling_registry'/name),source_plan=dict(path=str(source),sha256=p.digest(source)),
        build_receipt=str(build),build_receipt_sha256=p.digest(build),apk_path=b['apk_path'],apk_sha256=b['apk_sha256'],
        apk_preflight=dict(old['apk_preflight'],candidate=candidate),analysis_contract=dict(path=str(CONTRACT),sha256=p.digest(CONTRACT)),
        entries=[],status='PC_READY_DEVICE_UNVERIFIED',approval='user_autonomous_measurement',
        run_script_sha256=hashlib.sha256(script().encode()).hexdigest(),
        measurement_protocol_change='ABBA 1000/900/900/1000ms power sampling, same APK and 500ms arrivals; no causal attribution to aliasing alone',
        analysis_scope='sampling sensitivity and workload phase coverage; coefficient fit and accuracy PASS prohibited')
    if followup:
        prior=Path(old['output_root']);receipt=p.read(prior/'FINAL_RECEIPT.json')
        study.require(source.parent.name==FOLDER and receipt['status']=='stopped_no_resume' and receipt['completed_sessions']==2,'exact stopped predecessor')
        files={str(source):p.digest(source),str(prior/'FINAL_RECEIPT.json'):p.digest(prior/'FINAL_RECEIPT.json')}
        for e in old['entries'][:2]:
            folder=prior/f"{e['index']:02d}_{e['session_id']}"
            study.require(p.read(folder/'validated.json')['status']=='eligible_descriptive_only','import eligible first two only')
            for f in [folder/'validated.json',folder/'thermal.jsonl',source.parent/e['manifest'],*sorted((folder/'artifacts').glob('*'))]:
                if f.is_file():files[str(f)]=p.digest(f)
        plan['imported_completed']=dict(plan=str(source),indices=[0,1],files=files,
            limitation='separate block after timeout/cleanup; interrupted third stays failed and consumed, not replaced in original denominator; inter-block gap/history differs')
    for key in ('study_plan_file','study_freeze'):plan.pop(key,None)
    manifests=[]
    for i,period in enumerate(periods):
        m=copy.deepcopy(template);sid=str(uuid.uuid5(uuid.NAMESPACE_URL,name+'/'+str(i)))
        requests=study.model.requests('development',sid)
        for r in requests:r['request_id']=str(uuid.uuid5(uuid.NAMESPACE_URL,sid+'/'+str(r['ordinal'])))
        m.update(experiment_id=name,session_id=sid,phase=f'{"remaining" if followup else "sampling"}_{i}_{period}ms',policy=study.model.POLICIES[1],
            policy_study_role='development',power_sampling_version='online-power-phase-audit-v1',power_sample_period_ms=period,
            requests=requests,apk_sha256=b['apk_sha256'])
        for spec in m['models'].values():spec['identity']['session_id']=sid;spec['target']['apk_sha256']=b['apk_sha256']
        rel=f'manifests/{sid}.json'
        plan['entries'].append(dict(index=i,phase=m['phase'],condition=m['policy'],scenario=m['scenario'],policy=m['policy'],
            session_id=sid,manifest=rel,manifest_sha256=hashlib.sha256(p.canonical(m)).hexdigest(),requests=96,warmup=8,runtime_creations=4))
        manifests.append(m)
    return plan,manifests


def check(file):
    file=Path(file);plan=p.read(file)
    study.require(file.parent.name in (FOLDER,FOLLOWUP),'dedicated path')
    study.require(not Path(plan['registry']).exists() and not Path(plan['output_root']).exists(),'consumed; no resume')
    expected,manifests=specification(plan['source_plan']['path'],plan['build_receipt'],file.parent)
    study.require(expected==plan and (file.parent/'RUN_AFTER_APPROVAL.ps1').read_text(encoding='utf8')==script(),'frozen plan/script changed')
    for item in [plan['frozen_model'],*plan['source_files'].values(),*plan['references'].values()]:
        study.require(p.digest(item['path'])==item['sha256'],'bound source changed')
    for e,m in zip(plan['entries'],manifests):
        study.require(p.read(file.parent/e['manifest'])==m and p.digest(file.parent/e['manifest'])==e['manifest_sha256'],'manifest')
    study.require(p.digest(plan['apk_path'])==plan['apk_sha256'],'APK changed')
    return dict(status=plan['status'],plan_sha256=p.digest(file),budget=plan['budget'],device_commands=0)


def prepare(source,build,output):
    output=Path(output);study.require(not output.exists(),'fresh plan')
    plan,manifests=specification(source,build,output)
    output.mkdir();(output/'manifests').mkdir()
    for e,m in zip(plan['entries'],manifests):study.cal.write_new(output/e['manifest'],m)
    (output/'RUN_AFTER_APPROVAL.ps1').write_text(script(),encoding='utf8')
    study.cal.write_new(output/'collection_plan.json',plan)
    return check(output/'collection_plan.json')


def main():
    q=argparse.ArgumentParser();s=q.add_subparsers(dest='action',required=True)
    a=s.add_parser('prepare')
    for k in ('source','build','output'):a.add_argument('--'+k,required=True)
    a=s.add_parser('check-block');a.add_argument('--plan',required=True)
    a=s.add_parser('run-block')
    for k in ('plan','adb','expected-sha'):a.add_argument('--'+k,required=True)
    a.add_argument('--serial',default='');a.add_argument('--approved',action='store_true')
    a=q.parse_args()
    if a.action=='prepare':r=prepare(a.source,a.build,a.output)
    elif a.action=='check-block':r=check(a.plan)
    else:
        from tools.d1_arrival_energy_collection_device import run
        r=run(a.plan,a.adb,a.serial,a.expected_sha,a.approved)
    print(json.dumps(r,indent=2,ensure_ascii=False))


if __name__=='__main__':main()
