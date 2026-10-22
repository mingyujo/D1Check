"""Optimistic joint work/time/energy and thermal-deposition LP relaxations.

All actual schedules map into these continuous relaxations. Their solutions
are NOT schedules. The saved dual is repaired on finite variable boxes, so a
primal objective or failed search is never used as an optimality certificate.
"""
import math
import warnings
import numpy as np
from scipy.optimize import linprog
from scipy.sparse import coo_matrix

ROUTES = ('CPU', 'GPU')
MARGIN = 1e-4


def envelopes(physics, upper_c, step=.05):
    c = physics.c
    H = physics.shared
    modes = {}
    for route in ROUTES:
        cells = []
        lo = c.idle_c
        while lo < upper_c - 1e-10:
            hi = min(upper_c, lo + step)
            cells.append((lo, hi, physics.speed(lo, route, 1), physics.speed(hi, route, 1)))
            lo = hi
        modes[route] = cells
    maximum = H + sum(max(v for k, v in physics.solo.items() if k.endswith('_' + r)) - H for r in ROUTES) * (
        1 - c.leakage_fraction + c.leakage_fraction * math.exp(c.leakage_per_c * (upper_c - c.reference_c)))
    return dict(modes=modes, upper_c=upper_c, power_upper=maximum, shared=H, step=step)


def coefficients(physics, env, task, route):
    c = physics.c
    A = physics.solo[('classification' if task == 'C' else 'detection') + '_' + route] - physics.shared
    non = A + physics.shared / 2 - 1e-9
    values = []
    for lo, hi, fmax, fmin in env['modes'][route]:
        leak = math.exp(c.leakage_per_c * (lo - c.reference_c))
        values.append(A * (1 - c.leakage_fraction) * fmin ** 2 + (A * c.leakage_fraction * leak + physics.shared / 2) / fmax - 1e-9)
    return non, values


def quantiles(values, count):
    a = sorted(set(float(x) for x in values))
    return sorted(set(a[round(i * (len(a) - 1) / max(1, count - 1))] for i in range(count)))


class Problem:
    def __init__(self):
        self.lower = []; self.upper = []; self.cost = []; self.names = []
        self.eq = []; self.beq = []; self.ub = []; self.bub = []; self.tags = []

    def var(self, name, lo, hi, cost=0):
        i = len(self.cost); self.names.append(name)
        self.lower.append(lo); self.upper.append(hi); self.cost.append(cost)
        return i

    def equal(self, row, b):
        self.eq.append({k: v for k, v in row.items() if v}); self.beq.append(b)

    def atmost(self, row, b, tag):
        self.ub.append({k: v for k, v in row.items() if v}); self.bub.append(b); self.tags.append(tag)

    def matrix(self, rows):
        rr, cc, vv = [], [], []
        for i, row in enumerate(rows):
            for j, v in row.items(): rr.append(i); cc.append(j); vv.append(v)
        return coo_matrix((vv, (rr, cc)), shape=(len(rows), len(self.cost))).tocsr()

    def certificate(self, seconds=15):
        ae, au = self.matrix(self.eq), self.matrix(self.ub)
        with warnings.catch_warnings(record=True) as notices:
            warnings.simplefilter('always')
            result = linprog(self.cost, A_ub=au, b_ub=self.bub, A_eq=ae, b_eq=self.beq,
                             bounds=list(zip(self.lower, self.upper)), method='highs-ds',
                             options=dict(time_limit=seconds, dual_feasibility_tolerance=1e-8,
                                          primal_feasibility_tolerance=1e-8, threads=1))
        available = result.status == 0 and result.eqlin.marginals is not None
        ye = np.asarray(result.eqlin.marginals if available else np.zeros(len(self.eq)))
        yu = np.minimum(0., result.ineqlin.marginals) if available else np.zeros(len(self.ub))
        residual = np.asarray(self.cost) - ae.T @ ye - au.T @ yu
        terms = residual * np.where(residual >= 0, self.lower, self.upper)
        dual = float(np.dot(self.beq, ye) + np.dot(self.bub, yu) + sum(terms))
        margin = MARGIN + 1e-8 * (sum(abs(terms)) + sum(abs(np.asarray(self.beq) * ye)) + sum(abs(np.asarray(self.bub) * yu)))
        return dict(status=int(result.status), message=result.message, seconds_cap=seconds,warnings=[str(x.message) for x in notices],
                    primal_objective=float(result.fun) if result.fun is not None else None,
                    repaired_dual=dual, numerical_margin=margin, lower_bound=dual-margin,
                    dual_available=bool(available), x=result.x.tolist() if result.x is not None else None,
                    cost=self.cost, lower=self.lower, upper=self.upper,
                    equal_rows=[list(x.items()) for x in self.eq], equal_rhs=self.beq, equal_dual=ye.tolist(),
                    inequality_rows=[list(x.items()) for x in self.ub], inequality_rhs=self.bub, inequality_dual=yu.tolist())

    def error(self, x, include_counts=True):
        eq = self.matrix(self.eq) @ x - self.beq
        ub = self.matrix(self.ub) @ x - self.bub
        if not include_counts: ub = [v for v, tag in zip(ub, self.tags) if tag != 'count']
        return max(0., max(abs(eq), default=0.), max(ub, default=0.),
                   max(np.asarray(self.lower) - x), max(x - np.asarray(self.upper)))


def build(jobs, physics, env, reference, finish_limit, thermal_end=None):
    """Route fractions + aggregated execution work per task/route/temperature.

    Occupancy uses the FAST endpoint of each temperature cell; energy the
    independently favorable endpoints. Releases/deadline prefix constraints
    are necessary only. Fractions, preemption, independent cell temperatures,
    and independent heat deposition all FAVOR the optimizer.
    """
    p = Problem(); n = len(jobs); c = physics.c
    x, z, work, cold, prefix, nonwork, emin, premin = {}, {}, {}, {}, {}, {}, {}, {}
    for i, job in enumerate(jobs):
        release = job['queue_entry_ns'] / 1e9; due = job['deadline_ns'] / 1e9
        for route in ROUTES:
            v = [t / 1e9 for t in job['routes'][route]['stages_ns']]
            non, ee = coefficients(physics, env, job['task'], route)
            k = i, route
            cold[k] = sum(v); work[k] = v[1]; nonwork[k] = sum(v) - v[1]
            prefix[k] = sum(v[:2 if job['task'] == 'C' else 3])
            emin[k] = nonwork[k] * non + v[1] * min(ee)
            premin[k] = (prefix[k] - v[1]) * non + v[1] * min(ee)
            x[k] = p.var('x:%d:%s' % k, 0, 1, nonwork[k] * non if thermal_end is None else 0)
            z[k] = p.var('z:%d:%s' % k, 0, float(release + prefix[k] <= due + 1e-10))
            p.atmost({z[k]: 1, x[k]: -1}, 0, 'on-time route')
        p.equal({x[i, r]: 1 for r in ROUTES}, 1)
    T = p.var('finish', 35, finish_limit, c.baseline if thermal_end is None else 0)
    for i, job in enumerate(jobs):
        p.atmost({T: -1, **{x[i, r]: cold[i, r] for r in ROUTES}}, -job['queue_entry_ns']/1e9, 'individual completion')
    for urgent, count in [(False, reference['on_time']), (True, reference['urgent_on_time'])]:
        p.atmost({z[i, r]: -1 for i, j in enumerate(jobs) if not urgent or j['priority'] == 'U' for r in ROUTES}, -count, 'count')
    modes = {}
    for task in ('C', 'D'):
        for route in ROUTES:
            ids = [i for i, j in enumerate(jobs) if j['task'] == task]
            non, ee = coefficients(physics, env, task, route)
            maxwork = sum(work[i, route] for i in ids)
            for k, cell in enumerate(env['modes'][route]):
                modes[task, route, k] = p.var('w:%s:%s:%d' % (task, route, k), 0, maxwork, ee[k] if thermal_end is None else 0)
            p.equal({**{modes[task, route, k]: 1 for k in range(len(ee))},
                     **{x[i, route]: -work[i, route] for i in ids}}, 0)
    for route in ROUTES:
        p.atmost({T: -1, **{x[i, route]: nonwork[i, route] for i in range(n)},
                  **{idx: 1/env['modes'][route][k][2] for (task, r, k), idx in modes.items() if r == route}}, -35, 'coupled lane time')
    starts = quantiles([35, *[j['queue_entry_ns']/1e9 for j in jobs]], 24)
    ends = quantiles([j['deadline_ns']/1e9 for j in jobs], 24)
    for a in starts:
        for route in ROUTES:
            p.atmost({T: -1, **{x[i, route]: cold[i, route] for i, j in enumerate(jobs) if j['queue_entry_ns']/1e9 >= a-1e-10}}, -a, 'release capacity')
        for b in ends:
            if b <= a: continue
            ids = [i for i, j in enumerate(jobs) if j['queue_entry_ns']/1e9 >= a-1e-10 and j['deadline_ns']/1e9 <= b+1e-10]
            if ids:
                for route in ROUTES: p.atmost({z[i, route]: prefix[i, route] for i in ids}, b-a, 'deadline demand')
    deposit = []
    if thermal_end is not None:
        duration = thermal_end - 35
        bins = max(1, math.ceil(duration))
        edges = [35 + duration*k/bins for k in range(bins+1)]
        for a, b in zip(edges, edges[1:]):
            kernel = c.thermal_resistance * (-math.expm1(-(thermal_end-b)/c.thermal_tau_s)) / duration
            deposit.append(p.var('deposit:%d' % len(deposit), 0, env['power_upper']*(b-a), kernel))
        energy = {}
        for i, job in enumerate(jobs):
            for r in ROUTES:
                non, _ = coefficients(physics, env, job['task'], r)
                energy[x[i,r]] = nonwork[i,r]*non
        for (task,r,k), idx in modes.items(): energy[idx] = coefficients(physics, env, task, r)[1][k]
        p.atmost({**energy, **{idx: -1 for idx in deposit}}, 0, 'all work energy deposited')
        for cut in quantiles(edges[1:], 40):
            row = {z[i,r]: premin[i,r] for i,j in enumerate(jobs) if j['deadline_ns']/1e9 <= cut+1e-10 for r in ROUTES}
            row.update({idx: -1 for idx,b in zip(deposit, edges[1:]) if b <= cut+1e-10})
            p.atmost(row, 0, 'on-time prefix heat deposited')
    meta = dict(x=x, z=z, modes=modes, finish=T, deposit=deposit,
                constant_offset=-35*c.baseline if thermal_end is None else c.idle_c,
                thermal_end=thermal_end, finish_limit=finish_limit, kinds='energy' if thermal_end is None else 'temperature')
    return p, meta


def lift(jobs, result, physics, env, p, meta, end_ns):
    """Embed an actual trace in the relaxation; verifies its superset property."""
    value = np.zeros(len(p.cost)); byid = {j['request_id']: i for i,j in enumerate(jobs)}
    for q in result['requests']:
        i = byid[q['request_id']]; r = q['route']
        value[meta['x'][i,r]] = 1
        value[meta['z'][i,r]] = float(q['response_ns'] is not None and q['response_ns'] <= q['deadline_ns'])
    last = max(q['available_ns'] for q in result['requests'])
    value[meta['finish']] = last/1e9
    for tr in result['trace']:
        if tr['start_ns'] >= end_ns: break
        dt = (min(end_ns, tr['end_ns']) - tr['start_ns'])/1e9
        T = tr['state']['temperature_c']
        for a in tr['active']:
            if a['stage'] != 1: continue
            cells = env['modes'][a['route']]
            k = min(len(cells)-1, max(0, int((T-physics.c.idle_c)/env['step'])))
            value[meta['modes'][a['task'],a['route'],k]] += dt*tr['speeds'][a['route']]
        if meta['deposit']:
            duration = meta['thermal_end']-35; bins=len(meta['deposit']); width=duration/bins
            # Exact proportional energy split within a native transition for
            # active steps. Idle-tail integrals use the saved analytic state.
            start=tr['start_ns']/1e9; stop=min(end_ns,tr['end_ns'])/1e9
            k=max(0,min(bins-1,int((start-35)/width)))
            while start < stop-1e-12:
                b=min(stop,35+(k+1)*width); da=start-tr['start_ns']/1e9; db=b-tr['start_ns']/1e9
                if tr['active']: e=tr['increment']*(db-da)/tr['dt']
                else: e=physics.shared*tr['state']['shared_z']*physics.c.idle_tail_s*(math.exp(-da/physics.c.idle_tail_s)-math.exp(-db/physics.c.idle_tail_s))
                value[meta['deposit'][k]] += e; start=b; k=min(bins-1,k+1)
    # The native nanosecond engine rounds a phase end upward. Its final tick
    # can perform a fraction of a nanosecond of surplus work. Remove this
    # surplus in the relaxation: less occupied time/energy only helps it.
    for task in ('C','D'):
        for route in ROUTES:
            indices=[idx for (t,r,k),idx in meta['modes'].items() if t==task and r==route]
            target=sum(q['timing']['stages_ns'][1]/1e9 for q in result['requests'] if q['task']==task and q['route']==route)
            actual=sum(value[idx] for idx in indices)
            if actual:
                if target-actual>1e-7:raise ValueError('Incomplete work cannot lift into full-completion relaxation')
                for idx in indices:value[idx]*=target/actual
    return value
