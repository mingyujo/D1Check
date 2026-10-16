import copy
import unittest
import tempfile
from pathlib import Path
from tools import d1_scheduler_conditions as s
from tools import d1_request_ppo as rl
from tools.test_d1_empirical_request_policy import empty


class ConditionsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.f,case=s.p.inputs(s.p.BUNDLE);cls.initial=case['initial']

    def test_grid_and_split(self):
        spec=s.specification()
        self.assertEqual(27*5*3*len(s.POLICIES),spec['runs'])
        self.assertFalse(set(spec['development_seeds'])&set(spec['test_seeds']))
        for e in s.envelopes():
            qs=s.workload(e,123)
            self.assertEqual(len(qs),48)
            self.assertEqual(sum(q['task']=='classification' for q in qs),48*e['class_share'])
            self.assertTrue(all(35e9<=q['arrival_ns']<120e9 for q in qs))
            self.assertEqual(qs,s.workload(e,123))

    def test_csv_heterogeneous_instrumentation(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'x.csv'
            s.save_rows(path,[dict(policy='a',energy=1),dict(policy='b',energy=2,decision_calls=4)])
            self.assertIn('decision_calls',path.read_text(encoding='utf8'))

    def test_actual_entry_new_policies_lane_and_denominator(self):
        qs=s.workload(s.envelopes()[0],17)[:8]
        for policy in s.NEW:
            row,r,_,_=s.simulate(self.f,self.initial,qs,'mean',policy)
            self.assertEqual(row['planned'],8);self.assertEqual(row['completed'],8)
            self.assertEqual([r['arrival_ns'] for r in r['ledger']],[q['arrival_ns'] for q in qs])
            for b in ('CPU','GPU'):
                jobs=sorted([x for x in r['ledger'] if x['backend']==b],key=lambda x:x['dispatch_ns'])
                self.assertTrue(all(x['lane_available_ns']<=y['dispatch_ns'] for x,y in zip(jobs,jobs[1:])))

    def test_future_input_not_visible(self):
        qs=s.workload(s.envelopes()[-1],18)[:8];other=copy.deepcopy(qs)
        other[-1]['arrival_ns']+=1e9
        for policy in s.NEW:
            _,a,_,_=s.simulate(self.f,self.initial,qs,'mean',policy)
            _,b,_,_=s.simulate(self.f,self.initial,other,'mean',policy)
            self.assertEqual([x for x in a['decisions'] if x['now_ns']<qs[-1]['arrival_ns']],
                             [x for x in b['decisions'] if x['now_ns']<qs[-1]['arrival_ns']])

    def test_invalid_future_ticket_rejected(self):
        c=s.Controller(self.f,self.initial,'JIT_CPU_V1')
        with self.assertRaises(ValueError):
            c({},s.workload(s.envelopes()[0],1),empty(),34e9,rl.settings(),None,None)

    def test_tokens_not_debited_during_wait_and_bound(self):
        c=s.Controller(self.f,self.initial,'TOKEN_CPU_V1');c.tokens=0.
        q=s.workload(s.envelopes()[0],1)[0];q.update(task='detection',priority='normal',deadline_offset_ns=6e9)
        c.observe(35e9,empty())
        decision=c({},[q],empty(),35e9,rl.settings(),None,None)
        self.assertIsNone(decision['selected']);self.assertEqual(c.tokens,0.)
        self.assertLessEqual(decision['wait_until_ns'],37e9)
        decision=c({},[q],empty(),37e9,rl.settings(),None,None)
        self.assertIsNotNone(decision['selected'])

    def test_no_saving_for_failed_or_missing(self):
        base=dict(planned=48,completed=48,deadline_met=48,energy_j=200.,peak_ap_c=35.,thermal_degree_seconds=100.)
        self.assertFalse(s.useful(base,base))
        self.assertTrue(s.useful(dict(base,energy_j=199.),base))
        self.assertFalse(s.useful(dict(base,energy_j=199.,deadline_met=47),base))
        self.assertFalse(s.useful(dict(base,energy_j=199.,peak_ap_c=None),base))

    def test_frozen_physics_and_original_deadlines(self):
        self.assertEqual(s.p.digest(s.p.BUNDLE/'model.json'),s.p.MODEL_SHA)
        self.assertEqual(s.p.digest(s.p.BUNDLE/'initial_inputs.json'),s.p.INITIAL_SHA)
        for q in s.workload(s.envelopes()[0],1):
            self.assertEqual(q['deadline_offset_ns'],1.5e9 if q['priority']=='urgent' else 6e9)


if __name__=='__main__':unittest.main()
