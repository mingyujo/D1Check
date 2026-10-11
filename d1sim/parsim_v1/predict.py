"""Frozen confirmation predictions (stage 3-4): R4 (C) 16 sessions + R4 (S) 14 valid sessions, closed loop
(requests -> rule -> lanes -> activity -> thermal -> controller ratio), M-sup and M-kappa, 20 replicates each (seed 1001 ~ 1020).

Inputs = data/r4_start.csv (start state + policy + pair; no outcome) + data/r4_schedule.csv (planned requests) + profiles/parsim_v1_thermal_sum.json
Output = out/predict_confirm.json — written ONCE (refuses if it exists). Per session and replicate: urgent / normal P95 (ms),
on-time count, completed, 1 s model path (SKIN, AP), energy (model input, J — description only).

usage: python -m d1sim.parsim_v1.predict [--out PATH] [--reps 20] [--selftest]
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

from d1sim.parsim_v1 import rules
from d1sim.parsim_v1 import service_des as sd
from d1sim.parsim_v1 import thermal_sum as ts

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, 'data')
PROFILE = os.path.join(os.path.dirname(HERE), 'profiles', 'parsim_v1_thermal_sum.json')
OUT = os.path.join(HERE, 'out', 'predict_confirm.json')
SEEDS = tuple(range(1001, 1021))


def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


def load_profile(path=PROFILE):
    return json.load(open(path, encoding='utf-8'))


def forms(profile):
    return {'M-sup': (profile['M_sup']['g'], 1.0), 'M-kappa': (profile['M_kappa']['g'], profile['M_kappa']['kappa'])}


def requests_from_schedule(rows):
    return [dict(ordinal=int(r['ordinal']), task=r['task_id'], priority=r['priority'], sched=int(r['offset_ms']) / 1000.0,
                 deadline=int(r['deadline_ms']) / 1000.0) for r in sorted(rows, key=lambda r: int(r['ordinal']))]


def start_state(s):
    return dict(skin0=float(s['start_skin']), ap0=float(s['start_ap']), bat0=float(s['start_bat']),
                a0=float(s['gate_ap']) - float(s['gate_skin']))


def run_one(rule, svc, params, g, kappa, st, reqs, window_s, seed):
    dev = ts.Device(params, g, kappa, st['skin0'], st['ap0'], st['bat0'], st['a0'])
    eng = sd.Engine(rule, svc, dev, reqs, window_s, seed)
    res = eng.run()
    urg = [r['response'] for r in res['rows'] if r['priority'] == 'urgent']
    nor = [r['response'] for r in res['rows'] if r['priority'] == 'normal']
    # 1 s path (from the 0.5 s grid)
    pt, pk, pa = res['path_t'], res['path_skin'], res['path_ap']
    n = int(math.floor(window_s)) + 1
    path_skin = [round(sd.interp(pt, pk, float(t)), 4) for t in range(n)]
    path_ap = [round(sd.interp(pt, pa, float(t)), 4) for t in range(n)]
    p95u = sd.nearest_rank_p95(urg)
    p95n = sd.nearest_rank_p95(nor)
    return dict(seed=seed, urgent_p95_ms=None if p95u is None or math.isinf(p95u) else p95u * 1000.0,
                normal_p95_ms=None if p95n is None or math.isinf(p95n) else p95n * 1000.0,
                urgent_unfinished=sum(1 for x in urg if math.isinf(x)),
                on_time=sum(1 for r in res['rows'] if r['on_time']), completed=sum(1 for r in res['rows'] if r['status'] == 'succeeded'),
                planned=len(res['rows']), ap_max_path=max(pa), skin_max_path=max(pk), energy_J=res['energy_J'],
                lanes={k: v for k, v in _lane_counts(res['rows']).items()}, path_skin=path_skin, path_ap=path_ap)


def _lane_counts(rows):
    c = defaultdict(int)
    for r in rows:
        c[f"{r['task']}@{r.get('resource')}"] += 1
    return c


def predict(reps=20, out=OUT):
    if os.path.exists(out):
        raise SystemExit(f'refuse: {out} exists (frozen predictions are written once)')
    prof = load_profile()
    params = ts.load_v22()
    svc = sd.ServiceModel()
    sched = defaultdict(list)
    for r in csv.DictReader(open(os.path.join(DATA, 'r4_schedule.csv'), encoding='utf-8')):
        sched[(r['set'], r['index'])].append(r)
    sessions = []
    for s in csv.DictReader(open(os.path.join(DATA, 'r4_start.csv'), encoding='utf-8')):
        if s['valid_log'] != 'True':
            continue
        reqs = requests_from_schedule(sched[(s['set'], s['index'])])
        window_s = float(s['common_s'])
        st = start_state(s)
        entry = dict(set=s['set'], index=int(s['index']), folder=s['folder'], session_id=s['session_id'], policy=s['policy'],
                     block=s['block'], pair=int(s['pair']), start=st, window_s=window_s, planned=len(reqs), forms={})
        for form, (g, kappa) in forms(prof).items():
            reps_out = []
            for seed in SEEDS[:reps]:
                rule = rules.MEASURED[s['policy']]()
                reps_out.append(run_one(rule, svc, params, g, kappa, st, reqs, window_s, seed))
            med = lambda k: statistics.median([x[k] for x in reps_out if x[k] is not None]) if any(x[k] is not None for x in reps_out) else None
            entry['forms'][form] = dict(g=g, kappa=kappa, median=dict(urgent_p95_ms=med('urgent_p95_ms'), normal_p95_ms=med('normal_p95_ms'),
                                                                     on_time=med('on_time'), ap_max_path=med('ap_max_path'),
                                                                     skin_max_path=med('skin_max_path'), energy_J=med('energy_J')),
                                        reps=reps_out)
        sessions.append(entry)
        print(f"{s['set']} {int(s['index']):2d} {s['policy'][:10]:10s} " + ' | '.join(
            f"{f}: P95 {e['median']['urgent_p95_ms']:.1f} ms AP {e['median']['ap_max_path']:.2f} SKIN {e['median']['skin_max_path']:.2f}"
            for f, e in entry['forms'].items()), flush=True)
    doc = dict(what='P1l frozen confirmation predictions (closed loop) — R4 (C) 16 + R4 (S) valid 14',
               registration='d1sim/docs/병행시뮬_사전등록_v1.md sha256 81a5428dcab8053f8c65b8623c1d64a8c333f3e111885287f9508098e2299e0f',
               decisions='d1sim/parsim_v1/DECISIONS_P1l.md D5 · D6 · D9', seeds=list(SEEDS[:reps]),
               inputs=dict(profile=sha(PROFILE), r4_start=sha(os.path.join(DATA, 'r4_start.csv')),
                           r4_schedule=sha(os.path.join(DATA, 'r4_schedule.csv')), r3_requests=sha(os.path.join(DATA, 'r3_requests.csv')),
                           r3_sessions=sha(os.path.join(DATA, 'r3_sessions.csv'))),
               code={f: sha(os.path.join(HERE, f)) for f in ('thermal_sum.py', 'service_des.py', 'rules.py', 'predict.py')},
               sessions=sessions)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, separators=(',', ':'))
    print('wrote', out, sha(out))
    return doc


def selftest():
    prof = load_profile()
    params = ts.load_v22()
    svc = sd.ServiceModel()
    reqs = [dict(ordinal=i, task='classification' if i % 2 == 0 else 'detection', priority='urgent' if i % 2 == 0 else 'normal',
                 sched=35.0 + 0.2 * i, deadline=1.5 if i % 2 == 0 else 6.0) for i in range(192)]
    st = dict(skin0=30.5, ap0=29.5, bat0=30.5 - params['thermal']['d_ref'], a0=-1.0)
    a = run_one(rules.R3(), svc, params, prof['M_sup']['g'], 1.0, st, reqs, 120.0, 7)
    b = run_one(rules.R3(), svc, params, prof['M_sup']['g'], 1.0, st, reqs, 120.0, 7)
    c = run_one(rules.R2(), svc, params, prof['M_sup']['g'], 1.0, st, reqs, 120.0, 7)
    ok = a['urgent_p95_ms'] == b['urgent_p95_ms'] and a['path_ap'] == b['path_ap']           # deterministic
    ok &= a['completed'] == 192 and c['completed'] == 192
    ok &= c['urgent_p95_ms'] > a['urgent_p95_ms']                                              # serial queues urgent behind detection
    ok &= len(a['path_ap']) == 121
    print('predict selftest', 'PASS' if ok else 'FAIL', a['urgent_p95_ms'], c['urgent_p95_ms'], round(a['ap_max_path'], 2), round(c['ap_max_path'], 2))
    return ok


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=OUT)
    ap.add_argument('--reps', type=int, default=20)
    ap.add_argument('--selftest', action='store_true')
    a = ap.parse_args(argv)
    if a.selftest:
        return 0 if selftest() else 1
    predict(a.reps, a.out)


if __name__ == '__main__':
    sys.exit(main())
