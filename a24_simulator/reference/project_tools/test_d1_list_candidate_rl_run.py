"""Pure clock/source/update-boundary guards. No optimizer or environment."""
import time
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
import torch
from tools import d1_list_candidate_rl_run as driver

class Guards(unittest.TestCase):
    def test_rule_network_is_not_a_torch_checkpoint(self):
        self.assertIsNone(driver.network_hash(SimpleNamespace(network=object())))
        self.assertIsNone(driver.network_hash(SimpleNamespace()))
        module=torch.nn.Linear(2,1)
        self.assertEqual(driver.network_hash(SimpleNamespace(network=module)),driver.training.state_digest(module.state_dict()))
    def learner(self):
        return SimpleNamespace(pending_episodes=[None]*8,settings=SimpleNamespace(episodes_per_update=8),update_if_ready=Mock(return_value='updated'))
    def test_expired_clock_blocks_pending_update_before_optimizer(self):
        learner=self.learner();budget=SimpleNamespace(work_guard=Mock(side_effect=TimeoutError('clock')))
        with self.assertRaises(TimeoutError):driver.update(budget,learner)
        learner.update_if_ready.assert_not_called()
    def test_partial_batch_has_no_update(self):
        learner=self.learner();learner.pending_episodes=learner.pending_episodes[:4]
        budget=SimpleNamespace(work_guard=Mock())
        self.assertIsNone(driver.update(budget,learner))
        budget.work_guard.assert_not_called();learner.update_if_ready.assert_not_called()
    def test_update_guard_does_not_charge_or_reject_full_environment_cap(self):
        budget=driver.Budget.__new__(driver.Budget);budget.deadline=time.time()+60;budget.reg=dict(source_sha256={})
        budget.phase='main';budget.consumption=lambda:dict(design_environment_starts=1536,cumulative_environment_starts=20000)
        learner=self.learner()
        with patch.object(driver.c.p,'inputs',return_value=None):
            self.assertEqual(driver.update(budget,learner),'updated')
            with self.assertRaises(TimeoutError):budget.guard()
        learner.update_if_ready.assert_called_once()
    def test_source_change_blocks_update_without_modifying_files(self):
        budget=driver.Budget.__new__(driver.Budget);budget.deadline=time.time()+60
        budget.reg=dict(source_sha256={'tools/d1_list_candidate_rl_run.py':'invalid_hash'})
        learner=self.learner()
        with self.assertRaisesRegex(ValueError,'source changed'):driver.update(budget,learner)
        learner.update_if_ready.assert_not_called()

if __name__=='__main__':unittest.main()
