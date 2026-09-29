import unittest

from tools import d1_arrival_recorded_b2_residual as residual


class RecordedB2ResidualTest(unittest.TestCase):
    def setUp(self):
        self.frozen = dict(ap_cooling_rate_per_s=.1,
                           ap_slope_at_30_c_per_s=dict(resident_idle=.2,detection_CPU=.4),
                           whole_device_power_w=dict(resident_idle=1.,detection_CPU=2.))

    def test_candidate_is_continuous_and_idle_returns_to_initial_reference(self):
        segments = [dict(start_s=0.,end_s=1.,state='detection:CPU'),
                    dict(start_s=1.,end_s=3.,state='idle')]
        result = residual.candidate_path(segments,self.frozen,10.,[0.,1.,2.,3.])
        expected = 12.-2.*__import__('math').exp(-.1)
        self.assertAlmostEqual(result[0.],10.)
        self.assertAlmostEqual(result[1.],expected)
        self.assertTrue(10. < result[2.] < result[1.])
        self.assertTrue(10. < result[3.] < result[2.])

    def test_sensor_bins_preserve_whole_energy_and_mark_mixed_state(self):
        segments = [dict(start_s=0.,end_s=1.,state='detection:CPU'),
                    dict(start_s=1.,end_s=2.,state='idle')]
        # raw=-1000, mA hypothesis and 1000mV yield whole-device 1 W.
        samples = [dict(mono_ns=t,current_raw=-1000,voltage_mV=1000,plugged=0,
                        current_valid=True) for t in (0,2_000_000_000)]
        bins, duplicates, last = residual.sensor_intervals(samples,0,2_000_000_000,
                                                           segments,self.frozen)
        self.assertEqual((len(bins),duplicates,last),(1,0,1.))
        self.assertEqual(bins[0]['resolution'],'mixed')
        self.assertEqual(bins[0]['phase'],'work_idle_boundary_mixed')
        self.assertAlmostEqual(bins[0]['predicted_j'],3.)
        self.assertAlmostEqual(bins[0]['observed_j'],2.)

    def test_missing_sensor_is_not_zero(self):
        samples = [dict(mono_ns=t,current_raw=-1000,voltage_mV=1000,plugged=0,
                        current_valid=valid) for t,valid in ((0,True),(1_000_000_000,False))]
        bins,_,_ = residual.sensor_intervals(samples,0,1_000_000_000,
                       [dict(start_s=0.,end_s=1.,state='detection:CPU')],self.frozen)
        self.assertIsNone(bins[0]['observed_j'])
        self.assertIsNone(bins[0]['signed_error_j'])

    def test_state_gap_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'gap or overlap'):
            residual.overlap([dict(start_s=0.,end_s=.5,state='idle')],0.,1.)

    def test_effective_idle_reference_is_endpoint_diagnostic_only(self):
        self.assertIsNone(residual.effective_idle_reference(0.,35.,10.,34.,.1))
        self.assertAlmostEqual(residual.effective_idle_reference(0.,35.,100.,30.,.1),
                               29.999772989,places=5)


if __name__ == '__main__':
    unittest.main()
