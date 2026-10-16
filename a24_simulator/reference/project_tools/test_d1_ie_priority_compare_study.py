"""Counters and fixed evaluation scopes, without environment/device starts."""
import unittest
from unittest.mock import patch
from pathlib import Path
from tools import d1_ie_priority_compare_study as s

class Contract(unittest.TestCase):
    def test_no_new_directory_budget_reset(self):
        with patch.object(Path,'exists',return_value=True):
            with self.assertRaises(FileExistsError):s.register(Path('output/unused_new_folder'))
    def test_cumulative_failed_and_started_count(self):
        b=object.__new__(s.Budget);b.rows=[dict(status='failed'),dict(status='started')]
        self.assertEqual(b.consumption()['cumulative_environment_starts'],9271)
        self.assertEqual(b.consumption()['cumulative_learning_starts'],1449)
        self.assertEqual(b.consumption()['native_failed'],1)
    def test_stage_sum_and_disjoint_seeds(self):
        self.assertEqual(sum(s.STAGE_CAPS.values()),448)
        a=s.cases((822020101,822020102));b=s.cases((822030101,822030102))
        self.assertEqual((len(a),len(b),len(s.ROLES)),(24,24,9))
        self.assertFalse({q['seed'] for q in a}&{q['seed'] for q in b})
        self.assertEqual(len({(q['seed'],q['family'],q['context']) for q in a+b}),48)

if __name__=='__main__':unittest.main()
