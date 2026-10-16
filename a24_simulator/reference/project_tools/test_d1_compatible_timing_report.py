import copy
import gzip
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from tools import d1_compatible_timing_report as r


class CompatibleReadoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.records = r.shared.load(r.ROOT/'timing_ledgers.json')
        cls.controls = r.shared.load(r.c.b.ROOT/'run_v1/timing_ledgers.json')
        cls.inputs = r.shared.load(r.c.b.ROOT/'run_v1/inputs.json')

    def validate(self, records=None, controls=None):
        return r.validate(self.records if records is None else records,
                          self.controls if controls is None else controls, self.inputs)

    def test_full_saved_study_and_null_physics(self):
        r.verify(r.ROOT)
        paired = self.validate()
        self.assertEqual(len(paired), 48)
        self.assertEqual(sum(z['meta']['planned'] for z in self.records), 768)
        self.assertEqual(sum(z['meta']['deadline_met'] == 48 for z in self.records), 12)
        self.assertEqual(sum(z['meta']['detection_gpu_jobs'] for z in self.records), 94)
        self.assertTrue(all(z['energy_j'] is None and z['ap_peak_c'] is None and
                            not z['deployment_allowed'] for z in paired))

    def test_arrival_and_response_release_boundaries(self):
        bad = copy.deepcopy(self.records)
        bad[0]['ledger'][0]['arrival_ns'] += 1
        with self.assertRaises(ValueError): self.validate(bad)
        bad = copy.deepcopy(self.records)
        bad[0]['ledger'][0]['lane_available_ns'] = bad[0]['ledger'][0]['worker_release_ns']-1
        with self.assertRaises(ValueError): self.validate(bad)

    def test_partial_duplicate_and_missing_controls_rejected(self):
        with self.assertRaises(ValueError): self.validate(self.records[:-1])
        with self.assertRaises(ValueError): self.validate(self.records+[self.records[0]])
        with self.assertRaises(ValueError): self.validate(controls=self.controls[:-1])

    def test_unidentified_cost_and_wrong_completed_count_rejected(self):
        bad = copy.deepcopy(self.records); bad[0]['meta']['energy_j'] = 0
        with self.assertRaises(ValueError): self.validate(bad)
        bad = copy.deepcopy(self.records); bad[0]['meta']['completed'] -= 1
        with self.assertRaises(ValueError): self.validate(bad)

    def test_compressed_reaggregation_never_calls_event_engine(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ('timing_ledgers.json', 'registered_before_run.json'):
                data = r.shared.source_bytes(r.ROOT/name)
                (root/(name+'.gz')).write_bytes(gzip.compress(data, mtime=0))
            with patch.object(r.c.b.batch.engine, 'simulate', side_effect=AssertionError('new simulation forbidden')):
                rows = r.report(root)
            self.assertEqual(len(rows), 48)
            text = (root/'index.html').read_text(encoding='utf8')
            self.assertIn('미계측 / null', text)
            self.assertIn('独立', text) if False else self.assertIn('독립 예측', text)

    def test_actual_module_cli_enters_canonical_controller(self):
        import subprocess
        with TemporaryDirectory() as directory:
            output = Path(directory)/'actual_cli'
            result = subprocess.run(['python', '-m', 'tools.d1_compatible_timing_backfill', '--output', str(output)],
                cwd=r.c.b.f.x.p.ROOT, capture_output=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stderr.decode('utf8', errors='replace'))
            records = r.shared.load(output/'timing_ledgers.json')
            self.assertEqual(len(self.validate(records)), 48)


if __name__ == '__main__': unittest.main()
