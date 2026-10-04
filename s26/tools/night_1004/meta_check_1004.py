"""Print run_metadata model/engine fields and npu_artifact_hash for a result dir (read-only, single run)."""
import glob, json, os, sys
sys.stdout.reconfigure(encoding="utf-8")
res = sys.argv[1]
rd = glob.glob(os.path.join(res, "runs", "*"))[0]
f = glob.glob(os.path.join(rd, "gpu", "*.jsonl"))[0]
with open(f, encoding="utf-8") as fh:
    for line in fh:
        if '"run_metadata"' in line or '"npu_artifact_hash"' in line:
            e = json.loads(line)
            if e.get("event") == "run_metadata":
                keys = [k for k in e if any(s in k for s in ("model", "engine", "litert", "resource", "dispatch", "span", "input_spec", "accelerator"))]
                print("run_metadata:", {k: (str(e[k])[:70] if e[k] is not None else None) for k in keys})
            if e.get("event") == "npu_artifact_hash":
                d = e.get("detail")
                d = json.loads(d) if isinstance(d, str) else d
                print("npu_artifact_hash:", json.dumps(d, ensure_ascii=False)[:500])
        if '"load_start"' in line:
            break
