"""One-session, unapproved diagnostic of the post-probe device continuation.

The prior development freeze is deliberately not fitted or evaluated here. Prepare
and Check are PC-only; Run delegates to the existing single-use observed runner.
"""
from __future__ import annotations
import argparse
import copy
import json
import time
import uuid
from pathlib import Path

from tools import d1_arrival_plan as p
from tools import d1_arrival_timing_calibration as cal
from tools import d1_energy_state_collection as state
from tools import d1_energy_ap_followup as followup
from tools import d1_energy_collection as old
from tools import d1_energy_host_lifecycle as lifecycle
from tools import d1_energy_host_checkpoints as checkpoints
from tools import d1_apk_identity as apk
from tools.d1_energy_thermal import require

EXPERIMENT = 'ENERGY-AP-DEVICE-SEGMENT-DIAG-04'
CONTROL = 'device-after-probe-diagnostic-v1'
PLAN_FOLDER = 'energy_ap_device_segment_diag_plan_v4'
RUN_FOLDER = 'energy_ap_device_segment_diag_run_v4'
BUDGET = dict(state.BUDGET, sessions=1, development=0, confirmation=0, diagnostic=1,
    work_requests=1680, eligibility_requests=4, diagnostic_requests=1684,
    warmup=8, explicit_inference=1692, runtime_creations=4,
    staging=1, staged_files=7, apk_transfers=1, installs=1,
    installed_host_pulls=1, retry=0, replacement=0, additional=0,
    fixed_observation_seconds=1020, freeze_seconds=0,
    installed_preflight_seconds=600, apk_push_timeout_seconds=180,
    total_seconds=2700, adb_command_slots=11000, pre_cleanup_command_slots=10900,
    stopped_recovery_seconds=90, stopped_recovery_adb_commands=12)


def identity():
    return state.identity() | {'tools/d1_energy_ap_autonomous_diag.py': p.digest(__file__)}


def budget_check(b=BUDGET):
    require(b == BUDGET and b['sessions'] == b['diagnostic'] == 1, 'single diagnostic only')
    require(b['diagnostic_requests'] == b['work_requests'] + b['eligibility_requests'] and
            b['explicit_inference'] == b['diagnostic_requests'] + b['warmup'], 'inference budget')
    require(b['total_seconds'] == b['installed_preflight_seconds'] + b['session_seconds'] and
            b['fixed_observation_seconds'] == 120 + 120 + 600 + 180, 'time budget')
    require(b['apk_transfers'] == b['installs'] == b['installed_host_pulls'] == 1 and
            b['retry'] == b['replacement'] == b['additional'] == 0, 'deployment/no-retry budget')
    require(b['apk_push_timeout_seconds'] == 180 and b['adb_command_slots'] == 11000 and
            b['pre_cleanup_command_slots'] == 10900 and
            b['stopped_recovery_seconds'] == 90 and b['stopped_recovery_adb_commands'] == 12,
            'ADB budget')
    h=b['host_poll_seconds']
    poll_upper=(int(h/.25)+1)+3*(int(h/2)+1)+(int(h/10)+1)+int((int(h/2)+1)/5)+18
    # Same conservative poll bound as the formal runner; no mandatory AP or
    # screen observation is removed merely to make the command count smaller.
    normal_upper=21+poll_upper+(14+2+33+1+4+3)
    require(normal_upper==10361 and normal_upper<b['pre_cleanup_command_slots'] and
            b['adb_command_slots']-b['pre_cleanup_command_slots']>=100,
            'poll/cleanup ADB command reservation')


def expected_manifest(source, apk_sha):
    # The old confirmation CG_DC regimen is used only as a diagnostic workload.
    original = source['entries'][0]
    old_manifest = p.read(Path(source['plan_file']).parent / original['manifest'])
    m = copy.deepcopy(old_manifest)
    sid = str(uuid.uuid5(uuid.NAMESPACE_URL, EXPERIMENT + '/diagnostic/CG_DC'))
    m.update(experiment_id=EXPERIMENT, session_id=sid, apk_sha256=apk_sha,
             session_control=CONTROL, autonomous_diagnostic_only=True,
             device_screen_contract={k: source['screen_contract'][k] for k in
                 ('screen_brightness', 'screen_brightness_mode', 'screen_off_timeout')})
    for spec in m['models'].values():
        spec['identity']['session_id'] = sid
        spec['target']['apk_sha256'] = apk_sha
    return m


def prepare(source_file, build_file, output):
    source_file, build_file, output = map(Path, (source_file, build_file, output))
    require(not output.exists() and output.name == PLAN_FOLDER, 'new dedicated plan path')
    source, build = p.read(source_file), p.read(build_file)
    require(source['experiment_id'] == followup.EXPERIMENT and source['state_model_followup'] and
            source['entries'][0]['pair'] == 'CG_DC', 'source confirmation regimen')
    require(build['status'] == 'built_not_device_verified' and
            cal.apk_sources(build['source_code']) == cal.apk_sources(identity()) and
            p.digest(build['apk_path']) == build['apk_sha256'], 'built APK/source')
    candidate = apk.inspect(build['apk_path'], source['apk_preflight']['toolchain'])
    require(candidate['signer_sha256'] == source['apk_preflight']['candidate']['signer_sha256'],
            'project signer changed')
    budget_check()
    output.mkdir(); (output/'manifests').mkdir()
    plan = copy.deepcopy(source)
    for key in ('state_model_followup', 'prior_plan', 'prior_receipt', 'prior_freeze',
                'prior_completed_confirmation', 'installed_receipt'):
        plan.pop(key, None)
    plan.update(experiment_id=EXPERIMENT, status='PC_READY_DEVICE_UNVERIFIED_NOT_APPROVED',
        approval='not_approved', diagnostic_only=True, autonomous_diagnostic_only=True,
        budget=copy.deepcopy(BUDGET), source_code=identity(),
        plan_file=str((output/'collection_plan.json').resolve()),
        output_root=str(output.parent/RUN_FOLDER),
        registry=str(output.parent/'energy_collection_registry'/EXPERIMENT),
        build_receipt=str(build_file.resolve()), build_receipt_sha256=p.digest(build_file),
        apk_path=build['apk_path'], apk_sha256=build['apk_sha256'],
        apk_preflight=dict(source['apk_preflight'], candidate=candidate),
        source_plan=dict(path=str(source_file.resolve()), sha256=p.digest(source_file)),
        analysis=dict(scope='host-gated preparation followed by device-local baseline/load/cooling diagnostic',
            formal_confirmation=False, development_fit=False, ap_after_probe='host observed only; missing is ineligible',
            current_unit='A24 raw mA hypothesis; absolute J not certified'), entries=[])
    m = expected_manifest(source, build['apk_sha256'])
    mf = output/'manifests'/(m['session_id']+'.json'); cal.write_new(mf,m)
    plan['entries'].append(dict(index=0, phase=m['phase'], pair=m['pair'], mode=m['mode'],
        session_id=m['session_id'], manifest='manifests/'+mf.name, manifest_sha256=p.digest(mf)))
    file=output/'collection_plan.json'; cal.write_new(file,plan)
    script=state.render_run_script(p.digest(file)).replace('tools.d1_energy_state_collection',
                                                        'tools.d1_energy_ap_autonomous_diag')
    (output/'RUN_AFTER_APPROVAL.ps1').write_text(script,encoding='utf-8-sig')
    return check(file)


def check(file):
    file=Path(file); plan=p.read(file); budget_check(plan['budget'])
    require(plan['experiment_id']==EXPERIMENT and plan['protocol']==state.PROTOCOL and
            plan['status']=='PC_READY_DEVICE_UNVERIFIED_NOT_APPROVED' and
            plan['approval']=='not_approved' and not plan['experiment_ready'] and
            plan['state_model_calibration'] and plan['diagnostic_only'] and
            plan['autonomous_diagnostic_only'] and not plan.get('state_model_followup'), 'diagnostic identity')
    require(Path(plan['plan_file'])==file.resolve() and
            Path(plan['output_root'])==file.parent.parent/RUN_FOLDER and
            Path(plan['registry'])==file.parent.parent/'energy_collection_registry'/EXPERIMENT and
            not Path(plan['output_root']).exists() and not Path(plan['registry']).exists(),
            'single-use output/registry')
    source_file=Path(plan['source_plan']['path']);source=p.read(source_file)
    build=p.read(plan['build_receipt'])
    require(p.digest(source_file)==plan['source_plan']['sha256'] and
            p.digest(plan['build_receipt'])==plan['build_receipt_sha256'] and
            plan['source_code']==identity() and
            cal.apk_sources(build['source_code'])==cal.apk_sources(identity()) and
            plan['apk_path']==build['apk_path'] and p.digest(plan['apk_path'])==plan['apk_sha256'],
            'source/build/APK identity')
    require(apk.inspect(plan['apk_path'],plan['apk_preflight']['toolchain'])==
            plan['apk_preflight']['candidate'] and
            plan['apk_preflight']['candidate']['signer_sha256']==
            source['apk_preflight']['candidate']['signer_sha256'], 'signed APK')
    for entry in list(plan['source_files'].values())+list(plan['references'].values()):
        require(p.digest(entry['path'])==entry['sha256'], 'staging/reference changed')
    require(len(plan['entries'])==1 and len(plan['source_files'])==6 and
            len(plan['references'])==4, 'one seven-file diagnostic')
    e=plan['entries'][0];mf=file.parent/e['manifest'];m=p.read(mf)
    require(e['index']==0 and e['pair']=='CG_DC' and e['phase']=='confirmation' and
            e['mode']=='calibration' and m==expected_manifest(source,plan['apk_sha256']) and
            p.digest(mf)==e['manifest_sha256'] and m['session_id']==e['session_id'], 'manifest/control')
    require(plan['temperature_preparation']==source['temperature_preparation'] and
            plan['screen_contract']==source['screen_contract'] and
            plan['acceptance']==source['acceptance'], 'host gate contract changed')
    return dict(status=plan['status'],plan_sha256=p.digest(file),budget=BUDGET,device_commands=0)


def recover_stopped(file, adb_path, output, query=lifecycle.process_snapshot, device_factory=None):
    """One read-only, same-session recovery after the original host has exited.

    This never arms, launches, restarts, or stops an app. An absent terminal app
    record is an unknown running state, not permission to force recovery.
    """
    from tools import d1_energy_collection_device as device
    from tools.d1_adb_observed_client import ObservedDevice
    file, output = Path(file), Path(output)
    plan = p.read(file)
    require(plan['experiment_id'] == EXPERIMENT and plan['autonomous_diagnostic_only'] and
            plan['source_code'] == identity() and p.digest(plan['apk_path']) == plan['apk_sha256'],
            'recovery plan/source/APK identity')
    original = Path(plan['output_root'])
    owner = lifecycle.inspect_run(original, plan['registry'], p.digest(file), query=query)
    require(owner['status'] == 'host_exited' and owner['terminal'] != 'completed' and
            owner['recoverable'], 'original host active, unconfirmed, or complete')
    entry = plan['entries'][0]
    session = original / f"{entry['index']:02d}_{entry['session_id']}"
    require((session/'launch_attempt.json').is_file() and
            (session/'autonomous_segment_arm_intent.json').is_file(), 'same session was not armed')
    intent = p.read(session/'autonomous_segment_arm_intent.json')
    require(intent['session_id'] == entry['session_id'] and
            intent['manifest_sha256'] == entry['manifest_sha256'], 'armed session identity')
    require(output == original.parent/(RUN_FOLDER+'_read_only_recovery') and
            not output.exists(), 'one fixed read-only recovery output path')
    claim_dir=Path(plan['registry'])/'read_only_recovery_claim'
    claim_dir.mkdir(exist_ok=False)
    checkpoints.atomic_new(claim_dir/'claimed.json',dict(
        plan_sha256=p.digest(file),session_id=entry['session_id'],host_run_id=owner['host_run_id'],
        purpose='same_session_evidence_only_no_restart'))
    output.mkdir(parents=True)
    start = time.monotonic()
    d = (device_factory(adb_path, None, output/'host_commands', allow_select=True,
                        forbid_apk_deploy=True) if device_factory else
         ObservedDevice(adb_path, None, output/'host_commands', allow_select=True,
                        forbid_apk_deploy=True))
    d.deadline = start + BUDGET['stopped_recovery_seconds']
    d.command_limit = BUDGET['stopped_recovery_adb_commands']
    remote = f"files/{state.PROTOCOL}/{entry['session_id']}"
    result = dict(status='state_unconfirmed', source_plan_sha256=p.digest(file),
                  original_host=owner, session_id=entry['session_id'], remote=remote,
                  meaning='read_only_no_restart_or_force_stop')
    try:
        identity_record = d.identify(plan['device_fingerprint'])
        serial = d.call('shell','getprop','ro.serialno',timeout=3).stdout.decode().strip()
        require(serial == plan['device_hardware_serial'], 'wrong A24 hardware')
        result['device'] = identity_record
        manifest = device.pull_file(d,remote,'manifest.json',output/'identity')
        require(p.digest(manifest) == entry['manifest_sha256'], 'remote session manifest mismatch')
        cleanup = device.pull_file(d,remote,'cleanup.json',output/'identity')
        terminal = p.read(cleanup)
        require(terminal.get('status') in ('completed','failed'), 'app terminal state unconfirmed')
        result['app_terminal'] = terminal['status']
        result['recovery'] = device.recover(d,remote,output/'artifacts',best_effort_prefix=True)
        result['status'] = 'same_session_recovered'
    except BaseException as exc:
        result['error'] = repr(exc)
    result['adb_command_slots'] = d.sequence
    result['elapsed_seconds'] = time.monotonic()-start
    (output/'READ_ONLY_RECOVERY_RECEIPT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    return result


def main():
    parser=argparse.ArgumentParser();sub=parser.add_subparsers(dest='action',required=True)
    q=sub.add_parser('prepare');q.add_argument('--source-plan',required=True);q.add_argument('--build-receipt',required=True);q.add_argument('--output',required=True)
    q=sub.add_parser('check');q.add_argument('--plan',required=True)
    q=sub.add_parser('run')
    for name in ('plan','adb','expected-sha'):q.add_argument('--'+name,required=True)
    q.add_argument('--approved',action='store_true');q.add_argument('--serial')
    q=sub.add_parser('recover-stopped')
    for name in ('plan','adb','expected-sha','output'):q.add_argument('--'+name,required=True)
    q.add_argument('--approved',action='store_true')
    args=parser.parse_args()
    if args.action=='prepare':result=prepare(args.source_plan,args.build_receipt,args.output)
    elif args.action=='check':result=check(args.plan)
    elif args.action=='run':
        from tools import d1_energy_collection_device as device
        result=device.run(Path(args.plan),args.adb,args.serial,args.expected_sha,args.approved)
    else:
        require(args.approved and p.digest(args.plan)==args.expected_sha,
                'separate explicit read-only recovery approval/hash required')
        result=recover_stopped(args.plan,args.adb,args.output)
    print(__import__('json').dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
