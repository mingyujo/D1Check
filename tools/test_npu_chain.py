"""tools/npu_chain.py: chain-spec validation and the chain conservation check (P2, 2026-09-28).

The checker is tested in both directions (falsifiable-experiments "a validator must be shown to reject"):
the real chain JSONL written by npu-runner's JVM round trip (NpuTimedRunRoundTripTest, Robolectric,
npu-runner/build/npu-roundtrip/chain-*) must PASS, and copies with one segment dropped, two segments
swapped, a boundary shifted, an inference dropped or moved, a transition left unexplained, or a
tampered spec must FAIL on the matching check. Run `gradlew :npu-runner:testDebugUnitTest` first.
"""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

TOOLS = Path(__file__).resolve().parent
ARTIFACTS = TOOLS.parent / "npu-runner" / "build" / "npu-roundtrip"


def load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, TOOLS / filename)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


CHAIN = load("npu_chain_test", "npu_chain.py")
ORIGINAL = "models/mobilenet_v1_1.0_224.tflite"
AOT = "models/mobilenet_v1_1.0_224_Samsung_E9965.tflite"


def segment(accelerator, model, duty, seconds, **extra):
    return {"accelerator": accelerator, "model": model, "input_spec": "lcg-unit", "duty": duty,
            "duration_s": seconds, **extra}


def chain(*segments, prepare="per_segment"):
    return {"schema": CHAIN.SCHEMA, "chain_id": "M2_heated", "model_prepare": prepare,
            "segments": list(segments)}


def chain_cases() -> list[Path]:
    return sorted(p.parent for p in ARTIFACTS.glob("chain-*/roundtrip.json"))


def load_case(case: Path) -> tuple[list[dict], dict, str]:
    info = json.loads((case / "roundtrip.json").read_text("utf-8"))
    events = [json.loads(line) for line in (case / "runner.jsonl").read_text("utf-8").splitlines()]
    return events, json.loads(info["chain_json"]), info["chain_sha256"]


class ChainSpecTest(unittest.TestCase):
    def test_valid_chain_and_canonical_transport(self):
        spec = chain(segment("GPU", ORIGINAL, 100, 1200, label="heat", gpu_precision="FP32"),
                     segment("NPU", AOT, 100, 60, warmup=20))
        self.assertEqual({"segment_count": 2, "total_duration_s": 1260}, CHAIN.validate_spec(spec))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "chain.json"
            path.write_text(json.dumps(spec, indent=2), "utf-8")
            loaded = CHAIN.load_chain(path)
        import base64
        import hashlib
        text = base64.b64decode(loaded["b64"]).decode("ascii")
        self.assertEqual(loaded["canonical_json"], text)
        self.assertEqual(hashlib.sha256(text.encode("ascii")).hexdigest(), loaded["sha256"])
        self.assertEqual(spec, json.loads(text))
        self.assertNotIn(" ", text)

    def test_malformed_chains_fail_closed(self):
        good = segment("GPU", ORIGINAL, 100, 30)
        cases = {
            "AOT on GPU": chain(segment("GPU", AOT, 100, 30)),
            "original on NPU": chain(segment("NPU", ORIGINAL, 100, 30)),
            "unknown segment key": chain(dict(good, dutty=50)),
            "unknown top key": dict(chain(good), extra=1),
            "no model_prepare": {k: v for k, v in chain(good).items() if k != "model_prepare"},
            "bad model_prepare": chain(good, prepare="lazy"),
            "wrong schema": dict(chain(good), schema="d1-npu-chain-v0"),
            "duty 0": chain(segment("GPU", ORIGINAL, 0, 30)),
            "bool duty": chain(segment("GPU", ORIGINAL, True, 30)),
            "string duty": chain(segment("GPU", ORIGINAL, "100", 30)),
            "both model and path": chain(dict(good, model_path="/data/local/tmp/x.tflite")),
            "precision on NPU": chain(segment("NPU", AOT, 100, 30, gpu_precision="FP32")),
            "coordinate spec (host is stricter)": chain(dict(good, input_spec="coordinate-rgb-classification")),
            "sum over 3600 s": chain(segment("GPU", ORIGINAL, 100, 3000), segment("GPU", ORIGINAL, 10, 601)),
            "no segments": chain(),
            "fallback list": chain(segment("NPU,CPU", AOT, 100, 30)),
        }
        for name, value in cases.items():
            with self.subTest(case=name), self.assertRaises(CHAIN.ChainSpecError):
                CHAIN.validate_spec(value)


class ShippedChainFilesTest(unittest.TestCase):
    """tools/chains/*.json (smoke, M1, M2) pass the host rules and the orchestrator CLI rules."""

    def test_every_shipped_chain_validates_and_is_accepted_by_the_orchestrator(self):
        orch = load("d1_experiment_orchestrator_chains_test", "d1_experiment_orchestrator.py")
        files = sorted((TOOLS / "chains").glob("*.json"))
        self.assertGreaterEqual(len(files), 7)
        for path in files:
            with self.subTest(chain=path.name):
                chain = CHAIN.load_chain(path)
                self.assertEqual(path.stem, chain["chain_id"])
                args = orch.build_parser().parse_args([
                    "--resources", "NPU", "--mode", "pilot", "--accuracy-preflight", "off",
                    "--duration", str(chain["total_duration_s"]), "--npu-chain", str(path), "--dry-run",
                ])
                orch.validate_cli(args)
                gpu = [s for s in chain["spec"]["segments"] if s["accelerator"] == "GPU"]
                self.assertTrue(all(s.get("gpu_precision") == "FP32" for s in gpu))


@unittest.skipUnless(chain_cases(), "run `gradlew :npu-runner:testDebugUnitTest` to produce chain round trips")
class ChainConservationTest(unittest.TestCase):
    def test_runner_chain_output_passes(self):
        for case in chain_cases():
            events, spec, sha = load_case(case)
            with self.subTest(case=case.name):
                report = CHAIN.check_chain(events, spec, sha)
                self.assertTrue(report["passed"], report["failed_checks"])

    def test_checker_is_deterministic(self):
        events, spec, sha = load_case(chain_cases()[0])
        first = json.dumps(CHAIN.check_chain(events, spec, sha), sort_keys=True).encode()
        second = json.dumps(CHAIN.check_chain(copy.deepcopy(events), spec, sha), sort_keys=True).encode()
        self.assertEqual(first, second)

    def _m2(self):
        case = next(c for c in chain_cases() if c.name == "chain-m2-per-segment")
        return load_case(case)

    def assert_fails(self, events, spec, sha, *expected):
        report = CHAIN.check_chain(events, spec, sha)
        self.assertFalse(report["passed"])
        for name in expected:
            self.assertIn(name, report["failed_checks"])

    def test_dropping_a_segment_fails(self):
        events, spec, sha = self._m2()
        detail = lambda e: json.loads(e["detail"]) if isinstance(e.get("detail"), str) else {}
        drop = [e for e in events if e["event"] in ("segment_start", "segment_end") and detail(e).get("index") == 1]
        self.assert_fails([e for e in events if e not in drop], spec, sha,
                          "segment_count", "segment_order", "inference_conservation")

    def test_dropping_only_a_segment_end_fails(self):
        events, spec, sha = self._m2()
        last_end = max(i for i, e in enumerate(events) if e["event"] == "segment_end")
        self.assert_fails(events[:last_end] + events[last_end + 1:], spec, sha, "segment_count")

    def test_swapping_two_segments_fails(self):
        events, spec, sha = self._m2()
        swapped = copy.deepcopy(spec)
        swapped["segments"][0], swapped["segments"][1] = swapped["segments"][1], swapped["segments"][0]
        # the runner ran the original order; checking it against a swapped chain must fail
        self.assert_fails(events, swapped, None, "spec_roundtrip", "segment_fields_match_spec")
        # and a JSONL whose segment events are reordered must fail against the true chain
        reordered = copy.deepcopy(events)
        starts = [i for i, e in enumerate(reordered) if e["event"] == "segment_start"]
        reordered[starts[0]]["detail"], reordered[starts[1]]["detail"] = (
            reordered[starts[1]]["detail"], reordered[starts[0]]["detail"])
        self.assert_fails(reordered, spec, sha, "segment_order")

    def test_dropping_one_inference_fails(self):
        events, spec, sha = self._m2()
        first = next(i for i, e in enumerate(events) if e["event"] == "inference")
        self.assert_fails(events[:first] + events[first + 1:], spec, sha, "inference_conservation")

    def test_moving_an_inference_into_a_transition_fails(self):
        events, spec, sha = self._m2()
        moved = copy.deepcopy(events)
        transition = json.loads(next(e for e in moved if e["event"] == "chain_transition_end")["detail"])
        victim = next(e for e in moved if e["event"] == "inference")
        victim["start_mono_ns"] = transition["start_ns"]
        victim["mono_ns"] = transition["start_ns"] + 1
        self.assert_fails(moved, spec, sha, "inferences_inside_their_segment")

    def test_shifting_a_segment_start_leaves_a_gap_or_overlap(self):
        events, spec, sha = self._m2()
        for shift in (+2_000_000_000, -2_000_000_000):
            shifted = copy.deepcopy(events)
            start = [e for e in shifted if e["event"] == "segment_start"][1]
            detail = json.loads(start["detail"])
            detail["start_ns"] += shift
            start["detail"] = json.dumps(detail)
            with self.subTest(shift=shift):
                report = CHAIN.check_chain(shifted, spec, sha)
                self.assertFalse(report["passed"])
                self.assertTrue({"no_overlap", "boundary_gaps_within_tolerance", "time_conservation"}
                                & set(report["failed_checks"]))

    def test_unexplained_transition_fails(self):
        events, spec, sha = self._m2()
        transition = json.loads(next(e for e in events if e["event"] == "chain_transition_end")["detail"])
        inside = [e for e in events if e["event"] == "warmup"
                  and transition["start_ns"] <= e.get("start_mono_ns", -1) <= transition["end_ns"]]
        self.assertTrue(inside)
        stripped = [e for e in events if e not in inside]
        # removing the ~3 ms of warmup alone stays inside the 50 ms tolerance (by design), so also stretch
        # the transition by 100 ms that no recorded span covers: that must be reported as unexplained
        widened = copy.deepcopy(stripped)
        end = next(e for e in widened if e["event"] == "chain_transition_end")
        detail = json.loads(end["detail"])
        detail["end_ns"] += 100_000_000
        end["detail"] = json.dumps(detail)
        self.assert_fails(widened, spec, sha, "transitions_explained")

    def test_tampered_spec_or_sha_fails(self):
        events, spec, sha = self._m2()
        tampered = copy.deepcopy(spec)
        tampered["segments"][1]["duration_s"] = 2
        self.assert_fails(events, tampered, sha, "spec_roundtrip")
        self.assert_fails(events, spec, "0" * 64, "sha_roundtrip")

    def test_telemetry_gap_inside_the_load_window_fails(self):
        events, spec, sha = self._m2()
        load0 = next(e for e in events if e["event"] == "load_start")["mono_ns"]
        load1 = next(e for e in events if e["event"] == "load_end")["mono_ns"]
        even = list(range(load0, load1, 100_000_000))
        self.assertTrue(CHAIN.check_chain(events, spec, sha, even)["checks"]["telemetry_no_gap_in_load"])
        gap = [t for t in even if not load0 + 1_000_000_000 <= t < load0 + 2_000_000_000]
        report = CHAIN.check_chain(events, spec, sha, gap)
        self.assertFalse(report["checks"]["telemetry_no_gap_in_load"])
        # a timing-tolerance miss is a flag; the structure still holds
        self.assertEqual(["telemetry_no_gap_in_load"], report["timing_flags"])
        self.assertTrue(report["structure_passed"])

    def test_structural_failures_are_not_mere_flags(self):
        events, spec, sha = self._m2()
        first = next(i for i, e in enumerate(events) if e["event"] == "inference")
        report = CHAIN.check_chain(events[:first] + events[first + 1:], spec, sha)
        self.assertFalse(report["structure_passed"])
        self.assertNotIn("inference_conservation", report["timing_flags"])


if __name__ == "__main__":
    unittest.main()
