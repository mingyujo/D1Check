"""Guard the executed prefix and cancel only tentative reservations."""
import unittest
from unittest.mock import patch
from tools import d1_rolling_prefix_guard as x
from tools.test_d1_rolling_joint_thermal import hand
from tools.test_d1_ie_dispatch import ticket,lanes

class PrefixTests(unittest.TestCase):
    def test_single_prefix_does_not_credit_future_cooling(self):
        plan=[dict(request_id='a',backend='CPU',delay_ns=0),dict(request_id='b',backend='CPU',delay_ns=250000000)]
        self.assertEqual(x.actual_prefix(plan,dict(selected=plan[0]),None,0),plan[:1])
    def test_pending_same_time_pair_is_guarded_together(self):
        plan=[dict(request_id='a',backend='GPU',delay_ns=0),dict(request_id='b',backend='CPU',delay_ns=0)]
        reply=dict(selected=dict(request_id='a',backend='GPU'));pending=dict(now_ns=0,first=reply['selected'],second=dict(request_id='b',backend='CPU'))
        self.assertEqual(x.actual_prefix(plan,reply,pending,0),plan)
        self.assertEqual(x.actual_prefix(plan,reply,pending,1),plan[:1])
    def test_cooling_only_is_first_prefix(self):
        plan=[dict(request_id='a',backend='CPU',delay_ns=250000000),dict(request_id='b',backend='CPU',delay_ns=0)]
        self.assertEqual(x.actual_prefix(plan,dict(selected=None),None,0),plan[:1])
    def test_failed_first_prefix_returns_band_and_cancels_reservations(self):
        parent=hand();c=x.Controller(parent.frozen,parent.initial);q=[ticket('a',0)];public=lanes()
        plan=[dict(request_id='a',backend='CPU',delay_ns=0)]
        def proposal(*args):
            c.plan_records.append(dict(selected_plan=plan));c.pending=dict(bad=True);c.hold=dict(bad=True);c.cool_since=35e9
            return dict(selected=None,reason='proposal')
        reference=dict(valid=True,lane_end_s=40.,urgent_misses=0,normal_misses=0,urgent_p95_ms=100.,remaining_increment_j=1.,global_peak_ap_c=30.)
        with patch.object(x.old.Controller,'decide',side_effect=proposal),patch.object(x.old.fast,'forecast',return_value=reference),patch.object(x.old,'forecast_plan',return_value=dict(reference,global_peak_ap_c=30.01)):
            r=c.decide({},q,public,35e9,{},None,None)
        self.assertEqual(r['selected'],dict(request_id='a',backend='CPU'));self.assertTrue(r['prefix_guard_blocked'])
        self.assertIsNone(c.pending);self.assertIsNone(c.hold);self.assertIsNone(c.cool_since)
    def test_passing_guard_preserves_actual_reply(self):
        parent=hand();c=x.Controller(parent.frozen,parent.initial);plan=[dict(request_id='a',backend='CPU',delay_ns=0)];reply=dict(selected=plan[0],reason='proposal')
        def proposal(*args):c.plan_records.append(dict(selected_plan=plan));return reply
        f=dict(valid=True,lane_end_s=40.,urgent_misses=0,normal_misses=0,urgent_p95_ms=100.,remaining_increment_j=1.,global_peak_ap_c=30.)
        with patch.object(x.old.Controller,'decide',side_effect=proposal),patch.object(x.old.fast,'forecast',return_value=f),patch.object(x.old,'forecast_plan',return_value=f):
            self.assertIs(c.decide({},[ticket('a',0)],lanes(),35e9,{},None,None),reply)
        self.assertEqual(c.prefix_blocked_calls,0)
if __name__=='__main__':unittest.main()
