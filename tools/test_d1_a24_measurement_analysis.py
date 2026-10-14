import unittest
from d1_a24_measurement_analysis import integrate_window,decoded_match,NS

class AnalysisTests(unittest.TestCase):
    def test_bracketed_linear_boundaries_and_actual_elapsed_time(self):
        r=integrate_window([(0,0),(2*NS,4),(5*NS,10)],NS,4*NS,3*NS)
        self.assertAlmostEqual(r['integral'],15)
        self.assertEqual(r['maximum_observed_gap_ns'],3*NS)
    def test_missing_tail_and_large_gap_do_not_make_cost(self):
        self.assertIsNone(integrate_window([(0,2),(NS,2)],0,2*NS,NS)['integral'])
        self.assertIsNone(integrate_window([(0,2),(3*NS,2)],0,2*NS,NS)['integral'])
    def test_output_difference_cannot_pass_by_dropping_label_or_box(self):
        ref={'results':[{'label':'person','score':.7,'box':[1,2,3,4]}]}
        self.assertEqual(decoded_match(ref,ref)['status'],'DECODED_OUTPUT_MATCH')
        self.assertEqual(decoded_match({'results':[{'label':'dog','score':.7,'box':[1,2,3,4]}]},ref)['status'],'LABEL_OR_ORDER_MISMATCH')
        self.assertEqual(decoded_match({'results':[{'label':'person','score':.7,'box':[5,2,3,4]}]},ref)['status'],'DECODED_TOLERANCE_FAILED')

if __name__=='__main__':unittest.main()
