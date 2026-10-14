"""M8 host gate (gate_m8.json · 제안 TREF_DAY_IDLE_MEDIAN_V1 · 영훈 운영 결정 10/14: SOC 시작 하한 20 · 상한 없음) — pure functions over hal_cont rows + a small CLI (phone 0).

  Tref_day: 그 날 첫 블록 전 · 직전 실행 run-log 끝 (또는 충전 분리) 뒤 ≥ 1,200 s 유휴 → 그 뒤 120 s 창 SKIN 중앙값 (|SKIN 기울기| ≤ 0.1 ℃/min 이어야 · 아니면 60 s 마다 재검사 ≤ +1,200 s · 미달 = stable_miss 표시)
  START:    직전 60 s SKIN 중앙값 ∈ Tref_day ± 0.5 ∧ |SKIN|, |AP| 기울기 ≤ 0.1 ℃/min ∧ SOC ≥ 20 ∧ plugged 0 → start · 아니면 30 s 폴 · 최대 600 s → PRESTART_REJECT(reason)
  모든 판정 · 폴링 값 · Tref 는 ledger 행으로 (m8_driver 가 기록). 결과 · 거절 횟수를 보고 Tref 를 옮기지 않는다 (DEV 첫 블록에서 고정 · 확인 전 봉인).
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

ALGORITHM = "TREF_DAY_IDLE_MEDIAN_V1"
STATUS = "제안 (조민규 동의 전 · DEV 첫 블록에서 고정 · 확인 전 봉인 · 질문 #4)"


def window(rows: list[dict], t_end: float, seconds: float) -> list[dict]:
    return [r for r in rows if r.get("host_epoch_s") is not None and t_end - seconds <= r["host_epoch_s"] <= t_end]


def stats(rows: list[dict], t_end: float, seconds: float) -> dict:
    sel = window(rows, t_end, seconds)
    skin = [r["SKIN"] for r in sel if r.get("SKIN") is not None]
    ap = [r["AP"] for r in sel if r.get("AP") is not None]
    return dict(samples=len(sel), skin_median=round(statistics.median(skin), 2) if skin else None, ap_median=round(statistics.median(ap), 2) if ap else None,
                skin_slope_c_per_min=M8.slope_c_per_min([(r["host_epoch_s"], r.get("SKIN")) for r in sel]), ap_slope_c_per_min=M8.slope_c_per_min([(r["host_epoch_s"], r.get("AP")) for r in sel]),
                span_s=(sel[-1]["host_epoch_s"] - sel[0]["host_epoch_s"]) if len(sel) >= 2 else None, window_s=seconds)


def tref_candidate(rows: list[dict], t_end: float) -> dict:
    """120 s 창 (끝 = t_end) 의 SKIN 중앙값 = Tref 후보 · stable = |SKIN 기울기| ≤ 0.1."""
    s = stats(rows, t_end, M8.TREF_WINDOW_S)
    ok = s["skin_median"] is not None and s["skin_slope_c_per_min"] is not None and abs(s["skin_slope_c_per_min"]) <= M8.SLOPE_MAX_C_PER_MIN and s["samples"] >= 20
    return dict(algorithm=ALGORITHM, status=STATUS, tref_c=s["skin_median"], ap_ref_c=s["ap_median"], stable=ok, **s, idle_min_s=M8.TREF_IDLE_S, band_c=M8.TREF_BAND_C, slope_max=M8.SLOPE_MAX_C_PER_MIN)


def start_decision(rows: list[dict], t_now: float, tref_c: float | None, soc: int | None, plugged: bool | None) -> dict:
    """한 번의 START 판정 (60 s 창). reason = None → START."""
    s = stats(rows, t_now, M8.GATE_WINDOW_S)
    reasons = []
    if soc is None or soc < M8.SOC_MIN_START:
        reasons.append(f"soc {soc} < {M8.SOC_MIN_START}")
    if plugged:
        reasons.append("plugged")
    if tref_c is None:
        reasons.append("no Tref_day")
    elif s["skin_median"] is None:
        reasons.append("no SKIN samples in 60 s")
    elif abs(s["skin_median"] - tref_c) > M8.TREF_BAND_C:
        reasons.append(f"tref: SKIN median {s['skin_median']} outside {tref_c} ± {M8.TREF_BAND_C}")
    for name in ("skin_slope_c_per_min", "ap_slope_c_per_min"):
        v = s[name]
        if v is None or abs(v) > M8.SLOPE_MAX_C_PER_MIN:
            reasons.append(f"slope: {name} {None if v is None else round(v, 3)} > {M8.SLOPE_MAX_C_PER_MIN}")
    return dict(start=not reasons, reasons=reasons, tref_c=tref_c, soc=soc, plugged=plugged, soc_min=M8.SOC_MIN_START, soc_new_band_reference=M8.SOC_NEW_BAND,
                soc_in_new_band_reference_only=(soc is not None and M8.SOC_NEW_BAND[0] <= soc <= M8.SOC_NEW_BAND[1]), **s)


def reject_reason(decisions: list[dict]) -> str:
    last = decisions[-1]["reasons"] if decisions else ["no polls"]
    for key in ("soc", "plugged", "tref", "slope"):
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
    t_end = max(r["host_epoch_s"] for r in rows if r.get("host_epoch_s"))
    if args.tref is None:
        print(json.dumps(tref_candidate(rows, t_end), ensure_ascii=False, indent=1))
    else:
        print(json.dumps(start_decision(rows, t_end, args.tref, args.soc, False), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
