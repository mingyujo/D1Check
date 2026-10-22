"""Causal state-response cost observer. Historical electrical projection, not calibrated J.

Fits exclusive CC/CG/DC/CG+DC states and a causal first-order response. It never
uses a future realized overlap to choose a service pool. Unmeasured routes keep
an explicit transfer estimate and a sensitivity envelope, not a fitted discount.
"""
import math

STATES = ('classification_CPU', 'classification_GPU', 'detection_CPU',
          'classification_GPU+detection_CPU')
ANCHOR = (.5844294346219239, .4728843731804206, .712925901899471,
          .8878118931374972)
BASELINE = 1.204399931712509
SPEC = dict(schema='A24-causal-state-cost-v1', tau_candidates_s=[0., .9, 3., 10.],
            ridge=.01, bounds_W_proxy=[0., 4.],
            validation='leave-one-cohort-out; nested training-session leaveout tau selection',
            adoption='outer cohort-equal MAE at least 2% below same-baseline fixed anchor',
            unit='historical electrical projection W* / integrated J*; absolute calibration unknown',
            measured_J=None, temperature_feedback=False, new_device_measurements=0)


def state_key(state):
    parts = state.replace(':', '_').split('+')
    return '+'.join(sorted(parts))


def normalize(intervals):
    ans = []
    for row in intervals:
        a, b = float(row['start_s']), float(row['end_s'])
        if not math.isfinite(a+b) or b <= a:
            raise ValueError('Non-positive or nonfinite state interval')
        s = state_key(row['state'])
        if ans and a < ans[-1][1]-1e-8:
            raise ValueError('Overlapping exclusive states')
        ans.append((a, b, s))
    return ans


def exposures(intervals, windows, tau, states=STATES):
    """Exact mean filtered one-hot occupancy over each window; zero initial activity.

    The response is dx/dt=(u-x)/tau. State gaps are UNKNOWN, not implicit idle.
    Caller must provide a complete initial history and windows inside it.
    """
    seg = normalize(intervals)
    if not seg or tau < 0:
        raise ValueError('History and nonnegative tau required')
    boundaries = sorted(set([a for a,b in windows]+[b for a,b in windows]+
                            [a for a,b,s in seg]+[b for a,b,s in seg]))
    if any(b <= a or a < seg[0][0]-1e-8 or b > seg[-1][1]+1e-8 for a,b in windows):
        raise ValueError('Window beyond recorded state history')
    dim=len(states)
    x = [0.]*dim; cumulative = [0.]*dim; at = {}; j = 0
    for a,b in zip(boundaries,boundaries[1:]):
        if a < seg[0][0] or b > seg[-1][1]:
            continue
        while j+1 < len(seg) and a >= seg[j][1]-1e-9:
            j += 1
        if a < seg[j][0]-1e-8 or b > seg[j][1]+1e-8:
            raise ValueError('Missing state coverage')
        at[a] = list(cumulative)
        u = [float(seg[j][2] == s) for s in states]
        dt = b-a
        if tau == 0:
            integ = [v*dt for v in u]; x = u
        else:
            k = -math.expm1(-dt/tau)
            integ = [u[i]*dt+(x[i]-u[i])*tau*k for i in range(dim)]
            x = [u[i]+(x[i]-u[i])*(1-k) for i in range(dim)]
        cumulative = [cumulative[i]+integ[i] for i in range(dim)]
        at[b] = list(cumulative)
    return [[(at[b][i]-at[a][i])/(b-a) for i in range(dim)] for a,b in windows]


def fit(rows, ridge=SPEC['ridge'], prior=ANCHOR, upper=4.):
    """Session-equal bounded coordinate descent; prior only regularizes, never labels."""
    import numpy as np
    X = np.array([r['x'] for r in rows]); y = np.array([r['y'] for r in rows])
    counts = {}
    for r in rows: counts[r['session']] = counts.get(r['session'],0)+1
    w = np.array([1/counts[r['session']] for r in rows]); w /= w.sum()
    H = X.T@(w[:,None]*X)+ridge*np.eye(len(prior))
    v = X.T@(w*y)+ridge*np.array(prior)
    beta = np.array(prior)
    for _ in range(1000):
        old = beta.copy()
        for i in range(len(prior)):
            beta[i] = np.clip((v[i]-H[i]@beta+H[i,i]*beta[i])/H[i,i],0.,upper)
        if np.max(abs(beta-old)) < 1e-10: break
    return beta.tolist()


def predict(x, beta):
    return sum(a*b for a,b in zip(x,beta))


def observe(intervals, lo, hi, model, baseline_W_proxy=BASELINE):
    """Same-window baseline/increment plus route-coverage and transfer envelope.

    D_GPU and combinations without a matching measurement cannot silently inherit
    the measured CG_DC discount. Their nominal transfer is additive; lower/upper
    sensitivity limits are 0 and 2x additive (not a statistical confidence interval).
    """
    if hi <= lo or baseline_W_proxy <= 0: raise ValueError('Window/baseline')
    seg=normalize(intervals); known=[]; unsupported=[]
    adopted=model.get('adopted_for_qualified_states',False)
    beta=model['coefficients_W_proxy'] if adopted else ANCHOR
    tau=model['tau_s'] if adopted else 0.
    lookup=dict(zip(STATES,beta))
    lookup['detection_GPU']=.6013808404579677
    for a,b,s in seg:
        known.append(dict(start_s=a,end_s=b,state=s if s in STATES else 'idle'))
        d=max(0., min(b,hi)-max(a,lo))
        if not d: continue
        if s not in STATES and s not in ('idle','resident_idle'):
            power=sum(lookup.get(t,0.) for t in s.split('+'))
            if any(t not in lookup for t in s.split('+')): raise ValueError('Unknown route')
            unsupported.append(dict(state=s,seconds=d,additive_W_proxy=power))
    if not known: raise ValueError('No state coverage')
    x=exposures(known,[(lo,hi)],tau)[0]
    supported=predict(x,beta)*(hi-lo)
    transfer=sum(r['seconds']*r['additive_W_proxy'] for r in unsupported)
    # Unsupported-state causal dynamics are unidentified; no fitted tail is claimed.
    base=baseline_W_proxy*(hi-lo)
    return dict(baseline_J_proxy=base,supported_increment_J_proxy=supported,
                transferred_increment_J_proxy=transfer,increment_J_proxy=supported+transfer,
                total_J_proxy=base+supported+transfer,
                sensitivity_total_J_proxy=[base+supported,base+supported+2*transfer],
                sensitivity_is_CI=False,unsupported_states=unsupported,
                unsupported_seconds=sum(r['seconds'] for r in unsupported),
                measured_J=None,physical_energy_reduction_verified=False,
                fitted_candidate_adopted=adopted,effective_tau_s=tau,
                initial_activity='caller-provided recorded/simulated history; zero before its start',
                model_schema=SPEC['schema'])
