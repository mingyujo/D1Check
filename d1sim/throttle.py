"""Throttle model v0: power-driven thermal state -> throttle factor s -> latency / power.

Form (sim/스로틀모형_사전등록_v0.md §2, all [E] general-knowledge shapes):
  s        = clip(1 - k * (T_sensor - T_th), s_min, 1)
  latency  = L0 / s
  power    = P_idle + (P0 - P_idle) * s**alpha
  tau_f dHf/dt = G_f * (P - P_idle) - Hf         (fast node)
  tau_s dHs/dt = G_s * (P - P_idle) - Hs         (slow node; nodes=1 -> Hs == 0)
  T_sensor = T_start + Hf + Hs
Parameters come from a dict so the simulator (env.py) and the fit (tools/fit_throttle.py) share one code path.
"""
from __future__ import annotations

import math


def s_of(T, p):
    return min(1.0, max(p['s_min'], 1.0 - p['k'] * (T - p['T_th'])))


def power_of(s, p):
    return p['P_idle'] + (p['P0'] - p['P_idle']) * s ** p['alpha']


class ThrottleState:
    """Mutable thermal state of one resource. `advance(dt, busy)` integrates exactly per node over dt with
    power held at the value implied by s at the step start (dt should be <= 1 s)."""

    def __init__(self, p, T_start):
        self.p = p
        self.T_start = T_start
        self.Hf = 0.0
        self.Hs = 0.0

    @property
    def T(self):
        return self.T_start + self.Hf + self.Hs

    @property
    def s(self):
        return s_of(self.T, self.p)

    def power(self, busy):
        return power_of(self.s, self.p) if busy else self.p['P_idle']

    def advance(self, dt, busy):
        p = self.p
        dP = self.power(busy) - p['P_idle']
        tf = p['tau_f'] if busy else p.get('tau_f_cool', p['tau_f'])
        self.Hf = p['G_f'] * dP + (self.Hf - p['G_f'] * dP) * math.exp(-dt / tf)
        if p.get('nodes', 1) == 2:
            ts = p['tau_s'] if busy else p.get('tau_s_cool', p['tau_s'])
            self.Hs = p['G_s'] * dP + (self.Hs - p['G_s'] * dP) * math.exp(-dt / ts)


def simulate_continuous(p, T_start, duration_s, dt=1.0):
    """Continuous busy load (duty 100). Returns per-dt rows: t, s, latency_ms, power_w, T."""
    st = ThrottleState(p, T_start)
    out = []
    t = 0.0
    while t < duration_s - 1e-9:
        s = st.s
        out.append(dict(t=t, s=s, latency_ms=p['L0'] / s, power_w=power_of(s, p), T=st.T))
        st.advance(dt, True)
        t += dt
    return out


def onset_time(lat10, rise=0.10, hold_s=30, bin_s=10):
    """Operational throttle entry (프롬프트_밤측정_0928.md 1-1): first 10 s bin whose median is >= +10 % over the
    first-30 s median, staying >= +10 % for the following hold_s. `lat10` = list of (t_bin_start, median).
    First-30 s reference = median of the first 3 bin medians (exact for model, approx for measured -> caller
    passes an exact reference via `ref` when available). Returns t or None."""
    return onset_time_ref(lat10, None, rise, hold_s, bin_s)


def onset_time_ref(lat10, ref, rise=0.10, hold_s=30, bin_s=10):
    if ref is None:
        first = sorted(m for t, m in lat10 if t < 30)
        ref = first[len(first) // 2]
    need = hold_s // bin_s
    vals = [(t, m) for t, m in lat10]
    for i, (t, m) in enumerate(vals):
        if t < 30:
            continue
        if m >= ref * (1 + rise) and all(vals[j][1] >= ref * (1 + rise) for j in range(i + 1, min(i + 1 + need, len(vals)))) \
                and i + need < len(vals):
            return t
    return None
