"""Energy B + V3 description tables (markdown) from sim/out_energy (energy_b_compute.py output). No verdict names (prereg v1 §5).
  py -X utf8 s26\\tools\\energy_1008\\energy_b_tables.py > <md>
"""
import glob, json, os, sys

sys.stdout.reconfigure(encoding="utf-8")
O = r"C:\Users\rhoyo\OneDrive\문서\Mine\26-2\산공학회\D1_ondevice\sim\out_energy"


def f(x, nd=0, sign=False):
    if x is None:
        return "—"
    s = f"{x:+.{nd}f}" if sign else f"{x:.{nd}f}"
    return s


pairs = [json.load(open(p, encoding="utf-8")) for p in sorted(glob.glob(os.path.join(O, "pairs", "*.json")))]
order = ["N2 NPU EffNet", "N1 NPU MobileNet (민감도)", "N2 GPU EffNet", "N1 GPU MobileNet", "V3 v2 A2", "V3 v2 B2"]
for g in order:
    ps = sorted([p for p in pairs if p["group"] == g], key=lambda p: (p["pair_file"].endswith("s.json"), p["block"]))
    print(f"\n#### {g}\n")
    print("| 쌍 | 세션 A / B | 하한 A / B | 제외 | r | E_cc A · B (J) | ΔE_p (J) | ΔE_p / E_cc(A) | ΔE_adj (J) | E_int A · B (J) | ΔE_int (J) | q̄_J (J) | ΔE_p (눈금) | R A · B | 창 E/n A · B (mJ/추론, idle 포함) | 비고 |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for p in ps:
        print(f"| {os.path.basename(p['pair_file'])[:-5]} (b{p['block']}) | {p['session_a']} / {p['session_b']} | {p['lower_a']} / {p['lower_b']} | "
              f"{'제외: ' + ' · '.join(p['exclusion']) if p['excluded'] else '없음'} | {p['r']:.3f} | {f(p['E_cc_a'])} · {f(p['E_cc_b'])} | {f(p['dE_p'], 0, True)} | "
              f"{f(p['dE_pct_of_a'], 1, True)} % | {f(p['dE_adj'], 0, True)} | {f(p['E_int_a'])} · {f(p['E_int_b'])} | {f(p['dE_int'], 0, True)} | {f(p['q_bar_J'], 1)} | "
              f"{f(p['dE_in_ticks'], 2, True)} | {f(p['R_a'], 3)} · {f(p['R_b'], 3)} | {f(p['mJ_per_inf_a'], 2)} · {f(p['mJ_per_inf_b'], 2)} | {p['note'] or ''} |")
print("\n#### V3 v1 (짝 없음 — 부록, 런 값만)\n")
for rp in sorted(glob.glob(os.path.join(O, "runs", "A_base_b1_re__*.json"))):
    j = json.load(open(rp, encoding="utf-8"))
    e, q = j["energy"], j["qc"]
    print(f"- `{os.path.basename(rp)}` 세션 {q['session']} · 제외 {q['excluded']} · 창 {q['window_s']:.0f} s · n {e['n']} · E_cc {e['E_cc_J']:.0f} J · E_int {e['E_int_J']:.0f} J · "
          f"R {e['R_run']:.3f} · q_J {e['q_J']:.1f} J · 창 E/n {e['e_window_mJ_per_inference']:.2f} mJ/추론")
print("\n#### ② 세션 내부 일관성 (§3 — 세션별, 제외 뒤 런 전부)\n")
ss = json.load(open(os.path.join(O, "sessions.json"), encoding="utf-8"))
print("| 세션 | N | R_sum | 편차 | 허용 (3·σ/√N) | σ | ② |")
print("|---|---|---|---|---|---|---|")
for s, v in ss.items():
    print(f"| {s} | {v['N']} | {v['R_sum']:.3f} | {v['dev']:+.3f} | ±{v['tolerance']:.3f} | {v['sigma_source']} | {v['verdict']} |")
print("\n#### 런별 QC (§2-9)\n")
print("| 런 | 세션 | 칸 | 제외 | ① | 시계 | 무효 % | 최대 간격 s | 잔량계 갱신 눈금 분포 |")
print("|---|---|---|---|---|---|---|---|---|")
for rp in sorted(glob.glob(os.path.join(O, "runs", "*.json"))):
    j = json.load(open(rp, encoding="utf-8"))
    q, e = j["qc"], j["energy"]
    print(f"| {os.path.basename(rp)[:-5]} | {q['session']} | {q['cell']} b{q['block']} | {' · '.join(q['exclusion_reasons']) or '없음'} | {q['unit_1']} | {q['clock_check']} | "
          f"{q['invalid_pct']} | {q['max_gap_s']} | {json.dumps(e['drop_ticks_hist'], ensure_ascii=False)} |")
