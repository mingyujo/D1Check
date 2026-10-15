"""Pure regression for pre-APP cold deadlock; MAIN gate remains independent."""
import math
import unittest
from d1_a24_suite_dev_continue import cold_enough_to_prepare
from d1_a24_revision02_design import matches_fixed_reference
from d1_a24_revision02_suite import RULES, NS


def history(value):
    return [{'before_ns':i*5*NS,'after_ns':i*5*NS+100_000_000,'AP_c':value} for i in range(13)]


class ColdPreparationCases(unittest.TestCase):
    def test_colder_phone_may_prepare_but_still_cannot_start_MAIN(self):
        h=history(25.7)
        self.assertFalse(matches_fixed_reference(h,0,{'Tref_c':26.35},RULES))
        self.assertTrue(cold_enough_to_prepare(h,26.35))
        self.assertFalse(matches_fixed_reference(h,0,{'Tref_c':26.35},RULES))

    def test_hot_or_rising_or_short_or_gap_history_does_not_prepare(self):
        self.assertFalse(cold_enough_to_prepare(history(26.4),26.35))
        self.assertFalse(cold_enough_to_prepare(history(25.7)[:-1],26.35))
        h=history(25.7)
        for i,s in enumerate(h):s['AP_c']+=i*.02
        self.assertFalse(cold_enough_to_prepare(h,26.35))
        self.assertFalse(cold_enough_to_prepare(history(25.7)[::3],26.35))

    def test_missing_or_nonfinite_sensor_is_rejected(self):
        for value in (None,math.nan,math.inf):
            h=history(25.7);h[3]['AP_c']=value
            self.assertFalse(cold_enough_to_prepare(h,26.35))

    def test_in_band_stable_remains_accepted_and_current_window_used(self):
        self.assertTrue(cold_enough_to_prepare(history(26.3),26.35))
        h=history(27.0)+[{'before_ns':(13+i)*5*NS,'after_ns':(13+i)*5*NS+1,'AP_c':25.7} for i in range(13)]
        self.assertTrue(cold_enough_to_prepare(h,26.35))


if __name__=='__main__':unittest.main()
