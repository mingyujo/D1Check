import unittest
from tools.d1_scheduler_capacity import capacity


class CapacityTests(unittest.TestCase):
    def jobs(self,arrivals):
        return [dict(task='detection',priority='normal',arrival_ns=x*1e9,deadline_offset_ns=6e9) for x in arrivals]

    def test_overloaded_even_with_classification_removed(self):
        result=capacity(self.jobs([0]*11),{'detection_CPU_normal':[0,.6e9,0,1e9,1e9]})
        self.assertTrue(result['necessary_condition_violated']);self.assertAlmostEqual(result['excess_s'],.6)

    def test_tail_not_counted_as_before_response(self):
        result=capacity(self.jobs([0]*10),{'detection_CPU_normal':[0,.6e9,0,1e9,1e9]})
        self.assertFalse(result['necessary_condition_violated'])

    def test_window_not_whole_horizon_hides_overload(self):
        result=capacity(self.jobs([0]*11+[80]),{'detection_CPU_normal':[0,.6e9,0,0,0]})
        self.assertEqual(result['requests'],11);self.assertAlmostEqual(result['window_end_s'],6)


if __name__=='__main__':unittest.main()
