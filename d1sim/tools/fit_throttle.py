"""Fit throttle-model candidates on C1-probe r1 only; report r1 / r2 / 9/14 60 s errors side by side.

Usage (D1Check_v4 root): py d1sim/tools/fit_throttle.py [--out d1sim/out/throttle_fit_v0.json]
Pre-registration: 산공학회/D1_ondevice/sim/스로틀모형_사전등록_v0.md (mirror d1sim/docs/). Deterministic: fixed
Nelder-Mead starts, no randomness. Reads d1sim/data/trace*_*.csv (from tools/extract_traces.py).
"""
import argparse, csv, json, math, os, statistics as st, sys

import numpy as np
from scipy.optimize import minimize

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from d1sim.throttle import simulate_continuous, onset_time_ref  # noqa: E402

DATA = os.path.join(os.path.dirname(__file__), '..', 'data')
P_IDLE = 0.581      # [D] NPU_FORMAL_RESULTS.md:239 (100-run joint idle median). Energy absolute accuracy uncertified.
S_MIN = 0.3         # [E] prereg §2
TAU = {'SKIN': 34.4, 'AP': 17.0}   # [D] 평가층_사전등록_v1.md:47 (GPU SKIN heat tau median), :49 (AP heat GPU)

FORMS = {  # id: (sensor, nodes, free param names)
    'M-A1': ('SKIN', 1, ['G_f', 'T_th', 'k']),
    'M-B1': ('AP', 1, ['G_f', 'T_th', 'k']),
    'M-A2': ('SKIN', 2, ['G_f', 'G_s', 'tau_s', 'T_th', 'k']),
    'M-B2': ('AP', 2, ['G_f', 'G_s', 'tau_s', 'T_th', 'k']),
}
BOUNDS = {'G_f': (0, 5), 'G_s': (0, 5), 'tau_s': (60, 3000), 'T_th': (30, 50), 'k': (0, 2)}
STARTS = {  # fixed start points (no RNG)
    'G_f': [1.0, 1.5], 'G_s': [0.5, 1.5], 'tau_s': [200, 800], 'T_th': [37.0, 41.0], 'k': [0.1, 0.5]}


def load(tag):
    r1 = [r for r in csv.DictReader(open(os.path.join(DATA, f'trace_{tag}.csv'), encoding='utf-8'))]
    r10 = [r for r in csv.DictReader(open(os.path.join(DATA, f'trace10_{tag}.csv'), encoding='utf-8'))]
    ref = next(r for r in r10 if r['t_s'] == '-1')
    fl = lambda v: float(v) if v not in ('', None) else None  # noqa: E731
    one = [dict(t=int(r['t_s']), lat=float(r['lat_med_ms']), pw=fl(r['power_w']), SKIN=fl(r['SKIN']), AP=fl(r['AP']))
           for r in r1]
    ten = [(int(r['t_s']), float(r['lat_med_ms']), fl(r['power_w'])) for r in r10 if r['t_s'] != '-1']
    return dict(one=one, ten=ten, ref_lat=float(ref['lat_med_ms']), ref_pw=float(ref['power_w']))


def fit_alpha(d, L0, P0):
    """alpha from 10 s bins with measured s = L0/lat <= 0.95 (throttled): log(dP/dP0) = alpha*log(s), through origin."""
    xs, ys = [], []
    for t, lat, pw in d['ten']:
        s = L0 / lat
        if s <= 0.95 and pw and pw > P_IDLE:
            xs.append(math.log(s)); ys.append(math.log((pw - P_IDLE) / (P0 - P_IDLE)))
    xs, ys = np.array(xs), np.array(ys)
    a = float((xs * ys).sum() / (xs * xs).sum())
    resid = ys - a * xs
    return a, len(xs), float(np.sqrt((resid ** 2).mean()))


def params(form, theta, base):
    sensor, nodes, names = FORMS[form]
    p = dict(base, nodes=nodes, tau_f=TAU[sensor], G_s=0.0, tau_s=1.0)
    p.update(dict(zip(names, theta)))
    return p


def run_model(p, d, sensor, duration=None):
    T0 = next(r[sensor] for r in d['one'] if r[sensor] is not None)
    dur = duration or (d['one'][-1]['t'] + 1)
    return simulate_continuous(p, T0, dur)


def objective(theta, form, base, d):
    sensor, _, names = FORMS[form]
    for n, v in zip(names, theta):
        lo, hi = BOUNDS[n]
        if not lo <= v <= hi:
            return 1e6
    sim = run_model(params(form, theta, base), d, sensor)
    e_lat = [(sim[r['t']]['latency_ms'] / r['lat'] - 1) ** 2 for r in d['one'] if r['t'] < len(sim)]
    e_T = [(sim[r['t']]['T'] - r[sensor]) ** 2 for r in d['one'] if r['t'] < len(sim) and r[sensor] is not None]
    return float(np.mean(e_lat) + np.mean(e_T))


def fit(form, base, d):
    import itertools
    names = FORMS[form][2]
    best = None
    for start in itertools.product(*[STARTS[n] for n in names]):
        r = minimize(objective, np.array(start, float), args=(form, base, d), method='Nelder-Mead',
                     options=dict(maxiter=4000, xatol=1e-4, fatol=1e-8))
        if best is None or r.fun < best.fun:
            best = r
    return dict(zip(names, map(float, best.x))), float(best.fun)


def metrics(p, d, sensor):
    sim = run_model(p, d, sensor)
    n = len(sim)
    ten_m = [(t, st.median([sim[j]['latency_ms'] for j in range(t, min(t + 10, n))])) for t, _, _ in d['ten'] if t < n]
    pw_m = {t: st.mean([sim[j]['power_w'] for j in range(t, min(t + 10, n))]) for t, _, _ in d['ten'] if t < n}
    on_meas = onset_time_ref([(t, m) for t, m, _ in d['ten']], d['ref_lat'])
    on_mod = onset_time_ref(ten_m, p['L0'])
    last = [r for r in d['one'] if r['t'] >= n - 60]
    eq_meas = st.mean(r['lat'] for r in last)
    eq_mod = st.mean(sim[r['t']]['latency_ms'] for r in last)
    out = dict(
        onset_meas_s=on_meas, onset_model_s=on_mod,
        onset_err_s=(on_mod - on_meas) if (on_mod is not None and on_meas is not None) else
        ('mismatch' if (on_mod is None) != (on_meas is None) else None),
        eq_lat_meas_ms=eq_meas, eq_lat_model_ms=eq_mod, eq_lat_err_pct=100 * (eq_mod / eq_meas - 1),
        lat_mae_ms=float(np.mean([abs(m - lm) for (t, m, _), (_, lm) in zip(d['ten'], ten_m)])),
        pw_mae_w=float(np.mean([abs(pw - pw_m[t]) for t, _, pw in d['ten'] if pw is not None and t in pw_m])),
        last10_vs_first30_meas_pct=100 * (d['ten'][-1][1] / d['ref_lat'] - 1),
        last10_vs_first30_model_pct=100 * (ten_m[-1][1] / p['L0'] - 1),
    )
    for s_name in ('SKIN', 'AP'):
        if s_name == sensor:
            out[f'{s_name}_mae_c'] = float(np.mean([abs(sim[r['t']]['T'] - r[s_name]) for r in d['one']
                                                   if r[s_name] is not None and r['t'] < n]))
        else:
            out[f'{s_name}_mae_c'] = None   # no observation model for the non-driving sensor
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.join(os.path.dirname(__file__), '..', 'out', 'throttle_fit_v0.json'))
    a = ap.parse_args()
    r1, r2 = load('c1p_r1'), load('c1p_r2')
    f60 = {f'f914_gpu_d100_r00{i}': load(f'f914_gpu_d100_r00{i}') for i in range(1, 6)}
    L0, P0 = r1['ref_lat'], r1['ref_pw']
    alpha, n_alpha, rmse_alpha = fit_alpha(r1, L0, P0)
    alpha_r2 = fit_alpha(r2, L0, P0)
    base = dict(L0=L0, P0=P0, P_idle=P_IDLE, s_min=S_MIN, alpha=alpha)
    res = dict(fixed=dict(base, tau=TAU, source='r1 first-30 s exact reference; P_idle [D]; s_min [E]'),
               alpha=dict(r1=alpha, n_bins=n_alpha, rmse_log=rmse_alpha, r2_check=alpha_r2[0]), forms={})
    for form, (sensor, nodes, names) in FORMS.items():
        fitted, obj = fit(form, base, r1)
        p = params(form, [fitted[n] for n in names], base)
        res['forms'][form] = dict(sensor=sensor, nodes=nodes, n_free=len(names), fitted=fitted, r1_objective=obj,
                                  r1=metrics(p, r1, sensor), r2=metrics(p, r2, sensor),
                                  f60={k: metrics(p, v, sensor) for k, v in f60.items()})
        print(form, 'obj', round(obj, 5), {k: round(v, 4) for k, v in fitted.items()})
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    json.dump(res, open(a.out, 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
    print('alpha', alpha, n_alpha, rmse_alpha, 'r2 alpha', alpha_r2)
    print('wrote', a.out)


if __name__ == '__main__':
    main()
