"""KPIs and conservation checks. Reads only the Record built by env.Sim (policies never touch it).

KPI definitions (fixed in sim/시뮬_사전등록_v0.md §3):
  fg_p95_s        : 95th percentile (numpy linear) of FG response = completion - arrival; a FG request that is
                    rejected or unfinished at the horizon counts as +inf (so p95 = inf if > 5 % FG are lost)
  weighted_tardiness : sum w * max(0, C - d) over done; unfinished add w * max(0, horizon - d) (lower bound)
  deadline_violation_rate : (done late + rejected + unfinished with d <= horizon) / arrivals
  reject_rate, throughput_inf_s (completed inferences / horizon), bg_completion (done BG chunks / arrived BG),
  throttle_s per resource (time EXECUTING with s < 1/1.1), status2_s (time with status >= MODERATE),
  energy_j (PROVISIONAL, absolute accuracy uncertified), energy_per_inf_mj
"""
from __future__ import annotations

import math

from d1sim.profile import RESOURCES


def p_inf(xs, q):
    """numpy-'linear' percentile that returns inf when an interpolation neighbour is inf (np gives nan)."""
    xs = sorted(xs)
    if not xs:
        return None
    pos = (len(xs) - 1) * q / 100.0
    lo, hi = int(math.floor(pos)), int(math.ceil(pos))
    if math.isinf(xs[lo]) or math.isinf(xs[hi]):
        return math.inf
    return xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)


def kpis(rec):
    R = list(rec.requests.values())
    H = rec.horizon
    fg = [r for r in R if r['cls'] == 'FG']
    fg_resp = [(r['completion'] - r['arrival_s']) if r['status'] == 'done' else math.inf for r in fg]
    done = [r for r in R if r['status'] == 'done']
    late = sum(1 for r in done if r['completion'] > r['deadline_s'] + 1e-12)
    rej = sum(1 for r in R if r['status'] == 'rejected')
    unf_viol = sum(1 for r in R if r['status'] == 'unfinished' and r['deadline_s'] <= H)
    wt = sum(r['weight'] * max(0.0, r['completion'] - r['deadline_s']) for r in done) + \
        sum(r['weight'] * max(0.0, H - r['deadline_s']) for r in R if r['status'] == 'unfinished')
    bg = [r for r in R if r['cls'] == 'BG']
    n_inf = sum(r['n_inf'] for r in done)
    return dict(
        n=len(R), n_fg=len(fg),
        fg_p95_s=p_inf(fg_resp, 95),
        fg_p50_s=p_inf(fg_resp, 50),
        weighted_tardiness=wt,
        deadline_violation_rate=(late + rej + unf_viol) / len(R) if R else None,
        reject_rate=rej / len(R) if R else None,
        unfinished=sum(1 for r in R if r['status'] == 'unfinished'),
        throughput_inf_s=n_inf / H,
        bg_completion=(sum(1 for r in bg if r['status'] == 'done') / len(bg)) if bg else None,
        **{f'throttle_s_{r}': rec.throttle_s[r] for r in RESOURCES},
        **{f'exec_s_{r}': rec.exec_s[r] for r in RESOURCES},
        status2_s=rec.status_s[2],
        energy_j=rec.energy_j,
        energy_per_inf_mj=1000 * rec.energy_j / n_inf if n_inf else None,
        peak_skin_c=max((x[1] for x in rec.trace), default=None),
    )


def conservation(rec, tol=1e-6):
    """Returns a list of violated identities (empty = all hold)."""
    bad = []
    R = rec.requests
    for i, r in R.items():
        if r['status'] in ('done', 'running', 'unfinished') and 'start' in r:
            if r['start'] < r['arrival_s'] - tol:
                bad.append(f'start<arrival id={i}')
        if r['status'] == 'done':
            wait = r['start'] - r['arrival_s']
            resp = r['completion'] - r['arrival_s']
            if abs(resp - (wait + r['switch_s'] + r['exec_s'])) > tol:
                bad.append(f'response!=wait+switch+exec id={i}')
    n_arr = len(R)
    by = {s: sum(1 for r in R.values() if r['status'] == s) for s in ('done', 'rejected', 'unfinished')}
    if n_arr != by['done'] + by['rejected'] + by['unfinished']:
        bad.append(f'arrivals {n_arr} != done+rejected+unfinished {by}')
    # energy ledger contiguous over [0, horizon] and sums to the reported total
    segs = sorted(rec.energy)
    if not segs or abs(segs[0][0]) > tol or abs(segs[-1][1] - rec.horizon) > tol:
        bad.append('energy ledger does not span [0, horizon]')
    for a, b in zip(segs, segs[1:]):
        if abs(a[1] - b[0]) > tol:
            bad.append(f'energy ledger gap/overlap at {a[1]:.6f}'); break
    if abs(sum((b - a) * p for a, b, p in segs) - rec.energy_j) > 1e-6 * max(1.0, rec.energy_j):
        bad.append('energy != sum(power*time)')
    # sequential: per-resource and global busy intervals do not overlap
    allb = []
    for r in RESOURCES:
        iv = sorted(rec.busy[r])
        allb += iv
        for a, b in zip(iv, iv[1:]):
            if b[0] < a[1] - tol:
                bad.append(f'concurrent on {r} at {b[0]:.6f}'); break
    allb.sort()
    for a, b in zip(allb, allb[1:]):
        if b[0] < a[1] - tol:
            bad.append(f'global concurrency at {b[0]:.6f}'); break
    for r in RESOURCES:
        if rec.throttle_s[r] > rec.exec_s[r] + tol:
            bad.append(f'throttle_s > exec_s on {r}')
        busy = sum(b - a for a, b in rec.busy[r])
        if rec.exec_s[r] > busy + tol:
            bad.append(f'exec_s > busy on {r}')
    return bad
