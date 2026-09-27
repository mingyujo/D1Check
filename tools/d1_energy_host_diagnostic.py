"""One unapproved host-lifecycle diagnostic; installed APK, no baseline/load.

The existing APK cannot exit normally before its official baseline. This host
diagnostic deliberately leaves the probe gate unarmed and performs one bounded
host stop after observing fixed resident preparation. App cleanup is reported
separately and is not implied by a successful host stop.
"""

import argparse
import copy
import json
import os
from pathlib import Path
import time
import traceback
import threading
import uuid

from tools import d1_arrival_plan as p
from tools import d1_arrival_timing_calibration as cal
from tools import d1_arrival_timing_calibration_device as shared
from tools import d1_arrival_device as legacy
from tools import d1_energy_collection_device as runner
from tools import d1_energy_state_collection as state
from tools import d1_energy_host_checkpoints as checkpoints
from tools import d1_energy_host_lifecycle as lifecycle
from tools import d1_energy_collection as collection
from tools import d1_apk_identity as apk
from tools.d1_adb_observed_client import ObservedDevice

ID='ENERGY-AP-HOST-DIAG-01'
SOURCE_FILES=('tools/d1_energy_host_diagnostic.py','tools/d1_energy_host_recovery.py',
              'tools/d1_energy_host_lifecycle.py','tools/d1_energy_host_checkpoints.py',
              'tools/d1_energy_collection_device.py','tools/d1_energy_state_collection.py',
              'tools/d1_adb_observed_client.py')
BUDGET=dict(sessions=1,runtime_creations=4,warmup=8,eligibility_requests=4,
            explicit_inference=12,work_requests=0,staging=1,staged_files=7,
            apk_transfers=0,installs=0,installed_host_pulls=1,
            retry=0,replacement=0,additional=0,
            fixed_resident_preparation_seconds=120,maximum_preparation_seconds=360,
            official_baseline_seconds=0,load_seconds=0,cooling_seconds=0,
            installed_preflight_seconds=300,host_poll_seconds=900,
            post_stop_recovery_seconds=60,cleanup_seconds=45,
            session_seconds=1200,total_seconds=1500,
            adb_command_slots=3000,pre_cleanup_command_slots=2900)


def source_hashes():
    return {name:p.digest(cal.ROOT/name) for name in SOURCE_FILES}


def render_script(digest):
    script=state.render_run_script(digest)
    return (script.replace('tools.d1_energy_state_collection','tools.d1_energy_host_diagnostic')
                  .replace("'collection_plan.json'","'diagnostic_plan.json'"))


def prepare(source,output):
    source=Path(source);output=Path(output)
    if output.exists():raise FileExistsError(output)
    old=p.read(source)
    if old['experiment_id']!=state.EXPERIMENT or old['status']!='PC_READY_DEVICE_UNVERIFIED':
        raise ValueError('unexpected frozen source plan')
    sid=str(uuid.uuid5(uuid.NAMESPACE_URL,ID+'/CC_DG/preparation'))
    template=p.read(source.parent/old['entries'][0]['manifest'])
    manifest=copy.deepcopy(template)
    manifest.update(experiment_id=ID,session_id=sid,phase='diagnostic',
                    host_diagnostic_stop_before_baseline=True)
    for spec in manifest['models'].values():spec['identity']['session_id']=sid
    output.mkdir(parents=True,exist_ok=False);(output/'manifests').mkdir()
    mf=output/'manifests'/f'{sid}.json';cal.write_new(mf,manifest)
    root=output.parent
    plan={key:copy.deepcopy(old[key]) for key in ('protocol','apk_path','apk_sha256','apk_preflight',
        'build_receipt','build_receipt_sha256','installed_receipt','device_fingerprint',
        'device_hardware_serial','source_files','references','screen_contract',
        'temperature_preparation','operational_only','battery_start_percent',
        'battery_min_percent','battery_max_temperature_tenths_c','require_unplugged')}
    plan.update(experiment_id=ID,status='PC_READY_DEVICE_UNVERIFIED_NOT_APPROVED',
        purpose='host lifecycle diagnostic, not power/AP calibration',
        source_plan=dict(path=str(source.resolve()),sha256=p.digest(source)),
        source_code=old['source_code'],host_source_hashes=source_hashes(),
        host_source_identity=state.identity(),
        output_root=str(root/'energy_ap_host_diag_run_v1'),
        registry=str(root/'energy_collection_registry'/ID),
        plan_file=str((output/'diagnostic_plan.json').resolve()),budget=BUDGET,
        entries=[dict(index=0,phase='diagnostic',pair='CC_DG',mode='calibration',
                      session_id=sid,manifest='manifests/'+mf.name,manifest_sha256=p.digest(mf))],
        app_normal_cleanup_supported=False,experiment_ready=False)
    plan_file=output/'diagnostic_plan.json';cal.write_new(plan_file,plan)
    (output/'RUN_AFTER_APPROVAL.ps1').write_text(render_script(p.digest(plan_file)),encoding='utf-8-sig')
    return check(plan_file)


def check(plan_file):
    plan_file=Path(plan_file);plan=p.read(plan_file)
    if plan['experiment_id']!=ID or plan['status']!='PC_READY_DEVICE_UNVERIFIED_NOT_APPROVED' or \
       plan['budget']!=BUDGET or plan['experiment_ready'] is not False:
        raise ValueError('diagnostic ID/status/budget changed')
    if Path(plan['plan_file'])!=plan_file.resolve() or \
       Path(plan['output_root'])!=plan_file.parent.parent/'energy_ap_host_diag_run_v1' or \
       Path(plan['registry'])!=plan_file.parent.parent/'energy_collection_registry'/ID:
        raise ValueError('diagnostic namespace changed')
    if Path(plan['output_root']).exists() or Path(plan['registry']).exists():
        raise ValueError('consumed diagnostic plan; never resume')
    if plan['host_source_hashes']!=source_hashes() or plan['host_source_identity']!=state.identity():
        raise ValueError('host source changed')
    if p.digest(plan['source_plan']['path'])!=plan['source_plan']['sha256']:
        raise ValueError('source plan changed')
    if p.digest(plan['build_receipt'])!=plan['build_receipt_sha256'] or \
       p.digest(plan['apk_path'])!=plan['apk_sha256'] or \
       cal.apk_sources(plan['source_code'])!=cal.apk_sources(state.identity()):
        raise ValueError('APK/source lineage changed')
    installed=p.read(plan['installed_receipt']['path'])
    if p.digest(plan['installed_receipt']['path'])!=plan['installed_receipt']['sha256'] or \
       installed.get('status')!='verified' or installed.get('installed_apk_sha256')!=plan['apk_sha256']:
        raise ValueError('previously verified installed APK receipt changed')
    if apk.inspect(plan['apk_path'],plan['apk_preflight']['toolchain'])!=plan['apk_preflight']['candidate']:
        raise ValueError('signed APK changed')
    if (plan_file.parent/'RUN_AFTER_APPROVAL.ps1').read_text(encoding='utf-8-sig')!=render_script(p.digest(plan_file)):
        raise ValueError('entry script changed')
    for item in list(plan['source_files'].values())+list(plan['references'].values()):
        if p.digest(item['path'])!=item['sha256']:raise ValueError('frozen input changed')
    if len(plan['entries'])!=1 or len(plan['source_files'])!=6 or plan['app_normal_cleanup_supported'] is not False:
        raise ValueError('one diagnostic and six staged files required')
    entry=plan['entries'][0];mf=plan_file.parent/entry['manifest'];m=p.read(mf)
    source=p.read(plan['source_plan']['path'])
    expected=copy.deepcopy(p.read(Path(plan['source_plan']['path']).parent/source['entries'][0]['manifest']))
    expected.update(experiment_id=ID,session_id=entry['session_id'],phase='diagnostic',
                    host_diagnostic_stop_before_baseline=True)
    for spec in expected['models'].values():spec['identity']['session_id']=entry['session_id']
    if p.digest(mf)!=entry['manifest_sha256'] or m['session_id']!=entry['session_id'] or \
       m!=expected or m['experiment_id']!=ID or m['pair']!='CC_DG' or \
       m['apk_sha256']!=plan['apk_sha256']:
        raise ValueError('manifest identity changed')
    if BUDGET['explicit_inference']!=BUDGET['warmup']+BUDGET['eligibility_requests'] or \
       BUDGET['total_seconds']!=BUDGET['installed_preflight_seconds']+BUDGET['session_seconds'] or \
       BUDGET['pre_cleanup_command_slots']>=BUDGET['adb_command_slots']:
        raise ValueError('budget arithmetic')
    return dict(status=plan['status'],plan_sha256=p.digest(plan_file),budget=BUDGET,device_commands=0)


def run(plan_file,adb,serial,expected_sha,approved):
    if not approved or serial is not None or p.digest(plan_file)!=expected_sha:
        raise ValueError('approved plan hash and current transport auto-selection required')
    check(plan_file);plan=p.read(plan_file);entry=plan['entries'][0]
    root=Path(plan['output_root']);registry=Path(plan['registry'])
    registry.mkdir(parents=True,exist_ok=False);root.mkdir(parents=True,exist_ok=False)
    start=time.monotonic();hard=start+BUDGET['total_seconds']
    run_id=os.environ.get('D1_ENERGY_HOST_RUN_ID') or uuid.uuid4().hex
    identity=lifecycle.host_identity()
    checkpoints.atomic_new(registry/'claimed.json',dict(plan_sha256=expected_sha,
        host_run_id=run_id,host_identity=identity,utc=checkpoints.utc(),budget=BUDGET))
    journal=checkpoints.Checkpoints(root/'host_checkpoints',expected_sha,run_id,identity)
    d=None;remote=None;folder=None;identified=False;launch_attempted=False
    result=dict(status='stopped_no_resume',
        experiment_ready=False,planned_baseline_calls=0,planned_load_calls=0,
        confirmed_baseline_calls=None,confirmed_load_calls=None,host_run_id=run_id)
    try:
        journal.mark('claimed')
        d=ObservedDevice(adb,None,root/'host_commands',allow_select=True,forbid_apk_deploy=True)
        d.command_limit=BUDGET['pre_cleanup_command_slots'];d.deadline=hard-45
        pre=root/'installed_preflight';pre.mkdir()
        journal.mark('installed_preflight_start')
        result['installed_preflight']=runner.installed_preflight(d,plan,plan_file,pre,hard)
        identified=True
        journal.mark('installed_preflight_verified')
        if hard-time.monotonic()<BUDGET['session_seconds']:
            raise TimeoutError('insufficient whole diagnostic session reserve')
        folder=root/f"00_{entry['session_id']}";folder.mkdir()
        runner.save(folder/'attempt.json',dict(entry=entry,utc=checkpoints.utc()))
        journal.mark('session_reserved',session_id=entry['session_id'])
        d.deadline=hard-105
        runner.gates(d,plan,folder,'before_session')
        if runner.install.installed_hash(d,plan['apk_preflight']['candidate'])!=plan['apk_sha256']:
            raise ValueError('installed APK changed')
        mf=Path(plan_file).parent/entry['manifest'];(folder/'input_manifest.json').write_bytes(mf.read_bytes())
        remote=shared.stage_inputs(d,entry['session_id'],mf,
                                   {k:v['path'] for k,v in plan['source_files'].items()},plan['protocol'])
        journal.mark('inputs_staged',session_id=entry['session_id'])
        if hard-time.monotonic()<BUDGET['host_poll_seconds']+105:
            raise TimeoutError('insufficient poll and cleanup reserve')
        runner.save(folder/'launch_attempt.json',dict(utc=checkpoints.utc()))
        journal.mark('launch_intent',session_id=entry['session_id'])
        launch_attempted=True
        d.call('shell','am','start','-W','-n',legacy.PACKAGE+'/'+runner.ACTIVITY,
               '-a',runner.ACTION,'--es','session_id',entry['session_id'],timeout=20)
        journal.mark('launch_returned',session_id=entry['session_id'])
        m=p.read(mf)
        observed=runner.poll(d,remote,folder,m,plan,checkpoint=journal.mark,
                             diagnostic_stop_after_preparation=True)
        if not observed or observed['status']!='preparation_observed_host_stop_required':
            raise RuntimeError('temperature preparation not confirmed; no baseline arm')
        result['preparation']=observed
        journal.mark('diagnostic_preparation_observed',session_id=entry['session_id'])
        result['status']='observed_preparation_host_stop'
    except BaseException as error:
        result.update(status='stopped_no_resume',error=repr(error),exception_type=type(error).__name__,
                      exception_stack=traceback.format_exc(),exception_thread=threading.current_thread().name)
        try:journal.mark('failure_detected',error_type=type(error).__name__)
        except BaseException as mark_error:result['checkpoint_error']=repr(mark_error)
    finally:
        if d and identified and launch_attempted and remote and folder and hard-time.monotonic()>70:
            prefix=folder/'pre_stop';prefix.mkdir(exist_ok=True)
            d.deadline=min(hard-45,time.monotonic()+15)
            for name in ('manifest.json','progress.jsonl','cleanup.json'):
                try:runner.pull_file(d,remote,name,prefix)
                except BaseException as error:result.setdefault('pre_stop_errors',{})[name]=repr(error)
        if d and identified and launch_attempted:
            d.command_limit=BUDGET['adb_command_slots'];d.deadline=hard
            try:
                journal.mark('host_cleanup_start')
                result['host_cleanup']=shared.cleanup(d,hard)
                journal.mark('host_cleanup_returned')
            except BaseException as error:result['host_cleanup_error']=repr(error)
        if d and identified and launch_attempted and remote and folder and hard-time.monotonic()>30:
            try:
                d.deadline=hard
                result['recovery']=runner.recover(d,remote,folder/'artifacts',True)
            except BaseException as error:result['recovery_error']=repr(error)
        if d:result['adb_command_slots']=d.sequence
        result['elapsed_seconds']=time.monotonic()-start
        result['utc_end']=checkpoints.utc()
        app_file=folder/'artifacts/cleanup.json' if folder else None
        try:result['app_cleanup']=(p.read(app_file) if app_file and app_file.exists() else 'unconfirmed')
        except BaseException as error:
            result['app_cleanup']='unconfirmed'
            result['app_cleanup_read_error']=repr(error)
        progress_file=folder/'artifacts/progress.jsonl' if folder else None
        if progress_file and progress_file.exists():
            try:
                raw=progress_file.read_bytes()
                result['consumption_bounds']=state.progress_consumption(raw,True)
                rows,partial=collection.progress_prefix(raw)
                forbidden=[r for r in rows if r.get('phase') in ('resident_baseline','load') or
                           (r.get('kind')=='host_gate_accepted' and r.get('gate')=='probe')]
                result['confirmed_baseline_calls']=sum(r.get('kind')=='phase_start' and
                    r.get('phase')=='resident_baseline' for r in rows)
                counts=result['consumption_bounds']['counts']
                result['confirmed_load_calls']=counts['load']['confirmed_started_at_least']
                if (forbidden or partial or any(counts[k]['confirmed_returned']!=n for k,n in
                    (('runtime',4),('warmup',8),('eligibility',4))) or
                    counts['load']['confirmed_started_at_least']!=0):
                    result['progress_eligibility_error']='unexpected or incomplete diagnostic progression'
            except BaseException as error:result['progress_eligibility_error']=repr(error)
        else:result['progress_eligibility_error']='progress not recovered'
        if result['status']=='observed_preparation_host_stop' and \
           (not isinstance(result.get('host_cleanup'),dict) or not isinstance(result.get('recovery'),dict) or
            result.get('progress_eligibility_error')):
            result['status']='partial_or_unconfirmed'
        try:checkpoints.atomic_new(root/'FINAL_RECEIPT.json',result)
        except BaseException as error:
            result['final_receipt_write_error']=repr(error)
            try:checkpoints.atomic_new(root/'FAILURE_RECEIPT_FALLBACK.json',result)
            except BaseException:pass
        try:checkpoints.atomic_new(registry/'stopped.json',result)
        except BaseException as error:result['registry_write_error']=repr(error)
        try:journal.mark('stopped_no_resume',status=result['status'])
        except BaseException:pass
    return result


def main():
    ap=argparse.ArgumentParser();sub=ap.add_subparsers(dest='action',required=True)
    q=sub.add_parser('prepare');q.add_argument('--source',required=True);q.add_argument('--output',required=True)
    q=sub.add_parser('check');q.add_argument('--plan',required=True)
    q=sub.add_parser('run')
    for key in ('plan','adb','expected-sha'):q.add_argument('--'+key,required=True)
    q.add_argument('--serial');q.add_argument('--approved',action='store_true')
    args=ap.parse_args()
    value=(prepare(args.source,args.output) if args.action=='prepare' else
           check(args.plan) if args.action=='check' else
           run(args.plan,args.adb,args.serial,args.expected_sha,args.approved))
    print(json.dumps(value,ensure_ascii=False,sort_keys=True))
    if args.action=='run' and value['status']!='observed_preparation_host_stop':raise SystemExit(1)


if __name__=='__main__':main()
