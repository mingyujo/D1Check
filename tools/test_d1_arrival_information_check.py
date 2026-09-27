"""Focused tests for the first-action information diagnostic."""
import copy
import json
import math
import unittest

from tools import d1_arrival_explore as engine
from tools import d1_arrival_information_check as check
from tools import d1_arrival_thermal_feedback as feedback
from tools import d1_arrival_thermal_feedback_batch as frozen
from tools import d1_arrival_offline_search as offline


class InformationBoundaryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec=check.read(check.CONFIG)
        cls.source=check.read(frozen.CONFIG)
        cls.freeze=frozen.verify(cls.source)
        cls.config=check.read(frozen.INPUT/'estimates.json')
        cls.vectors=check.read(frozen.INPUT/'realizations.json')
        cls.case=cls.spec['cases'][0]
        cls.settings=frozen.settings(feedback.POLICY,cls.source,cls.freeze)
        cls.model=frozen.model(next(p for p in cls.source['profiles']
                                    if p['id']==cls.case['profile']),cls.source)

    def run_branch(self, branch_id, backend, vectors=None):
        branch=next(b for b in self.spec['branches'] if b['id']==branch_id)
        requests,actual=check.branch_inputs(self.case,branch,vectors or self.vectors)
        result,snapshot=check.replay(self.config,actual,requests,self.settings,self.model,
                                     self.case['seed'],backend)
        return requests,result,snapshot

    def test_same_past_different_future_and_identical_online_choice(self):
        req0,no_future,s0=self.run_branch('no_more','CPU')
        req3,urgent_future,s1=self.run_branch('original_three','CPU')
        self.assertEqual(req0[0],req3[0])
        self.assertEqual(s0,s1)
        self.assertEqual(s0['online_selected']['backend'],'GPU')
        self.assertEqual([x['id'] for x in s0['arrived_queue']],[req0[0]['id']])
        self.assertNotIn(req3[1]['id'],json.dumps(s0))
        self.assertNotEqual(no_future['metrics']['planned'],urgent_future['metrics']['planned'])

    def test_realization_changes_outcome_not_first_information(self):
        _,base_result,base_snapshot=self.run_branch('original_three','CPU')
        _,slow_result,slow_snapshot=self.run_branch('cpu_slow_1p25','CPU')
        self.assertEqual(base_snapshot,slow_snapshot)
        self.assertNotEqual(base_result['ledger'][0]['lane_available_ns'],
                            slow_result['ledger'][0]['lane_available_ns'])

    def test_forced_gpu_is_original_v1_and_lane_response_boundaries_hold(self):
        requests,forced,_=self.run_branch('original_three','GPU')
        baseline=engine.simulate(self.config,self.vectors,requests,policy=feedback.POLICY,
            settings=self.settings,seed=self.case['seed'],thermal_model=self.model)
        self.assertEqual(forced['ledger'],baseline['ledger'])
        self.assertEqual(forced['thermal'],baseline['thermal'])
        for row in forced['ledger']:
            self.assertLessEqual(row['dispatch_ns'],row['execution_start_ns'])
            self.assertLessEqual(row['output_ready_ns'],row['persist_complete_ns'])
            self.assertLessEqual(row['persist_complete_ns'],row['worker_release_ns'])
            self.assertLessEqual(row['worker_release_ns'],row['lane_available_ns'])
            expected='output_ready_ns' if row['priority']=='urgent' else 'persist_complete_ns'
            self.assertEqual(row['response_ns'],row[expected]-row['arrival_ns'])
        # Independent accounting of the same common-window occupancy path.
        path=offline.thermal_path('test','gpu',forced,self.model)
        self.assertTrue(math.isclose(path[-1]['cumulative_energy_j'],
            forced['thermal']['energy_j'],abs_tol=1e-6))
        self.assertTrue(math.isclose(path[-1]['ap_c'],forced['thermal']['ap_final_c'],abs_tol=1e-6))

    def test_rule_gate_is_not_a_numerical_improvement_test(self):
        x={'planned':1,'complete':1,'unfinished':0,'urgent_miss':0,'normal_miss':0,
           'responses_ms':{'r':100.},'energy_j':120.,'ap_peak_c':30.,'ap_exceed_s':0.,
           'urgent_n':0,'normal_n':1}
        y=copy.deepcopy(x);y['energy_j']=119.;y['responses_ms']['r']=101.
        self.assertFalse(check.no_worse(y,x,self.spec['numeric_tolerance']))
        self.assertAlmostEqual(check.delta(y,x)['energy_j'],-1.)

    def test_frozen_result_and_plan_denominator(self):
        result=check.read(check.OUTPUT/'RUN_SUMMARY.json')
        self.assertEqual(result['simulations'],24)
        self.assertFalse(result['first_action_cpu_rule_gate_passed'])
        self.assertFalse(result['experiment_ready'])
        self.assertEqual(len(self.spec['cases'])*len(self.spec['branches'])*2,24)


if __name__=='__main__':
    unittest.main()
