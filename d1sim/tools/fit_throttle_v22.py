"""fit_throttle_v22.py — fit throttle model v2.2 (d1sim/throttle_v22.py) and count the pre-registered selection score.

Prereg sim/스로틀모형_사전등록_v22.md (mirror d1sim/docs/, commit 9056685 — before any fit) · rules sim/G1_판정_1006.md §3 · §4.
Deterministic: fixed Nelder-Mead starts, no RNG (independent starts run in parallel processes — wall time only).
v0/v1/v2/v2.1 code, profiles and predictions are not modified; fit_throttle_v1/v21 and predict_night_1005e are imported for helpers.
The judges are imported by file path through predict_night_1005e.load_judge() (night1005e_judge 2db1cda5 -> night1005_judge ca8680c2).

  py d1sim/tools/fit_throttle_v22.py --forms A M [--write-profiles]    # prereg §3 · §4: fit, selection score, reports
  py d1sim/tools/fit_throttle_v22.py --holdout                          # prereg §6 / G1 §4: weak holdout — only after the fix commit
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np
from scipy.optimize import minimize

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, ROOT)
from d1sim import throttle_v21 as tv21  # noqa: E402
from d1sim import throttle_v22 as tv22  # noqa: E402
from d1sim.tools import extract_traces_v22 as x22  # noqa: E402
from d1sim.tools import fit_throttle_v1 as f1  # noqa: E402
from d1sim.tools import fit_throttle_v21 as f21  # noqa: E402
from d1sim.tools import predict_night_1005e as pn5e  # noqa: E402

DATA = os.path.join(ROOT, 'd1sim', 'data')
OUT = os.path.join(ROOT, 'd1sim', 'out')
PROFILES = os.path.join(ROOT, 'd1sim', 'profiles')
SIM = f1.SIM
MAN22 = json.load(open(os.path.join(DATA, 'trace_v22_manifest.json'), encoding='utf-8'))
RES_OF22 = {t: [x22.RUNS[t][2]] * len(MAN22[t]['segments']) for t in x22.RUNS}
EFFNET = {t for t in x22.RUNS if t.startswith(('n2_', 'n4_')) or t == 'h_gie_b1_spare'}
FIT_THERMAL22 = list(f21.FIT_THERMAL) + [(t, None) for t in x22.DEV_TAGS]          # prereg §1: 16 + 20 = 36
EFFNET_DEV = [t for t in x22.DEV_TAGS if t in EFFNET]                              # N2 8 + N4 4 = 12 (V22-M g_m)
NM_SKIN = dict(maxiter=1500, xatol=1e-4, fatol=1e-9)
NM_AP = dict(maxiter=800, xatol=1e-4, fatol=1e-9)
NM_GM = dict(maxiter=600, xatol=1e-4, fatol=1e-9)
TAU_A_GRID = (30.0, 50.0, 80.0, 120.0)
SKIN_KEYS = ('G_f', 'G_s', 'tau_s', 'c_f', 'c_s', 'k_b')
N_PARAMS = {'A': 22, 'M': 24}
N1_RUNS = [('out_1005n', f'{c}_b{b}') for c in ('NA', 'NB', 'GA', 'GB') for b in (1, 2)]
N1_PAIRS = [('out_1005n', f'pair_{r}_b{b}') for r in ('N', 'G') for b in (1, 2)]
N2_RUNS = [('out_1005e', f'{c}_b{b}') for c in ('NAe', 'NBe', 'GAe', 'GBe') for b in (1, 2)]
N2_PAIRS = [('out_1005e', f'pair_{r}_b{b}') for r in ('NPU', 'GPU') for b in (1, 2)]
SUPP_RUNS = [('out_1005n', 'NB_b2_re'), ('out_1005n', 'GB_b2_re')]
SUPP_PAIRS = [('out_1005n', 'pair_N_b2s'), ('out_1005n', 'pair_G_b2s')]
N4_JUDGE = {'n4_gie_b1': 'GIe_b1', 'n4_gie_b2': 'GIe_b2', 'n4_nie_b1': 'NIe_b1', 'n4_nie_b2': 'NIe_b2', 'h_gie_b1_spare': 'GIe_b1_spare'}


def log(*a):
    print(time.strftime('%H:%M:%S'), *a, flush=True)


# ============================================================ data (same code as fit_throttle_v21.series / schedule_of, prefix trace_v22_)
def rows1_22(tag, seg=None):
    rr = list(csv.DictReader(open(os.path.join(DATA, f'trace_v22_{tag}.csv'), encoding='utf-8')))
    return rr if seg is None else [r for r in rr if int(r['seg']) == seg]


def _duty1_22(tag):
    return {i for i, s in enumerate(MAN22[tag]['segments']) if s.get('duty') == 1}


def series22(tag, seg=None):
    fl = f21.fl
    rr = rows1_22(tag, seg)
    d1segs = _duty1_22(tag)
    P, SK, AP, BT, segs, act = [], [], [], [], [], []
    lp = lsk = lap = lbt = None
    for r in rr:
        p, sk, ap, bt = fl(r['power_w']), fl(r['SKIN']), fl(r['AP']), fl(r['BAT'])
        lp = p if p is not None else lp; lsk = sk if sk is not None else lsk; lap = ap if ap is not None else lap; lbt = bt if bt is not None else lbt
        P.append(lp); SK.append(lsk); AP.append(lap); BT.append(lbt); segs.append(int(r['seg']))
        act.append(int(r['n_inf']) > 0 and int(r['seg']) not in d1segs)
    for arr in (P, SK, AP, BT):
        first = next((x for x in arr if x is not None), None)
        for i in range(len(arr)):
            if arr[i] is None:
                arr[i] = first
            else:
                break
    return dict(P=np.array(P, float), SKIN=np.array(SK, float), AP=np.array(AP, float), seg=np.array(segs), active=act,
                T_start=SK[0], A0=AP[0] - SK[0], B0=BT[0], res=[RES_OF22[tag][g] for g in segs])


def series_any(tag, seg=None):
    return series22(tag, seg) if tag in x22.RUNS else f21.series(tag, seg)


def schedule22(tag):
    m = MAN22[tag]
    d1segs = _duty1_22(tag)
    sch = []
    for i, seg in enumerate(m['segments']):
        if i > 0:
            sch.append((f't{i}', None, None, m['transitions'][i - 1]['duration_s']))
        flags = [False] * len(rows1_22(tag, i)) if i in d1segs else [int(r['n_inf']) > 0 for r in rows1_22(tag, i)]
        sch.append((i, RES_OF22[tag][i], flags, seg['duration_s']))
    return sch


# ============================================================ Stage A (V22-A) — fit_throttle_v21.fit_thermal arithmetic, v2.1 start
def _tp_skin(x, tp21, d_ref):
    G_f, G_s, tau_s, c_f, c_s, k_b = x
    return dict(tau_f=f1.TAU_F, G_f=G_f, G_s=G_s, tau_s=tau_s, tau_a=tp21['tau_a'], G_a=dict(tp21['G_a']), P_idle=f1.P_IDLE,
                c_f=c_f, c_s=c_s, c_a=tp21['c_a'], k_b=k_b, d_ref=d_ref)


def skin_mse(tp, runs):
    return float(np.mean([np.mean((np.array(tv21.thermal_series(tp, S['P'], S['res'], S['T_start'], S['A0'], S['B0'])[0]) - S['SKIN']) ** 2)
                          for S in runs]))


def ap_mse(tp, runs):
    return float(np.mean([np.mean((np.array(tv21.thermal_series(tp, S['P'], S['res'], S['T_start'], S['A0'], S['B0'])[1]) - S['AP']) ** 2)
                          for S in runs]))


def skin_obj(x, runs, tp21, d_ref):
    G_f, G_s, tau_s, c_f, c_s, k_b = x
    if not (0 <= G_f <= 5 and 0 <= G_s <= 5 and 60 <= tau_s <= 3000 and 1 <= c_f <= 20 and 1 <= c_s <= 20 and -5 <= k_b <= 10):
        return 1e6
    return skin_mse(_tp_skin(x, tp21, d_ref), runs)


def ap_obj(x, runs, tp, tau_a):
    g1, g2, g3, c_a = x
    if not (0 <= g1 <= 5 and 0 <= g2 <= 5 and 0 <= g3 <= 5 and 1 <= c_a <= 20):
        return 1e6
    return ap_mse(dict(tp, tau_a=tau_a, G_a={'GPU': g1, 'NPU': g2, 'CPU4': g3}, c_a=c_a), runs)


def _job_skin(args):
    runs, tp21, d_ref, x0 = args
    r = minimize(skin_obj, np.array(x0, float), args=(runs, tp21, d_ref), method='Nelder-Mead', options=NM_SKIN)
    return dict(fun=float(r.fun), x=list(map(float, r.x)), nit=int(r.nit), nfev=int(r.nfev), x0=list(map(float, x0)))


def _job_ap(args):
    runs, tp, tau_a, x0 = args
    r = minimize(ap_obj, np.array(x0, float), args=(runs, tp, tau_a), method='Nelder-Mead', options=NM_AP)
    return dict(fun=float(r.fun), tau_a=tau_a, x=list(map(float, r.x)), nit=int(r.nit), nfev=int(r.nfev))


def stage_a(runs, tp21, pool):
    d_ref = f21.d_ref_of(runs)
    x0a = [float(tp21[k]) for k in SKIN_KEYS]
    x0b = x0a[:5] + [0.0]
    res = list(pool.map(_job_skin, [(runs, tp21, d_ref, x0a), (runs, tp21, d_ref, x0b)]))
    best = res[0] if res[0]['fun'] <= res[1]['fun'] else res[1]           # tie -> first start (prereg §3.1)
    tp = _tp_skin(best['x'], tp21, d_ref)
    x0ap = [tp21['G_a']['GPU'], tp21['G_a']['NPU'], tp21['G_a']['CPU4'], tp21['c_a']]
    ra = list(pool.map(_job_ap, [(runs, tp, ta, x0ap) for ta in TAU_A_GRID]))
    besta = min(ra, key=lambda r: (r['fun'], TAU_A_GRID.index(r['tau_a'])))   # first minimum in grid order (= v2.1 loop)
    tp['tau_a'] = besta['tau_a']
    tp['G_a'] = dict(zip(('GPU', 'NPU', 'CPU4'), besta['x'][:3]))
    tp['c_a'] = besta['x'][3]
    tp['source'] = ('stage A v2.2 (V22-A): SKIN NM (G_f,G_s,tau_s,c_f,c_s,k_b) from v2.1 values (+ k_b 0 start); d_ref = median(SKIN0-BAT0) '
                    'of the 36 thermal dev runs; AP tau_a grid {30,50,80,120} x NM (G_a x3, c_a) from v2.1 values')
    info = dict(d_ref=d_ref, skin_starts=res, chosen_start=('v2.1 values' if best is res[0] else 'k_b = 0'), skin_obj=best['fun'],
                ap_grid=[dict(tau_a=r['tau_a'], fun=r['fun'], nit=r['nit']) for r in ra], ap_obj=besta['fun'])
    return tp, info


# ============================================================ V22-M — g_m on EffNet closed loop
def closed_err(params, tag, model):
    S = series_any(tag)
    sch = schedule22(tag) if tag in x22.RUNS else f21.schedule_of(tag)
    rows = tv22.simulate(params, sch, S['T_start'], S['A0'], S['B0'], model=model)
    e2, e1 = [], []
    for i in sorted(set(int(v) for v in S['seg'])):
        m = np.array([r['skin'] for r in rows if r['seg'] == i])
        meas = S['SKIN'][S['seg'] == i]
        n = min(len(m), len(meas))
        d = m[:n] - meas[:n]
        e2.extend((d ** 2).tolist()); e1.extend(np.abs(d).tolist())
    return float(np.mean(e2)), float(np.mean(e1)), rows


def gm_obj(x, base):
    gN, gG = x
    if not (0.2 <= gN <= 5 and 0.2 <= gG <= 5):
        return 1e6
    p = dict(base, thermal=dict(base['thermal'], g_m={'NPU': float(gN), 'GPU': float(gG)}))
    return float(np.mean([closed_err(p, t, 'effnet')[0] for t in EFFNET_DEV]))


def fit_gm(base):
    r = minimize(gm_obj, np.array([1.0, 1.0]), args=(base,), method='Nelder-Mead', options=NM_GM)
    return dict(g_m={'NPU': float(r.x[0]), 'GPU': float(r.x[1])}, fun=float(r.fun), nit=int(r.nit), nfev=int(r.nfev),
                fun_at_1=float(gm_obj([1.0, 1.0], base)))


# ============================================================ params
def v21_params(engine='CM'):
    return tv22.load_params('throttle_v21_', engine)


def with_thermal(base, tp):
    return dict(base, thermal={k: v for k, v in tp.items() if k != 'source'})


# ============================================================ selection score (prereg §4)
def load_j(od, name):
    return json.load(open(os.path.join(SIM, od, f'{name}.json'), encoding='utf-8'))


def columns_of(runs, pairs):
    cols = {round(float(j['start_skin']), 3) for j in runs if j.get('start_skin') is not None}
    for p in pairs:
        sa, sb = p['a']['start_skin'], p['b']['start_skin']
        if sa is not None and sb is not None:
            cols.add(round((sa + sb) / 2.0, 3))
    return tuple(sorted(cols))


def predict_night(JE, params, d_ref, night, columns, simfn, label):
    if night == 'N2':
        cells, pairs_def, R0, effnet = pn5e.CELLS_E, pn5e.PAIRS_E, pn5e.R0_EFFNET, True
    else:
        cells, pairs_def, R0, effnet = pn5e.CELLS_M, pn5e.PAIRS_M, pn5e.r0_mobilenet(), False
    old = pn5e.COLUMNS
    pn5e.COLUMNS = tuple(columns)           # the driver's column loop, with the actual-start columns (prereg §4)
    try:
        c, pr, rs = pn5e.predict(JE, simfn, {None: (params, lambda T0: dict(B0=T0 - d_ref))}, R0, cells, pairs_def, effnet)
    finally:
        pn5e.COLUMNS = old
    return dict(model=label, night=night, columns=list(columns), A0=pn5e.A0, BAT0_rule=f'BAT0 = SKIN0 - d_ref ({d_ref:.4f})', R0=R0,
                cells=c, pairs=pr, resources=rs, rule='prereg v2.2 §4 — actual start SKIN columns (run starts ∪ pair means), A0 -1.0')


def count_cmp(cmp_var):
    out = dict(runs_ok=0, runs_judged=0, runs_unknown=0, runs_unsupported=0, pairs_ok=0, pairs_judged=0, pairs_unsupported=0,
               res_ok=0, res_judged=0, per_run={}, per_pair={}, resources={})
    for r in cmp_var['runs']:
        key = f"{r['cell']}_b{r['block']}"
        if not r.get('supported', True) or not r.get('rows'):
            out['runs_unsupported'] += 1; out['per_run'][key] = 'unsupported/열 없음'
            continue
        ok = sum(1 for x in r['rows'] if x['verdict'] == '맞음')
        jd = sum(1 for x in r['rows'] if x['verdict'] in ('맞음', '틀림'))
        out['runs_ok'] += ok; out['runs_judged'] += jd
        out['runs_unknown'] += sum(1 for x in r['rows'] if x['verdict'] == '미확인')
        out['per_run'][key] = f'{ok}/{jd}'
    for p in cmp_var['pairs']:
        key = f"{p['resource']}_b{p['block']}"
        if not p.get('supported', True) or not p.get('rows'):
            out['pairs_unsupported'] += 1; out['per_pair'][key] = 'unsupported/열 없음'
            continue
        ok = sum(1 for x in p['rows'] if x['verdict'] == '맞음')
        jd = sum(1 for x in p['rows'] if x['verdict'] in ('맞음', '틀림'))
        out['pairs_ok'] += ok; out['pairs_judged'] += jd
        out['per_pair'][key] = f'{ok}/{jd}'
    for res, x in cmp_var['resources'].items():
        v = x.get('verdict')
        out['resources'][res] = dict(verdict=v, predicted=x.get('predicted'), measured=x.get('measured'))
        if v in ('맞음', '틀림'):
            out['res_judged'] += 1
            out['res_ok'] += int(v == '맞음')
    out['total_ok'] = out['runs_ok'] + out['pairs_ok'] + out['res_ok']
    out['total_judged'] = out['runs_judged'] + out['pairs_judged'] + out['res_judged']
    return out


def score_model(JE, params, d_ref, simfn_of, label, save_prefix=None):
    """simfn_of(night) -> sim function with the predict_night_1005e signature."""
    res = {}
    for night, rl, pl in (('N1', N1_RUNS, N1_PAIRS), ('N2', N2_RUNS, N2_PAIRS)):
        runs = [load_j(*x) for x in rl]
        pairs = [load_j(*x) for x in pl]
        cols = columns_of(runs, pairs)
        pred = predict_night(JE, params, d_ref, night, cols, simfn_of(night), label)
        if save_prefix:
            json.dump(pred, open(os.path.join(OUT, f'{save_prefix}_{night}.json'), 'w', encoding='utf-8'), indent=1, ensure_ascii=False, default=str)
        cv = JE.N5.cmp_one(pred, runs, pairs, label)['variants']['(단일)']
        res[night] = count_cmp(cv)
        res[night]['columns'] = list(cols)
    res['total_ok'] = res['N1']['total_ok'] + res['N2']['total_ok']
    res['total_judged'] = res['N1']['total_judged'] + res['N2']['total_judged']
    return res


def counting_check(JE):
    """Prereg §4 check: frozen night_1005e_prediction_v21.json (columns 29.5/30.5) through the same cmp_one + count
    vs the stored cmp_1005e.json — must give the G1 table (N2 resource 1/2 · pair rows 7/16)."""
    runs = [load_j(*x) for x in N2_RUNS]
    pairs = [load_j(*x) for x in N2_PAIRS]
    pred = json.load(open(os.path.join(OUT, 'night_1005e_prediction_v21.json'), encoding='utf-8'))
    mine = count_cmp(JE.N5.cmp_one(pred, runs, pairs, 'v21')['variants']['(단일)'])
    stored = count_cmp(json.load(open(os.path.join(SIM, 'out_1005e', 'cmp_1005e.json'), encoding='utf-8'))['results']['v21']['variants']['(단일)'])
    keys = ('runs_ok', 'runs_judged', 'pairs_ok', 'pairs_judged', 'res_ok', 'res_judged')
    return dict(recount={k: mine[k] for k in keys}, stored={k: stored[k] for k in keys}, same=all(mine[k] == stored[k] for k in keys),
                g1_table=dict(pairs_ok=7, pairs_judged=16, res_ok=1, res_judged=2),
                g1_match=(mine['pairs_ok'] == 7 and mine['pairs_judged'] == 16 and mine['res_ok'] == 1 and mine['res_judged'] == 2))


def sim_v21_fn(night):
    return tv21.simulate


def sim_v22_fn(night):
    model = 'effnet' if night == 'N2' else 'mobilenet'
    return lambda p, sch, T0, A0, B0=None: tv22.simulate(p, sch, T0, A0, B0, model=model)


# ============================================================ reports (not used for selection)
def n4_report(params, model_of=lambda t: 'effnet'):
    out = {}
    for tag, jn in N4_JUDGE.items():
        if tag.startswith('h_'):
            continue
        out[tag] = _n4_one(params, tag, jn, model_of(tag))
    return out


def _n4_one(params, tag, jn, model):
    j = load_j('out_1005r', jn)
    err2, err1, rows = closed_err(params, tag, model)
    gpu = x22.RUNS[tag][2] == 'GPU'
    hm = f21.heat_metrics(rows, 1)
    im = f21.idle_metrics(rows, 1.10 if gpu else 1.06, 26 if gpu else 14)
    t = {x['t']: x for x in j['rest']['temps']}
    meas = dict(step1_s=j['heat'].get('step1_s'), onset_1_1_s=j['heat'].get('onset_1_1_s'), retighten_s=j['reheat'].get('retighten_s'),
                dskin=round(t[299]['SKIN'] - t[0]['SKIN'], 3), dap=round(t[299]['AP'] - t[0]['AP'], 3))
    model_m = dict(step1_s=hm['step1_s'], onset_1_1_s=hm['onset_1_1_s'], retighten_s=im['retighten_s'], dskin=round(im['dskin'], 3), dap=round(im['dap'], 3))
    return dict(model=model_m, measured=meas, closed_skin_mse=err2, closed_skin_mae=err1,
                retighten_within_10s=(meas['retighten_s'] is not None and model_m['retighten_s'] is not None
                                      and abs(model_m['retighten_s'] - meas['retighten_s']) <= 10),
                dskin_within_0_5=abs(model_m['dskin'] - meas['dskin']) <= 0.5)


def items19(params_cm, params_int):
    r = f21.evaluate(params_cm, params_int, f21.sim_v21)
    return dict(count=r['checklist_pass_count'], items=r['checklist_pass_items'], runs21=r['runs21'],
                checklist={k: {kk: vv for kk, vv in v.items() if kk in ('pass',)} for k, v in r['checklist'].items()})


# ============================================================ main
def main_fit(a):
    t0 = time.time()
    tp21 = json.load(open(os.path.join(PROFILES, 'throttle_v21_thermal.json'), encoding='utf-8'))
    log('loading', len(FIT_THERMAL22), 'thermal dev runs')
    runs = [series_any(t, s) for t, s in FIT_THERMAL22]
    tp21_th = {k: tp21[k] for k in tv22.THERMAL_KEYS}
    base_v21 = dict(skin_mse=skin_mse(tp21_th, runs), ap_mse=ap_mse(tp21_th, runs))
    log('v2.1 thermal on the 36 runs', base_v21)
    results = dict(model='v2.2', prereg='sim/스로틀모형_사전등록_v22.md (commit 9056685)', fit_runs=[f'{t} s{"all" if s is None else s}' for t, s in FIT_THERMAL22],
                   v21_thermal_on_dev36=base_v21, forms={}, timing={})
    JE, jsha = pn5e.load_judge()
    results['judge'] = dict(night1005e_judge=jsha, night1005_judge=pn5e._sha(JE._N5_PATH))
    chk = counting_check(JE)
    results['counting_check'] = chk
    log('counting check', chk)
    if not (chk['same'] and chk['g1_match']):
        log('COUNTING CHECK FAILED — stop (prereg §4)')
        json.dump(results, open(os.path.join(OUT, f'throttle_fit_v22{a.tag}.json'), 'w', encoding='utf-8'), indent=1, ensure_ascii=False, default=str)
        return 2
    # v2.1 selection score, same way
    p21 = v21_params('CM')
    results['score_v21'] = score_model(JE, p21, p21['thermal']['d_ref'], sim_v21_fn, 'v2.1 c6a7da2 (same counting)', save_prefix='v22_score_pred_v21')
    log('score v2.1', results['score_v21']['total_ok'], '/', results['score_v21']['total_judged'])
    tpA = None
    with ProcessPoolExecutor(max_workers=max(2, min(6, (os.cpu_count() or 4) - 2))) as pool:
        if 'A' in a.forms or 'M' in a.forms:
            ts = time.time()
            tpA, infoA = stage_a(runs, tp21, pool)
            results['timing']['stage_A_s'] = time.time() - ts
            log('V22-A thermal', {k: (round(v, 4) if isinstance(v, float) else v) for k, v in tpA.items() if k not in ('source',)}, infoA['skin_obj'], infoA['ap_obj'])
    pA = with_thermal(p21, tpA)
    scA = score_model(JE, pA, tpA['d_ref'], sim_v22_fn, 'v2.2 V22-A', save_prefix='v22_score_pred_A')
    log('score V22-A', scA['total_ok'], '/', scA['total_judged'])
    results['forms']['A'] = dict(thermal=tpA, stage_a=infoA, score=scA, n_params=N_PARAMS['A'])
    json.dump(results, open(os.path.join(OUT, f'throttle_fit_v22{a.tag}.json'), 'w', encoding='utf-8'), indent=1, ensure_ascii=False, default=str)
    if 'M' in a.forms:
        ts = time.time()
        gm = fit_gm(pA)
        results['timing']['g_m_s'] = time.time() - ts
        tpM = dict(tpA, g_m=gm['g_m'], source=tpA['source'] + ' + V22-M g_m (EffNet closed-loop model power, NM from (1,1) on N2 + N4)')
        pM = with_thermal(p21, tpM)
        scM = score_model(JE, pM, tpM['d_ref'], sim_v22_fn, 'v2.2 V22-M', save_prefix='v22_score_pred_M')
        log('V22-M g_m', gm, 'score', scM['total_ok'], '/', scM['total_judged'])
        results['forms']['M'] = dict(thermal=tpM, g_m_fit=gm, score=scM, n_params=N_PARAMS['M'])
        json.dump(results, open(os.path.join(OUT, f'throttle_fit_v22{a.tag}.json'), 'w', encoding='utf-8'), indent=1, ensure_ascii=False, default=str)
    # adoption (prereg §4): most "맞음" -> fewer params (A) on tie
    order = {'A': 0, 'M': 1}
    adopt = max(results['forms'], key=lambda f: (results['forms'][f]['score']['total_ok'], -results['forms'][f]['n_params'], -order[f]))
    best = results['forms'][adopt]['score']['total_ok']
    results['adopted'] = adopt
    results['v22_status'] = 'v2.2' if best > results['score_v21']['total_ok'] else 'v2.2 개선 없음'
    results['adoption_rule'] = ('선택 점수 (N1 + N2 cmp 맞음 수) 최다 → 동률이면 파라미터 적은 쪽 (V22-A); 최선 ≤ v2.1 (같은 방식) 이면 "v2.2 개선 없음" — '
                                '그래도 주 모형 = v2.2 최선 형태 (G1 §3-4)')
    log('adopted', adopt, results['v22_status'], best, 'vs v2.1', results['score_v21']['total_ok'])
    # reports (not used for selection)
    ts = time.time()
    pAd = with_thermal(p21, results['forms'][adopt]['thermal'])
    results['n4_report'] = {f: n4_report(with_thermal(p21, results['forms'][f]['thermal'])) for f in results['forms']}
    results['n4_report_v21'] = n4_report(p21)
    log('N4 report done')
    if not a.skip19:
        pcm, pint = with_thermal(v21_params('CM'), tpA), with_thermal(v21_params('INT'), tpA)
        results['items19_v22A'] = items19(pcm, pint)
        log('19 items V22-A', results['items19_v22A']['count'], results['items19_v22A']['items'])
        results['items19_v21_recount'] = items19(v21_params('CM'), v21_params('INT'))
        log('19 items v2.1 recount', results['items19_v21_recount']['count'], results['items19_v21_recount']['items'])
    results['timing']['reports_s'] = time.time() - ts
    results['timing']['total_s'] = time.time() - t0
    json.dump(results, open(os.path.join(OUT, f'throttle_fit_v22{a.tag}.json'), 'w', encoding='utf-8'), indent=1, ensure_ascii=False, default=str)
    if a.write_profiles:
        write_profiles(results, pAd)
    log('done', round(time.time() - t0), 's')
    return 0


def write_profiles(results, pAd):
    adopt = results['adopted']
    tp = results['forms'][adopt]['thermal']
    json.dump(dict(form=f'V22-{adopt}', **tp, fit_runs=results['fit_runs'], score=results['forms'][adopt]['score']['total_ok'],
                   score_v21=results['score_v21']['total_ok'], v22_status=results['v22_status'],
                   status='measured-fit (v2.2: thermal block refit on v2.1 dev + N1 + N2 + N4; controllers/power/R0 = v2.1 c6a7da2)'),
              open(os.path.join(PROFILES, 'throttle_v22_thermal.json'), 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
    for fn in ('GPU_compiledmodel', 'GPU_interpreter', 'NPU', 'CPU4_interpreter'):
        d = json.load(open(os.path.join(PROFILES, f'throttle_v21_{fn}.json'), encoding='utf-8'))
        d['form'] = f'V22-{adopt} (controller = v2.1 V21-Ht r1 unchanged)'
        d['source'] = 'copied from profiles/throttle_v21_' + fn + '.json (c6a7da2) — v2.2 changes the thermal block only'
        json.dump(d, open(os.path.join(PROFILES, f'throttle_v22_{fn}.json'), 'w', encoding='utf-8'), indent=1, ensure_ascii=False, default=str)
    log('wrote profiles V22-' + adopt)


def main_holdout(a):
    """G1 §4 — after the fix commit. Fixed profiles only."""
    JE, jsha = pn5e.load_judge()
    p22 = tv22.load_params('throttle_v22_', 'CM')
    runs = [load_j(*x) for x in SUPP_RUNS]
    pairs = [load_j(*x) for x in SUPP_PAIRS]
    cols = columns_of(runs, pairs)
    pred = predict_night(JE, p22, p22['thermal']['d_ref'], 'N1', cols, sim_v22_fn('N1'), 'v2.2 fixed (profiles/throttle_v22_*)')
    json.dump(pred, open(os.path.join(OUT, 'v22_weak_holdout_prediction_N1supp.json'), 'w', encoding='utf-8'), indent=1, ensure_ascii=False, default=str)
    cv = JE.N5.cmp_one(pred, runs, pairs, 'v22')['variants']['(단일)']
    c = count_cmp(cv)
    passed = c['pairs_ok'] >= 5 and c['runs_ok'] * 2 > c['runs_judged']
    stored = json.load(open(os.path.join(SIM, 'out_1005n', 'cmp_1005n_supp.json'), encoding='utf-8'))
    others = {}
    for tag, rr in stored['results'].items():
        for var, vo in rr['variants'].items():
            sub = dict(runs=[r for r in vo['runs'] if f"{r['cell']}_b{r['block']}" in ('NB_b2', 'GB_b2') and _is_supp(r, runs)],
                       pairs=[p for p in vo['pairs'] if _is_supp_pair(p, pairs)], resources={})
            others[f'{tag} {var}'] = count_cmp(sub)
    spare = _n4_one(p22, 'h_gie_b1_spare', 'GIe_b1_spare', 'effnet')
    out = dict(rule='G1 §4: 보충 쌍 차이 8 중 ≥ 5 맞음 그리고 보충 런 2개 런 항목 맞음 과반 → 약한 홀드아웃 통과', columns=list(cols),
               v22=c, v22_pass=passed, label='약한 홀드아웃 통과' if passed else '약한 홀드아웃 실패',
               stored_cmp_1005n_supp=others, gie_b1_spare=spare, judge=jsha,
               profiles={fn: pn5e._sha(os.path.join(PROFILES, f'throttle_v22_{fn}.json')) for fn in ('thermal', 'NPU', 'GPU_compiledmodel')})
    json.dump(out, open(os.path.join(OUT, 'v22_weak_holdout.json'), 'w', encoding='utf-8'), indent=1, ensure_ascii=False, default=str)
    log('weak holdout', out['label'], 'pairs', c['pairs_ok'], '/', c['pairs_judged'], 'runs', c['runs_ok'], '/', c['runs_judged'])
    return 0


def _is_supp(r, runs):
    return any(abs((r.get('start_skin') or -99) - j['start_skin']) < 1e-9 and r['cell'] == j['cell'] and r['block'] == j['block'] for j in runs)


def _is_supp_pair(p, pairs):
    return any(p['resource'] == q['resource'] and p['block'] == q['block'] for q in pairs)


def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument('--forms', nargs='*', default=['A', 'M'])
    ap.add_argument('--write-profiles', action='store_true')
    ap.add_argument('--holdout', action='store_true')
    ap.add_argument('--skip19', action='store_true')
    ap.add_argument('--tag', default='')
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    return main_holdout(a) if a.holdout else main_fit(a)


if __name__ == '__main__':
    sys.exit(main())
