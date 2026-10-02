# -*- coding: utf-8 -*-
"""m1m2_judge_1002.py — M1(스로틀 회복)·M2(자원 간 결합) 판정기. `sim\\M1M2_사전등록_초안_0928.md` §2·§3·§4·§5 를 글자 그대로.
results\\ 는 읽기만 한다. 같은 입력 두 번 = 같은 바이트 (출력은 sort_keys, 소수 6자리).

  py m1m2_judge_1002.py selftest
  py m1m2_judge_1002.py segments <run_dir> [--watch skin_watch.csv] [--out f.json]
  py m1m2_judge_1002.py m2 --c1 <run_dir> --h1 <run_dir> --h2 <run_dir> --c2 <run_dir>
                           [--victim 1] [--floor 0.03] [--metric all|first20] [--watch csv] [--out f.json]
  py m1m2_judge_1002.py m1 <run_dir> [--ref 0 --heat 1 --probe 2] [--watch csv] [--out f.json]
  py m1m2_judge_1002.py engine <run_dir> [--segment 0] [--out f.json]        # 초안 §3 엔진 대조 3항목
  py m1m2_judge_1002.py extract <run_dir> --segment K --out <dir>            # 구간 K 만 뽑은 가짜 결과 폴더 (throttle_curve_0928.py analyze 용)

run_dir = results\\<exp>\\runs\\<run_id>  (gpu\\*.jsonl 러너 JSONL + raw\\thermalservice.jsonl [+ merged\\events.jsonl 의 d1check 표본])

규칙 (초안 글자 그대로):
  구간 창 = segment_start.detail.start_ns ~ segment_end.detail.end_ns. 전환 창(초기화·warmup)은 어느 구간에도 넣지 않는다.
  지연 = 러너 JSONL inference.latency_ns. 10 s 칸 = 구간 시작 기준 [10k, 10k+10) s 에 시작한 추론, 완전한 칸만.
  M2 (§4): v = 피해자 구간 추론 전수 지연 중앙 (CPU 피해자: 처음 20 s 중앙이 주 지표).
      s_C = |v(C1) − v(C2)| / mean(v(C1), v(C2))
      결합 있음: min(v(H1), v(H2)) / max(v(C1), v(C2)) − 1 ≥ max(하한, 2 × s_C)      하한 = 0.03 (NPU·GPU 피해자) / 0.05 (CPU 피해자)
      결합 없음: max(v(H1), v(H2)) / min(v(C1), v(C2)) − 1 ≤ s_C
      그 밖 = 판정 보류
  M1 (§2): ref_d10 = 구간 0 전수 중앙. A3 = 구간 0 의 10 s 칸 배율이 전부 ±5 % 안이면 "기준 안정".
      회복 = 탐침 구간 첫 10 s 칸 k 로서 칸 k 와 뒤 3칸의 중앙이 모두 ≤ ref_d10 × 1.10 → 10k s. 없으면 "270 s 안 미회복"(중도절단).
      계단형 = 탐침 첫 칸 → 회복 칸 사이 줄어든 지연의 ≥ 50 % 가 한 칸 사이에서 줄었다. 아니면 점진형.
  엔진 대조 (§3): 진입(1-1 +10 %) ∈ [40, 90] s · 540~600 s 중앙 / 처음 30 s 중앙 ∈ [1.77, 2.29] · 540~600 s 평균 전력 / 처음 30 s ∈ [0.28, 0.51]
"""
import argparse, csv, datetime, glob, json, os, shutil, sys, tempfile

import numpy as np

BIN_S, REF_S, HOLD_S = 10, 30, 30
RISE = 0.10                       # 1-1 진입 문턱 (GPU·NPU)
M1_RECOVER = 1.10                 # 회복: ≤ ref_d10 × 1.10
M1_HOLD_BINS = 3                  # 칸 k + 뒤 3칸
M1_A3_TOL = 0.05                  # 기준 안정 ±5 %
M1_STEP_FRACTION = 0.50           # 계단형: 한 칸 사이 감소 ≥ 50 %
M2_FLOOR = {"NPU": 0.03, "GPU": 0.03, "CPU": 0.05}
M2_FIRST_S = 20                   # CPU 피해자 주 지표 창
M2_SOC_FLAG_PP = 5                # H·C 피해자 시작 SOC 차 > 5 %p 표시
ENGINE = {"onset_s": (40.0, 90.0), "ratio_540_600": (1.77, 2.29), "power_ratio_540_600": (0.28, 0.51)}
ND = 6


class JudgeError(RuntimeError):
    """구조가 깨진 입력 — 판정하지 않고 멈춘다."""


# ============================================================ 읽기
def _detail(e):
    d = e.get("detail")
    if isinstance(d, dict):
        return d
    try:
        return json.loads(d) if isinstance(d, str) else {}
    except ValueError:
        return {}


def _r(x):
    if isinstance(x, float):
        return round(x, ND)
    if isinstance(x, dict):
        return {k: _r(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_r(v) for v in x]
    if isinstance(x, (np.floating,)):
        return round(float(x), ND)
    if isinstance(x, (np.integer,)):
        return int(x)
    return x


def dumps(obj):
    return json.dumps(_r(obj), ensure_ascii=False, sort_keys=True, indent=1)


def load_run(run_dir):
    files = sorted(glob.glob(os.path.join(run_dir, "gpu", "*.jsonl")))
    if len(files) != 1:
        raise JudgeError(f"러너 JSONL 이 {len(files)}개 — {run_dir}")
    events = []
    bad = 0
    with open(files[0], encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            try:
                events.append(json.loads(line))
            except ValueError:
                bad += 1
    th = []
    tp = os.path.join(run_dir, "raw", "thermalservice.jsonl")
    if os.path.exists(tp):
        with open(tp, encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                try:
                    s = json.loads(line)
                except ValueError:
                    continue
                if s.get("parse_status") in (None, "ok") and isinstance(s.get("mono_ns"), int):
                    th.append(s)
    d1 = []
    mp = os.path.join(run_dir, "merged", "events.jsonl")
    if os.path.exists(mp):
        with open(mp, encoding="utf-8") as fh:
            for line in fh:
                if '"source":"d1check"' in line and '"event":"sample"' in line:
                    d1.append(json.loads(line))
    th.sort(key=lambda s: s["mono_ns"])
    d1.sort(key=lambda s: s["mono_ns"])
    return dict(run_dir=run_dir, jsonl=files[0], events=events, bad_lines=bad, thermal=th, d1=d1)


def load_watch(path):
    """s26_skin_watch(_npu).py CSV: local_time, thermal_status, SKIN, AP, BAT, battery_level, any_powered, action."""
    rows = []
    if not path:
        return rows
    with open(path, encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            try:
                t = datetime.datetime.fromisoformat(r["local_time"])
                lvl = int(r["battery_level"]) if r.get("battery_level") not in (None, "") else None
            except (ValueError, KeyError):
                continue
            rows.append((t, lvl, r))
    rows.sort(key=lambda x: x[0])
    return rows


# ============================================================ 구간
def segments_of(run):
    ev = run["events"]
    meta = next((e for e in ev if e.get("event") == "run_metadata"), None)
    if meta is None:
        raise JudgeError("run_metadata 없음")
    if meta.get("chain_mode") is not True:
        raise JudgeError("chain_mode 가 아님 (단일 런)")
    spec = meta.get("chain_spec") or {}
    n_spec = len(spec.get("segments", [])) if spec else None
    starts = [e for e in ev if e.get("event") == "segment_start"]
    ends = [e for e in ev if e.get("event") == "segment_end"]
    ls = [e for e in ev if e.get("event") == "load_start"]
    le = [e for e in ev if e.get("event") == "load_end"]
    if len(ls) != 1 or len(le) != 1:
        raise JudgeError(f"load_start {len(ls)} / load_end {len(le)}")
    sd = [_detail(e) for e in starts]
    ed = [_detail(e) for e in ends]
    if n_spec is not None and not (len(sd) == len(ed) == n_spec):
        raise JudgeError(f"구간 수 불일치: spec {n_spec} · segment_start {len(sd)} · segment_end {len(ed)}")
    if len(sd) != len(ed) or len(sd) == 0:
        raise JudgeError(f"segment_start {len(sd)} ≠ segment_end {len(ed)}")
    if [d.get("index") for d in sd] != list(range(len(sd))) or [d.get("index") for d in ed] != list(range(len(ed))):
        raise JudgeError("segment index 가 0..n-1 순서가 아님")
    inf = [e for e in ev if e.get("event") == "inference"]
    inf.sort(key=lambda e: int(e["start_mono_ns"]))
    st = np.array([int(e["start_mono_ns"]) for e in inf], dtype=np.int64)
    en = np.array([int(e["mono_ns"]) for e in inf], dtype=np.int64)
    lat = np.array([float(e["latency_ns"]) / 1e6 for e in inf], dtype=float)
    segs = []
    for s, e in zip(sd, ed):
        a, b = int(s["start_ns"]), int(e["end_ns"])
        if not a < b:
            raise JudgeError(f"구간 {s.get('index')} 창이 비정상 ({a} ≥ {b})")
        m = (st >= a) & (en <= b)
        n_in = int(m.sum())
        if e.get("inference_count") is not None and n_in != int(e["inference_count"]):
            raise JudgeError(f"구간 {s.get('index')} 추론 수 불일치: 창 안 {n_in} vs segment_end {e['inference_count']}")
        segs.append(dict(
            index=int(s["index"]), label=s.get("label"), accelerator=s.get("accelerator"), model=s.get("model"),
            duty=s.get("duty"), duration_s=s.get("duration_s"), gpu_precision=e.get("gpu_precision"),
            start_ns=a, end_ns=b, length_s=(b - a) / 1e9, termination_reason=e.get("termination_reason"),
            achieved_duty=e.get("achieved_duty_cycle_percent"), n=n_in,
            rel_t=(st[m] - a) / 1e9, lat_ms=lat[m],
            start_wall_ms=_wall_at(ev, a), end_wall_ms=_wall_at(ev, b),
        ))
    trans = []
    for a, b in zip([e for e in ev if e.get("event") == "chain_transition_start"],
                    [e for e in ev if e.get("event") == "chain_transition_end"]):
        d = _detail(b)
        trans.append({k: d.get(k) for k in ("to_segment", "from_accelerator", "to_accelerator", "backend_switch",
                                               "model_initialized", "warmup_count", "start_ns", "end_ns", "duration_ns",
                                               "env_init_ns", "model_init_ns", "buffer_init_ns")})
        if d.get("duration_ns") is not None:
            trans[-1]["duration_s"] = d["duration_ns"] / 1e9
    if len(trans) != len(segs) - 1:
        raise JudgeError(f"전환 창 {len(trans)}개 ≠ 구간 − 1 ({len(segs) - 1})")
    return dict(meta=meta, segments=segs, transitions=trans,
                load_start_ns=int(ls[0]["mono_ns"]), load_end_ns=int(le[0]["mono_ns"]))


def _wall_at(events, mono_ns):
    """mono_ns 에 가장 가까운 이벤트의 wall_ms 로 벽시계 근사 (SOC 를 호스트 감시 CSV 에서 찾을 때만 씀)."""
    best = None
    for e in events:
        m, w = e.get("mono_ns"), e.get("wall_ms")
        if isinstance(m, int) and isinstance(w, (int, float)):
            d = abs(m - mono_ns)
            if best is None or d < best[0]:
                best = (d, w + (mono_ns - m) / 1e6)
    return None if best is None else float(best[1])


def bins10(seg, bin_s=BIN_S):
    t, lat, L = seg["rel_t"], seg["lat_ms"], seg["length_s"]
    n = int(np.floor(L / bin_s + 1e-9))
    edges = np.searchsorted(t, np.arange(n + 1) * bin_s, side="left")
    out = []
    for k in range(n):
        v = lat[edges[k]:edges[k + 1]]
        out.append(dict(t0=k * bin_s, median_ms=float(np.median(v)) if len(v) else None, n=int(len(v))))
    return out


def window_median(seg, t0, t1):
    m = (seg["rel_t"] >= t0) & (seg["rel_t"] < t1)
    return (float(np.median(seg["lat_ms"][m])) if m.any() else None), int(m.sum())


def thermal_at(run, mono_ns):
    th = run["thermal"]
    if not th:
        return None
    i = int(np.argmin([abs(s["mono_ns"] - mono_ns) for s in th]))
    s = th[i]
    out = {k: (float(s[k]) if s.get(k) not in (None, "") else None) for k in ("SKIN", "AP", "BAT", "PA")}
    out["thermal_status"] = int(s["thermal_status"]) if s.get("thermal_status") not in (None, "") else None
    out["dt_s"] = (s["mono_ns"] - mono_ns) / 1e9
    return out


def d1_at(run, mono_ns):
    d1 = run["d1"]
    if not d1:
        return None
    i = int(np.argmin([abs(int(s["mono_ns"]) - mono_ns) for s in d1]))
    s = d1[i]
    return dict(thermal_status=s.get("thermal_status"), plugged=s.get("plugged"), headroom_now=s.get("headroom_now"),
                battery_temp_C=s.get("battery_temp_C"), dt_s=(int(s["mono_ns"]) - mono_ns) / 1e9)


def soc_at(watch, wall_ms):
    """호스트 감시 CSV 에서 벽시계 ≤ 구간 시작 인 마지막 battery_level. 없으면 None (= 미확인)."""
    if not watch or wall_ms is None:
        return None
    t = datetime.datetime.fromtimestamp(wall_ms / 1000.0)
    before = [(tt, lvl) for tt, lvl, _ in watch if tt <= t and lvl is not None]
    if not before:
        return None
    tt, lvl = before[-1]
    return dict(battery_level=lvl, age_s=(t - tt).total_seconds(), source="skin_watch_csv")


def power_series(run, seg):
    """d1check 표본 → (구간 시작 기준 t, W). current_raw µA · voltage mV, current_valid 만."""
    ts, pw = [], []
    for s in run["d1"]:
        if s.get("current_valid") is False or s.get("current_raw") is None or s.get("voltage_mV") is None:
            continue
        ts.append((int(s["mono_ns"]) - seg["start_ns"]) / 1e9)
        pw.append(-float(s["current_raw"]) * float(s["voltage_mV"]) / 1e9)
    return np.array(ts), np.array(pw)


def onset_1_1(seg, rise=RISE):
    """1-1: ref = 구간 처음 30 s 전수 중앙. t ≥ 30 s 첫 10 s 칸이 ref×(1+rise) 이상이고 뒤 3칸도 그 이상 → 칸 시작 시각."""
    ref, _ = window_median(seg, 0, REF_S)
    b = bins10(seg)
    if ref is None:
        return dict(ref_ms=None, onset_s=None, edge_candidate_s=None, bins=b)
    thr = ref * (1 + rise)
    need = HOLD_S // BIN_S
    edge = None
    onset = None
    for i, bb in enumerate(b):
        if bb["t0"] < REF_S or bb["median_ms"] is None:
            continue
        if bb["median_ms"] >= thr:
            follow = [b[j]["median_ms"] for j in range(i + 1, min(i + 1 + need, len(b)))]
            ok = all(v is not None and v >= thr for v in follow)
            if ok and i + need < len(b):
                onset = bb["t0"]
                break
            if ok and edge is None:
                edge = bb["t0"]
    return dict(ref_ms=ref, threshold_ms=thr, onset_s=onset, edge_candidate_s=edge,
                bins_ratio=[(bb["t0"], None if bb["median_ms"] is None else bb["median_ms"] / ref) for bb in b])


# ============================================================ segments 보고
def segment_report(run, watch=None):
    S = segments_of(run)
    meta = S["meta"]
    out = dict(run_dir=run["run_dir"], run_id=meta.get("run_id"), chain_id=(meta.get("chain_spec") or {}).get("chain_id"),
               chain_sha256=meta.get("chain_sha256"), model_prepare=meta.get("chain_model_prepare"),
               pilot_battery_pct=meta.get("pilot_battery_pct"), pilot_battery_temp_C=meta.get("pilot_battery_temp_C"),
               termination_reason=meta.get("termination_reason"), completed_inference_count=meta.get("completed_inference_count"),
               max_inference_spans=meta.get("max_inference_spans"), jvm_max_memory_bytes=meta.get("jvm_max_memory_bytes"),
               bad_jsonl_lines=run["bad_lines"], load_window_s=(S["load_end_ns"] - S["load_start_ns"]) / 1e9,
               thermal_samples=len(run["thermal"]), d1check_samples=len(run["d1"]), segments=[], transitions=S["transitions"])
    for seg in S["segments"]:
        f20, n20 = window_median(seg, 0, M2_FIRST_S)
        first10, _ = window_median(seg, 0, 10)
        rest, _ = window_median(seg, 10, seg["length_s"])
        out["segments"].append(dict(
            index=seg["index"], label=seg["label"], accelerator=seg["accelerator"], model=seg["model"], duty=seg["duty"],
            duration_s=seg["duration_s"], length_s=seg["length_s"], gpu_precision=seg["gpu_precision"],
            termination_reason=seg["termination_reason"], achieved_duty=seg["achieved_duty"], n=seg["n"],
            median_all_ms=float(np.median(seg["lat_ms"])) if seg["n"] else None,
            p95_ms=float(np.percentile(seg["lat_ms"], 95)) if seg["n"] else None,
            first20s_median_ms=f20, first20s_n=n20, first10s_median_ms=first10, after10s_median_ms=rest,
            bins10=bins10(seg), start_thermal=thermal_at(run, seg["start_ns"]), end_thermal=thermal_at(run, seg["end_ns"]),
            start_d1check=d1_at(run, seg["start_ns"]), start_soc=soc_at(watch, seg["start_wall_ms"]),
        ))
    return out


# ============================================================ M2
def m2_judge(runs, victim=1, floor=None, metric="all", watch=None):
    """runs = {'C1','H1','H2','C2'} → run dict. 초안 §4·§5 글자 그대로."""
    arms = {}
    for name in ("C1", "H1", "H2", "C2"):
        S = segments_of(runs[name])
        if victim >= len(S["segments"]):
            raise JudgeError(f"{name}: 피해자 구간 {victim} 없음")
        seg = S["segments"][victim]
        f20, n20 = window_median(seg, 0, M2_FIRST_S)
        first10, _ = window_median(seg, 0, 10)
        rest, _ = window_median(seg, 10, seg["length_s"])
        arms[name] = dict(
            run_id=S["meta"].get("run_id"), accelerator=seg["accelerator"], n=seg["n"],
            median_all_ms=float(np.median(seg["lat_ms"])) if seg["n"] else None,
            first20s_median_ms=f20, first10s_median_ms=first10, after10s_median_ms=rest, bins10=bins10(seg),
            victim_start_thermal=thermal_at(runs[name], seg["start_ns"]), victim_start_soc=soc_at(watch, seg["start_wall_ms"]),
            pilot_battery_pct=S["meta"].get("pilot_battery_pct"), transition=S["transitions"][victim - 1] if victim >= 1 else None,
            heat_segment=dict(accelerator=S["segments"][0]["accelerator"], length_s=S["segments"][0]["length_s"], n=S["segments"][0]["n"]),
        )
    accel = {arms[k]["accelerator"] for k in arms}
    if len(accel) != 1:
        raise JudgeError(f"팔마다 피해자 가속기가 다름: {sorted(accel)}")
    accel = accel.pop()
    if floor is None:
        floor = M2_FLOOR[accel]
    key = "first20s_median_ms" if metric == "first20" else "median_all_ms"
    v = {k: arms[k][key] for k in arms}
    if any(v[k] is None for k in v):
        raise JudgeError(f"피해자 지표 없음: {v}")
    vC1, vC2, vH1, vH2 = v["C1"], v["C2"], v["H1"], v["H2"]
    s_c = abs(vC1 - vC2) / ((vC1 + vC2) / 2.0)
    gain_low = min(vH1, vH2) / max(vC1, vC2) - 1.0
    gain_high = max(vH1, vH2) / min(vC1, vC2) - 1.0
    thr_yes = max(floor, 2.0 * s_c)
    if gain_low >= thr_yes:
        decision = "결합 있음"
    elif gain_high <= s_c:
        decision = "결합 없음"
    else:
        decision = "판정 보류"
    soc = {k: (arms[k]["victim_start_soc"] or {}).get("battery_level") for k in arms}
    soc_flag = None
    if all(soc[k] is not None for k in soc):
        soc_flag = max(abs(soc[h] - soc[c]) for h in ("H1", "H2") for c in ("C1", "C2")) > M2_SOC_FLAG_PP
    return dict(
        rule="M1M2_사전등록 §4/§5: 있음 = min(vH)/max(vC)−1 ≥ max(하한, 2·s_C) · 없음 = max(vH)/min(vC)−1 ≤ s_C · 그 밖 보류",
        victim_index=victim, victim_accelerator=accel, metric=("처음 20 s 중앙" if metric == "first20" else "구간 전수 중앙"),
        floor=floor, v_ms=v, s_C=s_c, gain_low=gain_low, gain_high=gain_high, threshold_yes=thr_yes, threshold_no=s_c,
        decision=decision, victim_start_soc=soc, soc_diff_over_5pp=soc_flag, arms=arms,
        note="결론 문장은 '자원 간 결합(열 또는 공유 전력 한도)' — 기제를 주장하지 않는다 (초안 §4 반대 해석 5)",
    )


# ============================================================ M1
def m1_judge(run, ref_i=0, heat_i=1, probe_i=2, watch=None):
    S = segments_of(run)
    if max(ref_i, heat_i, probe_i) >= len(S["segments"]):
        raise JudgeError(f"구간이 {len(S['segments'])}개 — ref/heat/probe {ref_i}/{heat_i}/{probe_i}")
    ref, heat, probe = S["segments"][ref_i], S["segments"][heat_i], S["segments"][probe_i]
    if ref["n"] == 0:
        raise JudgeError("기준 구간에 추론 없음")
    ref_d10 = float(np.median(ref["lat_ms"]))
    ref_bins = bins10(ref)
    ref_ratio = [None if b["median_ms"] is None else b["median_ms"] / ref_d10 for b in ref_bins]
    a3_stable = all(r is not None and abs(r - 1.0) <= M1_A3_TOL for r in ref_ratio)
    pb = bins10(probe)
    pr = [None if b["median_ms"] is None else b["median_ms"] / ref_d10 for b in pb]
    k_rec = None
    last_testable = len(pr) - 1 - M1_HOLD_BINS
    for k in range(0, last_testable + 1):
        win = pr[k:k + 1 + M1_HOLD_BINS]
        if all(r is not None and r <= M1_RECOVER for r in win):
            k_rec = k
            break
    shape = None
    step = None
    if k_rec is None:
        recovery = dict(recovered=False, recovery_s=None, censored=f"{(last_testable + 1) * BIN_S} s 안 미회복 (오른쪽 중도절단)",
                        last_testable_k=last_testable)
    else:
        recovery = dict(recovered=True, recovery_s=k_rec * BIN_S, k=k_rec, last_testable_k=last_testable)
        if k_rec == 0:
            shape = "즉시 회복 — 모양 판정 해당 없음"
        else:
            total = pr[0] - pr[k_rec]
            steps = [pr[j - 1] - pr[j] for j in range(1, k_rec + 1)]
            step = dict(total_drop_ratio=total, max_single_step=max(steps), argmax_step_k=int(np.argmax(steps)) + 1,
                        fraction=(max(steps) / total) if total > 0 else None)
            if total <= 0:
                shape = "감소 없음 — 모양 판정 해당 없음"
            else:
                shape = "계단형" if step["fraction"] >= M1_STEP_FRACTION else "점진형"
    # 탐침 칸별 SKIN·AP 나란히
    probe_thermal = []
    for b in pb:
        th = thermal_at(run, probe["start_ns"] + int(b["t0"] * 1e9))
        probe_thermal.append(dict(t0=b["t0"], ratio=None if b["median_ms"] is None else b["median_ms"] / ref_d10,
                                  median_ms=b["median_ms"], n=b["n"], SKIN=th and th["SKIN"], AP=th and th["AP"], BAT=th and th["BAT"]))
    # 구간 1 (가열) — C1a 재현성 보조 자료
    on = onset_1_1(heat)
    r540, _ = window_median(heat, 540, 600)
    r1000, _ = window_median(heat, 1000, 1200)
    heat_rep = dict(onset_s=on["onset_s"], edge_candidate_s=on["edge_candidate_s"], ref30_ms=on["ref_ms"],
                    ratio_540_600=(r540 / on["ref_ms"]) if (r540 and on["ref_ms"]) else None,
                    ratio_1000_1200=(r1000 / on["ref_ms"]) if (r1000 and on["ref_ms"]) else None,
                    n=heat["n"], length_s=heat["length_s"])
    return dict(
        rule="M1M2_사전등록 §2: 회복 = 탐침 10 s 칸 k 와 뒤 3칸 ≤ ref_d10×1.10 → 10k s · 없으면 중도절단 · 계단형 = 한 칸 감소 ≥ 50 %",
        run_id=S["meta"].get("run_id"), ref_d10_ms=ref_d10, ref_n=ref["n"], ref_bins_ratio=ref_ratio,
        a3_reference_stable=a3_stable, a3_label=("기준 안정" if a3_stable else "기준 불안정 (±5 % 밖 칸 있음)"),
        probe=dict(accelerator=probe["accelerator"], duty=probe["duty"], length_s=probe["length_s"], n=probe["n"],
                   bins_ratio=pr, bins=probe_thermal, start_thermal=thermal_at(run, probe["start_ns"]),
                   start_soc=soc_at(watch, probe["start_wall_ms"])),
        recovery=recovery, shape=shape, step=step, heat_segment=heat_rep,
        heat_end_thermal=thermal_at(run, heat["end_ns"]), transitions=S["transitions"],
        segment_start_soc={str(s["index"]): soc_at(watch, s["start_wall_ms"]) for s in S["segments"]},
        pilot_battery_pct=S["meta"].get("pilot_battery_pct"),
    )


# ============================================================ 엔진 대조 (§3)
def engine_compare(run, seg_i=0):
    S = segments_of(run)
    if seg_i >= len(S["segments"]):
        raise JudgeError(f"구간 {seg_i} 없음")
    seg = S["segments"][seg_i]
    on = onset_1_1(seg)
    m540, n540 = window_median(seg, 540, 600)
    ratio = (m540 / on["ref_ms"]) if (m540 is not None and on["ref_ms"]) else None
    pt, pw = power_series(run, seg)
    p0 = p540 = pratio = None
    if len(pt):
        m0 = (pt >= 0) & (pt < REF_S)
        m5 = (pt >= 540) & (pt < 600)
        if m0.any() and m5.any():
            p0, p540 = float(pw[m0].mean()), float(pw[m5].mean())
            pratio = p540 / p0 if p0 else None
    vals = dict(onset_s=on["onset_s"], ratio_540_600=ratio, power_ratio_540_600=pratio)
    checks = {}
    for k, (lo, hi) in ENGINE.items():
        checks[k] = None if vals[k] is None else bool(lo <= vals[k] <= hi)
    if any(v is None for v in checks.values()):
        verdict = "보류 (항목 미확인)"
    elif all(checks.values()):
        verdict = "같은 모양"
    else:
        verdict = "다른 모양"
    return dict(rule="M1M2_사전등록 §3: 진입 ∈ [40,90] s · 540~600/처음 30 s ∈ [1.77,2.29] · 전력 비 ∈ [0.28,0.51] — 셋 다 → 같은 모양",
                run_id=S["meta"].get("run_id"), segment=seg_i, accelerator=seg["accelerator"], length_s=seg["length_s"], n=seg["n"],
                ref30_ms=on["ref_ms"], median_540_600_ms=m540, n_540_600=n540, power_first30_W=p0, power_540_600_W=p540,
                values=vals, ranges=ENGINE, checks=checks, verdict=verdict, edge_candidate_s=on["edge_candidate_s"],
                bins_ratio=on["bins_ratio"])


# ============================================================ extract (구간 하나 → 가짜 결과 폴더)
def extract(run, seg_i, out_dir):
    """구간 K 의 inference 줄만 담은 러너 JSONL 과 thermalservice/merged 표본을 <out>/runs/<run_id>/ 에 쓴다.
    throttle_curve_0928.py analyze <out> --duration <구간 길이> --duty <구간 duty> 용. 1-6 의 duty·건수·증거 검사는 이 추출본에 맞지 않는다 (기록만)."""
    S = segments_of(run)
    seg = S["segments"][seg_i]
    meta = dict(S["meta"])
    rid = meta.get("run_id")
    dst = os.path.join(out_dir, "runs", rid)
    os.makedirs(os.path.join(dst, "gpu"), exist_ok=True)
    os.makedirs(os.path.join(dst, "raw"), exist_ok=True)
    os.makedirs(os.path.join(dst, "merged"), exist_ok=True)
    a, b = seg["start_ns"], seg["end_ns"]
    inf = [e for e in run["events"] if e.get("event") == "inference" and a <= int(e["start_mono_ns"]) and int(e["mono_ns"]) <= b]
    meta.update(dict(requested_duration_s=seg["duration_s"], target_duration_ns=int(seg["duration_s"]) * 1_000_000_000,
                     actual_load_duration_ns=b - a, completed_inference_count=len(inf), requested_duty_cycle_percent=seg["duty"],
                     extracted_segment=seg_i, extracted_from=os.path.basename(run["jsonl"]), termination_reason=seg["termination_reason"]))
    ls = dict(next(e for e in run["events"] if e.get("event") == "load_start")); ls["mono_ns"] = a; ls["start_mono_ns"] = a
    le = dict(next(e for e in run["events"] if e.get("event") == "load_end")); le["mono_ns"] = b; le["start_mono_ns"] = b
    fs = dict(next(e for e in reversed(run["events"]) if e.get("event") == "file_summary"))
    rows = [meta, ls] + inf + [le]
    fs.update(dict(inference_span_count=len(inf), completed_inference_count=len(inf), file_event_count=len(rows) + 1,
                   sequence_first=0, sequence_last=len(rows)))
    rows.append(fs)
    for i, e in enumerate(rows):
        e["sequence"] = i
    with open(os.path.join(dst, "gpu", os.path.basename(run["jsonl"])), "w", encoding="utf-8") as fh:
        for e in rows:
            fh.write(json.dumps(e, ensure_ascii=False, separators=(",", ":")) + "\n")
    src_th = os.path.join(run["run_dir"], "raw", "thermalservice.jsonl")
    if os.path.exists(src_th):
        shutil.copyfile(src_th, os.path.join(dst, "raw", "thermalservice.jsonl"))
    src_m = os.path.join(run["run_dir"], "merged", "events.jsonl")
    if os.path.exists(src_m):
        with open(src_m, encoding="utf-8") as fi, open(os.path.join(dst, "merged", "events.jsonl"), "w", encoding="utf-8") as fo:
            for line in fi:
                if '"event":"inference"' in line:
                    continue
                fo.write(line)
            for e in inf:
                fo.write(json.dumps(e, ensure_ascii=False, separators=(",", ":")) + "\n")
    with open(os.path.join(dst, "EXTRACT_README.txt"), "w", encoding="utf-8") as fh:
        fh.write(f"segment {seg_i} ({seg['label']}, {seg['accelerator']} d{seg['duty']} {seg['duration_s']} s) extracted from {run['run_dir']}\n"
                 f"load_start/load_end = segment window. Not a measurement run: 1-6 duty/count/evidence checks do not apply.\n")
    return dst


# ============================================================ selftest (합성 JSONL — 결과 보기 전 양방향)
def _synth_run(root, name, segments, rate=50.0, transition_s=0.5, model_init_ns=200_000_000, thermal=True, power=None, pilot_pct=85):
    """segments = [dict(accelerator, duty, duration_s, lat_ms=callable(t_rel)->ms)]. 1 s thermalservice 표본, 선택 d1check 전력 표본."""
    rd = os.path.join(root, name, "runs", "run-" + name)
    for d in ("gpu", "raw", "merged"):
        os.makedirs(os.path.join(rd, d), exist_ok=True)
    spec = {"schema": "d1-npu-chain-v1", "chain_id": name, "model_prepare": "per_segment",
            "segments": [{"accelerator": s["accelerator"], "model": "models/x.tflite", "input_spec": "lcg-unit",
                          "duty": s["duty"], "duration_s": s["duration_s"]} for s in segments]}
    t = 1_000_000_000_000  # mono_ns
    wall0 = 1_790_000_000_000
    ev = []
    seq = [0]

    def push(e):
        e = dict(e); e["sequence"] = seq[0]; seq[0] += 1
        e.setdefault("wall_ms", wall0 + (e["mono_ns"] - 1_000_000_000_000) // 1_000_000)
        ev.append(e)

    def inst(event, mono, detail=None, phase="chain"):
        push(dict(event=event, phase=phase, status="ok", mono_ns=mono, start_mono_ns=mono, latency_ns=0, detail=detail))

    meta = dict(event="run_metadata", mono_ns=t, chain_mode=True, chain_spec=spec, chain_sha256="0" * 64, chain_model_prepare="per_segment",
                run_id="run-" + name, pilot_battery_pct=pilot_pct, termination_reason="duration_complete", duty_cycle_period_ns=10_000_000_000,
                requested_duration_s=sum(s["duration_s"] for s in segments))
    push(meta)
    load0 = t + 1_000_000_000
    inst("load_start", load0, phase="run")
    cur = load0
    total_inf = 0
    infs = []
    for i, s in enumerate(segments):
        if i > 0:
            a = cur
            b = cur + int(transition_s * 1e9)
            inst("chain_transition_start", a, json.dumps(dict(to_segment=i, start_ns=a)))
            push(dict(event="chain_model_init", phase="setup", status="ok", start_mono_ns=a, mono_ns=a + model_init_ns, latency_ns=model_init_ns))
            inst("chain_transition_end", b, json.dumps(dict(to_segment=i, from_accelerator=segments[i - 1]["accelerator"],
                                                            to_accelerator=s["accelerator"], backend_switch=segments[i - 1]["accelerator"] != s["accelerator"],
                                                            model_initialized=True, warmup_count=20, start_ns=a, end_ns=b, duration_ns=b - a,
                                                            env_init_ns=5_000_000, model_init_ns=model_init_ns, buffer_init_ns=300_000)))
            cur = b
        a = cur
        b = a + int(s["duration_s"] * 1e9)
        inst("segment_start", a, json.dumps(dict(index=i, label=s.get("label", f"seg{i}"), accelerator=s["accelerator"], model="models/x.tflite",
                                                  input_spec="lcg-unit", duty=s["duty"], duration_s=s["duration_s"], first_inference_index=total_inf, start_ns=a)))
        n_seg = 0
        step = int(1e9 / rate)
        active = s["duty"] / 100.0
        tt = a
        while tt + 1 < b:
            rel = (tt - a) / 1e9
            # duty < 100: 10 s 주기 안 처음 duty% 만 가동
            if active < 1.0 and (rel % 10.0) >= 10.0 * active:
                tt = a + int((np.floor(rel / 10.0) + 1) * 10.0 * 1e9)
                continue
            lat_ns = int(round(float(s["lat_ms"](rel)) * 1e6))
            if tt + lat_ns > b:      # 러너는 구간 끝을 넘는 추론을 시작하지 않는다 (end_ns 는 마지막 추론 뒤)
                break
            infs.append(dict(event="inference", phase="run", status="ok", start_mono_ns=tt, mono_ns=tt + lat_ns, latency_ns=lat_ns,
                             inference_index=total_inf + n_seg, batch_size=1))
            n_seg += 1
            tt += max(step, lat_ns)
        for e in infs[len(infs) - n_seg:]:
            push(e)
        inst("segment_end", b, json.dumps(dict(index=i, label=s.get("label", f"seg{i}"), accelerator=s["accelerator"], model="models/x.tflite",
                                                gpu_precision=("FP32" if s["accelerator"] == "GPU" else None), requested_duty_cycle_percent=s["duty"],
                                                start_ns=a, end_ns=b, first_inference_index=total_inf, inference_count=n_seg,
                                                achieved_duty_cycle_percent=float(s["duty"]), termination_reason="duration_complete")))
        total_inf += n_seg
        cur = b
    inst("load_end", cur, phase="run")
    push(dict(event="file_summary", phase="flush", status="ok", mono_ns=cur, inference_span_count=total_inf, completed_inference_count=total_inf,
              file_event_count=len(ev) + 1, termination_reason="duration_complete"))
    with open(os.path.join(rd, "gpu", f"gpu-events-run-{name}.jsonl"), "w", encoding="utf-8") as fh:
        for e in ev:
            fh.write(json.dumps(e, separators=(",", ":")) + "\n")
    if thermal:
        with open(os.path.join(rd, "raw", "thermalservice.jsonl"), "w", encoding="utf-8") as fh:
            m = load0 - 60_000_000_000
            k = 0
            while m <= cur + 5_000_000_000:
                skin = 30.0 + 8.0 * min(1.0, max(0.0, (m - load0) / 1e9) / 600.0)
                fh.write(json.dumps(dict(source="thermalservice", event="sample", mono_ns=m, parse_status="ok", SKIN=f"{skin:.1f}", AP=f"{skin + 2:.1f}",
                                         BAT=f"{skin - 2:.1f}", PA=f"{skin:.1f}", thermal_status="0")) + "\n")
                m += 1_000_000_000; k += 1
    if power is not None:
        with open(os.path.join(rd, "merged", "events.jsonl"), "w", encoding="utf-8") as fh:
            m = load0 - 60_000_000_000
            while m <= cur + 5_000_000_000:
                w = float(power((m - load0) / 1e9))
                fh.write(json.dumps(dict(source="d1check", event="sample", mono_ns=m, current_raw=-int(w / 4.0 * 1e6), current_valid=True,
                                         voltage_mV=4000, plugged=0, thermal_status=0, headroom_now=0.5, battery_temp_C=30.0),
                                    separators=(",", ":")) + "\n")
                m += 1_000_000_000
    return rd


def selftest():
    results = []

    def check(name, cond, got):
        results.append((name, bool(cond), got))

    tmp = tempfile.mkdtemp(prefix="m1m2_selftest_")
    try:
        const = lambda v: (lambda t: v)
        # ---------- M2: NPU 피해자 (GPU 30/600 s → NPU 60 s) ----------
        def m2_set(tag, cC1, cC2, cH1, cH2, victim="NPU", heat_ms=4.0, base=0.74):
            runs = {}
            for arm, f, heat_s in (("C1", cC1, 30), ("C2", cC2, 30), ("H1", cH1, 600), ("H2", cH2, 600)):
                rd = _synth_run(tmp, f"{tag}_{arm}", [dict(accelerator="GPU", duty=100, duration_s=heat_s, lat_ms=const(heat_ms)),
                                                       dict(accelerator=victim, duty=100, duration_s=60, lat_ms=const(base * f))], rate=200.0)
                runs[arm] = load_run(rd)
            return runs
        j = m2_judge(m2_set("m2a", 1.0, 1.005, 1.05, 1.05 * 1.005))
        check("M2 H=C×1.05, s_C 0.5 % → 있음", j["decision"] == "결합 있음", f"{j['decision']} s_C={j['s_C']:.4%} gain_low={j['gain_low']:.3%}")
        j = m2_judge(m2_set("m2b", 1.0, 1.0, 1.0, 1.0))
        check("M2 H=C (동일) → 없음", j["decision"] == "결합 없음", f"{j['decision']} s_C={j['s_C']:.4%}")
        j = m2_judge(m2_set("m2b2", 1.0, 1.005, 1.001, 1.004))
        check("M2 H 가 대조 폭 안 (s_C 0.5 %) → 없음", j["decision"] == "결합 없음", f"{j['decision']} s_C={j['s_C']:.4%} gain_high={j['gain_high']:.3%}")
        j = m2_judge(m2_set("m2c", 1.0, 1.005, 1.02, 1.02 * 1.005))
        check("M2 H=C×1.02, s_C 0.5 % → 보류", j["decision"] == "판정 보류", f"{j['decision']} gain_low={j['gain_low']:.3%} thr={j['threshold_yes']:.3%}")
        j = m2_judge(m2_set("m2d", 1.0, 1.0305, 1.05, 1.05 * 1.0305))
        check("M2 H=C×1.05 인데 s_C 3 % → 보류 (2·s_C > 5 %)", j["decision"] == "판정 보류", f"{j['decision']} s_C={j['s_C']:.3%} thr={j['threshold_yes']:.3%}")
        # CPU 피해자: 처음 20 s 중앙이 주 지표 (+5 %). 60 s 안에서 스스로 오르는 CPU 를 흉내: 20 s 뒤 ×1.3
        def cpu_lat(f):
            return lambda t: 4.4 * f * (1.0 if t < 20 else 1.3)
        runs = {}
        for arm, f, heat_s in (("C1", 1.0, 30), ("C2", 1.004, 30), ("H1", 1.06, 600), ("H2", 1.062, 600)):
            runs[arm] = load_run(_synth_run(tmp, f"m2cpu_{arm}", [dict(accelerator="GPU", duty=100, duration_s=heat_s, lat_ms=const(4.0)),
                                                                  dict(accelerator="CPU", duty=100, duration_s=60, lat_ms=cpu_lat(f))], rate=200.0))
        j = m2_judge(runs, metric="first20")
        check("M2 CPU 피해자 first20 ×1.06 (하한 5 %) → 있음", j["decision"] == "결합 있음" and j["floor"] == 0.05, f"{j['decision']} floor={j['floor']} gain_low={j['gain_low']:.3%}")
        j2 = m2_judge(runs, metric="first20", floor=0.03)
        check("M2 같은 자료, 하한 3 % 로 바꿔도 결론 같음 (민감도)", j2["decision"] == "결합 있음", j2["decision"])
        # ---------- M1 ----------
        def m1_run(tag, probe_ratio, ref_fn=None, heat_fn=None):
            pr = list(probe_ratio)
            probe = lambda t: 1.0 * pr[min(int(t // 10), len(pr) - 1)]
            segs = [dict(accelerator="GPU", duty=10, duration_s=60, lat_ms=ref_fn or const(1.0)),
                    dict(accelerator="GPU", duty=100, duration_s=1200, lat_ms=heat_fn or (lambda t: 1.0 if t < 60 else 2.0)),
                    dict(accelerator="GPU", duty=10, duration_s=300, lat_ms=probe)]
            return load_run(_synth_run(tmp, tag, segs, rate=20.0))
        lin = [1.5 - 0.05125 * k for k in range(30)]              # k=8 → 1.09 ≤ 1.10, k=7 → 1.141
        j = m1_judge(m1_run("m1_lin", lin))
        check("M1 선형 감소, k=8 부터 4칸 ≤ ×1.10 → 80 s · 점진형", j["recovery"]["recovery_s"] == 80 and j["shape"] == "점진형",
              f"{j['recovery']} shape={j['shape']} step={j['step']}")
        j = m1_judge(m1_run("m1_cens", [1.2] * 30))
        check("M1 끝까지 ×1.2 → 중도절단", j["recovery"]["recovered"] is False and "미회복" in j["recovery"]["censored"], j["recovery"])
        j = m1_judge(m1_run("m1_step", [1.5] * 5 + [1.05] * 25))
        check("M1 한 칸에서 ×1.5 → ×1.05 → 50 s · 계단형", j["recovery"]["recovery_s"] == 50 and j["shape"] == "계단형", f"{j['recovery']} {j['shape']} {j['step']}")
        j = m1_judge(m1_run("m1_dip", [1.3] * 4 + [1.05, 1.05, 1.2, 1.05] + [1.05] * 22))
        check("M1 4칸 유지 안 되는 일시 하강은 회복 아님 → 70 s", j["recovery"]["recovery_s"] == 70, j["recovery"])
        check("M1 A3: 평탄 기준 → 기준 안정", j["a3_reference_stable"] is True, j["a3_label"])
        j = m1_judge(m1_run("m1_a3", [1.05] * 30, ref_fn=lambda t: 1.0 if t < 30 else 1.2))
        check("M1 A3: 기준 구간 칸이 ±5 % 밖 → 기준 불안정", j["a3_reference_stable"] is False, j["a3_label"])
        check("M1 가열 구간 1-1 진입 60 s (합성 계단)", j["heat_segment"]["onset_s"] == 60, j["heat_segment"])
        # ---------- 엔진 대조 ----------
        rd = _synth_run(tmp, "eng_same", [dict(accelerator="GPU", duty=100, duration_s=600, lat_ms=lambda t: 1.0 if t < 60 else 2.0),
                                           dict(accelerator="NPU", duty=100, duration_s=60, lat_ms=const(0.74))],
                        rate=100.0, power=lambda t: 6.5 if t < 60 else 2.6)
        e = engine_compare(load_run(rd))
        check("엔진 대조: 진입 60 · ×2.0 · 전력 0.4 → 같은 모양", e["verdict"] == "같은 모양", e["values"])
        rd = _synth_run(tmp, "eng_diff", [dict(accelerator="GPU", duty=100, duration_s=600, lat_ms=lambda t: 1.0 if t < 120 else 2.0),
                                           dict(accelerator="NPU", duty=100, duration_s=60, lat_ms=const(0.74))],
                        rate=100.0, power=lambda t: 6.5 if t < 120 else 2.6)
        e = engine_compare(load_run(rd))
        check("엔진 대조: 진입 120 s → 다른 모양", e["verdict"] == "다른 모양" and e["checks"]["onset_s"] is False, e["values"])
        rd = _synth_run(tmp, "eng_nopow", [dict(accelerator="GPU", duty=100, duration_s=600, lat_ms=lambda t: 1.0 if t < 60 else 2.0)], rate=100.0)
        e = engine_compare(load_run(rd))
        check("엔진 대조: 전력 표본 없음 → 보류", e["verdict"].startswith("보류"), e["values"])
        # ---------- 구조 ----------
        rd = _synth_run(tmp, "struct", [dict(accelerator="GPU", duty=100, duration_s=30, lat_ms=const(4.0)),
                                        dict(accelerator="NPU", duty=100, duration_s=60, lat_ms=const(0.74))], rate=100.0)
        good = load_run(rd)
        f = good["jsonl"]
        lines = open(f, encoding="utf-8").read().splitlines()
        keep = [l for l in lines if not ('"segment_start"' in l and '"index": 1' in json.dumps(_detail(json.loads(l)))) ]
        keep = [l for l in keep if not ('"segment_end"' in l and _detail(json.loads(l)).get("index") == 1)]
        bad_dir = os.path.join(tmp, "struct_bad", "runs", "run-bad")
        os.makedirs(os.path.join(bad_dir, "gpu"), exist_ok=True)
        open(os.path.join(bad_dir, "gpu", "x.jsonl"), "w", encoding="utf-8").write("\n".join(keep) + "\n")
        try:
            segment_report(load_run(bad_dir))
            check("구조: 구간 하나 뺀 JSONL → 오류로 멈춤", False, "판정이 나왔다")
        except JudgeError as err:
            check("구조: 구간 하나 뺀 JSONL → 오류로 멈춤", True, str(err))
        drop = [l for l in lines if '"inference_index": 5' not in l and '"inference_index":5' not in l]
        bad2 = os.path.join(tmp, "struct_bad2", "runs", "run-bad2")
        os.makedirs(os.path.join(bad2, "gpu"), exist_ok=True)
        open(os.path.join(bad2, "gpu", "x.jsonl"), "w", encoding="utf-8").write("\n".join(drop) + "\n")
        try:
            segment_report(load_run(bad2))
            check("구조: 추론 한 건 뺀 JSONL → 오류로 멈춤 (건수 불일치)", False, "판정이 나왔다")
        except JudgeError as err:
            check("구조: 추론 한 건 뺀 JSONL → 오류로 멈춤 (건수 불일치)", True, str(err))
        # ---------- 결정성 ----------
        a = dumps(segment_report(load_run(rd)))
        b = dumps(segment_report(load_run(rd)))
        check("결정성: 같은 입력 두 번 = 같은 바이트", a == b, f"{len(a)} B")
        # ---------- extract ----------
        out = extract(good, 0, os.path.join(tmp, "extract_out"))
        ex = [json.loads(l) for l in open(glob.glob(os.path.join(out, "gpu", "*.jsonl"))[0], encoding="utf-8")]
        n_inf = sum(1 for e in ex if e["event"] == "inference")
        check("extract: 구간 0 의 추론만 · load 창 = 구간 창", n_inf == segments_of(good)["segments"][0]["n"]
              and ex[1]["mono_ns"] == segments_of(good)["segments"][0]["start_ns"], f"{n_inf} 건")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    ok = all(c for _, c, _ in results)
    print("| 시험 | 결과 | 값 |\n|---|---|---|")
    for name, c, got in results:
        print(f"| {name} | {'PASS' if c else 'FAIL'} | {str(got)[:160]} |")
    print(f"\nselftest 전체: {'PASS' if ok else 'FAIL'} ({sum(1 for _, c, _ in results if c)}/{len(results)})")
    return 0 if ok else 1


# ============================================================ CLI
def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("selftest")
    a = sub.add_parser("segments"); a.add_argument("run_dir"); a.add_argument("--watch"); a.add_argument("--out")
    a = sub.add_parser("m2")
    for k in ("c1", "h1", "h2", "c2"):
        a.add_argument(f"--{k}", required=True)
    a.add_argument("--victim", type=int, default=1); a.add_argument("--floor", type=float); a.add_argument("--metric", choices=("all", "first20"), default="all")
    a.add_argument("--watch"); a.add_argument("--out")
    a = sub.add_parser("m1"); a.add_argument("run_dir"); a.add_argument("--ref", type=int, default=0); a.add_argument("--heat", type=int, default=1)
    a.add_argument("--probe", type=int, default=2); a.add_argument("--watch"); a.add_argument("--out")
    a = sub.add_parser("engine"); a.add_argument("run_dir"); a.add_argument("--segment", type=int, default=0); a.add_argument("--out")
    a = sub.add_parser("extract"); a.add_argument("run_dir"); a.add_argument("--segment", type=int, required=True); a.add_argument("--out", required=True)
    args = p.parse_args(argv)
    if args.cmd == "selftest":
        return selftest()
    try:
        if args.cmd == "segments":
            res = segment_report(load_run(args.run_dir), load_watch(args.watch))
        elif args.cmd == "m2":
            res = m2_judge({k.upper(): load_run(getattr(args, k)) for k in ("c1", "h1", "h2", "c2")}, args.victim, args.floor, args.metric, load_watch(args.watch))
        elif args.cmd == "m1":
            res = m1_judge(load_run(args.run_dir), args.ref, args.heat, args.probe, load_watch(args.watch))
        elif args.cmd == "engine":
            res = engine_compare(load_run(args.run_dir), args.segment)
        else:
            dst = extract(load_run(args.run_dir), args.segment, args.out)
            print(dst)
            return 0
    except JudgeError as err:
        print(f"JUDGE_ERROR: {err}", file=sys.stderr)
        return 2
    text = dumps(res)
    if getattr(args, "out", None):
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
