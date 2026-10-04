"""Bounded first-visit episodic Monte Carlo control; PC exploration only.

One vector-cost candidate, no neural dependency or physical-model refit. The
coarse observation is not claimed Markov. Expected lexicographic costs are
heuristics, not deadline/thermal guarantees. Future outcomes enter training
after the episode only; the deployed decision callback sees causal state only.
"""
from __future__ import annotations
import argparse
import bisect
import copy
import csv
from datetime import datetime, timezone
import json
import random
import time
from pathlib import Path
from tools import d1_empirical_request_policy as p
from tools import d1_arrival_explore as engine
from tools import d1_arrival_explore_batch as batch

VERSION = 'request-monte-carlo-rl-v1'
CONTRACT = p.ROOT / 'docs/results/request_rl_01/contract.json'
FAMILIES = ('low', 'queue', 'burst', 'sustained')
SCENARIOS = ('mean', 'short_context', 'long_context')
BASELINES = ('CPU_REFERENCE', 'SPLIT_REFERENCE', 'EFT_REFERENCE', 'ENERGY_AP_REQUEST_V1')


def workload(family, seed):
    """Fixed distribution, never selected by predicted cost or success."""
    rng = random.Random(seed * 10 + FAMILIES.index(family))
    n = 192 if family == 'sustained' else 24
    tasks = ['classification'] * (n // 2 if n == 192 else 6)
    tasks += ['detection'] * (n - len(tasks))
    rng.shuffle(tasks)
    interval = dict(low=1.2, queue=.2, burst=.08, sustained=.4)[family]
    now = 35.; tickets = []
    for i, task in enumerate(tasks):
        if i:
            now += interval * rng.uniform(.95, 1.05)
            if family == 'burst' and i % 6 == 0: now += 1.
        tickets.append(dict(id=f'{seed}/{family}/{i}', ordinal=i, task=task,
            priority='urgent' if task == 'classification' else 'normal',
            arrival_ns=round(now * 1e9),
            deadline_offset_ns=1_500_000_000 if task == 'classification' else 6_000_000_000))
    return tickets


def update_table(table, trajectory, cost):
    """First visit per (state, action); undiscounted terminal vector cost."""
    for state, action in dict.fromkeys(trajectory):
        row = table.setdefault(state, {}).setdefault(action, dict(n=0, mean=[0.] * 4))
        row['n'] += 1
        row['mean'] = [old + (value - old) / row['n'] for old, value in zip(row['mean'], cost)]


class Learner(p.Controller):
    def __init__(self, frozen, initial, estimates, table, epsilon=0., seed=0):
        super().__init__(frozen, initial, estimates, p.RL_POLICY)
        self.table = table; self.epsilon = epsilon; self.rng = random.Random(seed)
        self.trajectory = []

    def features(self, ordered, lanes, now):
        q = ordered[0]
        slack = (q['arrival_ns'] + q['deadline_offset_ns']) / 1e9 - now
        # No request ID, total future count, workload family, scenario or seed.
        values = [q['task'], bisect.bisect_right([0, .25, .75, 1.5, 3, 6], slack),
            int(max(0., p.END-now)//15),
            min(4, sum(x['priority'] == 'urgent' for x in ordered)),
            min(4, sum(x['priority'] == 'normal' for x in ordered)),
            bisect.bisect_right([.25, .75, 1.5, 2.], now - q['arrival_ns'] / 1e9),
            bisect.bisect_right([0, 1, 2, 4], self.t - self.init['reference_c']),
            bisect.bisect_right([0, .01, .03], self.h)]
        for backend in ('CPU', 'GPU'):
            lane = lanes[backend]
            values.append('idle' if lane['request'] is None else lane['request']['task'] + ':' + lane['phase'])
        return json.dumps(values, separators=(',', ':'))

    def __call__(self, config, queue, lanes, now_ns, settings, thermal_model, current_ap):
        # Inherited entry validates no future ticket/private engine state and
        # supplies deterministic EFT fallback under the new explicit policy ID.
        fallback = super().__call__(config, queue, lanes, now_ns, settings, thermal_model, current_ap)
        if not queue or fallback['reason'] == 'unknown_overrun_wait_for_event': return fallback
        now = now_ns / 1e9
        ordered = sorted(queue, key=lambda q: (0 if now_ns-q['arrival_ns'] >= settings['aging_ns'] else
            1 if q['priority'] == 'urgent' else 2, q['arrival_ns']+q['deadline_offset_ns'], q['ordinal'], q['id']))
        q = ordered[0]; active = self.active_jobs(lanes, now)
        actions = {b: self.place(q, b, now, active) for b in p.backends(q)}
        actions = {b: j for b, j in actions.items() if j['start'] <= now + 1e-9}
        if not actions: return dict(fallback, reason='RL_busy_EFT_event_wait')
        delay = min(p.WAIT_STEP, max(0., p.WAIT_LIMIT - (now-q['arrival_ns']/1e9)))
        # Local head guard only; no claim about pending/future requests.
        if delay > 1e-9 and any(j['response']+delay <= j['deadline']+1e-9 for j in actions.values()):
            actions['WAIT'] = None
        state = self.features(ordered, lanes, now)
        known = {a: self.table.get(state, {}).get(a) for a in actions}
        known = {a: r for a, r in known.items() if r is not None}
        if self.epsilon and self.rng.random() < self.epsilon:
            action = self.rng.choice(sorted(actions)); reason = 'RL_training_exploration'
        elif known:
            action = min(known, key=lambda a: (tuple(known[a]['mean']), a)); reason = 'RL_learned_action'
        else:
            if fallback['selected'] is None:
                return dict(fallback, reason='RL_unseen_state_EFT_fallback', state_key=state)
            action = fallback['selected']['backend']
            reason = 'RL_unseen_state_EFT_fallback'
        self.trajectory.append((state, action))
        result = dict(now_ns=now_ns, selected=None, reason=reason, state_key=state, rl_action=action,
            feasible_actions=sorted(actions), head_request_id=q['id'], modeled_ap_c=self.t)
        if action == 'WAIT':
            result.update(wait_until_ns=now_ns+delay*1e9, chosen_explicit_delay_s=delay)
        else: result['selected'] = dict(request_id=q['id'], backend=action)
        return result


def simulate(frozen, initial, tickets, scenario, policy, table=None, epsilon=0., seed=0):
    estimates = p.profile(frozen); actual = p.profile(frozen, scenario)
    vectors = dict(cells={k: [dict(source_request_id='development_context_'+scenario, durations_ns=v)
                            for _ in range(4)] for k, v in actual.items()})
    settings = batch.defaults('explore')
    settings.update(decision_ns=0, record_ns=0, dispatch_ns=0, interference=1., predicted_interference=1.)
    c = (Learner(frozen, initial, estimates, table, epsilon, seed) if policy == p.RL_POLICY else
         p.Controller(frozen, initial, estimates, policy))
    result = engine.simulate(dict(protocol=p.VERSION, cells=estimates), vectors, tickets,
        policy=policy, settings=settings, seed=seed, decision_provider=c)
    ss, costs, ap_end = p.account(result, initial, frozen)
    rows = result['ledger']; decisions = result['decisions']
    met = sum('response_ns' in r and r['response_ns'] <= r['deadline_offset_ns'] for r in rows)
    row = dict(policy=policy, planned=len(rows), completed=sum(r['status']=='succeeded' for r in rows),
        deadline_met=met, deadline_misses=len(rows)-met, energy_120s_j=costs['whole_120s_j'],
        peak_ap_35_180_c=max(costs['ap_path']) if ap_end == 180 else None,
        urgent_p95_ms=result['metrics']['urgent_p95_ms'],
        overlap_s=sum(x['end_s']-x['start_s'] for x in ss if '+' in x['state']),
        learned_decisions=sum(d['reason']=='RL_learned_action' for d in decisions),
        unseen_fallbacks=sum(d['reason']=='RL_unseen_state_EFT_fallback' for d in decisions),
        wait_decisions=sum(d.get('rl_action')=='WAIT' for d in decisions))
    return row, result, c


def terminal_cost(row, reference):
    # Penalty sentinel is training bookkeeping, never a fabricated AP observation.
    ap = (max(0., row['peak_ap_35_180_c'] - reference['peak_ap_35_180_c'])
          if row['peak_ap_35_180_c'] is not None and reference['peak_ap_35_180_c'] is not None else 1000.)
    return [row['deadline_misses']/row['planned'], ap,
            row['energy_120s_j']-reference['energy_120s_j'], row['urgent_p95_ms'] or 120000.]


def csv_write(path, rows):
    with Path(path).open('w', encoding='utf8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)


def run(output):
    contract = json.loads(CONTRACT.read_text(encoding='utf8'))
    if contract != specification(): raise ValueError('contract/code differ')
    start = time.monotonic(); output = Path(output); output.mkdir(parents=True, exist_ok=False)
    frozen, case = p.inputs(p.BUNDLE)
    initial = {k: copy.deepcopy(case['initial'][k]) for k in ('preload', 'preload_power_w')}
    sources = [Path(__file__), Path(p.__file__), Path(engine.__file__), CONTRACT,
               p.BUNDLE/'model.json', p.BUNDLE/'initial_inputs.json']
    hashes = {str(x.relative_to(p.ROOT)): p.digest(x) for x in sources}
    p.write(output/'preregistered.json', dict(contract=contract, hashes=hashes,
        recorded_utc=datetime.now(timezone.utc).isoformat()))
    traces = {str(seed): {f: workload(f, seed) for f in FAMILIES}
              for seed in contract['train_seeds']+contract['evaluation_seeds']}
    p.write(output/'inputs.json', dict(traces=traces, initial=initial))
    def bound():
        if time.monotonic()-start > contract['max_wall_seconds']:
            raise TimeoutError('PC budget reached; preserve checkpoint, no automatic restart')
    table = {}; train = []
    episodes = [(s, f, c) for s in contract['train_seeds'] for f in FAMILIES for c in SCENARIOS]
    random.Random(42).shuffle(episodes)
    for i, (seed, family, scenario) in enumerate(episodes):
        bound(); tickets = traces[str(seed)][family]
        ref, _, _ = simulate(frozen, initial, tickets, scenario, 'EFT_REFERENCE', seed=seed)
        epsilon = .3-(.3-.05)*i/(len(episodes)-1)
        row, _, learner = simulate(frozen, initial, tickets, scenario, p.RL_POLICY, table, epsilon, 9000+i)
        cost = terminal_cost(row, ref); update_table(table, learner.trajectory, cost)
        train.append(dict(episode=i+1, seed=seed, family=family, scenario=scenario, epsilon=epsilon,
                          cost=cost, states=len(table), **row))
        if (i+1) % 12 == 0:
            p.write(output/'checkpoint.json', dict(completed_training=i+1, elapsed_s=time.monotonic()-start, table=table))
            print(f'training {i+1}/{len(episodes)} states={len(table)}', flush=True)
    p.write(output/'learned_table.json', dict(version=VERSION, table=table, fitting_data='synthetic training episodes only'))
    learned_hash = p.digest(output/'learned_table.json')
    p.write(output/'freeze_before_evaluation.json', dict(policy_sha256=learned_hash,
        training_episodes=len(train), elapsed_s=time.monotonic()-start, evaluated=False,
        recorded_utc=datetime.now(timezone.utc).isoformat()))
    csv_write(output/'training.csv', train)
    results = []; details = []
    for seed in contract['evaluation_seeds']:
        for family in FAMILIES:
            for scenario in SCENARIOS:
                for policy in (*BASELINES, p.RL_POLICY):
                    bound()
                    row, result, _ = simulate(frozen, initial, traces[str(seed)][family], scenario,
                        policy, table, 0., seed)
                    results.append(dict(seed=seed, family=family, scenario=scenario, **row))
                    details.append(dict(seed=seed, family=family, scenario=scenario, policy=policy,
                                        ledger=result['ledger'], decisions=result['decisions']))
                print(f'evaluation {seed}/{family}/{scenario}', flush=True)
    if learned_hash != p.digest(output/'learned_table.json'): raise ValueError('frozen policy changed')
    # Evaluation must not mutate the in-memory table either.
    if table != json.loads((output/'learned_table.json').read_text(encoding='utf8'))['table']:
        raise ValueError('evaluation learned from held-out outcomes')
    if hashes != {str(x.relative_to(p.ROOT)): p.digest(x) for x in sources}: raise ValueError('source drift')
    csv_write(output/'comparison.csv', results)
    p.write(output/'local_details.json', details)
    p.write(output/'summary.json', dict(version=VERSION, training_episodes=len(train),
        training_reference_runs=len(train), evaluation_runs=len(results), elapsed_s=time.monotonic()-start,
        policy_sha256=learned_hash, results=results, device_commands=0, policy_winner=None,
        strict_supported=False, independent_device_validation=False, experiment_ready=False))
    return output


def specification():
    return dict(version=VERSION, candidate=p.RL_POLICY,
        algorithm='first-visit episodic Monte Carlo, sample-mean vector cost, lexicographic greedy epsilon control',
        train_seeds=list(range(1001,1009)), evaluation_seeds=[2001,2002], families=list(FAMILIES),
        baselines=list(BASELINES),
        service_scenarios=list(SCENARIOS), train_episodes=96, training_reference_runs=96, evaluation_runs=120,
        max_wall_seconds=1800, training_order_seed=42, epsilon=[.3,.05], discount=1.,
        objective=['min expected missed fraction (missing response counts)',
                   'min expected positive peak AP excess over paired EFT',
                   'min expected 120s J difference vs paired EFT', 'min expected urgent P95'],
        actions=['legal immediate CPU', 'legal immediate GPU', 'wait <=250ms; arrival age <=2s; local head deadline guard'],
        state='head task/slack/age; remaining window 15s bins; capped arrived queue counts; lane task/phase; modeled T-reference and H bins; no future',
        workload='fixed counts 24/192; shuffled task order; each interval uniform +/-5%; 35s start; seed fixed before outcomes',
        unseen='EFT fallback; no evaluation updates', selection='last training checkpoint only; no hyperparameter search',
        evaluation='24 paired synthetic conditions, completion/deadline/P95/J/AP separately; no measured accuracy PASS',
        promotion='no default/device adoption; no future error bounds; failures retained; no post-evaluation retuning',
        limitations=['coarse partially observed state', 'finite exploration; no convergence proof',
                     'expected priorities are not per-episode guarantees', 'common service transfer assumption',
                     'no temperature-to-throughput model', 'zero additional controller execution cost',
                     'fixed previously seen initial inputs', 'context extrema are not confidence bounds'],
        existing_model_sha256=p.MODEL_SHA, existing_initial_sha256=p.INITIAL_SHA,
        new_device_plan=False, device_commands=0, experiment_ready=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--output', required=True)
    args = parser.parse_args(); print(run(args.output))
