"""Bounded parent owner: one campaign, one recovery wait, one eligible repair block.

No device calls in prepare/check. Code repair is performed by the operator/agent,
not an automatic error-suppressing loop. Original child receipts stay immutable.
"""
import argparse
import copy
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
from datetime import datetime,timezone
from pathlib import Path
from tools import d1_history_control_plan as h
from tools import d1_energy_host_lifecycle as life

NAME='ENERGY-AP-HISTORY-RECOVERY-03'
FOLDER='energy_ap_history_recovery_plan_v3'
ENV='D1_HISTORY_CAMPAIGN_PERMIT'
require=h.require
write=h.cal.write_new
read=h.p.read
sha=h.p.digest


def limits():
    return dict(total_seconds=21600,terminal_reserve_seconds=600,wait_seconds=1200,
        wait_interval_seconds=60,wait_commands=20,readonly_recovery_seconds=120,
        readonly_recovery_commands=20,repair_blocks=1,sessions=13,
        requests=2016,warmup=104,explicit_inference=2120,runtime_creations=52,
        staging=13,staging_files=91,installed_host_pulls=2,apk_transfers=2,installs=2,
        trace_host_pulls=13,adb_commands=99240,
        repair_requires_zero_eligible_development=True,repair_requires_app_defect=True,
        retry_closed_plan=False,automatic_transport_switch=False)


def utc():return datetime.now(timezone.utc).isoformat()


def remaining(claim,now=None,wall=None):
    now=time.monotonic() if now is None else now
    wall=time.time() if wall is None else wall
    elapsed=now-claim['monotonic_start'];elapsed_wall=wall-claim['wall_start']
    require(elapsed>=0 and abs(elapsed-elapsed_wall)<5,'clock discontinuity/reboot; no new work')
    return limits()['total_seconds']-max(elapsed,elapsed_wall)


def child_spec(source,build,folder,role,campaign_root):
    folder=Path(folder);plan,ms=h.specification(source,build,folder)
    name=NAME+'-'+role.upper()
    plan.update(experiment_id=name,history_recovery_child=dict(role=role,campaign_root=str(Path(campaign_root).resolve())),
        output_root=str(Path(campaign_root)/role),registry=str(Path(campaign_root)/(role+'_registry')))
    for e,m in zip(plan['entries'],ms):
        sid=str(uuid.uuid5(uuid.NAMESPACE_URL,name+'/'+str(e['index'])))
        m.update(experiment_id=name,session_id=sid)
        for s in m['models'].values():s['identity']['session_id']=sid
        for key in ('requests','conditioning_requests'):
            for r in m[key]:r['request_id']=str(uuid.uuid5(uuid.NAMESPACE_URL,sid+'/'+key+'/'+str(r['ordinal'])))
        e.update(session_id=sid,manifest='manifests/'+sid+'.json',manifest_sha256=hashlib.sha256(h.p.canonical(m)).hexdigest())
    return plan,ms


def write_child(source,build,folder,role,campaign_root):
    folder=Path(folder);require(not folder.exists(),'fresh child plan')
    plan,ms=child_spec(source,build,folder,role,campaign_root)
    require(not Path(plan['output_root']).exists() and not Path(plan['registry']).exists(),'child consumed')
    folder.mkdir(parents=True);(folder/'manifests').mkdir()
    for e,m in zip(plan['entries'],ms):write(folder/e['manifest'],m)
    (folder/'RUN_AFTER_APPROVAL.ps1').write_text(h.script_text(),encoding='utf8',newline='\n')
    write(folder/'collection_plan.json',plan)
    return folder/'collection_plan.json'


def check_child(file):
    file=Path(file);plan=read(file);cfg=plan['history_recovery_child']
    require(cfg['role'] in ('primary','repair'),'child role')
    require(not Path(plan['output_root']).exists() and not Path(plan['registry']).exists(),'child consumed')
    expected,ms=child_spec(plan['source_plan']['path'],plan['build_receipt'],file.parent,cfg['role'],cfg['campaign_root'])
    require(plan==expected,'child plan/source drift')
    require(shutil.disk_usage(file.parent).free>=plan['minimum_host_free_bytes'],'4GiB disk reserve')
    require((file.parent/'RUN_AFTER_APPROVAL.ps1').read_text(encoding='utf8')==h.script_text(),'child script drift')
    for e,m in zip(plan['entries'],ms):require(read(file.parent/e['manifest'])==m and sha(file.parent/e['manifest'])==e['manifest_sha256'],'manifest drift')
    for x in [plan['frozen_model'],plan['activity_model'],*plan['source_files'].values(),*plan['references'].values()]:require(sha(x['path'])==x['sha256'],'input/model drift')
    require(sha(plan['trace_content_audit']['processor_path'])==plan['trace_content_audit']['processor_sha256'],'trace processor drift')
    return dict(status='PC_READY_UNAPPROVED',plan_sha256=sha(file),device_commands=0)


def script():
    return '''param([ValidateSet('Check','Run')][string]$Action='Check',[switch]$Approved,[string]$Serial,[string]$ExpectedPlanSha256,
[string]$Adb='C:/Users/LG/AppData/Local/Android/Sdk/platform-tools/adb.exe')
$ErrorActionPreference='Stop'
Push-Location '__ROOT__'
try {
 $p=Join-Path $PSScriptRoot 'campaign_plan.json'
 $cliArgs=@('-X','utf8','-B','-m','tools.d1_history_recovery_campaign',$Action.ToLower(),'--plan',$p)
 if($Action -eq 'Run') { if(-not $Approved -or -not $Serial -or -not $ExpectedPlanSha256){throw 'approval/transport/hash required'}; $cliArgs+=@('--approved','--serial',$Serial,'--adb',$Adb,'--expected-sha',$ExpectedPlanSha256) }
 & 'C:/Users/LG/AppData/Local/Programs/Python/Python311/python.exe' @cliArgs
 if($LASTEXITCODE -ne 0){throw "campaign exit $LASTEXITCODE"}
} finally {Pop-Location}
'''.replace('__ROOT__',str(h.ROOT).replace('\\','/'))


def prepare(source,build,output):
    folder=Path(output);require(folder.name==FOLDER and not folder.exists(),'fresh campaign plan')
    root=folder.parent/'energy_ap_history_recovery_run_v3';require(not root.exists(),'campaign consumed')
    folder.mkdir();child=write_child(source,build,folder/'primary_plan','primary',root)
    plan=dict(id=NAME,status='PC_READY_UNAPPROVED_UNCONSUMED',approval='not_approved',experiment_ready=False,
        limits=limits(),output_root=str(root),primary_plan=str(child),primary_sha256=sha(child),
        source_code=h.identity(),repair='one fresh block only after first app failure and zero eligible development; requires recorded causal review/tests/build and remaining full-block reserve',
        run_script_sha256=hashlib.sha256(script().encode()).hexdigest())
    previous=folder.parent/'energy_ap_history_recovery_run_v2/primary/FINAL_RECEIPT.json'
    require(previous.is_file() and read(previous)['status']=='stopped_no_resume','preserved prior receipt required')
    plan['previous_execution']=dict(path=str(previous),sha256=sha(previous),
        outcome='stopped_no_resume retained; no eligible development; separate protocol block',
        recorded_inference_starts=104,adb_commands=read(previous)['adb_commands'],
        accounting='prior attempt reported separately; no consumed claim reset')
    write(folder/'campaign_plan.json',plan);(folder/'RUN_AFTER_APPROVAL.ps1').write_text(script(),encoding='utf8',newline='\n')
    return check(folder/'campaign_plan.json')


def check(file):
    file=Path(file);plan=read(file)
    require(plan['id']==NAME and plan['limits']==limits() and plan['source_code']==h.identity(),'campaign identity')
    require(not Path(plan['output_root']).exists(),'campaign consumed')
    require(sha(plan['primary_plan'])==plan['primary_sha256'],'primary binding')
    require(sha(plan['previous_execution']['path'])==plan['previous_execution']['sha256'],'prior receipt drift')
    require((file.parent/'RUN_AFTER_APPROVAL.ps1').read_text(encoding='utf8')==script(),'wrapper drift')
    child=check_child(plan['primary_plan'])
    return dict(status=plan['status'],campaign_sha256=sha(file),primary=child,limits=limits(),device_commands=0)


def require_admission(file):
    permit_path=os.environ.get(ENV);require(bool(permit_path),'child must be admitted by campaign owner')
    permit=read(permit_path);plan=read(file)
    require(permit['parent_pid']==os.getppid() and permit['plan_sha256']==sha(file),'child owner/hash')
    claim=read(Path(plan['history_recovery_child']['campaign_root'])/'claim.json')
    require(permit['campaign_token']==claim['token'],'campaign owner token')
    require(remaining(claim)>=plan['budget']['total_seconds']+limits()['terminal_reserve_seconds'],'child time admission')


def invoke(file,root,adb,serial,claim,role):
    require(remaining(claim)>=h.budget()['total_seconds']+600,'full block and terminal reserve')
    permit=Path(root)/(role+'_permit.json')
    write(permit,dict(parent_pid=os.getpid(),plan_sha256=sha(file),campaign_token=claim['token']))
    env=dict(os.environ);env[ENV]=str(permit)
    command=[sys.executable,'-X','utf8','-B','-m','tools.d1_history_control_plan','run','--plan',str(file),'--adb',adb,'--serial',serial,'--expected-sha',sha(file),'--approved']
    with (Path(root)/(role+'_host.log')).open('xb') as log:
        result=subprocess.run(command,cwd=h.ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=h.budget()['total_seconds']+5)
    write(Path(root)/(role+'_child_exit.json'),dict(returncode=result.returncode,utc=utc(),parent_pid=os.getpid()))
    child=read(file);receipt=Path(child['output_root'])/'FINAL_RECEIPT.json'
    require(receipt.is_file(),'child exited without receipt; no automatic recovery/restart')
    return read(receipt)


def child_exited(child):
    info=read(Path(child['registry'])/'claimed.json')
    require(life.identity_state(info['host_identity']['child']) in ('exited','replaced'),'original collection child alive/unknown')
    # This new protocol keeps its parent owner alive intentionally; no second collector exists.
    for f in Path(child['output_root']).glob('host_commands/*/client/result.json'):
        record=read(f)
        require(record.get('status') in ('returned','nonzero_exit','timeout') and record.get('returncode') is not None,'client state unconfirmed')


def connection_failure(child):
    signals=(b'error: closed',b'device not found',b'no devices/emulators',b'device offline',b'cannot connect',b'device \'')
    files=sorted(Path(child['output_root']).glob('host_commands/*/client/stderr.bin'))
    return any(any(x in f.read_bytes().lower() for x in signals) for f in files[-4:])


def wait_online(device,deadline,record,sleep=time.sleep,clock=time.monotonic):
    events=[]
    for i in range(limits()['wait_commands']):
        if clock()+9>deadline:break
        start=clock();device.deadline=min(deadline,start+12)
        try:
            r=device.call('get-state',timeout=3,check=False)
            online=r.returncode==0 and r.stdout.strip()==b'device'
            events.append(dict(index=i,status='online' if online else 'unavailable'))
        except Exception as e:online=False;events.append(dict(index=i,error=repr(e)))
        record(events)
        if online:return True
        until=min(deadline,start+60)
        while clock()<until:sleep(min(1,until-clock()))
    return False


def recover_readonly(d,child,folder):
    from tools import d1_energy_collection_device as energy
    from tools import d1_arrival_device as legacy
    # Pinned endpoint only; no connect, setting, launch, force-stop or trace-stop command.
    model=d.call('shell','getprop','ro.product.model',timeout=3).stdout.decode().strip()
    fingerprint=d.call('shell','getprop','ro.build.fingerprint',timeout=3).stdout.decode().strip()
    serial=d.call('shell','getprop','ro.serialno',timeout=3).stdout.decode().strip()
    require(model=='SM-A245N' and fingerprint==child['device_fingerprint'] and serial==child['device_hardware_serial'],'recovered device differs')
    attempts=sorted(Path(child['output_root']).glob('*/launch_attempt.json'));require(bool(attempts),'no owned app launch')
    session=attempts[-1].parent;manifest=read(session/'input_manifest.json')
    remote='files/'+child['protocol']+'/'+manifest['session_id']
    raw=d.call('exec-out','run-as',legacy.PACKAGE,'cat',remote+'/manifest.json',timeout=3).stdout
    require(hashlib.sha256(raw).hexdigest()==sha(session/'input_manifest.json'),'recovered session mismatch')
    cleanup=d.call('exec-out','run-as',legacy.PACKAGE,'cat',remote+'/cleanup.json',timeout=3).stdout
    require(json.loads(cleanup)['status'] in ('completed','failed'),'no terminal app evidence')
    pid=d.call('shell','pidof',legacy.PACKAGE+':model_probe',timeout=3,check=False)
    require(pid.returncode in (0,1) and not pid.stderr.strip(),'process status unknown')
    require((pid.returncode==1 and not pid.stdout.strip()) or (pid.returncode==0 and re.fullmatch(rb'\d+',pid.stdout.strip())), 'ambiguous process inventory')
    result=energy.recover(d,remote,Path(folder)/'artifacts')
    return dict(status='recovered_terminal_app_evidence',recovery=result,app_cleanup=json.loads(cleanup),
        process='present_not_proof_of_inference' if pid.stdout.strip() else 'absent',
        original_session=str(session.name),trace='original trace recovery only; no second trace stop',original_outcome_unchanged=True)


def recover_once(plan,child,root,adb,serial,claim):
    from tools.d1_adb_observed_client import ObservedDevice
    child_exited(child);folder=Path(root)/'connection_recovery';folder.mkdir(exist_ok=False)
    start=time.monotonic();left=remaining(claim)
    deadline=start+min(1200,max(0,left-600-120));write(folder/'intent.json',dict(utc=utc(),max_wait_seconds=max(0,deadline-start)))
    d=ObservedDevice(adb,serial,folder/'commands',forbid_apk_deploy=True);d.command_limit=40
    def record(events):
        with (folder/'wait.jsonl').open('a',encoding='utf8') as f:f.write(json.dumps(events[-1])+'\n')
    result=dict(status='connection_unavailable',app_state='unknown')
    try:
        if wait_online(d,deadline,record):
            d.command_limit=d.sequence+20;d.deadline=time.monotonic()+min(120,max(0,remaining(claim)-600))
            result=recover_readonly(d,child,folder)
    except BaseException as e:result.update(status='recovery_failed_or_unknown',error=repr(e))
    result.update(adb_attempts=d.sequence,elapsed_seconds=time.monotonic()-start)
    write(folder/'receipt.json',result);return result


def repair_eligibility(receipt,root):
    require(receipt.get('status')=='stopped_no_resume' and receipt.get('completed_sessions')==0 and receipt.get('session_attempts',0)<=1 and receipt.get('launch_attempts',0)==1,'repair only before any eligible development')
    failures=list(Path(root).glob('*/artifacts/session_failure.json'))+list(Path(root).glob('*/failure_prefix/session_failure.json'))
    require(bool(failures),'no durable app failure; not an app-repair case')
    return failures


def prepare_repair(plan_file,build,review_file):
    plan=read(plan_file);root=Path(plan['output_root']);claim=read(root/'claim.json')
    require(plan['limits']==limits(),'campaign limits immutable')
    require(not (root/'repair_permit.json').exists(),'repair already attempted')
    primary=read(plan['primary_plan']);child_exited(primary)
    receipt=Path(primary['output_root'])/'FINAL_RECEIPT.json';repair_eligibility(read(receipt),primary['output_root'])
    review=read(review_file)
    require(review['original_receipt_sha256']==sha(receipt) and review['cause_status']=='reproduced_code_defect' and review['measurement_semantics_unchanged'] is True,'causal/compatibility review required')
    require(review['tests'] and all(t['passed'] is True and t['command'] for t in review['tests']),'focused verification required')
    require(review['source_code']==h.identity(),'repair review source drift')
    require(primary['budget']==h.budget(),'repair may not change resource/time limits')
    protected=[k for k in primary['source_code'] if k.endswith('.json') or 'perfetto' in k or
        (k.startswith('tools/') and any(word in k for word in ('analysis','model','protocol')))]
    for k in protected:require(h.identity().get(k)==primary['source_code'][k],'repair changes protected measurement/model contract: '+k)
    require(remaining(claim)>=h.budget()['total_seconds']+600,'repair no longer fits; no budget extension')
    file=write_child(primary['source_plan']['path'],build,Path(plan_file).parent/'repair_plan','repair',root)
    write(root/'repair_binding.json',dict(plan=str(file),sha256=sha(file),review=str(Path(review_file).resolve()),review_sha256=sha(review_file),original_receipt_sha256=sha(receipt)))
    return check_child(file)


def run(file,adb,serial,expected,approved,repair=False):
    require(approved and serial and sha(file)==expected,'explicit campaign approval/hash/transport')
    plan=read(file);root=Path(plan['output_root'])
    if not repair:
        check(file);root.mkdir(exist_ok=False)
        claim=dict(utc=utc(),monotonic_start=time.monotonic(),wall_start=time.time(),token=uuid.uuid4().hex,serial=serial,plan_sha256=sha(file))
        write(root/'claim.json',claim);childfile=Path(plan['primary_plan']);role='primary'
    else:
        claim=read(root/'claim.json');require(serial==claim['serial'] and claim['plan_sha256']==sha(file),'same campaign/transport')
        require(plan['limits']==limits(),'campaign limits immutable')
        binding=read(root/'repair_binding.json');require(sha(binding['plan'])==binding['sha256'] and sha(binding['review'])==binding['review_sha256'],'repair binding drift')
        childfile=Path(binding['plan']);check_child(childfile);role='repair'
    try:
        receipt=invoke(childfile,root,adb,serial,claim,role)
        result=dict(status=receipt['status'],child_receipt_sha256=sha(Path(read(childfile)['output_root'])/'FINAL_RECEIPT.json'))
        if receipt['status']=='stopped_no_resume':
            child=read(childfile)
            if connection_failure(child) and not (root/'connection_recovery').exists():result['connection_recovery']=recover_once(plan,child,root,adb,serial,claim)
            if role=='primary':
                try:repair_eligibility(receipt,child['output_root']);result['repair']='agent_diagnosis_required_before_prepare_repair; not automatic'
                except ValueError as e:result['repair']='not_eligible: '+str(e)
        result.update(remaining_seconds=remaining(claim),device_effect_claim='none; original/failure evidence retained',experiment_ready=False)
    except BaseException as e:
        result=dict(status='campaign_stopped',error=repr(e),app_state='unknown_unless_child_evidence',experiment_ready=False)
        raise
    finally:write(root/(role+'_campaign_receipt.json'),result)
    return result


def main():
    cli=argparse.ArgumentParser();cli.add_argument('action',choices=['prepare','check','run','prepare-repair','repair-run'])
    for n in ('source','build','output','plan','adb','serial','expected-sha','review'):cli.add_argument('--'+n)
    cli.add_argument('--approved',action='store_true');a=cli.parse_args()
    if a.action=='prepare':result=prepare(a.source,a.build,a.output)
    elif a.action=='check':result=check(a.plan)
    elif a.action=='prepare-repair':result=prepare_repair(a.plan,a.build,a.review)
    else:result=run(a.plan,a.adb,a.serial,a.expected_sha,a.approved,a.action=='repair-run')
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
