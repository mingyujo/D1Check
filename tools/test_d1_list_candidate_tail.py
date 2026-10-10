"""Source-faithful public continuation and on-policy admission tests."""
import copy
import unittest
import numpy as np
import torch
from tools import d1_list_candidate_rl as c
from tools import d1_list_candidate_tail as t
from tools import test_d1_list_candidate_service_list as fixture


class Contract(unittest.TestCase):
    def setup_controller(self,**kwargs):
        old,q,lanes=fixture.Contract().setup_controller()
        x=t.TailController(old.frozen,old.initial,feature_variant='head2+C_next',**kwargs)
        for event in old.events:x.on_public_event(event)
        x.observe(35e9,lanes)
        return x,q,lanes

    def test_legal_immediate_gpu_not_reserved_busy_cpu(self):
        x,q,l=self.setup_controller()
        owned=[dict(task='detection',backend='CPU',start=35.,end=35.001)]
        f=t.continuation([q[0]],owned,dict(jobs=[],wait=0.,held=[]),35.,x.means)
        self.assertEqual(f['prediction']['C']['backend'],'GPU')
        self.assertEqual(f['prediction']['C']['start'],35.)

    def test_response_and_actual_lane_boundary_all_arrived_preserved(self):
        x,q,l=self.setup_controller()
        q.append(dict(q[0],id='C2',ordinal=2))
        action=dict(jobs=[dict(request_id='C',backend='CPU')],wait=0.,held=[])
        f=t.continuation(q,[],action,35.,x.means)
        self.assertEqual(set(f['prediction']),{'C','C2','D'})
        self.assertAlmostEqual(f['prediction']['C']['response'],35.+sum(x.means[('classification','CPU')][:2]))
        self.assertGreater(f['prediction']['C2']['start'],f['prediction']['C']['response'])
        self.assertEqual(f['prediction']['C2']['start'],f['prediction']['C']['end'])
        self.assertAlmostEqual(f['prediction']['D']['response']-f['prediction']['D']['start'],sum(x.means[('detection','CPU')][:3]))

    def test_hold_interrupted_only_by_lane_available(self):
        x,q,l=self.setup_controller()
        action=dict(jobs=[],wait=.25,held=['C'])
        owned=[dict(task='detection',backend='CPU',start=35.,end=35.1)]
        f=t.continuation([q[0]],owned,action,35.,x.means)
        self.assertEqual(f['prediction']['C']['start'],35.1)

    def test_forecast_private_future_overrun_and_drain_rejected(self):
        x,q,l=self.setup_controller();a=dict(jobs=[],wait=0.,held=[])
        with self.assertRaises(ValueError):t.continuation([dict(q[0],arrival_ns=36e9)],[],a,35.,x.means)
        with self.assertRaises(c.formula.PredictionUnknown):t.continuation(q,[dict(task='detection',backend='CPU',start=35.,end=35.)],a,35.,x.means)
        with self.assertRaises(c.formula.PredictionUnknown):t.continuation(q,[],a,119.9,x.means)
        with self.assertRaises(ValueError):x.encode([dict(q[0],arrival_ns=36e9)],l,35e9,[])

    def test_same_physical_bank_and_effective_mask(self):
        x,q,l=self.setup_controller();old=c.Controller(x.frozen,x.initial,feature_variant='head2+C_next')
        actions=x.bank(q,l,35e9)
        self.assertEqual(actions,old.bank(q,l,35e9))
        e=x.encode(q,l,35e9,actions)
        self.assertTrue(e['mask'][e['base']]);self.assertFalse((e['mask'] & ~e['physical_mask']).any())
        for i,a in enumerate(actions):
            if 'C' in a['held']:self.assertFalse(e['mask'][i])
        self.assertNotEqual(x.schema_id,old.schema_id)
        self.assertEqual(e['state'].shape,(56,));self.assertEqual(e['candidates'].shape,(8,28))

    def test_grid_and_J_clipping_match_manual_account(self):
        x,q,l=self.setup_controller()
        work=dict(jobs=[dict(task='detection',backend='CPU',start=119.9,end=120.)],drain=120.)
        now=119.9
        x.observe(now*1e9,l)
        score=x.tail_cost(work,now)
        expected=x.initial['preload_power_w']*.1+x.frozen['energy_increment_w']['detection_CPU']*.1
        self.assertAlmostEqual(score['energy'],expected,places=10)
        slopes=x.frozen['ap']['parameters']['ap_slope_at_30_c_per_s']
        u=slopes['detection_CPU']-slopes['resident_idle']
        at120,h=c.p.thermal_step(x.t,x.h,u,x.init['reference_c'],x.frozen['ap'],.1)
        values=[c.p.thermal_step(at120,h,0.,x.init['reference_c'],x.frozen['ap'],float(s-120))[0] for s in range(120,181)]
        self.assertAlmostEqual(score['peak_ap'],max([*x.grid.values(),*values]),places=10)

    def test_sampling_logprob_and_forced_actor_mask(self):
        x,q,l=self.setup_controller(learned=True,network=c.ActorCritic(),deterministic=False)
        x({},q,l,35e9,{},None,None)
        s=x.snapshots[-1]
        dist,_=x.network(torch.from_numpy(s['state'])[None],torch.from_numpy(s['candidates'])[None],torch.from_numpy(s['mask'])[None])
        self.assertAlmostEqual(s['logprob'],float(dist.log_prob(torch.tensor([s['chosen']])).item()),places=7)
        self.assertEqual(s['actor_eligible'],int(s['mask'].sum())>1)
        self.assertTrue(s['physical_mask'][s['chosen']])

    def test_deterministic_zero_actor_ties_to_same_candidate_rule(self):
        x,q,l=self.setup_controller(learned=True,network=c.ActorCritic(),deterministic=True)
        a=x.bank(q,l,35e9);e=x.encode(q,l,35e9,a)
        self.assertEqual(x.choose(e,a,q),e['rule_reference'])

    def test_unknown_means_falls_back_without_zero_cost_claim(self):
        x,q,l=self.setup_controller();l['CPU']=dict(request=q[1],dispatch=34e9,phase=c.PHASES[1],since=34e9)
        a=x.bank([q[0]],l,35e9);e=x.encode([q[0]],l,35e9,a)
        self.assertFalse(e['tail_forecasts'][e['base']]['known'])
        self.assertEqual(int(e['mask'].sum()),1)
        self.assertEqual(x.choose(e,a,[q[0]]),e['base'])

    def test_forced_diagnostic_cannot_train_and_time_must_match(self):
        with self.assertRaises(ValueError):self.setup_controller(learned=True,forced_first=0)
        x,q,l=self.setup_controller()
        with self.assertRaises(ValueError):x.tail_cost(dict(jobs=[],drain=36.),36.)

if __name__=='__main__':unittest.main()
