import copy
import csv
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

from tools import d1_policy_resolution as m

ROOT = pathlib.Path(__file__).resolve().parents[1]
BUNDLE = ROOT/'docs/results/online_policy_study_01/separated_power_final'
CONTRACT = ROOT/'docs/results/online_policy_study_01/policy_resolution_pc_v1/analysis_contract.json'


class Resolution(unittest.TestCase):
    def test_historical_arithmetic_not_future_bound(self):
        r = m.historical_sensitivity(-2, [1, -3], [0, -10])
        self.assertEqual((r['historical_low'],r['historical_high']),(-13,1))
        self.assertFalse(r['sign_retained'])
        self.assertIsNone(r['future_bound'])
        self.assertIsNone(r['policy_winner'])
        reverse = m.historical_sensitivity(2,[0,-10],[1,-3])
        self.assertEqual(reverse['historical_low'],-r['historical_high'])
        self.assertEqual(reverse['historical_high'],-r['historical_low'])
        for a,b in [([], [1]),([None],[1]),([float('nan')],[1])]:
            with self.assertRaises(ValueError):m.historical_sensitivity(1,a,b)

    def test_no_future_inputs_and_no_policy_promotion(self):
        _, frozen, inputs, _ = m.load(BUNDLE)
        original = inputs[m.IDS[0]]
        changed = copy.deepcopy(original)
        changed['initial']['future_ap'] = [999]
        changed['initial']['actual_future_power'] = [-999]
        changed['actual_rows'] = [{'invalid': True}]
        self.assertEqual(m.counterfactual(original,frozen),m.counterfactual(changed,frozen))
        with self.assertRaisesRegex(ValueError,'policy selection unavailable'):
            m.replay.decision_support('energy-ap-policy-selection')

    def test_identity_and_no_missing_session(self):
        with tempfile.TemporaryDirectory() as d:
            bundle = pathlib.Path(d)/'bundle';shutil.copytree(BUNDLE,bundle)
            path = bundle/'evaluation.json'
            data = m.read(path);data = [r for r in data if r['id'] != m.IDS[-1]]
            m.write(path,data)
            with self.assertRaisesRegex(ValueError,'hash mismatch'):m.load(bundle)
            resources = m.read(bundle/'resources.json')
            resources['files']['evaluation.json'] = m.digest(path)
            m.write(bundle/'resources.json',resources)
            with self.assertRaisesRegex(ValueError,'all six'):m.load(bundle)

    def test_cli_and_shared_results(self):
        before = {p.name:m.digest(p) for p in BUNDLE.glob('*.json')}
        with tempfile.TemporaryDirectory() as d:
            out = pathlib.Path(d)/'result'
            command = [sys.executable,'-m','tools.d1_policy_resolution','--bundle',str(BUNDLE),
                       '--contract',str(CONTRACT),'--output',str(out)]
            options = dict(cwd=ROOT,capture_output=True,text=True,encoding='utf-8',timeout=60,
                           env=dict(os.environ,PYTHONIOENCODING='utf-8'))
            run = subprocess.run(command,**options)
            self.assertEqual(run.returncode,0,run.stderr)
            r = m.read(out/'evaluation.json')
            self.assertEqual([x['id'] for x in r['sessions']],m.IDS)
            self.assertEqual(len(r['counterfactual_predictions']),18)
            self.assertEqual(r['device_commands'],0)
            self.assertFalse(r['experiment_ready'])
            self.assertTrue(all(x['historical_low']<0<x['historical_high'] for x in r['same_initial_comparisons']))
            for name,key in [('sessions','sessions'),('same_initial_comparisons','same_initial_comparisons')]:
                with (out/(name+'.csv')).open(encoding='utf-8',newline='') as f:
                    csv_rows=list(csv.DictReader(f))
                self.assertEqual(len(csv_rows),len(r[key]))
                field='energy_error_j' if name=='sessions' else 'predicted_energy_delta_j'
                for row,expected in zip(csv_rows,r[key]):self.assertEqual(float(row[field]),expected[field])
            html=(out/'index.html').read_text(encoding='utf-8')
            for x in r['sessions']:self.assertIn(f'{x["energy_error_j"]:+.3f}',html)
            self.assertGreater((out/'comparison.png').stat().st_size,10000)
            for pair in r['observed_contrasts']:
                self.assertAlmostEqual(pair['predicted_energy_delta_j']-pair['observed_energy_delta_j'],pair['contrast_error_j'])
            # The command refuses overwriting a previous analysis result.
            rerun=subprocess.run(command,**options)
            self.assertNotEqual(rerun.returncode,0)
            self.assertIn('FileExistsError',rerun.stderr)
        self.assertEqual(before,{p.name:m.digest(p) for p in BUNDLE.glob('*.json')})


if __name__ == '__main__':unittest.main()
