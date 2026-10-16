import copy
import unittest
from unittest.mock import patch
import numpy as np
from tools import d1_power_residual_structure as d
from tools import d1_energy_memory30 as m


class StructureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.case=d.r.h.m.read(d.r.BUNDLE/'inputs.json.gz')[1];cls.frozen=d.r.h.m.read(d.r.h.m.MODEL)

    def test_recorded_runs_not_hardware_period(self):
        samples=[dict(t_s=i,current_raw=v) for i,v in enumerate([1,1,1,2,2,3])]
        runs=d.runs(samples,'current_raw')
        self.assertEqual([x['observed_span_s'] for x in runs],[2,1,0])
        self.assertEqual([x['samples'] for x in runs],[3,2,1])

    def test_past30_and_forecast_ignore_future_observations(self):
        first=d.past_residual(self.case,65,30,self.frozen);value=m.predict(self.case,self.frozen,65,.5)
        changed=copy.deepcopy(self.case)
        for row in changed['power_observations']:
            if row['available']>65:row['value']=9999
        self.assertEqual(first,d.past_residual(changed,65,30,self.frozen))
        self.assertEqual(value,m.predict(changed,self.frozen,65,.5))

    def test_five_and_ten_second_means_integrate_consistently(self):
        c=self.case;data=dict(power_t=[x['t'] for x in c['power_observations']],power_w=[x['value'] for x in c['power_observations']])
        direct=d.r.h.m.integral(data,35,45)
        split=d.r.h.m.integral(data,35,40)+d.r.h.m.integral(data,40,45)
        self.assertAlmostEqual(direct,split,places=10)
        p=d.past_residual(c,65,30,self.frozen)
        expected=(d.r.h.m.integral(data,p['start_s'],p['end_s'])-c['pre_w']*(p['end_s']-p['start_s'])-d.r.state_energy(c,self.frozen,p['start_s'],p['end_s']))/(p['end_s']-p['start_s'])
        self.assertAlmostEqual(p['residual_w'],expected,places=12)

    def test_unsupported_period_stale_and_gap_rejected(self):
        with self.assertRaises(ValueError):d.past_residual(self.case,65,20,self.frozen)
        bad=copy.deepcopy(self.case);bad['power_observations']=[x for x in bad['power_observations'] if x['t']<50]
        with self.assertRaises(ValueError):d.past_residual(bad,65,30,self.frozen)
        bad=copy.deepcopy(self.case);bad['power_observations']=[x for x in bad['power_observations'] if not 40<x['t']<50]
        with self.assertRaises(ValueError):d.past_residual(bad,65,30,self.frozen)

    def test_original_forecast_gain0_and_model_identity(self):
        snap=d.r.snapshot(self.case,65,self.frozen,d.r.h.m.read(d.r.BUNDLE/'contract.json'))
        self.assertEqual(m.predict(self.case,self.frozen,65,0),d.r.forecast_energy(self.case,self.frozen,snap,'FROZEN_OPEN_LOOP',75))
        self.assertEqual(d.r.h.m.sha(d.r.h.m.MODEL),d.r.h.m.MODEL_SHA)
        self.assertIsNone(d.correlation([1,1,1],[1,2,3]))

    def test_current_candidate_fit_excludes_evaluation_observations(self):
        original=m.source_rows();changed=copy.deepcopy(original)
        for row in changed:
            if row['role']!='development':row['observed_j']*=1000
        self.assertEqual(m.shrink.freeze(original),m.shrink.freeze(changed))

    def test_candidate_entry_rejects_duplicate_future_nonfinite_windows(self):
        rows=d.csv_rows(d.BUNDLE/'past_features.csv')
        bad=copy.deepcopy(rows);bad[1]=copy.deepcopy(bad[0])
        with patch.object(d,'csv_rows',return_value=bad),self.assertRaises(ValueError):m.source_rows()
        bad=copy.deepcopy(rows);bad[0]['past_available_s']='9999'
        with patch.object(d,'csv_rows',return_value=bad),self.assertRaises(ValueError):m.source_rows()
        bad=copy.deepcopy(rows);bad[0]['base_j']='nan'
        with patch.object(d,'csv_rows',return_value=bad),self.assertRaises(ValueError):m.source_rows()
        with self.assertRaises(ValueError):m.predict(self.case,self.frozen,36,.5)

    def test_actual_prediction_entry_matches_all_saved_candidate_windows(self):
        cases={c['id']:c for c in d.r.h.m.read(d.r.BUNDLE/'inputs.json.gz')}
        rows=d.csv_rows(m.BUNDLE/'window_errors.csv')
        self.assertEqual(len(rows),640)
        use=[x for x in rows if x['method']=='MEMORY30']
        self.assertEqual(len(use),160)
        for row in use:
            value=m.predict(cases[row['id']],self.frozen,float(row['start_s']),float(row['alpha']))
            self.assertEqual(value,float(row['predicted_j']))


if __name__=='__main__':unittest.main()
