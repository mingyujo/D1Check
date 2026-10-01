"""Bundled report entrypoint tests. Fake records are never new measurements."""
import json
import sys
import tempfile
import unittest
from contextlib import ExitStack,redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch
from tools import d1_ap_bundle_readout as readout
from tools import d1_ap_bundle_confirmation as bundle
from tools import d1_ap_transfer_confirmation as transfer
from tools import d1_ap_transfer_report as graphics
from tools import d1_arrival_energy_collection_device as runner
from tools import test_d1_ap_transfer_confirmation as fixtures


def save(file,value):
    file.parent.mkdir(parents=True,exist_ok=True)
    graphics.save(file,value)


def fixture(root):
    oldfile,first,frozen,freeze=fixtures.TransferTest()._fixture(root)
    original=transfer.p.read(oldfile)
    plan_dir=root/'plan';plan_dir.mkdir()
    second=root/'run/01_fixture2'
    import shutil
    shutil.copytree(first,second)
    entries=[]
    for i,role in enumerate(bundle.ROLES):
        folder=(first,second)[i];m={'phase':'PC fixture','session_id':folder.name[3:]}
        save(folder/'artifacts/manifest.json',m)
        target=plan_dir/f'manifest{i}.json';save(target,m)
        save(folder/'launch_attempt.json',{'status':'PC fixture only'})
        entries.append(dict(index=i,phase=role,session_id=folder.name[3:],
                            manifest=target.name,manifest_sha256=transfer.p.digest(target)))
    contract=plan_dir/'analysis_contract.json'
    save(contract,{'fixed_direction_windows_s':[[90,115],[120,145],[150,175]]})
    plan=original|dict(experiment_id=bundle.EXPERIMENT,source_code={'fixture':'isolated'},
        registry=str(root/'registry'),entries=entries,
        analysis_contract={'path':str(contract),'sha256':transfer.p.digest(contract)})
    plan_file=plan_dir/'collection_plan.json';save(plan_file,plan)
    stack=ExitStack()
    stack.enter_context(patch.object(bundle,'identity',return_value=plan['source_code']))
    stack.enter_context(patch.object(transfer,'FREEZE_SHA',transfer.p.digest(freeze)))
    stack.enter_context(patch.object(transfer.replay,'FROZEN_SHA',transfer.p.digest(frozen)))
    stack.enter_context(patch.object(runner,'ObservedDevice',side_effect=AssertionError('real ADB forbidden')))
    return plan_file,first,second,stack


class BundleReadoutTest(unittest.TestCase):
    def test_cli_two_sessions_csv_figures_html_and_source_preservation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);plan,first,second,stack=fixture(root)
            original={f:transfer.p.digest(f) for f in root.rglob('*') if f.is_file()}
            output=root/'report'
            with stack,patch.object(sys,'argv',['readout','--plan',str(plan),'--output',str(output),
                                               '--evidence-label','PC fixture - NOT MEASURED']),redirect_stdout(StringIO()):
                readout.main()
            result=transfer.p.read(output/'summary.json')
            self.assertEqual((result['readout_status'],result['evaluated_sessions']),('complete',2))
            self.assertIn('no new independent confirmation',result['data_role'])
            self.assertEqual(result['device_commands_by_analysis'],0)
            self.assertIsNone(result['policy_rank']);self.assertFalse(result['post_load_refit'])
            for item in result['sessions']:
                self.assertEqual(item['scores']['observed_energy_120s_j'],120.)
                self.assertEqual(item['independent_sessions'],0)
                self.assertEqual(item['rendering_status'],'completed')
                data=output/item['role'];graphics.validate_tables(data,item['scores'])
                for name in ('ap','energy'):
                    self.assertIn('PC TEST FIXTURE', (data/(name+'.svg')).read_text(encoding='utf-8'))
                    self.assertGreater((data/(name+'.png')).stat().st_size,5000)
                self.assertFalse((data/'lanes.svg').exists())
                self.assertIn(str(item['scores']['signed_energy_error_j']),
                              (output/'index.html').read_text(encoding='utf-8'))
            self.assertEqual(original,{f:transfer.p.digest(f) for f in original})
            self.assertFalse((root/'registry').exists())

    def test_stopped_bundle_keeps_first_score_and_second_denominator(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);plan,first,second,stack=fixture(root)
            import shutil
            shutil.rmtree(second) # Only isolated fake records, never original evidence.
            save(first.parent/'FINAL_RECEIPT.json',{'status':'stopped_no_resume','session_attempts':1,
                                                   'original_error':'fixture second stage'})
            with stack:result=readout.report(plan,root/'out',evidence_label='PC fixture')
            self.assertEqual(result['readout_status'],'partial')
            self.assertEqual(result['expected_sessions'],2)
            self.assertEqual(result['receipt']['original_error'],'fixture second stage')
            self.assertIsNotNone(result['sessions'][0]['scores'])
            self.assertEqual(result['sessions'][1]['status'],'unattempted')
            self.assertIsNone(result['sessions'][1]['scores'])
            self.assertEqual(result['consumption'][1]['counts']['request_start'],0)
            self.assertFalse((root/'out'/bundle.ROLES[1]).exists())

    def test_truncated_bytes_and_cleanup_error_preserve_prefix_and_primary_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);plan,first,second,stack=fixture(root)
            path=second/'artifacts/progress.jsonl'
            with path.open('ab') as stream:stream.write(b'{"kind":"request_start","broken":"\xe2\x82')
            (second/'artifacts/cleanup.json').write_bytes(b'{')
            save(first.parent/'FINAL_RECEIPT.json',{'status':'stopped_no_resume','original_error':'fixture closed'})
            digest=transfer.p.digest(path)
            with stack:result=readout.report(plan,root/'out',evidence_label='PC fixture')
            self.assertEqual(result['receipt']['original_error'],'fixture closed')
            self.assertEqual(result['readout_status'],'partial')
            self.assertIsNone(result['sessions'][1]['scores'])
            counts=result['consumption'][1]
            self.assertEqual(counts['progress_integrity']['status'],'partial_prefix')
            self.assertEqual(counts['app_cleanup']['status'],'unreadable')
            self.assertEqual(transfer.p.digest(path),digest)
            self.assertTrue((root/'out/summary.json').exists())

    def test_launch_without_recovered_progress_is_unknown_not_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);plan,first,second,stack=fixture(root)
            (second/'artifacts/progress.jsonl').unlink()
            (second/'validated.json').unlink()
            with stack:result=readout.report(plan,root/'out',evidence_label='PC fixture')
            self.assertTrue(result['consumption'][1]['launch_attempted'])
            self.assertIsNone(result['consumption'][1]['counts']['request_start'])
            self.assertIsNone(result['sessions'][1]['scores'])

    def test_missing_session_without_attempt_receipt_does_not_establish_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);plan,first,second,stack=fixture(root)
            import shutil
            shutil.rmtree(second)
            with stack:result=readout.report(plan,root/'out',evidence_label='PC fixture')
            self.assertEqual(result['sessions'][1]['status'],'incomplete_or_ineligible')
            self.assertIsNone(result['consumption'][1]['counts']['request_start'])

    def test_unterminated_valid_json_and_bad_middle_row_are_prefix_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            file=Path(tmp)/'progress.jsonl'
            for tail in (b'{"kind":"request_start"}',b'{}\nnot-json\n{"kind":"request_start"}\n'):
                file.write_bytes(b'{"kind":"warmup_start"}\n'+tail)
                records,status=readout.progress_prefix(file)
                self.assertEqual(status['status'],'partial_prefix')
                self.assertEqual(sum(r.get('kind')=='request_start' for r in records),0)

    def test_sensor_missing_values_do_not_create_whole_window_scores(self):
        for mode in ('power_gap','ap_gap'):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);plan,first,second,stack=fixture(root)
                if mode=='power_gap':
                    file=second/'artifacts/progress.jsonl'
                    rows=[json.loads(r) for r in file.read_text().splitlines()]
                    for r in rows:
                        if r.get('snapshot_start_ns')==160_000_000_000:r['current_valid']=False
                else:
                    file=second/'thermal.jsonl'
                    rows=[json.loads(r) for r in file.read_text().splitlines()]
                    for r in rows:
                        if 160_000_000_000<=r['before_ns']<180_000_000_000:r['AP']=''
                file.write_text(''.join(json.dumps(r)+'\n' for r in rows),encoding='utf-8')
                with stack:result=readout.report(plan,root/'out',evidence_label='PC fixture')
                self.assertEqual(result['readout_status'],'partial')
                self.assertIsNone(result['sessions'][1]['scores'])
                self.assertFalse(list((root/'out'/bundle.ROLES[1]).glob('*.svg')))

    def test_rendering_failure_keeps_numeric_scores_as_separate_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);plan,first,second,stack=fixture(root)
            with stack,patch.object(graphics,'figures',side_effect=OSError('fixture disk failure')):
                result=readout.report(plan,root/'out',evidence_label='PC fixture')
            self.assertEqual(result['readout_status'],'complete')
            for item in result['sessions']:
                self.assertEqual(item['rendering_status'],'failed')
                self.assertEqual(item['scores']['observed_energy_120s_j'],120.)
                self.assertTrue((root/'out'/item['role']/'rendering_error.txt').exists())
            self.assertNotIn('<img',(root/'out/index.html').read_text(encoding='utf-8'))

    def test_processing_failure_keeps_original_receipt_and_other_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);plan,first,second,stack=fixture(root)
            original=readout.transfer.readout_session
            def fail_first(file,plan,entry,output):
                if entry['index']==0:raise RuntimeError('fixture processing')
                return original(file,plan,entry,output)
            with stack,patch.object(readout.transfer,'readout_session',side_effect=fail_first):
                result=readout.report(plan,root/'out',evidence_label='PC fixture')
            self.assertEqual(result['sessions'][0]['status'],'analysis_processing_failed')
            self.assertIn('fixture processing',result['sessions'][0]['original_stack'])
            self.assertIsNotNone(result['sessions'][1]['scores'])
            self.assertEqual(result['receipt']['status'],'completed_descriptive_only')

    def test_changed_contract_and_protected_paths_fail_before_writing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);file,first,second,stack=fixture(root)
            with stack:
                for dest in (root/'run/out',root/'registry/out',file.parent/'out'):
                    with self.assertRaisesRegex(ValueError,'protected'):readout.report(file,dest)
                contract=Path(transfer.p.read(file)['analysis_contract']['path'])
                contract.write_bytes(contract.read_bytes()+b' ')
                with self.assertRaisesRegex(ValueError,'contract changed'):readout.report(file,root/'out')
            self.assertFalse((root/'out').exists())


if __name__=='__main__':unittest.main()
