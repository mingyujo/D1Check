"""Priority definitions, observable estimates, CPU protection and lane release."""
import unittest
from tools import d1_ie_priority_compare as m
from tools import d1_ie_dispatch as original


def ticket(name,task,arrival,ordinal=0):
    return dict(id=name,task=task,priority='urgent' if task=='classification' else 'normal',
        arrival_ns=round(arrival*1e9),ordinal=ordinal,
        deadline_offset_ns=1_500_000_000 if task=='classification' else 6_000_000_000)


class Contract(unittest.TestCase):
    def setup_rule(self,rule,now=40.):
        frozen,case=m.p.inputs(m.p.BUNDLE);c=m.Controller(frozen,case['initial'],rule)
        lanes={b:dict(request=None,phase='AVAILABLE',since=now*1e9,dispatch=None) for b in ('CPU','GPU')}
        c.observe(now*1e9,lanes)
        return c,lanes

    def decide(self,c,q,lanes,now=40.):return c.decide({},q,lanes,now*1e9,{},None,None)

    def test_earlier_due_and_minimum_response_slack_can_choose_differently(self):
        q=[ticket('C','classification',40.),ticket('D','detection',35.65,1)]
        e,l=self.setup_rule('EDD');s,_=self.setup_rule('MST')
        self.assertEqual(self.decide(e,q,l)['head_request_id'],'C')
        self.assertEqual(self.decide(s,q,l)['head_request_id'],'D')

    def test_normalized_CR_differs_from_absolute_slack(self):
        q=[ticket('C','classification',39.5),ticket('D','detection',36.,1)]
        ms,l=self.setup_rule('MST');cr,_=self.setup_rule('CR')
        self.assertEqual(self.decide(ms,q,l)['head_request_id'],'C')
        self.assertEqual(self.decide(cr,q,l)['head_request_id'],'D')

    def test_ATC_uses_response_slack_and_lane_productivity_at_fixed_k(self):
        c,l=self.setup_rule('ATC');q=[ticket('C','classification',40.),ticket('D','detection',40.,1)]
        out=self.decide(c,q,l)
        service=sum(c.estimates[m.p.key(q[0],'CPU')])/1e9
        mean=(service+sum(c.estimates[m.p.key(q[1],'CPU')])/1e9)/2
        chosen=c.place(q[0],'CPU',40.,[])
        expected=__import__('math').log(service)+(41.5-chosen['response'])/(2*mean)
        self.assertAlmostEqual(out['priority_scores']['C'],expected)
        self.assertEqual(out['ATC_k'],2.)

    def test_CPU_protection_reduces_arrived_D_expected_misses_when_C_meets_due(self):
        q=[ticket('C','classification',40.)]
        q += [ticket('D'+str(i),'detection',39.7 if i<9 else 40.,i+1) for i in range(10)]
        s,l=self.setup_rule('MST');guard,_=self.setup_rule('PROTECT')
        self.assertEqual(self.decide(s,q,l)['selected']['backend'],'CPU')
        out=self.decide(guard,q,l)
        self.assertEqual(out['selected']['backend'],'GPU')
        self.assertLess(out['CPU_protection']['GPU_route_expected_D_misses'],out['CPU_protection']['CPU_route_expected_D_misses'])
        self.assertLessEqual(out['predicted_response_s'],41.5)

    def test_no_protection_without_actual_expected_miss_reduction(self):
        c,l=self.setup_rule('PROTECT');out=self.decide(c,[ticket('C','classification',40.),ticket('D','detection',40.,1)],l)
        self.assertFalse(out['CPU_protection']['GPU_route_allowed']);self.assertEqual(c.protect_count,0)

    def test_worker_released_is_not_actual_lane_available(self):
        c,l=self.setup_rule('EDD');owner=ticket('owned','detection',39.)
        duration=sum(c.estimates[m.p.key(owner,'CPU')]);dispatch=40e9-duration+500_000
        l['CPU']=dict(request=owner,phase='WORKER_RELEASED',since=40e9-1000,dispatch=dispatch)
        out=self.decide(c,[ticket('D','detection',40.)],l)
        self.assertIsNone(out['selected']);self.assertGreater(out['wait_until_ns'],40e9)

    def test_future_and_unsupported_requests_rejected(self):
        c,l=self.setup_rule('CR')
        with self.assertRaises(ValueError):self.decide(c,[ticket('future','classification',41.)],l)
        bad=dict(ticket('bad','detection',40.),priority='urgent')
        with self.assertRaises(ValueError):self.decide(c,[bad],l)

    def test_EDD_wrapper_matches_original_queue_and_resource_choice(self):
        c,l=self.setup_rule('EDD');old=original.Controller(c.frozen,c.initial,'IE_EDD_ECT_LANE_PC_V1')
        q=[ticket('C','classification',39.8),ticket('D','detection',36.,1)]
        new=self.decide(c,q,l);prior=old.decide({},q,l,40e9,{},None,None)
        self.assertEqual(new['selected'],prior['selected']);self.assertEqual(new['ordered_ids'],prior['ordered_ids'])

    def test_unknown_overrun_does_not_invent_free_lane(self):
        c,l=self.setup_rule('MST');owner=ticket('busy','detection',35.)
        l['CPU']=dict(request=owner,phase='EXECUTING',since=35e9,dispatch=35e9)
        out=self.decide(c,[ticket('C','classification',40.)],l)
        self.assertIsNone(out['selected']);self.assertEqual(out['reason'],'unknown_overrun_wait_for_public_event')

if __name__=='__main__':unittest.main()
