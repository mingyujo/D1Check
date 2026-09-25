"""REPLAN-PC-01: request-level background dispatch gate, PC functionality only.

No device API, fitted interference, static-selection optimizer or P tuning.
An optional event hook reuses the v3 engine; legacy default calls remain unchanged.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import heapq
import json
from pathlib import Path

from tools import d1_arrival_explore as engine
from tools import d1_cal03_connection as base

VERSION = 'arrival-interaction-pc-v1'
DEFAULT_IDLE_NS = 15_000_000_000
MAX_EVENTS = 128
MAX_HORIZON_NS = 600_000_000_000


class InteractionGate:
    """Engine-owned event calendar; never passed to choose(). Initial state: idle."""

    def __init__(self, interactions, idle_ns=DEFAULT_IDLE_NS, restrict_background=True):
        base.require(type(idle_ns) is int and idle_ns > 0, 'positive idle ns')
        base.require(type(restrict_background) is bool, 'boolean start permission')
        self.restrict_background = restrict_background
        base.require(len(interactions) <= MAX_EVENTS, 'bounded interaction input')
        for event in interactions:
            base.require(set(event) == {'id', 'at_ns'} and isinstance(event['id'], str)
                         and type(event['at_ns']) is int and event['at_ns'] >= 0,
                         'interaction schema')
        base.require(len({e['id'] for e in interactions}) == len(interactions), 'duplicate interaction ID')
        self._events = sorted(copy.deepcopy(interactions), key=lambda e: (e['at_ns'], e['id']))
        self._index = 0
        self._expiries = []
        self.idle_ns = idle_ns
        self.generation = 0
        self.last_interaction_ns = None
        self.blocked_until_ns = None
        self.events = []
        self.dispatch_checks = []

    def interactions_at(self, now):
        changed = False
        while self._index < len(self._events) and self._events[self._index]['at_ns'] <= now:
            event = self._events[self._index]
            base.require(event['at_ns'] == now, 'engine skipped interaction')
            self._index += 1
            self.generation += 1
            self.last_interaction_ns = event['at_ns']
            self.blocked_until_ns = event['at_ns'] + self.idle_ns
            heapq.heappush(self._expiries, (self.blocked_until_ns, self.generation))
            self.events.append(dict(event='interaction', at_ns=round(now), id=event['id'],
                                    generation=self.generation, blocked_until_ns=self.blocked_until_ns))
            changed = True
        return changed

    def expiries_at(self, now):
        changed = False
        while self._expiries and self._expiries[0][0] <= now:
            at, generation = heapq.heappop(self._expiries)
            base.require(at == now, 'engine skipped expiry')
            valid = generation == self.generation
            self.events.append(dict(event='timer_expired' if valid else 'stale_expiry_ignored',
                                    at_ns=at, generation=generation))
            changed |= valid
        return changed

    def next_event(self):
        times = []
        if self._index < len(self._events): times.append(self._events[self._index]['at_ns'])
        if self._expiries: times.append(self._expiries[0][0])
        return min(times) if times else None

    def blocked(self, now):
        return self.restrict_background and self.blocked_until_ns is not None and now < self.blocked_until_ns

    def eligible(self, queue, now):
        return [q for q in queue if q['priority'] == 'urgent' or not self.blocked(now)]

    def snapshot(self, queue, now):
        # Contains no future interactions, expiries from future interactions, or future tickets.
        return dict(last_interaction_ns=self.last_interaction_ns,
                    blocked_until_ns=self.blocked_until_ns, generation=self.generation,
                    restrict_background=self.restrict_background,
                    background_allowed=not self.blocked(now),
                    queued_ids=[q['id'] for q in queue],
                    blocked_ids=[q['id'] for q in queue if q['priority'] == 'normal' and self.blocked(now)])

    def check_dispatch(self, ticket, now, pending):
        allowed = ticket['priority'] == 'urgent' or not self.blocked(now)
        self.dispatch_checks.append(dict(at_ns=round(now), request_id=ticket['id'],
            backend=pending['selected']['backend'], allowed=allowed,
            reason='urgent_exempt' if ticket['priority']=='urgent' else
                   'unrestricted' if not self.restrict_background else
                   'idle_timer_allows' if allowed else 'cancelled_by_current_interaction_gate',
            decision_start_ns=pending['start'], spent_scheduler_ns=now-pending['start'],
            blocked_until_ns=self.blocked_until_ns, generation=self.generation,
            queue_retained=not allowed, lane_acquired=allowed))
        return allowed


def metrics(ledger, observation_end_ns, horizon_ns):
    normal = [r for r in ledger if r['priority'] == 'normal']
    urgent = [r for r in ledger if r['priority'] == 'urgent']
    def persisted(rs, limit):
        return sum('persist_complete_ns' in r and r['persist_complete_ns'] <= limit for r in rs)
    all_background = bool(normal) and persisted(normal, horizon_ns) == len(normal)
    last_persist = max(r['persist_complete_ns'] for r in normal) if all_background else None
    all_lanes = all('lane_available_ns' in r for r in ledger)
    return dict(observation_end_ns=observation_end_ns, horizon_ns=horizon_ns,
        planned=len(ledger), not_dispatched=sum('dispatch_ns' not in r for r in ledger),
        status_counts={s:sum(r['status']==s for r in ledger) for s in
                       ('succeeded','failed','rejected','expired','unfinished','not_arrived')},
        background_planned=len(normal), interactive_planned=len(urgent),
        background_persisted_at_observation_end=persisted(normal, observation_end_ns),
        background_persisted_at_horizon=persisted(normal, horizon_ns),
        background_unfinished_at_horizon=len(normal)-persisted(normal, horizon_ns),
        background_all_persisted_at_ns=last_persist,
        background_completion_time_ns=(last_persist-min(r['arrival_ns'] for r in normal)) if all_background else None,
        interactive_output_ready=sum('output_ready_ns' in r for r in urgent),
        all_lanes_released_at_ns=max(r['lane_available_ns'] for r in ledger) if all_lanes else None,
        cleanup='not_modelled', failure_model='unsupported; no device reliability inference')


def simulate(config, vectors, requests, interactions, *, settings, seed,
             observation_end_ns, drain_ns, restrict_background=True, idle_ns=DEFAULT_IDLE_NS,
             enabled=True):
    """Static mapping + common EDF/aging. Not the legacy CPU_URGENT FIFO baseline."""
    base.require(type(observation_end_ns) is int and observation_end_ns >= 0 and
                 type(drain_ns) is int and drain_ns >= 0, 'observation/drain ns')
    horizon = observation_end_ns + drain_ns
    base.require(0 < horizon <= MAX_HORIZON_NS, 'bounded common horizon')
    base.require(type(enabled) is bool, 'boolean feature flag')
    gate = InteractionGate(interactions, idle_ns, restrict_background)
    for q in requests:
        base.require(set(q)=={'id','task','priority','ordinal','arrival_ns','deadline_offset_ns'} and
                     q['priority'] in ('urgent','normal') and q['task'] in ('classification','detection')
                     and type(q['arrival_ns']) is int and 0 <= q['arrival_ns'] <= observation_end_ns,
                     'request outside common observation interval')
    base.require(all(e['at_ns'] <= observation_end_ns for e in interactions), 'interaction outside observation')
    last_expiry = max((e['at_ns']+idle_ns for e in interactions), default=None)
    base.require(last_expiry is None or last_expiry <= horizon, 'common drain excludes last timer expiry')
    base.require(set(settings['static_map']) == {'classification','detection'} and
                 set(settings['static_map'].values()) <= {'CPU','GPU'} and
                 type(settings['static_parallel']) is bool, 'static assignment contract')
    out = engine.simulate(config, vectors, requests, policy='B2_PC', settings=settings, seed=seed,
                          horizon_ns=horizon, admission=gate if enabled else None)
    out.update(version=VERSION, engine_version=engine.VERSION,
        policy='REPLAN_STATIC_PRIORITY_DEV', engine_policy='B2_PC',
        assignment_role='provided static assignment; B2 selection not performed here',
        evidence='PC functional/exploratory model only; not Ente reproduction or policy performance PASS',
        start_permission=('interaction_gate' if restrict_background else 'unrestricted') if enabled else 'legacy_feature_disabled',
        feature_enabled=enabled,
        idle_ns=idle_ns, initial_interaction_state='idle_no_timer',
        interaction_input=copy.deepcopy(interactions), interaction_events=gate.events,
        dispatch_gate_checks=gate.dispatch_checks, last_timer_expiry_ns=last_expiry,
        gate_processing_ns_assumption=0, cancelled_dispatches=sum(not c['allowed'] for c in gate.dispatch_checks),
        background_metrics=metrics(out['ledger'], observation_end_ns, horizon))
    return out


def comparison_matrix(frozen_assignments):
    """Cross both gates with CPU and each externally development-frozen assignment.

    No selection, tuning, score, evaluation scenario or future result is accepted.
    Duplicate assignments collapse; equal development candidate/budget is a plan gate.
    """
    base.require(len(frozen_assignments)<=2, 'at most two development winners; no search here')
    assignments=[dict(id='cpu_fixed',static_map=dict(classification='CPU',detection='CPU'),static_parallel=False)]
    seen={(('CPU','CPU'),False)}
    for a in frozen_assignments:
        base.require(set(a)=={'id','static_map','static_parallel','development_freeze_sha256'}, 'frozen assignment schema')
        digest=a['development_freeze_sha256']
        base.require(isinstance(digest,str) and len(digest)==64 and all(c in '0123456789abcdef' for c in digest),
                     'development freeze identifier required')
        base.require(set(a['static_map'])=={'classification','detection'} and
                     set(a['static_map'].values()) <= {'CPU','GPU'} and type(a['static_parallel']) is bool,
                     'static assignment')
        key=(tuple(a['static_map'][t] for t in ('classification','detection')), a['static_parallel'])
        if key not in seen: assignments.append(copy.deepcopy(a));seen.add(key)
    base.require(len({a['id'] for a in assignments})==len(assignments),'duplicate assignment ID')
    return [dict(assignment=a,restrict_background=gate) for a in assignments for gate in (False,True)]


def demo():
    # Explicitly synthetic, hand-calculable vectors. Never calibration/performance input.
    from tools.test_d1_cal03_connection import fixture, request
    config,vectors=fixture()
    # Toy units scaled to seconds: D->S=1, S->O=2, O->P=3, P->W=.4, W->L=.6.
    scale=100_000_000
    for cell in config['cells'].values():
        for stat in [*cell['observed_phases'].values(),*cell['joint'].values()]:
            for k in ('median_ns','min_ns','max_ns'): stat[k]*=scale
    for cell in vectors['cells'].values():
        for row in cell: row['durations_ns']=[x*scale for x in row['durations_ns']]
    requests=[request('background',priority='normal'),request('interactive',arrival=1_000_000_000,ordinal=1)]
    requests[1]['task']='detection'
    for q in requests:q['deadline_offset_ns']=100_000_000_000
    settings=dict(mode='strict',decision_ns=0,record_ns=0,dispatch_ns=0,aging_ns=4_000_000_000,
                  interference=1.,predicted_interference=1.5,estimate_factor=1.,
                  static_parallel=False,static_map=dict(classification='CPU',detection='CPU'))
    scenarios={'none':[], 'intermittent':[0,20_000_000_000], 'finite_burst':[0,1_000_000_000,2_000_000_000]}
    # Expected output/persist/release from adding [1,2,3,.4,.6] seconds per request.
    expected={'none':{'background':(0,3,6,7),'interactive':(7,10,13,14)},
              'intermittent':{'background':(15,18,21,22),'interactive':(1,4,7,8)},
              'finite_burst':{'background':(17,20,23,24),'interactive':(1,4,7,8)}}
    results={}
    for name,times in scenarios.items():
        events=[dict(id=f'op{i}',at_ns=t) for i,t in enumerate(times)]
        out=simulate(config,vectors,requests,events,settings=settings,seed=7,
                     observation_end_ns=20_000_000_000,drain_ns=20_000_000_000)
        actual={r['id']:tuple(r[k]/1e9 for k in ('dispatch_ns','output_ready_ns','persist_complete_ns','lane_available_ns'))
                for r in out['ledger']}
        base.require(actual==expected[name], 'hand-calculated demo mismatch: '+name)
        results[name]=dict(expected_seconds=expected[name],actual_seconds=actual,result=out)
    return dict(version=VERSION,purpose='three hand-calculated functionality traces; not a policy ranking',
                source='synthetic toy fixture; no measured timing fit',experiment_ready=False,scenarios=results)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--demo',action='store_true',required=True,help='Only synthetic functionality demo; no batch/device path')
    parser.add_argument('--output',type=Path,required=True,help='New JSON file; refuses overwrite')
    args=parser.parse_args()
    result=demo()
    result['source_sha256']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in
                            (Path(__file__),Path(engine.__file__),Path(base.__file__),
                             Path(__file__).with_name('test_d1_cal03_connection.py'))}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',encoding='utf-8') as stream:
        json.dump(result,stream,indent=2,ensure_ascii=False)
    print(json.dumps(dict(output=str(args.output),traces=3,hand_calculation_match=True,experiment_ready=False)))


if __name__=='__main__':main()
