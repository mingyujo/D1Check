import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from tools import d1_online_power_diagnosis as d
from tools import d1_online_sampling_study as s
from tools import d1_arrival_energy_collection_device as runner
from tools import d1_online_sampling_readout as readout


class SamplingTests(unittest.TestCase):
    def test_pair_sign_and_incomplete_data_never_become_completed_comparison(self):
        rows=[dict(case=str(i),period_ms=period,observed_120s_j=float(i),
            observed_35_120s_j=2.*i,excess_35_120s_j=3.*i) for i,period in enumerate([1000,900,900,1000])]
        pairs=readout.paired_differences(rows)
        self.assertEqual([v['difference_900_minus_1000_j'] for v in pairs],[1.,-1.])
        with self.assertRaises(ValueError):readout.paired_differences(rows[:3])
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);s.study.cal.write_new(root/'plan.json',dict(output_root=tmp))
            s.study.cal.write_new(root/'FINAL_RECEIPT.json',dict(status='stopped_no_resume'))
            with self.assertRaisesRegex(ValueError,'incomplete'):readout.readout(root/'plan.json',root/'out')
            self.assertFalse((root/'out').exists())
    def test_phase_lock_and_noncommensurate_period(self):
        fixed=d.phase_counts([35+i for i in range(45)],2)
        shifted=d.phase_counts([35+.9*i for i in range(50)],2)
        self.assertEqual(sum(n>0 for n in fixed),2)
        self.assertEqual(sum(n>0 for n in shifted),8)
        self.assertEqual(sum(fixed),45)
        with self.assertRaises(ValueError):d.phase_counts([1],0)

    def test_actual_entry_checks_sampling_plan_before_device_or_claim(self):
        with tempfile.TemporaryDirectory() as tmp:
            f=Path(tmp)/'plan.json'
            s.study.cal.write_new(f,dict(online_sampling_audit=True,online_policy_study=True))
            with patch.object(s,'check',side_effect=ValueError('sampling guard')) as guard, \
                 patch.object(runner,'ObservedDevice',side_effect=AssertionError('device forbidden')) as device, \
                 patch('subprocess.Popen',side_effect=AssertionError('real process forbidden')):
                with self.assertRaisesRegex(ValueError,'sampling guard'):
                    runner.run(f,'forbidden','',s.p.digest(f),True)
                guard.assert_called_once_with(f);device.assert_not_called()
                self.assertEqual([x.name for x in Path(tmp).iterdir()],['plan.json'])

    def test_study_has_no_refit_and_fixed_abba_budget(self):
        c=s.p.read(s.CONTRACT)
        self.assertEqual(c['periods_ms'],[1000,900,900,1000]);self.assertFalse(c['fit_coefficients'])
        b=c['budget'];self.assertEqual(b['explicit'],4*(96+8))
        self.assertEqual(b['total_s'],600+4*700+3*90)
        self.assertEqual(b['adb'],4*3200+200)


if __name__=='__main__':unittest.main()
