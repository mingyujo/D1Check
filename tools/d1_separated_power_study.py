"""Separate-state development then immutable mixed-arrival confirmation; shared lifecycle runner."""
import argparse
import copy
import hashlib
import json
import sys
import shutil
import uuid
from pathlib import Path
import numpy as np
from tools import d1_online_policy_study as base
from tools import d1_online_policy_model as original
from tools import d1_separated_power_protocol as protocol
from tools import d1_arrival_plan as p

ROOT=base.ROOT
NAME='SEPARATED-POWER-STUDY-01'
FOLDER='separated_power_plan_v1'
CONTRACT=ROOT/'docs/results/online_policy_study_01/separated_power_v1/contract.json'
require=base.require


def identity():
    return base.identity() | {f.relative_to(ROOT).as_posix():p.digest(f) for f in (Path(__file__),Path(protocol.__file__),CONTRACT)}


def root_script():return base.root_script().replace('d1_online_policy_study','d1_separated_power_study')
def block_script():return base.block_script().replace('d1_online_policy_study','d1_separated_power_study')
def imported_cases(study):return []


class Model:
    @staticmethod
    def develop(cases):
        require(len(cases)==3 and all(c['study_phase']=='development' for c in cases),'development3 only')
        require([c['policy'] for c in cases]==list(original.POLICIES),'fixed policy order')
        contract=p.read(CONTRACT);binding=contract['unchanged_model']
        require(p.digest(binding['path'])==binding['sha256'],'original model drift')
        result=copy.deepcopy(p.read(binding['path'])['model']);x=[];y=[];service={}
        for c in cases:
            for a in range(35,120,5):
                x.append(original.exposure(c['inputs']['segments'],a,a+5))
                y.append(original.energy_at(c,a,a+5)-5*c['preload_power_w'])
            cells={}
            for r in c['rows']:
                key=r['task_id']+'_'+r['selected_backend']+'_'+r['priority']
                cells.setdefault(key,[]).append([r[b]-r[a] for a,b in zip(original.FIELDS,original.FIELDS[1:])])
            service[c['policy']]=dict(phase_means_ns={k:np.mean(v,axis=0).tolist() for k,v in cells.items()},counts={k:len(v) for k,v in cells.items()})
        x=np.array(x);y=np.array(y)
        require(np.isfinite(x).all() and np.isfinite(y).all() and np.linalg.matrix_rank(x)==4,'energy unidentified')
        coef=original.nnls(x,y)
        result.update(version='separated-power-model-v1',energy_baseline_mode='session_preload',energy_increment_w=dict(zip(original.STATES,coef.tolist())),
            service=service,development_ids=[c['id'] for c in cases],energy_design_singular_values=np.linalg.svd(x,compute_uv=False).tolist(),
            energy_fit_rmse_j=float(np.mean((x@coef-y)**2)**.5),preload_power_window_s=[-20,30],
            scope='registered separated development/mixed confirmation only; AP unchanged; no generic support',experiment_ready=False,accuracy_pass=None)
        return result

    @staticmethod
    def evaluate(cases,frozen):
        roles={c['study_phase'] for c in cases};require(len(roles)==1,'one phase evaluation')
        return original.evaluate(cases,frozen,planning_input_role=next(iter(roles)))


model=Model


def block_spec(file,phase,freeze=None):
    file=Path(file);study=p.read(file);source=p.read(study['source_plan']['path']);build=p.read(study['build_receipt']['path']);contract=p.read(CONTRACT)
    order=contract[phase+'_order'];n=len(order);plan=copy.deepcopy(source)
    for k in list(plan):
        if k.startswith('ap_') or k in ('online_sampling_audit','imported_completed','study_freeze','study_plan_file'):plan.pop(k)
    budget=dict(source['budget'],sessions=n,requests=n*96,warmup=n*8,explicit_inference=n*104,runtime_creations=n*4,staging=n,staging_files=n*7,
        total_seconds=600+n*700+(n-1)*90,adb_commands=n*3200+200,apk_transfers=int(phase=='development'),installs=int(phase=='development'),
        fixed_observation_seconds=n*210,installed_preflight_seconds=600,intersession_cooling_seconds=90)
    exp=NAME+'-'+phase.upper();plan.update(experiment_id=exp,separated_power_study=True,online_policy_study=True,
        online_configuration_owner_v1=True,study_phase=phase,study_plan_file=str(file),study_freeze=freeze,installed_only=phase=='confirmation',
        source_code=identity(),budget=budget,output_root=str(Path(study['output_root'])/phase),registry=str(Path(study['block_registry_root'])/exp),
        apk_path=build['apk_path'],apk_sha256=build['apk_sha256'],apk_preflight=dict(source['apk_preflight'],candidate=study['candidate']),
        analysis_contract=study['contract'],build_receipt=study['build_receipt']['path'],build_receipt_sha256=study['build_receipt']['sha256'],
        input_bundle=study['contract'],entries=[],status='PC_READY_DEVICE_UNVERIFIED',approval='user_autonomous_measurement',
        measurement_protocol_change='registered separated/mixed48:48 arrivals,900ms power sampler,preload mean(-20,30); no device slowdown',
        analysis_scope='development3 frozen before independent6; observed initial inputs only; no automatic accuracy PASS')
    sourcefile=Path(study['source_plan']['path']);template=p.read(sourcefile.parent/source['entries'][0]['manifest']);manifests=[]
    for i,policy in enumerate(order):
        m=copy.deepcopy(template);sid=str(uuid.uuid5(uuid.NAMESPACE_URL,exp+'/'+str(i)))
        for k in list(m):
            if k.startswith(('replay_','resident_control_')):m.pop(k)
        rows=protocol.requests(phase,sid)
        for r in rows:r['request_id']=str(uuid.uuid5(uuid.NAMESPACE_URL,sid+'/'+str(r['ordinal'])))
        m.update(experiment_id=exp,session_id=sid,phase=f'{phase}_{i}_{policy}',scenario='separated_power',policy=policy,
            policy_study_version='online-policy-model-study-v1',policy_study_role=phase,power_identification_version=protocol.VERSION,
            power_sampling_version='online-power-phase-audit-v1',power_sample_period_ms=900,requests=rows,apk_sha256=build['apk_sha256'])
        for spec in m['models'].values():spec['identity']['session_id']=sid;spec['target']['apk_sha256']=build['apk_sha256']
        rel=f'manifests/{sid}.json';plan['entries'].append(dict(index=i,phase=m['phase'],condition=policy,scenario=m['scenario'],policy=policy,
            session_id=sid,manifest=rel,manifest_sha256=hashlib.sha256(p.canonical(m)).hexdigest(),requests=96,warmup=8,runtime_creations=4));manifests.append(m)
    plan['run_script_sha256']=hashlib.sha256(block_script().encode()).hexdigest()
    return plan,manifests


def verify(study):
    require(study['source_code']==identity(),'source changed')
    for key in ('source_plan','build_receipt','contract','old_ap_model'):
        binding=study[key];require(p.digest(binding['path'])==binding['sha256'],'binding changed '+key)
    build=p.read(study['build_receipt']['path'])
    require(p.digest(build['apk_path'])==build['apk_sha256'],'APK hash')
    require(base.old.apk_sources(build['source_code'])==base.old.apk_sources(base.cal.code_identity()),'APK source')
    require(study['budget']==p.read(CONTRACT)['budget'],'budget changed')


def check_block(file,allow_consumed=False,allow_template=False):
    file=Path(file);plan=p.read(file);study=p.read(plan['study_plan_file']);verify(study)
    expected,ms=block_spec(plan['study_plan_file'],plan['study_phase'],plan['study_freeze']);require(expected==plan,'block drift')
    require((file.parent/'RUN_AFTER_APPROVAL.ps1').read_text(encoding='utf8')==block_script(),'script changed')
    if not allow_consumed:require(not Path(plan['output_root']).exists() and not Path(plan['registry']).exists(),'consumed')
    if plan['study_phase']=='confirmation' and not allow_template:
        binding=plan['study_freeze'];require(binding is not None and p.digest(binding['path'])==binding['sha256'],'freeze absent')
        frozen=p.read(binding['path']);require(frozen['source_code']==identity() and frozen['contract_sha256']==study['contract']['sha256'],'freeze changed')
        receipt=p.read(Path(study['output_root'])/'development/FINAL_RECEIPT.json')
        require(receipt['status']=='completed_descriptive_only' and receipt['sessions']==3,'development incomplete')
    for b in [plan['frozen_model'],*plan['source_files'].values(),*plan['references'].values()]:require(p.digest(b['path'])==b['sha256'],'input/model drift')
    for e,m in zip(plan['entries'],ms):require(p.read(file.parent/e['manifest'])==m and p.digest(file.parent/e['manifest'])==e['manifest_sha256'],'manifest drift')
    return dict(device_commands=0,budget=plan['budget'],sha256=p.digest(file))


def check(file):
    file=Path(file);study=p.read(file);verify(study)
    require(file.parent.name==FOLDER and not Path(study['registry']).exists() and not Path(study['output_root']).exists(),'occupied')
    require((file.parent/'RUN_AFTER_APPROVAL.ps1').read_text(encoding='utf8')==root_script(),'root script')
    source=p.read(study['source_plan']['path']);build=p.read(study['build_receipt']['path'])
    require(base.apk.inspect(build['apk_path'],source['apk_preflight']['toolchain'])==study['candidate'],'candidate identity')
    check_block(file.parent/'development/collection_plan.json')
    check_block(file.parent/'confirmation/template_plan.json',allow_template=True)
    return dict(status='PC_READY_DEVICE_UNVERIFIED',sha256=p.digest(file),budget=study['budget'],device_commands=0)


def prepare(source,build,output):
    source,build,output=map(Path,(source,build,output));require(output.name==FOLDER and not output.exists(),'new plan only')
    contract=p.read(CONTRACT);src,bld=p.read(source),p.read(build)
    candidate=base.apk.inspect(bld['apk_path'],src['apk_preflight']['toolchain'])
    require(candidate['signer_sha256']==src['apk_preflight']['candidate']['signer_sha256'],'project signer')
    study=dict(version=protocol.VERSION,experiment_id=NAME,source_code=identity(),budget=contract['budget'],
        source_plan=dict(path=str(source),sha256=p.digest(source)),build_receipt=dict(path=str(build),sha256=p.digest(build)),
        contract=dict(path=str(CONTRACT),sha256=p.digest(CONTRACT)),old_ap_model=contract['unchanged_model'],candidate=candidate,
        output_root=str(output.parent/'separated_power_run_v1'),registry=str(output.parent/'separated_power_registry'/NAME),
        block_registry_root=str(output.parent/'separated_power_block_registry'),experiment_ready=False,approval='user_autonomous_measurement')
    verify(study);require(not Path(study['output_root']).exists() and not Path(study['registry']).exists(),'consumed')
    output.mkdir();base.cal.write_new(output/'study_plan.json',study);(output/'RUN_AFTER_APPROVAL.ps1').write_text(root_script(),encoding='utf8')
    for phase in ('development','confirmation'):
        plan,ms=block_spec(output/'study_plan.json',phase);folder=output/phase;(folder/'manifests').mkdir(parents=True)
        for e,m in zip(plan['entries'],ms):base.cal.write_new(folder/e['manifest'],m)
        base.cal.write_new(folder/('collection_plan.json' if phase=='development' else 'template_plan.json'),plan)
        (folder/'RUN_AFTER_APPROVAL.ps1').write_text(block_script(),encoding='utf8')
    return check(output/'study_plan.json')


def load_cases(file):
    file=Path(file);plan=p.read(file);check_block(file,allow_consumed=True);receipt=p.read(Path(plan['output_root'])/'FINAL_RECEIPT.json')
    require(receipt['status']=='completed_descriptive_only' and receipt['sessions']==len(plan['entries']),'incomplete block')
    cases=[original.load_case(file,plan,e) for e in plan['entries']]
    for c in cases:
        protocol.validate(plan['study_phase'],c['manifest_requests'])
        c['preload_power_w']=original.energy_at(c,-20,30)/50
        c['preload_power_window_s']=[-20,30]
    return cases


def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','check','check-block','run','run-block'])
    for key in ('source','build','output','plan','adb','expected-sha','serial'):parser.add_argument('--'+key)
    parser.add_argument('--approved',action='store_true');a=parser.parse_args()
    if a.action=='prepare':result=prepare(a.source,a.build,a.output)
    elif a.action=='check':result=check(a.plan)
    elif a.action=='check-block':result=check_block(a.plan)
    elif a.action=='run':
        study=p.read(a.plan)
        require(shutil.disk_usage(Path(study['output_root']).parent).free>=p.read(CONTRACT)['minimum_host_free_bytes'],'host storage reserve; no claim/device calls')
        result=base.run(a.plan,a.adb,a.expected_sha,a.approved,adapter=sys.modules[__name__])
    else:
        from tools.d1_arrival_energy_collection_device import run
        result=run(a.plan,a.adb,a.serial or '',a.expected_sha,a.approved)
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
