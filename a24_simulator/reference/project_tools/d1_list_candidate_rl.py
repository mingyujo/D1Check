"""v4.1 CPU/GPU candidate controller. No simulator or training on import."""
from __future__ import annotations

import copy
import hashlib
import json
import math
import statistics
import time
import os
import random
from pathlib import Path

import numpy as np
import torch
from torch import nn

from tools import d1_empirical_request_policy as p
from tools import d1_list_candidate_rl_prepilot_check as formula

ROOT = Path(__file__).resolve().parents[1]
FEATURES = json.loads((ROOT/'docs/results/list_candidate_rl_review_01/design_amendment_v4.json').read_text(encoding='utf8'))['features']
STATE_FIELDS = tuple(FEATURES['state_fields'])
CANDIDATE_FIELDS = tuple(FEATURES['candidate_fields'])
VERSION = 'list-candidate-v4.1-implementation-01'
L0 = 'LIST_SERVICE_FIRST_PC_V4_1'
GREEDY = 'LIST_SAME_BANK_RISK5_PC_V4_1'
PPO = 'LIST_MASKED_PPO_PC_V4_1'
PHASES = ('ASSIGNED', 'EXECUTING', 'OUTPUT_READY', 'PERSISTED', 'WORKER_RELEASED')
PUBLIC_PHASE_EVENTS = ('execution_start_ns', 'output_ready_ns', 'persist_complete_ns', 'worker_release_ns', 'lane_available_ns')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def due(q):
    return q['arrival_ns']+q['deadline_offset_ns']


def rank95(values):
    return sorted(values)[math.ceil(.95*len(values))-1] if values else None


def heads_of(queue):
    return {task: min((q for q in queue if q['task'] == task),
                     key=lambda q: (q['arrival_ns'], q['ordinal'], q['id']), default=None)
            for task in ('classification', 'detection')}


def legal(job, queue, lanes):
    q = next((q for q in queue if q['id'] == job['request_id']), None)
    if q is None or job['backend'] not in p.backends(q) or lanes[job['backend']]['request'] is not None:
        return False
    members = [dict(task=v['request']['task'], backend=b) for b, v in lanes.items() if v['request']]
    candidate = dict(task=q['task'], backend=job['backend'])
    return all(formula.compatible(candidate, other) for other in members)


class ActorCritic(nn.Module):
    def __init__(self):
        super().__init__()
        self.state = nn.Sequential(nn.Linear(56, 64), nn.Tanh(), nn.Linear(64, 64), nn.Tanh())
        self.candidate = nn.Sequential(nn.Linear(28, 32), nn.Tanh(), nn.Linear(32, 32), nn.Tanh())
        self.actor = nn.Sequential(nn.Linear(96, 64), nn.Tanh(), nn.Linear(64, 1))
        self.critic = nn.Linear(64, 6)
        for layer in self.modules():
            if isinstance(layer, nn.Linear):
                nn.init.orthogonal_(layer.weight, math.sqrt(2)); nn.init.zeros_(layer.bias)
        nn.init.zeros_(self.actor[-1].weight); nn.init.zeros_(self.actor[-1].bias)

    def forward(self, state, candidates, mask):
        if not torch.all(mask.any(-1)):
            raise ValueError('empty physical mask')
        h = self.state(state); c = self.candidate(candidates)
        logits = self.actor(torch.cat((h[:, None, :].expand(-1, c.shape[1], -1), c), dim=-1)).squeeze(-1)
        return torch.distributions.Categorical(logits=logits.masked_fill(~mask, -torch.inf)), self.critic(h)


class Controller(p.Controller):
    """Public journals + frozen mean estimates only; no realized vector input."""
    def __init__(self, frozen, initial, policy=GREEDY, *, selector=None, network=None, deterministic=True, feature_variant='head2'):
        super().__init__(frozen, initial, p.profile(frozen), p.PPO_POLICY)
        self.public_policy = policy
        self.selector = selector
        self.network = network
        self.deterministic = deterministic
        if feature_variant not in ('head2', 'head2+C_next'):
            raise ValueError('unknown observation schema')
        self.feature_variant = feature_variant
        fields = list(STATE_FIELDS)
        if feature_variant == 'head2+C_next':fields[1] = 'C_next.deadline_remaining_over_1p5s'
        self.state_fields = tuple(fields)
        self.schema_id = digest(dict(version=VERSION,variant=feature_variant,state=self.state_fields,
                                     candidate=CANDIDATE_FIELDS,stored_dtype='float32',slots=8))
        self.means = {(task, b): [x/1e9 for x in self.estimates[task+'_'+b+'_'+('urgent' if task == 'classification' else 'normal')]]
                      for task, bs in formula.BACKENDS.items() for b in bs}
        self.credit = .25
        self.hold = None
        self.hold_counter = 0
        self.pending = None
        self.pending_mixed = None
        self.event_seq = 0
        self.tickets = {}
        self.arrival_history = []
        self.responses = {}
        self.credited = set()
        self.dispatch_receipts = {}
        self.phase_cursors = {}
        self.events = []
        self.controls = []
        self.snapshots = []
        self.grid = {}
        self.grid_cursor = 34
        self.last_key = None
        self.last_output = None
        self.fallbacks = 0
        self.selection_opportunities = 0
        self.deferred_seconds = 0.
        self.pair_cancelled = 0
        self.forced_waits = 0

    def _debit(self, now_ns):
        if self.hold is None:
            return
        end = min(float(now_ns), self.hold['end_ns'])
        delta = max(0., end-self.hold['last_debit_ns'])/1e9
        if delta:
            before = self.credit
            self.credit = max(0., self.credit-delta)
            self.deferred_seconds += delta
            self.hold['last_debit_ns'] = end
            self.controls.append(dict(kind='debit', hold_id=self.hold['id'], at_ns=now_ns,
                                      elapsed_s=delta, before=before, after=self.credit))

    def _end_hold(self, now_ns, reason):
        self._debit(now_ns)
        if self.hold is not None:
            self.controls.append(dict(kind='hold_end', hold_id=self.hold['id'], at_ns=now_ns, reason=reason))
            self.hold = None

    def _arm(self, now_ns, duration_s, held):
        self.hold_counter += 1
        self.hold = dict(id=self.hold_counter, start_ns=now_ns, end_ns=now_ns+duration_s*1e9,
                         last_debit_ns=now_ns, held=list(held))
        self.controls.append(dict(kind='hold_start', at_ns=now_ns, **copy.deepcopy(self.hold)))

    def on_public_event(self, event):
        allowed = {'at_ns', 'event_seq', 'request_id', 'backend', 'event', 'ticket'}
        if not set(event) <= allowed:
            raise ValueError('private event fields')
        if event['event_seq'] != self.event_seq+1:
            raise ValueError('missing/duplicate/out-of-order public event')
        if event['event'] != 'arrived' and event['request_id'] not in self.tickets:
            raise ValueError('event for unknown ticket')
        if event['event'] not in ('arrived', 'dispatch_ns') and event['request_id'] not in self.credited:
            raise ValueError('phase before actual dispatch')
        if event['event'] in PUBLIC_PHASE_EVENTS:
            next_phase = self.phase_cursors[event['request_id']]+1
            if next_phase >= 5 or event['event'] != PUBLIC_PHASE_EVENTS[next_phase]:
                raise ValueError('missing/out-of-order public phase')
            self.phase_cursors[event['request_id']] = next_phase
        self.event_seq = event['event_seq']
        self.events.append(copy.deepcopy(event))
        now, rid, kind = event['at_ns'], event['request_id'], event['event']
        self._debit(now)
        if kind == 'arrived':
            q = copy.deepcopy(event['ticket'])
            if set(q) != {'id','task','priority','ordinal','arrival_ns','deadline_offset_ns'} or rid in self.tickets:
                raise ValueError('private/duplicate arrival ticket')
            p.backends(q)
            if q['arrival_ns'] > now:
                raise ValueError('future arrival event')
            self.tickets[rid] = q
            self.arrival_history.append((q['arrival_ns']/1e9, q['task']))
            self._end_hold(now, 'arrival')
        elif kind == 'dispatch_ns':
            self._end_hold(now, 'actual_dispatch')
            if rid in self.credited:
                raise ValueError('duplicate actual dispatch')
            if event['backend'] not in p.backends(self.tickets[rid]):
                raise ValueError('unsupported actual dispatch backend')
            self.credited.add(rid); self.credit = .25
            self.dispatch_receipts[rid] = dict(request_id=rid, backend=event['backend'], at_ns=now, event_seq=self.event_seq)
            self.phase_cursors[rid] = -1
            self.controls.append(dict(kind='credit_reset', at_ns=now, request_id=rid, after=.25))
            if self.pending_mixed and self.pending_mixed['first_id'] == rid:
                mixed = self.pending_mixed; self.pending_mixed = None
                self._arm(now, mixed['duration'], mixed['held'])
        elif kind == 'lane_available_ns':
            self._end_hold(now, 'actual_lane_release')
        q = self.tickets.get(rid)
        if q and kind == ('output_ready_ns' if q['priority'] == 'urgent' else 'persist_complete_ns'):
            latency_ns = round(now-q['arrival_ns'])
            if rid in self.responses:
                raise ValueError('duplicate response')
            self.responses[rid] = dict(priority=q['priority'], response_ms=latency_ns/1e6,
                                       late=latency_ns > q['deadline_offset_ns'])

    def observe(self, now_ns, lanes):
        self._debit(now_ns)
        slopes = self.frozen['ap']['parameters']['ap_slope_at_30_c_per_s']
        start = max(self.now, self.init['anchor_s'])
        u = slopes[self.label]-slopes['resident_idle']
        for second in range(max(35, self.grid_cursor+1), min(180, math.floor(now_ns/1e9))+1):
            if second >= start:
                self.grid[second] = p.thermal_step(self.t, self.h, u, self.init['reference_c'], self.frozen['ap'], second-start)[0]
                self.grid_cursor = second
        super().observe(now_ns, lanes)
        if self.hold and now_ns >= self.hold['end_ns']:
            self._end_hold(now_ns, 'timer')

    def _l0_jobs(self, queue, lanes):
        simulated = copy.deepcopy(lanes)
        jobs = []
        heads = heads_of(queue)
        for q in sorted((q for q in heads.values() if q), key=lambda q: (due(q), q['arrival_ns'], q['ordinal'], q['id'])):
            options = [dict(request_id=q['id'], backend=b) for b in p.backends(q)]
            options = [job for job in options if legal(job, queue, simulated)]
            if not options:
                continue
            job = min(options, key=lambda job: (sum(self.estimates[p.key(q, job['backend'])]), job['backend'] != 'CPU'))
            jobs.append(job)
            simulated[job['backend']]['request'] = q
        if len(jobs) == 2:
            jobs.sort(key=lambda job: job['backend'] != 'GPU')
        return jobs

    def bank(self, queue, lanes, now_ns):
        heads = heads_of(queue); c, d = heads['classification'], heads['detection']
        now = now_ns/1e9; actions = []
        def add(kind, jobs, wait=0., held=()):
            signature = (tuple((j['request_id'], j['backend']) for j in jobs), wait, tuple(held))
            if signature not in [a['signature'] for a in actions]:
                actions.append(dict(kind=kind, jobs=jobs, wait=wait, held=list(held), signature=signature))
        c_cpu = dict(request_id=c['id'], backend='CPU') if c else None
        c_gpu = dict(request_id=c['id'], backend='GPU') if c else None
        d_cpu = dict(request_id=d['id'], backend='CPU') if d else None
        cp = c_cpu and legal(c_cpu, queue, lanes)
        cg = c_gpu and legal(c_gpu, queue, lanes)
        dp = d_cpu and legal(d_cpu, queue, lanes)
        if cp: add('C_CPU_NOW', [c_cpu])
        if cg and dp:
            add('PAIR_NOW', [c_gpu, d_cpu])
            for duration, name in ((.125, 'SHORT'), (.25, 'FULL')):
                for first, deferred, prefix in ((c_gpu, d, 'C_GPU_DEFER_D_'), (d_cpu, c, 'D_CPU_DEFER_C_')):
                    delay = min(duration, .25, max(0., (due(deferred)-now_ns)/1e9), max(0., 120-now))
                    if delay > 1e-9: add(prefix+name, [first], delay, [deferred['id']])
        else:
            if cg: add('C_GPU_NOW', [c_gpu])
            if dp: add('D_CPU_NOW', [d_cpu])
        if actions:
            earliest = min(due(q) for q in heads.values() if q)
            for duration, name in ((.125, 'SHORT'), (.25, 'FULL')):
                delay = min(duration, self.credit, max(0., (earliest-now_ns)/1e9), max(0., 120-now))
                if delay > 1e-9: add('DEFER_ALL_'+name, [], delay, [q['id'] for q in heads.values() if q])
        base_jobs = self._l0_jobs(queue, lanes)
        for action in actions:
            action['base'] = action['jobs'] == base_jobs and action['wait'] == 0
        if actions and sum(a['base'] for a in actions) != 1:
            raise ValueError('L0 not represented exactly once')
        if len(actions) > 8:
            raise ValueError('candidate bound')
        return actions

    def _active(self, lanes, now):
        active = []
        for backend, lane in lanes.items():
            q = lane['request']
            if q is None: continue
            mu = self.means[(q['task'], backend)]
            end = formula.owned_end(now, lane['dispatch']/1e9, PHASES.index(lane['phase']), mu)
            active.append(dict(task=q['task'], backend=backend, start=now, end=end))
        return active

    def forecast(self, action, queue, lanes, now_ns):
        now = now_ns/1e9
        heads = [q for q in heads_of(queue).values() if q]
        simple_heads = [dict(id=q['id'], task=q['task'], arrival=q['arrival_ns']/1e9, ordinal=q['ordinal']) for q in heads]
        active = self._active(lanes, now)
        jobs = [(j['request_id'], j['backend']) for j in action['jobs']]
        holds = {rid: now+action['wait'] for rid in action['held']}
        prediction = formula.shadow(now, simple_heads, active, jobs, holds, self.means)
        atom = list(active)
        for rid, backend in jobs:
            q = next(q for q in heads if q['id'] == rid)
            atom.append(dict(task=q['task'], backend=backend, start=now, end=now+sum(self.means[(q['task'], backend)])))
        end = now+action['wait'] if not jobs else max([now+action['wait']] + [j['end'] for j in atom])
        segments = p.segments([dict(state=j['task']+'_'+j['backend'], start=j['start'], end=j['end']) for j in atom], now, end)
        t, h, peak, energy = self.t, self.h, self.t, self.initial['preload_power_w']*(end-now)
        slopes = self.frozen['ap']['parameters']['ap_slope_at_30_c_per_s']
        for segment in segments:
            label = 'resident_idle' if segment['state'] == 'idle' else segment['state']
            if label != 'resident_idle' and label not in self.frozen['energy_increment_w']:
                raise formula.PredictionUnknown('unsupported energy state')
            a, b = segment['start_s'], segment['end_s']
            energy += (b-a)*self.frozen['energy_increment_w'].get(label, 0.)
            u = slopes[label]-slopes['resident_idle']
            for point in sorted({b} | {float(x) for x in range(math.ceil(a), math.floor(b)+1) if x > a}):
                peak = max(peak, p.thermal_step(t, h, u, self.init['reference_c'], self.frozen['ap'], point-a)[0])
            t, h = p.thermal_step(t, h, u, self.init['reference_c'], self.frozen['ap'], b-a)
        return dict(known=True, prediction=prediction, active=active, atom=atom, span=end-now,
                    energy=energy, end_ap=t-self.t, peak_ap=peak-self.t)

    def encode(self, queue, lanes, now_ns, actions):
        if any(q['arrival_ns'] > now_ns for q in queue):
            raise ValueError('future ticket in encoder')
        now = now_ns/1e9; heads = heads_of(queue)
        s = dict.fromkeys(STATE_FIELDS, 0.)
        urgent = [r['response_ms'] for r in self.responses.values() if r['priority'] == 'urgent']
        observed_p95 = rank95(urgent)
        s.update(elapsed_over_120s=now/120, remaining_over_120s=(120-now)/120,
                 queued_classification_over_192=sum(q['task']=='classification' for q in queue)/192,
                 queued_detection_over_192=sum(q['task']=='detection' for q in queue)/192,
                 CPU_owned=float(lanes['CPU']['request'] is not None), GPU_owned=float(lanes['GPU']['request'] is not None),
                 defer_credit_over_025s=self.credit/.25, valid_candidates_over_8=len(actions)/8,
                 estimated_AP_minus_reference_over_1C=self.t-self.init['reference_c'],
                 past_grid_peak_minus_reference_over_1C=max(self.grid.values(), default=self.t)-self.init['reference_c'],
                 observed_urgent_response_count_over_192=len(urgent)/192,
                 observed_urgent_P95_over_1500ms=(observed_p95 or 0.)/1500,
                 observed_urgent_failures_over_192=sum(r['late'] and r['priority']=='urgent' for r in self.responses.values())/192,
                 observed_normal_failures_over_192=sum(r['late'] and r['priority']=='normal' for r in self.responses.values())/192)
        for task, prefix in (('classification', 'C_head.'), ('detection', 'D_head.')):
            q = heads[task]
            if q is None: continue
            deadline = q['deadline_offset_ns']/1e9
            s[prefix+'present'] = 1.; s[prefix+'age_over_own_deadline'] = (now_ns-q['arrival_ns'])/q['deadline_offset_ns']
            s[prefix+'deadline_slack_over_own_deadline'] = (due(q)-now_ns)/q['deadline_offset_ns']
            s[prefix+'supported_backend_count_over_2'] = len(p.backends(q))/2
            s[prefix+'same_task_backlog_over_192'] = sum(r['task']==task for r in queue)/192
            for backend in p.backends(q):
                mu = self.means[(task, backend)]
                s[prefix+'mean_response_'+backend+'_over_own_deadline'] = sum(mu[:2 if task=='classification' else 3])/deadline
                s[prefix+backend+'_response_known'] = 1.
        for backend, lane in lanes.items():
            q = lane['request']; prefix = backend+'.'
            if q is None: continue
            s[prefix+'owned'] = 1.; s[prefix+q['task']] = 1.
            stage = PHASES.index(lane['phase'])
            s[prefix+'public_phase_index_over_5'] = (stage+1)/5
            s[prefix+'elapsed_since_dispatch_over_6s'] = (now_ns-lane['dispatch'])/6e9
            s[prefix+'elapsed_since_phase_over_6s'] = (now_ns-lane['since'])/6e9
            try:
                end = formula.owned_end(now, lane['dispatch']/1e9, stage, self.means[(q['task'], backend)])
                s[prefix+'estimated_remaining_lane_over_6s'] = (end-now)/6
                s[prefix+'remaining_prediction_known'] = 1.
            except formula.PredictionUnknown:
                pass
        history = self.arrival_history[-9:]
        if history:
            s['arrival.last_arrival_age_over_6s'] = (now-history[-1][0])/6
            s['arrival.classification_fraction_last8'] = sum(task=='classification' for _, task in history[-8:])/len(history[-8:])
        gaps = [b[0]-a[0] for a, b in zip(history, history[1:])]
        if gaps:
            s.update({'arrival.last_gap_over_1s': gaps[-1], 'arrival.mean_last8_gaps_over_1s': statistics.mean(gaps),
                      'arrival.min_last8_gaps_over_1s': min(gaps), 'arrival.std_last8_gaps_over_1s': statistics.pstdev(gaps),
                      'arrival.observed_gap_count_over_8': len(gaps)/8, 'arrival.has_gap_observation': 1.})
        if self.feature_variant == 'head2+C_next':
            ordered_c = sorted((q for q in queue if q['task']=='classification'),
                               key=lambda q:(q['arrival_ns'],q['ordinal'],q['id']))
            s[self.state_fields[1]] = (due(ordered_c[1])-now_ns)/1.5e9 if len(ordered_c)>=2 else 0.
        raw = []
        for action in actions:
            try: raw.append(self.forecast(action, queue, lanes, now_ns))
            except formula.PredictionUnknown: raw.append(dict(known=False, prediction=None, span=None, energy=None, end_ap=None, peak_ap=None))
        base = next(i for i, a in enumerate(actions) if a['base'])
        candidates = np.zeros((8, 28), dtype=np.float32); mask = np.zeros(8, dtype=bool)
        for index, (action, forecast) in enumerate(zip(actions, raw)):
            v = dict.fromkeys(CANDIDATE_FIELDS, 0.)
            jobs = action['jobs']; tasks = [next(q['task'] for q in queue if q['id']==j['request_id']) for j in jobs]
            v.update(uses_CPU_now=float(any(j['backend']=='CPU' for j in jobs)), uses_GPU_now=float(any(j['backend']=='GPU' for j in jobs)),
                     dispatches_classification=float('classification' in tasks), dispatches_detection=float('detection' in tasks),
                     is_bundle=float(len(jobs)==2), is_discretionary_defer=float(action['wait']>0),
                     defer_duration_over_025s=action['wait']/.25, dispatched_count_over_2=len(jobs)/2,
                     is_L0_choice=float(index==base), prediction_supported=float(forecast['known']))
            for task, prefix in (('classification', 'C_head'), ('detection', 'D_head')):
                q = heads[task]
                if q is None: continue
                v[prefix+'.deadline_slack_over_own_deadline'] = (due(q)-now_ns)/q['deadline_offset_ns']
                if forecast['known']:
                    response = forecast['prediction'][q['id']]['response']
                    v[prefix+'.predicted_response_over_own_deadline'] = (response-q['arrival_ns']/1e9)/(q['deadline_offset_ns']/1e9)
                    v[prefix+'_slack_after_this_atom_over_own_deadline'] = (due(q)/1e9-response)/(q['deadline_offset_ns']/1e9)
            if forecast['known']:
                atom = forecast['atom']
                v.update(proxy_span_duration_over_6s=forecast['span']/6, proxy_span_duration_known=1.,
                         proxy_span_whole_device_J_over_1J=forecast['energy'], span_J_known=1.,
                         proxy_end_AP_delta_over_1C=forecast['end_ap'], end_AP_known=1.,
                         proxy_span_peak_AP_delta_over_1C=forecast['peak_ap'], span_peak_known=1.,
                         CPU_new_occupation_over_6s=sum(j['end']-j['start'] for j in atom if j['backend']=='CPU' and j not in forecast['active'])/6,
                         GPU_new_occupation_over_6s=sum(j['end']-j['start'] for j in atom if j['backend']=='GPU' and j not in forecast['active'])/6,
                         estimated_next_free_over_6s=(min((j['end'] for j in atom), default=now)-now)/6)
                cpu = next((j for j in atom if j['backend']=='CPU'), None); gpu = next((j for j in atom if j['backend']=='GPU'), None)
                v['estimated_overlap_over_6s'] = max(0., min(cpu['end'],gpu['end'])-max(cpu['start'],gpu['start']))/6 if cpu and gpu else 0.
            candidates[index] = [v[field] for field in CANDIDATE_FIELDS]; mask[index] = True
        state = np.asarray([s[field] for field in self.state_fields], dtype=np.float32)
        if not np.isfinite(state).all() or not np.isfinite(candidates).all(): raise ValueError('nonfinite encoder')
        return dict(state=state, candidates=candidates, mask=mask, base=base, raw=raw,
                    kinds=[a['kind'] for a in actions], state_names=self.state_fields, candidate_names=CANDIDATE_FIELDS,
                    schema_id=self.schema_id, feature_variant=self.feature_variant,
                    now_ns=now_ns, event_seq=self.event_seq, credit=self.credit,
                    pending=copy.deepcopy(self.pending), hold=copy.deepcopy(self.hold), observed_p95_ms=observed_p95,
                    observed_urgent_count=len(urgent))

    def choose(self, encoded, actions, queue):
        base = encoded['base']
        if self.selector is not None:
            return int(self.selector(self, encoded, actions, queue))
        if self.public_policy == L0:
            return base
        if self.public_policy == PPO:
            with torch.no_grad():
                distribution, values = self.network(torch.from_numpy(encoded['state'])[None],
                    torch.from_numpy(encoded['candidates'])[None], torch.from_numpy(encoded['mask'])[None])
            encoded['old_value'] = values[0].numpy().copy()
            if self.deterministic:
                scores = distribution.logits[0].numpy()
                index = base if scores[base] == scores.max() else int(scores.argmax())
            else:
                index = int(distribution.sample().item())
            encoded['logprob'] = float(distribution.log_prob(torch.tensor([index])).item())
            return index
        if any(not item['known'] for item in encoded['raw']):
            self.fallbacks += 1
            return base
        simple = [dict(id=q['id'], task=q['task'], arrival=q['arrival_ns']/1e9, ordinal=q['ordinal']) for q in heads_of(queue).values() if q]
        baseline = encoded['raw'][base]['prediction']
        rankings = []
        for i, (action, forecast) in enumerate(zip(actions, encoded['raw'])):
            risk = formula.service_risk5(simple, forecast['prediction'], baseline,
                                         (encoded['observed_p95_ms'] or 0.)/1000, encoded['observed_urgent_count'])
            rankings.append((*risk, forecast['peak_ap'], forecast['end_ap'], forecast['energy'], i != base, i))
        return min(range(len(rankings)), key=lambda i: rankings[i])

    def __call__(self, config, queue, lanes, now_ns, settings, thermal_model, current_ap):
        if any(q['arrival_ns'] > now_ns for q in queue) or any(set(l)!= {'request','phase','since','dispatch'} for l in lanes.values()):
            raise ValueError('noncausal public ABI')
        out = dict(now_ns=now_ns, selected=None, reason='forced_public_event_wait', public_policy=self.public_policy)
        if self.pending:
            pending = self.pending; self.pending = None
            receipt = self.dispatch_receipts.get(pending['first']['request_id'])
            if (receipt and receipt['backend'] == pending['first']['backend'] and receipt['at_ns'] == pending['at_ns']
                    and now_ns == pending['at_ns']
                    and legal(pending['second'], queue, lanes)):
                return dict(out, selected=pending['second'], reason='PAIR_second_commit')
            self.pair_cancelled += 1
            self.controls.append(dict(kind='pair_cancel', at_ns=now_ns, pending=pending, retained=True))
            return out
        if self.hold:
            return dict(out, reason='hold_observer_only', wait_until_ns=self.hold['end_ns'])
        actions = self.bank(queue, lanes, now_ns)
        if not actions:
            self.forced_waits += 1
            return out
        key = digest(dict(queue=queue, lanes=lanes, now_ns=now_ns, event_seq=self.event_seq, credit=self.credit))
        if key == self.last_key:
            return copy.deepcopy(self.last_output)
        began = time.perf_counter()
        encoded = self.encode(queue, lanes, now_ns, actions)
        index = self.choose(encoded, actions, queue)
        if not 0 <= index < len(actions): raise ValueError('selector invalid action')
        action = actions[index]
        self.selection_opportunities += 1
        encoded.update(chosen=index, chosen_kind=action['kind'], informative=len(actions)>1,
                       actor_eligible=(self.public_policy==PPO and self.selector is None and not self.deterministic and len(actions)>1),
                       decision_seconds=time.perf_counter()-began, public_queue=copy.deepcopy(queue),
                       public_lanes=copy.deepcopy(lanes), action=copy.deepcopy(action))
        self.snapshots.append(encoded)
        out.update(reason=action['kind'], candidate_count=len(actions), chosen_index=index)
        if action['jobs']:
            out['selected'] = copy.deepcopy(action['jobs'][0])
            if len(action['jobs']) == 2:
                self.pending = dict(at_ns=now_ns, second=copy.deepcopy(action['jobs'][1]), first=copy.deepcopy(action['jobs'][0]))
            elif action['wait']:
                self.pending_mixed = dict(first_id=action['jobs'][0]['request_id'], duration=action['wait'], held=action['held'])
        else:
            self._arm(now_ns, action['wait'], action['held']); out['wait_until_ns'] = self.hold['end_ns']
        self.last_key = key; self.last_output = copy.deepcopy(out)
        return out


def episode_targets(controller, row, curve, reference):
    """Realized curve is posthoc only; costs masked for the whole trajectory."""
    trajectory = controller.snapshots
    if row['planned'] != reference['planned']:
        raise ValueError('reference planned-request denominator mismatch')
    for value in (row, reference):
        if value.get('completed') is None or not 0 <= value['completed'] <= value['planned']:
            raise ValueError('unknown completion ledger; no learner update')
    finite = lambda value: value is not None and math.isfinite(value)
    valid = np.ones(6, dtype=bool)
    full = row['completed']==row['planned'] and reference['completed']==reference['planned']
    valid[0] = full and finite(row.get('peak_ap_c')) and finite(reference.get('peak_ap_c'))
    valid[1] = full and finite(row.get('energy_j')) and finite(reference.get('energy_j'))
    costs = np.zeros(5)
    for i, (name, scale) in enumerate((('energy_j', 1.), ('incomplete', 1.), ('urgent_failure', 1.), ('normal_failure', 1.), ('urgent_p95_ms', 1500.))):
        if name == 'incomplete':
            costs[i] = max(0., (row['planned']-row['completed'])-(reference['planned']-reference['completed']))
            continue
        alias = {'urgent_failure': 'urgent_service_failure', 'normal_failure': 'normal_service_failure'}.get(name, name)
        left, right = row.get(name, row.get(alias)), reference.get(name, reference.get(alias))
        if not finite(left) or not finite(right):
            valid[i+1] = False; continue
        difference = (left-right)/scale
        costs[i] = difference if i == 0 else max(0., difference)
    rewards = np.zeros(len(trajectory))
    if trajectory and valid[0]:
        if not curve or any(not finite(v) for _, v in curve):
            raise ValueError('invalid realized reward curve')
        peaks = [max(v for t, v in curve if t <= step['now_ns']/1e9) for step in trajectory]
        for i in range(len(peaks)-1): rewards[i] = -(peaks[i+1]-peaks[i])
        rewards[-1] = -(row['peak_ap_c']-peaks[-1]) + reference['peak_ap_c']-peaks[0]
        if not math.isclose(float(rewards.sum()), reference['peak_ap_c']-row['peak_ap_c'], abs_tol=1e-12):
            raise ValueError('reward telescope')
    returns = np.cumsum(rewards[::-1])[::-1]
    return [dict(state=step['state'], candidates=step['candidates'], mask=step['mask'].copy(), action=step['chosen'],
                 informative=step.get('actor_eligible', False), old_value=step.get('old_value'), logprob=step.get('logprob'),
                 target=np.asarray([ret, *costs], dtype=np.float32), valid=valid.copy())
            for step, ret in zip(trajectory, returns)], rewards, costs, valid


def controller_state(controller):
    return copy.deepcopy({k: v for k, v in controller.__dict__.items() if k not in ('selector', 'network')})


def restore_controller(controller, state):
    if controller.schema_id != state['schema_id']:
        raise ValueError('controller schema mismatch')
    controller.__dict__.update(copy.deepcopy(state))


def save_checkpoint(path, controller, network, optimizer, multipliers, partial_batch, consumption):
    """Controller/RNG archive. Live engine continuation is outside this archive."""
    path=Path(path);temporary=path.with_suffix('.tmp')
    payload=dict(version=VERSION,schema_id=controller.schema_id,model_sha256=p.MODEL_SHA,initial_sha256=p.INITIAL_SHA,
                 controller_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                 network=network.state_dict(),optimizer=optimizer.state_dict(),multipliers=list(multipliers),
                 partial_batch=partial_batch,controller=controller_state(controller),consumption=consumption,
                 rng=dict(python=random.getstate(),numpy=np.random.get_state(),torch=torch.get_rng_state()),
                 archive_scope='policy/controller/RNG; not a live engine or learning-resume verification')
    with temporary.open('wb') as f:torch.save(payload,f);f.flush();os.fsync(f.fileno())
    os.replace(temporary,path)


def load_checkpoint(path, controller, network, optimizer):
    payload=torch.load(path,map_location='cpu',weights_only=False)
    if (payload['schema_id'] != controller.schema_id or payload['model_sha256'] != p.MODEL_SHA or payload['initial_sha256'] != p.INITIAL_SHA
            or payload['controller_source_sha256'] != hashlib.sha256(Path(__file__).read_bytes()).hexdigest()):
        raise ValueError('checkpoint schema/model/input mismatch')
    network.load_state_dict(payload['network']);optimizer.load_state_dict(payload['optimizer'])
    restore_controller(controller,payload['controller'])
    random.setstate(payload['rng']['python']);np.random.set_state(payload['rng']['numpy']);torch.set_rng_state(payload['rng']['torch'])
    return payload


def ppo_losses(network, episodes, multipliers):
    """Episode-sum actor, episode-mean critic/entropy; no optimizer step here."""
    if not episodes:raise ValueError('empty batch')
    frames=[frame for episode in episodes for frame in episode]
    if not frames:raise ValueError('no data')
    states=torch.from_numpy(np.stack([d['state'] for d in frames]))
    candidates=torch.from_numpy(np.stack([d['candidates'] for d in frames]))
    masks=torch.from_numpy(np.stack([d['mask'] for d in frames]))
    distribution,values=network(states,candidates,masks)
    targets=torch.from_numpy(np.stack([d['target'] for d in frames]))
    valid=torch.from_numpy(np.stack([d['valid'] for d in frames]))
    informative=torch.tensor([bool(d['informative']) for d in frames])
    old_values=torch.from_numpy(np.stack([d['old_value'] if d['old_value'] is not None else values[i].detach().numpy() for i,d in enumerate(frames)]))
    advantage=(targets-old_values)*valid
    weights=torch.tensor(multipliers,dtype=torch.float32)
    direct_energy=-weights[0]*advantage[:,1]
    combined=advantage[:,0]-(advantage[:,1:]*weights).sum(-1)
    slices=[];cursor=0;means=[];seconds=[]
    for episode in episodes:
        sl=slice(cursor,cursor+len(episode));slices.append(sl);cursor+=len(episode)
        selected=combined[sl][informative[sl]]
        if len(selected):means.append(selected.mean());seconds.append(selected.square().mean())
    if means:
        center=torch.stack(means).mean();variance=torch.stack(seconds).mean()-center.square()
        combined=(combined-center)/(variance.clamp(min=0).sqrt()+1e-8)
    actions=torch.tensor([d['action'] for d in frames])
    old_log=torch.tensor([d['logprob'] if d['logprob'] is not None else 0. for d in frames])
    if any(d['informative'] and (d['logprob'] is None or d['old_value'] is None) for d in frames):
        raise ValueError('sampled rollout likelihood/value missing')
    ratio=(distribution.log_prob(actions)-old_log).exp()
    surrogate=torch.minimum(ratio*combined,ratio.clamp(.8,1.2)*combined)
    zero=values.sum()*0.;actor=zero;critic=zero;entropy=zero
    per_frame=((values-targets).square()*valid).sum(-1)/valid.sum(-1).clamp(min=1)
    for sl in slices:
        info=informative[sl]
        if info.any():
            actor=actor-surrogate[sl][info].sum()/len(episodes)
            entropy=entropy+distribution.entropy()[sl][info].mean()/len(episodes)
        if sl.stop>sl.start:critic=critic+per_frame[sl].mean()/len(episodes)
    return dict(loss=actor+.5*critic-.01*entropy,actor=actor,critic=critic,entropy=entropy,
                direct_energy_advantage=direct_energy,advantage=advantage,values=values,
                sampled_choices=int(informative.sum()),episode_count=len(episodes))
