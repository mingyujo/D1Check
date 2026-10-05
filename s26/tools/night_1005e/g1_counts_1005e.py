# -*- coding: utf-8 -*-
"""Night 1005e: prereg night1005e s9 G1 (new) numbers only — per model/variant: resource verdict phrases right (of 2) and
pair-delta items right (Δ최고 SKIN · Δt38 · Δt40 · Δ조임 시간, 2 resources x 2 pairs x 4 = 16). Read-only copy of cmp_1005e.json values."""
import json, sys
sys.stdout.reconfigure(encoding="utf-8")
P = r"C:\Users\rhoyo\OneDrive\문서\Mine\26-2\산공학회\D1_ondevice\sim\out_1005e\cmp_1005e.json"
j = json.load(open(P, encoding="utf-8"))
ITEMS = ("Δ최고 SKIN (℃)", "Δt38 (s)", "Δt40 (s)", "Δ조임 시간 (s)")
print("| 모형 · 변형 | 자원 판정 맞힘 (/2) | 쌍 차이 4항목 맞힘 (/16) | 기준 (2/2 이고 ≥ 9) |")
print("|---|---:|---:|---|")
for m in ("v21", "v2", "v1"):
    for v, vv in j["results"][m]["variants"].items():
        rv = vv["resources"]
        res_ok = sum(1 for k in ("NPU", "GPU") if k in rv and rv[k].get("verdict") == "맞음")
        n_ok = n_all = 0
        for p in vv["pairs"]:
            for r in p.get("rows", []):
                if r["cell"] in ITEMS:
                    n_all += 1
                    n_ok += r["verdict"] == "맞음"
        print(f"| {m} · {v} | {res_ok} | {n_ok} (/{n_all}) | {'넘음' if res_ok == 2 and n_ok >= 9 else '못 넘음'} |")
