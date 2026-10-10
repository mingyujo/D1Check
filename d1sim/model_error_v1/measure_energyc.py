"""measure_energyc.py — measured side of the model-error check (prereg d1sim/docs/모형오차_사전등록_v1.md §2 · §3, 9e29851).

16 valid energy-C cells (8 blocks × NAc · NBc; NBc_b7 → NBc_b7_re · NAc_b8 → NAc_b8_re — freeze_energy.txt 19:0x) read from
  · the energy-C judge JSONs  OneDrive sim/out_1008c · out_1009c/<cell>_b<k>[_re].json  (night1005e_judge_c.py 4e4dbcd3, produced 10/8):
    start (load-start HAL SKIN/AP/BAT · lower flag · band) · temps.max_SKIN · temps.at_899.SKIN · work.first_throttle_s (k + 3 bins ≥ ×1.06)
    · work.throttle_time_s · work.bins ratios · n · rate
  · the thermal pair JSONs  sim/out_energy/c_thermal_pairs/tpair_b<k>.json: measured block Δ max SKIN (A − B) · work ratio (already public, 등록 §0)
  · the raw HAL series  results/S26_<cell>_b<k>_<sess>[_re]/runs/<run_id>/raw/thermalservice.jsonl (1 s samples) with the segment-0 start_ns
    and last-segment end_ns from the runner JSONL (segment_start / segment_end detail) → 10 s bin means of SKIN, k = [10k, 10k+10) s, 90 bins.
Cross-checks (must hold or the cell is flagged): recomputed max SKIN · 899 s SKIN · start SKIN · window length = judge JSON values.
Noise baseline (등록 §3, description only): sample SD (n−1) of the 8 measured Δ · SD of max SKIN among A cells · among B cells · start SKIN range.
results/ and the judge JSONs are read only.

  py -X utf8 -m d1sim.model_error_v1.measure_energyc [--selftest] [--out-od DIR] [--out-repo DIR]
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys

from d1sim.model_error_v1 import common as C

C.stdout_utf8()
HEAD_BYTES = 8 * 1024 * 1024
TAIL_BYTES = 8 * 1024 * 1024


def cell_sources():
    out = []
    for b in C.BLOCKS:
        tp_path = os.path.join(C.OD_SIM, 'out_energy', 'c_thermal_pairs', f'tpair_b{b}.json')
        tp = C.load_json(tp_path)
        sess = '1008c' if b <= 4 else '1009c'
        for side, cell in (('a', 'NAc'), ('b', 'NBc')):
            rid = tp[side]['run_id']
            suf = '_re' if (cell, b) in (('NAc', 8), ('NBc', 7)) else ''
            rd = os.path.join(C.ROOT, 'results', f'S26_{cell}_b{b}_{sess}{suf}')
            jj = os.path.join(C.OD_SIM, f'out_{sess}', f'{cell}_b{b}{suf}.json')
            out.append(dict(block=b, cell=cell, run_id=rid, run_dir=rd, judge_json=jj, tpair_json=tp_path, session=sess, retry=bool(suf)))
    return out


def segment_window_ns(gpu_jsonl):
    """segment 0 start_ns (segment_start detail) and last segment end_ns (segment_end detail) — read head and tail only."""
    size = os.path.getsize(gpu_jsonl)
    with open(gpu_jsonl, 'rb') as fh:
        head = fh.read(min(HEAD_BYTES, size))
        fh.seek(max(0, size - TAIL_BYTES))
        tail = fh.read()
    # the runner flushes lifecycle events (segment_start / segment_end / load_end) ahead of the inference events, so both ends of the
    # window are normally in the head; the tail is scanned too (fallback). The segment_end with the highest index wins.
    start_ns, end_ns, end_idx = None, None, -1
    for chunk in (head, tail):
        for line in chunk.split(b'\n'):
            if b'"event":"segment_start"' in line:
                d = json.loads(json.loads(line.decode('utf-8'))['detail'])
                if d.get('index') == 0 and start_ns is None:
                    start_ns = int(d['start_ns'])
            elif b'"event":"segment_end"' in line:
                d = json.loads(json.loads(line.decode('utf-8'))['detail'])
                if int(d.get('index', -1)) > end_idx:
                    end_idx, end_ns = int(d['index']), int(d['end_ns'])
    if start_ns is None or end_ns is None:
        raise SystemExit(f'segment window not found in {gpu_jsonl}')
    return start_ns, end_ns


def load_hal(path):
    th = []
    with open(path, encoding='utf-8') as fh:
        for line in fh:
            if not line.strip():
                continue
            try:
                s = json.loads(line)
            except ValueError:
                continue
            if s.get('parse_status') in (None, 'ok') and isinstance(s.get('mono_ns'), int) and s.get('SKIN') not in (None, ''):
                th.append((s['mono_ns'], float(s['SKIN'])))
    th.sort()
    return th


def hal_metrics(th, start_ns, end_ns, n_bins=C.N_BINS, bin_s=C.BIN_S):
    """window = [start_ns, end_ns] (night1005 hal_window) · bins k = [10k, 10k+10) s from start_ns · nearest sample for start and 899 s."""
    win = [(t, v) for t, v in th if start_ns <= t <= end_ns]
    sums, cnts = [0.0] * n_bins, [0] * n_bins
    for t, v in win:
        k = int((t - start_ns) // (bin_s * 1_000_000_000))
        if 0 <= k < n_bins:
            sums[k] += v
            cnts[k] += 1
    means = [round(sums[k] / cnts[k], 4) if cnts[k] else None for k in range(n_bins)]

    def nearest(ns):
        if not th:
            return None, None
        t, v = min(th, key=lambda s: abs(s[0] - ns))
        return v, (t - ns) / 1e9
    s0, dt0 = nearest(start_ns)
    s899, dt899 = nearest(start_ns + C.T_899 * 1_000_000_000)
    return dict(n_samples=len(win), max_skin=max(v for _, v in win) if win else None, bin_mean_skin=means, bin_counts=cnts,
                n_bins_with_samples=sum(1 for c in cnts if c), start_skin=s0, start_dt_s=None if dt0 is None else round(dt0, 6),
                skin_899=s899, skin_899_dt_s=None if dt899 is None else round(dt899, 6), window_s=(end_ns - start_ns) / 1e9)


def measure_cell(src):
    J = C.load_json(src['judge_json'])
    if J['run_id'] != src['run_id'] or J['cell'] != src['cell'] or J['block'] != src['block']:
        raise SystemExit(f"judge JSON mismatch {src['judge_json']}")
    rid = src['run_id']
    runs = os.listdir(os.path.join(src['run_dir'], 'runs'))
    if runs != [rid]:
        raise SystemExit(f"run dir {src['run_dir']} runs {runs} ≠ {rid}")
    rdir = os.path.join(src['run_dir'], 'runs', rid)
    gl = [f for f in os.listdir(os.path.join(rdir, 'gpu')) if f.endswith('.jsonl')]
    if len(gl) != 1:
        raise SystemExit(f'runner JSONL count {len(gl)} in {rdir}')
    gpu = os.path.join(rdir, 'gpu', gl[0])
    hal_path = os.path.join(rdir, 'raw', 'thermalservice.jsonl')
    a_ns, b_ns = segment_window_ns(gpu)
    th = load_hal(hal_path)
    hm = hal_metrics(th, a_ns, b_ns)
    jt, jw, js = J['temps'], J['work'], J['start']
    start_skin = J['start_skin']
    checks = dict(max_skin_equal=(hm['max_skin'] == jt['max_SKIN']), n_samples_equal=(hm['n_samples'] == jt['n_samples']),
                  skin_899_equal=(hm['skin_899'] == jt['at_899']['SKIN']), start_skin_equal=(hm['start_skin'] == start_skin),
                  window_equal=(abs(hm['window_s'] - jt['window_s']) < 1e-6), chain_sha_equal=(J['chain_sha256'] == C.CELLS[src['cell']]['canonical']),
                  judge_c_sha_prefix=J['judge_c']['night1005e_judge']['sha256'][:8], phone_watch_events=J['phone_watch']['n_events'])
    ratios = [b['ratio'] for b in jw['bins']]
    k1 = C.first_throttle(ratios)
    checks['first_throttle_recomputed_equal'] = ((None if k1 is None else k1 * C.BIN_S) == jw['first_throttle_s'])
    return dict(block=src['block'], cell=src['cell'], side=C.CELLS[src['cell']]['side'], run_id=rid, session=src['session'], retry=src['retry'],
                run_dir=os.path.relpath(src['run_dir'], C.ROOT), judge_json=os.path.relpath(src['judge_json'], C.OD), judge_json_sha256=C.sha256_file(src['judge_json']),
                hal_sha256=C.sha256_file(hal_path), runner_jsonl=gl[0], runner_jsonl_bytes=os.path.getsize(gpu),
                start_skin=start_skin, start_ap=js['load_start_thermal']['AP'], start_bat=js['load_start_thermal']['BAT'],
                lower=js['lower']['label'], band=js['band'], column=C.pick_column(start_skin), in_range=C.in_range(start_skin),
                max_skin=jt['max_SKIN'], skin_899=jt['at_899']['SKIN'], end_skin=(jw.get('end_thermal') or {}).get('SKIN'),
                t38_s=jt['t38_s'], t40_s=jt['t40_s'], t42_s=jt['t42_s'], status_ge1_s=jt['status_ge1_s'],
                first_throttle_s=jw['first_throttle_s'], first_throttle_label=jw['first_throttle_label'], throttle_time_s=jw['throttle_time_s'],
                ratio_bins=[C.r6(x) for x in ratios], n_active_bins=len(ratios), ref30_ms=jw['ref30_ms'], n=jw['n'], rate_per_s=jw['rate_per_s'],
                segment_window_ns=[a_ns, b_ns], hal=hm, checks=checks)


def noise(cells, blocks):
    d = [b['d_max_skin_meas'] for b in blocks]
    A = [c['max_skin'] for c in cells if c['cell'] == 'NAc']
    B = [c['max_skin'] for c in cells if c['cell'] == 'NBc']
    st = [c['start_skin'] for c in cells]
    sd = lambda xs: round(statistics.stdev(xs), 4) if len(xs) > 1 else None
    return dict(rule='표본 표준편차 (n − 1) · 기술만 (등록 §3)', n_blocks=len(d), delta_sd=sd(d), delta_mean=round(statistics.mean(d), 4),
                delta_min=min(d), delta_max=max(d), maxskin_sd_A=sd(A), maxskin_sd_B=sd(B), maxskin_mean_A=round(statistics.mean(A), 4),
                maxskin_mean_B=round(statistics.mean(B), 4), start_skin_range=[min(st), max(st)],
                start_skin_range_A=[min(c['start_skin'] for c in cells if c['cell'] == 'NAc'), max(c['start_skin'] for c in cells if c['cell'] == 'NAc')],
                start_skin_range_B=[min(c['start_skin'] for c in cells if c['cell'] == 'NBc'), max(c['start_skin'] for c in cells if c['cell'] == 'NBc')],
                skin899_sd_A=sd([c['skin_899'] for c in cells if c['cell'] == 'NAc']), skin899_sd_B=sd([c['skin_899'] for c in cells if c['cell'] == 'NBc']))


def measure_all(sources=None):
    sources = sources or cell_sources()
    cells = [measure_cell(s) for s in sources]
    blocks = []
    for b in C.BLOCKS:
        tp = C.load_json(os.path.join(C.OD_SIM, 'out_energy', 'c_thermal_pairs', f'tpair_b{b}.json'))
        a = next(c for c in cells if c['block'] == b and c['cell'] == 'NAc')
        bb = next(c for c in cells if c['block'] == b and c['cell'] == 'NBc')
        if tp['a']['run_id'] != a['run_id'] or tp['b']['run_id'] != bb['run_id']:
            raise SystemExit(f'tpair_b{b} run ids differ from cells')
        mean_start = (a['start_skin'] + bb['start_skin']) / 2
        blocks.append(dict(block=b, run_a=a['run_id'], run_b=bb['run_id'], start_skin_a=a['start_skin'], start_skin_b=bb['start_skin'],
                           start_skin_mean=round(mean_start, 3), column=C.pick_column(mean_start), in_range=C.in_range(mean_start),
                           d_max_skin_meas=tp['deltas']['d_max_skin'], d_max_skin_recomputed=round(a['max_skin'] - bb['max_skin'], 6),
                           d_throttle_time_meas=tp['deltas']['d_throttle_time_s'], d_t38_meas=tp['deltas']['d_t38_s'], work_ratio=tp['work_ratio'],
                           same_work_label=tp['same_work_label'], lower=dict(a=a['lower'], b=bb['lower']), tpair_sha256=C.sha256_file(os.path.join(C.OD_SIM, 'out_energy', 'c_thermal_pairs', f'tpair_b{b}.json'))))
    return cells, blocks


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--selftest', action='store_true')
    ap.add_argument('--out-od', default=C.OUT_OD)
    ap.add_argument('--out-repo', default=C.OUT_REPO)
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    cells, blocks = measure_all()
    bad = [(c['cell'], c['block'], k) for c in cells for k, v in c['checks'].items() if v is False]
    res = dict(kind='modelerr_measure_energyc_v1', registration=f'{C.REG} ({C.REG_COMMIT[:7]}) §2 · §3', n_cells=len(cells), cells=cells, blocks=blocks,
               noise=noise(cells, blocks), cross_check_failures=bad, hal_note='HAL 1 s 표본 (등록 §2 "2 s" 와 다름 — freeze_modelerr.txt (a))',
               shas=dict(this=C.sha256_file(os.path.abspath(__file__)), common_py=C.sha256_file(C.__file__)))
    p1 = os.path.join(a.out_od, 'measure_energyc.json')
    s1 = C.write_json(p1, res)
    s2 = C.write_json(os.path.join(a.out_repo, 'measure_energyc.json'), res)
    for c in cells:
        print(f"b{c['block']} {c['cell']} start {c['start_skin']} → col {c['column']} ({'범위 안' if c['in_range'] else '범위 밖'}) · max {c['max_skin']} · 899 s {c['skin_899']} · 1st thr {c['first_throttle_label']} · thr {c['throttle_time_s']} s · HAL bins {c['hal']['n_bins_with_samples']}/90 · checks {'OK' if all(v is not False for v in c['checks'].values()) else 'FAIL'}")
    for b in blocks:
        print(f"block {b['block']}: Δmax meas {b['d_max_skin_meas']:+.1f} (recomputed {b['d_max_skin_recomputed']:+.1f}) · start mean {b['start_skin_mean']} → col {b['column']} · r {b['work_ratio']:.4f}")
    print('noise', res['noise'])
    print('cross-check failures', bad)
    print('->', p1, s1, '| repo copy', s2)
    return 0


# ============================================================ selftest (합성 · 양방향)
def selftest():
    res = []

    def check(name, cond, got=''):
        res.append((name, bool(cond), got))
    ns = 1_000_000_000
    th = [(100 * ns + i * ns, 30.0 + 0.1 * i) for i in range(900)]          # 1 s samples, SKIN 30.0 → 119.9 (linear)
    hm = hal_metrics(th, 100 * ns, 100 * ns + 900 * ns)
    check('① bins: 90 · bin 0 mean = mean(30.0..30.9) = 30.45 · bin 89 mean = mean(119.0..119.9) = 119.45 · 10 samples each', len(hm['bin_mean_skin']) == 90
          and abs(hm['bin_mean_skin'][0] - 30.45) < 1e-9 and abs(hm['bin_mean_skin'][89] - 119.45) < 1e-9 and all(c == 10 for c in hm['bin_counts']), hm['bin_mean_skin'][:2])
    check('① window: n 900 · max = last sample 119.9 · start = 30.0 (dt 0) · 899 s = 119.9 (dt 0)', hm['n_samples'] == 900 and hm['max_skin'] == 119.9
          and hm['start_skin'] == 30.0 and hm['start_dt_s'] == 0 and hm['skin_899'] == 119.9 and hm['skin_899_dt_s'] == 0)
    hm2 = hal_metrics(th, 100 * ns + 500_000_000, 100 * ns + 900 * ns)       # window starts 0.5 s after the first sample
    check('① nearest sample: start_ns + 0.5 s → nearest is sample 0 or 1 (|dt| 0.5) · bins shift (bin 0 has 10 samples 1..10)',
          abs(hm2['start_dt_s']) == 0.5 and hm2['bin_counts'][0] == 10 and abs(hm2['bin_mean_skin'][0] - sum(30.0 + 0.1 * i for i in range(1, 11)) / 10) < 1e-9, hm2['bin_mean_skin'][0])
    th_gap = [s for s in th if not (200 <= (s[0] - 100 * ns) // ns < 230)]    # 30 s gap → bins 20..22 empty
    hm3 = hal_metrics(th_gap, 100 * ns, 100 * ns + 900 * ns)
    check('① HAL gap → empty bins are None · n_bins_with_samples 87', hm3['bin_mean_skin'][20] is None and hm3['bin_mean_skin'][23] is not None and hm3['n_bins_with_samples'] == 87)
    check('② first_throttle recomputation rule on judge ratios: [1,1,1.07,1.07,1.07,1.07,0.9] → 20 s', (lambda k: k * 10 if k is not None else None)(C.first_throttle([1, 1, 1.07, 1.07, 1.07, 1.07, 0.9])) == 20)
    check('② pick_column / in_range: 28.8 → 29.5 안 · 27.2 → 29.5 밖 · 31.7 → 30.5 밖 · 30.0 → 29.5', C.pick_column(28.8) == 29.5 and C.in_range(28.8) and C.pick_column(27.2) == 29.5
          and C.in_range(27.2) is False and C.pick_column(31.7) == 30.5 and C.in_range(31.7) is False and C.pick_column(30.0) == 29.5)
    fake_cells = [dict(cell='NAc', max_skin=37.0 + i * 0.1, skin_899=31.0, start_skin=30.0 + i * 0.1) for i in range(8)] + \
                 [dict(cell='NBc', max_skin=35.0, skin_899=32.0, start_skin=30.5) for _ in range(8)]
    fake_blocks = [dict(d_max_skin_meas=2.0 + 0.1 * i) for i in range(8)]
    nz = noise(fake_cells, fake_blocks)
    check('③ noise: Δ sd = sd(2.0..2.7) (4자리 반올림 0.2449) · B max sd 0 · A start range [30.0, 30.7]', nz['delta_sd'] == round(statistics.stdev([2.0 + 0.1 * i for i in range(8)]), 4)
          and nz['maxskin_sd_B'] == 0 and nz['start_skin_range_A'] == [30.0, 30.7], nz['delta_sd'])
    # segment window parser on a synthetic runner JSONL (head/tail scan)
    import tempfile
    tmp = tempfile.mkdtemp(prefix='modelerr_measure_selftest_')
    try:
        p = os.path.join(tmp, 'gpu.jsonl')
        J = lambda o: json.dumps(o, separators=(',', ':'))      # runner JSONL is compact (no spaces) — same as the real files
        with open(p, 'w', encoding='utf-8') as fh:
            fh.write(J(dict(event='run_metadata')) + '\n')
            fh.write(J(dict(event='segment_start', detail=J(dict(index=0, start_ns=1000)))) + '\n')
            for i in range(5000):
                fh.write(J(dict(event='inference', start_mono_ns=1000 + i, mono_ns=1001 + i)) + '\n')
            fh.write(J(dict(event='segment_end', detail=J(dict(index=0, end_ns=5000)))) + '\n')
            fh.write(J(dict(event='segment_start', detail=J(dict(index=1, start_ns=5100)))) + '\n')
            fh.write(J(dict(event='segment_end', detail=J(dict(index=1, end_ns=9000)))) + '\n')
            fh.write(J(dict(event='load_end')) + '\n')
        check('④ segment window = segment 0 start_ns 1000 · last segment end_ns 9000', segment_window_ns(p) == (1000, 9000), segment_window_ns(p))
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)
    srcs = cell_sources()
    check('⑤ 16 sources · 8 blocks × 2 cells · retry cells = NAc_b8 · NBc_b7 · all run dirs and judge JSONs exist',
          len(srcs) == 16 and sorted((s['cell'], s['block']) for s in srcs if s['retry']) == [('NAc', 8), ('NBc', 7)]
          and all(os.path.isdir(s['run_dir']) and os.path.exists(s['judge_json']) for s in srcs))
    ok = all(c for _, c, _ in res)
    print('| 시험 | 결과 | 값 |\n|---|---|---|')
    for name, c, got in res:
        print(f"| {name} | {'PASS' if c else 'FAIL'} | {str(got)[:160]} |")
    print(f"\nselftest 전체: {'PASS' if ok else 'FAIL'} ({sum(1 for _, c, _ in res if c)}/{len(res)})")
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
