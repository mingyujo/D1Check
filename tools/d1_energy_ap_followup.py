"""Separate, unapproved two-condition confirmation plan for a COLLECT-05 freeze.

No device calls in prepare/check. Run is single-use and delegates to the original
state session, gate, recovery, and evaluation paths without refitting coefficients.
"""
import argparse
import copy
import json
import uuid
from pathlib import Path

from tools import d1_arrival_plan as p
from tools import d1_arrival_timing_calibration as cal
from tools import d1_energy_state_collection as state
from tools import d1_energy_collection as old
from tools import d1_energy_operational as operational
from tools.d1_energy_thermal import require

EXPERIMENT = 'ENERGY-AP-STATE-CONFIRM-06'
PAIRS = ('CG_DC', 'CC_DG')
PLAN_FOLDER = 'energy_ap_state_confirm_plan_v1'
RUN_FOLDER = 'energy_ap_state_confirm_run_v1'
BUDGET = dict(state.BUDGET,
    sessions=2,development=0,confirmation=2,work_requests=3360,
    eligibility_requests=8,diagnostic_requests=3368,warmup=16,
    explicit_inference=3384,runtime_creations=8,staging=2,staged_files=14,
    fixed_observation_seconds=2040,freeze_seconds=0,total_seconds=4500,
    adb_command_slots=21000,pre_cleanup_command_slots=20900)


def identity():
    return state.identity() | {'tools/d1_energy_ap_followup.py':p.digest(__file__)}


def budget_check(b=BUDGET):
    require(b==BUDGET and b['development']==0 and b['confirmation']==len(PAIRS),'followup budget')
    require(b['work_requests']==len(PAIRS)*state.WORK_CAP and
            b['diagnostic_requests']==b['work_requests']+b['eligibility_requests'] and
            b['explicit_inference']==b['diagnostic_requests']+b['warmup'],'call caps')
    require(b['runtime_creations']==4*len(PAIRS) and b['staging']==len(PAIRS) and
            b['staged_files']==7*len(PAIRS),'runtime/staging caps')
    require(b['fixed_observation_seconds']==len(PAIRS)*(120+120+600+180) and
            b['total_seconds']==b['installed_preflight_seconds']+len(PAIRS)*b['session_seconds'],
            'time reservation')
    require(b['apk_transfers']==b['installs']==b['retry']==b['replacement']==b['additional']==0 and
            b['installed_host_pulls']==1,'installed-only single use')
    h=b['host_poll_seconds']
    poll_upper=(int(h/.25)+1)+3*(int(h/2)+1)+(int(h/10)+1)+int((int(h/2)+1)/5)+18
    normal_upper=21+len(PAIRS)*(poll_upper+57)
    require(normal_upper==20701 and normal_upper<b['pre_cleanup_command_slots'] and
            b['adb_command_slots']-b['pre_cleanup_command_slots']>=100,'ADB cap/reserve')


def prior(root):
    root=Path(root)
    plan_file=root/'energy_ap_state_plan_v5/collection_plan.json'
    run=root/'energy_ap_state_run_v5'
    plan=p.read(plan_file);receipt=p.read(run/'FINAL_RECEIPT.json')
    freeze=p.read(run/'development_freeze.json');freeze_receipt=p.read(run/'freeze_receipt.json')
    require(plan['experiment_id']==state.EXPERIMENT and receipt['status']=='stopped_no_resume' and
            receipt['completed_sessions']==4 and receipt['session_attempts']==5,
            'COLLECT-05 lineage/consumption')
    require(freeze_receipt['sha256']==p.digest(run/'development_freeze.json') and
            freeze['analysis_code_sha256']==p.digest(state.__file__) and
            freeze['input_conversion']==plan['analysis']['current_unit'] and
            freeze['plan_sha256']==p.digest(plan_file),'frozen analysis identity')
    require([p.read(next(run.glob(f'{i:02d}_*/validated.json')))['condition'] for i in range(4)]==
            ['CC_DG','CG_DC','DC_DG','DC_DG'],'completed dev/confirmation identity')
    return plan_file,plan,run,freeze_receipt['sha256']


def prepare(source_root, output):
    source_root,output=Path(source_root),Path(output)
    require(not output.exists() and output.name==PLAN_FOLDER,'write-once followup plan path')
    prior_file,old_plan,run,freeze_sha=prior(source_root)
    budget_check()
    output.mkdir(parents=True)
    (output/'manifests').mkdir()
    plan=copy.deepcopy(old_plan)
    plan.update(experiment_id=EXPERIMENT,status='PC_READY_DEVICE_UNVERIFIED',
        approval='not_approved',state_model_followup=True,source_code=identity(),
        plan_file=str((output/'collection_plan.json').resolve()),
        output_root=str(source_root/RUN_FOLDER),
        registry=str(source_root/'energy_collection_registry'/EXPERIMENT),
        budget=copy.deepcopy(BUDGET),entries=[],
        prior_plan=dict(path=str(prior_file.resolve()),sha256=p.digest(prior_file)),
        prior_receipt=dict(path=str((run/'FINAL_RECEIPT.json').resolve()),sha256=p.digest(run/'FINAL_RECEIPT.json')),
        prior_freeze=dict(path=str((run/'development_freeze.json').resolve()),sha256=freeze_sha),
        prior_completed_confirmation=dict(path=str(next(run.glob('03_*/validated.json')).resolve()),
                                          sha256=p.digest(next(run.glob('03_*/validated.json')))))
    for index,pair in enumerate(PAIRS):
        origin=old_plan['entries'][4+index]
        manifest=copy.deepcopy(p.read(prior_file.parent/origin['manifest']))
        sid=str(uuid.uuid5(uuid.NAMESPACE_URL,f'{EXPERIMENT}/confirmation/{pair}'))
        manifest.update(experiment_id=EXPERIMENT,session_id=sid)
        for spec in manifest['models'].values():
            spec['identity']['session_id']=sid
        file=output/'manifests'/f'{sid}.json'
        cal.write_new(file,manifest)
        plan['entries'].append(dict(index=index,original_index=4+index,
            phase='confirmation',pair=pair,mode='calibration',session_id=sid,
            manifest='manifests/'+file.name,manifest_sha256=p.digest(file)))
    file=output/'collection_plan.json'
    cal.write_new(file,plan)
    script=state.render_run_script(p.digest(file)).replace('tools.d1_energy_state_collection','tools.d1_energy_ap_followup')
    (output/'RUN_AFTER_APPROVAL.ps1').write_text(script,encoding='utf-8-sig')
    return check(file)


def check(file):
    from tools import d1_apk_identity as apk
    file=Path(file);plan=p.read(file);budget_check(plan['budget'])
    require(plan['protocol']==state.PROTOCOL and plan['experiment_id']==EXPERIMENT and
            plan['status']=='PC_READY_DEVICE_UNVERIFIED' and plan['approval']=='not_approved' and
            plan['state_model_calibration'] and plan['state_model_followup'] and
            plan['experiment_ready'] is False,'followup identity')
    require(Path(plan['plan_file'])==file.resolve() and
            Path(plan['output_root'])==file.parent.parent/RUN_FOLDER and
            Path(plan['registry'])==file.parent.parent/'energy_collection_registry'/EXPERIMENT,
            'isolated output/registry')
    prior_file,old_plan,run,freeze_sha=prior(file.parent.parent)
    require(plan['prior_plan']==dict(path=str(prior_file.resolve()),sha256=p.digest(prior_file)) and
            plan['prior_receipt']['sha256']==p.digest(run/'FINAL_RECEIPT.json') and
            plan['prior_freeze']==dict(path=str((run/'development_freeze.json').resolve()),sha256=freeze_sha) and
            plan['prior_completed_confirmation']['sha256']==p.digest(next(run.glob('03_*/validated.json'))),
            'prior frozen evidence changed')
    require(plan['source_code']==identity() and plan['apk_sha256']==old_plan['apk_sha256'] and
            plan['analysis']==old_plan['analysis'] and plan['acceptance']==old_plan['acceptance'] and
            plan['temperature_preparation']==operational.PREPARATION and
            plan['screen_observation']==old.OBSERVATION,'code/measurement contract changed')
    require(p.digest(plan['apk_path'])==plan['apk_sha256'] and
            apk.inspect(plan['apk_path'],plan['apk_preflight']['toolchain'])==plan['apk_preflight']['candidate'] and
            plan['apk_preflight']['candidate']==old_plan['apk_preflight']['candidate'],
            'APK/signature identity')
    require(p.digest(plan['installed_receipt']['path'])==plan['installed_receipt']['sha256'] and
            plan['installed_receipt']==old_plan['installed_receipt'],'prior installed receipt')
    for entry in list(plan['source_files'].values())+list(plan['references'].values()):
        require(p.digest(entry['path'])==entry['sha256'],'input/reference changed')
    require(len(plan['entries'])==2 and [e['pair'] for e in plan['entries']]==list(PAIRS),'subset/order')
    for index,entry in enumerate(plan['entries']):
        prior_manifest=p.read(prior_file.parent/old_plan['entries'][4+index]['manifest'])
        manifest_path=file.parent/entry['manifest'];manifest=p.read(manifest_path)
        expected=copy.deepcopy(prior_manifest)
        expected.update(experiment_id=EXPERIMENT,session_id=entry['session_id'])
        for spec in expected['models'].values():spec['identity']['session_id']=entry['session_id']
        require(entry['index']==index and entry['original_index']==index+4 and
                entry['phase']=='confirmation' and entry['pair']==PAIRS[index] and
                manifest==expected and p.digest(manifest_path)==entry['manifest_sha256'],
                'manifest identical except new identity')
    require(not Path(plan['output_root']).exists() and not Path(plan['registry']).exists(),
            'consumed plan; no run/resume')
    return dict(status=plan['status'],approval=plan['approval'],plan_sha256=p.digest(file),
                budget=BUDGET,device_commands=0)


def main():
    parser=argparse.ArgumentParser();sub=parser.add_subparsers(dest='action',required=True)
    q=sub.add_parser('prepare');q.add_argument('--source-root',required=True);q.add_argument('--output',required=True)
    q=sub.add_parser('check');q.add_argument('--plan',required=True)
    q=sub.add_parser('run')
    for field in ('plan','adb','expected-sha'):q.add_argument('--'+field,required=True)
    q.add_argument('--serial');q.add_argument('--approved',action='store_true')
    args=parser.parse_args()
    if args.action=='prepare':result=prepare(args.source_root,args.output)
    elif args.action=='check':result=check(args.plan)
    else:
        from tools.d1_energy_collection_device import run
        result=run(args.plan,args.adb,args.serial,args.expected_sha,args.approved)
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
