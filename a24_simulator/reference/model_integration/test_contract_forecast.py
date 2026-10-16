"""Sealed public-contract/callback fixtures; no simulator or model is run."""
from __future__ import annotations

import copy
import inspect
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import forecast_contract_run as subject
import protocol_simulator
from timing_model import UnsupportedContext


def dataset_pin():
    return {'path': str(subject.v3.WORK / 'SEALED_SYNTHETIC_DATASET.json'),
            'sha256': subject.v3.ORIGINAL_DATASET_SHA256, 'bytes': 1024}


def source(arm='ORDER'):
    return {'session_id': 'SEALED_ORDER', 'cohort_id': 'SEALED_COHORT', 'arm': arm,
            'source_family': 'm8', 'device': 'A24', 'public_order': 'EDD' if arm == 'ORDER' else 'FIFO',
            'public_route': 'C_GPU_D_CPU', 'protocol': 'CG_DC' if arm == 'PAIR_G' else 'SERIAL',
            'public_declared_protocol': 'CG_DC' if arm == 'PAIR_G' else 'SERIAL', 'requests': [{}, {}]}


def document():
    return {'schema': subject.CONTRACT_SCHEMA, 'original_dataset_pin': dataset_pin(),
            'contracts': [copy.deepcopy(subject.ORDER_FIELDS)],
            'order_roster': [{'session_id': 'SEALED_ORDER', 'cohort_id': 'SEALED_COHORT', 'protocol': 'SERIAL', 'requests': 2}]}


def operation():
    return {'dataset_pin': dataset_pin(), 'source_policy_contract_pin': {'sha256': 'b' * 64},
            'measured_arm_policy_map': {'ORDER': 'FIFO_SERIAL_CG', 'PAIR_G': 'FIFO_PAIR_CG', 'BASE': 'FIFO_SERIAL_CG'}}


def dummy_model():
    return SimpleNamespace(nominal=lambda context, task, route, *args, **kwargs: {'route': route, 'task': task})


def fake_predict(case, model, thermal, profile, op, guard, **kwargs):
    blocked = False
    try:
        model.nominal({}, 'C', 'CPU')
    except UnsupportedContext:
        blocked = True
    supported = model.nominal({}, 'C', 'GPU')
    sim = protocol_simulator.simulate_protocol({'sealed': True}, model, case['policy'],
                                              concurrency_mode='DATA_DERIVED_PROGRESS', pair_scope='READY_QUEUE')
    compact = {'sealed': True, 'C_CPU_blocked': blocked, 'C_GPU': supported, 'sim': sim}
    return {'qualification': {}, 'compact': compact, 'simulation': sim}, compact


class ContractForecastTests(unittest.TestCase):
    def test_explicit_public_ORDER_contract_resolves_EDD_without_outcomes(self):
        observed = source()
        observed.update(owner_intervals=[{'FORBIDDEN_FUTURE': True}], observations=[{'t_s': 999., 'ap_c': 999.}])
        observed['requests'][0].update(actual_arrival_s=999., response_s=999., route='CPU')
        contract, reason = subject.resolve_ORDER_contract(observed, document(), dataset_pin())
        self.assertIsNone(reason)
        self.assertEqual(contract['policy'], 'EDD')
        self.assertEqual(contract['validation_execution'], 'ATOMIC_PROTOCOL_GLOBAL_SERIAL')
        self.assertFalse(contract['installed_verified'])

    def test_missing_explicit_public_fields_remain_UNKNOWN_no_fallback(self):
        for field in ('public_order', 'public_route', 'protocol'):
            observed = source()
            del observed[field]
            with self.subTest(field=field):
                contract, reason = subject.resolve_ORDER_contract(observed, document(), dataset_pin())
                self.assertIsNone(contract)
                self.assertIn('UNKNOWN_MISSING_EXPLICIT_PUBLIC', reason)

    def test_contradictory_public_contract_or_plan_is_UNKNOWN(self):
        for field, value in (('public_order', 'FIFO'), ('public_route', 'C_CPU'), ('protocol', 'CG_DC'),
                             ('public_declared_protocol', 'CG_DC'), ('cohort_id', 'WRONG'), ('session_id', 'WRONG'),
                             ('device', 'S26'), ('requests', [])):
            observed = source()
            observed[field] = value
            with self.subTest(field=field):
                contract, reason = subject.resolve_ORDER_contract(observed, document(), dataset_pin())
                self.assertIsNone(contract)
                self.assertIn('UNKNOWN', reason)

    def test_document_cannot_change_policy_routes_dataset_or_installed_claim(self):
        for field, value in (('policy', 'FIFO_SERIAL_CG'), ('classification_route', 'CPU'),
                             ('installed_verified', True), ('scheduler_body_verified', True)):
            proof = document()
            proof['contracts'][0][field] = value
            with self.subTest(field=field), self.assertRaises(RuntimeError):
                subject.validate_contract_document(proof, dataset_pin())
        proof = document()
        proof['original_dataset_pin']['sha256'] = 'c' * 64
        with self.assertRaises(RuntimeError):
            subject.validate_contract_document(proof, dataset_pin())

    def test_public_ORDER_overrides_incorrect_declared_FIFO_mapping_only(self):
        original = subject.v3.exact_measured_policy
        decisions = []
        with subject.contract_callbacks(operation(), document(), decisions, []):
            self.assertEqual(subject.v3.exact_measured_policy(source(), operation()), ('EDD', None))
            self.assertEqual(subject.v3.exact_measured_policy(source('BASE'), operation()), ('FIFO_SERIAL_CG', None))
            self.assertEqual(subject.v3.exact_measured_policy(source('PAIR_G'), operation()), ('FIFO_PAIR_CG', None))
        self.assertIs(subject.v3.exact_measured_policy, original)
        self.assertEqual(len(decisions), 3)

    def test_EDD_earlier_deadline_wins_and_fixed_route_filter_blocks_CPU_C(self):
        rows = {'C': {'request_id': 'C', 'ordinal': 0, 'task': 'C', 'priority': 'U', 'group': 0,
                      'scheduled_arrival_ns': 0, 'queue_entry_ns': 0, 'deadline_ns': 20, 'context': {}},
                'D': {'request_id': 'D', 'ordinal': 1, 'task': 'D', 'priority': 'N', 'group': 0,
                      'scheduled_arrival_ns': 1, 'queue_entry_ns': 1, 'deadline_ns': 10, 'context': {}}}
        model = SimpleNamespace(nominal=lambda context, task, route, **kwargs: {'response_ns': 1, 'occupancy_ns': 5})
        public = {'queue': list(rows.values()), 'owners': [], 'now_ns': 2}
        with subject.ORDER_execution(model):
            action = protocol_simulator._rule_action('EDD', public, rows, model, 'READY_QUEUE', None)
            self.assertEqual(action['request_id'], 'D')
            self.assertEqual(action['route'], 'CPU')
            with self.assertRaises(UnsupportedContext):
                model.nominal({}, 'C', 'CPU')
            self.assertEqual(model.nominal({}, 'C', 'GPU')['occupancy_ns'], 5)

    def test_ORDER_callback_uses_original_atomic_executor_and_restores(self):
        model, decisions, completed = dummy_model(), [], []
        original_nominal = model.nominal
        fake_simulate = lambda template, timing, policy='ATC', **kwargs: {'policy': policy, **kwargs}
        with patch.object(subject.v3, 'predict_case', fake_predict), patch.object(protocol_simulator, 'simulate_protocol', fake_simulate):
            with subject.contract_callbacks(operation(), document(), decisions, completed):
                result, compact = subject.v3.predict_case({'policy': 'EDD', 'label': 'ORDER'}, model, {}, {}, operation(),
                                {'start_id': 'SEALED'}, validation_source=source())
                self.assertTrue(compact['C_CPU_blocked'])
                self.assertEqual(compact['sim']['concurrency_mode'], 'ATOMIC_PROTOCOL')
                self.assertEqual(compact['sim']['policy'], 'EDD')
                self.assertEqual(compact['source_policy_contract']['executor'], 'ATOMIC_PROTOCOL_GLOBAL_SERIAL')
                self.assertIs(protocol_simulator.simulate_protocol, fake_simulate)
                self.assertIs(model.nominal, original_nominal)
            self.assertIs(subject.v3.predict_case, fake_predict)
        self.assertEqual(len(completed), 1)

    def test_novel_callback_retains_original_progress_and_route_choices(self):
        model = dummy_model()
        fake_simulate = lambda template, timing, policy='ATC', **kwargs: {'policy': policy, **kwargs}
        with patch.object(subject.v3, 'predict_case', fake_predict), patch.object(protocol_simulator, 'simulate_protocol', fake_simulate):
            with subject.contract_callbacks(operation(), document(), [], []):
                result, compact = subject.v3.predict_case({'policy': 'ATC', 'label': 'NOVEL'}, model, {}, {}, operation(), {'start_id': 'SEALED'})
                self.assertFalse(compact['C_CPU_blocked'])
                self.assertEqual(compact['sim']['concurrency_mode'], 'DATA_DERIVED_PROGRESS')
                self.assertEqual(compact['source_policy_contract']['schedule_role'], 'GENERALIZED_NOVEL_COUNTERFACTUAL')
                self.assertFalse(compact['source_policy_contract']['novel_policy_route_admission_WAIT_behavior_changed'])

    def test_PAIR_G_keeps_rolling_without_atomic_samegroup_assumption(self):
        fake_simulate = lambda template, timing, policy='ATC', **kwargs: {'policy': policy, **kwargs}
        with patch.object(subject.v3, 'predict_case', fake_predict), patch.object(protocol_simulator, 'simulate_protocol', fake_simulate):
            with subject.contract_callbacks(operation(), document(), [], []):
                result, compact = subject.v3.predict_case({'policy': 'FIFO_PAIR_CG', 'label': 'PAIR'}, dummy_model(), {}, {}, operation(),
                                {'start_id': 'SEALED'}, validation_source=source('PAIR_G'))
                self.assertEqual(compact['sim']['concurrency_mode'], 'DATA_DERIVED_PROGRESS')
                meta = compact['source_policy_contract']
                self.assertFalse(meta['PAIR_G_atomic_or_same_group_assumption_added'])
                self.assertFalse(meta['EXACT_INSTALLED'])
                self.assertTrue(meta['SCHEDULER_BODY_NOT_VERIFIED'])

    def test_exception_restores_all_callback_and_nominal_objects(self):
        model = dummy_model()
        original_nominal = model.nominal
        original_policy = subject.v3.exact_measured_policy
        original_guard = subject.v3.process_guard
        original_support = subject.v3._select_redispatch
        fake_simulate = lambda *args, **kwargs: None
        def failure(*args, **kwargs):
            raise ValueError('SEALED_SYNTHETIC_FAILURE')
        with patch.object(subject.v3, 'predict_case', failure), patch.object(protocol_simulator, 'simulate_protocol', fake_simulate):
            with self.assertRaises(ValueError):
                with subject.contract_callbacks(operation(), document(), [], []):
                    subject.v3.predict_case({'policy': 'EDD', 'label': 'ORDER'}, model, {}, {}, operation(),
                                            {'start_id': 'SEALED'}, validation_source=source())
            self.assertIs(subject.v3.predict_case, failure)
            self.assertIs(subject.v3.exact_measured_policy, original_policy)
            self.assertIs(subject.v3.process_guard, original_guard)
            self.assertIs(subject.v3._select_redispatch, original_support)
            self.assertIs(protocol_simulator.simulate_protocol, fake_simulate)
            self.assertIs(model.nominal, original_nominal)

    def test_UNKNOWN_ORDER_is_rejected_before_any_callback(self):
        observed = source()
        observed['public_order'] = None
        calls = []
        with patch.object(subject.v3, 'predict_case', lambda *args, **kwargs: calls.append(True)):
            with subject.contract_callbacks(operation(), document(), [], []):
                self.assertIsNone(subject.v3.exact_measured_policy(observed, operation())[0])
                with self.assertRaises(RuntimeError):
                    subject.v3.predict_case({'policy': 'EDD', 'label': 'ORDER'}, dummy_model(), {}, {}, operation(),
                                            {'start_id': 'SEALED'}, validation_source=observed)
        self.assertEqual(calls, [])

    def test_frozen_V3_preserved_and_test_discovery_is_dedicated(self):
        self.assertEqual(subject.sha(Path(subject.v3.__file__)), subject.V3_SOURCE_SHA256)
        self.assertIn("pattern='test_contract_forecast.py'", inspect.getsource(subject.main))
        self.assertNotIn('simulate_protocol(', inspect.getsource(subject.main))
        self.assertNotIn('build_timing_candidate(', inspect.getsource(subject.main))
        self.assertEqual(subject.v3.VERSION, 'A24-REGISTERED-RULE-FORECAST-v1')

    def test_internal_guard_delegates_exact_actual_entry_and_same_known_PS_roster(self):
        seen, known = [], ['SEALED_KNOWN_PS']
        def original_guard(entry, known_ps=()):
            seen.append((entry, known_ps))
            return {'sealed_guard': True}
        with patch.object(subject.v3, 'process_guard', original_guard):
            with subject.contract_callbacks(operation(), document(), [], []):
                self.assertEqual(subject.v3.process_guard(subject.v3.__file__, known), {'sealed_guard': True})
                self.assertEqual(seen[0][0], subject.__file__)
                self.assertIs(seen[0][1], known)
                with self.assertRaises(RuntimeError):
                    subject.v3.process_guard('DIFFERENT_ENTRY.py', known)
            self.assertIs(subject.v3.process_guard, original_guard)
        self.assertEqual(len(seen), 1)

    def test_ORDER_gap_diagnostic_uses_only_same_fixed_routes_SERIAL_support(self):
        model, seen = dummy_model(), []
        template, case, op = {'public': 'SEALED'}, {'policy': 'EDD'}, operation()
        def original_support(timing, public, policy, selected_case, selected_op):
            seen.append((timing, public, policy, selected_case, selected_op))
            return {'mode': 'MEASURED', 'zero_baseline_id': None}
        with patch.object(subject.v3, '_select_redispatch', original_support):
            with subject.ORDER_execution(model):
                result = subject.v3._select_redispatch(model, template, 'EDD', case, op)
                self.assertEqual(result['mode'], 'MEASURED')
                self.assertEqual(result['source_policy_support_scope'], 'ORDER_EDD_FIXED_CG_GLOBAL_SERIAL')
                self.assertEqual(seen, [(model, template, 'FIFO_SERIAL_CG', case, op)])
            self.assertIs(subject.v3._select_redispatch, original_support)


if __name__ == '__main__':
    unittest.main()
