import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tools import d1_policy_feasibility as f

SOURCE=f.ROOT/'docs/results/online_policy_study_01/policy_resolution_pc_v1'


class Feasibility(unittest.TestCase):
    def test_known_sigma_formula_and_inverse(self):
        a=f.design_sensitivity(1.,1.,8)
        self.assertEqual(a['illustrative_pair_count'],8)
        self.assertIsNone(a['recommended_pairs'])
        self.assertIsNone(a['validated_power'])
        self.assertEqual(a['sessions'],16)
        self.assertEqual(a['fixed_observation_minutes'],56)
        b=f.design_sensitivity(a['approximate_detectable_j'],1.,8)
        self.assertAlmostEqual(b['required_sigma_j'],1.)
        double=f.design_sensitivity(1.,2.,8)
        self.assertAlmostEqual(double['approximate_detectable_j'],a['approximate_detectable_j']*2)

    def test_bias_is_not_averaged_away(self):
        for n in (8,100000):
            a=f.design_sensitivity(1.,1.,n,bias_bound=1.)
            self.assertIsNone(a['illustrative_pair_count'])
            self.assertIsNone(a['required_sigma_j'])
            self.assertGreater(a['approximate_detectable_j'],1.)
        a=f.design_sensitivity(1.,1.,8,bias_bound=.5)
        b=f.design_sensitivity(1.,1.,8)
        self.assertAlmostEqual(a['required_sigma_j'],b['required_sigma_j']/2)

    def test_invalid_or_missing_is_not_zero(self):
        for args in [(0.,1.,8),(1.,0.,8),(1.,None,8),(1.,math.nan,8),(1.,1.,True),(1.,1.,1),(1.,1.,2.5)]:
            with self.assertRaises(ValueError):f.design_sensitivity(*args)

    def test_real_cli_retains_both_blocks_and_no_measurement_plan(self):
        before=f.prior.digest(SOURCE/'evaluation/evaluation.json')
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'result'
            run=subprocess.run([sys.executable,'-m','tools.d1_policy_feasibility','--source',str(SOURCE),'--output',str(out)],
                cwd=f.ROOT,capture_output=True,encoding='utf-8',timeout=60,env=dict(os.environ,PYTHONIOENCODING='utf-8'))
            self.assertEqual(run.returncode,0,run.stderr)
            r=f.prior.read(out/'evaluation.json')
            self.assertEqual(r['contrast_count'],2)
            self.assertAlmostEqual(r['descriptive_sd_j'],31.53400160719666)
            self.assertEqual(r['scenarios'][0]['illustrative_pair_count'],2661)
            self.assertIsNone(r['actual_required_pairs'])
            self.assertIsNone(r['ap_sample_size'])
            self.assertFalse(r['run_ready'])
            self.assertEqual(r['device_commands'],0)
            self.assertEqual(r['new_forecasts'],0)
            self.assertGreater((out/'feasibility.png').stat().st_size,10000)
            self.assertFalse(list(out.rglob('*plan*')))
            with self.assertRaises(FileExistsError):f.analyze(SOURCE,out)
        self.assertEqual(f.prior.digest(SOURCE/'evaluation/evaluation.json'),before)


if __name__=='__main__':unittest.main()
