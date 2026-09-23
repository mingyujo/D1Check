import collections
import copy
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch, Mock

from tools import d1_arrival_plan as p
from tools import d1_arrival_device as d


class FixedComparisonTest(unittest.TestCase):
    def test_orders_counts_and_period_balance(self):
        for design, repeats, requests, urgent in (("minimum", 3, 162, 45), ("precise", 6, 324, 90)):
            layout = p.fixed_layout(design)
            self.assertEqual(len(layout), repeats * 3)
            total = sum(3 * len(p.trace(k, "classification")) for k, _, _ in layout)
            u = sum(3 * sum(q[2] == "urgent" for q in p.trace(k, "classification")) for k, _, _ in layout)
            self.assertEqual((total, u), (requests, urgent))
            for kind in ("low", "queue", "burst"):
                orders = [o for k, _, o in layout if k == kind]
                for period in range(3):
                    self.assertEqual(collections.Counter(o[period] for o in orders),
                                     dict.fromkeys(p.FIXED_POLICIES, repeats // 3))
                self.assertEqual(len(set(map(tuple, orders))), repeats)
            self.assertEqual(layout, p.fixed_layout(design))

    def test_generated_identity_hash_budget_and_workload_rejection(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            apk = root / "source.apk"
            apk.write_bytes(b"test-only-not-apk")
            old = dict(entries=[], source_files={}, apk_path=str(apk), apk_sha256=p.digest(apk),
                       device_fingerprint="test-only")
            for kind in ("burst", "low", "queue"):
                m = dict(session_id="old", policy="CPU_FIFO", protocol=p.PROTOCOL,
                         cpu_threads=1, maximum_concurrency=2,
                         models={"x": {"identity": {"session_id": "old"}}},
                         warmup_requests=[dict(request_id=f"old-w{i}") for i in range(8)],
                         requests=[dict(request_id=f"old-{kind}-{i}", offset_ms=t, task_id=task,
                                        priority=priority, sample_id="same")
                                   for i, (t, task, priority) in enumerate(p.trace(kind, "classification"))])
                (root / f"{kind}.json").write_bytes(p.canonical(m))
                old["entries"].append(dict(kind=kind, urgent_task="classification", manifest=f"{kind}.json"))
            source = root / "source.json"
            source.write_bytes(p.canonical(old))
            with patch.object(p, "FIXED_SOURCE_SHA", p.digest(source)), patch.object(p, "validate"):
                out = root / "new"
                result = p.generate_fixed(source, "minimum", out)
                self.assertEqual((result["sessions"], result["warmup_calls"]), (27, 216))
                plan = p.read(out / "comparison_plan.json")
                precise, _ = p.fixed_spec(source, "precise")
                self.assertFalse({e["session_id"] for e in plan["entries"]} &
                                 {e["session_id"] for e in precise["entries"]})
                for key, value in (("seed", 9), ("session_cap", 28), ("device_retry_cap", 1)):
                    bad = copy.deepcopy(plan); bad[key] = value
                    with self.assertRaises(ValueError):
                        p.validate_fixed(bad, out)
                bad = copy.deepcopy(plan); bad["entries"].reverse()
                with self.assertRaises(ValueError):
                    p.validate_fixed(bad, out)
                first = out / plan["entries"][0]["manifest"]
                m = p.read(first); m["requests"][0]["offset_ms"] += 1
                first.write_bytes(p.canonical(m))
                with self.assertRaises(ValueError):
                    p.validate_fixed(plan, out)
                with self.assertRaises(FileExistsError):
                    p.generate_fixed(source, "minimum", out)

    def test_existing_output_and_failure_never_resume(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with self.assertRaisesRegex(RuntimeError, "recover only"):
                d.output_gate(dict(protocol=p.FIXED_PROTOCOL, entries=[]), root)
            old = dict(protocol="arrival-independent-evaluation-v1", entries=[dict(index=0, session_id="x")])
            folder = root / "00_x"; folder.mkdir()
            (folder / "validated.json").write_text("{}")
            (folder / "cleanup_error.txt").write_text("lost connection")
            with self.assertRaises(RuntimeError):
                d.output_gate(old, root)

    def test_quality_and_battery_gates(self):
        summary = dict(status="completed", arrival_lag_exceeded=0)
        rows = [dict(terminal_status="succeeded")]
        environment = [dict(thermal_status=0, low_memory=False, admission_reason="admit")]
        d.quality_gate(summary, rows, environment)
        for bad in ([], [dict(thermal_status=1, low_memory=False)], [dict(error="sample lost")]):
            with self.assertRaises(RuntimeError):
                d.quality_gate(summary, rows, bad)
        with self.assertRaises(RuntimeError):
            d.quality_gate(dict(status="completed", arrival_lag_exceeded=1), rows)
        with self.assertRaises(RuntimeError):
            d.quality_gate(summary, [dict(terminal_status="rejected")], environment)
        plan = dict(battery_start_percent=55, battery_min_percent=30,
                    battery_max_temperature_tenths_c=350, require_unplugged=True)
        battery = "level: 60\nscale: 100\ntemperature: 300\nAC powered: false\nUSB powered: false\nWireless powered: false\n"
        d.battery_gate(plan, battery, True)
        for bad in (battery.replace("60", "54"), battery.replace("300", "351"), battery.replace("USB powered: false", "USB powered: true")):
            with self.assertRaises(RuntimeError):
                d.battery_gate(plan, bad, True)

    def test_recovery_only_and_conflict_preservation(self):
        device = Mock()
        device.call.side_effect = [subprocess.CompletedProcess([], 0, b"summary.json\nx.part\n", b""),
                                   subprocess.CompletedProcess([], 0, b"original", b"")]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            d.recover(device, "id", root)
            self.assertEqual((root / "summary.json").read_bytes(), b"original")
            self.assertFalse(any("start" in c.args or "install" in c.args for c in device.call.call_args_list))
            device.call.side_effect = [subprocess.CompletedProcess([], 0, b"summary.json\n", b""),
                                       subprocess.CompletedProcess([], 0, b"changed", b"")]
            with self.assertRaises(RuntimeError):
                d.recover(device, "id", root)
            self.assertEqual((root / "summary.json").read_bytes(), b"original")

    def test_deadline_prevents_external_call(self):
        device = d.Device("not-real-adb", None)
        device.deadline = 0
        with patch.object(d.subprocess, "run", side_effect=AssertionError("external call")):
            with self.assertRaises(TimeoutError):
                device.call("devices")

    def test_allocation_gate_matches_fixed_rule(self):
        rows = [dict(terminal_status="succeeded", priority="urgent", selected_backend="CPU"),
                dict(terminal_status="succeeded", priority="normal", selected_backend="GPU")]
        d.allocation_gate(dict(policy="FIXED_SPLIT"), rows)
        with self.assertRaises(RuntimeError):
            d.allocation_gate(dict(policy="CPU_URGENT"), rows)
        rows[0]["selected_backend"] = "GPU"
        with self.assertRaises(RuntimeError):
            d.allocation_gate(dict(policy="FIXED_SPLIT"), rows)

    def test_cleanup_absence_requires_successful_process_inventory(self):
        device = Mock()
        device.call.return_value = subprocess.CompletedProcess([], 0, b"USER PID NAME\nshell 1 sh\n", b"")
        d.require_stopped(device)
        for data in (b"", ("USER PID NAME\nu0 123 " + d.PACKAGE + ":model_probe\n").encode()):
            device.call.return_value = subprocess.CompletedProcess([], 0, data, b"")
            with self.assertRaises(RuntimeError):
                d.require_stopped(device)
        device.call.side_effect = RuntimeError("ADB disconnected")
        with self.assertRaises(RuntimeError):
            d.require_stopped(device)

    def test_interruption_stops_after_one_consumed_attempt_and_cleanup_failure_propagates(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            apk = root / "apk"; apk.write_bytes(b"fake")
            plan = dict(protocol=p.FIXED_PROTOCOL, session_cap=2, apk_sha256=p.digest(apk),
                        device_fingerprint="fake", host_wall_seconds=9000, initial_cool_seconds=120,
                        entries=[dict(index=i, session_id=str(i)) for i in range(2)])
            file = root / "plan.json"; file.write_bytes(p.canonical(plan))
            device = Mock(); device.identify.return_value = dict(serial="fake")
            device.deadline = None
            def call(*args, **kwargs):
                if args[:3] == ("shell", "dumpsys", "thermalservice"):
                    return subprocess.CompletedProcess([], 0, b"Thermal Status: 1", b"")
                if args[:3] == ("shell", "am", "force-stop"):
                    raise RuntimeError("mock cleanup connection loss")
                return subprocess.CompletedProcess([], 0, b"", b"")
            device.call.side_effect = call
            with patch.object(p, "validate"), patch.object(d, "Device", return_value=device), \
                 patch.object(d, "bounded_cool"), patch.object(d, "recover", return_value={}):
                with self.assertRaisesRegex(RuntimeError, "cleanup connection loss"):
                    d.run(file, apk, "not-adb", None, root / "out", 2, p.digest(file))
                self.assertEqual(len(list((root / "out").glob("*/attempt.json"))), 1)
                self.assertTrue((root / "out/00_0/error.json").exists())
                self.assertTrue((root / "out/00_0/cleanup_error.txt").exists())
                self.assertFalse((root / "out/00_0/validated.json").exists())
                self.assertFalse(any("start" in c.args for c in device.call.call_args_list))
                with self.assertRaisesRegex(RuntimeError, "recover only"):
                    d.run(file, apk, "not-adb", None, root / "out", 2, p.digest(file))


if __name__ == "__main__":
    unittest.main()
