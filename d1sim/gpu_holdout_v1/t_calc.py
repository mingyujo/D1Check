"""t_calc.py — T for the GPU same-work B chain (prereg GPU홀드아웃_사전등록_v1.md §2-2, energy-C rule), from N2 raw data only.

Rule (등록 §2-2): in N2 GBe_b1 and GBe_b2, the time at which B's cumulative inference count reaches the same block's A (GAe)
300 s total inference count; the mean of the two times, rounded UP to 10 s; T > 840 → T = 840 (recorded). No new measurement.
Primary value = the frozen N2 judge's own reach time (night1005e_judge pair → b_reach_s: first 10 s bin end whose cumulative
count ≥ n_A — the number the energy-C T (610 · 630 → 620) was taken from). Cross-check = the exact second of the n_A-th
inference start in GBe's work segment, read directly from the raw runner JSONL (results/, read only), and the GAe n_A recount.

  py -X utf8 -m d1sim.gpu_holdout_v1.t_calc [--selftest] [--out-od DIR] [--out-repo DIR]
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from d1sim.gpu_holdout_v1 import common as C

C.stdout_utf8()

N2_RUNS = {1: dict(a='S26_GAe_b1_1005e', b='S26_GBe_b1_1005e'), 2: dict(a='S26_GAe_b2_1005e', b='S26_GBe_b2_1005e')}


def segment0_window(gpu_jsonl):
    """segment 0 start_ns · end_ns from the runner JSONL (segment_start / segment_end detail, index 0)."""
    start_ns = end_ns = None
    with open(gpu_jsonl, 'rb') as fh:
        for line in fh:
            if b'"event":"segment_start"' in line or b'"event":"segment_end"' in line:
                e = json.loads(line.decode('utf-8'))
                d = e.get('detail')
                d = json.loads(d) if isinstance(d, str) else (d or {})
                if int(d.get('index', -1)) != 0:
                    continue
                if e['event'] == 'segment_start' and start_ns is None:
                    start_ns = int(d['start_ns'])
                elif e['event'] == 'segment_end' and end_ns is None:
                    end_ns = int(d['end_ns'])
    if start_ns is None or end_ns is None:
        raise SystemExit(f'segment 0 window not found in {gpu_jsonl}')
    return start_ns, end_ns


def work_inference_starts(gpu_jsonl, start_ns, end_ns):
    """sorted start_mono_ns of the inference events whose start lies in [start_ns, end_ns) (= the judge's work-segment rel_t set)."""
    st = []
    with open(gpu_jsonl, 'rb') as fh:
        for line in fh:
            if b'"event":"inference"' not in line:
                continue
            e = json.loads(line.decode('utf-8'))
            s = int(e['start_mono_ns'])
            if start_ns <= s < end_ns:
                st.append(s)
    st.sort()
    return st


def runner_jsonl(out_name):
    rd = os.path.join(C.ROOT, 'results', out_name, 'runs')
    subs = [d for d in os.listdir(rd) if os.path.isdir(os.path.join(rd, d))]
    if len(subs) != 1:
        raise SystemExit(f'{out_name}: runs {subs}')
    gl = [f for f in os.listdir(os.path.join(rd, subs[0], 'gpu')) if f.endswith('.jsonl')]
    if len(gl) != 1:
        raise SystemExit(f'{out_name}: runner JSONL count {len(gl)}')
    return subs[0], os.path.join(rd, subs[0], 'gpu', gl[0])


def reach_from_cumulative(cum, n_a):
    """night1005_judge._reach: first 10 s bin end with cum ≥ n_a (None if never)."""
    for c in cum:
        if c['cum'] >= n_a:
            return c['t_end']
    return None


def t_from_reaches(reaches, cap=C.T_CAP_S):
    mean = sum(reaches) / len(reaches)
    t = C.ceil10(mean)
    capped = t > cap
    return dict(reaches=list(reaches), mean_s=round(mean, 6), ceil10_s=t, cap_s=cap, capped=capped, T=min(t, cap))


def compute():
    blocks = {}
    for k, names in N2_RUNS.items():
        pair = C.load_json(os.path.join(C.N2_OUT, f'pair_GPU_b{k}.json'))
        ja = C.load_json(os.path.join(C.N2_OUT, f'GAe_b{k}.json'))
        jb = C.load_json(os.path.join(C.N2_OUT, f'GBe_b{k}.json'))
        if pair['a']['run_id'] != ja['run_id'] or pair['b']['run_id'] != jb['run_id']:
            raise SystemExit(f'block {k}: pair run ids ≠ judge JSONs')
        n_a = ja['work']['n']
        if pair['n_a'] != n_a:
            raise SystemExit(f'block {k}: pair n_a {pair["n_a"]} ≠ GAe work.n {n_a}')
        reach_judge = pair['b_reach_s']
        reach_recomputed = reach_from_cumulative(jb['work']['cumulative'], n_a)
        # raw cross-check
        rid_a, ja_jsonl = runner_jsonl(names['a'])
        rid_b, jb_jsonl = runner_jsonl(names['b'])
        if rid_a != ja['run_id'] or rid_b != jb['run_id']:
            raise SystemExit(f'block {k}: results run ids ≠ judge JSONs')
        a0, a1 = segment0_window(ja_jsonl)
        n_a_raw = len(work_inference_starts(ja_jsonl, a0, a1))
        b0, b1 = segment0_window(jb_jsonl)
        st_b = work_inference_starts(jb_jsonl, b0, b1)
        exact_s = (st_b[n_a - 1] - b0) / 1e9 if len(st_b) >= n_a else None
        blocks[k] = dict(a_out=names['a'], b_out=names['b'], a_run_id=ja['run_id'], b_run_id=jb['run_id'],
                         a_judge_sha256=C.sha256_file(os.path.join(C.N2_OUT, f'GAe_b{k}.json')), b_judge_sha256=C.sha256_file(os.path.join(C.N2_OUT, f'GBe_b{k}.json')),
                         pair_sha256=C.sha256_file(os.path.join(C.N2_OUT, f'pair_GPU_b{k}.json')),
                         n_a=n_a, n_b=jb['work']['n'], work_ratio_n2=pair['work_ratio'],
                         reach_s=reach_judge, reach_recomputed_s=reach_recomputed, reach_equal=(reach_judge == reach_recomputed),
                         raw=dict(n_a_recount=n_a_raw, n_a_equal=(n_a_raw == n_a), n_b_recount=len(st_b), n_b_equal=(len(st_b) == jb['work']['n']),
                                  exact_reach_s=None if exact_s is None else round(exact_s, 3), exact_in_bin=(exact_s is not None and reach_judge - 10 < exact_s <= reach_judge)))
    tt = t_from_reaches([blocks[k]['reach_s'] for k in sorted(blocks)])
    return dict(kind='gpuho_T_calc_v1', registration=f'{C.REG} §2-2', rule='N2 GBe_b1 · GBe_b2 에서 B 누적 추론 수가 같은 블록 GAe 의 300 s 총 추론 수에 닿은 시각 (10 s 칸 끝 · 판정기 b_reach_s) 두 개의 평균 → 10 s 올림 · 840 상한',
                blocks=blocks, **tt, chain_B=dict(work_d50=dict(duty=50, duration_s=tt['T']), tail_idle=dict(duty=1, duration_s=C.WINDOW_S - tt['T'])),
                energy_c_reference='NPU: b_reach 610 · 630 → 620 (에너지_사전등록_v1 §6-2)', this=C.sha256_file(os.path.abspath(__file__)))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--selftest', action='store_true')
    ap.add_argument('--out-od', default=C.OUT_OD)
    ap.add_argument('--out-repo', default=C.OUT_REPO)
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    res = compute()
    p1 = os.path.join(a.out_od, 'T_calc.json')
    s1 = C.write_json(p1, res)
    s2 = C.write_json(os.path.join(a.out_repo, 'T_calc.json'), res)
    for k, b in res['blocks'].items():
        print(f"block {k}: n_a {b['n_a']} · reach {b['reach_s']} s (recomputed {b['reach_recomputed_s']}) · raw exact {b['raw']['exact_reach_s']} s · n recount equal {b['raw']['n_a_equal']}/{b['raw']['n_b_equal']}")
    print(f"T: mean {res['mean_s']} → ceil10 {res['ceil10_s']} → T = {res['T']} (capped {res['capped']}) → B chain work_d50 {res['T']} s + tail_idle {C.WINDOW_S - res['T']} s")
    print('->', p1, s1, '| repo', s2)
    return 0


def selftest():
    res = []

    def check(name, cond, got=''):
        res.append((name, bool(cond), got))
    check('① ceil10: 500 → 500 · 495 → 500 · 500.1 → 510 · 491 → 500', C.ceil10(500) == 500 and C.ceil10(495) == 500 and C.ceil10(500.1) == 510 and C.ceil10(491) == 500)
    t = t_from_reaches([490, 510])
    check('② reaches 490 · 510 → mean 500 → T 500 (상한 아님)', t['T'] == 500 and t['mean_s'] == 500 and not t['capped'], t)
    t2 = t_from_reaches([490, 520])
    check('② reaches 490 · 520 → mean 505 → 올림 510', t2['T'] == 510, t2)
    t3 = t_from_reaches([840, 860])
    check('② reaches 840 · 860 → 850 > 840 → T = 840 (capped 기록)', t3['T'] == 840 and t3['capped'] and t3['ceil10_s'] == 850, t3)
    cum = [dict(t_end=10 * (i + 1), cum=100 * (i + 1)) for i in range(72)]
    check('③ reach_from_cumulative: n_a 250 → 30 s (경계 300 → 30) · 7201 → None', reach_from_cumulative(cum, 250) == 30 and reach_from_cumulative(cum, 300) == 30 and reach_from_cumulative(cum, 7201) is None)
    # synthetic runner JSONL: 50 inferences in segment 0 (1 s apart from 1000 ns), 5 in segment 1
    import tempfile
    tmp = tempfile.mkdtemp(prefix='gpuho_tcalc_')
    try:
        p = os.path.join(tmp, 'gpu.jsonl')
        J = lambda o: json.dumps(o, separators=(',', ':'))      # noqa: E731
        ns = 1_000_000_000
        with open(p, 'w', encoding='utf-8') as fh:
            fh.write(J(dict(event='run_metadata')) + '\n')
            fh.write(J(dict(event='segment_start', detail=J(dict(index=0, start_ns=1000)))) + '\n')
            for i in range(50):
                fh.write(J(dict(event='inference', start_mono_ns=1000 + i * ns, mono_ns=1000 + i * ns + 5)) + '\n')
            fh.write(J(dict(event='segment_end', detail=J(dict(index=0, end_ns=1000 + 50 * ns)))) + '\n')
            fh.write(J(dict(event='segment_start', detail=J(dict(index=1, start_ns=1000 + 50 * ns)))) + '\n')
            for i in range(5):
                fh.write(J(dict(event='inference', start_mono_ns=1000 + (50 + i) * ns, mono_ns=1000 + (50 + i) * ns + 5)) + '\n')
            fh.write(J(dict(event='segment_end', detail=J(dict(index=1, end_ns=1000 + 55 * ns)))) + '\n')
        a0, a1 = segment0_window(p)
        st = work_inference_starts(p, a0, a1)
        check('④ 합성 JSONL: 구간 0 창 · work 추론 50 (구간 1 의 5 제외) · 20번째 추론 = 19.0 s', (a0, a1) == (1000, 1000 + 50 * ns) and len(st) == 50 and (st[19] - a0) / 1e9 == 19.0)
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)
    check('⑤ N2 입력 존재: pair_GPU_b1 · b2 · GAe · GBe 판정 JSON · results 런 폴더', all(os.path.exists(os.path.join(C.N2_OUT, f)) for f in ('pair_GPU_b1.json', 'pair_GPU_b2.json', 'GAe_b1.json', 'GAe_b2.json', 'GBe_b1.json', 'GBe_b2.json'))
          and all(os.path.isdir(os.path.join(C.ROOT, 'results', n[s])) for n in N2_RUNS.values() for s in ('a', 'b')))
    return C.print_table(res)


if __name__ == '__main__':
    sys.exit(main())
