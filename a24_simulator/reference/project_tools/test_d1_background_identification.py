import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from tools import d1_background_identification as d


BUNDLE=d.CONTRACT.parent/'bundle'


class IdentificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases=d.c.read(BUNDLE/'inputs.json')
        cls.model=d.c.read(BUNDLE/'model.json')
        cls.cfg=d.c.read(d.CONTRACT)

    def test_real_bundle_app_windows_legacy_and_corrected_energy(self):
        for case in self.cases:
            self.assertEqual(len(case['app_input_audit']),14)
            self.assertTrue(all(abs(r['difference_w'])<1e-8 for r in case['app_input_audit']))
            delta=120*(case['preload_w']-case['legacy_preload_w'])
            self.assertAlmostEqual(case['corrected_predicted_j']-case['legacy_predicted_j'],delta)
            self.assertEqual(case['preload_window_s'],[-20,30])
        self.assertEqual(d.c.digest(BUNDLE/'model.json'),self.cfg['model_sha256'])

    def test_future_power_ap_and_actual_schedule_cannot_change_issued_prediction(self):
        case=copy.deepcopy(self.cases[2]);issue=55
        baseline=d.c.issued_forecast(case,self.model,.1,self.cfg,issue,30)
        case['observed_ap']=[999]*len(case['observed_ap'])
        case['trace_bins']=[]
        for s in case['power']:
            if s['ready_s']>issue:s['w']=999
        past=[]
        for s in case['actual_segments']:
            if s['start_s']<issue:past.append(dict(s,end_s=min(s['end_s'],issue)))
        past.append(dict(start_s=issue,end_s=180,state='idle'))
        case['actual_segments']=past
        self.assertEqual(baseline,d.c.issued_forecast(case,self.model,.1,self.cfg,issue,30))

    def test_no_development_role_leakage_or_missing_window_selection(self):
        cases=copy.deepcopy(self.cases);cases[0]['role']='confirmation'
        with self.assertRaisesRegex(ValueError,'development-only'):d.c.fit(cases,self.model,self.cfg)
        case=copy.deepcopy(self.cases[0]);case['power']=[]
        with self.assertRaisesRegex(ValueError,'missing candidate inputs'):d.features(case,self.model,self.cfg)

    def test_zero_excitation_stays_null_and_negative_fit_does_not_flip_constraint(self):
        case=copy.deepcopy(self.cases[0])
        for s in case['power']:s['w']=case['preload_w']
        self.assertIsNone(d.c.fit([case],self.model,self.cfg)['gamma'])
        fit=d.c.fit(self.cases,self.model,self.cfg)
        self.assertLess(fit['unconstrained_gamma'],0);self.assertEqual(fit['gamma'],0)

    def test_cpu_data_is_descriptive_not_fit_input_and_rank_detects_duplicates(self):
        cases=copy.deepcopy(self.cases)
        for case in cases:case['trace_bins']=[]
        self.assertEqual(d.c.fit(cases,self.model,self.cfg),d.c.fit(self.cases,self.model,self.cfg))
        g=d.geometry([[1,1,0],[2,2,0]])
        self.assertEqual(g['rank'],1);self.assertEqual(g['zero_columns'],[2]);self.assertIsNone(g['condition_number'])

    def test_real_cli_reproduction_device_forbidden_and_consumed_output_guard(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'evaluation'
            # Actual PC entrypoint; fake PATH entries cannot locate adb or a shell helper.
            import os
            env=dict(os.environ,PATH='',PYTHONIOENCODING='utf-8')
            result=subprocess.run([sys.executable,'-m','tools.d1_background_identification','analyze',
                '--bundle',str(BUNDLE),'--output',str(out)],cwd=d.ROOT,env=env,capture_output=True,text=True,timeout=30)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(json.loads(result.stdout)['status'],'not_adopted')
            for name in ('summary.json','candidate.json','ap_paths.csv','activity_bins.csv','forecasts.json'):
                self.assertEqual((out/name).read_bytes(),(d.CONTRACT.parent/'evaluation'/name).read_bytes())
            with self.assertRaises(FileExistsError):d.analyze(BUNDLE,out)
            with patch.object(d.c,'fit',return_value=dict(gamma=None)):
                null=d.analyze(BUNDLE,Path(tmp)/'null')
                self.assertIsNone(null['gamma']);self.assertEqual(null['status'],'unidentified')

    def test_bundle_drift_is_rejected_before_fit(self):
        import shutil
        with tempfile.TemporaryDirectory() as tmp:
            bundle=Path(tmp)/'bundle';shutil.copytree(BUNDLE,bundle)
            with (bundle/'inputs.json').open('a') as f:f.write(' ')
            with patch.object(d.c,'fit',side_effect=AssertionError('fit must not start')):
                with self.assertRaisesRegex(ValueError,'bundle drift'):d.analyze(bundle,Path(tmp)/'out')

    def test_shared_curve_integrals_and_display_numbers_match(self):
        import csv
        folder=d.CONTRACT.parent
        with (folder/'evaluation/energy_paths.csv').open(encoding='utf8') as f:
            energies=list(csv.DictReader(f))
        summary=d.c.read(folder/'evaluation/summary.json')
        html=(folder/'index.html').read_text(encoding='utf8')
        for case,s in zip(self.cases,summary):
            rows=[r for r in energies if r['id']==case['id']]
            self.assertEqual(len(rows),120)
            self.assertAlmostEqual(float(rows[-1]['observed_j']),s['observed_120s_j'])
            self.assertAlmostEqual(float(rows[-1]['corrected_error_j']),s['corrected_error_j'])
            total=sum(d.c.integral(case['power'],t,t+5) for t in range(0,120,5))
            self.assertAlmostEqual(total,s['observed_120s_j'])
            self.assertIn(f"{s['corrected_error_j']:+.3f}",html)


if __name__=='__main__':unittest.main()
