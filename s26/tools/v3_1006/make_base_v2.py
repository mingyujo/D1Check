"""V3 v2 (P1h 1-2): baseline chains v2 of sim/V3_사전등록_v2.md §2 (commit d0a513c) — same-work baseline.

Imports, unmodified: d1sim/v3/predict_v3.py (schedule · simulate · run_metrics · R0 · COLUMNS · MODELS) and
s26/tools/v3_1006/make_chains_v3.py (ser · TEMPLATE · the chain template rule). Writes only new files, never overwrites.

§2-1 bundle zones: bundle k start = start of the first active segment (duty >= 10) that starts in the 10 s cell holding
      arrival k or later; zone k = [start k, start k+1), last zone to the window end. Checked against the registration text.
§2-2 n_ours,k = v2.2 closed-loop prediction of the whole ours v1 chain, completed inferences inside zone k
      (Σ R0·s over executing model seconds) + d1 estimate (d1 seconds inside zone k × 0.01 × R0) — columns 29.5 and 30.5.
§2-3 L_k = shortest multiple of 10 s (<= v1 length) such that the base chain (earlier bundles at their chosen L, this bundle at L,
      later bundles at v1 length) predicted the same way gives n_base,k >= n_ours,k in BOTH columns; k = 1 -> 2 -> 3.
      d100 start cells unchanged; the removed seconds go to the d1 segment right after -> 7 segments, Σ unchanged.
      If even the v1 length fails, keep v1 length and flag it.
§2-4 stop: main-model r = n_ours / n_base (whole chain, d1 estimate incl.) outside [0.96, 1.00] in either column -> exit 6.
      Sensitivity models (v2.1 · v2 θ0.3 · θ0.75): r tabulated only.
§2-5 files tools/chains/v3_{A,B}_base_v2.json (chain_id v3_{A,B}_base_v2, format = v1) · all existing chains re-serialize
      byte-identical first · span ceiling = ceil(1.3 × max predicted n (4 models × 2 columns, d1 estimate incl.) / 1e5) × 1e5.

P1h 가 정함 (결과 전 — v2 칸 0):
  (a) a model second at absolute index i (row i of the 1 s replay) belongs to zone k when start_k <= i < start_k+1;
      d1 seconds per zone are counted from the chain segments the same way.
  (b) r for §2-4 = run_metrics(...)['n_with_d1_est'] ratio (whole chain, segment 0 d1 included — the same quantity as
      v3_prediction_1006.json blocks[*]['r_with_d1_est']).
  (c) n comparisons are made on unrounded floats.

  py -X utf8 s26\\tools\\v3_1006\\make_base_v2.py            # -> tools/chains/v3_{A,B}_base_v2.json + d1sim/out/v3_v2/base_v2_build.json
"""
import hashlib
import json
import math
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = r"C:\Users\rhoyo\AndroidStudioProjects\D1Check_v4"
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "s26", "tools", "v3_1006"))
from d1sim.v3 import predict_v3 as PV  # noqa: E402
import make_chains_v3 as MC  # noqa: E402

CH = os.path.join(ROOT, "tools", "chains")
OUT = os.path.join(ROOT, "d1sim", "out", "v3_v2")
TL = os.path.join(ROOT, "d1sim", "out", "v3_1006", "timelines.json")
COND = {"A": ("v3_A_base_v1", "v3_A_ours_v1", "v3_A_base_v2"), "B": ("v3_B_base_v1", "v3_B_ours_v1", "v3_B_base_v2")}
REG_ZONES = {"A": {"base": [10, 930, 1800], "ours": [10, 930, 1810]},
             "B": {"base": [50, 930, 1820], "ours": [50, 930, 1820]}}          # registration v2 §2-1 text
REG_SIGMA = {"A": 3010, "B": 2729}
R_LO, R_HI = 0.96, 1.00


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def load(cid):
    return json.loads(open(os.path.join(CH, cid + ".json"), "rb").read().decode("utf-8"))


def seg_starts(chain):
    t, out = 0, []
    for s in chain["segments"]:
        out.append(t)
        t += s["duration_s"]
    return out, t


def zones(chain, arrivals):
    st, sigma = seg_starts(chain)
    res = []
    for a in arrivals:
        cell = 10 * math.floor(a / 10)
        cand = [st[i] for i, s in enumerate(chain["segments"]) if s["duty"] >= 10 and st[i] >= cell]
        res.append(min(cand))
    return res, sigma


def zone_of(i, zs, sigma):
    for k in range(len(zs)):
        hi = zs[k + 1] if k + 1 < len(zs) else sigma
        if zs[k] <= i < hi:
            return k
    return None


def zone_n(chain, zs, model, T0):
    rows, _ = PV.simulate(model, PV.schedule(chain), T0)
    st, sigma = seg_starts(chain)
    n = [0.0] * len(zs)
    for i, r in enumerate(rows):
        k = zone_of(i, zs, sigma)
        if k is not None and r["ex"] and r["ratio"] is not None:
            n[k] += PV.R0 / r["ratio"]
    for j, s in enumerate(chain["segments"]):
        if s["duty"] <= 1:
            for i in range(st[j], st[j] + s["duration_s"]):
                k = zone_of(i, zs, sigma)
                if k is not None:
                    n[k] += 0.01 * PV.R0
    return n


def base_with(v1, Ls):
    """v1 base chain with bundle d100 lengths Ls (None = v1 length); removed seconds go to the next d1 segment."""
    obj = json.loads(json.dumps(v1))
    segs = obj["segments"]
    d100 = [i for i, s in enumerate(segs) if s["duty"] == 100]
    for k, L in enumerate(Ls):
        if L is None:
            continue
        i = d100[k]
        assert segs[i + 1]["duty"] == 1
        cut = segs[i]["duration_s"] - L
        segs[i]["duration_s"] = L
        segs[i + 1]["duration_s"] += cut
    return obj


def main():
    os.makedirs(OUT, exist_ok=True)
    existing = sorted(f for f in os.listdir(CH) if f.endswith(".json"))
    same = sum(1 for f in existing if MC.ser(json.loads(open(os.path.join(CH, f), "rb").read().decode("utf-8"))) == open(os.path.join(CH, f), "rb").read())
    print(f"step0 reserialize identical {same}/{len(existing)}")
    if same != len(existing):
        return 2
    tl = json.loads(open(TL, "rb").read().decode("utf-8"))
    tmpl = load(MC.TEMPLATE)
    report = dict(kind="v3_base_v2_build", registration="d1sim/docs/V3_사전등록_v2.md (d0a513c) §2", main_model=PV.MAIN,
                  columns=list(PV.COLUMNS), R0=PV.R0, decisions=__doc__.split("P1h 가 정함 (결과 전 — v2 칸 0):")[1].split("py -X")[0].strip(),
                  reserialize_identical=f"{same}/{len(existing)}", conditions={})
    rc = 0
    for c, (b1, o1, b2) in COND.items():
        vb, vo = load(b1), load(o1)
        arr = tl["conditions"][c]["burst_starts_s"]
        zb, sb = zones(vb, arr)
        zo, so = zones(vo, arr)
        assert sb == so == REG_SIGMA[c]
        zcheck = dict(base=zb, ours=zo, registration=REG_ZONES[c], equal=(zb == REG_ZONES[c]["base"] and zo == REG_ZONES[c]["ours"]))
        print(f"{c} arrivals {[round(a, 1) for a in arr]} zones base {zb} ours {zo} == registration {zcheck['equal']}")
        if not zcheck["equal"]:
            print("zone mismatch with registration §2-1 — stop")
            return 4
        n_ours = {str(T0): zone_n(vo, zo, PV.MAIN, T0) for T0 in PV.COLUMNS}
        v1L = [s["duration_s"] for s in vb["segments"] if s["duty"] == 100]
        Ls, search = [], []
        for k in range(len(v1L)):
            chosen, flag = None, None
            for L in range(10, v1L[k] + 1, 10):
                ch = base_with(vb, Ls + [L])
                nb = {str(T0): zone_n(ch, zb, PV.MAIN, T0) for T0 in PV.COLUMNS}
                ok = all(nb[str(T0)][k] >= n_ours[str(T0)][k] for T0 in PV.COLUMNS)
                if L >= v1L[k] - 60 or ok:
                    search.append(dict(k=k + 1, L=L, n_base={t: nb[t][k] for t in nb}, n_ours={t: n_ours[t][k] for t in n_ours}, ok=ok))
                if ok:
                    chosen = L
                    break
            if chosen is None:
                chosen, flag = v1L[k], "v1 length kept — condition not met even at v1 length (§2-3)"
                print(f"{c} bundle {k + 1}: {flag}")
            Ls.append(chosen)
            print(f"{c} bundle {k + 1}: L v1 {v1L[k]} -> v2 {chosen}  n_ours {[round(n_ours[str(T)][k]) for T in PV.COLUMNS]}")
        nb_final = base_with(vb, Ls)
        nb_final["chain_id"] = b2
        for i, s in enumerate(nb_final["segments"]):
            s["label"] = f"s{i:02d}_d{s['duty']}"
        # format check: every segment = template segment 0 apart from label/duty/duration_s
        t0 = {k: v for k, v in tmpl["segments"][0].items() if k not in ("label", "duty", "duration_s")}
        assert all({k: v for k, v in s.items() if k not in ("label", "duty", "duration_s")} == t0 for s in nb_final["segments"])
        assert [k for k in nb_final if k != "segments"] == [k for k in vb if k != "segments"]
        st_v1, _ = seg_starts(vb)
        st_v2, sig2 = seg_starts(nb_final)
        d100_starts_same = [st_v1[i] for i, s in enumerate(vb["segments"]) if s["duty"] == 100] == [st_v2[i] for i, s in enumerate(nb_final["segments"]) if s["duty"] == 100]
        assert sig2 == REG_SIGMA[c] and len(nb_final["segments"]) == len(vb["segments"]) == 7 and d100_starts_same
        n_base_z = {str(T0): zone_n(nb_final, zb, PV.MAIN, T0) for T0 in PV.COLUMNS}
        # whole-chain r, 4 models
        rtab, nmax = {}, {}
        for m in PV.MODELS:
            for T0 in PV.COLUMNS:
                rb, _e = PV.simulate(m, PV.schedule(nb_final), T0)
                ro, _f = PV.simulate(m, PV.schedule(vo), T0)
                mb, mo = PV.run_metrics(nb_final, rb, _e), PV.run_metrics(vo, ro, _f)
                rtab.setdefault(m, {})[str(T0)] = dict(r_with_d1_est=mo["n_with_d1_est"] / mb["n_with_d1_est"], r_model=mo["n_model"] / mb["n_model"],
                                                       n_base_with_d1_est=mb["n_with_d1_est"], n_ours_with_d1_est=mo["n_with_d1_est"])
                nmax[m + "@" + str(T0)] = mb["n_with_d1_est"]
        mx = max(nmax.values())
        spans = int(math.ceil(1.3 * mx / 100_000.0)) * 100_000
        rmain = {t: rtab[PV.MAIN][t]["r_with_d1_est"] for t in rtab[PV.MAIN]}
        stop = any(not (R_LO <= v <= R_HI) for v in rmain.values())
        data = MC.ser(nb_final)
        path = os.path.join(CH, b2 + ".json")
        info = dict(base_v1=b1, ours_v1=o1, base_v2=b2, arrivals_s=arr, zones=zcheck, L_v1=v1L, L_v2=Ls,
                    segments_v2=[(s["duty"], s["duration_s"]) for s in nb_final["segments"]], sigma_s=sig2, d100_starts_same=d100_starts_same,
                    n_ours_zone=n_ours, n_base_zone_v2=n_base_z, search_tail=search, r=rtab, r_main=rmain, stop_condition_hit=stop,
                    span_n_max_pred=mx, span_ceiling=spans, file_sha256=hashlib.sha256(data).hexdigest())
        report["conditions"][c] = info
        print(f"{c} v2 segments {' '.join(f'd{d}x{L}' for d, L in info['segments_v2'])} Σ {sig2}")
        for m in PV.MODELS:
            print(f"   r {m:8s} " + "  ".join(f"{t}: {rtab[m][t]['r_with_d1_est']:.4f} (model {rtab[m][t]['r_model']:.4f})" for t in rtab[m]))
        print(f"   span ceiling {spans} (max pred n {mx:.0f})")
        if stop:
            print(f"{c}: §2-4 stop condition — main r {rmain} outside [{R_LO}, {R_HI}] — chain NOT written")
            rc = 6
            continue
        if os.path.exists(path):
            if open(path, "rb").read() == data:
                print("exists, identical:", b2)
            else:
                print("EXISTS and differs, not overwritten:", b2)
                return 3
        else:
            open(path, "wb").write(data)
            print(f"wrote {b2}.json sha256 {info['file_sha256']}")
    p = os.path.join(OUT, "base_v2_build.json")
    open(p, "w", encoding="utf-8", newline="\n").write(json.dumps(report, indent=1, ensure_ascii=False))
    print("->", p, sha(p))
    return rc


if __name__ == "__main__":
    sys.exit(main())
