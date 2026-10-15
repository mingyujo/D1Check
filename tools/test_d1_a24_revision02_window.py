"""Pure PC checks: no ADB, no inference, no session claims."""
import copy,datetime,json,tempfile,unittest
from pathlib import Path
from d1_a24_revision02_window import check_deadline
from d1_a24_revision02_control import frozen_gate,run_one
from d1_a24_laptop_validator import ValidationError,sha256

class BoundedRevisionCases(unittest.TestCase):
    def setUp(self):
        self.window={'hard_stop_UTC':'2026-10-15T03:34:11+00:00'}
        self.end=datetime.datetime.fromisoformat(self.window['hard_stop_UTC']).timestamp()
        self.gate={'schema':'a24-revision02-blocked-gate-v1','frozen':True,'reference_role':'SELECT_FIRST','block_id':'synthetic-block','Tref_c':None,'sensor_name':'AP','sensor_type':0,'tref_tolerance_c':.5,'maximum_abs_slope_c_per_min':.1,'history_ns':60000000000,'maximum_gate_wait_ns':600000000000,'soc_contract':'USER_SOC_GE10_20261015','minimum_SOC_percent':10,'maximum_SOC_percent':100,'require_unplugged':True,'hal_poll_period_ns':2000000000,'maximum_observation_gap_ns':10000000000,'status_poll_period_ns':2000000000,'ready_timeout_ns':240000000000,'session_timeout_ns':1500000000000,'maximum_raw_bytes':67108864,'environment_reviewed':True,'screen_contract':'synthetic PC fixture only'}
    def test_activity_and_main_start_have_different_reserved_time(self):
        self.assertEqual(check_deadline(self.window,'APP_CREATE',self.end-1260),1260)
        self.assertEqual(check_deadline(self.window,'MAIN_START',self.end-300),300)
        for phase,seconds in [('APP_CREATE',1259.9),('NEW_SESSION',1259.9),('MAIN_START',299.9),('RPC',.9),('RPC',-1),('UNKNOWN',9999)]:
            with self.subTest(phase=phase,seconds=seconds),self.assertRaises(ValidationError):check_deadline(self.window,phase,self.end-seconds)
    def test_legacy_unbounded_client_is_rejected_before_any_file_or_device(self):
        for client in (None,object()):
            with self.assertRaisesRegex(ValidationError,'deadline-aware'):run_one({}, {}, {}, {},execute_authorized=True,client=client)
    def test_first_reference_is_an_algorithm_not_old_absolute_temperature(self):
        frozen_gate(self.gate)
        for change in ({'reference_role':'REANCHOR'},{'tref_tolerance_c':5},{'maximum_gate_wait_ns':900000000000},{'sensor_type':2},{'minimum_SOC_percent':5}):
            gate=copy.deepcopy(self.gate);gate.update(change)
            with self.subTest(change=change),self.assertRaises(ValidationError):frozen_gate(gate)
    def test_fixed_reference_binds_same_block_and_exact_bytes(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'anchor.json';path.write_text(json.dumps({'block_id':'synthetic-block','Tref_c':26.9}))
            gate=copy.deepcopy(self.gate);gate.update(reference_role='MATCH_FIXED',Tref_c=26.9,block_reference_path=str(path),block_reference_sha256=sha256(path))
            frozen_gate(gate)
            for change in ({'Tref_c':28.5},{'block_id':'foreign'},{'block_reference_sha256':'0'*64}):
                changed=copy.deepcopy(gate);changed.update(change)
                with self.subTest(change=change),self.assertRaises(ValidationError):frozen_gate(changed)
            path.write_text(json.dumps({'block_id':'synthetic-block','Tref_c':27.0}))
            with self.assertRaises(ValidationError):frozen_gate(gate)

    def test_mock_event_flow_freezes_before_start_and_refuses_reanchoring(self):
        import d1_a24_revision02_control as control
        from d1_a24_laptop_mock import fixture_manifest
        from test_d1_a24_laptop_control import FakeAdb
        from unittest import mock
        class BoundedFake(FakeAdb):
            bounded_window_authorized=True
            def check_window(self,phase):self.calls.append(('WINDOW',phase))
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);m=fixture_manifest('C252_CPU');m.update(plan_id='SOFTWARE-MOCK-REV02',plan_sha256='1'*64)
            gate=copy.deepcopy(self.gate);gate.update(sensor_name='MOCK_AP',block_reference_path=str(root/'anchor.json'))
            config={'registry_root':str(root/control.PROTOCOL/m['plan_id']),'output_root':str(root/'raw'),'apk':{'path':'NEVER_EXECUTED.apk'},'files':[],'manifest_bytes':json.dumps(m).encode(),'gate_sha256':'2'*64,'manifest_sha256':'3'*64,'require_journal_closed_before_recovery':True}
            auth={'serial':'MOCK','fingerprint':'SOFTWARE-MOCK-FINGERPRINT'}
            authorized={k:m[k] for k in ('session_id','plan_id','plan_sha256')};authorized['namespace']=control.PROTOCOL
            fake=BoundedFake(m,ap=26.9,closure_delay_ns=0)
            def check_start(state,detail):
                if state=='START':
                    anchor=json.loads((root/'anchor.json').read_text())
                    self.assertTrue(anchor['frozen_before_any_main_request'])
                    self.assertEqual(detail['admission']['block_reference_sha256'],sha256(root/'anchor.json'))
            original_record=control.FutureRegistry.record
            def record(reg,state,detail):check_start(state,detail);return original_record(reg,state,detail)
            with mock.patch.object(control,'check_authorization',return_value=authorized),mock.patch.object(control.FutureRegistry,'record',record),mock.patch('subprocess.run',side_effect=AssertionError('physical command forbidden')):
                result=control.run_one(m,config,auth,gate,execute_authorized=True,client=fake)
            self.assertEqual(result['status'],'COMPLETE_TRACE_RECOVERED')
            self.assertEqual(json.loads((root/'anchor.json').read_text())['Tref_c'],26.9)
            self.assertIn(('WINDOW','APP_CREATE'),fake.calls)
            self.assertIn(('WINDOW','MAIN_START'),fake.calls)
            self.assertTrue((root/'raw'/m['session_id']/'journal_closed.json').exists())

if __name__=='__main__':unittest.main()
