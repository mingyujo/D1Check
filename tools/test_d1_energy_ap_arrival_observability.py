import csv
import json
import tempfile
import unittest
from pathlib import Path

from tools import d1_energy_ap_arrival_observability as audit
from tools.d1_energy_ap_regimen_transition import write_dashboard


class ArrivalObservabilityTest(unittest.TestCase):
    def test_stored_schedule_matches_existing_cpu_ledger(self):
        rows, meta = audit.audit(audit.SOURCE)
        self.assertFalse(meta['supported_model_prediction'])
        got = {r['state']: r['total_s'] for r in rows
               if r['policy'] == 'CPU_URGENT' and r['clock'] == 'lane'}
        source = Path('docs/results/arrival_policy_screen_01/repro_bundle/occupancy_segments.csv')
        with source.open(encoding='utf-8-sig', newline='') as f:
            ledger = [r for r in csv.DictReader(f) if r['scenario'] == 'queue' and
                      r['seed'] == '201' and r['realized'] == '1.0' and r['policy'] == 'CPU_URGENT']
        for state, seconds in got.items():
            self.assertAlmostEqual(seconds, sum(float(r['end_s']) - float(r['start_s'])
                                                for r in ledger if r['state'] == state), places=6)
        self.assertNotIn('classification:CPU+detection:GPU',
                         {r['state'] for r in rows if r['policy'] == 'FIXED_SPLIT'})

    def test_overlap_and_gap_partition(self):
        rows = [dict(id='1', task='classification', backend='CPU',
                     dispatch_ns='100000000', lane_available_ns='600000000'),
                dict(id='2', task='detection', backend='GPU',
                     dispatch_ns='200000000', lane_available_ns='700000000')]
        parts = audit.segments(rows, 'dispatch_ns', 'lane_available_ns')
        self.assertEqual(sum(p['end_ns']-p['start_ns'] for p in parts), audit.HORIZON_NS)
        pair = [p for p in parts if '+' in p['state']]
        self.assertEqual(len(pair), 1)
        self.assertEqual(pair[0]['end_ns']-pair[0]['start_ns'], 400000000)
        report = audit.aggregate(parts, 'FIXED_SPLIT', 'lane')
        self.assertEqual(next(r for r in report if '+' in r['state'])['at_least_2_power_periods'], 0)

    def test_invalid_occupancy_rejected(self):
        rows = [dict(id='1', task='classification', backend='CPU',
                     dispatch_ns='100000000', lane_available_ns='600000000'),
                dict(id='2', task='detection', backend='CPU',
                     dispatch_ns='200000000', lane_available_ns='700000000')]
        with self.assertRaisesRegex(ValueError, 'same backend'):
            audit.segments(rows, 'dispatch_ns', 'lane_available_ns')

    def test_dashboard_only_links_generated_audit(self):
        original = Path('docs/results/energy_ap_transition_01')
        summary = json.loads((original/'summary.json').read_text(encoding='utf-8'))
        with (original/'blocks.csv').open(encoding='utf-8', newline='') as f:
            blocks = list(csv.DictReader(f))
        for row in blocks:
            for key in ('duration_s', 'observed_energy_j', 'predicted_energy_j',
                        'signed_energy_error_j', 'ap_mae_c'):
                row[key] = float(row[key])
        with tempfile.TemporaryDirectory() as temp:
            dest = Path(temp)
            write_dashboard(dest, summary, blocks)
            self.assertNotIn('short_transition_occupancy.svg', (dest/'dashboard.html').read_text(encoding='utf-8'))
            (dest/'short_transition_occupancy.svg').write_text('<svg/>', encoding='utf-8')
            write_dashboard(dest, summary, blocks)
            self.assertIn('short_transition_occupancy.svg', (dest/'dashboard.html').read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
