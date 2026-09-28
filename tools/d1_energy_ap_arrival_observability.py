"""Audit stored PC arrival schedules against A24 sensor cadence; no model fitting.

The stored schedule is a simulation, not an Android measurement. This module only
counts lane/inference occupancy and deliberately never estimates state power.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import statistics
from collections import defaultdict
from pathlib import Path

SOURCE = Path('docs/results/arrival_visualization_01/timeline.csv')
SCENARIO = 'queue'
SEED = '201'
MODE = 'strict'
POLICIES = ('CPU_URGENT', 'FIXED_SPLIT')
HORIZON_NS = 120_000_000_000
CADENCES_S = {'power_nominal': 1.0, 'ap_observed_approx': 2.65}


def read_rows(path: Path) -> list[dict]:
    with path.open(encoding='utf-8-sig', newline='') as stream:
        return [r for r in csv.DictReader(stream) if r['mode'] == MODE and
                r['scenario'] == SCENARIO and r['seed'] == SEED and r['policy'] in POLICIES]


def segments(rows: list[dict], start_field: str, end_field: str) -> list[dict]:
    """Partition a common clock window without adding idle to occupied states."""
    changes = defaultdict(list)
    for r in rows:
        start, end = int(r[start_field]), int(r[end_field])
        if not (0 <= start < end <= HORIZON_NS):
            raise ValueError(f'invalid or unfinished interval: {r["id"]}')
        member = (r['task'], r['backend'])
        changes[start].append((1, member))
        changes[end].append((-1, member))
    times = sorted({0, HORIZON_NS, *changes})
    active: list[tuple[str, str]] = []
    out = []
    for t, nxt in zip(times, times[1:]):
        for sign, member in sorted(changes[t]):
            if sign < 0:
                if member not in active:
                    raise ValueError('unbalanced completion')
                active.remove(member)
            else:
                if len(active) == 2:
                    raise ValueError('more than two concurrent requests')
                active.append(member)
        if len(active) == 2 and active[0][1] == active[1][1]:
            raise ValueError('same backend occupied twice')
        state = '+'.join(f'{task}:{backend}' for task, backend in sorted(active)) or 'idle'
        if out and out[-1]['state'] == state and out[-1]['end_ns'] == t:
            out[-1]['end_ns'] = nxt
        else:
            out.append(dict(start_ns=t, end_ns=nxt, state=state))
    if active or out[0]['start_ns'] != 0 or out[-1]['end_ns'] != HORIZON_NS:
        raise ValueError('incomplete common window')
    return out


def aggregate(parts: list[dict], policy: str, clock: str) -> list[dict]:
    groups = defaultdict(list)
    for p in parts:
        groups[p['state']].append((p['end_ns'] - p['start_ns']) / 1e9)
    result = []
    for state, durations in sorted(groups.items()):
        ordered = sorted(durations)
        result.append(dict(policy=policy, clock=clock, state=state,
                           intervals=len(ordered), total_s=round(sum(ordered), 6),
                           median_s=round(statistics.median(ordered), 6),
                           max_s=round(ordered[-1], 6),
                           at_least_2_power_periods=sum(d >= 2*CADENCES_S['power_nominal'] for d in ordered),
                           at_least_2_ap_periods=sum(d >= 2*CADENCES_S['ap_observed_approx'] for d in ordered)))
    if abs(sum(r['total_s'] for r in result) - 120) > 1e-5:
        raise ValueError('energy accounting window gap/overlap')
    return result


def audit(source: Path) -> tuple[list[dict], dict]:
    selected = read_rows(source)
    output = []
    for policy in POLICIES:
        rows = [r for r in selected if r['policy'] == policy]
        if len(rows) != 24 or len({r['id'] for r in rows}) != 24 or any(r['status'] != 'succeeded' for r in rows):
            raise ValueError(f'incomplete stored PC schedule: {policy}')
        for clock, start, end in (('lane', 'dispatch_ns', 'lane_available_ns'),
                                  ('inference', 'execution_start_ns', 'output_ready_ns')):
            output.extend(aggregate(segments(rows, start, end), policy, clock))
    metadata = dict(kind='PC_SIMULATION_OCCUPANCY_NOT_DEVICE_MEASUREMENT',
                    scenario=SCENARIO, seed=int(SEED), mode=MODE, requests_per_policy=24,
                    horizon_s=120, source=str(source.as_posix()),
                    source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                    sensor_cadence_s=CADENCES_S,
                    interpretation='two-period counts are only duration screens, not guaranteed samples; actual cadence/phase and state registration require Android observation',
                    supported_model_prediction=False, experiment_ready=False)
    return output, metadata


def write(output: Path, rows: list[dict], metadata: dict) -> None:
    output.mkdir(parents=True, exist_ok=True)
    with (output / 'short_transition_occupancy.csv').open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    (output / 'short_transition_audit.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    bars = []
    for index, row in enumerate(r for r in rows if r['clock'] == 'lane' and r['state'] != 'idle'):
        y = 48 + 32*index
        width = row['total_s'] * 22
        label = html.escape(f"{row['policy']} · {row['state']}")
        bars.append(f'<text x="12" y="{y+13}">{label}</text>'
                    f'<rect x="420" y="{y}" width="{width:.2f}" height="18" fill="#317da1"/>'
                    f'<text x="{430+width:.2f}" y="{y+14}">{row["total_s"]:.3f} s</text>')
    height = 75 + 32*len(bars)
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="{height}" viewBox="0 0 1000 {height}">'
           '<style>text{font:14px sans-serif;fill:#183246}</style>'
           '<text x="12" y="25">queue · seed 201 · strict PC 일정의 lane 상태 점유 (실기기 관측 아님)</text>'
           + ''.join(bars) + '</svg>')
    (output / 'short_transition_occupancy.svg').write_text(svg, encoding='utf-8')


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument('--source', type=Path, default=SOURCE)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    rows, metadata = audit(args.source)
    write(args.output, rows, metadata)
    print(json.dumps(dict(metadata=metadata, rows=rows), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
