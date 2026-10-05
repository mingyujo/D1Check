import copy
import csv
import gzip
import json
import os
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from tools import d1_joint_calendar_report as report
from tools import d1_joint_calendar_witness as witness


class JointCalendarReadoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = report.ROOT/'joint_calendar_v1'
        cls.witness = report.ROOT/'joint_calendar_witness_v1'

    def test_read_only_full_four_cases_without_optimizer_or_event_simulation(self):
        with (patch.object(report.study.solver, 'plan', side_effect=AssertionError('no optimizer')),
              patch.object(report.study.followup.x, 'simulate', side_effect=AssertionError('no new replay'))):
            result = report.load(self.source, self.witness)
        self.assertEqual(len(result['rows']), 4)
        self.assertEqual(len(result['details']), 2)
        self.assertEqual(sum(r['same_grid_feasible_witness'] for r in result['rows']), 4)
        missing = [r for r in result['rows'] if r['optimization_unresolved']]
        self.assertEqual(len(missing), 2)
        self.assertTrue(all(r['delta_energy_j'] is None and r['deadline_met'] is None for r in missing))
        self.assertFalse(result['physical_advantage_proven'])
        self.assertFalse(result['independent_prediction_validation'])
        self.assertFalse(result['experiment_ready'])

    def test_rectified_improvement_is_not_uniform_cooling_or_signed_area_improvement(self):
        result = report.load(self.source, self.witness)
        row = next(r for r in result['rows'] if r['envelope'] == 'g0.45_c0.75_b4' and r['seed'] == 223001)
        self.assertLess(row['delta_energy_j'], 0.)
        self.assertLess(row['delta_peak_ap_c'], 0.)
        self.assertLess(row['delta_thermal_degree_seconds'], 0.)
        self.assertGreater(row['signed_AP_area_delta_c_s'], 0.)
        self.assertGreater(row['integrated_model_drive_delta_c'], 0.)
        self.assertGreater(row['delta_urgent_p95_ms'], 0.)
        self.assertGreater(row['delta_normal_mean_ms'], 0.)
        self.assertAlmostEqual(row['unknown_incremental_controller_cost_to_erase_J_gain_j'], .05246832320642625)
        self.assertIsNone(row['device_energy_gain'])

    def test_incomplete_denominator_and_false_joint_label_rejected(self):
        with TemporaryDirectory() as tmp:
            out = Path(tmp)/'source'; shutil.copytree(self.source, out)
            raw = [json.loads(z) for z in gzip.decompress((out/'records.jsonl.gz').read_bytes()).decode().splitlines()]
            def store(rows):
                (out/'records.jsonl.gz').write_bytes(gzip.compress(('\n'.join(json.dumps(z) for z in rows)+'\n').encode()))
            store(raw[:3])
            with self.assertRaisesRegex(ValueError, 'denominator'): report.load(out, self.witness)
            changed = copy.deepcopy(raw); changed[2]['meta']['exact_replay_joint_nonworsening'] = False
            store(changed)
            with self.assertRaisesRegex(ValueError, 'joint improvement label'): report.load(out, self.witness)

    def test_witness_claim_cannot_replace_actual_rounded_grid_evidence(self):
        with TemporaryDirectory() as tmp:
            out = Path(tmp)/'witness'; shutil.copytree(self.witness, out)
            path = out/'result.json'; result = json.loads(path.read_text(encoding='utf8'))
            result['records'][0]['proof']['planning_area_c_s'] += 1.
            path.write_text(json.dumps(result), encoding='utf8')
            with self.assertRaisesRegex(ValueError, 'witness grid proof'): report.load(self.source, out)

    def test_source_hash_change_blocks_readout(self):
        with TemporaryDirectory() as tmp:
            out = Path(tmp)/'source'; shutil.copytree(self.source, out)
            path = out/'registered_before_run.json'; data = json.loads(path.read_text(encoding='utf8'))
            key = next(iter(data['code'])); data['code'][key] = '0'*64
            path.write_text(json.dumps(data), encoding='utf8')
            with self.assertRaisesRegex(ValueError, 'hash mismatch'): report.load(out, self.witness)

    def test_saved_csv_curves_match_model_and_no_null_becomes_zero(self):
        with TemporaryDirectory() as tmp:
            result = report.load(self.source, self.witness); out = report.save(result, Path(tmp)/'out')
            with (out/'comparisons.csv').open(encoding='utf8', newline='') as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(len(rows), 4); self.assertEqual(rows[0]['delta_energy_j'], '')
            with (out/'modeled_paths.csv').open(encoding='utf8', newline='') as stream:
                curves = list(csv.DictReader(stream))
            for series, detail in [('saved EFT', 'reference_path'), ('offline incumbent', 'result_path')]:
                aps = [float(r['modeled_AP_c']) for r in curves if r['series'] == series and r['modeled_AP_c']]
                self.assertEqual(aps, result['details'][0][detail]['ap_path'])
                energies = [float(r['modeled_J']) for r in curves if r['series'] == series and r['modeled_J']]
                self.assertAlmostEqual(energies[-1], result['details'][0][detail]['whole_120s_j'])
            page = (out/'index.html').read_text(encoding='utf8')
            self.assertIn('미확인 / null', page)
            self.assertTrue((out/'modeled_paths.png').is_file())
            with self.assertRaises(FileExistsError): report.save(result, out)

    def test_arrived_EDF_construction_does_not_consult_future_jobs(self):
        controls = report.study.work.budget.readout.source.records(report.ROOT/'run_v1/records.jsonl.gz')
        control = next(r for r in controls if r['meta']['stage'] == report.study.work.budget.STAGE and
            r['meta']['policy'] == 'EFT_REFERENCE' and r['meta']['scenario'] == 'mean' and
            r['meta']['envelope'] == 'g0.45_c0.75_b4' and r['meta']['seed'] == 223001)
        tickets = report.study.followup.tickets(control)
        frozen, _ = report.P.inputs(report.P.BUNDLE); profile = report.P.profile(frozen, 'mean')
        first = min(tickets, key=lambda q: (q['arrival_ns'], q['ordinal']))
        jobs = witness.calendar(tickets, profile)
        self.assertEqual(jobs[0]['id'], first['id'])
        modified = copy.deepcopy(tickets)
        for q in modified:
            if q['arrival_ns'] > first['arrival_ns']: q['arrival_ns'] += int(100e9)
        self.assertEqual(witness.calendar(modified, profile)[0], jobs[0])
        self.assertTrue(all(j['backend'] == 'CPU' for j in jobs))
        self.assertEqual(len(jobs), 48)
        self.assertEqual(len({j['id'] for j in jobs}), 48)

    def test_actual_cli_isolated_from_adb_and_preserves_complete_denominator(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp); marker = root/'ADB_CALLED'
            trap = root/'adb.cmd'
            trap.write_text('@echo off\n(echo forbidden)>"'+str(marker)+'"\nexit /b 99\n', encoding='ascii')
            environment = dict(os.environ, PATH=str(root)+os.pathsep+os.environ['PATH'],
                ADB=str(trap), ADB_PATH=str(trap), PYTHONDONTWRITEBYTECODE='1')
            out = root/'result'
            run = subprocess.run([os.sys.executable, '-B', '-m', 'tools.d1_joint_calendar_report',
                '--source', str(self.source), '--witness', str(self.witness), '--output', str(out)],
                cwd=report.P.ROOT, env=environment, capture_output=True, text=True, timeout=30.)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertFalse(marker.exists())
            result = json.loads((out/'result.json').read_text(encoding='utf8'))
            self.assertEqual(len(result['rows']), 4)
            self.assertEqual(result['device_commands'], 0)
            self.assertEqual(result['analysis_code_sha256'], report.P.digest(report.__file__))


if __name__ == '__main__': unittest.main()
