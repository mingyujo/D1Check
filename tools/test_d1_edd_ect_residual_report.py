"""A cost decrease cannot hide work loss, response loss, or weak comparisons."""
import unittest
from tools import d1_edd_ect_residual_report as r


def row(policy=r.BASE,**changes):
    value=dict(policy=policy,planned=10,completed=10,energy_full_work_eligible=True,
        urgent_service_failure=0,normal_service_failure=0,deadline_met=10,
        energy_j=10.,peak_ap_c=30.,urgent_p95_ms=100.,normal_mean_ms=1000.)
    value.update(changes)
    return value


class Eligibility(unittest.TestCase):
    def test_lower_heat_with_more_energy_is_not_gain(self):
        self.assertFalse(r.compare(row(peak_ap_c=29.,energy_j=10.1),row())['heat_gain'])

    def test_missing_work_cannot_be_gain(self):
        self.assertFalse(r.compare(row(completed=9,energy_full_work_eligible=False,energy_j=1.,peak_ap_c=20.),row())['nonworse'])

    def test_slower_urgent_cannot_be_gain(self):
        self.assertFalse(r.compare(row(urgent_p95_ms=101.,energy_j=9.,peak_ap_c=29.),row())['heat_gain'])

    def test_own_base_only_improvement_is_not_c_signal(self):
        refs=[row(r.BASE,energy_j=12.,peak_ap_c=31.),row(r.SHARED,energy_j=9.),row(r.BAND,energy_j=9.)]
        self.assertFalse(r.gain_signal(row(),refs,True))

    def test_overloaded_relative_gain_is_not_primary_witness(self):
        refs=[row(p,normal_service_failure=1,deadline_met=9) for p in (r.BASE,r.SHARED,r.BAND)]
        candidate=row(energy_j=9.,peak_ap_c=29.,normal_service_failure=1,deadline_met=9)
        self.assertTrue(r.compare(candidate,refs[0])['heat_gain'])
        self.assertFalse(r.gain_signal(candidate,refs,True))

    def test_supported_true_primary_signal(self):
        refs=[row(p) for p in (r.BASE,r.SHARED,r.BAND)]
        self.assertTrue(r.gain_signal(row(energy_j=9.,peak_ap_c=29.),refs,True))
        self.assertFalse(r.gain_signal(row(energy_j=9.,peak_ap_c=29.),refs,False))


if __name__=='__main__':unittest.main()
