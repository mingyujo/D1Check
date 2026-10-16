"""V3 pure overlay fixtures. No simulator, fit, archive, HTTP or device call.

The registered entry discovers only this new file. Prior V2's 23 registered
tests and their exact source remain preserved; no actual forecast is invoked.
"""
from __future__ import annotations

import copy
import inspect
from pathlib import Path
import unittest

import forecast_overlay_run as forecast
import forecast_run as preserved


def original_pin():
    return {'path': str(forecast.WORK / 'SEALED_SYNTHETIC_ORIGINAL.json'),
            'sha256': forecast.ORIGINAL_DATASET_SHA256, 'bytes': 1024}


def synthetic_inputs():
    sessions, records = [], []
    for index, sid in enumerate(sorted(forecast.INITIAL_DEV8_IDS)):
        bank = ('C252', 'L64', 'M128')[index % 3]
        reference = {'dataset_sha256': '0' * 64, 'json_pointer': '/sessions/' + str(index) + '/provenance',
                     'value_sha256': str(index) * 64}
        session = {'session_id': sid, 'cohort_id': forecast.INITIAL_DEV8_COHORT,
                   'source_family': 'm8', 'source_generation': 'SEALED_SYNTHETIC', 'device': 'A24',
                   'bank': None, 'protocol': 'SERIAL', 'initial_ap_c': 35. + index,
                   'initial_ap_time_s': -1., 'initial_ap_hi_s': -1., 'forecast_origin_s': 0.,
                   'prehistory_start_s': -10., 'ambient_c': None,
                   'compatibility': {'ap_activity_domain': 'SEALED_DOMAIN', 'bank_sha256': '8' * 64},
                   'activity_coverage_s': [-10., 12.], 'target_eligibility': {'timing_fit': True, 'ap_fit': True},
                   'observations': [{'channel': 'AP', 't_s': -1., 'lo_s': -1.1, 'hi_s': -1.,
                                     'ap_c': 35., 'initial_eligible': True},
                                    {'channel': 'AP', 't_s': 5., 'hi_s': 5.1, 'ap_c': 99.}],
                   'owner_intervals': [{'start_s': 1., 'end_s': 2., 'task': 'C', 'route': 'GPU',
                                        'request_id': 'MEASURED_C'}],
                   'requests': [{'request_id': 'MEASURED_C', 'ordinal': 0, 'task': 'C', 'priority': 'U',
                                 'scheduled_arrival_s': 1., 'deadline_s': 3., 'dispatch_s': 1.1,
                                 'response_s': 1.8, 'phases_s': [0.1] * 5}],
                   'provenance': {'saved_full_reference': reference}, 'extra_preserved': {'future': [1, None]}}
        sessions.append(session)
        records.append({'session_id': sid, 'cohort_id': forecast.INITIAL_DEV8_COHORT, 'old_bank': None,
                        'bank': bank, 'provenance_reference': copy.deepcopy(reference),
                        'public_recipe': {'session_id': sid, 'bank': bank, 'source_member': 'sealed/public.json',
                                          'source_sha256': 'a' * 64, 'crc_verified': True},
                        'development_proof': {'session_id': sid, 'bank': bank, 'source_path': 'sealed/DEV_PROFILE.json',
                                              'source_sha256': 'b' * 64, 'role': 'DEVELOPMENT'}})
    sessions.append({'session_id': 'UNCHANGED_OLD', 'cohort_id': 'OLD', 'source_family': 'old', 'bank': None,
                     'requests': [], 'observations': [], 'initial_ap_c': None})
    dataset = {'schema': 'SEALED_SYNTHETIC', 'sessions': sessions, 'other': {'unchanged': [None, 1.]}}
    overlay = {'schema': forecast.OVERLAY_VERSION, 'original_dataset_pin': original_pin(), 'records': records}
    return dataset, overlay


def apply(dataset, overlay):
    return forecast.apply_timing_bank_overlay(dataset, overlay, original_pin(), 'c' * 64)


def operation(mode='FORECAST_TEST'):
    dependencies = ('forecast_overlay_run.py', 'forecast_run.py', 'runtime_guard.py', 'timing_model.py',
                    'protocol_simulator.py', 'thermal_model.py', 'historical_observer.py', 'test_overlay_forecast.py')
    pins = [{'path': str(forecast.WORK / name),
             'sha256': forecast.V2_SOURCE_SHA256 if name == 'forecast_run.py' else 'd' * 64}
            for name in dependencies]
    return {'mode': mode, 'worker_lock_path': str(forecast.WORKER_LOCK), 'protected_pins': [{}] * 351,
            'source_pins': pins, 'new_environment': 0, 'HTTP': 0, 'device_commands': 0, 'automatic_retry': False}


class OverlayForecastTests(unittest.TestCase):
    def test_exact_eight_bank_only_copy_preserves_original_and_AP_inputs(self):
        dataset, overlay = synthetic_inputs()
        snapshot = copy.deepcopy(dataset)
        effective, proof = apply(dataset, overlay)
        self.assertEqual(dataset, snapshot)
        self.assertIsNot(effective, dataset)
        self.assertEqual(forecast.nonbank_dataset_projection(effective), forecast.nonbank_dataset_projection(dataset))
        self.assertEqual(forecast.thermal_input_projection(effective['sessions']), forecast.thermal_input_projection(dataset['sessions']))
        expected = {r['session_id']: r['bank'] for r in overlay['records']}
        self.assertEqual({s['session_id']: s['bank'] for s in effective['sessions'][:-1]}, expected)
        self.assertEqual(effective['sessions'][-1], dataset['sessions'][-1])
        self.assertEqual(proof['amended_sessions'], 8)
        self.assertEqual(proof['nonbank_dataset_before_sha256'], proof['nonbank_dataset_after_sha256'])
        self.assertEqual(proof['thermal_input_before_sha256'], proof['thermal_input_after_sha256'])
        self.assertNotEqual(proof['bank_map_before_sha256'], proof['effective_bank_map_sha256'])
        self.assertEqual(proof['data_original_sha256'], forecast.ORIGINAL_DATASET_SHA256)
        self.assertEqual(proof['new_AP_fit'], 0)
        self.assertFalse(proof['raw_CRC_reverified_here'])

    def test_wrong_original_dataset_path_SHA_or_bytes_rejected(self):
        for field, value in (('path', str(forecast.WORK / 'WRONG.json')), ('sha256', 'e' * 64), ('bytes', 999)):
            dataset, overlay = synthetic_inputs()
            overlay['original_dataset_pin'][field] = value
            with self.subTest(field=field), self.assertRaises(RuntimeError):
                apply(dataset, overlay)

    def test_exact_roster_and_native_cohort_conservation(self):
        for mode in ('missing', 'duplicate', 'replacement', 'cohort', 'source', 'device'):
            dataset, overlay = synthetic_inputs()
            if mode == 'missing':
                overlay['records'].pop()
            elif mode == 'duplicate':
                overlay['records'][-1] = copy.deepcopy(overlay['records'][0])
            elif mode == 'replacement':
                overlay['records'][0]['session_id'] = 'NOT_REGISTERED'
            elif mode == 'cohort':
                dataset['sessions'][0]['cohort_id'] = 'DIFFERENT'
            elif mode == 'source':
                dataset['sessions'][0]['source_family'] = 'old'
            else:
                dataset['sessions'][0]['device'] = 'S26'
            with self.subTest(mode=mode), self.assertRaises(RuntimeError):
                apply(dataset, overlay)

    def test_only_explicit_null_session_bank_can_be_filled(self):
        for mode in ('non_null', 'absent', 'non_null_old_proof', 'unknown_new_bank'):
            dataset, overlay = synthetic_inputs()
            if mode == 'non_null':
                dataset['sessions'][0]['bank'] = overlay['records'][0]['bank']
            elif mode == 'absent':
                del dataset['sessions'][0]['bank']
            elif mode == 'non_null_old_proof':
                overlay['records'][0]['old_bank'] = 'M128'
            else:
                overlay['records'][0]['bank'] = 'UNREGISTERED'
            with self.subTest(mode=mode), self.assertRaises(RuntimeError):
                apply(dataset, overlay)

    def test_explicit_request_bank_conflict_is_rejected_never_overwritten(self):
        dataset, overlay = synthetic_inputs()
        dataset['sessions'][0]['requests'][0]['bank'] = 'DIFFERENT'
        with self.assertRaises(RuntimeError):
            apply(dataset, overlay)
        self.assertEqual(dataset['sessions'][0]['requests'][0]['bank'], 'DIFFERENT')

    def test_explicit_request_bank_matching_or_null_is_preserved(self):
        dataset, overlay = synthetic_inputs()
        dataset['sessions'][0]['requests'][0]['bank'] = overlay['records'][0]['bank']
        dataset['sessions'][1]['requests'][0]['bank'] = None
        effective, proof = apply(dataset, overlay)
        self.assertEqual(effective['sessions'][0]['requests'], dataset['sessions'][0]['requests'])
        self.assertIsNone(effective['sessions'][1]['requests'][0]['bank'])
        self.assertEqual(sum(r['explicit_null_request_bank_retained'] for r in proof['changes']), 1)

    def test_public_recipe_and_DEVELOPMENT_must_agree_on_bank_and_ID(self):
        for section, field, value in (('public_recipe', 'bank', 'DIFFERENT'),
                                      ('public_recipe', 'session_id', 'DIFFERENT'),
                                      ('public_recipe', 'crc_verified', False),
                                      ('public_recipe', 'source_sha256', 'missing'),
                                      ('development_proof', 'bank', 'DIFFERENT'),
                                      ('development_proof', 'session_id', 'DIFFERENT'),
                                      ('development_proof', 'role', 'CONFIRMATION'),
                                      ('development_proof', 'source_sha256', None)):
            dataset, overlay = synthetic_inputs()
            overlay['records'][0][section][field] = value
            with self.subTest(section=section, field=field), self.assertRaises(RuntimeError):
                apply(dataset, overlay)

    def test_original_compact_provenance_binding_required(self):
        dataset, overlay = synthetic_inputs()
        overlay['records'][0]['provenance_reference']['value_sha256'] = 'e' * 64
        with self.assertRaises(RuntimeError):
            apply(dataset, overlay)

    def test_projection_preserves_AP_domains_owners_initials_labels_and_any_unlisted_field(self):
        dataset, _ = synthetic_inputs()
        before = forecast.digest(forecast.thermal_input_projection(dataset['sessions']))
        for field, value in (('initial_ap_c', 12.), ('initial_ap_hi_s', 5.),
                             ('compatibility', {'ap_activity_domain': 'DIFFERENT'}),
                             ('owner_intervals', []), ('observations', []),
                             ('cohort_id', 'DIFFERENT'), ('session_id', 'DIFFERENT')):
            changed = copy.deepcopy(dataset)
            changed['sessions'][0][field] = value
            with self.subTest(field=field):
                self.assertNotEqual(before, forecast.digest(forecast.thermal_input_projection(changed['sessions'])))
        changed = copy.deepcopy(dataset)
        changed['sessions'][0]['extra_preserved']['future'][0] = 9
        self.assertNotEqual(forecast.digest(forecast.nonbank_dataset_projection(dataset)),
                            forecast.digest(forecast.nonbank_dataset_projection(changed)))

    def test_V2_scientific_functions_and_classes_are_textually_unchanged(self):
        functions = ('digest', '_support_fingerprints', 'install_lookup_cache', 'lookup_cache_report', '_path_key',
                     '_integer', '_finite', '_ns', '_window_ns', '_declared_model', 'public_template',
                     'transform_public_template', 'custom_public_template', 'timing_template', 'build_cases',
                     'LedgerSnapshot', 'budget_arithmetic', '_ledger_rows', 'ForecastBudgetGuard', '_child',
                     '_bytes_new', 'ForecastJournal', 'FixedObserverBudget', 'generated_activity',
                     'historical_mobile_comparator', '_ap_times', '_select_redispatch', '_quantile',
                     'deadline_summary', 'ap_summary', 'work_scope', 'predict_case', 'score_ap_validation',
                     '_maybe_ns', '_actual_response', 'actual_deadline_summary', 'score_validation_trace',
                     'selected_cv_context', 'exact_measured_policy', 'cv_residual_bands', 'effect_rows',
                     'case_status', 'sample_input')
        for name in functions:
            with self.subTest(name=name):
                self.assertEqual(inspect.getsource(getattr(forecast, name)), inspect.getsource(getattr(preserved, name)))
        self.assertEqual(forecast.sha(Path(preserved.__file__)), forecast.V2_SOURCE_SHA256)

    def test_test_operation_requires_new_entry_and_overlay_fixture_source_pins(self):
        op = operation()
        forecast._validate_operation(op)
        for missing in ('forecast_overlay_run.py', 'forecast_run.py', 'test_overlay_forecast.py'):
            changed = copy.deepcopy(op)
            changed['source_pins'] = [p for p in changed['source_pins'] if Path(p['path']).name != missing]
            with self.subTest(missing=missing), self.assertRaises(RuntimeError):
                forecast._validate_operation(changed)
        wrong = copy.deepcopy(op)
        next(p for p in wrong['source_pins'] if Path(p['path']).name == 'forecast_run.py')['sha256'] = 'f' * 64
        with self.assertRaises(RuntimeError):
            forecast._validate_operation(wrong)

    def test_entry_discovers_only_new_overlay_fixtures_and_has_no_physics_call(self):
        text = inspect.getsource(forecast.main)
        self.assertIn("pattern='test_overlay_forecast.py'", text)
        self.assertNotIn("pattern='test_forecast_run.py'", text)
        helper = inspect.getsource(forecast.apply_timing_bank_overlay)
        for forbidden in ('simulate_protocol(', 'build_timing_candidate(', 'thermal_model.fit(', 'thermal_model.features(', 'ZipFile('):
            self.assertNotIn(forbidden, helper)
        self.assertIn('timing_bank_overlay_pin', forecast.description()['required_inputs'])


if __name__ == '__main__':
    unittest.main()
