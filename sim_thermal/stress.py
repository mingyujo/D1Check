"""SYNTHETIC — 파이프라인 검증 전용. 어떤 주장에도 쓰지 않음.

Stress grid for the pre-registered question (D1_ondevice/sim/응력시험_사전등록_v1.md, 2026-09-27 00:25 KST):
does any scenario make the thermal or battery constraint bind?  Stage 3 fixes the policy (B2_PC);
stage 4 compares policies only at binding points of the realistic region.
  py sim_thermal/stress.py --jo-root <dir containing his tools/> --out <new dir>
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import layer  # noqa: E402
import run  # noqa: E402
import synthetic_bundle  # noqa: E402

INTERVALS_MS = (1200, 200, 80, 40, 20)
HORIZONS_S = (120, 300, 600)
T0_SKIN = (30.0, 34.0, 38.0)
AP_OFFSET = 1.1  # observed load-start medians 30.3 SKIN vs 29.2 AP
GAINS = ('lo', 'mid', 'hi')
T_MAX = (34.0, 36.0, 38.0, 42.0)
BUDGET_PP = (1, 3, 5)
J_PER_PP = 470.0
SEEDS = run.EVAL_SEEDS
MAX_REQUESTS = 128


def realistic(interval_ms, t0):
    return interval_ms >= 80 and t0 <= 34.0


def workload(interval_ms, horizon_s):
    """His workload() rule (every 4th = urgent classification, else normal detection, 1.5 s / 6 s)
    at a fixed interval, capped at his 128-request limit and at the horizon."""
    n = min(MAX_REQUESTS, int(horizon_s * 1000 // interval_ms))
    rows = []
    for i in range(n):
        urgent = i % 4 == 1
        rows.append(dict(id=f'stress/{interval_ms}/{horizon_s}/{i}', task='classification' if urgent else 'detection',
                         priority='urgent' if urgent else 'normal', ordinal=i, arrival_ns=i * interval_ms * 1_000_000,
                         deadline_offset_ns=(1500 if urgent else 6000) * 1_000_000))
    return rows


def params(t0, gain):
    p = run.base_params()
    p['t_init'] = dict(SKIN=t0, AP=t0 - AP_OFFSET)
    p['gain']['SKIN'] = dict(run.GAIN[gain])
    return p


def simulate(jo, config, vectors, b2, policy, reqs, horizon_s, seed):
    s = jo.batch.defaults('explore'); s.update(b2)
    return jo.engine.simulate(config, vectors, reqs, policy=policy, settings=s, seed=seed,
                              horizon_ns=horizon_s * 1_000_000_000)


def thermal_points(jo, config, vectors, b2, policy, interval, horizon, seeds=SEEDS):
    reqs = workload(interval, horizon)
    results = [simulate(jo, config, vectors, b2, policy, reqs, horizon, sd) for sd in seeds]
    out = []
    for t0 in T0_SKIN:
        for g in GAINS:
            ev = [layer.evaluate(r, reqs, params(t0, g), jo.thermal, T_MAX, horizon * 1_000_000_000) for r in results]
            out.append(dict(interval_ms=interval, horizon_s=horizon, t0=t0, gain=g, requests=len(reqs),
                            completion=[r['metrics']['completion'] for r in results],
                            thermal=[e['thermal'] for e in ev], metrics=[e['metrics'] for e in ev]))
    return out


def judge_thermal(point, t_max):
    if point['t0'] >= t_max:
        return 'N/A_start_over'
    th = point['thermal']
    known = [t for t in th if t is not None]
    if len(known) < 3:
        return 'N/A_incomplete'
    over = sum(t['skin_over'][str(t_max)]['seconds'] > 0 for t in known)
    return 'bind' if over >= 3 else 'free'


def judge_battery(point, pp, net=False):
    th = [t for t in point['thermal'] if t is not None]
    if len(th) < 3:
        return 'N/A_incomplete'
    idle = 0.581 * point['horizon_s'] if net else 0.0
    over = sum(t['energy_j'] - idle > pp * J_PER_PP for t in th)
    return 'bind' if over >= 3 else 'free'


def rank(jo, config, vectors, b2, interval, horizon, t0, gain, t_max):
    """Stage 4: 평가층_사전등록_v1 definition (delta=0 + all-seed SKIN no-exceedance)."""
    reqs = workload(interval, horizon)
    rows = {}
    for pol in run.CANDIDATES:
        res = [simulate(jo, config, vectors, b2, pol, reqs, horizon, sd) for sd in SEEDS]
        ev = [layer.evaluate(r, reqs, params(t0, gain), jo.thermal, T_MAX, horizon * 1_000_000_000) for r in res]
        n_norm = sum(e['metrics']['planned'] - e['metrics']['urgent_n'] for e in ev)
        timely = sum((e['metrics']['normal_timely'] or 0) * (e['metrics']['planned'] - e['metrics']['urgent_n']) for e in ev)
        p95 = [e['metrics']['urgent_p95_ms'] for e in ev]
        th = [e['thermal'] for e in ev]
        rows[pol] = dict(normal_violation=1 - timely / n_norm if n_norm else None,
                         urgent_p95_ms=statistics.mean(p95) if all(v is not None for v in p95) else None,
                         thermal_complete=all(t is not None for t in th),
                         skin_over_s=sum(t['skin_over'][str(t_max)]['seconds'] for t in th) if all(th) else None,
                         energy_per_request_j=statistics.mean(t['energy_per_request_j'] for t in th) if all(th) else None,
                         completion=statistics.mean(e['metrics']['completion'] for e in ev))

    def best(thermal):
        ref = rows['CPU_URGENT']['normal_violation']
        elig = [p for p in run.CANDIDATES if rows[p]['normal_violation'] is not None and ref is not None
                and rows[p]['normal_violation'] <= ref + 1e-12 and rows[p]['urgent_p95_ms'] is not None]
        dropped = {}
        if thermal:
            for p in list(elig):
                if not rows[p]['thermal_complete']:
                    dropped[p] = 'incomplete'; elig.remove(p)
                elif rows[p]['skin_over_s'] > 0:
                    dropped[p] = 'skin_over'; elig.remove(p)
        if not elig:
            return [], dropped
        m = min(rows[p]['urgent_p95_ms'] for p in elig)
        return sorted(p for p in elig if abs(rows[p]['urgent_p95_ms'] - m) < 1e-9), dropped

    b0, _ = best(False)
    b1, dropped = best(True)
    cause = None
    if b0 != b1:
        cause = dict(mechanism='탈락' if any(p in dropped for p in b0) else '순서', dropped=dropped,
                     urgent_p95_change_ms=(rows[b1[0]]['urgent_p95_ms'] - rows[b0[0]]['urgent_p95_ms']) if b1 and b0 else None,
                     normal_violation_change=(rows[b1[0]]['normal_violation'] - rows[b0[0]]['normal_violation']) if b1 and b0 else None)
    return dict(point=dict(interval_ms=interval, horizon_s=horizon, t0=t0, gain=gain, t_max=t_max),
                rows=rows, base_best=b0, thermal_best=b1, changed=b0 != b1, cause=cause)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--jo-root', required=True)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=False)
    jo = run.Jo(a.jo_root)
    _, b2_id, b2 = run.select_b2(jo)
    record = dict(banner='SYNTHETIC — 파이프라인 검증 전용. 어떤 주장에도 쓰지 않음', jo_commit=run.JO_COMMIT,
                  prereg='D1_ondevice/sim/응력시험_사전등록_v1.md (2026-09-27 00:25 KST)', b2=b2_id, grid=[],
                  sensitivity=[], stage4=[])
    for interval in INTERVALS_MS:
        for horizon in HORIZONS_S:
            record['grid'] += thermal_points(jo, jo.config, jo.vectors, b2, 'B2_PC', interval, horizon)
    for point in record['grid']:
        point['judge_thermal'] = {str(t): judge_thermal(point, t) for t in T_MAX}
        point['judge_battery'] = {str(b): judge_battery(point, b) for b in BUDGET_PP}
        point['judge_battery_net'] = {str(b): judge_battery(point, b, net=True) for b in BUDGET_PP}
        point['realistic'] = realistic(point['interval_ms'], point['t0'])
    # synthetic-duration sensitivity (pre-registered representative point)
    for scale in (0.5, 1.0, 2.0):
        cfg, vec = synthetic_bundle.build(*jo.bundle_modules, scale=scale)
        for pt in thermal_points(jo, cfg, vec, b2, 'B2_PC', 200, 600):
            if pt['t0'] == 30.0:
                pt['scale'] = scale
                pt['judge_thermal'] = {str(t): judge_thermal(pt, t) for t in T_MAX}
                record['sensitivity'].append(pt)
    # stage 4: realistic binding points only
    seen = set()
    for pt in record['grid']:
        if not pt['realistic']:
            continue
        for t in T_MAX:
            if pt['judge_thermal'][str(t)] == 'bind':
                key = (pt['interval_ms'], pt['horizon_s'], pt['t0'], pt['gain'], t)
                if key not in seen:
                    seen.add(key)
                    record['stage4'].append(rank(jo, jo.config, jo.vectors, b2, *key))
    (out / 'stress_SYNTHETIC.json').write_text(json.dumps(record, ensure_ascii=False, indent=1, default=str), encoding='utf-8')
    print('B2', b2_id, 'grid', len(record['grid']), 'stage4 points', len(record['stage4']))


if __name__ == '__main__':
    main()
