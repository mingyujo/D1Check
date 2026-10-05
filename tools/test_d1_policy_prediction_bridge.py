import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import d1_policy_prediction_bridge as bridge
from tools import d1_simulator as sim


class PolicyBridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec=sim.read(bridge.CONTRACT)
        cls.preload,cls.model=bridge.initial_inputs(cls.spec['initialization_case_id'])
        cls.config=sim.read(sim.BUNDLE/'estimates.json')
        cls.vectors=sim.read(sim.BUNDLE/'realizations.json')
        cls.settings=sim.read(sim.FREEZE)['B2']['explore']['settings']
        cls.requests=sim.batch.workload('queue','evaluation')
        for r in cls.requests:r['arrival_ns']+=35_000_000_000

    def calculate(self, **changes):
        options=dict(policy='B2_PC',hold_s=0,preload=self.preload,model=self.model,
            power_w=self.spec['whole_device_power_w'],config=self.config,vectors=self.vectors,
            settings=self.settings,seed=201)
        options.update(changes)
        return bridge.predict(copy.deepcopy(self.requests),**options)

    def test_wait_keeps_arrivals_and_deadlines_and_has_no_extra_calls(self):
        base=self.calculate();wait=self.calculate(hold_s=.2)
        for result in (base,wait):
            self.assertEqual(result['service']['planned'],24)
            self.assertEqual(result['service']['unfinished'],0)
            self.assertEqual([(r['id'],r['arrival_ns'],r['deadline_offset_ns']) for r in result['ledger']],
                [(r['id'],r['arrival_ns'],r['deadline_offset_ns']) for r in self.requests])
        self.assertGreaterEqual(min(r['dispatch_ns'] for r in wait['ledger']),35_200_000_000)
        # A resource-specific hold need not worsen urgent GPU P95; verify the
        # actual held CPU request rather than presupposing a policy outcome.
        first=lambda result:next(r for r in result['ledger'] if r['ordinal']==0)
        delay=(first(wait)['dispatch_ns']-first(base)['dispatch_ns'])/1e9
        self.assertGreaterEqual(delay,.2)
        # The urgent arrival at the release instant may be dispatched first,
        # costing one existing decision/record/dispatch overhead (300us).
        overhead=sum(self.settings[k] for k in ('decision_ns','record_ns','dispatch_ns'))/1e9
        self.assertLessEqual(delay,.2+overhead+1e-9)
        self.assertGreater(first(wait)['persist_complete_ns'],first(base)['persist_complete_ns'])

    def test_whole_device_accounting_and_separate_prospective_window(self):
        d=self.calculate()['diagnostic']
        self.assertAlmostEqual(sum(d['state_seconds'].values()),120)
        expected=sum(self.spec['whole_device_power_w'][bridge.state_key(k)]*s for k,s in d['state_seconds'].items())
        self.assertAlmostEqual(d['whole_120s_j'],expected)
        self.assertAlmostEqual(d['whole_120s_j']-d['prospective_35_120s_j'],35*self.spec['whole_device_power_w']['resident_idle'])
        self.assertAlmostEqual(d['energy_path'][-1]['predicted_j'],expected)
        self.assertEqual((d['ap_path'][0]['common_s'],d['ap_path'][-1]['common_s']),(35,180))

    def test_future_ap_and_actual_schedule_never_enter_predictor(self):
        original=sim.read
        def altered(path):
            value=original(path)
            if Path(path).name=='ap_cases.json':
                for c in value:
                    c['observed_ap_c']=[999.]*len(c['observed_ap_c'])
                    c['inputs']['segments']=[dict(start_s=0,end_s=180,state='garbage')]
            return value
        with patch.object(sim,'read',side_effect=altered):
            preload,model=bridge.initial_inputs(self.spec['initialization_case_id'])
        self.assertEqual(preload,self.preload);self.assertEqual(model,self.model)
        a=self.calculate();b=self.calculate(preload=preload,model=model)
        self.assertEqual(a['diagnostic']['ap_path'],b['diagnostic']['ap_path'])
        bad=copy.deepcopy(preload);bad[-1]['hi']=35
        with self.assertRaisesRegex(ValueError,'future AP'):self.calculate(preload=bad)

    def test_outputs_have_independent_missing_state_handling(self):
        power=copy.deepcopy(self.spec['whole_device_power_w']);del power['detection_CPU']
        d=self.calculate(power_w=power)['diagnostic']
        self.assertIsNone(d['whole_120s_j']);self.assertIsNone(d['energy_path']);self.assertIsNotNone(d['ap_path'])
        model=copy.deepcopy(self.model);del model['parameters']['ap_slope_at_30_c_per_s']['detection_CPU']
        d=self.calculate(model=model)['diagnostic']
        self.assertIsNone(d['ap_path']);self.assertIsNotNone(d['whole_120s_j'])

    def test_unfinished_work_blocks_full_window_cost_and_invalid_hold(self):
        vectors=copy.deepcopy(self.vectors)
        for cell in vectors['cells'].values():
            for row in cell:row['durations_ns']=[v*1000 for v in row['durations_ns']]
        r=self.calculate(vectors=vectors)
        self.assertGreater(r['service']['unfinished'],0);self.assertIsNone(r['diagnostic'])
        with self.assertRaises(ValueError):self.calculate(hold_s=3)

    def test_real_entry_four_cases_no_device_and_no_validation_promotion(self):
        with patch('subprocess.Popen',side_effect=AssertionError('No device or child command')):
            result=bridge.run()
        self.assertEqual(len(result['cases']),4)
        self.assertFalse(result['original_research_goal_complete'])
        self.assertFalse(result['independent_end_to_end_validation'])
        for c in result['cases']:
            self.assertFalse(c['strict_support']);self.assertIsNone(c['policy_rank'])
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp)/'fresh';bridge.export(result,out)
            self.assertTrue((out/'summary.csv').exists())
            self.assertEqual(json.loads((out/'result.json').read_text(encoding='utf8'))['device_commands'],0)
            with self.assertRaises(FileExistsError):bridge.export(result,out)


if __name__=='__main__':unittest.main()
