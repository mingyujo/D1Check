"""Rule ladder (registration §5; details DECISIONS_P1l.md D7 · D13). Runs after the confirmation judgement; status of every
statement follows the judgement names (M-sup). R5 ~ R8 (three lanes at once) are extrapolation.

  step 1  --dev      : R7 offset in {0, -0.5} chosen on development seeds 1 ~ 10 (all loads) -> out/ladder_dev.json (once)
  step 2  --confirm  : all rules x loads x confirmation seeds 61 ~ 65 ONCE -> out/ladder.json + ladder.csv + ladder_pairs.csv

usage: python -m d1sim.parsim_v1.ladder --dev | --confirm [--status-json out/parsim_judge.json] | --selftest
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

from d1sim.parsim_v1 import rules
from d1sim.parsim_v1 import service_des as sd
from d1sim.parsim_v1 import thermal_sum as ts

HERE = os.path.dirname(os.path.abspath(__file__))
OUTDIR = os.path.join(HERE, 'out')
PROFILE = os.path.join(os.path.dirname(HERE), 'profiles', 'parsim_v1_thermal_sum.json')
LOADS = {'a400': (192, 0.4), 'a200': (192, 0.2), 'a100': (192, 0.1), 'b200': (3000, 0.2)}
DEV_SEEDS = tuple(range(1, 11))
CONF_SEEDS = tuple(range(61, 66))
GUARD_P95_MS = 1500.0
SEL = dict(C=1.0, s=60.0)


def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


def load_requests(n, dt):
    return [dict(ordinal=i, task='classification' if i % 2 == 0 else 'detection', priority='urgent' if i % 2 == 0 else 'normal',
                 sched=35.0 + dt * i, deadline=1.5 if i % 2 == 0 else 6.0) for i in range(n)]


def window(n, dt):
    return 720.0 if n == 3000 else max(120.0, 35.0 + n * dt + 50.0)


def rule_set(offset):
    return [rules.R1(), rules.R2(), rules.R3(), rules.R4(), rules.R5(), rules.R6(), rules.R7(offset), rules.R8()]


def run(rule, svc, params, g, kappa, load, seed):
    n, dt = LOADS[load]
    reqs = load_requests(n, dt)
    tp = params['thermal']
    dev = ts.Device(params, g, kappa, 30.5, 29.5, 30.5 - tp['d_ref'], -1.0)
    win = window(n, dt)
    eng = sd.Engine(rule, svc, dev, reqs, win, seed)
    res = eng.run()
    rows = res['rows']
    urg = [r['response'] for r in rows if r['priority'] == 'urgent']
    p95 = sd.nearest_rank_p95(urg)
    done = [r for r in rows if r['status'] == 'succeeded']
    last = max((r['output_ready'] if r['priority'] == 'urgent' else r['persist_complete']) for r in done) if done else math.nan
    on_time = sum(1 for r in rows if r['on_time'])
    pt, pk = res['path_t'], res['path_skin']
    t38 = sum((pt[i + 1] - pt[i]) for i in range(len(pt) - 1) if pk[i] >= 38.0)
    lanes = {}
    for r in rows:
        k = f"{r['task']}@{r.get('resource')}"
        lanes[k] = lanes.get(k, 0) + 1
    return dict(rule=rule.name, load=load, seed=seed, planned=len(rows), on_time=on_time, completed=len(done),
                urgent_p95_ms=None if math.isinf(p95) else p95 * 1000.0,
                guard_on_time=on_time == len(rows), guard_p95=(not math.isinf(p95)) and p95 * 1000.0 <= GUARD_P95_MS,
                ap_max=max(res['path_ap']), skin_max=max(pk), skin38_s=t38,
                throughput_rps=len(done) / (last - reqs[0]['sched']) if done else 0.0, energy_J=res['energy_J'], lanes=lanes)


def g_kappa(form='M-sup'):
    p = json.load(open(PROFILE, encoding='utf-8'))
    return (p['M_sup']['g'], 1.0) if form == 'M-sup' else (p['M_kappa']['g'], p['M_kappa']['kappa'])


def dev_step():
    target = os.path.join(OUTDIR, 'ladder_dev.json')
    if os.path.exists(target):
        raise SystemExit('refuse: ladder_dev.json exists')
    svc, params = sd.ServiceModel(), ts.load_v22()
    g, kappa = g_kappa()
    res = {}
    for off in (0.0, -0.5):
        runs = [run(rules.R7(off), svc, params, g, kappa, load, s) for load in LOADS for s in DEV_SEEDS]
        res[str(off)] = dict(guard_both=sum(r['guard_on_time'] and r['guard_p95'] for r in runs),
                             ap_max_mean=statistics.fmean(r['ap_max'] for r in runs), runs=runs)
    a, b = res['0.0'], res['-0.5']
    if b['guard_both'] > a['guard_both'] or (b['guard_both'] == a['guard_both'] and b['ap_max_mean'] < a['ap_max_mean'] - 1e-12):
        chosen = -0.5
    else:
        chosen = 0.0
    doc = dict(rule='DECISIONS D7: guard-both count -> lower mean max AP -> 0', seeds=list(DEV_SEEDS), chosen_offset=chosen,
               summary={k: dict(guard_both=v['guard_both'], ap_max_mean=v['ap_max_mean']) for k, v in res.items()}, detail=res,
               code={f: sha(os.path.join(HERE, f)) for f in ('rules.py', 'service_des.py', 'thermal_sum.py', 'ladder.py')})
    os.makedirs(OUTDIR, exist_ok=True)
    json.dump(doc, open(target, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('R7 offset chosen', chosen, doc['summary'], 'wrote', target, sha(target))
    return chosen


def cv(xs):
    m = statistics.fmean(xs)
    return statistics.pstdev(xs) / m if m else 0.0


def confirm_step(status_json):
    target = os.path.join(OUTDIR, 'ladder.json')
    if os.path.exists(target):
        raise SystemExit('refuse: ladder.json exists (confirmation seeds once)')
    dev = json.load(open(os.path.join(OUTDIR, 'ladder_dev.json'), encoding='utf-8'))
    offset = dev['chosen_offset']
    status = json.load(open(status_json, encoding='utf-8'))
    f = status['forms']['M-sup']
    th_err = max(f['confirm_mae']['ap_path_mae_median_C'], f['confirm_mae']['ap_path_mae_median_S'])
    sv_err = f['confirm_mae']['p95_abs_err_median_C']
    svc, params = sd.ServiceModel(), ts.load_v22()
    g, kappa = g_kappa()
    runs = []
    for load in LOADS:
        for rule in rule_set(offset):
            for s in CONF_SEEDS:
                rr = rule_set(offset)[[x.name for x in rule_set(offset)].index(rule.name)]
                runs.append(run(rr, svc, params, g, kappa, load, s))
    agg = {}
    for r in runs:
        agg.setdefault((r['load'], r['rule']), []).append(r)
    table = []
    for (load, rule), rs in agg.items():
        p95s = [x['urgent_p95_ms'] for x in rs if x['urgent_p95_ms'] is not None]
        table.append(dict(load=load, rule=rule, extrapolation=rule.startswith(('R5', 'R6', 'R7', 'R8')),
                          guard_pass=all(x['guard_on_time'] and x['guard_p95'] for x in rs),
                          on_time_min=min(x['on_time'] for x in rs), planned=rs[0]['planned'],
                          urgent_p95_ms_mean=statistics.fmean(p95s) if len(p95s) == len(rs) else None,
                          urgent_p95_cv=cv(p95s) if len(p95s) == len(rs) else None,
                          ap_max_mean=statistics.fmean(x['ap_max'] for x in rs), skin_max_mean=statistics.fmean(x['skin_max'] for x in rs),
                          skin38_s_mean=statistics.fmean(x['skin38_s'] for x in rs),
                          throughput_rps_mean=statistics.fmean(x['throughput_rps'] for x in rs),
                          energy_J_mean=statistics.fmean(x['energy_J'] for x in rs)))
    pairs = []
    for load in LOADS:
        rows = [t for t in table if t['load'] == load]
        for i, a in enumerate(rows):
            for b in rows[i + 1:]:
                if not (a['guard_pass'] and b['guard_pass']):
                    pairs.append(dict(load=load, a=a['rule'], b=b['rule'], readout='가드 미통과 쌍 — 열 비교 안 함'))
                    continue
                d_ap = b['ap_max_mean'] - a['ap_max_mean']
                d_38 = b['skin38_s_mean'] - a['skin38_s_mean']
                p95_thr = max(0.05 * a['urgent_p95_ms_mean'], 2 * max(a['urgent_p95_cv'], b['urgent_p95_cv']) * a['urgent_p95_ms_mean'])
                d_p95 = b['urgent_p95_ms_mean'] - a['urgent_p95_ms_mean']
                if abs(d_ap) < SEL['C'] and abs(d_38) < SEL['s']:
                    th = '열 차이 없음 (선별 문턱 아래)'
                elif abs(d_ap) < th_err:
                    th = '모형 오차 안 — 우열 미판정'
                else:
                    th = ('b 가 더 뜨거움' if d_ap > 0 else 'b 가 덜 뜨거움') + ' (모형 위 · 오차 밖)'
                if abs(d_p95) < p95_thr:
                    sv = '긴급 P95 차이 없음 (선별 문턱 아래)'
                elif abs(d_p95) < sv_err:
                    sv = '모형 오차 안 — 우열 미판정'
                else:
                    sv = 'b 가 더 느림' if d_p95 > 0 else 'b 가 더 빠름'
                tag = ' · 외삽' if (a['extrapolation'] or b['extrapolation']) else ''
                pairs.append(dict(load=load, a=a['rule'], b=b['rule'], d_ap_max=d_ap, d_skin38_s=d_38, d_urgent_p95_ms=d_p95,
                                  p95_threshold_ms=p95_thr, readout=f'열: {th} · 서비스: {sv}{tag}'))
    doc = dict(registration='§5', decisions='D7 · D13', offset=offset, seeds=list(CONF_SEEDS), form='M-sup',
               thermal_err_C=th_err, service_err_ms=sv_err, status=f['names'], table=table, pairs=pairs, runs=runs,
               code={x: sha(os.path.join(HERE, x)) for x in ('rules.py', 'service_des.py', 'thermal_sum.py', 'ladder.py')})
    json.dump(doc, open(target, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    for fn, rows in (('ladder.csv', table), ('ladder_pairs.csv', pairs)):
        keys = sorted({k for r in rows for k in r}, key=lambda k: list(rows[0].keys()).index(k) if k in rows[0] else 99)
        with open(os.path.join(OUTDIR, fn), 'w', encoding='utf-8', newline='\n') as fh:
            w = csv.DictWriter(fh, fieldnames=keys, lineterminator='\n')
            w.writeheader()
            w.writerows(rows)
    print('wrote', target, sha(target))
    return doc


def selftest():
    svc, params = sd.ServiceModel(), ts.load_v22()
    g, kappa = g_kappa()
    a = run(rules.R2(), svc, params, g, kappa, 'a200', 3)
    b = run(rules.R2(), svc, params, g, kappa, 'a200', 3)
    c = run(rules.R5(), svc, params, g, kappa, 'a100', 3)
    ok = a == b and a['planned'] == 192 and c['planned'] == 192 and set(LOADS) == {'a400', 'a200', 'a100', 'b200'}
    print('ladder selftest', 'PASS' if ok else 'FAIL', a['urgent_p95_ms'], a['guard_on_time'], c['lanes'])
    return ok


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--dev', action='store_true')
    ap.add_argument('--confirm', action='store_true')
    ap.add_argument('--status-json', default=os.path.join(OUTDIR, 'parsim_judge.json'))
    ap.add_argument('--selftest', action='store_true')
    a = ap.parse_args(argv)
    if a.selftest:
        return 0 if selftest() else 1
    if a.dev:
        dev_step()
    if a.confirm:
        confirm_step(a.status_json)


if __name__ == '__main__':
    sys.exit(main())
