import copy
import gzip
import json
import unittest
from tools import d1_method_followup as f


class FollowupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.frozen,case=f.x.p.inputs(f.x.p.BUNDLE);cls.initial=case['initial']
        cls.records=[json.loads(line) for line in gzip.decompress((f.ROOT/'run_v1/records.jsonl.gz').read_bytes()).decode().splitlines()]

    def test_fixed_input_full_denominator_and_service(self):
        self.assertEqual(f.spec()['new_simulations'],120)
        self.assertEqual(len(self.records),144)
        for record in self.records:
            self.assertEqual(len(record['ledger']),48)
            self.assertEqual(record['meta']['planned'],48)
            self.assertEqual(record['meta']['deadline_met'],sum('response_ns' in q and q['response_ns']<=q['deadline_offset_ns'] for q in record['ledger']))

    def test_stored_control_recalculated_without_future_feedback(self):
        r=next(r for r in self.records if r['meta']['stage']=='stored_regression' and r['meta']['policy']=='EFT_REFERENCE')
        meta,read=f.read_control(r,self.frozen,self.initial)
        self.assertEqual(read['ledger'],r['ledger']);self.assertEqual(meta['deadline_met'],48)
        corrupt=copy.deepcopy(r);corrupt['meta']['energy_j']+=1
        with self.assertRaises(ValueError):f.read_control(corrupt,self.frozen,self.initial)

    def test_partial_cost_never_joint_completion(self):
        rows=[dict(stage='s',envelope='e',seed=1,scenario='mean',policy=p,planned=48,
            completed=48,deadline_met=48,energy_j=10,peak_ap_c=30,thermal_degree_seconds=5,
            urgent_p95_ms=1,normal_mean_ms=2) for p in f.METHODS[:2]]
        rows[1].update(energy_j=9,peak_ap_c=None,completed=47)
        r=f.compare(rows)[0];self.assertFalse(r['joint_nonworsening']);self.assertIsNone(r['delta_peak_ap_c'])

    def test_full_common_window_integral_and_unchanged_model(self):
        for r in self.records:
            total=120*self.initial['preload_power_w']
            for s in r['segments']:
                if s['state']=='idle':continue
                self.assertIn(s['state'],self.frozen['energy_increment_w'])
                total+=max(0,min(120,s['end_s'])-s['start_s'])*self.frozen['energy_increment_w'][s['state']]
            self.assertAlmostEqual(total,r['meta']['energy_j'],places=7)
            self.assertEqual(len(r['predicted_ap_path']),146)
        self.assertEqual(f.x.p.digest(f.x.p.BUNDLE/'model.json'),f.x.p.MODEL_SHA)
        self.assertEqual(f.x.p.digest(f.x.p.BUNDLE/'initial_inputs.json'),f.x.p.INITIAL_SHA)


if __name__=='__main__':unittest.main()
