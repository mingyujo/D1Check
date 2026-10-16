"""Review candidate: persistent arrived-queue reservations and energy credit.

The legacy engine ABI is retained; PUBLIC_POLICY identifies this adapter.
The reservation/credit equations require Astra review before a performance batch.
No guarantee about future arrivals, realized service, or device costs is claimed.
"""
from __future__ import annotations

import copy
import math
import time
from tools import d1_pareto_beam as legacy

P, X = legacy.p, legacy.x
PUBLIC_POLICY = 'RESERVED_THERMAL_REQUEST_V1'
EPS = 1e-9  # Existing numerical comparison epsilon, not a physical error bound.
MAX_EXPANSIONS, BEAM_WIDTH, DEPTH = 64, 8, 4


def specification():
    return dict(version='reserved-thermal-review-candidate-v2', public_policy=PUBLIC_POLICY,
        engine_abi_policy=legacy.POLICY, review_required_before_pilot=True,
        reservation='cap_i=min(original deadline_i, long-context initial EFT response_i); never relaxed',
        energy_initial='B=C_observed+J_remaining(EFT of arrived queue)',
        energy_arrival='B+=J_remaining(EFT of full queue)-J_remaining(EFT of old queue), at same snapshot',
        energy_other_events='no budget renewal; observed prefix remains spent',
        energy_veto='C_observed+J_remaining(candidate)>B+numerical epsilon',
        full_calendar=True, prefix_cost_veto=False, maximum_expansions=MAX_EXPANSIONS,
        beam_width=BEAM_WIDTH, depth=DEPTH, wait_step_s=P.WAIT_STEP, wait_limit_s=P.WAIT_LIMIT,
        rank=['predicted running AP peak', 'predicted total J', 'urgent predicted response', 'sequence'],
        future_arrivals=False, predicted_lane_release=False, model_costs_only=True,
        ap_window_s=[35, 180], energy_window_s=[0, 120], physical_safety_guarantee=False,
        retained_calendar='preserve each pending absolute start lower bound; log expiry or conflict',
        terminal_budget='B_final-J_common_0_120; partial work separately marked',
        pending_reservation='first seen and issued times separate during unknown overrun',
        diagnostics='candidate rejection, callback fallback and actual request violation separate')


class ReservationBook:
    """Caps are issued once; arrival credit is an explicit signed transaction."""
    def __init__(self):
        self.caps = {}
        self.issued = set()
        self.budget_j = None
        self.disabled = False
        self.transactions = []
        self.breaks = []
        self._break_keys = set()
        self.calendar = []
        self.first_seen = {}
        self.pending = {}

    def see(self, now, queue):
        for q in queue:
            rid = q['id']
            self.first_seen.setdefault(rid, now)
            if rid not in self.issued:
                self.pending.setdefault(rid, self.first_seen[rid])

    def admit(self, now, jobs, new_ids, first_total_j, arrival_credit_j):
        new_ids = set(new_ids)
        if new_ids & self.issued:
            raise ValueError('reservation or arrival credit cannot be issued twice')
        before = self.budget_j
        for j in jobs:
            if j['id'] in new_ids:
                self.caps[j['id']] = min(j['deadline'], j['response'])
        if new_ids != {j['id'] for j in jobs if j['id'] in new_ids}:
            raise ValueError('new reservation missing from completed calendar')
        if not self.issued:
            self.budget_j = first_total_j
        elif new_ids:
            if self.budget_j is None or arrival_credit_j is None:
                self.disabled = True
            else:
                self.budget_j += arrival_credit_j
        if self.budget_j is None:
            self.disabled = True
        self.issued |= new_ids
        for rid in new_ids:
            self.pending.pop(rid, None)
        self.transactions.append(dict(now_s=now, new_ids=sorted(new_ids), before_j=before,
            signed_arrival_credit_j=arrival_credit_j, after_j=self.budget_j,
            issued_caps={rid: self.caps[rid] for rid in sorted(new_ids)},
            first_seen_s={rid: self.first_seen.get(rid, now) for rid in sorted(new_ids)}))

    def violations(self, jobs):
        return [j['id'] for j in jobs if not j['already_responded'] and
                (j['id'] not in self.caps or j['response'] > self.caps[j['id']] + EPS)]

    def accepts_energy(self, total_j):
        return not self.disabled and self.budget_j is not None and total_j <= self.budget_j + EPS

    def broken(self, now, reason, ids, **details):
        key = (reason, tuple(sorted(ids)))
        if key not in self._break_keys:
            self._break_keys.add(key)
            self.breaks.append(dict(now_s=now, reason=reason, ids=list(key[1]),
                caps={rid: self.caps[rid] for rid in key[1] if rid in self.caps},
                budget_j=self.budget_j, **details))


class Controller(legacy.Controller):
    def __init__(self, frozen, initial):
        super().__init__(frozen, initial)
        self.book = ReservationBook()
        self.observed_j = 0.
        self.running_peak_c = None
        self.observed_responses = {}
        self.projections = 0
        self.projection_host_s = 0.

    def observe(self, now_ns, lanes):
        now = now_ns / 1e9
        if now < self.now - EPS:
            raise ValueError('time reversal')
        a, b = min(self.now, P.END), min(now, P.END)
        label = 'idle' if self.label == 'resident_idle' else self.label
        increment = 0. if label == 'idle' else self.frozen['energy_increment_w'][label]
        self.observed_j += (b-a) * (self.initial['preload_power_w'] + increment)
        start = max(self.now, self.init['anchor_s'])
        if now > start:
            ap = self.frozen['ap']; slopes = ap['parameters']['ap_slope_at_30_c_per_s']
            u = slopes[self.label] - slopes['resident_idle']
            samples = {max(35., start), min(now, P.AP_END)}
            samples |= {float(t) for t in range(max(35, math.ceil(start)), min(180, math.floor(now))+1)}
            for at in sorted(samples):
                if not max(35., start) <= at <= min(now, P.AP_END):
                    continue
                value = P.thermal_step(self.t, self.h, u, self.init['reference_c'], ap, at-start)[0]
                self.running_peak_c = value if self.running_peak_c is None else max(self.running_peak_c, value)
        P.Controller.observe(self, now_ns, lanes)
        for lane in lanes.values():
            q = lane['request']
            if q is None or q['id'] in self.observed_responses:
                continue
            target = 'OUTPUT_READY' if q['priority'] == 'urgent' else 'PERSISTED'
            if lane['phase'] == target:
                at = lane['since']/1e9
                self.observed_responses[q['id']] = at
                cap = self.book.caps.get(q['id'])
                if cap is not None and at > cap + EPS:
                    self.book.broken(now, 'reservation_observed_violation', [q['id']])
        # Observation continues after the last decision/queue item.
        if any(l['request'] for l in lanes.values()) and (
                self.active_jobs(lanes, now) is None or self.long.active_jobs(lanes, now) is None):
            self.book.broken(now, 'observed_overrun',
                [l['request']['id'] for l in lanes.values() if l['request']])
        if self.book.budget_j is not None and self.observed_j > self.book.budget_j + EPS:
            self.book.broken(now, 'observed_energy_budget_exceeded', [], observed_j=self.observed_j)

    def plan_score(self, jobs, now):
        self.projections += 1
        began = time.perf_counter()
        try:
            return self._plan_score(jobs, now)
        finally:
            self.projection_host_s += time.perf_counter()-began

    def _plan_score(self, jobs, now):
        if jobs:
            out = P.Controller.score(self, jobs, now)
        else:
            peak = self.t
            for at in sorted({P.AP_END} | {float(t) for t in range(math.ceil(now), 181) if t > now}):
                peak = max(peak, P.thermal_step(self.t, self.h, 0., self.init['reference_c'],
                    self.frozen['ap'], at-now)[0])
            out = dict(remaining_energy_j=self.initial['preload_power_w'] * max(0., P.END-now),
                predicted_peak_ap_c=peak, deadline_misses=0, total_lateness_s=0.)
        if out is not None:
            out = dict(out, predicted_total_j=self.observed_j + out['remaining_energy_j'],
                predicted_running_peak_c=max(out['predicted_peak_ap_c'],
                    self.running_peak_c if self.running_peak_c is not None else out['predicted_peak_ap_c']))
        return out

    def eft_plan(self, queue, active, now, forecaster):
        jobs = copy.deepcopy(active)
        first = None
        for q in queue:
            j = min((forecaster.place(q, b, now, jobs) for b in P.backends(q)),
                key=lambda v: (v['response'], v['backend'] != 'CPU'))
            jobs.append(j)
            if first is None:
                first = j
        return jobs, first

    def _retained_sequence(self, queue, now):
        by_id = {q['id']: q for q in queue}
        saved = sorted((j for j in self.book.calendar if j['id'] in by_id),
            key=lambda j: (j['start'], j['id']))
        if not saved:
            return None
        expired = [j['id'] for j in saved if j['start'] < now-EPS]
        if expired:
            self.book.broken(now, 'retained_calendar_expired', expired)
            return None
        return tuple((j['id'], j['backend'], max(0., j['start']-now)) for j in saved)

    def finish_retained(self, sequence, queue, active, now, forecaster):
        """Offsets are per-job absolute lower bounds relative to this snapshot."""
        jobs = copy.deepcopy(active)
        by_id = {q['id']: q for q in queue}
        first, used, errors = None, set(), []
        for rid, backend, offset in sequence:
            q = by_id[rid]
            earliest = max(now+offset, first['start'] if first else now)
            asap = forecaster.place(q, backend, first['start'] if first else now, jobs)
            job = forecaster.place(q, backend, earliest, jobs)
            if job['start'] > asap['start']+EPS and earliest > q['arrival_ns']/1e9+P.WAIT_LIMIT+EPS:
                errors.append('retained_wait_limit')
            if job['start'] > earliest+EPS:
                errors.append('retained_conflict_shift')
            jobs.append(job); used.add(rid)
            if first is None:
                first = job
        for q in queue:
            if q['id'] not in used:
                job = min((forecaster.place(q, b, first['start'], jobs) for b in P.backends(q)),
                    key=lambda j: (j['response'], j['backend'] != 'CPU'))
                jobs.append(job)
        return jobs, first, sorted(set(errors))

    def _evaluate(self, sequence, queue, active, running, now, eligible_first_ids, retained=False):
        if retained:
            jobs, first, shifts = self.finish_retained(sequence, queue, active, now, self)
            guard_jobs, _, guard_shifts = self.finish_retained(sequence, queue, running, now, self.long)
        else:
            jobs, first = self.finish_plan(sequence, queue, active, now, self)
            guard_jobs, _ = self.finish_plan(sequence, queue, running, now, self.long)
            shifts, guard_shifts = [], []
        score = self.plan_score(jobs, now)
        reasons = []
        if 'retained_wait_limit' in shifts or 'retained_wait_limit' in guard_shifts:
            reasons.append('wait_limit')
        if sequence[0][0] not in eligible_first_ids:
            reasons.append('aging')
        if first['start'] > now + P.WAIT_LIMIT + EPS:
            reasons.append('wait_limit')
        violations = self.book.violations(guard_jobs)
        if violations:
            reasons.append('reservation_predicted_violation')
        if score is None:
            reasons.append('completion_window_unavailable')
        elif not self.book.accepts_energy(score['predicted_total_j']):
            reasons.append('energy_budget_rejection')
        if score is None:
            rank = (math.inf, math.inf, math.inf, sequence)
        else:
            urgent = max((j['response'] for j in jobs if j['state'].startswith('classification_')
                and not j['already_responded']), default=now)
            rank = (round(score['predicted_running_peak_c'], 9), round(score['predicted_total_j'], 9),
                urgent, sequence)
        return dict(sequence=sequence, jobs=jobs, first=first, score=score, reasons=reasons,
            violations=violations, rank=rank, retained=retained,
            calendar_changes=sorted(set(shifts+guard_shifts)))

    def search(self, queue, active, running, now, backend, settings):
        aged = [q for q in queue if now-q['arrival_ns']/1e9 >= settings['aging_ns']/1e9]
        pool = queue[:DEPTH]
        first_pool = aged[:DEPTH] if aged else pool
        allowed_first = {q['id'] for q in first_pool}
        reference = ((queue[0]['id'], backend, 0.),)
        evaluated = {}

        def evaluate(seq, retained=False):
            key = (retained, seq)
            if key not in evaluated:
                evaluated[key] = self._evaluate(seq, queue, active, running, now, allowed_first, retained)
            return evaluated[key]

        evaluate(reference)
        retained = self._retained_sequence(queue, now)
        if retained:
            evaluate(retained, True)
        nodes, expanded = [tuple()], 0
        for depth in range(min(DEPTH, len(pool))):
            layer = []
            for seq in nodes:
                used = {v[0] for v in seq}
                for q in (first_pool if depth == 0 else pool):
                    if q['id'] in used:
                        continue
                    for b in P.backends(q):
                        waits = (0., min(P.WAIT_STEP, max(0., P.WAIT_LIMIT-(now-q['arrival_ns']/1e9)))) if depth == 0 else (0.,)
                        for wait in sorted(set(waits)):
                            if expanded >= MAX_EXPANSIONS:
                                break
                            new = seq + ((q['id'], b, wait),)
                            expanded += 1
                            item = evaluate(new)
                            # Keep prefixes using completed-calendar rank, even
                            # when their current reservation/J test rejects them.
                            layer.append(item)
                        if expanded >= MAX_EXPANSIONS:
                            break
                    if expanded >= MAX_EXPANSIONS:
                        break
                if expanded >= MAX_EXPANSIONS:
                    break
            if not layer:
                break
            nodes = [x['sequence'] for x in sorted(layer, key=lambda x: x['rank'])[:BEAM_WIDTH]]
            if expanded >= MAX_EXPANSIONS:
                break
        admitted = [x for x in evaluated.values() if not x['reasons']]
        chosen = min(admitted, key=lambda x: x['rank']) if admitted else None
        return chosen, dict(expanded=expanded, evaluated=len(evaluated), admitted=len(admitted),
            maximum_depth_reached=max((len(x['sequence']) for x in evaluated.values() if not x['retained']), default=0),
            expansion_limit_reached=expanded >= MAX_EXPANSIONS,
            rejected_reservation=sum('reservation_predicted_violation' in x['reasons'] for x in evaluated.values()),
            rejected_energy=sum('energy_budget_rejection' in x['reasons'] for x in evaluated.values()),
            completed_calendar_before_veto=True,
            candidates=[dict(sequence=x['sequence'], retained=x['retained'], reasons=x['reasons'],
                violations=x['violations'], calendar_changes=x['calendar_changes'],
                predicted_total_j=x['score']['predicted_total_j'] if x['score'] else None,
                predicted_peak_ap_c=x['score']['predicted_running_peak_c'] if x['score'] else None)
                for x in evaluated.values()])

    def decide(self, config, queue, lanes, now_ns, settings, thermal_model, current_ap):
        ref = P.Controller.__call__(self, config, queue, lanes, now_ns, settings, thermal_model, current_ap)
        if not queue:
            return ref
        now = now_ns/1e9
        qs = X.ordered(queue, now_ns, settings)
        self.book.see(now, qs)
        active, running = self.active_jobs(lanes, now), self.long.active_jobs(lanes, now)
        if active is None or running is None:
            self.book.broken(now, 'observed_overrun', [v['request']['id'] for v in lanes.values() if v['request']])
            return dict(ref, reason='reserved_observed_overrun_EFT', public_policy=PUBLIC_POLICY)
        if 'chosen_backend' not in ref:
            return ref
        mean_ref, _ = self.eft_plan(qs, active, now, self)
        long_ref, _ = self.eft_plan(qs, running, now, self.long)
        new_ids = {q['id'] for q in qs} - self.book.issued
        if new_ids:
            all_score = self.plan_score(mean_ref, now)
            old_qs = [q for q in qs if q['id'] not in new_ids]
            old_jobs, _ = self.eft_plan(old_qs, active, now, self)
            old_score = self.plan_score(old_jobs, now)
            credit = (all_score['remaining_energy_j']-old_score['remaining_energy_j']
                if all_score is not None and old_score is not None else None)
            self.book.admit(now, long_ref, new_ids,
                all_score['predicted_total_j'] if all_score is not None else None, credit)
        chosen, log = self.search(qs, active, running, now, ref['chosen_backend'], settings)
        log.update(now_ns=now_ns, arrived_ids=[q['id'] for q in qs], observed_j=self.observed_j,
            running_peak_ap_c=self.running_peak_c, budget_j=self.book.budget_j,
            immutable_caps=dict(self.book.caps), new_ids=sorted(new_ids))
        self.records.append(log)
        if chosen is None:
            reasons = sorted({reason for item in log['candidates'] for reason in item['reasons']})
            violated = sorted({rid for item in log['candidates'] for rid in item['violations']})
            if violated:
                self.book.broken(now, 'reservation_predicted_violation', violated)
            self.book.broken(now, 'search_exhausted_no_admitted', [], rejection_reasons=reasons)
            log['selected'] = 'EFT_fallback'
            log['fallback_reasons'] = reasons
            return dict(ref, reason='reserved_no_admitted_calendar_EFT', public_policy=PUBLIC_POLICY)
        self.book.calendar = copy.deepcopy(chosen['jobs'])
        sequence, first = chosen['sequence'], chosen['first']
        origin = ('retained' if chosen['retained'] else 'reference' if sequence == ((qs[0]['id'], ref['chosen_backend'], 0.),) else 'search')
        log.update(selected=sequence, selected_origin=origin,
            selected_calendar=copy.deepcopy(chosen['jobs']),
            selected_total_j=chosen['score']['predicted_total_j'], calendar_changes=chosen['calendar_changes'])
        for change in chosen['calendar_changes']:
            self.book.broken(now, change, [j['id'] for j in chosen['jobs']])
        rid, backend, wait = sequence[0]
        out = dict(now_ns=now_ns, selected=None, public_policy=PUBLIC_POLICY, reason=PUBLIC_POLICY,
            chosen_request_id=rid, chosen_backend=backend, chosen_explicit_delay_s=wait,
            planned_start_s=first['start'], modeled_ap_c=self.t,
            local_deviation=(rid, backend, wait) != (qs[0]['id'], ref['chosen_backend'], 0.))
        if first['start'] <= now + EPS:
            out['selected'] = dict(request_id=rid, backend=backend)
        else:
            out['wait_until_ns'] = max(now_ns+1, round(min(first['start'], now+P.WAIT_STEP)*1e9))
        return out

    def terminal_audit(self, row, result):
        """Final accounting is retrospective; it never affects online decisions."""
        for job in result['ledger']:
            if 'response_ns' in job:
                at = (job['arrival_ns']+job['response_ns'])/1e9
                self.observed_responses.setdefault(job['id'], at)
                if job['id'] in self.book.caps and at > self.book.caps[job['id']]+EPS:
                    self.book.broken(at, 'reservation_observed_violation', [job['id']])
        energy = row['energy_j']
        available = energy is not None and math.isfinite(energy)
        budget = self.book.budget_j
        margin = budget-energy if available and budget is not None and not self.book.disabled else None
        row.update(final_budget_j=budget, final_common_window_j=energy,
            final_budget_margin_j=margin, final_budget_satisfied=margin >= -EPS if margin is not None else None,
            final_cost_available=available, final_full_work=row['completed']==row['planned'],
            final_energy_partial_work=row['completed']!=row['planned'],
            pending_reservations=len(self.book.pending),
            observed_cap_violation_requests=len({rid for event in self.book.breaks
                if event['reason']=='reservation_observed_violation' for rid in event['ids']}))
        if margin is not None and margin < -EPS:
            self.book.broken(P.END, 'terminal_energy_budget_exceeded', [], excess_j=-margin)
        for reason in ('reservation_predicted_violation','reservation_observed_violation','observed_overrun',
                       'search_exhausted_no_admitted','terminal_energy_budget_exceeded'):
            row[reason+'_events'] = sum(e['reason']==reason for e in self.book.breaks)
        for reason in ('reservation_predicted_violation','energy_budget_rejection','completion_window_unavailable'):
            row[reason+'_candidates'] = sum(reason in v['reasons'] for record in self.records for v in record['candidates'])
        row['fallback_callbacks'] = sum(record['selected']=='EFT_fallback' for record in self.records)
        row['maximum_depth_reached'] = max((v['maximum_depth_reached'] for v in self.records), default=0)
        row['expansion_limit_callbacks'] = sum(v['expansion_limit_reached'] for v in self.records)
        row['admitted_candidates'] = sum(v['admitted'] for v in self.records)


def simulate(frozen, initial, tickets, context, before_environment):
    """Require a caller-owned budget transaction before every engine start."""
    if not callable(before_environment):
        raise ValueError('registered environment budget required')
    before_environment()
    c = Controller(frozen, initial)
    vectors = dict(cells={key: [dict(source_request_id='fixed_'+context, durations_ns=values)
        for _ in range(4)] for key, values in P.profile(frozen, context).items()})
    result = X.old.engine.simulate(dict(protocol=P.VERSION, cells=P.profile(frozen)), vectors, tickets,
        policy=c.policy, settings=X.settings(), seed=201, decision_provider=c)
    row, segments, costs = X.outcome(result, initial, frozen)
    c.terminal_audit(row, result)
    row.update(policy=PUBLIC_POLICY, diagnostic_events=len(c.book.breaks),
        arrival_transactions=len(c.book.transactions), projections=c.projections,
        projection_host_s=c.projection_host_s,
        decision_host_total_s=sum(c.callback_times),
        decision_host_max_ms=1000*max(c.callback_times, default=0.))
    return row, result, c, (segments, costs)
