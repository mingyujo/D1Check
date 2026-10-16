"""Archive-only cooling/service study. No runner, device or RL dependencies."""
import argparse
import bisect
import csv
import hashlib
import json
import math
import re
import time
import traceback
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / 'docs/results/recovery_service_01'
MODEL = ROOT / 'docs/results/online_policy_study_01/overnight_sustained_run01/model.json'
FIELDS = ('dispatch_ns', 'execution_start_ns', 'output_ready_ns', 'persist_complete_ns',
          'worker_release_ns', 'lane_available_ns')
PHASES = ('dispatch_to_execution', 'execution_to_output', 'output_to_persist',
          'persist_to_worker_release', 'worker_release_to_lane')
METRICS = (*PHASES, 'invocation', 'execution_to_invoke', 'lane_total', 'response')
VERSION = 'recovery-service-pre-ap-v1'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf8'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf8')


def csv_write(path, rows):
    if not rows:
        raise ValueError('empty output table')
    with Path(path).open('w', encoding='utf8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)


def phase_values(row):
    values = [row[k] for k in FIELDS]
    if any(not isinstance(x, int) for x in values) or any(b < a for a, b in zip(values, values[1:])):
        raise ValueError('missing or reversed five-phase boundary')
    invoke = [row[k] for k in ('host_inference_start_ns', 'host_inference_return_ns')]
    if not values[1] <= invoke[0] <= invoke[1] <= values[2]:
        raise ValueError('invocation outside execution/output boundary')
    out = {k: (b-a)/1e6 for k, a, b in zip(PHASES, values, values[1:])}
    out.update(invocation=(invoke[1]-invoke[0])/1e6,
               execution_to_invoke=(invoke[0]-values[1])/1e6,
               lane_total=(values[-1]-values[0])/1e6,
               response=(row['output_ready_ns'] if row['task_id'] == 'classification' else row['persist_complete_ns']) / 1e6 - row['scheduled_arrival_ns']/1e6)
    if not math.isclose(sum(out[k] for k in PHASES), out['lane_total'], abs_tol=1e-8):
        raise ValueError('phase partition does not preserve lane total')
    return out


def prior_ap(samples, start, max_age_s=10):
    # Return-end is authoritative for causality. Midpoint is only a plotting clock.
    eligible = [r for r in samples if r['after_ns'] <= start]
    if not eligible:
        return None
    r = max(eligible, key=lambda x: x['after_ns'])
    if start-r['after_ns'] > max_age_s*1e9:
        return None
    return r


def union_overlap(start, end, intervals):
    clipped = sorted((max(start, a), min(end, b)) for a, b in intervals if a < end and b > start)
    length = 0; last = start
    for a, b in clipped:
        a = max(a, last)
        if b > a:
            length += b-a
        last = max(last, b)
    return length / (end-start) if end > start else 0.


def semantic_requests(rows):
    return [(r['ordinal'], r['task_id'], r['priority'], r['offset_ms'], r['deadline_ms']) for r in rows]


def extract(external, output):
    output = Path(output); output.mkdir(parents=True, exist_ok=False)
    src = read(ROOT/'docs/results/preboundary_evidence_01/run_v1/source_inventory.json')
    expected = read(ROOT/'docs/results/history_model_refinement_01/source_inventory.json')['raw_source_hashes']
    case_rows = []; requests = []; hashes = {}; identities = []
    for identity, location in src['source_locations'].items():
        folder = Path(external)/location
        files = {n: folder/'artifacts'/n for n in ('history_boundary.json', 'conditioning_requests.json', 'requests.json')}
        files['thermal.jsonl'] = folder/'thermal.jsonl'
        files['progress.jsonl'] = folder/'artifacts/progress.jsonl'
        files['input_manifest.json'] = folder/'input_manifest.json'
        for name, path in files.items():
            h = sha(path)
            if name != 'input_manifest.json' and h != expected[identity+'/'+name]:
                raise ValueError('registered raw source changed: '+identity+'/'+name)
            hashes[identity+'/'+name] = h
        m = read(files['input_manifest.json']); boundary = read(files['history_boundary.json'])
        if m['phase'] != identity or boundary['runtime_recreated'] or boundary['additional_warmup'] != 0:
            raise ValueError('changed identity/runtime/history')
        gap = int(m['history_recovery_seconds']); role = identity.split('_')[0]
        policy = identity.split('_')[-1]
        if gap not in (30, 180) or role not in ('development', 'confirmation') or policy not in ('C0', 'CPU', 'PAR'):
            raise ValueError('unexpected roster')
        core = dict(apk=m['apk_sha256'], protocol=m['protocol'], history=m['history_control_version'],
                    power=m['power_sampling_version'], period_ms=m['power_sample_period_ms'], threads=m['cpu_threads'],
                    models={k: dict(sha=v['model']['sha256'], runtime=v['runtime'], tensor=v['tensor']) for k, v in m['models'].items()},
                    images=[r['sha256'] for r in m['images']], conditioning=semantic_requests(m['conditioning_requests']))
        if identities and core != identities[0]:
            raise ValueError('APK/model/input/runtime/conditioning differs across sessions')
        identities.append(core)
        raw = [json.loads(x) for x in files['thermal.jsonl'].read_text(encoding='utf8').splitlines()]
        thermal = []
        for r in raw:
            if r.get('AP') in (None, ''):
                continue
            if not r['before_ns'] <= r['mono_ns'] <= r['after_ns']:
                raise ValueError('invalid AP clock bracket')
            section = r['raw'].split('Current temperatures from HAL:', 1)[1].split('Current cooling devices from HAL:', 1)[0]
            match = re.search(r'mValue=([-+0-9.eE]+),[^\n]*mName=AP,', section)
            if not match or float(match.group(1)) != float(r['AP']):
                raise ValueError('not the registered current HAL numeric AP')
            thermal.append(dict(before_ns=r['before_ns'], mono_ns=r['mono_ns'], after_ns=r['after_ns'],
                                ap=float(r['AP']), status=r['thermal_status']))
        thermal.sort(key=lambda r: r['after_ns'])
        conditioning = read(files['conditioning_requests.json']); target = read(files['requests.json'])
        if len(conditioning) != 96 or len(target) != (0 if policy == 'C0' else 96):
            raise ValueError('incomplete request denominator')
        if max(r['lane_available_ns'] for r in conditioning) > boundary['recovery_start_ns']:
            raise ValueError('recovery before conditioning lane release')
        target_start = min((r['dispatch_ns'] for r in target), default=boundary['target_start_ns']+35_000_000_000)
        initial = prior_ap(thermal, target_start)
        cond_end = prior_ap(thermal, boundary['recovery_start_ns'])
        if initial is None or cond_end is None:
            raise ValueError('missing fresh pre-target or conditioning-end AP')
        idle = [r for r in thermal if boundary['recovery_start_ns'] <= r['before_ns'] and r['after_ns'] <= target_start]
        if len(idle) < 3 or any(b['mono_ns']-a['mono_ns'] > 10e9 for a, b in zip(idle, idle[1:])):
            raise ValueError('incomplete recovery AP')
        tt = np.array([(r['mono_ns']-idle[0]['mono_ns'])/1e9 for r in idle]); yy = np.array([r['ap'] for r in idle])
        slope = float(np.linalg.lstsq(np.column_stack((np.ones(len(tt)), tt)), yy, rcond=None)[0][1])
        origin = boundary['conditioning_start_ns']
        case_rows.append(dict(session=identity, role=role, gap_s=gap, policy=policy, conditioning=96, target=len(target),
                              pre_target_ap_c=initial['ap'], conditioning_end_ap_c=cond_end['ap'],
                              recovery_ap_change_c=initial['ap']-cond_end['ap'], pre_trend_c_per_s=slope,
                              actual_idle_to_first_dispatch_s=(target_start-boundary['recovery_start_ns'])/1e9,
                              query_age_end_s=(target_start-initial['after_ns'])/1e9,
                              query_age_start_s=(target_start-initial['before_ns'])/1e9,
                              query_bracket_s=(initial['after_ns']-initial['before_ns'])/1e9,
                              ap_interval_median_s=float(np.median(np.diff([r['mono_ns']/1e9 for r in idle]))),
                              ap_max_gap_s=float(max(np.diff([r['mono_ns']/1e9 for r in idle]))),
                              runtime_recreated=False, additional_warmup=0))
        for stage, rows in (('conditioning', conditioning), ('target', target)):
            manifest = m['conditioning_requests'] if stage == 'conditioning' else m['requests']
            planned = {r['ordinal']: r for r in manifest}
            if len(planned) != len(rows) or len({r['ordinal'] for r in rows}) != len(rows):
                raise ValueError('duplicate or missing request')
            if stage == 'target' and rows and semantic_requests(manifest) != semantic_requests(m['conditioning_requests']):
                raise ValueError('different arrival/task/input sequence')
            for row in rows:
                plan = planned[row['ordinal']]
                if row['terminal_status'] != 'succeeded' or (row['task_id'], row['priority']) != (plan['task_id'], plan['priority']):
                    raise ValueError('request task/status differs from manifest')
                values = phase_values(row); ap = prior_ap(thermal, row['dispatch_ns'])
                peers = [r for r in rows if r['ordinal'] != row['ordinal']]
                overlap = union_overlap(row['host_inference_start_ns'], row['host_inference_return_ns'],
                                        [(r['host_inference_start_ns'], r['host_inference_return_ns']) for r in peers])
                lane_overlap = union_overlap(row['dispatch_ns'], row['lane_available_ns'],
                                             [(r['dispatch_ns'], r['lane_available_ns']) for r in peers])
                requests.append(dict(session=identity, role=role, gap_s=gap, policy=policy, stage=stage,
                                     ordinal=row['ordinal'], task=row['task_id'], backend=row['selected_backend'], priority=row['priority'],
                                     dispatch_s=(row['dispatch_ns']-origin)/1e9,
                                     invoke_start_s=(row['host_inference_start_ns']-origin)/1e9,
                                     invoke_end_s=(row['host_inference_return_ns']-origin)/1e9,
                                     lane_s=(row['lane_available_ns']-origin)/1e9,
                                     ap_before_c=None if ap is None else ap['ap'],
                                     ap_age_end_s=None if ap is None else (row['dispatch_ns']-ap['after_ns'])/1e9,
                                     ap_query_start_s=None if ap is None else (ap['before_ns']-origin)/1e9,
                                     ap_query_end_s=None if ap is None else (ap['after_ns']-origin)/1e9,
                                     pre_target_ap_c=initial['ap'], invocation_overlap=overlap, lane_overlap=lane_overlap, **values))
    write(output/'inputs.json', dict(version=VERSION, sessions=case_rows, requests=requests,
                                   core=identities[0], raw_hashes=hashes,
                                   source_locations=src['source_locations'], raw_root_required_only_for_extract=True))
    return dict(sessions=len(case_rows), target_sessions=sum(r['target'] > 0 for r in case_rows),
                work_rows=len(requests), raw_files=len(hashes), device_commands=0)


def summarize(data):
    rows = []
    for c in data['sessions']:
        for stage in ('conditioning', 'target'):
            use = [r for r in data['requests'] if r['session'] == c['session'] and r['stage'] == stage]
            for task, backend in sorted({(r['task'], r['backend']) for r in use}):
                cell = [r for r in use if (r['task'], r['backend']) == (task, backend)]
                rows.append(dict(session=c['session'], role=c['role'], gap_s=c['gap_s'], policy=c['policy'], stage=stage,
                                 cell=task+'_'+backend, n=len(cell), pre_target_ap_c=c['pre_target_ap_c'],
                                 ap_mean_c=float(np.mean([r['ap_before_c'] for r in cell if r['ap_before_c'] is not None])),
                                 overlap_mean=float(np.mean([r['invocation_overlap'] for r in cell])),
                                 **{k: float(np.mean([r[k] for r in cell])) for k in METRICS}))
    return rows


def fit_candidate(summaries):
    # Equal session weighting. Never use confirmation rows or post-load AP.
    dev = [r for r in summaries if r['role'] == 'development' and r['stage'] == 'target']
    heads = {}
    for policy, cell in sorted({(r['policy'], r['cell']) for r in dev}):
        rows = [r for r in dev if (r['policy'], r['cell']) == (policy, cell)]
        if len(rows) != 2 or {r['gap_s'] for r in rows} != {30, 180}:
            raise ValueError('candidate requires both registered development histories')
        ap = np.array([r['pre_target_ap_c'] for r in rows]); ref = float(ap.mean())
        d = ap-ref; y = np.log([r['execution_to_output'] for r in rows])
        raw = float(d @ (y-y.mean()) / (d@d)) if d@d > 1e-12 else None
        heads[policy+'|'+cell] = dict(reference_ap_c=ref, ap_min_c=float(ap.min()), ap_max_c=float(ap.max()),
                                    raw_gain_per_c=raw, gain_per_c=None if raw is None else max(0., raw),
                                    fixed_phases_ms=[float(np.mean([r[k] for r in rows])) for k in PHASES],
                                    development_sessions=[r['session'] for r in rows],
                                    two_point_gain_has_no_development_residual_degrees_of_freedom=True,
                                    single_gap_fold_cannot_identify_temperature_gain=True)
    return dict(version=VERSION, heads=heads, application_allowed=False, strict_support=False,
                accuracy_pass=None, experiment_ready=False,
                phase_two_means_execution_to_output_not_invocation=True,
                effect='pre-target observed AP association, constant within target; not dynamic recovery law')


def predict(candidate, policy, cell, pre_ap_c, *, diagnostic_extrapolation=False):
    if not math.isfinite(pre_ap_c):
        raise ValueError('invalid initial AP')
    head = candidate['heads'].get(policy+'|'+cell)
    if head is None or head['gain_per_c'] is None:
        return dict(phases_ms=None, supported=False, reason='unidentified_or_unmeasured_cell')
    inside = head['ap_min_c'] <= pre_ap_c <= head['ap_max_c']
    if not inside and not diagnostic_extrapolation:
        return dict(phases_ms=None, supported=False, reason='outside_development_initial_AP')
    v = list(head['fixed_phases_ms'])
    v[1] *= math.exp(head['gain_per_c']*(pre_ap_c-head['reference_ap_c']))
    return dict(phases_ms=v, supported=False, within_development_ap=inside,
                diagnostic_extrapolation=not inside, reason='posthoc_association_only')


def evaluate(data, candidate, frozen):
    output = []
    for session in data['sessions']:
        use = [r for r in data['requests'] if r['session'] == session['session'] and r['stage'] == 'target']
        for cell in sorted({r['task']+'_'+r['backend'] for r in use}):
            rr = [r for r in use if r['task']+'_'+r['backend'] == cell]
            key = session['policy']+'|'+cell; head = candidate['heads'][key]
            policy = 'CPU_URGENT_ONLINE_V1' if session['policy'] == 'CPU' else 'B2_PARALLEL_ONLINE_V1'
            prior = frozen['service'][policy]['phase_means_ns'][cell+'_'+rr[0]['priority']]
            vectors = {'original_frozen': [x/1e6 for x in prior], 'history_fixed_control': head['fixed_phases_ms'],
                       'pre_AP_candidate': predict(candidate, session['policy'], cell, session['pre_target_ap_c'], diagnostic_extrapolation=True)['phases_ms']}
            for model, vector in vectors.items():
                for i, metric in enumerate((*PHASES, 'lane_total')):
                    if vector is None:
                        pred = None; mae = signed = None
                    else:
                        pred = sum(vector) if metric == 'lane_total' else vector[i]
                        error = np.array([pred-r[metric] for r in rr]); mae = float(np.mean(abs(error))); signed = float(error.mean())
                    output.append(dict(session=session['session'], role=session['role'], gap_s=session['gap_s'], policy=session['policy'], cell=cell,
                                       n=len(rr), model=model, metric=metric, observed_mean_ms=float(np.mean([r[metric] for r in rr])),
                                       predicted_ms=pred, signed_ms=signed, mae_ms=mae,
                                       extrapolation=(not head['ap_min_c'] <= session['pre_target_ap_c'] <= head['ap_max_c']) if model == 'pre_AP_candidate' else None,
                                       fresh_independent_validation=False, supported=False))
    return output


def contrasts(data, summaries):
    result = []
    for role in ('development', 'confirmation'):
        for policy in ('CPU', 'PAR'):
            ss = [r for r in summaries if r['role'] == role and r['policy'] == policy and r['stage'] == 'target']
            for cell in sorted({r['cell'] for r in ss}):
                a = next(r for r in ss if r['cell'] == cell and r['gap_s'] == 30)
                b = next(r for r in ss if r['cell'] == cell and r['gap_s'] == 180)
                for metric in METRICS:
                    delta = b[metric]-a[metric]
                    result.append(dict(role=role, policy=policy, cell=cell, metric=metric, mean_30_ms=a[metric], mean_180_ms=b[metric],
                                       delta_180_minus_30_ms=delta, relative_percent=100*delta/a[metric],
                                       pre_AP_180_minus_30_c=b['pre_target_ap_c']-a['pre_target_ap_c'],
                                       invocation_overlap_180_minus_30=b['overlap_mean']-a['overlap_mean'],
                                       independent_session_pairs=1, cooling_causal_effect_identified=False))
    return result


def ordinal_contrasts(data):
    # Ordinal controls within policy; quartiles are dependent strata, not repetitions.
    out = []
    for role in ('development', 'confirmation'):
        for policy in ('CPU', 'PAR'):
            use = [r for r in data['requests'] if r['role'] == role and r['policy'] == policy and r['stage'] == 'target']
            for cell in sorted({r['task']+'_'+r['backend'] for r in use}):
                selected = [r for r in use if r['task']+'_'+r['backend'] == cell]
                a = {r['ordinal']: r for r in selected if r['gap_s'] == 30}; b = {r['ordinal']: r for r in selected if r['gap_s'] == 180}
                if set(a) != set(b):
                    raise ValueError('ordinal comparison lost denominator')
                ordinals = sorted(a)
                for quarter, ids in enumerate(np.array_split(ordinals, 4)):
                    for metric in ('invocation', 'execution_to_output', 'lane_total'):
                        out.append(dict(role=role, policy=policy, cell=cell, ordinal_quarter=quarter, n=len(ids), metric=metric,
                                        mean_delta_ms=float(np.mean([b[i][metric]-a[i][metric] for i in ids])),
                                        ordinal_pairs_not_independent_sessions=True))
    return out


def associations(data):
    out = []
    for c in data['sessions']:
        use = [r for r in data['requests'] if r['session'] == c['session'] and r['stage'] == 'target' and r['ap_before_c'] is not None]
        for cell in sorted({r['task']+'_'+r['backend'] for r in use}):
            rr = [r for r in use if r['task']+'_'+r['backend'] == cell]
            ap = np.array([r['ap_before_c'] for r in rr]); elapsed = np.array([r['dispatch_s'] for r in rr]); overlap = np.array([r['invocation_overlap'] for r in rr])
            cols = [ap-ap.mean(), elapsed-elapsed.mean()]
            if np.std(overlap) > 1e-12:
                cols.append(overlap-overlap.mean())
            x = np.array(cols).T; norms = np.linalg.norm(x, axis=0)
            gain = condition = None
            if min(norms) > 1e-12:
                sx = x/norms; sv = np.linalg.svd(sx, compute_uv=False)
                if sv[-1] > sv[0]*1e-12:
                    y = np.array([r['invocation'] for r in rr]); gain = float(np.linalg.lstsq(sx, y-y.mean(), rcond=None)[0][0]/norms[0]); condition = float(sv[0]/sv[-1])
            out.append(dict(session=c['session'], role=c['role'], policy=c['policy'], cell=cell, n=len(rr),
                            ap_min_c=float(ap.min()), ap_max_c=float(ap.max()),
                            ap_elapsed_correlation=float(np.corrcoef(ap, elapsed)[0, 1]) if np.std(ap) > 1e-12 else None,
                            adjusted_invocation_ms_per_c=gain, scaled_condition=condition,
                            causal_or_forecast_coefficient=False))
    return out


def analyze(output, registration):
    output = Path(output)
    if (output/'receipt.json').exists():
        raise FileExistsError('analysis already closed')
    reg = read(registration)
    for relative, expected in reg['sources'].items():
        if sha(ROOT/relative) != expected:
            raise ValueError('registered source drift: '+relative)
    if sha(output/'inputs.json') != reg['inputs_sha256']:
        raise ValueError('input drift')
    data = read(output/'inputs.json'); summaries = summarize(data)
    candidate = fit_candidate(summaries)
    write(output/'candidate.json', candidate)  # Written before any confirmation scoring.
    write(output/'development_freeze.json', dict(created_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                                                candidate_sha256=sha(output/'candidate.json'), training_sessions=[r['session'] for r in data['sessions'] if r['role']=='development' and r['target']],
                                                inputs_sha256=reg['inputs_sha256'], candidate_selection_uses_confirmation=False,
                                                data_previously_seen=True))
    scores = evaluate(data, candidate, read(MODEL)); diffs = contrasts(data, summaries)
    csv_write(output/'session_phases.csv', summaries); csv_write(output/'request_phases.csv', data['requests'])
    csv_write(output/'recovery_contrasts.csv', diffs); csv_write(output/'ordinal_contrasts.csv', ordinal_contrasts(data))
    csv_write(output/'within_session_associations.csv', associations(data)); csv_write(output/'prediction_errors.csv', scores)
    csv_write(output/'initial_conditions.csv', data['sessions'])
    aggregate = []
    for role in ('development', 'confirmation'):
        for model in ('original_frozen', 'history_fixed_control', 'pre_AP_candidate'):
            for metric in ('execution_to_output', 'lane_total'):
                rows = [r for r in scores if r['role'] == role and r['model'] == model and r['metric'] == metric]
                aggregate.append(dict(role=role, model=model, metric=metric, session_cells=len(rows),
                                      mean_cell_mae_ms=float(np.mean([r['mae_ms'] for r in rows if r['mae_ms'] is not None])) if any(r['mae_ms'] is not None for r in rows) else None,
                                      missing=sum(r['mae_ms'] is None for r in rows),
                                      extrapolated=sum(r['extrapolation'] is True for r in rows)))
    summary = dict(version=VERSION, independent_target_sessions=8, total_physical_sessions=12,
                   work_rows=len(data['requests']), target_rows=sum(r['stage']=='target' for r in data['requests']),
                   missing_request_AP=sum(r['ap_before_c'] is None for r in data['requests']),
                   comparison=aggregate, fitted_cell_temperature_slopes=len(candidate['heads']),
                   initial_AP_gain_not_dynamic_cooling_recovery=True, adoption=False,
                   default_RL_changed=False, experiment_ready=False, device_commands=0,
                   raw_hashes_unchanged=True, registered_source_hashes=reg['sources'])
    write(output/'summary.json', summary)
    write(output/'receipt.json', dict(status='completed_posthoc_descriptive_only', registration_sha256=sha(registration),
                                     files={p.name: sha(p) for p in sorted(output.iterdir()) if p.is_file()},
                                     device_commands=0, simulations=0, model_fits=1, per_cell_coefficients=4))
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    e = sub.add_parser('extract'); e.add_argument('--raw-root', required=True); e.add_argument('--output', required=True)
    a = sub.add_parser('analyze'); a.add_argument('--output', required=True); a.add_argument('--registration', default=str(BUNDLE/'registration.json'))
    args = parser.parse_args()
    try:
        result = extract(args.raw_root, args.output) if args.action == 'extract' else analyze(args.output, args.registration)
        print(json.dumps(result, ensure_ascii=False, allow_nan=False))
    except Exception as err:
        out = Path(args.output)
        if out.exists():
            path = out/'ERROR.json'
            if not path.exists():
                write(path, dict(type=type(err).__name__, message=str(err), stack=traceback.format_exc(), device_commands=0))
        raise


if __name__ == '__main__':
    main()
