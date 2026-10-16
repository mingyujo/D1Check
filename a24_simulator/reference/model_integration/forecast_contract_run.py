"""Thin registered public ORDER contract adapter over frozen forecast V3.

ORDER validation uses its explicit EDD / C_GPU_D_CPU / SERIAL prescription.
Only that heldout callback uses the existing atomic global-serial executor and
a temporary fixed-route nominal filter. Other validation and all novel forecasts
retain V3 behavior. No source/model/data is amended; every temporary callback
is restored on success or failure. Source declarations do not establish the
installed scheduler implementation. Import is inert. SOURCE ONLY until root
registration; no simulator, fit, NN, device or network is run by preparation.
"""
from __future__ import annotations

import argparse
import contextlib
import copy
import io
from pathlib import Path
import unittest

import forecast_overlay_run as v3
from runtime_guard import canonical, now, operation, pin, read, require, sha, write_new

VERSION = 'A24-REGISTERED-SOURCE-CONTRACT-FORECAST-v1'
CONTRACT_SCHEMA = 'A24_SOURCE_DECLARED_POLICY_CONTRACTS_V1'
V3_SOURCE_SHA256 = '120462570417bbf39dd2aadf7ec063bdff3f4e00074d527db2394d0180622254'
ORDER_FIELDS = {'arm': 'ORDER', 'policy': 'EDD', 'public_order': 'EDD', 'public_route': 'C_GPU_D_CPU',
                'protocol': 'SERIAL', 'validation_execution': 'ATOMIC_PROTOCOL_GLOBAL_SERIAL',
                'classification_route': 'GPU', 'detection_route': 'CPU',
                'installed_verified': False, 'scheduler_body_verified': False}


def validate_contract_document(document, dataset_pin):
    require(document.get('schema') == CONTRACT_SCHEMA, 'Registered source-policy contract schema')
    original = document.get('original_dataset_pin', {})
    require(original.get('sha256') == dataset_pin.get('sha256') == v3.ORIGINAL_DATASET_SHA256 and
            original.get('bytes') == dataset_pin.get('bytes') and
            v3._path_key(original.get('path', '')) == v3._path_key(dataset_pin.get('path', '')),
            'Source-policy proof must bind the same original f54 dataset path/SHA/size')
    contracts = document.get('contracts')
    require(isinstance(contracts, list) and len(contracts) == 1 and
            all(contracts[0].get(k) == value for k, value in ORDER_FIELDS.items()),
            'Only the registered public EDD/fixed-CG/global-SERIAL ORDER extension is supported')
    roster = document.get('order_roster')
    require(isinstance(roster, list) and roster and len({r['session_id'] for r in roster}) == len(roster),
            'Unique registered public ORDER session roster required')
    return contracts[0], {r['session_id']: r for r in roster}


def resolve_ORDER_contract(source, document, dataset_pin):
    """Read only public identity/prescription/plan fields, never trace outcomes."""
    contract, roster = validate_contract_document(document, dataset_pin)
    if source.get('arm') != 'ORDER':
        return None, 'NOT_ORDER_EXTENSION'
    registered = roster.get(source.get('session_id'))
    if registered is None or registered.get('cohort_id') != source.get('cohort_id'):
        return None, 'UNKNOWN_UNREGISTERED_ORDER_SESSION_OR_COHORT'
    if source.get('device') != 'A24' or source.get('source_family') != 'm8':
        return None, 'UNKNOWN_ORDER_DEVICE_OR_SOURCE_CONTRACT'
    for field in ('arm', 'public_order', 'public_route', 'protocol'):
        if source.get(field) is None:
            return None, 'UNKNOWN_MISSING_EXPLICIT_PUBLIC_' + field.upper()
        if source[field] != contract[field]:
            return None, 'UNKNOWN_CONTRADICTORY_PUBLIC_' + field.upper()
    declared = source.get('public_declared_protocol')
    if declared is not None and declared != contract['protocol']:
        return None, 'UNKNOWN_CONTRADICTORY_PUBLIC_DECLARED_PROTOCOL'
    if registered.get('protocol') != source['protocol'] or registered.get('requests') != len(source.get('requests', [])):
        return None, 'UNKNOWN_REGISTERED_ORDER_PLAN_MISMATCH'
    return contract, None


def execution_metadata(source, policy, contract_sha256, *, ORDER=False):
    return {'experiment_role': 'EXACT_VALIDATION', 'schedule_role': 'EXACT_DECLARED_VALIDATION_TEMPLATE',
            'meaning': 'Observed public template and declared policy constraints; timing and queue/deadline outcomes are independently predicted.',
            'source_session_id': source.get('session_id'), 'source_cohort_id': source.get('cohort_id'),
            'source_arm': source.get('arm'), 'policy': policy, 'source_policy_contract_sha256': contract_sha256,
            'executor': 'ATOMIC_PROTOCOL_GLOBAL_SERIAL' if ORDER else 'FROZEN_V3_DATA_DERIVED_PROGRESS',
            'routes': {'C': 'GPU', 'D': 'CPU'} if ORDER else 'FROZEN_V3_PUBLIC_RULE_ROUTE_CONTRACT',
            'installed_verified': False, 'EXACT_INSTALLED': False, 'scheduler_body_verified': False,
            'SCHEDULER_BODY_NOT_VERIFIED': True,
            'PAIR_G_atomic_or_same_group_assumption_added': False,
            'PAIR_G_scope': 'Original rolling/global FIFO/current-lane/max2 CG_DC compatible prediction; complete scheduler body unverified.',
            'source_declaration_is_installed_runtime_proof': False, 'fresh_confirmation': False,
            'predictive_accuracy_PASS': None, 'NN_training': 0}


@contextlib.contextmanager
def ORDER_execution(model):
    """Temporary route filter plus original global-serial executor, no new draw."""
    import protocol_simulator
    from timing_model import UnsupportedContext
    original_nominal, original_simulate = model.nominal, protocol_simulator.simulate_protocol
    original_gap_support = v3._select_redispatch
    def fixed_nominal(context, task, route, *args, **kwargs):
        if route != ('GPU' if task == 'C' else 'CPU'):
            raise UnsupportedContext('ORDER_SOURCE_DECLARED_FIXED_C_GPU_D_CPU_ROUTE')
        return original_nominal(context, task, route, *args, **kwargs)
    def serial_simulate(template, timing, policy='ATC', **kwargs):
        require(timing is model and policy == 'EDD', 'ORDER adapter may only execute its bound EDD validation model')
        kwargs = dict(kwargs)
        kwargs['concurrency_mode'] = 'ATOMIC_PROTOCOL'
        return original_simulate(template, timing, policy, **kwargs)
    def serial_gap_support(timing, template, policy, case, op):
        require(timing is model and policy == 'EDD', 'ORDER SERIAL gap support must use its bound EDD validation model')
        # This helper policy argument selects only fixed C_GPU/D_CPU routes and
        # SERIAL gap support. EDD ordering remains in serial_simulate above.
        result = original_gap_support(timing, template, 'FIFO_SERIAL_CG', case, op)
        return {**result, 'source_policy_support_scope': 'ORDER_EDD_FIXED_CG_GLOBAL_SERIAL',
                'support_diagnostic_reference': 'FIFO_SERIAL_CG means identical route/protocol eligibility only; ORDER execution stays EDD'}
    model.nominal, protocol_simulator.simulate_protocol = fixed_nominal, serial_simulate
    v3._select_redispatch = serial_gap_support
    try:
        yield
    finally:
        protocol_simulator.simulate_protocol = original_simulate
        model.nominal = original_nominal
        v3._select_redispatch = original_gap_support


@contextlib.contextmanager
def contract_callbacks(op, document, decisions, completed_callbacks):
    """Patch only V3 callback globals inside this one guarded, single process."""
    validate_contract_document(document, op['dataset_pin'])
    before = v3.digest(document)
    original_policy, original_predict, original_guard = v3.exact_measured_policy, v3.predict_case, v3.process_guard
    def actual_entry_guard(entry, known_ps=()):
        require(v3._path_key(entry) == v3._path_key(v3.__file__), 'Only the frozen V3 internal guard call may be adapted')
        # Exact original process guard, original limits and known-PS roster.
        # The running entry is this new adapter, including its venv ancestor
        # shims. Passing V3's file instead would incorrectly reject those shims.
        return original_guard(__file__, known_ps)
    def measured_policy(source, current_op):
        if source.get('arm') == 'ORDER':
            contract, reason = resolve_ORDER_contract(source, document, op['dataset_pin'])
            policy = contract['policy'] if contract else None
        else:
            policy, reason = original_policy(source, current_op)
        decisions.append({'session_id': source.get('session_id'), 'cohort_id': source.get('cohort_id'),
                          'arm': source.get('arm'), 'policy': policy, 'reason': reason,
                          'UNKNOWN_means_no_simulation_START': reason is not None,
                          'public_fields_only': True, 'observed_timing_or_overlap_used': False})
        return policy, reason
    def predict(case, model, thermal, profile, current_op, execution_guard, **kwargs):
        source = kwargs.get('validation_source')
        if source is None:
            result, compact = original_predict(case, model, thermal, profile, current_op, execution_guard, **kwargs)
            metadata = {'experiment_role': 'GENERALIZED_NOVEL', 'schedule_role': 'GENERALIZED_NOVEL_COUNTERFACTUAL',
                        'executor': 'FROZEN_V3_DATA_DERIVED_PROGRESS', 'source_policy_contract_sha256': op['source_policy_contract_pin']['sha256'],
                        'novel_policy_route_admission_WAIT_behavior_changed': False, 'EXACT_INSTALLED': False,
                        'SCHEDULER_BODY_NOT_VERIFIED': True, 'fresh_confirmation': False, 'predictive_accuracy_PASS': None}
        else:
            is_ORDER = source.get('arm') == 'ORDER'
            if is_ORDER:
                contract, reason = resolve_ORDER_contract(source, document, op['dataset_pin'])
                require(contract is not None and reason is None and case['policy'] == 'EDD',
                        'Missing/contradictory ORDER public contract must remain UNKNOWN with zero START')
                with ORDER_execution(model):
                    result, compact = original_predict(case, model, thermal, profile, current_op, execution_guard, **kwargs)
            else:
                result, compact = original_predict(case, model, thermal, profile, current_op, execution_guard, **kwargs)
            metadata = execution_metadata(source, case['policy'], op['source_policy_contract_pin']['sha256'], ORDER=is_ORDER)
        result.setdefault('qualification', {})['source_policy_contract'] = copy.deepcopy(metadata)
        compact['source_policy_contract'] = copy.deepcopy(metadata)
        result['compact'] = compact
        completed_callbacks.append({'label': case['label'], 'start_id': execution_guard.get('start_id'),
                                    'source_policy_contract': metadata})
        return result, compact
    v3.exact_measured_policy, v3.predict_case, v3.process_guard = measured_policy, predict, actual_entry_guard
    try:
        yield
    finally:
        v3.exact_measured_policy, v3.predict_case, v3.process_guard = original_policy, original_predict, original_guard
        require(v3.digest(document) == before, 'Registered source contract document mutated')


def validate_operation(op):
    require(op.get('mode') in ('FORECAST', 'FORECAST_CONTRACT_TEST'), 'Source-contract entry mode')
    require(v3._path_key(op['worker_lock_path']) == v3._path_key(v3.WORKER_LOCK) and
            len(op['protected_pins']) >= 351, 'Original lock/protected351 contract required')
    require(op.get('HTTP') == 0 and op.get('device_commands') == 0 and op.get('new_environment') == 0 and
            op.get('automatic_retry') is False, 'Frozen saved-only orchestration/no-retry contract required')
    names = {Path(p['path']).name for p in op['source_pins']}
    require({'forecast_contract_run.py', 'forecast_overlay_run.py', 'forecast_run.py', 'runtime_guard.py',
             'timing_model.py', 'protocol_simulator.py', 'thermal_model.py', 'historical_observer.py'} <= names,
            'Exact contract/V3/V2/frozen scientific source closure required')
    require(sum(Path(p['path']).name == 'forecast_overlay_run.py' for p in op['source_pins']) == 1 and
            next(p for p in op['source_pins'] if Path(p['path']).name == 'forecast_overlay_run.py')['sha256'] == V3_SOURCE_SHA256,
            'Frozen V3 source pin differs')
    if op['mode'] == 'FORECAST_CONTRACT_TEST':
        require('test_contract_forecast.py' in names, 'Dedicated new contract fixture pin required')
    else:
        v3._validate_operation(op)
        registered = {(v3._path_key(p['path']), p['sha256']) for p in op['input_pins']}
        spec = op['source_policy_contract_pin']
        require((v3._path_key(spec['path']), spec['sha256']) in registered, 'Source-policy contract is not registered input')


def forecast_stage(op, out, operation_path):
    validate_operation(op)
    document = read(pin(op['source_policy_contract_pin']))
    contract, roster = validate_contract_document(document, op['dataset_pin'])
    registered = {(v3._path_key(p['path']), p['sha256']) for p in op['input_pins']}
    for spec in document['source_evidence_pins']:
        require((v3._path_key(spec['path']), spec['sha256']) in registered, 'Declared source-policy evidence is not registered input')
        pin(spec)
    require(op.get('run_heldout_validation', True) is True,
            'This first source-contract adapter operation requires fresh registered heldout validation; prior V3 validation cannot be reused silently')
    write_new(out / 'SOURCE_POLICY_CONTRACT_BINDINGS.json', {'schema': VERSION,
              'source_policy_contract_pin': op['source_policy_contract_pin'], 'original_dataset_pin': op['dataset_pin'],
              'frozen_V3_sha256': V3_SOURCE_SHA256, 'ORDER_public_contract': contract,
              'ORDER_registered_sessions': sorted(roster), 'source_evidence_pins': document['source_evidence_pins'],
              'generalized_novel_executor_unchanged': True, 'PAIR_G_atomic_or_same_group_added': False,
              'EXACT_INSTALLED': False, 'SCHEDULER_BODY_NOT_VERIFIED': True,
              'independent_confirmation': False, 'new_parameter_fits': 0, 'new_AP_fits': 0,
              'new_policy_specific_timing_builds': 0, 'NN': 0})
    decisions, completed = [], []
    with contract_callbacks(op, document, decisions, completed):
        result = v3.forecast_stage(op, out, operation_path)
    write_new(out / 'SOURCE_POLICY_CONTRACT_APPLICATION.json', {'schema': VERSION,
              'source_policy_contract_sha256': op['source_policy_contract_pin']['sha256'],
              'decisions': decisions, 'completed_callbacks': completed,
              'ORDER_selected_EDD': sum(r['arm'] == 'ORDER' and r['policy'] == 'EDD' and r['reason'] is None for r in decisions),
              'ORDER_UNKNOWN_zero_START': sum(r['arm'] == 'ORDER' and r['reason'] is not None for r in decisions),
              'callbacks_restored': True, 'novel_physics_RNG_and_potential_math_changed': False,
              'original_V3_forecast_result_sha256': sha(out / 'FORECAST_RESULT.json'),
              'actual_simulation_START_consumed': result['simulation_START_consumed'],
              'new_environment_zero_is_orchestration_only': True, 'predictive_accuracy_PASS': None,
              'EXACT_INSTALLED': False, 'SCHEDULER_BODY_NOT_VERIFIED': True, 'utc': now()})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--operation', required=True)
    args = parser.parse_args()
    with operation(args.operation, __file__) as (op, out):
        validate_operation(op)
        if op['mode'] == 'FORECAST_CONTRACT_TEST':
            suite = unittest.TestLoader().discover(str(v3.WORK), pattern='test_contract_forecast.py')
            stream = io.StringIO()
            tests = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
            write_new(out / 'TEST_RESULT.json', {'status': 'PASS' if tests.wasSuccessful() else 'FAIL',
                      'testsRun': tests.testsRun, 'output': stream.getvalue(),
                      'failures': [(str(t), e) for t, e in tests.failures], 'errors': [(str(t), e) for t, e in tests.errors],
                      'actual_simulator_START': 0, 'actual_model_builds': 0, 'AP_fits': 0, 'NN': 0})
            require(tests.wasSuccessful(), 'New contract fixtures failed; namespace consumed, no automatic retry')
        else:
            forecast_stage(op, out, args.operation)
    print(canonical({'status': 'COMPLETE', 'mode': op['mode'], 'output': str(out)}))


if __name__ == '__main__':
    main()
