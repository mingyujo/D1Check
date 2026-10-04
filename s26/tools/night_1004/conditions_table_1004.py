"""Build the per-run conditions table for the night 1004 report from gate CSV, session_log, manifests and judge outputs (read-only).
Serial never appears (session_log already <SERIAL>)."""
import csv, json, os, re, sys, glob
sys.stdout.reconfigure(encoding="utf-8")
R = r"C:\Users\rhoyo\AndroidStudioProjects\D1Check_v4\results"
H = os.path.join(R, "S26_night_1004_host")
OUT = r"C:\Users\rhoyo\OneDrive\문서\Mine\26-2\산공학회\D1_ondevice\sim\out_1004"
cells = [("2 N50P", "02_N50P", "S26_N50P_1004", "N50P.json"),
         ("3-1 G50", "03_01_gpu50", "S26_EffB2_01_gpu50_1004", None), ("3-2 G100", "03_02_gpu100", "S26_EffB2_02_gpu100_1004", None),
         ("3-3 C50", "03_03_cpu50", "S26_EffB2_03_cpu50_1004", None), ("3-4 C100", "03_04_cpu100", "S26_EffB2_04_cpu100_1004", None),
         ("3-5 C100", "03_05_cpu100", "S26_EffB2_05_cpu100_1004", None), ("3-6 C50", "03_06_cpu50", "S26_EffB2_06_cpu50_1004", None),
         ("3-7 G100", "03_07_gpu100", "S26_EffB2_07_gpu100_1004", None), ("3-8 G50", "03_08_gpu50", "S26_EffB2_08_gpu50_1004", None),
         ("4 G50P", "04_G50P", "S26_G50P_1004", "G50P.json"), ("5 GI300", "05_GI300", "S26_GI300_1004", "GI300.json"),
         ("6 NI300", "06_NI300", "S26_NI300_1004", "NI300.json"), ("7 EffN420", "07_EffN420", "S26_EffN420_npu_1004", None)]
gates = {}
for r in csv.DictReader(open(os.path.join(H, "gate_log_1004.csv"), encoding="utf-8")):
    if r["pass"] == "True":
        gates[r["label"]] = r
launch = {}
for line in open(os.path.join(H, "session_log.txt"), encoding="utf-8-sig"):
    m = re.match(r"\[(.+?)\] (\S+) pid=\d+ out=(\S+) MemAvailable: (\d+) kB\s+level: (\d+)", line.strip())
    if m:
        launch[m.group(3)] = dict(time=m.group(1), mem=int(m.group(4)), level=int(m.group(5)))
blk = json.load(open(os.path.join(OUT, "EffB2_block.json"), encoding="utf-8")) if os.path.exists(os.path.join(OUT, "EffB2_block.json")) else None
blk_runs = {x["result_dir"]: x for x in (blk or {}).get("runs", [])}
print("| 칸 | 게이트 통과 · 대기 | SKIN / AP / BAT | SOC | MemAvailable kB | pilot_pct | load_start SKIN | 슬롯 · valid | 시작 (manifest, KST) ~ 끝 |")
print("|---|---|---|---|---:|---:|---|---|---|")
for lab, glab, out, jf in cells:
    g = gates.get(glab)
    mp = os.path.join(R, out, "experiment_manifest.json")
    man = json.load(open(mp, encoding="utf-8")) if os.path.exists(mp) else None
    slot = (man or {}).get("runs", [{}])[0] if man else {}
    v = slot.get("validation") or {}
    pilot = None; ls = None
    if jf and os.path.exists(os.path.join(OUT, jf)):
        j = json.load(open(os.path.join(OUT, jf), encoding="utf-8"))
        pilot = j.get("pilot_battery_pct"); ls = j.get("start_skin")
    elif out in blk_runs:
        x = blk_runs[out]; pilot = x.get("pilot_battery_pct"); ls = x["thermal"]["load_start"]["SKIN"]
    else:
        rs = glob.glob(os.path.join(R, out, "exports-v2", "run_summary.csv"))
        if rs:
            for row in csv.DictReader(open(rs[0], encoding="utf-8")):
                ls = row.get("skin_load_start_temperature_c")
    def kst(u):
        if not u:
            return "?"
        hh, mm, ss = int(u[11:13]), u[14:16], u[17:19]
        return f"{(hh + 9) % 24:02d}:{mm}:{ss}"
    la = launch.get(out, {})
    gl = f"{g['local_time'][11:19]} · {g['waited_s']} s" if g else "?"
    gt = f"{g['SKIN']} / {g['AP']} / {g['BAT']}" if g else "?"
    print(f"| {lab} | {gl} | {gt} | {g['soc'] if g else '?'} | {la.get('mem', '?'):,} | {pilot} | {ls} | {slot.get('status')} · {v.get('valid')} | {kst((man or {}).get('started_utc'))} ~ {kst((man or {}).get('completed_utc'))} |"
          if isinstance(la.get('mem'), int) else
          f"| {lab} | {gl} | {gt} | {g['soc'] if g else '?'} | ? | {pilot} | {ls} | {slot.get('status')} · {v.get('valid')} | {kst((man or {}).get('started_utc'))} ~ {kst((man or {}).get('completed_utc'))} |")
