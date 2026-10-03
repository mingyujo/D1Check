import copy
import tempfile
import unittest
import subprocess
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch
from tools import d1_sustained_protocol as s
from tools import d1_sustained_plan as plan
from tools import d1_arrival_energy_collection_device as device
from tools import d1_arrival_plan as p


class SustainedTests(unittest.TestCase):
    def test_fixed_input_and_no_unregistered_policy(self):
        rows=s.requests()
        for policy in s.POLICIES:s.validate(rows,policy)
        for bad in (rows[:-1], [dict(r,offset_ms=r['offset_ms']+1) for r in rows],
                    [dict(r,request_id='same') for r in rows]):
            with self.assertRaises(ValueError):s.validate(bad,s.POLICIES[0])
        with self.assertRaises(ValueError):s.validate(rows,'B2_SERIAL_ONLINE_V1')

    def test_existing_input_not_silently_widened(self):
        from tools import d1_separated_power_protocol as old
        with self.assertRaises(ValueError):old.validate('confirmation',s.requests())

    def test_budget_and_model_not_fitted(self):
        b=plan.budget()
        self.assertEqual((8,1536,64,1600,32,8,56,6830,25800),tuple(b[k] for k in
            ('sessions','requests','warmup','explicit_inference','runtime_creations','staging','staging_files','total_seconds','adb_commands')))
        self.assertEqual(700,sum(b[k] for k in ('stage_gate_seconds','host_poll_seconds','recovery_seconds','cleanup_seconds')))
        self.assertEqual(p.digest(plan.MODEL),plan.MODEL_SHA)
        self.assertFalse(p.read(plan.CONTRACT)['fit'])

    def test_entry_reaches_new_check_before_any_adb_or_claim(self):
        with tempfile.TemporaryDirectory() as directory:
            file=Path(directory)/'plan.json'
            file.write_bytes(p.canonical(dict(sustained_confirmation=True,online_policy_study=True)))
            with patch.object(plan,'check',side_effect=ValueError('fixture check stop')) as check, patch.object(device,'ObservedDevice',side_effect=AssertionError('actual ADB forbidden')):
                with self.assertRaisesRegex(ValueError,'fixture check stop'):
                    device.run(file,'forbidden','',p.digest(file),True)
                check.assert_called_once_with(file)

    def test_failure_validation_preserves_app_error_with_new_count(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory);(folder/'artifacts').mkdir()
            manifest=dict(requests=s.requests(),policy=s.POLICIES[0])
            for path,data in [('input_manifest.json',manifest),('artifacts/manifest.json',manifest),
                              ('artifacts/cleanup.json',dict(status='failed')),('artifacts/session_failure.json',dict(message='original lifecycle failure'))]:
                (folder/path).write_bytes(p.canonical(data))
            with self.assertRaisesRegex(RuntimeError,'original lifecycle failure'):
                device.validate(folder,manifest,dict(sustained_confirmation=True,online_policy_study=True))

    def test_script_reuses_original_foreground_entry_and_selection(self):
        text=plan.script_text()
        self.assertIn('tools.d1_sustained_plan run --plan',text)
        self.assertIn('--approved',text)
        self.assertNotIn('Start-Process',text)
        self.assertNotIn('adb devices',text)

    def test_preview_is_not_measurement_or_accuracy_pass(self):
        data=p.read(plan.PREVIEW)
        self.assertTrue(data['deadline_and_window_gate'])
        self.assertFalse(data['actual_measurement'])
        self.assertFalse(data['strict_supported'])
        self.assertIsNone(data['accuracy_pass'])
        self.assertTrue(all(x['deadline_met']==192 and x['last_lane_s']<120 for x in data['policies']))

    def run_fixture(self,fail_validation=False):
        with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
            folder=Path(directory);file=folder/'collection_plan.json'
            manifests=folder/'manifests';manifests.mkdir()
            entries=[]
            for i,policy in enumerate(plan.ORDER):
                sid=str(__import__('uuid').uuid4());m=dict(session_id=sid,policy=policy,requests=s.requests(sid))
                (manifests/(sid+'.json')).write_bytes(p.canonical(m))
                entries.append(dict(index=i,session_id=sid,manifest='manifests/'+sid+'.json'))
            data=dict(sustained_confirmation=True,online_policy_study=True,online_configuration_owner_v1=True,
                study_phase='confirmation',study_freeze=dict(path=str(plan.MODEL),sha256=plan.MODEL_SHA),
                frozen_model=dict(path=str(plan.MODEL),sha256=plan.MODEL_SHA),
                output_root=str(folder/'run'),registry=str(folder/'registry'),budget=plan.budget(),entries=entries,
                apk_path=str(plan.MODEL),apk_sha256='fixture',apk_preflight=dict(candidate={}),source_files={})
            file.write_bytes(p.canonical(data));calls=[];clock=[1000.]
            class Fake:
                def __init__(self,*a,**kw):self.sequence=0;self.deadline=None
                def call(self,*a,**kw):
                    calls.append(a);self.sequence+=1
                    return subprocess.CompletedProcess(a,0,b'',b'')
            stack.enter_context(patch.object(plan,'check',return_value={}))
            stack.enter_context(patch.object(device,'ObservedDevice',Fake))
            stack.enter_context(patch.object(device.time,'monotonic',side_effect=lambda:clock[0]))
            stack.enter_context(patch.object(device.time,'sleep',side_effect=lambda s:clock.__setitem__(0,clock[0]+s)))
            stack.enter_context(patch.object(device.energy_device,'installation',return_value=dict(status='verified')))
            stack.enter_context(patch.object(device.energy_device,'gates'))
            stack.enter_context(patch.object(device.install,'installed_hash',return_value='fixture'))
            stack.enter_context(patch.object(device.shared,'stage_inputs',return_value='fixture_remote'))
            poll=stack.enter_context(patch.object(device,'poll'))
            stack.enter_context(patch.object(device.energy_device,'recover',return_value=dict(status='recovered')))
            stop=stack.enter_context(patch.object(device.shared,'cleanup',return_value=dict(status='completed')))
            stats=dict(status='eligible_descriptive_only',requests=192)
            stack.enter_context(patch.object(device,'validate',side_effect=RuntimeError('original app failure') if fail_validation else lambda *a:dict(stats)))
            if fail_validation:
                with self.assertRaisesRegex(RuntimeError,'original app failure'):
                    device.run(file,'FAKE_ADB_ONLY','',p.digest(file),True)
                self.assertEqual(1,stop.call_count)
                receipt=p.read(folder/'run/FINAL_RECEIPT.json')
                self.assertEqual('stopped_no_resume',receipt['status'])
                self.assertIn('original app failure',receipt['error'])
                self.assertEqual(1,poll.call_count)
            else:
                receipt=device.run(file,'FAKE_ADB_ONLY','',p.digest(file),True)
                self.assertEqual((8,1536),(receipt['sessions'],receipt['requests']))
                self.assertEqual(8,stop.call_count);self.assertEqual(8,poll.call_count)
                self.assertTrue(all('OnlinePolicyStudyActivity' in str(c) for c in calls))
            self.assertTrue((folder/'registry/claimed.json').exists())
            # Actual consumed check, no helper bypass or real ADB.
            with self.assertRaisesRegex(ValueError,'consumed/occupied'):
                plan.check.__wrapped__(file) if hasattr(plan.check,'__wrapped__') else self.original_check(file)

    original_check=staticmethod(plan.check)

    def test_normal_actual_collector_entry_all_eight_no_early_stop(self):self.run_fixture()

    def test_failed_summary_preserves_original_error_and_single_cleanup(self):self.run_fixture(True)


if __name__=='__main__':unittest.main()
