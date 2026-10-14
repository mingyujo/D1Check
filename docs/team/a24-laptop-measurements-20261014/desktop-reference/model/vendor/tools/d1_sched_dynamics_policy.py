"""V17 causal, full-queue single-dispatch bank; no predicted future queue.

All rules and PPO share this bank and its operational mask. Legal simultaneous
execution is composed by rebuilding the bank after each same-time dispatch.
"""
from __future__ import annotations

import hashlib
import json
import math
import time
import numpy as np

VERSION = 'd1-scheduling-dynamics-full-queue-v17'
BACKENDS = ('CPU', 'GPU', 'NPU')
RULES = ('FIFO_READY', 'SPT', 'EDD', 'ATC', 'RR_READY', 'GREEDY_READY_V17')
REQUEST_SLOTS, REQUEST_DIM, RESOURCE_DIM, GLOBAL_DIM = 64, 22, 9, 20
STATE_DIM = REQUEST_SLOTS * REQUEST_DIM + len(BACKENDS) * RESOURCE_DIM + GLOBAL_DIM
ACTION_DIM = REQUEST_DIM + len(BACKENDS) + 7
SLOTS = REQUEST_SLOTS * len(BACKENDS) + 1
ATC_K = 2.0
ATC_WEIGHTS = {'urgent': 2.0, 'normal': 1.0}
SCHEMA_SPEC = dict(version=VERSION, state=[64, 22, 3, 9, 20], actions=[193, 32],
    request_features=['task_C','task_D','urgent','age/6s','declared_slack/6s',
        'original_slack/6s','declared_offset/6s','known_units/3',
        'CPU_occupancy/6s','CPU_response/6s','GPU_occupancy/6s','GPU_response/6s',
        'NPU_occupancy/6s','NPU_response/6s','supports_CPU','supports_GPU','supports_NPU',
        'log_ATC/10','EDD_rank/64','ATC_rank/64','minimum_supported_occupancy_rank/64','present'],
    candidates='all arrived unstarted requests; stable FIFO slots; no truncation',
    atc='log(w/p)-max(d-now-response,0)/(k*mean_occupancy)', k=ATC_K,
    weights=ATC_WEIGHTS, routes='device-supported single commits; same-time rebuild',
    wait='busy-resource wait only when no legal execution; no cooling',
    costs='delayed public sensors and observed activity only; no rollout/private outcomes',
    extra_global=['power_w/10', 'causal_activation_CPU', 'causal_activation_GPU',
        'causal_activation_NPU', 'past5s_AP_slope_C_per_s', 'past5s_power_slope_W_per_s'],
    work_units='known 1..3; execution phase scaled by device; no fitted batch claim')
SCHEMA = hashlib.sha256(json.dumps(SCHEMA_SPEC, sort_keys=True).encode()).hexdigest()
PUBLIC_REQUEST_FIELDS = {'id', 'ordinal', 'task', 'priority', 'arrival_ns', 'deadline_offset_ns', 'work_units'}


def tie(q):
    return q['arrival_ns'], q['ordinal'], q['id']


def response(ds, q):
    return sum(ds[:2 if q['priority'] == 'urgent' else 3])


def original_cap(q):
    return 1_500_000_000 if q['priority'] == 'urgent' else 6_000_000_000


def clip(x):
    return float(np.clip(x, -10., 10.))


def observed_slopes(public,now):
    history=public.get('observed_history', [])
    if any(type(v['time_ns']) is not int or v['time_ns']>now for v in history):
        raise ValueError('future or invalid observed history')
    if any(not math.isfinite(float(v[k])) for v in history for k in ('ap_c','power_w')):
        raise ValueError('nonfinite observed history')
    recent=sorted((v for v in history if v['time_ns']>=now-5_000_000_000),key=lambda v:v['time_ns'])
    if len(recent)<2 or recent[-1]['time_ns']==recent[0]['time_ns']:
        return 0.,0.
    seconds=(recent[-1]['time_ns']-recent[0]['time_ns'])/1e9
    return ((recent[-1]['ap_c']-recent[0]['ap_c'])/seconds,
            (recent[-1]['power_w']-recent[0]['power_w'])/seconds)


def validate_waiting(dev, waiting):
    if len(waiting) > REQUEST_SLOTS or len({q['id'] for q in waiting}) != len(waiting):
        raise ValueError('queue bound or duplicate request')
    for q in waiting:
        if set(q) not in (PUBLIC_REQUEST_FIELDS, PUBLIC_REQUEST_FIELDS - {'work_units'}):
            raise ValueError('private or unknown request field')
        if q['arrival_ns'] > dev.now or q['task'] not in ('classification', 'detection'):
            raise ValueError('future arrival or unsupported task')
        if q['priority'] not in ATC_WEIGHTS or q['deadline_offset_ns'] <= 0:
            raise ValueError('priority or deadline')
        if type(q.get('work_units', 1)) is not int or not 1 <= q.get('work_units', 1) <= 3:
            raise ValueError('known work_units must be integer 1..3')


def _routes(dev, q):
    if hasattr(dev, 'routes'):
        return tuple(dev.routes(q))
    if q['task'] == 'detection':
        return ('CPU',)
    return BACKENDS if dev.public()['npu_enabled'] else BACKENDS[:2]


def _estimate(dev, q, b):
    ds = tuple(float(x) for x in dev.estimate(q, b, [(q, b)]))
    if len(ds) != 5 or not all(math.isfinite(x) and x >= 0 for x in ds) or sum(ds) <= 0:
        raise ValueError('invalid public estimate')
    return ds


def _context(dev, waiting):
    validate_waiting(dev, waiting)
    ordered = sorted(waiting, key=tie)
    paths = {(q['id'], b): _estimate(dev, q, b) for q in ordered for b in _routes(dev, q)}
    reps = {}
    for q in ordered:
        b = min(_routes(dev, q), key=lambda route: (response(paths[q['id'], route], q),
            sum(paths[q['id'], route]), BACKENDS.index(route)))
        reps[q['id']] = (sum(paths[q['id'], b]), response(paths[q['id'], b], q), b)
    mean_p = sum(v[0] for v in reps.values()) / max(1, len(reps))
    scores = {q['id']: math.log(ATC_WEIGHTS[q['priority']]) - math.log(reps[q['id']][0] / 1e9)
        - max(q['arrival_ns'] + q['deadline_offset_ns'] - dev.now - reps[q['id']][1], 0.)
        / (ATC_K * mean_p) for q in ordered}
    ranks = {}
    for name, key in [('EDD', lambda q: (q['arrival_ns'] + q['deadline_offset_ns'], *tie(q))),
                      ('SPT', lambda q: (min(sum(paths[q['id'], b]) for b in _routes(dev,q)), *tie(q))),
                      ('ATC', lambda q: (-scores[q['id']], *tie(q)))]:
        ranks[name] = {q['id']: i for i, q in enumerate(sorted(ordered, key=key))}
    return ordered, paths, reps, scores, ranks


def build(dev, waiting):
    begin = time.perf_counter_ns()
    ordered, paths, reps, scores, ranks = _context(dev, waiting)
    atc_us = (time.perf_counter_ns() - begin) / 1e3
    public = dev.public()
    rows = {}
    for q in ordered:
        row = [float(q['task'] == 'classification'), float(q['task'] == 'detection'),
            float(q['priority'] == 'urgent'), clip((dev.now-q['arrival_ns'])/6e9),
            clip((q['arrival_ns']+q['deadline_offset_ns']-dev.now)/6e9),
            clip((q['arrival_ns']+original_cap(q)-dev.now)/6e9), clip(q['deadline_offset_ns']/6e9),
            q.get('work_units', 1)/3.]
        row.extend(v for b in BACKENDS for v in
            ((sum(paths[q['id'], b])/6e9, response(paths[q['id'], b], q)/6e9)
                if (q['id'], b) in paths else (0., 0.)))
        row.extend(float(b in _routes(dev, q)) for b in BACKENDS)
        row.extend([clip(scores[q['id']]/10.), ranks['EDD'][q['id']]/64.,
                    ranks['ATC'][q['id']]/64., ranks['SPT'][q['id']]/64., 1.])
        if len(row) != REQUEST_DIM:
            raise AssertionError('request feature derivation')
        rows[q['id']] = row
    state_values = [v for q in ordered for v in rows[q['id']]]
    state_values.extend([0.] * (REQUEST_DIM * (REQUEST_SLOTS-len(ordered))))
    phases = ('ASSIGNED', 'EXECUTING', 'OUTPUT_READY', 'PERSISTED', 'WORKER_RELEASED')
    for b in BACKENDS:
        lane = public['lanes'].get(b)
        if lane and lane.get('request'):
            q = lane['request']; elapsed = dev.now-lane['dispatch']; ds = lane['estimate_ns']
            state_values.extend([1., float(q['task']=='classification'), float(q['task']=='detection'),
                float(q['priority']=='urgent'), phases.index(lane['phase'])/4., clip(elapsed/6e9),
                clip(max(sum(ds)-elapsed, 0)/6e9), clip(max(response(ds, q)-elapsed, 0)/6e9),
                BACKENDS.index(b)/2.])
        else:
            state_values.extend([0.] * RESOURCE_DIM)
    busy = sum(bool(v and v.get('request')) for v in public['lanes'].values())
    n = len(ordered)
    activity = public.get('recent_activity', {})
    reference = public.get('reference_ap_c', public.get('ambient_c', 30.))
    legal_jobs = [(q, b) for q in ordered for b in _routes(dev, q) if dev.feasible([(q, b)])]
    ready_ids = {q['id'] for q, b in legal_jobs}
    state_values.extend([dev.now/120e9, n/64., sum(q['priority']=='urgent' for q in ordered)/max(n,1),
        sum(q['task']=='classification' for q in ordered)/max(n,1), busy/2.,
        float(public['npu_enabled']), clip((public.get('ap_c', reference)-30.)/10.),
        clip((public.get('skin_c', reference)-30.)/10.), clip((reference-30.)/10.),
        *(clip(activity.get(b, 0.)) for b in BACKENDS), public.get('observed_responses', 0)/64.,
        len(ready_ids)/max(n,1)])
    activation=public.get('activation_memory',{})
    slopes=observed_slopes(public,dev.now)
    state_values.extend([clip(public.get('power_w',0.)/10.),
        *(clip(activation.get(b,0.)) for b in BACKENDS),*(clip(v) for v in slopes)])
    actions = [[(q, b)] for q in ordered for b in _routes(dev, q)] + [[]]
    physical = np.zeros(SLOTS, dtype=bool)
    for i, jobs in enumerate(actions[:-1]):
        physical[i] = dev.feasible(jobs)
    # Empty queue returns an all-false bank and is never passed to inference.
    physical[len(actions)-1] = bool(ordered) and busy > 0
    mask = physical.copy()
    if physical[:len(actions)-1].any():
        mask[len(actions)-1] = False
    if ordered and not mask.any():
        raise ValueError('idle unsupported queue; no physical resource-wait progress')
    vectors = np.zeros((SLOTS, ACTION_DIM), dtype=np.float32)
    for i, jobs in enumerate(actions):
        if not jobs:
            vectors[i, 29] = 1.; vectors[i, 30] = float(physical[i])
            continue
        q, b = jobs[0]; ds = paths[q['id'], b]
        vectors[i, :REQUEST_DIM] = rows[q['id']]
        vectors[i, REQUEST_DIM+BACKENDS.index(b)] = 1.
        vectors[i, 25:] = [clip(sum(ds)/6e9), clip(response(ds, q)/6e9),
            clip((q['arrival_ns']+q['deadline_offset_ns']-dev.now-response(ds,q))/6e9),
            clip((q['arrival_ns']+original_cap(q)-dev.now-response(ds,q))/6e9),
            0., float(physical[i]), BACKENDS.index(b)/2.]
    state = np.asarray(state_values, dtype=np.float32)
    if state.shape != (STATE_DIM,) or not np.isfinite(state).all() or not np.isfinite(vectors).all():
        raise ValueError('state/action ABI')
    spreads = [(max(sum(paths[q['id'],b]) for b in _routes(dev,q))
        -min(sum(paths[q['id'],b]) for b in _routes(dev,q)))/1e6 for q in ordered]
    pair_checks=[]
    cs=[q for q in ordered if q['task']=='classification']
    ds=[q for q in ordered if q['task']=='detection']
    if cs and ds:
        for b in ('GPU','NPU'):
            jobs=[(cs[0],b),(ds[0],'CPU')]
            if b in _routes(dev,cs[0]) and dev.feasible(jobs):
                paired=[sum(dev.estimate(q,backend,jobs)) for q,backend in jobs]
                solo=[sum(paths[q['id'],backend]) for q,backend in jobs]
                pair_checks.append(dict(backend=b,estimated_occupancy_ratios=[v/s for v,s in zip(paired,solo)]))
    diagnostics = dict(queue=n, candidates=n, padded_actions=SLOTS, actions=len(actions),
        legal_execution_actions=len(legal_jobs), ready_requests=len(ready_ids),
        atc_us=atc_us, build_us=(time.perf_counter_ns()-begin)/1e3-atc_us,
        total_us=(time.perf_counter_ns()-begin)/1e3, route_spread_mean_ms=sum(spreads)/max(n,1),
        route_spread_max_ms=max(spreads, default=0.),
        atc_order=sorted(scores,key=lambda rid:ranks['ATC'][rid]),
        edd_order=sorted(scores,key=lambda rid:ranks['EDD'][rid]),
        spt_order=sorted(scores,key=lambda rid:ranks['SPT'][rid]),
        atc_edd_order_same=ranks['ATC']==ranks['EDD'], pair_estimate_checks=pair_checks,
        cooling_wait=False)
    return dict(state=state, candidates=vectors, physical_mask=physical, mask=mask,
        actions=actions, diagnostics=diagnostics, ordered=ordered, paths=paths, reps=reps,
        scores=scores, ranks=ranks)


def rule_index(dev, bank, rule, cursor=0, affinity=None):
    if rule not in RULES:
        raise ValueError('unregistered rule')
    legal = [i for i in range(len(bank['actions'])) if bank['mask'][i]]
    execution = [i for i in legal if bank['actions'][i]]
    if not execution:
        return legal[0] if legal else None
    def key(i):
        q, b = bank['actions'][i][0]; ds = bank['paths'][q['id'],b]
        path = (response(ds,q),sum(ds),BACKENDS.index(b))
        if rule == 'RR_READY':
            return (*tie(q),(BACKENDS.index(b)-cursor)%len(BACKENDS))
        if rule == 'GREEDY_READY_V17':
            pref = (affinity or {}).get(q['task'])
            if pref is None:
                pref = min(_routes(dev,q), key=lambda route:
                    (sum(bank['paths'][q['id'],route]),BACKENDS.index(route)))
            return (*tie(q), b!=pref, *path)
        if rule == 'FIFO_READY':
            return (*tie(q),*path)
        if rule == 'SPT':
            # Unrelated-resource ready-SPT: shortest currently legal occupancy,
            # rather than letting an unavailable representative lane block it.
            return (sum(ds),*tie(q),response(ds,q),BACKENDS.index(b))
        if rule == 'EDD':
            return (bank['ranks'][rule][q['id']],*path)
        return (-bank['scores'][q['id']],*tie(q),*path)
    return min(execution, key=key)


def rule_choice(dev, waiting, rule, cursor=0, affinity=None):
    if not waiting:
        return None
    bank = build(dev,waiting); i = rule_index(dev,bank,rule,cursor,affinity)
    return bank['actions'][i] or None if i is not None else None


class Controller:
    """Non-learning rules. V17 greedy is work-conserving, unlike old affinity wait."""
    def __init__(self, rule='ATC', affinity=None):
        if rule not in RULES:
            raise ValueError('rule')
        self.rule=rule; self.affinity=affinity; self.cursor=0
        self.decisions=[]; self.errors=[]; self.frames=[]

    def choose(self,dev,waiting):
        if not waiting:
            return None
        bank=build(dev,waiting)
        i=rule_index(dev,bank,self.rule,self.cursor,self.affinity)
        jobs=bank['actions'][i] if i is not None else []
        if jobs and self.rule=='RR_READY':
            self.cursor=(BACKENDS.index(jobs[0][1])+1)%len(BACKENDS)
        self.decisions.append(dict(now_ns=dev.now, policy=self.rule,
            chosen=[(q['id'],b) for q,b in jobs], **bank['diagnostics']))
        return jobs or None
