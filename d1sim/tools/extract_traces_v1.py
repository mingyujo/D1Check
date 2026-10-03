"""extract_traces_v1.py — 1 s / 10 s load-relative traces for the v1 throttle model. READ-ONLY on results/.

Usage (D1Check_v4 root):
  py d1sim/tools/extract_traces_v1.py            # write d1sim/data/trace_v1_<tag>.csv, trace_v1_10s_<tag>.csv, trace_v1_manifest.json
  py d1sim/tools/extract_traces_v1.py --verify   # compare 10 s bins / temps with sim/out_1002 + sim/out_0928 outputs (no write)
  py d1sim/tools/extract_traces_v1.py --only c1a m3   # subset of tags

Definitions (v0_홀드아웃_사전등록_1003.md §1 — same as v0 tools/extract_traces.py, one data source):
  latency : runs/<id>/gpu/*.jsonl  event=inference, latency_ns (NPU = write+run+read), binned by start_mono_ns
            1 s bin [k, k+1) relative to the SEGMENT start (single run: load_start); 10 s bin = all-inference median, complete bins only
  power   : merged/events.jsonl source=d1check event=sample, -current_raw(uA)*voltage_mV/1e9, current_valid only, 1 s mean
  sensors : merged/events.jsonl source=thermalservice event=sample (HAL block: SKIN AP PA BAT thermal_status), parse_status ok
            1 s row = sample inside [k, k+1) (else the last one before); 10 s row = sample nearest to the bin start (judge convention)
  chained : segments from segment_start/segment_end detail (start_ns..end_ns); transition windows are flagged, never inside a segment
  ref     : row t_s = -1 per segment = first-30 s all-inference median + mean power (v0 convention)
The v0 tool (tools/extract_traces.py) is untouched.
"""
from __future__ import annotations

import argparse
import csv
import glob
import hashlib
import json
import os
import re
import statistics as st
import sys

import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
DATA = os.path.join(ROOT, 'd1sim', 'data')
SIM = r'C:\Users\rhoyo\OneDrive\문서\Mine\26-2\산공학회\D1_ondevice\sim'
WATCH = os.path.join(ROOT, 'results', 'S26_night_1002_host', 'skin_watch_1002.csv')   # optional host SOC watch

# tag: (result dir, run_id or None (= the single run), resource label, duty, role)
RUNS = {
    'c1p_r1': ('results/S26_C1probe_gpu600_0927', '1f953a1e-d0e7-46a5-beae-a13fb4c33d1a', 'GPU', 100, 'GPU Interpreter fit (v0 r1)'),
    'c1p_r2': ('results/S26_C1probe_gpu600_0927', '7f394fda-9e80-4dce-92fd-1d8c9c98d2c0', 'GPU', 100, 'GPU Interpreter half-holdout'),
    'c1a': ('results/S26_C1a_gpu1300_0928', None, 'GPU', 100, 'GPU Interpreter 1300 s — v0 true holdout (T1)'),
    'm3': ('results/S26_M3_gpud50_0928', None, 'GPU', 50, 'GPU d50 Interpreter — v0 true holdout (T2)'),
    'c600_r1': ('results/S26_C600_cpu4_0928', None, 'CPU4', 100, 'CPU4 Interpreter fit'),
    'c600_r2': ('results/S26_C600_cpu4_0928_r2', None, 'CPU4', 100, 'CPU4 Interpreter half-holdout'),
    'n165': ('results/S26_N165_npu_0928', None, 'NPU', 100, 'NPU old install — reference only'),
    'n1300': ('results/S26_N1300_npu_1002', None, 'NPU', 100, 'NPU CompiledModel 1300 s — NPU fit'),
    'm1': ('results/S26_M1_gpu_1002', None, 'GPU', None, 'chain GPU d10 60 / d100 1200 / d10 300 — recovery'),
    'm2_C1': ('results/S26_M2_npu_C1_1002', None, 'GPU>NPU', None, 'chain GPU 30 -> NPU 60 (control)'),
    'm2_H1': ('results/S26_M2_npu_H1_1002', None, 'GPU>NPU', None, 'chain GPU 600 -> NPU 60 (heated)'),
    'm2_H2': ('results/S26_M2_npu_H2_1002', None, 'GPU>NPU', None, 'chain GPU 600 -> NPU 60 (heated)'),
    'm2_C2': ('results/S26_M2_npu_C2_1002', None, 'GPU>NPU', None, 'chain GPU 30 -> NPU 60 (control)'),
    'm2r_C1': ('results/S26_M2r_gpu_C1_1002', None, 'NPU>GPU', None, 'chain NPU 30 -> GPU 60 (control)'),
    'm2r_H1': ('results/S26_M2r_gpu_H1_1002', None, 'NPU>GPU', None, 'chain NPU 600 -> GPU 60 (heated)'),
    'm2r_H2': ('results/S26_M2r_gpu_H2_1002', None, 'NPU>GPU', None, 'chain NPU 600 -> GPU 60 (heated)'),
    'm2r_C2': ('results/S26_M2r_gpu_C2_1002', None, 'NPU>GPU', None, 'chain NPU 30 -> GPU 60 (control)'),
}

INF_RE = re.compile(r'"start_mono_ns":(\d+),"mono_ns":(\d+),"latency_ns":(\d+)')
KEEP_1S = ['tag', 'seg', 'seg_label', 'accelerator', 'duty', 't_s', 't_load_s', 'n_inf', 'lat_med_ms', 'power_w',
           'SKIN', 'AP', 'PA', 'BAT', 'status', 'active', 'in_transition']
KEEP_10S = ['tag', 'seg', 'seg_label', 'accelerator', 'duty', 't_s', 'n_inf', 'lat_med_ms', 'power_w',
            'SKIN', 'AP', 'PA', 'BAT', 'status', 'SOC']


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 24), b''):
            h.update(chunk)
    return h.hexdigest()


def detail(e):
    d = e.get('detail')
    if isinstance(d, dict):
        return d
    try:
        return json.loads(d) if isinstance(d, str) else {}
    except ValueError:
        return {}


def read_runner(path):
    """Returns dict(meta, load_start, load_end, segments[], transitions[], inf_start(np), inf_end(np), inf_lat_ms(np))."""
    meta = None
    ls = le = None
    seg_s, seg_e, tr_s, tr_e = [], [], [], []
    starts, ends, lats = [], [], []
    with open(path, encoding='utf-8') as fh:
        for line in fh:
            if '"event":"inference"' in line:
                m = INF_RE.search(line)
                if m is None:
                    e = json.loads(line)
                    starts.append(int(e['start_mono_ns'])); ends.append(int(e['mono_ns'])); lats.append(float(e['latency_ns']) / 1e6)
                else:
                    starts.append(int(m.group(1))); ends.append(int(m.group(2))); lats.append(int(m.group(3)) / 1e6)
                continue
            if not line.strip():
                continue
            try:
                e = json.loads(line)
            except ValueError:
                continue
            ev = e.get('event')
            if ev == 'run_metadata':
                meta = e
            elif ev == 'load_start':
                ls = int(e['mono_ns'])
            elif ev == 'load_end':
                le = int(e['mono_ns'])
            elif ev == 'segment_start':
                seg_s.append(detail(e))
            elif ev == 'segment_end':
                seg_e.append(detail(e))
            elif ev == 'chain_transition_start':
                tr_s.append(detail(e))
            elif ev == 'chain_transition_end':
                tr_e.append(detail(e))
    if meta is None or ls is None or le is None:
        raise RuntimeError(f'run_metadata/load_start/load_end missing in {path}')
    o = np.argsort(np.array(starts, dtype=np.int64), kind='stable')
    R = dict(meta=meta, load_start=ls, load_end=le,
             inf_start=np.array(starts, dtype=np.int64)[o], inf_end=np.array(ends, dtype=np.int64)[o],
             inf_lat_ms=np.array(lats, dtype=float)[o])
    if meta.get('chain_mode') is True:
        if len(seg_s) != len(seg_e) or not seg_s:
            raise RuntimeError(f'segment_start {len(seg_s)} != segment_end {len(seg_e)}')
        segs = []
        for s, e in zip(seg_s, seg_e):
            segs.append(dict(index=int(s['index']), label=s.get('label'), accelerator=s.get('accelerator'),
                             duty=s.get('duty'), duration_s=s.get('duration_s'), start_ns=int(s['start_ns']), end_ns=int(e['end_ns']),
                             inference_count=e.get('inference_count'), termination=e.get('termination_reason')))
        trans = [dict(to_segment=d.get('to_segment'), start_ns=int(d['start_ns']), end_ns=int(d['end_ns']),
                      duration_s=(int(d['end_ns']) - int(d['start_ns'])) / 1e9, model_init_ns=d.get('model_init_ns'),
                      backend_switch=d.get('backend_switch')) for d in tr_e]
    else:
        segs = [dict(index=0, label='load', accelerator=meta.get('resource'), duty=meta.get('requested_duty_cycle_percent'),
                     duration_s=meta.get('requested_duration_s'), start_ns=ls, end_ns=le, inference_count=None,
                     termination=meta.get('termination_reason'))]
        trans = []
    R['segments'] = segs
    R['transitions'] = trans
    return R


def read_merged(path):
    """d1check samples (power etc.) and thermalservice samples from merged/events.jsonl."""
    d1, th = [], []
    with open(path, encoding='utf-8') as fh:
        for line in fh:
            if '"event":"sample"' not in line:
                continue
            if '"source":"thermalservice"' in line:
                s = json.loads(line)
                if s.get('parse_status') not in (None, 'ok'):
                    continue
                th.append((int(s['mono_ns']), {k: _f(s.get(k)) for k in ('SKIN', 'AP', 'PA', 'BAT')},
                           int(s['thermal_status']) if s.get('thermal_status') not in (None, '') else None))
            elif '"source":"d1check"' in line:
                s = json.loads(line)
                ok = s.get('current_valid') is not False and s.get('current_raw') is not None and s.get('voltage_mV')
                d1.append((int(s['mono_ns']), (-float(s['current_raw']) * float(s['voltage_mV']) / 1e9) if ok else None,
                           s.get('plugged'), s.get('thermal_status'), s.get('wall_ms')))
    th.sort(key=lambda x: x[0]); d1.sort(key=lambda x: x[0])
    return d1, th


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def load_watch(path):
    rows = []
    if not os.path.exists(path):
        return rows
    import datetime
    with open(path, encoding='utf-8') as fh:
        for r in csv.DictReader(fh):
            try:
                t = datetime.datetime.fromisoformat(r['local_time']).timestamp() * 1000.0
                lvl = int(r['battery_level'])
            except (ValueError, KeyError, TypeError):
                continue
            rows.append((t, lvl))
    rows.sort()
    return rows


def extract(tag, res, rid, resource, duty, watch):
    d = os.path.join(ROOT, res)
    if rid is None:
        runs = [x for x in sorted(glob.glob(os.path.join(d, 'runs', '*'))) if os.path.isdir(x)]
        if len(runs) != 1:
            raise RuntimeError(f'{tag}: {len(runs)} runs in {d}')
        rid = os.path.basename(runs[0])
    rd = os.path.join(d, 'runs', rid)
    jf = glob.glob(os.path.join(rd, 'gpu', '*.jsonl'))
    if len(jf) != 1:
        raise RuntimeError(f'{tag}: runner jsonl {len(jf)}')
    mf = os.path.join(rd, 'merged', 'events.jsonl')
    R = read_runner(jf[0])
    d1, th = read_merged(mf)
    th_t = np.array([x[0] for x in th], dtype=np.int64)
    d1_t = np.array([x[0] for x in d1], dtype=np.int64)
    d1_p = np.array([x[1] if x[1] is not None else np.nan for x in d1], dtype=float)
    # wall clock offset for SOC (first d1check sample with wall_ms)
    wall_off = None
    for mono, _, _, _, wall in d1:
        if wall is not None:
            wall_off = wall - mono / 1e6
            break
    rows1, rows10 = [], []
    tr_windows = [(t['start_ns'], t['end_ns']) for t in R['transitions']]
    for seg in R['segments']:
        a, b = seg['start_ns'], seg['end_ns']
        m = (R['inf_start'] >= a) & (R['inf_end'] <= b)
        if seg['inference_count'] is not None and int(m.sum()) != int(seg['inference_count']):
            raise RuntimeError(f"{tag} seg {seg['index']}: inferences in window {int(m.sum())} != segment_end {seg['inference_count']}")
        rel = (R['inf_start'][m] - a) / 1e9
        lat = R['inf_lat_ms'][m]
        L = (b - a) / 1e9
        n1 = int(np.ceil(L - 1e-9))
        edges1 = np.searchsorted(rel, np.arange(n1 + 1) * 1.0, side='left')
        n10 = int(np.floor(L / 10 + 1e-9))
        edges10 = np.searchsorted(rel, np.arange(n10 + 1) * 10.0, side='left')
        # first-30 s reference
        m30 = rel < 30.0
        ref_lat = float(np.median(lat[m30])) if m30.any() else None
        mp30 = (d1_t >= a) & (d1_t < a + 30_000_000_000)
        ref_pw = float(np.nanmean(d1_p[mp30])) if mp30.any() and not np.all(np.isnan(d1_p[mp30])) else None
        rows10.append(dict(tag=tag, seg=seg['index'], seg_label=seg['label'], accelerator=seg['accelerator'], duty=seg['duty'],
                           t_s=-1, n_inf=int(m30.sum()), lat_med_ms=_r(ref_lat, 6), power_w=_r(ref_pw, 4),
                           SKIN='', AP='', PA='', BAT='', status='', SOC=''))
        last_th = None
        for k in range(n1):
            v = lat[edges1[k]:edges1[k + 1]]
            t0, t1 = a + k * 1_000_000_000, a + (k + 1) * 1_000_000_000
            mp = (d1_t >= t0) & (d1_t < t1)
            pw = float(np.nanmean(d1_p[mp])) if mp.any() and not np.all(np.isnan(d1_p[mp])) else None
            i0, i1 = np.searchsorted(th_t, t0, side='left'), np.searchsorted(th_t, t1, side='left')
            if i1 > i0:
                last_th = th[i1 - 1]
            elif last_th is None and i0 > 0:
                last_th = th[i0 - 1]
            s = last_th
            in_tr = int(any(ts <= t0 < te or ts < t1 <= te for ts, te in tr_windows))
            rows1.append(dict(tag=tag, seg=seg['index'], seg_label=seg['label'], accelerator=seg['accelerator'], duty=seg['duty'],
                              t_s=k, t_load_s=_r((t0 - R['load_start']) / 1e9, 3), n_inf=int(len(v)),
                              lat_med_ms=_r(float(np.median(v)), 6) if len(v) else '', power_w=_r(pw, 4),
                              SKIN=_s(s, 'SKIN'), AP=_s(s, 'AP'), PA=_s(s, 'PA'), BAT=_s(s, 'BAT'),
                              status=(s[2] if s and s[2] is not None else ''), active=int(len(v) > 0), in_transition=in_tr))
        for k in range(n10):
            v = lat[edges10[k]:edges10[k + 1]]
            t0, t1 = a + k * 10_000_000_000, a + (k + 1) * 10_000_000_000
            mp = (d1_t >= t0) & (d1_t < t1)
            pw = float(np.nanmean(d1_p[mp])) if mp.any() and not np.all(np.isnan(d1_p[mp])) else None
            s = th[int(np.argmin(np.abs(th_t - t0)))] if len(th_t) else None
            soc = ''
            if watch and wall_off is not None:
                w = wall_off + t0 / 1e6
                before = [lvl for t, lvl in watch if t <= w]
                soc = before[-1] if before else ''
            rows10.append(dict(tag=tag, seg=seg['index'], seg_label=seg['label'], accelerator=seg['accelerator'], duty=seg['duty'],
                               t_s=k * 10, n_inf=int(len(v)), lat_med_ms=_r(float(np.median(v)), 6) if len(v) else '',
                               power_w=_r(pw, 4), SKIN=_s(s, 'SKIN'), AP=_s(s, 'AP'), PA=_s(s, 'PA'), BAT=_s(s, 'BAT'),
                               status=(s[2] if s and s[2] is not None else ''), SOC=soc))
    man = dict(tag=tag, result_dir=res, run_id=rid, resource=resource, duty=duty, chain_mode=R['meta'].get('chain_mode') is True,
               engine=R['meta'].get('engine'), litert_version=R['meta'].get('litert_version'),
               termination_reason=R['meta'].get('termination_reason'), n_inference=int(len(R['inf_start'])),
               load_window_s=(R['load_end'] - R['load_start']) / 1e9,
               segments=[{k: v for k, v in s.items()} for s in R['segments']],
               transitions=R['transitions'],
               files={'runner_jsonl': dict(path=os.path.relpath(jf[0], ROOT), bytes=os.path.getsize(jf[0]), sha256=sha256(jf[0])),
                      'merged_events': dict(path=os.path.relpath(mf, ROOT), bytes=os.path.getsize(mf), sha256=sha256(mf))},
               rows_1s=len(rows1), rows_10s=len(rows10), thermal_samples=len(th), d1check_samples=len(d1),
               plugged_nonzero=sum(1 for x in d1 if x[2] not in (0, '0', None)))
    return rows1, rows10, man


def _r(x, n):
    return '' if x is None or (isinstance(x, float) and np.isnan(x)) else round(float(x), n)


def _s(s, key):
    if s is None or s[1].get(key) is None:
        return ''
    return s[1][key]


def write_csv(path, rows, fields):
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, '') for k in fields})


# ------------------------------------------------------------------ verify against existing judged outputs
def verify(tags):
    """10 s medians within 0.1 %, temps within 0.05 C against sim/out_0928 + sim/out_1002 (independent scripts)."""
    out = []

    def rows10(tag):
        return list(csv.DictReader(open(os.path.join(DATA, f'trace_v1_10s_{tag}.csv'), encoding='utf-8')))

    def rows1(tag):
        return list(csv.DictReader(open(os.path.join(DATA, f'trace_v1_{tag}.csv'), encoding='utf-8')))

    def cmp(name, pairs_lat, pairs_temp, n_pairs=()):
        dl = [abs(a / b - 1) for a, b in pairs_lat if a is not None and b]
        dt = [abs(a - b) for a, b in pairs_temp if a is not None and b is not None]
        dn = [abs(a - b) for a, b in n_pairs]
        ok = (not dl or max(dl) <= 0.001) and (not dt or max(dt) <= 0.05 + 1e-9) and (not dn or max(dn) == 0)
        out.append(dict(check=name, n_lat=len(dl), max_lat_rel=max(dl) if dl else None, n_temp=len(dt),
                        max_temp_abs=max(dt) if dt else None, n_count=len(dn), max_count_diff=max(dn) if dn else None, ok=ok))

    for tag, name in (('c1a', 'C1a'), ('m3', 'M3'), ('c600_r1', 'C600'), ('c600_r2', 'C600r2'), ('n165', 'N165'),
                      ('c1p_r1', 'ref_C1probe'), ('c1p_r2', 'ref_C1probe')):
        if tag not in tags:
            continue
        ref = json.load(open(os.path.join(SIM, 'out_0928', f'{name}.json'), encoding='utf-8'))
        r10 = {int(float(r['t_s'])): r for r in rows10(tag) if r['seg'] == '0'}
        r1 = {int(float(r['t_s'])): r for r in rows1(tag) if r['seg'] == '0'}
        rec = ref[0] if name != 'ref_C1probe' else next(x for x in ref if x['run_id'] == RUNS[tag][1])
        pl = [(float(r10[t]['lat_med_ms']), m) for t, m, n in rec['lat10'] if t in r10 and r10[t]['lat_med_ms'] != '']
        pn = [(int(r10[t]['n_inf']), n) for t, m, n in rec['lat10'] if t in r10]
        pt = []
        for row in rec['table60']:
            t = row['t'] + 60
            if t - 1 in r1 and r1[t - 1]['SKIN'] != '' and row['SKIN'] is not None:
                # table60 temp = sample nearest to t; our 1 s row t-1 holds the sample inside [t-1, t) -> may differ by one sample
                cand = [float(r1[x]['SKIN']) for x in (t - 1, t) if x in r1 and r1[x]['SKIN'] != '']
                pt.append((min(cand, key=lambda v: abs(v - row['SKIN'])), row['SKIN']))
        pl.append((float(next(r for r in rows10(tag) if r['seg'] == '0' and r['t_s'] == '-1')['lat_med_ms']), rec['ref_ms']))
        cmp(f'{tag} vs out_0928/{name}.json (lat10, table60 SKIN, ref)', pl, pt, pn)

    if 'n1300' in tags:
        ref = json.load(open(os.path.join(SIM, 'out_1002', 'N1300_table.json'), encoding='utf-8'))
        r10 = {int(float(r['t_s'])): r for r in rows10('n1300') if r['seg'] == '0'}
        pl = [(float(r10[b['t0']]['lat_med_ms']), b['median_ms']) for b in ref['bins10'] if b['t0'] in r10]
        # long_run_table.py bins10 temps = HAL sample nearest to the bin END (t0+10) -> compare with our 1 s row t0+9 / t0+10
        r1 = {int(float(r['t_s'])): r for r in rows1('n1300') if r['seg'] == '0'}
        pt = []
        for key in ('SKIN', 'AP'):
            for b in ref['bins10']:
                cand = [float(r1[x][key]) for x in (b['t0'] + 9, b['t0'] + 10) if x in r1 and r1[x][key] != '']
                if cand and b.get(key) is not None:
                    pt.append((min(cand, key=lambda v: abs(v - b[key])), b[key]))
        pn = [(int(r10[b['t0']]['n_inf']), b['n']) for b in ref['bins10'] if b['t0'] in r10]
        pl.append((float(r10[-1]['lat_med_ms']), ref['ref30_ms']))
        cmp("n1300 vs out_1002/N1300_table.json (bins10 median, n, ref30; SKIN/AP at bin END = that table's definition)", pl, pt, pn)

    if 'm1' in tags:
        ref = json.load(open(os.path.join(SIM, 'out_1002', 'M1_judge.json'), encoding='utf-8'))
        r = rows10('m1')
        seg2 = {int(float(x['t_s'])): x for x in r if x['seg'] == '2'}
        seg0 = {int(float(x['t_s'])): x for x in r if x['seg'] == '0'}
        pl = [(float(seg2[b['t0']]['lat_med_ms']), b['median_ms']) for b in ref['probe']['bins'] if b['t0'] in seg2]
        pt = [(float(seg2[b['t0']]['SKIN']), b['SKIN']) for b in ref['probe']['bins'] if b['t0'] in seg2 and seg2[b['t0']]['SKIN'] != '']
        pn = [(int(seg2[b['t0']]['n_inf']), b['n']) for b in ref['probe']['bins'] if b['t0'] in seg2]
        # ref_d10 = all-median of seg 0 -> recompute from 1 s? not available; compare first-30 ref of seg1 with heat ref30
        seg1 = {int(float(x['t_s'])): x for x in r if x['seg'] == '1'}
        pl.append((float(seg1[-1]['lat_med_ms']), ref['heat_segment']['ref30_ms']))
        cmp('m1 vs out_1002/M1_judge.json (probe bins median, SKIN, n; heat ref30)', pl, pt, pn)

    for grp, jf in (('m2', 'M2_npu_judge.json'), ('m2r', 'M2r_gpu_judge.json')):
        arms = [f'{grp}_{a}' for a in ('C1', 'H1', 'H2', 'C2')]
        if not all(a in tags for a in arms):
            continue
        ref = json.load(open(os.path.join(SIM, 'out_1002', jf), encoding='utf-8'))
        pl, pt, pn = [], [], []
        for a in ('C1', 'H1', 'H2', 'C2'):
            r = rows10(f'{grp}_{a}')
            seg1 = {int(float(x['t_s'])): x for x in r if x['seg'] == '1'}
            for b in ref['arms'][a]['bins10']:
                if b['t0'] in seg1:
                    pl.append((float(seg1[b['t0']]['lat_med_ms']), b['median_ms'])); pn.append((int(seg1[b['t0']]['n_inf']), b['n']))
            vst = ref['arms'][a]['victim_start_thermal']
            if seg1.get(0) and seg1[0]['SKIN'] != '':
                pt.append((float(seg1[0]['SKIN']), vst['SKIN'])); pt.append((float(seg1[0]['AP']), vst['AP']))
        cmp(f'{grp} 4 arms vs out_1002/{jf} (victim bins10 median, n, start SKIN/AP)', pl, pt, pn)

    for a in ('H1', 'H2'):
        tag = f'm2r_{a}'
        if tag not in tags:
            continue
        ref = json.load(open(os.path.join(SIM, 'out_1002', f'M2r_{a}_seg0_throttle.json'), encoding='utf-8'))[0]
        seg0 = {int(float(x['t_s'])): x for x in rows10(tag) if x['seg'] == '0'}
        pl = [(float(seg0[t]['lat_med_ms']), m) for t, m, n in ref['lat10'] if t in seg0]
        pn = [(int(seg0[t]['n_inf']), n) for t, m, n in ref['lat10'] if t in seg0]
        pl.append((float(seg0[-1]['lat_med_ms']), ref['ref_ms']))
        cmp(f'{tag} seg0 vs out_1002/M2r_{a}_seg0_throttle.json (lat10, ref)', pl, [], pn)

    print('| check | n_lat | max |Δlat| rel | n_temp | max |Δtemp| ℃ | n_count | max Δn | ok |\n|---|---:|---:|---:|---:|---:|---:|---|')
    for o in out:
        print(f"| {o['check']} | {o['n_lat']} | {o['max_lat_rel'] if o['max_lat_rel'] is None else f'{o['max_lat_rel']:.2e}'} | {o['n_temp']} | "
              f"{o['max_temp_abs'] if o['max_temp_abs'] is None else f'{o['max_temp_abs']:.3f}'} | {o['n_count']} | {o['max_count_diff']} | {'PASS' if o['ok'] else 'FAIL'} |")
    allok = all(o['ok'] for o in out)
    print(f"\nverify: {'PASS' if allok else 'FAIL'} ({sum(o['ok'] for o in out)}/{len(out)})")
    json.dump(out, open(os.path.join(ROOT, 'd1sim', 'out', 'trace_v1_verify.json'), 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
    return allok


def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument('--verify', action='store_true')
    ap.add_argument('--only', nargs='*')
    a = ap.parse_args()
    tags = a.only or list(RUNS)
    if a.verify:
        return 0 if verify(tags) else 1
    os.makedirs(DATA, exist_ok=True)
    os.makedirs(os.path.join(ROOT, 'd1sim', 'out'), exist_ok=True)
    watch = load_watch(WATCH)
    mp = os.path.join(DATA, 'trace_v1_manifest.json')
    manifest = json.load(open(mp, encoding='utf-8')) if os.path.exists(mp) else {}
    for tag in tags:
        res, rid, resource, duty, role = RUNS[tag]
        rows1, rows10, man = extract(tag, res, rid, resource, duty, watch)
        man['role'] = role
        write_csv(os.path.join(DATA, f'trace_v1_{tag}.csv'), rows1, KEEP_1S)
        write_csv(os.path.join(DATA, f'trace_v1_10s_{tag}.csv'), rows10, KEEP_10S)
        manifest[tag] = man
        print(tag, man['run_id'], 'segments', len(man['segments']), 'inf', man['n_inference'], 'rows1', man['rows_1s'], 'rows10', man['rows_10s'],
              'plugged!=0', man['plugged_nonzero'], flush=True)
    manifest['_definition'] = __doc__.split('Definitions')[1].strip() if 'Definitions' in __doc__ else ''
    manifest['_watch_csv'] = dict(path=os.path.relpath(WATCH, ROOT), present=bool(watch))
    json.dump(manifest, open(mp, 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
    print('wrote', mp)
    return 0


if __name__ == '__main__':
    sys.exit(main())
