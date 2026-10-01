"""One opt-in posthoc lag candidate. No default/profile/support mutation."""
import math
from tools.d1_ap_idle_response import predict as baseline
from tools.d1_arrival_recorded_replay_analysis import state_key

VERSION = 'ap-workload-lag-posthoc-v1'


def advance(t, h, u, reference, beta, tau, dt):
    if not all(math.isfinite(x) for x in (t, h, u, reference, beta, tau, dt)) or beta <= 0 or tau <= 0 or dt < 0:
        raise ValueError('invalid lag step')
    eb, el = math.exp(-beta*dt), math.exp(-dt/tau)
    difference = beta-1/tau
    convolution = dt*eb if abs(difference) < 1e-10 else (el-eb)/difference
    return (reference+(t-reference)*eb+u*(1-eb)/beta+(h-u)*convolution,
            u+(h-u)*el)


def predict(segments, frozen, initial_ap_c, reference_c, query_s, tau_s):
    if not math.isfinite(tau_s) or tau_s < 0:
        raise ValueError('invalid tau')
    # Reuse all existing state, continuity, finite and time boundary checks.
    original = baseline(segments, frozen, initial_ap_c, reference_c, query_s)
    if tau_s == 0:
        return original
    beta, slopes = frozen['ap_cooling_rate_per_s'], frozen['ap_slope_at_30_c_per_s']
    if any(not math.isfinite(v) for v in slopes.values()):
        raise ValueError('nonfinite slope')
    queries, pos, result = sorted(query_s), 0, {}
    t, h = initial_ap_c, 0.
    for s in segments:
        start, end = float(s['start_s']), float(s['end_s'])
        u = slopes[state_key(s['state'])]-slopes['resident_idle']
        while pos < len(queries) and queries[pos] <= end+1e-9:
            q = queries[pos]
            result[round(q, 9)] = advance(t, h, u, reference_c, beta, tau_s, max(0., q-start))[0]
            pos += 1
        t, h = advance(t, h, u, reference_c, beta, tau_s, end-start)
    return result


def path(case, parameters, tau):
    p = case['inputs']
    values = predict(p['segments'], parameters, p['initial_ap_c'], p['reference_c'], p['query_s'], tau)
    return [values[round(q, 9)] for q in p['query_s']]


def fit(cases, parameters, grid):
    if not cases or not grid:
        raise ValueError('empty fit')
    losses = []
    for tau in grid:
        session_losses = []
        for c in cases:
            observed = c['observed_ap_c']
            predicted = path(c, parameters, tau)
            if not observed or len(observed) != len(predicted) or any(not math.isfinite(y) for y in observed):
                raise ValueError('missing fit target')
            session_losses.append(sum((a-b)**2 for a,b in zip(predicted, observed))/len(observed))
        losses.append({'tau_s': tau, 'mse_c2': sum(session_losses)/len(session_losses)})
    best = min(losses, key=lambda x: (x['mse_c2'], x['tau_s']))
    return best['tau_s'], losses


def idle_difference_interval(ea, eb, ia, ib, low, high):
    """Scenario arithmetic, NOT a calibrated statistical uncertainty interval."""
    if not all(math.isfinite(v) for v in (ea,eb,ia,ib,low,high)) or min(ia,ib)<0 or low>high:
        raise ValueError('invalid stress inputs')
    difference = ea-eb
    return {'diagnostic_difference_j': difference,
            'stress_low_j': difference+low*ia-high*ib,
            'stress_high_j': difference+high*ia-low*ib,
            'symmetric_break_even_idle_w': abs(difference)/(ia+ib) if ia+ib else None}
