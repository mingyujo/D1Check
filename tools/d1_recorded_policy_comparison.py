"""Bounded ABBA recorded CPU/B2 comparison; PC prepare/check and approved run."""
import argparse
import copy
import csv
import hashlib
import json
import sys
import uuid
from pathlib import Path
from tools import d1_arrival_plan as p
from tools import d1_arrival_energy_collection as old
from tools import d1_arrival_timing_calibration as cal
from tools import d1_arrival_recorded_replay as replay
from tools import d1_arrival_ap_confirmation as prior
from tools import d1_apk_identity as apk

ROOT=replay.ROOT
VERSION='recorded-policy-comparison-v1'
EXPERIMENT='ENERGY-RECORDED-POLICY-COMPARE-01'
FOLDER='energy_recorded_policy_compare_plan_v1'
RUN='energy_recorded_policy_compare_run_v1'
CONTRACT=ROOT/'docs/results/recorded_policy_comparison_01/analysis_contract.json'
ORDER=('CPU_URGENT','B2_PC','B2_PC','CPU_URGENT')
BUDGET=dict(replay.BUDGET,sessions=4,requests=96,warmup=32,explicit_inference=128,
    runtime_creations=16,staging=4,staging_files=28,intersession_cooling_seconds=90,
    total_seconds=3670,adb_commands=13000,per_session_adb_commands=3200,
    adb_recovery_cleanup_reserve=100,connection_preparation_adb_commands=7,
    connection_preparation_timeout_sum_seconds=82)


def budget_check(b):
    old.require(b==BUDGET and b['total_seconds']==600+4*(120+485+50+45)+3*90 and
        b['adb_commands']==4*3200+200 and b['explicit_inference']==96+32 and
        b['staging_files']==4*7 and b['retry']==b['replacement']==b['additional']==0,'comparison budget')


def schedules():
    replay.source_check()
    with replay.TIMELINE.open(encoding='utf-8-sig',newline='') as f: all_rows=list(csv.DictReader(f))
    result={}
    for policy in set(ORDER):
        rows=[r for r in all_rows if (r['mode'],r['scenario'],r['seed'],r['policy'])==('explore','queue','201',policy)]
        old.require(len(rows)==24 and len({r['id'] for r in rows})==24,'saved schedule count')
        actual=[]
        for i,r in enumerate(rows):
            old.require(r['status']=='succeeded' and int(r['arrival_ns'])==i*200_000_000 and
                int(r['arrival_ns'])<=int(r['dispatch_ns'])<120_000_000_000 and
                r['backend']==('CPU' if policy=='CPU_URGENT' or r['task']=='detection' else 'GPU'), 'saved allocation/time')
            actual.append(dict(ordinal=i,source_request_id=r['id'],task_id=r['task'],priority=r['priority'],
                offset_ms=int(r['arrival_ns'])//1_000_000,deadline_ms=int(r['deadline_offset_ns'])//1_000_000,
                release_offset_ns=int(r['dispatch_ns']),recorded_backend=r['backend']))
        result[policy]=actual
    old.require([{k:v for k,v in r.items() if k not in ('recorded_backend','release_offset_ns')} for r in result['CPU_URGENT']]==
                [{k:v for k,v in r.items() if k not in ('recorded_backend','release_offset_ns')} for r in result['B2_PC']],
                'different workload between arms')
    return result


def identity():
    return old.identity() | {x.relative_to(ROOT).as_posix():p.digest(x) for x in
        (Path(__file__),ROOT/'tools/d1_recorded_policy_readout.py',CONTRACT,replay.TIMELINE,replay.OCCUPANCY)}


def specification(source_file,build_file,output):
    source_file,build_file,output=map(Path,(source_file,build_file,output))
    source,build=p.read(source_file),p.read(build_file)
    old.require(old.apk_sources(build['source_code'])==old.apk_sources(cal.code_identity()),'APK/source drift')
    old.require(p.digest(build['apk_path'])==build['apk_sha256'],'APK bytes')
    candidate=apk.inspect(build['apk_path'],source['apk_preflight']['toolchain'])
    old.require(candidate['signer_sha256']==source['apk_preflight']['candidate']['signer_sha256'],'project signer')
    old.require(p.digest(source['frozen_model']['path'])==replay.FROZEN_SHA,'original freeze')
    plan=copy.deepcopy(source)
    for key in ('ap_bundled_confirmation','bundle_edition','resident_control_pair','ap_transfer_confirmation',
                'ap_idle_pulse_followup','candidate_freeze','single_arrival_confirmation'):
        plan.pop(key,None)
    plan.update(experiment_id=EXPERIMENT,status='PC_READY_DEVICE_UNVERIFIED',approval='user_connect_and_measure_20261002',
        recorded_policy_comparison=True,recorded_replay_confirmation=True,source_code=identity(),budget=copy.deepcopy(BUDGET),
        source_plan=dict(path=str(source_file.resolve()),sha256=p.digest(source_file)),
        build_receipt=str(build_file.resolve()),build_receipt_sha256=p.digest(build_file),
        input_bundle=dict(path=str(replay.TIMELINE),sha256=p.digest(replay.TIMELINE)),
        analysis_contract=dict(path=str(CONTRACT),sha256=p.digest(CONTRACT)),
        apk_path=build['apk_path'],apk_sha256=build['apk_sha256'],apk_preflight=dict(source['apk_preflight'],candidate=candidate),
        output_root=str(output.parent/RUN),registry=str(output.parent/'recorded_policy_compare_registry'/EXPERIMENT),
        selection='queue201 saved CPU/B2 schedules; CPU,B2,B2,CPU; no release shift or forced slowdown',
        measurement_protocol_change='new opt-in replay validation for CPU-only; identical signed APK for all four sessions',
        analysis_scope='direct recorded-schedule descriptive comparison; not online policy validation; no model fitting',entries=[])
    template=p.read(source_file.parent/source['entries'][0]['manifest']);schedule=schedules();manifests=[]
    for i,policy in enumerate(ORDER):
        m=copy.deepcopy(template)
        for key in ('ap_bundle_role','candidate_procedure_sha256','ap_idle_response_version','ap_schedule_role','resident_control_version','resident_control_role'):
            m.pop(key,None)
        sid=str(uuid.uuid5(uuid.NAMESPACE_URL,EXPERIMENT+'/'+str(i)))
        requests=copy.deepcopy(schedule[policy])
        for r in requests:r['request_id']=str(uuid.uuid5(uuid.NAMESPACE_URL,sid+'/'+str(r['ordinal'])))
        m.update(experiment_id=EXPERIMENT,session_id=sid,phase=f'comparison_{i}_{policy}',scenario='queue',
            policy=replay.POLICY,replay_version=VERSION,source_policy=policy,source_mode='explore',source_seed=201,
            source_predicted_interference=1.5,source_realized_interference=1.5,replay_source_sha256=p.digest(replay.TIMELINE),
            apk_sha256=build['apk_sha256'],requests=requests,start_ap_gate='numeric-ap-observe-v2')
        for spec in m['models'].values():
            spec['identity']['session_id']=sid;spec['target']['apk_sha256']=build['apk_sha256']
        rel=f'manifests/{sid}.json'
        plan['entries'].append(dict(index=i,phase=m['phase'],scenario='queue',policy=replay.POLICY,source_policy=policy,
            session_id=sid,manifest=rel,manifest_sha256=hashlib.sha256(p.canonical(m)).hexdigest(),requests=24,warmup=8,runtime_creations=4))
        manifests.append(m)
    return plan,manifests


def script_text():
    return prior.script_text({}).replace('d1_arrival_ap_confirmation','d1_recorded_policy_comparison').replace(
        'python -B',"& '"+sys.executable.replace('\\','/')+"' -X utf8 -B")


def prepare(source,build,output):
    output=Path(output)
    old.require(output.name==FOLDER and not output.exists(),'fresh comparison path')
    plan,ms=specification(source,build,output)
    old.require(not Path(plan['registry']).exists() and not Path(plan['output_root']).exists(),'occupied/consumed')
    output.mkdir();(output/'manifests').mkdir()
    for e,m in zip(plan['entries'],ms):cal.write_new(output/e['manifest'],m)
    script=output/'RUN_AFTER_APPROVAL.ps1';script.write_text(script_text(),encoding='utf-8')
    plan['run_script_sha256']=p.digest(script);cal.write_new(output/'collection_plan.json',plan)
    return check(output/'collection_plan.json')


def check(file):
    file=Path(file);plan=p.read(file)
    old.require(file.parent.name==FOLDER and file.name=='collection_plan.json','comparison path')
    old.require(not Path(plan['registry']).exists() and not Path(plan['output_root']).exists(),'occupied/consumed; no resume')
    expected,ms=specification(plan['source_plan']['path'],plan['build_receipt'],file.parent)
    script=file.parent/'RUN_AFTER_APPROVAL.ps1';expected['run_script_sha256']=p.digest(script)
    old.require(plan==expected and script.read_text(encoding='utf-8')==script_text(),'frozen plan/source mismatch')
    budget_check(plan['budget'])
    for x in [*plan['source_files'].values(),*plan['references'].values()]:old.require(p.digest(x['path'])==x['sha256'],'staging/reference changed')
    for e,m in zip(plan['entries'],ms):old.require(p.read(file.parent/e['manifest'])==m and p.digest(file.parent/e['manifest'])==e['manifest_sha256'],'manifest drift')
    return dict(status=plan['status'],plan_sha256=p.digest(file),budget=BUDGET,device_commands=0)


def main():
    parser=argparse.ArgumentParser();sub=parser.add_subparsers(dest='action',required=True)
    a=sub.add_parser('prepare')
    for x in ('source-plan','build-receipt','output'):a.add_argument('--'+x,required=True)
    a=sub.add_parser('check');a.add_argument('--plan',required=True)
    a=sub.add_parser('run')
    for x in ('plan','adb','serial','expected-sha'):a.add_argument('--'+x,required=True)
    a.add_argument('--approved',action='store_true');args=parser.parse_args()
    if args.action=='prepare':result=prepare(args.source_plan,args.build_receipt,args.output)
    elif args.action=='check':result=check(args.plan)
    else:
        from tools.d1_arrival_energy_collection_device import run
        result=run(args.plan,args.adb,args.serial,args.expected_sha,args.approved)
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
