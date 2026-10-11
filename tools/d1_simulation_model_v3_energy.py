"""Bounded empirical energy head; development fitting and pre-only prediction.

The baseline relaxation is a predictive hypothesis, not an identified physical
background-power law. This module has no device, default-policy or RL entry point.
"""
from __future__ import annotations

from collections import Counter
import math

import numpy as np

from tools import d1_model_refinement as prior
from tools import d1_simulation_model_v2 as schedule


VERSION = 'empirical-simulation-model-v3-energy'
STATES = tuple(prior.base.STATES)
GROUPS = ('old', 'history30', 'history180', 'macro', 'new_recovery')
LAMBDAS = (0., .01, .1, 1., 10., 100.)
GAINS = (0., .5, 1.)
RELAXATION_TAU_S = 30.
FORBIDDEN_PREDICTION_FIELDS = (
    'power_t', 'power_w', 'power_samples', 'ap', 'observed_ap_c',
    'observed_120s_j', 'observed_energy_j',
)


def _finite(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float, np.number)) or not math.isfinite(value):
        raise ValueError('nonfinite/invalid ' + label)
    return float(value)


def _positive(value, label):
    value = _finite(value, label)
    if value <= 0:
        raise ValueError('nonpositive ' + label)
    return value


def source_group(c):
    if 'source_group' in c:
        value = c['source_group']
    else:
        name = c.get('id', '')
        if not isinstance(name, str) or not name:
            raise ValueError('missing session identity')
        if 'MODEL2_RECOVERY_' in name:
            value = 'new_recovery'
        elif name.startswith('session_'):
            value = 'macro'
        elif '_180_' in name:
            value = 'history180'
        elif '_30_' in name:
            value = 'history30'
        else:
            value = 'old'
    if value not in GROUPS:
        raise ValueError('unsupported development source group')
    return value


def _covered_segments(segments, end):
    schedule.validate_segments(segments)
    if segments[0]['start_s'] > 0 or segments[-1]['end_s'] + 1e-6 < end:
        raise ValueError('schedule does not cover prediction/training window')
    return segments


def initial_power_late(c):
    """Construct one prior input using only samples strictly before issue at 35s.

    A caller holding raw measured targets may call this once before projecting a
    safe forecast input. `predict` itself never accepts those raw target fields.
    """
    if 'initial_power_late_w' in c:
        return _positive(c['initial_power_late_w'], 'initial late power')
    if 'pre_power_t' in c or 'pre_power_w' in c:
        times, watts = c.get('pre_power_t'), c.get('pre_power_w')
        explicitly_pre = True
    else:
        times, watts = c.get('power_t'), c.get('power_w')
        explicitly_pre = False
    if not isinstance(times, (list, tuple, np.ndarray)) or not isinstance(watts, (list, tuple, np.ndarray)) or len(times) != len(watts):
        raise ValueError('missing/mismatched prior power samples')
    past = []
    for t, value in zip(times, watts):
        t = _finite(t, 'power sample time')
        if t >= 35:
            if explicitly_pre:
                raise ValueError('future sample in pre power inputs')
            continue  # Future values, including missing values, are never read.
        past.append((t, _positive(value, 'prior power sample')))
    if len(past) < 2:
        raise ValueError('insufficient prior power samples')
    t = np.asarray([r[0] for r in past]); p = np.asarray([r[1] for r in past])
    if np.any(np.diff(t) <= 0) or t[0] > 10 or t[-1] < 30:
        raise ValueError('prior power ordering/10..30 coverage')
    use = (t[:-1] < 30) & (t[1:] > 10)
    if np.any(np.diff(t)[use] > 2.5):
        raise ValueError('prior power gap')
    grid = np.r_[10., t[(t > 10) & (t < 30)], 30.]
    return _positive(float(np.trapezoid(np.interp(grid, t, p), grid) / 20), 'initial late power')


def relaxation_integral(c, t):
    """J per unit gain, zero through the issue boundary; prior inputs only."""
    t = _finite(t, 'energy horizon')
    if t < 0:
        raise ValueError('negative energy horizon')
    pre = _positive(c.get('pre_w'), 'initial baseline power')
    u = max(0., t - 35.)
    return (initial_power_late(c) - pre) * (u + RELAXATION_TAU_S * math.expm1(-u / RELAXATION_TAU_S))


def _bin_starts(c):
    end = _finite(c.get('common_end_s', 120.), 'registered end')
    if end < 40:
        raise ValueError('insufficient registered training window')
    _covered_segments(c['actual'], end)
    return list(range(35, int(end) - 4, 5))


def design(c):
    """Observed five-second development targets minus the fixed pre baseline."""
    pre = _positive(c.get('pre_w'), 'initial baseline power')
    bins = _bin_starts(c)
    X = np.asarray([prior.base.exposure(c['actual'], a, a + 5) for a in bins], dtype=float)
    y = np.asarray([prior.integral(c, a, a + 5) - pre * 5 for a in bins], dtype=float)
    if not np.isfinite(X).all() or not np.isfinite(y).all():
        raise ValueError('nonfinite energy design/target')
    return X, y


def _settings(lambda_, gain):
    lambda_ = _finite(lambda_, 'ridge strength'); gain = _finite(gain, 'baseline gain')
    if lambda_ not in LAMBDAS or gain not in GAINS:
        raise ValueError('unregistered ridge strength/baseline gain')
    return lambda_, gain


def fit(cases, original, lambda_, gain):
    lambda_, gain = _settings(lambda_, gain)
    if len(cases) < 3 or any(c.get('role') != 'development' for c in cases):
        raise ValueError('at least three development sessions only')
    ids = [c.get('id') for c in cases]
    if any(not isinstance(i, str) or not i for i in ids) or len(set(ids)) != len(ids):
        raise ValueError('unique development session identities required')
    groups = [source_group(c) for c in cases]; counts = Counter(groups)
    xs, ys = [], []
    for c, group in zip(cases, groups):
        X, y = design(c)
        if gain:
            # Project prior inputs before computing a hypothesis adjustment.
            safe = dict(pre_w=c['pre_w'], initial_power_late_w=initial_power_late(c))
            phi = np.asarray([relaxation_integral(safe, a + 5) - relaxation_integral(safe, a) for a in _bin_starts(c)])
            y = y - gain * phi
        weight = 1 / math.sqrt(len(counts) * counts[group] * len(y))
        xs.append(X * weight); ys.append(y * weight)
    X = np.vstack(xs); y = np.concatenate(ys)
    norms = np.linalg.norm(X, axis=0)
    if np.any(norms <= 0) or np.linalg.matrix_rank(X) != 4:
        raise ValueError('four state increments numerically unidentified')
    anchor = np.asarray([_finite(original['energy_increment_w'][k], 'original increment') for k in STATES])
    if np.any(anchor < 0):
        raise ValueError('negative original increment')
    standardized = X / norms
    if lambda_:
        ridge = math.sqrt(lambda_)
        z = prior.base.nnls(np.vstack((standardized, ridge * np.eye(4))), np.r_[y, ridge * norms * anchor])
    else:
        z = prior.base.nnls(standardized, y)
    powers = z / norms
    if not np.isfinite(powers).all() or np.any(powers < 0):
        raise ValueError('invalid fitted energy increments')
    return dict(version=VERSION, increments=dict(zip(STATES, map(float, powers))),
        lambda_=lambda_, gain=gain, relaxation_tau_s=RELAXATION_TAU_S,
        development_ids=ids, source_groups=dict(sorted(counts.items())),
        weighting='source equal, then session equal, then five-second bin equal',
        energy_rank=4, standardized_column_norms=norms.tolist(),
        scaled_condition=float(np.linalg.cond(standardized)),
        weighted_bin_RMSE_j=float(np.sqrt(np.sum((X @ powers - y) ** 2))),
        original_increment_anchor_w=dict(zip(STATES, map(float, anchor))),
        baseline_input='pre50 power and pre10..30 late power; future power forbidden',
        baseline_relaxation_is_predictive_hypothesis=True,
        physical_background_power_cause_identified=False,
        practical_state_power_identifiability_established=False,
        default=False, strict_support=False, experiment_ready=False, accuracy_pass=None)


def predict(c, head, t, segments=None):
    """Predict from a projected prior-only input and the supplied schedule."""
    forbidden = [key for key in FORBIDDEN_PREDICTION_FIELDS if key in c]
    if forbidden:
        raise ValueError('future target fields forbidden at prediction: ' + ', '.join(forbidden))
    t = _finite(t, 'energy horizon')
    if t < 0:
        raise ValueError('negative energy horizon')
    pre = _positive(c.get('pre_w'), 'initial baseline power')
    _, gain = _settings(head.get('lambda_'), head.get('gain'))
    if head.get('relaxation_tau_s') != RELAXATION_TAU_S:
        raise ValueError('baseline relaxation time changed')
    powers = np.asarray([_finite(head['increments'][k], 'energy increment') for k in STATES])
    if np.any(powers < 0):
        raise ValueError('negative energy increment')
    ss = c.get('actual') if segments is None else segments
    _covered_segments(ss, t)
    exposure = prior.base.exposure(ss, 0, t)
    correction = gain * relaxation_integral(c, t) if gain else 0.
    result = pre * t + float(exposure @ powers) + correction
    # gain<=1 is a convex baseline move between two positive prior powers.
    if not math.isfinite(result) or result < 0:
        raise ValueError('invalid predicted energy')
    return result
