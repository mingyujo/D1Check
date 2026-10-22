"""Read-only state replay of the idle WAIT fix; no trajectory or fit is run."""
import os
for key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[key] = '1'
import collections
import datetime
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys

H = Path(__file__).resolve().parent
R = H.parents[2]
A = R / 'a24_simulator'
O = A / 'results/A24_IDLE_WAIT_REPAIR_20261019_01'
P = A / 'results/A24_ATC_BC600_20261019_01'
sys.path.insert(0, str(H.parent))
from a24_idle_wait_repair_20261019 import load_components, VERSION, NETWORK_VERSION
C = load_components()
from a24_idle_wait_repair_20261019.policy import Policy
from a24_atc_bc_20261019.learner import Learner
from common_transfer import np, torch, loadpt, equal


def read(p):
    return json.loads(gzip.decompress(p.read_bytes()) if p.suffix == '.gz' else p.read_bytes())


def pin(p):
    return dict(path=p.relative_to(R).as_posix(), bytes=p.stat().st_size,
                sha256=hashlib.sha256(p.read_bytes()).hexdigest())


def save(name, value):
    with (O / name).open('x', encoding='utf-8') as f:
        json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)


def verify(pins):
    for p in pins:
        assert pin(R / p['path']) == p, p['path']


def main():
    assert not O.exists(), 'Saved review is exclusive; never overwrite previous evidence'
    op = read(A / 'experiments/a24_atc_bc_20261019/OPERATION.json')
    verify(op['pins'])
    parent_proof = read(P / 'FINAL_HANDOFF_PROOF.json')
    # Root progress documents may advance. Frozen experiment/result artifacts may not.
    frozen = [x for x in parent_proof['files'] if x['path'].startswith((
        'a24_simulator/experiments/a24_atc_bc_20261019/',
        'a24_simulator/results/A24_ATC_BC600_20261019_01/'))]
    verify(frozen)
    checkpoint = loadpt(P / 'BC.FINAL.pt.gz')
    learner = Learner(state=checkpoint)
    before = learner.snapshot()
    global_rng = torch.random.get_rng_state().clone()
    counts = collections.Counter()
    records, late_replays, sources = [], [], [pin(P / 'BC.FINAL.pt.gz'), pin(P / 'FINAL_HANDOFF_PROOF.json')]
    for row in read(P / 'RESULT.json')['rows']:
        rawfile = R / row['raw']['path']
        assert pin(rawfile) == row['raw']
        sources.append(pin(rawfile))
        raw = read(rawfile)
        late = [q for q in raw['result']['requests'] if q['response_ns'] is not None and q['response_ns'] > q['deadline_ns']]
        for i, (call, dec) in enumerate(zip(raw['calls'], raw['result']['decisions'])):
            s = dec['public_state']
            assert s['now_ns'] == call['time_ns']
            bank = dict(x=np.asarray(call['x'], np.float32), mask=np.asarray(call['mask'], bool),
                scores=np.asarray(call['forecast_scores'], np.float32), forecasts=call['forecasts'],
                version=NETWORK_VERSION)
            old_index, _ = learner.choose(bank, False)
            assert old_index == call['chosen']
            guarded = Policy.guard_bank(s, bank, call['actions'])
            new_index, _ = learner.choose(guarded, False)
            assert guarded['mask'][new_index] and np.all(guarded['mask'] <= bank['mask'])
            active = bool(s['owners'])
            info = guarded['idle_wait_guard']
            changed = old_index != new_index
            counts['frames'] += 1
            counts['active_frames' if active else 'idle_frames'] += 1
            counts['filtered_frames'] += int(info['applied'])
            counts['removed_WAIT_actions'] += len(info['removed'])
            counts['NN_choice_changed'] += int(changed)
            counts['old_choice_removed'] += int(not guarded['mask'][old_index])
            counts['context_only_choice_changed'] += int(changed and guarded['mask'][old_index])
            if active:
                assert np.array_equal(bank['mask'], guarded['mask']) and not changed
            if not info['applied']:
                assert np.array_equal(bank['mask'], guarded['mask']) and not changed
            elif changed and guarded['mask'][old_index]:
                assert call['actions'][new_index]['kind'] != 'WAIT' or guarded['mask'][new_index]
            if not active and call['action']['kind'] == 'WAIT':
                counts['old_idle_WAIT_choices'] += 1
                counts['old_idle_WAIT_preserved'] += int(guarded['mask'][old_index])
                best = min(range(len(call['actions'])), key=lambda k:(bank['scores'][k], k))
                counts['old_idle_WAIT_while_saved_teacher_dispatch'] += int(call['actions'][best]['kind'] == 'DISPATCH')
            record = dict(case=row['case'], decision_index=i, time_ns=call['time_ns'],
                old_chosen=old_index, new_chosen=new_index, mask=guarded['mask'].tolist(),
                guard=info)
            records.append(record)
            for q in late:
                if (not active and q['queue_entry_ns'] <= s['now_ns'] < q['dispatch_ns']
                        and call['action']['kind'] == 'WAIT'):
                    # Exercise the actual policy call and logging, using the exact saved encoder output.
                    policy = Policy(None, None, {}, 'BC', learner, False)
                    policy.encode = lambda _s:(guarded, call['actions'])
                    chosen = policy(s)
                    assert chosen == call['actions'][new_index] and chosen['kind'] == 'DISPATCH'
                    assert policy.calls[-1]['post_NN_override'] is False
                    assert not guarded['mask'][old_index]
                    with torch.no_grad():
                        logits, _ = learner.net(torch.from_numpy(bank['x'])[None], torch.from_numpy(bank['mask'])[None])
                        probabilities = (logits / learner.temperature).softmax(-1)[0].tolist()
                    late_replays.append(dict(**record, old_action=call['action'], new_action=chosen,
                        saved_scores=bank['scores'][:len(call['actions'])].tolist(),
                        NN_probabilities=probabilities[:len(call['actions'])],
                        old_action_nominal_cost=call['forecasts'][old_index]['cost']))
    assert counts['frames'] == 3781 and len(late_replays) == 9
    assert all(r['new_action'] == dict(kind='DISPATCH', request_id='user-00003', route='CPU') for r in late_replays)
    equal(before, learner.snapshot())
    assert torch.equal(global_rng, torch.random.get_rng_state())
    verify(op['pins']);verify(frozen)
    git = lambda *args:subprocess.check_output(['git', *args], cwd=R, text=True, encoding='utf-8').strip()
    source = [pin(p) for p in H.glob('*.py')]
    O.mkdir()
    record = dict(status='PASS', utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        version=VERSION, network_version=NETWORK_VERSION, HEAD=git('rev-parse', 'HEAD'),
        working_tree=git('status', '--short'), counts=dict(counts), late_request_states=late_replays,
        original_registered_pins_verified=len(op['pins']), original_frozen_artifacts_verified=len(frozen),
        whole_checkpoint_two_Adam_all_RNG_unchanged=True, sources=sources, repair_sources=source,
        new_environment=0, new_training=0, new_fit=0, new_device=0,
        budget_conservative_total=137715, budget_approved_cap=137715,
        diagnosis=dict(direct='BC argmax selected WAIT despite the already-recorded teacher cost favoring immediate CPU dispatch.',
                       structural='The prior mask enforced only physical legality; forecast cost was an unconstrained NN feature.',
                       training='TRAIN compatible accuracy 80.758%, WAIT accuracy 60.544%; fixed teacher-state data do not cover every state reached by repeated mistaken waits.',
                       causal_limit='Training-distribution explanations are plausible, not isolated causal proof.'),
        not_measured=['New scheduling trajectories', 'Post-fix energy/AP/P95/service', 'ATC-only effect'])
    save('SAVED_STATE_REVIEW.json', record)
    with gzip.open(O / 'DECISION_REPLAY.json.gz', 'xt', encoding='utf-8') as f:
        json.dump(records, f, ensure_ascii=False, allow_nan=False)
    print('IDLE_WAIT_SAVED_STATE_PASS', json.dumps(dict(counts), sort_keys=True), 'late states', len(late_replays))


if __name__ == '__main__':
    main()
