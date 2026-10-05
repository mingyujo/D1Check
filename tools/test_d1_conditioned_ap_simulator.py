"""Registered conditional AP is reproducible but never an arbitrary policy cost."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from tools import d1_simulator as sim


class ConditionedAPTests(unittest.TestCase):
    CASE='v2_confirmation_0_C'

    def test_registered_prediction_matches_preserved_reference(self):
        with patch('subprocess.Popen',side_effect=AssertionError('AP prediction must not run device or process')):
            result=sim.conditioned_ap(self.CASE)
        self.assertAlmostEqual(result['scores']['mae_c'],0.06166108783892558,places=10)
        self.assertAlmostEqual(result['scores']['max_absolute_error_c'],0.17304342973431375,places=10)
        self.assertFalse(result['post35_observations_used_as_inputs'])
        self.assertFalse(result['strict_support']);self.assertFalse(result['experiment_ready'])
        self.assertIsNone(result['energy_j']);self.assertIsNone(result['energy_ap_policy_rank'])

    def test_targets_do_not_change_predictions_and_future_initialization_rejected(self):
        original=sim.conditioned_ap(self.CASE);spec=sim.read(sim.AP_REGISTER)
        casefile=sim.ROOT/spec['cases_file'];cases=sim.read(casefile);actual_read=sim.read
        altered=copy.deepcopy(cases)
        for c in altered:c['observed_ap_c']=[v+3 for v in c['observed_ap_c']]
        def replacement(path):return altered if Path(path)==casefile else actual_read(path)
        with patch.object(sim,'read',side_effect=replacement):changed=sim.conditioned_ap(self.CASE)
        self.assertEqual([v['predicted_c'] for v in original['paths']],[v['predicted_c'] for v in changed['paths']])
        selected=next(c for c in altered if c['id']==self.CASE)
        selected['inputs']['preload'][-1]['hi']=35
        with patch.object(sim,'read',side_effect=replacement),self.assertRaisesRegex(ValueError,'future AP'):
            sim.conditioned_ap(self.CASE)

    def test_unknown_schedule_and_resource_drift_fail_closed(self):
        with self.assertRaisesRegex(ValueError,'unregistered'):sim.conditioned_ap('arbitrary_policy')
        spec=sim.read(sim.AP_REGISTER);spec['files'][spec['model_file']]='0'*64
        with tempfile.TemporaryDirectory() as tmp:
            f=Path(tmp)/'register.json';f.write_text(json.dumps(spec),encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'resource mismatch'):sim.conditioned_ap(self.CASE,f)
            spec=sim.read(sim.AP_REGISTER);spec['files'].pop(spec['model_file'])
            f.write_text(json.dumps(spec),encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'unbound'):sim.conditioned_ap(self.CASE,f)

    def test_real_cli_exports_without_device_and_refuses_new_initial_condition(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);cmd=[sys.executable,'-B','-m','tools.d1_simulator','ap-conditioned','--case-id',self.CASE,'--output',str(root/'valid')]
            result=subprocess.run(cmd,cwd=sim.ROOT,capture_output=True,text=True,timeout=30)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(len(sim.rows(root/'valid/ap_paths.csv')),55)
            self.assertIn('정확도 PASS·strict 승격 없음',(root/'valid/index.html').read_text(encoding='utf-8'))
            invalid=cmd[:-1]+[str(root/'invalid'),'--initial-ap-c','31']
            rejected=subprocess.run(invalid,cwd=sim.ROOT,capture_output=True,text=True,timeout=30)
            self.assertNotEqual(rejected.returncode,0)
            self.assertFalse((root/'invalid').exists())
            self.assertAlmostEqual(sim.read(root/'valid/result.json')['scores']['mae_c'],0.06166108783892558)


if __name__=='__main__':unittest.main()
