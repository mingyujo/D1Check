"""Eighteen request-level LSF/Band-LSF adaptations; completed comparators reused."""
import os
for key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[key] = '1'
import gc
import json
from pathlib import Path
import subprocess
import sys
import time
import traceback

H = Path(__file__).resolve().parent
A = H.parents[1]
R = A.parent
O = A / 'results/A24_LSF_BAND_20261020_01'
P = A / 'results/A24_QUEUE_PRESSURE_20261020_01'
sys.path.insert(0, str(H.parent))
from a24_logic_repair_20261019 import load_components
C = load_components()
from lsf_policy import Policy, VERSION, MODES
from a24_queue_pressure_20261020 import study as pressure
import drop_engine
from a24_bc_600_20261019 import study as old
from common_transfer import B, read, saved
sha, pin, new, stamp, verify = old.sha, old.pin, old.new, old.stamp, old.verify


def cases():
    return old.cases()+pressure.cases()

def public_and_contexts(case):
    return old.public_and_contexts(case) if case['condition']['rate_multiplier']==.4 else pressure.public_and_contexts(case)

def bankfile_for(case):
    folder=old.D if case['condition']['rate_multiplier']==.4 else pressure.H
    return folder/'banks'/(case['id']+'.BANK.json.gz')


def propose():
    assert not (H / 'PROPOSAL.json').exists() and not O.exists()
    parent = read(A / 'experiments/a24_queue_pressure_20261020/OPERATION.json')
    assert parent['authorized_total'] == 137741
    verify(parent['pins'])
    prior = read(P / 'RESULT.json')
    assert (prior['START'], prior['COMPLETE'], prior['FAIL']) == (16, 16, 0)
    paths = [R / p['path'] for p in parent['pins']]
    paths += [R / r['raw']['path'] for r in prior['rows']]
    paths += [P / 'RESULT.json', P / 'FINAL_HANDOFF_PROOF.json',
              A / 'experiments/a24_queue_pressure_20261020/OPERATION.json']
    paths += [p for p in H.rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    git = lambda *args:subprocess.check_output(['git', *args], cwd=R, text=True, encoding='utf-8').strip()
    new(H / 'PROPOSAL.json', dict(status='PREPARED_FOR_REQUESTED_LSF_BAND_COMPARISON', utc=stamp(),
        schema='A24_LSF_BAND_EVAL_V1', HEAD=git('rev-parse', 'HEAD'), branch=git('branch', '--show-current'),
        working_tree=git('status', '--short'), code_version=VERSION, planned_START=18,
        new_training=0, new_fit=0, new_device=0, new_NN_execution=0, old_results_rerun=0,
        budget=dict(previous_closed_total=137741, current_requested_EVAL=18, derived_total=137759, refund=0),
        evaluation_cases=[c['id'] for c in cases()], output_dir=O.relative_to(R).as_posix(),
        baseline_definition=dict(modes=MODES, public_only=True, full_Band_runtime=False, Band_commit='8600d4960ccb6f121221f6d252da8dbef2db160b', all_visible_queue=True, no_subgraph_partition=True, cpu_slots=3, gpu_slots=1, basic='min slack among free-route predictions', band='min slack including current worker release; skip busy best plan', drop_variant='predicted negative slack -> explicit DROP'),
        pins=[pin(p) for p in sorted(set(paths))]))


def register():
    auth = read(H / 'EXECUTION_AUTHORIZATION.json')
    assert auth['execution_authorized'] is True and auth['authorized_units'] == 18
    assert auth['derived_total'] == 137759 and auth['new_fit'] == 0
    assert isinstance(auth['user_message'], str) and len(auth['user_message']) > 1
    op = read(H / 'PROPOSAL.json');verify(op['pins'])
    assert not O.exists()
    op.update(status='AUTHORIZED_REGISTERED', authorization=pin(H / 'EXECUTION_AUTHORIZATION.json'),
              authorized_total=auth['derived_total'], registered_utc=stamp())
    new(H / 'OPERATION.json', op)


def run():
    import msvcrt
    import psutil
    op = read(H / 'OPERATION.json');verify(op['pins']);verify([op['authorization']])
    assert op['status'] == 'AUTHORIZED_REGISTERED' and op['authorized_total'] == 137759 and not O.exists()
    lock = (A / 'runtime/a24_local_worker.lock').open('r+b');locked = False
    deadline = time.monotonic()+3600; last_wait_notice = None
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
        wait_notice = (locked, len(processes), psutil.virtual_memory().available >= 1024**3,
                       __import__('shutil').disk_usage(R).free >= 8*1024**3)
        if wait_notice != last_wait_notice:
            print('RESOURCE_WAIT_STATUS mutex,python_count,memory_ok,disk_ok', wait_notice, flush=True)
            last_wait_notice = wait_notice
        assert time.monotonic() < deadline, 'Finite resource wait'
        time.sleep(5)
    rows, replayed, wait_replayed = [], 0, 0
    begin = time.monotonic();opsha = sha(H / 'OPERATION.json');active = [None]
    try:
        O.mkdir();new(O / 'START.json', dict(utc=stamp(), operation_sha256=opsha, HEAD=op['HEAD'], processes=processes))
        def receipt(event, label, **extra):
            r = dict(event=event, label=label, kind='EVAL', utc=stamp(), durable_START_consumed=True,
                     start_id=B.L.digest([opsha, label]), **extra)
            with (O / 'receipts.jsonl').open('a', encoding='utf-8') as f:
                f.write(json.dumps(r)+'\n');f.flush();os.fsync(f.fileno())
            active[0] = label if event == 'START' else None
            return r
        for case, mode in [(c,m) for c in cases() for m in MODES]:
            assert len(rows) < 18 and time.monotonic()-begin < 3600
            public, contexts, parent = public_and_contexts(case)
            bankfile = bankfile_for(case);bank = read(bankfile)
            physics = C.Physics(read(A / 'results/STATE_COST_IDENTIFICATION_20261017_01/MODEL.json'),
                B.Config(**parent['physics']), 'ORIGINAL', read(old.PORT / 'SHAPE.json'))
            model = B.BankModel(bank['jobs'], contexts)
            nominal = B.SavedNominal(public, [dict(nominal_vectors=bank['nominal_vectors'])])
            actor = Policy(nominal, physics, mode)
            label = 'ORIGINAL__LSF_BAND__'+case['id']+'__'+mode
            rec = receipt('START', label);episode = time.monotonic();last = [None]
            try:
                def guarded(s):
                    last[0] = s
                    if time.monotonic()-episode > 1200 or time.monotonic()-begin > 3600:
                        raise ValueError('Finite wall cap')
                    if len(actor.calls)+len(actor.wait_calls) > max(1024, 20*case['n']):raise ValueError('Finite policy call cap')
                    if __import__('shutil').disk_usage(R).free < 4*1024**3:raise ValueError('Disk guard')
                    return actor(s)
                engine = drop_engine if mode=='BAND_LSF_DROP' else C.engine
                result = engine.run(public, model, guarded, physics, case['common_potential_key'], rec)
                metrics = C.engine.metrics(result, case, physics)
                score = old.objective.outcome(result, case, physics)
                raw = O / (label+'.raw.json.gz')
                saved(raw, dict(result=result, calls=actor.calls, wait_calls=actor.wait_calls, case=case,
                    profile=dict(id='ORIGINAL', slots=3, beta=.25), policy_version=VERSION))
                replica = Policy(nominal, physics, mode)
                for w in actor.wait_calls:
                    assert replica(w['public_state']) == w['action']
                    assert replica.wait_calls[-1] == w
                    wait_replayed += 1
                replica = Policy(nominal, physics, mode)
                for dec, call in zip(result['decisions'], actor.calls):
                    assert replica(dec['public_state']) == dec['action'] == call['action']
                    assert replica.calls[-1] == call
                    replayed += 1
                assert len(result['decisions']) == len(actor.calls)
                row = dict(label=label, case=case['id'], condition=case['condition'], policy=mode,
                    kind='EVAL', status='COMPLETE', n=case['n'], metrics=metrics, score=score,
                    raw=pin(raw), bank=pin(bankfile), policy_version=VERSION, new_NN_execution=0)
                receipt('COMPLETE', label, raw_sha256=sha(raw));del result, replica
            except ValueError as e:
                if str(e) not in ('Decision cap', 'Integration cap', 'Finite wall cap', 'Finite policy call cap', 'Disk guard'):
                    raise
                raw = O / (label+'.FAILED.json.gz')
                saved(raw, dict(calls=actor.calls, case=case, last_public_state=last[0], error=str(e), partial_not_complete_trace=True))
                row = dict(label=label, case=case['id'], policy=mode, status='FAIL', failure=str(e),
                    metrics=None, score=None, raw=pin(raw), automatic_retry=False)
                receipt('FAIL', label, error=str(e), automatic_retry=False)
            new(O / (label+'.json'), row);rows.append(row)
            print('LSF_BAND_EVAL_TERMINAL', label, row['status'], flush=True)
            del actor, model, bank;gc.collect()
        verify(op['pins']);failed = sum(r['status'] == 'FAIL' for r in rows)
        new(O / 'REPLAY.json', dict(status='PASS', calls=replayed, wait_calls=wait_replayed, exact_LSF_Band_action_log_replay=True,
            new_environment=0, new_NN_execution=0))
        new(O / 'RESULT.json', dict(status='BATCH_COMPLETE', START=18, COMPLETE=18-failed, FAIL=failed,
            rows=rows, new_training=0, new_BC_fit=0, new_PPO=0, new_NN_execution=0,
            new_fit=0, new_device=0, elapsed_s=time.monotonic()-begin))
    except BaseException as e:
        if active[0] is not None:receipt('FAIL', active[0], error=str(e), automatic_retry=False)
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
