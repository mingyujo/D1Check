"""PC preparation and explicitly approved one-shot staged install + collection.

No device operation in prepare/check. Existing terminated plans are never resumed.
"""
import argparse
import copy
import json
from pathlib import Path
import re
import subprocess
import time
import uuid
from tools import d1_arrival_collection as c
from tools import d1_recorded_process as rp

RECOVERY='ARRIVAL-INSTALL-RECOVERY-01'
COLLECTION='ARRIVAL-COLLECT-02'
TOTAL=6090  # recovery600 + development2745 + confirmation2745; PC freeze also inside wall.


def prepare(old_path, output, revision=1, prior_recovery=None):
    old_path=Path(old_path);output=Path(output)
    c.v.require(not output.exists(),'new output required')
    c.v.require(revision in (1,2), 'only explicitly supported recovery revisions')
    recovery_id,collection_id=RECOVERY,COLLECTION
    lineage=None
    if revision==2:
        c.v.require(prior_recovery is not None,'closed predecessor required')
        prior_path=Path(prior_recovery);prior=c.p.read(prior_path)
        c.v.require(prior['experiment_id']==RECOVERY,'wrong predecessor')
        receipt=Path(prior['output_root'])/'receipt.json'
        stopped=Path(prior['workflow_root'])/'stopped.json'
        c.v.require(c.p.read(receipt)['status']=='failed' and c.p.read(stopped)['status']=='stopped_no_resume','predecessor not closed')
        lineage={str(f.resolve()):c.p.digest(f) for f in (prior_path,receipt,stopped,Path(prior['collection_plan']))}
        recovery_id,collection_id='ARRIVAL-INSTALL-RECOVERY-02','ARRIVAL-COLLECT-03'
    old=c.p.read(old_path)
    c.v.require(old['experiment_id']==c.EXPERIMENT,'wrong parent')
    c.v.require(c.cal.apk_sources(c.p.read(old['build_receipt'])['source_code'])==c.cal.apk_sources(c.identity()),'APK source changed; rebuild separately')
    c.v.require(c.p.digest(old['apk_path'])==old['apk_sha256'],'APK bytes changed')
    output.mkdir(parents=True);(output/'manifests').mkdir()
    plan=copy.deepcopy(old)
    plan.update(experiment_id=collection_id,source_code=c.identity(),install_cap=0,
        installation_contract='recovery-verified-only-v1',supersedes_plan_sha256=c.p.digest(old_path),
        registry=str(output.parent/'collection_execution_registry'/collection_id),
        output_root=str(output.parent/f'integrated_collection_run_v{revision+1}'),
        workflow_root=str(output.parent/f'collection_recovery_workflow_v{revision}'),
        recovery_receipt=str(output.parent/f'install_recovery_run_v{revision}/receipt.json'))
    for e in plan['entries']:
        m=c.p.read(old_path.parent/e['manifest'])
        sid=str(uuid.uuid5(uuid.NAMESPACE_URL,f"{collection_id}/{plan['seed']}/{e['phase']}/{e['condition']}"))
        m.update(session_id=sid,experiment_id=collection_id)
        for spec in m['models'].values():spec['identity']['session_id']=sid
        for key in ('requests','warmup_requests'):
            for i,q in enumerate(m[key]):q['request_id']=str(uuid.uuid5(uuid.UUID(sid),f'{key}/{i}'))
        f=output/'manifests'/f'{sid}.json';c.cal.write_new(f,m)
        e.update(session_id=sid,manifest='manifests/'+f.name,manifest_sha256=c.p.digest(f))
    cf=output/'collection_plan.json';c.cal.write_new(cf,plan)
    recovery=dict(protocol='collection-install-recovery-v1',experiment_id=recovery_id,status='PREPARED_NOT_APPROVED',
        collection_plan=str(cf.resolve()),collection_plan_sha256=c.p.digest(cf),
        parent_terminated_plan=str(old_path.resolve()),parent_terminated_plan_sha256=c.p.digest(old_path),
        output_root=str(output.parent/f'install_recovery_run_v{revision}'),
        workflow_root=str(output.parent/f'collection_recovery_workflow_v{revision}'),source_code=c.identity(),
        recovery_seconds=600,total_seconds=TOTAL,install_cap=1,transfer_cap=1,retry_cap=0,replacement_cap=0,additional_cap=0,
        session_cap=12,request_cap=48,warmup_cap=96,explicit_inference_cap=144,
        recovery_budgets=dict(preflight=200,transfer_and_remote_hash=150,package_install_and_client_reap=125,
                              post_identity=60,cleanup=45,administrative_reserve=20),
        method='adb push; remote sha256; adb shell pm install -r; installed APK hash; no streaming retry',
        skip_rule='only exact candidate APK/package/version/signer proven by preflight plus post SHA gate',
        remote_apk=f'/data/local/tmp/d1check-{recovery_id.lower()}/candidate.apk',
        experiment_ready=False)
    if lineage:recovery['closed_predecessor_evidence']=lineage
    c.cal.write_new(output/'recovery_plan.json',recovery)
    return check(output/'recovery_plan.json')


def check(path):
    r=c.p.read(path)
    pairs={RECOVERY:COLLECTION,'ARRIVAL-INSTALL-RECOVERY-02':'ARRIVAL-COLLECT-03'}
    c.v.require(r['protocol']=='collection-install-recovery-v1' and r['experiment_id'] in pairs,'namespace')
    if r['experiment_id']=='ARRIVAL-INSTALL-RECOVERY-02':
        c.v.require(len(r.get('closed_predecessor_evidence',{}))==4,'predecessor evidence missing')
        for name,sha in r['closed_predecessor_evidence'].items():c.v.require(c.p.digest(name)==sha,'predecessor evidence changed')
    c.v.require(r['source_code']==c.identity() and c.p.digest(r['collection_plan'])==r['collection_plan_sha256'],'identity')
    c.v.require((r['recovery_seconds'],r['total_seconds'],r['install_cap'],r['transfer_cap'],r['session_cap'],r['request_cap'],r['warmup_cap'],r['explicit_inference_cap'])==(600,TOTAL,1,1,12,48,96,144),'budget')
    c.v.require(all(r[k]==0 for k in ('retry_cap','replacement_cap','additional_cap')),'no retries')
    c.v.require(r['recovery_budgets']==dict(preflight=200,transfer_and_remote_hash=150,package_install_and_client_reap=125,post_identity=60,cleanup=45,administrative_reserve=20),'time allocation')
    c.v.require(r['remote_apk']==f"/data/local/tmp/d1check-{r['experiment_id'].lower()}/candidate.apk",'remote scope')
    pc=c.check(r['collection_plan']);plan=c.p.read(r['collection_plan'])
    c.v.require(plan['experiment_id']==pairs[r['experiment_id']] and plan['recovery_receipt']==str(Path(r['output_root'])/'receipt.json'),'collection binding')
    c.v.require(plan['workflow_root']==r['workflow_root'],'workflow binding')
    if r['experiment_id']=='ARRIVAL-INSTALL-RECOVERY-02':
        base=Path(path).resolve().parent.parent
        for value,expected in ((r['output_root'],base/'install_recovery_run_v2'),
            (r['workflow_root'],base/'collection_recovery_workflow_v2'),
            (plan['output_root'],base/'integrated_collection_run_v3'),
            (plan['registry'],base/'collection_execution_registry/ARRIVAL-COLLECT-03')):
            c.v.require(Path(value).resolve()==expected,'new plan output/registry scope')
    from tools import d1_apk_identity as apk
    for key,digest in plan['apk_preflight']['tool_sha256'].items():
        c.v.require(c.p.digest(plan['apk_preflight']['toolchain'][key])==digest,'signature tool changed')
    candidate=apk.inspect(plan['apk_path'],plan['apk_preflight']['toolchain'])
    c.v.require(candidate==plan['apk_preflight']['candidate'],'PC signature identity')
    return dict(status='PC_READY_NOT_APPROVED',recovery_plan_sha256=c.p.digest(path),collection=pc,
                recovery_seconds=600,total_seconds=TOTAL,device_calls=0)


def require_receipt(plan, collection_hash):
    r=c.p.read(plan['recovery_receipt'])
    c.v.require(r['status']=='verified' and r['collection_plan_sha256']==collection_hash and
                r['installed_apk_sha256']==plan['apk_sha256'] and r['cleanup']['status']=='completed','installation not verified')
    # Receipt binds the exact before/after evidence, not just a success flag.
    for path,sha in r['evidence_hashes'].items():c.v.require(c.p.digest(path)==sha,'recovery evidence changed')


def device_class():
    # Lazy import keeps PC prepare/check off the device path.
    from tools.d1_arrival_device import Device
    class RecordedDevice(Device):
        def __init__(self, adb, serial, root):
            super().__init__(adb,serial);self.root=Path(root);self.sequence=0;self.last_identity=None
        def identify(self, fingerprint):
            result=super().identify(fingerprint);self.last_identity=result;return result
        def call(self,*args,timeout=30,check=True):
            remaining=self.deadline-time.monotonic()
            c.v.require(remaining>5,'insufficient command/reap time')
            folder=self.root/f'{self.sequence:03d}';self.sequence+=1
            # Only fixed experiment arguments enter this API. No keystore/password argv.
            command=[self.adb,'-s',self.serial]+list(map(str,args))
            display=['adb','-s','<approved-A24>']+list(map(str,args))
            result=rp.run(command,folder,min(timeout,remaining-5),display)
            stdout=(folder/'stdout.bin').read_bytes() if (folder/'stdout.bin').exists() else b''
            stderr=(folder/'stderr.bin').read_bytes() if (folder/'stderr.bin').exists() else b''
            if result['status'] in ('timeout','host_interrupted','host_command_error'):
                raise RuntimeError(f"recorded command {self.sequence-1}: {result['status']}; no retry")
            if check and result['returncode']!=0:raise RuntimeError(f'recorded command {self.sequence-1}: nonzero exit')
            return subprocess.CompletedProcess(display,result['returncode'],stdout,stderr)
    return RecordedDevice


def installed_hash(device, expected):
    response=device.call('shell','pm','path',expected['package'],timeout=10)
    lines=response.stdout.decode().splitlines()
    c.v.require(len(lines)==1 and re.fullmatch(r'package:/data/app/[A-Za-z0-9_+./=~-]+/base\.apk',lines[0].strip()),'installed base path unknown')
    response=device.call('shell','sha256sum',lines[0].strip()[8:],timeout=10)
    tokens=response.stdout.decode().split()
    c.v.require(tokens and re.fullmatch('[a-f0-9]{64}',tokens[0]),'installed hash unavailable')
    return tokens[0]


def recover(path, adb, serial, overall_deadline):
    from tools import d1_arrival_device as legacy
    from tools import d1_arrival_timing_calibration_device as shared
    from tools import d1_apk_identity as apk
    r=c.p.read(path);plan=c.p.read(r['collection_plan']);out=Path(r['output_root'])
    c.v.require(not out.exists(),'recovery consumed; no retry')
    out.mkdir();start=time.monotonic();hard=min(start+600,overall_deadline)
    c.cal.write_new(out/'claim.json',dict(utc=rp.utc(),mono=start,recovery_plan_sha256=c.p.digest(path)))
    device=device_class()(adb,serial,out/'commands');device.deadline=min(start+200,hard-45)
    result=dict(status='failed',stage='preflight',utc_start=rp.utc(),install_attempts=0,transfer_attempts=0,
                collection_plan_sha256=r['collection_plan_sha256'],installed_apk_sha256=None)
    try:
        pre=apk.preflight(device,dict(plan,_plan_file=r['collection_plan']),out/'preflight')
        legacy.require_stopped(device)
        battery=device.call('shell','dumpsys','battery').stdout.decode();legacy.battery_gate(plan,battery,True)
        thermal=device.call('shell','dumpsys','thermalservice').stdout
        c.v.require(re.search(rb'Thermal Status:\s*0\b',thermal),'thermal gate')
        shared.screen_snapshot(device,out,'before_recovery',plan['screen_contract'],settings=True)
        if pre['installed']==pre['candidate']:
            result['installation']='skipped_exact_apk'
        else:
            result['stage']='transfer';device.deadline=min(time.monotonic()+150,hard-45-60-125)
            remote=r['remote_apk'];directory=remote.rsplit('/',1)[0]
            probe=device.call('shell','test','-e',directory,check=False,timeout=5)
            c.v.require(probe.returncode==1 and not probe.stderr.strip(),'remote recovery path already used/unavailable')
            device.call('shell','mkdir','-p',directory,timeout=5)
            result['transfer_attempts']=1
            c.cal.write_new(out/'transfer_attempt.json',dict(utc=rp.utc(),apk_sha256=plan['apk_sha256']))
            device.call('push',plan['apk_path'],remote,timeout=120)
            remote_digest=device.call('shell','sha256sum',remote,timeout=10).stdout.decode().split()[0]
            c.v.require(remote_digest==plan['apk_sha256'],'transferred APK mismatch')
            c.cal.write_new(out/'transfer_verified.json',dict(utc=rp.utc(),sha256=remote_digest))
            result['stage']='package_install';device.deadline=min(time.monotonic()+125,hard-45-60)
            result['install_attempts']=1
            c.cal.write_new(out/'install_attempt.json',dict(utc=rp.utc(),method='pm install -r',apk_sha256=remote_digest))
            response=device.call('shell','pm','install','-r',remote,timeout=120)
            c.v.require(re.search(rb'(?m)^Success\s*$',response.stdout),'package manager did not report Success')
            result['installation']='package_manager_returned_success'
        result['stage']='post_identity';device.deadline=min(time.monotonic()+60,hard-45)
        result['installed_apk_sha256']=installed_hash(device,pre['candidate'])
        c.v.require(result['installed_apk_sha256']==plan['apk_sha256'],'installed APK is not the exact candidate')
        result['status']='verified'
    except BaseException as error:
        result.update(error=repr(error),stop_utc=rp.utc())
        if device.last_identity and result['stage']!='post_identity':
            device.deadline=min(time.monotonic()+60,hard-45)
            try:result['post_failure_installed_apk_sha256']=installed_hash(device,plan['apk_preflight']['candidate'])
            except Exception as query_error:result['post_failure_query_error']=repr(query_error)
    finally:
        result['cleanup_start_utc']=rp.utc()
        if device.last_identity:
            try:result['cleanup']=shared.cleanup(device,hard)
            except Exception as error:result.update(status='failed',cleanup=dict(status='unconfirmed',error=repr(error)))
        else:result.update(status='failed',cleanup=dict(status='not_attempted_unidentified_device'))
        result.update(utc_end=rp.utc(),elapsed_seconds=time.monotonic()-start)
        result['evidence_hashes']={str(f.resolve()):c.p.digest(f) for f in out.rglob('*') if f.is_file()}
        c.cal.write_new(out/'receipt.json',result)
    c.v.require(result['status']=='verified','recovery failed; collection prohibited, no retry')
    return result


def run(path, adb, serial, approved, expected_hash):
    c.v.require(approved and c.p.digest(path)==expected_hash,'explicit bundle approval/hash required')
    check(path);r=c.p.read(path);plan=c.p.read(r['collection_plan'])
    root=Path(r['workflow_root'])
    c.v.require(not root.exists() and not Path(r['output_root']).exists() and
                not Path(plan['registry']).exists() and not Path(plan['output_root']).exists(),'bundle already used')
    root.mkdir();start=time.monotonic();hard=start+TOTAL
    c.cal.write_new(root/'claim.json',dict(utc=rp.utc(),recovery_plan_sha256=c.p.digest(path),total_seconds=TOTAL))
    try:
        recovery=recover(path,adb,serial,hard)
        from tools import d1_arrival_collection_device as runner
        results={}
        for phase in ('development','confirmation'):
            c.v.require(hard-time.monotonic()>=2745,'insufficient full collection phase budget; no start')
            freeze=root/'development_freeze.json'
            results[phase]=runner.run(r['collection_plan'],phase,adb,serial,12,r['collection_plan_sha256'],
                                     freeze if phase=='confirmation' else None,overall_deadline=hard)
            stats=c.summarize(r['collection_plan'],phase)
            if phase=='development':c.cal.write_new(freeze,stats)
            else:
                frozen=c.p.read(freeze);stats['freeze_sha256']=c.p.digest(freeze)
                stats['median_errors']={key:{k:v['median']-frozen['conditions'][key]['metrics'][k]['median']
                    for k,v in row['metrics'].items()} for key,row in stats['conditions'].items()}
                c.cal.write_new(root/'confirmation.json',stats)
        result=dict(status='completed',recovery=recovery['status'],collection=results,elapsed_seconds=time.monotonic()-start,
                    experiment_ready=False)
        c.cal.write_new(root/'complete.json',result);return result
    except BaseException as error:
        c.cal.write_new(root/'stopped.json',dict(status='stopped_no_resume',utc=rp.utc(),error=repr(error),elapsed_seconds=time.monotonic()-start))
        raise


def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    prep=sub.add_parser('prepare');prep.add_argument('--parent',required=True);prep.add_argument('--output',required=True)
    prep.add_argument('--revision',type=int,choices=(1,2),default=1);prep.add_argument('--prior-recovery')
    for name in ('check','run'):
        s=sub.add_parser(name);s.add_argument('--plan',required=True)
        if name=='run':
            for flag in ('adb','serial','expected-plan-sha256'):s.add_argument('--'+flag,required=True)
            s.add_argument('--approved',action='store_true')
    a=parser.parse_args()
    if a.command=='prepare':result=prepare(a.parent,a.output,a.revision,a.prior_recovery)
    elif a.command=='check':result=check(a.plan)
    else:result=run(a.plan,a.adb,a.serial,a.approved,a.expected_plan_sha256)
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
