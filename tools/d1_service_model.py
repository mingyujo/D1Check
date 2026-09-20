"""Session-held-out service analysis and fail-closed freeze preparation; no scheduler."""
import argparse
import datetime as dt
import hashlib
import json
import math
from pathlib import Path
import statistics as st

from tools.d1_sim_prepare import canonical
from tools.d1_task_profile import validate, read, digest

CANDIDATES = ('global_mean', 'task_backend_mean', 'initial_state_mean',
              'transition_mean', 'corun_state_mean', 'empirical_session_blocks')


def sha(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def quantile(values, q):
    values = sorted(values)
    return values[max(0, math.ceil(q*len(values))-1)] if values else None


def describe(values):
    return dict(n=len(values), mean=st.mean(values) if values else None,
                median=st.median(values) if values else None, p95=quantile(values, .95))


def ordered(ids, seed):
    if type(seed) is not int or not 0 <= seed < 2**64:
        raise ValueError('invalid split seed')
    return sorted(ids, key=lambda s: sha(['session-order-v1', seed, s]))


def load_sessions(root):
    """Validate actual profile artifacts, identities and equivalence before analysis."""
    sessions, excluded, ids, requests, fingerprints = [], [], set(), set(), set()
    identity = None
    for folder in sorted((Path(root)/'profiles').iterdir()):
        context = read(folder/'context.json')
        if not (folder/'receipt.json').exists():
            excluded.append(dict(session_id=folder.name, status=context['status'],
                                 planned_requests=len(context['recipe']['requests'])))
            continue
        receipt = validate(folder/'artifacts', (folder/'delegate_log.txt').read_text())
        m = read(folder/'artifacts/manifest.json')
        eq = read(folder/'equivalence.json')
        if m['protocol'] != 'task-profile-v3' or folder.name != receipt['session_id'] or not eq['passed']:
            raise ValueError('stale protocol, session identity or decoded gate')
        if receipt['failed'] or receipt['gpu']['status'] == 'unverified':
            raise ValueError('incomplete or unverified backend')
        current = (m['apk_sha256'], m['device_fingerprint'])
        if identity is not None and identity != current:
            raise ValueError('mixed APK/device contracts')
        identity = current
        sid = folder.name
        if sid in ids:
            raise ValueError('replayed session')
        ids.add(sid)
        events = sorted(receipt['events'], key=lambda e: (e['execution_start_ns'], e['request_id']))
        trace = [{k: e[k] for k in ('scheduled_arrival_ns', 'execution_start_ns', 'completion_ns',
                                  'task_id', 'requested_backend', 'input_tensor_sha256')} for e in events]
        fingerprint = sha(trace)
        if fingerprint in fingerprints:
            raise ValueError('replayed measurement with relabeled session')
        fingerprints.add(fingerprint)
        rows, previous, ordinal = [], {}, {}
        pair = '+'.join(sorted(m['models'])) if m['allowed_concurrency'] == 2 else 'solo'
        for e in events:
            if e['request_id'] in requests:
                raise ValueError('replayed request')
            requests.add(e['request_id'])
            worker = e['worker']
            prior = previous.get(worker)
            cell = e['task_id']+'/'+e['requested_backend']
            changed = prior is not None and prior['cell'] != cell
            ordinal[worker] = 1 if prior is None or changed else ordinal[worker]+1
            row = dict(session_id=sid, request_id=e['request_id'], cell=cell,
                       priority=e['priority'], role=e['role'], purpose=m['purpose'], pair=pair,
                       ordinal=ordinal[worker], first=prior is None, transition=changed,
                       from_backend=prior['cell'].split('/')[1] if changed else None,
                       gap_ns=e['execution_start_ns']-prior['terminal_ns'] if prior else None,
                       service_ns=e['service_ns'], prepare_ns=e['prepare_ns'], inference_ns=e['inference_ns'],
                       response_ns=e['completion_ns']-e['scheduled_arrival_ns'],
                       sample_id=e['sample_id'], terminal_ns=e['terminal_ns'])
            previous[worker] = row
            rows.append(row)
        files = []
        artifact_names = ['artifacts/'+p.name for p in sorted((folder/'artifacts').iterdir())]
        for name in (*artifact_names, 'delegate_log.txt', 'equivalence.json', 'context.json'):
            f = folder/name
            files.append(dict(path=str(f.resolve()), sha256=digest(f)))
        env = read(folder/'artifacts/environment.json')
        sessions.append(dict(session_id=sid, purpose=m['purpose'], started_utc=context['started_utc'],
                             measurement_fingerprint=fingerprint, apk_sha256=m['apk_sha256'],
                             device_fingerprint=m['device_fingerprint'], rows=rows, files=files,
                             peak_pss_kb=receipt['sampled_peak_pss_kb'],
                             thermal_statuses=sorted(set(x['thermal_status'] for x in env)),
                             battery_temperature_deci_c=[min(x['battery_temperature_deci_c'] for x in env),
                                                         max(x['battery_temperature_deci_c'] for x in env)]))
    if not sessions:
        raise ValueError('no validated sessions')
    return sessions, excluded


def validate_split(split):
    names = ('calibration', 'retrospective_holdout', 'post_discovery', 'prospective_holdout')
    flat = [s for name in names for s in split[name]]
    if len(flat) != len(set(flat)):
        raise ValueError('session holdout leakage or replay')
    if set(split['prospective_holdout']) & set(split['previously_seen']):
        raise ValueError('previously inspected session is not prospective holdout')
    if set(flat) != set(split['catalog_session_ids']):
        raise ValueError('split must account for every catalog session exactly once')
    return True


def make_split(sessions, seed):
    result = dict(protocol='service-session-split-v1', seed=seed,
                  rule='retain original purpose split; seed orders session folds, not a new random holdout',
                  calibration=[], retrospective_holdout=[], post_discovery=[], prospective_holdout=[],
                  previously_seen=sorted(s['session_id'] for s in sessions),
                  catalog_session_ids=sorted(s['session_id'] for s in sessions))
    for s in sessions:
        group = ('post_discovery' if len(s['rows']) == 7 else 'retrospective_holdout') if s['purpose'] == 'holdout' else 'calibration'
        result[group].append(s['session_id'])
    for name in ('calibration', 'retrospective_holdout', 'post_discovery'):
        result[name] = ordered(result[name], seed)
    validate_split(result)
    return result


def state(row, boundary):
    if row['transition']:
        return 'transition_'+row['from_backend']+'_to_'+row['cell'].split('/')[1]
    if row['first']:
        return 'cold_first'
    if row['ordinal'] == 2 and row['gap_ns'] <= boundary:
        return 'initial_followup'
    return 'warm_steady'


def gap_boundary(rows):
    # Only calibration dispatch-history gaps; no current-request latency or holdout values.
    values = sorted(set(max(1, r['gap_ns']) for r in rows if r['ordinal'] == 2 and r['gap_ns'] is not None))
    pairs = [(b/a, a, b) for a, b in zip(values, values[1:])]
    if not pairs or max(pairs)[0] < 10:
        return dict(boundary_ns=max(values, default=0), unobserved_gap_range=None)
    _, lo, hi = max(pairs)
    return dict(boundary_ns=math.isqrt(lo*hi), unobserved_gap_range=[lo, hi])


def key(row, candidate, boundary):
    if candidate == 'global_mean':
        return 'all'
    if candidate == 'task_backend_mean':
        return row['cell']
    phase = state(row, boundary)
    if candidate == 'initial_state_mean' and row['transition']:
        phase = 'cold_first'
    fields = [row['cell'], phase]
    if candidate in ('corun_state_mean', 'empirical_session_blocks'):
        fields.append(row['pair'])
    return '|'.join(fields)


def fit(rows, candidate):
    if candidate not in CANDIDATES or not rows:
        raise ValueError('empty calibration or unknown candidate')
    gap = gap_boundary(rows)
    groups = {}
    for row in rows:
        k = key(row, candidate, gap['boundary_ns'])
        groups.setdefault(k, {}).setdefault(row['session_id'], []).append(row['service_ns'])
    cells = {}
    for k, blocks in groups.items():
        values = [v for block in blocks.values() for v in block]
        # Session-balanced empirical model; deterministic means are request-weighted.
        empirical = candidate == CANDIDATES[-1]
        point = st.mean(st.mean(b) for b in blocks.values()) if empirical else st.mean(values)
        def percentile(q):
            if not empirical:
                return quantile(values, q)
            weighted = sorted((v, 1/(len(blocks)*len(b))) for b in blocks.values() for v in b)
            cumulative = 0.
            for v, weight in weighted:
                cumulative += weight
                if cumulative >= q-1e-12:
                    return v
            return weighted[-1][0]
        cells[k] = dict(mean_ns=point, median_ns=percentile(.5) if empirical else st.median(values), p95_ns=percentile(.95),
                        interval_ns=[percentile(.05), percentile(.95)],
                        session_count=len(blocks), request_count=len(values), blocks=blocks)
    return dict(candidate=candidate, gap=gap, cells=cells,
                calibration_sessions=sorted(set(r['session_id'] for r in rows)))


def predict(model, row):
    k = key(row, model['candidate'], model['gap']['boundary_ns'])
    cell = model['cells'].get(k)
    if cell is None:
        return None  # No silent borrowing from a different state or backend.
    return dict(key=k, point_ns=cell['mean_ns'], interval_ns=cell['interval_ns'],
                median_ns=cell['median_ns'], p95_ns=cell['p95_ns'],
                calibration_sessions=cell['session_count'])


def resample(model, row, seed, draw, block_id=0):
    """One deterministic empirical service draw; never advances time or completes a request."""
    if model['candidate'] != CANDIDATES[-1] or type(draw) is not int or draw < 0:
        raise ValueError('empirical model and nonnegative draw required')
    p = predict(model, row)
    if p is None:
        raise ValueError('unsupported state')
    blocks = model['cells'][p['key']]['blocks']
    names = ordered(blocks, seed)
    number = int(sha(['service-block-draw-v1', seed, block_id, p['key']]), 16)
    block = blocks[names[number % len(names)]]
    return block[((number // len(names))+draw) % len(block)]


def score_predictions(rows, predictions):
    good = [(r, p) for r, p in zip(rows, predictions) if p is not None]
    if not good:
        return dict(total=len(rows), predicted=0, support_rate=0., mae_ns=None, wape=None, coverage=None)
    ys = [r['service_ns'] for r, _ in good]
    ps = [p['point_ns'] for _, p in good]
    errors = [abs(y-p) for y, p in zip(ys, ps)]
    return dict(total=len(rows), predicted=len(good), support_rate=len(good)/len(rows),
                mae_ns=st.mean(errors), wape=sum(errors)/sum(ys),
                median_absolute_error_ns=st.median(errors), max_absolute_error_ns=max(errors),
                median_relative_error=st.median(e/y for e, y in zip(errors, ys)),
                max_relative_error=max(e/y for e, y in zip(errors, ys)),
                observed=describe(ys), predicted_point=describe(ps),
                mean_bias_ns=st.mean(ps)-st.mean(ys), median_bias_ns=st.median(ps)-st.median(ys),
                p95_point_bias_ns=quantile(ps,.95)-quantile(ys,.95),
                coverage=sum(p['interval_ns'][0] <= r['service_ns'] <= p['interval_ns'][1] for r,p in good)/len(good),
                interval_width_mean_ns=st.mean(p['interval_ns'][1]-p['interval_ns'][0] for _,p in good),
                quantile_loss_note='point-prediction distribution bias is separate from per-session/state distribution estimates')


def evaluate(model, rows, predictions=None):
    predictions = [predict(model, r) for r in rows] if predictions is None else predictions
    groups = {}
    for i, r in enumerate(rows):
        k = r['cell']+'|'+r['priority']+'|'+state(r, model['gap']['boundary_ns'])+'|'+r['pair']
        groups.setdefault(k, []).append(i)
    session_metrics = []
    for sid in sorted(set(r['session_id'] for r in rows)):
        indices = [i for i,r in enumerate(rows) if r['session_id']==sid]
        session_metrics.append(dict(session_id=sid, metrics=score_predictions([rows[i] for i in indices], [predictions[i] for i in indices])))
    distributions = []
    distribution_groups = {}
    for row, prediction in zip(rows, predictions):
        if prediction is not None:
            group = (row['session_id'], row['priority'], prediction['key'])
            distribution_groups.setdefault(group, []).append((row, prediction))
    for (sid, priority, group), pairs in sorted(distribution_groups.items()):
        observed = describe([r['service_ns'] for r, _ in pairs])
        p = pairs[0][1]
        expected = dict(mean=p['point_ns'], median=p['median_ns'], p95=p['p95_ns'])
        distributions.append(dict(session_id=sid, priority=priority, state_key=group, n=len(pairs),
                                  observed=observed, predicted=expected,
                                  absolute_error_ns={k:abs(expected[k]-observed[k]) for k in expected},
                                  relative_error={k:abs(expected[k]-observed[k])/observed[k] for k in expected},
                                  p95_sample_warning=len(pairs)<20))
    return dict(overall=score_predictions(rows,predictions), distribution_metrics=distributions,
                strata={k:score_predictions([rows[i] for i in ix],[predictions[i] for i in ix]) for k,ix in groups.items()},
                sessions=session_metrics)


def calibration_criteria(rows):
    """Freeze engineering thresholds from between-session calibration variability only."""
    boundary = gap_boundary(rows)['boundary_ns']
    groups = {}
    for r in rows:
        k = key(r, 'corun_state_mean', boundary)
        groups.setdefault(k, {}).setdefault(r['session_id'], []).append(r['service_ns'])
    comparisons = []
    for k, blocks in groups.items():
        names = sorted(blocks)
        for i, a in enumerate(names):
            for b in names[i+1:]:
                for metric in ('mean','median','p95'):
                    x,y=describe(blocks[a])[metric],describe(blocks[b])[metric]
                    comparisons.append(dict(stratum=k, sessions=[a,b], metric=metric,
                                            absolute_ns=abs(x-y), relative=abs(x-y)/((x+y)/2)))
    if not comparisons:
        raise ValueError('no between-session calibration variability')
    return dict(protocol='service-acceptance-v1', method='2 * nearest-rank Q95 between-session calibration differences',
                wape_max=2*quantile([x['relative'] for x in comparisons],.95),
                mae_ns_max=2*quantile([x['absolute_ns'] for x in comparisons],.95),
                distribution_relative_error_max=2*quantile([x['relative'] for x in comparisons],.95),
                prediction_interval_nominal=.90, required_empirical_coverage=.90,
                support_rate_required=1., min_calibration_sessions_per_state=2,
                min_holdout_sessions_per_cell=2, min_warm_observations_per_cell=20,
                acceptance_scope='all gates jointly: overall AND each cell/priority/state/pair MAE,WAPE,coverage; session-state distribution mean/median/P95 errors; no omitted or unsupported state; support and repetition counts mandatory',
                independence='all old sessions descriptive only; preregistered new sessions only',
                design_choices='factor 2 and 90% coverage are explicit prospective engineering rules, not a statistical guarantee; small calibration may yield inadequate or loose limits',
                variability_pairs=comparisons)


def check_prospective(plan, model, sessions):
    if sha(model) != plan['model_sha256'] or sha(plan['criteria']) != plan['criteria_sha256']:
        raise ValueError('model or acceptance criteria changed after preregistration')
    if not sessions:
        raise ValueError('no independent holdout')
    ids, traces, request_ids = set(), set(), set()
    frozen = dt.datetime.fromisoformat(plan['frozen_utc'])
    for s in sessions:
        sid = s['session_id']
        if sid in ids or sid in plan['previously_seen'] or sid in model['calibration_sessions']:
            raise ValueError('holdout leakage or replayed session')
        if dt.datetime.fromisoformat(s['started_utc']) <= frozen:
            raise ValueError('stale holdout predates acceptance freeze')
        if s['measurement_fingerprint'] in traces or s['measurement_fingerprint'] in plan['seen_measurements']:
            raise ValueError('replayed measurement')
        if s['apk_sha256'] != plan['apk_sha256'] or s['device_fingerprint'] != plan['device_fingerprint']:
            raise ValueError('holdout runtime identity drift')
        ids.add(sid);traces.add(s['measurement_fingerprint'])
        for row in s['rows']:
            if row['request_id'] in request_ids or row['request_id'] in plan['seen_requests']:
                raise ValueError('replayed request')
            request_ids.add(row['request_id'])
    return True


def metric_gate(metrics, criteria):
    """Descriptive pass of numeric gates is never independent-holdout or READY approval."""
    return (metrics['support_rate'] == criteria['support_rate_required'] and
            metrics['mae_ns'] is not None and metrics['mae_ns'] <= criteria['mae_ns_max'] and
            metrics['wape'] <= criteria['wape_max'] and
            metrics['coverage'] >= criteria['required_empirical_coverage'])


def validate_bundle(root):
    root = Path(root).resolve()
    receipt = read(root/'provenance.json')
    required = {'acceptance_criteria.json','baseline_bindings.json','candidate_model.json','candidate_models.json',
                'generation.json','gpu_tradeoff.json','model_comparison.json','observations.json',
                'prospective_plan.json','selection.json','simulation_input.json','source_manifest.json',
                'split.json','state_analysis.json'}
    if set(receipt['files']) not in (required, required | {'no_op_result.json'}):
        raise ValueError('incomplete artifact inventory')
    for name, expected in receipt['files'].items():
        path = root/name
        if Path(name).name != name or path.is_symlink() or not path.is_file() or digest(path) != expected:
            raise ValueError('artifact path/hash mismatch')
    for item in read(root/'source_manifest.json')['files']:
        path = Path(item['path'])
        if not path.is_file() or path.is_symlink() or digest(path) != item['sha256']:
            raise ValueError('stale source artifact')
    for name, expected in read(root/'generation.json')['generator_sources'].items():
        path = Path(name)
        if not path.is_file() or digest(path) != expected:
            raise ValueError('stale generator source')
    split=read(root/'split.json');validate_split(split)
    model=read(root/'candidate_model.json');plan=read(root/'prospective_plan.json');contract=read(root/'simulation_input.json')
    observations = read(root/'observations.json')
    source_manifest = read(root/'source_manifest.json')
    if sha(observations['sessions']) != source_manifest['source_catalog_sha256']:
        raise ValueError('source catalog binding mismatch')
    if (set(source_manifest['session_ids']) != set(split['catalog_session_ids']) or
            set(model['calibration_sessions']) != set(split['calibration']) or
            set(plan['previously_seen']) != set(split['previously_seen'])):
        raise ValueError('model/split binding or holdout leakage')
    if sha(model)!=plan['model_sha256'] or sha(plan['criteria'])!=plan['criteria_sha256']:
        raise ValueError('candidate/criteria binding mismatch')
    if plan['selection_sha256'] != digest(root/'selection.json'):
        raise ValueError('model selection changed after preregistration')
    if (contract['model_sha256'] != sha(model) or contract['status'] != 'SIM-01_INCOMPLETE' or
            contract['split_sha256'] != sha(split) or contract['criteria_sha256'] != sha(plan['criteria']) or
            read(root/'acceptance_criteria.json') != plan['criteria']):
        raise ValueError('unvalidated model cannot be promoted to READY')
    validate_contract(contract)
    if contract['constraints']['fallback']!='forbidden' or contract['constraints']['thermal_status_allowed']!=[0]:
        raise ValueError('unsupported runtime scope')
    policies=read(root/'baseline_bindings.json')['policies']
    names={'FIFO_CPU_only','feasible_fixed_GPU','static_task_mapping','EDF','proposed_adaptive_interface'}
    if len(policies) != len(names) or {p['policy'] for p in policies} != names:
        raise ValueError('baseline inventory drift')
    if any(p['input_sha256'] != sha(contract) or p['legal_cells_only'] is not True for p in policies):
        raise ValueError('baseline input drift')
    result=dict(status='SIM-01_INCOMPLETE',model_sha256=sha(model),simulation_input_sha256=sha(contract),
                dispatch_count=0,simulated_completion_count=0,comparative_results=None)
    if (root/'no_op_result.json').exists() and read(root/'no_op_result.json') != result:
        raise ValueError('fabricated no-op result')
    return result


def validate_contract(contract):
    """Fail-closed executable invariants accompany the published JSON Schema."""
    if contract['protocol'] != 'service-model-preparation-v1' or contract['status'] != 'SIM-01_INCOMPLETE':
        raise ValueError('only preparation, not frozen execution, is supported')
    cells = [(x['task'], x['backend']) for x in contract['capabilities']]
    if len(cells) != 4 or set(cells) != {(t,b) for t in ('classification','detection') for b in ('CPU','GPU')}:
        raise ValueError('invalid verified capability cells')
    if any(x['decoded_equivalence'] != '20_images_passed' for x in contract['capabilities']):
        raise ValueError('unverified quality cell')
    c = contract['constraints']
    if c['fallback'] != 'forbidden' or c['thermal_status_allowed'] != [0] or c['max_in_flight'] != 1 or c['allowed_corun'] != []:
        raise ValueError('unvalidated scope or fallback')
    if contract['deadline']['state'] != 'calibration_pending' or contract['deadline']['values_ns'] is not None:
        raise ValueError('unfrozen deadline')
    if (contract['no_scheduling_simulation'] is not True or
            set(contract['terminal_states']) != {'succeeded','failed','rejected','expired','cancelled','unfinished'}):
        raise ValueError('simulation or terminal accounting drift')
    return True


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['analyze','validate','no-op'])
    parser.add_argument('--source',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--seed',type=int,default=20260920)
    args=parser.parse_args()
    if args.command=='analyze':
        from tools.d1_service_model_generate import generate
        print(json.dumps(generate(args.source,args.output,args.seed),indent=2))
    else:
        print(json.dumps(validate_bundle(args.output),indent=2))


if __name__=='__main__':
    main()
