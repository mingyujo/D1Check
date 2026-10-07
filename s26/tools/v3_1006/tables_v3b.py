"""V3 v2 (P1h 1007): run / pair table for the result documents — reads the judge v2 JSONs (sim/out_v3_1007) and the gate CSV only.
usage: py -X utf8 tables_v3b.py <cell_key> [<cell_key> ...]      e.g. A2_base_b1 A2_ours_b1 A2_base_b2_re
"""
import csv, json, os, sys

sys.stdout.reconfigure(encoding="utf-8")
OUTV = r"C:\Users\rhoyo\OneDrive\문서\Mine\26-2\산공학회\D1_ondevice\sim\out_v3_1007"
GATE = r"C:\Users\rhoyo\AndroidStudioProjects\D1Check_v4\results\S26_host_v3_1007\gate_log_v3b.csv"


def f(x, nd=1):
    return "—" if x is None else (f"{x:.{nd}f}" if isinstance(x, float) else str(x))


gates = list(csv.DictReader(open(GATE, encoding="utf-8-sig")))
print("| 칸 | run_id | 게이트 label · SKIN / AP / BAT · SOC · 하한 | 시작 SKIN | 최고 SKIN / AP / BAT | t38 / t40 / t42 s | 조임 s (칸) | 창 끝 SKIN | n | 하한 표시 | 모델 SHA |")
print("|---|---|---|---:|---|---|---|---:|---:|---|---|")
for key in sys.argv[1:]:
    j = json.load(open(os.path.join(OUTV, key + ".json"), encoding="utf-8"))
    t, w, s = j["temps"], j["work"], j["start"]
    g = s.get("gate_row") or {}
    print(f"| {key} | `{j['run_id'][:8]}` | {g.get('label')} · {g.get('SKIN')} / {g.get('AP')} / {g.get('BAT')} · {g.get('soc')} · {g.get('action')} | "
          f"{f(j['start_skin'])} | {f(t['max_SKIN'])} / {f(t['max_AP'])} / {f(t['max_BAT'])} | {t['t38_s']} / {t['t40_s']} / {t['t42_s']} | "
          f"{w['throttle_time_s']} ({w['n_throttled_bins']}/{w['n_active_bins']}) | {f((t.get('end') or {}).get('SKIN'))} | {w['n']:,} | "
          f"{(s.get('lower') or {}).get('label')} | {j['model_sha_check'].get('label')} |")
    print(f"|   | segments n: " + " · ".join(f"{x['label']} {x['n']:,}" for x in w["n_by_segment"]) + " | status≥1 s " + str(t.get("status_ge1_s")) + " |")
