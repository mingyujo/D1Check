"""M8 host gate v2 (contract_v2/gate_m8.json · 조민규 01:5x #5 확정 · 영훈 운영 결정 10/14: SOC 시작 하한 20 · 상한 없음) — pure functions over hal_cont rows + a small CLI (phone 0).

  Tref_day (TREF_DAY_FIRST_STABLE_AP60_V2): 측정일 시작 시 (첫 DEV 정책 실행 전 · 직전 실행 끝/충전 분리 뒤 ≥ 1,200 s 유휴 · 같은 준비·유휴 조건: plugged 0 · 화면 켜짐 · 비행기 1 · 앱 추론 0 · 호스트 HAL 2.3 s)
            처음 확보한 "안정 60 s" 창의 AP 중앙값. 안정 = 실제 표본 시각으로 계산한 |AP 기울기| ≤ 0.1 ℃/min · 표본 ≥ 20 · 최대 gap ≤ 5 s. 창 끝을 표본마다 옮기며 첫 성립 창을 쓴다 (≤ 1,200 s 탐색 ·
            없으면 "Tref 판정 불가" 원장 + 최소 |기울기| 창을 stable_miss 로 표시해 사용). 그 날 (드라이버 시작 날짜) 에 한 번 고정 · 블록 안 재산출 0 · 결과/거절 횟수 보고 옮기지 않음.
  START:    직전 60 s AP 중앙값 ∈ Tref_day ± 0.5 ∧ |AP|, |SKIN| 기울기 ≤ 0.1 ℃/min ∧ SOC ≥ 20 ∧ plugged 0 → start · 아니면 30 s 폴 · 최대 600 s → PRESTART_REJECT(reason).
            판정 불가 (표본 < 20 · gap > 5 s · AP 결측) = decidable false → REJECT 가 아니라 "판정 불가" 원장 행 (폴 계속 · 600 s 뒤에도 불가면 GATE_UNDECIDABLE · REJECT 와 구분).
  RECENT_CPU 의 gate 도 준비 (prep) 전 = 앱 시작 전 호스트에서 (같은 규칙). 모든 판정 · 폴링 값 · Tref 는 ledger 행으로 (m8_driver 가 기록).
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import m8_common as M8  # noqa: E402

ALGORITHM = "TREF_DAY_FIRST_STABLE_AP60_V2"
STATUS = "조민규 확정 (10/15 01:5x #5) · 첫 DEV 정책 실행 전 고정 · 블록 안 재산출 0 · CONFIRM 전 봉인"
SENSOR = M8.TREF_SENSOR   # "AP"


def window(rows: list[dict], t_end: float, seconds: float) -> list[dict]:
    return [r for r in rows if r.get("host_epoch_s") is not None and t_end - seconds <= r["host_epoch_s"] <= t_end]


def _max_gap(sel: list[dict]) -> float | None:
    ts = [r["host_epoch_s"] for r in sel]
    return max((b - a for a, b in zip(ts, ts[1:])), default=None) if len(ts) >= 2 else None


def stats(rows: list[dict], t_end: float, seconds: float) -> dict:
    """한 창 (끝 = t_end · 길이 seconds) 의 표본 수 · AP/SKIN 중앙값 · 실제 표본 시각 기울기 · 최대 gap · 결측 수."""
    sel = window(rows, t_end, seconds)
    skin = [r["SKIN"] for r in sel if r.get("SKIN") is not None]
    ap = [r["AP"] for r in sel if r.get("AP") is not None]
    return dict(samples=len(sel), ap_samples=len(ap), ap_missing=len(sel) - len(ap), skin_median=round(statistics.median(skin), 2) if skin else None,
                ap_median=round(statistics.median(ap), 2) if ap else None,
                skin_slope_c_per_min=M8.slope_c_per_min([(r["host_epoch_s"], r.get("SKIN")) for r in sel]), ap_slope_c_per_min=M8.slope_c_per_min([(r["host_epoch_s"], r.get("AP")) for r in sel]),
                max_gap_s=_max_gap(sel), span_s=(sel[-1]["host_epoch_s"] - sel[0]["host_epoch_s"]) if len(sel) >= 2 else None, window_s=seconds,
                window_start_epoch=(sel[0]["host_epoch_s"] if sel else None), window_end_epoch=(sel[-1]["host_epoch_s"] if sel else None))


def decidable(s: dict, min_samples: int, max_gap_s: float) -> tuple[bool, str | None]:
    """판정 가능 조건 (결측 · gap · 표본 수) — 아니면 이유 (REJECT 가 아님)."""
    if s["ap_samples"] < min_samples:
        return False, f"undecidable: AP samples {s['ap_samples']} < {min_samples} (window {s['window_s']} s)"
    if s["max_gap_s"] is None or s["max_gap_s"] > max_gap_s:
        return False, f"undecidable: max gap {s['max_gap_s']} s > {max_gap_s} s"
    if s["ap_median"] is None or s["ap_slope_c_per_min"] is None:
        return False, "undecidable: AP median/slope missing"
    return True, None


def first_stable_window(rows: list[dict], t_from: float, t_until: float) -> dict:
    """[t_from, t_until] 안에서 창 끝을 실제 표본 시각마다 옮기며 처음 성립하는 안정 60 s AP 창. 없으면 stable false + 최소 |기울기| 창 (best)."""
    ends = sorted(r["host_epoch_s"] for r in rows if r.get("host_epoch_s") is not None and t_from + M8.TREF_WINDOW_S <= r["host_epoch_s"] <= t_until)
    best = None
    checked = 0
    for t_end in ends:
        s = stats([r for r in rows if r.get("host_epoch_s") is not None and r["host_epoch_s"] >= t_from], t_end, M8.TREF_WINDOW_S)
        ok, why = decidable(s, M8.TREF_MIN_SAMPLES, M8.TREF_MAX_GAP_S)
        checked += 1
        if not ok:
            continue
        slope = abs(s["ap_slope_c_per_min"])
        if best is None or slope < abs(best["ap_slope_c_per_min"]):
            best = s
        if slope <= M8.SLOPE_MAX_C_PER_MIN:
            return dict(stable=True, checked_windows=checked, **s)
    if best is None:
        return dict(stable=False, checked_windows=checked, reason="no decidable 60 s window (samples/gap/missing)", ap_median=None, ap_slope_c_per_min=None, skin_median=None,
                    skin_slope_c_per_min=None, samples=0, ap_samples=0, ap_missing=0, max_gap_s=None, span_s=None, window_s=M8.TREF_WINDOW_S, window_start_epoch=None, window_end_epoch=None)
    return dict(stable=False, checked_windows=checked, reason=f"no window with |AP slope| <= {M8.SLOPE_MAX_C_PER_MIN} (best {round(best['ap_slope_c_per_min'], 3)})", **best)


def tref_candidate(rows: list[dict], t_from: float, t_until: float) -> dict:
    """Tref_day 후보 = 처음 확보한 안정 60 s 창의 AP 중앙값 (SKIN 중앙값은 기록만)."""
    w = first_stable_window(rows, t_from, t_until)
    return dict(algorithm=ALGORITHM, status=STATUS, sensor=SENSOR, tref_c=w.get("ap_median"), skin_ref_c=w.get("skin_median"), **w,
                search_from_epoch=t_from, search_until_epoch=t_until, idle_min_s=M8.TREF_IDLE_S, band_c=M8.TREF_BAND_C, slope_max=M8.SLOPE_MAX_C_PER_MIN,
                min_samples=M8.TREF_MIN_SAMPLES, max_gap_s_rule=M8.TREF_MAX_GAP_S, hal_period_s=M8.HAL_TARGET_PERIOD_S)


def start_decision(rows: list[dict], t_now: float, tref_c: float | None, soc: int | None, plugged: bool | None) -> dict:
    """한 번의 START 판정 (직전 60 s · AP 기준). reason = None → START · decidable false = 판정 불가 (REJECT 아님)."""
    s = stats(rows, t_now, M8.GATE_WINDOW_S)
    ok, why = decidable(s, M8.GATE_MIN_SAMPLES, M8.GATE_MAX_GAP_S)
    reasons = []
    if soc is None or soc < M8.SOC_MIN_START:
        reasons.append(f"soc {soc} < {M8.SOC_MIN_START}")
    if plugged:
        reasons.append("plugged")
    if tref_c is None:
        reasons.append("tref: no Tref_day")
    elif not ok:
        reasons.append(why)
    else:
        if abs(s["ap_median"] - tref_c) > M8.TREF_BAND_C:
            reasons.append(f"tref: AP median {s['ap_median']} outside {tref_c} ± {M8.TREF_BAND_C}")
        for name in ("ap_slope_c_per_min", "skin_slope_c_per_min"):
            v = s[name]
            if v is None or abs(v) > M8.SLOPE_MAX_C_PER_MIN:
                reasons.append(f"slope: {name} {None if v is None else round(v, 3)} > {M8.SLOPE_MAX_C_PER_MIN}")
    return dict(start=not reasons, decidable=ok, reasons=reasons, tref_c=tref_c, sensor=SENSOR, soc=soc, plugged=plugged, soc_min=M8.SOC_MIN_START,
                soc_new_band_reference=M8.SOC_NEW_BAND, soc_in_new_band_reference_only=(soc is not None and M8.SOC_NEW_BAND[0] <= soc <= M8.SOC_NEW_BAND[1]), **s)


def reject_reason(decisions: list[dict]) -> str:
    last = decisions[-1]["reasons"] if decisions else ["no polls"]
    for key in ("undecidable", "soc", "plugged", "tref", "slope"):
        if any(r.startswith(key) for r in last):
            return key
    return "other"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("hal_csv", type=Path)
    ap.add_argument("--tref", type=float)
    ap.add_argument("--soc", type=int, default=50)
    args = ap.parse_args()
    import m7_driver as D
    rows = D.Driver.hal_rows(args.hal_csv)
    ts = [r["host_epoch_s"] for r in rows if r.get("host_epoch_s")]
    if args.tref is None:
        print(json.dumps(tref_candidate(rows, min(ts), max(ts)), ensure_ascii=False, indent=1))
    else:
        print(json.dumps(start_decision(rows, max(ts), args.tref, args.soc, False), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
