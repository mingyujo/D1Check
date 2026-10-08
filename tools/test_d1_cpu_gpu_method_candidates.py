"""Physical-mask and objective tests, zero simulator environment starts."""
import copy
from types import SimpleNamespace
import unittest
from tools import d1_cpu_gpu_method_candidates as x
from tools.test_d1_ie_dispatch import ticket,lanes,controller as hand


def controller():
    frozen,case=x.core.p.inputs(x.core.p.BUNDLE)
    c=x.Controller(frozen,case['initial']);c.estimates=hand().estimates
    c.profiles={ctx:copy.deepcopy(c.estimates) for ctx in x.core.CONTEXTS}
    c.observe(35e9,lanes());return c


class Candidate(unittest.TestCase):
    def test_c_forced_base_schema_hotfix_has_no_rng_draw(self):
        current=x.current;current.seed_all(11);frozen,case=x.core.p.inputs(x.core.p.BUNDLE)
        c=x.CurrentController(frozen,case['initial'],current.ActorCritic())
        c.estimates=hand().estimates;c.profiles={ctx:copy.deepcopy(c.estimates) for ctx in x.core.CONTEXTS}
        ls=lanes();ls['CPU']=dict(request=ticket('run',1,'detection',35.,6.),phase='EXECUTING',since=35.2e9,dispatch=35e9)
        c.observe(35.45e9,ls);before=current.torch.get_rng_state().clone()
        out=c.decide(None,[ticket('q',0)],ls,35.45e9,{},None,None)
        self.assertEqual(out['selected']['backend'],'GPU');self.assertFalse(c.trajectory[-1]['informative'])
        self.assertTrue(current.torch.equal(before,current.torch.get_rng_state()))
    def test_physical_mask_does_not_drop_late_request(self):
        c=controller();q=ticket('late',0);base=x.core.ie.Controller.decide(c,None,[q],lanes(),38e9,{},None,None)
        actions=c.physical([q],lanes(),38e9,base)
        self.assertTrue(any(a['jobs'] and a['jobs'][0]['request_id']=='late' for a in actions))

    def test_supported_joint_capacity_only(self):
        c=controller();ls=lanes();ls['CPU']=dict(request=ticket('active',1),phase='WORKER_RELEASED',since=35.9e9,dispatch=35e9)
        q=ticket('q',0);base=x.core.ie.Controller.decide(c,None,[q],ls,35.9e9,{},None,None)
        actions=c.physical([q],ls,35.9e9,base)
        self.assertFalse(any(a['jobs'] for a in actions)) # class CPU+class GPU unsupported

    def test_unknown_remaining_is_missing_not_fake_cost(self):
        c=controller();ls=lanes();active=ticket('active',1,'detection',35.,6.)
        ls['CPU']=dict(request=active,phase='WORKER_RELEASED',since=36e9,dispatch=35e9)
        q=ticket('q',0);d=c.decide(None,[q],ls,36.01e9,{},None,None)
        self.assertEqual(d['public_policy'],x.ENERGY_RULE)
        self.assertFalse(d['forecast_supported'])

    def test_wait_limit_and_no_wait_ablation(self):
        c=controller();q=ticket('q',0);base=x.core.ie.Controller.decide(c,None,[q],lanes(),35e9,{},None,None)
        waits=[a for a in c.physical([q],lanes(),35e9,base) if a['kind']=='cool_wait']
        self.assertEqual(waits[0]['wait_until_ns'],35.25e9)
        c.no_wait=True;self.assertFalse(any(a['kind']=='cool_wait' for a in c.physical([q],lanes(),35e9,base)))

    def test_unsupported_backend_and_future_input(self):
        c=controller();q=ticket('d',0,'detection',35.,6.)
        base=x.core.ie.Controller.decide(c,None,[q],lanes(),35e9,{},None,None)
        self.assertFalse(any(j['backend']=='GPU' for a in c.physical([q],lanes(),35e9,base) for j in a['jobs']))
        with self.assertRaisesRegex(ValueError,'future'):
            c.decide(None,[ticket('future',1,arrival=36.)],lanes(),35e9,{},None,None)

    def test_energy_objective_and_ap_constraint_separate(self):
        c=SimpleNamespace(trajectory=[dict(grid_peak=30.)],init=dict(anchor_ap_c=29.))
        row=dict(planned=10,completed=10,energy_j=9.,peak_ap_c=30.1,urgent_service_failure=0,normal_service_failure=0,urgent_p95_ms=100.)
        refs=[dict(row,energy_j=10.,peak_ap_c=30.) for _ in range(3)]
        data,costs,valid=x.targets(c,row,refs)
        self.assertAlmostEqual(data[0]['target'][0],1.)
        self.assertAlmostEqual(costs[0],.1,places=7)
        row['completed']=9;row['peak_ap_c']=None
        data,costs,valid=x.targets(c,row,refs)
        self.assertFalse(valid[0]);self.assertFalse(valid[1]);self.assertEqual(costs[1],1)


if __name__=='__main__':unittest.main()
