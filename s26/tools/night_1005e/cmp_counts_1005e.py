# -*- coding: utf-8 -*-
"""Night 1005e (copy of the 1005n script, path only): per-target 맞음/틀림 counts from cmp_1005n.json (frozen judge output). Read-only."""
import json, sys
sys.stdout.reconfigure(encoding="utf-8")
P = r"C:\Users\rhoyo\OneDrive\문서\Mine\26-2\산공학회\D1_ondevice\sim\out_1005e\cmp_1005e.json"
j = json.load(open(P, encoding="utf-8"))
cols = [(m, v) for m, mv in j["results"].items() for v in mv["variants"]]
order = ["v21", "v2", "v1"]
cols.sort(key=lambda x: order.index(x[0]))
targets = []
first = j["results"][cols[0][0]]["variants"][cols[0][1]]
for r in first["runs"]:
    targets.append(("runs", (r["cell"], r["block"]), f"{r['cell']}_b{r['block']}"))
for p in first["pairs"]:
    targets.append(("pairs", (p["resource"], p["block"]), f"{p['resource']} 쌍 b{p['block']}"))
print("| 대상 | 열 (v2.1) | " + " | ".join(f"{m} {v}" for m, v in cols) + " |")
print("|---|---|" + "---:|" * len(cols))
for kind, key, name in targets:
    cells = []
    colname = ""
    for m, v in cols:
        items = j["results"][m]["variants"][v][kind]
        it = [x for x in items if (x.get("cell", x.get("resource")), x["block"]) == key][0]
        if not it.get("supported", True) or not it.get("rows"):
            cells.append("unsupported"); continue
        c = {"맞음": 0, "틀림": 0}
        for r in it["rows"]:
            if r["verdict"] in c:
                c[r["verdict"]] += 1
        cells.append(f"{c['맞음']} / {c['틀림']}")
        if m == "v21":
            colname = it.get("column", "")
    print(f"| {name} | {colname} | " + " | ".join(cells) + " |")
row = []
for m, v in cols:
    rv = j["results"][m]["variants"][v]["resources"]
    row.append(" · ".join(f"{k} {rv[k]['verdict'] if 'measured' not in rv[k] else rv[k]['verdict'] + ' (예측 ' + rv[k]['predicted'] + ')'}" for k in ("NPU", "GPU")))
print("| 자원 판정 | | " + " | ".join(row) + " |")
