"""Two frozen-checkpoint evaluations of the idle WAIT guard; no training."""
import os
for key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[key] = '1'
import gc
from pathlib import Path
import subprocess
import sys
import time
import traceback
import json

H = Path(__file__).resolve().parent
A = H.parents[1]
R = A.parent
O = A / 'results/A24_IDLE_WAIT600_20261019_01'
P = A / 'results/A24_ATC_BC600_20261019_01'
G = A / 'experiments/a24_idle_wait_repair_20261019'
sys.path.insert(0, str(H.parent))
from a24_idle_wait_repair_20261019 import load_components, VERSION
C = load_components()
from a24_atc_bc_20261019.learner import Learner
from a24_bc_600_20261019 import study as old
from common_transfer import B, read, loadpt, pt, saved, np, equal
sha, pin, new, stamp, verify = old.sha, old.pin, old.new, old.stamp, old.verify


def propose():
    assert not (H / 'PROPOSAL.json').exists() and not O.exists()
    ancestor = read(A / 'experiments/a24_atc_bc_20261019/OPERATION.json')
    verify(ancestor['pins'])
    assert ancestor['approved_cap'] == 137715
    paths = [R / p['path'] for p in ancestor['pins']]
    proof = read(A / 'results/A24_IDLE_WAIT_REPAIR_20261019_01/VERIFICATION.json')
    repair = [p for p in proof['files'] if p['path'].startswith((
        'a24_simulator/experiments/a24_idle_wait_repair_20261019/',
        'a24_simulator/results/A24_IDLE_WAIT_REPAIR_20261019_01/'))]
    verify(repair)
    paths += [R / p['path'] for p in repair]
    paths += [A / 'results/A24_IDLE_WAIT_REPAIR_20261019_01/VERIFICATION.json']
    paths += [p for p in H.iterdir() if p.is_file() and p.suffix in ('.py', '.cjs', '.md')]
    parent = read(P / 'RESULT.json')
    assert parent['COMPLETE'] == 2 and parent['FAIL'] == 0
    paths += [R / r['raw']['path'] for r in parent['rows']]
    paths += [P / 'RESULT.json', P / 'BC.FINAL.pt.gz', P / 'FINAL_HANDOFF_PROOF.json',
              A / 'experiments/a24_atc_bc_20261019/OPERATION.json']
    git = lambda *args:subprocess.check_output(['git', *args], cwd=R, text=True, encoding='utf-8').strip()
    new(H / 'PROPOSAL.json', dict(status='PREPARED_FOR_REQUESTED_EVALUATION', utc=stamp(),
        schema='A24_IDLE_WAIT600_EVAL_V1', HEAD=git('rev-parse', 'HEAD'),
        branch=git('branch', '--show-current'), working_tree=git('status', '--short'),
        code_version=VERSION, planned_START=2, new_training=0, new_BC_fit=0, new_PPO=0,
        new_physical_fit=0, new_device=0, old_results_rerun=0,
        budget=dict(current=137715, existing_cap=137715, additional_units=2, requested_cap=137717, refund=0),
        checkpoint=pin(P / 'BC.FINAL.pt.gz'), evaluation_cases=[c['id'] for c in old.cases()],
        output_dir=O.relative_to(R).as_posix(), pins=[pin(p) for p in sorted(set(paths))]))


def register():
    approval = read(H / 'EXECUTION_AUTHORIZATION.json')
    assert approval['execution_authorized'] is True and approval['authorized_units'] == 2
    assert approval['derived_total'] == 137717 and approval['new_fit'] == 0
    assert isinstance(approval['user_message'], str) and len(approval['user_message']) > 1
    op = read(H / 'PROPOSAL.json');verify(op['pins'])
    assert not O.exists()
    op.update(status='AUTHORIZED_REGISTERED', authorization=pin(H / 'EXECUTION_AUTHORIZATION.json'),
              authorized_total=approval['derived_total'], registered_utc=stamp())
    new(H / 'OPERATION.json', op)


def run():
    import msvcrt
    import psutil
    op = read(H / 'OPERATION.json');verify(op['pins']);verify([op['authorization']])
    assert op['status'] == 'AUTHORIZED_REGISTERED' and op['authorized_total'] == 137717 and not O.exists()
    lock = (A / 'runtime/a24_local_worker.lock').open('r+b');locked = False
    deadline = time.monotonic() + 3600
    while True:
        if not locked:
            try:
                lock.seek(0);msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1);locked = True
            except OSError:
                pass
        processes = [p.info for p in psutil.process_iter(['pid', 'name'])
                     if (p.info['name'] or '').lower() in ('python.exe', 'python3.exe')]
        if (locked and len(processes) <= 3 and psutil.virtual_memory().available >= 1024**3
                and __import__('shutil').disk_usage(R).free >= 8*1024**3):
            break
        assert time.monotonic() < deadline, 'Finite resource wait'
        time.sleep(5)
    rows, replayed = [], 0
    begin = time.monotonic();opsha = sha(H / 'OPERATION.json');active_start = [None]
    try:
        O.mkdir();new(O / 'START.json', dict(utc=stamp(), operation_sha256=opsha, HEAD=op['HEAD'], processes=processes))
        def receipt(event, label, **extra):
            r = dict(event=event, label=label, kind='EVAL', utc=stamp(), durable_START_consumed=True,
                     start_id=B.L.digest([opsha, label]), **extra)
            with (O / 'receipts.jsonl').open('a', encoding='utf-8') as f:
                f.write(json.dumps(r)+'\n');f.flush();os.fsync(f.fileno())
            active_start[0] = label if event == 'START' else None
            return r
        snap = loadpt(R / op['checkpoint']['path'])
        for case in old.cases():
            assert len(rows) < 2 and time.monotonic()-begin < 3600
            public, contexts, parent = old.public_and_contexts(case)
            bankfile = old.D / 'banks' / (case['id']+'.BANK.json.gz');bank = read(bankfile)
            physics = C.Physics(read(A / 'results/STATE_COST_IDENTIFICATION_20261017_01/MODEL.json'),
                B.Config(**parent['physics']), 'ORIGINAL', read(old.PORT / 'SHAPE.json'))
            model = B.BankModel(bank['jobs'], contexts)
            nominal = B.SavedNominal(public, [dict(nominal_vectors=bank['nominal_vectors'])])
            learner = Learner(state=snap);before = learner.snapshot()
            actor = C.Policy(nominal, physics, case, 'BC', learner, False)
            label = 'ORIGINAL__IDLE_WAIT600__'+case['id']+'__IDLE_BC'
            rec = receipt('START', label);episode = time.monotonic();last = [None]
            try:
                def guarded(s):
                    last[0] = s
                    if time.monotonic()-episode > 1200 or time.monotonic()-begin > 3600:
                        raise ValueError('Finite wall cap')
                    if len(actor.calls) > max(1024, 20*case['n']):raise ValueError('Finite policy call cap')
                    if __import__('shutil').disk_usage(R).free < 4*1024**3:raise ValueError('Disk guard')
                    return actor(s)
                result = C.engine.run(public, model, guarded, physics, case['common_potential_key'], rec)
                metrics = C.engine.metrics(result, case, physics)
                score = old.objective.outcome(result, case, physics)
                raw = O / (label+'.raw.json.gz')
                saved(raw, dict(result=result, calls=actor.calls, case=case,
                    profile=dict(id='ORIGINAL', slots=3, beta=.25), policy_version=VERSION))
                pt(O / (label+'.FRAMES.pt.gz'), dict(frames=actor.frames,
                    network_sha256=snap['network_sha256'], collect=False, policy_version=VERSION))
                replica = Learner(state=before)
                for f in actor.frames:
                    i, a = replica.choose({k:f[k] for k in ('x', 'mask', 'scores')}, False)
                    assert i == f['index'] and a['old_logp'] == f['old_logp'] and np.array_equal(a['value'], f['value'])
                    replayed += 1
                equal(learner.snapshot(), before);equal(replica.snapshot(), before)
                row = dict(label=label, case=case['id'], condition=case['condition'], policy='IDLE_BC',
                    kind='EVAL', status='COMPLETE', n=case['n'], metrics=metrics, score=score,
                    raw=pin(raw), bank=pin(bankfile), network_sha256=snap['network_sha256'], policy_version=VERSION)
                receipt('COMPLETE', label, raw_sha256=sha(raw));del result, replica
            except ValueError as e:
                if str(e) not in ('Decision cap', 'Integration cap', 'Finite wall cap', 'Finite policy call cap', 'Disk guard'):
                    raise
                raw = O / (label+'.FAILED.json.gz')
                saved(raw, dict(calls=actor.calls, case=case, last_public_state=last[0], error=str(e), partial_not_complete_trace=True))
                row = dict(label=label, case=case['id'], policy='IDLE_BC', status='FAIL', failure=str(e),
                    metrics=None, score=None, raw=pin(raw), automatic_retry=False)
                receipt('FAIL', label, error=str(e), automatic_retry=False)
            new(O / (label+'.json'), row);rows.append(row)
            print('EVAL_TERMINAL', label, row['status'], flush=True)
            del actor, learner, model, bank;gc.collect()
        verify(op['pins'])
        failed = sum(r['status'] == 'FAIL' for r in rows)
        new(O / 'REPLAY.json', dict(status='PASS', frames=replayed, collect=False,
            whole_checkpoint_two_Adam_and_all_RNG_unchanged=True, new_environment=0))
        new(O / 'RESULT.json', dict(status='BATCH_COMPLETE', START=2, COMPLETE=2-failed, FAIL=failed,
            rows=rows, checkpoint=op['checkpoint'], new_training=0, new_BC_fit=0, new_PPO=0,
            new_fit=0, new_device=0, elapsed_s=time.monotonic()-begin))
    except BaseException as e:
        if active_start[0] is not None:receipt('FAIL', active_start[0], error=str(e), automatic_retry=False)
        if O.exists():new(O / 'FAILURE.json', dict(utc=stamp(), error=str(e), traceback=traceback.format_exc(), automatic_retry=False))
        raise
    finally:
        if locked:lock.seek(0);msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
        lock.close()


if __name__ == '__main__':
    if '--propose' in sys.argv:propose()
    elif '--register' in sys.argv:register()
    elif '--run' in sys.argv:run()
    else:print('Explicit --propose/--register/--run required; no automatic work')
