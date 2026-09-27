"""One-shot evidence recovery and cleanup after COLLECT-04 host runner exit.

No session, installation, staging, or inference is started. This is not a resume.
"""
import argparse
import json
from pathlib import Path
import time

from tools import d1_arrival_plan as p
from tools import d1_arrival_timing_calibration as cal
from tools import d1_arrival_timing_calibration_device as shared
from tools import d1_energy_collection_device as collection
from tools import d1_energy_state_collection as state
from tools import d1_adb_observed_client as observed
from tools import d1_recorded_process as rp


def run(plan_file, adb, output):
    plan_file=Path(plan_file);plan=p.read(plan_file);output=Path(output)
    if plan['experiment_id']!=state.EXPERIMENT or output.exists():
        raise ValueError('only fresh COLLECT-04 recovery output is allowed')
    root=Path(plan['output_root'])
    first=root/('00_'+plan['entries'][0]['session_id'])/'launch_attempt.json'
    if (root/'FINAL_RECEIPT.json').exists() or not first.exists():
        raise ValueError('no abandoned launched first session to recover')
    output.mkdir(parents=True)
    start=time.monotonic();hard=start+150
    cal.write_new(output/'claim.json',dict(utc=rp.utc(),plan_sha256=p.digest(plan_file),
                                          purpose='evidence_then_cleanup_only',seconds_cap=150))
    device=observed.ObservedDevice(adb,None,output/'commands',allow_select=True,
                                   forbid_apk_deploy=True)
    device.deadline=hard-45
    result=dict(status='unconfirmed',utc_start=rp.utc(),plan_sha256=p.digest(plan_file),
                session_id=plan['entries'][0]['session_id'],device_confirmed=False,
                recovery=None,app_cleanup=None,host_cleanup=None)
    try:
        identity=device.identify(plan['device_fingerprint'])
        hardware=device.call('shell','getprop','ro.serialno',timeout=3).stdout.decode().strip()
        if hardware!=plan['device_hardware_serial']:raise ValueError('hardware mismatch')
        result['device_confirmed']=True
        remote=f"files/{plan['protocol']}/{plan['entries'][0]['session_id']}"
        try:
            result['recovery']=collection.recover(device,remote,output/'artifacts',True)
        except BaseException as exc:
            result['recovery_error']=repr(exc)
        app_cleanup=output/'artifacts'/'cleanup.json'
        if app_cleanup.exists():
            try:result['app_cleanup']=json.loads(app_cleanup.read_text(encoding='utf-8'))
            except Exception as exc:result['app_cleanup_error']=repr(exc)
        try:
            result['host_cleanup']=shared.cleanup(device,hard)
        except BaseException as exc:
            result['host_cleanup_error']=repr(exc)
        result['status']='recovered_and_stopped' if result['recovery'] and result['host_cleanup'] else 'partial_recovery_or_cleanup_unconfirmed'
    except BaseException as exc:
        result['error']=repr(exc)
    finally:
        progress=output/'recovery_prefix'/'progress.jsonl'
        try:result['progress_bounds']=state.progress_consumption(progress.read_bytes() if progress.exists() else b'',True)
        except Exception as exc:result['progress_bounds_error']=repr(exc)
        result['elapsed_seconds']=time.monotonic()-start
        result['utc_end']=rp.utc()
        result['adb_command_slots']=device.sequence
        cal.write_new(output/'RESCUE_RECEIPT.json',result)
    return result


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--plan',required=True);parser.add_argument('--adb',required=True)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    print(run(args.plan,args.adb,args.output))


if __name__=='__main__':main()
