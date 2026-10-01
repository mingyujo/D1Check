"""Opt-in 0/24 resident control pair. Prepare/Check never invokes ADB."""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
import uuid
from pathlib import Path
from tools import d1_arrival_plan as p
from tools import d1_arrival_timing_calibration as cal
from tools import d1_arrival_energy_collection as old
from tools import d1_arrival_recorded_replay as replay
from tools import d1_arrival_ap_confirmation as prior
from tools import d1_apk_identity as apk

ROOT = replay.ROOT
BUNDLE = ROOT/'docs/results/resident_control_design_01'
EXPERIMENT = 'ENERGY-AP-RESIDENT-CONTROL-01'
FOLDER = 'energy_ap_resident_control_plan_v1'
RUN = 'energy_ap_resident_control_run_v1'
VERSION = 'resident-control-pair-v1'
ROLES = ('no_load_control', 'registered_load')
BUDGET = dict(replay.BUDGET, sessions=2, requests=24, warmup=16,
    explicit_inference=40, runtime_creations=8, staging=2, staging_files=14,
    intersession_cooling_seconds=90, total_seconds=2090, adb_commands=6600,
    adb_recovery_cleanup_reserve=100)


def identity():
    return old.identity() | {f.relative_to(ROOT).as_posix():p.digest(f) for f in
        (Path(__file__), Path(replay.__file__), Path(prior.__file__),
         ROOT/'tools/d1_resident_control_readout.py',
         BUNDLE/'load_input.json', BUNDLE/'execution_contract.json')}


def request_count(manifest):
    old.require(manifest.get('resident_control_version')==VERSION and
        manifest.get('resident_control_role') in ROLES and
        manifest.get('scenario')=='burst' and manifest.get('policy')==replay.POLICY and
        manifest.get('start_ap_gate')=='numeric-ap-observe-v2','resident control identity')
    count = 0 if manifest['resident_control_role']==ROLES[0] else 24
    old.require(len(manifest['requests'])==count,'resident control request count')
    return count


def manifests(source_file, candidate_sha):
    source=p.read(source_file)
    template=p.read(Path(source_file).parent/source['entries'][0]['manifest'])
    result=[]
    for role in ROLES:
        m=copy.deepcopy(template)
        for key in ('ap_idle_response_version','ap_schedule_role'):
            m.pop(key,None)
        sid=str(uuid.uuid5(uuid.NAMESPACE_URL,EXPERIMENT+'/'+role))
        rows=copy.deepcopy(p.read(BUNDLE/'load_input.json')['requests']) if role==ROLES[1] else []
        rows=[{k:v for k,v in row.items() if not k.startswith('pc_')} for row in rows]
        for row in rows:
            row['request_id']=str(uuid.uuid5(uuid.NAMESPACE_URL,sid+'/'+str(row['ordinal'])))
        m.update(experiment_id=EXPERIMENT,session_id=sid,phase=role,scenario='burst',
            resident_control_version=VERSION,resident_control_role=role,
            apk_sha256=candidate_sha,requests=rows,start_ap_gate='numeric-ap-observe-v2',
            replay_source_sha256=p.digest(BUNDLE/'load_input.json'))
        for spec in m['models'].values():
            spec['identity']['session_id']=sid
            spec['target']['apk_sha256']=candidate_sha
        request_count(m)
        result.append(m)
    return result


def specification(source_file,build_file,output):
    source_file,build_file,output=map(Path,(source_file,build_file,output))
    source,build=p.read(source_file),p.read(build_file)
    old.require(old.apk_sources(build['source_code'])==old.apk_sources(cal.code_identity()),'APK source drift')
    old.require(p.digest(build['apk_path'])==build['apk_sha256'],'APK hash')
    candidate=apk.inspect(build['apk_path'],source['apk_preflight']['toolchain'])
    old.require(candidate['signer_sha256']==source['apk_preflight']['candidate']['signer_sha256'], 'project signer')
    plan=copy.deepcopy(source)
    for key in ('ap_transfer_confirmation','ap_idle_pulse_followup','candidate_freeze','single_arrival_confirmation'):
        plan.pop(key,None)
    plan.update(experiment_id=EXPERIMENT,status='PC_READY_DEVICE_UNVERIFIED_NOT_APPROVED',
        approval='not_approved',experiment_ready=False,resident_control_pair=True,
        recorded_replay_confirmation=True,budget=copy.deepcopy(BUDGET),source_code=identity(),
        source_plan=dict(path=str(source_file.resolve()),sha256=p.digest(source_file)),
        build_receipt=str(build_file.resolve()),build_receipt_sha256=p.digest(build_file),
        input_bundle=dict(path=str(BUNDLE/'load_input.json'),sha256=p.digest(BUNDLE/'load_input.json')),
        analysis_contract=dict(path=str(BUNDLE/'execution_contract.json'),sha256=p.digest(BUNDLE/'execution_contract.json')),
        apk_path=build['apk_path'],apk_sha256=build['apk_sha256'],
        apk_preflight=dict(source['apk_preflight'],candidate=candidate),
        output_root=str(output.parent/RUN),registry=str(output.parent/'resident_control_registry'/EXPERIMENT),
        measurement_protocol_change='new opt-in zero-request control, same APK for both arms; no pooling with old APK',
        analysis_scope='one control then one load, structure development only, no fit or independent validation',entries=[])
    plan['selection']='fixed no-load then original burst201/release+35 CG_DC; no outcome-based selection'
    # Old transfer-specific schedule/bindings do not describe this pair.
    for key in ('schedule','candidate_model','candidate_freeze_sha256'):
        plan.pop(key,None)
    ms=manifests(source_file,build['apk_sha256'])
    for i,m in enumerate(ms):
        rel=f"manifests/{m['session_id']}.json"
        plan['entries'].append(dict(index=i,phase=ROLES[i],scenario='burst',policy=replay.POLICY,
            session_id=m['session_id'],manifest=rel,manifest_sha256=hashlib.sha256(p.canonical(m)).hexdigest(),
            requests=request_count(m),warmup=8,runtime_creations=4))
    return plan,ms


def script_text():
    return prior.script_text({}).replace('d1_arrival_ap_confirmation','d1_resident_control_plan').replace(
        ' -or -not $Serial','').replace(' --serial $Serial','').replace(' [string]$Serial,\n','').replace(
        'Separate approval, selected transport and exact plan hash required',
        'Separate approval and exact plan hash required; runner selects one current online transport')


def prepare(source,build,output):
    output=Path(output)
    old.require(output.name==FOLDER and not output.exists(),'fresh dedicated plan')
    plan,ms=specification(source,build,output)
    old.require(not Path(plan['registry']).exists() and not Path(plan['output_root']).exists(),'occupied execution')
    output.mkdir();(output/'manifests').mkdir()
    for entry,m in zip(plan['entries'],ms):cal.write_new(output/entry['manifest'],m)
    script=output/'RUN_AFTER_APPROVAL.ps1';script.write_text(script_text(),encoding='utf-8')
    plan['run_script_sha256']=p.digest(script)
    cal.write_new(output/'collection_plan.json',plan)
    return check(output/'collection_plan.json')


def check(file):
    file=Path(file);plan=p.read(file)
    old.require(file.name=='collection_plan.json' and file.parent.name==FOLDER,'plan path')
    old.require(not Path(plan['output_root']).exists() and not Path(plan['registry']).exists(),'consumed/occupied plan; no resume')
    expected,ms=specification(plan['source_plan']['path'],plan['build_receipt'],file.parent)
    script=file.parent/'RUN_AFTER_APPROVAL.ps1'
    expected['run_script_sha256']=p.digest(script)
    old.require(script.read_text(encoding='utf-8')==script_text() and plan==expected,'frozen plan/source/budget mismatch')
    old.require(p.digest(plan['frozen_model']['path'])==replay.FROZEN_SHA,'frozen model changed')
    for item in [*plan['source_files'].values(),*plan['references'].values()]:
        old.require(p.digest(item['path'])==item['sha256'],'staging/reference changed')
    for entry,m in zip(plan['entries'],ms):
        path=file.parent/entry['manifest']
        old.require(p.read(path)==m and p.digest(path)==entry['manifest_sha256'],'manifest changed')
    old.require(BUDGET['total_seconds']==600+2*700+90 and BUDGET['explicit_inference']==24+16,'budget arithmetic')
    return dict(status=plan['status'],plan_sha256=p.digest(file),budget=BUDGET,device_commands=0)


def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='action',required=True)
    a=sub.add_parser('prepare')
    for x in ('source-plan','build-receipt','output'):a.add_argument('--'+x,required=True)
    a=sub.add_parser('check');a.add_argument('--plan',required=True)
    a=sub.add_parser('run')
    for x in ('plan','adb','expected-sha'):a.add_argument('--'+x,required=True)
    a.add_argument('--serial',default='')
    a.add_argument('--approved',action='store_true')
    args=parser.parse_args()
    if args.action=='prepare':result=prepare(args.source_plan,args.build_receipt,args.output)
    elif args.action=='check':result=check(args.plan)
    else:
        from tools.d1_arrival_energy_collection_device import run
        result=run(args.plan,args.adb,args.serial,args.expected_sha,args.approved)
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
