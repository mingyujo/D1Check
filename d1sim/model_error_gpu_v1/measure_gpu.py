"""measure_gpu.py — measured side of the GPU model-error check (prereg §2 · §3, commit 35c9342) → sim/out_gpuerr/measure_gpu.json.
Run AFTER commit ② (first reading of the measured thermal series by this check). Sources (preflight (a)):
  · d1sim/data/trace_<v>_<tag>.csv      1 s rows (HAL SKIN sample inside [k, k+1) else the last before · t_load_s = chain-absolute time incl. transitions)
  · d1sim/data/trace_<v>_10s_<tag>.csv  10 s runner-latency bins per segment (all-inference median) + ref row t_s = −1 (first-30 s median)
  · OneDrive sim/out_*/<run>.json        that run's own judge output (start · max_SKIN · first-throttle items by its own "칸 k + 뒤 3칸" rule)
  · results/<run>/runs/<id>/raw/thermalservice.jsonl  raw HAL (only where the folder still exists — cross-check of max · start SKIN)
Per run: start SKIN · max SKIN (trace; judge where present) · SKIN by absolute second (for the window-end value at any T) · 10 s bin means ·
measured first throttle (judge item → chain-absolute s) + trace recomputation (same rule) as cross-check. Pairs: pair JSON deltas + Δ first throttle.
Resources: resource JSON verdicts. results/ · judge JSONs · traces are read only.

  py -X utf8 -m d1sim.model_error_gpu_v1.measure_gpu [--selftest] [--out-od DIR] [--out-repo DIR]
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from d1sim.model_error_gpu_v1 import common as C

C.stdout_utf8()


def skin_series(tag):
    """[(t_abs_s, SKIN)] over all 1 s rows with a SKIN · plus max t."""
    out = []
    for r in C.trace1(tag):
        if r['SKIN'] != '':
            out.append((float(r['t_load_s']), float(r['SKIN'])))
    return out


def judge_first_throttle(tag, J):
    """measured first throttle by the run's own judge rule → (segment-relative s, segment index, label)."""
    sec, seg = C.RUNS[tag]['judge_ft']
    if sec.startswith('v0_holdout:'):
        T = sec.split(':')[1]
        v = C.load_json(os.path.join(C.ROOT, 'd1sim', 'out', 'v0_holdout_1003.json'))[T]['onset_meas_s']
        return v, seg, f'v0_holdout_1003.json {T} onset_meas_s (onset_time_ref +10 % · 30 s 유지 · t ≥ 30, ref = 처음 30 s 중앙)'
    v = C.get_path(J, sec)
    return v, seg, f'{os.path.basename(C.RUNS[tag]["judge"])} {sec}'


def trace_first_throttle(tag, seg, thr):
    """같은 규칙을 추출 10 s 칸에: ratio = lat_med / ref(그 구간 처음 30 s 중앙) · 칸 k + 뒤 3칸 ≥ thr → 10k (구간 기준). cross-check only."""
    rows = [r for r in C.trace10(tag) if int(r['seg']) == seg]
    ref = next((C.fl(r['lat_med_ms']) for r in rows if r['t_s'] == '-1'), None)
    bins = [(C.fl(r['lat_med_ms']) / ref) if (ref and C.fl(r['lat_med_ms']) is not None) else None for r in rows if r['t_s'] != '-1']
    k = C.first_throttle(bins, thr)
    return (None if k is None else 10 * k), ref, len(bins)


def raw_hal_check(tag, m):
    rd = os.path.join(C.ROOT, m['result_dir'], 'runs', m['run_id'], 'raw', 'thermalservice.jsonl')
    if not os.path.exists(rd):
        return dict(present=False)
    a, b = m['segments'][0]['start_ns'], m['segments'][-1]['end_ns']
    th = []
    with open(rd, encoding='utf-8') as fh:
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
    win = [(t, v) for t, v in th if a <= t <= b]
    start = min(th, key=lambda s: abs(s[0] - a))[1] if th else None
    return dict(present=True, n_samples=len(win), max_skin=max(v for _, v in win) if win else None, start_skin_nearest=start, hal_sha256=C.sha256_file(rd))


def measure_run(tag, cells):
    r = C.RUNS[tag]
    m = C.run_manifest(tag)
    J = C.load_json(C.judge_path(tag))
    ss = skin_series(tag)
    t_max = max(t for t, _ in ss)
    n_bins = int((t_max + 1) // C.BIN_S)
    bins, cnts = C.bin_means(ss, n_bins)
    offs = C.seg_offsets_meas(tag)
    ft_rel, seg, ft_label = judge_first_throttle(tag, J)
    ft_abs = None if ft_rel is None else round(offs[seg] + ft_rel, 3)
    tr_rel, ref_ms, nb = trace_first_throttle(tag, seg, C.THR[r['resource']])
    max_judge = C.get_path(J, 'temps.max_SKIN')
    start_trace = cells['runs'][tag]['start_skin']
    raw = raw_hal_check(tag, m)
    max_trace = max(v for _, v in ss)
    checks = dict(start_skin_equal_judge=cells['runs'][tag]['start_skin_equal'],
                  max_skin_trace_equal_judge=(None if max_judge is None else abs(max_trace - max_judge) < 1e-9),
                  first_throttle_trace_equal_judge=(tr_rel == ft_rel),
                  raw_hal_max_equal_trace=(None if not raw['present'] else (raw['max_skin'] == max_trace)),
                  raw_hal_start_equal_trace=(None if not raw['present'] else (raw['start_skin_nearest'] == start_trace)),
                  rows_1s_equal_manifest=(len(C.trace1(tag)) == m['rows_1s']))
    return dict(tag=tag, label=r['label'], resource=r['resource'], model=r['model'], group=r['group'], role=r['role'], run_id=m['run_id'],
                start_skin=start_trace, in_range=C.in_range(start_trace), lower=cells['runs'][tag]['lower'], column_2pt=C.pick_column(start_trace),
                max_skin=max_trace, max_skin_judge=max_judge, t_max=t_max, n_rows_with_skin=len(ss), skin_by_t=[(t, v) for t, v in ss],
                bin_mean_skin=bins, bin_counts=cnts, n_bins=n_bins, seg_offsets_meas=offs,
                first_throttle=dict(rel_s=ft_rel, segment=seg, abs_s=ft_abs, source=ft_label, trace_recomputed_rel_s=tr_rel, trace_ref_ms=ref_ms, trace_n_bins=nb, threshold=C.THR[r['resource']]),
                throttle_time_judge_s=C.get_path(J, 'work.throttle_time_s'), t38_judge_s=C.get_path(J, 'temps.t38_s'), skin_899_judge=C.get_path(J, 'temps.at_899.SKIN'),
                judge_json=r['judge'], judge_json_sha256=C.sha256_file(C.judge_path(tag)), trace_1s_sha256=cells['runs'][tag]['trace_1s_sha256'], raw_hal=raw, checks=checks)


def measure_pairs(runs):
    out = {}
    for key, p in C.PAIRS.items():
        J = C.load_json(C.judge_path(p['judge']))
        a, b = runs[p['a']], runs[p['b']]
        fa, fb = a['first_throttle']['abs_s'], b['first_throttle']['abs_s']
        out[key] = dict(resource=p['resource'], group=p['group'], block=p['block'], a=p['a'], b=p['b'], start_skin_a=a['start_skin'], start_skin_b=b['start_skin'],
                        start_skin_mean=round((a['start_skin'] + b['start_skin']) / 2, 3), column_2pt=C.pick_column((a['start_skin'] + b['start_skin']) / 2),
                        in_range=(a['in_range'] and b['in_range']), d_max_skin=J['deltas']['d_max_skin'], d_max_skin_recomputed=C.r6(a['max_skin'] - b['max_skin']),
                        d_t38_s=J['deltas']['d_t38_s'], d_throttle_time_s=J['deltas']['d_throttle_time_s'], work_ratio=J['work_ratio'], same_work=J['same_work'], signs=J['signs'],
                        first_throttle_a=fa, first_throttle_b=fb, d_first_throttle_s=None if (fa is None or fb is None) else round(fa - fb, 3),
                        judge_json=p['judge'], judge_json_sha256=C.sha256_file(C.judge_path(p['judge'])), note=p.get('note'),
                        checks=dict(d_max_equal_recomputed=abs(J['deltas']['d_max_skin'] - (a['max_skin'] - b['max_skin'])) < 1e-6))
    return out


def measure_resources():
    out = {}
    for key, r in C.RESOURCES.items():
        J = C.load_json(C.judge_path(r['judge']))
        out[key] = dict(resource=r['resource'], group=r['group'], pairs=list(r['pairs']), verdict=J['verdict'], verdict_index=J.get('verdict_index'), sentence=J.get('sentence'),
                        judge_json=r['judge'], judge_json_sha256=C.sha256_file(C.judge_path(r['judge'])), note=r.get('note'))
    return out


def measure_all(cells):
    runs = {tag: measure_run(tag, cells) for tag in C.RUNS}
    return runs, measure_pairs(runs), measure_resources()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--selftest', action='store_true')
    ap.add_argument('--out-od', default=C.OUT_OD)
    ap.add_argument('--out-repo', default=C.OUT_REPO)
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    cells = C.load_json(C.CELLS_JSON)
    runs, pairs, resources = measure_all(cells)
    bad = [(t, k) for t, r in runs.items() for k, v in r['checks'].items() if v is False] + [(k, 'd_max') for k, p in pairs.items() if not p['checks']['d_max_equal_recomputed']]
    res = dict(kind='gpuerr_measure_v1', registration=f'{C.REG} ({C.REG_COMMIT[:7]}) §2 · §3', cells_sha256=C.sha256_file(C.CELLS_JSON), n_runs=len(runs), runs=runs, pairs=pairs, resources=resources,
               cross_check_failures=bad, shas=dict(this=C.sha256_file(os.path.abspath(__file__)), common_py=C.sha256_file(C.__file__)),
               note='실측 = 추출 trace (1 s HAL · 10 s 지연) + 판정 JSON (preflight (a)) · 창 끝 · 칸 정의 = preflight (e)')
    p1 = os.path.join(a.out_od, 'measure_gpu.json')
    s1 = C.write_json(p1, res)
    s2 = C.write_json(os.path.join(a.out_repo, 'measure_gpu.json'), res)
    for t, r in runs.items():
        ft = r['first_throttle']
        print(f"{t:15s} start {r['start_skin']} ({'안' if r['in_range'] else '밖'}) · max {r['max_skin']} (judge {r['max_skin_judge']}) · t_max {r['t_max']} · bins {r['n_bins']} · 1st thr {ft['rel_s']} (seg {ft['segment']} → abs {ft['abs_s']}; trace {ft['trace_recomputed_rel_s']}) · raw {r['raw_hal'].get('max_skin')} · checks {'OK' if all(v is not False for v in r['checks'].values()) else 'FAIL'}")
    for k, p in pairs.items():
        print(f"pair {k}: Δmax {p['d_max_skin']:+.1f} (recomputed {p['d_max_skin_recomputed']:+.1f}) · Δthr {p['d_first_throttle_s']} · r {p['work_ratio']:.4f} · col {p['column_2pt']}")
    for k, r in resources.items():
        print(f"resource {k}: {r['verdict']}")
    print('cross-check failures', bad)
    print('->', p1, s1, '| repo copy', s2)
    return 0


# ============================================================ selftest (합성 · 양방향 · 실제 trace 읽기 0)
def selftest():
    res = []

    def check(name, cond, got=''):
        res.append((name, bool(cond), got))
    ss = [(float(t), 30.0 + 0.01 * t) for t in range(0, 1301)]
    bins, cnts = C.bin_means(ss, int((1300 + 1) // 10))
    check('① 1301 행 (0..1300) → 130 칸 · 칸 0 = mean(30.00..30.09) = 30.045 · 칸 129 = 42.945 · 10 표본씩', len(bins) == 130 and abs(bins[0] - 30.045) < 1e-9 and abs(bins[129] - 42.945) < 1e-9 and all(c == 10 for c in cnts), bins[:2])
    ss2 = [(60.134 + t, 31.0) for t in range(0, 20)]
    b2, c2 = C.bin_means(ss2, 8)
    check('① 전환 오프셋 (60.134 + t): 칸 6 = [60, 70) 에 10 행 · 칸 7 에 10 행 · 칸 5 비어 None', c2[6] == 10 and c2[7] == 10 and b2[5] is None and b2[6] == 31.0, (c2, b2))
    check('② first_throttle on 10 s ratio bins (trace rule): [1.0,1.05,1.12,1.11,1.10,1.15] → k 2 → 20 s · [1.0]*6 → None',
          C.first_throttle([1.0, 1.05, 1.12, 1.11, 1.10, 1.15], 1.10) == 2 and C.first_throttle([1.0] * 6, 1.10) is None)
    check('③ get_path: heat.onset_1_1_s · work.first_throttle_s · 없으면 None', C.get_path(dict(heat=dict(onset_1_1_s=70)), 'heat.onset_1_1_s') == 70 and C.get_path(dict(work={}), 'work.first_throttle_s') is None and C.get_path({}, 'a.b') is None)
    check('④ 런 표의 judge_ft 구간: N1 · N2 = 0 (work) · 가열 구간 체인 = 1 · v0 = 0', all(C.RUNS[t]['judge_ft'][1] == 0 for t in C.RUNS if C.RUNS[t]['group'] in ('N1', 'N1s', 'N2'))
          and all(C.RUNS[t]['judge_ft'][1] == 1 for t in ('m1g_r2', 'gpace', 'g50p', 'gi300', 'g50p2', 'n4_gie_b1', 'n4_nie_b1')) and C.RUNS['c1a']['judge_ft'][1] == 0)
    offs = C.seg_offsets_meas('n1_ga_b1')
    check('⑤ seg_offsets_meas (manifest): 구간 0 = 0 · 구간 1 ≈ 300 (+ 전환 < 1 s) · model 오프셋 [0, 300]', offs[0] == 0 and 300 <= offs[1] < 301 and C.seg_offsets_model('n1_ga_b1') == [0, 300], offs)
    # synthetic raw-HAL / trace agreement path: bin_means over a series with a gap → None bins counted
    ss3 = [(t, 30.0) for t in range(0, 100) if not 30 <= t < 50]
    b3, c3 = C.bin_means(ss3, 10)
    check('⑥ HAL 공백 (30~50 s) → 칸 3 · 4 None · 나머지 10 표본', b3[3] is None and b3[4] is None and sum(1 for c in c3 if c == 10) == 8)
    check('⑦ pairs 표: Δ첫 조임 = A − B (둘 다 있을 때만) — 합성', (lambda fa, fb: None if (fa is None or fb is None) else fa - fb)(90, 470) == -380 and (lambda fa, fb: None if (fa is None or fb is None) else fa - fb)(None, 470) is None)
    return C.print_table(res)


if __name__ == '__main__':
    sys.exit(main())
