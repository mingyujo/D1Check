"""Print the key fields of a night1004_judge output (n50p/g50p/gi300/ni300) — read-only summary for the session."""
import json, sys
sys.stdout.reconfigure(encoding="utf-8")
j = json.load(open(sys.argv[1], encoding="utf-8"))


def f(x, nd=3):
    if isinstance(x, float):
        return round(x, nd)
    if isinstance(x, list):
        return [f(v, nd) for v in x]
    if isinstance(x, dict):
        return {k: f(v, nd) for k, v in x.items() if k not in ("dt_s",)}
    return x


print("run", j.get("run_id"), "chain", j.get("chain_id"), (j.get("chain_sha256") or "")[:12], "term", j.get("termination_reason"), "n", j.get("completed_inference_count"), "pilot", j.get("pilot_battery_pct"))
print("start_skin", j.get("start_skin"), "band", j.get("start_skin_in_band_29_1_31_6"), "dev", j.get("start_skin_in_dev_range"), "imports_ok", all(v["ok"] for v in j["imports"].values()))
for s in j["segments"]:
    print(" seg", s["index"], s["label"], s["accelerator"], "d", s["duty"], "len", round(s["length_s"], 3), "n", s["n"], "start", f(s["start_thermal"]), "end", f(s["end_thermal"]), "soc", (s["start_soc"] or {}).get("battery_level"))
print("transitions", [round(t.get("duration_s") or 0, 4) for t in j["transitions"]])
for k in ("ref_d50_ms", "ref_d10_ms", "ref_d100_ms", "a3_label"):
    if k in j:
        print(k, f(j[k], 5))
if "ref_bins_ratio" in j:
    print("ref bins", f(j["ref_bins_ratio"]))
if "ref0_bins_ratio" in j:
    print("ref0 bins", f(j["ref0_bins_ratio"]))
h = j["heat"]
print("HEAT ref30", f(h["ref30_ms"], 5), "onset_1_1", h["onset_1_1_s"], "edge", h["edge_candidate_s"], "step1", h["step1_s"], "window", h["window"], "ratio", f(h["ratio_window"], 4),
      "premise", h.get("premise_label"))
print("  onset_th", f(h["onset_thermal"]), "step1_th", f(h["step1_thermal"]), "end_th", f(h["end_thermal"]))
print("  heat bins", [(t, f(r)) for t, r in h["bins_ratio"]])
if "probe" in j:
    p = j["probe"]
    print("PROBE class", p["classification"], "| release", p["release_s"], "shape", p["shape"], "SKIN_k", p["SKIN_k"], "AP_k", p["AP_k"], "p15", f(p["bins_1_5_median"], 4))
    print("  retighten", p.get("retighten_label"), "| censored", p["release"]["censored"])
    print("  bins", f(p["bins_ratio"]))
    print("  temps", f(p["temps"]))
    if "ap_min_probe" in p:
        print("  ap_min_probe", p["ap_min_probe"], "bins_0_5", f(p["bins_0_5"]))
    print("HYP", j["hypotheses"])
    if "conclusion" in j:
        print("CONCL", j["conclusion"])
    if "compare_m1npu" in j:
        for k in ("a", "b"):
            c = j["compare_m1npu"][k]
            if c:
                print(" M1", k, "start", c["start_skin"], "step1", c["step1_s"], f(c["step1_thermal"]), "onset", c["onset_1_1_s"], f(c["onset_thermal"]), "540", f(c["ratio_540_600"], 4), "rel", c["release_s"], c["SKIN_k"], c["AP_k"])
if "rest" in j:
    r = j["rest"]
    print("REST", r["label"], "duty", r["duty"], "n", r["n"], "note", r["rest_note"])
    print("  temps", f(r["temps"]))
    print("  bins(desc)", f(r["bins_ratio_vs_ref_d10_descriptive"]))
    rh = j["reheat"]
    print("REHEAT", rh["retighten"], "| class", rh["classification"], "| SKIN_k", rh["SKIN_k"], "AP_k", rh["AP_k"], "first", f(rh["first_bin_ratio"], 4))
    print("  bins", f(rh["bins_ratio"]))
    for k in ("ratio_240_300", "ratio_240_300_vs_heat_540_600", "retighten_vs_step1_5runs"):
        if k in rh:
            print(" ", k, f(rh[k], 4))
    print("  compare", f(j.get("compare")))
