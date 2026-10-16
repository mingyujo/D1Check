"""Hand worked source semantics; none of these tests starts an environment."""
import copy
import unittest
from tools import d1_edd_ect_residual_controller as x
from tools.test_d1_ie_dispatch import ticket, controller as hand_base, lanes


def controller(policy=x.PRIOR):
    frozen, case=x.p.inputs(x.p.BUNDLE)
    c=x.Controller(frozen,case['initial'],policy,record_forecasts=True)
    c.estimates=hand_base().estimates
    c.profiles={ctx:copy.deepcopy(c.estimates) for ctx in x.CONTEXTS}
    c.observe(35e9,lanes())
    return c


def decide(c,qs,ls=None,now=35.):
    return c.decide(None,qs,ls or lanes(),now*1e9,{},None,None)


class Residual(unittest.TestCase):
    def test_exact_base_uses_ect_lane_not_response(self):
        c=controller(x.BASE)
        d=decide(c,[ticket('q',0)])
        self.assertEqual(d['selected']['backend'],'GPU')
        self.assertEqual(d['predicted_lane_end_s'],35.5)

    def test_projection_hand_timeline(self):
        c=controller();q=ticket('q',0)
        r=x.project(c.estimates,c.profiles,[q],lanes(),35e9,
                    dict(jobs=[dict(request_id='q',backend='GPU')]),'mean')
        self.assertEqual(r['dispatches'],[dict(request_id='q',backend='GPU',at_ns=35000000000)])
        self.assertAlmostEqual(r['jobs'][0]['response'],35.4)
        self.assertAlmostEqual(r['jobs'][0]['end'],35.5)
        self.assertEqual([t['stage'] for t in r['transitions']],[0,1,2,3,4])

    def test_ect_resource_wait_is_selectable(self):
        c=controller();ls=lanes()
        c.estimates['classification_CPU_urgent']=[50e6,50e6,0.,0.,50e6]
        ls['CPU']=dict(request=ticket('run',9,'detection',35.,6.),phase='EXECUTING',since=35.2e9,dispatch=35e9)
        c.observe(35.3e9,ls)
        qs=[ticket('q',0)]
        base=x.ie.Controller.decide(c,None,qs,ls,35.3e9,{},None,None)
        acts=c.candidates(qs,ls,35.3e9,base)
        self.assertEqual(acts[0]['kind'],'ect_resource_wait')
        self.assertTrue(any(a['jobs'] and a['jobs'][0]['backend']=='GPU' for a in acts))

    def test_resource_wait_rechecks_public_phase(self):
        c=controller();ls=lanes()
        ls['GPU']=dict(request=ticket('run',9),phase='EXECUTING',since=35.2e9,dispatch=35e9)
        r=x.project(c.estimates,c.profiles,[ticket('q',0)],ls,35.3e9,
                    dict(jobs=[],wait_until_ns=35.5e9),'mean')
        self.assertEqual(r['dispatches'][0]['backend'],'GPU')
        self.assertEqual(r['dispatches'][0]['at_ns'],35500000000)

    def test_worker_released_still_owns_lane(self):
        c=controller();ls=lanes()
        ls['CPU']=dict(request=ticket('run',9),phase='WORKER_RELEASED',since=35.2e9,dispatch=35e9)
        qs=[ticket('n',0,'detection',35.,6.)]
        base=x.ie.Controller.decide(c,None,qs,ls,35.3e9,{},None,None)
        acts=c.candidates(qs,ls,35.3e9,base)
        self.assertFalse(any(a['jobs'] for a in acts))

    def test_observed_phase_overrun_never_becomes_zero(self):
        c=controller();ls=lanes()
        ls['CPU']=dict(request=ticket('run',9,'detection',35.,6.),phase='EXECUTING',since=35.2e9,dispatch=35e9)
        c.observe(35.45e9,ls)
        qs=[ticket('q',0)]
        d=decide(c,qs,ls,35.45)
        self.assertEqual(d['reason'],'unavailable_forecast_exact_base')
        self.assertEqual(d['selected']['backend'],'GPU')

    def test_total_overrun_exact_base(self):
        c=controller();ls=lanes()
        ls['CPU']=dict(request=ticket('run',9),phase='WORKER_RELEASED',since=36e9,dispatch=35e9)
        d=decide(c,[ticket('q',0)],ls,36.01)
        self.assertEqual(d['reason'],'unknown_overrun_exact_base')
        self.assertIsNone(d['selected'])

    def test_cooling_credit_not_reset_by_arrival(self):
        c=controller();c.cool_since=35e9
        c.observe(35.1e9,lanes())
        self.assertAlmostEqual(c.credit,.15)
        c.observe(35.12e9,lanes())
        self.assertAlmostEqual(c.credit,.15)
        ls=lanes();ls['GPU']=dict(request=ticket('new',1),phase='ASSIGNED',since=35.12e9,dispatch=35.12e9)
        c.observe(35.12e9,ls)
        self.assertEqual(c.credit,.25)

    def test_bundle_commit_once_and_cancel(self):
        c=controller();q1=ticket('c',0);q2=ticket('n',1,'detection',35.,6.)
        c.pending=dict(now_ns=35e9,first=dict(request_id='c',backend='GPU'),second=dict(request_id='n',backend='CPU'))
        ls=lanes();ls['GPU']=dict(request=q1,phase='ASSIGNED',since=35e9,dispatch=35e9)
        d=decide(c,[q2],ls)
        self.assertEqual(d['reason'],'bundle_commit');self.assertIsNone(c.pending)
        c.pending=dict(now_ns=35e9,first=dict(request_id='c',backend='GPU'),second=dict(request_id='n',backend='CPU'))
        c.observe(35.01e9,ls)
        decide(c,[q2],ls,35.01)
        self.assertEqual(c.cancelled_bundles,1)

    def test_future_and_private_rejected(self):
        c=controller()
        with self.assertRaisesRegex(ValueError,'future'):decide(c,[ticket('q',0,arrival=36.)])
        ls=lanes();ls['CPU']['durations']=[]
        with self.assertRaisesRegex(ValueError,'private'):decide(c,[ticket('q',0)],ls)

    def test_entire_queue_deadline_not_just_eight_slots(self):
        c=controller()
        qs=[ticket(str(i),i,'detection',35.,6.) for i in range(12)]
        qs[-1]['deadline_offset_ns']=100_000_000
        r=x.project(c.estimates,c.profiles,qs,lanes(),35e9,dict(jobs=[]),'mean')
        self.assertEqual(len(r['jobs']),12);self.assertGreater(r['deadline_misses'],0)

    def test_full_forecast_dedup_and_schema(self):
        c=controller();qs=[ticket('c',0),ticket('n',1,'detection',35.,6.)]
        d=decide(c,qs)
        self.assertEqual(len(d['state_features']),109)
        self.assertTrue(all(len(row)==68 for row in d['candidate_features']))
        keys=[tuple(tuple((j['request_id'],j['backend'],j['at_ns']) for j in a['forecasts'][ctx]['dispatches'])
                    for ctx in x.CONTEXTS) for a in d['candidates'] if all(f['valid'] for f in a['forecasts'].values())]
        self.assertEqual(len(keys),len(set(keys)))

    def test_same_callback_no_new_action(self):
        c=controller();qs=[ticket('q',0)]
        first=decide(c,qs);count=c.projection_calls
        second=decide(c,qs)
        self.assertEqual(first,second);self.assertEqual(count,c.projection_calls)

    def test_grid_forecast_matches_independent_full_account(self):
        c=controller();q=ticket('q',0)
        a=dict(jobs=[dict(request_id='q',backend='GPU')])
        f=c.forecast([q],lanes(),35e9,a,'mean')
        r=dict(ledger=[dict(q,status='succeeded',backend='GPU',dispatch_ns=35e9,lane_available_ns=35.5e9)])
        _,costs,_=x.p.account(r,c.initial,c.frozen)
        self.assertAlmostEqual(f['peak_ap_c'],max(costs['ap_path']),places=9)


if __name__=='__main__':unittest.main()
