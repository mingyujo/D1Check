"""Analytic contracts: conservation, history, sharing, idle and candidate costs."""
from pathlib import Path
import json
import math
import unittest
from shared_cost import SharedActivationCost, KNOWN_PAIR, segments

ROOT = Path(__file__).resolve().parents[2]
MODEL = json.loads((ROOT/'results/STATE_COST_IDENTIFICATION_20261017_01/MODEL.json').read_text())


def owner(a, b, task='C', route='GPU'):
    return dict(start_s=a, end_s=b, task=task, route=route)


class Contracts(unittest.TestCase):
    def engine(self, scale=1., tau=.9):
        return SharedActivationCost(MODEL, scale, tau)

    def test_known_pair_preserved_at_every_shared_scale(self):
        for scale in (0., .5, 1., 1.5):
            m = self.engine(scale, 0.)
            c = m.observe([owner(0, 2), owner(0, 2, 'D', 'CPU')], 0, 2)
            self.assertAlmostEqual(c['increment_J_proxy'], 2*m.pair)

    def test_all_solos_preserved(self):
        for task, route in (('C', 'CPU'), ('C', 'GPU'), ('D', 'CPU'), ('D', 'GPU')):
            for scale in (0., 1., 1.5):
                m = self.engine(scale)
                c = m.observe([owner(0, 2, task, route)], 0, 2)
                name = ('classification' if task == 'C' else 'detection')+'_'+route
                self.assertAlmostEqual(c['increment_J_proxy'], 2*m.solo[name])

    def test_unknown_pair_shares_exactly_once(self):
        m = self.engine()
        c = m.observe([owner(0, 2, 'C', 'CPU'), owner(0, 2, 'D', 'GPU')], 0, 2)
        self.assertAlmostEqual(c['hypothesized_pair_credit_J_proxy'], -2*m.shared)
        self.assertTrue(c['hypothetical_unmeasured_pair_transfer'])

    def test_zero_scale_removes_unmeasured_discount_and_idle_cost(self):
        m = self.engine(0.)
        c = m.observe([owner(0, 1), owner(2, 3, 'C', 'CPU')], 0, 4)
        self.assertEqual(c['hypothesized_idle_tail_J_proxy'], 0.)
        self.assertAlmostEqual(c['increment_J_proxy'], sum(m.solo[s] for s in ('classification_GPU', 'classification_CPU')))

    def test_idle_tail_exact(self):
        m = self.engine()
        c = m.observe([owner(0, 1)], 1, 3)
        self.assertAlmostEqual(c['increment_J_proxy'], m.shared*.9*(1-math.exp(-2/.9)))

    def test_history_before_window_kept(self):
        m = self.engine()
        c = m.observe([owner(0, 1)], 2, 3)
        self.assertAlmostEqual(c['increment_J_proxy'], m.shared*.9*(math.exp(-1/.9)-math.exp(-2/.9)))

    def test_adjacent_interval_split_invariance(self):
        m = self.engine()
        a = m.observe([owner(0, 2)], 0, 4)
        b = m.observe([owner(0, 1), owner(1, 2)], 0, 4)
        self.assertAlmostEqual(a['increment_J_proxy'], b['increment_J_proxy'])

    def test_burst_reduces_repeated_tail_with_same_work(self):
        m = self.engine()
        burst = m.episode([owner(0, 1), owner(1, 2)])
        split = m.episode([owner(0, 1), owner(3, 4)])
        self.assertGreater(split['full_episode_increment_J_proxy'], burst['full_episode_increment_J_proxy'])
        self.assertAlmostEqual(split['full_episode_increment_J_proxy']-burst['full_episode_increment_J_proxy'], m.shared*.9*(1-math.exp(-2/.9)))

    def test_tau_zero_order_invariant_without_overlap(self):
        m = self.engine(tau=0.)
        a = m.episode([owner(0, 1), owner(3, 5, 'D', 'CPU')])
        b = m.episode([owner(0, 2, 'D', 'CPU'), owner(3, 4)])
        self.assertAlmostEqual(a['full_episode_increment_J_proxy'], b['full_episode_increment_J_proxy'])

    def test_baseline_is_common_not_reduced_to_show_effect(self):
        m = self.engine()
        a = m.observe([owner(0, 1)], 0, 10)
        b = m.observe([owner(3, 4)], 0, 10)
        self.assertEqual(a['baseline_J_proxy'], b['baseline_J_proxy'])
        self.assertEqual(a['baseline_J_proxy'], 10*MODEL['reference_baseline_W_proxy'])

    def test_full_tail_removes_window_end_credit(self):
        m = self.engine()
        a = m.episode([owner(0, 1)])
        b = m.episode([owner(10, 11)])
        self.assertAlmostEqual(a['full_episode_increment_J_proxy'], b['full_episode_increment_J_proxy'])

    def test_window_additivity_including_history(self):
        m = self.engine()
        owners = [owner(0, 1), owner(2, 4, 'D', 'CPU')]
        whole = m.observe(owners, 0, 6)['increment_J_proxy']
        parts = sum(m.observe(owners, a, b)['increment_J_proxy'] for a, b in ((0, 1.5), (1.5, 3), (3, 6)))
        self.assertAlmostEqual(whole, parts)

    def test_marginal_matches_full_evaluator_and_known_pair(self):
        m = self.engine()
        prefix = [owner(0, 1, 'D', 'CPU')]
        reserves = [owner(1, 3, 'D', 'CPU')]
        candidate = owner(1, 2)
        result = m.marginal(prefix, reserves, candidate, 1, 4)
        self.assertAlmostEqual(result['marginal_full_episode_J_proxy'], m.pair-m.solo['detection_CPU'])
        self.assertAlmostEqual(result['marginal_window_J_proxy'], sum(result['decomposition'].values()))
        self.assertFalse(result['future_actual_durations_used'])

    def test_marginal_sees_existing_hot_state(self):
        m = self.engine()
        past = [owner(0, 1)]
        result = m.marginal(past, [], owner(1.2, 2.2), 1.2, 4)
        self.assertAlmostEqual(result['initial_shared_activation_state'], math.exp(-.2/.9))

    def test_reject_future_realized_prefix(self):
        with self.assertRaises(ValueError):
            self.engine().marginal([owner(0, 2)], [], owner(1, 2), 1, 3)

    def test_reject_same_lane_conflict(self):
        with self.assertRaises(ValueError):
            self.engine().observe([owner(0, 2), owner(1, 3, 'D', 'GPU')], 0, 4)

    def test_reject_third_concurrent_owner(self):
        with self.assertRaises(ValueError):
            segments([owner(0, 1), owner(0, 1, 'D', 'CPU'), owner(0, 1, 'C', 'CPU')], 0, 2)

    def test_reject_negative_dynamic_power(self):
        with self.assertRaises(ValueError):
            self.engine(scale=100.)

    def test_reject_invalid_parameters(self):
        for scale, tau in ((-1, 0), (1, -1), (float('nan'), 1)):
            with self.assertRaises(ValueError):
                self.engine(scale, tau)

    def test_empty_history_and_initial_idle_state(self):
        m = self.engine()
        self.assertEqual(m.observe([], 0, 1)['increment_J_proxy'], 0.)
        self.assertAlmostEqual(m.observe([], 0, 1, initial_shared=.5)['increment_J_proxy'], .5*m.shared*.9*(1-math.exp(-1/.9)))

    def test_future_owners_do_not_change_prefix(self):
        m = self.engine()
        a = m.observe([owner(0, 1)], 0, 2)
        b = m.observe([owner(0, 1), owner(3, 4, 'D', 'CPU')], 0, 2)
        self.assertEqual(a, b)

    def test_wrapper_does_not_mutate_saved_summary(self):
        from cost_adapter import CostObserver
        observer = CostObserver()
        summary = dict(gantt=[owner(0, 1)])
        original = json.dumps(summary)
        self.assertIn('shared_activation_cost', observer.annotate(summary, 0, 2))
        self.assertEqual(json.dumps(summary), original)


if __name__ == '__main__':
    unittest.main()
