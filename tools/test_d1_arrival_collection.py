import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, Mock
from contextlib import ExitStack
from types import SimpleNamespace
from tools import d1_arrival_collection as c
from tools import d1_arrival_collection_device as d
from tools import d1_cal03_connection as pc
from tools.test_d1_cal03_connection import fixture
from tools.test_d1_arrival_timing_dev import fixture as old_fixture


class CollectionTest(unittest.TestCase):
    def setUp(self):
        self.q=[dict(id='n',task='detection',priority='normal',ordinal=0),dict(id='u',task='classification',priority='urgent',ordinal=1)]
        self.lanes={b:pc.available() for b in ('CPU','GPU')}

    def test_strict_gpu_unreachable_even_if_free(self):
        self.assertEqual(c.actual_choice(self.q,self.lanes,'strict_active','CPU',1)['selected']['backend'],'CPU')
        self.lanes['CPU']['phase']='EXECUTING'
        self.assertIsNone(c.actual_choice(self.q,self.lanes,'strict_active','CPU',1)['selected'])

    def test_global_serialization_and_per_lane_control(self):
        self.lanes['CPU']['phase']='EXECUTING'
        self.assertIsNone(c.actual_choice(self.q,self.lanes,'fixed_shadow','SPLIT',1)['selected'])
        self.assertEqual(c.actual_choice(self.q,self.lanes,'fixed_shadow','SPLIT',2)['selected'],dict(request_id='n',backend='GPU'))

    def test_shadow_selection_is_not_active_dispatch(self):
        cfg,_=fixture()
        expected=pc.decide(cfg,[dict(self.q[0],arrival_ns=0)],self.lanes,0)
        actual=c.actual_choice(self.q[:1],self.lanes,'fixed_shadow','SPLIT',1)
        self.assertEqual(expected['selected']['backend'],'CPU');self.assertEqual(actual['selected']['backend'],'GPU')

    def test_extension_requires_explicit_validator_and_replays(self):
        trace=old_fixture()['decision_trace.json'];trace['protocol']=c.PROTOCOL;trace['policy']=c.POLICY
        with self.assertRaises(ValueError):c.v.validate_trace(trace)
        c.v.validate_trace(trace,(c.PROTOCOL,c.POLICY,lambda q,l,n:c.v.replay(q,l,n,trace['budgets'])))
        trace['records'][0]['selected']['backend']='GPU'
        with self.assertRaises(ValueError):c.v.validate_trace(trace,(c.PROTOCOL,c.POLICY,lambda q,l,n:c.v.replay(q,l,n,trace['budgets'])))

    def test_claim_never_resumes_consumed_or_stopped(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=Path(tmp);plan=dict(registry=str(r/'registry'),output_root=str(r/'run'))
            file=r/'plan.json';c.cal.write_new(file,plan)
            d.claim(file,'development',None)
            with self.assertRaises(ValueError):d.claim(file,'development',None)
            c.cal.write_new(r/'registry/stopped.json',{})
            with self.assertRaises(ValueError):d.claim(file,'confirmation',None)

    def test_confirmation_requires_exact_development_freeze(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=Path(tmp);(r/'registry').mkdir();c.cal.write_new(r/'registry/development_complete.json',{})
            c.cal.write_new(r/'plan.json',dict(registry=str(r/'registry'),output_root=str(r/'run')))
            c.cal.write_new(r/'freeze.json',dict(input_hashes={},conditions='retuned'))
            with patch.object(c,'summarize',return_value=dict(input_hashes={},conditions='original')):
                with self.assertRaises(ValueError):d.claim(r/'plan.json','confirmation',r/'freeze.json')
            self.assertFalse((r/'registry/confirmation_consumed.json').exists())

    def test_signature_failure_has_no_install_or_launch(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=Path(tmp);plan=dict(registry=str(r/'registry'),output_root=str(r/'run'),host_phase_wall_seconds=2700)
            file=r/'plan.json';c.cal.write_new(file,plan)
            fake=Mock()
            with patch.object(c,'check'),patch.object(d.legacy,'Device',return_value=fake),patch.object(d.apk,'preflight',side_effect=ValueError('signer mismatch')):
                with self.assertRaises(ValueError):d.run(file,'development','never','never',12,c.p.digest(file))
            fake.call.assert_not_called()
            result=c.p.read(r/'run/development/stopped.json')
            self.assertEqual((result['install_attempts'],result['launch_attempts'],result['attempts']),(0,0,0))
            self.assertTrue((r/'registry/stopped.json').exists())

    def test_wrong_approval_does_not_touch_device_or_consume(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(d.legacy,'Device') as device:
            f=Path(tmp)/'plan.json';c.cal.write_new(f,{})
            with self.assertRaises(ValueError):d.run(f,'development','never','never',16,c.p.digest(f))
            device.assert_not_called()

    def test_freeze_rejects_changed_or_added_recovered_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'artifacts').mkdir()
            file=root/'artifacts/requests.json';file.write_bytes(b'[]')
            c.cal.write_new(root/'validated.json',dict(status='valid',recovery=dict(status='recovered',files=[
                dict(name=file.name,bytes=2,sha256=c.p.digest(file))])))
            c.verify_recovery(root)
            file.write_bytes(b'{}')
            with self.assertRaises(ValueError):c.verify_recovery(root)
            file.write_bytes(b'[]');(root/'artifacts/extra.json').write_bytes(b'{}')
            with self.assertRaises(ValueError):c.verify_recovery(root)

    def test_budget_layout_and_paired_workload_identity(self):
        self.assertEqual(len(c.CONDITIONS),6)
        self.assertEqual(2*len(c.CONDITIONS)*4,48)
        self.assertEqual(2*len(c.CONDITIONS)*8,96)
        self.assertEqual(c.CONDITIONS[-1][1:4],('fixed_shadow','SPLIT',2))
        # Three intervention pairs have only one intended factor different.
        self.assertEqual(c.CONDITIONS[0][2:],c.CONDITIONS[1][2:])
        self.assertEqual(c.CONDITIONS[4][1:3],c.CONDITIONS[5][1:3])
        self.assertEqual(c.CONDITIONS[4][4],c.CONDITIONS[5][4])

    def test_recovery_failure_still_cleans_up_and_does_not_retry(self):
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            r=Path(tmp);plan=dict(registry=str(r/'registry'),output_root=str(r/'run'),host_phase_wall_seconds=2700,
                screen_contract={},apk_path='synthetic.apk',apk_sha256='fake',initial_cool_seconds=0,cool_down_seconds=0,
                device_fingerprint='synthetic',source_files={},entries=[dict(index=0,session_id='synthetic-session',
                    condition='active_cpu_sparse',phase='development',manifest='synthetic.json')])
            file=r/'plan.json';c.cal.write_new(file,plan)
            fake=Mock();fake.call.side_effect=lambda *a,**k:SimpleNamespace(stdout=b'123' if 'pidof' in a else b'Thermal Status: 0\n')
            stack.enter_context(patch.object(c,'check'))
            stack.enter_context(patch.object(d.legacy,'Device',return_value=fake))
            stack.enter_context(patch.object(d.apk,'preflight',return_value=dict(device={})))
            for name in ('require_stopped','battery_gate','bounded_cool'):stack.enter_context(patch.object(d.legacy,name))
            for name in ('screen_snapshot','awake_gate','wait_for_cleanup'):stack.enter_context(patch.object(d.shared,name))
            stack.enter_context(patch.object(d.shared,'stage_inputs',return_value='synthetic/remote'))
            pull=stack.enter_context(patch.object(d.shared,'pull',side_effect=OSError('synthetic retrieval failure')))
            cleanup=stack.enter_context(patch.object(d.shared,'cleanup',return_value=dict(status='completed')))
            stack.enter_context(patch.object(d.evidence,'collect_failure',return_value=dict(status='unavailable')))
            with self.assertRaises(OSError):d.run(file,'development','never','never',12,c.p.digest(file))
            stopped=c.p.read(r/'run/development/stopped.json')
            self.assertEqual(stopped['stage'],'recovery');self.assertEqual(stopped['launch_attempts'],1)
            self.assertEqual(stopped['app_failure'],'unknown unless app evidence confirms')
            self.assertEqual(sum(a.args[0]=='install' for a in fake.call.call_args_list),1)
            cleanup.assert_called_once();self.assertEqual(pull.call_count,2) # normal then bounded evidence retrieval; no inference retry
            with self.assertRaises(ValueError):d.claim(file,'development',None)

    def test_dry_run_dispatch_never_imports_device_runner(self):
        import os
        path=os.environ.get('D1_COLLECTION_PLAN')
        if not path:self.skipTest('bound candidate not supplied')
        with patch.object(d.legacy,'Device',side_effect=AssertionError('dry-run accessed ADB')) as device:
            result=c.check(path)
            device.assert_not_called();self.assertEqual(result['adb_calls'],0)

    def test_actual_kotlin_export_matches_pc(self):
        # Optional in isolated environments; the task's validation explicitly supplies this export.
        import os
        path=os.environ.get('D1_COLLECTION_PARITY_OUTPUT')
        if not path:self.skipTest('Kotlin export not supplied')
        records=json.loads(Path(path).read_text(encoding='utf-8'));config,_=fixture()
        self.assertEqual(len(records),12)
        for record in records:
            self.assertEqual(record,pc.decide(config,record['queue'],record['lanes'],record['now_ns']))


if __name__=='__main__':unittest.main()
