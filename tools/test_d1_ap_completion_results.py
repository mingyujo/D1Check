import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from tools import d1_ap_completion_results as r


class ResultsTests(unittest.TestCase):
    def test_query_purpose_and_absence_are_separate(self):
        self.assertEqual(r.command_kind(['adb','-s','FIXTURE','exec-out','cat','/proc/uptime']),'uptime')
        self.assertEqual(r.command_kind(['adb','-s','FIXTURE','shell','test','-e','newpath']),'fresh_path_probe')
        self.assertEqual(r.command_kind(['adb','devices','-l']),'identity_environment_launch_other')

    def test_timeout_censoring_and_sequential_boundaries(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for i,status in enumerate(['returned','timeout']):
                folder=root/f'{i:04d}'/'client';folder.mkdir(parents=True)
                r.study.common.write_json(folder/'result.json',dict(command=['adb','-s','FIXTURE','exec-out','cat','/proc/uptime'],
                    status=status,returncode=0 if not i else 1,utc_start='fixture',utc_end='fixture',
                    elapsed_seconds=.1 if not i else 2.,timeout_seconds=2,stdout_bytes=0,stderr_bytes=0,
                    monotonic_start=i*3.,monotonic_end=i*3.+(.1 if not i else 2.)))
            result=r.commands(root);g=result['groups'][0]
            self.assertEqual((g['count'],g['timeouts'],g['median_s'],result['overlap_slots']),(2,1,.1,[]))
            self.assertAlmostEqual(g['client_wait_sum_s'],2.1)

    def test_failed_preflight_no_target_chart_or_missing_as_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);planroot=root/'plan';planroot.mkdir();block=planroot/'development';block.mkdir()
            run=root/'run';(run/'development').mkdir(parents=True)
            plan=dict(output_root=str(run),registry=str(root/'registry'),budget={},source_code={})
            r.study.common.write_json(planroot/'study_plan.json',plan)
            r.study.common.write_json(run/'FINAL_RECEIPT.json',dict(status='stopped_no_resume',elapsed_seconds=1))
            row=dict(index=0,session_id='fixture',phase='development_0_C',condition='C',requests=0)
            r.study.common.write_json(block/'collection_plan.json',dict(output_root=str(run/'development'),entries=[row]))
            r.study.common.write_json(run/'development/FINAL_RECEIPT.json',dict(status='stopped_no_resume',
                session_attempts=0,completed_sessions=0,adb_commands=0,elapsed_seconds=1))
            with patch.object(r.study,'verify_sources'),patch('subprocess.Popen',side_effect=AssertionError('no device')):
                result=r.analyse(planroot/'study_plan.json',root/'pc')
            self.assertFalse(result['model_fit_performed']);self.assertFalse(result['confirmation_attempted'])
            self.assertNotIn(',0.0,',(root/'pc/sessions.csv').read_text())
            self.assertEqual(len((root/'pc/ap_paths.csv').read_text().splitlines()),1)


if __name__=='__main__':unittest.main()
