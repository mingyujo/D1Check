"""Device<->host contract round trip for npu-runner timed runs, without a phone.

npu-runner's JVM test (NpuTimedRunRoundTripTest, Robolectric) runs the real NpuTimedRunEngine with the
real telemetry-contract GpuTelemetry serializer and drops the JSONL under
npu-runner/build/npu-roundtrip/<case>/. This test feeds those files to the host exactly as a formal
slot would: d1_logger_v4.analyze -> attach experiment accuracy -> validate_result(mode="formal").

Run `gradlew :npu-runner:testDebugUnitTest` first; without the artifacts these tests skip.
Device-only evidence (dispatch/ENN logcat lines, D1Check run_start/run_stop, thermalservice samples,
capture metadata) cannot come from a JVM, so it is injected here from the 2026-09-24 G4 run.
"""
import contextlib
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
G4_FINAL_SUMMARY = (
    REPO / "s26" / "npu" / "results"
    / "G4_summary_2026-09-24506_1569_WIRELESS_ACPLUGGED_NPU_GATE_FINAL.json"
)


def load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, TOOLS / filename)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


LOGGER = load("d1_logger_v4_roundtrip", "d1_logger_v4.py")
ORCH = load("d1_experiment_orchestrator_roundtrip", "d1_experiment_orchestrator.py")

# 2026-09-24 G4 device log lines (results/G4_GO_2026-09-24456_4289_..._NPU.txt) — injected evidence.
G4_DEVICE_LOG = "\n".join([
    "09-24 04:57:20.976 12719 12756 I litert  : [enn_manager.cc:79] Loading from: libenn_public_api_cpp.so",
    "09-24 04:57:21.088 12719 12756 I litert  : [enn_manager.cc:124] SetGenAiPerfConfigFromSoc: "
    "SOC=s5e9965, mode=7, configId=0",
    "09-24 04:57:21.088 12719 12756 I tflite  : Replacing 1 out of 1 node(s) with delegate "
    "(DispatchDelegate) node, yielding 1 partitions for subgraph 0 ().",
])


def cases() -> list[Path]:
    return sorted(path.parent for path in ARTIFACTS.glob("*/roundtrip.json"))


def formal_args():
    return ORCH.build_parser().parse_args(["--resources", "NPU", "--mode", "formal"])


def build_host_run(root: Path, case_dir: Path) -> tuple[Path, dict, list[dict]]:
    """Lay the JVM-produced runner file out as a formal slot's run directory."""
    info = json.loads((case_dir / "roundtrip.json").read_text("utf-8"))
    runner_text = (case_dir / "runner.jsonl").read_text("utf-8")
    events = [json.loads(line) for line in runner_text.splitlines() if line.strip()]
    run_id = info["run_id"]
    experiment = root / "experiment"
    run_dir = experiment / "runs" / run_id
    (run_dir / "raw").mkdir(parents=True)
    (run_dir / "gpu").mkdir()
    (run_dir / "gpu" / info["runner_file_name"]).write_text(runner_text, "utf-8")

    monos = [int(event["mono_ns"]) for event in events if "mono_ns" in event]
    d1 = [
        {"source": "d1check", "event": "run_start", "run_id": run_id, "mono_ns": min(monos) - 1},
        {"source": "d1check", "event": "run_stop", "run_id": run_id, "mono_ns": max(monos) + 1},
    ]
    (run_dir / "raw/logcat.jsonl").write_text("".join(json.dumps(e) + "\n" for e in d1), "utf-8")
    load_start = next((e["mono_ns"] for e in events if e.get("event") == "load_start"), min(monos))
    load_end = next((e["mono_ns"] for e in events if e.get("event") == "load_end"), max(monos))
    thermal = [
        {"event": "sample", "parse_status": "ok", "mono_ns": load_start + k * (load_end - load_start) // 4,
         "AP": "40.0", "SKIN": "33.0", "BAT": "30.0", "PA": "31.0", "thermal_status": "0"}
        for k in range(5)
    ]
    (run_dir / "raw/thermalservice.jsonl").write_text(
        "".join(json.dumps(e) + "\n" for e in thermal), "utf-8")
    (run_dir / "raw/logcat.txt").write_text(G4_DEVICE_LOG + "\n", "utf-8")
    (run_dir / "metadata.json").write_text(
        json.dumps({"device_model": "SM-S942N", "capture_error": None}), "utf-8")

    # NPU quality preflight: the real G4 gate summary, evaluated by the orchestrator for this model
    gate_summary = json.loads(G4_FINAL_SUMMARY.read_text("utf-8"))
    gate_summary["model_sha256"] = events[0].get("model_sha256")
    preflight = ORCH.evaluate_npu_quality_summary(
        gate_summary, gate_summary["run_id"], ORCH.DEFAULT_NPU_MODEL_ASSET,
    )
    (experiment / "experiment_manifest.json").write_text(
        json.dumps({"npu_quality_preflight": preflight}), "utf-8")
    return run_dir, info, events


def analyze_and_validate(run_dir: Path, info: dict) -> dict:
    with contextlib.redirect_stdout(io.StringIO()):
        LOGGER.analyze(run_dir)
    args = formal_args()
    experiment_accuracy = ORCH.experiment_config(args)["accuracy_preflight"]
    ORCH.attach_accuracy_to_analyzer_summary(run_dir, experiment_accuracy)
    return ORCH.validate_result(
        run_dir, "NPU", None, info["duration_s"], info["warmup"], info["run_id"],
        info["command_id"], "formal", info["duty_cycle_percent"], info["duty_cycle_period_s"],
        experiment_accuracy, ORCH.gpu_profile(args.gpu_profile),
    )


def failure_table(validation: dict) -> str:
    rows = [f"  {name}" for name in validation["failed_checks"]]
    summary = validation["summary"]
    rows.append(f"  formal_npu_conditions={summary.get('formal_npu_conditions')}")
    return "\n".join(rows)


@unittest.skipUnless(cases(), "run `gradlew :npu-runner:testDebugUnitTest` to produce npu-runner/build/npu-roundtrip")
class NpuRunnerRoundTripTest(unittest.TestCase):
    def test_valid_cases_pass_formal_validation(self):
        valid = [case for case in cases()
                 if json.loads((case / "roundtrip.json").read_text("utf-8"))["expect_valid"]]
        self.assertTrue(valid)
        for case in valid:
            with self.subTest(case=case.name), tempfile.TemporaryDirectory() as directory:
                run_dir, info, _ = build_host_run(Path(directory), case)
                validation = analyze_and_validate(run_dir, info)
                self.assertTrue(validation["valid"], "failed checks:\n" + failure_table(validation))
                self.assertIs(True, validation["checks"]["formal_npu_valid"])
                summary = validation["summary"]
                self.assertTrue(all(summary["formal_npu_conditions"].values()))
                self.assertEqual("verified", summary["npu_delegate_evidence"]["verification"])

    def test_host_catches_a_broken_runner_file(self):
        """The round trip is not vacuous: corrupting one runner field fails the matching check."""
        case = next(c for c in cases() if c.name == "npu-d100")
        mutations = {
            "cpu_affinity_none": {"cpu_affinity": "ALL"},
            "resource": {"resource": "GPU"},
            "duration_complete": {"termination_reason": "run_error"},
            "formal_npu_valid": {"npu_dispatch_lib_sha256": "0" * 64},
            "pilot_safety": {"pilot_safety_pass": False},
            "runner_accuracy_not_misrepresented": {"accuracy_preflight": {"status": "passed"}},
        }
        for check, fields in mutations.items():
            with self.subTest(check=check), tempfile.TemporaryDirectory() as directory:
                run_dir, info, events = build_host_run(Path(directory), case)
                runner = run_dir / "gpu" / info["runner_file_name"]
                events[0].update(fields)
                runner.write_text("".join(json.dumps(e) + "\n" for e in events), "utf-8")
                validation = analyze_and_validate(run_dir, info)
                self.assertFalse(validation["valid"])
                self.assertIn(check, validation["failed_checks"])

    def test_rejected_case_is_classified_and_invalid(self):
        rejected = [case for case in cases()
                    if not json.loads((case / "roundtrip.json").read_text("utf-8"))["expect_valid"]]
        self.assertTrue(rejected)
        for case in rejected:
            with self.subTest(case=case.name), tempfile.TemporaryDirectory() as directory:
                run_dir, info, events = build_host_run(Path(directory), case)
                kinds = {ORCH.classify_runner_terminal(event, info["run_id"]) for event in events}
                self.assertIn("failure", kinds)
                with contextlib.redirect_stdout(io.StringIO()):
                    with self.assertRaises(ValueError):
                        # no load_start/load_end: the analyzer refuses the envelope, like on device
                        LOGGER.analyze(run_dir)

    def test_remote_fallback_probe_reads_the_file_as_completed(self):
        for case in cases():
            info = json.loads((case / "roundtrip.json").read_text("utf-8"))
            lines = (case / "runner.jsonl").read_text("utf-8").splitlines()
            listing = subprocess.CompletedProcess([], 0, info["runner_file_name"] + "\n", "")
            tail = subprocess.CompletedProcess(
                [], 0, "\n".join(lines[-ORCH.REMOTE_TAIL_LINES:]) + "\n", "")

            class ScriptedAdb:
                def __init__(self):
                    self.responses = [listing, tail]
                    self.calls = []

                def run(self, arguments, timeout=30, check=True):
                    self.calls.append(arguments)
                    return self.responses.pop(0)

            adb = ScriptedAdb()
            probe = ORCH.probe_remote_runner(adb, info["run_id"], ORCH.NPU_REMOTE_RUNNER_DIRECTORY)
            with self.subTest(case=case.name):
                self.assertEqual(ORCH.NPU_REMOTE_RUNNER_DIRECTORY, adb.calls[0][-1])
                self.assertEqual(
                    "success" if info["expect_valid"] else "failure", probe.state, probe.detail,
                )


class NpuIntentContractTest(unittest.TestCase):
    """Every extra the orchestrator sends to an NPU slot is one npu-runner reads, with the same type."""

    def kotlin_extras(self) -> tuple[dict[str, str], set[str], set[str]]:
        source = KOTLIN_CONFIG.read_text("utf-8")
        constants = dict(re.findall(r'const val (EXTRA_[A-Z0-9_]+) = "([^"]+)"', source))

        def listed(name: str) -> set[str]:
            body = re.search(rf"val {name} = listOf\((.*?)\)", source, re.S).group(1)
            return {constants[item.strip()] for item in body.split(",") if item.strip()}

        return constants, listed("stringExtras"), listed("intExtras")

    def test_orchestrator_npu_intent_matches_npu_runner_parser(self):
        constants, strings, ints = self.kotlin_extras()
        arguments = ORCH.runner_intent_arguments(
            "NPU", None, 600, 20, "run", "command", 50, 10.0, ORCH.DEFAULT_GPU_PROFILE,
            npu_model_asset=ORCH.DEFAULT_NPU_MODEL_ASSET,
        )
        self.assertEqual(ORCH.NPU_RUNNER_ACTIVITY, arguments[arguments.index("-n") + 1])
        sent = [(arguments[i], arguments[i + 1]) for i in range(len(arguments) - 1)
                if arguments[i] in ("--es", "--ei", "--el", "--ef", "--ez")]
        self.assertTrue(sent)
        for flag, key in sent:
            with self.subTest(key=key):
                self.assertIn(key, constants.values())
                expected = {
                    "--es": key in strings,
                    "--ei": key in ints,
                    "--el": key == constants["EXTRA_DURATION_S"],
                    "--ef": key == constants["EXTRA_DUTY_CYCLE_PERIOD_S"],
                    "--ez": key == constants["EXTRA_AUTO_START"],
                }[flag]
                self.assertTrue(expected, f"{flag} {key} is not read with that type by npu-runner")


if __name__ == "__main__":
    unittest.main()
