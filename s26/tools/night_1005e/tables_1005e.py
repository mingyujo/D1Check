# -*- coding: utf-8 -*-
"""Night 1005e: markdown tables straight from the frozen judge outputs (sim\\out_1005e\\*.json) — copy of tables_1005n.py with
EffNet cell names, the _re JSONs, model-SHA / watch columns and the 'B t38 잘림 가능' column. Read-only, no judgement here.
Usage: py -X utf8 tables_1005e.py [NPU|GPU|ALL]"""
import json, os, sys
sys.stdout.reconfigure(encoding="utf-8")
D = r"C:\Users\rhoyo\OneDrive\문서\Mine\26-2\산공학회\D1_ondevice\sim\out_1005e"
RES = {"NPU": ("NAe", "NBe"), "GPU": ("GAe", "GBe")}


def load(n):
    p = os.path.join(D, n + ".json")
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else None


def names(c, b):
    return [n for n in (f"{c}_b{b}", f"{c}_b{b}_re") if load(n)]


def runs_table(cells):
    print("| 런 JSON | 시작 SKIN / AP / BAT (load_start) | 밴드 · 하한 | 게이트 label · SKIN / AP / BAT · SOC | work n | 처리율 /s | ref30 ms | 첫 조임 | 조임 시간 s | 최고 SKIN / AP / BAT | t38 / t40 / t42 s | status≥1 s | work 끝 SKIN / AP | 899 s SKIN / AP / BAT | 쉼 n | 모델 SHA | 감시 (표본 · 이벤트 · 최대 간격 s) |")
    print("|---|---|---|---|---:|---:|---:|---|---:|---|---|---:|---|---|---:|---|---|")
    for b in (1, 2):
        for c in cells:
            ns = names(c, b)
            if not ns:
                print(f"| {c}_b{b} | (판정 JSON 없음) |"); continue
            for n in ns:
                j = load(n)
                s, w, t = j["start"], j["work"], j["temps"]
                st, g = s["start_thermal"], s.get("gate_row") or {}
                pw = j.get("phone_watch") or {}
                print(f"| {n} | {st['SKIN']} / {st['AP']} / {st['BAT']} | {s['band']} · {s['lower']['label']} | {g.get('label')} · {g.get('SKIN')} / {g.get('AP')} / {g.get('BAT')} · {g.get('soc')} | {w['n']:,} | {w['rate_per_s']:.1f} | {w['ref30_ms']:.4f} | {w['first_throttle_label']} | {w['throttle_time_s']} | {t['max_SKIN']} / {t['max_AP']} / {t['max_BAT']} | {t['t38_s']} / {t['t40_s']} / {t['t42_s']} | {t['status_ge1_s']} | {w['end_thermal']['SKIN']} / {w['end_thermal']['AP']} | {t['at_899']['SKIN']} / {t['at_899']['AP']} / {t['at_899']['BAT']} | {j['tail']['n']:,} | {j['model_sha_check']['label']} | {pw.get('n_samples')} · {pw.get('n_events')} · {pw.get('max_gap_s')} |")


def bins_table(cells):
    print("| 런 | 10 s 칸 배율 (ref30 기준, 칸 0 부터) |")
    print("|---|---|")
    for b in (1, 2):
        for c in cells:
            for n in names(c, b):
                j = load(n)
                print(f"| {n} | " + " ".join(f"{x['ratio']:.3f}" for x in j["work"]["bins"]) + " |")


def pairs_table(tag):
    print("| 쌍 | A 시작 SKIN | B 시작 SKIN | n_A | n_B | 일 비 | 같은 일 | 처리율 A / B (비) | B 가 같은 일에 닿은 시각 (−300 s) | Δ최고 SKIN ℃ | Δt38 s | Δt40 s | Δt42 s (기술) | Δ조임 시간 s | 부호 (SKIN · t38 · t40 · 조임) | B 899 s SKIN · B t38 잘림 |")
    print("|---|---:|---:|---:|---:|---:|---|---|---|---:|---:|---:|---:|---:|---|---|")
    for b in (1, 2):
        p = load(f"pair_{tag}_b{b}")
        if not p:
            print(f"| {tag}_b{b} | (쌍 JSON 없음) |"); continue
        d, sg, cut = p["deltas"], p["signs"], p.get("b_t38_cut") or {}
        print(f"| {tag}_b{b} | {p['a']['start_skin']} | {p['b']['start_skin']} | {p['n_a']:,} | {p['n_b']:,} | {p['work_ratio']:.3f} | {p['same_work_label']} | {p['rate_a']:.1f} / {p['rate_b']:.1f} ({p['rate_ratio_b_over_a']:.3f}) | {p['b_reach_label']} ({p['b_reach_minus_300_s']}) | {d['d_max_skin']:+.1f} | {d['d_t38_s']:+.0f} | {d['d_t40_s']:+.0f} | {d['d_t42_s']:+.0f} | {d['d_throttle_time_s']:+.0f} | {sg['d_max_skin']} {sg['d_t38_s']} {sg['d_t40_s']} {sg['d_throttle_time_s']} | {cut.get('b_skin_899')} · {cut.get('label') or '없음'} |")


def resource_line(tag):
    r = load(f"res_{tag}")
    if not r:
        print(f"(res_{tag}.json 없음)"); return
    print(json.dumps({k: v for k, v in r.items() if k not in ("imports", "imports_e", "order")}, ensure_ascii=False, indent=1))


which = (sys.argv[1] if len(sys.argv) > 1 else "ALL").upper()
for name, (a, bb) in RES.items():
    if which not in ("ALL", name):
        continue
    print(f"\n## {name}\n\n### 런 지표\n")
    runs_table([a, bb])
    print("\n### 10 s 칸 배율\n")
    bins_table([a, bb])
    print("\n### 쌍\n")
    pairs_table(name)
    print("\n### 자원 판정 (res JSON)\n")
    resource_line(name)
