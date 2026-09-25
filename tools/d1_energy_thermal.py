"""energy-thermal-pc-v1: optional, non-causal-to-policy trace accounting.

Whole-device battery power; never a CPU/GPU rail measurement. No device commands.
Thermal dynamics are state-driven, NOT a separately identified power-to-heat law.
"""
from __future__ import annotations

import math

VERSION = 'energy-thermal-pc-v1'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def discharge_w(sample, scale_ua):
    """Scale is an explicit unit hypothesis, never fitted to a counter ratio."""
    require(scale_ua in (1, 1000), 'explicit uA or mA interpretation required')
    keys = ('current_raw', 'voltage_mV', 'plugged')
    if any(sample.get(k) is None for k in keys):
        return None
    i, v = sample['current_raw'], sample['voltage_mV']
    if (sample.get('current_valid') is not True or sample['plugged'] != 0
            or not math.isfinite(i) or not math.isfinite(v)
            or i == -2147483648 or i > 0 or v <= 0):
        return None
    return -i * scale_ua * v * 1e-9


def canonical_samples(samples, time_key='mono_ns'):
    by_time = {}
    duplicates = 0
    for sample in samples:
        t = sample[time_key]
        require(isinstance(t, int) and t >= 0, 'invalid monotonic timestamp')
        if t in by_time:
            require(by_time[t] == sample, 'conflicting duplicate timestamp')
            duplicates += 1
        by_time[t] = sample
    return [by_time[t] for t in sorted(by_time)], duplicates


def integrate(samples, start_ns, end_ns, scale_ua, max_gap_s=2.5):
    """Trapezoidal *power* interpolation; clip each segment at phase edges.

    No extrapolation, forward fill or bridging long gaps. Missing energy is not 0.
    Negative incremental energy after baseline subtraction is retained by caller.
    """
    require(end_ns >= start_ns and max_gap_s > 0, 'invalid integration window')
    samples, duplicates = canonical_samples(samples)
    energy = covered = 0.0
    dropped_gap_s = 0.0
    for a, b in zip(samples, samples[1:]):
        ta, tb = a['mono_ns'], b['mono_ns']
        lo, hi = max(ta, start_ns), min(tb, end_ns)
        if hi <= lo:
            continue
        dt = (tb - ta) / 1e9
        pa, pb = discharge_w(a, scale_ua), discharge_w(b, scale_ua)
        if dt > max_gap_s:
            dropped_gap_s += (hi-lo)/1e9
            continue
        if pa is None or pb is None:
            continue
        p0 = pa + (pb-pa)*(lo-ta)/(tb-ta)
        p1 = pa + (pb-pa)*(hi-ta)/(tb-ta)
        elapsed = (hi-lo)/1e9
        energy += (p0+p1)/2*elapsed
        covered += elapsed
    duration = (end_ns-start_ns)/1e9
    return dict(covered_energy_j=energy if covered else None,
                duration_s=duration, covered_s=covered,
                missing_s=max(0., duration-covered), dropped_gap_s=dropped_gap_s,
                full_energy_j=energy if abs(duration-covered) < 1e-6 else None,
                mean_power_w=energy/covered if covered else None,
                duplicates=duplicates, unit_hypothesis_ua_per_raw=scale_ua)


def transition(temperature, equilibrium, tau_s, dt_s):
    require(all(math.isfinite(x) for x in (temperature, equilibrium, tau_s, dt_s))
            and tau_s > 0 and dt_s >= 0, 'invalid thermal transition')
    return equilibrium + (temperature-equilibrium)*math.exp(-dt_s/tau_s)


def excess_degree_seconds(start, equilibrium, tau, duration, reference):
    """Exact positive area above a declared reference, not a safety threshold."""
    transition(start,equilibrium,tau,0)
    require(math.isfinite(reference) and math.isfinite(duration) and duration>=0,'invalid burden reference/window')
    cuts=[0.,duration]
    if start != equilibrium:
        ratio=(reference-equilibrium)/(start-equilibrium)
        if 0 < ratio < 1:
            t=-tau*math.log(ratio)
            if 0<t<duration:cuts.append(t)
    cuts.sort();area=0.
    for a,b in zip(cuts,cuts[1:]):
        if transition(start,equilibrium,tau,(a+b)/2)>reference:
            area+=(equilibrium-reference)*(b-a)+(start-equilibrium)*tau*(math.exp(-a/tau)-math.exp(-b/tau))
    return area


def account(segments, profile, *, device, model, mode, initial_temperature,
            planned, completed, service_constraints_met=None, scope=None):
    """Common-window state schedule, explicit power for each concurrent state.

    Modes: observed_replay, conditional_prediction, assumption_exploration.
    No resource-additive power default. State coefficients preserve sensor identity.
    """
    require(mode in ('observed_replay','conditional_prediction','assumption_exploration'), 'mode')
    require(profile['version'] == VERSION, 'profile version')
    require(0 <= completed <= planned, 'completion denominator')
    require(profile['device'] == device and profile['model'] == model, 'device/model mismatch')
    if mode == 'assumption_exploration':
        require(profile['evidence'] == 'explicit_assumptions', 'assumptions must be declared')
    else:
        require(profile['evidence'] == 'legacy_mobilenet_conditional', 'unsupported measured scope')
        require(model == 'mobilenet_v1_1.0_224_float', 'current models unsupported')
        require(scope is not None and all(profile.get(k) is not None and scope.get(k)==profile[k]
                for k in ('fingerprint','model_sha256','condition')), 'fingerprint/model/condition mismatch')
        if mode == 'observed_replay':
            require(profile.get('recorded_schedule') == segments, 'replay requires exact recorded schedule')
        if mode == 'conditional_prediction':
            sequence=[]
            for s in segments:
                if not sequence or sequence[-1]!=s['state']:sequence.append(s['state'])
            require(sequence==profile.get('supported_state_sequence'), 'unsupported state sequence')
    sensors = profile['sensors']
    require(set(initial_temperature) == set(sensors), 'sensor mismatch')
    temps = dict(initial_temperature)
    peak = dict(temps)
    reference=profile.get('reference_temperature',dict(temps))
    require(set(reference)==set(sensors),'reference sensor mismatch')
    burden={s:0. for s in sensors}
    trace = []
    energy = 0.
    end = 0.
    durations={}
    for s in segments:
        require(s['start_s'] == end and s['end_s'] >= end, 'noncontiguous/overlapping common window')
        state = profile['states'].get(s['state'])
        require(state is not None, 'unsupported state (including parallel)')
        dt = s['end_s']-end
        durations[s['state']]=durations.get(s['state'],0)+dt
        require(math.isfinite(state['power_w']) and state['power_w'] >= 0, 'invalid whole-device power')
        require(set(state['thermal']) == set(sensors), 'thermal sensor mismatch')
        if mode == 'conditional_prediction':
            require(durations[s['state']] <= state['max_observed_duration_s'], 'duration extrapolation unsupported')
            require(state.get('identified') is True, 'unidentified thermal coefficients')
        energy += state['power_w']*dt
        before = dict(temps)
        for sensor in sensors:
            v = state['thermal'][sensor]
            burden[sensor]+=excess_degree_seconds(temps[sensor],v['equilibrium_c'],v['tau_s'],dt,reference[sensor])
            if mode == 'conditional_prediction':
                require(v['observed_min_c'] <= temps[sensor] <= v['observed_max_c'], 'temperature out of support')
            temps[sensor] = transition(temps[sensor], v['equilibrium_c'], v['tau_s'], dt)
            if mode == 'conditional_prediction':
                require(v['observed_min_c'] <= temps[sensor] <= v['observed_max_c'], 'predicted temperature out of support')
            peak[sensor] = max(peak[sensor], temps[sensor])
        trace.append(dict(**s, temperature_start=before, temperature_end=dict(temps), cumulative_energy_j=energy))
        end = s['end_s']
    return dict(version=VERSION, mode=mode, source=profile.get('source'),
                unit_status=profile['unit_status'], energy_j=energy, temperature=temps,
                peak_temperature=peak, common_window_s=end, planned=planned, completed=completed,
                reference_temperature=reference,degree_seconds_above_reference=burden,
                unfinished=planned-completed,
                eligible_for_equal_work_comparison=completed == planned and service_constraints_met is True,
                optimization_pass=False, experiment_ready=False, trace=trace,
                thermal_driver='state-based; energy scale uncertainty does not numerically drive this model',
                evidence=profile['evidence'])


def ledger_segments(result, horizon_ns):
    """Read-only adapter from existing PC engine output; no changes to dispatch.

    States are joint lane occupancy tuples; request waiting is reported separately.
    Whole-device idle power includes waiting; never add idle twice per lane.
    """
    fields = ('dispatch_ns','execution_start_ns','output_ready_ns','persist_complete_ns',
              'worker_release_ns','lane_available_ns')
    labels = ('prepare','execute','store','worker_release','callback')
    boundaries = {0, horizon_ns}
    rows = result['ledger']
    for r in rows:
        boundaries.update(r[f] for f in fields if f in r and 0 <= r[f] <= horizon_ns)
        if 0 <= r['arrival_ns'] <= horizon_ns:
            boundaries.add(r['arrival_ns'])
    times = sorted(boundaries)
    segments = []
    for a,b in zip(times,times[1:]):
        active=[]
        waiting=0
        for r in rows:
            if r['arrival_ns'] <= a < r.get('dispatch_ns', math.inf):
                waiting += 1
            for i,label in enumerate(labels):
                if r.get(fields[i],math.inf) <= a < r.get(fields[i+1],math.inf):
                    active.append(f"{r['task']}:{r['backend']}:{r['priority']}:{label}")
        state = '+'.join(sorted(active)) or 'idle'
        segments.append(dict(start_s=a/1e9,end_s=b/1e9,state=state,waiting=waiting))
    return segments
