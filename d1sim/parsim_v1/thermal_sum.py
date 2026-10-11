"""Thermal summation (registration §1-1 · §1-2 · §1-3) on top of the frozen v2.2 thermal block.

Shared nodes (v2.2 ThermalV21 arithmetic, k_b body initial condition): fast H_f, slow H_s (SKIN = T_base + H_f + H_s) and AP node H_a
(AP = SKIN + A0 + H_a). Each instant, every resource r in {CPU, GPU, NPU} is either executing or not (piecewise constant between events):

    dP_r   = kappa * g_r * (P_r(s_r) - P_idle)        if r executing, else 0        P_r = v2.2 power_of(s, power[r])
    H_f*   = G_f * sum_r dP_r      H_s* = G_s * sum_r dP_r      H_a* = sum_r G_a[r] * dP_r         (targets)
    H(t+h) = H* + (H(t) - H*) exp(-h / (tau c))   with c = c_x when H > H* (cooling asymmetry), else 1

With one resource executing and kappa = g = 1 this is exactly ThermalV21.advance (selftest checks it). The per-resource AP sum
(sum_r G_a[r] dP_r) is the P1l decision for "AP 단계의 자원별 G_a 를 동시 실행에서 합치는 식" (DECISIONS_P1l.md D1).
g_GPU, g_NPU = v2.2 g_m (EffNet classification); g_CPU = fitted on R3 only (fit.py). CPU power = CPU4 profile at s = 1.
Controllers: GPU / NPU = frozen v2.2 controllers (V21-Hθ r1) driven by the shared SKIN, load u = executing fraction of the last
10 s (time). CPU: no controller (D3) — CPU work is never slowed by the model.
"""
from __future__ import annotations

import math
from collections import deque

from d1sim import throttle_v2 as tv2
from d1sim import throttle_v21 as tv21
from d1sim import throttle_v22 as tv22

RES = ('CPU', 'GPU', 'NPU')
WINDOW_S = 10.0
MAX_H = 0.5


def load_v22():
    """v2.2 params (thermal + GPU/NPU controllers + power incl. CPU4) — NOT rescaled by with_model (g is applied here per resource)."""
    p = tv22.load_params('throttle_v22_')
    power = {'CPU': dict(p['power']['CPU4']), 'GPU': dict(p['power']['GPU']), 'NPU': dict(p['power']['NPU'])}
    return dict(thermal=p['thermal'], ctrl={'GPU': p['ctrl']['GPU'], 'NPU': p['ctrl']['NPU']}, power=power)


class ThermalSum(tv21.ThermalV21):
    """v2.2 shared thermal nodes with a multi-resource input."""

    def __init__(self, tp, skin0, a0, bat0, ha0=0.0):
        super().__init__(tp, skin0, a0, bat0)
        self.Ha = float(ha0)

    def advance_multi(self, h, dps):
        """dps = {res: dP_r (W, already kappa * g_r scaled)}; exact over h with inputs held."""
        tp = self.tp
        tot = sum(dps.values())
        Ga = tp['G_a']
        ha_t = sum(Ga.get(r if r != 'CPU' else 'CPU4', 0.0) * v for r, v in dps.items())
        for name, target, tau, c in (('Hf', tp['G_f'] * tot, tp['tau_f'], tp.get('c_f', 1.0)),
                                     ('Hs', tp['G_s'] * tot, tp['tau_s'], tp.get('c_s', 1.0)),
                                     ('Ha', ha_t, tp['tau_a'], tp.get('c_a', 1.0))):
            H = getattr(self, name)
            te = tau * c if H > target else tau
            setattr(self, name, target + (H - target) * math.exp(-h / te))

    def clone(self):
        c = object.__new__(ThermalSum)
        c.__dict__.update(self.__dict__)
        return c


class Device:
    """Shared thermal + GPU/NPU controllers + per-resource 10 s executing windows. advance(h, active) integrates exactly over h."""

    def __init__(self, params, g, kappa, skin0, ap0, bat0, a0):
        self.p = params
        self.g = dict(g)
        self.kappa = float(kappa)
        self.th = ThermalSum(params['thermal'], skin0, a0, bat0, ha0=(ap0 - skin0) - a0)
        self.ctrl = {r: tv21.make_controller(r, {'ctrl': params['ctrl']}) for r in ('GPU', 'NPU')}
        self.P_idle = params['thermal']['P_idle']
        self.win = {r: deque() for r in RES}
        self.wt = {r: 0.0 for r in RES}
        self.wa = {r: 0.0 for r in RES}

    # -- controller view ---------------------------------------------------------------------------------------
    def u(self, r):
        return self.wa[r] / WINDOW_S if self.wt[r] > 0 else 0.0

    def s(self, r):
        c = self.ctrl.get(r)
        if c is None:
            return 1.0
        if hasattr(c, 'last_T'):
            c.last_T = c.drv(self.th)
        return c.s

    def ratio(self, r):
        return 1.0 / self.s(r)

    def first_arm_temp(self, r):
        """First arm threshold (SKIN) of r's controller at the current load u (R7 thermal check); CPU -> None (no controller)."""
        c = self.ctrl.get(r)
        if c is None:
            return None
        cp = c.cp
        T = cp['T1'] if r == 'NPU' else cp['T_on']
        return T + cp.get('kappa', 0.0) * (1.0 - self.u(r))

    @property
    def skin(self):
        return self.th.skin

    @property
    def ap(self):
        return self.th.ap

    # -- integration -------------------------------------------------------------------------------------------
    def power(self, r):
        return tv2.power_of(self.s(r), self.p['power'][r])

    def dps(self, active):
        return {r: self.kappa * self.g[r] * max(0.0, self.power(r) - self.P_idle) for r in active}

    def advance(self, h, active):
        """active = set of executing resources during h (h <= MAX_H recommended). Returns total input power (W)."""
        d = self.dps(active)
        self.th.advance_multi(h, d)
        for r in RES:
            ex = r in active
            self.win[r].append((h, ex))
            self.wt[r] += h
            if ex:
                self.wa[r] += h
            while self.win[r] and self.wt[r] - self.win[r][0][0] >= WINDOW_S - 1e-9:
                hh, e = self.win[r].popleft()
                self.wt[r] -= hh
                if e:
                    self.wa[r] -= hh
        for r, c in self.ctrl.items():
            c.step(h, self.th, r in active, scheduled=True, u=self.u(r))
        return self.P_idle + sum(d.values())

    def clone(self):
        c = object.__new__(Device)
        c.__dict__.update(self.__dict__)
        c.th = self.th.clone()
        c.ctrl = {r: cc.clone() for r, cc in self.ctrl.items()}
        c.win = {r: deque(q) for r, q in self.win.items()}
        c.wt = dict(self.wt)
        c.wa = dict(self.wa)
        return c


def selftest():
    ok = True
    p = load_v22()
    tp = p['thermal']
    # 1) one resource, kappa = g = 1 == ThermalV21.advance (same P)
    for r, rr in (('GPU', 'GPU'), ('NPU', 'NPU'), ('CPU', 'CPU4')):
        a = ThermalSum(tp, 30.5, -1.0, 28.35)
        b = tv21.ThermalV21(tp, 30.5, -1.0, 28.35)
        P = tv2.power_of(1.0, p['power'][r])
        for k in range(200):
            act = (k % 7) < 4
            a.advance_multi(0.5, {r: max(0.0, P - tp['P_idle'])} if act else {})
            b.advance(0.5, P if act else tp['P_idle'], rr if act else None)
        d = max(abs(a.skin - b.skin), abs(a.ap - b.ap))
        print(f'  single-resource {r}: |diff| {d:.2e}')
        ok &= d < 1e-9
    # 2) superposition: two resources targets add
    a = ThermalSum(tp, 30.5, -1.0, 28.35)
    a.advance_multi(1e6, {'CPU': 2.0, 'GPU': 1.0})
    exp_ap = tp['G_a']['CPU4'] * 2.0 + tp['G_a']['GPU'] * 1.0
    d = abs(a.Ha - exp_ap) + abs(a.Hf - tp['G_f'] * 3.0)
    print(f'  steady-state superposition |diff| {d:.2e}')
    ok &= d < 1e-6
    # 3) Device: idle keeps state; ha0 decays
    dev = Device(p, {'CPU': 1.0, 'GPU': 0.9113, 'NPU': 0.9734}, 1.0, 30.0, 32.0, 28.0, -1.0)
    ap0 = dev.ap
    for _ in range(600):
        dev.advance(0.5, set())
    print(f'  idle 300 s: AP {ap0:.3f} -> {dev.ap:.3f} (A0 -1.0 -> SKIN-1) · GPU ratio {dev.ratio("GPU"):.3f}')
    ok &= abs(ap0 - 32.0) < 1e-9 and dev.ap < ap0 and abs(dev.ratio('GPU') - 1.0) < 1e-12
    print('thermal_sum selftest', 'PASS' if ok else 'FAIL')
    return ok


if __name__ == '__main__':
    import sys
    sys.exit(0 if selftest() else 1)
