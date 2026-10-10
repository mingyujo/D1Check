"""judge_gpuerr.py — m1 ~ m6 · summaries · holdout pair k / n (prereg §3 · §4, commit 35c9342). Written before any error computation.

Inputs: predictions_gpu.json (predict_gpuerr.py, commit ②) · measure_gpu.json (measure_gpu.py, after commit ②).
Per run × 판 (column = the 판's own column rule: frozen actual-start column where the frozen file has it, else the two-point column
nearest the measured start SKIN — tie 29.5, no interpolation; v0 = its own actual-start replay):
  m1 = predicted max SKIN − measured max SKIN (℃)                 [predicted = frozen item where present, else the frozen-code series]
  m2 = predicted − measured SKIN at the window end = the run's last common second (N1 · N2 900 s window: 899 s, frozen skin_899)
  m3 = mean |predicted − measured| over 10 s bin means k = [10k, 10k+10) chain-absolute (common bins with both sides, count written)
  m4 = predicted first-throttle time − measured (chain-absolute s; "칸 k + 뒤 3칸" rule, GPU ×1.10 · NPU ×1.06); null + reason when either side has none
Per pair × 판 (N1 · N2): m5 = predicted Δ max SKIN (A − B, frozen pair item) vs measured Δ → same sign (6 dp) AND |diff| ≤ 1.0 ℃ → pass (k / n described,
  no verdict name) · Δ first throttle (description). Per resource × 판: m6 = predicted verdict (night1005_judge.resource_verdict) == measured verdict.
Verdict names (prereg §4, only two): v2.2 rows → "GPU 적합도 오차 (개발 자료)" (no pass / fail); each 판's holdout rows → "GPU 홀드아웃 오차 (판 ○ · 동결 예측)"
  + pair k / n. "계산 불가" rows stay in the denominator. Nothing here changes a frozen file; results are description, not a verdict.

  py -X utf8 -m d1sim.model_error_gpu_v1.judge_gpuerr [--selftest] [--pred f] [--meas f] [--out-od DIR] [--out-repo DIR]
"""
from __future__ import annotations

import argparse
import copy
import csv
import math
import os
import statistics
import sys

from d1sim.model_error_gpu_v1 import common as C

C.stdout_utf8()
WINDOW_900_GROUPS = ('N1', 'N1s', 'N2')


def choose_column(cols, start_skin):
    keys = list(cols)
    act = [k for k in keys if k.startswith('actual:')]
    if act:
        return act[0]
    c = C.pick_column(start_skin, [float(k.split('/')[0]) for k in keys])
    return next(k for k in keys if float(k.split('/')[0]) == c)


def skin_at(skin_by_t, T):
    t, v = min(skin_by_t, key=lambda s: abs(s[0] - T))
    return v, round(t - T, 3)


def run_errors(P, M, group):
    """m1 ~ m4 for one run × 판 (P = prediction column record · M = measured run record)."""
    repro_ok = bool((P.get('repro') or {}).get('all', True))
    items = P.get('items') or {}
    src = {}
    # m1
    if 'max_skin' in items:
        pm, src['m1'] = items['max_skin'], 'frozen'
    else:
        pm, src['m1'] = P['gen']['max_skin'], 'generated'
    m1 = None if (src['m1'] == 'generated' and not repro_ok) else C.r6(pm - M['max_skin'])
    # m2
    n_rows = P['n_rows']
    if group in WINDOW_900_GROUPS and 'skin_899' in items:
        T_end, pe, src['m2'] = 899, items['skin_899'], 'frozen'
        me, dt = skin_at(M['skin_by_t'], 899) if M.get('skin_899_judge') is None else (M['skin_899_judge'], 0.0)
    else:
        T_end = int(min(n_rows - 1, math.floor(M['t_max'])))
        pe, src['m2'] = P['gen']['skin_1s'][T_end], 'generated'
        me, dt = skin_at(M['skin_by_t'], T_end)
    m2 = None if (src['m2'] == 'generated' and not repro_ok) else C.r6(pe - me)
    # m3
    n = min(P['gen']['n_bins'], M['n_bins'])
    pairs = [(a, b) for a, b in zip(P['gen']['bin_mean_skin'][:n], M['bin_mean_skin'][:n]) if a is not None and b is not None]
    m3 = None if (not repro_ok or not pairs) else C.r6(sum(abs(a - b) for a, b in pairs) / len(pairs))
    # m4
    pf, mf = P.get('first_throttle_abs_s'), M['first_throttle']['abs_s']
    if pf is None and mf is None:
        m4, why = None, '둘 다 없음 (예측 · 실측 모두 조임 없음)'
    elif pf is None:
        m4, why = None, f'예측 없음 (실측 {mf} s)'
    elif mf is None:
        m4, why = None, f'실측 없음 (예측 {pf} s)'
    else:
        m4, why = round(pf - mf, 3), None
    status = '계산' if repro_ok else '계산 불가 (동결 코드 재생이 동결 파일 스칼라를 재현하지 못함)'
    return dict(status=status, column_key=P['column_key'], source=P['source'], m1=m1, m2=m2, m3=m3, m3_n_bins=len(pairs), m3_n_common=n, m4=m4, m4_reason=why,
                pred_max_skin=C.r6(pm), meas_max_skin=M['max_skin'], pred_end_skin=C.r6(pe), meas_end_skin=me, end_t_s=T_end, end_meas_dt_s=dt,
                pred_first_throttle_s=pf, meas_first_throttle_s=mf, item_source=src, repro_ok=repro_ok, n_rows_pred=n_rows)


def pair_errors(PP, MP):
    d_pred, d_meas = PP['d_max_skin'], MP['d_max_skin']
    same = C.sign(d_pred) == C.sign(d_meas)
    ad = round(abs(d_pred - d_meas), 6)
    fp_, fm = PP.get('d_first_throttle_s'), MP.get('d_first_throttle_s')
    return dict(status='계산', column_key=PP['column_key'], d_pred=C.r6(d_pred), d_meas=C.r6(d_meas), sign_pred=C.sign(d_pred), sign_meas=C.sign(d_meas), same_sign=same, abs_diff=ad,
                passed=bool(same and ad <= C.PASS_ABS), d_first_throttle_pred=fp_, d_first_throttle_meas=fm,
                d_first_throttle_same_sign=(None if (fp_ is None or fm is None) else C.sign(fp_) == C.sign(fm)), d_first_throttle_abs_diff=(None if (fp_ is None or fm is None) else round(abs(fp_ - fm), 3)),
                work_ratio_pred=PP.get('work_ratio'), work_ratio_meas=MP.get('work_ratio'))


def summarize(vals):
    v = [x for x in vals if x is not None]
    if not v:
        return dict(n=0, mean=None, mean_abs=None, max_abs=None, min=None, max=None, sd=None)
    return dict(n=len(v), mean=C.r6(statistics.mean(v)), mean_abs=C.r6(statistics.mean(abs(x) for x in v)), max_abs=C.r6(max(abs(x) for x in v)), min=C.r6(min(v)), max=C.r6(max(v)),
                sd=C.r6(statistics.stdev(v)) if len(v) > 1 else None)


def verdict_name(pan, resource):
    if pan == 'v22':
        return C.VERDICT_FIT if resource == 'GPU' else 'NPU 적합도 오차 (비교 · 개발 자료)'
    if pan == 'v22_2pt':
        return '기술 (v2.2 열 두 점 — 판정 아님)'
    return C.verdict_holdout(pan) if resource == 'GPU' else f'NPU 홀드아웃 오차 (판 {pan} · 비교)'


def judge(pred, meas, cells):
    runs_out = {}
    for tag, rec in pred['runs'].items():
        M = meas['runs'][tag]
        row = dict(label=M['label'], resource=M['resource'], model=M['model'], group=M['group'], role=M['role'], kind=cells['runs'][tag]['kind'], start_skin=M['start_skin'],
                   in_range=M['in_range'], lower=M['lower'], meas_max_skin=M['max_skin'], meas_first_throttle_s=M['first_throttle']['abs_s'], pans={})
        for pan, cols in rec.items():
            ck = choose_column(cols, M['start_skin'])
            e = run_errors(cols[ck], M, M['group'])
            e['verdict_name'] = verdict_name(pan, M['resource'])
            row['pans'][pan] = e
        runs_out[tag] = row
    pairs_out = {}
    for key, pp in pred['pairs'].items():
        MP = meas['pairs'][key]
        row = dict(resource=MP['resource'], group=MP['group'], block=MP['block'], a=MP['a'], b=MP['b'], start_skin_mean=MP['start_skin_mean'], in_range=MP['in_range'], note=MP.get('note'),
                   d_meas=MP['d_max_skin'], d_first_throttle_meas=MP['d_first_throttle_s'], pans={pan: pair_errors(v, MP) for pan, v in pp.items()})
        pairs_out[key] = row
    res_out = {}
    for key, rr in pred['resources'].items():
        MR = meas['resources'][key]
        res_out[key] = dict(resource=MR['resource'], group=MR['group'], pairs=MR['pairs'], measured=MR['verdict'], note=MR.get('note'),
                            pans={pan: dict(predicted=v['predicted_verdict'], columns=v['columns'], matched=(v['predicted_verdict'] == MR['verdict'])) for pan, v in rr.items()})
    # summaries: (pan, resource) over all runs with that pan; plus per group
    summ = {}
    pans_all = sorted({pan for r in runs_out.values() for pan in r['pans']})
    for pan in pans_all:
        for resource in ('GPU', 'NPU'):
            tags = [t for t, r in runs_out.items() if r['resource'] == resource and pan in r['pans']]
            if not tags:
                continue
            rows = [runs_out[t]['pans'][pan] for t in tags]
            pk = [k for k, p in pairs_out.items() if p['resource'] == resource and pan in p['pans']]
            rk = [k for k, r in res_out.items() if r['resource'] == resource and pan in r['pans']]
            n_na = sum(1 for r in rows if r['status'] != '계산')
            summ[f'{pan}|{resource}'] = dict(pan=pan, pan_label=C.PAN_LABEL.get(pan, pan), resource=resource, verdict_name=verdict_name(pan, resource), n_runs=len(tags), runs=tags,
                                             n_not_computable=n_na, m1=summarize([r['m1'] for r in rows]), m2=summarize([r['m2'] for r in rows]), m3=summarize([r['m3'] for r in rows]),
                                             m4=summarize([r['m4'] for r in rows]), m4_null=sum(1 for r in rows if r['m4'] is None),
                                             m4_null_reasons={r['m4_reason']: sum(1 for x in rows if x['m4_reason'] == r['m4_reason']) for r in rows if r['m4_reason']},
                                             m5_k=sum(1 for k in pk if pairs_out[k]['pans'][pan]['passed']), m5_n=len(pk), m5_pairs=pk,
                                             m5_first_throttle_same_sign=sum(1 for k in pk if pairs_out[k]['pans'][pan]['d_first_throttle_same_sign']), m5_first_throttle_n=sum(1 for k in pk if pairs_out[k]['pans'][pan]['d_first_throttle_same_sign'] is not None),
                                             m6_matched=sum(1 for k in rk if res_out[k]['pans'][pan]['matched']), m6_n=len(rk), m6_resources=rk,
                                             by_group={g: dict(n=len([t for t in tags if runs_out[t]['group'] == g]), m1=summarize([runs_out[t]['pans'][pan]['m1'] for t in tags if runs_out[t]['group'] == g]),
                                                               m3=summarize([runs_out[t]['pans'][pan]['m3'] for t in tags if runs_out[t]['group'] == g]))
                                                       for g in sorted({runs_out[t]['group'] for t in tags})})
    return dict(kind='gpuerr_judge_v1', registration=f'{C.REG} ({C.REG_COMMIT[:7]}) §3 · §4',
                rule=dict(column='판마다 그 판의 열 규칙 (동결 실제 시작 열 / 두 점 가까운 쪽 · 동률 29.5 / v0 실제 시작 재생)', m2='창 끝 = 마지막 공통 초 (N1 · N2 = 899 s 동결 skin_899)',
                          m3='10 s 칸 (체인 절대 시각) 공통 칸 |차| 평균', m4='칸 k + 뒤 3칸 · GPU ×1.10 · NPU ×1.06 · 절대 시각 · 둘 중 하나 없으면 null',
                          m5='부호 같음 (6자리) ∧ |예측 Δ − 실측 Δ| ≤ 1.0 ℃ → 통과 · k / n 기술 · 판정 이름 없음', m6='resource_verdict 문구 같음',
                          verdict_names=[C.VERDICT_FIT, C.verdict_holdout('○')], computable='계산 불가 = 분모에 남음'),
                summaries=summ, runs=runs_out, pairs=pairs_out, resources=res_out)


def write_csvs(res, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    p1 = os.path.join(out_dir, 'gpuerr_runs.csv')
    with open(p1, 'w', encoding='utf-8-sig', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(['tag', 'label', 'resource', 'model', 'group', 'kind', 'start_skin', 'in_range', 'lower', 'pan', 'verdict_name', 'status', 'column_key', 'source',
                    'meas_max_skin', 'pred_max_skin', 'm1_max_skin_err', 'end_t_s', 'meas_end_skin', 'pred_end_skin', 'm2_end_skin_err', 'm3_traj_mae', 'm3_n_bins',
                    'meas_first_throttle_s', 'pred_first_throttle_s', 'm4_first_throttle_err_s', 'm4_reason'])
        for tag, r in res['runs'].items():
            for pan, e in r['pans'].items():
                w.writerow([tag, r['label'], r['resource'], r['model'], r['group'], r['kind'], r['start_skin'], r['in_range'], r['lower'], pan, e['verdict_name'], e['status'], e['column_key'], e['source'],
                            e['meas_max_skin'], e['pred_max_skin'], e['m1'], e['end_t_s'], e['meas_end_skin'], e['pred_end_skin'], e['m2'], e['m3'], e['m3_n_bins'],
                            e['meas_first_throttle_s'], e['pred_first_throttle_s'], e['m4'], e['m4_reason']])
    p2 = os.path.join(out_dir, 'gpuerr_pairs.csv')
    with open(p2, 'w', encoding='utf-8-sig', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(['pair', 'resource', 'group', 'block', 'a', 'b', 'start_skin_mean', 'in_range', 'pan', 'column_key', 'd_meas_max_skin', 'd_pred_max_skin', 'sign_pred', 'sign_meas', 'same_sign', 'abs_diff', 'passed',
                    'd_first_throttle_meas_s', 'd_first_throttle_pred_s', 'd_first_throttle_same_sign', 'note'])
        for k, p in res['pairs'].items():
            for pan, e in p['pans'].items():
                w.writerow([k, p['resource'], p['group'], p['block'], p['a'], p['b'], p['start_skin_mean'], p['in_range'], pan, e['column_key'], e['d_meas'], e['d_pred'], e['sign_pred'], e['sign_meas'], e['same_sign'], e['abs_diff'], e['passed'],
                            e['d_first_throttle_meas'], e['d_first_throttle_pred'], e['d_first_throttle_same_sign'], p['note']])
    p3 = os.path.join(out_dir, 'gpuerr_summary.csv')
    with open(p3, 'w', encoding='utf-8-sig', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(['pan', 'resource', 'verdict_name', 'n_runs', 'n_not_computable', 'm1_mean', 'm1_max_abs', 'm2_mean', 'm2_mean_abs', 'm3_mean', 'm3_min', 'm3_max', 'm4_mean_abs', 'm4_n', 'm4_null', 'm5_k', 'm5_n', 'm6_matched', 'm6_n'])
        for k, s in res['summaries'].items():
            w.writerow([s['pan'], s['resource'], s['verdict_name'], s['n_runs'], s['n_not_computable'], s['m1']['mean'], s['m1']['max_abs'], s['m2']['mean'], s['m2']['mean_abs'], s['m3']['mean'], s['m3']['min'], s['m3']['max'],
                        s['m4']['mean_abs'], s['m4']['n'], s['m4_null'], s['m5_k'], s['m5_n'], s['m6_matched'], s['m6_n']])
    return p1, p2, p3


def write_fig8(res, out_dir, modelerr_cells_csv):
    """fig8_pred_vs_meas.csv — x = measured max SKIN · y = v2.2 predicted max SKIN: energy-C 16 NPU cells (P1j values as-is) + this session's runs."""
    p = os.path.join(out_dir, 'fig8_pred_vs_meas.csv')
    rows = []
    if modelerr_cells_csv and os.path.exists(modelerr_cells_csv):
        for r in csv.DictReader(open(modelerr_cells_csv, encoding='utf-8-sig')):
            if r['model'] == 'v22' and r['status'] == '계산':
                rows.append(dict(run=f"energyC_{r['cell']}_b{r['block']}", resource='NPU', model='effnet', group='energyC', kind='재현 홀드아웃 (에너지 C · P1j 값 그대로)', marker='holdout',
                                 start_skin=r['start_skin'], column=r['column'], meas_max_skin=r['meas_max_skin'], pred_max_skin_v22=r['pred_max_skin'], m3=r['m3_traj_mae'], source='sim/out_modelerr/modelerr_cells.csv'))
    for tag, r in res['runs'].items():
        e = r['pans'].get('v22')
        if not e:
            continue
        weak = r['group'] in ('N1s', 'N4s')
        rows.append(dict(run=tag, resource=r['resource'], model=r['model'], group=r['group'], kind=('약한 홀드아웃' if weak else '적합도 (개발 자료)'), marker=('holdout' if weak else 'fit'),
                         start_skin=r['start_skin'], column=e['column_key'], meas_max_skin=e['meas_max_skin'], pred_max_skin_v22=e['pred_max_skin'], m3=e['m3'], source='gpuerr.json'))
    with open(p, 'w', encoding='utf-8-sig', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=['run', 'resource', 'model', 'group', 'kind', 'marker', 'start_skin', 'column', 'meas_max_skin', 'pred_max_skin_v22', 'm3', 'source'])
        w.writeheader()
        for r in rows:
            w.writerow(r)
    return p, len(rows)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--selftest', action='store_true')
    ap.add_argument('--pred', default=C.PRED_JSON)
    ap.add_argument('--meas', default=os.path.join(C.OUT_OD, 'measure_gpu.json'))
    ap.add_argument('--out-od', default=C.OUT_OD)
    ap.add_argument('--out-repo', default=C.OUT_REPO)
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    pred, meas, cells = C.load_json(a.pred), C.load_json(a.meas), C.load_json(C.CELLS_JSON)
    res = judge(pred, meas, cells)
    res['inputs'] = dict(pred=os.path.relpath(a.pred, C.ROOT), pred_sha256=C.sha256_file(a.pred), meas=a.meas, meas_sha256=C.sha256_file(a.meas), cells_sha256=C.sha256_file(C.CELLS_JSON),
                         this=C.sha256_file(os.path.abspath(__file__)), common_py=C.sha256_file(C.__file__))
    p1 = os.path.join(a.out_od, 'gpuerr.json')
    s1 = C.write_json(p1, res)
    s2 = C.write_json(os.path.join(a.out_repo, 'gpuerr.json'), res)
    c = write_csvs(res, a.out_od)
    write_csvs(res, a.out_repo)
    f8 = write_fig8(res, a.out_od, os.path.join(C.OD_SIM, 'out_modelerr', 'modelerr_cells.csv'))
    write_fig8(res, a.out_repo, os.path.join(C.OD_SIM, 'out_modelerr', 'modelerr_cells.csv'))
    for k, s in res['summaries'].items():
        print(f"{k:14s} {s['verdict_name']:34s} n {s['n_runs']:2d} (불가 {s['n_not_computable']}) · m1 {s['m1']['mean']} (|max| {s['m1']['max_abs']}) · m2 {s['m2']['mean']} · m3 {s['m3']['mean']} [{s['m3']['min']} ~ {s['m3']['max']}] · m4 |·| {s['m4']['mean_abs']} (n {s['m4']['n']} null {s['m4_null']}) · m5 {s['m5_k']}/{s['m5_n']} · m6 {s['m6_matched']}/{s['m6_n']}")
    for tag, r in res['runs'].items():
        for pan, e in r['pans'].items():
            print(f"  {tag:15s} {pan:8s} col {e['column_key']:14s} m1 {e['m1']:+.3f} m2 {e['m2']:+.3f} m3 {e['m3']} (n {e['m3_n_bins']}) m4 {e['m4']} {e['m4_reason'] or ''} [{e['status']}]" if e['m1'] is not None else f"  {tag:15s} {pan:8s} {e['status']}")
    for k, p in res['pairs'].items():
        print(f"  pair {k}: Δmeas {p['d_meas']:+.2f} · " + ' · '.join(f"{pan} Δpred {e['d_pred']:+.3f} |차| {e['abs_diff']:.3f} {'PASS' if e['passed'] else 'fail'}" for pan, e in p['pans'].items()))
    for k, r in res['resources'].items():
        print(f"  resource {k}: 실측 {r['measured']} · " + ' · '.join(f"{pan} {e['predicted']} {'맞음' if e['matched'] else '틀림'}" for pan, e in r['pans'].items()))
    print('->', p1, s1, '| repo', s2, '| csv', c, '| fig8', f8)
    return 0


# ============================================================ selftest (합성 · 양방향 · 결과 전)
def _fake(n_runs_gpu=3, n_runs_npu=1, skin_bins=90):
    pred, meas, cells = dict(runs={}, pairs={}, resources={}), dict(runs={}, pairs={}, resources={}), dict(runs={})
    skin = [30.0 + 0.01 * t for t in range(900)]
    bins = [round(sum(skin[k * 10:(k + 1) * 10]) / 10, 4) for k in range(skin_bins)]
    tags = [(f'g{i}', 'GPU') for i in range(n_runs_gpu)] + [(f'n{i}', 'NPU') for i in range(n_runs_npu)]
    for tag, res in tags:
        mx, ft = 38.0, 100
        meas['runs'][tag] = dict(label=tag, resource=res, model='mobilenet', group='N1', role=res, start_skin=29.6, in_range=True, lower=None, max_skin=mx, t_max=900.2,
                                 skin_by_t=[(float(t), s) for t, s in enumerate(skin)] + [(900.2, skin[-1])], bin_mean_skin=bins, n_bins=skin_bins, skin_899_judge=skin[899],
                                 first_throttle=dict(abs_s=ft))
        cells['runs'][tag] = dict(kind='합성')
        rec = {}
        for pan in ('v21', 'v22'):
            rec[pan] = {'29.5': dict(source='frozen+generated_series', column_key='29.5', n_rows=900, items=dict(max_skin=mx, skin_899=skin[899], first_throttle_s=ft), repro=dict(all=True),
                                     gen=dict(max_skin=mx, skin_1s=skin, bin_mean_skin=bins, n_bins=skin_bins), first_throttle_abs_s=ft)}
        pred['runs'][tag] = rec
    meas['pairs']['P1'] = dict(resource='GPU', group='N1', block=1, a='g0', b='g1', start_skin_mean=29.6, in_range=True, d_max_skin=1.5, d_first_throttle_s=-100, work_ratio=1.0)
    meas['pairs']['P2'] = dict(resource='GPU', group='N1', block=2, a='g1', b='g2', start_skin_mean=29.6, in_range=True, d_max_skin=-0.4, d_first_throttle_s=None, work_ratio=1.0)
    for k, d in (('P1', 1.5), ('P2', -0.4)):
        pred['pairs'][k] = {pan: dict(column_key='29.5', d_max_skin=d, d_first_throttle_s=-100, work_ratio=1.0) for pan in ('v21', 'v22')}
    meas['resources']['R1'] = dict(resource='GPU', group='N1', pairs=['P1', 'P2'], verdict='엇갈림')
    pred['resources']['R1'] = {pan: dict(predicted_verdict='엇갈림', columns=['29.5', '29.5']) for pan in ('v21', 'v22')}
    return pred, meas, cells


def selftest():
    res = []

    def check(name, cond, got=''):
        res.append((name, bool(cond), got))
    pred, meas, cells = _fake()
    j = judge(pred, meas, cells)
    g0 = j['runs']['g0']['pans']['v22']
    check('① 예측 = 실측 → m1 = m2 = m3 = m4 = 0 (모든 런 · 판) · 쌍 통과 2/2 · 문구 일치 1/1 (v21 · v22)',
          all(e['m1'] == 0 and e['m2'] == 0 and e['m3'] == 0 and e['m4'] == 0 for r in j['runs'].values() for e in r['pans'].values())
          and j['summaries']['v22|GPU']['m5_k'] == 2 and j['summaries']['v22|GPU']['m5_n'] == 2 and j['summaries']['v21|GPU']['m6_matched'] == 1 and j['summaries']['v21|GPU']['m6_n'] == 1, (g0['m1'], g0['m3'], j['summaries']['v22|GPU']['m5_k']))
    check('① m2 창 끝 = 899 (N1 · 동결 skin_899) · m3 칸 90', g0['end_t_s'] == 899 and g0['item_source']['m2'] == 'frozen' and g0['m3_n_bins'] == 90)
    # sign flip on the predicted pair Δ → both pairs fail (P1 +1.5 → −1.5: sign differs; P2 −0.4 → +0.4: sign differs though |diff| 0.8 ≤ 1.0)
    pred2 = copy.deepcopy(pred)
    for k in pred2['pairs']:
        for pan in pred2['pairs'][k]:
            pred2['pairs'][k][pan]['d_max_skin'] = -pred2['pairs'][k][pan]['d_max_skin']
    j2 = judge(pred2, meas, cells)
    check('② 쌍 Δ 부호 뒤집음 → 2쌍 전부 실패 (P2 는 |차| 0.8 ≤ 1.0 이어도 부호 달라 실패) · k 0/2', j2['summaries']['v22|GPU']['m5_k'] == 0 and all(not e['passed'] for p in j2['pairs'].values() for e in p['pans'].values())
          and j2['pairs']['P2']['pans']['v22']['abs_diff'] == 0.8 and j2['pairs']['P2']['pans']['v22']['same_sign'] is False, [(k, e['abs_diff'], e['passed']) for k, p in j2['pairs'].items() for e in [p['pans']['v22']]])
    # |diff| boundary: pred Δ = meas + 1.0 → pass; + 1.000001 → fail
    pred3 = copy.deepcopy(pred)
    pred3['pairs']['P1']['v22']['d_max_skin'] = 2.5
    pred3['pairs']['P2']['v22']['d_max_skin'] = -0.4 - 1.000001
    j3 = judge(pred3, meas, cells)
    check('③ |차| 경계: 1.0 → 통과 · 1.000001 → 실패 (부호 같음)', j3['pairs']['P1']['pans']['v22']['passed'] and not j3['pairs']['P2']['pans']['v22']['passed'] and j3['pairs']['P2']['pans']['v22']['same_sign'])
    # 계산 불가: repro failure on g1 v22 → status 계산 불가 · m3 None · still counted in n_runs and n_not_computable
    pred4 = copy.deepcopy(pred)
    pred4['runs']['g1']['v22']['29.5']['repro'] = dict(all=False)
    j4 = judge(pred4, meas, cells)
    s4 = j4['summaries']['v22|GPU']
    check('④ 계산 불가 (재현 실패): 그 런 m3 None · m1 은 동결 항목이라 그대로 · n_runs 3 유지 · n_not_computable 1 · m3 n 2',
          j4['runs']['g1']['pans']['v22']['status'].startswith('계산 불가') and j4['runs']['g1']['pans']['v22']['m3'] is None and j4['runs']['g1']['pans']['v22']['m1'] == 0
          and s4['n_runs'] == 3 and s4['n_not_computable'] == 1 and s4['m3']['n'] == 2, (s4['n_runs'], s4['n_not_computable'], s4['m3']['n']))
    # verdict names: fit rows carry no pass/fail word; holdout rows carry the 판 name
    names = {e['verdict_name'] for r in j['runs'].values() for e in r['pans'].values()}
    check('⑤ 판정 이름: v2.2 행 = "GPU 적합도 오차 (개발 자료)" (통과 · 실패 · 확인 단어 없음) · v21 행 = "GPU 홀드아웃 오차 (판 v21 · 동결 예측)"',
          j['runs']['g0']['pans']['v22']['verdict_name'] == C.VERDICT_FIT and j['runs']['g0']['pans']['v21']['verdict_name'] == 'GPU 홀드아웃 오차 (판 v21 · 동결 예측)'
          and not any(w in j['summaries']['v22|GPU']['verdict_name'] for w in ('통과', '실패', '확인')) and j['runs']['n0']['pans']['v22']['verdict_name'].startswith('NPU 적합도'), names)
    check('⑤ 요약에 pass/fail 키 없음 (k / n 만)', 'passed' not in j['summaries']['v22|GPU'] and 'verdict' not in j['summaries']['v22|GPU'] and 'm5_k' in j['summaries']['v22|GPU'])
    # m4 null reasons and sign of m1/m2/m3 with an offset prediction
    pred5 = copy.deepcopy(pred)
    c5 = pred5['runs']['g0']['v22']['29.5']
    c5['items']['max_skin'] = 38.7; c5['items']['skin_899'] = c5['items']['skin_899'] - 0.3; c5['first_throttle_abs_s'] = None
    c5['gen']['bin_mean_skin'] = [None] * 5 + [x + 0.5 for x in c5['gen']['bin_mean_skin'][5:]]
    j5 = judge(pred5, meas, cells)
    e5 = j5['runs']['g0']['pans']['v22']
    check('⑥ m1 +0.7 · m2 −0.3 · m3 0.5 (85 칸, None 5 제외) · m4 null "예측 없음 (실측 100 s)"', abs(e5['m1'] - 0.7) < 1e-9 and abs(e5['m2'] + 0.3) < 1e-9 and abs(e5['m3'] - 0.5) < 1e-9 and e5['m3_n_bins'] == 85
          and e5['m4'] is None and e5['m4_reason'] == '예측 없음 (실측 100 s)', (e5['m1'], e5['m2'], e5['m3'], e5['m4_reason']))
    meas6 = copy.deepcopy(meas)
    meas6['runs']['g0']['first_throttle']['abs_s'] = None
    j6 = judge(pred, meas6, cells)
    check('⑥ 실측 조임 없음 → m4 null "실측 없음 (예측 100 s)" · 둘 다 없으면 "둘 다 없음"', j6['runs']['g0']['pans']['v22']['m4_reason'] == '실측 없음 (예측 100 s)'
          and judge(pred5, meas6, cells)['runs']['g0']['pans']['v22']['m4_reason'].startswith('둘 다 없음'))
    # window end for a non-900 group: last common second = min(n_rows − 1, floor(t_max))
    pred7, meas7, cells7 = _fake(1, 0)
    meas7['runs']['g0']['group'] = 'v1'; meas7['runs']['g0']['t_max'] = 1300.0; meas7['runs']['g0'].pop('skin_899_judge')
    pred7['runs']['g0']['v22']['29.5']['n_rows'] = 900
    j7 = judge(pred7, meas7, cells7)
    check('⑦ 900 s 창 밖 묶음: 창 끝 = min(900 − 1, 1300) = 899 (생성 행) · 실측 = 가장 가까운 행', j7['runs']['g0']['pans']['v22']['end_t_s'] == 899 and j7['runs']['g0']['pans']['v22']['item_source']['m2'] == 'generated' and j7['runs']['g0']['pans']['v22']['m2'] == 0)
    check('⑧ 열 고르기: actual: 열이 있으면 그것 · 두 점은 가까운 쪽 (29.6 → 29.5) · 29.45 열 하나면 그것', choose_column({'actual:31.2': 1}, 31.2) == 'actual:31.2' and choose_column({'29.5': 1, '30.5': 2}, 29.6) == '29.5'
          and choose_column({'29.5': 1, '30.5': 2}, 30.1) == '30.5' and choose_column({'29.45': 1}, 29.45) == '29.45')
    check('⑨ 결정성: 같은 입력 두 번 → 같은 JSON 바이트', C.dumps(judge(pred, meas, cells)) == C.dumps(j))
    return C.print_table(res)


if __name__ == '__main__':
    sys.exit(main())
