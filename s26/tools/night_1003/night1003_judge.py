# -*- coding: utf-8 -*-
"""night1003_judge.py — 밤 1003 판정기: M1-NPU (a)(b) · M1-GPU 2런째 · 모형(v1 [+v2]) 예측 대조 (cmp).
`M1_NPU_사전등록_v1.md` §2·§3·§5 와 `M1M2_사전등록_v1.md` §2 를 글자 그대로. 구간 추출은 `m1m2_judge_1002.py`
(SHA ea282d4a…) 의 segments 정의를 import 해서 쓴다 (복사·수정 금지). 1계단 시각은 `d1sim\\tools\\fit_throttle_v1.py`
의 `step1_time` 을 import (+4.5 % 유지 첫 칸 — P1b 와 같은 정의). results\\ 는 읽기만. 같은 입력 두 번 = 같은 바이트.

  py night1003_judge.py selftest
  py night1003_judge.py m1npu <run_dir> [--second <run_dir>] [--watch csv] [--out f.json]
  py night1003_judge.py m1gpu <run_dir> [--first-run-recovery-s 20] [--watch csv] [--out f.json]
  py night1003_judge.py cmp --pred <night_1003_prediction.json> [--pred-v2 f] [--pred-pacing f]
                            [--m1gpu <m1gpu.json>] [--m1npu-a <m1npu.json>] [--m1npu-b <m1npu.json>] [--out f.json]

규칙 (사전 등록 글자 그대로 — 결과 본 뒤 바꾸지 않는다):
  M1-NPU §2: ref_d10 = 구간 0 전수 중앙 · A3 = 구간 0 10 s 칸 ±5 % · 완전 회복 = 탐침 칸 k 와 뒤 3칸 ≤ ref_d10 × 1.03 → 10k s,
             마지막 검정 k = 56, 없으면 "570 s 안 미회복 (오른쪽 중도절단)" · 모양 = 한 칸 감소 ≥ 50 % → 계단형 · "≤ 1.06 첫 칸" 기술만
  M1-NPU §3: H-skin: SKIN_k ≥ 38.8 기각 · H-ap: AP_k ≥ 43.0 기각 · H-timer: 해제 > 60 s 기각 · 해제 ≤ 40 s → H-ap/H-timer 못 가름 선언
             · 40~100 s → 미분류 · 100~200 s 이고 SKIN_k 37~38.8 → H-skin 유지 · 두 런 해제 차 ≤ 20 s → 재현
  M1-GPU   : M1M2 v1 §2 (m1m2_judge_1002.m1_judge) + M1_NPU v1 §5: 회복 20~40 s 이고 계단형 → "v1 ⑥ 유지(2런)", 아니면 ⑥ 기각 · 1런째와 차 ≤ 10 s → 재현
  cmp      : v1_예측_밤1003.md 의 "이 차이면 틀린 것" 열 그대로 (GPU 진입 ±10 s · 배율 ±10 % · SKIN ±0.5 · NPU 계단 시각 ±20 s · 끝 배율 ±0.03
             · 탐침 SKIN MAE ≤ 0.5). 비교 열 = 실제 시작 SKIN 에 가까운 쪽 (29.5 / 30.5). 시작 SKIN 이 [28.3, 31.6] 밖 → unsupported.
"""
import argparse, importlib.util, json, os, shutil, sys, tempfile

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = r"C:\Users\rhoyo\AndroidStudioProjects\D1Check_v4"
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def _load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# --- import (복사·수정 금지) ---------------------------------------------------------------------
_J_PATH = os.path.join(HERE, "m1m2_judge_1002.py")
if not os.path.exists(_J_PATH):
    _J_PATH = os.path.join(REPO, "s26", "tools", "s26_m1m2_judge_1002.py")
J = _load_module("m1m2_judge_1002", _J_PATH)
load_run, segments_of, bins10, window_median, thermal_at, soc_at, load_watch, onset_1_1, dumps, JudgeError, _synth_run = (
    J.load_run, J.segments_of, J.bins10, J.window_median, J.thermal_at, J.soc_at, J.load_watch, J.onset_1_1, J.dumps, J.JudgeError, J._synth_run)
sys.path.insert(0, REPO)
F = _load_module("fit_throttle_v1", os.path.join(REPO, "d1sim", "tools", "fit_throttle_v1.py"))
step1_time = F.step1_time          # (bins=[(t, ratio)], level=1.045) → +4.5 % 를 그 칸 + 뒤 3칸 유지하는 첫 칸 (t ≥ 30)

BIN_S = 10
# ---- M1-NPU §2·§3 상수 ----
NPU_DELTA = 0.03                   # 완전 회복 δ
NPU_HOLD_BINS = 3                  # 칸 k + 뒤 3칸
NPU_LAST_K = 56                    # 탐침 600 s → 마지막 검정 가능 k
NPU_A3_TOL = 0.05
NPU_STEP_FRACTION = 0.50
NPU_LEVEL1_DESC = 1.06             # "≤ 1.06 첫 칸" (기술만)
NPU_STEP1_LEVEL = 1.045            # 1계단 = +4.5 % 유지 첫 칸 (P1b step1_time)
H_SKIN_REJECT = 38.8               # SKIN_k ≥ 38.8 → H-skin 기각
H_AP_REJECT = 43.0                 # AP_k ≥ 43.0 → H-ap 기각
H_TIMER_MAX_S = 60                 # 해제 > 60 s → H-timer 기각
H_UNDECIDABLE_S = 40               # 해제 ≤ 40 s → H-ap/H-timer 못 가름
H_SKIN_HOLD_LO, H_SKIN_HOLD_HI = 100, 200   # 100~200 s 이고 SKIN_k 37~38.8 → H-skin 유지
NPU_REPRO_S = 20                   # 두 런 해제 차 ≤ 20 s → 재현
# ---- M1-GPU §5 ----
GPU_V1_OK = (20, 40)               # 회복 20~40 s 이고 계단형 → v1 ⑥ 유지(2런)
GPU_REPRO_S = 10                   # 1런째(20 s)와 차 ≤ 10 s → 재현
GPU_FIRST_RUN_RECOVERY_S = 20      # [D sim\out_1002\M1_judge.json recovery_s]
# ---- cmp (v1_예측_밤1003.md) ----
CMP = dict(gpu_onset_s=10.0, gpu_ratio_rel=0.10, skin_abs=0.5, npu_step_s=20.0, npu_ratio_abs=0.03, probe_skin_mae=0.5)
DEV_RANGE = (28.3, 31.6)           # 모형 개발 자료 시작 SKIN 범위 — 밖이면 unsupported
TRIGGER_SKIN = (39.8, 40.0)        # "트리거 = 온도대 유지" 진입 온도
TRIGGER_AP = (44.2, 44.3)
PROBE_SKIN_T = (0, 60, 120, 300, 599)


# ============================================================ 공통
def _ratio_bins(seg, ref):
    return [None if b["median_ms"] is None else b["median_ms"] / ref for b in bins10(seg)]


def _thermal_bin(run, seg, t_s):
    th = thermal_at(run, seg["start_ns"] + int(round(t_s * 1e9)))
    return th


def _shape(pr, k_rec):
    """M1M2 v1 §2 모양: 첫 칸 → 회복 칸 감소의 ≥ 50 % 가 한 칸 사이 → 계단형."""
    if k_rec is None:
        return None, None
    if k_rec == 0:
        return "즉시 회복 — 모양 판정 해당 없음", None
    total = pr[0] - pr[k_rec]
    steps = [pr[j - 1] - pr[j] for j in range(1, k_rec + 1)]
    st = dict(total_drop_ratio=total, max_single_step=max(steps), argmax_step_k=int(np.argmax(steps)) + 1,
              fraction=(max(steps) / total) if total > 0 else None)
    if total <= 0:
        return "감소 없음 — 모양 판정 해당 없음", st
    return ("계단형" if st["fraction"] >= NPU_STEP_FRACTION else "점진형"), st


def _start_skin(run, S):
    th = thermal_at(run, S["segments"][0]["start_ns"])
    return None if th is None else th["SKIN"]


def _heat_report(run, heat):
    """가열 구간: 1-1 진입(+10 %) · 1계단(+4.5 % 유지 첫 칸, step1_time) · 540~600 s 배율 · 진입·1계단 온도 · 끝 온도."""
    on = onset_1_1(heat)
    ref = on["ref_ms"]
    br = on["bins_ratio"]
    s1 = step1_time(br, level=NPU_STEP1_LEVEL) if ref else None
    r540, n540 = window_median(heat, 540, 600)
    r1000, _ = window_median(heat, 1000, 1200)
    out = dict(ref30_ms=ref, onset_1_1_s=on["onset_s"], edge_candidate_s=on["edge_candidate_s"], step1_s=s1,
               ratio_540_600=(r540 / ref) if (r540 and ref) else None, n_540_600=n540,
               ratio_1000_1200=(r1000 / ref) if (r1000 and ref) else None,
               n=heat["n"], length_s=heat["length_s"], termination_reason=heat["termination_reason"],
               bins_ratio=br, end_thermal=thermal_at(run, heat["end_ns"]),
               onset_thermal=(None if on["onset_s"] is None else _thermal_bin(run, heat, on["onset_s"])),
               step1_thermal=(None if s1 is None else _thermal_bin(run, heat, s1)),
               first_bin_le_desc=None)
    return out


# ============================================================ M1-NPU
def m1npu_judge(run, watch=None, ref_i=0, heat_i=1, probe_i=2):
    S = segments_of(run)
    if max(ref_i, heat_i, probe_i) >= len(S["segments"]):
        raise JudgeError(f"구간이 {len(S['segments'])}개 — ref/heat/probe {ref_i}/{heat_i}/{probe_i}")
    ref, heat, probe = S["segments"][ref_i], S["segments"][heat_i], S["segments"][probe_i]
    if ref["n"] == 0:
        raise JudgeError("기준 구간에 추론 없음")
    if probe["n"] == 0:
        raise JudgeError("탐침 구간에 추론 없음")
    ref_d10 = float(np.median(ref["lat_ms"]))
    ref_ratio = _ratio_bins(ref, ref_d10)
    a3 = all(r is not None and abs(r - 1.0) <= NPU_A3_TOL for r in ref_ratio)
    pr = _ratio_bins(probe, ref_d10)
    thr = 1.0 + NPU_DELTA
    last_k = min(NPU_LAST_K, len(pr) - 1 - NPU_HOLD_BINS)
    k_rec = None
    for k in range(0, last_k + 1):
        win = pr[k:k + 1 + NPU_HOLD_BINS]
        if len(win) == 1 + NPU_HOLD_BINS and all(r is not None and r <= thr for r in win):
            k_rec = k
            break
    if k_rec is None:
        recovery = dict(recovered=False, recovery_s=None, k=None, last_testable_k=last_k,
                        censored=f"{(last_k + 1) * BIN_S} s 안 미회복 (오른쪽 중도절단)")
    else:
        recovery = dict(recovered=True, recovery_s=k_rec * BIN_S, k=k_rec, last_testable_k=last_k, censored=None)
    shape, step = _shape(pr, k_rec)
    # "≤ 1.06 첫 칸" — 기술만 (판정 아님)
    k106 = next((k for k, r in enumerate(pr) if r is not None and r <= NPU_LEVEL1_DESC), None)
    # 해제 칸 k 의 SKIN_k · AP_k (칸 시작에 가장 가까운 HAL 표본) → 세 가설
    rel_th = None if k_rec is None else _thermal_bin(run, probe, k_rec * BIN_S)
    skin_k = None if rel_th is None else rel_th["SKIN"]
    ap_k = None if rel_th is None else rel_th["AP"]
    rec_s = recovery["recovery_s"]
    hyp = {}
    if rec_s is None:
        hyp["H-skin"] = "판정 불가 (미회복·중도절단)"
        hyp["H-ap"] = "판정 불가 (미회복·중도절단)"
        hyp["H-timer"] = "기각 (해제 > 60 s — 570 s 안 미회복)"
        cls = "600 s 안 미회복 — R-fast·R-skin 둘 다 기각 (중도절단)"
    else:
        hyp["H-skin"] = ("기각 (SKIN_k ≥ 38.8)" if (skin_k is not None and skin_k >= H_SKIN_REJECT)
                         else ("유지 (SKIN_k < 38.8)" if skin_k is not None else "판정 불가 (SKIN_k 없음)"))
        hyp["H-ap"] = ("기각 (AP_k ≥ 43.0)" if (ap_k is not None and ap_k >= H_AP_REJECT)
                       else ("유지 (AP_k < 43.0)" if ap_k is not None else "판정 불가 (AP_k 없음)"))
        hyp["H-timer"] = "기각 (해제 > 60 s)" if rec_s > H_TIMER_MAX_S else "유지 (해제 ≤ 60 s)"
        if rec_s <= H_UNDECIDABLE_S:
            cls = "해제 ≤ 40 s — H-ap 와 H-timer 는 못 가른다 (둘 다 그 범위 예측): H-skin 기각, H-ap/H-timer 보류 로만 적는다"
        elif rec_s <= H_TIMER_MAX_S:
            cls = "해제 40~60 s — H-timer·H-ap 범위 밖은 아니나 사전 예측(≤ 40)과 어긋남 → 미분류 (사후 가설은 [E])"
        elif rec_s < H_SKIN_HOLD_LO:
            cls = "해제 60~100 s — 세 가설 중 어느 것도 사전 예측과 맞지 않는다 → 미분류 (사후 가설은 [E])"
        elif rec_s <= H_SKIN_HOLD_HI and skin_k is not None and 37.0 <= skin_k < H_SKIN_REJECT:
            cls = "해제 100~200 s 이고 SKIN_k ≈ 37~38.8 → H-skin 유지 (R-skin)"
        elif rec_s <= H_SKIN_HOLD_HI:
            cls = "해제 100~200 s 이나 SKIN_k 가 37~38.8 밖 → 미분류 (사후 가설은 [E])"
        else:
            cls = "해제 > 200 s — 사전 예측(R-skin 130~180) 밖 → 미분류 (사후 가설은 [E])"
    probe_bins = []
    for k, b in enumerate(bins10(probe)):
        th = _thermal_bin(run, probe, b["t0"])
        probe_bins.append(dict(k=k, t0=b["t0"], ratio=pr[k], median_ms=b["median_ms"], n=b["n"],
                               SKIN=None if th is None else th["SKIN"], AP=None if th is None else th["AP"],
                               BAT=None if th is None else th["BAT"], status=None if th is None else th["thermal_status"]))
    probe_skin_at = []
    for t in PROBE_SKIN_T:
        th = _thermal_bin(run, probe, t) if t < probe["length_s"] + 1 else None
        probe_skin_at.append(dict(t=t, skin=None if th is None else th["SKIN"], ap=None if th is None else th["AP"]))
    # 반대 해석 3 (기술만): d10 가동 1 s 안 첫 10 추론 중앙 vs 나머지 — 구간 0 과 탐침
    def _first10_vs_rest(seg):
        t, lat = seg["rel_t"], seg["lat_ms"]
        per = np.floor(t / 10.0)
        firsts, rests = [], []
        for p in np.unique(per):
            m = per == p
            idx = np.where(m)[0]
            if len(idx) > 10:
                firsts.append(lat[idx[:10]]); rests.append(lat[idx[10:]])
        if not firsts:
            return None
        return dict(first10_median_ms=float(np.median(np.concatenate(firsts))), rest_median_ms=float(np.median(np.concatenate(rests))),
                    periods=len(firsts))
    heat_rep = _heat_report(run, heat)
    return dict(
        rule="M1_NPU_사전등록_v1 §2: 완전 회복 = 탐침 칸 k 와 뒤 3칸 ≤ ref_d10×1.03 → 10k s · 마지막 검정 k=56 · 없으면 570 s 안 미회복 · 계단형 = 한 칸 감소 ≥ 50 % · §3 H-skin/H-ap/H-timer",
        run_id=S["meta"].get("run_id"), chain_id=(S["meta"].get("chain_spec") or {}).get("chain_id"), chain_sha256=S["meta"].get("chain_sha256"),
        termination_reason=S["meta"].get("termination_reason"), completed_inference_count=S["meta"].get("completed_inference_count"),
        pilot_battery_pct=S["meta"].get("pilot_battery_pct"), start_skin=_start_skin(run, S),
        start_skin_in_band_29_1_31_6=(None if _start_skin(run, S) is None else bool(29.1 <= _start_skin(run, S) <= 31.6)),
        ref_d10_ms=ref_d10, ref_n=ref["n"], ref_bins_ratio=ref_ratio, a3_reference_stable=a3,
        a3_label=("기준 안정" if a3 else "기준 불안정 (±5 % 밖 칸 있음)"), ref_first10_vs_rest=_first10_vs_rest(ref),
        recovery=recovery, shape=shape, step=step, first_bin_le_1_06_k=k106, first_bin_le_1_06_s=(None if k106 is None else k106 * BIN_S),
        release_thermal=rel_th, SKIN_k=skin_k, AP_k=ap_k, hypotheses=hyp, classification=cls,
        probe=dict(accelerator=probe["accelerator"], duty=probe["duty"], length_s=probe["length_s"], n=probe["n"],
                   termination_reason=probe["termination_reason"], bins_ratio=pr, bins=probe_bins,
                   start_thermal=thermal_at(run, probe["start_ns"]), start_soc=soc_at(watch, probe["start_wall_ms"]),
                   probe_skin_at=probe_skin_at, first10_vs_rest=_first10_vs_rest(probe)),
        heat=heat_rep, transitions=S["transitions"],
        segment_start_soc={str(s["index"]): soc_at(watch, s["start_wall_ms"]) for s in S["segments"]},
        segment_start_thermal={str(s["index"]): thermal_at(run, s["start_ns"]) for s in S["segments"]},
    )


def m1npu_pair(a, b):
    """두 런 해제 시각 차 ≤ 20 s → 재현 (§3 끝)."""
    ra, rb = a["recovery"]["recovery_s"], b["recovery"]["recovery_s"]
    if ra is None or rb is None:
        return dict(rule="두 런 해제 차 ≤ 20 s → 재현", a_s=ra, b_s=rb, diff_s=None,
                    verdict="1런씩 보고 (한쪽 이상 중도절단)")
    d = abs(ra - rb)
    return dict(rule="두 런 해제 차 ≤ 20 s → 재현", a_s=ra, b_s=rb, diff_s=d, verdict=("재현" if d <= NPU_REPRO_S else "1런씩 보고"),
                shapes=[a["shape"], b["shape"]], SKIN_k=[a["SKIN_k"], b["SKIN_k"]], AP_k=[a["AP_k"], b["AP_k"]],
                classifications=[a["classification"], b["classification"]])


# ============================================================ M1-GPU 2런째
def m1gpu_judge(run, watch=None, first_run_recovery_s=GPU_FIRST_RUN_RECOVERY_S):
    j = J.m1_judge(run, watch=watch)          # M1M2 v1 §2 글자 그대로 (m1m2_judge_1002)
    S = segments_of(run)
    rec = j["recovery"]["recovery_s"]
    shape = j["shape"]
    if rec is not None and GPU_V1_OK[0] <= rec <= GPU_V1_OK[1] and shape == "계단형":
        v1 = "v1 ⑥ 유지(2런)"
    else:
        v1 = "v1 ⑥ 기각"
    if rec is None:
        repro = "1런씩 보고 (중도절단)"
    else:
        repro = "재현" if abs(rec - first_run_recovery_s) <= GPU_REPRO_S else "1런씩 보고"
    probe = S["segments"][2]
    heat = S["segments"][1]
    rel_th = None if rec is None else _thermal_bin(run, probe, rec)
    j.update(dict(
        rule_v1="M1_NPU_사전등록_v1 §5: 회복 20~40 s 이고 계단형 → v1 ⑥ 유지(2런) · 1런째(20 s)와 차 ≤ 10 s → 재현",
        v1_check_6=v1, first_run_recovery_s=first_run_recovery_s, reproduction=repro,
        release_thermal=rel_th, SKIN_k=None if rel_th is None else rel_th["SKIN"], AP_k=None if rel_th is None else rel_th["AP"],
        start_skin=_start_skin(run, S), chain_id=(S["meta"].get("chain_spec") or {}).get("chain_id"), chain_sha256=S["meta"].get("chain_sha256"),
        termination_reason=S["meta"].get("termination_reason"), completed_inference_count=S["meta"].get("completed_inference_count"),
        heat_extra=_heat_report(run, heat),
        segment_start_thermal={str(s["index"]): thermal_at(run, s["start_ns"]) for s in S["segments"]},
    ))
    return j


# ============================================================ cmp — 동결 예측 vs 실측
def _pick_col(pred_keys, start_skin, suffix=""):
    """비교 열 = 실제 시작 SKIN 에 가까운 쪽 (29.5 / 30.5)."""
    cands = []
    for k in pred_keys:
        base = k.split("/")[0]
        try:
            cands.append((abs(float(base) - start_skin), k))
        except ValueError:
            continue
    if not cands or start_skin is None:
        return None
    cands.sort()
    return cands[0][1]


def _supported(start_skin):
    if start_skin is None:
        return False, "시작 SKIN 미확인 → unsupported"
    ok = DEV_RANGE[0] <= start_skin <= DEV_RANGE[1]
    return ok, ("적용 범위 안" if ok else f"적용 범위 밖 (unsupported): 시작 SKIN {start_skin} ∉ [{DEV_RANGE[0]}, {DEV_RANGE[1]}] — 범위를 넓히지 않는다")


def _row(name, pred, meas, crit, verdict, wrong_part):
    return dict(cell=name, predicted=pred, measured=meas, criterion=crit, verdict=verdict, if_wrong=wrong_part)


def cmp_gpu(pred_gpu, j, label):
    sk = j.get("start_skin")
    col = _pick_col(pred_gpu.keys(), sk)
    sup, sup_note = _supported(sk)
    rows = []
    if col is None:
        return dict(label=label, column=None, start_skin=sk, supported=sup, support_note=sup_note, rows=[], note="예측 열 없음")
    p = pred_gpu[col]
    hx = j["heat_extra"]; hs = j["heat_segment"]
    # 진입
    m = hs["onset_s"]; pv = p["heat_onset_s"]
    ok = None if m is None else abs(m - pv) <= CMP["gpu_onset_s"]
    rows.append(_row("가열 진입 (1-1)", pv, m, "|Δ| ≤ 10 s", _v(ok), "GPU CM 제어기 T_set·K (진입)"))
    for key, name, wrong in (("ratio_540_600", "540~600 s 배율", "깊이 (K·u_max·α)"), ("ratio_1000_1200", "1000~1200 s 배율", "느린 노드 G_s·τ_s")):
        m = hs.get(key); pv = p.get(key)
        ok = None if (m is None or pv is None) else abs(m / pv - 1.0) <= CMP["gpu_ratio_rel"]
        rows.append(_row(name, pv, m, "상대차 ≤ 10 %", _v(ok), wrong))
    et = j.get("heat_end_thermal") or {}
    m = et.get("SKIN"); pv = p.get("heat_end_skin")
    ok = None if m is None else abs(m - pv) <= CMP["skin_abs"]
    rows.append(_row("가열 끝 SKIN", pv, m, "|Δ| ≤ 0.5 ℃", _v(ok), "열 모형 (v1 은 이미 +0.7 높다 [E])"))
    rows.append(_row("가열 끝 AP · status (기술)", [p.get("heat_end_ap"), p.get("heat_end_status")], [et.get("AP"), et.get("thermal_status")], "기술만", "—", "—"))
    rec = j["recovery"]["recovery_s"]; shape = j["shape"]
    pr = p["recovery"]
    if rec is None:
        v = "계단 해제 구조 기각 (중도절단)"
    elif GPU_V1_OK[0] <= rec <= GPU_V1_OK[1] and shape == "계단형":
        v = "v1 ⑥ 유지(2런)" + (" — 회복 20 s 이면 v1 T_off placeholder(39.2) 가 ~0.4 ℃ 낮은 것" if rec == 20 else "")
    else:
        v = "계단 해제 구조 기각 (≥ 40 s 또는 점진형)"
    rows.append(_row("탐침 회복 시각 · 모양", [pr["recovery_s"], pr["shape"]], [rec, shape], "20~40 s 이고 계단형 → ⑥ 유지", v, "T_off placeholder / 계단 해제 구조"))
    rows.append(_row("해제 순간 SKIN · AP (기술)", [p["release_skin_ap"]["skin"], p["release_skin_ap"]["ap"]], [j.get("SKIN_k"), j.get("AP_k")], "기술만", "—", "—"))
    rows.append(_row("탐침 첫 8칸 배율 (기술)", p.get("probe_bins_ratio_first8"), (j["probe"]["bins_ratio"] or [])[:8], "기술만", "—", "—"))
    return dict(label=label, column=col, start_skin=sk, supported=sup, support_note=sup_note, rows=rows)


def _v(ok):
    return "미확인" if ok is None else ("맞음" if ok else "틀림")


def cmp_npu(pred_npu, j, label):
    sk = j.get("start_skin")
    sup, sup_note = _supported(sk)
    bases = sorted({k.split("/")[0] for k in pred_npu})
    col_base = _pick_col(bases, sk)
    if col_base is None:
        return dict(label=label, column=None, start_skin=sk, supported=sup, support_note=sup_note, rows=[], note="예측 열 없음")
    fast = pred_npu.get(f"{col_base}/fast"); skin = pred_npu.get(f"{col_base}/skin")
    base = fast or skin
    rows = []
    h = j["heat"]
    # 1계단 · 2계단 (두 변형의 가열 예측은 같다 — fast 열로)
    m1, m2 = h["step1_s"], h["onset_1_1_s"]
    for name, m, pv in (("가열 1계단 (+4.5 % 유지 첫 칸)", m1, base["step1_s"]), ("가열 2계단 (1-1 진입)", m2, base["step2_s"])):
        ok = None if m is None else abs(m - pv) <= CMP["npu_step_s"]
        rows.append(_row(name, pv, m, "|Δ| ≤ 20 s", _v(ok) + ("" if ok is not False else " → AP 노드 하위모형 기각 (홀드아웃 확정)"),
                         "AP 단일 노드 하위모형 (시각)"))
    # 진입 온도 — 트리거 = 온도대 유지?
    ot = h.get("onset_thermal") or {}
    s_in = ot.get("SKIN") is not None and TRIGGER_SKIN[0] <= ot["SKIN"] <= TRIGGER_SKIN[1]
    a_in = ot.get("AP") is not None and TRIGGER_AP[0] <= ot["AP"] <= TRIGGER_AP[1]
    tv = ("트리거 = 온도대 유지 (진입 SKIN 39.8~40.0 · AP 44.2~44.3 안)" if (s_in and a_in)
          else ("미확인" if ot.get("SKIN") is None else "진입 온도가 3런 범위 밖 — 온도대 유지 주장 못 함"))
    rows.append(_row("2계단 진입 SKIN · AP", [base["step2_skin_ap"]["skin"], base["step2_skin_ap"]["ap"]], [ot.get("SKIN"), ot.get("AP")],
                     "SKIN 39.8~40.0 · AP 44.2~44.3 → 트리거 = 온도대 유지", tv, "트리거 형태"))
    st1 = h.get("step1_thermal") or {}
    rows.append(_row("1계단 SKIN · AP (기술)", [base["step1_skin_ap"]["skin"], base["step1_skin_ap"]["ap"]], [st1.get("SKIN"), st1.get("AP")], "기술만", "—", "—"))
    m = h["ratio_540_600"]; pv = base["ratio_540_600"]
    ok = None if m is None else abs(m - pv) <= CMP["npu_ratio_abs"]
    rows.append(_row("540~600 s 배율", pv, m, "|Δ| ≤ 0.03", _v(ok), "계단 크기 (a1·a2·K)"))
    et = h.get("end_thermal") or {}
    m = et.get("SKIN"); pv = base["heat_end_skin"]
    ok = None if m is None else abs(m - pv) <= CMP["skin_abs"]
    rows.append(_row("가열 끝 SKIN", pv, m, "|Δ| ≤ 0.5 ℃", _v(ok) + ("" if ok is not False else " → 열 모형 과대/과소"), "열 모형"))
    rows.append(_row("가열 끝 AP · status (기술)", [base["heat_end_ap"], base["heat_end_status"]], [et.get("AP"), et.get("thermal_status")], "기술만", "—", "—"))
    # 해제 — 두 변형을 가른다
    rec = j["recovery"]["recovery_s"]
    if rec is None:
        rv = "600 s 안 없음 → R-fast·R-skin 둘 다 기각 (중도절단)"
    elif rec <= 60:
        rv = "≤ 60 s → R-fast(AP/타이머) 쪽 · R-skin 틀림"
    elif rec < 100:
        rv = "60~100 s → 어느 변형도 맞지 않는다 (사전 등록 §3 규칙으로 가른다)"
    elif rec <= 200:
        rv = "100~200 s → R-skin 쪽 · R-fast 틀림"
    else:
        rv = "> 200 s → 어느 변형도 맞지 않는다"
    rows.append(_row("탐침 해제 시각 (δ 0.03)", dict(fast=None if fast is None else fast["recovery_delta003_s"], skin=None if skin is None else skin["recovery_delta003_s"]),
                     rec, "≤ 60 → R-fast · 100~200 → R-skin · 없음 → 둘 다 기각", rv, "해제 규칙 (R-fast / R-skin)"))
    rows.append(_row("해제 때 SKIN · AP (기술)", dict(fast=None if fast is None else fast["release_skin_ap"], skin=None if skin is None else skin["release_skin_ap"]),
                     [j.get("SKIN_k"), j.get("AP_k")], "기술만", "—", "—"))
    # 탐침 모양
    shape = j["shape"]
    sv = "점진 하강 → 두 변형 다 '계단 해제' 기각" if shape == "점진형" else ("계단형 → 계단 해제 유지" if shape == "계단형" else f"{shape}")
    rows.append(_row("탐침 칸 배율 모양", "계단 (×1.14~1.16 유지 → 1.00)", [shape, (j["probe"]["bins_ratio"] or [])[:12]], "점진이면 계단 해제 기각", sv, "계단 해제 구조"))
    # 탐침 SKIN MAE (0/60/120/300/599)
    meas_sk = {d["t"]: d["skin"] for d in j["probe"]["probe_skin_at"]}
    errs = []
    for d in base["probe_skin_at"]:
        mv = meas_sk.get(d["t"])
        if mv is not None:
            errs.append(abs(mv - d["skin"]))
    mae = float(np.mean(errs)) if errs else None
    ok = None if mae is None else mae <= CMP["probe_skin_mae"]
    rows.append(_row("탐침 SKIN (0/60/120/300/599 s) MAE", [d["skin"] for d in base["probe_skin_at"]], [meas_sk.get(t) for t in PROBE_SKIN_T],
                     "MAE ≤ 0.5 ℃", _v(ok) + (f" (MAE {mae:.2f})" if mae is not None else ""), "냉각 τ (v1 은 가열 τ 와 같다고 가정)"))
    return dict(label=label, column=col_base, columns_used=[k for k in (f"{col_base}/fast", f"{col_base}/skin") if k in pred_npu],
                start_skin=sk, supported=sup, support_note=sup_note, rows=rows)


def cmp_all(pred_v1, pred_v2=None, pred_pacing=None, m1gpu=None, m1npu_a=None, m1npu_b=None):
    out = dict(rule="v1_예측_밤1003.md '이 차이면 틀린 것' 열 그대로 · 비교 열 = 시작 SKIN 에 가까운 쪽 · 시작 SKIN ∉ [28.3, 31.6] → unsupported",
               models=dict(v1=pred_v1.get("model"), v2=(None if pred_v2 is None else pred_v2.get("model")),
                           v1_pacing=(None if pred_pacing is None else pred_pacing.get("model"))),
               v2_present=pred_v2 is not None, v1_pacing_present=pred_pacing is not None, v1={}, v2={})
    if pred_v2 is None:
        out["v2_note"] = "v2 없음 — v1 만 대조 (P1b-2 미완)"
    if m1gpu is not None:
        out["v1"]["m1_gpu_r2"] = cmp_gpu(pred_v1["m1_gpu"], m1gpu, "M1-GPU 2런째")
        if pred_v2 is not None and "m1_gpu" in pred_v2:
            out["v2"]["m1_gpu_r2"] = cmp_gpu(pred_v2["m1_gpu"], m1gpu, "M1-GPU 2런째 (v2)")
    for lab, jj in (("m1_npu_a", m1npu_a), ("m1_npu_b", m1npu_b)):
        if jj is not None:
            out["v1"][lab] = cmp_npu(pred_v1["m1_npu"], jj, f"M1-NPU {lab[-1]}")
            if pred_v2 is not None and "m1_npu" in pred_v2:
                out["v2"][lab] = cmp_npu(pred_v2["m1_npu"], jj, f"M1-NPU {lab[-1]} (v2)")
    return out


# ============================================================ selftest (합성 — 결과 보기 전 양방향)
def _write_thermal(rd, load0_ns, end_ns, skin_fn, ap_fn):
    """_synth_run(thermal=False) 뒤 사용자 정의 HAL 표본 (1 s)."""
    with open(os.path.join(rd, "raw", "thermalservice.jsonl"), "w", encoding="utf-8") as fh:
        m = load0_ns - 60_000_000_000
        while m <= end_ns + 5_000_000_000:
            t = (m - load0_ns) / 1e9
            fh.write(json.dumps(dict(source="thermalservice", event="sample", mono_ns=m, parse_status="ok", SKIN=f"{skin_fn(t):.1f}",
                                     AP=f"{ap_fn(t):.1f}", BAT=f"{skin_fn(t) - 2:.1f}", PA=f"{skin_fn(t):.1f}", thermal_status="0")) + "\n")
            m += 1_000_000_000


def _npu_run(tmp, tag, probe_ratio, skin_k=37.5, ap_k=40.0, ref_fn=None, heat_fn=None, start_skin=30.0):
    """NPU d10 60 → d100 600 → d10 600 합성. 탐침 배율 = 10 s 칸 리스트. 온도: 가열 중 start→42, 탐침 중 42→(해제 칸 값 근처로 선형)."""
    pr = list(probe_ratio)
    probe = lambda t: 0.75 * pr[min(int(t // 10), len(pr) - 1)]
    const = lambda v: (lambda t: v)
    heat = heat_fn or (lambda t: 0.75 if t < 150 else (0.75 * 1.09 if t < 300 else 0.75 * 1.13))
    segs = [dict(accelerator="NPU", duty=10, duration_s=60, lat_ms=ref_fn or const(0.75)),
            dict(accelerator="NPU", duty=100, duration_s=600, lat_ms=heat),
            dict(accelerator="NPU", duty=10, duration_s=600, lat_ms=probe)]
    rd = _synth_run(tmp, tag, segs, rate=100.0, thermal=False)
    run = load_run(rd)
    S = segments_of(run)
    load0 = S["load_start_ns"]
    p0 = (S["segments"][2]["start_ns"] - load0) / 1e9
    h0 = (S["segments"][1]["start_ns"] - load0) / 1e9
    def skin(t):
        if t < h0: return start_skin
        if t < p0: return start_skin + (42.0 - start_skin) * min(1.0, (t - h0) / 600.0)
        return 42.0 + (skin_k - 42.0) * min(1.0, (t - p0) / 120.0)
    def ap(t):
        if t < h0: return start_skin - 1.0
        if t < p0: return start_skin - 1.0 + (46.2 - start_skin + 1.0) * min(1.0, (t - h0) / 600.0)
        return 46.2 + (ap_k - 46.2) * min(1.0, (t - p0) / 30.0)
    _write_thermal(rd, load0, S["load_end_ns"], skin, ap)
    return load_run(rd)


def selftest():
    res = []
    def check(name, cond, got):
        res.append((name, bool(cond), got))
    tmp = tempfile.mkdtemp(prefix="night1003_selftest_")
    try:
        # --- M1-NPU §2 ---
        j = m1npu_judge(_npu_run(tmp, "n_k5", [1.14] * 5 + [1.01] * 55))
        check("탐침 k=5 부터 4칸 ≤ ×1.03 → 50 s", j["recovery"]["recovery_s"] == 50, j["recovery"])
        check("한 칸에 ×1.14 → ×1.01 → 계단형", j["shape"] == "계단형", f"{j['shape']} {j['step']}")
        j = m1npu_judge(_npu_run(tmp, "n_cens", [1.09] * 60))
        check("끝까지 ×1.09 → 570 s 안 미회복 (중도절단)", j["recovery"]["recovered"] is False and "570 s" in j["recovery"]["censored"], j["recovery"])
        check("중도절단 → H-timer 기각 · R-fast/R-skin 둘 다 기각", "둘 다 기각" in j["classification"] and j["hypotheses"]["H-timer"].startswith("기각"), j["classification"])
        j = m1npu_judge(_npu_run(tmp, "n_step", [1.12] * 3 + [1.01] * 57))
        check("한 칸에 ×1.12 → ×1.01 → 계단형 · 30 s", j["shape"] == "계단형" and j["recovery"]["recovery_s"] == 30, f"{j['shape']} {j['recovery']}")
        lin = [max(1.0, 1.14 - 0.01 * k) for k in range(60)]        # k=11 → 1.03 ≤ 1.03
        j = m1npu_judge(_npu_run(tmp, "n_lin", lin))
        check("선형 감소 → 점진형", j["shape"] == "점진형", f"{j['shape']} {j['recovery']} {j['step']}")
        check("≤ 1.06 첫 칸 기술 (선형: k=8 → 80 s)", j["first_bin_le_1_06_s"] == 80, j["first_bin_le_1_06_s"])
        j = m1npu_judge(_npu_run(tmp, "n_dip", [1.14] * 4 + [1.01, 1.01, 1.08, 1.01] + [1.01] * 52))
        check("4칸 유지 안 되는 일시 하강은 회복 아님 → 70 s", j["recovery"]["recovery_s"] == 70, j["recovery"])
        check("A3: 평탄 기준 → 기준 안정", j["a3_reference_stable"] is True, j["a3_label"])
        j = m1npu_judge(_npu_run(tmp, "n_a3", [1.01] * 60, ref_fn=lambda t: 0.75 if t < 30 else 0.85))
        check("A3: 기준 칸 ±5 % 밖 → 기준 불안정 (판정은 한다)", j["a3_reference_stable"] is False and j["recovery"]["recovered"], j["a3_label"])
        check("가열 1계단 150 s (+4.5 % 유지) · 2계단(1-1) 300 s (합성)", j["heat"]["step1_s"] == 150 and j["heat"]["onset_1_1_s"] == 300, j["heat"]["step1_s"], )
        check("540~600 s 배율 ×1.13 (합성)", j["heat"]["ratio_540_600"] is not None and abs(j["heat"]["ratio_540_600"] - 1.13) < 0.005, j["heat"]["ratio_540_600"])
        # --- §3 세 가설 ---
        j = m1npu_judge(_npu_run(tmp, "h_skin", [1.14] * 13 + [1.01] * 47, skin_k=39.0, ap_k=40.0))   # 해제 130 s, SKIN_k 39.0
        check("SKIN_k 39.0 → H-skin 기각", j["hypotheses"]["H-skin"].startswith("기각"), f"SKIN_k={j['SKIN_k']} {j['hypotheses']}")
        j = m1npu_judge(_npu_run(tmp, "h_ap", [1.14] * 13 + [1.01] * 47, skin_k=37.5, ap_k=42.0))     # AP_k 42.0
        check("AP_k 42.0 → H-ap 유지", j["hypotheses"]["H-ap"].startswith("유지"), f"AP_k={j['AP_k']} {j['hypotheses']}")
        check("해제 130 s · SKIN_k 37.5 → H-skin 유지 (R-skin) · H-timer 기각", "H-skin 유지" in j["classification"] and j["hypotheses"]["H-timer"].startswith("기각"), j["classification"])
        j = m1npu_judge(_npu_run(tmp, "h_30", [1.14] * 3 + [1.01] * 57, skin_k=39.5, ap_k=40.2))
        check("해제 30 s → 'H-ap/H-timer 못 가름' 선언", "못 가른다" in j["classification"] and j["recovery"]["recovery_s"] == 30, j["classification"])
        j = m1npu_judge(_npu_run(tmp, "h_80", [1.14] * 8 + [1.01] * 52))
        check("해제 80 s → 미분류", "미분류" in j["classification"], j["classification"])
        # --- 재현 ---
        a = m1npu_judge(_npu_run(tmp, "r_a", [1.14] * 4 + [1.01] * 56)); b = m1npu_judge(_npu_run(tmp, "r_b", [1.14] * 5 + [1.01] * 55))
        check("두 런 해제 40 · 50 s (차 10 ≤ 20) → 재현", m1npu_pair(a, b)["verdict"] == "재현", m1npu_pair(a, b))
        c = m1npu_judge(_npu_run(tmp, "r_c", [1.14] * 13 + [1.01] * 47))
        check("두 런 해제 40 · 130 s → 1런씩 보고", m1npu_pair(a, c)["verdict"] == "1런씩 보고", m1npu_pair(a, c)["diff_s"])
        # --- M1-GPU §5 ---
        def gpu_run(tag, probe_ratio):
            pr = list(probe_ratio); probe = lambda t: 2.5 * pr[min(int(t // 10), len(pr) - 1)]
            segs = [dict(accelerator="GPU", duty=10, duration_s=60, lat_ms=lambda t: 2.5),
                    dict(accelerator="GPU", duty=100, duration_s=1200, lat_ms=lambda t: 2.5 if t < 80 else 5.1),
                    dict(accelerator="GPU", duty=10, duration_s=300, lat_ms=probe)]
            return load_run(_synth_run(tmp, tag, segs, rate=20.0))
        g = m1gpu_judge(gpu_run("g_20", [2.02, 2.0] + [0.98] * 28))
        check("GPU 회복 20 s 계단형 → v1 ⑥ 유지(2런) · 1런째와 재현", g["v1_check_6"] == "v1 ⑥ 유지(2런)" and g["reproduction"] == "재현", f"{g['recovery']} {g['shape']} {g['v1_check_6']} {g['reproduction']}")
        g = m1gpu_judge(gpu_run("g_50", [2.02] * 5 + [0.98] * 25))
        check("GPU 회복 50 s → ⑥ 기각 · 1런씩 보고", g["v1_check_6"] == "v1 ⑥ 기각" and g["reproduction"] == "1런씩 보고", f"{g['recovery']} {g['v1_check_6']}")
        g = m1gpu_judge(gpu_run("g_lin", [2.0 - 0.05 * k for k in range(30)]))     # k=18 → 1.10 ≤ 1.10 → 180 s · 점진형
        check("GPU 점진형 (180 s) → ⑥ 기각", g["v1_check_6"] == "v1 ⑥ 기각" and g["shape"] == "점진형" and g["recovery"]["recovery_s"] == 180, f"{g['recovery']} {g['shape']}")
        g = m1gpu_judge(gpu_run("g_cens", [2.0] * 30))
        check("GPU 끝까지 ×2.0 → 중도절단 · ⑥ 기각", g["v1_check_6"] == "v1 ⑥ 기각" and g["recovery"]["recovered"] is False, g["recovery"])
        # --- cmp ---
        pred_path = os.path.join(REPO, "d1sim", "out", "night_1003_prediction.json")
        pred = json.load(open(pred_path, encoding="utf-8"))
        jn = m1npu_judge(_npu_run(tmp, "c_in", [1.14] * 4 + [1.01] * 56, start_skin=29.7))
        c = cmp_all(pred, None, None, None, jn, None)
        check("v2 JSON 없음 → v1 만 대조 · 'v2 없음' 기록", c["v2_present"] is False and "v2 없음" in c.get("v2_note", "") and "m1_npu_a" in c["v1"], c.get("v2_note"))
        check("비교 열 = 시작 SKIN 29.7 → 29.5 열", c["v1"]["m1_npu_a"]["column"] == "29.5" and c["v1"]["m1_npu_a"]["supported"] is True, c["v1"]["m1_npu_a"]["column"])
        rel_row = next(r for r in c["v1"]["m1_npu_a"]["rows"] if r["cell"].startswith("탐침 해제"))
        check("해제 40 s → R-fast 쪽", "R-fast" in rel_row["verdict"] and "R-skin 틀림" in rel_row["verdict"], rel_row["verdict"])
        jo = m1npu_judge(_npu_run(tmp, "c_out", [1.14] * 4 + [1.01] * 56, start_skin=27.9))
        c2 = cmp_all(pred, None, None, None, jo, None)
        check("시작 SKIN 27.9 → 모형 대조 unsupported", c2["v1"]["m1_npu_a"]["supported"] is False and "unsupported" in c2["v1"]["m1_npu_a"]["support_note"], c2["v1"]["m1_npu_a"]["support_note"])
        jg = m1gpu_judge(gpu_run("c_g", [2.02, 2.0] + [0.98] * 28))
        c3 = cmp_all(pred, None, None, jg, None, None)
        on_row = next(r for r in c3["v1"]["m1_gpu_r2"]["rows"] if r["cell"].startswith("가열 진입"))
        check("GPU 진입 80 vs 예측 70 → |Δ| 10 ≤ 10 맞음", on_row["verdict"] == "맞음" and on_row["measured"] == 80, on_row)
        rec_row = next(r for r in c3["v1"]["m1_gpu_r2"]["rows"] if r["cell"].startswith("탐침 회복"))
        check("GPU 회복 20 s → ⑥ 유지 + T_off 0.4 ℃ 주석", "⑥ 유지" in rec_row["verdict"] and "0.4" in rec_row["verdict"], rec_row["verdict"])
        # v2 가짜 JSON 이 있으면 v2 열도 채운다
        fake_v2 = {"model": "fake-v2", "m1_npu": pred["m1_npu"], "m1_gpu": pred["m1_gpu"]}
        c4 = cmp_all(pred, fake_v2, None, jg, jn, None)
        check("v2 JSON 있으면 v2 열도 채움", c4["v2_present"] and "m1_npu_a" in c4["v2"] and "m1_gpu_r2" in c4["v2"], list(c4["v2"].keys()))
        # --- 구조 · 결정성 ---
        rd = _npu_run(tmp, "struct_ok", [1.01] * 60)
        lines = open(rd["jsonl"], encoding="utf-8").read().splitlines()
        keep = [l for l in lines if not ('"segment_start"' in l and J._detail(json.loads(l)).get("index") == 1)]
        keep = [l for l in keep if not ('"segment_end"' in l and J._detail(json.loads(l)).get("index") == 1)]
        bad = os.path.join(tmp, "struct_bad", "runs", "run-bad"); os.makedirs(os.path.join(bad, "gpu"), exist_ok=True)
        open(os.path.join(bad, "gpu", "x.jsonl"), "w", encoding="utf-8").write("\n".join(keep) + "\n")
        try:
            m1npu_judge(load_run(bad)); check("구간 하나 뺀 JSONL → 오류로 멈춤", False, "판정이 나왔다")
        except JudgeError as err:
            check("구간 하나 뺀 JSONL → 오류로 멈춤", True, str(err))
        a1 = dumps(m1npu_judge(_npu_run(tmp, "det1", [1.14] * 4 + [1.01] * 56)))
        a2 = dumps(m1npu_judge(_npu_run(tmp, "det2", [1.14] * 4 + [1.01] * 56)))
        check("결정성: 같은 입력 두 번 = 같은 바이트 (run_id 제외)", a1.replace("det1", "X") == a2.replace("det2", "X"), f"{len(a1)} B")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    ok = all(c for _, c, _ in res)
    print("| 시험 | 결과 | 값 |\n|---|---|---|")
    for name, c, got in res:
        print(f"| {name} | {'PASS' if c else 'FAIL'} | {str(got)[:170]} |")
    print(f"\nselftest 전체: {'PASS' if ok else 'FAIL'} ({sum(1 for _, c, _ in res if c)}/{len(res)})")
    return 0 if ok else 1


# ============================================================ CLI
def _load_json(p):
    return None if not p else json.load(open(p, encoding="utf-8"))


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("selftest")
    a = sub.add_parser("m1npu"); a.add_argument("run_dir"); a.add_argument("--second"); a.add_argument("--watch"); a.add_argument("--out")
    a = sub.add_parser("m1gpu"); a.add_argument("run_dir"); a.add_argument("--first-run-recovery-s", type=float, default=GPU_FIRST_RUN_RECOVERY_S)
    a.add_argument("--watch"); a.add_argument("--out")
    a = sub.add_parser("cmp"); a.add_argument("--pred", required=True); a.add_argument("--pred-v2"); a.add_argument("--pred-pacing")
    a.add_argument("--m1gpu"); a.add_argument("--m1npu-a"); a.add_argument("--m1npu-b"); a.add_argument("--out")
    args = p.parse_args(argv)
    if args.cmd == "selftest":
        return selftest()
    try:
        if args.cmd == "m1npu":
            res = m1npu_judge(load_run(args.run_dir), load_watch(args.watch))
            if args.second:
                res2 = m1npu_judge(load_run(args.second), load_watch(args.watch))
                res = dict(a=res, b=res2, pair=m1npu_pair(res, res2))
        elif args.cmd == "m1gpu":
            res = m1gpu_judge(load_run(args.run_dir), load_watch(args.watch), args.first_run_recovery_s)
        else:
            for k in ("pred_v2", "pred_pacing"):
                v = getattr(args, k)
                if v and not os.path.exists(v):
                    print(f"NOTE: {k} 파일 없음 → 생략 ({v})", file=sys.stderr); setattr(args, k, None)
            res = cmp_all(_load_json(args.pred), _load_json(args.pred_v2), _load_json(args.pred_pacing),
                          _load_json(args.m1gpu), _load_json(args.m1npu_a), _load_json(args.m1npu_b))
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
