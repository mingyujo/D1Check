import copy
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import d1_queue_ppo_evaluate as e


class EvaluationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.root=Path(cls.tmp.name)
        cls.lock=cls.root/'owner';cls.plan_file=cls.root/'eval_plan.json'
        with redirect_stdout(io.StringIO()):
            original=e.v.Session(cls.root/'source',fixture=True,lock=cls.lock)
        cases=[(301,'low','mean'),(302,'low','mean'),(303,'low','mean')]
        original.s['config']['test']=cases
        net=e.v.q.ActorCritic();actor_path=original.folder/'QUEUE_seed101.json';e.v.q.save_actor(actor_path,net)
        actor=dict(variant='QUEUE',seed=101,update=0,eligible=False,filename=actor_path.name,sha256=e.v.q.p.digest(actor_path))
        rows=[];ledgers=[];ref=None;ref_ledger=None
        for policy in original.s['plan']['baselines']+['QUEUE_seed101']:
            row,result,_,_=e.v.simulate(original.s['frozen'],original.s['initial'],e.v.q.old.workload('low',301),
                'mean','QUEUE' if policy=='QUEUE_seed101' else policy,net if policy=='QUEUE_seed101' else None,True)
            rows.append(dict(trace_seed=301,family='low',context='mean',policy=policy,**row))
            ledgers.append(dict(case=cases[0],policy=policy,ledger=result['ledger'],decisions=result.get('decisions')))
            if policy=='SHARED_EFT':ref=row;ref_ledger=result
        original.s.update(status='budget_stopped',phase='test',test_index=1,freeze=[actor],
            test_rows=rows,test_ledgers=ledgers,refs={cases[0]:ref},ref_ledgers={cases[0]:ref_ledger},
            validation_rows=[dict(fixture_only=True)],
            counts=dict(training=0,validation=0,test=5,reference=1,smoke=0))
        original.save();cls.lock.unlink()
        e.v.q.atomic(original.folder/'freeze_before_test.json',dict(selected=[actor],test_started=False))
        e.v.q.atomic(original.folder/'source_receipt.json',dict(status='budget_stopped',phase='test',
            counts=original.s['counts'],original_error=None))
        e.v.q.atomic(original.folder/'LATEST_RECEIPT.json',dict(file='source_receipt.json',status='budget_stopped'))
        meta=json.loads((original.folder/'checkpoint.json').read_text())
        files=['checkpoint.json',meta['file'],'run_manifest.json','LATEST_RECEIPT.json','source_receipt.json',
            'freeze_before_test.json',actor_path.name]
        cls.plan=dict(version=e.VERSION,source_output=str(original.folder),source_files={f:e.v.q.p.digest(original.folder/f) for f in files},
            source_counts=original.s['counts'],actors=[actor],completed_cases=1,total_cases=3,
            remaining_cases=[list(c) for c in cases[1:]],training_updates=0,device_commands=0,runner_sources={},
            budget=dict(test=10,reference=2,simulations=12,active_limit_s=900,receipt_reserve_s=120,retries=0))
        cls.plan_file.write_text(json.dumps(cls.plan),encoding='utf8');cls.source=original

    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()

    def setUp(self):
        self.patches=[patch.object(e,'PLAN',self.plan_file),patch.object(e.v.q,'LOCK',self.lock),
            patch.object(e,'claim_path',return_value=self.root/'unused_claim')]
        for p in self.patches:p.start();self.addCleanup(p.stop)

    def test_check_has_no_simulation_optimizer_output_or_claim(self):
        before=set(self.root.iterdir())
        with (patch.object(e.v,'simulate',side_effect=AssertionError('no simulation')),
                patch.object(e.v.q.prev,'optimize',side_effect=AssertionError('no optimizer'))):
            result=e.check(self.root/'not_started')
        self.assertEqual(result['remaining_cases'],2);self.assertEqual(result['policy_simulations'],0)
        self.assertEqual(before,set(self.root.iterdir()));self.assertFalse(e.claim_path().exists())

    def test_frozen_suffix_only_pause_resume_and_complete_denominator(self):
        calls=[];simulate=e.v.simulate
        def tracked(*args,**kwargs):
            calls.append(args[2][0]['id'].split('/')[0]);return simulate(*args,**kwargs)
        with (redirect_stdout(io.StringIO()),patch.object(e.v,'simulate',side_effect=tracked),
                patch.object(e.v.q.prev,'optimize',side_effect=AssertionError('evaluation cannot train'))):
            full=e.Session(self.root/'full',fixture=True);self.assertEqual(full.execute(),'completed')
            part=e.Session(self.root/'part',fixture=True);self.assertEqual(part.execute(pause_after=1),'paused')
            resumed=e.Session(part.folder,resume=True,fixture=True);self.assertEqual(resumed.execute(),'completed')
        self.assertEqual(set(calls),{'302','303'});self.assertEqual(len(calls),24)
        self.assertEqual((full.folder/'test.csv').read_bytes(),(part.folder/'test.csv').read_bytes())
        self.assertEqual((full.folder/'paired_differences.csv').read_bytes(),(part.folder/'paired_differences.csv').read_bytes())
        summary=json.loads((full.folder/'summary.json').read_text())
        self.assertEqual(summary['table_rows'],18);self.assertEqual(summary['original_run_status'],'budget_stopped')
        self.assertEqual(summary['training_updates'],0)
        self.assertLess((part.folder/'state_0.json').stat().st_size,10000)
        for name,sha in self.plan['source_files'].items():self.assertEqual(e.v.q.p.digest(self.source.folder/name),sha)
        with self.assertRaises(ValueError):e.Session(part.folder,resume=True,fixture=True)
        with self.assertRaises(ValueError):e.Session(full.folder,fixture=True)

    def test_budget_inside_case_preserves_partial_and_refuses_resume(self):
        with redirect_stdout(io.StringIO()):s=e.Session(self.root/'budget',fixture=True)
        expired=[False]
        def fake(*args):
            expired[0]=True
            row={k:value for k,value in self.source.s['test_rows'][0].items() if k not in ('trace_seed','family','context','policy')}
            return row,dict(ledger=[],decisions=[]),None,None
        with (redirect_stdout(io.StringIO()),patch.object(s,'elapsed',side_effect=lambda:781. if expired[0] else 0.),
                patch.object(e.v,'simulate',side_effect=fake) as mock):
            self.assertEqual(s.execute(),'budget_stopped')
        self.assertEqual(mock.call_count,1);self.assertEqual(s.s['cursor'],0)
        self.assertEqual(len(json.loads((s.folder/'PARTIAL_CASE.json').read_text())['rows']),1)
        with self.assertRaises(ValueError):e.Session(s.folder,resume=True,fixture=True)
        self.assertFalse(self.lock.exists())

    def test_original_error_and_receipt_failure_are_separate(self):
        with redirect_stdout(io.StringIO()):s=e.Session(self.root/'failed',fixture=True)
        atomic=e.v.q.atomic
        def fail(path,value):
            if Path(path).name.startswith('RECEIPT_') and Path(path).name!='RECEIPT_ERROR.json':raise OSError('receipt failed')
            atomic(path,value)
        with (redirect_stdout(io.StringIO()),patch.object(s,'step',side_effect=RuntimeError('original failure')),
                patch.object(e.v.q,'atomic',side_effect=fail)):
            with self.assertRaisesRegex(RuntimeError,'original failure'):s.execute()
        record=json.loads((s.folder/'RECEIPT_ERROR.json').read_text())
        self.assertEqual(record['original_error']['message'],'original failure')
        self.assertIn('receipt failed',record['receipt_error']);self.assertFalse(self.lock.exists())

    def test_actor_source_and_partial_prefix_tampering_are_blocked(self):
        plan=copy.deepcopy(self.plan);plan['source_files'][plan['actors'][0]['filename']]='0'*64
        with self.assertRaisesRegex(ValueError,'sealed source'):e.load_source(plan)
        plan=copy.deepcopy(self.plan);plan['completed_cases']=0
        with self.assertRaisesRegex(ValueError,'complete, unique'):e.load_source(plan)


if __name__=='__main__':unittest.main()
