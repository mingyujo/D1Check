"""Pure fresh-pairing, reward gate calculus and loader contracts; no simulation."""
import copy
import unittest
import numpy as np
import torch
from tools import d1_atc_costguard_targets as target
from tools import d1_atc_costguard_ppo as rl
from tools import d1_atc_costguard_study as s
from tools import d1_atc_costguard_budget as budget
from tools import d1_atc_costguard_orchestrator as run
from tools import d1_atc_waitlink_targets as old_target
from tools import d1_atc_waitlink_ppo as old_rl
from tools import test_d1_atc_waitlink as fixture_module


class CostGuardContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):fixture_module.WaitLinkStudy.setUpClass()
    def fixture(self):
        owner=fixture_module.WaitLinkStudy();controller,raw=owner.labels_fixture('DROP_FLAG_WAIT1')
        raw['row'].update(arrival_seed=923510101,condition=0,family='idle',factor='fixed')
        raw['curve']=[(at,30. if at==35 else 30.1) for at in range(35,181)]
        return controller,raw
    def dependencies(self,arm):
        return s.deps(dict(sources={'pure':'fixture'},input_sha='pure'),arm)
    def test_fresh_paired_network_adam_rng_and_new_objective_loader(self):
        models=[rl.Learner(1103,self.dependencies(arm)) for arm in rl.ARMS]
        for model in models:
            self.assertEqual(model.episodes,0);self.assertEqual(model.steps,0);self.assertFalse(model.optimizer.state)
            self.assertEqual(model.network.coupling,'DROP_FLAG_WAIT1')
            self.assertEqual(model.snapshot()['reward_arm'],model.reward_arm)
        for model in models[1:]:
            for name,value in models[0].network.state_dict().items():self.assertTrue(torch.equal(value,model.network.state_dict()[name]))
            self.assertTrue(torch.equal(models[0].action_rng.get_state(),model.action_rng.get_state()))
            self.assertTrue(torch.equal(models[0].shuffle_rng.get_state(),model.shuffle_rng.get_state()))
        np.testing.assert_array_equal(models[0].multipliers,[1,1,*([100]*6),20])
        np.testing.assert_array_equal(models[1].multipliers,[5,5,*([100]*6),20])
        with self.assertRaises(ValueError):rl.Learner.from_snapshot(dict(models[0].snapshot(),objective=old_rl.OBJECTIVE),models[0].dependencies)
        with self.assertRaises(ValueError):rl.Learner.from_snapshot(models[0].snapshot(),models[1].dependencies)
        with self.assertRaises(ValueError):rl.Learner.from_snapshot(dict(models[1].snapshot(),multipliers=models[0].multipliers),models[1].dependencies)
    def test_control_cost5_and_gatepass_labels_exact_original(self):
        controller,raw=self.fixture()
        expected=old_target.targets(controller,raw,120,'DROP_FLAG_WAIT1',raw)
        for arm in rl.ARMS:
            actual=target.targets(controller,raw,120,arm,raw)
            for left,right in zip(expected[0],actual[0]):np.testing.assert_array_equal(left['target'],right['target'])
            for left,right in zip(expected[1:],actual[1:]):np.testing.assert_array_equal(left,right)
            self.assertTrue(actual[0][0]['costguard_diagnostics']['gate_pass'])
    def test_absolute_gate_relative_tie_is_not_enough_and_invalid_rejected(self):
        _,raw=self.fixture();ref=copy.deepcopy(raw['row']);actual=copy.deepcopy(ref)
        actual['urgent_failure']=ref['urgent_failure']=1
        self.assertFalse(target.service_gate(actual,ref))
        for key in ('urgent_p95_ms','completed_work_units'):
            for value in (None,float('nan'),float('inf')):
                with self.assertRaises(ValueError):target.service_gate(dict(actual,**{key:value}),ref)
    def test_signed_interval_example_and_canonical_energy_partition_invariant(self):
        np.testing.assert_array_equal(target.remove_negative_intervals([-1.,1.]),[1.,1.])
        actual=dict(segments=[dict(start_s=0.,end_s=36.,state='idle'),dict(start_s=36.,end_s=37.,state='positive'),dict(start_s=37.,end_s=120.,state='idle')])
        ref=dict(segments=[dict(start_s=0.,end_s=35.,state='idle'),dict(start_s=35.,end_s=36.,state='negative'),dict(start_s=36.,end_s=120.,state='idle')])
        frozen={'energy_increment_w':{'negative':2.,'positive':1.}}
        self.assertAlmostEqual(target.canonical_energy(actual,ref,frozen,35e9),.1)
        split=copy.deepcopy(actual);split['segments'][0:1]=[dict(start_s=0.,end_s=20.,state='idle'),dict(start_s=20.,end_s=36.,state='idle')]
        self.assertEqual(target.canonical_energy(actual,ref,frozen,35e9),target.canonical_energy(split,ref,frozen,35e9))
        self.assertAlmostEqual(target.canonical_energy(actual,ref,frozen,36.5e9),.05)
    def test_ap_fixed_grid_projection_and_missing_grid_invalid(self):
        actual={'curve':[(at,30. if at<37 else 33.) for at in range(35,181)]}
        ref={'curve':[(at,30. if at==35 else 32. if at<38 else 34.) for at in range(35,181)]}
        self.assertAlmostEqual(target.canonical_ap(actual,ref,35e9),30.)
        self.assertAlmostEqual(target.canonical_ap(actual,ref,36.5e9),30.)
        self.assertEqual(target.canonical_ap(actual,ref,37e9),0.)
        missing=copy.deepcopy(actual);missing['curve']=[v for v in missing['curve'] if v[0]!=40]
        with self.assertRaises(ValueError):target.canonical_ap(missing,ref,35e9)
    def test_gatefail_canonical_cost_independent_of_added_decision_frames(self):
        controller,raw=self.fixture();reference=copy.deepcopy(raw)
        raw['row'].update(urgent_failure=1,urgent_original_cap_failure=1,urgent_p95_ms=1600,energy_j=120+2*controller.frozen['energy_increment_w']['classification_CPU'])
        raw['result']['ledger'][0].update(response_ns=1.6e9,output_ready_ns=36.6e9,persist_complete_ns=36.7e9,worker_release_ns=36.8e9,lane_available_ns=37e9)
        raw['segments']=[dict(start_s=0.,end_s=35.,state='idle'),dict(start_s=35.,end_s=37.,state='classification_CPU'),dict(start_s=37.,end_s=120.,state='idle')]
        first=target.targets(controller,raw,120,'GATED_COST5',reference)
        more=copy.deepcopy(controller);extra=copy.deepcopy(more.snapshots[0]);extra['now_ns']=35.1e9;more.snapshots.insert(1,extra)
        second=target.targets(more,raw,120,'GATED_COST5',reference)
        np.testing.assert_array_equal(first[1][0:2],second[1][0:2])
        self.assertGreater(first[1][0],0.)
        self.assertEqual(first[0][0]['costguard_diagnostics']['failure_reasons'],['urgent_failure','urgent_original_cap_failure','urgent_p95_ms'])
    def test_episode_diagnostics_survive_pending_without_update_and_worker1(self):
        controller,raw=self.fixture();frames,costs,valid,_=target.targets(controller,raw,120,'CONTROL',raw)
        model=rl.Learner(1103,self.dependencies('CONTROL'));model.add(frames,costs,valid,raw['row'])
        self.assertEqual(model.episode_logs[0]['costguard']['gate_pass'],True)
        clone=rl.Learner.from_snapshot(model.snapshot(),model.dependencies)
        self.assertEqual(model.episode_logs,clone.episode_logs);self.assertEqual(clone.steps,0)
        self.assertEqual(budget.AGGREGATE['model_workers'],1)
    def test_shared_stop_any_arm_damage_but_all_arms_stagnation(self):
        stops={'CONTROL':'three_additional_stage_stagnation','COST5':None,'GATED_COST5':None}
        self.assertIsNone(run.shared_stop(stops))
        self.assertEqual(run.shared_stop({arm:'three_additional_stage_stagnation' for arm in rl.ARMS}),'all_reward_arms_three_stage_stagnation')
        stops['GATED_COST5']='two_transition_service_P95_damage_at_two_seeds'
        self.assertEqual(run.shared_stop(stops),'two_transition_service_P95_damage_at_two_seeds')


if __name__=='__main__':unittest.main()
