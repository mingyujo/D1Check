"""tools/compiled_model_evidence.py — resource evidence ② for CompiledModel runs, tested in both directions.

Fixtures are filtered excerpts (tools/fixtures/compiled_model_evidence/*.log, made by make_fixtures.py,
which refuses to write an excerpt whose verdicts differ from the full log). Raw logcat is never committed.

  must PASS  CPU rule: C5 runs 6-20 (held out: the rule was frozen from runs 1-5 before they were opened)
             NPU rule: 9/25 NPU formal 20 runs, identical to the existing verdict
  must FAIL  NPU rule: 9/24 04:14 / 04:55 diagnostic dumps (DispatchDelegate line then dispatch failure)
             CPU rule: NPU formal logs and both 9/24 dumps (they print "XNNPACK CPU accelerator registered")
             GPU rule: every CPU and NPU log and both 9/24 dumps
  must PASS  GPU rule: the 2026-10-03 CompiledModel GPU smoke run (fixture gpu_smoke_1002_*, the ONE run the
             rule was frozen from -- a consistency check, not a held-out test; the first M1/M2 chain runs
             are the first real test)
Negative inputs are evaluated with metadata that CLAIMS the tested accelerator, so a FAIL comes from the
log, not from a metadata mismatch.
"""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

TOOLS = Path(__file__).resolve().parent
FIXTURES = TOOLS / "fixtures" / "compiled_model_evidence"
REPO = TOOLS.parent

spec = importlib.util.spec_from_file_location("compiled_model_evidence_test", TOOLS / "compiled_model_evidence.py")
E = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = E
spec.loader.exec_module(E)

MANIFEST = json.loads((FIXTURES / "MANIFEST.json").read_text("utf-8")) if (FIXTURES / "MANIFEST.json").is_file() else {}
FROZEN_CPU_FINGERPRINT = "cef076049ea750289c3406f707f58f70c872f2f7392d4644a3688f6005e7c7bb"  # 2026-09-28 11:23:47 +0900
FROZEN_GPU_FINGERPRINT = "36615b9e1377c02b13629adf9fe950f90d6614155b2876cdbadcf785aeac0618"  # 2026-10-03 00:3x +0900 (1002 smoke run 9f40b682)


def fixtures(prefix: str) -> list[tuple[str, str, dict]]:
    return [(name, (FIXTURES / f"{name}.log").read_text("utf-8"), info["metadata"])
            for name, info in sorted(MANIFEST.items()) if name.startswith(prefix)]


def claim(metadata: dict, accelerator: str) -> dict:
    return dict(metadata, npu_accelerator_requested=accelerator)


LOG_CONDITIONS_CPU = {"xnnpack_full_replacement_in_runner_pid", "xnnpack_delegate_created_in_runner_pid",
                      "no_other_delegate_replacement", "no_failure_or_fallback_line", "single_runner_process"}


@unittest.skipUnless(MANIFEST, "fixtures missing: run tools/fixtures/compiled_model_evidence/make_fixtures.py")
class CpuRuleTest(unittest.TestCase):
    def test_rule_is_still_the_frozen_one(self):
        self.assertEqual(FROZEN_CPU_FINGERPRINT, E.rule_fingerprints()["cpu"])

    def test_held_out_c5_runs_6_to_20_pass(self):
        held_out = [f for f in fixtures("c5_run") if int(f[0][6:8]) >= 6]
        self.assertEqual(15, len(held_out))
        for name, text, metadata in held_out:
            with self.subTest(run=name):
                result = E.evaluate_cpu(text, metadata)
                self.assertEqual("PASS", result["verdict"], result["failed_conditions"])

    def test_rule_building_runs_1_to_5_pass(self):
        building = [f for f in fixtures("c5_run") if int(f[0][6:8]) <= 5]
        self.assertEqual(5, len(building))
        for name, text, metadata in building:
            with self.subTest(run=name):
                self.assertEqual("PASS", E.evaluate_cpu(text, metadata)["verdict"])

    def test_npu_formal_logs_fail_the_cpu_rule_on_log_evidence(self):
        for name, text, metadata in fixtures("npu_formal"):
            with self.subTest(run=name):
                result = E.evaluate_cpu(text, claim(metadata, "CPU"))
                self.assertEqual("FAIL", result["verdict"])
                self.assertTrue(set(result["failed_conditions"]) & LOG_CONDITIONS_CPU)

    def test_g4_diagnostic_dumps_fail_despite_xnnpack_registration(self):
        for name, text, metadata in fixtures("g4_diag"):
            with self.subTest(run=name):
                self.assertIn("XNNPACK CPU accelerator registered.", text)
                self.assertIn(E.CPU_CREATED, text)
                result = E.evaluate_cpu(text, claim(metadata, "CPU"))
                self.assertEqual("FAIL", result["verdict"])
                self.assertIn("xnnpack_full_replacement_in_runner_pid", result["failed_conditions"])
                self.assertIn("no_other_delegate_replacement", result["failed_conditions"])

    def test_registration_lines_alone_are_not_evidence(self):
        name, text, metadata = fixtures("c5_run06")[0]
        stripped = "\n".join(line for line in text.splitlines() if "TfLiteXNNPackDelegate" not in line)
        self.assertIn("XNNPACK CPU accelerator registered.", stripped)
        result = E.evaluate_cpu(stripped, metadata)
        self.assertEqual(["xnnpack_full_replacement_in_runner_pid"], result["failed_conditions"])

    def test_partial_replacement_and_foreign_pid_fail(self):
        name, text, metadata = fixtures("c5_run07")[0]
        partial = text.replace("Replacing 31 out of 31", "Replacing 30 out of 31")
        self.assertIn("xnnpack_full_replacement_in_runner_pid", E.evaluate_cpu(partial, metadata)["failed_conditions"])
        # the same evidence printed by another process is not this run's evidence
        rows = E.parse_log(text)
        pid = sorted(E.runner_pids(rows))[0]
        foreign = "\n".join(
            line.replace(f" {pid} ", " 99999 ", 1) if "TfLiteXNNPackDelegate" in line else line
            for line in text.splitlines()
        )
        self.assertIn("xnnpack_full_replacement_in_runner_pid", E.evaluate_cpu(foreign, metadata)["failed_conditions"])

    def test_a_run_that_asked_for_another_accelerator_fails(self):
        name, text, metadata = fixtures("c5_run08")[0]
        self.assertEqual(["requested_accelerator_cpu"],
                         E.evaluate_cpu(text, claim(metadata, "NPU"))["failed_conditions"])


@unittest.skipUnless(MANIFEST, "fixtures missing")
class NpuRuleTest(unittest.TestCase):
    def test_npu_formal_20_pass_exactly_as_before(self):
        runs = fixtures("npu_formal")
        self.assertEqual(20, len(runs))
        for name, text, metadata in runs:
            with self.subTest(run=name):
                result = E.evaluate_npu(text, metadata)
                self.assertEqual(metadata["existing_npu_evidence"] == "verified", result["verdict"] == "PASS")
                self.assertEqual("PASS", result["verdict"], result["failed_conditions"])

    def test_dispatch_line_followed_by_failure_fails(self):
        for name, text, metadata in fixtures("g4_diag"):
            with self.subTest(run=name):
                self.assertRegex(text, r"Replacing 1 out of 1 node\(s\) with delegate \(DispatchDelegate\)")
                self.assertIn("Failed to create a dispatch delegate kernel", text)
                result = E.evaluate_npu(text, metadata)
                self.assertEqual("FAIL", result["verdict"])
                self.assertIn("existing_npu_delegate_evidence_verified", result["failed_conditions"])

    def test_dispatch_line_alone_is_not_enough(self):
        name, text, metadata = fixtures("npu_formal")[0]
        without_enn = "\n".join(line for line in text.splitlines() if "SetGenAiPerfConfigFromSoc" not in line)
        self.assertEqual("FAIL", E.evaluate_npu(without_enn, metadata)["verdict"])
        lines = text.splitlines()
        at = next(i for i, line in enumerate(lines) if "DispatchDelegate" in line)
        failure = lines[at].split(" I tflite")[0] + " E litert  : [dispatch_delegate.cc:131] Failed to create a dispatch delegate kernel: No usable Dispatch runtime found"
        self.assertEqual("FAIL", E.evaluate_npu("\n".join(lines[:at + 1] + [failure] + lines[at + 1:]), metadata)["verdict"])

    def test_cpu_logs_fail_the_npu_rule_even_though_enn_loads(self):
        for name, text, metadata in fixtures("c5_run"):
            with self.subTest(run=name):
                self.assertIn("SetGenAiPerfConfigFromSoc", text)   # ENN loads in CPU-only runs too
                self.assertEqual("FAIL", E.evaluate_npu(text, claim(metadata, "NPU"))["verdict"])


LOG_CONDITIONS_GPU = {"litert_cl_full_replacement_in_runner_pid", "gpu_environment_created_in_runner_pid",
                      "no_other_delegate_replacement", "no_failure_or_fallback_line", "single_runner_process"}


@unittest.skipUnless(MANIFEST, "fixtures missing")
class GpuRuleTest(unittest.TestCase):
    """GPU rule v1 (frozen 2026-10-03 from results/S26_GPUcm_smoke_1002 run 9f40b682, FP32 requested)."""

    def test_rule_is_still_the_frozen_one(self):
        self.assertEqual(FROZEN_GPU_FINGERPRINT, E.rule_fingerprints()["gpu"])

    def test_smoke_run_passes_and_is_neither_cpu_nor_npu_evidence(self):
        runs = fixtures("gpu_smoke")
        self.assertEqual(1, len(runs))
        name, text, metadata = runs[0]
        self.assertIn("Replacing 31 out of 31 node(s) with delegate (LITERT_CL)", text)
        self.assertIn("Created LiteRT GpuEnvironment.", text)
        result = E.evaluate_gpu(text, metadata)
        self.assertEqual("PASS", result["verdict"], result["failed_conditions"])
        self.assertEqual(["LITERT_CL"], result["details"]["gpu_delegate_names"])
        cpu = E.evaluate_cpu(text, claim(metadata, "CPU"))
        self.assertEqual("FAIL", cpu["verdict"])
        self.assertTrue(set(cpu["failed_conditions"]) & LOG_CONDITIONS_CPU)
        self.assertEqual("FAIL", E.evaluate_npu(text, claim(metadata, "NPU"))["verdict"])

    def test_cpu_npu_and_diagnostic_logs_fail(self):
        for name, text, metadata in fixtures("c5_run") + fixtures("npu_formal") + fixtures("g4_diag"):
            with self.subTest(run=name):
                result = E.evaluate_gpu(text, claim(metadata, "GPU"))
                self.assertEqual("FAIL", result["verdict"])
                self.assertTrue(set(result["failed_conditions"]) & LOG_CONDITIONS_GPU)

    def test_negatives_built_from_the_device_lines(self):
        name, text, metadata = fixtures("gpu_smoke")[0]
        pid = sorted(E.runner_pids(E.parse_log(text)))[0]
        lines = text.splitlines()
        stamp = next(line for line in lines if "(LITERT_CL)" in line).split(" I tflite")[0]
        partial = text.replace("Replacing 31 out of 31", "Replacing 30 out of 31")
        self.assertIn("litert_cl_full_replacement_in_runner_pid", E.evaluate_gpu(partial, metadata)["failed_conditions"])
        foreign = "\n".join(line.replace(f" {pid} ", " 99999 ", 1) if "(LITERT_CL)" in line else line for line in lines)
        self.assertIn("litert_cl_full_replacement_in_runner_pid", E.evaluate_gpu(foreign, metadata)["failed_conditions"])
        no_env = "\n".join(line for line in lines if "Created LiteRT GpuEnvironment." not in line)
        self.assertEqual(["gpu_environment_created_in_runner_pid"], E.evaluate_gpu(no_env, metadata)["failed_conditions"])
        mixed = text + "\n" + stamp + " I tflite  : Replacing 2 out of 2 node(s) with delegate (TfLiteXNNPackDelegate) node, yielding 1 partitions for subgraph 0 ()."
        self.assertIn("no_other_delegate_replacement", E.evaluate_gpu(mixed, metadata)["failed_conditions"])
        fallback = text + "\n" + stamp + " W litert  : Gracefully falling back to CPU"
        self.assertIn("no_failure_or_fallback_line", E.evaluate_gpu(fallback, metadata)["failed_conditions"])
        self.assertEqual(["requested_accelerator_gpu"], E.evaluate_gpu(text, claim(metadata, "NPU"))["failed_conditions"])

    def test_registration_and_load_lines_alone_are_not_evidence(self):
        name, text, metadata = fixtures("gpu_smoke")[0]
        stripped = "\n".join(line for line in text.splitlines() if "(LITERT_CL)" not in line)
        self.assertIn("Dynamically loaded GPU accelerator(libLiteRtClGlAccelerator.so) registered.", stripped)
        self.assertIn("Loaded OpenCL library with dlopen.", stripped)
        self.assertEqual(["litert_cl_full_replacement_in_runner_pid"], E.evaluate_gpu(stripped, metadata)["failed_conditions"])


@unittest.skipUnless(MANIFEST, "fixtures missing")
class DeterminismAndReadOnlyTest(unittest.TestCase):
    def test_same_input_same_bytes(self):
        for name, text, metadata in fixtures("c5_run")[:3] + fixtures("npu_formal")[:3] + fixtures("g4_diag"):
            for fn in (E.evaluate_cpu, E.evaluate_npu, E.evaluate_gpu):
                with self.subTest(run=name, rule=fn.__name__):
                    first = json.dumps(fn(text, copy.deepcopy(metadata)), sort_keys=True).encode()
                    second = json.dumps(fn(text, copy.deepcopy(metadata)), sort_keys=True).encode()
                    self.assertEqual(first, second)

    def test_evaluate_run_writes_nothing(self):
        name, text, metadata = fixtures("c5_run10")[0]
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory) / "run"
            (run / "raw").mkdir(parents=True)
            (run / "gpu").mkdir()
            (run / "raw" / "logcat.txt").write_text(text, "utf-8")
            (run / "gpu" / "gpu-events-x-y.jsonl").write_text(json.dumps(metadata) + "\n", "utf-8")
            before = sorted((p.relative_to(run), p.stat().st_mtime_ns) for p in run.rglob("*"))
            self.assertEqual("PASS", E.evaluate_run(run)["verdict"])
            after = sorted((p.relative_to(run), p.stat().st_mtime_ns) for p in run.rglob("*"))
            self.assertEqual(before, after)


class PrecisionReaderTest(unittest.TestCase):
    """The flatbuffer reader reproduces facts recorded earlier from the same files (작업결과_0926_2차.md)."""

    def test_original_mobilenet(self):
        facts = E.read_tflite(REPO / "benchmark-runner" / "src" / "main" / "assets" / "models" / "mobilenet_v1_1.0_224.tflite")
        self.assertEqual({"FLOAT32": 88, "INT32": 1}, facts["tensor_types"])
        self.assertEqual([{"type": "FLOAT32", "shape": [1, 224, 224, 3]}], facts["inputs"])
        self.assertEqual([{"type": "FLOAT32", "shape": [1, 1001]}], facts["outputs"])
        self.assertEqual(31, facts["operator_count"])
        self.assertEqual("d95b3c5ea86750cef882fa867ca357dfe4d265d0b80b67e83277a0bda310cfbb", facts["sha256"])

    def test_aot_model_weights_are_not_readable(self):
        path = REPO / "npu-runner" / "src" / "main" / "assets" / "models" / "mobilenet_v1_1.0_224_Samsung_E9965.tflite"
        facts = E.read_tflite(path)
        self.assertEqual(["DISPATCH_OP"], facts["custom_ops"])
        self.assertEqual({"FLOAT32": 2}, facts["tensor_types"])
        record = E.precision_four(path)
        self.assertTrue(record["storage"]["value"].startswith("unknown"))
        self.assertEqual("unknown", record["internal_compute"]["value"])

    def test_rejects_a_non_tflite_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "x.tflite"
            path.write_bytes(b"\x00" * 64)
            with self.assertRaises(ValueError):
                E.read_tflite(path)


if __name__ == "__main__":
    unittest.main()
