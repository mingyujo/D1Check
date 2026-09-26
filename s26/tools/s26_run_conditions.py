"""Per-run plugged / SOC / load-start temps for a formal result dir. Read-only.
Usage: py s26/tools/s26_run_conditions.py results/S26_formal_strict out.json
"""
import csv, json, os, sys, statistics as st
root = sys.argv[1]
rows = list(csv.DictReader(open(os.path.join(root, 'exports-v2', 'run_summary.csv'), encoding='utf-8')))
out = []
for r in rows:
    rid = r['run_id']
    ev = os.path.join(root, 'runs', rid, 'merged', 'events.jsonl')
    meta = None; plug_vals = {}; n = 0; load_start = None; first_load_sample = None; samples = []
    with open(ev, encoding='utf-8') as f:
        for line in f:
            try: e = json.loads(line)
            except Exception: continue
            if e.get('event') == 'run_metadata' and meta is None: meta = e
            if e.get('source') == 'gpu' and e.get('event') == 'load_start': load_start = e['mono_ns']
            if e.get('source') == 'd1check' and e.get('event') == 'sample':
                n += 1; p = e.get('plugged'); plug_vals[p] = plug_vals.get(p, 0) + 1
                samples.append(e)
    if meta is None:
        # run_metadata may be nested under config
        pass
    def mget(k):
        if meta is None: return None
        if k in meta: return meta[k]
        c = meta.get('config') or {}
        return c.get(k)
    ls_sample = None
    if load_start is not None:
        after = [s for s in samples if s['mono_ns'] >= load_start]
        ls_sample = after[0] if after else None
    out.append(dict(run_id=rid, slot=r['slot_id'], res=r['resource'], thr=r['cpu_threads'], duty=r['requested_duty_cycle_percent'],
        start_plugged=mget('pilot_plugged'), start_status=mget('pilot_battery_status'), start_pct=mget('pilot_battery_pct'),
        samples=n, plugged_counts=plug_vals,
        ls_batt_temp=ls_sample and ls_sample.get('battery_temp_C'), ls_thermal_status=ls_sample and ls_sample.get('thermal_status'),
        ap_ls=r['ap_load_start_temperature_c'], skin_ls=r['skin_load_start_temperature_c'], bat_ls=r['bat_load_start_temperature_c'],
        wall_ms=samples[0]['wall_ms'] if samples else None,
        max_thermal_status=max((s.get('thermal_status') or 0) for s in samples) if samples else None))
bad = [o for o in out if o['start_plugged'] != 0 or any(k not in (0,) for k in o['plugged_counts'])]
print('runs', len(out), 'bad', len(bad))
for o in bad: print('BAD', o)
json.dump(out, open(sys.argv[2], 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
def rng(k, sel):
    v = [float(o[k]) for o in sel if o[k] not in (None, '')]
    return (min(v), st.median(v), max(v), len(v)) if v else None
for res in ('CPU', 'GPU'):
    sel = [o for o in out if o['res'] == res]
    print(res, len(sel), 'pct', rng('start_pct', sel), 'skin_ls', rng('skin_ls', sel), 'ap_ls', rng('ap_ls', sel), 'bat_ls', rng('bat_ls', sel),
          'status', sorted({o['start_status'] for o in sel}), 'maxTS', sorted({o['max_thermal_status'] for o in sel}), 'samples', rng('samples', sel))
import datetime
ws = sorted(out, key=lambda o: o['wall_ms'])
print('first', datetime.datetime.fromtimestamp(ws[0]['wall_ms']/1000), ws[0]['start_pct'], 'last', datetime.datetime.fromtimestamp(ws[-1]['wall_ms']/1000), ws[-1]['start_pct'])
print('pct sequence', [o['start_pct'] for o in ws])
