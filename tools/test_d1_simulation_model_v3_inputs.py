import copy
import unittest

from tools import d1_simulation_model_v3_inputs as inputs
from tools import d1_simulation_model_v2 as prior


class InputsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.development = inputs.load_development()
        cls.original = prior.prior.read(prior.prior.MODEL)

    def test_registered_roles_counts_groups_and_raw_hash_inventory(self):
        self.assertEqual(len(self.development), 17)
        self.assertEqual({g: sum(inputs.group(c) == g for c in self.development) for g in inputs.GROUPS},
                         dict(old=3, history30=3, history180=3, macro=4, new_recovery=4))
        seen = inputs.load_seen()
        self.assertEqual(len(seen), 26)
        self.assertTrue(all(c['role'] != 'development' for c in seen))
        self.assertTrue(all('previously viewed' in c['evaluation_scope'] for c in seen))
        sources = inputs.source_inventory()
        self.assertTrue(sources['files'])
        self.assertTrue(all(len(h) == 64 for h in sources['files'].values()))
        self.assertFalse(sources['experiment_ready'])

    def test_future_targets_and_measured_schedule_do_not_change_B_forecast(self):
        first = inputs.development_B_cases(self.development, self.original)
        changed = copy.deepcopy(self.development)
        for c in changed:
            c['ap'] = [999.] * len(c['ap'])
            c['power_w'] = [w if t < 35 else 999. for t, w in zip(c['power_t'], c['power_w'])]
            c['actual'] = [dict(start_s=0., end_s=9999., state='idle')]
            c['forecast'] = ['forbidden measured schedule']
            c['last_lane_s'] = 9999.
            c['probe_rows'] = ['forbidden future requests']
            c['actual_requests'] = ['forbidden completion times']
        second = inputs.development_B_cases(changed, self.original)
        self.assertEqual(len(first), 6)
        self.assertEqual(sum(r['planning_shape_role'] == 'development' for r in first), 2)
        self.assertEqual(sum(r['planning_shape_role'] == 'confirmation' for r in first), 4)
        self.assertTrue(all(r['case']['role'] == 'development' for r in first))
        for a, b in zip(first, second):
            self.assertEqual(a['public'], b['public'])
            self.assertEqual(a['legacy'], b['legacy'])
            self.assertEqual(a['requests'], b['requests'])
            self.assertNotEqual(a['case']['ap'], b['case']['ap'])
            self.assertEqual(a['public']['actual'][-1]['end_s'], max(180., a['public']['q'][-1]))

    def test_A_public_is_whitelist_and_retains_causal_conditioning(self):
        for c in self.development:
            p = inputs.public_input(c)
            self.assertTrue(set(p) <= {'id', 'role', 'source_group', 'pre', 'pre_w', 'q',
                                      'history', 'initial_power_late_w'})
            self.assertTrue(all(r['hi'] < 35 for r in p['pre']))
            self.assertIn('initial_power_late_w', p)
        case = next(c for c in self.development if c['id'] == 'development_30_CPU')
        self.assertTrue(inputs.public_input(case)['history'])
        self.assertLessEqual(inputs.public_input(case)['history'][-1]['end_s'], 0)

    def test_noncausal_AP_history_and_power_coverage_fail(self):
        c = copy.deepcopy(self.development[0]); c['pre'][0]['hi'] = 35.
        with self.assertRaisesRegex(ValueError, 'pre AP'):
            inputs.public_input(c)
        c = copy.deepcopy(self.development[0])
        c['history'] = [dict(start_s=0., end_s=36., state='idle')]
        with self.assertRaisesRegex(ValueError, 'future history'):
            inputs.public_input(c)
        c = copy.deepcopy(self.development[0]); c['power_w'] = c['power_w'][:-1]
        with self.assertRaisesRegex(ValueError, 'length'):
            inputs.public_input(c)

    def test_manifest_tickets_cannot_be_reconstructed_from_changed_completion_rows(self):
        c = next(c for c in self.development if c['id'] == 'development_30_PAR')
        bad = copy.deepcopy(c); bad['manifest_requests'][0]['deadline_ms'] += 1
        with self.assertRaisesRegex(ValueError, 'planned requests'):
            inputs.source_manifest(bad)

    def test_new_seen_arrival_forecast_preserves_original_frozen_service(self):
        cases = [c for c in inputs.load_seen() if c['policy'] in ('ARRIVAL_CPU96', 'ARRIVAL_PAR96')]
        outputs = inputs.development_B_cases(cases, self.original)
        self.assertEqual(len(outputs), 2)
        self.assertTrue(all(r['case']['role'] == 'confirmation' for r in outputs))
        self.assertEqual({r['policy'] for r in outputs}, {inputs.CPU, inputs.PAR})
        self.assertTrue(all(len(r['legacy']['ledger']) == 96 for r in outputs))
        self.assertTrue(all('not fully OOF' in r['validation_scope'] for r in outputs))


if __name__ == '__main__':
    unittest.main()
