import unittest
from tools.d1_baseline_policy import SerialBaseline


class BaselineTest(unittest.TestCase):
    def snapshot(self):
        return dict(now_ns=100, common_constraints_allow_start=True, in_flight=[],
                    capability={'detection': {'CPU': 'passed'}}, queue=[
                        dict(request_id='old', arrival_ns=10, task_id='detection', priority='normal', deadline_ns=None),
                        dict(request_id='urgent', arrival_ns=20, task_id='detection', priority='urgent', deadline_ns=200)])

    def test_fifo_and_priority_are_separate(self):
        for policy, expected in [('4.4/B0', 'old'), ('4.4/B1', 'urgent')]:
            result = SerialBaseline(policy, {'detection': 'CPU'}, 1000).decide(self.snapshot())
            self.assertEqual(result['starts'][0]['request_id'], expected)

    def test_common_aging_prevents_normal_starvation(self):
        self.assertEqual(SerialBaseline('4.4/B1', {'detection': 'CPU'}, 85).decide(self.snapshot())['starts'][0]['request_id'], 'old')

    def test_edf_and_stable_tie(self):
        s = self.snapshot();s['queue'][0].update(priority='urgent', deadline_ns=150)
        self.assertEqual(SerialBaseline('4.4/B1', {'detection': 'CPU'}, 1000).decide(s)['starts'][0]['request_id'], 'old')

    def test_common_gate_busy_and_no_fallback(self):
        p = SerialBaseline('4.4/B0', {'detection': 'CPU'}, 1000)
        for key, value in [('common_constraints_allow_start', False), ('in_flight', ['running']), ('capability', {})]:
            s = self.snapshot();s[key] = value
            self.assertEqual(p.decide(s)['starts'], [])

    def test_future_arrival_rejected(self):
        s = self.snapshot();s['queue'][0]['arrival_ns'] = 101
        with self.assertRaises(ValueError):
            SerialBaseline('4.4/B0', {'detection': 'CPU'}, 1000).decide(s)
