import json
import tempfile
import unittest
from pathlib import Path

from tools import d1_arrival_service_guard as guard


class ServiceGuardTests(unittest.TestCase):
    def test_archived_screen_preserves_service_and_energy_boundary(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / 'readout'
            result = guard.evaluate(output)
            self.assertEqual(result['paired_conditions'], 45)
            self.assertEqual(result['case_count'], 135)
            self.assertEqual(result['candidate_eligible_counts'],
                             {'B2_PC': 21, 'B3_SOLO_EFT_PC': 22})
            self.assertEqual(result['eligible_both_count'], 7)
            rep = {r['policy']: r for r in result['representative']}
            self.assertTrue(rep['B2_PC']['eligible'])
            self.assertFalse(rep['B3_SOLO_EFT_PC']['eligible'])
            self.assertEqual(rep['B3_SOLO_EFT_PC']['failed_conditions'], 'urgent_p95_loss')
            self.assertEqual(rep['B3_SOLO_EFT_PC']['urgent_p95_delta_ms'], '373.651580')
            self.assertIsNone(result['energy_ap_policy_rank'])
            self.assertFalse(result['experiment_ready'])
            with self.assertRaises(FileExistsError):
                guard.evaluate(output)

    def test_zero_loss_boundaries_and_incomplete_requests(self):
        contract = json.loads(guard.CONTRACT.read_text(encoding='utf-8'))
        reference = dict(scenario='queue', realized='1.5', seed='201', policy='CPU_URGENT',
            planned='24', urgent_planned='6', normal_planned='18', unfinished='0',
            urgent_not_timely='0', normal_not_timely='6', urgent_p95_ms='641.346305',
            normal_mean_ms='4515.764720')
        candidate = dict(reference, policy='B2_PC', normal_not_timely='6')
        self.assertTrue(guard.screen(candidate, reference, contract)['eligible'])
        candidate['normal_not_timely'] = '7'
        self.assertEqual(guard.screen(candidate, reference, contract)['failed_conditions'],
                         'normal_deadline_loss')
        candidate['normal_not_timely'] = '6'
        candidate['unfinished'] = '1'
        self.assertEqual(guard.screen(candidate, reference, contract)['failed_conditions'],
                         'incomplete_requests')
        candidate['unfinished'] = '0'
        candidate['urgent_p95_ms'] = '641.346306'
        self.assertEqual(guard.screen(candidate, reference, contract)['failed_conditions'],
                         'urgent_p95_loss')


if __name__ == '__main__':
    unittest.main()
