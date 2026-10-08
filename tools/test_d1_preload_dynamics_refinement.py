import copy
import unittest
import numpy as np
from tools import d1_preload_dynamics_refinement as d


class PreloadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases,_=d.j.panel();cls.model=d.j.m.read(d.j.m.MODEL)

    def test_future_targets_do_not_enter_initializers(self):
        for c in self.cases:
            other=copy.deepcopy(c);other['ap']=[999.]*len(c['ap'])
            other['power_w']=[w if t<=31 else 999. for t,w in zip(c['power_t'],c['power_w'])]
            self.assertEqual(d.energy_initial(c),d.energy_initial(other))
            self.assertEqual(d.ap_initial(c['pre'],self.model),d.ap_initial(other['pre'],self.model))

    def test_synthetic_initial_states_identified_from_preload(self):
        beta=self.model['ap']['beta'];tau=30.;ref=28.;a=2.;h=.01
        t=np.arange(-25,35,2.);pre=[dict(t=float(z),lo=float(z-.1),hi=float(z+.1),ap=ref+a*np.exp(-beta*(z-t[0]))+h*d.j.h.memory.convolution(beta,tau,z-t[0])) for z in t]
        init=d.ap_initial(pre,self.model)
        self.assertAlmostEqual(init['reference_c'],ref,places=9);self.assertAlmostEqual(init['h_first_c_per_s'],h,places=9)
        c=dict(power_t=list(np.arange(-25,36,.9)),power_w=[])
        c['power_w']=[1.2+.3*np.exp(-(z+20)/30) for z in c['power_t']]
        e=d.energy_initial(c);self.assertAlmostEqual(e['reference_w'],1.2,places=10);self.assertAlmostEqual(e['transient_at_minus20_w'],.3,places=10)

    def test_latest_ap_anchor_and_state_transition_continuity(self):
        c=self.cases[0];init=d.ap_initial(c['pre'],self.model)
        public=d.j.m.case_input(c,c['actual'])['inputs'];public['query_s']=[35.,35.000001]
        p=d.predict_ap(public,self.model,init);self.assertLess(abs(p[1]-p[0]),1e-5)
        atanchor=d.j.h.memory._propagate(c['actual'],[init['anchor_s']],self.model['ap']['parameters']['ap_slope_at_30_c_per_s'],self.model['ap']['beta'],30.,0.,init)
        self.assertAlmostEqual(atanchor[0],c['pre'][-1]['ap'],places=10)

    def test_power_integral_and_prefix_preserved(self):
        c=self.cases[0];init=d.energy_initial(c)
        e=lambda t:d.predict_energy(c['pre_w'],c['actual'],self.model,init,t)
        self.assertAlmostEqual(e(35),c['pre_w']*35,places=10)
        self.assertLess(abs(e(35+1e-7)-e(35)),1e-5)
        self.assertAlmostEqual(sum(e(t+5)-e(t) for t in range(0,120,5)),e(120),places=10)

    def test_zero_transient_identity_with_original(self):
        c=self.cases[0];init=dict(reference_w=c['pre_w'],predicted_35_w=c['pre_w'])
        for t in [0,35,67,120]:self.assertAlmostEqual(d.predict_energy(c['pre_w'],c['actual'],self.model,init,t),d.j.m.energy_prediction(c,c['actual'],self.model,dict(name='FROZEN'),t),places=10)

    def test_missing_unsupported_future_preload_rejected(self):
        c=copy.deepcopy(self.cases[0]);c['power_w'][next(i for i,t in enumerate(c['power_t']) if 0<=t<=1)]=None
        with self.assertRaises(ValueError):d.energy_initial(c)
        c=copy.deepcopy(self.cases[0]);public=d.j.m.case_input(c,c['actual'])['inputs'];public['preload'][-1]['hi']=35
        with self.assertRaises(ValueError):d.predict_ap(public,self.model,d.ap_initial(c['pre'],self.model))
        c=copy.deepcopy(self.cases[0]);c['actual'][1]['state']='classification:NPU'
        with self.assertRaises(ValueError):d.predict_energy(c['pre_w'],c['actual'],self.model,dict(reference_w=1.,predicted_35_w=1.),120)

    def test_constant_preload_is_not_an_ambient_measurement(self):
        c=copy.deepcopy(self.cases[0]);c['pre']=[dict(p,ap=29.) for p in c['pre']]
        init=d.ap_initial(c['pre'],self.model);self.assertAlmostEqual(init['reference_c'],29.,places=8)
        self.assertFalse(init['reference_is_ambient']);self.assertFalse(init['latent_is_measured_internal_temperature'])

    def test_unavailable_component_retains_other_output_and_frozen_hash(self):
        c=self.cases[0];initials=dict(energy=None,ap=None)
        e=d.score(c,self.model,'E_PRE_TRANSIENT','A_conditional',initials)[0]
        self.assertIsNone(e['predicted_j']);self.assertTrue(e['ap_available'])
        a=d.score(c,self.model,'AP_FREE_INITIAL','A_conditional',initials)[0]
        self.assertIsNone(a['mae_c']);self.assertTrue(a['energy_available'])
        self.assertEqual(d.j.m.sha(d.j.m.MODEL),d.j.m.MODEL_SHA)


if __name__=='__main__':unittest.main()
