"""Throttle model v2 — shared thermal state (v1 block + separate cooling tau) + LOAD-DEPENDENT gate controllers
(sim/스로틀모형_사전등록_v2.md §2). v0 (throttle.py, 80ca6c4) and v1 (throttle_v1.py, 3050e09) are untouched; this is a new module.
All shapes are [E]; parameter values come from d1sim/tools/fit_throttle_v2.py.

Thermal (one state for the device; the executing resource drives it with its power):
  tau_f dHf/dt = G_f dP - Hf ; tau_s dHs/dt = G_s dP - Hs ; tau_a dHa/dt = G_a[r] dP - Ha      (dP = P - P_idle, v1)
  cooling asymmetry (new, checklist ⑫): while a node is ABOVE its target G dP it relaxes with tau * c_x (c_x >= 1; c_x = 1 -> v1)
  SKIN = T_start + Hf + Hs ; AP = SKIN + A0 + Ha ; status = HAL map (record only, v1)
Load variable u_r(t) = fraction of executing seconds of resource r in the last 10 s (current second included, 1 s grid).
Gate controller (GPU per engine; form 'Lk' | 'Lb' | 'S'), driver sensor T in {SKIN, AP}:
  threshold thr(u) = T_on + kappa (1 - u)            (kappa = 0 for Lb and S)
  arm   : T >= thr(u) for d_on consecutive executing seconds
  release: Lk/Lb immediately when T < thr(u) - h ; S when T < T_on - h for d_off consecutive seconds ; Lb also forces release when u < theta
  depth (armed): ratio = 1 + D clip((T - T_d0)/W, 0, 1) ; released: ratio = 1 ; s = 1/ratio ; P = P_idle + (P0 - P_idle) s**alpha
NPU step controller: ratio = 1 + a1[arm1] + a2[arm2] + a3[arm3]; step i arms/releases like a gate with its own T_i (shared kappa, h, theta).
CPU4: v1 Controller unchanged (imported).
The scheduled resource's controller advances every second of its segment (arm hold counts executing seconds only); other
resources' controllers are frozen (v1 r2 rule). Transition windows (res None) freeze everything.
"""
from __future__ import annotations

import math
from collections import deque

from d1sim.throttle_v1 import Controller as ControllerV1, bins_ratio, onset_time_ref, status_of  # noqa: F401  (re-exported)

WINDOW_S = 10


class ThermalV2:
    def __init__(self, tp, T_start, A0):
        self.tp = tp
        self.T_start, self.A0 = T_start, A0
        self.Hf = self.Hs = self.Ha = 0.0

    @property
    def skin(self):
        return self.T_start + self.Hf + self.Hs

    @property
    def ap(self):
        return self.skin + self.A0 + self.Ha

    def advance(self, dt, P, res=None):
        tp = self.tp
        dP = max(0.0, P - tp['P_idle'])
        Ga = tp['G_a']
        G_a = Ga[res] if isinstance(Ga, dict) and res in Ga else (0.0 if isinstance(Ga, dict) else Ga)
        for name, G, tau, c in (('Hf', tp['G_f'], tp['tau_f'], tp.get('c_f', 1.0)), ('Hs', tp['G_s'], tp['tau_s'], tp.get('c_s', 1.0)),
                                ('Ha', G_a, tp['tau_a'], tp.get('c_a', 1.0))):
            H = getattr(self, name)
            target = G * dP
            te = tau * c if H > target else tau
            setattr(self, name, target + (H - target) * math.exp(-dt / te))

    def clone(self):
        c = ThermalV2(self.tp, self.T_start, self.A0)
        c.Hf, c.Hs, c.Ha = self.Hf, self.Hs, self.Ha
        return c


def _sensor(cp, th):
    return th.ap if cp['sensor'] == 'AP' else th.skin


class Gate:
    """One arm/release gate with load-dependent threshold. Used by GpuGateController and (x3) by NpuStepController."""

    def __init__(self, T_on):
        self.T_on = T_on
        self.armed, self.hold, self.off_hold = False, 0.0, 0.0

    def step(self, dt, T, cp, executing, u):
        form = cp['form']
        thr = self.T_on + (cp.get('kappa', 0.0) * (1.0 - u) if form == 'Lk' else 0.0)
        if form == 'Lb' and u < cp['theta']:
            self.armed, self.hold, self.off_hold = False, 0.0, 0.0
            return
        if self.armed:
            if T < thr - cp['h']:
                if form == 'S':
                    self.off_hold += dt
                    if self.off_hold >= cp.get('d_off', 10.0) - 1e-9:
                        self.armed, self.hold, self.off_hold = False, 0.0, 0.0
                else:
                    self.armed, self.hold, self.off_hold = False, 0.0, 0.0
            else:
                self.off_hold = 0.0
        else:
            if executing and T >= thr:
                self.hold += dt
                if self.hold >= cp['d_on'] - 1e-9:
                    self.armed = True
            elif not executing:
                pass                      # idle second inside the duty period: hold is kept, not reset [E]
            else:
                self.hold = 0.0

    def state(self):
        return (self.armed, self.hold, self.off_hold)

    def restore(self, st):
        self.armed, self.hold, self.off_hold = st


class GpuGateController:
    def __init__(self, cp):
        self.cp = cp
        self.gate = Gate(cp['T_on'])
        self.last_T = None

    @property
    def armed(self):
        return self.gate.armed

    def ratio_at(self, T):
        cp = self.cp
        if not self.gate.armed:
            return 1.0
        x = (T - cp['T_d0']) / cp['W'] if cp['W'] > 0 else (1.0 if T >= cp['T_d0'] else 0.0)
        return 1.0 + cp['D'] * min(1.0, max(0.0, x))

    @property
    def s(self):
        return 1.0 / self.ratio_at(self.last_T if self.last_T is not None else -1e9)

    def step(self, dt, th, executing=True, scheduled=True, u=1.0):
        T = _sensor(self.cp, th)
        self.last_T = T
        if not scheduled:
            return
        self.gate.step(dt, T, self.cp, executing, u)

    def clone(self):
        c = GpuGateController(self.cp)
        c.gate.restore(self.gate.state()); c.last_T = self.last_T
        return c


class NpuStepController:
    def __init__(self, cp):
        self.cp = cp
        self.gates = [Gate(cp[f'T{i}']) for i in (1, 2, 3)]

    @property
    def ratio(self):
        return 1.0 + sum(self.cp[f'a{i + 1}'] for i, g in enumerate(self.gates) if g.armed)

    @property
    def s(self):
        return 1.0 / self.ratio

    @property
    def level(self):
        return sum(1 for g in self.gates if g.armed)

    def step(self, dt, th, executing=True, scheduled=True, u=1.0):
        if not scheduled:
            return
        T = _sensor(self.cp, th)
        for g in self.gates:
            g.step(dt, T, self.cp, executing, u)

    def clone(self):
        c = NpuStepController(self.cp)
        for a, b in zip(c.gates, self.gates):
            a.restore(b.state())
        return c


class CpuV1Adapter:
    """v1 integrating controller for CPU4 (unchanged); same step signature as the v2 controllers."""

    def __init__(self, cp):
        self.c = ControllerV1(cp)

    @property
    def s(self):
        return self.c.s

    def step(self, dt, th, executing=True, scheduled=True, u=1.0):
        self.c.step(dt, th, executing)

    def clone(self):
        a = CpuV1Adapter(self.c.cp)
        a.c = self.c.clone()
        return a


def make_controller(res, params):
    cp = params['ctrl'][res]
    if res == 'NPU':
        return NpuStepController(cp)
    if res == 'CPU4' or cp.get('v1_controller'):
        return CpuV1Adapter(cp)
    return GpuGateController(cp)


def power_of(s, pp):
    return pp['P_idle'] + (pp['P0'] - pp['P_idle']) * s ** pp['alpha']


class DeviceV2:
    """params = dict(thermal, ctrl{res}, power{res}, L0{res}); ctrl entries carry form/sensor/kappa/theta/h/d_on(/d_off)."""

    def __init__(self, params, T_start, A0):
        self.p = params
        self.th = ThermalV2(params['thermal'], T_start, A0)
        self.ctrl = {r: make_controller(r, params) for r in params['ctrl']}
        self.win = {r: deque([0] * WINDOW_S, maxlen=WINDOW_S) for r in params['ctrl']}

    def u(self, res):
        return sum(self.win[res]) / float(WINDOW_S)

    def s(self, res):
        return self.ctrl[res].s

    def power(self, res, executing):
        if res is None or not executing:
            return self.p['thermal']['P_idle']
        return power_of(self.s(res), self.p['power'][res])

    def advance(self, dt, res, executing):
        P = self.power(res, executing)
        self.th.advance(dt, P, res if executing else None)
        for r in self.win:
            self.win[r].append(1 if (executing and r == res) else 0)
        for r, c in self.ctrl.items():
            c.step(dt, self.th, executing and r == res, scheduled=(r == res), u=self.u(r))
        return P

    def status(self):
        return status_of(self.th.skin)

    def clone(self):
        c = object.__new__(DeviceV2)
        c.p = self.p
        c.th = self.th.clone()
        c.ctrl = {r: x.clone() for r, x in self.ctrl.items()}
        c.win = {r: deque(list(w), maxlen=WINDOW_S) for r, w in self.win.items()}
        return c


def simulate(params, schedule, T_start, A0, dt=1.0):
    """schedule = [(seg_id, resource|None, flags_per_second|None|True, duration_s)] — same contract and row keys as v1
    (seg, t, res, ex, s, ratio, skin, ap, status, P) plus 'u' (load window of the scheduled resource before this second)."""
    dev = DeviceV2(params, T_start, A0)
    out = []
    for seg_id, res, flags, dur in schedule:
        n = int(round(dur / dt))
        for i in range(n):
            t = i * dt
            if res is None or flags is None:
                ex = False
            elif flags is True:
                ex = True
            else:
                k = int(t)
                ex = bool(flags[k]) if k < len(flags) else False
            # the row's ratio is the one the inference at this second sees: evaluate the controller on the CURRENT temperature
            if res and res != 'CPU4' and ex:
                c = dev.ctrl[res]
                if isinstance(c, GpuGateController):
                    c.last_T = _sensor(c.cp, dev.th)
            s = dev.s(res) if res else None
            row = dict(seg=seg_id, t=t, res=res, ex=ex, s=s, ratio=(1.0 / s) if (ex and s) else None,
                       skin=dev.th.skin, ap=dev.th.ap, status=dev.status(), u=(dev.u(res) if res else None))
            # advance: the scheduled resource is `res` even on idle duty seconds (controllers of `res` keep stepping)
            P = dev.power(res, ex)
            dev.th.advance(dt, P, res if ex else None)
            for r in dev.win:
                dev.win[r].append(1 if (ex and r == res) else 0)
            for r, c in dev.ctrl.items():
                c.step(dt, dev.th, ex and r == res, scheduled=(r == res), u=dev.u(r))
            row['P'] = P
            out.append(row)
    return out
