import unittest
from d1_a24_partial_confirm_publication import screen,require_first_quartet


class ThermalEligibilityCases(unittest.TestCase):
    def test_partial_view_cannot_silently_mislabel_a_full_or_other_visit(self):
        good=[{'block':'b','recipe':'M128','arm':a} for a in ['BASE','ORDER','PAIR_G','WAIT200']]
        require_first_quartet(good)
        for bad in [good[:3],good*2,[dict(r,recipe='L64') for r in good]]:
            with self.assertRaises(AssertionError):require_first_quartet(bad)

    def test_incomplete_baseline_never_enters_thermal_difference_but_service_stays(self):
        sessions=[{'block':'b','recipe':'M128','arm':arm,'thermal_window_status':status,'mean_AP_c':mean,'observed_peak_AP_c':peak} for arm,status,mean,peak in [('BASE','GAP_OR_DUPLICATE_TIMESTAMP',None,29),('PAIR_G','READOUT_WINDOW_COVERED',28,29.7)]]
        pairs=[{'comparison':'혼합 병행','block':'b','delta_mean_AP_c':None,'delta_observed_peak_AP_c':.7,'delta_completed':0}]
        intervals=[{'comparison':'혼합 병행','metric':'delta_observed_peak_AP_c','n_independent_blocks':1,'mean':.7}]
        ss,pp,ii=screen(sessions,pairs,intervals)
        self.assertFalse(ss[0]['AP_comparison_eligible']);self.assertIsNone(ss[0]['primary_AP_observed_peak_c'])
        self.assertEqual(ss[0]['observed_peak_AP_c'],29)
        self.assertFalse(pp[0]['thermal_comparison_eligible']);self.assertIsNone(pp[0]['delta_observed_peak_AP_c']);self.assertEqual(pp[0]['delta_completed'],0)
        self.assertEqual(ii[0]['n_independent_blocks'],0);self.assertIsNone(ii[0]['mean'])
        self.assertEqual(pairs[0]['delta_observed_peak_AP_c'],.7,'original engine export must remain unchanged')

    def test_both_covered_keeps_one_pair_without_inventing_CI(self):
        sessions=[{'block':'b','recipe':'M128','arm':a,'thermal_window_status':'READOUT_WINDOW_COVERED','mean_AP_c':28,'observed_peak_AP_c':29} for a in ['BASE','PAIR_G']]
        _,p,i=screen(sessions,[{'comparison':'혼합 병행','block':'b','delta_mean_AP_c':0,'delta_observed_peak_AP_c':0}], [{'comparison':'혼합 병행','metric':'delta_mean_AP_c'}])
        self.assertTrue(p[0]['thermal_comparison_eligible']);self.assertEqual(i[0]['n_independent_blocks'],1);self.assertIsNone(i[0]['lower95'])


if __name__=='__main__':unittest.main()
