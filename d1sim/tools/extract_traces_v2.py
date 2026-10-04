"""extract_traces_v2.py — the 2026-10-03 night runs (M1-NPU a/b · M1-GPU r2 · GPU pacing) as v1-format traces. READ-ONLY on results/.

extract_traces_v1.py is NOT modified: its RUNS table is hard-coded, so this file imports its functions (extract, write_csv,
load_watch, KEEP_1S/KEEP_10S) unchanged and only supplies a new run table + output prefix `trace_v2_`. Definitions are
therefore identical to v1 (1 s / 10 s bins, segment windows, HAL nearest sample, first-30 s ref row t_s = -1).

  py d1sim/tools/extract_traces_v2.py                 # write d1sim/data/trace_v2_<tag>.csv, trace_v2_10s_<tag>.csv, trace_v2_manifest.json
  py d1sim/tools/extract_traces_v2.py --check-v1 m1   # re-extract a v1 tag through this module into a temp dir and compare bytes
                                                      # with d1sim/data/trace_v1_<tag>.csv (+10s): proves the import path is unchanged
"""
from __future__ import annotations

import argparse
import filecmp
import json
import os
import sys
import tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, ROOT)
from d1sim.tools import extract_traces_v1 as v1  # noqa: E402

DATA = v1.DATA
WATCH_1003 = os.path.join(ROOT, 'results', 'S26_night_1003_host', 'skin_watch_1003.csv')

# tag: (result dir, run_id or None, resource label, duty, role) — same tuple shape as v1.RUNS
RUNS = {
    'm1n_a': ('results/S26_M1_npu_1003', None, 'NPU', None, 'chain NPU d10 60 / d100 600 / d10 600 — M1-NPU (a), v2 FIT (release)'),
    'm1n_b': ('results/S26_M1_npu_r2_1003', None, 'NPU', None, 'chain NPU d10 60 / d100 600 / d10 600 — M1-NPU (b), v2 half-holdout'),
    'm1g_r2': ('results/S26_M1_gpu_r2_1003', None, 'GPU', None, 'chain GPU d10 60 / d100 1200 / d10 300 — M1-GPU 2nd run, v2 half-holdout'),
    'gpace': ('results/S26_GPUpace_1003', None, 'GPU', None, 'chain GPU d10 60 / d100 600 / d10 60 / d100 300 — pacing, v2 half-holdout'),
}


def write_all(tags, prefix, out_dir, watch):
    mp = os.path.join(out_dir, f'{prefix}manifest.json')
    manifest = json.load(open(mp, encoding='utf-8')) if os.path.exists(mp) else {}
    table = {**v1.RUNS, **RUNS}
    for tag in tags:
        res, rid, resource, duty, role = table[tag]
        rows1, rows10, man = v1.extract(tag, res, rid, resource, duty, watch)
        man['role'] = role
        v1.write_csv(os.path.join(out_dir, f'{prefix}{tag}.csv'), rows1, v1.KEEP_1S)
        v1.write_csv(os.path.join(out_dir, f'{prefix}10s_{tag}.csv'), rows10, v1.KEEP_10S)
        manifest[tag] = man
        print(tag, man['run_id'], 'segments', len(man['segments']), 'inf', man['n_inference'], 'rows1', man['rows_1s'], 'rows10', man['rows_10s'],
              'plugged!=0', man['plugged_nonzero'], flush=True)
    manifest['_definition'] = 'identical to trace_v1_manifest.json _definition (functions imported from extract_traces_v1.py unchanged)'
    manifest['_watch_csv'] = dict(path=os.path.relpath(WATCH_1003, ROOT), present=bool(watch))
    json.dump(manifest, open(mp, 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
    print('wrote', mp)


def check_v1(tag):
    """Byte comparison: v1 tag extracted through this module == committed trace_v1_<tag>.csv files."""
    with tempfile.TemporaryDirectory() as td:
        write_all([tag], 'trace_v1_', td, v1.load_watch(v1.WATCH))
        ok = True
        for name in (f'trace_v1_{tag}.csv', f'trace_v1_10s_{tag}.csv'):
            same = filecmp.cmp(os.path.join(td, name), os.path.join(DATA, name), shallow=False)
            print(name, 'byte-identical' if same else 'DIFFERS')
            ok = ok and same
    return ok


def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument('--check-v1', nargs='*')
    ap.add_argument('--only', nargs='*')
    a = ap.parse_args()
    if a.check_v1:
        return 0 if all(check_v1(t) for t in a.check_v1) else 1
    os.makedirs(DATA, exist_ok=True)
    write_all(a.only or list(RUNS), 'trace_v2_', DATA, v1.load_watch(WATCH_1003))
    return 0


if __name__ == '__main__':
    sys.exit(main())
