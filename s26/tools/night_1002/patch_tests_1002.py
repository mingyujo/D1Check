# -*- coding: utf-8 -*-
"""One-shot patch (2026-10-03): GPU rule v1 tests + fixture generator source. Run from D1Check_v4."""
import io

GPU_FP = "36615b9e1377c02b13629adf9fe950f90d6614155b2876cdbadcf785aeac0618"


def patch(path, pairs):
    s = io.open(path, encoding="utf-8").read()
    for old, new in pairs:
        assert s.count(old) == 1, (path, s.count(old), old[:70])
        s = s.replace(old, new)
    io.open(path, "w", encoding="utf-8", newline="\n").write(s)
    return s


# ---------------------------------------------------------------- tests
p = "tools/test_compiled_model_evidence.py"
s = io.open(p, encoding="utf-8").read()
start = s.index('@unittest.skipUnless(MANIFEST, "fixtures missing")\nclass GpuCandidateTest')
end = s.index('@unittest.skipUnless(MANIFEST, "fixtures missing")\nclass DeterminismAndReadOnlyTest')
new_cls = '''LOG_CONDITIONS_GPU = {"litert_cl_full_replacement_in_runner_pid", "gpu_environment_created_in_runner_pid",
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
        foreign = "\\n".join(line.replace(f" {pid} ", " 99999 ", 1) if "(LITERT_CL)" in line else line for line in lines)
        self.assertIn("litert_cl_full_replacement_in_runner_pid", E.evaluate_gpu(foreign, metadata)["failed_conditions"])
        no_env = "\\n".join(line for line in lines if "Created LiteRT GpuEnvironment." not in line)
        self.assertEqual(["gpu_environment_created_in_runner_pid"], E.evaluate_gpu(no_env, metadata)["failed_conditions"])
        mixed = text + "\\n" + stamp + " I tflite  : Replacing 2 out of 2 node(s) with delegate (TfLiteXNNPackDelegate) node, yielding 1 partitions for subgraph 0 ()."
        self.assertIn("no_other_delegate_replacement", E.evaluate_gpu(mixed, metadata)["failed_conditions"])
        fallback = text + "\\n" + stamp + " W litert  : Gracefully falling back to CPU"
        self.assertIn("no_failure_or_fallback_line", E.evaluate_gpu(fallback, metadata)["failed_conditions"])
        self.assertEqual(["requested_accelerator_gpu"], E.evaluate_gpu(text, claim(metadata, "NPU"))["failed_conditions"])

    def test_registration_and_load_lines_alone_are_not_evidence(self):
        name, text, metadata = fixtures("gpu_smoke")[0]
        stripped = "\\n".join(line for line in text.splitlines() if "(LITERT_CL)" not in line)
        self.assertIn("Dynamically loaded GPU accelerator(libLiteRtClGlAccelerator.so) registered.", stripped)
        self.assertIn("Loaded OpenCL library with dlopen.", stripped)
        self.assertEqual(["litert_cl_full_replacement_in_runner_pid"], E.evaluate_gpu(stripped, metadata)["failed_conditions"])


'''
s = s[:start] + new_cls + s[end:]
io.open(p, "w", encoding="utf-8", newline="\n").write(s)
patch(p, [
    ('''             CPU rule: NPU formal logs and both 9/24 dumps (they print "XNNPACK CPU accelerator registered")
             GPU candidate: every CPU and NPU log
''', '''             CPU rule: NPU formal logs and both 9/24 dumps (they print "XNNPACK CPU accelerator registered")
             GPU rule: every CPU and NPU log and both 9/24 dumps
  must PASS  GPU rule: the 2026-10-03 CompiledModel GPU smoke run (fixture gpu_smoke_1002_*, the ONE run the
             rule was frozen from -- a consistency check, not a held-out test; the first M1/M2 chain runs
             are the first real test)
'''),
    ('''FROZEN_CPU_FINGERPRINT = "cef076049ea750289c3406f707f58f70c872f2f7392d4644a3688f6005e7c7bb"  # 2026-09-28 11:23:47 +0900
''', '''FROZEN_CPU_FINGERPRINT = "cef076049ea750289c3406f707f58f70c872f2f7392d4644a3688f6005e7c7bb"  # 2026-09-28 11:23:47 +0900
FROZEN_GPU_FINGERPRINT = "%s"  # 2026-10-03 00:3x +0900 (1002 smoke run 9f40b682)
''' % GPU_FP),
    ('''            for fn in (E.evaluate_cpu, E.evaluate_npu, E.evaluate_gpu_candidate):''',
     '''            for fn in (E.evaluate_cpu, E.evaluate_npu, E.evaluate_gpu):'''),
])
t = io.open(p, encoding="utf-8").read()
assert "evaluate_gpu_candidate" not in t and "GpuCandidateTest" not in t
print("patched", p)

# ---------------------------------------------------------------- fixture generator
p = "tools/fixtures/compiled_model_evidence/make_fixtures.py"
patch(p, [
    ('''    EVIDENCE.REPLACE_RE.pattern, EVIDENCE.FAILURE_RE.pattern, EVIDENCE.GPU_SUPPORT_RE.pattern,
    EVIDENCE.GPU_FAILURE_RE.pattern, LOGGER.NPU_ENN_LOADED_RE.pattern, re.escape(EVIDENCE.CPU_CREATED),''',
     '''    EVIDENCE.REPLACE_RE.pattern, EVIDENCE.FAILURE_RE.pattern, EVIDENCE.GPU_ENVIRONMENT_RE.pattern,
    EVIDENCE.GPU_FAILURE_RE.pattern, LOGGER.NPU_ENN_LOADED_RE.pattern, re.escape(EVIDENCE.CPU_CREATED),'''),
    ('''                                    ("gpu", EVIDENCE.evaluate_gpu_candidate, "GPU"))}''',
     '''                                    ("gpu", EVIDENCE.evaluate_gpu, "GPU"))}'''),
    ('''NPU_FORMAL = REPO / "results" / "S26_NPU_formal_0925b"
''', '''NPU_FORMAL = REPO / "results" / "S26_NPU_formal_0925b"
GPU_SMOKE = REPO / "results" / "S26_GPUcm_smoke_1002"   # 2026-10-03: the one CompiledModel GPU run (GPU rule v1 source)
'''),
    ('''    for name, file in (("g4_diag_0924_0414_npu", ''', '''    if (GPU_SMOKE / "experiment_manifest.json").is_file():
        smoke = json.loads((GPU_SMOKE / "experiment_manifest.json").read_text("utf-8"))["runs"]
        for slot in sorted(smoke, key=lambda r: r.get("attempt_started_utc") or ""):
            if slot.get("status") != "completed":
                continue
            run_dir = GPU_SMOKE / "runs" / slot["run_id"]
            sources.append((f"gpu_smoke_1002_{slot['slot_id']}", run_dir / "raw" / "logcat.txt", run_metadata(run_dir),
                            "2026-10-03 CompiledModel GPU smoke (MobileNet original, FP32 requested): the ONE run "
                            "GPU rule v1 was frozen from (rule_building, no holdout yet)"))
    for name, file in (("g4_diag_0924_0414_npu", '''),
])
print("patched", p)
