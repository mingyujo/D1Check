import copy
import unittest
from unittest.mock import patch
import numpy as np
from tools import d1_pooled_energy_candidate as c
from tools.test_d1_online_policy_study import synthetic


class PooledTests(unittest.TestCase):
    def test_identification_and_initial_power_independence(self):
        cases,z=synthetic()
        def measured(case,a,b):return 1.2*(b-a)+float(c.m.exposure(case['inputs']['segments'],a,b)@z)
        with patch.object(c.m,'energy_at',side_effect=measured):
            old=c.m.develop(cases);before=copy.deepcopy(old)
            for case in cases:case['study_phase']='candidate_posthoc_development'
            fitted=c.fit(cases,old)
            self.assertAlmostEqual(fitted['resident_w'],1.2)
            np.testing.assert_allclose(list(fitted['energy_increment_w'].values()),z,atol=1e-10)
            self.assertEqual(old,before);self.assertEqual(fitted['ap'],old['ap']);self.assertEqual(fitted['service'],old['service'])
            a=cases[0];initial=dict(preload=a['inputs']['preload'],preload_power_w=1.)
            first=c.m.costs(a['inputs']['segments'],initial,a['inputs']['query_s'],fitted,180)
            initial['preload_power_w']=999.
            second=c.m.costs(a['inputs']['segments'],initial,a['inputs']['query_s'],fitted,180)
            self.assertEqual(first,second)
            self.assertAlmostEqual(first['whole_120s_j'],measured(a,0,120),places=8)
            cases[0]['study_phase']='confirmation'
            with self.assertRaisesRegex(ValueError,'designated'):c.fit(cases,old)

    def test_unidentified_and_unknown_modes_do_not_produce_costs(self):
        cases,_=synthetic()
        for a in cases:
            a['study_phase']='candidate_posthoc_development';a['inputs']['segments']=[dict(start_s=0,end_s=180,state='idle')]
        with patch.object(c.m,'energy_at',side_effect=lambda case,a,b:b-a):
            with self.assertRaisesRegex(ValueError,'unidentified'):c.fit(cases,{})
        with self.assertRaisesRegex(ValueError,'unregistered'):
            c.m.costs([],{},[],dict(energy_increment_w=dict.fromkeys(c.m.STATES,0),energy_baseline_mode='unknown'),120)


if __name__=='__main__':unittest.main()
