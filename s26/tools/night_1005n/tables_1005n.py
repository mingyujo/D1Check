# -*- coding: utf-8 -*-
"""Night 1005n: print markdown tables straight from the frozen judge outputs (sim\\out_1005n\\*.json).
Read-only. No judgement here — every value is copied from night1005_judge.py output (run / pair / resource / cmp).
Usage: py -X utf8 tables_1005n.py [NPU|GPU|ALL]"""
import json, os, sys
sys.stdout.reconfigure(encoding="utf-8")
D = r"C:\Users\rhoyo\OneDrive\문서\Mine\26-2\산공학회\D1_ondevice\sim\out_1005n"
RES = {"NPU": ("NA", "NB", "N"), "GPU": ("GA", "GB", "G")}
ORDER = {1: ["NA", "GB", "NB", "GA"], 2: ["GA", "NB", "GB", "NA"]}


def load(n):
    p = os.path.join(D, n + ".json")
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else None


def runs_table(cells):
    print("| 칸 | 블록 | 시작 SKIN / AP / BAT (load_start) | 밴드 · 하한 | 게이트 SKIN / AP / BAT · SOC | work n | 처리율 /s | ref30 ms | 첫 조임 | 조임 시간 s | 최고 SKIN / AP / BAT | t38 / t40 / t42 s | status≥1 s | work 끝 SKIN / AP | 899 s SKIN / AP / BAT | 쉼 n |")
    print("|---|---|---|---|---|---:|---:|---:|---|---:|---|---|---:|---|---|---:|")
    for b in (1, 2):
        for c in cells:
            j = load(f"{c}_b{b}")
            if not j:
                print(f"| {c} | {b} | (판정 JSON 없음) |"); continue
            s, w, t = j["start"], j["work"], j["temps"]
            st, g = s["start_thermal"], s.get("gate_row") or {}
            print(f"| {c} | {b} | {st['SKIN']} / {st['AP']} / {st['BAT']} | {s['band']} · {s['lower']['label']} | {g.get('SKIN')} / {g.get('AP')} / {g.get('BAT')} · {g.get('soc')} | {w['n']:,} | {w['rate_per_s']:.1f} | {w['ref30_ms']:.4f} | {w['first_throttle_label']} | {w['throttle_time_s']} | {t['max_SKIN']} / {t['max_AP']} / {t['max_BAT']} | {t['t38_s']} / {t['t40_s']} / {t['t42_s']} | {t['status_ge1_s']} | {w['end_thermal']['SKIN']} / {w['end_thermal']['AP']} | {t['at_899']['SKIN']} / {t['at_899']['AP']} / {t['at_899']['BAT']} | {j['tail']['n']:,} |")


def bins_table(cells):
    print("| 칸·블록 | 10 s 칸 배율 (ref30 기준, 칸 0 부터) |")
    print("|---|---|")
    for b in (1, 2):
        for c in cells:
            j = load(f"{c}_b{b}")
            if j:
                print(f"| {c}_b{b} | " + " ".join(f"{x['ratio']:.3f}" for x in j["work"]["bins"]) + " |")


def pairs_table(tag):
    print("| 쌍 | A 시작 SKIN | B 시작 SKIN | n_A | n_B | 일 비 | 같은 일 | 처리율 A / B (비) | B 가 같은 일에 닿은 시각 (−300 s) | Δ최고 SKIN ℃ | Δt38 s | Δt40 s | Δt42 s (기술) | Δ조임 시간 s | 부호 (SKIN · t38 · t40 · 조임) |")
    print("|---|---:|---:|---:|---:|---:|---|---|---|---:|---:|---:|---:|---:|---|")
    for b in (1, 2):
        p = load(f"pair_{tag}_b{b}")
        if not p:
            print(f"| {tag}_b{b} | (쌍 JSON 없음) |"); continue
        d, sg = p["deltas"], p["signs"]
        print(f"| {tag}_b{b} | {p['a']['start_skin']} | {p['b']['start_skin']} | {p['n_a']:,} | {p['n_b']:,} | {p['work_ratio']:.3f} | {p['same_work_label']} | {p['rate_a']:.1f} / {p['rate_b']:.1f} ({p['rate_ratio_b_over_a']:.3f}) | {p['b_reach_label']} ({p['b_reach_minus_300_s']}) | {d['d_max_skin']:+.1f} | {d['d_t38_s']:+d} | {d['d_t40_s']:+d} | {d['d_t42_s']:+d} | {d['d_throttle_time_s']:+d} | {sg['d_max_skin']} {sg['d_t38_s']} {sg['d_t40_s']} {sg['d_throttle_time_s']} |")


def resource_line(tag):
    r = load(f"resource_{tag}")
    if not r:
        print(f"(resource_{tag}.json 없음)"); return
    print(json.dumps({k: v for k, v in r.items() if k not in ("imports",)}, ensure_ascii=False, indent=1))


which = (sys.argv[1] if len(sys.argv) > 1 else "ALL").upper()
for name, (a, bb, tag) in RES.items():
    if which not in ("ALL", name):
        continue
    print(f"\n## {name}\n\n### 런 지표\n")
    runs_table([a, bb])
    print("\n### 10 s 칸 배율\n")
    bins_table([a, bb])
    print("\n### 쌍\n")
    pairs_table(tag)
    print("\n### 자원 판정 (resource JSON)\n")
    resource_line(tag)
