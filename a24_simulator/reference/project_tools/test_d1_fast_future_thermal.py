"""Exact cost equivalence and causal virtual-arrival hand cases, zero engines."""
import copy,unittest
from tools import d1_fast_thermal_forecast as fast
from tools import d1_future_thermal_v4 as future
from tools.test_d1_thermal_slack_v3 import controller
from tools.test_d1_ie_dispatch import ticket,lanes

class FastFutureTests(unittest.TestCase):
    def test_light_band_projection_exact_all_phase_contexts(self):
        c=controller();ls=lanes();c.observe(35e9,ls)
        qs=[ticket('d0',0,'detection',35.,6.),ticket('c0',1),ticket('d1',2,'detection',35.,6.),ticket('c1',3)]
        for ctx in fast.old.core.CONTEXTS:
            for action in (dict(jobs=[]),dict(jobs=[],wait_until_ns=35.25e9),dict(jobs=[dict(request_id='c0',backend='GPU'),dict(request_id='d0',backend='CPU')])):
                old=fast.old.project_band(c.estimates,c.profiles,qs,ls,35e9,action,ctx,c.band)
                new=fast.project(c.estimates,c.profiles,qs,ls,35e9,action,ctx,c.band)
                self.assertEqual(old,new)
                before=copy.deepcopy(c.band.__dict__);a=fast.old.Controller.forecast(c,qs,ls,35e9,action,ctx);b=fast.forecast(c,qs,ls,35e9,action,ctx)
                for field in ('peak_ap_c','global_peak_ap_c','remaining_increment_j','urgent_p95_ms','normal_margin','urgent_margin'):self.assertAlmostEqual(a[field],b[field],places=9)
                self.assertEqual(c.band.__dict__,before)

    def test_linear_formula_nonzero_memory_equal_and_unequal_poles(self):
        c=controller();c.observe(35e9,lanes());qs=[ticket('d',0,'detection',35.,6.)];action=dict(jobs=[],wait_until_ns=35.25e9)
        c.t=29.8;c.h=.004;c.frozen=copy.deepcopy(c.frozen)
        for beta in (.025,1/30.):
            c.frozen['ap'].update(beta=beta,g=.4)
            a=fast.old.Controller.forecast(c,qs,lanes(),35e9,action,'mean');b=fast.forecast(c,qs,lanes(),35e9,action,'mean')
            self.assertAlmostEqual(a['peak_ap_c'],b['peak_ap_c'],places=9)

    def test_public_running_phase_is_not_rewound_or_released_early(self):
        c=controller();ls=lanes();q=ticket('d',0,'detection',35.,6.);ls['CPU']=dict(request=q,phase='EXECUTING',since=35.001e9,dispatch=35e9)
        c.observe(35.01e9,ls);qs=[ticket('c',1,arrival=35.01)];action=dict(jobs=[])
        a=fast.old.project_band(c.estimates,c.profiles,qs,ls,35.01e9,action,'mean',c.band);b=fast.project(c.estimates,c.profiles,qs,ls,35.01e9,action,'mean',c.band);self.assertEqual(a,b)

    def test_virtual_arrival_does_not_dispatch_before_arrival(self):
        c=controller();c.observe(35e9,lanes());qs=[ticket('d',0,'detection',35.,6.)];probe=ticket('__probe',1,arrival=35.1)
        result=fast.project(c.estimates,c.profiles,qs,lanes(),35e9,dict(jobs=[],wait_until_ns=36e9),'mean',c.band,[probe])
        self.assertEqual(min(j['at_ns'] for j in result['dispatches']),35100000000)
        self.assertGreaterEqual(next(j['at_ns'] for j in result['dispatches'] if j['request_id']=='__probe'),probe['arrival_ns'])

    def test_invalid_virtual_arrival_is_not_known_queue(self):
        c=controller();c.observe(35e9,lanes())
        with self.assertRaises(fast.ProjectionUnavailable):fast.project(c.estimates,c.profiles,[],lanes(),35e9,dict(jobs=[]),'mean',c.band,[ticket('bad',0,arrival=35.)])

    def test_scenarios_use_only_observed_gaps_and_tasks(self):
        base=controller();c=future.Controller(base.frozen,base.initial,future.ROBUST)
        self.assertEqual(c.scenarios(35e9),[])
        for i,t in enumerate((35.,36.18,37.4)):c.observations[str(i)]=ticket(str(i),i,'detection',t,6.)
        scenarios=c.scenarios(37.4e9);self.assertEqual(len(scenarios),5);self.assertAlmostEqual(sum(s['weight'] for s in scenarios),1.)
        self.assertEqual({s['probes'][0]['arrival_ns'] for s in scenarios if s['probes']},{38580000000,38620000000})
        self.assertTrue(all(q['arrival_ns']>37.4e9 for s in scenarios for q in s['probes']))
        c.observations['same']=ticket('same',4,'detection',37.4,6.);self.assertEqual(c.scenarios(37.4e9),[])

    def test_future_probe_does_not_change_known_urgent_P95_denominator(self):
        c=controller();c.observe(35e9,lanes());c.observed_responses={str(i):dict(priority='urgent',response_ms=10.+i,failed=False) for i in range(19)}
        q=ticket('d',0,'detection',35.,6.);probe=ticket('__probe',1,arrival=35.1)
        f=fast.forecast(c,[q],lanes(),35e9,dict(jobs=[]),'mean',[probe]);self.assertEqual(f['urgent_p95_ms'],28.);self.assertIn('__probe',f['probe_urgent_ms'])

    def test_real_future_ticket_rejected(self):
        base=controller();c=future.Controller(base.frozen,base.initial,future.ROBUST)
        with self.assertRaises(ValueError):c.decide({},[ticket('future',0,arrival=36.)],lanes(),35e9,{},None,None)

if __name__=='__main__':unittest.main()
