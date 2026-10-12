"""M6 shared constants (2026-10-12) — S26 같은 APK: 게이지 진단 E · 냉각 K · 정책 대응 P. Imported by the m6_* tools only.

Registration (OneDrive bytes, commit ① abe64b8 of branch s26-m6):
  d1sim/docs/M6_동일APK_사전등록_v3.md SHA-256 b57b8957… — §1 APK (block M) · §2 E · §3 P (loads L / B · order · V1 ~ V5) · §4 K

Importing this module ADDS rows to mixreq_common / policy_ref tables at run time (those files are unchanged), so the existing
session / validate / readout code can look the new experiment ids and block M up:
  mixreq_common.EXPERIMENTS: S26-M6-P (100 requests · common 120 s · kind "m6p") · S26-M6-K (0 · 780 s · kind "m6k")
  mixreq_common.PHASES["M"] = PHASES["N"] (setup 180 s) · policy_ref.BLOCK_KEYS["M"] = 5 keys · BLOCK_POLICIES["M"] = 3 policies
The app (request-runner MixreqContract.M6_EXPERIMENTS · BLOCK_M · M6Plan) has the same rows and the same request derivation.
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import mixreq_common as C  # noqa: E402
import policy_ref  # noqa: E402

P_ID = "S26-M6-P"
P_SMOKE_ID = "S26-M6-P-SMOKE"
K_ID = "S26-M6-K"
K_SMOKE_ID = "S26-M6-K-SMOKE"
E_ID = "S26-M6-E"
E_SMOKE_ID = "S26-M6-E-SMOKE"
BLOCK = "M"

REGISTRATION = dict(file="d1sim/docs/M6_동일APK_사전등록_v3.md",
                    sha256="b57b8957e9ab29c7e8c9c5cb3e3b023df8ac93e5d781f400850f830d45656579",
                    commit="abe64b860a1c197fbf5ce613a2984b2552a06336", time="2026-10-12T23:29:53+09:00")

# 등록 §3-1 · §3-5: letters → policies; order (거울 · 결과 전 고정) index → "load-letter"
LETTER_POLICY = {"C": policy_ref.POLICY_CPU, "G": policy_ref.POLICY_PAR, "N": policy_ref.POLICY_PAR_NPU}
P_ORDER = ("L-C", "B-G", "L-N", "B-C", "L-G", "B-N", "B-N", "L-G", "B-C", "L-N", "B-G", "L-C")
P_DEV = tuple(range(0, 6))       # 개발 D (M6-A)
P_CONFIRM = tuple(range(6, 12))  # 확인 K (M6-B · 조민규 동결 SHA 뒤)
K_DEV = (0, 1)                   # K1 · K2 (M6-A · P 개발 블록 전)
K_CONFIRM = (2, 3)               # K3 · K4 (M6-B · P 확인 블록 뒤)
P_SMOKE_INDEX = 3                # B-C (프롬프트 4단계 스모크)
K_SMOKE_INDEX = 0
K_SMOKE_TIME_SCALE = 10
REQUEST_COUNT = 100
V2_BOUND_S = 120.000             # 등록 §3-6 V2: every lane_available < origin + 120.000 s
K_WINDOWS_S = dict(W=(0.0, 180.0), S=(600.0, 780.0))   # 등록 §4-2 (기술용 — 계산은 Cowork)
SOC_MIN, SOC_MAX = 30, 90        # 등록 v3 §3-4

# E (등록 §2-1): segments ms · poll target · smoke 30 s
E_SEGMENTS_MS = dict(idle_ms=60_000, load_ms=120_000, rest_ms=120_000)
E_SMOKE_SEGMENTS_MS = dict(idle_ms=6_000, load_ms=12_000, rest_ms=12_000)
E_POLL_TARGET_MS = 20
E_RUNS = ("E1", "E2", "E3", "ET")

C.EXPERIMENTS.setdefault(P_ID, dict(smoke_id=P_SMOKE_ID, request_count=REQUEST_COUNT, common_s=120, registration_version=3, kind="m6p", plan_dir="plan_m6p"))
C.EXPERIMENTS.setdefault(K_ID, dict(smoke_id=K_SMOKE_ID, request_count=0, common_s=780, registration_version=3, kind="m6k", plan_dir="plan_m6k"))
C.PHASES.setdefault(BLOCK, dict(C.PHASES["N"]))
policy_ref.BLOCK_KEYS.setdefault(BLOCK, tuple(policy_ref.BLOCK_KEYS["N"]))
policy_ref.BLOCK_POLICIES.setdefault(BLOCK, (policy_ref.POLICY_CPU, policy_ref.POLICY_PAR, policy_ref.POLICY_PAR_NPU))


def load_of(index: int) -> str:
    return P_ORDER[index].split("-")[0]


def letter_of(index: int) -> str:
    return P_ORDER[index].split("-")[1]


def policy_of(index: int) -> str:
    return LETTER_POLICY[letter_of(index)]


def slots(load: str) -> list[tuple[str, int]]:
    """(task, offset_ms) in ordinal order — same as request-runner M6Plan.slots."""
    if load == "L":
        return [("classification" if i % 2 == 0 else "detection", 35_000 + 400 * i) for i in range(REQUEST_COUNT)]
    if load == "B":
        return [("classification" if (i % 10) % 2 == 0 else "detection", 35_000 + 4_000 * (i // 10) + 50 * (i % 10)) for i in range(REQUEST_COUNT)]
    raise ValueError(f"unknown load {load}")


def load_requests(sid: str, load: str) -> list[dict]:
    rows = []
    for ordinal, (task, offset) in enumerate(slots(load)):
        urgent = task == "classification"
        rows.append(dict(request_id=C.request_id(sid, ordinal), ordinal=ordinal, task_id=task, priority="urgent" if urgent else "normal",
                         offset_ms=offset, deadline_ms=C.URGENT_DEADLINE_MS if urgent else C.NORMAL_DEADLINE_MS))
    validate_load(rows, load)
    return rows


def validate_load(rows: list[dict], load: str) -> None:
    expected = slots(load)
    if len(rows) != REQUEST_COUNT or len({r["request_id"] for r in rows}) != REQUEST_COUNT:
        raise ValueError("m6 request count/id")
    if any(a[1] >= b[1] for a, b in zip(expected, expected[1:])) or sum(1 for t, _ in expected if t == "classification") != 50:
        raise ValueError("m6 load form")
    for i, (q, (task, offset)) in enumerate(zip(rows, expected)):
        urgent = task == "classification"
        if q["ordinal"] != i or q["task_id"] != task or q["offset_ms"] != offset:
            raise ValueError(f"m6 request {i} task/offset")
        if q["priority"] != ("urgent" if urgent else "normal") or q["deadline_ms"] != (C.URGENT_DEADLINE_MS if urgent else C.NORMAL_DEADLINE_MS):
            raise ValueError(f"m6 request {i} priority/deadline")


def requests(experiment_id: str, index: int, sid: str) -> list[dict]:
    if experiment_id in (P_ID, P_SMOKE_ID):
        return load_requests(sid, load_of(index))
    if experiment_id in (K_ID, K_SMOKE_ID):
        return []
    raise ValueError(f"not an M6 experiment {experiment_id}")


PROJECTION_FIELDS = ("ordinal", "task_id", "priority", "offset_ms", "deadline_ms")


def projection(rows: list[dict]) -> list[list]:
    """등록 §3-2: the five columns (ordinal · 종류 · 우선순위 · 예정 도착 · 기한) — request id excluded."""
    return [[r[k] for k in PROJECTION_FIELDS] for r in rows]


def projection_sha256(rows: list[dict]) -> str:
    return C.sha256_bytes(C.canonical_json(projection(rows)))


def session_id(experiment_id: str, index: int) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{experiment_id}/{index}"))


def is_m6(experiment_id: str) -> bool:
    return experiment_id in (P_ID, P_SMOKE_ID, K_ID, K_SMOKE_ID)


def is_k(experiment_id: str) -> bool:
    return experiment_id in (K_ID, K_SMOKE_ID)
