"""Pure reward/fresh/restore/budget contracts; environment and Adam step forbidden."""
import copy
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np
import torch
from tools import d1_atc_energy_study as s
from tools import d1_atc_energy_targets as labels
from tools import d1_atc_energy_ppo as learning
from tools import d1_atc_energy_budget as budget
from tools.test_d1_atc_waitlink import WaitLinkStudy


class EnergyContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        WaitLinkStudy.setUpClass()
        cls.fixture = WaitLinkStudy()
        cls.reg = dict(sources={"pure": "fixture"}, input_sha="pure")

    def model(self, arm="CONTROL", seed=1013):
        return learning.Learner(seed, s.deps(self.reg, arm, seed))

    def labels_fixture(self):
        controller, reference = self.fixture.labels_fixture(learning.COUPLING)
        reference["curve"].append((180, 30.2))
        reference["row"]["peak_ap_c"] = 30.2
        return controller, reference

    def test_all12_fresh_same_seed_components_native_update_and_no_inheritance(self):
        receipt = s.paired_initial_proof(self.reg)
        self.assertEqual(set(receipt), {str(seed) for seed in s.SEEDS})
        self.assertEqual(len(learning.ARMS), 4)
        self.assertIs(learning.Learner._update, learning.native.Learner._update)
        self.assertIs(learning.Learner.controller, learning.native.Learner.controller)
        for arm in learning.ARMS:
            model = self.model(arm)
            self.assertEqual(model.episodes, 0); self.assertFalse(model.optimizer.state)
            self.assertEqual(model.network.coupling, "DROP_FLAG_WAIT1")
            np.testing.assert_array_equal(model.multipliers, [1 if arm == "CONTROL" else 5] * 2 + [100] * 6 + [20])

    def test_restore_rejects_objective_version_reward_weights_seed_sources_settings(self):
        model = self.model("ECO5"); data = model.snapshot(); dep = model.dependencies
        alterations = dict(version="atc-waitlink-learner-v8", objective="old", reward_arm="CONTROL", seed=1019,
                           schema="old", settings={})
        for key, value in alterations.items():
            with self.assertRaises(ValueError):
                learning.Learner.from_snapshot(dict(data, **{key: value}), dep)
        with self.assertRaises(ValueError):
            learning.Learner.from_snapshot(dict(data, multipliers=np.array([1.,1.,*([100.]*6),20.])), dep)
        with self.assertRaises(ValueError):
            learning.Learner.from_snapshot(data, dict(dep, sources={"changed": "source"}))
        with self.assertRaises(ValueError):
            learning.Learner.from_snapshot(data, s.deps(self.reg, "CONTROL", 1013))

    def test_same_labels_control_eco_and_gate_when_service_good(self):
        controller, raw = self.labels_fixture(); before = s.parent.payload_digest(raw)
        expected = learning.native.targets(controller, raw, 120, learning.COUPLING, raw)
        for arm in ("CONTROL", "ECO5", "GATED_ECO5"):
            actual = labels.targets(controller, raw, 120, arm, raw)
            for old, new in zip(expected[0], actual[0]):
                for key in ("target", "valid", "state", "candidates", "mask"):
                    np.testing.assert_array_equal(old[key], new[key])
            for old, new in zip(expected[1:], actual[1:]):
                np.testing.assert_array_equal(old, new)
        self.assertEqual(before, s.parent.payload_digest(raw))

    def test_gate_failed_clips_negative_only_preserves_rewards_service_positive_cost(self):
        controller, reference = self.labels_fixture(); raw = copy.deepcopy(reference)
        raw["row"]["urgent_p95_ms"] = 300
        raw["result"]["ledger"][0]["response_ns"] = .3e9
        raw["result"]["ledger"][0]["output_ready_ns"] = 35.3e9
        raw["segments"][1]["end_s"] = 35.3
        raw["segments"][2]["start_s"] = 35.3
        raw["row"]["energy_j"] = 120 + .3 * controller.frozen["energy_increment_w"]["classification_CPU"]
        raw["curve"] = [(35,30.),(36,30.05),(120,30.01),(180,30.08)]
        raw["row"]["peak_ap_c"] = 30.08
        before = s.parent.payload_digest(raw)
        old = labels.targets(controller, raw, 120, "ECO5", reference)
        new = labels.targets(controller, raw, 120, "GATED_ECO5", reference)
        self.assertFalse(labels.service_gate(raw, reference))
        self.assertTrue(any(np.any(frame["target"][1:3] < 0) for frame in old[0]))
        for first, second in zip(old[0], new[0]):
            np.testing.assert_array_equal(second["target"][1:3], np.maximum(first["target"][1:3], 0.))
            np.testing.assert_array_equal(second["target"][[0,*range(3,10)]], first["target"][[0,*range(3,10)]])
            for key in ("state", "candidates", "mask", "valid"):
                np.testing.assert_array_equal(first[key], second[key])
        np.testing.assert_array_equal(new[1][:2], new[0][0]["target"][1:3])
        np.testing.assert_array_equal(new[1][2:], old[1][2:]); np.testing.assert_array_equal(new[3], old[3])
        self.assertEqual(before, s.parent.payload_digest(raw))
        # A positive AP loss remains positive even when the E benefit is clipped.
        raw["curve"][1] = (36,30.3)
        positive = labels.targets(controller, raw, 120, "GATED_ECO5", reference)
        self.assertGreater(float(positive[0][0]["target"][2]), 0.)

    def test_AP180_only_changes_AP_offline_target_and_episode_cost(self):
        controller, reference = self.labels_fixture(); raw = copy.deepcopy(reference)
        raw["curve"][-1] = (180,30.15); raw["row"]["peak_ap_c"] = 30.15
        first = labels.targets(controller, raw, 120, "GATED_ECO5", reference)
        second = labels.targets(controller, raw, 120, "GATED_ECO5_AP180", reference)
        self.assertTrue(labels.service_gate(raw, reference))
        self.assertEqual(float(first[0][0]["target"][2]), 0.)
        self.assertAlmostEqual(float(second[0][0]["target"][2]), -.5, places=5)
        for old, new in zip(first[0], second[0]):
            np.testing.assert_array_equal(old["target"][[0,1,*range(3,10)]], new["target"][[0,1,*range(3,10)]])
        self.assertEqual(second[1][1], second[0][0]["target"][2])
        missing = copy.deepcopy(raw); missing["curve"].pop()
        with self.assertRaises(ValueError): labels.targets(controller, missing, 120, "GATED_ECO5_AP180", reference)

    def test_gate_completeness_units_declared_original_failures_and_P95(self):
        _, reference = self.labels_fixture()
        for key in ("completed", "completed_work_units"):
            raw = copy.deepcopy(reference); raw["row"][key] -= 1
            self.assertFalse(labels.service_gate(raw, reference))
        for key in labels.SERVICE:
            raw = copy.deepcopy(reference); raw["row"][key] += 1
            self.assertFalse(labels.service_gate(raw, reference))
        raw = copy.deepcopy(reference); raw["row"]["urgent_p95_ms"] = None
        self.assertFalse(labels.service_gate(raw, reference))

    def test_partial_pending_restore_action_shuffle_rng_exact_without_update(self):
        controller, raw = self.labels_fixture()
        frames, costs, valid, _ = labels.targets(controller, raw, 120, "GATED_ECO5_AP180", raw)
        model = self.model("GATED_ECO5_AP180")
        with patch.object(model.optimizer, "step", side_effect=AssertionError("pure check Adam forbidden")):
            for _ in range(3): model.add(frames, costs, valid, raw["row"])
        before = s.parent.payload_digest(model.snapshot())
        with tempfile.TemporaryDirectory(prefix="energy13-pure-", dir=s.ROOT.parent) as directory:
            target = Path(directory) / "partial.pt"; model.save(target)
            restored = learning.Learner.load(target, model.dependencies)
            self.assertEqual(before, s.parent.payload_digest(restored.snapshot()))
            self.assertEqual(len(restored.pending),3); self.assertEqual(restored.steps,0)
            self.assertTrue(torch.equal(torch.rand(5,generator=model.action_rng), torch.rand(5,generator=restored.action_rng)))
            self.assertTrue(torch.equal(torch.randperm(17,generator=model.shuffle_rng), torch.randperm(17,generator=restored.shuffle_rng)))

    def test_boundary_stop_precedes_consumption_and_single_worker_lock(self):
        worker = budget.Budget.__new__(budget.Budget); worker.folder = s.ROOT.parent
        worker.reg = dict(metadata=dict(deadline_unix=1000,final_reserve_seconds=1800))
        worker.start = 1.; worker.rows = []; worker.append = MagicMock()
        with patch("time.time", return_value=999), self.assertRaises(budget.ControlledStop):
            with worker.environment("not_consumed", "train", True): self.fail("body executed")
        worker.append.assert_not_called()
        with tempfile.TemporaryDirectory(prefix="energy13-budget-",dir=s.ROOT.parent) as directory:
            one = budget.Budget.register(Path(directory)/"worker",dict(deadline_unix=1e20,final_reserve_seconds=1800))
            two = budget.Budget(one.folder)
            with one.session():
                with self.assertRaises(FileExistsError):
                    with two.session(): self.fail("second worker admitted")

    def stage(self, ep, damage=0, gain=False, key=10.):
        return dict(episode=ep,damage_conditions=damage,meaningful_cost_gain=gain,eligible_guard=True,
                    risk_key=[0,0,0,0,0,0,100.,key,30.],cost_key=[key,30.,100.])

    def test_stop_all_cost_arms_not_single_bad_arm_and_512_not_additional(self):
        history = {f"{arm}_{seed}":[self.stage(ep) for ep in (512,1024,2048)] for arm in s.ARMS for seed in s.SEEDS}
        for seed in (1013,1019):
            for index,item in enumerate(history[f"ECO5_{seed}"]): item["damage_conditions"] = index
        self.assertIsNone(s.continuation_stop(history))
        for arm in s.COST_ARMS:
            for seed in (1013,1019):
                for index,item in enumerate(history[f"{arm}_{seed}"]): item["damage_conditions"] = index
        self.assertEqual(s.continuation_stop(history),"all3costarms_two_transition_damage_at_two_seeds")
        history = {f"{arm}_{seed}":[self.stage(ep) for ep in (512,1024,2048)] for arm in s.ARMS for seed in s.SEEDS}
        self.assertIsNone(s.continuation_stop(history))
        for values in history.values(): values.append(self.stage(4096))
        self.assertEqual(s.continuation_stop(history),"three_additional_stage_stagnation_all3costarms9seeds")
        history["GATED_ECO5_AP180_1019"][-1]["meaningful_cost_gain"] = True
        self.assertIsNone(s.continuation_stop(history))
        history["GATED_ECO5_AP180_1019"][-1]["meaningful_cost_gain"] = False
        history["ECO5_1013"][-1]["risk_key"][6] = 99.
        self.assertIsNone(s.continuation_stop(history))

    def test_namespace_counts_and_source_includes_tests(self):
        self.assertEqual(len(s.parent.cases(s.CONFIRM)),176)
        self.assertEqual(176 * (len(s.BASES)+len(s.ARMS)*len(s.SEEDS)+3),3696)
        self.assertIn("tools/test_d1_atc_energy.py",s.NEW_FILES)
        with patch.object(s.parent,"collect",side_effect=AssertionError("environment forbidden")):
            self.assertEqual(len(s.source_bindings({"sources":{}})),7)


if __name__ == "__main__": unittest.main()
