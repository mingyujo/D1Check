import copy
import unittest
from unittest.mock import patch

from tools import d1_ap_tail_scope as api


class ScopeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scope, _, _ = api.read_assets()
        cls.cases = api.tail.s.j.m.read(api.ROOT / 'docs/results/ap_tail_observation_run_05/run_v6/inputs.json.gz')
        cls.contexts = api.tail.s.j.m.read(api.ROOT / 'docs/results/ap_tail_scope_01/run_v4/recorded_contexts.json')

    def input(self, n=0):
        c = copy.deepcopy(self.cases[n])
        return c, copy.deepcopy(self.contexts[c['id']])

    def test_explicit_opt_in_and_usage_boundaries(self):
        c, ctx = self.input()
        self.assertIsNone(api.forecast(c, ctx)['prediction_ap_c'])
        for usage in ('strict', 'RL_training', 'online_end_to_end', 'policy_ranking'):
            with self.subTest(usage=usage):
                ctx['requested_usage'] = usage
                r = api.forecast(c, ctx, opt_in=True)
                self.assertEqual(r['status'], 'blocked')
                self.assertIsNone(r['prediction_ap_c'])

    def test_recorded_confirmation_matches_and_no_default_promotion(self):
        for i in range(2):
            c, ctx = self.input(i)
            r = api.forecast(c, ctx, opt_in=True)
            self.assertEqual(r['status'], 'diagnostic_AP_only')
            for key in ('strict_support', 'default_changed', 'rl_changed', 'experiment_ready',
                        'candidate_application_allowed', 'time_identified'):
                self.assertFalse(r[key])
            for key in ('accuracy_pass', 'energy_prediction_j', 'response_prediction_s'):
                self.assertIsNone(r[key])

    def test_initial_AP_boundaries_missing_nonfinite(self):
        c, _ = self.input()
        for ap in (26.5, 28.8):
            c['pre'][-1]['ap'] = ap
            self.assertEqual(api.schedule_reasons(c, self.scope), [])
        for ap in (26.4, 28.9, None, float('nan'), float('inf'), True):
            with self.subTest(ap=ap):
                c['pre'][-1]['ap'] = ap
                self.assertIn('pre_last_AP_outside_candidate_development_context',
                              api.schedule_reasons(c, self.scope))
        c['pre'] = []
        self.assertIn('missing_preload_AP', api.schedule_reasons(c, self.scope))

    def test_context_identity_and_numeric_types(self):
        for key, value in (('device_model', 'S26'), ('apk_sha256', 'wrong'), ('cpu_threads', 4),
                           ('cpu_threads', True), ('device_identity_verified', 1),
                           ('resident_keys', ['classification_CPU']), ('model_contract_sha256', 'wrong')):
            c, ctx = self.input()
            ctx[key] = value
            self.assertIn('context_mismatch:' + key, api.forecast(c, ctx, opt_in=True)['reasons'])
        self.assertEqual(api.forecast(None, {}, opt_in=True)['reasons'], ['malformed_case_or_context'])

    def test_unsupported_task_pair_and_registered_order(self):
        c, _ = self.input(1)
        seg = next(s for s in c['actual'] if s['state'] != 'idle')
        seg['state'] = 'classification_GPU+detection_GPU'
        self.assertIn('unsupported_task_backend_state', api.schedule_reasons(c, self.scope))
        c, _ = self.input(1)
        next(s for s in c['actual'] if s['state'] != 'idle')['state'] = 'classification_GPU'
        self.assertIn('state_entry_exit_or_order_outside_registered_blocks', api.schedule_reasons(c, self.scope))

    def test_preparation_history_cannot_be_silently_changed(self):
        for key, value in (('warmup_count', 16), ('baseline_seconds', 30),
                           ('preparation_fixed_seconds', 0), ('cadence_ms', 50),
                           ('collector_validated_and_cleanup_complete', False)):
            c, ctx = self.input()
            ctx[key] = value
            self.assertIn('context_mismatch:' + key, api.forecast(c, ctx, opt_in=True)['reasons'])

    def test_C0_cannot_hide_work_or_relabel_an_arrival(self):
        c, _ = self.input()
        c['actual'] = [dict(start_s=0., end_s=35., state='idle'),
                       dict(start_s=35., end_s=36., state='classification_CPU'),
                       dict(start_s=36., end_s=2555., state='idle')]
        self.assertIn('C0_has_registered_work', api.schedule_reasons(c, self.scope))
        c, _ = self.input(1)
        c['policy'] = 'B2_PARALLEL_ONLINE_V1'
        self.assertIn('unregistered_profile_or_arrival_schedule', api.schedule_reasons(c, self.scope))

    def test_horizon_gaps_future_preload_and_query(self):
        for mutation, reason in (
            (lambda c: c['actual'][-1].update(end_s=3000.), 'observation_horizon_mismatch'),
            (lambda c: c['actual'][0].update(start_s=1.), 'noncontiguous_or_invalid_lane_schedule'),
            (lambda c: c['pre'][-1].update(hi=35.), 'invalid_or_future_preload_AP'),
            (lambda c: c.update(q=[35., 60.]), 'invalid_or_uncovered_query_times'),
            (lambda c: c.update(q=[3000.]), 'invalid_or_uncovered_query_times')):
            c, _ = self.input()
            mutation(c)
            self.assertIn(reason, api.schedule_reasons(c, self.scope))

    def test_missing_clock_field_is_not_claimed_to_be_a_measured_mismatch(self):
        c, _ = self.input()
        del c['common_end_s']
        reasons = api.schedule_reasons(c, self.scope)
        self.assertIn('common_window_unrecorded_in_case', reasons)
        self.assertNotIn('common_window_mismatch', reasons)

    def test_postload_targets_and_power_cannot_enter_prediction(self):
        c, ctx = self.input(1)
        before = api.forecast(c, ctx, opt_in=True)['prediction_ap_c']
        c.update(ap=None, power_t=[999999.], power_w=[999999.], pre_w=-999999.)
        c['actual'][0]['observed_postload_AP'] = 999999.
        original = api.tail.predict
        with patch.object(api.tail, 'predict', wraps=original) as spy:
            after = api.forecast(c, ctx, opt_in=True)['prediction_ap_c']
            self.assertEqual(set(spy.call_args.args[0]), {'pre', 'q', 'actual'})
            self.assertEqual(set(spy.call_args.args[0]['actual'][0]), {'start_s', 'end_s', 'state'})
        self.assertEqual(before, after)

    def test_original_calculation_error_and_unexpected_exception_preserved(self):
        c, ctx = self.input()
        with patch.object(api.tail, 'predict', side_effect=ValueError('original initialization failure')):
            r = api.forecast(c, ctx, opt_in=True)
            self.assertEqual(r['status'], 'calculation_failed')
            self.assertEqual(r['original_error']['message'], 'original initialization failure')
            self.assertIn('original initialization failure', r['original_error']['stack'])
            self.assertIsNone(r['prediction_ap_c'])
        with patch.object(api.tail, 'predict', side_effect=RuntimeError('unexpected original error')):
            with self.assertRaisesRegex(RuntimeError, 'unexpected original error'):
                api.forecast(c, ctx, opt_in=True)

    def test_frozen_bytes_change_is_rejected(self):
        real = api.sha
        with patch.object(api, 'sha', side_effect=lambda p: real(p) if p == api.SCOPE else 'changed'):
            with self.assertRaisesRegex(ValueError, 'frozen asset changed'):
                api.read_assets()

    def test_prediction_implementation_change_is_rejected(self):
        with patch.object(api, 'source_sha', return_value='changed'):
            with self.assertRaisesRegex(ValueError, 'predictor code changed'):
                api.read_assets()


if __name__ == '__main__':
    unittest.main()
