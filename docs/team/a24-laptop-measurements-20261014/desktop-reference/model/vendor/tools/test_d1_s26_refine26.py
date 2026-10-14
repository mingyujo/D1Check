import copy,json,math,unittest
from pathlib import Path
import numpy as np
from tools import d1_s26_refine26_model as m
from tools import d1_s26_refine26_runtime as r

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'outputs/S26-POWER-HEAT-REFINE-26'

class Contracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        package=Path(__file__).resolve().parents[1]
        if(package/'test_fixture.json').exists():
            cls.model=json.loads((package/'model_v26.json').read_text(encoding='utf-8'))
            cls.ep=json.loads((package/'test_fixture.json').read_text(encoding='utf-8'))
        else:
            cls.model=json.loads((OUT/'model_v26.json').read_text(encoding='utf-8'))
            cls.ep=json.loads((OUT/'prepared_v2.json').read_text(encoding='utf-8'))[0]
    def test_bvls_signed_and_bounds(self):
        fit=m.bounded_fit(np.eye(3),[-3,5,1],.0001,[-2,0,0],[2,4,2])
        np.testing.assert_allclose(fit,[-2,4,1],atol=1e-4)
    def test_sub_bin_conservation(self):
        u=np.zeros((3,1));m.fill_interval(u,.001,.013,0)
        self.assertAlmostEqual(u.sum()*m.DT,.012)
    def test_boundary_initial_exact(self):
        state=r.CostState(self.model,self.ep['public'])
        for sensor in ('AP','SKIN'):self.assertEqual(state.temperature(sensor),self.ep['public']['initial_c'][sensor])
    def test_future_reads_rejected(self):
        p=[[t,t+.001,1.]for t in np.arange(-30,0,.5)]
        h={s:[[t,30.]for t in np.arange(-30,0,2)]for s in ('AP','SKIN','BAT')}
        boundary=r.public_from_past(p,h,5,battery_samples=[[-.5,29.]])
        self.assertEqual(boundary['battery_c'],29.)
        self.assertEqual(boundary['initial_c']['BAT'],30.)
        with self.assertRaises(ValueError):r.public_from_past(p+[[1,1.1,1]],h,5,battery_samples=[[-.5,29.]])
        with self.assertRaises(ValueError):r.public_from_past(p,h,5,[[-1,1,0]],battery_samples=[[-.5,29.]])
        with self.assertRaises(ValueError):r.public_from_past(p,h,5,battery_samples=[[.5,29.]])
    def test_owner_contract(self):
        state=r.CostState(self.model,self.ep['public']);state.dispatch('C','classification','GPU');state.dispatch('D','detection','CPU')
        with self.assertRaises(ValueError):state.dispatch('N','classification','NPU')
        with self.assertRaises(ValueError):state.available('wrong','GPU')
        state.set_activity([0,0,0,0,0,2]);state.advance(.01)
        self.assertEqual(len(state.owners),2)
        state.available('C','GPU');self.assertIn('CPU',state.owners)
    def test_stream_matches_grid_on_aligned_intervals(self):
        ep=copy.deepcopy(self.ep);ep.update(end_s=2.,intervals=[[0,.5,4],[.5,1,0],[1,1.1,5]],owners=[[0,1.1]])
        base=m.grid_episode(ep);physical=m.physical_grid(ep,base,self.model['power']);weights=np.asarray(self.model['power']['coefficients']);reference=float(physical.sum(axis=0)@weights*m.DT)
        state=r.CostState(self.model,ep['public']);state.dispatch('C','classification','CPU')
        for end,field in ((.5,4),(1.,0),(1.1,5)):
            u=np.zeros(6);u[field]=1;state.set_activity(u);state.advance(end)
        state.available('C','CPU');state.set_activity(np.zeros(6));state.advance(2.)
        self.assertAlmostEqual(state.energy,reference,places=8)
        for sensor,tm in self.model['thermal'].items():
            heat=m.heating_grid(physical[:,4:]*weights[4:],tm['beta']);target=m.thermal_predict(ep,sensor,heat,[2.],tm,tm['coefficients'])[0]
            self.assertAlmostEqual(state.temperature(sensor),target,places=8)
    def test_gauge_causal_constant_power(self):
        state=r.CostState(self.model,self.ep['public']);state.advance(.1)
        self.assertAlmostEqual(state.snapshot()['power_w'],state.baseline)
        with self.assertRaises(ValueError):state.integral(.2)
    def test_risk_tail_and_lag(self):
        model=copy.deepcopy(self.model);model['power'].update(tail_s=0,lag_s=.18)
        state=r.CostState(model,self.ep['public']);state.dispatch('C','classification','CPU');state.set_activity([1,0,0,0,0,0]);state.advance(.1)
        self.assertAlmostEqual(state.snapshot()['power_w'],state.baseline)
        self.assertGreater(state.energy,state.baseline*.1)
    def test_policy_name_not_feature(self):
        ep=copy.deepcopy(self.ep);a=m.physical_grid(ep,m.grid_episode(ep),self.model['power'])
        ep['policy_metadata_only']='PPO_MAGIC';ep['future_queue']=['never inspect']
        np.testing.assert_array_equal(a,m.physical_grid(ep,m.grid_episode(ep),self.model['power']))
    def test_zero_gpu_coeff_does_not_make_route_free(self):
        state=r.CostState(self.model,self.ep['public']);state.dispatch('G','classification','GPU')
        state.set_activity([0,0,0,0,1,0]);state.advance(.04)
        state.set_activity([0,0,1,0,0,0]);state.advance(.08)
        self.assertGreater(state.energy,state.baseline*.08)

if __name__=='__main__':unittest.main()
