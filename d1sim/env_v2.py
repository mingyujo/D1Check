"""env_v2.py — the v0 event simulator (d1sim/env.py, untouched) driven by throttle model v2 (d1sim/throttle_v2.py).

ThermalV2Adapter exposes the same surface env.Sim/Thermal uses (T, skin, s, power, status, advance, clone) on top of
throttle_v2.DeviceV2, so policies, KPIs, conservation checks and the runner stay identical. Differences vs v0 Thermal:
  - one shared device state (coupling is always 'shared' in v2); T(r) = the resource's driver sensor (SKIN or AP)
  - controllers are the v2 load-dependent gates; the 10 s load window u is kept in TIME (sub-steps of 0.5 s) here
  - status = HAL map of SKIN (record + npumgr input), as in v2 / v1
Variant axes (sim/시뮬_사전등록_v2.md §2): theta_npu (0.3 | 0.75) x cooling ('v2' | 'c1' = v1 cooling); throttle False = S0 check.
"""
from __future__ import annotations

import json
import os
from collections import deque

from d1sim import env as env0
from d1sim import throttle_v2 as tv2
from d1sim.profile import RESOURCES

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
PROFILES = os.path.join(ROOT, 'd1sim', 'profiles')
WINDOW_S = float(tv2.WINDOW_S)
DEFAULT_VARIANT_V2 = dict(theta_npu=0.3, cooling='v2', throttle=True, cross_scale=1.0)


def v2_params(theta_npu=0.3, cooling='v2'):
    tp = json.load(open(os.path.join(PROFILES, 'throttle_v2_thermal.json'), encoding='utf-8'))
    tp = {k: tp[k] for k in ('tau_f', 'G_f', 'G_s', 'tau_s', 'tau_a', 'G_a', 'P_idle', 'c_f', 'c_s', 'c_a')}
    if cooling == 'c1':
        tp = dict(tp, c_f=1.0, c_s=1.0, c_a=1.0)
    ctrl, power, L0 = {}, {}, {}
    for res, fn in (('GPU', 'GPU_compiledmodel'), ('NPU', 'NPU'), ('CPU4', 'CPU4_interpreter')):
        d = json.load(open(os.path.join(PROFILES, f'throttle_v2_{fn}.json'), encoding='utf-8'))
        ctrl[res] = dict(d['ctrl']); power[res] = {k: d['power'][k] for k in ('P_idle', 'P0', 'alpha')}; L0[res] = d['L0_ms']
    if ctrl['NPU'].get('form') == 'Lb':
        ctrl['NPU'] = dict(ctrl['NPU'], theta=theta_npu)
    return dict(thermal=tp, ctrl=ctrl, power=power, L0=L0)


class ThermalV2Adapter:
    def __init__(self, profile, variant):
        self.v = variant
        self.params = v2_params(variant['theta_npu'], variant['cooling'])
        self.dev = tv2.DeviceV2(self.params, profile.t_start, -1.0)
        self.P_idle = self.params['thermal']['P_idle']
        self.win = {r: deque() for r in RESOURCES}      # (h, executing) over the last WINDOW_S seconds
        self.hal = profile.hal

    # ---- v0 surface ----
    def _u(self, r):
        tot = sum(h for h, _ in self.win[r])
        act = sum(h for h, e in self.win[r] if e)
        return act / WINDOW_S if tot > 0 else 0.0     # missing history counts as idle

    def T(self, r):
        c = self.dev.ctrl[r]
        sensor = getattr(c, 'cp', {}).get('sensor', 'SKIN') if hasattr(c, 'cp') else 'SKIN'
        return self.dev.th.ap if sensor == 'AP' else self.dev.th.skin

    def skin(self):
        return self.dev.th.skin

    def s(self, r):
        if not self.v['throttle']:
            return 1.0
        c = self.dev.ctrl[r]
        if isinstance(c, tv2.GpuGateController):
            c.last_T = tv2._sensor(c.cp, self.dev.th)
        return c.s

    def power(self, running, executing):
        if running is None or not executing:
            return self.P_idle
        return tv2.power_of(self.s(running), self.params['power'][running])

    def status(self):
        # v0 Record.status_s keeps {0, 1, 2}; HAL SEVERE (3, SKIN >= 45) is recorded as 2 here (npumgr only tests >= 2)
        return min(2, tv2.status_of(self.dev.th.skin))

    def advance(self, h, running, executing):
        P = self.power(running, executing)
        self.dev.th.advance(h, P, running if executing else None)
        for r in RESOURCES:
            w = self.win[r]
            w.append((h, bool(executing and r == running)))
            tot = sum(x for x, _ in w)
            while w and tot - w[0][0] >= WINDOW_S - 1e-9:
                tot -= w[0][0]; w.popleft()
        if not self.v['throttle']:
            return
        for r, c in self.dev.ctrl.items():
            c.step(h, self.dev.th, bool(executing and r == running), scheduled=(r == running), u=self._u(r))

    def clone(self):
        c = object.__new__(ThermalV2Adapter)
        c.__dict__.update(self.__dict__)
        c.dev = self.dev.clone()
        c.win = {r: deque(list(w)) for r, w in self.win.items()}
        return c


class SimV2(env0.Sim):
    """env.Sim with the v2 thermal/throttle adapter. Everything else (dispatch, record, KPIs) is inherited."""

    def __init__(self, profile, requests, variant=None, horizon=600.0):
        v = dict(DEFAULT_VARIANT_V2, **(variant or {}))
        super().__init__(profile, requests, dict(env0.DEFAULT_VARIANT, cross_scale=v['cross_scale'], throttle=v['throttle']), horizon)
        self.v2 = v
        self.th = ThermalV2Adapter(profile, v)
