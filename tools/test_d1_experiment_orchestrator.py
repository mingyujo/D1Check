import contextlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest


MODULE_PATH = Path(__file__).with_name("d1_experiment_orchestrator.py")
SPEC = importlib.util.spec_from_file_location("d1_experiment_orchestrator", MODULE_PATH)
assert SPEC and SPEC.loader
ORCH = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = ORCH
SPEC.loader.exec_module(ORCH)


BATTERY = """Current Battery Service state:
  AC powered: false
  USB powered: false
  Wireless powered: false
  status: 3
  level: {level}
  scale: 100
  temperature: 303
"""
THERMAL = "Thermal Status: 1\nCurrent temperatures from HAL:\n"


def hal_thermal(ap=30.0, bat=29.0, pa=31.0, skin=28.0):
    return f"""Thermal Status: 0
Current temperatures from HAL:
 Temperature{{mValue={ap}, mType=0, mName=AP, mStatus=0}}
 Temperature{{mValue={bat}, mType=2, mName=BAT, mStatus=0}}
 Temperature{{mValue={pa}, mType=0, mName=PATHM, mStatus=0}}
 Temperature{{mValue={skin}, mType=3, mName=SKIN, mStatus=0}}
Current cooling devices from HAL:
"""


class FakeAdb:
    def __init__(self, activity_returncode=0, direct_returncode=0):
        self.calls = []
        self.activity_returncode = activity_returncode
        self.direct_returncode = direct_returncode

    def run(self, arguments, timeout=30, check=True):
        self.calls.append(list(arguments))
        code = (
            self.direct_returncode
            if arguments == ORCH.direct_stop_arguments()
            else self.activity_returncode
        )
        return subprocess.CompletedProcess(arguments, code, "", "failure" if code else "")


class ScriptedAdb:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def run(self, arguments, timeout=30, check=True):
        self.calls.append(list(arguments))
        if not self.responses:
            raise AssertionError(f"unexpected ADB call: {arguments}")
        return self.responses.pop(0)


class FakeClock:
    def __init__(self):
        self.value = 0.0

    def monotonic(self):
        return self.value

    def timeout(self, seconds):
        self.value += seconds
        raise ORCH.WaitTimeout("no Logcat terminal event")


class ManualClock:
    def __init__(self):
        self.value = 0.0

    def monotonic(self):
        return self.value

    def sleep(self, seconds):
        self.value += seconds

    def wait_timeout(self, seconds):
        self.value += seconds
        raise ORCH.WaitTimeout("interval elapsed")


class ExitedProcess:
    def poll(self):
        return 0

    def wait(self, timeout=None):
        return 0


class ExitedLogger:
    def __init__(self):
        self.process = ExitedProcess()
        self.lines = []

    def terminate(self):
        raise AssertionError("already-exited logger must not be terminated")


def gpu_event(event, sequence, status="ok", run_id="run-a", session="session-a", **extra):
    value = {
        "schema_version": 2,
        "source": "gpu",
        "event": event,
        "status": status,
        "run_id": run_id,
        "runner_session_id": session,
        "sequence": sequence,
    }
    value.update(extra)
    return value


def completed_footer(sequence=623):
    return gpu_event(
        "file_summary",
        sequence,
        sequence_first=0,
        sequence_last=sequence,
        file_event_count=sequence + 1,
        inference_span_count=595,
    )


def remote_adb_for(events, filename="gpu-events-run-a-session-a.jsonl"):
    listing = subprocess.CompletedProcess([], 0, filename + "\n", "")
    tail = subprocess.CompletedProcess(
        [], 0, "".join(json.dumps(event) + "\n" for event in events), ""
    )
    return ScriptedAdb([listing, tail])


class OrchestratorTest(unittest.TestCase):
    @staticmethod
    def conditioning_args(policy="stable", **overrides):
        values = {
            "logger": MODULE_PATH,
            "start_policy": policy,
            "stability_window_seconds": 2.0,
            "stability_sample_interval_seconds": 1.0,
            "stability_timeout_seconds": 3.0,
            "stability_max_range_c": 0.5,
            "stability_max_slope_c_per_minute": 0.2,
            "matched_tolerance_c": 0.5,
        }
        values.update(overrides)
        return SimpleNamespace(**values)

    def make_conditioner(self, directory, responses, policy="stable", manifest=None, **args):
        manifest = manifest if manifest is not None else {"runs": []}
        orchestrator = ORCH.ExperimentOrchestrator(
            self.conditioning_args(policy, **args),
            manifest,
            Path(directory) / ORCH.MANIFEST_NAME,
        )
        orchestrator.adb = ScriptedAdb([
            subprocess.CompletedProcess([], 0, response, "") for response in responses
        ])
        return orchestrator

    def test_selects_only_connected_device(self):
        devices = ORCH.parse_adb_devices(
            "List of devices attached\n192.0.2.1:5555 device product:a model:A24\n"
        )
        self.assertEqual("192.0.2.1:5555", ORCH.select_device(devices, None))

    def test_multiple_devices_require_explicit_serial(self):
        devices = {"first": "device", "second": "device"}
        with self.assertRaises(ORCH.OrchestratorError):
            ORCH.select_device(devices, None)
        self.assertEqual("second", ORCH.select_device(devices, "second"))

    def test_battery_100_passes_pilot_but_not_formal_energy(self):
        snapshot = ORCH.parse_safety_snapshot(BATTERY.format(level=100), THERMAL)
        pilot = ORCH.evaluate_safety(snapshot, "pilot")
        formal = ORCH.evaluate_safety(snapshot, "formal")
        self.assertTrue(pilot.mode_safety_pass)
        self.assertFalse(pilot.formal_energy_eligible)
        self.assertFalse(formal.mode_safety_pass)
        self.assertIn("formal_battery_level", formal.reasons)

    def test_battery_29_fails_pilot(self):
        snapshot = ORCH.parse_safety_snapshot(BATTERY.format(level=29), THERMAL)
        result = ORCH.evaluate_safety(snapshot, "pilot")
        self.assertFalse(result.mode_safety_pass)
        self.assertIn("pilot_battery_level", result.reasons)

    def test_hal_temperature_parser_uses_only_current_hal_section(self):
        text = (
            "Cached temperatures:\n"
            " Temperature{mValue=99, mType=0, mName=AP, mStatus=0}\n"
            + hal_thermal(30, 29, 31, 28)
        )
        self.assertEqual(
            {"AP": 30.0, "BAT": 29.0, "PA": 31.0, "SKIN": 28.0},
            ORCH.parse_hal_temperature_vector(text),
        )

    def test_hal_temperature_parser_rejects_missing_duplicate_and_malformed(self):
        missing = hal_thermal().replace(
            " Temperature{mValue=28.0, mType=3, mName=SKIN, mStatus=0}\n", ""
        )
        duplicate = hal_thermal() .replace(
            "Current cooling devices from HAL:",
            " Temperature{mValue=32, mType=0, mName=PA, mStatus=0}\n"
            "Current cooling devices from HAL:",
        )
        malformed = hal_thermal().replace("mValue=30.0", "mValue=oops")
        for text, detail in (
            (missing, "incomplete"),
            (duplicate, "duplicate"),
            (malformed, "malformed"),
        ):
            with self.subTest(detail=detail):
                with self.assertRaisesRegex(ValueError, detail):
                    ORCH.parse_hal_temperature_vector(text)

    def test_stability_range_and_slope_boundaries_are_inclusive(self):
        samples = []
        for second, ap in ((0.0, 30.0), (60.0, 30.2), (120.0, 30.4)):
            samples.append({
                "host_monotonic_s": second,
                "temperatures_c": {"AP": ap, "BAT": 29, "PA": 31, "SKIN": 28},
            })
        result = ORCH.evaluate_thermal_stability(samples, 120.0, 0.4, 0.2)
        self.assertTrue(result["stable"])
        self.assertAlmostEqual(0.4, result["sensor_evidence"]["AP"]["range_c"])
        self.assertAlmostEqual(
            0.2, result["sensor_evidence"]["AP"]["slope_c_per_minute"]
        )
        self.assertFalse(
            ORCH.evaluate_thermal_stability(samples, 120.0, 0.399, 0.2)["stable"]
        )
        self.assertFalse(
            ORCH.evaluate_thermal_stability(samples, 120.0, 0.4, 0.199)["stable"]
        )

    def test_stability_window_tolerates_real_sampling_jitter(self):
        samples = [
            {
                "host_monotonic_s": second,
                "temperatures_c": {"AP": 30, "BAT": 29, "PA": 31, "SKIN": 28},
            }
            for second in (0.0, 5.1, 10.2, 15.3, 20.4, 25.5, 30.6)
        ]
        result = ORCH.evaluate_thermal_stability(samples, 30.0, 0.0, 0.0)
        self.assertTrue(result["stable"])
        self.assertGreaterEqual(result["window_coverage_seconds"], 30.0)

    def test_stable_conditioning_succeeds_and_records_raw_samples(self):
        clock = ManualClock()
        with tempfile.TemporaryDirectory() as directory:
            orchestrator = self.make_conditioner(
                directory, [hal_thermal()] * 3, stability_timeout_seconds=4.0
            )
            slot = {"slot_id": "001", "steps": []}
            result = orchestrator.thermal_conditioning(
                slot, monotonic=clock.monotonic, sleep=clock.sleep
            )
            self.assertEqual("passed", result["status"])
            self.assertEqual(3, len(result["raw_samples"]))
            self.assertEqual("host_monotonic_s", result["clock_domain"])
            self.assertFalse(result["android_mono_ns_available"])

    def test_stable_conditioning_timeout_does_not_start_run(self):
        clock = ManualClock()
        values = [hal_thermal(ap=value) for value in (30.0, 31.0, 32.0, 33.0)]
        with tempfile.TemporaryDirectory() as directory:
            orchestrator = self.make_conditioner(directory, values)
            slot = {"slot_id": "001", "steps": []}
            with self.assertRaises(ORCH.WaitTimeout):
                orchestrator.thermal_conditioning(
                    slot, monotonic=clock.monotonic, sleep=clock.sleep
                )
            self.assertEqual("timeout", slot["thermal_conditioning"]["status"])

    def test_matched_reference_is_created_once_and_preserved_on_resume(self):
        clock = ManualClock()
        manifest = {"runs": []}
        with tempfile.TemporaryDirectory() as directory:
            first = self.make_conditioner(
                directory, [hal_thermal()] * 3, "matched", manifest,
                stability_timeout_seconds=4.0,
            )
            first_slot = {"slot_id": "001", "steps": []}
            first_result = first.thermal_conditioning(
                first_slot, monotonic=clock.monotonic, sleep=clock.sleep
            )
            reference = dict(manifest["thermal_conditioning_reference"])
            self.assertTrue(first_result["reference_created"])

            clock = ManualClock()
            second = self.make_conditioner(
                directory, [hal_thermal(ap=30.2)] * 3, "matched", manifest,
                stability_timeout_seconds=4.0,
            )
            second_slot = {"slot_id": "002", "steps": []}
            second_result = second.thermal_conditioning(
                second_slot, monotonic=clock.monotonic, sleep=clock.sleep
            )
            self.assertFalse(second_result["reference_created"])
            self.assertEqual(reference, manifest["thermal_conditioning_reference"])
            self.assertAlmostEqual(
                0.2, second_result["reference_evaluation"]["delta_c"]["AP"]
            )

    def test_matched_reference_outside_tolerance_times_out(self):
        clock = ManualClock()
        manifest = {
            "runs": [],
            "thermal_conditioning_reference": {
                "created_utc": "old",
                "source_slot_id": "001",
                "temperatures_c": {"AP": 30, "BAT": 29, "PA": 31, "SKIN": 28},
            },
        }
        with tempfile.TemporaryDirectory() as directory:
            orchestrator = self.make_conditioner(
                directory, [hal_thermal(ap=31)] * 4, "matched", manifest
            )
            slot = {"slot_id": "002", "steps": []}
            with self.assertRaises(ORCH.WaitTimeout):
                orchestrator.thermal_conditioning(
                    slot, monotonic=clock.monotonic, sleep=clock.sleep
                )
            self.assertFalse(slot["thermal_conditioning"]["reference_evaluation"]["matched"])
            self.assertEqual("old", manifest["thermal_conditioning_reference"]["created_utc"])

    def test_cooling_zero_and_positive_interval(self):
        clock = ManualClock()
        zero = ORCH.wait_for_idle_interval(
            0, clock.wait_timeout, monotonic=clock.monotonic
        )
        self.assertEqual(0, zero["actual_duration_s"])
        positive = ORCH.wait_for_idle_interval(
            3, clock.wait_timeout, monotonic=clock.monotonic
        )
        self.assertEqual(3, positive["actual_duration_s"])

    def test_cooling_and_load_emergency_abort(self):
        for stage in ("load", "cooling"):
            with self.subTest(stage=stage):
                monitor = ORCH.RuntimeSafetyMonitor(42.0, 1)
                monitor.stage = stage
                with self.assertRaises(ORCH.EmergencyAbort) as caught:
                    monitor.observe_event({
                        "source": "d1check",
                        "event": "sample",
                        "mono_ns": 123,
                        "thermal_status": 2,
                        "battery_temp_C": 30.0,
                        "plugged": False,
                    })
                self.assertEqual(stage, caught.exception.stage)
                self.assertIn(
                    "android_thermal_status_emergency", caught.exception.reasons
                )

    def test_plugged_hot_or_severe_thermal_is_rejected(self):
        snapshot = ORCH.SafetySnapshot(60, 3, 35.1, False, True, False, 2)
        result = ORCH.evaluate_safety(snapshot, "pilot")
        self.assertEqual(
            ("device_plugged", "battery_temperature", "android_thermal_status"),
            result.reasons,
        )

    def test_seeded_plan_is_deterministic_and_balanced(self):
        first = ORCH.build_plan(["CPU", "GPU"], 3, 20260908)
        second = ORCH.build_plan(["CPU", "GPU"], 3, 20260908)
        self.assertEqual(first, second)
        self.assertEqual(3, sum(item["resource"] == "CPU" for item in first))
        self.assertEqual(3, sum(item["resource"] == "GPU" for item in first))

    def test_cpu_intent_has_threads_but_gpu_intent_does_not(self):
        cpu = ORCH.runner_intent_arguments("CPU", 4, 60, 20, "run", "command")
        gpu = ORCH.runner_intent_arguments("GPU", 4, 60, 20, "run", "command")
        self.assertIn("d1_cpu_threads", cpu)
        self.assertNotIn("d1_cpu_threads", gpu)
        self.assertIn("DURATION", cpu)

    def test_runner_terminal_classification_is_run_scoped(self):
        failure = {"source": "gpu", "event": "run_error", "run_id": "run-a"}
        footer = {"source": "gpu", "event": "file_summary", "run_id": "run-a"}
        self.assertEqual("failure", ORCH.classify_runner_terminal(failure, "run-a"))
        footer["status"] = "ok"
        self.assertEqual("success", ORCH.classify_runner_terminal(footer, "run-a"))
        self.assertIsNone(ORCH.classify_runner_terminal(footer, "run-b"))

    def test_logcat_summary_remains_fast_success_path(self):
        probes = []

        def probe(final):
            probes.append(final)
            raise AssertionError("remote probe must not run for Logcat success")

        result = ORCH.wait_for_runner_terminal(
            "run-a",
            lambda _timeout: {
                "source": "gpu", "event": "file_summary", "status": "ok", "run_id": "run-a"
            },
            probe,
            10,
            20,
        )
        self.assertEqual("success", result.kind)
        self.assertEqual("logcat", result.source)
        self.assertFalse(result.fallback_used)
        self.assertEqual([], probes)

    def test_missing_logcat_summary_uses_completed_remote_jsonl(self):
        clock = FakeClock()
        remote = ORCH.probe_remote_runner(
            remote_adb_for([gpu_event("inference", 622), completed_footer()]), "run-a"
        )
        result = ORCH.wait_for_runner_terminal(
            "run-a",
            clock.timeout,
            lambda final: remote,
            10,
            30,
            monotonic=clock.monotonic,
        )
        self.assertEqual("success", result.kind)
        self.assertEqual("remote_runner_jsonl", result.source)
        self.assertTrue(result.fallback_used)
        self.assertTrue(result.logcat_terminal_missing)
        self.assertEqual(
            ORCH.REMOTE_RUNNER_DIRECTORY + "/gpu-events-run-a-session-a.jsonl",
            result.remote_runner_path,
        )

    def test_remote_file_ending_in_inference_is_not_success(self):
        probe = ORCH.probe_remote_runner(
            remote_adb_for([gpu_event("inference", 622)]), "run-a"
        )
        self.assertEqual("incomplete", probe.state)
        clock = FakeClock()
        with self.assertRaises(ORCH.WaitTimeout):
            ORCH.wait_for_runner_terminal(
                "run-a",
                clock.timeout,
                lambda final: probe,
                10,
                20,
                sparse_poll_interval_s=20,
                monotonic=clock.monotonic,
            )

    def test_remote_run_error_is_immediate_failure(self):
        probe = ORCH.probe_remote_runner(
            remote_adb_for([gpu_event("run_error", 12, status="error")]), "run-a"
        )
        self.assertEqual("failure", probe.state)
        clock = FakeClock()
        result = ORCH.wait_for_runner_terminal(
            "run-a", clock.timeout, lambda final: probe, 10, 30,
            monotonic=clock.monotonic,
        )
        self.assertEqual("failure", result.kind)
        self.assertEqual("remote_runner_jsonl", result.source)

    def test_remote_tail_validates_schema_source_run_and_sequence(self):
        invalid_events = [
            [gpu_event("inference", 1) | {"schema_version": 1}],
            [gpu_event("inference", 1) | {"source": "cpu"}],
            [gpu_event("inference", 1) | {"run_id": "run-b"}],
            [gpu_event("inference", 1), completed_footer(3)],
        ]
        for events in invalid_events:
            with self.subTest(events=events):
                with self.assertRaises(ORCH.RemoteRunnerValidationError):
                    ORCH.probe_remote_runner(remote_adb_for(events), "run-a")

    def test_multiple_remote_files_are_ambiguous(self):
        listing = subprocess.CompletedProcess(
            [], 0,
            "gpu-events-run-a-session-a.jsonl\ngpu-events-run-a-session-b.jsonl\n",
            "",
        )
        with self.assertRaises(ORCH.RemoteRunnerAmbiguityError):
            ORCH.probe_remote_runner(ScriptedAdb([listing]), "run-a")

    def test_remote_ls_and_tail_adb_failures_are_distinct_from_not_found(self):
        missing = subprocess.CompletedProcess([], 1, "", "No such file or directory")
        self.assertEqual(
            "not_found",
            ORCH.probe_remote_runner(ScriptedAdb([missing]), "run-a").state,
        )
        adb_failure = subprocess.CompletedProcess([], 1, "", "error: device offline")
        with self.assertRaises(ORCH.RemoteRunnerAdbError):
            ORCH.probe_remote_runner(ScriptedAdb([adb_failure]), "run-a")
        listing = subprocess.CompletedProcess(
            [], 0, "gpu-events-run-a-session-a.jsonl\n", ""
        )
        tail_failure = subprocess.CompletedProcess([], 1, "", "error: device offline")
        with self.assertRaises(ORCH.RemoteRunnerAdbError):
            ORCH.probe_remote_runner(ScriptedAdb([listing, tail_failure]), "run-a")

    def test_hard_timeout_performs_final_remote_probe(self):
        clock = FakeClock()
        calls = []

        def probe(final):
            calls.append(final)
            return (
                ORCH.RemoteRunnerProbe("success", "/remote/file", completed_footer())
                if final else ORCH.RemoteRunnerProbe("incomplete", "/remote/file")
            )

        result = ORCH.wait_for_runner_terminal(
            "run-a", clock.timeout, probe, 10, 20,
            sparse_poll_interval_s=20,
            monotonic=clock.monotonic,
        )
        self.assertEqual([False, True], calls)
        self.assertTrue(result.final_remote_probe_used)
        self.assertEqual("success", result.kind)

    def test_stop_timeout_uses_direct_service_recovery(self):
        adb = FakeAdb()
        calls = 0

        def wait_for_stop(_timeout):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise ORCH.WaitTimeout("missing run_stop")
            return {"event": "run_stop", "run_id": "run-a", "status": "ok"}

        result = ORCH.stop_d1_run(adb, wait_for_stop, 1)
        self.assertTrue(result["recovery_used"])
        self.assertEqual(ORCH.stop_run_arguments(), adb.calls[0])
        self.assertEqual(ORCH.direct_stop_arguments(), adb.calls[1])

    def test_failure_cleanup_records_every_step_without_overwriting_error(self):
        with tempfile.TemporaryDirectory() as directory:
            args = SimpleNamespace(logger=MODULE_PATH)
            manifest = {"runs": []}
            orchestrator = ORCH.ExperimentOrchestrator(
                args, manifest, Path(directory) / ORCH.MANIFEST_NAME
            )
            orchestrator.adb = FakeAdb()
            orchestrator._wait_run_stop = lambda monitor, logger, run_id, timeout: {
                "source": "d1check",
                "event": "run_stop",
                "run_id": run_id,
                "status": "ok",
            }
            slot = {
                "steps": [],
                "error": "WaitTimeout: original runner failure",
                "remote_runner_path": "/remote/runner.jsonl",
            }
            errors = orchestrator._failure_cleanup(
                slot, "run-a", False, object(), ExitedLogger()
            )
            names = {step["name"] for step in slot["steps"]}
            self.assertEqual(
                {
                    "failure_cleanup_activity_stop",
                    "failure_cleanup_direct_service_stop",
                    "failure_cleanup_run_stop_confirmation",
                    "failure_cleanup_logger",
                    "failure_cleanup_runner_force_stop",
                    "failure_cleanup_artifacts",
                },
                names,
            )
            self.assertEqual("WaitTimeout: original runner failure", slot["error"])
            self.assertFalse(slot["stop_recovery_used"])
            self.assertEqual([], errors)

    def test_emergency_abort_force_stops_runner_before_cleanup_and_is_recorded(self):
        with tempfile.TemporaryDirectory() as directory:
            orchestrator = ORCH.ExperimentOrchestrator(
                SimpleNamespace(logger=MODULE_PATH),
                {"runs": []},
                Path(directory) / ORCH.MANIFEST_NAME,
            )
            orchestrator.adb = FakeAdb()
            orchestrator._wait_run_stop = lambda monitor, logger, run_id, timeout: {
                "source": "d1check", "event": "run_stop", "run_id": run_id, "status": "ok"
            }
            slot = {
                "steps": [],
                "error": "EmergencyAbort: original safety failure",
                "runtime_safety": {"observations": []},
            }
            error = ORCH.EmergencyAbort(
                "logcat_telemetry", "load", ["device_plugged"], {"plugged": 1}
            )
            orchestrator._record_emergency_abort(slot, error)
            orchestrator._failure_cleanup(
                slot, "run-a", False, object(), ExitedLogger()
            )
            names = [step["name"] for step in slot["steps"]]
            self.assertEqual("emergency_runner_force_stop", names[0])
            self.assertIn("failure_cleanup_activity_stop", names)
            self.assertIn("failure_cleanup_logger", names)
            self.assertEqual("load", slot["runtime_safety"]["abort"]["stage"])
            self.assertEqual(
                "EmergencyAbort: original safety failure", slot["error"]
            )

    def test_atomic_manifest_preserves_completed_checkpoint(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ORCH.MANIFEST_NAME
            value = {"runs": [{"slot_id": "001", "status": "completed"}]}
            ORCH.atomic_write_json(path, value)
            loaded = ORCH.load_json(path)
            self.assertEqual("completed", loaded["runs"][0]["status"])
            loaded["runs"].append({"slot_id": "002", "status": "failed"})
            self.assertEqual(
                ["002"],
                [slot["slot_id"] for slot in ORCH.runnable_slots(loaded)],
            )
            self.assertEqual([], list(path.parent.glob("*.tmp")))

    def test_default_options_are_resume_compatible_with_pre_conditioning_manifest(self):
        args = ORCH.build_parser().parse_args([])
        current = ORCH.experiment_config(args)
        legacy = dict(current)
        legacy.pop("thermal_conditioning")
        legacy.pop("post_load_idle_seconds")
        legacy.pop("emergency_monitor")
        self.assertEqual(current, ORCH._legacy_compatible_config(legacy))

    def test_dry_run_performs_no_adb_and_writes_no_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = ORCH.main([
                    "--dry-run", "--resources", "CPU", "GPU",
                    "--duration", "60", "--repeat", "2",
                    "--output-dir", directory,
                ])
            payload = json.loads(output.getvalue())
            self.assertEqual(0, code)
            self.assertFalse(payload["performs_adb_calls"])
            self.assertEqual(4, len(payload["plan"]))
            self.assertEqual(
                "safety", payload["config"]["thermal_conditioning"]["start_policy"]
            )
            self.assertEqual(0.0, payload["config"]["post_load_idle_seconds"])
            self.assertFalse(payload["config"]["emergency_monitor"]["enabled"])
            self.assertFalse(payload["cooling"]["runner_force_stop_before_interval"])
            self.assertFalse((Path(directory) / ORCH.MANIFEST_NAME).exists())


if __name__ == "__main__":
    unittest.main()
