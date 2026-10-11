"""M5 shared constants (2026-10-12) — S26 상태 분리 블록 12세션 + 지속 감속 확인 ABBA 4세션. Imported by the statesplit_* tools only.

Registrations (OneDrive bytes, commit ① 9ed096f of branch s26-statesplit):
  d1sim/docs/상태분리_사전등록_v2.md   SHA-256 717bc4e5… — §1 session form (S1 · S2 · S3 · S4), 12 sessions, mirrored order
  d1sim/docs/지속감속_확인_사전등록_v1.md SHA-256 fd197584… — ABBA 4 sessions = plan_v3s CPU / PAR manifests, new experiment id

Importing this module ADDS two rows to mixreq_common.EXPERIMENTS at run time (the file mixreq_common.py is unchanged), so the existing
session / validate / readout code can look the new experiment ids up (common_s · request_count · observe cap · listing period):
  S26-STATESPLIT-01  522 requests · common 120 s · kind "statesplit" · registration_version 3 (host rules = v2/v3: CPU overlap 0 only)
  S26-SUSTAIN-ABBA-01 3,000 requests · common 720 s · kind "sustained" (the readout adds the (S)-6 sustained metrics, as for -03)
The app (request-runner MixreqContract.M5_EXPERIMENTS · StatesplitPlan) has the same rows and the same request derivation.
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import mixreq_common as C  # noqa: E402
import policy_ref  # noqa: E402

STATESPLIT_ID = "S26-STATESPLIT-01"
STATESPLIT_SMOKE_ID = "S26-STATESPLIT-01-SMOKE"
ABBA_ID = "S26-SUSTAIN-ABBA-01"
ABBA_SMOKE_ID = "S26-SUSTAIN-ABBA-01-SMOKE"

REGISTRATION_SS = dict(file="d1sim/docs/상태분리_사전등록_v2.md",
                       sha256="717bc4e50fcd680b25247901ce4d6122cca66d552caea73c8a017bdcd05ec4bd",
                       commit="9ed096fb2eb778969ea2972ad4bea538a2451e14", time="2026-10-12T01:37:52+09:00")
REGISTRATION_ABBA = dict(file="d1sim/docs/지속감속_확인_사전등록_v1.md",
                         sha256="fd197584d2979efec31b3ce6d8607c17fbde80f52ae467d869cac412f8c65641",
                         commit="9ed096fb2eb778969ea2972ad4bea538a2451e14", time="2026-10-12T01:37:52+09:00")
FROZEN_SUSTAIN_MODEL = dict(path="d1sim/sustain_v1/out/s1_frozen.json (branch s26-parsim, commit a49b0583)",
                            sha256="dbdb852cbec0075120380cac49eae7cccde6f9c25257de76153818e9b8dc97f2")

# 등록 §1 segments (offsets relative to the common-window origin; the table's segment times start at the first offset 35 s)
SEGMENTS = (
    dict(name="S1", task="classification", first_offset_ms=35_000, step_ms=100, count=250),
    dict(name="S2", task="detection", first_offset_ms=65_000, step_ms=300, count=84),
    dict(name="S3", task="classification", first_offset_ms=95_000, step_ms=200, count=125),
    dict(name="S3", task="detection", first_offset_ms=95_100, step_ms=400, count=63),
)
SEGMENT_WINDOWS_S = dict(S1=(35.0, 60.0), S2=(65.0, 90.0), S3=(95.0, 120.0), S4=(125.0, 155.0))   # common-origin seconds (기술용)
REQUEST_COUNT = 522
# statesplit_validate rule 3: dispatch / lane_available in [35 s, 150 s) = common window + drain (등록 §1 S3 ends at 119.9 s)
WINDOW_S = (35.0, 150.0)

# 등록 §1: block 1 (dev) C·G·N → block 2 (dev) N·G·C → block 3 (confirm) C·G·N → block 4 (confirm) N·G·C
LETTER_POLICY = {"C": policy_ref.POLICY_CPU, "G": policy_ref.POLICY_PAR, "N": policy_ref.POLICY_PAR_NPU}
LETTER_BLOCK = {"C": "A", "G": "A", "N": "N"}   # runtime residency = the R3 manifests of that policy (block A: 4 keys · block N: 5 keys)
BLOCK_ORDER = ((1, "dev", "CGN"), (2, "dev", "NGC"), (3, "confirm", "CGN"), (4, "confirm", "NGC"))
SESSION_ORDER = tuple((block, split, letter) for block, split, letters in BLOCK_ORDER for letter in letters)   # index 0..11
ABBA_ORDER = ("A", "B", "B", "A")
ABBA_POLICY = {"A": policy_ref.POLICY_CPU, "B": policy_ref.POLICY_PAR}

C.EXPERIMENTS.setdefault(STATESPLIT_ID, dict(smoke_id=STATESPLIT_SMOKE_ID, request_count=REQUEST_COUNT, common_s=120, registration_version=3,
                                             kind="statesplit", plan_dir="plan_v4ss"))
C.EXPERIMENTS.setdefault(ABBA_ID, dict(smoke_id=ABBA_SMOKE_ID, request_count=3000, common_s=720, registration_version=3,
                                       kind="sustained", plan_dir="plan_abba"))


def requests(sid: str) -> list[dict]:
    """Same derivation as request-runner StatesplitPlan.requests: offset order · uuid5(sid/ordinal) · urgent = classification."""
    slots = sorted(((s["task"], s["first_offset_ms"] + i * s["step_ms"]) for s in SEGMENTS for i in range(s["count"])), key=lambda x: x[1])
    rows = []
    for ordinal, (task, offset) in enumerate(slots):
        urgent = task == "classification"
        rows.append(dict(request_id=C.request_id(sid, ordinal), ordinal=ordinal, task_id=task, priority="urgent" if urgent else "normal",
                         offset_ms=offset, deadline_ms=C.URGENT_DEADLINE_MS if urgent else C.NORMAL_DEADLINE_MS))
    validate_requests(rows)
    return rows


def validate_requests(rows: list[dict]) -> None:
    slots = sorted(((s["task"], s["first_offset_ms"] + i * s["step_ms"]) for s in SEGMENTS for i in range(s["count"])), key=lambda x: x[1])
    if len(rows) != REQUEST_COUNT or len({r["request_id"] for r in rows}) != REQUEST_COUNT or len({o for _, o in slots}) != REQUEST_COUNT:
        raise ValueError("statesplit request count/id")
    for i, (q, (task, offset)) in enumerate(zip(rows, slots)):
        urgent = task == "classification"
        if q["ordinal"] != i or q["task_id"] != task or q["offset_ms"] != offset:
            raise ValueError(f"statesplit request {i} task/offset")
        if q["priority"] != ("urgent" if urgent else "normal") or q["deadline_ms"] != (C.URGENT_DEADLINE_MS if urgent else C.NORMAL_DEADLINE_MS):
            raise ValueError(f"statesplit request {i} priority/deadline")


def segment_of(offset_ms: int) -> str:
    s = offset_ms / 1000.0
    for name, (lo, hi) in SEGMENT_WINDOWS_S.items():
        if lo <= s < hi:
            return name
    return "-"


def session_id(experiment_id: str, index: int) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{experiment_id}/{index}"))
