"""One-shot registered local stages; no scheduler, network, or device launcher."""
from __future__ import annotations

import argparse
import ast
import io
from pathlib import Path
import sys
import traceback
import unittest

from runtime_guard import (FitBudget, canonical, operation, pin, read, sha,
                           write_new)

WORK = Path(__file__).resolve().parent


def test_sources(op, out):
    # Compile every registered Python source without importing external runners.
    compiled = []
    for spec in op['source_pins']:
        path = pin(spec)
        if path.suffix == '.py':
            compile(path.read_bytes(), str(path), 'exec')
            compiled.append(str(path))
    write_new(out / 'COMPILE.json', {'status': 'PASS', 'sources': compiled,
                                    'raw_data_access': 0, 'fits': 0, 'new_environment': 0})
    suite = unittest.TestLoader().discover(str(WORK), pattern='test_*.py')
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    write_new(out / 'TEST_RESULT.json', {'status': 'PASS' if result.wasSuccessful() else 'FAIL',
        'testsRun': result.testsRun, 'errors': [(str(t), e) for t,e in result.errors],
        'failures': [(str(t),e) for t,e in result.failures], 'skipped': [(str(t),e) for t,e in result.skipped],
        'output': stream.getvalue(), 'actual_raw_data_access': 0, 'new_environment': 0})
    if not result.wasSuccessful():
        raise RuntimeError('Registered synthetic suite failed; preserve namespace and inspect evidence')


def inventory_stage(op, out):
    import old_data
    import m8_data
    old = old_data.inventory(op['base'])
    incoming = m8_data.inventory_from_audits(op['m8']['audit_sources'])
    roster = m8_data.roster_from_metadata(op['m8']['metadata_sources'])
    declared = op['m8']['default_clock_contract']
    # A clock contract is a recorded-coordinate hypothesis, not proof of installed code.
    keys = list(roster)
    if isinstance(roster, dict) and 'sessions' in roster:
        entries = roster['sessions']
        keys = list(entries) if isinstance(entries, dict) else [x['session_id'] for x in entries]
    overrides = op['m8'].get('clock_overrides', {})
    contracts = {key: dict(overrides.get(key, overrides.get(roster.get(key, {}).get('family'), declared)))
                 for key in keys}
    specs = m8_data.build_session_specs(incoming, roster, contracts)
    write_new(out / 'OLD_INVENTORY.json', old)
    write_new(out / 'M8_MEMBER_INVENTORY.json', incoming)
    write_new(out / 'M8_ROSTER.json', roster)
    write_new(out / 'M8_SESSION_SPECS.json', specs)
    write_new(out / 'INVENTORY_RESULT.json', {'status': 'SAVED_METADATA_INVENTORY_COMPLETE',
        'raw_ZIP_payloads_opened': 0, 'new5_outcomes_opened': 0,
        'model_fits': 0, 'new_environment': 0,
        'old_inventory_sha256': sha(out/'OLD_INVENTORY.json'),
        'M8_specs_sha256': sha(out/'M8_SESSION_SPECS.json')})


def archive_index_stage(op, out):
    from archive_index import index_archives
    reports = index_archives(op['archives'], op['expanded_byte_cap'], op['member_cap'])
    write_new(out/'ARCHIVE_AUDITS.json', reports)
    write_new(out/'INDEX_RESULT.json', {'status':'OPAQUE_MEMBER_HASH_INDEX_COMPLETE',
        'archives':len(reports),'members':sum(x['members'] for x in reports),
        'new_semantic_payloads_parsed':0,'new_environment':0,'model_fits':0,
        'prior_CRC_receipts_modified':False})


def extract_stage(op, out):
    import old_data
    import m8_data
    m8_operation = dict(op['m8_extraction'])
    if 'sessions_pin' in m8_operation:
        session_specs = read(pin(m8_operation.pop('sessions_pin')))
        m8_operation['sessions'] = session_specs['sessions']
    older = old_data.extract(op['base'], raw_root_aliases=op.get('raw_root_aliases'))
    recent = m8_data.extract(m8_operation)
    write_new(out/'OLD_DATASET.json', older)
    write_new(out/'M8_DATASET.json', recent)
    sessions, by_sid = [], {}
    for source in (older, recent):
        for row in source['sessions']:
            sid = row['session_id']
            if sid in by_sid:
                raise ValueError('Duplicate session across historical/new dataset: ' + sid)
            by_sid[sid] = row
            sessions.append(row)
    write_new(out/'DATASET.json', {'schema':'A24-all-received-standardized-dataset-v1',
        'sessions': sessions, 'status':'OBSERVED_DEVELOPMENT_DATA_NOT_FRESH_CONFIRMATION',
        'sources': {'older_sha256':sha(out/'OLD_DATASET.json'), 'recent_sha256':sha(out/'M8_DATASET.json')},
        'all_received_scope_inventory': op['m8_extraction'].get('inventory_scope'),
        'measured_J': None, 'energy_error_J': None, 'quality_GT_verified':False,
        'original40_independent_success_increment':0})
    write_new(out/'DATASET_RESULT.json', {'status':'EXTRACTION_COMPLETE',
        'sessions':len(sessions), 'old_sessions':len(older['sessions']),
        'm8_sessions':len(recent['sessions']),
        'dataset_sha256':sha(out/'DATASET.json'), 'model_fits':0, 'new_environment':0,
        'HTTP':0, 'device_commands':0, 'source_originals_modified':0})


def fit_cv_stage(op, out):
    import thermal_model
    import timing_model
    from historical_observer import conditional_energy, load_models, observe_ap
    from analysis_metrics import saved_schedule_description
    dataset = read(pin(op['dataset_pin']))
    sessions = dataset['sessions']
    budget = FitBudget(op['fit_cap'], out)
    cv = thermal_model.cross_validate(sessions, candidates=op['thermal_candidates'],
                                     on_fit=budget.consume)
    write_new(out/'THERMAL_CV.json', cv)
    write_new(out/'THERMAL_SELECTION.json', {'selection':cv['selection'],
        'candidate_grid':op['thermal_candidates'], 'dataset_sha256':op['dataset_pin']['sha256'],
        'role':'POSTHOC_DEVELOPMENT_SELECTION_NOT_FRESH_CONFIRMATION',
        'policy_difference_not_selection_criterion':True})
    timing = timing_model.grouped_validate_timing(sessions, op['timing_candidates'],
                                                build_cap=op['timing_build_cap'])
    write_new(out/'TIMING_CV.json', timing)
    models = load_models()
    descriptions, observers = [], []
    observer_count = 0
    for session in sessions:
        descriptions.append(saved_schedule_description(session))
        try:
            energy = conditional_energy(session, models['profile'])
        except (ValueError, KeyError, TypeError) as exc:
            energy = {'status':'UNQUALIFIED_OWNER_STATE', 'reason':str(exc), 'measured_J':None}
        old_ap = []
        for model_name in ('TREND27', 'MEASURED35'):
            if observer_count >= op['historical_cost_observer_cap']:
                raise RuntimeError('Registered historical observer cap exhausted')
            observer_count += 1
            try:
                old_ap.append(observe_ap(session, models, model_name))
            except (ValueError, KeyError, TypeError) as exc:
                old_ap.append({'status':'UNKNOWN_ORIGINAL_MODEL_CONTEXT', 'reason':str(exc),
                               'historical_model':model_name, 'predictions':[], 'MAE_C':None})
        observers.append({'session_id':session['session_id'], 'conditional_energy':energy,
                          'historical_AP':old_ap})
    write_new(out/'OBSERVED_SCHEDULES.json', descriptions)
    write_new(out/'HISTORICAL_OBSERVERS.json', observers)
    write_new(out/'FIT_RESULT.json', {'status':'GROUPED_DEVELOPMENT_FITS_COMPLETE',
        'fit_budget':budget.summary(), 'historical_cost_observers':observer_count,
        'dataset_sha256':op['dataset_pin']['sha256'], 'selection_sha256':sha(out/'THERMAL_SELECTION.json'),
        'new_environment':0, 'NN':0, 'optimizer':0, 'actual_J':None,
        'fresh_confirmation':False, 'physical_goal_pass':False})


def final_fit_stage(op, out):
    import thermal_model
    dataset = read(pin(op['dataset_pin']))
    cv = read(pin(op['thermal_cv_pin']))
    selection = read(pin(op['thermal_selection_pin']))
    if selection['dataset_sha256'] != op['dataset_pin']['sha256'] or selection['selection'] != cv['selection']:
        raise ValueError('Final model selection/dataset/CV binding differs')
    dataset_ids = {s['session_id'] for s in dataset['sessions']}
    for fold in cv['folds'].get('folds', []):
        if set(fold['training_session_ids']) | set(fold['heldout_session_ids']) != dataset_ids:
            raise ValueError('Final fit dataset and CV roster differ')
    budget = FitBudget(op['fit_cap'], out)
    result = thermal_model.fit_selected(dataset['sessions'], cv, on_fit=budget.consume)
    write_new(out/'THERMAL_MODELS.json', result)
    write_new(out/'FIT_RESULT.json', {'status':result['status'], 'fit_budget':budget.summary(),
        'new_environment':0, 'measured_J':None, 'fresh_confirmation':False,
        'selection_sha256':op['thermal_selection_pin']['sha256']})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--operation', required=True)
    args = parser.parse_args()
    with operation(args.operation, __file__) as (op, out):
        functions = {'TEST':test_sources, 'ARCHIVE_INDEX':archive_index_stage, 'INVENTORY':inventory_stage,
                     'EXTRACT':extract_stage, 'FIT_CV':fit_cv_stage, 'FINAL_FIT':final_fit_stage}
        if op['mode'] not in functions:
            raise ValueError('Unregistered stage mode')
        functions[op['mode']](op, out)
    print(canonical({'status':'COMPLETE', 'mode':op['mode'], 'output':str(out)}))


if __name__ == '__main__':
    main()
