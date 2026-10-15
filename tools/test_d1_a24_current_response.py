import copy
import unittest
import json
from pathlib import Path
from unittest.mock import patch
from d1_a24_current_response_analysis import crossing,pulse_response
from d1_a24_current_response_diagnostic import validate_plan,DiagnosticClient,PACKAGE
from d1_a24_laptop_validator import ValidationError


class CurrentResponseTest(unittest.TestCase):
    def test_new_app_read_can_resume_after_registered_reconnect(self):
        client=object.__new__(DiagnosticClient)
        with patch('d1_a24_current_response_diagnostic.BoundedClient.command',side_effect=[ValidationError('connection recovered after ambiguous mutation'),b'closed']) as method:
            self.assertEqual(client.command('exec-out','run-as',PACKAGE,'cat','files/closure.json'),b'closed')
            self.assertEqual(method.call_count,2)
    def test_ambiguous_app_start_is_never_replayed(self):
        client=object.__new__(DiagnosticClient)
        with patch('d1_a24_current_response_diagnostic.BoundedClient.command',side_effect=ValidationError('connection recovered after ambiguous mutation')) as method:
            with self.assertRaises(ValidationError):client.command('shell','am','start','-n',PACKAGE)
            self.assertEqual(method.call_count,1)
    def test_bounded_registered_schedule(self):
        p=json.loads((Path(__file__).resolve().parents[1]/'docs/team/a24-measurement-revision02-20261015/current_response_diag_20261015/PLAN.json').read_text())
        self.assertEqual(validate_plan(p),543)
        p['maximum_APP_attempts']=2
        with self.assertRaises(AssertionError):validate_plan(p)
    def test_resource_or_split_change_is_rejected(self):
        p=json.loads((Path(__file__).resolve().parents[1]/'docs/team/a24-measurement-revision02-20261015/current_response_diag_20261015/PLAN.json').read_text())
        p['pulses'][4]['split']='DEVELOPMENT'
        with self.assertRaises(AssertionError):validate_plan(p)
    def test_known_step_detects_total_observed_delay(self):
        samples=[(i/10,100 if i/10<20.6 or i/10>=31.2 else 200) for i in range(601)]
        r=pulse_response(samples,20,30,0,60,.1)
        self.assertEqual(r['status'],'OBSERVED_RESPONSE');self.assertAlmostEqual(r['rise_t50_s'],.6);self.assertAlmostEqual(r['fall_t50_s'],1.2)
    def test_no_response_is_not_zero_delay(self):
        r=pulse_response([(i/10,100) for i in range(601)],20,30,0,60,.1)
        self.assertEqual(r['status'],'NO_CLEAR_INCREASE_ABOVE_BASELINE_VARIATION');self.assertIsNone(r['rise_t50_s'])
    def test_isolated_peak_is_not_crossing(self):
        self.assertIsNone(crossing([(0,100),(.1,200),(.2,100),(.3,100)],150,0,1,.1))
    def test_long_gap_not_bridged(self):
        self.assertIsNone(crossing([(0,200),(1,200)],150,0,2,.1))
    def test_scaling_does_not_change_response_time(self):
        data=[(i/10,100 if i<207 or i>=315 else 250) for i in range(601)]
        a=pulse_response(data,20,30,0,60,.1);b=pulse_response([(t,v*1000) for t,v in data],20,30,0,60,.1)
        self.assertEqual(a['rise_t50_s'],b['rise_t50_s']);self.assertEqual(a['fall_t50_s'],b['fall_t50_s'])
    def test_sparse_data_not_assigned_response(self):
        self.assertEqual(pulse_response([(0,1)],20,30,0,60,.1)['status'],'INSUFFICIENT_READS')


if __name__=='__main__':unittest.main()
