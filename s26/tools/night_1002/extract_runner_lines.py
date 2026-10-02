# -*- coding: utf-8 -*-
"""Print the litert/tflite/TfLite lines of the runner PID from a run's raw/logcat.txt (read-only).
Usage: py extract_runner_lines.py <run_dir> [--all-pids] [--max N]
Sensitive lines (iccid|euicc|imsi|msisdn|phone) are dropped. Also prints every 'Replacing ... delegate' line
and every line matching the parser's failure/GPU patterns, whatever the PID."""
import re, sys, json, glob, os, io
sys.path.insert(0, r"C:\Users\rhoyo\AndroidStudioProjects\D1Check_v4\tools")
import importlib.util
spec = importlib.util.spec_from_file_location("cme", r"C:\Users\rhoyo\AndroidStudioProjects\D1Check_v4\tools\compiled_model_evidence.py")
E = importlib.util.module_from_spec(spec); spec.loader.exec_module(E)
SENS = re.compile(r"iccid|euicc|imsi|msisdn|phone", re.I)
run_dir = sys.argv[1]
all_pids = "--all-pids" in sys.argv
mx = int(sys.argv[sys.argv.index("--max") + 1]) if "--max" in sys.argv else 400
text = io.open(os.path.join(run_dir, "raw", "logcat.txt"), encoding="utf-8", errors="replace").read()
rows = E.parse_log(text)
pids = E.runner_pids(rows)
out = sys.stdout
out.write(f"runner_pids={sorted(pids)} total_rows={len(rows)}\n")
tags = {}
for r in rows:
    if r["pid"] in pids:
        tags[r["tag"]] = tags.get(r["tag"], 0) + 1
out.write(f"runner tag counts: {json.dumps(tags)}\n")
n = 0
for r in rows:
    line = text.splitlines()[r["line"] - 1] if False else None
    keep = (r["pid"] in pids or all_pids) and r["tag"] not in ("D1GPU", "D1NPU", "D1CHECK_EVENT")
    special = E.REPLACE_RE.search(r["msg"]) or E.FAILURE_RE.search(r["msg"]) or E.GPU_ENVIRONMENT_RE.search(r["msg"]) or E.GPU_FAILURE_RE.search(r["msg"])
    if not (keep or special):
        continue
    s = f"{r['line']:>7} pid={r['pid']} {r['level']} {r['tag']}: {r['msg']}"
    if SENS.search(s):
        continue
    out.write(s[:400] + "\n")
    n += 1
    if n >= mx:
        out.write(f"... (truncated at {mx})\n")
        break
