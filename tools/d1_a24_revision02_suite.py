"""PC preparation and future guarded dispatch for all eight REV02 study arms.

The CLI only writes unapproved drafts. It cannot construct an ADB client or
produce an execution authorization, claim, registry, or device evidence.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import random
import re
from pathlib import Path

from d1_a24_laptop_plan import ARMS, bank, encode, identity
from d1_a24_laptop_validator import NS, ValidationError, contained_file, load_json, manifest_requests, sha256
from d1_a24_revision02_design import matches_fixed_reference

REVISION = 'A24-BLOCKED-INITIAL-STATE-REV02-20261015'
PREFIX = 'A24R02-SUITE-'
ARM_KEYS = {recipe + '_' + arm for recipe, arm, *_ in ARMS}
RULES = {'history_ns': 60 * NS, 'maximum_wait_ns': 600 * NS,
         'maximum_gap_ns': 10 * NS, 'tolerance_c': .5,
         'maximum_abs_slope_c_per_min': .1}


def require(condition, message):
    if not condition:
        raise ValidationError(message)


def draft_plan(plan_id, *, stage='CONFIRM', seed=None, bindings=None):
    require(plan_id.startswith(PREFIX) and re.fullmatch(r'[A-Za-z0-9-]+', plan_id) is not None, 'new suite plan ID required')
    require(stage in {'DEV', 'CONFIRM'}, 'suite supports DEV/CONFIRM only')
    seed = (2026101520 if stage == 'DEV' else 2026101550) if seed is None else seed
    sessions, banks = [], {}
    # DEV here is a single PC compatibility block, not a new device-run approval.
    for block_number in range(1, (5 if stage == 'CONFIRM' else 1) + 1):
        block = f'R02{stage}{block_number:02d}'
        recipes = ['L64', 'C252', 'M128']
        random.Random(seed + block_number * 10).shuffle(recipes)
        for recipe in recipes:
            key = block + '_' + recipe
            b = bank(plan_id, block, recipe, seed + block_number, bindings)
            banks[key] = b
            specs = [s for s in ARMS if s[0] == recipe]
            random.Random(seed + block_number * 100 + ['L64', 'C252', 'M128'].index(recipe)).shuffle(specs)
            for position, (_, arm, order, route, concurrency, wait_ms) in enumerate(specs):
                sessions.append({'session_id': identity(plan_id, f'SUITE:{block}:{recipe}:{arm}'),
                    'plan_id': plan_id, 'stage': stage, 'block': block, 'recipe': recipe, 'arm': arm,
                    'policy_id': 'R02_SUITE_' + recipe + '_' + arm,
                    'prescription_id': recipe + '_' + arm, 'order': order, 'route': route,
                    'concurrency': concurrency, 'wait_ms': wait_ms, 'resident_mode': 'STANDARD',
                    'perfetto': 'OFF', 'request_count': b['request_count'], 'input_seed': seed + block_number,
                    'bank_file': 'banks/' + key + '.json', 'bank_sha256': hashlib.sha256(encode(b)).hexdigest(),
                    'gate_block_id': plan_id + '-' + key,
                    'reference_role': 'SELECT_FIRST' if position == 0 else 'MATCH_FIXED',
                    'reference_owner_session_id': identity(plan_id, f'SUITE:{block}:{recipe}:{specs[0][1]}'),
                    'plan_ordinal': len(sessions)})
    return {'schema': 'a24-revision02-suite-plan-v1', 'revision_id': REVISION,
        'plan_id': plan_id, 'stage': stage, 'status': 'PC_DRAFT_NOT_APPROVED',
        'execution_authorized': False, 'experiment_ready': False,
        'session_count': len(sessions), 'sessions': sessions, 'order_seed': seed,
        'independent_blocks': 5 if stage == 'CONFIRM' else 1,
        'reference_rules': RULES, 'cold_start_rule': 'first eligible post-common-preparation window; fixed within recipe/block',
        'passive_before_each_MATCH_FIXED': True, 'retry_or_replacement': 0,
        'device_commands': 0, 'NN_calls': 0, 'claims': 0, 'sessions_consumed': 0,
        'energy_J': None, 'surface_temperature_verified': False}, banks


def validate_plan(plan):
    require(plan.get('schema') == 'a24-revision02-suite-plan-v1' and plan.get('revision_id') == REVISION, 'wrong suite revision')
    require(plan.get('plan_id', '').startswith(PREFIX), 'legacy plan cannot be resumed as a suite')
    expected_blocks = 5 if plan.get('stage') == 'CONFIRM' else 1 if plan.get('stage') == 'DEV' else 0
    require(plan.get('independent_blocks') == expected_blocks, 'independent block declaration changed')
    rows = plan.get('sessions', [])
    require(expected_blocks > 0 and len(rows) == 8 * expected_blocks and plan.get('session_count') == len(rows), 'confirmation must retain exactly40 sessions; DEV fixture has8')
    require(plan.get('reference_rules') == RULES and plan.get('passive_before_each_MATCH_FIXED') is True and plan.get('retry_or_replacement') == 0, 'initial controls/retry contract changed')
    ids, groups = set(), {}
    for ordinal, row in enumerate(rows):
        spec = next((s for s in ARMS if s[:2] == (row.get('recipe'), row.get('arm'))), None)
        require(spec is not None, 'unsupported study arm')
        require(row.get('stage') == plan['stage'] and row.get('plan_id') == plan['plan_id'] and row.get('plan_ordinal') == ordinal, 'row/stage/order mismatch')
        require(tuple(row.get(k) for k in ['order', 'route', 'concurrency', 'wait_ms']) == spec[2:], 'arm prescription changed')
        require(row.get('prescription_id') == row['recipe'] + '_' + row['arm'] and row.get('request_count') == {'L64': 64, 'C252': 252, 'M128': 128}[row['recipe']], 'arm identity/quantity changed')
        require(row.get('resident_mode') == 'STANDARD' and row.get('perfetto') == 'OFF', 'common preparation changed')
        expected_id = identity(plan['plan_id'], f"SUITE:{row['block']}:{row['recipe']}:{row['arm']}")
        require(row.get('session_id') == expected_id and expected_id not in ids, 'old/duplicate session identity')
        ids.add(expected_id)
        require(row.get('gate_block_id') == plan['plan_id'] + '-' + row['block'] + '_' + row['recipe'], 'reference block identity changed')
        groups.setdefault((row['block'], row['recipe']), []).append(row)
    require(len({b for b, _ in groups}) == expected_blocks, 'independent block count changed')
    require({b for b, _ in groups} == {f"R02{plan['stage']}{i:02d}" for i in range(1, expected_blocks+1)}, 'registered block labels changed')
    for block in {b for b, _ in groups}:
        require({r['prescription_id'] for r in rows if r['block'] == block} == ARM_KEYS, 'missing/duplicate arm in a block')
    for group in groups.values():
        require([x['plan_ordinal'] for x in group] == list(range(group[0]['plan_ordinal'], group[0]['plan_ordinal'] + len(group))), 'recipe comparison must be contiguous')
        require(group[0]['reference_role'] == 'SELECT_FIRST' and all(x['reference_role'] == 'MATCH_FIXED' for x in group[1:]), 'first/shared reference role changed')
        require(all(x['reference_owner_session_id'] == group[0]['session_id'] for x in group), 'multiple reference owners')
        require(len({(x['bank_file'], x['bank_sha256'], x['input_seed']) for x in group}) == 1, 'paired input bank differs')
    return rows


def write_draft(destination, plan_id, *, templates, stage='CONFIRM', seed=None):
    """Only non-executable copies; never call a legacy assembler that grants auth."""
    require(not destination.exists(), 'write-once draft: choose a new destination')
    by_arm = {}
    for path in templates.glob('*.json'):
        m = load_json(path)
        if m.get('recipe', '') + '_' + m.get('arm', '') in ARM_KEYS:
            by_arm.setdefault(m['recipe'] + '_' + m['arm'], m)
    require(set(by_arm) == ARM_KEYS, 'all eight bound templates required')
    c = by_arm['C252_CPU']['requests'][0]
    d = next(q for q in by_arm['M128_BASE']['requests'] if q['task'] == 'D')
    require(c['input_file'] == d['input_file'] and c['input_sha256'] == d['input_sha256'], 'current one-approved-image scope changed')
    bindings = {'approved_inputs': [{'input_file': c['input_file'], 'input_sha256': c['input_sha256'],
                 'tensor_sha256': {'C': c['tensor_sha256'], 'D': d['tensor_sha256']}}]}
    plan, banks = draft_plan(plan_id, stage=stage, seed=seed, bindings=bindings)
    validate_plan(plan)
    destination.mkdir(parents=True)
    (destination / 'banks').mkdir()
    (destination / 'manifests').mkdir()
    (destination / 'plan.json').write_bytes(encode(plan))
    plan_sha = sha256(destination / 'plan.json')
    for key, value in banks.items():
        (destination / 'banks' / (key + '.json')).write_bytes(encode(value))
    for row in plan['sessions']:
        m = copy.deepcopy(by_arm[row['prescription_id']])
        m.update(row)
        m.update(plan_sha256=plan_sha, revision_id=REVISION, execution_authorized=False,
                 authorization='NONE_PC_PREPARATION_ONLY', device_status='PC_ONLY_NOT_APPROVED', mock=True,
                 consumed=False, sessions_consumed=0, claims=0, NN_calls=0, experiment_ready=False,
                 requests=banks[row['block'] + '_' + row['recipe']]['requests'])
        for spec in m['models'].values():
            spec['identity']['session_id'] = row['session_id']
        manifest_requests(m, require_materials=True)
        (destination / 'manifests' / (row['session_id'] + '.json')).write_bytes(encode(m))
    summary = {'status': 'PC_PREPARED_NOT_EXECUTABLE', 'stage': stage,
        'plan_sha256': plan_sha, 'sessions': len(plan['sessions']),
        'planned_requests': sum(r['request_count'] for r in plan['sessions']),
        'reference_groups': len(banks), 'device_commands': 0, 'NN_calls': 0, 'claims': 0,
        'sessions_consumed': 0, 'current_budget_cap': 64, 'historical_attempts': 33,
        'unallocated': 31, 'extra_slots_if_entire_new_plan_executed': max(0, len(plan['sessions']) - 31),
        'additional_device_development_not_included': True}
    (destination / 'PREPARATION.json').write_bytes(encode(summary))
    return summary


def bound_document(config, authorization, key, sha_key):
    path = Path(config.get(key, ''))
    expected = config.get(sha_key)
    require(path.is_file() and isinstance(expected, str) and sha256(path) == expected == authorization.get(sha_key), key + ' exact bytes not authorized')
    return load_json(path)


def gate_for_registered_row(row, base_gate, run_root):
    """Pure future assembly; no file creation or new temperature selection."""
    require(re.fullmatch(r'[A-Za-z0-9_-]+', row['gate_block_id']) is not None, 'unsafe reference identity')
    gate = copy.deepcopy(base_gate)
    reference = Path(run_root) / 'references' / (row['gate_block_id'] + '.json')
    gate.update(schema='a24-revision02-blocked-gate-v1', block_id=row['gate_block_id'],
                reference_role=row['reference_role'], block_reference_path=str(reference), Tref_c=None)
    if row['reference_role'] == 'MATCH_FIXED':
        require(reference.is_file(), 'first arm must freeze its reference before assembling later arms')
        first = load_json(reference)
        require(first.get('block_id') == row['gate_block_id'] and first.get('reference_session_id') == row['reference_owner_session_id'], 'reference belongs to another block/first arm')
        gate.update(Tref_c=first['Tref_c'], block_reference_sha256=sha256(reference))
    return gate


def validate_suite_registration(manifest, config, authorization, gate):
    """Fail before any phone/registry activity when draft/budget/freeze is absent."""
    require(manifest.get('revision_id') == REVISION, 'suite revision missing')
    plan = bound_document(config, authorization, 'suite_plan_file', 'suite_plan_sha256')
    rows = validate_plan(plan)
    require(plan.get('status') == 'FROZEN_EXECUTION_PLAN' and plan.get('execution_authorized') is True, 'PC draft is not an execution plan')
    require(manifest.get('plan_sha256') == config['suite_plan_sha256'], 'manifest references different suite plan')
    row = next((r for r in rows if r['session_id'] == manifest.get('session_id')), None)
    require(row is not None and all(manifest.get(k) == v for k, v in row.items()), 'manifest not the exact registered arm')
    registry = Path(config.get('registry_root', ''))
    require(registry.name == plan['plan_id'] and registry.parent.name == 'a24-laptop-measurement-v1' and not registry.is_symlink(), 'foreign registry path')
    bank_path = contained_file(Path(config['suite_plan_file']).parent, row['bank_file'])
    require(bank_path.is_file() and sha256(bank_path) == row['bank_sha256'], 'paired bank bytes changed')
    require(load_json(bank_path)['requests'] == manifest.get('requests'), 'paired requests changed')
    contract = bound_document(config, authorization, 'revision_contract_file', 'revision_contract_sha256')
    require(contract.get('status') == 'FROZEN_EXECUTION_CONTRACT' and contract.get('plan_sha256') == manifest['plan_sha256'], 'execution contract not frozen for plan')
    require(contract.get('reference_rules') == RULES and contract.get('energy_J') is None and contract.get('surface_temperature_verified') is False, 'measurement meaning changed')
    budget = bound_document(config, authorization, 'budget_file', 'budget_sha256')
    require(budget.get('authorized') is True and budget.get('plan_sha256') == manifest['plan_sha256'], 'budget increase/reservation not explicitly authorized')
    for key in ['cap', 'spent_before_plan', 'reserved_for_plan']:
        require(type(budget.get(key)) is int and budget[key] >= 0, 'invalid budget arithmetic')
    require(budget['reserved_for_plan'] == len(rows) and budget['cap'] - budget['spent_before_plan'] >= len(rows), 'insufficient reserved budget; never shrink confirmation')
    require(gate.get('block_id') == row['gate_block_id'] and gate.get('reference_role') == row['reference_role'], 'reference group/role differs from plan')
    reference = Path(gate.get('block_reference_path', ''))
    reference_root = Path(config['output_root']).parent / 'references'
    require(reference.resolve() == (reference_root / (row['gate_block_id'] + '.json')).resolve() and not reference.is_symlink(), 'foreign reference path')
    if row['reference_role'] == 'MATCH_FIXED':
        require(reference.is_file() and load_json(reference).get('reference_session_id') == row['reference_owner_session_id'], 'first reference owner absent/different')
    window = bound_document(config, authorization, 'window_file', 'window_sha256')
    require(window.get('execution_authorized') is True and window.get('plan_sha256') == manifest['plan_sha256'], 'no future user execution window')
    from d1_a24_revision02_window import check_deadline
    check_deadline(window, 'NEW_SESSION')
    if manifest['stage'] == 'CONFIRM':
        freeze = bound_document(config, authorization, 'confirm_freeze', 'confirm_freeze_sha256')
        require(freeze.get('status') == 'FROZEN_BEFORE_CONFIRM' and freeze.get('plan_sha256') == manifest['plan_sha256'], 'new independent confirmation freeze absent')
        require(freeze.get('planned_confirm_sessions') == 40 and freeze.get('independent_blocks') == 5 and freeze.get('old_confirm_results_pooled') is False, 'confirmation scope/independence changed')
        require(freeze.get('apk_sha256') == config['apk']['sha256'] and freeze.get('source_sha256') == config['source_code_sha256'], 'freeze APK/source differs')
        require(freeze.get('budget_sha256') == config['budget_sha256'], 'freeze budget differs')
        documents = {}
        for key in ['analysis_contract', 'pre_measurement_predictions', 'prior_stage_ledger', 'new_protocol_functional_evidence']:
            documents[key] = bound_document(config, authorization, key, key + '_sha256')
            require(freeze.get(key + '_sha256') == config[key + '_sha256'], 'freeze ' + key + ' differs')
        require(documents['analysis_contract'].get('frozen') is True and documents['analysis_contract'].get('planned_confirm_sessions') == 40, 'analysis must be frozen for40')
        evidence = documents['new_protocol_functional_evidence']
        require(evidence.get('status') == 'DEVICE_VALIDATED' and evidence.get('mock') is False and type(evidence.get('NN_calls')) is int and evidence['NN_calls'] > 0 and set(evidence.get('supported_arms', [])) == ARM_KEYS and evidence.get('source_sha256') == config['source_code_sha256'] and evidence.get('apk_sha256') == config['apk']['sha256'], 'new protocol functional validation missing; PC mocks cannot substitute')
        require(isinstance(authorization.get('fingerprint'), str) and bool(authorization['fingerprint']) and evidence.get('device_fingerprint') == authorization['fingerprint'], 'functional evidence belongs to another device')
        require(documents['prior_stage_ledger'].get('attempt_counts') == {'I': 4, 'F': 4, 'DEV': 16}, 'original I/F/DEV attempt history must be preserved, not declared successful')
        require(documents['pre_measurement_predictions'].get('status') in {'NOT_CREATED_NO_MODEL_ACCURACY_CLAIM', 'FROZEN_PRE_MEASUREMENT_PREDICTIONS'}, 'predictions or explicit absence must be frozen')
    return row


def passive_before_dispatch(client, gate, evidence_path=None):
    """Only a future explicitly authorized client; no warmup or app in this wait."""
    if gate['reference_role'] == 'SELECT_FIRST':
        return
    from d1_a24_revision02_suite_control import read_hal
    reference_file = Path(gate['block_reference_path'])
    expected = gate['block_reference_sha256']
    reference = load_json(reference_file)
    samples = []
    if evidence_path is not None:
        require(not evidence_path.exists(), 'passive history already exists; never overwrite')
        evidence_path.parent.mkdir(parents=True, exist_ok=True)
    while True:
        client.check_window('NEW_SESSION')
        require(sha256(reference_file) == expected, 'shared reference changed during passive wait')
        x = read_hal(client)
        if evidence_path is not None:
            with evidence_path.open('a', encoding='utf-8') as stream:
                stream.write(json.dumps(x) + '\n')
        ap = [s['value_c'] for s in x['sensors'] if s['sensor_name'] == 'AP' and s['sensor_type'] == 0]
        samples.append({'before_ns': x['device_elapsed_before_ns'], 'after_ns': x['device_elapsed_after_ns'], 'AP_c': ap[0] if len(ap) == 1 else None})
        start = next((i for i in range(len(samples)-1, -1, -1) if samples[i]['before_ns'] <= samples[-1]['before_ns']-60*NS), None)
        if start is not None and len(ap) == 1 and ap[0] <= reference['Tref_c'] and matches_fixed_reference(samples[start:], samples[start]['before_ns'], reference, RULES):
            if evidence_path is not None:
                from d1_a24_revision02_suite_control import atomic_json
                atomic_json(evidence_path.with_suffix('.ready.json'), {
                    'source_reference_sha256': expected, 'samples': len(samples),
                    'observed_device_elapsed_s': (samples[-1]['after_ns'] - samples[0]['before_ns']) / NS,
                    'last_AP_c': ap[0], 'new_app_started': False,
                    'post_warmup_gate_still_required': True, 'idle_energy_assumed_zero': False})
            return
        client.sleep_ns(5*NS)


def run_registered_session(manifest, config, authorization, gate, *, execute_authorized=False, client=None):
    """Future API only. No CLI enables phone execution in this prep package."""
    require(execute_authorized and client is not None and getattr(client, 'bounded_window_authorized', False), 'PC preparation only; explicit later bounded execution required')
    from d1_a24_revision02_suite_control import check_authorization, run_one
    check_authorization(manifest, config, authorization, gate, execute_authorized=True)
    require(not (Path(config['registry_root']) / manifest['session_id']).exists() and not (Path(config['output_root']) / manifest['session_id']).exists(), 'session already attempted/recovered; never replay')
    history = Path(config['output_root']).parent / 'pre_app_cooldown' / (manifest['session_id'] + '.jsonl')
    passive_before_dispatch(client, gate, history)
    # run_one rechecks exact authorization and then runs the unchanged app lifecycle.
    result = run_one(manifest, config, authorization, gate, execute_authorized=True, client=client)
    if result['status'] == 'COMPLETE_TRACE_RECOVERED':
        from d1_a24_measurement_batch import finish_only_closed_owned_process
        released = finish_only_closed_owned_process(client, Path(config['output_root']) / manifest['session_id'], manifest['session_id'], package=config.get('package_name', 'com.example.d1check.benchmarkrunner.modelprobe'))
        require(released, 'closed empty owned process not proved; no next arm may start')
        result['closed_empty_owned_process_released'] = True
    return result


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--templates', type=Path, required=True)
    p.add_argument('--plan-id', required=True)
    p.add_argument('--stage', choices=['DEV', 'CONFIRM'], default='CONFIRM')
    p.add_argument('--seed', type=int)
    a = p.parse_args(argv)
    print(json.dumps(write_draft(a.output, a.plan_id, templates=a.templates, stage=a.stage, seed=a.seed)))


if __name__ == '__main__':
    main()
