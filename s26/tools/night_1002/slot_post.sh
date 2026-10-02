#!/usr/bin/env bash
# After one chain slot finished: slot report (validity, flags), judge segments -> out_1002/<tag>_segments.json,
# and (optional) engine comparison on segment 0. Usage: slot_post.sh <result_dir> <tag> [engine]
set -u
cd /c/Users/rhoyo/AndroidStudioProjects/D1Check_v4
R="$1"; TAG="$2"; ENG="${3:-}"
OUT="/c/Users/rhoyo/OneDrive/문서/Mine/26-2/산공학회/D1_ondevice/sim/out_1002"
JUDGE="/c/Users/rhoyo/OneDrive/문서/Mine/26-2/산공학회/D1_ondevice/sim/m1m2_judge_1002.py"
WATCH="results/S26_night_1002_host/skin_watch_1002.csv"
echo "### slot report $R"
py -X utf8 results/S26_night_1002_host/chain_slot_report.py "$R"
RUN=$(ls -d "$R"/runs/*/ 2>/dev/null | head -1)
if [ -z "$RUN" ]; then echo "NO RUN DIR"; exit 1; fi
echo "### judge segments -> $OUT/${TAG}_segments.json"
py -X utf8 "$JUDGE" segments "$RUN" --watch "$WATCH" --out "$OUT/${TAG}_segments.json" > /dev/null && \
py -X utf8 -c "
import json,sys
d=json.load(open(sys.argv[1],encoding='utf-8'))
print('run',d['run_id'],'chain',d['chain_id'],'term',d['termination_reason'],'n',d['completed_inference_count'],'load_s',round(d['load_window_s'],3),'pilot_pct',d['pilot_battery_pct'],'bad_lines',d['bad_jsonl_lines'])
for s in d['segments']:
    st=s['start_thermal'] or {}; soc=(s['start_soc'] or {}).get('battery_level')
    print(f\"  seg {s['index']} {s['label']} {s['accelerator']} d{s['duty']} len={s['length_s']:.3f} n={s['n']} median={s['median_all_ms']:.4f} first10={s['first10s_median_ms']:.4f} after10={s['after10s_median_ms']:.4f} first20={s['first20s_median_ms']:.4f} term={s['termination_reason']} start SKIN/AP/BAT={st.get('SKIN')}/{st.get('AP')}/{st.get('BAT')} status={st.get('thermal_status')} SOC={soc}\")
    bins=s['bins10']
    if len(bins)<=8: print('     bins10',[(b['t0'],round(b['median_ms'],4)) for b in bins])
    else: print('     bins10 first4',[(b['t0'],round(b['median_ms'],4)) for b in bins[:4]],'last4',[(b['t0'],round(b['median_ms'],4)) for b in bins[-4:]])
for t in d['transitions']:
    print(f\"  transition -> seg {t['to_segment']} {t['from_accelerator']}->{t['to_accelerator']} switch={t['backend_switch']} dur={t['duration_ns']/1e6:.1f} ms model_init={t['model_init_ns']/1e6:.1f} ms\")
" "$OUT/${TAG}_segments.json"
if [ "$ENG" = "engine" ]; then
  echo "### engine comparison (segment 0)"
  py -X utf8 "$JUDGE" engine "$RUN" --segment 0 --out "$OUT/${TAG}_engine.json" | py -X utf8 -c "
import json,sys;d=json.load(sys.stdin);print('values',d['values'],'checks',d['checks'],'verdict',d['verdict'],'ref30',d['ref30_ms'],'p0',d['power_first30_W'],'p540',d['power_540_600_W'],'edge',d['edge_candidate_s'])"
fi
echo "### evidence lines (runner PID, replacements/failures only)"
py -X utf8 results/S26_night_1002_host/extract_runner_lines.py "$RUN" --max 400 | grep -E "Replacing|falling|Failed|failed|Gracefully|not supported|runner_pids" | head -12
