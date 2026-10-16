"""Numerical necessary-bound checks; no new policy/device performance evidence."""
import copy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import numpy as np
from tools import d1_method_joint_bound as b


class JointBoundTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.frozen, cls.initial = b.P.inputs(b.P.BUNDLE)
        cls.records = b.work.budget.readout.source.records(b.work.budget.ROOT/'run_v1/records.jsonl.gz')
        cls.ref = next(r for r in cls.records if r['meta']['stage'] == b.work.budget.STAGE and
                       r['meta']['envelope'] == 'g0.45_c0.5_b4' and r['meta']['scenario'] == 'mean' and
                       r['meta']['policy'] == 'EFT_REFERENCE')

    def test_relaxation_upper_exceeds_known_positive_input_distribution(self):
        q = b.Q; beta = .05; gain = 1.1
        baseline = 29.-.6*np.exp(-.1*(q-35))
        amounts = np.array([.25, .6, .3]); times = np.array([35.25, 42.7, 49.1])
        values = baseline+gain*np.sum(amounts[None, :]*np.exp(-beta*np.maximum(q[:, None]-times[None, :], 0))*(q[:, None]>times[None, :]), axis=1)
        area = float(b.WEIGHTS@np.maximum(values-29., 0))
        result = b.heat_capacity(baseline, 29., beta, gain, 50., area, float(max(values)))
        self.assertGreaterEqual(result['heat_upper_c'], float(sum(amounts)))
        self.assertGreaterEqual(result['dual_min_slack'], -1e-8)
        self.assertGreaterEqual(result['primal_dual_gap_c'], -1e-8)
        self.assertFalse(result['realizable_schedule'])

    def test_extra_peak_constraint_cannot_increase_tight_bound(self):
        base = np.zeros(len(b.Q))
        area = b.heat_capacity(base, 0., .05, 1., 50., 20.)
        peak = b.heat_capacity(base, 0., .05, 1., 50., 20., .15)
        self.assertLessEqual(peak['heat_upper_c'], area['heat_upper_c']+1e-5)

    def test_changed_model_and_invalid_ap_inputs_rejected(self):
        changed = copy.deepcopy(self.frozen); changed['ap']['g'] = .1
        with self.assertRaisesRegex(ValueError, 'g=0'): b.identity(changed, 'mean')
        for args in ((0., 1., 50., 20.), (.05, 0., 50., 20.), (.05, 1., 181., 20.), (.05, 1., 50., float('nan'))):
            with self.subTest(args=args), self.assertRaises(ValueError):
                b.heat_capacity(np.zeros(len(b.Q)), 0., *args)

    def test_failed_reference_not_hidden_or_used_for_cost_claim(self):
        failed = next(r for r in self.records if r['meta']['stage'] == b.work.budget.STAGE and
                      r['meta']['policy'] == 'EFT_REFERENCE' and r['meta']['deadline_met'] < 48)
        with patch.object(b, 'heat_capacity', side_effect=AssertionError('no optimization for failed service')):
            result = b.case_bound(failed, self.frozen, self.initial['initial'])
        self.assertTrue(result['skipped']); self.assertIsNone(result['energy_gain_upper_j'])

    def test_whole_phase_context_and_actual_release_required(self):
        changed = copy.deepcopy(self.ref)
        changed['ledger'][0]['worker_release_ns'] += 100
        with self.assertRaises(ValueError): b.case_bound(changed, self.frozen, self.initial['initial'])

    def test_stored_reference_in_relaxation_is_not_feasibility_proof(self):
        result = b.case_bound(self.ref, self.frozen, self.initial['initial'])
        self.assertGreaterEqual(result['energy_gain_upper_j'], -1e-6)
        self.assertLess(result['energy_gain_upper_j'], .18)
        self.assertFalse(result['joint_gain_proven_possible'])
        self.assertFalse(result['impossibility_ruled_out'])
        self.assertGreaterEqual(result['latest_lane_bound_s'], max(r['lane_available_ns']/1e9 for r in self.ref['ledger']))

    def test_actual_saved_reference_drive_fits_relaxed_capacity(self):
        result = b.case_bound(self.ref, self.frozen, self.initial['initial'])
        _, _, drive, _, _ = b.identity(self.frozen, self.ref['meta']['scenario'])
        total = sum((s['end_s']-s['start_s'])*drive[s['state']]
                    for s in self.ref['segments'] if s['state'] != 'idle')
        self.assertGreaterEqual(result['heat_upper_c'], total)

    def test_solver_noncompletion_remains_unknown(self):
        from types import SimpleNamespace
        with patch.object(b, 'linprog', return_value=SimpleNamespace(success=False, status=1, message='time limit')):
            result = b.heat_capacity(np.zeros(len(b.Q)), 0., .05, 1., 50., 20.)
        self.assertEqual(result['status'], 'unresolved'); self.assertIsNone(result['heat_upper_c'])

    def test_real_analysis_no_simulate_and_preserves_all_cases_and_hashes(self):
        before = b.work.verify_resources()
        with TemporaryDirectory() as tmp, patch.object(b.work.budget.readout.source.f.x.old.engine, 'simulate',
                side_effect=AssertionError('new simulation forbidden')):
            out = Path(tmp)/'bound'; rows = b.run(out)
            self.assertEqual(len(rows), 24)
            self.assertEqual(sum(r['modeled_joint_saving_upper_j'] is None for r in rows), 6)
            result = json.loads((out/'result.json').read_text(encoding='utf8'))
            self.assertFalse(result['physical_advantage_proven'])
            before_bytes = (out/'result.json').read_bytes()
            with self.assertRaises(FileExistsError): b.run(out)
            self.assertEqual(before_bytes, (out/'result.json').read_bytes())
        self.assertEqual(b.work.verify_resources(), before)


if __name__ == '__main__': unittest.main()
