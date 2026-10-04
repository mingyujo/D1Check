"""Read-only validity summary of finished single-run result dirs (NEVER call on a dir whose orchestrator is still running).
Usage: py single_slot_check_1004.py <result_dir> [...]"""
import json, os, sys
sys.stdout.reconfigure(encoding="utf-8")
for d in sys.argv[1:]:
    mp = os.path.join(d, "experiment_manifest.json")
    if not os.path.exists(mp):
        print(os.path.basename(d), "NO MANIFEST"); continue
    m = json.load(open(mp, encoding="utf-8"))
    for r in m.get("runs", []):
        v = r.get("validation") or {}
        print(f"{os.path.basename(d)}: manifest={m.get('status')} halt={m.get('halt_reason')} started={m.get('started_utc')} completed={m.get('completed_utc')} "
              f"slot={r.get('status')} attempts={r.get('attempts')} valid={v.get('valid')} failed={v.get('failed_checks')} error={r.get('error')} run_id={r.get('run_id')}")
