"""g_CPU (M-sup, kappa = 1) and (g_CPU, kappa) (M-kappa) fitted on R3 ONLY (registration §1-2 · §2).

Objective (DECISIONS D4): thermal driven by the MEASURED R3 resource activity (open loop — exact request stage timestamps, so
service sampling noise does not enter the thermal fit); per session the mean of (model AP - HAL AP)^2 over the HAL samples inside the
common window; the objective is the mean over the 16 sessions. Start state rule = DECISIONS D5 (same as the confirmation predictions).
Writes profiles/parsim_v1_thermal_sum.json (g, kappa for both forms + objective values + session list + data SHA).

usage: python -m d1sim.parsim_v1.fit [--selftest]
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
from collections import defaultdict

from scipy.optimize import minimize, minimize_scalar

from d1sim.parsim_v1 import service_des as sd
from d1sim.parsim_v1 import thermal_sum as ts

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, 'data')
PROFILE = os.path.join(os.path.dirname(HERE), 'profiles', 'parsim_v1_thermal_sum.json')
G_FIXED = None


def g_frozen(params):
    gm = params['thermal']['g_m']
    return {'GPU': float(gm['GPU']), 'NPU': float(gm['NPU'])}


def start_state(s):
    """DECISIONS D5: SKIN0 / AP0 / BAT0 = last HAL row at or before the common-window start; A0 = gate idle (AP - SKIN);
    H_a(0) = (AP0 - SKIN0) - A0 (decays with the v2.2 AP time constants)."""
    return dict(skin0=float(s['start_skin']), ap0=float(s['start_ap']), bat0=float(s['start_bat']),
                a0=float(s['gate_ap']) - float(s['gate_skin']))


def intervals_from_rows(rows, t0_ns):
    """measured activity -> list of (t_start, t_end, resource) in seconds from the window start."""
    out = []
    for r in rows:
        res = r['selected_backend']
        d, a, b, e = (int(r[k]) for k in ('dispatch_ns', 'host_inference_start_ns', 'host_inference_return_ns', 'lane_available_ns'))
        if res == 'CPU':
            out.append(((d - t0_ns) / 1e9, (e - t0_ns) / 1e9, 'CPU'))
        else:
            out += [((d - t0_ns) / 1e9, (a - t0_ns) / 1e9, 'CPU'), ((a - t0_ns) / 1e9, (b - t0_ns) / 1e9, res),
                    ((b - t0_ns) / 1e9, (e - t0_ns) / 1e9, 'CPU')]
    return out


def open_loop(params, g, kappa, st, intervals, t_end, rec_dt=0.5):
    """Integrate thermal_sum.Device over [0, t_end] with the given activity; returns (path_t, skin, ap)."""
    dev = ts.Device(params, g, kappa, st['skin0'], st['ap0'], st['bat0'], st['a0'])
    bnd = sorted({0.0, t_end} | {x for iv in intervals for x in iv[:2] if 0.0 < x < t_end})
    pt, pk, pa = [0.0], [dev.skin], [dev.ap]
    t, nxt_rec = 0.0, rec_dt
    starts = sorted(intervals)
    k = 0
    active_ivs = []
    for b in bnd[1:]:
        while t < b - 1e-12:
            h = min(ts.MAX_H, b - t, nxt_rec - t if nxt_rec > t + 1e-12 else ts.MAX_H)
            mid = t + 0.5 * h
            while k < len(starts) and starts[k][0] <= mid:
                active_ivs.append(starts[k]); k += 1
            active_ivs = [iv for iv in active_ivs if iv[1] > mid]
            act = {iv[2] for iv in active_ivs if iv[0] <= mid < iv[1]}
            dev.advance(h, act)
            t += h
            if t >= nxt_rec - 1e-12:
                pt.append(round(nxt_rec, 6)); pk.append(dev.skin); pa.append(dev.ap)
                nxt_rec += rec_dt
    return pt, pk, pa


def load_r3():
    sess = list(csv.DictReader(open(os.path.join(DATA, 'r3_sessions.csv'), encoding='utf-8')))
    req = defaultdict(list)
    for r in csv.DictReader(open(os.path.join(DATA, 'r3_requests.csv'), encoding='utf-8')):
        req[r['index']].append(r)
    hal = defaultdict(list)
    for r in csv.DictReader(open(os.path.join(DATA, 'r3_hal.csv'), encoding='utf-8')):
        hal[r['index']].append(r)
    cases = []
    for s in sess:
        t0 = int(s['start_ns']); t_end = (int(s['end_ns']) - t0) / 1e9
        hs = [(float(h['t_s']) - t0 / 1e9, float(h['AP']), float(h['SKIN'])) for h in hal[s['index']]]
        hs = [x for x in hs if 0.0 <= x[0] <= t_end]
        cases.append(dict(index=s['index'], policy=s['policy'], st=start_state(s), iv=intervals_from_rows(req[s['index']], t0),
                          t_end=t_end, hal=hs))
    return cases


def session_errors(params, g, kappa, case):
    pt, pk, pa = open_loop(params, g, kappa, case['st'], case['iv'], case['t_end'])
    ea = [sd.interp(pt, pa, t) - ap for t, ap, _ in case['hal']]
    es = [sd.interp(pt, pk, t) - sk for t, _, sk in case['hal']]
    return ea, es, pt, pk, pa


def objective(params, gcpu, kappa, cases):
    g = dict(g_frozen(params), CPU=gcpu)
    tot = 0.0
    for c in cases:
        ea = session_errors(params, g, kappa, c)[0]
        tot += sum(e * e for e in ea) / len(ea)
    return tot / len(cases)


def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


def fit():
    params = ts.load_v22()
    cases = load_r3()
    r1 = minimize_scalar(lambda x: objective(params, x, 1.0, cases), bounds=(0.05, 5.0), method='bounded', options=dict(xatol=1e-4))
    g_sup = float(r1.x)
    f2 = lambda v: objective(params, min(5.0, max(0.05, v[0])), min(3.0, max(0.1, v[1])), cases)
    r2 = minimize(f2, [g_sup, 1.0], method='Nelder-Mead', options=dict(xatol=1e-4, fatol=1e-6, maxiter=400))
    g_k, kap = min(5.0, max(0.05, float(r2.x[0]))), min(3.0, max(0.1, float(r2.x[1])))
    per = []
    for c in cases:
        for form, gc, kp in (('M-sup', g_sup, 1.0), ('M-kappa', g_k, kap)):
            ea, es, *_ = session_errors(params, dict(g_frozen(params), CPU=gc), kp, c)
            per.append(dict(form=form, index=c['index'], policy=c['policy'], ap_mse=sum(e * e for e in ea) / len(ea),
                            ap_mae=sum(abs(e) for e in ea) / len(ea), skin_mae=sum(abs(e) for e in es) / len(es), n=len(ea)))
    out = dict(form='parsim-v1 thermal summation (v2.2 e52a922 thermal block unchanged)',
               M_sup=dict(kappa=1.0, g=dict(g_frozen(params), CPU=g_sup), objective=float(r1.fun), evals=int(r1.nfev)),
               M_kappa=dict(kappa=kap, g=dict(g_frozen(params), CPU=g_k), objective=float(r2.fun), evals=int(r2.nfev)),
               g_source=dict(GPU='v2.2 g_m (EffNet, fit on N2 + N4) — frozen', NPU='v2.2 g_m — frozen', CPU='fit here on R3 only'),
               cpu_power='v2.2 CPU4_interpreter power profile at s = 1 (P0 7.3615 W) x g_CPU',
               objective_def='mean over R3 sessions of mean (model AP - HAL AP)^2 at HAL samples in the common window; open loop (measured activity)',
               sessions=[c['index'] for c in cases], per_session=per,
               data=dict(r3_requests=sha(os.path.join(DATA, 'r3_requests.csv')), r3_hal=sha(os.path.join(DATA, 'r3_hal.csv')),
                         r3_sessions=sha(os.path.join(DATA, 'r3_sessions.csv'))))
    return out


def selftest():
    params = ts.load_v22()
    st = dict(skin0=30.0, ap0=30.0, bat0=28.0, a0=0.0)
    pt, pk, pa = open_loop(params, dict(g_frozen(params), CPU=1.0), 1.0, st, [], 60.0)
    ok = abs(pa[-1] - pa[0]) < 0.6 and len(pt) == 121
    pt2, pk2, pa2 = open_loop(params, dict(g_frozen(params), CPU=1.0), 1.0, st, [(10.0, 50.0, 'CPU')], 60.0)
    pt3, pk3, pa3 = open_loop(params, dict(g_frozen(params), CPU=2.0), 1.0, st, [(10.0, 50.0, 'CPU')], 60.0)
    ok &= max(pa2) > max(pa) + 3 and max(pa3) > max(pa2)
    print('fit selftest', 'PASS' if ok else 'FAIL', round(max(pa), 3), round(max(pa2), 3), round(max(pa3), 3))
    return ok


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--selftest', action='store_true')
    a = ap.parse_args(argv)
    if a.selftest:
        return 0 if selftest() else 1
    out = fit()
    os.makedirs(os.path.dirname(PROFILE), exist_ok=True)
    json.dump(out, open(PROFILE, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(json.dumps({k: out[k] for k in ('M_sup', 'M_kappa')}, indent=1))
    print('wrote', PROFILE, sha(PROFILE))


if __name__ == '__main__':
    sys.exit(main())
