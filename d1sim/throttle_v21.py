"""Throttle model v2.1 — v2 thermal block + BODY INITIAL CONDITION (k_b) + two new controller forms
(sim/스로틀모형_사전등록_v21.md §2). v0/v1/v2 modules are untouched; this module imports throttle_v2 and only adds.
All shapes are [E]; parameter values come from d1sim/tools/fit_throttle_v21.py.

Body initial condition (prereg v2.1 §2.0, checklist ⑳):
  z = (SKIN0 - BAT0) - d_ref ;  Hs(0) = k_b z ;  T_base = SKIN0 - k_b z   (so SKIN(0) = SKIN0; a cold body (z > 0) heats slower)
  BAT0 None -> z = 0 (v2 behaviour).  Everything else = throttle_v2.ThermalV2.
Forms (ctrl 'form'):
  'Ht' (V21-Htheta): threshold thr(u) = T + kappa (1 - u); arm T_drv >= thr(u) for d_on executing seconds;
        release immediately when u <= theta_low OR T_drv < thr(u) - h.  NPU: 3 steps (shared kappa_N, h). GPU: gate + static depth map.
  'F'  (V21-F): per-resource fast node  tau_F dF/dt = g_F (P - P_idle)[r executing] - F  (F evolves every second, all resources);
        T_drv = base sensor + F ; arm T_drv >= T_i for d_on ; release T_drv < T_i - h (immediately). No u, no theta.
  'Lk' | 'Lb' | 'S' are delegated to throttle_v2 unchanged.
"""
from __future__ import annotations

import math
from collections import deque

from d1sim import throttle_v2 as tv2
from d1sim.throttle_v1 import bins_ratio, onset_time_ref, status_of  # noqa: F401  (re-exported)

WINDOW_S = tv2.WINDOW_S


class ThermalV21(tv2.ThermalV2):
    def __init__(self, tp, T_start, A0, B0=None):
        super().__init__(tp, T_start, A0)
        self.z = 0.0
        kb = tp.get('k_b', 0.0)
        if B0 is not None and kb:
            self.z = (T_start - B0) - tp.get('d_ref', 0.0)
            self.Hs = kb * self.z
            self.T_start = T_start - self.Hs

    def advance(self, dt, P, res=None):
        tp = self.tp
        if not (isinstance(tp['G_f'], dict) or isinstance(tp['G_s'], dict)):
            return super().advance(dt, P, res)
        # r2 (ledger V21-Hθ-r2): per-resource fast / slow gains (dict) — same arithmetic as ThermalV2.advance otherwise
        dP = max(0.0, P - tp['P_idle'])

        def g(G):
            return (G.get(res, 0.0) if res is not None else 0.0) if isinstance(G, dict) else G
        for name, G, tau, c in (('Hf', g(tp['G_f']), tp['tau_f'], tp.get('c_f', 1.0)), ('Hs', g(tp['G_s']), tp['tau_s'], tp.get('c_s', 1.0)),
                                ('Ha', g(tp['G_a']), tp['tau_a'], tp.get('c_a', 1.0))):
            H = getattr(self, name)
            target = G * dP
            te = tau * c if H > target else tau
            setattr(self, name, target + (H - target) * math.exp(-dt / te))

    def clone(self):
        c = ThermalV21(self.tp, self.T_start, self.A0)
        c.Hf, c.Hs, c.Ha, c.z = self.Hf, self.Hs, self.Ha, self.z
        return c


def _base(cp, th):
    return th.ap if cp['sensor'] == 'AP' else th.skin


class GateHt:
    """V21-Htheta gate: load-shifted threshold (arm + release) + forced release at u <= theta_low."""

    def __init__(self, T_on):
        self.T_on = T_on
        self.armed, self.hold = False, 0.0

    def step(self, dt, T, cp, executing, u):
        thr = self.T_on + cp.get('kappa', 0.0) * (1.0 - u)
        if u <= cp['theta_low'] + 1e-12:
            self.armed, self.hold = False, 0.0
            return
        if self.armed:
            if T < thr - cp['h']:
                self.armed, self.hold = False, 0.0
        else:
            if executing and T >= thr:
                self.hold += dt
                if self.hold >= cp['d_on'] - 1e-9:
                    self.armed = True
            elif executing:
                self.hold = 0.0

    def state(self):
        return (self.armed, self.hold)

    def restore(self, st):
        self.armed, self.hold = st


class GateF:
    """V21-F gate on T_drv = base + F (no load term)."""

    def __init__(self, T_on):
        self.T_on = T_on
        self.armed, self.hold = False, 0.0

    def step(self, dt, T, cp, executing, u):
        if self.armed:
            if T < self.T_on - cp['h']:
                self.armed, self.hold = False, 0.0
        else:
            if executing and T >= self.T_on:
                self.hold += dt
                if self.hold >= cp['d_on'] - 1e-9:
                    self.armed = True
            elif executing:
                self.hold = 0.0

    def state(self):
        return (self.armed, self.hold)

    def restore(self, st):
        self.armed, self.hold = st


class _FastNode:
    def __init__(self):
        self.F = 0.0

    def advance(self, dt, cp, dP, executing):
        target = cp.get('g_F', 0.0) * dP if executing else 0.0
        self.F = target + (self.F - target) * math.exp(-dt / cp['tau_F'])


class GpuV21:
    def __init__(self, cp):
        self.cp = cp
        self.gate = (GateF if cp['form'] == 'F' else GateHt)(cp['T_on'])
        self.fast = _FastNode()
        self.last_T = None

    @property
    def armed(self):
        return self.gate.armed

    def drv(self, th):
        return _base(self.cp, th) + (self.fast.F if self.cp['form'] == 'F' else 0.0)

    def ratio_at(self, T):
        cp = self.cp
        if not self.gate.armed:
            return 1.0
        x = (T - cp['T_on']) / cp['W'] if cp['W'] > 0 else (1.0 if T >= cp['T_on'] else 0.0)
        return 1.0 + cp['D'] * min(1.0, max(0.0, x))

    @property
    def s(self):
        return 1.0 / self.ratio_at(self.last_T if self.last_T is not None else -1e9)

    def fast_advance(self, dt, dP, executing):
        if self.cp['form'] == 'F':
            self.fast.advance(dt, self.cp, dP, executing)

    def step(self, dt, th, executing=True, scheduled=True, u=1.0):
        T = self.drv(th)
        self.last_T = T
        if not scheduled:
            return
        self.gate.step(dt, T, self.cp, executing, u)

    def clone(self):
        c = GpuV21(self.cp)
        c.gate.restore(self.gate.state()); c.fast.F = self.fast.F; c.last_T = self.last_T
        return c


class NpuV21:
    def __init__(self, cp):
        self.cp = cp
        G = GateF if cp['form'] == 'F' else GateHt
        self.gates = [G(cp[f'T{i}']) for i in (1, 2, 3)]
        self.fast = _FastNode()

    @property
    def ratio(self):
        return 1.0 + sum(self.cp[f'a{i + 1}'] for i, g in enumerate(self.gates) if g.armed)

    @property
    def s(self):
        return 1.0 / self.ratio

    @property
    def level(self):
        return sum(1 for g in self.gates if g.armed)

    def drv(self, th):
        return _base(self.cp, th) + (self.fast.F if self.cp['form'] == 'F' else 0.0)

    def fast_advance(self, dt, dP, executing):
        if self.cp['form'] == 'F':
            self.fast.advance(dt, self.cp, dP, executing)

    def step(self, dt, th, executing=True, scheduled=True, u=1.0):
        if not scheduled:
            return
        T = self.drv(th)
        for g in self.gates:
            g.step(dt, T, self.cp, executing, u)

    def clone(self):
        c = NpuV21(self.cp)
        for a, b in zip(c.gates, self.gates):
            a.restore(b.state())
        c.fast.F = self.fast.F
        return c


def make_controller(res, params):
    cp = params['ctrl'][res]
    if res == 'CPU4' or cp.get('v1_controller'):
        return tv2.CpuV1Adapter(cp)
    if cp.get('form') in ('Ht', 'F'):
        return NpuV21(cp) if res == 'NPU' else GpuV21(cp)
    return tv2.make_controller(res, params)


def simulate(params, schedule, T_start, A0, B0=None, dt=1.0):
    """Same contract and row keys as throttle_v2.simulate (+ 'drv' = driver temperature of the scheduled resource).
    B0 = BAT at start (body initial condition; None -> v2 thermal behaviour)."""
    th = ThermalV21(params['thermal'], T_start, A0, B0)
    ctrl = {r: make_controller(r, params) for r in params['ctrl']}
    win = {r: deque([0] * WINDOW_S, maxlen=WINDOW_S) for r in params['ctrl']}
    P_idle = params['thermal']['P_idle']

    def u(r):
        return sum(win[r]) / float(WINDOW_S)

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
            c = ctrl.get(res) if res else None
            if c is not None and res != 'CPU4' and ex and hasattr(c, 'last_T'):
                c.last_T = c.drv(th) if hasattr(c, 'drv') else tv2._sensor(c.cp, th)
            s = c.s if c is not None else None
            row = dict(seg=seg_id, t=t, res=res, ex=ex, s=s, ratio=(1.0 / s) if (ex and s) else None,
                       skin=th.skin, ap=th.ap, status=status_of(th.skin), u=(u(res) if res else None),
                       drv=(c.drv(th) if (c is not None and hasattr(c, 'drv')) else None))
            P = P_idle if (res is None or not ex) else tv2.power_of(c.s, params['power'][res])
            th.advance(dt, P, res if ex else None)
            dP = max(0.0, P - P_idle)
            for r in win:
                win[r].append(1 if (ex and r == res) else 0)
            for r, cc in ctrl.items():
                if hasattr(cc, 'fast_advance'):
                    cc.fast_advance(dt, dP, ex and r == res)
            for r, cc in ctrl.items():
                cc.step(dt, th, ex and r == res, scheduled=(r == res), u=u(r))
            row['P'] = P
            out.append(row)
    return out


def thermal_series(tp, P, res, T_start, A0, B0=None):
    """Fast open-loop thermal (measured power in) — identical arithmetic to ThermalV21.advance; returns (skin[], ap[]) BEFORE each step."""
    th = ThermalV21(tp, T_start, A0, B0)
    tau_f, tau_s, tau_a = tp['tau_f'], tp['tau_s'], tp['tau_a']
    cf, cs, ca = tp.get('c_f', 1.0), tp.get('c_s', 1.0), tp.get('c_a', 1.0)
    Gf, Gs, Ga, Pi = tp['G_f'], tp['G_s'], tp['G_a'], tp['P_idle']
    Hf, Hs, Ha = th.Hf, th.Hs, th.Ha
    T0 = th.T_start
    ef, efc = math.exp(-1.0 / tau_f), math.exp(-1.0 / (tau_f * cf))
    es, esc = math.exp(-1.0 / tau_s), math.exp(-1.0 / (tau_s * cs))
    ea, eac = math.exp(-1.0 / tau_a), math.exp(-1.0 / (tau_a * ca))
    sk, ap = [], []
    for p, r in zip(P, res):
        s = T0 + Hf + Hs
        sk.append(s); ap.append(s + A0 + Ha)
        dP = p - Pi
        if dP < 0:
            dP = 0.0
        ga = (Ga.get(r, 0.0) if isinstance(Ga, dict) else Ga) if r is not None else (0.0 if isinstance(Ga, dict) else Ga)
        gf = (Gf.get(r, 0.0) if r is not None else 0.0) if isinstance(Gf, dict) else Gf
        gs = (Gs.get(r, 0.0) if r is not None else 0.0) if isinstance(Gs, dict) else Gs
        tg = gf * dP; Hf = tg + (Hf - tg) * (efc if Hf > tg else ef)
        tg = gs * dP; Hs = tg + (Hs - tg) * (esc if Hs > tg else es)
        tg = ga * dP; Ha = tg + (Ha - tg) * (eac if Ha > tg else ea)
    return sk, ap
