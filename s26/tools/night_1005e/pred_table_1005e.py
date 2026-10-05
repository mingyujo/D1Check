"""NIGHT 1005e: markdown tables of the frozen EffNet predictions (d1sim/out/night_1005e_prediction_{v21,v2,v1}.json) for sim/v21_예측_밤1005e.md."""
import json, sys
sys.stdout.reconfigure(encoding="utf-8")
OUT = r"C:\Users\rhoyo\AndroidStudioProjects\D1Check_v4\d1sim\out"


def f(x, nd=1):
    if x is None:
        return "없음"
    if isinstance(x, (int, float)):
        return f"{x:,.{nd}f}"
    return str(x)


for m in ("v21", "v2", "v1"):
    R = json.load(open(f"{OUT}\\night_1005e_prediction_{m}.json", encoding="utf-8"))
    print(f"\n### {m} — {R['model']}\n")
    print("| 칸 | 열 | 첫 조임 s | 조임 시간 s | 최고 SKIN | t38 s | t40 s | 899 s SKIN | 처리율 /s | n |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for c, cols in R["cells"].items():
        for col, v in cols.items():
            print(f"| {c} | {col} | {f(v['first_throttle_s'],0)} | {f(v['throttle_time_s'],0)} | {f(v['max_skin'],2)} | {f(v['t38_s'],0)} | {f(v['t40_s'],0)} | "
                  f"{f(v['skin_899'],2)} | {f(v['rate_per_s'],1)} | {f(v['n'],0)} |")
    print("\n| 자원 | 열 | 일 비 | ΔSKIN | Δt38 | Δt40 | Δ조임 | 부호 (SKIN·t38·t40·조임) | B t38 잘림 | 판정 (2쌍 같다고 볼 때) |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for r, cols in R["pairs"].items():
        for col, v in cols.items():
            s = v["signs"]
            print(f"| {r} | {col} | {v['work_ratio']:.3f} | {f(v['d_max_skin'],2)} | {f(v['d_t38_s'],0)} | {f(v['d_t40_s'],0)} | {f(v['d_throttle_time_s'],0)} | "
                  f"{s['d_max_skin']}{s['d_t38_s']}{s['d_t40_s']}{s['d_throttle_time_s']} | {v.get('b_t38_cut') or '—'} | {R['resources'][r][col]['verdict']} |")
