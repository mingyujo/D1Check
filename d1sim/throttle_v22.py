"""Throttle model v2.2 — v2.1 controllers · power · throughput · adapter unchanged, thermal block refit on N1 + N2 + N4
(prereg sim/스로틀모형_사전등록_v22.md, mirror d1sim/docs/, commit 9056685 — before any fit; rules sim/G1_판정_1006.md §3).
v0/v1/v2/v2.1 modules are untouched; this module imports throttle_v21 and only adds.

Forms:
  V22-A : thermal block (G_f, G_s, tau_s, c_f, c_s, k_b; tau_a, G_a, c_a) refit — same arithmetic as ThermalV21.
  V22-M : V22-A + per-model thermal-input multiplier g_m = {'NPU': g, 'GPU': g} stored in thermal['g_m'], applied to EffNet runs
          only, in the closed-loop model power: P_in - P_idle = g_m[r] (P_model(s) - P_idle). Because
          power_of(s, pp) = P_idle + (P0 - P_idle) s^alpha is linear in (P0 - P_idle), this is exactly P0' = P_idle + g_m (P0 - P_idle).
          MobileNet runs (and any run without model='effnet') see g_m = 1, i.e. V22-A.
"""
from __future__ import annotations

import json
import os

from d1sim import throttle_v21 as tv21

PROFILES = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'profiles')
thermal_series = tv21.thermal_series          # open-loop thermal, measured power in (identical arithmetic)
THERMAL_KEYS = ('tau_f', 'G_f', 'G_s', 'tau_s', 'tau_a', 'G_a', 'P_idle', 'c_f', 'c_s', 'c_a', 'k_b', 'd_ref')


def with_model(params, model):
    """Params for a run of `model` ('mobilenet' | 'effnet'). EffNet + thermal['g_m'] -> P0 rescaled per resource; otherwise unchanged."""
    gm = (params.get('thermal') or {}).get('g_m')
    if model != 'effnet' or not gm:
        return params
    power = {r: dict(v) for r, v in params['power'].items()}
    for r, g in gm.items():
        if r in power:
            pp = power[r]
            pp['P0'] = pp['P_idle'] + float(g) * (pp['P0'] - pp['P_idle'])
    return dict(params, power=power)


def simulate(params, schedule, T_start, A0, B0=None, dt=1.0, model='mobilenet'):
    """throttle_v21.simulate contract (same row keys) with the V22-M model multiplier applied for model='effnet'."""
    return tv21.simulate(with_model(params, model), schedule, T_start, A0, B0, dt)


def load_params(prefix='throttle_v22_', engine='CM'):
    """dict(thermal, ctrl{GPU,NPU,CPU4}, power, L0) from profiles/<prefix>*.json (same layout as throttle_v21_*.json)."""
    tp = json.load(open(os.path.join(PROFILES, f'{prefix}thermal.json'), encoding='utf-8'))
    th = {k: tp[k] for k in THERMAL_KEYS}
    if tp.get('g_m'):
        th['g_m'] = dict(tp['g_m'])
    gfn = 'GPU_compiledmodel' if engine == 'CM' else 'GPU_interpreter'
    ctrl, power, L0 = {}, {}, {}
    for res, fn in (('GPU', gfn), ('NPU', 'NPU'), ('CPU4', 'CPU4_interpreter')):
        d = json.load(open(os.path.join(PROFILES, f'{prefix}{fn}.json'), encoding='utf-8'))
        ctrl[res] = dict(d['ctrl']); power[res] = {k: d['power'][k] for k in ('P_idle', 'P0', 'alpha')}; L0[res] = d['L0_ms']
    ctrl['CPU4'] = dict(ctrl['CPU4'], v1_controller=True)
    return dict(thermal=th, ctrl=ctrl, power=power, L0=L0)
