import copy
import unittest
from unittest.mock import patch
from tools import d1_reserved_thermal_numeric_r2 as r2
from tools import test_d1_reserved_thermal as old_tests


class NumericR2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        old_tests.ControllerBoundaryTests.setUpClass()
        cls.frozen = old_tests.ControllerBoundaryTests.frozen
        cls.initial = old_tests.ControllerBoundaryTests.initial
        cls.lanes = old_tests.ControllerBoundaryTests.lanes
        cls.q = dict(old_tests.ControllerBoundaryTests.q, task='detection', priority='normal',
                     deadline_offset_ns=6000000000)

    def test_front_boundary_snaps_only_sub_nanosecond(self):
        c = r2.Controller(self.frozen, self.initial)
        a = c.place(dict(self.q, id='a'), 'CPU', 35., [])
        events = []
        b = r2.BoundedPlacement(c, events).place(dict(self.q, id='b'), 'CPU',
                                               a['end']-3.333440190544934e-10, [a])
        self.assertEqual(b['start'], a['end'])
        self.assertGreater(events[-1]['displacement_s'], 0)
        self.assertLessEqual(events[-1]['displacement_s'], r2.rule.EPS)
        self.assertTrue(r2.rule.P.segments([a, b], 35., 120.))

    def test_future_boundary_rejects_large_displacement(self):
        c = r2.Controller(self.frozen, self.initial)
        a = c.place(self.q, 'CPU', 35., [])
        blocker = dict(a, id='future', start=a['end']-3.333440190544934e-10, end=a['end']+1.)
        events = []
        with self.assertRaisesRegex(r2.NumericConflict, 'total_displacement'):
            r2.BoundedPlacement(c, events).place(self.q, 'CPU', 35., [blocker])
        self.assertGreater(events[-1]['required_displacement_s'], 1.)
        self.assertFalse(events[-1]['accepted'])

    def test_cumulative_shift_cannot_exceed_epsilon(self):
        class Fixed:
            def place(self, request, backend, earliest, jobs):
                return dict(id=request['id'], start=earliest, end=earliest+1e-6,
                            backend=backend, state='detection_CPU')
        jobs = [dict(start=-1., end=6e-10, backend='CPU', state='detection_CPU'),
                dict(start=1e-6+2e-10, end=1e-6+1e-9, backend='CPU', state='detection_CPU')]
        events = []
        with self.assertRaisesRegex(r2.NumericConflict, 'total_displacement'):
            r2.BoundedPlacement(Fixed(), events).place(self.q, 'CPU', 0., jobs)
        self.assertEqual(events[-1]['displacement_s'], 6e-10)

    def test_real_saved_gap_deadline_and_supported_parallel_unchanged(self):
        c = r2.Controller(self.frozen, self.initial)
        a = c.place(dict(self.q, id='a'), 'CPU', 35., [])
        b = r2.BoundedPlacement(c).place(dict(self.q, id='b'), 'CPU', a['end']+.25, [a])
        self.assertEqual(b['start'], a['end']+.25)
        self.assertEqual(b['deadline'], 41.)
        q = dict(self.q, id='gpu', task='classification', priority='urgent')
        parallel = r2.BoundedPlacement(c).place(q, 'GPU', 35., [a])
        self.assertEqual(parallel['start'], 35.)

    def test_large_unsupported_overlap_is_rejected(self):
        class Broken:
            def place(self, request, backend, earliest, jobs):
                return dict(id=request['id'], start=35., end=36., backend=backend, state='detection_CPU')
        with self.assertRaisesRegex(r2.NumericConflict, 'overlap_exceeded'):
            r2.BoundedPlacement(Broken()).place(self.q, 'CPU', 35.,
                [dict(start=35., end=36., backend='CPU', state='detection_CPU')])

    def test_rejected_retained_candidate_continues_unchanged_reference(self):
        a = r2.rule.Controller(self.frozen, self.initial)
        b = r2.Controller(self.frozen, self.initial)
        for c in (a, b):
            c.observe(35e9, self.lanes)
            c.book.calendar = [c.place(self.q, 'CPU', 35., [])]
            c.book.disabled = True  # Force the original reference fallback independently of numeric veto.
        with patch.object(b, 'finish_retained', side_effect=r2.NumericConflict('numeric_total_displacement_exceeded')):
            actual = b(None, [self.q], self.lanes, 35e9, r2.rule.X.settings(), None, None)
        expected = a(None, [self.q], self.lanes, 35e9, r2.rule.X.settings(), None, None)
        actual.pop('public_policy'); expected.pop('public_policy')
        self.assertEqual(actual, expected)
        self.assertTrue(any('numeric_total_displacement_exceeded' in x['reasons'] for x in b.records[-1]['candidates']))

    def test_effective_wait_dedup_and_real_lane_ownership(self):
        job = dict(id='a', backend='CPU', start=35.5)
        first = r2.effective_action(job, 35_000_000_000, self.lanes)
        second = r2.effective_action(dict(job, start=35.8), 35_000_000_000, self.lanes)
        self.assertEqual(first['signature'], second['signature'])
        self.assertEqual(first['wait_until_ns'], 35_250_000_000)
        lanes = copy.deepcopy(self.lanes); lanes['CPU']['request'] = self.q
        self.assertEqual(r2.effective_action(dict(job, start=35.), 35_000_000_000, lanes)['kind'], 'INVALID_BUSY_DISPATCH')

    def test_telemetry_preserves_original_choice_caps_budget(self):
        a = r2.rule.Controller(self.frozen, self.initial)
        b = r2.Controller(self.frozen, self.initial)
        for c in (a, b): c.observe(35e9, self.lanes)
        actual = b(None, [self.q], self.lanes, 35e9, r2.rule.X.settings(), None, None)
        expected = a(None, [self.q], self.lanes, 35e9, r2.rule.X.settings(), None, None)
        actual.pop('public_policy'); expected.pop('public_policy')
        self.assertEqual(actual, expected)
        self.assertEqual(a.book.caps, b.book.caps)
        self.assertEqual(a.book.budget_j, b.book.budget_j)
        self.assertTrue(all('effective_action' in x for x in b.records[-1]['candidates']))

    def test_environment_requires_budget_callback(self):
        with self.assertRaisesRegex(ValueError, 'budget'):
            r2.simulate(self.frozen, self.initial, [self.q], 'mean', None)


if __name__ == '__main__':
    unittest.main()
