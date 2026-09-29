"""Static figures from the small post-hoc B2 residual bundle; no device I/O."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from tools.d1_arrival_recorded_b2_residual import read_csv


def draw(bundle, output):
    bundle, output = Path(bundle), Path(output)
    if output.exists():
        raise FileExistsError(output)
    summary = json.loads((bundle/'summary.json').read_text(encoding='utf-8'))
    if summary['version'] != 'recorded-b2-residual-pc-v1' or summary['accuracy_pass'] is not None:
        raise ValueError('wrong post-hoc bundle')
    output.mkdir(parents=True)
    ap = read_csv(bundle/'ap_diagnostics.csv')
    e = read_csv(bundle/'cumulative_energy.csv')
    bins = read_csv(bundle/'sensor_intervals.csv')
    compare = read_csv(bundle/'candidate_comparison.csv')
    cut = summary['last_active_s']

    fig, axes = plt.subplots(3, 1, figsize=(9, 10), sharex=True)
    t = [float(r['elapsed_s']) for r in ap]
    for field, label in [('observed_ap_c','Observed HAL AP'),('frozen_ap_c','Frozen extrapolation'),
                         ('candidate_ap_c','Start-reference candidate (post-hoc)')]:
        axes[0].plot(t,[float(r[field]) for r in ap],label=label)
    axes[0].axhline(summary['initial_ap_c'],color='gray',ls=':',lw=1,label='Observed start AP')
    axes[0].set(ylabel='AP (C)',title='Absolute AP: actual lane schedule, initial AP 29.9 C')
    axes[0].legend(fontsize=8);axes[0].grid(alpha=.2)
    for field,label in [('observed_change_from_start_c','Observed delta'),
                        ('frozen_change_from_start_c','Frozen delta')]:
        axes[1].plot(t,[float(r[field]) for r in ap],label=label)
    axes[1].set(ylabel='Change from initial AP (C)',title='The frozen and observed paths start at the same AP')
    axes[1].legend(fontsize=8);axes[1].grid(alpha=.2)
    for field,label in [('frozen_signed_error_c','Frozen minus observed'),
                        ('first_sample_aligned_error_c','First-sample aligned (diagnostic only)'),
                        ('candidate_signed_error_c','Candidate minus observed (post-hoc)')]:
        axes[2].plot(t,[float(r[field]) for r in ap],label=label)
    axes[2].axhline(0,color='gray',lw=.8)
    axes[2].set(xlabel='Seconds after common start',ylabel='AP residual (C)',
                title='Offset removal does not explain the frozen shape error')
    axes[2].legend(fontsize=8);axes[2].grid(alpha=.2)
    for ax in axes:
        ax.axvspan(cut,120,color='#e8f1f6',alpha=.65)
        ax.axvline(cut,color='#557183',lw=.8)
    axes[-1].set_xlim(0,120)
    fig.tight_layout();fig.savefig(output/'ap_decomposition.svg',metadata={'Date':None});plt.close(fig)

    fig, axes = plt.subplots(3, 1, figsize=(9, 9), sharex=True)
    te = [float(r['elapsed_s']) for r in e]
    axes[0].plot(te,[float(r['observed_cumulative_j']) for r in e],label='Observed 120 s')
    axes[0].plot(te,[float(r['predicted_cumulative_j']) for r in e],label='Frozen extrapolation')
    axes[0].set(ylabel='Cumulative J',title='Whole-device energy; exact common-window endpoint included')
    axes[0].legend(fontsize=8)
    axes[1].plot(te,[float(r['signed_error_j']) for r in e],label='Frozen minus observed')
    axes[1].axhline(0,color='gray',lw=.8);axes[1].set(ylabel='Cumulative residual (J)')
    for resolution,color in [('mixed','#d97706'),('pure','#2563a6')]:
        selected=[r for r in bins if r['resolution']==resolution]
        axes[2].scatter([(float(r['start_s'])+float(r['end_s']))/2 for r in selected],
                        [float(r['signed_error_j']) for r in selected],s=12,
                        label=f'{resolution} sensor interval',color=color)
    axes[2].axhline(0,color='gray',lw=.8)
    axes[2].set(xlabel='Seconds after common start',ylabel='1-sensor-interval residual (J)',
                title='Mixed intervals cannot identify separate short-state power')
    axes[2].legend(fontsize=8)
    for ax in axes:
        ax.axvspan(cut,120,color='#e8f1f6',alpha=.65)
        ax.axvline(cut,color='#557183',lw=.8);ax.grid(alpha=.2)
    axes[-1].set_xlim(0,120)
    fig.tight_layout();fig.savefig(output/'energy_cancellation.svg',metadata={'Date':None});plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 4.8))
    names=[r['name'] for r in compare]
    ys=list(range(len(compare)))
    ax.barh([y-.18 for y in ys],[float(r['frozen_mae_c']) for r in compare],height=.34,
            label='Frozen AP MAE')
    ax.barh([y+.18 for y in ys],[float(r['candidate_mae_c']) for r in compare],height=.34,
            label='One post-hoc candidate AP MAE')
    ax.set(yticks=ys,yticklabels=names,xlabel='AP MAE (C)',
           title='Candidate helps seen B2, worsens other seen sessions')
    ax.invert_yaxis();ax.legend(fontsize=8);ax.grid(axis='x',alpha=.2)
    fig.tight_layout();fig.savefig(output/'candidate_comparison.svg',metadata={'Date':None});plt.close(fig)
    for svg in output.glob('*.svg'):
        svg.write_text('\n'.join(line.rstrip() for line in svg.read_text(encoding='utf-8').splitlines())+'\n',
                       encoding='utf-8')


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument('--bundle',required=True)
    cli.add_argument('--output',required=True)
    args=cli.parse_args()
    draw(args.bundle,args.output)


if __name__=='__main__':
    main()
