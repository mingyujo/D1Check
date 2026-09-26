"""One script for S26 thermal fits (tau, R^2, MAE) and end-of-load slopes. Read-only.

Usage (from D1Check_v4 root):
  py s26/tools/s26_thermal_fit.py results/S26_formal_strict results/S26_NPU_formal_0925b -o <out.csv>

Per run and sensor (AP, SKIN, BAT, PA):
  heat : load phase, t = load_relative_s in [0, 60], T0 + dT * (1 - exp(-t / tau))
  cool : cooling phase, t = phase_elapsed_s,          Tinf + dT * exp(-t / tau)
  tau bounds [1, 3000] s. R^2 = 1 - SSres/SStot, MAE in degC (no percentage error).
  slope_end : OLS slope of temperature on load_relative_s in [40, 60] s, degC/min
  reach60   : 1 - exp(-60 / tau_heat), fitted fraction of dT reached at 60 s
Prints condition medians (5 repetitions) per resource x threads x duty.
"""
import argparse, csv, math, os, statistics as st
from collections import defaultdict
import numpy as np
from scipy.optimize import curve_fit

SENSORS = ("AP", "SKIN", "BAT", "PA")


def heat(t, t0, dt, tau):
    return t0 + dt * (1.0 - np.exp(-t / tau))


def cool(t, tinf, dt, tau):
    return tinf + dt * np.exp(-t / tau)


def fit(fn, t, y, p0):
    t = np.asarray(t, float); y = np.asarray(y, float)
    if len(t) < 5 or np.ptp(y) == 0:
        return None
    try:
        p, _ = curve_fit(fn, t, y, p0=p0, bounds=([-np.inf, -np.inf, 1.0], [np.inf, np.inf, 3000.0]), maxfev=20000)
    except Exception:
        return None
    r = y - fn(t, *p)
    sst = float(np.sum((y - y.mean()) ** 2))
    return dict(tau=float(p[2]), dT=float(p[1]), r2=1.0 - float(np.sum(r ** 2)) / sst if sst > 0 else float("nan"),
                mae=float(np.mean(np.abs(r))))


def slope_per_min(t, y):
    t = np.asarray(t, float); y = np.asarray(y, float)
    if len(t) < 5:
        return None
    return float(np.polyfit(t, y, 1)[0]) * 60.0


def load_runs(result_dir):
    path = os.path.join(result_dir, "exports-v2", "thermal_timeseries.csv")
    runs = defaultdict(list)
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("parse_status") != "ok":
                continue
            runs[row["run_id"]].append(row)
    return runs


def analyse(result_dir):
    out = []
    for rid, rows in load_runs(result_dir).items():
        r0 = rows[0]
        key = dict(run_id=rid, slot_id=r0["slot_id"], resource=r0["resource"], cpu_threads=r0["cpu_threads"],
                   duty=int(float(r0["requested_duty_cycle_percent"])))
        load = [r for r in rows if r["phase"] == "load"]
        coolr = [r for r in rows if r["phase"] == "cooling"]
        for s in SENSORS:
            lt = [float(r["load_relative_s"]) for r in load if r[s] != ""]
            ly = [float(r[s]) for r in load if r[s] != ""]
            ct = [float(r["phase_elapsed_s"]) for r in coolr if r[s] != ""]
            cy = [float(r[s]) for r in coolr if r[s] != ""]
            h = fit(heat, lt, ly, (ly[0] if ly else 30, (max(ly) - ly[0]) if ly else 1, 30)) if ly else None
            c = fit(cool, ct, cy, (cy[-1] if cy else 30, (cy[0] - cy[-1]) if cy else 1, 60)) if cy else None
            tail = [(t, y) for t, y in zip(lt, ly) if 40.0 <= t <= 60.0]
            out.append(dict(key, sensor=s,
                            heat_tau=h and h["tau"], heat_r2=h and h["r2"], heat_mae=h and h["mae"],
                            cool_tau=c and c["tau"], cool_r2=c and c["r2"], cool_mae=c and c["mae"],
                            load_rise=(ly[-1] - ly[0]) if ly else None,
                            slope_end=slope_per_min([a for a, _ in tail], [b for _, b in tail]) if tail else None,
                            reach60=(1.0 - math.exp(-60.0 / h["tau"])) if h else None))
    return out


def med(v):
    v = [x for x in v if x is not None and not (isinstance(x, float) and math.isnan(x))]
    return st.median(v) if v else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dirs", nargs="+")
    ap.add_argument("-o", "--out")
    a = ap.parse_args()
    rows = []
    for d in a.dirs:
        rows += analyse(d)
    if a.out:
        with open(a.out, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader(); w.writerows(rows)
    groups = defaultdict(list)
    for r in rows:
        groups[(r["resource"], r["cpu_threads"], r["duty"], r["sensor"])].append(r)
    cols = ("heat_tau", "heat_r2", "heat_mae", "cool_tau", "cool_r2", "load_rise", "slope_end", "reach60")
    print("resource,threads,duty,sensor,n," + ",".join(cols))
    for k in sorted(groups, key=lambda k: (k[3], k[0], str(k[1]), k[2])):
        g = groups[k]
        vals = [med([r[c] for r in g]) for c in cols]
        print(",".join(map(str, k)) + f",{len(g)}," + ",".join("" if v is None else f"{v:.4g}" for v in vals))


if __name__ == "__main__":
    main()
