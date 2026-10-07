import copy
import unittest
import numpy as np
from tools import d1_model_refinement as m
from tools import d1_model_robust_gain as g


class RobustTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases=m.read(m.BUNDLE/'inputs.json.gz');cls.frozen=m.read(m.MODEL)
        cls.train=[c for c in cls.cases if c['block']!='sustained'];cls.ids={c['id'] for c in cls.train}

    def test_role_and_duplicate_guard(self):
        with self.assertRaises(ValueError):g.fit([self.cases[-1]],self.frozen,self.ids)
        with self.assertRaises(ValueError):g.fit([self.train[0]]*2,self.frozen,self.ids)

    def test_late_training_targets_do_not_fit(self):
        before=g.fit(self.train,self.frozen,self.ids);changed=copy.deepcopy(self.train)
        for c in changed:
            c['ap']=[v if t<=c['last_lane_s'] else v+100 for t,v in zip(c['q'],c['ap'])]
            c['power_w']=[v if t<=c['last_lane_s']+2 else v+100 for t,v in zip(c['power_t'],c['power_w'])]
        self.assertEqual(before,g.fit(changed,self.frozen,self.ids))

    def test_eval_targets_do_not_predict_or_mutate_frozen(self):
        original=copy.deepcopy(self.frozen);mod=g.model(self.frozen,g.fit(self.train,self.frozen,self.ids))
        c=self.cases[-1];d=copy.deepcopy(c);d['ap']=[100.]*len(d['ap']);d['power_w']=[999.]*len(d['power_w'])
        np.testing.assert_array_equal(m.predict(c,c['actual'],mod,{'name':'FROZEN'})[0],m.predict(d,d['actual'],mod,{'name':'FROZEN'})[0])
        self.assertEqual(m.energy_prediction(c,c['actual'],mod,{'name':'FROZEN'},120),m.energy_prediction(d,d['actual'],mod,{'name':'FROZEN'},120))
        self.assertEqual(self.frozen,original);self.assertEqual(m.sha(m.MODEL),m.MODEL_SHA)

    def test_identity_partition_and_pre_features(self):
        mod=g.model(self.frozen,{'energy_gain':1.,'k':self.frozen['ap']['k']})
        self.assertEqual(mod,self.frozen)
        c=self.cases[-1];r,_,_=m.metrics(c,c['actual'],mod,{'name':'FROZEN'})
        self.assertAlmostEqual(r['signed_j'],sum(r[k+'_signed_j'] for k in ('pre','load','post')))
        d=copy.deepcopy(c);d['ap']=[100.]*len(d['ap']);d['power_w']=[v if t<35 else 999. for t,v in zip(d['power_t'],d['power_w'])]
        self.assertEqual(g.features(c),g.features(d))


if __name__=='__main__':unittest.main()
