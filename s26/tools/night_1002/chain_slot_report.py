# -*- coding: utf-8 -*-
"""Read-only summary of a chain-mode result dir (after the orchestrator exited — never while it runs):
slot status, validation (valid / failed_checks / chain_structure / chain_conservation_flags / chain_check notes),
transitions, per-segment termination, formal_npu_valid + not_chain_run, retry count, timings.
Usage: py chain_slot_report.py <result_dir> [<result_dir> ...]"""
import json, sys, os, glob, csv

for R in sys.argv[1:]:
    print("=" * 100)
    print(R)
    mp = os.path.join(R, "experiment_manifest.json")
    if not os.path.exists(mp):
        print("  (no manifest)"); continue
    m = json.load(open(mp, encoding="utf-8"))
    print("  manifest status:", m.get("status"), "| halt:", m.get("halt_reason"), "| started", m.get("started_utc"), "| completed", m.get("completed_utc"))
    for s in m.get("runs", []):
        v = s.get("validation") or {}
        print(f"  slot {s.get('slot_id')} status={s.get('status')} attempts={s.get('attempts')} run_id={s.get('run_id')} error={s.get('error')}")
        print(f"    valid={v.get('valid')} failed_checks={v.get('failed_checks')}")
        print(f"    chain_conservation_flags={v.get('chain_conservation_flags')}")
        cc = v.get("chain_check") or {}
        if cc:
            print(f"    chain_check passed={cc.get('passed')} structure_passed={cc.get('structure_passed')} timing_flags={cc.get('timing_flags')} failed={cc.get('failed_checks')}")
            for n in cc.get("notes", [])[:6]:
                print("      note:", n[:200])
        steps = s.get("steps") or []
        names = [st.get("name") or st.get("step") for st in steps if isinstance(st, dict)]
        print(f"    steps({len(steps)}):", names[:30])
        for st in steps:
            if isinstance(st, dict) and any(k in json.dumps(st)[:400] for k in ("cooling", "stabil", "emergency")):
                pass
        rid = s.get("run_id")
        if rid:
            rd = os.path.join(R, "runs", rid)
            f = glob.glob(os.path.join(rd, "gpu", "*.jsonl"))
            if f:
                ev = {}
                meta = None; segs = []; trans = []
                with open(f[0], encoding="utf-8") as fh:
                    for line in fh:
                        try:
                            e = json.loads(line)
                        except ValueError:
                            ev["<bad>"] = ev.get("<bad>", 0) + 1; continue
                        ev[e.get("event")] = ev.get(e.get("event"), 0) + 1
                        if e.get("event") == "run_metadata": meta = e
                        elif e.get("event") == "segment_end": segs.append(json.loads(e["detail"]) if isinstance(e.get("detail"), str) else e.get("detail"))
                        elif e.get("event") == "chain_transition_end": trans.append(json.loads(e["detail"]) if isinstance(e.get("detail"), str) else e.get("detail"))
                print("    runner events:", {k: ev[k] for k in sorted(ev, key=str)})
                if meta:
                    print(f"    meta: termination={meta.get('termination_reason')} completed={meta.get('completed_inference_count')} chain_mode={meta.get('chain_mode')} model_prepare={meta.get('chain_model_prepare')} max_spans={meta.get('max_inference_spans')} jvm={meta.get('jvm_max_memory_bytes')} pilot_pct={meta.get('pilot_battery_pct')} load_ns={meta.get('actual_load_duration_ns')}")
                for d in segs:
                    print(f"    seg {d.get('index')} {d.get('label')} {d.get('accelerator')} d{d.get('requested_duty_cycle_percent')} n={d.get('inference_count')} term={d.get('termination_reason')} dur={d.get('actual_duration_ns', 0)/1e9:.3f}s achieved={d.get('achieved_duty_cycle_percent')} gpu_precision={d.get('gpu_precision')}")
                for d in trans:
                    print(f"    transition -> seg {d.get('to_segment')} {d.get('from_accelerator')}->{d.get('to_accelerator')} switch={d.get('backend_switch')} model_initialized={d.get('model_initialized')} dur={d.get('duration_ns', 0)/1e6:.1f} ms model_init={d.get('model_init_ns', 0)/1e6:.1f} ms env_init={d.get('env_init_ns', 0)/1e6:.1f} ms warmup={d.get('warmup_count')}")
            sp = os.path.join(rd, "merged", "summary.json")
            if os.path.exists(sp):
                sm = json.load(open(sp, encoding="utf-8"))
                print(f"    summary: formal_npu_valid={sm.get('formal_npu_valid')} not_chain_run={(sm.get('formal_npu_conditions') or {}).get('not_chain_run')} thermalservice_samples={sm.get('thermalservice_sample_count')} telemetry={sm.get('telemetry_sample_count')}")
            lp = os.path.join(rd, "raw", "logcat.txt")
            if os.path.exists(lp):
                n = 0; d1 = 0
                with open(lp, encoding="utf-8", errors="replace") as fh:
                    for line in fh:
                        n += 1
                        if " D1GPU " in line or " D1GPU:" in line: d1 += 1
                print(f"    raw logcat lines={n} D1GPU={d1}")
    rs = os.path.join(R, "exports-v2", "run_summary.csv")
    if os.path.exists(rs):
        for r in csv.DictReader(open(rs, encoding="utf-8")):
            print("    run_summary:", {k: r.get(k) for k in ("slot_status", "validation_status", "termination_reason", "completed_inference_count", "actual_load_duration_s", "latency_median_ms", "skin_load_start_temperature_c", "skin_load_end_temperature_c", "ap_load_end_temperature_c", "cooling_status")})
