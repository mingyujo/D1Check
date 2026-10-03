# -*- coding: utf-8 -*-
"""night1003_judge_effblock.py — EffNet 개발 블록 (8런, 거울 순서) 분석. `EffNet블록_사전등록_v1.md` §3·§4 글자 그대로.
단일 런(비연쇄) 결과 폴더를 읽는다 (results\\S26_EffB1_<nn>_<cpu|gpu><duty>_1003). results\\ 는 읽기만. 같은 입력 두 번 = 같은 바이트.

  py night1003_judge_effblock.py selftest
  py night1003_judge_effblock.py run <result_dir> [--no-evidence] [--out f.json]
  py night1003_judge_effblock.py block <result_dir> [<result_dir> ...] [--no-evidence] [--gate-log csv] [--out f.json]

규칙:
  런별: latency_median_ms (write+run+read, inference.latency_ns 전수 중앙) · run_only_median_ms (run_only_summary.detail.median_ns — 블록의 주 지연) · 추론 수
        · SKIN 상승 (load_end HAL SKIN − load_start HAL SKIN) · 잠정 전력 W (d1check 표본 평균, 단위 가정 · 비율 참고만) · 자원 증거 (compiled_model_evidence evaluate --rule cpu|gpu)
  셀별: 두 런 값 · 평균 · 두 런 차 (표류 지표, |a−b|/mean)
  모델×duty 상호작용 (CPU 만): EffNet CPU run_only d50/d100 (셀 평균 비) 가 MobileNet CompiledModel CPU (C5, 0927 — 5런 중앙 run_only) 비 0.88217 의 ±2 % 안
        → "상호작용 없음 — d25·d75 는 MobileNet 모양으로 보간 가능", 밖 → "상호작용 있음 — 2수준만으로는 부족". GPU 는 판정 안 함 (MobileNet CompiledModel GPU d50 자료 없음)
  자원 증거 규칙 v1: X < Y 면 규칙을 풀지 말고 "규칙 밖(X/Y)". GPU X/Y < 0.9 또는 폴백 줄 → 그 런은 GPU 자료 아님
"""
import argparse, csv, glob, json, os, re, shutil, subprocess, sys, tempfile

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = r"C:\Users\rhoyo\AndroidStudioProjects\D1Check_v4"
EVIDENCE = os.path.join(REPO, "tools", "compiled_model_evidence.py")
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ND = 6
REF_S = 30
BIN_S = 10
MOBILENET_C5_RUN_ONLY_D50_D100 = 0.88217     # [P C5 run_only_summary 5런 중앙: d50 3.8593 / d100 4.3748 ms — EffNet블록_사전등록_v1 §4]
MOBILENET_C5_WRR_D50_D100 = 0.88095          # [P C5 inference_latency.median_ms 5런 중앙: d50 3.8825 / d100 4.4072 — 보조]
INTERACTION_TOL = 0.02                        # ±2 %
GPU_PARTIAL_MIN = 0.9
CELL_OF = {("CPU", 50): "C50", ("CPU", 100): "C100", ("GPU", 50): "G50", ("GPU", 100): "G100"}
MIRROR_ORDER = ["C50", "C100", "G50", "G100", "G100", "G50", "C100", "C50"]


class JudgeError(RuntimeError):
    pass


def _r(x):
    if isinstance(x, float):
        return round(x, ND)
    if isinstance(x, dict):
        return {k: _r(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_r(v) for v in x]
    if isinstance(x, np.floating):
        return round(float(x), ND)
    if isinstance(x, np.integer):
        return int(x)
    return x


def dumps(obj):
    return json.dumps(_r(obj), ensure_ascii=False, sort_keys=True, indent=1)


def _detail(e):
    d = e.get("detail")
    if isinstance(d, dict):
        return d
    try:
        return json.loads(d) if isinstance(d, str) else {}
    except ValueError:
        return {}


def parse_folder(result_dir):
    m = re.search(r"S26_EffB(\d+)_(\d+)_(cpu|gpu)(\d+)_(\d{4})", os.path.basename(os.path.normpath(result_dir)))
    if not m:
        return dict(block=None, order=None, accel_folder=None, duty_folder=None, date=None)
    return dict(block=int(m.group(1)), order=int(m.group(2)), accel_folder=m.group(3).upper(), duty_folder=int(m.group(4)), date=m.group(5))


def load_single(result_dir):
    mp = os.path.join(result_dir, "experiment_manifest.json")
    if not os.path.exists(mp):
        raise JudgeError(f"manifest 없음: {result_dir}")
    man = json.load(open(mp, encoding="utf-8"))
    runs = man.get("runs") or []
    if len(runs) != 1:
        raise JudgeError(f"슬롯이 {len(runs)}개 (1 기대): {result_dir}")
    slot = runs[0]
    rid = slot.get("run_id")
    rd = os.path.join(result_dir, "runs", rid) if rid else None
    files = sorted(glob.glob(os.path.join(rd, "gpu", "*.jsonl"))) if rd else []
    if len(files) != 1:
        raise JudgeError(f"러너 JSONL 이 {len(files)}개 — {rd}")
    ev = []
    bad = 0
    for line in open(files[0], encoding="utf-8"):
        if not line.strip():
            continue
        try:
            ev.append(json.loads(line))
        except ValueError:
            bad += 1
    meta = next((e for e in ev if e.get("event") == "run_metadata"), None)
    if meta is None:
        raise JudgeError("run_metadata 없음")
    if meta.get("chain_mode"):
        raise JudgeError("연쇄 런 — 이 판정기는 단일 런용")
    ls = [e for e in ev if e.get("event") == "load_start"]; le = [e for e in ev if e.get("event") == "load_end"]
    if len(ls) != 1 or len(le) != 1:
        raise JudgeError(f"load_start {len(ls)} / load_end {len(le)}")
    inf = [e for e in ev if e.get("event") == "inference"]
    ros = [e for e in ev if e.get("event") == "run_only_summary"]
    th = []
    tp = os.path.join(rd, "raw", "thermalservice.jsonl")
    if os.path.exists(tp):
        for line in open(tp, encoding="utf-8"):
            try:
                s = json.loads(line)
            except ValueError:
                continue
            if s.get("parse_status") in (None, "ok") and isinstance(s.get("mono_ns"), int):
                th.append(s)
    th.sort(key=lambda s: s["mono_ns"])
    d1 = []
    mpth = os.path.join(rd, "merged", "events.jsonl")
    if os.path.exists(mpth):
        for line in open(mpth, encoding="utf-8"):
            if '"source":"d1check"' in line and '"event":"sample"' in line:
                d1.append(json.loads(line))
    return dict(result_dir=result_dir, run_dir=rd, run_id=rid, manifest=man, slot=slot, meta=meta, load_start=ls[0], load_end=le[0],
                inferences=inf, run_only=(_detail(ros[0]) if ros else None), run_only_count=len(ros), thermal=th, d1=d1, bad_lines=bad)


def _th_at(th, mono):
    if not th:
        return None
    i = int(np.argmin([abs(s["mono_ns"] - mono) for s in th]))
    s = th[i]
    out = {k: (float(s[k]) if s.get(k) not in (None, "") else None) for k in ("SKIN", "AP", "BAT", "PA")}
    out["thermal_status"] = int(s["thermal_status"]) if s.get("thermal_status") not in (None, "") else None
    out["dt_s"] = (s["mono_ns"] - mono) / 1e9
    return out


def evidence(run_dir, rule):
    """compiled_model_evidence.py evaluate --rule cpu|gpu (읽기 전용 외부 도구). 판정 PASS/FAIL + 교체 줄 X/Y (있으면)."""
    try:
        p = subprocess.run([sys.executable, "-X", "utf8", EVIDENCE, "evaluate", "--rule", rule, run_dir], capture_output=True, text=True, timeout=600, encoding="utf-8")
    except Exception as e:  # noqa: BLE001
        return dict(rule=rule, verdict="ERROR", error=repr(e))
    out = dict(rule=rule, returncode=p.returncode)
    try:
        j = json.loads(p.stdout)
        j = j[0] if isinstance(j, list) and j else j
        out.update(verdict=j.get("verdict"), rule_name=j.get("rule"), failed_conditions=j.get("failed_conditions"), conditions=j.get("conditions"),
                   replacement_lines=(j.get("details") or {}).get("replacement_lines"), failure_lines=(j.get("details") or {}).get("failure_lines"),
                   runner_pids=(j.get("details") or {}).get("runner_pids"))
    except ValueError:
        out.update(verdict="UNPARSED", stdout=p.stdout[:800], stderr=p.stderr[:400])
    # 교체 줄 X/Y 발췌 (raw logcat, 러너 PID 줄만)
    xy = []
    lp = os.path.join(run_dir, "raw", "logcat.txt")
    pids = set(out.get("runner_pids") or [])
    if os.path.exists(lp):
        with open(lp, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if "Replacing" in line and "out of" in line:
                    m = re.search(r"Replacing (\d+) out of (\d+) node\(s\) with delegate \(([^)]*)\)", line)
                    if m:
                        pid_ok = (not pids) or any(f" {pid} " in line or f"({pid})" in line or f" {pid}:" in line for pid in pids)
                        xy.append(dict(X=int(m.group(1)), Y=int(m.group(2)), delegate=m.group(3), runner_pid_match=pid_ok))
    out["replacements"] = xy[:8]
    full = [d for d in xy if d["X"] == d["Y"]]
    part = [d for d in xy if d["X"] < d["Y"]]
    if part:
        out["xy_note"] = "규칙 밖(X/Y): " + ", ".join(f"{d['X']}/{d['Y']} {d['delegate']}" for d in part[:4])
    elif full:
        out["xy_note"] = "전 그래프 교체: " + ", ".join(f"{d['X']}/{d['Y']} {d['delegate']}" for d in full[:4])
    else:
        out["xy_note"] = "교체 줄 없음 (발췌 범위)"
    if rule == "gpu":
        bad = [d for d in xy if d["Y"] and d["X"] / d["Y"] < GPU_PARTIAL_MIN]
        out["gpu_data_ok"] = (out.get("verdict") == "PASS") and not bad and not (out.get("failure_lines") or [])
        out["gpu_note"] = "GPU 자료" if out["gpu_data_ok"] else "GPU 자료 아님 (X/Y < 0.9 · 폴백 줄 · 규칙 FAIL 중 하나)"
    return out


def run_report(result_dir, with_evidence=True, gate_rows=None):
    R = load_single(result_dir)
    meta, ls, le = R["meta"], R["load_start"], R["load_end"]
    a, b = int(ls["mono_ns"]), int(le["mono_ns"])
    inf = [e for e in R["inferences"] if a <= int(e["start_mono_ns"]) and int(e["mono_ns"]) <= b]
    lat = np.array([float(e["latency_ns"]) / 1e6 for e in inf]) if inf else np.array([])
    rel = np.array([(int(e["start_mono_ns"]) - a) / 1e9 for e in inf]) if inf else np.array([])
    ref30 = float(np.median(lat[rel < REF_S])) if (len(lat) and (rel < REF_S).any()) else None
    L = (b - a) / 1e9
    bins = []
    for k in range(int(np.floor(L / BIN_S + 1e-9))):
        m = (rel >= k * BIN_S) & (rel < (k + 1) * BIN_S)
        med = float(np.median(lat[m])) if m.any() else None
        bins.append(dict(t0=k * BIN_S, median_ms=med, n=int(m.sum()), ratio=(med / ref30) if (med and ref30) else None))
    ths, the = _th_at(R["thermal"], a), _th_at(R["thermal"], b)
    st_max = None
    inload = [s for s in R["thermal"] if a <= s["mono_ns"] <= b and s.get("thermal_status") not in (None, "")]
    if inload:
        st_max = max(int(s["thermal_status"]) for s in inload)
    pw = []
    for s in R["d1"]:
        if s.get("current_valid") is False or s.get("current_raw") is None or s.get("voltage_mV") is None:
            continue
        if a <= int(s["mono_ns"]) <= b:
            pw.append(-float(s["current_raw"]) * float(s["voltage_mV"]) / 1e9)
    ro = R["run_only"] or {}
    acc = meta.get("npu_accelerator_requested")
    duty = meta.get("requested_duty_cycle_percent")
    cell = CELL_OF.get((acc, duty))
    fo = parse_folder(result_dir)
    val = R["slot"].get("validation") or {}
    out = dict(
        result_dir=os.path.basename(os.path.normpath(result_dir)), run_id=R["run_id"], folder=fo, cell=cell, order=fo["order"],
        accelerator_requested=acc, resource_label=meta.get("npu_timed_resource_label"), duty=duty, achieved_duty=meta.get("achieved_duty_cycle_percent"),
        gpu_precision_requested=((meta.get("compiled_model_options") or {}).get("gpu_options") or {}).get("precision") if isinstance(meta.get("compiled_model_options"), dict) else meta.get("npu_gpu_precision"),
        model_sha256=meta.get("model_sha256"), timed_input_spec=meta.get("npu_timed_input_spec"), litert_version=meta.get("litert_version"),
        slot_status=R["slot"].get("status"), attempts=R["slot"].get("attempts"), valid=val.get("valid"), failed_checks=val.get("failed_checks"),
        termination_reason=meta.get("termination_reason"), completed_inference_count=meta.get("completed_inference_count"),
        n_inferences_in_load=len(inf), load_s=L, bad_jsonl_lines=R["bad_lines"], pilot_battery_pct=meta.get("pilot_battery_pct"),
        latency_median_ms=(float(np.median(lat)) if len(lat) else None), latency_p95_ms=(float(np.percentile(lat, 95)) if len(lat) else None),
        run_only=dict(present=bool(ro), median_ms=(ro.get("median_ns") / 1e6 if ro.get("median_ns") else None), count=ro.get("count"), missing=ro.get("missing"),
                      p95_ms=(ro.get("p95_ns") / 1e6 if ro.get("p95_ns") else None), span=ro.get("span")),
        ref30_ms=ref30, bins10=bins, max_bin_ratio=(max((bb["ratio"] for bb in bins if bb["ratio"] is not None), default=None)),
        thermal=dict(load_start=ths, load_end=the, skin_rise=((the["SKIN"] - ths["SKIN"]) if (ths and the and ths["SKIN"] is not None and the["SKIN"] is not None) else None),
                     ap_rise=((the["AP"] - ths["AP"]) if (ths and the and ths["AP"] is not None and the["AP"] is not None) else None), status_max_in_load=st_max, samples=len(R["thermal"])),
        power=dict(mean_W_in_load=(float(np.mean(pw)) if pw else None), samples=len(pw), note="단위 가정 · 절대 정확도 미인증 — 비율 참고만"),
        start_skin_in_band_29_1_31_6=(None if not ths or ths["SKIN"] is None else bool(29.1 <= ths["SKIN"] <= 31.6)),
    )
    if gate_rows:
        g = gate_rows.get(fo["order"])
        out["gate"] = g
    if with_evidence and acc in ("CPU", "GPU"):
        out["evidence"] = evidence(R["run_dir"], acc.lower())
    return out


def block_report(result_dirs, with_evidence=True, gate_rows=None):
    runs = []
    errors = []
    for d in result_dirs:
        try:
            runs.append(run_report(d, with_evidence, gate_rows))
        except JudgeError as e:
            errors.append(dict(result_dir=d, error=str(e)))
    runs.sort(key=lambda r: (r["order"] if r["order"] is not None else 99))
    cells = {}
    for r in runs:
        if r["cell"]:
            cells.setdefault(r["cell"], []).append(r)
    cell_tab = {}
    for c, rr in cells.items():
        ro = [x["run_only"]["median_ms"] for x in rr if x["run_only"]["median_ms"] is not None]
        wr = [x["latency_median_ms"] for x in rr if x["latency_median_ms"] is not None]
        sk = [x["thermal"]["skin_rise"] for x in rr if x["thermal"]["skin_rise"] is not None]
        pw = [x["power"]["mean_W_in_load"] for x in rr if x["power"]["mean_W_in_load"] is not None]
        def agg(v):
            if not v:
                return dict(values=[], mean=None, diff=None, diff_rel=None, n=0)
            return dict(values=v, mean=float(np.mean(v)), diff=(abs(v[0] - v[1]) if len(v) == 2 else None),
                        diff_rel=((abs(v[0] - v[1]) / float(np.mean(v))) if (len(v) == 2 and np.mean(v)) else None), n=len(v))
        cell_tab[c] = dict(orders=[x["order"] for x in rr], run_ids=[x["run_id"] for x in rr], valid=[x["valid"] for x in rr],
                           run_only_median_ms=agg(ro), latency_median_ms=agg(wr), skin_rise=agg(sk), power_W=agg(pw),
                           evidence_verdicts=[(x.get("evidence") or {}).get("verdict") for x in rr],
                           gpu_data_ok=[(x.get("evidence") or {}).get("gpu_data_ok") for x in rr] if c.startswith("G") else None)
    # 상호작용 (CPU 만)
    def ratio(cA, cB, key):
        a = cell_tab.get(cA, {}).get(key, {}).get("mean"); b = cell_tab.get(cB, {}).get(key, {}).get("mean")
        return (a / b) if (a and b) else None
    r_cpu = ratio("C50", "C100", "run_only_median_ms")
    r_cpu_wrr = ratio("C50", "C100", "latency_median_ms")
    lo, hi = MOBILENET_C5_RUN_ONLY_D50_D100 * (1 - INTERACTION_TOL), MOBILENET_C5_RUN_ONLY_D50_D100 * (1 + INTERACTION_TOL)
    if r_cpu is None:
        inter = "판정 불가 (C50 또는 C100 셀 결측)"
    elif lo <= r_cpu <= hi:
        inter = "상호작용 없음 — d25·d75 는 MobileNet 모양으로 보간 가능"
    else:
        inter = "상호작용 있음 — 2수준만으로는 부족"
    r_gpu = ratio("G50", "G100", "run_only_median_ms")
    missing = [c for c in ("C50", "C100", "G50", "G100") if len(cells.get(c, [])) < 2]
    return dict(
        rule="EffNet블록_사전등록_v1 §3·§4: 셀별 두 런·평균·차 · CPU d50/d100 run_only 비 vs MobileNet C5 0.88217 ±2 % · GPU 판정 안 함",
        design=dict(mirror_order=MIRROR_ORDER, observed_order=[r["cell"] for r in runs], order_matches_mirror=([r["cell"] for r in runs] == MIRROR_ORDER)),
        runs=runs, errors=errors, cells=cell_tab, cells_incomplete=missing,
        interaction_cpu=dict(ratio_run_only_d50_d100=r_cpu, ratio_wrr_d50_d100=r_cpu_wrr, mobilenet_c5_run_only=MOBILENET_C5_RUN_ONLY_D50_D100,
                             mobilenet_c5_wrr=MOBILENET_C5_WRR_D50_D100, window=[lo, hi], verdict=inter),
        interaction_gpu=dict(ratio_run_only_d50_d100=r_gpu, verdict="판정 안 함 (MobileNet CompiledModel GPU d50 자료 없음 — Interpreter 9/14 비는 엔진 다름, 참고만)"),
        note="개발 블록 — 확인 블록(10/4, 자원 순서 바꾼 거울) 전에는 결론 아님. CI·검정력 주장 없음. 선형 표류만 산술 상쇄, 비선형·잔열은 남는다",
    )


def load_gate(path):
    """s26_start_gate CSV → {order: row} (label 끝의 2자리 순번으로)."""
    rows = {}
    if not path or not os.path.exists(path):
        return rows
    for r in csv.DictReader(open(path, encoding="utf-8")):
        m = re.search(r"06_(\d+)_", r.get("label", ""))
        if m and r.get("pass") == "True":
            rows[int(m.group(1))] = dict(local_time=r["local_time"], waited_s=int(r["waited_s"]), SKIN=float(r["SKIN"]), AP=float(r["AP"]), BAT=float(r["BAT"]), soc=int(r["soc"]))
    return rows


# ============================================================ selftest
def _synth_single(root, name, accel, duty, dur, lat_ms, run_only_ms, rate=200.0, skin0=30.0, skin_rise=3.0, power_w=3.0):
    rd = os.path.join(root, name, "runs", "run-" + name)
    for d in ("gpu", "raw", "merged"):
        os.makedirs(os.path.join(rd, d), exist_ok=True)
    t0 = 1_000_000_000_000
    ev = []
    def push(e):
        e = dict(e); e["sequence"] = len(ev); e.setdefault("wall_ms", 1_790_000_000_000 + (e["mono_ns"] - t0) // 1_000_000); ev.append(e)
    push(dict(event="run_metadata", mono_ns=t0, run_id="run-" + name, resource="NPU", npu_accelerator_requested=accel,
              npu_timed_resource_label=f"{accel.lower()}_compiled_model", requested_duty_cycle_percent=duty, achieved_duty_cycle_percent=float(duty),
              termination_reason="duration_complete", pilot_battery_pct=70, model_sha256="6c7a" + "0" * 60, npu_timed_input_spec="lcg-rgb-127-128",
              litert_version="2.2.0", requested_duration_s=dur))
    a = t0 + 1_000_000_000
    push(dict(event="load_start", mono_ns=a, start_mono_ns=a, latency_ns=0))
    tt = a; n = 0; step = int(1e9 / rate)
    while tt + int(lat_ms * 1e6) < a + int(dur * 1e9):
        rel = (tt - a) / 1e9
        if duty < 100 and (rel % 10.0) >= duty / 10.0:
            tt = a + int((np.floor(rel / 10.0) + 1) * 10.0 * 1e9); continue
        push(dict(event="inference", start_mono_ns=tt, mono_ns=tt + int(lat_ms * 1e6), latency_ns=int(lat_ms * 1e6), inference_index=n)); n += 1
        tt += max(step, int(lat_ms * 1e6))
    b = a + int(dur * 1e9)
    push(dict(event="run_only_summary", mono_ns=b, start_mono_ns=b, latency_ns=0, detail=json.dumps(dict(span="run_only", count=n, missing=0, median_ns=int(run_only_ms * 1e6), p95_ns=int(run_only_ms * 1.1e6), min_ns=1, max_ns=2, mean_ns=int(run_only_ms * 1e6)))))
    push(dict(event="load_end", mono_ns=b, start_mono_ns=b, latency_ns=0))
    ev[0]["completed_inference_count"] = n
    push(dict(event="file_summary", mono_ns=b, inference_span_count=n, completed_inference_count=n))
    with open(os.path.join(rd, "gpu", f"gpu-events-run-{name}.jsonl"), "w", encoding="utf-8") as fh:
        for e in ev:
            fh.write(json.dumps(e, separators=(",", ":")) + "\n")
    with open(os.path.join(rd, "raw", "thermalservice.jsonl"), "w", encoding="utf-8") as fh:
        m = a - 30_000_000_000
        while m <= b + 5_000_000_000:
            sk = skin0 + skin_rise * min(1.0, max(0.0, (m - a) / 1e9) / dur)
            fh.write(json.dumps(dict(source="thermalservice", event="sample", mono_ns=m, parse_status="ok", SKIN=f"{sk:.1f}", AP=f"{sk + 1:.1f}", BAT=f"{sk - 2:.1f}", PA=f"{sk:.1f}", thermal_status="0")) + "\n")
            m += 1_000_000_000
    with open(os.path.join(rd, "merged", "events.jsonl"), "w", encoding="utf-8") as fh:
        m = a - 30_000_000_000
        while m <= b + 5_000_000_000:
            fh.write(json.dumps(dict(source="d1check", event="sample", mono_ns=m, current_raw=-int(power_w / 4.0 * 1e6), current_valid=True, voltage_mV=4000, plugged=0), separators=(",", ":")) + "\n")
            m += 1_000_000_000
    man = dict(runs=[dict(run_id="run-" + name, status="completed", attempts=1, duty_cycle_percent=duty, validation=dict(valid=True, failed_checks=[]))])
    json.dump(man, open(os.path.join(root, name, "experiment_manifest.json"), "w", encoding="utf-8"))
    return os.path.join(root, name)


def selftest():
    res = []
    def check(name, cond, got):
        res.append((name, bool(cond), got))
    tmp = tempfile.mkdtemp(prefix="effblock_selftest_")
    try:
        def mk(i, accel, duty, lat, ro, tag=""):
            return _synth_single(tmp, f"S26_EffB1_{i:02d}_{accel.lower()}{duty}_1003{tag}", accel, duty, 60, lat, ro)
        # 상호작용 없음: C50/C100 run_only = 0.882
        dirs = [mk(1, "CPU", 50, 6.0, 5.90), mk(2, "CPU", 100, 6.8, 6.69), mk(3, "GPU", 50, 2.0, 1.9), mk(4, "GPU", 100, 2.1, 2.0),
                mk(5, "GPU", 100, 2.12, 2.02), mk(6, "GPU", 50, 2.02, 1.92), mk(7, "CPU", 100, 6.82, 6.71), mk(8, "CPU", 50, 6.02, 5.92)]
        B = block_report(dirs, with_evidence=False)
        r = B["interaction_cpu"]["ratio_run_only_d50_d100"]
        check("8런 파싱 · 거울 순서 일치", len(B["runs"]) == 8 and B["design"]["order_matches_mirror"], B["design"]["observed_order"])
        check("CPU d50/d100 run_only 0.882 (±2 % 안) → 상호작용 없음", B["interaction_cpu"]["verdict"].startswith("상호작용 없음") and abs(r - 0.8821) < 0.001, r)
        check("셀별 두 런 · 차 (표류)", B["cells"]["C50"]["run_only_median_ms"]["n"] == 2 and B["cells"]["C50"]["run_only_median_ms"]["diff"] is not None, B["cells"]["C50"]["run_only_median_ms"])
        check("GPU 판정 안 함 (비만 기록)", B["interaction_gpu"]["verdict"].startswith("판정 안 함") and B["interaction_gpu"]["ratio_run_only_d50_d100"] is not None, B["interaction_gpu"])
        check("런별 run_only · write+run+read 둘 다", B["runs"][0]["run_only"]["median_ms"] == 5.9 and abs(B["runs"][0]["latency_median_ms"] - 6.0) < 1e-6, (B["runs"][0]["run_only"], B["runs"][0]["latency_median_ms"]))
        check("SKIN 상승 3.0 · 전력 3.0 W (합성)", abs(B["runs"][0]["thermal"]["skin_rise"] - 3.0) < 0.15 and abs(B["runs"][0]["power"]["mean_W_in_load"] - 3.0) < 1e-6, (B["runs"][0]["thermal"]["skin_rise"], B["runs"][0]["power"]["mean_W_in_load"]))
        # 상호작용 있음: 0.95
        dirs2 = [mk(1, "CPU", 50, 6.5, 6.4, "b"), mk(2, "CPU", 100, 6.8, 6.69, "b"), mk(7, "CPU", 100, 6.82, 6.71, "b"), mk(8, "CPU", 50, 6.52, 6.42, "b")]
        B2 = block_report(dirs2, with_evidence=False)
        check("CPU d50/d100 0.956 (밖) → 상호작용 있음", B2["interaction_cpu"]["verdict"].startswith("상호작용 있음"), B2["interaction_cpu"]["ratio_run_only_d50_d100"])
        check("GPU 셀 결측 → cells_incomplete 에 G50·G100", set(B2["cells_incomplete"]) >= {"G50", "G100"}, B2["cells_incomplete"])
        # 결측 런 1개 → 셀 n=1, diff None · 판정은 평균으로
        B3 = block_report(dirs2[:3], with_evidence=False)
        check("한 셀에 런 1개 → diff None · 상호작용 판정은 낸다", B3["cells"]["C50"]["run_only_median_ms"]["n"] == 1 and B3["cells"]["C50"]["run_only_median_ms"]["diff"] is None and B3["interaction_cpu"]["ratio_run_only_d50_d100"] is not None, B3["cells"]["C50"]["run_only_median_ms"])
        B4 = block_report([dirs2[1], dirs2[2]], with_evidence=False)
        check("C50 전부 결측 → 판정 불가", B4["interaction_cpu"]["verdict"].startswith("판정 불가"), B4["interaction_cpu"]["verdict"])
        # 구조: 연쇄 런 거부 · manifest 없음
        bad = mk(9, "CPU", 50, 6.0, 5.9, "chain")
        f = glob.glob(os.path.join(bad, "runs", "*", "gpu", "*.jsonl"))[0]
        lines = open(f, encoding="utf-8").read().splitlines()
        e0 = json.loads(lines[0]); e0["chain_mode"] = True; lines[0] = json.dumps(e0)
        open(f, "w", encoding="utf-8").write("\n".join(lines) + "\n")
        try:
            run_report(bad, False); check("연쇄 런 → 오류로 멈춤", False, "판정이 나왔다")
        except JudgeError as err:
            check("연쇄 런 → 오류로 멈춤", True, str(err))
        try:
            run_report(os.path.join(tmp, "nope"), False); check("manifest 없음 → 오류", False, "판정")
        except JudgeError as err:
            check("manifest 없음 → 오류", True, str(err))
        a1 = dumps(run_report(mk(1, "CPU", 50, 6.0, 5.9, "detA"), False)); a2 = dumps(run_report(mk(1, "CPU", 50, 6.0, 5.9, "detB"), False))
        check("결정성: 같은 입력 두 번 = 같은 바이트 (이름 제외)", a1.replace("detA", "X") == a2.replace("detB", "X"), f"{len(a1)} B")
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
    a = sub.add_parser("run"); a.add_argument("result_dir"); a.add_argument("--no-evidence", action="store_true"); a.add_argument("--gate-log"); a.add_argument("--out")
    a = sub.add_parser("block"); a.add_argument("result_dirs", nargs="+"); a.add_argument("--no-evidence", action="store_true"); a.add_argument("--gate-log"); a.add_argument("--out")
    args = p.parse_args(argv)
    if args.cmd == "selftest":
        return selftest()
    try:
        gate = load_gate(getattr(args, "gate_log", None))
        if args.cmd == "run":
            res = run_report(args.result_dir, not args.no_evidence, gate)
        else:
            res = block_report(args.result_dirs, not args.no_evidence, gate)
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
