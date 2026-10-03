import unittest
from tools import d1_post_idle_diagnosis as d
from tools import d1_energy_thermal as e


class DiagnosisTests(unittest.TestCase):
    def test_clock_brackets_and_no_extrapolation(self):
        rows=[dict(start=100.,end=100.2,uptime=10.),dict(start=110.,end=110.2,uptime=20.)]
        convert,width=d.clock_map(rows,10.)
        self.assertAlmostEqual(convert(105.1),5.)
        self.assertAlmostEqual(width,.11)
        self.assertIsNone(convert(99.))
        with self.assertRaises(ValueError):d.clock_map([],0)

    def test_command_types_keep_observation_purposes_separate(self):
        prefix=['adb','-s','fake']
        self.assertEqual(d.kind(prefix+['exec-out','cat','/proc/uptime']),'uptime')
        self.assertEqual(d.kind(prefix+['shell','dumpsys','thermalservice']),'thermal')
        self.assertEqual(d.kind(prefix+['shell','am','force-stop','fake']),'other')

    def test_missing_power_is_not_zero_and_partition_preserved(self):
        rows=[dict(mono_ns=i*10**9,current_raw=-250,current_valid=True,voltage_mV=4000,plugged=0) for i in range(11)]
        self.assertAlmostEqual(e.integrate(rows,0,10**10,1000)['full_energy_j'],10.)
        parts=[e.integrate(rows,a*10**9,(a+5)*10**9,1000)['full_energy_j'] for a in [0,5]]
        self.assertAlmostEqual(sum(parts),10.)
        rows[5]['current_valid']=False
        self.assertIsNone(e.integrate(rows,0,10**10,1000)['full_energy_j'])


if __name__=='__main__':unittest.main()
