"""Public-tape and actual wait semantics; three counted frozen-model fixtures."""
import unittest
from types import SimpleNamespace
from tools import d1_rolling_prefix_opportunity as m
from tools import d1_rolling_prefix_opportunity_study as study
def ticket(name,task='detection',ordinal=0):
    return dict(id=name,ordinal=ordinal,task=task,priority='normal' if task=='detection' else 'urgent',
        arrival_ns=35_000_000_000,deadline_offset_ns=6_000_000_000 if task=='detection' else 1_500_000_000)
class Semantics(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.budget=study.Budget()
        study.write(study.LOCAL/'fixture_registration.json',dict(test_source_sha256=study.sha(__file__),
            expected_model_projection_starts=3,shared_projection_cap=792,fixture_input='synthetic tickets, original measured five-phase profiles',
            native_environment_learning_device_starts=0,clock_reset=False))
    def controller(self):
        frozen,_=m.p.inputs(m.p.BUNDLE);initial=study.read(study.ROOT/'docs/results/rolling_prefix_01/inputs.json')['initial']
        return m.previous.Controller(frozen,initial)
    def test_resource_wait_ignores_phase_until_actual_available(self):
        c=self.controller();d=ticket('owned');q=ticket('C','classification',1);now=35e9
        lanes=dict(CPU=dict(request=d,phase='ASSIGNED',since=now,dispatch=now),GPU=dict(request=None,phase='AVAILABLE',since=now,dispatch=None))
        c.observe(now,lanes);expected_end=now+sum(c.profiles['mean'][m.p.key(d,'CPU')])
        result=self.budget.call('fixture_resource_hold','prefix',lambda:m.project(c,[q],lanes,now,dict(kind='resource_wait',until_ns=None,hold_signature=[]),'mean'))
        self.assertGreaterEqual(result['dispatches'][0]['at_ns']+1,expected_end)
        self.assertEqual(result['dispatches'][0]['request_id'],'C')
    def test_cool_wait_resumes_Band_not_discarded_target(self):
        c=self.controller();queue=[ticket('earlier',ordinal=0),ticket('later',ordinal=1)];now=35e9
        lanes={b:dict(request=None,phase='AVAILABLE',since=now,dispatch=None) for b in ('CPU','GPU')};c.observe(now,lanes)
        result=self.budget.call('fixture_cooling_Band','prefix',lambda:m.project(c,queue,lanes,now,dict(kind='cool_wait',until_ns=now+250e6,hold_signature=[]),'mean'))
        self.assertEqual(result['dispatches'][0]['request_id'],'earlier')
        self.assertEqual(result['dispatches'][0]['at_ns'],now+250e6)
        self.assertEqual(len(result['dispatches']),2)
    def test_single_prefix_keeps_response_and_lane_boundaries(self):
        c=self.controller();q=ticket('C','classification');now=35e9
        lanes={b:dict(request=None,phase='AVAILABLE',since=now,dispatch=None) for b in ('CPU','GPU')};c.observe(now,lanes)
        result=self.budget.call('fixture_single_response','prefix',lambda:m.project(c,[q],lanes,now,dict(kind='single',jobs=[dict(request_id='C',backend='CPU')]),'mean'))
        job=result['jobs'][0];self.assertLess(job['response'],job['end'])
        self.assertAlmostEqual(job['response'],(round(now+sum(c.profiles['mean'][m.p.key(q,'CPU')][:2])))/1e9)
    def test_public_tape_excludes_future_and_keeps_worker_owner(self):
        d=ticket('owned');future=dict(ticket('future'),arrival_ns=40e9)
        item=dict(result=dict(ledger=[d,future],decisions=[dict(now_ns=35e9,selected=dict(request_id='owned',backend='CPU')),dict(now_ns=36e9,selected=None)],
            transitions=[dict(at_ns=36_000_000_000,request_id='owned',backend='CPU',event='worker_release_ns')]))
        class Observer:
            def observe(self,now,lanes):pass
        observer=Observer();observer.hold=None
        queue,lanes,_=m.PublicTape(item).restore(observer,1)
        self.assertEqual(queue,[]);self.assertEqual(lanes['CPU']['request']['id'],'owned')
        self.assertEqual(lanes['CPU']['phase'],'WORKER_RELEASED')
    def test_wait_descriptor_has_no_future_target(self):
        c=self.controller();queue=[ticket('D')];now=35e9
        lanes={b:dict(request=None,phase='AVAILABLE',since=now,dispatch=None) for b in ('CPU','GPU')}
        action=m.actual_action(c,[dict(request_id='D',backend='CPU',delay_ns=250e6)],queue,lanes,now)
        self.assertEqual(action['kind'],'cool_wait');self.assertNotIn('jobs',action)
        self.assertNotIn('request_id',action)
if __name__=='__main__':unittest.main()
