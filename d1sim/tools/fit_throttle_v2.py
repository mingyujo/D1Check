"""fit_throttle_v2.py — fit throttle model v2 (d1sim/throttle_v2.py) and run the pre-registered 12-item checklist.

Pre-registration: sim/스로틀모형_사전등록_v2.md (mirror d1sim/docs/). Deterministic (fixed Nelder-Mead starts, no RNG).
Reads d1sim/data/trace_v1_*.csv (v1 tags, unchanged) and trace_v2_*.csv (10/3 night runs, extract_traces_v2.py).
Writes d1sim/out/throttle_fit_v2.json and, with --write-profiles, d1sim/profiles/throttle_v2_*.json.

Stages (prereg §3):  A thermal (v1 block + cooling c_f/c_s/c_a)  ·  B controllers on measured sensor + measured duty (u)
                     ·  C closed loop -> checklist ①~⑧ (v1 definitions, same runs) + ⑨~⑬ (prereg v2 §4)
Forms: V2-Lk (load-dependent threshold), V2-Lb (load gate theta), V2-S (static map + delay). Driver sensor SKIN / AP both fitted.
v1 is re-counted on the same 12 items from its frozen outputs (no v1 code is modified or re-run).

  py d1sim/tools/fit_throttle_v2.py [--forms Lk Lb S] [--write-profiles]
"""
from __future__ import annotations

import argparse
import csv
import itertools
import json
import math
import os
import sys
import time

import numpy as np
from scipy.optimize import minimize

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, ROOT)
from d1sim import throttle_v2 as tv2  # noqa: E402
from d1sim.tools import fit_throttle_v1 as f1  # noqa: E402  (metric helpers + v1 constants; never modified)

DATA = os.path.join(ROOT, 'd1sim', 'data')
OUT = os.path.join(ROOT, 'd1sim', 'out')
PROFILES = os.path.join(ROOT, 'd1sim', 'profiles')
SIM = f1.SIM
V2_TAGS = {'m1n_a', 'm1n_b', 'm1g_r2', 'gpace'}
MAN2 = json.load(open(os.path.join(DATA, 'trace_v2_manifest.json'), encoding='utf-8'))
RES_OF = dict(f1.RES_OF, m1n_a=['NPU'] * 3, m1n_b=['NPU'] * 3, m1g_r2=['GPU'] * 3, gpace=['GPU'] * 4)
ENGINE_OF = dict(f1.ENGINE_OF, m1n_a='CM', m1n_b='CM', m1g_r2='CM', gpace='CM')
P_IDLE, D_ON = f1.P_IDLE, f1.D_ON
FIT_THERMAL = [('m2_H1', 0), ('n1300', 0), ('c1p_r1', 0), ('c600_r1', 0), ('m1', None), ('m1n_a', None)]
HOLD_THERMAL = [('m2_H2', 0), ('c1p_r2', 0), ('c1a', 0), ('m3', 0), ('c600_r2', 0), ('m2r_H1', 0), ('m2r_H2', 0), ('m1n_b', None), ('m1g_r2', None), ('gpace', None)]
CTRL_FIT = {'GPU_INT': [('c1p_r1', [0]), ('m3', [0])], 'GPU_CM': [('m2_H1', [0]), ('m1', [0, 1, 2])], 'NPU': [('n1300', [0]), ('m1n_a', [0, 1, 2])]}
# measured targets for ⑨~⑬ [P sim/out_1003/*.json — M1_NPU_결과_1003 §C, M1_GPU2_결과_1003 §2, GPU페이싱_결과_1003 §2, M1_결과_1002]
MEAS = dict(
    m1n_a=dict(rec=20, rel_skin=41.4, rel_ap=43.9, r540=1.207469, skin_at={0: 42.2, 60: 40.5, 120: 39.8, 300: 38.3, 599: 37.0}, ap_at={0: 46.2, 60: 42.5, 120: 41.5, 300: 40.2, 599: 37.9}),
    m1n_b=dict(rec=20, rel_skin=41.4, rel_ap=43.9, r540=1.208, skin_at={0: 42.4, 60: 40.4, 120: 39.7, 300: 38.3, 599: 36.8}, ap_at={0: 46.3, 60: 42.4, 120: 41.3, 300: 39.8, 599: 37.8}),
    m1=dict(rec=20, rel_skin=37.1, rel_ap=38.0),
    m1g_r2=dict(rec=10, rel_skin=38.2, rel_ap=39.1, skin_at={0: 38.7, 60: 37.4, 120: 36.9, 180: 36.5, 240: 36.2, 290: 35.9}, ap_at={0: 41.0, 60: 38.1, 120: 37.5, 180: 37.1, 240: 36.6, 290: 36.3}),
    gpace=dict(ret=10, first=1.019254, ret_ratio=2.019, r240=2.231),
)


# ============================================================ data (prefix-aware copies of the v1 loaders)
def fl(v):
    return None if v in ('', None) else float(v)


def prefix(tag):
    return 'trace_v2_' if tag in V2_TAGS else 'trace_v1_'


def man(tag):
    return MAN2[tag] if tag in V2_TAGS else f1.MAN[tag]


def rows1(tag, seg=None):
    rr = list(csv.DictReader(open(os.path.join(DATA, f'{prefix(tag)}{tag}.csv'), encoding='utf-8')))
    return rr if seg is None else [r for r in rr if int(r['seg']) == seg]


def series(tag, seg=None):
    rr = rows1(tag, seg)
    P, SK, AP, segs, act = [], [], [], [], []
    lp = lsk = lap = None
    for r in rr:
        p, sk, ap = fl(r['power_w']), fl(r['SKIN']), fl(r['AP'])
        lp = p if p is not None else lp; lsk = sk if sk is not None else lsk; lap = ap if ap is not None else lap
        P.append(lp); SK.append(lsk); AP.append(lap); segs.append(int(r['seg'])); act.append(int(r['n_inf']) > 0)
    for arr in (P, SK, AP):
        first = next((x for x in arr if x is not None), None)
        for i in range(len(arr)):
            if arr[i] is None:
                arr[i] = first
            else:
                break
    return dict(P=np.array(P, float), SKIN=np.array(SK, float), AP=np.array(AP, float), seg=np.array(segs), active=act,
                T_start=SK[0], A0=AP[0] - SK[0], res=[RES_OF[tag][g] for g in segs])


def bins10(tag, seg):
    rr = [r for r in csv.DictReader(open(os.path.join(DATA, f'{prefix(tag)}10s_{tag}.csv'), encoding='utf-8')) if int(r['seg']) == seg]
    ref = next(r for r in rr if r['t_s'] == '-1')
    b = [(int(r['t_s']), fl(r['lat_med_ms']), int(r['n_inf']), fl(r['power_w'])) for r in rr if r['t_s'] != '-1']
    return dict(ref=fl(ref['lat_med_ms']), ref_pw=fl(ref['power_w']), bins=b, ratio=[(t, (m / fl(ref['lat_med_ms'])) if m else None) for t, m, n, pw in b])


def schedule_of(tag):
    m = man(tag)
    sch = []
    for i, seg in enumerate(m['segments']):
        if i > 0:
            sch.append((f't{i}', None, None, m['transitions'][i - 1]['duration_s']))
        sch.append((i, RES_OF[tag][i], [int(r['n_inf']) > 0 for r in rows1(tag, i)], seg['duration_s']))
    return sch


def closed(tag, params):
    S = series(tag)
    return tv2.simulate(params, schedule_of(tag), S['T_start'], S['A0'], dt=1.0), S


# ============================================================ Stage A — thermal (v1 block + cooling asymmetry)
def thermal_run(tp, S):
    th = tv2.ThermalV2(tp, S['T_start'], S['A0'])
    sk, ap = [], []
    for P, r in zip(S['P'], S['res']):
        sk.append(th.skin); ap.append(th.ap)
        th.advance(1.0, float(P), r)
    return np.array(sk), np.array(ap)


def fit_thermal(runs, tp1):
    def obj(x):
        G_f, G_s, tau_s, c_f, c_s = x
        if not (0 <= G_f <= 5 and 0 <= G_s <= 5 and 60 <= tau_s <= 3000 and 1 <= c_f <= 20 and 1 <= c_s <= 20):
            return 1e6
        tp = dict(tau_f=f1.TAU_F, G_f=G_f, G_s=G_s, tau_s=tau_s, tau_a=30.0, G_a=0.0, P_idle=P_IDLE, c_f=c_f, c_s=c_s, c_a=1.0)
        return float(np.mean([np.mean((thermal_run(tp, S)[0] - S['SKIN']) ** 2) for S in runs]))
    best = None
    for c in (1.5, 3.0):
        r = minimize(obj, np.array([tp1['G_f'], tp1['G_s'], tp1['tau_s'], c, c]), method='Nelder-Mead', options=dict(maxiter=1500, xatol=1e-4, fatol=1e-9))
        if best is None or r.fun < best.fun:
            best = r
    G_f, G_s, tau_s, c_f, c_s = map(float, best.x)
    tp = dict(tau_f=f1.TAU_F, G_f=G_f, G_s=G_s, tau_s=tau_s, tau_a=30.0, G_a=dict(tp1['G_a']), P_idle=P_IDLE, c_f=c_f, c_s=c_s, c_a=1.0)
    skin_obj = float(best.fun)
    # AP node: tau_a grid x NM over (G_a GPU/NPU/CPU4, c_a) on the pooled AP error (closed form is lost with the asymmetry)
    best_a = None
    for tau_a in (30.0, 50.0, 80.0, 120.0):
        def obj_a(x, tau_a=tau_a):
            g1, g2, g3, c_a = x
            if not (0 <= g1 <= 5 and 0 <= g2 <= 5 and 0 <= g3 <= 5 and 1 <= c_a <= 20):
                return 1e6
            t = dict(tp, tau_a=tau_a, G_a={'GPU': g1, 'NPU': g2, 'CPU4': g3}, c_a=c_a)
            return float(np.mean([np.mean((thermal_run(t, S)[1] - S['AP']) ** 2) for S in runs]))
        r = minimize(obj_a, np.array([tp1['G_a']['GPU'], tp1['G_a']['NPU'], tp1['G_a']['CPU4'], 2.0]), method='Nelder-Mead',
                     options=dict(maxiter=800, xatol=1e-4, fatol=1e-9))
        if best_a is None or r.fun < best_a[0]:
            best_a = (float(r.fun), tau_a, list(map(float, r.x)))
    tp['tau_a'] = best_a[1]
    tp['G_a'] = dict(zip(('GPU', 'NPU', 'CPU4'), best_a[2][:3]))
    tp['c_a'] = best_a[2][3]
    tp['source'] = 'stage A v2: SKIN NM (G_f,G_s,tau_s,c_f,c_s) from v1 start; AP tau_a grid {30,50,80,120} x NM (G_a x3, c_a)'
    return tp, skin_obj, best_a[0]


def thermal_errors(tp, S):
    sk, ap = thermal_run(tp, S)
    return dict(skin_mae=float(np.mean(np.abs(sk - S['SKIN']))), ap_mae=float(np.mean(np.abs(ap - S['AP']))),
                skin_end_model=float(sk[-1]), skin_end_meas=float(S['SKIN'][-1]))


# ============================================================ Stage B — controllers on measured sensor + measured duty
def u_series(active):
    w, out = [], []
    for a in active:
        w.append(1 if a else 0)
        if len(w) > tv2.WINDOW_S:
            w.pop(0)
        out.append(sum(w) / float(tv2.WINDOW_S))
    return out


class _Th:
    pass


def ctrl_ratio_series(cp, res, T, active, segs):
    """Per-second model ratio over a measured sensor series (segments concatenated; the scheduled resource is the run's)."""
    c = tv2.NpuStepController(cp) if res == 'NPU' else tv2.GpuGateController(cp)
    u = u_series(active)
    th = _Th()
    out = []
    for i, (Ti, a) in enumerate(zip(T, active)):
        th.ap = th.skin = float(Ti)
        if res == 'NPU':
            r = c.ratio
        else:
            c.last_T = float(Ti)
            r = c.ratio_at(float(Ti))
        out.append(r if a else None)
        c.step(1.0, th, bool(a), scheduled=True, u=u[i])
    return out


def meas_ratio_bins(tag, segs_wanted):
    """Measured 10 s ratio per segment relative to the run's COLD reference (segment 0 first-30 s median) -> list of (seg, t, ratio)."""
    ref0 = bins10(tag, 0)['ref']
    out = []
    for sg in segs_wanted:
        for t, m, n, pw in bins10(tag, sg)['bins']:
            out.append((sg, t, (m / ref0) if m else None))
    return out


def model_ratio_bins(rs, segs, segs_wanted):
    out = {}
    idx = {}
    for i, sg in enumerate(segs):
        idx.setdefault(sg, []).append(i)
    for sg in segs_wanted:
        ii = idx.get(sg, [])
        for k in range(len(ii) // 10):
            v = sorted(rs[j] for j in ii[k * 10:(k + 1) * 10] if rs[j] is not None)
            out[(sg, k * 10)] = v[len(v) // 2] if v else None
    return out


def ctrl_obj(cp, res, sensor, fitdata):
    e = []
    for S, meas, segs_wanted in fitdata:
        T = S['AP'] if sensor == 'AP' else S['SKIN']
        rs = ctrl_ratio_series(cp, res, T, S['active'], S['seg'])
        mb = model_ratio_bins(rs, list(S['seg']), segs_wanted)
        for sg, t, m in meas:
            p = mb.get((sg, t))
            if p is not None and m is not None:
                e.append((p / m - 1) ** 2)
    return float(np.mean(e)) if e else 1e6


def fit_gpu(key, form, sensor, kappa_fixed):
    fitdata = [(series(tag), meas_ratio_bins(tag, segs), segs) for tag, segs in CTRL_FIT[key]]
    # r2 (ledger V2-Lk-r2): kappa is fitted PER ENGINE (r1 fixed the CompiledModel kappa to the Interpreter m3 value 0.87 and the
    # d10 release at SKIN 38.2 could then only come from the depth map ramp -> gradual, h inflated to 1.7). CM's kappa is identified
    # by the m1 probe release (lower bound, scanned down like NPU); INT's by m3 (d50 onset). h starts near 0.
    # r3 (ledger V2-Lk-r3): r1·r2 both left the gate DEAD — a free T_d0 (~37.3) let the depth map ramp to 1.0 at the d10 release
    # temperatures, so the objective never needed the gate (h inflated, kappa arbitrary). Constraint: T_d0 = T_on (depth starts
    # rising at the arm threshold) -> the release must come from the gate; kappa_CM = kappa_INT (m3 d50) as the prereg §2.1 says.
    free_kappa = (form == 'Lk' and kappa_fixed is None)
    names = ['T_on', 'h', 'W', 'D'] + (['kappa'] if free_kappa else [])
    t0 = {'SKIN': [36.8, 37.6], 'AP': [41.5, 42.6]}[sensor]
    starts = [t0, [0.2], [1.0, 2.5], [1.2]] + ([[1.0, 2.5]] if free_kappa else [])
    bounds = [(30, 50), (0, 6), (0.05, 10), (0.2, 3)] + ([(0, 10)] if free_kappa else [])

    def mk(x):
        d = dict(sensor=sensor, form=form, d_on=D_ON, d_off=10.0, T_on=x[0], h=x[1], T_d0=x[0], W=x[2], D=x[3],
                 kappa=(x[4] if free_kappa else (kappa_fixed if (form == 'Lk' and kappa_fixed is not None) else 0.0)),
                 theta=(0.3 if form == 'Lb' else 0.0), T_d0_rule='T_d0 = T_on (r3 constraint)')
        return d

    def obj(x):
        for v, (lo, hi) in zip(x, bounds):
            if not lo <= v <= hi:
                return 1e6
        return ctrl_obj(mk(x), 'GPU', sensor, fitdata)
    best = None
    for st in itertools.product(*starts):
        r = minimize(obj, np.array(st, float), method='Nelder-Mead', options=dict(maxiter=1200, xatol=1e-4, fatol=1e-9))
        if best is None or r.fun < best.fun:
            best = r
    x = list(map(float, best.x))
    cp = mk(x)
    info = dict(zip(names, x))
    return cp, float(best.fun), info


def fit_npu(form, sensor):
    fitdata = [(series(tag), meas_ratio_bins(tag, segs), segs) for tag, segs in CTRL_FIT['NPU']]
    free_kappa = (form == 'Lk')
    names = ['T1', 'T2', 'T3', 'a1', 'a2', 'a3', 'h'] + (['kappa'] if free_kappa else [])
    t1 = {'SKIN': 38.0, 'AP': 42.3}[sensor]
    starts = [[t1 - 0.3, t1 + 0.3], [t1 + 1.7], [t1 + 3.4], [0.09], [0.03], [0.07], [0.5]] + ([[3.0, 6.0]] if free_kappa else [])
    bounds = [(30, 50), (30, 50), (30, 50), (0, 0.5), (0, 0.5), (0, 0.5), (0, 6)] + ([(0, 30)] if free_kappa else [])

    def mk(x):
        return dict(sensor=sensor, form=form, d_on=D_ON, d_off=10.0, T1=x[0], T2=x[1], T3=x[2], a1=x[3], a2=x[4], a3=x[5], h=x[6],
                    kappa=(x[7] if free_kappa else 0.0), theta=(0.3 if form == 'Lb' else 0.0))

    def obj(x):
        for v, (lo, hi) in zip(x, bounds):
            if not lo <= v <= hi:
                return 1e6
        if not (x[0] < x[1] < x[2]):
            return 1e6
        return ctrl_obj(mk(x), 'NPU', sensor, fitdata)
    best = None
    for st in itertools.product(*starts):
        r = minimize(obj, np.array(st, float), method='Nelder-Mead', options=dict(maxiter=1500, xatol=1e-4, fatol=1e-9))
        if best is None or r.fun < best.fun:
            best = r
    x = list(map(float, best.x))
    cp = mk(x)
    info = dict(zip(names, x))
    if free_kappa:
        # kappa is identified only as a LOWER BOUND by the d10 release: scan down until the objective worsens (> 2 %)
        base = float(best.fun)
        k_lo = cp['kappa']
        k = cp['kappa']
        while k - 0.25 >= 0:
            k -= 0.25
            if obj(x[:7] + [k]) <= base * 1.02 + 1e-12:
                k_lo = k
            else:
                break
        info['kappa_fit'] = cp['kappa']
        info['kappa_lo'] = k_lo
        cp['kappa'] = k_lo
        cp['kappa_variants'] = {'kappa_lo': k_lo, 'kappa_2': 2 * k_lo, 'kappa_inf': 1e9}
    return cp, float(best.fun), info


# ============================================================ Stage C — closed loop + checklist
def params_for(engine, tp, ctrl, power, L0):
    g = 'GPU_CM' if engine == 'CM' else 'GPU_INT'
    return dict(thermal=tp, ctrl={'GPU': ctrl[g], 'NPU': ctrl['NPU'], 'CPU4': ctrl['CPU4']},
                power={'GPU': power[g], 'NPU': power['NPU'], 'CPU4': power['CPU4']}, L0={'GPU': L0[g], 'NPU': L0['NPU'], 'CPU4': L0['CPU4']})


def recovery_metrics(rows, probe_seg, delta, ref_seg=0, times=(0, 60, 120, 300, 599)):
    ref = f1.win_med(rows, ref_seg, 0, 60)
    pb = tv2.bins_ratio(rows, probe_seg)
    pr = [None if m is None else m / ref for t, m in pb]
    k_rec = next((k for k in range(0, len(pr) - 3) if all(x is not None and x <= 1 + delta for x in pr[k:k + 4])), None)
    shape, frac = '중도절단', None
    if k_rec is not None and k_rec > 0:
        total = pr[0] - pr[k_rec]
        steps = [pr[j - 1] - pr[j] for j in range(1, k_rec + 1)]
        frac = (max(steps) / total) if total > 0 else None
        shape = '계단형' if (frac is not None and frac >= 0.5) else '점진형'
    elif k_rec == 0:
        shape = '즉시'
    probe = [r for r in rows if r['seg'] == probe_seg]
    rel = probe[10 * k_rec] if (k_rec is not None and 10 * k_rec < len(probe)) else None
    return dict(ref_model=ref, probe_bins_ratio_first8=pr[:8], recovery_s=(10 * k_rec if k_rec is not None else None), shape=shape, step_fraction=frac,
                release_skin=(rel['skin'] if rel else None), release_ap=(rel['ap'] if rel else None),
                probe_skin_at={t: probe[t]['skin'] for t in times if t < len(probe)}, probe_ap_at={t: probe[t]['ap'] for t in times if t < len(probe)})


def retighten_metrics(rows, heat_seg=1, rest_seg=2, reheat_seg=3):
    ref = f1.win_med(rows, heat_seg, 0, 30)
    pb = [None if m is None else m / ref for t, m in tv2.bins_ratio(rows, reheat_seg)]
    k = next((k for k in range(0, len(pb) - 3) if all(x is not None and x >= 1.10 for x in pb[k:k + 4])), None)
    re = [r for r in rows if r['seg'] == reheat_seg]
    return dict(ref_d100_model=ref, reheat_bins_first6=pb[:6], retighten_s=(10 * k if k is not None else None), first_bin=pb[0] if pb else None,
                retighten_bin_ratio=(pb[k] if k is not None else None), ratio_240_300=(f1.win_med(rows, reheat_seg, 240, 300) / ref if f1.win_med(rows, reheat_seg, 240, 300) else None),
                retighten_skin=(re[10 * k]['skin'] if k is not None else None), retighten_ap=(re[10 * k]['ap'] if k is not None else None),
                rest_end_skin=[r for r in rows if r['seg'] == rest_seg][-1]['skin'], rest_end_ap=[r for r in rows if r['seg'] == rest_seg][-1]['ap'])


def third_level(rows, seg):
    mb = tv2.bins_ratio(rows, seg)
    vals = [(t, m) for t, m in mb if m is not None]
    for i, (t, m) in enumerate(vals):
        if m >= 1.165 and i + 2 < len(vals) and all(vals[j][1] >= 1.165 for j in range(i + 1, i + 3)):
            return t
    return None


def m2_metrics(grp, params_cm, judge):
    v, first, second = {}, {}, {}
    for arm in ('C1', 'H1', 'H2', 'C2'):
        rows, S = closed(f'{grp}_{arm}', params_cm)
        v[arm] = f1.win_med(rows, 1, 0, 60); first[arm] = f1.win_med(rows, 1, 0, 10); second[arm] = f1.win_med(rows, 1, 10, 20)
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


def sixty_s(params):
    out = {}
    for res in ('GPU', 'NPU', 'CPU4'):
        rows = tv2.simulate(params, [(0, res, True, 60)], 30.3, -1.0)
        b = tv2.bins_ratio(rows, 0)
        first30 = float(np.median([r['ratio'] for r in rows[:30]]))
        out[res] = dict(last10_over_first30_pct=100 * (b[5][1] / first30 - 1), skin_end=rows[-1]['skin'])
    return out


def ok_on(x, lim):
    return isinstance(x, (int, float)) and abs(x) <= lim


def run_form(form, tp, alpha, L0, P0, ctrl_cpu):
    t0 = time.time()
    ctrl, fitinfo = {}, {}
    # GPU Interpreter first (kappa_G from m3 d50), then CompiledModel with the same kappa; both sensors, pick by objective
    for key in ('GPU_INT', 'GPU_CM'):
        cands = {}
        for sensor in ('SKIN', 'AP'):
            kfix = None if key == 'GPU_INT' else (ctrl['GPU_INT']['kappa'] if form == 'Lk' else 0.0)   # r3: kappa_CM = kappa_INT (prereg §2.1)
            cp, o, x = fit_gpu(key, form, sensor, kfix)
            cands[sensor] = (cp, o, x)
        sensor = min(cands, key=lambda s: cands[s][1])
        cp, o, x = cands[sensor]
        if key == 'GPU_CM':
            cp['kappa_source'] = 'GPU_INT fit on m3 (d50, Interpreter) — applied to CompiledModel [E, engine differs] (prereg v2 §2.1)' if form == 'Lk' else 'n/a'
        ctrl[key] = cp
        fitinfo[key] = dict(sensor=sensor, fit_obj=o, x=x, other_sensor={s: dict(fit_obj=cands[s][1], x=cands[s][2]) for s in cands if s != sensor},
                            fit_runs=[f'{t} s{sg}' for t, sg in CTRL_FIT[key]])
    cands = {}
    for sensor in ('SKIN', 'AP'):
        cands[sensor] = fit_npu(form, sensor)
    sensor = min(cands, key=lambda s: cands[s][1])
    cp, o, x = cands[sensor]
    ctrl['NPU'] = cp
    fitinfo['NPU'] = dict(sensor=sensor, fit_obj=o, x=x, other_sensor={s: dict(fit_obj=cands[s][1], x=cands[s][2]) for s in cands if s != sensor},
                          fit_runs=[f'{t} s{sg}' for t, sg in CTRL_FIT['NPU']])
    ctrl['CPU4'] = dict(ctrl_cpu, v1_controller=True)
    n_params = {'GPU_INT': len(fitinfo['GPU_INT']['x']), 'GPU_CM': len(fitinfo['GPU_CM']['x']), 'NPU': len([k for k in fitinfo['NPU']['x'] if k not in ('kappa', 'kappa_fit', 'kappa_lo')]), 'CPU4': 0,
                'thermal_new': 3}
    power = {k: dict(P_idle=P_IDLE, P0=P0[k], alpha=alpha[k]) for k in ('GPU_CM', 'GPU_INT', 'NPU', 'CPU4')}
    pcm, pint = params_for('CM', tp, ctrl, power, L0), params_for('INT', tp, ctrl, power, L0)
    res = dict(form=form, ctrl=ctrl, fit=fitinfo, n_params=n_params, n_params_total=sum(n_params.values()), runs={}, checklist={})
    # ---- closed loop per run (v1 set + 10/3 runs)
    for tag in ('c1p_r1', 'c1p_r2', 'c1a', 'm3', 'm2_H1', 'm2_H2', 'm1', 'n1300', 'm2r_H1', 'm2r_H2', 'c600_r1', 'c600_r2', 'm1n_a', 'm1n_b', 'm1g_r2', 'gpace'):
        params = pcm if ENGINE_OF[tag] == 'CM' else pint
        rows, S = closed(tag, params)
        seg = 1 if tag in ('m1', 'm1n_a', 'm1n_b', 'm1g_r2', 'gpace') else 0
        B = bins10(tag, seg)
        L = man(tag)['segments'][seg]['duration_s']
        r0 = RES_OF[tag][seg]
        m = f1.gpu_metrics(rows, seg, B, S, L) if r0 == 'GPU' else (f1.npu_metrics(rows, seg, B, S, L) if r0 == 'NPU' else f1.cpu_metrics(rows, seg, B, S, L))
        m.update(f1.temps_err(rows, S))
        if tag == 'm1':
            m['m1'] = f1.m1_metrics(rows)
            m['recovery'] = recovery_metrics(rows, 2, 0.10, times=(0, 60, 120, 180, 240, 290))
        if tag == 'm1g_r2':
            m['recovery'] = recovery_metrics(rows, 2, 0.10, times=(0, 60, 120, 180, 240, 290))
        if tag in ('m1n_a', 'm1n_b'):
            m['recovery'] = recovery_metrics(rows, 2, 0.03)
            m['third_level_s'] = third_level(rows, 1)
        if tag == 'gpace':
            m['retighten'] = retighten_metrics(rows)
        if tag == 'c1a':
            sk420 = next(r['skin'] for r in rows if r['t'] == 420); sk1200 = next(r['skin'] for r in rows if r['t'] == 1200)
            m['skin_rise_420_1200_model'] = sk1200 - sk420; m['skin_rise_420_1200_meas'] = float(S['SKIN'][1200] - S['SKIN'][420])
        m['role'] = 'fit' if any(tag == t for k in CTRL_FIT for t, _ in CTRL_FIT[k]) else 'half-holdout'
        res['runs'][tag] = m
    judges = {'m2': json.load(open(os.path.join(SIM, 'out_1002', 'M2_npu_judge.json'), encoding='utf-8')),
              'm2r': json.load(open(os.path.join(SIM, 'out_1002', 'M2r_gpu_judge.json'), encoding='utf-8'))}
    res['coupling'] = {g: m2_metrics(g, pcm, judges[g]) for g in ('m2', 'm2r')}
    res['sixty_s'] = sixty_s(pcm)
    # ---- checklist ①~⑧ (v1 definitions verbatim)
    R = res['runs']
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
    c4 = dict(onset=all(ok_on(R[t]['onset_err_s'], 20) for t in ('c600_r1', 'c600_r2')), plateau=all(ok_on(R[t]['plateau_err_pct'], 10) for t in ('c600_r1', 'c600_r2')), first10_boost_reproduced=False)
    c4['pass'] = c4['onset'] and c4['plateau']; res['checklist']['④'] = c4
    cp5 = res['coupling']
    c5 = dict(npu_range=cp5['m2']['in_range'], gpu_range=cp5['m2r']['in_range'], npu_dir=cp5['m2']['direction_ok'], gpu_dir=cp5['m2r']['direction_ok'])
    c5['pass'] = all(c5.values()); res['checklist']['⑤'] = c5
    m1 = R['m1']['m1']
    res['checklist']['⑥'] = dict(recovery_s=m1['recovery_s'], shape=m1['shape'], **{'pass': m1['recovery_s'] is not None and abs(m1['recovery_s'] - 20) <= 10 and m1['shape'] == '계단형'}, note='1런 (1002) — v1 정의 그대로')
    sx = res['sixty_s']
    c7 = dict(GPU=sx['GPU']['last10_over_first30_pct'], NPU=sx['NPU']['last10_over_first30_pct'], CPU4=sx['CPU4']['last10_over_first30_pct'])
    c7['pass'] = c7['GPU'] <= 5 and c7['NPU'] <= 5 and 5 <= c7['CPU4'] <= 30; res['checklist']['⑦'] = c7
    res['checklist']['⑧'] = dict(note='전환비용 표 = device_profile_S26_v2.yaml switch_cost_s (v1 값 그대로)', **{'pass': None})
    # ---- ⑨~⑬ (prereg v2 §4)
    def rec_ok(tag, lo, hi):
        rc = R[tag]['recovery']
        return dict(recovery_s=rc['recovery_s'], shape=rc['shape'], release_skin=rc['release_skin'], release_ap=rc['release_ap'],
                    time_ok=(rc['recovery_s'] is not None and lo <= rc['recovery_s'] <= hi), shape_ok=(rc['shape'] == '계단형'),
                    skin_ok=(rc['release_skin'] is not None and abs(rc['release_skin'] - MEAS[tag]['rel_skin']) <= 0.5))
    c9 = {t: rec_ok(t, 10, 30) for t in ('m1n_a', 'm1n_b')}
    c9['pass'] = all(v['time_ok'] and v['shape_ok'] and v['skin_ok'] for v in c9.values()); res['checklist']['⑨'] = c9
    c10 = {'m1': rec_ok('m1', 10, 30), 'm1g_r2': rec_ok('m1g_r2', 0, 20)}
    c10['pass'] = all(v['time_ok'] and v['shape_ok'] and v['skin_ok'] for v in c10.values()); res['checklist']['⑩'] = c10
    rt = R['gpace']['retighten']; g = MEAS['gpace']
    c11 = dict(retighten_s=rt['retighten_s'], first_bin=rt['first_bin'], retighten_bin_ratio=rt['retighten_bin_ratio'], ratio_240_300=rt['ratio_240_300'],
               time_ok=(rt['retighten_s'] is not None and rt['retighten_s'] <= 20), first_ok=(rt['first_bin'] is not None and rt['first_bin'] <= 1.10),
               depth_ok=(rt['retighten_bin_ratio'] is not None and abs(rt['retighten_bin_ratio'] / g['ret_ratio'] - 1) <= 0.10),
               tail_ok=(rt['ratio_240_300'] is not None and abs(rt['ratio_240_300'] / g['r240'] - 1) <= 0.10))
    c11['pass'] = c11['time_ok'] and c11['first_ok'] and c11['depth_ok'] and c11['tail_ok']; res['checklist']['⑪'] = c11
    c12 = {}
    for t in ('m1n_a', 'm1n_b', 'm1g_r2'):
        rc = R[t]['recovery']
        mae = float(np.mean([abs(rc['probe_skin_at'][k] - v) for k, v in MEAS[t]['skin_at'].items() if k in rc['probe_skin_at']]))
        mae_ap = float(np.mean([abs(rc['probe_ap_at'][k] - v) for k, v in MEAS[t]['ap_at'].items() if k in rc['probe_ap_at']]))
        c12[t] = dict(skin_mae=mae, ap_mae=mae_ap, model_skin_at=rc['probe_skin_at'], ok=mae <= 0.5)
    c12['pass'] = all(v['ok'] for k, v in c12.items() if k != 'pass'); res['checklist']['⑫'] = c12
    c13 = {}
    for t in ('m1n_a', 'm1n_b'):
        mm = R[t]['ratio_540_600_model']
        c13[t] = dict(ratio_540_600_model=mm, ratio_540_600_meas=MEAS[t]['r540'], third_level_s=R[t]['third_level_s'],
                      ok=(mm is not None and abs(mm - MEAS[t]['r540']) <= 0.03 and R[t]['third_level_s'] is not None))
    c13['pass'] = all(v['ok'] for k, v in c13.items() if k != 'pass'); res['checklist']['⑬'] = c13
    res['checklist_pass_count'] = sum(1 for k, v in res['checklist'].items() if v.get('pass') is True)
    res['checklist_pass_items'] = [k for k, v in res['checklist'].items() if v.get('pass') is True]
    res['elapsed_s'] = time.time() - t0
    return res, pcm, pint


def v1_recount():
    """v1 (3050e09) on the same 12 items from its frozen outputs — no v1 code is run or modified."""
    fit1 = json.load(open(os.path.join(OUT, 'throttle_fit_v1.json'), encoding='utf-8'))
    c = fit1['candidates'][fit1['adopted']]['checklist']
    pred = json.load(open(os.path.join(OUT, 'night_1003_prediction.json'), encoding='utf-8'))
    pace = json.load(open(os.path.join(SIM, 'out_1003', 'night_1003_prediction_v1_pacing.json'), encoding='utf-8'))
    out = {k: c[k].get('pass') for k in ('①', '②', '③', '④', '⑤', '⑥', '⑦')}
    na, nb = pred['m1_npu']['29.5/fast'], pred['m1_npu']['30.5/fast']
    out['⑨'] = all(10 <= x['recovery_delta003_s'] <= 30 for x in (na, nb))
    g1, g2 = pred['m1_gpu']['29.5'], pred['m1_gpu']['30.5']
    out['⑩'] = (10 <= g1['recovery']['recovery_s'] <= 30) and (0 <= g2['recovery']['recovery_s'] <= 20)   # 1002 run vs r2 run windows
    p = pace['pacing']['30.5']
    out['⑪'] = p['retighten']['retighten_s'] is not None and p['retighten']['retighten_s'] <= 20 and p['reheat_bins_ratio_first12'][0] <= 1.10
    def mae(pr, meas):
        d = {x['t']: x['skin'] for x in pr['probe_skin_at']}
        return float(np.mean([abs(d[k] - v) for k, v in meas.items() if k in d]))
    out['⑫'] = mae(na, MEAS['m1n_a']['skin_at']) <= 0.5 and mae(nb, MEAS['m1n_b']['skin_at']) <= 0.5
    out['⑬'] = abs(na['ratio_540_600'] - MEAS['m1n_a']['r540']) <= 0.03 and abs(nb['ratio_540_600'] - MEAS['m1n_b']['r540']) <= 0.03
    return dict(items=out, count=sum(1 for v in out.values() if v is True),
                detail=dict(rec9=[na['recovery_delta003_s'], nb['recovery_delta003_s']], rec10=[g1['recovery']['recovery_s'], g2['recovery']['recovery_s']],
                            ret11=p['retighten']['retighten_s'], mae12=[mae(na, MEAS['m1n_a']['skin_at']), mae(nb, MEAS['m1n_b']['skin_at'])], r13=[na['ratio_540_600'], nb['ratio_540_600']]),
                source='d1sim/out/throttle_fit_v1.json (①~⑦) · night_1003_prediction.json (⑨⑩⑫⑬) · sim/out_1003/night_1003_prediction_v1_pacing.json (⑪) — frozen v1 outputs')


def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument('--forms', nargs='*', default=['Lk', 'Lb', 'S'])
    ap.add_argument('--write-profiles', action='store_true')
    ap.add_argument('--thermal-only', action='store_true')
    ap.add_argument('--profiles-only', action='store_true', help='write profiles from the existing throttle_fit_v2.json (no refit)')
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    if a.profiles_only:
        results = json.load(open(os.path.join(OUT, 'throttle_fit_v2.json'), encoding='utf-8'))
        write_profiles(results)
        return 0
    tp1 = json.load(open(os.path.join(PROFILES, 'throttle_v1_thermal.json'), encoding='utf-8'))
    t0 = time.time()
    fit_runs = [series(t, s) for t, s in FIT_THERMAL]
    tp, skin_obj, ap_obj = fit_thermal(fit_runs, tp1)
    thermal = dict(params=tp, fit_obj_skin_mse=skin_obj, fit_obj_ap_mse=ap_obj, fit_runs=[f'{t} s{"all" if s is None else s}' for t, s in FIT_THERMAL],
                   errors={f'{t} s{"all" if s is None else s}': dict(role='fit' if (t, s) in FIT_THERMAL else 'half-holdout', **thermal_errors(tp, series(t, s)))
                           for t, s in FIT_THERMAL + HOLD_THERMAL})
    print('thermal', {k: (round(v, 4) if isinstance(v, float) else v) for k, v in tp.items() if k != 'source'}, 'skin_obj', round(skin_obj, 5), 'ap_obj', round(ap_obj, 5), f'({time.time() - t0:.0f}s)', flush=True)
    results = dict(model='v2', thermal=thermal, candidates={}, v1_recount=v1_recount())
    print('v1 recount', results['v1_recount']['items'], 'count', results['v1_recount']['count'], flush=True)
    if a.thermal_only:
        json.dump(results, open(os.path.join(OUT, 'throttle_fit_v2.json'), 'w', encoding='utf-8'), indent=1, ensure_ascii=False, default=str)
        return 0
    # alpha / L0 / P0 / CPU4 controller from the frozen v1 profiles (unchanged values)
    alpha, L0, P0 = {}, {}, {}
    for key, fn in (('GPU_CM', 'GPU_compiledmodel'), ('GPU_INT', 'GPU_interpreter'), ('NPU', 'NPU'), ('CPU4', 'CPU4_interpreter')):
        d = json.load(open(os.path.join(PROFILES, f'throttle_v1_{fn}.json'), encoding='utf-8'))
        alpha[key], L0[key], P0[key] = d['power']['alpha'], d['L0_ms'], d['power']['P0']
        if key == 'CPU4':
            ctrl_cpu = dict(d['ctrl'])
    results['alpha'] = alpha; results['L0_ms'] = L0; results['P0_w'] = P0
    for form in a.forms:
        res, pcm, pint = run_form(form, tp, alpha, L0, P0, ctrl_cpu)
        results['candidates'][form] = res
        print(f'V2-{form}', 'checklist', {k: v.get('pass') for k, v in res['checklist'].items()}, 'count', res['checklist_pass_count'],
              'params', res['n_params_total'], 'sensors', {k: res['fit'][k]['sensor'] for k in ('GPU_INT', 'GPU_CM', 'NPU')}, f'({res["elapsed_s"]:.0f}s)', flush=True)
        res['_params_cm'] = pcm; res['_params_int'] = pint
        json.dump(results, open(os.path.join(OUT, 'throttle_fit_v2.json'), 'w', encoding='utf-8'), indent=1, ensure_ascii=False, default=str)
    order = {'Lk': 0, 'Lb': 1, 'S': 2}
    adopt = max(results['candidates'], key=lambda n: (results['candidates'][n]['checklist_pass_count'], -results['candidates'][n]['n_params_total'], -order[n]))
    results['adopted'] = adopt
    results['v2_status'] = 'v2' if results['candidates'][adopt]['checklist_pass_count'] > results['v1_recount']['count'] else 'v2 미완 (v1 보다 많지 않음)'
    results['adoption_rule'] = '12항목 통과 수 최다 → 동률이면 피팅 파라미터 수 적은 쪽 → V2-Lk → V2-Lb → V2-S (사전 등록 v2 §6)'
    json.dump(results, open(os.path.join(OUT, 'throttle_fit_v2.json'), 'w', encoding='utf-8'), indent=1, ensure_ascii=False, default=str)
    print('adopted', adopt, results['v2_status'])
    if a.write_profiles:
        write_profiles(results)
    return 0


def write_profiles(results):
    adopt = results['adopted']
    tp, thermal = results['thermal']['params'], results['thermal']
    alpha, L0, P0 = results['alpha'], results['L0_ms'], results['P0_w']
    c = results['candidates'][adopt]
    os.makedirs(PROFILES, exist_ok=True)
    json.dump(dict(form=f'V2-{adopt}', **{k: v for k, v in tp.items()}, fit_runs=thermal['fit_runs'], checklist_pass=c['checklist_pass_items'],
                   v2_status=results['v2_status'], status='measured-fit (shared thermal + cooling asymmetry; v2 stage A)'),
              open(os.path.join(PROFILES, 'throttle_v2_thermal.json'), 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
    names = {'GPU_CM': 'GPU_compiledmodel', 'GPU_INT': 'GPU_interpreter', 'NPU': 'NPU', 'CPU4': 'CPU4_interpreter'}
    for key, fn in names.items():
        d = dict(form=f'V2-{adopt}', resource=('GPU' if key.startswith('GPU') else key), engine=('Interpreter 1.4.2' if key in ('GPU_INT', 'CPU4') else 'CompiledModel 2.2.0'),
                 ctrl=c['ctrl'][key], power=dict(P_idle=P_IDLE, P0=P0[key], alpha=alpha[key]), L0_ms=L0[key],
                 fit=(c['fit'].get(key) if key != 'CPU4' else 'v1 controller unchanged (throttle_v1_CPU4_interpreter.json)'),
                 source='d1sim/tools/fit_throttle_v2.py stage B (measured sensor + duty in) + stage C closed loop',
                 status='measured-fit' + (' — kappa_NPU lower bound only (variants kappa_lo / kappa_2 / kappa_inf, tonight N50P)' if key == 'NPU' and adopt == 'Lk' else ''))
        json.dump(d, open(os.path.join(PROFILES, f'throttle_v2_{fn}.json'), 'w', encoding='utf-8'), indent=1, ensure_ascii=False, default=str)
    print('wrote profiles', adopt)


if __name__ == '__main__':
    sys.exit(main())
