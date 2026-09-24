import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from tools import d1_arrival_failure_evidence as e
from tools import d1_arrival_timing_calibration_device as d
from tools import d1_arrival_timing_calibration as c


class FailureEvidenceTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.manifest=dict(session_id='s', requests=[dict(request_id='q0'),dict(request_id='q1')],
                           warmup_requests=[dict(request_id='w0'),dict(request_id='w1')])

    def row(self, sequence, stage, edge, rid=None):
        return c.p.canonical(dict(protocol=e.CONTRACT,session_id='s',manifest_sha256=e.p_hash(self.manifest),
               sequence=sequence,mono_ns=sequence,stage=stage,edge=edge,request_id=rid,performance_excluded=True))

    def test_missing_and_torn_journal_preserve_unknown_denominator(self):
        missing=e.summarize_journal(b'',self.manifest)
        self.assertEqual(missing['diagnostic']['actual_call_bounds'],[0,2])
        data=self.row(0,'warmup','start','w0')+self.row(1,'warmup','succeeded','w0')+self.row(2,'warmup','start','w1')+b'{"partial"'
        result=e.summarize_journal(data,self.manifest)
        self.assertIsNotNone(result['invalid_suffix'])
        self.assertEqual(result['warmup']['adapter_returned'],1)
        self.assertEqual(result['warmup']['intents_without_terminal'],1)
        self.assertEqual(result['warmup']['actual_call_bounds'],[1,2])

    def test_runtime_failure_and_cancel_do_not_invent_calls(self):
        data=self.row(0,'runtime_create','start')+self.row(1,'runtime_wait','failed')+self.row(2,'session','stopped')
        result=e.summarize_journal(data,self.manifest)
        self.assertEqual(result['warmup']['durable_start_intents'],0)
        self.assertEqual(result['warmup']['no_start_evidence'],2)
        self.assertEqual(result['last_record']['edge'],'stopped')
        self.assertEqual(result['warmup']['actual_call_bounds'],[0,2])

    def test_orphan_completion_retry_and_wrong_identity_rejected(self):
        with self.assertRaisesRegex(ValueError,'orphan'):
            e.summarize_journal(self.row(0,'diagnostic','succeeded','q0'),self.manifest)
        with self.assertRaisesRegex(ValueError,'duplicate'):
            e.summarize_journal(self.row(0,'diagnostic','start','q0')+self.row(1,'diagnostic','start','q0'),self.manifest)
        corrupted=json.loads(self.row(0,'diagnostic','start','q0'));corrupted['session_id']='other'
        result=e.summarize_journal(c.p.canonical(corrupted),self.manifest)
        self.assertEqual(result['valid_prefix_records'],0);self.assertIsNotNone(result['invalid_suffix'])

    def test_exact_manifest_bytes_not_reserialization_define_identity(self):
        import hashlib
        raw=json.dumps(self.manifest,indent=4).encode('utf-8')
        digest=hashlib.sha256(raw).hexdigest()
        row=json.loads(self.row(0,'diagnostic','start','q0'))
        row['manifest_sha256']=digest
        data=json.dumps(row).encode()+b'\n'
        self.assertEqual(e.summarize_journal(data,self.manifest,digest)['valid_prefix_records'],1)
        self.assertEqual(e.summarize_journal(data,self.manifest)['valid_prefix_records'],0)

    def test_capture_failures_bounded_read_only_and_deadline_restored(self):
        dev=Mock();dev.deadline=1000
        dev.call.side_effect=[RuntimeError('connection lost')]+[SimpleNamespace(returncode=0,stdout=b'evidence',stderr=b'')]*4
        with patch.object(e.time,'monotonic',return_value=100):
            result=e.collect_failure(dev,self.root/'capture','42')
        self.assertEqual(dev.deadline,1000)
        self.assertEqual(result['commands'][0]['status'],'capture_failed')
        self.assertEqual(len(result['commands']),5)
        self.assertTrue(all(x.kwargs['timeout']==2 for x in dev.call.call_args_list))
        self.assertFalse(any(x.args[0] in ('install','push') or 'force-stop' in x.args for x in dev.call.call_args_list))
        exhausted=Mock();exhausted.deadline=99
        with patch.object(e.time,'monotonic',return_value=100):
            result=e.collect_failure(exhausted,self.root/'exhausted','42')
        exhausted.call.assert_not_called();self.assertTrue(all(x['status']=='skipped_budget' for x in result['commands']))

    def test_capture_and_pull_errors_separate_and_cleanup_not_blocked(self):
        dev=Mock();dev.deadline=1000;cleaned=False
        try:
            with patch.object(d.failure_evidence,'collect_failure',side_effect=OSError('local disk failed')), patch.object(d,'pull',side_effect=RuntimeError('ADB lost')), patch.object(d.time,'monotonic',return_value=100):
                d.failed_attempt_evidence(dev,'s',self.root,'42')
        finally:
            cleaned=True
        self.assertTrue(cleaned);self.assertEqual(dev.deadline,1000)
        self.assertTrue((self.root/'evidence_capture_error.json').exists())
        self.assertTrue((self.root/'recovery_error.json').exists())

    def test_poll_timeout_is_not_missing_file_or_application_crash(self):
        dev=Mock();dev.call.return_value=SimpleNamespace(returncode=1,stdout=b'',stderr=b'')
        with patch.object(d.time,'monotonic',side_effect=[0,0,126]), patch.object(d.time,'sleep'):
            with self.assertRaisesRegex(TimeoutError,'app outcome unknown'):
                d.wait_for_cleanup(dev,'output')
        dev.call.return_value=SimpleNamespace(returncode=0,stdout=b'',stderr=b'')
        d.wait_for_cleanup(dev,'output')

    def test_pull_connection_failure_not_misreported_as_no_app_output(self):
        dev=Mock();dev.call.return_value=SimpleNamespace(returncode=1,stdout=b'',stderr=b'device offline')
        with self.assertRaisesRegex(RuntimeError,'listing unavailable'):
            d.pull(dev,'s',self.root/'partial')
        dev.call.return_value.stderr=b'No such file or directory'
        self.assertEqual(d.pull(dev,'s',self.root/'partial')['status'],'output_missing')

    def test_durable_diagnosis_never_enters_calibration_fit(self):
        c.write_new(self.root/'manifest.json',dict(self.manifest,failure_diagnostic_contract=e.CONTRACT,performance_excluded=True))
        with self.assertRaisesRegex(ValueError,'not calibration/performance'):
            c.observations(self.root)

    def test_real_runner_timeout_with_recovery_failure_still_cleans_and_stops(self):
        apk=self.root/'test.apk';apk.write_bytes(b'synthetic')
        manifest=self.root/'manifest.json';c.write_new(manifest,{})
        plan=dict(protocol=c.PROTOCOL,experiment_id=c.EXPERIMENT,apk_path=str(apk),apk_sha256=c.p.digest(apk),
            registry=str(self.root/'registry'),host_phase_wall_seconds=3600,device_fingerprint='fake',
            initial_cool_seconds=0,source_files={},entries=[dict(index=0,phase='development',session_id='s',manifest='manifest.json')])
        path=self.root/'plan.json';c.write_new(path,plan)
        dev=Mock();dev.identify.return_value={'model':'fake'}
        def call(*args,**kwargs):
            content=b'42' if 'pidof' in args else b'Thermal Status: 0' if 'thermalservice' in args else b'ok'
            return SimpleNamespace(returncode=0,stdout=content,stderr=b'')
        dev.call.side_effect=call
        with patch.object(c,'check'), patch.object(d.legacy,'Device',return_value=dev), patch.object(d.legacy,'bounded_cool'), patch.object(d.legacy,'battery_gate'), patch.object(d.legacy,'require_stopped'), patch.object(d,'stage_inputs',return_value='remote'), patch.object(d,'wait_for_cleanup',side_effect=TimeoutError('injected app outcome unknown')), patch.object(e,'collect_failure',side_effect=OSError('evidence disk')), patch.object(d,'pull',side_effect=RuntimeError('offline')), patch.object(d,'cleanup',return_value={'status':'completed'}) as cleanup:
            with self.assertRaises(TimeoutError):
                d.run(path,'development',self.root/'run','unused','unused',16,c.p.digest(path))
        cleanup.assert_called_once()
        folder=self.root/'run/00_s'
        self.assertEqual(c.p.read(folder/'error.json')['host_stage'],'completion_poll')
        self.assertTrue((folder/'recovery_error.json').exists())
        self.assertTrue((folder/'host_cleanup.json').exists())
        self.assertEqual(c.p.read(self.root/'run/stopped.json')['completed'],0)


if __name__ == '__main__':
    unittest.main()
