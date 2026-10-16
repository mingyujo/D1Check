import unittest
from tools import d1_ie_response_backfill as m
from tools.test_d1_ie_priority_compare import ticket
class Contract(unittest.TestCase):
    def setup(self,remaining=.1385,owner_task='detection'):
        frozen,case=m.p.inputs(m.p.BUNDLE);c=m.Controller(frozen,case['initial']);now=40e9
        owner=ticket('owner',owner_task,39.)
        dispatch=now-sum(c.estimates[m.p.key(owner,'CPU')])+remaining*1e9
        lanes=dict(CPU=dict(request=owner,phase='EXECUTING',since=dispatch,dispatch=dispatch),
            GPU=dict(request=None,phase='AVAILABLE',since=now,dispatch=None))
        c.observe(now,lanes);return c,lanes
    def test_response_boundary_opportunity_dispatches_GPU(self):
        c,l=self.setup();out=c.decide({},[ticket('C','classification',40.)],l,40e9,{},None,None)
        self.assertEqual(out['selected'],dict(request_id='C',backend='GPU'))
        self.assertTrue(out['response_guard']['all_arrived_responses_nonworse'])
    def test_faster_CPU_response_preserves_wait(self):
        c,l=self.setup(.13);out=c.decide({},[ticket('C','classification',40.)],l,40e9,{},None,None)
        self.assertIsNone(out['selected']);self.assertEqual(c.corrections,0)
    def test_classifier_owned_CPU_cannot_dispatch_parallel_classifier(self):
        c,l=self.setup(owner_task='classification');out=c.decide({},[ticket('C','classification',40.)],l,40e9,{},None,None)
        self.assertIsNone(out['selected'])
    def test_queued_response_worsening_rejects(self):
        c,l=self.setup();calls=[]
        def projection(ordered,active,first,now):
            calls.append(first['backend']);return dict(C=first['response'],D=42. if first['backend']=='CPU' else 43.)
        c.project=projection
        out=c.decide({},[ticket('C','classification',40.),ticket('D','detection',40.,1)],l,40e9,{},None,None)
        self.assertIsNone(out['selected']);self.assertEqual(calls,['CPU','GPU'])
    def test_suffix_cannot_backfill_before_reserved_head(self):
        c,l=self.setup();q=[ticket('C','classification',40.),ticket('C2','classification',40.,1)]
        first=dict(id='C',backend='CPU',state='classification_CPU',start=42.,end=42.2,response=42.1)
        starts=[];original=c.place
        def capture(request,backend,earliest,jobs):
            starts.append(earliest);return original(request,backend,earliest,jobs)
        c.place=capture;c.project(q,[],first,40.)
        self.assertTrue(starts);self.assertTrue(all(t>=42. for t in starts))
if __name__=='__main__':unittest.main()
