"""Energy B + V3 description tables (energy prereg v1 §1-1 · §1-2 · §5, P1i 1-3) — runs AFTER the judge freeze (commit 7578f8e).

Imports the frozen judge sim/energy_judge_v1.py (SHA dcd6d9b7…, refuses otherwise) and calls only its functions:
  energy_run (per run) · pair_energy (A/B or base/ours — the judge itself refuses energy C cells) · session_check (②).
Pairs = the thermal pair files as registered (§1-1 table · §1-2): out_1005e pair_NPU_b1/b2 · pair_GPU_b1/b2 · out_1005n pair_N_b1/b2 ·
pair_G_b1/b2 · supplementary pair_N_b2s · pair_G_b2s (session differs — flagged) · out_v3_1007 pair_A2_b1/b2 · pair_B2_b1/b2 ·
out_v3_1006 A_base_b1_re (no partner — run values only, appendix).
Run folder = results\\<folder>\\runs\\<run_id> found by run_id. Session key for ② = the folder suffix (e.g. 1005e · 1005n · 1006r · 1007).
Writes sim/out_energy/{runs,pairs}/*.json · sessions.json · energy_b_summary.json · energy_b_log.txt (status lines only).
  py -X utf8 s26\\tools\\energy_1008\\energy_b_compute.py
"""
import hashlib, importlib.util, json, os, sys, time, traceback

sys.stdout.reconfigure(encoding="utf-8")
REPO = r"C:\Users\rhoyo\AndroidStudioProjects\D1Check_v4"
SIM = r"C:\Users\rhoyo\OneDrive\문서\Mine\26-2\산공학회\D1_ondevice\sim"
OUT = os.path.join(SIM, "out_energy")
JPATH = os.path.join(SIM, "energy_judge_v1.py")
JSHA = "dcd6d9b7b500a6871caf55b94ca6a446b37eb3bd7779be84328e7af575cfa85b"
LOG = os.path.join(OUT, "energy_b_log.txt")


def log(m):
    line = time.strftime("[%Y-%m-%d %H:%M:%S] ") + m
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")


got = hashlib.sha256(open(JPATH, "rb").read()).hexdigest()
if got != JSHA:
    raise SystemExit(f"judge SHA {got[:8]} != {JSHA[:8]}")
spec = importlib.util.spec_from_file_location("energy_judge_v1", JPATH)
EJ = importlib.util.module_from_spec(spec)
spec.loader.exec_module(EJ)

PAIRS = [  # (group, pair file, A key, B key, note)
    ("N2 NPU EffNet", "out_1005e/pair_NPU_b1.json", "a", "b", ""),
    ("N2 NPU EffNet", "out_1005e/pair_NPU_b2.json", "a", "b", ""),
    ("N1 NPU MobileNet (민감도)", "out_1005n/pair_N_b1.json", "a", "b", ""),
    ("N1 NPU MobileNet (민감도)", "out_1005n/pair_N_b2.json", "a", "b", ""),
    ("N1 NPU MobileNet (민감도)", "out_1005n/pair_N_b2s.json", "a", "b", "보충 쌍 — 세션 다름"),
    ("N2 GPU EffNet", "out_1005e/pair_GPU_b1.json", "a", "b", ""),
    ("N2 GPU EffNet", "out_1005e/pair_GPU_b2.json", "a", "b", ""),
    ("N1 GPU MobileNet", "out_1005n/pair_G_b1.json", "a", "b", ""),
    ("N1 GPU MobileNet", "out_1005n/pair_G_b2.json", "a", "b", ""),
    ("N1 GPU MobileNet", "out_1005n/pair_G_b2s.json", "a", "b", "보충 쌍 — 세션 다름"),
    ("V3 v2 A2", "out_v3_1007/pair_A2_b1.json", "base", "ours", ""),
    ("V3 v2 A2", "out_v3_1007/pair_A2_b2.json", "base", "ours", ""),
    ("V3 v2 B2", "out_v3_1007/pair_B2_b1.json", "base", "ours", ""),
    ("V3 v2 B2", "out_v3_1007/pair_B2_b2.json", "base", "ours", ""),
]
SINGLES = [("V3 v1 A (짝 없음 — 부록)", "out_v3_1006/A_base_b1_re.json")]
# "_re" folders: session = when they ran (folder / console times [P]): N1 supplementary runs were measured in the N4 session 10/6 08:3x~09:3x
# (1006r) · V3 A2_base_b2_re 10/7 16:0x (1007) · V3 v1 A_base_b1_re 10/7 00:2x (P1g night 1006).
RE_SESSION = {"S26_NB_b2_1005n_re": "1006r", "S26_GB_b2_1005n_re": "1006r", "S26_V3_A2_base_b2_1007_re": "1007", "S26_V3_A_base_b1_1006_re": "1006"}


def index_runs():
    idx = {}
    res = os.path.join(REPO, "results")
    for top in os.scandir(res):
        rd = os.path.join(top.path, "runs")
        if top.is_dir() and os.path.isdir(rd):
            for r in os.scandir(rd):
                if r.is_dir():
                    idx.setdefault(r.name, []).append((top.name, r.path))
    return idx


def thermal_json_for(run_id, out_dir):
    for f in sorted(os.listdir(os.path.join(SIM, out_dir))):
        if not f.endswith(".json") or f.startswith(("pair_", "watch_", "check_", "cmp_", "res", "cond_", "resource_")) or f.endswith(("_check.json", "_watch.json")):
            continue
        try:
            j = json.load(open(os.path.join(SIM, out_dir, f), encoding="utf-8"))
        except Exception:
            continue
        if j.get("run_id") == run_id:
            return f, j
    return None, None


def main():
    os.makedirs(os.path.join(OUT, "runs"), exist_ok=True)
    os.makedirs(os.path.join(OUT, "pairs"), exist_ok=True)
    log(f"START judge {JSHA[:8]} imports={ {k: v['sha256'][:8] for k, v in EJ.import_check().items()} }")
    idx = index_runs()
    log(f"indexed {len(idx)} run ids")
    run_cache = {}

    def do_run(run_id, out_dir, group):
        if run_id in run_cache:
            return run_cache[run_id]
        tf, tj = thermal_json_for(run_id, out_dir)
        if tj is None:
            raise RuntimeError(f"thermal run JSON for {run_id} not found in {out_dir}")
        locs = idx.get(run_id, [])
        if len(locs) != 1:
            raise RuntimeError(f"run folder for {run_id}: {len(locs)} found")
        folder, rd = locs[0]
        sess = RE_SESSION.get(folder) or folder.rsplit("_", 1)[-1]
        t0 = time.time()
        j = EJ.energy_run(EJ.load_run(rd), tj["cell"], tj["block"], sess)
        lower = ((tj.get("start") or {}).get("lower") or {}).get("label")
        j["source"] = dict(group=group, folder=folder, thermal_json=f"{out_dir}/{tf}", lower_label=lower, start_skin=tj.get("start_skin"))
        name = f"{tf[:-5]}__{folder}.json"
        with open(os.path.join(OUT, "runs", name), "w", encoding="utf-8") as fh:
            fh.write(EJ.dumps(j) + "\n")
        q = j["qc"]
        log(f"RUN {tf} folder={folder} session={sess} excluded={q['excluded']} reasons={' · '.join(q['exclusion_reasons']) or '-'} "
            f"unit={q['unit_1']} clock={q['clock_check']} lower={lower} ({time.time() - t0:.0f} s)")
        run_cache[run_id] = (name, j)
        return run_cache[run_id]

    pairs_out, errors = [], []
    for group, pf, ka, kb, note in PAIRS:
        try:
            pj = json.load(open(os.path.join(SIM, pf), encoding="utf-8"))
            od = pf.split("/")[0]
            na, ja = do_run(pj[ka]["run_id"], od, group)
            nb, jb = do_run(pj[kb]["run_id"], od, group)
            p = EJ.pair_energy(ja, jb)
            p["group"], p["pair_file"], p["note"] = group, pf, note
            p["lower_a"], p["lower_b"] = ja["source"]["lower_label"], jb["source"]["lower_label"]
            p["run_files"] = [na, nb]
            name = os.path.basename(pf).replace("pair_", "epair_")
            with open(os.path.join(OUT, "pairs", f"{od}__{name}"), "w", encoding="utf-8") as fh:
                fh.write(EJ.dumps(p) + "\n")
            pairs_out.append(p)
            log(f"PAIR {pf} ok excluded={p['excluded']}")
        except Exception as e:  # noqa
            errors.append(dict(pair=pf, error=repr(e)[:400]))
            log(f"PAIR {pf} ERROR {repr(e)[:300]}")
            log(traceback.format_exc()[-600:])
    singles = []
    for group, f in SINGLES:
        try:
            tj = json.load(open(os.path.join(SIM, f), encoding="utf-8"))
            n, j = do_run(tj["run_id"], f.split("/")[0], group)
            singles.append(dict(group=group, file=n))
        except Exception as e:  # noqa
            errors.append(dict(single=f, error=repr(e)[:400]))
            log(f"SINGLE {f} ERROR {repr(e)[:300]}")
    sessions = {}
    by_sess = {}
    for rid, (n, j) in run_cache.items():
        by_sess.setdefault(j["qc"]["session"], []).append(j)
    for s, runs in sorted(by_sess.items()):
        sessions[s] = dict(EJ.session_check(runs), runs=[r["qc"]["run_id"] for r in runs])
        log(f"SESSION {s} N={sessions[s]['N']} verdict={sessions[s]['verdict']}")
    with open(os.path.join(OUT, "sessions.json"), "w", encoding="utf-8") as fh:
        fh.write(EJ.dumps(sessions) + "\n")
    summ = dict(kind="energy_b_summary_v1", judge_sha256=JSHA, pairs=[os.path.basename(p["pair_file"]) for p in pairs_out], singles=singles, errors=errors,
                runs=sorted(n for n, _ in run_cache.values()))
    with open(os.path.join(OUT, "energy_b_summary.json"), "w", encoding="utf-8") as fh:
        fh.write(EJ.dumps(summ) + "\n")
    log(f"END pairs={len(pairs_out)} runs={len(run_cache)} errors={len(errors)}")


if __name__ == "__main__":
    main()
