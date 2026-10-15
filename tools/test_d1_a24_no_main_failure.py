import copy
import json
from pathlib import Path
import tempfile
import unittest

from d1_a24_laptop_validator import sha256, ValidationError, PROTOCOL
from d1_a24_no_main_failure import verify_failed_without_main


class NoMainCases(unittest.TestCase):
    def fixture(self, root):
        sid='11111111-1111-4111-8111-111111111111';plan={'plan_id':'MOCK'};row={'session_id':sid,'request_count':64}
        outcome={'session_id':sid,'status':'FAILED_PRESERVED','APP_launch_intent':True,
            'reason':'connection recovered after ambiguous mutation; never replay install/push/start/claim'}
        def write(path,obj):path.write_text(json.dumps(obj),encoding='utf-8')
        write(root/(sid+'.outcome.json'),outcome);write(root/'WINDOW_STOPPED.json',{'outcomes':[outcome]})
        reg=root/'registry'/PROTOCOL/'MOCK'/sid;reg.mkdir(parents=True)
        write(reg/'PRESTART_REJECT.json',{'START':False,'session_run_consumed':False})
        raw=root/'read_only_recovery'/sid/'recovered_app';raw.mkdir(parents=True)
        obs={'session_id':sid,'plan_sha256':'a'*64,'outcome_sha256':sha256(root/(sid+'.outcome.json')),
            'observations':[{'host_before_ns':n,'host_after_ns':n+1,'registered_identity_match':True,
                'all_app_processes_absent':True,'remote_output_directory_absent':True,'remote_start_approval_absent':True}
                for n in [0,6_000_000_000]]}
        write(raw/'NO_MAIN_READONLY_OBSERVATIONS.json',obs)
        return plan,row,raw,reg,obs

    def test_ambiguous_delivery_retains_consumed_budget_and_unknown_warmups(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);plan,row,raw,_,_=self.fixture(root)
            proof=verify_failed_without_main(root,plan,row,raw,plan_sha256='a'*64)
            self.assertEqual(proof['APP_budget_consumed'],1);self.assertFalse(proof['budget_refund'])
            self.assertFalse(proof['MAIN_START']);self.assertIsNone(proof['actual_warmup_calls'])
            self.assertFalse(proof['normal_comparison_eligible'])

    def test_any_process_output_approval_or_short_read_separation_blocks(self):
        for key in ['all_app_processes_absent','remote_output_directory_absent','remote_start_approval_absent','time']:
            with self.subTest(key=key),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);plan,row,raw,_,obs=self.fixture(root)
                if key=='time':obs['observations'][1]['host_after_ns']=10
                else:obs['observations'][1][key]=False
                (raw/'NO_MAIN_READONLY_OBSERVATIONS.json').write_text(json.dumps(obs))
                with self.assertRaises(ValidationError):verify_failed_without_main(root,plan,row,raw,plan_sha256='a'*64)

    def test_prior_MAIN_or_approval_upload_blocks(self):
        for key in ['START','approval']:
            with self.subTest(key=key),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);plan,row,raw,reg,_=self.fixture(root)
                if key=='START':(reg/'START.json').write_text('{}')
                else:(root/'adb_commands.jsonl').write_text(json.dumps({'argv':['push','x-'+row['session_id']+'-start_approval.json','remote']})+'\n')
                with self.assertRaises(ValidationError):verify_failed_without_main(root,plan,row,raw,plan_sha256='a'*64)


if __name__=='__main__':unittest.main()
