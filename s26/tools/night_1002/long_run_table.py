# -*- coding: utf-8 -*-
"""60 s / 10 s tables for one long single-segment run (read-only).
Usage: py long_run_table.py <run_dir> [--watch skin_watch.csv] [--bins10-until 300] [--out f.json]
Prints: ref (first 30 s median), 60 s windows (latency median, ratio, power W, SKIN/AP/BAT/PA at window end, max status, SOC),
10 s bins up to --bins10-until with ratio, last-60 s ratios, last-300 s 60 s medians (range) and 10 s OLS slope (%/min) — description only."""
import sys, os, glob, json, csv, datetime
import numpy as np

run_dir = sys.argv[1]
watch = sys.argv[sys.argv.index("--watch") + 1] if "--watch" in sys.argv else None
until = int(sys.argv[sys.argv.index("--bins10-until") + 1]) if "--bins10-until" in sys.argv else 300
out = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else None

f = glob.glob(os.path.join(run_dir, "gpu", "*.jsonl"))[0]
st = []; lat = []; load0 = load1 = None; meta = None; wall0 = None
with open(f, encoding="utf-8") as fh:
    for line in fh:
        if '"event":"inference"' in line:
            e = json.loads(line); st.append(e["start_mono_ns"]); lat.append(e["latency_ns"])
        elif '"event":"load_start"' in line:
            e = json.loads(line); load0 = e["mono_ns"]; wall0 = e.get("wall_ms")
        elif '"event":"load_end"' in line:
            load1 = json.loads(line)["mono_ns"]
        elif '"event":"run_metadata"' in line:
            meta = json.loads(line)
st = np.array(st, dtype=np.int64); lat = np.array(lat, dtype=float) / 1e6
o = np.argsort(st, kind="stable"); st = st[o]; lat = lat[o]
t = (st - load0) / 1e9
L = (load1 - load0) / 1e9
ref = float(np.median(lat[(t >= 0) & (t < 30)]))

# telemetry
th = []
tp = os.path.join(run_dir, "raw", "thermalservice.jsonl")
for line in open(tp, encoding="utf-8"):
    if not line.strip(): continue
    s = json.loads(line)
    if s.get("parse_status") not in (None, "ok"): continue
    th.append(((s["mono_ns"] - load0) / 1e9, float(s["SKIN"]), float(s["AP"]), float(s["BAT"]), float(s.get("PA") or "nan"), int(s.get("thermal_status") or 0)))
th.sort()
d1 = []
mp = os.path.join(run_dir, "merged", "events.jsonl")
with open(mp, encoding="utf-8") as fh:
    for line in fh:
        if '"source":"d1check"' in line and '"event":"sample"' in line:
            s = json.loads(line)
            if s.get("current_valid") is False or s.get("current_raw") is None or s.get("voltage_mV") is None: continue
            d1.append(((s["mono_ns"] - load0) / 1e9, -float(s["current_raw"]) * float(s["voltage_mV"]) / 1e9, int(s.get("thermal_status") or 0), int(s.get("plugged") or 0)))
d1.sort()
pt = np.array([a for a, *_ in d1]); pw = np.array([b for _, b, *_ in d1])
p0 = float(pw[(pt >= 0) & (pt < 30)].mean()) if len(pt) else None
plugged_nonzero = sum(1 for *_, p in d1 if p != 0)
status_max_d1 = max((s for _, _, s, _ in d1), default=None)

rows = []
if watch and os.path.exists(watch):
    for r in csv.DictReader(open(watch, encoding="utf-8")):
        try: rows.append((datetime.datetime.fromisoformat(r["local_time"]), int(r["battery_level"])))
        except Exception: pass

def soc_at(tsec):
    if not rows or wall0 is None: return None
    tt = datetime.datetime.fromtimestamp((wall0 + tsec * 1000) / 1000.0)
    before = [lvl for ts, lvl in rows if ts <= tt]
    return before[-1] if before else None

def th_at(tsec):
    if not th: return None
    i = int(np.argmin([abs(r[0] - tsec) for r in th])); return th[i]

def win(a, b):
    m = (t >= a) & (t < b); n = int(m.sum())
    med = float(np.median(lat[m])) if n else None
    mp_ = (pt >= a) & (pt < b)
    p = float(pw[mp_].mean()) if mp_.any() else None
    smax = max([s for (x, _, s, _) in d1 if a <= x < b], default=None)
    return n, med, p, smax

table60 = []
for k in range(int(L // 60)):
    a, b = 60 * k, 60 * (k + 1)
    n, med, p, smax = win(a, b)
    r = th_at(b)
    table60.append(dict(t0=a, t1=b, n=n, median_ms=med, ratio=(med / ref) if med else None, power_W=p, power_ratio=(p / p0) if (p and p0) else None,
                        SKIN=r and r[1], AP=r and r[2], BAT=r and r[3], PA=r and r[4], status_max=smax, SOC=soc_at(b)))
bins10 = []
for k in range(int(min(L, until) // 10)):
    a, b = 10 * k, 10 * (k + 1)
    n, med, p, _ = win(a, b)
    r = th_at(b)
    bins10.append(dict(t0=a, n=n, median_ms=med, ratio=(med / ref) if med else None, power_W=p, SKIN=r and r[1], AP=r and r[2]))
last60 = win(L - 60, L)
m60 = [win(L - 300 + 60 * j, L - 300 + 60 * (j + 1))[1] for j in range(5)]
pts = [(10 * k + 5, win(10 * k, 10 * k + 10)[1]) for k in range(int((L - 300) // 10), int(L // 10))]
x = np.array([a for a, _ in pts]); y = np.array([b for _, b in pts])
slope = float(np.polyfit(x, y, 1)[0]) * 60 / float(np.mean(y)) * 100
thermal_status_max_th = max((r[5] for r in th if 0 <= r[0] <= L), default=None)
res = dict(run_dir=run_dir, run_id=meta.get("run_id"), load_s=L, n=int(len(lat)), ref30_ms=ref, p0_W=p0,
           overall_median_ms=float(np.median(lat)), last60=dict(n=last60[0], median_ms=last60[1], ratio=last60[1] / ref, power_W=last60[2], power_ratio=(last60[2] / p0) if (last60[2] and p0) else None),
           last300_60s_medians=m60, last300_range=(max(m60) - min(m60)) / float(np.mean(m60)), last300_slope_pct_per_min=slope,
           thermal_status_max_thermalservice=thermal_status_max_th, thermal_status_max_d1check=status_max_d1, plugged_nonzero_samples=plugged_nonzero,
           d1_samples=len(d1), thermal_samples=len(th), skin_load_start=th_at(0) and th_at(0)[1], skin_load_end=th_at(L) and th_at(L)[1],
           ap_load_end=th_at(L) and th_at(L)[2], bat_load_end=th_at(L) and th_at(L)[3], pilot_battery_pct=meta.get("pilot_battery_pct"),
           soc_start=soc_at(0), soc_end=soc_at(L), table60=table60, bins10=bins10)
text = json.dumps(res, ensure_ascii=False, indent=1, default=lambda v: None if v != v else v)
if out:
    open(out, "w", encoding="utf-8").write(text)
print(f"run {res['run_id']} load {L:.1f} s n={len(lat)} ref30={ref:.4f} ms overall median={res['overall_median_ms']:.4f} p0={p0} W")
print(f"last60: median {last60[1]:.4f} ms ratio {last60[1]/ref:.4f} power {last60[2]} W ratio {res['last60']['power_ratio']}")
print(f"last300 60s medians {['%.4f' % v for v in m60]} range {res['last300_range']:.4%} slope {slope:+.3f} %/min")
print(f"status max: thermalservice {thermal_status_max_th} d1check {status_max_d1}; plugged!=0 samples {plugged_nonzero}/{len(d1)}")
print("t0  t1   n     med_ms  ratio  P_W   P/P0   SKIN  AP    BAT   PA   st SOC")
for r in table60:
    print(f"{r['t0']:4d} {r['t1']:4d} {r['n']:6d} {r['median_ms']:.4f} {r['ratio']:.4f} {r['power_W'] if r['power_W'] is None else round(r['power_W'],2)} {r['power_ratio'] if r['power_ratio'] is None else round(r['power_ratio'],3)} {r['SKIN']} {r['AP']} {r['BAT']} {r['PA']} {r['status_max']} {r['SOC']}")
print("10 s bins:")
for r in bins10:
    print(f"  {r['t0']:4d} n={r['n']:5d} med={r['median_ms']:.4f} ratio={r['ratio']:.4f} P={None if r['power_W'] is None else round(r['power_W'],2)} SKIN={r['SKIN']} AP={r['AP']}")
