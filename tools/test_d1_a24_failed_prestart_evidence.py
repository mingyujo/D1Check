import copy
import json
from pathlib import Path
import tempfile
import unittest

from d1_a24_failed_prestart_evidence import verify_failed_prestart
from d1_a24_laptop_validator import PROTOCOL, ValidationError


class FailedPrestartCases(unittest.TestCase):
    def fixture(self, root):
        def write(p, x):
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(x), encoding='utf-8')
        reg = root/'registry'/PROTOCOL/'p'/'s'
        raw = root/'read_only_recovery'/'s'/'recovered_app'
        write(root/'s.outcome.json', {'session_id':'s','status':'PRESTART_REJECT','APP_launch_intent':True})
        write(reg/'PRESTART_REJECT.json', {'START':False,'session_run_consumed':False})
        for n,x in {
            'identity.json':{'session_id':'s','process_id':123},
            'ready.json':{'session_id':'s','plan_sha256':'a'*64},
            'journal_closed.json':{'session_id':'s','process_id':123,'status':'SYNCED_AND_CLOSED'},
            'cleanup.json':{'status':'DRAINED','actual_return_confirmed':True,'error':None,'session_failure':'timeout'},
            'failure.json':{'status':'FAILED'},
            'requests.json':[{'terminal_status':'UNFINISHED'}]*2,
        }.items():write(raw/n,x)
        (raw/'events.jsonl').write_text(json.dumps({'kind':'warmup_result'})+'\n'+json.dumps({'kind':'session_failure'})+'\n')
        return reg,raw

    def check(self,root,raw):
        return verify_failed_prestart(root,{'plan_id':'p'},{'session_id':'s','request_count':2},raw,plan_sha256='a'*64)

    def test_closed_rejection_remains_consumed_and_unfinished(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);_,raw=self.fixture(root);x=self.check(root,raw)
            self.assertEqual(x['APP_budget_consumed'],1)
            self.assertEqual(x['planned_unfinished'],2)
            self.assertFalse(x['normal_comparison_eligible'])
            self.assertFalse(x['budget_refund'])

    def test_MAIN_claim_drain_identity_closure_and_request_counterexamples_rejected(self):
        for kind in ['START','CLAIM','COMPLETE','launched_false','wrong_outcome','reject_started',
                     'identity','ready_hash','closed_pid','not_closed','not_drained','not_returned',
                     'cleanup_error','failure_missing','MAIN_event','missing_request','completed_request']:
            with self.subTest(kind=kind),tempfile.TemporaryDirectory() as t:
                root=Path(t);reg,raw=self.fixture(root)
                def update(p,**changes):
                    x=json.loads(p.read_text());x.update(changes);p.write_text(json.dumps(x))
                if kind in {'START','CLAIM','COMPLETE'}:(reg/(kind+'.json')).write_text('{}')
                elif kind=='launched_false':update(root/'s.outcome.json',APP_launch_intent=False)
                elif kind=='wrong_outcome':update(root/'s.outcome.json',status='COMPLETE_TRACE_RECOVERED')
                elif kind=='reject_started':update(reg/'PRESTART_REJECT.json',START=True)
                elif kind=='identity':update(raw/'identity.json',session_id='other')
                elif kind=='ready_hash':update(raw/'ready.json',plan_sha256='b'*64)
                elif kind=='closed_pid':update(raw/'journal_closed.json',process_id=456)
                elif kind=='not_closed':update(raw/'journal_closed.json',status='OPEN')
                elif kind=='not_drained':update(raw/'cleanup.json',status='DRAIN_FAILED')
                elif kind=='not_returned':update(raw/'cleanup.json',actual_return_confirmed=False)
                elif kind=='cleanup_error':update(raw/'cleanup.json',error='busy')
                elif kind=='failure_missing':update(raw/'failure.json',status='OK')
                elif kind=='MAIN_event':(raw/'events.jsonl').write_text(json.dumps({'kind':'common_start'})+'\n')
                elif kind=='missing_request':(raw/'requests.json').write_text('[{"terminal_status":"UNFINISHED"}]')
                elif kind=='completed_request':(raw/'requests.json').write_text('[{"terminal_status":"COMPLETED"},{"terminal_status":"UNFINISHED"}]')
                with self.assertRaises(ValidationError):self.check(root,raw)


if __name__=='__main__':unittest.main()
