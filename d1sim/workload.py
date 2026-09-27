"""Synthetic workload scenarios. Request format = 0912 §3.3 {id, arrival_s, deadline_s, weight, min_tier, model}
+ two fields we add: cls (FG / NORMAL / BG, NPU-Manager-style priority class) and n_inf (inferences in the job).

Load is defined relative to capacity (0912 §9-5): rho = offered work / capacity of the sequential server, i.e. the
FASTEST resource's unthrottled rate (NPU, profile median duty 100 = 0.743 ms). rho = 1 saturates the NPU even
without throttle. (First draft used GPU units; at rho_GPU 0.9 the NPU was ~18 % busy and no resource ever throttled
on dev seed 1 -> scenarios said nothing about heat. Changed 18:25, recorded in 가설원장.)
Deadlines [D 시뮬레이터_현황_0926.md:33]: urgent 1.5 s (FG) / normal 6 s (stream). BG batch deadline separate [E].
Seeds [D 0912 §3.3 split, re-sized]: dev 1-10 · validation 51-60 · independent 61-65. Only dev seeds are run in v0.
"""
from __future__ import annotations

import random

DEV_SEEDS = tuple(range(1, 11))
VAL_SEEDS = tuple(range(51, 61))
IND_SEEDS = tuple(range(61, 66))

FG = dict(cls='FG', weight=3, deadline=1.5, n_inf=1)          # user-facing single-image request
NORMAL = dict(cls='NORMAL', weight=2, deadline=6.0)            # stream frame, "일반" 6 s
BG = dict(cls='BG', weight=1, n_inf=128)                        # photo-library batch chunk [E: 128 images]


def _req(i, t, spec, n_inf=None, deadline=None):
    return dict(id=i, arrival_s=round(t, 6), deadline_s=round(t + (deadline if deadline is not None else spec['deadline']), 6),
                weight=spec['weight'], min_tier='FP32', model='mobilenet_v1', cls=spec['cls'],
                n_inf=n_inf if n_inf is not None else spec['n_inf'])


def poisson_fg(rng, lam, horizon, start_id):
    out, t, i = [], 0.0, start_id
    while True:
        t += rng.expovariate(lam)
        if t >= horizon:
            return out
        out.append(_req(i, t, FG)); i += 1


def scenario(name, seed, profile, horizon=600.0, **kw):
    """S0: FG only (control). S1: BG backlog + FG. S2: continuous stream + FG."""
    rng = random.Random(seed)
    L_ref = min(profile.L0_ms.values()) / 1000.0     # fastest resource (NPU)
    if name == 'S0':
        return poisson_fg(rng, kw.get('lam_fg', 2.0), horizon, 0)
    if name == 'S1':
        rho = kw.get('rho', 0.9)
        n_chunks = int(round(rho * horizon / (BG['n_inf'] * L_ref)))   # backlog present at t=0 (photo library)
        bg_deadline = kw.get('bg_deadline', horizon)                   # [E] "finish within the episode"
        reqs = [_req(i, 0.0 + i * 1e-6, BG, deadline=bg_deadline) for i in range(n_chunks)]
        return reqs + poisson_fg(rng, kw.get('lam_fg', 0.5), horizon, n_chunks)
    if name == 'S2':
        rho = kw.get('rho', 0.876)
        fps = kw.get('fps', 30.0)
        n_inf = max(1, int(round(rho / fps / L_ref)))                   # inferences per frame (multi-crop) [E]
        reqs, i, k = [], 0, 0
        while True:
            t = k / fps + rng.uniform(0, 0.005)
            if t >= horizon:
                break
            reqs.append(_req(i, t, NORMAL, n_inf=n_inf)); i += 1; k += 1
        return reqs + poisson_fg(rng, kw.get('lam_fg', 0.5), horizon, i)
    raise ValueError(name)


def offered_rho(reqs, profile, horizon):
    return sum(r['n_inf'] for r in reqs) * min(profile.L0_ms.values()) / 1000.0 / horizon
