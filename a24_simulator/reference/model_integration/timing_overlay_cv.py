"""Saved-only INITIAL_DEV8 bank overlay timing CV, with bounded build receipts.

The original grouped_validate_timing function, candidate order, folds, lookup
semantics, latent selection, scores and original result are preserved. Only the
registered bank labels and the separately tested exact instance-local lookup
cache differ. No AP fit, neural training or simulator/environment START exists.
Import is inert; only the root may register and execute a fresh operation.
"""
from __future__ import annotations

import argparse
import contextlib
import copy
import io
from pathlib import Path
import unittest

from runtime_guard import append, canonical, now, operation, pin, read, require, sha, write_new
from forecast_overlay_run import (INITIAL_DEV8_IDS, ORIGINAL_DATASET_SHA256, V2_SOURCE_SHA256,
                                 WORK, WORKER_LOCK, _path_key, apply_timing_bank_overlay,
                                 digest, install_lookup_cache, lookup_cache_report)

VERSION = 'A24-TIMING-BANK-OVERLAY-CACHED-CV-v1'
MODES = ('TIMING_OVERLAY_CV', 'TIMING_OVERLAY_CV_TEST')
TOTAL_BUILD_CAP = 512


class TimingBuildJournal:
    """Every model-build attempt consumes its START even if it fails."""
    def __init__(self, out, *, operation_sha256, prior_builds, new_cap, total_cap):
        require(type(prior_builds) is int and prior_builds > 0,
                'Positive original artifact-certified timing builds required')
        require(type(new_cap) is int and new_cap == prior_builds and
                type(total_cap) is int and total_cap == TOTAL_BUILD_CAP and
                prior_builds + new_cap <= total_cap, 'Exact original-definition new / shared512 timing-build caps required')
        self.path = Path(out) / 'timing_build_receipts.jsonl'
        with self.path.open('xb') as handle:
            handle.flush()
            import os
            os.fsync(handle.fileno())
        self.operation_sha256, self.prior, self.cap, self.total = operation_sha256, prior_builds, new_cap, total_cap
        self.used, self.completed, self.failed = 0, 0, 0

    def start(self, configuration, training, excluded_cohorts):
        require(self.used < self.cap and self.prior + self.used < self.total, 'Timing build START cap exhausted')
        self.used += 1
        identity = 'A24_TIMING_BANK_OVERLAY_' + self.operation_sha256[:16] + '_' + str(self.used).zfill(3)
        append(self.path, {'event': 'START', 'identity': identity, 'index': self.used, 'utc': now(),
                          'operation_sha256': self.operation_sha256, 'configuration': configuration,
                          'training_session_ids_sha256': digest(sorted(s['session_id'] for s in training)),
                          'training_cohort_ids_sha256': digest(sorted({s['cohort_id'] for s in training})),
                          'excluded_cohorts': excluded_cohorts, 'prior_artifact_certified_builds': self.prior,
                          'total_timing_builds_after_START': self.prior + self.used, 'total_cap': self.total,
                          'new_build_cap': self.cap, 'simulation_START_consumed': 0, 'automatic_retry': False})
        return identity

    def complete(self, identity, model_digest):
        self.completed += 1
        append(self.path, {'event': 'COMPLETE', 'identity': identity, 'utc': now(), 'model_digest': model_digest,
                          'simulation_START_consumed': 0})

    def fail(self, identity, error):
        self.failed += 1
        append(self.path, {'event': 'FAIL', 'identity': identity, 'utc': now(), 'error_type': type(error).__name__,
                          'error': str(error), 'build_START_remains_consumed': True, 'automatic_retry': False,
                          'simulation_START_consumed': 0})

    def summary(self):
        return {'prior_artifact_certified_timing_builds': self.prior, 'new_model_build_START_consumed': self.used,
                'new_model_build_COMPLETE': self.completed, 'new_model_build_FAIL': self.failed,
                'total_timing_builds_consumed': self.prior + self.used, 'new_build_cap': self.cap,
                'total_build_cap': self.total, 'receipt_path': str(self.path), 'receipt_sha256': sha(self.path),
                'FAIL_is_consumed': True, 'simulation_START_consumed': 0, 'parameter_fits': 0, 'AP_fits': 0, 'NN': 0}


@contextlib.contextmanager
def cached_registered_builds(timing_module, sessions, journal, cache_reports):
    """Wrap only the original builder; restore it even on a failed build/CV.

    The frozen CV calls its own original function and receives the exact same
    model object after cache installation. All original support rows remain in
    place/order; cache reports must prove unchanged support at the fold end.
    """
    original = timing_module.build_timing_candidate
    cohorts = {s['cohort_id'] for s in sessions}
    active_model = None
    def finish_previous():
        nonlocal active_model
        if active_model is not None:
            cache_reports.append(lookup_cache_report(active_model))
            active_model = None
    def build(training, **configuration):
        nonlocal active_model
        finish_previous()
        excluded = sorted(cohorts - {s['cohort_id'] for s in training})
        require(len(excluded) == 1, 'Frozen timing CV must exclude one whole cohort per build')
        identity = journal.start(configuration, training, excluded)
        try:
            model = original(training, **configuration)
            install_lookup_cache(model, identity)
            active_model = model
            journal.complete(identity, model.metadata['model_digest'])
            return model
        except BaseException as exc:
            journal.fail(identity, exc)
            raise
    timing_module.build_timing_candidate = build
    try:
        yield
    finally:
        timing_module.build_timing_candidate = original
        finish_previous()


def validate_operation(op):
    require(op.get('mode') in MODES, 'Timing-overlay CV entry mode')
    require(_path_key(op['worker_lock_path']) == _path_key(WORKER_LOCK), 'Original G002 worker lock required')
    require(len(op['protected_pins']) >= 351, 'Protected351 union may not be reduced')
    require(op.get('new_environment') == 0 and op.get('HTTP') == 0 and op.get('device_commands') == 0 and
            op.get('automatic_retry') is False, 'Saved-only, no-retry operation required')
    names = {Path(p['path']).name for p in op['source_pins']}
    require({'timing_overlay_cv.py', 'forecast_overlay_run.py', 'forecast_run.py', 'timing_model.py',
             'runtime_guard.py'} <= names, 'Exact timing/overlay/cache source closure required')
    require(sum(Path(p['path']).name == 'forecast_run.py' for p in op['source_pins']) == 1 and
            next(p for p in op['source_pins'] if Path(p['path']).name == 'forecast_run.py')['sha256'] == V2_SOURCE_SHA256,
            'Original V2 source preservation pin differs')
    if op['mode'] == 'TIMING_OVERLAY_CV_TEST':
        require('test_timing_overlay_cv.py' in names, 'New helper fixture source pin required')
        return
    inputs = {(_path_key(p['path']), p['sha256']) for p in op['input_pins']}
    for name in ('dataset_pin', 'timing_bank_overlay_pin', 'original_fit_operation_pin', 'original_timing_cv_pin'):
        require((_path_key(op[name]['path']), op[name]['sha256']) in inputs, name + ' is not an exact registered input')
    require(op['dataset_pin']['sha256'] == ORIGINAL_DATASET_SHA256, 'Original f54 compact dataset only')
    require(type(op.get('prior_timing_builds')) is int and op['prior_timing_builds'] > 0 and
            op.get('new_timing_build_cap') == op['prior_timing_builds'] and
            op.get('total_timing_build_cap') == TOTAL_BUILD_CAP,
            'Original-definition consumed/new builds with shared512 cap must be registered explicitly')


def timing_cv_stage(op, out, operation_path):
    import timing_model
    validate_operation(op)
    original_operation = read(pin(op['original_fit_operation_pin']))
    require(original_operation.get('mode') == 'FIT_CV' and
            original_operation.get('dataset_pin') == op['dataset_pin'], 'Original timing CV operation/dataset binding differs')
    original_cv = read(pin(op['original_timing_cv_pin']))
    prior_builds = original_cv.get('model_builds')
    require(type(prior_builds) is int and prior_builds == op['prior_timing_builds'] and
            original_cv.get('parameter_fits') == 0, 'Original consumed model-build artifact differs')
    configurations = copy.deepcopy(original_operation['timing_candidates'])
    if 'timing_candidates' in op:
        require(configurations == op['timing_candidates'], 'Candidate grid differs from original registered timing CV')
    require({r['candidate'] for r in original_cv['rows']} == {digest(c) for c in configurations},
            'Original saved rows do not bind the registered candidate grid')
    dataset = read(pin(op['dataset_pin']))
    overlay = read(pin(op['timing_bank_overlay_pin']))
    effective, proof = apply_timing_bank_overlay(dataset, overlay, op['dataset_pin'], op['timing_bank_overlay_pin']['sha256'])
    del dataset
    sessions = effective['sessions']
    cohorts = sorted({s['cohort_id'] for s in sessions})
    expected_builds = len(configurations) * len(cohorts)
    require(expected_builds == prior_builds == op['new_timing_build_cap'],
            'Original saved builds, original grid x actual whole cohorts, and registered new cap must agree')
    require(len(original_cv['rows']) == len(configurations) * sum(len(s.get('requests', [])) for s in sessions),
            'Original timing CV request/candidate denominator differs')
    write_new(Path(out) / 'TIMING_BANK_OVERLAY_PROOF.json', proof)
    bindings = {'schema': VERSION, 'data_original_sha256': op['dataset_pin']['sha256'],
                'timing_bank_overlay_sha256': op['timing_bank_overlay_pin']['sha256'],
                'effective_bank_map_sha256': proof['effective_bank_map_sha256'],
                'thermal_input_projection_sha256': proof['thermal_input_after_sha256'],
                'original_fit_operation_pin': op['original_fit_operation_pin'],
                'original_timing_cv_pin': op['original_timing_cv_pin'],
                'candidate_grid_sha256': digest(configurations), 'cohorts_sha256': digest(cohorts),
                'expected_builds': expected_builds, 'source_pins_sha256': digest(op['source_pins']),
                'AP_fits': 0, 'NN': 0, 'simulation_START_consumed': 0,
                'definition': 'Frozen original grouped_validate_timing with original candidate order and whole-cohort roster; only registered bank overlay and exact lookup cache'}
    write_new(Path(out) / 'TIMING_CV_BINDINGS.json', bindings)
    journal = TimingBuildJournal(out, operation_sha256=sha(operation_path), prior_builds=op['prior_timing_builds'],
                                 new_cap=op['new_timing_build_cap'], total_cap=op['total_timing_build_cap'])
    reports = []
    with cached_registered_builds(timing_model, sessions, journal, reports):
        result = timing_model.grouped_validate_timing(sessions, configurations, build_cap=op['new_timing_build_cap'])
    require(result['model_builds'] == journal.used == expected_builds and journal.failed == 0,
            'New timing CV build result/receipt conservation differs')
    write_new(Path(out) / 'TIMING_CV.json', result)
    write_new(Path(out) / 'LOOKUP_CACHE_REPORT.json', {'schema': VERSION, 'models': reports,
              'model_count': len(reports), 'source_math_unchanged': True, 'no_cache_shared_across_cohorts_or_candidates': True})
    write_new(Path(out) / 'TIMING_CV_RESULT.json', {'schema': VERSION, 'status': 'POSTHOC_TIMING_CV_COMPLETE_NO_PASS_CLAIM',
              'budget': journal.summary(), 'bindings_sha256': sha(Path(out) / 'TIMING_CV_BINDINGS.json'),
              'result_sha256': sha(Path(out) / 'TIMING_CV.json'), 'cache_report_sha256': sha(Path(out) / 'LOOKUP_CACHE_REPORT.json'),
              'original_timing_result_preserved': True, 'original_result_sha256': op['original_timing_cv_pin']['sha256'],
              'rows': len(result['rows']), 'all_heldout_retained': result['all_heldout_retained'],
              'predictive_accuracy_PASS': None, 'selection': None, 'AP_fits': 0, 'NN': 0,
              'simulation_START_consumed': 0, 'automatic_retry': False,
              'role': 'POSTHOC_BANK_LABEL_REPAIR_DEVELOPMENT_CV_NOT_INDEPENDENT_CONFIRMATION'})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--operation', required=True)
    args = parser.parse_args()
    with operation(args.operation, __file__) as (op, out):
        validate_operation(op)
        if op['mode'] == 'TIMING_OVERLAY_CV_TEST':
            suite = unittest.TestLoader().discover(str(WORK), pattern='test_timing_overlay_cv.py')
            stream = io.StringIO()
            tests = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
            write_new(out / 'TEST_RESULT.json', {'status': 'PASS' if tests.wasSuccessful() else 'FAIL',
                      'testsRun': tests.testsRun, 'output': stream.getvalue(),
                      'failures': [(str(t), e) for t, e in tests.failures], 'errors': [(str(t), e) for t, e in tests.errors],
                      'actual_model_builds': 0, 'AP_fits': 0, 'NN': 0, 'simulation_START_consumed': 0})
            require(tests.wasSuccessful(), 'New timing helper fixtures failed; namespace consumed, no retry')
        else:
            timing_cv_stage(op, out, args.operation)
    print(canonical({'status': 'COMPLETE', 'mode': op['mode'], 'output': str(out)}))


if __name__ == '__main__':
    main()
