import unittest
from d1_a24_conditional_energy_comparison import integrate, comparison, NS, nonworsening


def row(t,i=-100,v=4000):
    return dict(read_start_ns=int(t*NS),read_end_ns=int(t*NS),current_raw=i,
                voltage_raw=v,plugged=0,current_unit='uA_API_DEVICE_UNVERIFIED',voltage_unit='mV')


class ConditionalEnergyTest(unittest.TestCase):
    def test_known_discharge_and_unit_ratio(self):
        samples=[row(t) for t in range(11)]
        self.assertAlmostEqual(integrate(samples,0,10*NS)['energy_j'],4.)
        self.assertAlmostEqual(integrate(samples,0,10*NS,scale=1)['energy_j'],.004)

    def test_linear_power_boundary_interpolation(self):
        samples=[row(0,0),row(2,-200)]
        self.assertAlmostEqual(integrate(samples,NS//2,3*NS//2)['energy_j'],.4)

    def test_invalid_samples_are_not_filtered_and_bridged(self):
        for patch in ({'current_raw':-2147483648},{'current_raw':None},{'voltage_raw':None},
                      {'plugged':1},{'current_raw':100},{'current_unit':'mA'}, {'current_valid':False}):
            with self.subTest(patch=patch):
                samples=[row(t) for t in range(3)];samples[1].update(patch)
                self.assertIsNone(integrate(samples,0,2*NS)['energy_j'])

    def test_gap_duplicate_and_missing_boundary(self):
        for samples,start,end in [([row(0),row(3)],0,3*NS),
                                  ([row(0),row(1),row(1),row(2)],0,2*NS),
                                  ([row(1),row(2)],0,2*NS)]:
            self.assertIsNone(integrate(samples,start,end)['energy_j'])

    def test_counter_has_no_effect_zero_current_valid(self):
        samples=[row(0,0),row(1,0)]
        samples[0]['charge_counter_raw']=4000000;samples[1]['charge_counter_raw']=0
        self.assertEqual(integrate(samples,0,NS)['energy_j'],0.)

    def test_positive_shared_gain_cancels_but_offset_does_not(self):
        self.assertEqual(comparison(80,100)['reduction_pct'],comparison(80000,100000)['reduction_pct'])
        self.assertNotEqual(comparison(80,100)['reduction_pct'],comparison(90,110)['reduction_pct'])
        self.assertIsNone(comparison(1,0)['reduction_pct'])

    def test_service_loss_blocks_descriptive_nonworsening(self):
        baseline=dict(planned=128,completed=128,failed=0,unfinished=0,C_on_time=96,D_on_time=32,C_P95_ms=200.)
        self.assertTrue(nonworsening(baseline,baseline))
        self.assertFalse(nonworsening(baseline|dict(D_on_time=31),baseline))
        self.assertFalse(nonworsening(baseline|dict(completed=127,unfinished=1),baseline))
        self.assertFalse(nonworsening(baseline|dict(C_P95_ms=201.),baseline))


if __name__=='__main__':unittest.main()
