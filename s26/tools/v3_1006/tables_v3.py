"""V3 1006: report tables from the judge JSONs (OneDrive sim/out_v3_1006) + gate CSV + run folders. Reads only.
Prints Markdown rows: run table (gate · previous cell · rest · order · start SKIN/BAT · SOC · metrics), block table, prediction comparison.
Rest = this run's segment 0 start wall − previous run's last segment end wall (runner wall_ms via m1m2_judge_1002._wall_at).
usage: py -X utf8 tables_v3.py [A|B]
"""
import csv, datetime, glob, importlib.util, json, os, sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = r"C:\Users\rhoyo\AndroidStudioProjects\D1Check_v4"
SIM = r"C:\Users\rhoyo\OneDrive\문서\Mine\26-2\산공학회\D1_ondevice\sim"
OUTV = os.path.join(SIM, "out_v3_1006")
H = os.path.join(ROOT, "results", "S26_host_v3_1006")
COND = sys.argv[1] if len(sys.argv) > 1 else "A"
spec = importlib.util.spec_from_file_location("m1m2_judge_1002", os.path.join(SIM, "m1m2_judge_1002.py"))
J = importlib.util.module_from_spec(spec); spec.loader.exec_module(J)


def f(x, nd=2):
    return "—" if x is None else (f"{x:.{nd}f}" if isinstance(x, float) else str(x))


def walls(out_name):
    rd = glob.glob(os.path.join(ROOT, "results", out_name, "runs", "*"))
    if len(rd) != 1:
        return None
    try:
        S = J.segments_of(J.load_run(rd[0]))
    except J.JudgeError:
        return None            # invalid slot without a runner JSONL on the host
    return S["segments"][0]["start_wall_ms"], S["segments"][-1]["end_wall_ms"]


def main():
    st = json.load(open(os.path.join(H, f"driver_state_v3_{COND}.json"), encoding="utf-8-sig"))
    gates = {r["label"]: r for r in csv.DictReader(open(os.path.join(H, "gate_log_v3.csv"), encoding="utf-8-sig"))}
    order = []
    for line in open(os.path.join(H, "driver_v3_log.txt"), encoding="utf-8-sig"):
        if "] CELL " in line and " -> S26_V3_" in line and "label=" in line:
            key = line.split("] CELL ")[1].split(" ->")[0]
            out = line.split(" -> ")[1].split(" ")[0]
            lab = line.split("label=")[1].split(" ")[0]
            order.append((key, out, lab))
    rows, prev_end, prev_key = [], None, None
    print("| # | 칸 | 블록 · 순서 | 게이트 label · 행동 | 게이트 SKIN / AP / BAT · SOC · 기다림 | 직전 칸 | 직전 쉼 (구간 끝 → 구간 0 시작) | 시작 SKIN / BAT (HAL) | 최고 SKIN / AP / BAT | t38 / t40 / t42 s | 조임 s | 창 끝 SKIN | n | status ≥ 1 s | 모델 SHA | 감시 | 슬롯 |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for i, (key, out, lab) in enumerate(order, 1):
        g = gates.get(lab, {})
        jp = os.path.join(OUTV, f"{key}.json")
        status = st["cells"].get(key, "—")
        j = json.load(open(jp, encoding="utf-8")) if os.path.exists(jp) else None
        w = walls(out) if os.path.isdir(os.path.join(ROOT, "results", out)) else None
        rest = None if (w is None or prev_end is None) else (w[0] - prev_end) / 1000.0
        if j:
            t, s0 = j["temps"], j["start"]["start_thermal"] or {}
            blk = j["block"]
            pos = "1 (기준선 먼저)" if (blk == 1 and j["role"] == "base") or (blk == 2 and j["role"] == "ours") else "2"
            pw = j.get("phone_watch") or {}
            print(f"| {i} | {key} | b{blk} · {pos} | {lab} · {g.get('action', '—')} | {g.get('SKIN')} / {g.get('AP')} / {g.get('BAT')} · {g.get('soc')} · {g.get('waited_s')} s | "
                  f"{prev_key or '— (세션 첫 칸)'} | {f(rest, 0)} s | {f(s0.get('SKIN'), 1)} / {f(s0.get('BAT'), 1)} | {f(t['max_SKIN'], 1)} / {f(t['max_AP'], 1)} / {f(t['max_BAT'], 1)} | "
                  f"{t['t38_s']} / {t['t40_s']} / {t['t42_s']} | {j['work']['throttle_time_s']} | {f((t.get('end') or {}).get('SKIN'), 1)} | {j['work']['n']:,} | {t['status_ge1_s']} | "
                  f"{j['model_sha_check']['label']} | {pw.get('n_events', '—')} 건 | {status} |")
        else:
            print(f"| {i} | {key} | — | {lab} · {g.get('action', '—')} | {g.get('SKIN')} / {g.get('AP')} / {g.get('BAT')} · {g.get('soc')} | {prev_key or '—'} | {f(rest, 0)} | — | — | — | — | — | — | — | — | — | {status} |")
        if w is not None:
            prev_end, prev_key = w[1], key
    for b in (1, 2):
        pp = os.path.join(OUTV, f"pair_{COND}_b{b}.json")
        if os.path.exists(pp):
            p = json.load(open(pp, encoding="utf-8"))
            d = p["deltas"]
            print(f"\n블록 {b}: Δ최고 SKIN {d['d_max_skin']:+.2f} ℃ · Δt38 {d['d_t38_s']:+.0f} · Δt40 {d['d_t40_s']:+.0f} · Δt42 {d['d_t42_s']:+.0f} · Δ조임 {d['d_throttle_time_s']:+.0f} s · "
                  f"Δ창 끝 SKIN {f(d['d_end_skin'])} · ΔAP {f(d['d_max_ap'])} · ΔBAT {f(d['d_max_bat'])} · r {p['r']:.4f} {p.get('r_note') or ''} · 시작 SKIN 평균 {f(p['start_skin_mean'])} · 하한 {p['lower_flags']}")
    cp = os.path.join(OUTV, f"cond_{COND}.json")
    if os.path.exists(cp):
        c = json.load(open(cp, encoding="utf-8"))
        print("\n③", c["j3"]["sentence"])
        print("④ (v2.2)", c["j4_main"]["label"], [(b["column"], b["pred_d"], b["meas_d"], b["abs_diff"], b["sign_same"], b["pred_r"]) for b in c["j4_main"]["blocks"]])
        for m, v in c["j4_sensitivity"].items():
            print("   민감도", m, v["label"], [(b["column"], round(b["pred_d"], 2), b["abs_diff"], b["sign_same"]) for b in v["blocks"]])
        print("결론 표:", c["conclusion"])


if __name__ == "__main__":
    main()
