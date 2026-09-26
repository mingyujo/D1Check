import copy
import unittest

from tools import d1_arrival_policy_screen as screen


class PolicyScreenTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = screen.read_csv(screen.SOURCE / 'interference_metrics.csv')

    def test_aligned_existing_results_and_frontier(self):
        rows = screen.screen(self.source)
        self.assertEqual(len(rows), 45)
        queue = {r['policy']: r for r in rows if r['scenario'] == 'queue' and r['realized'] == 1.5}
        self.assertEqual({p for p, r in queue.items() if r['mean_frontier']},
                         {'FIXED_SPLIT', 'B2_PC', 'B3_SOLO_EFT_PC', 'P_PAIR_COST_PC'})
        self.assertEqual(queue['P_PAIR_COST_PC']['normal_planned'], 90)
        self.assertEqual(queue['P_PAIR_COST_PC']['predicted'], 1.5)
        self.assertEqual(sum(r['unfinished'] for r in rows), 0)

    def test_missing_denominator_or_duplicate_is_rejected(self):
        damaged = copy.deepcopy(self.source)
        damaged[0]['normal_planned'] = '17'
        with self.assertRaisesRegex(ValueError, 'denominator'):
            screen.screen(damaged)
        with self.assertRaisesRegex(ValueError, 'duplicated'):
            screen.screen(self.source + [self.source[0]])

    def test_dominance_keeps_ties_and_rejects_tradeoff(self):
        a = dict(zip(screen.METRICS, (100., 0., 1000., 0., 0)))
        b = dict(a)
        c = dict(zip(screen.METRICS, (120., 0., 1100., 0., 0)))
        d = dict(zip(screen.METRICS, (90., 0., 1500., 0., 0)))
        self.assertFalse(screen.dominates(a, b))
        self.assertTrue(screen.dominates(a, c))
        self.assertFalse(screen.dominates(a, d))


if __name__ == '__main__':
    unittest.main()
