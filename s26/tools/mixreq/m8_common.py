"""M8 shared tables (2026-10-14 · v2 2026-10-15) — 새 계약 (d1sim/docs/M8_계약표_v2.md · s26/results/m8_prep/contract_v2/*.json · 조민규 답 10/14 + 10/15 01:5x 8항목): 정책 7 · bank 4 · 실험 7 · ns 정수 (offset_ns · µs/ms 는 floor) · 기한 0.8/2 ·
uuid5 새 계보 · DEV/CONFIRM 대역 · 단계 (baseline 60 · cooling 90). Imported by the m8_* tools only. The app (request-runner M8Plan · MixreqContract M8_*) has the same rows.

activate() registers the M8 rows into the shared host tables at run time (mixreq_common.EXPERIMENTS · PHASES["NONE"] · policy_ref.BLOCK_KEYS["NONE"] · USED_KEYS M8 정책 ·
session_cap_s for M8 ids · m6_common SOC band = 영훈 운영 결정 (하한 20 · 상한 없음)). m6_common · m7_common · mixreq_common · policy_ref files are unchanged (import only);
importing this module without activate() changes nothing (test_m6 · test_m7 · test_m8 share one pytest process). Nothing here reads a device.
"""
from __future__ import annotations

import math
import sys
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE))
import mixreq_common as C  # noqa: E402
import policy_ref  # noqa: E402
import m6_common as M6  # noqa: E402

CYCLE = "m8"
CONTRACT = "M8"
CONTRACT_VERSION = "v2"           # 조민규 01:5x 8항목 반영 (첫 DEV 정책 실행 전 → 전 블록 v2 · 한 블록 안 계약 섞지 않음)
CONTRACT_MD = REPO / "d1sim" / "docs" / f"M8_계약표_{CONTRACT_VERSION}.md"
CONTRACT_DIR = REPO / "s26" / "results" / "m8_prep" / f"contract_{CONTRACT_VERSION}"
REGISTRATION_FILE = f"d1sim/docs/M8_사전등록_{CONTRACT_VERSION}.md"
REGISTRATION_FILE_V1 = "d1sim/docs/M8_사전등록_v1.md"


def registration() -> dict:
    """등록 v2 가 있으면 그 SHA (v1 SHA 도 함께) · 없으면 v1 · 둘 다 없으면 계약표 SHA (plan bytes 는 등록 커밋 뒤에 만든다)."""
    p = REPO / REGISTRATION_FILE
    p1 = REPO / REGISTRATION_FILE_V1
    if p.is_file():
        return dict(file=REGISTRATION_FILE, sha256=C.sha256_file(p), version=CONTRACT_VERSION, v1_file=REGISTRATION_FILE_V1, v1_sha256=C.sha256_file(p1) if p1.is_file() else None)
    if p1.is_file():
        return dict(file=REGISTRATION_FILE_V1, sha256=C.sha256_file(p1), version="v1")
    return dict(file=str(CONTRACT_MD.relative_to(REPO)).replace("\\", "/"), sha256=C.sha256_file(CONTRACT_MD) if CONTRACT_MD.is_file() else "", version=CONTRACT_VERSION)


M8_NS = uuid.uuid5(uuid.NAMESPACE_URL, "S26-M8-lineage-v1")
FIRST_OFFSET_US = 35_000_000
FIRST_OFFSET_NS = 35_000_000_000
URGENT_DEADLINE_MS = 800
NORMAL_DEADLINE_MS = 2_000
BURST_INTERVAL_US = 537_155
BURST_INTERVAL_NS = 537_155_000
BURST_COUNT, BURST_SIZE, BURST_PATTERN = 16, 8, "CCCDCCCD"
# 조민규 01:5x #3: 기존 동결 프로필 (SHA 아래 · 이쪽에 파일 없음 [D]) 평균 AVAILABLE — 합성 입력용 평균 기반 수치 · 새 M8 실측 성능 · 실제 이용률 90 % 보장 아님
BURST_PROFILE_SHA256 = "bd8d55c14e531e8629c5fcc84289f167f7e69cee3e7cc9dd761a25f345d4cc39"
BURST_C_GPU_MEAN_MS = 73.54419138
BURST_D_CPU_MEAN_MS = 241.71965499333334
BURST_INTERVAL_RAW_MS = 537.154788874   # 8 × max(96·C, 32·D) / (128 × 0.9) 올림 전
PREP_S, PREP_GAP_S = 60, 5
BASELINE_S, COOLING_S, COMMON_S, DRAIN_S, GATE_S, SETUP_S = 60, 90, 120, 30, 60, 180
WATCHDOG_S = 1_260
DEV_SEED, CONFIRM_SEED = 20261014, 20261022

# 정책 7 + NO_RUNTIME (policies_m8.json)
P_FIFO_SERIAL_CPU = "FIFO_SERIAL_CPU_V1"
P_FIFO_SERIAL_CG = "FIFO_SERIAL_CG_V1"
P_FIFO_SERIAL_CN = "FIFO_SERIAL_CN_V1"
P_EDD_SERIAL_CG = "EDD_SERIAL_CG_V1"
P_FIFO_PAIR_CG = "FIFO_PAIR_CG_V1"
P_FIFO_PAIR_CN = "FIFO_PAIR_CN_V1"
P_FIFO_WAIT_CG = "FIFO_WAIT_CG_V1"
P_NO_RUNTIME = "NO_RUNTIME_V1"
M8_POLICIES = (P_FIFO_SERIAL_CPU, P_FIFO_SERIAL_CG, P_FIFO_SERIAL_CN, P_EDD_SERIAL_CG, P_FIFO_PAIR_CG, P_FIFO_PAIR_CN, P_FIFO_WAIT_CG)
USED_KEYS_M8 = {
    P_FIFO_SERIAL_CPU: ("classification_CPU", "detection_CPU"),
    P_FIFO_SERIAL_CG: ("classification_GPU", "detection_CPU"), P_EDD_SERIAL_CG: ("classification_GPU", "detection_CPU"),
    P_FIFO_PAIR_CG: ("classification_GPU", "detection_CPU"), P_FIFO_WAIT_CG: ("classification_GPU", "detection_CPU"),
    P_FIFO_SERIAL_CN: ("classification_NPU", "detection_CPU"), P_FIFO_PAIR_CN: ("classification_NPU", "detection_CPU"),
    P_NO_RUNTIME: (),
}
SELECTION = {p: ("EDD" if p == P_EDD_SERIAL_CG else "FIFO") for p in M8_POLICIES}
CONCURRENCY = {p: ("PAIR" if p in (P_FIFO_PAIR_CG, P_FIFO_PAIR_CN) else "SERIAL") for p in M8_POLICIES}


def wait_args(wait_ms: int, first_n_bursts: int) -> dict:
    """조민규 01:5x #2: ID 하나 FIFO_WAIT_CG_V1 + 인자 · nominal_total_ms = wait × n (명목 · 실제 dose 는 앱이 따로 기록 · 명목으로 실제를 대신하지 않음)."""
    return dict(wait_ms=wait_ms, first_n_bursts=first_n_bursts, nominal_total_ms=wait_ms * first_n_bursts)


WAIT200X16 = wait_args(200, 16)      # 핵심 · 명목 3.2 s
WAIT200X12 = wait_args(200, 12)      # P2 대조 · 명목 2.4 s
WAIT1000X12 = wait_args(1_000, 12)   # P2 긴 대기 · 명목 12 s

BLOCK_M, BLOCK_NONE = "M", "NONE"
KEYS_M = ("classification_CPU", "classification_GPU", "classification_NPU", "detection_CPU", "detection_GPU")
KEYS_NONE = ()

# 실험 7 (MixreqContract.M8_EXPERIMENTS)
FN_ID, L64_ID, C252_ID, M128_ID, S128_ID, RECENT_ID, IDLE_ID = ("S26-M8-FN", "S26-M8-L64", "S26-M8-C252", "S26-M8-M128", "S26-M8-S128", "S26-M8-RECENT", "S26-M8-IDLE")
INDEX_MAX = {FN_ID: 99, L64_ID: 399, C252_ID: 399, M128_ID: 999, S128_ID: 399, RECENT_ID: 399, IDLE_ID: 199}
EXPERIMENT_IDS = tuple(INDEX_MAX)
PLAN_DIR = {FN_ID: "plan_m8fn", L64_ID: "plan_m8l64", C252_ID: "plan_m8c252", M128_ID: "plan_m8m128", S128_ID: "plan_m8s128", RECENT_ID: "plan_m8recent", IDLE_ID: "plan_m8idle"}


def arm(name, bank, policy, block=BLOCK_M, wait=None, prep="NONE"):
    return dict(name=name, bank=bank, policy=policy, block=block, wait=wait, prep=prep)


ARMS = {
    FN_ID: [arm("C252_CPU", "C252", P_FIFO_SERIAL_CPU), arm("C252_GPU", "C252", P_FIFO_SERIAL_CG), arm("C252_NPU", "C252", P_FIFO_SERIAL_CN),
            arm("M128_BASE", "M128", P_FIFO_SERIAL_CG), arm("M128_PAIR_G", "M128", P_FIFO_PAIR_CG), arm("M128_PAIR_N", "M128", P_FIFO_PAIR_CN)],
    L64_ID: [arm("L64_BASE", "L64", P_FIFO_SERIAL_CG), arm("L64_PAIR_G", "L64", P_FIFO_PAIR_CG)],
    C252_ID: [arm("C252_CPU", "C252", P_FIFO_SERIAL_CPU), arm("C252_GPU", "C252", P_FIFO_SERIAL_CG), arm("C252_NPU", "C252", P_FIFO_SERIAL_CN)],
    M128_ID: [arm("M128_BASE", "M128", P_FIFO_SERIAL_CG), arm("M128_ORDER", "M128", P_EDD_SERIAL_CG), arm("M128_PAIR_G", "M128", P_FIFO_PAIR_CG),
              arm("M128_WAIT200x16", "M128", P_FIFO_WAIT_CG, wait=WAIT200X16), arm("M128_NPU_SERIAL", "M128", P_FIFO_SERIAL_CN), arm("M128_PAIR_N", "M128", P_FIFO_PAIR_CN),
              arm("M128_WAIT200x12", "M128", P_FIFO_WAIT_CG, wait=WAIT200X12), arm("M128_WAIT1000x12", "M128", P_FIFO_WAIT_CG, wait=WAIT1000X12)],
    S128_ID: [arm("SMOOTH128_BASE", "SMOOTH128", P_FIFO_SERIAL_CG), arm("SMOOTH128_ORDER", "SMOOTH128", P_EDD_SERIAL_CG), arm("SMOOTH128_PAIR_G", "SMOOTH128", P_FIFO_PAIR_CG)],
    RECENT_ID: [arm("RECENT_CPU60_C252_CPU", "C252", P_FIFO_SERIAL_CPU, prep="CPU60"), arm("RECENT_CPU60_C252_GPU", "C252", P_FIFO_SERIAL_CG, prep="CPU60"),
                arm("RECENT_CPU60_C252_NPU", "C252", P_FIFO_SERIAL_CN, prep="CPU60"), arm("RECENT_IDLE60_C252_CPU", "C252", P_FIFO_SERIAL_CPU, prep="IDLE60"),
                arm("RECENT_IDLE60_C252_GPU", "C252", P_FIFO_SERIAL_CG, prep="IDLE60"), arm("RECENT_IDLE60_C252_NPU", "C252", P_FIFO_SERIAL_CN, prep="IDLE60")],
    IDLE_ID: [arm("IDLE_NO_RUNTIME", "NONE", P_NO_RUNTIME, block=BLOCK_NONE), arm("IDLE_RESIDENT", "NONE", P_FIFO_SERIAL_CPU)],
}
BANK_COUNT = dict(L64=64, C252=252, M128=128, SMOOTH128=128, NONE=0)


def main_id(experiment_id: str) -> str:
    base = experiment_id[:-6] if experiment_id.endswith("-SMOKE") else experiment_id
    if base not in INDEX_MAX:
        raise ValueError(f"not an M8 experiment {experiment_id}")
    return base


def is_m8(experiment_id: str) -> bool:
    try:
        main_id(experiment_id)
        return True
    except ValueError:
        return False


def arms(experiment_id: str) -> list[dict]:
    return ARMS[main_id(experiment_id)]


def arm_of(experiment_id: str, index: int) -> dict:
    a = arms(experiment_id)
    return a[index % len(a)]


def repetition_of(experiment_id: str, index: int) -> int:
    return index // len(arms(experiment_id))


def index_of(experiment_id: str, arm_name: str, repetition: int) -> int:
    a = arms(experiment_id)
    pos = next(i for i, x in enumerate(a) if x["name"] == arm_name)
    return pos + len(a) * repetition


def dev_count(experiment_id: str) -> int:
    return (INDEX_MAX[main_id(experiment_id)] + 1) // 2


def analysis_split_of(experiment_id: str, index: int) -> str:
    return "dev" if index < dev_count(experiment_id) else "confirm"


def session_id(experiment_id: str, index: int) -> str:
    return str(uuid.uuid5(M8_NS, f"{experiment_id}/{index}"))


def request_id(sid: str, ordinal: int) -> str:
    return str(uuid.uuid5(M8_NS, f"{sid}/{ordinal}"))


def burst_interval_raw_ms(s_cgpu_ms: float, s_dcpu_ms: float) -> float:
    """조민규 #3: 8 × max(96·s_CGPU, 32·s_DCPU) / (128 × 0.9) (ms · 올림 전)."""
    return 8.0 * max(96.0 * s_cgpu_ms, 32.0 * s_dcpu_ms) / (128.0 * 0.9)


def burst_interval_us(s_cgpu_ms: float, s_dcpu_ms: float) -> int:
    return math.ceil(burst_interval_raw_ms(s_cgpu_ms, s_dcpu_ms) * 1000.0)


def burst_interval_ns(s_cgpu_ms: float, s_dcpu_ms: float) -> int:
    return burst_interval_us(s_cgpu_ms, s_dcpu_ms) * 1000


def slots_ns(bank: str) -> list[tuple[str, int]]:
    """(task, offset_ns) — M8Plan.slotsNs 와 같은 식 (조민규 #4: SMOOTH128 = 35,000,000,000 + floor(i × 15 × 537,155,000 / 127))."""
    if bank == "L64":
        return [("classification" if i % 2 == 0 else "detection", FIRST_OFFSET_NS + 1_000_000_000 * i) for i in range(64)]
    if bank == "C252":
        return [("classification", FIRST_OFFSET_NS + 333_200_000 * i) for i in range(252)]
    if bank == "M128":
        return [("classification" if BURST_PATTERN[i % BURST_SIZE] == "C" else "detection", FIRST_OFFSET_NS + BURST_INTERVAL_NS * (i // BURST_SIZE)) for i in range(BURST_COUNT * BURST_SIZE)]
    if bank == "SMOOTH128":
        return [(t, FIRST_OFFSET_NS + (i * 15 * BURST_INTERVAL_NS) // 127) for i, (t, _) in enumerate(slots_ns("M128"))]
    if bank == "NONE":
        return []
    raise ValueError(f"unknown bank {bank}")


def slots(bank: str) -> list[tuple[str, int]]:
    """(task, offset_us) = floor(ns / 1,000) — 표시 · 대조용."""
    return [(t, ns // 1000) for t, ns in slots_ns(bank)]


def bank_requests(sid: str, bank: str) -> list[dict]:
    rows = []
    for ordinal, (task, offset_ns) in enumerate(slots_ns(bank)):
        urgent = task == "classification"
        rows.append(dict(request_id=request_id(sid, ordinal), ordinal=ordinal, task_id=task, priority="urgent" if urgent else "normal",
                         offset_ms=offset_ns // 1_000_000, deadline_ms=URGENT_DEADLINE_MS if urgent else NORMAL_DEADLINE_MS, offset_us=offset_ns // 1000, offset_ns=offset_ns))
    validate_bank(rows, bank)
    return rows


def validate_bank(rows: list[dict], bank: str) -> None:
    expected = slots_ns(bank)
    if len(rows) != BANK_COUNT[bank] or len({r["request_id"] for r in rows}) != BANK_COUNT[bank]:
        raise ValueError(f"m8 request count/id ({bank})")
    for i, (q, (task, off)) in enumerate(zip(rows, expected)):
        urgent = task == "classification"
        if q["ordinal"] != i or q["task_id"] != task or q["offset_ns"] != off or q["offset_us"] != off // 1000 or q["offset_ms"] != off // 1_000_000:
            raise ValueError(f"m8 request {i} task/offset")
        if q["priority"] != ("urgent" if urgent else "normal") or q["deadline_ms"] != (URGENT_DEADLINE_MS if urgent else NORMAL_DEADLINE_MS):
            raise ValueError(f"m8 request {i} priority/deadline")


def requests(experiment_id: str, index: int, sid: str) -> list[dict]:
    return bank_requests(sid, arm_of(experiment_id, index)["bank"])


def burst_index_of(rows: list[dict]) -> dict[str, int]:
    times = sorted({r["offset_ns"] for r in rows})
    of = {t: k for k, t in enumerate(times)}
    return {r["request_id"]: of[r["offset_ns"]] for r in rows}


def lane_for(policy: str, task: str) -> str:
    if task == "detection" or policy == P_FIFO_SERIAL_CPU:
        return "CPU"
    if policy in (P_FIFO_SERIAL_CN, P_FIFO_PAIR_CN):
        return "NPU"
    if policy in M8_POLICIES:
        return "GPU"
    raise ValueError(f"unknown M8 policy {policy}")


def phases(block: str) -> dict:
    return dict(setup_s=SETUP_S, gate_s=GATE_S, baseline_s=BASELINE_S, common_s=COMMON_S, drain_s=DRAIN_S, cooling_s=COOLING_S)


# ---------------------------------------------------------------- 운영 상수 (gate_m8.json · session_m8.json · 영훈 추가 지시 10/14 22:2x)
SOC_MIN_START = 20            # 영훈 운영 결정 (조민규 40~80 과 다름 · 등록 D-0 명시 · 소급 없음) · 상한 없음
SOC_MAX_START = 100
SOC_NEW_BAND = (40, 80)       # 참고 열만
HAL_PRE_START_S = 60          # 앱 시작 ≥ 60 s 전 호스트 HAL
HAL_AFTER_ORIGIN_S = 300      # common 0 + 300 s 까지
RUN_GAP_MIN_S = 90
# Tref v2 (조민규 01:5x #5 · m8_gate TREF_DAY_FIRST_STABLE_AP60_V2): 측정일 시작 (유휴 ≥ 1,200 s 뒤) 같은 준비·유휴 조건에서 처음 확보한 안정 60 s AP 창의 중앙값 · 블록 안 재산출 0
TREF_SENSOR = "AP"
TREF_IDLE_S = 1200            # 직전 실행 끝/충전 분리 뒤 유휴 ≥ 1,200 s (v1 과 같은 상수 · 측정일 시작 조건)
TREF_WINDOW_S = 60            # 안정 60 s 창 (AP 중앙값 = Tref_day · SKIN 중앙값은 기록)
TREF_MIN_SAMPLES = 20         # 60 s / HAL 2.3 s ≈ 26 표본 → 최소 20 (결측 허용 ≤ 6)
TREF_MAX_GAP_S = 5.0          # 창 안 표본 간격 상한 (host HAL 2.3 s 의 2배 + 여유)
TREF_SEARCH_MAX_S = 1200      # 유휴 뒤 안정 창 탐색 ≤ 1,200 s · 없으면 "Tref 판정 불가" 원장 + 최소 |기울기| 창 (stable_miss)
TREF_BAND_C = 0.5
GATE_WINDOW_S = 60            # START: 직전 60 s AP 중앙값 ∈ Tref ± 0.5 · |AP|,|SKIN| 기울기 ≤ 0.1 (실제 표본 시각)
GATE_MIN_SAMPLES = 20         # 미만 · gap > 5 s · AP 결측 = "판정 불가" (REJECT 아님 · 원장)
GATE_MAX_GAP_S = 5.0
SLOPE_MAX_C_PER_MIN = 0.1
GATE_POLL_S = 30
GATE_MAX_WAIT_S = 600         # 10 min → PRESTART_REJECT (판정 불가가 이어지면 GATE_UNDECIDABLE · REJECT 와 구분)
SAFETY_SKIN_C = 43.0
SAFETY_THERMAL_STATUS = 3
CHARGE_TO_FIRST_RUN_MIN_S = 1200
HAL_TARGET_PERIOD_S = 2.3
APP_MAX_GAP_S = 2.5
HAL_MAX_GAP_S = 5.0
APP_PRE_T0_MIN_S = 60
APP_POST_T0_MIN_S = 210
APP_POINTS_S = (0.0, 35.0, 120.0, 180.0)
HAL_AP_POINTS_S = (35.0, 180.0)
HAL_IV_POINTS_S = (0.0, 180.0)


# ---------------------------------------------------------------- registration into the shared host tables (process-local)
_ACTIVE = False
_ORIG = {}


def activate() -> None:
    """Register M8 rows (idempotent). mixreq_session · warmup gate · session cap · SOC band all read these tables."""
    global _ACTIVE
    if _ACTIVE:
        return
    for eid in EXPERIMENT_IDS:
        C.EXPERIMENTS.setdefault(eid, dict(smoke_id=f"{eid}-SMOKE", request_count=0, common_s=COMMON_S, registration_version=8, kind="m8", plan_dir=PLAN_DIR[eid]))
    C.PHASES.setdefault(BLOCK_NONE, dict(C.PHASES["N"]))
    policy_ref.BLOCK_KEYS.setdefault(BLOCK_NONE, KEYS_NONE)
    for p, keys in USED_KEYS_M8.items():
        policy_ref.USED_KEYS.setdefault(p, keys)
    _ORIG["session_cap_s"] = C.session_cap_s
    _ORIG["listing_period_s"] = C.listing_period_s
    _ORIG["SOC"] = (M6.SOC_MIN, M6.SOC_MAX)

    def cap(experiment_id: str, block: str) -> int:
        if is_m8(experiment_id):
            return SETUP_S + GATE_S + BASELINE_S + PREP_S + PREP_GAP_S + COMMON_S + DRAIN_S + COOLING_S + 240   # 845 (M8 phases + host margin)
        return _ORIG["session_cap_s"](experiment_id, block)

    def listing(experiment_id: str) -> float:
        return 1.0 if is_m8(experiment_id) else _ORIG["listing_period_s"](experiment_id)

    C.session_cap_s = cap
    C.listing_period_s = listing
    M6.SOC_MIN, M6.SOC_MAX = SOC_MIN_START, SOC_MAX_START
    _ACTIVE = True


def deactivate() -> None:
    global _ACTIVE
    if not _ACTIVE:
        return
    C.session_cap_s = _ORIG["session_cap_s"]
    C.listing_period_s = _ORIG["listing_period_s"]
    M6.SOC_MIN, M6.SOC_MAX = _ORIG["SOC"]
    _ACTIVE = False


def slope_c_per_min(points: list[tuple[float, float]]) -> float | None:
    pts = [(t, v) for t, v in points if t is not None and v is not None]
    if len(pts) < 2:
        return None
    n = len(pts)
    mt = sum(t for t, _ in pts) / n
    mv = sum(v for _, v in pts) / n
    sxx = sum((t - mt) ** 2 for t, _ in pts)
    if sxx == 0:
        return None
    return sum((t - mt) * (v - mv) for t, v in pts) / sxx * 60.0
