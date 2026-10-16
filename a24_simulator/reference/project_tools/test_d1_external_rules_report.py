"""Independent aggregation/paired eligibility checks; no simulator calls."""
import unittest
from tools import d1_external_rules_report as report


def row(policy,completed=2,timely=2,energy=10,peak=30):
    return dict(scope='gate',environment='quiet_healthy',seed=1,family='low',context='mean',policy=policy,
                planned=2,completed=completed,deadline_met=timely,urgent_n=1,normal_n=1,
                urgent_service_failure=0,normal_service_failure=2-timely,
                energy_j=energy,peak_ap_c=peak,thermal_degree_seconds=0 if peak is not None else None,
                urgent_p95_ms=100,normal_mean_ms=200 if completed==2 else None,
                overlap_s=1,cpu_occupied_s=2,gpu_occupied_s=1,decision_host_total_s=None)


class ReportTests(unittest.TestCase):
    def test_lower_partial_energy_cannot_be_a_joint_gain(self):
        pairs=report.paired([row(report.r.ALWAYS),row(report.r.ENTE,completed=1,timely=1,energy=8,peak=None)])
        x=pairs[-1]
        self.assertEqual(x['delta_energy_j'],-2)
        self.assertFalse(x['full_work']);self.assertFalse(x['both_full_timely']);self.assertFalse(x['joint_strict'])
        self.assertIsNone(x['delta_peak_ap_c'])

    def test_denominator_and_unavailable_AP_not_silently_dropped(self):
        first=row(report.r.ENTE);second=dict(row(report.r.ENTE,completed=1,timely=1,peak=None),seed=2)
        g=report.group_summary([first,second])[0]
        self.assertEqual(g['planned'],4);self.assertEqual(g['completed'],3)
        self.assertEqual(g['completion_rate'],.75);self.assertEqual(g['timely_rate'],.75)
        self.assertEqual(g['ap_complete_cases'],1);self.assertIsNone(g['peak_ap_c'])
        self.assertIsNone(g['decision_host_total_s'])


if __name__=='__main__':unittest.main()
