"""Pure deadline/mean-AP/loader/boundary contracts; mocked collector, zero real environments."""
import contextlib
import copy
import gzip
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import torch

from tools import d1_atc_deadline_targets as target
from tools import d1_atc_deadline_ppo as rl
from tools import d1_atc_deadline_study as s
from tools import d1_atc_deadline_budget as budget
from tools import d1_atc_deadline_orchestrator as run
from tools import d1_atc_deadline_report as report
from tools import d1_atc_costguard_targets as oldtarget
from tools import d1_atc_costguard_ppo as oldrl
from tools import test_d1_atc_waitlink as fixture_module


class DeadlineContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture_module.WaitLinkStudy.setUpClass()
        cls.frozen={name:budget.digest(s.ROOT/name) for name in s.source13.check(s.ROOT.parent/'ATC-COST-GUARD-13')['sources']}

    @classmethod
    def tearDownClass(cls):
        for name,sha in cls.frozen.items():
            if budget.digest(s.ROOT/name)!=sha:raise AssertionError('old frozen source changed '+name)

    def fixture(self):
        owner=fixture_module.WaitLinkStudy();controller,raw=owner.labels_fixture('DROP_FLAG_WAIT1')
        raw['row'].update(arrival_seed=923510101,condition=0,family='idle',factor='fixed',primary=True,release_domain=False)
        raw['curve']=[(at,30. if at==35 else 30.1) for at in range(35,181)]
        return controller,raw

    def deps(self,arm):return s.deps(dict(sources={'pure':'fixture'},input_sha='pure'),arm)

    def late(self,raw,controller):
        raw=copy.deepcopy(raw)
        raw['row'].update(urgent_failure=1,urgent_original_cap_failure=1,urgent_p95_ms=1600,
            energy_j=120+2*controller.frozen['energy_increment_w']['classification_CPU'])
        raw['result']['ledger'][0].update(response_ns=1.6e9,output_ready_ns=36.6e9,persist_complete_ns=36.7e9,worker_release_ns=36.8e9,lane_available_ns=37e9)
        raw['segments']=[dict(start_s=0.,end_s=35.,state='idle'),dict(start_s=35.,end_s=37.,state='classification_CPU'),dict(start_s=37.,end_s=120.,state='idle')]
        return raw

    def incomplete(self,raw):
        raw=copy.deepcopy(raw);raw['row'].update(completed=0,incomplete=1,completed_work_units=0,urgent_failure=1,urgent_original_cap_failure=1,energy_j=None,peak_ap_c=None,urgent_p95_ms=None)
        q=raw['result']['ledger'][0];q['status']='unfinished'
        for k in ('response_ns','output_ready_ns','persist_complete_ns','worker_release_ns','lane_available_ns'):q.pop(k,None)
        return raw

    def test_current_cost5_exact_old13_labels_weights_and_fresh_pairing(self):
        controller,raw=self.fixture()
        for actual in (raw,self.late(raw,controller)):
            left=oldtarget.targets(controller,actual,120,'COST5',raw);right=target.targets(controller,actual,120,'CURRENT_COST5',raw)
            for f,g in zip(left[0],right[0]):
                np.testing.assert_array_equal(f['target'],g['target']);np.testing.assert_array_equal(f['valid'],g['valid'])
            for f,g in zip(left[1:],right[1:]):np.testing.assert_array_equal(f,g)
        np.testing.assert_array_equal(rl.WEIGHTS['CURRENT_COST5'],oldrl.WEIGHTS['COST5'])
        models=[rl.Learner(1201,self.deps(arm)) for arm in rl.ARMS]
        for model in models:
            self.assertEqual((model.episodes,model.steps),(0,0));self.assertFalse(model.optimizer.state)
            self.assertEqual(model.network.coupling,'DROP_FLAG_WAIT1')
        for model in models[1:]:
            for k,v in models[0].network.state_dict().items():self.assertTrue(torch.equal(v,model.network.state_dict()[k]))
            self.assertTrue(torch.equal(models[0].action_rng.get_state(),model.action_rng.get_state()))
            self.assertTrue(torch.equal(models[0].shuffle_rng.get_state(),model.shuffle_rng.get_state()))
        for model in models[1:]:
            with self.assertRaises(ValueError):rl.Learner.from_snapshot(models[0].snapshot(),model.dependencies)
        with self.assertRaises(ValueError):rl.Learner.from_snapshot(dict(models[0].snapshot(),version='atc-costguard13-learner-v1'),models[0].dependencies)

    def test_deadline_channels_no_time_reward_and_valid_mask_blocks_old_critic(self):
        controller,reference=self.fixture();raw=self.late(reference,controller)
        orig=s.objectives.service.targets(controller,raw,120,'CAUSAL')
        for arm in rl.ARMS[1:]:
            frames,costs,valid,reward=target.targets(controller,raw,120,arm,reference)
            self.assertFalse(valid[0]);self.assertFalse(valid[9]);self.assertEqual(costs[8],0.)
            np.testing.assert_array_equal(reward,np.zeros(len(frames)))
            np.testing.assert_array_equal(costs[2:8],orig[1][2:8])
            for frame,prior in zip(frames,orig[0]):
                np.testing.assert_array_equal(frame['target'][3:9],prior['target'][3:9])
                np.testing.assert_array_equal(frame['valid'][3:9],np.ones(6,dtype=bool))
                self.assertEqual(frame['target'][0],0.);self.assertEqual(frame['target'][9],0.)
                frame['old_value']=np.full(10,7.,dtype=np.float32)
            model=rl.Learner(1201,self.deps(arm))
            reference_loss=rl.core.ppo_losses(model.network,[frames],model.multipliers)
            np.testing.assert_array_equal(reference_loss['advantage'][:,[0,9]].numpy(),np.zeros((len(frames),2)))
            model.add(frames,costs,valid,raw['row'])
            self.assertFalse(model.episode_logs[0]['deadline_objective']['time_reward_valid'])
            clone=rl.Learner.from_snapshot(model.snapshot(),model.dependencies)
            self.assertEqual(clone.episode_logs,model.episode_logs);self.assertEqual(len(clone.pending),1)

    def test_mean_ap_geometry_fixed_denominators_pairing_and_partition(self):
        constant={'curve':[(at,30.) for at in range(35,181)]}
        ramp={'curve':[(at,float(at)) for at in range(35,181)]}
        for end in (120,180):
            self.assertEqual(target.ap_mean_suffix(constant,0,end),30.)
            self.assertEqual(target.ap_mean_suffix(constant,end*1e9,end),0.)
            self.assertEqual(target.ap_mean_suffix(constant,(end+1)*1e9,end),0.)
            t=35.25
            expected=(end**2-t**2)/(2*(end-35))
            self.assertAlmostEqual(target.ap_mean_suffix(ramp,t*1e9,end),expected)
            self.assertAlmostEqual(target.ap_mean_suffix(constant,t*1e9,end),30*(end-t)/(end-35))
            shifted={'curve':[(at,val+2.) for at,val in constant['curve']]}
            self.assertAlmostEqual(target.ap_mean_suffix(shifted,t*1e9,end)-target.ap_mean_suffix(constant,t*1e9,end),2*(end-t)/(end-35))
            # More decision boundaries do not change full physical integral.
            ts=[35e9,35.25e9,36.6e9,90e9,end*1e9]
            suffix=np.array([target.ap_mean_suffix(ramp,v,end) for v in ts])
            intervals=np.r_[suffix[:-1]-suffix[1:],suffix[-1]]
            self.assertAlmostEqual(float(intervals.sum()),target.ap_mean_suffix(ramp,35e9,end))
        c,raw=self.fixture();more=copy.deepcopy(c);step=copy.deepcopy(more.snapshots[0]);step['now_ns']=35.1e9;more.snapshots.insert(1,step)
        ref=copy.deepcopy(raw);raw['curve']=[(at,val+.05 if at>35 else val) for at,val in raw['curve']]
        for arm in rl.ARMS[1:]:np.testing.assert_array_equal(target.targets(c,raw,120,arm,ref)[1][:2],target.targets(more,raw,120,arm,ref)[1][:2])

    def test_incomplete_equal_work_costs_invalid_service_preserved_and_mean_missing(self):
        c,ref=self.fixture();raw=self.incomplete(ref)
        for actual,reference in ((raw,ref),(ref,raw)):
            for arm in rl.ARMS[1:]:
                frames,costs,valid,reward=target.targets(c,actual,120,arm,reference)
                np.testing.assert_array_equal(valid[[0,1,2,9]],np.zeros(4,dtype=bool))
                np.testing.assert_array_equal(valid[3:9],np.ones(6,dtype=bool))
                for f in frames:np.testing.assert_array_equal(f['valid'][[0,1,2,9]],np.zeros(4,dtype=bool))
                self.assertTrue(np.isfinite(costs).all());self.assertEqual(float(reward.sum()),0.)
        observed120=target.ap_mean_suffix(raw,35e9,120);observed180=target.ap_mean_suffix(raw,35e9,180)
        raw['row'].update(mean_ap_120_c=None,mean_ap_180_c=None,observed_mean_ap_120_c=observed120,observed_mean_ap_180_c=observed180,mean_ap_equal_work_valid=False)
        report.validate_means(raw,raw['row'])
        self.assertIsNone(report.aggregate([30.,None])['mean']);self.assertEqual(report.aggregate([30.,None])['missing'],1)
        self.assertEqual(report.aggregate([30.,None])['complete_conditional_mean'],30.)
        q=copy.deepcopy(ref['row']);q.update(policy='A',mean_ap_120_c=30.,mean_ap_180_c=30.,energy_j=1.,peak_ap_c=31.)
        better=dict(q,policy='B',energy_j=.9);bad=dict(q,policy='C',urgent_failure=1,energy_j=.1)
        pareto=report.pareto_by_scope([q,better,bad]);full={v['role']:v for v in pareto if v['scope']=='full'}
        self.assertFalse(full['A']['mean_pareto']);self.assertTrue(full['B']['mean_pareto']);self.assertIsNone(full['C']['mean_pareto'])
        for end in (120,180):
            missing=copy.deepcopy(raw);missing['curve']=[p for p in missing['curve'] if p[0]!=end]
            with self.assertRaises(ValueError):target.ap_mean_suffix(missing,35e9,end)
        malformed=copy.deepcopy(raw);malformed['curve'][3]=(38,float('nan'))
        with self.assertRaises(ValueError):target.ap_mean_suffix(malformed,35e9,180)
        with self.assertRaises(ValueError):target.ap_mean_suffix(raw,float('nan'),180)
        missing=copy.deepcopy(raw);missing['row']['completed_work_units']=None
        with self.assertRaises(ValueError):target.targets(c,missing,120,'DEADLINE_MEAN180',ref)

    def test_dev_absolute_service_only_no_p95_key_and_shared_stop(self):
        _,raw=self.fixture();raw['row'].update(energy_j=1.,peak_ap_c=30.,mean_ap_180_c=29.)
        rr=[dict(raw['row'],condition=i,urgent_p95_ms=999999.) for i in range(160)]
        result=s.assess(rr,[],[]);self.assertTrue(result['eligible_guard']);self.assertFalse(result['p95_used_in_selection_or_stop'])
        changed=copy.deepcopy(rr)
        for row in changed:row['urgent_p95_ms']=None
        self.assertEqual(result,s.assess(changed,[],[]))
        changed[0]['urgent_failure']=1;self.assertFalse(s.assess(changed,[],[])['eligible_guard'])
        changed=copy.deepcopy(rr);changed[0]['mean_ap_180_c']=None;self.assertFalse(s.assess(changed,[],[])['eligible_guard'])
        history=[dict(episode=512*2**i,damage_conditions=0,service_risk=[0]*5,eligible_guard=True,cost_key=[1.,29.,30.]) for i in range(4)]
        histories={seed:copy.deepcopy(history) for seed in s.SEEDS}
        self.assertEqual(s.continuation_stop(histories),'three_additional_stage_cost_stagnation')
        histories[s.SEEDS[0]][-1]['cost_key'][1]-=.001
        self.assertIsNone(s.continuation_stop(histories))
        stop={arm:'three_additional_stage_cost_stagnation' for arm in s.ARMS};stop[s.ARMS[-1]]=None
        self.assertIsNone(run.shared_stop(stop));stop[s.ARMS[-1]]='two_transition_service_damage_at_two_seeds'
        self.assertEqual(run.shared_stop(stop),'two_transition_service_damage_at_two_seeds')
        for seed in s.SEEDS[:2]:
            for item,n in zip(histories[seed][-3:],(1,2,3)):item['damage_conditions']=n
        self.assertEqual(s.continuation_stop(histories),'two_transition_service_damage_at_two_seeds')

    def test_resource_floors_observed_before_start_no_consumption_on_stop(self):
        with tempfile.TemporaryDirectory(prefix='pure14_',dir=s.ROOT.parent) as directory:
            self.assertTrue(Path(directory).is_relative_to(s.ROOT.parent))
            b=budget.Budget.register(Path(directory)/'worker','model',dict(deadline_unix=time.time()+10000,final_reserve_seconds=3600))
            def space(gib):return type('Disk',(),{'free':gib*1024**3})()
            with patch('shutil.disk_usage',return_value=space(15)),patch.object(budget,'available_ram_bytes',return_value=2*1024**3):
                self.assertEqual(b.can_begin('train'),(False,'raw_disk_reserve'));self.assertEqual(b.can_begin('confirmation'),(True,None))
            with patch('shutil.disk_usage',return_value=space(20)),patch.object(budget,'available_ram_bytes',return_value=1024**3):
                with b.session():
                    with self.assertRaises(budget.ControlledStop):
                        with b.environment('neverstarted','train',True):self.fail('must not enter')
                self.assertEqual(b.used()['environments'],0);self.assertEqual(b.used()['failed'],0)
                self.assertEqual(b.last_resources['available_ram_bytes'],1024**3)
            self.assertEqual(budget.AGGREGATE['model_workers'],1)

    def test_collector_one_commit_and_mean_failure_inside_session_mock_only(self):
        c,raw=self.fixture();row=raw['result']['ledger'][0]
        for snap in c.snapshots:snap.update(raw_rank_same=True,ATC_EDD_same=True,ATC_EDD_legal_actions_same=True)
        result=copy.deepcopy(raw['result']);result['metrics']=dict(urgent_p95_ms=200,normal_mean_ms=None)
        class FakeBudget:
            def __init__(self):self.failures=0
            @contextlib.contextmanager
            def environment(self,*args):
                try:yield
                except BaseException:self.failures+=1;raise
        case=dict(arrival_seed=923510101,condition=0,family='idle',factor='fixed',primary=True,release_domain=False,requests=[{k:row[k] for k in ('id','ordinal','task','priority','arrival_ns','deadline_offset_ns','work_units')}])
        costs=dict(whole_120s_j=raw['row']['energy_j'],ap_path=[v for _,v in raw['curve']])
        with tempfile.TemporaryDirectory(prefix='pure14collect_',dir=s.ROOT.parent) as directory:
            self.assertTrue(Path(directory).is_relative_to(s.ROOT.parent));folder=Path(directory)
            b=FakeBudget()
            with patch.object(s.parent.engine,'simulate',return_value=result) as simulator,patch.object(s.parent,'realizations',return_value={}),patch.object(s.parent,'audit_ledger',return_value={}),patch.object(s.parent.a.hybrid,'account',return_value=(raw['segments'],costs,180)),patch.object(s.os,'replace',wraps=s.os.replace) as commit:
                saved=s.collect(b,folder,'fixture','test',case,c)
                commits=[args[1] for args,_ in commit.call_args_list]
                self.assertEqual(sum(str(v).endswith('.json.gz') for v in commits),1)
                self.assertEqual(sum(str(v).endswith('fixture.json') for v in commits),1)
                receipt=budget.read(folder/'rows/fixture.json');stored=json.loads(gzip.decompress((folder/'items/fixture.json.gz').read_bytes()))
                self.assertEqual(receipt['row'],stored['row']);report.validate_means(saved,saved['row'])
                self.assertEqual(simulator.call_count,1)  # mocked call, no simulator body was executed
                with patch.object(target,'ap_mean_suffix',side_effect=ValueError('missing180')):
                    with self.assertRaises(ValueError):s.collect(b,folder,'invalidmean','test',case,c)
                self.assertEqual(b.failures,1);self.assertFalse((folder/'rows/invalidmean.json').exists());self.assertFalse((folder/'items/invalidmean.json.gz').exists())


if __name__=='__main__':unittest.main()
