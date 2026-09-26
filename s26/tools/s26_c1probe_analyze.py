"""C1-probe analysis (C1probe_사전등록_v1.md §4-5). Read-only.
Usage: py c1probe_analyze.py <result_dir>
Per run: SKIN/AP/BAT at 60 s grid of load_relative_s, 600 s rise (last load - first load sample, same as
s26_thermal_fit.load_rise), end slope OLS on [580,600] s, first thermal_status>=1, latency median per 60 s bin."""
import csv, glob, json, os, statistics as st, sys
import numpy as np

THRESH_SLOW, DT_MAX, SLOPE_MAX = 7.98, 6.98, 0.2
d = sys.argv[1]
rows = [r for r in csv.DictReader(open(os.path.join(d, "exports-v2", "thermal_timeseries.csv"), encoding="utf-8"))
        if r["parse_status"] == "ok"]
runs = {}
for r in rows:
    runs.setdefault(r["run_id"], []).append(r)
verdicts = []
for rid, rr in runs.items():
    slot = rr[0]["slot_id"]
    load = [r for r in rr if r["phase"] == "load"]
    t = np.array([float(r["load_relative_s"]) for r in load])
    sk = np.array([float(r["SKIN"]) for r in load])
    print(f"\n## {slot}  run {rid}")
    print(f"load samples {len(load)}, t {t.min():.1f}..{t.max():.1f} s")
    print("| t (s) | SKIN | AP | BAT | PA | status |\n|---:|---:|---:|---:|---:|---:|")
    for g in range(0, 601, 60):
        i = int(np.argmin(np.abs(t - g)))
        r = load[i]
        print(f"| {g} | {r['SKIN']} | {r['AP']} | {r['BAT']} | {r['PA']} | {r['thermal_status']} |")
    rise = sk[-1] - sk[0]
    m = (t >= 580) & (t <= 600)
    slope = float(np.polyfit(t[m], sk[m], 1)[0]) * 60 if m.sum() >= 5 else float("nan")
    peak_i = int(np.argmax(sk))
    thr = [r for r in load if r["thermal_status"] not in ("", "0")]
    first_thr = f"{float(thr[0]['load_relative_s']):.1f} s (SKIN {thr[0]['SKIN']})" if thr else "none (status 0 throughout load)"
    print(f"\nload_start SKIN {sk[0]:.1f} (band 29.1-31.6: {'in' if 29.1 <= sk[0] <= 31.6 else 'OUT'}), "
          f"600 s rise {rise:.2f} C, end slope [580,600] {slope:+.3f} C/min, "
          f"peak SKIN {sk.max():.1f} at {t[peak_i]:.0f} s, first status>=1: {first_thr}")
    for s in ("AP", "BAT", "PA"):
        y = np.array([float(r[s]) for r in load])
        print(f"  {s}: start {y[0]:.1f} peak {y.max():.1f} at {t[int(np.argmax(y))]:.0f} s end {y[-1]:.1f}")
    # latency per 60 s bin from runner events
    ev = glob.glob(os.path.join(d, "runs", rid, "gpu", "*.jsonl"))
    if ev:
        lat = []
        for line in open(ev[0], encoding="utf-8"):
            if '"event":"inference"' in line:
                e = json.loads(line)
                lat.append((e["start_mono_ns"], e["latency_ms"]))
        t0 = lat[0][0]
        bins = {}
        for s0, l in lat:
            bins.setdefault(int((s0 - t0) / 60e9), []).append(l)
        print("  latency median ms per 60 s bin: " +
              ", ".join(f"{k*60}-{k*60+60}:{st.median(v):.3f}(n={len(v)})" for k, v in sorted(bins.items()) if k < 10))
    verdicts.append((rise, slope))
    cls = ("slow" if rise > THRESH_SLOW else
           "fit" if rise <= DT_MAX and abs(slope) <= SLOPE_MAX else "hold")
    print(f"  per-run class: {cls}")
cls = ["slow" if r > THRESH_SLOW else "fit" if r <= DT_MAX and abs(s) <= SLOPE_MAX else "hold" for r, s in verdicts]
final = ("느린 모드 있음" if all(c == "slow" for c in cls) else
         "1차 fit 이 맞음" if all(c == "fit" for c in cls) else "판단 보류")
print(f"\n### 판정 (§5): {final}   per-run {cls}")
