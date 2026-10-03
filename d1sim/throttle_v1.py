"""Throttle model v1 — SHARED thermal state + per-resource controllers (sim/스로틀모형_사전등록_v1.md §2).

v0 (throttle.py, frozen 80ca6c4) is untouched; this is a new module. All shapes are [E] (general first-order thermal
dynamics + an integrating controller); parameter values come from d1sim/tools/fit_throttle_v1.py.

Thermal (one state for the whole device; whichever resource executes drives it with its power):
  tau_f dHf/dt = G_f (P - P_idle) - Hf          tau_f fixed 34.4 s [D]
  tau_s dHs/dt = G_s (P - P_idle) - Hs          slow node
  SKIN = T_start + Hf + Hs
  tau_a dHa/dt = G_a[r] (P - P_idle) - Ha       tau_a fixed 17.0 s [D]; G_a per executing resource r (r2: the AP sensor
  AP   = SKIN + A0 + Ha                          sits on the SoC and each IP heats it differently) ; A0 = (AP - SKIN) at start
Controller (GPU / CPU4; sensor = AP for form M-P, SKIN for M-S) — r2: the controller only advances (arms, integrates,
releases) while ITS resource executes (idle resources keep their state; M2r: GPU was not pre-throttled by NPU heating):
  arm when sensor >= T_on for d_on consecutive executing seconds; while armed du/dt = K (sensor - T_set), u in [0, u_max];
  release (u -> 0, disarm) when sensor < T_off.   s = 1 - u, latency = L0 / s, P = P_idle + (P0 - P_idle) s**alpha
NPU (two discrete steps + slow integral):
  ratio = 1 + a1 [arm1] + a2 [arm2] + min(K ∫_{arm2} (sensor - T2)+ dt, u_cap); s = 1 / ratio
  release variants: 'fast' (sensor < T_off -> 0) | 'skin' (SKIN < T_skin_rel -> 0)   -- untested, tonight's M1-NPU
Status (HAL map, record only): SKIN >= 45 -> 3, >= 42 -> 2, >= 40 -> 1 else 0 [P N1300].
"""
from __future__ import annotations

import math

STATUS_MAP = ((45.0, 3), (42.0, 2), (40.0, 1))


def status_of(skin):
    for th, v in STATUS_MAP:
        if skin >= th:
            return v
    return 0


class ThermalV1:
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
        G_a = tp['G_a'][res] if isinstance(tp['G_a'], dict) and res in tp['G_a'] else (0.0 if isinstance(tp['G_a'], dict) else tp['G_a'])
        for name, G, tau in (('Hf', tp['G_f'], tp['tau_f']), ('Hs', tp['G_s'], tp['tau_s']), ('Ha', G_a, tp['tau_a'])):
            H = getattr(self, name)
            setattr(self, name, G * dP + (H - G * dP) * math.exp(-dt / tau))

    def clone(self):
        c = ThermalV1(self.tp, self.T_start, self.A0)
        c.Hf, c.Hs, c.Ha = self.Hf, self.Hs, self.Ha
        return c


class Controller:
    """M-P / M-S integrating controller for GPU and CPU4."""

    def __init__(self, cp):
        self.cp = cp
        self.armed, self.hold, self.u = False, 0.0, 0.0

    def sensor(self, th):
        return th.ap if self.cp['sensor'] == 'AP' else th.skin

    @property
    def s(self):
        return 1.0 - self.u

    def step(self, dt, th, executing=True):
        if not executing:
            return
        cp, T = self.cp, self.sensor(th)
        if self.armed:
            if T < cp['T_off']:
                self.armed, self.hold, self.u = False, 0.0, 0.0
                return
            self.u = min(cp['u_max'], max(0.0, self.u + cp['K'] * (T - cp['T_set']) * dt))
        else:
            if T >= cp['T_on']:
                self.hold += dt
                if self.hold >= cp['d_on'] - 1e-9:
                    self.armed = True
            else:
                self.hold = 0.0

    def clone(self):
        c = Controller(self.cp)
        c.armed, c.hold, c.u = self.armed, self.hold, self.u
        return c


class NpuController:
    def __init__(self, cp):
        self.cp = cp
        self.hold1 = self.hold2 = 0.0
        self.arm1 = self.arm2 = False
        self.ui = 0.0

    def sensor(self, th):
        return th.ap if self.cp['sensor'] == 'AP' else th.skin

    @property
    def ratio(self):
        cp = self.cp
        return 1.0 + (cp['a1'] if self.arm1 else 0.0) + (cp['a2'] if self.arm2 else 0.0) + min(self.ui, cp['u_cap'])

    @property
    def s(self):
        return 1.0 / self.ratio

    def _release(self):
        self.hold1 = self.hold2 = 0.0
        self.arm1 = self.arm2 = False
        self.ui = 0.0

    def step(self, dt, th, executing=True):
        if not executing:
            return
        cp, T = self.cp, self.sensor(th)
        rel = cp.get('release', 'fast')
        if (self.arm1 or self.arm2) and ((rel == 'fast' and T < cp['T_off']) or (rel == 'skin' and th.skin < cp['T_skin_rel'])):
            self._release()
            return
        for i in (1, 2):
            if not getattr(self, f'arm{i}'):
                if T >= cp[f'T{i}']:
                    h = getattr(self, f'hold{i}') + dt
                    setattr(self, f'hold{i}', h)
                    if h >= cp['d_on'] - 1e-9:
                        setattr(self, f'arm{i}', True)
                else:
                    setattr(self, f'hold{i}', 0.0)
        if self.arm2:
            self.ui += cp['K'] * max(0.0, T - cp['T2']) * dt

    def clone(self):
        c = NpuController(self.cp)
        c.hold1, c.hold2, c.arm1, c.arm2, c.ui = self.hold1, self.hold2, self.arm1, self.arm2, self.ui
        return c


def make_controller(res, params):
    return NpuController(params['ctrl'][res]) if res == 'NPU' else Controller(params['ctrl'][res])


def power_of(s, pp):
    return pp['P_idle'] + (pp['P0'] - pp['P_idle']) * s ** pp['alpha']


class DeviceV1:
    """Thermal + one controller per resource. `params` = dict(thermal, ctrl{res}, power{res}, L0{res})."""

    def __init__(self, params, T_start, A0):
        self.p = params
        self.th = ThermalV1(params['thermal'], T_start, A0)
        self.ctrl = {r: make_controller(r, params) for r in params['ctrl']}

    def s(self, res):
        return self.ctrl[res].s

    def power(self, res, executing):
        if res is None or not executing:
            return self.p['thermal']['P_idle']
        return power_of(self.s(res), self.p['power'][res])

    def advance(self, dt, res, executing):
        P = self.power(res, executing)
        self.th.advance(dt, P, res if executing else None)
        for r, c in self.ctrl.items():
            c.step(dt, self.th, executing and r == res)
        return P

    def status(self):
        return status_of(self.th.skin)

    def clone(self):
        c = object.__new__(DeviceV1)
        c.p = self.p
        c.th = self.th.clone()
        c.ctrl = {r: x.clone() for r, x in self.ctrl.items()}
        return c


def simulate(params, schedule, T_start, A0, dt=1.0):
    """schedule = [(seg_id, resource|None, flags_per_second|None|True, duration_s)]. Returns 1 row per dt:
    seg, t (segment-relative), res, ex, s, ratio, P, skin, ap, status. Latency ratio defined only when executing."""
    dev = DeviceV1(params, T_start, A0)
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
            s = dev.s(res) if res else None
            row = dict(seg=seg_id, t=t, res=res, ex=ex, s=s, ratio=(1.0 / s) if (ex and s) else None,
                       skin=dev.th.skin, ap=dev.th.ap, status=dev.status())
            row['P'] = dev.advance(dt, res if ex else None, ex)
            out.append(row)
    return out


def bins_ratio(rows, seg_id, bin_s=10, key='ratio'):
    rr = [r for r in rows if r['seg'] == seg_id]
    if not rr:
        return []
    L = rr[-1]['t'] + (rr[1]['t'] - rr[0]['t'] if len(rr) > 1 else 1.0)
    out = []
    for k in range(int(L // bin_s)):
        v = sorted(r[key] for r in rr if k * bin_s <= r['t'] < (k + 1) * bin_s and r[key] is not None)
        out.append((k * bin_s, v[len(v) // 2] if v else None))
    return out


def onset_time_ref(bins, ref=1.0, rise=0.10, hold_s=30, bin_s=10):
    """Same rule as v0 throttle.onset_time_ref (1-1): first bin >= ref*(1+rise) at t>=30 held for the next 3 bins."""
    vals = [(t, m) for t, m in bins if m is not None]
    need = hold_s // bin_s
    for i, (t, m) in enumerate(vals):
        if t < 30:
            continue
        if m >= ref * (1 + rise) and i + need < len(vals) and all(vals[j][1] >= ref * (1 + rise) for j in range(i + 1, i + 1 + need)):
            return t
    return None
