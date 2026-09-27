"""Prepare and (only after separate approval) run one bounded, observed APK push.

No install, collection, retries, server restart, remote deletion or rename.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
import json
from pathlib import Path
import re
import socket
import time

from tools import d1_arrival_plan as p
from tools import d1_recorded_process as rp
from tools.d1_apk_push_readonly import parse_devices, parse_stat, require, write_new


ID='ENERGY-AP-PUSH-OBSERVE-01'
REMOTE='/data/local/tmp/d1check-energy-ap-push-observe-01.apk'
APK_SHA='b273f74b9b4eb91227db1ec2f7ef260d3d0f2c813790eaf4aedf30af98a114cf'
APK_BYTES=106092116
PROBE_SECONDS=(20,40,60,80,100,120,140,160)


def parse_available_bytes(output):
    rows=output.decode(errors='replace').strip().splitlines()
    require(len(rows)>=2 and 'Available' in rows[0], 'storage output unavailable')
    columns=rows[-1].split()
    require(len(columns)>=4 and columns[3].isdigit(), 'storage available count unavailable')
    return int(columns[3])*1024


def progress_classification(samples):
    valid=[s for s in samples if isinstance(s.get('bytes'),int)]
    rises=sum(b['bytes']>a['bytes'] for a,b in zip(valid,valid[1:]))
    if rises:
        return 'remote_size_increased_observed'
    if len(valid)>=4 and valid[-1]['seconds']-valid[0]['seconds']>=60 and \
            len({x['bytes'] for x in valid})==1:
        return 'remote_size_plateau_observed_not_proof_of_no_transfer'
    return 'progress_unobserved'


def prepare(bundle, apk, adb, readonly_receipt, readonly_plan):
    bundle,apk,adb,readonly_receipt,readonly_plan=map(
        Path,(bundle,apk,adb,readonly_receipt,readonly_plan))
    require(not bundle.exists(),'new bundle required')
    source=Path(__file__).resolve().parent.parent
    require(p.digest(apk)==APK_SHA,'APK changed')
    previous=p.read(readonly_receipt)
    identity=p.read(readonly_plan)
    require(p.digest(readonly_plan)==previous['plan_sha256'] and
            identity['experiment_id']=='ENERGY-AP-PUSH-READONLY-01',
            'readonly identity source changed')
    require(previous['status']=='completed_read_only' and all(
        x['status']=='stat_failed' and 'No such file or directory' in x['stderr']
        for x in previous['remote'].values()),'readonly result does not justify new transfer candidate')
    plan=dict(protocol='energy-ap-push-observed-v1',experiment_id=ID,
              status='PC_READY_NOT_APPROVED_DEVICE_UNVERIFIED',
              readonly_receipt=str(readonly_receipt.resolve()),
              readonly_receipt_sha256=p.digest(readonly_receipt),
              readonly_plan=str(readonly_plan.resolve()),
              readonly_plan_sha256=p.digest(readonly_plan),
              apk=str(apk.resolve()),apk_sha256=APK_SHA,apk_bytes=apk.stat().st_size,
              adb=str(adb.resolve()),adb_sha256=p.digest(adb),adb_version='37.0.1-15733141',
              source_sha256={name:p.digest(source/name) for name in
                             ('tools/d1_apk_push_observed.py','tools/d1_apk_push_readonly.py',
                              'tools/d1_arrival_plan.py','tools/d1_recorded_process.py')},
              output_root=str((bundle.parent/'energy_ap_push_observed_run_v1').resolve()),
              remote_apk=REMOTE,model=identity['device_model'],
              fingerprint=identity['device_fingerprint'],
              hardware_serial=identity['device_hardware_serial'],
              preflight_commands=6,preflight_each_timeout_seconds=5,
              push_cap=1,push_timeout_seconds=180,probe_interval_seconds=20,
              probe_schedule_seconds=list(PROBE_SECONDS),probe_cap=8,probe_each_timeout_seconds=3,
              final_stat_cap=1,final_stat_timeout_seconds=5,
              final_sha_cap=1,final_sha_timeout_seconds=120,
              total_adb_command_cap=17,total_seconds=420,cleanup_reserve_seconds=25,
              install_cap=0,retry_cap=0,replacement_cap=0,inference_cap=0,
              interpretation='diagnostic only; concurrent exact-path stat may perturb push; no remote SHA means no verified transfer')
    bundle.mkdir(parents=True)
    write_new(bundle/'diagnosis_plan.json',plan)
    return check(bundle/'diagnosis_plan.json')


def check(path):
    path=Path(path);q=p.read(path)
    require(q['protocol']=='energy-ap-push-observed-v1' and q['experiment_id']==ID,'namespace')
    require(q['status']=='PC_READY_NOT_APPROVED_DEVICE_UNVERIFIED','status changed')
    require(q['remote_apk']==REMOTE and q['probe_schedule_seconds']==list(PROBE_SECONDS),'probe/remote changed')
    require((q['preflight_commands'],q['preflight_each_timeout_seconds'],q['push_cap'],
             q['push_timeout_seconds'],q['probe_cap'],q['probe_each_timeout_seconds'],
             q['final_stat_cap'],q['final_stat_timeout_seconds'],q['final_sha_cap'],
             q['final_sha_timeout_seconds'],q['total_adb_command_cap'],q['total_seconds'],
             q['cleanup_reserve_seconds'],q['install_cap'],q['retry_cap'],q['replacement_cap'],q['inference_cap'])==
            (6,5,1,180,8,3,1,5,1,120,17,420,25,0,0,0,0),'budget changed')
    require(Path(q['output_root']).resolve()==path.resolve().parent.parent/'energy_ap_push_observed_run_v1',
            'output changed')
    require(not Path(q['output_root']).exists(),'diagnosis consumed')
    require(p.digest(q['readonly_receipt'])==q['readonly_receipt_sha256'],'readonly evidence changed')
    if 'readonly_plan' in q:
        require(p.digest(q['readonly_plan'])==q['readonly_plan_sha256'] and
                p.read(q['readonly_plan'])['experiment_id']=='ENERGY-AP-PUSH-READONLY-01',
                'readonly identity source changed')
    require(q['apk_bytes']==APK_BYTES and Path(q['apk']).stat().st_size==q['apk_bytes'] and
            p.digest(q['apk'])==q['apk_sha256']==APK_SHA,
            'APK changed')
    require(p.digest(q['adb'])==q['adb_sha256'],'adb changed')
    source=Path(__file__).resolve().parent.parent
    require(set(q['source_sha256'])=={'tools/d1_apk_push_observed.py',
            'tools/d1_apk_push_readonly.py','tools/d1_arrival_plan.py',
            'tools/d1_recorded_process.py'},'source manifest changed')
    require(all(p.digest(source/name)==sha for name,sha in q['source_sha256'].items()),'source changed')
    return dict(status=q['status'],plan_sha256=p.digest(path),push_cap=1,install_cap=0,
                total_adb_command_cap=17,total_seconds=420,device_calls=0)


def run(path, expected_sha, approved):
    require(approved and p.digest(path)==expected_sha,'separate frozen-plan approval required')
    check(path);q=p.read(path);out=Path(q['output_root']);out.mkdir()
    start=time.monotonic();hard=start+q['total_seconds']
    receipt=dict(status='failed',started_utc=rp.utc(),plan_sha256=expected_sha,commands=[],
                 probes=[],push_attempts=0,install_attempts=0,inference_attempts=0)
    write_new(out/'claim.json',dict(utc=rp.utc(),plan_sha256=expected_sha))
    serial=None
    def call(args,limit,folder,allow_nonzero=False):
        require(len(receipt['commands'])+receipt['push_attempts']<q['total_adb_command_cap'],'ADB command cap')
        remaining=hard-time.monotonic()-25
        require(remaining>5,'cleanup/evidence reserve exhausted')
        cmd=[q['adb']]+(['-s',serial] if serial else [])+args
        display=['adb']+(['-s','<verified-A24>'] if serial else [])+args
        result=rp.run(cmd,out/folder,min(limit,remaining),display,root_only=True)
        receipt['commands'].append(dict(folder=folder,args=args,status=result['status'],
                                        elapsed_seconds=result['elapsed_seconds']))
        require(result['status'] in ('returned','nonzero_exit'),'query timeout/host error')
        require(allow_nonzero or result['returncode']==0,'query nonzero exit')
        path_out=out/folder
        return result,(path_out/'stdout.bin').read_bytes(),(path_out/'stderr.bin').read_bytes()
    try:
        with socket.create_connection(('127.0.0.1',5037),timeout=1):pass
        _,stdout,_=call(['devices','-l'],5,'commands/00')
        serial=parse_devices(stdout);receipt['transport']=serial
        for index,(prop,expected) in enumerate((('ro.product.model',q['model']),
                ('ro.build.fingerprint',q['fingerprint']),('ro.serialno',q['hardware_serial'])),1):
            _,stdout,_=call(['shell','getprop',prop],5,f'commands/{index:02d}')
            require(stdout.decode(errors='replace').strip()==expected,'A24 identity mismatch')
        probe,_,stderr=call(['shell','stat','-c','%s:%Y',REMOTE],5,'commands/04',True)
        require(probe['returncode']!=0 and b'No such file or directory' in stderr,'remote target already present')
        _,stdout,_=call(['shell','df','-k','/data/local/tmp'],5,'commands/05')
        receipt['storage_stdout']=stdout.decode(errors='replace')[:1000]
        receipt['available_bytes']=parse_available_bytes(stdout)
        require(receipt['available_bytes']>q['apk_bytes'],'insufficient remote storage')
        require(hard-time.monotonic()>180+120+25,'insufficient full push/final verification budget')
        receipt['push_attempts']=1
        push_folder=out/'push'
        push_start=time.monotonic()
        with ThreadPoolExecutor(max_workers=1) as executor:
            future=executor.submit(rp.run,[q['adb'],'-s',serial,'push',q['apk'],REMOTE],
                                   push_folder,180,['adb','-s','<verified-A24>','push','<candidate-apk>',REMOTE],
                                   root_only=True)
            for index,offset in enumerate(PROBE_SECONDS):
                wait=max(0,push_start+offset-time.monotonic())
                try:future.result(timeout=wait);break
                except FutureTimeout:pass
                if future.done():break
                result,stdout,stderr=call(['shell','stat','-c','%s:%Y',REMOTE],3,
                                          f'probes/{index:02d}',True)
                row=dict(seconds=round(time.monotonic()-push_start,3),status=result['status'],
                         stderr_bytes=(push_folder/'stderr.bin').stat().st_size if
                         (push_folder/'stderr.bin').exists() else None)
                if result['returncode']==0:
                    try:row.update(parse_stat(stdout))
                    except ValueError:row['status']='malformed_stat'
                else:row['stat_error']=stderr.decode(errors='replace')[:200]
                receipt['probes'].append(row)
            push=future.result(timeout=max(1,hard-time.monotonic()-145))
        receipt['push']=push
        receipt['progress_classification']=progress_classification(receipt['probes'])
        # Even after timeout, final exact-path state is checked once; client success alone is insufficient.
        result,stdout,stderr=call(['shell','stat','-c','%s:%Y',REMOTE],5,'final_stat',True)
        if result['returncode']==0:
            receipt['final_remote']=parse_stat(stdout)
            if receipt['final_remote']['bytes']==q['apk_bytes']:
                _,stdout,_=call(['shell','sha256sum',REMOTE],120,'final_sha')
                tokens=stdout.decode(errors='replace').split()
                require(tokens and re.fullmatch(r'[0-9a-f]{64}',tokens[0]),'final SHA unavailable')
                receipt['final_remote']['sha256']=tokens[0]
                receipt['status']='transfer_verified' if tokens[0]==APK_SHA else 'hash_mismatch'
            else:receipt['status']='partial_file_observed'
        else:
            receipt['final_remote']=dict(status='stat_failed',stderr=stderr.decode(errors='replace')[:300])
            receipt['status']='remote_absent_or_unavailable'
    except BaseException as error:
        receipt['error']=repr(error)
    finally:
        receipt.update(ended_utc=rp.utc(),elapsed_seconds=time.monotonic()-start,
                       adb_commands_used=len(receipt['commands'])+receipt['push_attempts'],
                       host_cleanup='each launched ADB client bounded/reaped by recorded_process; shared daemon not owned')
        write_new(out/'receipt.json',receipt)
    return receipt


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='action',required=True)
    prep=sub.add_parser('prepare')
    for key in ('bundle','apk','adb','readonly-receipt','readonly-plan'):
        prep.add_argument('--'+key,required=True)
    for name in ('check','run'):
        q=sub.add_parser(name);q.add_argument('--plan',required=True)
        if name=='run':q.add_argument('--expected-sha256',required=True);q.add_argument('--approved',action='store_true')
    a=parser.parse_args()
    if a.action=='prepare':result=prepare(a.bundle,a.apk,a.adb,a.readonly_receipt,a.readonly_plan)
    elif a.action=='check':result=check(a.plan)
    else:result=run(a.plan,a.expected_sha256,a.approved)
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
