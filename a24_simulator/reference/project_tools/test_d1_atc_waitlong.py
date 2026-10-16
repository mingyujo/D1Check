"""Pure contracts and real frozen-origin migration; simulator/optimizer updates forbidden."""
import copy
import time
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import torch

from tools import d1_atc_waitlong_study as s
from tools import d1_atc_waitlong_budget as b
from tools import d1_atc_waitlong_migration as m


class LongWaitContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reg, cls.origins=m.read_origins(s.ROOT.parent/"ATC-WAITLINK-EXPAND-11")

    def test_new_namespaces_and_all_registered_cells(self):
        self.assertEqual([len(s.cases(seeds)) for seeds in (s.TRAIN,s.DEV,s.CONFIRM)],[2816,176,176])
        self.assertFalse(set(s.TRAIN)&set(s.DEV+s.CONFIRM))
        self.assertEqual(len(s.FAMILY),11)
        self.assertTrue(all(q['work_units']==1 for case in s.cases(s.DEV) for q in case['requests']))
        for seed in s.DEV:
            self.assertEqual(len([case for case in s.cases(s.DEV) if case['arrival_seed']==seed]),22)

    def test_real_three_origin_exact_migration_forward_and_next_rng(self):
        new=dict(sources=s.source_bindings(self.reg),input_sha=s.parent.a.native.digest({'new':'pure_fixture'}))
        with patch.object(s.parent,'collect',side_effect=AssertionError('environment forbidden')):
            for seed,item in self.origins.items():
                learner,receipt=m.rebind(item['snapshot'],s.parent.deps(self.reg,s.ARM),s.deps(new),seed)
                self.assertEqual(learner.episodes,4096);self.assertFalse(learner.pending)
                self.assertTrue(receipt['network_Adam_action_shuffle_pending_history_exact'])
                self.assertTrue(receipt['next_rng_exact']);self.assertTrue(receipt['public_forward_logprob_value_exact'])
                self.assertEqual(receipt['new_environments'],0);self.assertEqual(receipt['new_learning'],0)
                self.assertEqual(m.file_sha(item['path']),item['sha256'])

    def test_migration_rejects_schema_objective_seed_and_pending_changes(self):
        item=self.origins[1013];old=s.parent.deps(self.reg,s.ARM)
        new=dict(old,sources={'new':'value'},input_sha='new input binding')
        for name in ('schema','objective','arm'):
            with self.assertRaises(ValueError):m.rebind(item['snapshot'],old,dict(new,**{name:'changed'}),1013)
        with self.assertRaises(ValueError):m.rebind(item['snapshot'],old,new,1019)
        altered=copy.deepcopy(item['snapshot']);altered['pending']=[{}]
        with self.assertRaises(ValueError):m.rebind(altered,old,new,1013)

    def test_reserve_stop_is_before_start_without_environment_failure(self):
        worker=b.Budget.__new__(b.Budget);worker.folder=s.ROOT.parent
        worker.reg={'metadata':dict(deadline_unix=1000,final_reserve_seconds=1800)}
        worker.start=1.;worker.rows=[];worker.append=MagicMock()
        with patch('time.time',return_value=999),self.assertRaises(b.ControlledStop):
            with worker.environment('notconsumed','train',True):
                self.fail('stopped body executed')
        worker.append.assert_not_called();self.assertEqual(worker.rows,[])
        worker.reg['metadata']=dict(deadline_unix=2000,final_reserve_seconds=1800)
        with patch('time.time',return_value=500),patch('shutil.disk_usage',return_value=SimpleNamespace(free=40*1024**3)):
            self.assertEqual(worker.can_begin('train')[0],False)
            self.assertEqual(worker.can_begin('confirmation')[0],True)

    def row(self,condition,p95=100.,J=10.,AP=30.):
        return dict(condition=condition,primary=True,planned=2,completed=2,planned_work_units=2,completed_work_units=2,
            incomplete=0,urgent_failure=0,urgent_original_cap_failure=0,normal_failure=0,normal_original_cap_failure=0,
            urgent_p95_ms=p95,energy_j=J,peak_ap_c=AP)

    def test_damage_is_unique_condition_and_eligible_checks_both_references(self):
        inherited=[self.row(0),self.row(1)];rule=[self.row(0,p95=120.),self.row(1,p95=120.)]
        candidate=[self.row(0,p95=130.),self.row(1)]
        result=s.assess(candidate,rule,inherited)
        self.assertEqual(result['damage_conditions'],1)
        self.assertEqual(result['rule_damage_conditions'],1);self.assertEqual(result['inherited_damage_conditions'],1)
        self.assertFalse(result['eligible_guard'])
        middle=[self.row(0,p95=110.),self.row(1)]
        result=s.assess(middle,rule,inherited)
        self.assertTrue(result['rule_guard']);self.assertFalse(result['eligible_guard'])
        self.assertEqual(result['worst_deltas']['inherited_same_seed']['urgent_p95_ms'],10.)

    def stage(self,episode,damage=0,gain=False,eligible=True,key=10.):
        return dict(episode=episode,damage_conditions=damage,meaningful_cost_gain=gain,eligible_guard=eligible,
                    risk_key=[0,0,0,0,0,0,100.,key,30.],cost_key=[key,30.,100.])

    def test_stage_stop_damage_stagnation_and_missing_cost_key(self):
        histories={seed:[self.stage(4096),self.stage(8192,damage=1),self.stage(16384,damage=2)] for seed in s.SEEDS}
        self.assertEqual(s.continuation_stop(histories),'two_transition_service_P95_damage_at_two_seeds')
        histories={seed:[self.stage(ep) for ep in (4096,8192,16384,32768)] for seed in s.SEEDS}
        self.assertEqual(s.continuation_stop(histories),'three_additional_stage_stagnation')
        histories[1013][-1]['cost_key'][0]=9.99
        self.assertIsNone(s.continuation_stop(histories))
        missing=[self.stage(4096,eligible=False,key='UNAVAILABLE'),self.stage(8192,eligible=False,key=10.)]
        self.assertEqual(s.best_key(missing)[0],1)
        self.assertEqual(s.best_key(missing)[1][-2],10.)

    def test_register_source_includes_both_new_tests_and_fixed_runtime(self):
        bindings=s.source_bindings(self.reg)
        self.assertIn('tools/test_d1_atc_waitlong.py',bindings)
        self.assertIn('tools/test_d1_atc_waitlink.py',bindings)
        for name,sha in self.reg['sources'].items():self.assertEqual(bindings[name],sha)

    def test_existing_actual_pending_save_restore_and_rng_exact_without_update(self):
        path=s.ROOT.parent/'ATC-WAITLINK-EXPAND-11/seed1013/paused_checkpoints/DROP_FLAG_WAIT1_1013.pt'
        original_file_sha=m.file_sha(path)
        raw=torch.load(path,map_location='cpu',weights_only=False)
        dependencies=s.parent.deps(self.reg,s.ARM)
        learner=s.learning.Learner.from_snapshot(raw,dependencies)
        self.assertEqual(len(learner.pending),4)
        before=s.parent.payload_digest(learner.snapshot())
        with tempfile.TemporaryDirectory(prefix='waitlong-pure-',dir=s.ROOT.parent) as folder:
            self.assertTrue(Path(folder).resolve().is_relative_to(s.ROOT.parent.resolve()))
            target=Path(folder)/'pending.pt';learner.save(target)
            clone=s.learning.Learner.load(target,dependencies)
            self.assertEqual(before,s.parent.payload_digest(clone.snapshot()))
            self.assertTrue(torch.equal(torch.rand(5,generator=learner.action_rng),torch.rand(5,generator=clone.action_rng)))
            self.assertTrue(torch.equal(torch.randperm(17,generator=learner.shuffle_rng),torch.randperm(17,generator=clone.shuffle_rng)))
            self.assertEqual(clone.steps,raw['steps'])
        self.assertEqual(m.file_sha(path),original_file_sha)


if __name__=='__main__':unittest.main()
