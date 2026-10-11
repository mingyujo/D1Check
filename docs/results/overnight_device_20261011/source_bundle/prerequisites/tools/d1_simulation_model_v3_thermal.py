"""Development-only, source-balanced thermal correction of the frozen model.

Prediction consumes only pre-issue AP, a covered schedule and known history.
No future measured AP or power is used by prediction or its cache.
"""
from __future__ import annotations

from collections import Counter
from functools import lru_cache
import hashlib
import json
import math

import numpy as np

from tools import d1_simulation_model_v2 as v2

VERSION = 'empirical-simulation-model-v3-thermal'
SLOW_TAU_S = 1920.
INITIAL_TAU_S = 30.
ALPHAS = (0., .5, 1.)


def group(c):
    """One source per measurement family, rather than one source per session."""
    identity = c['id']
    if 'MODEL2_RECOVERY' in identity:
        return 'new_recovery'
    if identity.startswith('session_'):
        return 'macro'
    if '_30_' in identity:
        return 'history30'
    if '_180_' in identity:
        return 'history180'
    return 'old'


def prior_coefficients(original):
    """Exact five-column representation of the original, g=0 AP model."""
    ap = original['ap']
    if float(ap['g']) != 0.:
        raise ValueError('the five-column prior requires original g=0')
    slopes = ap['parameters']['ap_slope_at_30_c_per_s']
    theta = np.array([float(ap['k'])*(slopes[s]-slopes['resident_idle'])
                      for s in v2.STATES] + [0.], dtype=float)
    if not np.all(np.isfinite(theta)) or np.any(theta < 0):
        raise ValueError('nonfinite/negative original AP prior')
    return theta


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def _original_input(original):
    beta = float(original['ap']['beta'])
    powers = {s: float(original['energy_increment_w'][s]) for s in v2.STATES}
    if not math.isfinite(beta) or beta <= 0 or any(not math.isfinite(p) or p < 0 for p in powers.values()):
        raise ValueError('invalid frozen decay or slow input powers')
    return dict(beta=beta, slow_tau_s=SLOW_TAU_S, slow_input_w=powers)


def _prediction(c, parameters, theta, alpha):
    if alpha not in ALPHAS:
        raise ValueError('unsupported initial-state alpha')
    theta = np.asarray(theta, dtype=float)
    model = dict(ap=dict(parameters, coefficients=theta.tolist()))
    # The existing validity boundary covers pre brackets/gaps, query order,
    # known history, supported states and complete schedule coverage.
    existing, initial = v2.ap_prediction(c, model)
    if alpha == 1.:
        return np.asarray(existing), dict(initial, initial_alpha=1., initial_h_penalty=0.)

    ss = v2.predictive_schedule(c)
    pre = c['pre']
    times = np.array([r['t'] for r in pre], dtype=float)
    observed = np.array([r['ap'] for r in pre], dtype=float)
    beta = parameters['beta']

    def forcing(ts):
        return (v2.kernel(ss, ts, beta, dict(zip(v2.STATES, theta[:4]))) +
                theta[4]*v2.kernel(ss, ts, 1/SLOW_TAU_S, parameters['slow_input_w']))

    corrected = observed-forcing(times)
    dt = times-times[0]
    eb = np.exp(-beta*dt)
    matrix = np.column_stack((1-eb, [v2.memory.convolution(beta, INITIAL_TAU_S, float(t)) for t in dt]))
    norms = np.linalg.norm(matrix, axis=0)
    scaled = matrix/norms
    target = corrected-corrected[0]*eb
    if alpha == 0.:
        reference = float(matrix[:, 0]@target/(matrix[:, 0]@matrix[:, 0]))
        h0 = 0.
        penalty = None  # Exact constrained H=0, rather than an infinite JSON value.
    else:
        penalty = (1-alpha)/alpha
        augmented = np.vstack((scaled, [0., math.sqrt(penalty)]))
        coefficients = np.linalg.lstsq(augmented, np.r_[target, 0.], rcond=None)[0]/norms
        reference, h0 = map(float, coefficients)
    anchor = times[-1]
    h = h0*math.exp(-(anchor-times[0])/INITIAL_TAU_S)
    queries = np.asarray(c['q'], dtype=float)
    elapsed = queries-anchor
    values = (reference+(corrected[-1]-reference)*np.exp(-beta*elapsed) +
              h*np.array([v2.memory.convolution(beta, INITIAL_TAU_S, float(t)) for t in elapsed]) +
              forcing(queries))
    if not np.all(np.isfinite(values)):
        raise ValueError('nonfinite regularized AP prediction')
    initial.update(reference_c=reference, h_last=h, initial_alpha=alpha,
                   initial_h_penalty=penalty, initial_h_constrained_zero=alpha == 0.)
    return values, initial


@lru_cache(maxsize=512)
def _cached_design(input_json, parameters_json, alpha):
    c = json.loads(input_json)
    parameters = json.loads(parameters_json)
    baseline, initial = _prediction(c, parameters, np.zeros(5), alpha)
    columns = []
    for index in range(5):
        unit = np.zeros(5)
        unit[index] = 1.
        columns.append(_prediction(c, parameters, unit, alpha)[0]-baseline)
    return baseline, np.column_stack(columns), initial


def design(c, original, alpha):
    """Return affine basis; content-keyed cache cannot reuse mutated inputs."""
    if alpha not in ALPHAS:
        raise ValueError('unsupported initial-state alpha')
    inputs = {k: c[k] for k in ('pre', 'q', 'actual')}
    inputs['history'] = c.get('history', [])
    baseline, matrix, initial = _cached_design(_canonical(inputs), _canonical(_original_input(original)), float(alpha))
    # Callers may mutate returned arrays without changing a later prediction.
    return baseline.copy(), matrix.copy(), dict(initial)


def predict(c, head, original):
    theta = np.asarray(head['coefficients'], dtype=float)
    if theta.shape != (5,) or not np.all(np.isfinite(theta)) or np.any(theta < 0):
        raise ValueError('invalid thermal coefficients')
    baseline, matrix, _ = design(c, original, head['alpha'])
    values = baseline+matrix@theta
    if not np.all(np.isfinite(values)):
        raise ValueError('nonfinite AP prediction')
    # A known-history forcing can change the estimated R/H. Report the applied
    # head's initial condition, rather than the zero-forcing design reference.
    _, initial = _prediction(c, _original_input(original), theta, head['alpha'])
    return values.tolist(), initial


def fit(cases, original, lambda_, alpha):
    """Source -> session -> sample equal weighted NNLS with frozen-prior ridge."""
    if len(cases) < 3 or any(c.get('role') != 'development' for c in cases) or len({c['id'] for c in cases}) != len(cases):
        raise ValueError('unique development sessions only; confirmation fit forbidden')
    if not math.isfinite(lambda_) or lambda_ < 0 or alpha not in ALPHAS:
        raise ValueError('invalid ridge/initial-state choice')
    theta0 = prior_coefficients(original)
    groups = Counter(group(c) for c in cases)
    matrices, targets = [], []
    for c in cases:
        baseline, matrix, _ = design(c, original, alpha)
        observed = np.asarray(c['ap'], dtype=float)
        if observed.shape != baseline.shape or not np.all(np.isfinite(observed)):
            raise ValueError('missing/nonfinite development AP targets')
        weight = 1/math.sqrt(len(groups)*groups[group(c)]*len(baseline))
        matrices.append(matrix*weight)
        targets.append((observed-baseline)*weight)
    matrix, target = np.vstack(matrices), np.concatenate(targets)
    norms = np.linalg.norm(matrix, axis=0)
    rank = int(np.linalg.matrix_rank(matrix))
    if rank != 5 or np.any(norms <= 0) or not np.all(np.isfinite(matrix)):
        raise ValueError('thermal correction inputs are not numerically identified')
    regularization = math.sqrt(lambda_)*np.diag(norms)
    augmented = np.vstack((matrix, regularization))
    augmented_target = np.r_[target, regularization@theta0]
    theta = v2.nnls(augmented, augmented_target)
    if not np.all(np.isfinite(theta)) or np.any(theta < 0):
        raise ValueError('invalid fitted thermal correction')
    return dict(version=VERSION, head='thermal', coefficients=theta.tolist(),
                alpha=float(alpha), lambda_=float(lambda_), beta=float(original['ap']['beta']),
                slow_tau_s=SLOW_TAU_S, initial_tau_s=INITIAL_TAU_S,
                original_coefficients=theta0.tolist(), regularization_column_norms=norms.tolist(),
                development_ids=[c['id'] for c in cases], source_groups=dict(groups),
                weighting='source equal, then session equal, then AP sample equal',
                numerical_rank=rank, scaled_condition=float(np.linalg.cond(matrix/norms)),
                weighted_training_rmse_c=float(np.sqrt(np.sum((matrix@theta-target)**2))),
                original_input_sha256=hashlib.sha256(_canonical(_original_input(original)).encode()).hexdigest(),
                default=False, strict_support=False, experiment_ready=False, accuracy_pass=None,
                thermal_service_feedback=None, slow_tau_identified=False,
                evidence='development-only empirical correction; physical thermal parameters not identified')
