import copy
import unittest
from tools import d1_preboundary_evidence as e


class PreBoundaryTests(unittest.TestCase):
    def case(self):return next(c for c in e.current.cases() if c['id']=='development_30_C0')

    def test_future_targets_do_not_enter_fixed_initialization_prediction(self):
        c=self.case();original=e.current.prior.old.analysis.j.m.read(e.current.prior.old.analysis.j.m.MODEL)
        model=e.current.prior.old.scope_api.read_assets()[2]
        expected=e.compare(c,c['pre'],original,model)[0]
        changed=copy.deepcopy(c);changed['ap']=[999.]*len(c['ap']);changed['power_w']=[999.]*len(c['power_w'])
        self.assertEqual(expected,e.compare(changed,c['pre'],original,model)[0])

    def test_preload_that_returns_after_start_is_rejected(self):
        c=self.case();original=e.current.prior.old.analysis.j.m.read(e.current.prior.old.analysis.j.m.MODEL)
        model=e.current.prior.old.scope_api.read_assets()[2]
        pre=copy.deepcopy(c['pre']);pre[-1]['hi']=36.
        with self.assertRaises(ValueError):e.compare(c,pre,original,model)

    def test_longer_constant_pre_does_not_create_a_new_thermal_offset(self):
        c=copy.deepcopy(self.case());c['pre']=[dict(t=t,lo=t-.01,hi=t+.01,ap=28.) for t in range(-29,35,3)]
        long=[dict(t=t,lo=t-.01,hi=t+.01,ap=28.) for t in range(-59,-29,3)]+c['pre']
        original=e.current.prior.old.analysis.j.m.read(e.current.prior.old.analysis.j.m.MODEL);model=e.current.prior.old.scope_api.read_assets()[2]
        a=e.compare(c,c['pre'],original,model)[0];b=e.compare(c,long,original,model)[0]
        for x,y in zip(a,b):self.assertAlmostEqual(x,y,places=10)


if __name__=='__main__':unittest.main()
