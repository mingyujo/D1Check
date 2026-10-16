import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from tools import d1_ap_tail_observation_results as r


class ResultTests(unittest.TestCase):
    def test_energy_clipping_gaps_and_endpoint_are_not_zero_filled(self):
        c=dict(power_t=[0.,1.,2.,3.],power_w=[1.,2.,3.,4.])
        self.assertAlmostEqual(r.measured_energy(c,.5,2.5)['full_energy_j'],5.)
        self.assertIsNone(r.measured_energy(c,0.,4.)['full_energy_j'])
        self.assertEqual(r.measured_energy(c,0.,4.)['missing_s'],1.)
        self.assertEqual(r.measured_energy(c,0.,4.)['covered_energy_j'],7.5)
        c=dict(power_t=[0.,1.,5.,6.],power_w=[1.]*4)
        x=r.measured_energy(c,0.,6.);self.assertIsNone(x['full_energy_j']);self.assertEqual(x['missing_s'],4.)

    def test_predictions_ignore_post_ap_and_power_targets(self):
        p=r.p;c=copy.deepcopy(p.tail.s.j.m.read(p.tail.s.INPUTS)[0]);original=p.old.p.read(p.j.m.MODEL)
        models=p.old.p.read(p.CANDIDATES);c['actual'][-1]['end_s']=2555.;c['q']=list(map(float,range(35,2556,2)));c['ap']=[28.]*len(c['q'])
        with patch.object(r,'measured_energy',return_value=dict(full_energy_j=None,covered_energy_j=None,covered_s=0.,missing_s=1.)):
            pred,_,_=r.assess_case(c,original,models)
            changed=copy.deepcopy(c);changed['ap']=[99.]*len(c['q']);changed['power_w']=[99.]*len(c['power_w'])
            after,_,_=r.assess_case(changed,original,models)
        self.assertEqual(pred,after)

    def test_phase_direction_and_peak_match_the_same_window(self):
        c=dict(q=[35.,36.,635.,636.,637.],ap=[28.,29.,31.,30.,29.])
        y=[28.,29.,31.,32.,33.]
        a=r.phase_score(c,y,35.,635.);b=r.phase_score(c,y,635.,637.)
        self.assertTrue(a['direction_match']);self.assertFalse(b['direction_match'])
        self.assertEqual(b['observed_change_c'],-2.);self.assertEqual(b['predicted_change_c'],2.)
        self.assertEqual(b['observed_peak_c'],31.);self.assertEqual(b['predicted_peak_c'],33.)

    def test_active_run_cannot_publish_a_finished_graph(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);file=root/'plan.json';r.write(file,dict(output_root=str(root/'active')))
            with self.assertRaises(FileNotFoundError):r.publish(file,root/'results')
            self.assertFalse((root/'results').exists())

    def test_failure_consumption_requires_matching_lower_upper_bounds(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan=dict(entries=[],budget={});counts={}
            for name,cap in [('runtime',4),('warmup',8),('eligibility',4),('load',0)]:
                counts[name]=dict(confirmed_started_at_least=cap,confirmed_returned=cap,actual_started_upper=cap)
            receipt=dict(status='stopped_no_resume',adb_command_slots=1584,last_session_progress=dict(counts=counts))
            x=r.consumption(Path(tmp),plan,receipt,4)
            self.assertEqual(x['total_adb_commands'],1588);self.assertEqual(x['failed_session_confirmed_explicit_inference'],12)
            counts['eligibility']['confirmed_returned']=3
            x=r.consumption(Path(tmp),plan,receipt,4)
            self.assertIsNone(x['failed_session_confirmed_explicit_inference'])
            self.assertIsNone(x['failed_session_exact_counts_from_complete_bounds']['eligibility'])


if __name__=='__main__':unittest.main()
