"""PC plan for a fixed background/load-timing contrast; Run requires later approval."""
import argparse
import copy
import hashlib
import json
import uuid
from pathlib import Path
from tools import d1_ap_memory_confirmation as memory

p, old, cal = memory.p, memory.old, memory.cal
ROOT = memory.ROOT
BUNDLE = ROOT/'docs/results/ap_background_contrast_01'
EXPERIMENT = 'ENERGY-AP-BACKGROUND-CONTRAST-01'
FOLDER = 'energy_ap_background_contrast_plan_v1'
RUN = 'energy_ap_background_contrast_run_v1'
ROLES = ('control_first','load35_forward','load65_forward','load65_reverse','load35_reverse','control_last')
CONDITIONS = ('C','L35','L65','L65','L35','C')
BUDGET = dict(memory.BUDGET, sessions=6, development=0, confirmation=0,
    diagnostic_sessions=6, requests=96, warmup=48, explicit_inference=144,
    runtime_creations=24, staging=6, staging_files=42, total_seconds=5250, adb_commands=19400)


def identity():
    files = (Path(__file__), ROOT/'tools/d1_ap_background_contrast_readout.py', BUNDLE/'analysis_contract.json')
    return memory.identity() | {f.relative_to(ROOT).as_posix():p.digest(f) for f in files}


def budget_check(b):
    old.require(b == BUDGET and b['total_seconds']==600+6*(120+485+50+45)+5*90 and
        b['adb_commands']==6*3200+200 and b['explicit_inference']==4*24+6*8 and
        b['runtime_creations']==6*4 and b['staging_files']==6*7 and
        b['apk_transfers']==b['installs']==b['retry']==b['replacement']==b['additional']==0,
        'contrast budget arithmetic')


def specification(source_file, build_file, output):
    output=Path(output)
    plan,templates=memory.specification(source_file,build_file,output)
    contract=p.read(BUNDLE/'analysis_contract.json')
    old.require(contract['roles']==list(ROLES) and contract['conditions']==list(CONDITIONS) and
        contract['memory_candidate_sha256']==memory.CANDIDATE_SHA and
        contract['initialization_cutoff_s']==35 and contract['post_load_refit'] is False,'contrast contract')
    plan.pop('ap_memory_confirmation',None)
    plan.update(experiment_id=EXPERIMENT,ap_background_contrast=True,resident_control_pair=True,
        source_code=identity(),budget=copy.deepcopy(BUDGET),
        analysis_contract=dict(path=str(BUNDLE/'analysis_contract.json'),sha256=p.digest(BUNDLE/'analysis_contract.json')),
        output_root=str(output.parent/RUN),registry=str(output.parent/'ap_background_registry'/EXPERIMENT),
        selection='C,L35,L65,L65,L35,C fixed before new outcomes; no outcome-based selection',
        analysis_scope='structure discrimination; fixed-memory conditional evaluation; no coefficient fitting or accuracy PASS',
        measurement_protocol_change='same 74e APK/resident/warmup/polling for six arms; AP initialization cutoff common+35 in every arm',
        entries=[])
    manifests=[]
    for i,(role,condition) in enumerate(zip(ROLES,CONDITIONS)):
        m=copy.deepcopy(templates[0]);sid=str(uuid.uuid5(uuid.NAMESPACE_URL,EXPERIMENT+'/'+role))
        m.update(experiment_id=EXPERIMENT,session_id=sid,phase=role,ap_bundle_role=role,
            background_condition=condition,resident_control_version=memory.base.control.VERSION,
            resident_control_role='no_load_control' if condition=='C' else 'registered_load')
        if condition=='C':m['requests']=[]
        for row in m['requests']:
            row['request_id']=str(uuid.uuid5(uuid.NAMESPACE_URL,sid+'/'+str(row['ordinal'])))
            if condition=='L65':row['release_offset_ns']+=30_000_000_000
            old.require(row['offset_ms']*1_000_000<=row['release_offset_ns']<120_000_000_000,'release boundary')
        for spec in m['models'].values():spec['identity']['session_id']=sid
        count=memory.base.control.request_count(m)
        rel=f'manifests/{sid}.json'
        plan['entries'].append(dict(index=i,phase=role,condition=condition,scenario='burst',policy=memory.base.replay.POLICY,
            session_id=sid,manifest=rel,manifest_sha256=hashlib.sha256(p.canonical(m)).hexdigest(),
            requests=count,warmup=8,runtime_creations=4))
        manifests.append(m)
    budget_check(plan['budget'])
    return plan,manifests


def script_text():
    return memory.script_text().replace('d1_ap_memory_confirmation','d1_ap_background_contrast')


def prepare(source_file,build_file,output):
    output=Path(output)
    old.require(output.name==FOLDER and not output.exists(),'fresh dedicated contrast plan only')
    plan,manifests=specification(source_file,build_file,output)
    old.require(not Path(plan['registry']).exists() and not Path(plan['output_root']).exists(),'occupied/consumed; no resume')
    output.mkdir();(output/'manifests').mkdir()
    for e,m in zip(plan['entries'],manifests):cal.write_new(output/e['manifest'],m)
    script=output/'RUN_AFTER_APPROVAL.ps1';script.write_text(script_text(),encoding='utf-8')
    plan['run_script_sha256']=p.digest(script)
    cal.write_new(output/'collection_plan.json',plan)
    return check(output/'collection_plan.json')


def check(file):
    file=Path(file);plan=p.read(file)
    old.require(file.parent.name==FOLDER and file.name=='collection_plan.json','contrast plan path')
    old.require(not Path(plan['registry']).exists() and not Path(plan['output_root']).exists(),'occupied/consumed; no resume')
    expected,manifests=specification(plan['source_plan']['path'],plan['build_receipt'],file.parent)
    script=file.parent/'RUN_AFTER_APPROVAL.ps1';expected['run_script_sha256']=p.digest(script)
    old.require(script.read_text(encoding='utf-8')==script_text() and expected==plan,'frozen plan/code/budget differs')
    for item in [plan['frozen_model'],plan['candidate_freeze'],plan['memory_candidate'],*plan['source_files'].values(),*plan['references'].values()]:
        old.require(p.digest(item['path'])==item['sha256'],'source/freeze changed')
    for e,m in zip(plan['entries'],manifests):
        old.require(p.read(file.parent/e['manifest'])==m and p.digest(file.parent/e['manifest'])==e['manifest_sha256'],'manifest changed')
    return dict(status=plan['status'],plan_sha256=p.digest(file),budget=plan['budget'],device_commands=0)


def main():
    q=argparse.ArgumentParser(description=__doc__);sub=q.add_subparsers(dest='action',required=True)
    a=sub.add_parser('prepare')
    for key in ('source-plan','build-receipt','output'):a.add_argument('--'+key,required=True)
    a=sub.add_parser('check');a.add_argument('--plan',required=True)
    a=sub.add_parser('run')
    for key in ('plan','adb','expected-sha'):a.add_argument('--'+key,required=True)
    a.add_argument('--serial',default='');a.add_argument('--approved',action='store_true');args=q.parse_args()
    if args.action=='prepare':result=prepare(args.source_plan,args.build_receipt,args.output)
    elif args.action=='check':result=check(args.plan)
    else:
        from tools.d1_arrival_energy_collection_device import run
        result=run(args.plan,args.adb,args.serial,args.expected_sha,args.approved)
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
