import copy
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from tools import d1_queue_ppo_design as d
from tools import d1_queue_ppo_v2 as v


class DesignTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.frozen,cls.initial_case=v.q.p.inputs(v.q.p.BUNDLE)

    def test_capacity_failure_is_not_witness_success(self):
        for context in d.workload.SCENARIOS:
            for family in d.workload.FAMILIES:
                cert=d.classify(d.workload.workload(family,610720001),self.frozen,context)
                self.assertEqual(cert['status'],'overload_proved' if family in ('queue','burst') else 'feasible_witness')
                self.assertFalse(cert['physical_capacity_certified'])
        model=copy.deepcopy(self.frozen)
        for x in model['service'].values():
            if 'classification_GPU_urgent' in x['phase_means_ns']:
                x['phase_means_ns']['classification_GPU_urgent'][1]=3e9
        cert=d.classify(d.workload.workload('low',610720001),model,'mean')
        self.assertEqual(cert['status'],'unknown')  # passing detector bound is insufficient

    def test_witness_keeps_lane_tail_and_supported_joint(self):
        q0=dict(id='a',ordinal=0,task='classification',priority='urgent',arrival_ns=119000000000,deadline_offset_ns=1500000000)
        job=dict(id='a',backend='GPU',dispatch_ns=119e9,response_ns=119.1e9,lane_available_ns=120.1e9)
        result=d.validate_witness([q0],[job])
        self.assertEqual(result['service_misses'],0);self.assertFalse(result['all_lane_release_by_120'])
        q1=dict(q0,id='b',ordinal=1)
        with self.assertRaisesRegex(ValueError,'lane overlap'):
            d.validate_witness([q0,q1],[job,dict(job,id='b')])
        with self.assertRaisesRegex(ValueError,'unsupported joint'):
            d.validate_witness([q0,q1],[dict(job,backend='CPU'),dict(job,id='b')])

    def test_invalid_inputs_and_primary_overload_are_blocked(self):
        tickets=d.workload.workload('low',610720001)
        wrong=copy.deepcopy(tickets);wrong[0]['deadline_offset_ns']+=1
        with self.assertRaisesRegex(ValueError,'deadline'):d.classify(wrong,self.frozen,'mean')
        wrong=copy.deepcopy(tickets);wrong[0]['priority']='normal'
        if wrong[0]['task']=='detection':wrong[0]['priority']='urgent'
        with self.assertRaises(ValueError):d.classify(wrong,self.frozen,'mean')
        plan=d.specification();plan['data']['primary_families']=['queue']
        with self.assertRaisesRegex(ValueError,'primary admission blocked'):d.preflight(plan,self.frozen)

    def test_plan_budget_split_hash_and_unchanged_models(self):
        plan=v.load_plan();train,val,test=d.cases(plan)
        self.assertEqual((len(train),len(val),len(test)),(1024,24,192))
        self.assertEqual(set(f for _,f,_ in train),{'low','sustained'})
        self.assertFalse({s for s,_,_ in train}&{s for s,_,_ in test})
        self.assertEqual(sum(plan['budget']['counts'].values()),10024)
        self.assertEqual(plan['budget']['counts']['training'],6*128*8)
        evidence=json.loads((d.BUNDLE/'verification.json').read_text(encoding='utf8'))
        original=evidence['check']['sources']
        for name in v.q.hashes():self.assertEqual(v.q.p.digest(v.q.p.ROOT/name),original[name],name)

    def test_check_never_calls_engine_optimizer_or_creates_claim(self):
        before={p.name for p in d.BUNDLE.iterdir()};claim=v.claim_path()
        with (patch.object(v.q.old.engine,'simulate',side_effect=AssertionError('no engine in Check')),
              patch.object(v.q.prev,'optimize',side_effect=AssertionError('no learning in Check'))):
            result=v.check()
        self.assertEqual(result['policy_simulations'],0);self.assertFalse(result['consumption_claim_created'])
        self.assertFalse(claim.exists());self.assertEqual(before,{p.name for p in d.BUNDLE.iterdir()})

    def test_consumed_output_owner_and_plan_claim_block_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            existing=Path(tmp)/'old';existing.mkdir()
            with self.assertRaisesRegex(ValueError,'existing/consumed'):v.check(existing)
            lock=Path(tmp)/'owner';lock.write_text('{}')
            with patch.object(v.q,'LOCK',lock),self.assertRaisesRegex(ValueError,'owner'):v.check()
            claim=Path(tmp)/'claim';claim.write_text('{}')
            with patch.object(v,'claim_path',return_value=claim),self.assertRaisesRegex(ValueError,'claimed'):v.check()

    def test_thermal_costs_cannot_cancel_and_selection_matches(self):
        row=dict(energy_j=150.,thermal_degree_seconds=12.,peak_ap_c=31.,urgent_service_failure=0,normal_service_failure=0,
            urgent_n=6,normal_n=18,equal_work=True,urgent_p95_ms=100.,normal_mean_ms=700.)
        low=dict(row,thermal_degree_seconds=8.,peak_ap_c=29.)
        self.assertEqual(v.costs(low,row).tolist(),[0.,0.,0.,0.])
        self.assertTrue(np.all(v.costs(row,low)[2:]>0))
        self.assertEqual(v.validation_key([low],[row])[3],0)
        self.assertEqual(v.validation_key([row],[low])[3],1)
        within=dict(row,thermal_degree_seconds=row['thermal_degree_seconds']+d.EPS/2)
        outside=dict(row,thermal_degree_seconds=row['thermal_degree_seconds']+d.EPS*2)
        self.assertEqual(v.validation_key([within],[row])[3],0)
        self.assertEqual(v.validation_key([outside],[row])[3],1)

    def test_energy_and_service_rewards_preserved(self):
        initial={k:copy.deepcopy(self.initial_case['initial'][k]) for k in ('preload','preload_power_w')}
        v.q.prev.seed_all(101);net=v.q.ActorCritic()
        row,result,c,extra=v.simulate(self.frozen,initial,d.workload.workload('low',101),'mean','QUEUE',net)
        original=v.q.rewards(c,result,extra,initial,self.frozen)
        changed=v.rewards(c,result,extra,initial,self.frozen,row,row)
        np.testing.assert_array_equal(changed[:,:3],original[:,:3])
        self.assertAlmostEqual(float(changed[:,0].sum()),-row['energy_j']/10,places=5)
        np.testing.assert_allclose(changed[:,1:].sum(0),v.costs(row,row),atol=1e-7)
        self.assertTrue(result['decisions'][0]['evidence_only_not_actor_features'])

    def test_controller_observation_and_action_preserve_causal_boundary(self):
        initial={k:copy.deepcopy(self.initial_case['initial'][k]) for k in ('preload','preload_power_w')}
        tickets=d.workload.workload('low',101);queue=[tickets[0]]
        lanes={b:dict(request=None,phase=None,since=None,dispatch=None) for b in ('CPU','GPU')}
        old=v.q.Controller(self.frozen,initial,'SHARED_EFT');new=v.Controller(self.frozen,initial,'SHARED_EFT')
        a=old(None,queue,lanes,queue[0]['arrival_ns'],None,None,None)
        b=new(None,queue,lanes,queue[0]['arrival_ns'],None,None,None)
        self.assertEqual(a,{k:b[k] for k in a})
        self.assertEqual(old.seen,new.seen)
        future=copy.deepcopy(queue);future[0]['arrival_ns']+=1
        with self.assertRaisesRegex(ValueError,'future ticket'):new(None,future,lanes,queue[0]['arrival_ns'],None,None,None)

    def test_known_late_gpu_removed_only_with_immediate_on_time_alternative(self):
        initial={k:copy.deepcopy(self.initial_case['initial'][k]) for k in ('preload','preload_power_w')}
        request=dict(id='first',ordinal=0,task='classification',priority='urgent',arrival_ns=35000000000,deadline_offset_ns=1500000000)
        lanes={b:dict(request=None,phase=None,since=None,dispatch=None) for b in ('CPU','GPU')}
        old=v.q.Controller(self.frozen,initial,'QUEUE');new=v.Controller(self.frozen,initial,'QUEUE')
        self.assertTrue(old.legal([request],lanes,36.343)[1][1])
        mask=new.legal([request],lanes,36.343)[1]
        self.assertTrue(mask[0]);self.assertFalse(mask[1])
        # Both paths late: processing must remain possible, not expire work.
        later=new.legal([request],lanes,37.)[1]
        self.assertTrue(later[0]);self.assertTrue(later[1])
        shared=v.Controller(self.frozen,initial,'SHARED_EFT')
        np.testing.assert_array_equal(mask,shared.legal([request],lanes,36.343)[1])

    def test_idle_backlog_is_observation_not_reconstructed_cause(self):
        rows=[dict(arrival_ns=35e9,dispatch_ns=36e9,lane_available_ns=37e9),
              dict(arrival_ns=38e9,dispatch_ns=38e9,lane_available_ns=39e9)]
        gaps=d.idle_with_backlog(rows)
        self.assertEqual([(x['start_s'],x['end_s']) for x in gaps],[(35.,36.)])
        self.assertIsNone(gaps[0]['causal_WAIT_effect']);self.assertIsNone(gaps[0]['decision_reason'])

    def test_legacy_readout_retains_all_failures_and_update_zero(self):
        evidence=json.loads((d.BUNDLE/'legacy_readout.json').read_text())
        self.assertEqual(len(evidence['aggregates']),44)
        group=[x for x in evidence['aggregates'] if x['policy']=='SHARED_EFT']
        self.assertEqual(sum(x['service_success_cases'] for x in group),96)
        self.assertEqual(sum(x['planned_requests'] for x in group),12672)
        self.assertEqual(sum(x['update']==0 for x in evidence['selected']),2)
        self.assertTrue(all(x['decision_snapshot_available'] is False for x in evidence['representatives']))


class EntryTests(unittest.TestCase):
    def test_real_training_entry_and_exact_pause_resume_fixture(self):
        cfg=v.fixture_config()
        cfg.update(train=cfg['train']*2,updates=2,validation_updates=[1,2],
            expected=dict(training=2,validation=3,test=10,reference=4,smoke=0))
        with tempfile.TemporaryDirectory() as root,redirect_stdout(io.StringIO()),patch.object(v,'fixture_config',return_value=cfg):
            lock=Path(root)/'fixture.lock'
            full=v.Session(Path(root)/'full',fixture=True,lock=lock)
            self.assertEqual(full.execute(),'completed');self.assertEqual(sum(full.s['counts'].values()),19)
            part=v.Session(Path(root)/'part',fixture=True,lock=lock)
            self.assertEqual(part.execute(pause_after=3),'paused')
            self.assertEqual(part.s['update'],1)
            self.assertIsNotNone(part.s['optimizer'])
            resumed=v.Session(part.folder,v.durable.read_state(part.folder),lock=lock)
            self.assertEqual(resumed.execute(),'completed')
            self.assertEqual(resumed.s['update'],2)
            self.assertEqual(full.s['test_rows'],resumed.s['test_rows'])
            self.assertTrue(any(x['total_lateness_s']>0 for x in full.s['test_rows'] if x['family']=='queue'))
            self.assertEqual((full.folder/'QUEUE_seed101.json').read_bytes(),(part.folder/'QUEUE_seed101.json').read_bytes())
            self.assertEqual((full.folder/'paired_differences.csv').read_bytes(),(part.folder/'paired_differences.csv').read_bytes())
            notes=[json.loads(s) for s in (part.folder/'journal.jsonl').read_text().splitlines()]
            training=next(x for x in notes if x['stage']=='training')
            for key in ('energy_J','mean_costs','multipliers','returns_abs_mean','advantages_std','single_legal_decisions'):self.assertIn(key,training)
            with (part.folder/'paired_differences.csv').open(encoding='utf8',newline='') as f:
                self.assertEqual(set(x['stratum'] for x in __import__('csv').DictReader(f)),{'primary','overload_stress'})
            with self.assertRaises(ValueError):v.durable.read_state(part.folder)
            with self.assertRaises(FileExistsError):v.Session(part.folder,fixture=True,lock=lock)

    def test_budget_stops_between_test_policies_preserving_partial_results(self):
        with tempfile.TemporaryDirectory() as root,redirect_stdout(io.StringIO()):
            s=v.Session(Path(root)/'test-budget',fixture=True,lock=Path(root)/'lock')
            case=s.s['config']['test'][0]
            row=dict(planned=24)
            s.s.update(phase='test',freeze=[],refs={tuple(case):row},
                ref_ledgers={tuple(case):dict(ledger=[],decisions=[])})
            expired=[False];calls=[]
            def elapsed():return 781. if expired[0] else 0.
            def episode(*args):
                calls.append(args[1]);expired[0]=True
                return row,dict(ledger=[],decisions=[]),None,None
            with patch.object(s,'elapsed',side_effect=elapsed),patch.object(s,'episode',side_effect=episode):
                self.assertEqual(s.execute(),'budget_stopped')
            self.assertEqual(calls,['CPU_REFERENCE'])
            self.assertEqual(s.s['counts']['test'],1)
            self.assertEqual(len(s.s['test_rows']),1)
            receipt=json.loads((s.folder/json.loads((s.folder/'LATEST_RECEIPT.json').read_text())['file']).read_text())
            self.assertEqual(receipt['stop_reason']['type'],'ActiveBudgetExceeded')
            self.assertIsNone(receipt['original_error'])
            self.assertFalse(s.lock.exists())
            with self.assertRaises(ValueError):v.durable.read_state(s.folder)

    def test_budget_no_reset_partial_error_and_receipt_preserves_original(self):
        with tempfile.TemporaryDirectory() as root,redirect_stdout(io.StringIO()):
            s=v.Session(Path(root)/'budget',fixture=True,lock=Path(root)/'lock')
            s.s['config']['active_limit_s']=120
            self.assertEqual(s.execute(),'budget_stopped');self.assertEqual(s.s['counts']['training'],0)
            failed=v.Session(Path(root)/'failed',fixture=True,lock=Path(root)/'lock')
            original=v.q.atomic
            def fail(path,obj):
                if Path(path).name.startswith('RECEIPT_') and Path(path).name!='RECEIPT_ERROR.json':raise OSError('receipt fixture')
                original(path,obj)
            with patch.object(failed,'step',side_effect=TimeoutError('original fixture')),patch.object(v.q,'atomic',side_effect=fail):
                with self.assertRaisesRegex(TimeoutError,'original fixture'):failed.execute()
            evidence=json.loads((failed.folder/'RECEIPT_ERROR.json').read_text())
            self.assertEqual(evidence['original_error']['message'],'original fixture')
            self.assertFalse(failed.lock.exists())


if __name__=='__main__':unittest.main()
