import unittest
from tools.d1_scheduler_conditions_report import group_result


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.b=dict(planned=48,completed=48,deadline_met=48,energy_j=200.,peak_ap_c=35.,
                    thermal_degree_seconds=100.,urgent_p95_ms=300.,normal_mean_ms=1000.)

    def test_response_delay_inside_deadline_not_rejected(self):
        x=dict(self.b,energy_j=199.,peak_ap_c=34.9,thermal_degree_seconds=99.,urgent_p95_ms=600.)
        r=group_result([x],[self.b]);self.assertTrue(r['all_cases_J_and_heat_lower'])
        self.assertEqual(r['mean_delta_urgent_p95_ms'],300.)

    def test_each_context_must_pass_not_only_mean(self):
        x=dict(self.b,energy_j=190.);y=dict(self.b,energy_j=201.)
        self.assertFalse(group_result([x,y],[self.b,self.b])['joint_nonworse_gain'])

    def test_deadline_failure_not_gain(self):
        x=dict(self.b,energy_j=190.,deadline_met=47)
        self.assertEqual(group_result([x],[self.b])['classification'],'deadline_failure')

    def test_missing_not_zero(self):
        x=dict(self.b,energy_j=None)
        r=group_result([x],[self.b]);self.assertIsNone(r['mean_delta_energy_j'])
        self.assertFalse(r['joint_nonworse_gain'])

    def test_equal_not_winner(self):
        self.assertEqual(group_result([self.b],[self.b])['classification'],'unchanged')


if __name__=='__main__':unittest.main()
