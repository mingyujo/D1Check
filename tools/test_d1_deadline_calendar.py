import copy
import json
import math
import unittest
from tools import d1_deadline_calendar as d
x=d.x


class CalendarTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.frozen,case=x.p.inputs(x.p.BUNDLE);cls.initial=case['initial']
        cls.qs=json.loads((x.ROOT/'inputs.json').read_text(encoding='utf8'))['cases'][x.CASES[-1]]['tickets'][:4]
        cls.result=d.plan(cls.frozen,cls.initial,cls.qs,grid_s=.02,timeout_s=10)

    def test_real_event_calendar_and_response_lane_boundary(self):
        r=self.result;self.assertEqual(r['status'],'replayed_incumbent');self.assertEqual(r['metrics']['deadline_met'],4)
        x.validate_schedule(x.jobs_from_ledger(r['ledger']),self.qs,x.p.profile(self.frozen))
        for q in r['ledger']:
            self.assertGreaterEqual(q['dispatch_ns'],q['arrival_ns'])
            self.assertLessEqual(q['response_ns'],q['deadline_offset_ns'])
            self.assertLess(q['output_ready_ns'],q['lane_available_ns'])
        self.assertFalse(r['original_continuous_optimality_proved'])

    def test_linear_kernel_matches_existing_rounded_thermal_plant(self):
        jobs=copy.deepcopy(self.result['jobs']);profile=x.p.profile(self.frozen)
        for j in jobs:
            q=next(q for q in self.qs if q['id']==j['id'])
            j['end']=j['start']+math.ceil(sum(profile[x.p.key(q,j['backend'])])/1e9/.02-1e-8)*.02
        ss=x.p.segments(jobs,0.,180.)
        costs=x.p.model.costs(ss,self.initial,list(range(35,181)),self.frozen,180.)
        self.assertAlmostEqual(max(costs['ap_path']),self.result['rounded_planning_peak_ap_c'],places=8)
        self.assertAlmostEqual(costs['whole_120s_j']-120*self.initial['preload_power_w'],self.result['rounded_planning_incremental_j'],places=7)

    def test_infeasible_cap_does_not_fake_zero_prediction(self):
        result=d.plan(self.frozen,self.initial,self.qs,grid_s=.05,timeout_s=5,ap_cap_c=20.)
        self.assertEqual(result['status'],'no_incumbent');self.assertIsNone(result['jobs'])
        self.assertNotIn('metrics',result)

    def test_invalid_grid_and_frozen_preserved(self):
        with self.assertRaises(ValueError):d.plan(self.frozen,self.initial,self.qs,grid_s=0)
        self.assertEqual(x.p.digest(x.p.BUNDLE/'model.json'),x.p.MODEL_SHA)
        self.assertEqual(x.p.digest(x.p.BUNDLE/'initial_inputs.json'),x.p.INITIAL_SHA)


if __name__=='__main__':unittest.main()
