"""Two consecutive, fixed-procedure AP confirmations; no new development fit.

Prepare/Check are PC only. Run reuses the installed APK, selected transport,
single-use runner and its existing failure/recovery path. No deployment fallback.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
import sys
import uuid
from pathlib import Path
from tools import d1_arrival_plan as p
from tools import d1_arrival_energy_collection as old
from tools import d1_arrival_recorded_replay as replay
from tools import d1_arrival_timing_calibration as cal
from tools import d1_resident_control_plan as control
from tools import d1_ap_transfer_confirmation as transfer

ROOT = replay.ROOT
BUNDLE = ROOT/'docs/results/ap_bundle_confirmation_01'
EXPERIMENT = 'ENERGY-AP-BUNDLE-CONFIRM-01'
FOLDER = 'energy_ap_bundle_confirm_plan_v1'
RUN = 'energy_ap_bundle_confirm_run_v1'
ROLES = ('confirmation_one_pulse', 'confirmation_two_pulses')
BUDGET = dict(control.BUDGET, development=0, confirmation=2, requests=48,
    explicit_inference=64, apk_transfers=0, installs=0,
    installed_preflight_seconds=600, per_session_adb_commands=3200)


def run_names(edition):
    """Explicit separate invocation IDs; never select or retry an edition automatically."""
    old.require(type(edition) is int and edition in (1,2),'dedicated bundle edition')
    return (f'ENERGY-AP-BUNDLE-CONFIRM-{edition:02d}',
            f'energy_ap_bundle_confirm_plan_v{edition}',f'energy_ap_bundle_confirm_run_v{edition}')


def identity():
    files = (Path(__file__), Path(transfer.__file__), Path(control.__file__),
             ROOT/'tools/d1_ap_bundle_readout.py', BUNDLE/'analysis_contract.json')
    return old.identity() | {x.relative_to(ROOT).as_posix():p.digest(x) for x in files}


def budget_check(b):
    old.require(b == BUDGET and b['explicit_inference'] == 48+16 and
        b['total_seconds'] == 600+2*(120+485+50+45)+90 and
        b['adb_commands'] == 2*3200+200 and b['runtime_creations'] == 8 and
        b['staging_files'] == 2*7 and b['retry'] == b['replacement'] == b['additional'] == 0,
        'bundle budget arithmetic')


def specification(source_file, build_file, output, edition=1):
    """Reuse signed-build and source identity verification; never reuse a claim."""
    source_file, build_file, output = map(Path, (source_file, build_file, output))
    experiment,folder,run=run_names(edition)
    plan, templates = control.specification(source_file, build_file, output)
    for key in ('resident_control_pair',):
        plan.pop(key, None)
    freeze = output.parent/'energy_ap_idle_response_run_v1/ap_model_freeze.json'
    old.require(p.digest(freeze) == transfer.FREEZE_SHA, 'candidate procedure changed')
    contract = p.read(BUNDLE/'analysis_contract.json')
    old.require(contract['candidate_freeze_sha256'] == transfer.FREEZE_SHA and
                contract['post_load_refit'] is False, 'analysis contract changed')
    plan.update(experiment_id=experiment, bundle_edition=edition,status='PC_READY_DEVICE_UNVERIFIED',
        approval='approved_user_bundle_20261002' if edition==2 else 'approved_user_bundle_20261001',
        ap_bundled_confirmation=True,
        source_code=identity(), budget=copy.deepcopy(BUDGET),
        source_plan=dict(path=str(source_file.resolve()),sha256=p.digest(source_file)),
        analysis_contract=dict(path=str(BUNDLE/'analysis_contract.json'),
                               sha256=p.digest(BUNDLE/'analysis_contract.json')),
        candidate_freeze=dict(path=str(freeze),sha256=transfer.FREEZE_SHA),
        output_root=str(output.parent/run), registry=str(output.parent/'ap_bundle_registry'/experiment),
        selection='fixed burst201 CG_DC; one pulse +35, then two half-pulses +35/+60',
        analysis_scope='two prospective fixed-procedure confirmations, n=1 per history; no refit or accuracy PASS',
        measurement_protocol_change='same current 3d8 APK for both; protocol transfer from 747 candidate-development APK',
        entries=[])
    result=[]
    for index,role in enumerate(ROLES):
        m=copy.deepcopy(templates[1])
        for key in ('resident_control_version','resident_control_role'):
            m.pop(key,None)
        sid=str(uuid.uuid5(uuid.NAMESPACE_URL, experiment+'/'+role))
        rows=copy.deepcopy(p.read(control.BUNDLE/'load_input.json')['requests'])
        for row in rows:
            for key in list(row):
                if key.startswith('pc_'): del row[key]
            row['request_id']=str(uuid.uuid5(uuid.NAMESPACE_URL,sid+'/'+str(row['ordinal'])))
            if index==1 and row['ordinal']>=12:
                row['release_offset_ns']+=25_000_000_000
            old.require(row['offset_ms']*1_000_000 <= row['release_offset_ns'] < 120_000_000_000,
                        'release outside common window')
        m.update(experiment_id=experiment,session_id=sid,phase=role,requests=rows,
                 ap_bundle_role=role,candidate_procedure_sha256=transfer.FREEZE_SHA)
        for spec in m['models'].values():
            spec['identity']['session_id']=sid
        rel=f'manifests/{sid}.json'
        plan['entries'].append(dict(index=index,phase=role,scenario='burst',policy=replay.POLICY,
            session_id=sid,manifest=rel,manifest_sha256=hashlib.sha256(p.canonical(m)).hexdigest(),
            requests=24,warmup=8,runtime_creations=4))
        result.append(m)
    return plan,result


def script_text():
    return control.script_text().replace('d1_resident_control_plan','d1_ap_bundle_confirmation').replace(
        'python -B', "& '"+sys.executable.replace('\\','/')+"' -X utf8 -B")


def prepare(source_file,build_file,output,edition=1):
    output=Path(output)
    _,folder,_=run_names(edition)
    old.require(output.name==folder and not output.exists(),'fresh dedicated bundle only')
    plan,manifests=specification(source_file,build_file,output,edition)
    old.require(not Path(plan['registry']).exists() and not Path(plan['output_root']).exists(),
                'occupied/consumed plan; no resume')
    output.mkdir();(output/'manifests').mkdir()
    for e,m in zip(plan['entries'],manifests): cal.write_new(output/e['manifest'],m)
    script=output/'RUN_AFTER_APPROVAL.ps1';script.write_text(script_text(),encoding='utf-8')
    plan['run_script_sha256']=p.digest(script)
    cal.write_new(output/'collection_plan.json',plan)
    return check(output/'collection_plan.json')


def check(file):
    file=Path(file);plan=p.read(file)
    edition=plan.get('bundle_edition',1)
    _,folder,_=run_names(edition)
    old.require(file.parent.name==folder and file.name=='collection_plan.json','bundle path')
    old.require(not Path(plan['output_root']).exists() and not Path(plan['registry']).exists(),
                'occupied/consumed plan; no resume')
    expected,manifests=specification(plan['source_plan']['path'],plan['build_receipt'],file.parent,edition)
    script=file.parent/'RUN_AFTER_APPROVAL.ps1'
    expected['run_script_sha256']=p.digest(script)
    old.require(script.read_text(encoding='utf-8')==script_text() and plan==expected,
                'frozen source/plan/budget mismatch')
    budget_check(plan['budget'])
    for item in [plan['frozen_model'],plan['candidate_freeze'],*plan['source_files'].values(),*plan['references'].values()]:
        old.require(p.digest(item['path'])==item['sha256'],'source/freeze changed')
    for e,m in zip(plan['entries'],manifests):
        old.require(p.read(file.parent/e['manifest'])==m and
                    p.digest(file.parent/e['manifest'])==e['manifest_sha256'],'manifest changed')
    return dict(status=plan['status'],plan_sha256=p.digest(file),budget=BUDGET,device_commands=0)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='action',required=True)
    a=sub.add_parser('prepare')
    for k in ('source-plan','build-receipt','output'):a.add_argument('--'+k,required=True)
    a.add_argument('--edition',type=int,choices=(1,2),default=1)
    a=sub.add_parser('check');a.add_argument('--plan',required=True)
    a=sub.add_parser('run')
    for k in ('plan','adb','expected-sha'):a.add_argument('--'+k,required=True)
    a.add_argument('--serial',default='');a.add_argument('--approved',action='store_true')
    args=parser.parse_args()
    if args.action=='prepare':result=prepare(args.source_plan,args.build_receipt,args.output,args.edition)
    elif args.action=='check':result=check(args.plan)
    else:
        from tools.d1_arrival_energy_collection_device import run
        result=run(args.plan,args.adb,args.serial,args.expected_sha,args.approved)
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
