import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from tools import d1_method_decision_readout as r


class DecisionReadoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.records=r.source.records(r.source.f.ROOT/'run_v1/records.jsonl.gz')

    def test_same_seed_reference_and_complete_denominator(self):
        rows=r.summarize(self.records,'run_v1','new_seed_confirmation',{})
        self.assertEqual(len(rows),12)
        self.assertTrue(all(z['planned']==288 and z['cases']==6 for z in rows))
        self.assertTrue(all(z['seed_ids']=='223001,223002' for z in rows))
        queue=next(z for z in rows if z['policy']=='CPU_BOTTLENECK_GUARD_V1' and z['envelope']=='g0.45_c0.5_b4')
        self.assertTrue(queue['complete_service_and_metrics']);self.assertLess(queue['max_delta_energy_j'],0)
        self.assertGreater(queue['max_delta_peak_ap_c'],0);self.assertTrue(queue['pareto_candidate'])

    def test_zero_relative_heat_cap_blocks_energy_heat_tradeoff(self):
        rows=r.summarize(self.records,'run_v1','new_seed_confirmation',dict(energy_j=0,peak_ap_c=0,thermal_degree_seconds=0))
        queue=[z for z in rows if z['envelope']=='g0.45_c0.5_b4']
        self.assertEqual([z['policy'] for z in queue if z['epsilon_feasible']],['EFT_REFERENCE'])
        same=next(z for z in rows if z['envelope']=='g0.45_c0.75_b4' and z['policy']=='ATC_QUEUED_GUARD_V1')
        self.assertTrue(same['equivalent_to_reference'])
        self.assertTrue(all(z['device_policy_winner'] is None and not z['deployment_allowed'] for z in rows))

    def test_burst_failure_cannot_become_pareto_success(self):
        rows=r.summarize(self.records,'run_v1','new_seed_confirmation',{})
        burst=[z for z in rows if z['envelope']=='g0.15_c0.5_b8']
        self.assertTrue(all(not z['complete_service_and_metrics'] and not z['pareto_candidate'] for z in burst))

    def test_null_cost_not_zero_or_feasible(self):
        records=copy.deepcopy(self.records)
        next(z['meta'] for z in records if z['meta']['policy']=='CPU_BOTTLENECK_GUARD_V1' and z['meta']['stage']=='new_seed_confirmation')['energy_j']=None
        rows=r.summarize(records,'run_v1','new_seed_confirmation',{})
        self.assertTrue(any(not z['model_metrics_known'] and z['max_delta_energy_j'] is None and not z['epsilon_feasible'] for z in rows))

    def test_missing_reference_cost_invalidates_all_paired_differences(self):
        records=copy.deepcopy(self.records)
        target=next(z['meta'] for z in records if z['meta']['policy']=='EFT_REFERENCE' and z['meta']['stage']=='new_seed_confirmation')
        target['peak_ap_c']=None
        rows=r.summarize(records,'run_v1','new_seed_confirmation',{})
        related=[z for z in rows if z['envelope']==target['envelope']]
        self.assertTrue(all(not z['model_metrics_known'] and not z['epsilon_feasible'] and z['max_delta_peak_ap_c'] is None for z in related))

    def test_partial_context_or_invalid_cap_is_not_allowed(self):
        with self.assertRaises(ValueError):r.summarize(self.records[:-1],'run_v1','new_seed_confirmation',{})
        with self.assertRaises(ValueError):r.summarize(self.records,'run_v1','new_seed_confirmation',dict(energy_j=float('nan')))
        with self.assertRaises(ValueError):r.summarize(self.records,'run_v1','new_seed_confirmation',dict(bat_temperature=35))

    def test_registered_readout_runs_without_any_simulation(self):
        with patch.object(r.source.f.x.old.engine,'simulate',side_effect=AssertionError('no new simulation')):
            result=r.readout(r.source.f.ROOT,'new_seed_confirmation',{})
        self.assertEqual(len(result['rows']),28)
        self.assertIsNone(result['counterfactual_accuracy_bounds']);self.assertEqual(result['new_simulations'],0)
        self.assertTrue(all(z['comparison_block'] in ('run_v1','beam_v1','beam_v2') for z in result['rows']))
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)/'readout';r.save(result,output)
            self.assertTrue((output/'constraints_and_frontiers.csv').exists())
            self.assertIn('실제 승자/배포 추천은 null', (output/'index.html').read_text(encoding='utf8'))
            with self.assertRaises(FileExistsError):r.save(result,output)


if __name__=='__main__':unittest.main()
