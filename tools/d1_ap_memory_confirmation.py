"""Fixed preparation-memory confirmation: PC prepare/check; explicit single-use Run."""
import argparse
import copy
import hashlib
import json
import uuid
from pathlib import Path
from tools import d1_ap_bundle_confirmation as base
from tools import d1_ap_preparation_memory as model

p, old, cal = base.p, base.old, base.cal
ROOT = base.ROOT
BUNDLE = ROOT/'docs/results/ap_memory_confirmation_01'
EXPERIMENT = 'ENERGY-AP-MEMORY-CONFIRM-01'
FOLDER = 'energy_ap_memory_confirm_plan_v1'
RUN = 'energy_ap_memory_confirm_run_v1'
ROLES = ('confirmation_preidle35', 'confirmation_preidle65')
CANDIDATE = ROOT/'docs/results/ap_preparation_memory_01/final/candidate.json'
CANDIDATE_SHA = 'd885b87c32d7df5b812b4cd85dcdae5230f47c9bd16d7ae2807df427b26c1466'
BUDGET = copy.deepcopy(base.BUDGET)


def identity():
    files = (Path(__file__), Path(model.__file__), ROOT/'tools/d1_ap_memory_confirmation_readout.py',
             ROOT/'tools/d1_ap_model_completion.py', ROOT/'tools/d1_ap_idle_response.py',
             ROOT/'tools/d1_arrival_recorded_replay_analysis.py', ROOT/'tools/d1_ap_workload_lag.py',
             BUNDLE/'analysis_contract.json', CANDIDATE)
    return base.identity() | {f.relative_to(ROOT).as_posix():p.digest(f) for f in files}


def specification(source_file, build_file, output):
    output = Path(output)
    plan, templates = base.specification(source_file, build_file, output, 2)
    contract = p.read(BUNDLE/'analysis_contract.json')
    old.require(p.digest(CANDIDATE)==CANDIDATE_SHA and contract['candidate_sha256']==CANDIDATE_SHA,
                'memory candidate changed')
    old.require(contract['roles']==list(ROLES) and contract['post_load_refit'] is False,
                'memory analysis contract')
    plan.pop('bundle_edition',None)
    plan.update(experiment_id=EXPERIMENT, ap_memory_confirmation=True,
        status='PC_READY_DEVICE_UNVERIFIED_NOT_APPROVED',approval='not_approved',
        source_code=identity(),budget=copy.deepcopy(BUDGET),
        analysis_contract=dict(path=str(BUNDLE/'analysis_contract.json'),sha256=p.digest(BUNDLE/'analysis_contract.json')),
        memory_candidate=dict(path=str(CANDIDATE),sha256=CANDIDATE_SHA),
        output_root=str(output.parent/RUN),registry=str(output.parent/'ap_memory_registry'/EXPERIMENT),
        selection='same burst201 CG_DC requests; all release offsets +35 then +65, arrivals unchanged',
        analysis_scope='two prospective fixed-candidate confirmations, n=1 per preparation interval; no refit or accuracy PASS',
        measurement_protocol_change='reuse current signed APK; preparation-to-work passive interval differs by 30s; no added warmup or heating',
        entries=[])
    manifests=[]
    # Both reuse the one-pulse template; never inherit the old second half-pulse.
    for i, role in enumerate(ROLES):
        m=copy.deepcopy(templates[0]);sid=str(uuid.uuid5(uuid.NAMESPACE_URL,EXPERIMENT+'/'+role))
        m.update(experiment_id=EXPERIMENT,session_id=sid,phase=role,ap_bundle_role=role,
                 memory_candidate_sha256=CANDIDATE_SHA)
        for row in m['requests']:
            row['request_id']=str(uuid.uuid5(uuid.NAMESPACE_URL,sid+'/'+str(row['ordinal'])))
            row['release_offset_ns']+=i*30_000_000_000
            old.require(row['offset_ms']*1_000_000<=row['release_offset_ns']<120_000_000_000,
                        'registered release outside window')
        for spec in m['models'].values():spec['identity']['session_id']=sid
        rel=f'manifests/{sid}.json'
        plan['entries'].append(dict(index=i,phase=role,scenario='burst',policy=base.replay.POLICY,
            session_id=sid,manifest=rel,manifest_sha256=hashlib.sha256(p.canonical(m)).hexdigest(),
            requests=24,warmup=8,runtime_creations=4))
        manifests.append(m)
    return plan,manifests


def script_text():
    return base.script_text().replace('d1_ap_bundle_confirmation','d1_ap_memory_confirmation')


def prepare(source_file,build_file,output):
    output=Path(output)
    old.require(output.name==FOLDER and not output.exists(),'fresh dedicated memory plan only')
    plan,manifests=specification(source_file,build_file,output)
    old.require(not Path(plan['registry']).exists() and not Path(plan['output_root']).exists(),
                'occupied/consumed; no resume')
    output.mkdir();(output/'manifests').mkdir()
    for e,m in zip(plan['entries'],manifests):cal.write_new(output/e['manifest'],m)
    script=output/'RUN_AFTER_APPROVAL.ps1';script.write_text(script_text(),encoding='utf8')
    plan['run_script_sha256']=p.digest(script)
    cal.write_new(output/'collection_plan.json',plan)
    return check(output/'collection_plan.json')


def check(file):
    file=Path(file);plan=p.read(file)
    old.require(file.parent.name==FOLDER and file.name=='collection_plan.json','memory plan path')
    old.require(not Path(plan['registry']).exists() and not Path(plan['output_root']).exists(),
                'occupied/consumed; no resume')
    expected,manifests=specification(plan['source_plan']['path'],plan['build_receipt'],file.parent)
    script=file.parent/'RUN_AFTER_APPROVAL.ps1';expected['run_script_sha256']=p.digest(script)
    old.require(script.read_text(encoding='utf8')==script_text() and expected==plan,'frozen plan/code/budget differs')
    base.budget_check(plan['budget'])
    for item in [plan['frozen_model'],plan['candidate_freeze'],plan['memory_candidate'],
                 *plan['source_files'].values(),*plan['references'].values()]:
        old.require(p.digest(item['path'])==item['sha256'],'source/freeze changed')
    for e,m in zip(plan['entries'],manifests):
        old.require(p.read(file.parent/e['manifest'])==m and p.digest(file.parent/e['manifest'])==e['manifest_sha256'],
                    'manifest changed')
    return dict(status=plan['status'],plan_sha256=p.digest(file),budget=plan['budget'],device_commands=0)


def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='action',required=True)
    q=sub.add_parser('prepare')
    for key in ('source-plan','build-receipt','output'):q.add_argument('--'+key,required=True)
    q=sub.add_parser('check');q.add_argument('--plan',required=True)
    q=sub.add_parser('run')
    for key in ('plan','adb','expected-sha'):q.add_argument('--'+key,required=True)
    q.add_argument('--serial',default='');q.add_argument('--approved',action='store_true')
    args=parser.parse_args()
    if args.action=='prepare':result=prepare(args.source_plan,args.build_receipt,args.output)
    elif args.action=='check':result=check(args.plan)
    else:
        from tools.d1_arrival_energy_collection_device import run
        result=run(args.plan,args.adb,args.serial,args.expected_sha,args.approved)
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
