import copy,unittest
from d1_a24_failed5_contract import CASES,PLAN_ID,ROLE,validate_plan
from d1_a24_failed5_runner import lifecycle_identity
from d1_a24_laptop_validator import ARMS
from d1_a24_laptop_plan import identity
from d1_a24_revision02_suite import RULES

def fixture():
 rows=[]
 for i,(name,old,key,_) in enumerate(CASES):
  r=dict(zip(['recipe','order','route','concurrency','wait_ms'],ARMS[key]));sid=identity(PLAN_ID,old)
  r.update(session_id=sid,original_failed_session_id=old,case_name=name,plan_id=PLAN_ID,plan_ordinal=i,stage='DEV',prescription_id=key,
   request_count=64 if i==1 else 32 if i==4 else 128,resident_mode='STANDARD',perfetto='ON' if i==4 else 'OFF',reference_role='SELECT_FIRST',
   reference_owner_session_id=sid,gate_block_id=PLAN_ID+'-'+name);rows.append(r)
 return {'schema':'a24-failed5-followon-v1','plan_id':PLAN_ID,'analysis_role':ROLE,'session_count':5,'sessions':rows,'reference_rules':copy.deepcopy(RULES),
  'historical_failures_preserved':True,'pooled_with_original_confirm':False,'maximum_new_attempts_per_failed_ID':1}

class Failed5(unittest.TestCase):
 def test_exact_five_480_requests(self):self.assertEqual(sum(r['request_count'] for r in validate_plan(fixture())),480)
 def test_replay_extra_or_original_identity_blocked(self):
  for mutation in ['extra','old','order']:
   p=fixture()
   if mutation=='extra':p['sessions'].append(copy.deepcopy(p['sessions'][0]))
   elif mutation=='old':p['sessions'][0]['session_id']=CASES[0][1]
   else:p['sessions'].reverse()
   with self.assertRaises(ValueError):validate_plan(p)
 def test_runtime_reference_or_prescription_change_blocked(self):
  for field in ['request_count','perfetto','resident_mode','reference_role','concurrency','wait_ms']:
   p=fixture();p['sessions'][1][field]='changed'
   with self.assertRaises(ValueError):validate_plan(p)
 def test_original_lifecycle_and_only_documented_trace_path_fix(self):self.assertTrue(lifecycle_identity()['MAIN_rules_unchanged'])

if __name__=='__main__':unittest.main()
