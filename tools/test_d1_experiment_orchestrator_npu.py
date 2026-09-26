"""NPU path of d1_experiment_orchestrator (npu-runner, S26). Separate file so the existing
CPU/GPU orchestrator tests stay untouched."""
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
SPEC = importlib.util.spec_from_file_location("d1_experiment_orchestrator_npu_test", MODULE_PATH)
assert SPEC and SPEC.loader
ORCH = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = ORCH
SPEC.loader.exec_module(ORCH)

REPO = Path(__file__).resolve().parents[1]
G4_FINAL_SUMMARY = (
    REPO / "s26" / "npu" / "results"
    / "G4_summary_2026-09-24506_1569_WIRELESS_ACPLUGGED_NPU_GATE_FINAL.json"
)
MOBILENET_AOT_SHA = "1415b2c87d01b67a9380b8f912e2b4ef4561502105b06f313332c97c1c8cb5cf"


def completed(stdout="", returncode=0):
    return subprocess.CompletedProcess([], returncode, stdout, "")


class ScriptedAdb:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def run(self, arguments, timeout=30, check=True):
        self.calls.append(list(arguments))
        if not self.responses:
            raise AssertionError(f"unexpected ADB call: {arguments}")
        return self.responses.pop(0)


def npu_summary(run_id="npuq-1", **overrides):
    value = {
        "schema": "npu-runner-smoke-v1", "run_id": run_id, "engine": "litert-compiled-model",
        "accelerator_requested": "NPU", "model": ORCH.DEFAULT_NPU_MODEL_ASSET,
        "model_sha256": MOBILENET_AOT_SHA, "input_spec": "lcg-unit", "status": "OK",
        "device_model": "SM-S942N",
        "quality_gate": {
            "version": "npu-quality-gate-v1", "n": 32, "bit_identical_count": 0,
            "bit_identical_to_cpu": False, "argmax_agreement": "32/32",
            "cosine_min": 0.99971543, "verdict": "PASS",
        },
    }
    value.update(overrides)
    return value


class NpuPlanTest(unittest.TestCase):
    def test_cpu_and_gpu_conditions_are_unchanged(self):
        self.assertEqual(
            [
                {"condition_id": "cpu-t04-d100", "resource": "CPU", "cpu_threads": 4,
                 "duty_cycle_percent": 100},
                {"condition_id": "gpu-d100", "resource": "GPU", "cpu_threads": None,
                 "duty_cycle_percent": 100},
            ],
            ORCH.build_conditions(["CPU", "GPU"], [4], [100]),
        )

    def test_npu_condition(self):
        self.assertEqual(
            [{"condition_id": "npu-d025", "resource": "NPU", "cpu_threads": None,
              "duty_cycle_percent": 25}],
            ORCH.build_conditions(["npu"], [4], [25]),
        )

    def test_unknown_resource_is_rejected(self):
        with self.assertRaises(ValueError):
            ORCH.build_conditions(["DSP"], [4], [100])

    def test_three_resource_plan_and_manifest_validation(self):
        args = ORCH.build_parser().parse_args(
            ["--resources", "CPU", "GPU", "NPU", "--repeat", "2", "--seed", "7"]
        )
        config = ORCH.experiment_config(args)
        plan = ORCH.build_plan(
            args.resources, args.repeat, args.seed,
            config["cpu_thread_levels"], config["duty_cycles"],
        )
        self.assertEqual(6, len(plan))
        self.assertEqual({"CPU": 2, "GPU": 2, "NPU": 2},
                         {r: sum(s["resource"] == r for s in plan) for r in ("CPU", "GPU", "NPU")})
        self.assertFalse(ORCH.upgrade_and_validate_manifest_plan({"runs": plan}, config))


class NpuIntentTest(unittest.TestCase):
    def test_cpu_and_gpu_intents_are_unchanged(self):
        tail = [
            "--es", "d1_limit_mode", "DURATION", "--el", "d1_duration_s", "60",
            "--ei", "d1_warmup_count", "20", "--es", "d1_run_id", "run",
            "--es", "d1_command_id", "command", "--es", "d1_experiment_mode", "BASIC",
            "--ei", "d1_duty_cycle_percent", "100", "--ef", "d1_duty_cycle_period_s", "10.0",
        ]
        head = ["shell", "am", "start", "-W", "-n", ORCH.RUNNER_ACTIVITY,
                "--ez", "d1_auto_start", "true"]
        self.assertEqual(
            head + ["--es", "d1_resource", "CPU", "--ei", "d1_cpu_threads", "4"] + tail,
            ORCH.runner_intent_arguments("CPU", 4, 60, 20, "run", "command"),
        )
        self.assertEqual(
            head + ["--es", "d1_resource", "GPU", "--es", "d1_gpu_profile",
                    ORCH.DEFAULT_GPU_PROFILE] + tail,
            ORCH.runner_intent_arguments("GPU", None, 60, 20, "run", "command"),
        )

    def test_npu_intent_targets_npu_runner(self):
        arguments = ORCH.runner_intent_arguments(
            "NPU", None, 60, 20, "run", "command", 50, 10.0, ORCH.DEFAULT_GPU_PROFILE,
            npu_model_asset="models/x_Samsung_E9965.tflite",
        )
        self.assertEqual(ORCH.NPU_RUNNER_ACTIVITY, arguments[arguments.index("-n") + 1])
        self.assertIn("d1_npu_model_asset", arguments)
        self.assertEqual("models/x_Samsung_E9965.tflite",
                         arguments[arguments.index("d1_npu_model_asset") + 1])
        self.assertNotIn("d1_gpu_profile", arguments)
        self.assertNotIn("d1_cpu_threads", arguments)
        self.assertEqual("50", arguments[arguments.index("d1_duty_cycle_percent") + 1])

    def test_package_and_logger_helpers(self):
        for resource in ("CPU", "GPU"):
            self.assertEqual(ORCH.RUNNER_PACKAGE, ORCH.runner_package_for(resource))
            self.assertEqual(ORCH.REMOTE_RUNNER_DIRECTORY, ORCH.remote_runner_directory_for(resource))
            self.assertEqual([], ORCH.npu_logger_capture_arguments(resource))
            self.assertEqual({}, ORCH.npu_runner_intent_kwargs(resource, SimpleNamespace()))
            self.assertEqual(30, ORCH.logger_exit_timeout_seconds(resource))
        self.assertEqual(300, ORCH.logger_exit_timeout_seconds("NPU"))
        self.assertEqual(ORCH.NPU_RUNNER_PACKAGE, ORCH.runner_package_for("NPU"))
        self.assertEqual(ORCH.NPU_REMOTE_RUNNER_DIRECTORY, ORCH.remote_runner_directory_for("NPU"))
        self.assertEqual(
            ["--runner-package", ORCH.NPU_RUNNER_PACKAGE, "--extra-logcat-tag", "litert:I"],
            ORCH.npu_logger_capture_arguments("NPU"),
        )

    def test_quality_intent_uses_smoke_protocol(self):
        arguments = ORCH.npu_quality_intent_arguments(
            "npuq-1", ORCH.DEFAULT_NPU_MODEL_ASSET, ORCH.DEFAULT_NPU_REFERENCE_ASSET, "lcg-unit",
        )
        self.assertEqual(ORCH.NPU_RUNNER_ACTIVITY, arguments[arguments.index("-n") + 1])
        self.assertEqual("32", arguments[arguments.index("quality_n") + 1])
        self.assertEqual("NPU", arguments[arguments.index("accelerator") + 1])
        self.assertEqual(
            ["exec-out", "run-as", ORCH.NPU_RUNNER_PACKAGE, "cat",
             "files/npu-runner-v1/summary-npuq-1.json"],
            ORCH.npu_quality_summary_arguments("npuq-1"),
        )


class NpuRemoteProbeTest(unittest.TestCase):
    def test_npu_probe_lists_the_npu_runner_directory(self):
        adb = ScriptedAdb([completed("")])
        probe = ORCH.probe_remote_runner(adb, "run-a", ORCH.NPU_REMOTE_RUNNER_DIRECTORY)
        self.assertEqual("not_found", probe.state)
        self.assertEqual(["shell", "ls", "-1", ORCH.NPU_REMOTE_RUNNER_DIRECTORY], adb.calls[0])

    def test_default_probe_still_lists_benchmark_runner(self):
        adb = ScriptedAdb([completed("")])
        ORCH.probe_remote_runner(adb, "run-a")
        self.assertEqual(["shell", "ls", "-1", ORCH.REMOTE_RUNNER_DIRECTORY], adb.calls[0])


class NpuQualityEvaluationTest(unittest.TestCase):
    def test_passing_summary(self):
        result = ORCH.evaluate_npu_quality_summary(npu_summary(), "npuq-1",
                                                   ORCH.DEFAULT_NPU_MODEL_ASSET)
        self.assertEqual("passed", result["status"], result["failure_reasons"])
        self.assertEqual(MOBILENET_AOT_SHA, result["candidate_model_sha256"])
        self.assertTrue(ORCH.accuracy_policy_allows_slots("required", result["status"]))

    def test_each_criterion_fails_closed(self):
        gate = npu_summary()["quality_gate"]
        cases = {
            "bit_identical_to_cpu": {"quality_gate": {**gate, "bit_identical_to_cpu": True}},
            "argmax_disagreement": {"quality_gate": {**gate, "argmax_agreement": "31/32"}},
            "cosine_below_threshold": {"quality_gate": {**gate, "cosine_min": 0.9899}},
            "quality_gate_n_mismatch": {"quality_gate": {**gate, "n": 3, "argmax_agreement": "3/3"}},
            "runner_verdict_not_pass": {"quality_gate": {**gate, "verdict": "NOT_APPLICABLE"}},
            "quality_gate_missing": {"quality_gate": None},
            "model_sha256_missing": {"model_sha256": None},
            "model_asset_mismatch": {"model": "models/other.tflite"},
            "accelerator_not_npu": {"accelerator_requested": "CPU"},
            "runner_status_not_ok": {"status": "FAILED"},
            "run_id_mismatch": {"run_id": "other"},
        }
        for reason, override in cases.items():
            with self.subTest(reason=reason):
                result = ORCH.evaluate_npu_quality_summary(
                    npu_summary(**override), "npuq-1", ORCH.DEFAULT_NPU_MODEL_ASSET,
                )
                self.assertEqual("failed", result["status"])
                self.assertIn(reason, result["failure_reasons"])
                self.assertFalse(ORCH.accuracy_policy_allows_slots("required", result["status"]))

    def test_real_g4_summary_passes_every_criterion_except_missing_model_hash(self):
        """The 9/24 05:06 run predates model_sha256 in the summary; all gate criteria hold."""
        summary = json.loads(G4_FINAL_SUMMARY.read_text(encoding="utf-8"))
        result = ORCH.evaluate_npu_quality_summary(
            summary, summary["run_id"], ORCH.DEFAULT_NPU_MODEL_ASSET,
        )
        self.assertEqual(["model_sha256_missing"], result["failure_reasons"])


class NpuConfigAndCliTest(unittest.TestCase):
    def test_cpu_gpu_config_has_no_npu_block(self):
        self.assertNotIn("npu", ORCH.experiment_config(ORCH.build_parser().parse_args([])))

    def test_npu_config_block(self):
        config = ORCH.experiment_config(ORCH.build_parser().parse_args(["--resources", "NPU"]))
        self.assertEqual(ORCH.NPU_RUNNER_PACKAGE, config["npu"]["runner_package"])
        self.assertEqual(32, config["npu"]["quality_gate"]["n"])
        self.assertEqual("CPU:" + ORCH.DEFAULT_NPU_REFERENCE_ASSET,
                         config["npu"]["quality_gate"]["reference"])

    def test_coordinate_input_is_not_a_32_sample_gate_input(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            ORCH.build_parser().parse_args(
                ["--resources", "NPU", "--npu-input-spec", "coordinate-rgb-classification"]
            )

    def test_dry_run_routes_npu_slots_to_npu_runner(self):
        args = ORCH.build_parser().parse_args(["--resources", "CPU", "NPU", "--dry-run"])
        payload = ORCH.dry_run_payload(args)
        by_resource = {command["resource"]: command for command in payload["commands"]}
        self.assertIn(ORCH.NPU_RUNNER_PACKAGE, by_resource["NPU"]["force_stop"])
        self.assertIn(ORCH.NPU_RUNNER_ACTIVITY, by_resource["NPU"]["runner"])
        self.assertIn("--runner-package", by_resource["NPU"]["logger_capture_extra"])
        self.assertIn(ORCH.RUNNER_PACKAGE, by_resource["CPU"]["force_stop"])
        self.assertNotIn("logger_capture_extra", by_resource["CPU"])


class NpuValidateResultTest(unittest.TestCase):
    def write_run(self, root: Path, resource: str, formal_npu_valid):
        run_dir = root / "run-a"
        (run_dir / "merged").mkdir(parents=True)
        (run_dir / "gpu").mkdir()
        summary = {"run_id": "run-a", "resource": resource, "formal_npu_valid": formal_npu_valid}
        (run_dir / "merged" / "summary.json").write_text(json.dumps(summary), "utf-8")
        (run_dir / "metadata.json").write_text("{}", "utf-8")
        events = [
            {"event": "run_metadata", "run_id": "run-a", "resource": resource},
            {"event": "file_summary", "status": "ok"},
        ]
        (run_dir / "gpu" / "gpu-events-run-a-s1.jsonl").write_text(
            "\n".join(json.dumps(e) for e in events) + "\n", "utf-8")
        return run_dir

    def test_formal_npu_valid_is_required_for_npu_formal_runs(self):
        for flag in (True, False, None):
            with self.subTest(flag=flag), tempfile.TemporaryDirectory() as directory:
                run_dir = self.write_run(Path(directory), "NPU", flag)
                result = ORCH.validate_result(run_dir, "NPU", None, 60, 20, "run-a", "c", "formal")
                self.assertIs(flag is True, result["checks"]["formal_npu_valid"])
                self.assertEqual(flag is not True, "formal_npu_valid" in result["failed_checks"])
                self.assertNotIn("formal_gpu_valid", result["checks"])

    def test_pilot_and_gpu_runs_have_no_npu_check(self):
        with tempfile.TemporaryDirectory() as directory:
            run_dir = self.write_run(Path(directory), "NPU", False)
            self.assertNotIn("formal_npu_valid", ORCH.validate_result(
                run_dir, "NPU", None, 60, 20, "run-a", "c", "pilot")["checks"])
        with tempfile.TemporaryDirectory() as directory:
            run_dir = self.write_run(Path(directory), "GPU", None)
            self.assertNotIn("formal_npu_valid", ORCH.validate_result(
                run_dir, "GPU", None, 60, 20, "run-a", "c", "formal")["checks"])


class NpuQualityPreflightTest(unittest.TestCase):
    def orchestrator(self, directory: Path, responses, policy="required"):
        args = ORCH.build_parser().parse_args(
            ["--resources", "NPU", "--mode", "formal", "--accuracy-preflight", policy]
        )
        manifest = {"config": ORCH.experiment_config(args), "runs": []}
        orchestrator = ORCH.ExperimentOrchestrator(args, manifest, directory / "experiment_manifest.json")
        orchestrator.adb = ScriptedAdb(responses)
        return orchestrator

    def test_passing_preflight_is_recorded_and_reused(self):
        with tempfile.TemporaryDirectory() as directory, \
                mock.patch.object(ORCH.time, "sleep"), \
                mock.patch.object(ORCH.uuid, "uuid4", return_value="1"):
            orchestrator = self.orchestrator(Path(directory), [
                completed(), completed(), completed(json.dumps(npu_summary())), completed(),
            ])
            result = orchestrator.ensure_npu_quality_preflight()
            self.assertEqual("passed", result["status"], result["failure_reasons"])
            saved = json.loads((Path(directory) / "experiment_manifest.json").read_text("utf-8"))
            self.assertEqual("passed", saved["npu_quality_preflight"]["status"])
            calls = orchestrator.adb.calls
            self.assertEqual(["shell", "am", "force-stop", ORCH.NPU_RUNNER_PACKAGE], calls[0])
            self.assertIn(ORCH.NPU_RUNNER_ACTIVITY, calls[1])
            self.assertEqual(ORCH.npu_quality_summary_arguments("npuq-1"), calls[2])
            # a second call reuses the passed result without touching the device
            self.assertIs(result, orchestrator.ensure_npu_quality_preflight())
            self.assertEqual(4, len(calls))

    def test_missing_summary_times_out_as_failed(self):
        clock = {"now": 0.0}

        def monotonic():
            clock["now"] += 100.0
            return clock["now"]

        with tempfile.TemporaryDirectory() as directory, \
                mock.patch.object(ORCH.time, "sleep"), \
                mock.patch.object(ORCH.time, "monotonic", side_effect=monotonic):
            orchestrator = self.orchestrator(Path(directory), [
                completed(), completed(), completed("", 1), completed(),
            ])
            result = orchestrator.ensure_npu_quality_preflight()
        self.assertEqual("failed", result["status"])
        self.assertEqual(["summary_timeout"], result["failure_reasons"])

    def test_policy_off_does_not_touch_the_device(self):
        with tempfile.TemporaryDirectory() as directory:
            orchestrator = self.orchestrator(Path(directory), [], policy="off")
            orchestrator.args.mode = "pilot"
            self.assertEqual("not_run", orchestrator.ensure_npu_quality_preflight()["status"])


EFFICIENTNET_AOT_SHA = "311e4aac8fa1d8def4e13359c731ddc1c92f4c9ff7074e0d3860b036df8b2a31"


class NpuUnlockOptionsTest(unittest.TestCase):
    """2026-09-26 additive NPU options: absent = old Intent/config, present = new extras only."""

    def parse(self, *extra):
        return ORCH.build_parser().parse_args(["--resources", "NPU", "--dry-run", *extra])

    def intent(self, args):
        return ORCH.runner_intent_arguments(
            "NPU", None, 60, 20, "run", "cmd", 100, 10.0, args.gpu_profile,
            **ORCH.npu_runner_intent_kwargs("NPU", args),
        )

    def test_defaults_send_no_new_extras_and_add_no_config_keys(self):
        args = self.parse()
        sent = self.intent(args)
        for key in ("d1_npu_model_path", "d1_npu_input_spec", "d1_npu_accelerator", "d1_npu_run_only_span"):
            self.assertNotIn(key, sent)
        config = ORCH.npu_config(args)
        for key in ("model_path", "model_expected", "timed_input_spec", "timed_accelerator",
                    "run_only_span", "diagnostic_logcat_tags"):
            self.assertNotIn(key, config)
        self.assertNotIn("reference_path", config["quality_gate"])
        self.assertEqual(["--runner-package", ORCH.NPU_RUNNER_PACKAGE, "--extra-logcat-tag", "litert:I"],
                         ORCH.npu_logger_capture_arguments("NPU"))

    def test_efficientnet_timed_run_sends_asset_and_input_spec_and_records_sha(self):
        args = self.parse("--npu-model-asset", "models/efficientnet_lite0_Samsung_E9965.tflite",
                          "--npu-timed-input-spec", "lcg-rgb-127-128", "--npu-input-spec", "lcg-rgb-127-128")
        sent = self.intent(args)
        self.assertEqual("models/efficientnet_lite0_Samsung_E9965.tflite",
                         sent[sent.index("d1_npu_model_asset") + 1])
        self.assertEqual("lcg-rgb-127-128", sent[sent.index("d1_npu_input_spec") + 1])
        config = ORCH.npu_config(args)
        self.assertEqual(EFFICIENTNET_AOT_SHA, config["model_expected"]["sha256"])
        self.assertEqual(10_033_376, config["model_expected"]["size_bytes"])
        self.assertEqual("lcg-rgb-127-128", config["quality_gate"]["input_spec"])

    def test_device_model_path_requires_declared_sha_and_size(self):
        with self.assertRaises(ValueError):
            ORCH.validate_cli(self.parse("--npu-model-path", "/data/local/tmp/m.tflite"))
        args = self.parse("--npu-model-path", "/data/local/tmp/m.tflite",
                          "--npu-model-sha256", "a" * 64, "--npu-model-size", "123")
        sent = self.intent(args)
        self.assertEqual("/data/local/tmp/m.tflite", sent[sent.index("d1_npu_model_path") + 1])
        self.assertEqual("a" * 64, ORCH.npu_config(args)["model_expected"]["sha256"])

    def test_cpu_is_a_single_labelled_accelerator(self):
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            self.parse("--npu-accelerator", "NPU,CPU")
        args = self.parse("--npu-accelerator", "CPU", "--npu-run-only-span")
        sent = self.intent(args)
        self.assertEqual("CPU", sent[sent.index("d1_npu_accelerator") + 1])
        index = sent.index("d1_npu_run_only_span")
        self.assertEqual(("--ez", "true"), (sent[index - 1], sent[index + 1]))
        config = ORCH.npu_config(args)
        self.assertEqual("cpu_compiled_model", config["timed_resource_label"])

    def test_diagnostic_capture_and_file_reference_are_opt_in(self):
        self.assertEqual(
            ["litert:I", "litert:V", "tflite:V", "TfLite:V"],
            [a for a in ORCH.npu_logger_capture_arguments("NPU", True) if ":" in a],
        )
        self.assertEqual([], ORCH.npu_logger_capture_arguments("CPU", True))
        old = ORCH.npu_quality_intent_arguments("r", "m.tflite", "ref.tflite", "lcg-unit")
        new = ORCH.npu_quality_intent_arguments("r", "m.tflite", "ref.tflite", "lcg-unit",
                                                reference_path="/data/local/tmp/ref.tflite")
        self.assertNotIn("ref_model_path", old)
        self.assertEqual("/data/local/tmp/ref.tflite", new[new.index("ref_model_path") + 1])
        self.assertEqual(old[-4:], new[-4:])


if __name__ == "__main__":
    unittest.main()
