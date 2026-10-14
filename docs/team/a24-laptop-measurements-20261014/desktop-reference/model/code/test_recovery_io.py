"""Small disk-only fault tests; no simulator, learner, or external workloads."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock
import recovery_io as io


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.out = Path(self.temp.name)
        self.identity = "TRAIN_S26_ATC_WAIT_37001_EP1"
        self.start = dict(event="START", identity=self.identity, request_sha="requests", training=True)
        io.append_jsonl(self.out / "receipts.jsonl", self.start)
        self.row = dict(identity=self.identity, raw_path=str(self.out / "raw" / "S26" /
            (self.identity + ".json.gz")), environment_seed=7, metrics={"energy_180_j": 20},
            physical_PASS=True, wall_s=1)
        self.raw = dict(request_sha="requests", environment_seed=7, metrics=self.row["metrics"],
            physical_audit={k: True for k in ("legal_events", "AVAILABLE", "response_separate",
                                             "no_future_input", "max2", "energy_heat_balance")})

    def tearDown(self):
        self.temp.cleanup()

    def test_commit_and_reconcile_are_idempotent(self):
        row = io.commit_environment(self.out, self.row, self.raw)
        state = io.reconcile(self.out)
        self.assertEqual(state["rows"], [row])
        self.assertEqual(state["recovered_rows"], [])
        self.assertEqual([r["event"] for r in state["receipts"]], ["START", "PREPARED", "COMPLETE"])
        self.assertEqual(io.reconcile(self.out)["recovered_receipts"], [])

    def test_prepared_raw_before_rename_is_recovered(self):
        original = io.os.replace
        def interrupted(source, target):
            if str(source).endswith(".json.gz.prepared"):
                raise RuntimeError("power loss before raw rename")
            return original(source, target)
        with mock.patch.object(io.os, "replace", side_effect=interrupted):
            with self.assertRaises(RuntimeError):
                io.commit_environment(self.out, self.row, self.raw)
        state = io.reconcile(self.out)
        self.assertEqual(state["recovered_rows"], [self.identity])
        self.assertEqual(state["recovered_receipts"], [self.identity])
        self.assertEqual(len(state["rows"]), 1)

    def test_row_before_complete_is_recovered_without_duplicate(self):
        original = io.append_jsonl
        def interrupted(path, value):
            if value.get("event") == "COMPLETE":
                raise RuntimeError("power loss before COMPLETE")
            return original(path, value)
        with mock.patch.object(io, "append_jsonl", side_effect=interrupted):
            with self.assertRaises(RuntimeError):
                io.commit_environment(self.out, self.row, self.raw)
        state = io.reconcile(self.out)
        self.assertEqual(state["recovered_rows"], [])
        self.assertEqual(state["recovered_receipts"], [self.identity])
        self.assertEqual(len(state["rows"]), 1)

    def test_prepared_manifest_without_prepared_receipt_is_recovered(self):
        original = io.append_jsonl
        def interrupted(path, value):
            if value.get("event") == "PREPARED":
                raise RuntimeError("power loss before PREPARED")
            return original(path, value)
        with mock.patch.object(io, "append_jsonl", side_effect=interrupted):
            with self.assertRaises(RuntimeError):
                io.commit_environment(self.out, self.row, self.raw)
        state = io.reconcile(self.out)
        self.assertEqual(state["recovered_rows"], [self.identity])

    def test_tampered_raw_is_rejected(self):
        row = io.commit_environment(self.out, self.row, self.raw)
        Path(row["raw_path"]).write_bytes(b"changed")
        with self.assertRaises(io.RecoveryError):
            io.reconcile(self.out)

    def test_failed_or_unclosed_start_never_reexecutes(self):
        receipts = io.read_jsonl(self.out / "receipts.jsonl")
        with self.assertRaises(io.RecoveryError):
            io.assert_fresh(self.identity, [], receipts)
        io.append_jsonl(self.out / "receipts.jsonl", dict(event="FAIL", identity=self.identity))
        state = io.reconcile(self.out)
        self.assertEqual(state["consumed_uncommitted"], [self.identity])
        with self.assertRaises(io.RecoveryError):
            io.assert_fresh(self.identity, {}, {self.identity: state["receipts"]})
        io.assert_fresh(self.identity + "_G2", {}, {self.identity: state["receipts"]})

    def test_training_artifact_is_required_on_recovery(self):
        arc = self.out / "rollouts" / "experience.npz"
        arc.parent.mkdir()
        arc.write_bytes(b"exact causal input and action RNG bytes")
        io.commit_environment(self.out, self.row, self.raw,
                              artifacts=[dict(path=str(arc), sha=io.file_sha(arc))])
        arc.write_bytes(b"changed")
        with self.assertRaises(io.RecoveryError):
            io.reconcile(self.out)

    def test_torn_tail_preserved_but_complete_corruption_rejected(self):
        path = self.out / "learning.jsonl"
        io.append_jsonl(path, {"episode": 1})
        with path.open("ab") as f:
            f.write(b'{"episode":2')
        self.assertEqual(io.read_jsonl(path, True), [{"episode": 1}])
        evidence = list((self.out / "recovery_evidence").glob("*.bin"))
        self.assertEqual(evidence[0].read_bytes(), b'{"episode":2')
        with path.open("ab") as f:
            f.write(b"invalid\n")
        with self.assertRaises(io.RecoveryError):
            io.read_jsonl(path, True)

    def test_episode_and_optimizer_logs_replay_once_and_detect_drift(self):
        path = self.out / "learning.jsonl"
        row = dict(episode=1, network_sha="net", archive={"sha": "arc"})
        log = io.IdempotentLog(path)
        self.assertTrue(log.append(row))
        replay = dict(row, archive={"sha": "arc", "recovered": True})
        self.assertFalse(io.IdempotentLog(path).append(replay))
        with self.assertRaises(io.RecoveryError):
            io.append_idempotent(path, dict(row, network_sha="wrong"))
        optim = io.IdempotentLog(self.out / "optimizer.jsonl", key_fields=("update",))
        self.assertTrue(optim.append(dict(update=1, adam_steps=5)))
        self.assertFalse(optim.append(dict(update=1, adam_steps=5)))
        self.assertEqual(len(io.read_jsonl(path)), 1)

    def test_indexed_commit_does_not_read_journals(self):
        receipts = [self.start]
        index = {self.identity: [self.start]}
        with mock.patch.object(io, "read_jsonl", side_effect=AssertionError("unbounded journal read")):
            row = io.commit_environment(self.out, self.row, self.raw, rows={}, receipts=receipts,
                                        receipt_index=index)
        self.assertEqual([r["event"] for r in receipts], ["START", "PREPARED", "COMPLETE"])
        self.assertEqual(receipts, index[self.identity])
        self.assertEqual(row["identity"], self.identity)

    def test_raw_path_cannot_escape_run(self):
        with self.assertRaises(io.RecoveryError):
            io.commit_environment(self.out, dict(self.row, raw_path=str(self.out / "outside.json.gz")), self.raw)


if __name__ == "__main__":
    unittest.main()
