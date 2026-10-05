import json
import unittest
from tools import d1_energy_heat_frontier as f
x=f.f.x


class FrontierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.frozen,case=x.p.inputs(x.p.BUNDLE);cls.initial=case['initial']
        cls.qs=json.loads((x.ROOT/'inputs.json').read_text(encoding='utf8'))['cases'][x.CASES[-1]]['tickets']
        cls.c=f.coefficients(cls.frozen,cls.initial,cls.qs,'mean')

    def test_equal_work_overlap_costs_have_opposing_directions(self):
        c=self.c
        self.assertLess(c['gpu_assignment_extra_j']-c['class_gpu_s']*c['overlap_discount_w'],0)
        self.assertGreater(c['gpu_assignment_extra_input_c']+c['class_gpu_s']*c['overlap_extra_input_c_per_s'],0)

    def test_enumerated_relaxation_cannot_beat_its_bound(self):
        c=self.c
        for ng in range(c['nc']+1):
            for fraction in (0,.5,1):
                overlap=fraction*min(ng*c['class_gpu_s'],c['nd']*c['det_cpu_s'])
                energy=c['base_j']+ng*c['gpu_assignment_extra_j']-overlap*c['overlap_discount_w']
                drive=c['base_input_c']+ng*c['gpu_assignment_extra_input_c']+overlap*c['overlap_extra_input_c_per_s']
                r=f.bound(c,energy)
                self.assertIsNotNone(r['minimum_integrated_input_c'])
                self.assertLessEqual(r['minimum_integrated_input_c'],drive+1e-7)

    def test_signed_tail_identity_not_zero_filled_finite_area(self):
        ap=self.frozen['ap'];u=.2;dt=.3
        # Integrate the exact unit-response difference well beyond the chosen
        # finite comparison window. Identical initial conditions cancel.
        t,h=x.p.thermal_step(0.,0.,u,0.,ap,dt)
        area_load=ap['k']*u/ap['beta']*(dt-(1-__import__('math').exp(-ap['beta']*dt))/ap['beta'])
        area_tail=t/ap['beta']
        self.assertAlmostEqual(area_load+area_tail,ap['k']/ap['beta']*u*dt,places=10)

    def test_infeasible_budget_returns_null(self):
        r=f.bound(self.c,0)
        self.assertIsNone(r['minimum_integrated_input_c'])


if __name__=='__main__':unittest.main()
