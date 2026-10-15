import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from d1_a24_extra4_contract import PLAN_ID, ROLE, SCHEMA, ORDER, validate_extra4_plan
from d1_a24_extra4_runner import lifecycle_identity, ExtraClient
from d1_a24_laptop_plan import identity
from d1_a24_laptop_validator import ValidationError
from d1_a24_revision02_suite import draft_plan, RULES


class Extra4Cases(unittest.TestCase):
    def plan(self):
        old,_=draft_plan('A24R02-SUITE-EXTRA4-TEST')
        rows=[]
        for i,arm in enumerate(ORDER):
            row=copy.deepcopy(next(r for r in old['sessions'] if r['block']=='R02CONFIRM03' and r['recipe']=='M128' and r['arm']==arm))
            row.update(session_id=identity(PLAN_ID,'EXTRA4:'+arm),plan_id=PLAN_ID,stage='DEV',block='REBASE_M128_01',plan_ordinal=i,
                gate_block_id=PLAN_ID+'-REBASE_M128_01',reference_owner_session_id=identity(PLAN_ID,'EXTRA4:'+ORDER[0]),
                reference_role='SELECT_FIRST' if i==0 else 'MATCH_FIXED')
            rows.append(row)
        return {'schema':SCHEMA,'plan_id':PLAN_ID,'analysis_role':ROLE,'sessions':rows,'session_count':4,'reference_rules':RULES,
                'retry_or_replacement':0,'original_confirm40_preserved':True,'pooled_with_original_confirm':False,
                'original_M128_bank_sha256':rows[0]['bank_sha256']}

    def test_exact_new4_keeps_prescriptions_and_shared_input(self):
        p=self.plan();rows=validate_extra4_plan(p)
        self.assertEqual(sum(r['request_count'] for r in rows),512)
        self.assertEqual(len({r['session_id'] for r in rows}),4)

    def test_counts_identity_controls_input_role_and_scope_not_relaxed(self):
        for kind in ['count','duplicate','route','wait','requests','role','owner','bank','rule','pool','independent']:
            with self.subTest(kind=kind):
                p=self.plan();r=p['sessions'][1]
                if kind=='count':p['sessions'].pop()
                elif kind=='duplicate':r['session_id']=p['sessions'][0]['session_id']
                elif kind=='route':r['route']='D_GPU'
                elif kind=='wait':r['wait_ms']=500
                elif kind=='requests':r['request_count']=64
                elif kind=='role':r['reference_role']='SELECT_FIRST'
                elif kind=='owner':r['reference_owner_session_id']='foreign'
                elif kind=='bank':r['bank_sha256']='b'*64
                elif kind=='rule':p['reference_rules']={**RULES,'tolerance_c':5}
                elif kind=='pool':p['pooled_with_original_confirm']=True
                elif kind=='independent':p['analysis_role']='INDEPENDENT_CONFIRM40'
                with self.assertRaises(ValidationError):validate_extra4_plan(p)

    def test_lifecycle_is_identical_including_admission_response_and_lane_release(self):
        x=lifecycle_identity();self.assertEqual(x['status'],'PASS_EXACT_COMMON_LIFECYCLE')
        self.assertIn('run_one',x['same_functions_and_classes'])
        self.assertIn('admission',x['same_functions_and_classes'])

    def test_fifth_extra_APP_is_rejected_before_parent_or_device(self):
        with tempfile.TemporaryDirectory() as t:
            c=object.__new__(ExtraClient);c.global_root=Path(t)
            for i in range(4):
                p=c.global_root/'reservations'/str(i);p.mkdir(parents=True);(p/'APP_LAUNCH_INTENT.json').write_text('{}')
            with patch('d1_a24_confirm_after_diagnostic.FollowupClient.command') as parent:
                with self.assertRaises(ValidationError):c.command('shell','am','start')
                parent.assert_not_called()


if __name__=='__main__':unittest.main()
