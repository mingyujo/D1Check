"""Single-use development3 -> immutable model -> independent confirmation6."""
import argparse
import copy
import hashlib
import json
import time
import traceback
import uuid
from pathlib import Path
from tools import d1_arrival_plan as p
from tools import d1_arrival_energy_collection as old
from tools import d1_arrival_timing_calibration as cal
from tools import d1_arrival_recorded_replay as replay
from tools import d1_apk_identity as apk
from tools import d1_ap_completion_study as previous
from tools import d1_online_policy_model as model
from tools import d1_energy_host_checkpoints as checkpoints

ROOT=replay.ROOT
CONTRACT=ROOT/'docs/results/online_policy_study_01/analysis_contract.json'
NAME='ONLINE-POLICY-MODEL-STUDY-04'
FOLDER='online_policy_study_plan_v4'
RUN='online_policy_study_run_v4'
require=old.require


def identity():
    return old.identity() | {f.relative_to(ROOT).as_posix():p.digest(f) for f in (Path(__file__),Path(model.__file__),CONTRACT,model.PARAMETERS,
        ROOT/'tools/d1_online_policy_readout.py',ROOT/'tools/d1_simulator.py',ROOT/'tools/d1_arrival_explore.py',ROOT/'tools/d1_ap_completion_model.py',ROOT/'tools/d1_ap_preparation_memory.py',ROOT/'tools/d1_arrival_policy_screen.py',ROOT/'tools/d1_arrival_explore_batch.py')}


def remaining_budget():
    b=copy.deepcopy(p.read(CONTRACT)['budget'])
    b.update(sessions=7,development_sessions=1,requests=672,warmup=56,explicit_inference=728,
        runtime_creations=28,staging=7,staging_files=49,fixed_observation_seconds=1470,
        intersession_idle_seconds=450,development_block_seconds=1300,total_seconds=7150,adb_commands=22800)
    return b


def imported_cases(study):
    imported=study.get('imported_development')
    if imported is None:return []
    for file,digest in imported['files'].items():require(p.digest(file)==digest,'imported development evidence changed')
    file=Path(imported['plan']);plan=p.read(file)
    receipt=p.read(imported['receipt'])
    require(receipt['status']=='stopped_no_resume','past failure must remain stopped')
    cases=[model.load_case(file,plan,plan['entries'][i]) for i in imported['indices']]
    require([c['policy'] for c in cases]==list(model.POLICIES[:2]),'only completed first two developments')
    return cases


def root_script():return previous.root_script().replace('d1_ap_completion_study','d1_online_policy_study')
def block_script():return previous.block_script().replace('d1_ap_completion_study','d1_online_policy_study')


def block_spec(file,phase,freeze=None):
    file=Path(file);study=p.read(file);source=p.read(study['source_plan']['path']);contract=p.read(CONTRACT)
    plan=copy.deepcopy(source)
    for k in list(plan):
        if k.startswith('ap_') or k.startswith('resident_') or k.startswith('recorded_') or k in ('single_arrival_confirmation','bundle_edition','candidate_freeze','memory_candidate'):plan.pop(k)
    order=study.get('remaining_development_order',contract['development_order']) if phase=='development' else contract['confirmation_order'];n=len(order);build=p.read(study['build_receipt']['path'])
    budget=dict(replay.BUDGET,sessions=n,requests=n*96,warmup=n*8,explicit_inference=n*104,runtime_creations=n*4,
        staging=n,staging_files=n*7,total_seconds=600+n*700+(n-1)*90,adb_commands=n*3200+200,
        per_session_adb_commands=3200,adb_recovery_cleanup_reserve=100,installed_preflight_seconds=600,intersession_cooling_seconds=90,
        apk_transfers=int(phase=='development'),installs=int(phase=='development'))
    exp=NAME+'-'+phase.upper()
    plan.update(experiment_id=exp,online_policy_study=True,study_phase=phase,study_plan_file=str(file),study_freeze=freeze,
        online_configuration_owner_v1=True,installed_only=phase=='confirmation',status='PC_READY_DEVICE_UNVERIFIED',approval='user_autonomous_measurement_20261002',
        source_code=identity(),budget=budget,output_root=str(Path(study['output_root'])/phase),registry=str(Path(study['block_registry_root'])/exp),
        apk_path=build['apk_path'],apk_sha256=build['apk_sha256'],apk_preflight=dict(source['apk_preflight'],candidate=study['candidate']),
        analysis_contract=study['contract'],build_receipt=study['build_receipt']['path'],build_receipt_sha256=study['build_receipt']['sha256'],
        input_bundle=study['contract'],entries=[],selection='online causal policy, independent fixed arrivals; no replay dispatch',
        measurement_protocol_change='opt-in 96 request causal policy; same sampler/warmup/thermal gates; new Activity handles registered configuration changes without owner recreation; original destroy cancellation retained',analysis_scope='development fit then independent policy-context forecasting, no automatic accuracy PASS')
    sourcefile=Path(study['source_plan']['path']);template=p.read(sourcefile.parent/source['entries'][0]['manifest']);ms=[]
    for i,policy in enumerate(order):
        m=copy.deepcopy(template)
        for k in list(m):
            if k.startswith(('replay_','source_','resident_control_','ap_bundle_','ap_idle_','ap_schedule_','candidate_procedure_')):m.pop(k)
        sid=str(uuid.uuid5(uuid.NAMESPACE_URL,exp+'/'+str(i)))
        rows=model.requests(phase,sid)
        for r in rows:r['request_id']=str(uuid.uuid5(uuid.NAMESPACE_URL,sid+'/'+str(r['ordinal'])))
        m.update(experiment_id=exp,session_id=sid,phase=f'{phase}_{i}_{policy}',scenario='sustained_mixed',policy=policy,
            policy_study_version='online-policy-model-study-v1',policy_study_role=phase,requests=rows,start_ap_gate='numeric-ap-observe-v2',apk_sha256=build['apk_sha256'])
        for spec in m['models'].values():spec['identity']['session_id']=sid;spec['target']['apk_sha256']=build['apk_sha256']
        rel=f'manifests/{sid}.json';plan['entries'].append(dict(index=i,phase=m['phase'],condition=policy,scenario=m['scenario'],policy=policy,session_id=sid,manifest=rel,
            manifest_sha256=hashlib.sha256(p.canonical(m)).hexdigest(),requests=96,warmup=8,runtime_creations=4));ms.append(m)
    plan['run_script_sha256']=hashlib.sha256(block_script().encode()).hexdigest()
    return plan,ms


def verify(study):
    require(len(imported_cases(study))==2,'two imported eligible developments required')
    require(study['source_code']==identity() and study['budget']==remaining_budget(),'study code/budget changed')
    for key in ('source_plan','build_receipt','contract','old_ap_model'):
        x=study[key];require(p.digest(x['path'])==x['sha256'],'bound resource changed '+key)
    contract=p.read(CONTRACT);b=study['budget']
    require(contract['development_order']==list(model.POLICIES) and contract['confirmation_order']==list(model.POLICIES)+list(reversed(model.POLICIES)),'policy order')
    require(b['total_seconds']==1300+5250+600 and b['adb_commands']==7*3200+400 and b['explicit_inference']==7*(96+8),'budget arithmetic')
    previous_model=p.read(study['old_ap_model']['path'])['selected_model']
    require(previous_model['parameters']==p.read(model.PARAMETERS)['fixed_parameters'] and previous_model['beta']==contract['ap']['beta'] and previous_model['k']==1 and previous_model['g']==0,'fixed M0 initialization/coefficients')
    build=p.read(study['build_receipt']['path'])
    require(old.apk_sources(build['source_code'])==old.apk_sources(cal.code_identity()),'APK source mismatch')
    require(p.digest(build['apk_path'])==build['apk_sha256'],'APK hash')


def check_block(file,allow_consumed=False):
    file=Path(file);plan=p.read(file);study=p.read(plan['study_plan_file']);verify(study)
    expected,ms=block_spec(plan['study_plan_file'],plan['study_phase'],plan['study_freeze'])
    require(plan==expected,'block differs')
    require((file.parent/'RUN_AFTER_APPROVAL.ps1').read_text(encoding='utf8')==block_script(),'block script')
    if not allow_consumed:require(not Path(plan['output_root']).exists() and not Path(plan['registry']).exists(),'consumed; no resume')
    if plan['study_phase']=='confirmation' and file.name!='template_plan.json':
        x=plan['study_freeze'];require(x is not None and p.digest(x['path'])==x['sha256'],'confirmation freeze absent')
        freeze=p.read(x['path']);require(freeze['source_code']==identity() and freeze['contract_sha256']==study['contract']['sha256'],'freeze changed')
        dev=p.read(Path(study['output_root'])/'development/FINAL_RECEIPT.json')
        require(dev['status']=='completed_descriptive_only' and dev['sessions']==1 and len(imported_cases(study))==2,'development not complete')
    for x in [plan['frozen_model'],*plan['source_files'].values(),*plan['references'].values()]:require(p.digest(x['path'])==x['sha256'],'model/input/reference drift')
    for e,m in zip(plan['entries'],ms):require(p.read(file.parent/e['manifest'])==m and p.digest(file.parent/e['manifest'])==e['manifest_sha256'],'manifest drift')
    return dict(device_commands=0,budget=plan['budget'],sha256=p.digest(file))


def check(file):
    file=Path(file);study=p.read(file);verify(study)
    require(file.parent.name==FOLDER and not Path(study['registry']).exists() and not Path(study['output_root']).exists(),'occupied study')
    require((file.parent/'RUN_AFTER_APPROVAL.ps1').read_text(encoding='utf8')==root_script(),'root script drift')
    source=p.read(study['source_plan']['path']);build=p.read(study['build_receipt']['path'])
    require(apk.inspect(build['apk_path'],source['apk_preflight']['toolchain'])==study['candidate'],'candidate identity')
    for phase in ('development','confirmation'):check_block(file.parent/phase/('collection_plan.json' if phase=='development' else 'template_plan.json'))
    return dict(status='PC_READY_DEVICE_UNVERIFIED',sha256=p.digest(file),budget=study['budget'],device_commands=0)


def prepare(source,build,apfreeze,output):
    source,build,apfreeze,output=map(Path,(source,build,apfreeze,output))
    require(output.name==FOLDER and not output.exists(),'fresh study path')
    src,bld=p.read(source),p.read(build)
    previous_receipt=output.parent/'online_policy_study_run_v3/FINAL_RECEIPT.json'
    previous_plan=output.parent/'online_policy_study_plan_v3/development/collection_plan.json'
    past=p.read(previous_plan);files={str(previous_plan):p.digest(previous_plan),str(previous_receipt):p.digest(previous_receipt)}
    for entry in past['entries'][:2]:
        manifest=previous_plan.parent/entry['manifest'];files[str(manifest)]=p.digest(manifest)
        folder=Path(past['output_root'])/f"{entry['index']:02d}_{entry['session_id']}"
        for item in folder.rglob('*'):
            if item.is_file():files[str(item)]=p.digest(item)
    imported=dict(plan=str(previous_plan),receipt=str(previous_receipt),indices=[0,1],files=files,
        reason='first two eligible developments preserved; third stopped during cooling on configuration-driven destroy',
        protocol_transfer='first two old Activity; remaining new configuration-handling component; inference/sampler/policy unchanged, no cost correction')
    require(old.apk_sources(bld['source_code'])==old.apk_sources(cal.code_identity()),'APK/source mismatch')
    candidate=apk.inspect(bld['apk_path'],src['apk_preflight']['toolchain'])
    require(candidate['signer_sha256']==src['apk_preflight']['candidate']['signer_sha256'],'project signer')
    study=dict(version='online-policy-model-study-v1',experiment_id=NAME,source_code=identity(),budget=remaining_budget(),
        source_plan=dict(path=str(source.resolve()),sha256=p.digest(source)),build_receipt=dict(path=str(build.resolve()),sha256=p.digest(build)),
        contract=dict(path=str(CONTRACT),sha256=p.digest(CONTRACT)),old_ap_model=dict(path=str(apfreeze.resolve()),sha256=p.digest(apfreeze)),candidate=candidate,
        output_root=str(output.parent/RUN),registry=str(output.parent/'online_policy_registry'/NAME),block_registry_root=str(output.parent/'online_policy_block_registry'),
        imported_development=imported,remaining_development_order=[model.POLICIES[2]],task_level_prior_stops=2,
        experiment_ready=False,approval='user_autonomous_measurement_and_failure_recovery_20261002')
    require(not Path(study['output_root']).exists() and not Path(study['registry']).exists(),'occupied')
    output.mkdir();cal.write_new(output/'study_plan.json',study);(output/'RUN_AFTER_APPROVAL.ps1').write_text(root_script(),encoding='utf8')
    for phase in ('development','confirmation'):
        plan,ms=block_spec(output/'study_plan.json',phase);folder=output/phase;(folder/'manifests').mkdir(parents=True)
        for e,m in zip(plan['entries'],ms):cal.write_new(folder/e['manifest'],m)
        cal.write_new(folder/('collection_plan.json' if phase=='development' else 'template_plan.json'),plan)
        (folder/'RUN_AFTER_APPROVAL.ps1').write_text(block_script(),encoding='utf8')
    return check(output/'study_plan.json')


def load_cases(file):
    file=Path(file);plan=p.read(file);check_block(file,allow_consumed=True)
    receipt=p.read(Path(plan['output_root'])/'FINAL_RECEIPT.json')
    require(receipt['status']=='completed_descriptive_only' and receipt['sessions']==len(plan['entries']),'incomplete block')
    return [model.load_case(file,plan,e) for e in plan['entries']]


def run(file,adb,expected_sha,approved):
    require(approved and p.digest(file)==expected_sha,'approved exact hash');check(file)
    from tools import d1_arrival_energy_collection_device as runner
    from tools import d1_energy_host_lifecycle as lifecycle
    file=Path(file);study=p.read(file);root=Path(study['output_root']);registry=Path(study['registry'])
    registry.mkdir(parents=True,exist_ok=False);root.mkdir(exist_ok=False)
    start=time.monotonic();journal=checkpoints.Checkpoints(root/'study_checkpoints',expected_sha,uuid.uuid4().hex,lifecycle.host_identity())
    checkpoints.atomic_new(registry/'claimed.json',journal.mark('claimed',budget=study['budget']))
    (root/'frozen_study_plan.json').write_bytes(file.read_bytes());outcome={};phase='development';original=None
    try:
        dev=file.parent/'development/collection_plan.json';journal.mark('development_start')
        outcome['development']=runner.run(dev,adb,'',p.digest(dev),True)
        phase='model_freeze';freeze_start=time.monotonic();cases=imported_cases(study)+load_cases(dev)
        cal.write_new(root/'development_cases.json',cases);fitted=model.develop(cases)
        original_plan=p.read(dev);fitted['original_whole_device_power_w']=p.read(original_plan['frozen_model']['path'])['whole_device_power_w']
        freeze=dict(model=fitted,source_code=identity(),contract_sha256=study['contract']['sha256'],utc=checkpoints.utc(),development_cases_sha256=p.digest(root/'development_cases.json'))
        checkpoints.atomic_new(root/'model_freeze.json',freeze);binding=dict(path=str(root/'model_freeze.json'),sha256=p.digest(root/'model_freeze.json'))
        cal.write_new(root/'development_evaluation.json',model.evaluate(cases,fitted))
        require(time.monotonic()-freeze_start<=study['budget']['pc_freeze_seconds'],'freeze time exceeded')
        plan,ms=block_spec(file,'confirmation',binding);confirm=file.parent/'confirmation/collection_plan.json';cal.write_new(confirm,plan);check_block(confirm)
        require(study['budget']['total_seconds']-(time.monotonic()-start)>=plan['budget']['total_seconds'],'confirmation full reserve')
        journal.mark('frozen_confirmation_start',freeze_sha256=binding['sha256']);phase='confirmation'
        outcome['confirmation']=runner.run(confirm,adb,'',p.digest(confirm),True)
        require(p.digest(binding['path'])==binding['sha256'],'confirmation changed model')
        confirmed=load_cases(confirm);cal.write_new(root/'confirmation_cases.json',confirmed)
        cal.write_new(root/'confirmation_evaluation.json',model.evaluate(confirmed,fitted))
        outcome.update(status='completed_development_and_confirmation',freeze_sha256=binding['sha256'])
    except BaseException as error:
        original=error;outcome.update(status='stopped_no_resume',phase=phase,error=repr(error),original_stack=traceback.format_exc())
        try:journal.mark('original_failure',error=repr(error),stack=outcome['original_stack'])
        except BaseException as secondary:outcome['checkpoint_error']=repr(secondary)
        raise
    finally:
        outcome.update(elapsed_seconds=time.monotonic()-start,experiment_ready=False,automatic_retry=0)
        errors=[]
        for name in ('development','confirmation'):
            r=root/name/'FINAL_RECEIPT.json'
            if r.exists():
                try:outcome[name]=p.read(r)
                except BaseException as e:errors.append(dict(stage=name,error=repr(e)))
        outcome['secondary_recording_errors']=errors
        for path in (root/'FINAL_RECEIPT.json',registry/('stopped.json' if outcome['status']=='stopped_no_resume' else 'completed.json')):
            try:checkpoints.atomic_new(path,outcome)
            except BaseException as e:errors.append(dict(stage=str(path),error=repr(e)))
        try:journal.mark('terminal',outcome=outcome)
        except BaseException as e:errors.append(dict(stage='terminal',error=repr(e)))
        if errors:
            try:checkpoints.atomic_new(root/'TERMINAL_RECORDING_ERROR.json',dict(outcome=outcome,errors=errors))
            except BaseException:pass
            if original is None:raise RuntimeError('receipt recording failed '+repr(errors))
    return outcome


def main():
    q=argparse.ArgumentParser();sub=q.add_subparsers(dest='action',required=True)
    a=sub.add_parser('prepare')
    for x in ('source','build','apfreeze','output'):a.add_argument('--'+x,required=True)
    for name in ('check','check-block'):
        a=sub.add_parser(name);a.add_argument('--plan',required=True)
    for name in ('run','run-block'):
        a=sub.add_parser(name)
        for x in ('plan','adb','expected-sha'):a.add_argument('--'+x,required=True)
        a.add_argument('--serial',default='');a.add_argument('--approved',action='store_true')
    a=q.parse_args()
    if a.action=='prepare':r=prepare(a.source,a.build,a.apfreeze,a.output)
    elif a.action=='check':r=check(a.plan)
    elif a.action=='check-block':r=check_block(a.plan)
    elif a.action=='run':r=run(a.plan,a.adb,a.expected_sha,a.approved)
    else:
        from tools.d1_arrival_energy_collection_device import run as block_run
        r=block_run(a.plan,a.adb,a.serial,a.expected_sha,a.approved)
    print(json.dumps(r,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
