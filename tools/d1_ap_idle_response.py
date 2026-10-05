"""Prespecified AP idle-reference diagnostic; never replaces the frozen profile.

The pre-load AP trace is an observed initial condition.  Only the frozen beta and
state *differences* are carried over.  A per-session effective idle reference is
estimated before the first request, never from the post-load comparison window.
It is not an ambient-temperature estimate or a new physical thermal coefficient.
"""
from __future__ import annotations

import math
import csv
import json
from pathlib import Path

from tools.d1_energy_thermal import transition
from tools.d1_arrival_recorded_replay_analysis import state_key

VERSION = 'ap-preload-idle-reference-diagnostic-v1'


def preload_reference(samples, beta, *, minimum_seconds=55., maximum_gap_seconds=10.):
    """Return an effective idle reference and diagnostics from ordered (s, C).

    Beta is fixed by the old development freeze.  A long pre-load interval makes
    the reference numerically observable, but cannot identify ambient or hidden
    heat.  The first measured AP is the initial state, not an equilibrium.
    """
    if not math.isfinite(beta) or beta <= 0 or len(samples) < 15:
        raise ValueError('insufficient pre-load AP samples or invalid frozen beta')
    if any(not math.isfinite(t) or not math.isfinite(y) for t, y in samples):
        raise ValueError('missing/nonfinite pre-load AP')
    if any(not 0 < b[0]-a[0] <= maximum_gap_seconds
           for a, b in zip(samples, samples[1:])):
        raise ValueError('pre-load AP timestamp gap/order')
    duration = samples[-1][0]-samples[0][0]
    if duration < minimum_seconds:
        raise ValueError('pre-load idle too short for this diagnostic')
    t0, y0 = samples[0]
    basis = [1-math.exp(-beta*(t-t0)) for t, _ in samples]
    denominator = sum(x*x for x in basis)
    if denominator < 1:
        raise ValueError('effective idle reference numerically unidentified')
    reference = sum(x*(y-y0*(1-x)) for x, (_, y) in zip(basis, samples))/denominator
    residual = [y-(y0*(1-x)+reference*x) for x, (_, y) in zip(basis, samples)]
    if not math.isfinite(reference):
        raise ValueError('nonfinite effective reference')
    return dict(version=VERSION, effective_idle_reference_c=reference,
                first_ap_c=y0, last_preload_ap_c=samples[-1][1],
                first_s=t0, last_s=samples[-1][0], duration_s=duration,
                samples=len(samples), prefit_mae_c=sum(map(abs, residual))/len(residual),
                prefit_max_absolute_error_c=max(map(abs, residual)),
                meaning='pre-load observed effective reference; not ambient or independent beta')


def predict(segments, frozen, initial_ap_c, effective_idle_reference_c, query_s):
    """Continuous conditional AP path; no observed post-load AP enters prediction."""
    beta = frozen['ap_cooling_rate_per_s']
    slopes = frozen['ap_slope_at_30_c_per_s']
    idle = slopes['resident_idle']
    if not all(math.isfinite(v) for v in (initial_ap_c, effective_idle_reference_c, beta)) or beta <= 0:
        raise ValueError('invalid candidate inputs')
    result = {}
    current = initial_ap_c
    cursor = 0.
    queries = sorted(query_s)
    if any(not math.isfinite(q) or q < 0 for q in queries):
        raise ValueError('invalid prediction time')
    pos = 0
    for segment in segments:
        start, end = float(segment['start_s']), float(segment['end_s'])
        if abs(start-cursor) > 1e-6 or end < start:
            raise ValueError('noncontiguous state path')
        state = state_key(segment['state'])
        if state not in slopes:
            raise ValueError('unsupported AP state: '+state)
        equilibrium = effective_idle_reference_c+(slopes[state]-idle)/beta
        while pos < len(queries) and queries[pos] <= end+1e-9:
            q = queries[pos]
            if q < start-1e-9:
                raise ValueError('query before state')
            result[round(q, 9)] = transition(current, equilibrium, 1/beta, max(0., q-start))
            pos += 1
        current = transition(current, equilibrium, 1/beta, end-start)
        cursor = end
    if pos != len(queries):
        raise ValueError('query outside state path')
    return result


def analyze_session(session_folder, frozen_file, output):
    """After a completed run, score only AP *after* the first dispatch.

    The per-session reference stored in validated.json was calculated by the
    host from pre-load samples.  This readout never refits it from comparison
    samples and never converts a diagnostic into strict support.
    """
    from tools import d1_arrival_plan as p
    from tools import d1_arrival_recorded_replay_analysis as replay_analysis
    from tools import d1_arrival_recorded_replay as replay
    from tools import d1_arrival_energy_analysis as descriptive
    folder, output = Path(session_folder), Path(output)
    if output.exists():
        raise FileExistsError(output)
    if p.digest(frozen_file) != replay.FROZEN_SHA:
        raise ValueError('original development freeze changed')
    frozen = p.read(frozen_file)
    validated = p.read(folder/'validated.json')
    if validated['status'] != 'eligible_descriptive_only' or validated['preload_ap']['version'] != VERSION:
        raise ValueError('no eligible pre-load AP estimate')
    artifacts=folder/'artifacts'
    manifest=p.read(artifacts/'manifest.json')
    if manifest.get('ap_idle_response_version') != VERSION:
        raise ValueError('wrong AP diagnostic manifest')
    boundary=p.read(artifacts/'common_boundary.json')
    origin=boundary['start_ns'];end=boundary['planned_end_ns']
    if end-origin != 120_000_000_000:
        raise ValueError('changed common boundary')
    rows=p.read(artifacts/'requests.json')
    if len(rows)!=24 or any(r['terminal_status']!='succeeded' for r in rows):
        raise ValueError('incomplete workload')
    initial=p.read(artifacts/'start_ap.accepted.json')
    if initial['common_start_ns'] != origin or initial.get('gate_mode')!='numeric-ap-observe-v2':
        raise ValueError('initial AP boundary')
    first_dispatch=min(r['dispatch_ns'] for r in rows)
    last_release=max(r['lane_available_ns'] for r in rows)
    if not origin < first_dispatch < last_release < end:
        raise ValueError('load outside common window')
    segments=replay_analysis.observed_segments(rows,origin)
    events=descriptive.read_lines(artifacts/'progress.jsonl')
    cooling_end=[e['mono_ns'] for e in events if e.get('phase')=='resident_cooling' and e.get('kind')=='phase_end']
    if len(cooling_end)!=1 or cooling_end[0]<=end:
        raise ValueError('missing resident cooling end')
    cool_s=(cooling_end[0]-origin)/1e9
    segments.append(dict(start_s=120.,end_s=cool_s,state='idle'))
    thermal=descriptive.read_lines(folder/'thermal.jsonl')
    points=[((x['mono_ns']-origin)/1e9,float(x['AP'])) for x in thermal
            if first_dispatch<=x['mono_ns']<=cooling_end[0] and x.get('AP') not in ('',None)
            and x.get('thermal_status')=='0']
    if (len(points)<20 or points[0][0]-(first_dispatch-origin)/1e9>10 or
            cool_s-points[-1][0]>10 or
            any(not 0<b[0]-a[0]<=10 for a,b in zip(points,points[1:]))):
        raise ValueError('incomplete post-load AP coverage')
    effective=validated['preload_ap']['effective_idle_reference_c']
    starts=float(initial['ap_c'])
    predicted=predict(segments,frozen,starts,effective,[t for t,_ in points]+
                      [s['end_s'] for s in segments])
    last_s=(last_release-origin)/1e9
    table=[]
    for t,actual in points:
        estimate=predicted[round(t,9)]
        phase='work' if t<=last_s else 'resident_idle_after_work'
        table.append(dict(elapsed_s=t,phase=phase,observed_ap_c=actual,
            predicted_ap_c=estimate,observed_change_from_start_c=actual-starts,
            predicted_change_from_start_c=estimate-starts,
            signed_error_c=estimate-actual))
    idle=[r for r in table if r['phase']=='resident_idle_after_work']
    if sum(r['phase']=='work' for r in table)<2:
        raise ValueError('insufficient work AP samples')
    if len(idle)<10:
        raise ValueError('insufficient post-work idle AP')
    errors=[r['signed_error_c'] for r in table]
    split={phase:dict(samples=sum(r['phase']==phase for r in table),
        signed_mean_c=sum(r['signed_error_c'] for r in table if r['phase']==phase)/
            sum(r['phase']==phase for r in table))
        for phase in ('work','resident_idle_after_work') if any(r['phase']==phase for r in table)}
    report=dict(version=VERSION,role=manifest['ap_schedule_role'],
        data_role='independent_confirmation' if manifest['ap_schedule_role']=='confirmation' else 'development',
        frozen_sha256=p.digest(frozen_file),initial_ap_c=starts,
        preload_effective_reference_c=effective,preload_fit=validated['preload_ap'],
        first_dispatch_s=(first_dispatch-origin)/1e9,last_lane_release_s=last_s,
        cooling_end_s=cool_s,ap_samples=len(table),
        observed_idle_direction_c=idle[-1]['observed_ap_c']-idle[0]['observed_ap_c'],
        predicted_idle_direction_c=idle[-1]['predicted_ap_c']-idle[0]['predicted_ap_c'],
        ap_path_mae_c=sum(map(abs,errors))/len(errors),
        ap_path_max_absolute_error_c=max(map(abs,errors)),
        ap_peak_observed_c=max(r['observed_ap_c'] for r in table),
        ap_peak_predicted_c=max(r['predicted_ap_c'] for r in table),
        ap_peak_signed_error_c=max(r['predicted_ap_c'] for r in table)-
            max(r['observed_ap_c'] for r in table),
        phase_residuals=split,accuracy_pass=None,policy_selection_pass=None,
        strict_support=False,ambient_identified=False,hidden_heat_identified=False,
        meaning='actual lane schedule and pre-load AP supplied; later AP is comparison only')
    output.mkdir(parents=True)
    (output/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    with (output/'ap_path.csv').open('w',encoding='utf-8',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(table[0]));writer.writeheader();writer.writerows(table)
    return report
