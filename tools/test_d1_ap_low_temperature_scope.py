"""Source-backed PC boundary checks; no device execution or new accuracy PASS."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import d1_ap_low_temperature_scope as scope
from tools import d1_arrival_energy_research as research
from tools.test_d1_arrival_energy_research import request, result


class LowTemperatureScopeTest(unittest.TestCase):
    def setUp(self):
        self.data=scope.read(scope.BUNDLE/'inputs.json')
        self.contract=scope.read(scope.BUNDLE/'contract.json')
        self.inputs=copy.deepcopy(self.data['cases'][1]['prediction_inputs'])

    def calculate(self, **kwargs):
        return scope.conditional_path(self.inputs,self.data['parameters'],self.contract,**kwargs)

    def test_archived_reference_and_scores_reproduced_without_raw_files(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch('subprocess.Popen',side_effect=AssertionError('no device or child commands')):
                report=scope.evaluate(scope.BUNDLE,Path(temp)/'new')
            self.assertAlmostEqual(report['results'][1]['mae_c'],0.4175211229048267,places=9)
            self.assertAlmostEqual(report['results'][0]['mae_c'],0.4875183853439651,places=9)
            self.assertEqual(report['results'][1]['original_data_role'],'independent_confirmation')
            self.assertFalse(report['strict_support'])
            self.assertIn('ap_peak_c,UNSUPPORTED', (Path(temp)/'new/output_scope.csv').read_text())
            with self.assertRaises(FileExistsError):
                scope.evaluate(scope.BUNDLE,Path(temp)/'new')

    def test_future_observations_are_targets_only(self):
        original=self.calculate()
        self.inputs['observed_postload_ap_c']=[99.]*54
        again=self.calculate()
        self.assertEqual(original['ap_path'],again['ap_path'])
        self.assertFalse(again['post_load_ap_used_as_input'])
        self.assertGreater(again['prediction_information_cutoff_s'],35.)
        self.inputs['query_s'].insert(0,0.)
        self.assertIn('precede',self.calculate()['reason'])

    def test_peak_threshold_energy_and_policy_outputs_stay_null(self):
        for output in ('ap_peak_c','threshold_exceedance_s','whole_device_energy_j','policy_rank'):
            with self.subTest(output=output):
                out=self.calculate(output=output)
                self.assertIsNone(out['ap_path'])
                self.assertIsNone(out[output])
        self.assertIsNone(self.calculate(mode='strict')['ap_path'])
        self.inputs['schedule_source']='planned_PC_dispatch'
        self.assertIsNone(self.calculate()['ap_path'])

    def test_short_preload_and_query_bracket_leak_blocked(self):
        self.inputs['preload_ap']=[p for p in self.inputs['preload_ap'] if p['t']>=0]
        self.assertIn('insufficient pre-load',self.calculate()['reason'])
        self.setUp()
        first=self.inputs['preload_ap'][0]['t']
        for i,p in enumerate(self.inputs['preload_ap']):
            p.update(t=first+i,lo=first+i-.1,hi=first+i+.1)
        self.assertIn('too short',self.calculate()['reason'])
        self.setUp()
        self.inputs['preload_ap'][-1]['hi']=self.inputs['prediction_information_cutoff_s']
        self.assertIn('bracket',self.calculate()['reason'])

    def test_context_state_and_denominator_cannot_silently_transfer(self):
        self.inputs['context']['apk_sha256']='new-apk'
        self.assertIn('APK',self.calculate()['reason'])
        self.setUp();self.inputs['segments'][1]['state']='detection:CPU+detection:GPU'
        self.assertIn('unsupported',self.calculate()['reason'])
        self.setUp();self.inputs['completed']=23
        self.assertIsNone(self.calculate()['ap_path'])
        self.setUp();self.inputs['common_window_s']=0
        self.assertIsNone(self.calculate()['ap_path'])

    def test_stratum_is_not_redefined_as_empirical_support_or_safety(self):
        self.inputs['initial_ap_c']=30.
        out=self.calculate()
        self.assertEqual(out['status'],'CONDITIONAL_DIAGNOSTIC_ONLY')
        self.assertFalse(out['strict_support'])
        for value in (32.5,34.,float('nan')):
            self.inputs['initial_ap_c']=value
            self.assertIsNone(self.calculate()['ap_path'])

    def test_frozen_coefficients_and_gaps_rejected(self):
        self.data['parameters']['ap_cooling_rate_per_s']*=1.01
        self.assertIn('parameters',self.calculate()['reason'])
        self.setUp();self.inputs['segments'][1]['start_s']+=.01
        self.assertIsNone(self.calculate()['ap_path'])
        self.setUp();self.inputs['preload_ap'][2]['ap']=float('nan')
        self.assertIsNone(self.calculate()['ap_path'])

    def test_actual_arrival_aggregate_rejects_candidate_as_policy_cost(self):
        row=dict(request(),status='succeeded',backend='CPU',dispatch_ns=0,
            execution_start_ns=0,output_ready_ns=10,persist_complete_ns=11,
            worker_release_ns=12,lane_available_ns=13)
        out=research.aggregate([request()],result([row]),horizon_ns=100,
                               profile=self.contract,initial_ap_c=28.7)
        self.assertEqual(out['service']['succeeded'],1)
        self.assertEqual(out['energy_ap']['status'],'UNSUPPORTED_PRELOAD_AP_CANDIDATE_FOR_POLICY_COST')
        self.assertIsNone(out['energy_ap']['whole_device_energy_j'])
        self.assertIsNone(out['energy_ap']['ap_peak_c'])

    def test_dashboard_scope_and_saved_numbers_share_the_same_readout(self):
        from tools import d1_ap_simulation_closure as closure
        with tempfile.TemporaryDirectory() as temp:
            report=scope.evaluate(scope.BUNDLE,Path(temp)/'scope')
            with (closure.DEFAULT/'readout/energy_accounting.csv').open(encoding='utf-8',newline='') as f:
                import csv
                energy=list(csv.DictReader(f))
            for row in energy:
                for key in ('observed_j','predicted_j','signed_error_j','relative_error_pct'):
                    row[key]=float(row[key])
            closure.page(scope.read(closure.DEFAULT/'readout/summary.json'),energy,Path(temp))
            page=(Path(temp)/'index.html').read_text(encoding='utf-8')
            self.assertIn('AP 최고·한도 초과 시간',page)
            self.assertIn('계산 불가(null)',page)
            self.assertIn('0.418',page)
            self.assertEqual(f"{report['results'][1]['mae_c']:.3f}",'0.418')


if __name__=='__main__':
    unittest.main()
