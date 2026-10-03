# -*- coding: utf-8 -*-
"""night1003_judge_pacing.py — GPU 페이싱 체인 판정 (`gpu_pacing_v1.json`: GPU d10 60 → d100 600 → d10 60 → d100 300).
`GPU페이싱_사전등록_v1.md` §2 글자 그대로. 구간 추출은 `m1m2_judge_1002.py` (SHA ea282d4a…) import (복사·수정 금지). 결과 보기 전 SHA 고정.

  py night1003_judge_pacing.py selftest
  py night1003_judge_pacing.py pacing <run_dir> [--watch csv] [--out f.json]
  py night1003_judge_pacing.py cmp --pred <night_1003_prediction_v1_pacing.json> --judge <pacing.json> [--out f.json]

규칙:
  ref_d100 = 구간 1 의 처음 30 s 추론 전수 중앙 (식은 d100 — 1-1 과 같은 정의) · ref_d10 = 구간 0 전수 중앙 (A3 ±5 %)
  구간 1 진입 = 1-1 (+10 %, 그 칸 + 뒤 3칸) — M1·M2 (70~100 s) 와 나란히 (기술)
  구간 2 회복 = M1M2 v1 §2 를 60 s 탐침에: 칸 k + 뒤 3칸 ≤ ref_d10 × 1.10 → 10k s, 마지막 검정 k = 2, 없으면 "검정 가능 범위(≤ 20 s) 안 미회복 — 중도절단"
  재조임 시각 = 구간 3 의 첫 10 s 칸 k 로서 칸 k 와 뒤 3칸이 모두 ≥ ref_d100 × 1.10 → 10k s. k = 0 → "즉시(0 s)". 300 s 안에 없으면 "재조임 없음"
  분류: ≤ 20 s → "60 s 휴지로는 재조임을 못 늦춘다" · ≥ 60 s → "60 s 휴지가 재조임을 늦춘다 (페이싱 후보)" · 30~50 s → "중간"
  보조 (기술만): 재조임 칸 SKIN·AP · 구간 3 의 240~300 s 배율 vs 구간 1 의 540~600 s 배율 · 구간 2 끝 SKIN·AP
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


_J_PATH = os.path.join(HERE, "m1m2_judge_1002.py")
if not os.path.exists(_J_PATH):
    _J_PATH = os.path.join(REPO, "s26", "tools", "s26_m1m2_judge_1002.py")
J = _load_module("m1m2_judge_1002", _J_PATH)
load_run, segments_of, bins10, window_median, thermal_at, soc_at, load_watch, onset_1_1, dumps, JudgeError, _synth_run = (
    J.load_run, J.segments_of, J.bins10, J.window_median, J.thermal_at, J.soc_at, J.load_watch, J.onset_1_1, J.dumps, J.JudgeError, J._synth_run)

BIN_S = 10
REF_S = 30
RISE = 0.10                 # 재조임 문턱 = ref_d100 × 1.10 (1-1 과 대칭)
HOLD_BINS = 3               # 그 칸 + 뒤 3칸
REST_RECOVER = 1.10         # 구간 2 회복 ≤ ref_d10 × 1.10 (M1M2 v1 §2)
REST_LAST_K = 2             # 60 s 탐침 → 마지막 검정 k
A3_TOL = 0.05
CLASS_FAST_S = 20           # ≤ 20 s → 못 늦춘다
CLASS_SLOW_S = 60           # ≥ 60 s → 페이싱 후보
EXPECTED_LABELS = ["cold_ref_d10", "heat_d100", "rest_d10", "reheat_d100"]
CMP_ONSET_S = 10.0          # cmp: 재조임·진입 시각 ±10 s (v1 §5 GPU 진입 기준) · 배율 ±10 %
CMP_RATIO_REL = 0.10


def _ratio_bins(seg, ref):
    return [None if b["median_ms"] is None else b["median_ms"] / ref for b in bins10(seg)]


def _thermal_bin(run, seg, t_s):
    return thermal_at(run, seg["start_ns"] + int(round(t_s * 1e9)))


def pacing_judge(run, watch=None):
    S = segments_of(run)
    segs = S["segments"]
    if len(segs) != 4:
        raise JudgeError(f"구간이 {len(segs)}개 — 페이싱 체인은 4구간")
    labels = [s["label"] for s in segs]
    if labels != EXPECTED_LABELS:
        raise JudgeError(f"구간 라벨 불일치: {labels} ≠ {EXPECTED_LABELS}")
    ref0, heat, rest, reheat = segs
    for s in segs:
        if s["n"] == 0:
            raise JudgeError(f"구간 {s['index']} ({s['label']}) 에 추론 없음")
    # 기준
    ref_d10 = float(np.median(ref0["lat_ms"]))
    ref0_ratio = _ratio_bins(ref0, ref_d10)
    a3 = all(r is not None and abs(r - 1.0) <= A3_TOL for r in ref0_ratio)
    ref_d100, n_ref100 = window_median(heat, 0, REF_S)
    if ref_d100 is None:
        raise JudgeError("구간 1 처음 30 s 에 추론 없음")
    # 구간 1 진입 (1-1)
    on = onset_1_1(heat)
    r540, _ = window_median(heat, 540, 600)
    heat_rep = dict(ref30_ms=on["ref_ms"], onset_1_1_s=on["onset_s"], edge_candidate_s=on["edge_candidate_s"],
                    ratio_540_600=(r540 / ref_d100) if r540 else None, n=heat["n"], length_s=heat["length_s"],
                    bins_ratio=on["bins_ratio"], end_thermal=thermal_at(run, heat["end_ns"]),
                    onset_thermal=(None if on["onset_s"] is None else _thermal_bin(run, heat, on["onset_s"])),
                    compare_note="M1 1002 진입 80 s · M2 H1/H2 60~100 s [D M1_결과_1002 · M2_결과_1002] — 재현성 기술만")
    # 구간 2 회복 (60 s 탐침, M1M2 v1 §2 규칙, 마지막 k = 2)
    pr2 = _ratio_bins(rest, ref_d10)
    last_k2 = min(REST_LAST_K, len(pr2) - 1 - HOLD_BINS)
    k_rec = None
    for k in range(0, last_k2 + 1):
        win = pr2[k:k + 1 + HOLD_BINS]
        if len(win) == 1 + HOLD_BINS and all(r is not None and r <= REST_RECOVER for r in win):
            k_rec = k
            break
    if k_rec is None:
        rest_rec = dict(recovered=False, recovery_s=None, k=None, last_testable_k=last_k2,
                        censored=f"검정 가능 범위(≤ {last_k2 * BIN_S} s) 안 미회복 — 중도절단")
    else:
        rest_rec = dict(recovered=True, recovery_s=k_rec * BIN_S, k=k_rec, last_testable_k=last_k2, censored=None)
    rest_bins = []
    for k, b in enumerate(bins10(rest)):
        th = _thermal_bin(run, rest, b["t0"])
        rest_bins.append(dict(k=k, t0=b["t0"], ratio_vs_ref_d10=pr2[k], median_ms=b["median_ms"], n=b["n"],
                              SKIN=None if th is None else th["SKIN"], AP=None if th is None else th["AP"]))
    # 구간 3 재조임
    pr3 = _ratio_bins(reheat, ref_d100)
    thr = ref_d100 * (1 + RISE) / ref_d100
    last_k3 = len(pr3) - 1 - HOLD_BINS
    k_re = None
    for k in range(0, last_k3 + 1):
        win = pr3[k:k + 1 + HOLD_BINS]
        if len(win) == 1 + HOLD_BINS and all(r is not None and r >= thr for r in win):
            k_re = k
            break
    if k_re is None:
        reheat_rec = dict(retightened=False, retighten_s=None, k=None, last_testable_k=last_k3, label=f"재조임 없음 ({reheat['length_s']:.0f} s 안)")
        cls = "재조임 없음 (300 s 안) — 분류 해당 없음"
    else:
        t_re = k_re * BIN_S
        reheat_rec = dict(retightened=True, retighten_s=t_re, k=k_re, last_testable_k=last_k3, label=("즉시(0 s)" if k_re == 0 else f"{t_re} s"))
        if t_re <= CLASS_FAST_S:
            cls = "60 s 휴지로는 재조임을 못 늦춘다 (재조임 ≤ 20 s)"
        elif t_re >= CLASS_SLOW_S:
            cls = "60 s 휴지가 재조임을 늦춘다 (페이싱 후보) (재조임 ≥ 60 s)"
        else:
            cls = "중간 (재조임 30~50 s)"
    re_th = None if k_re is None else _thermal_bin(run, reheat, k_re * BIN_S)
    r240, _ = window_median(reheat, 240, 300)
    reheat_bins = []
    for k, b in enumerate(bins10(reheat)):
        th = _thermal_bin(run, reheat, b["t0"])
        reheat_bins.append(dict(k=k, t0=b["t0"], ratio_vs_ref_d100=pr3[k], median_ms=b["median_ms"], n=b["n"],
                                SKIN=None if th is None else th["SKIN"], AP=None if th is None else th["AP"]))
    return dict(
        rule="GPU페이싱_사전등록_v1 §2: 재조임 = 구간 3 첫 칸 k 로서 칸 k 와 뒤 3칸 ≥ ref_d100×1.10 → 10k s · 구간 2 회복 = M1M2 v1 §2 (≤ ref_d10×1.10, 마지막 k=2) · 분류 ≤20 / 30~50 / ≥60",
        run_id=S["meta"].get("run_id"), chain_id=(S["meta"].get("chain_spec") or {}).get("chain_id"), chain_sha256=S["meta"].get("chain_sha256"),
        termination_reason=S["meta"].get("termination_reason"), completed_inference_count=S["meta"].get("completed_inference_count"),
        pilot_battery_pct=S["meta"].get("pilot_battery_pct"),
        start_skin=(thermal_at(run, ref0["start_ns"]) or {}).get("SKIN"),
        ref_d10_ms=ref_d10, ref0_bins_ratio=ref0_ratio, a3_reference_stable=a3, a3_label=("기준 안정" if a3 else "기준 불안정 (±5 % 밖 칸 있음)"),
        ref_d100_ms=ref_d100, ref_d100_n=n_ref100,
        heat=heat_rep,
        rest=dict(recovery=rest_rec, bins_ratio=pr2, bins=rest_bins, start_thermal=thermal_at(run, rest["start_ns"]), end_thermal=thermal_at(run, rest["end_ns"]),
                  start_soc=soc_at(watch, rest["start_wall_ms"]), n=rest["n"], length_s=rest["length_s"]),
        reheat=dict(retighten=reheat_rec, classification=cls, retighten_thermal=re_th,
                    SKIN_k=None if re_th is None else re_th["SKIN"], AP_k=None if re_th is None else re_th["AP"],
                    bins_ratio=pr3, bins=reheat_bins, start_thermal=thermal_at(run, reheat["start_ns"]), end_thermal=thermal_at(run, reheat["end_ns"]),
                    start_soc=soc_at(watch, reheat["start_wall_ms"]), n=reheat["n"], length_s=reheat["length_s"],
                    ratio_240_300=(r240 / ref_d100) if r240 else None,
                    ratio_240_300_vs_heat_540_600=(None if (r240 is None or heat_rep["ratio_540_600"] is None) else (r240 / ref_d100) / heat_rep["ratio_540_600"])),
        transitions=S["transitions"],
        segment_start_soc={str(s["index"]): soc_at(watch, s["start_wall_ms"]) for s in segs},
        segment_start_thermal={str(s["index"]): thermal_at(run, s["start_ns"]) for s in segs},
        counter_interpretations=[
            "재가열 시작 온도가 식은 출발보다 높아 일찍 조이는 것은 측정하려는 기제 자체 — 온도(재조임 칸 AP ≈ 42 근처인가)와 시간 설명을 같이 적는다",
            "d10 휴지는 idle 이 아니다 (10 % 부하 아래의 회복)",
            "전환 창 잔재 — 첫 칸만으로 판정하지 않는다 (칸 k + 뒤 3칸)",
            "SOC 하락 — 구간별 SOC 기록",
        ],
    )


def cmp_pacing(pred, j):
    """동결 v1 페이싱 예측 vs 실측. 비교 열 = 시작 SKIN 에 가까운 쪽. 시작 SKIN ∉ [28.3, 31.6] → unsupported."""
    sk = j.get("start_skin")
    cols = pred.get("pacing") or {}
    col = None
    if sk is not None and cols:
        col = min(cols, key=lambda k: abs(float(k) - sk))
    sup = sk is not None and 28.3 <= sk <= 31.6
    rows = []
    if col is None:
        return dict(column=None, start_skin=sk, supported=sup, rows=rows, note="예측 열 없음")
    p = cols[col]
    def v(ok):
        return "미확인" if ok is None else ("맞음" if ok else "틀림")
    m = j["heat"]["onset_1_1_s"]; pv = p.get("heat_onset_s")
    rows.append(dict(cell="가열 진입 (1-1)", predicted=pv, measured=m, criterion="|Δ| ≤ 10 s", verdict=v(None if (m is None or pv is None) else abs(m - pv) <= CMP_ONSET_S)))
    m = j["heat"]["ratio_540_600"]; pv = p.get("ratio_540_600")
    rows.append(dict(cell="540~600 s 배율", predicted=pv, measured=m, criterion="상대차 ≤ 10 %", verdict=v(None if (m is None or pv is None) else abs(m / pv - 1) <= CMP_RATIO_REL)))
    m = j["rest"]["recovery"]["recovery_s"]; pv = (p.get("rest_recovery") or {}).get("recovery_s")
    rows.append(dict(cell="휴지 60 s 회복 시각", predicted=pv, measured=m, criterion="같은 칸 (±10 s) · 둘 다 중도절단이면 맞음",
                     verdict=("맞음" if (m is None and pv is None) else v(None if (m is None or pv is None) else abs(m - pv) <= CMP_ONSET_S))))
    m = j["reheat"]["retighten"]["retighten_s"]; pv = (p.get("retighten") or {}).get("retighten_s")
    rows.append(dict(cell="재조임 시각", predicted=pv, measured=m, criterion="|Δ| ≤ 10 s · 둘 다 없음이면 맞음",
                     verdict=("맞음" if (m is None and pv is None) else v(None if (m is None or pv is None) else abs(m - pv) <= CMP_ONSET_S)),
                     if_wrong="v1 적분 제어기 K (식은 진입과 뜨거운 재진입을 한 K 로 못 냄 — 스로틀모형_v1 §6)"))
    m = j["reheat"]["classification"]; pv = p.get("classification")
    rows.append(dict(cell="분류", predicted=pv, measured=m, criterion="같은 분류", verdict=v(None if (m is None or pv is None) else m.split(" (")[0] == str(pv).split(" (")[0])))
    m = j["reheat"]["ratio_240_300"]; pv = p.get("reheat_ratio_240_300")
    rows.append(dict(cell="재가열 240~300 s 배율", predicted=pv, measured=m, criterion="상대차 ≤ 10 %", verdict=v(None if (m is None or pv is None) else abs(m / pv - 1) <= CMP_RATIO_REL)))
    et = j["rest"]["end_thermal"] or {}
    rows.append(dict(cell="휴지 끝 SKIN · AP (기술)", predicted=[p.get("rest_end_skin"), p.get("rest_end_ap")], measured=[et.get("SKIN"), et.get("AP")], criterion="기술만", verdict="—"))
    return dict(model=pred.get("model"), column=col, start_skin=sk, supported=sup,
                support_note=("적용 범위 안" if sup else f"적용 범위 밖 (unsupported): 시작 SKIN {sk} ∉ [28.3, 31.6]"), rows=rows)


# ============================================================ selftest
def _run(tmp, tag, rest_ratio, reheat_ratio, heat_onset=70, ref_fn=None):
    const = lambda v: (lambda t: v)
    rr = list(rest_ratio); rh = list(reheat_ratio)
    segs = [dict(accelerator="GPU", duty=10, duration_s=60, lat_ms=ref_fn or const(2.5), label="cold_ref_d10"),
            dict(accelerator="GPU", duty=100, duration_s=600, lat_ms=(lambda t: 2.5 if t < heat_onset else 5.1), label="heat_d100"),
            dict(accelerator="GPU", duty=10, duration_s=60, lat_ms=(lambda t: 2.5 * rr[min(int(t // 10), len(rr) - 1)]), label="rest_d10"),
            dict(accelerator="GPU", duty=100, duration_s=300, lat_ms=(lambda t: 2.5 * rh[min(int(t // 10), len(rh) - 1)]), label="reheat_d100")]
    return load_run(_synth_run(tmp, tag, segs, rate=50.0))


def selftest():
    res = []
    def check(name, cond, got):
        res.append((name, bool(cond), got))
    tmp = tempfile.mkdtemp(prefix="pacing_selftest_")
    try:
        j = pacing_judge(_run(tmp, "p_imm", [1.0] * 6, [2.0] * 30))
        check("재조임 첫 칸부터 ≥ ×1.10 → 즉시(0 s) · 못 늦춘다", j["reheat"]["retighten"]["label"] == "즉시(0 s)" and "못 늦춘다" in j["reheat"]["classification"], j["reheat"]["retighten"])
        j = pacing_judge(_run(tmp, "p_10", [1.0] * 6, [1.0] + [2.0] * 29))
        check("재조임 10 s → 못 늦춘다", j["reheat"]["retighten"]["retighten_s"] == 10 and "못 늦춘다" in j["reheat"]["classification"], j["reheat"]["classification"])
        j = pacing_judge(_run(tmp, "p_40", [1.0] * 6, [1.0] * 4 + [2.0] * 26))
        check("재조임 40 s → 중간", j["reheat"]["retighten"]["retighten_s"] == 40 and j["reheat"]["classification"].startswith("중간"), j["reheat"]["classification"])
        j = pacing_judge(_run(tmp, "p_60", [1.0] * 6, [1.0] * 6 + [2.0] * 24))
        check("재조임 60 s → 페이싱 후보", j["reheat"]["retighten"]["retighten_s"] == 60 and "페이싱 후보" in j["reheat"]["classification"], j["reheat"]["classification"])
        j = pacing_judge(_run(tmp, "p_none", [1.0] * 6, [1.05] * 30))
        check("300 s 안 ≥ ×1.10 없음 → 재조임 없음", j["reheat"]["retighten"]["retightened"] is False and "재조임 없음" in j["reheat"]["classification"], j["reheat"]["retighten"])
        j = pacing_judge(_run(tmp, "p_dip", [1.0] * 6, [1.0, 2.0, 2.0, 1.0, 2.0, 2.0, 2.0, 2.0] + [2.0] * 22))
        check("4칸 유지 안 되는 일시 상승은 재조임 아님 → 40 s", j["reheat"]["retighten"]["retighten_s"] == 40, j["reheat"]["retighten"])
        j = pacing_judge(_run(tmp, "r_10", [2.0, 0.98, 0.99, 1.0, 1.0, 1.0], [2.0] * 30))
        check("휴지 회복 k=1 → 10 s", j["rest"]["recovery"]["recovery_s"] == 10, j["rest"]["recovery"])
        j = pacing_judge(_run(tmp, "r_20", [2.0, 2.0, 0.98, 0.99, 1.0, 1.0], [2.0] * 30))
        check("휴지 회복 k=2 → 20 s (마지막 검정 k)", j["rest"]["recovery"]["recovery_s"] == 20 and j["rest"]["recovery"]["last_testable_k"] == 2, j["rest"]["recovery"])
        j = pacing_judge(_run(tmp, "r_cens", [2.0, 2.0, 2.0, 0.98, 0.99, 1.0], [2.0] * 30))
        check("휴지 회복 k=3 (검정 불가) → 중도절단", j["rest"]["recovery"]["recovered"] is False and "중도절단" in j["rest"]["recovery"]["censored"], j["rest"]["recovery"])
        check("구간 1 진입 70 s (합성) · 540~600 ×2.04", j["heat"]["onset_1_1_s"] == 70 and abs(j["heat"]["ratio_540_600"] - 2.04) < 0.01, (j["heat"]["onset_1_1_s"], j["heat"]["ratio_540_600"]))
        check("A3 평탄 → 기준 안정", j["a3_reference_stable"] is True, j["a3_label"])
        j = pacing_judge(_run(tmp, "a3", [1.0] * 6, [2.0] * 30, ref_fn=lambda t: 2.5 if t < 30 else 2.8))
        check("A3 기준 칸 ±5 % 밖 → 기준 불안정", j["a3_reference_stable"] is False, j["a3_label"])
        # cmp
        fake = dict(model="fake", pacing={"29.5": dict(heat_onset_s=70, ratio_540_600=2.0, rest_recovery=dict(recovery_s=10), retighten=dict(retighten_s=10),
                                                      classification="60 s 휴지로는 재조임을 못 늦춘다", reheat_ratio_240_300=2.0, rest_end_skin=37.0, rest_end_ap=38.0)})
        j = pacing_judge(_run(tmp, "c1", [2.0, 0.98, 0.99, 1.0, 1.0, 1.0], [1.0] + [2.0] * 29))
        c = cmp_pacing(fake, j)
        check("cmp: 재조임 10 vs 10 · 분류 같음 → 맞음", all(r["verdict"] in ("맞음", "—") for r in c["rows"]), [(r["cell"], r["verdict"]) for r in c["rows"]])
        j2 = pacing_judge(_run(tmp, "c2", [2.0, 0.98, 0.99, 1.0, 1.0, 1.0], [1.0] * 6 + [2.0] * 24))
        c2 = cmp_pacing(fake, j2)
        rt = next(r for r in c2["rows"] if r["cell"] == "재조임 시각")
        check("cmp: 재조임 60 vs 예측 10 → 틀림", rt["verdict"] == "틀림", rt)
        # 구조
        rd = _run(tmp, "struct", [1.0] * 6, [2.0] * 30)
        lines = open(rd["jsonl"], encoding="utf-8").read().splitlines()
        keep = [l for l in lines if not ('"segment_start"' in l and J._detail(json.loads(l)).get("index") == 2)]
        keep = [l for l in keep if not ('"segment_end"' in l and J._detail(json.loads(l)).get("index") == 2)]
        bad = os.path.join(tmp, "bad", "runs", "run-bad"); os.makedirs(os.path.join(bad, "gpu"), exist_ok=True)
        open(os.path.join(bad, "gpu", "x.jsonl"), "w", encoding="utf-8").write("\n".join(keep) + "\n")
        try:
            pacing_judge(load_run(bad)); check("구간 하나 뺀 JSONL → 오류로 멈춤", False, "판정이 나왔다")
        except JudgeError as err:
            check("구간 하나 뺀 JSONL → 오류로 멈춤", True, str(err))
        a1 = dumps(pacing_judge(_run(tmp, "detA", [1.0] * 6, [1.0] * 4 + [2.0] * 26))); a2 = dumps(pacing_judge(_run(tmp, "detB", [1.0] * 6, [1.0] * 4 + [2.0] * 26)))
        check("결정성: 같은 입력 두 번 = 같은 바이트 (run_id 제외)", a1.replace("detA", "X") == a2.replace("detB", "X"), f"{len(a1)} B")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    ok = all(c for _, c, _ in res)
    print("| 시험 | 결과 | 값 |\n|---|---|---|")
    for name, c, got in res:
        print(f"| {name} | {'PASS' if c else 'FAIL'} | {str(got)[:170]} |")
    print(f"\nselftest 전체: {'PASS' if ok else 'FAIL'} ({sum(1 for _, c, _ in res if c)}/{len(res)})")
    return 0 if ok else 1


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("selftest")
    a = sub.add_parser("pacing"); a.add_argument("run_dir"); a.add_argument("--watch"); a.add_argument("--out")
    a = sub.add_parser("cmp"); a.add_argument("--pred", required=True); a.add_argument("--judge", required=True); a.add_argument("--out")
    args = p.parse_args(argv)
    if args.cmd == "selftest":
        return selftest()
    try:
        if args.cmd == "pacing":
            res = pacing_judge(load_run(args.run_dir), load_watch(args.watch))
        else:
            res = cmp_pacing(json.load(open(args.pred, encoding="utf-8")), json.load(open(args.judge, encoding="utf-8")))
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
