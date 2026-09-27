"""One-shot installation of the already verified remote energy/AP APK.

Prepare/check are PC-only. Run never pushes, launches, or infers.
"""
import argparse
import json
from pathlib import Path
import re
import subprocess
import time

from tools import d1_apk_identity as apk
from tools import d1_arrival_device as legacy
from tools import d1_arrival_plan as p
from tools import d1_arrival_timing_calibration_device as shared
from tools import d1_collection_recovery as recovery
from tools import d1_recorded_process as rp


ID = 'ENERGY-AP-INSTALL-ONLY-02'
REMOTE = '/data/local/tmp/d1check-energy-ap-push-observe-01.apk'
APK_SHA = 'b273f74b9b4eb91227db1ec2f7ef260d3d0f2c813790eaf4aedf30af98a114cf'
SOURCE = ('tools/d1_energy_ap_install_only.py', 'tools/d1_apk_identity.py',
          'tools/d1_collection_recovery.py', 'tools/d1_arrival_device.py',
          'tools/d1_arrival_timing_calibration_device.py', 'tools/d1_recorded_process.py',
          'tools/d1_arrival_plan.py', 'tools/d1_arrival_collection.py')
BUDGET = dict(preflight=220, remote_sha=120, install=125, post_identity=60,
              cleanup=45, reserve=20)
TOTAL_SECONDS = 600
ADB_CAP = 22


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def write_new(path, value):
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def remote_hash(device, path):
    response = device.call('shell', 'sha256sum', path, timeout=120)
    match = re.fullmatch(rb'([0-9a-f]{64})\s+' + re.escape(path.encode()) + rb'\s*',
                         response.stdout.strip())
    require(match is not None, 'remote SHA output unavailable or wrong path')
    return match[1].decode()


def prepare(bundle, observed_receipt, observed_plan, parent_plan):
    bundle, observed_receipt, observed_plan, parent_plan = map(
        Path, (bundle, observed_receipt, observed_plan, parent_plan))
    require(not bundle.exists(), 'new install-only bundle required')
    observed = p.read(observed_receipt)
    earlier = p.read(observed_plan)
    parent = p.read(parent_plan)
    require(observed['status'] == 'transfer_verified' and
            observed['plan_sha256'] == p.digest(observed_plan), 'observed push not bound')
    require(earlier['experiment_id'] == 'ENERGY-AP-PUSH-OBSERVE-01' and
            earlier['remote_apk'] == REMOTE and earlier['apk_sha256'] == APK_SHA,
            'observed plan changed')
    require(observed['final_remote']['sha256'] == APK_SHA and
            observed['final_remote']['bytes'] == earlier['apk_bytes'], 'observed remote not verified')
    require(parent['experiment_id'] == 'ENERGY-AP-STATE-COLLECT-03' and
            parent['apk_sha256'] == APK_SHA and
            parent['apk_preflight']['candidate']['apk_sha256'] == APK_SHA,
            'candidate lineage changed')
    require(p.digest(parent['apk_path']) == APK_SHA and
            p.digest(earlier['adb']) == earlier['adb_sha256'], 'local executable changed')
    root = Path(__file__).resolve().parent.parent
    plan = dict(protocol='energy-ap-install-only-v2', experiment_id=ID,
        status='PC_READY_DEVICE_UNVERIFIED',
        observed_receipt=str(observed_receipt.resolve()),
        observed_receipt_sha256=p.digest(observed_receipt),
        observed_plan=str(observed_plan.resolve()),
        observed_plan_sha256=p.digest(observed_plan),
        parent_plan=str(parent_plan.resolve()), parent_plan_sha256=p.digest(parent_plan),
        apk_path=parent['apk_path'], apk_sha256=APK_SHA,
        apk_preflight=parent['apk_preflight'],
        device_fingerprint=parent['device_fingerprint'],
        device_hardware_serial=parent['device_hardware_serial'],
        battery_start_percent=parent['battery_start_percent'],
        battery_min_percent=parent['battery_min_percent'],
        battery_max_temperature_tenths_c=parent['battery_max_temperature_tenths_c'],
        require_unplugged=parent['require_unplugged'],
        screen_contract=parent['screen_contract'],
        adb=earlier['adb'], adb_sha256=earlier['adb_sha256'],
        remote_apk=REMOTE, candidate=parent['apk_preflight']['candidate'],
        source_sha256={name:p.digest(root/name) for name in SOURCE},
        output_root=str((bundle.parent/'energy_ap_install_only_run_v2').resolve()),
        registry=str((bundle.parent/'energy_ap_install_only_registry'/ID).resolve()),
        total_seconds=TOTAL_SECONDS, stage_budgets=BUDGET, adb_cap=ADB_CAP,
        pull_cap=1, push_cap=0, install_cap=1, install_timeout_seconds=120,
        launch_cap=0, warmup_cap=0, inference_cap=0,
        retry_cap=0, replacement_cap=0, additional_cap=0,
        skip_rule='skip only when preflight pulled installed base APK exactly equals candidate',
        experiment_ready=False)
    bundle.mkdir(parents=True)
    write_new(bundle/'install_plan.json', plan)
    digest = p.digest(bundle/'install_plan.json')
    script = ("param([ValidateSet('Check','Run')][string]$Action='Check', [switch]$Approved)\n"
        "$ErrorActionPreference='Stop'\n"
        "$repo='C:/Users/LG/AndroidStudioProjects/D1Check-model02b'\n"
        "Set-Location $repo\n"
        "$plan=Join-Path $PSScriptRoot 'install_plan.json'\n"
        "if ($Action -eq 'Check') { python -m tools.d1_energy_ap_install_only check --plan $plan; exit $LASTEXITCODE }\n"
        "if (-not $Approved) { throw 'Run requires approval' }\n"
        f"python -m tools.d1_energy_ap_install_only run --plan $plan --expected-sha256 {digest} --approved\n"
        "exit $LASTEXITCODE\n")
    (bundle/'RUN_AFTER_APPROVAL.ps1').write_text(script, encoding='utf-8')
    return check(bundle/'install_plan.json')


def check(path):
    path = Path(path); q = p.read(path)
    require(q['protocol'] == 'energy-ap-install-only-v2' and q['experiment_id'] == ID and
            q['status'] == 'PC_READY_DEVICE_UNVERIFIED', 'install namespace/status')
    require(q['remote_apk'] == REMOTE and q['apk_sha256'] == APK_SHA, 'APK/remote changed')
    require(q['total_seconds'] == TOTAL_SECONDS and q['stage_budgets'] == BUDGET and
            sum(BUDGET.values()) == 590 and q['adb_cap'] == ADB_CAP,
            'install time/command budget changed')
    require((q['pull_cap'], q['push_cap'], q['install_cap'],q['install_timeout_seconds'],
             q['launch_cap'],q['warmup_cap'],q['inference_cap'],q['retry_cap'],
             q['replacement_cap'],q['additional_cap']) == (1,0,1,120,0,0,0,0,0,0),
             'operation budget changed')
    base = path.resolve().parent.parent
    require(Path(q['output_root']).resolve() == base/'energy_ap_install_only_run_v2' and
            Path(q['registry']).resolve() == base/'energy_ap_install_only_registry'/ID and
            not Path(q['output_root']).exists() and not Path(q['registry']).exists(),
            'install-only plan consumed/output changed')
    require(p.digest(q['observed_receipt']) == q['observed_receipt_sha256'] and
            p.digest(q['observed_plan']) == q['observed_plan_sha256'] and
            p.digest(q['parent_plan']) == q['parent_plan_sha256'], 'lineage changed')
    observed=p.read(q['observed_receipt']); parent=p.read(q['parent_plan'])
    require(observed['status']=='transfer_verified' and
            observed['final_remote']['sha256']==APK_SHA and
            parent['apk_preflight']['candidate']==q['candidate'], 'remote/candidate lineage')
    require(all(q[key]==parent[key] for key in ('apk_path','apk_preflight','device_fingerprint',
            'device_hardware_serial','battery_start_percent','battery_min_percent',
            'battery_max_temperature_tenths_c','require_unplugged','screen_contract')),
            'frozen parent gates changed')
    require(p.digest(q['adb'])==q['adb_sha256'] and p.digest(q['apk_path'])==APK_SHA,
            'ADB or candidate APK changed')
    root=Path(__file__).resolve().parent.parent
    require(set(q['source_sha256'])==set(SOURCE) and all(
            p.digest(root/name)==sha for name,sha in q['source_sha256'].items()),
            'install code changed')
    tools=q['apk_preflight']['toolchain']
    require(all(p.digest(tools[name])==sha for name,sha in
                q['apk_preflight']['tool_sha256'].items()), 'signature tool changed')
    require(apk.inspect(q['apk_path'], tools)==q['candidate'], 'APK signature/package changed')
    return dict(status=q['status'], plan_sha256=p.digest(path), device_calls=0,
                pull_cap=1,push_cap=0,install_cap=1,total_seconds=600)


def recorded_device():
    parent = recovery.device_class(root_only=True)
    class InstallDevice(parent):
        def __init__(self, adb, root):
            super().__init__(adb, None, root)
            self.pulls=0; self.installs=0
        def call(self, *args, timeout=30, check=True):
            require(self.sequence < ADB_CAP, 'ADB command cap reached')
            require(args[0] != 'push', 'new APK push forbidden')
            if self.serial is None:
                require(args == ('devices','-l'), 'transport must be selected first')
                remaining=self.deadline-time.monotonic()
                require(remaining>5, 'insufficient command/reap time')
                folder=self.root/f'{self.sequence:03d}';self.sequence+=1
                response=rp.run([self.adb,'devices','-l'],folder,min(timeout,remaining-5),
                                ['adb','devices','-l'],root_only=True)
                stdout=(folder/'stdout.bin').read_bytes() if (folder/'stdout.bin').exists() else b''
                stderr=(folder/'stderr.bin').read_bytes() if (folder/'stderr.bin').exists() else b''
                require(response['status'] in ('returned','nonzero_exit'),
                        'unselected transport query failed; no retry')
                require(not check or response['returncode']==0,
                        'unselected transport query nonzero; no retry')
                return subprocess.CompletedProcess(['adb','devices','-l'],
                                                   response['returncode'],stdout,stderr)
            if args[0] == 'pull':
                require(self.pulls == 0, 'second pull forbidden'); self.pulls += 1
            if args[:3] == ('shell','pm','install'):
                require(self.installs == 0, 'second install forbidden'); self.installs += 1
            return super().call(*args, timeout=timeout, check=check)
    return InstallDevice


def install_only_cleanup(device, hard):
    """No app was launched; verify absence without sending a force-stop command."""
    previous=device.deadline
    device.deadline=min(time.monotonic()+BUDGET['cleanup'],hard)
    try:
        legacy.require_stopped(device)
        thermal=device.call('shell','dumpsys','thermalservice',timeout=15).stdout
        require(re.search(rb'Thermal Status:\s*0\b',thermal),'post-install thermal gate')
        return dict(status='completed',app_cleanup='not_applicable_no_app_launch',
                    host_client_cleanup='recorded_per_command',utc=rp.utc())
    finally:
        device.deadline=previous


def run(path, expected_sha, approved):
    require(approved and p.digest(path)==expected_sha, 'approved frozen plan required')
    check(path);q=p.read(path)
    registry=Path(q['registry']);registry.parent.mkdir(parents=True,exist_ok=True);registry.mkdir()
    out=Path(q['output_root']);out.mkdir()
    start=time.monotonic();hard=start+TOTAL_SECONDS
    write_new(registry/'claim.json',dict(utc=rp.utc(),plan_sha256=expected_sha))
    write_new(out/'claim.json',dict(utc=rp.utc(),plan_sha256=expected_sha))
    device=recorded_device()(q['adb'],out/'commands')
    result=dict(status='failed',stage='preflight',utc_start=rp.utc(),
                plan_sha256=expected_sha,remote_apk=REMOTE,
                remote_sha256=None,installed_apk_sha256=None)
    try:
        device.deadline=min(start+BUDGET['preflight'],hard-BUDGET['cleanup']-BUDGET['reserve'])
        pre=apk.preflight(device,dict(q,_plan_file=str(path)),out/'preflight')
        result['candidate']=pre['candidate'];result['installed_before']=pre['installed']
        hardware=device.call('shell','getprop','ro.serialno',timeout=3).stdout.decode().strip()
        require(hardware==q['device_hardware_serial'],'hardware serial mismatch')
        legacy.require_stopped(device)
        battery=device.call('shell','dumpsys','battery',timeout=15).stdout.decode(errors='replace')
        legacy.battery_gate(q,battery,True)
        thermal=device.call('shell','dumpsys','thermalservice',timeout=15).stdout
        require(re.search(rb'Thermal Status:\s*0\b',thermal),'thermal gate')
        shared.screen_snapshot(device,out,'before_install',q['screen_contract'],settings=True)
        result['preflight']='compatible_and_environment_passed'
        result['stage']='remote_sha'
        require(hard-time.monotonic()>sum(BUDGET[k] for k in
                ('remote_sha','install','post_identity','cleanup','reserve')),
                'insufficient remaining time for stages')
        device.deadline=min(time.monotonic()+BUDGET['remote_sha'],
                            hard-sum(BUDGET[k] for k in ('install','post_identity','cleanup','reserve')))
        result['remote_sha256']=remote_hash(device,REMOTE)
        require(result['remote_sha256']==APK_SHA,'remote APK SHA mismatch')
        if pre['installed']==pre['candidate']:
            result['installation']='skipped_exact_installed_apk'
        else:
            result['stage']='package_install'
            require(hard-time.monotonic()>sum(BUDGET[k] for k in
                    ('install','post_identity','cleanup','reserve')),
                    'insufficient install/verification/cleanup reserve')
            device.deadline=min(time.monotonic()+BUDGET['install'],
                                hard-sum(BUDGET[k] for k in ('post_identity','cleanup','reserve')))
            write_new(out/'install_attempt.json',dict(utc=rp.utc(),method='pm install -r',
                                                     remote_apk=REMOTE,apk_sha256=APK_SHA))
            response=device.call('shell','pm','install','-r',REMOTE,timeout=120)
            require(re.search(rb'(?m)^Success\s*$',response.stdout),'package manager did not report Success')
            result['installation']='package_manager_returned_success'
        result['stage']='post_identity'
        device.deadline=min(time.monotonic()+BUDGET['post_identity'],
                            hard-BUDGET['cleanup']-BUDGET['reserve'])
        result['installed_apk_sha256']=recovery.installed_hash(device,pre['candidate'])
        require(result['installed_apk_sha256']==APK_SHA,'installed APK differs from candidate')
        result['status']='verified'
    except BaseException as error:
        result.update(error=repr(error),stop_utc=rp.utc())
        if device.last_identity and result['stage'] != 'post_identity':
            device.deadline=min(time.monotonic()+BUDGET['post_identity'],hard-BUDGET['cleanup'])
            try:result['post_failure_installed_apk_sha256']=recovery.installed_hash(device,q['candidate'])
            except Exception as query_error:result['post_failure_query_error']=repr(query_error)
    finally:
        if device.last_identity:
            try:result['cleanup']=install_only_cleanup(device,hard)
            except Exception as error:result.update(status='failed',cleanup=dict(status='unconfirmed',error=repr(error)))
        else:result['cleanup']=dict(status='not_attempted_unidentified_device')
        result.update(utc_end=rp.utc(),elapsed_seconds=time.monotonic()-start,
                      adb_commands_used=device.sequence,pull_attempts=device.pulls,
                      push_attempts=0,install_attempts=device.installs,
                      launch_attempts=0,warmup_attempts=0,inference_attempts=0)
        result['evidence_hashes']={str(f.resolve()):p.digest(f) for f in out.rglob('*') if f.is_file()}
        write_new(out/'receipt.json',result)
        write_new(registry/('complete.json' if result['status']=='verified' else 'stopped.json'),
                  dict(utc=rp.utc(),status=result['status'],receipt=str(out/'receipt.json')))
    require(result['status']=='verified','install-only run stopped; no retry')
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='action',required=True)
    prep=sub.add_parser('prepare')
    for name in ('bundle','observed-receipt','observed-plan','parent-plan'):
        prep.add_argument('--'+name,required=True)
    for action in ('check','run'):
        q=sub.add_parser(action);q.add_argument('--plan',required=True)
        if action=='run':
            q.add_argument('--expected-sha256',required=True)
            q.add_argument('--approved',action='store_true')
    args=parser.parse_args()
    if args.action=='prepare':result=prepare(args.bundle,args.observed_receipt,
                                             args.observed_plan,args.parent_plan)
    elif args.action=='check':result=check(args.plan)
    else:result=run(args.plan,args.expected_sha256,args.approved)
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
