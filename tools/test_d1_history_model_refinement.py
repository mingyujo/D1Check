import copy
import unittest
import numpy as np
from tools import d1_history_model_refinement as r


class HistoryRefinementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases=r.m.read(r.BUNDLE/'inputs.json.gz')
        cls.dev=[x for x in cls.cases if x['role']=='development']
        cls.frozen=r.m.read(r.m.MODEL)

    def test_original_reproduced_at_zero_penalty(self):
        for c in self.cases:
            old,_=r.m.thermal.predict(dict(inputs=r.inputs(c)),self.frozen['ap'])
            new,_=r.ap_prediction(r.inputs(c),self.frozen)
            np.testing.assert_allclose(old,new,atol=1e-12,rtol=0)
            predj=r.energy_prediction(r.features(c),c['actual'],self.frozen,dict(alpha=0.,gain=1.),120)
            self.assertAlmostEqual(predj,r.m.energy_prediction(c,c['actual'],self.frozen,dict(name='FROZEN'),120),places=10)

    def test_preload_and_future_information_boundary(self):
        c=copy.deepcopy(self.dev[1]);public=r.inputs(c);features=r.features(c)
        old=r.ap_prediction(public,self.frozen,.1)[0]
        c['ap']=[999]*len(c['ap'])
        c['power_w']=[w if t<35 else 999 for t,w in zip(c['power_t'],c['power_w'])]
        self.assertEqual(features,r.features(c))
        self.assertEqual(old,r.ap_prediction(r.inputs(c),self.frozen,.1)[0])
        public['preload'][-1]['hi']=35
        with self.assertRaises(ValueError):r.ap_prediction(public,self.frozen,.1)

    def test_development_only_fit_and_unidentified_zero_trend(self):
        with self.assertRaises(ValueError):r.fit_energy([self.cases[-1]],self.frozen)
        changed=copy.deepcopy(self.dev)
        for c in changed:
            if c['policy']=='C0':c['power_w']=[c['pre_w']]*len(c['power_w'])
        with self.assertRaisesRegex(ValueError,'idle coefficient unidentified'):r.fit_energy(changed,self.frozen)

    def test_fit_no_evaluation_dependency(self):
        first=r.fit_energy(self.dev,self.frozen)
        changed=copy.deepcopy(self.cases)
        for c in changed:
            if c['role']!='development':
                c['ap']=[1000]*len(c['ap']);c['power_w']=[1000]*len(c['power_w'])
        second=r.fit_energy([c for c in changed if c['role']=='development'],self.frozen)
        self.assertEqual(first,second)

    def test_integration_partition_and_missing_values(self):
        coef=r.fit_energy(self.dev,self.frozen)
        score,_,_,windows=r.evaluate(self.dev[1],self.frozen,coef,.1)
        self.assertAlmostEqual(sum(score[k+'_signed_j'] for k in ('pre','load','post')),score['signed_j'],places=9)
        self.assertAlmostEqual(sum(x['signed_j'] for x in windows),score['signed_j'],places=9)
        bad=copy.deepcopy(self.dev[1]);bad['power_w'][next(i for i,t in enumerate(bad['power_t']) if t>60)]=None
        with self.assertRaises(ValueError):r.evaluate(bad,self.frozen,coef)

    def test_candidate_initialization_continuity_and_fixed_comparator(self):
        c=self.dev[2];p,init=r.ap_prediction(r.inputs(c),self.frozen,.1)
        self.assertEqual(init['anchor_ap_c'],c['pre'][-1]['ap'])
        query={'preload':c['pre'],'segments':c['actual'],'query_s':[35.]}
        first=r.ap_prediction(query,self.frozen,.1)[0][0]
        dense={'preload':c['pre'],'segments':c['actual'],'query_s':[35.,36.]}
        self.assertEqual(first,r.ap_prediction(dense,self.frozen,.1)[0][0])
        changed=copy.deepcopy(self.frozen['ap']);changed['g']=r.FIXED_G
        expected,_=r.m.thermal.predict(dict(inputs=r.inputs(c)),changed)
        actual,_=r.ap_prediction(r.inputs(c),self.frozen,fixed_g=r.FIXED_G)
        np.testing.assert_allclose(expected,actual,rtol=0,atol=1e-12)

    def test_nonpositive_energy_and_unsupported_state(self):
        with self.assertRaises(ValueError):r.energy_prediction(dict(pre_w=1.,trend_w=1.),self.dev[1]['actual'],self.frozen,dict(alpha=-2.,gain=1.),120)
        c=copy.deepcopy(self.dev[1]);c['actual'][0]['state']='unsupported'
        with self.assertRaises(ValueError):r.ap_prediction(r.inputs(c),self.frozen,.1)
        self.assertEqual(r.m.sha(r.m.MODEL),r.m.MODEL_SHA)

    def test_duplicate_missing_cells_and_heldout_fit_guard(self):
        contract=r.m.read(r.BUNDLE/'contract.json')
        duplicate=copy.deepcopy(self.dev);duplicate[-1]=copy.deepcopy(duplicate[0])
        with self.assertRaises(ValueError):r.freeze(duplicate,self.frozen,contract)
        evaluation=copy.deepcopy(self.dev);evaluation[-1]['role']='confirmation'
        with self.assertRaises(ValueError):r.freeze(evaluation,self.frozen,contract)


if __name__=='__main__':unittest.main()
