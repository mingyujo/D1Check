"""judge_modelerr.py — m1~m5 · block pass · k · 3-way verdict (prereg d1sim/docs/모형오차_사전등록_v1.md §3 · §4, 9e29851). Written before any run.

Inputs: predict_energyc.json (predict_energyc.py) · measure_energyc.json (measure_energyc.py).
Per cell · per model (column = measured load-start SKIN → nearest of 29.5 / 30.5, tie 29.5, no interpolation — V3 v2 rule):
  m1 = predicted max SKIN − measured max SKIN (℃)        m2 = predicted SKIN at 899 s − measured 899 s SKIN (℃)
  m3 = mean |predicted − measured| over the 10 s bin means k = 0..89 (bins without HAL samples skipped, count written)
  m4 = predicted first-throttle time − measured (s); null + reason when either side has none (k + 3 bins ≥ ×1.06 rule both sides)
Per block · per model (column = nearest to the mean of the two cells' start SKIN):
  m5: predicted Δ = pred(NAc) max SKIN − pred(NBc) max SKIN (same column) vs measured Δ (tpair deltas.d_max_skin) → same sign (6-dp, 0 counts as
  its own sign) AND |pred Δ − meas Δ| ≤ 1.0 ℃ (6-dp) → block pass. A block whose prediction is missing = "계산 불가" (not a pass, stays in /8).
k = passes / 8 → k ≥ 7 "재현 확인 (에너지 C · 같은 계열 · 8블록 중 k)" · 5 ≤ k ≤ 6 "부분 재현 (k/8)" · k ≤ 4 "재현 미확인 (k/8)".
Main verdict = v22 only (표 ① row 9). Sensitivity models (v21 · v2 θ0.3 · θ0.75) are listed beside it and never enter the main verdict.
m1~m4 = description only (mean · mean |·| · max |·| · n). Described-only extra: the same arithmetic on the 'actual-start' rows (판정 아님).

  py -X utf8 -m d1sim.model_error_v1.judge_modelerr [--selftest] [--pred f] [--meas f] [--out-od DIR] [--out-repo DIR]
"""
from __future__ import annotations

import argparse
import copy
import csv
import os
import statistics
import sys

from d1sim.model_error_v1 import common as C

C.stdout_utf8()


def verdict_label(k, n=8):
    if k >= 7:
        return f'재현 확인 (에너지 C · 같은 계열 · {n}블록 중 {k})'
    if 5 <= k <= 6:
        return f'부분 재현 ({k}/{n})'
    return f'재현 미확인 ({k}/{n})'


def _pred_for(pred_runs, cell, model, column):
    try:
        return pred_runs[cell][model][str(column)]
    except (KeyError, TypeError):
        return None


def cell_errors(p, mc):
    """m1~m4 for one cell (p = predicted metrics dict or None, mc = measured cell dict)."""
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


def block_pass(pred_a, pred_b, d_meas):
    """m5 for one block: (pred Δ, same sign, |diff|, pass, status)."""
    if pred_a is None or pred_b is None:
        return dict(status='계산 불가', d_pred=None, same_sign=None, abs_diff=None, passed=False)
    d_pred = C.r6(pred_a['max_skin'] - pred_b['max_skin'])
    same = C.sign(d_pred) == C.sign(d_meas)
    ad = round(abs(d_pred - d_meas), 6)
    return dict(status='계산', d_pred=d_pred, d_meas=C.r6(d_meas), sign_pred=C.sign(d_pred), sign_meas=C.sign(d_meas), same_sign=same, abs_diff=ad,
                within=(ad <= C.PASS_ABS + 0.0), passed=bool(same and ad <= C.PASS_ABS))


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
        row = dict(block=mc['block'], cell=mc['cell'], run_id=mc['run_id'], start_skin=mc['start_skin'], column=mc['column'], in_range=mc['in_range'],
                   lower=mc['lower'], meas_max_skin=mc['max_skin'], meas_skin_899=mc['skin_899'], meas_first_throttle_s=mc['first_throttle_s'],
                   meas_throttle_time_s=mc['throttle_time_s'], hal_bins=mc['hal']['n_bins_with_samples'], models={})
        for m in models:
            row['models'][m] = cell_errors(_pred_for(runs, mc['cell'], m, mc['column']), mc)
        cells_out.append(row)
    for mb in meas['blocks']:
        row = dict(block=mb['block'], start_skin_mean=mb['start_skin_mean'], column=mb['column'], in_range=mb['in_range'], d_meas=mb['d_max_skin_meas'],
                   work_ratio=mb['work_ratio'], lower=mb['lower'], models={})
        for m in models:
            row['models'][m] = block_pass(_pred_for(runs, 'NAc', m, mb['column']), _pred_for(runs, 'NBc', m, mb['column']), mb['d_max_skin_meas'])
        blocks_out.append(row)
    n_blocks = len(blocks_out)
    for m in models:
        k = sum(1 for b in blocks_out if b['models'][m]['passed'])
        n_na = sum(1 for b in blocks_out if b['models'][m]['status'] == '계산 불가')
        per_model[m] = dict(label=C.MODEL_LABEL.get(m, m), k=k, n_blocks=n_blocks, n_not_computable=n_na, verdict=verdict_label(k, n_blocks),
                            blocks_passed=[b['block'] for b in blocks_out if b['models'][m]['passed']],
                            blocks_failed=[b['block'] for b in blocks_out if not b['models'][m]['passed']],
                            m1=summarize([c['models'][m]['m1'] for c in cells_out]), m2=summarize([c['models'][m]['m2'] for c in cells_out]),
                            m3=summarize([c['models'][m]['m3'] for c in cells_out]), m4=summarize([c['models'][m]['m4'] for c in cells_out]),
                            m4_null=sum(1 for c in cells_out if c['models'][m]['m4'] is None),
                            m1_A=summarize([c['models'][m]['m1'] for c in cells_out if c['cell'] == 'NAc']), m1_B=summarize([c['models'][m]['m1'] for c in cells_out if c['cell'] == 'NBc']),
                            d_pred_blocks=[b['models'][m]['d_pred'] for b in blocks_out], abs_diff_blocks=[b['models'][m]['abs_diff'] for b in blocks_out])
    main_v = per_model[main]
    sens = {m: per_model[m] for m in models if m != main}
    return dict(kind='modelerr_judge_energyc_v1', registration=f'{C.REG} ({C.REG_COMMIT[:7]}) §3 · §4', main_model=main, models=list(models),
                rule=dict(block_pass='m5 부호 같음 (6자리) 그리고 |예측 Δ − 실측 Δ| ≤ 1.0 ℃ (6자리) · 계산 불가 = 통과 아님 · 분모에 남음',
                          verdict='k ≥ 7 재현 확인 · 5 ≤ k ≤ 6 부분 재현 · k ≤ 4 재현 미확인 · 주 모형 판정만 표 ① 행 9 · 민감도는 나란히 기술',
                          column='칸 = 시작 SKIN 에 가까운 열 · 블록 = A·B 시작 SKIN 평균에 가까운 열 (같으면 29.5 · 보간 없음) · 범위 [28.3, 31.6] 밖은 표시만'),
                main_verdict=dict(model=main, k=main_v['k'], n_blocks=n_blocks, verdict=main_v['verdict']), per_model=per_model, sensitivity=sens,
                cells=cells_out, blocks=blocks_out, noise=meas.get('noise'))


def actual_rows(pred, meas, models=C.MODELS):
    """Described-only: same m1~m5 arithmetic with the actual-start predictions (판정 아님)."""
    rows = (pred.get('actual_start_rows') or {}).get('rows') or {}
    if not rows:
        return None
    cells, blocks = [], []
    for mc in meas['cells']:
        key = C.cell_key(mc['cell'], mc['block'])
        cells.append(dict(block=mc['block'], cell=mc['cell'], T0=rows.get(key, {}).get('T0'), models={m: cell_errors(rows.get(key, {}).get(m), mc) for m in models}))
    for mb in meas['blocks']:
        ka, kb = C.cell_key('NAc', mb['block']), C.cell_key('NBc', mb['block'])
        blocks.append(dict(block=mb['block'], d_meas=mb['d_max_skin_meas'], models={m: block_pass(rows.get(ka, {}).get(m), rows.get(kb, {}).get(m), mb['d_max_skin_meas']) for m in models}))
    per = {m: dict(k=sum(1 for b in blocks if b['models'][m]['passed']), m1=summarize([c['models'][m]['m1'] for c in cells]), m3=summarize([c['models'][m]['m3'] for c in cells]),
                   m2=summarize([c['models'][m]['m2'] for c in cells]), m4=summarize([c['models'][m]['m4'] for c in cells])) for m in models}
    return dict(note='기술만 — 판정 아님 (T0 = 칸의 실제 시작 SKIN · 결과 전 선언 freeze_modelerr.txt (b))', per_model=per, cells=cells, blocks=blocks)


def write_csvs(res, out_dir, models=C.MODELS):
    os.makedirs(out_dir, exist_ok=True)
    p1 = os.path.join(out_dir, 'modelerr_cells.csv')
    with open(p1, 'w', encoding='utf-8-sig', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(['block', 'cell', 'run_id', 'start_skin', 'column', 'in_range', 'lower', 'model', 'status', 'meas_max_skin', 'pred_max_skin', 'm1_max_skin_err',
                    'meas_skin_899', 'pred_skin_899', 'm2_skin_899_err', 'm3_traj_mae', 'm3_n_bins', 'meas_first_throttle_s', 'pred_first_throttle_s', 'm4_first_throttle_err_s', 'm4_reason',
                    'meas_throttle_time_s', 'pred_throttle_time_s'])
        for c in res['cells']:
            for m in models:
                e = c['models'][m]
                w.writerow([c['block'], c['cell'], c['run_id'], c['start_skin'], c['column'], c['in_range'], c['lower'], m, e['status'], c['meas_max_skin'], e.get('pred_max_skin'), e['m1'],
                            c['meas_skin_899'], e.get('pred_skin_899'), e['m2'], e['m3'], e['m3_n_bins'], c['meas_first_throttle_s'], e.get('pred_first_throttle_s'), e['m4'], e['m4_reason'],
                            c['meas_throttle_time_s'], e.get('pred_throttle_time_s')])
    p2 = os.path.join(out_dir, 'modelerr_blocks.csv')
    with open(p2, 'w', encoding='utf-8-sig', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(['block', 'start_skin_mean', 'column', 'in_range', 'work_ratio', 'd_meas_max_skin', 'model', 'status', 'd_pred_max_skin', 'sign_pred', 'sign_meas', 'same_sign', 'abs_diff', 'passed'])
        for b in res['blocks']:
            for m in models:
                e = b['models'][m]
                w.writerow([b['block'], b['start_skin_mean'], b['column'], b['in_range'], b['work_ratio'], b['d_meas'], m, e['status'], e.get('d_pred'), e.get('sign_pred'), e.get('sign_meas'), e.get('same_sign'), e.get('abs_diff'), e['passed']])
    return p1, p2


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--selftest', action='store_true')
    ap.add_argument('--pred', default=os.path.join(C.OUT_OD, 'predict_energyc.json'))
    ap.add_argument('--meas', default=os.path.join(C.OUT_OD, 'measure_energyc.json'))
    ap.add_argument('--out-od', default=C.OUT_OD)
    ap.add_argument('--out-repo', default=C.OUT_REPO)
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    pred, meas = C.load_json(a.pred), C.load_json(a.meas)
    res = judge(pred, meas)
    res['actual_start_rows'] = actual_rows(pred, meas)
    res['inputs'] = dict(pred=os.path.relpath(a.pred, C.OD) if a.pred.startswith(C.OD) else a.pred, pred_sha256=C.sha256_file(a.pred),
                         meas=os.path.relpath(a.meas, C.OD) if a.meas.startswith(C.OD) else a.meas, meas_sha256=C.sha256_file(a.meas),
                         this=C.sha256_file(os.path.abspath(__file__)), common_py=C.sha256_file(C.__file__))
    p1 = os.path.join(a.out_od, 'modelerr_energyc.json')
    s1 = C.write_json(p1, res)
    s2 = C.write_json(os.path.join(a.out_repo, 'modelerr_energyc.json'), res)
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
        print(f"  {m}: m1 mean {v['m1']['mean']} (|max| {v['m1']['max_abs']}) · m2 mean {v['m2']['mean']} · m3 MAE mean {v['m3']['mean']} · m4 n {v['m4']['n']} null {v['m4_null']}")
    print('->', p1, s1, '| repo', s2, '| csv', c1, c2)
    return 0


# ============================================================ selftest (합성 · 양방향 · 결과 전)
def _fake_meas(d_meas=(1.7, 2.2, 1.9, 2.2, 2.9, 1.7, 1.8, -1.1)):
    cells, blocks = [], []
    for b in C.BLOCKS:
        for cell, mx in (('NAc', 38.0), ('NBc', 38.0 - d_meas[b - 1])):
            st = 30.0 if cell == 'NAc' else 30.4
            cells.append(dict(block=b, cell=cell, run_id=f'r{cell}{b}', start_skin=st, column=C.pick_column(st), in_range=C.in_range(st), lower='하한 통과',
                              max_skin=mx, skin_899=31.0, first_throttle_s=100 if cell == 'NAc' else None, throttle_time_s=50,
                              hal=dict(bin_mean_skin=[30.0 + 0.05 * k for k in range(90)], n_bins_with_samples=90)))
        blocks.append(dict(block=b, start_skin_mean=30.2, column=29.5, in_range=True, d_max_skin_meas=d_meas[b - 1], work_ratio=1.0, lower=dict(a='x', b='x')))
    return dict(cells=cells, blocks=blocks, noise=None)


def _fake_pred_from_meas(meas, models=C.MODELS):
    """prediction equal to the measurement for every model (one column set, both columns identical)."""
    runs = {}
    for cell in C.CELLS:
        for m in models:
            for T0 in C.COLUMNS:
                mc = next(c for c in meas['cells'] if c['cell'] == cell and c['block'] == 1)
                runs.setdefault(cell, {}).setdefault(m, {})[str(T0)] = dict(max_skin=mc['max_skin'], skin_899=mc['skin_899'], first_throttle_s=mc['first_throttle_s'],
                                                                         throttle_time_s=mc['throttle_time_s'], bin_mean_skin=list(mc['hal']['bin_mean_skin']))
    return dict(runs=runs)


def selftest():
    res = []

    def check(name, cond, got=''):
        res.append((name, bool(cond), got))
    # 1. prediction = measurement in every block → k = 8 → 재현 확인 (uniform Δ = block-1 Δ for the model → make meas Δ uniform)
    meas = _fake_meas(d_meas=(1.7,) * 8)
    pred = _fake_pred_from_meas(meas)
    j = judge(pred, meas)
    check('① 예측 = 실측 (8블록 Δ 전부 같음) → k = 8 · "재현 확인 (… 8블록 중 8)" · m1 = m2 = m3 = 0 · m4 A 0 / B null (둘 다 없음)',
          j['main_verdict']['k'] == 8 and j['main_verdict']['verdict'] == '재현 확인 (에너지 C · 같은 계열 · 8블록 중 8)'
          and j['per_model']['v22']['m1']['max_abs'] == 0 and j['per_model']['v22']['m3']['max_abs'] == 0
          and all(c['models']['v22']['m4'] == 0 for c in j['cells'] if c['cell'] == 'NAc')
          and all(c['models']['v22']['m4'] is None and c['models']['v22']['m4_reason'].startswith('둘 다 없음') for c in j['cells'] if c['cell'] == 'NBc'), j['main_verdict'])
    # 2. flip the sign of the predicted Δ (swap A/B max) → every block fails → k = 0 → 재현 미확인
    pred2 = copy.deepcopy(pred)
    for T0 in C.COLUMNS:
        pred2['runs']['NAc']['v22'][str(T0)]['max_skin'], pred2['runs']['NBc']['v22'][str(T0)]['max_skin'] = \
            pred2['runs']['NBc']['v22'][str(T0)]['max_skin'], pred2['runs']['NAc']['v22'][str(T0)]['max_skin']
    j2 = judge(pred2, meas)
    check('② Δ 부호 뒤집음 (A·B 예측 맞바꿈) → 8블록 전부 실패 · k = 0 · "재현 미확인 (0/8)" · |차| 3.4 = 2·1.7',
          j2['main_verdict']['k'] == 0 and j2['main_verdict']['verdict'] == '재현 미확인 (0/8)' and all(b['models']['v22']['same_sign'] is False for b in j2['blocks'])
          and abs(j2['blocks'][0]['models']['v22']['abs_diff'] - 3.4) < 1e-9, j2['main_verdict'])
    # 3. |diff| boundary: measured Δ varies per block; prediction fixed → set meas so |diff| = 1.0 exactly in block 1 (pass), 1.000001 in block 2 (fail), −1.0 in block 3 (pass)
    meas3 = _fake_meas(d_meas=(1.7 + 1.0, 1.7 + 1.000001, 1.7 - 1.0, 1.7, 1.7, 1.7, 1.7, 1.7))
    j3 = judge(pred, meas3)
    b3 = [b['models']['v22'] for b in j3['blocks']]
    check('③ |예측 Δ − 실측 Δ| 경계: 1.0 → 통과 · 1.000001 → 실패 · −1.0 (|·| 1.0) → 통과 · k = 7 → 재현 확인',
          b3[0]['passed'] and abs(b3[0]['abs_diff'] - 1.0) < 1e-9 and not b3[1]['passed'] and b3[1]['same_sign'] and b3[2]['passed'] and j3['main_verdict']['k'] == 7
          and j3['main_verdict']['verdict'].startswith('재현 확인'), [(x['abs_diff'], x['passed']) for x in b3[:3]])
    # 3b. sign rule: measured Δ = 0 with predicted +1.7 → not same sign (fails even though |diff| ≤ 1.0 would be false anyway) ; measured −0.3 vs pred +0.3 → |diff| 0.6 ≤ 1 but sign differs → fail
    meas3b = _fake_meas(d_meas=(0.0, -0.3, 1.7, 1.7, 1.7, 1.7, 1.7, 1.7))
    pred3b = copy.deepcopy(pred)
    for T0 in C.COLUMNS:
        pred3b['runs']['NBc']['v22'][str(T0)]['max_skin'] = 38.0 - 0.3      # pred Δ = +0.3 in every block (NAc 38.0)
    j3b = judge(pred3b, meas3b)
    bb = [b['models']['v22'] for b in j3b['blocks']]
    check('③ 부호: 실측 0 vs 예측 + → 실패 · 실측 −0.3 vs 예측 +0.3 (|차| 0.6 ≤ 1.0) → 부호 달라 실패 · 실측 +1.7 vs 예측 +0.3 (|차| 1.4) → 실패',
          not bb[0]['passed'] and bb[0]['sign_meas'] == '0' and not bb[1]['passed'] and bb[1]['abs_diff'] == 0.6 and bb[1]['same_sign'] is False and not bb[2]['passed'] and bb[2]['same_sign'] is True, [(x['sign_meas'], x['abs_diff'], x['passed']) for x in bb[:3]])
    # 4. 계산 불가: remove the v22 prediction for the column used by block 5 (both columns removed for NBc → all blocks 계산 불가) — use one-column removal with per-block columns
    meas4 = _fake_meas(d_meas=(1.7,) * 8)
    meas4['blocks'][4]['column'] = 30.5                                       # block 5 compares in column 30.5
    pred4 = copy.deepcopy(pred)
    del pred4['runs']['NBc']['v22']['30.5']
    j4 = judge(pred4, meas4)
    check('④ 계산 불가 칸 (블록 5 의 B 예측 열 없음) → 그 블록 "계산 불가" · 통과 아님 · 분모 8 그대로 · k = 7 · n_not_computable 1',
          j4['blocks'][4]['models']['v22']['status'] == '계산 불가' and not j4['blocks'][4]['models']['v22']['passed'] and j4['main_verdict']['n_blocks'] == 8
          and j4['main_verdict']['k'] == 7 and j4['per_model']['v22']['n_not_computable'] == 1, (j4['main_verdict'], j4['per_model']['v22']['n_not_computable']))
    # 5. sensitivity never enters the main verdict: break v21 completely (k = 0) with v22 perfect → main 재현 확인 · sens v21 재현 미확인; and vice versa
    pred5 = copy.deepcopy(pred)
    for T0 in C.COLUMNS:
        pred5['runs']['NAc']['v21'][str(T0)]['max_skin'] = 30.0               # Δ pred = 30 − 38 = −8 → wrong sign everywhere
    j5 = judge(pred5, meas)
    pred5b = copy.deepcopy(pred)
    for T0 in C.COLUMNS:
        pred5b['runs']['NAc']['v22'][str(T0)]['max_skin'] = 30.0
    j5b = judge(pred5b, meas)
    check('⑤ 민감도 모형이 주 판정에 안 섞임: v21 전부 틀려도 주 (v22) "재현 확인 … 8" · v21 "재현 미확인 (0/8)"; v22 전부 틀리면 주 "재현 미확인 (0/8)" 인데 v21 은 8',
          j5['main_verdict']['k'] == 8 and j5['sensitivity']['v21']['k'] == 0 and j5['sensitivity']['v21']['verdict'] == '재현 미확인 (0/8)' and 'v22' not in j5['sensitivity']
          and j5b['main_verdict']['k'] == 0 and j5b['main_verdict']['verdict'] == '재현 미확인 (0/8)' and j5b['per_model']['v21']['k'] == 8, (j5['main_verdict']['k'], j5['sensitivity']['v21']['k']))
    # 6. verdict labels at every k
    check('⑥ 판정 3갈래: k 8·7 → 재현 확인 · 6·5 → 부분 재현 · 4·0 → 재현 미확인',
          verdict_label(8).startswith('재현 확인') and verdict_label(7).startswith('재현 확인') and verdict_label(6) == '부분 재현 (6/8)' and verdict_label(5) == '부분 재현 (5/8)'
          and verdict_label(4) == '재현 미확인 (4/8)' and verdict_label(0) == '재현 미확인 (0/8)')
    # 7. m3 skips bins without HAL samples · m4 reasons · m2
    meas7 = _fake_meas(d_meas=(1.7,) * 8)
    meas7['cells'][0]['hal']['bin_mean_skin'][10:20] = [None] * 10
    pred7 = copy.deepcopy(pred)
    for T0 in C.COLUMNS:
        pred7['runs']['NAc']['v22'][str(T0)]['bin_mean_skin'] = [x + 0.5 for x in pred7['runs']['NAc']['v22'][str(T0)]['bin_mean_skin']]
        pred7['runs']['NAc']['v22'][str(T0)]['first_throttle_s'] = None
        pred7['runs']['NAc']['v22'][str(T0)]['skin_899'] = 31.4
    j7 = judge(pred7, meas7)
    c0 = j7['cells'][0]['models']['v22']
    check('⑦ m3 = 0.5 over 80 bins (10 None skipped) · m4 null "예측 없음 (실측 100 s)" · m2 = +0.4', abs(c0['m3'] - 0.5) < 1e-9 and c0['m3_n_bins'] == 80
          and c0['m4'] is None and c0['m4_reason'] == '예측 없음 (실측 100 s)' and abs(c0['m2'] - 0.4) < 1e-9, (c0['m3'], c0['m3_n_bins'], c0['m4_reason'], c0['m2']))
    # 8. determinism of the JSON output
    check('⑧ 결정성: 같은 입력 두 번 → 같은 JSON 바이트', C.dumps(judge(pred, meas)) == C.dumps(judge(pred, meas)))
    # 9. partial verdict k = 5 and 6
    for kk in (5, 6):
        d = tuple([1.7] * kk + [-1.7] * (8 - kk))
        jk = judge(pred, _fake_meas(d_meas=d))
        check(f'⑨ k = {kk} → "부분 재현 ({kk}/8)"', jk['main_verdict']['k'] == kk and jk['main_verdict']['verdict'] == f'부분 재현 ({kk}/8)', jk['main_verdict']['verdict'])
    ok = all(c for _, c, _ in res)
    print('| 시험 | 결과 | 값 |\n|---|---|---|')
    for name, c, got in res:
        print(f"| {name} | {'PASS' if c else 'FAIL'} | {str(got)[:170]} |")
    print(f"\nselftest 전체: {'PASS' if ok else 'FAIL'} ({sum(1 for _, c, _ in res if c)}/{len(res)})")
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
