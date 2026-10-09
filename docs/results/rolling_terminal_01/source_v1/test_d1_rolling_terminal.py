"""Frozen thermal equations, common time, conditional continuation and rollback."""
import math,unittest
from unittest.mock import patch
from tools import d1_rolling_terminal as x
from tools.test_d1_rolling_joint_thermal import hand
from tools.test_d1_ie_dispatch import ticket,lanes

class TerminalTests(unittest.TestCase):
    def test_original_g_zero_has_no_workload_driven_h(self):
        c=hand();self.assertEqual(c.frozen['ap']['g'],0.)
        a=x.terminal_state(c,[],35e9,36.)
        b=x.terminal_state(c,[dict(state='detection_CPU',start=35.,end=36.)],35e9,36.)
        self.assertAlmostEqual(a['h_c_per_s'],b['h_c_per_s'],places=12)
        self.assertGreater(b['ap_c'],a['ap_c'])
    def test_terminal_matches_original_scalar_equation(self):
        c=hand();s=c.frozen['ap']['parameters']['ap_slope_at_30_c_per_s'];u=s['detection_CPU']-s['resident_idle']
        expected=x.p.thermal_step(c.t,c.h,u,c.init['reference_c'],c.frozen['ap'],1.)
        r=x.terminal_state(c,[dict(state='detection_CPU',start=35.,end=36.)],35e9,36.)
        self.assertEqual((r['ap_c'],r['h_c_per_s']),expected)
    def test_delayed_normal_job_uses_same_end_and_is_hotter_there(self):
        c=hand();q=ticket('d',0,'detection',35.,6.);plan=[dict(request_id='d',backend='CPU',delay_ns=250000000.)]
        r=x.terminal_pair(c,[q],lanes(),35e9,plan,'mean')
        self.assertTrue(r['valid']);self.assertAlmostEqual(r['common_end_s']-r['baseline_lane_end_s'],.25,places=10)
        self.assertEqual(r['common_end_s'],r['candidate_lane_end_s']);self.assertGreater(r['delta_ap_c'],0.)
        self.assertAlmostEqual(r['delta_h_c_per_s'],0.,places=12);self.assertFalse(r['passed'])
    def test_identical_Band_prefix_is_not_a_useful_improvement(self):
        c=hand();q=[ticket('d',0,'detection',35.,6.)];plan=[dict(request_id='d',backend='CPU',delay_ns=0.)]
        first={ctx:x.old.forecast_plan(c,q,lanes(),35e9,plan,ctx) for ctx in x.CONTEXTS}
        refs={ctx:x.old.fast.forecast(c,q,lanes(),35e9,dict(jobs=[]),ctx) for ctx in x.CONTEXTS}
        r=x.assess(c,q,lanes(),35e9,plan,first,refs,True)
        self.assertTrue(r['terminal_pass']);self.assertFalse(r['first_prefix_strict_gain']);self.assertFalse(r['useful'])
    def test_terminal_cannot_end_before_owned_jobs(self):
        c=hand()
        with self.assertRaises(ValueError):x.terminal_state(c,[dict(state='detection_CPU',start=35.,end=36.)],35e9,35.5)
    def test_same_future_input_preserves_order_only_conditionally(self):
        # Mathematical state perturbations, not calibrated values or workloads.
        c=hand();ap=c.frozen['ap'];reference=c.init['reference_c']
        for dt in (0.,1.,10.,60.):
            a=x.p.thermal_step(30.,.001,.1,reference,ap,dt)
            b=x.p.thermal_step(29.99,0.,.1,reference,ap,dt)
            self.assertLessEqual(b[0],a[0]);self.assertLessEqual(b[1],a[1])
        # Different future input invalidates that implication.
        a=x.p.thermal_step(30.,0.,0.,reference,ap,10.)
        b=x.p.thermal_step(29.99,0.,.2,reference,ap,10.);self.assertGreater(b[0],a[0])
    def test_failed_terminal_cancels_only_tentative_reservations(self):
        parent=hand();c=x.Controller(parent.frozen,parent.initial);reply=dict(selected=None,reason='proposed')
        def proposal(*args):
            c.prefix_guard_records.append(dict(passed=True,actual_prefix=[]));c.pending=dict(bad=True);c.hold=dict(bad=True);c.cool_since=35e9;return reply
        with patch.object(x.prefix.Controller,'decide',side_effect=proposal),patch.object(x,'terminal_pair',return_value=dict(valid=True,passed=False)):
            r=c.decide({},[ticket('a',0)],lanes(),35e9,{},None,None)
        self.assertEqual(r['selected'],dict(request_id='a',backend='CPU'));self.assertTrue(r['terminal_guard_blocked'])
        self.assertIsNone(c.pending);self.assertIsNone(c.hold);self.assertIsNone(c.cool_since)
if __name__=='__main__':unittest.main()
