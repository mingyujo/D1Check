"""Finite rolling plans and original timing boundaries; no environment starts."""
import unittest
from tools import d1_rolling_joint_thermal as x
from tools.test_d1_ie_dispatch import ticket,lanes

def hand(policy=x.WAIT):
    frozen,data=x.p.inputs(x.p.BUNDLE);c=x.Controller(frozen,data['initial'],policy);c.observe(35e9,lanes());return c

class RollingTests(unittest.TestCase):
    def test_within_task_EDD_and_joint_interleaving(self):
        qs=[ticket('c1',1,arrival=35.1),ticket('c0',0),ticket('d1',3,'detection',35.1,6.),ticket('d0',2,'detection',35.,6.)]
        plans=x.candidate_plans(qs,.25,True);self.assertEqual(len(plans),72)
        for plan in plans:
            ids=[j['request_id'] for j in plan];self.assertEqual(set(ids),{'c0','c1','d0','d1'})
            self.assertLess(ids.index('c0'),ids.index('c1'));self.assertLess(ids.index('d0'),ids.index('d1'))
            self.assertLessEqual(sum(bool(j['delay_ns']) for j in plan),1)
            self.assertTrue(all(j['backend']=='CPU' for j in plan if j['request_id'].startswith('d')))

    def test_no_wait_removes_only_discretionary_delay(self):
        qs=[ticket('c',0),ticket('d',1,'detection',35.,6.)];plans=x.candidate_plans(qs,.25,False)
        self.assertEqual(len(plans),4);self.assertTrue(all(not j['delay_ns'] for plan in plans for j in plan))

    def test_current_credit_limits_first_delay(self):
        qs=[ticket('d',0,'detection',35.,6.)];plans=x.candidate_plans(qs,.08,True)
        self.assertEqual(max(j['delay_ns'] for plan in plans for j in plan),80000000.)

    def test_CPU_only_slack_job_is_kept_in_four_slots(self):
        c=hand();qs=[ticket('c'+str(i),i) for i in range(5)]+[ticket('d',8,'detection',35.,6.)]
        window=x.window_requests(c,qs,lanes(),35e9);self.assertEqual(len(window),4);self.assertIn('d',{q['id'] for q in window})

    def test_plan_can_place_class_GPU_and_detection_CPU_together(self):
        c=hand();qs=[ticket('c',0),ticket('d',1,'detection',35.,6.)];plan=[dict(request_id='c',backend='GPU',delay_ns=0.),dict(request_id='d',backend='CPU',delay_ns=0.)]
        result=x.project_plan(c.estimates,c.profiles,qs,lanes(),35e9,plan,'mean',c.band)
        self.assertEqual([j['at_ns'] for j in result['dispatches']],[35000000000,35000000000])
        self.assertEqual({j['id'] for j in result['jobs']},{'c','d'})

    def test_plan_does_not_free_lane_at_response_or_worker_release(self):
        c=hand();qs=[ticket('d0',0,'detection',35.,6.),ticket('d1',1,'detection',35.,6.)];plan=[dict(request_id=q['id'],backend='CPU',delay_ns=0.) for q in qs]
        result=x.project_plan(c.estimates,c.profiles,qs,lanes(),35e9,plan,'mean',c.band)
        self.assertEqual(result['dispatches'][1]['at_ns'],round(35e9+sum(c.profiles['mean'][x.p.key(qs[0],'CPU')])))

    def test_window_prefix_preserves_remaining_queue(self):
        c=hand();qs=[ticket('d'+str(i),i,'detection',35.,6.) for i in range(5)];plan=[dict(request_id=q['id'],backend='CPU',delay_ns=0.) for q in qs[:4]]
        result=x.project_plan(c.estimates,c.profiles,qs,lanes(),35e9,plan,'mean',c.band);self.assertEqual({j['id'] for j in result['jobs']},{q['id'] for q in qs})

    def test_cooling_not_claimed_when_urgent_is_queued(self):
        c=hand();qs=[ticket('d',0,'detection',35.,6.),ticket('c',1)];plan=[dict(request_id='d',backend='CPU',delay_ns=250000000.)]
        with self.assertRaises(x.ProjectionUnavailable):x.project_plan(c.estimates,c.profiles,qs,lanes(),35e9,plan,'mean',c.band)

    def test_plan_guard_rejects_service_energy_and_AP_worsening(self):
        r=dict(valid=True,lane_end_s=40.,urgent_misses=0,normal_misses=0,urgent_p95_ms=100.,remaining_increment_j=10.,global_peak_ap_c=30.)
        self.assertTrue(x.acceptable(dict(r),r))
        for key,value in (('urgent_misses',1),('normal_misses',1),('urgent_p95_ms',101.),('remaining_increment_j',10.01),('global_peak_ap_c',30.01),('lane_end_s',121.)):
            self.assertFalse(x.acceptable(dict(r,**{key:value}),r))

    def test_real_future_request_rejected(self):
        c=hand()
        with self.assertRaises(ValueError):c.decide({},[ticket('future',0,arrival=36.)],lanes(),35e9,{},None,None)

if __name__=='__main__':unittest.main()
