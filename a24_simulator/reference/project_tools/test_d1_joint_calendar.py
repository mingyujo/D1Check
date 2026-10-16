import copy
import json
import math
import unittest
import numpy as np
from unittest.mock import patch
from tools import d1_joint_calendar as joint

x = joint.original.x


class JointCalendarTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.frozen, initial = x.p.inputs(x.p.BUNDLE); cls.initial = initial['initial']
        cls.tickets = json.loads((x.ROOT/'inputs.json').read_text(encoding='utf8'))['cases'][x.CASES[-1]]['tickets'][:4]
        old = joint.original.plan(cls.frozen, cls.initial, cls.tickets, grid_s=.02, timeout_s=10.)
        jobs = copy.deepcopy(old['jobs']); profile = x.p.profile(cls.frozen)
        for j in jobs:
            q = next(q for q in cls.tickets if q['id'] == j['id'])
            j['end'] = j['start']+math.ceil(sum(profile[x.p.key(q, j['backend'])])/1e9/.02-1e-8)*.02
        cls.segments = x.p.segments(jobs, 0., 180.)
        cost = x.p.model.costs(cls.segments, cls.initial, list(range(35, 181)), cls.frozen, 180.)
        ref = x.p.memory.initialize(cls.initial['preload'], cls.frozen['ap']['beta'], 30.)['reference_c']
        rise = np.maximum(np.array(cost['ap_path'])-ref, 0.)
        cls.peak_cap = max(cost['ap_path'])+1e-6
        cls.area_cap = float(np.sum((rise[1:]+rise[:-1])*.5))+1e-6
        cls.before = x.p.digest(joint.original.__file__)
        cls.solver_before = joint.original.milp
        cls.result = joint.plan(cls.frozen, cls.initial, cls.tickets,
            ap_cap_c=cls.peak_cap, area_cap_c_s=cls.area_cap, grid_s=.02, timeout_s=15.)

    def test_real_engine_replay_meets_peak_area_and_full_deadlines(self):
        result = self.result
        self.assertEqual(result['status'], 'replayed_incumbent')
        self.assertEqual(result['metrics']['deadline_met'], 4)
        self.assertTrue(result['actual_replay_within_model_ap_cap'])
        self.assertTrue(result['actual_replay_within_AP_area_cap'])
        x.validate_schedule(x.jobs_from_ledger(result['ledger']), self.tickets, x.p.profile(self.frozen))
        self.assertFalse(result['original_continuous_optimality_proved'])

    def test_epigraph_area_matches_unchanged_rounded_plant(self):
        result = self.result; jobs = copy.deepcopy(result['jobs']); profile = x.p.profile(self.frozen)
        for j in jobs:
            q = next(q for q in self.tickets if q['id'] == j['id'])
            j['end'] = j['start']+math.ceil(sum(profile[x.p.key(q, j['backend'])])/1e9/.02-1e-8)*.02
        segments = x.p.segments(jobs, 0., 180.)
        cost = x.p.model.costs(segments, self.initial, list(range(35, 181)), self.frozen, 180.)
        ref = x.p.memory.initialize(self.initial['preload'], self.frozen['ap']['beta'], 30.)['reference_c']
        rise = np.maximum(np.array(cost['ap_path'])-ref, 0.)
        area = float(np.sum((rise[1:]+rise[:-1])*.5))
        self.assertAlmostEqual(area, result['rounded_planning_AP_area_c_s'], places=8)
        self.assertLessEqual(area, result['planning_epigraph_area_c_s']+1e-8)
        self.assertLessEqual(area, self.area_cap+1e-8)

    def test_original_planner_globals_and_frozen_bytes_preserved(self):
        self.assertEqual(x.p.digest(joint.original.__file__), self.before)
        self.assertIs(joint.original.milp, type(self).solver_before)
        self.assertEqual(x.p.digest(x.p.BUNDLE/'model.json'), x.p.MODEL_SHA)
        self.assertEqual(x.p.digest(x.p.BUNDLE/'initial_inputs.json'), x.p.INITIAL_SHA)
        self.assertFalse(self.result['old_planner_mutated'])

    def test_impossible_comparison_returns_no_result_not_zero_cost(self):
        result = joint.plan(self.frozen, self.initial, self.tickets,
                            ap_cap_c=20., area_cap_c_s=0., grid_s=.05, timeout_s=5.)
        self.assertEqual(result['status'], 'no_incumbent'); self.assertIsNone(result['jobs'])
        self.assertIsNone(result['actual_replay_within_AP_area_cap'])
        self.assertNotIn('metrics', result)

    def test_missing_comparison_and_negative_area_rejected(self):
        for cap in (float('nan'), -1.):
            with self.assertRaises(ValueError):
                joint.plan(self.frozen, self.initial, self.tickets, ap_cap_c=self.peak_cap, area_cap_c_s=cap)

    def test_extended_invalid_solution_cannot_hide_in_projection(self):
        from scipy.optimize import OptimizeResult
        def invalid(c, **kwargs):
            return OptimizeResult(status=1, success=False, message='fixture', x=np.zeros(len(c)), fun=0.)
        with patch.object(joint.original, 'milp', side_effect=invalid), self.assertRaisesRegex(ValueError, 'extended constraints'):
            joint.plan(self.frozen, self.initial, self.tickets, ap_cap_c=self.peak_cap,
                       area_cap_c_s=self.area_cap, grid_s=.05, timeout_s=5.)


if __name__ == '__main__': unittest.main()
