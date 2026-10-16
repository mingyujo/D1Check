"""Service-denominator and null-cost interpretation tests; no environments."""
import unittest
from unittest.mock import patch
from tools import d1_triton_report as r


def row(policy, **changes):
    x = dict(scope='resource', environment='immediate_allow', seed=1, family='low', context='mean',
        policy=policy, planned=10, completed=10, deadline_met=10, urgent_n=2, normal_n=8,
        urgent_service_failure=0, normal_service_failure=0, urgent_p95_ms=1., normal_mean_ms=2.,
        energy_j=10., peak_ap_c=30., thermal_degree_seconds=4., overlap_s=1.,
        cpu_occupied_s=1., gpu_occupied_s=1., decision_host_total_s=0.)
    x.update(changes)
    return x


class ReportCases(unittest.TestCase):
    def test_lower_partial_energy_cannot_be_joint_reduction_and_AP_delta_null(self):
        rows = [row(r.NEW[0]), row('SHARED_EFT'), row(r.NEW[1], completed=5, deadline_met=5,
                energy_j=1., peak_ap_c=None, thermal_degree_seconds=None)]
        pairs = r.paired(rows)
        x = next(x for x in pairs if x['policy'] == r.NEW[1] and x['reference'] == r.NEW[0])
        self.assertEqual(x['delta_energy_j'], -9)
        self.assertIsNone(x['delta_peak_ap_c'])
        self.assertFalse(x['joint_strict'])
        self.assertEqual(x['interpretation'], 'service_loss')

    def test_full_work_with_deadline_loss_not_eligible_for_cost_success(self):
        pairs = r.paired([row(r.NEW[0]), row('SHARED_EFT'),
                          row(r.NEW[1], deadline_met=9, energy_j=9, peak_ap_c=29)])
        x = next(x for x in pairs if x['policy'] == r.NEW[1])
        self.assertTrue(x['both_full_work'])
        self.assertFalse(x['both_full_timely'])
        self.assertFalse(x['joint_strict'])

    def test_group_keeps_whole_denominator_and_missing_AP_not_dropped(self):
        group = r.old.group_summary([row(r.NEW[1]), row(r.NEW[1], seed=2, completed=5,
            deadline_met=5, peak_ap_c=None, thermal_degree_seconds=None)])[0]
        self.assertEqual(group['completion_rate'], .75)
        self.assertEqual(group['timely_rate'], .75)
        self.assertEqual(group['ap_complete_cases'], 1)
        self.assertIsNone(group['peak_ap_c'])


class ReproductionCases(unittest.TestCase):
    def test_new_replay_uses_separate_accounting_without_environment_execution(self):
        from tools import d1_triton_reproduce as replay
        s = r.s
        original = s.LOCAL
        before = s.consumption()
        original_contract = s.digest(s.BUNDLE / 'contract.json')
        target = s.ROOT / ('output/external_rules_20261007_replay_io_fixture_' +
                           s.stamp().replace(':', '').replace('.', '').replace('+', '_'))
        with patch.object(s, 'LOCAL', original), patch.object(s, 'START', s.START), patch.object(s, 'run', return_value=[]) as mocked:
            replay.run(target)
            self.assertEqual(s.LOCAL, target.resolve())
            self.assertNotEqual(s.START, '2026-10-07T13:45:00+00:00')
            mocked.assert_called_once_with()
        self.assertEqual(s.LOCAL, original)
        self.assertEqual(s.consumption(), before)
        self.assertEqual(s.digest(s.BUNDLE / 'contract.json'), original_contract)

    def test_replay_cannot_overwrite_original_campaign_or_existing_user_directory(self):
        from tools import d1_triton_reproduce as replay
        with self.assertRaises(ValueError):
            replay.run(r.s.LOCAL)
        with self.assertRaises(ValueError):
            replay.run(r.s.ROOT / 'docs')


if __name__ == '__main__':
    unittest.main()
