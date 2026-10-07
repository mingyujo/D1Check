"""Shared constants and helpers for the S26 mixed-request host tools (R1, 2026-10-08).

Registration: d1sim/docs/혼합요청_사전등록_v1.md (SHA-256 edf9e594…, commit 20967fb). The constants below are copied from it
and from the request-runner Kotlin contract (request-runner/src/main/java/MixreqContract.kt). Nothing here reads a device.
"""
from __future__ import annotations

import hashlib
import json
import math
import uuid
from pathlib import Path

import policy_ref

PROTOCOL = "s26-mixreq-session-v1"
EXPERIMENT_ID = "S26-MIXREQ-01"
SMOKE_EXPERIMENT_ID = "S26-MIXREQ-01-SMOKE"
REGISTRATION_SHA256 = "edf9e594c66b695104698c52ded8ff5c869f70946ee886bc42364ef99c862e28"
REGISTRATION_COMMIT = "20967fb98478c451bd36d9c6c83e0e33154b9109"
REGISTRATION_TIME = "2026-10-08T03:41:26+09:00"

REQUEST_COUNT = 192
SMOKE_REQUEST_COUNT = 24
FIRST_OFFSET_MS = 35_000
STEP_MS = 400
URGENT_DEADLINE_MS = 1_500
NORMAL_DEADLINE_MS = 6_000
COMMON_S = 120
WINDOW_START_S = 35  # dispatch / lane_available must lie in [35 s, 120 s) (등록 §4-3 · A24 d1_online_policy_model 62~67)
PHASES = {"A": dict(setup_s=150, gate_s=60, baseline_s=30, common_s=120, drain_s=30, cooling_s=60),
          "N": dict(setup_s=180, gate_s=60, baseline_s=30, common_s=120, drain_s=30, cooling_s=60)}
SAMPLE_PERIOD_MS = 900
STOP_RULES = dict(battery_deci_c_max=420, thermal_status_max=2, soc_min=20)
START_CHECK = dict(thermal_status_max=1)
WARMUPS_PER_KEY = 2

# 등록 §3-3 session order (index -> block, policy); pair = index // 2 (A) · (index - 8) // 2 (N)
SESSION_ORDER = (
    ("A", policy_ref.POLICY_CPU), ("A", policy_ref.POLICY_PAR), ("A", policy_ref.POLICY_PAR), ("A", policy_ref.POLICY_CPU),
    ("A", policy_ref.POLICY_PAR), ("A", policy_ref.POLICY_CPU), ("A", policy_ref.POLICY_CPU), ("A", policy_ref.POLICY_PAR),
    ("N", policy_ref.POLICY_CPU), ("N", policy_ref.POLICY_PAR_NPU), ("N", policy_ref.POLICY_PAR_NPU), ("N", policy_ref.POLICY_CPU),
    ("N", policy_ref.POLICY_PAR_NPU), ("N", policy_ref.POLICY_CPU), ("N", policy_ref.POLICY_CPU), ("N", policy_ref.POLICY_PAR_NPU),
)
SMOKE_SESSIONS = (  # (smoke index, block, policy) — ID namespace S26-MIXREQ-01-SMOKE/<index>
    (0, "A", policy_ref.POLICY_CPU), (1, "A", policy_ref.POLICY_PAR), (9, "N", policy_ref.POLICY_PAR_NPU),
)
SMOKE_WARMUP_ONLY_INDEX = 8  # S1 = block N configuration, warmup 10, no requests (등록 §3-8 스모크 셈)

# Pinned artifacts (등록 §1-3 · §1-4)
CLS_MODEL_SHA256 = "6c7ab0a6e5dcbf38a8c33b960996a55a3b4300b36a018c4545801de3a3c8bde0"
DET_MODEL_SHA256 = "40338edf5ec70d43e318b0a716a84d4564cd1802759a7a07170c7e43796dbf58"
AOT_MODEL_SHA256 = "311e4aac8fa1d8def4e13359c731ddc1c92f4c9ff7074e0d3860b036df8b2a31"
CLS_LABEL_SHA256 = "e697a491aa735cc6c2aaf982f8e86e8fc7b0a1ea7750a2cc6a2bdfc1e109012f"
DET_LABEL_SHA256 = "f8803ef7900160c629d570848dfda4175e21667bf7b71f73f8ece4938c9f2bf2"
ANCHORS_SHA256 = "e095e869203d5f5442583712e1546aac8f5112512b1a98925165fe17b455c3bc"
PNG_SHA256 = "3e8b925feafbfe5fdd4efb9d7911f445a3212100fa73744f6fd855cf6160f1ab"
RGB_SHA256 = "ca6c2e2bf77bfd8c9240404f516a17eb21c24ba34159ce2e3722bf8aaf225455"
CLS_INPUT_TENSOR_SHA256 = "603328d02dfc2b1aa356b26b0f14b9e70f8cdb80609c89fd171bcf4c3ff85462"
IMAGE_WIDTH, IMAGE_HEIGHT = 1024, 683
DISPATCH_LIB_SHA256 = "f08656a642c46e7b06b64fbe1e0800de9e73b0b69c1641b87995562b4a16840f"

DEVICE_INPUT_DIR = "/data/local/tmp/mixreq"
DEVICE_SESSION_DIR = "/data/local/tmp/mixreq/sessions"
APP_PACKAGE = "com.example.d1check.requestrunner"
APP_ACTIVITY = f"{APP_PACKAGE}/.SessionActivity"
APP_OUTPUT_DIR = f"/storage/emulated/0/Android/data/{APP_PACKAGE}/files/mixreq"
MEASURE_APP_PACKAGE = "com.example.d1check.npurunner"  # never installed / stopped by these tools
LOG_TAG = "D1MIX"

# A24 quality rule (tools/d1_probe_compare.compare_decoded · d1_energy_collection quality): classification top-5 same label/index,
# |dscore| <= 0.001; detection same count/labels, |dscore| <= 1e-3, box <= 2 px (등록 §4-1 · §4-6)
CLS_SCORE_TOL = 1e-3
DET_SCORE_TOL = 1e-3
DET_BOX_TOL_PX = 2.0
# 등록 §4-N npu-mixreq-contract-v1
NPU_COSINE_MIN = 0.99


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path | str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json(value) -> bytes:
    """Deterministic bytes (sorted keys, compact) — plan files must be byte-identical across runs."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def read_json(path: Path | str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path | str, value, indent: int | None = 2) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(value, f, indent=indent, ensure_ascii=False, sort_keys=True, allow_nan=False)
        f.write("\n")


def session_id(experiment_id: str, index: int) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{experiment_id}/{index}"))


def request_id(sid: str, ordinal: int) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{sid}/{ordinal}"))


def requests(sid: str, count: int = REQUEST_COUNT) -> list[dict]:
    """A24 tools/d1_sustained_protocol.requests + d1_sustained_plan 85~87 (uuid5 ids); same field names as the A24 manifest."""
    rows = []
    for i in range(count):
        urgent = i % 2 == 0
        rows.append(dict(request_id=request_id(sid, i), ordinal=i,
                         task_id="classification" if urgent else "detection",
                         priority="urgent" if urgent else "normal",
                         offset_ms=FIRST_OFFSET_MS + i * STEP_MS,
                         deadline_ms=URGENT_DEADLINE_MS if urgent else NORMAL_DEADLINE_MS))
    return rows


def validate_requests(rows: list[dict], count: int = REQUEST_COUNT) -> None:
    if count not in (REQUEST_COUNT, SMOKE_REQUEST_COUNT) or len(rows) != count or len({r["request_id"] for r in rows}) != count:
        raise ValueError("request count/id")
    for i, q in enumerate(rows):
        urgent = i % 2 == 0
        if q["ordinal"] != i or q["offset_ms"] != FIRST_OFFSET_MS + i * STEP_MS:
            raise ValueError(f"request {i} ordinal/offset")
        if q["task_id"] != ("classification" if urgent else "detection") or q["priority"] != ("urgent" if urgent else "normal"):
            raise ValueError(f"request {i} task/priority")
        if q["deadline_ms"] != (URGENT_DEADLINE_MS if urgent else NORMAL_DEADLINE_MS):
            raise ValueError(f"request {i} deadline")


def pair_of(block: str, index: int) -> int:
    return index // 2 if block == "A" else (index - 8) // 2


def nearest_rank_p95(values: list[float], planned: int):
    """등록 §5: P95 = sorted[ceil(0.95·n) − 1] with the denominator = planned count of that class; missing → +inf.
    Returns None when planned == 0."""
    if planned <= 0:
        return None
    v = sorted(list(values) + [math.inf] * (planned - len(values)))
    return v[math.ceil(0.95 * planned) - 1]


def top5_from_softmax(softmax: list[float]) -> list[tuple[int, float]]:
    """A24 decoder: score descending then class index ascending (tools/d1_classification_reference 64~65)."""
    order = sorted(range(len(softmax)), key=lambda i: (-softmax[i], i))[:5]
    return [(i, softmax[i]) for i in order]


def cosine(a: list[float], b: list[float]):
    if len(a) != len(b) or not a:
        return None
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0 or not all(math.isfinite(x) for x in a + b):
        return None
    return dot / (na * nb)
