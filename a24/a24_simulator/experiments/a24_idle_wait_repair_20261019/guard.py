"""Public-forecast Pareto filter for idle-system WAIT actions only.

Never consults request outcomes, route banks, checkpoints or past decisions.
"""
import math
import numpy as np
from . import VERSION

ABS_TOL = 1e-9
REL_TOL = 1e-9
HORIZON_TOL_S = 1e-8
METRICS = ('energy', 'mean_heat', 'urgent_lateness', 'normal_lateness',
           'unfinished', 'AP_end', 'peak')


def metrics(f):
    """Reject incomplete/unknown forecasts rather than assuming dominance."""
    if (f.get('comparison_complete') is not True or f.get('capped') is not False
            or f.get('no_future_arrivals') is not True or f.get('no_future_latents') is not True):
        return None
    try:
        values = [*f['cost'], f['AP_end'], f['peak']]
        if len(values) != len(METRICS) or not all(math.isfinite(v) for v in values):
            return None
        if not math.isfinite(f['H_s']):
            return None
        if not isinstance(f['visible_ids'], list):
            return None
    except (KeyError, TypeError, ValueError):
        return None
    return values


def dominates(a, b):
    tol = [ABS_TOL + REL_TOL * max(abs(x), abs(y)) for x, y in zip(a, b)]
    return (all(x <= y + t for x, y, t in zip(a, b, tol))
            and any(x < y - t for x, y, t in zip(a, b, tol)))


def filter_idle_waits(s, actions, forecasts, physical_mask):
    """Return a fresh eligibility mask and a public, auditable explanation."""
    eligible = np.asarray(physical_mask, dtype=bool).copy()
    if eligible.ndim != 1 or len(actions) > len(eligible) or len(actions) != len(forecasts):
        raise ValueError('Action, forecast and mask dimensions differ')
    if eligible[len(actions):].any() or not eligible.any():
        raise ValueError('Physical mask must contain only existing actions')
    record = dict(version=VERSION, applied=False, removed=[], metric_names=list(METRICS),
                  absolute_tolerance=ABS_TOL, relative_tolerance=REL_TOL,
                  reason='Owners present' if s['owners'] else 'No dominated idle WAIT')
    if s['owners'] or not s['queue']:
        return eligible, record
    queued_ids = {q['request_id'] for q in s['queue']}
    dispatches = [i for i, a in enumerate(actions) if eligible[i] and a['kind'] == 'DISPATCH'
                  and a.get('request_id') in queued_ids and a.get('route') in ('CPU', 'GPU')]
    vectors = [metrics(f) for f in forecasts]
    for i, action in enumerate(actions):
        if not eligible[i] or action['kind'] != 'WAIT' or vectors[i] is None:
            continue
        for j in dispatches:
            if vectors[j] is None:
                continue
            a, b = forecasts[j], forecasts[i]
            if (not math.isclose(a['H_s'], b['H_s'], rel_tol=0., abs_tol=HORIZON_TOL_S)
                    or sorted(a['visible_ids']) != sorted(b['visible_ids'])
                    or actions[j]['request_id'] not in a['visible_ids']):
                continue
            if dominates(vectors[j], vectors[i]):
                eligible[i] = False
                record['removed'].append(dict(index=i, action=action.copy(),
                    witness_index=j, witness_action=actions[j].copy(),
                    dispatch_metrics=vectors[j], wait_metrics=vectors[i], horizon_s=a['H_s']))
                break
    # Dispatches are never removed; this cannot strand the policy without actions.
    assert eligible.any()
    record['applied'] = bool(record['removed'])
    if record['applied']:
        record['reason'] = 'An available dispatch dominates idle WAIT in every public forecast metric'
    return eligible, record
