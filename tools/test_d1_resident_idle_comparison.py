import unittest
from tools.d1_resident_idle_comparison import windows


class IdleComparisonTest(unittest.TestCase):
    def setUp(self):
        self.samples=[dict(mono_ns=i*1_000_000_000,current_raw=-250,voltage_mV=4000,
                           current_valid=True,plugged=0) for i in range(121)]
        self.states=[dict(start_s=0.,end_s=35.25,state='idle'),
                     dict(start_s=35.25,end_s=46.75,state='detection:CPU'),
                     dict(start_s=46.75,end_s=120.,state='idle')]
        self.frozen={'whole_device_power_w':{'resident_idle':1.2,'detection_CPU':2.}}

    def test_phase_conservation_and_boundary_purity(self):
        rows=windows(self.samples,self.states,0,self.frozen)
        phases=[r for r in rows if r['phase']!='sensor_pure_long_idle']
        self.assertAlmostEqual(sum(r['observed_j'] for r in phases),120)
        self.assertAlmostEqual(sum(r['duration_s'] for r in phases),120)
        pure=[r for r in rows if r['phase']=='sensor_pure_long_idle']
        self.assertEqual([(r['start_s'],r['end_s']) for r in pure],[(0.,35.),(47.,120.)])
        self.assertTrue(all(r['observed_mean_w']==1. for r in pure))

    def test_missing_power_never_zero_filled(self):
        samples=[x for x in self.samples if not 55<=x['mono_ns']/1e9<=60]
        rows=windows(samples,self.states,0,self.frozen)
        post=next(r for r in rows if r['phase']=='post_load_idle')
        self.assertIsNone(post['observed_j']);self.assertIsNone(post['signed_error_j'])
        self.assertGreater(post['missing_seconds'],0)

    def test_unsupported_or_noncontiguous_map_rejected(self):
        self.states[1]['state']='classification:CPU+classification:GPU'
        with self.assertRaisesRegex(ValueError,'unsupported'):windows(self.samples,self.states,0,self.frozen)
        self.states[1]['state']='detection:CPU';self.states[1]['start_s']=36.
        with self.assertRaisesRegex(ValueError,'gaps'):windows(self.samples,self.states,0,self.frozen)


if __name__=='__main__':unittest.main()
