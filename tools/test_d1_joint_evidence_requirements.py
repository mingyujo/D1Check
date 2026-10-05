import copy
import csv
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from tools import d1_joint_evidence_requirements as evidence


class JointEvidenceRequirementsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.summary=json.loads((evidence.P.BUNDLE/'summary.json').read_text(encoding='utf8'))

    def test_same_four_pairs_two_layers_and_exact_difference(self):
        rows=evidence.historical_pairs(self.summary['metrics'])
        self.assertEqual(len(rows),8)
        self.assertEqual({r['pair'] for r in rows},set(range(4)))
        for row in rows:
            self.assertAlmostEqual(row['paired_signed_prediction_error_j'],row['predicted_par_minus_cpu_j']-row['observed_par_minus_cpu_j'])
            self.assertEqual(row['independent_pairs'],4)
            self.assertIsNone(row['universal_energy_error_bound_j'])
            self.assertIsNone(row['universal_coefficient_error_bound_w'])
            self.assertFalse(row['background_subtracted_from_observation'])
            self.assertIn('not uniform 35..180 grid', row['AP_peak_boundary'])
            self.assertGreater(row['cpu_ap_observed_end_s'], row['cpu_ap_observed_start_s'])

    def test_missing_duplicate_nonfinite_and_changed_energy_identity_blocked(self):
        base=self.summary['metrics']
        duplicate=copy.deepcopy(base);duplicate[-1]=copy.deepcopy(duplicate[0])
        nonfinite=copy.deepcopy(base);nonfinite[0]['observed_120s_j']=float('nan')
        wrong=copy.deepcopy(base);wrong[0]['energy_signed_error_j']+=1.
        missing_pair=copy.deepcopy(base);missing_pair[0]['pair']=3
        for rows in (base[:-1],duplicate,nonfinite,wrong,missing_pair):
            with self.assertRaises(ValueError):evidence.historical_pairs(rows)

    def test_readonly_resources_and_no_universal_bound_or_fake_budget(self):
        engine=evidence.sensitivity.source.study.followup.x.old.engine
        before=evidence.P.digest(evidence.P.BUNDLE/'model.json')
        with patch.object(engine,'simulate',side_effect=AssertionError('must not simulate')):
            result=evidence.analyze()
        self.assertEqual(len(result['requirements']),8)
        self.assertEqual(sum(r['device_certification']=='not_computable' for r in result['requirements']),2)
        self.assertEqual(sum(r['device_certification']=='not_established' for r in result['requirements']),6)
        self.assertFalse(result['goal_achieved'])
        self.assertFalse(result['new_device_plan'])
        self.assertTrue(result['paired_errors_are_not_universal_bound'])
        self.assertIn('includes actual controller cost', result['routes']['direct_pair'])
        self.assertIn('never certify', result['routes']['online_policy'])
        self.assertEqual(before,evidence.P.digest(evidence.P.BUNDLE/'model.json'))
        self.assertEqual(before,evidence.P.MODEL_SHA)
        for row in result['requirements']:
            self.assertIsNone(row['coefficient_error_bound_observed_w'])
            self.assertIsNone(row['differential_controller_energy_observed_j'])

    def test_actual_cli_fake_adb_csv_and_overwrite_block(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp);marker=root/'ADB_CALLED'
            (root/'adb.cmd').write_text('@echo off\necho called>"'+str(marker)+'"\nexit /b 99\n',encoding='ascii')
            env=dict(os.environ,PATH=str(root)+os.pathsep+os.environ.get('PATH',''),PYTHONIOENCODING='utf8')
            out=root/'result';command=[sys.executable,'-B','-m','tools.d1_joint_evidence_requirements','--output',str(out)]
            run=subprocess.run(command,cwd=evidence.P.ROOT,env=env,capture_output=True,text=True,encoding='utf8',timeout=40)
            self.assertEqual(run.returncode,0,run.stderr)
            self.assertFalse(marker.exists())
            result=json.loads((out/'result.json').read_text(encoding='utf8'))
            with (out/'historical_pairs.csv').open(encoding='utf8',newline='') as file:rows=list(csv.DictReader(file))
            self.assertEqual(len(rows),8)
            for actual,expected in zip(rows,result['historical_pairs']):
                self.assertAlmostEqual(float(actual['paired_signed_prediction_error_j']),expected['paired_signed_prediction_error_j'])
            original=(out/'result.json').read_bytes()
            repeated=subprocess.run(command,cwd=evidence.P.ROOT,env=env,capture_output=True,text=True,encoding='utf8',timeout=40)
            self.assertNotEqual(repeated.returncode,0)
            self.assertIn('FileExistsError',repeated.stderr)
            self.assertEqual(original,(out/'result.json').read_bytes())
            self.assertFalse(marker.exists())


if __name__=='__main__':unittest.main()
