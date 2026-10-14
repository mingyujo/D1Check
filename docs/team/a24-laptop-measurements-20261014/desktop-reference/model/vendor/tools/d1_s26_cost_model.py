"""Exploratory S26 costs. Observed events only; no scheduler or PPO import."""
from __future__ import annotations
import itertools
import math
from typing import Mapping
import numpy as np

ABI = 's26-cost-v1'
LANES = ('CPU', 'GPU', 'NPU')
SUPPORTED = {
    (('CPU', 'classification'),), (('CPU', 'detection'),),
    (('GPU', 'classification'),), (('NPU', 'classification'),),
    (('CPU', 'detection'), ('GPU', 'classification')),
    (('CPU', 'detection'), ('NPU', 'classification')),
}


def checked_busy(busy):
    keys = tuple(sorted(busy.items()))
    if keys and keys not in SUPPORTED:
        raise ValueError(f'unsupported occupancy: {keys}')
    return np.array([float(r in busy) for r in LANES])


def validate_profile(profile):
    if profile.get('abi') != ABI or profile.get('experiment_ready') is not False:
        raise ValueError('cost ABI/readiness mismatch')
    if profile.get('strict_eligible') is not False:
        raise ValueError('exploratory model cannot claim strict eligibility')
    power = profile['power']
    if power['tau_s'] not in (0, 5, 15):
        raise ValueError('unsupported power memory')
    for field, bound in ((power['coeff_w'], 20),):
        v = np.asarray(field, dtype=float)
        if v.shape != (3,) or not np.isfinite(v).all() or (v < 0).any() or (v > bound).any():
            raise ValueError('power coefficients')
    for sensor in ('AP', 'SKIN'):
        h = profile['thermal'][sensor]
        g = np.asarray(h['gains_c'], dtype=float)
        if h['beta_per_s'] not in (.01, .03, .06, .12, .25) or h['mix'] not in (1, .6):
            raise ValueError('thermal structure')
        if g.shape != (3,) or not np.isfinite(g).all() or (g < 0).any() or (g > 60).any():
            raise ValueError('thermal coefficients')
    return profile


def filtered_step(z, u, dt, tau):
    """Value at end and exact integral, piecewise constant observed input."""
    u = np.asarray(u, dtype=float)
    if tau == 0:
        return u.copy(), u * dt
    e = math.exp(-dt / tau)
    return u + (z-u)*e, u*dt + (z-u)*tau*(1-e)


class CostState:
    """advance -> release AVAILABLE owners -> begin observed dispatches.

    No future release time or request duration is accepted by this interface.
    Peaks include event boundaries and samples at most .5s apart.
    """
    def __init__(self, profile, baseline_w, reference_c, initial_c, start_s=0):
        self.profile = validate_profile(profile)
        if not math.isfinite(baseline_w) or baseline_w < 0:
            raise ValueError('invalid baseline')
        if not math.isfinite(start_s):
            raise ValueError('invalid clock')
        for name in ('AP', 'SKIN'):
            if not all(math.isfinite(d[name]) for d in (reference_c, initial_c)):
                raise ValueError('invalid initial temperature')
        self.baseline = baseline_w
        self.reference, self.initial = dict(reference_c), dict(initial_c)
        self.start = self.now = start_s
        self.owners = {}
        self.z = np.zeros(3)
        self.fast = {s: np.zeros(3) for s in ('AP', 'SKIN')}
        self.slow = {s: np.zeros(3) for s in ('AP', 'SKIN')}
        self.energy = 0.
        self.peak = dict(initial_c)

    def temperatures(self):
        out = {}
        for sensor, h in self.profile['thermal'].items():
            b, m = h['beta_per_s'], h['mix']
            residual = (self.initial[sensor]-self.reference[sensor])*math.exp(-b*(self.now-self.start))
            out[sensor] = self.reference[sensor]+residual+float(np.dot(h['gains_c'], m*self.fast[sensor]+(1-m)*self.slow[sensor]))
        return out

    def advance(self, now_s):
        if not math.isfinite(now_s) or now_s < self.now:
            raise ValueError('clock reversal/nonfinite')
        u = checked_busy({b: task for b, (rid, task) in self.owners.items()})
        while self.now < now_s:
            next_time = min(self.now+.5, now_s)
            dt = next_time-self.now
            self.z, integ = filtered_step(self.z, u, dt, self.profile['power']['tau_s'])
            self.energy += self.baseline*dt+float(np.dot(self.profile['power']['coeff_w'], integ))
            for sensor, h in self.profile['thermal'].items():
                self.fast[sensor], _ = filtered_step(self.fast[sensor], u, dt, 1/h['beta_per_s'])
                self.slow[sensor], _ = filtered_step(self.slow[sensor], u, dt, 10/h['beta_per_s'])
            self.now = next_time
            for sensor, temp in self.temperatures().items():
                self.peak[sensor] = max(self.peak[sensor], temp)
        return self.snapshot()

    def dispatch(self, request_id, task, backend):
        if backend in self.owners or any(request_id == rid for rid, _ in self.owners.values()):
            raise ValueError('occupied lane or duplicate request')
        proposed = {b: item[1] for b, item in self.owners.items()}
        proposed[backend] = task
        checked_busy(proposed)
        self.owners[backend] = (request_id, task)

    def available(self, request_id, backend):
        if backend not in self.owners or self.owners[backend][0] != request_id:
            raise ValueError('unmatched AVAILABLE')
        del self.owners[backend]

    def snapshot(self):
        return dict(time_s=self.now, energy_j=self.energy, temperatures_c=self.temperatures(),
                    peaks_c=dict(self.peak), power_w=self.baseline+float(np.dot(self.profile['power']['coeff_w'], self.z)),
                    status='exploratory_cost_model', strict_eligible=False, experiment_ready=False)


def ledger_events(rows, origin_ns=0):
    events = []
    ids = set()
    for i, row in enumerate(rows):
        rid = row.get('id', row.get('request_id', str(i)))
        if rid in ids:
            raise ValueError('duplicate request ledger')
        ids.add(rid)
        task = row.get('task', row.get('task_id'))
        b = row.get('backend', row.get('selected_backend'))
        a, z = row['dispatch_ns'], row['lane_available_ns']
        if not isinstance(a, (int, float)) or not isinstance(z, (int, float)) or not (math.isfinite(a) and math.isfinite(z)) or z <= a:
            raise ValueError('nonpositive/nonfinite lane interval')
        for field in ('execution_start_ns', 'output_ready_ns', 'persist_complete_ns', 'worker_release_ns'):
            if field in row and not a <= row[field] <= z:
                raise ValueError('phase outside occupancy')
        events.extend(((float(a-origin_ns)/1e9, 1, rid, task, b), (float(z-origin_ns)/1e9, 0, rid, task, b)))
    return sorted(events, key=lambda x: (x[0], x[1], x[2], x[4]))


def attach_costs(rows, profile, baseline_w, reference_c, initial_c, window_s=120, origin_ns=0):
    """Saved-ledger sidecar, does not modify rows or perform service execution."""
    if profile is None:
        return dict(energy_j=None, peaks_c=None, status='cost_model_unavailable', strict_eligible=False)
    if not 0 < window_s <= 120:
        raise ValueError('short service scope <=120s')
    state = CostState(profile, baseline_w, reference_c, initial_c)
    for t, release_first, rid, task, backend in ledger_events(rows, origin_ns):
        if t < 0:
            raise ValueError('ledger begins before cost origin')
        if t > window_s:
            break
        state.advance(t)
        if release_first == 0:
            state.available(rid, backend)
        else:
            state.dispatch(rid, task, backend)
    return state.advance(window_s)


def resource_intervals(rows, origin_ns):
    """Validate all physical states and return constant-input observed segments."""
    busy, intervals, last = {}, [], None
    for t, kind, rid, task, b in ledger_events(rows, origin_ns):
        if last is not None and t > last:
            intervals.append((last, t, checked_busy({k: v[1] for k, v in busy.items()})))
        if kind == 0:
            if b not in busy or busy[b][0] != rid:
                raise ValueError('bad resource release')
            del busy[b]
        else:
            if b in busy or any(v[0] == rid for v in busy.values()):
                raise ValueError('double occupancy')
            busy[b] = (rid, task)
            checked_busy({k: v[1] for k, v in busy.items()})
        last = t
    return intervals


def filter_features(intervals, times, tau):
    """Exact 3-lane filter values/integrals at requested times, start=0, z0=0."""
    ts = np.asarray(times, dtype=float)
    if ts.ndim != 1 or (ts < 0).any() or not np.isfinite(ts).all():
        raise ValueError('feature time axis')
    events = []
    for a, b, u in intervals:
        if b <= 0:
            continue
        if a < 0:
            raise ValueError('initial busy history missing')
        events.extend(((a, 1, u), (b, 0, np.zeros(3))))
    # Segments include idle and adjacent states: an end followed by start replaces u.
    events.sort(key=lambda x: (x[0], x[1]))
    order = np.argsort(ts, kind='stable')
    values, integrals = np.zeros((len(ts), 3)), np.zeros((len(ts), 3))
    z = np.zeros(3); accum = np.zeros(3); u = np.zeros(3); now = 0.; j = 0
    for oi in order:
        target = ts[oi]
        while j < len(events) and events[j][0] <= target:
            t, _, next_u = events[j]
            z, area = filtered_step(z, u, t-now, tau)
            accum += area; now = t; u = next_u; j += 1
        z, area = filtered_step(z, u, target-now, tau)
        accum += area; now = target
        values[oi] = z; integrals[oi] = accum
    return values, integrals


def bounded_fit(x, y, ridge, bound):
    """3-variable convex box ridge via exhaustive active faces (27), NumPy only."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    if x.shape != (len(y), 3) or not len(y) or not np.isfinite(x).all() or not np.isfinite(y).all():
        raise ValueError('invalid fit inputs')
    summed = x.sum(1)
    shared = float(np.clip(np.dot(summed, y)/max(np.dot(summed, summed), 1e-12), 0, bound))
    a = np.vstack((x, np.eye(3)*math.sqrt(ridge/3)))
    b = np.r_[y, np.full(3, shared)*math.sqrt(ridge/3)]
    best = None
    for faces in itertools.product((-1, 0, 1), repeat=3):
        free = [i for i, f in enumerate(faces) if f == 0]
        c = np.array([bound if f == 1 else 0. for f in faces])
        if free:
            c[free] = np.linalg.lstsq(a[:, free], b-a@c, rcond=None)[0]
        if (c < -1e-9).any() or (c > bound+1e-9).any():
            continue
        c = np.clip(c, 0, bound)
        loss = float(np.sum((a@c-b)**2))
        if best is None or loss < best[0]:
            best = loss, c
    return best[1], shared
