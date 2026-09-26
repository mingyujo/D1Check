"""Screen existing exploratory policy results without rerunning the event model."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'docs/results/arrival_diagnostic_02'
OUTPUT = ROOT / 'docs/results/arrival_policy_screen_01'
POLICIES = ('CPU_URGENT', 'FIXED_SPLIT', 'B2_PC', 'B3_SOLO_EFT_PC', 'P_PAIR_COST_PC')
METRICS = ('urgent_p95_ms', 'urgent_not_timely_rate', 'normal_mean_ms',
           'normal_not_timely_rate', 'unfinished')


def read_csv(path):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def dominates(a, b):
    return all(a[k] <= b[k] for k in METRICS) and any(a[k] < b[k] for k in METRICS)


def screen(rows):
    grouped = defaultdict(dict)
    for raw in rows:
        if raw['policy'] == 'P_PAIR_COST_PC' and float(raw['predicted']) != 1.5:
            continue
        key = (raw['scenario'], float(raw['realized']), int(raw['seed']))
        policy = raw['policy']
        if policy not in POLICIES or policy in grouped[key]:
            raise ValueError(f'unsupported or duplicated policy: {key}/{policy}')
        row = {k: float(raw[k]) for k in METRICS}
        row['unfinished'] = int(raw['unfinished'])
        for field in ('planned', 'urgent_planned', 'normal_planned'):
            row[field] = int(raw[field])
        if (row['planned'], row['urgent_planned'], row['normal_planned']) != (24, 6, 18):
            raise ValueError(f'inconsistent denominator: {key}/{policy}')
        for priority, count in (('urgent', 6), ('normal', 18)):
            rate = row[f'{priority}_not_timely_rate']
            if abs(rate * count - round(rate * count)) > 1e-8:
                raise ValueError(f'nonintegral deadline misses: {key}/{policy}')
        grouped[key][policy] = row
    if len(grouped) != 45 or any(set(group) != set(POLICIES) for group in grouped.values()):
        raise ValueError('incomplete scenario/realized/seed comparison')
    if any({(v['planned'], v['urgent_planned'], v['normal_planned']) for v in group.values()} != {(24, 6, 18)}
           for group in grouped.values()):
        raise ValueError('unequal workload')
    output = []
    for scenario in ('low', 'queue', 'burst'):
        for realized in (1., 1.5, 2.):
            seeds = [grouped[scenario, realized, seed] for seed in range(201, 206)]
            means = {policy: {k: sum(seed[policy][k] for seed in seeds) / 5 for k in METRICS}
                     for policy in POLICIES}
            for policy in POLICIES:
                values = [seed[policy] for seed in seeds]
                dominators = [other for other in POLICIES if other != policy and
                              dominates(means[other], means[policy])]
                nondominated_seeds = sum(not any(dominates(seed[other], seed[policy])
                                             for other in POLICIES if other != policy)
                                         for seed in seeds)
                output.append(dict(scenario=scenario, realized=realized, policy=policy,
                    predicted=1.5 if policy == 'P_PAIR_COST_PC' else '',
                    seed_count=5, planned=120, urgent_planned=30, normal_planned=90,
                    unfinished=sum(v['unfinished'] for v in values),
                    urgent_p95_mean_ms=means[policy]['urgent_p95_ms'],
                    urgent_p95_min_ms=min(v['urgent_p95_ms'] for v in values),
                    urgent_p95_max_ms=max(v['urgent_p95_ms'] for v in values),
                    normal_mean_response_ms=means[policy]['normal_mean_ms'],
                    normal_response_min_ms=min(v['normal_mean_ms'] for v in values),
                    normal_response_max_ms=max(v['normal_mean_ms'] for v in values),
                    urgent_miss_count=sum(round(v['urgent_not_timely_rate'] * 6) for v in values),
                    normal_miss_count=sum(round(v['normal_not_timely_rate'] * 18) for v in values),
                    mean_frontier=not dominators, nondominated_seeds=nondominated_seeds,
                    dominated_by=';'.join(dominators)))
    return output


def save(rows, output, source=SOURCE):
    output.mkdir(parents=True, exist_ok=True)
    with (output / 'policy_screen.csv').open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    payload = json.dumps(rows, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
    template = (ROOT / 'tools/assets/d1_arrival_policy_screen.html').read_text(encoding='utf-8')
    (output / 'dashboard.html').write_text(template.replace('/*__ROWS__*/', f'const ROWS={payload};'), encoding='utf-8')
    paths = [source / 'interference_metrics.csv', source / 'energy_boundaries.csv',
             source / 'ap_sensitivity.csv', source / 'CONFIG.json']
    (output / 'SOURCE_HASHES.json').write_text(json.dumps({str(p.relative_to(ROOT) if p.is_relative_to(ROOT) else p):hashlib.sha256(p.read_bytes()).hexdigest()
                                                    for p in paths}, indent=2) + '\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, default=SOURCE)
    parser.add_argument('--output', type=Path, default=OUTPUT)
    args = parser.parse_args()
    rows = screen(read_csv(args.source / 'interference_metrics.csv'))
    save(rows, args.output, args.source)
    print(f'{len(rows)} policy/condition summaries -> {args.output}')


if __name__ == '__main__':
    main()
