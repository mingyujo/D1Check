import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from tools import d1_arrival_collection as c

class SummaryTest(unittest.TestCase):
    def build(self,root,count,followup=True):
        plan=dict(output_root=str(root/'out'),registry=str(root/'registry'),entries=[])
        if followup:plan['installation_contract']='followup-exact-installed-v1'
        folder=root/'out'/'confirmation';folder.mkdir(parents=True)
        (folder/'complete.json').write_text('{}')
        for i in range(count):
            plan['entries'].append(dict(index=i,session_id=str(i),phase='confirmation',condition='condition'+str(i)))
            d=folder/f'{i:02d}_{i}';(d/'artifacts').mkdir(parents=True)
            (d/'host_cleanup.json').write_text('{"status":"completed"}');(d/'validated.json').write_text('{}')
            rows=[dict(request_id=str(j),task_id='classification',selected_backend='CPU',priority='urgent',dispatch_ns=3,
                execution_start_ns=4,output_ready_ns=5,persist_complete_ns=6,lane_available_ns=7) for j in range(4)]
            trace=dict(records=[dict(actual_selected=dict(request_id=str(j)),snapshot_ns=0,compute_start_ns=0,compute_end_ns=1,selection_end_ns=1,record_end_ns=2) for j in range(4)])
            for name,value in (('requests',rows),('collection_trace',trace)):(d/'artifacts'/f'{name}.json').write_text(json.dumps(value))
        p=root/'plan.json';p.write_text(json.dumps(plan));return p

    def test_three_condition_followup_summary(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(c,'verify_recovery'):
            r=c.summarize(self.build(Path(tmp),3),'confirmation');self.assertEqual(len(r['conditions']),3)

    def test_legacy_six_condition_rule_preserved(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(c,'verify_recovery'):
            with self.assertRaises(ValueError):c.summarize(self.build(Path(tmp),3,False),'confirmation')

    def test_missing_followup_condition_not_accepted(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(c,'verify_recovery'):
            with self.assertRaises(ValueError):c.summarize(self.build(Path(tmp),2),'confirmation')

if __name__=='__main__':unittest.main()
