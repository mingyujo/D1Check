"""Synthetic PC fixtures only; never creates data in experiment roots or calls ADB."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import d1_arrival_timing_calibration as c
from tools import d1_arrival_timing_calibration_device as device
from tools import d1_arrival_timing_dev as v
from tools import test_d1_arrival_timing_dev as old_test


def artifacts(backend="GPU", priority="normal", task="detection"):
    old = old_test.fixture()
    trace = copy.deepcopy(old["decision_trace.json"])
    trace.update(protocol=v.CAL_PROTOCOL, policy=v.CAL_POLICY, calibration_backend=backend,
                 budgets=c.pending()["budgets"], records=[])
    lanes = {b: {"phase": "AVAILABLE", "request_id": None, "task": None, "phase_since_ns": 0, "persist_since_ns": None} for b in ("CPU", "GPU")}
    rows, requests, files = [], [], {}
    timestamp_fields = ("scheduled_arrival_ns", "actual_arrival_ns", "queue_entry_ns", "dispatch_ns", "execution_start_ns",
                        "inference_start_ns", "inference_end_ns", "output_ready_ns", "persist_complete_ns", "worker_release_ns", "lane_available_ns")
    for ordinal in range(4):
        rid, delta = f"q{ordinal}", 1000 + ordinal * 5_000_000_000
        row = copy.deepcopy(old["requests.json"][0])
        row.update(protocol=v.CAL_PROTOCOL, request_id=rid, task_id=task, priority=priority, ordinal=ordinal,
                   selected_backend=backend, decision_reason="calibration_fixed_backend", arrival_lag_ns=1)
        for field in timestamp_fields:
            row[field] += delta
        row["completion_ns"] = row["output_ready_ns" if priority == "urgent" else "persist_complete_ns"]
        row["response_ns"] = row["completion_ns"] - row["scheduled_arrival_ns"]
        row["deadline_ns"] = row["scheduled_arrival_ns"] + 5_000_000_000
        rows.append(row)
        files[f"{rid}.event.json"] = {k: value for k, value in row.items() if k != "lane_available_ns"}
        requests.append({k: row[k] for k in ("request_id", "task_id", "priority", "ordinal", "sample_id")} |
                        {"offset_ms": ordinal * 5000, "deadline_ms": 5000})
        for old_record in old["decision_trace.json"]["records"]:
            record = copy.deepcopy(old_record)
            record.update(seq=len(trace["records"]), mono_ns=record["mono_ns"] + delta)
            if record["kind"] == "phase":
                record.update(backend=backend, request_id=rid)
                phase = record["phase"]
                previous = lanes[backend]
                lanes[backend] = dict(phase=phase, request_id=None if phase == "AVAILABLE" else rid,
                    task=None if phase == "AVAILABLE" else task, phase_since_ns=record["mono_ns"],
                    persist_since_ns=record["mono_ns"] if phase == "PERSISTED" else None if phase in ("ASSIGNED", "AVAILABLE") else previous["persist_since_ns"])
            else:
                record["decision_end_ns"] += delta
                record["queue"] = [dict(id=rid, task=task, priority=priority, ordinal=ordinal)] if record["queue"] else []
                record["lanes"] = copy.deepcopy(lanes)
                for b, lane in record["lanes"].items():
                    lane["remaining_ns"], lane["remaining_state"] = v.remaining(lane, record["mono_ns"], trace["budgets"], b)
                record.update(v.replay(record["queue"], lanes, record["mono_ns"], trace["budgets"], backend))
            trace["records"].append(record)
    manifest = copy.deepcopy(old["manifest.json"])
    manifest.update(protocol=v.CAL_PROTOCOL, policy=v.CAL_POLICY, requests=requests, calibration_backend=backend,
                    maximum_concurrency=1, execution_purpose="boundary_calibration_only", storage_mode="persist_all",
                    observation_contract=c.OBSERVATION)
    manifest["timing_estimates"]["budgets"] = trace["budgets"]
    manifest["warmup_requests"] = [dict(request_id=f"w{i}", model_key=key) for i, key in enumerate([k for k in c.p.SOURCE_KEYS for _ in range(2)])]
    warm = []
    for i, q in enumerate(manifest["warmup_requests"]):
        warm.extend([q | dict(kind="start", mono_ns=2*i), q | dict(kind="end", mono_ns=2*i+1, status="succeeded")])
    files.update({"decision_trace.json": trace, "manifest.json": manifest, "requests.json": rows,
                  "summary.json": dict(protocol=v.CAL_PROTOCOL, session_id="s", request_count=4, terminal_count=4,
                                       status="completed", workload_start_ns=1001), "warmup_trace.json": warm,
                  "cleanup.json": {"status": "completed"}})
    return files


class CalibrationTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        reference = self.root / "reference"
        reference.mkdir()
        raw = reference / "synthetic.input"
        raw.write_bytes(b"PC test, not a real model")
        template = dict(images=[dict(sample_id="image")], models={k: {"identity": {}, "target": {}} for k in v.KEYS})
        c.write_new(reference / "template.json", template)
        old = dict(entries=[dict(manifest="template.json", manifest_sha256=c.p.digest(reference / "template.json"))],
                   source_files={"synthetic.input": dict(path=str(raw), bytes=raw.stat().st_size, sha256=c.p.digest(raw))},
                   device_fingerprint="synthetic", apk_sha256="old")
        self.source = reference / "source.json"
        c.write_new(self.source, old)
        self.patch = patch.object(c, "SOURCE_SHA", c.p.digest(self.source))
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def prepare(self, bound=False):
        output = self.root / ("bound" if bound else "proposal")
        if bound:
            apk = self.root / "synthetic.apk"
            apk.write_bytes(b"unit-test-only; not an APK")
            receipt = self.root / "build.json"
            c.write_new(receipt, dict(status="built_not_device_verified", source_code=c.code_identity(), apk_sha256=c.p.digest(apk)))
            c.prepare(self.source, output, apk, receipt)
        else:
            c.prepare(self.source, output)
        return output / "calibration_plan.json"

    def test_plan_and_dry_run_never_touch_device_or_create_measurements(self):
        with patch.object(device.legacy, "Device", side_effect=AssertionError("ADB forbidden")), patch.object(device.subprocess, "run", side_effect=AssertionError("process forbidden")):
            path = self.prepare()
            result = c.check(path)
        self.assertEqual((result["sessions"], result["diagnostic_requests"], result["warmup_calls"]), (16, 64, 128))
        self.assertEqual(result["generated_measurements"], 0)
        self.assertFalse(result["experiment_ready"])
        self.assertEqual(len(list(path.parent.glob("manifests/*.json"))), 16)
        self.assertFalse(list(path.parent.rglob("*requests.json")))
        self.assertEqual(c.layout()[8:], [("confirmation", *x[1:]) for x in reversed(c.layout()[:8])])

    def test_proposal_and_general_policy_experiment_cannot_execute(self):
        path = self.prepare()
        with patch.object(device.legacy, "Device", side_effect=AssertionError("ADB forbidden")), self.assertRaisesRegex(ValueError, "unbound APK"):
            device.run(path, "development", self.root / "run", "unused", "unused", 16, c.p.digest(path))
        plan = c.p.read(path)
        plan["protocol"] = "arrival-timing-dev-v1"
        path.write_bytes(c.p.canonical(plan))
        with self.assertRaisesRegex(ValueError, "calibration-only"):
            c.check(path)

    def test_null_manifest_and_role_reversal_are_explicit(self):
        path = self.prepare()
        cells = set()
        for entry in c.p.read(path)["entries"]:
            manifest = c.p.read(path.parent / entry["manifest"])
            cells.add((entry["task"], entry["backend"], entry["priority"]))
            self.assertEqual(len(v.check_estimates(manifest["timing_estimates"])["missing_budgets"]), 20)
            self.assertEqual(manifest["maximum_concurrency"], 1)
            self.assertEqual({q["task_id"] for q in manifest["requests"]}, {entry["task"]})
        self.assertEqual(cells, set(c.CONDITIONS))

    def test_normal_and_urgent_boundaries_and_actual_release(self):
        for priority in ("urgent", "normal"):
            files = artifacts(priority=priority)
            with patch.object(v, "read", side_effect=lambda p: files[p.name]), patch.object(c.p, "read", side_effect=lambda p: files[p.name]):
                samples = c.observations(Path("synthetic"))
            self.assertEqual(samples[0]["values"], dict(zip(v.ALL_FIELDS, [2, 68, 120, 10, 20])))
            self.assertEqual(c.usage(priority, "output_ready_to_persist_ns", "response"), "not_applicable" if priority == "urgent" else "applicable")
            self.assertEqual(c.usage(priority, "output_ready_to_persist_ns", "lane_from_dispatch"), "applicable")

    def test_missing_is_not_na_and_failed_overflow_or_lost_records_rejected(self):
        self.assertEqual(len(v.check_estimates(c.pending())["missing_budgets"]), 20)
        for mutate in (lambda f: f["decision_trace.json"].update(overflow=True),
                       lambda f: f["requests.json"][0].update(terminal_status="failed"),
                       lambda f: f["warmup_trace.json"].pop(),
                       lambda f: f["summary.json"].update(status="incomplete"),
                       lambda f: f["requests.json"][0].pop("lane_available_ns")):
            files = artifacts()
            mutate(files)
            with patch.object(v, "read", side_effect=lambda p: files[p.name]), patch.object(c.p, "read", side_effect=lambda p: files[p.name]), self.assertRaises(ValueError):
                c.observations(Path("synthetic"))

    def test_manifest_budget_and_estimate_tampering_rejected(self):
        path = self.prepare()
        plan = c.p.read(path)
        manifest = path.parent / plan["entries"][0]["manifest"]
        data = c.p.read(manifest)
        data["timing_estimates"]["budgets"]["classification_CPU"][v.DECISION_FIELD] = 0
        manifest.write_bytes(c.p.canonical(data))
        with self.assertRaisesRegex(ValueError, "manifest changed"):
            c.check(path)

    def test_consumed_plan_cannot_restart_with_new_output(self):
        path = self.prepare(True)
        plan = c.p.read(path)
        c.claim(plan, "development", self.root / "run")
        with self.assertRaises(FileExistsError):
            c.claim(plan, "development", self.root / "replacement")
        self.assertFalse((self.root / "replacement").exists())
        with self.assertRaisesRegex(ValueError, "development/freeze"):
            c.claim(plan, "confirmation", self.root / "check")

    def test_technical_connection_failure_is_consumed_and_never_retried(self):
        path = self.prepare(True)
        with patch.object(device.legacy, "Device") as factory:
            factory.return_value.identify.side_effect = RuntimeError("synthetic connection failure")
            with self.assertRaisesRegex(RuntimeError, "connection"):
                device.run(path, "development", self.root / "run", "unused", "unused", 16, c.p.digest(path))
            with self.assertRaisesRegex(ValueError, "previous failure|consumed/stopped phase"):
                device.run(path, "development", self.root / "retry", "unused", "unused", 16, c.p.digest(path))
            self.assertEqual(factory.call_count, 1)
            factory.return_value.call.assert_not_called()
        stopped = c.p.read(self.root / "run" / "stopped.json")
        self.assertEqual((stopped["attempts"], stopped["completed"]), (0, 0))

    def test_existing_output_and_insufficient_approval_do_not_access_device(self):
        path = self.prepare(True)
        existing = self.root / "existing"
        existing.mkdir()
        with patch.object(device.legacy, "Device", side_effect=AssertionError("ADB forbidden")):
            with self.assertRaises(ValueError):
                device.run(path, "development", existing, "unused", "unused", 16, c.p.digest(path))
            with self.assertRaises(ValueError):
                device.run(path, "development", self.root / "new", "unused", "unused", 27, c.p.digest(path))

    def test_fit_uses_development_only_and_confirmation_does_not_refit(self):
        plan_file = self.prepare(True)
        plan = c.p.read(plan_file)
        cells = {}
        for task, backend, priority in c.CONDITIONS:
            cells[f"{task}_{backend}_{priority}"] = [dict(priority=priority, values=dict.fromkeys(v.ALL_FIELDS, n)) for n in (2, 4, 6, 8)]
        source = self.root / "reference" / "synthetic.input"
        inputs = {str(source): c.p.digest(source)}
        freeze = self.root / "fit.json"
        with patch.object(c, "phase_inputs", return_value=(plan, cells, inputs)) as reader:
            c.fit(plan_file, self.root / "development", freeze)
            self.assertEqual(reader.call_args.args[1], "development")
        fixed = freeze.read_bytes()
        estimate = c.p.read(freeze)["estimates"]["detection_GPU_urgent"]["output_ready_to_persist_ns"]
        self.assertEqual((estimate["median_ns"], estimate["response_use"], estimate["lane_use"]), (5, "not_applicable", "applicable"))
        registry = Path(plan["registry"])
        registry.mkdir(parents=True)
        c.write_new(registry / "confirmation_consumed.json", {"freeze_sha256": c.p.digest(freeze)})
        confirmation = copy.deepcopy(cells)
        for samples in confirmation.values():
            for sample in samples:
                sample["values"] = dict.fromkeys(v.ALL_FIELDS, 9)
        report = self.root / "confirmation.json"
        with patch.object(c, "phase_inputs", return_value=(plan, confirmation, inputs)) as reader:
            c.confirm(plan_file, self.root / "confirmation", freeze, report)
            self.assertEqual(reader.call_args.args[1], "confirmation")
        self.assertEqual(freeze.read_bytes(), fixed)
        result = c.p.read(report)
        self.assertEqual(result["errors"]["detection_GPU_urgent"][v.DECISION_FIELD]["signed_error_ns"], [4, 4, 4, 4])
        self.assertFalse(result["experiment_ready"])
        self.assertIsNone(result["performance_pass"])

    def test_packaging_cannot_overwrite_existing_build(self):
        output = self.root / "existing-build"
        output.mkdir()
        with patch.object(device.subprocess, "run", side_effect=AssertionError("build must not run")), self.assertRaises(ValueError):
            device.package(output)

    def test_gpu_raw_sentinel_requires_separate_delegate_proof_not_rewriting(self):
        row = dict(selected_backend="GPU", actual_backend="unverified_requires_host_delegate_log")
        device.backend_gate(row, "GPU")
        self.assertEqual(row["actual_backend"], "unverified_requires_host_delegate_log")
        with self.assertRaises(ValueError):
            device.backend_gate(dict(selected_backend="GPU", actual_backend="CPU"), "GPU")
        with self.assertRaises(ValueError):
            device.backend_gate(dict(selected_backend="GPU", actual_backend="GPU"), "GPU")

    def test_apk_and_host_version_bindings_are_separate(self):
        current = c.code_identity()
        historical = current | {"tools/d1_arrival_timing_calibration_device.py": "old-host-only"}
        self.assertEqual(c.apk_sources(current), c.apk_sources(historical))
        path = "benchmark-runner/src/modelProbe/java/com/example/d1check/benchmarkrunner/ArrivalSchedulerActivity.kt"
        changed = historical | {path: "different-APK-source"}
        self.assertNotEqual(c.apk_sources(current), c.apk_sources(changed))


if __name__ == "__main__":
    unittest.main()
