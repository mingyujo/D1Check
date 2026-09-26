"""Focused checks for the post-hoc arrival stress accounting."""
import csv
import json
import unittest

from tools import d1_arrival_energy_sensitivity as stress


def rows(name):
    with (stress.OUTPUT / name).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


class ArrivalEnergyStressTest(unittest.TestCase):
    def test_strict_p_and_b3_have_identical_recorded_execution(self):
        schedules = stress.load_timelines()
        fields = ('id', 'backend', 'dispatch_ns', 'execution_start_ns',
                  'output_ready_ns', 'persist_complete_ns', 'lane_available_ns')
        for scenario in stress.SCENARIOS:
            p = schedules['strict', scenario, 'P_PAIR_COST_PC']
            b = schedules['strict', scenario, 'B3_SOLO_EFT_PC']
            self.assertEqual([[r.get(k) for k in fields] for r in p],
                             [[r.get(k) for k in fields] for r in b])

    def test_profile_is_explicit_whole_device_assumption(self):
        p = stress.profile(3, 42, {'idle', 'idle|queued', 'classification_CPU',
                                   'classification_CPU+det_GPU'})
        self.assertEqual(p['evidence'], 'explicit_assumptions')
        self.assertEqual(p['states']['idle|queued']['power_w'], 1)
        self.assertEqual(p['states']['classification_CPU']['power_w'], 2)
        self.assertEqual(p['states']['classification_CPU+det_GPU']['power_w'], 3)
        self.assertEqual(p['states']['classification_CPU+det_GPU']['thermal']['AP']['equilibrium_c'], 42)

    def test_time_integral_and_missing_coverage(self):
        p = stress.profile(3, 42, {'idle'})
        trace = [dict(start_s=0., end_s=120., state='idle', cumulative_energy_j=120.,
                      temperature_start={'AP':29.})]
        self.assertEqual(stress.sample_path(trace, p, 60), (60., 29.))
        with self.assertRaises(ValueError):
            stress.sample_path(trace, p, 121)

    def test_published_stress_scope_and_sign_flip(self):
        contrast = rows('arrival_energy_stress_contrasts.csv')
        summary = rows('arrival_energy_stress.csv')
        path = rows('arrival_energy_stress_path.csv')
        self.assertEqual(len(contrast), 2*3*4)
        lookup = {(r['mode'], r['scenario'], r['profile']): r for r in contrast}
        self.assertTrue(all(float(r['p_minus_b3_energy_j_assumed']) == 0
                            for r in contrast if r['mode'] == 'strict'))
        self.assertGreater(float(lookup['explore','queue','P2_T30']['p_minus_b3_energy_j_assumed']), 0)
        self.assertLess(float(lookup['explore','queue','P3_T30']['p_minus_b3_energy_j_assumed']), 0)
        manifest = json.loads((stress.OUTPUT / 'arrival_energy_stress_profiles.json').read_text(encoding='utf-8'))
        self.assertEqual(manifest['device_sessions'], 0)
        self.assertEqual(manifest['evidence'], 'explicit_assumptions_only')
        self.assertIn('temperature-to-runtime feedback', manifest['unsupported'])
        self.assertEqual(len(rows('arrival_energy_stress_path.csv')), 2*3*5*4*25)
        endpoints = {(r['mode'],r['scenario'],r['policy'],r['profile']): r
                     for r in path if r['time_s'] == '120'}
        for row in summary:
            end = endpoints[row['mode'],row['scenario'],row['policy'],row['profile']]
            self.assertAlmostEqual(float(row['energy_j_assumed']),
                                   float(end['cumulative_energy_j_assumed']))


if __name__ == '__main__':
    unittest.main()
