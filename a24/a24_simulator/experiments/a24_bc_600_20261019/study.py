"""Two new BC evaluations only; completed comparators are read, never rerun."""
import os
for key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[key] = '1'
import copy
import datetime
import gc
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
import traceback

H = Path(__file__).resolve().parent
A = H.parents[1]
R = A.parent
P = A / 'results/A24_DURATION_040_20261019_01'
S = A / 'results/A24_S26_METHOD_20261019_01'
D = A / 'experiments/a24_duration_040_20261019'
O = A / 'results/A24_BC_600_20261019_01'
sys.path.insert(0, str(A / 'experiments/public_transfer_20261018'))
from common_transfer import B, read, saved, loadpt, pt, np, torch, equal
from transfer_learner import Learner, digest
sys.path[:0] = [str(A / 'experiments' / d) for d in (
    'a24_s26_method_20261019', 'a24_candidate_repair_20261018', 'a24_parallel_20261018')]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


PORT = A / 'experiments/a24_s26_method_20261019'
Physics = module('_bc600_frozen_physics', PORT / 'physics.py').Physics
Policy = module('_bc600_frozen_policy', PORT / 'policy.py').Policy
engine = module('_bc600_frozen_engine', PORT / 'engine.py')
objective = module('_bc600_objective', A / 'experiments/a24_cem_identification_20261019/objective.py')


def sha(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda: f.read(1024*1024), b''):
            h.update(b)
    return h.hexdigest()


def stamp():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def new(p, value):
    with Path(p).open('x', encoding='utf-8') as f:
        json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)


def relocate(p):
    suffix = str(p).replace('\\', '/').split('/a24_simulator/', 1)[1]
    return A / suffix


def pin(p):
    return dict(path=Path(p).relative_to(R).as_posix(), bytes=Path(p).stat().st_size, sha256=sha(p))


def verify(pins):
    for p in pins:
        f = R / p['path']
        assert f.stat().st_size == p['bytes'] and sha(f) == p['sha256'], p['path']


def cases():
    return [c for c in read(D / 'INPUTS.json')['cases'] if c['condition']['supply_s'] == 600]


def review_bc():
    snap = loadpt(S / 'ORIGINAL.BC.FINAL.pt.gz')
    assert (snap['episodes'], snap['updates'], snap['steps'], snap['bc_steps']) == (0, 0, 0, 384)
    assert not snap['pending'] and all(torch.isfinite(t).all() for t in snap['network'].values())
    frames = loadpt(S / 'ORIGINAL.BC.FRAMES.pt.gz')
    trace = loadpt(S / 'ORIGINAL.BC.TRACE.pt.gz')
    assert len(frames) == trace['frames'] == 1320 and trace['teacher_uses_future'] is False
    groups = {g: sum(f['group'] == g for f in frames) for g in trace['groups']}
    assert groups == trace['groups']
    for i, f in enumerate(frames):
        assert f['teacher_mask'][f['index']] and f['mask'][f['index']]
        assert int(np.argmin(np.where(f['mask'], f['scores'], np.inf))) == f['index']
        assert abs(float(trace['group_weights'][i]) - len(frames)/(len(groups)*groups[f['group']])) < 1e-6
    learner = Learner(state=snap)
    x = torch.from_numpy(np.stack([f['x'] for f in frames]))
    mask = torch.from_numpy(np.stack([f['mask'] for f in frames]))
    target = torch.from_numpy(np.stack([f['teacher_mask'] for f in frames]))
    with torch.no_grad():
        chosen = torch.cat([learner.net(x[i:i+128], mask[i:i+128])[0].argmax(-1)
                            for i in range(0, len(x), 128)])
    acc = float(target.gather(1, chosen[:, None]).float().mean())
    assert abs(acc - trace['logs'][-1]['compatible_accuracy']) < 1e-7
    equal(learner.snapshot(), snap)
    first = sorted(S.glob('ORIGINAL__EP1__*__PPO.BEFORE.pt.gz'))
    assert len(first) == 1
    equal(loadpt(first[0]), snap)
    design = read(PORT / 'INPUTS.json')
    assert not ({c['id'] for c in design['training']} & {c['id'] for c in design['evaluation']})
    demo_times = {f['time_ns'] for f in frames}
    assert demo_times and all(t >= 35e9 for t in demo_times)
    return dict(status='PASS', frames=len(frames), epochs=len(trace['logs']),
                groups=groups, compatible_accuracy=acc, per_group=trace['logs'][-1]['per_route'],
                final_loss=trace['logs'][-1]['loss'], no_new_training=True,
                BC_is_exact_PPO_EP1_initialization=True,
                TRAIN_EVAL_case_ids_disjoint=True, checkpoint=pin(S / 'ORIGINAL.BC.FINAL.pt.gz'),
                network_sha256=snap['network_sha256'], source_files=[pin(first[0]),
                    pin(S / 'ORIGINAL.BC.FRAMES.pt.gz'), pin(S / 'ORIGINAL.BC.TRACE.pt.gz')])


def register():
    assert not (H / 'OPERATION.json').exists() and not O.exists()
    prior = read(D / 'BUDGET_RESERVATION.json')
    assert prior['known_conservative_after'] + 2 == prior['shared_cap'] == 137712
    ancestor = read(D / 'OPERATION.json')
    paths = []
    for p in ancestor['pins']:
        local = relocate(p['path'])
        assert local.stat().st_size == p['bytes'] and sha(local) == p['sha256']
        paths.append(local)
    review = review_bc()
    new(H / 'BC_REVIEW.json', review)
    for name in ('ORIGINAL.BC.FINAL.pt.gz', 'ORIGINAL.BC.FRAMES.pt.gz',
                 'ORIGINAL.BC.TRACE.pt.gz', 'ORIGINAL.BC_EXACT.json'):
        paths.append(S / name)
    paths += [R / p['path'] for p in review['source_files']]
    paths += [D / 'BUDGET_RESERVATION.json', D / 'OPERATION.json', P / 'RESULT.json']
    for c in cases():
        paths += [P / (c['id'] + '.PUBLIC.json'), D / 'banks' / (c['id'] + '.BANK.json.gz')]
        for policy in ('FIFO_CPU', 'EDF_CPU', 'OLD_PPO'):
            paths.append(P / ('ORIGINAL__DURATION__' + c['id'] + '__' + policy + '.raw.json.gz'))
    paths += list(H.glob('*.py')) + list(H.glob('*.cjs')) + list(H.glob('*.md')) + [H / 'BC_REVIEW.json']
    git = lambda *args: subprocess.check_output(['git', *args], cwd=R, text=True, encoding='utf-8').strip()
    new(H / 'OPERATION.json', dict(schema='A24_BC600_V1', utc=stamp(), HEAD=git('rev-parse', 'HEAD'),
        working_tree=git('status', '--short'), output_dir=O.relative_to(R).as_posix(),
        planned_START=2, checkpoint=review['checkpoint'], cases=[c['id'] for c in cases()],
        comparator_policies=['FIFO_CPU', 'EDF_CPU', 'OLD_PPO'],
        code_version='FROZEN_DURATION_S26_METHOD_ORIGINAL', logic_repair_applied=False,
        budget=dict(before=137710, new_reservation=2, after=137712, cap=137712,
                    old_unused_refund=0, fresh_global_host_census=False),
        preregistration='LOCAL_SHA_BEFORE_START_NOT_REMOTE_PUBLICATION',
        pins=[pin(p) for p in sorted(set(paths))], new_training=0, new_fit=0, new_device=0))
    print('REGISTERED_BC600', len(paths), 'pins; new environments 0', flush=True)


def public_and_contexts(case):
    parent = read(A / 'experiments/a24_parallel_20261018/OPERATION.json')
    parent['registration']['path'] = str(relocate(parent['registration']['path']))
    reg = B.registration(parent)
    catalog = read(B.L.pin(reg['catalog_pin']))
    design = read(D / 'INPUTS.json')
    base = design['base_cases'][case['condition']['pattern_index']]
    proto, contexts = B.public_input(base, catalog)
    public = read(P / (case['id'] + '.PUBLIC.json'))['public']
    lookup = {q['request_id']: q for q in public['requests']}
    mapped = {q['request_id']: contexts[proto['requests'][i % len(proto['requests'])]['request_id']]
              for i, q in enumerate(public['requests'])}
    for context in mapped.values():
        context['_requests_by_id'] = lookup
    return public, mapped, parent


def run():
    import msvcrt
    import psutil
    op = read(H / 'OPERATION.json')
    verify(op['pins'])
    assert '--registered' in sys.argv and not O.exists() and len(cases()) == 2
    lock = (A / 'runtime/a24_local_worker.lock').open('r+b')
    locked, deadline = False, time.monotonic() + 3600
    while True:
        if not locked:
            try:
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
                locked = True
            except OSError:
                pass
        processes = [p.info for p in psutil.process_iter(['pid', 'name'])
                     if (p.info['name'] or '').lower() in ('python.exe', 'python3.exe')]
        if locked and len(processes) <= 3 and psutil.virtual_memory().available >= 1024**3 and shutil.disk_usage(R).free >= 8*1024**3:
            break
        assert time.monotonic() < deadline, 'Finite resource wait'
        time.sleep(5)
    start, rows, count, replayed = time.monotonic(), [], 0, 0
    try:
        snap = loadpt(R / op['checkpoint']['path'])
        power = read(A / 'results/STATE_COST_IDENTIFICATION_20261017_01/MODEL.json')
        shape = read(PORT / 'SHAPE.json')
        opsha = sha(H / 'OPERATION.json')
        O.mkdir()
        new(O / 'START.json', dict(utc=stamp(), pid=os.getpid(), operation_sha256=opsha,
                                  HEAD=op['HEAD'], working_tree=op['working_tree'], processes=processes))
        def receipt(value):
            with (O / 'receipts.jsonl').open('a', encoding='utf-8') as f:
                f.write(json.dumps(value) + '\n')
                f.flush()
                os.fsync(f.fileno())
        for case in cases():
            assert count < 2 and time.monotonic()-start < 3600 and shutil.disk_usage(R).free >= 4*1024**3
            public, contexts, parent = public_and_contexts(case)
            bankfile = D / 'banks' / (case['id'] + '.BANK.json.gz')
            bank = read(bankfile)
            model = B.BankModel(bank['jobs'], contexts)
            nominal = B.SavedNominal(public, [dict(nominal_vectors=bank['nominal_vectors'])])
            physics = Physics(power, B.Config(**parent['physics']), 'ORIGINAL', shape)
            learner = Learner(state=snap)
            actor = Policy(nominal, physics, case, 'BC', learner, False)
            before = learner.snapshot()
            label = 'ORIGINAL__BC600__' + case['id'] + '__BC'
            rec = dict(event='START', label=label, kind='EVAL', utc=stamp(), durable_START_consumed=True,
                       start_id=hashlib.sha256((opsha+label).encode()).hexdigest())
            receipt(rec)
            count += 1
            episode = time.monotonic()
            last = [None]
            print('START_BC600', count, label, 'n', case['n'], flush=True)
            try:
                def guarded(s):
                    last[0] = s
                    if time.monotonic()-episode > 1200 or time.monotonic()-start > 3600:
                        raise ValueError('Finite wall cap')
                    if len(actor.calls) > max(1024, 20*case['n']):
                        raise ValueError('Finite policy call cap')
                    return actor(s)
                result = engine.run(public, model, guarded, physics, case['common_potential_key'], rec)
                metrics = engine.metrics(result, case, physics)
                score = objective.outcome(result, case, physics)
                raw = O / (label + '.raw.json.gz')
                saved(raw, dict(result=result, calls=actor.calls, case=case,
                               profile=dict(id='ORIGINAL', slots=3, beta=.25)))
                pt(O / (label + '.FRAMES.pt.gz'), dict(frames=actor.frames,
                    network_sha256=before['network_sha256'], collect=False))
                replica = Learner(state=before)
                for f in actor.frames:
                    idx, again = replica.choose({k:f[k] for k in ('x','mask','scores')}, False)
                    assert idx == f['index'] and again['old_logp'] == f['old_logp'] and np.array_equal(again['value'], f['value'])
                    replayed += 1
                equal(learner.snapshot(), before)
                equal(replica.snapshot(), before)
                row = dict(label=label, case=case['id'], condition=case['condition'], policy='BC',
                           kind='EVAL', status='COMPLETE', profile=dict(id='ORIGINAL', slots=3, beta=.25),
                           n=case['n'], metrics=metrics, score=score, raw=pin(raw), bank=pin(bankfile),
                           network_sha256=before['network_sha256'], checkpoint=op['checkpoint'])
                receipt({**rec, 'event':'COMPLETE', 'utc':stamp(), 'raw_sha256':sha(raw)})
                print('COMPLETE_BC600', count, metrics['on_time'], metrics['urgent_on_time'],
                      'elapsed', round(time.monotonic()-start, 1), flush=True)
                del result, replica
            except ValueError as e:
                if str(e) not in ('Decision cap','Integration cap','Finite wall cap','Finite policy call cap'):
                    receipt({**rec, 'event':'FAIL', 'utc':stamp(), 'error':str(e), 'automatic_retry':False})
                    raise
                raw = O / (label + '.FAILED.json.gz')
                saved(raw, dict(calls=actor.calls, case=case, last_public_state=last[0],
                               error=str(e), partial_not_complete_trace=True))
                row = dict(label=label, case=case['id'], policy='BC', status='FAIL', failure=str(e),
                           metrics=None, score=None, raw=pin(raw), automatic_retry=False)
                receipt({**rec, 'event':'FAIL', 'utc':stamp(), 'error':str(e), 'automatic_retry':False})
            new(O / (label + '.json'), row)
            rows.append(row)
            del actor, learner, bank, model
            gc.collect()
        verify(op['pins'])
        failed = sum(r['status'] == 'FAIL' for r in rows)
        new(O / 'REPLAY.json', dict(status='PASS', frames=replayed, collect=False,
            whole_checkpoint_two_Adam_and_all_RNG_unchanged=True, new_training=0))
        new(O / 'RESULT.json', dict(status='BATCH_COMPLETE', START=count, COMPLETE=count-failed,
            FAIL=failed, rows=rows, elapsed_s=time.monotonic()-start, new_training=0, new_fit=0, new_device=0))
        print('BC600_ALL_COMPLETE', count, failed, flush=True)
    except BaseException as e:
        if O.exists():
            new(O / 'FAILURE.json', dict(utc=stamp(), error=str(e), traceback=traceback.format_exc(), automatic_retry=False))
        raise
    finally:
        if locked:
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
        lock.close()


if __name__ == '__main__':
    if '--register' in sys.argv:
        register()
    elif '--run' in sys.argv:
        run()
    else:
        # Import and input binding check only: no durable START, no engine.run.
        for case in cases():
            public, contexts, _ = public_and_contexts(case)
            assert len(public['requests']) == len(contexts) == case['n']
        print('PREFLIGHT_BINDINGS_PASS', json.dumps(review_bc(), ensure_ascii=False))
