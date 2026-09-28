"""Single-use short-transition protocol transfer, never a policy or model fit.

Prepare/Check run on PC only. Run delegates to the existing observed device runner.
The COLLECT-05 development freeze is copied byte-for-byte before this one session.
"""
from __future__ import annotations

import argparse
import copy
import json
import uuid
from pathlib import Path

from tools import d1_arrival_plan as p
from tools import d1_arrival_timing_calibration as cal
from tools import d1_apk_identity as apk
from tools import d1_energy_state_collection as state
from tools import d1_energy_ap_autonomous_diag as autonomous
from tools.d1_energy_thermal import require

EXPERIMENT = 'ENERGY-AP-SHORT-TRANSITION-DIAG-01'
PLAN_FOLDER = 'energy_ap_short_transition_plan_v1'
RUN_FOLDER = 'energy_ap_short_transition_run_v1'
FREEZE_SHA = '35ed6987b1fc09789284018f8502107eaf4e3125373651a01e3a08d427034c54'
SHORT_BLOCKS = tuple((f'cycle{i}_{name}', lanes, seconds)
                     for i in range(6) for name, lanes, seconds in (
                         ('pair', (0, 1), 20), ('idle_after_pair', (), 10),
                         ('solo_b', (1,), 15), ('idle_after_b', (), 10),
                         ('solo_a', (0,), 15), ('idle_after_a', (), 10)))
BUDGET = dict(autonomous.BUDGET)


def identity():
    return state.identity() | {'tools/d1_energy_ap_short_transition.py': p.digest(__file__)}


def budget_check(b=BUDGET):
    autonomous.budget_check(b)
    require(len(SHORT_BLOCKS) == 36 and len({x[0] for x in SHORT_BLOCKS}) == 36 and
            sum(s for _,_,s in SHORT_BLOCKS) == 480 and
            sum(len(l)*s*4 for _,l,s in SHORT_BLOCKS) == b['work_requests'], 'transition/call cap')
    require(b['sessions'] == 1 and b['retry'] == b['replacement'] == b['additional'] == 0,
            'one session, no rerun')


def expected_manifest(source, apk_sha):
    entry = next(e for e in source['entries'] if e['pair'] == 'CC_DG')
    m = copy.deepcopy(p.read(Path(source['plan_file']).parent / entry['manifest']))
    sid = str(uuid.uuid5(uuid.NAMESPACE_URL, EXPERIMENT + '/CC_DG/short-transition'))
    m.update(experiment_id=EXPERIMENT, session_id=sid, apk_sha256=apk_sha,
             session_control=autonomous.CONTROL, autonomous_diagnostic_only=True,
             short_transition_diagnostic_only=True, calibration_version='short-transition-diagnostic-v1',
             blocks=[dict(id=n, lane_indices=list(l), seconds=s) for n,l,s in SHORT_BLOCKS],
             device_screen_contract={k:source['screen_contract'][k] for k in
                                     ('screen_brightness','screen_brightness_mode','screen_off_timeout')})
    for spec in m['models'].values():
        spec['identity']['session_id'] = sid
        spec['target']['apk_sha256'] = apk_sha
    return m


def prepare(source_file, build_file, frozen_file, output):
    source_file, build_file, frozen_file, output = map(Path,(source_file,build_file,frozen_file,output))
    require(not output.exists() and output.name == PLAN_FOLDER, 'new plan path only')
    source, build = p.read(source_file), p.read(build_file)
    budget_check()
    require(source['state_model_followup'] and source['experiment_id'] == 'ENERGY-AP-STATE-CONFIRM-06' and
            {e['pair'] for e in source['entries']} == {'CC_DG','CG_DC'}, 'confirmation source')
    require(p.digest(frozen_file) == FREEZE_SHA and
            build['status'] == 'built_not_device_verified' and
            cal.apk_sources(build['source_code']) == cal.apk_sources(identity()) and
            p.digest(build['apk_path']) == build['apk_sha256'], 'frozen/build/source identity')
    candidate = apk.inspect(build['apk_path'], source['apk_preflight']['toolchain'])
    require(candidate['signer_sha256'] == source['apk_preflight']['candidate']['signer_sha256'],
            'project signer')
    output.mkdir(); (output/'manifests').mkdir()
    plan = copy.deepcopy(source)
    for key in ('prior_plan','prior_receipt','prior_completed_confirmation','installed_receipt'):
        plan.pop(key,None)
    plan.update(experiment_id=EXPERIMENT,status='PC_READY_DEVICE_UNVERIFIED_NOT_APPROVED',
        approval='not_approved', diagnostic_only=True, autonomous_diagnostic_only=True,
        short_transition_diagnostic_only=True, state_model_followup=False,
        budget=copy.deepcopy(BUDGET),source_code=identity(),plan_file=str((output/'collection_plan.json').resolve()),
        output_root=str(output.parent/RUN_FOLDER),registry=str(output.parent/'energy_collection_registry'/EXPERIMENT),
        build_receipt=str(build_file.resolve()),build_receipt_sha256=p.digest(build_file),
        apk_path=build['apk_path'],apk_sha256=build['apk_sha256'],
        apk_preflight=dict(source['apk_preflight'],candidate=candidate),
        source_plan=dict(path=str(source_file.resolve()),sha256=p.digest(source_file)),
        prior_freeze=dict(path=str(frozen_file.resolve()),sha256=FREEZE_SHA),
        analysis=dict(scope='one CC_DG short-transition schedule-conditional protocol transfer; not arrival/policy validation',
            frozen_coefficients='COLLECT-05 development only, byte unchanged',
            timing='actual block boundaries given after session',
            current_unit='A24 raw mA conditional; absolute J not certified'),
        acceptance=dict(source['acceptance'],joint_lane_occupancy_min_seconds=10),entries=[])
    m = expected_manifest(source,build['apk_sha256'])
    mf=output/'manifests'/(m['session_id']+'.json');cal.write_new(mf,m)
    plan['entries']=[dict(index=0,phase='confirmation',pair='CC_DG',mode='calibration',
                          session_id=m['session_id'],manifest='manifests/'+mf.name,manifest_sha256=p.digest(mf))]
    file=output/'collection_plan.json';cal.write_new(file,plan)
    script=state.render_run_script(p.digest(file)).replace('tools.d1_energy_state_collection',
                                                          'tools.d1_energy_ap_short_transition')
    (output/'RUN_AFTER_APPROVAL.ps1').write_text(script,encoding='utf-8-sig')
    return check(file)


def check(file):
    file=Path(file);plan=p.read(file);budget_check(plan['budget'])
    require(plan['experiment_id']==EXPERIMENT and plan['status']=='PC_READY_DEVICE_UNVERIFIED_NOT_APPROVED' and
            plan['approval']=='not_approved' and not plan['experiment_ready'] and
            plan['autonomous_diagnostic_only'] and plan['short_transition_diagnostic_only'] and
            not plan['state_model_followup'] and plan['diagnostic_only'], 'plan identity')
    require(Path(plan['plan_file'])==file.resolve() and
            Path(plan['output_root'])==file.parent.parent/RUN_FOLDER and
            Path(plan['registry'])==file.parent.parent/'energy_collection_registry'/EXPERIMENT and
            not Path(plan['output_root']).exists() and not Path(plan['registry']).exists(), 'no consumed run')
    source=p.read(plan['source_plan']['path']);build=p.read(plan['build_receipt'])
    require(p.digest(plan['source_plan']['path'])==plan['source_plan']['sha256'] and
            p.digest(plan['prior_freeze']['path'])==plan['prior_freeze']['sha256']==FREEZE_SHA and
            p.digest(plan['build_receipt'])==plan['build_receipt_sha256'] and
            plan['source_code']==identity() and
            cal.apk_sources(build['source_code'])==cal.apk_sources(identity()) and
            p.digest(plan['apk_path'])==plan['apk_sha256'], 'source/APK/freeze identity')
    require(apk.inspect(plan['apk_path'],plan['apk_preflight']['toolchain'])==
            plan['apk_preflight']['candidate'] and
            plan['apk_preflight']['candidate']['signer_sha256']==
            source['apk_preflight']['candidate']['signer_sha256'], 'signed APK')
    for item in list(plan['source_files'].values())+list(plan['references'].values()):
        require(p.digest(item['path'])==item['sha256'], 'staging/reference identity')
    require(len(plan['entries'])==1 and len(plan['source_files'])==6 and len(plan['references'])==4,
            'single seven-file session')
    entry=plan['entries'][0];m=p.read(file.parent/entry['manifest'])
    require(entry['pair']=='CC_DG' and entry['phase']=='confirmation' and entry['index']==0 and
            m==expected_manifest(source,plan['apk_sha256']) and
            p.digest(file.parent/entry['manifest'])==entry['manifest_sha256'] and
            plan['temperature_preparation']==source['temperature_preparation'] and
            plan['screen_contract']==source['screen_contract'] and
            plan['acceptance']['joint_lane_occupancy_min_seconds']==10, 'short transition/gates')
    return dict(status=plan['status'],plan_sha256=p.digest(file),budget=BUDGET,device_commands=0)


def main():
    cli=argparse.ArgumentParser();sub=cli.add_subparsers(dest='action',required=True)
    q=sub.add_parser('prepare')
    for name in ('source-plan','build-receipt','frozen','output'):q.add_argument('--'+name,required=True)
    q=sub.add_parser('check');q.add_argument('--plan',required=True)
    q=sub.add_parser('run')
    for name in ('plan','adb','expected-sha'):q.add_argument('--'+name,required=True)
    q.add_argument('--approved',action='store_true');q.add_argument('--serial')
    a=cli.parse_args()
    if a.action=='prepare':result=prepare(a.source_plan,a.build_receipt,a.frozen,a.output)
    elif a.action=='check':result=check(a.plan)
    else:
        from tools import d1_energy_collection_device as device
        result=device.run(Path(a.plan),a.adb,a.serial,a.expected_sha,a.approved)
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
