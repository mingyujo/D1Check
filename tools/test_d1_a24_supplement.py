import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from d1_a24_supplement_contract import CASES, PLAN_ID, ROLE, validate_plan
from d1_a24_supplement_runner import lifecycle_identity, require_no_prior_owners
from d1_a24_confirm_after_diagnostic import FollowupClient
from d1_a24_laptop_plan import identity
from d1_a24_laptop_validator import ARMS, ValidationError
from d1_a24_revision02_suite import RULES


class SupplementCases(unittest.TestCase):
    def plan(self):
        rows=[]
        for i,(name,old,key) in enumerate(CASES):
            sid=identity(PLAN_ID,old);spec=ARMS[key];group='TRACE' if i in {2,3} else name
            rows.append(dict(zip(['recipe','order','route','concurrency','wait_ms'],spec),
                session_id=sid,original_failed_session_id=old,case_name=name,plan_id=PLAN_ID,plan_ordinal=i,stage='DEV',
                prescription_id=key,request_count=0 if i<2 else 32 if i<4 else 64 if i==6 else 128 if i in {7,10,11} else 252,
                resident_mode='NONE' if i==0 else 'STANDARD',perfetto='ON' if i==3 else 'OFF',
                reference_role='MATCH_FIXED' if i==3 else 'SELECT_FIRST',gate_block_id=PLAN_ID+'-'+group,
                reference_owner_session_id=identity(PLAN_ID,CASES[2][1]) if i==3 else sid,bank_sha256='a'*64))
        return {'schema':'a24-failed-supplement-v1','plan_id':PLAN_ID,'analysis_role':ROLE,'sessions':rows,'session_count':12,
                'reference_rules':RULES,'pooled_with_original_confirm':False,'historical_failures_preserved':True,
                'maximum_new_attempts_per_failed_ID':1}

    def test_exact12_new_ids_preserve_prescription_and_exclude_recovered_GPU(self):
        rows=validate_plan(self.plan())
        self.assertEqual(len({r['session_id'] for r in rows}),12)
        self.assertFalse({r['session_id'] for r in rows}&{c[1] for c in CASES})
        self.assertNotIn('1165a564-7dba-5ed9-bfe9-50cd7ac2c5e3',{c[1] for c in CASES})
        self.assertEqual(sum(r['request_count'] for r in rows),1520)

    def test_never_promote_old_failure_or_expand_scope_or_resources(self):
        for case in ['oldid','duplicate','thirteenth','pool','sla','npu','trace','resident','repeat','count','reference','bank']:
            with self.subTest(case=case):
                p=copy.deepcopy(self.plan());r=p['sessions'][3]
                if case=='oldid':r['session_id']=CASES[3][1]
                elif case=='duplicate':r['session_id']=p['sessions'][2]['session_id']
                elif case=='thirteenth':p['sessions'].append(copy.deepcopy(r))
                elif case=='pool':p['pooled_with_original_confirm']=True
                elif case=='sla':p['reference_rules']={**RULES,'tolerance_c':2}
                elif case=='npu':r['route']='NPU'
                elif case=='trace':r['perfetto']='OFF'
                elif case=='resident':p['sessions'][0]['resident_mode']='STANDARD'
                elif case=='repeat':p['maximum_new_attempts_per_failed_ID']=2
                elif case=='count':r['request_count']=16
                elif case=='reference':r['reference_role']='SELECT_FIRST'
                elif case=='bank':r['bank_sha256']='b'*64
                with self.assertRaises(ValidationError):validate_plan(p)

    def test_original_MAIN_wait_completion_and_lane_functions_unchanged(self):
        proof=lifecycle_identity()
        self.assertIn('run_one',proof['same_functions_and_classes'])
        self.assertIn('admission',proof['same_functions_and_classes'])

    def test_active_previous_owner_blocks_new_measurement(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent=Path(tmp);p=parent/'A24R02C10_GLOBAL';p.mkdir();(p/'ACTIVE_OWNER.json').write_text('{}')
            with self.assertRaises(ValidationError):require_no_prior_owners(parent)
            (p/'ACTIVE_OWNER.json').unlink();require_no_prior_owners(parent)

    def test_thirteenth_APP_blocked_before_device_or_parent(self):
        with tempfile.TemporaryDirectory() as tmp:
            client=object.__new__(FollowupClient);client.global_root=Path(tmp);client.active_sid='new'
            client.ledger={'total_consumed':85,'cap':97}
            for i in range(12):
                p=client.global_root/'reservations'/str(i);p.mkdir(parents=True);(p/'APP_LAUNCH_INTENT.json').write_text('{}')
            with patch('d1_a24_revision02_window.BoundedClient.command') as parent:
                with self.assertRaises(ValidationError):client.command('shell','am','start','--es','session_id','new')
                parent.assert_not_called()


if __name__=='__main__':unittest.main()
