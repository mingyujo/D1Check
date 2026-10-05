"""extract_traces_v21.py — the 2026-10-04 night + 2026-10-05 morning chain runs as v1-format traces (v2.1 development data). READ-ONLY on results/.

Same pattern as extract_traces_v2.py: extract_traces_v1.py is NOT modified — this file imports its functions (extract, write_csv,
load_watch, KEEP_1S/KEEP_10S) unchanged and only supplies a new run table + output prefix `trace_v21_`. Definitions are therefore
identical to v1/v2 (1 s / 10 s bins, segment windows, HAL nearest sample, first-30 s ref row t_s = -1).

  py d1sim/tools/extract_traces_v21.py                 # write d1sim/data/trace_v21_<tag>.csv, trace_v21_10s_<tag>.csv, trace_v21_manifest.json
  py d1sim/tools/extract_traces_v21.py --check-v1 m1   # byte comparison through this module (import path unchanged)
  py d1sim/tools/extract_traces_v21.py --verify        # 10 s bins vs sim/out_1004 · out_1005 judge JSONs (ratio rel <= 0.1 %, temps <= 0.05 C)
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, ROOT)
from d1sim.tools import extract_traces_v1 as v1  # noqa: E402
from d1sim.tools import extract_traces_v2 as v2  # noqa: E402  (check_v1 helper pattern; never modified)

DATA = v1.DATA
WATCH = {'1004': os.path.join(ROOT, 'results', 'S26_night_1004_host', 'skin_watch_1004.csv'),
         '1005': os.path.join(ROOT, 'results', 'S26_am_1005_host', 'skin_watch_1005.csv')}

# tag: (result dir, run_id or None, resource label, duty, role, night) — v1.RUNS tuple shape + watch key
RUNS = {
    'n50p': ('results/S26_N50P_1004', None, 'NPU', None, 'chain NPU d50 60 / d100 420 / d50 480 — N50P (10/4), v2.1 dev', '1004'),
    'g50p': ('results/S26_G50P_1004', None, 'GPU', None, 'chain GPU d50 60 / d100 300 / d50 480 — G50P (10/4), v2.1 dev', '1004'),
    'gi300': ('results/S26_GI300_1004', None, 'GPU', None, 'chain GPU d10 60 / d100 600 / d1 300 / d100 300 — GI300 (10/4), v2.1 dev', '1004'),
    'ni300': ('results/S26_NI300_1004', None, 'NPU', None, 'chain NPU d10 60 / d100 300 / d1 300 / d100 180 — NI300 (10/4), v2.1 dev', '1004'),
    'n50p2': ('results/S26_N50P2_1005', None, 'NPU', None, 'chain NPU d50 60 / d100 420 / d50 480 — N50P2 (10/5), v2.1 dev', '1005'),
    'g50p2': ('results/S26_G50P2_1005', None, 'GPU', None, 'chain GPU d50 60 / d100 300 / d50 480 — G50P2 (10/5), v2.1 dev', '1005'),
    'ni300r2': ('results/S26_NI300r2_1005', None, 'NPU', None, 'chain NPU d10 60 / d100 300 / d1 300 / d100 180 — NI300r2 (10/5), v2.1 dev', '1005'),
}
JUDGE = {'n50p': ('out_1004', 'N50P'), 'g50p': ('out_1004', 'G50P'), 'gi300': ('out_1004', 'GI300'), 'ni300': ('out_1004', 'NI300'),
         'n50p2': ('out_1005', 'N50P2'), 'g50p2': ('out_1005', 'G50P2'), 'ni300r2': ('out_1005', 'NI300r2')}


def write_all(tags, out_dir):
    mp = os.path.join(out_dir, 'trace_v21_manifest.json')
    manifest = json.load(open(mp, encoding='utf-8')) if os.path.exists(mp) else {}
    for tag in tags:
        res, rid, resource, duty, role, night = RUNS[tag]
        rows1, rows10, man = v1.extract(tag, res, rid, resource, duty, v1.load_watch(WATCH[night]))
        man['role'] = role
        v1.write_csv(os.path.join(out_dir, f'trace_v21_{tag}.csv'), rows1, v1.KEEP_1S)
        v1.write_csv(os.path.join(out_dir, f'trace_v21_10s_{tag}.csv'), rows10, v1.KEEP_10S)
        manifest[tag] = man
        print(tag, man['run_id'], 'segments', len(man['segments']), 'inf', man['n_inference'], 'rows1', man['rows_1s'], 'rows10', man['rows_10s'],
              'plugged!=0', man['plugged_nonzero'], flush=True)
    manifest['_definition'] = 'identical to trace_v1_manifest.json _definition (functions imported from extract_traces_v1.py unchanged)'
    manifest['_watch_csv'] = {k: dict(path=os.path.relpath(p, ROOT), present=os.path.exists(p)) for k, p in WATCH.items()}
    json.dump(manifest, open(mp, 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
    print('wrote', mp)


def _bins_from_judge(j):
    """Judge JSON segment blocks -> {segment label: [(t0, ratio-or-None, SKIN, AP)]} where ratio is the block's own reference."""
    out = {}
    for key in ('probe', 'rest', 'reheat'):
        blk = j.get(key)
        if isinstance(blk, dict) and blk.get('bins'):
            out[key] = blk['bins']
    if isinstance(j.get('heat'), dict) and j['heat'].get('bins'):
        out['heat'] = j['heat']['bins']
    return out


def verify():
    """Temperatures of every 10 s row that the judge JSON also lists (same nearest-HAL convention) + latency medians."""
    sim = v1.SIM
    tot = ok = 0
    detail = {}
    for tag, (od, name) in JUDGE.items():
        j = json.load(open(os.path.join(sim, od, f'{name}.json'), encoding='utf-8'))
        rr = list(csv.DictReader(open(os.path.join(DATA, f'trace_v21_10s_{tag}.csv'), encoding='utf-8')))
        segs = {s['label']: s['index'] for s in j['segments']}
        n_t = n_ok = 0
        for key, bins in _bins_from_judge(j).items():
            lab = {'probe': None, 'rest': None, 'reheat': None, 'heat': None}
            # segment index by role: heat = 1, probe = 2 (3-seg chains) · rest = 2, reheat = 3 (4-seg chains)
            idx = {'heat': 1, 'probe': 2, 'rest': 2, 'reheat': 3}[key]
            mine = {int(r['t_s']): r for r in rr if int(r['seg']) == idx and r['t_s'] != '-1'}
            for b in bins:
                t0 = b.get('t0')
                r = mine.get(t0)
                if r is None:
                    continue
                for k in ('SKIN', 'AP'):
                    if b.get(k) is None or r[k] == '':
                        continue
                    n_t += 1
                    if abs(float(r[k]) - float(b[k])) <= 0.05:
                        n_ok += 1
                if b.get('median_ms') is not None and r['lat_med_ms'] != '':
                    n_t += 1
                    if abs(float(r['lat_med_ms']) / float(b['median_ms']) - 1) <= 0.001:
                        n_ok += 1
        detail[tag] = dict(checked=n_t, match=n_ok, segments=segs)
        tot += n_t; ok += n_ok
        print(tag, 'checked', n_t, 'match', n_ok, flush=True)
    print('TOTAL', ok, '/', tot)
    return dict(total=tot, match=ok, detail=detail)


def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument('--check-v1', nargs='*')
    ap.add_argument('--only', nargs='*')
    ap.add_argument('--verify', action='store_true')
    a = ap.parse_args()
    if a.check_v1:
        return 0 if all(v2.check_v1(t) for t in a.check_v1) else 1
    if a.verify:
        r = verify()
        json.dump(r, open(os.path.join(ROOT, 'd1sim', 'out', 'trace_v21_verify.json'), 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
        return 0 if r['match'] == r['total'] else 1
    os.makedirs(DATA, exist_ok=True)
    write_all(a.only or list(RUNS), DATA)
    return 0


if __name__ == '__main__':
    sys.exit(main())
