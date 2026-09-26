"""Thermal/energy evaluation layer v1 (1겹). Evaluation only — no feedback into the schedule.

Reuses 조민규 `d1_energy_thermal.ledger_segments` / `account` unchanged. New here (0단계 판정):
  1. parameters -> his per-state profile (equilibrium = T_init + gain * (P - idle_w), our assumption)
  2. exact t_skin_max exceedance time / count from his trace
Cannot add an NPU lane or throttle-induced delay: the schedule comes from his engine as-is.
"""
from __future__ import annotations

import math

SENSORS = ('AP', 'SKIN')
HORIZON_NS = 120_000_000_000


def parse_state(state):
    """Joint lane-occupancy string -> {backend: [labels]}."""
    lanes = {}
    if state == 'idle':
        return lanes
    for item in state.split('+'):
        task, backend, priority, label = item.split(':')
        lanes.setdefault(backend, []).append(label)
    return lanes


def state_entry(state, p):
    """Power and thermal target for one joint state. Every value here is an assumption."""
    lanes = parse_state(state)
    executing = sorted(b for b, labels in lanes.items() if 'execute' in labels)
    other = sorted(b for b in lanes if b not in executing)
    busy = {b: p['busy_w'][b] * p['busy_scale'] for b in ('CPU', 'GPU')}
    drivers = executing or (other if p['nonexec_power'] == 'busy' else [])
    if len(drivers) == 2:
        # No measured concurrent whole-device power exists: exploration value only, never CPU+GPU.
        power = p['parallel_k'] * max(busy.values())
        gain = {s: max(p['gain'][s][b] for b in drivers) for s in SENSORS}
        tau = {s: min(p['tau_heat'][s][b] for b in drivers) for s in SENSORS}
    elif len(drivers) == 1:
        b = drivers[0]
        power = busy[b]
        gain = {s: p['gain'][s][b] for s in SENSORS}
        tau = {s: p['tau_heat'][s][b] for s in SENSORS}
    else:
        power = p['idle_w']
        gain = {s: 0.0 for s in SENSORS}
        tau = {s: p['tau_cool'][s] for s in SENSORS}
    dp = power - p['idle_w']
    thermal = {s: dict(equilibrium_c=p['t_init'][s] + gain[s] * dp, tau_s=tau[s]) for s in SENSORS}
    return dict(power_w=power, thermal=thermal)


def profile(segments, p, thermal_module):
    states = {s['state']: state_entry(s['state'], p) for s in segments}
    return dict(version=thermal_module.VERSION, device='SYNTHETIC', model='SYNTHETIC',
                evidence='explicit_assumptions', sensors=list(SENSORS), states=states,
                reference_temperature=dict(p['t_init']),
                source='sim_thermal/layer.py v1: S26 MobileNet W repurposed_assumption + assumed gain/tau',
                unit_status='W and degC assumed; S26 energy absolute accuracy uncertified')


def exceedance(trace, states, sensor, limit):
    """Exact time above `limit` and number of entries, using the monotone exponential in each segment."""
    above = 0.0
    entries = 0
    was_above = None
    for seg in trace:
        t0 = seg['temperature_start'][sensor]
        t1 = seg['temperature_end'][sensor]
        dt = seg['end_s'] - seg['start_s']
        eq = states[seg['state']]['thermal'][sensor]['equilibrium_c']
        tau = states[seg['state']]['thermal'][sensor]['tau_s']
        start_above = t0 > limit
        if was_above is None and start_above:
            entries += 1
        if start_above and t1 > limit:
            above += dt
        elif start_above != (t1 > limit) and dt > 0 and t0 != eq:
            cross = -tau * math.log((limit - eq) / (t0 - eq))
            cross = min(max(cross, 0.0), dt)
            above += (cross if start_above else dt - cross)
            if not start_above:
                entries += 1
        was_above = t1 > limit
    return above, entries


def evaluate(result, requests, p, thermal_module, limits):
    """His KPIs pass through unchanged; thermal/energy added, or None when the ledger is incomplete."""
    out = dict(metrics=result['metrics'])
    ledger = result['ledger']
    if any(r.get('status') != 'succeeded' for r in ledger):
        out.update(thermal=None, reason='incomplete ledger: open occupancy is not idle (his rule)')
        return out
    segments = thermal_module.ledger_segments(result, HORIZON_NS)
    prof = profile(segments, p, thermal_module)
    acc = thermal_module.account(segments, prof, device='SYNTHETIC', model='SYNTHETIC',
                                 mode='assumption_exploration', initial_temperature=dict(p['t_init']),
                                 planned=len(requests), completed=len(requests))
    exc = {lim: exceedance(acc['trace'], prof['states'], 'SKIN', lim) for lim in limits}
    parallel_s = sum(s['end_s'] - s['start_s'] for s in segments
                     if sum('execute' in l for l in parse_state(s['state']).values()) == 2)
    out['thermal'] = dict(energy_j=acc['energy_j'], energy_per_request_j=acc['energy_j'] / len(requests),
                          peak_skin_c=acc['peak_temperature']['SKIN'], peak_ap_c=acc['peak_temperature']['AP'],
                          skin_over={str(k): dict(seconds=v[0], entries=v[1]) for k, v in exc.items()},
                          parallel_execute_s=parallel_s)
    return out
