import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from tools import d1_arrival_initialization as n
from tools import d1_arrival_timing_calibration_device as d
from tools import d1_apk_identity as apk


class InitializationTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)

    def test_prepare_and_dry_run_zero_device_and_zero_calls(self):
        candidate=self.root/'candidate.apk';candidate.write_bytes(b'PC test fixture')
        manifest=dict(session_id='parent',requests=[{'request_id':'old'}],warmup_requests=[{'request_id':'warm','model_key':'classification_CPU'}],
                      models={k:dict(identity={},target={}) for k in n.ORDER})
        n.c.write_new(self.root/'old.json',manifest)
        tool=self.root/'tool';tool.write_bytes(b'fake')
        identity=dict(apk_sha256=n.p.digest(candidate),package='fake',version_code=1,signer_sha256='a'*64)
        parent=dict(entries=[dict(manifest='old.json',manifest_sha256=n.p.digest(self.root/'old.json'),session_id='parent')],
                    apk_preflight=dict(candidate=identity,toolchain={'java':str(tool)},tool_sha256={'java':n.p.digest(tool)}),
                    source_files={},device_fingerprint='fake',battery_start_percent=55,battery_min_percent=30,
                    battery_max_temperature_tenths_c=350,require_unplugged=True)
        n.c.write_new(self.root/'parent.json',parent)
        n.c.write_new(self.root/'receipt.json',dict(apk_sha256=n.p.digest(candidate),status='built_not_device_verified',source_code={'source':'hash'}))
        with patch.object(n,'PARENT_SHA',n.p.digest(self.root/'parent.json')),patch.object(n,'code_identity',return_value={'source':'hash'}),patch.object(apk,'inspect',return_value=identity),patch.object(n.legacy,'Device',side_effect=AssertionError('no device')) as device:
            report=n.prepare(self.root/'parent.json',candidate,self.root/'receipt.json',self.root/'plan')
            self.assertEqual(report['adb_calls'],0);self.assertEqual(report['generated_measurements'],0)
            planned=n.p.read(self.root/'plan/manifest.json')
            self.assertEqual(planned['requests'],[]);self.assertEqual(planned['warmup_requests'],[])
            self.assertEqual(planned['failure_diagnostic_scope'],'setup_only')
            self.assertFalse((self.root/'runtime_initialization_run_v1').exists());device.assert_not_called()
            extra=n.prepare(self.root/'parent.json',candidate,self.root/'receipt.json',self.root/'first-plan',scope='first_warmup')
            first_plan=n.p.read(self.root/'first-plan/initialization_plan.json')
            first_manifest=n.p.read(self.root/'first-plan/manifest.json')
            self.assertEqual(extra['budget']['warmup_calls'],1)
            self.assertEqual(extra['budget']['inference_calls'],1)
            self.assertEqual(first_manifest['requests'],[])
            self.assertEqual([q['model_key'] for q in first_manifest['warmup_requests']],['classification_CPU'])
            self.assertNotEqual(first_plan['registry'],n.p.read(self.root/'plan/initialization_plan.json')['registry'])
            self.assertFalse((self.root/'first_warmup_run_v1').exists())
            device.assert_not_called()
            planned['warmup_requests']=[{}];(self.root/'plan/manifest.json').write_bytes(n.p.canonical(planned))
            with self.assertRaisesRegex(ValueError,'manifest changed'):n.check(self.root/'plan/initialization_plan.json')

    def test_single_use_claim_even_if_output_changed(self):
        plan=dict(experiment_id=n.EXPERIMENT,budget=n.BUDGET,output_root=str(self.root/'run'),registry=str(self.root/'registry'))
        path=self.root/'plan.json';n.c.write_new(path,plan)
        n.claim(plan,path)
        plan['output_root']=str(self.root/'other')
        with self.assertRaisesRegex(ValueError,'consumed'):n.claim(plan,path)

    def artifacts(self,completed=4,torn=False):
        folder=self.root/'artifacts';folder.mkdir()
        manifest=dict(session_id='s',requests=[],warmup_requests=[],failure_diagnostic_scope='setup_only')
        n.c.write_new(folder/'manifest.json',manifest);sha=n.p.digest(folder/'manifest.json');rows=[]
        def add(stage,edge,key=None):
            rows.append(dict(protocol=n.evidence.CONTRACT,session_id='s',manifest_sha256=sha,sequence=len(rows),
                             mono_ns=len(rows),stage=stage,edge=edge,model_key=key,thread_id=1 if key and key.endswith('CPU') else 2,
                             performance_excluded=True,detail='before_runtime_creation/admit: {}'))
        for i,key in enumerate(n.ORDER):
            add('admission','observed',key);add('runtime_create','start',key)
            if i>=completed:break
            add('runtime_create','succeeded',key)
        if completed==4:add('setup_only','succeeded');add('cleanup','succeeded')
        else:add('runtime_wait','timeout',n.ORDER[completed])
        raw=b''.join(n.p.canonical(row) for row in rows)+(b'{"incomplete"' if torn else b'')
        (folder/'failure_progress.jsonl').write_bytes(raw)
        n.c.write_new(folder/'cleanup.json',dict(status='completed' if completed==4 else 'failed'))
        return folder,sha

    def test_partial_creation_preserves_prefix_and_unknown_attempts(self):
        folder,sha=self.artifacts(2,True);report=n.inspect_artifacts(folder,sha)
        self.assertEqual(report['runtime_start_intents'],3);self.assertEqual(report['runtime_returned'],2)
        self.assertEqual(report['runtime_actual_attempt_bounds'],[2,4]);self.assertIsNotNone(report['invalid_suffix'])
        self.assertEqual(report['status'],'INCOMPLETE_OR_FAILED')

    def test_complete_setup_not_gpu_success_or_cause_resolution(self):
        folder,sha=self.artifacts();report=n.inspect_artifacts(folder,sha)
        self.assertEqual(report['status'],'SETUP_COMPLETED_NOT_CAUSE_RESOLVED')
        self.assertFalse(report['native_gpu_verified']);self.assertFalse(report['performance_eligible'])
        n.c.write_new(folder/'unexpected.result.json',{})
        self.assertEqual(n.inspect_artifacts(folder,sha)['status'],'INCOMPLETE_OR_FAILED')

    def test_cleanup_never_extends_absolute_deadline(self):
        dev=Mock();dev.deadline=545;observed=[]
        def call(*a,**kw):
            observed.append(dev.deadline)
            return SimpleNamespace(stdout=b'Thermal Status: 0',stderr=b'',returncode=0)
        dev.call.side_effect=call
        with patch.object(d.time,'monotonic',return_value=590),patch.object(d.legacy,'require_stopped'):
            d.cleanup(dev,hard_deadline=600)
        self.assertEqual(observed,[600,600]);self.assertEqual(dev.deadline,545)

    def test_signature_subprocesses_share_deadline(self):
        f=self.root/'x.apk';f.write_bytes(b'x')
        cert='Number of signers: 1\nSigner #1 certificate SHA-256 digest: '+'a'*64
        with patch.object(apk.time,'monotonic',side_effect=[598,601]),patch.object(apk.subprocess,'run',return_value=SimpleNamespace(stdout=cert)) as proc:
            with self.assertRaises(TimeoutError):apk.inspect(f,dict(java='j',apksigner='s',aapt2='a'),deadline=600)
        self.assertEqual(proc.call_count,1);self.assertEqual(proc.call_args.kwargs['timeout'],2)

    def test_host_timeout_recovery_error_and_cleanup_remain_distinct(self):
        plan=dict(experiment_id=n.EXPERIMENT,budget=n.BUDGET,output_root=str(self.root/'run'),registry=str(self.root/'registry'),session_id='s',manifest='m.json',
                  manifest_sha256='a'*64,apk_path='fake.apk',apk_sha256='b'*64,source_files={},apk_preflight=dict(candidate={}))
        path=self.root/'plan.json';n.c.write_new(path,plan)
        clock=[0.0];dev=Mock();dev.call.return_value=SimpleNamespace(stdout=b'42',stderr=b'',returncode=0)
        def cool(*a):clock[0]+=120
        def poll(device,remote):
            self.assertEqual(device.deadline,245) # cooling120 + original poll125, not a new600
            clock[0]=245
            raise TimeoutError('app outcome unknown')
        with patch.object(n,'check'),patch.object(n.legacy,'Device',return_value=dev),patch.object(n.time,'monotonic',side_effect=lambda:clock[0]),patch.object(n.apk,'preflight',return_value={'installed':{}}),patch.object(n,'environment_gate'),patch.object(n.legacy,'bounded_cool',side_effect=cool),patch.object(d,'stage_inputs',return_value='remote'),patch.object(d,'wait_for_cleanup',side_effect=poll),patch.object(d.failure_evidence,'collect_failure',side_effect=OSError('capture disk')),patch.object(d,'pull',side_effect=RuntimeError('connection')),patch.object(d,'cleanup',return_value={'status':'completed'}) as clean:
            result=n.run(path,'unused','unused',n.p.digest(path),n.EXPERIMENT)
        clean.assert_called_once_with(dev,hard_deadline=600)
        self.assertEqual(result['status'],'stopped_no_retry');self.assertEqual(result['counts']['session_attempts'],1)
        self.assertEqual(result['runtime_actual_attempt_bounds'],[0,4])
        for name in ('host_error.json','evidence_capture_error.json','recovery_error.json','host_cleanup.json','FINAL_RECEIPT.json'):
            self.assertTrue((self.root/'run'/name).exists(),name)
        self.assertEqual(n.p.read(self.root/'run/host_error.json')['host_stage'],'completion_poll')

    def test_preflight_failure_has_zero_install_session_and_blocks_rerun(self):
        plan=dict(experiment_id=n.EXPERIMENT,budget=n.BUDGET,output_root=str(self.root/'run'),registry=str(self.root/'registry'))
        path=self.root/'plan.json';n.c.write_new(path,plan);dev=Mock()
        with patch.object(n,'check'),patch.object(n.legacy,'Device',return_value=dev),patch.object(n.apk,'preflight',side_effect=ValueError('incompatible')),patch.object(d,'cleanup') as cleanup:
            report=n.run(path,'unused','unused',n.p.digest(path),n.EXPERIMENT)
            self.assertEqual(report['counts']['install_attempts'],0);self.assertEqual(report['counts']['session_attempts'],0)
            self.assertEqual(report['runtime_actual_attempt_bounds'],[0,0]);cleanup.assert_not_called()
            with self.assertRaisesRegex(ValueError,'consumed'):n.run(path,'unused','unused',n.p.digest(path),n.EXPERIMENT)
        dev.call.assert_not_called()

    def test_first_warmup_artifact_requires_real_return_and_order(self):
        folder,sha=self.artifacts()
        manifest=n.p.read(folder/'manifest.json')
        manifest.update(failure_diagnostic_scope='first_warmup',warmup_requests=[dict(request_id='w',model_key='classification_CPU')])
        (folder/'manifest.json').write_bytes(n.p.canonical(manifest));sha=n.p.digest(folder/'manifest.json')
        rows=[json.loads(line) for line in (folder/'failure_progress.jsonl').read_bytes().splitlines()]
        rows=rows[:-2]
        def add(stage,edge):
            rows.append(dict(rows[-1],stage=stage,edge=edge,model_key='classification_CPU',request_id='w',thread_id=1))
        add('warmup_wait','start');add('warmup','start')
        for stage in ('input_preparation','host_inference','output_readback','output_decode'):
            add(stage,'start');add(stage,'succeeded')
        add('warmup','succeeded');add('warmup_wait','succeeded');add('first_warmup','succeeded');add('cleanup','succeeded')
        def write():
            for i,row in enumerate(rows):row.update(sequence=i,mono_ns=i,manifest_sha256=sha)
            (folder/'failure_progress.jsonl').write_bytes(b''.join(n.p.canonical(x) for x in rows))
        write();report=n.inspect_artifacts(folder,sha)
        self.assertEqual(report['status'],'FIRST_WARMUP_COMPLETED_NOT_CAUSE_RESOLVED')
        self.assertEqual(report['host_inference_returned'],1)
        self.assertEqual(report['warmup']['adapter_returned'],1)
        rows[:]=[x for x in rows if not (x['stage']=='host_inference' and x['edge']=='succeeded')]
        write();self.assertEqual(n.inspect_artifacts(folder,sha)['status'],'INCOMPLETE_OR_FAILED')


    def test_first_warmup_host_timeout_preserves_unknown_call_range(self):
        plan=dict(experiment_id=n.WARMUP_EXPERIMENT,budget=dict(n.BUDGET,warmup_calls=1,inference_calls=1),
                  output_root=str(self.root/'run'),registry=str(self.root/'registry'),session_id='s',manifest='m.json',
                  manifest_sha256='a'*64,apk_path='fake.apk',apk_sha256='b'*64,source_files={},apk_preflight=dict(candidate={}))
        path=self.root/'plan.json';n.c.write_new(path,plan)
        dev=Mock();dev.call.return_value=SimpleNamespace(stdout=b'42',stderr=b'',returncode=0)
        with patch.object(n,'check'),patch.object(n.legacy,'Device',return_value=dev),patch.object(n.apk,'preflight',return_value={'installed':{}}),patch.object(n,'environment_gate'),patch.object(n.legacy,'bounded_cool'),patch.object(d,'stage_inputs',return_value='remote'),patch.object(d,'wait_for_cleanup',side_effect=TimeoutError('stop')),patch.object(d,'failed_attempt_evidence'),patch.object(n,'inspect_artifacts',side_effect=FileNotFoundError()),patch.object(d,'cleanup',return_value={'status':'completed'}):
            result=n.run(path,'unused','unused',n.p.digest(path),n.WARMUP_EXPERIMENT)
        self.assertIsNone(result['counts']['warmup_calls']);self.assertIsNone(result['counts']['inference_calls'])
        self.assertEqual(result['warmup_call_bounds'],[0,1]);self.assertEqual(result['inference_call_bounds'],[0,1])
        self.assertTrue(result['no_resume'])


if __name__=='__main__':unittest.main()
