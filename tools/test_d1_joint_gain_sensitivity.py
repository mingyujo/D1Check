import csv
import json
import math
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from tools import d1_joint_gain_sensitivity as sensitivity


def segments(active, end=180.):
    return [dict(start_s=0., end_s=active, state='CC'),
            dict(start_s=active, end_s=end, state='idle')]


class JointGainSensitivityTests(unittest.TestCase):
    def test_clipped_energy_window_and_worst_sign_bound(self):
        coefficients = dict(CC=2.)
        self.assertEqual(sensitivity.exposure(segments(150.), coefficients), dict(CC=120.))
        result = sensitivity.inverse(segments(10.), segments(12.), coefficients, -4.)
        self.assertEqual(result['exposure_l1_s'], 2.)
        radius = result['uniform_increment_error_break_even_w']
        self.assertEqual(radius, 2.)
        # Mathematical worst direction only; no fitted/changed physical model.
        perturbation = {s: radius*math.copysign(1., dt) for s, dt in result['delta_state_seconds'].items()}
        changed_delta = result['modeled_delta_j'] + sum(result['delta_state_seconds'][s]*v for s, v in perturbation.items())
        self.assertAlmostEqual(changed_delta, 0.)
        self.assertLess(result['modeled_delta_j'] + .5*radius*result['exposure_l1_s'], 0.)

    def test_gap_unknown_state_and_missing_window_are_not_partial_totals(self):
        wrong = segments(10.); wrong[1]['start_s'] = 11.
        unknown = segments(10.); unknown[0]['state'] = 'unmeasured'
        for case in (wrong, unknown, segments(10., 179.)):
            with self.assertRaises(ValueError): sensitivity.exposure(case, dict(CC=2.))

    def test_nonfinite_mismatch_and_no_gain_remain_blocked_or_null(self):
        for coefficients, delta in [(dict(CC=float('nan')), -4.), (dict(CC=2.), float('nan')), (dict(CC=2.), -3.)]:
            with self.assertRaises(ValueError): sensitivity.inverse(segments(10.), segments(12.), coefficients, delta)
        result = sensitivity.inverse(segments(12.), segments(10.), dict(CC=2.), 4.)
        self.assertIsNone(result['modeled_J_gain_j'])
        self.assertIsNone(result['uniform_increment_error_break_even_w'])

    def test_saved_denominator_readonly_and_frozen_hashes(self):
        bundle = sensitivity.P.BUNDLE
        before = {f: sensitivity.P.digest(bundle/f) for f in ('model.json', 'initial_inputs.json')}
        engine = sensitivity.source.study.followup.x.old.engine
        with patch.object(engine, 'simulate', side_effect=AssertionError('readout must not simulate')):
            result = sensitivity.analyze()
        self.assertEqual(len(result['rows']), 8)
        self.assertEqual(sum(r['modeled_J_gain_j'] is None for r in result['rows']), 2)
        self.assertEqual(sum(r['modeled_J_gain_j'] is not None for r in result['rows']), 6)
        for row in result['rows']:
            self.assertIsNone(row['actual_coefficient_error_bound_w'])
            self.assertIsNone(row['actual_controller_delta_j'])
            self.assertFalse(row['independent_policy_advantage_confirmed'])
        self.assertEqual(before, {f: sensitivity.P.digest(bundle/f) for f in before})
        self.assertEqual(before['model.json'], sensitivity.P.MODEL_SHA)
        self.assertEqual(before['initial_inputs.json'], sensitivity.P.INITIAL_SHA)

    def test_actual_cli_fake_adb_trap_csv_json_and_no_overwrite(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp); marker = root/'ADB_CALLED'; trap = root/'adb.cmd'
            trap.write_text('@echo off\necho called>"'+str(marker)+'"\nexit /b 99\n', encoding='ascii')
            env = dict(os.environ, PATH=str(root)+os.pathsep+os.environ.get('PATH', ''), PYTHONIOENCODING='utf8')
            output = root/'report'
            command = [sys.executable, '-B', '-m', 'tools.d1_joint_gain_sensitivity', '--output', str(output)]
            done = subprocess.run(command, cwd=sensitivity.P.ROOT, env=env, capture_output=True, text=True, encoding='utf8', timeout=40)
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertFalse(marker.exists())
            result = json.loads((output/'result.json').read_text(encoding='utf8'))
            manifest = json.loads((output/'analysis_manifest.json').read_text(encoding='utf8'))
            self.assertFalse(manifest['registration_before_analysis'])
            self.assertEqual(manifest['source_sha256'], sensitivity.P.digest(__import__('tools.d1_joint_gain_sensitivity', fromlist=['']).__file__))
            with (output/'requirements.csv').open(encoding='utf8', newline='') as file:
                rows = list(csv.DictReader(file))
            self.assertEqual(len(rows), len(result['rows']))
            for row, expected in zip(rows, result['rows']):
                if expected['modeled_J_gain_j'] is not None:
                    self.assertAlmostEqual(float(row['modeled_J_gain_j']), expected['modeled_J_gain_j'])
            original = (output/'result.json').read_bytes()
            repeated = subprocess.run(command, cwd=sensitivity.P.ROOT, env=env, capture_output=True, text=True, encoding='utf8', timeout=40)
            self.assertNotEqual(repeated.returncode, 0)
            self.assertIn('FileExistsError', repeated.stderr)
            self.assertEqual(original, (output/'result.json').read_bytes())
            self.assertFalse(marker.exists())


if __name__ == '__main__': unittest.main()
