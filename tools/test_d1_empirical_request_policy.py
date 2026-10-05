import copy
import json
import unittest
from tools import d1_empirical_request_policy as p
from tools import d1_arrival_explore as engine, d1_arrival_explore_batch as batch
from tools import d1_ap_completion_model as ap


def empty():
    return {b:dict(request=None,phase='AVAILABLE',since=0,dispatch=None) for b in ('CPU','GPU')}


class EmpiricalRequestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.frozen,cls.case=p.inputs(p.BUNDLE)
        cls.initial=cls.case['initial']; cls.means=p.profile(cls.frozen)
        cls.config=dict(protocol=p.VERSION,cells=cls.means)
        cls.settings=batch.defaults('explore')
        cls.settings.update(interference=1.,predicted_interference=1.,decision_ns=0,record_ns=0,dispatch_ns=0)

    def controller(self, policy='ENERGY_AP_REQUEST_V1'):
        return p.Controller(self.frozen,self.initial,self.means,policy)

    def tickets(self,name='queue'):
        return [dict(q,arrival_ns=q['arrival_ns']+35e9) for q in batch.workload(name,'evaluation')]

    def simulate(self, policy, scenario='mean', tickets=None):
        actual=p.profile(self.frozen,scenario)
        vectors=dict(cells={k:[dict(source_request_id='fixture',durations_ns=v) for _ in range(4)] for k,v in actual.items()})
        return engine.simulate(self.config,vectors,tickets or self.tickets(),policy=policy,settings=self.settings,
                               seed=201,decision_provider=self.controller(policy))

    def test_frozen_and_sources_unchanged(self):
        before=json.dumps(self.frozen,sort_keys=True)
        p.profile(self.frozen,'short_context');p.profile(self.frozen,'long_context')
        self.simulate('ENERGY_AP_REQUEST_V1')
        self.assertEqual(before,json.dumps(self.frozen,sort_keys=True))
        self.assertEqual(p.digest(p.BUNDLE/'model.json'),p.MODEL_SHA)

    def test_common_profile_preserves_whole_context_vectors(self):
        for key in p.CELLS:
            rows=[s['phase_means_ns'][key] for s in self.frozen['service'].values() if key in s['phase_means_ns']]
            self.assertIn(p.profile(self.frozen,'short_context')[key],rows)
            self.assertIn(p.profile(self.frozen,'long_context')[key],rows)
        self.assertEqual(len(p.POLICIES),5)

    def test_unknown_cells_and_pairs_rejected(self):
        with self.assertRaises(ValueError):p.backends(dict(task='detection',priority='urgent'))
        with self.assertRaises(ValueError):p.state(['classification_CPU','classification_GPU'])
        c=self.controller();q=self.tickets()[1]
        job=dict(state='classification_GPU',backend='GPU',start=35.,end=36.)
        self.assertGreaterEqual(c.place(q,'CPU',35.,[job])['start'],36.)

    def test_actual_entry_complete_ownership_and_independent_arrivals(self):
        for policy in p.POLICIES:
            r=self.simulate(policy)
            self.assertEqual(len(r['ledger']),24)
            self.assertTrue(all(x['status']=='succeeded' for x in r['ledger']))
            self.assertEqual([x['arrival_ns'] for x in r['ledger']],[q['arrival_ns'] for q in self.tickets()])
            for b in ('CPU','GPU'):
                jobs=sorted((x for x in r['ledger'] if x['backend']==b),key=lambda x:x['dispatch_ns'])
                self.assertTrue(all(a['lane_available_ns']<=b['dispatch_ns'] for a,b in zip(jobs,jobs[1:])))
            for x in r['ledger']:
                stamps=[x[k] for k in ('dispatch_ns',*engine.FIELDS)]
                self.assertEqual(stamps,sorted(stamps))

    def test_future_arrivals_do_not_change_decision_prefix(self):
        a=self.tickets();b=copy.deepcopy(a);b[-1]['arrival_ns']+=10e9
        ra=self.simulate('ENERGY_AP_REQUEST_V1',tickets=a);rb=self.simulate('ENERGY_AP_REQUEST_V1',tickets=b)
        cutoff=a[-1]['arrival_ns']
        self.assertEqual([d for d in ra['decisions'] if d['now_ns']<cutoff],
                         [d for d in rb['decisions'] if d['now_ns']<cutoff])

    def test_no_private_lane_or_future_ticket_input(self):
        c=self.controller();q=self.tickets()[0]
        with self.assertRaises(ValueError):c(self.config,[q],empty(),34e9,self.settings,None,None)
        lanes=empty();lanes['CPU']['left']=100
        with self.assertRaises(ValueError):c(self.config,[q],lanes,35e9,self.settings,None,None)

    def test_unknown_overrun_not_zero(self):
        c=self.controller();lanes=empty();q=self.tickets()[0]
        lanes['CPU']=dict(request=q,phase='EXECUTING',since=35e9,dispatch=35e9)
        c.observe(40e9,lanes)
        d=c(self.config,[self.tickets()[1]],lanes,40e9,self.settings,None,None)
        self.assertIsNone(d['selected']);self.assertEqual(d['reason'],'unknown_overrun_wait_for_event')

    def test_ap_step_matches_existing_frozen_equation(self):
        c=self.controller();ss=[dict(start_s=0.,end_s=35.,state='idle'),
            dict(start_s=35.,end_s=36.,state='classification_GPU'),dict(start_s=36.,end_s=180.,state='idle')]
        grid=list(range(35,181))
        path,_=ap.predict(dict(inputs=dict(preload=self.initial['preload'],query_s=grid,segments=ss)),self.frozen['ap'])
        expected=[path[0],path[1],path[-1]]
        now=c.init['anchor_s'];t,h=c.t,c.h;vals=[]
        for end,label in ((35.,'resident_idle'),(36.,'classification_GPU'),(180.,'resident_idle')):
            slopes=self.frozen['ap']['parameters']['ap_slope_at_30_c_per_s']
            t,h=p.thermal_step(t,h,slopes[label]-slopes['resident_idle'],c.init['reference_c'],self.frozen['ap'],end-now)
            vals.append(t);now=end
        for a,b in zip(expected,vals):self.assertAlmostEqual(a,b,places=10)

    def test_energy_conservation_reordering_and_common_horizon(self):
        c=self.controller();c.observe(35e9,empty())
        jobs=[dict(id='a',state='classification_CPU',backend='CPU',start=35.,end=36.,response=36.,deadline=40.,already_responded=False)]
        shifted=copy.deepcopy(jobs);shifted[0].update(start=36.,end=37.,response=37.)
        self.assertAlmostEqual(c.score(jobs,35.)['remaining_energy_j'],c.score(shifted,35.)['remaining_energy_j'],places=10)
        jobs[0]['end']=121.
        self.assertIsNone(c.score(jobs,35.))

    def test_no_backfill_before_deferred_head(self):
        c=self.controller();q=self.tickets()[0:2]
        jobs,first=c.rollout(q,[],'CPU',.25,36.)
        self.assertTrue(all(j['start']>=first['start'] for j in jobs))

    def test_delayed_start_still_observes_wait_limit(self):
        r=self.simulate('ENERGY_AP_REQUEST_V1')
        tickets={q['id']:q for q in self.tickets()}
        # Every selected voluntary delay is bounded relative to arrived head, not reset by wakeup.
        for d in r['decisions']:
            if d.get('chosen_explicit_delay_s',0)>0:
                self.assertLessEqual(d['chosen_explicit_delay_s'],.25)
                age=d['now_ns']/1e9-tickets[d['head_request_id']]['arrival_ns']/1e9
                self.assertLessEqual(age+d['chosen_explicit_delay_s'],2.+1e-8)
        self.assertEqual(r['metrics']['planned'],24)

    def test_context_sensitivity_does_not_change_policy_estimates(self):
        for scenario in ('short_context','long_context'):
            r=self.simulate('ENERGY_AP_REQUEST_V1',scenario)
            self.assertEqual(len(r['ledger']),24)
        self.assertEqual(self.config['cells'],self.means)

    def test_existing_policy_selection_guard_preserved(self):
        from tools.d1_separated_power_readout import decision_support
        with self.assertRaises(ValueError):decision_support('energy-ap-policy-selection')

    def test_unfinished_has_no_invented_cooling(self):
        result=dict(ledger=[dict(task='detection',backend='CPU',dispatch_ns=119e9,status='unfinished')])
        ss,costs,end=p.account(result,self.initial,self.frozen)
        self.assertEqual(end,120);self.assertEqual(ss[-1]['state'],'detection_CPU')
        self.assertEqual(len(costs['ap_path']),86)
        self.assertEqual(costs['energy_path'][-1]['common_s'],120)

    def test_controller_observation_equals_offline_ap(self):
        c=self.controller();lanes=empty()
        c.observe(35e9,lanes)
        q=self.tickets()[1];lanes['GPU']=dict(request=q,phase='EXECUTING',since=35e9,dispatch=35e9)
        c.observe(35e9,lanes);c.observe(36e9,empty());c.observe(180e9,empty())
        vals,_=ap.predict(dict(inputs=dict(preload=self.initial['preload'],query_s=list(range(35,181)),segments=c.history)),self.frozen['ap'])
        self.assertAlmostEqual(c.t,vals[-1],places=10)


if __name__=='__main__':unittest.main()
