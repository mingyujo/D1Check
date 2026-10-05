"""Post-hoc, read-only B2 residual analysis and one separate AP candidate.

The candidate is a diagnostic sensitivity calculation. It never changes the
frozen model, strict support mask, or a collection plan.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path

from tools import d1_arrival_energy_analysis as descriptive
from tools import d1_arrival_plan as plan
from tools import d1_arrival_recorded_replay as replay
from tools import d1_arrival_recorded_replay_analysis as prior
from tools import d1_energy_thermal as energy

CANDIDATE_ID = 'energy-ap-start-referenced-idle-diagnostic-v1'


def read_csv(path):
    with Path(path).open(encoding='utf-8', newline='') as stream:
        return list(csv.DictReader(stream))


def write_csv(path, records):
    if not records:
        raise ValueError('empty result')
    with Path(path).open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)


def candidate_path(segments, frozen, initial_ap, query_s):
    """Phenomenological start-reference alternative, with no fitted parameter.

    This treats initial AP as an *effective* idle reference, not ambient
    temperature. It may fail when residual heat remains at the start.
    """
    beta = frozen['ap_cooling_rate_per_s']
    slope = frozen['ap_slope_at_30_c_per_s']
    idle_slope = slope['resident_idle']
    if not math.isfinite(initial_ap) or beta <= 0:
        raise ValueError('candidate initial state')
    position, temperature = 0., initial_ap
    result = {}
    for target in sorted(set(query_s)):
        if target < position-1e-9 or target > segments[-1]['end_s']+1e-9:
            raise ValueError('candidate query outside schedule')
        while position < target-1e-10:
            segment = next((row for row in segments
                            if row['start_s'] <= position+1e-10 < row['end_s']-1e-10), None)
            if segment is None:
                raise ValueError('candidate schedule gap')
            end = min(target, segment['end_s'])
            key = prior.state_key(segment['state'])
            equilibrium = initial_ap+(slope[key]-idle_slope)/beta
            temperature = energy.transition(temperature, equilibrium, 1/beta, end-position)
            position = end
        result[round(target, 9)] = temperature
    return result


def overlap(segments, start_s, end_s):
    parts = {}
    for row in segments:
        seconds = max(0., min(end_s, row['end_s'])-max(start_s, row['start_s']))
        if seconds:
            parts[row['state']] = parts.get(row['state'], 0.)+seconds
    if abs(sum(parts.values())-(end_s-start_s)) > 1e-7:
        raise ValueError('state partition gap or overlap')
    return parts


def sensor_intervals(samples, origin_ns, end_ns, segments, frozen):
    """One sensor-to-sensor interval is the smallest interpretable J bin."""
    power = frozen['whole_device_power_w']
    last_active = max(row['end_s'] for row in segments if row['state'] != 'idle')
    records = []
    samples, duplicates = energy.canonical_samples(samples)
    for left, right in zip(samples, samples[1:]):
        a = max(origin_ns, left['mono_ns'])
        b = min(end_ns, right['mono_ns'])
        if b <= a:
            continue
        start_s, end_s = (a-origin_ns)/1e9, (b-origin_ns)/1e9
        pieces = overlap(segments, start_s, end_s)
        predicted = sum(power[prior.state_key(state)]*seconds for state, seconds in pieces.items())
        measured = energy.integrate([left, right], a, b, 1000)
        observed = measured['full_energy_j']
        if end_s <= last_active+1e-9:
            phase = 'through_last_lane_release'
        elif start_s >= last_active-1e-9:
            phase = 'post_work_idle'
        else:
            phase = 'work_idle_boundary_mixed'
        records.append(dict(start_s=start_s, end_s=end_s, duration_s=end_s-start_s,
                            phase=phase, state_mix='|'.join(sorted(pieces)),
                            resolution='pure' if len(pieces) == 1 else 'mixed',
                            predicted_j=predicted, observed_j=observed,
                            signed_error_j=predicted-observed if observed is not None else None,
                            covered_s=measured['covered_s']))
    return records, duplicates, last_active


def block_candidate(stats, frozen):
    """Compare already viewed regimen sessions; no independent selection claim."""
    beta = frozen['ap_cooling_rate_per_s']
    slope = frozen['ap_slope_at_30_c_per_s']
    initial = stats['start_ap_c']
    idle = slope['resident_idle']
    frozen_temp = candidate_temp = initial
    frozen_errors, candidate_errors = [], []
    for block in stats['blocks']:
        state = block['state']
        frozen_eq = frozen['ap_reference_c']+slope[state]/beta
        candidate_eq = initial+(slope[state]-idle)/beta
        for sample in block['ap_path']:
            elapsed = (sample['mono_ns']-block['start_ns'])/1e9
            actual = sample['ap_c']
            frozen_at = energy.transition(frozen_temp, frozen_eq, 1/beta, elapsed)
            candidate_at = energy.transition(candidate_temp, candidate_eq, 1/beta, elapsed)
            frozen_errors.append(abs(frozen_at-actual))
            candidate_errors.append(abs(candidate_at-actual))
        duration = (block['end_ns']-block['start_ns'])/1e9
        frozen_temp = energy.transition(frozen_temp, frozen_eq, 1/beta, duration)
        candidate_temp = energy.transition(candidate_temp, candidate_eq, 1/beta, duration)
    if not frozen_errors:
        raise ValueError('missing block AP')
    return dict(initial_ap_c=initial, ap_samples=len(frozen_errors),
                frozen_mae_c=sum(frozen_errors)/len(frozen_errors),
                candidate_mae_c=sum(candidate_errors)/len(candidate_errors),
                frozen_max_error_c=max(frozen_errors), candidate_max_error_c=max(candidate_errors))


def effective_idle_reference(first_time_s, first_ap_c, last_time_s, last_ap_c, beta):
    """Endpoint diagnostic with beta fixed; not a separately identified ambient."""
    dt = last_time_s-first_time_s
    if dt < 20 or beta <= 0:
        return None
    decay = math.exp(-beta*dt)
    return (last_ap_c-first_ap_c*decay)/(1-decay)


def analyze(bundle, session, frozen_file, development_run, transfer_run, output):
    bundle, session, output = Path(bundle), Path(session), Path(output)
    if output.exists():
        raise FileExistsError(output)
    frozen_file = Path(frozen_file)
    if plan.digest(frozen_file) != replay.FROZEN_SHA:
        raise ValueError('frozen byte identity changed')
    frozen = plan.read(frozen_file)
    baseline = plan.read(bundle/'summary.json')
    if (baseline['status'] != 'initial_ap_extrapolation_diagnostic_not_strict_support'
            or baseline['terminal_completed'] != 24 or baseline['observation_eligibility'] != 'full_common_window'
            or baseline['frozen_sha256'] != replay.FROZEN_SHA):
        raise ValueError('wrong B2 completed diagnostic')
    receipt = plan.read(session.parent/'FINAL_RECEIPT.json')
    if receipt['status'] != 'completed_descriptive_only' or receipt['requests'] != 24:
        raise ValueError('wrong original receipt')
    artifact = session/'artifacts'
    boundary = plan.read(artifact/'common_boundary.json')
    accepted = plan.read(artifact/'start_ap.accepted.json')
    origin, end = boundary['start_ns'], boundary['planned_end_ns']
    if (end-origin != 120_000_000_000 or accepted['common_start_ns'] != origin
            or accepted['ap_c'] != baseline['initial_ap_c']):
        raise ValueError('AP/common clock boundary')
    raw_events = descriptive.read_lines(artifact/'progress.jsonl')
    samples = [dict(row, mono_ns=(row['snapshot_start_ns']+row['sensor_read_end_ns'])//2)
               for row in raw_events if row['kind'] == 'power_sample']
    if len(samples) != baseline['power_sample_count']:
        raise ValueError('power sample denominator')
    full = energy.integrate(samples, origin, end, 1000)
    if full['full_energy_j'] is None or abs(full['full_energy_j']-baseline['observed_energy_120s_j']) > 1e-8:
        raise ValueError('original energy integral changed')
    state_csv = read_csv(bundle/'states.csv')
    segments = [dict(start_s=float(row['start_s']), end_s=float(row['end_s']), state=row['state'])
                for row in state_csv]
    if (segments[0]['start_s'] != 0 or abs(segments[-1]['end_s']-120) > 1e-9
            or any(abs(a['end_s']-b['start_s']) > 1e-9 for a, b in zip(segments, segments[1:]))
            or any(prior.state_key(row['state']) != saved['frozen_state']
                   for row, saved in zip(segments, state_csv))):
        raise ValueError('state mapping or clock gap')
    power = frozen['whole_device_power_w']
    predicted_full = sum((row['end_s']-row['start_s'])*power[prior.state_key(row['state'])]
                         for row in segments)
    if abs(predicted_full-baseline['predicted_energy_120s_j']) > 1e-8:
        raise ValueError('frozen power accounting changed')
    bins, duplicates, last_active = sensor_intervals(samples, origin, end, segments, frozen)
    if any(row['observed_j'] is None for row in bins):
        raise ValueError('new missing sensor interval; no zero fill')
    if (abs(sum(row['observed_j'] for row in bins)-full['full_energy_j']) > 1e-8
            or abs(sum(row['predicted_j'] for row in bins)-predicted_full) > 1e-8):
        raise ValueError('sensor interval does not conserve whole-window J')
    active_end_ns = origin+round(last_active*1e9)
    phases = {}
    for name, start, finish in [('through_last_lane_release', origin, active_end_ns),
                                ('post_work_idle', active_end_ns, end)]:
        observed = energy.integrate(samples, start, finish, 1000)
        predicted = sum(power[prior.state_key(state)]*seconds for state, seconds in
                        overlap(segments, (start-origin)/1e9, (finish-origin)/1e9).items())
        phases[name] = dict(duration_s=(finish-start)/1e9, observed_j=observed['full_energy_j'],
                            predicted_j=predicted, signed_error_j=predicted-observed['full_energy_j'])
    ap_csv = read_csv(bundle/'ap_path.csv')
    thermal = descriptive.read_lines(session/'thermal.jsonl')
    raw_ap = [(row['mono_ns'], float(row['AP'])) for row in thermal
              if origin <= row['mono_ns'] <= end and row['AP'] != '']
    if len(raw_ap) != len(ap_csv) or len(ap_csv) != baseline['ap_sample_count']:
        raise ValueError('AP sample denominator')
    common_thermal = [row for row in thermal if origin <= row['mono_ns'] <= end and row['AP'] != '']
    if any(row['thermal_status'] != '0' for row in common_thermal):
        raise ValueError('thermal status changed in AP samples')
    common_power = [row for row in samples if origin <= row['mono_ns'] <= end]
    ap_points = []
    first_error = float(ap_csv[0]['signed_error_c'])
    previous = 0.
    for raw, row in zip(raw_ap, ap_csv):
        elapsed = (raw[0]-origin)/1e9
        observed, predicted = float(row['observed_ap_c']), float(row['predicted_ap_c'])
        if abs(elapsed-float(row['elapsed_s'])) > 1e-8 or observed != raw[1]:
            raise ValueError('AP sensor clock or value changed')
        present = overlap(segments, previous, elapsed)
        ap_points.append(dict(elapsed_s=elapsed, observed_ap_c=observed,
                              frozen_ap_c=predicted,
                              observed_change_from_start_c=observed-accepted['ap_c'],
                              frozen_change_from_start_c=predicted-accepted['ap_c'],
                              frozen_signed_error_c=predicted-observed,
                              first_sample_aligned_error_c=predicted-observed-first_error,
                              state_mix_since_previous='|'.join(sorted(present))))
        previous = elapsed
    frozen_at_ap = prior.forecast(segments, frozen, accepted['ap_c'],
                                  [row['elapsed_s'] for row in ap_points],
                                  diagnostic_extrapolation=True)
    lookup = {round(row['elapsed_s'], 9): row['predicted_ap_c'] for row in frozen_at_ap}
    if any(abs(lookup[round(row['elapsed_s'], 9)]-row['frozen_ap_c']) > 1e-8 for row in ap_points):
        raise ValueError('original frozen AP recurrence changed')
    candidate = candidate_path(segments, frozen, accepted['ap_c'],
                               [row['elapsed_s'] for row in ap_points])
    for row in ap_points:
        row['candidate_ap_c'] = candidate[round(row['elapsed_s'], 9)]
        row['candidate_signed_error_c'] = row['candidate_ap_c']-row['observed_ap_c']
    maef = sum(abs(row['frozen_signed_error_c']) for row in ap_points)/len(ap_points)
    maec = sum(abs(row['candidate_signed_error_c']) for row in ap_points)/len(ap_points)
    if abs(maef-baseline['ap_mae_c']) > 1e-8:
        raise ValueError('baseline AP MAE changed')
    idle_ap = [row for row in ap_points if row['elapsed_s'] >= last_active]
    if len(idle_ap) < 2:
        raise ValueError('no post-work AP samples')
    comparisons = [dict(data_role='B2_seen_transfer_diagnostic', name='B2_recorded_replay',
                        initial_ap_c=accepted['ap_c'], ap_samples=len(ap_points),
                        frozen_mae_c=maef, candidate_mae_c=maec,
                        frozen_max_error_c=max(abs(row['frozen_signed_error_c']) for row in ap_points),
                        candidate_max_error_c=max(abs(row['candidate_signed_error_c']) for row in ap_points))]
    beta = frozen['ap_cooling_rate_per_s']
    idle_reference = [dict(data_role='B2_seen_transfer_diagnostic',name='B2_recorded_replay',
        block='post_work_idle',first_sample_s=idle_ap[0]['elapsed_s'],
        last_sample_s=idle_ap[-1]['elapsed_s'],first_ap_c=idle_ap[0]['observed_ap_c'],
        last_ap_c=idle_ap[-1]['observed_ap_c'],
        effective_reference_c=effective_idle_reference(idle_ap[0]['elapsed_s'],
            idle_ap[0]['observed_ap_c'],idle_ap[-1]['elapsed_s'],idle_ap[-1]['observed_ap_c'],beta))]
    dev = sorted(Path(development_run).glob('0?_*/validated.json'))
    if len(dev) != 4:
        raise ValueError('expected development 3 + confirmation 1')
    for path in dev:
        stats = plan.read(path)
        if stats['phase'] not in ('development', 'confirmation'):
            raise ValueError('unexpected historical phase')
        metrics = block_candidate(stats, frozen)
        if stats['phase'] == 'confirmation':
            expected = stats['confirmation_errors']['ap_path_mae_c']
            if abs(metrics['frozen_mae_c']-expected) > 1e-8:
                raise ValueError('DC_DG frozen AP mismatch')
        comparisons.append(dict(data_role='frozen_development' if stats['phase'] == 'development'
                                else 'already_viewed_confirmation',
                                name=stats['condition']+'_'+stats['phase'], **metrics))
        for block in stats['blocks']:
            if block['state'] != 'resident_idle' or len(block['ap_path']) < 2:
                continue
            first, last = block['ap_path'][0], block['ap_path'][-1]
            a, b = ((first['mono_ns']-block['start_ns'])/1e9,
                    (last['mono_ns']-block['start_ns'])/1e9)
            reference = effective_idle_reference(a,first['ap_c'],b,last['ap_c'],beta)
            if reference is not None:
                idle_reference.append(dict(data_role=stats['phase'],
                    name=stats['condition']+'_'+stats['phase'],block=block['name'],
                    first_sample_s=a,last_sample_s=b,first_ap_c=first['ap_c'],
                    last_ap_c=last['ap_c'],effective_reference_c=reference))
    transfer = list(Path(transfer_run).glob('00_*/validated.json'))
    if len(transfer) != 1:
        raise ValueError('expected one transfer diagnostic')
    stats = plan.read(transfer[0])
    if stats['condition'] != 'CG_DC':
        raise ValueError('unexpected transfer pair')
    comparisons.append(dict(data_role='already_viewed_protocol_transfer', name='CG_DC_diag04',
                            **block_candidate(stats, frozen)))
    for block in stats['blocks']:
        if block['state'] != 'resident_idle' or len(block['ap_path']) < 2:
            continue
        first, last = block['ap_path'][0], block['ap_path'][-1]
        a, b = ((first['mono_ns']-block['start_ns'])/1e9,
                (last['mono_ns']-block['start_ns'])/1e9)
        reference = effective_idle_reference(a,first['ap_c'],b,last['ap_c'],beta)
        if reference is not None:
            idle_reference.append(dict(data_role='already_viewed_protocol_transfer',name='CG_DC_diag04',
                block=block['name'],first_sample_s=a,last_sample_s=b,first_ap_c=first['ap_c'],
                last_ap_c=last['ap_c'],effective_reference_c=reference))
    cumulative = [dict(elapsed_s=0., observed_cumulative_j=0.,
                       predicted_cumulative_j=0., signed_error_j=0.)]
    for row in read_csv(bundle/'energy_path.csv'):
        if row['observed_cumulative_j'] != '':
            cumulative.append(dict(elapsed_s=float(row['elapsed_s']),
                                   observed_cumulative_j=float(row['observed_cumulative_j']),
                                   predicted_cumulative_j=float(row['predicted_cumulative_j']),
                                   signed_error_j=float(row['signed_error_j'])))
    cumulative.append(dict(elapsed_s=120., observed_cumulative_j=full['full_energy_j'],
                           predicted_cumulative_j=predicted_full,
                           signed_error_j=predicted_full-full['full_energy_j']))
    summary = dict(version='recorded-b2-residual-pc-v1', frozen_sha256=replay.FROZEN_SHA,
                   source_receipt_sha256=plan.digest(session.parent/'FINAL_RECEIPT.json'),
                   data_role='posthoc_reanalysis_of_one_seen_extrapolation_session',
                   base_integrator_or_clock_defect_found=False,
                   clock_and_sensor=dict(common_window_s=120.,
                       power_timestamp='Android monotonic midpoint of app snapshot bracket',
                       ap_timestamp='Android uptime midpoint of host HAL bracket; not host monotonic',
                       ap_sensor='HAL AP name, type 0, Celsius; not cached AP or BAT',
                       power_snapshot_max_bracket_s=max((row['sensor_read_end_ns']-
                           row['snapshot_start_ns'])/1e9 for row in common_power),
                       ap_max_uncertainty_s=max(row['sampling_uncertainty_ns']/1e9
                                                for row in common_thermal),
                       energy_covered_s=full['covered_s'],energy_missing_s=full['missing_s'],
                       current_unit='raw=mA conditional; absolute J accuracy uncertified'),
                   initial_ap_c=accepted['ap_c'], first_ap_sample_s=ap_points[0]['elapsed_s'],
                   frozen_idle_equilibrium_c=frozen['ap_reference_c']+
                       frozen['ap_slope_at_30_c_per_s']['resident_idle']/frozen['ap_cooling_rate_per_s'],
                   last_active_s=last_active, energy_120s=dict(observed_j=full['full_energy_j'],
                       frozen_j=predicted_full,signed_error_j=predicted_full-full['full_energy_j']),
                   phases=phases, sensor_intervals=dict(count=len(bins), duplicates=duplicates,
                       mixed_count=sum(row['resolution']=='mixed' for row in bins),
                       mixed_seconds=sum(row['duration_s'] for row in bins if row['resolution']=='mixed'),
                       positive_error_j=sum(max(0.,row['signed_error_j']) for row in bins),
                       negative_error_j=sum(min(0.,row['signed_error_j']) for row in bins)),
                   ap=dict(frozen_mae_c=maef,candidate_mae_c=maec,
                       first_sample_signed_error_c=first_error,
                       first_sample_aligned_mae_c=sum(abs(row['first_sample_aligned_error_c'])
                                                      for row in ap_points)/len(ap_points),
                       post_idle_first_observed_c=idle_ap[0]['observed_ap_c'],
                       post_idle_last_observed_c=idle_ap[-1]['observed_ap_c'],
                       post_idle_first_frozen_c=idle_ap[0]['frozen_ap_c'],
                       post_idle_last_frozen_c=idle_ap[-1]['frozen_ap_c']),
                   candidate=dict(id=CANDIDATE_ID, formula='equilibrium(state) = initial_AP + '
                       '(frozen_slope(state)-frozen_slope(resident_idle))/frozen_beta',
                       new_fitted_parameters=0, initial_ap_is_ambient=False,
                       status='posthoc_exploratory_not_registered_or_independently_confirmed'),
                   accuracy_pass=None,policy_selection_pass=None,experiment_ready=False)
    output.mkdir(parents=True)
    (output/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    for name, rows in [('sensor_intervals.csv',bins),('ap_diagnostics.csv',ap_points),
                       ('candidate_comparison.csv',comparisons),('cumulative_energy.csv',cumulative),
                       ('idle_effective_reference.csv',idle_reference)]:
        write_csv(output/name,rows)
    return summary


def main():
    parser = argparse.ArgumentParser()
    for name in ('bundle','session','frozen','development-run','transfer-run','output'):
        parser.add_argument('--'+name,required=True)
    args = parser.parse_args()
    result = analyze(args.bundle,args.session,args.frozen,args.development_run,args.transfer_run,args.output)
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
