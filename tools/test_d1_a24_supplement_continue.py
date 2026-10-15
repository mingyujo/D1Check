import copy
from pathlib import Path
import unittest
from d1_a24_supplement_continue import pending_scope
from d1_a24_laptop_validator import load_json


class UnusedScope(unittest.TestCase):
    def test_only_exact_unstarted_eight(self):
        p=load_json(Path(__file__).resolve().parents[1]/'docs/team/a24-measurement-revision02-20261015/failed_supplement12_20261016/plan.json')
        rows=p['sessions'];actual={r['session_id']:{'status':'COMPLETE_TRACE_RECOVERED' if i<3 else 'FAILED_PRESERVED'} for i,r in enumerate(rows[:4])}
        self.assertEqual([r['session_id'] for r in pending_scope(p,actual)],[r['session_id'] for r in rows[4:]])
        for extra in [rows[4]['session_id'],'unknown']:
            bad=copy.deepcopy(actual);bad[extra]={'status':'FAILED_PRESERVED'}
            with self.assertRaises(ValueError):pending_scope(p,bad)
        bad=copy.deepcopy(actual);bad[rows[0]['session_id']]['status']='FAILED_PRESERVED'
        with self.assertRaises(ValueError):pending_scope(p,bad)


if __name__=='__main__':unittest.main()
