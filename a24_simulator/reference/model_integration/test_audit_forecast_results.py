"""Saved-auditor boundary fixtures, no real archive/model/simulation."""
import unittest
import audit_forecast_results as subject

class SavedAuditTests(unittest.TestCase):
    def test_terminal_counts_cannot_hide_duplicate_and_missing_failed_identity(self):
        starts=[{'identity':'a'},{'identity':'b'}]
        with self.assertRaises(RuntimeError):subject.terminal_bijection(starts,[{'identity':'a'},{'identity':'a'}])
        subject.terminal_bijection(starts,[{'identity':'b'},{'identity':'a'}])

    def test_unavailable_AP_is_retained_as_unknown_with_no_fake_numbers(self):
        ap={'status':'UNKNOWN','reason':'model unavailable or solver did not converge','model_sha256':None,'ap_c':[None],'t_s':[0.]}
        subject.unavailable_ap_guard(ap,{})
        with self.assertRaises(RuntimeError):subject.unavailable_ap_guard(ap,{'AP_peak_c':0.})
        with self.assertRaises(RuntimeError):subject.unavailable_ap_guard(dict(ap,ap_c=[30.]),{})

    def test_incomplete_requested_P95_and_tardiness_remain_lower_bounds(self):
        rows=[{'request_id':'a','scheduled_arrival_ns':0,'deadline_ns':1,'response_ns':2},
              {'request_id':'b','scheduled_arrival_ns':0,'deadline_ns':1,'response_ns':None}]
        result=subject.summary(rows,10)
        self.assertIsNone(result['P95_all_requested_response_s'])
        self.assertEqual(result['P95_all_requested_response_lower_bound_s'],10/subject.NS)
        self.assertIsNone(result['total_tardiness_s'])
        self.assertEqual(result['uncompleted'],1)
        self.assertEqual(result['on_time'],0)

    def test_halfopen_release_and_next_owner_is_not_overlap(self):
        owners=[{'start_s':0,'end_s':1,'task':'D','route':'CPU'},
                {'start_s':1,'end_s':2,'task':'C','route':'CPU'}]
        self.assertEqual(subject.check_owners(owners),0)

    def test_illegal_same_lane_or_third_owner_fails(self):
        for owners in ([{'start_s':0,'end_s':1,'task':'D','route':'CPU'},
                        {'start_s':0,'end_s':1,'task':'C','route':'CPU'}],
                       [{'start_s':0,'end_s':1,'task':'D','route':'CPU'},
                        {'start_s':0,'end_s':1,'task':'C','route':'GPU'},
                        {'start_s':0,'end_s':1,'task':'C','route':'GPU'}]):
            with self.assertRaises(RuntimeError):subject.check_owners(owners)

    def test_only_qualified_pair_and_real_overlap_area(self):
        owners=[{'start_s':0,'end_s':2,'task':'D','route':'CPU'},
                {'start_s':1,'end_s':3,'task':'C','route':'GPU'}]
        self.assertEqual(subject.check_owners(owners),1)

    def test_energy_keeps_baseline_and_requires_window_coverage(self):
        profile={'measured35':{'baseline_w':2},'cost_anchor':{'energy_increment_w':dict(zip(subject.STATES,[3,4,5,8]))}}
        activity={'activity_coverage_s':[0,10],'observation_window_s':[0,10],
                  'owner_intervals':[{'start_s':1,'end_s':3,'task':'C','route':'GPU'}]}
        self.assertEqual(subject.energy(activity,profile,[0,10]),30)
        self.assertIsNone(subject.energy(activity,profile,[0,11]))

    def test_owner_censoring_clips_to_forecast_without_inventing_AVAILABLE(self):
        rows=[{'request_id':'x','dispatch_ns':1*subject.NS,'available_ns':None,'task':'C','route':'GPU'}]
        owners=subject.expected_owners({'observation_end_ns':3*subject.NS},rows)
        self.assertEqual(owners[0]['end_s'],3)
        self.assertTrue(owners[0]['end_is_censored_forecast_window'])
        self.assertIsNone(rows[0]['available_ns'])

    def test_bad_numeric_or_changed_null_rejected(self):
        for a,b in ((1,2),(None,0),(True,1),(float('nan'),float('nan'))):
            with self.assertRaises(RuntimeError):subject.tree_equal(a,b,'fixture')

if __name__=='__main__':unittest.main()
