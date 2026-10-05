import copy
import unittest
import numpy as np
from tools import d1_supervised_selector as m


class Constant:
    def __init__(self,value):self.value=value
    def predict(self,x):return np.full(len(x),self.value)


class SelectorTests(unittest.TestCase):
    def setUp(self):
        self.e=m.s.envelopes()[13]
        self.h=m.previous(self.e,123001)
        self.bounds=([-1]*5,[100]*5)
        self.ms=[Constant(0),Constant(150),Constant(32),Constant(5)]

    def test_history_before_cutoff(self):
        self.assertLess(max(q['arrival_ns'] for q in self.h),0)
        self.assertEqual(len(m.features(self.h,0)),5)

    def test_future_rejected(self):
        self.h[-1]['arrival_ns']=1
        with self.assertRaises(ValueError):m.features(self.h,0)

    def test_cold_start_rejected(self):
        with self.assertRaises(ValueError):m.features(self.h[:8],0)

    def test_order_rejected(self):
        self.h[1]['arrival_ns']=self.h[0]['arrival_ns']
        with self.assertRaises(ValueError):m.features(self.h,0)

    def test_unobserved_fields_unused(self):
        before=m.features(self.h,0)
        for q in self.h:q.update(id='unknown',future_energy=999,scenario='long',deadline_offset_ns=-1)
        self.assertEqual(before,m.features(self.h,0))

    def test_outside_fallback(self):
        d=m.choose(self.ms,self.h,'energy',([100]*5,[101]*5))
        self.assertEqual(d['reason'],'feature_box_outside')
        self.assertEqual(d['policy'],'EFT_REFERENCE')

    def test_risk_fallback(self):
        self.ms[0]=Constant(.1)
        self.assertEqual(m.choose(self.ms,self.h,'thermal',self.bounds)['reason'],'no_predicted_feasible')

    def test_nonfinite_not_zero(self):
        self.ms[1]=Constant(float('nan'))
        with self.assertRaises(ValueError):m.choose(self.ms,self.h,'energy',self.bounds)

    def test_unknown_objective_policy(self):
        with self.assertRaises(ValueError):m.choose(self.ms,self.h,'invented',self.bounds)
        with self.assertRaises(ValueError):m.vector([0]*5,'DETECTION_GPU')

    def test_whole_envelope_holdout(self):
        self.assertEqual(sum(m.holdout(e) for e in m.s.envelopes()),9)
        X,Y,meta=m.training(m.read(m.SOURCE))
        forbidden={e['id'] for e in m.s.envelopes() if m.holdout(e)}
        self.assertFalse(forbidden & {r['envelope'] for r in meta})
        self.assertEqual({r['seed'] for r in meta},{81001,81002})
        self.assertEqual(X.shape,(288,13));self.assertEqual(Y.shape,(288,4))

    def test_test_labels_do_not_change_fit_data(self):
        rows=m.read(m.SOURCE);X,Y,_=m.training(rows)
        for r in rows:
            if r['stage']!='development':r['energy_j']=-999999
        xx,yy,_=m.training(rows)
        np.testing.assert_array_equal(X,xx);np.testing.assert_array_equal(Y,yy)

    def test_missing_training_cost_rejected(self):
        rows=m.read(m.SOURCE)
        eid=next(e['id'] for e in m.s.envelopes() if not m.holdout(e))
        next(r for r in rows if r['envelope']==eid and r['stage']=='development')['energy_j']=None
        with self.assertRaises(ValueError):m.training(rows)

    def test_prediction_does_not_update_model(self):
        before=copy.deepcopy([x.__dict__ for x in self.ms])
        m.choose(self.ms,self.h,'thermal',self.bounds)
        self.assertEqual(before,[x.__dict__ for x in self.ms])

    def test_real_estimators_and_causal_selection(self):
        X,Y,_=m.training(m.read(m.SOURCE))
        bounds=(X[:,:5].min(axis=0),X[:,:5].max(axis=0))
        for kind in m.MODELS:
            models=m.fit(X,Y,kind)
            decision=m.choose(models,self.h,'energy',bounds)
            self.assertIn(decision['policy'],m.POLICIES)
            self.assertEqual(decision,m.choose(models,self.h,'energy',bounds))


if __name__=='__main__':unittest.main()
