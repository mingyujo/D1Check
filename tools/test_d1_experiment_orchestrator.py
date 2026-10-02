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
from unittest import mock


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
            "List of devices attached\n<IP:PORT> device product:a model:A24\n"
        )
        self.assertEqual("<IP:PORT>", ORCH.select_device(devices, None))

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

    def test_stable_cooling_completes_after_window_and_minimum(self):
        clock = ManualClock()
        record = {}
        result = ORCH.wait_for_thermal_cooling(
            record, "stable", 2.0, 5.0, 1.0, 2.0, 0.1, 0.1, 0.5,
            None, lambda: {"AP": 30, "BAT": 29, "PA": 31, "SKIN": 28},
            clock.wait_timeout, monotonic=clock.monotonic,
        )
        self.assertEqual("completed", result["status"])
        self.assertEqual("stable_condition_met", result["completion_reason"])
        self.assertEqual(2.0, result["actual_duration_s"])
        self.assertEqual(3, len(result["raw_temperature_samples"]))

    def test_stable_cooling_timeout_is_explicit(self):
        clock = ManualClock()
        values = iter((30.0, 31.0, 32.0, 33.0))
        record = {}
        with self.assertRaises(ORCH.CoolingTimeout):
            ORCH.wait_for_thermal_cooling(
                record, "stable", 0.0, 3.0, 1.0, 2.0, 0.1, 0.1, 0.5,
                None,
                lambda: {
                    "AP": next(values), "BAT": 29, "PA": 31, "SKIN": 28
                },
                clock.wait_timeout, monotonic=clock.monotonic,
            )
        self.assertEqual("timeout", record["status"])
        self.assertEqual("cooling_timeout", record["completion_reason"])
        self.assertEqual(
            "thermal_conditioning_timeout", record["failure_classification"]
        )

    def test_matched_cooling_success_tolerance_failure_and_missing_reference(self):
        reference = {"AP": 30.0, "BAT": 29.0, "PA": 31.0, "SKIN": 28.0}
        clock = ManualClock()
        success = {}
        ORCH.wait_for_thermal_cooling(
            success, "matched", 0.0, 3.0, 1.0, 2.0, 0.1, 0.1, 0.5,
            reference,
            lambda: {"AP": 30.5, "BAT": 29, "PA": 31, "SKIN": 28},
            clock.wait_timeout, monotonic=clock.monotonic,
        )
        self.assertEqual("matched_condition_met", success["completion_reason"])
        self.assertTrue(success["reference_evaluation"]["matched"])

        clock = ManualClock()
        failed = {}
        with self.assertRaises(ORCH.CoolingTimeout):
            ORCH.wait_for_thermal_cooling(
                failed, "matched", 0.0, 3.0, 1.0, 2.0, 0.1, 0.1, 0.5,
                reference,
                lambda: {"AP": 30.6, "BAT": 29, "PA": 31, "SKIN": 28},
                clock.wait_timeout, monotonic=clock.monotonic,
            )
        self.assertFalse(failed["reference_evaluation"]["matched"])
        self.assertEqual("timeout", failed["status"])
        self.assertEqual("cooling_timeout", failed["completion_reason"])
        self.assertEqual(
            "thermal_conditioning_timeout", failed["failure_classification"]
        )

        missing = {}
        with self.assertRaisesRegex(
            ORCH.OrchestratorError, "thermal_conditioning_reference"
        ):
            ORCH.wait_for_thermal_cooling(
                missing, "matched", 0.0, 3.0, 1.0, 2.0, 0.1, 0.1, 0.5,
                None, lambda: reference, clock.wait_timeout, monotonic=clock.monotonic,
            )
        self.assertEqual(
            "missing_thermal_conditioning_reference", missing["completion_reason"]
        )

    def test_conditioned_cooling_propagates_emergency_abort(self):
        clock = ManualClock()
        record = {}
        monitor = ORCH.RuntimeSafetyMonitor(42.0, 1, monotonic=clock.monotonic)
        monitor.stage = "cooling"

        def emergency_wait(seconds):
            clock.value += min(seconds, 0.5)
            monitor.observe_event({
                "source": "d1check", "event": "sample", "mono_ns": 123,
                "thermal_status": 2, "battery_temp_C": 30.0, "plugged": 0,
            })

        with self.assertRaises(ORCH.EmergencyAbort):
            ORCH.wait_for_thermal_cooling(
                record, "stable", 0.0, 5.0, 1.0, 2.0, 0.1, 0.1, 0.5,
                None, lambda: {"AP": 30, "BAT": 29, "PA": 31, "SKIN": 28},
                emergency_wait, monotonic=clock.monotonic,
            )
        self.assertEqual("collecting", record["status"])

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

    def test_matrix_has_sixteen_conditions_in_each_of_five_blocks(self):
        plan = ORCH.build_plan(
            ["CPU", "GPU"], 5, 20260909, [1, 2, 4], [25, 50, 75, 100]
        )

        self.assertEqual(80, len(plan))
        for block_index in range(1, 6):
            block = [slot for slot in plan if slot["block_index"] == block_index]
            self.assertEqual(16, len(block))
            self.assertEqual(16, len({slot["condition_id"] for slot in block}))

    def test_matched_plan_warning_depends_on_condition_count_not_repetitions(self):
        two_condition = ORCH.new_manifest(ORCH.build_parser().parse_args([
            "--start-policy", "matched", "--resources", "CPU", "GPU",
            "--repeat", "5",
        ]))
        self.assertEqual(2, two_condition["plan_summary"]["condition_count"])
        self.assertEqual([], two_condition["methodology_warnings"])

        three_condition = ORCH.new_manifest(ORCH.build_parser().parse_args([
            "--start-policy", "matched", "--resources", "CPU", "GPU",
            "--cpu-thread-levels", "1", "2", "--repeat", "1",
        ]))
        warnings = three_condition["methodology_warnings"]
        self.assertEqual(1, len(warnings))
        self.assertEqual(ORCH.MATCHED_MATRIX_WARNING_CODE, warnings[0]["code"])
        self.assertFalse(warnings[0]["blocking"])

    def test_stable_matrix_has_no_matched_reference_warning(self):
        manifest = ORCH.new_manifest(ORCH.build_parser().parse_args([
            "--start-policy", "stable", "--resources", "CPU", "GPU",
            "--cpu-thread-levels", "1", "2", "4",
            "--duty-cycles", "25", "50", "75", "100",
        ]))
        self.assertEqual(16, manifest["plan_summary"]["condition_count"])
        self.assertEqual([], manifest["methodology_warnings"])

    def test_matched_matrix_warning_does_not_fail_manifest_or_dry_run(self):
        arguments = [
            "--dry-run", "--start-policy", "matched",
            "--resources", "CPU", "GPU", "--cpu-thread-levels", "1", "2",
            "--duty-cycles", "100", "--repeat", "2",
        ]
        args = ORCH.build_parser().parse_args(arguments)
        manifest = ORCH.new_manifest(args)
        self.assertEqual(6, len(manifest["runs"]))
        self.assertEqual(1, len(manifest["methodology_warnings"]))

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(0, ORCH.main(arguments))
        payload = json.loads(output.getvalue())
        self.assertEqual(1, len(payload["methodology_warnings"]))
        self.assertFalse(payload["methodology_warnings"][0]["blocking"])

    def test_matrix_is_reproducible_by_seed_and_only_order_changes(self):
        arguments = (["CPU", "GPU"], 3, 20260909, [1, 2, 4], [25, 50])
        first = ORCH.build_plan(*arguments)
        second = ORCH.build_plan(*arguments)
        different = ORCH.build_plan(
            ["CPU", "GPU"], 3, 7, [1, 2, 4], [25, 50]
        )

        self.assertEqual(first, second)
        self.assertNotEqual(
            [slot["condition_id"] for slot in first],
            [slot["condition_id"] for slot in different],
        )
        self.assertEqual(
            sorted((slot["block_index"], slot["condition_id"]) for slot in first),
            sorted((slot["block_index"], slot["condition_id"]) for slot in different),
        )

    def test_cpu_cartesian_product_gpu_null_threads_and_stable_ids(self):
        plan = ORCH.build_plan(
            ["CPU", "GPU"], 1, None, [1, 2], [25, 100]
        )
        cpu = [slot for slot in plan if slot["resource"] == "CPU"]
        gpu = [slot for slot in plan if slot["resource"] == "GPU"]

        self.assertEqual(
            {(1, 25), (1, 100), (2, 25), (2, 100)},
            {(slot["cpu_threads"], slot["duty_cycle_percent"]) for slot in cpu},
        )
        self.assertTrue(all(slot["cpu_threads"] is None for slot in gpu))
        self.assertEqual("cpu-t01-d025-r001", plan[0]["slot_id"])
        self.assertEqual("cpu-t01-d025", plan[0]["condition_id"])
        self.assertEqual("gpu-d100-r001", gpu[-1]["slot_id"])

    def test_slot_values_are_forwarded_exactly_to_runner_intent(self):
        def extra(arguments, name):
            return arguments[arguments.index(name) + 1]

        cpu = ORCH.runner_intent_arguments(
            "CPU", 2, 37, 11, "run-id", "command-id", 75, 4.5
        )
        gpu = ORCH.runner_intent_arguments(
            "GPU", None, 37, 11, "run-id", "command-id", 25, 4.5
        )
        self.assertEqual("CPU", extra(cpu, "d1_resource"))
        self.assertEqual("2", extra(cpu, "d1_cpu_threads"))
        self.assertEqual("75", extra(cpu, "d1_duty_cycle_percent"))
        self.assertEqual("4.5", extra(cpu, "d1_duty_cycle_period_s"))
        self.assertEqual("37", extra(cpu, "d1_duration_s"))
        self.assertEqual("11", extra(cpu, "d1_warmup_count"))
        self.assertEqual("run-id", extra(cpu, "d1_run_id"))
        self.assertEqual("command-id", extra(cpu, "d1_command_id"))
        self.assertEqual("GPU", extra(gpu, "d1_resource"))
        self.assertNotIn("d1_cpu_threads", gpu)
        self.assertEqual("25", extra(gpu, "d1_duty_cycle_percent"))

    def test_single_value_cli_compatibility_and_multi_value_conflicts(self):
        single = ORCH.build_parser().parse_args([
            "--resources", "CPU", "GPU",
            "--cpu-threads", "4",
            "--duty-cycle-percent", "75",
        ])
        ORCH.validate_cli(single)
        config = ORCH.experiment_config(single)
        self.assertEqual([4], config["cpu_thread_levels"])
        self.assertEqual([75], config["duty_cycles"])

        for options in (
            ["--cpu-threads", "4", "--cpu-thread-levels", "1", "2"],
            ["--duty-cycle-percent", "50", "--duty-cycles", "25", "50"],
        ):
            with self.subTest(options=options):
                with self.assertRaises(ORCH.OrchestratorError):
                    ORCH.validate_cli(ORCH.build_parser().parse_args(options))

    def test_matrix_rejects_invalid_and_duplicate_axis_values(self):
        for options in (
            ["--cpu-thread-levels", "0", "2"],
            ["--cpu-thread-levels", "1", "17"],
            ["--duty-cycles", "0", "50"],
            ["--duty-cycles", "50", "101"],
            ["--cpu-thread-levels", "2", "2"],
            ["--duty-cycles", "25", "25"],
        ):
            with self.subTest(options=options):
                with self.assertRaises(ORCH.OrchestratorError):
                    ORCH.validate_cli(ORCH.build_parser().parse_args(options))

    def test_planned_metadata_mismatch_is_detected_for_each_axis(self):
        valid = {
            "resource": "CPU",
            "cpu_threads": 2,
            "requested_duty_cycle_percent": 50,
            "duty_cycle_period_ns": 10_000_000_000,
        }
        self.assertTrue(all(ORCH.planned_metadata_checks(valid, "CPU", 2, 50, 10).values()))
        for key, value in (
            ("resource", "GPU"),
            ("cpu_threads", 4),
            ("requested_duty_cycle_percent", 75),
            ("duty_cycle_period_ns", 5_000_000_000),
        ):
            metadata = dict(valid)
            metadata[key] = value
            self.assertFalse(
                all(ORCH.planned_metadata_checks(metadata, "CPU", 2, 50, 10).values())
            )
        gpu = dict(valid, resource="GPU", cpu_threads=2)
        self.assertFalse(
            ORCH.planned_metadata_checks(gpu, "GPU", None, 50, 10)[
                "planned_cpu_threads"
            ]
        )
        profile = ORCH.gpu_profile("gpu-compat-default-v1")
        gpu = dict(valid, resource="GPU", cpu_threads=None, gpu_delegate_profile=profile)
        self.assertTrue(
            ORCH.planned_metadata_checks(gpu, "GPU", None, 50, 10, profile)[
                "planned_gpu_delegate_profile"
            ]
        )
        self.assertFalse(
            ORCH.planned_metadata_checks(
                gpu, "GPU", None, 50, 10, ORCH.gpu_profile("gpu-fp32-strict-v1")
            )["planned_gpu_delegate_profile"]
        )

    def test_cpu_intent_has_threads_but_gpu_intent_does_not(self):
        cpu = ORCH.runner_intent_arguments("CPU", 4, 60, 20, "run", "command")
        gpu = ORCH.runner_intent_arguments("GPU", 4, 60, 20, "run", "command")
        self.assertIn("d1_cpu_threads", cpu)
        self.assertNotIn("d1_cpu_threads", gpu)
        self.assertIn("DURATION", cpu)
        self.assertIn("d1_duty_cycle_percent", cpu)
        self.assertIn("d1_duty_cycle_period_s", gpu)

    def test_duty_cycle_cli_bounds_are_rejected(self):
        for options in (
            ["--duty-cycle-percent", "0"],
            ["--duty-cycle-percent", "101"],
            ["--duty-cycle-period-seconds", "0"],
        ):
            with self.subTest(options=options):
                args = ORCH.build_parser().parse_args(options)
                with self.assertRaises(ORCH.OrchestratorError):
                    ORCH.validate_cli(args)

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

    def test_legacy_resume_adds_axes_without_reordering_or_replacing_reference(self):
        args = ORCH.build_parser().parse_args([
            "--resources", "CPU", "GPU", "--repeat", "1", "--seed", "9"
        ])
        config = ORCH.experiment_config(args)
        reference = {
            "created_utc": "old",
            "source_slot_id": "001-cpu-r001",
            "temperatures_c": {"AP": 30, "BAT": 29, "PA": 31, "SKIN": 28},
        }
        manifest = {
            "thermal_conditioning_reference": reference,
            "runs": [
                {
                    "slot_id": "001-cpu-r001", "resource": "CPU",
                    "repetition": 1, "order_index": 1, "status": "completed",
                    "attempts": 1,
                },
                {
                    "slot_id": "002-gpu-r001", "resource": "GPU",
                    "repetition": 1, "order_index": 2, "status": "failed",
                    "attempts": 1,
                },
            ],
        }
        original_slot_ids = [slot["slot_id"] for slot in manifest["runs"]]

        self.assertTrue(ORCH.upgrade_and_validate_manifest_plan(manifest, config))
        self.assertEqual(original_slot_ids, [slot["slot_id"] for slot in manifest["runs"]])
        self.assertIs(reference, manifest["thermal_conditioning_reference"])
        self.assertEqual(
            ["002-gpu-r001"],
            [slot["slot_id"] for slot in ORCH.runnable_slots(manifest)],
        )

    def test_new_resume_plan_and_shared_reference_are_not_mutated(self):
        args = ORCH.build_parser().parse_args([
            "--resources", "CPU", "GPU", "--cpu-thread-levels", "1", "2",
            "--duty-cycles", "25", "50", "--repeat", "2", "--seed", "17",
            "--start-policy", "matched",
        ])
        manifest = ORCH.new_manifest(args)
        manifest["thermal_conditioning_reference"] = {
            "created_utc": "fixed",
            "source_slot_id": manifest["runs"][0]["slot_id"],
            "temperatures_c": {"AP": 30, "BAT": 29, "PA": 31, "SKIN": 28},
        }
        manifest.pop("methodology_warnings")
        before = json.loads(json.dumps(manifest))

        self.assertFalse(
            ORCH.upgrade_and_validate_manifest_plan(manifest, manifest["config"])
        )
        self.assertTrue(
            ORCH.sync_matrix_methodology_warnings(
                manifest,
                args.start_policy,
                manifest["plan_summary"]["condition_count"],
            )
        )
        self.assertEqual(before["runs"], manifest["runs"])
        self.assertEqual(
            before["thermal_conditioning_reference"],
            manifest["thermal_conditioning_reference"],
        )

    def test_missing_or_corrupt_shared_reference_is_not_silently_rebuilt(self):
        corrupt = {
            "thermal_conditioning_reference": {
                "temperatures_c": {"AP": 30, "BAT": 29}
            }
        }
        with self.assertRaisesRegex(ORCH.OrchestratorError, "exactly AP/BAT/PA/SKIN"):
            ORCH.validated_reference_vector(corrupt)

        clock = ManualClock()
        manifest = {
            "runs": [
                {"slot_id": "earlier", "attempts": 1},
                {"slot_id": "current", "attempts": 1},
            ]
        }
        with tempfile.TemporaryDirectory() as directory:
            orchestrator = self.make_conditioner(
                directory, [hal_thermal()] * 3, "matched", manifest,
                stability_timeout_seconds=4.0,
            )
            with self.assertRaisesRegex(ORCH.OrchestratorError, "refusing to recreate"):
                orchestrator.thermal_conditioning(
                    {"slot_id": "current", "steps": []},
                    monotonic=clock.monotonic,
                    sleep=clock.sleep,
                )

    def test_default_options_are_resume_compatible_with_pre_conditioning_manifest(self):
        args = ORCH.build_parser().parse_args([])
        current = ORCH.experiment_config(args)
        legacy = dict(current)
        legacy.pop("thermal_conditioning")
        legacy.pop("post_load_idle_seconds")
        legacy.pop("emergency_monitor")
        legacy.pop("duty_cycle_percent")
        legacy.pop("duty_cycle_period_seconds")
        legacy.pop("accuracy_preflight")
        legacy.pop("energy_measurement")
        legacy.pop("cooling_policy")
        legacy.pop("cpu_thread_levels")
        legacy.pop("duty_cycles")
        legacy.pop("repeat")
        legacy.pop("block_design")
        self.assertEqual(current, ORCH._legacy_compatible_config(legacy))
        changed = ORCH.build_parser().parse_args(["--duty-cycle-percent", "25"])
        self.assertNotEqual(
            ORCH.experiment_config(changed), ORCH._legacy_compatible_config(legacy)
        )

    def test_manifest_provenance_defaults_are_explicitly_unverified(self):
        manifest = ORCH.new_manifest(ORCH.build_parser().parse_args([]))
        accuracy = manifest["provenance"]["accuracy_preflight"]
        energy = manifest["provenance"]["energy_measurement"]

        self.assertEqual("not_run", accuracy["status"])
        self.assertEqual(32, accuracy["deterministic_input_count"])
        self.assertEqual("optional", accuracy["policy"])
        self.assertEqual("raw_unverified", energy["status"])
        self.assertFalse(energy["calculation_performed"])
        self.assertFalse(energy["current_unit_verified"])

    def test_accuracy_finalization_requires_numeric_and_full_delegate(self):
        args = ORCH.build_parser().parse_args([])
        expected = ORCH.accuracy_expected_provenance(args, "fingerprint")
        command_id = "11111111-1111-4111-8111-111111111111"
        metadata = {
            "schema_version": 1,
            "event": "accuracy_preflight_metadata",
            "command_id": command_id,
            "equivalence_scope": expected["equivalence_scope"],
            "comparator_version": "combined-tolerance-v1",
            "model_id": expected["model_id"],
            "model_sha256": expected["model_sha256"],
            "litert_version": expected["litert_version"],
            "delegate_configuration": "TfLiteGpuDelegateV2_CompatibilityList_bestOptions",
            "input_set_version": expected["input_set_version"],
            "seed": expected["seed"],
            "input_count": expected["input_count"],
            "input_shape": expected["input_shape"],
            "input_dtype": expected["input_dtype"],
            "normalization": expected["normalization"],
            "reference_cpu_threads": expected["reference_cpu_threads"],
            "tolerance": expected["tolerance"],
            "reference_resource": "CPU", "candidate_resource": "GPU",
            "output_tensor_count": 1, "output_shape": [1, 1001],
            "output_dtype": "FLOAT32", "input_set_sha256": "a" * 64,
            "reference_model_sha256": expected["model_sha256"],
            "candidate_model_sha256": expected["model_sha256"],
        }
        input_hashes, input_set_hash = ORCH.deterministic_accuracy_input_hashes(
            expected["seed"], 32, 1 * 224 * 224 * 3
        )
        metadata["input_set_sha256"] = input_set_hash
        inputs = [
            {"event": "accuracy_preflight_input", "input_index": index,
             "input_sha256": input_hashes[index],
             "reference_output_sha256": f"r{index}",
             "candidate_output_sha256": f"c{index}"}
            for index in range(32)
        ]
        summary = {
            "event": "accuracy_preflight_summary",
            "numeric_equivalence_passed": True,
            "mismatch_count": 0, "non_finite_count": 0,
            "argmax_match_count": 32, "argmax_mismatch_count": 0,
            "aggregate": {"max_absolute_error": 1e-5},
        }
        runner = {"metadata": metadata, "inputs": inputs, "summary": summary}
        verified = {
            "verification": "verified", "full_delegate": True,
            "replaced_nodes": 31, "total_nodes": 31,
        }
        result = ORCH.finalize_accuracy_preflight(
            runner, verified, expected, command_id, {
                "sha256": "b" * 64,
                "host_recomputed": {
                    "mismatch_count": 0, "non_finite_count": 0,
                    "argmax_match_count": 32, "argmax_mismatch_count": 0,
                    "reference_output_sha256": [f"r{i}" for i in range(32)],
                    "candidate_output_sha256": [f"c{i}" for i in range(32)],
                },
            }
        )
        self.assertEqual("passed", result["status"], result["failure_reasons"])
        unverified = dict(verified, verification="unverified", full_delegate=False)
        result = ORCH.finalize_accuracy_preflight(
            runner, unverified, expected, command_id, {
                "sha256": "b" * 64,
                "host_recomputed": {
                    "mismatch_count": 0, "non_finite_count": 0,
                    "argmax_match_count": 32, "argmax_mismatch_count": 0,
                    "reference_output_sha256": [f"r{i}" for i in range(32)],
                    "candidate_output_sha256": [f"c{i}" for i in range(32)],
                },
            }
        )
        self.assertEqual("failed", result["status"])
        self.assertIn("gpu_full_delegation_unverified", result["failure_reasons"])

    def test_accuracy_31_inputs_cannot_pass_formal_minimum(self):
        args = ORCH.build_parser().parse_args(["--accuracy-input-count", "31"])
        expected = ORCH.accuracy_expected_provenance(args, "fingerprint")
        command_id = "22222222-2222-4222-8222-222222222222"
        metadata = {
            "schema_version": 1, "event": "accuracy_preflight_metadata",
            "command_id": command_id, "reference_resource": "CPU",
            "candidate_resource": "GPU", "output_tensor_count": 1,
            "output_shape": [1, 1001], "output_dtype": "FLOAT32",
            "reference_model_sha256": expected["model_sha256"],
            "candidate_model_sha256": expected["model_sha256"],
            **{key: expected[key] for key in (
                "equivalence_scope", "comparator_version", "model_id", "model_sha256",
                "litert_version", "delegate_configuration", "input_set_version", "seed",
                "input_count", "input_shape", "input_dtype", "normalization",
                "reference_cpu_threads", "tolerance",
            )},
        }
        input_hashes, input_set_hash = ORCH.deterministic_accuracy_input_hashes(
            expected["seed"], 31, 1 * 224 * 224 * 3
        )
        metadata["input_set_sha256"] = input_set_hash
        runner = {
            "metadata": metadata,
            "inputs": [
                {"input_sha256": value, "reference_output_sha256": f"r{index}",
                 "candidate_output_sha256": f"c{index}"}
                for index, value in enumerate(input_hashes)
            ],
            "summary": {"numeric_equivalence_passed": True, "mismatch_count": 0,
                        "non_finite_count": 0, "argmax_match_count": 31,
                        "argmax_mismatch_count": 0},
        }
        result = ORCH.finalize_accuracy_preflight(
            runner, {"verification": "verified", "full_delegate": True}, expected,
            command_id, {"host_recomputed": {
                "mismatch_count": 0, "non_finite_count": 0,
                "argmax_match_count": 31, "argmax_mismatch_count": 0,
                "reference_output_sha256": [f"r{i}" for i in range(31)],
                "candidate_output_sha256": [f"c{i}" for i in range(31)],
            }},
        )
        self.assertEqual("failed", result["status"])
        self.assertIn("insufficient_input_count", result["failure_reasons"])

    def test_accuracy_policy_formal_blocks_not_run_and_pilot_optional_does_not(self):
        self.assertFalse(ORCH.accuracy_policy_allows_slots("required", "not_run"))
        self.assertFalse(ORCH.accuracy_policy_allows_slots("required", "failed"))
        self.assertTrue(ORCH.accuracy_policy_allows_slots("required", "passed"))
        self.assertTrue(ORCH.accuracy_policy_allows_slots("optional", "failed"))
        formal = ORCH.build_parser().parse_args(["--mode", "formal"])
        pilot = ORCH.build_parser().parse_args(["--mode", "pilot"])
        self.assertEqual("required", ORCH.effective_accuracy_policy(formal))
        self.assertEqual("optional", ORCH.effective_accuracy_policy(pilot))

    def test_accuracy_resume_reuses_only_exact_success_provenance(self):
        args = ORCH.build_parser().parse_args([])
        expected = ORCH.accuracy_expected_provenance(args, "fp")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifact = root / "accuracy_preflight" / "result.json"
            artifact.parent.mkdir()
            artifact.write_text("{}", encoding="utf-8")
            result = {
                "status": "passed", "provenance": expected,
                "artifact_path": "accuracy_preflight/result.json",
                "artifact_sha256": ORCH.sha256_file(artifact),
            }
            self.assertTrue(ORCH.can_reuse_accuracy_preflight(result, expected, root))
            changed = json.loads(json.dumps(expected))
            changed["tolerance"]["atol"] = 0.5
            self.assertFalse(ORCH.can_reuse_accuracy_preflight(result, changed, root))
            legacy_version = json.loads(json.dumps(expected))
            legacy_version["comparator_version"] = "output-equivalence-v2"
            self.assertFalse(
                ORCH.can_reuse_accuracy_preflight(result, legacy_version, root)
            )
            artifact.write_text("changed", encoding="utf-8")
            self.assertFalse(ORCH.can_reuse_accuracy_preflight(result, expected, root))

    def test_accuracy_cli_validation_and_dry_run_are_explicit(self):
        with self.assertRaisesRegex(ORCH.OrchestratorError, "at least 32"):
            args = ORCH.build_parser().parse_args([
                "--mode", "formal", "--accuracy-input-count", "31"
            ])
            ORCH.validate_cli(args)
        with self.assertRaisesRegex(ORCH.OrchestratorError, "require"):
            args = ORCH.build_parser().parse_args([
                "--mode", "formal", "--accuracy-preflight", "off"
            ])
            ORCH.validate_cli(args)
        args = ORCH.build_parser().parse_args(["--dry-run"])
        payload = ORCH.dry_run_payload(args)
        self.assertEqual("optional", payload["accuracy_preflight"]["policy"])
        self.assertFalse(payload["performs_adb_calls"])
        self.assertFalse(payload["writes_manifest"])

    def test_representative_intent_carries_container_and_preprocessing_hashes(self):
        arguments = ORCH.accuracy_preflight_intent_arguments(
            "11111111-2222-3333-4444-555555555555", 40, 7, 4,
            1e-4, 1e-3, 1e-6, "representative",
            "gpu-compat-default-v1", "/remote/input.d1tset", "a" * 64,
            "b" * 64,
        )
        self.assertIn("d1_accuracy_tensor_set_sha256", arguments)
        self.assertIn("a" * 64, arguments)
        self.assertIn("d1_accuracy_preprocessing_sha256", arguments)
        self.assertIn("b" * 64, arguments)

    def test_host_deterministic_input_hashes_are_reproducible_and_seeded(self):
        first = ORCH.deterministic_accuracy_input_hashes(7, 3, 8)
        self.assertEqual(first, ORCH.deterministic_accuracy_input_hashes(7, 3, 8))
        self.assertNotEqual(first, ORCH.deterministic_accuracy_input_hashes(8, 3, 8))

    def test_host_recomputes_binary_tolerance_nonfinite_and_argmax(self):
        tolerance = {"atol": 0.1, "rtol": 0.0, "relative_error_epsilon": 1e-6}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "outputs.bin"
            values = [
                ([1.0, 2.0, 3.0], [1.1, 2.0, 3.0]),
                ([3.0, 2.0, 1.0], [2.0, 4.0, float("inf")]),
            ]
            payload = b"D1EQV001" + __import__("struct").pack("<II", 2, 3)
            for reference, candidate in values:
                payload += __import__("struct").pack("<3f", *reference)
                payload += __import__("struct").pack("<3f", *candidate)
            path.write_bytes(payload)
            result = ORCH.validate_accuracy_binary(
                path, ORCH.sha256_file(path), 2, 3, tolerance
            )["host_recomputed"]
        self.assertGreaterEqual(result["mismatch_count"], 2)
        self.assertEqual(1, result["non_finite_count"])
        self.assertEqual(1, result["argmax_match_count"])
        self.assertEqual(1, result["argmax_mismatch_count"])

    def test_host_top5_boundary_ties_are_not_applicable(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ties.bin"
            values = [
                ([0.0] * 6, [0.0] * 6),
                ([0.6, 0.2, 0.1, 0.05, 0.025, 0.025],
                 [0.6, 0.2, 0.1, 0.05, 0.03, 0.02]),
                ([0.60, 0.15, 0.10, 0.07, 0.05, 0.03],
                 [0.60, 0.15, 0.10, 0.03, 0.05, 0.07]),
            ]
            payload = b"D1EQV001" + __import__("struct").pack("<II", 3, 6)
            for reference, candidate in values:
                payload += __import__("struct").pack("<6f", *reference)
                payload += __import__("struct").pack("<6f", *candidate)
            path.write_bytes(payload)
            host = ORCH.validate_accuracy_binary(
                path, ORCH.sha256_file(path), 3, 6,
                {"atol": 1e-4, "rtol": 1e-3, "relative_error_epsilon": 1e-6},
            )["host_recomputed"]
        self.assertFalse(host["per_input"][0]["top5_overlap_applicable"])
        self.assertEqual(
            "reference_and_candidate_top5_boundary_tie",
            host["per_input"][0]["top5_overlap_not_applicable_reason"],
        )
        self.assertFalse(host["per_input"][1]["top5_overlap_applicable"])
        self.assertTrue(host["per_input"][2]["top5_overlap_applicable"])
        self.assertEqual(1, host["top5_overlap_applicable_count"])
        self.assertEqual(2, host["top5_overlap_not_applicable_count"])
        self.assertEqual(4, host["minimum_top5_overlap_count"])

    def test_tied_overlap_is_excluded_but_determinate_overlap_failure_blocks(self):
        policy = ORCH.representative_acceptance_policy()
        base = {
            "argmax_mismatch_count": 0,
            "maximum_total_variation_distance": 0.001,
            "minimum_cosine_similarity": 0.9999,
        }
        tied_failures, integrity = ORCH.representative_acceptance_failures(
            dict(base, top5_overlap_applicable_count=0,
                 minimum_top5_overlap_count=None), policy
        )
        self.assertEqual([], tied_failures)
        self.assertEqual([], integrity)
        determinate_failures, integrity = ORCH.representative_acceptance_failures(
            dict(base, top5_overlap_applicable_count=39,
                 minimum_top5_overlap_count=3), policy
        )
        self.assertIn(
            "representative_top5_overlap_below_minimum", determinate_failures
        )
        self.assertEqual([], integrity)

    def test_representative_acceptance_failure_preserves_execution_integrity(self):
        args = ORCH.build_parser().parse_args([])
        representative = {
            "header": {
                "format_version": "d1-representative-tensor-set-v1",
                "selection": {"seed": 7},
            },
            "input_count": 40,
            "tensor_set_sha256": "1" * 64,
            "container_sha256": "2" * 64,
            "label_mapping_file_sha256": "3" * 64,
            "preprocessing_configuration_sha256": "4" * 64,
        }
        expected = ORCH.accuracy_expected_provenance(
            args, "fingerprint", "representative", representative
        )
        command_id = "33333333-3333-4333-8333-333333333333"
        metadata = {
            "schema_version": ORCH.ACCURACY_SCHEMA_VERSION,
            "validation_scope": "representative",
            "command_id": command_id,
            "comparator_version": expected["comparator_version"],
            "model_id": expected["model_id"],
            "model_sha256": expected["model_sha256"],
            "litert_version": expected["litert_version"],
            "input_shape": expected["input_shape"],
            "input_dtype": expected["input_dtype"],
            "reference_cpu_threads": expected["reference_cpu_threads"],
            "tolerance": expected["tolerance"],
            "comparator_version": expected["comparator_version"],
            "gpu_delegate_profile": expected["gpu_delegate_profile"],
            "reference_model_sha256": expected["model_sha256"],
            "candidate_model_sha256": expected["model_sha256"],
            "output_shape": ORCH.ACCURACY_OUTPUT_SHAPE,
            "output_dtype": ORCH.ACCURACY_OUTPUT_DTYPE,
            "representative_tensor_set": {
                key: expected[key] for key in (
                    "tensor_set_sha256", "tensor_set_container_sha256",
                    "label_mapping_file_sha256",
                    "preprocessing_configuration_sha256",
                )
            },
        }
        inputs = [
            {"reference_output_sha256": f"r{index}",
             "candidate_output_sha256": f"c{index}",
             "ground_truth": {"mapped_output_index": 1}}
            for index in range(40)
        ]
        summary = {
            "mismatch_count": 10, "non_finite_count": 0,
            "argmax_match_count": 39, "argmax_mismatch_count": 1,
            "aggregate": {},
        }
        host = {
            "mismatch_count": 10, "non_finite_count": 0,
            "argmax_match_count": 39, "argmax_mismatch_count": 1,
            "reference_output_sha256": [f"r{i}" for i in range(40)],
            "candidate_output_sha256": [f"c{i}" for i in range(40)],
            "top5_overlap_applicable_count": 40,
            "top5_overlap_not_applicable_count": 0,
            "minimum_top5_overlap_count": 1,
            "maximum_total_variation_distance": 0.023043,
            "minimum_cosine_similarity": 0.9999,
            "per_input": [
                {"reference_argmax": 1, "candidate_argmax": 1,
                 "reference_top5": [1], "candidate_top5": [1]}
                for _ in range(40)
            ],
        }
        result = ORCH.finalize_accuracy_preflight(
            {"metadata": metadata, "inputs": inputs, "summary": summary},
            {"verification": "verified", "full_delegate": True}, expected,
            command_id, {"sha256": "5" * 64, "host_recomputed": host},
        )
        self.assertEqual("failed", result["status"])
        self.assertEqual("passed", result["execution_integrity_status"])
        self.assertEqual("failed", result["equivalence_acceptance_status"])
        self.assertEqual([], result["execution_integrity_failure_reasons"])
        self.assertIn(
            "representative_top1_mismatch_limit_exceeded",
            result["equivalence_acceptance_failure_reasons"],
        )
        self.assertIn(
            "representative_top5_overlap_below_minimum",
            result["equivalence_acceptance_failure_reasons"],
        )

    def test_accuracy_result_is_atomically_attached_to_analyzer_summary(self):
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory)
            (run_dir / "merged").mkdir()
            summary_path = run_dir / "merged" / "summary.json"
            summary_path.write_text('{"run_id":"run-a"}', encoding="utf-8")
            accuracy = {"status": "passed", "artifact_sha256": "a" * 64}
            ORCH.attach_accuracy_to_analyzer_summary(run_dir, accuracy)
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
        self.assertEqual(accuracy, summary["accuracy_preflight"])
        self.assertEqual(
            "experiment_level_preflight_not_task_accuracy", summary["accuracy_scope"]
        )

    def test_axis_or_seed_change_is_resume_config_mismatch(self):
        base = ORCH.experiment_config(ORCH.build_parser().parse_args([
            "--cpu-thread-levels", "1", "2", "--duty-cycles", "25", "50",
            "--seed", "1",
        ]))
        changed_threads = ORCH.experiment_config(ORCH.build_parser().parse_args([
            "--cpu-thread-levels", "1", "4", "--duty-cycles", "25", "50",
            "--seed", "1",
        ]))
        changed_seed = ORCH.experiment_config(ORCH.build_parser().parse_args([
            "--cpu-thread-levels", "1", "2", "--duty-cycles", "25", "50",
            "--seed", "2",
        ]))
        self.assertNotEqual(base, changed_threads)
        self.assertNotEqual(base, changed_seed)

    def test_eighty_slot_matrix_dry_run_has_no_adb_or_manifest_write(self):
        with tempfile.TemporaryDirectory() as directory:
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = ORCH.main([
                    "--dry-run", "--mode", "formal",
                    "--resources", "CPU", "GPU",
                    "--cpu-thread-levels", "1", "2", "4",
                    "--duty-cycles", "25", "50", "75", "100",
                    "--duration", "600", "--warmup", "20", "--repeat", "5",
                    "--seed", "20260909", "--duty-cycle-period-seconds", "10",
                    "--start-policy", "matched", "--cooling-policy", "matched",
                    "--output-dir", directory,
                ])
            payload = json.loads(output.getvalue())
            self.assertEqual(0, code)
            self.assertEqual(80, payload["plan_summary"]["slot_count"])
            self.assertEqual(5, payload["plan_summary"]["block_count"])
            self.assertEqual(16, payload["plan_summary"]["condition_count"])
            self.assertEqual([16] * 5, payload["plan_summary"]["slots_per_block"])
            self.assertFalse(payload["performs_adb_calls"])
            self.assertFalse(payload["writes_manifest"])
            self.assertFalse((Path(directory) / ORCH.MANIFEST_NAME).exists())

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
            self.assertEqual(100, payload["config"]["duty_cycle_percent"])
            self.assertEqual(10.0, payload["config"]["duty_cycle_period_seconds"])
            self.assertEqual("fixed", payload["cooling"]["policy"])
            self.assertFalse((Path(directory) / ORCH.MANIFEST_NAME).exists())
            self.assertFalse((Path(directory) / "exports").exists())

    def test_completed_orchestrator_exports_and_preserves_export_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest_path = root / ORCH.MANIFEST_NAME
            manifest = {"runs": [], "status": "planned"}
            orchestrator = ORCH.ExperimentOrchestrator(
                ORCH.build_parser().parse_args([]), manifest, manifest_path
            )
            orchestrator.connect = lambda: None
            raw_marker = root / "raw-result.txt"
            raw_marker.write_text("preserve", encoding="utf-8")

            with mock.patch.object(
                ORCH, "export_thermal_dataset", side_effect=RuntimeError("export failed")
            ) as exporter:
                self.assertEqual(1, orchestrator.run())
            exporter.assert_called_once_with(root)
            self.assertEqual("preserve", raw_marker.read_text(encoding="utf-8"))
            self.assertEqual("failed", manifest["postprocessing"]["status"])
            self.assertTrue(manifest["postprocessing"]["sources_preserved"])
            self.assertIn("--experiment-dir", manifest["postprocessing"]["regeneration_command"])

            with mock.patch.object(
                ORCH, "export_thermal_dataset", return_value={}
            ) as exporter:
                self.assertEqual(0, orchestrator.run())
            exporter.assert_called_once_with(root)
            self.assertNotIn("postprocessing", manifest)
            self.assertEqual(1, len(manifest["postprocessing_history"]))

    def test_gpu_profiles_are_explicit_and_have_distinct_hashes(self):
        compatible = ORCH.gpu_profile("gpu-compat-default-v1")
        strict = ORCH.gpu_profile("gpu-fp32-strict-v1")
        self.assertTrue(compatible["precision_loss_allowed"])
        self.assertFalse(strict["precision_loss_allowed"])
        self.assertTrue(compatible["quantized_models_allowed"])
        self.assertEqual("FAST_SINGLE_ANSWER", compatible["inference_preference"])
        self.assertEqual("UNSET", compatible["force_backend"])
        self.assertNotEqual(
            compatible["configuration_sha256"], strict["configuration_sha256"]
        )

    def test_synthetic_outside_tolerance_is_not_task_or_integrity_failure(self):
        synthetic = {
            "status": "passed",
            "numerical_tolerance_result": "outside",
            "mismatch_count": 912,
            "failure_reasons": [],
        }
        result = ORCH.compose_accuracy_validation(
            "thermal-only-pilot", "required", synthetic
        )
        self.assertEqual("passed", result["status"])
        self.assertEqual("outside", result["synthetic_numerical_check"]["numerical_tolerance_result"])
        self.assertEqual("not_run", result["task_accuracy_check"]["status"])

    def test_schema_v2_synthetic_outside_tolerance_passes_only_integrity(self):
        args = ORCH.build_parser().parse_args([])
        expected = ORCH.accuracy_expected_provenance(args, "fingerprint", "synthetic")
        command_id = "22222222-2222-4222-8222-222222222222"
        input_hashes, input_set_hash = ORCH.deterministic_accuracy_input_hashes(
            expected["seed"], expected["input_count"], 1 * 224 * 224 * 3
        )
        inputs = [
            {
                "input_sha256": input_hashes[index],
                "reference_output_sha256": f"r{index}",
                "candidate_output_sha256": f"c{index}",
            }
            for index in range(32)
        ]
        metadata = {
            "schema_version": 2, "command_id": command_id,
            "validation_scope": "synthetic", "model_id": expected["model_id"],
            "model_sha256": expected["model_sha256"],
            "reference_model_sha256": expected["model_sha256"],
            "candidate_model_sha256": expected["model_sha256"],
            "litert_version": expected["litert_version"],
            "input_shape": expected["input_shape"], "input_dtype": expected["input_dtype"],
            "reference_cpu_threads": expected["reference_cpu_threads"],
            "tolerance": expected["tolerance"],
            "comparator_version": expected["comparator_version"],
            "gpu_delegate_profile": expected["gpu_delegate_profile"],
            "output_shape": [1, 1001], "output_dtype": "FLOAT32",
            "input_set_sha256": input_set_hash,
        }
        summary = {
            "mismatch_count": 912, "non_finite_count": 0,
            "argmax_match_count": 32, "argmax_mismatch_count": 0,
            "aggregate": {"max_absolute_error": 0.008},
        }
        host = {
            "mismatch_count": 912, "non_finite_count": 0,
            "argmax_match_count": 32, "argmax_mismatch_count": 0,
            "reference_output_sha256": [f"r{i}" for i in range(32)],
            "candidate_output_sha256": [f"c{i}" for i in range(32)],
        }
        result = ORCH.finalize_accuracy_preflight(
            {"schema_version": 2, "metadata": metadata, "inputs": inputs, "summary": summary},
            {"verification": "verified", "full_delegate": True}, expected, command_id,
            {"host_recomputed": host},
        )
        self.assertEqual("passed", result["status"], result["failure_reasons"])
        self.assertEqual("outside", result["numerical_tolerance_result"])
        metadata["gpu_delegate_profile"] = ORCH.gpu_profile("gpu-fp32-strict-v1")
        mismatch = ORCH.finalize_accuracy_preflight(
            {"schema_version": 2, "metadata": metadata, "inputs": inputs, "summary": summary},
            {"verification": "verified", "full_delegate": True}, expected, command_id,
            {"host_recomputed": host},
        )
        self.assertIn("gpu_delegate_profile_mismatch", mismatch["failure_reasons"])

    def test_formal_scopes_have_distinct_blocking_gates(self):
        synthetic = {"status": "passed", "failure_reasons": []}
        representative = {"status": "passed", "failure_reasons": []}
        task_not_run = {"status": "not_run", "failure_reasons": []}
        backend = ORCH.compose_accuracy_validation(
            "backend-performance-formal", "required", synthetic,
            representative, task_not_run,
        )
        accuracy = ORCH.compose_accuracy_validation(
            "accuracy-preserving-formal", "required", synthetic,
            representative, task_not_run,
        )
        self.assertEqual("passed", backend["formal_gate_result"]["status"])
        self.assertEqual("failed", accuracy["formal_gate_result"]["status"])
        self.assertIn(
            "task_accuracy_check_not_passed",
            accuracy["formal_gate_result"]["failure_reasons"],
        )

    def test_representative_not_run_blocks_backend_formal_but_not_thermal_pilot(self):
        synthetic = {"status": "passed", "failure_reasons": []}
        formal = ORCH.compose_accuracy_validation(
            "backend-performance-formal", "required", synthetic
        )
        pilot = ORCH.compose_accuracy_validation(
            "thermal-only-pilot", "optional", synthetic
        )
        self.assertEqual("failed", formal["status"])
        self.assertEqual("passed", pilot["status"])

    def test_accuracy_cache_rejects_profile_or_artifact_change(self):
        args = ORCH.build_parser().parse_args([])
        first = ORCH.accuracy_cache_provenance(args, "fingerprint", None)
        strict_args = ORCH.build_parser().parse_args([
            "--gpu-profile", "gpu-fp32-strict-v1"
        ])
        strict = ORCH.accuracy_cache_provenance(strict_args, "fingerprint", None)
        self.assertNotEqual(ORCH.canonical_sha256(first), ORCH.canonical_sha256(strict))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = []
            check = {"status": "passed"}
            for index, (path_key, hash_key) in enumerate((
                ("artifact_path", "artifact_sha256"),
                ("runner_artifact_path", "runner_artifact_sha256"),
                ("binary_artifact_path", "binary_artifact_sha256"),
                ("delegate_log_path", "delegate_log_sha256"),
            )):
                path = root / f"artifact-{index}"
                path.write_bytes(f"value-{index}".encode())
                paths.append(path)
                check[path_key] = path.name
                check[hash_key] = ORCH.sha256_file(path)
            key = ORCH.canonical_sha256(first)
            result = {
                "schema_version": 2, "status": "passed",
                "cache_key_sha256": key,
                "synthetic_numerical_check": check,
                "representative_input_equivalence": {"status": "not_run"},
            }
            self.assertTrue(ORCH.can_reuse_accuracy_validation(result, key, root))
            paths[0].write_text("changed", encoding="utf-8")
            self.assertFalse(ORCH.can_reuse_accuracy_validation(result, key, root))


if __name__ == "__main__":
    unittest.main()
