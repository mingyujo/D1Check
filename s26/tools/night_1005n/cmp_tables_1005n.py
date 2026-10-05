# -*- coding: utf-8 -*-
"""Night 1005n: print cmp_1005n.json (frozen judge cmp output) as markdown tables. Read-only, copies values only."""
import json, sys
from collections import Counter
sys.stdout.reconfigure(encoding="utf-8")
P = r"C:\Users\rhoyo\OneDrive\문서\Mine\26-2\산공학회\D1_ondevice\sim\out_1005n\cmp_1005n.json"
j = json.load(open(P, encoding="utf-8"))
mode = sys.argv[1] if len(sys.argv) > 1 else "all"
if mode == "keys":
    for m, mv in j["results"].items():
        print(m, list(mv.keys()))
        for v, vv in mv["variants"].items():
            print("  ", v, {k: (type(x).__name__, len(x) if hasattr(x, "__len__") else x) for k, x in vv.items()})
    sys.exit()
summary = []
for m, mv in j["results"].items():
    for v, vv in mv["variants"].items():
        tot = Counter()
        print(f"\n### {m} · {v}\n")
        for kind in ("runs", "pairs", "resources"):
            items = vv.get(kind) or []
            if kind == "resources":
                print("\n**resources**\n")
                print("| 자원 | 열 | 실측 판정 | 예측 판정 | 결과 |")
                print("|---|---|---|---|---|")
                for res, rv in items.items():
                    if "measured" in rv:
                        tot[rv["verdict"]] += 1
                    print(f"| {res} | {rv.get('columns','')} | {rv.get('measured','')} | {rv.get('predicted','')} | {rv['verdict']} |")
                continue
            if not items:
                continue
            print(f"\n**{kind}**\n")
            print("| 대상 | 열 | 항목 | 실측 | 예측 | 기준 | 판정 | 차 |")
            print("|---|---|---|---|---|---|---|---|")
            for it in items:
                tgt = it.get("cell") or it.get("resource")
                if kind == "runs":
                    tgt = f"{it.get('cell')}_b{it.get('block')}"
                elif kind == "pairs":
                    tgt = f"{it.get('resource')} 쌍 b{it.get('block')}"
                col = it.get("column")
                if not it.get("supported", True):
                    print(f"| {tgt} | {col} | (unsupported — 시작 SKIN {it.get('start_skin', it.get('mean_start_skin'))} 범위 밖) | | | | unsupported | |")
                    tot["unsupported"] += 1
                    continue
                for r in it.get("rows", []):
                    tot[r["verdict"]] += 1
                    print(f"| {tgt} | {col} | {r['cell']} | {r['measured']} | {r['predicted']} | {r['criterion']} | {r['verdict']} | {r.get('if_wrong','')} |")
        summary.append((m, v, dict(tot)))
print("\n### 합계 (맞음 / 틀림 / 기술 / unsupported 항목 수)\n")
print("| 모형 | 변형 | 맞음 | 틀림 | 기술 | unsupported (런·쌍 단위) |")
print("|---|---|---:|---:|---:|---:|")
for m, v, t in summary:
    print(f"| {m} | {v} | {t.get('맞음',0)} | {t.get('틀림',0)} | {t.get('기술',0)} | {t.get('unsupported',0)} |")
