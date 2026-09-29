import csv
import tempfile
import unittest
from pathlib import Path

from tools import d1_arrival_service_choice as choice


class ServiceChoiceTests(unittest.TestCase):
    def test_saved_denominators_and_representative_tradeoff(self):
        source_sha = choice.digest(choice.BUNDLE / 'service_metrics.csv')
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / 'readout'
            result = choice.evaluate(output)
            self.assertEqual(result['case_count'], 135)
            self.assertEqual(result['measured_energy_ap_complete_cases'], 0)
            self.assertIsNone(result['policy_energy_ap_rank'])
            self.assertFalse(result['experiment_ready'])
            service = {r['policy']: r for r in result['representative_service']}
            self.assertEqual([(service[p]['timely_all_planned'], service[p]['unfinished'])
                for p in choice.POLICIES], [(18, 0), (20, 0), (20, 0)])
            self.assertLess(service['B2_PC']['urgent_p95_ms'],
                            service['B3_SOLO_EFT_PC']['urgent_p95_ms'])
            self.assertGreater(service['B2_PC']['normal_mean_ms'],
                               service['B3_SOLO_EFT_PC']['normal_mean_ms'])
            with (output / 'service_cases.csv').open(encoding='utf-8', newline='') as stream:
                cases = list(csv.DictReader(stream))
            self.assertEqual(len(cases), 135)
            self.assertTrue(all(r['energy_j'] == '' and r['ap_peak_c'] == '' for r in cases))
            with self.assertRaises(FileExistsError):
                choice.evaluate(output)
        self.assertEqual(choice.digest(choice.BUNDLE / 'service_metrics.csv'), source_sha)

    def test_misses_are_counted_over_all_planned_requests(self):
        row = dict(scenario='queue', realized='1.5', seed='201', policy='B2_PC',
                   planned='24', urgent_planned='6', normal_planned='18',
                   unfinished='2', urgent_p95_ms='400', normal_mean_ms='4100',
                   urgent_not_timely_rate=str(1/6), normal_not_timely_rate=str(3/18))
        result = choice.service_row(row)
        self.assertEqual((result['urgent_not_timely'], result['normal_not_timely'],
                          result['timely_all_planned']), (1, 3, 20))
        row['unfinished'] = '5'
        with self.assertRaises(ValueError):
            choice.service_row(row)
        row['unfinished'] = '2'
        row['normal_not_timely_rate'] = '0.2'
        with self.assertRaises(ValueError):
            choice.service_row(row)


if __name__ == '__main__':
    unittest.main()
