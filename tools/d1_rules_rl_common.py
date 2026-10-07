"""Durable, capped accounting for the explicitly approved 2026-10-07 PC study."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import time
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / 'docs/results/request_ppo_01/rules_rl_amount_v1'
OUTPUT = ROOT / 'output/rules_rl_amount_20261007_v1'


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1048576), b''): h.update(block)
    return h.hexdigest()


def atomic(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    with tmp.open('w', encoding='utf8') as f:
        json.dump(value, f, ensure_ascii=False, allow_nan=False, indent=2)
        f.write('\n'); f.flush(); os.fsync(f.fileno())
    os.replace(tmp, path)


def append(path, value):
    with Path(path).open('a', encoding='utf8') as f:
        f.write(json.dumps(value, ensure_ascii=False, allow_nan=False) + '\n')
        f.flush(); os.fsync(f.fileno())


def read(path): return json.loads(Path(path).read_text(encoding='utf8'))
def utc(): return datetime.now(timezone.utc).isoformat()


class BudgetStop(RuntimeError): pass


class Budget:
    """Every simulator entry, including failed/replayed entries, is charged first.

    A torn ledger is a hard stop, not silent loss of consumed executions. Pending
    entries remain charged even if a process dies before publishing a result.
    Only one owner may use this ledger at a time (enforced by the study runners).
    """
    def __init__(self, folder=OUTPUT, fixture=False):
        self.folder = Path(folder); self.fixture = fixture
        self.plan = read(self.folder/'campaign.json')
        self.path = self.folder/'consumption.jsonl'
        self.counts = dict(recombination=0, rl=0)
        self.training = {}; self.optimizers = {}; self.pending = {}
        self.serial = 0
        if self.path.exists():
            for line in self.path.read_text(encoding='utf8').splitlines():
                entry = json.loads(line); self.serial = max(self.serial, entry['serial'])
                if entry['event'] == 'start':
                    self.counts[entry['category']] += 1; self.pending[entry['serial']] = entry
                    if entry.get('training_identity'):
                        k = entry['training_identity']; self.training[k] = self.training.get(k, 0)+1
                elif entry['event'] == 'finish': self.pending.pop(entry['started_serial'], None)
                elif entry['event'] == 'optimizer':
                    k = entry['identity']; self.optimizers[k] = self.optimizers.get(k, 0)+1
                elif entry['event'] == 'fixture_training_annotation':
                    k=entry['identity'];self.training[k]=self.training.get(k,0)+entry['episodes']

    def check(self, category=None, training_identity=None, reserve=0):
        deadline = datetime.fromisoformat(self.plan['deadline_utc']).timestamp()
        if time.time() >= deadline-reserve: raise BudgetStop('wall clock limit/reserved finalization time')
        if category and self.counts[category] >= self.plan['limits'][category]:
            raise BudgetStop(category+' environment limit')
        if training_identity and not training_identity.startswith('fixture'):
            if self.training.get(training_identity, 0) >= self.plan['limits']['episodes_per_learner']:
                raise BudgetStop('learner episode cap: '+training_identity)

    def event(self, **entry):
        self.serial += 1; entry.update(serial=self.serial, utc=utc())
        append(self.path, entry)
        return self.serial

    def execute(self, category, purpose, fn, training_identity=None, reserve=300, **meta):
        self.check(category, training_identity, reserve)
        number = self.event(event='start', category=category, purpose=purpose,
                            training_identity=training_identity, **meta)
        self.counts[category] += 1
        if training_identity: self.training[training_identity] = self.training.get(training_identity, 0)+1
        self.pending[number] = dict(category=category, purpose=purpose, **meta)
        try: result = fn()
        except BaseException as e:
            self.event(event='finish', started_serial=number, result='error', error=repr(e))
            self.pending.pop(number); self.publish(); raise
        self.event(event='finish', started_serial=number, result='completed')
        self.pending.pop(number)
        return result

    def optimized(self, identity, update, minibatches):
        self.event(event='optimizer', identity=identity, update=update, minibatches=minibatches)
        self.optimizers[identity] = self.optimizers.get(identity, 0)+1

    def fixture_annotation(self,identity,episodes,updates,provenance):
        self.event(event='fixture_training_annotation',identity=identity,episodes=episodes,provenance=provenance)
        self.training[identity]=self.training.get(identity,0)+episodes
        for update in range(1,updates+1):self.optimized(identity,update,None)

    def publish(self, **extra):
        atomic(self.folder/'consumption.json', dict(environment_runs=self.counts,
            training_episodes_including_replay=self.training, optimizer_updates=self.optimizers,
            unresolved_entries=self.pending, device_commands=0, updated_utc=utc(), **extra))


def initialize():
    """Register authorization and budgets before any environment is executed."""
    if OUTPUT.exists(): raise ValueError('existing study; inspect instead of initializing again')
    OUTPUT.mkdir(parents=True)
    # Conservative clock origin precedes this turn's initial read-only inspection.
    start = '2026-10-06T18:00:00+00:00'
    atomic(OUTPUT/'campaign.json', dict(id='RULES-RL-AMOUNT-20261007-V1',
        started_utc=start, clock_origin='conservative earlier boundary, includes startup inspection',
        deadline_utc='2026-10-07T10:00:00+00:00', wall_limit_seconds=57600,
        training_stop_reserve_s=5400, final_save_reserve_s=300,
        limits=dict(recombination=4000, rl=80000, episodes_per_learner=8192),
        fixture_and_recovery_included=True, device_commands=0, experiment_ready=False,
        base_head='9e1975bfd4cb96587e7cfb5b18b85f5409ff0b83',
        historical_fixture_consumption=dict(environment_runs=114, training_episodes=12,
            scope='prior completed work, preserved separately, not new execution')))
    source = Path('C:/Users/LG/.codex/attachments/e3f2674a-1737-4e5f-ad5a-24d6df350d08/Pasted text.txt')
    (OUTPUT/'user_authorization.txt').write_bytes(source.read_bytes())
    paths = []
    for name in ('output/queue_ppo_feasible_v2', 'output/queue_ppo_v2_evaluation_v1'):
        paths.extend(p for p in (ROOT/name).rglob('*') if p.is_file())
    paths.extend((ROOT/'tools').glob('d1_queue_ppo*.py'))
    paths.extend([ROOT/'docs/results/online_policy_study_01/overnight_sustained_run01'/name
                  for name in ('model.json', 'initial_inputs.json')])
    atomic(OUTPUT/'protected_sources.json', {p.relative_to(ROOT).as_posix():digest(p) for p in paths})
    Budget().publish(stage='registered_not_started')


def verify_protected(folder=OUTPUT):
    sources=read(Path(folder)/'protected_sources.json')
    changed=[name for name,sha in sources.items() if digest(ROOT/name)!=sha]
    if changed: raise ValueError('protected original changed: '+repr(changed))
    return len(sources)


if __name__ == '__main__': initialize()
