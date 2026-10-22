"""Passive sensor response surrogate. API power is not certified physical watts."""
import math
import numpy as np


def advance(x, p0, p1, dt, tau):
    assert dt >= 0 and tau > 0
    if dt == 0:
        return float(x)
    d = dt / tau
    q = -math.expm1(-d)
    linear = (d / 2 - d*d / 6 + d**3 / 24) if d < 1e-5 else 1 - q / d
    return math.exp(-d) * x + q * p0 + linear * (p1 - p0)


def filtered(times, values, anchor, queries, tau):
    """Exact convolution with piecewise linear samples, no endpoint extension."""
    times, values, queries = map(lambda x: np.asarray(x, dtype=float), (times, values, queries))
    assert times[0] <= anchor <= queries[0] <= queries[-1] <= times[-1]
    assert np.all(np.diff(times) > 0) and np.all(np.diff(queries) > 0)
    knots = np.unique(np.r_[anchor, times[(times > anchor) & (times < queries[-1])], queries])
    p = np.interp(knots, times, values)
    result, x = {float(anchor): 0.}, 0.
    for j in range(1, len(knots)):
        x = advance(x, p[j-1], p[j], knots[j]-knots[j-1], tau)
        result[float(knots[j])] = x
    return np.asarray([result[float(t)] for t in queries])


def features(ep, tau):
    decay = np.exp(-(ep['times'] - ep['anchor_s']) / tau)
    base = ep['skin'] + (ep['anchor_AP'] - ep['skin']) * decay
    x = filtered(ep['power_times'], ep['power_values']-ep['baseline'], ep['anchor_s'], ep['times'], tau)
    return base, np.column_stack((1-decay, x))


def fit(train, tau):
    counts = {}
    for ep in train:
        counts[ep['cohort']] = counts.get(ep['cohort'], 0)+1
    H, b, data = np.zeros((2, 2)), np.zeros(2), []
    for ep in train:
        base, X = ep['features'][tau]
        y = ep['observed']-base
        w = 1 / (len(counts)*counts[ep['cohort']]*len(y))
        H += w * X.T @ X
        b += w * X.T @ y
        data.append((X, y, w))
    coef = np.linalg.lstsq(H, b, rcond=None)[0]
    if coef[1] < 0:
        coef = np.array([b[0]/H[0, 0], 0.])
    gradient = H @ coef - b
    kkt = max(abs(gradient[0]), abs(gradient[1]) if coef[1] > 1e-10 else max(0., -gradient[1]))
    assert kkt < 1e-7 and np.isfinite(coef).all()
    mse = sum(w * float(np.sum((X @ coef-y)**2)) for X, y, w in data)
    return dict(tau_s=tau, delta_C=float(coef[0]), gain_C_per_API_W=float(coef[1]), train_MSE=mse,
                KKT_residual=float(kkt), condition_number=float(np.linalg.cond(H)))


def predict(ep, model):
    base, X = ep['features'][model['tau_s']]
    return base + X @ np.array([model['delta_C'], model['gain_C_per_API_W']])
