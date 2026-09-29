import tempfile
import unittest
from pathlib import Path

from tools import d1_arrival_measured_support as audit


class MeasuredSupportAuditTest(unittest.TestCase):
    def test_exact_state_mapping_does_not_merge_joint_tasks(self):
        self.assertEqual(audit.measured_state('idle'), 'resident_idle')
        self.assertEqual(audit.measured_state('classification:GPU+detection:CPU'),
                         'classification_GPU+detection_CPU')
        self.assertEqual(audit.measured_state('classification:CPU+classification:GPU'),
                         'classification_CPU+classification_GPU')

    def test_saved_schedule_is_partitioned_and_never_becomes_measured_cost(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            (output / 'frozen_support.json').write_bytes((audit.OUTPUT / 'frozen_support.json').read_bytes())
            result = audit.generate(audit.BUNDLE, output)
            self.assertEqual(result['case_count'], 135)
            self.assertEqual(result['complete_measured_energy_ap_cases'], 0)
            self.assertEqual(result['missing_state_cases'], 9)
            self.assertIsNone(result['numerical_energy_j'])
            self.assertIsNone(result['numerical_ap_c'])
            rows = audit.read_csv(output / 'support_status.csv')
            self.assertEqual(len(rows), 135)
            self.assertEqual({x['energy'] for x in rows}, {'UNSUPPORTED_ARRIVAL_STATE_TRANSITIONS'})
            self.assertEqual({x['ap'] for x in rows}, {'UNSUPPORTED_INITIAL_AP_AND_ARRIVAL_TRANSITIONS'})
            first = audit.read_csv(output / 'first_blockers.csv')
            self.assertEqual(len(first), 270)
            self.assertEqual({x['first_blocker_s'] for x in first}, {'0'})
            self.assertTrue(all(float(x['first_concrete_transition_s']) > 0 for x in first))
            blockers = audit.read_csv(output / 'all_blockers.csv')
            self.assertEqual(len(blockers), 6759)
            self.assertEqual(sum(x['rule']=='STATE_COEFFICIENT_ABSENT' for x in blockers), 9)
            self.assertIn('<svg', (output / 'representative_schedule.svg').read_text(encoding='utf-8'))

    def test_gap_and_overlap_are_not_silently_charged_as_idle(self):
        good = [dict(start_s='0', end_s='5'), dict(start_s='5', end_s='120')]
        audit.verify_partition(good)
        for second in ('4.9', '5.1'):
            bad = [dict(start_s='0', end_s='5'), dict(start_s=second, end_s='120')]
            with self.assertRaises(ValueError):
                audit.verify_partition(bad)

    def test_frozen_byte_mismatch_and_bundle_hash_mismatch_fail(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            bad = folder / 'frozen.json'
            bad.write_text('{}', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'frozen byte SHA changed'):
                audit.generate(audit.BUNDLE, folder / 'out', bad)
            bundle = folder / 'bundle'
            bundle.mkdir()
            for name in ('SOURCE_HASHES.json','occupancy_segments.csv','service_metrics.csv','assumptions.json'):
                (bundle / name).write_bytes((audit.BUNDLE / name).read_bytes())
            (bundle / 'occupancy_segments.csv').write_text('corrupt', encoding='utf-8')
            output = folder / 'out'
            output.mkdir(exist_ok=True)
            (output / 'frozen_support.json').write_bytes((audit.OUTPUT / 'frozen_support.json').read_bytes())
            with self.assertRaisesRegex(ValueError, 'source hash mismatch'):
                audit.generate(bundle, output)


if __name__ == '__main__':
    unittest.main()
