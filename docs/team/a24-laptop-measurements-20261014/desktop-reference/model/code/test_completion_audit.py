"""Pure failure/replay fixtures; no environment rollout or optimizer step."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
import torch
import completion_audit as gate
import ppo


def recorded():
    torch.manual_seed(123)
    net = ppo.Net()
    bank = dict(requests=np.zeros((24, 24), np.float32), resources=np.zeros((3, 12), np.float32),
        global_state=np.zeros(24, np.float32), features=np.zeros((80, 16), np.float32),
        request_index=np.zeros(80, np.int64), backend_index=np.zeros(80, np.int64), mask=np.zeros(80, bool))
    bank["requests"][:2, -1] = 1; bank["mask"][:3] = True
    with torch.no_grad():
        logits, value = net(*ppo.tensors(bank)); idx = int(logits[0].argmax()); logp = float(logits.log_softmax(-1)[0, idx])
    frame = {**bank, "physical_mask": bank["mask"].copy(), "value": value[0].numpy().copy(),
        "index": idx, "old_logp": logp, "time_ns": 35_000_000_000, "alpha": .9, "heat": .5,
        "learn_actor": True, "input_sha": ppo.input_digest(bank)}
    decision = dict(time_ns=frame["time_ns"], chosen_index=idx, input_sha=frame["input_sha"], logprob=logp,
                    critic=frame["value"].tolist())
    ctl = type("Recorded", (), {})(); ctl.net = net; ctl.frames = [frame]; ctl.decisions = [decision]
    ctl.collect = False; ctl.errors = []; ctl.rng = torch.Generator().manual_seed(7)
    return ctl


class AuditFixtures(unittest.TestCase):
    def test_eval_archive_preserves_argmax_and_rng(self):
        ctl = recorded(); state = ctl.rng.get_state().clone()
        with tempfile.TemporaryDirectory() as folder, patch.object(gate, "OUT", Path(folder)):
            arc = gate.persist_eval(ctl, "PURE", 17)
            frames, rng = gate.archive_frames(arc["path"])
            self.assertIsNone(rng)
            self.assertEqual(gate.replay_frames(ctl.net, frames, True, ctl.decisions)["frames"], 1)
            self.assertTrue(torch.equal(state, ctl.rng.get_state()))
            self.assertFalse(arc["collection"])
            with np.load(arc["path"], allow_pickle=False) as z:
                self.assertNotIn("target", z.files); self.assertNotIn("adv", z.files)

    def test_inference_corruption_rejected(self):
        ctl = recorded(); ctl.frames[0]["old_logp"] += .01
        with self.assertRaisesRegex(ValueError, "log probability"):
            gate.replay_frames(ctl.net, ctl.frames, True)

    def test_nonargmax_legal_choice_rejected(self):
        ctl = recorded(); ctl.frames[0]["index"] = 1
        with self.assertRaisesRegex(ValueError, "argmax"):
            gate.replay_frames(ctl.net, ctl.frames, True)

    def test_input_bytes_corruption_rejected(self):
        ctl = recorded(); ctl.frames[0]["global_state"][0] = 1
        with self.assertRaisesRegex(ValueError, "digest"):
            gate.replay_frames(ctl.net, ctl.frames)

    def test_sampling_capture_rejected(self):
        ctl = recorded(); ctl.collect = True
        with self.assertRaisesRegex(ValueError, "stochastic"):
            gate.persist_eval(ctl, "PURE")

    def test_physical_mask_violation_rejected(self):
        ctl = recorded(); ctl.frames[0]["physical_mask"][:] = False
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "input.npz"
            np.savez_compressed(path, **gate.frame_arrays(ctl.frames))
            with self.assertRaisesRegex(ValueError, "physical mask"):
                gate.archive_frames(path)

    def test_failed_attempt_is_counted_and_preserved(self):
        rows = [dict(identity="good", raw_sha="abc", split="TRAIN")]
        receipts = [dict(event="START", identity="old", number=1, unix=1, training=False),
            dict(event="FAIL", identity="old", unix=2), dict(event="START", identity="good", number=2, unix=3, training=True),
            dict(event="PREPARED", identity="good", unix=4), dict(event="ERROR", identity="good", unix=5),
            dict(event="COMPLETE", identity="good", unix=6, raw_sha="abc")]
        counts, _ = gate.receipts_proof(rows, receipts, 2)
        self.assertEqual(counts["environments_started"], 2); self.assertEqual(counts["failures"], 1)
        self.assertEqual(counts["recovered_commit_errors"], 1)
        with self.assertRaisesRegex(ValueError, "cap"): gate.receipts_proof(rows, receipts, 1)

    def test_orphan_start_rejected(self):
        with self.assertRaisesRegex(ValueError, "unterminated"):
            gate.receipts_proof([], [dict(event="START", identity="pending", number=1, unix=1)], 1)

    def test_absent_role_and_exact_ceil(self):
        m = dict(incomplete=0, energy_180_j=1, mean_ap_c=1, urgent_planned=3, urgent_on_time=2, normal_planned=0, normal_on_time=0)
        self.assertTrue(gate.qualified(m, .6)); self.assertFalse(gate.qualified(m, .7))
        self.assertTrue(gate.qualified(m, 1, normal_only=True))
        m["incomplete"] = 1; self.assertFalse(gate.qualified(m, .6))

    def test_clusters_not_episodes(self):
        pairs = [(0, 12, 1)] * 10 + [(1, 15, 2)] * 10
        interval = gate.independent_interval(pairs, 123)
        self.assertEqual(interval["independent_case_clusters"], 2)
        self.assertTrue(interval["strict_mean_target_lower_bounds"])
        self.assertIsNone(gate.independent_interval([(0, 100, 4)], 123)["energy_CI95"])


if __name__ == "__main__": unittest.main()
