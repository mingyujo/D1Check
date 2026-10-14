"""Isolated M6 development cost runtime; shared dynamics/PPO remain frozen.

Heating retains the separated-heat06 basis beta.  Only the legacy initial
recovery uses initial_beta_per_s.  No source/global monkey patch is needed.
"""
from __future__ import annotations

import copy
import math

import numpy as np

from tools import d1_sched_dynamics_plant as base
from tools import d1_s26_observer_separate_heat as separate
from tools import d1_s26_pair_observer_model as observer
from tools.d1_s26_cost_refine_model import current_vector

COST_ABI = 's26-m6-decoupled-initial-cost-v1'
ABI = COST_ABI
SCHEMA = 'd1-s26-m6-development-event-plant-v1'
HORIZON_NS = base.HORIZON_NS
BACKENDS = base.BACKENDS


def validate(cost):
    if cost.get('abi') != COST_ABI:
        raise ValueError('explicit M6 decoupled cost ABI required')
    converted = copy.deepcopy(cost)
    converted['abi'] = separate.ABI
    separate.validate(converted)
    for sensor, model in cost['thermal'].items():
        beta = model.get('initial_beta_per_s')
        if isinstance(beta, bool) or not isinstance(beta, (int, float, np.floating)) or not math.isfinite(beta) or beta <= 0:
            raise ValueError('finite positive M6 initial beta required: ' + sensor)
    return cost


def initial_terms(model, init, sensor, times):
    """Legacy initial recovery beta is independent of heating/filter beta."""
    if model['initial_mode'] != 'legacy':
        return observer.initial_terms(model, init, sensor, times)
    times = np.asarray(times, dtype=float)
    initial = init['initial_c'][sensor]
    reference = init['reference_c'][sensor]
    beta = model['initial_beta_per_s']
    decay = np.exp(-beta * times)
    value = reference + (initial - reference) * decay
    area = reference * times + (initial - reference) * (1 - decay) / beta
    zeros = np.zeros((len(times), 2))
    return value, zeros, area, zeros.copy()


class CostState(separate.CostState):
    def __init__(self, cost, init):
        validate(cost)
        converted = copy.deepcopy(cost)
        converted['abi'] = separate.ABI
        # Converted headers pass the frozen06 validator; thermal beta is not
        # rewritten. The new initial-beta fields survive this conversion.
        super().__init__(converted, copy.deepcopy(init))
        self.profile = copy.deepcopy(cost)

    def temperature(self, sensor):
        model = self.profile['thermal'][sensor]
        elapsed = self.now - self.anchor
        heat, _ = self._history(sensor, max(0., elapsed - model['delay_s']))
        initial, recovery, _, _ = initial_terms(model, self.init, sensor, [elapsed])
        return float(initial[0] + heat @ model['coefficients'][:6] + recovery[0] @ model['coefficients'][6:])

    def advance(self, to):
        if not math.isfinite(to) or to < self.now:
            raise ValueError('M6 cost boundary clock')
        occupied = current_vector(self.owners, 'task')
        while self.now < to:
            nxt = min(to, (math.floor((self.now-self.anchor)*4+1e-9)+1)/4+self.anchor)
            elapsed = nxt-self.anchor
            self.power_basis.advance(elapsed, occupied)
            for basis in self.basis.values():
                basis.advance(elapsed, occupied)
            self.now = nxt
            self.hist_times.append(elapsed)
            for sensor, basis in self.basis.items():
                self.hist[sensor].append(((basis.mix*basis.fast+(1-basis.mix)*basis.slow).copy(), basis.heat_area.copy()))
            # Byte-identical algebra to separated-heat06 energy; new initial
            # beta does not alter the power basis or integrated energy.
            self.energy = self.init['energy_prefix_estimate_j'] + self.init['baseline_w']*elapsed + float(self.power_basis.area @ self.profile['power']['coefficients'])
            for sensor, model in self.profile['thermal'].items():
                _, heat_area = self._history(sensor, max(0., elapsed-model['delay_s']))
                _, _, initial_area, recovery_area = initial_terms(model, self.init, sensor, [elapsed])
                self.temperature_area[sensor] = self.init['temperature_prefix_area'][sensor] + float(initial_area[0] + heat_area @ model['coefficients'][:6] + recovery_area[0] @ model['coefficients'][6:])
            if self.now == 35:
                self.area_at35 = dict(self.temperature_area)
            self._record()
        return self.snapshot()


class Device(base.Device):
    """New cost anchor only; the event/service/public-state contract is V17."""
    def __init__(self, profile, *args, **kwargs):
        original = copy.deepcopy(profile)
        cost = original['cost_anchor']
        new_model = cost.get('abi') == COST_ABI
        if not new_model:
            # Frozen06 is supported as a separate baseline in the same loop.
            super().__init__(original, *args, **kwargs)
            return
        validate(cost)
        if original['device'] != 'S26' or cost['mode'] != 'START0':
            raise ValueError('M6 dynamics anchor requires S26 START0')
        converted = copy.deepcopy(original)
        converted['cost_anchor']['abi'] = separate.ABI
        super().__init__(converted, *args, **kwargs)
        # At t0 both initial equations return the exact same boundary values.
        # No policy has run and no owner/history of real work is discarded.
        boundary = copy.deepcopy(self._anchor.init)
        self._anchor = CostState(cost, boundary)
        self.profile = original
        self._record(force=True)


def simulate(profile, requests, controller, split='confirm', environment_seed=0, npu=True, deterministic=False, initial=None, step_s=None):
    """Fresh event execution, not an offline cost projection of an old ledger."""
    if not requests or len(requests) > 1200 or len({q['id'] for q in requests}) != len(requests):
        raise ValueError('bounded distinct roster')
    for request in requests:
        base.validate_request(request)
    dev = Device(profile, split=split, environment_seed=environment_seed, npu=npu, deterministic=deterministic, initial=initial, step_s=step_s)
    pending = sorted(copy.deepcopy(requests), key=lambda q: (q['arrival_ns'], q['ordinal'], q['id']))
    waiting = []
    cursor = 0
    last_revision = None
    while dev.now < HORIZON_NS:
        dev.advance(dev.now)
        new_arrival = False
        while cursor < len(pending) and pending[cursor]['arrival_ns'] <= dev.now:
            waiting.append(pending[cursor])
            cursor += 1
            new_arrival = True
        if waiting and (new_arrival or dev.decision_revision != last_revision):
            last_revision = dev.decision_revision
            jobs = controller.choose(dev, waiting)
            if jobs:
                dev.dispatch(jobs)
                ids = {q['id'] for q, backend in jobs}
                waiting = [q for q in waiting if q['id'] not in ids]
                continue
        if cursor == len(pending) and not waiting and not dev._work:
            break
        times = [HORIZON_NS]
        if cursor < len(pending):
            times.append(pending[cursor]['arrival_ns'])
        if dev.next_event() is not None:
            times.append(dev.next_event())
        dev.advance(min(t for t in times if t > dev.now))
    service_end = dev.now
    dev.advance(HORIZON_NS)
    ledger = []
    for request in requests:
        row = copy.deepcopy(dev.records.get(request['id'], dict(request, status='unfinished')))
        if row['status'] == 'running':
            row['status'] = 'unfinished'
        ledger.append(row)
    metrics = base.old.metrics(ledger)
    costs = copy.deepcopy(dev.current_cost())
    complete = metrics['incomplete'] == 0
    learning_trace = copy.deepcopy(dev.learning_cost_trace)
    trace120 = copy.deepcopy(dev.cost_trace)
    all_available = not any(dev._owners.values())
    cooling = copy.deepcopy(dev.observe_cooling()) if all_available else None
    is_m6 = profile['cost_anchor'].get('abi') == COST_ABI
    metrics.update(
        energy_j=costs['energy_window_j'] if complete else None,
        energy_prefix_j=costs['energy_window_j'], resident_baseline_j=dev.initial['baseline_w']*120.,
        planned_work_units=sum(q.get('work_units', 1) for q in requests),
        completed_work_units=sum(r.get('work_units', 1) for r in ledger if r['status'] == 'succeeded'),
        mean_ap_c=cooling['mean_after35_c'] if complete and cooling else None,
        peak_ap_c=cooling['peak_after35_c'] if complete and cooling else None,
        mean_ap_0_120_c=costs['mean_ap_c'], peak_ap_0_120_c=costs['peak_ap_c'],
        ap_excess_area_c_s=costs['ap_excess_area_c_s'],
        cost_model_status='M6_development_only' if is_m6 else 'frozen06_baseline',
        hardware_validated=False, strict_eligible=False, experiment_ready=False)
    return dict(
        schema=SCHEMA, device=dev.device, profile=profile['name'], metrics=metrics,
        ledger=ledger, events=dev.events, service_end_ns=service_end, end_ns=HORIZON_NS,
        environment_seed=environment_seed, split=split, npu=dev.npu,
        cost_120=costs, cooling_180=cooling, cost_trace=dev.cost_trace,
        prefix_trace120=trace120, learning_cost_trace=learning_trace,
        cooling_status='provided; all actual AVAILABLE at120' if all_available else 'UNAVAILABLE; unfinished owner at120',
        integration_segments=dev.integration_segments, policy_cost_learning=False,
        hardware_validated=False, strict_eligible=False, experiment_ready=False)
