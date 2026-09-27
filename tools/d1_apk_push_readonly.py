"""One-shot, bounded read-only inspection of two previously attempted APK staging paths."""
import argparse
import json
from pathlib import Path
import re
import socket
import time

from tools import d1_arrival_plan as p
from tools import d1_recorded_process as rp


EXPERIMENT = 'ENERGY-AP-PUSH-READONLY-01'
EXPECTED_APK = 'b273f74b9b4eb91227db1ec2f7ef260d3d0f2c813790eaf4aedf30af98a114cf'
PATHS = (
    '/data/local/tmp/d1check-energy-ap-state-collect-03.apk',
    '/data/local/tmp/d1check-energy-ap-deploy-recovery-01/candidate.apk',
)
COMMANDS = (('devices -l', 5), ('getprop ro.product.model', 5),
            ('getprop ro.build.fingerprint', 5), ('getprop ro.serialno', 5),
            ('stat old %s:%Y', 5), ('stat recovery %s:%Y', 5),
            ('df -k /data/local/tmp', 5), ('sha256sum old if full-size', 120),
            ('sha256sum recovery if full-size', 120))


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def write_new(path, value):
    with Path(path).open('x', encoding='utf-8') as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.write('\n')


def prepare(bundle, apk, old_result, recovery_result, adb, identity_plan):
    bundle, apk, old_result, recovery_result, adb, identity_plan = map(
        Path, (bundle, apk, old_result, recovery_result, adb, identity_plan))
    require(not bundle.exists(), 'new diagnostic bundle required')
    require(p.digest(apk) == EXPECTED_APK, 'candidate APK changed')
    old, new = p.read(old_result), p.read(recovery_result)
    identity = p.read(identity_plan)
    require(identity['experiment_id'] == 'ENERGY-AP-STATE-COLLECT-03', 'identity source changed')
    require(old['status'] == new['status'] == 'timeout', 'prior failures changed')
    require(old['timeout_seconds'] == new['timeout_seconds'] == 120, 'prior timeout changed')
    source = Path(__file__).resolve().parent.parent
    plan = dict(protocol='energy-ap-push-readonly-v1', experiment_id=EXPERIMENT,
                status='READ_ONLY_APPROVED_DEVICE_UNVERIFIED',
                apk=str(apk.resolve()), apk_bytes=apk.stat().st_size, apk_sha256=EXPECTED_APK,
                prior_evidence={str(f.resolve()): p.digest(f) for f in (old_result, recovery_result)},
                identity_plan=str(identity_plan.resolve()), identity_plan_sha256=p.digest(identity_plan),
                adb=str(adb.resolve()), adb_sha256=p.digest(adb), adb_version='37.0.1-15733141',
                code_sha256={name:p.digest(source/name) for name in
                             ('tools/d1_apk_push_readonly.py', 'tools/d1_recorded_process.py')},
                output_root=str((bundle.parent/'energy_ap_push_readonly_run_v1').resolve()),
                device_fingerprint=identity['device_fingerprint'],
                device_hardware_serial=identity['device_hardware_serial'], device_model='SM-A245N',
                remote_paths=list(PATHS), commands=[dict(name=n,timeout_seconds=t) for n,t in COMMANDS],
                adb_command_cap=9, query_seconds=275, administrative_reserve_seconds=25,
                total_seconds=300, transfer_cap=0, install_cap=0, retry_cap=0,
                interpretation='current remote state only; not timeout-time state')
    bundle.mkdir(parents=True)
    write_new(bundle/'diagnosis_plan.json', plan)
    return check(bundle/'diagnosis_plan.json')


def check(path):
    path = Path(path)
    plan = p.read(path)
    require(plan['protocol']=='energy-ap-push-readonly-v1' and plan['experiment_id']==EXPERIMENT,
            'namespace')
    require(plan['remote_paths']==list(PATHS), 'remote path changed')
    require(plan['commands']==[dict(name=n,timeout_seconds=t) for n,t in COMMANDS], 'command list changed')
    require((plan['adb_command_cap'],plan['query_seconds'],plan['administrative_reserve_seconds'],
             plan['total_seconds'],plan['transfer_cap'],plan['install_cap'],plan['retry_cap']) ==
            (9,275,25,300,0,0,0), 'budget changed')
    require(Path(plan['output_root']).resolve()==path.resolve().parent.parent/'energy_ap_push_readonly_run_v1',
            'output scope changed')
    require(not Path(plan['output_root']).exists(), 'diagnosis already consumed')
    require(Path(plan['apk']).stat().st_size==plan['apk_bytes'] and
            p.digest(plan['apk'])==plan['apk_sha256']==EXPECTED_APK, 'APK identity')
    require(p.digest(plan['adb'])==plan['adb_sha256'], 'adb executable changed')
    require(all(p.digest(f)==sha for f,sha in plan['prior_evidence'].items()), 'prior evidence changed')
    if 'identity_plan' in plan:
        require(p.digest(plan['identity_plan'])==plan['identity_plan_sha256'], 'identity source changed')
    source=Path(__file__).resolve().parent.parent
    require(all(p.digest(source/name)==sha for name,sha in plan['code_sha256'].items()), 'code changed')
    return dict(status=plan['status'],plan_sha256=p.digest(path),adb_commands_max=9,
                total_seconds=300,device_calls=0)


def parse_stat(output):
    match=re.fullmatch(r'(\d+):(\d+)', output.decode(errors='replace').strip())
    require(match is not None, 'remote stat unavailable')
    return dict(bytes=int(match[1]),mtime_epoch_seconds=int(match[2]))


def parse_devices(output):
    lines=output.decode(errors='replace').splitlines()[1:]
    online=[x.split() for x in lines if len(x.split())>=2 and x.split()[1]=='device']
    require(len(online)==1 and online[0][0].startswith('adb-') and
            online[0][0].endswith('._adb-tls-connect._tcp'), 'single wireless A24 transport required')
    return online[0][0]


def run(path, expected_sha):
    require(p.digest(path)==expected_sha, 'frozen plan SHA required')
    check(path)
    plan=p.read(path)
    output=Path(plan['output_root']);output.mkdir()
    start=time.monotonic();deadline=start+300
    receipt=dict(status='failed',started_utc=rp.utc(),plan_sha256=expected_sha,commands=[],
                 remote={},transfer_attempts=0,install_attempts=0,inference_attempts=0)
    write_new(output/'claim.json',dict(utc=rp.utc(),plan_sha256=expected_sha))
    serial=None
    def call(args, limit, allow_nonzero=False):
        require(len(receipt['commands'])<9, 'ADB command cap')
        left=deadline-time.monotonic()
        require(left>3, 'diagnosis wall deadline')
        index=len(receipt['commands'])
        cmd=[plan['adb']]+(['-s',serial] if serial else [])+args
        display=['adb']+(['-s','<verified-A24>'] if serial else [])+args
        folder=output/'commands'/f'{index:02d}'
        result=rp.run(cmd,folder,min(limit,left-3),display,root_only=True)
        receipt['commands'].append(dict(index=index,args=args,status=result['status'],
                                        elapsed_seconds=result['elapsed_seconds'],
                                        result_file=str(folder/'result.json')))
        require(result['status'] in ('returned','nonzero_exit'), 'ADB query timeout or host failure')
        require(allow_nonzero or result['returncode']==0, 'ADB query nonzero exit')
        return result, (folder/'stdout.bin').read_bytes(), (folder/'stderr.bin').read_bytes()
    try:
        # A socket probe does not start or restart the shared ADB daemon.
        with socket.create_connection(('127.0.0.1',5037),timeout=1):
            pass
        _,stdout,_=call(['devices','-l'],5)
        serial=parse_devices(stdout)
        receipt['transport']=serial
        for prop,expected in (('ro.product.model',plan['device_model']),
                              ('ro.build.fingerprint',plan['device_fingerprint']),
                              ('ro.serialno',plan['device_hardware_serial'])):
            _,stdout,_=call(['shell','getprop',prop],5)
            require(stdout.decode(errors='replace').strip()==expected,'selected A24 identity mismatch')
        for label,remote in zip(('old_collection','deployment_recovery'),PATHS):
            result,stdout,stderr=call(['shell','stat','-c','%s:%Y',remote],5,allow_nonzero=True)
            if result['returncode']:
                receipt['remote'][label]=dict(status='stat_failed',stderr=stderr.decode(errors='replace')[:500])
            else:
                receipt['remote'][label]=dict(status='stat_returned',**parse_stat(stdout))
        _,stdout,_=call(['shell','df','-k','/data/local/tmp'],5)
        receipt['storage_stdout']=stdout.decode(errors='replace')[:1000]
        for label,remote in zip(('old_collection','deployment_recovery'),PATHS):
            row=receipt['remote'][label]
            if row.get('bytes') != plan['apk_bytes']:
                row['sha256_status']='not_queried_size_not_candidate'
                continue
            _,stdout,_=call(['shell','sha256sum',remote],120)
            tokens=stdout.decode(errors='replace').split()
            require(tokens and re.fullmatch(r'[0-9a-f]{64}',tokens[0]),'remote SHA unavailable')
            row.update(sha256=tokens[0],sha256_status='matches_candidate' if tokens[0]==EXPECTED_APK else 'mismatch')
        receipt['status']='completed_read_only'
    except BaseException as error:
        receipt['error']=repr(error)
    finally:
        receipt.update(ended_utc=rp.utc(),elapsed_seconds=time.monotonic()-start,
                       commands_used=len(receipt['commands']))
        write_new(output/'receipt.json',receipt)
    return receipt


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='action',required=True)
    prep=sub.add_parser('prepare')
    for name in ('bundle','apk','old-result','recovery-result','adb','identity-plan'):
        prep.add_argument('--'+name,required=True)
    for name in ('check','run'):
        q=sub.add_parser(name);q.add_argument('--plan',required=True)
        if name=='run':q.add_argument('--expected-sha256',required=True)
    a=parser.parse_args()
    if a.action=='prepare':result=prepare(a.bundle,a.apk,a.old_result,a.recovery_result,a.adb,a.identity_plan)
    elif a.action=='check':result=check(a.plan)
    else:result=run(a.plan,a.expected_sha256)
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
