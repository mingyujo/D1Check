"""Software-only suite contracts and mocked lifecycle, never a physical client."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import d1_a24_revision02_suite as suite
import d1_a24_revision02_suite_control as control
from d1_a24_laptop_plan import encode
from d1_a24_laptop_validator import ValidationError, sha256
from d1_a24_laptop_mock import fixture_manifest
from test_d1_a24_laptop_control import FakeAdb
import test_d1_a24_revision02_window as pilot_tests


class PlanCases(unittest.TestCase):
    def test_confirmation40_preserves_all_arms_quantities_and15_shared_references(self):
        plan, banks = suite.draft_plan('A24R02-SUITE-PC-CONFIRM')
        suite.validate_plan(plan)
        self.assertEqual(len(plan['sessions']), 40)
        self.assertEqual(sum(r['request_count'] for r in plan['sessions']), 5720)
        self.assertEqual(len(banks), 15)
        self.assertEqual(sum(r['reference_role'] == 'SELECT_FIRST' for r in plan['sessions']), 15)
        self.assertFalse(plan['execution_authorized'])

    def test_reproducible_order_and_separate_DEV_CONFIRM_seeds_and_identities(self):
        a, _ = suite.draft_plan('A24R02-SUITE-PC-CONFIRM')
        b, _ = suite.draft_plan('A24R02-SUITE-PC-CONFIRM')
        dev, _ = suite.draft_plan('A24R02-SUITE-PC-DEV', stage='DEV')
        self.assertEqual(a, b)
        self.assertNotEqual(dev['order_seed'], a['order_seed'])
        self.assertFalse({r['session_id'] for r in a['sessions']} & {r['session_id'] for r in dev['sessions']})

    def test_missing_arm_changed_dose_wrong_reference_or_smaller_confirmation_rejected(self):
        original, _ = suite.draft_plan('A24R02-SUITE-PC-CONFIRM')
        variations = []
        p = copy.deepcopy(original);p['sessions'] = p['sessions'][:24];p['session_count'] = 24;variations.append(p)
        for key, value in [('wait_ms', 1000), ('route', 'C_GPU'), ('reference_role', 'MATCH_FIXED'), ('request_count', 63), ('reference_owner_session_id', 'foreign')]:
            p = copy.deepcopy(original);p['sessions'][0][key] = value;variations.append(p)
        for p in variations:
            with self.subTest(p=p['sessions'][0]), self.assertRaises(ValidationError):suite.validate_plan(p)

    def test_default_dispatch_never_calls_native_or_creates_files(self):
        with tempfile.TemporaryDirectory() as td, mock.patch('subprocess.run', side_effect=AssertionError('physical command forbidden')):
            for kwargs in [{}, {'execute_authorized': True}, {'client': object()}]:
                with self.assertRaises(ValidationError):suite.run_registered_session({}, {}, {}, {}, **kwargs)
            self.assertEqual(list(Path(td).iterdir()), [])

    def test_later_arm_cannot_reanchor_and_uses_exact_first_arm_reference(self):
        plan,_=suite.draft_plan('A24R02-SUITE-PC-REFERENCE')
        first,later=plan['sessions'][:2]
        with tempfile.TemporaryDirectory() as td:
            base={'frozen':False,'Tref_c':123.0}
            self.assertIsNone(suite.gate_for_registered_row(first,base,td)['Tref_c'])
            with self.assertRaises(ValidationError):suite.gate_for_registered_row(later,base,td)
            p=Path(td)/'references'/(first['gate_block_id']+'.json');p.parent.mkdir()
            p.write_bytes(encode({'block_id':first['gate_block_id'],'reference_session_id':first['session_id'],'Tref_c':28.6}))
            gate=suite.gate_for_registered_row(later,base,td)
            self.assertEqual(gate['Tref_c'],28.6);self.assertEqual(gate['block_reference_sha256'],sha256(p));self.assertFalse(gate['frozen'])

    def test_passive_wait_never_creates_app_and_does_not_start_above_reference(self):
        class Clock:
            def __init__(self):self.i=0;self.sleeps=0
            def check_window(self,phase):
                if self.i>60:raise AssertionError('time failed to advance')
            def sleep_ns(self,n):self.sleeps+=1
        clock=Clock()
        def hal(client):
            i=client.i;client.i+=1
            return {'device_elapsed_before_ns':i*5*10**9,'device_elapsed_after_ns':i*5*10**9+1,'sensors':[{'sensor_name':'AP','sensor_type':0,'value_c':29.1 if i<15 else 28.6}]}
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'ref.json';p.write_bytes(encode({'Tref_c':28.6}))
            gate={'reference_role':'MATCH_FIXED','block_reference_path':str(p),'block_reference_sha256':sha256(p)}
            with mock.patch.object(control,'read_hal',side_effect=hal),mock.patch('subprocess.run',side_effect=AssertionError('physical command forbidden')):
                suite.passive_before_dispatch(clock,gate)
            self.assertGreaterEqual(clock.i,28);self.assertGreater(clock.sleeps,0)

    def test_wrapper_orders_full_authorization_before_passive_wait_and_lifecycle(self):
        class Bounded:bounded_window_authorized=True
        order=[]
        def lifecycle(*a,**kw):order.append('lifecycle');return {'status':'COMPLETE_TRACE_RECOVERED'}
        def closed(*a,**kw):order.append('proved-closed-process');return True
        with mock.patch.object(control,'check_authorization',side_effect=lambda *a,**kw:order.append('auth')),mock.patch.object(suite,'passive_before_dispatch',side_effect=lambda *a:order.append('passive')),mock.patch.object(control,'run_one',side_effect=lifecycle),mock.patch('d1_a24_measurement_batch.finish_only_closed_owned_process',side_effect=closed):
            suite.run_registered_session({'session_id':'SOFTWARE-MOCK'}, {'output_root':'SOFTWARE-MOCK/raw','registry_root':'SOFTWARE-MOCK/registry'}, {}, {},execute_authorized=True,client=Bounded())
        self.assertEqual(order,['auth','passive','lifecycle','proved-closed-process'])

    def test_used_session_rejected_before_even_passive_queries(self):
        class Bounded:bounded_window_authorized=True
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);(root/'registry/used').mkdir(parents=True)
            with mock.patch.object(control,'check_authorization'),mock.patch.object(suite,'passive_before_dispatch',side_effect=AssertionError('passive query forbidden')),self.assertRaisesRegex(ValidationError,'already attempted'):
                suite.run_registered_session({'session_id':'used'},{'output_root':str(root/'raw'),'registry_root':str(root/'registry')},{},{},execute_authorized=True,client=Bounded())

    def test_draft_writer_never_grants_execution_or_creates_auth_registry(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td);templates = root/'templates';templates.mkdir()
            for arm in suite.ARM_KEYS:
                m = fixture_manifest(arm)
                m['arm'] = arm[len(m['recipe'])+1:]
                m['models'] = {k: {'identity': {'session_id': m['session_id']}} for k in ['C_CPU','C_GPU','D_CPU','D_GPU']}
                for q in m['requests']:q.update(input_file='approved.png',input_sha256='1'*64,tensor_sha256=('2' if q['task']=='C' else '3')*64)
                (templates/(arm+'.json')).write_bytes(encode(m))
            summary = suite.write_draft(root/'draft','A24R02-SUITE-PC-WRITER',templates=templates)
            self.assertEqual(summary['sessions'],40)
            for p in (root/'draft/manifests').glob('*.json'):
                m=json.loads(p.read_text());self.assertFalse(m['execution_authorized']);self.assertTrue(m['mock'])
            self.assertFalse(list((root/'draft').rglob('authorization.json')))
            self.assertFalse((root/'draft/registry').exists())
            with self.assertRaises(ValidationError):suite.write_draft(root/'draft','A24R02-SUITE-PC-WRITER',templates=templates)


class RegistrationCases(unittest.TestCase):
    """All approvals below are hypothetical in TemporaryDirectory; never published."""
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.plan,self.banks=suite.draft_plan('A24R02-SUITE-PC-FUTURE')
        self.plan.update(status='FROZEN_EXECUTION_PLAN',execution_authorized=True)
        self.config={'output_root':str(self.root/'raw'),'registry_root':str(self.root/'a24-laptop-measurement-v1'/self.plan['plan_id']),'source_code_sha256':'b'*64,'apk':{'sha256':'c'*64}}
        self.auth={'fingerprint':'SOFTWARE-MOCK-FINGERPRINT'};self.bind('suite_plan_file','suite_plan_sha256',self.plan)
        self.row=self.plan['sessions'][0]
        for key,bank in self.banks.items():
            p=self.root/'banks'/(key+'.json');p.parent.mkdir(exist_ok=True);p.write_bytes(encode(bank))
        self.m={**self.row,'revision_id':suite.REVISION,'plan_sha256':self.config['suite_plan_sha256'],'requests':self.banks[self.row['block']+'_'+self.row['recipe']]['requests']}
        self.gate={'block_id':self.row['gate_block_id'],'reference_role':'SELECT_FIRST','block_reference_path':str(self.root/'references'/(self.row['gate_block_id']+'.json'))}
        self.contract={'status':'FROZEN_EXECUTION_CONTRACT','plan_sha256':self.m['plan_sha256'],'reference_rules':suite.RULES,'energy_J':None,'surface_temperature_verified':False}
        self.bind('revision_contract_file','revision_contract_sha256',self.contract)
        self.budget={'authorized':True,'plan_sha256':self.m['plan_sha256'],'cap':73,'spent_before_plan':33,'reserved_for_plan':40}
        self.bind('budget_file','budget_sha256',self.budget)
        self.bind('window_file','window_sha256',{'execution_authorized':True,'plan_sha256':self.m['plan_sha256'],'hard_stop_UTC':'2100-01-01T00:00:00+00:00'})
        self.freeze={'status':'FROZEN_BEFORE_CONFIRM','plan_sha256':self.m['plan_sha256'],'planned_confirm_sessions':40,'independent_blocks':5,'old_confirm_results_pooled':False,'apk_sha256':'c'*64,'source_sha256':'b'*64,'budget_sha256':self.config['budget_sha256']}
        docs={'analysis_contract':{'frozen':True,'planned_confirm_sessions':40},'pre_measurement_predictions':{'status':'NOT_CREATED_NO_MODEL_ACCURACY_CLAIM'},'prior_stage_ledger':{'attempt_counts':{'I':4,'F':4,'DEV':16}},'new_protocol_functional_evidence':{'status':'DEVICE_VALIDATED','mock':False,'NN_calls':1,'supported_arms':sorted(suite.ARM_KEYS),'source_sha256':'b'*64,'apk_sha256':'c'*64,'device_fingerprint':'SOFTWARE-MOCK-FINGERPRINT'}}
        for key,value in docs.items():self.bind(key,key+'_sha256',value);self.freeze[key+'_sha256']=self.config[key+'_sha256']
        self.bind('confirm_freeze','confirm_freeze_sha256',self.freeze)

    def bind(self,key,sha_key,value):
        p=self.root/(key+'.json');p.write_bytes(encode(value));self.config[key]=str(p);self.config[sha_key]=self.auth[sha_key]=sha256(p)

    def check(self):return suite.validate_suite_registration(self.m,self.config,self.auth,self.gate)

    def test_hypothetical_complete_future_contract_accepts_registered_row(self):
        self.assertEqual(self.check(),self.row)

    def test_current31_unallocated_cannot_authorize40_or_shrink_it(self):
        self.budget['cap']=64;self.bind('budget_file','budget_sha256',self.budget)
        with self.assertRaisesRegex(ValidationError,'insufficient'):self.check()

    def test_PC_draft_is_rejected_even_with_other_hypothetical_certificates(self):
        self.plan.update(status='PC_DRAFT_NOT_APPROVED',execution_authorized=False);self.bind('suite_plan_file','suite_plan_sha256',self.plan)
        with self.assertRaisesRegex(ValidationError,'PC draft'):self.check()

    def test_expired_window_rejected_without_any_device_query(self):
        self.bind('window_file','window_sha256',{'execution_authorized':True,'plan_sha256':self.m['plan_sha256'],'hard_stop_UTC':'2000-01-01T00:00:00+00:00'})
        with mock.patch('subprocess.run',side_effect=AssertionError('physical command forbidden')), self.assertRaisesRegex(ValidationError,'bounded window'):self.check()

    def test_missing_freeze_or_changed_analysis_bytes_rejected(self):
        Path(self.config['confirm_freeze']).unlink()
        with self.assertRaisesRegex(ValidationError,'confirm_freeze'):self.check()
        self.bind('confirm_freeze','confirm_freeze_sha256',self.freeze)
        Path(self.config['analysis_contract']).write_bytes(b'{}')
        with self.assertRaisesRegex(ValidationError,'analysis_contract'):self.check()

    def test_PC_mock_cannot_substitute_for_device_functional_evidence(self):
        key='new_protocol_functional_evidence';value=json.loads(Path(self.config[key]).read_text());value['mock']=True
        self.bind(key,key+'_sha256',value);self.freeze[key+'_sha256']=self.config[key+'_sha256'];self.bind('confirm_freeze','confirm_freeze_sha256',self.freeze)
        with self.assertRaisesRegex(ValidationError,'functional validation'):self.check()

    def test_wrong_shared_reference_block_or_policy_rejected(self):
        self.gate['block_id']='foreign'
        with self.assertRaisesRegex(ValidationError,'reference group'):self.check()
        self.gate['block_id']=self.row['gate_block_id'];self.m['wait_ms']=1000
        with self.assertRaisesRegex(ValidationError,'exact registered'):self.check()

    def test_device_functional_evidence_from_another_phone_rejected(self):
        self.auth['fingerprint']='OTHER-PHONE'
        with self.assertRaisesRegex(ValidationError,'another device'):self.check()


class LifecycleCases(unittest.TestCase):
    def test_all8_mock_lifecycles_preserve_requests_and_close_without_native_commands(self):
        class BoundedFake(FakeAdb):
            bounded_window_authorized=True
            def check_window(self,phase):self.calls.append(('WINDOW',phase))
        for arm in sorted(suite.ARM_KEYS):
            with self.subTest(arm=arm),tempfile.TemporaryDirectory() as td:
                root=Path(td);m=fixture_manifest(arm);m.update(plan_id='SOFTWARE-MOCK-SUITE',plan_sha256='1'*64)
                base=pilot_tests.BoundedRevisionCases();base.setUp();gate=copy.deepcopy(base.gate);gate.update(sensor_name='MOCK_AP',block_reference_path=str(root/'references/reference.json'))
                config={'registry_root':str(root/control.PROTOCOL/m['plan_id']),'output_root':str(root/'raw'),'apk':{'path':'NEVER_EXECUTED.apk'},'files':[],'manifest_bytes':json.dumps(m).encode(),'gate_sha256':'2'*64,'manifest_sha256':'3'*64,'require_journal_closed_before_recovery':True}
                authorized={k:m[k] for k in ['session_id','plan_id','plan_sha256']};authorized['namespace']=control.PROTOCOL
                fake=BoundedFake(m,ap=26.9,closure_delay_ns=0)
                with mock.patch.object(control,'check_authorization',return_value=authorized),mock.patch('subprocess.run',side_effect=AssertionError('physical command forbidden')):
                    result=control.run_one(m,config,{'serial':'MOCK','fingerprint':'SOFTWARE-MOCK-FINGERPRINT'},gate,execute_authorized=True,client=fake)
                self.assertEqual(result['status'],'COMPLETE_TRACE_RECOVERED')
                self.assertEqual(result['trace']['metrics']['planned'],len(m['requests']))
                self.assertTrue((root/'raw'/m['session_id']/'journal_closed.json').exists())


if __name__ == '__main__':unittest.main()
