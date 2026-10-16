"""Selection guard checks, no environment/learning starts."""
import unittest
from tools import d1_cpu_gpu_method_report as r


def row(policy,**changes):
    value=dict(seed=1,family='low',context='mean',policy=policy,planned=10,completed=10,
        energy_full_work_eligible=True,deadline_met=10,urgent_service_failure=0,normal_service_failure=0,
        energy_j=10.,peak_ap_c=30.,urgent_p95_ms=100.,normal_mean_ms=1000.)
    value.update(changes);return value


class Selection(unittest.TestCase):
    def setUp(self):self.saved=dict(r.LABELS);r.LABELS={r.SHARED:'Shared',r.BAND:'Band','E_seed11':'E'}
    def tearDown(self):r.LABELS=self.saved
    def candidate(self,**changes):
        results=r.eligibility([row(r.SHARED),row(r.BAND),row('E_seed11',**changes)])
        return next(x for x in results if x['policy']=='E_seed11')
    def test_energy_gain_without_ap_regression_is_eligible(self):
        self.assertTrue(self.candidate(energy_j=9.)['eligible'])
    def test_heat_regression_rejects_energy_gain(self):
        self.assertFalse(self.candidate(energy_j=9.,peak_ap_c=30.1)['eligible'])
    def test_incomplete_work_rejects_energy_gain(self):
        self.assertFalse(self.candidate(energy_j=9.,completed=9,energy_full_work_eligible=False)['eligible'])
    def test_tie_does_not_claim_improvement(self):
        self.assertTrue(self.candidate()['all_conditions_nonworse'])
        self.assertFalse(self.candidate()['eligible'])
    def test_primary_deadline_violation_not_relative_success(self):
        rows=[row(p,normal_service_failure=1,deadline_met=9,energy_j=9. if p=='E_seed11' else 10.) for p in (r.SHARED,r.BAND,'E_seed11')]
        self.assertFalse(next(x for x in r.eligibility(rows) if x['policy']=='E_seed11')['eligible'])


if __name__=='__main__':unittest.main()
