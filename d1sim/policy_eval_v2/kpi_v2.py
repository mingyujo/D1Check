"""kpi_v2.py — per-run KPIs of sim/정책비교_사전등록_v2.md §5 (reads only the simulator record).

§5-1 denominators (FG · BG separately; BG in chunks AND inferences): planned · completed · on_time · late (completed after the deadline —
     "지각 성공" = success + miss) · failed (no failure path in this simulator: 0) · rejected · unfinished (left at the horizon).
§5-2 (a) per run: FG late = failed = rejected = unfinished = 0 and BG late = unfinished = 0 (no tolerance).
§5-3 FG P95 = nearest-rank over ALL planned FG: sorted[ceil(0.95 N) - 1], not-completed = +inf (late = its real response) ->
     > 5 % not completed gives +inf. Completed-only P95 = auxiliary (null when none completed).
§5-4 thermal on the common window [0, horizon]: max SKIN · time with SKIN >= 38 / 40 / 42 (s; step-start SKIN, steps <= 0.5 s) ·
     throttle time (executing s with ratio >= NPU 1.06 / GPU 1.10) · throughput (completed inferences / horizon).
§5-5 completion (separate from the window): per burst (last chunk completion - burst arrival) · last BG completion · end-of-window SKIN.
J / energy: provisional ledger only (conservation), never a KPI (§3-9).
"""
from __future__ import annotations

import math

from d1sim.kpi import conservation
from d1sim.policy_eval_v2.sim import PERIOD_S

INF = math.inf


def nearest_rank(xs, q=0.95):
    if not xs:
        return None
    v = sorted(xs)
    return v[max(0, int(math.ceil(q * len(v) - 1e-9)) - 1)]


def summarize(sim, rec, policy):
    R = list(rec.requests.values())
    H = sim.horizon
    fg = [r for r in R if r['cls'] == 'FG']
    bg = [r for r in R if r['cls'] == 'BG']

    def on_time(r):
        return r['status'] == 'done' and r['completion'] <= r['deadline_s'] + 1e-9

    def resp(r):
        return (r['completion'] - r['arrival_s']) if r['status'] == 'done' else INF

    fg_done = [r for r in fg if r['status'] == 'done']
    fg_d = dict(planned=len(fg), completed=len(fg_done), on_time=sum(1 for r in fg if on_time(r)),
                late=sum(1 for r in fg_done if not on_time(r)), failed=0,
                rejected=sum(1 for r in fg if r['status'] == 'rejected'), unfinished=sum(1 for r in fg if r['status'] == 'unfinished'),
                p95_all=nearest_rank([resp(r) for r in fg]), p95_completed=nearest_rank([resp(r) for r in fg_done]))
    bg_done = [r for r in bg if r['status'] == 'done']
    bg_d = dict(planned=len(bg), completed=len(bg_done), on_time=sum(1 for r in bg if on_time(r)),
                late=sum(1 for r in bg_done if not on_time(r)), failed=0,
                rejected=sum(1 for r in bg if r['status'] == 'rejected'), unfinished=sum(1 for r in bg if r['status'] == 'unfinished'),
                planned_inf=sum(r['n_inf'] for r in bg), completed_inf=sum(r['n_inf'] for r in bg_done),
                on_time_inf=sum(r['n_inf'] for r in bg if on_time(r)))
    bg_d['on_time_rate'] = (bg_d['on_time'] / bg_d['planned']) if bg_d['planned'] else None
    bursts = []
    for b in sorted({r['burst'] for r in bg}):
        rb = [r for r in bg if r['burst'] == b]
        arr = min(r['arrival_s'] for r in rb)
        alldone = all(r['status'] == 'done' for r in rb)
        last = max(r['completion'] for r in rb) if alldone else None
        bursts.append(dict(burst=b, arrival_s=arr, deadline_s=rb[0]['deadline_s'], chunks=len(rb), done_all=alldone,
                           completion_s=(last - arr) if alldone else None, last_completion=last,
                           on_time_all=all(on_time(r) for r in rb)))
    guard_a = (fg_d['late'] == 0 and fg_d['failed'] == 0 and fg_d['rejected'] == 0 and fg_d['unfinished'] == 0
               and bg_d['late'] == 0 and bg_d['unfinished'] == 0)
    th = sim.therm
    n_inf_done = sum(r['n_inf'] for r in R if r['status'] == 'done')
    real = [round(100.0 * x / PERIOD_S, 3) for x in sim.bg_exec_per]
    cmd = getattr(policy, 'log', None)
    cmd = {int(k): v[0] for k, v in cmd.items()} if cmd is not None else dict(getattr(policy, 'cmd', {}) or {})
    bad = conservation(rec)
    return dict(
        policy=policy.name, horizon=H, fg=fg_d, bg=bg_d, bursts=bursts, guard_a=guard_a,
        thermal=dict(max_skin=th['max_skin'], t38_s=th['t_level'][38.0], t40_s=th['t_level'][40.0], t42_s=th['t_level'][42.0],
                     throttle_s=th['throttle_s'], exec_s=th['exec_s'], throughput_inf_s=n_inf_done / H, end_skin=sim.end_skin),
        completion=dict(bg_last_completion=(max(r['completion'] for r in bg_done) if bg_done and len(bg_done) == len(bg) else None),
                        bursts_s=[b['completion_s'] for b in bursts]),
        duty_cmd=cmd, duty_real=real,
        duty_cmd_mean=(sum(cmd.values()) / len(cmd)) if cmd else None,
        duty_real_mean_active=(sum(sim.bg_exec_per) / (PERIOD_S * len(cmd))) * 100.0 if cmd else None,
        energy_j_provisional=rec.energy_j, decisions=sim.decisions,
        conservation_ok=not bad, conservation=bad[:3])
