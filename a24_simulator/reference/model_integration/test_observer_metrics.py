import unittest

from analysis_metrics import ap_window, request_metrics, saved_schedule_description
from historical_observer import conditional_energy, observe_ap
from archive_index import safe_info
import zipfile


class ObserverAndCoverageTests(unittest.TestCase):
    def test_original_zip_name_before_normalization(self):
        info = zipfile.ZipInfo('a/b')
        info.orig_filename = 'a\\b'
        with self.assertRaisesRegex(ValueError,'Normalized'):
            safe_info(info)

    def test_zip_traversal(self):
        with self.assertRaisesRegex(ValueError,'traversal'):
            safe_info(zipfile.ZipInfo('../a'))
    def test_missing_requests_remain_in_denominator(self):
        result = request_metrics([{'priority':'U','scheduled_arrival_s':0,'deadline_s':1,'response_s':.5},
                                  {'priority':'U','scheduled_arrival_s':0,'deadline_s':1}])
        self.assertEqual(result['ALL']['planned'], 2)
        self.assertEqual(result['ALL']['incomplete'], 1)
        self.assertEqual(result['ALL']['service_fraction'], .5)
        self.assertIsNone(result['N']['service_fraction'])

    def test_future_ap_cannot_fill_window_start(self):
        result = ap_window([{'t_s':36.,'ap_c':30.},{'t_s':180.,'ap_c':30.}])
        self.assertIsNone(result['mean_C'])

    def test_ap_long_gap_is_unknown(self):
        result = ap_window([{'t_s':t,'ap_c':30.} for t in (35,40,80,180)])
        self.assertEqual(result['status'], 'UNKNOWN_INTERNAL_GAP')

    def test_known_constant_temperature_window(self):
        result = ap_window([{'t_s':t,'ap_c':31.} for t in range(30,181,5)])
        self.assertEqual(result['mean_C'], 31.)

    def test_conditional_energy_independent_arithmetic(self):
        session = {'observation_window_s':[0,180], 'owner_intervals':[
            {'start_s':0.,'end_s':10.,'task':'C','route':'GPU'},
            {'start_s':5.,'end_s':15.,'task':'D','route':'CPU'}]}
        profile = {'measured35':{'baseline_w':1.}, 'cost_anchor':{'energy_increment_w':{
            'classification_CPU':.6,'classification_GPU':.4,'detection_CPU':.7,
            'classification_GPU+detection_CPU':.8}}}
        result = conditional_energy(session,profile)
        self.assertAlmostEqual(result['historical_conditional_J'], 189.5)
        self.assertIsNone(result['measured_J'])

    def test_unobserved_tail_is_not_filled(self):
        result = conditional_energy({'observation_window_s':[0,120]}, {})
        self.assertIsNone(result['historical_conditional_J'])

    def test_two_cpu_owners_rejected(self):
        session = {'observation_window_s':[0,180], 'owner_intervals':[
            {'start_s':0.,'end_s':1.,'task':'C','route':'CPU'},
            {'start_s':0.,'end_s':1.,'task':'D','route':'CPU'}]}
        with self.assertRaisesRegex(ValueError,'Unsupported'):
            conditional_energy(session, {})

    def test_missing_pre_brackets_not_fabricated(self):
        session = {'observations':[{'t_s':-35.+i*5.,'ap_c':30.} for i in range(8)]}
        result = observe_ap(session,{})
        self.assertEqual(result['status'],'UNKNOWN_REAL_PRECOMMON_CLOCK_BRACKETS')


if __name__ == '__main__':
    unittest.main()
