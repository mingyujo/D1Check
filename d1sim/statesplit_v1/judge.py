"""상태 분리 판정기 — 등록 `상태분리_사전등록_v2.md` §2 그대로 (측정 결과 보기 전 커밋).

usage: python -m d1sim.statesplit_v1.judge --dev <dir>... --confirm <dir>... [--r4c-root <mixreq_1008>] [--out DIR]
  <dir> = 세션 폴더 (device/common_boundary.json · device/progress.jsonl · host/hal.csv) · 폴더 이름에 정책 이름이 들어 있어야 함
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import statistics
import sys

import numpy as np
from scipy.optimize import least_squares, nnls

from d1sim.a24fmt_v1 import compute as C

HERE = os.path.dirname(os.path.abspath(__file__))
STATES = C.STATES
EXPO_MIN, VIF_MAX, P_MAX, TH_MAX = 6, 10.0, 5.0, 5.0
J_REL_MAX, AP_MAE_MAX = 0.10, 1.0


def policy_of(d):
    b = os.path.basename(os.path.normpath(d))
    for k in ('CPU_URGENT', 'B2_PARALLEL', 'NPU_PARALLEL'):
        if k in b:
            return k
    raise SystemExit(f'policy not in folder name: {b}')


def load_dir(d):
    """a24fmt_v1.compute.load 와 같은 읽기 (경로를 직접 받음)."""
    root = os.path.dirname(os.path.dirname(os.path.normpath(d)))
    parent = os.path.basename(os.path.dirname(os.path.normpath(d)))
    if parent.endswith('_blocks'):
        return C.load(root, dict(set=parent[:-len('_blocks')], folder=os.path.basename(os.path.normpath(d))))
    # 다른 폴더 구조: 임시 심볼릭 링크로 같은 꼴을 만든다
    import tempfile
    tmp = tempfile.mkdtemp()
    os.makedirs(os.path.join(tmp, 'X_blocks'))
    os.symlink(os.path.abspath(d), os.path.join(tmp, 'X_blocks', os.path.basename(os.path.normpath(d))))
    return C.load(tmp, dict(set='X', folder=os.path.basename(os.path.normpath(d))))


def session(d):
    S = load_dir(d)
    W = C.windows(S, None)
    return dict(dir=d, policy=policy_of(d), S=S, W=W)


def design(sess):
    A, y = [], []
    for x in sess:
        if x['W']['p_pre'] is None:
            continue
        for b in x['W']['bins']:
            if b['J'] is None:
                continue
            A.append([b['occ'].get(st, 0.0) for st in STATES])
            y.append(b['J'] - x['W']['p_pre'] * C.BIN_S)
    return np.array(A), np.array(y)


def vif(A):
    out = {}
    for j in range(A.shape[1]):
        if A[:, j].sum() <= 0:
            continue
        others = np.delete(A, j, axis=1)
        X = np.c_[others, np.ones(len(A))]
        c, *_ = np.linalg.lstsq(X, A[:, j], rcond=None)
        ss = np.sum((A[:, j] - A[:, j].mean()) ** 2)
        r2 = 1 - np.sum((X @ c - A[:, j]) ** 2) / max(ss, 1e-12)
        out[STATES[j]] = float(1 / max(1 - r2, 1e-9))
    return out


def evaluate(x, p_inc, beta, theta):
    W, S = x['W'], x['S']
    r = dict(dir=os.path.basename(os.path.normpath(x['dir'])), policy=x['policy'])
    if W['p_pre'] is not None and W['e120'] is not None:
        occ = C.occupancy(W['tl'], W['c0'], W['c0'] + 120)
        pred = W['p_pre'] * 120 + sum((p_inc.get(st) or 0.0) * v for st, v in occ.items())
        r.update(J_meas=W['e120'], J_pred=pred, J_rel=(pred - W['e120']) / W['e120'])
    inp = C.t1_inputs(S, W)
    if inp:
        th = np.array([theta.get(st) or 0.0 for st in STATES])
        p = C.t1_path(inp, beta, th)
        tg = np.arange(len(p)) * inp['dt']
        errs = [float(np.interp(t, tg, p)) - ap for t, ap in inp['obs']]
        r.update(ap_mae=float(np.mean(np.abs(errs))))
    r['ok'] = (r.get('J_rel') is not None and abs(r['J_rel']) <= J_REL_MAX and r.get('ap_mae') is not None and r['ap_mae'] <= AP_MAE_MAX)
    return r


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--dev', nargs='+', required=True)
    ap.add_argument('--confirm', nargs='+', required=True)
    ap.add_argument('--r4c-root')
    ap.add_argument('--out', default=os.path.join(HERE, 'out'))
    a = ap.parse_args(argv)
    os.makedirs(a.out, exist_ok=True)
    dev = [session(d) for d in a.dev]
    con = [session(d) for d in a.confirm]

    # E0 (dev only)
    A, y = design(dev)
    used = [j for j in range(len(STATES)) if A[:, j].sum() > 0]
    coef, _ = nnls(A[:, used], y)
    p_raw = {STATES[j]: float(c) for j, c in zip(used, coef)}
    V = vif(A[:, :])
    expo = {st: int(((A[:, j] / C.BIN_S) >= 0.5).sum()) for j, st in enumerate(STATES)}

    # T1 (dev only)
    inps = [i for i in (C.t1_inputs(x['S'], x['W']) for x in dev) if i]
    fit = least_squares(C.t1_resid, [0.05] + [0.1] * len(STATES), bounds=([0.005] + [0.0] * len(STATES), [0.5] + [TH_MAX] * len(STATES)), args=(inps,))
    beta = float(fit.x[0])
    th_raw = dict(zip(STATES, map(float, fit.x[1:])))

    # 식별 (§2-2)
    ident, p_inc, theta = {}, {}, {}
    for st in STATES:
        reasons = []
        if expo[st] < EXPO_MIN:
            reasons.append(f'exposure {expo[st]} < {EXPO_MIN}')
        if V.get(st, float('inf')) > VIF_MAX:
            reasons.append(f'VIF {V.get(st)} > {VIF_MAX}')
        if st in p_raw and not (0.0 <= p_raw[st] <= P_MAX):
            reasons.append(f'p {p_raw[st]:.3f} outside [0, {P_MAX}]')
        if th_raw[st] >= TH_MAX - 1e-6:
            reasons.append('theta at upper bound')
        ok = not reasons and st in p_raw
        ident[st] = dict(identified=ok, reasons=reasons)
        p_inc[st] = p_raw.get(st) if ok else None
        theta[st] = th_raw[st] if ok else None

    # 확인 (§2-3): 식별된 계수만 · 미식별 상태는 0 으로 두지 않고 그 세션의 예측을 계산 불가로
    def usable(x):
        occ = C.occupancy(x['W']['tl'], x['W']['c0'], x['W']['c0'] + 120)
        return all(ident.get(st, {}).get('identified') for st, v in occ.items() if v > 0)
    rows = []
    for x in con:
        if usable(x):
            rows.append(evaluate(x, p_inc, beta, theta))
        else:
            rows.append(dict(dir=os.path.basename(os.path.normpath(x['dir'])), policy=x['policy'], ok=False, note='미식별 상태 점유 → 계산 불가 (통과 아님)'))
    n_ok = sum(r['ok'] for r in rows)
    per = {}
    for r in rows:
        per.setdefault(r['policy'], []).append(r['ok'])
    name = ('상태 분리 값 확인 (같은 꼴 · 2 블록)' if n_ok >= 4 and all(sum(v) >= 1 for v in per.values()) else '확인 안 됨')

    retro = []
    if a.r4c_root:
        for s in C.sessions():
            if s['set'] != 'R4C':
                continue
            S = C.load(a.r4c_root, s)
            x = dict(dir=s['folder'], policy=C.CTX[s['policy']], S=S, W=C.windows(S, s))
            retro.append(evaluate(x, p_inc, beta, theta) if usable(x) else dict(dir=s['folder'], policy=x['policy'], note='미식별 상태 점유'))

    out = dict(registration='상태분리_사전등록_v2.md §2', dev=[os.path.basename(os.path.normpath(d)) for d in a.dev],
               confirm_dirs=[os.path.basename(os.path.normpath(d)) for d in a.confirm],
               identification=ident, exposure=expo, vif=V, p_raw_w=p_raw, theta_raw=th_raw, beta=beta,
               state_increment_w=p_inc, theta_c_per_s=theta, confirm=rows, confirm_ok=n_ok, confirm_per_policy={k: sum(v) for k, v in per.items()},
               name=name, r4c_retro=retro)
    path = os.path.join(a.out, 'statesplit_judge.json')
    json.dump(out, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(path, hashlib.sha256(open(path, 'rb').read()).hexdigest())
    print(name, n_ok, out['confirm_per_policy'])


if __name__ == '__main__':
    sys.exit(main())
