"""Pure V8 coupling/likelihood/label checks: no simulator, learner update or device."""
import copy
import unittest
from unittest.mock import patch

import numpy as np
import torch

from tools import d1_atc_waitlink_policy as a
from tools import d1_atc_waitlink_ppo as rl
from tools import d1_atc_waitlink_targets as label
from tools import d1_atc_wait_policy as old
from tools import d1_atc_wait_ppo as old_rl
from tools import d1_atc_wait_targets as old_label


class WaitLinkStudy(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.f, initial, _ = a.hybrid.load()
        cls.initial = initial['initial']
        torch.set_num_threads(1)

    def fixture(self, arm=a.ARMS[0], owned=False):
        controller = a.Controller(self.f, self.initial, mode=a.RULE, coupling=arm)
        q = dict(id='0', ordinal=0, task='classification', priority='urgent',
                 arrival_ns=35e9, deadline_offset_ns=1.5e9, work_units=1)
        lanes = {b: dict(request=None, phase='AVAILABLE', since=35e9, dispatch=None)
                 for b in ('CPU', 'GPU')}
        now = 35e9
        if owned:
            owner = dict(q, id='D', ordinal=1, task='detection', priority='normal',
                         deadline_offset_ns=6e9)
            ds = a.phase_estimate(controller.estimates, owner, 'CPU')
            now += ds[0] + max(0., ds[1] - 50e6)
            q['arrival_ns'] = now
            lanes['CPU'] = dict(request=owner, phase='EXECUTING',
                                since=35e9+ds[0], dispatch=35e9)
        e = a.bank([q], lanes, now, controller.estimates, coupling=arm)
        encoded = controller.encode([q], lanes, now, e)
        return controller, q, lanes, now, e, encoded

    def labels_fixture(self, arm=a.ARMS[0]):
        c, q, _, now, e, encoded = self.fixture(arm)
        c.snapshots = [dict(copy.deepcopy(encoded), now_ns=t, chosen=e['base'],
                            actor_eligible=False) for t in (now, 35.25e9, 35.4e9)]
        r = dict(q, status='succeeded', backend='CPU', dispatch_ns=35e9,
                 execution_start_ns=35.1e9, output_ready_ns=35.2e9,
                 persist_complete_ns=35.3e9, worker_release_ns=35.35e9,
                 lane_available_ns=35.4e9, response_ns=.2e9)
        row = dict(planned=1, completed=1, incomplete=0, planned_work_units=1,
                   completed_work_units=1, urgent_planned=1, normal_planned=0,
                   urgent_failure=0, urgent_original_cap_failure=0,
                   normal_failure=0, normal_original_cap_failure=0,
                   urgent_p95_ms=200, energy_j=120+.4*self.f['energy_increment_w']['classification_CPU'],
                   peak_ap_c=30.1)
        raw = dict(row=row, result=dict(ledger=[r]), segments=[
            dict(start_s=0., end_s=35., state='idle'),
            dict(start_s=35., end_s=35.4, state='classification_CPU'),
            dict(start_s=35.4, end_s=120., state='idle')],
            curve=[(35, 30.), (36, 30.1), (120, 30.05)])
        return c, raw

    @staticmethod
    def tensors(encoded):
        return tuple(torch.from_numpy(encoded[k])[None] for k in ('state', 'candidates', 'mask'))

    def test_fresh_schema_ids_and_shared_urgent_objective(self):
        self.assertEqual((a.STATE_DIM, a.ACTION_DIM, a.SLOTS), (226, 57, 32))
        self.assertNotEqual(a.SCHEMA, old.SCHEMA)
        self.assertIn('V8', a.POLICY)
        self.assertIn('V8', a.RULE)
        self.assertEqual(len(set(rl.OBJECTIVES.values())), 1)
        networks = []
        for arm in a.ARMS:
            learner = rl.Learner(77, dict(arm=arm, schema=a.SCHEMA, sequencing='ATC'))
            np.testing.assert_array_equal(learner.multipliers, [1., 1., *([100.]*6), 20.])
            self.assertEqual(learner.episodes, 0)
            self.assertEqual(learner.steps, 0)
            self.assertEqual(learner.objective, rl.OBJECTIVE)
            networks.append(learner.network.state_dict())
            with self.assertRaises(ValueError):
                rl.Learner.from_snapshot(dict(learner.snapshot(), schema=old.SCHEMA), learner.dependencies)
        for first, other in zip(networks, networks[1:]):
            for name in first:
                self.assertTrue(torch.equal(first[name], other[name]), name)

    def test_physical_bank_state_and_raw_teacher_are_identical_to_10(self):
        for owned in (False, True):
            for arm in a.ARMS:
                c, q, lanes, now, e, encoded = self.fixture(arm, owned)
                previous = old.Controller(self.f, self.initial, mode=old.RULE)
                bank = old.bank([q], lanes, now, previous.estimates)
                old_encoded = previous.encode([q], lanes, now, bank)
                self.assertEqual(e['actions'], bank['actions'])
                self.assertEqual(e['base'], bank['base'])
                np.testing.assert_array_equal(e['mask'], bank['mask'])
                np.testing.assert_array_equal(e['physical_mask'], e['mask'])
                np.testing.assert_array_equal(encoded['state'], old_encoded['state'])
                np.testing.assert_array_equal(encoded['candidates'], old_encoded['candidates'])
                self.assertEqual(int(((encoded['candidates'][:, 52]>.5)&e['mask']).sum()), 1)
                self.assertEqual(encoded['candidates'][e['base'], 52], 1.)
                self.assertTrue(all(not e['mask'][i] for i, v in enumerate(e['actions']) if v is None))
                if owned:
                    self.assertTrue(any(v and v['kind']=='resource_wait' and e['mask'][i]
                                        for i, v in enumerate(e['actions'])))
                    self.assertTrue(any(v and v['kind']=='single' and e['mask'][i]
                                        for i, v in enumerate(e['actions'])))

    def test_drop52_changes_only_nn_embedding_and_preserves_input_and_guards(self):
        for arm in a.ARMS:
            _, _, _, _, e, encoded = self.fixture(arm, True)
            state, candidates, mask = self.tensors(encoded)
            before = candidates.clone()
            net = rl.ActorCritic(arm)
            seen = []
            handle = net.candidate.register_forward_pre_hook(lambda module, args: seen.append(args[0].detach().clone()))
            dist, value = net(state, candidates, mask)
            handle.remove()
            self.assertTrue(torch.equal(before, candidates))
            expected = before.clone()
            if arm in a.DROP_TEACHER_FLAG:
                expected[..., 52] = 0.
            self.assertTrue(torch.equal(seen[0], expected))
            self.assertTrue(torch.equal(value, torch.zeros_like(value)))
            with self.assertRaises(ValueError):
                net(state, candidates.clone().index_fill(-1, torch.tensor([52]), 0.), mask)
            duplicate = candidates.clone()
            alternatives = [i for i in np.flatnonzero(e['mask']) if i != e['base']]
            duplicate[0, alternatives[0], 52] = 1.
            with self.assertRaises(ValueError):
                net(state, duplicate, mask)
            self.assertTrue(torch.isfinite(dist.logits[mask]).all())

    def test_wait0_wait1_prior_and_sample_likelihood_use_same_distribution(self):
        for arm in a.ARMS:
            _, _, _, _, e, encoded = self.fixture(arm, True)
            state, candidates, mask = self.tensors(encoded)
            net = rl.ActorCritic(arm)
            dist, _ = net(state, candidates, mask)
            gap = torch.where(candidates[..., 2]>.5,
                              torch.minimum(candidates[..., 54], candidates[..., 56]),
                              candidates[..., 54])
            wait = candidates[..., 3]>.5
            progress = mask & ~wait
            maximum = gap.masked_fill(~progress, -torch.inf).max(-1).values
            penalty = (torch.zeros_like(maximum) if arm in a.WAIT_ZERO_GAP else
                       torch.where(progress.any(-1), maximum+1, torch.zeros_like(maximum)))
            expected = torch.distributions.Categorical(logits=(-torch.where(wait, penalty[:, None], gap)).masked_fill(~mask, -torch.inf))
            torch.testing.assert_close(dist.probs, expected.probs, rtol=0, atol=0)
            generator = torch.Generator().manual_seed(98)
            chosen = torch.multinomial(dist.probs[0], 1, generator=generator)
            torch.testing.assert_close(dist.log_prob(chosen), torch.log(dist.probs[0, chosen]), rtol=1e-6, atol=1e-6)
            waits = torch.nonzero(mask[0]&wait[0]).flatten()
            self.assertGreater(float(dist.probs[0, waits[0]].detach()), 0.)
            if arm in a.WAIT_ZERO_GAP:
                torch.testing.assert_close(dist.probs[0, waits[0]], dist.probs[0, e['base']], rtol=0, atol=0)
            else:
                self.assertLess(float(dist.probs[0, waits[0]].detach()), float(dist.probs[0, e['base']].detach()))
                old_net = old_rl.ActorCritic('URGENT_HOLD')
                old_dist, _ = old_net(state, candidates, mask)
                torch.testing.assert_close(dist.probs, old_dist.probs, rtol=0, atol=0)

    def test_pair_gap_min_and_wait1_ignore_masked_action_gaps(self):
        state = torch.zeros((1, a.STATE_DIM))
        candidates = torch.zeros((1, a.SLOTS, a.ACTION_DIM))
        mask = torch.zeros((1, a.SLOTS), dtype=torch.bool)
        mask[0, :3] = True
        candidates[0, :4, 0] = 1.
        candidates[0, 0, 1] = 1.
        candidates[0, 0, 52] = 1.
        candidates[0, 1, 2] = 1.
        candidates[0, 1, 54] = 3.
        candidates[0, 1, 56] = 1.
        candidates[0, 2, 3] = 1.
        candidates[0, 2, 54] = 10.
        candidates[0, 3, 1] = 1.
        candidates[0, 3, 54] = 9.
        for arm in a.ARMS:
            dist, _ = rl.ActorCritic(arm)(state, candidates, mask)
            torch.testing.assert_close(dist.logits[0, 1]-dist.logits[0, 0], torch.tensor(-1.))
            torch.testing.assert_close(dist.logits[0, 2]-dist.logits[0, 0],
                                       torch.tensor(0. if arm in a.WAIT_ZERO_GAP else -2.))
            self.assertEqual(float(dist.probs[0, 3].detach()), 0.)

    def test_drop52_stays_hidden_after_nonzero_actor_and_has_zero_input_gradient(self):
        for arm in a.DROP_TEACHER_FLAG:
            _, _, _, _, e, encoded = self.fixture(arm, True)
            state, candidates, mask = self.tensors(encoded)
            net = rl.ActorCritic(arm)
            with torch.no_grad():
                net.actor[-1].weight.fill_(.125)
            candidates.requires_grad_(True)
            dist, _ = net(state, candidates, mask)
            alternate = candidates.detach().clone()
            alternate[..., 52] = 0.
            alternative = next(i for i in np.flatnonzero(e['mask']) if i != e['base'])
            alternate[0, alternative, 52] = 1.
            other, _ = net(state, alternate, mask)
            torch.testing.assert_close(dist.probs, other.probs, rtol=0, atol=0)
            dist.log_prob(torch.tensor([e['base']])).sum().backward()
            self.assertTrue(torch.equal(candidates.grad[..., 52], torch.zeros_like(candidates.grad[..., 52])))
            self.assertTrue(torch.equal(net.candidate[0].weight.grad[:, 52],
                                        torch.zeros_like(net.candidate[0].weight.grad[:, 52])))

    def test_initial_argmax_tie_is_rule_and_model_error_falls_back_without_mask_changes(self):
        for owned in (False, True):
            for arm in a.ARMS:
                _, q, lanes, now, e, _ = self.fixture(arm, owned)
                net = rl.ActorCritic(arm)
                controller = a.Controller(self.f, self.initial, net, True, coupling=arm)
                with patch.object(label, 'targets', side_effect=AssertionError('online label')):
                    action = controller({}, [q], lanes, now, {}, None, None)
                self.assertEqual(controller.snapshots[-1]['chosen'], e['base'])
                self.assertEqual(controller.stats['fallback'], 0)
                self.assertEqual(action['selected'], e['actions'][e['base']]['jobs'][0])
                broken = a.Controller(self.f, self.initial, net, True, coupling=arm)
                with patch.object(net, 'forward', side_effect=ValueError('synthetic model error')):
                    result = broken({}, [q], lanes, now, {}, None, None)
                self.assertEqual(result['selected'], action['selected'])
                self.assertEqual(broken.stats['fallback'], 1)
                self.assertIn('model_error', broken.snapshots[-1])
                np.testing.assert_array_equal(broken.snapshots[-1]['mask'], e['mask'])

    def test_all_arms_exactly_reuse_10_urgent_holding_and_paired_phi_labels(self):
        for arm in a.ARMS:
            controller, reference = self.labels_fixture(arm)
            raw = copy.deepcopy(reference)
            raw['result']['ledger'][0]['response_ns'] = .3e9
            raw['result']['ledger'][0]['output_ready_ns'] = 35.3e9
            raw['row']['urgent_p95_ms'] = 300
            expected = old_label.targets(controller, raw, 120, 'URGENT_HOLD', reference)
            actual = label.targets(controller, raw, 120, arm, reference)
            for expected_frame, frame in zip(expected[0], actual[0]):
                np.testing.assert_array_equal(frame['target'], expected_frame['target'])
                np.testing.assert_array_equal(frame['valid'], expected_frame['valid'])
                np.testing.assert_array_equal(frame['state'], expected_frame['state'])
                np.testing.assert_array_equal(frame['candidates'], expected_frame['candidates'])
            for expected_array, array in zip(expected[1:], actual[1:]):
                np.testing.assert_array_equal(array, expected_array)
            self.assertAlmostEqual(float(actual[0][0]['target'][9]), 1., places=6)
            self.assertEqual(float(actual[0][-1]['target'][9]), 0.)
            same = label.targets(controller, reference, 120, arm, reference)
            self.assertAlmostEqual(float(same[0][0]['target'][0]), -.2/1.5, places=6)
            np.testing.assert_array_equal(same[0][0]['target'][[1, 2, 9]], np.zeros(3, np.float32))
            incomplete = copy.deepcopy(reference)
            incomplete['row']['completed'] = 0
            with self.assertRaises(ValueError):
                label.targets(controller, raw, 120, arm, incomplete)
            missing = copy.deepcopy(reference)
            missing['row']['urgent_p95_ms'] = None
            with self.assertRaises(ValueError):
                label.targets(controller, raw, 120, arm, missing)
        with self.assertRaises(ValueError):
            label.targets(controller, raw, 120, 'URGENT_HOLD', reference)

    def test_forward_rejects_all_masked_and_snapshot_restores_rng_without_update(self):
        _, _, _, _, _, encoded = self.fixture(owned=True)
        state, candidates, mask = self.tensors(encoded)
        for arm in a.ARMS:
            learner = rl.Learner(78, dict(arm=arm, schema=a.SCHEMA, sequencing='ATC'))
            with self.assertRaises(ValueError):
                learner.network(state, candidates, torch.zeros_like(mask))
            clone = rl.Learner.from_snapshot(learner.snapshot(), learner.dependencies)
            self.assertTrue(torch.equal(torch.rand(5, generator=learner.action_rng),
                                        torch.rand(5, generator=clone.action_rng)))
            self.assertTrue(torch.equal(torch.randperm(17, generator=learner.shuffle_rng),
                                        torch.randperm(17, generator=clone.shuffle_rng)))
            self.assertEqual(clone.steps, 0)
            self.assertEqual(clone.logs, [])


if __name__ == '__main__':
    unittest.main()
