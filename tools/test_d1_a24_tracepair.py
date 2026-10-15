import copy
from pathlib import Path
import unittest
from d1_a24_tracepair_contract import PLAN_ID,ROLE,KEYS,validate_plan
from d1_a24_tracepair_runner import lifecycle_identity
from d1_a24_laptop_plan import identity
from d1_a24_laptop_validator import ARMS
from d1_a24_revision02_suite import RULES


def fixture():
    rows=[]
    for i,key in enumerate(KEYS):
        r=dict(zip(['recipe','order','route','concurrency','wait_ms'],ARMS[key]))
        r.update(session_id=identity(PLAN_ID,key),plan_id=PLAN_ID,plan_ordinal=i,stage='DEV',prescription_id=key,
            request_count=32,resident_mode='STANDARD',perfetto='OFF' if i==0 else 'ON',block='TRACE_REPAIR',
            reference_owner_session_id=identity(PLAN_ID,KEYS[0]),gate_block_id=PLAN_ID+'-TRACE',
            reference_role='SELECT_FIRST' if i==0 else 'MATCH_FIXED',bank_file='TRACE.json',bank_sha256='same',input_seed=123)
        rows.append(r)
    return {'schema':'a24-trace-config-path-repair2-v1','plan_id':PLAN_ID,'analysis_role':ROLE,'session_count':2,'sessions':rows,
        'reference_rules':copy.deepcopy(RULES),'old_failures_preserved':True,'pooled_with_original_confirm':False}


class TracePair(unittest.TestCase):
    def test_exact_pair_only(self):self.assertEqual(len(validate_plan(fixture())),2)
    def test_input_reference_trace_or_extra_attempt_changes_blocked(self):
        for field in ['bank_sha256','reference_role','perfetto','request_count']:
            p=fixture();p['sessions'][1][field]='changed'
            with self.assertRaises(ValueError):validate_plan(p)
        p=fixture();p['sessions'].append(copy.deepcopy(p['sessions'][0]))
        with self.assertRaises(ValueError):validate_plan(p)
    def test_only_documented_config_path_and_registration_differ(self):
        self.assertEqual(lifecycle_identity()['status'],'PASS_ORIGINAL_RUNTIME_WITH_TRACE_CONFIG_PATH_FIX')
        p=Path(__file__).resolve().parent/'d1_a24_tracepair_control.py';s=p.read_text(encoding='utf-8')
        self.assertIn('remote_profile = f"/data/misc/perfetto-configs/a24-{session_id}-perfetto.pbtxt"',s)
        self.assertNotIn('remote_profile = f"/data/local/tmp/',s)


if __name__=='__main__':unittest.main()
