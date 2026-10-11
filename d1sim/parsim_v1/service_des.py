"""Service part (registration §1-4) — discrete events, one job per lane at a time, non-preemptive, coupled to thermal_sum.Device.

A request (task, priority, scheduled offset, deadline) goes through the measured stages of request-runner (S26 mixreq):
    actual arrival = scheduled + jitter
    dispatch       = decision time + overhead          (overhead: lane free at arrival -> 'arr', lane was busy -> 'gap')
    inference      = dispatch + prepare                 prepare = decode PNG + tensor (CPU work on the lane thread)
    inference end  = inference + execution * ratio_r    ratio_r = v2.2 controller ratio of the accelerator at dispatch (CPU: 1)
    output_ready   = inference end + out
    persist        = output_ready + persist
    lane_available = persist + release                  (lane is owned until here — the next job on the lane cannot start before)
    response       = output_ready - scheduled (urgent classification) · persist - scheduled (normal detection)   [조민규 경계표]
Stage durations are drawn JOINTLY (one measured R3 request = one tuple) from the R3 empirical distribution of the same
(context, task, resource): context 'serial' = CPU_URGENT_ONLINE_V1, 'par_gpu' = B2_PARALLEL_ONLINE_V1, 'par_npu' = S26_NPU_PARALLEL_V1
(interference between the two lanes is already inside the measured durations — registration §1-4).
Thermal activity: accelerator r executing during [inference, inference end); CPU executing during the rest of every lane busy
interval and during the whole busy interval of a CPU lane (binary: any CPU work -> CPU executing, DECISIONS D2).
"""
from __future__ import annotations

import bisect
import csv
import math
import os
import random
import statistics
from collections import defaultdict

from d1sim.parsim_v1 import thermal_sum as ts

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, 'data')
POLICY_CTX = {'CPU_URGENT_ONLINE_V1': 'serial', 'B2_PARALLEL_ONLINE_V1': 'par_gpu', 'S26_NPU_PARALLEL_V1': 'par_npu'}
SEG = ('pre', 'inf', 'out', 'pers', 'rel')
DEADLINE_S = {'urgent': 1.5, 'normal': 6.0}


class ServiceModel:
    """R3 empirical stage tuples + dispatch overhead + arrival jitter (all in seconds)."""

    def __init__(self, req_csv=None, sess_csv=None, sessions=None):
        req_csv = req_csv or os.path.join(DATA, 'r3_requests.csv')
        sess_csv = sess_csv or os.path.join(DATA, 'r3_sessions.csv')
        pol = {r['index']: r['policy'] for r in csv.DictReader(open(sess_csv, encoding='utf-8'))}
        self.tuples = defaultdict(list)
        self.jitter = defaultdict(list)
        self.ov = defaultdict(list)
        by = defaultdict(list)
        for r in csv.DictReader(open(req_csv, encoding='utf-8')):
            if sessions is not None and r['index'] not in sessions:
                continue
            by[r['index']].append(r)
        for i, rs in by.items():
            ctx = POLICY_CTX[pol[i]]
            lanes = defaultdict(list)
            for r in rs:
                res = r['selected_backend']
                g = lambda a, b: (int(r[b]) - int(r[a])) / 1e9
                self.tuples[(ctx, r['task_id'], res)].append((g('dispatch_ns', 'host_inference_start_ns'),
                                                              g('host_inference_start_ns', 'host_inference_return_ns'),
                                                              g('host_inference_return_ns', 'output_ready_ns'),
                                                              g('output_ready_ns', 'persist_complete_ns'),
                                                              g('persist_complete_ns', 'lane_available_ns')))
                self.jitter[r['task_id']].append(g('scheduled_arrival_ns', 'actual_arrival_ns'))
                lanes['CPU' if (ctx == 'serial' or r['task_id'] == 'detection') else 'ACC'].append(r)
            for lr in lanes.values():
                lr.sort(key=lambda r: int(r['dispatch_ns']))
                prev = None
                for r in lr:
                    a, d = int(r['actual_arrival_ns']), int(r['dispatch_ns'])
                    if prev is None or a >= prev:
                        self.ov['arr'].append((d - a) / 1e9)
                    else:
                        self.ov['gap'].append((d - prev) / 1e9)
                    prev = int(r['lane_available_ns'])
        for k in self.tuples:
            self.tuples[k].sort()
        self.med = {k: tuple(statistics.median(t[i] for t in v) for i in range(5)) for k, v in self.tuples.items()}
        # pooled detection-on-CPU for 3-lane rules (DECISIONS D6)
        pool = self.tuples[('par_gpu', 'detection', 'CPU')] + self.tuples[('par_npu', 'detection', 'CPU')]
        self.tuples[('par', 'detection', 'CPU')] = sorted(pool)
        self.med[('par', 'detection', 'CPU')] = tuple(statistics.median(t[i] for t in pool) for i in range(5))

    def sample(self, rng, key):
        v = self.tuples[key]
        return v[rng.randrange(len(v))]

    def overhead(self, rng, kind):
        v = self.ov[kind]
        return v[rng.randrange(len(v))]

    def arrival_jitter(self, rng, task):
        v = self.jitter[task]
        return v[rng.randrange(len(v))]


class Job:
    __slots__ = ('req', 'lane', 'res', 'dispatch', 'inf_start', 'inf_end', 'output_ready', 'persist', 'lane_available', 'ratio', 'key')


class Engine:
    """Closed loop: requests -> rule -> lanes (stage tuples) -> resource activity -> thermal_sum.Device -> controller ratio -> stages."""

    def __init__(self, rule, svc, dev, requests, window_s, seed, record_dt=0.5):
        self.rule, self.svc, self.dev = rule, svc, dev
        self.rng = random.Random(seed)
        self.window_s = float(window_s)
        self.t = 0.0
        self.lanes = {name: dict(res=res, tasks=set(tasks), job=None, free_at=0.0) for name, (res, tasks) in rule.lanes().items()}
        self.reqs = []
        for q in requests:
            q = dict(q)
            q['actual'] = q['sched'] + self.svc.arrival_jitter(self.rng, q['task'])
            q['deadline_abs'] = q['sched'] + q['deadline']
            q['state'] = 'future'
            self.reqs.append(q)
        self.future = sorted(self.reqs, key=lambda q: (q['actual'], q['ordinal']))
        self.fi = 0
        self.waiting = []
        self.jobs = []
        self.record_dt = record_dt
        self.path_t, self.path_skin, self.path_ap, self.path_P = [], [], [], []
        self.next_rec = 0.0
        self.pending_decision = []          # (time, lane) decisions scheduled after an overhead
        self.wake = math.inf
        self.energy_J = 0.0

    # -- activity ---------------------------------------------------------------------------------------------
    def active_at(self, t):
        act = set()
        for ln in self.lanes.values():
            j = ln['job']
            if j is None or not (j.dispatch <= t < j.lane_available):
                continue
            if j.res == 'CPU':
                act.add('CPU')
            elif j.inf_start <= t < j.inf_end:
                act.add(j.res)
            else:
                act.add('CPU')
        return act

    def _boundaries(self):
        b = []
        for ln in self.lanes.values():
            j = ln['job']
            if j is not None:
                b += [x for x in (j.inf_start, j.inf_end, j.output_ready, j.persist, j.lane_available) if x > self.t + 1e-12]
        return b

    def advance_to(self, t_end):
        """Integrate thermal from self.t to t_end (piecewise-constant activity; sub-steps <= 0.5 s; records path on the grid)."""
        while self.t < t_end - 1e-12:
            bnd = [x for x in self._boundaries() if x < t_end]
            nxt = min([t_end, self.t + ts.MAX_H, self.next_rec] + bnd)
            if nxt <= self.t + 1e-12:
                if self.next_rec <= self.t + 1e-12:
                    self._record()
                    continue
                nxt = min(t_end, self.t + 1e-9)
            h = nxt - self.t
            act = self.active_at(self.t + 0.5 * h)
            P = self.dev.advance(h, act)
            self.energy_J += P * h
            self.t = nxt
            if self.next_rec <= self.t + 1e-12:
                self._record()

    def _record(self):
        self.path_t.append(round(self.next_rec, 6))
        self.path_skin.append(self.dev.skin)
        self.path_ap.append(self.dev.ap)
        self.next_rec += self.record_dt

    # -- dispatch ---------------------------------------------------------------------------------------------
    def start(self, q, lane_name, decided_at, after_busy):
        ln = self.lanes[lane_name]
        res = ln['res']
        key = self.rule.ctx_key(q['task'], res, lane_name)
        pre, inf, out, pers, rel = self.svc.sample(self.rng, key)
        j = Job()
        j.req, j.lane, j.res, j.key = q, lane_name, res, key
        j.dispatch = decided_at + self.svc.overhead(self.rng, 'gap' if after_busy else 'arr')
        j.ratio = self.dev.ratio(res) if res != 'CPU' else 1.0
        j.inf_start = j.dispatch + pre
        j.inf_end = j.inf_start + inf * j.ratio
        j.output_ready = j.inf_end + out
        j.persist = j.output_ready + pers
        j.lane_available = j.persist + rel
        ln['job'] = j
        q['state'] = 'dispatched'
        q['job'] = j
        self.waiting.remove(q)
        self.jobs.append(j)
        self.rule.on_dispatch(self, j)

    def free_lanes(self):
        return [n for n, ln in self.lanes.items() if ln['job'] is None]

    def run(self):
        end = self.window_s
        while True:
            t_arr = self.future[self.fi]['actual'] if self.fi < len(self.future) else math.inf
            t_rel = min([ln['job'].lane_available for ln in self.lanes.values() if ln['job'] is not None] or [math.inf])
            t_next = min(t_arr, t_rel, self.wake)
            if t_next == math.inf or t_next > end + 600.0:
                break
            self.advance_to(t_next)
            after_busy = set()
            for n, ln in self.lanes.items():
                if ln['job'] is not None and ln['job'].lane_available <= self.t + 1e-12:
                    ln['job'] = None
                    ln['free_at'] = self.t
                    after_busy.add(n)
            while self.fi < len(self.future) and self.future[self.fi]['actual'] <= self.t + 1e-12:
                q = self.future[self.fi]
                q['state'] = 'waiting'
                self.waiting.append(q)
                self.fi += 1
            if self.wake <= self.t + 1e-12:
                self.wake = math.inf
            self.decide(after_busy)
        self.advance_to(max(end, self.t))
        return self.result()

    def decide(self, after_busy):
        while self.waiting:
            free = self.free_lanes()
            if not free:
                return
            pick = self.rule.choose(self, free)
            if pick is None:
                return
            if pick[0] == 'wait':
                self.wake = min(self.wake, pick[1])
                return
            q, lane = pick
            busy_before = lane in after_busy or self.lanes[lane]['free_at'] > q['actual'] - 1e-12
            self.start(q, lane, self.t, busy_before)

    # -- outputs ----------------------------------------------------------------------------------------------
    def result(self):
        rows = []
        for q in self.reqs:
            j = q.get('job')
            if j is None:
                rows.append(dict(ordinal=q['ordinal'], task=q['task'], priority=q['priority'], sched=q['sched'], status='unfinished',
                                 response=math.inf, on_time=False, lane=None))
                continue
            done = j.output_ready if q['priority'] == 'urgent' else j.persist
            resp = done - q['sched']
            rows.append(dict(ordinal=q['ordinal'], task=q['task'], priority=q['priority'], sched=q['sched'], actual=q['actual'],
                             dispatch=j.dispatch, inference_start=j.inf_start, inference_end=j.inf_end, output_ready=j.output_ready,
                             persist_complete=j.persist, lane_available=j.lane_available, lane=j.lane, resource=j.res,
                             ratio=j.ratio, status='succeeded', response=resp, on_time=resp <= q['deadline'] + 1e-12))
        return dict(rows=rows, path_t=self.path_t, path_skin=self.path_skin, path_ap=self.path_ap, energy_J=self.energy_J)


def nearest_rank_p95(values):
    """Team rule: nearest rank over ALL planned requests of the class; unfinished = +inf."""
    v = sorted(values)
    if not v:
        return None
    k = max(1, math.ceil(0.95 * len(v)))
    return v[k - 1]


def interp(path_t, path_y, t):
    i = bisect.bisect_right(path_t, t)
    if i <= 0:
        return path_y[0]
    if i >= len(path_t):
        return path_y[-1]
    t0, t1 = path_t[i - 1], path_t[i]
    w = (t - t0) / (t1 - t0) if t1 > t0 else 0.0
    return path_y[i - 1] * (1 - w) + path_y[i] * w
