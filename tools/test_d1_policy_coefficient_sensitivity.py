import copy
import math
import unittest
from unittest.mock import patch
from tools import d1_policy_coefficient_sensitivity as s


class SensitivityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=s.j.m.read(s.BUNDLE/'inputs.json.gz');cls.cases=cls.data['cases'];cls.variants=s.models()

    def values(self,energy,ap):
        return [dict(model=str(i),delta_energy_j=x,delta_peak_ap_c=y) for i,(x,y) in enumerate(zip(energy,ap))]

    def test_service_and_both_deadlines_before_gain_claim(self):
        v=self.values([-1]*5,[-.1]*5)
        self.assertEqual(s.guard(v,True,True)['status'],'joint_direction_all_five')
        self.assertEqual(s.guard(v,False,True)['status'],'service_ineligible')
        self.assertEqual(s.guard(v,True,False)['status'],'deadline_ineligible')
        self.assertFalse(s.guard(v,True,False)['all_deadline_joint_direction'])

    def test_sign_crossing_tie_and_missing_not_zero(self):
        self.assertEqual(s.guard(self.values([-1,-1,-1,-1,1],[-.1]*5),True,True)['status'],'sign_sensitive')
        self.assertEqual(s.guard(self.values([0]*5,[0]*5),True,True)['status'],'numerical_tie')
        r=s.guard(self.values([-1,-1,-1,-1,None],[-.1]*5),True,True)
        self.assertEqual(r['status'],'unavailable');self.assertIsNone(r['energy_min_j'])
        with self.assertRaises(ValueError):s.guard(self.values([-1]*4,[-.1]*4),True,True)

    def test_full_denominator_and_same_workload_for_all_policies(self):
        self.assertEqual(len(self.cases),72)
        ids={(c['seed'],c['family'],c['context'],c['policy']) for c in self.cases};self.assertEqual(len(ids),72)
        for family in s.FAMILIES:
            for context in s.CONTEXTS:
                use=[c for c in self.cases if c['family']==family and c['context']==context]
                ticket=lambda c:[tuple(r[k] for k in ('id','ordinal','task','priority','arrival_ns','deadline_offset_ns')) for r in c['ledger']]
                self.assertTrue(all(ticket(c)==ticket(use[0]) for c in use))

    def test_output_ready_not_lane_release_and_original_ledgers_unchanged(self):
        c=copy.deepcopy(self.cases[0]);ledger=copy.deepcopy(c['ledger']);ss=s.segments(ledger)
        release=max(r['lane_available_ns'] for r in ledger)/1e9
        self.assertAlmostEqual(max(x['end_s'] for x in ss if x['state']!='idle'),release)
        self.assertEqual(ledger,c['ledger'])
        changed=copy.deepcopy(ledger)
        for r in changed:r['lane_available_ns']=r['output_ready_ns'];r['worker_release_ns']=r['output_ready_ns'];r['persist_complete_ns']=r['output_ready_ns']
        t=s.segments(changed)
        self.assertLess(sum(x['end_s']-x['start_s'] for x in t if x['state']!='idle'),sum(x['end_s']-x['start_s'] for x in ss if x['state']!='idle'))

    def test_no_scheduler_invoked_and_original_costs_reproduce(self):
        with patch.object(s.j.m.base.engine,'simulate',side_effect=AssertionError('scheduler must not start')):
            for c in self.cases:
                costs=s.j.m.base.costs(c['segments'],self.data['initial'],list(range(35,181)),self.variants[0][1],180)
                self.assertAlmostEqual(costs['whole_120s_j'],c['row']['energy_j'],places=7)
                self.assertAlmostEqual(max(costs['ap_path']),c['row']['peak_ap_c'],places=7)
                area=float(s.np.trapezoid([max(0,t-costs['initial']['reference_c']) for t in costs['ap_path']],range(35,181)))
                self.assertAlmostEqual(area,c['row']['thermal_degree_seconds'],places=7)

    def test_same_preload_idle_cancels_in_policy_difference(self):
        use=[c for c in self.cases if c['family']=='sustained' and c['context']=='mean'];a,b=use[:2]
        for _,model in self.variants:
            inc=list(model['energy_increment_w'][k] for k in s.j.m.base.STATES)
            exposures=[s.j.m.base.exposure(c['segments'],0,120) for c in (a,b)]
            direct=sum((x-y)*v for x,y,v in zip(exposures[0],exposures[1],inc))
            cost=lambda c:s.j.m.base.costs(c['segments'],self.data['initial'],list(range(35,181)),model,180)['whole_120s_j']
            self.assertAlmostEqual(cost(a)-cost(b),direct,places=10)

    def test_missing_boundary_unsupported_and_unfinished_rejected(self):
        bad=copy.deepcopy(self.cases[0]['ledger']);del bad[0]['lane_available_ns']
        with self.assertRaises(ValueError):s.segments(bad)
        bad=copy.deepcopy(self.cases[0]['ledger']);bad[0]['status']='failed'
        with self.assertRaises(ValueError):s.segments(bad)
        bad=copy.deepcopy(self.cases[0]['ledger']);bad[0]['backend']='NPU'
        with self.assertRaises(ValueError):s.j.m.base.exposure(s.segments(bad),0,120)

    def test_original_frozen_hash_and_refit_artifact_identity(self):
        self.assertEqual(s.j.m.sha(s.j.m.MODEL),s.j.m.MODEL_SHA)
        self.assertEqual([n for n,_ in self.variants],['FROZEN','JOINT_all9','exclude_history_180','exclude_history_30','exclude_old_development'])
        c=s.j.m.read(s.BUNDLE/'contract.json')
        for p,digest in c['input_hashes'].items():self.assertEqual(s.j.m.sha(s.j.m.ROOT/p),digest)


if __name__=='__main__':unittest.main()
