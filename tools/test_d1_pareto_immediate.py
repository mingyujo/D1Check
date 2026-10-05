import json
import unittest
from tools import d1_pareto_beam_immediate as b
x=b.x


class ImmediateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.frozen,case=x.p.inputs(x.p.BUNDLE);cls.initial=case['initial']
        cls.qs=json.loads((x.ROOT/'inputs.json').read_text(encoding='utf8'))['cases'][x.CASES[-1]]['tickets']

    def test_actual_entry_no_voluntary_deferral(self):
        row,rr,c,_,_=b.simulate(self.frozen,self.initial,self.qs,'mean')
        self.assertEqual(row['completed'],8);self.assertEqual(row['wait_actions'],0)
        for decision in rr['decisions']:
            if decision['reason']==b.POLICY:
                self.assertIsNotNone(decision['selected'])
                self.assertEqual(decision['chosen_explicit_delay_s'],0)
        x.validate_schedule(x.jobs_from_ledger(rr['ledger']),self.qs,x.p.profile(self.frozen))

    def test_first_future_start_rejected_not_fake_lane_release(self):
        c=b.Controller(self.frozen,self.initial);jobs,first=c.finish_plan(((self.qs[0]['id'],'CPU',.25),),self.qs,[],35.,c)
        self.assertIsNone(c.score(jobs,35.));self.assertFalse(first['_immediate_first'])

    def test_parent_policy_and_frozen_preserved(self):
        self.assertEqual(b.parent.POLICY,'PARETO_BEAM_SERVICE_V1')
        self.assertEqual(x.p.digest(x.p.BUNDLE/'model.json'),x.p.MODEL_SHA)
        self.assertEqual(x.p.digest(x.p.BUNDLE/'initial_inputs.json'),x.p.INITIAL_SHA)


if __name__=='__main__':unittest.main()
