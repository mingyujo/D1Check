import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


MODULE_PATH = Path(__file__).with_name("d1_logger_v4.py")
FIXTURE_PATH = Path(__file__).with_name("fixtures") / "galaxy_a24_thermalservice.txt"
SPEC = importlib.util.spec_from_file_location("d1_logger_v4", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
LOGGER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(LOGGER)


class D1LoggerV4Test(unittest.TestCase):
    A24_GPU_LOG = """Created TensorFlow Lite delegate for GPU.
Loaded OpenCL library with dlopen.
Replacing 31 out of 31 node(s) with delegate (TfLiteGpuDelegateV2) node,
yielding 1 partitions for subgraph 0.
Initialized OpenCL-based API.
Created 1 GPU delegate kernels.
"""

    def test_existing_galaxy_a24_aliases(self):
        text = """Thermal Status: 2
Current temperatures from HAL:
 Temperature{mValue=40.1, mType=0, mName=AP, mStatus=1}
 Temperature{mValue=35.2, mType=3, mName=SKIN, mStatus=0}
 Temperature{mValue=33.3, mType=2, mName=BAT, mStatus=0}
 Temperature{mValue=38.4, mType=0, mName=PATHM, mStatus=0}
Current cooling devices from HAL:
"""
        self.assertEqual(
            LOGGER.parse_thermalservice(text),
            {
                "AP": "40.1",
                "SKIN": "35.2",
                "BAT": "33.3",
                "PA": "38.4",
                "thermal_status": "2",
            },
        )

    def test_galaxy_a24_thermalservice_fixture_prefers_current_hal_values(self):
        values = LOGGER.parse_thermalservice(FIXTURE_PATH.read_text(encoding="utf-8"))
        self.assertEqual("41.2", values["AP"])
        self.assertEqual("32.8", values["BAT"])
        self.assertEqual("38.7", values["PA"])
        self.assertEqual("35.4", values["SKIN"])

    def test_normal_uptime_response(self):
        self.assertEqual(332079680000000, LOGGER.parse_uptime("332079.68 338607.19\n"))

    def test_empty_uptime_response_has_explicit_error(self):
        with self.assertRaisesRegex(ValueError, "expected at least 2 uptime tokens, got 0"):
            LOGGER.parse_uptime("", "uptime before thermalservice")

    def test_failed_adb_response_includes_returncode(self):
        result = SimpleNamespace(returncode=7, stdout="", stderr="device offline")
        with patch.object(LOGGER.subprocess, "run", return_value=result):
            with self.assertRaisesRegex(RuntimeError, "returncode=7; device offline"):
                LOGGER.adb_text(["adb"], ["exec-out", "cat", "/proc/uptime"], "uptime")

    def test_successful_adb_with_empty_stdout_is_rejected(self):
        result = SimpleNamespace(returncode=0, stdout=" \r\n", stderr="")
        with patch.object(LOGGER.subprocess, "run", return_value=result):
            with self.assertRaisesRegex(RuntimeError, "adb returned empty stdout"):
                LOGGER.adb_text(["adb"], ["exec-out", "cat", "/proc/uptime"], "uptime")

    def test_thermal_dump_uses_separate_checked_adb_responses(self):
        fixture = FIXTURE_PATH.read_text(encoding="utf-8")
        responses = [
            SimpleNamespace(returncode=0, stdout="332079.68 338607.19\n", stderr=""),
            SimpleNamespace(returncode=0, stdout=fixture, stderr=""),
            SimpleNamespace(returncode=0, stdout="332080.12 338607.70\n", stderr=""),
        ]
        with patch.object(LOGGER.subprocess, "run", side_effect=responses) as run:
            values, raw = LOGGER.thermal_dump(["adb"])
        self.assertEqual(3, run.call_count)
        self.assertEqual("ok", values["parse_status"])
        self.assertEqual("38.7", values["PA"])
        self.assertEqual(fixture, raw)

    def test_perfetto_lifecycle_replay_starts_kills_and_pulls_exactly_once(self):
        with tempfile.TemporaryDirectory() as directory:
            session = LOGGER.CaptureSession(
                "adb", None, Path(directory), 1.0, True, Path("host-config.pbtxt")
            )
            session.run_id = "run-a"
            session.run_dir = Path(directory)
            (session.run_dir / "raw").mkdir()
            (session.run_dir / "diagnostics").mkdir()
            success = SimpleNamespace(returncode=0, stdout="", stderr="")

            def run_command(command, **_kwargs):
                if "perfetto" in command:
                    return SimpleNamespace(returncode=0, stdout="4321\n", stderr="")
                if "pull" in command:
                    Path(command[-1]).write_bytes(b"first-trace")
                return success

            events = (
                "diagnostic_trace_start",
                "diagnostic_trace_stop",
                "diagnostic_trace_start",
                "load_end",
                "diagnostic_trace_stop",
            )
            with patch.object(LOGGER.subprocess, "run", side_effect=run_command) as run, \
                    patch.object(LOGGER.time, "sleep"):
                for event in events:
                    session.handle_logcat_line(json.dumps({
                        "source": "gpu", "event": event, "run_id": "run-a",
                    }))
                session.stop_perfetto()  # capture finally

            commands = [call.args[0] for call in run.call_args_list]
            self.assertEqual(1, sum("perfetto" in command for command in commands))
            self.assertEqual(1, sum("kill" in command for command in commands))
            self.assertEqual(1, sum("pull" in command for command in commands))
            self.assertEqual(1, sum("rm" in command for command in commands))
            self.assertEqual(
                b"first-trace",
                (session.run_dir / "diagnostics/d1check.perfetto-trace").read_bytes(),
            )
            self.assertIs(session.perfetto_state, LOGGER.PerfettoState.COMPLETED)
            self.assertIsNone(session.perfetto_pid)

            push_command = next(command for command in commands if "push" in command)
            self.assertEqual(LOGGER.PERFETTO_DEVICE_CONFIG_PATH, push_command[-1])
            perfetto_command = next(command for command in commands if "perfetto" in command)
            self.assertEqual(
                LOGGER.PERFETTO_DEVICE_CONFIG_PATH,
                perfetto_command[perfetto_command.index("-c") + 1],
            )
            self.assertEqual(
                LOGGER.PERFETTO_DEVICE_TRACE_PATH,
                perfetto_command[perfetto_command.index("-o") + 1],
            )
            pull_command = next(command for command in commands if "pull" in command)
            self.assertEqual(LOGGER.PERFETTO_DEVICE_TRACE_PATH, pull_command[-2])
            cleanup_command = next(command for command in commands if "rm" in command)
            self.assertIn(LOGGER.PERFETTO_DEVICE_CONFIG_PATH, cleanup_command)
            self.assertIn(LOGGER.PERFETTO_DEVICE_TRACE_PATH, cleanup_command)

    def test_perfetto_start_failure_is_preserved_in_capture_error(self):
        with tempfile.TemporaryDirectory() as directory:
            session = LOGGER.CaptureSession(
                "adb", None, Path(directory), 1.0, True, Path("host-config.pbtxt")
            )
            session.run_id = "run-a"
            success = SimpleNamespace(returncode=0, stdout="", stderr="")
            denied = SimpleNamespace(
                returncode=13,
                stdout="config rejected",
                stderr="open failed: Permission denied",
            )
            with patch.object(
                LOGGER.subprocess, "run",
                side_effect=[success, denied],
            ):
                session.handle_logcat_line(json.dumps({
                    "source": "gpu",
                    "event": "diagnostic_trace_start",
                    "run_id": "run-a",
                }))
            self.assertTrue(session.stop.is_set())
            self.assertIn("returncode=13", session.capture_error)
            self.assertIn("Permission denied", session.capture_error)
            self.assertIn("config rejected", session.capture_error)
            self.assertIs(session.perfetto_state, LOGGER.PerfettoState.FAILED)

            with patch.object(LOGGER.subprocess, "run") as run:
                session.start_perfetto()
            run.assert_not_called()

    def test_perfetto_exit_zero_with_warning_stderr_is_success(self):
        with tempfile.TemporaryDirectory() as directory:
            session = LOGGER.CaptureSession(
                "adb", None, Path(directory), 1.0, True, Path("host-config.pbtxt")
            )
            success = SimpleNamespace(returncode=0, stdout="", stderr="warning: cleanup")
            started = SimpleNamespace(
                returncode=0,
                stdout="8765\n",
                stderr="warning: ftrace event unavailable",
            )
            with patch.object(
                LOGGER.subprocess, "run", side_effect=[success, started]
            ):
                session.start_perfetto()
            self.assertEqual("8765", session.perfetto_pid)

    def test_perfetto_pull_failure_retains_remote_trace_and_blocks_replay(self):
        with tempfile.TemporaryDirectory() as directory:
            session = LOGGER.CaptureSession(
                "adb", None, Path(directory), 1.0, True, Path("host-config.pbtxt")
            )
            session.run_id = "run-a"
            session.run_dir = Path(directory)
            (session.run_dir / "raw").mkdir()
            (session.run_dir / "diagnostics").mkdir()
            success = SimpleNamespace(returncode=0, stdout="", stderr="")
            failed_pull = SimpleNamespace(
                returncode=1, stdout="0 files pulled", stderr="remote read failed"
            )

            def run_command(command, **_kwargs):
                if "perfetto" in command:
                    return SimpleNamespace(returncode=0, stdout="999\n", stderr="")
                if "pull" in command:
                    return failed_pull
                return success

            with patch.object(LOGGER.subprocess, "run", side_effect=run_command) as run, \
                    patch.object(LOGGER.time, "sleep"):
                session.handle_logcat_line(json.dumps({
                    "source": "gpu", "event": "diagnostic_trace_start", "run_id": "run-a",
                }))
                session.handle_logcat_line(json.dumps({
                    "source": "gpu", "event": "diagnostic_trace_stop", "run_id": "run-a",
                }))
                session.handle_logcat_line(json.dumps({
                    "source": "gpu", "event": "diagnostic_trace_start", "run_id": "run-a",
                }))
                session.stop_perfetto()

            commands = [call.args[0] for call in run.call_args_list]
            self.assertEqual(1, sum("perfetto" in command for command in commands))
            self.assertEqual(1, sum("kill" in command for command in commands))
            self.assertEqual(1, sum("pull" in command for command in commands))
            self.assertEqual(0, sum("rm" in command for command in commands))
            self.assertIs(session.perfetto_state, LOGGER.PerfettoState.FAILED)
            self.assertIn(LOGGER.PERFETTO_DEVICE_TRACE_PATH, session.capture_error)
            self.assertIn("remote trace retained", session.capture_error)
            self.assertFalse(
                (session.run_dir / "diagnostics/d1check.perfetto-trace.part").exists()
            )

    def test_basic_perfetto_methods_remain_no_op(self):
        with tempfile.TemporaryDirectory() as directory:
            session = LOGGER.CaptureSession(
                "adb", None, Path(directory), 1.0, False, Path("host-config.pbtxt")
            )
            with patch.object(LOGGER.subprocess, "run") as run:
                session.start_perfetto()
                session.stop_perfetto()
                session.cleanup_perfetto()
            run.assert_not_called()
            self.assertIs(session.perfetto_state, LOGGER.PerfettoState.IDLE)

    def test_gpu_file_sequence_validation(self):
        events = [
            {"run_id": "r", "runner_session_id": "s", "sequence": 0, "event": "run_metadata"},
            {"run_id": "r", "runner_session_id": "s", "sequence": 1, "event": "inference"},
            {
                "run_id": "r",
                "runner_session_id": "s",
                "sequence": 2,
                "event": "file_summary",
                "file_event_count": 3,
                "sequence_last": 2,
            },
        ]
        LOGGER.validate_gpu_file(events, "r", "s")
        events[1]["sequence"] = 9
        with self.assertRaises(ValueError):
            LOGGER.validate_gpu_file(events, "r")

    def test_logcat_eof_stops_capture_as_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            session = LOGGER.CaptureSession(
                "adb", None, Path(directory), 1.0, False, Path("config")
            )
            session.consume_logcat([])
            self.assertTrue(session.stop.is_set())
            self.assertIn("stdout EOF", session.capture_error)

    def test_footerless_capture_uses_fallback_discovery(self):
        class Session(LOGGER.CaptureSession):
            def __init__(self, root):
                super().__init__("adb", None, root, 1.0, False, Path("config"))
                self.pulled = []

            def discover_runner_paths(self):
                return [
                    "/storage/emulated/0/Android/data/pkg/files/runs/"
                    "gpu-events-run-a-session-b.jsonl"
                ]

            def pull_runner_file(self, event):
                self.pulled.append(event)

        with tempfile.TemporaryDirectory() as directory:
            session = Session(Path(directory))
            session.run_id = "run-a"
            session.run_dir = Path(directory) / "run-a"
            session.recover_runner_files()
            self.assertEqual("session-b", session.pulled[0]["runner_session_id"])

    def test_new_run_inside_envelope_is_rejected(self):
        d1 = [
            {"event": "run_start", "run_id": "run-a", "mono_ns": 1},
            {"event": "run_start", "run_id": "run-b", "mono_ns": 2},
            {"event": "run_stop", "run_id": "run-a", "mono_ns": 10},
        ]
        gpu = [
            {"event": "load_start", "mono_ns": 3},
            {"event": "load_end", "mono_ns": 9},
        ]
        with self.assertRaises(ValueError):
            LOGGER.validate_run_envelope(d1, gpu, "run-a")

    def test_a24_31_of_31_gpu_delegate_is_verified(self):
        evidence = LOGGER.delegate_evidence(self.A24_GPU_LOG)
        self.assertEqual(31, evidence["replaced_nodes"])
        self.assertEqual(31, evidence["total_nodes"])
        self.assertEqual(1, evidence["gpu_delegate_kernel_count"])
        self.assertTrue(evidence["full_delegate"])

    def test_partial_gpu_delegation_is_unverified(self):
        evidence = LOGGER.delegate_evidence(self.A24_GPU_LOG.replace("31 out of 31", "30 out of 31"))
        self.assertFalse(evidence["full_delegate"])
        self.assertEqual("unverified", evidence["verification"])

    def test_full_node_count_with_failure_or_fallback_is_unverified(self):
        for failure in (
            "failed to apply delegate",
            "restored original execution plan",
            "remaining nodes run on CPU",
        ):
            with self.subTest(failure=failure):
                evidence = LOGGER.delegate_evidence(self.A24_GPU_LOG + failure)
                self.assertFalse(evidence["full_delegate"])
                self.assertTrue(evidence["failure_or_fallback_evidence"])

    def test_non_gpu_delegate_is_unverified(self):
        log = self.A24_GPU_LOG.replace("GPU", "NNAPI").replace(
            "TfLiteGpuDelegateV2", "TfLiteNnapiDelegate"
        )
        self.assertFalse(LOGGER.delegate_evidence(log)["full_delegate"])

    def test_thermal_coverage_requires_95_percent_and_load_sample(self):
        events = [
            {"event": "sample", "parse_status": "ok", "mono_ns": value}
            for value in range(1, 20)
        ] + [{"event": "sample_error", "error": "timeout"}]
        coverage = LOGGER.thermal_coverage(events, 10, 12)
        self.assertEqual(0.95, coverage["valid_ratio"])
        self.assertEqual(1, coverage["error_count"])
        self.assertTrue(coverage["passes_formal_requirement"])

    def test_thermal_coverage_fails_without_valid_load_sample(self):
        events = [{"event": "sample", "parse_status": "ok", "mono_ns": 1}]
        self.assertFalse(
            LOGGER.thermal_coverage(events, 10, 12)["passes_formal_requirement"]
        )

    def test_current_raw_is_not_calibrated(self):
        source = MODULE_PATH.read_text(encoding="utf-8")
        self.assertNotIn("current_A_calibrated", source)
        self.assertNotIn("battery_power_W_signed", source)

    def test_current_and_charge_counter_use_positive_discharge_magnitude(self):
        current_magnitude = LOGGER.current_now_discharge_magnitude_ua(-360000.0)
        counter_magnitude = LOGGER.charge_counter_discharge_magnitude_ua(
            3_000_000.0, 2_999_000.0, 10.0
        )
        self.assertEqual(360000.0, current_magnitude)
        self.assertEqual(360000.0, counter_magnitude)

    def test_charge_counter_increase_is_not_treated_as_discharge(self):
        with self.assertRaisesRegex(ValueError, "charge counter increased"):
            LOGGER.charge_counter_discharge_magnitude_ua(
                2_999_000.0, 3_000_000.0, 10.0
            )


if __name__ == "__main__":
    unittest.main()
