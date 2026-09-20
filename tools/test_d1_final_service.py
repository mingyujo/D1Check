import copy
import datetime as dt
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from tools import d1_final_service as f
from tools import d1_service_model as sm
from tools.d1_final_calib import save_new


class FinalServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)

    def test_frozen_bytes_immutable(self):
        p=self.root/'frozen_contract.json';save_new(p,{'model':1});h=f.digest(p)
        p.write_text('{"model":2}')
        with self.assertRaisesRegex(ValueError,'mutated'):f.validate_frozen(self.root,h)

    def test_required_state_model_never_merges_transition_into_cold(self):
        sessions=[]
        for s in ('a','b','c'):
            rows=[]
            for i,(b,first,transition) in enumerate([('CPU',True,False),('CPU',False,False),('GPU',False,True),('GPU',False,False)]):
                rows.append(dict(session_id=s,request_id=s+str(i),cell='classification/'+b,first=first,transition=transition,
                                 from_backend='CPU' if transition else None,ordinal=1 if first or transition else 2,
                                 gap_ns=1,service_ns=100+i,priority='normal',pair='solo'))
            sessions.append(dict(session_id=s,rows=rows))
        a,b=f.select_model(sessions,dict(wape_max=.4));c,d=f.select_model(sessions,dict(wape_max=.4))
        self.assertIn(a['candidate'],sm.CANDIDATES[3:]);self.assertEqual(a,c);self.assertEqual(b,d)
        self.assertTrue(any('transition_CPU_to_GPU' in k for k in a['cells']))

    def test_original_coverage_not_relaxed(self):
        schema=f.read(Path('tools/schemas/service-final-freeze-v1.schema.json'))
        self.assertEqual(schema['properties']['criteria']['properties']['required_empirical_coverage']['const'],.9)

    def test_holdout_count_required_before_metrics(self):
        x=dict(plan=dict(sessions=[]),model={})
        with patch.object(sm,'check_prospective'):
            with self.assertRaisesRegex(ValueError,'16'):f.evaluate_sessions(x,[])

    def test_plan_replay_rejected(self):
        p=dict(plan=dict(sessions=[dict(session_id='a'),dict(session_id='a')]))
        with self.assertRaisesRegex(ValueError,'replay'):f.validate_partition(p)

    def test_cross_phase_leakage_rejected(self):
        e=[dict(session_id=str(i),phase=p) for i,p in enumerate('A'*4+'B'*16+'C'*2)]
        x=dict(plan=dict(sessions=e),calibration_sessions=['4'],previously_seen=[])
        with self.assertRaisesRegex(ValueError,'leakage'):f.validate_partition(x)

    def test_previously_seen_holdout_rejected(self):
        e=[dict(session_id=str(i),phase=p) for i,p in enumerate('A'*4+'B'*16+'C'*2)]
        x=dict(plan=dict(sessions=e),calibration_sessions=['0','1','2','3'],previously_seen=['4'])
        with self.assertRaisesRegex(ValueError,'leakage'):f.validate_partition(x)

    def test_schema_is_valid(self):
        import jsonschema
        jsonschema.Draft202012Validator.check_schema(f.read(Path('tools/schemas/service-final-freeze-v1.schema.json')))

if __name__=='__main__':unittest.main()
