"""Build source-bound report JSON from saved registered artifacts only.

No work runs on import. No model/simulator/fit/browser/network is imported.
CLI: python build_report_data.py --operation <new parent-registered operation>
The runtime guard owns exclusive output creation, source/input/protection pins
and process/free-space checks. This source never changes a source result/HTML.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
import random

from runtime_guard import canonical, operation, pin, read, sha, write_new

SCHEMA = 'A24-source-bound-report-data-v1'
CV_MODES = ('old-only', 'm8-only', 'combined')
ZERO_FIELDS = ('new_environment', 'HTTP', 'device_commands', 'NN', 'fit', 'optimizer', 'selection')
COHORT_BOOTSTRAP_REPETITIONS = 2000
COHORT_BOOTSTRAP_SEED = 20261016


def require(ok, message):
    if not ok:
        raise ValueError(message)


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def identity(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def q95(values):
    values = sorted(x for x in values if finite(x))
    if not values:
        return None
    at = .95 * (len(values)-1)
    left = int(math.floor(at)); right = min(len(values)-1, left+1)
    return values[left] + (values[right]-values[left]) * (at-left)


def percentile(values, probability):
    values = sorted(values)
    if not values:
        return None
    at = probability*(len(values)-1)
    left = int(math.floor(at)); right = min(len(values)-1, left+1)
    return values[left] + (values[right]-values[left])*(at-left)


def fstr(value, digits=3, suffix=''):
    return f'{value:.{digits}f}{suffix}' if finite(value) else '미확인'


def source_request_metrics(session):
    """Correct report-only fields; never reuse the frozen default180s bound.

    A missing record is not proof that no response existed until sensor end.
    Qualified censor bounds therefore remain null unless an explicit continuous
    response-tracking contract is present. Assumption-only arithmetic is named
    separately. All planned missing/failed requests remain in the denominator.
    """
    requests = session.get('requests', [])
    planned_window = session.get('planned_windows') or {}
    cutoff = planned_window.get('service_cutoff_s')
    recorded = session.get('actual_recorded_window_s', session.get('observation_window_s'))
    observed_end = recorded[1] if isinstance(recorded, list) and len(recorded) == 2 and finite(recorded[1]) else None
    tracking = session.get('continuous_response_tracking_verified') is True
    report = {'derivation': 'REPORT_ONLY_SOURCE_SERVICE_CUTOFF_AND_ACTUAL_RECORDED_WINDOW_V1',
              'source_service_cutoff_s': cutoff, 'actual_recorded_observation_end_s': observed_end,
              'overrides_frozen_analysis_default_180_s': True,
              'continuous_response_tracking_verified': tracking,
              'missing_telemetry_is_proof_of_nonresponse': False, 'by_cohort': {}}
    if not requests and session.get('source_family') == 'old':
        report.update(status='UNKNOWN_HISTORICAL_NORMALIZED_REQUEST_TABLE_ABSENT',
                      planned_request_count=None)
        return report
    report.update(status='ALL_SAVED_PLANNED_REQUESTS_RETAINED', planned_request_count=len(requests))
    for name in ('ALL', 'U', 'N', 'C', 'D', 'CU', 'CN', 'DU', 'DN'):
        selected = [r for r in requests if name in ('ALL', r.get('priority'), r.get('task'),
                                                    str(r.get('task')) + str(r.get('priority')))]
        responded = [r for r in selected if finite(r.get('response_s'))]
        latencies = [r['response_s']-r['scheduled_arrival_s'] for r in responded if finite(r.get('scheduled_arrival_s'))]
        missing = [r for r in selected if not finite(r.get('response_s'))]
        deadline_met = sum(finite(r.get('deadline_s')) and r['response_s'] <= r['deadline_s'] for r in responded)
        service_success = (sum(finite(r.get('deadline_s')) and r['response_s'] <= min(cutoff, r['deadline_s'])
                               for r in responded) if finite(cutoff) else None)
        bounds = []
        for r in missing:
            candidate = max(0., observed_end-r['deadline_s']) if finite(observed_end) and finite(r.get('deadline_s')) else None
            bounds.append({'request_id': r.get('request_id'),
                           'recorded_end_assumption_only_bound_s': candidate,
                           'qualified_tardiness_lower_bound_s': candidate if tracking else None,
                           'reason': None if tracking else 'MISSING_TELEMETRY_DOES_NOT_PROVE_CONTINUOUS_NONRESPONSE'})
        report['by_cohort'][name] = {'planned': len(selected), 'responded': len(responded),
            'missing_or_invalid_response': len(missing), 'failed_declared': sum(r.get('status') == 'FAILED' for r in selected),
            'deadline_met_any_recorded_time': deadline_met,
            'on_time_within_source_service_cutoff': service_success,
            'service_fraction': service_success/len(selected) if selected and service_success is not None else None,
            'response_P95_s': q95(latencies), 'response_P95_denominator': len(latencies),
            'response_P95_population': 'VALID_COMPLETED_RESPONSES_ONLY',
            'no_valid_response_not_counted_success': True, 'missing_response_bounds': bounds}
    return report


def thin_sessions(dataset):
    """Retain chart/coverage data, release repeated provenance before large CV read."""
    sessions = dataset.get('sessions')
    require(isinstance(sessions, list) and sessions, 'Saved normalized sessions required')
    require(len({s['session_id'] for s in sessions}) == len(sessions), 'Duplicate report session identity')
    result = []
    for session in sessions:
        observations = [r for r in session.get('observations', [])
                        if r.get('channel') == 'AP' and finite(r.get('t_s'))]
        observations.sort(key=lambda r: r['t_s'])
        valid = [r for r in observations if finite(r.get('ap_c'))]
        gaps = [{'left_s': a['t_s'], 'right_s': b['t_s'], 'gap_s': b['t_s']-a['t_s']}
                for a,b in zip(valid, valid[1:]) if b['t_s']-a['t_s'] > 5.]
        compatibility = session.get('compatibility') or {}
        result.append({k: session.get(k) for k in ('session_id', 'cohort_id', 'source_family',
            'source_generation', 'family', 'block', 'arm', 'bank', 'protocol', 'original_role',
            'observed_role', 'role', 'initial_ap_c', 'initial_ap_time_s', 'initial_ap_hi_s',
            'forecast_origin_s', 'prehistory_start_s', 'actual_recorded_window_s', 'activity_coverage_s',
            'target_eligibility', 'target_exclusions', 'clock_issues', 'exclusion', 'use')}
            | {'observed': [[r['t_s'], r.get('ap_c')] for r in observations],
               'observed_AP_samples': len(valid), 'observed_AP_nulls': len(observations)-len(valid),
               'actual_AP_window_s': [valid[0]['t_s'], valid[-1]['t_s']] if valid else None,
               'observed_long_gaps': gaps, 'max_plot_gap_s': 5.,
               'compatibility': {k: compatibility.get(k) for k in
                    ('ap_sensor_contract_qualified', 'ap_activity_domain', 'activity_pool_qualified',
                     'within_domain_exploratory', 'M8_activity_pool_qualified', 'source_clock_authority',
                     'installed_APK_verified', 'signer_verified', 'quality_binding_verified')},
               'request_metrics_report': source_request_metrics(session),
               'owner_interval_count': len(session.get('owner_intervals', [])),
               'aggregate_state_interval_count': len(session.get('state_intervals', [])),
               'source_dataset_pointer': '/sessions/' + str(len(result))})
    return result


def selected_cv(cv, selection, session_ids):
    require(cv.get('fresh_confirmation') is False and cv.get('physical_goal_pass') is False,
            'CV role/physical boundary differs')
    require(selection.get('selection') == cv.get('selection'), 'Frozen selection/CV binding differs')
    folds = cv.get('folds', {}).get('folds', [])
    membership = {}
    for fold in folds:
        train, held = set(fold['training_session_ids']), set(fold['heldout_session_ids'])
        require(not train.intersection(held) and train.union(held) == set(session_ids), 'CV training/heldout roster differs')
        for sid in held:
            require(sid not in membership, 'A report session appears in multiple heldout folds')
            membership[sid] = fold['fold_id']
    require(set(membership) == set(session_ids), 'Not all report sessions have a heldout fold')
    candidates = {c['candidate_index']: c for c in cv.get('candidates', [])}
    selected = {}
    for mode in CV_MODES:
        choice = selection['selection'].get(mode, {})
        if choice.get('status') != 'POSTHOC_DEVELOPMENT_SELECTED':
            selected[mode] = {'status': choice.get('status', 'UNKNOWN'), 'predictions': {}, 'rows': {},
                              'summary': choice.get('summary', {}), 'choice': choice}
            continue
        require(choice['candidate_index'] in candidates, 'Selected thermal candidate absent')
        candidate = candidates[choice['candidate_index']]
        require(candidate['config'] == choice['config'], 'Selected candidate configuration differs')
        saved = candidate['modes'][mode]
        predictions = {r['session_id']: r for r in saved['predictions']}
        rows = {r['session_id']: r for r in saved['rows']}
        require(len(predictions) == len(saved['predictions']) and len(rows) == len(saved['rows']), 'Duplicate CV session row')
        require(set(predictions) == set(session_ids) and set(rows) == set(session_ids), 'Selected CV mode omitted sessions')
        clean_predictions = {}
        for sid, r in predictions.items():
            require(r['fold_id'] == rows[sid]['fold_id'] == membership[sid], 'CV model/score/fold binding differs')
            require(len(r['t_s']) == len(r['ap_c']), 'CV prediction time/value length differs')
            clean_predictions[sid] = {k: r.get(k) for k in
                ('session_id', 'fold_id', 'status', 'reason', 'model_sha256', 'extrapolation_flags',
                 'coefficient_reference_domain', 'activity_domain', 'contract_equivalence_verified',
                 'anchor_s', 'initial_ap_c', 'initial_input_latest_hi_s')}
            clean_predictions[sid]['series'] = [[t,v] for t,v in zip(r['t_s'],r['ap_c'])]
        selected[mode] = {'status': choice['status'], 'choice': choice, 'summary': saved['summary'],
                          'predictions': clean_predictions, 'rows': rows}
    return selected, {'folds': folds, 'groups': cv.get('folds', {}).get('groups', {}),
                      'fold_sha256': cv.get('folds', {}).get('fold_sha256'), 'membership': membership}


def observer_summary(body):
    rows = body if isinstance(body, list) else body.get('sessions', [])
    require(isinstance(rows, list), 'Unknown historical observer schema')
    result = {}
    for row in rows:
        require(row['session_id'] not in result, 'Duplicate historical observer session')
        result[row['session_id']] = {'conditional_energy': row.get('conditional_energy'),
            'original_historical_AP_diagnostics': [{k: r.get(k) for k in
                ('status','historical_model','reason','MAE_C','conditional_on_actual_schedule')}
                for r in row.get('historical_AP', [])],
            'role': 'ORIGINAL_EQUATIONS_DESCRIPTIVE_DIAGNOSTIC_NOT_SELECTED_CV_BASELINE'}
    return result


def timing_summary(body):
    rows = body.get('rows', [])
    by = {}
    for row in rows:
        key = row.get('candidate', 'UNKNOWN')
        item = by.setdefault(key, {'configuration': row.get('configuration'), 'all_heldout_requests': 0,
                                    'validated_requests': 0, 'errors_ns': [], 'unknown_reasons': Counter()})
        item['all_heldout_requests'] += 1
        if finite(row.get('prediction_error_ns')):
            item['validated_requests'] += 1; item['errors_ns'].append(row['prediction_error_ns'])
        else:
            item['unknown_reasons'][str(row.get('unknown_reason', row.get('status')))] += 1
    for item in by.values():
        errors = item.pop('errors_ns')
        item['response_MAE_s'] = sum(abs(x) for x in errors)/len(errors)/1e9 if errors else None
        item['worst_absolute_response_error_s'] = max(map(abs, errors))/1e9 if errors else None
        item['unknown_reasons'] = dict(item['unknown_reasons'])
    return {'role': body.get('role'), 'candidates': by, 'strata': body.get('strata'),
            'model_builds': body.get('model_builds'), 'confidence_interval': body.get('confidence_interval'),
            'selection': None, 'unknowns_retained': True,
            'validation_scope': body.get('queue_overlap_deadline_validation')}


def paired_thermal_CV(selected, fold_info, sessions):
    """Paired differences on the same heldout sessions, linked cohorts intact.

    Resampling descriptive selected-CV errors does not refit, create new
    observations, remove selection optimism or become fresh confirmation.
    Separate marginal global CIs are never substituted for this paired CI.
    """
    membership = {}
    for group_id, members in fold_info['groups'].items():
        for sid in members:
            require(sid not in membership, 'Session duplicated across bootstrap whole groups')
            membership[sid] = group_id
    require(set(membership) == {s['session_id'] for s in sessions}, 'Bootstrap group roster differs')
    comparisons = []
    for reference in ('old-only','m8-only'):
        paired_rows, clusters = [], {}
        for session in sessions:
            sid = session['session_id']
            a = selected['combined']['rows'].get(sid, {})
            b = selected[reference]['rows'].get(sid, {})
            same_fold = a.get('fold_id') == b.get('fold_id') == fold_info['membership'][sid]
            qualified = same_fold and finite(a.get('mae_c')) and finite(b.get('mae_c'))
            delta = a['mae_c']-b['mae_c'] if qualified else None
            row = {'session_id':sid,'cohort_id':session['cohort_id'],'whole_linked_group':membership[sid],
                'heldout_fold':fold_info['membership'][sid], 'combined_MAE_C':a.get('mae_c'),
                'reference_MAE_C':b.get('mae_c'),'delta_combined_minus_reference_C':delta,
                'paired_qualified':qualified,'same_heldout_fold':same_fold,
                'unknown_reason':None if qualified else 'BOTH_SAME_HELDOUT_VALID_MAE_REQUIRED',
                'combined_status':a.get('predicted'),'reference_status':b.get('predicted')}
            paired_rows.append(row)
            if qualified:
                clusters.setdefault(membership[sid], []).append(row)
        cluster_rows = [{'whole_linked_group':key,'paired_sessions':len(value),
            'session_ids':[r['session_id'] for r in value],
            'cohort_labels':sorted({r['cohort_id'] for r in value}),
            'mean_paired_delta_C':sum(r['delta_combined_minus_reference_C'] for r in value)/len(value)}
            for key,value in sorted(clusters.items())]
        means = [r['mean_paired_delta_C'] for r in cluster_rows]
        delta = sum(means)/len(means) if means else None
        ci = None
        if len(means) >= 2:
            rng = random.Random(COHORT_BOOTSTRAP_SEED)
            boot = [sum(rng.choice(means) for _ in means)/len(means)
                    for _ in range(COHORT_BOOTSTRAP_REPETITIONS)]
            ci = [percentile(boot,.025),percentile(boot,.975)]
        valid = [r for r in paired_rows if r['paired_qualified']]
        deterioration = max((r['delta_combined_minus_reference_C'] for r in valid), default=None)
        comparisons.append({'id':'combined_vs_'+reference,'reference_mode':reference,'candidate_mode':'combined',
            'direction':'NEGATIVE_DELTA_MEANS_LOWER_COMBINED_MAE',
            'all_heldout_sessions':len(sessions),'paired_sessions':len(valid),
            'unknown_or_unpaired_sessions':len(sessions)-len(valid),
            'all_linked_whole_groups':len(fold_info['groups']),'paired_whole_groups':len(cluster_rows),
            'cohort_balanced_paired_MAE_delta_C':delta,'paired_CI95_C':ci,
            'CI_reason':None if ci is not None else 'FEWER_THAN_TWO_QUALIFIED_WHOLE_GROUPS',
            'bootstrap_repetitions':COHORT_BOOTSTRAP_REPETITIONS,'bootstrap_seed':COHORT_BOOTSTRAP_SEED,
            'bootstrap_unit':'WHOLE_CV_LINKED_COHORT_GROUP; session/raw clones never split',
            'CI_role':'POSTHOC_SELECTED_CV_DEVELOPMENT_NOT_FRESH_CONFIRMATION',
            'same_CV_hyperparameter_selection_optimism':True,
            'marginal_global_CIs_are_not_paired_difference_CIs':True,
            'sessions_worse':sum(r['delta_combined_minus_reference_C'] > 0 for r in valid),
            'sessions_better':sum(r['delta_combined_minus_reference_C'] < 0 for r in valid),
            'sessions_tied':sum(r['delta_combined_minus_reference_C'] == 0 for r in valid),
            'worst_session_delta_C':deterioration,
            'worst_session_ids':[r['session_id'] for r in valid if r['delta_combined_minus_reference_C']==deterioration],
            'session_rows':paired_rows,'whole_group_rows':cluster_rows,
            'new_fit':0,'new_observations':0,'fresh_confirmation':False,
            'measured_J':None,'energy_error_CI_J':None,'physical_goal_pass':False})
    return comparisons


def forecast_scenarios(body):
    """Strict saved forecast adapter. Unknown schemas fail, never vanish as zero."""
    require(body.get('schema') == 'A24-report-forecast-scenarios-v1', 'Unsupported saved forecast report adapter schema')
    scenarios = body.get('scenarios')
    require(isinstance(scenarios, list), 'Saved forecast scenarios required')
    require(len({s['id'] for s in scenarios}) == len(scenarios), 'Duplicate scenario identity')
    result = []
    for s in scenarios:
        require(isinstance(s.get('rows'), list), 'All scenario policy rows required')
        require('conditions' in s and 'seed' in s, 'Scenario conditions and seed must be preserved')
        rows = []
        for row in s['rows']:
            require(isinstance(row.get('policy'), str), 'Forecast policy identity required')
            require(row.get('measured_J') is None, 'Forecast cannot contain measured J')
            normalized = dict(row)
            AP = row.get('ap_prediction') or []
            at180 = [p[1] for p in AP if isinstance(p,list) and len(p)==2 and p[0]==180. and finite(p[1])]
            require(len(set(at180)) <= 1, 'Conflicting normalized exact180s AP')
            normalized['source_report_legacy_AP_residual_C'] = row.get('AP_residual_C')
            normalized['AP_residual_C'] = at180[0] if at180 else None
            normalized['AP_at180_C'] = normalized['AP_residual_C']
            normalized['AP_at180_status'] = 'EXACT_SAVED_180S_QUERY' if at180 else 'UNKNOWN_NO_EXACT_180S_PREDICTION'
            normalized['conditional_J_is_efficiency_claim'] = False
            normalized.setdefault('work_equivalence_status','UNKNOWN_WORK_EQUIVALENCE')
            rows.append(normalized)
        result.append({**s, 'rows': rows,
            'note': s.get('note', '') + ' · 조건 ' + canonical(s['conditions']) + ' · seed ' + str(s['seed']),
            'limits': s.get('limits') or '가정·외삽·미확인 항목을 아래 검산 정보에 유지합니다. 조건부 J는 새 실측 J가 아닙니다.'})
    return result


def saved_forecast_rows(spec):
    rows, ids = [], set()
    with pin(spec).open('r', encoding='utf-8-sig') as handle:
        for line_no, text in enumerate(handle, 1):
            if not text.strip():
                continue
            row = json.loads(text)
            require(isinstance(row, dict) and isinstance(row.get('identity'), str), 'Forecast row identity required')
            require(row['identity'] not in ids, 'Duplicate forecast identity')
            ids.add(row['identity'])
            rows.append({**row, 'report_source_line': line_no})
    return rows


def forecast_receipt_summary(spec):
    records = []
    with pin(spec).open('r', encoding='utf-8-sig') as handle:
        for line_no, text in enumerate(handle,1):
            if text.strip():
                record = json.loads(text)
                require(isinstance(record,dict), 'Forecast receipt must be object')
                records.append({**record,'report_source_line':line_no})
    starts = [r for r in records if r.get('event') == 'START']
    require(len({r['identity'] for r in starts}) == len(starts), 'Duplicate simulator START identity')
    terminal = [r for r in records if r.get('event') in ('COMPLETE','FAIL')]
    return {'event_counts':dict(Counter(str(r.get('event')) for r in records)),
            'simulator_STARTs':len(starts),'START_identities':[r['identity'] for r in starts],
            'terminal_records':terminal,'all_STARTs_remain_consumed':True,
            'report_generation_STARTs':0,'forecast_rows_are_not_START_count':True}


def join_forecast_case_roster(case_status, rows, receipt_summary):
    require(case_status.get('schema') == 'A24-REGISTERED-RULE-FORECAST-v1-CASE-STATUS', 'Unknown complete forecast case roster schema')
    cases = case_status.get('cases')
    require(isinstance(cases,list) and len(cases) == case_status.get('registered_case_roster'), 'Forecast planned case roster incomplete')
    require(case_status.get('no_unknown_or_failed_case_dropped') is True, 'Complete unknown/failed case ledger required')
    by_identity = {r['identity']:r for r in rows}
    require(len(by_identity) == len(rows), 'Duplicate saved forecast row identity')
    used, planned_keys, joined = set(), set(), []
    for index, case in enumerate(cases):
        require(isinstance(case,dict), 'Forecast case entry must be object')
        key = identity({k:case.get(k) for k in ('label','kind','bank','intervention','policy','seed',
                                               'public_scenario_sha256','public_initial_context_sha256','source_session_id')})
        require(key not in planned_keys, 'Duplicate planned forecast case')
        planned_keys.add(key)
        row_id = case.get('row_identity')
        if row_id is not None:
            require(row_id in by_identity and row_id not in used, 'Forecast case/row identity binding differs')
            source = by_identity[row_id]; used.add(row_id)
            for name in ('kind','bank','policy','seed','comparison_group_id','public_scenario_sha256','public_initial_context_sha256'):
                require(case.get(name) == source.get(name), 'Forecast case/public row differs: '+name)
            merged = {**source, 'case_status':case, 'status':case['status']}
        else:
            merged = {**case, 'case_status':case, 'metrics':{'planned':case.get('planned'), 'on_time':None,
                'incomplete_by_drain':None}, 'deadline_summary':{},
                'AP_status':'UNKNOWN_NO_COMPLETED_SOURCE_FORECAST_ROW', 'AP_points':[], 'gantt':[],
                'owner_history_unknown':True, 'uncertainty_flags':['NO_COMPLETED_SOURCE_FORECAST_ROW'],
                'report_source_line':None, 'historical_conditional_J':None}
        merged['planned_case_report_key'] = key
        merged['case_status_json_pointer'] = '/cases/'+str(index)
        joined.append(merged)
    require(used == set(by_identity), 'Saved forecast row absent from complete case roster')
    STARTs = receipt_summary['simulator_STARTs']
    require(case_status.get('simulation_START_consumed') == STARTs, 'Case roster/receipt START accounting differs')
    require(sum(c.get('simulation_START_consumed',0) for c in cases) == STARTs, 'Case consumed START sum differs')
    return joined


def native_forecast_adapter(rows):
    """Adapt compact registered rows; retain failed/unknown and validation rows.

    comparison_group_id is produced by the forecast source from public scenario,
    initial context, seed and model bindings. No pairing is invented here from
    matching filenames, policy labels, seeds or visually similar trajectories.
    """
    groups, validations = {}, []
    for row in rows:
        kind = row.get('kind')
        require(kind in ('PREDECLARED_NOVEL_GRID', 'WHOLE_COHORT_HELDOUT_VALIDATION', 'REGISTERED_CUSTOM'), 'Unknown forecast row role')
        compact = {k:v for k,v in row.items() if k not in ('manifest','AP_points','gantt')}
        if row.get('manifest') is not None:
            compact['manifest_saved_reference'] = {'forecast_row_identity':row['identity'],
                'source_line':row['report_source_line'], 'field':'manifest', 'value_sha256':identity(row['manifest'])}
        compact['AP_points_saved_in_same_source_row'] = True
        compact['gantt_saved_in_same_source_row'] = True
        if kind == 'WHOLE_COHORT_HELDOUT_VALIDATION':
            validations.append(compact)
            continue
        group_id = row.get('comparison_group_id')
        require(isinstance(group_id, str) and group_id, 'Explicit source comparison_group_id required')
        require('seed' in row and isinstance(row.get('intervention'), dict), 'Novel scenario seed/conditions required')
        condition = {'bank':row.get('bank'), 'intervention':row['intervention'],
                     'public_scenario_sha256':row.get('public_scenario_sha256'),
                     'public_initial_context_sha256':row.get('public_initial_context_sha256'),
                     'source_public_template_sha256':row.get('source_public_template_sha256')}
        s = groups.setdefault(group_id, {'id':group_id, 'label':row.get('label') or str(row.get('bank')),
            'conditions':condition, 'seed':row['seed'], 'rows':[], 'kind':kind})
        require(s['conditions'] == condition and s['seed'] == row['seed'], 'Forecast comparison group mixes public conditions/seed')
        metrics, deadlines = row.get('metrics') or {}, row.get('deadline_summary') or {}
        owner_intervals = []
        for interval in row.get('gantt') or []:
            require(isinstance(interval, list) and len(interval) >= 4, 'Unknown compact forecast Gantt schema')
            require(finite(interval[0]) and finite(interval[1]) and interval[0] <= interval[1], 'Invalid forecast owner interval')
            owner_intervals.append({'start_s':interval[0], 'end_s':interval[1], 'task':interval[2], 'route':interval[3]})
        AP = row.get('AP_points') or []
        require(all(isinstance(p,list) and len(p)==2 and finite(p[0]) and (p[1] is None or finite(p[1])) for p in AP),
                'Unknown compact forecast AP schema')
        if row.get('actual_J') is not None or row.get('measured_J') is not None:
            raise ValueError('Forecast row cannot establish measured J')
        at180 = [p[1] for p in AP if p[0] == 180. and finite(p[1])]
        require(len(set(at180)) <= 1, 'Conflicting exact180s forecast AP query points')
        AP_at180 = at180[0] if at180 else None
        work = ('ALL_REQUESTS_CLOSED_BY_DRAIN' if type(metrics.get('planned')) is int
                and metrics.get('incomplete_by_drain') == 0 else 'UNFINISHED_OR_UNKNOWN_WORK')
        s['rows'].append({**compact, 'policy':str(row.get('policy','UNKNOWN_POLICY')),
            'on_time':metrics.get('on_time'), 'planned':metrics.get('planned'),
            'P95_s':deadlines.get('P95_all_requested_response_s'),
            'P95_completed_s':deadlines.get('P95_completed_response_s'),
            'P95_all_requested_lower_bound_s':deadlines.get('P95_all_requested_response_lower_bound_s'),
            'AP_mean_C':row.get('AP_mean_c'), 'AP_peak_C':row.get('AP_peak_c'),
            'AP_residual_C':AP_at180, 'AP_at180_C':AP_at180,
            'AP_at180_status':'EXACT_SAVED_180S_QUERY' if AP_at180 is not None else 'UNKNOWN_NO_EXACT_180S_PREDICTION',
            'AP_delta_from_actual_initial_C':row.get('AP_residual_c'), 'AP_endpoint_C':row.get('AP_endpoint_c'),
            'conditional_J':row.get('historical_conditional_J'), 'measured_J':None,
            'ap_prediction':AP, 'owner_intervals':owner_intervals,
            'work_equivalence_status':work,
            'conditional_J_is_efficiency_claim':False,
            'P95_population':'ALL_REQUESTED; null is not replaced by completed-only P95',
            'owner_history_status':'SAVED_COMPLETE_COMPACT_TRACE' if 'gantt' in row and not row.get('owner_history_unknown') else 'UNKNOWN_COMPACT_TRACE_ABSENT'})
    scenarios = []
    for s in groups.values():
        s['note'] = '조건 ' + canonical(s['conditions']) + ' · seed ' + str(s['seed'])
        s['limits'] = ('등록된 미측정 일정 예측입니다. 실패·미확인·외삽을 유지합니다. '
            '전체 요청 P95가 미확인이면 완료 요청 P95로 대체하지 않습니다. J*는 과거 고정 계측 모형의 조건부 진단입니다.')
        s['limits'] += (' 180초 AP는 정확히180초의 저장 예측값이며 초기/주변온도 대비 잔열이 아닙니다. '
            '미완료 작업량이 다른 정책의 낮은 J를 효율 향상으로 해석하지 않습니다. 비교 전 work_equivalence_status를 확인합니다.')
        scenarios.append(s)
    return scenarios, validations


def assemble(sessions, selected, fold_info, observers, timing, coverage, forecasts, artifact_pins, final_models, forecast_audit=None):
    paired = paired_thermal_CV(selected, fold_info, sessions)
    output_sessions = []
    for session in sessions:
        sid = session['session_id']
        old = selected['old-only']['predictions'].get(sid, {})
        combined = selected['combined']['predictions'].get(sid, {})
        old_score = selected['old-only']['rows'].get(sid, {})
        score = selected['combined']['rows'].get(sid, {})
        flags = sorted(set(old.get('extrapolation_flags') or []).union(combined.get('extrapolation_flags') or []))
        label = ' · '.join(str(v) for v in (session['source_family'], session.get('family') or session['source_generation'],
                                          session.get('bank'), session.get('arm'), sid) if v is not None)
        note = ('관측 작업 점유 경로와 실제 초기 AP를 입력한 묶음 제외 재생 평가입니다. '
                '모형 선택에도 같은 CV를 사용한 사후 개발 결과이며 새 독립 확인이 아닙니다. '
                '모든 관측 구간을 유지했고 5초 초과 간격은 연결하지 않습니다.')
        if flags:
            note += ' 가정·외삽: ' + '; '.join(flags)
        window = session['actual_AP_window_s']
        stats = [{'label':'자료 / 평가 역할', 'value':str(session.get('source_family')) + ' / 사후 개발 CV'},
            {'label':'묶음 / 제외 fold', 'value':str(session['cohort_id']) + ' / ' + str(fold_info['membership'][sid])},
            {'label':'관측 AP / 구간', 'value':str(session['observed_AP_samples']) + '개 / ' + str(window)},
            {'label':'실제 초기 AP / 완료 시각', 'value':fstr(session.get('initial_ap_c'),3,'℃') + ' / ' + fstr(session.get('initial_ap_hi_s'),3,'초')},
            {'label':'기존 자료만 적합한 CV MAE', 'value':fstr(old_score.get('mae_c'),3,'℃')},
            {'label':'통합 후보 CV MAE / 최대 오차', 'value':fstr(score.get('mae_c'),3,'℃') + ' / ' + fstr(score.get('max_abs_error_c'),3,'℃')},
            {'label':'관측 간격 5초 초과', 'value':str(len(session['observed_long_gaps'])) + '구간'},
            {'label':'추정 상태 / 미확인 사유', 'value':str(combined.get('status','UNKNOWN')) + ' / ' + str(combined.get('reason') or '별도 가정 참조')}]
        output_sessions.append({**session, 'label': label, 'note': note, 'stats': stats,
            'old_prediction': old.get('series', []), 'prediction': combined.get('series', []),
            'series_roles': {'old_prediction':'SELECTED_OLD_ONLY_WHOLE_COHORT_HELDOUT_CV',
                             'prediction':'SELECTED_COMBINED_WHOLE_COHORT_HELDOUT_CV',
                             'original_historical':'SEPARATE_DESCRIPTIVE_DIAGNOSTIC_ONLY'},
            'selected_CV': {'old-only': {'prediction':{k:v for k,v in old.items() if k != 'series'}, 'score':old_score},
                            'combined': {'prediction':{k:v for k,v in combined.items() if k != 'series'}, 'score':score}},
            'original_historical_diagnostic': observers.get(sid), 'assumption_flags':flags})
    counts = coverage.get('confirmed_counts', {})
    actual_counts = Counter(s['source_family'] for s in sessions)
    planned = sum((s['request_metrics_report']['planned_request_count'] or 0) for s in sessions)
    AP_count = sum(s['observed_AP_samples'] for s in sessions)
    ap_eligible = sum((s.get('target_eligibility') or {}).get('ap_fit') is True for s in sessions)
    timing_eligible = sum((s.get('target_eligibility') or {}).get('timing_fit') is True for s in sessions)
    summaries = {mode: selected[mode]['summary'] for mode in CV_MODES}
    final_summary = {mode:{k:model.get(k) for k in ('status','model_sha256','config','training_session_ids','training_cohort_ids')}
                     for mode,model in (final_models or {}).get('final_models', {}).items()}
    assumptions = ['AP는 내부 HAL 관측 채널이며 표면온도 검증이 아닙니다.',
        '실측 J·에너지 오차·물리 목표 달성은 미확정입니다. 표시되는 J는 기존 고정 계측 모형의 조건부 관찰자 값입니다.',
        '기존 자료 4건과 M8 1건의 미실행은 관측 세션 115건과 별도 원장입니다.',
        '수신 ZIP 원장 76행은 초기 4개 중복 색인을 포함한 고유 경로 72개입니다.',
        '자료 전체 보존과 모형별 적격성은 다릅니다. 결측·실패·센서/코드 계약 미확인은 제외 이유와 함께 유지합니다.',
        'CV는 전체 묶음을 제외하지만 후보 시간상수·규제 선택에도 같은 CV를 썼으므로 선택 낙관성이 남습니다.',
        'CI가 존재하면 전체 cohort 재표집을 사용한 개발용 불확실성입니다. AP 표본/요청 행을 독립 반복으로 간주하지 않습니다.',
        '기존 원모형의 저장/재생 진단과 기존 자료만으로 다시 적합한 제외 묶음 CV는 다른 근거입니다.',
        '새 도착 간격·순서·CPU/GPU 배정·병행·WAIT 예측은 실측과 구분하며 지원 범위를 넘는 외삽 가정과 미확인을 남깁니다.',
        '초기 AP 이전 활동 공백, 설치 APK·실제 delegate·품질 기준 미검증을 물리적 동등성으로 바꾸지 않습니다.',
        '역사 39세션의 긴 저장 AP 투영은 보존했지만 native raw 163멤버 재검증은 0이며 전체 native prehistory 복구는 미확정입니다.',
        '요청 통계는 source service cutoff와 실제 기록 끝으로 보고서에서만 재계산했습니다. 누락 로그에 연속 미응답을 단정한 하한은 null입니다.']
    return {'schema':SCHEMA, 'measured_J':None, 'energy_error_J':None,
        'automation_status':'PAUSED', 'fresh_confirmation':False, 'physical_goal_pass':False,
        'badges':['115개 관측 세션 · 묶음 단위 CV','기존 + 수신 실측 · 사후 모형 개발','실측 J 미확정'],
        'boundary':'모형 선택과 검증은 사후 개발입니다. 미측정 일정은 예측으로 표시하며, 실제 J 절감이나 물리 목표 PASS로 해석하지 않습니다.',
        'cards':[{'label':'보존된 관측 세션','value':str(len(sessions)), 'note':'기존 '+str(actual_counts['old'])+' + M8 '+str(actual_counts['m8'])},
                 {'label':'정규화 M8 계획 요청','value':str(planned), 'note':'누락·실패도 전체 분모에 유지; 역사 요청 표는 별도 미복구'},
                 {'label':'보존 AP 관측','value':str(AP_count), 'note':'실제 전체 기록 구간; AP 적격 '+str(ap_eligible)+'세션'}],
        'sessions':output_sessions, 'scenarios':forecasts, 'paired_comparisons':paired,
        'prediction_pending':'아직 측정하지 않은 일정의 등록 예측·검산이 준비 중입니다. 이 상태는 0건 성공을 뜻하지 않습니다.',
        'inventory':[{'label':'기존 관측 / 새 수신 관측','value':str(actual_counts['old'])+' / '+str(actual_counts['m8'])},
                     {'label':'미실행 원장: 기존 / M8','value':str(counts.get('old_unattempted_ledger_entries','미확인'))+' / '+str(counts.get('m8_inventory_excluded_sessions','미확인'))},
                     {'label':'수신 ZIP 고유 경로 / 원장 행','value':str(counts.get('distinct_archive_paths','미확인'))+' / '+str(counts.get('archive_audit_occurrences','미확인'))},
                     {'label':'AP / 시간 모형 적격 세션','value':str(ap_eligible)+' / '+str(timing_eligible)},
                     {'label':'선택된 통합 CV 예측 / 미확인','value':str(summaries['combined'].get('predicted_sessions','미확인'))+' / '+str(summaries['combined'].get('unknown_sessions','미확인'))}],
        'limitations':assumptions,
        'audit':{'artifact_pins':artifact_pins, 'counts':{'sessions':len(sessions),'source_family':dict(actual_counts),
            'M8_planned_requests':planned,'AP_observations':AP_count,'coverage_ledger':counts},
            'thermal_selected_choices':{m:selected[m]['choice'] for m in CV_MODES},
            'thermal_CV_summaries':summaries,'folds':fold_info['folds'],'whole_groups':fold_info['groups'],
            'thermal_paired_comparisons':paired,
            'fold_sha256':fold_info['fold_sha256'],'timing_CV':timing,'final_models':final_summary,
            'final_fit_predictions_used_as_holdout':False,'original_historical_series_used_as_old_only_CV':False,
            'CV_selection_optimism_disclosed':True,'confidence_unit':'WHOLE_COHORT_POSTHOC_DEVELOPMENT',
            'full_scenario_conditions_seeds_unknowns_harms_retained':True,
            'forecast_row_count_is_not_simulator_START_count':True,
            'forecast_validation_and_harms':forecast_audit,
            'new_environment':0,'HTTP':0,'device_commands':0,'fits':0,'automatic_retry':False}}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--operation', required=True)
    args = parser.parse_args()
    with operation(args.operation, __file__) as (op, out):
        require(op.get('mode') == 'REPORT_DATA', 'Wrong saved-report operation mode')
        for field in ZERO_FIELDS:
            require(type(op.get(field)) is int and op[field] == 0, 'Saved-only zero boundary differs: '+field)
        require(op.get('automation_status') == 'PAUSED', 'Automation boundary differs')
        dataset = read(pin(op['dataset_pin']))
        sessions = thin_sessions(dataset)
        require(len(sessions) == op['expected_sessions'], 'All-session report roster count differs')
        require(identity([s['session_id'] for s in sessions]) == op['session_roster_sha256'], 'Exact report roster binding differs')
        del dataset
        cv = read(pin(op['thermal_cv_pin']))
        selection = read(pin(op['thermal_selection_pin']))
        require(selection.get('dataset_sha256') == op['dataset_pin']['sha256'], 'Selection dataset differs')
        selected, fold_info = selected_cv(cv, selection, [s['session_id'] for s in sessions])
        del cv
        observers = observer_summary(read(pin(op['historical_observer_pin'])))
        require(set(observers) == {s['session_id'] for s in sessions}, 'Historical observer report roster differs')
        timing = timing_summary(read(pin(op['timing_cv_pin'])))
        coverage = read(pin(op['coverage_review_pin']))
        require(coverage.get('artifact_bindings', {}).get('model_inputs_sha256') == op['dataset_pin']['sha256'],
                'Coverage review/model inputs binding differs')
        final_models = read(pin(op['final_models_pin'])) if op.get('final_models_pin') else None
        if final_models is not None:
            require(final_models.get('CV_selection_sha256') == identity(selection['selection']), 'Final model/CV selection binding differs')
            require(final_models.get('fresh_confirmation') is False and final_models.get('physical_goal_pass') is False,
                    'Final model evaluation role differs')
        else:
            require(op.get('final_fit_status') == 'PENDING_FINAL_FIT', 'Explicit pending final model contract required')
        forecast_audit = {}
        if op.get('forecast_pin'):
            if op.get('forecast_format') == 'A24_COUNTERFACTUAL_ROWS_JSONL_V1':
                forecast_rows = saved_forecast_rows(op['forecast_pin'])
                require(op.get('case_status_pin') and op.get('forecast_receipts_pin'), 'All-case roster and START ledger pins required')
                receipts = forecast_receipt_summary(op['forecast_receipts_pin'])
                complete_cases = join_forecast_case_roster(read(pin(op['case_status_pin'])), forecast_rows, receipts)
                forecasts, validations = native_forecast_adapter(complete_cases)
                require(len(complete_cases) == op['expected_total_forecast_cases'], 'Forecast all-planned-case denominator differs')
                require(sum(r['kind']=='PREDECLARED_NOVEL_GRID' for r in complete_cases) == op['expected_novel_rows'], 'Novel grid denominator differs')
                require(len(validations) == op['expected_validation_rows'], 'Heldout schedule validation denominator differs')
                require(sum(r['kind']=='REGISTERED_CUSTOM' for r in complete_cases) == op.get('expected_custom_rows',0), 'Registered custom scenario denominator differs')
                forecast_audit.update(heldout_schedule_validation_rows=validations,
                    all_planned_forecast_cases=len(complete_cases), successful_saved_forecast_rows=len(forecast_rows),
                    novel_grid_rows=sum(r['kind']=='PREDECLARED_NOVEL_GRID' for r in complete_cases),
                    registered_custom_rows=sum(r['kind']=='REGISTERED_CUSTOM' for r in complete_cases),
                    heldout_validation_rows=len(validations),
                    explicitly_failed_rows=sum('FAIL' in str(r.get('status','')).upper() or 'ERROR' in str(r.get('status','')).upper() for r in complete_cases),
                    unknown_AP_mean_rows=sum(r.get('AP_mean_c') is None for r in complete_cases),
                    status_counts=dict(Counter(str(r.get('status')) for r in complete_cases)),
                    AP_status_counts=dict(Counter(str(r.get('AP_status')) for r in complete_cases)),
                    receipt_accounting=receipts)
                del forecast_rows
                for name in ('forecast_result_pin','forecast_complete_pin','effects_harms_pin','heldout_validation_pin'):
                    require(op.get(name), 'Registered completed forecast evidence required: '+name)
                    forecast_audit[name[:-4]] = read(pin(op[name]))
                require(forecast_audit['forecast_result'].get('simulation_START_consumed') == receipts['simulator_STARTs'],
                        'Forecast result/START receipt count differs')
            elif op.get('forecast_format') == 'A24_REPORT_FORECAST_SCENARIOS_V1':
                forecasts = forecast_scenarios(read(pin(op['forecast_pin'])))
            else:
                raise ValueError('Explicit registered forecast artifact format required')
        else:
            require(op.get('forecast_status') == 'PENDING_REGISTERED_FORECAST', 'Explicit pending forecast contract required')
            forecasts = []
        artifact_pins = {k:v for k,v in op.items() if k.endswith('_pin')}
        report = assemble(sessions, selected, fold_info, observers, timing, coverage, forecasts, artifact_pins, final_models, forecast_audit)
        write_new(out/'REPORT_DATA.json', report)
        write_new(out/'REPORT_REQUEST_METRICS.json', [{'session_id':s['session_id'], **s['request_metrics_report']} for s in report['sessions']])
        write_new(out/'REPORT_DATA_RESULT.json', {'status':'SOURCE_BOUND_REPORT_DATA_READY_PENDING_RENDER_AND_UI_QA',
            'sessions':len(report['sessions']), 'scenarios':len(report['scenarios']),
            'report_data_sha256':sha(out/'REPORT_DATA.json'),'report_value_sha256':identity(report),
            'source_dataset_sha256':op['dataset_pin']['sha256'],
            'report_ROSTER_sha256':op['session_roster_sha256'],'new_environment':0,'HTTP':0,'fits':0,
            'measured_J':None,'fresh_confirmation':False,'physical_goal_pass':False,
            'original_results_or_HTML_overwritten':False})
    print(canonical({'status':'COMPLETE','output':str(out)}))


if __name__ == '__main__':
    main()
