import copy
import hashlib
import unittest

from tools import d1_history_policy_readout as readout


class PolicyReadoutTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pairs, cls.groups, cls.errors, cls.summary = readout.analyze()

    def test_complete_saved_denominators(self):
        self.assertEqual(len(self.pairs), 1920)
        self.assertEqual(self.summary['policy_rows_reused'], 2112)
        self.assertEqual(sum(x['eligible_pairs']+x['ineligible_pairs'] for x in self.groups
                             if x['scope']=='all_conditions'), 1920)

    def test_service_failure_cannot_be_joint_gain(self):
        row = dict(cost_eligible='True', service_preserved='False', delta_energy_j='-50', delta_peak_ap_c='-3')
        self.assertEqual(readout.classify(row), 'service_not_preserved')
        row['cost_eligible']='False'
        self.assertEqual(readout.classify(row), 'cost_or_full_work_ineligible')

    def test_missing_and_nonfinite_are_not_zero(self):
        for value in ('', 'nan', 'inf'):
            with self.assertRaises(ValueError):
                readout.number({'J':value}, 'J')
        with self.assertRaises(ValueError):
            readout.boolean({'pass':''}, 'pass')

    def test_exact_saved_primary_comparison(self):
        row = next(x for x in self.groups if x['scope']=='primary_low_sustained' and
                   x['baseline']=='TRITON_RATE_OFF_FIXED_REQUEST_ADAPT_V1')
        self.assertEqual(row['comparisons'],96)
        self.assertEqual(row['joint_model_gain_pairs'],96)
        self.assertAlmostEqual(row['delta_energy_mean_j'], -.790013531, places=8)
        band = next(x for x in self.groups if x['scope']=='primary_low_sustained' and
                    x['baseline']=='BAND_HEFT_WHOLE_REQUEST_ADAPT_V1')
        self.assertEqual(band['joint_model_gain_pairs'],0)
        self.assertGreater(band['delta_energy_mean_j'],0)

    def test_differential_error_and_peak_metric(self):
        metrics=readout.csv_rows(readout.ROOT/(readout.HISTORY+'metrics.csv'))
        for row in self.errors:
            self.assertAlmostEqual(row['predicted_par_minus_cpu_j']-row['observed_par_minus_cpu_j'],
                                   row['signed_contrast_error_j'],places=9)
            pair={x['policy']:x for x in metrics if x['role']==row['role'] and
                  int(x['gap'])==row['gap_s'] and x['model']=='frozen'}
            expected=float(pair['B2_PARALLEL_ONLINE_V1']['peak_signed_error_c'])-float(pair['CPU_URGENT_ONLINE_V1']['peak_signed_error_c'])
            self.assertEqual(row['signed_peak_contrast_error_c'],expected)
        altered=copy.deepcopy(metrics)
        altered[0]['signed_j']='999'
        # Change a contrast constituent; C0 is not used in the CPU/PAR difference.
        next(x for x in altered if x['condition']=='confirmation_30_CPU' and x['model']=='frozen')['signed_j']='999'
        with self.assertRaises(ValueError):
            readout.contrasts(altered,readout.csv_rows(readout.ROOT/(readout.HISTORY+'contrast_diagnostic.csv')))

    def test_no_universal_claim_or_model_change(self):
        for key in ('physical_policy_winner','large_effect_threshold','confidence_interval'):
            self.assertIsNone(self.summary[key])
        self.assertEqual(self.summary['new_simulations'],0)
        self.assertEqual(self.summary['device_commands'],0)
        self.assertEqual(hashlib.sha256((readout.ROOT/readout.MODEL).read_bytes()).hexdigest(),readout.MODEL_SHA)
        self.assertTrue(all(x['independent_phone_policy_gain']=='unverified' for x in self.pairs))


if __name__=='__main__':
    unittest.main()
