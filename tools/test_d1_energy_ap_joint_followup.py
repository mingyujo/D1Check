import copy
import unittest
from unittest.mock import patch
from tools import d1_energy_ap_joint_followup as e


class EnergyTests(unittest.TestCase):
    def model(self):
        return dict(idle_bias_w=.03, increments=dict(zip(e.analysis.j.m.base.STATES, (1., 2., 3., 4.))))

    def case(self):
        keys=e.analysis.j.m.base.STATES
        return dict(pre_w=1., actual=[dict(start_s=0., end_s=35., state='idle'),
            dict(start_s=35.,end_s=40.,state=keys[0]),
            dict(start_s=40.,end_s=635.,state='idle')])

    def test_whole_power_accounting_and_additive_intervals(self):
        c=self.case();m=self.model()
        value=e.prediction(c,m,0.,50.)
        self.assertAlmostEqual(value,50.+.03*15+5.)
        self.assertAlmostEqual(value,e.prediction(c,m,0.,25.)+e.prediction(c,m,25.,50.))

    def test_offset_starts_at35_and_accumulates_in_idle(self):
        c=self.case();m=self.model()
        self.assertEqual(e.prediction(c,m,0.,35.),35.)
        self.assertAlmostEqual(e.prediction(c,m,40.,600.)-560.,.03*560.)

    def test_missing_sensor_endpoint_is_not_zero_filled(self):
        c=dict(power_t=[0.,1.,2.,3.,4.,5.,5.9],power_w=[1.]*7)
        cov=e.observed.measured_energy(c,0.,6.)
        self.assertIsNone(cov['full_energy_j'])
        self.assertAlmostEqual(cov['covered_energy_j'],5.9)
        self.assertAlmostEqual(cov['missing_s'],.1)

    def test_nonpositive_power_horizon_and_unknown_state_rejected(self):
        c=self.case();m=self.model();m['idle_bias_w']=-1.1
        with self.assertRaisesRegex(ValueError,'nonpositive'):e.prediction(c,m,0.,50.)
        with self.assertRaisesRegex(ValueError,'beyond'):e.prediction(c,self.model(),0.,636.)
        c['actual'][1]['state']='detection_GPU'
        with self.assertRaisesRegex(ValueError,'unsupported'):e.prediction(c,self.model(),0.,50.)

    def test_targets_do_not_enter_energy_prediction(self):
        c=self.case();before=e.prediction(c,self.model(),35.,120.)
        c.update(ap=[999.],power_t=[999.],power_w=[999.])
        self.assertEqual(before,e.prediction(c,self.model(),35.,120.))

    def test_confirmation_or_unregistered_development_cannot_fit(self):
        cases=[dict(id='session_'+str(n),role='confirmation',policy='DEV_A') for n in range(3)]
        with self.assertRaisesRegex(ValueError,'registered'):e.train(cases,{},[c['id'] for c in cases])
        for c in cases:c['role']='development'
        with self.assertRaisesRegex(ValueError,'registered'):e.train(cases,{},['another_development'])

    def test_actual_energy_fit_restores_identified_synthetic_coefficients(self):
        keys=e.analysis.j.m.base.STATES
        segments=[dict(start_s=0.,end_s=35.,state='idle')]
        cursor=35.
        for key in keys:
            segments += [dict(start_s=cursor,end_s=cursor+60,state=key),
                         dict(start_s=cursor+60,end_s=cursor+150,state='idle')]
            cursor+=150
        cases=[dict(id='session_'+str(n),role='development',policy='DEV_A',
                    common_end_s=635.,pre_w=1.,actual=copy.deepcopy(segments)) for n in range(3)]
        true=self.model()
        with patch.object(e.analysis.j.m,'integral',side_effect=lambda c,a,b:e.prediction(c,true,a,b)):
            fitted=e.train(cases,{},[c['id'] for c in cases])
        self.assertAlmostEqual(fitted['idle_bias_w'],.03,places=10)
        for key in keys:self.assertAlmostEqual(fitted['increments'][key],true['increments'][key],places=10)


if __name__=='__main__':unittest.main()
