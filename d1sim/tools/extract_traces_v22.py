"""extract_traces_v22.py — night N1 (1005n) · N2 (1005e) · N4 (1005r/1006r) chain runs as v1-format traces (v2.2 data). READ-ONLY on results/.

Prereg sim/스로틀모형_사전등록_v22.md §1 · §2 (mirror d1sim/docs/, commit 9056685 — before any fit).
Same pattern as extract_traces_v21.py: extract_traces_v1.py is NOT modified — this file imports its functions (extract, write_csv,
load_watch, KEEP_1S/KEEP_10S) unchanged and only supplies a new run table + output prefix `trace_v22_`.

  py d1sim/tools/extract_traces_v22.py                 # write d1sim/data/trace_v22_<tag>.csv, trace_v22_10s_<tag>.csv, trace_v22_manifest.json
  py d1sim/tools/extract_traces_v22.py --check-v1 m1   # byte comparison through the v2 helper (import path unchanged)
  py d1sim/tools/extract_traces_v22.py --verify        # 10 s bins vs sim/out_1005n · out_1005e · out_1005r judge JSONs
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
from d1sim.tools import extract_traces_v2 as v2  # noqa: E402  (check_v1 helper; never modified)

DATA = v1.DATA
WATCH = {'1005n': os.path.join(ROOT, 'results', 'S26_night_1005n_host', 'skin_watch_1005n.csv'),
         '1005e': os.path.join(ROOT, 'results', 'S26_host_1005e', 'skin_watch_1005e.csv'),
         '1006r': os.path.join(ROOT, 'results', 'S26_host_1006r', 'skin_watch_1006r.csv')}

# tag: (result dir, run_id or None, resource label, duty, role, watch key, judge (out dir, file), group)
RUNS = {
    'n1_na_b1': ('results/S26_NA_b1_1005n', None, 'NPU', None, 'N1 NA b1 — MobileNet NPU d100 300 / d1 600', '1005n', ('out_1005n', 'NA_b1'), 'dev'),
    'n1_na_b2': ('results/S26_NA_b2_1005n', None, 'NPU', None, 'N1 NA b2', '1005n', ('out_1005n', 'NA_b2'), 'dev'),
    'n1_nb_b1': ('results/S26_NB_b1_1005n', None, 'NPU', None, 'N1 NB b1 — MobileNet NPU d50 660 / d1 240', '1005n', ('out_1005n', 'NB_b1'), 'dev'),
    'n1_nb_b2': ('results/S26_NB_b2_1005n', None, 'NPU', None, 'N1 NB b2', '1005n', ('out_1005n', 'NB_b2'), 'dev'),
    'n1_ga_b1': ('results/S26_GA_b1_1005n', None, 'GPU', None, 'N1 GA b1 — MobileNet GPU d100 300 / d1 600', '1005n', ('out_1005n', 'GA_b1'), 'dev'),
    'n1_ga_b2': ('results/S26_GA_b2_1005n', None, 'GPU', None, 'N1 GA b2', '1005n', ('out_1005n', 'GA_b2'), 'dev'),
    'n1_gb_b1': ('results/S26_GB_b1_1005n', None, 'GPU', None, 'N1 GB b1 — MobileNet GPU d50 480 / d1 420', '1005n', ('out_1005n', 'GB_b1'), 'dev'),
    'n1_gb_b2': ('results/S26_GB_b2_1005n', None, 'GPU', None, 'N1 GB b2 (하한 미달 시작)', '1005n', ('out_1005n', 'GB_b2'), 'dev'),
    'n2_nae_b1': ('results/S26_NAe_b1_1005e', None, 'NPU', None, 'N2 NAe b1 — EffNet NPU d100 300 / d1 600', '1005e', ('out_1005e', 'NAe_b1'), 'dev'),
    'n2_nae_b2': ('results/S26_NAe_b2_1005e', None, 'NPU', None, 'N2 NAe b2', '1005e', ('out_1005e', 'NAe_b2'), 'dev'),
    'n2_nbe_b1': ('results/S26_NBe_b1_1005e', None, 'NPU', None, 'N2 NBe b1 — EffNet NPU d50 660 / d1 240', '1005e', ('out_1005e', 'NBe_b1'), 'dev'),
    'n2_nbe_b2': ('results/S26_NBe_b2_1005e', None, 'NPU', None, 'N2 NBe b2', '1005e', ('out_1005e', 'NBe_b2'), 'dev'),
    'n2_gae_b1': ('results/S26_GAe_b1_1005e', None, 'GPU', None, 'N2 GAe b1 — EffNet GPU d100 300 / d1 600', '1005e', ('out_1005e', 'GAe_b1'), 'dev'),
    'n2_gae_b2': ('results/S26_GAe_b2_1005e', None, 'GPU', None, 'N2 GAe b2', '1005e', ('out_1005e', 'GAe_b2'), 'dev'),
    'n2_gbe_b1': ('results/S26_GBe_b1_1005e', None, 'GPU', None, 'N2 GBe b1 — EffNet GPU d50 720 / d1 180', '1005e', ('out_1005e', 'GBe_b1'), 'dev'),
    'n2_gbe_b2': ('results/S26_GBe_b2_1005e', None, 'GPU', None, 'N2 GBe b2', '1005e', ('out_1005e', 'GBe_b2'), 'dev'),
    'n4_gie_b1': ('results/S26_GIe_b1_1005r', None, 'GPU', None, 'N4 GIe b1 — EffNet GPU d10 60 / d100 600 / d1 300 / d100 300', '1005e', ('out_1005r', 'GIe_b1'), 'dev'),
    'n4_gie_b2': ('results/S26_GIe_b2_1005r', None, 'GPU', None, 'N4 GIe b2', '1006r', ('out_1005r', 'GIe_b2'), 'dev'),
    'n4_nie_b1': ('results/S26_NIe_b1_1005r', None, 'NPU', None, 'N4 NIe b1 — EffNet NPU d10 60 / d100 300 / d1 300 / d100 180', '1005e', ('out_1005r', 'NIe_b1'), 'dev'),
    'n4_nie_b2': ('results/S26_NIe_b2_1005r', None, 'NPU', None, 'N4 NIe b2', '1006r', ('out_1005r', 'NIe_b2'), 'dev'),
    'h_nb_b2_re': ('results/S26_NB_b2_1005n_re', None, 'NPU', None, 'N1 보충 NB b2 — 약한 홀드아웃 (피팅 안 씀)', '1006r', ('out_1005n', 'NB_b2_re'), 'holdout'),
    'h_gb_b2_re': ('results/S26_GB_b2_1005n_re', None, 'GPU', None, 'N1 보충 GB b2 — 약한 홀드아웃 (피팅 안 씀)', '1006r', ('out_1005n', 'GB_b2_re'), 'holdout'),
    'h_gie_b1_spare': ('results/S26_GIe_b1_1005r_spare', None, 'GPU', None, 'N4 예비 GIe b1 — 약한 홀드아웃 (피팅 안 씀)', '1006r', ('out_1005r', 'GIe_b1_spare'), 'holdout'),
}
DEV_TAGS = [t for t, r in RUNS.items() if r[7] == 'dev']
HOLDOUT_TAGS = [t for t, r in RUNS.items() if r[7] == 'holdout']


def write_all(tags, out_dir):
    mp = os.path.join(out_dir, 'trace_v22_manifest.json')
    manifest = json.load(open(mp, encoding='utf-8')) if os.path.exists(mp) else {}
    for tag in tags:
        res, rid, resource, duty, role, wk, judge, group = RUNS[tag]
        rows1, rows10, man = v1.extract(tag, res, rid, resource, duty, v1.load_watch(WATCH[wk]))
        man['role'] = role
        man['group'] = group
        v1.write_csv(os.path.join(out_dir, f'trace_v22_{tag}.csv'), rows1, v1.KEEP_1S)
        v1.write_csv(os.path.join(out_dir, f'trace_v22_10s_{tag}.csv'), rows10, v1.KEEP_10S)
        manifest[tag] = man
        print(tag, man['run_id'], 'segments', len(man['segments']), 'inf', man['n_inference'], 'rows1', man['rows_1s'], 'rows10', man['rows_10s'],
              'plugged!=0', man['plugged_nonzero'], flush=True)
    manifest['_definition'] = 'identical to trace_v1_manifest.json _definition (functions imported from extract_traces_v1.py unchanged)'
    manifest['_watch_csv'] = {k: dict(path=os.path.relpath(p, ROOT), present=os.path.exists(p)) for k, p in WATCH.items()}
    json.dump(manifest, open(mp, 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
    print('wrote', mp)


def _rows10(tag):
    return list(csv.DictReader(open(os.path.join(DATA, f'trace_v22_10s_{tag}.csv'), encoding='utf-8')))


def verify():
    """10 s bins vs the judge JSONs: ratio (bin median / first-30 s median of the segment) rel <= 0.1 %, SKIN · AP <= 0.05 C,
    median_ms rel <= 0.1 % where the judge lists it. N1/N2 = work.bins (segment 0); N4 = heat.bins_ratio (seg 1) + rest.bins (seg 2)
    + reheat.bins (seg 3)."""
    tot = ok = 0
    detail = {}
    for tag, r in RUNS.items():
        od, name = r[6]
        j = json.load(open(os.path.join(v1.SIM, od, f'{name}.json'), encoding='utf-8'))
        rr = _rows10(tag)
        by_seg = {}
        for x in rr:
            by_seg.setdefault(int(x['seg']), {})[int(x['t_s'])] = x
        n_t = n_ok = 0
        bad = []

        def chk(kind, a, b, tol, rel):
            nonlocal n_t, n_ok
            if a in (None, '') or b is None:
                return
            n_t += 1
            d = abs(float(a) / float(b) - 1) if rel else abs(float(a) - float(b))
            if d <= tol + 1e-12:
                n_ok += 1
            elif len(bad) < 5:
                bad.append((kind, a, b))

        def seg_rows(i):
            s = by_seg.get(i, {})
            ref = s.get(-1)
            return s, (float(ref['lat_med_ms']) if ref and ref['lat_med_ms'] != '' else None)

        if j.get('kind') == 'night1005_run':
            s, ref = seg_rows(0)
            for b in j['work']['bins']:
                x = s.get(int(b['t0']))
                if x is None:
                    continue
                if b.get('ratio') is not None and x['lat_med_ms'] != '' and ref:
                    chk('ratio', float(x['lat_med_ms']) / ref, b['ratio'], 0.001, True)
                for k in ('SKIN', 'AP'):
                    chk(k, x[k], b.get(k), 0.05, False)
                chk('median_ms', x['lat_med_ms'], b.get('median_ms'), 0.001, True)
        else:
            s, ref = seg_rows(1)
            for t0, val in (j['heat'].get('bins_ratio') or []):     # [[t0, ratio vs heat ref30], …]
                x = s.get(int(t0))
                if x is not None and val is not None and x['lat_med_ms'] != '' and ref:
                    chk('heat_ratio', float(x['lat_med_ms']) / ref, val, 0.001, True)
            for key, seg in (('rest', 2), ('reheat', 3)):
                s, _ = seg_rows(seg)
                for b in (j.get(key) or {}).get('bins') or []:
                    x = s.get(int(b['t0']))
                    if x is None:
                        continue
                    for k in ('SKIN', 'AP'):
                        chk(k, x[k], b.get(k), 0.05, False)
                    chk('median_ms', x['lat_med_ms'], b.get('median_ms'), 0.001, True)
        detail[tag] = dict(checked=n_t, match=n_ok, first_mismatch=bad)
        tot += n_t; ok += n_ok
        print(tag, 'checked', n_t, 'match', n_ok, bad[:2], flush=True)
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
        json.dump(r, open(os.path.join(ROOT, 'd1sim', 'out', 'trace_v22_verify.json'), 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
        return 0 if r['match'] == r['total'] else 1
    os.makedirs(DATA, exist_ok=True)
    write_all(a.only or list(RUNS), DATA)
    return 0


if __name__ == '__main__':
    sys.exit(main())
