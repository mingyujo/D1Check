"""Connection adapter for an external event-based scheduler (P1l v2 stage 7 — 조민규 질문 2).

Two ways to use the S26 parallel model:

1) Library (the scheduler owns the queue and the decisions):

    from d1sim.parsim_v1.adapter import ParallelDevice
    dev = ParallelDevice(form='M-sup', start=dict(skin=30.5, ap=29.5, bat=28.35, a0=-1.0), seed=1)
    dev.advance(35.0)                                   # integrate the device to t = 35 s (seconds from the session origin)
    dev.state()                                         # skin · ap (℃), ratio (GPU/NPU throttle x), u (10 s busy), lane busy-until
    dev.estimate('classification', 'GPU')               # median stage durations (s) incl. the current ratio — for EFT-like rules
    job = dev.dispatch(35.0, 'req-0', 'classification', 'urgent', 'GPU')
    # -> dispatch · inference_start · inference_end · output_ready · persist_complete · lane_available (s) + ratio + sample source
    #    response(urgent) = output_ready - scheduled arrival · response(normal) = persist_complete - scheduled arrival
    #    the lane stays occupied until lane_available (dispatching again before that raises LaneBusy)
    dev.dispatch(..., durations=(prepare, execution, out, persist, release))   # use YOUR stage durations (s); the model adds
                                                                               # the throttle ratio to `execution` and the heat
2) Batch CLI (the model's own rules R1 ~ R8 decide):

    python -m d1sim.parsim_v1.adapter run --requests REQ.json --rule R3 [--start START.json] [--form M-sup] [--seed 1]
                                           [--window 120] --out EVENTS.jsonl
    REQ.json  = [{"ordinal":0,"task":"classification","priority":"urgent","sched":35.0,"deadline":1.5}, ...]
    START.json = {"skin":30.5,"ap":29.5,"bat":28.35,"a0":-1.0}
    EVENTS.jsonl = one line per request (stage times, lane, resource, ratio, response, on_time) + a last line {"path": ...}

Units: seconds, ℃, W, J. Resources: CPU · GPU · NPU (one lane each; CPU lane takes both tasks, GPU/NPU lanes classification only —
the measured S26 support; detection on GPU/NPU has no S26 request data and is refused, never filled with zeros).
What every number is (measured fit / measured distribution / frozen v2.2 / assumption): MODEL_CARD.md.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys

from d1sim.parsim_v1 import predict as pr
from d1sim.parsim_v1 import rules
from d1sim.parsim_v1 import service_des as sd
from d1sim.parsim_v1 import thermal_sum as ts

SUPPORTED = {('classification', 'CPU'), ('classification', 'GPU'), ('classification', 'NPU'), ('detection', 'CPU')}
RULES = {'R1': rules.R1, 'R2': rules.R2, 'R3': rules.R3, 'R4': rules.R4, 'R5': rules.R5, 'R6': rules.R6,
         'R7': lambda: rules.R7(0.0), 'R8': rules.R8}


class LaneBusy(RuntimeError):
    pass


class _ExternalRule:
    """Lane layout for library use: one lane per resource; decisions come from the caller."""

    name = 'external'

    def lanes(self):
        return rules.LANES3

    def ctx_key(self, task, res, lane):
        return rules.ctx3(task, res)

    def choose(self, eng, free):
        return None

    def on_dispatch(self, eng, job):
        pass


def default_start(params):
    return dict(skin=30.5, ap=29.5, bat=30.5 - params['thermal']['d_ref'], a0=-1.0)


class ParallelDevice:
    def __init__(self, form='M-sup', start=None, seed=1, overhead=False, profile=None):
        prof = profile or pr.load_profile()
        g, kappa = pr.forms(prof)[form]
        self.params = ts.load_v22()
        st = dict(default_start(self.params), **(start or {}))
        self.dev = ts.Device(self.params, g, kappa, st['skin'], st['ap'], st['bat'], st['a0'])
        self.svc = sd.ServiceModel()
        self.eng = sd.Engine(_ExternalRule(), self.svc, self.dev, [], window_s=0.0, seed=seed)
        self.overhead = overhead
        self.form = form
        self.jobs = []

    # -- time ---------------------------------------------------------------------------------------------------
    def advance(self, t):
        if t < self.eng.t - 1e-9:
            raise ValueError('time reversal')
        self.eng.advance_to(t)
        for ln in self.eng.lanes.values():
            if ln['job'] is not None and ln['job'].lane_available <= self.eng.t + 1e-12:
                ln['job'] = None
                ln['free_at'] = self.eng.t

    # -- views --------------------------------------------------------------------------------------------------
    def state(self):
        return dict(t=self.eng.t, skin=self.dev.skin, ap=self.dev.ap,
                    ratio={r: self.dev.ratio(r) for r in ('GPU', 'NPU')}, u={r: self.dev.u(r) for r in ts.RES},
                    first_arm_skin={r: self.dev.first_arm_temp(r) for r in ('GPU', 'NPU')},
                    lanes={n: (None if ln['job'] is None else ln['job'].lane_available) for n, ln in self.eng.lanes.items()})

    def estimate(self, task, resource):
        if (task, resource) not in SUPPORTED:
            raise ValueError(f'unsupported {task} on {resource} (no S26 request data)')
        pre, inf, out, pers, rel = self.svc.med[rules.ctx3(task, resource)]
        r = self.dev.ratio(resource) if resource != 'CPU' else 1.0
        return dict(prepare=pre, execution=inf * r, out=out, persist=pers, release=rel, ratio=r)

    # -- dispatch -----------------------------------------------------------------------------------------------
    def dispatch(self, t, request_id, task, priority, resource, durations=None):
        if (task, resource) not in SUPPORTED:
            raise ValueError(f'unsupported {task} on {resource} (no S26 request data)')
        self.advance(t)
        ln = self.eng.lanes[resource]
        if ln['job'] is not None:
            raise LaneBusy(f'{resource} lane busy until {ln["job"].lane_available:.6f}')
        q = dict(ordinal=len(self.jobs), task=task, priority=priority, sched=t, deadline=sd.DEADLINE_S[priority], actual=t,
                 request_id=request_id, state='waiting')
        self.eng.waiting.append(q)
        if durations is None:
            self.eng.start(q, resource, t, after_busy=False) if self.overhead else self._start_no_overhead(q, resource, t, None)
        else:
            self._start_no_overhead(q, resource, t, tuple(float(x) for x in durations))
        j = q['job']
        rec = dict(request_id=request_id, task=task, priority=priority, resource=resource, dispatch=j.dispatch,
                   inference_start=j.inf_start, inference_end=j.inf_end, output_ready=j.output_ready,
                   persist_complete=j.persist, lane_available=j.lane_available, ratio=j.ratio,
                   source='caller durations' if durations is not None else f'R3 stage tuple {j.key}')
        self.jobs.append(rec)
        return rec

    def _start_no_overhead(self, q, resource, t, durations):
        svc = self.svc
        if durations is None:
            durations = svc.sample(self.eng.rng, rules.ctx3(q['task'], resource))
        saved_sample, saved_ov = svc.sample, svc.overhead
        try:
            svc.sample = lambda rng, key: durations
            svc.overhead = lambda rng, kind: 0.0
            self.eng.start(q, resource, t, after_busy=False)
        finally:
            svc.sample, svc.overhead = saved_sample, saved_ov


def run_batch(requests, rule_name='R3', start=None, form='M-sup', seed=1, window=None):
    prof = pr.load_profile()
    g, kappa = pr.forms(prof)[form]
    params = ts.load_v22()
    st = dict(default_start(params), **(start or {}))
    dev = ts.Device(params, g, kappa, st['skin'], st['ap'], st['bat'], st['a0'])
    win = window or max(120.0, max(q['sched'] for q in requests) + 50.0)
    eng = sd.Engine(RULES[rule_name](), sd.ServiceModel(), dev, requests, win, seed)
    res = eng.run()
    return res, win


def write_events(res, out, meta):
    with open(out, 'w', encoding='utf-8', newline='\n') as f:
        for r in sorted(res['rows'], key=lambda r: r['ordinal']):
            r = {k: (None if isinstance(v, float) and math.isinf(v) else v) for k, v in r.items()}
            f.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + '\n')
        f.write(json.dumps(dict(meta=meta, path=dict(t=res['path_t'], skin=[round(x, 6) for x in res['path_skin']],
                                                    ap=[round(x, 6) for x in res['path_ap']]), energy_J=res['energy_J']),
                           ensure_ascii=False, sort_keys=True) + '\n')


def selftest():
    ok = True
    # (1) library: deterministic, lane ownership, ratio, unsupported pair refused
    a = ParallelDevice(seed=3)
    j1 = a.dispatch(35.0, 'r0', 'classification', 'urgent', 'GPU')
    try:
        a.dispatch(35.01, 'r1', 'classification', 'urgent', 'GPU')
        ok = False
    except LaneBusy:
        pass
    j2 = a.dispatch(35.01, 'r1', 'detection', 'normal', 'CPU')
    a.advance(40.0)
    b = ParallelDevice(seed=3)
    k1 = b.dispatch(35.0, 'r0', 'classification', 'urgent', 'GPU')
    ok &= j1 == k1 and j1['lane_available'] > j1['output_ready'] > j1['inference_end'] > j1['inference_start'] >= j1['dispatch'] == 35.0
    try:
        b.dispatch(36.0, 'x', 'detection', 'normal', 'GPU')
        ok = False
    except ValueError:
        pass
    # (2) caller durations: stage arithmetic exact at ratio 1
    c = ParallelDevice(seed=1)
    j = c.dispatch(10.0, 'q', 'classification', 'urgent', 'NPU', durations=(0.03, 0.03, 0.0, 0.002, 0.0005))
    ok &= abs(j['lane_available'] - 10.0625) < 1e-12 and j['ratio'] == 1.0
    # (3) batch == the frozen prediction path (same engine, same seed)
    reqs = [dict(ordinal=i, task='classification' if i % 2 == 0 else 'detection', priority='urgent' if i % 2 == 0 else 'normal',
                 sched=35.0 + 0.2 * i, deadline=1.5 if i % 2 == 0 else 6.0) for i in range(192)]
    res, win = run_batch(reqs, 'R3', seed=5, window=120.0)
    prof = pr.load_profile()
    one = pr.run_one(rules.R3(), sd.ServiceModel(), ts.load_v22(), prof['M_sup']['g'], 1.0,
                     dict(skin0=30.5, ap0=29.5, bat0=30.5 - ts.load_v22()['thermal']['d_ref'], a0=-1.0), reqs, 120.0, 5)
    ok &= abs(max(res['path_ap']) - one['ap_max_path']) < 1e-12
    print('adapter selftest', 'PASS' if ok else 'FAIL', round(j1['lane_available'] - j1['dispatch'], 4), round(max(res['path_ap']), 3))
    return ok


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd')
    r = sub.add_parser('run')
    r.add_argument('--requests', required=True)
    r.add_argument('--rule', default='R3', choices=sorted(RULES))
    r.add_argument('--start')
    r.add_argument('--form', default='M-sup', choices=('M-sup', 'M-kappa'))
    r.add_argument('--seed', type=int, default=1)
    r.add_argument('--window', type=float)
    r.add_argument('--out', required=True)
    sub.add_parser('selftest')
    a = ap.parse_args(argv)
    if a.cmd == 'selftest':
        return 0 if selftest() else 1
    if a.cmd == 'run':
        reqs = json.load(open(a.requests, encoding='utf-8'))
        start = json.load(open(a.start, encoding='utf-8')) if a.start else None
        res, win = run_batch(reqs, a.rule, start, a.form, a.seed, a.window)
        write_events(res, a.out, dict(rule=a.rule, form=a.form, seed=a.seed, window_s=win, start=start))
        urg = [x['response'] for x in res['rows'] if x['priority'] == 'urgent']
        p95 = sd.nearest_rank_p95(urg)
        print(json.dumps(dict(rule=a.rule, requests=len(reqs), on_time=sum(x['on_time'] for x in res['rows']),
                              urgent_p95_ms=None if p95 is None or math.isinf(p95) else round(p95 * 1000, 3),
                              ap_max=round(max(res['path_ap']), 3), skin_max=round(max(res['path_skin']), 3)), ensure_ascii=False))
        return 0
    ap.print_help()
    return 2


if __name__ == '__main__':
    sys.exit(main())
