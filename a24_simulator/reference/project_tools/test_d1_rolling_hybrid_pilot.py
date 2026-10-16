import inspect, unittest
from tools import d1_rolling_hybrid_pilot as x
from tools.test_d1_rolling_execution_pilot import rows

class Pilot(unittest.TestCase):
    def test_same_unused_budget_and_fixed_conditions(self):
        source=inspect.getsource(x.prepare)
        self.assertIn('copy.deepcopy(read(prepared.LOCAL',source)
        self.assertIn('original pilot already activated',source)
        self.assertIn('same unused112 cap',source)
        self.assertEqual(x.SEEDS,x.prepared.SEEDS)
        self.assertEqual(x.ROLES,x.prepared.ROLES)
    def test_all_service_and_original_unit_gates_preserved(self):
        self.assertTrue(x.gate_rows(rows(peak_ap_c=30.9))['promising'])
        bad=rows(peak_ap_c=30.9);bad[-1]['urgent_p95_ms']=101.
        self.assertFalse(x.gate_rows(bad)['promising'])
        self.assertFalse(x.gate_rows(rows(completed=1,incomplete=1,energy_j=1.))['promising'])
    def test_four_existing_native_fixtures_and_hybrid_controllers(self):
        self.assertEqual(len(x.fixtures()),4)
        f,i,_=x.hybrid.load()
        for role in x.ROLES:self.assertTrue(hasattr(x.controller(role,f,i['initial']),'hybrid_state'))
    def test_no_fitting_device_or_learner_in_new_runner(self):
        source=inspect.getsource(x)
        for forbidden in ('subprocess.run(["adb"','thermal.fit(','energy.fit(','optimizer.step('):self.assertNotIn(forbidden,source)
        self.assertIn('learning_starts=0,device_commands=0',source)

if __name__=='__main__':unittest.main()
