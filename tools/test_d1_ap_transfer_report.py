"""PC report integration fixtures; never measurements or device stability evidence."""
import csv
import json
import sys
import tempfile
import unittest
from contextlib import ExitStack, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from tools import d1_ap_transfer_report as report
from tools import d1_ap_transfer_confirmation as transfer
from tools import d1_arrival_energy_collection_device as runner
from tools import test_d1_ap_transfer_confirmation as fixtures


class ReportTest(unittest.TestCase):
    def fixture(self, root):
        plan, folder, frozen, freeze = fixtures.TransferTest()._fixture(root)
        artifact = folder/'artifacts'
        requests = json.loads((artifact/'requests.json').read_text())
        design = []
        for i, r in enumerate(requests):
            r['request_id'] = 'test-'+str(i)
            q = dict(request_id=r['request_id'], ordinal=i, task_id=r['task_id'],
                     recorded_backend=r['selected_backend'], offset_ms=35000,
                     release_offset_ns=r['dispatch_ns']-100_000_000_000)
            for key in ('execution_start_ns', 'output_ready_ns', 'persist_complete_ns',
                        'worker_release_ns', 'lane_available_ns'):
                q['pc_'+key] = r[key]-100_000_000_000
            design.append(q)
        (artifact/'requests.json').write_text(json.dumps(requests))
        input_file = root/'input.json'; input_file.write_text(json.dumps(dict(requests=design)))
        p = json.loads(plan.read_text())
        p.update(registry=str(root/'registry'), input_bundle=dict(path=str(input_file),
                 sha256=transfer.p.digest(input_file)))
        plan.unlink()
        plan_dir=root/'plan';plan_dir.mkdir()
        (root/'manifest.json').rename(plan_dir/'manifest.json')
        plan=plan_dir/'collection_plan.json';plan.write_text(json.dumps(p))
        stack = ExitStack()
        stack.enter_context(patch.object(transfer, 'identity', return_value={'fixture':'isolated'}))
        stack.enter_context(patch.object(transfer.replay, 'FROZEN_SHA', transfer.p.digest(frozen)))
        stack.enter_context(patch.object(transfer, 'FREEZE_SHA', transfer.p.digest(freeze)))
        stack.enter_context(patch.object(runner, 'ObservedDevice', side_effect=AssertionError('real ADB forbidden')))
        return plan, folder, stack

    def test_cli_to_readout_csv_svg_and_html_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); plan, folder, stack = self.fixture(root)
            original = {f:transfer.p.digest(f) for f in root.rglob('*') if f.is_file()}
            out = root/'report'
            with stack, patch.object(sys, 'argv', ['report','--plan',str(plan),'--output',str(out)]), redirect_stdout(StringIO()):
                self.assertEqual(report.main(), 0)
            result = json.loads((out/'report.json').read_text())
            self.assertEqual(result['status'], 'report_complete_diagnostic_only')
            self.assertEqual(result['device_commands'], 0)
            self.assertEqual(result['observed_energy_120s_j'], 120.)
            self.assertIsNone(result['policy_rank']); self.assertIsNone(result['accuracy_pass'])
            for name in ('lanes','energy','ap'):
                self.assertIn('<svg', (out/(name+'.svg')).read_text(encoding='utf-8'))
                self.assertGreater((out/(name+'.png')).stat().st_size, 5000)
            html = (out/'index.html').read_text(encoding='utf-8')
            self.assertIn(str(result['signed_energy_error_j']), html)
            self.assertIn('부하 후 관측은 점수에만', html)
            table = report.rows(out/'timing.csv')
            self.assertEqual(len(table),24)
            self.assertTrue(all(float(r['lane_delta_vs_pc_s'])==0. for r in table))
            self.assertEqual(original, {f:transfer.p.digest(f) for f in original})
            self.assertFalse((root/'registry').exists())
            inventory = json.loads((out/'inventory.json').read_text())
            self.assertTrue(all(not Path(r['file']).is_absolute() for r in inventory))

    def test_failed_receipt_is_null_no_curves_and_original_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); plan, folder, stack=self.fixture(root)
            receipt=folder.parent/'FINAL_RECEIPT.json'
            receipt.write_text(json.dumps(dict(status='stopped_no_resume',original_error='closed')))
            sha=transfer.p.digest(receipt)
            with stack: result=report.report(plan,root/'out',evidence_label='PC fixture only')
            self.assertEqual(result['status'],'not_evaluable')
            self.assertIsNone(result['observed_energy_120s_j'])
            self.assertIn('not a completed',result['reason'])
            self.assertFalse(list((root/'out').glob('*.svg')))
            self.assertEqual(sha,transfer.p.digest(receipt))
            with self.assertRaises(FileExistsError): report.report(plan,root/'out')

    def test_sensor_gap_and_missing_ap_do_not_become_zero(self):
        for mode in ('power_gap','missing_ap'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp); plan, folder, stack=self.fixture(root)
                if mode=='power_gap':
                    file=folder/'artifacts/progress.jsonl'; lines=[json.loads(s) for s in file.read_text().splitlines()]
                    for r in lines:
                        if r.get('snapshot_start_ns')==160_000_000_000:r['current_valid']=False
                else:
                    file=folder/'thermal.jsonl'; lines=[json.loads(s) for s in file.read_text().splitlines()]
                    for r in lines:
                        if r['before_ns']>=135_100_000_000:r['AP']=''
                file.write_text(''.join(json.dumps(r)+'\n' for r in lines))
                with stack: result=report.report(plan,root/'out')
                self.assertEqual(result['status'],'not_evaluable')
                self.assertIsNone(result['signed_energy_error_j'])
                self.assertEqual(result['comparison_figures'],0)

    def test_score_boundary_guard_and_timing_error_preserve_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); plan, folder, stack=self.fixture(root)
            with stack:
                summary=transfer.readout(plan,root/'data')
                # Last in-window sample at 119 s cannot be called a full 120 s prediction.
                energy=report.rows(root/'data/energy_path.csv'); energy[-1]['elapsed_s']='119'
                report.csv_write(root/'data/energy_path.csv',energy)
                with self.assertRaisesRegex(ValueError,'boundary'):
                    report.validate_tables(root/'data',summary)
                r=transfer.p.read(folder/'artifacts/requests.json');r[0]['selected_backend']='GPU'
                report.save(folder/'artifacts/requests.json',r)
                with self.assertRaisesRegex(ValueError,'task/backend'):
                    report.timing(plan,transfer.p.read(plan),100_000_000_000)
                result=report.report(plan,root/'out')
                self.assertEqual(result['status'],'not_evaluable')
                self.assertFalse(list((root/'out').glob('*.svg')))

    def test_protected_destinations_and_processing_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); plan, folder, stack=self.fixture(root)
            with stack:
                for output in (root/'run/report',root/'registry/report',plan.parent/'report'):
                    with self.assertRaisesRegex(ValueError,'cannot write'):
                        report.report(plan,output)
                with patch.object(transfer,'readout',side_effect=RuntimeError('implementation error')):
                    result=report.report(plan,root/'out')
                self.assertEqual(result['status'],'processing_error')

    def test_rendering_error_preserves_validated_scores_as_separate_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);plan,folder,stack=self.fixture(root)
            with stack, patch.object(report,'figures',side_effect=OSError('rendering fixture failure')):
                with self.assertRaisesRegex(OSError,'rendering fixture'):
                    report.report(plan,root/'out')
            result=json.loads((root/'out/report.json').read_text())
            self.assertEqual(result['status'],'rendering_failed')
            self.assertEqual(result['observed_energy_120s_j'],120.)
            self.assertTrue((root/'out/rendering_error.txt').is_file())
            self.assertFalse((root/'out/index.html').exists())

    def test_irregular_sensor_end_is_integrated_at_exact120_without_refit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);plan,folder,stack=self.fixture(root)
            file=folder/'artifacts/progress.jsonl';records=[json.loads(s) for s in file.read_text().splitlines()]
            last=records[-1]
            last['snapshot_start_ns']=last['sensor_read_end_ns']=219_500_000_000
            records.append(dict(last,snapshot_start_ns=220_500_000_000,sensor_read_end_ns=220_500_000_000))
            file.write_text(''.join(json.dumps(r)+'\n' for r in records))
            original=transfer.p.digest(file)
            with stack:result=report.report(plan,root/'out',evidence_label='PC fixture only')
            self.assertEqual(result['status'],'report_complete_diagnostic_only')
            data=root/'out/data'
            old=json.loads((data/'summary.json').read_text())
            self.assertEqual(old['predicted_energy_120s_j'],result['predicted_energy_120s_j'])
            self.assertEqual(float(report.rows(data/'frozen_reader_energy_path.csv')[-1]['elapsed_s']),119.5)
            self.assertAlmostEqual(result['observed_energy_120s_j'],120.)
            self.assertEqual(float(report.rows(data/'energy_path.csv')[-1]['elapsed_s']),120.)
            self.assertEqual(original,transfer.p.digest(file))


if __name__=='__main__': unittest.main()
