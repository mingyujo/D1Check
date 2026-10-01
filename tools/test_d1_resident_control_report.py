"""Post-run cumulative plot boundaries, without device access."""
import unittest
from tools.d1_resident_control_report import diagnostic_cumulative_j


class CumulativeDiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.power={'resident_idle':1., 'detection_CPU':2.,
                    'classification_GPU+detection_CPU':3.}
        self.states=[dict(start_s=0.,end_s=35.,state='idle'),
                     dict(start_s=35.,end_s=36.,state='classification:GPU+detection:CPU'),
                     dict(start_s=36.,end_s=40.,state='detection:CPU'),
                     dict(start_s=40.,end_s=120.,state='idle')]

    def test_exact_boundaries_and_whole_device_no_double_count(self):
        for t,j in [(0,0),(35,35),(35.5,36.5),(36,38),(40,46),(120,126)]:
            self.assertAlmostEqual(diagnostic_cumulative_j(self.states,self.power,t),j)

    def test_unknown_state_does_not_fill_zero_or_idle(self):
        states=[dict(start_s=0,end_s=120,state='classification:CPU')]
        self.assertIsNone(diagnostic_cumulative_j(states,self.power,120))

    def test_gap_overlap_and_truncated_states_are_not_full_window(self):
        for start in (34,36):
            states=[dict(self.states[0]),dict(self.states[1],start_s=start)]
            self.assertIsNone(diagnostic_cumulative_j(states,self.power,36))
        self.assertIsNone(diagnostic_cumulative_j(self.states[:-1],self.power,120))

    def test_incomplete_case_zero_origin_is_not_full_energy(self):
        self.assertEqual(diagnostic_cumulative_j([],self.power,0),0)
        self.assertIsNone(diagnostic_cumulative_j([],self.power,1))
        self.assertIsNone(diagnostic_cumulative_j(self.states,self.power,121))
        self.assertIsNone(diagnostic_cumulative_j(self.states,self.power,-1))


if __name__=='__main__':unittest.main()
