import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools import d1_resident_history_analysis as h


class HistoryReadoutTests(unittest.TestCase):
    def setUp(self):
        self.case=dict(states=[dict(start_s=0.,end_s=120.,state='idle')],
            samples=[dict(relative_ns=i*10**9,read_start_ns=i*10**9-10**7,read_end_ns=i*10**9+10**7,
                current_raw=-250,current_valid=True,voltage_mV=4000,plugged=0,active_count=0,
                resident_keys=['classification_CPU','classification_GPU','detection_CPU','detection_GPU'],
                phase='common_window') for i in range(-1,181)],
            ap_samples=[dict(relative_ns=i*10**9,ap_c=28+i/100) for i in range(-2,182,2)])

    def test_fixed_boundaries_energy_and_ap_continuity(self):
        value=h.window(self.case,5,30)
        self.assertEqual(value['observed_j'],25)
        self.assertEqual(value['mean_w'],1)
        self.assertAlmostEqual(value['ap_change_c'],.25)
        pieces=[h.window(self.case,t,t+10)['observed_j'] for t in range(0,120,10)]
        self.assertAlmostEqual(sum(pieces),h.window(self.case,0,120,False)['observed_j'])

    def test_gap_and_missing_tail_are_null_without_window_shift(self):
        self.case['samples']=[s for s in self.case['samples'] if s['relative_ns']<179*10**9]
        value=h.window(self.case,150,180)
        self.assertIsNone(value['observed_j'])
        self.assertEqual(value['end_s'],180)
        self.assertGreater(value['missing_s'],0)
        self.case['ap_samples']=[s for s in self.case['ap_samples'] if s['relative_ns']<178*10**9]
        self.assertIsNone(h.window(self.case,150,180)['ap_mean_c'])

    def test_short_active_interval_between_samples_is_not_idle(self):
        self.case['states']=[dict(start_s=0,end_s=5.2,state='idle'),
            dict(start_s=5.2,end_s=5.3,state='detection:CPU'),dict(start_s=5.3,end_s=120,state='idle')]
        self.assertIsNone(h.window(self.case,5,30)['mean_w'])
        self.assertEqual(h.window(self.case,0,120,False)['observed_j'],120)

    def test_active_bracket_outside_fixed_idle_start_is_not_imported(self):
        self.case['states']=[dict(start_s=0,end_s=4.9,state='detection:CPU'),
            dict(start_s=4.9,end_s=120,state='idle')]
        self.case['samples'][5]['active_count']=1  # t=4; bracket would interpolate at t=4.95
        self.assertIsNone(h.window(self.case,4.95,30)['mean_w'])

    def test_bad_state_map_charging_and_resident_mismatch(self):
        original=copy.deepcopy(self.case)
        self.case['states'][0]['start_s']=1
        with self.assertRaisesRegex(ValueError,'gap'):h.window(self.case,5,30)
        self.case=copy.deepcopy(original)
        for s in self.case['samples']:s['plugged']=1
        self.assertIsNone(h.window(self.case,5,30)['observed_j'])
        self.case=copy.deepcopy(original)
        self.case['samples'][10]['resident_keys']=[]
        self.assertIsNone(h.window(self.case,5,30)['mean_w'])

    def test_recorded_cli_and_prior_metrics_missing_preserved(self):
        root=Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp)/'readout'
            cmd=[sys.executable,'-X','utf8','-B','-m','tools.d1_resident_history_analysis','analyze',
                '--bundle',str(h.PUBLIC/'inputs.json'),'--contract',str(h.PUBLIC/'contract.json'),'--output',str(out)]
            run=subprocess.run(cmd,cwd=root,capture_output=True,text=True,timeout=45)
            self.assertEqual(run.returncode,0,run.stderr)
            result=json.loads((out/'summary.json').read_text())
            self.assertEqual((result['existing_candidate_improved'],result['existing_candidate_worsened']),(2,3))
            self.assertAlmostEqual(result['pair_difference_of_changes_w'],-.202360713472311)
            self.assertIsNone(result['cases'][0]['pre_to_late_w'])
            self.assertEqual(result['device_commands'],0)
            self.assertIsNone(result['simulation_scope']['dynamic_energy_policy_rank'])
            self.assertFalse(result['history_coefficients_identified'])
            before=(out/'summary.json').read_bytes()
            blocked=subprocess.run(cmd,cwd=root,capture_output=True,text=True,timeout=15)
            self.assertNotEqual(blocked.returncode,0)
            self.assertIn('preserve prior analysis',blocked.stderr)
            self.assertEqual(before,(out/'summary.json').read_bytes())


if __name__=='__main__':unittest.main()
