"""Pure boundary/analytic fixtures; no raw measurements or environment."""
import math,unittest
from state_cost import *

class CostTests(unittest.TestCase):
    def seg(self,a,b,s):return dict(start_s=a,end_s=b,state=s)
    def model(self,tau=0,adopted=True):return dict(tau_s=tau,coefficients_W_proxy=[1,2,3,4],adopted_for_qualified_states=adopted)
    def test_constant_exact(self):
        self.assertEqual(exposures([self.seg(0,5,STATES[0])],[(0,5)],0),[[1,0,0,0]])
    def test_decay_integral(self):
        x=exposures([self.seg(0,2,STATES[0]),self.seg(2,10,'idle')],[(0,10)],1)[0][0]*10
        self.assertAlmostEqual(x,2-(1-math.exp(-2))*math.exp(-8),places=12)
    def test_additive_windows(self):
        s=[self.seg(0,2,STATES[0]),self.seg(2,10,'idle')]
        a=exposures(s,[(0,2),(2,10),(0,10)],3)
        self.assertAlmostEqual(2*a[0][0]+8*a[1][0],10*a[2][0],places=12)
    def test_no_future_leak(self):
        a=[self.seg(0,3,'idle'),self.seg(3,5,STATES[0])]
        b=[self.seg(0,3,'idle'),self.seg(3,5,STATES[2])]
        self.assertEqual(exposures(a,[(0,3)],1),exposures(b,[(0,3)],1))
    def test_gap_fails(self):
        with self.assertRaises(ValueError):exposures([self.seg(0,2,'idle'),self.seg(3,5,'idle')],[(0,5)],1)
    def test_overlap_fails(self):
        with self.assertRaises(ValueError):exposures([self.seg(0,3,'idle'),self.seg(2,5,'idle')],[(0,5)],1)
    def test_outside_fails(self):
        with self.assertRaises(ValueError):exposures([self.seg(0,5,'idle')],[(-1,5)],1)
    def test_idle_baseline_preserved(self):
        r=observe([self.seg(0,10,'idle')],0,10,self.model(),2)
        self.assertEqual(r['total_J_proxy'],20);self.assertEqual(r['increment_J_proxy'],0)
    def test_unknown_route_fails(self):
        with self.assertRaises(ValueError):observe([self.seg(0,5,'NPU')],0,5,self.model())
    def test_unmeasured_not_discounted(self):
        r=observe([self.seg(0,5,'classification_CPU+detection_GPU')],0,5,self.model(),1)
        self.assertAlmostEqual(r['increment_J_proxy'],5*(1+.6013808404579677))
        self.assertEqual(r['unsupported_seconds'],5);self.assertFalse(r['sensitivity_is_CI'])
        self.assertLess(r['sensitivity_total_J_proxy'][0],r['total_J_proxy'])
    def test_rejected_fit_falls_back(self):
        r=observe([self.seg(0,5,STATES[0])],0,5,self.model(3,False),1)
        self.assertAlmostEqual(r['total_J_proxy'],5+5*ANCHOR[0]);self.assertFalse(r['fitted_candidate_adopted'])
    def test_history_before_window_used(self):
        r=observe([self.seg(0,2,STATES[0]),self.seg(2,10,'idle')],2,10,self.model(1),1)
        self.assertGreater(r['increment_J_proxy'],.86)
    def test_native_colon_state(self):
        self.assertEqual(state_key('detection:CPU+classification:GPU'),STATES[3])
    def test_fit_session_weight_and_bounds(self):
        rows=[dict(x=[1,0,0,0],y=2,session='A')]*100+[dict(x=[1,0,0,0],y=0,session='B')]
        self.assertLess(fit(rows)[0],1.01);self.assertGreater(fit(rows)[0],.9)
        self.assertTrue(all(0<=a<=4 for a in fit([dict(x=[1,0,0,0],y=100,session='A')])))
    def test_permutation_fit(self):
        a=[dict(x=[1,0,0,0],y=1,session='A'),dict(x=[0,1,0,0],y=2,session='B')]
        self.assertEqual(fit(a),fit(a[::-1]))
    def test_baseline_never_off(self):
        with self.assertRaises(ValueError):observe([self.seg(0,5,'idle')],0,5,self.model(),0)
    def test_generalized_state_dimension(self):
        a=exposures([self.seg(0,3,'detection_GPU')],[(0,3)],0,('detection_GPU',))
        self.assertEqual(a,[[1.]])
    def test_native_owners_capacity(self):
        from relative_drain import exclusive
        owners=[dict(start_s=1,end_s=4,task='C',route='GPU'),dict(start_s=2,end_s=5,task='D',route='CPU')]
        s=exclusive(owners,0,6)
        self.assertEqual([r['state'] for r in s],['idle','classification_GPU',STATES[3],'detection_CPU','idle'])
    def test_native_conflict_fails(self):
        from relative_drain import exclusive
        with self.assertRaises(ValueError):exclusive([dict(start_s=0,end_s=3,task=t,route='CPU') for t in ('C','D')],0,5)
    def test_native_unqualified_is_null(self):
        import relative_drain as R
        self.assertIsNone(R.observe([],0,5,None)['mean_index'])
    def test_native_zero_future_knowledge(self):
        import relative_drain as R
        m=dict(adopted_as_relative_sensor_predictor=True,states=list(R.ALL_STATES),tau_s=0,
               coefficients=[1.]*8,support=[dict(state=s,qualified=s!=STATES[0]) for s in R.ALL_STATES])
        r=R.observe([dict(start_s=0,end_s=1,task='C',route='CPU')],0,5,m)
        self.assertEqual(r['status'],'UNQUALIFIED_ROUTE_SUPPORT');self.assertIsNone(r['mean_index'])

if __name__=='__main__':unittest.main()
