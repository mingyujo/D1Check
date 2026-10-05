"""Focused PC boundaries; fake samples are not device validation."""
import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import d1_ap_simulation_closure as c
from tools import d1_ap_idle_response as candidate


def point(t, y, radius=.1):
    return dict(t=t, ap=y, lo=t-radius, hi=t+radius)


class ClosureTests(unittest.TestCase):
    def test_release_is_lane_union_not_inference_or_nominal_end(self):
        windows = c.idle_windows([(0, 2), (1, 4), (16, 17)], 40)
        self.assertEqual(windows, [dict(release_s=4, idle_end_s=16), dict(release_s=17, idle_end_s=40)])
        self.assertEqual(c.idle_windows([(0, 2), (3, 4)], 10), [])
        with self.assertRaises(ValueError):
            c.idle_windows([(2, 1)], 10)

    def test_peak_plateau_query_brackets_not_physical_delay(self):
        samples = [point(2, 28.8),point(4.5, 29.7),point(7,29.7),point(9.5,28.8)]
        r = c.window_readout(samples, dict(release_s=0, idle_end_s=12))
        self.assertTrue(r['interior_rise_then_fall'])
        self.assertEqual(r['peak_first_s'], 4.5)
        self.assertEqual(r['peak_last_s'], 7)
        self.assertIsNone(r['physical_delay_s'])
        self.assertAlmostEqual(r['changed_value_appearance_lo_s'], 1.9)
        self.assertAlmostEqual(r['peak_query_lo_after_release_s'], 4.4)

    def test_ambiguous_release_bracket_not_idle_rise_evidence(self):
        samples = [point(0,27),point(2,30),point(4,29),point(6,28)]
        r = c.window_readout(samples, dict(release_s=0, idle_end_s=8))
        self.assertEqual(r['first_ap_c'], 30)
        self.assertFalse(r['interior_rise_then_fall'])

    def test_missing_gap_nonfinite_are_not_filled_with_zero(self):
        self.assertEqual(c.window_readout([point(1,29),point(3,30)],
            dict(release_s=0,idle_end_s=8))['status'], 'INSUFFICIENT_AP')
        self.assertEqual(c.window_readout([point(1,29),point(3,30),point(20,29)],
            dict(release_s=0,idle_end_s=22))['status'], 'AP_GAP')
        with self.assertRaises(ValueError):
            c.cadence([point(1,math.nan),point(2,29)])

    def test_repeated_value_does_not_identify_hardware_period(self):
        r = c.cadence([point(t,29 if t < 10 else 30) for t in range(0, 20, 2)])
        self.assertEqual(r['query_gap_median_s'], 2)
        self.assertEqual(r['repeated_adjacent'], 8)
        self.assertIsNone(r['hardware_update_period_s'])

    def test_single_state_idle_is_monotonic_and_continuous(self):
        model = dict(ap_cooling_rate_per_s=.05, ap_slope_at_30_c_per_s={'resident_idle':.2})
        segments = [dict(start_s=0,end_s=10,state='idle'),dict(start_s=10,end_s=40,state='idle')]
        cold = candidate.predict(segments,model,28,30,[0,5,10,15,40])
        hot = candidate.predict(segments,model,32,30,[0,5,10,15,40])
        self.assertEqual(cold[0],28)
        self.assertTrue(all(a < b for a,b in zip(cold.values(),list(cold.values())[1:])))
        self.assertTrue(all(a > b for a,b in zip(hot.values(),list(hot.values())[1:])))
        self.assertAlmostEqual(cold[40], 30+(28-30)*math.exp(-.05*40))

    def test_real_inputs_existing_interfaces_no_device_or_refit(self):
        inputs = c.DEFAULT/'inputs.json'
        before = c.sha(inputs)
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)/'readout'
            with patch('subprocess.Popen', side_effect=AssertionError('no processes')), patch.object(c,'plot'):
                result = c.evaluate(inputs, output)
            self.assertEqual(result['evidence_sessions'],8)
            self.assertEqual(result['observed_nonmonotonic_idle_windows'],2)
            self.assertEqual(result['fixed_episode']['status'],'TRADEOFF')
            self.assertIsNone(result['fixed_episode']['model_candidate'])
            self.assertEqual([(row['block'], row['mode']) for row in result['fixed_observations']],
                [('development','serial'),('development','parallel'),
                 ('confirmation','parallel'),('confirmation','serial')])
            self.assertAlmostEqual(result['fixed_observations'][2]['common_window_energy_j_conditional']-
                result['fixed_observations'][3]['common_window_energy_j_conditional'], 4.5585121168)
            dashboard = (output/'index.html').read_text(encoding='utf-8')
            self.assertIn('개발 -36.255J에서 확인 +4.559J', dashboard)
            self.assertIn('완료시점 J', dashboard)
            self.assertEqual(result['complete_dynamic_energy_ap_policy_cases'],0)
            self.assertFalse(result['experiment_ready'])
            for item in result['dynamic_representatives']:
                self.assertIsNone(item['full_window_j'])
                self.assertIsNone(item['policy_rank'])
            with self.assertRaises(FileExistsError):
                c.evaluate(inputs, output)
        self.assertEqual(c.sha(inputs),before)


if __name__ == '__main__':
    unittest.main()
