"""Source-only synthetic checks; no actual simulator/fit/archive/network calls.

No test calls simulate_protocol. Cache equivalence checks the exact pool,
nominal, whole-vector CRN draw and progress-rate functions against unmodified
instances. Journal STARTs are sealed dummy callbacks in temporary directories.
Do not execute until the root registers these exact sources and test operation.
"""
from __future__ import annotations

import copy
import gzip
import json
from pathlib import Path
import tempfile
import unittest

import forecast_run as forecast
from timing_model import build_timing_candidate, context_of, reserve_dispatch, UnsupportedContext


def source(sid='source', bank='M128', protocol='SERIAL'):
    model = '3' * 64
    registry = {k: {'model': {'sha256': model}} for k in ('C_CPU', 'C_GPU', 'D_CPU')}
    width = 200 if protocol == 'CG_DC' else 100
    requests = []
    for ordinal, task, route in ((0, 'C', 'GPU'), (1, 'D', 'CPU')):
        dispatch = 0 if ordinal == 0 or protocol == 'CG_DC' else width * 5
        row = {'request_id': 'ORIGINAL_' + task, 'ordinal': ordinal, 'task': task,
               'priority': 'U' if task == 'C' else 'N', 'group': 0, 'route': route,
               'scheduled_arrival_ns': 0, 'actual_arrival_ns': 0, 'queue_entry_ns': 0,
               'dispatch_ns': dispatch, 'deadline_ns': 10000, 'available_ns': dispatch + width * 5,
               'input_sha256': '1' * 64, 'tensor_sha256': '2' * 64, 'model_sha256': model,
               'phases_ns': [width] * 5, 'complete_vector': True}
        for i, key in enumerate(('execution_start', 'output_ready', 'persist_complete', 'worker_release', 'lane_available'), 1):
            row[key + '_ns'] = dispatch + i * width
        requests.append(row)
    return {'session_id': sid, 'cohort_id': sid, 'source_family': 'm8', 'source_generation': 'SEALED_SYNTHETIC',
            'device': 'A24', 'bank': bank, 'protocol': protocol,
            'arm': 'FIFO_PAIR_CG' if protocol == 'CG_DC' else 'FIFO_SERIAL_CG',
            'public_route': 'GPU', 'public_order': 'FIFO',
            'compatibility': {'public_models': registry, 'public_apk_sha256': '4' * 64,
                              'ap_activity_domain': 'SEALED_DOMAIN', 'ap_sensor_contract_qualified': True,
                              'quality_binding_verified': False},
            'requests': requests, 'request_event_coverage': 'COMPLETE',
            'service_stop_ns': 10000, 'drain_stop_ns': 20000, 'observation_end_ns': 20000,
            'initial_ap_c': 35., 'initial_ap_time_s': -1., 'initial_ap_hi_s': -1.,
            'observations': [{'channel': 'AP', 't_s': -1., 'lo_s': -1.1, 'hi_s': -1.,
                              'ap_c': 35., 'initial_eligible': True},
                             {'channel': 'AP', 't_s': 5., 'lo_s': 4.9, 'hi_s': 5.1,
                              'ap_c': 99., 'initial_eligible': False}],
            'owner_intervals': [{'start_s': 100., 'end_s': 999., 'task': 'C', 'route': 'GPU'}]}


def budget():
    return {'global_cap': 137712, 'global_registered_total': 119750,
            'additional_global_reservation': 0, 'operation_simulation_cap': 256,
            'shared_forecast_cap': 256, 'reservation_id': 'SEALED_TEST', 'a24_pool_cap': 2048,
            'a24_remaining_before_allocation': 353, 'allocated_from_existing_a24': 256,
            'reserved_global_excluding_this': 92997, 'reserved_a24_excluding_this': 97}


def budget_call(config=None, **overrides):
    values = dict(canonical_global=26454, canonical_a24=1695, extra_global=43,
                  prior_forecast_global=0, prior_a24=0, prior_shared=0, current_used=0)
    values.update(overrides)
    return forecast.budget_arithmetic(config or budget(), **values)


def case(label='C0'):
    public = forecast.transform_public_template(forecast.public_template(source()))
    return {'label': label, 'bank': 'M128', 'policy': 'FIFO_SERIAL_CG', 'seed': 0,
            'template': public, 'kind': 'PREDECLARED_NOVEL_GRID'}


class DummyGuard:
    def before_start(self, fingerprint):
        return {'sealed_synthetic_only': True, 'logical_case_sha256': fingerprint}


class ForecastSourceTests(unittest.TestCase):
    def test_public_template_masks_all_observed_future_times_and_AP(self):
        original = source()
        original['compatibility']['future_actual_overlap'] = 'FORBIDDEN'
        public = forecast.public_template(original)
        self.assertNotIn('owner_intervals', public)
        self.assertNotIn('future_actual_overlap', public['compatibility'])
        self.assertEqual(len(public['observations']), 1)
        self.assertEqual(public['observations'][0]['ap_c'], 35.)
        for q in public['requests']:
            for key in ('actual_arrival_ns', 'queue_entry_ns', 'dispatch_ns', 'available_ns', 'response_ns', 'phases_ns', 'route'):
                self.assertNotIn(key, q)
        self.assertEqual(original['observations'][1]['ap_c'], 99.)

    def test_interventions_preserve_anchor_and_define_relative_deadlines(self):
        base = forecast.public_template(source())
        base['requests'][0].update(scheduled_arrival_ns=35_000_000_000, deadline_ns=36_000_000_000)
        base['requests'][1].update(scheduled_arrival_ns=38_000_000_000, deadline_ns=40_000_000_000)
        dense = forecast.transform_public_template(base, 'dense0.65', 'relative0.65')
        self.assertEqual(dense['requests'][0]['scheduled_arrival_ns'], 35_000_000_000)
        self.assertEqual(dense['requests'][1]['scheduled_arrival_ns'], 36_950_000_000)
        self.assertEqual(dense['requests'][1]['deadline_ns'], 38_250_000_000)
        burst = forecast.transform_public_template(base, 'burstbucket2s')
        self.assertEqual(burst['requests'][1]['scheduled_arrival_ns'], 37_000_000_000)
        self.assertEqual(burst['requests'][1]['deadline_ns'], 39_000_000_000)

    def test_default_grid180_and_paired_potential_policy_independent(self):
        sessions = [source('c', 'C252'), source('l', 'L64'), source('m', 'M128')]
        op = {'templates': [{'session_id': s['session_id'], 'bank': s['bank']} for s in sessions],
              'dataset_pin': {'sha256': '5' * 64}, 'budget': budget()}
        cases = forecast.build_cases(sessions, op)
        self.assertEqual(len(cases), 180)
        first = [c for c in cases if c['bank'] == 'M128' and c['seed'] == 0]
        self.assertEqual(len({forecast.digest(c['scenario_key']) for c in first}), 1)
        self.assertEqual({q['request_id'] for q in first[0]['template']['requests']}, {'cf-c-00000', 'cf-d-00001'})

    def test_custom_public_requests_reject_hidden_fields_and_stabilize_ids(self):
        base = forecast.public_template(source())
        custom = {'label': 'CUSTOM', 'requests': [{'request_id': 'USER_LABEL', 'ordinal': 7, 'task': 'C',
                  'priority': 'N', 'group': 1, 'scheduled_arrival_s': 1., 'deadline_s': 2.,
                  'input_sha256': '1' * 64, 'tensor_sha256': '2' * 64}]}
        result = forecast.custom_public_template(base, custom)
        self.assertEqual(result['requests'][0]['request_id'], 'cf-c-00007')
        self.assertEqual(result['request_id_mapping'][0]['source_public_request_id'], 'USER_LABEL')
        custom['requests'][0]['actual_arrival_s'] = 1.5
        with self.assertRaises(RuntimeError):
            forecast.custom_public_template(base, custom)

    def test_budget_counts_START_not_success_and_preserves_reservation(self):
        first = budget_call()
        self.assertEqual(first['global_START_after'], 26498)
        self.assertEqual(first['global_actual_plus_reserved'], 119750)
        self.assertTrue(first['FAIL_is_consumed'])
        last = budget_call(current_used=255)
        self.assertEqual(last['shared_forecast_START_after'], 256)
        with self.assertRaises(RuntimeError):
            budget_call(current_used=256)
        wrong = budget()
        wrong['reserved_global_excluding_this'] += 1
        with self.assertRaises(RuntimeError):
            budget_call(wrong)

    def test_immutable_ledger_FAIL_is_not_refunded_and_drift_detected(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'receipts.jsonl'
            forecast.append(path, {'event': 'START', 'identity': 'FAILED'})
            forecast.append(path, {'event': 'FAIL', 'identity': 'FAILED'})
            snapshot = forecast.LedgerSnapshot({'path': str(path), 'sha256': forecast.sha(path), 'START': 1, 'FAIL': 1})
            self.assertEqual(snapshot.counts['START'], 1)
            snapshot.check()
            forecast.append(path, {'event': 'START', 'identity': 'NEW'})
            with self.assertRaises(RuntimeError):
                snapshot.check()

    def test_declared_missing_ledger_must_stay_missing(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'missing.jsonl'
            snapshot = forecast.LedgerSnapshot({'path': str(path), 'missing': True, 'START': 0})
            path.write_text('', encoding='utf-8')
            with self.assertRaises(RuntimeError):
                snapshot.check()

    def test_journal_durable_order_and_exact_hash_chain(self):
        with tempfile.TemporaryDirectory() as temporary:
            op = {'forecast_identity_prefix': 'A24CF_TEST_SOURCE', 'budget': {'reservation_id': 'SEALED_TEST'}}
            journal = forecast.ForecastJournal(op, temporary, '6' * 64, DummyGuard())
            row = journal.run(case(), {'model': 'SEALED'}, lambda guard: ({'sealed': True}, {'status': 'SEALED_SYNTHETIC_ONLY', 'metrics': {}}))
            receipts = forecast._ledger_rows(journal.receipts)
            self.assertEqual([r['event'] for r in receipts], ['START', 'PREPARED', 'COMPLETE'])
            self.assertEqual(forecast.sha(row['raw_path']), row['raw_sha256'])
            self.assertEqual(forecast.sha(row['prepared_path']), row['prepared_sha256'])
            terminal = forecast.read(receipts[-1]['terminal_path'])
            self.assertEqual(terminal['row_sha256'], forecast.digest(row))
            raw = json.loads(gzip.decompress(Path(row['raw_path']).read_bytes()).decode('utf-8'))
            self.assertTrue(raw['sealed'])
            with self.assertRaises(RuntimeError):
                journal.run(case(), {'model': 'SEALED'}, lambda guard: ({}, {'status': 'SHOULD_NOT_RUN'}))

    def test_journal_failed_START_consumed_without_retry(self):
        with tempfile.TemporaryDirectory() as temporary:
            journal = forecast.ForecastJournal({'forecast_identity_prefix': 'A24CF_TEST_FAILURE', 'budget': {'reservation_id': 'SEALED_TEST'}},
                                                temporary, '7' * 64, DummyGuard())
            def fail(guard):
                raise UnsupportedContext('SEALED_UNSUPPORTED')
            with self.assertRaises(UnsupportedContext):
                journal.run(case(), {}, fail)
            rows = forecast._ledger_rows(journal.receipts)
            self.assertEqual([r['event'] for r in rows], ['START', 'FAIL'])
            self.assertEqual(rows[0]['new_simulator_environments_consumed'], 1)
            self.assertTrue(journal.rows.is_file())
            self.assertEqual(journal.rows.stat().st_size, 0)
            self.assertEqual(forecast.sha(journal.rows), 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855')
            with self.assertRaises(RuntimeError):
                journal.run(case(), {}, fail)

    def test_full_denominator_P95_and_tardiness_lower_bounds(self):
        rows = [{'request_id': 'a', 'task': 'C', 'priority': 'U', 'scheduled_arrival_ns': 0,
                 'deadline_ns': 2_000_000_000, 'response_ns': 1_000_000_000},
                {'request_id': 'b', 'task': 'D', 'priority': 'N', 'scheduled_arrival_ns': 0,
                 'deadline_ns': 3_000_000_000, 'response_ns': None}]
        result = forecast.deadline_summary(rows, service_stop_ns=4_000_000_000, drain_stop_ns=5_000_000_000)
        self.assertIsNone(result['P95_all_requested_response_s'])
        self.assertEqual(result['P95_all_requested_response_lower_bound_s'], 5.)
        self.assertEqual(result['P95_completed_response_s'], 1.)
        self.assertEqual(result['total_tardiness_lower_bound_s'], 2.)
        self.assertFalse(result['service_threshold_flags']['70'])
        self.assertIsNone(result['by_cohort']['CN']['service_threshold_flags']['70'])

    def test_generated_activity_uses_forecast_owners_and_marks_censor(self):
        public = forecast.public_template(source())
        prediction = {'requests': [{'request_id': 'cf-c-00000', 'task': 'C', 'route': 'GPU',
                                  'dispatch_ns': 100, 'available_ns': None}]}
        generated = forecast.generated_activity(public, prediction)
        owner = generated['owner_intervals'][0]
        self.assertEqual(owner['end_s'], public['observation_end_ns'] / 1e9)
        self.assertTrue(owner['end_is_censored_forecast_window'])
        self.assertNotEqual(owner['start_s'], 100.)

    def test_exact_policy_does_not_guess_from_actual_routes(self):
        measured = source()
        self.assertEqual(forecast.exact_measured_policy(measured, {})[0], 'FIFO_SERIAL_CG')
        measured['arm'] = 'UNKNOWN_ARM'
        self.assertIsNone(forecast.exact_measured_policy(measured, {})[0])
        measured['arm'] = 'FIFO_PAIR_CG'
        self.assertIsNone(forecast.exact_measured_policy(measured, {})[0])

    def test_registered_fold_rejects_same_cohort_leakage(self):
        a, b = source('a'), source('b')
        b['cohort_id'] = a['cohort_id']
        cv = {'folds': {'folds': [{'fold_id': 0, 'heldout_session_ids': ['a'], 'training_session_ids': ['b']}]}}
        with self.assertRaises(RuntimeError):
            forecast.selected_cv_context(cv, [a, b])

    def test_lookup_cache_exact_pool_nominal_progress_and_CRN_equivalence(self):
        sources = [source('s0'), source('s1'), source('p0', protocol='CG_DC'), source('p1', protocol='CG_DC')]
        plain, cached = build_timing_candidate(sources), build_timing_candidate(sources)
        forecast.install_lookup_cache(cached, 'SEALED_CACHE_EQUIVALENCE')
        context, _ = context_of(sources[0], sources[0]['requests'][0])
        a = plain._pool(plain.samples, context, 'C', 'GPU', 'SERIAL', state={})
        b = cached._pool(cached.samples, context, 'C', 'GPU', 'SERIAL', state={})
        c = cached._pool(cached.samples, context, 'C', 'GPU', 'SERIAL', state={})
        self.assertEqual([x['sample_id'] for x in a], [x['sample_id'] for x in b])
        self.assertIsNot(b, c)
        self.assertTrue(all(x is y for x, y in zip(b, c)))
        self.assertEqual(plain.nominal(context, 'C', 'GPU'), cached.nominal(context, 'C', 'GPU', state={'future_actual_overlap': True}))
        self.assertEqual(plain.nominal(context, 'C', 'GPU'), cached.nominal(context, 'C', 'GPU'))
        public = {'now_ns': 0, 'queue': [{'request_id': 'q', 'task': 'C', 'route': 'GPU', 'queue_entry_ns': 0}], 'owners': []}
        action = {'request_id': 'q', 'task': 'C', 'route': 'GPU', 'context': context}
        lock = reserve_dispatch([action], public, 'SERIAL')
        self.assertEqual(plain.draw(action, public, 'SERIAL', lock, ['CRN']), cached.draw(action, public, 'SERIAL', lock, ['CRN']))
        self.assertEqual(plain.progress_rates(action, public), cached.progress_rates(action, public))
        report = forecast.lookup_cache_report(cached)
        self.assertTrue(report['support_bytes_canonical_digest_unchanged'])
        self.assertGreater(report['pool_hits'], 0)
        self.assertGreater(report['nominal_hits'], 0)

    def test_lookup_unknown_preserves_exception_and_support_hash(self):
        model = build_timing_candidate([source()])
        forecast.install_lookup_cache(model, 'UNKNOWN')
        context, _ = context_of(source(), source()['requests'][0])
        messages = []
        for _ in range(2):
            with self.assertRaises(UnsupportedContext) as error:
                model._pool(model.samples, context, 'C', 'CPU', 'CG_DC')
            messages.append(str(error.exception))
        self.assertEqual(messages[0], messages[1])
        self.assertEqual(forecast.lookup_cache_report(model)['pool_hits'], 1)

    def test_unknown_case_status_preserves_public_planned_count(self):
        status = forecast.case_status(case())
        self.assertEqual(status['planned'], 2)
        self.assertIsNone(status['row_identity'])
        self.assertEqual(status['simulation_START_consumed'], 0)
        self.assertEqual(status['source_session_id'], 'source')

    def test_future_initial_AP_is_unknown_not_a_timing_feature(self):
        original = source()
        original.update(initial_ap_time_s=1., initial_ap_hi_s=1.1, initial_ap_c=99.)
        public = forecast.public_template(original)
        self.assertIsNone(public['initial_ap_c'])
        self.assertIn('UNKNOWN', public['initial_context_status'])

    def test_partial_work_energy_decrease_has_no_efficiency_PASS(self):
        common = {'bank': 'M128', 'seed': 0, 'kind': 'PREDECLARED_NOVEL_GRID',
                  'comparison_group_id': 'EXACT_SAME_INPUT_INITIAL', 'intervention': {}}
        baseline = {**common, 'identity': 'BASE', 'policy': 'FIFO_SERIAL_CG', 'metrics': {'on_time': 2},
                    'historical_conditional_J': 100., 'AP_peak_c': 40., 'AP_endpoint_c': 38.,
                    'work_scope': {'planned': 2, 'responded_by_drain': 2, 'AVAILABLE_by_energy_end': 2, 'unfinished_by_drain': 0}}
        partial = {**common, 'identity': 'PARTIAL', 'policy': 'ATC', 'metrics': {'on_time': 1},
                   'historical_conditional_J': 50., 'AP_peak_c': 39., 'AP_endpoint_c': 37.,
                   'work_scope': {'planned': 2, 'responded_by_drain': 1, 'AVAILABLE_by_energy_end': 1, 'unfinished_by_drain': 1}}
        effect = next(r for r in forecast.effect_rows([baseline, partial]) if r['policy'] == 'ATC')
        self.assertEqual(effect['conditional_J_change'], -50.)
        self.assertTrue(effect['deadline_harm'])
        self.assertFalse(effect['work_equivalence']['both_complete_by_drain'])
        self.assertFalse(effect['conditional_energy_decrease_is_efficiency_or_goal_PASS'])

    def test_heldout_trace_scores_after_ID_mapping_and_task_boundaries(self):
        original = source()
        public = forecast.public_template(original)
        predicted = []
        for q, p in zip(original['requests'], public['requests']):
            row = copy.deepcopy(q)
            row['request_id'] = p['request_id']
            row['response_ns'] = q['output_ready_ns'] if q['task'] == 'C' else q['persist_complete_ns']
            predicted.append(row)
        score = forecast.score_validation_trace({'requests': predicted, 'metrics': {'overlap_ns': 0}}, original, public)
        self.assertEqual(score['response_latency_error_s_mae'], 0.)
        self.assertEqual(score['queue_error_s_mae'], 0.)
        self.assertEqual(score['AVAILABLE_error_s_mae'], 0.)
        self.assertEqual(score['actual']['planned'], 2)

    def test_queue_conditioned_cache_keeps_public_state_in_key(self):
        model = build_timing_candidate([source()], feature_mode='queue_ap')
        forecast.install_lookup_cache(model, 'QUEUE_AP')
        context, _ = context_of(source(), source()['requests'][0])
        model.nominal(context, 'C', 'GPU', state={'queue_count': 2, 'initial_ap_c': 35.})
        with self.assertRaises(UnsupportedContext):
            model.nominal(context, 'C', 'GPU', state={'queue_count': 0, 'initial_ap_c': 35.})
        self.assertEqual(forecast.lookup_cache_report(model)['nominal_hits'], 0)

    def test_actual_untracked_missing_has_no_qualified_lower_bound(self):
        missing = [{'request_id': 'missing', 'task': 'D', 'priority': 'N',
                    'scheduled_arrival_ns': 1_000_000_000, 'deadline_ns': 3_000_000_000,
                    'response_ns': None}]
        summary = forecast.actual_deadline_summary(missing,
                  {'actual_recorded_window_s': [0., 5.]}, service_stop_ns=4_000_000_000)
        self.assertEqual(summary['planned'], 1)
        self.assertEqual(summary['uncompleted'], 1)
        self.assertIsNone(summary['P95_all_requested_response_lower_bound_s'])
        self.assertIsNone(summary['total_tardiness_lower_bound_s'])
        self.assertIsNone(summary['uncompleted_lower_bounds'][0]['tardiness_lower_bound_s'])
        self.assertEqual(summary['uncompleted_lower_bounds'][0]['recorded_end_assumption_only_tardiness_bound_s'], 2.)

    def test_actual_tracked_missing_uses_actual_earlier_endpoint(self):
        missing = [{'request_id': 'missing', 'task': 'D', 'priority': 'N',
                    'scheduled_arrival_ns': 1_000_000_000, 'deadline_ns': 3_000_000_000,
                    'response_ns': None}]
        summary = forecast.actual_deadline_summary(missing,
                  {'actual_recorded_window_s': [0., 5.], 'continuous_response_tracking_verified': True},
                  service_stop_ns=10_000_000_000)
        self.assertEqual(summary['P95_all_requested_response_lower_bound_s'], 4.)
        self.assertEqual(summary['total_tardiness_lower_bound_s'], 2.)
        self.assertEqual(summary['actual_recorded_observation_end_s'], 5.)

    def test_validation_untracked_bound_errors_null_but_sim_bounds_remain(self):
        original = source()
        original['actual_recorded_window_s'] = [0., .00001]
        original['requests'][1]['response_s'] = None
        public = forecast.public_template(original)
        predicted = []
        for q, p in zip(original['requests'], public['requests']):
            item = copy.deepcopy(q)
            item['request_id'] = p['request_id']
            item['response_ns'] = None if q['task'] == 'D' else q['output_ready_ns']
            predicted.append(item)
        score = forecast.score_validation_trace({'requests': predicted, 'metrics': {'overlap_ns': 0}}, original, public)
        self.assertEqual(score['actual']['planned'], 2)
        self.assertEqual(score['actual']['uncompleted'], 1)
        self.assertIsNone(score['actual']['total_tardiness_lower_bound_s'])
        self.assertIsNone(score['total_tardiness_lower_bound_s_error'])
        self.assertIsNone(score['P95_all_requested_response_lower_bound_s_error'])
        self.assertIsNotNone(score['predicted']['total_tardiness_lower_bound_s'])
        self.assertIsNone(score['on_time_count_error'])
        original['continuous_response_tracking_verified'] = True
        tracked = forecast.score_validation_trace({'requests': predicted, 'metrics': {'overlap_ns': 0}}, original, public)
        self.assertEqual(tracked['actual']['actual_recorded_observation_end_s'], .00001)
        self.assertEqual(tracked['total_tardiness_lower_bound_s_error'], 0.)


if __name__ == '__main__':
    unittest.main()
