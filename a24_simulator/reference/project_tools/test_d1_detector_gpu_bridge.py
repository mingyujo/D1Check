import copy
import gzip
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from tools import d1_detector_gpu_report as report
from tools import d1_detector_gpu_bridge as b
from tools import d1_detector_gpu_reference as reference


class BridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.evidence=report.load(b.ROOT/'run_v1/timing_evidence.json')
        cls.controls=report.load(b.ROOT/'run_v1/timing_ledgers.json')
        cls.refs=report.load(b.ROOT/'reference_v1/timing_ledgers.json')

    def test_actual_paired_worker_release_boundary(self):
        row=dict(zip(b.base.STEPS,[10,12,20,24,27,30]));row['terminal_status']='succeeded'
        self.assertEqual(b.phases(row),[2,8,4,3,3])
        self.assertEqual(sum(b.phases(row)),20)
        del row['worker_release_ns']
        with self.assertRaises(KeyError):b.phases(row)

    def test_invalid_order_and_failure_rejected(self):
        row=dict(zip(b.base.STEPS,[10,12,20,24,23,30]));row['terminal_status']='succeeded'
        with self.assertRaises(ValueError):b.phases(row)
        row['worker_release_ns']=27;row['terminal_status']='failed'
        with self.assertRaises(ValueError):b.phases(row)

    def test_original_roles_and_delegate_evidence(self):
        self.assertEqual(len(self.evidence['rows']),32)
        for role in ('development','confirmation'):
            for cell in b.CELLS:
                rows=[z for z in self.evidence['rows'] if z['role']==role and z['cell']==cell]
                self.assertEqual(len(rows),4)
                self.assertTrue(all(len(z['durations_ns'])==5 for z in rows))
                self.assertTrue(all(z['independent_sessions_per_cell_role']==1 for z in rows))
                if 'GPU' in cell:self.assertTrue(all(z['gpu_delegate_verified'] for z in rows))
        self.assertFalse(self.evidence['comparison']['apk_identical'])
        self.assertTrue(all(self.evidence['comparison']['same_runtime'].values()))

    def test_portable_development_vectors_match_extracted_original(self):
        vectors=b.read(b.BUNDLE/'realizations.json')['cells']
        for row in self.evidence['rows']:
            if row['role']=='development':
                original=next(z for z in vectors[row['cell']] if z['source_request_id']==row['source_request_id'])
                self.assertEqual(original['durations_ns'],row['durations_ns'])

    def test_historical_timing_does_not_admit_current_physics(self):
        req=b.requirements(self.evidence)
        for k in ('current_dg_service','current_dg_increment_w','current_cc_dg_increment_w','current_ap_dg_transfer','current_ap_cc_dg_transfer'):
            self.assertIsNone(req[k])
        self.assertFalse(self.evidence['current_profile_admission'])
        self.assertFalse(req['device_plan_created']);self.assertFalse(req['device_claim_created'])

    def test_current_backend_mask_does_not_silently_expand(self):
        self.assertEqual(b.f.x.p.backends(dict(task='detection',priority='normal')),('CPU',))
        self.assertNotIn('detection_GPU_normal',b.f.x.p.CELLS)

    def test_current_joint_cost_missing_remains_rejected(self):
        with self.assertRaises(ValueError):b.f.x.p.state(['classification_CPU','detection_GPU'])
        frozen,_=b.f.x.p.inputs(b.f.x.p.BUNDLE)
        self.assertNotIn('detection_GPU',frozen['energy_increment_w'])

    def test_original_arrivals_and_full_denominators(self):
        inputs=report.load(b.ROOT/'run_v1/inputs.json')
        for item in inputs:
            for rec in self.controls+self.refs:
                if (rec['meta']['envelope'],rec['meta']['seed'])==(item['envelope'],item['seed']):
                    self.assertEqual(len(rec['ledger']),48)
                    self.assertEqual([(q['id'],q['arrival_ns']) for q in rec['ledger']],[(q['id'],q['arrival_ns']) for q in item['tickets']])

    def test_unknown_same_task_parallel_explicit_and_no_partial_cost(self):
        rows=report.aggregate(self.controls+self.refs)
        self.assertEqual(len(rows),32)
        self.assertTrue(all(z['planned']==96 and z['energy_j'] is None and z['ap_peak_c'] is None for z in rows))
        self.assertEqual(sum(z['meta']['unmeasured_concurrency_s']>0 for z in self.refs),12)
        for rec in self.refs:
            self.assertEqual(reference.occupancy(rec['ledger']),rec['segments'])
            self.assertAlmostEqual(sum(z['end_s']-z['start_s'] for z in rec['segments']),120)
            self.assertFalse(rec['meta']['current_profile_supported'])

    def test_cost_or_denominator_corruption_rejected(self):
        bad=copy.deepcopy(self.controls[:1]);bad[0]['meta']['energy_j']=0
        with self.assertRaises(ValueError):report.aggregate(bad)
        bad=copy.deepcopy(self.controls[:1]);bad[0]['ledger'].pop()
        with self.assertRaises(ValueError):report.aggregate(bad)

    def test_registered_sources_and_frozen_bytes_unchanged(self):
        report.verify(b.ROOT)
        self.assertEqual(b.f.x.p.digest(b.f.x.p.BUNDLE/'model.json'),b.f.x.p.MODEL_SHA)
        self.assertEqual(b.f.x.p.digest(b.f.x.p.BUNDLE/'initial_inputs.json'),b.f.x.p.INITIAL_SHA)

    def test_compressed_shared_bytes_need_no_original_or_new_simulation(self):
        with TemporaryDirectory() as directory:
            path=Path(directory)/'saved.json'
            raw=b'{"evidence":"recorded","energy_j":null}'
            Path(str(path)+'.gz').write_bytes(gzip.compress(raw,mtime=0))
            with patch.object(b.batch.engine,'simulate',side_effect=AssertionError('no simulation')):
                self.assertEqual(report.source_bytes(path),raw)
                self.assertIsNone(report.load(path)['energy_j'])


if __name__=='__main__':unittest.main()
