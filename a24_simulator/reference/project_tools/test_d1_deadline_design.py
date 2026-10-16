"""Checks input construction, response boundaries, provenance and preservation."""
import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools import d1_deadline_design as d


class DeadlineDesignTest(unittest.TestCase):
    def fixture(self):
        return {'service': {
            'first': {'phase_means_ns': {
                'classification_CPU_urgent': [1e6, 100e6, 900e6, 5e6, 6e6],
                'detection_CPU_normal': [1e6, 500e6, 9e6, 5e6, 6e6]}},
            'second': {'phase_means_ns': {
                'classification_CPU_urgent': [1e6, 101.1e6, 1e6, 5e6, 6e6],
                'detection_CPU_normal': [1e6, 501.1e6, 9e6, 5e6, 6e6]}}}}

    def test_response_boundary_is_not_lane_or_execution_only(self):
        r = d.reference(self.fixture())
        self.assertEqual(r['classification']['reference_ns'], 103_000_000)
        self.assertEqual(r['detection']['reference_ns'], 512_000_000)

    def test_missing_nonfinite_or_partial_profiles_rejected(self):
        for value in ([], [1, 2], [1, 2, float('nan'), 4, 5], [0]*5, [-1, 2, 3, 4, 5]):
            m = self.fixture()
            for s in m['service'].values():
                s['phase_means_ns']['classification_CPU_urgent'] = value
            with self.assertRaises(ValueError):
                d.reference(m)
        with self.assertRaises(ValueError):
            d.reference({'service': {}})

    def test_deadlines_do_not_depend_on_backend_or_future_requests(self):
        scenario = d.design(self.fixture())['scenarios'][0]
        q = dict(task='classification', priority='urgent', id='a', arrival_ns=35_000_000_000,
                 deadline_offset_ns=1_500_000_000, backend='CPU')
        first = d.assign([q], scenario)
        other = dict(q, backend='GPU')
        future = dict(q, id='future', arrival_ns=100_000_000_000)
        second = d.assign([other, future], scenario)
        self.assertEqual(first[0]['deadline_offset_ns'], second[0]['deadline_offset_ns'])
        self.assertEqual(q['deadline_offset_ns'], 1_500_000_000)
        self.assertEqual(first[0]['arrival_ns'], q['arrival_ns'])

    def test_unsupported_priority_and_bad_deadline_rejected(self):
        scenario = d.design(self.fixture())['scenarios'][0]
        with self.assertRaises(ValueError):
            d.assign([dict(task='classification', priority='normal')], scenario)
        for value in (0, -1, True, float('nan')):
            bad = copy.deepcopy(scenario)
            bad['relative_deadline_ns']['classification'] = value
            with self.assertRaises(ValueError):
                d.assign([dict(task='classification', priority='urgent')], bad)

    def test_legacy_and_frozen_model_preserved(self):
        data = d.MODEL.read_bytes()
        self.assertEqual(hashlib.sha256(data).hexdigest(), d.MODEL_SHA)
        result = d.design(json.loads(data))
        self.assertEqual(result['scenarios'][-1]['relative_deadline_ns'],
                         dict(classification=1_500_000_000, detection=6_000_000_000))
        self.assertIsNone(result['user_sla'])
        self.assertFalse(result['experiment_ready'])
        self.assertEqual(d.MODEL.read_bytes(), data)

    def test_real_cli_and_existing_output_protection(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder)/'design.json'
            command = [sys.executable, '-B', '-m', 'tools.d1_deadline_design', '--output', str(target)]
            run = subprocess.run(command, cwd=d.ROOT, capture_output=True, timeout=30)
            self.assertEqual(run.returncode, 0, run.stderr)
            original = target.read_bytes()
            again = subprocess.run(command, cwd=d.ROOT, capture_output=True, timeout=30)
            self.assertNotEqual(again.returncode, 0)
            self.assertEqual(target.read_bytes(), original)


if __name__ == '__main__':
    unittest.main()
