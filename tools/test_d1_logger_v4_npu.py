"""NPU path of d1_logger_v4 (npu-runner, S26). Kept apart from test_d1_logger_v4.py so the
CPU/GPU tests stay untouched."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


MODULE_PATH = Path(__file__).with_name("d1_logger_v4.py")
SPEC = importlib.util.spec_from_file_location("d1_logger_v4_npu_test", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
LOGGER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(LOGGER)

MOBILENET_AOT_SHA = "1415b2c87d01b67a9380b8f912e2b4ef4561502105b06f313332c97c1c8cb5cf"

# Lines as they appear in the 2026-09-24 G4 runs (results/G4_GO_2026-09-24456_4289_..._NPU.txt).
G4_PASS_LOG = "\n".join([
    "09-24 04:57:20.964 12719 12756 I litert  : [litert_dispatch.cc:159] Loading shared library: "
    "/data/app/x/lib/arm64/libLiteRtDispatch_Samsung.so",
    "09-24 04:57:20.976 12719 12756 I litert  : [enn_manager.cc:79] Loading from: libenn_public_api_cpp.so",
    "09-24 04:57:21.088 12719 12756 I litert  : [enn_manager.cc:124] SetGenAiPerfConfigFromSoc: "
    "SOC=s5e9965, mode=7, configId=0",
    "09-24 04:57:21.088 12719 12756 I tflite  : Replacing 1 out of 1 node(s) with delegate "
    "(DispatchDelegate) node, yielding 1 partitions for subgraph 0 ().",
])
# Before the <uses-native-library> fix (results/G4_DIAG_NPU_2026-09-24455_1519_...): the Replacing
# line is still printed, then the dispatch kernel fails.
G4_ENN_FAIL_LOG = "\n".join([
    "09-24 04:55:17.506 11787 11874 I litert  : [enn_manager.cc:81] Failed to load enn runtime.",
    "09-24 04:55:17.506 11787 11874 E litert  : [dispatch_delegate.cc:116] Failed to initialize Dispatch API: ERROR",
    "09-24 04:55:17.506 11787 11874 I tflite  : Replacing 1 out of 1 node(s) with delegate "
    "(DispatchDelegate) node, yielding 1 partitions for subgraph 0 ().",
    "09-24 04:55:17.506 11787 11874 E litert  : [dispatch_delegate.cc:131] Failed to create a dispatch "
    "delegate kernel: No usable Dispatch runtime found",
])
CPU_ONLY_LOG = (
    "09-24 04:53:24.075 11384 11420 I tflite  : Replacing 31 out of 31 node(s) with delegate "
    "(TfLiteXNNPackDelegate) node, yielding 1 partitions for subgraph 0 ()."
)


def passing_preflight(sha=MOBILENET_AOT_SHA, **gate_overrides):
    gate = {
        "version": "npu-quality-gate-v1", "n": 32, "bit_identical_count": 0,
        "bit_identical_to_cpu": False, "argmax_agreement": "32/32",
        "cosine_min": 0.99971543, "cosine_mean": 0.99994283, "verdict": "PASS",
    }
    gate.update(gate_overrides)
    return {"status": "passed", "candidate_model_sha256": sha, "quality_gate": gate}


class NpuDelegateEvidenceTest(unittest.TestCase):
    def test_g4_log_is_verified_full(self):
        evidence = LOGGER.npu_delegate_evidence(G4_PASS_LOG, MOBILENET_AOT_SHA)
        self.assertEqual("verified", evidence["verification"])
        self.assertTrue(evidence["npu_full"])
        self.assertFalse(evidence["npu_partial_delegation"])
        self.assertEqual((1, 1, 1), (
            evidence["dispatch_replaced_nodes"], evidence["dispatch_total_nodes"],
            evidence["dispatch_partitions"],
        ))
        self.assertEqual("s5e9965", evidence["enn_soc"])

    def test_replacing_line_alone_is_not_evidence(self):
        evidence = LOGGER.npu_delegate_evidence(G4_ENN_FAIL_LOG, MOBILENET_AOT_SHA)
        self.assertEqual("unverified", evidence["verification"])
        self.assertFalse(evidence["npu_full"])
        self.assertIsNone(evidence["enn_soc"])
        self.assertTrue(evidence["failure_or_fallback_evidence"])

    def test_xnnpack_only_log_is_unverified(self):
        evidence = LOGGER.npu_delegate_evidence(CPU_ONLY_LOG, MOBILENET_AOT_SHA)
        self.assertEqual("unverified", evidence["verification"])
        self.assertIsNone(evidence["dispatch_replaced_nodes"])

    def test_unknown_model_is_unverified(self):
        evidence = LOGGER.npu_delegate_evidence(G4_PASS_LOG, "0" * 64)
        self.assertIsNone(evidence["aot_partition"])
        self.assertEqual("unverified", evidence["verification"])

    def test_node_count_must_match_aot_manifest(self):
        log = G4_PASS_LOG.replace("Replacing 1 out of 1", "Replacing 1 out of 2")
        evidence = LOGGER.npu_delegate_evidence(log, MOBILENET_AOT_SHA)
        self.assertFalse(evidence["partition_matches_aot_manifest"])
        self.assertEqual("unverified", evidence["verification"])

    def test_every_listed_model_is_a_one_partition_aot_output(self):
        for sha, entry in LOGGER.FORMAL_NPU_AOT_MODELS.items():
            self.assertRegex(sha, r"^[0-9a-f]{64}$")
            self.assertGreaterEqual(entry["dispatch_ops"], 1)


class NpuQualityGateTest(unittest.TestCase):
    def test_passing_gate(self):
        self.assertTrue(LOGGER.npu_quality_gate_passes(passing_preflight(), MOBILENET_AOT_SHA))

    def test_bit_identical_means_cpu_and_fails(self):
        preflight = passing_preflight(bit_identical_to_cpu=True, bit_identical_count=32)
        self.assertFalse(LOGGER.npu_quality_gate_passes(preflight, MOBILENET_AOT_SHA))

    def test_each_fixed_criterion_can_fail(self):
        for overrides in (
            {"argmax_agreement": "31/32"},
            {"cosine_min": 0.989},
            {"n": 16, "argmax_agreement": "16/16"},
            {"verdict": "FAIL"},
            {"cosine_min": None},
        ):
            with self.subTest(overrides=overrides):
                self.assertFalse(LOGGER.npu_quality_gate_passes(
                    passing_preflight(**overrides), MOBILENET_AOT_SHA,
                ))

    def test_preflight_must_be_for_the_same_model(self):
        self.assertFalse(LOGGER.npu_quality_gate_passes(passing_preflight(), "0" * 64))
        self.assertFalse(LOGGER.npu_quality_gate_passes(passing_preflight(sha=""), ""))

    def test_failed_or_missing_preflight(self):
        failed = passing_preflight()
        failed["status"] = "failed"
        self.assertFalse(LOGGER.npu_quality_gate_passes(failed, MOBILENET_AOT_SHA))
        self.assertFalse(LOGGER.npu_quality_gate_passes(None, MOBILENET_AOT_SHA))


def write_run(root: Path, resource: str, raw_log: str, manifest: dict | None,
              device_model: str = "SM-S942N", metadata_overrides: dict | None = None) -> Path:
    run_id = "run-1"
    run_dir = root / "experiment" / "runs" / run_id
    (run_dir / "raw").mkdir(parents=True)
    (run_dir / "gpu").mkdir()
    if manifest is not None:
        (root / "experiment" / "experiment_manifest.json").write_text(json.dumps(manifest), "utf-8")
    (run_dir / "metadata.json").write_text(json.dumps({"device_model": device_model}), "utf-8")
    d1 = [
        {"source": "d1check", "event": "run_start", "run_id": run_id, "mono_ns": 1_000},
        {"source": "d1check", "event": "run_stop", "run_id": run_id, "mono_ns": 100_000},
    ]
    (run_dir / "raw/logcat.jsonl").write_text("\n".join(json.dumps(e) for e in d1) + "\n", "utf-8")
    thermal = [{"event": "sample", "parse_status": "ok", "mono_ns": 50_000, "AP": "40", "SKIN": "33",
                "BAT": "30", "PA": "31", "thermal_status": "0"}]
    (run_dir / "raw/thermalservice.jsonl").write_text(json.dumps(thermal[0]) + "\n", "utf-8")
    (run_dir / "raw/logcat.txt").write_text(raw_log + "\n", "utf-8")
    metadata = {
        "event": "run_metadata", "resource": resource, "experiment_mode": "BASIC",
        "experiment_valid": True, "engine": "litert-compiled-model",
        "model_sha256": MOBILENET_AOT_SHA, "litert_version": "2.2.0",
        "npu_dispatch_lib_sha256": LOGGER.NPU_DISPATCH_LIB_SHA256,
        "mono_ns": 2_000,
    }
    if resource != "NPU":
        metadata.update({"engine": None, "npu_dispatch_lib_sha256": None,
                         "model_sha256": "D95B3C5EA86750CEF882FA867CA357DFE4D265D0B80B67E83277A0BDA310CFBB",
                         "litert_version": "1.4.2"})
    metadata.update(metadata_overrides or {})
    events = [
        metadata,
        {"event": "load_start", "mono_ns": 3_000},
        {"event": "inference", "inference_index": 0, "start_mono_ns": 3_500, "mono_ns": 4_000,
         "latency_ms": 0.7},
        {"event": "load_end", "mono_ns": 90_000},
    ]
    events.append({"event": "file_summary", "status": "ok", "file_event_count": len(events) + 1,
                   "sequence_last": len(events), "mono_ns": 91_000})
    for index, event in enumerate(events):
        event.update({"sequence": index, "run_id": run_id, "runner_session_id": "s1"})
    (run_dir / "gpu" / f"gpu-events-{run_id}-s1.jsonl").write_text(
        "\n".join(json.dumps(e) for e in events) + "\n", "utf-8")
    return run_dir


class NpuAnalyzeTest(unittest.TestCase):
    def analyze(self, run_dir: Path) -> dict:
        with patch("builtins.print"):
            LOGGER.analyze(run_dir)
        return json.loads((run_dir / "merged" / "summary.json").read_text("utf-8"))

    def test_npu_run_with_all_evidence_is_formal_valid(self):
        with tempfile.TemporaryDirectory() as directory:
            run_dir = write_run(Path(directory), "NPU", G4_PASS_LOG,
                                {"npu_quality_preflight": passing_preflight()})
            summary = self.analyze(run_dir)
        self.assertTrue(summary["formal_npu_valid"], summary["formal_npu_conditions"])
        self.assertEqual(9, len(summary["formal_npu_conditions"]))
        self.assertEqual("verified", summary["npu_delegate_evidence"]["verification"])
        self.assertFalse(summary["npu_partial_delegation"])
        self.assertIsNone(summary["formal_gpu_valid"])

    def test_npu_run_fails_closed_on_each_missing_piece(self):
        cases = {
            "dispatch_evidence_verified": dict(raw_log=G4_ENN_FAIL_LOG),
            "quality_gate_pass": dict(manifest={}),
            "validated_device": dict(device_model="SM-A245N"),
            "validated_runtime_pairing": dict(metadata_overrides={"litert_version": "2.3.0"}),
            "known_aot_model": dict(metadata_overrides={"model_sha256": "0" * 64}),
            "runner_experiment_valid": dict(metadata_overrides={"experiment_valid": False}),
        }
        for failing, override in cases.items():
            with self.subTest(failing=failing), tempfile.TemporaryDirectory() as directory:
                arguments = {"raw_log": G4_PASS_LOG,
                             "manifest": {"npu_quality_preflight": passing_preflight()}}
                arguments.update(override)
                run_dir = write_run(Path(directory), "NPU", **arguments)
                summary = self.analyze(run_dir)
                self.assertFalse(summary["formal_npu_valid"])
                self.assertFalse(summary["formal_npu_conditions"][failing])

    def test_cpu_and_gpu_summaries_get_no_npu_keys(self):
        for resource in ("CPU", "GPU"):
            with self.subTest(resource=resource), tempfile.TemporaryDirectory() as directory:
                run_dir = write_run(Path(directory), resource, CPU_ONLY_LOG, None)
                summary = self.analyze(run_dir)
                for key in ("formal_npu_valid", "formal_npu_conditions", "npu_delegate_evidence",
                            "npu_quality_preflight", "npu_partial_delegation", "engine"):
                    self.assertNotIn(key, summary)
                self.assertFalse((run_dir / "merged" / "npu_delegate_evidence.json").exists())


class NpuCaptureArgumentsTest(unittest.TestCase):
    def test_defaults_are_the_benchmark_runner(self):
        args = LOGGER.build_parser().parse_args(["capture", "out"])
        self.assertEqual(LOGGER.RUNNER_PACKAGE, args.runner_package)
        self.assertEqual([], args.extra_logcat_tag)

    def test_npu_arguments(self):
        args = LOGGER.build_parser().parse_args([
            "capture", "out", "--runner-package", LOGGER.NPU_RUNNER_PACKAGE,
            "--extra-logcat-tag", "litert:I",
        ])
        self.assertEqual(LOGGER.NPU_RUNNER_PACKAGE, args.runner_package)
        self.assertEqual(["litert:I"], args.extra_logcat_tag)

    def logcat_command(self, **kwargs):
        with tempfile.TemporaryDirectory() as directory:
            session = LOGGER.CaptureSession(
                "adb", "SERIAL", Path(directory), 1.0, False, Path("unused"), **kwargs,
            )
            captured = {}

            class FakeProcess:
                stdout = iter(())

                def poll(self):
                    return 0

            def fake_popen(command, **_):
                captured["command"] = command
                return FakeProcess()

            with patch.object(LOGGER.subprocess, "Popen", side_effect=fake_popen):
                session.logcat_loop()
            return session, captured["command"]

    def test_default_logcat_filter_is_unchanged(self):
        session, command = self.logcat_command()
        self.assertEqual(LOGGER.RUNNER_PACKAGE, session.runner_package)
        self.assertEqual(
            ["D1CHECK_EVENT:I", "D1GPU:I", "tflite:I", "TfLite:I", "*:S"],
            command[command.index("threadtime") + 1:],
        )

    def test_npu_logcat_filter_adds_litert_before_silence(self):
        session, command = self.logcat_command(
            runner_package=LOGGER.NPU_RUNNER_PACKAGE, extra_logcat_tags=["litert:I"],
        )
        self.assertEqual(LOGGER.NPU_RUNNER_PACKAGE, session.runner_package)
        self.assertEqual(
            ["D1CHECK_EVENT:I", "D1GPU:I", "tflite:I", "TfLite:I", "litert:I", "*:S"],
            command[command.index("threadtime") + 1:],
        )


if __name__ == "__main__":
    unittest.main()
