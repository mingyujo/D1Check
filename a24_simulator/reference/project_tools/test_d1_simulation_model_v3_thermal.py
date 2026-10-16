import copy
import unittest

import numpy as np

from tools import d1_simulation_model_v2 as v2
from tools import d1_simulation_model_v3_thermal as thermal


class ThermalV3Tests(unittest.TestCase):
    def original(self):
        slopes = {s: .2+.05*(i+1) for i, s in enumerate(v2.STATES)}
        slopes['resident_idle'] = .2
        return dict(ap=dict(beta=.05, k=1.1, g=0., parameters=dict(
            ap_cooling_rate_per_s=.05, ap_slope_at_30_c_per_s=slopes)),
            energy_increment_w=dict(zip(v2.STATES, [.6, .7, .4, 1.])))

    def case(self, identity='development_0'):
        pre = [dict(t=float(t), lo=t-.01, hi=t+.01, ap=29.+.003*t) for t in range(-25, 35, 3)]
        segments = [dict(start_s=0., end_s=35., state='idle')]
        for i, state in enumerate(v2.STATES):
            segments.append(dict(start_s=35.+15*i, end_s=50.+15*i, state=state))
        segments.append(dict(start_s=95., end_s=180., state='idle'))
        return dict(id=identity, role='development', pre=pre,
                    q=list(np.arange(35., 180.1, 3.)), actual=segments)

    def test_original_mapping_is_exact_and_alpha_one_preserves_v2(self):
        c, original = self.case(), self.original()
        theta = thermal.prior_coefficients(original)
        head = dict(coefficients=theta.tolist(), alpha=1.)
        predicted, _ = thermal.predict(c, head, original)
        old, _ = v2.prior.thermal.predict(v2.prior.case_input(c, c['actual']), original['ap'])
        np.testing.assert_allclose(predicted, old, rtol=1e-12, atol=1e-11)
        model = dict(ap=dict(beta=.05, slow_tau_s=1920., slow_input_w=original['energy_increment_w'], coefficients=[.1]*5))
        current, _ = v2.ap_prediction(c, model)
        same, _ = thermal.predict(c, dict(coefficients=[.1]*5, alpha=1.), original)
        np.testing.assert_allclose(same, current, atol=1e-11)

    def test_zero_h_refits_reference_and_keeps_last_observed_anchor(self):
        c, original = self.case(), self.original()
        c['actual'] = [dict(start_s=0., end_s=180., state='idle')]
        for p in c['pre']:
            p['ap'] = 29.
        predicted, initial = thermal.predict(c, dict(coefficients=[0.]*5, alpha=0.), original)
        self.assertEqual(initial['h_last'], 0.)
        self.assertTrue(initial['initial_h_constrained_zero'])
        self.assertEqual(initial['anchor_s'], c['pre'][-1]['t'])
        np.testing.assert_allclose(predicted, [29.]*len(c['q']), atol=1e-11)

    def test_half_alpha_penalty_is_normalized_and_reduces_h(self):
        c, original = self.case(), self.original()
        _, _, free = thermal.design(c, original, 1.)
        _, _, regularized = thermal.design(c, original, .5)
        self.assertEqual(regularized['initial_h_penalty'], 1.)
        self.assertLess(abs(regularized['h_last']), abs(free['h_last']))

    def test_future_targets_are_absent_and_mutated_pre_cannot_reuse_cache(self):
        c, original = self.case(), self.original()
        head = dict(coefficients=[.1]*5, alpha=.5)
        before = thermal.predict(c, head, original)
        c['ap'] = [999.]*len(c['q'])
        c['power_w'] = [999.]
        c['power_t'] = [100.]
        self.assertEqual(before, thermal.predict(c, head, original))
        c['pre'][-1]['ap'] += .1
        self.assertNotEqual(before[0], thermal.predict(c, head, original)[0])
        a, x, _ = thermal.design(c, original, .5)
        a[:] = 999.
        x[:] = 999.
        self.assertNotEqual(thermal.design(c, original, .5)[0][0], 999.)

    def test_known_history_affine_basis_and_reported_initial_state(self):
        c, original = self.case(), self.original()
        c['history'] = [dict(start_s=-100., end_s=-26., state='classification_CPU'),
                        dict(start_s=-26., end_s=0., state='idle')]
        theta = np.array([.08, .09, .12, .16, .002])
        for alpha in thermal.ALPHAS:
            predicted, initial = thermal.predict(c, dict(coefficients=theta.tolist(), alpha=alpha), original)
            direct, applied = thermal._prediction(c, thermal._original_input(original), theta, alpha)
            np.testing.assert_allclose(predicted, direct, atol=1e-11)
            self.assertEqual(initial, applied)
            self.assertEqual(initial['history_intervals'], 2)

    def test_missing_future_schedule_and_future_pre_are_rejected(self):
        original = self.original()
        c = self.case()
        c['actual'][-1]['end_s'] = 150.
        with self.assertRaises(ValueError):
            thermal.design(c, original, 1.)
        c = self.case()
        c['pre'][-1]['hi'] = 35.
        with self.assertRaises(ValueError):
            thermal.design(c, original, 0.)

    def test_development_only_unique_full_rank_fit_and_prior_ridge(self):
        original = self.original()
        cases = [self.case('development_'+str(i)) for i in range(3)]
        theta = thermal.prior_coefficients(original)
        for c in cases:
            c['ap'] = thermal.predict(c, dict(coefficients=theta.tolist(), alpha=1.), original)[0]
        fitted = thermal.fit(cases, original, 10., 1.)
        np.testing.assert_allclose(fitted['coefficients'], theta, atol=1e-11)
        self.assertEqual(fitted['numerical_rank'], 5)
        self.assertFalse(fitted['experiment_ready'])
        bad = copy.deepcopy(cases)
        bad[0]['role'] = 'confirmation'
        with self.assertRaises(ValueError):
            thermal.fit(bad, original, 1., 1.)
        bad = copy.deepcopy(cases)
        bad[1]['id'] = bad[0]['id']
        with self.assertRaises(ValueError):
            thermal.fit(bad, original, 1., 1.)

    def test_source_weighting_is_unchanged_by_duplicate_equivalent_session(self):
        original = self.original()
        cases = [self.case(i) for i in ('development_0', 'session_00', 'development_0_MODEL2_RECOVERY_A')]
        theta = thermal.prior_coefficients(original)
        for i, c in enumerate(cases):
            c['ap'] = (np.array(thermal.predict(c, dict(coefficients=theta.tolist(), alpha=1.), original)[0])+.1*i).tolist()
        before = thermal.fit(cases, original, .1, 1.)
        copied = copy.deepcopy(cases[-1])
        copied['id'] = 'development_1_MODEL2_RECOVERY_A'
        after = thermal.fit(cases+[copied], original, .1, 1.)
        np.testing.assert_allclose(before['coefficients'], after['coefficients'], atol=1e-11)
        self.assertEqual(after['source_groups']['new_recovery'], 2)


if __name__ == '__main__':
    unittest.main()
