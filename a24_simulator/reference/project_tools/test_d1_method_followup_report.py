import copy
import csv
import json
import unittest
from tools import d1_method_followup_report as r


class ReportTests(unittest.TestCase):
    def test_historical_source_guard_rejects_accounting_change(self):
        from tempfile import TemporaryDirectory
        from pathlib import Path
        reg=json.loads((r.f.ROOT/'run_v1/registered_before_run.json').read_text())
        key='tools/d1_empirical_request_policy.py'
        self.assertEqual(r.verify_registered_source(key,reg['hashes'][key],r.f.ROOT),
            'exact_archive_plus_verified_namespace_only_extension')
        with TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'source_snapshots').mkdir()
            archive=(r.f.ROOT/'source_snapshots/d1_empirical_request_policy.py').read_bytes()
            (root/'source_snapshots/d1_empirical_request_policy.py').write_bytes(archive+b'\n# changed\n')
            with self.assertRaises(ValueError):r.verify_registered_source(key,reg['hashes'][key],root)

    def test_both_candidate_names_survive_aggregation(self):
        for folder in ('beam_v1','beam_v2'):
            records=r.records(r.f.ROOT/folder/'records.jsonl.gz')
            rows=r.aggregate_candidates(r.f.compare([z['meta'] for z in records]))
            self.assertEqual(len(rows),8)
            self.assertEqual(sum(z['planned'] for z in rows),48*48)
            self.assertEqual(sum(z['joint_nonworsening_cases'] for z in rows),0)

    def test_missing_output_stays_unknown(self):
        pair=dict(stage='s',envelope='e',policy='candidate',planned=48,deadline_met=47,
            full_service=False,joint_nonworsening=False,delta_energy_j=1,delta_peak_ap_c=None,
            delta_thermal_degree_seconds=None,delta_urgent_p95_ms=1,delta_normal_mean_ms=2,
            delta_deadline_met=-1)
        result=r.aggregate_candidates([pair,copy.deepcopy(pair)])[0]
        self.assertIsNone(result['mean_delta_peak_ap_c'])
        self.assertEqual(result['planned'],96)
        self.assertEqual(result['full_service_cases'],0)

    def test_shared_values_match_source_and_no_observed_curve(self):
        frozen,case=r.f.x.p.inputs(r.f.x.p.BUNDLE)
        with (r.f.ROOT/'representative_curves.csv').open(encoding='utf8') as fp:rows=list(csv.DictReader(fp))
        self.assertTrue(all(z['observed_j']==z['observed_ap_c']=='' for z in rows))
        for record in r.records(r.f.ROOT/'run_v1/records.jsonl.gz'):
            self.assertAlmostEqual(r.energy(record,120,frozen,case['initial']),record['meta']['energy_j'],places=7)
        with (r.f.ROOT/'state_exposure.csv').open(encoding='utf8') as fp:exposure=list(csv.DictReader(fp))
        self.assertEqual(set(z['study'] for z in exposure),{'run_v1','beam_v1','beam_v2'})


if __name__=='__main__':unittest.main()
