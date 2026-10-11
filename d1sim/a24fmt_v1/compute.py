"""S26 → A24 시뮬레이터 꼴 (S0 서비스 · E0 에너지 · T1 AP) — DECISIONS_A24FMT.md D1 ~ D10 그대로.

usage: python -m d1sim.a24fmt_v1.compute <mixreq_1008 folder> [--out DIR]
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

import numpy as np
from scipy.optimize import least_squares, nnls

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, '..', 'parsim_v1', 'data')
PHASES = [('dispatch_ns', 'execution_start_ns'), ('execution_start_ns', 'output_ready_ns'), ('output_ready_ns', 'persist_complete_ns'),
          ('persist_complete_ns', 'worker_release_ns'), ('worker_release_ns', 'lane_available_ns')]
PHASE_NAMES = ['dispatch_to_execution_start', 'execution_start_to_output_ready', 'output_ready_to_persist_complete',
               'persist_complete_to_worker_release', 'worker_release_to_lane_available']
STATES = ['cls_CPU', 'det_CPU', 'cls_GPU', 'cls_NPU', 'det_CPU&cls_GPU', 'det_CPU&cls_NPU']
CTX = {'CPU_URGENT_ONLINE_V1': 'CPU_URGENT', 'B2_PARALLEL_ONLINE_V1': 'B2_PARALLEL', 'S26_NPU_PARALLEL_V1': 'NPU_PARALLEL'}
BIN_S = 5.0
COND_MAX = 30.0


def sessions():
    out = []
    for f, setname in (('r3_sessions.csv', 'R3'), ('r4_start.csv', 'R4')):
        for r in csv.DictReader(open(os.path.join(DATA, f), encoding='utf-8')):
            ok = (r.get('eligible', r['valid_log']) == 'True') if r['set'] == 'R3' else r['valid_log'] == 'True'
            if ok:
                out.append(r)
    return out


def load(root, s):
    d = os.path.join(root, f"{s['set']}_blocks", s['folder'])
    cb = json.load(open(os.path.join(d, 'device', 'common_boundary.json'), encoding='utf-8'))
    ev, power = {}, []
    for line in open(os.path.join(d, 'device', 'progress.jsonl'), encoding='utf-8'):
        j = json.loads(line)
        k = j.get('kind')
        if k in ('phase_start', 'phase_end'):
            ev[(k, j.get('phase'))] = j['mono_ns']
        elif k == 'power_sample':
            if j.get('current_valid') and j.get('plugged') == 0 and j.get('voltage_mV', -1) > 0:
                t = (j['snapshot_start_ns'] + j['sensor_read_end_ns']) / 2e9
                power.append((t, -j['current_raw'] * j['voltage_mV'] / 1e9))
    hal = [(float(r['device_boottime_s']), float(r['AP'])) for r in csv.DictReader(open(os.path.join(d, 'host', 'hal.csv'), encoding='utf-8'))
           if r.get('AP') not in (None, '')]
    rows = [r for r in cb['rows'] if r.get('lane_available_ns') and r.get('terminal_status') == 'succeeded']
    return dict(cb=cb, ev=ev, power=sorted(power), hal=sorted(hal), rows=rows)


# --- E0 -------------------------------------------------------------------------------------------------------------
def integral(power, a, b):
    """trapezoid with linear interpolation at the edges; None if any gap > 2.5 s touches [a, b] or no coverage."""
    ts = [p[0] for p in power]
    if not ts or ts[0] > a or ts[-1] < b:
        return None
    pts = [(a, float(np.interp(a, ts, [p[1] for p in power])))] + [p for p in power if a < p[0] < b] + \
          [(b, float(np.interp(b, ts, [p[1] for p in power])))]
    i0 = max(i for i, t in enumerate(ts) if t <= a)
    i1 = min(i for i, t in enumerate(ts) if t >= b)
    if any(ts[i + 1] - ts[i] > 2.5 for i in range(i0, i1)):
        return None
    return sum((pts[i + 1][0] - pts[i][0]) * (pts[i + 1][1] + pts[i][1]) / 2 for i in range(len(pts) - 1))


def state_timeline(rows):
    """breakpoints → list of (t0, t1, state) with seconds on the device mono axis."""
    pts = []
    for r in rows:
        lane = r['selected_backend']
        task = 'cls' if r['task_id'] == 'classification' else 'det'
        pts.append((r['dispatch_ns'] / 1e9, +1, lane, task))
        pts.append((r['lane_available_ns'] / 1e9, -1, lane, task))
    pts.sort(key=lambda x: (x[0], x[1]))
    busy, out, last = {}, [], None
    for t, sgn, lane, task in pts:
        if last is not None and t > last and busy:
            out.append((last, t, name(busy)))
        if sgn > 0:
            busy[lane] = task
        else:
            busy.pop(lane, None)
        last = t
    return out


def name(busy):
    keys = tuple(sorted(busy.items()))
    m = {(('CPU', 'cls'),): 'cls_CPU', (('CPU', 'det'),): 'det_CPU', (('GPU', 'cls'),): 'cls_GPU', (('NPU', 'cls'),): 'cls_NPU',
         (('CPU', 'det'), ('GPU', 'cls')): 'det_CPU&cls_GPU', (('CPU', 'det'), ('NPU', 'cls')): 'det_CPU&cls_NPU'}
    return m.get(keys, 'other:' + '+'.join(f'{a}_{b}' for a, b in keys))


def occupancy(tl, a, b):
    occ = {}
    for t0, t1, st in tl:
        lo, hi = max(a, t0), min(b, t1)
        if hi > lo:
            occ[st] = occ.get(st, 0.0) + hi - lo
    return occ


def windows(S, s):
    c0 = S['cb']['start_ns'] / 1e9
    b0, b1 = S['ev'][('phase_start', 'resident_baseline')] / 1e9, S['ev'][('phase_end', 'resident_baseline')] / 1e9
    e_pre = integral(S['power'], b0, b1)
    p_pre = None if e_pre is None else e_pre / (b1 - b0)
    tl = state_timeline(S['rows'])
    bins = []
    for k in range(int(120 / BIN_S)):
        a, b = c0 + k * BIN_S, c0 + (k + 1) * BIN_S
        e = integral(S['power'], a, b)
        occ = occupancy(tl, a, b)
        bins.append(dict(k=k, J=e, occ=occ))
    e120 = integral(S['power'], c0, c0 + 120)
    return dict(p_pre=p_pre, bins=bins, e120=e120, tl=tl, c0=c0)


# --- T1 -------------------------------------------------------------------------------------------------------------
def t1_inputs(S, W):
    c0 = W['c0']
    cool_end = S['ev'].get(('phase_end', 'resident_cooling'))
    t_end = c0 + 180.0 if cool_end is None else min(c0 + 180.0, cool_end / 1e9)
    b1 = S['ev'][('phase_end', 'resident_baseline')] / 1e9
    pre = [ap for t, ap in S['hal'] if b1 - 10.0 <= t <= c0]
    before = [ap for t, ap in S['hal'] if t <= c0]
    if not pre or not before:
        return None
    R, T0 = statistics.mean(pre), before[-1]
    dt = 0.5
    n = int((t_end - c0) / dt)
    X = np.zeros((n, len(STATES)))
    for i in range(n):
        occ = occupancy(W['tl'], c0 + i * dt, c0 + (i + 1) * dt)
        for j, st in enumerate(STATES):
            X[i, j] = occ.get(st, 0.0) / dt
    obs = [(t - c0, ap) for t, ap in S['hal'] if c0 < t <= t_end]
    return dict(R=R, T0=T0, X=X, dt=dt, obs=obs)


def t1_path(inp, beta, theta):
    T, R, dt = inp['T0'], inp['R'], inp['dt']
    path = [T]
    e = math.exp(-beta * dt)
    for i in range(inp['X'].shape[0]):
        u = float(inp['X'][i] @ theta)
        T = R + u / beta + (T - R - u / beta) * e
        path.append(T)
    return np.array(path)


def t1_resid(params, inps):
    beta, theta = params[0], np.array(params[1:])
    res = []
    for inp in inps:
        p = t1_path(inp, beta, theta)
        tg = np.arange(len(p)) * inp['dt']
        for t, ap in inp['obs']:
            res.append(float(np.interp(t, tg, p)) - ap)
    return np.array(res)


# --- main -----------------------------------------------------------------------------------------------------------
def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('root')
    ap.add_argument('--out', default=os.path.join(HERE, 'out'))
    a = ap.parse_args(argv)
    os.makedirs(a.out, exist_ok=True)
    loaded = []
    for s in sessions():
        S = load(a.root, s)
        loaded.append((s, S, windows(S, s)))

    # S0 (R3 only)
    svc = {}
    for s, S, W in loaded:
        if s['set'] != 'R3':
            continue
        ctx = CTX[s['policy']]
        for r in S['rows']:
            key = f"{ctx}|{r['task_id']}|{r['selected_backend']}"
            svc.setdefault(key, []).append([r[b] - r[a_] for a_, b in PHASES])
    service = {}
    for key, v in sorted(svc.items()):
        arr = np.array(v, dtype=float)
        service[key] = dict(n=len(v), phase_means_ns=[float(x) for x in arr.mean(0)], phase_medians_ns=[float(x) for x in np.median(arr, 0)],
                            phase_p95_ns=[float(x) for x in np.percentile(arr, 95, axis=0)], total_mean_ms=float(arr.sum(1).mean() / 1e6))

    # E0 fit (R3)
    A, y, meta, other = [], [], [], {}
    for s, S, W in loaded:
        if s['set'] != 'R3' or W['p_pre'] is None:
            continue
        for b in W['bins']:
            if b['J'] is None:
                continue
            for st, v in b['occ'].items():
                if st not in STATES:
                    other[st] = other.get(st, 0.0) + v
            A.append([b['occ'].get(st, 0.0) for st in STATES])
            y.append(b['J'] - W['p_pre'] * BIN_S)
            meta.append((s['index'], b['k']))
    A, y = np.array(A), np.array(y)
    used = [j for j in range(len(STATES)) if A[:, j].sum() > 0]
    As = A[:, used]
    rank = int(np.linalg.matrix_rank(As))
    sd = As.std(0)
    cond = float(np.linalg.cond((As - As.mean(0)) / np.where(sd > 0, sd, 1))) if As.shape[0] > len(used) else float('inf')
    coef, _ = nnls(As, y)
    p_inc = {STATES[j]: float(c) for j, c in zip(used, coef)}
    rmse = float(np.sqrt(np.mean((As @ coef - y) ** 2)))
    exposure = {STATES[j]: int(((A[:, j] / BIN_S) >= 0.5).sum()) for j in range(len(STATES))}
    # 공선 진단: 각 열을 나머지로 회귀한 R²
    vif = {}
    for i, j in enumerate(used):
        others = np.delete(As, i, axis=1)
        if others.shape[1] == 0:
            continue
        c, *_ = np.linalg.lstsq(np.c_[others, np.ones(len(As))], As[:, i], rcond=None)
        r2 = 1 - np.sum((np.c_[others, np.ones(len(As))] @ c - As[:, i]) ** 2) / max(np.sum((As[:, i] - As[:, i].mean()) ** 2), 1e-12)
        vif[STATES[j]] = float(1 / max(1 - r2, 1e-9))
    identified = rank == len(used) and cond <= COND_MAX

    # T1 fit (R3)
    inps = []
    for s, S, W in loaded:
        if s['set'] == 'R3':
            inp = t1_inputs(S, W)
            if inp:
                inps.append(inp)
    x0 = [0.05] + [0.1] * len(STATES)
    lb = [0.005] + [0.0] * len(STATES)
    ub = [0.5] + [5.0] * len(STATES)
    fit = least_squares(t1_resid, x0, bounds=(lb, ub), args=(inps,))
    beta, theta = float(fit.x[0]), np.array(fit.x[1:])
    t1_rmse = float(np.sqrt(np.mean(fit.fun ** 2)))
    J = fit.jac
    try:
        t1_cond = float(np.linalg.cond(J / np.where(np.abs(J).max(0) > 0, np.abs(J).max(0), 1)))
    except Exception:
        t1_cond = float('inf')

    # 평가 (모든 세트 · 조건 A = 실측 점유)
    rows_out = []
    for s, S, W in loaded:
        r = dict(set=s['set'], index=s['index'], policy=CTX[s['policy']], folder=s['folder'], p_pre_w=W['p_pre'])
        if W['p_pre'] is not None and W['e120'] is not None:
            occ = occupancy(W['tl'], W['c0'], W['c0'] + 120)
            pred = W['p_pre'] * 120 + sum(p_inc.get(st, 0.0) * v for st, v in occ.items())
            r.update(J120_meas=W['e120'], J120_pred=pred, J120_err=pred - W['e120'], J120_rel=(pred - W['e120']) / W['e120'],
                     other_state_s=sum(v for st, v in occ.items() if st not in STATES))
        inp = t1_inputs(S, W)
        if inp:
            p = t1_path(inp, beta, theta)
            tg = np.arange(len(p)) * inp['dt']
            errs = [float(np.interp(t, tg, p)) - ap for t, ap in inp['obs']]
            pk_p = max(float(np.interp(t, tg, p)) for t, _ in inp['obs'])
            pk_m = max(ap for _, ap in inp['obs'])
            r.update(ap_mae=float(np.mean(np.abs(errs))), ap_max_abs=float(np.max(np.abs(errs))), ap_peak_err=pk_p - pk_m, ap_n=len(errs))
        rows_out.append(r)

    # R4S 감속 기술 (CPU 직렬 실행 시간 1분 칸)
    slow = []
    for s, S, W in loaded:
        if s['set'] != 'R4S' or CTX[s['policy']] != 'CPU_URGENT':
            continue
        by = {}
        for r in S['rows']:
            m = int((r['dispatch_ns'] / 1e9 - W['c0']) // 60)
            by.setdefault((m, r['task_id']), []).append((r['output_ready_ns'] - r['execution_start_ns']) / 1e6)
        base = {t: statistics.median(by[(0, t)]) for t in ('classification', 'detection') if (0, t) in by}
        slow.append(dict(index=s['index'], ratio={t: [round(statistics.median(by[(m, t)]) / base[t], 3) for m in range(10) if (m, t) in by]
                                                  for t in base}))

    model = dict(model_family='s26-a24fmt-v1 (S0 · E0 · T1 — A24 꼴, S26 계수)', decisions='DECISIONS_A24FMT.md D1 ~ D10',
                 data='R3 S26-MIXREQ-02 16세션 (개발) · origin/s26-mixreq 21cba44', current_unit='uA (S26 가정) — W = -I*V/1e9',
                 service={k: dict(n=v['n'], phase_means_ns=v['phase_means_ns']) for k, v in service.items()}, phases=PHASE_NAMES,
                 power=dict(pre_mode='session resident_baseline 30 s mean', state_increment_w=p_inc, states=STATES, bin_s=BIN_S),
                 thermal=dict(form='dT/dt = -beta (T - R) + sum theta_s x_s ; R = baseline last 10 s AP mean ; T0 = last AP before common start',
                              beta_per_s=beta, theta_c_per_s=dict(zip(STATES, map(float, theta)))),
                 thermal_service_feedback=None, unsupported=['detection_GPU', 'detection_NPU', '3-resource', 'throttle'])
    audit = dict(energy=dict(bins=int(len(y)), rank=rank, n_states_used=len(used), cond_std=cond, cond_max=COND_MAX, identified=identified,
                             rmse_J_per_bin=rmse, exposure_bins_ge50pct=exposure, vif=vif, other_state_seconds=other),
                 thermal=dict(rmse_c=t1_rmse, jac_cond=t1_cond, n_obs=int(len(fit.fun)), status=int(fit.status)),
                 service_detail=service, r4s_cpu_exec_ratio_by_minute=slow)
    json.dump(model, open(os.path.join(a.out, 's26_a24fmt_model.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    json.dump(audit, open(os.path.join(a.out, 'audit.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    with open(os.path.join(a.out, 'sessions_eval.csv'), 'w', encoding='utf-8', newline='') as f:
        keys = sorted({k for r in rows_out for k in r})
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows_out)
    for fn in ('s26_a24fmt_model.json', 'audit.json', 'sessions_eval.csv'):
        print(fn, hashlib.sha256(open(os.path.join(a.out, fn), 'rb').read()).hexdigest())
    print(json.dumps(dict(p_inc=p_inc, rank=rank, cond=cond, identified=identified, rmse=rmse, exposure=exposure, vif=vif, other=other,
                          beta=beta, theta=dict(zip(STATES, map(float, theta))), t1_rmse=t1_rmse, t1_cond=t1_cond), ensure_ascii=False, indent=1))


if __name__ == '__main__':
    sys.exit(main())
