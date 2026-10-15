"""Read-only, post-hoc A24 raw-energy comparison. No device or model execution.

Current scale is a named hypothesis, not a calibration. Original reports and
their null validated-J fields remain unchanged. CLI requires a new output dir.
"""
from __future__ import annotations

import argparse
import bisect
import csv
import hashlib
import io
import json
import math
import statistics
import zipfile
from pathlib import Path

NS = 1_000_000_000
ROOT = Path(__file__).resolve().parents[1]
BASE = Path('docs/results/a24_revision02_20261015')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False)+'\n', encoding='utf-8')


def write_csv(path, rows):
    names = list(dict.fromkeys(k for row in rows for k in row))
    with path.open('w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.DictWriter(handle, names)
        writer.writeheader()
        writer.writerows(rows)


def finite(x):
    return type(x) in (int, float) and math.isfinite(x)


def timestamp(sample, mode):
    a, b = sample.get('read_start_ns'), sample.get('read_end_ns')
    if type(a) is not int or type(b) is not int or a < 0 or b < a:
        raise ValueError('invalid sensor read timestamps')
    return {'read_start_ns': a, 'read_end_ns': b, 'read_midpoint_ns': (a+b)//2}[mode]


def integrate(samples, start, end, scale=1000, mode='read_end_ns', max_gap=2_500_000_000):
    """Never drop invalid samples and bridge over them. No tail extrapolation."""
    if end <= start or scale not in (1, 1000):
        raise ValueError('invalid integration contract')
    rows = sorted((timestamp(s, mode), i, s) for i, s in enumerate(samples))
    times = [r[0] for r in rows]
    null = dict(status='BOUNDARY_NOT_BRACKETED', energy_j=None, left_hold_j=None,
                right_hold_j=None, samples=0, max_gap_s=None)
    if len(rows) < 2 or times[0] > start or times[-1] < end:
        return null
    left = bisect.bisect_left(times, start)
    if times[left] != start:
        left -= 1
    right = bisect.bisect_right(times, end)-1
    if times[right] != end:
        right += 1
    selected = rows[left:right+1]
    gaps = [b[0]-a[0] for a, b in zip(selected, selected[1:])]
    if not gaps or any(g <= 0 or g > max_gap for g in gaps):
        return null | dict(status='GAP_OR_DUPLICATE_TIMESTAMP')
    points = []
    for t, _, s in selected:
        i, v = s.get('current_raw'), s.get('voltage_raw')
        if (not finite(i) or i > 0 or i == -2147483648 or
                not finite(v) or v <= 0 or s.get('plugged') != 0 or
                s.get('current_unit') != 'uA_API_DEVICE_UNVERIFIED' or
                s.get('voltage_unit') != 'mV' or s.get('current_valid', True) is not True):
            return null | dict(status='INVALID_OR_CHARGING_SAMPLE')
        points.append((t, -i*v*scale/1e9))
    total = left_total = right_total = 0.
    for (a, x), (b, y) in zip(points, points[1:]):
        lo, hi = max(a, start), min(b, end)
        if hi <= lo:
            continue
        p = x+(y-x)*(lo-a)/(b-a)
        q = x+(y-x)*(hi-a)/(b-a)
        dt = (hi-lo)/NS
        total += (p+q)*.5*dt
        left_total += x*dt
        right_total += y*dt
    return dict(status='CONDITIONAL_READOUT_WINDOW_COVERED', energy_j=total,
                left_hold_j=left_total, right_hold_j=right_total,
                samples=len(selected), max_gap_s=max(gaps)/NS)


def comparison(treatment, reference):
    if treatment is None or reference is None or reference <= 0:
        return dict(delta_J_mA_hypothesis=None, reduction_pct=None)
    return dict(delta_J_mA_hypothesis=treatment-reference,
                reduction_pct=100*(1-treatment/reference))


def request_signature(requests, archive, sid, origin):
    """Compare task/input/deadline/arrival semantics, not realized outcomes."""
    signature = []
    for r in sorted(requests, key=lambda x: x['ordinal']):
        result = json.loads(archive.read(f"{sid}/{r['request_id']}.result.json"))
        signature.append([r['ordinal'], r['task'], r['scheduled_arrival_ns']-origin,
                          r['deadline_ns']-r['scheduled_arrival_ns'],
                          *[result[k] for k in ('model_sha256', 'image_sha256',
                            'input_tensor_sha256', 'adapter_contract', 'canonical_input_contract')]])
    return digest(json.dumps(signature, separators=(',', ':')).encode())


def service(requests, reported):
    if len({r['request_id'] for r in requests}) != len(requests):
        raise ValueError('duplicate requests')
    out = {k: int(reported[k]) for k in ('planned', 'completed', 'failed', 'unfinished')}
    if len(requests) != out['planned']:
        raise ValueError('planned denominator mismatch')
    actual = sum(r['terminal_status'] == 'COMPLETED' for r in requests)
    if actual != out['completed']:
        raise ValueError('completed count mismatch')
    for task in ('C', 'D'):
        selected = [r for r in requests if r['task'] == task]
        successes = [r for r in selected if r['terminal_status'] == 'COMPLETED'
                     and r.get('response_in_service_window') is True]
        on_time = sum(r['response_complete_ns'] <= r['deadline_ns'] for r in successes)
        durations = sorted((r['response_complete_ns']-r['scheduled_arrival_ns'])/1e6 for r in successes)
        p95 = durations[math.ceil(.95*len(durations))-1] if durations else None
        if len(selected) != int(reported[task+'_planned']) or on_time != int(reported[task+'_on_time']):
            raise ValueError('service reconstruction mismatch')
        if p95 is not None and not math.isclose(p95, float(reported[task+'_response_P95_ms_service_successes']), abs_tol=1e-8):
            raise ValueError('P95 reconstruction mismatch')
        out.update({task+'_planned': len(selected), task+'_on_time': on_time, task+'_P95_ms': p95})
    return out


def nonworsening(treatment, reference):
    checks = [treatment['planned'] == reference['planned'],
              treatment['completed'] >= reference['completed'],
              treatment['failed'] <= reference['failed'],
              treatment['unfinished'] <= reference['unfinished']]
    for task in ('C', 'D'):
        checks.append(treatment[task+'_on_time'] >= reference[task+'_on_time'])
    if reference['C_P95_ms'] is not None:
        checks.append(treatment['C_P95_ms'] is not None and treatment['C_P95_ms'] <= reference['C_P95_ms'])
    return all(checks)


def analyze(contract_path, output):
    if output.exists():
        raise FileExistsError('new output directory required')
    contract_bytes = contract_path.read_bytes()
    contract = json.loads(contract_bytes)
    if (contract['schema'] != 'a24-conditional-energy-comparison-v1' or
            contract['assumed_current_uA_per_raw'] != 1000 or
            contract['primary_window_s'] != [0, 180] or contract['max_gap_ns'] != 2_500_000_000):
        raise ValueError('unsupported contract')
    # Snapshot every registered source. All later reads use these bytes.
    snapshots = {}
    for rel, expected in contract['sources'].items():
        data = (ROOT/rel).read_bytes()
        if digest(data) != expected:
            raise ValueError('source SHA mismatch: '+rel)
        snapshots[rel] = data
    sessions, windows, arithmetic = [], [], []
    window_defs = [contract['primary_window_s']]+contract['secondary_windows_s']
    for folder in contract['input_folders']:
        prefix = (BASE/folder).as_posix()+'/'
        reports = list(csv.DictReader(io.StringIO(snapshots[prefix+'sessions.csv'].decode('utf-8-sig'))))
        contexts = {r['session_id']: r for r in csv.DictReader(io.StringIO(snapshots[prefix+'run_context.csv'].decode('utf-8-sig')))}
        catalog = json.loads(snapshots[prefix+'device_raw.sha256.json'])
        raw = snapshots[prefix+'device_raw.zip']
        if digest(raw) != catalog['archive_sha256']:
            raise ValueError('archive SHA mismatch')
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            if len(archive.namelist()) != len(set(archive.namelist())) or set(archive.namelist()) != {m['path'] for m in catalog['members']}:
                raise ValueError('archive member inventory mismatch')
            for member in catalog['members']:
                data = archive.read(member['path'])
                if len(data) != member['bytes'] or digest(data) != member['sha256']:
                    raise ValueError('member SHA mismatch')
            for report in reports:
                sid = report['session_id']; context = contexts[sid]
                summary = json.loads(archive.read(sid+'/summary.json'))
                origin = summary['common_start_ns']
                events = [json.loads(line) for line in archive.read(sid+'/events.jsonl').splitlines()]
                if any(e['session_id'] != sid for e in events):
                    raise ValueError('event session mismatch')
                samples = [e for e in events if e['kind'] == 'sensor_sample']
                requests = json.loads(archive.read(sid+'/requests.json'))
                srv = service(requests, report)
                pre = max((s for s in samples if s['read_end_ns'] <= origin), key=lambda s:s['read_end_ns'])
                ap_ok = report['thermal_window_status'] == 'READOUT_WINDOW_COVERED'
                head = dict(session_id=sid, stage=report['stage'], block=report['block'],
                            recipe=report['recipe'], arm=report['arm'])
                session = head | srv | dict(
                    input_schedule_sha256=request_signature(requests, archive, sid, origin),
                    last_lane_return_relative_s=max(r['lane_available_ns']-origin for r in requests)/NS,
                    pre_origin_SOC_pct=100*pre['battery_level']/pre['battery_scale'],
                    pre_origin_voltage_mV=pre['voltage_raw'],
                    pre_origin_battery_temperature_c=pre['battery_temperature_deci_c']/10,
                    pre_origin_AP_c=float(context['last_preMAIN_reported_AP_c']),
                    AP_window_eligible=ap_ok,
                    AP_mean_c=float(report['mean_AP_c']) if ap_ok else None,
                    AP_peak_c=float(report['observed_peak_AP_c']) if ap_ok else None,
                    source_manifest_sha256_actual=context['source_manifest_sha256_actual'],
                    validated_energy_J=None, validated_energy_savings=None)
                for lo, hi in window_defs:
                    start, end = origin+lo*NS, origin+hi*NS
                    result = integrate(samples, start, end)
                    api = integrate(samples, start, end, scale=1)
                    alternatives = [integrate(samples, start, end, mode=mode)
                                    for mode in contract['timestamp_sensitivity']]
                    energy = result['energy_j']
                    delta = max(abs(x['energy_j']-energy) for x in alternatives) if energy is not None and all(x['energy_j'] is not None for x in alternatives) else None
                    windows.append(head | dict(window_start_s=lo, window_end_s=hi,
                        status=result['status'], J_mA_hypothesis=energy, J_API_uA_hypothesis=api['energy_j'],
                        left_hold_J_mA_hypothesis=result['left_hold_j'], right_hold_J_mA_hypothesis=result['right_hold_j'],
                        read_timestamp_max_abs_delta_J=delta,
                        numerical_method_spread_J=(max(energy,result['left_hold_j'],result['right_hold_j'])-min(energy,result['left_hold_j'],result['right_hold_j'])) if energy is not None else None,
                        max_sample_gap_s=result['max_gap_s'], sample_count=result['samples'],
                        validated_energy_J=None))
                    if energy is not None:
                        if not math.isclose(energy, api['energy_j']*1000, rel_tol=1e-12):
                            raise ValueError('unit scale arithmetic failed')
                        # Independent frozen engine, used only on full-valid windows.
                        from d1_a24_measurement_analysis import integrate_window
                        old = integrate_window([(s['read_end_ns'],-s['current_raw']*s['voltage_raw']/1e9) for s in samples], start, end, contract['max_gap_ns'])
                        if old['integral'] is None or not math.isclose(energy,old['integral']*1000,rel_tol=1e-12):
                            raise ValueError('frozen engine cross-check failed')
                        arithmetic.append(dict(session_id=sid,window=[lo,hi],frozen_engine_agreement=True,unit_scale_agreement=True))
                    if [lo,hi] == contract['primary_window_s']:
                        session.update(J180_mA_hypothesis=energy, energy_status=result['status'])
                    if [lo,hi] == [0,35]:
                        session['pre_request_mean_W_mA_hypothesis'] = energy/35 if energy is not None else None
                sessions.append(session)
    pairs = []
    for treatment in sessions:
        for recipe, arm, ref in contract['comparisons']:
            if (treatment['recipe'], treatment['arm']) != (recipe, arm):
                continue
            reference = next((r for r in sessions if (r['stage'],r['block'],r['recipe'],r['arm']) == (treatment['stage'],treatment['block'],recipe,ref)),None)
            if reference is None:
                continue
            if treatment['input_schedule_sha256'] != reference['input_schedule_sha256']:
                raise ValueError('unmatched request/input/deadline pair')
            for lo,hi in window_defs:
                def win(s):
                    return next(w for w in windows if w['session_id']==s['session_id'] and (w['window_start_s'],w['window_end_s'])==(lo,hi))
                a,b=win(treatment),win(reference)
                pair = dict(stage=treatment['stage'],block=treatment['block'],recipe=recipe,
                    treatment=arm,reference=ref,window_start_s=lo,window_end_s=hi,
                    treatment_J_mA_hypothesis=a['J_mA_hypothesis'], reference_J_mA_hypothesis=b['J_mA_hypothesis'],
                    **comparison(a['J_mA_hypothesis'],b['J_mA_hypothesis']),
                    service_nonworsening_descriptive=nonworsening(treatment,reference),
                    delta_pre_request_W=treatment['pre_request_mean_W_mA_hypothesis']-reference['pre_request_mean_W_mA_hypothesis'] if treatment['pre_request_mean_W_mA_hypothesis'] is not None and reference['pre_request_mean_W_mA_hypothesis'] is not None else None,
                    delta_pre_AP_c=treatment['pre_origin_AP_c']-reference['pre_origin_AP_c'],
                    delta_pre_SOC_pct=treatment['pre_origin_SOC_pct']-reference['pre_origin_SOC_pct'],
                    AP_comparison_eligible=treatment['AP_window_eligible'] and reference['AP_window_eligible'],
                    validated_energy_savings=None)
                api_pct=comparison(a['J_API_uA_hypothesis'],b['J_API_uA_hypothesis'])['reduction_pct']
                if pair['reduction_pct'] is not None and not math.isclose(pair['reduction_pct'],api_pct,abs_tol=1e-10):
                    raise ValueError('relative scale cancellation failed')
                pairs.append(pair)
    # Freeze inputs against concurrent writes before publishing derived files.
    if contract_path.read_bytes()!=contract_bytes or any((ROOT/rel).read_bytes()!=data for rel,data in snapshots.items()):
        raise ValueError('input changed during analysis')
    output.mkdir(parents=True,exist_ok=False)
    for name,rows in [('sessions',sessions),('windows',windows),('pairs',pairs)]:
        dump(output/(name+'.json'),rows);write_csv(output/(name+'.csv'),rows)
    summary=dict(schema=contract['schema'], contract_sha256=digest(contract_bytes),
        source_code_sha256=digest(Path(__file__).read_bytes()),
        sessions=len(sessions),planned=sum(s['planned'] for s in sessions),
        completed=sum(s['completed'] for s in sessions),failed=sum(s['failed'] for s in sessions),
        unfinished=sum(s['unfinished'] for s in sessions), windows=len(windows),
        valid_windows=sum(w['J_mA_hypothesis'] is not None for w in windows),
        primary_comparisons=sum(p['window_start_s']==0 and p['window_end_s']==180 for p in pairs),
        arithmetic_checks=len(arithmetic),device_commands=0,new_sessions=0,
        coefficients_modified=False, independent_energy_validation=False,
        validated_energy_J=None,validated_energy_savings=None,
        scope=contract['scope_excludes'])
    dump(output/'verification.json',summary|dict(arithmetic=arithmetic,inputs_sha256=contract['sources']))
    print(json.dumps(summary,ensure_ascii=False))
    return sessions, windows, pairs


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('contract',type=Path);parser.add_argument('output',type=Path)
    args=parser.parse_args();analyze(args.contract,args.output)
