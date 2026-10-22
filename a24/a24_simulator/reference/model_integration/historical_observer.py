"""Unchanged A24 historical model observed along saved schedules, not new J.

Only supported complete owner intervals are observed. No future policy is run.
Raw battery API readings are never scaled into energy by this module.
"""
from __future__ import annotations

import importlib.util
import math
from pathlib import Path

BASE = Path('C:/Users/chomg/Documents/Codex/2026-10-11/dkfo')
ADAPTER = BASE / 'work/A24-INTEGRATED-SIM-20261016-G002/a24_cost_adapter.py'
ADAPTER_SHA = '91a4015be1a1981afe51923d9047da66f735c5faf953118dbd00fc86ff45945e'
STATES = ('classification_CPU', 'detection_CPU', 'classification_GPU',
          'classification_GPU+detection_CPU')


def _finite(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def _state(active):
    pairs = {(x['task'], x['route']) for x in active}
    if len(active) != len(pairs):
        raise ValueError('Duplicate active same-resource owners')
    if not pairs:
        return 'resident_idle'
    if pairs == {('C', 'CPU')}:
        return STATES[0]
    if pairs == {('D', 'CPU')}:
        return STATES[1]
    if pairs == {('C', 'GPU')}:
        return STATES[2]
    if pairs == {('C', 'GPU'), ('D', 'CPU')}:
        return STATES[3]
    raise ValueError('Unsupported owner combination')


def conditional_energy(session, profile, start_s=0., end_s=180.):
    """Fixed historical gauge-space arithmetic, with actual coverage required."""
    intervals = session.get('owner_intervals', [])
    window = session.get('observation_window_s', session.get('actual_recorded_window_s'))
    activity = session.get('activity_coverage_s')
    if activity:
        window = [max(window[0], activity[0]), min(window[1], activity[1])] if window else activity
    if not window or window[0] > start_s or window[1] < end_s:
        return {'status': 'UNKNOWN_WINDOW_COVERAGE', 'historical_conditional_J': None,
                'measured_J': None, 'energy_error_J': None}
    if session.get('state_intervals') and not intervals:
        return {'status': 'UNKNOWN_AGGREGATE_OWNER_COST_BINDING', 'historical_conditional_J': None,
                'measured_J': None, 'energy_error_J': None}
    marks = sorted({start_s, end_s, *[max(start_s, min(end_s, float(x[k])))
                   for x in intervals for k in ('start_s', 'end_s')]})
    occupancy = {key: 0. for key in (*STATES, 'resident_idle')}
    for a, b in zip(marks, marks[1:]):
        if b <= a:
            continue
        active = [x for x in intervals if x['start_s'] < b and x['end_s'] > a]
        occupancy[_state(active)] += b-a
    baseline = float(profile['measured35']['baseline_w'])
    powers = profile['cost_anchor']['energy_increment_w']
    terms = {key: occupancy[key] * float(powers[key]) for key in STATES}
    energy = baseline * (end_s-start_s) + sum(terms.values())
    return {'status': 'HISTORICAL_GAUGE_CONDITIONAL_ONLY',
            'window_s': [start_s, end_s], 'state_seconds': occupancy,
            'baseline_J': baseline*(end_s-start_s), 'increment_terms_J': terms,
            'historical_conditional_J': energy, 'measured_J': None,
            'energy_error_J': None, 'independent_energy_saving_validated': False}


def load_models():
    from runtime_guard import sha
    if sha(ADAPTER) != ADAPTER_SHA:
        raise ValueError('Frozen historical cost adapter changed')
    spec = importlib.util.spec_from_file_location('a24_pinned_historical_observer', ADAPTER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.modelsload()


def observe_ap(session, models, model_name='MEASURED35'):
    """Observe original equations, preserving the real precommon history gate."""
    if session.get('state_intervals') and not session.get('owner_intervals'):
        return {'status':'UNKNOWN_AGGREGATE_HISTORICAL_OWNER_REPLAY',
                'predictions':[], 'historical_model':model_name, 'MAE_C':None}
    pre = [x for x in session.get('observations', [])
           if _finite(x.get('t_s')) and _finite(x.get('ap_c')) and x['t_s'] <= 0.]
    pre.sort(key=lambda x: x['t_s'])
    if len(pre) < 8 or pre[-1]['t_s']-pre[0]['t_s'] < 20.:
        return {'status': 'UNKNOWN_REAL_INITIAL_HISTORY', 'predictions': [],
                'historical_model': model_name, 'MAE_C': None}
    if any(not _finite(x.get('lo_s')) or not _finite(x.get('hi_s'))
           or not x['lo_s'] <= x['t_s'] <= x['hi_s'] <= 0 for x in pre):
        return {'status': 'UNKNOWN_REAL_PRECOMMON_CLOCK_BRACKETS', 'predictions': [],
                'historical_model': model_name, 'MAE_C': None}
    from copy import deepcopy
    profile = deepcopy(models['profile'])
    public = deepcopy(profile['trend27_anchor']['public_boundary'])
    public['pre'] = [{'t': float(x['t_s']), 'lo': float(x['lo_s']),
                      'hi': float(x['hi_s']), 'ap': float(x['ap_c'])} for x in pre]
    public['pre_w'] = models['baseline_w']
    original = models['A24Cost'](profile['cost_anchor'], profile['trend27_anchor']['thermal']['AP'], public)
    state = original if model_name == 'TREND27' else models['CompactCost'](original, profile)
    intervals = session.get('owner_intervals', [])
    observations = [x for x in session.get('observations', [])
                    if _finite(x.get('t_s')) and _finite(x.get('ap_c')) and x['t_s'] >= 0.]
    observations.sort(key=lambda x: x['t_s'])
    # Initial owners crossing0 cannot be invented from events whose dispatch is missing.
    if any(x['start_s'] < 0 < x['end_s'] for x in intervals):
        return {'status': 'UNKNOWN_PRECOMMON_OWNER_STATE', 'predictions': [], 'MAE_C': None}
    events = []
    for i, x in enumerate(intervals):
        if x['end_s'] <= 0:
            continue
        events.extend([(float(x['start_s']), 1, str(x.get('request_id', i)), x),
                       (float(x['end_s']), 0, str(x.get('request_id', i)), x)])
    events.sort(key=lambda x: (x[0], x[1], x[2]))
    cursor = 0
    predictions = []
    active = {}
    for observation in observations:
        t = float(observation['t_s'])
        while cursor < len(events) and events[cursor][0] <= t:
            et, kind, rid, item = events[cursor]
            if et < 0:
                raise ValueError('Unqualified historical initial owner event')
            state.advance(et)
            if kind == 1:
                active[rid] = item
                _state(list(active.values()))
                state.dispatch(rid, 'classification' if item['task']=='C' else 'detection', item['route'])
            else:
                if rid not in active:
                    raise ValueError('AVAILABLE without recorded dispatch')
                state.available(rid, item['route'])
                del active[rid]
            cursor += 1
        state.advance(t)
        pred = float(state.snapshot()['temperature_c']['AP'])
        predictions.append({'t_s': t, 'observed_AP_C': float(observation['ap_c']),
                            'predicted_AP_C': pred, 'error_C': pred-float(observation['ap_c'])})
    return {'status': 'SAVED_SCHEDULE_HISTORICAL_OBSERVER', 'historical_model': model_name,
            'predictions': predictions,
            'MAE_C': sum(abs(x['error_C']) for x in predictions)/len(predictions) if predictions else None,
            'measured_J': None, 'new_environment': 0, 'conditional_on_actual_schedule': True}
