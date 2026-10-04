"""Print key fields of night1004_judge_effblock2 output (read-only)."""
import json, sys
sys.stdout.reconfigure(encoding="utf-8")
b = json.load(open(sys.argv[1], encoding="utf-8"))
print("order", b["design"]["observed_order"], "matches_block2", b["design"]["order_matches_block2"], "errors", b["errors"], "incomplete", b["cells_incomplete"])
print("import", b["import"]["ok"], b["import"]["sha256"][:8], "| block1", b.get("block1_source"))
for x in b["runs"]:
    ev = x.get("evidence") or {}
    th = x["thermal"]
    print(f"{x['order']} {x['cell']} n={x['n_inferences_in_load']} ro={x['run_only']['median_ms']:.4f} wrr={x['latency_median_ms']:.4f} maxbin={x['max_bin_ratio']:.3f} "
          f"start={th['load_start']['SKIN']} dSKIN={th['skin_rise']:.1f} dAP={th['ap_rise']:.1f} stmax={th['status_max_in_load']} W={x['power']['mean_W_in_load']:.2f} "
          f"ev={ev.get('verdict')} {ev.get('xy_note')} gpu_ok={ev.get('gpu_data_ok')} valid={x['valid']} gate={(x.get('gate') or {}).get('waited_s')} soc={(x.get('gate') or {}).get('soc')} band={x['start_skin_in_band_29_1_31_6']} pilot={x['pilot_battery_pct']}")
for c, v in b["cells"].items():
    ro = v["run_only_median_ms"]; wr = v["latency_median_ms"]
    print(f"cell {c} orders={v['orders']} ro={ro['values']} mean={ro['mean']:.4f} diff_rel={ro['diff_rel']} | wrr mean={wr['mean']:.4f} | skin={v['skin_rise']['values']} W={v['power_W']['values']}")
print("interaction (block2 per import rule):", b["interaction_cpu"])
print("interaction_cpu_block2:", b["interaction_cpu_block2"])
print("two_block:")
for c, v in b["two_block"]["cells"].items():
    print("  ", c, v["run_only_median_ms"], "| wrr", v["latency_median_ms"])
