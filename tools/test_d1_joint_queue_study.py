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
from tools import d1_joint_queue_report as report


class JointQueueStudyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.source = report.ROOT/'joint_queue_area_v1'

    def test_fixed_candidate_parameters_and_complete_paired_scope(self):
        spec = report.study.specification()
        self.assertEqual(spec['parameter_candidates'], 1)
        self.assertEqual(spec['maximum_PC_runs'], 12)
        self.assertEqual(spec['seeds'], [523001, 523002])
        with (patch.object(report.study.candidate, 'simulate', side_effect=AssertionError('no replay')),
              patch.object(report.study.candidate.x, 'simulate', side_effect=AssertionError('no EFT rerun'))):
            result = report.analyze(self.source)
        self.assertEqual(len(result['rows']), 6)
        self.assertEqual(sum(r['deadline_met'] for r in result['rows']), 288)
        self.assertEqual(sum(r['joint_nonworsening'] for r in result['rows']), 0)
        self.assertTrue(all(r['delta_energy_j'] > 0 and r['delta_peak_ap_c'] < 0 for r in result['rows']))
        self.assertFalse(result['physical_advantage_proven'])
        self.assertFalse(result['independent_prediction_validation'])

    def test_energy_identity_distinguishes_assignment_and_overlap_cost(self):
        rows = report.analyze(self.source)['rows']
        for row in rows:
            self.assertAlmostEqual(row['energy_from_changed_GPU_assignments_j']+row['energy_from_changed_overlap_j'], row['delta_energy_j'], places=7)
            self.assertLess(row['delta_GPU_assignments'], 0)
            self.assertLess(row['delta_pair_overlap_s'], 0)
            self.assertGreater(row['energy_from_changed_overlap_j'], 0.)
            self.assertIsNone(row['EFT_PC_callback_total_s'])
            self.assertIsNone(row['actual_device_controller_delta_j'])
            self.assertFalse(row['local_guard_pass_is_global_guarantee'])

    def test_partial_denominator_and_changed_input_hash_rejected(self):
        with TemporaryDirectory() as tmp:
            out = Path(tmp)/'source'; shutil.copytree(self.source, out)
            records = gzip.decompress((out/'records.jsonl.gz').read_bytes()).splitlines()
            (out/'records.jsonl.gz').write_bytes(gzip.compress(b'\n'.join(records[:-1])))
            with self.assertRaisesRegex(ValueError, 'denominator'): report.analyze(out)
            (out/'inputs.json').write_text('[]', encoding='utf8')
            with self.assertRaisesRegex(ValueError, 'input hash'): report.analyze(out)

    def test_future_guard_ticket_and_false_local_veto_pass_rejected(self):
        with TemporaryDirectory() as tmp:
            out = Path(tmp)/'source'; shutil.copytree(self.source, out)
            records = [json.loads(r) for r in gzip.decompress((out/'records.jsonl.gz').read_bytes()).decode().splitlines()]
            def store(raw):
                (out/'records.jsonl.gz').write_bytes(gzip.compress((''.join(json.dumps(r)+'\n' for r in raw)).encode()))
            changed = copy.deepcopy(records)
            candidate = next(r for r in changed if r['meta']['policy'] == report.study.candidate.LABEL)
            candidate['guards'][0]['arrived_ids'].append(candidate['ledger'][-1]['id'])
            store(changed)
            with self.assertRaisesRegex(ValueError, 'future arrival leaked'): report.analyze(out)
            changed = copy.deepcopy(records)
            candidate = next(r for r in changed if r['meta']['policy'] == report.study.candidate.LABEL)
            guard = next(g for g in candidate['guards'] if g.get('selected_sequence'))
            guard['prediction']['future_rectified_AP_area_c_s'] = guard['reference']['future_rectified_AP_area_c_s']+1.
            store(changed)
            with self.assertRaisesRegex(ValueError, 'local joint guard'): report.analyze(out)

    def test_failed_study_preserves_first_run_and_original_stack(self):
        with TemporaryDirectory() as tmp, patch.object(report.study.candidate, 'simulate', side_effect=RuntimeError('original candidate failure')):
            out = Path(tmp)/'failed'
            with self.assertRaisesRegex(RuntimeError, 'original candidate failure'): report.study.run(out)
            error = json.loads((out/'PC_FAILURE.json').read_text(encoding='utf8'))
            self.assertEqual(error['completed_runs'], 1)
            self.assertIn('RuntimeError: original candidate failure', error['stack'])
            self.assertEqual(len(gzip.decompress((out/'records.jsonl.gz').read_bytes()).splitlines()), 1)
            self.assertFalse((out/'summary.json').exists())

    def test_consumed_output_path_reexecution_blocked(self):
        with TemporaryDirectory() as tmp, patch.object(report.study.candidate, 'simulate', side_effect=AssertionError('must not run')):
            with self.assertRaises(FileExistsError): report.study.run(tmp)

    def test_csv_curve_full_window_and_ap_differences_match_source(self):
        with TemporaryDirectory() as tmp:
            result = report.analyze(self.source); out = report.save(result, Path(tmp)/'out')
            with (out/'modeled_difference_paths.csv').open(encoding='utf8', newline='') as stream:
                curves = list(csv.DictReader(stream))
            for row in result['rows']:
                matched = [r for r in curves if int(r['seed']) == row['seed'] and r['scenario'] == row['scenario']]
                end = next(r for r in matched if r['time_s'] == '120' and r['delta_modeled_J'])
                self.assertAlmostEqual(float(end['delta_modeled_J']), row['delta_energy_j'], places=8)
                self.assertEqual(len([r for r in matched if r['delta_modeled_AP_c']]), 146)
            self.assertTrue((out/'modeled_differences.png').is_file())
            with self.assertRaises(FileExistsError): report.save(result, out)

    def test_actual_readonly_entry_under_fake_adb_trap(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp); marker = root/'ADB_CALLED'; trap = root/'adb.cmd'
            trap.write_text('@echo off\n(echo forbidden)>"'+str(marker)+'"\nexit /b 99\n', encoding='ascii')
            environment = dict(os.environ, PATH=str(root)+os.pathsep+os.environ['PATH'], ADB=str(trap), ADB_PATH=str(trap))
            out = root/'out'
            run = subprocess.run([os.sys.executable, '-B', '-m', 'tools.d1_joint_queue_report', '--source', str(self.source),
                '--output', str(out)], cwd=report.P.ROOT, env=environment, capture_output=True, text=True, timeout=30.)
            self.assertEqual(run.returncode, 0, run.stderr); self.assertFalse(marker.exists())
            data = json.loads((out/'result.json').read_text(encoding='utf8'))
            self.assertEqual(data['new_simulations'], 0); self.assertEqual(data['device_commands'], 0)
            self.assertEqual(len(data['rows']), 6)


if __name__ == '__main__': unittest.main()
