"""PC-only preparation and separately approved, one-shot APK deployment recovery.

The stopped energy collection plan supplies immutable APK identity only. Its sessions
are never called. Deployment stages and cleanup reuse d1_collection_recovery.recover.
"""
import argparse
import json
from pathlib import Path
import time

from tools import d1_apk_identity as apk
from tools import d1_arrival_plan as p
from tools import d1_collection_recovery as recovery
from tools import d1_recorded_process as rp


ID = 'ENERGY-AP-DEPLOY-RECOVERY-01'
PARENT_SHA = 'b717df5c51c27f1f8a0f4d08604203b0c89b9d61fd054c96e794bc9537a59f02'
BUDGET = dict(preflight=200, transfer_and_remote_hash=150,
              package_install_and_client_reap=125, post_identity=60,
              cleanup=45, administrative_reserve=20)
HOST_FILES = ('tools/d1_energy_ap_deploy_recovery.py', 'tools/d1_collection_recovery.py',
              'tools/d1_recorded_process.py', 'tools/d1_apk_identity.py')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def write_new(path, value):
    with Path(path).open('x', encoding='utf-8') as out:
        json.dump(value, out, ensure_ascii=False, indent=2)
        out.write('\n')


def prepare(parent, stopped_receipt, stopped_registry, bundle):
    parent, stopped_receipt, stopped_registry, bundle = map(
        Path, (parent, stopped_receipt, stopped_registry, bundle))
    require(not bundle.exists(), 'new bundle path required')
    require(p.digest(parent) == PARENT_SHA, 'stopped parent plan changed')
    prior = p.read(parent)
    require(p.read(stopped_receipt)['status'] == 'stopped_no_resume', 'parent not stopped')
    require(p.read(stopped_registry)['status'] == 'stopped_no_resume', 'registry not stopped')
    require(prior['experiment_id'] == 'ENERGY-AP-STATE-COLLECT-03', 'wrong parent')
    require(p.digest(prior['apk_path']) == prior['apk_sha256'], 'candidate APK changed')
    require(p.digest(prior['build_receipt']) == prior['build_receipt_sha256'], 'build receipt changed')
    source_root = Path(__file__).resolve().parent.parent
    host = {name: p.digest(source_root / name) for name in HOST_FILES}
    base = bundle.parent.resolve()
    plan = dict(protocol='energy-ap-deploy-recovery-v1', experiment_id=ID,
                status='PC_READY_DEVICE_UNVERIFIED_NOT_APPROVED',
                collection_plan=str(parent.resolve()), collection_plan_sha256=PARENT_SHA,
                stopped_receipt=str(stopped_receipt.resolve()),
                stopped_receipt_sha256=p.digest(stopped_receipt),
                stopped_registry=str(stopped_registry.resolve()),
                stopped_registry_sha256=p.digest(stopped_registry),
                candidate_apk_sha256=prior['apk_sha256'],
                candidate_identity=prior['apk_preflight']['candidate'],
                build_receipt_sha256=prior['build_receipt_sha256'], host_sha256=host,
                output_root=str(base / 'energy_ap_deploy_recovery_run_v1'),
                registry=str(base / 'energy_ap_deploy_registry' / ID),
                remote_apk='/data/local/tmp/d1check-energy-ap-deploy-recovery-01/candidate.apk',
                recovery_seconds=600, recovery_budgets=BUDGET,
                transfer_cap=1, install_cap=1, session_cap=0, inference_cap=0,
                retry_cap=0, replacement_cap=0, additional_cap=0,
                push_timeout_seconds=120, install_timeout_seconds=120,
                skip_rule='only exact candidate package/version/signer/APK SHA after live pull',
                experiment_ready=False)
    bundle.mkdir(parents=True)
    write_new(bundle / 'recovery_plan.json', plan)
    plan_sha = p.digest(bundle / 'recovery_plan.json')
    script = ("param([ValidateSet('Check','Run')][string]$Action='Check', "
              "[switch]$Approved, [string]$Serial)\n"
              "$ErrorActionPreference='Stop'\n"
              "$repo='C:/Users/LG/AndroidStudioProjects/D1Check-model02b'\n"
              "Set-Location $repo\n"
              "$plan=Join-Path $PSScriptRoot 'recovery_plan.json'\n"
              "if ($Action -eq 'Check') { python -m tools.d1_energy_ap_deploy_recovery check --plan $plan; exit $LASTEXITCODE }\n"
              "if (-not $Approved -or -not $Serial) { throw 'Run requires -Approved and live A24 transport serial' }\n"
              "$adb='C:/Users/LG/AppData/Local/Android/Sdk/platform-tools/adb.exe'\n"
              "python -m tools.d1_energy_ap_deploy_recovery run --plan $plan --adb $adb --serial $Serial "
              f"--expected-plan-sha256 {plan_sha} --approved\n"
              "exit $LASTEXITCODE\n")
    (bundle / 'RUN_AFTER_APPROVAL.ps1').write_text(script, encoding='utf-8')
    return check(bundle / 'recovery_plan.json')


def check(path):
    path = Path(path)
    r = p.read(path)
    require(r['protocol'] == 'energy-ap-deploy-recovery-v1' and r['experiment_id'] == ID,
            'wrong deployment namespace')
    require(r['status'] == 'PC_READY_DEVICE_UNVERIFIED_NOT_APPROVED', 'status changed')
    require(r['collection_plan_sha256'] == PARENT_SHA and
            p.digest(r['collection_plan']) == PARENT_SHA, 'parent plan identity')
    require(p.read(r['stopped_receipt'])['status'] == 'stopped_no_resume' and
            p.digest(r['stopped_receipt']) == r['stopped_receipt_sha256'], 'parent receipt changed')
    require(p.read(r['stopped_registry'])['status'] == 'stopped_no_resume' and
            p.digest(r['stopped_registry']) == r['stopped_registry_sha256'], 'parent registry changed')
    require(r['recovery_seconds'] == sum(BUDGET.values()) == 600 and
            r['recovery_budgets'] == BUDGET, 'time budget changed')
    require((r['transfer_cap'], r['install_cap'], r['session_cap'], r['inference_cap'],
             r['retry_cap'], r['replacement_cap'], r['additional_cap']) == (1, 1, 0, 0, 0, 0, 0),
            'operation budget changed')
    require(r['push_timeout_seconds'] == r['install_timeout_seconds'] == 120, 'timeout changed')
    require(r['remote_apk'] == '/data/local/tmp/d1check-energy-ap-deploy-recovery-01/candidate.apk',
            'remote path changed')
    base = path.resolve().parent.parent
    require(Path(r['output_root']).resolve() == base / 'energy_ap_deploy_recovery_run_v1' and
            Path(r['registry']).resolve() == base / 'energy_ap_deploy_registry' / ID,
            'deployment output/registry scope changed')
    require(not Path(r['output_root']).exists() and not Path(r['registry']).exists(),
            'deployment consumed: no retry')
    parent = p.read(r['collection_plan'])
    require(parent['experiment_id'] == 'ENERGY-AP-STATE-COLLECT-03' and
            parent['apk_sha256'] == r['candidate_apk_sha256'] and
            parent['apk_preflight']['candidate'] == r['candidate_identity'], 'APK binding')
    require(p.digest(parent['build_receipt']) == r['build_receipt_sha256'], 'build receipt changed')
    root = Path(__file__).resolve().parent.parent
    require(set(r['host_sha256']) == set(HOST_FILES) and all(
        p.digest(root / name) == sha for name, sha in r['host_sha256'].items()),
        'host code changed')
    for name, sha in parent['apk_preflight']['tool_sha256'].items():
        require(p.digest(parent['apk_preflight']['toolchain'][name]) == sha, 'APK tool changed')
    require(apk.inspect(parent['apk_path'], parent['apk_preflight']['toolchain']) == r['candidate_identity'],
            'candidate APK or signature changed')
    return dict(status=r['status'], plan_sha256=p.digest(path), apk_sha256=r['candidate_apk_sha256'],
                device_calls=0, transfer_cap=1, install_cap=1, collection_sessions=0,
                recovery_seconds=600)


def run(path, adb, serial, approved, expected_plan_sha256):
    require(approved and expected_plan_sha256 == p.digest(path), 'separate approval and frozen hash required')
    check(path)
    r = p.read(path)
    registry = Path(r['registry'])
    registry.parent.mkdir(parents=True, exist_ok=True)
    registry.mkdir()  # One-shot claim before any device call; a crash cannot silently retry.
    start = time.monotonic()
    write_new(registry / 'claim.json', dict(utc=rp.utc(), plan_sha256=p.digest(path),
                                           recovery_seconds=600, serial=serial))
    try:
        result = recovery.recover(path, adb, serial, start + 600,
                                  root_only=True, require_hardware_serial=True)
        write_new(registry / 'complete.json', dict(utc=rp.utc(), status='verified',
                                                  receipt=str(Path(r['output_root']) / 'receipt.json')))
        return result
    except BaseException as error:
        write_new(registry / 'stopped.json', dict(utc=rp.utc(), status='stopped_no_resume',
                                                 error=repr(error)))
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    prep = sub.add_parser('prepare')
    for flag in ('parent', 'stopped-receipt', 'stopped-registry', 'bundle'):
        prep.add_argument('--' + flag, required=True)
    for command in ('check', 'run'):
        q = sub.add_parser(command)
        q.add_argument('--plan', required=True)
        if command == 'run':
            for flag in ('adb', 'serial', 'expected-plan-sha256'):
                q.add_argument('--' + flag, required=True)
            q.add_argument('--approved', action='store_true')
    args = parser.parse_args()
    if args.command == 'prepare':
        result = prepare(args.parent, args.stopped_receipt, args.stopped_registry, args.bundle)
    elif args.command == 'check':
        result = check(args.plan)
    else:
        result = run(args.plan, args.adb, args.serial, args.approved, args.expected_plan_sha256)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
