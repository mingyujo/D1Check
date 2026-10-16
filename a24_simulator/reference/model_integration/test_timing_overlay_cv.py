"""Pure receipt/wrapper fixtures; no actual timing build, fit or simulation."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import timing_overlay_cv as subject


def journal_at(folder, **changes):
    config = {'operation_sha256': 'a' * 64, 'prior_builds': 180, 'new_cap': 180, 'total_cap': 512}
    config.update(changes)
    return subject.TimingBuildJournal(folder, **config)


class TimingOverlayCVTests(unittest.TestCase):
    def test_dynamic_actual_original_build_count_and_shared_cap(self):
        with tempfile.TemporaryDirectory() as folder:
            journal = journal_at(folder)
            self.assertEqual(journal.summary()['new_model_build_START_consumed'], 0)
            self.assertEqual(journal.summary()['prior_artifact_certified_timing_builds'], 180)
            self.assertEqual(journal.path.stat().st_size, 0)
        for changes in ({'prior_builds': 180, 'new_cap': 174}, {'prior_builds': 257, 'new_cap': 257},
                        {'total_cap': 513}, {'prior_builds': 0, 'new_cap': 0}):
            with tempfile.TemporaryDirectory() as folder, self.subTest(changes=changes), self.assertRaises(RuntimeError):
                journal_at(folder, **changes)

    def test_FAIL_consumes_build_START_and_no_environment(self):
        with tempfile.TemporaryDirectory() as folder:
            journal = journal_at(folder, prior_builds=1, new_cap=1)
            identity = journal.start({'sealed': True}, [{'session_id': 'TRAIN', 'cohort_id': 'A'}], ['B'])
            journal.fail(identity, ValueError('SEALED_SYNTHETIC_FAILURE'))
            report = journal.summary()
            self.assertEqual(report['new_model_build_START_consumed'], 1)
            self.assertEqual(report['new_model_build_FAIL'], 1)
            self.assertEqual(report['total_timing_builds_consumed'], 2)
            self.assertEqual(report['simulation_START_consumed'], 0)
            rows = [json.loads(line) for line in journal.path.read_text().splitlines()]
            self.assertEqual([r['event'] for r in rows], ['START', 'FAIL'])
            self.assertTrue(rows[-1]['build_START_remains_consumed'])
            with self.assertRaises(RuntimeError):
                journal.start({}, [], [])

    def test_new_namespace_ledger_exclusive_no_retry(self):
        with tempfile.TemporaryDirectory() as folder:
            journal_at(folder)
            with self.assertRaises(FileExistsError):
                journal_at(folder)

    def test_original_builder_arguments_object_and_function_restored_on_success(self):
        sessions = [{'session_id': 'A', 'cohort_id': 'CA'}, {'session_id': 'B', 'cohort_id': 'CB'}]
        called, reports = [], []
        model = SimpleNamespace(metadata={'model_digest': 'b' * 64})
        def original(training, **configuration):
            called.append((training, configuration))
            return model
        frozen_cv = object()
        module = SimpleNamespace(build_timing_candidate=original, grouped_validate_timing=frozen_cv)
        with tempfile.TemporaryDirectory() as folder:
            journal = journal_at(folder, prior_builds=1, new_cap=1)
            with patch.object(subject, 'install_lookup_cache', return_value=model) as cache, \
                 patch.object(subject, 'lookup_cache_report', return_value={'unchanged': True}):
                with subject.cached_registered_builds(module, sessions, journal, reports):
                    returned = module.build_timing_candidate(sessions[:1], family='m8', estimator='empirical', seed=123)
                    self.assertIs(returned, model)
                    self.assertIs(module.grouped_validate_timing, frozen_cv)
                    cache.assert_called_once()
            self.assertIs(module.build_timing_candidate, original)
            self.assertEqual(called, [(sessions[:1], {'family': 'm8', 'estimator': 'empirical', 'seed': 123})])
            self.assertEqual(reports, [{'unchanged': True}])
            self.assertEqual(journal.summary()['new_model_build_COMPLETE'], 1)

    def test_original_builder_restored_and_FAIL_recorded_on_build_exception(self):
        sessions = [{'session_id': 'A', 'cohort_id': 'CA'}, {'session_id': 'B', 'cohort_id': 'CB'}]
        def original(training, **configuration):
            raise ValueError('SEALED_SYNTHETIC_FAILURE')
        module = SimpleNamespace(build_timing_candidate=original)
        with tempfile.TemporaryDirectory() as folder:
            journal = journal_at(folder, prior_builds=1, new_cap=1)
            with self.assertRaises(ValueError):
                with subject.cached_registered_builds(module, sessions, journal, []):
                    module.build_timing_candidate(sessions[:1], family='m8')
            self.assertIs(module.build_timing_candidate, original)
            self.assertEqual(journal.summary()['new_model_build_FAIL'], 1)

    def test_whole_cohort_exclusion_required_before_build_START(self):
        sessions = [{'session_id': 'A', 'cohort_id': 'CA'}, {'session_id': 'B', 'cohort_id': 'CB'}]
        original = lambda training, **configuration: None
        module = SimpleNamespace(build_timing_candidate=original)
        with tempfile.TemporaryDirectory() as folder:
            journal = journal_at(folder, prior_builds=1, new_cap=1)
            with self.assertRaises(RuntimeError):
                with subject.cached_registered_builds(module, sessions, journal, []):
                    module.build_timing_candidate(sessions, family='m8')
            self.assertIs(module.build_timing_candidate, original)
            self.assertEqual(journal.used, 0)


if __name__ == '__main__':
    unittest.main()
