"""Explicit three-environment desktop package smoke, no learning/device calls.

Default command only verifies the transported V1 source/session. The explicit
run-smoke command registers its own cap before running already-seen development
cases. It is a functional check, never independent performance confirmation.
"""
import argparse
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from tools import d1_joint_amount_cli as cli

x = cli.x
ROOT = x.ROOT
DEST = ROOT / 'output/desktop_package_smoke_20261011_v1'


def run_smoke():
    checked = cli.verify()
    if checked['status'] != 'PASS_V1_payload_and_shared_session_restore':
        raise ValueError('complete transported source and original checkpoints required')
    if DEST.exists():
        raise FileExistsError('smoke task already exists; never reset consumed starts')
    # Use a declared, already-used development input, not a fresh confirmation.
    case = x.read(x.LOCAL / 'inputs.json')['development'][0]
    if case['family'] != 'low' or case['context'] != 'mean':
        raise ValueError('fixed first low/mean development fixture changed')
    checkpoint_paths = {seed: x.LOCAL / 'checkpoints' / f'seed{seed}_ep64.pt' for seed in x.SEEDS}
    registration = dict(task='DESKTOP-PACKAGE-FUNCTIONAL-SMOKE-01',
        registered_utc=datetime.now(timezone.utc).isoformat(), native_cap=3, learning_cap=0,
        wall_seconds=60, save_reserve_seconds=10, case=case,
        case_scope='already-used development; not independent performance confirmation',
        policy=x.n.POLICY, schema=x.n.SCHEMA, objective=x.n.objective.OBJECTIVE,
        checkpoint_sha256={str(seed): x.sha(path) for seed, path in checkpoint_paths.items()},
        source_check=checked['source_receipt'],
        smoke_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        model_export_sha256=x.sha(x.h.MODEL), device_commands=0,
        automatic_adoption=False, new_hardware_tested=False)
    DEST.mkdir(parents=True)
    x.write(DEST / 'registration.json', registration)
    start = time.monotonic(); deadline = start + 50
    learners = cli.session.initial(checkpoint_paths, cli.original_dependencies())
    events, rows = [], []
    for seed in x.SEEDS:
        if time.monotonic() >= deadline:
            raise TimeoutError('smoke save reserve')
        event = dict(seed=seed, native_start=len(events) + 1, learning=False, status='started')
        events.append(event); x.write(DEST / 'events.json', events)
        try:
            frozen, initial, _ = x.h.load()
            profile = x.h.p.profile(frozen, case['context'])
            vectors = dict(cells={key: [dict(source_request_id='desktop_functional_' + case['context'],
                durations_ns=value) for _ in range(4)] for key, value in profile.items()})
            agent = x.actor(learners[seed].network)
            agent.execution_deadline = deadline
            with x.h.forecast_scope():
                result = x.h.prior.external.old.engine.simulate(
                    dict(protocol=x.h.p.VERSION, cells=x.h.p.profile(frozen)), vectors,
                    case['tickets'], policy=agent.policy,
                    settings=x.read(x.LOCAL / 'registration.json')['common_settings'],
                    seed=201, decision_provider=agent)
            x.old.x.previous.audit(result, case['tickets'])
            ledger = result['ledger']
            completed = sum(row['status'] == 'succeeded' for row in ledger)
            if len(ledger) != len(case['tickets']) or completed != len(ledger):
                raise ValueError('request preservation/completion failed')
            if any(not snapshot['mask'][snapshot['chosen']] or
                   (snapshot['mask'] & ~snapshot['physical_mask']).any() for snapshot in agent.snapshots):
                raise ValueError('illegal selected action')
            _, costs, end = x.h.account(result, initial['initial'], frozen)
            row = dict(seed=seed, planned=len(ledger), completed=completed,
                urgent_p95_ms=result['metrics']['urgent_p95_ms'],
                energy_j=costs['whole_120s_j'], peak_ap_c=max(costs['ap_path']),
                informative_decisions=sum(sum(snapshot['mask']) > 1 for snapshot in agent.snapshots),
                new_learning=0)
            rows.append(row); event['status'] = 'completed'
            x.write(DEST / f'result_{seed}.json', dict(row=row, ledger=ledger))
        except BaseException as error:
            event.update(status='failed', error=type(error).__name__)
            x.write(DEST / 'events.json', events)
            raise
        x.write(DEST / 'events.json', events)
    receipt = dict(status='PASS_isolated_same_PC_three_environment_smoke',
        new_native=len(events), new_learning=0, failed=sum(event['status'] == 'failed' for event in events),
        planned=sum(row['planned'] for row in rows), completed=sum(row['completed'] for row in rows),
        seconds=time.monotonic() - start, device_commands=0, new_hardware_tested=False,
        not_independent_confirmation=True, source_lock_verified=True, rows=rows)
    x.write(DEST / 'completion.json', receipt)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', nargs='?', choices=('verify', 'run-smoke'), default='verify')
    args = parser.parse_args()
    result = cli.verify() if args.command == 'verify' else run_smoke()
    print(json.dumps(x.serial(result), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
