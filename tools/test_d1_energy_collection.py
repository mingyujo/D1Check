import copy
import io
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch
from tools import d1_energy_collection as c
from tools import d1_energy_collection_device as d

def row(i,key,start,end):
    return dict(id=str(i),key=key,scheduled_arrival_ns=0,dispatch_ns=start,execution_start_ns=start+1,
        invocation_start_ns=start+2,invocation_end_ns=end-3,output_ready_ns=end-2,persist_complete_ns=end-1,
        worker_release_ns=end,lane_available_ns=end+1,terminal_status='succeeded')

class EnergyCollectionTest(unittest.TestCase):
    def test_sampler_diagnostic_has_one_unchanged_workload_and_no_freeze(self):
        experiment,budget,order,output=c.plan_profile(True)
        self.assertEqual(experiment,'ENERGY-SAMPLER-LOAD-DIAG-01')
        self.assertEqual(order,[('diagnostic','CC_DG','serial')])
        self.assertEqual(budget['diagnostic_requests'],678+192+2)
        self.assertEqual(budget['explicit_inference'],880)
        self.assertEqual((budget['development'],budget['confirmation'],budget['freeze_seconds']),(0,0,0))
        self.assertEqual(budget['total_seconds'],600+1500)
        self.assertNotEqual(output,c.plan_profile(False)[3])
        for key in ['session_seconds','host_poll_seconds','stage_gate_seconds','recovery_seconds','cleanup_seconds',
                    'baseline_seconds','common_work_seconds','cooling_seconds','retry','replacement','additional']:
            self.assertEqual(budget[key],c.BUDGET[key])
    def test_diagnostic_budget_or_identity_tampering_fails_before_apk_inspection(self):
        from tools import d1_apk_identity
        with tempfile.TemporaryDirectory() as t:
            file=Path(t)/'plan.json'
            plan=dict(protocol=c.PROTOCOL,experiment_id=c.DIAG_EXPERIMENT,diagnostic_only=True,
                      budget=dict(c.DIAG_BUDGET,sessions=2),experiment_ready=False)
            file.write_text(json.dumps(plan))
            with patch.object(d1_apk_identity,'inspect') as inspect:
                with self.assertRaises(ValueError):c.check(file)
                inspect.assert_not_called()
                plan['budget']=c.DIAG_BUDGET;plan['diagnostic_only']=False;file.write_text(json.dumps(plan))
                with self.assertRaises(ValueError):c.check(file)
                inspect.assert_not_called()
    def test_diagnostic_runner_ends_after_one_session_without_freeze(self):
        calls=[]
        class Fake:
            def __init__(self,*args):self.deadline=None
            def call(self,*args,**kwargs):calls.append(args)
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);manifest=root/'manifest.json';manifest.write_text('{}')
            plan=dict(output_root=str(root/'run'),registry=str(root/'registry'),budget=c.DIAG_BUDGET,
                diagnostic_only=True,apk_preflight={'candidate':{}},apk_sha256='hash',source_files={},
                entries=[dict(index=0,phase='diagnostic',pair='CC_DG',mode='serial',session_id='sid',manifest=manifest.name)])
            file=root/'plan.json';file.write_text(json.dumps(plan))
            with (patch.object(c,'check'),patch.object(d,'ObservedDevice',Fake),
                patch.object(d,'installation',return_value={'status':'verified'}),patch.object(d,'gates'),
                patch.object(d.install,'installed_hash',return_value='hash'),
                patch.object(d.shared,'stage_inputs',return_value='remote'),patch.object(d,'poll'),
                patch.object(d,'recover',return_value={'status':'recovered'}),
                patch.object(d.shared,'cleanup',return_value={'status':'completed'}),
                patch.object(c,'summarize_session',return_value={'status':'eligible_descriptive_only','condition':'CC_DG_serial'})):
                result=d.run(file,'not-an-adb','fixture',c.p.digest(file),True)
            self.assertEqual(result['status'],'completed_diagnostic_only')
            self.assertEqual((result['sessions'],result['diagnostic_requests'],result['explicit_inference']),(1,872,880))
            self.assertEqual(len(calls),1)
            self.assertFalse((root/'run/development_freeze.json').exists())
    def test_budget_exact_no_silent_old_reuse(self):
        b=c.BUDGET
        self.assertEqual(b['diagnostic_requests'],8*(678+192+2))
        self.assertEqual(b['explicit_inference'],b['diagnostic_requests']+8*8)
        self.assertEqual(b['total_seconds'],8*b['session_seconds']+b['installation_seconds']+b['freeze_seconds'])
        self.assertLessEqual(b['stage_gate_seconds']+b['host_poll_seconds']+b['recovery_seconds']+b['cleanup_seconds'],b['session_seconds'])
    def test_stage_order_serial_before_parallel(self):
        for phase in ('development','confirmation'):
            order=[(pair,mode) for p,pair,mode in c.layout() if p==phase]
            for pair in c.PAIRS:self.assertLess(order.index((pair,'serial')),order.index((pair,'parallel')))
    def test_actual_overlap_and_tail(self):
        r=[row(0,'classification_CPU',0,10),row(1,'detection_GPU',0,20)]
        out=c.validate_rows(r,'CC_DG','parallel',[1,1]);self.assertEqual(out['host_api_overlap_ns'],5)
        self.assertFalse(out['kernel_overlap_verified'])
        with self.assertRaises(ValueError):c.validate_rows(r,'CC_DG','serial',[1,1])
    def test_serial_and_late_release(self):
        r=[row(0,'classification_CPU',0,10),row(1,'detection_GPU',11,30)]
        self.assertEqual(c.validate_rows(r,'CC_DG','serial',[1,1])['host_api_overlap_ns'],0)
        with self.assertRaises(ValueError):c.validate_rows(r,'CC_DG','parallel',[1,1])
        r[1]['dispatch_ns']=9
        with self.assertRaises(ValueError):c.validate_rows(r,'CC_DG','serial',[1,1])
    def test_missing_and_failed_denominator(self):
        r=[row(0,'classification_CPU',0,10)]
        with self.assertRaises(ValueError):c.validate_rows(r,'CC_DG','serial',[1,1])
        r.append(row(1,'detection_GPU',11,30));r[1]['terminal_status']='failed'
        with self.assertRaises(ValueError):c.validate_rows(r,'CC_DG','serial',[1,1])
    def test_bad_clock(self):
        r=[row(0,'classification_GPU',0,10),row(1,'detection_CPU',11,30)]
        r[0]['persist_complete_ns']=4
        with self.assertRaises(ValueError):c.validate_rows(r,'CG_DC','serial',[1,1])
    def test_quality_separate_from_backend(self):
        ref=dict(task_id='classification',model_sha256='m',image_sha256='i',input_tensor_sha256='t',requested_backend='CPU',
            adapter_contract='v2',actual_backend='CPU',results=[dict(label=str(i),class_index=i,score=.9-i*.1) for i in range(5)])
        c.quality(ref,copy.deepcopy(ref));bad=copy.deepcopy(ref);bad['results'][0]['score']-=.01
        with self.assertRaises(ValueError):c.quality(ref,bad)
    def test_partial_progress_retains_unknown_range(self):
        self.assertEqual(c.progress_prefix(b'{"kind":"runtime_return"}'),([],1))
        self.assertEqual(c.progress_prefix(b'bad\n{"kind":"runtime_return"}\n'),([],2))
        raw=b'{"kind":"runtime_start","key":"classification_GPU"}\n{"kind":'
        x=c.progress_consumption(raw,True)
        self.assertEqual(x['counts']['runtime']['confirmed_started_at_least'],1)
        self.assertEqual(x['counts']['runtime']['confirmed_returned'],0)
        self.assertEqual(x['counts']['warmup']['actual_started_upper'],8)
        self.assertEqual(x['partial_lines'],1)
        self.assertEqual(c.progress_consumption(b'',False)['counts']['warmup']['actual_started_upper'],0)
    def test_common_energy_partition_and_remaining_tail(self):
        rows=[row(0,'classification_CPU',0,10_000_000_000),row(1,'detection_GPU',0,20_000_000_000)]
        spans=c.state_intervals(rows,0,30_000_000_000)
        self.assertEqual([x['state'] for x in spans],['classification_CPU+detection_GPU','detection_GPU','resident_idle'])
        samples=[dict(mono_ns=i*1_000_000_000,current_raw=-1000,voltage_mV=4000,plugged=0,current_valid=True) for i in range(31)]
        states=c.power_by_state(samples,spans)
        self.assertAlmostEqual(sum(x['covered_energy_j'] for x in states.values()),120)
    def test_thermal_burden_crossing_reference(self):
        x=c.thermal_burden([dict(mono_ns=0,AP='29'),dict(mono_ns=2_000_000_000,AP='31')],0,2_000_000_000,30)
        self.assertAlmostEqual(x['degree_seconds'],.5)
        self.assertEqual(x['covered_seconds'],2)
    def test_counter_hypotheses_not_fitted(self):
        samples=[dict(mono_ns=i*1_000_000_000,current_raw=-360,voltage_mV=4000,current_valid=True,plugged=0,
            charge_valid=True,charge_counter_raw=100000-i*100) for i in range(121)]
        x=c.counter_windows(samples,0,120_000_000_000)[0]
        self.assertAlmostEqual(x['ratio_mA'],1)
        self.assertAlmostEqual(x['ratio_uA'],.001)
        for s in samples:s['charge_valid']=False
        self.assertEqual(c.counter_windows(samples,0,120_000_000_000)[0]['status'],'counter_missing')
    def test_no_arm_without_approval(self):
        with patch.object(c.p,'digest',return_value='x'),patch.object(c,'check') as check:
            with self.assertRaises(ValueError):d.run('x','adb','serial','x',False)
            check.assert_not_called()
    def test_gpu_evidence_requires_two_complete_instances(self):
        lines=['runtime_scope_start=s',
               'Replacing 10 out of 10 node(s) with delegate (TfLiteGpuDelegateV2)',
               'Created 1 GPU delegate kernels',
               'Replacing 20 out of 20 node(s) with delegate (TfLiteGpuDelegateV2)',
               'Created 1 GPU delegate kernels','runtime_scope_end=s']
        log='\n'.join('09-25 00:00:00 123 4 I tag: '+x for x in lines)
        self.assertEqual(d.gpu_proof(log,'s')['instances'],2)
        with self.assertRaises(ValueError):d.gpu_proof(log.replace('20 out of 20','19 out of 20'),'s')
    def test_install_failure_has_finite_cleanup_and_consumption(self):
        class Device:
            deadline=1000
            def call(self,*args,**kw):
                if args[0]=='push':raise TimeoutError('partial transfer')
                return subprocess.CompletedProcess(args,1,b'',b'')
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);plan={'apk_path':'unused','apk_sha256':'a'*64}
            pre={'candidate':{'apk_sha256':'a'*64},'installed':{'apk_sha256':'b'*64}}
            with patch.object(d.apk,'preflight',return_value=pre),patch.object(d,'gates'),patch.object(d.shared,'cleanup',return_value={'status':'completed'}) as clean:
                with self.assertRaises(TimeoutError):d.installation(Device(),plan,'unused',root,d.time.monotonic()+600)
                clean.assert_called_once()
                receipt=json.loads((root/'installation_receipt.json').read_text())
                self.assertEqual(receipt['apk_transfer_attempts'],1);self.assertEqual(receipt['install_attempts'],0)
                self.assertEqual(receipt['status'],'failed')
    def test_pull_failure_not_app_failure(self):
        class Failed:
            def call(self,*a,**kw):raise TimeoutError('transport')
        with tempfile.TemporaryDirectory() as t:
            with self.assertRaises(TimeoutError):d.recover(Failed(),'remote',Path(t)/'artifacts')
            self.assertFalse((Path(t)/'artifacts/cleanup.json').exists())
    def test_archive_traversal_rejected(self):
        data=io.BytesIO()
        with tarfile.open(fileobj=data,mode='w') as a:
            m=tarfile.TarInfo('../outside');m.size=1;a.addfile(m,io.BytesIO(b'x'))
        class Device:
            def call(self,*args,**kw):return subprocess.CompletedProcess(args,0,data.getvalue() if 'tar' in args else b'{}',b'')
        with tempfile.TemporaryDirectory() as t:
            with self.assertRaises(ValueError):d.recover(Device(),'remote',Path(t)/'artifacts')
            self.assertFalse((Path(t)/'outside').exists())
    def test_consumed_check_precedes_device_import(self):
        # run's check fails before claim/device use; no hidden retry to new paths.
        with (patch.object(c.p,'digest',return_value='x'),patch.object(c,'check',side_effect=ValueError('consumed')),
             patch.object(d,'ObservedDevice') as device):
            with self.assertRaises(ValueError):d.run('x','adb','serial','x',True)
            device.assert_not_called()

if __name__=='__main__':unittest.main()
