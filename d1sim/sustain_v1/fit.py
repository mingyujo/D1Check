"""S1 지속 감속 적합 (DECISIONS_SUSTAIN.md D1 ~ D4) + 확인 판정기 (D5 · D6).

usage:
  python -m d1sim.sustain_v1.fit fit <mixreq_1008 folder>            # R4 (S) 로 적합 → out/s1_frozen.json (있으면 거부)
  python -m d1sim.sustain_v1.fit judge <frozen json> <session dir>... # 새 ABBA 세션 (device/common_boundary.json 이 있는 폴더) 판정
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import statistics
import sys

import numpy as np
from scipy.optimize import least_squares

from d1sim.a24fmt_v1 import compute as C

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'out')
CELLS = [('CPU_URGENT', 'classification', 'CPU'), ('CPU_URGENT', 'detection', 'CPU'), ('B2_PARALLEL', 'classification', 'GPU'),
         ('B2_PARALLEL', 'detection', 'CPU'), ('NPU_PARALLEL', 'classification', 'NPU'), ('NPU_PARALLEL', 'detection', 'CPU')]
JUDGED = CELLS[:4]
MAE_MAX = 0.08


def union_busy(rows):
    iv = sorted((r['dispatch_ns'] / 1e9, r['lane_available_ns'] / 1e9) for r in rows)
    merged = []
    for a, b in iv:
        if merged and a <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    return merged


def cum_busy(merged, t):
    return sum(max(0.0, min(b, t) - a) for a, b in merged if a < t)


def points(rows, c0, policy):
    """[(cell, c, ratio, minute)] for one session."""
    merged = union_busy(rows)
    out = []
    by = {}
    for r in rows:
        cell = (policy, r['task_id'], r['selected_backend'])
        ex = (r['output_ready_ns'] - r['execution_start_ns']) / 1e6
        by.setdefault(cell, []).append((r['execution_start_ns'] / 1e9, ex, r['dispatch_ns'] / 1e9))
    for cell, v in by.items():
        base = [ex for t, ex, d in v if d - c0 < 60.0]
        if not base:
            continue
        b = statistics.median(base)
        for t, ex, d in v:
            out.append((cell, cum_busy(merged, t), ex / b, int((d - c0) // 60)))
    return out


def model(c, a, tau):
    return 1.0 + a * (1.0 - np.exp(-np.asarray(c) / tau))


def fit(root):
    path = os.path.join(OUT, 's1_frozen.json')
    if os.path.exists(path):
        raise SystemExit('s1_frozen.json exists — refuse to overwrite (frozen)')
    pts = []
    for s in C.sessions():
        if s['set'] != 'R4S':
            continue
        S = C.load(root, s)
        pts += points(S['rows'], S['cb']['start_ns'] / 1e9, C.CTX[s['policy']])
    params = {}
    for cell in CELLS:
        cs = np.array([p[1] for p in pts if p[0] == cell])
        rs = np.array([p[2] for p in pts if p[0] == cell])
        res = least_squares(lambda x: model(cs, x[0], x[1]) - rs, [0.6, 200.0], bounds=([0.0, 10.0], [3.0, 3000.0]))
        params['|'.join(cell)] = dict(a=float(res.x[0]), tau_s=float(res.x[1]), n=int(len(cs)), rmse=float(np.sqrt(np.mean(res.fun ** 2))))
    os.makedirs(OUT, exist_ok=True)
    doc = dict(form='r = 1 + a (1 - exp(-c/tau)) · c = cumulative union-busy s since common start · base = first-60 s median exec',
               decisions='DECISIONS_SUSTAIN.md', fit_data='R4 (S) valid 14 · origin/s26-mixreq 21cba44', params=params,
               judge=dict(cells=['|'.join(c) for c in JUDGED], minutes='2..10', mae_max=MAE_MAX, rule='>= 6/8 (session, cell) and per policy >= 3/4'),
               scope='200 ms mixed · <= 10 min · start SKIN 28.6 ~ 32.2')
    json.dump(doc, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(path, hashlib.sha256(open(path, 'rb').read()).hexdigest())
    print(json.dumps(params, indent=1))


def judge(frozen, dirs):
    P = json.load(open(frozen, encoding='utf-8'))['params']
    rows_out = []
    for d in dirs:
        cb = json.load(open(os.path.join(d, 'device', 'common_boundary.json'), encoding='utf-8'))
        rows = [r for r in cb['rows'] if r.get('lane_available_ns') and r.get('terminal_status') == 'succeeded']
        base = os.path.basename(os.path.normpath(d))
        policy = 'CPU_URGENT' if 'CPU_URGENT' in base else 'B2_PARALLEL' if 'B2_PARALLEL' in base else 'NPU_PARALLEL' if 'NPU' in base else None
        if policy is None:
            raise SystemExit(f'policy not in folder name: {base}')
        pts = points(rows, cb['start_ns'] / 1e9, policy)
        for cell in JUDGED:
            if cell[0] != policy:
                continue
            p = P['|'.join(cell)]
            errs = []
            for m in range(1, 10):
                sel = [(c, r) for cc, c, r, mm in pts if cc == cell and mm == m]
                if not sel:
                    continue
                meas = statistics.median(r for _, r in sel)
                pred = statistics.median(float(model(c, p['a'], p['tau_s'])) for c, _ in sel)
                errs.append(pred - meas)
            mae = float(np.mean(np.abs(errs))) if errs else None
            rows_out.append(dict(session=os.path.basename(d), cell='|'.join(cell), mae=mae, ok=mae is not None and mae <= MAE_MAX, minutes=len(errs)))
    ok = sum(r['ok'] for r in rows_out)
    per = {pol: sum(r['ok'] for r in rows_out if r['cell'].startswith(pol)) for pol in ('CPU_URGENT', 'B2_PARALLEL')}
    name = '지속 감속 확인 (ABBA 4 · 200 ms · 10분)' if ok >= 6 and all(v >= 3 for v in per.values()) else '지속 감속 확인 안 됨'
    print(json.dumps(dict(rows=rows_out, ok=ok, per_policy=per, name=name), ensure_ascii=False, indent=1))


def selftest():
    c = np.linspace(0, 600, 50)
    r = model(c, 0.6, 300.0)
    res = least_squares(lambda x: model(c, x[0], x[1]) - r, [0.3, 100.0], bounds=([0, 10], [3, 3000]))
    ok = abs(res.x[0] - 0.6) < 1e-3 and abs(res.x[1] - 300) < 1
    ok &= cum_busy([[0, 1], [2, 4]], 3.0) == 2.0
    print('sustain selftest', 'PASS' if ok else 'FAIL')
    return ok


if __name__ == '__main__':
    a = sys.argv[1:]
    if a and a[0] == 'fit':
        fit(a[1])
    elif a and a[0] == 'judge':
        judge(a[1], a[2:])
    else:
        sys.exit(0 if selftest() else 1)
