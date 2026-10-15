"""Bounded passive AP observation only. Never starts an app, inference, or a claim."""
import argparse
import datetime
import json
import time
from pathlib import Path
from d1_a24_laptop_validator import load_json
from d1_a24_revision02_control import read_hal, atomic_json
from d1_a24_revision02_window import BoundedClient, check_deadline
from d1_a24_revision02_design import matches_fixed_reference, NS


def observe(job_path, window_path, reference_path, output):
    job, window, reference = map(load_json, [job_path, window_path, reference_path])
    target = load_json(Path(job['device_registration']))
    output.mkdir(exist_ok=False)
    client = BoundedClient(job, target, window)
    assert client.command('shell', 'getprop', 'ro.serialno').decode().strip() == target['hardware_serial']
    assert client.command('shell', 'getprop', 'ro.build.fingerprint').decode().strip() == target['build_fingerprint']
    samples = []
    matched = False
    rules = dict(history_ns=60*NS, maximum_wait_ns=3600*NS, maximum_gap_ns=10*NS,
                 tolerance_c=.5, maximum_abs_slope_c_per_min=.1)
    with (output/'readings.jsonl').open('x', encoding='utf-8') as stream:
        while time.time() < datetime.datetime.fromisoformat(window['hard_stop_UTC']).timestamp()-8:
            record = read_hal(client)
            stream.write(json.dumps(record)+'\n'); stream.flush()
            ap = [s['value_c'] for s in record['sensors'] if s['sensor_name']=='AP' and s['sensor_type']==0]
            samples.append(dict(before_ns=record['device_elapsed_before_ns'],after_ns=record['device_elapsed_after_ns'],AP_c=ap[0] if len(ap)==1 else None))
            if len(ap)==1:
                matched = matches_fixed_reference(samples, samples[0]['before_ns'], reference, rules)
            print(json.dumps({'UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'AP_c':ap,'passive_60s_match':matched,'app_starts':0,'inference':0}),flush=True)
            if matched: break
            check_deadline(window,'RPC');time.sleep(5)
    atomic_json(output/'PASSIVE_STOPPED.json',{'passive_60s_match':matched,'source_reference_c':reference['Tref_c'],
        'actual_stop_UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'device_calls':client.actual_calls,
        'app_starts':0,'inference':0,'START_or_claim':0,'does_not_prove_post_warmup_admission':True})


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['job','window','reference','output']:p.add_argument(name,type=Path)
    a=p.parse_args();observe(a.job,a.window,a.reference,a.output)
