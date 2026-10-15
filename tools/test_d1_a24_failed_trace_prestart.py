import json
from pathlib import Path
import tempfile
import unittest
from d1_a24_failed_trace_prestart import CAUSE,verify_closed_trace_failure
from d1_a24_laptop_validator import PROTOCOL


class FailedTraceProof(unittest.TestCase):
    def fixture(self,p):
        root=p/'visit';raw=p/'closed';sid='new';plan={'plan_id':'plan'};row={'session_id':sid,'perfetto':'ON','request_count':2}
        reg=root/'registry'/PROTOCOL/'plan'/sid;reg.mkdir(parents=True);raw.mkdir()
        def write(path,x):path.write_text(json.dumps(x),encoding='utf-8')
        out={'status':'FAILED_PRESERVED','reason':CAUSE,'APP_launch_intent':True}
        write(root/(sid+'.outcome.json'),out);write(root/'WINDOW_STOPPED.json',{'outcomes':[out]})
        write(reg/'PRESTART_REJECT.json',{'START':False,'session_run_consumed':False,'reason':CAUSE})
        audit={'argv':['shell','perfetto','--txt','--detach=a24_new'],'exit':1,
            'stderr':'Could not open /data/local/tmp/a24-new-perfetto.pbtxt Permission denied'}
        (root/'adb_commands.jsonl').write_text(json.dumps(audit)+'\n')
        for name,value in [('identity',{'session_id':sid,'process_id':7}),('ready',{'session_id':sid,'plan_sha256':'a'}),
            ('journal_closed',{'session_id':sid,'process_id':7,'status':'SYNCED_AND_CLOSED'}),
            ('cleanup',{'status':'DRAINED','actual_return_confirmed':True,'error':None,'session_failure':'timeout'}),
            ('failure',{'status':'FAILED'}),('requests',[{'terminal_status':'UNFINISHED'}]*2)]:write(raw/(name+'.json'),value)
        (raw/'events.jsonl').write_text(json.dumps({'kind':'sensor_sample'})+'\n')
        return root,plan,row,raw,reg

    def test_closed_denied_config_preserves_failure_and_denominator(self):
        with tempfile.TemporaryDirectory() as d:
            r,p,row,raw,_=self.fixture(Path(d));x=verify_closed_trace_failure(r,p,row,raw,plan_sha256='a')
            self.assertFalse(x['MAIN_START']);self.assertEqual(x['planned_unfinished'],2);self.assertFalse(x['budget_refund'])

    def test_main_activity_missing_closure_or_claim_cannot_pass(self):
        for problem in ['activity','closure','claim']:
            with self.subTest(problem=problem),tempfile.TemporaryDirectory() as d:
                r,p,row,raw,reg=self.fixture(Path(d))
                if problem=='activity':(raw/'events.jsonl').write_text(json.dumps({'kind':'dispatch'})+'\n')
                elif problem=='closure':(raw/'journal_closed.json').unlink()
                else:(reg/'START.json').write_text('{}')
                with self.assertRaises((ValueError,FileNotFoundError)):
                    verify_closed_trace_failure(r,p,row,raw,plan_sha256='a')

    def test_success_or_ambiguous_capture_is_not_config_denial(self):
        for code in [0,124]:
            with self.subTest(exit=code),tempfile.TemporaryDirectory() as d:
                r,p,row,raw,_=self.fixture(Path(d));q=r/'adb_commands.jsonl';x=json.loads(q.read_text());x['exit']=code;q.write_text(json.dumps(x)+'\n')
                with self.assertRaises(ValueError):verify_closed_trace_failure(r,p,row,raw,plan_sha256='a')


if __name__=='__main__':unittest.main()
