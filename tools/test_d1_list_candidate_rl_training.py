"""Pure weighted-loss/dual/serialization tests: zero environment/optimizer steps."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import torch

from tools import d1_list_candidate_rl as core
from tools import d1_list_candidate_rl_training as training


def episodes(network):
    """Synthetic ABI tensors, deliberately not device or scheduling evidence."""
    rng = np.random.RandomState(21); result = []
    for episode_index, length in enumerate((3, 5)):
        rows = []
        for i in range(length):
            state = rng.normal(size=56).astype(np.float32)
            candidates = rng.normal(size=(8, 28)).astype(np.float32)
            mask = np.arange(8) < (1 if i == 0 else 2+i)
            action = int(i % int(mask.sum()))
            with torch.no_grad():
                dist, value = network(torch.from_numpy(state)[None], torch.from_numpy(candidates)[None], torch.from_numpy(mask)[None])
            rows.append(dict(state=state, candidates=candidates, mask=mask, action=action,
                informative=bool(mask.sum()>1), old_value=value[0].numpy().copy(),
                logprob=float(dist.log_prob(torch.tensor([action])).item()),
                target=np.asarray([.1*(i+1), -.2, 0., 1., 2., .05], dtype=np.float32),
                valid=np.asarray([episode_index==0, episode_index==0, True, True, True, True])))
        result.append(rows)
    return result


class Pure(unittest.TestCase):
    def setUp(self):
        torch.set_num_threads(1); torch.manual_seed(11)
        self.network = core.ActorCritic(); self.data = episodes(self.network)
        self.multipliers = [1., 10., 1., 1., 1.]

    def test_fixed_partition_matches_core_full_loss_and_scaled_weighted_mean(self):
        prepared = training.prepare_batch(self.network, self.data, self.multipliers)
        full = core.ppo_losses(self.network, self.data, self.multipliers)
        indices = (torch.tensor([0, 3]), torch.tensor([1, 4, 7]), torch.tensor([2, 5, 6]))
        for name in ('loss', 'actor', 'critic', 'entropy'):
            unscaled = sum(training.minibatch_losses(self.network, prepared, idx)[name] for idx in indices)
            scaled = sum(training.minibatch_losses(self.network, prepared, idx, unbiased_scale=True)[name]*len(idx)/prepared['n'] for idx in indices)
            # This checks float32 loss accounting, not a KPI acceptance margin.
            torch.testing.assert_close(unscaled, full[name], atol=2e-6, rtol=1e-5)
            torch.testing.assert_close(scaled, full[name], atol=2e-6, rtol=1e-5)

    def test_episode_weights_and_invalid_channel_do_not_leak(self):
        prepared = training.prepare_batch(self.network, self.data, self.multipliers)
        self.assertEqual(prepared['sampled_choices'], 6)
        d = prepared['tensors']
        for sl in prepared['slices']:
            self.assertAlmostEqual(float(d['value_weight'][sl].sum()), .5, places=6)
            self.assertAlmostEqual(float(d['entropy_weight'][sl].sum()), .5, places=6)
        self.assertTrue(torch.equal(prepared['raw_advantage'][3:, :2], torch.zeros((5, 2))))
        zero_j = training.prepare_batch(self.network, self.data, [0., 10., 1., 1., 1.])
        self.assertEqual(int(torch.count_nonzero(zero_j['direct_energy'])), 0)

    def test_dual_is_episode_mean_valid_signed_J_and_positive_services(self):
        episodes = [dict(costs=np.asarray([-2., 0., 1., 2., .1]), valid=np.ones(6, bool)),
                    dict(costs=np.asarray([1000., 0., 3., 0., .3]), valid=np.asarray([True, False, True, True, True, True]))]
        after, means = training.dual_update(self.multipliers, episodes)
        self.assertEqual(means, [-2., 0., 2., 1., .2])
        np.testing.assert_array_equal(after, np.asarray([.98, 10., 1.02, 1.01, 1.002]))
        bad = copy.deepcopy(episodes); bad[0]['costs'][2] = -1.
        with self.assertRaisesRegex(ValueError, 'positive-part'): training.dual_update(self.multipliers, bad)

    def test_wrong_dtype_forced_sample_and_old_log_rejected(self):
        for change in ('dtype', 'force', 'log'):
            bad = copy.deepcopy(self.data)
            if change == 'dtype': bad[0][0]['state'] = bad[0][0]['state'].astype(np.float64)
            elif change == 'force': bad[0][0]['informative'] = True
            else: bad[0][1]['logprob'] = None
            with self.assertRaises(ValueError): training.prepare_batch(self.network, bad, self.multipliers)

    def test_boundary_checkpoint_partial_batch_rng_and_dependency_guard_without_updates(self):
        frozen, case = core.p.inputs(core.p.BUNDLE)
        probe = core.Controller(frozen, case['initial'], feature_variant='head2+C_next')
        dependencies = training.dependency_manifest({'trace_contract': 'pure-fixture-only'})
        learner = training.Learner(11, probe.schema_id, dependencies)
        data = episodes(learner.network)[0]
        learner.add_episode(data, dict(planned=1, completed=1), np.asarray([-.2, 0., 1., 2., .05]),
                            np.ones(6, bool), cursor={'next': 1}, consumption={'learning_starts': 0})
        self.assertIsNone(learner.update_if_ready())
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'boundary.pt'; learner.save(path)
            expected = training.rng_state()
            clone = training.Learner.load(path, expected_schema_id=probe.schema_id, expected_dependencies=dependencies)
            self.assertEqual(training.state_digest(expected), training.state_digest(training.rng_state()))
            self.assertEqual(training.state_digest(learner.pending_episodes), training.state_digest(clone.pending_episodes))
            self.assertEqual(clone.cursor, {'next': 1}); self.assertEqual(clone.optimizer_steps, 0)
            self.assertFalse(clone.optimizer.state)
            wrong = dict(dependencies, caller_contracts={'trace_contract': 'changed'})
            with self.assertRaises(ValueError): training.Learner.load(path, expected_schema_id=probe.schema_id, expected_dependencies=wrong)
            with self.assertRaises(ValueError): training.Learner.load(path, expected_schema_id='wrong', expected_dependencies=dependencies)
        self.assertEqual(learner.optimizer_steps, 0)

    def test_update_failure_rolls_back_weights_rng_and_keeps_partial_batch_without_steps(self):
        learner = training.Learner(11, 'synthetic-loss-fixture', {'fixture': 'no-native-no-step'})
        learner.pending_episodes = [dict(data=[]) for _ in range(8)]
        before = learner.snapshot()
        def fail():
            with torch.no_grad(): next(learner.network.parameters()).add_(1.)
            torch.rand(4)
            raise ValueError('injected pre-optimizer failure')
        with patch.object(learner, '_update_ready_batch', side_effect=fail):
            with self.assertRaisesRegex(ValueError, 'injected'): learner.update_if_ready()
        self.assertEqual(training.state_digest(before['network']), training.state_digest(learner.network.state_dict()))
        self.assertEqual(training.state_digest(before['rng']), training.state_digest(training.rng_state()))
        self.assertEqual(learner.optimizer_steps, 0); self.assertEqual(len(learner.pending_episodes), 8)
        self.assertTrue(learner.failed_updates[0]['rolled_back'])


if __name__ == '__main__': unittest.main()
