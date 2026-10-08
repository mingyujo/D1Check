"""Energy C judgment (P1i 4단계) — runs ONLY when the 8 valid blocks are complete (prereg v1 §4 · P1i prompt 4단계).
1) per run: frozen sim/energy_judge_v1.py (SHA dcd6d9b7…) `run` -> sim/out_energy/c_runs/<cell>_b<k>.json (session C1 / C2)
2) once: `judgeC --runs …` -> sim/out_energy/judgeC_v1.json (the judge refuses an existing output — one judgment).
Run folders = the valid run of each block / cell (results\\S26_<cell>_b<k>_1008c|1009c[_re]). Invalid runs are not passed.
  py -X utf8 judge_c_run.py
"""
import hashlib, os, subprocess, sys

sys.stdout.reconfigure(encoding="utf-8")
REPO = r"C:\Users\rhoyo\AndroidStudioProjects\D1Check_v4"
SIM = r"C:\Users\rhoyo\OneDrive\문서\Mine\26-2\산공학회\D1_ondevice\sim"
J = os.path.join(SIM, "energy_judge_v1.py")
assert hashlib.sha256(open(J, "rb").read()).hexdigest().startswith("dcd6d9b7"), "judge SHA"
OUT = os.path.join(SIM, "out_energy", "c_runs")
os.makedirs(OUT, exist_ok=True)
RUNS = []   # (cell, block, session, folder)
for k in range(1, 9):
    sess, sfx = ("C1", "1008c") if k <= 4 else ("C2", "1009c")
    for cell in ("NAc", "NBc"):
        folder = f"S26_{cell}_b{k}_{sfx}"
        if (k, cell) in ((7, "NBc"), (8, "NAc")):
            folder += "_re"            # first tries slot-invalid (adb closed 16:53 / adb timeout 18:23) — the valid runs are the _re (driver log 17:31 · 19:03)
        RUNS.append((cell, k, sess, folder))
files = []
for cell, k, sess, folder in RUNS:
    rdir = os.path.join(REPO, "results", folder, "runs")
    subs = [d for d in os.listdir(rdir) if os.path.isdir(os.path.join(rdir, d))]
    assert len(subs) == 1, (folder, subs)
    out = os.path.join(OUT, f"{cell}_b{k}.json")
    p = subprocess.run(["py", "-X", "utf8", J, "run", os.path.join(rdir, subs[0]), "--cell", cell, "--block", str(k), "--session", sess, "--out", out],
                       capture_output=True, text=True, encoding="utf-8")
    print(folder, "rc", p.returncode, (p.stdout.strip().splitlines() or [""])[0][:200], p.stderr.strip()[-200:])
    if p.returncode != 0:
        sys.exit(2)
    files.append(out)
jo = os.path.join(SIM, "out_energy", "judgeC_v1.json")
p = subprocess.run(["py", "-X", "utf8", J, "judgeC", "--runs", *files, "--out", jo], capture_output=True, text=True, encoding="utf-8")
print("judgeC rc", p.returncode, p.stderr.strip()[-300:])
print("wrote", jo if p.returncode == 0 else "(none)")
