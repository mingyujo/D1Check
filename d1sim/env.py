"""Event-driven simulator v0: arrivals / dispatch / completion, ONE job at a time (0911 §2.2 sequential default).

Thermal/throttle dynamics = d1sim/throttle.py form M-A2 (frozen 402acab), re-implemented per node here so the
drive can be any resource's power (shared coupling). tests/test_env.py checks that a continuous GPU job here gives
the same latency/power trajectory as throttle.simulate_continuous.

Structural variants (스로틀모형_v0.md §6), all in `variant`:
  npu_cpu_throttle : 'none' | 'scaled'      NPU/CPU4 throttle with the GPU form driven by their own power
  coupling         : 'independent' | 'shared'
  recovery         : 'same' | 'slow'        slow = cooling tau x3 and s recovers at most RECOVER_RATE per s
  status_model     : 'zero' | 'hal40'       hal40: device SKIN >= 40 -> MODERATE(2), >= 38 -> LIGHT(1)  [assumption]
  throttle         : True | False           False = no throttle at all (S0 sanity check)
  cross_scale      : float                  resource->resource switch = cross_scale * target init (placeholder)
  T_th_shift, tau_scale : sensitivity knobs on the throttle parameters
Policies see an immutable snapshot and a pure predictor; they never get a reference to the simulator.
"""
from __future__ import annotations

import copy
import math
from types import MappingProxyType

from d1sim.profile import RESOURCES
from d1sim.throttle import s_of

DT = 0.5                 # max thermal sub-step (s)
S_THROTTLED = 1 / 1.1    # "throttled" = latency >= +10 % (same threshold as the operational entry rule)
RECOVER_RATE = 0.01      # slow recovery: max increase of s per second [placeholder]
DEFAULT_VARIANT = dict(npu_cpu_throttle='none', coupling='independent', recovery='same', status_model='zero',
                       throttle=True, cross_scale=1.0, T_th_shift=0.0, tau_scale=1.0)


def throttle_params(profile, variant):
    """Per-resource parameter dicts (copies). GPU = frozen fit; NPU/CPU4 = GPU form with their own P0 (variant b)."""
    g = dict(profile.throttle_gpu)
    g['T_th'] = g['T_th'] + variant['T_th_shift']
    g['tau_f'] = g['tau_f'] * variant['tau_scale']
    g['tau_s'] = g['tau_s'] * variant['tau_scale']
    out = {}
    for r in RESOURCES:
        p = dict(g)
        if r != 'GPU':
            p['P0'] = profile.P_load[r]       # GPU keeps the fit P0 (same session as the fit)
        p['throttles'] = variant['throttle'] and (r == 'GPU' or variant['npu_cpu_throttle'] == 'scaled')
        out[r] = p
    return out


class Thermal:
    """Heat states. independent: one (Hf, Hs) per resource, driven by that resource's power.
    shared: one (Hf, Hs) driven by whichever resource runs. Device SKIN = t_start + sum of all H."""

    def __init__(self, profile, variant):
        self.v = variant
        self.p = throttle_params(profile, variant)
        self.t_start = profile.t_start
        self.P_idle = profile.P_idle
        keys = RESOURCES if variant['coupling'] == 'independent' else ('SoC',)
        self.H = {k: [0.0, 0.0] for k in keys}
        self.s_hold = {r: 1.0 for r in RESOURCES}   # rate-limited s (slow recovery)
        self.hal = profile.hal

    def key(self, r):
        return r if self.v['coupling'] == 'independent' else 'SoC'

    def T(self, r):
        h = self.H[self.key(r)]
        return self.t_start + h[0] + h[1]

    def skin(self):
        return self.t_start + sum(h[0] + h[1] for h in self.H.values())

    def s(self, r):
        p = self.p[r]
        if not p['throttles']:
            return 1.0
        s = s_of(self.T(r), p)
        return min(s, self.s_hold[r]) if self.v['recovery'] == 'slow' else s

    def power(self, running, executing):
        if running is None or not executing:
            return self.P_idle
        p = self.p[running]
        return p['P_idle'] + (p['P0'] - p['P_idle']) * self.s(running) ** p['alpha']

    def status(self):
        if self.v['status_model'] == 'zero':
            return 0
        sk = self.skin()
        return 2 if sk >= self.hal['MODERATE'] else 1 if sk >= self.hal['LIGHT'] else 0

    def advance(self, h, running, executing):
        """Exact exponential over h with the drive held constant (power at step start)."""
        s_before = {r: self.s(r) for r in RESOURCES}
        dP = self.power(running, executing) - self.P_idle
        for k, H in self.H.items():
            heating = executing and running is not None and self.key(running) == k
            p = self.p[running] if heating else self.p['GPU']
            drive = dP if heating else 0.0
            cool = 3.0 if (self.v['recovery'] == 'slow' and not heating) else 1.0
            tf, ts = p['tau_f'] * (1 if heating else cool), p['tau_s'] * (1 if heating else cool)
            H[0] = p['G_f'] * drive + (H[0] - p['G_f'] * drive) * math.exp(-h / tf)
            H[1] = p['G_s'] * drive + (H[1] - p['G_s'] * drive) * math.exp(-h / ts)
        if self.v['recovery'] == 'slow':
            for r in RESOURCES:
                self.s_hold[r] = min(1.0, s_before[r] + RECOVER_RATE * h)

    def clone(self):
        return copy.deepcopy(self)


class Record:
    """Everything the KPI / conservation layer reads. Built only by the simulator."""

    def __init__(self, horizon):
        self.horizon = horizon
        self.requests = {}          # id -> dict
        self.energy = []            # (t0, t1, power_w)
        self.busy = {r: [] for r in RESOURCES}   # (start, end) incl. switch
        self.throttle_s = {r: 0.0 for r in RESOURCES}
        self.exec_s = {r: 0.0 for r in RESOURCES}
        self.status_s = {0: 0.0, 1: 0.0, 2: 0.0}
        self.trace = []             # (t, skin, s_GPU, s_NPU, s_CPU4, status)
        self.energy_j = 0.0


def freeze(x):
    if isinstance(x, dict):
        return MappingProxyType({k: freeze(v) for k, v in x.items()})
    if isinstance(x, (list, tuple)):
        return tuple(freeze(v) for v in x)
    return x


class Sim:
    def __init__(self, profile, requests, variant=None, horizon=600.0):
        self.prof = profile
        self.v = dict(DEFAULT_VARIANT, **(variant or {}))
        self.horizon = horizon
        self.reqs = sorted((dict(r) for r in requests), key=lambda r: (r['arrival_s'], r['id']))
        self.th = Thermal(profile, self.v)
        self.rec = Record(horizon)
        self.t = 0.0
        self.queue = []
        self.loaded = None
        self.job = None     # dict(req, r, start, switch_end, work_left)
        self.wake = None

    # ---------- policy interface ----------
    def switch_cost(self, r):
        if self.loaded == r:
            return 0.0
        base = self.prof.init_s[r]
        return base if self.loaded is None else base * self.v['cross_scale']

    def snapshot(self):
        th = self.th.clone()
        prof, v, loaded = self.prof, dict(self.v), self.loaded

        def predict(resource, n_inf, t_delay=0.0):
            """Pure: completion time if a job of n_inf inferences is dispatched on `resource` after idling t_delay s.
            Returns dict(finish_s, s_end, T_end, skin_end). Uses a clone of the current thermal state."""
            sim = th.clone()
            t = 0.0
            while t_delay - t > 1e-12:
                h = min(DT, t_delay - t); sim.advance(h, None, False); t += h
            sw = prof.init_s[resource] if loaded is None else (0.0 if loaded == resource else prof.init_s[resource] * v['cross_scale'])
            tt = 0.0
            while sw - tt > 1e-12:
                h = min(DT, sw - tt); sim.advance(h, resource, False); tt += h
            work = n_inf * prof.L0_ms[resource] / 1000.0
            te = 0.0
            while work > 1e-12:
                s = sim.s(resource)
                h = min(DT, work / s)
                sim.advance(h, resource, True); work -= s * h; te += h
            return dict(finish_s=t_delay + sw + te, s_end=sim.s(resource), T_end=sim.T(resource), skin_end=sim.skin())

        return MappingProxyType(dict(
            t=self.t, loaded=self.loaded,
            queue=tuple(self.queue),   # items are frozen at arrival (MappingProxy)
            s=freeze({r: self.th.s(r) for r in RESOURCES}), T=freeze({r: self.th.T(r) for r in RESOURCES}),
            skin=self.th.skin(), status=self.th.status(),
            L0_ms=freeze(dict(prof.L0_ms)), init_s=freeze(dict(prof.init_s)),
            supported=freeze({r: prof.supported(r) for r in RESOURCES}),
            predict=predict))

    # ---------- core ----------
    def _log_req(self, req, **kw):
        self.rec.requests[req['id']].update(kw)

    def _dispatch(self, rid, r):
        req = next(q for q in self.queue if q['id'] == rid)
        if not self.prof.supported(r, req.get('min_tier', 'FP32')):
            raise ValueError(f'masked action: {r}')
        self.queue.remove(req)
        sw = self.switch_cost(r)
        self.loaded = r
        self.job = dict(req=req, r=r, start=self.t, switch_end=self.t + sw,
                        work_left=req['n_inf'] * self.prof.L0_ms[r] / 1000.0)
        self._log_req(req, status='running', resource=r, start=self.t, switch_s=sw)

    def _decide(self, policy):
        for _ in range(10_000):
            if self.job is not None or not self.queue:
                return
            act = policy.decide(self.snapshot())
            kind = act[0]
            if kind == 'dispatch':
                self._dispatch(act[1], act[2]); return
            if kind == 'reject':
                req = next(q for q in self.queue if q['id'] == act[1])
                self.queue.remove(req)
                self._log_req(req, status='rejected', completion=self.t); continue
            if kind == 'unload':
                self.loaded = None; continue
            if kind == 'wait':
                self.wake = act[1] if len(act) > 1 and act[1] is not None and act[1] > self.t + 1e-9 else None
                return
            raise ValueError(f'unknown action {act}')
        raise RuntimeError('policy loop did not terminate')

    def _advance_to(self, t_target):
        while t_target - self.t > 1e-12:
            h = min(DT, t_target - self.t)
            j = self.job
            r = j['r'] if j else None
            executing = False
            if j is not None:
                if self.t < j['switch_end'] - 1e-12:
                    h = min(h, j['switch_end'] - self.t)
                else:
                    executing = True
                    s = self.th.s(r)
                    h = min(h, j['work_left'] / s)
            P = self.th.power(r, executing)
            st_ = self.th.status()
            if executing:
                s = self.th.s(r)
                j['work_left'] -= s * h
                self.rec.exec_s[r] += h
                if s < S_THROTTLED:
                    self.rec.throttle_s[r] += h
            self.rec.status_s[st_] += h
            self.rec.energy.append((self.t, self.t + h, P))
            self.rec.energy_j += P * h
            self.th.advance(h, r, executing)
            self.t += h
            if not self.rec.trace or self.t - self.rec.trace[-1][0] >= 1.0 - 1e-9:
                self.rec.trace.append((self.t, self.th.skin(), self.th.s('GPU'), self.th.s('NPU'), self.th.s('CPU4'),
                                       self.th.status()))
            if j is not None and executing and j['work_left'] <= 1e-12:
                self._complete()
                return

    def _complete(self):
        j = self.job
        self.rec.busy[j['r']].append((j['start'], self.t))
        self._log_req(j['req'], status='done', completion=self.t, exec_s=self.t - j['switch_end'])
        self.job = None

    def run(self, policy):
        for r in self.reqs:
            self.rec.requests[r['id']] = dict(r, status='pending')
        ai = 0
        while True:
            # admit arrivals at current time
            while ai < len(self.reqs) and self.reqs[ai]['arrival_s'] <= self.t + 1e-12:
                self.queue.append(freeze(self.reqs[ai])); self.rec.requests[self.reqs[ai]['id']]['status'] = 'queued'; ai += 1
            if self.wake is not None and self.wake <= self.t + 1e-12:
                self.wake = None
            self._decide(policy)
            if self.t >= self.horizon - 1e-12:
                break
            nxt = [self.horizon]
            if ai < len(self.reqs):
                nxt.append(self.reqs[ai]['arrival_s'])
            if self.wake is not None:
                nxt.append(self.wake)
            if self.job is None and not nxt[1:] and not self.queue:
                nxt = [self.horizon]
            target = max(min(nxt), self.t)
            if self.job is not None:
                # run until completion or next external event, whichever first (_advance_to stops at completion)
                self._advance_to(min(target, self.horizon)) if target > self.t else None
                if target <= self.t + 1e-12 and self.job is not None:
                    # external event at now but job running: advance a sub-step so time moves
                    self._advance_to(min(self.t + DT, self.horizon))
            else:
                if target <= self.t + 1e-12:
                    if ai < len(self.reqs) or self.wake is not None:
                        continue
                    target = self.horizon
                self._advance_to(target)
        # horizon: running job and queue -> unfinished
        if self.job is not None:
            j = self.job
            self.rec.busy[j['r']].append((j['start'], self.t))
            self._log_req(j['req'], status='unfinished')
            self.job = None
        for q in self.queue:
            self._log_req(q, status='unfinished')
        for i in range(ai, len(self.reqs)):
            pass  # arrivals after horizon are not part of the episode
        self.rec.requests = {k: v for k, v in self.rec.requests.items() if v['arrival_s'] < self.horizon}
        return self.rec
