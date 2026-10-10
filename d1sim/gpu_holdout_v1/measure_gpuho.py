"""measure_gpuho.py — measured side of the GPU holdout check (prereg d1sim/docs/GPU홀드아웃_사전등록_v1.md §2 · §3). Written before any phone cell.

Input = cells_gpuho.json (cells_from_state.py — the valid attempt of every cell from the session driver's state file, or
'invalid_twice' / missing with the reason) and, per valid cell:
  · the GH judge JSON  OneDrive sim/out_gpuho/<cell>_b<k>[_re].json  (night1005e_judge_h.py wrapper over the frozen night1005e_judge.py 2db1cda5):
    start (load-start HAL SKIN/AP/BAT · lower flag · band) · temps.max_SKIN · temps.at_899.SKIN · work.first_throttle_s (k + 3 bins ≥ ×1.10, GPU)
    · work.throttle_time_s · work.bins ratios · n · rate
  · the GH pair JSON  sim/out_gpuho/pair_b<k>.json (wrapper pair — thermal description): measured block Δ max SKIN (A − B) · work ratio r · b_reach
  · the raw HAL series  results/S26_<cell>_b<k>_1011h[_re]/runs/<run_id>/raw/thermalservice.jsonl (1 s samples) with the segment-0 start_ns
    and last-segment end_ns from the runner JSONL → 10 s bin means of SKIN, k = [10k, 10k+10) s, 90 bins (model_error_v1.measure_energyc arithmetic, imported).
Cross-checks (must hold or the cell is flagged): recomputed max SKIN · 899 s SKIN · start SKIN · window length = judge JSON values · chain SHA · first throttle rule.
Blocks whose A or B has no valid run (invalid_twice) = "계산 불가" rows (kept in the 8-block denominator — judge_gpuho).
Noise baseline (등록 §3, description only): sample SD (n−1) of the measured Δ · SD of max SKIN among A cells · among B cells · start SKIN range.
results/ and the judge JSONs are read only.

  py -X utf8 -m d1sim.gpu_holdout_v1.measure_gpuho [--selftest] [--cells cells_gpuho.json] [--out-od DIR] [--out-repo DIR]
"""
from __future__ import annotations

import argparse
import os
import statistics
import sys

from d1sim.gpu_holdout_v1 import common as C
from d1sim.model_error_v1 import measure_energyc as ME     # segment_window_ns · load_hal · hal_metrics (unchanged arithmetic)

C.stdout_utf8()
CELLS_JSON_DEFAULT = os.path.join(C.OUT_OD, 'cells_gpuho.json')


def measure_cell(c):
    J = C.load_json(os.path.join(C.OD, c['judge_json']))
    if J['cell'] != c['cell'] or J['block'] != c['block']:
        raise SystemExit(f"judge JSON mismatch {c['judge_json']}: {J['cell']} b{J['block']} ≠ {c['cell']} b{c['block']}")
    rid = J['run_id']
    run_dir = os.path.join(C.ROOT, 'results', c['out_name'])
    runs = os.listdir(os.path.join(run_dir, 'runs'))
    if runs != [rid]:
        raise SystemExit(f"run dir {run_dir} runs {runs} ≠ {rid}")
    rdir = os.path.join(run_dir, 'runs', rid)
    gl = [f for f in os.listdir(os.path.join(rdir, 'gpu')) if f.endswith('.jsonl')]
    if len(gl) != 1:
        raise SystemExit(f'runner JSONL count {len(gl)} in {rdir}')
    gpu = os.path.join(rdir, 'gpu', gl[0])
    hal_path = os.path.join(rdir, 'raw', 'thermalservice.jsonl')
    a_ns, b_ns = ME.segment_window_ns(gpu)
    th = ME.load_hal(hal_path)
    hm = ME.hal_metrics(th, a_ns, b_ns)
    jt, jw, js = J['temps'], J['work'], J['start']
    start_skin = J['start_skin']
    checks = dict(max_skin_equal=(hm['max_skin'] == jt['max_SKIN']), n_samples_equal=(hm['n_samples'] == jt['n_samples']),
                  skin_899_equal=(hm['skin_899'] == jt['at_899']['SKIN']), start_skin_equal=(hm['start_skin'] == start_skin),
                  window_equal=(abs(hm['window_s'] - jt['window_s']) < 1e-6), chain_sha_equal=(J['chain_sha256'] == C.CELLS[c['cell']]['canonical']),
                  resource_gpu=(J['resource'] == 'GPU' and J['threshold_ratio'] == C.THR),
                  model_sha_label=(J.get('model_sha_check') or {}).get('label'), judge_h_sha_prefix=((J.get('judge_h') or {}).get('night1005e_judge') or {}).get('sha256', '')[:8],
                  phone_watch_events=None if J.get('phone_watch') is None else J['phone_watch']['n_events'])
    ratios = [b['ratio'] for b in jw['bins']]
    k1 = C.first_throttle(ratios, C.THR)
    checks['first_throttle_recomputed_equal'] = ((None if k1 is None else k1 * C.BIN_S) == jw['first_throttle_s'])
    return dict(block=c['block'], cell=c['cell'], side=C.CELLS[c['cell']]['side'], run_id=rid, out_name=c['out_name'], attempt=c.get('attempt'), retry=bool(c.get('retry')),
                run_dir=os.path.relpath(run_dir, C.ROOT), judge_json=c['judge_json'], judge_json_sha256=C.sha256_file(os.path.join(C.OD, c['judge_json'])),
                hal_sha256=C.sha256_file(hal_path), runner_jsonl=gl[0], runner_jsonl_bytes=os.path.getsize(gpu),
                start_skin=start_skin, start_ap=js['load_start_thermal']['AP'], start_bat=js['load_start_thermal']['BAT'],
                lower=js['lower']['label'], lower_marked=(js['lower']['label'] == '하한 미달'), band=js['band'], column=C.pick_column(start_skin), in_range=C.in_range(start_skin),
                max_skin=jt['max_SKIN'], skin_899=jt['at_899']['SKIN'], end_skin=(jw.get('end_thermal') or {}).get('SKIN'),
                t38_s=jt['t38_s'], t40_s=jt['t40_s'], t42_s=jt['t42_s'], status_ge1_s=jt['status_ge1_s'],
                first_throttle_s=jw['first_throttle_s'], first_throttle_label=jw['first_throttle_label'], throttle_time_s=jw['throttle_time_s'],
                ratio_bins=[C.r6(x) for x in ratios], n_active_bins=len(ratios), ref30_ms=jw['ref30_ms'], n=jw['n'], rate_per_s=jw['rate_per_s'],
                segment_window_ns=[a_ns, b_ns], hal=hm, checks=checks)


def block_rows(cells_json, cells):
    blocks = []
    for b in C.BLOCKS:
        a = next((c for c in cells if c['block'] == b and c['cell'] == 'GAh'), None)
        bb = next((c for c in cells if c['block'] == b and c['cell'] == 'GBh'), None)
        info = cells_json.get('blocks', {}).get(str(b), {})
        if a is None or bb is None:
            why = info.get('reason') or ('A 유효 런 없음' if a is None else 'B 유효 런 없음')
            blocks.append(dict(block=b, status='계산 불가', reason=why, run_a=None if a is None else a['run_id'], run_b=None if bb is None else bb['run_id'],
                               start_skin_a=None if a is None else a['start_skin'], start_skin_b=None if bb is None else bb['start_skin'],
                               start_skin_mean=None, column=None, in_range=None, d_max_skin_meas=None, d_first_throttle_meas=None, work_ratio=None,
                               lower=dict(a=None if a is None else a['lower'], b=None if bb is None else bb['lower'])))
            continue
        pp = os.path.join(C.OUT_OD, f'pair_b{b}.json')
        tp = C.load_json(pp)
        if tp['a']['run_id'] != a['run_id'] or tp['b']['run_id'] != bb['run_id'] or tp['block'] != b:
            raise SystemExit(f'pair_b{b} run ids / block differ from cells')
        mean_start = (a['start_skin'] + bb['start_skin']) / 2
        fa, fb = a['first_throttle_s'], bb['first_throttle_s']
        blocks.append(dict(block=b, status='계산', run_a=a['run_id'], run_b=bb['run_id'], start_skin_a=a['start_skin'], start_skin_b=bb['start_skin'],
                           start_skin_mean=round(mean_start, 3), column=C.pick_column(mean_start), in_range=C.in_range(mean_start),
                           d_max_skin_meas=tp['deltas']['d_max_skin'], d_max_skin_recomputed=round(a['max_skin'] - bb['max_skin'], 6),
                           d_throttle_time_meas=tp['deltas']['d_throttle_time_s'], d_t38_meas=tp['deltas']['d_t38_s'],
                           d_first_throttle_meas=None if (fa is None or fb is None) else fa - fb, first_throttle_a=fa, first_throttle_b=fb,
                           work_ratio=tp['work_ratio'], same_work_label=tp['same_work_label'], b_reach_s=tp.get('b_reach_s'),
                           lower=dict(a=a['lower'], b=bb['lower']), lower_marked=bool(a['lower_marked'] or bb['lower_marked']),
                           pair_json=os.path.relpath(pp, C.OD), pair_sha256=C.sha256_file(pp)))
    return blocks


def noise(cells, blocks):
    d = [b['d_max_skin_meas'] for b in blocks if b['d_max_skin_meas'] is not None]
    A = [c['max_skin'] for c in cells if c['cell'] == 'GAh']
    B = [c['max_skin'] for c in cells if c['cell'] == 'GBh']
    st = [c['start_skin'] for c in cells]
    sd = lambda xs: round(statistics.stdev(xs), 4) if len(xs) > 1 else None   # noqa: E731
    mean = lambda xs: round(statistics.mean(xs), 4) if xs else None            # noqa: E731
    rng = lambda xs: [min(xs), max(xs)] if xs else None                         # noqa: E731
    return dict(rule='표본 표준편차 (n − 1) · 기술만 (등록 §3)', n_blocks=len(d), delta_sd=sd(d), delta_mean=mean(d), delta_min=min(d) if d else None, delta_max=max(d) if d else None,
                maxskin_sd_A=sd(A), maxskin_sd_B=sd(B), maxskin_mean_A=mean(A), maxskin_mean_B=mean(B), start_skin_range=rng(st),
                start_skin_range_A=rng([c['start_skin'] for c in cells if c['cell'] == 'GAh']), start_skin_range_B=rng([c['start_skin'] for c in cells if c['cell'] == 'GBh']),
                skin899_sd_A=sd([c['skin_899'] for c in cells if c['cell'] == 'GAh']), skin899_sd_B=sd([c['skin_899'] for c in cells if c['cell'] == 'GBh']),
                n_lower_marked=sum(1 for c in cells if c['lower_marked']), n_out_of_range=sum(1 for c in cells if c['in_range'] is False))


def measure_all(cells_json):
    valid = [c for c in cells_json['cells'] if c.get('status') == 'valid']
    cells = [measure_cell(c) for c in valid]
    blocks = block_rows(cells_json, cells)
    return cells, blocks


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--selftest', action='store_true')
    ap.add_argument('--cells', default=CELLS_JSON_DEFAULT)
    ap.add_argument('--out-od', default=C.OUT_OD)
    ap.add_argument('--out-repo', default=C.OUT_REPO)
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    cj = C.load_json(a.cells)
    cells, blocks = measure_all(cj)
    bad = [(c['cell'], c['block'], k) for c in cells for k, v in c['checks'].items() if v is False]
    res = dict(kind='gpuho_measure_v1', registration=f'{C.REG} ({C.REG_COMMIT[:7]}) §2 · §3', cells_json=os.path.relpath(a.cells, C.OD) if a.cells.startswith(C.OD) else a.cells,
               cells_json_sha256=C.sha256_file(a.cells), n_cells=len(cells), cells=cells, blocks=blocks, noise=noise(cells, blocks), cross_check_failures=bad,
               not_computable_blocks=[b['block'] for b in blocks if b['status'] != '계산'], hal_note='HAL 1 s 표본 · 10 s 칸 평균 90칸 (P1j 와 같음)',
               shas=dict(this=C.sha256_file(os.path.abspath(__file__)), common_py=C.sha256_file(C.__file__), measure_energyc_py=C.sha256_file(ME.__file__)))
    p1 = os.path.join(a.out_od, 'measure_gpuho.json')
    s1 = C.write_json(p1, res)
    s2 = C.write_json(os.path.join(a.out_repo, 'measure_gpuho.json'), res)
    for c in cells:
        print(f"b{c['block']} {c['cell']} {c['out_name']} start {c['start_skin']} → col {c['column']} ({'범위 안' if c['in_range'] else '범위 밖'} · {c['lower']}) · max {c['max_skin']} · 899 s {c['skin_899']} · 1st thr {c['first_throttle_label']} · thr {c['throttle_time_s']} s · HAL bins {c['hal']['n_bins_with_samples']}/90 · checks {'OK' if all(v is not False for v in c['checks'].values()) else 'FAIL'}")
    for b in blocks:
        if b['status'] == '계산':
            print(f"block {b['block']}: Δmax meas {b['d_max_skin_meas']:+.1f} (recomputed {b['d_max_skin_recomputed']:+.1f}) · Δ1st thr {b['d_first_throttle_meas']} · start mean {b['start_skin_mean']} → col {b['column']} · r {b['work_ratio']:.4f}")
        else:
            print(f"block {b['block']}: 계산 불가 ({b['reason']})")
    print('noise', res['noise'])
    print('cross-check failures', bad)
    print('->', p1, s1, '| repo copy', s2)
    return 0


# ============================================================ selftest (합성 · 양방향 · 결과 전)
def selftest():
    res = []

    def check(name, cond, got=''):
        res.append((name, bool(cond), got))
    ns = 1_000_000_000
    th = [(100 * ns + i * ns, 30.0 + 0.1 * i) for i in range(900)]
    hm = ME.hal_metrics(th, 100 * ns, 100 * ns + 900 * ns)
    check('① HAL bins (imported measure_energyc arithmetic): 90 · bin 0 30.45 · n 900 · max 119.9 · 899 s 119.9',
          len(hm['bin_mean_skin']) == 90 and abs(hm['bin_mean_skin'][0] - 30.45) < 1e-9 and hm['n_samples'] == 900 and hm['max_skin'] == 119.9 and hm['skin_899'] == 119.9)
    check('② first_throttle GPU 규칙: [1,1,1.10,1.10,1.10,1.10,0.9] → 20 s · [1,1.07,1.07,1.07,1.07] → None', (lambda k: k * 10 if k is not None else None)(C.first_throttle([1, 1, 1.10, 1.10, 1.10, 1.10, 0.9], C.THR)) == 20
          and C.first_throttle([1, 1.07, 1.07, 1.07, 1.07], C.THR) is None)
    fake_cells = [dict(cell='GAh', max_skin=38.0 + i * 0.1, skin_899=31.0, start_skin=30.0 + i * 0.1, lower_marked=(i == 0), in_range=True) for i in range(8)] + \
                 [dict(cell='GBh', max_skin=38.0, skin_899=32.0, start_skin=30.5, lower_marked=False, in_range=(i != 3)) for i in range(8)]
    fake_blocks = [dict(d_max_skin_meas=0.1 * i) for i in range(8)]
    nz = noise(fake_cells, fake_blocks)
    check('③ noise: Δ sd = sd(0.0..0.7) · B max sd 0 · A start range [30.0, 30.7] · 하한 미달 1 · 범위 밖 1', nz['delta_sd'] == round(statistics.stdev([0.1 * i for i in range(8)]), 4)
          and nz['maxskin_sd_B'] == 0 and nz['start_skin_range_A'] == [30.0, 30.7] and nz['n_lower_marked'] == 1 and nz['n_out_of_range'] == 1, nz['delta_sd'])
    nz2 = noise(fake_cells, [dict(d_max_skin_meas=None)] * 8)
    check('③ noise: 계산 불가 블록만 → delta_sd None · n_blocks 0 (오류 없음)', nz2['delta_sd'] is None and nz2['n_blocks'] == 0)
    # block_rows: a block with a missing B → 계산 불가 · stays in the list of 8
    cells8 = [dict(block=b, cell='GAh', run_id=f'a{b}', start_skin=30.0, max_skin=38.0, first_throttle_s=100, lower='하한 통과', lower_marked=False) for b in C.BLOCKS]
    cj = dict(cells=[], blocks={'3': dict(reason='invalid_twice (B)')})
    br = block_rows(cj, cells8)
    check('④ block_rows: B 없는 8블록 → 전부 "계산 불가" · 블록 3 사유 = invalid_twice (B) · 분모 8', len(br) == 8 and all(b['status'] == '계산 불가' for b in br) and br[2]['reason'] == 'invalid_twice (B)', br[2])
    check('⑤ cells_gpuho.json 기본 경로 · results 폴더 접두 S26_<cell>_b<k>_1011h', CELLS_JSON_DEFAULT.endswith('cells_gpuho.json') and C.SESSION_SFX == '1011h')
    return C.print_table(res)


if __name__ == '__main__':
    sys.exit(main())
