"""Two single-use collection blocks with a development-only freeze between them."""
import argparse
import copy
import hashlib
import json
import time
import traceback
import uuid
from pathlib import Path
from tools import d1_ap_background_contrast as contrast
from tools import d1_ap_background_contrast_readout as readout
from tools import d1_ap_completion_model as model
from tools import d1_ap_model_completion as common
from tools import d1_ap_bundle_readout as consumption
from tools import d1_energy_host_checkpoints as checkpoints

p,require=contrast.p,contrast.old.require
ROOT=contrast.ROOT
CONTRACT=contrast.BUNDLE/'completion_study.json'
NAME='AP-LIMITED-MODEL-COMPLETION-STUDY-01'
FOLDER='ap_completion_study_plan_v1'
RUN='ap_completion_study_run_v1'


def identity():
    return contrast.identity() | {f.relative_to(ROOT).as_posix():p.digest(f) for f in (Path(__file__),Path(model.__file__),CONTRACT)}


def block_spec(study_file,phase,freeze=None):
    study_file=Path(study_file);study=p.read(study_file);folder=study_file.parent/phase
    # Legacy template locates freezes relative to the archive root, not nested blocks.
    template_output=study_file.parent.parent/('ap_completion_template_'+phase)
    plan,manifests=contrast.specification(study['source_plan']['path'],study['build_receipt']['path'],template_output)
    contract=p.read(CONTRACT);order=contract[phase+'_order'];fresh=[]
    exp=NAME+'-'+phase.upper()
    plan.update(ap_completion_study=True,study_phase=phase,study_plan_file=str(study_file),
        experiment_id=exp,source_code=identity(),approval='user_goal_execute_20261002',
        output_root=str(Path(study['output_root'])/phase),
        registry=str(Path(study['block_registry_root'])/exp),study_freeze=freeze,entries=[],
        selection='prespecified development or heldout order; fixed request transforms',
        analysis_scope='development-only fit then unchanged conditional confirmation; no accuracy PASS')
    # Use the new L35 template, not the original resident control's earlier release times.
    loaded=manifests[1]
    for i,condition in enumerate(order):
        m=copy.deepcopy(loaded);sid=str(uuid.uuid5(uuid.NAMESPACE_URL,exp+'/'+str(i)))
        role=f'{phase}_{i}_{condition}'
        m.update(experiment_id=exp,session_id=sid,phase=role,ap_bundle_role=role,background_condition=condition,
            resident_control_role='no_load_control' if condition=='C' else 'registered_load')
        if condition=='C':m['requests']=[]
        for row in m['requests']:
            row['request_id']=str(uuid.uuid5(uuid.NAMESPACE_URL,sid+'/'+str(row['ordinal'])))
            shift=30 if condition=='L65' or condition=='SPLIT_DELAY30' and row['ordinal']>=12 else 15 if condition=='L50' else 0
            row['release_offset_ns']+=shift*1_000_000_000
            require(row['offset_ms']*1_000_000<=row['release_offset_ns']<120_000_000_000,'study release boundary')
        for spec in m['models'].values():spec['identity']['session_id']=sid
        rel=f'manifests/{sid}.json';count=contrast.memory.base.control.request_count(m)
        plan['entries'].append(dict(index=i,phase=role,condition=condition,session_id=sid,scenario='burst',
            policy=contrast.memory.base.replay.POLICY,manifest=rel,manifest_sha256=hashlib.sha256(p.canonical(m)).hexdigest(),
            requests=count,warmup=8,runtime_creations=4))
        fresh.append(m)
    plan['run_script_sha256']=hashlib.sha256(block_script().encode()).hexdigest()
    return plan,fresh


def block_script():
    return contrast.script_text().replace('d1_ap_background_contrast','d1_ap_completion_study').replace(' check --plan',' check-block --plan').replace(' run --plan',' run-block --plan')


def root_script():
    return contrast.script_text().replace('d1_ap_background_contrast','d1_ap_completion_study').replace("'collection_plan.json'","'study_plan.json'")


def prepare(original,output):
    original,output=Path(original),Path(output);old=p.read(original)
    require(output.name==FOLDER and not output.exists(),'fresh dedicated study plan required')
    require(not Path(old['output_root']).exists() and not Path(old['registry']).exists(),'old contrast already consumed')
    require(p.digest(original)==p.read(CONTRACT)['existing_collection_plan_sha256'],'original plan bytes changed')
    study=dict(version='ap-completion-study-v1',experiment_id=NAME,approval='user_goal_execute_20261002',
        status='PC_READY_DEVICE_UNVERIFIED',source_code=identity(),
        original_contrast=dict(path=str(original),sha256=p.digest(original)),
        source_plan=old['source_plan'],build_receipt=dict(path=old['build_receipt'],sha256=p.digest(old['build_receipt'])),
        contract=dict(path=str(CONTRACT),sha256=p.digest(CONTRACT)),budget=p.read(CONTRACT)['budget'],
        output_root=str(output.parent/RUN),registry=str(output.parent/'ap_completion_registry'/NAME),
        block_registry_root=str(output.parent/'ap_completion_block_registry'),
        experiment_ready=False,run_script_sha256=hashlib.sha256(root_script().encode()).hexdigest())
    require(not Path(study['output_root']).exists() and not Path(study['registry']).exists(),'study occupied')
    output.mkdir();contrast.cal.write_new(output/'study_plan.json',study)
    (output/'RUN_AFTER_APPROVAL.ps1').write_text(root_script(),encoding='utf-8')
    for phase in ('development','confirmation'):
        plan,ms=block_spec(output/'study_plan.json',phase);folder=output/phase;folder.mkdir();(folder/'manifests').mkdir()
        for e,m in zip(plan['entries'],ms):contrast.cal.write_new(folder/e['manifest'],m)
        contrast.cal.write_new(folder/('collection_plan.json' if phase=='development' else 'template_plan.json'),plan)
        (folder/'RUN_AFTER_APPROVAL.ps1').write_text(block_script(),encoding='utf-8')
    return check(output/'study_plan.json')


def verify_sources(study):
    require(study['source_code']==identity() and study['budget']==p.read(CONTRACT)['budget'],'study code/budget drift')
    for key in ('original_contrast','source_plan','build_receipt','contract'):
        item=study[key];require(p.digest(item['path'])==item['sha256'],'study bound resource drift')


def check_block(file,*,allow_consumed=False):
    file=Path(file);plan=p.read(file);phase=plan['study_phase'];study=p.read(plan['study_plan_file'])
    verify_sources(study)
    expected,ms=block_spec(plan['study_plan_file'],phase,plan['study_freeze'])
    require(plan==expected and file.parent.name==phase,'block/code/phase mismatch')
    require((file.parent/'RUN_AFTER_APPROVAL.ps1').read_text(encoding='utf-8')==block_script(),'block script drift')
    if not allow_consumed:
        require(not Path(plan['output_root']).exists() and not Path(plan['registry']).exists(),'consumed block; no resume')
    if phase=='confirmation' and file.name!='template_plan.json':
        binding=plan['study_freeze'];require(binding is not None and p.digest(binding['path'])==binding['sha256'],'confirmation has no frozen model')
        freeze=p.read(binding['path'])
        require(freeze['contract_sha256']==study['contract']['sha256'] and freeze['analysis_source_code']==identity(), 'freeze contract/code drift')
        development=p.read(Path(study['output_root'])/'development/FINAL_RECEIPT.json')
        require(development['status']=='completed_descriptive_only' and development['sessions']==6,'development incomplete')
    for item in [plan[key] for key in ('frozen_model','candidate_freeze','memory_candidate')]+list(plan['source_files'].values())+list(plan['references'].values()):
        require(p.digest(item['path'])==item['sha256'],'freeze/input/reference changed')
    for e,m in zip(plan['entries'],ms):
        require(p.read(file.parent/e['manifest'])==m and p.digest(file.parent/e['manifest'])==e['manifest_sha256'],'manifest drift')
    return dict(plan_sha256=p.digest(file),budget=plan['budget'],device_commands=0)


def check(file):
    file=Path(file);study=p.read(file);verify_sources(study)
    require(file.parent.name==FOLDER and file.name=='study_plan.json','study path')
    require(not Path(study['registry']).exists() and not Path(study['output_root']).exists(),'study consumed; no resume')
    require((file.parent/'RUN_AFTER_APPROVAL.ps1').read_text(encoding='utf-8')==root_script(),'study script drift')
    for phase in ('development','confirmation'):
        check_block(file.parent/phase/('collection_plan.json' if phase=='development' else 'template_plan.json'))
    return dict(status=study['status'],plan_sha256=p.digest(file),budget=study['budget'],device_commands=0)


def load_cases(file):
    file=Path(file);plan=p.read(file);check_block(file,allow_consumed=True)
    require(p.read(Path(plan['output_root'])/'FINAL_RECEIPT.json')['status']=='completed_descriptive_only','block not completed')
    cases=[]
    for entry in plan['entries']:
        folder=Path(plan['output_root'])/f"{entry['index']:02d}_{entry['session_id']}"
        require(p.read(folder/'validated.json')['status']=='eligible_descriptive_only','partial block')
        case=readout.case_from_session(file,plan,entry);case['study_phase']=plan['study_phase'];cases.append(case)
    return cases


def evaluate(cases,selected,output):
    output=Path(output);require(not output.exists(),'fresh study readout required');output.mkdir(parents=True)
    contract=p.read(contrast.BUNDLE/'analysis_contract.json');m0=p.read(contrast.memory.CANDIDATE)['fixed_parameters']
    baseline=dict(beta=m0['ap_cooling_rate_per_s'],k=1.,g=0.,parameters=m0)
    scores=[];paths=[]
    for c in cases:
        for name,frozen in [('M0',baseline),('selected',selected)]:
            values,init=model.predict(c,frozen)
            row=readout.describe(c,values,init,contract);row.update(model=name,
                directions=model.directions(c,values,p.read(CONTRACT)['direction_windows_s']),
                prediction_generated_utc=checkpoints.utc(),initialization_input_end_s=init['input_end_s'],
                inputs='pre35 AP and actual full lane schedule; post35 AP/current excluded; offline conditional',
                original_start_ap_in_development_range=32.5<=c['common_start_ap_c']<=34.,
                short_transition_strict_supported=False)
            scores.append(row)
            for t,y,v in zip(c['inputs']['query_s'],c['observed_ap_c'],values):
                paths.append(dict(role=c['id'],condition=c['condition'],model=name,common_s=t,observed_c=y,predicted_c=v,residual_c=v-y,
                    observed_delta_c=y-init['anchor_ap_c'],predicted_delta_c=v-init['anchor_ap_c']))
    common.write_json(output/'scores.json',scores);common.write_csv(output/'paths.csv',paths)
    plot(output,paths,cases)
    return scores


def plot(output,paths,cases):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(6,2,figsize=(12,16),constrained_layout=True)
    for i,c in enumerate(cases):
        pp=[r for r in paths if r['role']==c['id']];obs=[r for r in pp if r['model']=='M0']
        axes[i,0].plot([r['common_s'] for r in obs],[r['observed_c'] for r in obs],color='black',label='Observed')
        for name in ('M0','selected'):
            rows=[r for r in pp if r['model']==name];ts=[r['common_s'] for r in rows]
            axes[i,0].plot(ts,[r['predicted_c'] for r in rows],label=name)
            axes[i,1].plot(ts,[r['residual_c'] for r in rows],label=name)
        for ax in axes[i]:
            ax.set_title(c['id']);ax.set_xlabel('Common-origin seconds');ax.grid(alpha=.2);ax.legend()
            if c.get('last_lane_s') is not None:ax.axvspan(c['first_dispatch_s'],c['last_lane_s'],alpha=.1,color='gray')
        axes[i,0].set_ylabel('AP C');axes[i,1].set_ylabel('Predicted - observed C')
    fig.suptitle(cases[0]['study_phase']+'; actual schedule conditional; no accuracy PASS')
    fig.savefig(output/'paths.png',dpi=120);fig.savefig(output/'paths.svg');plt.close(fig)


def run(file,adb,expected_sha,approved):
    require(approved and p.digest(file)==expected_sha,'approved exact study hash required');check(file)
    file=Path(file);study=p.read(file);root=Path(study['output_root']);registry=Path(study['registry'])
    registry.mkdir(parents=True,exist_ok=False);root.mkdir(exist_ok=False)
    from tools import d1_energy_host_lifecycle as lifecycle
    from tools import d1_arrival_energy_collection_device as runner
    start=time.monotonic();journal=checkpoints.Checkpoints(root/'study_checkpoints',expected_sha,uuid.uuid4().hex,lifecycle.host_identity())
    claim=journal.mark('study_claimed',budget=study['budget']);checkpoints.atomic_new(registry/'claimed.json',claim)
    (root/'frozen_study_plan.json').write_bytes(file.read_bytes());outcome={};phase='development';original_error=None
    try:
        dev=file.parent/'development/collection_plan.json';journal.mark('development_start')
        outcome['development']=runner.run(dev,adb,'',p.digest(dev),True)
        journal.mark('development_complete',outcome=outcome['development'])
        phase='development_freeze';pc_start=time.monotonic();cases=load_cases(dev)
        common.write_json(root/'development_cases.json',cases)
        params=p.read(contrast.memory.CANDIDATE)['fixed_parameters'];result=model.develop(cases,params,p.read(CONTRACT))
        common.write_json(root/'development_selection.json',result)
        evaluate(cases,result.get('selected_model') or result['m0'],root/'development_readout')
        outcome['development_selection']=dict(status=result['status'],reason=result['reason'],selected=result.get('selected_name'))
        require(time.monotonic()-pc_start<=study['budget']['pc_freeze_limit_seconds'],'PC freeze budget exceeded')
        if result['status']!='ready_to_freeze':
            outcome['status']='completed_development_unidentified_no_confirmation'
            journal.mark('scientific_stop',selection=outcome['development_selection'])
        else:
            inv=[dict(path=f.relative_to(root/'development').as_posix(),bytes=f.stat().st_size,sha256=p.digest(f))
                 for f in sorted((root/'development').rglob('*')) if f.is_file()]
            common.write_json(root/'development_inventory.json',inv)
            freeze=dict(version='ap-completion-frozen-v1',selected_name=result['selected_name'],selected_model=result['selected_model'],
                contract_sha256=study['contract']['sha256'],analysis_source_code=identity(),
                development_plan_sha256=p.digest(dev),development_inventory_sha256=p.digest(root/'development_inventory.json'),
                selection_sha256=p.digest(root/'development_selection.json'),utc=checkpoints.utc(),
                support='A24 registered CG_DC short pulses; actual schedule + pre35 AP; no general policy/strict support',
                accuracy_pass=None,experiment_ready=False)
            checkpoints.atomic_new(root/'model_freeze.json',freeze)
            binding=dict(path=str(root/'model_freeze.json'),sha256=p.digest(root/'model_freeze.json'))
            checkpoints.atomic_new(root/'freeze_receipt.json',dict(**binding,utc=checkpoints.utc()))
            plan,ms=block_spec(file,'confirmation',binding)
            confirm=file.parent/'confirmation/collection_plan.json';contrast.cal.write_new(confirm,plan);check_block(confirm)
            require(time.monotonic()-pc_start<=study['budget']['pc_freeze_limit_seconds'],'PC freeze budget exceeded')
            require(study['budget']['active_work_limit_seconds']-(time.monotonic()-start)>=plan['budget']['total_seconds'],'confirmation full reserve')
            journal.mark('model_frozen_confirmation_start',freeze_sha256=binding['sha256'],confirmation_plan_sha256=p.digest(confirm))
            phase='confirmation';outcome['confirmation']=runner.run(confirm,adb,'',p.digest(confirm),True)
            require(p.digest(binding['path'])==binding['sha256'],'freeze changed after confirmation')
            confirmed=load_cases(confirm);common.write_json(root/'confirmation_cases.json',confirmed)
            evaluate(confirmed,freeze['selected_model'],root/'confirmation_readout')
            outcome.update(status='completed_development_and_confirmation',freeze_sha256=binding['sha256'])
            journal.mark('confirmation_and_readout_complete',outcome=outcome['confirmation'])
    except BaseException as error:
        original_error=error
        outcome.update(status='stopped_no_resume',phase=phase,error=repr(error),original_stack=traceback.format_exc())
        try:journal.mark('original_failure',error=repr(error),stack=outcome['original_stack'])
        except BaseException as secondary:outcome['original_checkpoint_error']=repr(secondary)
        raise
    finally:
        outcome.update(elapsed_seconds=time.monotonic()-start,experiment_ready=False,automatic_retry=0)
        errors=[]
        for name in ('development','confirmation'):
            receipt=root/name/'FINAL_RECEIPT.json'
            if receipt.exists():
                try:outcome[name]=p.read(receipt)
                except BaseException as secondary:errors.append(dict(stage=name+'_receipt_read',error=repr(secondary)))
        outcome['secondary_recording_errors']=errors
        try:checkpoints.atomic_new(root/'FINAL_RECEIPT.json',outcome)
        except BaseException as secondary:errors.append(dict(stage='final_receipt',error=repr(secondary)))
        try:
            name='recording_failed.json' if errors else 'stopped.json' if outcome['status']=='stopped_no_resume' else 'completed.json'
            checkpoints.atomic_new(registry/name,outcome)
        except BaseException as secondary:errors.append(dict(stage='registry_receipt',error=repr(secondary)))
        try:journal.mark('study_terminal',outcome=outcome,recording_errors=errors)
        except BaseException as secondary:errors.append(dict(stage='terminal_checkpoint',error=repr(secondary)))
        if errors:
            try:checkpoints.atomic_new(root/'TERMINAL_RECORDING_ERROR.json',dict(outcome=outcome,errors=errors))
            except BaseException:pass  # filesystem-wide failure cannot be guaranteed recoverable
            if original_error is None:raise RuntimeError('terminal receipt persistence failed: '+repr(errors))
    return outcome


def main():
    q=argparse.ArgumentParser(description=__doc__);sub=q.add_subparsers(dest='action',required=True)
    a=sub.add_parser('prepare');a.add_argument('--original',required=True);a.add_argument('--output',required=True)
    for name in ('check','check-block'):
        a=sub.add_parser(name);a.add_argument('--plan',required=True)
    for name in ('run','run-block'):
        a=sub.add_parser(name)
        for k in ('plan','adb','expected-sha'):a.add_argument('--'+k,required=True)
        a.add_argument('--serial',default='');a.add_argument('--approved',action='store_true')
    a=q.parse_args()
    if a.action=='prepare':result=prepare(a.original,a.output)
    elif a.action=='check':result=check(a.plan)
    elif a.action=='check-block':result=check_block(a.plan)
    elif a.action=='run':result=run(a.plan,a.adb,a.expected_sha,a.approved)
    else:
        require(p.read(a.plan)['study_phase']=='development' or p.read(a.plan)['study_freeze'] is not None,'unbound confirmation forbidden')
        from tools.d1_arrival_energy_collection_device import run as block_run
        result=block_run(a.plan,a.adb,a.serial,a.expected_sha,a.approved)
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
