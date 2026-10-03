"""Four structural development contrasts, opt-in observation; Check never uses ADB."""
import argparse
import copy
import hashlib
import json
import shutil
import shlex
import time
import uuid
from pathlib import Path
from tools import d1_arrival_plan as p
from tools import d1_arrival_energy_collection as old
from tools import d1_arrival_timing_calibration as cal
from tools import d1_arrival_ap_confirmation as prior
from tools import d1_apk_identity as apk
from tools import d1_separated_power_protocol as inputs
from tools import d1_ap_background_contrast as script_source

ROOT=Path(__file__).resolve().parents[1]
VERSION='background-activity-contrast-v1'
NAME='BACKGROUND-ACTIVITY-DEVELOPMENT-04'
FOLDER='background_activity_plan_v4'
ORDER=('C0_PRE','CPU_URGENT_ONLINE_V1','B2_PARALLEL_ONLINE_V1','C0_POST')
CONTRACT=ROOT/'docs/results/online_policy_study_01/background_activity_pc_v1/contract.json'
TRACE_CONFIG=ROOT/'tools/perfetto/background_activity.pbtxt'
MODEL=ROOT/'docs/results/online_policy_study_01/separated_power_final/model.json'
MODEL_SHA='5682082a936b7c83efeee747ceeb64fd0c64f0bef8765bbf1b90b807db872db2'
require=old.require


def budget():
    # Trace recovery is in addition to original 50s evidence/45s app cleanup.
    return dict(prior.BUDGET,sessions=4,requests=192,warmup=32,explicit_inference=224,
        runtime_creations=16,staging=4,staging_files=28,installed_host_pulls=1,
        apk_transfers=0,installs=0,installation_seconds=0,installed_preflight_seconds=440,
        fixed_observation_seconds=840,intersession_cooling_seconds=90,
        trace_sessions=4,trace_recovery_seconds=120,trace_content_audit_seconds=40,trace_start_seconds=90,app_launch_seconds=26,trace_max_seconds=600,
        trace_max_bytes=67108864,trace_host_pulls=4,
        session_seconds=936,total_seconds=440+4*936+3*90,
        per_session_adb_commands=3209,adb_commands=200+4*3209,
        adb_recovery_cleanup_reserve=109)


def identity():
    return old.identity() | {x.relative_to(ROOT).as_posix():p.digest(x) for x in
        (Path(__file__),CONTRACT,TRACE_CONFIG,MODEL,Path(inputs.__file__),ROOT/'tools/d1_background_activity_readout.py',*[ROOT/f'tools/perfetto/background_{name}.sql' for name in ('sched','frequency','loss','clock','cpu')])}


def script_text():
    return prior.script_text({}).replace('d1_arrival_ap_confirmation','d1_background_activity_plan').replace('python -B', "& 'C:/Users/LG/anaconda3/python.exe' -X utf8 -B")


def specification(source_file,build_file,output):
    source_file,build_file,output=map(Path,(source_file,build_file,output))
    source,build=p.read(source_file),p.read(build_file)
    require(old.apk_sources(build['source_code'])==old.apk_sources(cal.code_identity()),'APK/source mismatch')
    require(p.digest(build['apk_path'])==build['apk_sha256'],'APK drift')
    candidate=apk.inspect(build['apk_path'],source['apk_preflight']['toolchain'])
    require(candidate['signer_sha256']==source['apk_preflight']['candidate']['signer_sha256'],'project signer')
    plan=copy.deepcopy(source)
    for k in list(plan):
        if k.startswith(('separated_','ap_','resident_','recorded_','online_','study_')):plan.pop(k)
    plan.update(background_activity_contrast=True,installed_only=True,online_policy_study=True,online_configuration_owner_v1=True,
        study_phase='development',experiment_id=NAME,approval='not_approved',experiment_ready=False,
        status='PC_READY_DEVICE_UNVERIFIED_NOT_APPROVED',minimum_host_free_bytes=2**31,budget=budget(),source_code=identity(),
        source_plan=dict(path=str(source_file.resolve()),sha256=p.digest(source_file)),
        build_receipt=str(build_file.resolve()),build_receipt_sha256=p.digest(build_file),
        apk_path=build['apk_path'],apk_sha256=build['apk_sha256'],apk_preflight=dict(source['apk_preflight'],candidate=candidate),
        analysis_contract=dict(path=str(CONTRACT),sha256=p.digest(CONTRACT)),
        input_bundle=dict(path=str(CONTRACT),sha256=p.digest(CONTRACT)),
        activity_model=dict(path=str(MODEL),sha256=MODEL_SHA),
        output_root=str(output.parent/'background_activity_run_v4'),
        trace_content_audit=dict(processor_path='C:/Users/LG/.local/share/perfetto/prebuilts/trace_processor_shell-adfa6bad3d72be3b.exe',
            processor_sha256='adfa6bad3d72be3ba9b83fa2b17b69fa13b3ab1cad0f42e52b86188bd5f0f997',
            processor_version='v58.2-add693d8b',expected_cpus=list(range(8)),seconds=40,
            trace_recovery_seconds=120,window='common_start_to_planned_end',required_before_next_session=True),
        registry=str(output.parent/'background_activity_registry'/NAME),entries=[],
        measurement_protocol_change='trace-v2 RING_BUFFER and producer flush5s, offline content audit before next session; unchanged APK/sampler/host polling; new development block only',
        analysis_scope='structural identification, no adopted candidate or independent policy validation',
        prewarmup_observation='precommon-observation-gap-v3')
    template=p.read(source_file.parent/source['entries'][0]['manifest']);manifests=[]
    for i,policy in enumerate(ORDER):
        m=copy.deepcopy(template)
        for k in list(m):
            if k.startswith(('policy_study','power_identification','resident_control','replay_','source_')):m.pop(k)
        sid=str(uuid.uuid5(uuid.NAMESPACE_URL,NAME+'/'+str(i)));control=policy.startswith('C0')
        rows=[] if control else inputs.requests('confirmation',sid)
        for row in rows:row['request_id']=str(uuid.uuid5(uuid.NAMESPACE_URL,sid+'/'+str(row['ordinal'])))
        m.update(experiment_id=NAME,session_id=sid,phase=policy,scenario='burst' if control else 'separated_power',
            policy='RECORDED_B2_REPLAY_V1' if control else policy,requests=rows,
            background_observation_version=VERSION,background_observation_role='development',
            power_sampling_version='online-power-phase-audit-v1',power_sample_period_ms=900,
            start_ap_gate='numeric-ap-observe-v2',apk_sha256=build['apk_sha256'])
        if control:m.update(resident_control_version='resident-control-pair-v1',resident_control_role='no_load_control',replay_version='recorded-b2-dispatch-gate-v1')
        else:m['power_identification_version']='separated-power-input-v1'
        for spec in m['models'].values():spec['identity']['session_id']=sid;spec['target']['apk_sha256']=build['apk_sha256']
        rel='manifests/'+sid+'.json';manifests.append(m)
        plan['entries'].append(dict(index=i,phase=policy,condition=policy,scenario=m['scenario'],policy=m['policy'],
            session_id=sid,manifest=rel,manifest_sha256=hashlib.sha256(p.canonical(m)).hexdigest(),requests=len(rows),warmup=8,runtime_creations=4))
    plan['run_script_sha256']=hashlib.sha256(script_text().encode('utf8')).hexdigest()
    return plan,manifests


def prepare(source,build,output):
    output=Path(output);require(output.name==FOLDER and not output.exists(),'fresh plan required')
    plan,ms=specification(source,build,output)
    require(not Path(plan['output_root']).exists() and not Path(plan['registry']).exists(),'occupied')
    output.mkdir();(output/'manifests').mkdir()
    for e,m in zip(plan['entries'],ms):cal.write_new(output/e['manifest'],m)
    (output/'RUN_AFTER_APPROVAL.ps1').write_text(script_text(),encoding='utf8',newline='\n')
    cal.write_new(output/'collection_plan.json',plan)
    return check(output/'collection_plan.json')


def check(file):
    file=Path(file);plan=p.read(file)
    require(file.parent.name==FOLDER and not Path(plan['registry']).exists() and not Path(plan['output_root']).exists(),'consumed/occupied')
    require(shutil.disk_usage(file.parent).free>=plan['minimum_host_free_bytes'],'host 2GiB reserve before claim/device')
    expected,ms=specification(plan['source_plan']['path'],plan['build_receipt'],file.parent)
    require(expected==plan and (file.parent/'RUN_AFTER_APPROVAL.ps1').read_text(encoding='utf8')==script_text(),'plan/script drift')
    for x in [plan['frozen_model'],plan['activity_model'],*plan['source_files'].values(),*plan['references'].values()]:require(p.digest(x['path'])==x['sha256'],'binding drift')
    require(p.digest(MODEL)==MODEL_SHA,'original frozen model drift')
    audit=plan['trace_content_audit']
    require(p.digest(audit['processor_path'])==audit['processor_sha256'],'TraceProcessor drift')
    for e,m in zip(plan['entries'],ms):require(p.digest(file.parent/e['manifest'])==e['manifest_sha256'] and p.read(file.parent/e['manifest'])==m,'manifest drift')
    return dict(status=plan['status'],plan_sha256=p.digest(file),budget=budget(),device_commands=0)


def trace_identity(session):
    require(str(uuid.UUID(session))==session,'trace session UUID')
    return 'd1-bg-'+session,'/data/misc/perfetto-traces/d1-bg-'+session+'.pftrace'


def trace_start(d,session,folder):
    key,remote=trace_identity(session)
    # This installed Perfetto prints complete help to stderr and returns 1.
    # Accept only recognizable help with every required option, not arbitrary failures.
    help_result=d.call('shell','perfetto','--help',timeout=5,check=False)
    helptext=(help_result.stdout+help_result.stderr).decode(errors='replace')
    require(help_result.returncode in (0,1) and 'Usage: perfetto' in helptext and
        all(x in helptext for x in ('--detach','--attach','--is_detached','--txt')),
        'Perfetto help failed or required CLI unsupported; no app launch')
    sources=d.call('shell','perfetto','--query',timeout=5).stdout.decode(errors='replace')
    require('linux.ftrace' in sources and 'linux.process_stats' in sources,'required trace data sources unavailable')
    exists=d.call('shell','test','-e',remote,check=False,timeout=3)
    require(exists.returncode==1 and not exists.stdout.strip() and not exists.stderr.strip(),'trace path exists or unavailable')
    config=TRACE_CONFIG.read_text(encoding='utf8')
    command="printf '%s' "+shlex.quote(config)+' | perfetto --txt -c - -o '+shlex.quote(remote)+' --detach='+key
    # Persist identity BEFORE launch: timeout may leave a bounded recording alive.
    state=dict(key=key,remote=remote,start_attempted=True,recovery_attempted=False,duration_ms=600000,max_bytes=67108864)
    cal.write_new(Path(folder)/'trace_start_intent.json',state)
    d.background_trace=(Path(folder),state)
    result=d.call('shell',command,timeout=35)
    require(result.returncode==0,'trace start failed')
    active=d.call('shell','perfetto','--is_detached='+key,timeout=5,check=False)
    require(active.returncode==0,'trace not active; no app launch')
    cal.write_new(Path(folder)/'trace_started.json',dict(state,status='active_verified'))


def trace_recover(d,deadline):
    owned=getattr(d,'background_trace',None)
    if owned is None:return None
    folder,state=owned
    if state['recovery_attempted']:return state.get('result',dict(status='unknown_after_attempt'))
    state['recovery_attempted']=True
    result=dict(status='partial_or_unknown',errors=[],remote=state['remote'])
    previous=d.deadline;d.deadline=min(deadline,time.monotonic()+getattr(d,'background_trace_audit',{}).get('trace_recovery_seconds',80))
    try:
        # No PID kill, global stop or retry. Only the key registered by this owner.
        try:
            status=d.call('shell','perfetto','--is_detached='+state['key'],timeout=5,check=False)
            require(status.returncode in (0,2),'trace state unknown')
            if status.returncode==0:d.call('shell','perfetto','--attach='+state['key'],'--stop',timeout=10)
            result['termination']='owned_stop' if status.returncode==0 else 'not_active_observed'
        except BaseException as e:result['errors'].append(dict(stage='trace_stop',error=repr(e)))
        try:
            stat=d.call('shell','stat','-c','%s',state['remote'],timeout=3)
            size=int(stat.stdout.strip());require(0<size<67108864,'trace missing/empty/file cap reached')
            target=folder/'system_activity.pftrace'
            d.call('pull',state['remote'],str(target),timeout=30)
            require(target.stat().st_size==size,'trace size mismatch')
            result.update(bytes=size,sha256=p.digest(target),file=str(target))
        except BaseException as e:result['errors'].append(dict(stage='trace_recovery',error=repr(e)))
        if not result['errors']:
            audit=getattr(d,'background_trace_audit',None)
            if audit:
                try:
                    from tools import d1_background_activity_readout as readout
                    result['content_audit']=readout.audit(audit['processor_path'],audit['processor_sha256'],target,folder,
                        folder/'trace_export',min(d.deadline,time.monotonic()+audit['seconds']),audit['expected_cpus'])
                    result['status']='recovered_content_eligible'
                except BaseException as error:result['errors'].append(dict(stage='trace_content_audit',error=repr(error)))
            else:result['status']='recovered_requires_clock_loss_content_audit'
    finally:
        d.deadline=previous;state['result']=result
        cal.write_new(folder/'trace_recovery.json',result)
    return result


def main():
    a=argparse.ArgumentParser();a.add_argument('action',choices=['prepare','check','run'])
    for name in ('source-plan','build-receipt','output','plan','adb','serial','expected-sha'):a.add_argument('--'+name)
    a.add_argument('--approved',action='store_true');q=a.parse_args()
    if q.action=='prepare':result=prepare(q.source_plan,q.build_receipt,q.output)
    elif q.action=='check':result=check(q.plan)
    else:
        require(bool(q.serial),'explicit current transport required')
        from tools.d1_arrival_energy_collection_device import run
        result=run(q.plan,q.adb,q.serial,q.expected_sha,q.approved)
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
