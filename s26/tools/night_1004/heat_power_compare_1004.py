"""Descriptive only (not a verdict): NPU d100 heating segment — mean d1check power (W, unit-assumed), inference rate, SKIN/AP/BAT path,
for N50P (1004) vs M1-NPU a/b (1003). Uses m1m2_judge_1002 (import, unchanged) for segments/power/thermal."""
import importlib.util, json, os, sys
import numpy as np
sys.stdout.reconfigure(encoding="utf-8")
SIM = r"C:\Users\rhoyo\OneDrive\문서\Mine\26-2\산공학회\D1_ondevice\sim"
spec = importlib.util.spec_from_file_location("m1m2_judge_1002", os.path.join(SIM, "m1m2_judge_1002.py"))
J = importlib.util.module_from_spec(spec); spec.loader.exec_module(J)
R = r"C:\Users\rhoyo\AndroidStudioProjects\D1Check_v4\results"
runs = [("N50P_1004", "S26_N50P_1004", 1), ("M1npu_a_1003", "S26_M1_npu_1003", 1), ("M1npu_b_1003", "S26_M1_npu_r2_1003", 1)]
out = {}
for tag, folder, hi in runs:
    base = os.path.join(R, folder, "runs")
    rd = os.path.join(base, os.listdir(base)[0])
    run = J.load_run(rd)
    S = J.segments_of(run)
    seg = S["segments"][hi]
    pt, pw = J.power_series(run, seg)
    rows = {}
    for a, b in ((0, 60), (60, 180), (180, 300), (300, 420)):
        m = (pt >= a) & (pt < b)
        n = int(((seg["rel_t"] >= a) & (seg["rel_t"] < b)).sum())
        rows[f"{a}-{b}"] = dict(power_W=(float(pw[m].mean()) if m.any() else None), inf_per_s=n / (b - a))
    th = {t: J.thermal_at(run, seg["start_ns"] + int(t * 1e9)) for t in (0, 60, 120, 180, 240, 300, 360, 419)}
    out[tag] = dict(start_thermal=J.thermal_at(run, S["segments"][0]["start_ns"]), windows=rows,
                    path={t: (v["SKIN"], v["AP"], v["BAT"]) for t, v in th.items()}, d1_samples=len(run["d1"]))
    print(tag, "seg0 start", {k: out[tag]["start_thermal"][k] for k in ("SKIN", "AP", "BAT")}, "d1 samples", len(run["d1"]))
    for k, v in rows.items():
        print("   heat", k, "W", None if v["power_W"] is None else round(v["power_W"], 2), "inf/s", round(v["inf_per_s"], 1))
    print("   SKIN/AP/BAT at heat t:", out[tag]["path"])
json.dump(out, open(os.path.join(SIM, "out_1004", "N50P_heat_power_compare_desc.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=float)
