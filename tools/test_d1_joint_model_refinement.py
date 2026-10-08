import copy
import unittest
from unittest.mock import patch
from tools import d1_joint_model_refinement as j


class JointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases,cls.duplicates=j.panel();cls.original=j.m.read(j.m.MODEL)

    def test_panel_denominator_and_exact_dedup(self):
        self.assertEqual(len(self.cases),29);self.assertEqual(len(self.duplicates),8)
        self.assertEqual(sum(c['role']=='development' for c in self.cases),9)
        bad=j.m.read(j.SOURCES[1]);bad[-1]['power_w'][0]+=1
        real=j.m.read
        with patch.object(j.m,'read',side_effect=lambda p:bad if p==j.SOURCES[1] else real(p)):
            with self.assertRaisesRegex(ValueError,'duplicate'):j.panel()

    def test_frozen_actual_and_forecast_reproduce_stored_paths(self):
        for c in self.cases:
            if 'frozen_reference' not in c:continue
            for mode,key in [('A_conditional','actual_schedule_conditional'),('B_arrival','arrival_forecast')]:
                r,path,*_=j.evaluate(c,self.original,mode)
                self.assertAlmostEqual(r['predicted_j'],c['frozen_reference'][key]['whole_j'],places=8)
                self.assertLess(max(abs(a-b) for a,b in zip(path,c['frozen_reference'][key]['ap'])),1e-9)

    def test_forward_predictions_ignore_postload_targets(self):
        c=next(c for c in self.cases if c['id']=='sustained_1');other=copy.deepcopy(c)
        other['ap']=[999.]*len(c['ap'])
        other['power_w']=[w if t<35 else w+999 for t,w in zip(c['power_t'],c['power_w'])]
        for segkey in ['actual','forecast']:
            self.assertEqual(j.m.predict(c,c[segkey],self.original,dict(name='FROZEN')),
                             j.m.predict(other,other[segkey],self.original,dict(name='FROZEN')))
            self.assertEqual(j.m.energy_prediction(c,c[segkey],self.original,dict(name='FROZEN'),120),
                             j.m.energy_prediction(other,other[segkey],self.original,dict(name='FROZEN'),120))

    def test_evaluation_and_duplicate_fit_rejected(self):
        with self.assertRaisesRegex(ValueError,'development'):j.fit([self.cases[-1]],self.original)
        c=self.cases[0]
        with self.assertRaisesRegex(ValueError,'duplicate'):j.fit([c,c],self.original)

    def test_full_partial_window_integral_and_transition_continuity(self):
        c=next(c for c in self.cases if c['id']=='sustained_1')
        r,path,init,windows,value=j.evaluate(c,self.original)
        self.assertAlmostEqual(sum(w['signed_j'] for w in windows),r['signed_j'],places=10)
        self.assertAlmostEqual(sum(r[k+'_signed_j'] for k in ['pre','load','post']),r['signed_j'],places=10)
        for s in c['actual'][1:]:
            t=s['start_s']
            public=j.m.case_input(c,c['actual']);public['inputs']['query_s']=[t-1e-6,t,t+1e-6]
            if t<35 or t+1e-6>c['actual'][-1]['end_s']:continue
            p,_=j.m.thermal.predict(public,self.original['ap'])
            self.assertLess(max(abs(p[1]-p[0]),abs(p[2]-p[1])),1e-5)

    def test_unsupported_gap_and_missing_sensor_rejected(self):
        bad=copy.deepcopy(self.cases[0]);bad['actual'][1]['state']='unsupported:GPU'
        with self.assertRaises(ValueError):j.evaluate(bad,self.original)
        bad=copy.deepcopy(self.cases[0]);bad['power_w'][next(i for i,t in enumerate(bad['power_t']) if t>=50)]=None
        with self.assertRaises(ValueError):j.evaluate(bad,self.original)
        bad=copy.deepcopy(self.cases[0]);bad['pre'][0]['hi']=35
        with self.assertRaises(ValueError):j.evaluate(bad,self.original)

    def test_pair_orientation_matches_actual_policy_and_80s_not_120(self):
        rows=[]
        for c in self.cases:
            if c['id'].startswith(('sustained','confirmation_30_','confirmation_180_')):
                r=j.evaluate(c,self.original)[0]
                rows.append(dict(id=c['id'],policy=c['policy'],block=c['evaluation_block'],mode='A_conditional',model='FROZEN',**r))
        pairs=j.paired(rows);self.assertEqual(len(pairs),6)
        second=next(r for r in pairs if r['cpu']=='sustained_3')
        a=next(r for r in rows if r['id']=='sustained_3');b=next(r for r in rows if r['id']=='sustained_2')
        self.assertAlmostEqual(second['observed_difference_j'],b['observed_j']-a['observed_j'])
        self.assertTrue(all(r['full120_error'] is None and not r['policy_counterfactual'] for r in j.memory_pairs()))

    def test_budget_reserve_and_frozen_identity(self):
        with patch.object(j,'DEADLINE',0):
            with self.assertRaises(TimeoutError):j.reserve()
        self.assertEqual(j.m.sha(j.m.MODEL),j.m.MODEL_SHA)


if __name__=='__main__':unittest.main()
