"""Policy x scenario x variant x seed runner (dev seeds only). Pre-registration: sim/시뮬_사전등록_v0.md.

  py -m d1sim.run_compare tune   --out d1sim/out/tune_v0.csv       # v0 hand grid (6) + random search (12)
  py -m d1sim.run_compare select --tune d1sim/out/tune_v0.csv       # apply §5 selection rule -> tune_select.json
  py -m d1sim.run_compare main   --select d1sim/out/tune_select.json --out d1sim/out/main_v0.csv
  py -m d1sim.run_compare sweep  --select d1sim/out/tune_select.json --out d1sim/out/sweep_v0.csv
  py -m d1sim.run_compare report --main d1sim/out/main_v0.csv --sweep d1sim/out/sweep_v0.csv --select d1sim/out/tune_select.json
Deterministic: fixed seeds, fixed search RNG 20260927. Parallel over processes only (no shared state).
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import random
import statistics as st
import sys
from concurrent.futures import ProcessPoolExecutor

from d1sim.env import Sim
from d1sim.kpi import conservation, kpis
from d1sim.policies import Fixed, NpuManagerApprox, OursV0, ShortestLatency
from d1sim.profile import Profile
from d1sim.workload import DEV_SEEDS, scenario

VARIANTS = {
    'V1': dict(npu_cpu_throttle='none', coupling='independent', recovery='same', status_model='zero'),
    'V2': dict(npu_cpu_throttle='scaled', coupling='independent', recovery='same', status_model='zero'),
    'V3': dict(npu_cpu_throttle='none', coupling='shared', recovery='same', status_model='zero'),
    'V4': dict(npu_cpu_throttle='scaled', coupling='shared', recovery='same', status_model='zero'),
    'V5': dict(npu_cpu_throttle='scaled', coupling='shared', recovery='slow', status_model='zero'),
    'V6': dict(npu_cpu_throttle='scaled', coupling='shared', recovery='same', status_model='hal40'),
    'V7': dict(npu_cpu_throttle='none', coupling='independent', recovery='same', status_model='hal40'),
}
HAND = [(0.5, 10, 2), (0, 10, 2), (1, 10, 2), (0.5, 30, 2), (0.5, 10, 5), (1, 30, 5)]
SEARCH_SEED = 20260927
KEEP = ('fg_p95_s', 'fg_p50_s', 'weighted_tardiness', 'deadline_violation_rate', 'reject_rate', 'unfinished',
        'throughput_inf_s', 'bg_completion', 'throttle_s_CPU4', 'throttle_s_GPU', 'throttle_s_NPU', 'exec_s_CPU4',
        'exec_s_GPU', 'exec_s_NPU', 'status2_s', 'energy_j', 'energy_per_inf_mj', 'peak_skin_c', 'first_throttle_s')


def random_configs(n=12):
    rng = random.Random(SEARCH_SEED)
    return [(round(rng.uniform(-1, 2), 3), round(math.exp(rng.uniform(math.log(1), math.log(60))), 3),
             round(math.exp(rng.uniform(math.log(0.5), math.log(20))), 3)) for _ in range(n)]


def make_policy(spec, T_th):
    kind = spec[0]
    if kind == 'fixed':
        return Fixed(spec[1])
    if kind == 'shortest':
        return ShortestLatency()
    if kind == 'npumgr':
        return NpuManagerApprox()
    if kind == 'ours':
        m, L, d = spec[1]
        return OursV0(margin_c=m, lookahead_s=L, defer_s=d, T_th=T_th)
    raise ValueError(spec)


def label(spec):
    return {'fixed': lambda s: f'fixed-{s[1]}', 'shortest': lambda s: 'shortest', 'npumgr': lambda s: 'npumgr',
            'ours': lambda s: f'ours{tuple(s[1])}'}[spec[0]](spec)


def one(job):
    spec, sc, vid, vextra, seed, tag = job
    P = Profile()
    reqs = scenario(sc, seed, P)
    v = dict(VARIANTS[vid], **vextra)
    rec = Sim(P, reqs, v).run(make_policy(spec, P.throttle_gpu['T_th']))
    k = kpis(rec)
    thr = [t for t, _, sg, sn, sc4, _ in rec.trace if min(sg, sn, sc4) < 1 / 1.1]
    k['first_throttle_s'] = thr[0] if thr else None      # device-level: some resource's s below 1/1.1 (trace, 1 s)
    bad = conservation(rec)
    row = dict(tag=tag, policy=label(spec), scenario=sc, variant=vid, extra=json.dumps(vextra, sort_keys=True),
               seed=seed, conservation_ok=not bad, conservation=';'.join(bad[:3]))
    row.update({x: k[x] for x in KEEP})
    return row


def run_jobs(jobs, out):
    rows = []
    with ProcessPoolExecutor(max_workers=max(1, (os.cpu_count() or 2) - 2)) as ex:
        for i, r in enumerate(ex.map(one, jobs, chunksize=1)):
            rows.append(r)
            if i % 100 == 0:
                print(f'{i}/{len(jobs)}', flush=True)
    os.makedirs(os.path.dirname(out) or '.', exist_ok=True)
    with open(out, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print('wrote', out, len(rows), 'conservation failures', sum(not r['conservation_ok'] for r in rows))


def fnum(x):
    return math.inf if x == 'inf' else (None if x in ('', 'None') else float(x))


def load(path):
    return list(csv.DictReader(open(path, encoding='utf-8')))


def cell_stats(rows, key='fg_p95_s'):
    """(policy, scenario, variant, extra) -> dict(seed -> value)."""
    out = {}
    for r in rows:
        out.setdefault((r['policy'], r['scenario'], r['variant'], r['extra']), {})[int(r['seed'])] = r
    return out


def guards_ok(c, b):
    """c, b = dict(seed->row) for candidate and npumgr in one cell. §3 guards on seed medians."""
    med = lambda d, k: st.median(fnum(r[k]) for r in d.values())  # noqa: E731
    ok = med(c, 'deadline_violation_rate') <= med(b, 'deadline_violation_rate') + 0.01
    ok &= med(c, 'reject_rate') <= med(b, 'reject_rate')
    if fnum(next(iter(b.values()))['bg_completion']) is not None:
        ok &= med(c, 'bg_completion') >= med(b, 'bg_completion') - 0.02
    return ok


def ratio(c, b):
    num, den = st.median(fnum(r['fg_p95_s']) for r in c.values()), st.median(fnum(r['fg_p95_s']) for r in b.values())
    if math.isinf(den):
        return 0.0 if not math.isinf(num) else 1.0
    return num / den


def select(rows):
    cells = cell_stats(rows)
    pols = sorted({k[0] for k in cells if k[0].startswith('ours')})
    res = {}
    for p in pols:
        rs, feas, fails = [], True, []
        for sc in ('S1', 'S2'):
            for vid in VARIANTS:
                c, b = cells[(p, sc, vid, '{}')], cells[('npumgr', sc, vid, '{}')]
                rs.append(ratio(c, b))
                if not guards_ok(c, b):
                    feas = False; fails.append(f'{sc}/{vid}')
        res[p] = dict(score=st.mean(rs), feasible=feas, guard_fail_cells=fails)
    return res


def cmd_tune(a):
    hand = [('ours', c) for c in HAND]
    rnd = [('ours', c) for c in random_configs()]
    jobs = [(spec, sc, vid, {}, seed, grp) for grp, specs in (('hand', hand), ('random', rnd), ('base', [('npumgr',)]))
            for spec in specs for sc in ('S1', 'S2') for vid in VARIANTS for seed in DEV_SEEDS]
    run_jobs(jobs, a.out)


def cmd_select(a):
    rows = load(a.tune)
    res = select(rows)
    by_tag = {}
    for r in rows:
        by_tag[r['policy']] = r['tag']
    out = {}
    for grp in ('hand', 'random'):
        cand = {p: v for p, v in res.items() if by_tag[p] == grp}
        feas = {p: v for p, v in cand.items() if v['feasible']}
        best = min(feas, key=lambda p: feas[p]['score']) if feas else None
        best_any = min(cand, key=lambda p: cand[p]['score'])
        out[grp] = dict(best_feasible=best, best_feasible_score=feas[best]['score'] if best else None,
                        best_ignoring_guards=best_any, best_ignoring_guards_score=cand[best_any]['score'],
                        n=len(cand), n_feasible=len(feas), all=cand)
    json.dump(out, open(a.out, 'w', encoding='utf-8'), indent=1)
    for g, v in out.items():
        print(g, 'n', v['n'], 'feasible', v['n_feasible'], 'best', v['best_feasible'], v['best_feasible_score'],
              '| ignoring guards', v['best_ignoring_guards'], round(v['best_ignoring_guards_score'], 4))


def parse_ours(name):
    return ('ours', tuple(float(x) for x in name[len('ours('):-1].split(',')))


def chosen_specs(sel):
    out = []
    for g in ('hand', 'random'):
        p = sel[g]['best_feasible'] or sel[g]['best_ignoring_guards']
        out.append((g, parse_ours(p)))
    return out


def cmd_main(a):
    sel = json.load(open(a.select, encoding='utf-8'))
    specs = [('fixed', 'CPU4'), ('fixed', 'GPU'), ('fixed', 'NPU'), ('shortest',), ('npumgr',)]
    jobs = [(s, sc, vid, {}, seed, 'baseline') for s in specs for sc in ('S0', 'S1', 'S2') for vid in VARIANTS for seed in DEV_SEEDS]
    jobs += [(s, sc, vid, {}, seed, f'chosen-{g}') for g, s in chosen_specs(sel) for sc in ('S0', 'S1', 'S2')
             for vid in VARIANTS for seed in DEV_SEEDS]
    run_jobs(jobs, a.out)


SWEEP = [dict(T_th_shift=x) for x in (-2, -1, 1, 2)] + [dict(tau_scale=x) for x in (0.5, 2)] + \
        [dict(cross_scale=x) for x in (0.5, 2)]


def cmd_sweep(a):
    sel = json.load(open(a.select, encoding='utf-8'))
    ours = [s for g, s in chosen_specs(sel) if g == 'hand']
    specs = [('fixed', 'NPU'), ('npumgr',)] + ours
    jobs = [(s, sc, vid, ex, seed, 'sweep') for s in specs for sc in ('S1', 'S2') for vid in ('V2', 'V4')
            for ex in SWEEP for seed in DEV_SEEDS]
    run_jobs(jobs, a.out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd')
    ap.add_argument('--out')
    ap.add_argument('--tune')
    ap.add_argument('--select')
    a = ap.parse_args()
    {'tune': cmd_tune, 'select': cmd_select, 'main': cmd_main, 'sweep': cmd_sweep}[a.cmd](a)


if __name__ == '__main__':
    sys.exit(main())
