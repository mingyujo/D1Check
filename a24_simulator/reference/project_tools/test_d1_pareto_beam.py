import copy
import json
import unittest
from tools import d1_pareto_beam as b
x=b.x


class BeamTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.frozen,case=x.p.inputs(x.p.BUNDLE);cls.initial=case['initial']
        cls.qs=json.loads((x.ROOT/'inputs.json').read_text(encoding='utf8'))['cases'][x.CASES[-1]]['tickets']

    def test_real_callbacks_preserve_ownership_and_denominator(self):
        row,rr,c,_,_=b.simulate(self.frozen,self.initial,self.qs,'mean')
        self.assertEqual(row['planned'],8);self.assertEqual(row['completed'],8)
        x.validate_schedule(x.jobs_from_ledger(rr['ledger']),self.qs,x.p.profile(self.frozen))
        for r in c.records:
            self.assertLessEqual(r['expanded'],64)
            if 'prediction' in r:
                self.assertLessEqual(r['prediction']['remaining_energy_j'],r['reference']['remaining_energy_j']+1e-9)
                self.assertLessEqual(r['prediction']['predicted_peak_ap_c'],r['reference']['predicted_peak_ap_c']+1e-9)

    def test_future_completion_or_arrival_is_not_online_input(self):
        changed=copy.deepcopy(self.qs);changed[-1]['arrival_ns']+=1_000_000_000;cutoff=self.qs[-1]['arrival_ns']
        _,a,_,_,_=b.simulate(self.frozen,self.initial,self.qs,'mean')
        _,c,_,_,_=b.simulate(self.frozen,self.initial,changed,'mean')
        self.assertEqual([r for r in a['decisions'] if r['now_ns']<cutoff],[r for r in c['decisions'] if r['now_ns']<cutoff])

    def test_strict_and_private_lane_rejected(self):
        c=b.Controller(self.frozen,self.initial);lanes={z:dict(request=None,phase='AVAILABLE',since=0,dispatch=None) for z in ('CPU','GPU')}
        lanes['CPU']['future_duration']=1
        with self.assertRaises(ValueError):c({},self.qs[:1],lanes,35e9,x.settings(),None,None)
        vectors=dict(cells={k:[dict(durations_ns=v) for _ in range(4)] for k,v in x.p.profile(self.frozen).items()})
        settings=x.settings();settings['mode']='strict'
        with self.assertRaises(ValueError):x.old.engine.simulate(dict(protocol=x.p.VERSION,cells=x.p.profile(self.frozen)),
            vectors,self.qs,policy=b.POLICY,settings=settings,seed=201,decision_provider=c)

    def test_frozen_coefficients_unchanged(self):
        self.assertEqual(x.p.digest(x.p.BUNDLE/'model.json'),x.p.MODEL_SHA)
        self.assertEqual(x.p.digest(x.p.BUNDLE/'initial_inputs.json'),x.p.INITIAL_SHA)


if __name__=='__main__':unittest.main()
