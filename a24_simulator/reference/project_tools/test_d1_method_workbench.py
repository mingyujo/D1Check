"""Saved-evidence workbench boundary and real PC CLI; never a device test."""
import copy
import csv
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from tools import d1_method_workbench as w
from tools import d1_simulator as sim


class MethodWorkbenchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.frozen, _ = w.budget.readout.source.f.x.p.inputs(w.budget.readout.source.f.x.p.BUNDLE)
        cls.record = next(z for z in w.budget.readout.source.records(w.budget.ROOT/'run_v1/records.jsonl.gz')
                          if z['meta']['stage'] == w.budget.STAGE)

    def test_exact_resources_and_incomplete_or_changed_hash_rejected(self):
        original = json.loads(w.RESOURCE.read_text(encoding='utf8'))
        self.assertEqual(len(w.verify_resources()), 8)
        with TemporaryDirectory() as tmp:
            p = Path(tmp)/'resources.json'
            bad = copy.deepcopy(original); bad['files'].pop(next(iter(bad['files'])))
            p.write_text(json.dumps(bad), encoding='utf8')
            with self.assertRaisesRegex(ValueError, 'complete registered'): w.verify_resources(p)
            bad = copy.deepcopy(original); bad['files'][next(iter(bad['files']))] = '0'*64
            p.write_text(json.dumps(bad), encoding='utf8')
            with self.assertRaisesRegex(ValueError, 'resource mismatch'): w.verify_resources(p)

    def test_unsupported_detector_gpu_not_substituted(self):
        bad = copy.deepcopy(self.record)
        next(q for q in bad['ledger'] if q['task'] == 'detection')['backend'] = 'GPU'
        with self.assertRaisesRegex(ValueError, 'unsupported method'): w.audit_record(bad, self.frozen)

    def test_worker_release_cannot_replace_lane_release(self):
        bad = copy.deepcopy(self.record)
        bad['ledger'][0]['lane_available_ns'] = bad['ledger'][0]['worker_release_ns']
        with self.assertRaisesRegex(ValueError, 'state boundaries'): w.audit_record(bad, self.frozen)

    def test_same_lane_overlap_and_missing_interval_rejected(self):
        bad = copy.deepcopy(self.record)
        q, r = [z for z in bad['ledger'] if z['backend'] == 'CPU'][:2]
        delta = r['dispatch_ns']-q['dispatch_ns']
        for field in ('arrival_ns', 'dispatch_ns', 'execution_start_ns', 'output_ready_ns',
                      'persist_complete_ns', 'worker_release_ns', 'lane_available_ns'):
            r[field] -= delta
        with self.assertRaises(ValueError): w.audit_record(bad, self.frozen)
        bad = copy.deepcopy(self.record); bad['segments'].pop()
        with self.assertRaisesRegex(ValueError, 'incomplete stored'): w.audit_record(bad, self.frozen)

    def test_nonfinite_clock_rejected(self):
        bad = copy.deepcopy(self.record); bad['ledger'][0]['dispatch_ns'] = float('nan')
        with self.assertRaises(ValueError): w.audit_record(bad, self.frozen)

    def test_analyze_never_simulates_or_promotes_validation(self):
        before = w.verify_resources()
        with patch.object(sim.engine, 'simulate', side_effect=AssertionError('new simulation forbidden')):
            result = w.analyze()
        self.assertEqual(len(result['audit']), 168)
        self.assertTrue(all(z['complete_model_window'] for z in result['audit']))
        self.assertTrue(all(not z['strict_support'] and not z['independent_prediction_validation']
                            and z['policy_difference_distinguishable'] is None for z in result['audit']))
        self.assertIsNone(result['scope']['accuracy_pass'])
        self.assertEqual(result['new_simulations'], 0)
        self.assertEqual(w.verify_resources(), before)

    def test_cli_rejects_new_options_and_overwrite_before_analysis(self):
        with TemporaryDirectory() as tmp, patch.object(w, 'analyze', side_effect=AssertionError('should not start')):
            path = Path(tmp)/'new'
            for option in (['--seed', '201'], ['--initial-ap-c', '29.1'], ['--mode', 'strict'],
                           ['--policy', 'EFT_REFERENCE'], ['--ap-cap-c', '0'],
                           ['--online-bundle', 'anything'], ['--case-id', 'anything']):
                with self.subTest(option=option), self.assertRaises(SystemExit):
                    sim.main(['method-readout', '--output', str(path), *option])
                self.assertFalse(path.exists())
            with self.assertRaises(SystemExit): sim.main(['method-readout', '--output', tmp])

    def test_actual_cli_saved_output_csv_and_no_adb(self):
        with TemporaryDirectory() as tmp:
            folder = Path(tmp); marker = folder/'adb-called.txt'; trap = folder/'adb.cmd'
            trap.write_text('@echo off\r\necho unexpected>"'+str(marker)+'"\r\nexit /b 99\r\n', encoding='utf8')
            env = dict(os.environ, PATH=str(folder)+os.pathsep+os.environ['PATH'])
            out = folder/'result'
            command = [sys.executable, '-B', '-m', 'tools.d1_simulator', 'method-readout', '--output', str(out)]
            done = subprocess.run(command, cwd=w.ROOT, env=env, capture_output=True, text=True, timeout=45)
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertFalse(marker.exists())
            status = json.loads(done.stdout); self.assertEqual(status['cases'], 168)
            result = json.loads((out/'result.json').read_text(encoding='utf8'))
            with (out/'summary.csv').open(encoding='utf8', newline='') as f: rows = list(csv.DictReader(f))
            self.assertEqual(len(rows), 28)
            self.assertTrue(all(z['strict_support'] == 'False' and z['actual_device_energy_gain'] == '' for z in rows))
            self.assertEqual(result['readout']['physical_model_sha256'], w.budget.readout.source.f.x.p.MODEL_SHA)
            before = (out/'result.json').read_bytes()
            repeated = subprocess.run(command, cwd=w.ROOT, env=env, capture_output=True, timeout=15)
            self.assertNotEqual(repeated.returncode, 0)
            self.assertEqual(before, (out/'result.json').read_bytes())


if __name__ == '__main__': unittest.main()
