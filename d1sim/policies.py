"""Policies. Each gets an immutable snapshot `obs` (env.Sim.snapshot) and returns one action:
  ('dispatch', req_id, resource) | ('reject', req_id) | ('unload',) | ('wait', until_t or None)
Policies keep only their own bookkeeping; they cannot reach the simulator or the record.
"""
from __future__ import annotations

PRIO = {'FG': 0, 'NORMAL': 1, 'BG': 2, 'OPPORTUNISTIC': 3}


def fifo_head(queue):
    return min(queue, key=lambda q: (q['arrival_s'], q['id']))


def prio_head(queue, allow=lambda q: True):
    cand = [q for q in queue if allow(q)]
    return min(cand, key=lambda q: (PRIO[q['cls']], q['arrival_s'], q['id'])) if cand else None


class Fixed:
    """FIFO on one resource."""

    def __init__(self, resource):
        self.r = resource
        self.name = f'fixed-{resource}'

    def decide(self, obs):
        return ('dispatch', fifo_head(obs['queue'])['id'], self.r)


class ShortestLatency:
    """FIFO + resource with the shortest pre-throttle latency (profile L0 + switch cost from the loaded model)."""
    name = 'shortest'

    def decide(self, obs):
        q = fifo_head(obs['queue'])

        def cost(r):
            sw = 0.0 if obs['loaded'] == r else obs['init_s'][r]
            return sw + q['n_inf'] * obs['L0_ms'][r] / 1000.0
        r = min((r for r in obs['L0_ms'] if obs['supported'][r]), key=cost)
        return ('dispatch', q['id'], r)


class NpuManagerApprox:
    """KS-C baseline (재설계안 §7 / ref_NPU_Manager_Android17.md): priority FG > NORMAL > BACKGROUND > OPPORTUNISTIC,
    NPU only (NPU Manager has no CPU/GPU routing), reactive: when thermal_status >= MODERATE, unload once and hold
    BACKGROUND work until status drops (re-check every `recheck_s`). The status comes from the variant's status model."""
    name = 'npumgr'

    def __init__(self, resource='NPU', recheck_s=1.0):
        self.r = resource
        self.recheck_s = recheck_s
        self.unloaded = False

    def decide(self, obs):
        hot = obs['status'] >= 2
        if hot and not self.unloaded and obs['loaded'] is not None:
            self.unloaded = True
            return ('unload',)
        if not hot:
            self.unloaded = False
        q = prio_head(obs['queue'], allow=(lambda x: x['cls'] != 'BG') if hot else (lambda x: True))
        if q is None:
            return ('wait', obs['t'] + self.recheck_s)
        return ('dispatch', q['id'], self.r)


class OursV0:
    """Rule-based, throttle-predictive (uses the simulator's own throttle model through obs['predict'] - i.e. a
    PERFECT model; see report limits). Priority FG > NORMAL > BG.
      FG          : resource with the earliest predicted completion of this request (throttle + switch included)
      NORMAL / BG : resource with the least predicted time for a lookahead window of work (queued inferences of the
                    same class, capped at `lookahead_s` of GPU-unthrottled work) - amortises the switch cost
      BG only     : prefer resources whose predicted sensor temperature at the end of that window stays below
                    T_th - margin_c (or that never slow down); if none and the chunk has slack > min_slack_s,
                    defer `defer_s` s; otherwise take the best resource anyway.
    Tunables (development seeds only): margin_c, lookahead_s, defer_s.
    Rule history: r1 (18:22) FG/NORMAL/BG all used single-request earliest completion -> on dev seed 1 S2 it stuck on
    CPU4 (switching to NPU costs 0.111 s > one 8-inference frame on CPU4). r2 = lookahead window for NORMAL/BG."""

    def __init__(self, margin_c=0.5, lookahead_s=10.0, defer_s=2.0, T_th=None, min_slack_s=30.0):
        self.margin_c, self.lookahead_s, self.defer_s = margin_c, lookahead_s, defer_s
        self.T_th = T_th
        self.min_slack_s = min_slack_s
        self.name = f'ours-v0(m={margin_c:g},L={lookahead_s:g},d={defer_s:g})'

    def decide(self, obs):
        q = prio_head(obs['queue'])
        res = [r for r in obs['L0_ms'] if obs['supported'][r]]
        if q['cls'] == 'FG':
            preds = {r: obs['predict'](r, q['n_inf']) for r in res}
            return ('dispatch', q['id'], min(res, key=lambda r: preds[r]['finish_s']))
        cap = int(self.lookahead_s * 1000.0 / obs['L0_ms']['GPU'])
        backlog = 0
        for x in obs['queue']:
            if x['cls'] == q['cls']:
                backlog += x['n_inf']
                if backlog >= cap:
                    break
        n_look = max(q['n_inf'], min(backlog, cap))
        preds = {r: obs['predict'](r, n_look) for r in res}
        best = min(res, key=lambda r: preds[r]['finish_s'])
        if q['cls'] != 'BG':
            return ('dispatch', q['id'], best)
        cool = [r for r in res
                if preds[r]['s_end'] >= 1.0 and (preds[r]['T_end'] >= self.T_th or preds[r]['T_end'] < self.T_th - self.margin_c)]
        if cool:
            return ('dispatch', q['id'], min(cool, key=lambda r: preds[r]['finish_s']))
        slack = q['deadline_s'] - obs['t'] - obs['predict'](best, q['n_inf'])['finish_s']
        if slack > self.min_slack_s:
            return ('wait', obs['t'] + self.defer_s)
        return ('dispatch', q['id'], best)
