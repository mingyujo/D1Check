"""M8 CONFIRM R21 analysis contract (2026-10-16 · 조민규 1016 정정안 SHA 1dc9f5b5… · 동결 R21 2단계 3 ~ 6) — 새 파일 · m8_readout.py 무변경.

  py -3 -X utf8 s26/tools/mixreq/m8_readout_r21.py dev-energy --results results --out <dir>          (DEV 38 → 에너지 적격 규칙 근거 표 · CONFIRM 자료 미열람)
  py -3 -X utf8 s26/tools/mixreq/m8_readout_r21.py confirm --results results --manifest <r21_manifest.json> --dev-energy <energy_eligibility_dev.json> --out <dir> [--blocks 1,2]

주결과 (세션별 → 같은 R블록 기준군 대비 Δ): J0~180 (등록 단위 가설 아래 gauge 추정 J · 에너지 적격일 때만) · AP35~180 시간 평균 · 관측 peak · AP180 · AP180 − AP0 잔열
+ 같은 표: 긴급/일반/전체 완료 · 정시율 · svc70~100 · 응답 P95 · 납기 손해 (late 수 · 비율 · 넘긴 ms 합) · failed · undispatched · unfinished · 미완료 세션.
보조: J0~120 · J35~180 · 실제 병행 dose · WAIT 명목/planned/dose/초과/cut · 입장 · 배정 지연 분포.
규칙: 시간 0 = common_boundary.start_ns (기기 CLOCK_BOOTTIME · progress mono_ns 와 HAL device_boottime_s 는 같은 시계 — 정정 3판) · 경계값 = 양측 실제 표본 선형 (gap 상한 안) · 창 안 gap 초과 = null ·
보간으로 결측 채우기 0 · 이웃 세션 이어붙임 0 · tail 외삽 0 · AP = HAL 온도 센서 (표면온도 아님 · SKIN 과 구분).
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

SCHEMA = "s26-m8-readout-r21-v1"
REVISION_ID = "M8_CONFIRM_R21_v1"
APP_MAX_GAP_S = 2.5          # 동결 v1 settings.coverage.app_max_gap_s
HAL_MAX_GAP_S = 5.0          # 동결 v1 settings.coverage.hal_max_gap_s
J_WINDOWS = {"J0_180": (0.0, 180.0), "J0_120": (0.0, 120.0), "J35_180": (35.0, 180.0)}
AP_MEAN_WINDOW = (35.0, 180.0)
LOAD_WINDOW = (35.0, 120.0)  # 부하 중 = 첫 도착 (offset 35 s) ~ common 끝 (120 s)
# 에너지 적격 (동결 R21 2단계 4 · 단위 · 배율 가설 확인용 · 정밀 교정 아님)
DISCHARGE_NEG_MIN = 0.95
VOLTAGE_RANGE_MV = (3000, 4600)
R_RANGE = (0.8, 1.25)
ENERGY_LABEL = "등록 단위 가설 아래 gauge 추정 J"
ENERGY_NOTE = "두 값이 맞아도 내부 배터리 gauge 끼리의 정합 · 외부 전력계 교정 아님"
UNIT_HYPOTHESIS = "current_raw µA · voltage mV · 방전 음수 · W = −I × V / 10⁹ · Q_int = ∫(−I_µA) dt / 3600 [µAh] vs ΔQ_cc = charge_counter 감소 [µAh] · A24 단위/배율 가져오기 0"
# 비교쌍 (사전 지정 · d = arm − ref · 같은 R블록 1:1)
PAIRS = [
    ("M128_BASE", "M128_ORDER"), ("M128_BASE", "M128_PAIR_G"), ("M128_BASE", "M128_NPU_SERIAL"), ("M128_BASE", "M128_WAIT200x16"),
    ("SMOOTH128_BASE", "SMOOTH128_PAIR_G"),
    ("M128_BASE", "SMOOTH128_BASE"), ("M128_PAIR_G", "SMOOTH128_PAIR_G"),
]
PRIMARY = ["J0_180", "AP35_180_mean", "AP35_180_peak", "AP180", "AP180_minus_AP0"]
SERVICE = ["all_completed_n", "urgent_completed_n", "normal_completed_n", "all_ontime_rate", "urgent_ontime_rate", "normal_ontime_rate",
           "svc70", "svc80", "svc90", "svc95", "svc100", "urgent_p95_ms", "normal_p95_ms", "all_p95_ms",
           "late_n", "late_rate", "late_ms_sum", "failed", "undispatched", "unfinished"]
AUX = ["J0_120", "J35_180", "concurrency_dose_s", "wait_nominal_total_ms", "wait_planned_total_ms", "wait_dose_total_ms", "wait_overrun_total_ms", "wait_cut",
       "admission_delay_med_ms", "admission_delay_p95_ms", "assign_delay_med_ms", "assign_delay_p95_ms"]
T975 = {1: 12.7062047362, 2: 4.30265272975, 3: 3.18244630528, 4: 2.7764451052, 5: 2.57058183564}
HEADER = ("조민규 1016 정정안 (SHA 1dc9f5b5…) — 앞 축소안 '시간 동작만' 철회 · 주목표 = 스케줄링별 에너지 · 열 차이와 납기 · 완료량 교환관계 · "
          "3블록은 통계적 최소나 유의성 보장이 아니다 · 요청 128건을 독립 반복으로 세지 않는다 · t (df = n − 1) 구간 = 기술용")


# ---------------------------------------------------------------- pure functions (단위 시험 대상)
def value_at(samples: list[tuple[float, float]], t: float, max_gap: float) -> float | None:
    """경계값: 정확히 t 인 표본이 있으면 그 값 · 아니면 양측 실제 표본 (t 직전 · 직후) 선형 — 두 표본 간격 ≤ max_gap 일 때만 · 한쪽이 없으면 None (외삽 0)."""
    before = after = None
    for x, v in samples:
        if v is None:
            continue
        if x == t:
            return v
        if x < t:
            before = (x, v)
        elif after is None:
            after = (x, v)
            break
    if before is None or after is None or after[0] - before[0] > max_gap:
        return None
    (x0, v0), (x1, v1) = before, after
    return v0 + (v1 - v0) * (t - x0) / (x1 - x0)


def integrate(samples: list[tuple[float, float]], a: float, b: float, max_gap: float) -> dict:
    """∫_a^b 사다리꼴 · 경계 = value_at (양측 선형) · 구간 안 (경계 포함 이웃) 간격 > max_gap → value None (보간 0)."""
    pts = [(x, v) for x, v in samples if v is not None]
    va, vb = value_at(pts, a, max_gap), value_at(pts, b, max_gap)
    if va is None or vb is None:
        return dict(value=None, reason="boundary_missing_or_gap", n=0, max_gap_s=None)
    inner = [(x, v) for x, v in pts if a < x < b]
    seq = [(a, va)] + inner + [(b, vb)]
    gaps = [seq[i + 1][0] - seq[i][0] for i in range(len(seq) - 1)]
    mg = max(gaps) if gaps else 0.0
    # 경계 이웃: a 직전 실제 표본 ~ 첫 내부 표본, 마지막 내부 표본 ~ b 직후 실제 표본 간격도 gap 규칙
    if mg > max_gap:
        return dict(value=None, reason="gap_in_window", n=len(inner), max_gap_s=round(mg, 3))
    total = sum((seq[i + 1][0] - seq[i][0]) * (seq[i][1] + seq[i + 1][1]) / 2 for i in range(len(seq) - 1))
    return dict(value=total, reason=None, n=len(inner), max_gap_s=round(mg, 3))


def watts(current_raw: float, voltage_mv: float) -> float:
    return -current_raw * voltage_mv / 1e9


def charge_consistency(t: list[float], current: list[float], cc: list[float], max_gap: float = APP_MAX_GAP_S) -> dict:
    """Q_int vs ΔQ_cc: 구간 = 앱 유효 표본 중 charge_counter 가 바뀐 첫 표본 ~ 마지막 바뀐 표본 (계단 경계 사이) · Q_int = ∫(−I) dt / 3600 [µAh] · r = Q_int / ΔQ_cc."""
    ch = [k for k in range(1, len(cc)) if cc[k] != cc[k - 1]]
    steps = [cc[k - 1] - cc[k] for k in ch]
    out = dict(changes=len(ch), step_sizes=sorted(set(steps)), step_min=min(steps) if steps else None, increases=sum(1 for s in steps if s < 0))
    if len(ch) < 2:
        return dict(out, r=None, reason="charge_counter 계단 < 2")
    i1, i2 = ch[0], ch[-1]
    dq = cc[i1] - cc[i2]
    if dq <= 0:
        return dict(out, r=None, reason="ΔQ_cc ≤ 0 (감소 아님)", dq_cc_uah=dq)
    seg = [(t[k], -current[k]) for k in range(i1, i2 + 1)]
    gaps = [seg[k + 1][0] - seg[k][0] for k in range(len(seg) - 1)]
    if gaps and max(gaps) > max_gap:
        return dict(out, r=None, reason="gap_in_interval", dq_cc_uah=dq)
    q = sum((seg[k + 1][0] - seg[k][0]) * (seg[k][1] + seg[k + 1][1]) / 2 for k in range(len(seg) - 1)) / 3600.0
    return dict(out, r=q / dq, q_int_uah=q, dq_cc_uah=dq, interval_s=[t[i1], t[i2]], interval_len_s=t[i2] - t[i1], reason=None,
                boundary_note="계단 시각 = 바뀐 값이 처음 보인 표본 (실제 계단은 직전 표본과 사이 · 양끝 같은 규칙)")


def change_intervals(t: list[float], vals: list) -> dict:
    """값 변화 간격 (읽기 주기와 구분) — 바뀐 표본 시각 사이 간격의 중앙값 · 최대."""
    ts = [t[k] for k in range(1, len(vals)) if vals[k] != vals[k - 1]]
    d = [ts[i + 1] - ts[i] for i in range(len(ts) - 1)]
    return dict(changes=len(ts), median_s=round(statistics.median(d), 3) if d else None, max_s=round(max(d), 3) if d else None)


def percentile(xs: list[float], q: float) -> float | None:
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    k = (len(xs) - 1) * q
    f = math.floor(k)
    c = min(f + 1, len(xs) - 1)
    return xs[f] + (xs[c] - xs[f]) * (k - f)


def overlap_dose(intervals: list[tuple[int, int]]) -> float:
    """≥ 2 건이 동시에 실행 중인 시간 합 (s) — sweep."""
    ev = sorted([(a, 1) for a, b in intervals if a is not None and b is not None and b > a] + [(b, -1) for a, b in intervals if a is not None and b is not None and b > a])
    cur, last, dose = 0, None, 0
    for x, d in ev:
        if cur >= 2 and last is not None:
            dose += x - last
        cur += d
        last = x
    return dose / 1e9


def t_cdf(t: float, df: int) -> float:
    """Student t CDF (정규화 불완전 베타 · 연분수)."""
    x = df / (df + t * t)
    ib = _betainc(df / 2.0, 0.5, x)
    return 1 - 0.5 * ib if t > 0 else 0.5 * ib


def _betainc(a: float, b: float, x: float) -> float:
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    lbeta = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log(1 - x)
    if x < (a + 1) / (a + b + 2):
        return math.exp(lbeta) * _cf(a, b, x) / a
    return 1 - math.exp(lbeta) * _cf(b, a, 1 - x) / b


def _cf(a, b, x, it=300, eps=1e-15):
    qab, qap, qam = a + b, a + 1, a - 1
    c, d = 1.0, 1 - qab * x / qap
    d = 1 / (d if abs(d) > 1e-300 else 1e-300)
    h = d
    for m in range(1, it):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1 + aa * d
        d = 1 / (d if abs(d) > 1e-300 else 1e-300)
        c = 1 + aa / c if abs(1 + aa / c) > 1e-300 else 1e-300
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1 + aa * d
        d = 1 / (d if abs(d) > 1e-300 else 1e-300)
        c = 1 + aa / c if abs(1 + aa / c) > 1e-300 else 1e-300
        de = d * c
        h *= de
        if abs(de - 1) < eps:
            break
    return h


def summarize(d: list[float | None]) -> dict:
    """블록별 d_b 전부 + 평균 · 중앙값 · 최소 · 최대 · 부호 k/n · t (df n−1) 95 % 구간 (기술용) · 양측 p (Holm 전)."""
    x = [v for v in d if v is not None]
    n = len(x)
    out = dict(d_b=d, n=n, mean=None, median=None, min=None, max=None, pos=sum(v > 0 for v in x), neg=sum(v < 0 for v in x), zero=sum(v == 0 for v in x),
               sign=f"+{sum(v > 0 for v in x)}/−{sum(v < 0 for v in x)}/0:{sum(v == 0 for v in x)} (n={n})", ci95=None, p=None)
    if n == 0:
        return out
    out.update(mean=statistics.fmean(x), median=statistics.median(x), min=min(x), max=max(x))
    if n >= 2:
        sd = statistics.stdev(x)
        se = sd / math.sqrt(n)
        tq = T975.get(n - 1)
        if se > 0:
            out["ci95"] = [out["mean"] - tq * se, out["mean"] + tq * se]
            out["p"] = 2 * (1 - t_cdf(abs(out["mean"] / se), n - 1))
        else:
            out["ci95"] = [out["mean"], out["mean"]]
            out["p"] = None if out["mean"] == 0 else 0.0
    return out


def holm(ps: list[float | None]) -> list[float | None]:
    """Holm (FWER) 보정 p — None 은 제외하고 m = 유효 p 수."""
    idx = sorted((i for i, p in enumerate(ps) if p is not None), key=lambda i: ps[i])
    m = len(idx)
    adj = [None] * len(ps)
    run = 0.0
    for r, i in enumerate(idx):
        run = max(run, min(1.0, (m - r) * ps[i]))
        adj[i] = run
    return adj


# ---------------------------------------------------------------- file readers
def sha256(p: Path) -> str | None:
    if not p or not Path(p).is_file():
        return None
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for ch in iter(lambda: f.read(1 << 20), b""):
            h.update(ch)
    return h.hexdigest()


def read_json(p: Path):
    return json.loads(Path(p).read_text(encoding="utf-8")) if Path(p).is_file() else None


def power_samples(folder: Path) -> list[dict]:
    out = []
    with open(folder / "device" / "progress.jsonl", encoding="utf-8") as f:
        for line in f:
            if '"power_sample"' in line:
                try:
                    e = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if e.get("kind") == "power_sample":
                    out.append(e)
    return out


def hal_rows(p: Path) -> list[dict]:
    rows = []
    if not p or not Path(p).is_file():
        return rows
    with open(p, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            def num(k):
                try:
                    return float(r[k]) if r.get(k) not in (None, "") else None
                except ValueError:
                    return None
            # 연속 HAL (m7_hal_cont) = host_ms · device_uptime_s · 세션 hal.csv = pc_ms · device_boottime_s — 둘 다 기기 CLOCK_BOOTTIME (정정 3판: progress mono_ns/1e9 와 같은 시계)
            up = num("device_uptime_s") if "device_uptime_s" in r else num("device_boottime_s")
            rows.append(dict(pc_ms=num("host_ms") if "host_ms" in r else num("pc_ms"), up=up, AP=num("AP"), SKIN=num("SKIN"), BAT=num("BAT"),
                             err=(r.get("err") or None)))
    return rows


def app_energy(folder: Path, t0_ns: int) -> dict:
    ps = power_samples(folder)
    valid = [p for p in ps if p.get("current_valid") and p.get("voltage_mV") is not None and p.get("current_raw") is not None]
    t = [(p["mono_ns"] - t0_ns) / 1e9 for p in valid]
    I = [float(p["current_raw"]) for p in valid]
    V = [float(p["voltage_mV"]) for p in valid]
    ccv = [p for p in valid if p.get("charge_valid") and p.get("charge_counter_raw") is not None]
    tcc = [(p["mono_ns"] - t0_ns) / 1e9 for p in ccv]
    W = [(t[k], watts(I[k], V[k])) for k in range(len(t))]
    load = [I[k] for k in range(len(t)) if LOAD_WINDOW[0] <= t[k] <= LOAD_WINDOW[1]]
    plugged = [p.get("plugged") for p in valid]
    read_d = [t[k + 1] - t[k] for k in range(len(t) - 1)]
    out = dict(
        samples=len(ps), valid=len(valid), first_s=round(t[0], 3) if t else None, last_s=round(t[-1], 3) if t else None,
        read_interval_median_s=round(statistics.median(read_d), 3) if read_d else None, read_interval_max_s=round(max(read_d), 3) if read_d else None,
        current_change=change_intervals(t, I), voltage_change=change_intervals(t, V),
        charge_change=change_intervals(tcc, [p["charge_counter_raw"] for p in ccv]),
        sensor_update_time="미제공 (앱 표본 = 읽기 시각 snapshot_start_ns/sensor_read_end_ns 만 · 센서 갱신 시각 없음)",
        load_samples=len(load), load_neg_fraction=(sum(1 for x in load if x < 0) / len(load)) if load else None,
        voltage_min_mv=min(V) if V else None, voltage_max_mv=max(V) if V else None, plugged_any=any(bool(x) for x in plugged),
        charge=charge_consistency(tcc, [float(p["current_raw"]) for p in ccv], [float(p["charge_counter_raw"]) for p in ccv]),
    )
    for name, (a, b) in J_WINDOWS.items():
        r = integrate(W, a, b, APP_MAX_GAP_S)
        out[name + "_raw"] = r["value"]
        out[name + "_detail"] = r
    return out


def dev_verdict(rows: list[dict]) -> dict:
    loads = [r for r in rows if r.get("load_neg_fraction") is not None]
    neg = sum(r["load_neg_fraction"] * r["load_samples"] for r in loads) / max(1, sum(r["load_samples"] for r in loads))
    vmin = min(r["voltage_min_mv"] for r in rows if r.get("voltage_min_mv") is not None)
    vmax = max(r["voltage_max_mv"] for r in rows if r.get("voltage_max_mv") is not None)
    rs = [r["charge"]["r"] for r in rows if r["charge"].get("r") is not None]
    rmed = statistics.median(rs) if rs else None
    checks = dict(discharge_neg_fraction=dict(value=neg, rule=f"≥ {DISCHARGE_NEG_MIN}", ok=neg >= DISCHARGE_NEG_MIN),
                  voltage_range_mv=dict(value=[vmin, vmax], rule=f"{VOLTAGE_RANGE_MV[0]} ~ {VOLTAGE_RANGE_MV[1]}", ok=VOLTAGE_RANGE_MV[0] <= vmin and vmax <= VOLTAGE_RANGE_MV[1]),
                  r_median=dict(value=rmed, n=len(rs), min=min(rs) if rs else None, max=max(rs) if rs else None, rule=f"{R_RANGE[0]} ~ {R_RANGE[1]}",
                                ok=rmed is not None and R_RANGE[0] <= rmed <= R_RANGE[1],
                                outside_range=sum(1 for x in rs if not (R_RANGE[0] <= x <= R_RANGE[1]))))
    ok = all(c["ok"] for c in checks.values())
    return dict(verdict="단위 가설 적격" if ok else "미확정 — raw 보존 · 에너지 미판정", eligible=ok, checks=checks, hypothesis=UNIT_HYPOTHESIS, note=ENERGY_NOTE)


def session_energy_gate(e: dict, dev_ok: bool) -> tuple[bool, str | None]:
    if not dev_ok:
        return False, "DEV 단위 가설 미확정"
    if e.get("plugged_any"):
        return False, "세션 중 plugged"
    r = (e.get("charge") or {}).get("r")
    if r is None:
        return False, "r 없음 (" + str((e.get("charge") or {}).get("reason")) + ")"
    if not (R_RANGE[0] <= r <= R_RANGE[1]):
        return False, f"r {r:.3f} 범위 밖 ({R_RANGE[0]} ~ {R_RANGE[1]})"
    return True, None


def hal_metrics(hal_csv: Path, t0_ns: int) -> dict:
    rows = hal_rows(hal_csv)
    t0 = t0_ns / 1e9
    ap = [(r["up"] - t0, r["AP"]) for r in rows if r["up"] is not None and r["AP"] is not None]
    out = dict(rows=len(rows), ap_samples=len(ap), first_s=round(ap[0][0], 3) if ap else None, last_s=round(ap[-1][0], 3) if ap else None,
               first_pc_ms=rows[0]["pc_ms"] if rows else None, last_pc_ms=rows[-1]["pc_ms"] if rows else None,
               sensor_update_time="미제공 (HAL 읽기 = host 호출 시각 pc_ms · 기기 boottime 만)")
    m = integrate(ap, AP_MEAN_WINDOW[0], AP_MEAN_WINDOW[1], HAL_MAX_GAP_S)
    out["AP35_180_mean"] = (m["value"] / (AP_MEAN_WINDOW[1] - AP_MEAN_WINDOW[0])) if m["value"] is not None else None
    out["AP35_180_detail"] = m
    inwin = [v for x, v in ap if AP_MEAN_WINDOW[0] <= x <= AP_MEAN_WINDOW[1]]
    out["AP35_180_peak"] = max(inwin) if (inwin and m["value"] is not None) else None
    out["AP35_180_peak_note"] = "관측 peak = [35, 180] 안 실제 HAL 표본 최대 (보간값 아님) · 창 coverage 실패면 null"
    out["AP0"] = value_at(ap, 0.0, HAL_MAX_GAP_S)
    out["AP35"] = value_at(ap, 35.0, HAL_MAX_GAP_S)
    out["AP180"] = value_at(ap, 180.0, HAL_MAX_GAP_S)
    out["AP180_minus_AP0"] = (out["AP180"] - out["AP0"]) if (out["AP180"] is not None and out["AP0"] is not None) else None
    out["AP180_minus_AP35_v1"] = (out["AP180"] - out["AP35"]) if (out["AP180"] is not None and out["AP35"] is not None) else None
    return out


def service(folder: Path, cb: dict, v: dict) -> dict:
    svc = v.get("service") or {}
    counts = v.get("counts") or {}
    rows = cb.get("rows") or []
    late_ms = [(r["response_ns"] - r["deadline_ns"]) / 1e6 for r in rows if r.get("response_ns") and r.get("deadline_ns") and r["response_ns"] > r["deadline_ns"]]
    out = {}
    for pr, key in (("urgent", "urgent"), ("normal", "normal"), ("all", "all")):
        s = svc.get(key) or {}
        planned = s.get("planned")
        rr = [r for r in rows if pr == "all" or r.get("priority") == pr]
        out[f"{pr}_planned"] = planned
        out[f"{pr}_completed_n"] = sum(1 for r in rr if r.get("terminal_status") == "succeeded")
        out[f"{pr}_ontime_n"] = s.get("deadline_met")
        out[f"{pr}_ontime_rate"] = (s.get("deadline_met") / planned) if (planned and s.get("deadline_met") is not None) else None
        out[f"{pr}_late_n"] = s.get("late")
        out[f"{pr}_p95_ms"] = s.get("p95_ms")
    lv = (svc.get("all") or {}).get("levels") or {}
    for L in (70, 80, 90, 95, 100):
        out[f"svc{L}"] = None if lv.get(str(L)) is None else int(bool(lv.get(str(L))))
    planned = (svc.get("all") or {}).get("planned") or counts.get("planned")
    out.update(late_n=len(late_ms), late_rate=(len(late_ms) / planned) if planned else None, late_ms_sum=sum(late_ms),
               late_note="late = 응답 있음 & response_ns > deadline_ns (응답 경계 = priority: 긴급 output_ready · 일반 readback) · 응답 없음 (failed/undispatched) 은 따로",
               failed=counts.get("failed", (svc.get("all") or {}).get("failed")), undispatched=counts.get("undispatched", (svc.get("all") or {}).get("undispatched")),
               unfinished=counts.get("unfinished"), planned=planned, succeeded=counts.get("succeeded"))
    adm = [(r["queue_entry_ns"] - r["actual_arrival_ns"]) / 1e6 for r in rows if r.get("queue_entry_ns") and r.get("actual_arrival_ns")]
    asg = [(r["dispatch_ns"] - r["queue_entry_ns"]) / 1e6 for r in rows if r.get("dispatch_ns") and r.get("queue_entry_ns")]
    out.update(admission_delay_med_ms=percentile(adm, 0.5), admission_delay_p95_ms=percentile(adm, 0.95), admission_delay_max_ms=max(adm) if adm else None,
               assign_delay_med_ms=percentile(asg, 0.5), assign_delay_p95_ms=percentile(asg, 0.95), assign_delay_max_ms=max(asg) if asg else None,
               concurrency_dose_s=overlap_dose([(r.get("execution_start_ns"), r.get("worker_release_ns")) for r in rows]),
               delay_note="입장 = queue_entry − actual_arrival · 배정 = dispatch − queue_entry · 병행 dose = execution_start ~ worker_release 가 ≥ 2 건 겹친 시간 합")
    a7 = ((v.get("rules") or {}).get("A7_wait") or {}).get("detail") or {}
    out.update(wait_count=a7.get("waits"), wait_nominal_total_ms=a7.get("nominal_total_ms"), wait_planned_total_ms=a7.get("planned_total_ms"), wait_dose_total_ms=a7.get("dose_total_ms"),
               wait_overrun_total_ms=a7.get("overrun_total_ms"), wait_cut=(len(a7.get("cut") or []) if a7.get("waits") is not None else None))
    return out


def read_session(folder: Path, hal_csv: str | None, ev: dict | None, dev_ok: bool) -> dict:
    v = read_json(folder / "validated.json") or {}
    cb = read_json(folder / "device" / "common_boundary.json") or {}
    t0 = cb.get("start_ns")
    rec = dict(folder=f"{folder.parent.name}/{folder.name}", eligible=v.get("eligible"), reasons=v.get("reasons"), arm=v.get("arm"), policy=v.get("policy"), attempt=v.get("attempt"),
               session_id=v.get("session_id"), index=v.get("session_index"))
    if t0 is None:
        return dict(rec, error="common_boundary.start_ns 없음")
    sched = [r["scheduled_arrival_ns"] for r in cb.get("rows") or [] if r.get("scheduled_arrival_ns")]
    e = app_energy(folder, t0)
    ok, why = session_energy_gate(e, dev_ok)
    energy = {}
    for name in J_WINDOWS:
        raw = e[name + "_raw"]
        energy[name] = raw if (ok and raw is not None) else None
        energy[name + "_null_reason"] = None if energy[name] is not None else (why or e[name + "_detail"]["reason"])
    h = hal_metrics(Path(hal_csv), t0) if hal_csv else dict(error="HAL csv 없음")
    rec.update(
        common_boundary_start_ns=t0, planned_first_offset_s=((min(sched) - t0) / 1e9) if sched else None, scheduled_binding="scheduled_arrival_ns = start_ns + offset_ns (common_boundary rows)",
        energy_label=ENERGY_LABEL, energy_eligible=ok, energy_null_reason=why, energy=energy, app=e,
        hal=h, service=service(folder, cb, v),
        provenance=dict(app_power=dict(file=f"{folder.name}/device/progress.jsonl", sha256=sha256(folder / "device" / "progress.jsonl"), clock="기기 CLOCK_BOOTTIME (mono_ns) − common_boundary.start_ns",
                                       first_s=e["first_s"], last_s=e["last_s"], sensor_update_time=e["sensor_update_time"]),
                        common_boundary=dict(file=f"{folder.name}/device/common_boundary.json", sha256=sha256(folder / "device" / "common_boundary.json")),
                        hal=dict(file=Path(hal_csv).name if hal_csv else None, sha256=sha256(Path(hal_csv)) if hal_csv else None, clock="device_boottime_s (기기 CLOCK_BOOTTIME · 앱과 같은 시계) · pc_ms = host 호출 시각",
                                 read_first_s=h.get("first_s"), read_last_s=h.get("last_s"), read_first_pc_ms=h.get("first_pc_ms"), read_last_pc_ms=h.get("last_pc_ms"),
                                 sensor_update_time=h.get("sensor_update_time")),
                        validated=dict(file=f"{folder.name}/validated.json", sha256=sha256(folder / "validated.json"))),
        initial_state=(ev or {}).get("initial_state"), gate=(ev or {}).get("gate_summary"),
        rules_note="이웃 세션 이어붙임 0 · 결측 보간 0 · tail 외삽 0 · AP = HAL 온도 센서 (표면온도 아님)")
    return rec


def flat(rec: dict) -> dict:
    s = rec.get("service") or {}
    h = rec.get("hal") or {}
    en = rec.get("energy") or {}
    row = {k: en.get(k) for k in J_WINDOWS}
    row.update({k: h.get(k) for k in ("AP35_180_mean", "AP35_180_peak", "AP0", "AP180", "AP180_minus_AP0", "AP180_minus_AP35_v1")})
    row.update(all_completed_n=s.get("all_completed_n"), urgent_completed_n=s.get("urgent_completed_n"), normal_completed_n=s.get("normal_completed_n"),
               all_ontime_rate=s.get("all_ontime_rate"), urgent_ontime_rate=s.get("urgent_ontime_rate"), normal_ontime_rate=s.get("normal_ontime_rate"),
               urgent_p95_ms=s.get("urgent_p95_ms"), normal_p95_ms=s.get("normal_p95_ms"), all_p95_ms=s.get("all_p95_ms"), **{f"svc{L}": s.get(f"svc{L}") for L in (70, 80, 90, 95, 100)},
               late_n=s.get("late_n"), late_rate=s.get("late_rate"), late_ms_sum=s.get("late_ms_sum"), failed=s.get("failed"), undispatched=s.get("undispatched"), unfinished=s.get("unfinished"),
               concurrency_dose_s=s.get("concurrency_dose_s"), wait_nominal_total_ms=s.get("wait_nominal_total_ms"), wait_planned_total_ms=s.get("wait_planned_total_ms"),
               wait_dose_total_ms=s.get("wait_dose_total_ms"), wait_overrun_total_ms=s.get("wait_overrun_total_ms"), wait_cut=s.get("wait_cut"),
               admission_delay_med_ms=s.get("admission_delay_med_ms"), admission_delay_p95_ms=s.get("admission_delay_p95_ms"),
               assign_delay_med_ms=s.get("assign_delay_med_ms"), assign_delay_p95_ms=s.get("assign_delay_p95_ms"),
               energy_eligible=rec.get("energy_eligible"), energy_null_reason=rec.get("energy_null_reason"), r_charge=((rec.get("app") or {}).get("charge") or {}).get("r"))
    return row


def pair_table(by_block: dict[int, dict[str, dict]], blocks: list[int]) -> dict:
    """by_block[b][arm] = flat row (유효 세션만 · 무효/빈 자리 = 없음) → 쌍 × 지표 요약 + Holm (지표마다 쌍 묶음)."""
    out = {}
    for metric in PRIMARY + SERVICE + AUX:
        per = []
        for ref, arm in PAIRS:
            d = []
            for b in blocks:
                x, y = (by_block.get(b) or {}).get(arm), (by_block.get(b) or {}).get(ref)
                d.append(None if (x is None or y is None or x.get(metric) is None or y.get(metric) is None) else float(x[metric]) - float(y[metric]))
            per.append(dict(pair=f"{arm} − {ref}", ref=ref, arm=arm, **summarize(d)))
        adj = holm([p["p"] for p in per])
        for p, a in zip(per, adj):
            p["p_holm"] = a
            p["holm_lt_0.05"] = (a is not None and a < 0.05)
        out[metric] = per
    return out


# ---------------------------------------------------------------- CLI
def dev_sessions(results: Path, repo: Path) -> list[tuple[str, Path]]:
    blocks = read_json(repo / "s26" / "results" / "m8_prep" / "plan_m8" / "blocks.json")
    out = []
    for blk in blocks["stages"]["dev_blocks"]:
        for s in blk["sessions"]:
            plan = read_json(repo / "s26" / "results" / "m8_prep" / s["plan_dir"] / "plan.json")
            pol = next(e["policy"] for e in plan["sessions"] if e["index"] == s["index"])
            for a in (1, 2):   # 대표 = 첫 유효 시도 (B1-01 a1 · B1-06 a2 · 조민규 확인)
                p = results / "S26_M8_DEV" / s["plan_dir"] / f"S26_MIXREQ_{s['index']:02d}_{pol}_a{a}"
                v = read_json(p / "validated.json")
                if v and v.get("eligible"):
                    out.append((s["label"], p))
                    break
    return out


def write_csv(path: Path, rows: list[dict]):
    keys = []
    for r in rows:
        for k in r:
            if k not in keys:
                keys.append(k)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for r in rows:
            w.writerow({k: ("" if r.get(k) is None else (json.dumps(r[k], ensure_ascii=False) if isinstance(r[k], (list, dict)) else r[k])) for k in keys})


def cmd_dev_energy(args) -> int:
    repo = HERE.parents[2]
    rows = []
    for label, folder in dev_sessions(args.results, repo):
        cb = read_json(folder / "device" / "common_boundary.json")
        e = app_energy(folder, cb["start_ns"])
        rows.append(dict(label=label, folder=f"{folder.parent.name}/{folder.name}", progress_sha256=sha256(folder / "device" / "progress.jsonl"),
                         **{k: e[k] for k in ("samples", "valid", "first_s", "last_s", "read_interval_median_s", "read_interval_max_s", "load_samples", "load_neg_fraction",
                                              "voltage_min_mv", "voltage_max_mv", "plugged_any", "current_change", "voltage_change", "charge_change", "sensor_update_time", "charge")}))
    verdict = dev_verdict(rows)
    args.out.mkdir(parents=True, exist_ok=True)
    doc = dict(schema=SCHEMA + "-dev-energy", revision_id=REVISION_ID, header=HEADER, scope="DEV 블록 1 · 2 38 세션 (대표 = 첫 유효 시도) · DEV 로 규칙 봉인 · CONFIRM 자료 미열람",
               rule=dict(discharge_neg_min=DISCHARGE_NEG_MIN, load_window_s=LOAD_WINDOW, voltage_range_mv=VOLTAGE_RANGE_MV, r_range=R_RANGE, app_max_gap_s=APP_MAX_GAP_S,
                         per_session_confirm="DEV 적격 & 세션 r ∈ r_range & plugged 0 & J 창 coverage 통과일 때만 J 값 · 아니면 null + 사유 · ×1000 등 임의 보정 0"),
               verdict=verdict, sessions=rows, label=ENERGY_LABEL)
    (args.out / "energy_eligibility_dev.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    write_csv(args.out / "energy_eligibility_dev.csv", [dict(label=r["label"], folder=r["folder"], valid=r["valid"], read_med_s=r["read_interval_median_s"], load_neg=r["load_neg_fraction"],
                                                             v_min=r["voltage_min_mv"], v_max=r["voltage_max_mv"], i_change_med_s=r["current_change"]["median_s"],
                                                             v_change_med_s=r["voltage_change"]["median_s"], cc_change_med_s=r["charge_change"]["median_s"], cc_steps=r["charge"]["step_sizes"],
                                                             cc_changes=r["charge"]["changes"], q_int_uah=r["charge"].get("q_int_uah"), dq_cc_uah=r["charge"].get("dq_cc_uah"),
                                                             interval_s=r["charge"].get("interval_len_s"), r=r["charge"].get("r"), r_reason=r["charge"].get("reason")) for r in rows])
    print(json.dumps(dict(sessions=len(rows), verdict=verdict["verdict"], checks={k: (v["value"], v["ok"]) for k, v in verdict["checks"].items()}), ensure_ascii=False, default=str))
    return 0


def confirm_events(results: Path) -> dict:
    out = {}
    p = results / "S26_M8_driver_events.jsonl"
    if p.is_file():
        for l in p.read_text(encoding="utf-8").splitlines():
            if '"run_end"' not in l:
                continue
            e = json.loads(l)
            if e.get("what") == "run_end" and e.get("run_kind") == "confirm" and e.get("rc") is not None:
                out[(e["label"], e["attempt"])] = e
    return out


def cmd_confirm(args) -> int:
    man = read_json(args.manifest)
    dev = read_json(args.dev_energy)
    dev_ok = bool(dev and dev["verdict"]["eligible"])
    evs = confirm_events(args.results)
    want = [int(x) for x in args.blocks.split(",")] if args.blocks else [b["block_no"] for b in man["stages"]["confirm_blocks"]]
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "sessions").mkdir(exist_ok=True)
    by_block, table, slots = {}, [], []
    for blk in man["stages"]["confirm_blocks"]:
        b = blk["block_no"]
        if b not in want:
            continue
        for s in blk["sessions"]:
            plan = read_json(HERE.parents[2] / "s26" / "results" / "m8_prep" / s["plan_dir"] / "plan.json")
            pol = next(e["policy"] for e in plan["sessions"] if e["index"] == s["index"])
            attempts = []
            for a in (1, 2):
                f = args.results / "S26_M8_CONFIRM" / s["plan_dir"] / f"S26_MIXREQ_{s['index']:02d}_{pol}_a{a}"
                if f.is_dir():
                    attempts.append((a, f))
            rep = None
            slot = dict(block=b, label=s["label"], arm=s["arm"], index=s["index"], session_id=s["session_id"], origin=s["origin_slot"]["label"], attempts=[a for a, _ in attempts], status="빈 자리 (START 0)",
                        v1_index=s.get("v1_index"), prior_consumed=s.get("prior_consumed"), revision_id=s.get("revision_id"))
            for a, f in attempts:
                ev = evs.get((s["label"], a))
                rec = read_session(f, (ev or {}).get("hal_csv"), ev, dev_ok)
                rec.update(block=b, label=s["label"], origin_slot=s["origin_slot"], revision_id=s.get("revision_id"), v1_index=s.get("v1_index"))
                (args.out / "sessions" / f"{s['label']}_a{a}.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
                row = dict(block=b, label=s["label"], arm=s["arm"], attempt=a, index=s["index"], origin_slot=s["origin_slot"]["label"], revision_id=s.get("revision_id"),
                           eligible=rec.get("eligible"), reasons=";".join(rec.get("reasons") or []), representative=False, **flat(rec))
                pv = rec.get("provenance") or {}
                row.update({f"init_{k}": v for k, v in (rec.get("initial_state") or {}).items()})
                row.update({f"gate_{k}": v for k, v in (rec.get("gate") or {}).items()})
                row.update(common_boundary_start_ns=rec.get("common_boundary_start_ns"), planned_first_offset_s=rec.get("planned_first_offset_s"),
                           app_power_file=(pv.get("app_power") or {}).get("file"), app_power_sha256=(pv.get("app_power") or {}).get("sha256"),
                           app_first_s=(pv.get("app_power") or {}).get("first_s"), app_last_s=(pv.get("app_power") or {}).get("last_s"),
                           hal_file=(pv.get("hal") or {}).get("file"), hal_sha256=(pv.get("hal") or {}).get("sha256"), hal_read_first_s=(pv.get("hal") or {}).get("read_first_s"),
                           hal_read_last_s=(pv.get("hal") or {}).get("read_last_s"), sensor_update_time="미제공", host_commit=((evs.get((s["label"], a)) or {}).get("host_commit") or {}).get("commit"))
                table.append(row)
                if rec.get("eligible") and rep is None:
                    rep = row
                    row["representative"] = True
            if rep is not None:
                by_block.setdefault(b, {})[s["arm"]] = rep
                slot["status"] = f"유효 (a{rep['attempt']})"
            elif attempts:
                slot["status"] = "무효 (invalid_twice 또는 진행 중)"
            slots.append(slot)
    pairs = pair_table(by_block, want)
    write_csv(args.out / "sessions_r21.csv", table)
    write_csv(args.out / "slots_r21.csv", slots)
    flatp = []
    for metric, per in pairs.items():
        for p in per:
            flatp.append(dict(metric=metric, group=("primary" if metric in PRIMARY else "service" if metric in SERVICE else "aux"), pair=p["pair"],
                              **{f"d_R{b}": p["d_b"][i] for i, b in enumerate(want)}, n=p["n"], mean=p["mean"], median=p["median"], min=p["min"], max=p["max"], sign=p["sign"],
                              ci95_lo=(p["ci95"] or [None, None])[0], ci95_hi=(p["ci95"] or [None, None])[1], p=p["p"], p_holm=p["p_holm"], holm_lt_005=p["holm_lt_0.05"]))
    write_csv(args.out / "pairs_r21.csv", flatp)
    doc = dict(schema=SCHEMA, revision_id=man.get("revision_id"), header=HEADER, blocks=want, v1_consumed=man.get("v1_consumed"), dev_energy_verdict=(dev or {}).get("verdict", {}).get("verdict"), energy_label=ENERGY_LABEL, energy_note=ENERGY_NOTE,
               pairs_rule="d = arm − ref (같은 R블록 1:1 · 한쪽 무효/빈 자리 = 그 블록 쌍 제외 · 대체 0) · Holm = 지표마다 7쌍 묶음 · '유의' 대신 'Holm 보정 p < 0.05 (k/n)'",
               slots=slots, pairs=pairs)
    (args.out / "readout_r21.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(json.dumps(dict(blocks=want, slots=len(slots), valid=sum(1 for s in slots if s["status"].startswith("유효")), dev_energy=doc["dev_energy_verdict"]), ensure_ascii=False))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("dev-energy")
    a.add_argument("--results", type=Path, required=True)
    a.add_argument("--out", type=Path, required=True)
    c = sub.add_parser("confirm")
    c.add_argument("--results", type=Path, required=True)
    c.add_argument("--manifest", type=Path, required=True)
    c.add_argument("--dev-energy", type=Path, required=True)
    c.add_argument("--out", type=Path, required=True)
    c.add_argument("--blocks", default="")
    args = ap.parse_args()
    return cmd_dev_energy(args) if args.cmd == "dev-energy" else cmd_confirm(args)


if __name__ == "__main__":
    sys.exit(main())
