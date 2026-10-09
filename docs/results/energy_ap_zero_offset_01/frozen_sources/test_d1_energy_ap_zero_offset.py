import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import d1_energy_ap_zero_offset as z


class ZeroOffsetTests(unittest.TestCase):
    def model(self):
        return dict(idle_bias_w=0.,coefficient_count=4,increments=dict(zip(z.STATES,(.7,.8,.4,1.2))))

    def synthetic_cases(self):
        segments=[dict(start_s=0.,end_s=35.,state='idle')];cursor=35.
        for key in z.STATES:
            segments += [dict(start_s=cursor,end_s=cursor+60,state=key),dict(start_s=cursor+60,end_s=cursor+150,state='idle')]
            cursor+=150
        return [dict(id='session_'+str(n),role='development',policy='DEV_A',common_end_s=635.,pre_w=1.,actual=copy.deepcopy(segments)) for n in range(3)]

    def test_four_coefficients_restore_without_idle_offset(self):
        cases=self.synthetic_cases();truth=self.model()
        with patch.object(z.old.observed,'measured_energy',side_effect=lambda c,a,b:dict(full_energy_j=z.energy(c,c['actual'],truth,a,b))):
            fitted=z.train(cases,[c['id'] for c in cases])
        self.assertEqual(fitted['idle_bias_w'],0.)
        for key in z.STATES:self.assertAlmostEqual(fitted['increments'][key],truth['increments'][key],places=10)

    def test_confirmation_and_rank_deficiency_cannot_fit(self):
        cases=self.synthetic_cases();cases[0]['role']='confirmation'
        with self.assertRaisesRegex(ValueError,'development-only'):z.train(cases,[c['id'] for c in cases])
        cases=self.synthetic_cases()
        for c in cases:
            for s in c['actual']:s['state']='idle'
        with patch.object(z.old.observed,'measured_energy',return_value=dict(full_energy_j=5.)):
            with self.assertRaisesRegex(ValueError,'not identified'):z.train(cases,[c['id'] for c in cases])

    def test_missing_training_interval_is_not_zero_filled(self):
        cases=self.synthetic_cases()
        with patch.object(z.old.observed,'measured_energy',return_value=dict(full_energy_j=None)):
            with self.assertRaisesRegex(ValueError,'covered'):z.train(cases,[c['id'] for c in cases])

    def test_additive_energy_and_post_lane_idle_no_drift(self):
        c=self.synthetic_cases()[0];m=self.model()
        self.assertAlmostEqual(z.energy(c,c['actual'],m,0.,635.),z.energy(c,c['actual'],m,0.,35.)+z.energy(c,c['actual'],m,35.,635.))
        self.assertAlmostEqual(z.energy(c,c['actual'],m,600.,635.),35.)
        before=z.energy(c,c['actual'],m,35.,120.)
        c.update(ap=[999.],power_w=[999.])
        self.assertEqual(z.energy(c,c['actual'],m,35.,120.),before)

    def test_hash_change_and_repeated_fit_do_not_reset_output(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder);z.write(p/'candidate.json',self.model())
            z.write(p/'fit_receipt.json',dict(candidate_sha256='wrong',registration_sha256='wrong'))
            with patch.object(z,'registration',return_value={}):
                with self.assertRaisesRegex(ValueError,'hash'):z.read_candidate(p)
                with self.assertRaises(FileExistsError):z.fit(p)

    def recorded(self):
        c=z.old.analysis.j.m.read(z.ROOT/'docs/results/ap_tail_observation_run_05/run_v6/inputs.json.gz')[1]
        contexts=z.old.analysis.j.m.read(z.ROOT/'docs/results/ap_tail_scope_01/run_v4/recorded_contexts.json')
        context=dict(contexts[c['id']],requested_usage='diagnostic_energy_AP_only',power_pre_window_s=[-20,30],
            power_initialization_clock='canonical_common_start_seconds',power_pre_ready_s=31.)
        return c,context

    def test_actual_guarded_AP_entry_and_joint_target_nonuse(self):
        c,context=self.recorded()
        with patch.object(z,'read_candidate',return_value=(self.model(),{})):
            blocked=z.forecast(c,context,'fixture',opt_in=False)
            self.assertEqual(blocked['status'],'blocked')
            baseline=z.forecast(c,context,'fixture',opt_in=True)
            c=copy.deepcopy(c);c['ap']=[999.]*len(c['ap']);c['power_w']=[999.]*len(c['power_w'])
            changed=z.forecast(c,context,'fixture',opt_in=True)
        self.assertEqual(baseline['status'],'diagnostic_energy_AP_only')
        self.assertEqual(baseline['energy_prediction_j'],changed['energy_prediction_j'])
        self.assertEqual(baseline['prediction_ap_c'],changed['prediction_ap_c'])

    def test_usage_future_initialization_unknown_states_block(self):
        c,context=self.recorded()
        with patch.object(z,'read_candidate',return_value=(self.model(),{})):
            context['requested_usage']='RL_cost'
            self.assertEqual(z.forecast(c,context,'fixture',opt_in=True)['status'],'blocked')
            context['requested_usage']='diagnostic_energy_AP_only';context['power_pre_ready_s']=36.
            self.assertEqual(z.forecast(c,context,'fixture',opt_in=True)['status'],'blocked')
            context['power_pre_ready_s']=31.;c=copy.deepcopy(c);c['actual'][1]['state']='detection_GPU'
            self.assertEqual(z.forecast(c,context,'fixture',opt_in=True)['status'],'blocked')


if __name__=='__main__':unittest.main()
