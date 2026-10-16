import copy
import unittest
from tools import d1_scheduler_alternatives_report as r


class AlternativeReportTests(unittest.TestCase):
    def row(self,policy):
        return dict(stage='test',trace_seed=1,family='queue',scenario='mean',policy=policy,
            planned=24,completed=24,urgent_service_failure=0,normal_service_failure=1,
            energy_j=140.,thermal_degree_seconds=15.,peak_ap_c=31.,urgent_p95_ms=200.,
            deadline_met=23,gap_to_relaxed_bound_j=.5)

    def test_lower_energy_cannot_hide_service_failure(self):
        ref=self.row('EFT_REFERENCE');candidate=self.row('X');candidate.update(energy_j=130.,normal_service_failure=2)
        out=r.compare([ref,candidate])[-1]
        self.assertTrue(out['j_not_worse']);self.assertFalse(out['all_guard']);self.assertFalse(out['strict_model_improvement'])

    def test_missing_thermal_not_zero_or_pass(self):
        ref=self.row('EFT_REFERENCE');candidate=self.row('X');candidate.update(thermal_degree_seconds=None,peak_ap_c=None,completed=23)
        out=r.compare([ref,candidate])[-1]
        self.assertIsNone(out['delta_ap_area']);self.assertFalse(out['heat_not_worse']);self.assertFalse(out['all_guard'])

    def test_case_pairing_and_equality_not_improvement(self):
        ref=self.row('EFT_REFERENCE');candidate=self.row('X')
        out=r.compare([ref,candidate])[-1]
        self.assertTrue(out['all_guard']);self.assertFalse(out['strict_model_improvement'])
        candidate['trace_seed']=2
        with self.assertRaises(KeyError):r.compare([ref,candidate])


if __name__=='__main__':unittest.main()
