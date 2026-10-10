"""Relevant causal clock, phase ledger, training split and opt-in boundaries."""
import copy
import math
import unittest
from tools import d1_recovery_service as s


class RecoveryServiceTest(unittest.TestCase):
    def test_five_phase_and_invocation_are_distinct_and_conserved(self):
        row = dict(zip(s.FIELDS, (10, 20, 100, 120, 130, 150)))
        row.update(host_inference_start_ns=40, host_inference_return_ns=90,
                   task_id='classification', scheduled_arrival_ns=0)
        v = s.phase_values(row)
        self.assertAlmostEqual(sum(v[k] for k in s.PHASES), v['lane_total'])
        self.assertNotEqual(v['invocation'], v['execution_to_output'])
        row['worker_release_ns'] = 151
        with self.assertRaisesRegex(ValueError, 'reversed'):
            s.phase_values(row)

    def test_query_return_causality_age_and_missing(self):
        raw = [dict(before_ns=0, mono_ns=5, after_ns=11, ap=30),
               dict(before_ns=6, mono_ns=8, after_ns=21, ap=31)]
        self.assertEqual(s.prior_ap(raw, 20)['ap'], 30)
        self.assertIsNone(s.prior_ap(raw, 10))
        self.assertIsNone(s.prior_ap(raw, 21+10_000_000_001))
        self.assertEqual(s.prior_ap(raw[:1], 11+10_000_000_000)['ap'], 30)

    def test_union_overlap_does_not_double_count_peers(self):
        self.assertAlmostEqual(s.union_overlap(0, 10, [(1, 5), (3, 9)]), .8)
        self.assertEqual(s.union_overlap(0, 10, [(10, 20)]), 0)

    def fixture(self):
        rows = []
        for gap, ap, phase in ((30, 32, 110), (180, 30, 90)):
            rows.append(dict(session='development_'+str(gap), role='development', stage='target', policy='CPU',
                             cell='classification_CPU', gap_s=gap, pre_target_ap_c=ap, n=1 if gap==30 else 999,
                             **dict(zip(s.PHASES, (1, phase, 3, 4, 5)))))
        return rows

    def test_confirmation_never_changes_fit_and_sessions_equal_weight(self):
        rows = self.fixture(); model = s.fit_candidate(rows)
        extra = dict(rows[0], role='confirmation', execution_to_output=99999, pre_target_ap_c=99)
        self.assertEqual(model, s.fit_candidate(rows+[extra]))
        h = model['heads']['CPU|classification_CPU']
        self.assertEqual(h['fixed_phases_ms'][1], 100)
        self.assertAlmostEqual(h['gain_per_c'], math.log(110/90)/2)
        with self.assertRaisesRegex(ValueError, 'both registered'):
            s.fit_candidate(rows[:1])

    def test_predict_preserves_other_phases_and_requires_extrapolation_opt_in(self):
        model = s.fit_candidate(self.fixture())
        a = s.predict(model, 'CPU', 'classification_CPU', 30)
        b = s.predict(model, 'CPU', 'classification_CPU', 32)
        self.assertLess(a['phases_ms'][1], b['phases_ms'][1])
        self.assertEqual(a['phases_ms'][2:], b['phases_ms'][2:])
        self.assertFalse(a['supported'])
        self.assertIsNone(s.predict(model, 'CPU', 'classification_CPU', 29)['phases_ms'])
        self.assertTrue(s.predict(model, 'CPU', 'classification_CPU', 29, diagnostic_extrapolation=True)['diagnostic_extrapolation'])
        self.assertIsNone(s.predict(model, 'CPU', 'detection_GPU', 31)['phases_ms'])
        with self.assertRaisesRegex(ValueError, 'invalid'):
            s.predict(model, 'CPU', 'classification_CPU', float('nan'))

    def test_negative_and_unidentified_gains_not_invented(self):
        rows = self.fixture(); rows[0]['execution_to_output'] = 70
        self.assertEqual(s.fit_candidate(rows)['heads']['CPU|classification_CPU']['gain_per_c'], 0)
        rows[0]['pre_target_ap_c'] = 30
        model = s.fit_candidate(rows)
        self.assertIsNone(model['heads']['CPU|classification_CPU']['gain_per_c'])
        self.assertIsNone(s.predict(model, 'CPU', 'classification_CPU', 30)['phases_ms'])

    def test_ordinal_pair_requires_whole_denominator(self):
        data = dict(requests=[dict(role='development', policy='CPU', stage='target', task='classification',
                                  backend='CPU', gap_s=30, ordinal=0)])
        with self.assertRaisesRegex(ValueError, 'lost denominator'):
            s.ordinal_contrasts(data)


if __name__ == '__main__':
    unittest.main()
