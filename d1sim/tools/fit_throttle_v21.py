"""fit_throttle_v21.py — fit throttle model v2.1 (d1sim/throttle_v21.py) and run the pre-registered 19-item checklist.

Pre-registration: sim/스로틀모형_사전등록_v21.md (mirror d1sim/docs/, commit 3f8b6e6 — before any form fit).
Deterministic (fixed Nelder-Mead starts, no RNG). Reads trace_v1_* (v1 tags), trace_v2_* (10/3 tags), trace_v21_* (10/4·10/5 tags).
Writes d1sim/out/throttle_fit_v21.json and, with --write-profiles, d1sim/profiles/throttle_v21_*.json.
v0/v1/v2 code and outputs are not modified; fit_throttle_v1/v2 are imported for their metric helpers only.

Stages (prereg v2.1 §3): A thermal (v2 block from v2 values + body initial condition k_b) · B controllers on measured sensor + duty
(+ measured power for V21-F) · C closed loop -> 19 items (①~⑦ ⑨~⑬ = v2 definitions, ⑭~⑳ = prereg v2.1 §4).
v2 (42338e7, theta 0.3 / 0.75) is re-counted on the same 19 items with its frozen profiles and unmodified code.

  py d1sim/tools/fit_throttle_v21.py [--forms Ht F] [--write-profiles]
"""
from __future__ import annotations

import argparse
import csv
import itertools
import json
import os
import statistics
import sys
import time

import numpy as np
from scipy.optimize import minimize

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, ROOT)
from d1sim import throttle_v2 as tv2  # noqa: E402
from d1sim import throttle_v21 as tv21  # noqa: E402
from d1sim.tools import fit_throttle_v1 as f1  # noqa: E402
from d1sim.tools import fit_throttle_v2 as f2  # noqa: E402

DATA = os.path.join(ROOT, 'd1sim', 'data')
OUT = os.path.join(ROOT, 'd1sim', 'out')
PROFILES = os.path.join(ROOT, 'd1sim', 'profiles')
MAN21 = json.load(open(os.path.join(DATA, 'trace_v21_manifest.json'), encoding='utf-8'))
V21_TAGS = {'n50p', 'g50p', 'gi300', 'ni300', 'n50p2', 'g50p2', 'ni300r2'}
RES_OF = dict(f2.RES_OF, n50p=['NPU'] * 3, n50p2=['NPU'] * 3, g50p=['GPU'] * 3, g50p2=['GPU'] * 3,
              gi300=['GPU'] * 4, ni300=['NPU'] * 4, ni300r2=['NPU'] * 4)
ENGINE_OF = dict(f2.ENGINE_OF, **{t: 'CM' for t in V21_TAGS})
P_IDLE, D_ON = f1.P_IDLE, f1.D_ON
THETA_LOW = 0.3
TAU_F_GRID = (10.0, 20.0, 40.0, 60.0)
# prereg v2.1 §1
FIT_THERMAL = [('m2_H1', 0), ('n1300', 0), ('c1p_r1', 0), ('c600_r1', 0), ('m1', None), ('m1n_a', None),
               ('m1n_b', None), ('m1g_r2', None), ('gpace', None),
               ('n50p', None), ('g50p', None), ('gi300', None), ('ni300', None), ('n50p2', None), ('g50p2', None), ('ni300r2', None)]
CTRL_FIT = {'GPU_INT': [('c1p_r1', [0]), ('m3', [0])],
            'GPU_CM': [('m2_H1', [0]), ('m1', [0, 1, 2]), ('m1g_r2', [0, 1, 2]), ('gpace', [0, 1, 2, 3]),
                       ('g50p', [0, 1, 2]), ('g50p2', [0, 1, 2]), ('gi300', [0, 1, 3])],
            'NPU': [('n1300', [0]), ('m1n_a', [0, 1, 2]), ('m1n_b', [0, 1, 2]), ('n50p', [0, 1, 2]), ('n50p2', [0, 1, 2]),
                    ('ni300', [0, 1, 3]), ('ni300r2', [0, 1, 3])]}
NPU_RESIDUE_SKIP_S = 30     # NPU segments after a transition: bins t < 30 s are not fit targets (transition residue ㉑ — not modelled)
# ⑭~⑳ measured targets [P sim/out_1004, out_1005 judge JSONs] — prereg v2.1 §4
MEAS21 = dict(
    n50p=dict(step1=370, onset=None, release=20, release_skin=37.8, release_ap=40.9, probe479_skin=36.0),
    n50p2=dict(step1=120, onset=260, release=None, p15=1.127547, probe_skin={0: 41.9, 60: 40.8, 120: 40.8, 240: 40.7, 479: 41.1}),
    g50p=dict(onset=100, r240=1.593855, release=10, release_skin=37.4, release_ap=39.6, retighten=320, retighten_skin=38.0),
    g50p2=dict(onset=30, r240=2.064491, release=None, minutes=[2.02, 1.883, 1.703, 1.684, 1.696, 1.688, 1.699, 1.749]),
    gi300=dict(retighten=20, dskin=-4.2, dap=-6.9),
    ni300=dict(retighten=40, dskin=-3.9, dap=-7.1),
    ni300r2=dict(retighten=30, dskin=-4.1, dap=-7.5),
    step1_spread=dict(low='n50p', band=('n50p2', 'ni300', 'ni300r2'), meas=370 - (120 + 130 + 140) / 3.0, tol=40.0),
)


# ============================================================ data (prefix-aware)
def fl(v):
    return None if v in ('', None) else float(v)


def prefix(tag):
    return 'trace_v21_' if tag in V21_TAGS else f2.prefix(tag)


def man(tag):
    return MAN21[tag] if tag in V21_TAGS else f2.man(tag)


def rows1(tag, seg=None):
    rr = list(csv.DictReader(open(os.path.join(DATA, f'{prefix(tag)}{tag}.csv'), encoding='utf-8')))
    return rr if seg is None else [r for r in rr if int(r['seg']) == seg]


def _duty1_segments(tag):
    return {i for i, s in enumerate(man(tag)['segments']) if s.get('duty') == 1}


def series(tag, seg=None):
    rr = rows1(tag, seg)
    d1segs = _duty1_segments(tag)
    P, SK, AP, BT, segs, act = [], [], [], [], [], []
    lp = lsk = lap = lbt = None
    for r in rr:
        p, sk, ap, bt = fl(r['power_w']), fl(r['SKIN']), fl(r['AP']), fl(r['BAT'])
        lp = p if p is not None else lp; lsk = sk if sk is not None else lsk; lap = ap if ap is not None else lap; lbt = bt if bt is not None else lbt
        P.append(lp); SK.append(lsk); AP.append(lap); BT.append(lbt); segs.append(int(r['seg']))
        act.append(int(r['n_inf']) > 0 and int(r['seg']) not in d1segs)     # prereg §2.0: d1 = idle in the 1 s grid
    for arr in (P, SK, AP, BT):
        first = next((x for x in arr if x is not None), None)
        for i in range(len(arr)):
            if arr[i] is None:
                arr[i] = first
            else:
                break
    return dict(P=np.array(P, float), SKIN=np.array(SK, float), AP=np.array(AP, float), seg=np.array(segs), active=act,
                T_start=SK[0], A0=AP[0] - SK[0], B0=BT[0], res=[RES_OF[tag][g] for g in segs])


def bins10(tag, seg):
    rr = [r for r in csv.DictReader(open(os.path.join(DATA, f'{prefix(tag)}10s_{tag}.csv'), encoding='utf-8')) if int(r['seg']) == seg]
    ref = next(r for r in rr if r['t_s'] == '-1')
    b = [(int(r['t_s']), fl(r['lat_med_ms']), int(r['n_inf']), fl(r['power_w'])) for r in rr if r['t_s'] != '-1']
    return dict(ref=fl(ref['lat_med_ms']), ref_pw=fl(ref['power_w']), bins=b, ratio=[(t, (m / fl(ref['lat_med_ms'])) if m else None) for t, m, n, pw in b])


def schedule_of(tag):
    m = man(tag)
    d1segs = _duty1_segments(tag)
    sch = []
    for i, seg in enumerate(m['segments']):
        if i > 0:
            sch.append((f't{i}', None, None, m['transitions'][i - 1]['duration_s']))
        flags = [False] * len(rows1(tag, i)) if i in d1segs else [int(r['n_inf']) > 0 for r in rows1(tag, i)]
        sch.append((i, RES_OF[tag][i], flags, seg['duration_s']))
    return sch


def sim_v21(params, sch, T, A, B):
    return tv21.simulate(params, sch, T, A, B)


def sim_v2(params, sch, T, A, B):
    return tv2.simulate(params, sch, T, A)


def closed(tag, params, sim):
    S = series(tag)
    return sim(params, schedule_of(tag), S['T_start'], S['A0'], S['B0']), S


# ============================================================ Stage A — thermal + k_b
def d_ref_of(runs):
    return float(statistics.median([S['T_start'] - S['B0'] for S in runs if S['B0'] is not None]))


def fit_thermal(runs, tp2):
    d_ref = d_ref_of(runs)

    def tp_of(x):
        G_f, G_s, tau_s, c_f, c_s, k_b = x
        return dict(tau_f=f1.TAU_F, G_f=G_f, G_s=G_s, tau_s=tau_s, tau_a=tp2['tau_a'], G_a=dict(tp2['G_a']), P_idle=P_IDLE,
                    c_f=c_f, c_s=c_s, c_a=tp2['c_a'], k_b=k_b, d_ref=d_ref)

    def obj(x):
        G_f, G_s, tau_s, c_f, c_s, k_b = x
        if not (0 <= G_f <= 5 and 0 <= G_s <= 5 and 60 <= tau_s <= 3000 and 1 <= c_f <= 20 and 1 <= c_s <= 20 and -5 <= k_b <= 10):
            return 1e6
        tp = tp_of(x)
        return float(np.mean([np.mean((np.array(tv21.thermal_series(tp, S['P'], S['res'], S['T_start'], S['A0'], S['B0'])[0]) - S['SKIN']) ** 2)
                              for S in runs]))
    x0 = [tp2['G_f'], tp2['G_s'], tp2['tau_s'], tp2['c_f'], tp2['c_s']]
    best = None
    for kb in (0.0, 1.0):
        r = minimize(obj, np.array(x0 + [kb]), method='Nelder-Mead', options=dict(maxiter=1500, xatol=1e-4, fatol=1e-9))
        if best is None or r.fun < best.fun:
            best = r
    tp = tp_of(list(map(float, best.x)))
    skin_obj = float(best.fun)
    # same objective with k_b = 0 (v2 thermal refit on the same runs) — for the ledger: what k_b alone buys
    r0 = minimize(lambda x: obj(list(x) + [0.0]), np.array(x0), method='Nelder-Mead', options=dict(maxiter=1500, xatol=1e-4, fatol=1e-9))
    best_a = None
    for tau_a in (30.0, 50.0, 80.0, 120.0):
        def obj_a(x, tau_a=tau_a):
            g1, g2, g3, c_a = x
            if not (0 <= g1 <= 5 and 0 <= g2 <= 5 and 0 <= g3 <= 5 and 1 <= c_a <= 20):
                return 1e6
            t = dict(tp, tau_a=tau_a, G_a={'GPU': g1, 'NPU': g2, 'CPU4': g3}, c_a=c_a)
            return float(np.mean([np.mean((np.array(tv21.thermal_series(t, S['P'], S['res'], S['T_start'], S['A0'], S['B0'])[1]) - S['AP']) ** 2)
                                  for S in runs]))
        r = minimize(obj_a, np.array([tp2['G_a']['GPU'], tp2['G_a']['NPU'], tp2['G_a']['CPU4'], tp2['c_a']]), method='Nelder-Mead',
                     options=dict(maxiter=800, xatol=1e-4, fatol=1e-9))
        if best_a is None or r.fun < best_a[0]:
            best_a = (float(r.fun), tau_a, list(map(float, r.x)))
    tp['tau_a'] = best_a[1]
    tp['G_a'] = dict(zip(('GPU', 'NPU', 'CPU4'), best_a[2][:3]))
    tp['c_a'] = best_a[2][3]
    tp['source'] = ('stage A v2.1: SKIN NM (G_f,G_s,tau_s,c_f,c_s,k_b) from v2 values; d_ref = median(SKIN0-BAT0) of the thermal dev runs; '
                    'AP tau_a grid {30,50,80,120} x NM (G_a x3, c_a)')
    return tp, skin_obj, best_a[0], dict(kb0_skin_obj=float(r0.fun), kb0_x=list(map(float, r0.x)), d_ref=d_ref)


def fit_thermal_res(runs, tp2, tp_r1):
    """r2 (ledger V21-Hθ-r2): G_f and G_s per resource {GPU, NPU, CPU4}, from the r1 values; then the same AP stage."""
    d_ref = d_ref_of(runs)
    R3 = ('GPU', 'NPU', 'CPU4')

    def tp_of(x):
        gf, gs = dict(zip(R3, x[0:3])), dict(zip(R3, x[3:6]))
        tau_s, c_f, c_s, k_b = x[6:10]
        return dict(tau_f=f1.TAU_F, G_f=gf, G_s=gs, tau_s=tau_s, tau_a=tp_r1['tau_a'], G_a=dict(tp_r1['G_a']), P_idle=P_IDLE,
                    c_f=c_f, c_s=c_s, c_a=tp_r1['c_a'], k_b=k_b, d_ref=d_ref)

    def obj(x):
        if not (all(0 <= v <= 6 for v in x[0:6]) and 60 <= x[6] <= 3000 and 1 <= x[7] <= 20 and 1 <= x[8] <= 20 and -5 <= x[9] <= 10):
            return 1e6
        tp = tp_of(x)
        return float(np.mean([np.mean((np.array(tv21.thermal_series(tp, S['P'], S['res'], S['T_start'], S['A0'], S['B0'])[0]) - S['SKIN']) ** 2)
                              for S in runs]))
    x0 = [tp_r1['G_f']] * 3 + [tp_r1['G_s']] * 3 + [tp_r1['tau_s'], tp_r1['c_f'], tp_r1['c_s'], tp_r1['k_b']]
    r = minimize(obj, np.array(x0), method='Nelder-Mead', options=dict(maxiter=4000, xatol=1e-4, fatol=1e-9))
    tp = tp_of(list(map(float, r.x)))
    best_a = None
    for tau_a in (30.0, 50.0, 80.0, 120.0):
        def obj_a(x, tau_a=tau_a):
            g1, g2, g3, c_a = x
            if not (0 <= g1 <= 5 and 0 <= g2 <= 5 and 0 <= g3 <= 5 and 1 <= c_a <= 20):
                return 1e6
            t = dict(tp, tau_a=tau_a, G_a={'GPU': g1, 'NPU': g2, 'CPU4': g3}, c_a=c_a)
            return float(np.mean([np.mean((np.array(tv21.thermal_series(t, S['P'], S['res'], S['T_start'], S['A0'], S['B0'])[1]) - S['AP']) ** 2)
                                  for S in runs]))
        ra = minimize(obj_a, np.array([tp_r1['G_a']['GPU'], tp_r1['G_a']['NPU'], tp_r1['G_a']['CPU4'], tp_r1['c_a']]), method='Nelder-Mead',
                      options=dict(maxiter=800, xatol=1e-4, fatol=1e-9))
        if best_a is None or ra.fun < best_a[0]:
            best_a = (float(ra.fun), tau_a, list(map(float, ra.x)))
    tp['tau_a'] = best_a[1]; tp['G_a'] = dict(zip(R3, best_a[2][:3])); tp['c_a'] = best_a[2][3]
    tp['source'] = 'stage A v2.1 r2: per-resource G_f/G_s + tau_s,c_f,c_s,k_b NM from r1 values; AP stage as r1'
    return tp, float(r.fun), best_a[0], dict(d_ref=d_ref, nm_iterations=int(r.nit))


def thermal_errors(tp, S, with_body=True):
    sk, ap = tv21.thermal_series(tp, S['P'], S['res'], S['T_start'], S['A0'], S['B0'] if with_body else None)
    sk, ap = np.array(sk), np.array(ap)
    return dict(skin_mae=float(np.mean(np.abs(sk - S['SKIN']))), ap_mae=float(np.mean(np.abs(ap - S['AP']))),
                skin_end_model=float(sk[-1]), skin_end_meas=float(S['SKIN'][-1]))


# ============================================================ Stage B — controllers on measured sensor + duty (+ power for F)
class _Th:
    pass


def ctrl_ratio_series(cp, res, S, sensor):
    c = tv21.NpuV21(cp) if res == 'NPU' else tv21.GpuV21(cp)
    u = f2.u_series(S['active'])
    th = _Th()
    T = S['AP'] if sensor == 'AP' else S['SKIN']
    out = []
    for i, (Ti, a, p) in enumerate(zip(T, S['active'], S['P'])):
        th.ap = th.skin = float(Ti)
        if res == 'NPU':
            r = c.ratio
        else:
            c.last_T = c.drv(th)
            r = c.ratio_at(c.last_T)
        out.append(r if a else None)
        c.fast_advance(1.0, max(0.0, float(p) - P_IDLE), bool(a))
        c.step(1.0, th, bool(a), scheduled=True, u=u[i])
    return out


def meas_ratio_bins(tag, segs_wanted, res):
    ref0 = bins10(tag, 0)['ref']
    out = []
    for sg in segs_wanted:
        for t, m, n, pw in bins10(tag, sg)['bins']:
            if res == 'NPU' and sg > 0 and t < NPU_RESIDUE_SKIP_S:
                continue
            out.append((sg, t, (m / ref0) if m else None))
    return out


def ctrl_obj(cp, res, sensor, fitdata):
    e = []
    for S, meas, segs_wanted in fitdata:
        rs = ctrl_ratio_series(cp, res, S, sensor)
        mb = f2.model_ratio_bins(rs, list(S['seg']), segs_wanted)
        for sg, t, m in meas:
            p = mb.get((sg, t))
            if p is not None and m is not None:
                e.append((p / m - 1) ** 2)
    return float(np.mean(e)) if e else 1e6


def _nm(obj, starts, maxiter):
    best = None
    for st in itertools.product(*starts):
        r = minimize(obj, np.array(st, float), method='Nelder-Mead', options=dict(maxiter=maxiter, xatol=1e-4, fatol=1e-9))
        if best is None or r.fun < best.fun:
            best = r
    return best


def fit_gpu(key, form, sensor):
    fitdata = [(series(tag), meas_ratio_bins(tag, segs, 'GPU'), segs) for tag, segs in CTRL_FIT[key]]
    t0 = {'SKIN': [37.2], 'AP': [41.5]}[sensor]
    if form == 'Ht':
        names = ['T_on', 'kappa', 'h', 'W', 'D']
        starts = [t0, [0.5, 2.0], [0.2], [1.2], [1.2]]
        bounds = [(30, 50), (0, 10), (0, 6), (0.05, 10), (0.2, 3)]
        taus = [None]
    else:
        names = ['T_on', 'h', 'W', 'D', 'g_F']
        starts = [[t0[0] + 0.5], [0.3], [1.2], [1.2], [0.2, 0.6]]
        bounds = [(30, 55), (0, 6), (0.05, 10), (0.2, 3), (0, 5)]
        taus = list(TAU_F_GRID)
    best = None
    for tau in taus:
        def mk(x, tau=tau):
            d = dict(sensor=sensor, form=form, d_on=D_ON, theta_low=THETA_LOW, T_d0_rule='T_d0 = T_on (v2 r3 constraint)')
            d.update(zip(names, x))
            if form == 'F':
                d['tau_F'] = tau
                d.pop('theta_low')
            return d

        def obj(x, mk=mk):
            for v, (lo, hi) in zip(x, bounds):
                if not lo <= v <= hi:
                    return 1e6
            return ctrl_obj(mk(x), 'GPU', sensor, fitdata)
        r = _nm(obj, starts, 900)
        if best is None or r.fun < best[0].fun:
            best = (r, mk)
    r, mk = best
    x = list(map(float, r.x))
    cp = mk(x)
    return cp, float(r.fun), dict(cp)


def fit_npu(form, sensor):
    fitdata = [(series(tag), meas_ratio_bins(tag, segs, 'NPU'), segs) for tag, segs in CTRL_FIT['NPU']]
    t1 = {'SKIN': 38.13, 'AP': 42.3}[sensor]
    base_starts = [[t1], [t1 + 1.76], [t1 + 3.7], [0.091], [0.035], [0.068], [0.47]]
    if form == 'Ht':
        names = ['T1', 'T2', 'T3', 'a1', 'a2', 'a3', 'h', 'kappa']
        starts = base_starts + [[0.0, 1.5]]
        bounds = [(30, 50)] * 3 + [(0, 0.5)] * 3 + [(0, 6), (0, 10)]
        taus = [None]
    else:
        names = ['T1', 'T2', 'T3', 'a1', 'a2', 'a3', 'h', 'g_F']
        starts = [[t1 + 0.5], [t1 + 2.26], [t1 + 4.2], [0.091], [0.035], [0.068], [0.47], [0.15, 0.4]]
        bounds = [(30, 55)] * 3 + [(0, 0.5)] * 3 + [(0, 6), (0, 5)]
        taus = list(TAU_F_GRID)
    best = None
    for tau in taus:
        def mk(x, tau=tau):
            d = dict(sensor=sensor, form=form, d_on=D_ON, theta_low=THETA_LOW)
            d.update(zip(names, x))
            if form == 'F':
                d['tau_F'] = tau
                d.pop('theta_low')
            return d

        def obj(x, mk=mk):
            for v, (lo, hi) in zip(x, bounds):
                if not lo <= v <= hi:
                    return 1e6
            if not (x[0] < x[1] < x[2]):
                return 1e6
            return ctrl_obj(mk(x), 'NPU', sensor, fitdata)
        r = _nm(obj, starts, 1200)
        if best is None or r.fun < best[0].fun:
            best = (r, mk)
    r, mk = best
    cp = mk(list(map(float, r.x)))
    return cp, float(r.fun), dict(cp)


# ============================================================ Stage C — closed loop + 19 items
def win_med(rows, seg, a, b):
    return f1.win_med(rows, seg, a, b)


def at(rows, seg, t):
    return next((r for r in rows if r['seg'] == seg and r['t'] == t), None)


def first_k(pr, pred, last_k, start=0):
    for k in range(start, min(last_k, len(pr) - 4) + 1):
        if all(x is not None and pred(x) for x in pr[k:k + 4]):
            return k
    return None


def heat_metrics(rows, seg):
    ref30 = win_med(rows, seg, 0, 30)
    hb = [(t, (m / ref30) if (m is not None and ref30) else None) for t, m in tv2.bins_ratio(rows, seg)]
    return dict(ref30=ref30, step1_s=f1.step1_time(hb, 1.045), onset_1_1_s=tv2.onset_time_ref(hb, 1.0),
                ratio=lambda a, b: (win_med(rows, seg, a, b) / ref30) if (ref30 and win_med(rows, seg, a, b)) else None)


def probe_metrics(rows, delta, retighten_thr=None):
    ref = win_med(rows, 0, 0, 60)
    pb = [None if m is None else m / ref for t, m in tv2.bins_ratio(rows, 2)]
    k = first_k(pb, lambda x: x <= 1 + delta, 44)
    rel = at(rows, 2, 10 * k) if k is not None else None
    out = dict(release_s=(10 * k if k is not None else None), release_skin=(rel['skin'] if rel else None), release_ap=(rel['ap'] if rel else None),
               bins=pb, p15=(statistics.median([x for x in pb[1:6] if x is not None]) if any(x is not None for x in pb[1:6]) else None),
               temps={t: (at(rows, 2, t)['skin'] if at(rows, 2, t) else None) for t in (0, 60, 120, 240, 479)},
               minutes=[(statistics.median([x for x in pb[6 * m:6 * m + 6] if x is not None]) if any(x is not None for x in pb[6 * m:6 * m + 6]) else None)
                        for m in range(8)])
    if retighten_thr is not None and k is not None:
        kk = first_k(pb, lambda x: x >= retighten_thr, 44, start=k + 1)
        rr = at(rows, 2, 10 * kk) if kk is not None else None
        out.update(retighten_s=(10 * kk if kk is not None else None), retighten_skin=(rr['skin'] if rr else None))
    else:
        out.update(retighten_s=None, retighten_skin=None)
    return out


def idle_metrics(rows, thr, last_k):
    ref = win_med(rows, 1, 0, 30)
    pb = [None if m is None else m / ref for t, m in tv2.bins_ratio(rows, 3)]
    k = first_k(pb, lambda x: x >= thr, last_k)
    r0, r299 = at(rows, 2, 0), at(rows, 2, 299)
    return dict(retighten_s=(10 * k if k is not None else None), dskin=r299['skin'] - r0['skin'], dap=r299['ap'] - r0['ap'], first_bin=pb[0] if pb else None)


def _t_ok(model, meas, tol):
    if model is None and meas is None:
        return True
    if model is None or meas is None:
        return False
    return abs(model - meas) <= tol + 1e-9


def items_new(R21):
    M = MEAS21
    it = {}
    n, m = R21['n50p'], M['n50p']
    d = dict(step1=n['heat']['step1_s'], onset=n['heat']['onset_1_1_s'], release=n['probe']['release_s'], release_skin=n['probe']['release_skin'],
             release_ap=n['probe']['release_ap'], probe479=n['probe']['temps'][479])
    d['ok'] = dict(step1=_t_ok(d['step1'], m['step1'], 20), onset=d['onset'] is None, release=_t_ok(d['release'], m['release'], 10),
                   release_skin=(d['release_skin'] is not None and abs(d['release_skin'] - m['release_skin']) <= 0.5),
                   probe479=(d['probe479'] is not None and abs(d['probe479'] - m['probe479_skin']) <= 0.5))
    d['pass'] = all(d['ok'].values()); it['⑭'] = d
    n, m = R21['n50p2'], M['n50p2']
    mae = float(np.mean([abs(n['probe']['temps'][t] - v) for t, v in m['probe_skin'].items()]))
    d = dict(step1=n['heat']['step1_s'], onset=n['heat']['onset_1_1_s'], release=n['probe']['release_s'], p15=n['probe']['p15'], probe_skin_mae=mae)
    d['ok'] = dict(step1=_t_ok(d['step1'], m['step1'], 20), onset=_t_ok(d['onset'], m['onset'], 20), release=d['release'] is None,
                   p15=(d['p15'] is not None and abs(d['p15'] - m['p15']) <= 0.03), probe_skin=mae <= 0.5)
    d['pass'] = all(d['ok'].values()); it['⑮'] = d
    n, m = R21['g50p'], M['g50p']
    d = dict(onset=n['heat']['onset_1_1_s'], r240=n['heat']['r240'], release=n['probe']['release_s'], release_skin=n['probe']['release_skin'],
             release_ap=n['probe']['release_ap'], retighten=n['probe']['retighten_s'], retighten_skin=n['probe']['retighten_skin'])
    d['ok'] = dict(onset=_t_ok(d['onset'], m['onset'], 10), r240=(d['r240'] is not None and abs(d['r240'] / m['r240'] - 1) <= 0.10),
                   release=_t_ok(d['release'], m['release'], 10),
                   release_skin=(d['release_skin'] is not None and abs(d['release_skin'] - m['release_skin']) <= 0.5),
                   retighten=_t_ok(d['retighten'], m['retighten'], 10),
                   retighten_skin=(d['retighten_skin'] is not None and abs(d['retighten_skin'] - m['retighten_skin']) <= 0.5))
    d['pass'] = all(d['ok'].values()); it['⑯'] = d
    n, m = R21['g50p2'], M['g50p2']
    d = dict(onset=n['heat']['onset_1_1_s'], r240=n['heat']['r240'], release=n['probe']['release_s'], minutes=n['probe']['minutes'])
    d['ok'] = dict(onset=_t_ok(d['onset'], m['onset'], 10), r240=(d['r240'] is not None and abs(d['r240'] / m['r240'] - 1) <= 0.10),
                   release=d['release'] is None,
                   minutes=all(x is not None and abs(x / y - 1) <= 0.10 for x, y in zip(d['minutes'], m['minutes'])))
    d['pass'] = all(d['ok'].values()); it['⑰'] = d
    n, m = R21['gi300'], M['gi300']
    d = dict(retighten=n['idle']['retighten_s'], dskin=n['idle']['dskin'], dap=n['idle']['dap'])
    d['ok'] = dict(retighten=_t_ok(d['retighten'], m['retighten'], 10), dskin=abs(d['dskin'] - m['dskin']) <= 0.5, dap=abs(d['dap'] - m['dap']) <= 0.5)
    d['pass'] = all(d['ok'].values()); it['⑱'] = d
    d = {}
    for t in ('ni300', 'ni300r2'):
        n, m = R21[t], M[t]
        x = dict(retighten=n['idle']['retighten_s'], dskin=n['idle']['dskin'], dap=n['idle']['dap'])
        x['ok'] = dict(retighten=_t_ok(x['retighten'], m['retighten'], 10), dskin=abs(x['dskin'] - m['dskin']) <= 0.5, dap=abs(x['dap'] - m['dap']) <= 0.5)
        d[t] = x
    d['pass'] = all(all(d[t]['ok'].values()) for t in ('ni300', 'ni300r2')); it['⑲'] = d
    sp = M['step1_spread']
    s_low = R21[sp['low']]['heat']['step1_s']
    s_band = [R21[t]['heat']['step1_s'] for t in sp['band']]
    diff = (s_low - float(np.mean(s_band))) if (s_low is not None and all(x is not None for x in s_band)) else None
    it['⑳'] = dict(step1_low=s_low, step1_band=s_band, diff_model=diff, diff_meas=sp['meas'],
                   **{'pass': diff is not None and abs(diff - sp['meas']) <= sp['tol'] + 1e-9})
    return it


def m2_metrics(grp, params_cm, judge, sim):
    v, first, second = {}, {}, {}
    for arm in ('C1', 'H1', 'H2', 'C2'):
        rows, S = closed(f'{grp}_{arm}', params_cm, sim)
        v[arm] = win_med(rows, 1, 0, 60); first[arm] = win_med(rows, 1, 0, 10); second[arm] = win_med(rows, 1, 10, 20)
    cmean = (v['C1'] + v['C2']) / 2
    vm = judge['v_ms']; cmean_meas = (vm['C1'] + vm['C2']) / 2
    meas_rel = {a: vm[a] / cmean_meas for a in ('H1', 'H2')}
    tol = max(2 * judge['s_C'], 0.01)
    lo, hi = min(meas_rel.values()) - tol, max(meas_rel.values()) + tol
    pred_rel = {a: v[a] / cmean for a in ('H1', 'H2')}
    first_rel = {a: first[a] / cmean for a in ('H1', 'H2')}; second_rel = {a: second[a] / cmean for a in ('H1', 'H2')}
    dir_ok = all(first_rel[a] < second_rel[a] for a in first_rel) if grp == 'm2' else all(first_rel[a] <= 1.10 for a in first_rel)
    return dict(victim_rel_pred=pred_rel, victim_rel_meas=meas_rel, range=[lo, hi], in_range=all(lo <= pred_rel[a] <= hi for a in pred_rel),
                first10_rel_pred=first_rel, bin_10_20_rel_pred=second_rel, direction_ok=dir_ok)


def sixty_s(params, sim):
    out = {}
    for res in ('GPU', 'NPU', 'CPU4'):
        rows = sim(params, [(0, res, True, 60)], 30.3, -1.0, None)
        b = tv2.bins_ratio(rows, 0)
        first30 = float(np.median([r['ratio'] for r in rows[:30]]))
        out[res] = dict(last10_over_first30_pct=100 * (b[5][1] / first30 - 1), skin_end=rows[-1]['skin'])
    return out


def evaluate(pcm, pint, sim):
    """19 items for one parameter set (CompiledModel / Interpreter params) through `sim`."""
    res = dict(runs={}, checklist={})
    for tag in ('c1p_r1', 'c1p_r2', 'c1a', 'm3', 'm2_H1', 'm2_H2', 'm1', 'n1300', 'm2r_H1', 'm2r_H2', 'c600_r1', 'c600_r2', 'm1n_a', 'm1n_b', 'm1g_r2', 'gpace'):
        params = pcm if ENGINE_OF[tag] == 'CM' else pint
        rows, S = closed(tag, params, sim)
        seg = 1 if tag in ('m1', 'm1n_a', 'm1n_b', 'm1g_r2', 'gpace') else 0
        B = bins10(tag, seg)
        L = man(tag)['segments'][seg]['duration_s']
        r0 = RES_OF[tag][seg]
        m = f1.gpu_metrics(rows, seg, B, S, L) if r0 == 'GPU' else (f1.npu_metrics(rows, seg, B, S, L) if r0 == 'NPU' else f1.cpu_metrics(rows, seg, B, S, L))
        m.update(f1.temps_err(rows, S))
        if tag == 'm1':
            m['m1'] = f1.m1_metrics(rows)
            m['recovery'] = f2.recovery_metrics(rows, 2, 0.10, times=(0, 60, 120, 180, 240, 290))
        if tag == 'm1g_r2':
            m['recovery'] = f2.recovery_metrics(rows, 2, 0.10, times=(0, 60, 120, 180, 240, 290))
        if tag in ('m1n_a', 'm1n_b'):
            m['recovery'] = f2.recovery_metrics(rows, 2, 0.03)
            m['third_level_s'] = f2.third_level(rows, 1)
        if tag == 'gpace':
            m['retighten'] = f2.retighten_metrics(rows)
        if tag == 'c1a':
            sk420 = next(r['skin'] for r in rows if r['t'] == 420); sk1200 = next(r['skin'] for r in rows if r['t'] == 1200)
            m['skin_rise_420_1200_model'] = sk1200 - sk420; m['skin_rise_420_1200_meas'] = float(S['SKIN'][1200] - S['SKIN'][420])
        res['runs'][tag] = m
    judges = {'m2': json.load(open(os.path.join(f1.SIM, 'out_1002', 'M2_npu_judge.json'), encoding='utf-8')),
              'm2r': json.load(open(os.path.join(f1.SIM, 'out_1002', 'M2r_gpu_judge.json'), encoding='utf-8'))}
    res['coupling'] = {g: m2_metrics(g, pcm, judges[g], sim) for g in ('m2', 'm2r')}
    res['sixty_s'] = sixty_s(pcm, sim)
    R = res['runs']
    ok_on = f2.ok_on
    c1_runs = ['c1a', 'm2_H1', 'm2_H2', 'm1']
    c1 = dict(onset=all(ok_on(R[t]['onset_err_s'], 10) for t in c1_runs),
              plateau=all(ok_on(R[t].get('ratio_540_600_err_pct'), 10) for t in c1_runs) and ok_on(R['c1a'].get('ratio_1000_1300_err_pct'), 10) and ok_on(R['m1'].get('ratio_1000_1200_err_pct'), 10),
              power=all(0.3 <= (R[t]['power_ratio_540_600_model'] or 0) <= 0.5 for t in c1_runs), skin_rise=R['c1a']['skin_rise_420_1200_model'] >= 0.5)
    c1['pass'] = all(c1.values()); res['checklist']['①'] = c1
    res['checklist']['②'] = dict(onset_err_s=R['m3']['onset_err_s'], **{'pass': ok_on(R['m3']['onset_err_s'], 10)})
    npu_runs = ['n1300', 'm2r_H1', 'm2r_H2']
    c3 = dict(step1=all(ok_on(R[t]['step1_err_s'], 20) for t in npu_runs), step2=all(ok_on(R[t]['step2_err_s'], 20) for t in npu_runs),
              level=all(ok_on(R[t].get('ratio_540_600_err'), 0.02) for t in npu_runs), end60=ok_on(R['n1300']['end60_err'], 0.03),
              status2=ok_on((R['n1300']['status2_model_s'] or 1e9) - 799.5, 60))
    c3['pass'] = all(c3.values()); res['checklist']['③'] = c3
    c4 = dict(onset=all(ok_on(R[t]['onset_err_s'], 20) for t in ('c600_r1', 'c600_r2')), plateau=all(ok_on(R[t]['plateau_err_pct'], 10) for t in ('c600_r1', 'c600_r2')))
    c4['pass'] = c4['onset'] and c4['plateau']; res['checklist']['④'] = c4
    cp5 = res['coupling']
    c5 = dict(npu_range=cp5['m2']['in_range'], gpu_range=cp5['m2r']['in_range'], npu_dir=cp5['m2']['direction_ok'], gpu_dir=cp5['m2r']['direction_ok'])
    c5['pass'] = all(c5.values()); res['checklist']['⑤'] = c5
    m1 = R['m1']['m1']
    res['checklist']['⑥'] = dict(recovery_s=m1['recovery_s'], shape=m1['shape'], **{'pass': m1['recovery_s'] is not None and abs(m1['recovery_s'] - 20) <= 10 and m1['shape'] == '계단형'})
    sx = res['sixty_s']
    c7 = dict(GPU=sx['GPU']['last10_over_first30_pct'], NPU=sx['NPU']['last10_over_first30_pct'], CPU4=sx['CPU4']['last10_over_first30_pct'])
    c7['pass'] = c7['GPU'] <= 5 and c7['NPU'] <= 5 and 5 <= c7['CPU4'] <= 30; res['checklist']['⑦'] = c7

    def rec_ok(tag, lo, hi):
        rc = R[tag]['recovery']
        return dict(recovery_s=rc['recovery_s'], shape=rc['shape'], release_skin=rc['release_skin'], release_ap=rc['release_ap'],
                    time_ok=(rc['recovery_s'] is not None and lo <= rc['recovery_s'] <= hi), shape_ok=(rc['shape'] == '계단형'),
                    skin_ok=(rc['release_skin'] is not None and abs(rc['release_skin'] - f2.MEAS[tag]['rel_skin']) <= 0.5))
    c9 = {t: rec_ok(t, 10, 30) for t in ('m1n_a', 'm1n_b')}
    c9['pass'] = all(v['time_ok'] and v['shape_ok'] and v['skin_ok'] for v in c9.values()); res['checklist']['⑨'] = c9
    c10 = {'m1': rec_ok('m1', 10, 30), 'm1g_r2': rec_ok('m1g_r2', 0, 20)}
    c10['pass'] = all(v['time_ok'] and v['shape_ok'] and v['skin_ok'] for v in c10.values()); res['checklist']['⑩'] = c10
    rt = R['gpace']['retighten']; g = f2.MEAS['gpace']
    c11 = dict(retighten_s=rt['retighten_s'], first_bin=rt['first_bin'], retighten_bin_ratio=rt['retighten_bin_ratio'], ratio_240_300=rt['ratio_240_300'],
               time_ok=(rt['retighten_s'] is not None and rt['retighten_s'] <= 20), first_ok=(rt['first_bin'] is not None and rt['first_bin'] <= 1.10),
               depth_ok=(rt['retighten_bin_ratio'] is not None and abs(rt['retighten_bin_ratio'] / g['ret_ratio'] - 1) <= 0.10),
               tail_ok=(rt['ratio_240_300'] is not None and abs(rt['ratio_240_300'] / g['r240'] - 1) <= 0.10))
    c11['pass'] = c11['time_ok'] and c11['first_ok'] and c11['depth_ok'] and c11['tail_ok']; res['checklist']['⑪'] = c11
    c12 = {}
    for t in ('m1n_a', 'm1n_b', 'm1g_r2'):
        rc = R[t]['recovery']
        mae = float(np.mean([abs(rc['probe_skin_at'][k] - v) for k, v in f2.MEAS[t]['skin_at'].items() if k in rc['probe_skin_at']]))
        mae_ap = float(np.mean([abs(rc['probe_ap_at'][k] - v) for k, v in f2.MEAS[t]['ap_at'].items() if k in rc['probe_ap_at']]))
        c12[t] = dict(skin_mae=mae, ap_mae=mae_ap, ok=mae <= 0.5)
    c12['pass'] = all(v['ok'] for k, v in c12.items() if k != 'pass'); res['checklist']['⑫'] = c12
    c13 = {}
    for t in ('m1n_a', 'm1n_b'):
        mm = R[t]['ratio_540_600_model']
        c13[t] = dict(ratio_540_600_model=mm, ratio_540_600_meas=f2.MEAS[t]['r540'], third_level_s=R[t]['third_level_s'],
                      ok=(mm is not None and abs(mm - f2.MEAS[t]['r540']) <= 0.03 and R[t]['third_level_s'] is not None))
    c13['pass'] = all(v['ok'] for k, v in c13.items() if k != 'pass'); res['checklist']['⑬'] = c13
    # ---- ⑭~⑳ (prereg v2.1 §4)
    R21 = {}
    for tag in ('n50p', 'n50p2', 'g50p', 'g50p2'):
        rows, S = closed(tag, pcm, sim)
        hm = heat_metrics(rows, 1)
        L = man(tag)['segments'][1]['duration_s']
        npu = RES_OF[tag][1] == 'NPU'
        R21[tag] = dict(start=dict(T=S['T_start'], A0=S['A0'], B0=S['B0']),
                        heat=dict(step1_s=hm['step1_s'], onset_1_1_s=hm['onset_1_1_s'], r240=hm['ratio'](240, 300), end_skin=at(rows, 1, L - 1)['skin']),
                        probe=probe_metrics(rows, 0.03 if npu else 0.10, retighten_thr=None if npu else 1.10))
    for tag in ('gi300', 'ni300', 'ni300r2'):
        rows, S = closed(tag, pcm, sim)
        hm = heat_metrics(rows, 1)
        gpu = tag == 'gi300'
        R21[tag] = dict(start=dict(T=S['T_start'], A0=S['A0'], B0=S['B0']), heat=dict(step1_s=hm['step1_s'], onset_1_1_s=hm['onset_1_1_s']),
                        idle=idle_metrics(rows, 1.10 if gpu else 1.06, 26 if gpu else 14))
    res['runs21'] = {k: dict(v, probe=({kk: vv for kk, vv in v['probe'].items() if kk != 'bins'} if 'probe' in v else None)) for k, v in R21.items()}
    res['checklist'].update(items_new(R21))
    res['checklist']['⑧'] = dict(note='전환비용 표 = v1 값 그대로', **{'pass': None})
    res['checklist_pass_count'] = sum(1 for k, v in res['checklist'].items() if v.get('pass') is True)
    res['checklist_pass_items'] = [k for k in ('①', '②', '③', '④', '⑤', '⑥', '⑦', '⑨', '⑩', '⑪', '⑫', '⑬', '⑭', '⑮', '⑯', '⑰', '⑱', '⑲', '⑳')
                                   if res['checklist'][k].get('pass') is True]
    return res


def v2_params(engine):
    pre = 'throttle_v2_'
    tp = json.load(open(os.path.join(PROFILES, f'{pre}thermal.json'), encoding='utf-8'))
    tp = {k: tp[k] for k in ('tau_f', 'G_f', 'G_s', 'tau_s', 'tau_a', 'G_a', 'P_idle', 'c_f', 'c_s', 'c_a')}
    ctrl, power, L0 = {}, {}, {}
    gfn = 'GPU_compiledmodel' if engine == 'CM' else 'GPU_interpreter'
    for res, fn in (('GPU', gfn), ('NPU', 'NPU'), ('CPU4', 'CPU4_interpreter')):
        d = json.load(open(os.path.join(PROFILES, f'{pre}{fn}.json'), encoding='utf-8'))
        ctrl[res] = dict(d['ctrl']); power[res] = {k: d['power'][k] for k in ('P_idle', 'P0', 'alpha')}; L0[res] = d['L0_ms']
    ctrl['CPU4'] = dict(ctrl['CPU4'], v1_controller=True)
    return dict(thermal=tp, ctrl=ctrl, power=power, L0=L0)


def v2_recount():
    out = {}
    for th in (0.3, 0.75):
        pcm, pint = v2_params('CM'), v2_params('INT')
        for p in (pcm, pint):
            p['ctrl']['NPU'] = dict(p['ctrl']['NPU'], theta=th)
        r = evaluate(pcm, pint, sim_v2)
        out[f'theta_{th}'] = dict(count=r['checklist_pass_count'], items=r['checklist_pass_items'], checklist=r['checklist'], runs21=r['runs21'])
        print(f'v2 theta {th}: {r["checklist_pass_count"]}/19', r['checklist_pass_items'], flush=True)
    return out


def params_for(engine, tp, ctrl, power, L0):
    g = 'GPU_CM' if engine == 'CM' else 'GPU_INT'
    return dict(thermal=tp, ctrl={'GPU': ctrl[g], 'NPU': ctrl['NPU'], 'CPU4': ctrl['CPU4']},
                power={'GPU': power[g], 'NPU': power['NPU'], 'CPU4': power['CPU4']}, L0={'GPU': L0[g], 'NPU': L0['NPU'], 'CPU4': L0['CPU4']})


def run_form(form, tp, alpha, L0, P0, ctrl_cpu):
    t0 = time.time()
    ctrl, fitinfo = {}, {}
    for key in ('GPU_INT', 'GPU_CM'):
        cands = {s: fit_gpu(key, form, s) for s in ('SKIN', 'AP')}
        sensor = min(cands, key=lambda s: cands[s][1])
        ctrl[key] = cands[sensor][0]
        fitinfo[key] = dict(sensor=sensor, fit_obj=cands[sensor][1], x=cands[sensor][2],
                            other_sensor={s: dict(fit_obj=cands[s][1], x=cands[s][2]) for s in cands if s != sensor}, fit_runs=[f'{t} s{sg}' for t, sg in CTRL_FIT[key]])
        print(f'  {form} {key}', sensor, round(cands[sensor][1], 5), {s: round(cands[s][1], 5) for s in cands}, f'({time.time() - t0:.0f}s)', flush=True)
    cands = {s: fit_npu(form, s) for s in ('SKIN', 'AP')}
    sensor = min(cands, key=lambda s: cands[s][1])
    ctrl['NPU'] = cands[sensor][0]
    fitinfo['NPU'] = dict(sensor=sensor, fit_obj=cands[sensor][1], x=cands[sensor][2],
                          other_sensor={s: dict(fit_obj=cands[s][1], x=cands[s][2]) for s in cands if s != sensor}, fit_runs=[f'{t} s{sg}' for t, sg in CTRL_FIT['NPU']])
    print(f'  {form} NPU', sensor, round(cands[sensor][1], 5), {s: round(cands[s][1], 5) for s in cands}, f'({time.time() - t0:.0f}s)', flush=True)
    ctrl['CPU4'] = dict(ctrl_cpu, v1_controller=True)
    nf = {'Ht': {'GPU_INT': 5, 'GPU_CM': 5, 'NPU': 8}, 'F': {'GPU_INT': 6, 'GPU_CM': 6, 'NPU': 9}}[form]
    n_params = dict(nf, CPU4=0, thermal_new=4 + (4 if isinstance(tp.get('G_s'), dict) else 0))    # c_f c_s c_a (v2) + k_b (v2.1) [+ r2: G_f, G_s per resource +4]
    power = {k: dict(P_idle=P_IDLE, P0=P0[k], alpha=alpha[k]) for k in ('GPU_CM', 'GPU_INT', 'NPU', 'CPU4')}
    pcm, pint = params_for('CM', tp, ctrl, power, L0), params_for('INT', tp, ctrl, power, L0)
    res = evaluate(pcm, pint, sim_v21)
    res.update(form=form, ctrl=ctrl, fit=fitinfo, n_params=n_params, n_params_total=sum(n_params.values()), elapsed_s=time.time() - t0,
               _params_cm=pcm, _params_int=pint)
    return res


def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument('--forms', nargs='*', default=['Ht', 'F'])
    ap.add_argument('--write-profiles', action='store_true')
    ap.add_argument('--v2-only', action='store_true')
    ap.add_argument('--profiles-only', action='store_true')
    ap.add_argument('--thermal', default='shared', choices=['shared', 'res'])
    ap.add_argument('--tag', default='')
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    outp = os.path.join(OUT, f'throttle_fit_v21{"_" + a.tag if a.tag else ""}.json')
    if a.profiles_only:
        write_profiles(json.load(open(outp, encoding='utf-8')))
        return 0
    if a.v2_only:
        json.dump(dict(v2_recount=v2_recount()), open(os.path.join(OUT, 'throttle_v21_v2recount.json'), 'w', encoding='utf-8'), indent=1, ensure_ascii=False, default=str)
        return 0
    tp2 = json.load(open(os.path.join(PROFILES, 'throttle_v2_thermal.json'), encoding='utf-8'))
    t0 = time.time()
    runs = [series(t, s) for t, s in FIT_THERMAL]
    tp, skin_obj, ap_obj, extra = fit_thermal(runs, tp2)
    if a.thermal == 'res':
        extra['r1_shared'] = dict(params=dict(tp), skin_obj=skin_obj)
        tp, skin_obj, ap_obj, e2 = fit_thermal_res(runs, tp2, tp)
        extra.update(e2)
    errs = {}
    for t, s in FIT_THERMAL:
        S = series(t, s)
        errs[f'{t} s{"all" if s is None else s}'] = dict(with_k_b=thermal_errors(tp, S), z=((S['T_start'] - S['B0']) - extra['d_ref']) if S['B0'] is not None else None,
                                                        B0=S['B0'], T_start=S['T_start'])
    thermal = dict(params=tp, fit_obj_skin_mse=skin_obj, fit_obj_ap_mse=ap_obj, kb0=extra, fit_runs=[f'{t} s{"all" if s is None else s}' for t, s in FIT_THERMAL], errors=errs)
    print('thermal', {k: (round(v, 4) if isinstance(v, float) else v) for k, v in tp.items() if k != 'source'}, 'skin_obj', round(skin_obj, 5),
          'kb0_obj', round(extra['kb0_skin_obj'], 5), 'ap_obj', round(ap_obj, 5), f'({time.time() - t0:.0f}s)', flush=True)
    results = dict(model='v2.1', thermal=thermal, candidates={})
    results['v2_recount'] = v2_recount()
    alpha, L0, P0 = {}, {}, {}
    for key, fn in (('GPU_CM', 'GPU_compiledmodel'), ('GPU_INT', 'GPU_interpreter'), ('NPU', 'NPU'), ('CPU4', 'CPU4_interpreter')):
        d = json.load(open(os.path.join(PROFILES, f'throttle_v1_{fn}.json'), encoding='utf-8'))
        alpha[key], L0[key], P0[key] = d['power']['alpha'], d['L0_ms'], d['power']['P0']
        if key == 'CPU4':
            ctrl_cpu = dict(d['ctrl'])
    results['alpha'] = alpha; results['L0_ms'] = L0; results['P0_w'] = P0
    for form in a.forms:
        res = run_form(form, tp, alpha, L0, P0, ctrl_cpu)
        results['candidates'][form] = res
        print(f'V21-{form}', 'count', res['checklist_pass_count'], res['checklist_pass_items'], 'params', res['n_params_total'],
              'sensors', {k: res['fit'][k]['sensor'] for k in ('GPU_INT', 'GPU_CM', 'NPU')}, f'({res["elapsed_s"]:.0f}s)', flush=True)
        json.dump(results, open(outp, 'w', encoding='utf-8'), indent=1, ensure_ascii=False, default=str)
    order = {'Ht': 0, 'F': 1}
    adopt = max(results['candidates'], key=lambda n: (results['candidates'][n]['checklist_pass_count'], -results['candidates'][n]['n_params_total'], -order[n]))
    v2best = max(v['count'] for v in results['v2_recount'].values())
    results['adopted'] = adopt
    results['v21_status'] = 'v2.1' if results['candidates'][adopt]['checklist_pass_count'] > v2best else 'v2.1 미완 (v2 보다 많지 않음)'
    results['adoption_rule'] = '19항목 통과 수 최다 → 동률이면 피팅 파라미터 수 적은 쪽 → V21-Hθ → V21-F; v2 (두 변형 중 많은 쪽) 보다 많지 않으면 v2.1 미완 (사전 등록 v2.1 §5)'
    json.dump(results, open(outp, 'w', encoding='utf-8'), indent=1, ensure_ascii=False, default=str)
    print('adopted', adopt, results['v21_status'], 'v2 best', v2best)
    if a.write_profiles:
        write_profiles(results)
    return 0


def write_profiles(results):
    adopt = results['adopted']
    tp = results['thermal']['params']
    c = results['candidates'][adopt]
    json.dump(dict(form=f'V21-{adopt}', **tp, fit_runs=results['thermal']['fit_runs'], checklist_pass=c['checklist_pass_items'], v21_status=results['v21_status'],
                   status='measured-fit (v2 thermal block refit + body initial condition k_b; v2.1 stage A)'),
              open(os.path.join(PROFILES, 'throttle_v21_thermal.json'), 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
    names = {'GPU_CM': 'GPU_compiledmodel', 'GPU_INT': 'GPU_interpreter', 'NPU': 'NPU', 'CPU4': 'CPU4_interpreter'}
    for key, fn in names.items():
        d = dict(form=f'V21-{adopt}', resource=('GPU' if key.startswith('GPU') else key), engine=('Interpreter 1.4.2' if key in ('GPU_INT', 'CPU4') else 'CompiledModel 2.2.0'),
                 ctrl=c['ctrl'][key], power=dict(P_idle=P_IDLE, P0=results['P0_w'][key], alpha=results['alpha'][key]), L0_ms=results['L0_ms'][key],
                 fit=(c['fit'].get(key) if key != 'CPU4' else 'v1 controller unchanged'), source='d1sim/tools/fit_throttle_v21.py', status='measured-fit')
        json.dump(d, open(os.path.join(PROFILES, f'throttle_v21_{fn}.json'), 'w', encoding='utf-8'), indent=1, ensure_ascii=False, default=str)
    print('wrote profiles', adopt)


if __name__ == '__main__':
    sys.exit(main())
