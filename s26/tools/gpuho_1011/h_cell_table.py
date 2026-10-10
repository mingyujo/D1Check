"""GPU holdout (GH 1011) copy of energy_1008/c_cell_table.py — changed only: host dir S26_host_gpuho_1011 · gate_log_h.csv · judge outputs sim/out_gpuho (QC columns stay empty — no energy QC).\nEnergy C session cell table (P1i — 충전 단계 · 4단계): gate · previous cell · rest · start SKIN / BAT · SOC · run QC (§2-9) · lower mark.
NO energy numbers (no E · ΔE · R) — prereg §4 (pair numbers only in judgeC, once). Reads host logs + sim/out_<sfx> JSONs (thermal run, qc, watch).
  py -X utf8 h_cell_table.py 1011h
"""
import csv, json, os, re, sys
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8")
H = r"C:\Users\rhoyo\AndroidStudioProjects\D1Check_v4\results\S26_host_gpuho_1011"
SIM = r"C:\Users\rhoyo\OneDrive\문서\Mine\26-2\산공학회\D1_ondevice\sim"
TS = re.compile(r"^\[(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)")


def t(line):
    m = TS.match(line)
    return datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S") if m else None


gate = {r["label"]: r for r in csv.DictReader(open(os.path.join(H, "gate_log_h.csv"), encoding="utf-8-sig"))}
for sfx in sys.argv[1:]:
    print(f"\n#### 세션 {sfx}\n")
    print("| # | 칸 | 라벨 | 게이트 시각 | 게이트 대기 s | 게이트 SKIN · AP · BAT | SOC | 하한 | 직전 칸 (끝) | 쉼 (직전 끝 → 실행) | 실행 → 끝 | 슬롯 | 감시 이벤트 | 모델 SHA | 시작 SKIN · BAT (HAL) | QC 제외 | ① | 시계 |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    prev_end, prev_name = None, None
    cells = sorted([f for f in os.listdir(H) if f.startswith("cell_") and f.endswith("_log.txt")], key=lambda f: os.path.getmtime(os.path.join(H, f)))
    rows = []
    for f in cells:
        lines = open(os.path.join(H, f), encoding="utf-8-sig").read().splitlines()
        starts = [i for i, ln in enumerate(lines) if "CELL START" in ln and f"_{sfx}" in ln]
        if not starts:
            continue
        lines = lines[starts[-1]:]          # this session's attempt only (a log file can hold an earlier session's lines)
        st = lines[0]
        label = re.search(r"label=(\S+)", st).group(1)
        key = label.split("_", 1)[1]
        launched = next((t(ln) for ln in lines if "LAUNCHED" in ln), None)
        end = next((t(ln) for ln in lines if "CELL END" in ln), None)
        rows.append((launched, key, label, lines, end))
    rows.sort(key=lambda r: r[0] or datetime.max)
    for i, (launched, key, label, lines, end) in enumerate(rows, 1):
        g = gate.get(label, {})
        out = os.path.join(SIM, "out_gpuho")
        jr = os.path.join(out, f"{key}.json")
        jq = os.path.join(out, f"{key}_qc.json")
        jw = os.path.join(out, f"{key}_watch.json")
        th = json.load(open(jr, encoding="utf-8")) if os.path.exists(jr) else {}
        qc = (json.load(open(jq, encoding="utf-8")) if os.path.exists(jq) else {}).get("qc", {})
        wj = json.load(open(jw, encoding="utf-8")) if os.path.exists(jw) else {}
        stt = ((th.get("start") or {}).get("start_thermal") or {})
        slot = next((ln.split("DONE ", 1)[1] for ln in lines if " DONE " in ln), "")
        slot_s = "valid" if "valid=True" in slot else ("invalid" if slot else "—")
        rest = "—" if (prev_end is None or launched is None) else f"{int((launched - prev_end).total_seconds())} s"
        dur = "—" if (launched is None or end is None) else f"{int((end - launched).total_seconds() / 60)} 분"
        lower = "하한 미달 (표시 실행)" if g.get("action") == "run_marked_lower_fail" else ("상한만 (스모크)" if g.get("action") == "run_upper_only" else ("하한 통과" if g.get("action") == "run" else g.get("action", "—")))
        print(f"| {i} | {key} | {label} | {g.get('local_time', '—')[11:19]} | {g.get('waited_s', '—')} | {g.get('SKIN', '—')} · {g.get('AP', '—')} · {g.get('BAT', '—')} | {g.get('soc', '—')} | {lower} | "
              f"{prev_name or '— (세션 첫 칸)'}{'' if prev_end is None else ' (' + prev_end.strftime('%H:%M') + ')'} | {rest} | {dur} | {slot_s} | "
              f"{(wj.get('phone_watch') or {}).get('n_events', '—')} | {(th.get('model_sha_check') or {}).get('label', '—')} | {stt.get('SKIN', '—')} · {stt.get('BAT', '—')} | "
              f"{('제외: ' + ' · '.join(qc['exclusion_reasons'])) if qc.get('excluded') else ('없음' if qc else '—')} | {qc.get('unit_1', '—')} | {qc.get('clock_check', '—')} |")
        prev_end, prev_name = end, key
