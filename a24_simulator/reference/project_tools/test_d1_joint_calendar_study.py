import gzip
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from tools import d1_joint_calendar_study as study


class JointCalendarStudyTests(unittest.TestCase):
    def test_four_fixed_comparisons_exact_caps_and_null_no_incumbent(self):
        calls = []
        def missing(frozen, initial, tickets, **kwargs):
            calls.append((tickets, kwargs))
            return dict(status='no_incumbent', jobs=None, status_code=1,
                        solver_gap=None, grid_optimality_only=False)
        with TemporaryDirectory() as tmp, patch.object(study.solver, 'plan', side_effect=missing):
            out = Path(tmp)/'study'; rows = study.run(out)
            raw = [json.loads(line) for line in gzip.decompress((out/'records.jsonl.gz').read_bytes()).decode().splitlines()]
            self.assertEqual(len(calls), 4); self.assertEqual(len(rows), 4)
            self.assertTrue(all(len(qs) == 48 for qs, _ in calls))
            for (_, args), record in zip(calls, raw):
                self.assertEqual(args['ap_cap_c'], record['reference']['peak_ap_c'])
                self.assertEqual(args['area_cap_c_s'], record['reference']['thermal_degree_seconds'])
                self.assertEqual(args['grid_s'], .02); self.assertEqual(args['timeout_s'], 120.)
                self.assertEqual(args['scenario'], 'mean')
                self.assertIsNone(record['meta']['delta_energy_j'])
                self.assertIsNone(record['meta']['deadline_met'])
                self.assertFalse(record['meta']['exact_replay_joint_nonworsening'])
            self.assertEqual(json.loads((out/'summary.json').read_text())['new_offline_replays'], 0)

    def test_original_error_and_completed_case_are_preserved(self):
        with TemporaryDirectory() as tmp, patch.object(study.solver, 'plan', side_effect=[
            dict(status='no_incumbent', jobs=None, status_code=1), RuntimeError('original fixture failure')]):
            out = Path(tmp)/'failed'
            with self.assertRaisesRegex(RuntimeError, 'original fixture failure'): study.run(out)
            failure = json.loads((out/'PC_FAILURE.json').read_text(encoding='utf8'))
            self.assertEqual(failure['completed_solves'], 1)
            self.assertIn('RuntimeError: original fixture failure', failure['stack'])
            self.assertTrue(failure['original_error_preserved'])
            self.assertEqual(len(gzip.decompress((out/'records.jsonl.gz').read_bytes()).splitlines()), 1)
            self.assertFalse((out/'summary.json').exists())

    def test_output_reexecution_is_blocked_before_solver(self):
        with TemporaryDirectory() as tmp, patch.object(study.solver, 'plan', side_effect=AssertionError('must not start')):
            with self.assertRaises(FileExistsError): study.run(tmp)


if __name__ == '__main__': unittest.main()
