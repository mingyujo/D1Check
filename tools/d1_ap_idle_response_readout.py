"""Read-only, post-run comparison of the pre-frozen AP models.

The session estimator and its outputs are left unchanged.  This supplemental
readout compares the original frozen equation at exactly the candidate's AP
sample times and splits residuals by actual lane occupancy (including the
idle interval between the confirmation pulses).
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

from tools import d1_ap_idle_response as candidate
from tools import d1_arrival_plan as plan_io
from tools import d1_arrival_recorded_replay as replay
from tools import d1_arrival_recorded_replay_analysis as replay_analysis
from tools import d1_arrival_energy_analysis as descriptive
from tools import d1_energy_thermal as energy


def phase_at(t, segments, last_release):
    if t > last_release:
        return 'resident_idle_after_work'
    state = next((s['state'] for s in segments
                  if s['start_s'] <= t < s['end_s']), None)
    if state is None:
        raise ValueError('AP sample outside state timeline')
    return 'idle_between_pulses' if state == 'idle' else 'occupied'


def _scores(rows, column):
    errors = [r[column]-r['observed_ap_c'] for r in rows]
    return dict(samples=len(rows), mae_c=sum(map(abs, errors))/len(errors),
                max_absolute_error_c=max(map(abs, errors)),
                peak_signed_error_c=max(r[column] for r in rows)-
                    max(r['observed_ap_c'] for r in rows),
                signed_mean_c=sum(errors)/len(errors))


def readout(plan_file, run_root, frozen_file, output):
    from tools import d1_ap_idle_response_plan as prepared
    plan_file, run_root, frozen_file, output = map(Path,
        (plan_file, run_root, frozen_file, output))
    if output.exists():
        raise FileExistsError(output)
    registered = plan_io.read(plan_file)
    if registered['experiment_id'] != prepared.EXPERIMENT or len(registered['entries']) != 2:
        raise ValueError('different plan')
    if run_root != Path(registered['output_root']):
        raise ValueError('different run root')
    if plan_io.digest(frozen_file) != replay.FROZEN_SHA:
        raise ValueError('original AP freeze changed')
    receipt = plan_io.read(run_root/'FINAL_RECEIPT.json')
    if receipt['status'] != 'completed_descriptive_only' or receipt['sessions'] != 2:
        raise ValueError('not two completed descriptive sessions')
    freeze = plan_io.read(run_root/'ap_model_freeze.json')
    if (freeze['analysis_code_sha256'] != plan_io.digest(candidate.__file__) or
        freeze['structure_sha256'] != registered['analysis_contract']['sha256'] or
        freeze['original_frozen_sha256'] != replay.FROZEN_SHA or
        plan_io.digest(run_root/'ap_model_freeze.json') !=
            plan_io.read(run_root/'ap_model_freeze_receipt.json')['sha256']):
        raise ValueError('candidate structure/freeze changed')
    frozen = plan_io.read(frozen_file)
    beta = frozen['ap_cooling_rate_per_s']
    original_idle_equilibrium = (frozen['ap_reference_c']+
        frozen['ap_slope_at_30_c_per_s']['resident_idle']/beta)
    all_rows = []
    summaries = []
    timelines = {}
    for entry in registered['entries']:
        role = entry['phase']
        folder = run_root/f"{entry['index']:02d}_{entry['session_id']}"
        valid = plan_io.read(folder/'validated.json')
        current = plan_io.read(folder/'ap_analysis/summary.json')
        if (valid['status'] != 'eligible_descriptive_only' or
            valid['requests'] != 24 or valid['warmup'] != 8 or
            current['role'] != role or current['strict_support'] or
            plan_io.read(folder/'artifacts/cleanup.json')['status'] != 'completed' or
            plan_io.read(folder/'host_cleanup.json')['status'] != 'completed'):
            raise ValueError('session completion/cleanup evidence')
        boundary = plan_io.read(folder/'artifacts/common_boundary.json')
        origin = boundary['start_ns']
        if boundary['planned_end_ns']-origin != 120_000_000_000:
            raise ValueError('changed 120 s common window')
        requests = plan_io.read(folder/'artifacts/requests.json')
        if len(requests) != 24 or any(r['terminal_status'] != 'succeeded' for r in requests):
            raise ValueError('incomplete request denominator')
        segments = replay_analysis.observed_segments(requests, origin)
        cooling_end = current['cooling_end_s']
        prediction_segments = [*segments,
            dict(start_s=120., end_s=cooling_end, state='idle')]
        with (folder/'ap_analysis/ap_path.csv').open(encoding='utf-8', newline='') as stream:
            saved = list(csv.DictReader(stream))
        if not saved or int(current['ap_samples']) != len(saved):
            raise ValueError('missing AP comparison samples')
        times = [float(r['elapsed_s']) for r in saved]
        original = candidate.predict(prediction_segments, frozen,
            float(current['initial_ap_c']), original_idle_equilibrium, times)
        again = candidate.predict(prediction_segments, frozen,
            float(current['initial_ap_c']), float(current['preload_effective_reference_c']), times)
        rows = []
        for item, t in zip(saved, times):
            predicted = float(item['predicted_ap_c'])
            if abs(predicted-again[round(t, 9)]) > 1e-7:
                raise ValueError('saved candidate prediction differs from frozen procedure')
            observed = float(item['observed_ap_c'])
            rows.append(dict(role=role, elapsed_s=t,
                actual_phase=phase_at(t, prediction_segments, current['last_lane_release_s']),
                observed_ap_c=observed, frozen_ap_c=original[round(t, 9)],
                candidate_ap_c=predicted,
                observed_change_from_start_c=observed-current['initial_ap_c'],
                frozen_change_from_start_c=original[round(t, 9)]-current['initial_ap_c'],
                candidate_change_from_start_c=predicted-current['initial_ap_c'],
                frozen_signed_error_c=original[round(t, 9)]-observed,
                candidate_signed_error_c=predicted-observed))
        phases = defaultdict(list)
        for row in rows:
            phases[row['actual_phase']].append(row)
        idle = phases['resident_idle_after_work']
        if len(phases['occupied']) < 2 or len(idle) < 10:
            raise ValueError('insufficient phase-specific AP coverage')
        events = descriptive.read_lines(folder/'artifacts/progress.jsonl')
        power = [dict(e, mono_ns=(e['snapshot_start_ns']+e['sensor_read_end_ns'])//2)
                 for e in events if e['kind'] == 'power_sample']
        observed_energy = energy.integrate(power, origin, boundary['planned_end_ns'], 1000)
        if observed_energy['full_energy_j'] is None:
            raise ValueError('incomplete descriptive energy window')
        phase_scores = {name:dict(frozen=_scores(group, 'frozen_ap_c'),
                                  candidate=_scores(group, 'candidate_ap_c'))
                        for name, group in phases.items()}
        summaries.append(dict(role=role, data_role=current['data_role'],
            initial_ap_c=current['initial_ap_c'],
            preload_samples=valid['preload_ap']['samples'],
            preload_duration_s=valid['preload_ap']['duration_s'],
            effective_idle_reference_c=current['preload_effective_reference_c'],
            original_idle_equilibrium_c=original_idle_equilibrium,
            ap_samples=len(rows), observed_energy_120s_j=observed_energy['full_energy_j'],
            observed_postwork_direction_c=idle[-1]['observed_ap_c']-idle[0]['observed_ap_c'],
            frozen_postwork_direction_c=idle[-1]['frozen_ap_c']-idle[0]['frozen_ap_c'],
            candidate_postwork_direction_c=idle[-1]['candidate_ap_c']-idle[0]['candidate_ap_c'],
            frozen=_scores(rows, 'frozen_ap_c'),
            candidate=_scores(rows, 'candidate_ap_c'), phase_scores=phase_scores,
            observed_state_seconds={key:sum(x['end_s']-x['start_s'] for x in segments
                if x['state'] == key) for key in sorted({x['state'] for x in segments})},
            independent_session_count=1,
            strict_support=False, accuracy_pass=None, policy_selection_pass=None))
        timelines[role] = segments
        all_rows.extend(rows)
    output.mkdir(parents=True)
    shared = dict(plan_sha256=plan_io.digest(plan_file),
        original_frozen_sha256=plan_io.digest(frozen_file),
        candidate_freeze_sha256=plan_io.digest(run_root/'ap_model_freeze.json'),
        protocol='AP pre-load effective reference diagnostic; original frozen calculation is extrapolation',
        posthoc_phase_split='actual lane occupancy; does not change the frozen estimator',
        energy_meaning='descriptive current/voltage 120 s integration, not new power coefficient validation',
        summaries=summaries)
    (output/'summary.json').write_text(json.dumps(shared, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    with (output/'ap_paths.csv').open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(all_rows[0]));writer.writeheader();writer.writerows(all_rows)
    _plot(all_rows, timelines, output)
    return shared


def _plot(rows, timelines, output):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(2, 2, figsize=(13, 8), sharex='row')
    for index, role in enumerate(('development', 'confirmation')):
        data = [r for r in rows if r['role'] == role]
        x = [r['elapsed_s'] for r in data]
        upper, lower = axes[index]
        for segment in timelines[role]:
            if segment['state'] != 'idle':
                upper.axvspan(segment['start_s'], segment['end_s'], color='#eea147', alpha=.12)
                lower.axvspan(segment['start_s'], segment['end_s'], color='#eea147', alpha=.12)
        upper.plot(x, [r['observed_ap_c'] for r in data], 'o-', color='#202020', ms=3, label='Observed HAL AP')
        upper.plot(x, [r['frozen_ap_c'] for r in data], '--', color='#be423a', label='Original frozen (extrapolation)')
        upper.plot(x, [r['candidate_ap_c'] for r in data], '-', color='#296ba8', label='Pre-load candidate')
        lower.axhline(0, color='#888888', lw=.8)
        lower.plot(x, [r['frozen_signed_error_c'] for r in data], '--', color='#be423a', label='Frozen - observed')
        lower.plot(x, [r['candidate_signed_error_c'] for r in data], '-', color='#296ba8', label='Candidate - observed')
        upper.set_title(role+' | orange = occupied lane')
        upper.set_ylabel('AP (°C)')
        lower.set_ylabel('Signed error (°C)')
        lower.set_xlabel('Seconds from common-window start')
        upper.legend(fontsize=8, loc='best')
        lower.legend(fontsize=8, loc='best')
    fig.tight_layout()
    svg = output/'ap_comparison.svg'
    fig.savefig(svg)
    # Matplotlib writes spaces after SVG path line breaks.  Keep the committed
    # visualization whitespace-clean without changing any plotted values.
    svg.write_text('\n'.join(line.rstrip() for line in svg.read_text(encoding='utf-8').splitlines())+'\n',
                   encoding='utf-8')
    fig.savefig(output/'ap_comparison.png', dpi=145)
    plt.close(fig)


def main():
    cli = argparse.ArgumentParser()
    for name in ('plan', 'run-root', 'frozen', 'output'):
        cli.add_argument('--'+name, required=True)
    args = cli.parse_args()
    result = readout(args.plan, args.run_root, args.frozen, args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
