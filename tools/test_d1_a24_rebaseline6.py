import copy
import unittest
from d1_a24_rebaseline6_contract import PLAN_ID,ROLE,KEYS,validate_plan
from d1_a24_rebaseline6_runner import lifecycle_identity
from d1_a24_laptop_plan import identity
from d1_a24_laptop_validator import ARMS
from d1_a24_revision02_suite import RULES


def fixture():
    rows=[]
    for i,key in enumerate(KEYS):
        recipe=key.split('_')[0];first=0 if i<2 else 2
        row=dict(zip(['recipe','order','route','concurrency','wait_ms'],ARMS[key]))
        row.update(plan_id=PLAN_ID,session_id=identity(PLAN_ID,key),prescription_id=key,plan_ordinal=i,stage='DEV',
            request_count=64 if i<2 else 128,resident_mode='STANDARD',perfetto='OFF',block='NEW_'+recipe,
            gate_block_id=PLAN_ID+'-'+recipe,reference_role='SELECT_FIRST' if i==first else 'MATCH_FIXED',
            reference_owner_session_id=identity(PLAN_ID,KEYS[first]),bank_file=recipe+'.json',bank_sha256=recipe,input_seed=123)
        rows.append(row)
    return {'schema':'a24-matched-rebaseline6-v1','plan_id':PLAN_ID,'analysis_role':ROLE,'session_count':6,'sessions':rows,
        'reference_rules':copy.deepcopy(RULES),'pooled_with_original_confirm':False,'old_failures_preserved':True}


class MatchedCohort(unittest.TestCase):
    def test_exact_shared_groups(self):self.assertEqual(len(validate_plan(fixture())),6)
    def test_own_reference_or_changed_pair_input_blocked(self):
        for change in ['reference_owner_session_id','bank_sha256','reference_role']:
            p=fixture();p['sessions'][1][change]='foreign'
            with self.assertRaises(ValueError):validate_plan(p)
    def test_extra_attempt_old_id_or_weaker_main_blocked(self):
        for change in ['extra','old','weaker']:
            p=fixture()
            if change=='extra':p['sessions'].append(copy.deepcopy(p['sessions'][-1]))
            elif change=='old':p['sessions'][0]['session_id']=identity('OLD','BASE')
            else:p['reference_rules']['maximum_wait_ns']+=1
            with self.assertRaises(ValueError):validate_plan(p)
    def test_runtime_lifecycle_is_unchanged(self):
        self.assertEqual(lifecycle_identity()['status'],'PASS_EXACT_COMMON_LIFECYCLE')


if __name__=='__main__':unittest.main()
