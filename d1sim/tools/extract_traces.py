"""Extract 1 s load-relative traces from raw run folders. READ-ONLY on results/.

Usage (D1Check_v4 root): py d1sim/tools/extract_traces.py
Writes d1sim/data/trace_<tag>.csv (1 s) and trace10_<tag>.csv (10 s: exact median over inferences;
  row t_s=-1 = exact first-30 s reference: all-inference median and mean power) with columns:
  t_s (bin start, load-relative), n_inf, lat_med_ms, power_w, SKIN, AP, BAT, PA, status, headroom_now, headroom_60s
Sources per run:
  latency  : runs/<id>/gpu/*.jsonl  event=inference, start_mono_ns - load_start.mono_ns
  power    : runs/<id>/raw/logcat.jsonl  d1check event=sample, -current_raw(uA)*voltage_mV, current_valid only
  sensors  : exports-v2/thermal_timeseries.csv  load_relative_s, parse_status ok
"""
import csv, glob, json, os, statistics as st

ROOT = os.path.join(os.path.dirname(__file__), '..', '..')
RUNS = {  # tag: (result dir, run_id, role)
    'c1p_r1': ('results/S26_C1probe_gpu600_0927', '1f953a1e-d0e7-46a5-beae-a13fb4c33d1a'),
    'c1p_r2': ('results/S26_C1probe_gpu600_0927', '7f394fda-9e80-4dce-92fd-1d8c9c98d2c0'),
    'f914_gpu_d100_r001': ('results/S26_formal_strict', '1691c91b-2feb-4d58-b7f2-19ee1a5f7c55'),
    'f914_gpu_d100_r002': ('results/S26_formal_strict', '2dd29027-8c9d-4c73-9a24-3248b78bb2f5'),
    'f914_gpu_d100_r003': ('results/S26_formal_strict', '3ef3ac25-cda3-4464-8535-999f9f505dc3'),
    'f914_gpu_d100_r004': ('results/S26_formal_strict', '1d2eb428-1c5f-45ea-8e95-ae102f9a03b4'),
    'f914_gpu_d100_r005': ('results/S26_formal_strict', 'b4f0b080-a363-42b8-9881-ec718eb22318'),
}


def extract(res, rid):
    d = os.path.join(ROOT, res)
    ev = glob.glob(os.path.join(d, 'runs', rid, 'gpu', '*.jsonl'))[0]
    t0, lat, lat10 = None, {}, {}
    for line in open(ev, encoding='utf-8'):
        if '"event":"load_start"' in line:
            t0 = json.loads(line)['mono_ns']
        elif '"event":"inference"' in line and t0 is not None:
            e = json.loads(line)
            lat.setdefault(int((e['start_mono_ns'] - t0) // 1_000_000_000), []).append(e['latency_ms'])
            lat10.setdefault(int((e['start_mono_ns'] - t0) // 10_000_000_000), []).append(e['latency_ms'])
    pw, hn, h60 = {}, {}, {}
    for line in open(os.path.join(d, 'runs', rid, 'raw', 'logcat.jsonl'), encoding='utf-8'):
        if '"event":"sample"' not in line:
            continue
        e = json.loads(line)
        k = (e['mono_ns'] - t0) // 1_000_000_000
        if e.get('current_valid') and e.get('voltage_mV'):
            pw.setdefault(k, []).append(-e['current_raw'] * e['voltage_mV'] / 1e9)
        if e.get('headroom_now') is not None:
            hn[k] = e['headroom_now']
        if e.get('headroom_60s') is not None:
            h60[k] = e['headroom_60s']
    sens = {}
    for r in csv.DictReader(open(os.path.join(d, 'exports-v2', 'thermal_timeseries.csv'), encoding='utf-8')):
        if r['run_id'] == rid and r['parse_status'] == 'ok' and r['phase'] == 'load':
            sens[int(float(r['load_relative_s']) // 1)] = r
    rows = []
    for k in sorted(lat):
        s = sens.get(k) or sens.get(k - 1) or {}
        rows.append(dict(t_s=k, n_inf=len(lat[k]), lat_med_ms=round(st.median(lat[k]), 5),
                         power_w=round(st.mean(pw[k]), 4) if k in pw else '',
                         SKIN=s.get('SKIN', ''), AP=s.get('AP', ''), BAT=s.get('BAT', ''), PA=s.get('PA', ''),
                         status=s.get('thermal_status', ''), headroom_now=hn.get(k, ''), headroom_60s=h60.get(k, '')))
    rows10 = [dict(t_s=k * 10, n_inf=len(v), lat_med_ms=round(st.median(v), 5),
                   power_w=round(st.mean([x for j in range(k * 10, k * 10 + 10) for x in pw.get(j, [])]), 4))
              for k, v in sorted(lat10.items()) if len(v) > 0]
    first30 = sorted(x for k, v in lat.items() if k < 30 for x in v)
    rows10.insert(0, dict(t_s=-1, n_inf=len(first30), lat_med_ms=round(st.median(first30), 5),
                          power_w=round(st.mean([x for j in range(30) for x in pw.get(j, [])]), 4)))
    return rows, rows10


if __name__ == '__main__':
    out = os.path.join(ROOT, 'd1sim', 'data')
    for tag, (res, rid) in RUNS.items():
        rows, rows10 = extract(res, rid)
        for name, rr in ((f'trace_{tag}.csv', rows), (f'trace10_{tag}.csv', rows10)):
            with open(os.path.join(out, name), 'w', newline='', encoding='utf-8') as f:
                w = csv.DictWriter(f, fieldnames=list(rr[0]))
                w.writeheader(); w.writerows(rr)
        print(tag, rid, 'bins', len(rows), 'inf', sum(r['n_inf'] for r in rows))
