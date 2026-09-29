"""Small, read-only figures from a completed recorded-B2 analysis bundle."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def rows(path):
    with Path(path).open(encoding='utf-8', newline='') as stream:
        return list(csv.DictReader(stream))


def draw(bundle, output):
    bundle, output = Path(bundle), Path(output)
    summary = json.loads((bundle / 'summary.json').read_text(encoding='utf-8'))
    if summary['status'] not in ('initial_ap_extrapolation_diagnostic_not_strict_support',
                                 'conditional_diagnostic_not_strict_support'):
        raise ValueError('full-window analysis required; no completion figure for partial data')
    if output.exists():
        raise FileExistsError(output)
    output.mkdir(parents=True)
    timing = rows(bundle / 'timing.csv')
    if len(timing) != 24 or summary['terminal_completed'] != 24:
        raise ValueError('request denominator')
    fig, ax = plt.subplots(figsize=(9, 6))
    for row in timing:
        ordinal = int(row['ordinal'])
        release = float(row['recorded_release_s'])
        dispatched = float(row['actual_dispatch_s'])
        ax.plot([release, dispatched], [ordinal, ordinal], color='#9aaab4', linewidth=1)
        ax.plot(dispatched, ordinal, marker='o', markersize=3,
                color='#df7a28' if row['backend'] == 'CPU' else '#397bb3')
    ax.set(xlabel='Seconds after actual common start', ylabel='Recorded request ordinal',
           title='Recorded release (line start) and actual dispatch (dot)')
    ax.grid(alpha=.2)
    fig.tight_layout(); fig.savefig(output / 'dispatch.svg'); plt.close(fig)

    states = rows(bundle / 'states.csv')
    fig, ax = plt.subplots(figsize=(9, 2.6))
    for row in states:
        state = row['state']
        if state == 'idle':
            continue
        start, end = float(row['start_s']), float(row['end_s'])
        for lane, y, color in (('CPU', 10, '#df7a28'), ('GPU', 25, '#397bb3')):
            if lane in state:
                ax.broken_barh([(start, end-start)], (y, 9), facecolors=color)
    ax.set(xlim=(0, 120), ylim=(5, 38), yticks=[14.5, 29.5], yticklabels=['CPU', 'GPU'],
           xlabel='Seconds after actual common start', title='Actual lane occupancy; idle omitted')
    ax.grid(axis='x', alpha=.2)
    fig.tight_layout(); fig.savefig(output / 'lanes.svg'); plt.close(fig)

    energy = rows(bundle / 'energy_path.csv')
    valid = [row for row in energy if row['observed_cumulative_j']]
    if not valid:
        raise ValueError('missing observed cumulative energy')
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.plot([float(r['elapsed_s']) for r in valid],
            [float(r['observed_cumulative_j']) for r in valid], label='Observed whole-device J')
    ax.plot([float(r['elapsed_s']) for r in energy],
            [float(r['predicted_cumulative_j']) for r in energy], label='Frozen-model extrapolation')
    ax.set(xlabel='Seconds', ylabel='Cumulative J', xlim=(0, 120),
           title='Common 120 s: observed vs conditional calculation')
    ax.legend(); ax.grid(alpha=.2)
    fig.tight_layout(); fig.savefig(output / 'energy.svg'); plt.close(fig)

    ap = rows(bundle / 'ap_path.csv')
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.plot([float(r['elapsed_s']) for r in ap],
            [float(r['observed_ap_c']) for r in ap], label='Observed HAL AP')
    ax.plot([float(r['elapsed_s']) for r in ap],
            [float(r['predicted_ap_c']) for r in ap], label='Frozen-model extrapolation')
    ax.set(xlabel='Seconds', ylabel='AP (C)', xlim=(0, 120),
           title='Common 120 s: AP path outside development start range')
    ax.legend(); ax.grid(alpha=.2)
    fig.tight_layout(); fig.savefig(output / 'ap.svg'); plt.close(fig)
    for svg in output.glob('*.svg'):
        svg.write_text(''.join(line.rstrip() + '\n' for line in svg.read_text(encoding='utf-8').splitlines()),
                       encoding='utf-8')


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument('--bundle', required=True)
    cli.add_argument('--output', required=True)
    args = cli.parse_args()
    draw(args.bundle, args.output)


if __name__ == '__main__':
    main()
