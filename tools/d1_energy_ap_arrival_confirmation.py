"""PC-only arrival confirmation input and start-AP evidence screen.

This does not arm an Android session. The current app cannot enforce a numeric
AP gate at workload start; Check deliberately returns a blocked status.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import statistics
import uuid
from pathlib import Path

from tools import d1_arrival_energy_collection as arrival

ROOT = Path(__file__).resolve().parents[1]
FROZEN_SHA = '35ed6987b1fc09789284018f8502107eaf4e3125373651a01e3a08d427034c54'
EXPERIMENT = 'ENERGY-AP-ARRIVAL-CONFIRM-DESIGN-01'
SOURCE_TIMELINE = ROOT / 'docs/results/arrival_visualization_01/timeline.csv'
SCENARIO = 'queue'
POLICY = 'FIXED_SPLIT'
SEED = 201  # PC timing-screen seed; Android offset rule has no random draw.


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def start_ap_evidence(samples: list[dict], start_ns: int, low: float, high: float,
                      max_age_ns: int = 3_000_000_000) -> dict:
    """Screen *recorded* start evidence, never authorize a future app start.

    Timestamp of a host read is its interval end, not the last hardware update.
    A passing sample cannot prove AP stayed in range after that read.
    """
    valid = [s for s in samples if s.get('after_ns', s.get('mono_ns', 0)) <= start_ns]
    if not valid:
        return dict(eligible=False, reason='missing_before_start')
    sample = max(valid, key=lambda s: s.get('after_ns', s['mono_ns']))
    before = sample.get('before_ns', sample['mono_ns'])
    after = sample.get('after_ns', sample['mono_ns'])
    if before > after or (after - before) > 4_000_000_000:
        return dict(eligible=False, reason='uncertain_clock')
    age = start_ns - after
    if age > max_age_ns:
        return dict(eligible=False, reason='stale_sample', age_ns=age)
    try:
        ap = float(sample['AP'])
    except (KeyError, TypeError, ValueError):
        return dict(eligible=False, reason='missing_numeric_ap')
    if sample.get('thermal_status') != '0':
        return dict(eligible=False, reason='thermal_status_not_zero')
    if not low <= ap <= high:
        return dict(eligible=False, reason='outside_initial_support', ap_c=ap,
                    age_ns=age)
    return dict(eligible=True, reason='retrospective_fresh_sample_only', ap_c=ap,
                age_ns=age, proves_start_gate=False)


def _intervals(values: list[int]) -> dict:
    gaps = [(b - a) / 1e9 for a, b in zip(values, values[1:])]
    if not gaps or any(x <= 0 for x in gaps):
        raise ValueError('missing or nonmonotonic sensor timestamps')
    return dict(samples=len(values), median_interval_s=round(statistics.median(gaps), 6),
                max_gap_s=round(max(gaps), 6))


def screen_raw(run: Path) -> dict:
    sessions = list(run.glob('00_*/artifacts/progress.jsonl'))
    if len(sessions) != 1:
        raise ValueError('expected exactly one immutable short-transition session')
    progress_path = sessions[0]
    session = progress_path.parent.parent
    thermal_path = session / 'thermal.jsonl'
    progress = [json.loads(line) for line in progress_path.read_text(encoding='utf-8').splitlines()]
    thermal = [json.loads(line) for line in thermal_path.read_text(encoding='utf-8').splitlines()]
    start = next(x['mono_ns'] for x in progress if x.get('kind') == 'phase_start' and x.get('phase') == 'load')
    end = next(x['mono_ns'] for x in progress if x.get('kind') == 'phase_end' and x.get('phase') == 'post_work_wait')
    power = [x for x in progress if x.get('kind') == 'power_sample' and start <= x['mono_ns'] <= end]
    ap = [x for x in thermal if start <= x['mono_ns'] <= end and x.get('AP') not in (None, '')]
    if not power or not ap:
        raise ValueError('no common-window sensor evidence')
    lanes = [x for x in progress if x.get('kind') == 'lane_available' and x.get('phase') == 'load']
    durations = [(x['lane_available_ns'] - x['dispatch_ns']) / 1e9 for x in lanes]
    if any(d <= 0 for d in durations):
        raise ValueError('invalid lane duration')
    return dict(source='A24 short-transition diagnostic; not an arrival session',
                source_sha256={'progress': sha(progress_path), 'thermal': sha(thermal_path)},
                common_window_s=round((end-start)/1e9, 6),
                power=_intervals([x['mono_ns'] for x in power]),
                ap=_intervals([x['mono_ns'] for x in ap]),
                consecutive_repeated_ap_fraction=round(sum(a['AP'] == b['AP'] for a,b in zip(ap,ap[1:]))/(len(ap)-1), 6),
                request_lane=dict(count=len(lanes), median_s=round(statistics.median(durations), 6),
                                  max_s=round(max(durations), 6)),
                start_ap_evidence=start_ap_evidence(thermal, start, 32.5, 34.0),
                note='query interval is not hardware update interval; requests cannot receive individual power coefficients')


def prepare(frozen_path: Path, run: Path, output: Path) -> dict:
    if output.exists():
        raise FileExistsError(output)
    frozen = json.loads(frozen_path.read_text(encoding='utf-8'))
    if sha(frozen_path) != FROZEN_SHA or frozen['version'] != 'energy-ap-state-regimen-fit-v1':
        raise ValueError('frozen model mismatch')
    if frozen['initial_ap_development_range_c'] != [32.5, 34.0]:
        raise ValueError('initial AP support changed')
    screen = screen_raw(run)
    sid = str(uuid.uuid5(uuid.NAMESPACE_URL, EXPERIMENT + '/queue/FIXED_SPLIT'))
    requests = arrival.requests(SCENARIO, sid)
    if len(requests) != 24 or [r['offset_ms'] for r in requests] != list(range(0,4800,200)):
        raise ValueError('arrival generator drift')
    with SOURCE_TIMELINE.open(encoding='utf-8-sig', newline='') as stream:
        rows = [r for r in csv.DictReader(stream) if (r['mode'],r['scenario'],r['seed'],r['policy']) ==
                ('strict',SCENARIO,str(SEED),POLICY)]
    if len(rows) != 24:
        raise ValueError('stored timing screen drift')
    output.mkdir(parents=True)
    write(output/'sensor_screen.json', screen)
    with (output/'requests.csv').open('w', encoding='utf-8', newline='') as stream:
        writer=csv.DictWriter(stream, fieldnames=list(requests[0]))
        writer.writeheader();writer.writerows(requests)
    manifest = dict(experiment_id=EXPERIMENT, status='PC_INPUT_FIXED_RUN_BLOCKED',
        approval='not_approved', experiment_ready=False, scenario=SCENARIO,
        policy=POLICY, timing_screen_seed=SEED, android_generator_seed=None,
        planned_requests=24, research_deadline_ms={'urgent':1500,'normal':6000},
        requests=requests, common_window_seconds=120, resident_baseline_seconds=30,
        cooling_seconds=60, drain_seconds=30, denominator='all 24 planned requests',
        planned_arrivals_independent_of_completion=True,
        initial_ap_gate=dict(sensor='HAL numeric AP mName=AP mType=0',
            initial_development_range_c=frozen['initial_ap_development_range_c'],
            observed_path_range_c=frozen['ap_development_observed_range_c'],
            prospective_rule='must be enforced at actual common-window start before dispatch',
            retrospective_max_sample_age_seconds=3,
            retrospective_only=True, run_authorization=False),
        model=dict(version=frozen['version'], sha256=FROZEN_SHA,
            states=frozen['states'], allowed_assigned_states=['classification_CPU','detection_GPU',
                'classification_CPU+detection_GPU','resident_idle'],
            strict_arrival_support=False),
        prediction_a='recorded actual state boundaries plus observed initial AP; frozen power/AP only; no later measured current/AP as inputs',
        prediction_b='planned arrivals plus pre-frozen service model; not yet validated for current APK/protocol',
        source=dict(generator='tools/d1_arrival_energy_collection.py:requests',
                    timing_screen='docs/results/arrival_visualization_01/timeline.csv',
                    timing_screen_sha256=sha(SOURCE_TIMELINE),
                    requests_csv_sha256=sha(output/'requests.csv'),
                    sensor_screen_sha256=sha(output/'sensor_screen.json')),
        blocking_reasons=['Android arrival runner cannot read numeric AP at load start',
                          'host has no pre-load gate after resident baseline',
                          'current signed APK/source identity does not match old 12-session arrival plan',
                          'frozen regimen strict interface does not support arbitrary arrival transitions'],
        device_command_budget=0, session_budget=0, registry=None, output_root=None)
    write(output/'input_manifest.json', manifest)
    return check(output/'input_manifest.json')


def check(file: Path) -> dict:
    m = json.loads(file.read_text(encoding='utf-8'))
    if m['experiment_id'] != EXPERIMENT or m['status'] != 'PC_INPUT_FIXED_RUN_BLOCKED':
        raise ValueError('not the blocked design input')
    if m['source']['sensor_screen_sha256'] != sha(file.parent/'sensor_screen.json'):
        raise ValueError('sensor screen changed')
    if m['source']['requests_csv_sha256'] != sha(file.parent/'requests.csv'):
        raise ValueError('request CSV changed')
    if m['source']['timing_screen_sha256'] != sha(SOURCE_TIMELINE):
        raise ValueError('timing source changed')
    if m['model']['sha256'] != FROZEN_SHA or m['requests'] != arrival.requests(SCENARIO,
            str(uuid.uuid5(uuid.NAMESPACE_URL, EXPERIMENT + '/queue/FIXED_SPLIT'))):
        raise ValueError('model or requests changed')
    if m['device_command_budget'] != 0 or m['session_budget'] != 0 or m['registry'] is not None:
        raise ValueError('blocked design cannot consume a device session')
    return dict(status=m['status'], manifest_sha256=sha(file), device_commands=0,
                runnable=False, blocking_reasons=m['blocking_reasons'])


def main() -> None:
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest='action',required=True)
    a=sub.add_parser('prepare');a.add_argument('--frozen',type=Path,required=True)
    a.add_argument('--run',type=Path,required=True);a.add_argument('--output',type=Path,required=True)
    b=sub.add_parser('check');b.add_argument('--manifest',type=Path,required=True)
    args=p.parse_args()
    result=prepare(args.frozen,args.run,args.output) if args.action=='prepare' else check(args.manifest)
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__': main()
