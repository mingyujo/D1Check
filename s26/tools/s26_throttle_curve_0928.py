# -*- coding: utf-8 -*-
"""throttle_curve_0928.py — 스로틀곡선_사전등록_0928.md 의 판정기·검사기. results\\ 는 읽기만 한다.

  py throttle_curve_0928.py selftest                 # 1단계: 문턱 근거(잡음) + 양방향 시험 (1-1 · 1-2 · 1-6)
  py throttle_curve_0928.py analyze <result_dir> [--equilibrium] [--duration S] [--duty D] [--threads N] [--out f.json]

1-1 진입   : d1sim/throttle.py:77-89 onset_time_ref 와 같은 정의. ref = load 처음 30 s 추론 전수 지연 중앙,
             t >= 30 s 인 10 s 구간 중앙값이 ref*(1+RISE) 이상이고 뒤따르는 HOLD_S/10 개 구간도 모두 그 이상 -> 그 구간 시작 시각.
1-2 평형   : 마지막 300 s — (가) 60 s 구간 중앙 5개 (max-min)/mean <= EQ_RANGE, (나) 10 s 중앙 OLS |기울기| <= EQ_SLOPE %/min.
1-6 보존   : 부하 길이·duty / 추론 건수 / 텔레메트리 시각 / 자원 증거 / 전원.
"""
import argparse, csv, glob, json, os, re, shutil, sys, tempfile
from collections import Counter
import numpy as np

RES = r"C:\Users\rhoyo\AndroidStudioProjects\D1Check_v4\results"
# ---- 1-1 ----
BIN_S, REF_S, HOLD_S = 10, 30, 30
RISE_ORIG = 0.10                                   # 원 규칙 (P1 스로틀 모형 v0 와 같음)
RISE = {"GPU": 0.10, "NPU": 0.10, "CPU": 0.15}     # 자원별 문턱 — 1단계 잡음 확인 후 확정 (바뀌면 원 규칙과 둘 다 보고)
# CPU 0.15: 9/14 CPU4 d100 5런 처음 30 s 10 s 중앙 RMS 4.912 % → 3×RMS 14.74 % > 10 % (1-1 규칙) → 15 %.
#           단 그 변동은 잡음이 아니라 5/5 런 공통의 단조 상승이다 (사전등록 1-1 에 기록). 원 규칙 10 % 도 항상 같이 보고.
POWER_DROP = 0.15                                  # 보조(기록만): 10 s 평균 전력 <= (1-0.15)*처음 30 s
# ---- 1-2 ----
EQ_WIN_S, EQ_RANGE, EQ_SLOPE = 300, 0.05, 0.5      # EQ_SLOPE 단위 %/min — 60분 규칙으로 원 문턱 고정 (사전등록 1-2)
EQ_RHO = 0.382                                     # 보조(판정 아님): C1-probe r1·r2 300~600 s 10 s 잔차 lag-1 자기상관 평균 (0.255, 0.509)
# ---- 1-6 ----
DUR_TOL_S, DUTY_TOL_PP, GAP_FACTOR = 2.0, 3.0, 3.0
BAND = (29.1, 31.6)
LOGCAT_RE = re.compile(r"^\d\d-\d\d \d\d:\d\d:\d\d\.\d+\s+(\d+)\s+(\d+)\s+([VDIWEF])\s+(\S+)\s*:\s?(.*)$")


# ============================================================ 읽기
def runner_jsonl(run_dir):
    f = sorted(glob.glob(os.path.join(run_dir, "gpu", "*.jsonl")))
    return f


def parse_runner(path):
    """러너 JSONL (기준 자료). 추론 = event 'inference'."""
    R = dict(path=path, lines=0, bad_lines=0, events=Counter(), seqs=[], inf_start=[], inf_lat_ms=[],
             meta=None, fsum=None, load_start=None, load_end=None, run_only=None)
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            R["lines"] += 1
            try:
                e = json.loads(line)
            except ValueError:
                R["bad_lines"] += 1
                continue
            ev = e.get("event")
            R["events"][ev] += 1
            if e.get("sequence") is not None:
                R["seqs"].append(int(e["sequence"]))
            if ev == "inference":
                R["inf_start"].append(int(e["start_mono_ns"]))
                R["inf_lat_ms"].append(float(e["latency_ns"]) / 1e6 if e.get("latency_ns") is not None else float(e["latency_ms"]))
            elif ev == "run_metadata":
                R["meta"] = e
            elif ev == "file_summary":
                R["fsum"] = e
            elif ev == "load_start":
                R["load_start"] = int(e["mono_ns"])
            elif ev == "load_end":
                R["load_end"] = int(e["mono_ns"])
            elif ev == "run_only_summary":
                R["run_only"] = e
    o = np.argsort(np.array(R["inf_start"], dtype=np.int64), kind="stable")
    R["inf_start"] = np.array(R["inf_start"], dtype=np.int64)[o]
    R["inf_lat_ms"] = np.array(R["inf_lat_ms"], dtype=float)[o]
    return R


def parse_merged(run_dir):
    """merged/events.jsonl 에서 d1check 표본(전력·headroom·status·plugged)·thermalservice 표본·추론 건수."""
    p = os.path.join(run_dir, "merged", "events.jsonl")
    M = dict(path=p, exists=os.path.exists(p), d1=[], th=[], inference=0)
    if not M["exists"]:
        return M
    with open(p, encoding="utf-8") as fh:
        for line in fh:
            if '"event":"inference"' in line:
                M["inference"] += 1
                continue
            if '"source":"d1check"' in line and '"event":"sample"' in line:
                M["d1"].append(json.loads(line))
            elif '"source":"thermalservice"' in line and '"event":"sample"' in line:
                M["th"].append(json.loads(line))
    return M


def fnum(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def run_summary_rows(result_dir):
    p = os.path.join(result_dir, "exports-v2", "run_summary.csv")
    return {r["run_id"]: r for r in csv.DictReader(open(p, encoding="utf-8"))} if os.path.exists(p) else {}


# ============================================================ 계열
def load_len_s(R):
    return (R["load_end"] - R["load_start"]) / 1e9


def rel_t(R):
    return (R["inf_start"] - R["load_start"]) / 1e9


def bins10(R):
    """완전한 10 s 구간만 (구간이 부하 창 안에 다 들어가야 함). [(t0, median|None, n)]"""
    t, lat, L = rel_t(R), R["inf_lat_ms"], load_len_s(R)
    n = int(np.floor(L / BIN_S + 1e-9))
    edges = np.searchsorted(t, np.arange(n + 1) * BIN_S, side="left")
    out = []
    for k in range(n):
        seg = lat[edges[k]:edges[k + 1]]
        out.append((k * BIN_S, float(np.median(seg)) if len(seg) else None, int(len(seg))))
    return out


def ref_latency(R):
    t = rel_t(R)
    m = (t >= 0) & (t < REF_S)
    return float(np.median(R["inf_lat_ms"][m])) if m.any() else None


def onset(lat10, ref, rise, hold_s=HOLD_S):
    """d1sim/throttle.py:77-89 와 같은 판정. 반환 (t, 끝경계후보 t)."""
    need = hold_s // BIN_S
    vals = [(t, m) for t, m, _ in lat10]
    thr = ref * (1 + rise)
    edge = None
    for i, (t, m) in enumerate(vals):
        if t < REF_S or m is None:
            continue
        if m >= thr:
            follow = [vals[j][1] for j in range(i + 1, min(i + 1 + need, len(vals)))]
            ok_follow = all(v is not None and v >= thr for v in follow)
            if ok_follow and i + need < len(vals):
                return t, None
            if ok_follow and edge is None:
                edge = t          # 뒤 구간이 모자라 유지 확인 불가 (끝 경계)
    return None, edge


def first_cross(lat10, ref, rise):
    for t, m, _ in lat10:
        if t >= REF_S and m is not None and m >= ref * (1 + rise):
            return t
    return None


def d1_power(M, R):
    """d1check 표본 → (load 기준 t, W). current_raw µA · voltage mV. current_valid 만."""
    out = []
    for s in M["d1"]:
        if s.get("current_valid") is False or s.get("current_raw") is None or s.get("voltage_mV") is None:
            continue
        out.append(((int(s["mono_ns"]) - R["load_start"]) / 1e9, -float(s["current_raw"]) * float(s["voltage_mV"]) / 1e9))
    out.sort()
    return np.array([a for a, _ in out]), np.array([b for _, b in out])


def power10(M, R):
    pt, pw = d1_power(M, R)
    L = load_len_s(R)
    n = int(np.floor(L / BIN_S + 1e-9))
    res = []
    for k in range(n):
        m = (pt >= k * BIN_S) & (pt < (k + 1) * BIN_S)
        res.append((k * BIN_S, float(pw[m].mean()) if m.any() else None, int(m.sum())))
    m0 = (pt >= 0) & (pt < REF_S)
    p0 = float(pw[m0].mean()) if m0.any() else None
    return res, p0


def power_onset(p10, p0, drop=POWER_DROP, hold_s=HOLD_S):
    if p0 is None:
        return None
    need = hold_s // BIN_S
    vals = [(t, p) for t, p, _ in p10]
    thr = p0 * (1 - drop)
    for i, (t, p) in enumerate(vals):
        if t < REF_S or p is None or p > thr:
            continue
        if i + need < len(vals) and all(vals[j][1] is not None and vals[j][1] <= thr for j in range(i + 1, i + 1 + need)):
            return t
    return None


def th_series(M, R):
    rows = []
    for s in M["th"]:
        if s.get("parse_status") not in (None, "ok"):
            continue
        rows.append(((int(s["mono_ns"]) - R["load_start"]) / 1e9, {k: fnum(s.get(k)) for k in ("SKIN", "AP", "PA", "BAT")},
                     s.get("thermal_status")))
    rows.sort(key=lambda r: r[0])
    return rows


def th_at(rows, t):
    if not rows:
        return None
    i = int(np.argmin([abs(r[0] - t) for r in rows]))
    return rows[i]


# ============================================================ 1-2 평형
def equilibrium(R, lat10, win_s=EQ_WIN_S, rng_max=EQ_RANGE, slope_max=EQ_SLOPE):
    L = len(lat10) * BIN_S
    t0 = L - win_s
    if t0 < 0:
        return dict(ok=None, reason="부하가 창보다 짧음")
    t, lat = rel_t(R), R["inf_lat_ms"]
    m60 = []
    for j in range(win_s // 60):
        m = (t >= t0 + 60 * j) & (t < t0 + 60 * (j + 1))
        m60.append(float(np.median(lat[m])) if m.any() else None)
    if any(v is None for v in m60):
        return dict(ok=False, reason="빈 60 s 구간", m60=m60)
    a_val = (max(m60) - min(m60)) / float(np.mean(m60))
    pts = [(tb + BIN_S / 2, m) for tb, m, _ in lat10 if tb >= t0 and m is not None]
    x, y = np.array([p[0] for p in pts]), np.array([p[1] for p in pts])
    coef = np.polyfit(x, y, 1)
    slope = float(coef[0])                                      # ms/s
    b_val = slope * 60 / float(np.mean(y)) * 100                # %/min
    # 보조(판정에 쓰지 않음): AR(1) 보정 기울기 95 % 구간
    resid = y - np.polyval(coef, x)
    se = float(np.sqrt(np.sum(resid ** 2) / (len(y) - 2) / np.sum((x - x.mean()) ** 2)))
    se_ar = se * np.sqrt((1 + EQ_RHO) / (1 - EQ_RHO)) * 60 / float(np.mean(y)) * 100
    return dict(ok=bool(a_val <= rng_max and abs(b_val) <= slope_max), a_range=a_val, b_slope_pct_min=b_val,
                slope_ci95_ar_pct_min=(float(b_val - 1.96 * se_ar), float(b_val + 1.96 * se_ar)),
                a_ok=bool(a_val <= rng_max), b_ok=bool(abs(b_val) <= slope_max), m60=m60, window=(t0, L),
                eq_latency_ms=float(np.median(lat[(t >= t0) & (t < L)])))


def equilibrium_from_lat10(lat10, win_s=EQ_WIN_S, rng_max=EQ_RANGE, slope_max=EQ_SLOPE):
    """합성 시험용: 10 s 중앙만으로 (가)는 60 s 안 10 s 중앙들의 중앙으로 근사."""
    L = len(lat10) * BIN_S
    t0 = L - win_s
    seg = [(tb, m) for tb, m, _ in lat10 if tb >= t0]
    m60 = [float(np.median([m for tb, m in seg if t0 + 60 * j <= tb < t0 + 60 * (j + 1)])) for j in range(win_s // 60)]
    a_val = (max(m60) - min(m60)) / float(np.mean(m60))
    x = np.array([tb + BIN_S / 2 for tb, _ in seg]); y = np.array([m for _, m in seg])
    b_val = float(np.polyfit(x, y, 1)[0]) * 60 / float(np.mean(y)) * 100
    return dict(ok=bool(a_val <= rng_max and abs(b_val) <= slope_max), a_range=a_val, b_slope_pct_min=b_val)


# ============================================================ 1-6 보존·정합
def logcat_evidence(run_dir, resource):
    p = os.path.join(run_dir, "raw", "logcat.txt")
    E = dict(exists=os.path.exists(p), d1gpu_pids=Counter(), lines=[], xnn=[], gpu=[], gpu_kernels=[], dispatch=[], enn=[],
             dispatch_fail=[], other_delegate=[])
    if not E["exists"]:
        return E
    with open(p, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            m = LOGCAT_RE.match(line.rstrip("\n"))
            if not m:
                continue
            pid, lvl, tag, msg = m.group(1), m.group(3), m.group(4), m.group(5)
            if tag == "D1GPU":
                E["d1gpu_pids"][pid] += 1
                continue
            if tag not in ("tflite", "TfLite", "litert"):
                continue
            if "TfLiteXNNPackDelegate" in msg and "Replacing" in msg:
                E["xnn"].append((pid, msg))
            if "TfLiteGpuDelegateV2" in msg and "Replacing" in msg:
                E["gpu"].append((pid, msg))
            if "GPU delegate kernels" in msg:
                E["gpu_kernels"].append((pid, msg))
            if "DispatchDelegate" in msg and "Replacing" in msg:
                E["dispatch"].append((pid, msg))
            if "SetGenAiPerfConfigFromSoc" in msg:
                E["enn"].append((pid, msg))
            if "Failed to create a dispatch delegate kernel" in msg:
                E["dispatch_fail"].append((pid, msg))
    return E


def check_resource(run_dir, R, resource, threads=None):
    E = logcat_evidence(run_dir, resource)
    pid = E["d1gpu_pids"].most_common(1)[0][0] if E["d1gpu_pids"] else None
    notes, ok = [], True
    def need(cond, msg):
        nonlocal ok
        if not cond:
            ok = False
            notes.append(msg)
    if resource == "GPU":
        de = json.load(open(os.path.join(run_dir, "merged", "delegate_evidence.json"), encoding="utf-8"))
        need(de.get("verification") == "verified" and not de.get("failure_or_fallback_evidence"), f"delegate_evidence {de.get('verification')}")
        need(any(p == pid and "31 out of 31" in s for p, s in E["gpu"]), "TfLiteGpuDelegateV2 31/31 줄 (D1GPU PID) 없음")
        need(any(p == pid for p, _ in E["gpu_kernels"]), "Created 1 GPU delegate kernels 줄 (D1GPU PID) 없음")
        need(not E["xnn"] and not E["dispatch"], "다른 delegate 줄 있음")
    elif resource == "CPU":
        need(any(p == pid and "31 out of 31" in s for p, s in E["xnn"]), "TfLiteXNNPackDelegate 31/31 줄 (D1GPU PID) 없음")
        need(not E["gpu"] and not E["dispatch"], "GPU/Dispatch delegate 줄 있음")
        if threads is not None:
            need(R["meta"] is not None and R["meta"].get("cpu_threads") == threads, f"cpu_threads {R['meta'] and R['meta'].get('cpu_threads')} != {threads}")
    elif resource == "NPU":
        pe = os.path.join(run_dir, "merged", "npu_delegate_evidence.json")
        de = json.load(open(pe, encoding="utf-8")) if os.path.exists(pe) else {}
        need(de.get("verification") == "verified", f"npu_delegate_evidence {de.get('verification')}")
        need(de.get("partition_matches_aot_manifest") is True, "partition_matches_aot_manifest 아님")
        need(not de.get("failure_or_fallback_evidence"), "failure_or_fallback_evidence 있음")
        need(any(p == pid for p, _ in E["enn"]), "ENN 로드 줄(SetGenAiPerfConfigFromSoc, D1GPU PID) 없음")
        need(not E["dispatch_fail"], "dispatch 실패 줄 있음")
        # DispatchDelegate 'Replacing' 줄만으로는 판정하지 않는다 (9/24 04:55 진단 로그 766행 — 실패해도 찍힘)
    return dict(ok=ok, pid=pid, notes=notes,
                counts={k: len(E[k]) for k in ("xnn", "gpu", "gpu_kernels", "dispatch", "enn", "dispatch_fail")})


def active_fraction(R, period_s=10.0):
    """duty 주기(10 s)마다 (마지막 추론 끝 - 첫 추론 시작) 합 / 부하 길이. 러너 자기보고와 독립."""
    t = rel_t(R)
    end = t + R["inf_lat_ms"] / 1e3
    L = load_len_s(R)
    n = int(np.ceil(L / period_s - 1e-9))
    tot = 0.0
    idx = np.searchsorted(t, np.arange(n + 1) * period_s, side="left")
    for k in range(n):
        a, b = idx[k], idx[k + 1]
        if b > a:
            tot += min(end[b - 1], (k + 1) * period_s, L) - t[a]
    return 100.0 * tot / L


def conservation(run_dir, row, resource, req_duration=None, req_duty=None, threads=None, R=None, M=None):
    R = R or parse_runner(runner_jsonl(run_dir)[0])
    M = M or parse_merged(run_dir)
    res = {}
    # 1. 부하 길이·duty
    L = load_len_s(R)
    fs = R["fsum"] or {}
    ach = fs.get("achieved_duty_cycle_percent")
    act = active_fraction(R)
    c1 = []
    if req_duration is not None and abs(L - req_duration) > DUR_TOL_S:
        c1.append(f"부하 {L:.3f} s vs 요청 {req_duration}")
    if req_duty is not None:
        if ach is None or abs(float(ach) - req_duty) > DUTY_TOL_PP:
            c1.append(f"러너 achieved_duty {ach} vs 요청 {req_duty}")
        if abs(act - req_duty) > DUTY_TOL_PP:
            c1.append(f"추론 시각으로 계산한 가동 {act:.2f} % vs 요청 {req_duty}")
    res["1_load_duty"] = dict(ok=not c1, load_s=L, runner_achieved_duty=ach, computed_active_pct=act, notes=c1)
    # 2. 추론 건수
    n_jsonl = len(R["inf_start"])
    n_sum = int(row["completed_inference_count"]) if row and row.get("completed_inference_count") not in (None, "") else None
    n_fs_span, n_fs_comp = fs.get("inference_span_count"), fs.get("completed_inference_count")
    n_meta = (R["meta"] or {}).get("completed_inference_count")
    seq_ok = (fs.get("file_event_count") == R["lines"] and fs.get("sequence_first") == 0
              and fs.get("sequence_last") == R["lines"] - 1 and len(set(R["seqs"])) == R["lines"])
    c2 = []
    for name, v in (("run_summary", n_sum), ("file_summary.inference_span_count", n_fs_span),
                    ("file_summary.completed_inference_count", n_fs_comp), ("run_metadata.completed_inference_count", n_meta)):
        if v is None or int(v) != n_jsonl:
            c2.append(f"{name} {v} != JSONL {n_jsonl}")
    if not seq_ok:
        c2.append(f"sequence/줄 수 불일치 (file_event_count {fs.get('file_event_count')} · 줄 {R['lines']} · 고유 seq {len(set(R['seqs']))})")
    if R["bad_lines"]:
        c2.append(f"깨진 줄 {R['bad_lines']}")
    merged_note = None
    if M["exists"] and M["inference"] != n_jsonl:
        merged_note = f"merged 추론 {M['inference']} != JSONL {n_jsonl}"
        if resource != "NPU":
            c2.append(merged_note)        # NPU 는 logcat 사본 결손이 예상됨 → 기록만
    res["2_count"] = dict(ok=not c2, jsonl=n_jsonl, run_summary=n_sum, fs_span=n_fs_span, fs_completed=n_fs_comp,
                          merged=M["inference"] if M["exists"] else None, merged_note=merged_note, notes=c2)
    # 3. 텔레메트리 시각
    c3, gaps = [], {}
    for name, rows in (("d1check", M["d1"]), ("thermalservice", M["th"])):
        ts = np.array([int(s["mono_ns"]) for s in rows], dtype=np.int64)
        if len(ts) < 3:
            c3.append(f"{name} 표본 {len(ts)}")
            continue
        d = np.diff(ts)
        nonmono = int((d <= 0).sum())
        med = float(np.median(d))
        big = np.where(d > GAP_FACTOR * med)[0]
        gaps[name] = dict(n=len(ts), median_interval_s=med / 1e9, nonmonotonic=nonmono, gaps_gt3x=len(big),
                          gap_at_load_s=[round((int(ts[i]) - R["load_start"]) / 1e9, 1) for i in big[:10]],
                          gap_len_s=[round(float(d[i]) / 1e9, 2) for i in big[:10]])
        if nonmono:
            c3.append(f"{name} 비단조 {nonmono}")
    res["3_telemetry"] = dict(ok=not c3, detail=gaps, notes=c3)       # 공백은 개수·위치만 기록 (불일치 사유 아님)
    # 4. 자원 증거
    res["4_resource"] = check_resource(run_dir, R, resource, threads)
    # 5. 전원
    pl = [s.get("plugged") for s in M["d1"]]
    bad = [p for p in pl if p not in (0, "0")]
    res["5_power"] = dict(ok=bool(pl) and not bad, samples=len(pl), plugged_nonzero=len(bad))
    res["ok"] = all(v["ok"] for k, v in res.items() if isinstance(v, dict) and "ok" in v)
    return res, R, M


# ============================================================ 1-3 기록
def record(run_dir, row, resource, R, M, equilibrium_mode=False):
    lat10 = bins10(R)
    ref = ref_latency(R)
    rise = RISE.get(resource, RISE_ORIG)
    on_new, edge_new = onset(lat10, ref, rise)
    on_orig, edge_orig = onset(lat10, ref, RISE_ORIG)
    p10, p0 = power10(M, R)
    pon = power_onset(p10, p0)
    th = th_series(M, R)
    L = len(lat10) * BIN_S
    t, lat = rel_t(R), R["inf_lat_ms"]
    out = dict(run_id=os.path.basename(run_dir), slot=row.get("slot_id") if row else None, resource=resource,
               load_s=load_len_s(R), n_inf=int(len(t)), ref_ms=ref, rise=rise,
               onset_orig_s=on_orig, onset_orig_edge_candidate_s=edge_orig,
               onset_s=on_new, onset_edge_candidate_s=edge_new,
               first_cross_orig_s=first_cross(lat10, ref, RISE_ORIG), power_p0_w=p0, power_onset_aux_s=pon)
    tent = on_orig if on_orig is not None else None
    e = th_at(th, tent) if tent is not None else None
    out["onset_temps"] = dict(t=e[0], **e[1]) if e else None
    s0 = th_at(th, 0.0)
    out["load_start_temps"] = dict(t=s0[0], **s0[1]) if s0 else None
    out["load_start_skin_in_band"] = (s0 is not None and s0[1]["SKIN"] is not None and BAND[0] <= s0[1]["SKIN"] <= BAND[1])
    inload = [r for r in th if 0 <= r[0] <= load_len_s(R)]
    out["end_temps"] = dict(t=inload[-1][0], **inload[-1][1]) if inload else None
    # status (둘 다) — 최대값과 바뀐 시각
    st = []
    for s in M["d1"]:
        st.append(("d1check", (int(s["mono_ns"]) - R["load_start"]) / 1e9, s.get("thermal_status")))
    for tt, _, s in th:
        st.append(("thermalservice", tt, s))
    stat = {}
    for src in ("d1check", "thermalservice"):
        seq = sorted([(tt, int(v)) for sname, tt, v in st if sname == src and v not in (None, "")])
        changes = [(round(seq[i][0], 1), seq[i - 1][1], seq[i][1]) for i in range(1, len(seq)) if seq[i][1] != seq[i - 1][1]]
        stat[src] = dict(max=max([v for _, v in seq]) if seq else None, changes=changes[:20])
    out["thermal_status"] = stat
    # headroom 60 s 격자 (load 안)
    hr = sorted([((int(s["mono_ns"]) - R["load_start"]) / 1e9, s.get("headroom_now"), s.get("headroom_60s")) for s in M["d1"]])
    grid = []
    for g in range(0, int(L) + 1, 60):
        if not hr:
            break
        i = int(np.argmin([abs(h[0] - g) for h in hr]))
        grid.append((g, hr[i][1], hr[i][2]))
    hl = [h for h in hr if 0 <= h[0] <= L]
    out["headroom"] = dict(grid=grid, now_min=min([h[1] for h in hl if h[1] is not None], default=None),
                           now_max=max([h[1] for h in hl if h[1] is not None], default=None),
                           h60_min=min([h[2] for h in hl if h[2] is not None], default=None),
                           h60_max=max([h[2] for h in hl if h[2] is not None], default=None))
    # 배율
    pt, pw = d1_power(M, R)
    def win(a, b):
        m = (t >= a) & (t < b)
        mp = (pt >= a) & (pt < b)
        return (float(np.median(lat[m])) if m.any() else None, float(pw[mp].mean()) if mp.any() else None)
    l60, pw60 = win(L - 60, L)
    out["end60"] = dict(lat_ms=l60, lat_ratio=l60 / ref if l60 and ref else None, power_w=pw60,
                        power_ratio=pw60 / p0 if pw60 and p0 else None)
    if equilibrium_mode:
        eq = equilibrium(R, lat10)
        l300, pw300 = win(L - EQ_WIN_S, L)
        eq.update(lat_ratio=l300 / ref if l300 and ref else None, power_w=pw300, power_ratio=pw300 / p0 if pw300 and p0 else None)
        out["equilibrium"] = eq
    # 끝 60 s 기울기 (SKIN ℃/min, 전력 W/min)
    tt = np.array([r[0] for r in inload]); sk = np.array([r[1]["SKIN"] for r in inload], dtype=float)
    mm = tt >= L - 60
    out["end60_skin_slope_c_per_min"] = float(np.polyfit(tt[mm], sk[mm], 1)[0] * 60) if mm.sum() >= 5 else None
    mp = (pt >= L - 60) & (pt < L)
    out["end60_power_slope_w_per_min"] = float(np.polyfit(pt[mp], pw[mp], 1)[0] * 60) if mp.sum() >= 5 else None
    # 60 s 표
    tab = []
    for g in range(0, int(L), 60):
        lm, pm = win(g, g + 60)
        e2 = th_at(inload, g + 60)
        tab.append(dict(t=g, lat_ms=lm, power_w=pm, n=int(((t >= g) & (t < g + 60)).sum()),
                        SKIN=e2[1]["SKIN"] if e2 else None, AP=e2[1]["AP"] if e2 else None, PA=e2[1]["PA"] if e2 else None,
                        BAT=e2[1]["BAT"] if e2 else None))
    out["table60"] = tab
    out["lat10"] = [(a, b, c) for a, b, c in lat10]
    out["power10"] = p10
    return out


# ============================================================ analyze
def analyze(result_dir, equilibrium_mode=False, req_duration=None, req_duty=None, threads=None, out=None):
    rows = run_summary_rows(result_dir)
    runs = sorted(d for d in glob.glob(os.path.join(result_dir, "runs", "*")) if os.path.isdir(d))
    allres = []
    for rd in runs:
        rid = os.path.basename(rd)
        row = rows.get(rid, {})
        fj = runner_jsonl(rd)
        if len(fj) != 1:
            print(f"## {rid}: 러너 JSONL {len(fj)}개 — 분석 불가")
            allres.append(dict(run_id=rid, error=f"runner jsonl {len(fj)}"))
            continue
        R = parse_runner(fj[0])
        resource = (R["meta"] or {}).get("resource") or row.get("resource")
        cons, R, M = conservation(rd, row, resource, req_duration, req_duty, threads)
        rec = record(rd, row, resource, R, M, equilibrium_mode)
        rec["conservation"] = cons
        rec["run_summary"] = {k: row.get(k) for k in ("slot_id", "slot_status", "validation_status", "termination_reason",
                                                      "completed_inference_count", "actual_load_duration_s", "achieved_duty_cycle_percent")}
        rec["runner_termination"] = (R["meta"] or {}).get("termination_reason")
        allres.append(rec)
        print_run(rec)
    if out:
        with open(out, "w", encoding="utf-8") as fh:
            json.dump(allres, fh, ensure_ascii=False, indent=1, default=str)
        print(f"\n(JSON: {out})")
    return allres


def f(x, n=3):
    return "—" if x is None else (f"{x:.{n}f}" if isinstance(x, float) else str(x))


def print_run(r):
    c = r["conservation"]
    print(f"\n## {r['slot']} · run {r['run_id']} · {r['resource']}")
    print(f"종료: runner {r['runner_termination']} · run_summary {r['run_summary']}")
    print(f"보존 검사 전체: {'OK' if c['ok'] else '보존 불일치'}")
    for k in ("1_load_duty", "2_count", "3_telemetry", "4_resource", "5_power"):
        v = c[k]
        extra = {kk: vv for kk, vv in v.items() if kk not in ("ok",)}
        print(f"  {k}: {'OK' if v['ok'] else 'FAIL'} {json.dumps(extra, ensure_ascii=False, default=str)}")
    print(f"부하 {r['load_s']:.3f} s · 추론 {r['n_inf']} · ref(0~30 s) {f(r['ref_ms'],4)} ms")
    print(f"진입(원 규칙 +{RISE_ORIG:.0%}·{HOLD_S} s): {f(r['onset_orig_s'])} s  (끝 경계 후보 {f(r['onset_orig_edge_candidate_s'])}) · "
          f"처음 +10 % 넘은 구간 {f(r['first_cross_orig_s'])} s")
    if r["rise"] != RISE_ORIG:
        print(f"진입(새 규칙 +{r['rise']:.0%}): {f(r['onset_s'])} s (끝 경계 후보 {f(r['onset_edge_candidate_s'])})")
    print(f"보조 전력 −{POWER_DROP:.0%} 진입(기록만): {f(r['power_onset_aux_s'])} s · P0 {f(r['power_p0_w'])} W")
    print(f"진입 시 온도: {r['onset_temps']} · load_start {r['load_start_temps']} (밴드 {'안' if r['load_start_skin_in_band'] else '밖'}) · 끝 {r['end_temps']}")
    print(f"status: {r['thermal_status']}")
    print(f"headroom: {r['headroom']}")
    e = r["end60"]
    print(f"끝 60 s: 지연 {f(e['lat_ms'],4)} ms (×{f(e['lat_ratio'])}) · 전력 {f(e['power_w'])} W (×{f(e['power_ratio'])}) · "
          f"SKIN 기울기 {f(r['end60_skin_slope_c_per_min'])} ℃/min · 전력 기울기 {f(r['end60_power_slope_w_per_min'])} W/min")
    if "equilibrium" in r:
        q = r["equilibrium"]
        print(f"평형(1-2): {q.get('ok')} · (가) {f(q.get('a_range'),4)} (≤{EQ_RANGE}) · (나) {f(q.get('b_slope_pct_min'),3)} %/min (|·|≤{EQ_SLOPE}) · "
              f"보조 AR(1) 기울기 95 % 구간 {[round(v,3) for v in q.get('slope_ci95_ar_pct_min',())]} %/min · "
              f"60 s 중앙 {[round(v,4) for v in q.get('m60',[]) if v]} · 평형 지연 {f(q.get('eq_latency_ms'),4)} ms (×{f(q.get('lat_ratio'))}) · "
              f"전력 {f(q.get('power_w'))} W (×{f(q.get('power_ratio'))})")
    print("| t (s) | 지연 중앙 ms | 전력 W | n | SKIN | AP | PA | BAT |\n|---:|---:|---:|---:|---:|---:|---:|---:|")
    for x in r["table60"]:
        print(f"| {x['t']}-{x['t']+60} | {f(x['lat_ms'],3)} | {f(x['power_w'],2)} | {x['n']} | {f(x['SKIN'],1)} | {f(x['AP'],1)} | {f(x['PA'],1)} | {f(x['BAT'],1)} |")


# ============================================================ selftest (1단계)
def runs_of(exp, resource, duty, threads=None):
    rows = list(csv.DictReader(open(os.path.join(RES, exp, "exports-v2", "run_summary.csv"), encoding="utf-8")))
    return [(os.path.join(RES, exp, "runs", r["run_id"]), r) for r in rows
            if r["resource"] == resource and r["requested_duty_cycle_percent"] == str(duty)
            and (threads is None or r["cpu_threads"] == str(threads)) and r["validation_status"] == "valid"]


def synth_lat10(duration, level, sigma_bin, seed, base=7.2):
    rng = np.random.default_rng(seed)
    n = int(duration // BIN_S)
    eps = rng.normal(0.0, sigma_bin, n)
    return [(k * BIN_S, base * level(k * BIN_S + BIN_S / 2) * float(np.exp(eps[k])), 1000) for k in range(n)]


def detrended_sd(lat10, a, b):
    pts = [(t + BIN_S / 2, m) for t, m, _ in lat10 if a <= t < b and m is not None]
    x, y = np.array([p[0] for p in pts]), np.array([p[1] for p in pts])
    fit = np.polyval(np.polyfit(x, y, 1), x)
    return float(np.std((y - fit) / fit, ddof=2)), float(np.sum((x - x.mean()) ** 2))


def selftest():
    ok_all = True
    def rep(name, cond, detail=""):
        nonlocal ok_all
        ok_all &= bool(cond)
        print(f"- [{'PASS' if cond else 'FAIL'}] {name} {detail}")

    c1p = os.path.join(RES, "S26_C1probe_gpu600_0927")
    c1rows = run_summary_rows(c1p)
    c1 = []
    for rd in sorted(glob.glob(os.path.join(c1p, "runs", "*"))):
        R = parse_runner(runner_jsonl(rd)[0])
        c1.append((rd, c1rows[os.path.basename(rd)], R))
    c1.sort(key=lambda x: x[1]["slot_id"])

    print("# 1-1 문턱 근거 — 처음 30 s 의 10 s 구간 중앙 잡음 (자원별)\n")
    sets = {
        "GPU (C1-probe r1·r2)": [(rd, R) for rd, _, R in c1],
        "GPU d100 60 s (9/14 strict, 보조)": [(rd, parse_runner(runner_jsonl(rd)[0])) for rd, _ in runs_of("S26_formal_strict", "GPU", 100)],
        "GPU d50 60 s (9/14 strict, 보조 — M3 칸)": [(rd, parse_runner(runner_jsonl(rd)[0])) for rd, _ in runs_of("S26_formal_strict", "GPU", 50)],
        "NPU (9/25 formal d100)": [(rd, parse_runner(runner_jsonl(rd)[0])) for rd, _ in runs_of("S26_NPU_formal_0925b", "NPU", 100)],
        "CPU4 (9/14 strict d100 4스레드)": [(rd, parse_runner(runner_jsonl(rd)[0])) for rd, _ in runs_of("S26_formal_strict", "CPU", 100, 4)],
    }
    noise = {}
    real60 = {}
    for name, rs in sets.items():
        devs, mx = [], 0.0
        for rd, R in rs:
            ref = ref_latency(R)
            l10 = bins10(R)
            d = [m / ref - 1 for t, m, _ in l10 if t < REF_S and m is not None]
            devs += d
            mx = max(mx, max(abs(x) for x in d))
        sd = float(np.sqrt(np.mean(np.square(devs))))
        noise[name] = (sd, mx, len(rs))
        print(f"- {name}: 런 {len(rs)} · 10 s 중앙/30 s 중앙 − 1 의 RMS **{sd*100:.3f} %** · 최대 |·| {mx*100:.3f} % · "
              f"3×RMS = {3*sd*100:.3f} % → 10 % {'≥' if 0.10 >= 3*sd else '<'} 3×잡음, 3×최대 = {3*mx*100:.3f} %")
        real60[name] = rs

    print("\n# 1-1 판정기 양방향 시험\n")
    print("## 잡아야 할 것 — C1-probe r1·r2")
    for rd, row, R in c1:
        l10, ref = bins10(R), ref_latency(R)
        on, edge = onset(l10, ref, RISE_ORIG)
        fc = first_cross(l10, ref, RISE_ORIG)
        around = [(t, round(m / ref, 4)) for t, m, _ in l10 if 30 <= t <= 90]
        rep(f"{row['slot_id']} 진입 잡힘", on is not None, f"진입 {on} s · 처음 +10 % 구간 {fc} s · 같은가 {on == fc} · ref {ref:.4f} ms · 30~90 s 배율 {around}")
        rep(f"{row['slot_id']} 진입 = 처음 +10 % 넘는 구간 (C1probe_결과 §4: 60 s 구간 4.06/4.25 ms)", on == fc == 60)
    print("\n## 걸러야 할 것 ① — 평탄 + 20 s 짜리 +15 % 급등 (합성, seed 20개)")
    sd_gpu = noise["GPU (C1-probe r1·r2)"][0]
    for spike_s, expect in ((20, None), (30, None), (40, 110)):
        hits = []
        for seed in range(20):
            lvl = (lambda s: (lambda t: 1.15 if 100 <= t < 100 + s else 1.0))(spike_s)
            l10 = synth_lat10(600, lvl, max(sd_gpu, 0.002), seed, base=3.65)
            ref = float(np.median([m for t, m, _ in l10 if t < REF_S]))
            hits.append(onset(l10, ref, RISE_ORIG)[0])
        if spike_s == 20:
            rep("20 s 급등 → 진입 0/20", all(h is None for h in hits), f"결과 {Counter(hits)}")
        else:
            print(f"  (경계 기록) {spike_s} s 급등 → {Counter(hits)} — 규칙상 진입 구간 + 뒤 30 s = 40 s 이상이어야 진입")
    print("\n## 걸러야 할 것 ② — 자원별 실제 60 s 런")
    for name, res_key in (("GPU d100 60 s (9/14 strict, 보조)", "GPU"), ("NPU (9/25 formal d100)", "NPU"), ("CPU4 (9/14 strict d100 4스레드)", "CPU")):
        for rise in sorted({RISE_ORIG, RISE[res_key]}):
            ons, mxr, series = [], 0.0, []
            for rd, R in real60[name]:
                l10, ref = bins10(R), ref_latency(R)
                ons.append(onset(l10, ref, rise)[0])
                mxr = max(mxr, max(m / ref for t, m, _ in l10 if m is not None))
                series.append([round(m / ref, 3) for t, m, _ in l10])
            rep(f"{name} (+{rise:.0%}): 진입 0건", all(o is None for o in ons), "(구조적으로 보장 — 60 s 런은 t≥30 구간 뒤 3칸이 없다)")
            rep(f"{name} (+{rise:.0%}): 문턱 넘는 10 s 구간 0개 (실질 확인)", mxr < 1 + rise,
                f"최대 배율 {mxr:.4f}" + ("" if mxr < 1 + rise else f" · 10 s 배율 계열 {series}"))
    print("\n## 추가 — 합성 계단 (양성·음성 대조)")
    for step, expect in ((1.12, 100), (1.08, None)):
        hits = []
        for seed in range(20):
            l10 = synth_lat10(600, (lambda s: (lambda t: s if t >= 100 else 1.0))(step), max(sd_gpu, 0.002), seed, base=3.65)
            ref = float(np.median([m for t, m, _ in l10 if t < REF_S]))
            hits.append(onset(l10, ref, RISE_ORIG)[0])
        rep(f"계단 ×{step} @100 s → {'진입 100 s' if expect else '진입 없음'} 20/20", all(h == expect for h in hits), f"결과 {Counter(hits)}")

    print("\n# 1-2 평형 — 문턱 근거 (C1-probe r1·r2, 300~600 s 10 s 중앙 추세 제거 잡음)\n")
    sds, sxx = [], None
    for rd, row, R in c1:
        s, sxx_ = detrended_sd(bins10(R), 300, 600)
        sds.append(s)
        sxx = sxx_
        print(f"- {row['slot_id']}: 추세 제거 상대 SD σ10 = {s*100:.3f} %")
    s10 = float(np.sqrt(np.mean(np.square(sds))))
    se_slope = s10 / np.sqrt(sxx) * 60 * 100        # %/min
    sd60 = s10 / np.sqrt(6)                          # 60 s 중앙 ≈ 10 s 중앙 6개 (근사)
    print(f"- 합동 σ10 {s10*100:.3f} % · 30점(10 s 간격) OLS 기울기 표준오차 ≈ {se_slope:.3f} %/min → X = {EQ_SLOPE} %/min 은 {EQ_SLOPE/se_slope:.1f} SE")
    print(f"- 60 s 중앙 잡음 ≈ σ10/√6 = {sd60*100:.3f} % → 순수 잡음에서 5개 범위 기대 ≈ 2.33σ = {2.33*sd60*100:.3f} % (문턱 5 % 는 그 {0.05/(2.33*sd60):.1f} 배)")
    print(f"- 참고: 추세 제거 전 r1·r2 300~600 s 기울기 = " + ", ".join(
        f"{equilibrium(R, bins10(R))['b_slope_pct_min']:.2f} %/min" for _, _, R in c1))
    print("\n# 1-2 판정기 양방향 시험\n")
    for rd, row, R in c1:
        eq = equilibrium(R, bins10(R))
        rep(f"{row['slot_id']} 300~600 s → 평형 아님", eq["ok"] is False,
            f"(가) {eq['a_range']*100:.2f} % (나) {eq['b_slope_pct_min']:.3f} %/min · 60 s 중앙 {[round(v,3) for v in eq['m60']]}")
    sig = max(s10, 0.002)
    for label, slope_pct, expect in (("평탄", 0.0, True), ("기울기 X/2", EQ_SLOPE / 2, True), ("기울기 2X", 2 * EQ_SLOPE, False)):
        res = []
        for seed in range(20):
            lvl = (lambda sp: (lambda t: 1 + sp / 100 * (t - 1000) / 60))(slope_pct)
            l10 = synth_lat10(1300, lvl, sig, 1000 + seed)
            res.append(equilibrium_from_lat10(l10)["ok"])
        k = sum(1 for r in res if r == expect)
        rep(f"{label} (1300 s, σ10={sig*100:.2f} %) → {'평형' if expect else '평형 아님'}", k >= 19, f"{k}/20 기대대로")
    # 자기상관 잡음(AR(1), 실측 σ10·ρ)에서 원 규칙의 검정력과 r1·r2 의 위치
    rng = np.random.default_rng(20260928)
    sims = []
    for _ in range(4000):
        e = np.empty(30); e[0] = rng.normal(0, s10)
        for i in range(1, 30):
            e[i] = EQ_RHO * e[i - 1] + rng.normal(0, s10 * np.sqrt(1 - EQ_RHO ** 2))
        l10 = [(1000 + k * BIN_S, 7.2 * float(np.exp(e[k])), 1000) for k in range(30)]
        q = equilibrium_from_lat10([(k * BIN_S, 7.2, 1000) for k in range(100)] + l10)
        sims.append((q["a_range"], abs(q["b_slope_pct_min"]), q["ok"]))
    A = np.array([s[0] for s in sims]); B = np.array([s[1] for s in sims])
    print(f"- AR(1) 평탄 잡음 (σ10 {s10*100:.2f} %, ρ {EQ_RHO}) 4000회: 원 규칙(5 %·{EQ_SLOPE} %/min) 평형 비율 {np.mean([s[2] for s in sims]):.3f} · "
          f"(가) 95 백분위 {np.percentile(A,95)*100:.2f} % · |(나)| 95 백분위 {np.percentile(B,95):.3f} %/min")
    for rd, row, R in c1:
        eq = equilibrium(R, bins10(R))
        pa = float(np.mean(A >= eq["a_range"])); pb = float(np.mean(B >= abs(eq["b_slope_pct_min"])))
        print(f"- {row['slot_id']} 300~600 s: (가) {eq['a_range']*100:.2f} % → 평탄 잡음에서 이 이상 나올 확률 {pa:.3f} · "
              f"(나) {eq['b_slope_pct_min']:.3f} %/min → {pb:.3f} · AR 보정 95 % 구간 {[round(v,2) for v in eq['slope_ci95_ar_pct_min']]}")
    # (가)만으로는 통과하는 표류를 (나)가 잡는가
    l10 = synth_lat10(1300, lambda t: 1 + 1.0 / 100 * (t - 1000) / 60, 0.0, 0)
    q = equilibrium_from_lat10(l10)
    rep("분당 1 % 표류: (가)만이면 통과, (나)에서 걸림", q["a_range"] <= EQ_RANGE and not q["ok"], f"(가) {q['a_range']*100:.2f} % (나) {q['b_slope_pct_min']:.3f}")

    print("\n# 1-6 보존 검사기 양방향 시험\n")
    rd, row, R = c1[0]
    cons, _, M = conservation(rd, row, "GPU", 600, 100, None, R=R)
    rep("통과해야 할 것: C1-probe r1 원본 → 전부 OK", cons["ok"], json.dumps({k: v["ok"] for k, v in cons.items() if isinstance(v, dict)}, ensure_ascii=False))
    for rd2, row2, R2 in c1[1:]:
        cons2, _, _ = conservation(rd2, row2, "GPU", 600, 100, None, R=R2)
        rep("통과해야 할 것: C1-probe r2 원본 → 전부 OK", cons2["ok"])
    for rd3, row3 in runs_of("S26_formal_strict", "CPU", 100, 4)[:1]:
        cons3, _, _ = conservation(rd3, row3, "CPU", 60, 100, 4)
        rep("통과해야 할 것: 9/14 CPU4 d100 1런 → 전부 OK (스레드 4)", cons3["ok"], json.dumps(cons3["4_resource"], ensure_ascii=False))
        cons3b, _, _ = conservation(rd3, row3, "CPU", 60, 100, 2)
        rep("걸러야 할 것: 같은 CPU4 런을 스레드 2 로 요구 → 4번 FAIL", not cons3b["4_resource"]["ok"])
    for rd4, row4 in runs_of("S26_C4_npu_runonly_0927", "NPU", 100)[:1]:
        cons4, _, _ = conservation(rd4, row4, "NPU", 60, 100)
        rep("통과해야 할 것: 0927 C4 NPU d100 1런 → 전부 OK", cons4["ok"], json.dumps(cons4["4_resource"], ensure_ascii=False))
    for rd5, row5 in runs_of("S26_formal_strict", "GPU", 50)[:1]:
        cons5, _, _ = conservation(rd5, row5, "GPU", 60, 50)
        rep("통과해야 할 것: 9/14 GPU d50 1런 → 가동 비율 ~50 % OK", cons5["1_load_duty"]["ok"], json.dumps(cons5["1_load_duty"], ensure_ascii=False))
        cons5b, _, _ = conservation(rd5, row5, "GPU", 60, 100)
        rep("걸러야 할 것: 같은 d50 런을 d100 으로 요구 → 1번 FAIL", not cons5b["1_load_duty"]["ok"])
    tmp = tempfile.mkdtemp(prefix="tc0928_")
    try:
        # 추론 한 건을 뺀 JSONL
        src = runner_jsonl(rd)[0]
        d_a = os.path.join(tmp, "drop1"); os.makedirs(os.path.join(d_a, "gpu")); shutil.copytree(os.path.join(rd, "merged"), os.path.join(d_a, "merged"))
        shutil.copytree(os.path.join(rd, "raw"), os.path.join(d_a, "raw"))
        dropped = False
        with open(src, encoding="utf-8") as fi, open(os.path.join(d_a, "gpu", os.path.basename(src)), "w", encoding="utf-8") as fo:
            for line in fi:
                if not dropped and '"event":"inference"' in line and '"inference_index":5000,' in line:
                    dropped = True
                    continue
                fo.write(line)
        ca, _, _ = conservation(d_a, row, "GPU", 600, 100, None)
        rep("걸러야 할 것: 추론 한 건을 뺀 JSONL → 2번 FAIL", dropped and not ca["2_count"]["ok"] and not ca["ok"], "; ".join(ca["2_count"]["notes"]))
        # plugged 1 표본 하나
        d_b = os.path.join(tmp, "plug1"); os.makedirs(os.path.join(d_b, "merged")); shutil.copytree(os.path.join(rd, "gpu"), os.path.join(d_b, "gpu"))
        shutil.copytree(os.path.join(rd, "raw"), os.path.join(d_b, "raw"))
        shutil.copy(os.path.join(rd, "merged", "delegate_evidence.json"), os.path.join(d_b, "merged"))
        done = False
        with open(os.path.join(rd, "merged", "events.jsonl"), encoding="utf-8") as fi, \
                open(os.path.join(d_b, "merged", "events.jsonl"), "w", encoding="utf-8") as fo:
            for line in fi:
                if not done and '"source":"d1check"' in line and '"event":"sample"' in line and '"tick":300,' in line:
                    line = line.replace('"plugged":0', '"plugged":1'); done = True
                fo.write(line)
        cb, _, _ = conservation(d_b, row, "GPU", 600, 100, None)
        rep("걸러야 할 것: plugged 1 표본 하나 → 5번 FAIL", done and not cb["5_power"]["ok"] and not cb["ok"], json.dumps(cb["5_power"]))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"\n# selftest 전체: {'PASS' if ok_all else 'FAIL'}")
    return ok_all


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("selftest")
    a = sp.add_parser("analyze")
    a.add_argument("result_dir")
    a.add_argument("--equilibrium", action="store_true")
    a.add_argument("--duration", type=float)
    a.add_argument("--duty", type=float)
    a.add_argument("--threads", type=int)
    a.add_argument("--out")
    ns = ap.parse_args()
    if ns.cmd == "selftest":
        sys.exit(0 if selftest() else 1)
    analyze(ns.result_dir, ns.equilibrium, ns.duration, ns.duty, ns.threads, ns.out)
