import copy
import unittest
from unittest.mock import patch
import numpy as np
from tools import d1_session_contrast_cost as c


class ContrastTests(unittest.TestCase):
    def test_same_centering_removes_level_bias_without_clipping_negative_values(self):
        X=np.array([[0.,1.],[1.,0.],[2.,3.]])
        y=X@np.array([.4,.8])+7.
        x,z=c.centered_design(X,y,'CENTERED')
        np.testing.assert_allclose(z,x@np.array([.4,.8]))
        self.assertLess(float(x.min()),0.)
        self.assertLess(float(z.min()),0.)

    def test_synthetic_energy_and_AP_coefficients_restore_despite_session_offsets(self):
        original=c.prior.old.analysis.j.m.read(c.prior.old.analysis.j.m.MODEL)
        cases=[dict(id='d'+str(i),role='development') for i in range(3)]
        for head,n in [('energy',4),('AP',5)]:
            theta=np.arange(1,n+1,dtype=float)/10
            X=np.vstack([np.eye(n),np.zeros((2,n))])
            def design(case,requested,model):return X,X@theta+int(case['id'][1:])+2.
            with patch.object(c,'design',side_effect=design):
                result=c.estimate(cases,head,'CENTERED',original,[x['id'] for x in cases])
            actual=list(result['increments'].values()) if head=='energy' else result['coefficients']
            np.testing.assert_allclose(actual,theta,atol=1e-10)
            self.assertEqual(result['training_nuisance_levels_used'],3)

    def test_confirmation_and_unidentified_design_cannot_fit(self):
        with self.assertRaisesRegex(ValueError,'development'):
            c.estimate([dict(id='x',role='confirmation')],'energy','CENTERED',{},['x'])
        with patch.object(c,'design',return_value=(np.zeros((4,4)),np.zeros(4))):
            with self.assertRaisesRegex(ValueError,'unidentified'):
                c.estimate([dict(id='x',role='development')],'energy','CENTERED',{},['x'])

    def test_no_load_predictions_ignore_training_nuisance_and_future_targets(self):
        original=c.prior.old.analysis.j.m.read(c.prior.old.analysis.j.m.MODEL)
        case=c.prior.old.analysis.j.m.read(c.ROOT/'docs/results/ap_tail_observation_run_05/run_v6/inputs.json.gz')[0]
        m=c.prior.old.analysis.j.m.read(c.prior.BUNDLE/'run_v1/candidate.json')
        am=c.prior.old.scope_api.read_assets()[2]
        a=c.prior.energy(case,case['actual'],m,35.,635.)
        ap=c.prior.old.scope_api.tail.predict(case,original,am)[0]
        changed=copy.deepcopy(case);changed['ap']=[999.]*len(case['ap']);changed['power_w']=[999.]*len(case['power_w'])
        m=dict(m,nuisance_not_used_in_prediction=[99999.]);am=dict(am,nuisance_not_used_in_prediction=[99999.])
        self.assertEqual(a,c.prior.energy(changed,changed['actual'],m,35.,635.))
        self.assertEqual(ap,c.prior.old.scope_api.tail.predict(changed,original,am)[0])


if __name__=='__main__':unittest.main()
