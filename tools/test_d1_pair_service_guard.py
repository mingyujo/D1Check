import copy
import unittest
from tools import d1_pair_service_guard as g


class GuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.f,case=g.p.inputs(g.p.BUNDLE);cls.i=case['initial']
        cls.e=next(e for e in g.s.envelopes() if e['id']==g.EID)

    def test_lateness_not_just_count(self):
        self.assertEqual(g.worsens({'a':.2},{'a':.1}),['a'])
        self.assertEqual(g.worsens({'a':0},{'a':0}),[])
        self.assertEqual(g.worsens({'a':0},{'a':.1}),[])

    def test_denominator_mismatch_rejected(self):
        with self.assertRaises(ValueError):g.worsens({'a':0},{'b':0})

    def test_actual_engine_guard_and_lane_ownership(self):
        qs=g.s.workload(self.e,123001)[:8]
        row,rr,c,_=g.simulate(self.f,self.i,qs,'mean',g.ID)
        self.assertEqual(row['planned'],8);self.assertEqual(row['completed'],8)
        self.assertTrue(c.guard_records)
        for backend in ('CPU','GPU'):
            jobs=sorted([r for r in rr['ledger'] if r['backend']==backend],key=lambda r:r['dispatch_ns'])
            self.assertTrue(all(a['lane_available_ns']<=b['dispatch_ns'] for a,b in zip(jobs,jobs[1:])))
        for d in c.guard_records:
            self.assertEqual(d['veto'],bool(g.worsens(d['proposed_lateness_s'],d['reference_lateness_s'])))

    def test_no_future_arrival_information(self):
        qs=g.s.workload(self.e,123001)[:8];other=copy.deepcopy(qs);other[-1]['arrival_ns']+=int(1e9)
        _,a,_,_=g.simulate(self.f,self.i,qs,'mean',g.ID)
        _,b,_,_=g.simulate(self.f,self.i,other,'mean',g.ID)
        cutoff=qs[-1]['arrival_ns']
        self.assertEqual([d for d in a['decisions'] if d['now_ns']<cutoff],[d for d in b['decisions'] if d['now_ns']<cutoff])

    def test_existing_policy_exactly_preserved(self):
        qs=g.s.workload(self.e,123001)[:8]
        _,a,_,_=g.simulate(self.f,self.i,qs,'mean','PAIR_COALESCE_V1')
        _,b,_,_=g.s.simulate(self.f,self.i,qs,'mean','PAIR_COALESCE_V1')
        self.assertEqual(a,b)


if __name__=='__main__':unittest.main()
