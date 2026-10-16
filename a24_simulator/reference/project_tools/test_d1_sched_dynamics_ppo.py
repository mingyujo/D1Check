"""Pure ABI/PPO math checks. Synthetic Adam only; zero plant episodes."""
import copy
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import torch

from tools import d1_sched_dynamics_ppo as rl

SMALL = rl.ABI("synthetic-dynamics-v17", 5, 4, 7)


def frames(network, count=2, sole=False):
    output = []
    for index in range(count):
        state = np.array([index*.1, .2, .3, .4, .5], dtype=np.float32)
        candidates = np.zeros((SMALL.slots, SMALL.action_dim), dtype=np.float32)
        candidates[:3, 0] = [1., 2., 3.]
        mask = np.zeros(SMALL.slots, dtype=np.bool_)
        mask[:1 if sole else 3] = True
        with torch.no_grad():
            dist, value = network(torch.from_numpy(state)[None], torch.from_numpy(candidates)[None], torch.from_numpy(mask)[None])
        action = 0 if sole else index % 3
        output.append(dict(now_ns=index*1_000_000_000, state=state, candidates=candidates, mask=mask, action=action, informative=not sole, logprob=float(dist.log_prob(torch.tensor([action]))), old_value=float(value[0, 0]), target=np.array([-float(index+1)], dtype=np.float32), valid=np.array([True])))
    return output


def synthetic_result():
    ledger = [dict(id="q0", arrival_ns=0, priority="urgent", deadline_offset_ns=1_500_000_000, response_ns=500_000_000, response_at_ns=500_000_000, status="succeeded"), dict(id="q1", arrival_ns=0, priority="normal", deadline_offset_ns=6_000_000_000, status="unfinished")]
    service = sum(rl._service_cost(r, 2, 1, 1) for r in ledger)
    return dict(ledger=ledger, metrics=dict(service_cost=service, resident_baseline_j=12.), learning_cost_trace=[dict(time_ns=0, energy_j=0., ap_excess_area_c_s=0.), dict(time_ns=1_000_000_000, energy_j=2., ap_excess_area_c_s=1.), dict(time_ns=rl.HORIZON_NS, energy_j=24., ap_excess_area_c_s=60.)])


class Contracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(1)

    def test_fresh_initialization_mask_and_global_rng(self):
        before = torch.random.get_rng_state().clone()
        a = rl.Learner(1701, {"synthetic": "v1"}, abi=SMALL)
        self.assertTrue(torch.equal(before, torch.random.get_rng_state()))
        b = rl.Learner(1701, {"synthetic": "v1"}, abi=SMALL)
        c = rl.Learner(1703, {"synthetic": "v1"}, abi=SMALL)
        self.assertEqual(rl.digest(a.snapshot()), rl.digest(b.snapshot()))
        self.assertNotEqual(rl.digest(a.network.state_dict()), rl.digest(c.network.state_dict()))
        self.assertFalse(a.optimizer.state)
        self.assertEqual(a.steps, 0)
        f = frames(a.network, 1)[0]
        dist, _ = a.network(torch.from_numpy(f["state"])[None], torch.from_numpy(f["candidates"])[None], torch.from_numpy(f["mask"])[None])
        np.testing.assert_allclose(dist.probs.detach().numpy()[0, :3], np.repeat(1/3, 3), rtol=1e-6)
        self.assertEqual(float(dist.probs[0, 3:].sum().detach()), 0.)

    def test_actor_rejects_bad_masks_dimensions_and_nonfinite(self):
        net = rl.ActorCritic(SMALL)
        state = torch.zeros(1, SMALL.state_dim)
        cand = torch.zeros(1, SMALL.slots, SMALL.action_dim)
        mask = torch.ones(1, SMALL.slots, dtype=torch.bool)
        with self.assertRaises(ValueError):
            net(state, cand, mask & False)
        with self.assertRaises(ValueError):
            net(state[:, :-1], cand, mask)
        with self.assertRaises(ValueError):
            net(state, cand, mask.float())
        state[0, 0] = float("nan")
        with self.assertRaises(ValueError):
            net(state, cand, mask)

    def test_native_clipping_and_partition_loss_exact(self):
        from tools import d1_s26_npu_ppo as native
        learner = rl.Learner(1701, {}, abi=SMALL)
        episodes = [frames(learner.network, 3), frames(learner.network, 2)]
        episodes[0][0]["logprob"] -= .7
        episodes[0][1]["logprob"] += .7
        batch = rl.prepare(learner.network, episodes)
        ids = torch.arange(batch["n"])
        full = rl.minibatch_losses(learner.network, batch, ids)
        expected = native.minibatch_losses(learner.network, batch, ids)
        for key in full:
            self.assertEqual(float(full[key].detach()), float(expected[key].detach()))
            partition = sum(rl.minibatch_losses(learner.network, batch, chunk)[key] for chunk in ids.chunk(3))
            self.assertAlmostEqual(float(full[key].detach()), float(partition.detach()), places=5)

    def test_sole_choice_actor_zero_critic_active(self):
        learner = rl.Learner(1701, {}, abi=SMALL)
        batch = rl.prepare(learner.network, [frames(learner.network, 2, sole=True)])
        self.assertEqual(batch["normalization"]["informative_episodes"], 0)
        losses = rl.minibatch_losses(learner.network, batch, [0, 1])
        self.assertEqual(float(losses["actor"].detach()), 0.)
        self.assertEqual(float(losses["entropy"].detach()), 0.)
        losses["loss"].backward()
        actor_norm = sum(float(p.grad.square().sum()) for p in learner.network.actor.parameters() if p.grad is not None)
        self.assertEqual(actor_norm, 0.)
        self.assertGreater(float(learner.network.critic.weight.grad.square().sum()), 0.)

    def test_post_episode_reward_telescope_and_incomplete_penalty(self):
        learner = rl.Learner(1701, {}, abi=SMALL)
        controller = SimpleNamespace(frames=frames(learner.network, 3), errors=[])
        result = synthetic_result()
        labels = rl.targets(controller, result)
        expected = 10*result["metrics"]["service_cost"]+1.2+.5
        self.assertAlmostEqual(-sum(f["reward"] for f in labels), expected, places=8)
        self.assertAlmostEqual(float(labels[0]["target"][0]), -expected, places=4)
        self.assertLess(labels[-1]["reward"], -250.)
        self.assertNotIn("reward", controller.frames[0])
        result["learning_cost_trace"][1]["energy_j"] = 25.
        with self.assertRaises(ValueError):
            rl.targets(controller, result)

    def test_checkpoint_partial_resume_optimizer_and_rng_exact(self):
        settings = rl.Settings(epochs=1)
        learner = rl.Learner(1701, {"synthetic": "v1"}, settings, SMALL)
        learner.pending = [frames(learner.network, 2) for _ in range(8)]
        learner.episodes = 8
        learner.update()  # One synthetic native update / one Adam step.
        self.assertTrue(learner.logs[-1]["actor_changed"])
        self.assertGreater(learner.logs[-1]["actor_gradient_max"], 0.)
        learner.pending = [frames(learner.network, 2) for _ in range(3)]
        learner.episodes = 11
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/"synthetic.pt"
            learner.save(path)
            loaded = rl.Learner.load(path, {"synthetic": "v1"}, settings, SMALL)
            self.assertEqual(rl.digest(learner.snapshot()), rl.digest(loaded.snapshot()))
            self.assertEqual(len(loaded.pending), 3)
            with self.assertRaises(ValueError):
                rl.Learner.load(path, {"synthetic": "v2"}, settings, SMALL)
            with self.assertRaises(ValueError):
                rl.Learner.load(path, {"synthetic": "v1"}, rl.Settings(), SMALL)
            self.assertTrue(torch.equal(torch.rand(3, generator=learner.action_rng), torch.rand(3, generator=loaded.action_rng)))
            self.assertTrue(torch.equal(torch.randperm(5, generator=learner.shuffle_rng), torch.randperm(5, generator=loaded.shuffle_rng)))
            learner.finish()
            loaded.finish()  # Two more synthetic updates / two Adam steps.
            self.assertEqual(rl.digest(learner.snapshot()), rl.digest(loaded.snapshot()))
            self.assertEqual(loaded.steps, 2)
            self.assertFalse(loaded.pending)

    def test_fixed_argmax_does_not_change_model_or_action_rng(self):
        learner = rl.Learner(1701, {}, abi=SMALL)
        f = frames(learner.network, 1)[0]
        jobs = [[({"id": "a"}, "CPU")], [({"id": "b"}, "GPU")], []]
        def builder(dev, waiting):
            return dict(state=f["state"].copy(), candidates=f["candidates"].copy(), mask=f["mask"].copy(), physical_mask=f["mask"].copy(), actions=jobs, diagnostics={})
        dev = SimpleNamespace(now=0, feasible=lambda j: True)
        controller = rl.Controller(learner.network, learner.action_rng, True, False, builder=builder, fallback=lambda d,w: jobs[0])
        before = rl.digest(learner.snapshot())
        self.assertEqual(controller.choose(dev, [{"id": "a"}]), jobs[0])
        self.assertEqual(before, rl.digest(learner.snapshot()))
        self.assertFalse(controller.errors)
        self.assertFalse(controller.frames)

    def test_input_mismatch_explicit_edd_fallback_training_reject(self):
        learner = rl.Learner(1701, {}, abi=SMALL)
        dev = SimpleNamespace(now=0, feasible=lambda jobs: True)
        chosen = [({"id": "fallback"}, "CPU")]
        controller = rl.Controller(learner.network, learner.action_rng, False, True, builder=lambda d,w: {}, fallback=lambda d,w: chosen)
        self.assertEqual(controller.choose(dev, [{}]), chosen)
        self.assertEqual(len(controller.errors), 1)
        controller.frames = frames(learner.network, 1)
        with self.assertRaises(ValueError):
            rl.targets(controller, synthetic_result())

    def test_real_bank_controller_common_mask_and_future_privacy(self):
        from tools import d1_sched_dynamics_policy as policy
        class PublicOnly:
            now = 2_000_000_000
            _events = ["private future phase"]
            _remaining = 999999
            def routes(self, q):
                return ("CPU", "GPU", "NPU") if q["task"] == "classification" else ("CPU",)
            def estimate(self, q, backend, jobs=()):
                return [1_000_000, (40_000_000 if backend == "CPU" else 20_000_000)*q.get("work_units", 1), 1_000_000, 1_000_000, 1_000_000]
            def feasible(self, jobs):
                return len(jobs) == 1 and jobs[0][1] in self.routes(jobs[0][0])
            def public(self):
                return dict(now_ns=self.now, lanes={b:None for b in policy.BACKENDS}, npu_enabled=True, observed_responses=0, ap_c=31., skin_c=30.5, reference_ap_c=30., ambient_c=30., power_w=1.2, recent_activity={b:.1 for b in policy.BACKENDS}, recent_load={b:.1 for b in policy.BACKENDS}, activation_memory={b:.2 for b in policy.BACKENDS}, observed_history=[dict(time_ns=0, ap_c=30., power_w=1.), dict(time_ns=2_000_000_000, ap_c=31., power_w=1.2)])
            @property
            def next_event(self):
                raise AssertionError("private future event accessed")
            @property
            def records(self):
                raise AssertionError("realized durations accessed")
        dev = PublicOnly()
        waiting = [dict(id="q0", ordinal=0, task="classification", priority="urgent", arrival_ns=0, deadline_offset_ns=1_500_000_000, work_units=1), dict(id="q1", ordinal=1, task="detection", priority="normal", arrival_ns=1_000_000_000, deadline_offset_ns=6_000_000_000, work_units=3)]
        bank = policy.build(dev, waiting)
        learner = rl.Learner(1701, {"synthetic_full_public_ABI":True})
        controller = learner.controller(deterministic=True, collect=True)
        controller.choose(dev, waiting)
        self.assertFalse(controller.errors)
        np.testing.assert_array_equal(controller.frames[0]["state"], bank["state"])
        np.testing.assert_array_equal(controller.frames[0]["candidates"], bank["candidates"])
        np.testing.assert_array_equal(controller.frames[0]["mask"], bank["mask"])
        self.assertEqual(learner.steps, 0)
        dev._remaining = -5
        dev._events = ["different future realization"]
        again = policy.build(dev, waiting)
        for key in ("state", "candidates", "mask", "physical_mask"):
            np.testing.assert_array_equal(bank[key], again[key])

    def test_extended_declared_deadline_preserves_original_slo_penalty(self):
        from tools import d1_s26_npu_engine as service
        learner = rl.Learner(1701, {}, abi=SMALL)
        controller = SimpleNamespace(frames=frames(learner.network, 3), errors=[])
        result = synthetic_result()
        result["ledger"] = [dict(id="q0", arrival_ns=0, priority="urgent", deadline_offset_ns=2_500_000_000, response_ns=2_000_000_000, response_at_ns=2_000_000_000, status="succeeded"), dict(id="q1", arrival_ns=0, priority="normal", deadline_offset_ns=9_000_000_000, response_ns=7_000_000_000, response_at_ns=7_000_000_000, status="succeeded")]
        expected_service = sum(service.request_cost(row, 2, 1, 1) for row in result["ledger"])
        self.assertGreaterEqual(expected_service, 25.)  # Original U20+N5 misses remain.
        result["metrics"]["service_cost"] = expected_service
        labels = rl.targets(controller, result)
        self.assertAlmostEqual(-sum(f["reward"] for f in labels), 10*expected_service+1.2+.5, places=8)
        result["ledger"][0]["deadline_offset_ns"] = 2_500_000_001
        with self.assertRaises(ValueError):
            rl.targets(controller, result)


if __name__ == "__main__":
    unittest.main()
