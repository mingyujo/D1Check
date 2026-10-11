import unittest
from tools import d1_s26_mixed_audit as a


class Adapter(unittest.TestCase):
    def test_seven_intervals_response_ownership_and_missing(self):
        row=dict(priority="urgent",scheduled_arrival_ns=0)
        row.update(zip(a.POINTS,(10,20,30,50,55,70,75,90)))
        r=a.phase_adapter(row)
        self.assertEqual(r["source_intervals_ns"],[10,10,20,5,15,5,15])
        self.assertEqual(r["phase5_ns"],[10,35,15,5,15])
        self.assertEqual(r["response_ns"],55);self.assertEqual(r["occupied_ns"],80)
        row["priority"]="normal";self.assertEqual(a.phase_adapter(row)["response_ns"],70)
        row.pop("lane_available_ns")
        with self.assertRaises(ValueError):a.phase_adapter(row)

    def test_only_periodic_power_samples_count(self):
        r=a.power_counts([dict(kind="power_sample",mono_ns=1,current_raw=-100000),
            dict(kind="admission",mono_ns=1,current_raw=-100000)])
        self.assertEqual(r["power_samples"],1);self.assertEqual(r["admission_sensor_events"],1)
        self.assertEqual(r["current_unit"],"microampere")


if __name__=="__main__":unittest.main()
