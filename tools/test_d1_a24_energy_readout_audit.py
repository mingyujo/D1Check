import unittest
from d1_a24_energy_readout_audit import audit_events, NS


class UnitAuditCases(unittest.TestCase):
    def events(self):
        return [{'kind':'sensor_sample','read_end_ns':i*NS,'current_raw':-3600,
                 'charge_counter_raw':10000-i,'plugged':0} for i in range(181)]

    def test_equal_declared_charge_is_not_calibration_and_no_scale_fix(self):
        d=audit_events(self.events(),0)
        self.assertEqual(d['counter_drop_to_current_integral_ratio'],1)
        self.assertIsNone(d['calibrated_energy_J'])
        self.assertFalse(d['independent_power_ground_truth'])
        self.assertFalse(d['unit_scale_correction_applied'])

    def test_missing_boundary_and_charging_are_not_filled(self):
        self.assertEqual(audit_events(self.events()[1:],0)['status'],'COUNTER_ENDPOINTS_NOT_BRACKETED')
        a=self.events();a[50]['plugged']=1
        self.assertEqual(audit_events(a,0)['status'],'MISSING_OR_CHARGING_SAMPLE')

    def test_coarse_counter_and_thousandfold_disagreement_remain_diagnostic(self):
        a=self.events()
        for e in a:e['current_raw']=-3600000
        d=audit_events(a,0)
        self.assertEqual(d['counter_drop_to_current_integral_ratio'],.001)
        self.assertEqual(d['raw_current_median'],-3600000)
        self.assertIsNone(d['calibrated_energy_J'])


if __name__=='__main__':unittest.main()
