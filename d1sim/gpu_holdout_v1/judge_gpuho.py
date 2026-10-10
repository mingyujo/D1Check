"""judge_gpuho.py — m1~m6 · block pass · k · 3-way GPU verdict (prereg d1sim/docs/GPU홀드아웃_사전등록_v1.md §3 · §4). Written before any phone cell. Runs ONCE.

Inputs: predict_gpuho.json (predict_gpuho.py, committed before the first cell) · measure_gpuho.json (measure_gpuho.py).
Per cell · per model (column = measured load-start SKIN → nearest of 29.5 / 30.5, tie 29.5, no interpolation — V3 v2 rule):
  m1 = predicted max SKIN − measured max SKIN (℃)        m2 = predicted SKIN at 899 s − measured 899 s SKIN (℃)
  m3 = mean |predicted − measured| over the 10 s bin means k = 0..89 (bins without HAL samples skipped, count written)
  m4 = predicted first-throttle time − measured (s); null + reason when either side has none (k + 3 bins ≥ ×1.10 GPU rule both sides)
Per block · per model (column = nearest to the mean of the two cells' start SKIN):
  m5 (주): predicted Δ = pred(GAh) max SKIN − pred(GBh) max SKIN (same column) vs measured Δ (pair d_max_skin) → same sign (6-dp, 0 is its own
  sign) AND |pred Δ − meas Δ| ≤ 1.0 ℃ (6-dp) → block pass. A block without a measured pair (invalid_twice) or without a prediction = "계산 불가"
  (not a pass, stays in /8).   m6 (기술): block Δ first throttle (A − B) predicted vs measured (null when either side has none).
k = passes / 8 → k ≥ 7 "GPU 재현 확인 (같은 계열 새 세션 · 8블록 중 k)" · 5 ≤ k ≤ 6 "GPU 부분 재현 (k/8)" · k ≤ 4 "GPU 재현 미확인 (k/8)".
Main verdict = v22 only (표 ① new row "GPU 홀드아웃 (GH)"). Sensitivity models are listed beside it and never enter the main verdict.
m1~m4 · m6 = description only. 하한 미달 cells / blocks are judged and flagged. Noise (measure) is copied. The judge refuses to run if its
output already exists (readout once — 등록 §4-5).

  py -X utf8 -m d1sim.gpu_holdout_v1.judge_gpuho [--selftest] [--pred f] [--meas f] [--out-od DIR] [--out-repo DIR]
"""
from __future__ import annotations

import argparse
import copy
import csv
import os
import statistics
import sys

from d1sim.gpu_holdout_v1 import common as C

C.stdout_utf8()
OUT_NAME = 'gpuho_judge.json'


def _pred_for(pred_runs, cell, model, column):
    try:
        return pred_runs[cell][model][str(column)]
    except (KeyError, TypeError):
        return None


def cell_errors(p, mc):
    if p is None:
        return dict(status='계산 불가', m1=None, m2=None, m3=None, m3_n_bins=0, m4=None, m4_reason='예측 없음')
    m1 = C.r6(p['max_skin'] - mc['max_skin'])
    m2 = None if (p.get('skin_899') is None or mc.get('skin_899') is None) else C.r6(p['skin_899'] - mc['skin_899'])
    pairs = [(a, b) for a, b in zip(p['bin_mean_skin'], mc['hal']['bin_mean_skin']) if a is not None and b is not None]
    m3 = C.r6(sum(abs(a - b) for a, b in pairs) / len(pairs)) if pairs else None
    pf, mf = p.get('first_throttle_s'), mc.get('first_throttle_s')
    if pf is None and mf is None:
        m4, why = None, '둘 다 없음 (예측 · 실측 모두 조임 없음)'
    elif pf is None:
        m4, why = None, f'예측 없음 (실측 {mf} s)'
    elif mf is None:
        m4, why = None, f'실측 없음 (예측 {pf} s)'
    else:
        m4, why = pf - mf, None
    return dict(status='계산', m1=m1, m2=m2, m3=m3, m3_n_bins=len(pairs), m4=m4, m4_reason=why,
                pred_max_skin=p['max_skin'], pred_skin_899=p.get('skin_899'), pred_first_throttle_s=pf, pred_throttle_time_s=p.get('throttle_time_s'),
                d_throttle_time_s=None if p.get('throttle_time_s') is None else p['throttle_time_s'] - mc['throttle_time_s'])


def block_pass(pred_a, pred_b, d_meas, d_ft_meas=None):
    if pred_a is None or pred_b is None:
        return dict(status='계산 불가', reason='예측 없음', d_pred=None, same_sign=None, abs_diff=None, passed=False, m6_d_pred=None, m6_d_meas=d_ft_meas, m6_diff=None)
    if d_meas is None:
        return dict(status='계산 불가', reason='실측 쌍 없음 (invalid_twice)', d_pred=C.r6(pred_a['max_skin'] - pred_b['max_skin']), same_sign=None, abs_diff=None, passed=False,
                    m6_d_pred=None, m6_d_meas=None, m6_diff=None)
    d_pred = C.r6(pred_a['max_skin'] - pred_b['max_skin'])
    same = C.sign(d_pred) == C.sign(d_meas)
    ad = round(abs(d_pred - d_meas), 6)
    fa, fb = pred_a.get('first_throttle_s'), pred_b.get('first_throttle_s')
    m6p = None if (fa is None or fb is None) else fa - fb
    return dict(status='계산', d_pred=d_pred, d_meas=C.r6(d_meas), sign_pred=C.sign(d_pred), sign_meas=C.sign(d_meas), same_sign=same, abs_diff=ad,
                within=(ad <= C.PASS_ABS + 0.0), passed=bool(same and ad <= C.PASS_ABS),
                m6_d_pred=m6p, m6_d_meas=d_ft_meas, m6_diff=None if (m6p is None or d_ft_meas is None) else m6p - d_ft_meas)


def summarize(vals):
    v = [x for x in vals if x is not None]
    if not v:
        return dict(n=0, mean=None, mean_abs=None, max_abs=None, sd=None)
    return dict(n=len(v), mean=C.r6(statistics.mean(v)), mean_abs=C.r6(statistics.mean(abs(x) for x in v)), max_abs=C.r6(max(abs(x) for x in v)),
                sd=C.r6(statistics.stdev(v)) if len(v) > 1 else None)


def judge(pred, meas, models=C.MODELS, main=C.MAIN):
    runs = pred['runs']
    cells_out, blocks_out, per_model = [], [], {}
    for mc in meas['cells']:
        row = dict(block=mc['block'], cell=mc['cell'], run_id=mc['run_id'], out_name=mc.get('out_name'), start_skin=mc['start_skin'], column=mc['column'], in_range=mc['in_range'],
                   lower=mc['lower'], lower_marked=mc.get('lower_marked'), meas_max_skin=mc['max_skin'], meas_skin_899=mc['skin_899'], meas_first_throttle_s=mc['first_throttle_s'],
                   meas_throttle_time_s=mc['throttle_time_s'], hal_bins=mc['hal']['n_bins_with_samples'], models={})
        for m in models:
            row['models'][m] = cell_errors(_pred_for(runs, mc['cell'], m, mc['column']), mc)
        cells_out.append(row)
    for mb in meas['blocks']:
        row = dict(block=mb['block'], meas_status=mb['status'], reason=mb.get('reason'), start_skin_mean=mb['start_skin_mean'], column=mb['column'], in_range=mb['in_range'],
                   d_meas=mb['d_max_skin_meas'], d_first_throttle_meas=mb.get('d_first_throttle_meas'), work_ratio=mb['work_ratio'], lower=mb['lower'], lower_marked=mb.get('lower_marked'), models={})
        for m in models:
            col = mb['column'] if mb['column'] is not None else C.COLUMNS[0]
            row['models'][m] = block_pass(_pred_for(runs, 'GAh', m, col), _pred_for(runs, 'GBh', m, col), mb['d_max_skin_meas'], mb.get('d_first_throttle_meas'))
        blocks_out.append(row)
    n_blocks = len(blocks_out)
    if n_blocks != len(C.BLOCKS):
        raise SystemExit(f'blocks {n_blocks} ≠ {len(C.BLOCKS)} — measure must list every block (계산 불가 included)')
    for m in models:
        k = sum(1 for b in blocks_out if b['models'][m]['passed'])
        n_na = sum(1 for b in blocks_out if b['models'][m]['status'] == '계산 불가')
        per_model[m] = dict(label=C.MODEL_LABEL.get(m, m), k=k, n_blocks=n_blocks, n_not_computable=n_na, verdict=C.verdict_label(k, n_blocks),
                            blocks_passed=[b['block'] for b in blocks_out if b['models'][m]['passed']],
                            blocks_failed=[b['block'] for b in blocks_out if not b['models'][m]['passed']],
                            m1=summarize([c['models'][m]['m1'] for c in cells_out]), m2=summarize([c['models'][m]['m2'] for c in cells_out]),
                            m3=summarize([c['models'][m]['m3'] for c in cells_out]), m4=summarize([c['models'][m]['m4'] for c in cells_out]),
                            m4_null=sum(1 for c in cells_out if c['models'][m]['m4'] is None),
                            m1_A=summarize([c['models'][m]['m1'] for c in cells_out if c['cell'] == 'GAh']), m1_B=summarize([c['models'][m]['m1'] for c in cells_out if c['cell'] == 'GBh']),
                            m6=summarize([b['models'][m]['m6_diff'] for b in blocks_out]),
                            d_pred_blocks=[b['models'][m]['d_pred'] for b in blocks_out], abs_diff_blocks=[b['models'][m]['abs_diff'] for b in blocks_out])
    main_v = per_model[main]
    sens = {m: per_model[m] for m in models if m != main}
    return dict(kind='gpuho_judge_v1', registration=f'{C.REG} ({C.REG_COMMIT[:7]}) §3 · §4', main_model=main, models=list(models),
                rule=dict(block_pass='m5 부호 같음 (6자리) 그리고 |예측 Δ − 실측 Δ| ≤ 1.0 ℃ (6자리) · 계산 불가 (invalid_twice · 예측 없음) = 통과 아님 · 분모 8 유지',
                          verdict='k ≥ 7 GPU 재현 확인 · 5 ≤ k ≤ 6 GPU 부분 재현 · k ≤ 4 GPU 재현 미확인 · 주 모형 판정만 표 ① 새 행 · 민감도는 나란히 기술',
                          column='칸 = 시작 SKIN 에 가까운 열 · 블록 = A·B 시작 SKIN 평균에 가까운 열 (같으면 29.5 · 보간 없음) · 범위 [28.3, 31.6] 밖 · 하한 미달은 표시만',
                          m4='첫 조임 = 칸 k + 뒤 3칸 ≥ ×1.10 (GPU · night1005e 판정기 규칙) 예측 · 실측 같은 규칙 · m6 = 블록 Δ첫 조임 (A − B) 기술'),
                main_verdict=dict(model=main, k=main_v['k'], n_blocks=n_blocks, verdict=main_v['verdict']), per_model=per_model, sensitivity=sens,
                cells=cells_out, blocks=blocks_out, noise=meas.get('noise'), not_computable_blocks=[b['block'] for b in blocks_out if b['meas_status'] != '계산'],
                n_lower_marked_cells=sum(1 for c in cells_out if c.get('lower_marked')), n_out_of_range_cells=sum(1 for c in cells_out if c['in_range'] is False))


def actual_rows(pred_actual, meas, models=C.MODELS):
    """Described-only (등록 §1 기술 열): same m1~m5 arithmetic with the actual-start predictions — 판정 아님."""
    if not pred_actual:
        return None
    rows = pred_actual.get('actual_rows') or {}
    cells, blocks = [], []
    for mc in meas['cells']:
        key = C.cell_key(mc['cell'], mc['block'])
        cells.append(dict(block=mc['block'], cell=mc['cell'], T0=rows.get(key, {}).get('T0'), models={m: cell_errors(rows.get(key, {}).get(m), mc) for m in models}))
    for mb in meas['blocks']:
        ka, kb = C.cell_key('GAh', mb['block']), C.cell_key('GBh', mb['block'])
        blocks.append(dict(block=mb['block'], d_meas=mb['d_max_skin_meas'], models={m: block_pass(rows.get(ka, {}).get(m), rows.get(kb, {}).get(m), mb['d_max_skin_meas'], mb.get('d_first_throttle_meas')) for m in models}))
    per = {m: dict(k=sum(1 for b in blocks if b['models'][m]['passed']), m1=summarize([c['models'][m]['m1'] for c in cells]), m3=summarize([c['models'][m]['m3'] for c in cells]),
                   m2=summarize([c['models'][m]['m2'] for c in cells]), m4=summarize([c['models'][m]['m4'] for c in cells])) for m in models}
    return dict(note='기술만 — 판정 아님 (T0 = 칸의 실제 시작 SKIN · 등록 §1 기술 열)', per_model=per, cells=cells, blocks=blocks)


def write_csvs(res, out_dir, models=C.MODELS):
    os.makedirs(out_dir, exist_ok=True)
    p1 = os.path.join(out_dir, 'gpuho_cells.csv')
    with open(p1, 'w', encoding='utf-8-sig', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(['block', 'cell', 'run_id', 'out_name', 'start_skin', 'column', 'in_range', 'lower', 'model', 'status', 'meas_max_skin', 'pred_max_skin', 'm1_max_skin_err',
                    'meas_skin_899', 'pred_skin_899', 'm2_skin_899_err', 'm3_traj_mae', 'm3_n_bins', 'meas_first_throttle_s', 'pred_first_throttle_s', 'm4_first_throttle_err_s', 'm4_reason',
                    'meas_throttle_time_s', 'pred_throttle_time_s'])
        for c in res['cells']:
            for m in models:
                e = c['models'][m]
                w.writerow([c['block'], c['cell'], c['run_id'], c['out_name'], c['start_skin'], c['column'], c['in_range'], c['lower'], m, e['status'], c['meas_max_skin'], e.get('pred_max_skin'), e['m1'],
                            c['meas_skin_899'], e.get('pred_skin_899'), e['m2'], e['m3'], e['m3_n_bins'], c['meas_first_throttle_s'], e.get('pred_first_throttle_s'), e['m4'], e['m4_reason'],
                            c['meas_throttle_time_s'], e.get('pred_throttle_time_s')])
    p2 = os.path.join(out_dir, 'gpuho_blocks.csv')
    with open(p2, 'w', encoding='utf-8-sig', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(['block', 'meas_status', 'reason', 'start_skin_mean', 'column', 'in_range', 'lower_a', 'lower_b', 'work_ratio', 'd_meas_max_skin', 'model', 'status', 'd_pred_max_skin', 'sign_pred', 'sign_meas',
                    'same_sign', 'abs_diff', 'passed', 'm6_d_first_throttle_pred', 'm6_d_first_throttle_meas', 'm6_diff'])
        for b in res['blocks']:
            for m in models:
                e = b['models'][m]
                w.writerow([b['block'], b['meas_status'], b.get('reason'), b['start_skin_mean'], b['column'], b['in_range'], (b['lower'] or {}).get('a'), (b['lower'] or {}).get('b'), b['work_ratio'], b['d_meas'], m, e['status'],
                            e.get('d_pred'), e.get('sign_pred'), e.get('sign_meas'), e.get('same_sign'), e.get('abs_diff'), e['passed'], e.get('m6_d_pred'), e.get('m6_d_meas'), e.get('m6_diff')])
    return p1, p2


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--selftest', action='store_true')
    ap.add_argument('--pred', default=os.path.join(C.OUT_OD, 'predict_gpuho.json'))
    ap.add_argument('--pred-actual', default=os.path.join(C.OUT_OD, 'predict_gpuho_actual.json'))
    ap.add_argument('--meas', default=os.path.join(C.OUT_OD, 'measure_gpuho.json'))
    ap.add_argument('--out-od', default=C.OUT_OD)
    ap.add_argument('--out-repo', default=C.OUT_REPO)
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    p1 = os.path.join(a.out_od, OUT_NAME)
    if os.path.exists(p1):
        print('REFUSED: judge output already exists (readout once — 등록 §4-5):', p1)
        return 7
    pred, meas = C.load_json(a.pred), C.load_json(a.meas)
    if pred.get('kind') != 'gpuho_predict_v1':
        raise SystemExit(f"pred kind {pred.get('kind')} ≠ gpuho_predict_v1")
    res = judge(pred, meas)
    pa = C.load_json(a.pred_actual) if os.path.exists(a.pred_actual) else None
    res['actual_start_rows'] = actual_rows(pa, meas)
    res['inputs'] = dict(pred=os.path.relpath(a.pred, C.OD) if a.pred.startswith(C.OD) else a.pred, pred_sha256=C.sha256_file(a.pred),
                         pred_actual=None if pa is None else os.path.relpath(a.pred_actual, C.OD), pred_actual_sha256=None if pa is None else C.sha256_file(a.pred_actual),
                         meas=os.path.relpath(a.meas, C.OD) if a.meas.startswith(C.OD) else a.meas, meas_sha256=C.sha256_file(a.meas),
                         this=C.sha256_file(os.path.abspath(__file__)), common_py=C.sha256_file(C.__file__))
    s1 = C.write_json(p1, res)
    s2 = C.write_json(os.path.join(a.out_repo, OUT_NAME), res)
    c1, c2 = write_csvs(res, a.out_od)
    write_csvs(res, a.out_repo)
    mv = res['main_verdict']
    print(f"주 모형 {mv['model']}: k = {mv['k']} / {mv['n_blocks']} → {mv['verdict']}")
    for m, v in res['sensitivity'].items():
        print(f"민감도 {m}: k = {v['k']} / {v['n_blocks']} → {v['verdict']}")
    for b in res['blocks']:
        e = b['models'][C.MAIN]
        print(f"  block {b['block']} col {b['column']}: Δpred {e.get('d_pred')} vs Δmeas {b['d_meas']} · |diff| {e.get('abs_diff')} · same sign {e.get('same_sign')} → {'PASS' if e['passed'] else 'fail'} ({e['status']})")
    for m in C.MODELS:
        v = res['per_model'][m]
        print(f"  {m}: m1 mean {v['m1']['mean']} (|max| {v['m1']['max_abs']}) · m2 mean {v['m2']['mean']} · m3 MAE mean {v['m3']['mean']} · m4 n {v['m4']['n']} null {v['m4_null']} · m6 n {v['m6']['n']}")
    print('->', p1, s1, '| repo', s2, '| csv', c1, c2)
    return 0


# ============================================================ selftest (합성 · 양방향 · 결과 전)
def _fake_meas(d_meas=(0.1, 0.2, -0.1, 0.0, 0.3, 0.1, -0.2, 0.1), missing=()):
    cells, blocks = [], []
    for b in C.BLOCKS:
        if b in missing:
            blocks.append(dict(block=b, status='계산 불가', reason='invalid_twice (B)', start_skin_mean=None, column=None, in_range=None, d_max_skin_meas=None, d_first_throttle_meas=None, work_ratio=None, lower=dict(a='하한 통과', b=None), lower_marked=False))
            continue
        for cell, mx in (('GAh', 38.3), ('GBh', 38.3 - d_meas[b - 1])):
            st = 30.0 if cell == 'GAh' else 30.4
            cells.append(dict(block=b, cell=cell, run_id=f'r{cell}{b}', out_name=f'S26_{cell}_b{b}_1011h', start_skin=st, column=C.pick_column(st), in_range=C.in_range(st), lower='하한 통과', lower_marked=False,
                              max_skin=mx, skin_899=31.0, first_throttle_s=110 if cell == 'GAh' else 500, throttle_time_s=50,
                              hal=dict(bin_mean_skin=[30.0 + 0.05 * k for k in range(90)], n_bins_with_samples=90)))
        blocks.append(dict(block=b, status='계산', start_skin_mean=30.2, column=29.5, in_range=True, d_max_skin_meas=d_meas[b - 1], d_first_throttle_meas=110 - 500, work_ratio=1.0, lower=dict(a='하한 통과', b='하한 통과'), lower_marked=False))
    return dict(cells=cells, blocks=blocks, noise=None)


def _fake_pred_from_meas(meas, models=C.MODELS):
    runs = {}
    for cell in C.CELLS:
        for m in models:
            for T0 in C.COLUMNS:
                mc = next(c for c in meas['cells'] if c['cell'] == cell)
                runs.setdefault(cell, {}).setdefault(m, {})[str(T0)] = dict(max_skin=mc['max_skin'], skin_899=mc['skin_899'], first_throttle_s=mc['first_throttle_s'],
                                                                         throttle_time_s=mc['throttle_time_s'], bin_mean_skin=list(mc['hal']['bin_mean_skin']))
    return dict(kind='gpuho_predict_v1', runs=runs)


def selftest():
    res = []

    def check(name, cond, got=''):
        res.append((name, bool(cond), got))
    meas = _fake_meas(d_meas=(0.1,) * 8)
    pred = _fake_pred_from_meas(meas)
    j = judge(pred, meas)
    check('① 예측 = 실측 (8블록 Δ 같음) → k = 8 · "GPU 재현 확인 (같은 계열 새 세션 · 8블록 중 8)" · m1 = m3 = 0 · m4 0 · m6 0',
          j['main_verdict']['k'] == 8 and j['main_verdict']['verdict'] == 'GPU 재현 확인 (같은 계열 새 세션 · 8블록 중 8)' and j['per_model']['v22']['m1']['max_abs'] == 0
          and j['per_model']['v22']['m3']['max_abs'] == 0 and all(c['models']['v22']['m4'] == 0 for c in j['cells']) and j['per_model']['v22']['m6']['max_abs'] == 0, j['main_verdict'])
    pred2 = copy.deepcopy(pred)
    for T0 in C.COLUMNS:
        pred2['runs']['GAh']['v22'][str(T0)]['max_skin'], pred2['runs']['GBh']['v22'][str(T0)]['max_skin'] = pred2['runs']['GBh']['v22'][str(T0)]['max_skin'], pred2['runs']['GAh']['v22'][str(T0)]['max_skin']
    j2 = judge(pred2, meas)
    check('② Δ 부호 뒤집음 → 8블록 실패 · k = 0 · "GPU 재현 미확인 (0/8)"', j2['main_verdict']['k'] == 0 and j2['main_verdict']['verdict'] == 'GPU 재현 미확인 (0/8)' and all(b['models']['v22']['same_sign'] is False for b in j2['blocks']), j2['main_verdict'])
    meas3 = _fake_meas(d_meas=(0.1 + 1.0, 0.1 + 1.000001, 0.1 - 1.0, 0.1, 0.1, 0.1, 0.1, 0.1))
    j3 = judge(pred, meas3)
    b3 = [b['models']['v22'] for b in j3['blocks']]
    check('③ |차| 경계: 1.0 → 통과 · 1.000001 → 실패 · −0.9 (부호 다름) → 실패 · k = 6 → "GPU 부분 재현 (6/8)"',
          b3[0]['passed'] and abs(b3[0]['abs_diff'] - 1.0) < 1e-9 and not b3[1]['passed'] and b3[1]['same_sign'] and not b3[2]['passed'] and b3[2]['same_sign'] is False
          and j3['main_verdict']['k'] == 6 and j3['main_verdict']['verdict'] == 'GPU 부분 재현 (6/8)', [(x['abs_diff'], x['passed']) for x in b3[:3]])
    meas3b = _fake_meas(d_meas=(0.0, -0.3, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1))
    pred3b = copy.deepcopy(pred)
    for T0 in C.COLUMNS:
        pred3b['runs']['GBh']['v22'][str(T0)]['max_skin'] = 38.3 - 0.3
    j3b = judge(pred3b, meas3b)
    bb = [b['models']['v22'] for b in j3b['blocks']]
    check('③ 부호: 실측 0 vs 예측 + → 실패 · 실측 −0.3 vs 예측 +0.3 (|차| 0.6) → 실패 · 실측 +0.1 vs +0.3 → 통과',
          not bb[0]['passed'] and bb[0]['sign_meas'] == '0' and not bb[1]['passed'] and bb[1]['abs_diff'] == 0.6 and bb[2]['passed'], [(x['sign_meas'], x['abs_diff'], x['passed']) for x in bb[:3]])
    # ④ invalid_twice block (no measured pair) → 계산 불가 · not a pass · denominator 8 · k counts the other 7
    meas4 = _fake_meas(d_meas=(0.1,) * 8, missing=(5,))
    pred4 = _fake_pred_from_meas(meas4)
    j4 = judge(pred4, meas4)
    check('④ invalid_twice 블록 (실측 쌍 없음) → "계산 불가" · 통과 아님 · 분모 8 · k = 7 · n_not_computable 1 · 칸 수 14',
          j4['blocks'][4]['models']['v22']['status'] == '계산 불가' and not j4['blocks'][4]['models']['v22']['passed'] and j4['main_verdict']['n_blocks'] == 8 and j4['main_verdict']['k'] == 7
          and j4['per_model']['v22']['n_not_computable'] == 1 and len(j4['cells']) == 14 and j4['not_computable_blocks'] == [5], j4['main_verdict'])
    meas4b = _fake_meas(d_meas=(0.1,) * 8)
    meas4b['blocks'][4]['column'] = 30.5
    pred4b = copy.deepcopy(pred)
    del pred4b['runs']['GBh']['v22']['30.5']
    j4b = judge(pred4b, meas4b)
    check('④ 예측 열 없음 (블록 5 B 30.5) → "계산 불가" · 분모 8 · k = 7', j4b['blocks'][4]['models']['v22']['status'] == '계산 불가' and j4b['main_verdict']['k'] == 7 and j4b['main_verdict']['n_blocks'] == 8)
    pred5 = copy.deepcopy(pred)
    for T0 in C.COLUMNS:
        pred5['runs']['GAh']['v21'][str(T0)]['max_skin'] = 30.0
    j5 = judge(pred5, meas)
    pred5b = copy.deepcopy(pred)
    for T0 in C.COLUMNS:
        pred5b['runs']['GAh']['v22'][str(T0)]['max_skin'] = 30.0
    j5b = judge(pred5b, meas)
    check('⑤ 민감도 분리: v21 전부 틀려도 주 v22 8 · v21 0; v22 전부 틀리면 주 0 인데 v21 8', j5['main_verdict']['k'] == 8 and j5['sensitivity']['v21']['k'] == 0 and 'v22' not in j5['sensitivity']
          and j5b['main_verdict']['k'] == 0 and j5b['per_model']['v21']['k'] == 8)
    check('⑥ 판정 3갈래 이름: 8·7 GPU 재현 확인 · 6·5 GPU 부분 재현 · 4·0 GPU 재현 미확인', C.verdict_label(8).startswith('GPU 재현 확인') and C.verdict_label(7) == 'GPU 재현 확인 (같은 계열 새 세션 · 8블록 중 7)'
          and C.verdict_label(6) == 'GPU 부분 재현 (6/8)' and C.verdict_label(5) == 'GPU 부분 재현 (5/8)' and C.verdict_label(4) == 'GPU 재현 미확인 (4/8)' and C.verdict_label(0) == 'GPU 재현 미확인 (0/8)')
    meas7 = _fake_meas(d_meas=(0.1,) * 8)
    meas7['cells'][0]['hal']['bin_mean_skin'][10:20] = [None] * 10
    meas7['cells'][0]['lower'] = '하한 미달'; meas7['cells'][0]['lower_marked'] = True; meas7['blocks'][0]['lower_marked'] = True
    pred7 = copy.deepcopy(pred)
    for T0 in C.COLUMNS:
        pred7['runs']['GAh']['v22'][str(T0)]['bin_mean_skin'] = [x + 0.5 for x in pred7['runs']['GAh']['v22'][str(T0)]['bin_mean_skin']]
        pred7['runs']['GAh']['v22'][str(T0)]['first_throttle_s'] = None
        pred7['runs']['GAh']['v22'][str(T0)]['skin_899'] = 31.4
    j7 = judge(pred7, meas7)
    c0 = j7['cells'][0]['models']['v22']
    check('⑦ m3 = 0.5 (80칸 · None 10 건너뜀) · m4 null "예측 없음 (실측 110 s)" · m2 +0.4 · 하한 미달 표시 칸 1 (판정은 그대로 · k 8) · m6 null (예측 조임 없음)',
          abs(c0['m3'] - 0.5) < 1e-9 and c0['m3_n_bins'] == 80 and c0['m4'] is None and c0['m4_reason'] == '예측 없음 (실측 110 s)' and abs(c0['m2'] - 0.4) < 1e-9
          and j7['n_lower_marked_cells'] == 1 and j7['main_verdict']['k'] == 8 and j7['blocks'][0]['models']['v22']['m6_d_pred'] is None, (c0['m3'], c0['m4_reason'], j7['n_lower_marked_cells']))
    check('⑧ m6: 예측 Δ첫 조임 (A − B) = 110 − 500 = −390 · 실측 −390 → m6_diff 0', j['blocks'][0]['models']['v22']['m6_d_pred'] == -390 and j['blocks'][0]['models']['v22']['m6_diff'] == 0)
    check('⑨ 결정성: 같은 입력 두 번 → 같은 JSON 바이트', C.dumps(judge(pred, meas)) == C.dumps(judge(pred, meas)))
    for kk in (5, 6):
        d = tuple([0.1] * kk + [-0.3] * (8 - kk))
        jk = judge(pred, _fake_meas(d_meas=d))
        check(f'⑩ k = {kk} → "GPU 부분 재현 ({kk}/8)"', jk['main_verdict']['k'] == kk and jk['main_verdict']['verdict'] == f'GPU 부분 재현 ({kk}/8)', jk['main_verdict']['verdict'])
    try:
        judge(pred, dict(cells=meas['cells'], blocks=meas['blocks'][:7]))
        check('⑪ 블록 7개만 주면 오류 (분모 8 강제)', False, '판정이 나왔다')
    except SystemExit as e:
        check('⑪ 블록 7개만 주면 오류 (분모 8 강제)', True, str(e)[:80])
    check('⑫ readout 한 번: 출력 파일이 이미 있으면 거부 (지금 없음 = 아직 판정 전)', not os.path.exists(os.path.join(C.OUT_OD, OUT_NAME)), os.path.join(C.OUT_OD, OUT_NAME))
    return C.print_table(res)


if __name__ == '__main__':
    sys.exit(main())
