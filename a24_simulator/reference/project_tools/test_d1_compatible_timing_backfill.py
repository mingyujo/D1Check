import copy
import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from tools import d1_compatible_timing_backfill as c


class CompatibleTimingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config=c.b.read(c.b.BUNDLE/'estimates.json');cls.vectors=c.b.read(c.b.BUNDLE/'realizations.json')
        cls.settings=c.b.batch.defaults('explore')
        cls.requests=[dict(id=str(i),ordinal=i,task='classification' if i<2 else 'detection',
            priority='urgent' if i<2 else 'normal',arrival_ns=0,deadline_offset_ns=1500000000 if i<2 else 6000000000) for i in range(3)]

    def simulate(self,vectors=None):
        return c.b.batch.engine.simulate(self.config,vectors or self.vectors,self.requests,
            policy=c.POLICY,settings=self.settings,seed=123,decision_provider=c.Controller())

    def test_actual_event_path_backfills_DG_without_same_task_overlap(self):
        result=self.simulate();ledger=result['ledger']
        self.assertTrue(all(q['status']=='succeeded' for q in ledger))
        self.assertTrue(all(q['backend']=='CPU' for q in ledger[:2]));self.assertEqual(ledger[2]['backend'],'GPU')
        self.assertLess(ledger[2]['dispatch_ns'],ledger[0]['lane_available_ns'])
        self.assertGreaterEqual(ledger[1]['dispatch_ns'],ledger[0]['lane_available_ns'])
        from tools.d1_detector_gpu_reference import occupancy
        self.assertTrue(all(z['historical_fixed_state_exists'] for z in occupancy(ledger)))
        self.assertNotIn('thermal',result)

    def test_worker_released_is_not_lane_available(self):
        lane=dict(request=self.requests[0],phase='WORKER_RELEASED',since=50,dispatch=0)
        free=dict(request=None,phase='AVAILABLE',since=50,dispatch=None)
        d=c.Controller()(self.config,[self.requests[1]],dict(CPU=lane,GPU=free),50,self.settings,None,None)
        self.assertIsNone(d['selected'])

    def test_private_or_future_information_rejected(self):
        free=dict(request=None,phase='AVAILABLE',since=0,dispatch=None)
        q=dict(self.requests[0],arrival_ns=1)
        with self.assertRaises(ValueError):c.Controller()(self.config,[q],dict(CPU=free,GPU=free),0,self.settings,None,None)
        with self.assertRaises(ValueError):c.Controller()(self.config,[dict(self.requests[0],durations_ns=[1])],dict(CPU=free,GPU=free),0,self.settings,None,None)
        with self.assertRaises(ValueError):c.Controller()(self.config,[self.requests[0]],dict(CPU=dict(free,left=1),GPU=free),0,self.settings,None,None)

    def test_realized_timing_not_used_before_observation(self):
        alternate=copy.deepcopy(self.vectors)
        for q in alternate['cells']['detection_GPU_normal']:q['durations_ns'][3]+=200000000
        original=self.simulate();changed=self.simulate(alternate)
        self.assertEqual(original['decisions'][:2],changed['decisions'][:2])
        self.assertGreater(changed['ledger'][2]['lane_available_ns'],original['ledger'][2]['lane_available_ns'])
        self.assertEqual(changed['ledger'][2]['worker_release_ns']-original['ledger'][2]['worker_release_ns'],200000000)

    def test_no_fake_thermal_or_implicit_protocol(self):
        with self.assertRaises(ValueError):c.b.batch.engine.simulate(self.config,self.vectors,self.requests,
            policy='B3_SOLO_EFT_PC',settings=self.settings,seed=123,decision_provider=c.Controller())
        with self.assertRaises(ValueError):c.b.batch.engine.simulate(self.config,self.vectors,self.requests,
            policy=c.POLICY,settings=self.settings,seed=123,decision_provider=c.Controller(),thermal_model={})

    def test_exact_legacy_routing_guard_and_event_regression(self):
        self.assertEqual(c.verify_legacy_engine(c.LEGACY_ENGINE_SHA),'exact_legacy_archive_plus_timing_only_opt_in_routing')
        spec=importlib.util.spec_from_file_location('legacy_arrival_event_engine',c.ARCHIVE)
        old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
        for policy in ('CPU_URGENT','B2_PC','B3_SOLO_EFT_PC'):
            original=old.simulate(self.config,self.vectors,self.requests,policy=policy,settings=self.settings,seed=123)
            current=c.b.batch.engine.simulate(self.config,self.vectors,self.requests,policy=policy,settings=self.settings,seed=123)
            self.assertEqual(original,current)
        with TemporaryDirectory() as directory:
            altered=Path(directory)/'engine.py';altered.write_text(Path(c.b.batch.engine.__file__).read_text(encoding='utf8')+'\n# unrelated change\n',encoding='utf8')
            with patch.object(c.b.batch.engine,'__file__',str(altered)):
                with self.assertRaises(ValueError):c.verify_legacy_engine(c.LEGACY_ENGINE_SHA)

    def test_existing_empirical_model_mask_and_hash_preserved(self):
        self.assertEqual(c.b.f.x.p.backends(dict(task='detection',priority='normal')),('CPU',))
        self.assertEqual(c.b.f.x.p.digest(c.b.f.x.p.BUNDLE/'model.json'),c.b.f.x.p.MODEL_SHA)
        self.assertEqual(c.b.f.x.p.digest(c.b.f.x.p.BUNDLE/'initial_inputs.json'),c.b.f.x.p.INITIAL_SHA)


if __name__=='__main__':unittest.main()
