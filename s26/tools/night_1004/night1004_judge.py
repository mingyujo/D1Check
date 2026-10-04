# -*- coding: utf-8 -*-
"""night1004_judge.py — 밤 1004 판정기: N50P · G50P · GI300 · NI300 + 동결 예측 대조 (cmp).
`밤1004_사전등록_v1.md` (동결 c80f9e1, SHA 70f7cae2…) §1~§5·§8 을 글자 그대로. 구간 추출은 `m1m2_judge_1002.py` (SHA ea282d4a…) 의
segments 정의를 import, 1계단 시각은 `d1sim\\tools\\fit_throttle_v1.py` (379039dd…) 의 step1_time import, 칸 배율·HAL 표본·모양·
합성 HAL 쓰기는 `night1003_judge.py` (a5ceab41…) 의 함수 import — 전부 복사·수정 금지. results\\ 는 읽기만. 같은 입력 두 번 = 같은 바이트.

  py night1004_judge.py selftest
  py night1004_judge.py n50p  <run_dir> [--watch csv] [--out f.json]
  py night1004_judge.py g50p  <run_dir> [--watch csv] [--out f.json]
  py night1004_judge.py gi300 <run_dir> [--watch csv] [--out f.json]
  py night1004_judge.py ni300 <run_dir> [--watch csv] [--out f.json]
  py night1004_judge.py cmp [--pred-v2 night_1004_prediction_v2.json] [--pred-v1 night_1004_prediction_v1.json]
                            [--n50p f.json] [--g50p f.json] [--gi300 f.json] [--ni300 f.json] [--out f.json]

규칙 (사전 등록 글자 그대로 — 결과 본 뒤 바꾸지 않는다):
  공통 §1: 구간 창 = segment_start.start_ns ~ segment_end.end_ns · 전환 창 제외 · 지연 = 러너 JSONL latency_ns (write+run+read) ·
       10 s 칸 = 구간 시작 기준 [10k, 10k+10) 에 시작한 추론 전수 중앙 · 온도 = thermalservice HAL 표본 ·
       칸의 SKIN_k·AP_k = 칸 k 시작에 가장 가까운 HAL 표본 · 칸 k + 뒤 3칸 규칙 (첫 칸만으로 판정하지 않는다)
  N50P §2: ref_d50 = 구간 0 전수 중앙 · A3 = 구간 0 칸 배율 전부 ±5 % → "기준 안정" (아니면 표시, 판정은 한다) ·
       가열 (구간 1, ref30 = 처음 30 s 중앙): 1-1 진입 (+10 %, 칸 + 뒤 3칸) · 1계단 (step1_time, +4.5 % 유지 첫 칸) · 360~420 s 배율 ·
       끝 SKIN·AP·BAT·status · 전제: 360~420 s 배율 ≥ 1.06 → "가열 충분", 아니면 "가열 부족 — 탐침 판정 불가" (기술만) ·
       해제 = 구간 2 첫 칸 k 로서 칸 k 와 뒤 3칸 ≤ ref_d50 × 1.03 → 10k s, 마지막 검정 k = 44, 없으면 "440 s 안 미회복 (중도절단)" ·
       모양 = 첫 칸 → 해제 칸 감소의 ≥ 50 % 가 한 칸 사이 → 계단형, 아니면 점진형 (해제가 있을 때만) ·
       분류: ≤ 40 s R50-fast · 60~440 s R50-slow · 중도절단 R50-none · 50 s 미분류 ·
       가설: H-timer → R50-fast · H-load (θ ≤ 50 %) → R50-slow/none · H-load (θ > 50 %) → R50-fast ·
       → R50-fast: "H-timer 와 H-load(θ > 50 %) 는 못 가른다 — 다음은 d75" · R50-slow/none: "H-timer 기각 · H-load(θ ≤ 50 %) 쪽" ·
       보조 (기술): 탐침 1~5 칸 (10~60 s) 중앙 배율 · 해제 SKIN_k·AP_k (d10 해제 41.4 · 43.9 와 나란히) ·
       해제 뒤 칸 k′ + 뒤 3칸 ≥ ref_d50 × 1.06 → "해제 뒤 재조임 (k′)" · 탐침 SKIN·AP·BAT 0/60/120/240/479 s
  G50P §3: 같은 틀 · 해제 = 칸 k + 뒤 3칸 ≤ ref_d50 × 1.10, 마지막 k = 44 · 가열 1-1 진입 · 240~300 s 배율 · 끝 SKIN·AP ·
       전제 240~300 s 배율 ≥ 1.5 · 분류 = §2 경계 · H-timer → R50-fast · H-ap-히스: 해제 칸 AP_k ≥ 40.0 → 기각 ·
       H-load(GPU) → R50-slow/none · 보조: 탐침 1~5 칸 · 해제 SKIN_k·AP_k vs d10 해제 (SKIN 37.1~38.2 · AP 38.0~39.1) · 0928 M3 참고
  GI300 §4: ref_d100 = 구간 1 처음 30 s 전수 중앙 · 구간 1 진입 · 540~600 s 배율 · 휴지: 지연 판정 없음 (칸 배율 기술만) ·
       휴지 SKIN·AP·BAT 0/60/120/180/240/299 s · 재조임 = 구간 3 칸 k + 뒤 3칸 ≥ ref_d100 × 1.10 → 10k s (첫 칸부터면 "즉시(0 s)",
       300 s 안에 없으면 "재조임 없음") · 분류 ≤ 20 s "300 s 유휴로도 재조임을 못 늦춘다" · 30~50 s "중간" ·
       ≥ 60 s "300 s 유휴가 재조임을 늦춘다 (유예 레버)" · 보조: 재조임 칸 SKIN·AP · 구간 3 첫 칸 배율 · 240~300 s vs 구간 1 540~600 s
  NI300 §5: ref_d100 · 1계단 · 1-1 진입 · 240~300 s 배율 · 끝 SKIN·AP·BAT · 전제 240~300 ≥ 1.06 ("가열 부족 — 재조임 판정 불가") ·
       재조임 = 구간 3 칸 k + 뒤 3칸 ≥ ref_d100 × 1.06 → 10k s, 마지막 k = 14, 없으면 "180 s 안 재조임 없음" ·
       분류 ≤ 20 · 30~50 · ≥ 60 s 또는 없음 (§4 문구, NPU) · 보조: 휴지 온도 vs M1-NPU (a)(b) 탐침 · 재조임 칸 SKIN·AP vs 1계단 진입 5런
  휴지 duty (d_min): 체인기록 §0 = 1 → "유휴 = duty 1 (100 ms/10 s)" · 10 이면 "완전 유휴 아님 — 조민규 인계의 유휴 질문에 답 못 함"
  cmp §8 + `v2_예측_밤1004.md` "이 차이면 틀린 것" 열 · 헤더 기준 (= 스로틀모형_사전등록_v2 §5: 시각 ±10 s · 배율 NPU ±0.03 / GPU ±10 % ·
       SKIN ±0.5 ℃ · AP 보고): NPU 계단 시각 (1계단 · 1-1 진입) ±20 s (표의 행 기준) · GPU 1-1 진입 ±10 s · 해제·재조임 시각 ±10 s
       (둘 다 없음 = 맞음 · 한쪽만 없음 = 틀림) · 분류 = 같은 분류 (R50-fast/slow/none · 못 늦춘다/중간/유예 레버/재조임 없음; 실측 미분류는 미확인) ·
       배율 NPU ±0.03 · GPU 상대 ±10 % · SKIN ±0.5 ℃ · 온도 궤적 SKIN MAE ≤ 0.5 ℃ (AP MAE 보고) · AP·status·BAT 보고 ·
       v2 채택형 (V2-Lb, 변형 θ_0.3·θ_0.75) 전용 행: GI300 재조임 칸 SKIN = T_on 37.2 ± 0.5 · NI300 재조임 칸 SKIN ∈ [38.1, 38.6] ·
       G50P "계단형 하강" 은 수치 정의가 없어 칸 0~5 궤적을 기술로만 붙인다 · v1 (fast/skin) · reference_forms 는 같은 일반 기준 (행 기준 중
       모형 고유 파라미터 행은 예측값 ± 일반 허용오차로) · 측정 쪽 전제 실패 (가열 부족) 면 탐침·재조임 행은 "판정 불가 (가열 부족)" ·
       비교 열 = 실제 시작 SKIN (구간 0 시작 HAL) 에 가까운 쪽 (29.5 / 30.5, 같으면 29.5) · 시작 SKIN ∉ [28.3, 31.6] (night1003_judge.DEV_RANGE)
       → "적용 범위 밖 (unsupported)" — 범위를 넓히지 않는다 · 변형마다 따로 · reference_forms 는 "참고 — 선택에 쓰지 않음" ·
       예측 JSON 없음 → "예측 없음" 기록
"""
import argparse, hashlib, importlib.util, json, os, shutil, sys, tempfile

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
_F_PATH = os.path.join(REPO, "d1sim", "tools", "fit_throttle_v1.py")
F = _load_module("fit_throttle_v1", _F_PATH)
load_run, segments_of, bins10, window_median, thermal_at, soc_at, load_watch, onset_1_1, dumps, JudgeError, _synth_run = (
    J.load_run, J.segments_of, J.bins10, J.window_median, J.thermal_at, J.soc_at, J.load_watch, J.onset_1_1, J.dumps, J.JudgeError, J._synth_run)
step1_time = F.step1_time            # (bins=[(t, ratio)], level) → +4.5 % 를 그 칸 + 뒤 3칸 유지하는 첫 칸 (t ≥ 30)
_ratio_bins, _thermal_bin, _shape, _write_thermal, _v, _row = N3._ratio_bins, N3._thermal_bin, N3._shape, N3._write_thermal, N3._v, N3._row
DEV_RANGE = N3.DEV_RANGE             # (28.3, 31.6) 모형 개발 자료 시작 SKIN 범위 — 밖이면 unsupported

IMPORTS = {"m1m2_judge_1002": (_J_PATH, "ea282d4a"), "night1003_judge": (_N3_PATH, "a5ceab41"), "fit_throttle_v1": (_F_PATH, "379039dd")}

BIN_S = 10
HOLD = 3                              # 칸 k + 뒤 3칸
A3_TOL = 0.05
STEP1_LEVEL = 1.045
# ---- N50P §2 ----
N50_LABELS = ["cold_ref_d50", "heat_d100", "probe_d50"]
N50_DELTA = 0.03
N50_LAST_K = 44
N50_PREMISE = 1.06
N50_HEAT_WIN = (360, 420)
N50_RETIGHTEN = 1.06
PROBE_T = (0, 60, 120, 240, 479)
D10_RELEASE_NPU = dict(SKIN=41.4, AP=43.9)                    # [P 10/3 M1-NPU 2런] 사전 등록 §2 보조
# ---- G50P §3 ----
G50_DELTA = 0.10
G50_LAST_K = 44
G50_PREMISE = 1.5
G50_HEAT_WIN = (240, 300)
H_AP_HYS_REJECT = 40.0
D10_RELEASE_GPU = dict(SKIN=[37.1, 38.2], AP=[38.0, 39.1])     # [P 3런] 사전 등록 §3
M3_REF = "0928 M3 (Interpreter GPU d50 식은 출발) 진입 350 s @ SKIN 38.1 [D 가설원장 T2-M3] — 엔진 다름, 참고"
# ---- 분류 경계 (§2 = §3) ----
CLS_FAST_MAX, CLS_UNCLASSIFIED = 40, 50
# ---- GI300 §4 / NI300 §5 ----
IDLE_LABELS = ["cold_ref_d10", "heat_d100", "rest_*", "reheat_d100"]
GI_RISE = 1.10
GI_HEAT_WIN = (540, 600)
NI_RISE = 1.06
NI_LAST_K = 14
NI_PREMISE = 1.06
NI_HEAT_WIN = (240, 300)
REST_T = (0, 60, 120, 180, 240, 299)
IDLE_FAST_MAX, IDLE_SLOW_MIN = 20, 60
STEP1_5RUNS = dict(SKIN=[37.6, 38.3], AP=[41.7, 42.6])         # [P/D] 사전 등록 §5 보조
# ---- cmp ----
TOL = dict(npu_step_s=20.0, gpu_onset_s=10.0, event_s=10.0, npu_ratio_abs=0.03, gpu_ratio_rel=0.10, skin_abs=0.5, skin_mae=0.5)
V2_GI_TON = (37.2, 0.5)               # v2 채택형: GI300 재조임 칸 SKIN = T_on 37.2 ± 0.5
V2_NI_T1 = (38.1, 38.6)               # v2 채택형: NI300 재조임 칸 SKIN ∈ [38.1, 38.6]
# ---- 나란히 (기술만) — 10/3 판정 출력 ----
OUT_1003 = os.path.join(OD_SIM, "out_1003")
CMP_SRC = dict(m1npu_a=os.path.join(OUT_1003, "M1_npu_a.json"), m1npu_b=os.path.join(OUT_1003, "M1_npu_b.json"),
               m1gpu_r2=os.path.join(OUT_1003, "M1_gpu_r2.json"), gpace=os.path.join(OUT_1003, "GPUpace.json"))


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


def _load_json_opt(p):
    if not p or not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


# ============================================================ 공통
def _expect(S, labels, accel, duties, allow_empty=()):
    segs = S["segments"]
    got = [s["label"] for s in segs]
    if len(segs) != len(labels):
        raise JudgeError(f"구간이 {len(segs)}개 — 기대 {len(labels)} ({labels}), 실제 라벨 {got}")
    for i, (g, e) in enumerate(zip(got, labels)):
        if e.endswith("*"):
            if not (g or "").startswith(e[:-1]):
                raise JudgeError(f"구간 {i} 라벨 {g} ≠ {e}")
        elif g != e:
            raise JudgeError(f"구간 라벨 불일치: {got} ≠ {labels}")
    for i, s in enumerate(segs):
        if s["accelerator"] != accel:
            raise JudgeError(f"구간 {i} 가속기 {s['accelerator']} ≠ {accel}")
        if duties[i] is not None and s["duty"] != duties[i]:
            raise JudgeError(f"구간 {i} duty {s['duty']} ≠ {duties[i]}")
        if s["n"] == 0 and i not in allow_empty:
            raise JudgeError(f"구간 {i} ({s['label']}) 에 추론 없음")
    return segs


def _th(run, seg, t_s):
    th = _thermal_bin(run, seg, t_s)
    if th is None:
        return None
    return dict(SKIN=th["SKIN"], AP=th["AP"], BAT=th["BAT"], status=th["thermal_status"], dt_s=th["dt_s"])


def _th_ns(run, ns):
    th = thermal_at(run, ns)
    if th is None:
        return None
    return dict(SKIN=th["SKIN"], AP=th["AP"], BAT=th["BAT"], status=th["thermal_status"], dt_s=th["dt_s"])


def _first_hold(pr, pred, last_k, start=0):
    """칸 k 와 뒤 3칸이 모두 pred 를 만족하는 첫 k (start ≤ k ≤ last). last = min(last_k, len−1−3)."""
    last = min(last_k, len(pr) - 1 - HOLD)
    for k in range(start, last + 1):
        win = pr[k:k + 1 + HOLD]
        if len(win) == 1 + HOLD and all(r is not None and pred(r) for r in win):
            return k, last
    return None, last


def _heat(run, heat, win, with_step1=True):
    on = onset_1_1(heat)
    ref = on["ref_ms"]
    br = on.get("bins_ratio") or []
    s1 = step1_time(br, level=STEP1_LEVEL) if (with_step1 and ref) else None
    rw, nw = window_median(heat, win[0], win[1])
    return dict(ref30_ms=ref, onset_1_1_s=on["onset_s"], edge_candidate_s=on["edge_candidate_s"], step1_s=s1,
                window=f"{win[0]}~{win[1]}", ratio_window=(rw / ref) if (rw is not None and ref) else None, n_window=nw,
                n=heat["n"], length_s=heat["length_s"], termination_reason=heat["termination_reason"], bins_ratio=br,
                start_thermal=_th(run, heat, 0), end_thermal=_th_ns(run, heat["end_ns"]),
                onset_thermal=None if on["onset_s"] is None else _th(run, heat, on["onset_s"]),
                step1_thermal=None if s1 is None else _th(run, heat, s1))


def _bins_table(run, seg, pr):
    out = []
    for k, b in enumerate(bins10(seg)):
        th = _th(run, seg, b["t0"])
        out.append(dict(k=k, t0=b["t0"], ratio=pr[k], median_ms=b["median_ms"], n=b["n"],
                        SKIN=None if th is None else th["SKIN"], AP=None if th is None else th["AP"],
                        BAT=None if th is None else th["BAT"], status=None if th is None else th["status"]))
    return out


def _temps(run, seg, ts):
    out = []
    for t in ts:
        th = _th(run, seg, t) if t <= seg["length_s"] + 1 else None
        out.append(dict(t=t, SKIN=None if th is None else th["SKIN"], AP=None if th is None else th["AP"],
                        BAT=None if th is None else th["BAT"], status=None if th is None else th["status"]))
    return out


def _meta(S, run, watch):
    m = S["meta"]
    st = _th_ns(run, S["segments"][0]["start_ns"])
    sk = None if st is None else st["SKIN"]
    return dict(run_id=m.get("run_id"), chain_id=(m.get("chain_spec") or {}).get("chain_id"), chain_sha256=m.get("chain_sha256"),
                termination_reason=m.get("termination_reason"), completed_inference_count=m.get("completed_inference_count"),
                pilot_battery_pct=m.get("pilot_battery_pct"), start_skin=sk, start_thermal=st,
                start_skin_in_band_29_1_31_6=(None if sk is None else bool(29.1 <= sk <= 31.6)),
                start_skin_in_dev_range=(None if sk is None else bool(DEV_RANGE[0] <= sk <= DEV_RANGE[1])),
                segments=[dict(index=s["index"], label=s["label"], accelerator=s["accelerator"], duty=s["duty"], duration_s=s["duration_s"],
                               length_s=s["length_s"], n=s["n"], achieved_duty=s["achieved_duty"], termination_reason=s["termination_reason"],
                               start_thermal=_th_ns(run, s["start_ns"]), end_thermal=_th_ns(run, s["end_ns"]),
                               start_soc=soc_at(watch, s["start_wall_ms"])) for s in S["segments"]],
                transitions=S["transitions"], imports=import_check())


def _r50_class(rs):
    if rs is None:
        return "R50-none", "R50-none (440 s 안 미회복 — 중도절단)"
    if rs <= CLS_FAST_MAX:
        return "R50-fast", f"R50-fast (해제 {rs} s ≤ 40 s)"
    if rs == CLS_UNCLASSIFIED:
        return "미분류", "미분류 (해제 50 s)"
    return "R50-slow", f"R50-slow (해제 {rs} s, 60~440 s)"


def _release(run, probe, pr, delta, last_k):
    k, last = _first_hold(pr, lambda r: r <= 1.0 + delta, last_k)
    shape, step = _shape(pr, k)
    th = None if k is None else _th(run, probe, k * BIN_S)
    return dict(recovered=k is not None, release_s=None if k is None else k * BIN_S, k=k, last_testable_k=last,
                censored=None if k is not None else f"{last * BIN_S} s 안 미회복 (중도절단)",
                threshold_ratio=1.0 + delta, shape=shape, step=step, release_thermal=th,
                SKIN_k=None if th is None else th["SKIN"], AP_k=None if th is None else th["AP"])


def _p15(pr):
    v = [x for x in pr[1:6] if x is not None]
    return float(np.median(v)) if v else None


def _rest_note(duty):
    if duty == 10:
        return "완전 유휴 아님 — 조민규 인계의 유휴 질문에 답 못 함 (휴지 duty 10)"
    if duty is None:
        return "휴지 duty 미확인"
    return f"유휴 = duty {duty} ({duty * 100} ms/10 s) — 완전 유휴 아님 ({duty} % 가동); 휴지 칸 배율은 기술만"


def _cmp_side(name, f):
    """10/3 판정 JSON 에서 나란히 볼 값만 (기술). 없으면 None."""
    return _load_json_opt(CMP_SRC.get(name)) if f is None else f


def _probe_side(j, ts):
    """10/3 탐침 칸 (bins: t0·SKIN·AP) 에서 t 에 해당하는 칸 (t0 = floor(t/10)·10) 값 — 기술."""
    if j is None:
        return None
    bins = (j.get("probe") or {}).get("bins") or []
    by = {b.get("t0"): b for b in bins}
    out = []
    for t in ts:
        t0 = int(t // BIN_S) * BIN_S
        b = by.get(t0)
        out.append(dict(t=t, bin_t0=t0, SKIN=None if b is None else b.get("SKIN"), AP=None if b is None else b.get("AP"),
                        BAT=None if b is None else b.get("BAT")))
    return out


# ============================================================ N50P (§2)
def n50p_judge(run, watch=None, side=None):
    S = segments_of(run)
    ref0, heat, probe = _expect(S, N50_LABELS, "NPU", [50, 100, 50])
    ref_d50 = float(np.median(ref0["lat_ms"]))
    ref_ratio = _ratio_bins(ref0, ref_d50)
    a3 = all(r is not None and abs(r - 1.0) <= A3_TOL for r in ref_ratio)
    h = _heat(run, heat, N50_HEAT_WIN, with_step1=True)
    premise = h["ratio_window"] is not None and h["ratio_window"] >= N50_PREMISE
    pr = _ratio_bins(probe, ref_d50)
    rel = _release(run, probe, pr, N50_DELTA, N50_LAST_K)
    tok, cls = _r50_class(rel["release_s"])
    # 해제 뒤 재조임 (k′ + 뒤 3칸 ≥ ref_d50 × 1.06) — 기술
    kk = None
    if rel["k"] is not None:
        kk, _ = _first_hold(pr, lambda r: r >= N50_RETIGHTEN, len(pr), start=rel["k"] + 1)
    hyp_names = ("H-timer", "H-load (θ ≤ 50 %)", "H-load (θ > 50 %)")
    if not premise:
        hyp = {n: "판정 불가 (가열 부족 — 탐침 판정 불가, 기술만)" for n in hyp_names}
        concl = "가열 부족 — 탐침 판정 불가 (기술만)"
    elif tok == "R50-fast":
        hyp = {"H-timer": "유지 (R50-fast)", "H-load (θ ≤ 50 %)": "기각 (R50-fast)", "H-load (θ > 50 %)": "유지 (R50-fast)"}
        concl = "H-timer 와 H-load(θ > 50 %) 는 못 가른다 — 다음은 d75"
    elif tok in ("R50-slow", "R50-none"):
        hyp = {"H-timer": f"기각 ({tok})", "H-load (θ ≤ 50 %)": f"유지 ({tok})", "H-load (θ > 50 %)": f"기각 ({tok})"}
        concl = "H-timer 기각 · H-load(θ ≤ 50 %) 쪽"
    else:
        hyp = {n: "판정 불가 (미분류 — 해제 50 s)" for n in hyp_names}
        concl = "미분류 (해제 50 s) — 가설 판정 불가"
    side = side or {}
    a, b = _cmp_side("m1npu_a", side.get("m1npu_a")), _cmp_side("m1npu_b", side.get("m1npu_b"))
    def _m1(jj):
        if jj is None:
            return None
        hh = jj.get("heat") or {}
        return dict(run_id=jj.get("run_id"), start_skin=jj.get("start_skin"), step1_s=hh.get("step1_s"), onset_1_1_s=hh.get("onset_1_1_s"),
                    step1_thermal=hh.get("step1_thermal"), onset_thermal=hh.get("onset_thermal"), ratio_540_600=hh.get("ratio_540_600"),
                    release_s=(jj.get("recovery") or {}).get("recovery_s"), SKIN_k=jj.get("SKIN_k"), AP_k=jj.get("AP_k"),
                    probe_skin_at=(jj.get("probe") or {}).get("probe_skin_at"))
    out = dict(
        rule="밤1004_사전등록_v1 §2 (N50P): 해제 = 탐침 칸 k + 뒤 3칸 ≤ ref_d50×1.03 → 10k s · 마지막 k=44 · 분류 ≤40 fast / 60~440 slow / 중도절단 none / 50 미분류 · 전제 360~420 ≥ 1.06",
        **_meta(S, run, watch),
        ref_d50_ms=ref_d50, ref_n=ref0["n"], ref_bins_ratio=ref_ratio, a3_reference_stable=a3,
        a3_label=("기준 안정" if a3 else "기준 불안정 (±5 % 밖 칸 있음) — 표시하고 판정은 한다"),
        heat=dict(h, premise_ok=premise, premise_label=("가열 충분 (360~420 s 배율 ≥ 1.06)" if premise else "가열 부족 — 탐침 판정 불가 (기술만)")),
        probe=dict(accelerator=probe["accelerator"], duty=probe["duty"], length_s=probe["length_s"], n=probe["n"],
                   termination_reason=probe["termination_reason"], bins_ratio=pr, bins=_bins_table(run, probe, pr),
                   release=rel, release_s=rel["release_s"], class_token=tok, classification=cls, shape=rel["shape"],
                   SKIN_k=rel["SKIN_k"], AP_k=rel["AP_k"], d10_release_ref=D10_RELEASE_NPU,
                   bins_1_5_median=_p15(pr), retighten_after_release_k=kk,
                   retighten_after_release_s=None if kk is None else kk * BIN_S,
                   retighten_label=(None if rel["k"] is None else ("해제 뒤 재조임 없음" if kk is None else f"해제 뒤 재조임 (k′={kk}, {kk * BIN_S} s)")),
                   temps=_temps(run, probe, PROBE_T), start_soc=soc_at(watch, probe["start_wall_ms"])),
        hypotheses=hyp, conclusion=concl,
        compare_m1npu=dict(note="M1-NPU (a)(b) 10/3 (d100 600 s 가열 · d10 탐침) — 나란히, 기술만", a=_m1(a), b=_m1(b)),
        counter_interpretations=["① d50 은 뜨거운 상태에서 더 데운다 — 늦게 풀림이 부하 문턱이 아니라 온도가 계속 높아서일 수 있다 (탐침 SKIN·AP 궤적)",
                                 "② 가열 420 s 라 600 s (M1) 보다 얕다 — 해제는 이 런의 가열 끝 상태 기준으로만",
                                 "③ d50 가동 주기 첫 추론들은 느리다 — 같은 d50 인 ref_d50 과만 비교",
                                 "④ 1런", "⑤ 전환 잔재 — 첫 칸만으로 판정하지 않는다 (k + 뒤 3칸)"],
    )
    return out


# ============================================================ G50P (§3)
def g50p_judge(run, watch=None):
    S = segments_of(run)
    ref0, heat, probe = _expect(S, N50_LABELS, "GPU", [50, 100, 50])
    ref_d50 = float(np.median(ref0["lat_ms"]))
    ref_ratio = _ratio_bins(ref0, ref_d50)
    a3 = all(r is not None and abs(r - 1.0) <= A3_TOL for r in ref_ratio)
    h = _heat(run, heat, G50_HEAT_WIN, with_step1=False)
    premise = h["ratio_window"] is not None and h["ratio_window"] >= G50_PREMISE
    pr = _ratio_bins(probe, ref_d50)
    rel = _release(run, probe, pr, G50_DELTA, G50_LAST_K)
    tok, cls = _r50_class(rel["release_s"])
    names = ("H-timer", "H-ap-히스", "H-load(GPU)")
    bins = _bins_table(run, probe, pr)
    ap_vals = [b["AP"] for b in bins if b["AP"] is not None]
    if not premise:
        hyp = {n: "판정 불가 (가열 부족 — 탐침 판정 불가, 기술만)" for n in names}
    else:
        hyp = {}
        hyp["H-timer"] = ("유지 (R50-fast)" if tok == "R50-fast" else (f"기각 ({tok})" if tok in ("R50-slow", "R50-none") else "판정 불가 (미분류)"))
        if rel["release_s"] is None:
            hyp["H-ap-히스"] = "판정 불가 (해제 없음 — 규칙은 해제 칸 AP_k 로만)"
        elif rel["AP_k"] is None:
            hyp["H-ap-히스"] = "판정 불가 (AP_k 없음)"
        elif rel["AP_k"] >= H_AP_HYS_REJECT:
            hyp["H-ap-히스"] = f"기각 (해제 칸 AP_k {rel['AP_k']} ≥ 40.0)"
        else:
            hyp["H-ap-히스"] = f"유지 (해제 칸 AP_k {rel['AP_k']} < 40.0)"
        hyp["H-load(GPU)"] = (f"유지 ({tok})" if tok in ("R50-slow", "R50-none") else ("기각 (R50-fast)" if tok == "R50-fast" else "판정 불가 (미분류)"))
    return dict(
        rule="밤1004_사전등록_v1 §3 (G50P): 해제 = 탐침 칸 k + 뒤 3칸 ≤ ref_d50×1.10 → 10k s · 마지막 k=44 · 분류 §2 경계 · 전제 240~300 ≥ 1.5 · H-ap-히스 AP_k ≥ 40.0 기각",
        **_meta(S, run, watch),
        ref_d50_ms=ref_d50, ref_n=ref0["n"], ref_bins_ratio=ref_ratio, a3_reference_stable=a3,
        a3_label=("기준 안정" if a3 else "기준 불안정 (±5 % 밖 칸 있음) — 표시하고 판정은 한다"),
        heat=dict(h, premise_ok=premise, premise_label=("가열 충분 (240~300 s 배율 ≥ 1.5)" if premise else "가열 부족 — 탐침 판정 불가 (기술만)")),
        probe=dict(accelerator=probe["accelerator"], duty=probe["duty"], length_s=probe["length_s"], n=probe["n"],
                   termination_reason=probe["termination_reason"], bins_ratio=pr, bins=bins, release=rel, release_s=rel["release_s"],
                   class_token=tok, classification=cls, shape=rel["shape"], SKIN_k=rel["SKIN_k"], AP_k=rel["AP_k"],
                   d10_release_ref=D10_RELEASE_GPU, bins_1_5_median=_p15(pr), bins_0_5=pr[:6],
                   ap_min_probe=(min(ap_vals) if ap_vals else None), temps=_temps(run, probe, PROBE_T),
                   start_soc=soc_at(watch, probe["start_wall_ms"])),
        hypotheses=hyp, m3_reference=M3_REF,
        counter_interpretations=["§2 ① d50 은 뜨거운 상태에서 더 데운다 (탐침 SKIN·AP 궤적)", "§2 ③ d50 가동 주기 첫 추론 — ref_d50 과만 비교",
                                 "§2 ④ 1런", "§2 ⑤ 전환 잔재 — k + 뒤 3칸 (GPU 는 전환 잔재가 없다 [P 페이싱 k0 ×1.02] 지만 규칙 유지)"],
    )


# ============================================================ GI300 (§4) · NI300 (§5)
def _idle_common(run, watch, accel):
    S = segments_of(run)
    ref0, heat, rest, reheat = _expect(S, IDLE_LABELS, accel, [10, 100, None, 100], allow_empty={2})
    ref_d10 = float(np.median(ref0["lat_ms"]))
    ref0_ratio = _ratio_bins(ref0, ref_d10)
    a3 = all(r is not None and abs(r - 1.0) <= A3_TOL for r in ref0_ratio)
    ref_d100, n100 = window_median(heat, 0, 30)
    if ref_d100 is None:
        raise JudgeError("구간 1 처음 30 s 에 추론 없음")
    rest_pr = _ratio_bins(rest, ref_d10) if rest["n"] else [None] * len(bins10(rest))
    pr3 = _ratio_bins(reheat, ref_d100)
    return S, ref0, heat, rest, reheat, ref_d10, ref0_ratio, a3, ref_d100, n100, rest_pr, pr3


def _idle_class(t, none_label, none_class):
    if t is None:
        return "재조임 없음", none_class, none_label
    lab = "즉시(0 s)" if t == 0 else f"{t} s"
    if t <= IDLE_FAST_MAX:
        return "못 늦춘다", f"300 s 유휴로도 재조임을 못 늦춘다 (재조임 {t} s ≤ 20 s)", lab
    if t >= IDLE_SLOW_MIN:
        return "유예 레버", f"300 s 유휴가 재조임을 늦춘다 (유예 레버) (재조임 {t} s ≥ 60 s)", lab
    return "중간", f"중간 (재조임 {t} s, 30~50 s)", lab


def gi300_judge(run, watch=None, side=None):
    S, ref0, heat, rest, reheat, ref_d10, ref0_ratio, a3, ref_d100, n100, rest_pr, pr3 = _idle_common(run, watch, "GPU")
    h = _heat(run, heat, GI_HEAT_WIN, with_step1=False)
    k, last = _first_hold(pr3, lambda r: r >= GI_RISE, len(pr3))
    t_re = None if k is None else k * BIN_S
    tok, cls, lab = _idle_class(t_re, f"재조임 없음 ({reheat['length_s']:.0f} s 안, 검정 가능 k ≤ {last})",
                                "재조임 없음 (300 s 안) — §4 분류 문구는 ≤ 20 · 30~50 · ≥ 60 만 (없음은 따로 적는다)")
    re_th = None if k is None else _th(run, reheat, k * BIN_S)
    r240, _ = window_median(reheat, 240, 300)
    ratio240 = (r240 / ref_d100) if r240 is not None else None
    side = side or {}
    r2, gp = _cmp_side("m1gpu_r2", side.get("m1gpu_r2")), _cmp_side("gpace", side.get("gpace"))
    return dict(
        rule="밤1004_사전등록_v1 §4 (GI300): 재조임 = 구간 3 칸 k + 뒤 3칸 ≥ ref_d100×1.10 → 10k s (k=0 즉시) · 분류 ≤20 / 30~50 / ≥60 · 휴지 지연 판정 없음",
        **_meta(S, run, watch),
        ref_d10_ms=ref_d10, ref0_bins_ratio=ref0_ratio, a3_reference_stable=a3, a3_label=("기준 안정" if a3 else "기준 불안정 (±5 % 밖 칸 있음)"),
        ref_d100_ms=ref_d100, ref_d100_n=n100, heat=h,
        rest=dict(label=rest["label"], duty=rest["duty"], rest_note=_rest_note(rest["duty"]), n=rest["n"], length_s=rest["length_s"],
                  temps=_temps(run, rest, REST_T), bins_ratio_vs_ref_d10_descriptive=rest_pr,
                  bins=_bins_table(run, rest, rest_pr), start_soc=soc_at(watch, rest["start_wall_ms"])),
        reheat=dict(n=reheat["n"], length_s=reheat["length_s"], bins_ratio=pr3, bins=_bins_table(run, reheat, pr3),
                    retighten=dict(retightened=k is not None, retighten_s=t_re, k=k, last_testable_k=last, label=lab),
                    retighten_s=t_re, class_token=tok, classification=cls, retighten_thermal=re_th,
                    SKIN_k=None if re_th is None else re_th["SKIN"], AP_k=None if re_th is None else re_th["AP"],
                    first_bin_ratio=pr3[0] if pr3 else None, ratio_240_300=ratio240,
                    ratio_240_300_vs_heat_540_600=(None if (ratio240 is None or h["ratio_window"] is None) else ratio240 / h["ratio_window"]),
                    start_thermal=_th_ns(run, reheat["start_ns"]), end_thermal=_th_ns(run, reheat["end_ns"]),
                    start_soc=soc_at(watch, reheat["start_wall_ms"])),
        compare=dict(note="나란히 (기술만) — 휴지 길이·종류 두 가지가 다르다",
                     m1gpu_r2_probe_d10=_probe_side(r2, REST_T),
                     gpace_1003=(None if gp is None else dict(rest="d10 60 s", retighten=(gp.get("reheat") or {}).get("retighten"),
                                                                classification=(gp.get("reheat") or {}).get("classification")))),
        counter_interpretations=["재가열 시작 온도가 식은 출발보다 높아 일찍 조이는 것은 측정하려는 기제 자체 — 재조임 칸 온도와 시간 설명을 같이",
                                 "휴지 duty 1 은 완전 유휴가 아니다 (100 ms/10 s)", "전환 창 잔재 — 첫 칸만으로 판정하지 않는다 (칸 k + 뒤 3칸)", "1런"],
    )


def ni300_judge(run, watch=None, side=None):
    S, ref0, heat, rest, reheat, ref_d10, ref0_ratio, a3, ref_d100, n100, rest_pr, pr3 = _idle_common(run, watch, "NPU")
    h = _heat(run, heat, NI_HEAT_WIN, with_step1=True)
    premise = h["ratio_window"] is not None and h["ratio_window"] >= NI_PREMISE
    k, last = _first_hold(pr3, lambda r: r >= NI_RISE, NI_LAST_K)
    t_re = None if k is None else k * BIN_S
    tok, cls, lab = _idle_class(t_re, f"{(last + HOLD + 1) * BIN_S} s 안 재조임 없음",
                                "300 s 유휴가 재조임을 늦춘다 (유예 레버) (≥ 60 s 또는 없음 — 180 s 안 재조임 없음)")
    if not premise:
        cls = "판정 불가 (가열 부족 — 재조임 판정 불가) · 기술: " + cls
    re_th = None if k is None else _th(run, reheat, k * BIN_S)
    side = side or {}
    a, b = _cmp_side("m1npu_a", side.get("m1npu_a")), _cmp_side("m1npu_b", side.get("m1npu_b"))
    def _in(v, lohi):
        return None if v is None else bool(lohi[0] <= v <= lohi[1])
    return dict(
        rule="밤1004_사전등록_v1 §5 (NI300): 재조임 = 구간 3 칸 k + 뒤 3칸 ≥ ref_d100×1.06 → 10k s · 마지막 k=14 · 분류 ≤20 / 30~50 / ≥60 또는 없음 · 전제 240~300 ≥ 1.06",
        **_meta(S, run, watch),
        ref_d10_ms=ref_d10, ref0_bins_ratio=ref0_ratio, a3_reference_stable=a3, a3_label=("기준 안정" if a3 else "기준 불안정 (±5 % 밖 칸 있음)"),
        ref_d100_ms=ref_d100, ref_d100_n=n100,
        heat=dict(h, premise_ok=premise, premise_label=("가열 충분 (240~300 s 배율 ≥ 1.06)" if premise else "가열 부족 — 재조임 판정 불가")),
        rest=dict(label=rest["label"], duty=rest["duty"], rest_note=_rest_note(rest["duty"]), n=rest["n"], length_s=rest["length_s"],
                  temps=_temps(run, rest, REST_T), bins_ratio_vs_ref_d10_descriptive=rest_pr,
                  bins=_bins_table(run, rest, rest_pr), start_soc=soc_at(watch, rest["start_wall_ms"])),
        reheat=dict(n=reheat["n"], length_s=reheat["length_s"], bins_ratio=pr3, bins=_bins_table(run, reheat, pr3),
                    retighten=dict(retightened=k is not None, retighten_s=t_re, k=k, last_testable_k=last, label=lab),
                    retighten_s=t_re, class_token=tok, classification=cls, premise_ok=premise, retighten_thermal=re_th,
                    SKIN_k=None if re_th is None else re_th["SKIN"], AP_k=None if re_th is None else re_th["AP"],
                    retighten_vs_step1_5runs=dict(range=STEP1_5RUNS, SKIN_in=_in(None if re_th is None else re_th["SKIN"], STEP1_5RUNS["SKIN"]),
                                                  AP_in=_in(None if re_th is None else re_th["AP"], STEP1_5RUNS["AP"])),
                    first_bin_ratio=pr3[0] if pr3 else None,
                    start_thermal=_th_ns(run, reheat["start_ns"]), end_thermal=_th_ns(run, reheat["end_ns"]),
                    start_soc=soc_at(watch, reheat["start_wall_ms"])),
        compare=dict(note="휴지 온도 vs M1-NPU (a)(b) 10/3 d10 탐침 같은 시점 (299 s ↔ 290 s 칸) — 기술만",
                     m1npu_a_probe_d10=_probe_side(a, REST_T), m1npu_b_probe_d10=_probe_side(b, REST_T)),
        counter_interpretations=["가열 300 s 는 2계단 전일 수 있다 (1계단만)", "재가열 180 s 는 짧다 (중도절단 가능)", "휴지 duty 1 은 완전 유휴가 아니다", "1런"],
    )


# ============================================================ cmp — 동결 예측 vs 실측
def _pick_base(start_skin):
    if start_skin is None:
        return None
    c = sorted([(abs(29.5 - start_skin), "29.5"), (abs(30.5 - start_skin), "30.5")])
    return c[0][1]


def _support(sk):
    if sk is None:
        return False, "시작 SKIN 미확인 → unsupported"
    ok = DEV_RANGE[0] <= sk <= DEV_RANGE[1]
    return ok, ("적용 범위 안" if ok else f"적용 범위 밖 (unsupported): 시작 SKIN {sk} ∉ [{DEV_RANGE[0]}, {DEV_RANGE[1]}] — 범위를 넓히지 않는다")


def _tok_probe(s):
    if s is None:
        return None
    for t in ("R50-fast", "R50-slow", "R50-none", "미분류"):
        if str(s).startswith(t):
            return t
    return str(s)


def _tok_idle(s):
    if s is None:
        return None
    s = str(s)
    if "못 늦춘다" in s:
        return "못 늦춘다"
    if s.startswith("중간"):
        return "중간"
    if "유예" in s:
        return "유예 레버"
    if "없음" in s:
        return "재조임 없음"
    return s


def _r_time(cell, p, m, tol, wrong):
    if p is None and m is None:
        ok = True
    elif p is None or m is None:
        ok = False
    else:
        ok = abs(m - p) <= tol
    return _row(cell, p, m, f"|Δ| ≤ {tol:g} s · 둘 다 없음 = 맞음 · 한쪽만 없음 = 틀림", _v(ok), wrong)


def _r_abs(cell, p, m, tol, wrong):
    ok = None if (p is None or m is None) else abs(m - p) <= tol
    return _row(cell, p, m, f"|Δ| ≤ {tol:g}", _v(ok), wrong)


def _r_rel(cell, p, m, tol, wrong):
    ok = None if (p is None or m is None or p == 0) else abs(m / p - 1.0) <= tol
    return _row(cell, p, m, f"상대차 ≤ {tol * 100:g} %", _v(ok), wrong)


def _r_skin(cell, p, m, wrong):
    ok = None if (p is None or m is None) else abs(m - p) <= TOL["skin_abs"]
    return _row(cell, p, m, "|Δ| ≤ 0.5 ℃", _v(ok), wrong)


def _r_class(cell, pt, mt, wrong):
    ok = None if (pt is None or mt is None or mt == "미분류") else (pt == mt)
    return _row(cell, pt, mt, "같은 분류 (실측 미분류 → 미확인)", _v(ok), wrong)


def _r_mae(cell, ptemps, mtemps, wrong):
    pm = {d.get("t"): d for d in (ptemps or [])}
    errs, aerrs, pv, mv = [], [], [], []
    for d in (mtemps or []):
        p = pm.get(d["t"])
        pv.append(None if p is None else [p.get("skin"), p.get("ap")])
        mv.append([d.get("SKIN"), d.get("AP")])
        if p is not None and d.get("SKIN") is not None and p.get("skin") is not None:
            errs.append(abs(d["SKIN"] - p["skin"]))
        if p is not None and d.get("AP") is not None and p.get("ap") is not None:
            aerrs.append(abs(d["AP"] - p["ap"]))
    mae = float(np.mean(errs)) if errs else None
    amae = float(np.mean(aerrs)) if aerrs else None
    ok = None if mae is None else mae <= TOL["skin_mae"]
    r = _row(cell, pv, mv, "SKIN MAE ≤ 0.5 ℃ (AP MAE 보고)", _v(ok) + ("" if mae is None else f" (SKIN MAE {mae:.2f} · AP MAE {amae:.2f})" if amae is not None else f" (SKIN MAE {mae:.2f})"), wrong)
    r["skin_mae"], r["ap_mae"] = mae, amae
    return r


def _r_info(cell, p, m):
    return _row(cell, p, m, "기술만", "—", "—")


def _na(rows, reason):
    for r in rows:
        if r["verdict"] not in ("—",):
            r["verdict"] = f"판정 불가 ({reason})"
    return rows


def _cmp_n50p(c, j, v2_adopted):
    h, p = j["heat"], j["probe"]
    et, ot, st = h.get("end_thermal") or {}, h.get("onset_thermal") or {}, h.get("step1_thermal") or {}
    rows = [_r_info("A3 (구간 0 칸 ±5 %)", c.get("A3_stable"), j.get("a3_reference_stable")),
            _r_time("1계단 (+4.5 % 유지 첫 칸)", c.get("heat_step1_s"), h.get("step1_s"), TOL["npu_step_s"], "열 블록"),
            _r_time("1-1 진입 (+10 %)", c.get("heat_onset_1_1_s"), h.get("onset_1_1_s"), TOL["npu_step_s"], "열 블록 · 진입 온도대가 틀리면 계단 문턱 T2"),
            _r_skin("1-1 진입 SKIN (진입 온도대)", (c.get("heat_onset_skin_ap") or {}).get("skin"), ot.get("SKIN"), "계단 문턱 T2"),
            _r_info("1-1 진입 AP · 1계단 SKIN·AP", [(c.get("heat_onset_skin_ap") or {}).get("ap"), c.get("heat_step1_skin_ap")],
                    [ot.get("AP"), dict(skin=st.get("SKIN"), ap=st.get("AP"))]),
            _r_abs("360~420 s 배율", c.get("heat_ratio_end"), h.get("ratio_window"), TOL["npu_ratio_abs"], "계단 크기 a1+a2"),
            _r_skin("가열 끝 SKIN", c.get("heat_end_skin"), et.get("SKIN"), "열 블록"),
            _r_info("가열 끝 AP · status · BAT", [c.get("heat_end_ap"), c.get("heat_end_status"), c.get("heat_end_bat")],
                    [et.get("AP"), et.get("status"), et.get("BAT")])]
    probe_rows = [_r_class("탐침 해제 분류", _tok_probe(c.get("probe_class")), p.get("class_token"),
                           "θ ≤ 0.5: R50-fast 면 기각 · θ > 0.5: R50-slow/none 이면 기각 · R50-slow 면 둘 다 (이진형 자체)"),
                  _r_time("탐침 해제 시각", c.get("probe_release_s"), p.get("release_s"), TOL["event_s"], "해제 규칙"),
                  _r_info("탐침 해제 모양", c.get("probe_release_shape"), p.get("shape")),
                  _r_abs("탐침 1~5 칸 (10~60 s) 중앙 배율", c.get("probe_bins_1_5_median"), p.get("bins_1_5_median"), TOL["npu_ratio_abs"],
                         "θ 0.3: 계단 크기 · θ 0.75: > 1.03 이면 해제 지연")]
    prs = c.get("release_skin_ap")
    if prs and p.get("SKIN_k") is not None:
        probe_rows.append(_r_skin("해제 칸 SKIN", prs.get("skin"), p.get("SKIN_k"), "냉각 (c_f=1)"))
    else:
        probe_rows.append(_r_info("해제 칸 SKIN (한쪽 이상 해제 없음 — 해당 없음)", None if not prs else prs.get("skin"), p.get("SKIN_k")))
    probe_rows.append(_r_info("해제 칸 AP", None if not prs else prs.get("ap"), p.get("AP_k")))
    if c.get("probe_release_s") is None and p.get("release_s") is None:
        probe_rows.append(_r_info("해제 뒤 재조임 (둘 다 해제 없음 — 해당 없음)", None, None))
    else:
        probe_rows.append(_r_time("해제 뒤 재조임", c.get("retighten_after_release_s"), p.get("retighten_after_release_s"), TOL["event_s"],
                                  "'d50 은 다시 데운다' → 열 블록 (d50 전력)"))
    probe_rows.append(_r_mae("탐침 SKIN·AP 0/60/120/240/479 s", c.get("probe_temps"), p.get("temps"), "냉각 c_s · d50 전력 (α_NPU)"))
    if not h.get("premise_ok"):
        probe_rows = _na(probe_rows, "가열 부족")
    return rows + probe_rows


def _cmp_g50p(c, j, v2_adopted):
    h, p = j["heat"], j["probe"]
    et = h.get("end_thermal") or {}
    rows = [_r_time("1-1 진입", c.get("heat_onset_1_1_s"), h.get("onset_1_1_s"), TOL["gpu_onset_s"], "T_on,CM 37.2"),
            _r_rel("240~300 s 배율", c.get("heat_ratio_end"), h.get("ratio_window"), TOL["gpu_ratio_rel"], "깊이 W·D"),
            _r_skin("가열 끝 SKIN", c.get("heat_end_skin"), et.get("SKIN"), "열 블록"),
            _r_info("가열 끝 AP", c.get("heat_end_ap"), et.get("AP"))]
    probe_rows = [_r_class("탐침 해제 분류", _tok_probe(c.get("probe_class")), p.get("class_token"),
                           "R50-fast → θ_GPU > 0.5 또는 타이머 (모형 기각) · R50-slow → '깊이가 온도 따라 서서히 풀린다' 쪽 (칸 배율 궤적으로 가른다)"),
                  _r_time("탐침 해제 시각", c.get("probe_release_s"), p.get("release_s"), TOL["event_s"], "해제 규칙"),
                  _r_rel("탐침 1~5 칸 중앙 배율", c.get("probe_bins_1_5_median"), p.get("bins_1_5_median"), TOL["gpu_ratio_rel"], "깊이 = 정적 지도"),
                  _r_info("탐침 칸 0~5 궤적 ('계단형 하강' 은 수치 정의 없음 — 궤적 첨부)", (c.get("probe_bins_ratio_first12") or [])[:6], p.get("bins_0_5")),
                  _r_info("해제 칸 SKIN · AP (H-ap-히스 는 밤 규칙 — g50p 판정)", c.get("release_skin_ap"), [p.get("SKIN_k"), p.get("AP_k")]),
                  _r_mae("탐침 SKIN·AP 0/60/120/240/479 s", c.get("probe_temps"), p.get("temps"), "열 (d50 전력 α_GPU)")]
    if not h.get("premise_ok"):
        probe_rows = _na(probe_rows, "가열 부족")
    return rows + probe_rows


def _cmp_gi300(c, j, v2_adopted):
    h, r, rh = j["heat"], j["rest"], j["reheat"]
    et = h.get("end_thermal") or {}
    rows = [_r_time("1-1 진입", c.get("heat_onset_1_1_s"), h.get("onset_1_1_s"), TOL["gpu_onset_s"], "T_on"),
            _r_rel("540~600 s 배율", c.get("heat_ratio_end"), h.get("ratio_window"), TOL["gpu_ratio_rel"], "깊이"),
            _r_info("가열 끝 SKIN · AP", [c.get("heat_end_skin"), c.get("heat_end_ap")], [et.get("SKIN"), et.get("AP")]),
            _r_mae("휴지 SKIN·AP 0/60/120/180/240/299 s", c.get("rest_temps"), r.get("temps"), "냉각 c_s·c_f"),
            _r_class("재조임 분류", _tok_idle(c.get("retighten_class")), rh.get("class_token"),
                     "≤ 20 s → 못 늦춤 (모형보다 빠름 → 낮은 문턱 또는 깊이 기억) · ≥ 60 s → 유예 레버 (모형보다 느림)"),
            _r_time("재조임 시각", c.get("retighten_s"), rh.get("retighten_s"), TOL["event_s"], "재조임 규칙")]
    pre = (c.get("retighten_skin_ap") or {})
    if v2_adopted:
        m = rh.get("SKIN_k")
        ok = None if m is None else abs(m - V2_GI_TON[0]) <= V2_GI_TON[1]
        rows.append(_row("재조임 칸 SKIN (v2: = T_on 37.2 ± 0.5)", [V2_GI_TON[0], pre.get("skin")], m, "|SKIN_k − 37.2| ≤ 0.5 ℃", _v(ok), "T_on"))
    else:
        rows.append(_r_skin("재조임 칸 SKIN", pre.get("skin"), rh.get("SKIN_k"), "재조임 문턱"))
    rows.append(_r_info("재조임 칸 AP", pre.get("ap"), rh.get("AP_k")))
    rows.append(_r_rel("재가열 첫 칸", c.get("reheat_first_bin"), rh.get("first_bin_ratio"), TOL["gpu_ratio_rel"], "> 1.10 → 깊이에 기억"))
    rows.append(_r_rel("재가열 240~300 s 배율", c.get("reheat_ratio_240_300"), rh.get("ratio_240_300"), TOL["gpu_ratio_rel"], "깊이"))
    return rows


def _cmp_ni300(c, j, v2_adopted):
    h, r, rh = j["heat"], j["rest"], j["reheat"]
    et = h.get("end_thermal") or {}
    rows = [_r_time("1계단", c.get("heat_step1_s"), h.get("step1_s"), TOL["npu_step_s"], "열 블록"),
            _r_time("1-1 진입 (300 s 안)", c.get("heat_onset_1_1_s"), h.get("onset_1_1_s"), TOL["npu_step_s"],
                    "29.5 에서 진입이 나오면 가열이 모형보다 빠른 것"),
            _r_abs("240~300 s 배율", c.get("heat_ratio_end"), h.get("ratio_window"), TOL["npu_ratio_abs"], "계단 크기 · < 1.06 이면 가열 부족 (판정 불가)"),
            _r_skin("가열 끝 SKIN", c.get("heat_end_skin"), et.get("SKIN"), "열"),
            _r_info("가열 끝 AP", c.get("heat_end_ap"), et.get("AP")),
            _r_mae("휴지 SKIN·AP 0/60/120/180/240/299 s", c.get("rest_temps"), r.get("temps"), "냉각 (c_s 또는 d10 전력)")]
    re_rows = [_r_class("재조임 분류", _tok_idle(c.get("retighten_class")), rh.get("class_token"),
                        "≤ 20 s → 못 늦춤 (모형보다 빠름 → T1 38.1 보다 낮은 문턱 또는 기억) · 없음 → 냉각이 모형보다 깊음"),
               _r_time("재조임 시각 (≥ ref_d100 × 1.06, 마지막 k = 14)", c.get("retighten_s"), rh.get("retighten_s"), TOL["event_s"], "재조임 규칙")]
    pre = (c.get("retighten_skin_ap") or {})
    if v2_adopted:
        m = rh.get("SKIN_k")
        ok = None if m is None else (V2_NI_T1[0] <= m <= V2_NI_T1[1])
        re_rows.append(_row("재조임 칸 SKIN (v2: ∈ [38.1, 38.6])", [list(V2_NI_T1), pre.get("skin")], m, "38.1 ≤ SKIN_k ≤ 38.6", _v(ok), "T1"))
    else:
        re_rows.append(_r_skin("재조임 칸 SKIN", pre.get("skin"), rh.get("SKIN_k"), "T1"))
    re_rows.append(_r_info("재조임 칸 AP", pre.get("ap"), rh.get("AP_k")))
    re_rows.append(_r_abs("재가열 첫 칸", c.get("reheat_first_bin"), rh.get("first_bin_ratio"), TOL["npu_ratio_abs"], "> 1.03 → 기억"))
    if not h.get("premise_ok"):
        re_rows = _na(re_rows, "가열 부족")
    return rows + re_rows


CMP_FN = dict(n50p=_cmp_n50p, g50p=_cmp_g50p, gi300=_cmp_gi300, ni300=_cmp_ni300)


def _counts(rows):
    out = {}
    for r in rows:
        v = r["verdict"].split(" (")[0]
        out[v] = out.get(v, 0) + 1
    return out


def _block(label, cell, chain, j, v2_adopted):
    sk = j.get("start_skin")
    sup, note = _support(sk)
    rows = CMP_FN[chain](cell, j, v2_adopted)
    return dict(label=label, start_skin=sk, supported=sup, support_note=note, rows=rows, counts=_counts(rows))


def cmp_all(pred_v2=None, pred_v1=None, judged=None):
    judged = judged or {}
    out = dict(rule=("밤1004_사전등록_v1 §8 + v2_예측_밤1004.md '이 차이면 틀린 것' 열 + 헤더 기준 (스로틀모형_사전등록_v2 §5) · "
                     "비교 열 = 시작 SKIN 에 가까운 쪽 (29.5/30.5, 같으면 29.5) · 시작 SKIN ∉ [28.3, 31.6] → unsupported · 변형마다 따로"),
               dev_range=list(DEV_RANGE), tolerances=TOL, imports=import_check(),
               predictions=dict(v2=dict(present=pred_v2 is not None, model=None if pred_v2 is None else pred_v2.get("model")),
                                v1=dict(present=pred_v1 is not None, model=None if pred_v1 is None else pred_v1.get("model"))),
               measured={k: (None if v is None else dict(run_id=v.get("run_id"), start_skin=v.get("start_skin"))) for k, v in judged.items()},
               v2={}, v1={}, reference_forms={}, notes=[])
    if pred_v2 is None:
        out["notes"].append("v2 예측 없음")
    if pred_v1 is None:
        out["notes"].append("v1 예측 없음")
    for chain in ("n50p", "g50p", "gi300", "ni300"):
        j = judged.get(chain)
        if j is None:
            out["notes"].append(f"{chain}: 실측 없음 (칸 미실행·FAILED·미판정) — 대조 안 함")
            continue
        base = _pick_base(j.get("start_skin"))
        if base is None:
            out["notes"].append(f"{chain}: 시작 SKIN 미확인 — 비교 열 못 고름")
            continue
        if pred_v2 is not None:
            cells = (pred_v2.get("cells") or {}).get(chain) or {}
            for var in ("theta_0.3", "theta_0.75"):
                key = f"{base}/{var}"
                if key in cells:
                    out["v2"].setdefault(chain, {})[var] = dict(column=key, **_block(f"v2 {pred_v2.get('adopted_form')} {var} · {chain}", cells[key], chain, j, True))
            for form, by_chain in (pred_v2.get("reference_forms") or {}).items():
                for key, cell in ((by_chain or {}).get(chain) or {}).items():
                    if key.split("/")[0] == base:
                        out["reference_forms"].setdefault(form, {}).setdefault(chain, {})[key.split("/", 1)[1]] = dict(
                            column=key, **_block(f"참고 — 선택에 쓰지 않음: {form} {key} · {chain}", cell, chain, j, False))
        if pred_v1 is not None:
            cells = (pred_v1.get("cells") or {}).get(chain) or {}
            for key, cell in cells.items():
                if key.split("/")[0] == base:
                    out["v1"].setdefault(chain, {})[key.split("/", 1)[1]] = dict(column=key, **_block(f"v1 {key} · {chain}", cell, chain, j, False))
    if pred_v2 is not None:
        out["effn420"] = pred_v2.get("effn420")
    return out


# ============================================================ selftest (합성 — 결과 보기 전 양방향)
def _seg_fn(S, per_seg):
    """per_seg[i](t_in_seg) → 값. t = load_start 기준 초. 구간 0 앞 = 구간 0 의 0 s 값 · 전환 창 = 앞 구간 끝 값."""
    load0 = S["load_start_ns"]
    bounds = [((s["start_ns"] - load0) / 1e9, (s["end_ns"] - load0) / 1e9) for s in S["segments"]]

    def f(t):
        for i, (a, b) in enumerate(bounds):
            if t < a:
                return per_seg[i - 1](bounds[i - 1][1] - bounds[i - 1][0]) if i > 0 else per_seg[0](0.0)
            if t <= b:
                return per_seg[i](t - a)
        i = len(bounds) - 1
        return per_seg[i](bounds[i][1] - bounds[i][0])
    return f


def _mk(tmp, tag, segs, skin_ps, ap_ps, rate=20.0):
    rd = _synth_run(tmp, tag, segs, rate=rate, thermal=False)
    S = segments_of(load_run(rd))
    _write_thermal(rd, S["load_start_ns"], S["load_end_ns"], _seg_fn(S, skin_ps), _seg_fn(S, ap_ps))
    return load_run(rd)


def _piece(pr, base):
    return lambda t: base * pr[min(int(t // 10), len(pr) - 1)]


def _n50_run(tmp, tag, probe_ratio, heat_fn=None, ref_fn=None, start_skin=29.5, rel_skin=40.0, rel_ap=43.0, accel="NPU", probe_ap=None):
    base = 0.75 if accel == "NPU" else 2.5
    heat = heat_fn or ((lambda t: base if t < 150 else (base * 1.09 if t < 300 else base * 1.13)) if accel == "NPU"
                       else (lambda t: base if t < 70 else base * 1.9))
    hl = 420 if accel == "NPU" else 300
    segs = [dict(accelerator=accel, duty=50, duration_s=60, lat_ms=ref_fn or (lambda t: base), label="cold_ref_d50"),
            dict(accelerator=accel, duty=100, duration_s=hl, lat_ms=heat, label="heat_d100"),
            dict(accelerator=accel, duty=50, duration_s=480, lat_ms=_piece(list(probe_ratio), base), label="probe_d50")]
    skin = [lambda t: start_skin, lambda t: start_skin + (41.5 - start_skin) * t / hl, lambda t: 41.5 + (rel_skin - 41.5) * min(1.0, t / 60.0)]
    ap = [lambda t: start_skin - 1.0, lambda t: start_skin - 1.0 + (45.0 - start_skin + 1.0) * t / hl,
          probe_ap or (lambda t: 45.0 + (rel_ap - 45.0) * min(1.0, t / 30.0))]
    return _mk(tmp, tag, segs, skin, ap)


def _idle_run(tmp, tag, reheat_ratio, accel="GPU", heat_fn=None, rest_duty=1, rest_label="rest_idle", start_skin=29.5, re_skin=None):
    base = 2.5 if accel == "GPU" else 0.75
    hl = 600 if accel == "GPU" else 300
    rl = 300 if accel == "GPU" else 180
    heat = heat_fn or ((lambda t: base if t < 70 else base * 2.04) if accel == "GPU" else (lambda t: base if t < 150 else base * 1.09))
    segs = [dict(accelerator=accel, duty=10, duration_s=60, lat_ms=lambda t: base, label="cold_ref_d10"),
            dict(accelerator=accel, duty=100, duration_s=hl, lat_ms=heat, label="heat_d100"),
            dict(accelerator=accel, duty=rest_duty, duration_s=300, lat_ms=lambda t: base * 1.5, label=rest_label),
            dict(accelerator=accel, duty=100, duration_s=rl, lat_ms=_piece(list(reheat_ratio), base), label="reheat_d100")]
    skin = [lambda t: start_skin, lambda t: start_skin + (38.0 - start_skin) * t / hl, lambda t: 38.0 - 4.0 * t / 300.0,
            re_skin or (lambda t: 34.0 + 4.0 * min(1.0, t / 100.0))]
    ap = [lambda t: start_skin - 1.0, lambda t: start_skin - 1.0 + (41.0 - start_skin + 1.0) * t / hl, lambda t: 41.0 - 7.0 * t / 300.0,
          lambda t: 34.0 + 8.0 * min(1.0, t / 100.0)]
    return _mk(tmp, tag, segs, skin, ap)


def selftest():
    res = []

    def check(name, cond, got):
        res.append((name, bool(cond), got))
    tmp = tempfile.mkdtemp(prefix="night1004_selftest_")
    try:
        ic = import_check()
        check("import 대상 SHA 접두 일치 (m1m2 ea282d4a · night1003 a5ceab41 · fit_v1 379039dd)", all(v["ok"] for v in ic.values()),
              {k: v["sha256"][:8] for k, v in ic.items()})
        # ---------------- N50P ----------------
        j = n50p_judge(_n50_run(tmp, "n_k3", [1.13] * 3 + [1.01] * 45))
        check("n50p: 탐침 k=3 부터 4칸 ≤ ×1.03 → 30 s · R50-fast", j["probe"]["release_s"] == 30 and j["probe"]["class_token"] == "R50-fast", j["probe"]["classification"])
        check("n50p: R50-fast → 'H-timer 와 H-load(θ > 50 %) 는 못 가른다 — 다음은 d75'", "못 가른다" in j["conclusion"] and j["hypotheses"]["H-load (θ ≤ 50 %)"].startswith("기각"), j["conclusion"])
        check("n50p: 한 칸에 ×1.13 → ×1.01 → 계단형", j["probe"]["shape"] == "계단형", j["probe"]["shape"])
        check("n50p: 가열 1계단 150 s · 1-1 진입 300 s · 360~420 ×1.13 · 가열 충분 (합성)",
              j["heat"]["step1_s"] == 150 and j["heat"]["onset_1_1_s"] == 300 and abs(j["heat"]["ratio_window"] - 1.13) < 0.005 and j["heat"]["premise_ok"],
              (j["heat"]["step1_s"], j["heat"]["onset_1_1_s"], j["heat"]["ratio_window"]))
        check("n50p: A3 평탄 → 기준 안정", j["a3_reference_stable"] is True, j["a3_label"])
        check("n50p: 탐침 120 s SKIN = 40.0 (합성 HAL)", j["probe"]["temps"][2]["SKIN"] == 40.0, j["probe"]["temps"])
        j = n50p_judge(_n50_run(tmp, "n_cens", [1.09] * 48))
        check("n50p: 끝까지 ×1.09 → 440 s 안 미회복 (중도절단) · R50-none", j["probe"]["class_token"] == "R50-none" and "440 s" in j["probe"]["release"]["censored"], j["probe"]["release"])
        check("n50p: R50-none → 'H-timer 기각 · H-load(θ ≤ 50 %) 쪽'", j["conclusion"] == "H-timer 기각 · H-load(θ ≤ 50 %) 쪽" and j["hypotheses"]["H-timer"].startswith("기각"), j["conclusion"])
        j = n50p_judge(_n50_run(tmp, "n_weak", [1.01] * 48, heat_fn=lambda t: 0.75 if t < 300 else 0.75 * 1.04))
        check("n50p: 가열 360~420 s ×1.04 → '가열 부족 — 탐침 판정 불가'", (not j["heat"]["premise_ok"]) and "가열 부족" in j["conclusion"]
              and all("판정 불가" in v for v in j["hypotheses"].values()), (j["heat"]["ratio_window"], j["conclusion"]))
        j = n50p_judge(_n50_run(tmp, "n_50", [1.13] * 5 + [1.01] * 43))
        check("n50p: 해제 50 s → 미분류 · 가설 판정 불가", j["probe"]["class_token"] == "미분류" and "미분류" in j["conclusion"], j["probe"]["classification"])
        j = n50p_judge(_n50_run(tmp, "n_slow", [1.13] * 10 + [1.01] * 38))
        check("n50p: 해제 100 s → R50-slow · H-timer 기각", j["probe"]["class_token"] == "R50-slow" and j["hypotheses"]["H-timer"].startswith("기각"), j["probe"]["classification"])
        j = n50p_judge(_n50_run(tmp, "n_k44", [1.09] * 44 + [1.01] * 4))
        check("n50p: 마지막 검정 k = 44 → 440 s · R50-slow", j["probe"]["release_s"] == 440 and j["probe"]["class_token"] == "R50-slow", j["probe"]["release"])
        j = n50p_judge(_n50_run(tmp, "n_k45", [1.09] * 45 + [1.01] * 3))
        check("n50p: k = 45 부터 하강 (검정 불가) → 중도절단", j["probe"]["class_token"] == "R50-none", j["probe"]["release"])
        j = n50p_judge(_n50_run(tmp, "n_ret", [1.13] * 2 + [1.01] * 10 + [1.08] * 36))
        check("n50p: 해제 20 s 뒤 칸 12 부터 ≥ ×1.06 → 해제 뒤 재조임 (k′=12, 120 s)", j["probe"]["release_s"] == 20 and j["probe"]["retighten_after_release_s"] == 120,
              (j["probe"]["release_s"], j["probe"]["retighten_label"]))
        j = n50p_judge(_n50_run(tmp, "n_p15", [1.20, 1.10, 1.12, 1.14, 1.16, 1.18] + [1.12] * 42))
        check("n50p: 탐침 1~5 칸 중앙 배율 = 칸 1..5 중앙 (1.14)", abs(j["probe"]["bins_1_5_median"] - 1.14) < 1e-6, j["probe"]["bins_1_5_median"])
        lin = [max(1.0, 1.13 - 0.01 * k) for k in range(48)]
        j = n50p_judge(_n50_run(tmp, "n_lin", lin))
        check("n50p: 선형 감소 → 점진형", j["probe"]["shape"] == "점진형", (j["probe"]["shape"], j["probe"]["release_s"]))
        j = n50p_judge(_n50_run(tmp, "n_a3", [1.01] * 48, ref_fn=lambda t: 0.75 if t < 30 else 0.85))
        check("n50p: A3 기준 칸 ±5 % 밖 → 기준 불안정 (판정은 한다)", j["a3_reference_stable"] is False and j["probe"]["release_s"] is not None, j["a3_label"])
        # ---------------- G50P ----------------
        g = g50p_judge(_n50_run(tmp, "g_hys", [1.9, 1.9] + [1.05] * 46, accel="GPU", probe_ap=lambda t: 42.0 if t < 15 else 40.2))
        check("g50p: 해제 20 s · 해제 칸 AP 40.2 → H-ap-히스 기각 · R50-fast · H-load(GPU) 기각",
              g["probe"]["release_s"] == 20 and g["hypotheses"]["H-ap-히스"].startswith("기각") and g["probe"]["class_token"] == "R50-fast"
              and g["hypotheses"]["H-load(GPU)"].startswith("기각"), (g["probe"]["AP_k"], g["hypotheses"]))
        g = g50p_judge(_n50_run(tmp, "g_ok", [1.9, 1.9] + [1.05] * 46, accel="GPU", probe_ap=lambda t: 42.0 if t < 15 else 39.0))
        check("g50p: 해제 칸 AP 39.0 → H-ap-히스 유지", g["hypotheses"]["H-ap-히스"].startswith("유지"), (g["probe"]["AP_k"], g["hypotheses"]["H-ap-히스"]))
        g = g50p_judge(_n50_run(tmp, "g_weak", [1.05] * 48, accel="GPU", heat_fn=lambda t: 2.5 if t < 70 else 2.5 * 1.4))
        check("g50p: 240~300 s ×1.4 → 가열 부족 — 탐침 판정 불가", (not g["heat"]["premise_ok"]) and all("판정 불가" in v for v in g["hypotheses"].values()), g["heat"]["ratio_window"])
        g = g50p_judge(_n50_run(tmp, "g_none", [1.9] * 48, accel="GPU"))
        check("g50p: 끝까지 ×1.9 → R50-none · H-timer 기각 · H-load(GPU) 유지 · H-ap-히스 판정 불가",
              g["probe"]["class_token"] == "R50-none" and g["hypotheses"]["H-timer"].startswith("기각") and g["hypotheses"]["H-load(GPU)"].startswith("유지")
              and g["hypotheses"]["H-ap-히스"].startswith("판정 불가"), g["hypotheses"])
        g = g50p_judge(_n50_run(tmp, "g_slow", [1.5] * 8 + [1.05] * 40, accel="GPU"))
        check("g50p: 해제 80 s → R50-slow · 1-1 진입 70 s · 240~300 ×1.9", g["probe"]["class_token"] == "R50-slow" and g["heat"]["onset_1_1_s"] == 70
              and abs(g["heat"]["ratio_window"] - 1.9) < 0.005, (g["probe"]["release_s"], g["heat"]["onset_1_1_s"], g["heat"]["ratio_window"]))
        g = g50p_judge(_n50_run(tmp, "g_d108", [1.9, 1.9] + [1.08] * 46, accel="GPU"))
        check("g50p: ×1.08 (≤ 1.10) 도 해제 (δ 0.10) · n50p 였으면 아님", g["probe"]["release_s"] == 20, g["probe"]["release"])
        # ---------------- GI300 ----------------
        r = gi300_judge(_idle_run(tmp, "gi_imm", [2.0] * 30))
        check("gi300: 재조임 첫 칸부터 ≥ ×1.10 → 즉시(0 s) · 못 늦춘다", r["reheat"]["retighten"]["label"] == "즉시(0 s)" and r["reheat"]["class_token"] == "못 늦춘다", r["reheat"]["classification"])
        r = gi300_judge(_idle_run(tmp, "gi_none", [1.05] * 30))
        check("gi300: 300 s 안 없음 → 재조임 없음", r["reheat"]["retighten"]["retightened"] is False and r["reheat"]["class_token"] == "재조임 없음"
              and "재조임 없음" in r["reheat"]["retighten"]["label"], r["reheat"]["retighten"])
        r = gi300_judge(_idle_run(tmp, "gi_30", [1.0] * 3 + [2.0] * 27))
        check("gi300: 재조임 30 s → 중간", r["reheat"]["retighten_s"] == 30 and r["reheat"]["class_token"] == "중간", r["reheat"]["classification"])
        r = gi300_judge(_idle_run(tmp, "gi_60", [1.0] * 6 + [2.0] * 24))
        check("gi300: 재조임 60 s → 유예 레버", r["reheat"]["retighten_s"] == 60 and r["reheat"]["class_token"] == "유예 레버", r["reheat"]["classification"])
        r = gi300_judge(_idle_run(tmp, "gi_20", [1.0] * 2 + [2.0] * 28))
        check("gi300: 재조임 20 s → 못 늦춘다", r["reheat"]["retighten_s"] == 20 and r["reheat"]["class_token"] == "못 늦춘다", r["reheat"]["classification"])
        check("gi300: 휴지 SKIN 299 s = 34.0 · 0 s = 38.0 (합성) · 휴지 duty 1 표기",
              r["rest"]["temps"][-1]["SKIN"] == 34.0 and r["rest"]["temps"][0]["SKIN"] == 38.0 and "duty 1" in r["rest"]["rest_note"], (r["rest"]["temps"], r["rest"]["rest_note"]))
        check("gi300: 진입 70 s · 540~600 ×2.04 · 첫 칸 배율 · 240~300 비", r["heat"]["onset_1_1_s"] == 70 and abs(r["heat"]["ratio_window"] - 2.04) < 0.005
              and abs(r["reheat"]["first_bin_ratio"] - 1.0) < 1e-6 and r["reheat"]["ratio_240_300_vs_heat_540_600"] is not None,
              (r["heat"]["onset_1_1_s"], r["heat"]["ratio_window"], r["reheat"]["first_bin_ratio"]))
        r = gi300_judge(_idle_run(tmp, "gi_d10", [2.0] * 30, rest_duty=10, rest_label="rest_d10"))
        check("gi300: 휴지 d10 (rest_d10) → '완전 유휴 아님'", "완전 유휴 아님" in r["rest"]["rest_note"], r["rest"]["rest_note"])
        # ---------------- NI300 ----------------
        n = ni300_judge(_idle_run(tmp, "ni_weak", [1.0] * 18, accel="NPU", heat_fn=lambda t: 0.75 if t < 150 else 0.75 * 1.05))
        check("ni300: 가열 240~300 ×1.05 → 가열 부족 — 재조임 판정 불가", (not n["heat"]["premise_ok"]) and "판정 불가" in n["reheat"]["classification"], n["heat"]["premise_label"])
        n = ni300_judge(_idle_run(tmp, "ni_20", [1.0] * 2 + [1.08] * 16, accel="NPU"))
        check("ni300: 재조임 20 s (≥ ×1.06) → 못 늦춘다 · 1계단 150 s · 가열 충분", n["reheat"]["retighten_s"] == 20 and n["reheat"]["class_token"] == "못 늦춘다"
              and n["heat"]["step1_s"] == 150 and n["heat"]["premise_ok"], (n["reheat"]["classification"], n["heat"]["step1_s"]))
        n = ni300_judge(_idle_run(tmp, "ni_none", [1.0] * 18, accel="NPU"))
        check("ni300: 180 s 안 없음 → '180 s 안 재조임 없음' · 분류 유예 레버 (≥ 60 s 또는 없음)", n["reheat"]["class_token"] == "재조임 없음"
              and "180 s 안 재조임 없음" in n["reheat"]["retighten"]["label"] and "유예 레버" in n["reheat"]["classification"], (n["reheat"]["retighten"], n["reheat"]["classification"]))
        n = ni300_judge(_idle_run(tmp, "ni_k14", [1.0] * 14 + [1.08] * 4, accel="NPU"))
        check("ni300: k = 14 (마지막 검정) → 140 s · 유예 레버", n["reheat"]["retighten_s"] == 140 and n["reheat"]["class_token"] == "유예 레버", n["reheat"]["retighten"])
        n = ni300_judge(_idle_run(tmp, "ni_k15", [1.0] * 15 + [1.08] * 3, accel="NPU"))
        check("ni300: k = 15 부터 상승 (검정 불가) → 재조임 없음", n["reheat"]["class_token"] == "재조임 없음", n["reheat"]["retighten"])
        n = ni300_judge(_idle_run(tmp, "ni_106", [1.0] * 3 + [1.06] * 15, accel="NPU"))
        check("ni300: 경계 ×1.06 은 재조임 (≥) → 30 s 중간", n["reheat"]["retighten_s"] == 30 and n["reheat"]["class_token"] == "중간", n["reheat"]["retighten"])
        # ---------------- cmp ----------------
        pv2 = _load_json_opt(os.path.join(REPO, "d1sim", "out", "night_1004_prediction_v2.json"))
        pv1 = _load_json_opt(os.path.join(REPO, "d1sim", "out", "night_1004_prediction_v1.json"))
        jf = n50p_judge(_n50_run(tmp, "c_fast", [1.13] + [1.01] * 47, start_skin=29.7))
        c = cmp_all(pv2, pv1, dict(n50p=jf))
        cls03 = next(rw for rw in c["v2"]["n50p"]["theta_0.3"]["rows"] if rw["cell"] == "탐침 해제 분류")
        cls75 = next(rw for rw in c["v2"]["n50p"]["theta_0.75"]["rows"] if rw["cell"] == "탐침 해제 분류")
        check("cmp: N50P R50-fast (10 s) → θ_0.3 틀림 · θ_0.75 맞음 · 열 29.5", cls03["verdict"] == "틀림" and cls75["verdict"] == "맞음"
              and c["v2"]["n50p"]["theta_0.3"]["column"] == "29.5/theta_0.3", (cls03["verdict"], cls75["verdict"]))
        check("cmp: v1 (fast/skin) 와 reference_forms (참고) 블록도 채움", set(c["v1"].get("n50p", {}).keys()) == {"fast", "skin"}
              and "V2-Lk" in c["reference_forms"] and c["reference_forms"]["V2-Lk"]["n50p"]["kappa_lo"]["label"].startswith("참고"),
              (list(c["v1"].get("n50p", {}).keys()), list(c["reference_forms"].keys())))
        js = n50p_judge(_n50_run(tmp, "c_slow", [1.13] * 10 + [1.01] * 38, start_skin=30.2))
        c = cmp_all(pv2, None, dict(n50p=js))
        v = [next(rw for rw in c["v2"]["n50p"][var]["rows"] if rw["cell"] == "탐침 해제 분류")["verdict"] for var in ("theta_0.3", "theta_0.75")]
        check("cmp: N50P R50-slow → 두 변형 다 틀림 · 시작 30.2 → 30.5 열 · v1 없음 기록", v == ["틀림", "틀림"] and c["v2"]["n50p"]["theta_0.3"]["column"] == "30.5/theta_0.3"
              and "v1 예측 없음" in c["notes"], (v, c["notes"]))
        jt = n50p_judge(_n50_run(tmp, "c_tie", [1.13] * 10 + [1.01] * 38, start_skin=30.0))
        check("cmp: 시작 SKIN 30.0 (같은 거리) → 29.5 열", _pick_base(jt["start_skin"]) == "29.5", jt["start_skin"])
        jo = n50p_judge(_n50_run(tmp, "c_out", [1.13] * 10 + [1.01] * 38, start_skin=27.9))
        c = cmp_all(pv2, None, dict(n50p=jo))
        check("cmp: 시작 SKIN 27.9 → 적용 범위 밖 (unsupported)", c["v2"]["n50p"]["theta_0.3"]["supported"] is False
              and "unsupported" in c["v2"]["n50p"]["theta_0.3"]["support_note"], c["v2"]["n50p"]["theta_0.3"]["support_note"])
        c = cmp_all(None, None, dict(n50p=jf))
        check("cmp: 예측 JSON 없음 → '예측 없음' 기록 · 대조 블록 없음", "v2 예측 없음" in c["notes"] and "v1 예측 없음" in c["notes"] and not c["v2"] and not c["v1"], c["notes"])
        c = cmp_all(pv2, None, dict(n50p=None))
        check("cmp: 칸 실측 없음 → '실측 없음' 기록", any("실측 없음" in s for s in c["notes"]), c["notes"])
        rg = gi300_judge(_idle_run(tmp, "c_gi20", [1.0] * 2 + [2.0] * 28, re_skin=lambda t: 37.5))
        c = cmp_all(pv2, None, dict(gi300=rg))
        rows = c["v2"]["gi300"]["theta_0.3"]["rows"]
        vc = next(rw for rw in rows if rw["cell"] == "재조임 분류")["verdict"]
        vt = next(rw for rw in rows if rw["cell"] == "재조임 시각")["verdict"]
        vs = next(rw for rw in rows if rw["cell"].startswith("재조임 칸 SKIN"))["verdict"]
        check("cmp: GI300 재조임 20 s vs v2 30 s 중간 → 분류 틀림 · 시각 ±10 맞음 · 재조임 SKIN 37.5 = T_on ±0.5 맞음",
              vc == "틀림" and vt == "맞음" and vs == "맞음", (vc, vt, vs))
        rg = gi300_judge(_idle_run(tmp, "c_gi_hot", [1.0] * 3 + [2.0] * 27, re_skin=lambda t: 37.9))
        c = cmp_all(pv2, None, dict(gi300=rg))
        vs = next(rw for rw in c["v2"]["gi300"]["theta_0.3"]["rows"] if rw["cell"].startswith("재조임 칸 SKIN"))["verdict"]
        check("cmp: GI300 재조임 칸 SKIN 37.9 → v2 T_on 행 틀림", vs == "틀림", vs)
        rn = ni300_judge(_idle_run(tmp, "c_ni_none", [1.0] * 18, accel="NPU"))
        c = cmp_all(pv2, None, dict(ni300=rn))
        rows = c["v2"]["ni300"]["theta_0.3"]["rows"]
        vc = next(rw for rw in rows if rw["cell"] == "재조임 분류")["verdict"]
        vt = next(rw for rw in rows if rw["cell"].startswith("재조임 시각"))["verdict"]
        check("cmp: NI300 재조임 없음 vs v2 29.5 60 s → 분류 틀림 · 시각 틀림", vc == "틀림" and vt == "틀림", (vc, vt))
        rnw = ni300_judge(_idle_run(tmp, "c_ni_weak", [1.0] * 18, accel="NPU", heat_fn=lambda t: 0.75 if t < 150 else 0.75 * 1.05))
        c = cmp_all(pv2, None, dict(ni300=rnw))
        vc = next(rw for rw in c["v2"]["ni300"]["theta_0.3"]["rows"] if rw["cell"] == "재조임 분류")["verdict"]
        check("cmp: NI300 실측 가열 부족 → 재조임 행 '판정 불가 (가열 부족)'", vc.startswith("판정 불가"), vc)
        # ---------------- 구조 · 결정성 ----------------
        rd = _n50_run(tmp, "struct_ok", [1.01] * 48)
        lines = open(rd["jsonl"], encoding="utf-8").read().splitlines()
        keep = [l for l in lines if not ('"segment_start"' in l and J._detail(json.loads(l)).get("index") == 1)]
        keep = [l for l in keep if not ('"segment_end"' in l and J._detail(json.loads(l)).get("index") == 1)]
        bad = os.path.join(tmp, "struct_bad", "runs", "run-bad")
        os.makedirs(os.path.join(bad, "gpu"), exist_ok=True)
        open(os.path.join(bad, "gpu", "x.jsonl"), "w", encoding="utf-8").write("\n".join(keep) + "\n")
        try:
            n50p_judge(load_run(bad))
            check("구간 하나 뺀 JSONL → 오류로 멈춤", False, "판정이 나왔다")
        except JudgeError as err:
            check("구간 하나 뺀 JSONL → 오류로 멈춤", True, str(err))
        try:
            n50p_judge(_n50_run(tmp, "struct_gpu", [1.05] * 48, accel="GPU"))
            check("GPU 체인을 n50p 로 → 오류로 멈춤 (가속기)", False, "판정이 나왔다")
        except JudgeError as err:
            check("GPU 체인을 n50p 로 → 오류로 멈춤 (가속기)", True, str(err))
        try:
            gi300_judge(_n50_run(tmp, "struct_lab", [1.05] * 48, accel="GPU"))
            check("3구간 체인을 gi300 으로 → 오류로 멈춤 (구간 수)", False, "판정이 나왔다")
        except JudgeError as err:
            check("3구간 체인을 gi300 으로 → 오류로 멈춤 (구간 수)", True, str(err))
        a1 = dumps(n50p_judge(_n50_run(tmp, "detA", [1.13] * 3 + [1.01] * 45)))
        a2 = dumps(n50p_judge(_n50_run(tmp, "detB", [1.13] * 3 + [1.01] * 45)))
        check("결정성: n50p 같은 입력 두 번 = 같은 바이트 (태그 제외)", a1.replace("detA", "X") == a2.replace("detB", "X"), f"{len(a1)} B")
        b1 = dumps(cmp_all(pv2, pv1, dict(gi300=gi300_judge(_idle_run(tmp, "detC", [1.0] * 3 + [2.0] * 27)))))
        b2 = dumps(cmp_all(pv2, pv1, dict(gi300=gi300_judge(_idle_run(tmp, "detD", [1.0] * 3 + [2.0] * 27)))))
        check("결정성: cmp 같은 입력 두 번 = 같은 바이트 (태그 제외)", b1.replace("detC", "X") == b2.replace("detD", "X"), f"{len(b1)} B")
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
    for name in ("n50p", "g50p", "gi300", "ni300"):
        a = sub.add_parser(name)
        a.add_argument("run_dir")
        a.add_argument("--watch")
        a.add_argument("--out")
    a = sub.add_parser("cmp")
    a.add_argument("--pred-v2")
    a.add_argument("--pred-v1")
    for name in ("n50p", "g50p", "gi300", "ni300"):
        a.add_argument(f"--{name}")
    a.add_argument("--out")
    args = p.parse_args(argv)
    if args.cmd == "selftest":
        return selftest()
    try:
        if args.cmd in ("n50p", "g50p", "gi300", "ni300"):
            fn = dict(n50p=n50p_judge, g50p=g50p_judge, gi300=gi300_judge, ni300=ni300_judge)[args.cmd]
            res = fn(load_run(args.run_dir), load_watch(args.watch))
        else:
            for k in ("pred_v2", "pred_v1"):
                v = getattr(args, k)
                if v and not os.path.exists(v):
                    print(f"NOTE: {k} 파일 없음 → '예측 없음' ({v})", file=sys.stderr)
            judged = {}
            for name in ("n50p", "g50p", "gi300", "ni300"):
                v = getattr(args, name)
                judged[name] = _load_json_opt(v) if v else None
            res = cmp_all(_load_json_opt(args.pred_v2), _load_json_opt(args.pred_v1), judged)
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
