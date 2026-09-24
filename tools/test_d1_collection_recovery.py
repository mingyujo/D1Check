import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import Mock,patch
from types import SimpleNamespace
from contextlib import ExitStack
from tools import d1_recorded_process as rp
from tools import d1_collection_recovery as r
from tools import d1_arrival_collection as c
from tools import d1_arrival_collection_device as cd


class ProcessTest(unittest.TestCase):
    def test_nonzero_output_and_no_secret_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            code="import sys; print('prefix',flush=True); print('failure',file=sys.stderr,flush=True); sys.exit(7)"
            x=rp.run([sys.executable,'-c',code],Path(tmp)/'run',3,['python','<test>'])
            self.assertEqual((x['status'],x['returncode']),('nonzero_exit',7))
            self.assertIn(b'prefix',(Path(tmp)/'run/stdout.bin').read_bytes())
            self.assertIn(b'failure',(Path(tmp)/'run/stderr.bin').read_bytes())
            self.assertEqual(x['command'],['python','<test>'])

    def test_timeout_preserves_partial_bytes_and_reaps_descendant(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);pidfile=root/'child.txt'
            child="import time; time.sleep(20)"
            code=f"import subprocess,sys,time,pathlib; p=subprocess.Popen([sys.executable,'-c',{child!r}]); pathlib.Path({str(pidfile)!r}).write_text(str(p.pid)); print('partial',flush=True); print('partial-error',file=sys.stderr,flush=True); time.sleep(20)"
            x=rp.run([sys.executable,'-c',code],root/'run',1,['python','<blocking-test>'])
            self.assertEqual(x['status'],'timeout');self.assertTrue(x['root_reaped'])
            self.assertLess(x['elapsed_seconds'],7)
            self.assertEqual((root/'run/stdout.bin').read_bytes().strip(),b'partial')
            self.assertIn(b'partial-error',(root/'run/stderr.bin').read_bytes())
            pid=int(pidfile.read_text())
            if os.name=='nt':
                import ctypes
                kernel=ctypes.WinDLL('kernel32',use_last_error=True)
                kernel.OpenProcess.restype=ctypes.c_void_p
                h=kernel.OpenProcess(0x1000,False,pid)
                if h:
                    exitcode=ctypes.c_ulong()
                    kernel.GetExitCodeProcess(ctypes.c_void_p(h),ctypes.byref(exitcode))
                    kernel.CloseHandle(ctypes.c_void_p(h))
                    self.assertNotEqual(exitcode.value,259)
            else:
                try:os.kill(pid,0)
                except ProcessLookupError:pass
                else:self.assertIn('Z',Path(f'/proc/{pid}/stat').read_text().split()[2])

    def test_spawn_failure_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            x=rp.run([str(Path(tmp)/'no-such-program')],Path(tmp)/'run',1,['missing'])
            self.assertEqual(x['status'],'host_command_error');self.assertIsNone(x['returncode'])
            self.assertTrue((Path(tmp)/'run/result.json').exists())


class RecoveryTest(unittest.TestCase):
    def test_revision_two_requires_closed_predecessor_before_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            with self.assertRaises(ValueError):r.prepare('unused',root/'out',2)
            self.assertFalse((root/'out').exists())
            receipt=root/'receipt.json';stopped=root/'stopped.json';prior=root/'prior.json'
            c.cal.write_new(receipt,dict(status='verified'))
            c.cal.write_new(stopped,dict(status='stopped_no_resume'))
            c.cal.write_new(prior,dict(experiment_id=r.RECOVERY,output_root=str(root),workflow_root=str(root)))
            with self.assertRaises(ValueError):r.prepare('unused',root/'out',2,prior)
            self.assertFalse((root/'out').exists())

    def test_revision_two_has_disjoint_ids_and_preserves_closed_evidence(self):
        file=os.environ.get('D1_RECOVERY_PLAN')
        if not file:self.skipTest('prepared plan not supplied')
        bundle=c.p.read(file)
        if bundle['experiment_id']!='ARRIVAL-INSTALL-RECOVERY-02':self.skipTest('revision two only')
        new=c.p.read(bundle['collection_plan'])
        predecessor=next(c.p.read(name) for name in bundle['closed_predecessor_evidence'] if Path(name).name=='collection_plan.json')
        self.assertFalse(set(e['session_id'] for e in new['entries']) & set(e['session_id'] for e in predecessor['entries']))
        for key in ('output_root','registry','workflow_root','recovery_receipt'):self.assertNotEqual(new[key],predecessor[key])
        for name,sha in bundle['closed_predecessor_evidence'].items():self.assertEqual(c.p.digest(name),sha)
        self.assertEqual(new['apk_sha256'],predecessor['apk_sha256'])
        for key in ('freeze_rule','analysis_contract','parallel_gate','screen_contract','seed'):self.assertEqual(new[key],predecessor[key])

    def test_bundle_orders_recovery_freeze_confirmation_and_stops_on_failure(self):
        for fail in (False,True):
            with self.subTest(fail=fail),tempfile.TemporaryDirectory() as tmp,ExitStack() as stack:
                root=Path(tmp);collection=root/'c.json';bundle=root/'r.json'
                c.cal.write_new(collection,dict(registry=str(root/'registry'),output_root=str(root/'sessions')))
                c.cal.write_new(bundle,dict(collection_plan=str(collection),collection_plan_sha256=c.p.digest(collection),
                    workflow_root=str(root/'workflow'),output_root=str(root/'recovery')))
                stack.enter_context(patch.object(r,'check'))
                stack.enter_context(patch.object(r,'recover',side_effect=ValueError('recovery stopped') if fail else None,return_value=dict(status='verified')))
                order=[]
                def phase_run(*args,**kwargs):
                    order.append(args[1])
                    self.assertIn('overall_deadline',kwargs)
                    if args[1]=='confirmation':self.assertTrue((root/'workflow/development_freeze.json').exists())
                    return dict(status='completed')
                runner=stack.enter_context(patch.object(cd,'run',side_effect=phase_run))
                stack.enter_context(patch.object(c,'summarize',return_value=dict(conditions={},input_hashes={})))
                if fail:
                    with self.assertRaises(ValueError):r.run(bundle,'never','never',True,c.p.digest(bundle))
                    runner.assert_not_called();self.assertTrue((root/'workflow/stopped.json').exists())
                else:
                    r.run(bundle,'never','never',True,c.p.digest(bundle))
                    self.assertEqual(order,['development','confirmation']);self.assertTrue((root/'workflow/confirmation.json').exists())
                with self.assertRaises(ValueError):r.run(bundle,'never','never',True,c.p.digest(bundle))

    def test_bound_plan_is_pc_only_and_preserves_workload(self):
        planfile=os.environ.get('D1_RECOVERY_PLAN')
        if not planfile:self.skipTest('prepared plan not supplied')
        from tools import d1_arrival_device as legacy
        with patch.object(legacy,'Device',side_effect=AssertionError('PC check reached ADB')) as device:
            result=r.check(planfile);device.assert_not_called()
        self.assertEqual(result['total_seconds'],6090)
        bundle=c.p.read(planfile);newfile=Path(bundle['collection_plan']);new=c.p.read(newfile)
        oldfile=Path(bundle['parent_terminated_plan']);old=c.p.read(oldfile)
        self.assertFalse(set(e['session_id'] for e in new['entries']) & set(e['session_id'] for e in old['entries']))
        self.assertEqual((new['install_cap'],new['session_cap'],new['request_cap'],new['warmup_cap']),(0,12,48,96))
        for a,b in zip(old['entries'],new['entries']):
            x=c.p.read(oldfile.parent/a['manifest']);y=c.p.read(newfile.parent/b['manifest'])
            for key in ('collection_condition','collection_mode','collection_assignment','maximum_concurrency','cpu_threads','images'):
                self.assertEqual(x[key],y[key])
            for key in ('requests','warmup_requests'):
                self.assertEqual([{k:v for k,v in q.items() if k!='request_id'} for q in x[key]],
                                 [{k:v for k,v in q.items() if k!='request_id'} for q in y[key]])

    def test_unapproved_run_does_not_check_or_access_device(self):
        with patch.object(r,'check') as check:
            with self.assertRaises(ValueError):r.run('missing','adb','serial',False,'hash')
            check.assert_not_called()

    def test_bad_receipt_cannot_start_collection(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(cd,'claim') as claim,patch.object(c,'check'):
            root=Path(tmp);f=root/'receipt.json';c.cal.write_new(f,dict(status='failed'))
            w=root/'workflow';w.mkdir();c.cal.write_new(w/'claim.json',{})
            p=root/'plan.json';c.cal.write_new(p,dict(installation_contract='recovery-verified-only-v1',recovery_receipt=str(f),workflow_root=str(w)))
            with self.assertRaises(ValueError):cd.run(p,'development','never','never',12,c.p.digest(p),overall_deadline=time.monotonic()+2745)
            claim.assert_not_called()

    def test_direct_phase_cannot_bypass_total_wall_cap(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(cd,'claim') as claim,patch.object(c,'check'):
            p=Path(tmp)/'plan.json';c.cal.write_new(p,dict(installation_contract='recovery-verified-only-v1'))
            with self.assertRaises(ValueError):cd.run(p,'development','never','never',12,c.p.digest(p))
            claim.assert_not_called()

    def test_valid_receipt_binds_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);e=root/'evidence';e.write_bytes(b'original')
            f=root/'receipt.json';c.cal.write_new(f,dict(status='verified',collection_plan_sha256='plan',installed_apk_sha256='apk',cleanup=dict(status='completed'),evidence_hashes={str(e):c.p.digest(e)}))
            plan=dict(recovery_receipt=str(f),apk_sha256='apk');r.require_receipt(plan,'plan')
            e.write_bytes(b'changed')
            with self.assertRaises(ValueError):r.require_receipt(plan,'plan')

    def test_query_failure_not_installed(self):
        fake=Mock();fake.call.return_value=SimpleNamespace(stdout=b'not a package path')
        with self.assertRaises(ValueError):r.installed_hash(fake,dict(package='example'))
        self.assertEqual(fake.call.call_count,1)

    def exercise(self, same=False, fail=None):
        from tools import d1_apk_identity as apk
        from tools import d1_arrival_device as legacy
        from tools import d1_arrival_timing_calibration_device as shared
        with tempfile.TemporaryDirectory() as tmp,ExitStack() as stack:
            root=Path(tmp);out=root/'recovery'
            candidate=dict(package='example',apk_sha256='a'*64,signer_sha256='cert',version_code=1)
            plan=dict(apk_sha256='a'*64,apk_path='candidate.apk',device_fingerprint='fingerprint',screen_contract={},apk_preflight=dict(candidate=candidate))
            cf=root/'collection.json';c.cal.write_new(cf,plan)
            rf=root/'recovery.json';c.cal.write_new(rf,dict(collection_plan=str(cf),collection_plan_sha256=c.p.digest(cf),output_root=str(out),remote_apk='/data/local/tmp/test/candidate.apk'))
            fake=Mock();fake.last_identity={'model':'test'}
            def call(*args,**kwargs):
                if args[0]=='push' and fail=='transfer':raise RuntimeError('transfer timeout')
                if args[:3]==('shell','pm','install') and fail=='install':raise RuntimeError('install timeout')
                return SimpleNamespace(returncode=1 if 'test' in args else 0,stderr=b'',
                    stdout=b'Thermal Status: 0' if 'thermalservice' in args else b'a'*64+b' file' if 'sha256sum' in args else b'Success\n')
            fake.call.side_effect=call
            stack.enter_context(patch.object(r,'device_class',return_value=lambda *a:fake))
            stack.enter_context(patch.object(apk,'preflight',return_value=dict(candidate=candidate,installed=candidate if same else dict(candidate,apk_sha256='old'))))
            stack.enter_context(patch.object(legacy,'require_stopped'));stack.enter_context(patch.object(legacy,'battery_gate'))
            stack.enter_context(patch.object(shared,'screen_snapshot'))
            cleanup=stack.enter_context(patch.object(shared,'cleanup',return_value=dict(status='completed')))
            query=stack.enter_context(patch.object(r,'installed_hash',side_effect=ValueError('query unavailable') if fail=='query' else None,return_value='a'*64))
            if fail:
                with self.assertRaises(ValueError):r.recover(rf,'never','never',time.monotonic()+600)
            else:r.recover(rf,'never','never',time.monotonic()+600)
            result=c.p.read(out/'receipt.json');cleanup.assert_called_once()
            with self.assertRaises(ValueError):r.recover(rf,'never','never',time.monotonic()+600)
            return result,fake.call.call_args_list,query.call_count

    def test_exact_apk_skips_transfer_and_install(self):
        result,calls,_=self.exercise(same=True)
        self.assertEqual((result['install_attempts'],result['transfer_attempts']),(0,0))
        self.assertFalse(any(a.args[0]=='push' or 'install' in a.args for a in calls))

    def test_transfer_timeout_never_installs(self):
        result,_,_=self.exercise(fail='transfer')
        self.assertEqual((result['transfer_attempts'],result['install_attempts']),(1,0))
        self.assertEqual(result['stage'],'transfer')

    def test_install_timeout_no_retry_and_post_query(self):
        result,calls,n=self.exercise(fail='install')
        self.assertEqual(result['install_attempts'],1);self.assertEqual(n,1)
        self.assertEqual(sum(a.args[:3]==('shell','pm','install') for a in calls),1)

    def test_post_identity_failure_stops_without_query_retry(self):
        result,_,n=self.exercise(fail='query')
        self.assertEqual((result['status'],result['stage'],n),('failed','post_identity',1))

    def test_staged_install_success(self):
        result,_,_=self.exercise()
        self.assertEqual((result['status'],result['install_attempts'],result['transfer_attempts']),('verified',1,1))


if __name__=='__main__':unittest.main()
