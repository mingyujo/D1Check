import contextlib
import importlib.util
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


MODULE_PATH = Path(__file__).with_name("d1_logger_v4.py")
FIXTURE_PATH = Path(__file__).with_name("fixtures") / "galaxy_a24_thermalservice.txt"
PERFETTO_CONFIG_PATH = Path(__file__).with_name("perfetto") / "gpu_diagnostic.pbtxt"
SPEC = importlib.util.spec_from_file_location("d1_logger_v4", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
LOGGER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(LOGGER)


class D1LoggerV4Test(unittest.TestCase):
    DIAGNOSTIC_SESSION_ID = "33333333-3333-3333-3333-333333333333"

    def detached_control_metadata(self):
        return {
            "diagnostic_perfetto_control_mode": "detached_session",
            "diagnostic_perfetto_session_key": (
                f"d1check-{self.DIAGNOSTIC_SESSION_ID}"
            ),
            "diagnostic_perfetto_start_pid": None,
            "diagnostic_perfetto_control_results": {
                stage: {
                    "status": "completed",
                    "returncode": returncode,
                    "stdout": "",
                    "stderr": "",
                    "timeout_seconds": 5,
                }
                for stage, returncode in LOGGER.DETACHED_SUCCESS_RETURN_CODES.items()
            },
            "diagnostic_perfetto_readiness_semantics": (
                LOGGER.DETACHED_READINESS_SEMANTICS
            ),
            "diagnostic_perfetto_pid_control": LOGGER.DETACHED_PID_CONTROL,
            "diagnostic_perfetto_config_write_into_file": True,
            "diagnostic_perfetto_config_duration_ms": 183000,
        }

    def gpu_profile(self, profile_id="gpu-compat-default-v1", digest="a" * 64):
        return {
            "profile_id": profile_id,
            "configuration_sha256": digest,
            "precision_loss_allowed": profile_id == "gpu-compat-default-v1",
            "quantized_models_allowed": True,
            "inference_preference": "FAST_SINGLE_ANSWER",
            "force_backend": "UNSET",
            "actual_fp16_execution": "unknown_not_exposed_by_litert_api",
        }

    def test_gpu_profile_compat_and_strict_are_preserved(self):
        for profile in (
            self.gpu_profile(),
            self.gpu_profile("gpu-fp32-strict-v1", "b" * 64),
        ):
            result = LOGGER.validate_gpu_execution_profile(
                "GPU", profile, profile, profile, manifest_available=True
            )
            self.assertTrue(result["valid"])
            self.assertEqual("pass", result["status"])
            self.assertEqual(profile["profile_id"], result["profile_id"])

    def test_cpu_profile_is_not_applicable(self):
        result = LOGGER.validate_gpu_execution_profile("CPU", None)
        self.assertTrue(result["valid"])
        self.assertEqual("not_applicable", result["status"])

    def test_gpu_profile_id_and_hash_mismatch_fail(self):
        timed = self.gpu_profile()
        wrong_id = self.gpu_profile("gpu-fp32-strict-v1")
        wrong_hash = self.gpu_profile(digest="b" * 64)
        result = LOGGER.validate_gpu_execution_profile(
            "GPU", timed, wrong_id, wrong_hash, manifest_available=True
        )
        self.assertFalse(result["valid"])
        self.assertIn("config_gpu_profile_id_mismatch", result["failure_reasons"])
        self.assertIn(
            "accuracy_preflight_gpu_profile_hash_mismatch",
            result["failure_reasons"],
        )

    def test_legacy_gpu_profile_is_missing_without_inference(self):
        result = LOGGER.validate_gpu_execution_profile("GPU", None)
        self.assertFalse(result["valid"])
        self.assertEqual("legacy_missing", result["status"])

    def test_unrun_accuracy_and_uncalibrated_energy_are_not_misrepresented(self):
        provenance = LOGGER.measurement_provenance({})

        self.assertEqual("not_run", provenance["accuracy_preflight"]["status"])
        self.assertEqual(
            "raw_unverified", provenance["energy_measurement"]["status"]
        )
        self.assertFalse(
            provenance["energy_measurement"]["current_unit_verified"]
        )
        self.assertFalse(
            provenance["energy_measurement"]["calculation_performed"]
        )
        self.assertNotIn("joules", provenance["energy_measurement"])
        self.assertNotIn("mWh", provenance["energy_measurement"])

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

    def test_perfetto_detached_lifecycle_starts_stops_and_pulls_exactly_once(self):
        with tempfile.TemporaryDirectory() as directory:
            session = LOGGER.CaptureSession(
                "adb", None, Path(directory), 1.0, True, PERFETTO_CONFIG_PATH,
                2, self.DIAGNOSTIC_SESSION_ID, 183000,
            )
            session.run_id = "run-a"
            session.run_dir = Path(directory)
            (session.run_dir / "raw").mkdir()
            (session.run_dir / "diagnostics").mkdir()
            success = SimpleNamespace(returncode=0, stdout="", stderr="")
            detached_probe_count = 0
            pushed_config_text = None

            def run_command(command, **_kwargs):
                nonlocal detached_probe_count, pushed_config_text
                if any(value.startswith("--is_detached=") for value in command):
                    detached_probe_count += 1
                    return SimpleNamespace(
                        returncode=(2, 0, 2)[detached_probe_count - 1],
                        stdout="", stderr="",
                    )
                if any(value.startswith("--detach=") for value in command):
                    return SimpleNamespace(returncode=0, stdout="4321\n", stderr="")
                if any(value.startswith("--attach=") for value in command):
                    return success
                if "push" in command:
                    pushed_config_text = Path(command[-2]).read_text(encoding="utf-8")
                if "pull" in command:
                    Path(command[-1]).write_bytes(b"first-trace")
                return success

            events = (
                ("diagnostic_trace_start", None),
                ("diagnostic_trace_stop", None),
                ("diagnostic_trace_start", 5),
                ("load_end", 6),
                ("diagnostic_trace_stop", 7),
            )
            with patch.object(LOGGER.subprocess, "run", side_effect=run_command) as run, \
                    patch.object(LOGGER.time, "sleep"):
                session.start_perfetto()
                for event, sequence in events:
                    record = {
                        "source": "gpu", "event": event, "run_id": "run-a",
                        "protocol_version": 2,
                        "diagnostic_session_id": self.DIAGNOSTIC_SESSION_ID,
                        "requested_trace_mode": "on",
                    }
                    if sequence is not None:
                        record["sequence"] = sequence
                    session.handle_logcat_line(json.dumps(record))
                session.stop_perfetto()  # capture finally

            commands = [call.args[0] for call in run.call_args_list]
            self.assertTrue(all(call.kwargs.get("timeout", 0) > 0 for call in run.call_args_list))
            self.assertEqual(1, sum(any(value.startswith("--detach=") for value in command)
                                    for command in commands))
            self.assertEqual(1, sum(any(value.startswith("--attach=") for value in command)
                                    for command in commands))
            self.assertEqual(3, sum(any(value.startswith("--is_detached=") for value in command)
                                    for command in commands))
            self.assertFalse(any("kill" in command for command in commands))
            self.assertEqual(1, sum("pull" in command for command in commands))
            self.assertEqual(1, sum("rm" in command for command in commands))
            self.assertEqual(
                b"first-trace",
                (session.run_dir / "diagnostics" /
                 session.diagnostic_trace_filename).read_bytes(),
            )
            self.assertIs(session.perfetto_state, LOGGER.PerfettoState.COMPLETED)
            self.assertIsNone(session.perfetto_pid)
            self.assertIsNone(session.perfetto_start_pid)
            self.assertIsNone(session.capture_error)
            control_metadata = session.perfetto_control_metadata()
            self.assertEqual(
                LOGGER.DETACHED_READINESS_SEMANTICS,
                control_metadata["diagnostic_perfetto_readiness_semantics"],
            )
            self.assertEqual(
                LOGGER.DETACHED_PID_CONTROL,
                control_metadata["diagnostic_perfetto_pid_control"],
            )
            self.assertIsNone(control_metadata["diagnostic_perfetto_start_pid"])
            self.assertTrue(
                control_metadata["diagnostic_perfetto_config_write_into_file"]
            )
            self.assertEqual(
                183000,
                control_metadata["diagnostic_perfetto_config_duration_ms"],
            )
            self.assertEqual(len(b"first-trace"), session.pulled_trace_size_bytes)
            self.assertEqual(
                LOGGER.hashlib.sha256(b"first-trace").hexdigest(),
                session.pulled_trace_sha256,
            )

            push_command = next(command for command in commands if "push" in command)
            self.assertEqual(session.perfetto_device_config_path, push_command[-1])
            self.assertIsNotNone(pushed_config_text)
            self.assertEqual(1, pushed_config_text.count("write_into_file: true"))
            self.assertEqual(1, pushed_config_text.count("duration_ms: 183000"))
            perfetto_command = next(
                command for command in commands
                if any(value.startswith("--detach=") for value in command)
            )
            self.assertEqual([
                "adb", "shell", "perfetto", "--txt",
                f"--detach=d1check-{self.DIAGNOSTIC_SESSION_ID}",
                "--config", session.perfetto_device_config_path,
                "--out", session.perfetto_device_trace_path,
            ], perfetto_command)
            self.assertNotIn("--background", perfetto_command)
            self.assertNotIn("--background-wait", perfetto_command)
            pull_command = next(command for command in commands if "pull" in command)
            self.assertEqual(session.perfetto_device_trace_path, pull_command[-2])
            cleanup_command = next(command for command in commands if "rm" in command)
            self.assertIn(session.perfetto_device_config_path, cleanup_command)
            self.assertIn(session.perfetto_device_trace_path, cleanup_command)

    def test_perfetto_start_failure_is_preserved_in_capture_error(self):
        with tempfile.TemporaryDirectory() as directory:
            session = LOGGER.CaptureSession(
                "adb", None, Path(directory), 1.0, True, PERFETTO_CONFIG_PATH,
                2, self.DIAGNOSTIC_SESSION_ID,
            )
            session.run_id = "run-a"
            absent = SimpleNamespace(returncode=2, stdout="", stderr="")
            denied = SimpleNamespace(
                returncode=13,
                stdout="config rejected",
                stderr="open failed: Permission denied",
            )
            with patch.object(
                LOGGER.subprocess, "run",
                side_effect=[absent, denied],
            ), self.assertRaisesRegex(RuntimeError, "returncode=13"):
                session.start_perfetto()
            self.assertIn("returncode=13", session.capture_error)
            self.assertIn("Permission denied", session.capture_error)
            self.assertIn("config rejected", session.capture_error)
            self.assertIs(session.perfetto_state, LOGGER.PerfettoState.FAILED)

            with patch.object(LOGGER.subprocess, "run") as run:
                session.start_perfetto()
            run.assert_not_called()

    def test_trace_on_startup_failures_are_reported_before_ready(self):
        success = SimpleNamespace(returncode=0, stdout="", stderr="")
        absent = SimpleNamespace(returncode=2, stdout="", stderr="")
        started = SimpleNamespace(returncode=0, stdout="8765\n", stderr="")
        cases = (
            (
                "stale detached session",
                [success],
                "stale/replay detached session already exists",
            ),
            (
                "pre-start capability error",
                [SimpleNamespace(returncode=1, stdout="bad option", stderr="unsupported")],
                "pre-start detached-session probe failed: returncode=1",
            ),
            (
                "pre-start timeout",
                [subprocess.TimeoutExpired(["adb", "shell", "perfetto"], 5)],
                "pre_start_is_detached timed out after 5s",
            ),
            (
                "config push nonzero",
                [absent, SimpleNamespace(returncode=13, stdout="push rejected", stderr="Permission denied")],
                "Perfetto config push failed: returncode=13",
            ),
            (
                "config push timeout",
                [absent, subprocess.TimeoutExpired(["adb", "push"], 30)],
                "config_push timed out after 30s",
            ),
            (
                "config push OS error",
                [absent, OSError("host spawn failed")],
                "host spawn failed",
            ),
            (
                "Perfetto start nonzero",
                [absent, success, SimpleNamespace(returncode=7, stdout="start rejected", stderr="not allowed")],
                "Perfetto start failed: returncode=7",
            ),
            (
                "Perfetto start timeout",
                [absent, success, subprocess.TimeoutExpired(["adb", "shell", "perfetto"], 30)],
                "start timed out after 30s",
            ),
            (
                "ready session absent",
                [absent, success, started, absent],
                "ready detached-session probe failed: returncode=2",
            ),
            (
                "ready capability error",
                [
                    absent, success, started,
                    SimpleNamespace(returncode=1, stdout="", stderr="gone"),
                ],
                "ready detached-session probe failed: returncode=1",
            ),
        )

        for name, responses, expected in cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                session = LOGGER.CaptureSession(
                    "adb", None, Path(directory), 1.0, True,
                    PERFETTO_CONFIG_PATH, 2, self.DIAGNOSTIC_SESSION_ID,
                )
                stderr = io.StringIO()
                with patch.object(LOGGER.subprocess, "run", side_effect=responses), \
                        patch.object(session, "cleanup_perfetto") as cleanup, \
                        contextlib.redirect_stderr(stderr):
                    self.assertEqual(1, session.run())

                self.assertIn(expected, session.capture_error)
                self.assertIn(expected, stderr.getvalue())
                self.assertNotIn("capture started", stderr.getvalue())
                cleanup.assert_called_once_with()
                self.assertEqual([], list(Path(directory).iterdir()))

    def test_trace_on_startup_cleanup_error_is_suppressed_and_flushed(self):
        denied = SimpleNamespace(
            returncode=13, stdout="config rejected", stderr="Permission denied",
        )
        with tempfile.TemporaryDirectory() as directory:
            session = LOGGER.CaptureSession(
                "adb", None, Path(directory), 1.0, True,
                PERFETTO_CONFIG_PATH, 2, self.DIAGNOSTIC_SESSION_ID,
            )
            absent = SimpleNamespace(returncode=2, stdout="", stderr="")
            with patch.object(LOGGER.subprocess, "run", side_effect=[absent, denied]), \
                    patch.object(
                        session, "cleanup_perfetto",
                        side_effect=OSError("cleanup transport failed"),
                    ) as cleanup, \
                    patch("builtins.print") as output:
                self.assertEqual(1, session.run())

            primary = session.capture_error
            self.assertIsNotNone(primary)
            self.assertIn("Perfetto config push failed: returncode=13", primary)
            self.assertNotIn("cleanup transport failed", primary)
            self.assertIn(
                "suppressed cleanup error: cleanup transport failed",
                session.capture_warnings,
            )
            output.assert_any_call(
                f"error: {primary}", file=LOGGER.sys.stderr, flush=True,
            )
            output.assert_any_call(
                "warning: suppressed cleanup error: cleanup transport failed",
                file=LOGGER.sys.stderr,
                flush=True,
            )
            self.assertFalse(
                any("capture started" in str(call.args) for call in output.call_args_list)
            )
            cleanup.assert_called_once_with()

    def test_perfetto_exit_zero_with_warning_stderr_is_success(self):
        with tempfile.TemporaryDirectory() as directory:
            session = LOGGER.CaptureSession(
                "adb", None, Path(directory), 1.0, True, PERFETTO_CONFIG_PATH,
                2, self.DIAGNOSTIC_SESSION_ID,
            )
            absent = SimpleNamespace(returncode=2, stdout="", stderr="")
            success = SimpleNamespace(returncode=0, stdout="", stderr="warning: cleanup")
            started = SimpleNamespace(
                returncode=0,
                stdout="8765\n",
                stderr="warning: ftrace event unavailable",
            )
            with patch.object(
                LOGGER.subprocess, "run",
                side_effect=[absent, success, started, success],
            ):
                session.start_perfetto()
            self.assertIsNone(session.perfetto_pid)
            self.assertIsNone(session.perfetto_start_pid)
            self.assertIs(session.perfetto_state, LOGGER.PerfettoState.RUNNING)

    def test_perfetto_ready_requires_detached_session_probe_zero(self):
        with tempfile.TemporaryDirectory() as directory:
            session = LOGGER.CaptureSession(
                "adb", None, Path(directory), 1.0, True, PERFETTO_CONFIG_PATH,
                2, self.DIAGNOSTIC_SESSION_ID,
            )
            responses = [
                SimpleNamespace(returncode=2, stdout="", stderr=""),
                SimpleNamespace(returncode=0, stdout="", stderr=""),
                SimpleNamespace(returncode=0, stdout="8765\n", stderr=""),
                SimpleNamespace(returncode=2, stdout="", stderr="no session"),
            ]
            with patch.object(LOGGER.subprocess, "run", side_effect=responses), \
                    self.assertRaisesRegex(RuntimeError, "ready detached-session probe"):
                session.start_perfetto()
            self.assertFalse(session.perfetto_started_successfully)
            self.assertIs(session.perfetto_state, LOGGER.PerfettoState.FAILED)

    def test_perfetto_start_timeout_fails_closed_with_bounded_call(self):
        with tempfile.TemporaryDirectory() as directory:
            session = LOGGER.CaptureSession(
                "adb", None, Path(directory), 1.0, True, PERFETTO_CONFIG_PATH,
                2, self.DIAGNOSTIC_SESSION_ID,
            )
            success = SimpleNamespace(returncode=0, stdout="", stderr="")
            absent = SimpleNamespace(returncode=2, stdout="", stderr="")
            timeout = LOGGER.subprocess.TimeoutExpired(
                ["adb", "shell", "perfetto"], 30
            )
            cleanup = SimpleNamespace(returncode=0, stdout="", stderr="")
            with patch.object(
                LOGGER.subprocess, "run",
                side_effect=[
                    absent, success, timeout,
                    success, cleanup, absent, cleanup,
                ],
            ) as run:
                with self.assertRaisesRegex(RuntimeError, "timed out"):
                    session.start_perfetto()
                self.assertEqual(
                    LOGGER.PERFETTO_START_TIMEOUT_S,
                    run.call_args_list[2].kwargs["timeout"],
                )
                self.assertFalse(session.perfetto_started_successfully)
                session.cleanup_perfetto()
                self.assertIn("rm", run.call_args.args[0])
                self.assertEqual(
                    LOGGER.PERFETTO_CLEANUP_TIMEOUT_S,
                    run.call_args.kwargs["timeout"],
                )
                commands = [call.args[0] for call in run.call_args_list]
                self.assertEqual(1, sum(
                    any(value.startswith("--attach=") for value in command)
                    for command in commands
                ))
                self.assertFalse(any("kill" in command for command in commands))

    def test_detached_start_failure_absent_session_cleanup_is_no_op(self):
        with tempfile.TemporaryDirectory() as directory:
            session = LOGGER.CaptureSession(
                "adb", None, Path(directory), 1.0, True, PERFETTO_CONFIG_PATH,
                2, self.DIAGNOSTIC_SESSION_ID, 183000,
            )
            absent = SimpleNamespace(returncode=2, stdout="", stderr="no session")
            success = SimpleNamespace(returncode=0, stdout="", stderr="")
            start_failed = SimpleNamespace(
                returncode=7, stdout="rejected", stderr="detach failed"
            )
            with patch.object(
                LOGGER.subprocess, "run",
                side_effect=[absent, success, start_failed, absent, success],
            ) as run, contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(1, session.run())
            commands = [call.args[0] for call in run.call_args_list]
            self.assertFalse(any(
                any(value.startswith("--attach=") for value in command)
                for command in commands
            ))
            self.assertFalse(any("kill" in command for command in commands))
            self.assertEqual([], session.capture_warnings)
            self.assertIn("returncode=7", session.capture_error)

    def test_detached_start_failure_active_session_runs_attach_stop_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            session = LOGGER.CaptureSession(
                "adb", None, Path(directory), 1.0, True, PERFETTO_CONFIG_PATH,
                2, self.DIAGNOSTIC_SESSION_ID, 183000,
            )
            absent = SimpleNamespace(returncode=2, stdout="", stderr="no session")
            success = SimpleNamespace(returncode=0, stdout="", stderr="")
            active = SimpleNamespace(returncode=0, stdout="", stderr="active")
            start_failed = SimpleNamespace(
                returncode=7, stdout="rejected", stderr="detach failed"
            )
            with patch.object(
                LOGGER.subprocess, "run",
                side_effect=[
                    absent, success, start_failed,
                    active, success, absent, success,
                ],
            ) as run, contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(1, session.run())
            commands = [call.args[0] for call in run.call_args_list]
            self.assertEqual(1, sum(
                any(value.startswith("--attach=") for value in command)
                for command in commands
            ))
            self.assertFalse(any("kill" in command for command in commands))
            self.assertIn("returncode=7", session.capture_error)

    def test_detached_config_strict_validation_rejects_missing_and_bad_duration(self):
        valid_data_source = 'data_sources { config { name: "linux.ftrace" } }\n'
        cases = (
            (valid_data_source + "duration_ms: 1000\n", "write_into_file"),
            (valid_data_source + "write_into_file: true\n", "duration_ms"),
            (
                valid_data_source + "write_into_file: true\nduration_ms: 0\n",
                "positive",
            ),
            (
                valid_data_source + "write_into_file: true\nduration_ms: -1\n",
                "positive",
            ),
        )
        for text, expected in cases:
            with self.subTest(expected=expected), self.assertRaisesRegex(
                RuntimeError, expected
            ):
                LOGGER.CaptureSession._validate_detached_perfetto_config_text(text)

    def test_existing_safe_detached_config_is_not_rewritten_or_duplicated(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "complete.pbtxt"
            original = "write_into_file: true\nduration_ms: 12345\n"
            config.write_text(original, encoding="utf-8")
            session = LOGGER.CaptureSession(
                "adb", None, Path(directory) / "out", 1.0, True, config,
                2, self.DIAGNOSTIC_SESSION_ID, 183000,
            )
            prepared, temporary = session._prepare_detached_perfetto_config()
            self.assertEqual(config, prepared)
            self.assertIsNone(temporary)
            self.assertEqual(original, prepared.read_text(encoding="utf-8"))
            self.assertEqual(12345, session.perfetto_config_duration_ms)

    def test_explicit_unsafe_detached_config_fails_before_subprocess(self):
        cases = (
            ("write_into_file: false\nduration_ms: 1000\n", "write_into_file"),
            ("write_into_file: true\nduration_ms: 0\n", "positive"),
            ("write_into_file: true\nduration_ms: -1\n", "positive"),
        )
        for content, expected in cases:
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as directory:
                config = Path(directory) / "unsafe.pbtxt"
                config.write_text(content, encoding="utf-8")
                session = LOGGER.CaptureSession(
                    "adb", None, Path(directory) / "out", 1.0, True, config,
                    2, self.DIAGNOSTIC_SESSION_ID, 183000,
                )
                with patch.object(LOGGER.subprocess, "run") as run, \
                        self.assertRaisesRegex(RuntimeError, expected):
                    session.start_perfetto()
                run.assert_not_called()

    def test_detached_execution_failure_cleanup_is_bounded_and_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            session = LOGGER.CaptureSession(
                "adb", None, Path(directory), 1.0, True, PERFETTO_CONFIG_PATH,
                2, self.DIAGNOSTIC_SESSION_ID,
            )
            session.perfetto_state = LOGGER.PerfettoState.RUNNING
            session.perfetto_session_may_exist = True
            session.capture_error = "inference failed"
            responses = [
                SimpleNamespace(returncode=0, stdout="active", stderr=""),
                SimpleNamespace(returncode=0, stdout="stopped", stderr=""),
                SimpleNamespace(returncode=2, stdout="", stderr="no session"),
            ]
            with patch.object(LOGGER.subprocess, "run", side_effect=responses) as run:
                session.cleanup_perfetto()
                session.cleanup_perfetto()
            commands = [call.args[0] for call in run.call_args_list]
            self.assertEqual(1, sum(any(value.startswith("--attach=") for value in command)
                                    for command in commands))
            self.assertEqual(2, sum(any(value.startswith("--is_detached=") for value in command)
                                    for command in commands))
            self.assertTrue(all(call.kwargs.get("timeout", 0) > 0
                                for call in run.call_args_list))
            self.assertEqual("inference failed", session.capture_error)
            self.assertFalse(any("kill" in command for command in commands))

    def test_detached_stop_remaining_session_fails_and_runs_one_cleanup_attempt(self):
        with tempfile.TemporaryDirectory() as directory:
            session = LOGGER.CaptureSession(
                "adb", None, Path(directory), 1.0, True, PERFETTO_CONFIG_PATH,
                2, self.DIAGNOSTIC_SESSION_ID,
            )
            session.run_dir = Path(directory)
            (session.run_dir / "diagnostics").mkdir()
            responses = [
                SimpleNamespace(returncode=2, stdout="", stderr=""),
                SimpleNamespace(returncode=0, stdout="", stderr=""),
                SimpleNamespace(returncode=0, stdout="32624\n", stderr=""),
                SimpleNamespace(returncode=0, stdout="", stderr=""),
                SimpleNamespace(returncode=0, stdout="stopped", stderr=""),
                SimpleNamespace(returncode=0, stdout="", stderr="still active"),
                SimpleNamespace(returncode=0, stdout="", stderr="still active"),
                SimpleNamespace(returncode=0, stdout="stopped in cleanup", stderr=""),
                SimpleNamespace(returncode=2, stdout="", stderr="no session"),
                SimpleNamespace(returncode=0, stdout="", stderr=""),
            ]
            with patch.object(LOGGER.subprocess, "run", side_effect=responses) as run:
                session.start_perfetto()
                session.stop_perfetto()
            commands = [call.args[0] for call in run.call_args_list]
            self.assertIs(session.perfetto_state, LOGGER.PerfettoState.FAILED)
            self.assertIn("session remains active", session.capture_error)
            self.assertEqual(2, sum(any(value.startswith("--attach=") for value in command)
                                    for command in commands))
            self.assertFalse(any("kill" in command for command in commands))

    def test_detached_stop_command_failure_runs_one_cleanup_attempt(self):
        with tempfile.TemporaryDirectory() as directory:
            session = LOGGER.CaptureSession(
                "adb", None, Path(directory), 1.0, True, PERFETTO_CONFIG_PATH,
                2, self.DIAGNOSTIC_SESSION_ID,
            )
            session.perfetto_state = LOGGER.PerfettoState.RUNNING
            session.perfetto_session_may_exist = True
            responses = [
                SimpleNamespace(returncode=7, stdout="", stderr="stop failed"),
                SimpleNamespace(returncode=0, stdout="", stderr="active"),
                SimpleNamespace(returncode=0, stdout="cleanup stopped", stderr=""),
                SimpleNamespace(returncode=2, stdout="", stderr="no session"),
            ]
            with patch.object(LOGGER.subprocess, "run", side_effect=responses) as run:
                session.stop_perfetto()
            commands = [call.args[0] for call in run.call_args_list]
            self.assertIs(session.perfetto_state, LOGGER.PerfettoState.FAILED)
            self.assertIn("detached stop failed: returncode=7", session.capture_error)
            self.assertEqual(2, sum(any(value.startswith("--attach=") for value in command)
                                    for command in commands))
            self.assertEqual(2, sum(any(value.startswith("--is_detached=") for value in command)
                                    for command in commands))
            self.assertFalse(any("kill" in command for command in commands))

    def test_detached_cleanup_failure_is_suppressed_beside_primary_error(self):
        with tempfile.TemporaryDirectory() as directory:
            session = LOGGER.CaptureSession(
                "adb", None, Path(directory), 1.0, True, PERFETTO_CONFIG_PATH,
                2, self.DIAGNOSTIC_SESSION_ID,
            )
            session.perfetto_state = LOGGER.PerfettoState.FAILED
            session.perfetto_session_may_exist = True
            session.capture_error = "first execution error"
            responses = [
                SimpleNamespace(returncode=0, stdout="", stderr="active"),
                SimpleNamespace(returncode=7, stdout="", stderr="stop denied"),
                SimpleNamespace(returncode=0, stdout="", stderr="still active"),
            ]
            with patch.object(LOGGER.subprocess, "run", side_effect=responses) as run:
                session.cleanup_perfetto()
            self.assertEqual("first execution error", session.capture_error)
            self.assertTrue(any("detached cleanup stop" in warning
                                for warning in session.capture_warnings))
            self.assertTrue(any("session remains active" in warning
                                for warning in session.capture_warnings))
            self.assertEqual(3, run.call_count)

    def test_detached_cleanup_probe_error_is_suppressed_without_attach(self):
        with tempfile.TemporaryDirectory() as directory:
            session = LOGGER.CaptureSession(
                "adb", None, Path(directory), 1.0, True, PERFETTO_CONFIG_PATH,
                2, self.DIAGNOSTIC_SESSION_ID, 183000,
            )
            session.perfetto_state = LOGGER.PerfettoState.FAILED
            session.perfetto_session_may_exist = True
            session.capture_error = "first start error"
            probe_error = SimpleNamespace(
                returncode=1, stdout="", stderr="capability error"
            )
            with patch.object(
                LOGGER.subprocess, "run", return_value=probe_error
            ) as run:
                session.cleanup_perfetto()
            self.assertEqual("first start error", session.capture_error)
            self.assertTrue(any("pre-stop probe" in warning
                                for warning in session.capture_warnings))
            commands = [call.args[0] for call in run.call_args_list]
            self.assertFalse(any(
                any(value.startswith("--attach=") for value in command)
                for command in commands
            ))

    def test_perfetto_pull_failure_cleans_remote_trace_and_blocks_replay(self):
        with tempfile.TemporaryDirectory() as directory:
            session = LOGGER.CaptureSession(
                "adb", None, Path(directory), 1.0, True, PERFETTO_CONFIG_PATH,
                2, self.DIAGNOSTIC_SESSION_ID,
            )
            session.run_id = "run-a"
            session.run_dir = Path(directory)
            (session.run_dir / "raw").mkdir()
            (session.run_dir / "diagnostics").mkdir()
            success = SimpleNamespace(returncode=0, stdout="", stderr="")
            failed_pull = SimpleNamespace(
                returncode=1, stdout="0 files pulled", stderr="remote read failed"
            )
            detached_probe_count = 0

            def run_command(command, **_kwargs):
                nonlocal detached_probe_count
                if any(value.startswith("--is_detached=") for value in command):
                    detached_probe_count += 1
                    return SimpleNamespace(
                        returncode=(2, 0, 2)[detached_probe_count - 1],
                        stdout="", stderr="",
                    )
                if any(value.startswith("--detach=") for value in command):
                    return SimpleNamespace(returncode=0, stdout="999\n", stderr="")
                if any(value.startswith("--attach=") for value in command):
                    return success
                if "pull" in command:
                    return failed_pull
                return success

            with patch.object(LOGGER.subprocess, "run", side_effect=run_command) as run, \
                    patch.object(LOGGER.time, "sleep"):
                session.start_perfetto()
                session.handle_logcat_line(json.dumps({
                    "source": "gpu", "event": "diagnostic_trace_start", "run_id": "run-a",
                    "protocol_version": 2,
                    "diagnostic_session_id": self.DIAGNOSTIC_SESSION_ID,
                    "requested_trace_mode": "on",
                }))
                session.handle_logcat_line(json.dumps({
                    "source": "gpu", "event": "diagnostic_trace_stop", "run_id": "run-a",
                    "protocol_version": 2,
                    "diagnostic_session_id": self.DIAGNOSTIC_SESSION_ID,
                    "requested_trace_mode": "on",
                }))
                session.handle_logcat_line(json.dumps({
                    "source": "gpu", "event": "diagnostic_trace_start", "run_id": "run-a",
                    "protocol_version": 2,
                    "diagnostic_session_id": self.DIAGNOSTIC_SESSION_ID,
                    "requested_trace_mode": "on",
                }))
                session.stop_perfetto()

            commands = [call.args[0] for call in run.call_args_list]
            self.assertEqual(1, sum(any(value.startswith("--detach=") for value in command)
                                    for command in commands))
            self.assertEqual(1, sum(any(value.startswith("--attach=") for value in command)
                                    for command in commands))
            self.assertFalse(any("kill" in command for command in commands))
            self.assertEqual(1, sum("pull" in command for command in commands))
            self.assertEqual(1, sum("rm" in command for command in commands))
            self.assertIs(session.perfetto_state, LOGGER.PerfettoState.FAILED)
            self.assertIn(session.perfetto_device_trace_path, session.capture_error)
            self.assertIn("trace was not finalized", session.capture_error)
            self.assertFalse(
                (session.run_dir / "diagnostics" /
                 f"{session.diagnostic_trace_filename}.part").exists()
            )

    def test_stale_local_trace_is_never_reused_when_current_pull_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            session = LOGGER.CaptureSession(
                "adb", None, Path(directory), 1.0, True, PERFETTO_CONFIG_PATH,
                2, self.DIAGNOSTIC_SESSION_ID,
            )
            session.run_dir = Path(directory)
            diagnostics = session.run_dir / "diagnostics"
            diagnostics.mkdir()
            stale = diagnostics / session.diagnostic_trace_filename
            stale.write_bytes(b"stale-trace")
            probe_count = 0

            def run_command(command, **_kwargs):
                nonlocal probe_count
                if any(value.startswith("--is_detached=") for value in command):
                    probe_count += 1
                    return SimpleNamespace(
                        returncode=(2, 0, 2)[probe_count - 1],
                        stdout="", stderr="",
                    )
                if any(value.startswith("--detach=") for value in command):
                    return SimpleNamespace(returncode=0, stdout="1234\n", stderr="")
                if any(value.startswith("--attach=") for value in command):
                    return SimpleNamespace(returncode=0, stdout="", stderr="")
                if "pull" in command:
                    return SimpleNamespace(returncode=1, stdout="", stderr="pull failed")
                return SimpleNamespace(returncode=0, stdout="", stderr="")

            with patch.object(LOGGER.subprocess, "run", side_effect=run_command) as run, \
                    patch.object(LOGGER.time, "sleep"):
                session.start_perfetto()
                session.stop_perfetto()
            self.assertEqual(b"stale-trace", stale.read_bytes())
            self.assertEqual(1, sum("pull" in call.args[0] for call in run.call_args_list))
            self.assertIs(session.perfetto_state, LOGGER.PerfettoState.FAILED)
            self.assertIn("pull failed", session.capture_error)

    def _forced_stop_session(self, directory):
        session = LOGGER.CaptureSession(
            "adb", None, Path(directory), 1.0, True, PERFETTO_CONFIG_PATH,
        )
        session.run_dir = Path(directory)
        (session.run_dir / "diagnostics").mkdir()
        session.perfetto_pid = "777"
        session.perfetto_state = LOGGER.PerfettoState.RUNNING
        session.perfetto_started_successfully = True
        return session

    def test_perfetto_stop_escalates_to_term_and_never_finalizes_forced_trace(self):
        with tempfile.TemporaryDirectory() as directory:
            session = self._forced_stop_session(directory)
            current_signal = None

            def run_command(command, **_kwargs):
                nonlocal current_signal
                if "-INT" in command:
                    current_signal = "INT"
                elif "-TERM" in command:
                    current_signal = "TERM"
                if "-0" in command:
                    return SimpleNamespace(
                        returncode=1 if current_signal == "TERM" else 0,
                        stdout="", stderr="",
                    )
                return SimpleNamespace(returncode=0, stdout="", stderr="")

            with patch.object(LOGGER.subprocess, "run", side_effect=run_command) as run, \
                    patch.object(LOGGER.time, "sleep"):
                session.stop_perfetto()
            commands = [call.args[0] for call in run.call_args_list]
            self.assertEqual(1, sum("-INT" in command for command in commands))
            self.assertEqual(1, sum("-TERM" in command for command in commands))
            self.assertEqual(0, sum("-KILL" in command for command in commands))
            self.assertEqual(LOGGER.PERFETTO_SIGNAL_GRACE_ATTEMPTS + 1,
                             sum("-0" in command for command in commands))
            self.assertIs(session.perfetto_state, LOGGER.PerfettoState.FAILED)
            self.assertTrue(session.perfetto_process_exited)
            self.assertIn("SIGTERM", session.capture_error)
            self.assertFalse(any((Path(directory) / "diagnostics").iterdir()))

    def test_perfetto_stop_escalates_to_kill_and_never_finalizes_forced_trace(self):
        with tempfile.TemporaryDirectory() as directory:
            session = self._forced_stop_session(directory)
            current_signal = None

            def run_command(command, **_kwargs):
                nonlocal current_signal
                for signal in ("INT", "TERM", "KILL"):
                    if f"-{signal}" in command:
                        current_signal = signal
                if "-0" in command:
                    return SimpleNamespace(
                        returncode=1 if current_signal == "KILL" else 0,
                        stdout="", stderr="",
                    )
                return SimpleNamespace(returncode=0, stdout="", stderr="")

            with patch.object(LOGGER.subprocess, "run", side_effect=run_command) as run, \
                    patch.object(LOGGER.time, "sleep"):
                session.stop_perfetto()
            commands = [call.args[0] for call in run.call_args_list]
            self.assertEqual(["-INT", "-TERM", "-KILL"], [
                command[-2] for command in commands
                if command[-2] in {"-INT", "-TERM", "-KILL"}
            ])
            self.assertIs(session.perfetto_state, LOGGER.PerfettoState.FAILED)
            self.assertTrue(session.perfetto_process_exited)
            self.assertIn("SIGKILL", session.capture_error)
            self.assertFalse(any((Path(directory) / "diagnostics").iterdir()))

    def test_perfetto_stop_has_bounded_final_failure_and_preserves_first_error(self):
        with tempfile.TemporaryDirectory() as directory:
            session = self._forced_stop_session(directory)
            session.capture_error = "first capture failure"

            def run_command(command, **_kwargs):
                return SimpleNamespace(returncode=0, stdout="", stderr="")

            with patch.object(LOGGER.subprocess, "run", side_effect=run_command) as run, \
                    patch.object(LOGGER.time, "sleep"):
                session.stop_perfetto()
            commands = [call.args[0] for call in run.call_args_list]
            self.assertEqual(3, sum(
                command[-2] in {"-INT", "-TERM", "-KILL"} for command in commands
            ))
            self.assertEqual(3 * LOGGER.PERFETTO_SIGNAL_GRACE_ATTEMPTS,
                             sum("-0" in command for command in commands))
            self.assertTrue(all(call.kwargs.get("timeout", 0) > 0
                                for call in run.call_args_list))
            self.assertIs(session.perfetto_state, LOGGER.PerfettoState.FAILED)
            self.assertFalse(session.perfetto_process_exited)
            self.assertEqual("first capture failure", session.capture_error)
            self.assertTrue(any("suppressed cleanup error" in warning and "remains alive" in warning
                                for warning in session.capture_warnings))

    def test_failed_state_cleanup_retries_termination_idempotently(self):
        with tempfile.TemporaryDirectory() as directory:
            session = self._forced_stop_session(directory)
            session.perfetto_state = LOGGER.PerfettoState.FAILED
            session.capture_error = "first capture failure"

            def run_command(command, **_kwargs):
                if "-0" in command:
                    return SimpleNamespace(returncode=1, stdout="", stderr="gone")
                return SimpleNamespace(returncode=0, stdout="", stderr="")

            with patch.object(LOGGER.subprocess, "run", side_effect=run_command) as run:
                session.cleanup_perfetto()
                session.cleanup_perfetto()
            commands = [call.args[0] for call in run.call_args_list]
            self.assertEqual(1, sum("-INT" in command for command in commands))
            self.assertEqual(1, sum("rm" in command for command in commands))
            self.assertEqual("first capture failure", session.capture_error)

    def test_basic_perfetto_methods_remain_no_op(self):
        with tempfile.TemporaryDirectory() as directory:
            session = LOGGER.CaptureSession(
                "adb", None, Path(directory), 1.0, False, PERFETTO_CONFIG_PATH
            )
            with patch.object(LOGGER.subprocess, "run") as run:
                session.start_perfetto()
                session.stop_perfetto()
                session.cleanup_perfetto()
            run.assert_not_called()
            self.assertIs(session.perfetto_state, LOGGER.PerfettoState.IDLE)

    def test_legacy_manual_diagnostic_marker_still_starts_perfetto(self):
        with tempfile.TemporaryDirectory() as directory:
            session = LOGGER.CaptureSession(
                "adb", None, Path(directory), 1.0, True, PERFETTO_CONFIG_PATH
            )
            session.run_id = "run-a"
            responses = [
                SimpleNamespace(returncode=0, stdout="", stderr=""),
                SimpleNamespace(returncode=0, stdout="5432\n", stderr=""),
                SimpleNamespace(returncode=0, stdout="", stderr=""),
            ]
            with patch.object(LOGGER.subprocess, "run", side_effect=responses) as run:
                session.handle_logcat_line(json.dumps({
                    "source": "gpu", "event": "diagnostic_trace_start",
                    "run_id": "run-a",
                }))
            self.assertIs(session.perfetto_state, LOGGER.PerfettoState.RUNNING)
            self.assertEqual("5432", session.perfetto_pid)
            self.assertEqual(
                LOGGER.LEGACY_PERFETTO_DEVICE_TRACE_PATH,
                session.perfetto_device_trace_path,
            )
            self.assertEqual(3, run.call_count)

    def test_legacy_diagnostic_perfetto_cli_flag_remains_accepted(self):
        args = LOGGER.build_parser().parse_args(["capture", "--diagnostic-perfetto"])
        self.assertEqual("on", args.diagnostic_perfetto)

    def test_diagnostic_v2_trace_off_executes_no_perfetto_command(self):
        with tempfile.TemporaryDirectory() as directory:
            session = LOGGER.CaptureSession(
                "adb", None, Path(directory), 1.0, False, Path("unused.pbtxt"),
                2, self.DIAGNOSTIC_SESSION_ID,
            )
            with patch.object(LOGGER.subprocess, "run") as run:
                session.start_perfetto()
                session.stop_perfetto()
                session.cleanup_perfetto()
            run.assert_not_called()
            self.assertEqual("off", "on" if session.diagnostic_perfetto else "off")

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

    def test_v2_gpu_file_rejects_mixed_session_and_replay(self):
        def record(sequence, event, diagnostic_id=self.DIAGNOSTIC_SESSION_ID):
            value = {
                "run_id": "r",
                "runner_session_id": "s",
                "sequence": sequence,
                "event": event,
                "protocol_version": 2,
                "diagnostic_session_id": diagnostic_id,
                "requested_trace_mode": "off",
            }
            if event == "file_summary":
                value.update(file_event_count=3, sequence_last=2)
            return value

        events = [record(0, "run_metadata"), record(1, "inference"), record(2, "file_summary")]
        LOGGER.validate_gpu_file(
            events, "r", "s", self.DIAGNOSTIC_SESSION_ID, "off"
        )
        events[1]["diagnostic_session_id"] = "44444444-4444-4444-4444-444444444444"
        with self.assertRaisesRegex(ValueError, "diagnostic_session_id"):
            LOGGER.validate_gpu_file(events, "r", "s", self.DIAGNOSTIC_SESSION_ID)

    def test_v2_gpu_file_requires_trace_mode_on_every_record(self):
        def record(sequence, event, mode="off"):
            value = {
                "run_id": "r", "runner_session_id": "s", "sequence": sequence,
                "event": event, "protocol_version": 2,
                "diagnostic_session_id": self.DIAGNOSTIC_SESSION_ID,
                "requested_trace_mode": mode,
            }
            if event == "file_summary":
                value.update(file_event_count=3, sequence_last=2)
            return value

        records = [record(0, "run_metadata"), record(1, "inference"),
                   record(2, "file_summary")]
        LOGGER.validate_gpu_file(records, "r", "s", self.DIAGNOSTIC_SESSION_ID, "off")
        records[1].pop("requested_trace_mode")
        with self.assertRaisesRegex(ValueError, "requested_trace_mode"):
            LOGGER.validate_gpu_file(records, "r", "s", self.DIAGNOSTIC_SESSION_ID, "off")
        records[1]["requested_trace_mode"] = "on"
        with self.assertRaisesRegex(ValueError, "requested_trace_mode"):
            LOGGER.validate_gpu_file(records, "r", "s", self.DIAGNOSTIC_SESSION_ID, "off")

    def test_malicious_run_id_creates_no_directory_or_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            session = LOGGER.CaptureSession(
                "adb", None, root, 1.0, False, Path("unused.pbtxt"),
                2, self.DIAGNOSTIC_SESSION_ID,
            )
            session.record_logcat({
                "source": "d1check", "event": "run_start",
                "run_id": "../escape", "mono_ns": 1,
            })
            self.assertTrue(session.stop.is_set())
            self.assertIsNone(session.run_dir)
            self.assertEqual([], list(root.iterdir()))

    def test_malicious_runner_filename_writes_nothing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "gpu").mkdir()
            session = LOGGER.CaptureSession(
                "adb", None, root, 1.0, False, Path("unused.pbtxt"),
                2, self.DIAGNOSTIC_SESSION_ID,
            )
            session.run_id = "11111111-1111-1111-1111-111111111111"
            session.run_dir = root
            with patch.object(LOGGER.subprocess, "run") as run, \
                    self.assertRaisesRegex(ValueError, "unsafe|does not match"):
                session.pull_runner_file({
                    "file_path": (
                        f"/storage/emulated/0/Android/data/{LOGGER.RUNNER_PACKAGE}/files/"
                        "diagnostics-v2/../escape.jsonl"
                    ),
                    "runner_session_id": "runner",
                })
            run.assert_not_called()
            self.assertEqual([], list((root / "gpu").iterdir()))

    def test_noncanonical_session_and_trace_filename_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "canonical"):
                LOGGER.CaptureSession(
                    "adb", None, Path(directory), 1.0, False, Path("unused.pbtxt"),
                    2, "AAAAAAAA-AAAA-AAAA-AAAA-AAAAAAAAAAAA",
                )
            run_dir = Path(directory)
            (run_dir / "diagnostics").mkdir()
            metadata = {
                "requested_trace_mode": "on",
                "diagnostic_trace_session_id": self.DIAGNOSTIC_SESSION_ID,
                "diagnostic_trace_filename": "../escape.perfetto-trace",
                **self.detached_control_metadata(),
            }
            with self.assertRaisesRegex(ValueError, "filename"):
                LOGGER.validate_diagnostic_trace_artifacts(
                    run_dir, metadata, self.DIAGNOSTIC_SESSION_ID
                )

    def test_v2_logcat_marker_from_other_session_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            session = LOGGER.CaptureSession(
                "adb", None, Path(directory), 1.0, False, Path("unused.pbtxt"),
                2, self.DIAGNOSTIC_SESSION_ID,
            )
            session.run_id = "run-a"
            session.handle_logcat_line(json.dumps({
                "source": "gpu",
                "event": "load_start",
                "run_id": "run-a",
                "protocol_version": 2,
                "diagnostic_session_id": "44444444-4444-4444-4444-444444444444",
                "requested_trace_mode": "off",
            }))
            self.assertTrue(session.stop.is_set())
            self.assertIn("protocol/session/trace-mode mismatch", session.capture_error)

    def test_trace_off_rejects_trace_and_trace_on_rejects_foreign_trace(self):
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory)
            diagnostics = run_dir / "diagnostics"
            diagnostics.mkdir()
            metadata = {
                "requested_trace_mode": "off",
                "diagnostic_trace_session_id": self.DIAGNOSTIC_SESSION_ID,
                "diagnostic_perfetto_control_mode": None,
                "diagnostic_perfetto_session_key": None,
                "diagnostic_perfetto_start_pid": None,
                "diagnostic_perfetto_control_results": {},
                "diagnostic_perfetto_readiness_semantics": None,
                "diagnostic_perfetto_pid_control": None,
                "diagnostic_perfetto_config_write_into_file": None,
                "diagnostic_perfetto_config_duration_ms": None,
            }
            foreign = diagnostics / "d1check-foreign.perfetto-trace"
            foreign.write_bytes(b"foreign")
            with self.assertRaisesRegex(ValueError, "trace-off"):
                LOGGER.validate_diagnostic_trace_artifacts(
                    run_dir, metadata, self.DIAGNOSTIC_SESSION_ID
                )
            metadata.update({
                "requested_trace_mode": "on",
                "diagnostic_trace_filename": (
                    f"d1check-{self.DIAGNOSTIC_SESSION_ID}.perfetto-trace"
                ),
                "diagnostic_trace_size_bytes": 7,
                "diagnostic_trace_sha256": LOGGER.hashlib.sha256(b"foreign").hexdigest(),
                **self.detached_control_metadata(),
            })
            with self.assertRaisesRegex(ValueError, "mixed or missing"):
                LOGGER.validate_diagnostic_trace_artifacts(
                    run_dir, metadata, self.DIAGNOSTIC_SESSION_ID
                )

    def test_trace_on_rejects_detached_session_key_mixing(self):
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory)
            diagnostics = run_dir / "diagnostics"
            diagnostics.mkdir()
            trace = diagnostics / (
                f"d1check-{self.DIAGNOSTIC_SESSION_ID}.perfetto-trace"
            )
            trace.write_bytes(b"current-trace")
            metadata = {
                "requested_trace_mode": "on",
                "diagnostic_trace_session_id": self.DIAGNOSTIC_SESSION_ID,
                "diagnostic_trace_filename": trace.name,
                "diagnostic_trace_size_bytes": trace.stat().st_size,
                "diagnostic_trace_sha256": LOGGER.sha256_file(trace),
                **self.detached_control_metadata(),
            }
            LOGGER.validate_diagnostic_trace_artifacts(
                run_dir, metadata, self.DIAGNOSTIC_SESSION_ID
            )
            metadata["diagnostic_perfetto_session_key"] = (
                "d1check-44444444-4444-4444-4444-444444444444"
            )
            with self.assertRaisesRegex(ValueError, "session key"):
                LOGGER.validate_diagnostic_trace_artifacts(
                    run_dir, metadata, self.DIAGNOSTIC_SESSION_ID
                )

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
        evidence = LOGGER.delegate_evidence(self.A24_GPU_LOG, diagnostic_v2=True)
        self.assertEqual(31, evidence["replaced_nodes"])
        self.assertEqual(31, evidence["total_nodes"])
        self.assertEqual(1, evidence["gpu_delegate_kernel_count"])
        self.assertTrue(evidence["full_delegate"])
        self.assertEqual("OPENCL", evidence["actual_backend_observed"])
        self.assertIn("not_physical", evidence["gpu_delegate_kernel_count_semantics"])

    def test_v1_delegate_evidence_schema_has_no_v2_backend_fields(self):
        evidence = LOGGER.delegate_evidence(self.A24_GPU_LOG)
        self.assertNotIn("actual_backend_observed", evidence)
        self.assertNotIn("gpu_delegate_kernel_count_semantics", evidence)

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

    def test_runner_fallback_preserves_v1_root_and_selects_diagnostic_v2_root(self):
        completed = LOGGER.subprocess.CompletedProcess
        with tempfile.TemporaryDirectory() as directory:
            session = LOGGER.CaptureSession(
                "adb", None, Path(directory), 1.0, False, Path("unused.pbtxt")
            )
            session.run_id = "run-a"
            v1_responses = [
                completed([], 0, "/storage/emulated/0/Android/data/pkg/files/runs/gpu-events-run-a-v1.jsonl\n", ""),
                completed([], 1, "", "missing"),
            ]
            with patch.object(LOGGER.subprocess, "run", side_effect=v1_responses) as run:
                self.assertIn("/files/runs/", session.discover_runner_paths()[0])
                self.assertEqual(2, run.call_count)
            session.runner_output_directories = ("diagnostics-v2",)
            v2_responses = [
                completed([], 0, "/storage/emulated/0/Android/data/pkg/files/diagnostics-v2/gpu-events-run-a-v2.jsonl\n", ""),
                completed([], 1, "", "missing"),
            ]
            with patch.object(LOGGER.subprocess, "run", side_effect=v2_responses) as run:
                self.assertIn("/files/diagnostics-v2/", session.discover_runner_paths()[0])
                self.assertEqual(2, run.call_count)


if __name__ == "__main__":
    unittest.main()
