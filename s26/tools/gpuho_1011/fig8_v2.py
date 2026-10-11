"""fig8_v2.py — GH (1011) 5단계-3: deck page-8 figure data v2 = P1k's fig8_pred_vs_meas.csv (46 points, values as-is) + this session's
GPU holdout 16 cells (▲ holdout) → sim/out_gpuho/fig8_pred_vs_meas_v2.csv and sim/fig8_pred_vs_meas_v2.png (same look as P1k's:
x = measured max SKIN · y = v2.2 predicted max SKIN (two-point column) · diagonal + ±1.0 ℃ band · NPU blue / GPU red · fit ● / holdout ▲ ·
no title, legend only · Malgun Gothic). PNG stays in D1_ondevice only (the repo gets the CSV). Reads the GH judge output (gpuho_judge.json) —
runs only after the single readout.
  py -X utf8 fig8_v2.py
"""
import csv, hashlib, os, sys

sys.stdout.reconfigure(encoding="utf-8")
REPO = r"C:\Users\rhoyo\AndroidStudioProjects\D1Check_v4"
sys.path.insert(0, REPO)
from d1sim.gpu_holdout_v1 import common as C  # noqa: E402

P1K_CSV = os.path.join(C.OD_SIM, "out_gpuerr", "fig8_pred_vs_meas.csv")
OUT_CSV = os.path.join(C.OUT_OD, "fig8_pred_vs_meas_v2.csv")
OUT_PNG = os.path.join(C.OD_SIM, "fig8_pred_vs_meas_v2.png")
J = C.load_json(os.path.join(C.OUT_OD, "gpuho_judge.json"))
rows = list(csv.DictReader(open(P1K_CSV, encoding="utf-8-sig")))
fields = list(rows[0].keys())
n_p1k = len(rows)
for c in J["cells"]:
    e = c["models"]["v22"]
    rows.append(dict(run=f"gpuho_{c['cell']}_b{c['block']}", resource="GPU", model="effnet", group="gpuho", kind="GPU 홀드아웃 (GH · 같은 계열 새 세션 · 10/11)", marker="holdout",
                     start_skin=c["start_skin"], column=c["column"], meas_max_skin=c["meas_max_skin"], pred_max_skin_v22=e.get("pred_max_skin"), m3=e.get("m3"),
                     source="sim/out_gpuho/gpuho_judge.json"))
with open(OUT_CSV, "w", encoding="utf-8-sig", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=fields)
    w.writeheader()
    for r in rows:
        w.writerow({k: r.get(k, "") for k in fields})
sha = hashlib.sha256(open(OUT_CSV, "rb").read()).hexdigest()
print(f"csv {OUT_CSV} rows {len(rows)} (P1k {n_p1k} + GH {len(rows) - n_p1k}) sha256 {sha}")
# ---- PNG
import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402
for cand in ("Malgun Gothic", "맑은 고딕", "NanumGothic"):
    if any(f.name == cand for f in font_manager.fontManager.ttflist):
        plt.rcParams["font.family"] = cand
        break
plt.rcParams["axes.unicode_minus"] = False
fig, ax = plt.subplots(figsize=(6.4, 5.6), dpi=150)
xs = [float(r["meas_max_skin"]) for r in rows if r.get("meas_max_skin") not in ("", None)]
ys = [float(r["pred_max_skin_v22"]) for r in rows if r.get("pred_max_skin_v22") not in ("", None)]
lo, hi = min(xs + ys) - 0.5, max(xs + ys) + 0.5
ax.fill_between([lo, hi], [lo - 1.0, hi - 1.0], [lo + 1.0, hi + 1.0], color="#dddddd", alpha=0.5, linewidth=0, label="±1.0 ℃")
ax.plot([lo, hi], [lo, hi], color="#555555", linewidth=1, label="예측 = 실측")
styles = {("NPU", "fit"): dict(c="#1f5fbf", m="o", lab="NPU 적합도 ●"), ("NPU", "holdout"): dict(c="#1f5fbf", m="^", lab="NPU 홀드아웃 ▲"),
          ("GPU", "fit"): dict(c="#c0392b", m="o", lab="GPU 적합도 ●"), ("GPU", "holdout"): dict(c="#c0392b", m="^", lab="GPU 홀드아웃 ▲")}
for (res, mk), st in styles.items():
    pts = [(float(r["meas_max_skin"]), float(r["pred_max_skin_v22"])) for r in rows if r["resource"] == res and r["marker"] == mk and r["group"] != "gpuho" and r.get("pred_max_skin_v22") not in ("", None)]
    if pts:
        ax.scatter([p[0] for p in pts], [p[1] for p in pts], c=st["c"], marker=st["m"], s=34, alpha=0.85, edgecolors="white", linewidths=0.5, label=f"{st['lab']} (n={len(pts)})")
gh = [(float(r["meas_max_skin"]), float(r["pred_max_skin_v22"])) for r in rows if r["group"] == "gpuho"]
if gh:
    ax.scatter([p[0] for p in gh], [p[1] for p in gh], facecolors="none", edgecolors="#c0392b", marker="^", s=90, linewidths=1.2, label=f"GPU 홀드아웃 GH 10/11 (n={len(gh)})")
ax.set_xlim(lo, hi); ax.set_ylim(lo, hi); ax.set_aspect("equal")
ax.set_xlabel("실측 최고 SKIN (℃)"); ax.set_ylabel("v2.2 예측 최고 SKIN (℃)")
ax.grid(True, linewidth=0.3, alpha=0.5)
ax.legend(fontsize=8, loc="upper left", framealpha=0.9)
fig.tight_layout()
fig.savefig(OUT_PNG)
print(f"png {OUT_PNG}")
