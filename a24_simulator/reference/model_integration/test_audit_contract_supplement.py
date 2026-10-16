"""Pure synthetic fixtures, loaded only by the registered guarded runner.

No direct main; fixtures do not read real datasets, import models, fit, simulate,
decompress a real raw file, use a process guard, or access network/devices.
"""
import copy
import json
from pathlib import Path
import tempfile
import unittest

import audit_contract_supplement as audit


def fold_fixture():
    sessions = [{'session_id': 'a', 'cohort_id': 'A'}, {'session_id': 'b', 'cohort_id': 'B'}]
    models, folds, timing = [], [], []
    for index, (held, train) in enumerate((('a', 'b'), ('b', 'a'))):
        model = {'status': 'EXPERIMENTAL_FIT', 'training_sessions': [train],
                 'training_cohorts': [train.upper()], 'coefficients': [1]}
        model['model_sha256'] = audit.digest(model)
        models.append({'fold_id': index, 'model': model})
        fold = {'fold_id': index, 'heldout_session_ids': [held], 'training_session_ids': [train]}
        folds.append(fold)
        timing.append(copy.deepcopy(fold))
    selection = {'combined': {'candidate_index': 2}}
    cv = {'selection': selection, 'candidates': [{'candidate_index': 2, 'modes': {'combined': {'fold_models': models}}}],
          'folds': {'folds': folds, 'groups': {'A': ['a'], 'B': ['b']}}}
    return cv, {'dataset_sha256': 'D', 'selection': selection}, {'dataset_sha256': 'D', 'sessions': sessions}, {'folds': timing}


def request(rid, task='C', ordinal=0, deadline=100):
    return {'request_id': rid, 'task': task, 'ordinal': ordinal, 'priority': 'N', 'group': ordinal,
            'scheduled_arrival_ns': 0, 'queue_entry_ns': 0, 'deadline_ns': deadline}


def order_fixture():
    # Response is earlier than AVAILABLE; second owner must wait for AVAILABLE.
    a, b = request('a', deadline=20), request('b', 'D', 1, 30)
    rows, decisions = [], []
    for q, at, queue in ((a, 0, [a, b]), (b, 5, [b])):
        state = {'now_ns': at, 'queue': copy.deepcopy(queue), 'owners': []}
        route = 'GPU' if q['task'] == 'C' else 'CPU'
        decisions.append({'time_ns': at, 'public_state': state, 'public_state_sha256': audit.digest(state),
                          'action': {'kind': 'DISPATCH', 'request_id': q['request_id'], 'route': route}})
        offsets = {'execution_start': 1, 'output_ready': 2, 'persist_complete': 3, 'worker_release': 4, 'lane_available': 5}
        row = {**q, 'dispatch_ns': at, 'reserved_at_ns': at, 'route': route, 'protocol': 'SERIAL',
               'available_ns': at + 5, 'response_ns': at + (2 if q['task'] == 'C' else 3), 'timing': {'offsets_ns': offsets}}
        for key in ('execution_start', 'output_ready', 'persist_complete', 'worker_release'):
            row[key + '_ns'] = at + offsets[key]
        rows.append(row)
    return {'public_input': {'observation_end_ns': 20, 'service_stop_ns': 20},
            'simulation': {'mode': 'GENERALIZED_ROLLING_COUNTERFACTUAL_ATOMIC_RESERVATIONS', 'policy': 'EDD',
                           'requests': rows, 'decisions': decisions, 'events': [], 'wait_used_ns': 0}}


def wait_fixture():
    q = request('a')
    state = {'now_ns': 0, 'queue': [q], 'owners': []}
    decision = {'time_ns': 0, 'public_state': state, 'action': {'kind': 'DISPATCH', 'request_id': 'a', 'route': 'GPU'},
                'applied_control': {'kind': 'WAIT', 'wait_ns': 200_000_000}}
    return {'public_input': {'service_stop_ns': 1_000_000_000},
            'simulation': {'decisions': [decision], 'requests': [{**q, 'reserved_at_ns': 200_000_000}],
                           'wait_used_ns': 200_000_000, 'status': 'COUNTERFACTUAL_COMPLETE_UNVALIDATED',
                           'events': [{'kind': 'WAIT_END', 'time_ns': 200_000_000}]}}


def budget_fixture():
    return {'global_cap': 137712, 'global_registered_total': 119750, 'a24_pool_cap': 2048,
            'shared_forecast_cap': 256, 'allocated_from_existing_a24': 256, 'a24_remaining_before_allocation': 353,
            'additional_global_reservation': 0, 'operation_simulation_cap': 256,
            'reserved_global_excluding_this': 92966, 'reserved_a24_excluding_this': 97}


class ContractSupplementTests(unittest.TestCase):
    def test_selected_fold_training_cohorts_are_disjoint(self):
        checks = audit.Checks()
        context, _ = audit.selected_fold_context(*fold_fixture(), 'D', checks)
        self.assertEqual(checks.failed, 0)
        self.assertEqual(context['a']['training_sessions'], ['b'])
        self.assertEqual(context['a']['training_cohorts'], ['B'])

    def test_selected_fold_rejects_target_cohort_training(self):
        cv, selection, metadata, timing = fold_fixture()
        model = cv['candidates'][0]['modes']['combined']['fold_models'][0]['model']
        model.update(training_sessions=['a'], training_cohorts=['A'])
        model['model_sha256'] = audit.digest({k: v for k, v in model.items() if k != 'model_sha256'})
        checks = audit.Checks()
        audit.selected_fold_context(cv, selection, metadata, timing, 'D', checks)
        self.assertGreater(checks.failed, 0)

    def test_heldout_manifest_cannot_substitute_final_model(self):
        checks = audit.Checks()
        context, _ = audit.selected_fold_context(*fold_fixture(), 'D', checks)
        manifest = {'model_bindings': {'fold_id': 0, 'training_session_ids_sha256': context['a']['training_ids_sha256'],
                                      'thermal_artifact_sha256': 'FINAL', 'thermal_model_sha256': 'FINAL_MODEL'}}
        audit.check_heldout_model({'source_session_id': 'a'}, None, None, context, {'thermal_cv_pin': {'sha256': 'CV'}}, checks, manifest)
        self.assertGreaterEqual(checks.failed, 2)

    def test_unavailable_selected_fold_stays_null_without_final_fallback(self):
        checks = audit.Checks()
        context = {'a': {'fold_id': 0, 'timing_binding_present': True, 'model_sha256': None, 'model_status': 'UNAVAILABLE',
                         'training_ids_sha256': 'T', 'training_sessions': [], 'training_cohorts': [], 'heldout_cohorts': ['A']}}
        manifest = {'model_bindings': {'fold_id': 0, 'training_session_ids_sha256': 'T', 'thermal_artifact_sha256': 'CV', 'thermal_model_sha256': None}}
        row = {'manifest': manifest, 'AP_model_sha256': None}
        raw = {'AP_prediction': {'model_sha256': None, 'status': 'UNKNOWN', 'ap_c': [None, None]}}
        report = audit.check_heldout_model({'source_session_id': 'a'}, row, raw, context, {'thermal_cv_pin': {'sha256': 'CV'}}, checks)
        self.assertEqual(checks.failed, 0)
        self.assertTrue(report['training_cohorts_disjoint'])

    def test_policy_consistency_checks_simulation_and_available_compact(self):
        manifest = {'policy': 'EDD'}
        row = {'identity': 'x', 'manifest': manifest, 'policy': 'EDD', 'planned': 2}
        raw = {'forecast_manifest': manifest, 'simulation': {'policy': 'FIFO_SERIAL_CG'}, 'compact': {'planned': 2}, 'qualification': {}}
        checks = audit.Checks()
        audit.check_policy_bindings(raw, row, {'manifest': manifest}, checks)
        self.assertEqual(checks.failed, 1)

    def test_ORDER_AVAILABLE_only_and_deterministic_tie_key(self):
        raw = order_fixture()
        checks = audit.Checks()
        audit.check_ORDER_trace(raw, checks)
        self.assertEqual(checks.failed, 0)
        # Exact tie hierarchy from source: deadline, scheduled arrival, ordinal, id.
        a, b = request('z', ordinal=0), request('a', ordinal=1)
        self.assertEqual(min([b, a], key=audit.ready_order_key)['request_id'], 'z')
        b['ordinal'] = 0
        self.assertEqual(min([b, a], key=audit.ready_order_key)['request_id'], 'a')

    def test_ORDER_wrong_ready_head_and_incomplete_snapshot_rejected(self):
        raw = order_fixture()
        raw['simulation']['decisions'][0]['action']['request_id'] = 'b'
        raw['simulation']['decisions'][0]['public_state']['queue'] = [request('b', 'D', 1, 30)]
        state = raw['simulation']['decisions'][0]['public_state']
        raw['simulation']['decisions'][0]['public_state_sha256'] = audit.digest(state)
        checks = audit.Checks()
        audit.check_ORDER_trace(raw, checks)
        self.assertGreater(checks.failed, 0)

    def test_ORDER_second_owner_waits_for_AVAILABLE_not_response(self):
        raw = order_fixture()
        raw['simulation']['requests'][1]['reserved_at_ns'] = 2
        checks = audit.Checks()
        audit.check_ORDER_trace(raw, checks)
        self.assertTrue(any('AVAILABLE' in f['check'] for f in checks.failures))

    def test_WAIT_exact_dose_and_end_boundary(self):
        checks = audit.Checks()
        report = audit.check_WAIT_trace(wait_fixture(), 'FIFO_WAIT_CG', checks)
        self.assertEqual(checks.failed, 0)
        self.assertEqual(report['interval_end_evidence'], 'CHECKED')

    def test_WAIT_duplicate_group_or_reservation_at_start_rejected(self):
        raw = wait_fixture()
        raw['simulation']['requests'][0]['reserved_at_ns'] = 0
        second = copy.deepcopy(raw['simulation']['decisions'][0])
        second['time_ns'] = 200_000_000
        raw['simulation']['decisions'].append(second)
        raw['simulation']['wait_used_ns'] *= 2
        checks = audit.Checks()
        audit.check_WAIT_trace(raw, 'FIFO_WAIT_CG', checks)
        self.assertGreater(checks.failed, 0)

    def test_WAIT_schema_absence_is_explicit_UNKNOWN(self):
        checks = audit.Checks()
        report = audit.check_WAIT_trace({'simulation': {}, 'public_input': {}}, 'FIFO_WAIT_CG', checks)
        self.assertEqual(report['status'], 'UNKNOWN_WAIT_ACTION_SCHEMA_UNAVAILABLE')
        self.assertEqual(checks.failed, 0)

    def test_PREPARED_receipt_is_one_to_one_and_exact(self):
        row = {'identity': 'x', 'raw_path': 'r', 'raw_sha256': 'R', 'prepared_path': 'p', 'prepared_sha256': 'P'}
        receipts = [{'event': 'START', 'identity': 'x'}, {'event': 'PREPARED', **row}, {'event': 'COMPLETE', **row}]
        checks = audit.Checks()
        audit.receipt_index(receipts, [row], checks)
        self.assertEqual(checks.failed, 0)
        receipts.insert(2, {'event': 'PREPARED', **row})
        checks = audit.Checks()
        audit.receipt_index(receipts, [row], checks)
        self.assertGreater(checks.failed, 0)

    def test_FAIL_present_refs_and_terminal_body_are_checked(self):
        terminal = {'event': 'FAIL', 'identity': 'x', 'raw_path': 'r', 'raw_sha256': 'R', 'prepared_path': 'p', 'prepared_sha256': 'P'}
        body = {**terminal, 'operation_sha256': 'OP', 'raw_sha256': 'WRONG'}
        item = {'start': {'identity': 'x'}, 'terminal': terminal, 'row': None}
        checks = audit.Checks()
        audit.terminal_body_check(item, body, 'OP', checks)
        self.assertEqual(checks.failed, 1)

    def test_legacy_duplicate_unresolved_START_never_refunded(self):
        report = audit.ledger_summary([{'event': 'START', 'identity': 'x'}, {'event': 'START', 'identity': 'x'},
                                      {'event': 'FAIL', 'identity': 'x'}, {'event': 'START', 'identity': 'y'}])
        self.assertEqual(report['START'], 3)
        self.assertEqual(report['unresolved_START_rows'], 2)
        self.assertEqual(report['duplicate_START_identities'], {'x': 2})

    def test_independent_budget_conserves_reserved_and_counts_FAILED_START(self):
        first = audit.independent_budget(budget_fixture(), canonical=26454, canonical_a24=1695, extra=74, prior=0, prior_shared=0, index=0)
        last = audit.independent_budget(budget_fixture(), canonical=26454, canonical_a24=1695, extra=74, prior=0, prior_shared=0, index=248)
        self.assertEqual(first['global_actual_plus_reserved'], 119750)
        self.assertEqual(last['global_actual_plus_reserved'], 119750)
        self.assertEqual(last['a24_shared_START_after'] + last['a24_reserved_remaining_after'], 2048)
        self.assertTrue(last['FAIL_is_consumed'])
        invalid = budget_fixture()
        invalid['operation_simulation_cap'] = 0
        with self.assertRaises(RuntimeError):
            audit.validate_budget_config(invalid)
        with self.assertRaises(RuntimeError):
            audit.independent_budget(budget_fixture(), canonical=26454, canonical_a24=1695, extra=74, prior=0, prior_shared=0, index=256)

    def test_empty_rows_completion_map_and_unbound_reference(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'producer'
            root.mkdir()
            op_path = Path(temp) / 'op.json'
            op_path.write_text(json.dumps({'output_dir': str(root)}), encoding='utf-8')
            rows = root / 'forecast_rows.jsonl'
            rows.write_bytes(b'')
            complete = root / 'COMPLETE.json'
            complete.write_text(json.dumps({'operation_sha256': audit.sha(op_path), 'outputs': {'forecast_rows.jsonl': {'sha256': audit.sha(rows), 'bytes': 0}}}), encoding='utf-8')
            saved = audit.SavedArtifacts({'path': str(op_path), 'sha256': audit.sha(op_path)}, {'path': str(complete), 'sha256': audit.sha(complete)})
            self.assertEqual(saved.bound(rows).stat().st_size, 0)
            with self.assertRaises(RuntimeError):
                saved.bound(root / 'unregistered.json')
