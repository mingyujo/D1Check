"""N4 1006r: print the non-bin fields of night1004_judge gi300 / ni300 output JSONs (read only) for the result documents.
usage: py -X utf8 n4_summary_1006r.py <json> [<json> ...]"""
import json, sys

sys.stdout.reconfigure(encoding="utf-8")
for p in sys.argv[1:]:
    d = json.load(open(p, encoding="utf-8"))
    print("=" * 20, p.split("\\")[-1])
    for k in ("chain_id", "run_id", "start_skin", "start_skin_in_band_29_1_31_6", "start_thermal", "a3_label", "ref_d10_ms", "ref_d100_ms",
              "completed_inference_count", "pilot_battery_pct", "termination_reason"):
        print(f"{k}: {json.dumps(d.get(k), ensure_ascii=False)}")
    for sec in ("heat", "rest", "reheat"):
        v = d.get(sec) or {}
        print(f"[{sec}]")
        for kk, vv in v.items():
            if kk in ("bins", "bins_ratio"):
                continue
            print(f"  {kk}: {json.dumps(vv, ensure_ascii=False)}")
        if sec == "rest":
            print("  temps@0/60/120/180/240/299:", [(b.get("t0"), b.get("SKIN"), b.get("AP"), b.get("BAT")) for b in v.get("bins", []) if b.get("t0") in (0, 60, 120, 180, 240, 290)])
        if sec == "reheat":
            print("  ratios:", [round(b.get("ratio"), 3) for b in v.get("bins", [])])
    for seg in d.get("segments", []):
        print("  seg", json.dumps({k: seg.get(k) for k in ("index", "label", "n", "duty", "length_s", "start_soc", "soc")}, ensure_ascii=False))
