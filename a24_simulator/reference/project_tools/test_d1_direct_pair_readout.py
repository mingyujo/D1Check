import copy
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import subprocess
import sys
import unittest
from unittest.mock import patch
from tools import d1_direct_pair_readout as readout


class DirectPairReadoutTests(unittest.TestCase):
    def session(self):
        return dict(input_signature='same-input',protocol_signature='same-protocol',planned=2,
            outcomes=dict(completed=2,failed=0,incomplete=0,unknown=0),deadline_met=2,
            energy_window_s=[0.,120.],energy_j=3.,ap_window_s=[35.,180.],ap_complete=True,
            peak_ap_c=32.,initial=dict(AP=29.))

    def test_semantic_input_excludes_only_session_specific_id(self):
        requests=[dict(ordinal=0,offset_ms=0,deadline_ms=1500,priority='urgent',task_id='classification',request_id='a')]
        other=copy.deepcopy(requests);other[0]['request_id']='b'
        self.assertEqual(readout.input_signature(requests),readout.input_signature(other))
        other[0]['offset_ms']=1
        self.assertNotEqual(readout.input_signature(requests),readout.input_signature(other))
        wrong=copy.deepcopy(requests);wrong[0]['ordinal']=1
        with self.assertRaises(ValueError):readout.input_signature(wrong)

    def test_whole_direct_cost_no_controller_double_count_no_winner(self):
        candidate=self.session();reference=self.session();candidate['energy_j']=2.;candidate['peak_ap_c']=31.
        result=readout.pair(candidate,reference)
        self.assertEqual(result['energy_point_delta_j'],-1.)
        self.assertEqual(result['AP_point_delta_c'],-1.)
        self.assertFalse(result['differential_controller_j_separately_added'])
        self.assertIsNone(result['policy_winner'])
        self.assertIsNone(result['inferential_pair_error_bound_j'])

    def test_missing_energy_does_not_remove_valid_AP_and_reverse(self):
        candidate=self.session();reference=self.session();candidate['energy_j']=None
        result=readout.pair(candidate,reference)
        self.assertIsNone(result['energy_point_delta_j'])
        self.assertEqual(result['AP_point_delta_c'],0.)
        candidate=self.session();candidate['ap_complete']=False
        result=readout.pair(candidate,reference)
        self.assertEqual(result['energy_point_delta_j'],0.)
        self.assertIsNone(result['AP_point_delta_c'])

    def test_mismatch_failed_unknown_and_partial_window_keep_denominator(self):
        reference=self.session()
        for field,value in [('input_signature','different'),('protocol_signature','different'),('energy_window_s',[0.,119.])]:
            candidate=self.session();candidate[field]=value
            result=readout.pair(candidate,reference);self.assertIsNone(result['energy_point_delta_j'])
        candidate=self.session();candidate['outcomes']=dict(completed=1,failed=0,incomplete=0,unknown=1);candidate['deadline_met']=1
        result=readout.pair(candidate,reference)
        self.assertEqual(result['candidate_planned'],2)
        self.assertEqual(result['candidate_outcomes']['unknown'],1)
        self.assertIsNone(result['energy_point_delta_j'])
        candidate['deadline_met']=2
        with self.assertRaises(ValueError):readout.pair(candidate,reference)
        candidate=self.session();candidate['ap_complete']='False'
        with self.assertRaises(ValueError):readout.pair(candidate,reference)

    def test_actual_cli_isolated_fake_adb_path(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp);marker=root/'ADB_CALLED'
            (root/'adb.cmd').write_text('@echo off\necho called>"'+str(marker)+'"\nexit /b 99\n',encoding='ascii')
            env=dict(os.environ,PATH=str(root)+os.pathsep+os.environ.get('PATH',''),PYTHONIOENCODING='utf8')
            run=subprocess.run([sys.executable,'-B','-m','tools.d1_direct_pair_readout','--output',str(root/'result')],cwd=readout.P.ROOT,env=env,capture_output=True,text=True,encoding='utf8',timeout=40)
            self.assertEqual(run.returncode,0,run.stderr)
            self.assertFalse(marker.exists())
            result=json.loads((root/'result/result.json').read_text(encoding='utf8'))
            self.assertIsNone(result['policy_winner'])
            self.assertEqual(result['device_commands'],0)

    def test_actual_historical_input_and1536_response_boundaries_readonly(self):
        engine=readout.evidence.sensitivity.source.study.followup.x.old.engine
        with patch.object(engine,'simulate',side_effect=AssertionError('must not simulate')):
            result=readout.analyze()
        self.assertEqual(len(result['rows']),4)
        self.assertEqual(len({r['input_signature'] for r in result['rows']}),1)
        self.assertTrue(all(r['energy_point_comparison_eligible'] for r in result['rows']))
        self.assertTrue(all(r['AP_point_delta_c'] is None for r in result['rows']))
        self.assertTrue(all(not r['initial_conditions_matched'] for r in result['rows']))
        self.assertEqual(readout.P.digest(readout.P.BUNDLE/'model.json'),readout.P.MODEL_SHA)
        with TemporaryDirectory() as tmp:
            out=Path(tmp)/'output';readout.save(result,out)
            self.assertEqual(json.loads((out/'result.json').read_text(encoding='utf8'))['independent_pairs'],4)
            with self.assertRaises(FileExistsError):readout.save(result,out)

    def test_changed_original_evidence_blocked_before_readout(self):
        digest=readout.P.digest
        def changed(path):
            return 'changed' if Path(path).name=='timing.csv' else digest(path)
        with patch.object(readout.P,'digest',side_effect=changed):
            with self.assertRaisesRegex(ValueError,'historical evidence hash mismatch'):readout.analyze()


if __name__=='__main__':unittest.main()
