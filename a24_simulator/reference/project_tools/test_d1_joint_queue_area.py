import copy
import math
import unittest
from tools import d1_joint_queue_area as joint

P = joint.P


class JointQueueAreaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.frozen, case = P.inputs(P.BUNDLE); cls.initial = case['initial']
        cls.q = dict(id='fixture/0', ordinal=0, task='classification', priority='urgent',
            arrival_ns=int(35e9), deadline_offset_ns=int(1.5e9))
        cls.lanes = {b: dict(request=None, phase='AVAILABLE', since=0, dispatch=None) for b in ('CPU', 'GPU')}
        cls.before = P.digest(joint.parent.__file__)

    def controller(self, now=35.):
        c = joint.Controller(self.frozen, self.initial)
        c.observe(now*1e9, self.lanes)
        return c

    def test_global_query_area_matches_original_model_continuation(self):
        for now in (35., 42.37, 43.):
            c = self.controller(now)
            q = dict(self.q, arrival_ns=round(now*1e9))
            jobs = [c.place(q, 'GPU', now, [])]
            value = c.future_area(jobs, now)
            segments = copy.deepcopy(c.history)+P.segments(jobs, now, 180.)
            cost = P.model.costs(segments, self.initial, list(range(35, 181)), self.frozen, 180.)
            expected = sum((.5 if t in (35, 180) else 1.)*max(0., ap-c.init['reference_c'])
                for t, ap in zip(range(35, 181), cost['ap_path']) if t >= math.ceil(now))
            self.assertAlmostEqual(value, expected, places=8)

    def test_relative_area_veto_cannot_become_an_absolute_temperature_target(self):
        c = self.controller(); c.t = 32.
        cpu = [c.place(self.q, 'CPU', 35., [])]
        gpu = [c.place(self.q, 'GPU', 35., [])]
        reference = c.score(cpu, 35.)
        self.assertIsNotNone(reference)
        self.assertEqual(c.reference_area, reference['future_rectified_AP_area_c_s'])
        self.assertGreater(c.future_area(gpu, 35.), c.reference_area)
        self.assertIsNone(c.score(gpu, 35.))
        self.assertEqual(c.area_vetoes, 1)
        self.assertIsNotNone(c.score(cpu, 35.))

    def test_future_queue_private_lane_data_and_unmeasured_state_blocked(self):
        c = self.controller(); settings = joint.x.settings()
        with self.assertRaisesRegex(ValueError, 'future ticket'):
            c(None, [dict(self.q, arrival_ns=int(36e9))], self.lanes, int(35e9), settings, None, None)
        bad = copy.deepcopy(self.lanes); bad['CPU']['future_service_ns'] = 1
        with self.assertRaisesRegex(ValueError, 'private lane'):
            c(None, [self.q], bad, int(35e9), settings, None, None)
        with self.assertRaisesRegex(ValueError, 'unsupported joint'):
            c.future_area([dict(state='detection_GPU', start=35., end=36.)], 35.)

    def test_no_observed_future_ap_input_and_reference_reset_each_decision(self):
        c1 = self.controller(); c2 = self.controller(); settings = joint.x.settings()
        first = c1(None, [self.q], self.lanes, int(35e9), settings, None, None)
        second = c2(None, [self.q], self.lanes, int(35e9), settings, None, 999.)
        self.assertEqual(first, second)
        self.assertIsNotNone(c1.reference_area)
        c1(None, [], self.lanes, int(35e9), settings, None, None)
        self.assertIsNone(c1.reference_area)

    def test_old_source_frozen_bytes_and_search_limits_preserved(self):
        self.assertEqual(P.digest(joint.parent.__file__), self.before)
        self.assertEqual(P.digest(P.BUNDLE/'model.json'), P.MODEL_SHA)
        self.assertEqual(P.digest(P.BUNDLE/'initial_inputs.json'), P.INITIAL_SHA)
        c = self.controller()
        c(None, [self.q], self.lanes, int(35e9), joint.x.settings(), None, None)
        self.assertTrue(all(r['expanded'] <= 64 for r in c.records))


if __name__ == '__main__': unittest.main()
