"""fit_throttle_v1.py — fit throttle model v1 (d1sim/throttle_v1.py) and run the pre-registered checklist.

Pre-registration: sim/스로틀모형_사전등록_v1.md (mirror d1sim/docs/). Deterministic (fixed Nelder-Mead starts, no RNG).
Reads d1sim/data/trace_v1_*.csv (tools/extract_traces_v1.py). Writes d1sim/out/throttle_fit_v1.json (+ .md) and, with
--write-profiles, d1sim/profiles/throttle_v1_*.json.

Stages (prereg §3):
  A  thermal (shared): measured 1 s power -> SKIN, AP      fit runs: m2_H1 s0 + n1300 + c1p_r1 + c600_r1 ; holdout: the rest
  B  controllers (per resource/engine): measured sensor -> 10 s latency ratio   (open loop, reported only)
  C  closed loop for every run from its own T_start / A0 / duty pattern -> checklist ①~⑧ and the per-resource criteria (§4·§5)
Two candidates share the code: M-P (sensor AP) and M-S (sensor SKIN).

  py d1sim/tools/fit_throttle_v1.py [--write-profiles]
"""
from __future__ import annotations

import argparse
import csv
import itertools
import json
import math
import os
import statistics as st
import sys

import numpy as np
from scipy.optimize import minimize

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, ROOT)
from d1sim.throttle_v1 import Controller, NpuController, ThermalV1, bins_ratio, onset_time_ref, simulate  # noqa: E402

DATA = os.path.join(ROOT, 'd1sim', 'data')
OUT = os.path.join(ROOT, 'd1sim', 'out')
PROFILES = os.path.join(ROOT, 'd1sim', 'profiles')
SIM = r'C:\Users\rhoyo\OneDrive\문서\Mine\26-2\산공학회\D1_ondevice\sim'
MAN = json.load(open(os.path.join(DATA, 'trace_v1_manifest.json'), encoding='utf-8'))

TAU_F, TAU_A, P_IDLE = 34.4, 17.0, 0.581      # [D] 평가층_사전등록_v1:47·:49 · NPU_FORMAL_RESULTS:239
D_ON, U_MAX_GPU, U_CAP_NPU = 10.0, 0.7, 0.5    # [E] prereg §2
FIT_THERMAL = [('m2_H1', 0), ('n1300', 0), ('c1p_r1', 0), ('c600_r1', 0)]
HOLD_THERMAL = [('m2_H2', 0), ('m1', None), ('c1p_r2', 0), ('c1a', 0), ('m3', 0), ('c600_r2', 0), ('m2r_H1', 0), ('m2r_H2', 0)]
# controller fit run per resource/engine; half-holdout runs
CTRL = {
    'GPU_CM': dict(res='GPU', fit=('m2_H1', 0), hold=[('m2_H2', 0), ('m1', 1)]),
    'GPU_INT': dict(res='GPU', fit=('c1p_r1', 0), hold=[('c1p_r2', 0), ('c1a', 0), ('m3', 0)]),
    'NPU': dict(res='NPU', fit=('n1300', 0), hold=[('m2r_H1', 0), ('m2r_H2', 0)]),
    'CPU4': dict(res='CPU4', fit=('c600_r1', 0), hold=[('c600_r2', 0)]),
}
ENGINE_OF = {'m2_H1': 'CM', 'm2_H2': 'CM', 'm1': 'CM', 'n1300': 'CM', 'm2r_H1': 'CM', 'm2r_H2': 'CM', 'm2_C1': 'CM', 'm2_C2': 'CM',
             'm2r_C1': 'CM', 'm2r_C2': 'CM', 'c1p_r1': 'INT', 'c1p_r2': 'INT', 'c1a': 'INT', 'm3': 'INT', 'c600_r1': 'INT', 'c600_r2': 'INT'}


# ============================================================ data
def fl(v):
    return None if v in ('', None) else float(v)


def rows1(tag, seg=None):
    rr = list(csv.DictReader(open(os.path.join(DATA, f'trace_v1_{tag}.csv'), encoding='utf-8')))
    if seg is not None:
        rr = [r for r in rr if int(r['seg']) == seg]
    return rr


def series(tag, seg=None):
    """Concatenated 1 s rows (forward-filled power/temps). Returns dict of np arrays + seg ids."""
    rr = rows1(tag, seg)
    P, SK, AP, segs, act, lat = [], [], [], [], [], []
    lp = lsk = lap = None
    for r in rr:
        p, sk, ap = fl(r['power_w']), fl(r['SKIN']), fl(r['AP'])
        lp = p if p is not None else lp
        lsk = sk if sk is not None else lsk
        lap = ap if ap is not None else lap
        P.append(lp); SK.append(lsk); AP.append(lap); segs.append(int(r['seg'])); act.append(int(r['n_inf']) > 0); lat.append(fl(r['lat_med_ms']))
    # back-fill leading None
    for arr in (P, SK, AP):
        first = next((x for x in arr if x is not None), None)
        for i in range(len(arr)):
            if arr[i] is None:
                arr[i] = first
            else:
                break
    res = [RES_OF[tag][g] for g in segs]
    return dict(P=np.array(P, float), SKIN=np.array(SK, float), AP=np.array(AP, float), seg=np.array(segs), active=act,
                lat=lat, T_start=SK[0], A0=AP[0] - SK[0], res=res)


def bins10(tag, seg):
    rr = [r for r in csv.DictReader(open(os.path.join(DATA, f'trace_v1_10s_{tag}.csv'), encoding='utf-8')) if int(r['seg']) == seg]
    ref = next(r for r in rr if r['t_s'] == '-1')
    b = [(int(r['t_s']), fl(r['lat_med_ms']), int(r['n_inf']), fl(r['power_w'])) for r in rr if r['t_s'] != '-1']
    return dict(ref=fl(ref['lat_med_ms']), ref_pw=fl(ref['power_w']), bins=b, ratio=[(t, (m / fl(ref['lat_med_ms'])) if m else None) for t, m, n, pw in b])


def schedule_of(tag, resources):
    man = MAN[tag]
    sch = []
    for i, seg in enumerate(man['segments']):
        if i > 0:
            sch.append((f't{i}', None, None, man['transitions'][i - 1]['duration_s']))
        flags = [int(r['n_inf']) > 0 for r in rows1(tag, i)]
        sch.append((i, resources[i], flags, seg['duration_s']))
    return sch


RES_OF = {'m1': ['GPU', 'GPU', 'GPU'], 'm2_C1': ['GPU', 'NPU'], 'm2_H1': ['GPU', 'NPU'], 'm2_H2': ['GPU', 'NPU'], 'm2_C2': ['GPU', 'NPU'],
          'm2r_C1': ['NPU', 'GPU'], 'm2r_H1': ['NPU', 'GPU'], 'm2r_H2': ['NPU', 'GPU'], 'm2r_C2': ['NPU', 'GPU'],
          'n1300': ['NPU'], 'c1p_r1': ['GPU'], 'c1p_r2': ['GPU'], 'c1a': ['GPU'], 'm3': ['GPU'], 'c600_r1': ['CPU4'], 'c600_r2': ['CPU4']}


# ============================================================ Stage A — thermal
def thermal_run(tp, S):
    th = ThermalV1(tp, S['T_start'], S['A0'])
    sk, ap = [], []
    for P, r in zip(S['P'], S['res']):
        sk.append(th.skin); ap.append(th.ap)
        th.advance(1.0, float(P), r)
    return np.array(sk), np.array(ap)


def fit_thermal(runs):
    def obj(x):
        G_f, G_s, tau_s = x
        if not (0 <= G_f <= 5 and 0 <= G_s <= 5 and 60 <= tau_s <= 3000):
            return 1e6
        tp = dict(tau_f=TAU_F, G_f=G_f, G_s=G_s, tau_s=tau_s, tau_a=TAU_A, G_a=0.0, P_idle=P_IDLE)
        return float(np.mean([np.mean((thermal_run(tp, S)[0] - S['SKIN']) ** 2) for S in runs]))
    best = None
    for start in itertools.product([0.5, 1.0], [1.5, 3.0], [200.0, 600.0]):
        r = minimize(obj, np.array(start), method='Nelder-Mead', options=dict(maxiter=3000, xatol=1e-4, fatol=1e-9))
        if best is None or r.fun < best.fun:
            best = r
    G_f, G_s, tau_s = map(float, best.x)
    tp = dict(tau_f=TAU_F, G_f=G_f, G_s=G_s, tau_s=tau_s, tau_a=TAU_A, G_a=0.0, P_idle=P_IDLE)
    # G_a closed form PER RESOURCE (r2) and tau_a on a grid (r3: AP-SKIN gap builds slower than the 17 s AP heating tau [D] —
    # r2 left the model AP ~1 C too high in the first 300 s of every run; NPU step 1 -90 s, M3 onset -110 s)
    best_a = None
    for tau_a in (17.0, 30.0, 50.0, 80.0, 120.0, 180.0, 250.0):
        acc, sse = {}, 0.0
        hv_all = []
        for S in runs:
            sk, _ = thermal_run(tp, S)
            h, hv = 0.0, []
            for P in S['P']:
                hv.append(h)
                dP = max(0.0, P - P_IDLE)
                h = dP + (h - dP) * math.exp(-1.0 / tau_a)
            hv = np.array(hv)
            resid = S['AP'] - (sk + S['A0'])
            r = S['res'][0]
            a = acc.setdefault(r, [0.0, 0.0])
            a[0] += float((hv * resid).sum()); a[1] += float((hv * hv).sum())
            hv_all.append((r, hv, resid))
        G = {r: (n / d if d else 0.0) for r, (n, d) in acc.items()}
        sse = sum(float(((resid - G[r] * hv) ** 2).sum()) for r, hv, resid in hv_all)
        if best_a is None or sse < best_a[0]:
            best_a = (sse, tau_a, G)
    tp['tau_a'] = best_a[1]
    tp['G_a'] = best_a[2]
    tp['tau_a_source'] = 'r3 grid {17,30,50,80,120,180,250} s on pooled AP residual (17 s [D] was r1·r2)'
    return tp, float(best.fun)


def thermal_errors(tp, S):
    sk, ap = thermal_run(tp, S)
    return dict(skin_mae=float(np.mean(np.abs(sk - S['SKIN']))), ap_mae=float(np.mean(np.abs(ap - S['AP']))),
                skin_end_model=float(sk[-1]), skin_end_meas=float(S['SKIN'][-1]), skin_max_abs_err=float(np.max(np.abs(sk - S['SKIN']))))


# ============================================================ Stage B — controllers (measured sensor in)
def ctrl_bins(cp, res, sensor_series, active):
    """Run a controller over a measured sensor series (1 s). Returns 10 s bin medians of ratio over active seconds."""
    class _Th:  # minimal thermal stand-in exposing .ap/.skin
        pass
    c = NpuController(cp) if res == 'NPU' else Controller(cp)
    ratios = []
    th = _Th()
    for T, a in zip(sensor_series, active):
        th.ap = th.skin = float(T)
        ratios.append((1.0 / c.s) if a else None)
        c.step(1.0, th, bool(a))
    n = len(ratios) // 10
    return [(k * 10, (lambda v: v[len(v) // 2] if v else None)(sorted(x for x in ratios[k * 10:(k + 1) * 10] if x is not None))) for k in range(n)]


def ratio_obj(pred, meas):
    e = [(p / m - 1) ** 2 for (t, p), (t2, m) in zip(pred, meas) if p is not None and m is not None]
    return float(np.mean(e)) if e else 1e6


def fit_controller(key, sensor, S, B):
    res = CTRL[key]['res']
    T = S['AP'] if sensor == 'AP' else S['SKIN']
    meas = B['ratio']
    if res == 'NPU':
        names = ['T1', 'T2', 'a1', 'a2', 'K']
        starts = {'AP': [[42.3, 42.7], [44.0, 44.4], [0.08], [0.04], [3e-5, 1e-4]], 'SKIN': [[38.2, 38.5], [39.8, 40.1], [0.08], [0.04], [3e-5, 1e-4]]}[sensor]
        bounds = [(30, 50), (30, 50), (0, 0.5), (0, 0.5), (0, 0.01)]

        def mk(x):
            return dict(sensor=sensor, d_on=D_ON, T1=x[0], T2=x[1], a1=x[2], a2=x[3], K=x[4], u_cap=U_CAP_NPU, release='fast', T_off=None, T_skin_rel=None)
    else:
        if res == 'CPU4':
            names = ['T_on', 'K', 'T_set', 'u_max']
            starts = {'AP': [[41.0, 42.5], [0.005, 0.03], [40.0, 42.0], [0.28, 0.32]], 'SKIN': [[34.5, 35.5], [0.005, 0.03], [36.0, 38.0], [0.28, 0.32]]}[sensor]
            bounds = [(30, 50), (0, 1), (30, 50), (0.05, 0.7)]
        else:
            names = ['T_on', 'K', 'T_set']
            starts = {'AP': [[41.5, 42.5], [0.002, 0.01], [40.5, 41.5]], 'SKIN': [[36.5, 37.5], [0.002, 0.01], [37.5, 38.5]]}[sensor]
            bounds = [(30, 50), (0, 1), (30, 50)]

        def mk(x):
            d = dict(sensor=sensor, d_on=D_ON, T_on=x[0], K=x[1], T_set=x[2], u_max=(x[3] if res == 'CPU4' else U_MAX_GPU))
            d['T_off'] = min(d['T_set'], d['T_on']) - 2.0      # provisional; GPU_CM refits on M1 below
            return d

    def obj(x):
        for v, (lo, hi) in zip(x, bounds):
            if not lo <= v <= hi:
                return 1e6
        cp = mk(x)
        if res == 'NPU' and cp['T2'] < cp['T1']:
            return 1e6
        if res != 'NPU' and cp['T_on'] < cp['T_set']:
            return 1e6   # r2: arming below the setpoint is meaningless (d_on would never act)
        cp['T_off'] = -1e9 if res == 'NPU' else cp['T_off']   # never release inside the fit run
        if res != 'NPU':
            cp = dict(cp, T_off=-1e9)
        return ratio_obj(ctrl_bins(cp, res, T, S['active']), meas)
    best = None
    for start in itertools.product(*starts):
        r = minimize(obj, np.array(start, float), method='Nelder-Mead', options=dict(maxiter=4000, xatol=1e-5, fatol=1e-10))
        if best is None or r.fun < best.fun:
            best = r
    cp = mk(list(map(float, best.x)))
    return cp, float(best.fun), dict(zip(names, map(float, best.x)))


def fit_T_off_on_m1(cp, sensor):
    """GPU_CM release threshold from the M1 probe (measured sensor in): the T_off interval that yields recovery at 20 s
    (judge rule) -> midpoint. Returns (T_off, interval)."""
    S = series('m1')
    T = S['AP'] if sensor == 'AP' else S['SKIN']
    seg = S['seg']
    judge = json.load(open(os.path.join(SIM, 'out_1002', 'M1_judge.json'), encoding='utf-8'))
    good = []
    for cand in np.arange(34.0, 44.01, 0.1):
        c = dict(cp, T_off=float(cand))
        rb = ctrl_bins(c, 'GPU', T, S['active'])
        # probe bins = bins whose start lies in seg 2
        idx2 = [i for i in range(len(T)) if seg[i] == 2]
        if not idx2:
            break
        t2 = idx2[0]
        probe = [(t - t2, m) for t, m in rb if t >= t2]
        # ref_d10 = median of model ratio in seg 0 (= 1 when unthrottled)
        pr = [m for t, m in probe]
        k_rec = None
        for k in range(0, len(pr) - 3):
            if all(x is not None and x <= 1.10 for x in pr[k:k + 4]):
                k_rec = k
                break
        if k_rec is not None and 10 * k_rec == judge['recovery']['recovery_s']:
            good.append(float(cand))
    if not good:
        return None, []
    return float(round((min(good) + max(good)) / 2, 2)), [min(good), max(good)]


# ============================================================ Stage C — closed loop
def params_for(engine, tp, ctrl, power, L0):
    gkey = 'GPU_CM' if engine == 'CM' else 'GPU_INT'
    return dict(thermal=tp, ctrl={'GPU': ctrl[gkey], 'NPU': ctrl['NPU'], 'CPU4': ctrl['CPU4']},
                power={'GPU': power[gkey], 'NPU': power['NPU'], 'CPU4': power['CPU4']},
                L0={'GPU': L0[gkey], 'NPU': L0['NPU'], 'CPU4': L0['CPU4']})


def closed(tag, params):
    S = series(tag)
    return simulate(params, schedule_of(tag, RES_OF[tag]), S['T_start'], S['A0'], dt=1.0), S


def win_med(rows, seg, a, b):
    v = sorted(r['ratio'] for r in rows if r['seg'] == seg and a <= r['t'] < b and r['ratio'] is not None)
    return v[len(v) // 2] if v else None


def win_mean_P(rows, seg, a, b):
    v = [r['P'] for r in rows if r['seg'] == seg and a <= r['t'] < b]
    return float(np.mean(v)) if v else None


def temps_err(rows, S):
    """SKIN/AP MAE between closed-loop rows and measured 1 s rows (segment rows only, in order)."""
    rr = [r for r in rows if not str(r['seg']).startswith('t')]
    n = min(len(rr), len(S['SKIN']))
    sk = np.array([r['skin'] for r in rr[:n]]); ap = np.array([r['ap'] for r in rr[:n]])
    return dict(skin_mae=float(np.mean(np.abs(sk - S['SKIN'][:n]))), ap_mae=float(np.mean(np.abs(ap - S['AP'][:n]))),
                skin_end_model=float(sk[-1]), skin_end_meas=float(S['SKIN'][n - 1]))


def step1_time(bins, level=1.045):
    vals = [(t, m) for t, m in bins if m is not None]
    for i, (t, m) in enumerate(vals):
        if t >= 30 and m >= level and i + 3 < len(vals) and all(vals[j][1] >= level for j in range(i + 1, i + 4)):
            return t
    return None


def gpu_metrics(rows, seg, B, S, L):
    mb = bins_ratio(rows, seg)
    on_mod, on_meas = onset_time_ref(mb, 1.0), onset_time_ref(B['ratio'], 1.0)
    out = dict(onset_model_s=on_mod, onset_meas_s=on_meas, onset_err_s=(on_mod - on_meas) if (on_mod is not None and on_meas is not None) else 'mismatch')
    for a, b in ((540, 600), (1000, 1200), (1000, 1300)):
        if b <= L:
            mm = win_med(rows, seg, a, b)
            me = [m for t, m in B['ratio'] if a <= t < b and m is not None]
            me = float(np.mean(me)) if me else None
            out[f'ratio_{a}_{b}_model'] = mm; out[f'ratio_{a}_{b}_meas'] = me
            out[f'ratio_{a}_{b}_err_pct'] = 100 * (mm / me - 1) if (mm and me) else None
    p0 = win_mean_P(rows, seg, 0, 30)
    p5 = win_mean_P(rows, seg, 540, 600)
    out['power_ratio_540_600_model'] = (p5 / p0) if (p0 and p5) else None
    pm = [pw for t, m, n, pw in B['bins'] if 540 <= t < 600 and pw is not None]
    out['power_ratio_540_600_meas'] = (float(np.mean(pm)) / B['ref_pw']) if (pm and B['ref_pw']) else None
    out['end60_ratio_model'] = win_med(rows, seg, L - 60, L)
    me = [m for t, m in B['ratio'] if L - 60 <= t < L and m is not None]
    out['end60_ratio_meas'] = float(np.mean(me)) if me else None
    e = [abs(mm - m) for (t, mm), (t2, m) in zip(mb, B['ratio']) if mm is not None and m is not None]
    out['ratio_mae_10s'] = float(np.mean(e)) if e else None
    out['lat_mae_ms_10s'] = out['ratio_mae_10s'] * B['ref'] if out['ratio_mae_10s'] is not None else None
    return out


def npu_metrics(rows, seg, B, S, L):
    mb = bins_ratio(rows, seg)
    out = dict(step1_model_s=step1_time(mb), step1_meas_s=step1_time(B['ratio']),
               step2_model_s=onset_time_ref(mb, 1.0), step2_meas_s=onset_time_ref(B['ratio'], 1.0))
    out['step1_err_s'] = (out['step1_model_s'] - out['step1_meas_s']) if None not in (out['step1_model_s'], out['step1_meas_s']) else 'mismatch'
    out['step2_err_s'] = (out['step2_model_s'] - out['step2_meas_s']) if None not in (out['step2_model_s'], out['step2_meas_s']) else 'mismatch'
    # step levels: median ratio between step1 and step2 (model vs meas), and 540~600
    s1, s2 = out['step1_meas_s'], out['step2_meas_s']
    if s1 is not None and s2 is not None and s2 > s1 + 20:
        mm = win_med(rows, seg, s1 + 10, s2)
        me = [m for t, m in B['ratio'] if s1 + 10 <= t < s2 and m is not None]
        out['level1_model'] = mm; out['level1_meas'] = float(np.mean(me)) if me else None
        out['level1_err'] = (mm - out['level1_meas']) if (mm and out['level1_meas']) else None
    mm = win_med(rows, seg, 540, 600)
    me = [m for t, m in B['ratio'] if 540 <= t < 600 and m is not None]
    out['ratio_540_600_model'] = mm; out['ratio_540_600_meas'] = float(np.mean(me)) if me else None
    out['ratio_540_600_err'] = (mm - out['ratio_540_600_meas']) if (mm and out['ratio_540_600_meas']) else None
    out['end60_ratio_model'] = win_med(rows, seg, L - 60, L)
    me = [m for t, m in B['ratio'] if L - 60 <= t < L and m is not None]
    out['end60_ratio_meas'] = float(np.mean(me)) if me else None
    out['end60_err'] = (out['end60_ratio_model'] - out['end60_ratio_meas']) if (out['end60_ratio_model'] and out['end60_ratio_meas']) else None
    st2 = next((r['t'] for r in rows if r['seg'] == seg and r['status'] >= 2), None)
    st1 = next((r['t'] for r in rows if r['seg'] == seg and r['status'] >= 1), None)
    out['status1_model_s'] = st1; out['status2_model_s'] = st2
    e = [abs(mm - m) for (t, mm), (t2, m) in zip(mb, B['ratio']) if mm is not None and m is not None]
    out['ratio_mae_10s'] = float(np.mean(e)) if e else None
    return out


def cpu_metrics(rows, seg, B, S, L):
    mb = bins_ratio(rows, seg)
    on_mod, on_meas = onset_time_ref(mb, 1.0), onset_time_ref(B['ratio'], 1.0)
    mm = win_med(rows, seg, 240, 600)
    me = [m for t, m in B['ratio'] if 240 <= t < 600 and m is not None]
    me = float(np.mean(me)) if me else None
    return dict(onset_model_s=on_mod, onset_meas_s=on_meas, onset_err_s=(on_mod - on_meas) if None not in (on_mod, on_meas) else 'mismatch',
                plateau_240_600_model=mm, plateau_240_600_meas=me, plateau_err_pct=100 * (mm / me - 1) if (mm and me) else None,
                first10_meas=B['ratio'][0][1], first10_model=mb[0][1])


def m1_metrics(rows):
    ref = win_med(rows, 0, 0, 60)
    pb = bins_ratio(rows, 2)
    pr = [None if m is None else m / ref for t, m in pb]
    k_rec, shape, frac = None, '중도절단', None
    for k in range(0, len(pr) - 3):
        if all(x is not None and x <= 1.10 for x in pr[k:k + 4]):
            k_rec = k
            break
    if k_rec is not None and k_rec > 0:
        total = pr[0] - pr[k_rec]
        steps = [pr[j - 1] - pr[j] for j in range(1, k_rec + 1)]
        frac = (max(steps) / total) if total > 0 else None
        shape = '계단형' if (frac is not None and frac >= 0.5) else '점진형'
    elif k_rec == 0:
        shape = '즉시'
    skin_probe = [r for r in rows if r['seg'] == 2]
    return dict(ref_d10_model=ref, probe_bins_ratio=pr[:8], recovery_s=(10 * k_rec if k_rec is not None else None), shape=shape, step_fraction=frac,
                probe_start_skin_model=skin_probe[0]['skin'], probe_start_ap_model=skin_probe[0]['ap'],
                probe_20s_ap_model=skin_probe[20]['ap'] if len(skin_probe) > 20 else None)


def m2_metrics(grp, params_cm, judge):
    v, first, second, skin0 = {}, {}, {}, {}
    for arm in ('C1', 'H1', 'H2', 'C2'):
        rows, S = closed(f'{grp}_{arm}', params_cm)
        v[arm] = win_med(rows, 1, 0, 60)
        first[arm] = win_med(rows, 1, 0, 10)
        second[arm] = win_med(rows, 1, 10, 20)
        skin0[arm] = next(r['skin'] for r in rows if r['seg'] == 1)
    cmean = (v['C1'] + v['C2']) / 2
    vm = judge['v_ms']
    cmean_meas = (vm['C1'] + vm['C2']) / 2
    meas_rel = {a: vm[a] / cmean_meas for a in ('H1', 'H2')}
    tol = max(2 * judge['s_C'], 0.01)
    lo, hi = min(meas_rel.values()) - tol, max(meas_rel.values()) + tol
    pred_rel = {a: v[a] / cmean for a in ('H1', 'H2')}
    in_range = all(lo <= pred_rel[a] <= hi for a in pred_rel)
    first_rel = {a: first[a] / cmean for a in ('H1', 'H2')}
    second_rel = {a: second[a] / cmean for a in ('H1', 'H2')}
    jb = {a: judge['arms'][a]['bins10'] for a in ('H1', 'H2')}
    meas_first = {a: jb[a][0]['median_ms'] / cmean_meas for a in jb}
    meas_second = {a: jb[a][1]['median_ms'] / cmean_meas for a in jb}
    if grp == 'm2':   # NPU victim: first bin < later bins (direction)
        dir_ok = all(first_rel[a] < second_rel[a] for a in first_rel)
    else:             # GPU victim: first bin <= 1.10
        dir_ok = all(first_rel[a] <= 1.10 for a in first_rel)
    return dict(victim_rel_pred=pred_rel, victim_rel_meas=meas_rel, range=[lo, hi], in_range=in_range,
                first10_rel_pred=first_rel, first10_rel_meas=meas_first, bin_10_20_rel_pred=second_rel, bin_10_20_rel_meas=meas_second,
                direction_ok=dir_ok, victim_start_skin_model=skin0,
                victim_start_skin_meas={a: judge['arms'][a]['victim_start_thermal']['SKIN'] for a in ('C1', 'H1', 'H2', 'C2')})


def sixty_s(params):
    out = {}
    for res in ('GPU', 'NPU', 'CPU4'):
        rows = simulate(params, [(0, res, True, 60)], 30.3, -1.0)
        b = bins_ratio(rows, 0)
        first30 = float(np.median([r['ratio'] for r in rows[:30]]))
        out[res] = dict(last10_over_first30_pct=100 * (b[5][1] / first30 - 1), skin_end=rows[-1]['skin'])
    return out


def alpha_fit(B):
    xs, ys = [], []
    ref, p0 = B['ref'], B['ref_pw']
    for t, m, n, pw in B['bins']:
        if m is None or pw is None or p0 is None:
            continue
        s = ref / m
        if s <= 0.95 and pw > P_IDLE and p0 > P_IDLE:
            xs.append(math.log(s)); ys.append(math.log((pw - P_IDLE) / (p0 - P_IDLE)))
    if len(xs) < 3:
        return None, len(xs)
    xs, ys = np.array(xs), np.array(ys)
    return float((xs * ys).sum() / (xs * xs).sum()), len(xs)


# ============================================================ main
def run_candidate(sensor, tp, alpha, L0, P0):
    ctrl, fitinfo = {}, {}
    for key in CTRL:
        tag, seg = CTRL[key]['fit']
        S, B = series(tag, seg), bins10(tag, seg)
        cp, obj, x = fit_controller(key, sensor, S, B)
        fitinfo[key] = dict(fit_obj=obj, x=x, fit_run=f'{tag} s{seg}')
        ctrl[key] = cp
    # release thresholds
    toff, interval = fit_T_off_on_m1(ctrl['GPU_CM'], sensor)
    ctrl['GPU_CM']['T_off'] = toff if toff is not None else ctrl['GPU_CM']['T_set'] - 2.0
    ctrl['GPU_CM']['T_off_source'] = f'M1 probe recovery 20 s interval {interval} (measured sensor in)' if toff is not None else 'placeholder T_set-2 (no admissible T_off)'
    ctrl['GPU_INT']['T_off'] = ctrl['GPU_INT']['T_set'] - (ctrl['GPU_CM']['T_set'] - ctrl['GPU_CM']['T_off'])
    ctrl['GPU_INT']['T_off_source'] = 'same offset below T_set as GPU_CM [E] — no Interpreter recovery data'
    ctrl['CPU4']['T_off'] = ctrl['CPU4']['T_set'] - 2.0
    ctrl['CPU4']['T_off_source'] = 'placeholder T_set-2 [E] — no CPU recovery data'
    ctrl['NPU']['T_off'] = ctrl['NPU']['T1'] - 0.5
    ctrl['NPU']['T_skin_rel'] = None
    ctrl['NPU']['release_source'] = 'R-fast T_off = T1-0.5 [E] / R-skin T_skin_rel set from the SKIN at step 1 [E] — untested, tonight M1-NPU'
    power = {k: dict(P_idle=P_IDLE, P0=P0[k], alpha=alpha[k]) for k in CTRL}
    pcm, pint = params_for('CM', tp, ctrl, power, L0), params_for('INT', tp, ctrl, power, L0)
    # R-skin threshold: model SKIN at the moment NPU step 1 arms in the n1300 closed loop (set after a first pass)
    rows, S = closed('n1300', pcm)
    t_arm = next((r['t'] for r in rows if r['ratio'] and r['ratio'] >= 1 + 0.5 * ctrl['NPU']['a1']), None)
    ctrl['NPU']['T_skin_rel'] = float(rows[int(t_arm)]['skin']) if t_arm is not None else None
    res = dict(sensor=sensor, ctrl=ctrl, fit=fitinfo, runs={}, checklist={})
    # per-run closed loop
    for tag in ('c1p_r1', 'c1p_r2', 'c1a', 'm3', 'm2_H1', 'm2_H2', 'm1', 'n1300', 'm2r_H1', 'm2r_H2', 'c600_r1', 'c600_r2'):
        params = pcm if ENGINE_OF[tag] == 'CM' else pint
        rows, S = closed(tag, params)
        seg = 1 if tag == 'm1' else 0
        B = bins10(tag, seg)
        L = MAN[tag]['segments'][seg]['duration_s']
        r0 = RES_OF[tag][seg]
        if r0 == 'GPU':
            m = gpu_metrics(rows, seg, B, S, L)
        elif r0 == 'NPU':
            m = npu_metrics(rows, seg, B, S, L)
        else:
            m = cpu_metrics(rows, seg, B, S, L)
        m.update(temps_err(rows, S))
        if tag == 'm1':
            m['m1'] = m1_metrics(rows)
        if tag == 'c1a':
            sk420 = next(r['skin'] for r in rows if r['t'] == 420); sk1200 = next(r['skin'] for r in rows if r['t'] == 1200)
            m['skin_rise_420_1200_model'] = sk1200 - sk420
            m['skin_rise_420_1200_meas'] = float(S['SKIN'][1200] - S['SKIN'][420])
        m['role'] = 'fit' if any(tag == CTRL[k]['fit'][0] for k in CTRL) else 'half-holdout'
        res['runs'][tag] = m
    judges = {'m2': json.load(open(os.path.join(SIM, 'out_1002', 'M2_npu_judge.json'), encoding='utf-8')),
              'm2r': json.load(open(os.path.join(SIM, 'out_1002', 'M2r_gpu_judge.json'), encoding='utf-8'))}
    res['coupling'] = {g: m2_metrics(g, pcm, judges[g]) for g in ('m2', 'm2r')}
    res['sixty_s'] = sixty_s(pcm)
    # ---- checklist ----
    R = res['runs']
    def ok_on(x, lim):
        return isinstance(x, (int, float)) and abs(x) <= lim
    c1_runs = ['c1a', 'm2_H1', 'm2_H2', 'm1']
    c1 = dict(onset=all(ok_on(R[t]['onset_err_s'], 10) for t in c1_runs),
              plateau=all(ok_on(R[t].get('ratio_540_600_err_pct'), 10) for t in c1_runs) and ok_on(R['c1a'].get('ratio_1000_1300_err_pct'), 10)
              and ok_on(R['m1'].get('ratio_1000_1200_err_pct'), 10),
              power=all(0.3 <= (R[t]['power_ratio_540_600_model'] or 0) <= 0.5 for t in c1_runs),
              skin_rise=R['c1a']['skin_rise_420_1200_model'] >= 0.5)
    c1['pass'] = all(c1.values())
    res['checklist']['①'] = c1
    res['checklist']['②'] = dict(onset_err_s=R['m3']['onset_err_s'], **{'pass': ok_on(R['m3']['onset_err_s'], 10)})
    npu_runs = ['n1300', 'm2r_H1', 'm2r_H2']
    c3 = dict(step1=all(ok_on(R[t]['step1_err_s'], 20) for t in npu_runs), step2=all(ok_on(R[t]['step2_err_s'], 20) for t in npu_runs),
              level=all(ok_on(R[t].get('ratio_540_600_err'), 0.02) for t in npu_runs), end60=ok_on(R['n1300']['end60_err'], 0.03),
              status2=ok_on((R['n1300']['status2_model_s'] or 1e9) - 799.5, 60))
    c3['pass'] = all(c3.values())
    res['checklist']['③'] = c3
    c4 = dict(onset=all(ok_on(R[t]['onset_err_s'], 20) for t in ('c600_r1', 'c600_r2')), plateau=all(ok_on(R[t]['plateau_err_pct'], 10) for t in ('c600_r1', 'c600_r2')),
              first10_boost_reproduced=False)
    c4['pass'] = c4['onset'] and c4['plateau']
    res['checklist']['④'] = c4
    cp5 = res['coupling']
    c5 = dict(npu_range=cp5['m2']['in_range'], gpu_range=cp5['m2r']['in_range'], npu_dir=cp5['m2']['direction_ok'], gpu_dir=cp5['m2r']['direction_ok'])
    c5['pass'] = all(c5.values())
    res['checklist']['⑤'] = c5
    m1 = R['m1']['m1']
    c6 = dict(recovery_s=m1['recovery_s'], shape=m1['shape'], **{'pass': m1['recovery_s'] is not None and abs(m1['recovery_s'] - 20) <= 10 and m1['shape'] == '계단형'}, note='1런 — 검증 없음')
    res['checklist']['⑥'] = c6
    sx = res['sixty_s']
    c7 = dict(GPU=sx['GPU']['last10_over_first30_pct'], NPU=sx['NPU']['last10_over_first30_pct'], CPU4=sx['CPU4']['last10_over_first30_pct'])
    c7['pass'] = c7['GPU'] <= 5 and c7['NPU'] <= 5 and 5 <= c7['CPU4'] <= 30
    res['checklist']['⑦'] = c7
    res['checklist']['⑧'] = dict(note='전환비용 표는 프로파일 device_profile_S26_v1.yaml switch_cost_s (열 모형 아님)', **{'pass': None})
    res['checklist_pass_count'] = sum(1 for k, v in res['checklist'].items() if v.get('pass') is True)
    return res, pcm, pint


def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument('--write-profiles', action='store_true')
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    # ---- Stage A
    fit_runs = [series(t, s) for t, s in FIT_THERMAL]
    tp, obj = fit_thermal(fit_runs)
    thermal = dict(params=tp, fit_obj_mse=obj, fit_runs=[f'{t} s{s}' for t, s in FIT_THERMAL],
                   errors={f'{t} s{"all" if s is None else s}': dict(role='fit' if (t, s) in FIT_THERMAL else 'half-holdout', **thermal_errors(tp, series(t, s)))
                           for t, s in FIT_THERMAL + HOLD_THERMAL})
    print('thermal', {k: (round(v, 4) if isinstance(v, float) else v) for k, v in tp.items()}, 'obj', round(obj, 5), flush=True)
    # alpha / L0 / P0 per resource-engine from the controller fit run
    alpha, L0, P0, alpha_n = {}, {}, {}, {}
    for key in CTRL:
        tag, seg = CTRL[key]['fit']
        B = bins10(tag, seg)
        alpha[key], alpha_n[key] = alpha_fit(B)
        if alpha[key] is None:
            alpha[key] = 1.519   # [D] v0 value as fallback (flagged)
        L0[key], P0[key] = B['ref'], B['ref_pw']
    print('alpha', alpha, 'n', alpha_n, 'L0', L0, 'P0', P0, flush=True)
    results = dict(thermal=thermal, alpha=alpha, alpha_n_bins=alpha_n, L0_ms=L0, P0_w=P0, candidates={})
    for sensor, name in (('AP', 'M-P'), ('SKIN', 'M-S')):
        res, pcm, pint = run_candidate(sensor, tp, alpha, L0, P0)
        results['candidates'][name] = res
        print(name, 'checklist', {k: v.get('pass') for k, v in res['checklist'].items()}, 'count', res['checklist_pass_count'], flush=True)
        results['candidates'][name]['_params_cm'] = pcm
        results['candidates'][name]['_params_int'] = pint
    # adoption rule: more checklist passes; tie -> ⑤ then ① then ②
    def score(n):
        c = results['candidates'][n]['checklist']
        return (results['candidates'][n]['checklist_pass_count'], c['⑤']['pass'], c['①']['pass'], c['②']['pass'])
    adopt = max(results['candidates'], key=score)
    results['adopted'] = adopt
    results['adoption_rule'] = '체크리스트 통과 수 최대, 동률이면 ⑤ → ① → ② 순 (사전 등록 §2 주 후보 M-P 는 규칙에 들어가지 않음)'
    json.dump(results, open(os.path.join(OUT, 'throttle_fit_v1.json'), 'w', encoding='utf-8'), indent=1, ensure_ascii=False, default=str)
    print('adopted', adopt)
    if a.write_profiles:
        c = results['candidates'][adopt]
        os.makedirs(PROFILES, exist_ok=True)
        json.dump(dict(form=adopt, **tp, fit_runs=thermal['fit_runs'], source='d1sim/tools/fit_throttle_v1.py stage A (measured power in)',
                       status='measured-fit (shared thermal, 4 runs; 8 half-holdout)'),
                  open(os.path.join(PROFILES, 'throttle_v1_thermal.json'), 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
        names = {'GPU_CM': 'GPU_compiledmodel', 'GPU_INT': 'GPU_interpreter', 'NPU': 'NPU', 'CPU4': 'CPU4_interpreter'}
        for key, fn in names.items():
            d = dict(form=adopt, resource=CTRL[key]['res'], engine=('Interpreter 1.4.2' if key in ('GPU_INT', 'CPU4') else 'CompiledModel 2.2.0'),
                     ctrl=c['ctrl'][key], power=dict(P_idle=P_IDLE, P0=P0[key], alpha=alpha[key], alpha_n_bins=alpha_n[key]), L0_ms=L0[key],
                     fit_run=c['fit'][key]['fit_run'], fit_obj=c['fit'][key]['fit_obj'],
                     source='d1sim/tools/fit_throttle_v1.py stage B (measured sensor in) + stage C closed loop',
                     status='measured-fit' + (' — NPU release untested (tonight)' if key == 'NPU' else ''))
            json.dump(d, open(os.path.join(PROFILES, f'throttle_v1_{fn}.json'), 'w', encoding='utf-8'), indent=1, ensure_ascii=False, default=str)
        print('wrote profiles')
    return 0


if __name__ == '__main__':
    sys.exit(main())
