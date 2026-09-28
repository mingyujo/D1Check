"""P2 (2026-09-28) additions to d1_experiment_orchestrator: CompiledModel GPU slots, npu-runner span cap,
chain mode, runner/logger timeout options, and the NPU emergency-stop package fix.
A separate file so the existing orchestrator tests stay byte-for-byte untouched."""
import base64
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parent
ARTIFACTS = REPO / "npu-runner" / "build" / "npu-roundtrip"
KOTLIN_CONFIG = REPO / "npu-runner" / "src" / "main" / "java" / "NpuRunConfig.kt"


def load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, TOOLS / filename)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


ORCH = load("d1_experiment_orchestrator_p2_test", "d1_experiment_orchestrator.py")
ORIGINAL = "models/mobilenet_v1_1.0_224.tflite"
AOT = ORCH.DEFAULT_NPU_MODEL_ASSET


def parse(*argv):
    return ORCH.build_parser().parse_args(list(argv))


def chain_file(directory: str, segments, prepare="per_segment") -> Path:
    path = Path(directory) / "chain.json"
    path.write_text(json.dumps({
        "schema": "d1-npu-chain-v1", "chain_id": "test_chain", "model_prepare": prepare,
        "segments": segments,
    }, indent=2), "utf-8")
    return path


GPU_D10 = {"accelerator": "GPU", "model": ORIGINAL, "input_spec": "lcg-unit", "duty": 10, "duration_s": 60}
GPU_D100 = {"accelerator": "GPU", "model": ORIGINAL, "input_spec": "lcg-unit", "duty": 100, "duration_s": 240}
NPU_D100 = {"accelerator": "NPU", "model": AOT, "input_spec": "lcg-unit", "duty": 100, "duration_s": 60}


class DefaultsAreThePreviousBehaviourTest(unittest.TestCase):
    def test_runner_timeout_default_is_the_old_formula_on_a_grid(self):
        for duration in (1, 60, 165, 600, 1300, 3600):
            for warmup in (0, 20, 1800, 5000, 10000):
                args = parse("--duration", str(duration), "--warmup", str(warmup))
                self.assertEqual(duration + 180 + min(warmup * 2, 3600), ORCH.runner_timeout_seconds(args))
        self.assertEqual(1500.0, ORCH.runner_timeout_seconds(parse("--runner-timeout-seconds", "1500")))

    def test_logger_exit_timeout_default_is_the_old_constant(self):
        args = parse()
        self.assertEqual(30, ORCH.logger_exit_timeout_for(args, "CPU"))
        self.assertEqual(30, ORCH.logger_exit_timeout_for(args, "GPU"))
        self.assertEqual(300, ORCH.logger_exit_timeout_for(args, "NPU"))
        self.assertEqual(2400.0, ORCH.logger_exit_timeout_for(parse("--logger-exit-timeout-seconds", "2400"), "NPU"))

    def test_analyze_timeout_default_is_the_old_constant(self):
        self.assertEqual(120, ORCH.analyze_timeout_seconds(parse()))
        self.assertEqual(600.0, ORCH.analyze_timeout_seconds(parse("--analyze-timeout-seconds", "600")))

    def test_configs_and_intents_carry_no_new_keys_without_the_options(self):
        for argv in ([], ["--resources", "NPU"], ["--resources", "NPU", "--npu-accelerator", "CPU"]):
            config = ORCH.experiment_config(parse(*argv))
            for key in ("runner_timeout_seconds", "logger_exit_timeout_seconds", "analyze_timeout_seconds",
                        "logger_keep_files_open"):
                self.assertNotIn(key, config)
            for key in ("chain", "max_inference_spans", "timed_gpu_precision"):
                self.assertNotIn(key, config.get("npu", {}))
        intent = ORCH.runner_intent_arguments(
            "NPU", None, 60, 20, "run", "command", 100, 10.0,
            **ORCH.npu_runner_intent_kwargs("NPU", parse("--resources", "NPU")),
        )
        for extra in ("d1_npu_gpu_precision", "d1_max_inference_spans", "d1_npu_chain_b64", "d1_npu_chain_sha256"):
            self.assertNotIn(extra, intent)

    def test_cpu_compiled_label_is_unchanged(self):
        config = ORCH.experiment_config(parse("--resources", "NPU", "--npu-accelerator", "CPU"))
        self.assertEqual("cpu_compiled_model", config["npu"]["timed_resource_label"])

    def test_default_quality_gate_intent_and_evaluation_are_unchanged(self):
        intent = ORCH.npu_quality_intent_arguments("q", AOT, ORIGINAL, "lcg-unit")
        self.assertEqual("NPU", intent[intent.index("accelerator") + 1])
        summary = {"schema": "npu-runner-smoke-v1", "run_id": "q", "status": "OK", "accelerator_requested": "NPU",
                   "model": AOT, "model_sha256": "1" * 64,
                   "quality_gate": {"version": "npu-quality-gate-v1", "n": 32, "bit_identical_to_cpu": False,
                                    "argmax_agreement": "32/32", "cosine_min": 0.999, "verdict": "PASS"}}
        result = ORCH.evaluate_npu_quality_summary(summary, "q", AOT)
        self.assertEqual("passed", result["status"])
        self.assertNotIn("candidate_accelerator", result)


class GpuAcceleratorTest(unittest.TestCase):
    def test_gpu_slot_intent_and_config(self):
        args = parse("--resources", "NPU", "--npu-accelerator", "GPU", "--npu-model-asset", ORIGINAL,
                     "--npu-gpu-precision", "FP32", "--accuracy-preflight", "off")
        ORCH.validate_cli(args)
        intent = ORCH.runner_intent_arguments(
            "NPU", None, 60, 20, "run", "command", 100, 10.0, **ORCH.npu_runner_intent_kwargs("NPU", args))
        self.assertEqual("GPU", intent[intent.index("d1_npu_accelerator") + 1])
        self.assertEqual("FP32", intent[intent.index("d1_npu_gpu_precision") + 1])
        npu = ORCH.experiment_config(args)["npu"]
        self.assertEqual("gpu_compiled_model", npu["timed_resource_label"])
        self.assertEqual("FP32", npu["timed_gpu_precision"])

    def test_gpu_needs_the_original_model_and_precision_needs_gpu(self):
        for argv in (
            ["--resources", "NPU", "--npu-accelerator", "GPU"],                       # default AOT model
            ["--resources", "NPU", "--npu-gpu-precision", "FP32"],                     # precision without GPU
            ["--resources", "NPU", "--npu-accelerator", "CPU", "--npu-gpu-precision", "FP16"],
        ):
            with self.subTest(argv=argv), self.assertRaises(ORCH.OrchestratorError):
                ORCH.validate_cli(parse(*argv, "--accuracy-preflight", "off"))

    def test_gpu_quality_gate_runs_the_gpu_candidate(self):
        intent = ORCH.npu_quality_intent_arguments("q", ORIGINAL, ORIGINAL, "lcg-unit", accelerator="GPU")
        self.assertEqual("GPU", intent[intent.index("accelerator") + 1])
        summary = {"schema": "npu-runner-smoke-v1", "run_id": "q", "status": "OK", "accelerator_requested": "GPU",
                   "model": ORIGINAL, "model_sha256": "2" * 64,
                   "quality_gate": {"version": "npu-quality-gate-v1", "n": 32, "bit_identical_to_cpu": False,
                                    "argmax_agreement": "32/32", "cosine_min": 0.9999, "verdict": "PASS"}}
        self.assertEqual("passed", ORCH.evaluate_npu_quality_summary(summary, "q", ORIGINAL, accelerator="GPU")["status"])
        # a GPU candidate that is bit-identical to CPU means it ran on CPU: same rule as NPU
        cpu_like = json.loads(json.dumps(summary))
        cpu_like["quality_gate"]["bit_identical_to_cpu"] = True
        result = ORCH.evaluate_npu_quality_summary(cpu_like, "q", ORIGINAL, accelerator="GPU")
        self.assertIn("bit_identical_to_cpu", result["failure_reasons"])
        self.assertIn("accelerator_not_gpu",
                      ORCH.evaluate_npu_quality_summary(dict(summary, accelerator_requested="NPU"), "q",
                                                        ORIGINAL, accelerator="GPU")["failure_reasons"])

    def test_gpu_gate_uses_the_timed_runs_precision(self):
        plain = ORCH.npu_quality_intent_arguments("q", ORIGINAL, ORIGINAL, "lcg-unit", accelerator="GPU")
        self.assertNotIn("gpu_precision", plain)
        fp32 = ORCH.npu_quality_intent_arguments("q", ORIGINAL, ORIGINAL, "lcg-unit", accelerator="GPU",
                                                 gpu_precision="FP32")
        self.assertEqual("FP32", fp32[fp32.index("gpu_precision") + 1])
        # the Intent tail (run_id, autofinish) stays last, so the runner reads every extra
        self.assertEqual(["--ez", "autofinish", "true"], fp32[-3:])
        summary = {"schema": "npu-runner-smoke-v1", "run_id": "q", "status": "OK", "accelerator_requested": "GPU",
                   "model": ORIGINAL, "model_sha256": "2" * 64, "gpu_precision": "FP32",
                   "quality_gate": {"version": "npu-quality-gate-v1", "n": 32, "bit_identical_to_cpu": False,
                                    "argmax_agreement": "32/32", "cosine_min": 0.9999, "verdict": "PASS"}}
        passed = ORCH.evaluate_npu_quality_summary(summary, "q", ORIGINAL, accelerator="GPU", gpu_precision="FP32")
        self.assertEqual("passed", passed["status"])
        self.assertEqual("FP32", passed["candidate_gpu_precision"])
        unset = {k: v for k, v in summary.items() if k != "gpu_precision"}
        self.assertIn("gpu_precision_mismatch", ORCH.evaluate_npu_quality_summary(
            unset, "q", ORIGINAL, accelerator="GPU", gpu_precision="FP32")["failure_reasons"])


class SpanCapAndTimeoutTest(unittest.TestCase):
    def test_span_cap_is_sent_and_recorded(self):
        args = parse("--resources", "NPU", "--npu-max-inference-spans", "1600000", "--accuracy-preflight", "off")
        ORCH.validate_cli(args)
        intent = ORCH.runner_intent_arguments(
            "NPU", None, 1200, 20, "run", "command", 100, 10.0, **ORCH.npu_runner_intent_kwargs("NPU", args))
        index = intent.index("d1_max_inference_spans")
        self.assertEqual(("--ei", "1600000"), (intent[index - 1], intent[index + 1]))
        self.assertEqual(1600000, ORCH.experiment_config(args)["npu"]["max_inference_spans"])

    def test_bad_values_are_rejected(self):
        for argv in (
            ["--resources", "NPU", "--npu-max-inference-spans", "0"],
            ["--resources", "NPU", "--npu-max-inference-spans", "3000001"],
            ["--resources", "CPU", "--npu-max-inference-spans", "500000"],
            ["--runner-timeout-seconds", "0"],
            ["--logger-exit-timeout-seconds", "nan"],
        ):
            with self.subTest(argv=argv), self.assertRaises(ORCH.OrchestratorError):
                ORCH.validate_cli(parse(*argv, "--accuracy-preflight", "off"))

    def test_timeout_overrides_are_recorded_in_the_config(self):
        config = ORCH.experiment_config(parse("--runner-timeout-seconds", "1100", "--logger-exit-timeout-seconds", "900"))
        self.assertEqual(1100.0, config["runner_timeout_seconds"])
        self.assertEqual(900.0, config["logger_exit_timeout_seconds"])


class ChainCliTest(unittest.TestCase):
    def base(self, path, *extra, duration="300"):
        return ["--resources", "NPU", "--mode", "pilot", "--accuracy-preflight", "off",
                "--duration", duration, "--npu-chain", str(path), *extra]

    def test_valid_chain_goes_into_intent_config_and_dry_run(self):
        with tempfile.TemporaryDirectory() as directory:
            path = chain_file(directory, [GPU_D10, GPU_D100])
            args = parse(*self.base(path), "--dry-run")
            ORCH.validate_cli(args)
            payload = ORCH.dry_run_payload(args)
        runner = payload["commands"][0]["runner"]
        b64 = runner[runner.index("d1_npu_chain_b64") + 1]
        sha = runner[runner.index("d1_npu_chain_sha256") + 1]
        text = base64.b64decode(b64).decode("ascii")
        self.assertEqual(hashlib.sha256(text.encode("ascii")).hexdigest(), sha)
        chain = payload["config"]["npu"]["chain"]
        self.assertEqual(json.loads(text), chain["spec"])
        self.assertEqual(sha, chain["sha256"])
        self.assertEqual(300, chain["total_duration_s"])
        self.assertEqual(2, len(chain["segment_models"]))
        self.assertTrue(all("sha256" in model for model in chain["segment_models"]))
        self.assertTrue(re.fullmatch(r"[A-Za-z0-9+/=]+", b64))

    def test_chain_rules(self):
        with tempfile.TemporaryDirectory() as directory:
            good = chain_file(directory, [GPU_D10, GPU_D100])
            cases = {
                "formal": self.base(good)[:2] + ["--mode", "formal"] + self.base(good)[4:],
                "cpu resource": ["--resources", "CPU"] + self.base(good)[2:],
                "preflight on": [a if a != "off" else "optional" for a in self.base(good)],
                "duration mismatch": self.base(good, duration="301"),
                "duty set": self.base(good, "--duty-cycles", "50"),
                "accelerator set": self.base(good, "--npu-accelerator", "GPU", "--npu-model-asset", ORIGINAL),
                "run-only set": self.base(good, "--npu-run-only-span"),
                "model asset set": self.base(good, "--npu-model-asset", ORIGINAL),
            }
            bad_file = chain_file(directory, [dict(GPU_D10, model=AOT)])
            cases["AOT on GPU in file"] = self.base(bad_file, duration="60")
            for name, argv in cases.items():
                with self.subTest(case=name), self.assertRaises((ORCH.OrchestratorError, ValueError)):
                    ORCH.validate_cli(parse(*argv))


class EmergencyAbortTargetsTheRunningRunnerTest(unittest.TestCase):
    """2-B: the only intentional behaviour change without a new argument."""

    class Adb:
        def __init__(self):
            self.calls = []

        def run(self, arguments, timeout=30, check=True):
            self.calls.append(list(arguments))
            return subprocess.CompletedProcess(arguments, 0, "", "")

    def stopped_package(self, resource: str) -> str:
        with tempfile.TemporaryDirectory() as directory:
            args = parse("--resources", resource)
            manifest = {"runs": []}
            orchestrator = ORCH.ExperimentOrchestrator(args, manifest, Path(directory) / "experiment_manifest.json")
            orchestrator.adb = self.Adb()
            slot = {"resource": resource, "runtime_safety": {}, "steps": []}
            error = ORCH.EmergencyAbort("dumpsys", "load", ["battery_temperature_emergency"], {"battery": 43.0})
            orchestrator._record_emergency_abort(slot, error)
            self.assertEqual("emergency_runner_force_stop", slot["steps"][-1]["name"])
            return orchestrator.adb.calls[-1][-1]

    def test_npu_slot_stops_npu_runner(self):
        self.assertEqual(ORCH.NPU_RUNNER_PACKAGE, self.stopped_package("NPU"))

    def test_cpu_and_gpu_slots_still_stop_benchmark_runner(self):
        self.assertEqual(ORCH.RUNNER_PACKAGE, self.stopped_package("CPU"))
        self.assertEqual(ORCH.RUNNER_PACKAGE, self.stopped_package("GPU"))


class P2IntentContractTest(unittest.TestCase):
    """Every new extra the orchestrator can send is one npu-runner reads, with the same type."""

    def test_new_extras_match_the_runner_parser(self):
        source = KOTLIN_CONFIG.read_text("utf-8")
        constants = dict(re.findall(r'const val (EXTRA_[A-Z0-9_]+) = "([^"]+)"', source))

        def listed(name):
            body = re.search(rf"val {name} = listOf\((.*?)\)", source, re.S).group(1)
            return {constants[item.strip()] for item in body.split(",") if item.strip()}

        strings, ints = listed("stringExtras"), listed("intExtras")
        arguments = ORCH.runner_intent_arguments(
            "NPU", None, 300, 20, "run", "command", 100, 10.0, npu_model_asset=AOT,
            npu_accelerator="GPU", npu_gpu_precision="FP32", npu_max_inference_spans=1_000_000,
            npu_chain_b64="e30=", npu_chain_sha256="0" * 64,
        )
        sent = {arguments[i + 1]: arguments[i] for i in range(len(arguments) - 1)
                if arguments[i] in ("--es", "--ei")}
        self.assertEqual("--es", sent["d1_npu_gpu_precision"])
        self.assertEqual("--ei", sent["d1_max_inference_spans"])
        self.assertEqual("--es", sent["d1_npu_chain_b64"])
        self.assertEqual("--es", sent["d1_npu_chain_sha256"])
        for key, flag in sent.items():
            with self.subTest(key=key):
                self.assertIn(key, constants.values())
                self.assertIn(key, strings if flag == "--es" else ints)


def roundtrip_cases(prefix: str) -> list[Path]:
    return sorted(p.parent for p in ARTIFACTS.glob(f"{prefix}*/roundtrip.json"))


@unittest.skipUnless(roundtrip_cases("chain-"), "run `gradlew :npu-runner:testDebugUnitTest` first")
class ChainAndGpuSlotsThroughTheHostTest(unittest.TestCase):
    """The JVM-produced chain/GPU runner files go through analyze + the slot validator like a real slot."""

    @classmethod
    def setUpClass(cls):
        cls.RT = load("test_npu_runner_roundtrip_p2", "test_npu_runner_roundtrip.py")

    def analyze(self, run_dir, info):
        with contextlib.redirect_stdout(io.StringIO()):
            self.RT.LOGGER.analyze(run_dir)
        args = ORCH.build_parser().parse_args(["--resources", "NPU", "--mode", "pilot"])
        accuracy = ORCH.experiment_config(args)["accuracy_preflight"]
        ORCH.attach_accuracy_to_analyzer_summary(run_dir, accuracy)
        return accuracy

    def test_chain_slots_validate_and_are_never_formal(self):
        for case in roundtrip_cases("chain-"):
            with self.subTest(case=case.name), tempfile.TemporaryDirectory() as directory:
                run_dir, info, events = self.RT.build_host_run(Path(directory), case)
                accuracy = self.analyze(run_dir, info)
                spec = json.loads(info["chain_json"])
                chain = {"spec": spec, "sha256": info["chain_sha256"]}
                validation = ORCH.validate_chain_result(
                    run_dir, info["duration_s"], info["warmup"], info["run_id"], info["command_id"],
                    info["duty_cycle_period_s"], chain, accuracy,
                )
                self.assertTrue(validation["valid"], validation["failed_checks"])
                summary = validation["summary"]
                self.assertIs(False, summary["formal_npu_valid"])
                self.assertIs(False, summary["formal_npu_conditions"]["not_chain_run"])
                self.assertTrue(validation["chain_check"]["checks"]["telemetry_no_gap_in_load"])
                # the same file checked as a single-duty slot fails on the duty checks it replaces
                single = ORCH.validate_result(
                    run_dir, "NPU", None, info["duration_s"], info["warmup"], info["run_id"],
                    info["command_id"], "pilot", 100, info["duty_cycle_period_s"], accuracy, None,
                )
                self.assertIn("duty_request", single["failed_checks"])

    def test_chain_validation_fails_when_the_chain_does_not_match(self):
        case = next(c for c in roundtrip_cases("chain-") if c.name == "chain-m2-per-segment")
        with tempfile.TemporaryDirectory() as directory:
            run_dir, info, events = self.RT.build_host_run(Path(directory), case)
            accuracy = self.analyze(run_dir, info)
            spec = json.loads(info["chain_json"])
            spec["segments"] = list(reversed(spec["segments"]))
            validation = ORCH.validate_chain_result(
                run_dir, info["duration_s"], info["warmup"], info["run_id"], info["command_id"],
                info["duty_cycle_period_s"], {"spec": spec, "sha256": info["chain_sha256"]}, accuracy,
            )
            self.assertFalse(validation["valid"])
            self.assertIn("chain_conservation", validation["failed_checks"])

    def test_gpu_slot_is_a_valid_pilot_and_never_formal_npu(self):
        case = next(c for c in roundtrip_cases("gpu-") if c.name == "gpu-compiled-d100")
        with tempfile.TemporaryDirectory() as directory:
            run_dir, info, events = self.RT.build_host_run(Path(directory), case)
            accuracy = self.analyze(run_dir, info)
            validation = ORCH.validate_result(
                run_dir, "NPU", None, info["duration_s"], info["warmup"], info["run_id"], info["command_id"],
                "pilot", info["duty_cycle_percent"], info["duty_cycle_period_s"], accuracy, None,
            )
            self.assertTrue(validation["valid"], validation["failed_checks"])
            self.assertIs(False, validation["summary"]["formal_npu_valid"])
            self.assertEqual("gpu_compiled_model", events[0]["npu_timed_resource_label"])


if __name__ == "__main__":
    unittest.main()
