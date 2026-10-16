"""Independent saved A24 forecast arithmetic/integrity audit. SOURCE ONLY.

No simulation, timing-model construction, AP fit, neural training, archive/device
or network call exists. This reads one exact completed forecast namespace and
the original pinned data/models/profile. AP is independently rebuilt by scalar
sequential exponential state propagation, following the independently audited
Node formulation as a source reference; Node is never imported or executed.
Only the root may register and execute this entry or its sealed fixtures.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import gzip
import io
import json
import math
from pathlib import Path
import statistics
import unittest

from runtime_guard import canonical, operation, pin, read, require, sha, write_new

WORK = Path(__file__).resolve().parent
LOCK = Path('C:/Users/chomg/Documents/Codex/2026-10-11/dkfo/outputs/A24-INTEGRATED-SIM-20261016-G002/worker.lock')
VERSION = 'A24-SAVED-FORECAST-INDEPENDENT-AUDIT-v1'
NODE_SOURCE_SHA = '6ab8f92c8cd0f5e463ffeea73f147ae51c93111ca7834c6fc12b83ae56a15fb7'
STATES = ('classification_CPU', 'detection_CPU', 'classification_GPU', 'classification_GPU+detection_CPU')
BOUNDARIES = ('execution_start', 'output_ready', 'persist_complete', 'worker_release', 'lane_available')
GROUPS = ('U', 'N', 'C', 'D', 'CU', 'CN', 'DU', 'DN')
NS = 1_000_000_000


def digest(value):
    import hashlib
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def clock(row, key):
    value = row.get(key + '_ns')
    if type(value) is int and value >= 0:
        return value
    value = row.get(key + '_s')
    return round(value * NS) if finite(value) and value >= 0 else None


def quantile(values):
    return sorted(values)[math.ceil(.95 * len(values)) - 1] if values else None


class Checks:
    def __init__(self, failure_limit=1000):
        self.count, self.failed, self.failures, self.limit = 0, 0, [], failure_limit
        self.max_numeric_error = 0.

    def check(self, condition, name, context=None):
        self.count += 1
        if not condition:
            self.failed += 1
            if len(self.failures) < self.limit:
                self.failures.append({'check': name, 'context': context})
        return bool(condition)

    def equal(self, actual, expected, name, context=None):
        if finite(actual) and finite(expected):
            error = abs(actual - expected)
            self.max_numeric_error = max(self.max_numeric_error, error)
            return self.check(error <= 1e-7 + 1e-10 * max(abs(actual), abs(expected)), name,
                              {'case': context, 'saved': actual, 'independent': expected, 'error': error})
        return self.check(actual == expected, name, {'case': context, 'saved': actual, 'independent': expected})


class CompletedInputs:
    """Every forecast artifact must belong to the exact completed output map."""
    def __init__(self, complete_pin, operation_pin):
        self.complete_path = pin(complete_pin)
        self.root = self.complete_path.parent.resolve()
        self.complete = read(self.complete_path)
        self.operation_path = pin(operation_pin)
        self.operation = read(self.operation_path)
        require(self.complete.get('operation_sha256') == operation_pin['sha256'], 'Forecast COMPLETE/operation binding differs')
        require(Path(self.operation['output_dir']).resolve() == self.root, 'Forecast output namespace differs')
        self.files = {}
        for relative, spec in self.complete['outputs'].items():
            path = self.root / relative
            require(path.resolve().is_relative_to(self.root), 'Completed artifact path escapes namespace')
            self.files[str(path.resolve())] = {'path': str(path), **spec}
        self.reads, self.expanded = set(), 0

    def bound(self, path):
        path = Path(path)
        if not path.is_absolute():
            path = self.root / path
        resolved = path.resolve()
        require(resolved.is_relative_to(self.root), 'Artifact reference escapes forecast namespace')
        require(str(resolved) in self.files, 'Artifact absent from exact forecast COMPLETE: ' + str(path))
        for parent in (path, *path.parents):
            require(not parent.is_symlink() and not (getattr(parent.stat(), 'st_file_attributes', 0) & 0x400),
                    'Reparse/symlink in saved artifact reference')
            if parent.resolve() == self.root:
                break
        result = pin(self.files[str(resolved)])
        self.reads.add(str(resolved))
        return result

    def json(self, path):
        return read(self.bound(path))

    def lines(self, path):
        with self.bound(path).open(encoding='utf-8-sig') as source:
            return [json.loads(line) for line in source if line.strip()]

    def raw(self, path, per_file_cap, total_cap):
        with gzip.open(self.bound(path), 'rb') as source:
            payload = source.read(per_file_cap + 1)
        require(len(payload) <= per_file_cap, 'Registered expanded raw per-file byte cap exceeded')
        self.expanded += len(payload)
        require(self.expanded <= total_cap, 'Registered expanded raw total byte cap exceeded')
        return json.loads(payload.decode('utf-8-sig'))


def summary(rows, *, drain=None, actual_tracking=False, actual_endpoint=None):
    """Independent nearest-rank requested-population arithmetic."""
    complete, latencies, tardiness, missing, ontime = [], [], [], [], 0
    for row in rows:
        response, arrival, deadline = row.get('response_ns'), row['scheduled_arrival_ns'], row['deadline_ns']
        known = response is not None and (drain is None or response <= drain)
        if known:
            latency, late = max(0, response - arrival) / NS, max(0, response - deadline) / NS
            complete.append(latency)
            ontime += response <= deadline
        else:
            endpoint = drain if drain is not None else round(actual_endpoint * NS) if actual_tracking and finite(actual_endpoint) else None
            latency = max(0, endpoint - arrival) / NS if endpoint is not None else None
            late = max(0, endpoint - deadline) / NS if endpoint is not None else None
            missing.append(row['request_id'])
        latencies.append(latency)
        tardiness.append(late)
    bounded = all(value is not None for value in latencies + tardiness)
    return {'planned': len(rows), 'on_time': ontime, 'uncompleted': len(missing),
            'on_time_rate_planned': ontime / len(rows) if rows else None,
            'P95_all_requested_response_s': quantile(latencies) if not missing else None,
            'P95_all_requested_response_lower_bound_s': quantile(latencies) if bounded else None,
            'P95_completed_response_s': quantile(complete),
            'P95_all_requested_tardiness_s': quantile(tardiness) if not missing else None,
            'P95_all_requested_tardiness_lower_bound_s': quantile(tardiness) if bounded else None,
            'total_tardiness_s': sum(tardiness) if not missing else None,
            'total_tardiness_lower_bound_s': sum(tardiness) if bounded else None,
            'service_threshold_flags': {str(p): ontime / len(rows) >= p / 100 if rows else None for p in (70, 80, 90, 95, 100)},
            '_completed': len(complete), '_missing': missing}


def audit_summary(checks, saved, rows, context, **options):
    expected = summary(rows, **options)
    for key, value in expected.items():
        if not key.startswith('_'):
            checks.equal(saved.get(key), value, 'requested_population_' + key, context)
    for group in GROUPS:
        subset = [r for r in rows if group in (r.get('priority'), r.get('task'), str(r.get('task')) + str(r.get('priority')))]
        group_expected = summary(subset, **options)
        for key, value in group_expected.items():
            if not key.startswith('_'):
                checks.equal(saved.get('by_cohort', {}).get(group, {}).get(key), value, 'subgroup_' + key, [context, group])
    checks.check(saved.get('missing_response_imputed') is False, 'no_missing_response_imputation', context)
    return expected


def segments(activity):
    lo, hi = activity['activity_coverage_s']
    require(finite(lo) and finite(hi) and lo < hi, 'Activity coverage invalid')
    events, seen = [], set()
    for owner in activity.get('owner_intervals', []):
        rid, start, end = owner['request_id'], owner['start_s'], owner['end_s']
        require(rid not in seen and lo <= start < end <= hi, 'Owner identity/coverage invalid')
        seen.add(rid)
        label = {'C': 'classification', 'D': 'detection'}[owner['task']] + '_' + owner['route']
        events.extend(((start, 1, rid, label), (end, 0, rid, label)))
    active, cursor, result = {}, lo, []
    def state():
        key = '+'.join(sorted(active.values()))
        require(not key or key in STATES, 'Unsupported owner combination or same-lane ownership')
        return key or 'resident_idle'
    for at, on, rid, label in sorted(events):
        if at > cursor:
            result.append((cursor, at, state()))
            cursor = at
        if on:
            active[rid] = label
            require(len(active) <= 2 and len(set(active.values())) == len(active), 'Max2/nonpreemptive lane contract violated')
            state()
        else:
            require(rid in active, 'Owner release without admission')
            del active[rid]
    if cursor < hi:
        result.append((cursor, hi, state()))
    return result


def independent_AP(model, activity, times, saved, explicit_reference=None):
    """Scalar sequential exponential ODE; no call to frozen thermal functions."""
    cfg = model['config']
    ap, anchor = activity.get('initial_ap_c'), activity.get('initial_ap_time_s')
    hi = activity.get('initial_ap_hi_s', anchor)
    require(finite(ap) and finite(anchor) and finite(hi) and anchor <= hi <= activity.get('forecast_origin_s', 0), 'Unknown/future AP anchor')
    past = sorted((r['t_s'], r['ap_c']) for r in activity.get('observations', [])
                  if r.get('channel') == 'AP' and r.get('initial_eligible') and finite(r.get('hi_s')) and
                  r['hi_s'] <= hi and finite(r.get('ap_c')) and anchor - 30 <= r['t_s'] <= anchor)
    slope = 0.
    if len(past) >= 2 and past[-1][0] - past[0][0] >= 5:
        tm, ym = statistics.mean(t for t, _ in past), statistics.mean(v for _, v in past)
        slope = math.fsum((t - tm) * (v - ym) for t, v in past) / math.fsum((t - tm) ** 2 for t, _ in past)
    intervals = segments(activity)
    require(intervals and intervals[0][0] <= activity.get('forecast_origin_s', 0), 'Unknown AP activity origin')
    require(all(finite(t) for t in times) and all(a <= b for a, b in zip(times, times[1:])), 'AP query clock invalid')
    require(not times or max(anchor, hi, intervals[0][0]) <= times[0] <= times[-1] <= intervals[-1][1], 'AP queries outside covered activity')
    cursor, index, memory = intervals[0][0], 0, [0.] * 4
    def advance(to):
        nonlocal cursor, index, memory
        while cursor < to:
            while index < len(intervals) - 1 and intervals[index][1] <= cursor:
                index += 1
            start, end, label = intervals[index]
            target = min(to, end)
            require(target > cursor, 'AP activity propagation stalled')
            decay = math.exp(-(target - cursor) / cfg['activity_tau_s'])
            gain = -math.expm1(-(target - cursor) / cfg['activity_tau_s'])
            memory = [value * decay + (gain if label == STATES[k] else 0.) for k, value in enumerate(memory)]
            cursor = target
        return list(memory)
    z0 = advance(anchor) if anchor >= cursor else [0.] * 4
    compatibility = activity.get('compatibility', {})
    domain = compatibility.get('ap_activity_domain') or 'UNVERIFIED:' + ':'.join(str(activity.get(k, 'UNKNOWN')) for k in ('source_family', 'source_generation', 'protocol', 'cohort_id'))
    reference = domain
    required_flags = []
    if domain not in model['domains']:
        choices = [d for d in model['domains'] if activity.get('source_family') in model.get('domain_sources', {}).get(d, [])] or model['domains']
        reference = explicit_reference or min(choices, key=lambda d: (-model.get('domain_session_counts', {}).get(d, 0), d))
        required_flags.append('CONTRACT_EQUIVALENCE_UNVERIFIED_REFERENCE_ASSUMPTION')
    require(reference in model['domains'], 'Unknown AP coefficient reference')
    offset = model['domains'].index(reference) * 7
    coefficients = model['coefficients'][offset:offset + 7].copy()
    present = {label for _, _, label in intervals if label != 'resident_idle'}
    for label in sorted(present - set(model['domain_activity_support'][reference])):
        if label == STATES[3] and all(s in model['domain_activity_support'][reference] for s in (STATES[1], STATES[2])):
            coefficients[6] = coefficients[4] + coefficients[5]
            required_flags.append('UNMEASURED_OVERLAP_ADDITIVE_SOLO_GAIN_ASSUMPTION')
        else:
            values = [model['coefficients'][model['domains'].index(d) * 7 + 3 + STATES.index(label)]
                      for d in model['domains'] if label in model['domain_activity_support'][d]]
            require(values, 'Unidentified AP activity coefficient')
            coefficients[3 + STATES.index(label)] = statistics.median(values)
            required_flags.append('UNMEASURED_STATE_OTHER_DOMAIN_GAIN_ASSUMPTION:' + label)
    values = []
    for at in times:
        z = advance(at)
        elapsed = at - anchor
        decay, equilibrium = math.exp(-elapsed / cfg['cooling_tau_s']), -math.expm1(-elapsed / cfg['cooling_tau_s'])
        known_ambient = finite(activity.get('ambient_c'))
        baseline = ap * decay + (activity['ambient_c'] * equilibrium if known_ambient else 0.)
        features = [0. if known_ambient else equilibrium, equilibrium if known_ambient else 0.,
                    slope * cfg['pre_slope_tau_s'] * (-math.expm1(-elapsed / cfg['pre_slope_tau_s'])) * decay,
                    *[z[k] - z0[k] * decay for k in range(4)]]
        values.append(baseline + math.fsum(x * c for x, c in zip(features, coefficients)))
    return {'ap_c': values, 'reference': reference, 'required_flags': required_flags, 'z0': z0}


def independent_energy(activity, profile, window):
    lo, hi = window
    coverage = activity['activity_coverage_s']
    if coverage[0] > lo or coverage[1] < hi:
        return {'historical_conditional_J': None, 'status': 'UNKNOWN_WINDOW_COVERAGE'}
    occupancy = {key: 0. for key in (*STATES, 'resident_idle')}
    for start, end, label in segments(activity):
        occupancy[label] += max(0., min(end, hi) - max(start, lo))
    baseline = profile['measured35']['baseline_w'] * (hi - lo)
    terms = {label: occupancy[label] * profile['cost_anchor']['energy_increment_w'][label] for label in STATES}
    return {'historical_conditional_J': baseline + math.fsum(terms.values()),
            'status': 'HISTORICAL_GAUGE_CONDITIONAL_ONLY', 'state_seconds': occupancy,
            'baseline_J': baseline, 'increment_terms_J': terms, 'window_s': window}


def audit_trace(checks, raw, row, source_requests, allowed_training, model, profile, forecast_operation):
    identity = row['identity']
    public, prediction, activity = raw['public_input'], raw['simulation'], raw['simulated_activity']
    requests = prediction['requests']
    by_id, public_by_id = {q['request_id']: q for q in requests}, {q['request_id']: q for q in public['requests']}
    checks.check(len(by_id) == len(requests) == len(public_by_id) == row['metrics']['planned'], 'all_requested_exact_roster', identity)
    checks.check(set(by_id) == set(public_by_id), 'all_requested_ID_conservation', identity)
    checks.check('owner_intervals' not in public and 'state_intervals' not in public, 'no_measured_future_owner_in_public_input', identity)
    for observation in public.get('observations', []):
        checks.check(observation.get('initial_eligible') is True and finite(observation.get('hi_s')) and
                     observation['t_s'] <= observation['hi_s'] <= 0, 'public_AP_completed_past_only', identity)
    checks.equal(public.get('public_initial_context_sha256'), row.get('public_initial_context_sha256'), 'public_initial_context_binding', identity)
    checks.equal(digest({k: public[k] for k in ('public_base_sha256', 'requests', 'intervention')}),
                 public['public_scenario_sha256'], 'public_scenario_rehashed', identity)
    checks.equal(prediction['start_id'], identity, 'prediction_consumed_START_identity', identity)
    checks.equal(prediction.get('new_environment_STARTs'), 1, 'one_environment_per_schedule', identity)
    checks.check(prediction.get('mode') == 'DATA_DERIVED_PROGRESS' and prediction.get('unidentified_overlap') == 'SERIAL_INDEPENDENT',
                 'registered_progress_and_explicit_fallback', identity)
    end, drain, stop = public['observation_end_ns'], public['drain_stop_ns'], public['service_stop_ns']
    expected_owners, reservations, stages_checked = [], [], 0
    logs = defaultdict(list)
    for entry in prediction.get('rate_history', []):
        logs[(entry['request_id'], entry['stage'])].append(entry)
    for rid, request in by_id.items():
        plan = public_by_id[rid]
        for field in ('ordinal', 'task', 'priority', 'group', 'scheduled_arrival_ns', 'deadline_ns'):
            checks.equal(request.get(field), plan.get(field), 'public_plan_field_conserved_' + field, [identity, rid])
        admission = request['admission']
        checks.equal(request['actual_arrival_ns'] - request['scheduled_arrival_ns'], admission['scheduled_to_actual_ns'], 'admission_scheduled_to_actual', [identity, rid])
        checks.equal(request['queue_entry_ns'] - request['actual_arrival_ns'], admission['actual_to_queue_ns'], 'admission_actual_to_queue', [identity, rid])
        checks.check(0 <= request['scheduled_arrival_ns'] <= request['actual_arrival_ns'] <= request['queue_entry_ns'], 'causal_admission_chain', [identity, rid])
        dispatch = request.get('dispatch_ns')
        if dispatch is None:
            checks.check(request.get('response_ns') is None and request.get('available_ns') is None and request.get('route') is None,
                         'undispatched_has_no_response_release_or_route', [identity, rid])
            continue
        checks.check(request['queue_entry_ns'] <= request['reserved_at_ns'] <= dispatch < stop,
                     'ready_before_reservation_before_dispatch_before_service_stop', [identity, rid])
        checks.check((request['task'], request['route']) in (('C', 'CPU'), ('C', 'GPU'), ('D', 'CPU')), 'supported_task_route', [identity, rid])
        overhead = request['redispatch']
        checks.equal(dispatch - request['reserved_at_ns'], overhead.get('delay_ns'), 'redispatch_gap_clock', [identity, rid])
        if row['redispatch']['mode'] == 'ZERO_EXPLICIT_BASELINE':
            checks.check(overhead.get('delay_ns') == 0 and overhead.get('evidence') == 'REGISTERED_IDEAL_ZERO_ASSUMPTION' and
                         overhead.get('baseline_id') == forecast_operation['zero_redispatch_baseline_id'],
                         'zero_gap_is_named_assumption', [identity, rid])
        else:
            checks.check(overhead.get('sample_id') is not None and overhead.get('physical_latency_claim') is False,
                         'measured_gap_has_saved_sample_and_no_runtime_causal_claim', [identity, rid])
        timing = request['timing']
        checks.check(timing.get('latent_work_coordinate') == 'OBSERVED_SERIAL_NS_NOT_PHYSICAL_WORK' and
                     timing.get('response_prediction_interval_ns') is None, 'latent_whole_vector_and_no_invented_CI', [identity, rid])
        sample_id = timing.get('sample_id')
        source = source_requests.get(sample_id)
        checks.check(source is not None, 'latent_source_sample_exists', [identity, rid, sample_id])
        if source is not None:
            source_session, source_request = source
            checks.check(source_session['session_id'] in allowed_training and
                         source_session['cohort_id'] in timing['source']['cohort_id'], 'latent_source_in_allowed_training', [identity, rid])
            source_route = source_request.get('route', source_request.get('backend', source_request.get('requested_backend')))
            checks.check(source_request['task'] == request['task'] and source_route == request['route'], 'latent_same_task_route', [identity, rid])
            vector = source_request.get('phases_ns')
            if vector is None:
                phases = source_request.get('phases_s')
                vector = [round(phases[key] * NS) for key in ('dispatch_to_execution', 'execution_to_output', 'output_to_persist', 'persist_to_worker_release', 'worker_release_to_available')] if isinstance(phases, dict) else [round(x * NS) for x in phases] if isinstance(phases, list) else None
            checks.equal(timing['stages_ns'], vector, 'whole_selected_vector_matches_observed_source', [identity, rid])
        vector = timing['stages_ns']
        checks.check(len(vector) == 5 and all(type(v) is int and v >= 0 for v in vector), 'five_nonnegative_latent_stages', [identity, rid])
        selection = timing['selection']
        checks.check(type(selection.get('sample_index')) is int and 0 <= selection['sample_index'] < selection['support_requests'] and
                     selection.get('validation_status') == 'UNVALIDATED', 'saved_latent_index_and_support_metadata', [identity, rid])
        potential = [[public['public_base_sha256'], row['seed']], request['ordinal'], rid]
        expected_potential = digest(['A24-PROTOCOL-TIMING-v1', prediction['model']['seed'], potential, 'service'])
        checks.equal(selection['potential_sha256'], expected_potential, 'policy_independent_CRN_potential', [identity, rid])
        if prediction['model']['estimator'] == 'empirical':
            checks.equal(selection['sample_index'], int(expected_potential, 16) % selection['support_requests'], 'empirical_saved_index_arithmetic', [identity, rid])
        clocks = [dispatch] + [request.get(boundary + '_ns') for boundary in BOUNDARIES]
        seen_missing = False
        for at in clocks:
            if at is None:
                seen_missing = True
            else:
                checks.check(not seen_missing and type(at) is int and dispatch <= at <= end, 'phase_prefix_and_window', [identity, rid])
        known = [at for at in clocks if at is not None]
        checks.check(all(a <= b for a, b in zip(known, known[1:])), 'five_phase_monotonic_clocks', [identity, rid])
        checks.equal(request.get('response_ns'), request.get(('output_ready' if request['task'] == 'C' else 'persist_complete') + '_ns'),
                     'C_output_D_persist_response_boundary', [identity, rid])
        checks.equal(request.get('available_ns'), request.get('lane_available_ns'), 'AVAILABLE_exact_lane_release', [identity, rid])
        for stage in range(min(5, len(known) - 1)):
            lo, hi = clocks[stage], clocks[stage + 1]
            stage_logs = sorted(logs[(rid, stage)], key=lambda r: r['time_ns'])
            integral = 0.
            max_rate = 1.
            for index, record in enumerate(stage_logs):
                right = stage_logs[index + 1]['time_ns'] if index + 1 < len(stage_logs) else hi
                duration = max(0, min(right, hi) - max(record['time_ns'], lo))
                checks.check(finite(record['rate']) and record['rate'] > 0, 'positive_public_progress_rate', [identity, rid, stage])
                integral += duration * record['rate']
                max_rate = max(max_rate, record['rate'])
            checks.check(abs(integral - vector[stage]) <= max_rate + 1e-5, 'stage_work_integral_integer_ceiling',
                         [identity, rid, stage, integral, vector[stage]])
            stages_checked += 1
        available = request.get('available_ns')
        release = available if available is not None else end
        reservations.append({'start_s': request['reserved_at_ns'] / NS, 'end_s': release / NS,
                             'task': request['task'], 'route': request['route'], 'request_id': rid})
        clipped = min(end, release)
        if dispatch < clipped:
            expected_owners.append({'start_s': dispatch / NS, 'end_s': clipped / NS, 'request_id': rid,
                                    'task': request['task'], 'route': request['route'],
                                    'end_is_censored_forecast_window': available is None or available > end})
    checks.equal(activity['owner_intervals'], expected_owners, 'owners_derived_only_from_saved_new_schedule', identity)
    checks.equal(activity.get('activity_coverage_s'), [0., end / NS], 'model_activity_forecast_coverage', identity)
    checks.check(activity.get('actual_recorded_window_s') is None and activity.get('counterfactual') is True,
                 'new_activity_not_device_observation', identity)
    actual_segments = segments(activity)
    # Reservation intervals independently enforce resource locks, including
    # controller latency before execution begins, and every incomplete owner.
    if reservations:
        segments({'owner_intervals': reservations, 'activity_coverage_s': [0., end / NS]})
    for record in prediction.get('rate_history', []):
        at = record['time_ns'] / NS
        active = {(q['task'], q['route']) for q in expected_owners if q['start_s'] <= at < q['end_s']}
        checks.equal(record['public_overlap'], active == {('C', 'GPU'), ('D', 'CPU')}, 'progress_uses_only_current_public_owners', [identity, at])
        if not record['public_overlap']:
            checks.equal(record['rate'], 1., 'serial_progress_unit_rate', [identity, at])
    wait, waits = 0, []
    for decision in prediction.get('decisions', []):
        now, state = decision['time_ns'], decision['public_state']
        checks.equal(digest(state), decision['public_state_sha256'], 'public_state_rehashed', [identity, now])
        checks.equal(state.get('now_ns'), now, 'public_decision_clock', [identity, now])
        for item in state['queue']:
            checks.check(set(item) <= {'request_id', 'ordinal', 'task', 'priority', 'group', 'scheduled_arrival_ns', 'queue_entry_ns', 'deadline_ns'} and
                         item['queue_entry_ns'] <= now, 'queue_visibility_no_future_outcomes', [identity, now])
        for item in state['owners']:
            checks.check(set(item) <= {'request_id', 'task', 'route', 'dispatch_ns', 'reservation_id', 'protocol'} and
                         item['dispatch_ns'] <= now, 'owner_visibility_no_latent_finish', [identity, now])
        action = decision.get('applied_control') or decision['action']
        if action.get('kind') == 'WAIT':
            dose = action['wait_ns']
            checks.check(type(dose) is int and dose > 0, 'positive_WAIT_dose', [identity, now])
            wait += dose
            waits.append((now, min(stop, now + dose)))
    checks.equal(prediction['wait_used_ns'], wait, 'WAIT_cumulative_control_conservation', identity)
    checks.check(wait <= 12 * NS, 'WAIT_global12s_cap', identity)
    for request in requests:
        if request.get('reserved_at_ns') is not None:
            checks.check(not any(a < request['reserved_at_ns'] < b for a, b in waits), 'no_dispatch_reservation_inside_WAIT', [identity, request['request_id']])
    deadline = audit_summary(checks, row['deadline_summary'], requests, identity, drain=drain)
    metrics = row['metrics']
    for key, value in {'planned': len(requests), 'response_completed': deadline['_completed'], 'on_time': deadline['on_time'],
                       'on_time_rate_planned': deadline['on_time_rate_planned'], 'response_missing': deadline['uncompleted'],
                       'AVAILABLE_by_drain': sum(q.get('available_ns') is not None and q['available_ns'] <= drain for q in requests),
                       'service_stop_ns': stop, 'drain_stop_ns': drain}.items():
        checks.equal(metrics.get(key), value, 'simulator_metrics_' + key, identity)
    checks.equal(metrics.get('incomplete_by_drain'), len(requests) - metrics['AVAILABLE_by_drain'], 'AVAILABLE_incomplete_conservation', identity)
    checks.equal(row['gantt'], [[o['start_s'], o['end_s'], o['task'], o['route']] for o in expected_owners], 'gantt_exact_generated_owners', identity)
    energy_window = [forecast_operation.get('energy_start_s', 0.), forecast_operation.get('energy_end_s', 180.)]
    for key, window in (('historical_conditional_energy', energy_window), ('historical_conditional_energy_full_forecast_window', [0., end / NS])):
        rebuilt = independent_energy(activity, profile, window)
        saved = raw[key]
        for field, value in rebuilt.items():
            checks.equal(saved.get(field), value, 'conditional_energy_' + field, [identity, key])
        checks.check(saved.get('measured_J') is None and saved.get('energy_error_J') is None, 'historical_J_never_measured_energy', [identity, key])
    checks.equal(row.get('historical_conditional_J'), raw['historical_conditional_energy'].get('historical_conditional_J'), 'row_J_matches_raw', identity)
    checks.equal(row.get('historical_conditional_J_full_forecast_window'), raw['historical_conditional_energy_full_forecast_window'].get('historical_conditional_J'), 'row_full_J_matches_raw', identity)
    work = row['work_scope']
    for label, cutoff in (('energy_end', energy_window[1] * NS), ('drain', drain)):
        checks.equal(work.get('responded_by_' + label), sum(q.get('response_ns') is not None and q['response_ns'] <= cutoff for q in requests), 'work_responded_' + label, identity)
        checks.equal(work.get('AVAILABLE_by_' + label), sum(q.get('available_ns') is not None and q['available_ns'] <= cutoff for q in requests), 'work_AVAILABLE_' + label, identity)
    checks.equal(work.get('unfinished_by_drain'), len(requests) - work['AVAILABLE_by_drain'], 'work_unfinished_denominator', identity)
    for label, cutoff in (('service', stop), ('drain', drain), ('energy', energy_window[1] * NS)):
        active = [q['request_id'] for q in requests if q.get('dispatch_ns') is not None and q['dispatch_ns'] <= cutoff and
                  (q.get('available_ns') is None or q['available_ns'] > cutoff)]
        checks.equal(work.get('owners_at_' + label + '_cutoff'), active, 'residual_cutoff_owners_' + label, identity)
    after = sum(max(0, min(q.get('available_ns') if q.get('available_ns') is not None else end, end) - max(q['dispatch_ns'], energy_window[1] * NS)) / NS
                for q in requests if q.get('dispatch_ns') is not None)
    checks.equal(work.get('modeled_owner_seconds_after_energy_window'), after, 'work_shift_after_Jwindow_visible', identity)
    checks.check(work.get('energy_decrease_is_efficiency_or_goal_PASS') is False and row.get('measured_J') is None and
                 row.get('physical_goal_pass') is False and row.get('predictive_accuracy_PASS') is None and row.get('RL_connected') is False,
                 'no_partial_work_energy_or_new_RL_PASS_claim', identity)
    ap = raw['AP_prediction']
    checks.equal(row.get('AP_status'), ap.get('status'), 'AP_status_row_raw_conservation', identity)
    checks.equal(row.get('AP_points'), [[t, v] for t, v in zip(ap['t_s'], ap['ap_c'])], 'AP_points_row_raw_conservation', identity)
    if ap.get('status') == 'CONDITIONAL_AP_PREDICTION':
        rebuilt = independent_AP(model, activity, ap['t_s'], ap, forecast_operation.get('AP_reference_domain'))
        checks.equal(ap.get('coefficient_reference_domain'), rebuilt['reference'], 'AP_public_reference_domain_rule', identity)
        checks.check(set(rebuilt['required_flags']) <= set(ap.get('extrapolation_flags', [])), 'AP_transfer_assumptions_disclosed', identity)
        for at, saved, independent in zip(ap['t_s'], ap['ap_c'], rebuilt['ap_c']):
            checks.equal(saved, independent, 'AP_independent_scalar_state_propagation', [identity, at])
        checks.equal(ap.get('real_activity_state_at_anchor'), rebuilt['z0'], 'AP_real_anchor_activity_memory', identity)
    else:
        checks.check(ap.get('status') == 'UNKNOWN' and all(value is None for value in ap['ap_c']), 'unknown_AP_is_null', identity)
    window = row['AP_summary_window_s']
    selected = [(t, v) for t, v in zip(ap['t_s'], ap['ap_c']) if window[0] <= t <= window[1]]
    identified = ap.get('status') == 'CONDITIONAL_AP_PREDICTION' and selected and selected[0][0] == window[0] and selected[-1][0] == window[1] and all(finite(v) for _, v in selected)
    mean = sum((b[0] - a[0]) * (a[1] + b[1]) / 2 for a, b in zip(selected, selected[1:])) / (window[1] - window[0]) if identified else None
    endpoint = selected[-1][1] if identified else None
    for key, value in {'AP_mean_c': mean, 'AP_peak_c': max(v for _, v in selected) if identified else None,
                       'AP_endpoint_c': endpoint, 'AP_residual_c': endpoint - public['initial_ap_c'] if endpoint is not None and finite(public.get('initial_ap_c')) else None}.items():
        checks.equal(row.get(key), value, 'AP_summary_' + key, identity)
    checks.equal(row.get('compact', raw['compact']).get('metrics'), raw['compact']['metrics'], 'raw_compact_metric_conservation', identity)
    return {'identity': identity, 'planned': len(requests), 'dispatched': len(expected_owners), 'completed_stages_audited': stages_checked,
            'AP_points': len(ap['t_s']), 'AP_status': ap.get('status'), 'on_time': deadline['on_time'],
            'uncompleted': deadline['uncompleted'], 'WAIT_s': wait / NS,
            'modeled_censored_owner_hold': any(o['end_is_censored_forecast_window'] for o in expected_owners),
            'software_arithmetic_only': True, 'new_simulation_START': 0}
