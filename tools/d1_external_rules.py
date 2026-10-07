"""Source-pinned decision rules adapted to the existing whole-request PC ABI.

Band HEFT control flow adapted from Copyright 2023 Seoul National University,
Apache-2.0. See docs/results/external_rules_01/NOTICE.md and sources.json.
Ente predicates independently expressed from the pinned behavioral contract;
no Ente app/runtime or external models are distributed or executed here.
"""
from __future__ import annotations

import copy
import math
import time

from tools import d1_empirical_request_policy as p
from tools import d1_request_rl as old
from tools import d1_joint_queue_area as joint

BAND = 'BAND_HEFT_WHOLE_REQUEST_ADAPT_V1'
ENTE = 'ENTE_ANDROID_BG_GATE_ADAPT_V1'
ALWAYS = 'ALWAYS_ALLOW_BG_EFT_V1'
RESOURCE_POLICIES = ('CPU_REFERENCE', 'SPLIT_REFERENCE', 'EFT_REFERENCE',
                     'SHARED_EDF', 'SHARED_EFT', 'ENERGY_AP_REQUEST_V1', joint.LABEL, BAND)


def settings():
    x = old.batch.defaults('explore')
    x.update(decision_ns=0, record_ns=0, dispatch_ns=0,
             interference=1., predicted_interference=1.)
    return x


def health_issues(snapshot, now_s):
    """Android branch of pinned DeviceHealthPolicy; exact strict boundaries."""
    age = now_s - snapshot['observed_s']
    if age < 0 or age > 120:
        return ['staleObservation']
    issues = []
    available = snapshot['battery_status'] == 'available'
    if not available:
        issues.append('batteryUnavailable')
    elif snapshot['battery_percent'] < 20:
        issues.append('lowBattery')
    temp, health = snapshot['battery_c'], snapshot['battery_health']
    if available:
        if temp is None:
            issues.append('batteryTemperatureUnavailable')
        elif temp > 42:
            issues.append('batteryTooHot')
        if health is None or health == 'unknown':
            issues.append('batteryHealthUnavailable')
        elif health != 'good':
            issues.append('batteryUnhealthy')
    if snapshot['thermal_status'] == 'available':
        if snapshot['thermal_state'] not in ('nominal', 'light', 'moderate'):
            issues.append('thermalTooHigh')
    elif not (snapshot['thermal_status'] == 'unsupported' and temp is not None
              and health is not None and health != 'unknown'):
        issues.append('thermalUnavailable')
    return issues


def allow_compute(snapshot, now_s, last_interaction_s, *, initial_checks=True,
                  blocked=False, interaction_override=False):
    issues = health_issues(snapshot, now_s)
    if not initial_checks:
        issues.append('initial_checks_incomplete')
    if blocked:
        issues.append('compute_blocked')
    if not interaction_override and now_s < last_interaction_s + 15:
        issues.append('user_interacting')
    return not issues, issues


class Environment:
    """Exogenous event delivery, not a policy forecast of future health/activity.

    The runner knows event times like the engine knows arrivals. Only current
    snapshots and past interactions enter the predicate. A scheduled wakeup
    delivers a signal; it is never a promise that the next state will be healthy.
    """
    def __init__(self, spec):
        self.spec = copy.deepcopy(spec)

    def current(self, now):
        updates = [s for s in self.spec['snapshots'] if s['observed_s'] <= now]
        if not updates:
            raise ValueError('no initial health snapshot')
        last = max([0.] + [t for t in self.spec['activity_s'] if t <= now])
        return copy.deepcopy(updates[-1]), last

    def next_delivery(self, now):
        # Clock/environment driver only. Future values are not returned.
        times = [s['observed_s'] for s in self.spec['snapshots']]
        times += self.spec['activity_s']
        _, last = self.current(now)
        times.append(last + 15.)
        return min((t for t in times if t > now + 1e-9), default=None)


class Timed(p.Controller):
    def __init__(self, frozen, initial, estimates=None):
        # Existing validated opt-in ABI; the study uses a distinct public ID.
        super().__init__(frozen, initial, estimates or p.profile(frozen), 'EFT_REFERENCE')
        self.callback_times = []

    def __call__(self, *args):
        began = time.perf_counter()
        try:
            return self.decide(*args)
        finally:
            self.callback_times.append(time.perf_counter() - began)

    def validate_public(self, queue, lanes, now):
        if any(q['arrival_ns'] > now for q in queue):
            raise ValueError('future ticket')
        if any(set(l) != {'request', 'phase', 'since', 'dispatch'} for l in lanes.values()):
            raise ValueError('private lane data')
        for q in queue:
            p.backends(q)


class GateController(Timed):
    def __init__(self, frozen, initial, environment, gate=True):
        super().__init__(frozen, initial)
        self.environment = Environment(environment)
        self.gate = gate

    def decide(self, config, queue, lanes, now_ns, cfg, thermal_model, current_ap):
        self.validate_public(queue, lanes, now_ns)
        now = now_ns / 1e9
        snapshot, last = self.environment.current(now)
        allowed, issues = allow_compute(snapshot, now, last)
        eligible = [q for q in queue if not self.gate or allowed or q['priority'] == 'urgent']
        out = p.Controller.__call__(self, config, eligible, lanes, now_ns, cfg, thermal_model, current_ap)
        out.update(public_policy=ENTE if self.gate else ALWAYS,
                   bg_allowed=allowed if self.gate else True, source_gate_allowed=allowed,
                   health_snapshot=snapshot, last_interaction_s=last,
                   gate_issues=issues if self.gate else [],
                   withheld_ids=[q['id'] for q in queue if q not in eligible])
        # External signal delivery remains active even while the lower EFT waits.
        next_time = self.environment.next_delivery(now)
        if self.gate and not out['selected'] and next_time is not None:
            out['wait_until_ns'] = min(out.get('wait_until_ns', math.inf), next_time * 1e9)
        return out


def heft_pick(queue, expected_ns, waiting_ns, idle, legal_now):
    """Single-unit specialization of upstream Schedule, reserve=false.

    The full source scans first window_size requests; duplicate (model, resolved)
    groups use first FIFO representative. Strict greater job rank preserves the
    first tie. Engine GetShortestSubgraphKey uses >=, hence last backend tie.
    Return one immediate action; engine zero-cost dispatch then repeats.
    """
    waiting = dict(waiting_ns)
    yielded = set()
    audit = []
    while True:
        target = None
        largest = -1
        searched = set()
        for q in queue:
            if q['id'] in yielded or q['task'] in searched:
                continue
            searched.add(q['task'])
            best = None
            for b in p.backends(q):
                latency = expected_ns[p.key(q, b)] + waiting[b]
                if best is None or latency <= best[0]:
                    best = (latency, b)
            audit.append(dict(request_id=q['id'], shortest_ns=best[0], best_worker=best[1]))
            if best[0] > largest:
                largest, target = best[0], (q, best[1])
        if target is None:
            return None, audit, sorted(yielded)
        q, b = target
        if b not in idle or not legal_now(q, b):
            waiting[b] += expected_ns[p.key(q, b)]
            yielded.add(q['id'])
            continue
        return dict(request_id=q['id'], backend=b), audit, sorted(yielded)


class BandController(Timed):
    def __init__(self, frozen, initial):
        super().__init__(frozen, initial)
        self.expected = {k: int(sum(v)) for k, v in self.estimates.items()}
        self.running = {}
        self.ema_records = []

    def observe(self, now_ns, lanes):
        # Completion evidence is the public lane return, never private durations.
        for b, old_job in list(self.running.items()):
            current = lanes[b]['request']
            if current is None or current['id'] != old_job['q']['id']:
                cell = p.key(old_job['q'], b)
                actual = round(now_ns - old_job['dispatch'])
                before = self.expected[cell]
                self.expected[cell] = int(.1 * actual + .9 * before)
                factor = self.expected[cell] / before
                self.estimates[cell] = [d * factor for d in self.estimates[cell]]
                self.ema_records.append(dict(at_ns=now_ns, request_id=old_job['q']['id'],
                                             cell=cell, before_ns=before, observed_ns=actual,
                                             after_ns=self.expected[cell]))
                del self.running[b]
        for b, l in lanes.items():
            if l['request'] is not None:
                self.running[b] = dict(q=l['request'], dispatch=l['dispatch'])
        super().observe(now_ns, lanes)

    def decide(self, config, queue, lanes, now_ns, cfg, thermal_model, current_ap):
        self.validate_public(queue, lanes, now_ns)
        now = now_ns / 1e9
        out = dict(now_ns=now_ns, selected=None, reason=BAND, public_policy=BAND,
                   modeled_ap_c=self.t)
        idle = {b for b, l in lanes.items() if l['request'] is None}
        if not idle:
            return dict(out, reason='Band_no_idle_worker')
        active = self.active_jobs(lanes, now)
        if active is None:
            return dict(out, reason='Band_adapt_unknown_lane_overrun')
        waiting = {b: max([0.] + [j['end'] - now for j in active if j['backend'] == b]) * 1e9
                   for b in lanes}
        fifo = sorted(queue, key=lambda q: (q['arrival_ns'], q['ordinal'], q['id']))
        selected, scores, yielded = heft_pick(
            fifo, self.expected, waiting, idle,
            lambda q, b: self.place(q, b, now, active)['start'] <= now + 1e-9)
        return dict(out, selected=selected, candidates=scores, yielded_ids=yielded,
                    expected_ns=dict(self.expected))


def simulate(frozen, initial, tickets, context, policy, environment=None):
    """Only new adapters wrap the frozen engine; old controllers are unchanged."""
    if policy == BAND:
        controller = BandController(frozen, initial)
    elif policy in (ENTE, ALWAYS):
        controller = GateController(frozen, initial, environment, policy == ENTE)
    elif policy == joint.LABEL:
        controller = joint.Controller(frozen, initial)
    elif policy in ('SHARED_EDF', 'SHARED_EFT'):
        from tools import d1_queue_ppo as shared
        controller = shared.Controller(frozen, initial, policy)
    elif policy in p.POLICIES:
        controller = p.Controller(frozen, initial, p.profile(frozen), policy)
    else:
        raise ValueError('unknown fixed policy')
    actual = p.profile(frozen, context)
    vectors = dict(cells={k: [dict(source_request_id='shared_development_context_' + context,
                                  durations_ns=v) for _ in range(4)] for k, v in actual.items()})
    result = old.engine.simulate(dict(protocol=p.VERSION, cells=p.profile(frozen)), vectors,
                                 tickets, policy=controller.policy, settings=settings(), seed=201,
                                 decision_provider=controller)
    return result, controller
