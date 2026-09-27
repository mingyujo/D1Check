"""One-shot, manually approved evidence recovery for a *new* state collection.

Never resumes a session, starts inference, or kills a host process. If the
recorded parent/child identity cannot be resolved, no device command is issued.
"""

import argparse
import json
from pathlib import Path
import time
import traceback

from tools import d1_arrival_plan as p
from tools import d1_arrival_timing_calibration_device as shared
from tools import d1_arrival_device as legacy
from tools import d1_energy_collection_device as collection
from tools import d1_energy_host_checkpoints as checkpoints
from tools import d1_energy_host_lifecycle as lifecycle
from tools.d1_adb_observed_client import ObservedDevice


def last_attempt(plan):
    root=Path(plan['output_root'])
    attempts=[]
    for entry in plan['entries']:
        folder=root/f"{entry['index']:02d}_{entry['session_id']}"
        if (folder/'launch_attempt.json').exists():
            attempts.append((entry,folder))
    return attempts[-1] if attempts else (None,None)


def remaining_budget(plan):
    """Host monotonic clock is comparable only within the same Windows boot."""
    try:
        first=p.read(Path(plan['output_root'])/'host_checkpoints/0000.json')
        elapsed=time.monotonic()-float(first['monotonic'])
        if elapsed<0 or elapsed>plan['budget']['total_seconds']+86400:
            return None
        return max(0,plan['budget']['total_seconds']-elapsed)
    except (OSError,ValueError,KeyError,TypeError):
        return None


def check(plan_file, output):
    plan_file=Path(plan_file);plan=p.read(plan_file);output=Path(output)
    digest=p.digest(plan_file)
    if output.exists():
        receipt=output/'RECOVERY_RECEIPT.json'
        return dict(status='already_recorded' if receipt.exists() else 'claimed_unconfirmed',
                    device_commands=0)
    state=lifecycle.inspect_run(plan['output_root'],plan['registry'],digest)
    remaining=remaining_budget(plan)
    entry,folder=last_attempt(plan)
    return dict(status=state['status'],recoverable=state['recoverable'] and entry is not None and
                remaining is not None and remaining>=60,
                host=state,remaining_plan_seconds=remaining,
                session_id=entry['session_id'] if entry else None,device_commands=0)


def run(plan_file, output, adb, expected_sha, approved, seconds_cap=150):
    plan_file=Path(plan_file);output=Path(output)
    if not approved or p.digest(plan_file)!=expected_sha or not 60<=seconds_cap<=300:
        raise ValueError('explicit bounded recovery approval and frozen plan hash required')
    if output.exists():
        receipt=output/'RECOVERY_RECEIPT.json'
        return p.read(receipt) if receipt.exists() else dict(status='claimed_unconfirmed',device_commands=0)
    gate=check(plan_file,output)
    if not gate['recoverable']:
        return dict(status='recovery_blocked',gate=gate,device_commands=0)
    plan=p.read(plan_file);entry,folder=last_attempt(plan)
    output.mkdir(parents=True,exist_ok=False)
    start=time.monotonic();actual_cap=min(seconds_cap,gate['remaining_plan_seconds'])
    hard=start+actual_cap
    checkpoints.atomic_new(output/'claim.json',dict(plan_sha256=expected_sha,
        session_id=entry['session_id'],utc=checkpoints.utc(),purpose='evidence_and_cleanup_only',
        budget_seconds=actual_cap,host=gate['host']))
    result=dict(status='recovery_unconfirmed',plan_sha256=expected_sha,
                session_id=entry['session_id'],start_utc=checkpoints.utc(),
                host=gate['host'],app_cleanup='unconfirmed',host_cleanup='unconfirmed',
                recovery='unconfirmed',no_session_resume=True)
    device=None
    try:
        device=ObservedDevice(adb,None,output/'commands',allow_select=True,forbid_apk_deploy=True)
        device.deadline=hard-45
        result['device_identity']=device.identify(plan['device_fingerprint'])
        serial=device.call('shell','getprop','ro.serialno',timeout=3).stdout.decode().strip()
        if serial!=plan['device_hardware_serial']:
            raise ValueError('hardware identity mismatch; do not touch other device')
        remote=f"files/{plan['protocol']}/{entry['session_id']}"
        # Small durable prefix before host stop if it fits. A long archive is
        # never allowed to consume the 45-second cleanup reservation.
        if hard-time.monotonic()>75:
            prefix=output/'pre_stop';prefix.mkdir()
            for name in ('manifest.json','progress.jsonl','cleanup.json'):
                if hard-time.monotonic()<=60:break
                try:collection.pull_file(device,remote,name,prefix)
                except BaseException as error:
                    result.setdefault('pre_stop_errors',{})[name]=repr(error)
        app_present=None;app_owner_confirmed=False
        try:
            observed=device.call('shell','pidof',legacy.PACKAGE+':model_probe',timeout=3,check=False)
            app_present=observed.returncode==0 and bool(observed.stdout.strip())
            result['app_process_before_host_stop']=dict(exit_code=observed.returncode,
                present=app_present,query_succeeded=observed.returncode in (0,1))
            if observed.returncode not in (0,1):app_present=None
            if app_present:
                activity=device.call('shell','dumpsys','activity','activities',timeout=5).stdout.decode(errors='replace')
                app_owner_confirmed=(entry['session_id'] in activity and collection.ACTIVITY in activity)
                result['app_owner_confirmed']=app_owner_confirmed
        except BaseException as error:
            result['app_process_before_host_stop']=dict(status='unconfirmed',error=repr(error))
            app_present=None
        original=Path(plan['output_root'])/'FINAL_RECEIPT.json'
        previous=None
        if original.exists():
            try:previous=p.read(original).get('host_cleanup')
            except BaseException as error:result['prior_receipt_read_error']=repr(error)
        if isinstance(previous,dict) and previous.get('status')=='completed':
            result['host_cleanup']=dict(status='already_confirmed_in_original_receipt')
            result['host_requested_stop']=False
        elif app_present is False:
            result['host_cleanup']=dict(status='app_process_absent_at_check')
            result['host_requested_stop']=False
        elif app_present is None or not app_owner_confirmed:
            result['host_cleanup']=dict(status='blocked_app_owner_unconfirmed')
            result['host_requested_stop']=False
        else:
            try:
                result['host_cleanup']=shared.cleanup(device,hard)
                result['host_requested_stop']=True
            except BaseException as error:
                result['host_cleanup_error']=repr(error)
                result['host_requested_stop']='unconfirmed'
        # App files may be read after the process is stopped. Keep all recovery
        # failures independent of cleanup failures.
        if hard-time.monotonic()>20:
            device.deadline=hard
            try:result['recovery']=collection.recover(device,remote,output/'artifacts',True)
            except BaseException as error:result['recovery_error']=repr(error)
        else:result['recovery']='skipped_insufficient_reserve'
        for candidate in (output/'artifacts/cleanup.json',output/'pre_stop/cleanup.json'):
            if candidate.exists():
                try:result['app_cleanup']=json.loads(candidate.read_text(encoding='utf-8-sig'))
                except BaseException as error:result['app_cleanup_error']=repr(error)
                break
        good_cleanup=isinstance(result['host_cleanup'],dict) and result['host_cleanup'].get('status') in (
            'completed','already_confirmed_in_original_receipt','app_process_absent_at_check')
        result['status']='recovery_recorded' if good_cleanup else 'partial_or_unconfirmed'
    except BaseException as error:
        result.update(status='partial_or_unconfirmed',error=repr(error),stack=traceback.format_exc())
    finally:
        result.update(end_utc=checkpoints.utc(),elapsed_seconds=time.monotonic()-start,
                      adb_command_slots=device.sequence if device else 0)
        try:checkpoints.atomic_new(output/'RECOVERY_RECEIPT.json',result)
        except BaseException as error:
            result['receipt_write_error']=repr(error)
            try:checkpoints.atomic_new(output/'RECOVERY_RECEIPT_FALLBACK.json',result)
            except BaseException:pass
    return result


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=('check','run'))
    parser.add_argument('--plan',required=True);parser.add_argument('--output',required=True)
    parser.add_argument('--adb');parser.add_argument('--expected-sha');parser.add_argument('--approved',action='store_true')
    parser.add_argument('--seconds-cap',type=int,default=150)
    args=parser.parse_args()
    value=(check(args.plan,args.output) if args.action=='check' else
           run(args.plan,args.output,args.adb,args.expected_sha,args.approved,args.seconds_cap))
    print(json.dumps(value,ensure_ascii=False,sort_keys=True))
    if args.action=='run' and value['status'] not in ('recovery_recorded','already_recorded'):
        raise SystemExit(1)


if __name__=='__main__':main()
