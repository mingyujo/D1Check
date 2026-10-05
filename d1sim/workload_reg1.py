"""Registered workload for the policy comparison (sim/정책비교_사전등록_v1.md §2) — BG work arrives in BURSTS with a slack-based
deadline, FG requests are Poisson. New file: workload.py (v0, S0/S1/S2) is untouched and has no burst/slack arguments.

  slack s = (BG burst deadline - burst arrival) / (time to do that burst's work at d100 on a cold resource)
          -> burst deadline = arrival + s * burst_work_s     (s in {1.0, 1.5, 2.0, 3.0} — prereg grid)
  burst work = burst_work_s * rate_d100 inferences, split into chunks of `bg_chunk_inf` (all arrive at the burst time)
  bursts k = 0..n_bursts-1 arrive at k * period_s + U(0, jitter_s)   (seeded; burst 0 at U(0, jitter_s) too)
  FG: Poisson(lam_fg) on [0, horizon), single inference, deadline 1.5 s (team research deadline, 조민규 §5)
  horizon = last BG deadline + tail_s (300 s)
With the defaults (3 bursts x 300 s of d100 work every 900 s) the average BG load is 0.29~0.37 of the cold d100 capacity —
below the sustained (throttled) capacity of NPU (~0.84 = 1/1.19) and GPU (~0.49 = 1/2.06, MobileNet [P-fit v2.1]) — while
each burst is 1.0 (instantaneous load above sustainable): mean < sustainable < burst, as registered.
Request dict = workload.py 0912 §3.3 format {id, arrival_s, deadline_s, weight, min_tier, model, cls, n_inf} + burst index.
"""
from __future__ import annotations

import random

FG_DEADLINE_S = 1.5
DEV_SEEDS = tuple(range(1, 11))
HOLDOUT_SEEDS = tuple(range(51, 61))


def scenario_reg1(seed, slack, lam_fg, rate_d100, model='efficientnet_lite0', n_bursts=3, burst_work_s=300.0, period_s=900.0,
                  jitter_s=60.0, bg_chunk_inf=128, tail_s=300.0):
    if slack <= 0 or rate_d100 <= 0 or n_bursts < 1:
        raise ValueError('slack, rate_d100 > 0 and n_bursts >= 1')
    rng = random.Random(seed)
    reqs, i = [], 0
    starts = [k * period_s + rng.uniform(0.0, jitter_s) for k in range(n_bursts)]
    work = int(round(burst_work_s * rate_d100))
    last_deadline = 0.0
    for k, t in enumerate(starts):
        dl = t + slack * burst_work_s
        last_deadline = max(last_deadline, dl)
        left = work
        j = 0
        while left > 0:
            n = min(bg_chunk_inf, left)
            reqs.append(dict(id=i, arrival_s=round(t + j * 1e-6, 6), deadline_s=round(dl, 6), weight=1, min_tier='FP32', model=model,
                             cls='BG', n_inf=n, burst=k))
            i += 1; j += 1; left -= n
    horizon = last_deadline + tail_s
    t = 0.0
    while True:
        t += rng.expovariate(lam_fg)
        if t >= horizon:
            break
        reqs.append(dict(id=i, arrival_s=round(t, 6), deadline_s=round(t + FG_DEADLINE_S, 6), weight=3, min_tier='FP32', model=model,
                         cls='FG', n_inf=1, burst=None))
        i += 1
    reqs.sort(key=lambda r: (r['arrival_s'], r['id']))
    return dict(requests=reqs, horizon_s=horizon, burst_starts_s=starts, burst_work_inf=work,
                avg_bg_load_d100=(n_bursts * burst_work_s) / horizon)
