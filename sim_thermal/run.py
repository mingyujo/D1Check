"""SYNTHETIC — 파이프라인 검증 전용. 어떤 주장에도 쓰지 않음.

Runs the pre-registered evaluation (D1_ondevice/sim/평가층_사전등록_v1.md, 2026-09-26 22:40 KST).
조민규 code is imported from an extracted copy (never committed here):
  py sim_thermal/run.py --jo-root <dir containing his tools/> --out <new dir>
"""
from __future__ import annotations

import argparse
import copy
import itertools
import json
import math
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import layer  # noqa: E402
import synthetic_bundle  # noqa: E402

JO_COMMIT = '36632fadf67f52791d8681e18027927ba05f0011'
CANDIDATES = ('CPU_URGENT', 'FIXED_SPLIT', 'B2_PC', 'B3_SOLO_EFT_PC', 'P_PAIR_COST_PC')
SCENARIOS = ('queue', 'low', 'burst')
EVAL_SEEDS = (201, 202, 203, 204, 205)
DEV_SEEDS = (101, 102, 103)
T_MAX = (34.0, 36.0, 38.0, 42.0)
BASE_T_MAX = 36.0
GAIN = {  # SKIN degC/W: [observed 60 s transient, extrapolated median, extrapolated max]
    'lo': dict(CPU=0.90, GPU=0.95), 'mid': dict(CPU=1.00, GPU=1.15), 'hi': dict(CPU=2.08, GPU=1.55)}
GAIN_KIND = dict(lo='관측 60 s 과도', mid='외삽(점근 중앙)', hi='외삽(점근 최대)')
TAU_SKIN = {'min': dict(CPU=12.0, GPU=22.9), 'med': dict(CPU=19.5, GPU=34.4), 'max': dict(CPU=45.5, GPU=45.8)}


def base_params():
    return dict(busy_w=dict(CPU=7.259, GPU=6.457), idle_w=0.581, busy_scale=1.0, parallel_k=1.25,
                nonexec_power='idle',
                gain=dict(SKIN=dict(GAIN['mid']), AP=dict(CPU=2.08, GPU=2.07)),
                tau_heat=dict(SKIN=dict(TAU_SKIN['med']), AP=dict(CPU=3.8, GPU=17.0)),
                tau_cool=dict(SKIN=85.0, AP=45.0), t_init=dict(SKIN=30.3, AP=29.2),
                provenance=dict(busy_w='repurposed_assumption (S26 MobileNet CPU4/GPU d100 load W)',
                                idle_w='repurposed_assumption (S26 100-run idle median)',
                                parallel_k='exploration (concurrent power null)', gain='assumed range',
                                tau='assumed from S26 fits'))


class Jo:
    def __init__(self, root):
        sys.path.insert(0, str(root))
        from tools import d1_arrival_explore as engine
        from tools import d1_arrival_explore_batch as batch
        from tools import d1_energy_thermal as thermal
        from tools import d1_cal03_connection as c
        from tools import d1_arrival_timing_dev as legacy
        self.engine, self.batch, self.thermal = engine, batch, thermal
        self.config, self.vectors = synthetic_bundle.build(c, legacy)
        self.bundle_modules = (c, legacy)


def select_b2(jo):
    """조민규 run() B2 rule, explore mode only, copied without change of criteria."""
    sim = lambda name, pol, s, seed: jo.engine.simulate(jo.config, jo.vectors, jo.batch.workload(name, 'development'),
                                                        policy=pol, settings=s, seed=seed)['metrics']
    refs = {n: [sim(n, 'CPU_URGENT', jo.batch.defaults('explore'), sd) for sd in DEV_SEEDS] for n in ('low', 'queue', 'burst')}
    cands = []
    for cc, dd, par in itertools.product(('CPU', 'GPU'), ('CPU', 'GPU'), (False, True)):
        s = jo.batch.defaults('explore'); s.update(static_map=dict(classification=cc, detection=dd), static_parallel=par)
        rows, ok = [], True
        for n in ('low', 'queue', 'burst'):
            ms = [sim(n, 'B2_PC', s, sd) for sd in DEV_SEEDS]
            mean = lambda g, k: statistics.mean(m[k] for m in g)
            ok &= all(m['completion'] == 1 for m in ms) and mean(ms, 'normal_mean_ms') <= mean(refs[n], 'normal_mean_ms') + 1e-9 \
                and mean(ms, 'normal_timely') >= mean(refs[n], 'normal_timely') - 1e-12
            rows += ms
        score = [statistics.mean(m[k] for m in rows) for k in ('urgent_deadline_violation', 'urgent_p95_ms', 'normal_mean_ms', 'makespan_s')]
        if ok:
            cands.append((score, f'{cc}_{dd}_{"parallel" if par else "serial"}', dict(static_map=s['static_map'], static_parallel=par)))
    if not cands:
        raise ValueError('no feasible static candidate; do not relax constraint')
    return min(cands, key=lambda x: (x[0], x[1]))


def schedules(jo, b2, changes, policies):
    out = {}
    for scen in SCENARIOS:
        reqs = jo.batch.workload(scen, 'evaluation')
        for seed in EVAL_SEEDS:
            for pol in policies:
                s = jo.batch.defaults('explore'); s.update(b2); s.update(changes)
                out[(scen, seed, pol)] = (reqs, jo.engine.simulate(jo.config, jo.vectors, reqs, policy=pol, settings=s, seed=seed))
    return out


def evaluate_all(jo, sched, params):
    return {k: layer.evaluate(res, reqs, params, jo.thermal, T_MAX) for k, (reqs, res) in sched.items()}


def aggregate(evals, t_max):
    """Per scenario x policy, the pre-registered aggregation."""
    rows = {}
    for scen in SCENARIOS:
        for pol in CANDIDATES:
            g = [evals[(scen, sd, pol)] for sd in EVAL_SEEDS]
            normal_planned = sum(e['metrics']['planned'] - e['metrics']['urgent_n'] for e in g)
            normal_timely = sum(e['metrics']['normal_timely'] * (e['metrics']['planned'] - e['metrics']['urgent_n']) for e in g)
            th = [e['thermal'] for e in g]
            thermal_ok = all(t is not None for t in th)
            rows[(scen, pol)] = dict(
                normal_violation=1 - normal_timely / normal_planned,
                urgent_p95_ms=statistics.mean(e['metrics']['urgent_p95_ms'] for e in g),
                normal_mean_ms=statistics.mean(e['metrics']['normal_mean_ms'] for e in g),
                completion=statistics.mean(e['metrics']['completion'] for e in g),
                makespan_s=statistics.mean(e['metrics']['makespan_s'] for e in g) if all(e['metrics']['makespan_s'] for e in g) else None,
                thermal_complete=thermal_ok,
                skin_over_s=sum(t['skin_over'][str(t_max)]['seconds'] for t in th) if thermal_ok else None,
                skin_over_entries=sum(t['skin_over'][str(t_max)]['entries'] for t in th) if thermal_ok else None,
                peak_skin_c=max(t['peak_skin_c'] for t in th) if thermal_ok else None,
                energy_per_request_j=statistics.mean(t['energy_per_request_j'] for t in th) if thermal_ok else None,
                energy_j=statistics.mean(t['energy_j'] for t in th) if thermal_ok else None,
                parallel_execute_s=statistics.mean(t['parallel_execute_s'] for t in th) if thermal_ok else None)
    return rows


def best(rows, scen, thermal):
    ref = rows[(scen, 'CPU_URGENT')]['normal_violation']
    elig = [p for p in CANDIDATES if rows[(scen, p)]['normal_violation'] <= ref + 1e-12]
    dropped = {}
    if thermal:
        for p in list(elig):
            r = rows[(scen, p)]
            if not r['thermal_complete']:
                dropped[p] = 'incomplete'; elig.remove(p)
            elif r['skin_over_s'] > 0:
                dropped[p] = 'skin_over'; elig.remove(p)
    if not elig:
        return [], dropped
    m = min(rows[(scen, p)]['urgent_p95_ms'] for p in elig)
    return sorted(p for p in elig if abs(rows[(scen, p)]['urgent_p95_ms'] - m) < 1e-9), dropped


def verdict(rows):
    out = {}
    for scen in SCENARIOS:
        b0, _ = best(rows, scen, False)
        b1, dropped = best(rows, scen, True)
        order_p95 = sorted(CANDIDATES, key=lambda p: rows[(scen, p)]['urgent_p95_ms'])
        energy = [p for p in CANDIDATES if rows[(scen, p)]['energy_per_request_j'] is not None]
        order_e = sorted(energy, key=lambda p: rows[(scen, p)]['energy_per_request_j'])
        cause = None
        if b0 != b1:
            cause = dict(mechanism='탈락' if any(p in dropped for p in b0) else '순서',
                         dropped=dropped,
                         urgent_p95_change_ms=(rows[(scen, b1[0])]['urgent_p95_ms'] - rows[(scen, b0[0])]['urgent_p95_ms']) if b1 else None,
                         normal_violation_change=(rows[(scen, b1[0])]['normal_violation'] - rows[(scen, b0[0])]['normal_violation']) if b1 else None)
        out[scen] = dict(base_best=b0, thermal_best=b1, changed=b0 != b1, dropped=dropped, cause=cause,
                         p95_order=order_p95, energy_order=order_e, energy_order_differs=order_e != [p for p in order_p95 if p in energy])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--jo-root', required=True)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=False)
    jo = Jo(a.jo_root)
    policies = list(jo.engine.POLICIES)
    score, b2_id, b2 = select_b2(jo)
    record = dict(banner='SYNTHETIC — 파이프라인 검증 전용. 어떤 주장에도 쓰지 않음', jo_commit=JO_COMMIT,
                  bundle_provenance=synthetic_bundle.PROVENANCE, b2=dict(id=b2_id, score=score, settings=b2),
                  base_params=base_params(), runs={})

    def run_case(name, changes, params, t_max=BASE_T_MAX, cache={}):
        key = json.dumps(changes, sort_keys=True)
        if key not in cache:
            cache[key] = schedules(jo, b2, changes, policies)
        rows = aggregate(evaluate_all(jo, cache[key], params), t_max)
        record['runs'][name] = dict(changes=changes, t_max=t_max,
                                    rows={f'{s}|{p}': v for (s, p), v in rows.items()}, verdict=verdict(rows))
        return record['runs'][name]

    P = base_params
    run_case('base', {}, P())
    for g in ('lo', 'mid', 'hi'):
        p = P(); p['gain']['SKIN'] = dict(GAIN[g]); run_case(f'gain_{g}', {}, p)
    for t in ('min', 'med', 'max'):
        p = P(); p['tau_heat']['SKIN'] = dict(TAU_SKIN[t]); run_case(f'tau_skin_{t}', {}, p)
    for tm in T_MAX:
        run_case(f't_max_{tm:g}', {}, P(), t_max=tm)
    for b in (0.8, 1.0, 1.2):
        p = P(); p['busy_scale'] = b; run_case(f'busy_x{b}', {}, p)
    for k in (1.0, 1.25, 1.5):
        p = P(); p['parallel_k'] = k; run_case(f'parallel_k{k}', {}, p)
    for n in ('idle', 'busy'):
        p = P(); p['nonexec_power'] = n; run_case(f'nonexec_{n}', {}, p)
    for v in (1.0, 1.5, 2.0):
        run_case(f'interf_A_actual_{v}', dict(interference=v, predicted_interference=1.5), P())
        run_case(f'interf_B_predicted_{v}', dict(interference=1.5, predicted_interference=v), P())
        run_case(f'interf_C_both_{v}', dict(interference=v, predicted_interference=v), P())
    for g, v in itertools.product(('lo', 'mid', 'hi'), (1.0, 1.5, 2.0)):
        p = P(); p['gain']['SKIN'] = dict(GAIN[g]); run_case(f'grid_gain_{g}_interfC_{v}', dict(interference=v, predicted_interference=v), p)
    (out / 'results.json').write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding='utf-8')
    print('B2', b2_id)
    for name, r in record['runs'].items():
        print(name, {s: (v['base_best'], v['thermal_best'], v['changed']) for s, v in r['verdict'].items()})


if __name__ == '__main__':
    main()
