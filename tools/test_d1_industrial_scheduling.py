import copy
import json
import unittest

from tools import d1_industrial_scheduling as x


def empty():
    return {b:dict(request=None,phase='AVAILABLE',since=0,dispatch=None) for b in ('CPU','GPU')}


class IndustrialTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.frozen,case=x.p.inputs(x.p.BUNDLE); cls.initial=case['initial']
        cls.data=json.loads((x.ROOT/'inputs.json').read_text(encoding='utf8'))
        cls.qs=cls.data['cases'][x.CASES[-1]]['tickets']

    def test_contract_and_input_provenance(self):
        self.assertEqual(json.loads((x.ROOT/'contract.json').read_text(encoding='utf8')),x.specification())
        self.assertEqual(len(self.data['source_sha256']),64)
        if x.SOURCE.exists():
            self.assertEqual(x.p.digest(x.SOURCE),self.data['source_sha256'])
        # Parent file may be absent in a small shared checkout. Its byte audit
        # is explicitly unavailable there; tickets/contract remain verifiable.
        for case in self.data['cases'].values():
            self.assertEqual(case['original_planned'],48)
            self.assertEqual(len(case['tickets']),8)
            self.assertTrue(all(set(q)==set(x.TICKET_FIELDS) for q in case['tickets']))

    def test_real_engine_completion_phases_and_lane(self):
        for method in (x.ATC,x.BOTTLENECK):
            row,rr,c,ss,_=x.simulate(self.frozen,self.initial,self.qs,'mean',method)
            self.assertEqual(row['planned'],8);self.assertEqual(row['completed'],8)
            self.assertEqual([q['arrival_ns'] for q in self.qs],[r['arrival_ns'] for r in rr['ledger']])
            x.validate_schedule(x.jobs_from_ledger(rr['ledger']),self.qs,x.p.profile(self.frozen))
            for r in rr['ledger']:
                stamps=[r[k] for k in ('dispatch_ns',*x.old.engine.FIELDS)]
                self.assertEqual(stamps,sorted(stamps))
            self.assertAlmostEqual(sum(s['end_s']-s['start_s'] for s in ss),180.)
            self.assertTrue(c.records)

    def test_online_prefix_has_no_future_information(self):
        changed=copy.deepcopy(self.qs);changed[-1]['arrival_ns']+=1_000_000_000
        cutoff=self.qs[-1]['arrival_ns']
        for method in (x.ATC,x.BOTTLENECK):
            _,a,_,_,_=x.simulate(self.frozen,self.initial,self.qs,'mean',method)
            _,b,_,_,_=x.simulate(self.frozen,self.initial,changed,'mean',method)
            self.assertEqual([d for d in a['decisions'] if d['now_ns']<cutoff],
                             [d for d in b['decisions'] if d['now_ns']<cutoff])

    def test_private_lanes_and_future_ticket_rejected(self):
        c=x.Controller(self.frozen,self.initial,x.ATC)
        with self.assertRaises(ValueError):c({},[self.qs[0]],empty(),34e9,x.settings(),None,None)
        lanes=empty();lanes['CPU']['left']=1
        with self.assertRaises(ValueError):c({},[self.qs[0]],lanes,35e9,x.settings(),None,None)

    def test_guard_preserves_individual_lateness_not_only_count(self):
        self.assertEqual(x.guard_worsens({'a':.2,'b':0},{'a':.1,'b':0}),['a'])
        with self.assertRaises(ValueError):x.guard_worsens({'a':0},{'b':0})
        for method in (x.ATC,x.BOTTLENECK):
            _,_,c,_,_=x.simulate(self.frozen,self.initial,self.qs,'mean',method)
            self.assertTrue(all(v['guard_veto']==bool(v['worsened_ids']) for r in c.records for v in r['candidates']))

    def test_unknown_active_overrun_is_not_zero_work(self):
        c=x.Controller(self.frozen,self.initial,x.BOTTLENECK)
        lanes=empty();lanes['CPU']=dict(request=self.qs[0],phase='EXECUTING',since=35e9,dispatch=35e9)
        result=c({},[self.qs[1]],lanes,50e9,x.settings(),None,None)
        self.assertIsNone(result['selected']);self.assertEqual(result['reason'],'unknown_overrun_wait_for_event')

    def test_offline_search_calendar_replays_through_engine(self):
        qs=self.qs[:4]
        _,rr,_,_,_=x.simulate(self.frozen,self.initial,qs,'mean','EFT_REFERENCE')
        winners,stats=x.search(self.frozen,self.initial,qs,'mean',[x.jobs_from_ledger(rr['ledger'])],width=8,timeout=10.)
        self.assertFalse(stats['optimality_proved']);self.assertFalse(stats['lower_bound'])
        self.assertEqual(stats['depth_completed'],4)
        for plan in winners.values():
            x.validate_schedule(plan,qs,x.p.profile(self.frozen))
            row,replay,_,_,_=x.simulate(self.frozen,self.initial,qs,'mean',x.REPLAY,plan)
            self.assertEqual(row['completed'],4)
            for j in plan:
                r=next(r for r in replay['ledger'] if r['id']==j['id'])
                self.assertAlmostEqual(r['dispatch_ns']/1e9,j['start'],places=8)

    def test_timeout_preserves_incumbent_not_fake_optimum(self):
        _,rr,_,_,_=x.simulate(self.frozen,self.initial,self.qs,'mean','EFT_REFERENCE')
        jobs=x.jobs_from_ledger(rr['ledger'])
        winners,stats=x.search(self.frozen,self.initial,self.qs,'mean',[jobs],timeout=0.)
        self.assertTrue(stats['timed_out']);self.assertEqual(stats['depth_completed'],0)
        self.assertFalse(stats['optimality_proved'])
        self.assertEqual(winners['energy'],jobs)

    def test_calendar_rejects_missing_and_unsupported_or_early_work(self):
        _,rr,_,_,_=x.simulate(self.frozen,self.initial,self.qs,'mean','EFT_REFERENCE')
        jobs=x.jobs_from_ledger(rr['ledger']);profile=x.p.profile(self.frozen)
        with self.assertRaises(ValueError):x.validate_schedule(jobs[:-1],self.qs,profile)
        wrong=copy.deepcopy(jobs);wrong[0]['backend']='GPU'
        with self.assertRaises(ValueError):x.validate_schedule(wrong,self.qs,profile)
        early=copy.deepcopy(jobs);early[0]['start']-=1
        with self.assertRaises(ValueError):x.validate_schedule(early,self.qs,profile)

    def test_common_energy_accounting_matches_existing(self):
        row,rr,_,_,cost=x.simulate(self.frozen,self.initial,self.qs,'mean','EFT_REFERENCE')
        _,original=x.old.simulate(self.frozen,self.initial,self.qs,'mean','EFT_REFERENCE',seed=201)[:2]
        self.assertEqual(rr,original)
        _,before,_=x.p.account(rr,self.initial,self.frozen)
        self.assertAlmostEqual(row['energy_j'],before['whole_120s_j'],places=10)
        self.assertEqual(cost['ap_path'],before['ap_path'])

    def test_frozen_and_initial_hashes_unchanged(self):
        before=json.dumps(self.frozen,sort_keys=True)
        x.simulate(self.frozen,self.initial,self.qs,'long_context',x.ATC)
        self.assertEqual(json.dumps(self.frozen,sort_keys=True),before)
        self.assertEqual(x.p.digest(x.p.BUNDLE/'model.json'),x.p.MODEL_SHA)
        self.assertEqual(x.p.digest(x.p.BUNDLE/'initial_inputs.json'),x.p.INITIAL_SHA)

    def test_strict_entry_cannot_use_new_methods(self):
        c=x.Controller(self.frozen,self.initial,x.ATC)
        vectors=dict(cells={k:[dict(durations_ns=d) for _ in range(4)] for k,d in x.p.profile(self.frozen).items()})
        strict=x.settings();strict['mode']='strict'
        with self.assertRaises(ValueError):x.old.engine.simulate(dict(protocol=x.p.VERSION,cells=x.p.profile(self.frozen)),
            vectors,self.qs,policy=x.ATC,settings=strict,seed=201,decision_provider=c)


if __name__=='__main__':unittest.main()
