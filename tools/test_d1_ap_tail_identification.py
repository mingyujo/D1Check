import copy
import unittest
import json
from unittest.mock import patch
import numpy as np
from tools import d1_ap_tail_identification as t
from tools import test_d1_resident_ap_structure as fixtures


class TailTests(unittest.TestCase):
    def case(self,profile='DEV_A',sid='fixture'):
        return fixtures.StructureTests().case(profile,sid)

    def original(self):return t.s.j.m.read(t.s.j.m.MODEL)

    def model(self,tau=240.,mode='LOAD_SLOW'):
        return dict(mode=mode,tau_s=tau,coefficients=[.08,.12,.05,.17,.01],
                    original_model_sha256=t.s.j.m.MODEL_SHA,beta_fixed=self.original()['ap']['beta'])

    def test_load_kernel_has_exact_pulse_and_cooling_solution(self):
        c=self.case();c['q']=list(range(35,156,5));tau=240.;o=self.original()
        _,_,kernel,_,_=t.bases(c,o,tau);power=o['energy_increment_w']['classification_CPU']
        self.assertAlmostEqual(kernel[0],0.,places=12)
        for q in [50,95,125]:
            work=min(q-35,60);expected=power*tau*(1-np.exp(-work/tau))*np.exp(-max(0,q-95)/tau)
            self.assertAlmostEqual(kernel[c['q'].index(q)],expected,places=10)

    def test_zero_work_memory_and_nonzero_clock_are_separate(self):
        c=self.case();c['actual']=[dict(start_s=0.,end_s=815.,state='idle')]
        _,_,kernel,clock,_=t.bases(c,self.original(),240.)
        self.assertTrue(np.all(kernel==0));self.assertGreater(clock[-1],0.)
        a,_=t.predict(c,self.original(),self.model());m=self.model(mode='CLOCK_SHIFT');m['coefficients'][-1]=1.
        b,_=t.predict(c,self.original(),m);self.assertGreater(b[-1],a[-1])

    def test_synthetic_tau_and_coefficients_recovered(self):
        o=self.original();known=self.model();cases=[]
        for i,p in enumerate(['DEV_A','DEV_B','DEV_A']):
            c=self.case(p,str(i));c['ap']=t.predict(c,o,known)[0];cases.append(c)
        model,profile=t.fit(cases,o,'LOAD_SLOW',[30.,60.,120.,240.,480.,960.,1920.])
        self.assertEqual(model['tau_s'],240.);self.assertEqual(len(profile),7)
        np.testing.assert_allclose(model['coefficients'],known['coefficients'],atol=1e-9,rtol=0)
        self.assertTrue(model['time_identified_within_grid']);self.assertFalse(model['physical_cause_identified'])
        json.dumps(model,allow_nan=False)

    def test_upper_boundary_does_not_extend_grid_or_certify(self):
        o=self.original();cases=[]
        for i,p in enumerate(['DEV_A','DEV_B','DEV_A']):
            c=self.case(p,str(i));c['ap']=t.predict(c,o,self.model(1920.))[0];cases.append(c)
        model,profile=t.fit(cases,o,'LOAD_SLOW',[30.,60.,120.,240.,480.,960.,1920.])
        self.assertEqual(model['tau_s'],1920.);self.assertTrue(model['tau_boundary'])
        self.assertFalse(model['time_identified_within_grid']);self.assertFalse(model['application_allowed'])
        self.assertEqual(len(profile),7)

    def test_future_targets_and_power_not_prediction_inputs(self):
        c=self.case();a,_=t.predict(c,self.original(),self.model())
        c['ap']=[1000]*len(c['q']);c['power_w']=[float('nan')]*100
        b,_=t.predict(c,self.original(),self.model());self.assertEqual(a,b)

    def test_continuity_and_initial_bracket(self):
        c=self.case();a,_=t.predict(c,self.original(),self.model());seg=c['actual'][1];mid=(seg['start_s']+seg['end_s'])/2
        c['actual'][1:2]=[dict(seg,end_s=mid),dict(seg,start_s=mid)]
        b,_=t.predict(c,self.original(),self.model());np.testing.assert_allclose(a,b,atol=1e-10,rtol=0)
        c['pre'][-1]['hi']=35.
        with self.assertRaisesRegex(ValueError,'future AP'):t.predict(c,self.original(),self.model())

    def test_confirmation_fit_and_unknown_state_blocked(self):
        cases=[self.case(sid=str(i)) for i in range(3)];cases[0]['role']='confirmation'
        with self.assertRaisesRegex(ValueError,'forbidden'):t.fit(cases,self.original(),'LOAD_SLOW',[30.,60.])
        c=self.case();c['actual'][1]['state']='detection_GPU'
        with self.assertRaisesRegex(ValueError,'unsupported state'):t.predict(c,self.original(),self.model())

    def test_zero_sensitivity_is_not_tau_identification(self):
        o=self.original();cases=[self.case(sid=str(i)) for i in range(3)]
        for c in cases:c['ap']=t.bases(c,o,240.)[0].tolist()
        model,_=t.fit(cases,o,'LOAD_SLOW',[30.,60.,120.,240.])
        self.assertEqual(model['coefficients'][-1],0.);self.assertFalse(model['time_identified_within_grid'])

    def test_profile_reconstruction_does_not_run_optimizer(self):
        o=self.original();cases=[]
        for i,p in enumerate(['DEV_A','DEV_B','DEV_A']):
            c=self.case(p,str(i));c['ap']=t.predict(c,o,self.model())[0];cases.append(c)
        model,profile=t.fit(cases,o,'LOAD_SLOW',[30.,60.,120.,240.,480.])
        with patch.object(t,'constrained',side_effect=AssertionError('no optimizer on recovery')):
            restored=t.model_from_profile(cases,o,'LOAD_SLOW',[30.,60.,120.,240.,480.],profile)
        self.assertEqual(model,restored)

    def test_power_intersection_is_explicit_and_missing_not_zero(self):
        c=self.case();c['ap']=[28]*len(c['q']);c['last_lane_s']=545.;c['pre_w']=1.
        c['power_t']=list(range(-20,812));c['power_w']=[1.]*len(c['power_t'])
        row=t.power_common_windows([c],self.original())[0]
        self.assertEqual(row['power_common_end_s'],811.);self.assertAlmostEqual(row['late_power_w'],1.)
        self.assertLess(row['power_common_end_s'],row['ap_interval_end_s'])
        c['power_w'][-1]=float('nan');row=t.power_common_windows([c],self.original())[0]
        self.assertIsNone(row['late_power_w']);self.assertIsNotNone(row['error'])


if __name__=='__main__':unittest.main()
