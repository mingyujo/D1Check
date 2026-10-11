"""Confirmation judgement (registration §3 · §4; arithmetic = DECISIONS_P1l.md D10 · D11). Run ONCE after measure_r4.

Inputs: out/predict_confirm.json (frozen, closed loop) + out/r4_measured.json. Output: out/parsim_judge.json + sessions.csv + pairs.csv.
Per session and form, from each replicate: model AP / SKIN at the measured HAL sample times -> max, 10 s-bin path MAE; then the
median over replicates (D9). Service: urgent P95 error = median predicted P95 - measured P95.
Verdict names (M-sup only): S passes -> "병행 [열/서비스] 재현 확인 (기존 자료 · 2자원)" · only L -> "병행 [열/서비스] 탐색용 (오차 ○ 붙임)"
· neither -> "병행 [열/서비스] 미재현". M-kappa side by side.

usage: python -m d1sim.parsim_v1.judge_parsim [--pred P] [--meas M] [--out DIR] [--selftest]
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import statistics
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
OUTDIR = os.path.join(HERE, 'out')
AP_TOL0 = 0.05      # sign tie (D10)
MS_TOL0 = 0.5
THERMAL = dict(L=dict(ap_max=2.0, frac=0.75, mae=1.5, pair_frac=0.75), S=dict(ap_max=1.0, frac=0.85, mae=1.0, pair_d=1.0))
SERVICE = dict(L=dict(p95=25.0, n=12), S=dict(p95=15.0, n=14, pair_d=15.0, pair_n=6))
NAMES = {'S': '병행 {} 재현 확인 (기존 자료 · 2자원)', 'L': '병행 {} 탐색용 (오차 ○ 붙임)', None: '병행 {} 미재현'}


def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


def at(path, t):
    """1 s path, linear interpolation."""
    i = int(math.floor(t))
    if i >= len(path) - 1:
        return path[-1]
    if i < 0:
        return path[0]
    w = t - i
    return path[i] * (1 - w) + path[i + 1] * w


def path_mae(path, hal, col):
    bins = defaultdict(lambda: ([], []))
    for row in hal:
        t = row[0]
        b = int(t // 10)
        bins[b][0].append(at(path, t))
        bins[b][1].append(row[col])
    errs = [abs(statistics.fmean(m) - statistics.fmean(h)) for m, h in bins.values()]
    return statistics.fmean(errs)


def sign(x, tol):
    if x is None:
        return None
    return 0 if abs(x) < tol else (1 if x > 0 else -1)


def session_rows(pred, meas):
    mi = {(m['set'], m['index']): m for m in meas['sessions']}
    rows = []
    for p in pred['sessions']:
        m = mi.get((p['set'], p['index']))
        if m is None:
            continue
        hal = m['hal']
        for form, e in p['forms'].items():
            apmax, skmax, apmae, skmae, s38 = [], [], [], [], []
            for r in e['reps']:
                apmax.append(max(at(r['path_ap'], t) for t, _, _ in hal))
                skmax.append(max(at(r['path_skin'], t) for t, _, _ in hal))
                apmae.append(path_mae(r['path_ap'], hal, 1))
                skmae.append(path_mae(r['path_skin'], hal, 2))
                s38.append(next((float(i) for i, v in enumerate(r['path_skin']) if v >= 38.0), None))
            med = statistics.median
            pred_p95 = e['median']['urgent_p95_ms']
            s38m = med([x for x in s38 if x is not None]) if sum(x is not None for x in s38) * 2 > len(s38) else None
            rows.append(dict(set=p['set'], index=p['index'], policy=p['policy'], block=p['block'], pair=p['pair'], form=form,
                             pred_ap_max=med(apmax), meas_ap_max=m['ap_max'], ap_max_err=med(apmax) - m['ap_max'],
                             ap_path_mae=med(apmae), pred_skin_max=med(skmax), meas_skin_max=m['skin_max'], skin_max_err=med(skmax) - m['skin_max'],
                             skin_path_mae=med(skmae), skin_saturated=m['skin_saturated'],
                             pred_skin38_s=s38m, meas_skin38_s=m['skin38_first_s'],
                             skin38_err_s=(s38m - m['skin38_first_s']) if (s38m is not None and m['skin38_first_s'] is not None) else None,
                             pred_p95_ms=pred_p95, meas_p95_ms=m['urgent_p95_ms'],
                             p95_err_ms=(pred_p95 - m['urgent_p95_ms']) if (pred_p95 is not None and m['urgent_p95_ms'] is not None) else None,
                             pred_on_time=e['median']['on_time'], meas_on_time=m['on_time'], planned=m['planned'],
                             ap_max_err_p05=sorted(x - m['ap_max'] for x in apmax)[int(0.05 * len(apmax))],
                             ap_max_err_p95=sorted(x - m['ap_max'] for x in apmax)[min(len(apmax) - 1, int(0.95 * len(apmax)))]))
    return rows


def pair_rows(rows):
    out = []
    by = defaultdict(dict)
    for r in rows:
        by[(r['set'], r['form'], r['block'], r['pair'])]['ser' if r['policy'].startswith('CPU') else 'par'] = r
    for (st, form, block, pair), d in sorted(by.items()):
        if 'ser' not in d or 'par' not in d:
            continue
        s, p = d['ser'], d['par']
        pd_ap, md_ap = p['pred_ap_max'] - s['pred_ap_max'], p['meas_ap_max'] - s['meas_ap_max']
        pd_ms = (p['pred_p95_ms'] - s['pred_p95_ms']) if None not in (p['pred_p95_ms'], s['pred_p95_ms']) else None
        md_ms = (p['meas_p95_ms'] - s['meas_p95_ms']) if None not in (p['meas_p95_ms'], s['meas_p95_ms']) else None
        out.append(dict(set=st, form=form, block=block, pair=pair, par_policy=p['policy'],
                        pred_d_ap=pd_ap, meas_d_ap=md_ap, ap_sign_match=sign(pd_ap, AP_TOL0) == sign(md_ap, AP_TOL0),
                        ap_d_err=pd_ap - md_ap, pred_d_p95=pd_ms, meas_d_p95=md_ms,
                        p95_sign_match=(sign(pd_ms, MS_TOL0) == sign(md_ms, MS_TOL0)) if None not in (pd_ms, md_ms) else False,
                        p95_d_err=(pd_ms - md_ms) if None not in (pd_ms, md_ms) else None))
    return out


def judge_thermal(srows, prows):
    n = len(srows)
    mae_med = statistics.median(r['ap_path_mae'] for r in srows)
    res = {}
    for lv in ('L', 'S'):
        c = THERMAL[lv]
        k_ok = sum(abs(r['ap_max_err']) <= c['ap_max'] for r in srows)
        frac_ok = k_ok / n >= c['frac'] - 1e-12
        mae_ok = mae_med <= c['mae'] + 1e-12
        sm = sum(p['ap_sign_match'] for p in prows)
        if lv == 'L':
            pair_ok = sm >= math.floor(c['pair_frac'] * len(prows))
            res[lv] = dict(sessions_ok=k_ok, sessions=n, mae_median=mae_med, pairs_sign=sm, pairs=len(prows),
                           pass_=frac_ok and mae_ok and pair_ok, parts=dict(frac=frac_ok, mae=mae_ok, pairs=pair_ok))
        else:
            d_ok = all(abs(p['ap_d_err']) <= c['pair_d'] + 1e-12 for p in prows)
            pair_ok = sm == len(prows)
            res[lv] = dict(sessions_ok=k_ok, sessions=n, mae_median=mae_med, pairs_sign=sm, pairs=len(prows),
                           pairs_d_ok=sum(abs(p['ap_d_err']) <= c['pair_d'] + 1e-12 for p in prows),
                           pass_=frac_ok and mae_ok and pair_ok and d_ok, parts=dict(frac=frac_ok, mae=mae_ok, pairs=pair_ok, pair_d=d_ok))
    return res


def judge_service(srows, prows):
    res = {}
    errs = [r['p95_err_ms'] for r in srows]
    for lv in ('L', 'S'):
        c = SERVICE[lv]
        k = sum(e is not None and abs(e) <= c['p95'] + 1e-12 for e in errs)
        sm = sum(p['p95_sign_match'] for p in prows)
        sign_ok = sm == 8 and len(prows) == 8
        if lv == 'L':
            res[lv] = dict(sessions_ok=k, need=c['n'], pairs_sign=sm, pairs=len(prows), pass_=k >= c['n'] and sign_ok)
        else:
            kd = sum(p['p95_d_err'] is not None and abs(p['p95_d_err']) <= c['pair_d'] + 1e-12 for p in prows)
            res[lv] = dict(sessions_ok=k, need=c['n'], pairs_sign=sm, pairs=len(prows), pairs_d_ok=kd, need_pairs_d=c['pair_n'],
                           pass_=k >= c['n'] and sign_ok and kd >= c['pair_n'])
    return res


def name(part, verdict):
    lv = 'S' if verdict['S']['pass_'] else ('L' if verdict['L']['pass_'] else None)
    return NAMES[lv].format(part), lv


def judge(pred, meas):
    srows = session_rows(pred, meas)
    prows = pair_rows(srows)
    out = dict(forms={})
    for form in ('M-sup', 'M-kappa'):
        f = {}
        sC = [r for r in srows if r['form'] == form and r['set'] == 'R4C']
        sS = [r for r in srows if r['form'] == form and r['set'] == 'R4S']
        pC = [p for p in prows if p['form'] == form and p['set'] == 'R4C']
        pS_A = [p for p in prows if p['form'] == form and p['set'] == 'R4S' and p['block'] == 'A']
        f['thermal_C'] = judge_thermal(sC, pC)
        f['thermal_S'] = judge_thermal(sS, pS_A)
        f['service_C'] = judge_service(sC, pC)
        f['names'] = dict(thermal_C=name('열', f['thermal_C']), thermal_S=name('열', f['thermal_S']), service_C=name('서비스', f['service_C']))
        lvl = {None: 0, 'L': 1, 'S': 2}
        low = min((f['names']['thermal_C'], f['names']['thermal_S']), key=lambda x: lvl[x[1]])
        f['names']['thermal_ladder_status'] = low
        f['confirm_mae'] = dict(ap_path_mae_median_C=f['thermal_C']['L']['mae_median'], ap_path_mae_median_S=f['thermal_S']['L']['mae_median'],
                                p95_abs_err_median_C=statistics.median(abs(r['p95_err_ms']) for r in sC if r['p95_err_ms'] is not None))
        out['forms'][form] = f
    out['sessions'] = srows
    out['pairs'] = prows
    return out


def write(out, outdir, pred_path, meas_path):
    target = os.path.join(outdir, 'parsim_judge.json')
    if os.path.exists(target):
        raise SystemExit(f'refuse: {target} exists (judged once)')
    out = dict(out, inputs=dict(predict_confirm=sha(pred_path), r4_measured=sha(meas_path)), judge_sha256=sha(os.path.abspath(__file__)))
    json.dump(out, open(target, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    for fn, rows in (('parsim_sessions.csv', out['sessions']), ('parsim_pairs.csv', out['pairs'])):
        with open(os.path.join(outdir, fn), 'w', encoding='utf-8', newline='\n') as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()), lineterminator='\n')
            w.writeheader()
            w.writerows(rows)
    print('wrote', target, sha(target))


def selftest():
    """Synthetic: perfect prediction -> S passes everywhere; shifted AP -> thermal fails; sign flip -> pair fails."""
    def mk(shift_ap=0.0, flip=False):
        pred, meas = dict(sessions=[]), dict(sessions=[])
        for st, n, win in (('R4C', 16, 120), ('R4S', 14, 720)):
            for i in range(n):
                block = 'A' if i < 8 else 'N'
                pair = (i % 8) // 2
                ser = i % 2 == 0
                pol = 'CPU_URGENT_ONLINE_V1' if ser else ('B2_PARALLEL_ONLINE_V1' if block == 'A' else 'S26_NPU_PARALLEL_V1')
                peak = 42.5 if ser else 41.5
                if flip and not ser:
                    peak = 43.5
                ap = [30 + (peak - 30) * min(1, t / 40) for t in range(int(win) + 1)]
                sk = [30 + 4 * min(1, t / 60) for t in range(int(win) + 1)]
                hal = [[float(t), ap[t], sk[t]] for t in range(1, int(win), 2)]
                p95 = 120.0 if ser else 75.0
                rep = dict(path_ap=[a + shift_ap for a in ap], path_skin=sk)
                pred['sessions'].append(dict(set=st, index=i, policy=pol, block=block, pair=pair, forms={
                    f: dict(median=dict(urgent_p95_ms=p95, on_time=192), reps=[rep] * 3) for f in ('M-sup', 'M-kappa')}))
                meas['sessions'].append(dict(set=st, index=i, policy=pol, block=block, pair=pair, ap_max=max(a for _, a, _ in hal),
                                             skin_max=max(s for _, _, s in hal), skin_saturated=False, skin38_first_s=None,
                                             urgent_p95_ms=p95, on_time=192, planned=192, hal=hal))
        return pred, meas
    j = judge(*mk())
    ok = all(j['forms']['M-sup']['names'][k][1] == 'S' for k in ('thermal_C', 'thermal_S', 'service_C'))
    j2 = judge(*mk(shift_ap=2.5))
    ok &= j2['forms']['M-sup']['names']['thermal_C'][1] is None and j2['forms']['M-sup']['names']['service_C'][1] == 'S'
    p, m = mk(flip=True)
    for s in m['sessions']:          # measured keeps original peaks -> predicted pair sign flipped
        if not s['policy'].startswith('CPU'):
            s['ap_max'] = 41.5
            s['hal'] = [[t, 30 + 11.5 * min(1, t / 40), sk] for t, _, sk in s['hal']]
    j3 = judge(p, m)
    ok &= not j3['forms']['M-sup']['thermal_C']['L']['parts']['pairs']
    print('judge selftest', 'PASS' if ok else 'FAIL', j['forms']['M-sup']['names']['thermal_C'], j2['forms']['M-sup']['names']['thermal_C'])
    return ok


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--pred', default=os.path.join(OUTDIR, 'predict_confirm.json'))
    ap.add_argument('--meas', default=os.path.join(OUTDIR, 'r4_measured.json'))
    ap.add_argument('--out', default=OUTDIR)
    ap.add_argument('--selftest', action='store_true')
    a = ap.parse_args(argv)
    if a.selftest:
        return 0 if selftest() else 1
    pred = json.load(open(a.pred, encoding='utf-8'))
    meas = json.load(open(a.meas, encoding='utf-8'))
    out = judge(pred, meas)
    write(out, a.out, a.pred, a.meas)
    for form, f in out['forms'].items():
        print(form, {k: v[0] for k, v in f['names'].items()})


if __name__ == '__main__':
    sys.exit(main())
