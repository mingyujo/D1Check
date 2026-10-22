"""Regression checks: no environment run, optimizer step, or scientific fit."""
import os
for key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[key] = '1'
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import numpy as np
from a24_idle_wait_repair_20261019.guard import filter_idle_waits
from a24_idle_wait_repair_20261019.policy import Policy
from a24_idle_wait_repair_20261019 import VERSION, NETWORK_VERSION, load_components
from a24_atc_bc_20261019.test_contracts import job, state, Physics, Nominal


def fixture():
    s = state([job()])
    actions = [dict(kind='DISPATCH', request_id='0', route='CPU'),
               dict(kind='DISPATCH', request_id='0', route='GPU'),
               dict(kind='WAIT', wait_ns=20_000_000), dict(kind='WAIT', wait_ns=50_000_000)]
    def forecast(energy):
        return dict(cost=[energy, .1, 0., 0., 0.], AP_end=27., peak=28.,
            H_s=11., visible_ids=['0'], capped=False, comparison_complete=True,
            no_future_arrivals=True, no_future_latents=True)
    forecasts = [forecast(1.), forecast(1.1), forecast(1.2), forecast(1.3)]
    mask = np.zeros(36, bool)
    mask[:4] = True
    return s, actions, forecasts, mask


class Contracts(unittest.TestCase):
    def test_dominated_idle_waits_removed_and_dispatches_preserved(self):
        s, a, f, m = fixture()
        out, info = filter_idle_waits(s, a, f, m)
        self.assertEqual(out[:4].tolist(), [True, True, False, False])
        self.assertEqual([x['witness_index'] for x in info['removed']], [0, 0])
        self.assertTrue(info['applied'])

    def test_each_objective_tradeoff_preserves_wait(self):
        for key in range(7):
            with self.subTest(metric=key):
                s, a, f, m = fixture()
                if key < 5:
                    for d in f[:2]:d['cost'][key] = 2.
                    f[2]['cost'][key] = .5
                else:
                    f[2][('AP_end', 'peak')[key-5]] = 20.
                out, _ = filter_idle_waits(s, a, f, m)
                self.assertTrue(out[2])

    def test_exact_ties_are_not_assumed_to_favor_dispatch(self):
        s, a, f, m = fixture()
        f = [copy.deepcopy(f[0]) for _ in f]
        out, info = filter_idle_waits(s, a, f, m)
        self.assertTrue(np.array_equal(out, m))
        self.assertFalse(info['applied'])

    def test_tolerance_does_not_turn_roundoff_into_dominance(self):
        s, a, f, m = fixture()
        f[2] = copy.deepcopy(f[0]);f[2]['cost'][0] += 1e-11
        out, _ = filter_idle_waits(s, a, f, m)
        self.assertTrue(out[2])

    def test_waits_with_active_owners_preserved(self):
        s, a, f, m = fixture();s['owners'] = [dict(request_id='owner')]
        out, info = filter_idle_waits(s, a, f, m)
        self.assertTrue(np.array_equal(out, m));self.assertFalse(info['applied'])

    def test_unavailable_dispatch_is_not_a_witness(self):
        s, a, f, m = fixture();m[:2] = False
        out, _ = filter_idle_waits(s, a, f, m)
        self.assertTrue(np.array_equal(out, m))

    def test_nonqueued_or_unknown_route_dispatch_not_a_witness(self):
        s, a, f, m = fixture();a[0]['request_id'] = 'future';a[1]['route'] = 'NPU'
        out, _ = filter_idle_waits(s, a, f, m)
        self.assertTrue(np.array_equal(out, m))

    def test_incomplete_noncausal_or_nonfinite_forecast_keeps_wait(self):
        variants = [('capped', True), ('comparison_complete', False),
                    ('no_future_arrivals', False), ('no_future_latents', False),
                    ('H_s', float('nan')), ('cost', [float('inf')]*5)]
        for key, value in variants:
            with self.subTest(key=key):
                s, a, f, m = fixture();f[2][key] = value
                out, _ = filter_idle_waits(s, a, f, m)
                self.assertTrue(out[2])

    def test_different_horizons_or_job_sets_keep_wait(self):
        for value in (12., ['0', 'other']):
            s, a, f, m = fixture()
            f[2]['H_s' if isinstance(value, float) else 'visible_ids'] = value
            out, _ = filter_idle_waits(s, a, f, m)
            self.assertTrue(out[2])

    def test_no_pending_jobs_is_noop(self):
        s, a, f, m = fixture();s['queue'] = []
        out, _ = filter_idle_waits(s, a, f, m)
        self.assertTrue(np.array_equal(out, m))

    def test_input_order_does_not_change_eligibility(self):
        s, a, f, m = fixture()
        out, _ = filter_idle_waits(s, a, f, m)
        ids = [3, 1, 2, 0]
        reversed_mask = m.copy();reversed_mask[:4] = m[ids]
        reordered, _ = filter_idle_waits(s, [a[i] for i in ids], [f[i] for i in ids], reversed_mask)
        self.assertEqual(reordered[:4].tolist(), out[ids].tolist())

    def test_inputs_are_immutable_and_repeated_calls_idempotent(self):
        s, a, f, m = fixture();before = copy.deepcopy((s, a, f));before_mask = m.copy()
        out, _ = filter_idle_waits(s, a, f, m)
        again, info = filter_idle_waits(s, a, f, out)
        self.assertEqual((s, a, f), before);self.assertTrue(np.array_equal(m, before_mask))
        self.assertTrue(np.array_equal(out, again));self.assertFalse(info['applied'])

    def test_invalid_masks_fail_explicitly(self):
        s, a, f, m = fixture()
        with self.assertRaises(ValueError):filter_idle_waits(s, a, f[:-1], m)
        m[5] = True
        with self.assertRaises(ValueError):filter_idle_waits(s, a, f, m)
        with self.assertRaises(ValueError):filter_idle_waits(s, a, f, np.zeros(36, bool))

    def test_event_wait_is_never_pruned_by_this_rule(self):
        s, a, f, m = fixture();a[2] = dict(kind='WAIT_EVENT', max_wait_ns=500_000_000)
        out, _ = filter_idle_waits(s, a, f, m)
        self.assertTrue(out[2])

    def test_mask_is_applied_before_learner_and_return_has_no_override(self):
        s, actions, forecasts, mask = fixture()
        bank = dict(x=np.zeros((36, 50), np.float32), mask=mask,
                    scores=np.array([1., 1.1, 1.2, 1.3]+[0.]*32),
                    forecasts=forecasts, version=NETWORK_VERSION)
        class ChooseLast:
            def choose(self, b, collect):
                self.mask = b['mask'].copy()
                return int(np.flatnonzero(b['mask'])[-1]), {}
        learner = ChooseLast()
        p = Policy(None, None, {}, 'BC', learner, False)
        p.encode = lambda s:(Policy.guard_bank(s, bank, actions), actions)
        self.assertEqual(p(s), actions[1])
        self.assertFalse(learner.mask[2:].any())
        self.assertEqual(p.calls[-1]['chosen'], 1)
        self.assertFalse(p.calls[-1]['post_NN_override'])
        self.assertTrue(p.calls[-1]['pre_NN_forecast_filter'])
        self.assertEqual(p.calls[-1]['version'], VERSION)

    def test_production_encoder_retains_feature_abi_and_causal_state(self):
        s = state([job(), job(1)]);before = copy.deepcopy(s)
        p = load_components().Policy(Nominal(), Physics(),
            dict(n=2, service_stop_s=12, supply_stop_s=10), 'TEACHER')
        b, actions = p.encode(s)
        self.assertEqual(b['x'].shape, (36, 50));self.assertEqual(s, before)
        self.assertEqual(b['version'], NETWORK_VERSION);self.assertEqual(b['policy_version'], VERSION)
        self.assertTrue(np.all(b['mask'] <= b['physical_mask']))
        action = p(s)
        self.assertEqual(action, p.calls[-1]['action'])
        self.assertTrue(p.frames[-1]['teacher_mask'][p.frames[-1]['index']])
        self.assertFalse(np.any(p.frames[-1]['teacher_mask'] & ~p.frames[-1]['mask']))


if __name__ == '__main__':
    unittest.main(verbosity=2)
