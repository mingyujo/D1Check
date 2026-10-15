import unittest
import tempfile
from pathlib import Path
from d1_a24_energy_unit_forensics import aligned_interval, select_lossless_copies, NS


class AlignedChargeCases(unittest.TestCase):
    def data(self):
        return [{'read_start_ns':i*NS-100,'read_end_ns':i*NS,'current_raw':-3600,
                 'charge_counter_raw':10000-i,'plugged':0} for i in range(181)]

    def test_ns_seconds_hours_and_discharge_sign_match_same_endpoints(self):
        d=aligned_interval(self.data());self.assertEqual(d['duration_s'],180)
        self.assertEqual(d['current_integral_declared_uAh'],180)
        self.assertEqual(d['charge_drop_declared_uAh'],180)
        self.assertEqual(d['required_scale_NOT_A_CALIBRATION'],1)
        self.assertIsNone(d['energy_J']);self.assertFalse(d['correction_applied'])

    def test_subinterval_counter_and_integral_share_actual_endpoints(self):
        d=aligned_interval(self.data(),10*NS,100*NS)
        self.assertEqual(d['duration_s'],90);self.assertEqual(d['current_integral_declared_uAh'],90)
        self.assertEqual(d['charge_drop_declared_uAh'],90)

    def test_charging_missing_sample_and_large_gap_are_not_imputed(self):
        x=self.data();x[50]['plugged']=1
        self.assertEqual(aligned_interval(x)['status'],'CHARGING_OR_UNKNOWN_NOT_COMPARED')
        x=self.data();x[50]['current_raw']=None
        self.assertEqual(aligned_interval(x)['status'],'NULL_OR_INVALID_RAW_SAMPLE')
        x=self.data();del x[20:30]
        self.assertEqual(aligned_interval(x)['status'],'GAP_OR_NONMONOTONIC_NOT_FILLED')

    def test_recovery_prefix_is_counted_once_without_using_outcome(self):
        with tempfile.TemporaryDirectory() as td:
            paths=[Path(td)/str(i) for i in range(3)]
            for p,b in zip(paths,[b'one\n',b'one\ntwo\n',b'one\ntwo\n']):p.write_bytes(b)
            items=[{'path':str(p),'session_id':'s','root_label':str(i)} for i,p in enumerate(paths)]
            selected,audit=select_lossless_copies(items)
            self.assertEqual(len(selected),1);self.assertEqual(len(audit),3)
            self.assertEqual(sum(a['selected'] for a in audit),1)
            self.assertEqual({a['relationship'] for a in audit},{'SELECTED','IDENTICAL','EXACT_SHORTER_PREFIX'})
            self.assertEqual(paths[0].read_bytes(),b'one\n')

    def test_divergent_recoveries_cannot_be_selected_by_length(self):
        with tempfile.TemporaryDirectory() as td:
            a=Path(td)/'a';b=Path(td)/'b';a.write_bytes(b'one\n');b.write_bytes(b'OTHER\n')
            with self.assertRaisesRegex(AssertionError,'divergent'):
                select_lossless_copies([{'path':str(p),'session_id':'s','root_label':'mock'} for p in [a,b]])


if __name__=='__main__':unittest.main()
