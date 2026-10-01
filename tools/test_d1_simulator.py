"""Workbench boundaries and real CLI; no device binary or Android execution."""
import copy
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

from tools import d1_simulator as sim


class WorkbenchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = sim.arrival()

    def test_exact_archived_schedules_and_service_guard(self):
        self.assertEqual([c['recorded_source_schedule_match'] for c in self.result['cases']], [True]*3)
        self.assertEqual([c['guard']['eligible'] for c in self.result['cases']], [True, True, False])
        self.assertEqual([len(c['observations']) for c in self.result['cases']], [2, 2, 0])
        self.assertTrue(all(c['service']['planned'] == c['service']['succeeded'] == 24 for c in self.result['cases']))

    def test_observations_never_become_prediction_or_rank(self):
        for c in self.result['cases']:
            self.assertIsNone(c['energy_ap']['whole_device_energy_j'])
            self.assertIsNone(c['energy_ap']['ap_peak_c'])
            self.assertIsNone(c['guard']['energy_ap_rank'])
        self.assertIsNone(self.result['energy_ap_policy_rank'])
        self.assertFalse(self.result['experiment_ready'])

    def test_input_seed_and_mode_changes_do_not_reuse_observations(self):
        for kwargs in ({'scenario': 'low'}, {'seed': 202}, {'mode': 'strict'}):
            with self.subTest(kwargs=kwargs):
                changed = sim.arrival(**kwargs)
                self.assertTrue(all(not c['observations'] for c in changed['cases']))

    def test_same_key_but_changed_lane_or_backend_does_not_match(self):
        result = dict(policy='B2_PC', ledger=copy.deepcopy(self.result['cases'][1]['ledger']))
        result['ledger'][0]['lane_available_ns'] += 1
        self.assertFalse(sim.archived_match(result, 'queue', 'explore', 201))
        result['ledger'][0]['lane_available_ns'] -= 1
        result['ledger'][0]['backend'] = 'GPU'
        self.assertFalse(sim.archived_match(result, 'queue', 'explore', 201))

    def test_reference_loader_not_available_to_scheduler(self):
        with patch.object(sim, 'observations', return_value=[{'sentinel': 'no scheduler input'}]):
            changed = sim.arrival()
        for actual, expected in zip(changed['cases'], self.result['cases']):
            self.assertEqual(actual['ledger'], expected['ledger'])
            self.assertEqual(actual['service'], expected['service'])
            self.assertEqual(actual['energy_ap'], expected['energy_ap'])

    def test_missing_service_is_ineligible_not_zero(self):
        row = sim.guard_row('CPU_URGENT', self.result['cases'][0]['service'], 'queue', 201)
        row['urgent_p95_ms'] = 'None'
        result = sim.service_guard(row, row, sim.read(sim.guard.CONTRACT))
        self.assertFalse(result['eligible'])
        self.assertEqual(result['failed_conditions'], 'missing_response_metric')

    def test_resource_mutation_fails_closed(self):
        spec = sim.read(sim.CONTRACT)
        key = next(iter(spec['files']))
        spec['files'][key] = '0'*64
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'resources.json'
            path.write_text(json.dumps(spec), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'resource mismatch'):
                sim.verify_resources(path)

    def test_episode_reuses_frozen_model_and_rejects_temperature_sweep(self):
        out = sim.fixed_episode()
        self.assertEqual(out['result']['status'], 'TRADEOFF')
        self.assertFalse(out['result']['candidate_is_deployable'])
        self.assertEqual(sim.fixed_episode(29.2)['result']['status'], 'OUT_OF_SUPPORT')
        self.assertEqual(sim.fixed_episode(completion_cap=250, ap_cap=35)['result']['model_candidate'], 'parallel')

    def test_figure_data_and_svg_validity(self):
        rendered = sim.render(self.result)
        for snippet in re.findall(r'<svg.*?</svg>', rendered):
            ET.fromstring(snippet)
        for case in self.result['cases']:
            for obs in case['observations']:
                index = obs['summary']['index']
                source = sim.rows(sim.OBSERVED/f'{index}_ap.csv')
                self.assertEqual(len(obs['ap_path']), len(source))
                self.assertEqual(obs['ap_path'][-1][1], float(source[-1]['observed_ap_c']))
                self.assertIn(f'{obs["summary"]["energy_j"]:.3f}', rendered)
        self.assertIn('미지원 / 미지원', rendered)
        self.assertIn(' hidden', rendered)

    def test_missing_plot_point_splits_path(self):
        rendered = sim.plot([('missing', [[0, 2], [1, None], [2, 3]])], 'AP')
        self.assertEqual(rendered.count('<polyline'), 2)
        self.assertEqual(sim.plot([('missing', [[0, None]])], 'AP'), '<p>관측 없음 / 계산 불가</p>')

    def test_real_cli_exports_both_routes_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            # Trap any accidental shell ADB invocation; no real adb path supplied.
            marker = root/'adb_called.txt'
            (root/'adb.cmd').write_text(f'@echo DEVICE_CALL>{marker}\r\nexit /b 93\r\n')
            env = dict(os.environ, PATH=str(root), PYTHONIOENCODING='utf-8', PYTHONDONTWRITEBYTECODE='1')
            for route in ('arrival', 'episode'):
                command = [sys.executable, '-B', '-m', 'tools.d1_simulator', route, '--output', str(root/route)]
                ran = subprocess.run(command, cwd=sim.ROOT, env=env, capture_output=True, text=True, timeout=30)
                self.assertEqual(ran.returncode, 0, ran.stderr)
                result = sim.read(root/route/'result.json')
                self.assertFalse(result['experiment_ready'])
                self.assertTrue((root/route/'index.html').is_file())
                table = sim.rows(root/route/'summary.csv')
                if route == 'arrival':
                    self.assertEqual(len(table), 3)
                    self.assertEqual(table[1]['energy_j'], '')
                    self.assertAlmostEqual(float(table[1]['urgent_p95_ms']), result['cases'][1]['service']['urgent']['response_p95_ms'])
                before = sim.digest(root/route/'result.json')
                again = subprocess.run(command, cwd=sim.ROOT, env=env, capture_output=True, text=True, timeout=30)
                self.assertNotEqual(again.returncode, 0)
                self.assertEqual(sim.digest(root/route/'result.json'), before)
            self.assertFalse(marker.exists())

    def test_episode_rejects_arrival_options(self):
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder)/'result'
            command = [sys.executable, '-B', '-m', 'tools.d1_simulator', 'episode', '--seed', '202', '--output', str(out)]
            ran = subprocess.run(command, cwd=sim.ROOT, capture_output=True, timeout=30)
            self.assertNotEqual(ran.returncode, 0)
            self.assertFalse(out.exists())


if __name__ == '__main__':
    unittest.main()
