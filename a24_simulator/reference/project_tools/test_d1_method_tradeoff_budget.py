import copy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from tools import d1_method_tradeoff_budget as b


class TradeoffBudgetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.records = b.readout.source.records(b.ROOT/'run_v1/records.jsonl.gz')

    def summarize(self, records=None):
        return b.summarize(self.records if records is None else records, 'run_v1')

    def test_energy_budget_is_minimum_same_case_gain_not_mean(self):
        groups, cases = self.summarize()
        group = next(z for z in groups if z['envelope'] == 'g0.45_c0.5_b4' and z['policy'] == 'CPU_BOTTLENECK_GUARD_V1')
        local = [z for z in cases if z['envelope'] == group['envelope'] and z['policy'] == group['policy']]
        self.assertEqual(len(local), 6)
        self.assertEqual(group['minimum_saved_energy_budget_j'], min(-z['delta_energy_j'] for z in local))
        self.assertAlmostEqual(group['minimum_saved_energy_budget_j'], .43042088716188687)
        self.assertAlmostEqual(group['maximum_required_peak_AP_cap_c'], .2910825998987505)
        self.assertFalse(group['joint_modeled_improvement'])

    def test_infeasible_burst_has_no_feasible_saving_budget(self):
        groups, cases = self.summarize()
        for group in groups:
            if group['envelope'] == 'g0.15_c0.5_b8':
                self.assertFalse(group['paired_full_service'])
                self.assertIsNone(group['minimum_saved_energy_budget_j'])
        for case in cases:
            if case['envelope'] == 'g0.15_c0.5_b8':
                self.assertIsNone(case['strict_energy_gain_requires_unknown_delta_j_below'])

    def test_saved_zero_reference_timing_is_unknown_not_measurement(self):
        _, cases = self.summarize()
        for case in cases:
            self.assertIsNone(case['unknown_device_controller_delta_j'])
            self.assertIsNone(case['safe_global_extra_delay_ms'])
            self.assertIsNone(case['future_accuracy_margin_j'])
            if case['policy'] == 'EFT_REFERENCE':
                self.assertIsNone(case['recorded_candidate_PC_callback_total_s'])
                self.assertFalse(case['reference_PC_callback_measured'])

    def test_missing_metrics_cannot_become_zero_or_energy_budget(self):
        bad = copy.deepcopy(self.records)
        row = next(z for z in bad if z['meta']['stage'] == b.STAGE and z['meta']['envelope'] == 'g0.45_c0.5_b4' and
                   z['meta']['policy'] == 'EFT_REFERENCE')
        row['meta']['energy_j'] = None
        groups, cases = self.summarize(bad)
        for group in groups:
            if group['envelope'] == row['meta']['envelope']:
                self.assertIsNone(group['minimum_saved_energy_budget_j'])
                self.assertFalse(group['paired_full_service'])

    def test_summary_corruption_and_response_boundary_rejected(self):
        bad = copy.deepcopy(self.records)
        row = next(z for z in bad if z['meta']['stage'] == b.STAGE)
        row['meta']['deadline_met'] -= 1
        with self.assertRaises(ValueError): self.summarize(bad)
        bad = copy.deepcopy(self.records)
        row = next(z for z in bad if z['meta']['stage'] == b.STAGE)
        row['ledger'][0]['response_ns'] += 1
        with self.assertRaises(ValueError): self.summarize(bad)

    def test_moved_arrival_or_partial_block_rejected(self):
        bad = copy.deepcopy(self.records)
        row = next(z for z in bad if z['meta']['stage'] == b.STAGE and z['meta']['policy'] == 'ATC_QUEUED_GUARD_V1')
        row['ledger'][0]['arrival_ns'] += 1
        with self.assertRaises(ValueError): self.summarize(bad)
        with self.assertRaises(ValueError): self.summarize(self.records[:-1])

    def test_equal_metrics_has_no_positive_energy_budget(self):
        groups, _ = self.summarize()
        group = next(z for z in groups if z['envelope'] == 'g0.45_c0.75_b4' and z['policy'] == 'ATC_QUEUED_GUARD_V1')
        self.assertTrue(group['equivalent_to_reference'])
        self.assertIsNone(group['minimum_saved_energy_budget_j'])
        self.assertFalse(group['joint_modeled_improvement'])

    def test_actual_readout_and_save_never_simulate(self):
        with patch.object(b.readout.source.f.x.old.engine, 'simulate', side_effect=AssertionError('simulation forbidden')):
            result = b.analyze()
            with TemporaryDirectory() as directory:
                output = Path(directory)/'readout'
                b.save(result, output)
                loaded = json.loads((output/'result.json').read_text(encoding='utf8'))
                self.assertEqual(len(loaded['groups']), 28)
                self.assertEqual(len(loaded['cases']), 168)
                self.assertEqual(loaded['new_simulations'], 0)
                self.assertIsNone(loaded['accuracy_pass'])
                self.assertEqual(b.readout.source.f.x.p.digest(b.readout.source.f.x.p.BUNDLE/'model.json'), b.readout.source.f.x.p.MODEL_SHA)


if __name__ == '__main__': unittest.main()
