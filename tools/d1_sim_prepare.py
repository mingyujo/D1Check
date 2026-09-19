"""Preparation contract only. This module cannot dispatch or simulate a request."""
import argparse
import hashlib
import json
import math
import re
import uuid
from pathlib import Path
from typing import Protocol

POLICIES = {
    '4.4/B0': 'task-fixed backend; FIFO; serial',
    '4.4/B1': 'same task-fixed backend; urgent/EDF with common aging; serial',
    '4.4/B2': 'development-selected legal static mapping and concurrency; common thermal pacing',
    '4.4/B3': 'common priority/aging; solo service plus preparation earliest-finish; legal concurrency',
    '4.4/P': 'common priority/aging; measured interference plus preparation; compare start versus wait',
}
REQUIRED_EVIDENCE = ('task_adapters', 'quality', 'solo_service', 'backend_transition',
                     'concurrency', 'thermal_memory', 'independent_holdout', 'evaluation_freeze')
STATES = ('passed', 'failed', 'unsupported', 'unverified')


class SchedulingPolicy(Protocol):
    """Future non-preemptive implementation returns request/backend assignments or bounded wait.

    Snapshot carries now_ns, queue, in-flight identities, capability and profile hashes.
    Decision carries starts (at most two), wait_until_ns and reason. All policies share
    admission, expiry, aging, CPU worker budget, memory and thermal constraints.
    No implementation or actual scheduling is provided by this preparation module.
    """
    def decide(self, snapshot: dict) -> dict: ...


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()


def keys(value, expected):
    if not isinstance(value, dict) or set(value) != set(expected):
        raise ValueError(f'expected exact fields: {sorted(expected)}')


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch('[a-zA-Z0-9][a-zA-Z0-9_.-]{0,99}', value):
        raise ValueError('invalid identifier')


def digest(value):
    if not isinstance(value, str) or not re.fullmatch('[a-f0-9]{64}', value):
        raise ValueError('invalid SHA-256')


def derive_seed(master, partition, purpose, block):
    if type(master) is not int or not 0 <= master < 2**64 or partition not in ('calibration', 'development', 'evaluation'):
        raise ValueError('invalid seed namespace')
    identifier(purpose)
    if type(block) is not int or block < 0:
        raise ValueError('invalid block')
    # Fully specified across Python versions; no dependency on process hash/random state.
    material = canonical(['d1-seed-sha256-v1', master, partition, purpose, block])
    return int.from_bytes(hashlib.sha256(material).digest()[:8], 'big')


def validate_input(value, evidence_root):
    keys(value, ('protocol', 'schema_version', 'plan_revision', 'device_id', 'tasks', 'capabilities',
                 'workloads', 'seed', 'deadline', 'constraints', 'policies', 'evidence'))
    if (value['protocol'], value['schema_version'], value['plan_revision']) != ('sim-input-preparation-v1', 1, '4.4'):
        raise ValueError('unsupported preparation contract')
    identifier(value['device_id'])
    tasks = value['tasks']
    if not isinstance(tasks, list) or len(tasks) < 2:
        raise ValueError('multiple actual task classes required')
    task_ids = []
    for task in tasks:
        keys(task, ('task_id', 'model_id', 'model_sha256', 'preprocessing_id', 'adapter_status'))
        for key in ('task_id', 'model_id', 'preprocessing_id'):
            identifier(task[key])
        digest(task['model_sha256'])
        if task['adapter_status'] not in ('pending', 'verified'):
            raise ValueError('invalid adapter status')
        task_ids.append(task['task_id'])
    if len(set(task_ids)) != len(task_ids):
        raise ValueError('duplicate task identity')
    matrix = {}
    for cell in value['capabilities']:
        keys(cell, ('task_id', 'backend', 'status', 'evidence_sha256'))
        key = (cell['task_id'], cell['backend'])
        if key in matrix or key[0] not in task_ids or key[1] not in ('CPU', 'GPU') or cell['status'] not in STATES:
            raise ValueError('invalid/duplicate capability cell')
        if cell['status'] != 'unverified' or cell['evidence_sha256'] is not None:
            digest(cell['evidence_sha256'])
        matrix[key] = cell
    if set(matrix) != {(t, b) for t in task_ids for b in ('CPU', 'GPU')}:
        raise ValueError('explicit complete capability matrix required')
    names = set()
    for workload in value['workloads']:
        keys(workload, ('workload_id', 'arrival_source', 'mix'))
        identifier(workload['workload_id'])
        if workload['workload_id'] in names or workload['arrival_source'] != 'synthetic_assumption':
            raise ValueError('duplicate workload or unsupported arrival provenance')
        names.add(workload['workload_id'])
        seen, total = set(), 0.0
        for part in workload['mix']:
            keys(part, ('task_id', 'priority', 'fraction'))
            key = (part['task_id'], part['priority'])
            if key in seen or key[0] not in task_ids or key[1] not in ('urgent', 'normal'):
                raise ValueError('task and priority must be independent explicit axes')
            seen.add(key)
            if type(part['fraction']) not in (int, float) or not math.isfinite(part['fraction']) or not 0 <= part['fraction'] <= 1:
                raise ValueError('invalid workload fraction')
            total += part['fraction']
        if not math.isclose(total, 1.0, abs_tol=1e-9):
            raise ValueError('workload fractions must sum to one')
    if not names:
        raise ValueError('at least one declared workload required')
    keys(value['seed'], ('contract', 'master_seed', 'repetitions_state'))
    if value['seed']['contract'] != 'd1-seed-sha256-v1' or value['seed']['repetitions_state'] != 'thresholds_pending':
        raise ValueError('this draft contract has no frozen repetitions')
    derive_seed(value['seed']['master_seed'], 'development', 'noop', 0)
    # Draft-only on purpose: no numeric deadline or formal settings can enter without
    # the future full service/profile schema and semantic validator being implemented.
    if value['deadline'] != {'state': 'calibration_pending', 'values_ns': None}:
        raise ValueError('unvalidated absolute deadline cannot enter preparation')
    if value['constraints'] != {'state': 'thresholds_pending', 'max_in_flight': 1, 'allowed_corun': []}:
        raise ValueError('unvalidated concurrency/constraints cannot enter preparation')
    if value['policies'] != POLICIES:
        raise ValueError('baseline/proposed policy revision drift')
    keys(value['evidence'], REQUIRED_EVIDENCE)
    missing = []
    root = Path(evidence_root).resolve(strict=True)
    for gate, reference in value['evidence'].items():
        if reference is None:
            missing.append(gate)
            continue
        keys(reference, ('path', 'sha256', 'status'))
        digest(reference['sha256'])
        # Evidence receipts can be linked and audited, but cannot promote this draft to READY.
        relative = Path(reference['path'])
        if relative.is_absolute() or '..' in relative.parts or not relative.parts:
            raise ValueError('invalid evidence path')
        path = root / relative
        if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root):
            raise ValueError('evidence must be a contained regular file')
        if hashlib.sha256(path.read_bytes()).hexdigest() != reference['sha256']:
            raise ValueError('evidence hash mismatch')
        if reference['status'] not in ('pending', 'failed', 'verified'):
            raise ValueError('invalid evidence status')
        if reference['status'] != 'verified':
            missing.append(gate)
    return sorted(set(missing + ['frozen_service_profile_schema', 'calibrated_deadlines', 'frozen_constraints_and_repetitions']))


def noop(value, evidence_root):
    missing = validate_input(value, evidence_root)
    return {'protocol': 'sim-preparation-result-v1', 'status': 'SIM-01_INCOMPLETE',
            'input_sha256': hashlib.sha256(canonical(value)).hexdigest(), 'missing': missing,
            'dispatch_count': 0, 'simulated_completion_count': 0, 'comparative_results': None,
            'seed_contract_example': derive_seed(value['seed']['master_seed'], 'development', 'noop', 0)}


def request_kpis(arrivals, terminals):
    """Validate terminal coverage and compute service rates paired with conditional P95.

    This is a host contract function, not a production adapter or simulation engine.
    All times are integer ns in one caller-declared monotonic domain.
    """
    ids = {a['request_id'] for a in arrivals}
    if len(ids) != len(arrivals) or len({r['request_id'] for r in terminals}) != len(terminals) or ids != {r['request_id'] for r in terminals}:
        raise ValueError('every arrival needs exactly one terminal record')
    by_id = {r['request_id']: r for r in terminals}
    groups = {p: {'arrivals': 0, 'deadlines_set': 0, 'completed': 0, 'on_time': 0, 'late': 0,
                  'failed': 0, 'rejected': 0, 'expired': 0, 'cancelled': 0, 'unfinished': 0, 'responses_ns': []}
              for p in ('urgent', 'normal')}
    for arrival in arrivals:
        keys(arrival, ('request_id', 'task_id', 'priority', 'arrival_ns', 'deadline_ns'))
        if str(uuid.UUID(arrival['request_id'])) != arrival['request_id']:
            raise ValueError('invalid request identity')
        identifier(arrival['task_id'])
        if arrival['priority'] not in groups or type(arrival['arrival_ns']) is not int or arrival['arrival_ns'] < 0:
            raise ValueError('invalid arrival')
        deadline = arrival['deadline_ns']
        if deadline is not None and (type(deadline) is not int or deadline < arrival['arrival_ns']):
            raise ValueError('invalid deadline')
        row = by_id[arrival['request_id']]
        keys(row, ('request_id', 'status', 'requested_backend', 'actual_backend', 'enqueue_ns',
                   'execution_start_ns', 'execution_finish_ns', 'output_ready_ns', 'persist_complete_ns', 'terminal_ns'))
        if row['requested_backend'] not in ('CPU', 'GPU') or row['actual_backend'] not in (None, 'CPU', 'GPU'):
            raise ValueError('invalid backend')
        if row['actual_backend'] is not None and row['actual_backend'] != row['requested_backend']:
            raise ValueError('silent fallback forbidden')
        times = [arrival['arrival_ns']] + [row[k] for k in ('enqueue_ns', 'execution_start_ns', 'execution_finish_ns',
                 'output_ready_ns', 'persist_complete_ns', 'terminal_ns') if row[k] is not None]
        if any(type(t) is not int for t in times) or times != sorted(times) or row['terminal_ns'] is None:
            raise ValueError('invalid monotonic terminal boundaries')
        group = groups[arrival['priority']]
        group['arrivals'] += 1
        group['deadlines_set'] += deadline is not None
        if row['status'] == 'succeeded':
            required = ['enqueue_ns', 'execution_start_ns', 'execution_finish_ns', 'output_ready_ns', 'actual_backend']
            if arrival['priority'] == 'normal':
                required.append('persist_complete_ns')
            if any(row[k] is None for k in required):
                raise ValueError('success without actual completion boundaries')
            completion = row['output_ready_ns'] if arrival['priority'] == 'urgent' else row['persist_complete_ns']
            group['completed'] += 1
            group['responses_ns'].append(completion - arrival['arrival_ns'])
            if deadline is not None:
                group['on_time' if completion <= deadline else 'late'] += 1
        else:
            if row['status'] not in ('failed', 'rejected', 'expired', 'cancelled', 'unfinished') or row['output_ready_ns'] is not None or row['persist_complete_ns'] is not None:
                raise ValueError('invalid unsuccessful terminal')
            group[row['status']] += 1
    for group in groups.values():
        values = sorted(group.pop('responses_ns'))
        group['completed_response_p95_ns'] = values[math.ceil(.95 * len(values)) - 1] if values else None
        group['service_success_rate'] = group['completed'] / group['arrivals'] if group['arrivals'] else None
        group['on_time_service_rate'] = group['on_time'] / group['arrivals'] if group['arrivals'] and group['deadlines_set'] == group['arrivals'] else None
    return groups


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('validate', 'no-op'))
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--evidence-root', type=Path, required=True)
    args = parser.parse_args()
    from tools.d1_model_probe import read_json
    value = read_json(args.input)
    print(json.dumps(noop(value, args.evidence_root), sort_keys=True, indent=2))


if __name__ == '__main__':
    main()
