# -*- coding: utf-8 -*-
"""night1005_judge.py — 밤 1005 판정기: 같은 일 d100 (A) vs d50 (B) 레버 시험 (NA·NB·GA·GB) + 동결 예측 대조 (cmp).
`밤1005_사전등록_v1.md` (동결 adc17a5, SHA 16af8331…) §1·§3·§4 를 글자 그대로. 구간 추출·10 s 칸·HAL 표본은 `m1m2_judge_1002.py`
(SHA ea282d4a…) 의 함수, 칸 배율·HAL 칸 표본·범위·비교 열은 `night1003_judge.py` (a5ceab41…) 의 함수를 import — 복사·수정 금지
(SHA 를 출력 JSON 의 imports 에 적는다). results\\ 는 읽기만. 같은 입력 두 번 = 같은 바이트. 결과 보기 전 (2026-10-05 오후) 고정.

  py night1005_judge.py selftest
  py night1005_judge.py run <run_dir> --cell NA|NB|GA|GB --block 1|2 [--watch csv] [--gate-log csv] [--gate-label L] [--out f.json]
  py night1005_judge.py pair --a f.json --b f.json [--out f.json]
  py night1005_judge.py resource --pairs f1.json f2.json [--out f.json]
  py night1005_judge.py cmp [--pred-v21 f] [--pred-v2 f] [--pred-v1 f] --runs r1.json … --pairs p1.json … [--out f.json]

규칙 (사전 등록 글자 그대로 — 결과 본 뒤 바꾸지 않는다):
  공통 §1: 구간 창 = segment_start.start_ns ~ segment_end.end_ns · 전환 창 제외 · 지연 = 러너 JSONL latency_ns · 10 s 칸 전수 중앙 ·
       HAL 1 s 표본 · 칸 k 시작에 가장 가까운 HAL
  조임 문턱 §3: NPU ×1.06 · GPU ×1.10 (자원별)
  런 §3 (창 = 체인 전체 900 s):
       work 구간 (구간 0): n · 처리율 = n / 길이 (추론/s) · 10 s 칸 배율 (기준 = 그 구간 처음 30 s 중앙, ref30) ·
       첫 조임 = 칸 k + 뒤 3칸 ≥ 문턱인 첫 칸 (10k s, 없으면 "없음") · 조임 시간 = 칸 1 부터 끝까지 배율 ≥ 문턱인 칸 수 × 10 s ·
       누적 추론 수 (10 s 칸 끝마다)
       온도 (HAL 1 s 표본, 900 s 창 = 구간 0 start_ns ~ 마지막 구간 end_ns): 최고 SKIN·AP·BAT · SKIN ≥ 38.0/40.0/42.0 ℃ 시간 (s = 표본 수) ·
       status ≥ 1 시간 (s = 표본 수) · 899 s SKIN·AP·BAT (구간 0 시작 + 899 s 에 가장 가까운 표본) · work 끝 시점 SKIN·AP
       시작 상태: load_start (구간 0 시작 HAL) SKIN·AP·BAT · 밴드 [29.1, 31.6] 안/밖 · 게이트 값 (--gate-log) · 하한 미달 표시
       (게이트 줄의 lower_pass, 없으면 그 줄 SKIN ≥ 29.1 이고 BAT ≥ 27.5; 게이트 기록 없으면 "미확인")
  쌍 §3 (같은 블록 · 같은 자원, A = d100, B = d50): 일 비 n_B/n_A ≥ 0.95 → "같은 일" · Δ = A − B (양수 = B 가 열 부담 낮음):
       Δ최고 SKIN · Δt38 · Δt40 · Δt42 · Δ조임 시간 · 처리율 비 B/A · 일 비 · B 가 같은 일에 닿은 시각 (B 누적이 n_A 에 닿은 첫 10 s 칸의 끝,
       못 닿으면 "못 닿음") 과 그 시각 − 300 s · 선별 기준 Δ최고 SKIN 1.0 ℃ · Δt38·Δt40·Δ조임 시간 60 s (Δt42 기술만) ·
       부호: Δ ≥ 기준 → + · Δ ≤ −기준 → − · 그 밖 0 (Δ 는 소수 6자리 반올림 뒤 비교)
  자원 §3 (2쌍, 위에서부터 먼저 맞는 것 하나): 1 같은 일 아님 → 2 차이 없음 (2쌍) → 3 B 낮음 (2쌍) → 4 B 높음 (2쌍) → 5 맞바꿈 (2쌍) → 6 엇갈림 ·
       결론 문장 = 사전 등록 §3 문장에 숫자만 (쌍 값은 "블록1 / 블록2") + 조건 괄호.
       쌍이 2개가 아니면 자원 판정을 하지 않는다 ("쌍 부족 — 사전 등록 §3 은 2쌍 규칙" — 6개 판정 밖의 '판정 안 함' 표시)
  cmp §4: 시각 (첫 조임) ±20 s (둘 다 없음 = 맞음 · 한쪽만 = 틀림) · 조임 시간 ±30 s · SKIN (최고·899 s) ±0.5 ℃ · t38/t40 ±30 s ·
       처리율 ±5 % (상대) · n 은 기술 · 쌍 차이: Δ최고 SKIN ±0.5 ℃ · Δt38·Δt40·Δ조임 시간 ±30 s · 일 비는 기술 ·
       자원별 판정 문구가 다르면 틀림 (예측 판정 = 예측 쌍 값을 같은 순서 규칙에 넣은 것 — 각 실측 쌍의 비교 열에서) ·
       비교 열 = 실제 시작 SKIN 에 가까운 쪽 (29.5/30.5, 같으면 29.5, 보간 안 함; 쌍은 A·B 시작 SKIN 평균) ·
       범위 [28.3, 31.6] (night1003_judge.DEV_RANGE) 밖 → unsupported · 변형마다 따로 · 예측 파일 없음 → "예측 없음" ·
       예측 파일 SHA-256 을 출력에 적는다
  예측 JSON 틀 (3단계 predict_night_1005.py 가 이 틀로 쓴다):
       {"model": str, "variants": {name: …} (선택), "cells": {"NA"|"NB"|"GA"|"GB": {"29.5[/변형]": {first_throttle_s, throttle_time_s,
        max_skin, t38_s, t40_s, skin_899, rate_per_s, n, …}}}, "pairs": {"NPU"|"GPU": {"29.5[/변형]": {d_max_skin, d_t38_s, d_t40_s,
        d_throttle_time_s, work_ratio, …}}}, "resources": {"NPU"|"GPU": {"29.5[/변형]": {"verdict": …}}}}
"""
import argparse, csv, hashlib, importlib.util, json, os, shutil, sys, tempfile

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = r"C:\Users\rhoyo\AndroidStudioProjects\D1Check_v4"
OD_SIM = r"C:\Users\rhoyo\OneDrive\문서\Mine\26-2\산공학회\D1_ondevice\sim"
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def _load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _first_existing(*paths):
    for p in paths:
        if os.path.exists(p):
            return p
    raise FileNotFoundError(paths[0])


# --- import (복사·수정 금지) ---------------------------------------------------------------------
_J_PATH = _first_existing(os.path.join(HERE, "m1m2_judge_1002.py"), os.path.join(OD_SIM, "m1m2_judge_1002.py"),
                          os.path.join(REPO, "s26", "tools", "s26_m1m2_judge_1002.py"))
J = _load_module("m1m2_judge_1002", _J_PATH)
_N3_PATH = _first_existing(os.path.join(HERE, "night1003_judge.py"), os.path.join(OD_SIM, "night1003_judge.py"),
                           os.path.join(REPO, "s26", "tools", "night_1003", "night1003_judge.py"))
N3 = _load_module("night1003_judge", _N3_PATH)
load_run, segments_of, bins10, window_median, thermal_at, soc_at, load_watch, dumps, JudgeError, _synth_run = (
    J.load_run, J.segments_of, J.bins10, J.window_median, J.thermal_at, J.soc_at, J.load_watch, J.dumps, J.JudgeError, J._synth_run)
_ratio_bins, _thermal_bin, _pick_col, _supported, _v, _row = N3._ratio_bins, N3._thermal_bin, N3._pick_col, N3._supported, N3._v, N3._row
DEV_RANGE = N3.DEV_RANGE             # (28.3, 31.6)

IMPORTS = {"m1m2_judge_1002": (_J_PATH, "ea282d4a"), "night1003_judge": (_N3_PATH, "a5ceab41")}

BIN_S = 10
HOLD = 3                              # 칸 k + 뒤 3칸
REF_S = 30                            # ref30
EPS = 1e-9                            # 부동소수 비교 여유 (문턱 경계를 문턱 쪽으로)
THR = {"NPU": 1.06, "GPU": 1.10}      # 조임 문턱 (자원별)
BAND = (29.1, 31.6)
LOWER = dict(SKIN=29.1, BAT=27.5)     # 게이트 하한
TEMP_LEVELS = (38.0, 40.0, 42.0)
T_899 = 899
WORK_RATIO_MIN = 0.95
SEL = dict(d_max_skin=1.0, d_t38_s=60.0, d_t40_s=60.0, d_throttle_time_s=60.0)   # 선별 기준 (Δt42 기술만)
SEL_NAMES = dict(d_max_skin="최고 SKIN", d_t38_s="38 ℃ 초과", d_t40_s="40 ℃ 초과", d_throttle_time_s="조임 시간")
A_WORK_S = 300
CELLS = {
    "NA": dict(resource="NPU", side="A", chain="npu_work100_v1", labels=["work_d100", "tail_idle"], duties=[100, 1], durs=[300, 600]),
    "NB": dict(resource="NPU", side="B", chain="npu_work50_v1", labels=["work_d50", "tail_idle"], duties=[50, 1], durs=[660, 240]),
    "GA": dict(resource="GPU", side="A", chain="gpu_work100_v1", labels=["work_d100", "tail_idle"], duties=[100, 1], durs=[300, 600]),
    "GB": dict(resource="GPU", side="B", chain="gpu_work50_v1", labels=["work_d50", "tail_idle"], duties=[50, 1], durs=[480, 420]),
}
VERDICTS = ["같은 일 아님", "차이 없음 (2쌍)", "B 낮음 (2쌍)", "B 높음 (2쌍)", "맞바꿈 (2쌍)", "엇갈림"]
COND = ("— 조건: 이 설치본 · 시작 밴드 · 비행기 모드 켬 · 실내 23 ℃ (진술) · 자원당 2쌍 · "
        "도착·기한·긴급 요청 없는 레버 시험 (정책 시험 아님)")
# ---- cmp §4 ----
TOL = dict(time_s=20.0, throttle_time_s=30.0, skin_abs=0.5, t_level_s=30.0, rate_rel=0.05,
           d_max_skin=0.5, d_t38_s=30.0, d_t40_s=30.0, d_throttle_time_s=30.0)


def _sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        h.update(fh.read())
    return h.hexdigest()


def import_check():
    out = {}
    for k, (p, pre) in IMPORTS.items():
        s = _sha(p)
        out[k] = dict(path=p, sha256=s, expected_prefix=pre, ok=s.startswith(pre))
    return out


def _load_json(p):
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def _r6(x):
    return None if x is None else round(float(x), 6)


# ============================================================ 런
def _expect(S, cell):
    c = CELLS[cell]
    segs = S["segments"]
    got = [s["label"] for s in segs]
    if len(segs) != len(c["labels"]):
        raise JudgeError(f"구간이 {len(segs)}개 — 기대 {len(c['labels'])} ({c['labels']}), 실제 라벨 {got}")
    if got != c["labels"]:
        raise JudgeError(f"구간 라벨 불일치: {got} ≠ {c['labels']}")
    for i, s in enumerate(segs):
        if s["accelerator"] != c["resource"]:
            raise JudgeError(f"구간 {i} 가속기 {s['accelerator']} ≠ {c['resource']}")
        if s["duty"] != c["duties"][i]:
            raise JudgeError(f"구간 {i} duty {s['duty']} ≠ {c['duties'][i]}")
        if s["duration_s"] != c["durs"][i]:
            raise JudgeError(f"구간 {i} duration_s {s['duration_s']} ≠ {c['durs'][i]}")
    if segs[0]["n"] == 0:
        raise JudgeError("work 구간에 추론 없음")
    cid = (S["meta"].get("chain_spec") or {}).get("chain_id")
    if cid != c["chain"]:
        raise JudgeError(f"chain_id {cid} ≠ {c['chain']} (칸 {cell})")
    return segs


def _th_ns(run, ns):
    th = thermal_at(run, ns)
    if th is None:
        return None
    return dict(SKIN=th["SKIN"], AP=th["AP"], BAT=th["BAT"], status=th["thermal_status"], dt_s=th["dt_s"])


def first_throttle(pr, thr):
    """칸 k 와 뒤 3칸이 모두 ≥ 문턱인 첫 k (k = 0 부터). 없으면 None."""
    for k in range(0, len(pr) - HOLD):
        win = pr[k:k + 1 + HOLD]
        if all(r is not None and r >= thr - EPS for r in win):
            return k
    return None


def throttle_time(pr, thr):
    return BIN_S * sum(1 for r in pr[1:] if r is not None and r >= thr - EPS)


def cumulative(seg):
    """10 s 칸 끝마다 누적 추론 수 (추론 시작 시각 < 칸 끝). 마지막 칸이 10 s 보다 짧으면 그 칸 끝 = 10·ceil."""
    t = seg["rel_t"]
    nb = int(np.ceil(seg["length_s"] / BIN_S - 1e-9))
    return [dict(t_end=BIN_S * (k + 1), cum=int(np.searchsorted(t, BIN_S * (k + 1), side="left"))) for k in range(nb)]


def hal_window(run, a_ns, b_ns):
    th = [s for s in run["thermal"] if a_ns <= s["mono_ns"] <= b_ns]

    def col(k):
        return [float(s[k]) for s in th if s.get(k) not in (None, "")]
    sk, ap, bt = col("SKIN"), col("AP"), col("BAT")
    st = [int(s["thermal_status"]) for s in th if s.get("thermal_status") not in (None, "")]
    out = dict(n_samples=len(th), max_SKIN=max(sk) if sk else None, max_AP=max(ap) if ap else None, max_BAT=max(bt) if bt else None,
               status_ge1_s=sum(1 for x in st if x >= 1))
    for lv in TEMP_LEVELS:
        out[f"t{int(lv)}_s"] = sum(1 for x in sk if x >= lv - EPS)
    return out


def _gate_row(path, label, cell, block):
    if not path:
        return None, "게이트 기록 없음"
    if not os.path.exists(path):
        raise JudgeError(f"게이트 CSV 없음: {path}")
    with open(path, encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))
    if label:
        cand = [r for r in rows if r.get("label") == label]
    else:
        key = f"{cell}_b{block}"
        cand = [r for r in rows if key in (r.get("label") or "")]
    if not cand:
        return None, f"게이트 줄 없음 (label {label or cell + '_b' + str(block)})"
    run_rows = [r for r in cand if (r.get("action") or "run") == "run"]
    return (run_rows or cand)[-1], f"게이트 줄 {len(cand)}개 중 마지막 실행 줄"


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _lower_flag(row):
    if row is None:
        return dict(lower_pass=None, label="하한 미확인 (게이트 기록 없음)")
    lp = (row.get("lower_pass") or "").strip()
    if lp in ("True", "False"):
        ok = lp == "True"
        src = "게이트 줄 lower_pass"
    else:
        s, b = _f(row.get("SKIN")), _f(row.get("BAT"))
        ok = None if (s is None or b is None) else (s >= LOWER["SKIN"] - EPS and b >= LOWER["BAT"] - EPS)
        src = "게이트 줄 SKIN·BAT 로 계산"
    lab = "하한 미확인" if ok is None else ("하한 통과" if ok else "하한 미달")
    return dict(lower_pass=ok, label=lab, source=src)


def run_judge(run, cell, block, watch=None, gate_log=None, gate_label=None):
    if cell not in CELLS:
        raise JudgeError(f"칸 {cell} ∉ {list(CELLS)}")
    if block not in (1, 2):
        raise JudgeError(f"블록 {block} ∉ (1, 2)")
    c = CELLS[cell]
    S = segments_of(run)
    work, tail = _expect(S, cell)
    thr = THR[c["resource"]]
    ref30, n_ref = window_median(work, 0, REF_S)
    if ref30 is None:
        raise JudgeError("work 처음 30 s 에 추론 없음 — ref30 없음")
    pr = _ratio_bins(work, ref30)
    k1 = first_throttle(pr, thr)
    a_ns, b_ns = S["segments"][0]["start_ns"], S["segments"][-1]["end_ns"]
    hw = hal_window(run, a_ns, b_ns)
    st = _th_ns(run, a_ns)
    sk = None if st is None else st["SKIN"]
    grow, gnote = _gate_row(gate_log, gate_label, cell, block)
    bins = []
    for k, b in enumerate(bins10(work)):
        th = _thermal_bin(run, work, b["t0"])
        bins.append(dict(k=k, t0=b["t0"], ratio=pr[k], median_ms=b["median_ms"], n=b["n"],
                         SKIN=None if th is None else th["SKIN"], AP=None if th is None else th["AP"]))
    m = S["meta"]
    return dict(
        kind="night1005_run", cell=cell, block=block, resource=c["resource"], side=c["side"],
        run_id=m.get("run_id"), chain_id=(m.get("chain_spec") or {}).get("chain_id"), chain_sha256=m.get("chain_sha256"),
        termination_reason=m.get("termination_reason"), imports=import_check(),
        threshold_ratio=thr,
        work=dict(label=work["label"], duty=work["duty"], duration_s=work["duration_s"], length_s=work["length_s"], n=work["n"],
                  rate_per_s=work["n"] / work["length_s"], achieved_duty=work["achieved_duty"], termination_reason=work["termination_reason"],
                  ref30_ms=ref30, n_ref30=n_ref, first_throttle_s=None if k1 is None else k1 * BIN_S,
                  first_throttle_label="없음" if k1 is None else f"{k1 * BIN_S} s",
                  throttle_time_s=throttle_time(pr, thr), bins=bins, cumulative=cumulative(work),
                  end_thermal=_th_ns(run, work["end_ns"])),
        tail=dict(label=tail["label"], duty=tail["duty"], length_s=tail["length_s"], n=tail["n"]),
        temps=dict(window="구간 0 start_ns ~ 마지막 구간 end_ns", window_s=(b_ns - a_ns) / 1e9, **hw,
                   at_899=_th_ns(run, a_ns + T_899 * 1_000_000_000)),
        start=dict(start_thermal=st, start_skin=sk, load_start_thermal=_th_ns(run, S["load_start_ns"]),
                   band=None if sk is None else ("밴드 안 (29.1~31.6)" if BAND[0] <= sk <= BAND[1] else "밴드 밖 (29.1~31.6)"),
                   gate_row=grow, gate_note=gnote, lower=_lower_flag(grow)),
        start_skin=sk,
        segments=[dict(index=s["index"], label=s["label"], duty=s["duty"], length_s=s["length_s"], n=s["n"],
                       start_soc=soc_at(watch, s["start_wall_ms"])) for s in S["segments"]],
        transitions=S["transitions"])


# ============================================================ 쌍
def _sign(d, thr):
    if d is None:
        return None
    d = round(d, 6)
    if d >= thr:
        return "+"
    if d <= -thr:
        return "-"
    return "0"


def _reach(b, n_a):
    for c in b["work"]["cumulative"]:
        if c["cum"] >= n_a:
            return c["t_end"]
    return None


def pair_judge(a, b):
    for x, side in ((a, "A"), (b, "B")):
        if x.get("kind") != "night1005_run":
            raise JudgeError(f"{side} 가 런 판정 JSON 이 아님")
        if x["side"] != side:
            raise JudgeError(f"{side} 자리에 {x['cell']} ({x['side']})")
    if a["resource"] != b["resource"]:
        raise JudgeError(f"자원 다름: {a['resource']} vs {b['resource']}")
    if a["block"] != b["block"]:
        raise JudgeError(f"블록 다름: {a['block']} vs {b['block']}")
    na, nb = a["work"]["n"], b["work"]["n"]
    wr = nb / na
    same = wr >= WORK_RATIO_MIN - EPS
    ta, tb = a["temps"], b["temps"]

    def dd(x, y):
        return None if (x is None or y is None) else round(x - y, 6)
    d = dict(d_max_skin=dd(ta["max_SKIN"], tb["max_SKIN"]), d_t38_s=dd(ta["t38_s"], tb["t38_s"]), d_t40_s=dd(ta["t40_s"], tb["t40_s"]),
             d_t42_s=dd(ta["t42_s"], tb["t42_s"]), d_throttle_time_s=dd(a["work"]["throttle_time_s"], b["work"]["throttle_time_s"]))
    signs = {k: _sign(d[k], v) for k, v in SEL.items()}
    reach = _reach(b, na)
    return dict(kind="night1005_pair", resource=a["resource"], block=a["block"], a=dict(cell=a["cell"], run_id=a["run_id"], start_skin=a["start_skin"]),
                b=dict(cell=b["cell"], run_id=b["run_id"], start_skin=b["start_skin"]),
                n_a=na, n_b=nb, work_ratio=wr, same_work=same,
                same_work_label="같은 일" if same else "같은 일 아님 — 비교 기술만",
                rate_a=a["work"]["rate_per_s"], rate_b=b["work"]["rate_per_s"], rate_ratio_b_over_a=b["work"]["rate_per_s"] / a["work"]["rate_per_s"],
                b_reach_s=reach, b_reach_label="못 닿음" if reach is None else f"{reach} s",
                b_reach_minus_300_s=None if reach is None else reach - A_WORK_S,
                deltas=d, signs=signs, selection=SEL, imports=import_check(),
                start=dict(a=a["start"], b=b["start"]))


# ============================================================ 자원
def resource_verdict(pairs):
    """사전 등록 §3 순서. pairs = 쌍 판정 dict 2개 (same_work · signs 만 본다)."""
    if len(pairs) != 2:
        return None
    if not all(p["same_work"] for p in pairs):
        return VERDICTS[0]
    keys = list(SEL)
    s1, s2 = pairs[0]["signs"], pairs[1]["signs"]
    if all(s1[k] == "0" and s2[k] == "0" for k in keys):
        return VERDICTS[1]
    both_p = [k for k in keys if s1[k] == "+" and s2[k] == "+"]
    both_m = [k for k in keys if s1[k] == "-" and s2[k] == "-"]
    any_m = any(s1[k] == "-" or s2[k] == "-" for k in keys)
    any_p = any(s1[k] == "+" or s2[k] == "+" for k in keys)
    flip = [k for k in keys if {s1[k], s2[k]} == {"+", "-"}]
    if both_p and not any_m:
        return VERDICTS[2]
    if both_m and not any_p:
        return VERDICTS[3]
    if both_p and both_m and not flip:
        return VERDICTS[4]
    return VERDICTS[5]


def _fmt(x, nd=1):
    if x is None:
        return "?"
    if isinstance(x, int) or (isinstance(x, float) and float(x).is_integer() and nd == 0):
        return f"{int(x):,}"
    return f"{x:.{nd}f}"


def _pp(pairs, key, nd=1, f=lambda p, k: p["deltas"][k]):
    return " / ".join(_fmt(f(p, key), nd) for p in pairs)


def _metric_phrase(pairs, keys, word):
    out = []
    for k in keys:
        if k == "d_max_skin":
            out.append(f"최고 SKIN {_pp(pairs, k, 1, lambda p, kk: abs(p['deltas'][kk]))} ℃ {word[0]}")
        elif k in ("d_t38_s", "d_t40_s"):
            out.append(f"{SEL_NAMES[k]} {_pp(pairs, k, 0, lambda p, kk: abs(p['deltas'][kk]))} s {word[1]}")
        else:
            out.append(f"조임 시간 {_pp(pairs, k, 0, lambda p, kk: abs(p['deltas'][kk]))} s {word[1]}")
    return " · ".join(out)


def sentence(resource, verdict, pairs):
    keys = list(SEL)
    if verdict is None:
        return None
    s1, s2 = pairs[0]["signs"], pairs[1]["signs"]
    both_p = [k for k in keys if s1[k] == "+" and s2[k] == "+"]
    both_m = [k for k in keys if s1[k] == "-" and s2[k] == "-"]
    wr = " / ".join(f"{p['work_ratio']:.3f}" for p in pairs)
    if verdict == VERDICTS[2]:
        reach = " / ".join("못 닿음" if p["b_reach_minus_300_s"] is None else f"{p['b_reach_minus_300_s']}" for p in pairs)
        rates = " / ".join(f"{p['rate_a']:.1f} vs {p['rate_b']:.1f}" for p in pairs)
        s = (f"S26 {resource} 에서 같은 일 (추론 {' / '.join(f'{p['n_a']:,}' for p in pairs)} 건) 을 d50 으로 나눠 하자, d100 으로 몰아서 할 때보다 "
             f"[{_metric_phrase(pairs, both_p, ('낮음', '감소'))}] 였다 (2쌍 같은 방향). 대신 같은 일에 닿는 데 {reach} s 더 걸렸고 "
             f"처리율은 {rates} 추론/s 였다 (B 일 비 {wr}).")
    elif verdict == VERDICTS[3]:
        s = (f"S26 {resource} 에서 같은 일을 d50 으로 나눠 하자 [{_metric_phrase(pairs, both_m, ('높음', '증가'))}] 가 오히려 늘었다 "
             f"(2쌍 같은 방향, B 일 비 {wr}) — 이 조건에서 나눠 하기는 열 부담을 줄이지 않았다.")
    elif verdict == VERDICTS[4]:
        s = (f"S26 {resource} 에서 같은 일을 d50 으로 나누자 [{_metric_phrase(pairs, both_p, ('낮음', '감소'))}] 는 줄고 "
             f"[{_metric_phrase(pairs, both_m, ('높음', '증가'))}] 는 늘었다 (2쌍 같은 방향, B 일 비 {wr}) — 세기는 열 부담의 모양을 바꿨다 (줄였다고 쓰지 않는다).")
    elif verdict == VERDICTS[1]:
        s = "같은 일을 d50 으로 나눠도 열 부담 지표가 선별 기준 안이었다 (2쌍) — 이 조건에서 세기 차이로는 열 부담이 바뀌지 않았다."
    elif verdict == VERDICTS[5]:
        s = "2쌍이 엇갈렸다 — 이 자료로 세기의 효과를 말하지 않는다."
    else:
        s = f"d50 이 정한 시간 안에 같은 일을 못 했다 (일 비 {wr}) — 비교 기술만."
    return s + " " + COND


def resource_judge(pairs):
    for p in pairs:
        if p.get("kind") != "night1005_pair":
            raise JudgeError("쌍 판정 JSON 이 아님")
    res = {p["resource"] for p in pairs}
    if len(res) != 1:
        raise JudgeError(f"자원이 섞임: {sorted(res)}")
    blocks = sorted(p["block"] for p in pairs)
    resource = res.pop()
    pairs = sorted(pairs, key=lambda p: p["block"])
    v = resource_verdict(pairs)
    if v is None:
        return dict(kind="night1005_resource", resource=resource, blocks=blocks, verdict=None,
                    verdict_label=f"쌍 부족 ({len(pairs)}쌍) — 사전 등록 §3 은 2쌍 규칙 · 자원 판정 안 함",
                    sentence=None, pairs=[dict(block=p["block"], signs=p["signs"], same_work=p["same_work"], work_ratio=p["work_ratio"]) for p in pairs])
    if len(set(blocks)) != 2:
        raise JudgeError(f"두 쌍의 블록이 같다: {blocks}")
    return dict(kind="night1005_resource", resource=resource, blocks=blocks, verdict=v, verdict_index=VERDICTS.index(v) + 1,
                sentence=sentence(resource, v, pairs), order=VERDICTS,
                pairs=[dict(block=p["block"], signs=p["signs"], deltas=p["deltas"], same_work=p["same_work"], work_ratio=p["work_ratio"],
                            n_a=p["n_a"], n_b=p["n_b"], b_reach_s=p["b_reach_s"], rate_a=p["rate_a"], rate_b=p["rate_b"],
                            start_a=p["a"]["start_skin"], start_b=p["b"]["start_skin"]) for p in pairs],
                imports=import_check())


# ============================================================ cmp (§4)
def _keys_for(cells_by_col, variant):
    out = []
    for k in cells_by_col:
        parts = k.split("/", 1)
        if (variant is None and len(parts) == 1) or (variant is not None and len(parts) == 2 and parts[1] == variant):
            out.append(k)
    return out


def _variants(pred):
    v = pred.get("variants")
    if isinstance(v, dict) and v:
        return sorted(v)
    return [None]


def _cmp_time(name, p, m, tol):
    if p is None and m is None:
        return _row(name, p, m, f"±{tol} s (둘 다 없음 = 맞음)", "맞음", "")
    if p is None or m is None:
        return _row(name, p, m, f"±{tol} s (한쪽만 없음 = 틀림)", "틀림", "있음/없음 불일치")
    ok = abs(p - m) <= tol + EPS
    return _row(name, p, m, f"±{tol} s", _v(ok), "" if ok else f"차 {m - p:+.1f} s")


def _cmp_abs(name, p, m, tol, unit):
    if p is None or m is None:
        return _row(name, p, m, f"±{tol} {unit}", "미확인", "값 없음")
    ok = abs(p - m) <= tol + EPS
    return _row(name, p, m, f"±{tol} {unit}", _v(ok), "" if ok else f"차 {m - p:+.3f} {unit}")


def _cmp_rel(name, p, m, tol):
    if p is None or m is None or p == 0:
        return _row(name, p, m, f"±{tol * 100:.0f} %", "미확인", "값 없음")
    rel = (m - p) / p
    ok = abs(rel) <= tol + EPS
    return _row(name, p, m, f"±{tol * 100:.0f} %", _v(ok), "" if ok else f"상대 차 {rel * 100:+.1f} %")


def _info(name, p, m):
    return _row(name, p, m, "기술", "기술", "")


def cmp_run(pc, j):
    w, t = j["work"], j["temps"]
    a899 = t.get("at_899") or {}
    return [_cmp_time("첫 조임 (s)", pc.get("first_throttle_s"), w["first_throttle_s"], TOL["time_s"]),
            _cmp_abs("조임 시간 (s)", pc.get("throttle_time_s"), w["throttle_time_s"], TOL["throttle_time_s"], "s"),
            _cmp_abs("최고 SKIN (℃)", pc.get("max_skin"), t["max_SKIN"], TOL["skin_abs"], "℃"),
            _cmp_abs("t38 (s)", pc.get("t38_s"), t["t38_s"], TOL["t_level_s"], "s"),
            _cmp_abs("t40 (s)", pc.get("t40_s"), t["t40_s"], TOL["t_level_s"], "s"),
            _cmp_abs("899 s SKIN (℃)", pc.get("skin_899"), a899.get("SKIN"), TOL["skin_abs"], "℃"),
            _cmp_rel("처리율 (추론/s)", pc.get("rate_per_s"), w["rate_per_s"], TOL["rate_rel"]),
            _info("n (기술)", pc.get("n"), w["n"])]


def cmp_pair(pp, p):
    d = p["deltas"]
    return [_cmp_abs("Δ최고 SKIN (℃)", pp.get("d_max_skin"), d["d_max_skin"], TOL["d_max_skin"], "℃"),
            _cmp_abs("Δt38 (s)", pp.get("d_t38_s"), d["d_t38_s"], TOL["d_t38_s"], "s"),
            _cmp_abs("Δt40 (s)", pp.get("d_t40_s"), d["d_t40_s"], TOL["d_t40_s"], "s"),
            _cmp_abs("Δ조임 시간 (s)", pp.get("d_throttle_time_s"), d["d_throttle_time_s"], TOL["d_throttle_time_s"], "s"),
            _info("일 비 (기술)", pp.get("work_ratio"), p["work_ratio"])]


def _pred_pair_as_judged(pp):
    """예측 쌍 → 순서 규칙 입력 (same_work · signs) — 같은 함수로."""
    wr = pp.get("work_ratio")
    d = {k: pp.get(k) for k in SEL}
    return dict(same_work=(wr is not None and wr >= WORK_RATIO_MIN - EPS), signs={k: _sign(d[k], v) for k, v in SEL.items()},
                deltas=d, work_ratio=wr)


def _counts(rows):
    out = {}
    for r in rows:
        out[r["verdict"]] = out.get(r["verdict"], 0) + 1
    return out


def cmp_one(pred, runs, pairs, tag):
    out = dict(variants={})
    for var in _variants(pred):
        vo = dict(runs=[], pairs=[], resources={})
        for j in runs:
            cells = (pred.get("cells") or {}).get(j["cell"]) or {}
            sk = j.get("start_skin")
            sup, note = _supported(sk)
            keys = _keys_for(cells, var)
            col = _pick_col(keys, sk) if sk is not None else None
            if not sup:
                vo["runs"].append(dict(cell=j["cell"], block=j["block"], start_skin=sk, supported=False, note=note, rows=[]))
                continue
            if col is None:
                vo["runs"].append(dict(cell=j["cell"], block=j["block"], start_skin=sk, supported=True, note="예측 열 없음", rows=[]))
                continue
            rows = cmp_run(cells[col], j)
            vo["runs"].append(dict(cell=j["cell"], block=j["block"], start_skin=sk, supported=True, note=note, column=col, rows=rows, counts=_counts(rows)))
        by_res = {}
        for p in pairs:
            ppred = (pred.get("pairs") or {}).get(p["resource"]) or {}
            sa, sb = p["a"]["start_skin"], p["b"]["start_skin"]
            supa, na_ = _supported(sa)
            supb, nb_ = _supported(sb)
            if not (supa and supb):
                vo["pairs"].append(dict(resource=p["resource"], block=p["block"], supported=False, note=f"A: {na_} · B: {nb_}", rows=[]))
                by_res.setdefault(p["resource"], []).append(None)
                continue
            mean_sk = (sa + sb) / 2.0
            col = _pick_col(_keys_for(ppred, var), mean_sk)
            if col is None:
                vo["pairs"].append(dict(resource=p["resource"], block=p["block"], supported=True, note="예측 열 없음", rows=[]))
                by_res.setdefault(p["resource"], []).append(None)
                continue
            rows = cmp_pair(ppred[col], p)
            vo["pairs"].append(dict(resource=p["resource"], block=p["block"], supported=True, column=col, mean_start_skin=mean_sk,
                                    rows=rows, counts=_counts(rows)))
            by_res.setdefault(p["resource"], []).append((p, _pred_pair_as_judged(ppred[col]), col))
        for res, lst in sorted(by_res.items()):
            if any(x is None for x in lst):
                vo["resources"][res] = dict(verdict="unsupported 또는 예측 열 없음 — 판정 문구 대조 안 함")
                continue
            if len(lst) != 2:
                vo["resources"][res] = dict(verdict=f"쌍 {len(lst)}개 — 판정 문구 대조 안 함 (2쌍 규칙)")
                continue
            lst = sorted(lst, key=lambda x: x[0]["block"])
            mv = resource_verdict([x[0] for x in lst])
            pv = resource_verdict([x[1] for x in lst])
            vo["resources"][res] = dict(predicted=pv, measured=mv, columns=[x[2] for x in lst], verdict=_v(pv == mv),
                                        criterion="자원별 판정 문구가 다르면 틀림")
        out["variants"]["(단일)" if var is None else var] = vo
    return out


def cmp_all(preds, runs, pairs):
    """preds = {"v21": (path, obj|None), "v2": …, "v1": …}"""
    out = dict(rule="밤1005_사전등록_v1 §4 — 시각 ±20 s · 조임 시간 ±30 s · SKIN ±0.5 ℃ · t38/t40 ±30 s · 처리율 ±5 % · 판정 문구 다르면 틀림 · "
                    "비교 열 = 시작 SKIN 에 가까운 쪽 (보간 안 함, 같으면 29.5; 쌍은 A·B 평균) · [28.3, 31.6] 밖 unsupported · 변형마다 따로",
               dev_range=list(DEV_RANGE), tolerances=TOL, imports=import_check(), predictions={}, results={}, notes=[],
               measured=dict(runs=[dict(cell=j["cell"], block=j["block"], run_id=j["run_id"], start_skin=j["start_skin"]) for j in runs],
                             pairs=[dict(resource=p["resource"], block=p["block"]) for p in pairs]))
    for tag in ("v21", "v2", "v1"):
        path, obj = preds.get(tag, (None, None))
        if obj is None:
            out["predictions"][tag] = dict(present=False, path=path, sha256=None)
            out["notes"].append(f"{tag}: 예측 없음" + (f" ({path})" if path else ""))
            continue
        out["predictions"][tag] = dict(present=True, path=path, sha256=_sha(path) if path and os.path.exists(path) else None, model=obj.get("model"))
        out["results"][tag] = cmp_one(obj, runs, pairs, tag)
    return out


# ============================================================ selftest (합성 — 결과 보기 전 양방향)
def _write_hal(rd, load0_ns, end_ns, skin_fn, ap_fn=None, bat_fn=None, status_fn=None):
    """합성 HAL 표본 (1 s). t = load_start 기준 초."""
    with open(os.path.join(rd, "raw", "thermalservice.jsonl"), "w", encoding="utf-8") as fh:
        m = load0_ns - 60_000_000_000
        while m <= end_ns + 5_000_000_000:
            t = (m - load0_ns) / 1e9
            s = skin_fn(t)
            fh.write(json.dumps(dict(source="thermalservice", event="sample", mono_ns=m, parse_status="ok", SKIN=f"{s:.1f}",
                                     AP=f"{(ap_fn or (lambda x: s + 2))(t):.1f}", BAT=f"{(bat_fn or (lambda x: s - 2))(t):.1f}", PA=f"{s:.1f}",
                                     thermal_status=str((status_fn or (lambda x: 0))(t)))) + "\n")
            m += 1_000_000_000


def _mk_run(tmp, tag, cell, work_lat, skin_fn, rate=20.0, tail_lat=None, status_fn=None, drop_seg=False):
    c = CELLS[cell]
    root = os.path.join(tmp, tag)
    base = work_lat(0.0)
    segs = [dict(accelerator=c["resource"], duty=c["duties"][0], duration_s=c["durs"][0], lat_ms=work_lat, label=c["labels"][0]),
            dict(accelerator=c["resource"], duty=c["duties"][1], duration_s=c["durs"][1], lat_ms=tail_lat or (lambda t: base * 1.5), label=c["labels"][1])]
    rd = _synth_run(root, c["chain"], segs, rate=rate, thermal=False)
    if drop_seg:   # 구간 하나 (segment_end 1) 를 뺀 JSONL
        jp = [os.path.join(rd, "gpu", f) for f in os.listdir(os.path.join(rd, "gpu"))][0]
        with open(jp, encoding="utf-8") as fh:
            lines = fh.readlines()
        keep = [ln for ln in lines if not ('"segment_end"' in ln and '\\"index\\": 1' in ln)]
        with open(jp, "w", encoding="utf-8") as fh:
            fh.writelines(keep)
        return rd
    S = segments_of(load_run(rd))
    _write_hal(rd, S["load_start_ns"], S["load_end_ns"], skin_fn, status_fn=status_fn)
    return rd


def _steps(base, pairs_):
    """pairs_ = [(t_from, ratio)] 오름차순 → 계단 함수."""
    def f(t):
        r = 1.0
        for t0, rr in pairs_:
            if t >= t0:
                r = rr
        return base * r
    return f


def _ramp(t0v, peak, t_peak, t_end=None, end=None):
    def f(t):
        if t <= 0:
            return t0v
        if t <= t_peak:
            return t0v + (peak - t0v) * t / t_peak
        if t_end is None:
            return peak
        return peak + (end - peak) * min(1.0, (t - t_peak) / (t_end - t_peak))
    return f


def _fake_run(cell, block, n, max_skin, t38, t40, t42, thr_time, start=30.0, cum=None, rate=None):
    c = CELLS[cell]
    L = c["durs"][0]
    cum = cum or [dict(t_end=BIN_S * (k + 1), cum=int(round(n * (k + 1) / (L / BIN_S)))) for k in range(L // BIN_S)]
    return dict(kind="night1005_run", cell=cell, block=block, resource=c["resource"], side=c["side"], run_id=f"fake-{cell}{block}",
                start_skin=start, start=dict(), work=dict(n=n, rate_per_s=rate or n / L, throttle_time_s=thr_time, cumulative=cum,
                                                          first_throttle_s=None),
                temps=dict(max_SKIN=max_skin, t38_s=t38, t40_s=t40, t42_s=t42, at_899=dict(SKIN=33.0)))


def selftest():
    res = []

    def check(name, cond, got):
        res.append((name, bool(cond), got))
    tmp = tempfile.mkdtemp(prefix="night1005_selftest_")
    try:
        ic = import_check()
        check("import 대상 SHA 접두 일치 (m1m2 ea282d4a · night1003 a5ceab41)", all(v["ok"] for v in ic.values()), {k: v["sha256"][:8] for k, v in ic.items()})
        # ---------------- run: 문턱 경계 (자원별) ----------------
        flat = lambda t: 29.5
        for cell, base, lo, hi in (("NA", 0.75, 1.059, 1.060), ("GA", 2.5, 1.099, 1.100)):
            for r, expect in ((lo, None), (hi, 100)):
                rd = _mk_run(tmp, f"thr_{cell}_{r}", cell, _steps(base, [(100, r)]), flat)
                j = run_judge(load_run(rd), cell, 1)
                check(f"run {cell}: 100 s 부터 ×{r} → 첫 조임 {expect} (문턱 {THR[CELLS[cell]['resource']]})",
                      j["work"]["first_throttle_s"] == expect, (j["work"]["first_throttle_s"], j["work"]["throttle_time_s"]))
        rd = _mk_run(tmp, "thr_time", "NA", _steps(0.75, [(100, 1.06), (200, 1.0)]), flat)
        j = run_judge(load_run(rd), "NA", 1)
        check("run NA: 100~200 s ×1.06 → 첫 조임 100 · 조임 시간 100 s", j["work"]["first_throttle_s"] == 100 and j["work"]["throttle_time_s"] == 100,
              (j["work"]["first_throttle_s"], j["work"]["throttle_time_s"]))
        rd = _mk_run(tmp, "thr_short", "NA", _steps(0.75, [(100, 1.2), (130, 1.0)]), flat)
        j = run_judge(load_run(rd), "NA", 1)
        check("run NA: ×1.2 가 3칸만 → 첫 조임 없음 (칸 + 뒤 3칸) · 조임 시간 30 s", j["work"]["first_throttle_s"] is None and j["work"]["throttle_time_s"] == 30
              and j["work"]["first_throttle_label"] == "없음", (j["work"]["first_throttle_s"], j["work"]["throttle_time_s"]))
        # 처리율 · 누적
        rd = _mk_run(tmp, "rate", "NB", lambda t: 0.75, flat, rate=20.0)
        j = run_judge(load_run(rd), "NB", 2)
        check("run NB: d50 20/s → n ≈ 660·0.5·20 = 6,600 · 처리율 ≈ 10/s · 누적 마지막 = n", abs(j["work"]["n"] - 6600) <= 2 and abs(j["work"]["rate_per_s"] - 10.0) < 0.01
              and j["work"]["cumulative"][-1]["cum"] == j["work"]["n"] and len(j["work"]["cumulative"]) == 66, (j["work"]["n"], j["work"]["rate_per_s"]))
        # 온도 지표
        skin = _ramp(29.5, 41.0, 300.0, 900.0, 33.0)
        rd = _mk_run(tmp, "temps", "GA", lambda t: 2.5, skin, status_fn=lambda t: 1 if 200 <= t < 260 else 0)
        j = run_judge(load_run(rd), "GA", 1)
        T = j["temps"]
        check("run GA: 최고 SKIN 41.0 · t38/t40/t42 > 0 순서 · t42 = 0 · status≥1 ≈ 60 s", T["max_SKIN"] == 41.0 and T["t38_s"] > T["t40_s"] > 0 and T["t42_s"] == 0
              and 58 <= T["status_ge1_s"] <= 61, (T["max_SKIN"], T["t38_s"], T["t40_s"], T["t42_s"], T["status_ge1_s"]))
        check("run GA: 899 s SKIN ≈ 33.0 (끝) · work 끝 SKIN ≈ 41", abs(T["at_899"]["SKIN"] - 33.0) <= 0.3 and abs(j["work"]["end_thermal"]["SKIN"] - 41.0) <= 0.2,
              (T["at_899"]["SKIN"], j["work"]["end_thermal"]["SKIN"]))
        # 하한 · 게이트
        gl = os.path.join(tmp, "gate.csv")
        with open(gl, "w", encoding="utf-8") as fh:
            fh.write("label,local_time,waited_s,SKIN,AP,BAT,thermal_status,soc,plugged,upper_pass,lower_skin_ge_29.1,lower_bat_ge_27.5,lower_pass,lower_policy,action\n")
            fh.write("01_NA_b1,2026-10-05T23:00:00,0,28.9,28.0,27.9,0,90,False,True,False,True,False,mark,run\n")
            fh.write("02_GB_b1,2026-10-05T23:30:00,0,29.5,28.0,27.9,0,85,False,True,True,True,True,mark,run\n")
        rd = _mk_run(tmp, "gate", "NA", lambda t: 0.75, lambda t: 28.9)
        j = run_judge(load_run(rd), "NA", 1, gate_log=gl)
        check("run: 게이트 줄 lower_pass False → '하한 미달' · 밴드 밖", j["start"]["lower"]["label"] == "하한 미달" and j["start"]["band"].startswith("밴드 밖"),
              (j["start"]["lower"], j["start"]["band"]))
        rd = _mk_run(tmp, "gate2", "GB", lambda t: 2.5, lambda t: 29.5)
        j = run_judge(load_run(rd), "GB", 1, gate_log=gl)
        check("run: 게이트 줄 lower_pass True → '하한 통과' · 밴드 안", j["start"]["lower"]["label"] == "하한 통과" and j["start"]["band"].startswith("밴드 안"),
              j["start"]["lower"])
        j = run_judge(load_run(rd), "GB", 2)
        check("run: 게이트 기록 없음 → '하한 미확인'", j["start"]["lower"]["lower_pass"] is None, j["start"]["lower"])
        # 구조 오류
        rd = _mk_run(tmp, "drop", "NA", lambda t: 0.75, flat, drop_seg=True)
        try:
            run_judge(load_run(rd), "NA", 1)
            check("구간 하나 뺀 JSONL → 오류로 멈춤", False, "판정이 나왔다")
        except JudgeError as err:
            check("구간 하나 뺀 JSONL → 오류로 멈춤", True, str(err))
        rd = _mk_run(tmp, "wrongcell", "NA", lambda t: 0.75, flat)
        try:
            run_judge(load_run(rd), "NB", 1)
            check("NA 체인을 NB 로 → 오류로 멈춤", False, "판정이 나왔다")
        except JudgeError as err:
            check("NA 체인을 NB 로 → 오류로 멈춤", True, str(err))
        # ---------------- pair ----------------
        A = _fake_run("NA", 1, 10000, 40.0, 200, 100, 0, 200)
        for nb, exp in ((9499, False), (9500, True)):
            p = pair_judge(A, _fake_run("NB", 1, nb, 40.0, 200, 100, 0, 200))
            check(f"pair: 일 비 {nb / 10000:.4f} → 같은 일 {exp}", p["same_work"] is exp, (p["work_ratio"], p["same_work_label"]))
        for dsk, exp in ((1.0, "+"), (0.9, "0"), (-1.0, "-"), (-0.9, "0")):
            p = pair_judge(A, _fake_run("NB", 1, 10000, round(40.0 - dsk, 1), 200, 100, 0, 200))
            check(f"pair: Δ최고 SKIN {dsk:+.1f} → {exp}", p["signs"]["d_max_skin"] == exp, p["deltas"]["d_max_skin"])
        for dt, exp in ((60, "+"), (59, "0"), (-60, "-"), (-59, "0")):
            p = pair_judge(A, _fake_run("NB", 1, 10000, 40.0, 200 - dt, 100 - dt, 0, 200 - dt))
            check(f"pair: Δt38·Δt40·Δ조임 {dt:+d} s → {exp}", p["signs"]["d_t38_s"] == exp and p["signs"]["d_t40_s"] == exp and p["signs"]["d_throttle_time_s"] == exp,
                  p["signs"])
        cum = [dict(t_end=10 * (k + 1), cum=200 * (k + 1)) for k in range(66)]
        p = pair_judge(A, _fake_run("NB", 1, 13200, 40.0, 200, 100, 0, 200, cum=cum))
        check("pair: B 누적 200/칸 → n_A 10,000 에 500 s 끝에 닿음 · −300 = 200 s", p["b_reach_s"] == 500 and p["b_reach_minus_300_s"] == 200, p["b_reach_label"])
        cum = [dict(t_end=10 * (k + 1), cum=140 * (k + 1)) for k in range(66)]
        p = pair_judge(A, _fake_run("NB", 1, 9240, 40.0, 200, 100, 0, 200, cum=cum))
        check("pair: B 가 n_A 에 못 닿음 → '못 닿음'", p["b_reach_s"] is None and p["b_reach_label"] == "못 닿음", p["b_reach_label"])
        try:
            pair_judge(A, _fake_run("GB", 1, 10000, 40.0, 200, 100, 0, 200))
            check("pair: 자원 다름 → 오류", False, "판정이 나왔다")
        except JudgeError as err:
            check("pair: 자원 다름 → 오류", True, str(err))
        try:
            pair_judge(A, _fake_run("NB", 2, 10000, 40.0, 200, 100, 0, 200))
            check("pair: 블록 다름 → 오류", False, "판정이 나왔다")
        except JudgeError as err:
            check("pair: 블록 다름 → 오류", True, str(err))
        # ---------------- resource (6개 + 경계) ----------------
        def P(block, signs, same=True, n_b=10000):
            d = {k: (1.0 if s == "+" else (-1.0 if s == "-" else 0.0)) * (1.0 if k == "d_max_skin" else 60.0) for k, s in signs.items()}
            return dict(kind="night1005_pair", resource="NPU", block=block, same_work=same, signs=signs, deltas=dict(d, d_t42_s=0.0),
                        work_ratio=n_b / 10000, n_a=10000, n_b=n_b, b_reach_s=500, b_reach_minus_300_s=200, rate_a=1200.0, rate_b=600.0,
                        a=dict(start_skin=30.0), b=dict(start_skin=30.0))

        def S4(sk, t38, t40, thr):
            return dict(d_max_skin=sk, d_t38_s=t38, d_t40_s=t40, d_throttle_time_s=thr)
        z = S4("0", "0", "0", "0")
        cases = [
            ("같은 일 아님 (한 쌍 실패)", [P(1, S4("+", "+", "0", "0")), P(2, S4("+", "+", "0", "0"), same=False, n_b=9000)], VERDICTS[0]),
            ("차이 없음", [P(1, z), P(2, z)], VERDICTS[1]),
            ("B 낮음 (두 쌍 SKIN +)", [P(1, S4("+", "0", "0", "0")), P(2, S4("+", "+", "0", "0"))], VERDICTS[2]),
            ("B 높음 (두 쌍 − 만)", [P(1, S4("-", "0", "0", "0")), P(2, S4("-", "-", "0", "0"))], VERDICTS[3]),
            ("맞바꿈 (두 쌍 모두 + 와 −)", [P(1, S4("+", "0", "0", "-")), P(2, S4("+", "0", "0", "-"))], VERDICTS[4]),
            ("엇갈림 (한 쌍만 기준 넘음)", [P(1, S4("+", "0", "0", "0")), P(2, z)], VERDICTS[5]),
            ("B 낮음 아님 (한 쌍에서 한 지표 −)", [P(1, S4("+", "-", "0", "0")), P(2, S4("+", "0", "0", "0"))], VERDICTS[5]),
            ("엇갈림 (두 쌍 사이 + / − 뒤집힘)", [P(1, S4("+", "-", "+", "0")), P(2, S4("+", "-", "-", "0"))], VERDICTS[5]),
            ("엇갈림 (쌍끼리 방향 반대)", [P(1, S4("+", "0", "0", "0")), P(2, S4("-", "0", "0", "0"))], VERDICTS[5]),
        ]
        for name, prs, exp in cases:
            r = resource_judge(prs)
            check(f"resource: {name} → {exp}", r["verdict"] == exp, (r["verdict"], (r["sentence"] or "")[:60]))
        r = resource_judge([P(1, S4("+", "+", "0", "0")), P(2, S4("+", "0", "0", "0"))])
        check("resource: B 낮음 문장 = 사전 등록 틀 + 숫자 + 조건 괄호", r["sentence"].startswith("S26 NPU 에서 같은 일 (추론 10,000 / 10,000 건)") and "최고 SKIN 1.0 / 1.0 ℃ 낮음" in r["sentence"]
              and "38 ℃ 초과" not in r["sentence"] and r["sentence"].endswith(COND), r["sentence"][:150])
        r = resource_judge([P(1, S4("+", "0", "0", "0"))])
        check("resource: 쌍 1개 → 판정 안 함 (2쌍 규칙)", r["verdict"] is None and "쌍 부족" in r["verdict_label"], r["verdict_label"])
        # ---------------- cmp ----------------
        rd = _mk_run(tmp, "cmpA", "NA", _steps(0.75, [(100, 1.1)]), _ramp(29.5, 41.0, 300.0, 900.0, 33.0))
        ja = run_judge(load_run(rd), "NA", 1)
        rd = _mk_run(tmp, "cmpB", "NB", lambda t: 0.75, _ramp(29.5, 39.0, 660.0, 900.0, 33.0), rate=40.0)
        jb = run_judge(load_run(rd), "NB", 1)
        pj = pair_judge(ja, jb)
        pred = dict(model="synthetic", cells=dict(
            NA={"29.5": dict(first_throttle_s=100, throttle_time_s=ja["work"]["throttle_time_s"], max_skin=41.0, t38_s=ja["temps"]["t38_s"], t40_s=ja["temps"]["t40_s"],
                             skin_899=33.0, rate_per_s=ja["work"]["rate_per_s"] * 1.04, n=ja["work"]["n"]),
                "30.5": dict(first_throttle_s=50, throttle_time_s=0, max_skin=45.0, t38_s=0, t40_s=0, skin_899=40.0, rate_per_s=1.0, n=1)},
            NB={"29.5": dict(first_throttle_s=None, throttle_time_s=0, max_skin=39.6, t38_s=jb["temps"]["t38_s"] + 31, t40_s=0, skin_899=33.0,
                             rate_per_s=jb["work"]["rate_per_s"] * 0.94, n=jb["work"]["n"])}),
            pairs=dict(NPU={"29.5": dict(d_max_skin=pj["deltas"]["d_max_skin"], d_t38_s=pj["deltas"]["d_t38_s"], d_t40_s=pj["deltas"]["d_t40_s"],
                                         d_throttle_time_s=pj["deltas"]["d_throttle_time_s"], work_ratio=pj["work_ratio"])}))
        pp = os.path.join(tmp, "pred.json")
        with open(pp, "w", encoding="utf-8") as fh:
            json.dump(pred, fh)
        c = cmp_all({"v21": (pp, pred), "v2": (os.path.join(tmp, "missing.json"), None)}, [ja, jb], [pj])
        rows_a = {r["cell"]: r for r in c["results"]["v21"]["variants"]["(단일)"]["runs"][0]["rows"]}
        rows_b = {r["cell"]: r for r in c["results"]["v21"]["variants"]["(단일)"]["runs"][1]["rows"]}
        check("cmp: NA 29.5 열 · 첫 조임 맞음 · 처리율 +4 % 맞음", c["results"]["v21"]["variants"]["(단일)"]["runs"][0]["column"] == "29.5"
              and rows_a["첫 조임 (s)"]["verdict"] == "맞음" and rows_a["처리율 (추론/s)"]["verdict"] == "맞음", (rows_a["첫 조임 (s)"], rows_a["처리율 (추론/s)"]["verdict"]))
        check("cmp: NB 최고 SKIN 0.6 ℃ 차 → 틀림 · t38 31 s 차 → 틀림 · 처리율 −6 % → 틀림 · 첫 조임 둘 다 없음 → 맞음",
              rows_b["최고 SKIN (℃)"]["verdict"] == "틀림" and rows_b["t38 (s)"]["verdict"] == "틀림" and rows_b["처리율 (추론/s)"]["verdict"] == "틀림"
              and rows_b["첫 조임 (s)"]["verdict"] == "맞음", {k: v["verdict"] for k, v in rows_b.items()})
        check("cmp: 예측 파일 SHA 기록 · 없는 예측 → '예측 없음'", c["predictions"]["v21"]["sha256"] == _sha(pp) and c["predictions"]["v2"]["present"] is False
              and any("v2: 예측 없음" in n for n in c["notes"]), c["notes"])
        pr0 = c["results"]["v21"]["variants"]["(단일)"]["pairs"][0]
        check("cmp: 쌍 차이 예측 = 실측 → 맞음 4", pr0["counts"].get("맞음") == 4, pr0["counts"])
        rd = _mk_run(tmp, "cold", "NA", lambda t: 0.75, lambda t: 27.9)
        jc = run_judge(load_run(rd), "NA", 2)
        c2 = cmp_all({"v21": (pp, pred)}, [jc], [])
        r0 = c2["results"]["v21"]["variants"]["(단일)"]["runs"][0]
        check("cmp: 시작 SKIN 27.9 → unsupported (범위를 넓히지 않는다)", r0["supported"] is False and "unsupported" in r0["note"], r0["note"])
        jd = dict(ja, start_skin=30.0)
        c3 = cmp_all({"v21": (pp, pred)}, [jd], [])
        check("cmp: 시작 SKIN 30.0 (가운데) → 29.5 열", c3["results"]["v21"]["variants"]["(단일)"]["runs"][0]["column"] == "29.5",
              c3["results"]["v21"]["variants"]["(단일)"]["runs"][0]["column"])
        je = dict(ja, start_skin=30.4)
        c4 = cmp_all({"v21": (pp, pred)}, [je], [])
        check("cmp: 시작 SKIN 30.4 → 30.5 열 (틀림 나옴)", c4["results"]["v21"]["variants"]["(단일)"]["runs"][0]["column"] == "30.5"
              and c4["results"]["v21"]["variants"]["(단일)"]["runs"][0]["counts"].get("틀림", 0) >= 3, c4["results"]["v21"]["variants"]["(단일)"]["runs"][0]["counts"])
        # 변형 · 자원 판정 문구 대조
        predv = dict(model="synthetic-var", variants={"a": 1, "b": 2}, cells={}, pairs=dict(NPU={
            "29.5/a": dict(d_max_skin=1.5, d_t38_s=0, d_t40_s=0, d_throttle_time_s=0, work_ratio=1.1),
            "29.5/b": dict(d_max_skin=0.0, d_t38_s=0, d_t40_s=0, d_throttle_time_s=0, work_ratio=1.1)}))
        p1 = dict(P(1, S4("+", "0", "0", "0")), a=dict(start_skin=29.6), b=dict(start_skin=29.4))
        p2 = dict(P(2, S4("+", "0", "0", "0")), a=dict(start_skin=29.6), b=dict(start_skin=29.4))
        c5 = cmp_all({"v2": (None, predv)}, [], [p1, p2])
        ra, rb = c5["results"]["v2"]["variants"]["a"]["resources"]["NPU"], c5["results"]["v2"]["variants"]["b"]["resources"]["NPU"]
        check("cmp: 변형마다 따로 — a 'B 낮음' = 실측 → 맞음 · b '차이 없음' ≠ → 틀림", ra["verdict"] == "맞음" and rb["verdict"] == "틀림",
              (ra["predicted"], rb["predicted"], ra["measured"]))
        # 결정성
        rd1 = _mk_run(tmp, "detA", "GB", _steps(2.5, [(200, 1.2)]), _ramp(29.5, 39.0, 480.0, 900.0, 33.0))
        rd2 = _mk_run(tmp, "detB", "GB", _steps(2.5, [(200, 1.2)]), _ramp(29.5, 39.0, 480.0, 900.0, 33.0))
        a1 = dumps(run_judge(load_run(rd1), "GB", 1)).replace(rd1, "X").replace(rd1.replace("\\", "\\\\"), "X")
        a2 = dumps(run_judge(load_run(rd2), "GB", 1)).replace(rd2, "X").replace(rd2.replace("\\", "\\\\"), "X")
        check("결정성: run 같은 입력 두 번 = 같은 바이트 (경로 제외)", a1 == a2, f"{len(a1)} B")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    ok = all(c for _, c, _ in res)
    print("| 시험 | 결과 | 값 |\n|---|---|---|")
    for name, c, got in res:
        print(f"| {name} | {'PASS' if c else 'FAIL'} | {str(got)[:170]} |")
    print(f"\nselftest 전체: {'PASS' if ok else 'FAIL'} ({sum(1 for _, c, _ in res if c)}/{len(res)})")
    return 0 if ok else 1


# ============================================================ CLI
def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("selftest")
    a = sub.add_parser("run")
    a.add_argument("run_dir")
    a.add_argument("--cell", required=True, choices=sorted(CELLS))
    a.add_argument("--block", required=True, type=int, choices=(1, 2))
    a.add_argument("--watch")
    a.add_argument("--gate-log")
    a.add_argument("--gate-label")
    a.add_argument("--out")
    a = sub.add_parser("pair")
    a.add_argument("--a", required=True)
    a.add_argument("--b", required=True)
    a.add_argument("--out")
    a = sub.add_parser("resource")
    a.add_argument("--pairs", nargs="+", required=True)
    a.add_argument("--out")
    a = sub.add_parser("cmp")
    a.add_argument("--pred-v21")
    a.add_argument("--pred-v2")
    a.add_argument("--pred-v1")
    a.add_argument("--runs", nargs="*", default=[])
    a.add_argument("--pairs", nargs="*", default=[])
    a.add_argument("--out")
    args = p.parse_args(argv)
    if args.cmd == "selftest":
        return selftest()
    try:
        if args.cmd == "run":
            res = run_judge(load_run(args.run_dir), args.cell, args.block, load_watch(args.watch), args.gate_log, args.gate_label)
        elif args.cmd == "pair":
            res = pair_judge(_load_json(args.a), _load_json(args.b))
        elif args.cmd == "resource":
            res = resource_judge([_load_json(f) for f in args.pairs])
        else:
            preds = {}
            for tag in ("v21", "v2", "v1"):
                v = getattr(args, f"pred_{tag}")
                if v and not os.path.exists(v):
                    print(f"NOTE: pred-{tag} 파일 없음 → '예측 없음' ({v})", file=sys.stderr)
                preds[tag] = (v, _load_json(v) if (v and os.path.exists(v)) else None)
            res = cmp_all(preds, [_load_json(f) for f in args.runs], [_load_json(f) for f in args.pairs])
    except JudgeError as err:
        print(f"JUDGE_ERROR: {err}", file=sys.stderr)
        return 2
    text = dumps(res)
    if getattr(args, "out", None):
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
