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
        manifest=dict(session_id='parent',calibration_backend='GPU',requests=[dict(request_id='old',task_id='classification',priority='urgent',offset_ms=0)],
                      warmup_requests=[dict(request_id='warm'+str(i),model_key=k) for i,k in enumerate([k for k in n.ORDER for _ in range(2)])],
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
            combined=n.prepare(self.root/'parent.json',candidate,self.root/'receipt.json',self.root/'integrated-plan',scope='warmup_and_request')
            self.assertEqual((combined['budget']['warmup_calls'],combined['budget']['diagnostic_requests'],combined['budget']['inference_calls']),(8,1,9))
            self.assertEqual(combined['generated_measurements'],0);device.assert_not_called()
            self.assertFalse((self.root/'warmup_request_run_v1').exists())
            observed=n.prepare(self.root/'parent.json',candidate,self.root/'receipt.json',self.root/'observed-plan',scope='observed_warmup_request')
            op=n.p.read(self.root/'observed-plan/initialization_plan.json')
            om=n.p.read(self.root/'observed-plan/manifest.json')
            self.assertEqual(op['experiment_id'],n.OBSERVED_EXPERIMENT)
            self.assertEqual(om['failure_diagnostic_scope'],'warmup_and_request')
            self.assertEqual((len(om['warmup_requests']),len(om['requests'])),(8,1))
            self.assertEqual(op['host_observation']['offsets_seconds'],[5,35,105])
            self.assertEqual(observed['adb_calls'],0);device.assert_not_called()
            self.assertFalse(Path(op['output_root']).exists())
            self.assertNotEqual(op['registry'],first_plan['registry'])
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


class IntegratedTest(unittest.TestCase):
    setUp = InitializationTest.setUp
    artifacts = InitializationTest.artifacts
    def integrated(self):
        folder,sha=self.artifacts()
        m=n.p.read(folder/'manifest.json')
        m.update(failure_diagnostic_scope='warmup_and_request',calibration_backend='GPU',
                 warmup_requests=[dict(request_id='w'+str(i),model_key=k) for i,k in enumerate([k for k in n.ORDER for _ in range(2)])],
                 requests=[dict(request_id='r',task_id='classification',priority='urgent',offset_ms=0)])
        (folder/'manifest.json').write_bytes(n.p.canonical(m));sha=n.p.digest(folder/'manifest.json')
        rows=[json.loads(x) for x in (folder/'failure_progress.jsonl').read_bytes().splitlines()][:-2]
        def add(stage,edge,key=None,rid=None,thread=3,detail=None):
            rows.append(dict(rows[0],stage=stage,edge=edge,model_key=key,request_id=rid,thread_id=thread,detail=detail))
        phases=('input_preparation','host_inference','output_readback','output_decode')
        for q in m['warmup_requests']:
            key=q['model_key'];rid=q['request_id'];thread=1 if key.endswith('CPU') else 2
            add('warmup_wait','start',key,rid);add('warmup','start',key,rid,thread)
            for stage in phases:
                for edge in ('start','succeeded'):add(stage,edge,key,rid,thread)
            add('warmup','succeeded',key,rid,thread);add('warmup_wait','succeeded',key,rid)
        add('warmups_complete','observed');add('admission','observed',detail='before_workload/admit: {}')
        key='classification_GPU';rid='r'
        for stage,edge in [('request_arrival','observed'),('request_queue','observed'),('request_submit','start')]:add(stage,edge,key,rid)
        add('request_worker','start',key,rid,2);add('admission','observed',key,thread=2,detail='before_invocation/admit: {}');add('diagnostic','start',key,rid,2)
        for stage in phases:
            for edge in ('start','succeeded'):add(stage,edge,key,rid,2)
        for stage,edge in [('diagnostic','succeeded'),('output_ready','observed'),('persist','start'),('persist','succeeded'),('request_worker','succeeded'),('worker_release','observed'),('event_commit','start'),('event_commit','succeeded')]:add(stage,edge,key,rid,2)
        add('lane_available','observed',key,rid);add('decision_wait','observed');add('warmup_and_request','succeeded');add('cleanup','succeeded')
        from tools.test_d1_arrival_timing_calibration import artifacts
        fixture=artifacts(backend='GPU',priority='urgent',task='classification')
        trace=fixture['decision_trace.json']; trace['records']=trace['records'][:9]
        trace=json.loads(json.dumps(trace).replace('q0','r'))
        row=fixture['requests.json'][0];row['request_id']='r';row['result_sha256']=hashlib.sha256(n.p.canonical({})).hexdigest()
        event={k:v for k,v in row.items() if k!='lane_available_ns'}
        for name,value in [('summary.json',dict(status='completed')),('requests.json',[row]),('r.result.json',{}),('r.event.json',event),('decision_trace.json',trace)]:n.c.write_new(folder/name,value)
        def write(rows_to_write=None):
            target=rows if rows_to_write is None else rows_to_write
            for i,row in enumerate(target):row.update(sequence=i,mono_ns=i,manifest_sha256=sha)
            (folder/'failure_progress.jsonl').write_bytes(b''.join(n.p.canonical(x) for x in target))
        write();return folder,sha,rows,write

    def test_all_calls_and_partial_prefix_are_separate(self):
        folder,sha,rows,write=self.integrated();report=n.inspect_artifacts(folder,sha)
        self.assertEqual(report['status'],'WARMUP_REQUEST_COMPLETED_NOT_CAUSE_RESOLVED')
        self.assertEqual(report['warmup']['adapter_returned'],8);self.assertEqual(report['diagnostic']['adapter_returned'],1)
        self.assertEqual(report['host_inference_returned'],9)
        # Cut at every stage: no partial prefix can masquerade as complete.
        for end in range(len(rows)):
            write(rows[:end]);self.assertEqual(n.inspect_artifacts(folder,sha)['status'],'INCOMPLETE_OR_FAILED',end)
        write()
        for stage in ['lane_available','persist','host_inference','event_commit']:
            write([r for r in rows if not(r['stage']==stage and r.get('request_id')=='r')])
            self.assertEqual(n.inspect_artifacts(folder,sha)['status'],'INCOMPLETE_OR_FAILED',stage)

    def test_integrated_rejects_wrong_thread_or_extra_inference(self):
        folder,sha,rows,write=self.integrated()
        r=next(r for r in rows if r['stage']=='host_inference' and r.get('request_id')=='r');r['thread_id']=1;write()
        self.assertEqual(n.inspect_artifacts(folder,sha)['status'],'INCOMPLETE_OR_FAILED')
        r['thread_id']=2;rows.insert(-2,dict(r,request_id='unplanned'));write()
        self.assertEqual(n.inspect_artifacts(folder,sha)['status'],'INCOMPLETE_OR_FAILED')


    def test_integrated_host_consumption_complete_and_unknown(self):
        for complete in (True,False):
            root=self.root/str(complete);root.mkdir()
            plan=dict(experiment_id=n.INTEGRATED_EXPERIMENT,budget=dict(n.BUDGET,warmup_calls=8,inference_calls=9,diagnostic_requests=1),
                      output_root=str(root/'run'),registry=str(root/'registry'),session_id='s',manifest='m.json',
                      manifest_sha256='a'*64,apk_path='fake.apk',apk_sha256='b'*64,source_files={},apk_preflight=dict(candidate={}))
            path=root/'plan.json';n.c.write_new(path,plan)
            dev=Mock();dev.call.return_value=SimpleNamespace(stdout=b'42',stderr=b'',returncode=0)
            result=dict(status='WARMUP_REQUEST_COMPLETED_NOT_CAUSE_RESOLVED',runtime_actual_attempt_bounds=[4,4],runtime_returned=4,
                        warmup=dict(adapter_returned=8),diagnostic=dict(adapter_returned=1),host_inference_returned=9)
            with patch.object(n,'check'),patch.object(n.legacy,'Device',return_value=dev),patch.object(n.apk,'preflight',return_value={'installed':{}}),patch.object(n,'environment_gate'),patch.object(n.legacy,'bounded_cool'),patch.object(d,'stage_inputs',return_value='remote'),patch.object(d,'wait_for_cleanup',side_effect=None if complete else TimeoutError('stop')),patch.object(d,'failed_attempt_evidence'),patch.object(n,'inspect_artifacts',return_value=result,side_effect=None if complete else FileNotFoundError()),patch.object(d,'cleanup',return_value={'status':'completed'}):
                receipt=n.run(path,'unused','unused',n.p.digest(path),n.INTEGRATED_EXPERIMENT)
            self.assertEqual(receipt['counts']['diagnostic_requests'],1 if complete else None)
            self.assertEqual(receipt['warmup_call_bounds'],[8,8] if complete else [0,8])
            self.assertEqual(receipt['inference_call_bounds'],[9,9] if complete else [0,9])
            self.assertEqual(receipt['diagnostic_call_bounds'],[1,1] if complete else [0,1])
            self.assertTrue((root/'registry/closed.json').exists())

    def test_partial_pull_prioritizes_identity_and_journal(self):
        device=Mock();seen=[]
        def call(*args,**kwargs):
            if args[-2]=='ls':return SimpleNamespace(returncode=0,stdout=b'cleanup.json\nfailure_progress.jsonl\nmanifest.json\nrequests.json\n',stderr=b'')
            seen.append(args[-1].split('/')[-1]);return SimpleNamespace(returncode=0,stdout=b'{}',stderr=b'')
        device.call.side_effect=call
        d.pull(device,'s',self.root/'partial')
        self.assertEqual(seen,['manifest.json','failure_progress.jsonl','cleanup.json','requests.json'])


if __name__=='__main__':unittest.main()
