"""Opt-in causal queue PPO; PC only. Check/smoke/run/status entry points.

Keep the measured model and the historical PPO/engine byte-identical.
"""
from __future__ import annotations
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import signal
import sys
import time
import uuid

import numpy as np
import torch
from torch import nn
from tools import d1_request_ppo as prev

p, old = prev.p, prev.old
PLAN = p.ROOT / 'docs/results/request_ppo_01/queue_training_plan_v1.json'
VERSION = 'request-queue-ppo-v1'
DIMENSION = 85
LOCK = p.ROOT / 'output/.queue_ppo_active.json'


def atomic(path, obj):
    """A failed receipt must not replace the last readable checkpoint."""
    path = Path(path)
    temp = path.with_name(path.name + '.tmp')
    with temp.open('w', encoding='utf8') as stream:
        json.dump(obj, stream, ensure_ascii=False, allow_nan=False, indent=2)
        stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
    os.replace(temp, path)


def files():
    return list(dict.fromkeys([Path(__file__), PLAN, *prev.sources(),
        Path(p.model.__file__), Path(p.memory.__file__), Path(old.batch.__file__),
        p.ROOT / 'tools/RUN_QUEUE_PPO.ps1']))


def hashes():
    return {str(f.relative_to(p.ROOT)).replace('\\', '/'): p.digest(f) for f in files()}


def load_plan():
    obj = json.loads(PLAN.read_text(encoding='utf8'))
    if obj['version'] != 'request-ppo-queue-final-plan-v1':
        raise ValueError('plan version')
    if obj['deadlines_ns'] != dict(classification_output_ready=1500000000,
                                  detection_persist_complete=6000000000):
        raise ValueError('deadline contract')
    if obj['actions']['output_slots'] != 17 or obj['budget']['formal_simulation_runs_total'] != 17936:
        raise ValueError('fixed plan budget')
    for name, digest in obj['frozen_files'].items():
        if p.digest(p.ROOT / name) != digest: raise ValueError('frozen source hash: ' + name)
    return obj


def cases(plan):
    data = plan['data']; families = data['families']; contexts = data['service_contexts']
    start = data['train_trace_seed_range_inclusive'][0]
    train = [(start+i//4, families[i % 4], contexts[(i//4+i % 4) % 3]) for i in range(2048)]
    def cross(name):
        a, b = data[name + '_trace_seed_range_inclusive']
        return [(s, f, c) for s in range(a, b+1) for f in families for c in contexts]
    return train, cross('validation'), cross('test')


def input_manifest(plan):
    groups = cases(plan); all_seeds = {c[0] for group in groups for c in group}
    conflicts = []
    def scan(value, path):
        if isinstance(value, dict):
            for key, item in value.items():
                if key == 'seed' or key.endswith('_seed') or key.endswith('_seeds'):
                    ints = item if isinstance(item, list) else [item]
                    if any(type(x) is int and x in all_seeds for x in ints): conflicts.append(str(path))
                scan(item, path)
        elif isinstance(value, list):
            for item in value: scan(item, path)
    # Registered JSON and tabular trace-seed fields only; numeric neural weights
    # are not seed evidence. Missing external histories remain a stated limit.
    for path in (p.ROOT / 'docs/results').rglob('*.json'):
        if path == PLAN or 'actor' in path.name or path.name == 'task_deadline_contract_v1.json': continue
        if path.stat().st_size > 20_000_000: continue
        try: value = json.loads(path.read_text(encoding='utf8'))
        except (ValueError, UnicodeError): continue
        scan(value, path.relative_to(p.ROOT))
    for path in (p.ROOT / 'docs/results').rglob('*.csv'):
        with path.open(encoding='utf8', newline='') as stream:
            rows = csv.DictReader(stream)
            names = [n for n in (rows.fieldnames or []) if n in ('seed', 'trace_seed', 'arrival_seed')]
            if not names: continue
            for row in rows:
                if any(row[n].isdigit() and int(row[n]) in all_seeds for n in names):
                    conflicts.append(str(path.relative_to(p.ROOT))); break
    if conflicts: raise ValueError('previous seed usage: ' + ', '.join(sorted(set(conflicts))))
    trace_hashes = {}; split_keys = []
    for group in groups:
        keys = set()
        for seed, family, _ in group:
            key = (seed, family)
            if key not in trace_hashes:
                raw = json.dumps(old.workload(family, seed), sort_keys=True, separators=(',', ':')).encode()
                trace_hashes[key] = hashlib.sha256(raw).hexdigest()
            keys.add(trace_hashes[key])
        split_keys.append(keys)
    if any(split_keys[i] & split_keys[j] for i in range(3) for j in range(i)):
        raise ValueError('input split hash collision')
    return dict(ordered_cases=[list(map(list, group)) for group in groups],
        trace_hashes={f'{s}/{f}': h for (s, f), h in trace_hashes.items()},
        seed_history_scope='accessible repository registered JSON/CSV; external unregistered histories unknown')


class ActorCritic(nn.Module):
    def __init__(self):
        super().__init__()
        self.body = nn.Sequential(nn.Linear(DIMENSION, 64), nn.Tanh(), nn.Linear(64, 64), nn.Tanh())
        self.actor = nn.Linear(64, 17); self.value = nn.Linear(64, 5)
        for layer in self.modules():
            if isinstance(layer, nn.Linear):
                nn.init.orthogonal_(layer.weight, math.sqrt(2)); nn.init.zeros_(layer.bias)
        nn.init.orthogonal_(self.actor.weight, .01); nn.init.orthogonal_(self.value.weight, 1.)

    def forward(self, obs, mask):
        if not torch.all(mask.any(-1)): raise ValueError('empty action mask')
        h = self.body(obs)
        return torch.distributions.Categorical(logits=self.actor(h).masked_fill(~mask, -1e9)), self.value(h)


class Controller(p.Controller):
    def __init__(self, frozen, initial, variant, network=None, deterministic=True):
        super().__init__(frozen, initial, p.profile(frozen), p.PPO_POLICY)
        if variant not in ('HEAD', 'QUEUE', 'SHARED_EDF', 'SHARED_EFT'): raise ValueError('variant')
        self.variant = variant; self.network = network; self.deterministic = deterministic
        self.seen = {}; self.rollout_data = []; self.action_counts = [0]*17; self.choices = 0

    def age_limit(self, q):
        p.backends(q)
        ref = sum(self.estimates[p.key(q, 'CPU')][:2 if q['priority'] == 'urgent' else 3])/1e9
        return min(2., max(0., q['deadline_offset_ns']/1e9 - math.ceil(ref*1000)/1000))

    @staticmethod
    def due_key(q):
        return (q['arrival_ns']+q['deadline_offset_ns'], q['arrival_ns'], q['ordinal'], q['id'])

    def schedule_score(self, queue, active, now):
        jobs = list(active)
        for q in queue:
            jobs.append(min((self.place(q, b, now, jobs) for b in p.backends(q)),
                            key=lambda j: (j['response'], j['backend'] != 'CPU')))
        pending = [j for j in jobs if not j['already_responded']]
        return (sum(j['response'] > j['deadline']+1e-9 for j in pending),
                sum(max(0., j['response']-j['deadline']) for j in pending))

    def legal(self, queue, lanes, now):
        if any(q['arrival_ns']/1e9 > now for q in queue): raise ValueError('future ticket')
        if any(set(x) != {'request', 'phase', 'since', 'dispatch'} for x in lanes.values()):
            raise ValueError('private lane data')
        ordered = sorted(queue, key=lambda q: (0 if now-q['arrival_ns']/1e9 >= self.age_limit(q)
                         else 1 if q['priority'] == 'urgent' else 2, *self.due_key(q)))
        active = self.active_jobs(lanes, now)
        if active is None: return ordered[:8], np.zeros(17, bool), 0., 'unknown_overrun_event_wait'
        immediate = {}
        for q in ordered:
            for b in p.backends(q):
                job = self.place(q, b, now, active)
                if job['start'] <= now+1e-9: immediate[(q['id'], b)] = job
        aged = [q for q in ordered if now-q['arrival_ns']/1e9 >= self.age_limit(q)
                and any((q['id'], b) in immediate for b in p.backends(q))]
        forced = min(aged, key=self.due_key) if aged else None
        if forced: ordered = [forced] + [q for q in ordered if q['id'] != forced['id']]
        candidates = ordered[:8]
        mask = np.zeros(17, bool)
        for i, q in enumerate(candidates):
            for j, b in enumerate(('CPU', 'GPU')):
                mask[2*i+j] = ((q['id'], b) in immediate and
                    (not forced or q['id'] == forced['id']) and (self.variant != 'HEAD' or i == 0))
        delay = min([.25] + [max(0., self.age_limit(q)-(now-q['arrival_ns']/1e9)) for q in ordered])
        if mask.any() and not forced and delay > 1e-9:
            before = self.schedule_score(ordered, active, now)
            after = self.schedule_score(ordered, active, now+delay)
            mask[16] = after[0] <= before[0] and after[1] <= before[1]+1e-9
        return candidates, mask, delay, 'forced_aging' if forced else 'legal'

    def __call__(self, config, queue, lanes, now_ns, cfg, thermal_model, current_ap):
        now = now_ns/1e9
        out = dict(now_ns=now_ns, selected=None, reason='queue_PPO_event_wait')
        if not queue: return out
        candidates, mask, delay, reason = self.legal(queue, lanes, now)
        if not mask.any(): return dict(out, reason=reason)
        # Reuse the frozen 85-field causal observation; its queued aggregates see
        # all currently arrived tickets, while slots use the forced candidate order.
        ordered = candidates + [q for q in queue if q['id'] not in {x['id'] for x in candidates}]
        obs = prev.Controller.observation(self, ordered, lanes, now)
        if self.network is None:
            allowed = [a for a in range(16) if mask[a]]
            active = self.active_jobs(lanes, now)
            def rank(a):
                q = candidates[a//2]; b = ('CPU', 'GPU')[a % 2]
                response = self.place(q, b, now, active)['response']
                return ((*self.due_key(q), response, b != 'CPU') if self.variant == 'SHARED_EDF'
                        else (response, *self.due_key(q), b != 'CPU'))
            action = min(allowed, key=rank)
        else:
            with torch.no_grad():
                dist, values = self.network(torch.from_numpy(obs)[None], torch.from_numpy(mask)[None])
                a = dist.probs.argmax(-1) if self.deterministic else dist.sample()
                action = int(a.item())
                self.rollout_data.append(dict(t=now, obs=obs, mask=mask.copy(), action=action,
                    logprob=float(dist.log_prob(a).item()), value=values[0].numpy()))
        self.action_counts[action] += 1; self.choices += int(mask.sum() > 1)
        out.update(reason=reason, action_slot=action, candidate_ids=[q['id'] for q in candidates],
                   valid_actions=mask.tolist(), modeled_ap_c=self.t)
        if action == 16: out.update(wait_until_ns=round(now_ns+delay*1e9), chosen_explicit_delay_s=delay)
        else: out['selected'] = dict(request_id=candidates[action//2]['id'], backend=('CPU', 'GPU')[action % 2])
        return out


def simulate(frozen, initial, tickets, scenario, variant, network=None, deterministic=True):
    if variant in ('CPU_REFERENCE', 'SPLIT_REFERENCE', 'EFT_REFERENCE'):
        row, result, _, _ = prev.simulate(frozen, initial, tickets, scenario, policy=variant)
        row['equal_work'] = all(r.get('lane_available_ns', math.inf) <= 120e9 for r in result['ledger'])
        return row, result, None, None
    controller = Controller(frozen, initial, variant, network, deterministic)
    vectors = dict(cells={k: [dict(source_request_id='common_context_'+scenario, durations_ns=v)
                        for _ in range(4)] for k, v in p.profile(frozen, scenario).items()})
    result = old.engine.simulate(dict(protocol=p.VERSION, cells=p.profile(frozen)), vectors, tickets,
        policy=p.PPO_POLICY, settings=prev.settings(), seed=201, decision_provider=controller)
    row, extra = prev.outcome(result, initial, frozen)
    row.update(equal_work=all(r.get('lane_available_ns', math.inf) <= 120e9 for r in result['ledger']),
               actions=controller.action_counts, controllable_decisions=controller.choices)
    return row, result, controller, extra


def rewards(controller, result, extra, initial, frozen):
    ss, grid, rise, end = extra; trace = controller.rollout_data
    if not trace or end != 180: raise ValueError('missing decision/AP cost; no zero-filled training')
    cuts = np.array([0.] + [x['t'] for x in trace[1:]] + [180.])
    area = np.concatenate(([0.], np.cumsum((rise[:-1]+rise[1:])*.5*np.diff(grid))))
    area_at = np.interp(cuts, grid, area, left=0., right=area[-1])
    # rise is clipped at the effective idle reference and cannot reconstruct
    # absolute AP below it. Use the unchanged model's absolute path for peaks.
    ap = np.asarray(p.model.costs(ss, initial, list(grid), frozen, float(end))['ap_path'], dtype=float)
    running = np.maximum.accumulate(ap)
    # Account grid samples in (a,b]; first interval receives the initial peak.
    peaks = np.array([running[min(len(running)-1, max(0, np.searchsorted(grid, x, side='right')-1))]
                      if x >= grid[0] else 0. for x in cuts])
    channels = np.zeros((len(trace), 5), dtype=np.float64)
    for i, (a, b) in enumerate(zip(cuts, cuts[1:])):
        energy = initial['preload_power_w']*max(0., min(b, 120)-a)
        for s in ss:
            overlap = max(0., min(b, 120, s['end_s'])-max(a, s['start_s']))
            state = s['state']
            if state != 'idle' and state not in frozen['energy_increment_w']:
                raise ValueError('unsupported cost state: '+state)
            energy += overlap*frozen['energy_increment_w'].get(state, 0.)
        channels[i, 0] = -energy/10
        channels[i, 3] = (area_at[i+1]-area_at[i])/100
        channels[i, 4] = peaks[i+1]-peaks[i]
    count = {key: sum(r['priority'] == key for r in result['ledger']) for key in ('urgent', 'normal')}
    for r in result['ledger']:
        if r['status'] != 'succeeded' or r.get('response_ns', math.inf) > r['deadline_offset_ns']:
            index = max(0, min(len(trace)-1, np.searchsorted(cuts,
                (r['arrival_ns']+r['deadline_offset_ns'])/1e9, side='right')-1))
            channels[index, 1 if r['priority'] == 'urgent' else 2] += 1/count[r['priority']]
    return channels.astype(np.float32)


def costs(row, ref):
    if any(row[k] is None or ref[k] is None for k in ('energy_j', 'thermal_degree_seconds', 'peak_ap_c')):
        raise ValueError('unavailable cost; retained null, training stopped')
    return np.array([row['urgent_service_failure']/row['urgent_n'],
        row['normal_service_failure']/row['normal_n'],
        (row['thermal_degree_seconds']-ref['thermal_degree_seconds'])/100,
        row['peak_ap_c']-ref['peak_ap_c']], dtype=float)


def gae(channels, values):
    advantage = np.zeros_like(channels); carry = np.zeros(5, dtype=np.float32)
    for t in reversed(range(len(channels))):
        nxt = values[t+1] if t+1 < len(values) else np.zeros(5, dtype=np.float32)
        carry = channels[t]+nxt-values[t]+.95*carry; advantage[t] = carry
    return advantage, advantage+values


def pack(episodes):
    data = {key: [] for key in ('obs', 'mask', 'actions', 'old_logprob', 'advantages', 'returns')}
    for controller, channels in episodes:
        trace = controller.rollout_data
        adv, ret = gae(channels, np.stack([x['value'] for x in trace]))
        for key, source in [('obs', 'obs'), ('mask', 'mask'), ('actions', 'action'), ('old_logprob', 'logprob')]:
            data[key].extend(x[source] for x in trace)
        data['advantages'].extend(adv); data['returns'].extend(ret)
    return {key: torch.tensor(np.array(value)) for key, value in data.items()}


def save_actor(path, network):
    atomic(path, dict(version=VERSION, dimension=DIMENSION, sha256=prev.model_hash(network),
                      tensors={k: v.detach().tolist() for k, v in network.state_dict().items()}))


def load_actor(path):
    obj = json.loads(Path(path).read_text(encoding='utf8')); network = ActorCritic()
    if obj['version'] != VERSION or obj['dimension'] != DIMENSION: raise ValueError('actor schema')
    network.load_state_dict({k: torch.tensor(v, dtype=torch.float32) for k, v in obj['tensors'].items()})
    if prev.model_hash(network) != obj['sha256']: raise ValueError('actor hash')
    network.eval(); return network


def validation_key(rows, refs):
    v = [costs(r, ref) for r, ref in zip(rows, refs)]
    return (sum(not r['equal_work'] for r in rows), sum(x[0] > 0 or x[1] > 0 for x in v),
        sum(x[0]+x[1] for x in v), sum(x[2] > 1e-9 or x[3] > 1e-9 for x in v),
        sum(max(0., x[2])+max(0., x[3]) for x in v), np.mean([r['energy_j'] for r in rows]),
        np.mean([r['urgent_p95_ms'] if r['urgent_p95_ms'] is not None else math.inf for r in rows]),
        np.mean([r['normal_mean_ms'] if r['normal_mean_ms'] is not None else math.inf for r in rows]))


def check():
    plan = load_plan(); inputs = input_manifest(plan)
    if LOCK.exists(): raise ValueError('active or unresolved owner lock: '+str(LOCK))
    return dict(version=VERSION, status='CHECK_PASSED', plan_sha256=p.digest(PLAN),
        sources=hashes(), ordered_input_sha256=hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest(),
        observation_dimension=DIMENSION, runtime=dict(python=sys.version, torch=torch.__version__, numpy=np.__version__),
        input_history_scope=inputs['seed_history_scope'], device_commands=0)


class Recorder:
    def __init__(self, output, limit):
        self.output = Path(output); self.start = time.monotonic(); self.limit = limit
        self.counts = dict(training=0, validation=0, test=0, reference=0, smoke=0)
        self.id = uuid.uuid4().hex
        self.output.mkdir(parents=True, exist_ok=False)
        LOCK.parent.mkdir(parents=True, exist_ok=True)
        with LOCK.open('x', encoding='utf8') as stream:
            json.dump(dict(run_id=self.id, pid=os.getpid(), started_utc=datetime.now(timezone.utc).isoformat(),
                           output=str(self.output.resolve()), command=sys.argv), stream)
        self.note('started', run_id=self.id, pid=os.getpid())

    def note(self, stage, **fields):
        obj = dict(stage=stage, utc=datetime.now(timezone.utc).isoformat(), elapsed_s=round(time.monotonic()-self.start, 3),
                   counts=self.counts.copy(), **fields)
        atomic(self.output/'progress.json', obj)
        with (self.output/'journal.jsonl').open('a', encoding='utf8') as stream:
            stream.write(json.dumps(obj, ensure_ascii=False, allow_nan=False)+'\n'); stream.flush()
        print(json.dumps(obj, ensure_ascii=False, allow_nan=False), flush=True)

    def budget(self):
        if time.monotonic()-self.start >= self.limit-120: raise TimeoutError('PC budget: 120s reserved for receipt')

    def finish(self, status, error=None):
        receipt = dict(status=status, run_id=self.id, counts=self.counts, elapsed_s=time.monotonic()-self.start,
                       error=error, device_commands=0, experiment_ready=False, independent_device_validation=False)
        record_ok = True
        try: atomic(self.output/'FINAL_RECEIPT.json', receipt)
        except Exception as later:
            record_ok = False
            print('receipt write failed: '+repr(later)+'; original='+repr(error), flush=True)
            try: atomic(self.output/'RECEIPT_ERROR.json', dict(original_error=error, receipt_error=repr(later)))
            except Exception: pass
        finally:
            try: self.note(status if record_ok else status+'_receipt_failed', original_error=error)
            except Exception as later: print('final progress write failed: '+repr(later)+'; original='+repr(error), flush=True)
            try:
                if LOCK.exists() and json.loads(LOCK.read_text(encoding='utf8')).get('run_id') == self.id: LOCK.unlink()
            except Exception as later: print('owner lock release failed: '+repr(later), flush=True)
        return record_ok


def run(output, smoke=False):
    import traceback
    manifest = check(); plan = load_plan()
    recorder = Recorder(output, 900 if smoke else 7200)
    original = None
    try:
        atomic(recorder.output/'run_manifest.json', dict(manifest, plan=plan, inputs=input_manifest(plan),
            mode='smoke_fixture_not_training_result' if smoke else 'formal', observation_schema_source='Controller.observation in frozen d1_request_ppo.py',
            optimizer_source='optimize in frozen d1_request_ppo.py', source_hashes=hashes()))
        frozen, case = p.inputs(p.BUNDLE); initial = {k: case['initial'][k] for k in ('preload', 'preload_power_w')}
        if smoke:
            # Same training->selection->freeze->test implementation as Run.
            # Train/validation deliberately share a fixture; never research data.
            formal(recorder, plan, frozen, initial, fixture=True)
        else:
            formal(recorder, plan, frozen, initial)
        if manifest['sources'] != hashes(): raise ValueError('source drift during run')
    except BaseException as exc:
        original = dict(type=type(exc).__name__, message=str(exc), stack=traceback.format_exc())
        try: atomic(recorder.output/'ORIGINAL_ERROR.json', original)
        except Exception as later: print('original evidence write failed: '+repr(later), flush=True)
        recorder.finish('stopped_no_automatic_restart', original)
        raise
    else:
        if not recorder.finish('smoke_completed' if smoke else 'formal_completed'):
            raise OSError('normal receipt write failed; checkpoint and receipt-error evidence retained')


def formal(rec, plan, frozen, initial, fixture=False):
    train, val_cases, test_cases = cases(plan); refs = {}; selected = []; validations = []; ref_ledgers = {}
    variants = plan['variants']; learning_seeds = plan['learning_seeds']
    updates = 256; batch_size = 8; validation_updates = (64, 128, 192, 256)
    if fixture:
        train = val_cases = [(101, 'queue', 'mean')]; test_cases = [(102, 'queue', 'short_context')]
        variants = ['QUEUE']; learning_seeds = [101]; updates = batch_size = 1; validation_updates = (1,)
    final_cases = set(test_cases)
    def reference(case):
        if case not in refs:
            rec.budget(); s, f, c = case
            row, result, _, _ = simulate(frozen, initial, old.workload(f, s), c, 'SHARED_EFT')
            refs[case] = row
            if case in final_cases: ref_ledgers[case] = result
            rec.counts['reference'] += 1
        return refs[case]
    def validate(network, variant, seed, update):
        before = prev.model_hash(network); rows = []; reference_rows = []
        for case in val_cases:
            rec.budget(); s, f, c = case
            row = simulate(frozen, initial, old.workload(f, s), c, variant, network)[0]
            rec.counts['validation'] += 1; rows.append(row); reference_rows.append(reference(case))
            validations.append(dict(variant=variant, seed=seed, update=update, trace_seed=s, family=f, context=c, **row))
        if prev.model_hash(network) != before: raise ValueError('validation altered network')
        old.csv_write(rec.output/'validation.csv', validations)
        key = tuple(float(x) for x in validation_key(rows, reference_rows))
        rec.note('validation', variant=variant, seed=seed, update=update, selection_key=key)
        return key
    for variant in variants:
        for seed in learning_seeds:
            prev.seed_all(seed); network = ActorCritic()
            opt = torch.optim.Adam(network.parameters(), lr=.0003, eps=1e-5)
            multipliers = np.array([10., 10., 1., 1.]); folder = rec.output/f'{variant}_seed{seed}'; folder.mkdir()
            best = validate(network, variant, seed, 0); best_update = 0
            save_actor(folder/'selected_actor.json', network)
            for update in range(1, updates+1):
                rec.budget(); episodes = []; violations = []; batch_rows = []
                for case in train[(update-1)*batch_size:update*batch_size]:
                    rec.budget(); s, f, c = case
                    row, result, controller, extra = simulate(frozen, initial, old.workload(f, s), c, variant, network, False)
                    rec.counts['training'] += 1; batch_rows.append(row)
                    violations.append(costs(row, reference(case)))
                    episodes.append((controller, rewards(controller, result, extra, initial, frozen)))
                stats = prev.optimize(network, opt, pack(episodes), multipliers)
                multipliers = np.clip(multipliers+5*np.mean(violations, axis=0), 0., 100.)
                rec.note('training_fixture' if fixture else 'training', variant=variant, seed=seed, update=update, total_updates=updates,
                    learner_episodes=update*batch_size, energy_J=float(np.mean([r['energy_j'] for r in batch_rows])),
                    mean_costs=np.mean(violations, axis=0).tolist(), multipliers=multipliers.tolist(), **stats)
                if update % 16 == 0 or update == updates:
                    temp = folder/'checkpoint.pt.tmp'
                    torch.save(dict(network=network.state_dict(), optimizer=opt.state_dict(), update=update,
                        multipliers=multipliers, torch_rng=torch.get_rng_state(), source_hashes=hashes()), temp)
                    os.replace(temp, folder/'checkpoint.pt')
                if update in validation_updates:
                    key = validate(network, variant, seed, update)
                    if key < best: best = key; best_update = update; save_actor(folder/'selected_actor.json', network)
            selected.append(dict(variant=variant, seed=seed, update=best_update, validation_key=best,
                adoption_eligible=best[0] == 0 and best[1] == 0 and best[3] == 0,
                path=str((folder/'selected_actor.json').relative_to(rec.output)), sha256=p.digest(folder/'selected_actor.json')))
    before_run = json.loads((rec.output/'run_manifest.json').read_text(encoding='utf8'))['source_hashes']
    if before_run != hashes(): raise ValueError('source drift before final-test freeze')
    atomic(rec.output/'freeze_before_test.json', dict(selected=selected, test_started=False, fixture_only=fixture, source_hashes=hashes()))
    rec.note('actors_frozen_opening_test', actors=len(selected), fixture_only=fixture)
    networks = {x['path']: load_actor(rec.output/x['path']) for x in selected}; rows = []
    with (rec.output/'test_ledgers.jsonl').open('x', encoding='utf8') as stream:
        for case in test_cases:
            s, f, c = case; tickets = old.workload(f, s)
            ref = reference(case)
            for policy in plan['baselines']:
                rec.budget()
                if policy == 'SHARED_EFT': row = ref; result = ref_ledgers[case]
                else:
                    row, result, _, _ = simulate(frozen, initial, tickets, c, policy)
                    rec.counts['test'] += 1
                rows.append(dict(trace_seed=s, family=f, context=c, policy=policy, **row))
                if result: stream.write(json.dumps(dict(case=case, policy=policy, ledger=result['ledger']))+'\n')
            for item in selected:
                rec.budget(); policy = f'{item["variant"]}_seed{item["seed"]}'
                row, result, _, _ = simulate(frozen, initial, tickets, c, item['variant'], networks[item['path']])
                rec.counts['test'] += 1
                rows.append(dict(trace_seed=s, family=f, context=c, policy=policy, **row))
                stream.write(json.dumps(dict(case=case, policy=policy, ledger=result['ledger']))+'\n')
            stream.flush(); old.csv_write(rec.output/'test.csv', rows)
            rec.note('test_fixture' if fixture else 'final_test', finished_cases=len(rows)//(len(selected)+5), total_cases=len(test_cases))
    for item in selected:
        if p.digest(rec.output/item['path']) != item['sha256']: raise ValueError('test actor drift')
    expected = (dict(training=1, validation=2, test=5, reference=2, smoke=0) if fixture
                else dict(training=12288, validation=1440, test=1920, reference=2288, smoke=0))
    if rec.counts != expected:
        raise ValueError('formal budget accounting')
    atomic(rec.output/'summary.json', dict(selected=selected, test_rows=len(rows), counts=rec.counts,
        actual_simulations=sum(rec.counts.values()), fixture_only=fixture, policy_winner=None, independent_device_validation=False))
    if not fixture: report(rec.output, rows)


def report(output, rows):
    """Full-case paired readout; invalid/partial work never becomes zero gain."""
    import html
    reference = {(r['trace_seed'], r['family'], r['context']): r for r in rows if r['policy'] == 'SHARED_EFT'}
    paired = []
    for row in rows:
        ref = reference[(row['trace_seed'], row['family'], row['context'])]
        eligible = all(r['equal_work'] and r['urgent_service_failure'] == r['normal_service_failure'] == 0
                       for r in (row, ref))
        costs_valid = all(r[k] is not None for r in (row, ref)
                          for k in ('energy_j', 'peak_ap_c', 'thermal_degree_seconds'))
        item = dict(trace_seed=row['trace_seed'], family=row['family'], context=row['context'], policy=row['policy'],
                    comparison_eligible=eligible and costs_valid)
        for metric in ('energy_j', 'peak_ap_c', 'thermal_degree_seconds'):
            item['delta_'+metric] = row[metric]-ref[metric] if eligible and costs_valid else None
        item['joint_model_improvement'] = bool(item['comparison_eligible'] and
            all(item['delta_'+k] < -1e-9 for k in ('energy_j', 'peak_ap_c', 'thermal_degree_seconds')))
        paired.append(item)
    old.csv_write(Path(output)/'paired_differences.csv', paired)
    body = ['<h1>PC queue PPO final test</h1><p>Model evaluation only; no device validation. '
            'All seeds/cases retained. No automatic policy winner.</p><table><tr><th>Policy</th><th>Cases</th>'
            '<th>Eligible full-work pairs</th><th>Joint model improvement</th></tr>']
    for policy in sorted({r['policy'] for r in paired}):
        group = [r for r in paired if r['policy'] == policy]
        body.append(f'<tr><td>{html.escape(policy)}</td><td>{len(group)}</td><td>'
                    f'{sum(r["comparison_eligible"] for r in group)}</td><td>'
                    f'{sum(r["joint_model_improvement"] for r in group)}</td></tr>')
    body.append('</table><p>See test.csv, paired_differences.csv, freeze_before_test.json and FINAL_RECEIPT.json.</p>')
    (Path(output)/'index.html').write_text('<!doctype html><meta charset="utf-8">'+''.join(body), encoding='utf8')


def main():
    parser = argparse.ArgumentParser(description='PC queue PPO; no device commands')
    parser.add_argument('--action', choices=['check', 'smoke', 'run', 'status'], default='check')
    parser.add_argument('--output')
    args = parser.parse_args()
    if args.action == 'check': print(json.dumps(check(), ensure_ascii=False, indent=2), flush=True)
    elif args.action == 'status':
        if not args.output: parser.error('--output is required')
        print((Path(args.output)/'progress.json').read_text(encoding='utf8'), flush=True)
    else:
        if not args.output: parser.error('--output is required; use a new directory')
        # PowerShell Ctrl+C and normal Python cancellation produce a partial receipt.
        signal.signal(signal.SIGINT, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
        run(args.output, smoke=args.action == 'smoke')


if __name__ == '__main__': main()
