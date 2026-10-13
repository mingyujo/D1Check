"""M7 shared tables (2026-10-13) — S26 확대 반복 (조민규 10/13 요청): K 3조건 × 세트 5 · P 5블록 · 준비 P 10 · 지속 S 12. Imported by the m7_* tools only.

Registration (OneDrive bytes, commits ① 09bc97d9 (v1) · 9395151d (v2) of branch s26-m6):
  d1sim/docs/M7_확대반복_사전등록_v2.md SHA-256 c3da26cc… = v1 (899d63c6…) 전문 + 머리 단락 (M7-apk 전환 · index 는 M6 · R4 자리 뒤에 잇는다)

activate() / extended() EXTEND the m6_common tables at run time, only inside the m7 tools (m6_common.py · mixreq_common.py are unchanged, import only;
importing this module changes nothing — test_m6 and test_m7 share one pytest process):
  m6_common.P_ORDER     = M6 rows 0..11 + M7 P rows 12..41 (등록 §2-3) + 준비 rows 42..51 (§1-2)   → m6_plan.manifest / m6_common.requests work for M7 indices
  m6_common.REGISTRATION = the M7 v2 registration (so M7 manifests · validated.json carry the M7 registration)
The app (request-runner M6Plan.ORDER_M7_P · ORDER_M7_PREP · S_ORDER · MixreqContract index 상한 51 / 18 / 27) has the same rows — M7-apk.
Nothing here reads a device.
"""
from __future__ import annotations

import contextlib
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import mixreq_common as C  # noqa: E402
import policy_ref  # noqa: E402
import m6_common as M  # noqa: E402

REGISTRATION = dict(file="d1sim/docs/M7_확대반복_사전등록_v2.md",
                    sha256="c3da26cc05c496ed4ebaf718f9c7d3293204e5223e0830a1fb0c378968a226bb",
                    commit="9395151ddd22482b70a029fc72f8733db8bedb51", time="2026-10-13T21:03:58+09:00")
REGISTRATION_V1 = dict(file="d1sim/docs/M7_확대반복_사전등록_v1.md",
                       sha256="899d63c68c3fe0c8a4e940e82a8bb85b5c57160fc17b498d1ae720c2eaca2b43",
                       commit="09bc97d99f19f49b50ba0551d55a7f77ae578cf0", time="2026-10-13T20:40:42+09:00")
M6_REGISTRATION = dict(M.REGISTRATION)   # kept for the cycle = m6 rows
CYCLE = "m7"

# ---------------------------------------------------------------- P (항목 2 · 등록 §2-3) — index 12..41, 블록 6 × 5
P_BLOCKS = {
    "D1": ("L-C", "B-C", "L-G", "B-G", "L-N", "B-N"),
    "D2": ("B-G", "L-G", "B-N", "L-N", "B-C", "L-C"),
    "D3": ("L-N", "B-N", "L-C", "B-C", "L-G", "B-G"),
    "K1": ("B-C", "L-C", "B-N", "L-N", "B-G", "L-G"),
    "K2": ("L-G", "B-G", "L-C", "B-C", "L-N", "B-N"),
}
P_BLOCK_ORDER = ("D1", "D2", "D3", "K1", "K2")
P_FIRST = 12
P_DEV_BLOCKS = ("D1", "D2", "D3")
P_CONFIRM_BLOCKS = ("K1", "K2")
P_SMOKE_INDEX = 12            # S26-M6-P-SMOKE index 12 = L-C (M6 smoke index 3 a1 is on the device)
P_ROWS = tuple(x for b in P_BLOCK_ORDER for x in P_BLOCKS[b])          # 30 rows → index 12..41
# ---------------------------------------------------------------- 준비 P (항목 1 B · C · 등록 §1-2) — index 42..51
PREP_FIRST = 42
PREP_ROWS = tuple("L-C" if i % 2 == 0 else "L-N" for i in range(10))   # 세트 n: L-C = 42 + 2(n−1) · L-N = 43 + 2(n−1)
# ---------------------------------------------------------------- K (항목 1 · 등록 §1-5) — index 4..18, 세트 5 × 조건 자리
K_FIRST = 4
K_SETS = {1: "ABC", 2: "BCA", 3: "CAB", 4: "ACB", 5: "BAC"}            # 라틴 방진 · 결과 전 고정
K_DEV_SETS = (1, 2, 3)
K_CONFIRM_SETS = (4, 5)
K_SMOKE_INDEX = 4             # S26-M6-K-SMOKE index 4 (M6 smoke index 0 a1 is on the device)
K_SMOKE_TIME_SCALE = 10
PREP_LOAD_OF_COND = {"B": "L-C", "C": "L-N"}
# ---------------------------------------------------------------- S (항목 4 · 등록 §4-4) — S26-MIXREQ-03 index 16..27
S_ID = "S26-MIXREQ-03"
S_SMOKE_ID = "S26-MIXREQ-03-SMOKE"
S_FIRST = 16
S_ORDER = ("C", "G", "N", "N", "G", "C", "G", "C", "N", "N", "C", "G")  # S1..S12 (개발 1..6 · 확인 7..12)
S_DEV = tuple(range(16, 22))
S_CONFIRM = tuple(range(22, 28))
S_SMOKE_INDEX = 16
S_SMOKE_TIME_SCALE = 10
S_SMOKE_REQUESTS = C.SMOKE_REQUEST_COUNT   # 24 (R4 S2 smoke form) at time_scale 10
S_BLOCK_OF_LETTER = {"C": "A", "G": "A", "N": "N"}                      # R4 (S) 와 같음 · 블록 M 아님 (등록 §4-2)

# ---------------------------------------------------------------- 운영 상수 (등록 §1-2 · §2-4 · §2-6 · §4-3 · §4-4 · 프롬프트 1단계-4)
IDLE_MIN_S = 1200             # A: 직전 run log 끝 → K 앱 시작 ≥ 1,200 s
STABLE_WINDOW_S = 120         # A: 시작 직전 120 s 기울기
STABLE_SLOPE_C_PER_MIN = 0.1  # |AP| · |SKIN| 기울기 ≤ 0.1 ℃/min → stable
STABLE_RECHECK_S = 60
STABLE_EXTRA_MAX_S = 1200     # 미달이면 60 s 마다 재검사 · 추가 1,200 s 넘으면 stable_miss 로 진행
PREP_TO_K_GAP_S = 90          # B · C: 준비 run log 끝 → K 앱 시작 90 s (허용 90 ~ 100 · 넘으면 gap_over)
PREP_TO_K_GAP_MAX_S = 100
RUN_GAP_MIN_S = 90            # 실행 사이 ≥ 90 s (run log 기준 — m6_session 이 지킨다)
HAL_PRE_START_BC_S = 120      # B · C: 연속 HAL 은 준비 P 앱 시작 ≥ 120 s 전부터
HAL_PRE_START_P_S = 60        # P: 세션 앱 시작 ≥ 60 s 전부터
HAL_P_AFTER_ORIGIN_S = 300    # P: 원점 + 300 s 까지
HAL_S_AFTER_WINDOW_S = 600    # S: 창 끝 + 600 s 까지
S_GAP_MIN_S = 600             # S 세션 사이 ≥ 600 s
HAL_TARGET_PERIOD_S = 2.3
SAFETY_SKIN_C = 43.0          # 폰 안전 멈춤 (프롬프트 규칙)
SAFETY_THERMAL_STATUS = 3
CHARGE_TO_FIRST_RUN_MIN_S = 1200   # 분리 → 블록 첫 실행 ≥ 1,200 s (등록 §2-4)

LETTER_POLICY = dict(M.LETTER_POLICY)

# ---------------------------------------------------------------- the extended tables (applied to m6_common only by activate() / extended())
M6_P_ORDER = tuple(M.P_ORDER)                                  # 0..11 (M6 등록 §3-5)
EXTENDED_P_ORDER = M6_P_ORDER + P_ROWS + PREP_ROWS             # 0..11 M6 · 12..41 M7 P · 42..51 준비 = request-runner M6Plan.ORDER
assert len(EXTENDED_P_ORDER) == 52 and M6_P_ORDER == ("L-C", "B-G", "L-N", "B-C", "L-G", "B-N", "B-N", "L-G", "B-C", "L-N", "B-G", "L-C")


def activate() -> None:
    """Point m6_common at the M7 tables (process-local: m7_plan while building · m7_session before m6_session.main())."""
    M.P_ORDER = EXTENDED_P_ORDER
    M.REGISTRATION = dict(REGISTRATION)


def deactivate() -> None:
    M.P_ORDER = M6_P_ORDER
    M.REGISTRATION = dict(M6_REGISTRATION)


@contextlib.contextmanager
def extended():
    activate()
    try:
        yield
    finally:
        deactivate()


def load_of(index: int) -> str:
    return EXTENDED_P_ORDER[index].split("-")[0]


def letter_of(index: int) -> str:
    return EXTENDED_P_ORDER[index].split("-")[1]


def policy_of(index: int) -> str:
    return LETTER_POLICY[letter_of(index)]


def p_index(block: str, pos: int) -> int:
    """등록 §2-3 블록 (D1 · D2 · D3 · K1 · K2) 의 pos (0..5) 번째 → plan index."""
    return P_FIRST + P_BLOCK_ORDER.index(block) * 6 + pos


def p_block_of(index: int) -> tuple[str, int]:
    if not P_FIRST <= index < PREP_FIRST:
        raise ValueError(f"not an M7 P index {index}")
    k = index - P_FIRST
    return P_BLOCK_ORDER[k // 6], k % 6


def p_analysis_split(index: int) -> str:
    return "dev" if p_block_of(index)[0] in P_DEV_BLOCKS else "confirm"


def prep_index(set_no: int, cond: str) -> int:
    """세트 n (1..5) · 조건 B (L-C) / C (L-N) 의 준비 P index (42 + 2(n−1) + {B: 0, C: 1})."""
    if set_no not in K_SETS or cond not in PREP_LOAD_OF_COND:
        raise ValueError(f"prep set/cond {set_no} {cond}")
    return PREP_FIRST + 2 * (set_no - 1) + (0 if cond == "B" else 1)


def prep_set_of(index: int) -> tuple[int, str]:
    if not PREP_FIRST <= index < PREP_FIRST + 10:
        raise ValueError(f"not a prep index {index}")
    k = index - PREP_FIRST
    return k // 2 + 1, "B" if k % 2 == 0 else "C"


def k_index(set_no: int, pos: int) -> int:
    """세트 s (1..5) 의 p (0..2) 번째 K → plan index 4 + 3(s−1) + p."""
    return K_FIRST + 3 * (set_no - 1) + pos


def k_cond(set_no: int, pos: int) -> str:
    return K_SETS[set_no][pos]


def k_set_of(index: int) -> tuple[int, int, str]:
    if not K_FIRST <= index < K_FIRST + 15:
        raise ValueError(f"not an M7 K index {index}")
    k = index - K_FIRST
    s, p = k // 3 + 1, k % 3
    return s, p, k_cond(s, p)


def k_analysis_split(index: int) -> str:
    return "dev" if k_set_of(index)[0] in K_DEV_SETS else "confirm"


def s_letter_of(index: int) -> str:
    if not S_FIRST <= index < S_FIRST + 12:
        raise ValueError(f"not an M7 S index {index}")
    return S_ORDER[index - S_FIRST]


def s_label(index: int) -> str:
    return f"S{index - S_FIRST + 1}"


def s_analysis_split(index: int) -> str:
    return "dev" if index in S_DEV else "confirm"


def latin_square_ok(sets: dict[int, str]) -> bool:
    """개발 세트 1..3: 세 조건이 1 · 2 · 3 번째 자리에 한 번씩 (라틴 방진) · 확인 4 · 5 는 서로 다른 순서."""
    dev = [sets[i] for i in K_DEV_SETS]
    for pos in range(3):
        if {s[pos] for s in dev} != {"A", "B", "C"}:
            return False
    return all(sorted(s) == ["A", "B", "C"] for s in sets.values()) and len(set(sets.values())) == len(sets)


def p_positions_ok(blocks: dict[str, tuple[str, ...]]) -> bool:
    """등록 §2-3: 각 개발 블록에 여섯 조합이 한 번씩 · 정책 C/G/N 이 개발 블록의 1 · 2 · 3 번째 쌍 자리에 한 번씩."""
    combos = {"L-C", "B-C", "L-G", "B-G", "L-N", "B-N"}
    if any(set(v) != combos for v in blocks.values()):
        return False
    for letter in "CGN":
        pos = {next(i for i, x in enumerate(blocks[b]) if x.endswith(letter)) // 2 for b in P_DEV_BLOCKS}
        if pos != {0, 1, 2}:
            return False
    return True


# ---------------------------------------------------------------- 계산 (기울기 · 간격 · 덮임) — 기술만 · 판정 아님
def slope_c_per_min(points: list[tuple[float, float]]) -> float | None:
    """Least-squares slope of (t_s, value_c) in ℃/min. None when < 2 distinct times."""
    pts = [(t, v) for t, v in points if t is not None and v is not None]
    if len(pts) < 2:
        return None
    n = len(pts)
    mt = sum(t for t, _ in pts) / n
    mv = sum(v for _, v in pts) / n
    sxx = sum((t - mt) ** 2 for t, _ in pts)
    if sxx == 0:
        return None
    sxy = sum((t - mt) * (v - mv) for t, v in pts)
    return (sxy / sxx) * 60.0


def stable_from_hal(rows: list[dict], t_end: float, window_s: float = STABLE_WINDOW_S, limit: float = STABLE_SLOPE_C_PER_MIN) -> dict:
    """rows: hal_cont rows (host_epoch_s · AP · SKIN as floats or None). Slope over [t_end − window, t_end]. 등록 §1-2 A."""
    sel = [r for r in rows if r.get("host_epoch_s") is not None and t_end - window_s <= r["host_epoch_s"] <= t_end]
    ap = slope_c_per_min([(r["host_epoch_s"], r.get("AP")) for r in sel])
    skin = slope_c_per_min([(r["host_epoch_s"], r.get("SKIN")) for r in sel])
    ok = ap is not None and skin is not None and abs(ap) <= limit and abs(skin) <= limit
    return dict(stable=ok, ap_slope_c_per_min=ap, skin_slope_c_per_min=skin, samples=len(sel), window_s=window_s, limit_c_per_min=limit,
                span_s=(sel[-1]["host_epoch_s"] - sel[0]["host_epoch_s"]) if len(sel) >= 2 else None)


def gap_record(prev_end_epoch: float | None, start_epoch: float | None, target: float = PREP_TO_K_GAP_S, max_ok: float = PREP_TO_K_GAP_MAX_S) -> dict:
    """준비 run log 끝 → K 앱 시작 간격 (실제값 · 허용 90 ~ 100 · 넘으면 gap_over 표시 · 무효 아님)."""
    if prev_end_epoch is None or start_epoch is None:
        return dict(gap_s=None, gap_over=None, target_s=target, max_ok_s=max_ok)
    g = start_epoch - prev_end_epoch
    return dict(gap_s=round(g, 3), gap_over=g > max_ok, gap_under=g < target, target_s=target, max_ok_s=max_ok)


def coverage_after(last_available_epoch: float | None, last_sample_epoch: float | None) -> float | None:
    """마지막 lane_available (host) 뒤 마지막 표본까지 (s) — power_sample · hal_cont 각각."""
    if last_available_epoch is None or last_sample_epoch is None:
        return None
    return round(last_sample_epoch - last_available_epoch, 3)
