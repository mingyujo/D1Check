"""Adapter event/hold/pair checks with mocked choices, no plant projections."""
import copy,unittest
from unittest.mock import Mock,patch
from tools import d1_rolling_execution_prefix as x
from tools.test_d1_ie_priority_compare import ticket
def lanes(now=35e9):return {b:dict(request=None,phase='AVAILABLE',since=now,dispatch=None) for b in ('CPU','GPU')}
class Adapter(unittest.TestCase):
    def setup(self):
        frozen,case=x.p.inputs(x.p.BUNDLE);c=x.Controller(frozen,case['initial']);public=lanes();c.observe(35e9,public);return c,public
    def decide(self,c,q,l,now=35e9):return c.decide({},q,l,now,{},None,None)
    def cool(self,now=35e9):return dict(kind='cool_wait',until_ns=now+250e6,hold_signature=[])
    def test_arrival_interrupts_hold_without_renewing_credit(self):
        c,l=self.setup();q=[ticket('D','detection',35.)];c.choose_prefix=Mock(return_value=self.cool())
        self.assertIsNone(self.decide(c,q,l)['selected'])
        c.observe(35.1e9,l);q.append(ticket('C','classification',35.1,1))
        c.choose_prefix=Mock(return_value=dict(kind='single',jobs=[dict(request_id='C',backend='GPU')]))
        self.assertEqual(self.decide(c,q,l,35.1e9)['selected']['request_id'],'C')
        self.assertAlmostEqual(c.credit,.15);self.assertIsNone(c.hold)
    def test_phase_callback_keeps_resource_hold_and_real_owner(self):
        c,l=self.setup();owner=ticket('owner','detection',35.);l['CPU']=dict(request=owner,phase='ASSIGNED',since=35e9,dispatch=35e9)
        q=[ticket('C','classification',35.,1)];c.observe(35e9,l);c.choose_prefix=Mock(return_value=dict(kind='resource_wait',until_ns=None,hold_signature=[]))
        self.assertIsNone(self.decide(c,q,l)['selected']);c.choose_prefix.reset_mock()
        l['CPU']['phase']='WORKER_RELEASED';l['CPU']['since']=35.5e9;c.observe(35.5e9,l)
        self.assertIsNone(self.decide(c,q,l,35.5e9)['selected']);c.choose_prefix.assert_not_called()
        self.assertIsNotNone(l['CPU']['request'])
    def test_any_lane_available_ends_resource_hold(self):
        c,l=self.setup();q=[ticket('D','detection',35.,2)]
        l['CPU']=dict(request=ticket('ownerD','detection',35.),phase='ASSIGNED',since=35e9,dispatch=35e9)
        l['GPU']=dict(request=ticket('ownerC','classification',35.,1),phase='ASSIGNED',since=35e9,dispatch=35e9)
        c.observe(35e9,l);c.choose_prefix=Mock(return_value=dict(kind='resource_wait',until_ns=None,hold_signature=[]));self.decide(c,q,l)
        l['CPU']=dict(request=None,phase='AVAILABLE',since=35.1e9,dispatch=None);c.observe(35.1e9,l)
        c.choose_prefix=Mock(return_value=dict(kind='single',jobs=[dict(request_id='D',backend='CPU')]))
        self.assertEqual(self.decide(c,q,l,35.1e9)['selected'],dict(request_id='D',backend='CPU'));self.assertIsNone(c.hold)
    def test_timer_expiry_makes_time_progress_and_no_repeat_wait(self):
        c,l=self.setup();q=[ticket('D','detection',35.)];c.choose_prefix=Mock(return_value=self.cool());r=self.decide(c,q,l)
        self.assertGreater(r['wait_until_ns'],r['now_ns']);c.observe(r['wait_until_ns'],l);c.choose_prefix=Mock(return_value=None)
        self.assertEqual(self.decide(c,q,l,r['wait_until_ns'])['selected']['request_id'],'D');self.assertAlmostEqual(c.credit,0.)
    def test_pair_second_is_committed_only_after_first_dispatch(self):
        c,l=self.setup();q=[ticket('C','classification',35.),ticket('D','detection',35.,1)]
        c.choose_prefix=Mock(return_value=dict(kind='bundle',jobs=[dict(request_id='C',backend='GPU'),dict(request_id='D',backend='CPU')]))
        self.assertEqual(self.decide(c,q,l)['selected']['request_id'],'C')
        l['GPU']=dict(request=q[0],phase='ASSIGNED',since=35e9,dispatch=35e9);q=q[1:];c.observe(35e9,l)
        self.assertEqual(self.decide(c,q,l)['selected'],dict(request_id='D',backend='CPU'));self.assertIsNone(c.pending)
    def test_failed_second_commit_preserves_all_queued_requests(self):
        c,l=self.setup();q=[ticket('C','classification',35.),ticket('D','detection',35.,1)];before=copy.deepcopy(q)
        c.pending=dict(now_ns=35e9,first=dict(request_id='C',backend='GPU'),second=dict(request_id='D',backend='CPU'))
        c.choose_prefix=Mock(return_value=None);self.decide(c,q,l)
        self.assertEqual(q,before);self.assertIsNone(c.pending);self.assertEqual(c.cancelled_bundles,1)
    def test_owned_lane_and_urgent_cooling_rejected(self):
        c,l=self.setup();owner=ticket('owner','detection',35.);l['CPU']=dict(request=owner,phase='WORKER_RELEASED',since=35e9,dispatch=35e9)
        q=[ticket('D','detection',35.,1)];c.choose_prefix=Mock(return_value=dict(kind='single',jobs=[dict(request_id='D',backend='CPU')]))
        self.assertIsNone(self.decide(c,q,l)['selected'])
        l=lanes();q=[ticket('C','classification',35.)];c.choose_prefix=Mock(return_value=self.cool())
        r=self.decide(c,q,l);self.assertTrue(r['prefix_application_rejected']);self.assertNotIn('wait_until_ns',r)
if __name__=='__main__':unittest.main()
