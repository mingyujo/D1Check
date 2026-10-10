"""cells_from_state.py — GH (1011) 5단계-2: build sim/out_gpuho/cells_gpuho.json (input of measure_gpuho.py) from the session driver's
state file(s) (results/S26_host_gpuho_1011/driver_state_h*.json — every driver run appends its own cells map; the latest value per key wins)
and the judge JSONs in sim/out_gpuho. Mechanical: per block · cell the single attempt whose state is "valid" (key <cell>_b<k> or <cell>_b<k>_re);
blocks with a cell that has no valid attempt -> blocks[k].reason (invalid_twice text from the driver, or 'no valid run'). Invalid / abort attempts
are listed for the report. Reads only.
  py -X utf8 cells_from_state.py [--out <cells_gpuho.json>]
"""
import glob, hashlib, json, os, sys

sys.stdout.reconfigure(encoding="utf-8")
REPO = r"C:\Users\rhoyo\AndroidStudioProjects\D1Check_v4"
H = os.path.join(REPO, "results", "S26_host_gpuho_1011")
OD = r"C:\Users\rhoyo\OneDrive\문서\Mine\26-2\산공학회\D1_ondevice"
OUTC = os.path.join(OD, "sim", "out_gpuho")
SFX = "1011h"
CELLS = ("GAh", "GBh")
out_path = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else os.path.join(OUTC, "cells_gpuho.json")

cells_state, not_comp, aborts, lower_marked, smoke = {}, {}, [], [], {}
state_files = sorted(glob.glob(os.path.join(H, "driver_state_h*.json")), key=os.path.getmtime)
for sf in state_files:
    st = json.load(open(sf, encoding="utf-8"))
    cells_state.update(st.get("cells") or {})
    not_comp.update(st.get("not_computable") or {})
    aborts += list(st.get("aborts") or [])
    lower_marked += list(st.get("lower_marked") or [])
    smoke.update(st.get("smoke") or {})
# the driver log is the authoritative per-attempt record when a later driver run re-wrote a key (state maps are merged above)
rows, blocks, attempts = [], {}, []
for k in range(1, 9):
    for cell in CELLS:
        cands = [(key, v) for key, v in cells_state.items() if key == f"{cell}_b{k}" or key == f"{cell}_b{k}_re"]
        for key, v in cands:
            attempts.append(dict(block=k, cell=cell, key=key, state=v))
        valid = [key for key, v in cands if v == "valid"]
        if len(valid) > 1:
            sys.exit(f"block {k} {cell}: more than one valid attempt {valid}")
        if valid:
            key = valid[0]
            out_name = f"S26_{cell}_b{k}_{SFX}" + ("_re" if key.endswith("_re") else "")
            jj = os.path.join(OUTC, f"{key}.json")
            if not os.path.exists(jj) or not os.path.isdir(os.path.join(REPO, "results", out_name)):
                sys.exit(f"{key}: judge JSON or results folder missing ({jj} · {out_name})")
            J = json.load(open(jj, encoding="utf-8"))
            rows.append(dict(block=k, cell=cell, status="valid", attempt=key, retry=key.endswith("_re"), out_name=out_name, run_id=J["run_id"],
                             judge_json=os.path.relpath(jj, OD), judge_json_sha256=hashlib.sha256(open(jj, "rb").read()).hexdigest(),
                             start_skin=J["start_skin"], lower=J["start"]["lower"]["label"], lower_marked=(key in lower_marked or J["start"]["lower"]["label"] == "하한 미달")))
        else:
            rows.append(dict(block=k, cell=cell, status="no_valid_run", attempt=None, retry=None, out_name=None, run_id=None, judge_json=None,
                             states={key: v for key, v in cands}))
            blocks[str(k)] = dict(reason=not_comp.get(f"b{k}") or f"no valid run ({cell}: {[v for _, v in cands] or 'not run'})")
res = dict(kind="gpuho_cells_v1", session_suffix=SFX, state_files=[os.path.relpath(f, REPO) for f in state_files], cells=rows, blocks=blocks,
           attempts=attempts, aborts=aborts, lower_marked=sorted(set(lower_marked)), smoke=smoke,
           n_valid=sum(1 for r in rows if r["status"] == "valid"), n_blocks_not_computable=len(blocks))
s = json.dumps(res, ensure_ascii=False, indent=1, sort_keys=True)
os.makedirs(os.path.dirname(out_path), exist_ok=True)
open(out_path, "w", encoding="utf-8", newline="\n").write(s + "\n")
print(f"valid {res['n_valid']}/16 · not computable blocks {sorted(blocks)} · aborts {len(aborts)} · lower marked {res['lower_marked']} -> {out_path} sha256 {hashlib.sha256((s + chr(10)).encode('utf-8')).hexdigest()}")
