"""Reuse eligible CPU development, collect remaining two, freeze, confirm six."""
import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path
from tools import d1_separated_power_study as prior
from tools import d1_preparation_observation as observation

p=prior.p
base=prior.base
ROOT=prior.ROOT
CONTRACT=ROOT/'docs/results/online_policy_study_01/separated_power_followup/contract.json'
NAME='SEPARATED-POWER-FOLLOWUP-02'
FOLDER='separated_power_plan_v2'
model=prior.model
require=prior.require


def identity():
    return prior.identity() | {f.relative_to(ROOT).as_posix():p.digest(f) for f in (Path(__file__),Path(observation.__file__),CONTRACT,CONTRACT.with_name('contract_v3.json'),CONTRACT.with_name('contract_v4.json'))}


def root_script():return prior.root_script().replace('d1_separated_power_study','d1_separated_power_followup')
def block_script():return prior.block_script().replace('d1_separated_power_study','d1_separated_power_followup')


def imported_cases(study):
    bindings=study['imported_development']
    if isinstance(bindings,dict):bindings=[bindings]
    cases=[]
    for binding in bindings:
        for name,digest in binding['files'].items():require(p.digest(name)==digest,'imported evidence changed')
        file=Path(binding['plan']);plan=p.read(file);entry=plan['entries'][binding.get('index',0)]
        case=prior.original.load_case(file,plan,entry)
        prior.protocol.validate('development',case['manifest_requests'])
        case['preload_power_w']=prior.original.energy_at(case,-20,30)/50
        case['preload_power_window_s']=[-20,30]
        cases.append(case)
    require([c['policy'] for c in cases]==list(prior.original.POLICIES)[:len(cases)] and len(cases) in (1,2),'ordered eligible development import only')
    return cases


def block_spec(file,phase,freeze=None):
    study=p.read(file);contract=Path(study['contract']['path'])
    plan,manifests=prior.block_spec(file,phase,freeze,contract_file=contract,experiment_id=study['experiment_id'])
    plan.update(source_code=identity(),separated_power_followup=True,installed_only=True,
                prewarmup_observation=p.read(contract).get('prewarmup_observation_version',observation.VERSION),
                measurement_protocol_change='one silent reaped prewarmup listing timeout may be an observation gap; no post-arm change; prior CPU development retained as earlier block')
    plan['budget'].update(apk_transfers=0,installs=0)
    plan['run_script_sha256']=hashlib.sha256(block_script().encode()).hexdigest()
    return plan,manifests


def verify(study):
    require(study['source_code']==identity(),'source changed')
    for key in ('source_plan','build_receipt','contract','old_ap_model'):
        b=study[key];require(p.digest(b['path'])==b['sha256'],'binding changed '+key)
    b=p.read(study['build_receipt']['path']);require(p.digest(b['apk_path'])==b['apk_sha256'],'APK changed')
    require(base.old.apk_sources(b['source_code'])==base.old.apk_sources(base.cal.code_identity()),'APK source')
    require(study['budget']==p.read(study['contract']['path'])['budget'],'budget changed')
    imported_cases(study)


def check_block(file,allow_consumed=False,allow_template=False):
    file=Path(file);plan=p.read(file);study=p.read(plan['study_plan_file']);verify(study)
    expected,manifests=block_spec(plan['study_plan_file'],plan['study_phase'],plan['study_freeze'])
    require(expected==plan,'block drift')
    require((file.parent/'RUN_AFTER_APPROVAL.ps1').read_text(encoding='utf8')==block_script(),'script drift')
    if not allow_consumed:require(not Path(plan['output_root']).exists() and not Path(plan['registry']).exists(),'consumed')
    if plan['study_phase']=='confirmation' and not allow_template:
        b=plan['study_freeze'];require(b is not None and p.digest(b['path'])==b['sha256'],'freeze missing')
        f=p.read(b['path']);require(f['source_code']==identity() and f['contract_sha256']==study['contract']['sha256'],'freeze drift')
        r=p.read(Path(study['output_root'])/'development/FINAL_RECEIPT.json')
        require(r['status']=='completed_descriptive_only' and r['sessions']==len(p.read(study['contract']['path'])['development_order']),'remaining development incomplete')
    for b in [plan['frozen_model'],*plan['source_files'].values(),*plan['references'].values()]:require(p.digest(b['path'])==b['sha256'],'source input drift')
    for e,m in zip(plan['entries'],manifests):require(p.read(file.parent/e['manifest'])==m and p.digest(file.parent/e['manifest'])==e['manifest_sha256'],'manifest drift')
    return dict(device_commands=0,budget=plan['budget'],sha256=p.digest(file))


def check(file):
    file=Path(file);s=p.read(file);verify(s)
    require(file.parent.name==s.get('plan_folder',FOLDER) and not Path(s['registry']).exists() and not Path(s['output_root']).exists(),'consumed')
    require((file.parent/'RUN_AFTER_APPROVAL.ps1').read_text(encoding='utf8')==root_script(),'root script')
    require(base.apk.inspect(s['candidate']['apk_path'] if 'apk_path' in s['candidate'] else p.read(s['build_receipt']['path'])['apk_path'],p.read(s['source_plan']['path'])['apk_preflight']['toolchain'])==s['candidate'],'candidate identity')
    check_block(file.parent/'development/collection_plan.json')
    check_block(file.parent/'confirmation/template_plan.json',allow_template=True)
    return dict(status='PC_READY_DEVICE_UNVERIFIED',sha256=p.digest(file),budget=s['budget'],device_commands=0)


def load_cases(file):
    file=Path(file);plan=p.read(file);check_block(file,allow_consumed=True)
    r=p.read(Path(plan['output_root'])/'FINAL_RECEIPT.json')
    require(r['status']=='completed_descriptive_only' and r['sessions']==len(plan['entries']),'incomplete block')
    cases=[prior.original.load_case(file,plan,e) for e in plan['entries']]
    for c in cases:
        prior.protocol.validate(plan['study_phase'],c['manifest_requests'])
        c['preload_power_w']=prior.original.energy_at(c,-20,30)/50;c['preload_power_window_s']=[-20,30]
    return cases


def prepare(previous,output):
    previous,output=Path(previous),Path(output);s=p.read(previous)
    require(output.name==FOLDER and not output.exists(),'new plan only')
    oldplan=previous.parent/'development/collection_plan.json';old=p.read(oldplan)
    folder=Path(old['output_root'])/f"00_{old['entries'][0]['session_id']}"
    files=[oldplan,Path(s['output_root'])/'FINAL_RECEIPT.json',*filter(Path.is_file,folder.rglob('*'))]
    s.update(experiment_id=NAME,source_code=identity(),budget=p.read(CONTRACT)['budget'],
             contract=dict(path=str(CONTRACT),sha256=p.digest(CONTRACT)),
             imported_development=dict(plan=str(oldplan),files={str(f):p.digest(f) for f in files}),
             output_root=str(output.parent/'separated_power_run_v2'),registry=str(output.parent/'separated_power_registry'/NAME))
    verify(s);require(not Path(s['output_root']).exists() and not Path(s['registry']).exists(),'consumed')
    output.mkdir();base.cal.write_new(output/'study_plan.json',s);(output/'RUN_AFTER_APPROVAL.ps1').write_text(root_script(),encoding='utf8')
    for phase in ('development','confirmation'):
        plan,ms=block_spec(output/'study_plan.json',phase);folder=output/phase;(folder/'manifests').mkdir(parents=True)
        for e,m in zip(plan['entries'],ms):base.cal.write_new(folder/e['manifest'],m)
        base.cal.write_new(folder/('collection_plan.json' if phase=='development' else 'template_plan.json'),plan)
        (folder/'RUN_AFTER_APPROVAL.ps1').write_text(block_script(),encoding='utf8')
    return check(output/'study_plan.json')


def prepare_remaining(previous,output):
    previous,output=Path(previous),Path(output);study=p.read(previous)
    require(output.name=='separated_power_plan_v4' and not output.exists(),'new v4 only')
    oldplan=previous.parent/'development/collection_plan.json';old=p.read(oldplan)
    folder=Path(old['output_root'])/f"00_{old['entries'][0]['session_id']}"
    files=[oldplan,Path(study['output_root'])/'FINAL_RECEIPT.json',*filter(Path.is_file,folder.rglob('*'))]
    contract=CONTRACT.with_name('contract_v4.json')
    study.update(experiment_id='SEPARATED-POWER-FOLLOWUP-04',plan_folder=output.name,source_code=identity(),budget=p.read(contract)['budget'],
        contract=dict(path=str(contract),sha256=p.digest(contract)),
        imported_development=[study['imported_development'],dict(plan=str(oldplan),index=0,files={str(f):p.digest(f) for f in files})],
        output_root=str(output.parent/'separated_power_run_v4'),registry=str(output.parent/'separated_power_registry/SEPARATED-POWER-FOLLOWUP-04'))
    verify(study);require(not Path(study['output_root']).exists() and not Path(study['registry']).exists(),'consumed')
    output.mkdir();base.cal.write_new(output/'study_plan.json',study);(output/'RUN_AFTER_APPROVAL.ps1').write_text(root_script(),encoding='utf8')
    for phase in ('development','confirmation'):
        plan,ms=block_spec(output/'study_plan.json',phase);folder=output/phase;(folder/'manifests').mkdir(parents=True)
        for e,m in zip(plan['entries'],ms):base.cal.write_new(folder/e['manifest'],m)
        base.cal.write_new(folder/('collection_plan.json' if phase=='development' else 'template_plan.json'),plan)
        (folder/'RUN_AFTER_APPROVAL.ps1').write_text(block_script(),encoding='utf8')
    return check(output/'study_plan.json')


def main():
    q=argparse.ArgumentParser();q.add_argument('action',choices=['prepare','check','check-block','run','run-block'])
    for key in ('previous','output','plan','adb','expected-sha','serial'):q.add_argument('--'+key)
    q.add_argument('--approved',action='store_true');a=q.parse_args()
    if a.action=='prepare':r=(prepare_remaining if Path(a.output).name=='separated_power_plan_v4' else prepare)(a.previous,a.output)
    elif a.action=='check':r=check(a.plan)
    elif a.action=='check-block':r=check_block(a.plan)
    elif a.action=='run':
        s=p.read(a.plan);require(shutil.disk_usage(Path(s['output_root']).parent).free>=p.read(s['contract']['path'])['minimum_host_free_bytes'],'storage reserve')
        r=base.run(a.plan,a.adb,a.expected_sha,a.approved,adapter=sys.modules[__name__])
    else:
        from tools.d1_arrival_energy_collection_device import run
        r=run(a.plan,a.adb,a.serial or '',a.expected_sha,a.approved)
    print(json.dumps(r,indent=2))


if __name__=='__main__':main()
