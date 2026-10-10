"""Finite additional budget and variant identity without environment starts."""
import unittest
from unittest.mock import patch
from pathlib import Path
from tools import d1_list_candidate_tail_run as r


class Contract(unittest.TestCase):
    def budget(self,phase,rows):
        b=object.__new__(r.Budget);b.phase=phase;b.rows=rows
        b.reg=dict(previous_cumulative_environment_starts=7865,previous_cumulative_learning_starts=1045)
        b.work_guard=lambda:None
        return b

    def test_previous_totals_never_reset_and_all_starts_count(self):
        b=self.budget('pilot',[dict(learning=True,status='failed',phase='pilot'),dict(learning=False,status='started',phase='gate')])
        c=b.consumption()
        self.assertEqual(c['cumulative_environment_starts'],7867)
        self.assertEqual(c['cumulative_learning_starts'],1046)
        self.assertEqual(c['failed'],1)

    def test_phase_cap_does_not_borrow_other_phase_room(self):
        b=self.budget('opportunity',[dict(learning=False,status='completed',phase='opportunity') for _ in range(32)])
        with self.assertRaises(TimeoutError):b.guard()

    def test_whole_tranche_and_learning_caps(self):
        b=self.budget('gate',[dict(learning=False,status='completed',phase='pilot') for _ in range(1536)])
        with self.assertRaises(TimeoutError):b.guard()
        b=self.budget('main',[dict(learning=True,status='completed',phase='pilot') for _ in range(416)])
        with self.assertRaises(TimeoutError):b.guard(learning=True)

    def test_registered_case_sets_are_disjoint_and_roles_have_same_budget(self):
        train=r.r.cases(range(820010001,820010017),True)
        develop=r.r.cases((820020101,820020102));final=r.r.cases((820030101,820030102,820030103,820030104))
        self.assertEqual((len(train),len(develop),len(final)),(64,24,48))
        self.assertFalse({q['seed'] for q in train}&{q['seed'] for q in develop+final})
        self.assertFalse({q['seed'] for q in develop}&{q['seed'] for q in final})
        self.assertEqual(r.STAGE_CAPS['pilot'],2*3*32)
        self.assertEqual(r.STAGE_CAPS['main'],2*3*32)
        self.assertEqual(sum(r.STAGE_CAPS.values()),1404)

    def test_completed_task_cannot_create_a_budget_in_another_directory(self):
        with patch.object(Path,'exists',return_value=True):
            with self.assertRaises(FileExistsError):r.register(Path('output/new_directory_cannot_reset_budget'))

if __name__=='__main__':unittest.main()
