"""Reviewed retained-calendar correction with a total displacement bound.

This opt-in adapter preserves the original rule and plant. Rejected numerical
placements reject only their candidate; telemetry never enters the ranking.
"""
from __future__ import annotations

import copy
import math
from tools import d1_reserved_thermal as rule

PUBLIC_POLICY = 'RESERVED_THERMAL_REQUEST_V1_NUMERIC_R2'


class NumericConflict(ValueError):
    pass


class BoundedPlacement:
    def __init__(self, forecaster, telemetry=None):
        self.forecaster = forecaster
        self.telemetry = telemetry if telemetry is not None else []

    def place(self, request, backend, earliest, jobs):
        initial_start = None
        event = dict(request_id=request['id'], backend=backend, earliest_s=earliest,
                     proposed_start_s=None, corrected_start_s=None, displacement_s=None,
                     accepted=False, reason=None)
        self.telemetry.append(event)
        for _ in range(len(jobs)+1):
            job = self.forecaster.place(request, backend, earliest, jobs)
            if initial_start is None:
                initial_start = job['start']
                event['proposed_start_s'] = initial_start
            shift = job['start']-initial_start
            event.update(corrected_start_s=job['start'], displacement_s=shift)
            if shift < 0 or shift > rule.EPS:
                event['reason'] = 'numeric_total_displacement_exceeded'
                raise NumericConflict(event['reason'])
            conflicts = [j for j in jobs if job['start'] < j['end'] and job['end'] > j['start']
                and (j['backend'] == backend or
                     '+'.join(sorted((job['state'], j['state']))) not in rule.P.STATES)]
            if not conflicts:
                event.update(accepted=True, reason='unchanged' if shift == 0 else 'numeric_boundary_snap')
                return job
            if any(min(job['end'], j['end'])-max(job['start'], j['start']) > rule.EPS
                   for j in conflicts):
                event['reason'] = 'numeric_overlap_exceeded'
                raise NumericConflict(event['reason'])
            next_start = max(job['start'], max(j['end'] for j in conflicts))
            if next_start-initial_start > rule.EPS:
                event.update(reason='numeric_total_displacement_exceeded',
                             required_start_s=next_start, required_displacement_s=next_start-initial_start)
                raise NumericConflict(event['reason'])
            earliest = next_start
        event['reason'] = 'numeric_placement_not_converged'
        raise NumericConflict(event['reason'])


def effective_action(first, now_ns, lanes):
    """Signature of the original rule's actual return, using public lane ownership."""
    if first is None:
        return dict(kind='REJECTED', signature=['REJECTED'])
    now = now_ns/1e9
    backend = first['backend']
    available = lanes[backend]['request'] is None
    if first['start'] <= now+rule.EPS:
        if not available:
            return dict(kind='INVALID_BUSY_DISPATCH', signature=['INVALID_BUSY_DISPATCH', first['id'], backend])
        return dict(kind='DISPATCH', signature=['DISPATCH', first['id'], backend])
    wake = max(now_ns+1, round(min(first['start'], now+rule.P.WAIT_STEP)*1e9))
    return dict(kind='WAIT', signature=['WAIT', wake], wait_until_ns=wake)


class Controller(rule.Controller):
    def __init__(self, frozen, initial):
        super().__init__(frozen, initial)
        self.numeric_events = []
        self.action_audit = []
        self._candidate_details = {}
        self._lanes = {b: dict(request=None) for b in ('CPU', 'GPU')}

    def finish_retained(self, sequence, queue, active, now, forecaster):
        return super().finish_retained(sequence, queue, active, now,
            BoundedPlacement(forecaster, self.numeric_events))

    def _evaluate(self, sequence, queue, active, running, now, eligible_first_ids, retained=False):
        begin = len(self.numeric_events)
        try:
            item = super()._evaluate(sequence, queue, active, running, now, eligible_first_ids, retained)
        except NumericConflict as error:
            item = dict(sequence=sequence, jobs=[], first=None, score=None,
                reasons=[str(error)], violations=[], rank=(math.inf, math.inf, math.inf, sequence),
                retained=retained, calendar_changes=[])
        first = item['first']
        self._candidate_details[(retained, sequence)] = dict(
            first_start_s=first['start'] if first else None,
            first_request_id=first['id'] if first else None,
            first_backend=first['backend'] if first else None,
            effective_action=effective_action(first, round(now*1e9), self._lanes),
            numeric_events=copy.deepcopy(self.numeric_events[begin:]))
        return item

    def search(self, *args):
        self._candidate_details = {}
        chosen, log = super().search(*args)
        for candidate in log['candidates']:
            seq = tuple(tuple(v) for v in candidate['sequence'])
            candidate.update(self._candidate_details[(candidate['retained'], seq)])
        return chosen, log

    def decide(self, config, queue, lanes, now_ns, settings, thermal_model, current_ap):
        self._lanes = lanes
        out = super().decide(config, queue, lanes, now_ns, settings, thermal_model, current_ap)
        selected = out.get('selected')
        signature = (['DISPATCH', selected['request_id'], selected['backend']] if selected else
                     ['WAIT', out['wait_until_ns']] if 'wait_until_ns' in out else ['WAIT_FOR_EVENT'])
        self.action_audit.append(dict(now_ns=now_ns, reason=out['reason'], signature=signature))
        out['public_policy'] = PUBLIC_POLICY
        return out


def simulate(frozen, initial, tickets, context, before_environment):
    if not callable(before_environment):
        raise ValueError('registered environment budget required')
    before_environment()
    c = Controller(frozen, initial)
    vectors = dict(cells={key: [dict(source_request_id='fixed_'+context, durations_ns=values)
        for _ in range(4)] for key, values in rule.P.profile(frozen, context).items()})
    result = rule.X.old.engine.simulate(dict(protocol=rule.P.VERSION, cells=rule.P.profile(frozen)),
        vectors, tickets, policy=c.policy, settings=rule.X.settings(), seed=201, decision_provider=c)
    row, segments, costs = rule.X.outcome(result, initial, frozen)
    c.terminal_audit(row, result)
    row.update(policy=PUBLIC_POLICY, diagnostic_events=len(c.book.breaks),
        arrival_transactions=len(c.book.transactions), projections=c.projections,
        projection_host_s=c.projection_host_s,
        decision_host_total_s=sum(c.callback_times),
        decision_host_max_ms=1000*max(c.callback_times, default=0.))
    return row, result, c, (segments, costs)
