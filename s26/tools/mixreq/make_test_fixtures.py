"""Deterministic JSON fixtures for the request-runner JVM tests (K2 policy cross-check · K4 decoder cross-check).

  py -3 s26/tools/mixreq/make_test_fixtures.py --a24-tools local_inputs/a24_repo --out request-runner/src/test/resources

policy_cases_v1.json : 1,000 random (policy, waiting queue, lane availability) cases -> expected choice from policy_ref.choose
decode_cases_v1.json : 50 random small raw-output cases + edge cases -> expected decode from A24 tools/d1_detection_contract.decode
                       (score tie, IoU at the 0.3 boundary, empty result, score exactly 0.5 / just below, class tie first index)
Seeded, so re-running yields byte-identical files.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import policy_ref  # noqa: E402

SEED = 20261008


def f32(values):
    """Round to float32-representable doubles so Kotlin FloatArray parsing is exact."""
    return [float(np.float32(v)) for v in values]


def policy_cases(rng: random.Random, n: int) -> list[dict]:
    cases = []
    for _ in range(n):
        policy = rng.choice(policy_ref.POLICIES)
        size = rng.randint(0, 8)
        waiting = []
        for k in range(size):
            urgent = rng.random() < 0.5
            waiting.append({
                "id": f"{rng.randrange(16**8):08x}",
                "task": "classification" if urgent else "detection",
                "priority": "urgent" if urgent else "normal",
                "ordinal": rng.randint(0, 5),  # duplicates on purpose -> id tie-break exercised
            })
        free = {"CPU": rng.random() < 0.6, "GPU": rng.random() < 0.6, "NPU": rng.random() < 0.6}
        expected = policy_ref.choose(policy, waiting, free["CPU"], free["GPU"], free["NPU"])
        cases.append({"policy": policy, "free": free, "waiting": waiting,
                      "expected": None if expected is None else {"id": expected["id"], "backend": expected["backend"]}})
    return cases


def decode_case(det, name, labels, anchors, width, height, scores2d, loc2d):
    expected = det.decode(scores2d, loc2d, anchors, labels, width, height)
    return {"name": name, "labels": labels, "anchors": anchors, "width": width, "height": height,
            "scores": f32([v for row in scores2d for v in row]), "locations": f32([v for row in loc2d for v in row]),
            "expected": [{"label": e["label"], "score": e["score"], "box": e["box"]} for e in expected]}


def decode_cases(det, rng: random.Random) -> list[dict]:
    cases = []
    for k in range(50):
        n_labels = rng.randint(1, 6)
        n_anchors = rng.randint(1, 24)
        labels = [f"l{i}" for i in range(n_labels)]
        anchors = [f32([rng.uniform(0.05, 0.95), rng.uniform(0.05, 0.95), rng.uniform(0.02, 0.6), rng.uniform(0.02, 0.6)]) for _ in range(n_anchors)]
        width, height = rng.randint(1, 640), rng.randint(1, 480)
        scores = [f32([rng.random() if rng.random() < 0.35 else rng.uniform(0, 0.49) for _ in range(n_labels)]) for _ in range(n_anchors)]
        locs = [f32([rng.uniform(-0.5, 0.5), rng.uniform(-0.5, 0.5), rng.uniform(-0.7, 0.7), rng.uniform(-0.7, 0.7)]) for _ in range(n_anchors)]
        cases.append(decode_case(det, f"random_{k}", labels, anchors, width, height, scores, locs))
    labels = ["a", "b"]
    # score tie between two anchors of the same class (pre-NMS order by anchor index), boxes apart -> both kept
    cases.append(decode_case(det, "score_tie_two_anchors", labels,
                             [f32([0.2, 0.2, 0.1, 0.1]), f32([0.8, 0.8, 0.1, 0.1])], 100, 100,
                             [f32([0.1, 0.75]), f32([0.1, 0.75])], [[0.0] * 4, [0.0] * 4]))
    # overlapping identical boxes, equal score -> second suppressed (IoU 1 > 0.3)
    cases.append(decode_case(det, "identical_boxes_equal_score", labels,
                             [f32([0.5, 0.5, 0.2, 0.2]), f32([0.5, 0.5, 0.2, 0.2])], 100, 100,
                             [f32([0.1, 0.7]), f32([0.7, 0.1])], [[0.0] * 4, [0.0] * 4]))
    # IoU at the 0.3 boundary: A=[0,0,10,10], B=[0,0,3,10] -> inter 30 / union 100 (double arithmetic decides)
    cases.append(decode_case(det, "iou_at_0_3_boundary", labels,
                             [f32([0.05, 0.05, 0.1, 0.1]), f32([0.015, 0.05, 0.03, 0.1])], 100, 100,
                             [f32([0.9, 0.1]), f32([0.8, 0.1])], [[0.0] * 4, [0.0] * 4]))
    # class tie -> first index
    cases.append(decode_case(det, "class_tie_first_index", labels, [f32([0.5, 0.5, 0.2, 0.2])], 10, 10,
                             [f32([0.6, 0.6])], [[0.0] * 4]))
    # score exactly 0.5 accepted, just below rejected
    cases.append(decode_case(det, "score_threshold_edge", labels,
                             [f32([0.2, 0.2, 0.1, 0.1]), f32([0.8, 0.8, 0.1, 0.1])], 50, 50,
                             [f32([0.5, 0.1]), f32([0.49999997, 0.1])], [[0.0] * 4, [0.0] * 4]))
    # empty result
    cases.append(decode_case(det, "empty_result", labels, [f32([0.5, 0.5, 0.2, 0.2])] * 3, 20, 20,
                             [f32([0.1, 0.2])] * 3, [[0.0] * 4] * 3))
    # A24 ExplicitDetectionDecoderTest.yxhwLabelOffsetAndOriginalCoordinates
    cases.append(decode_case(det, "a24_yxhw_offset", ["a", "b"], [f32([0.5, 0.5, 0.4, 0.2])], 100, 200,
                             [f32([0.1, 0.75])], [f32([0.5, -0.25, 0.0, 0.0])]))
    return cases


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--a24-tools", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()
    sys.path.insert(0, str(args.a24_tools.resolve()))
    from tools import d1_detection_contract as det  # A24, unmodified

    args.out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(SEED)
    policy = {"schema": "s26-mixreq-policy-cases-v1", "seed": SEED, "generator": "s26/tools/mixreq/make_test_fixtures.py",
              "reference": "s26/tools/mixreq/policy_ref.py", "cases": policy_cases(rng, 1000)}
    (args.out / "policy_cases_v1.json").write_bytes(json.dumps(policy, separators=(",", ":"), sort_keys=True).encode())
    rng = random.Random(SEED + 1)
    decode = {"schema": "s26-mixreq-decode-cases-v1", "seed": SEED + 1, "generator": "s26/tools/mixreq/make_test_fixtures.py",
              "reference": "A24 tools/d1_detection_contract.decode @ feature/arrival-scheduling-20260923",
              "cases": decode_cases(det, rng)}
    (args.out / "decode_cases_v1.json").write_bytes(json.dumps(decode, separators=(",", ":"), sort_keys=True).encode())
    print("policy cases", len(policy["cases"]), "non-null", sum(c["expected"] is not None for c in policy["cases"]))
    print("decode cases", len(decode["cases"]), "detections", sum(len(c["expected"]) for c in decode["cases"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
