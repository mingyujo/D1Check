"""Boundary tests for recombination and exact unchanged-PPO continuation."""
import copy
from contextlib import redirect_stdout
import io
from datetime import datetime,timedelta,timezone
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from tools import d1_rules_rl_common as common
from tools import d1_rule_recombination as rules
from tools import d1_rl_amount_campaign as amount
from tools import d1_queue_ppo_learning_amount as archive


class Tests(unittest.TestCase):
    def setup_folder(self,folder):
        common.atomic(folder/'campaign.json',dict(deadline_utc=(datetime.now(timezone.utc)+timedelta(hours=2)).isoformat(),
            limits=dict(recombination=4000,rl=80000,episodes_per_learner=8192)))
        common.atomic(folder/'rl_contract_before_run.json',dict(configuration={},sources={},runtime=amount.v.durable.Session.runtime()))

    def test_budget_charges_failed_and_replayed_execution(self):
        with tempfile.TemporaryDirectory() as t:
            folder=Path(t);self.setup_folder(folder);b=common.Budget(folder)
            with self.assertRaisesRegex(OSError,'fixture'):
                b.execute('rl','fixture',lambda:(_ for _ in ()).throw(OSError('fixture')))
            b.execute('rl','fixture_recovery',lambda:7)
            restored=common.Budget(folder)
            self.assertEqual(restored.counts['rl'],2);self.assertEqual(restored.pending,{})
            restored.plan['limits']['rl']=2
            with self.assertRaises(common.BudgetStop):restored.execute('rl','blocked',lambda:1)

    def test_first1024_and_extension_decision_do_not_use_test(self):
        original=amount.v.design.cases(amount.v.load_plan())[0]
        self.assertEqual(amount.training_cases(1024),original)
        learners={}
        for variant,seed in amount.IDENTITIES:
            learners[f'{variant}_{seed}']=dict(best_update=32,validation_history={str(i):dict(key=[0.,0.,0.,0.,0.,163.,400.,1000.]) for i in (416,448,480,512)})
        self.assertFalse(amount.extension_decision(learners)['extend'])
        learners['HEAD_11']['validation_history']['512']['key'][5]=162.9
        decision=amount.extension_decision(learners)
        self.assertTrue(decision['extend']);self.assertFalse(decision['final_test_opened'])
        learners['HEAD_11']['validation_history']['512']['key'][5]=163.1
        self.assertEqual(amount.extension_decision(learners)['learners'][0]['state'],'uncertain')

    def test_completion_can_recover_a_prefix_rejected_branch(self):
        frozen,case=rules.P.inputs(rules.P.BUNDLE);initial={k:case['initial'][k] for k in ('preload','preload_power_w')}
        qs=rules.small_tickets('CCD',101)
        c=rules.Controller(frozen,initial,rules.COMPLETE)
        # A controlled decision-state fixture: the first GPU prefix plus greedy
        # continuation is worse, while adding the second explicit assignment
        # changes the complete continuation and passes the identical guard.
        def score(jobs,now):
            first=jobs[0];second=jobs[1]
            bad=first['backend']=='GPU' and second['backend']=='CPU'
            return dict(remaining_energy_j=2. if bad else .5 if first['backend']=='GPU' else 1.,
                predicted_peak_ap_c=30.,future_rectified_AP_area_c_s=0.,deadline_misses=0,total_lateness_s=0.)
        c.score=score
        selected,_,log=c.search(qs,[],[],qs[0]['arrival_ns']/1e9,'CPU',rules.area.x.settings())
        self.assertGreater(log['missed_eligible_complete'],0)
        self.assertEqual(selected[0][1],'GPU')
        self.assertLessEqual(log['complete_candidates'],48)

    def test_real_small_cases_preserve_denominator_and_no_added_wait(self):
        frozen,case=rules.P.inputs(rules.P.BUNDLE);initial={k:case['initial'][k] for k in ('preload','preload_power_w')}
        budget=common.Budget();tickets=rules.small_tickets('CCD',610710001)
        for mode in (rules.PREFIX,rules.COMPLETE):
            row,result,c,_=budget.execute('recombination','fixture',lambda:rules.simulate(frozen,initial,tickets,'mean',mode))
            self.assertEqual(row['planned'],3);self.assertEqual(row['completed'],3)
            self.assertTrue(all(d.get('chosen_explicit_delay_s',0)==0 for d in result['decisions']))
            self.assertTrue(all(r['complete_candidates']<=48 for r in c.records if not r.get('unavailable')))
        budget.publish(stage='recombination_fixture')

    def test_exact_pause_resume_matches_unchanged_v2_optimizer_and_rng(self):
        # Counts for all real fixture simulations below are in the campaign
        # ledger, including the original runner's diagnostic final test.
        cfg=amount.v.fixture_config();cfg.update(train=cfg['train']*2,updates=2,validation_updates=[1,2],
            expected=dict(training=2,validation=3,test=10,reference=4,smoke=0))
        ours=dict(identities=[('QUEUE',101)],train=cfg['train'],validation=cfg['validation'],test=cfg['test'],
            batch=1,validation_period=1,milestones=[1,2],training_reserve_s=300)
        outer_budget=common.Budget();original_simulate=amount.v.simulate
        def counted(*args,**kwargs):
            return outer_budget.execute('rl','fixture_original_v2',lambda:original_simulate(*args,**kwargs))
        with tempfile.TemporaryDirectory() as t,redirect_stdout(io.StringIO()):
            root=Path(t)
            with patch.object(amount.v,'fixture_config',return_value=cfg),patch.object(amount.v,'simulate',side_effect=counted):
                old=archive.TerminalArchiveSession(root/'old',fixture=True,lock=root/'lock')
                self.assertEqual(old.execute(),'completed')
            outer_budget.fixture_annotation('fixture_original_v2',2,2,'completed unchanged-v2 fixture counts, executions already charged')
            outer_budget.publish(stage='rl_fixture_original')
            for name in ('full','part'):
                folder=root/name;self.setup_folder(folder)
            # Redirect new fixture accounting to the same durable outer ledger,
            # while keeping temporary output/learner states independent.
            with patch.object(amount.common,'Budget',return_value=outer_budget):
                full=amount.Session(root/'full',fixture_config=ours)
                self.assertEqual(full.execute(),'training_completed')
                part=amount.Session(root/'part',fixture_config=ours)
                self.assertEqual(part.execute(stop_after_units=2),'paused')
                resumed=amount.Session(root/'part',resume=True,fixture_config=ours)
                self.assertEqual(resumed.execute(),'training_completed')
            a=amount.v.torch.load(root/'old/terminal_QUEUE_seed101_update2.pt',weights_only=False)
            b=amount.v.torch.load(root/'full/rl/learners/QUEUE_101/terminal_update2.pt',weights_only=False)
            c=amount.v.torch.load(root/'part/rl/learners/QUEUE_101/terminal_update2.pt',weights_only=False)
            for candidate in (b,c):
                for key,value in a['network'].items():amount.v.torch.testing.assert_close(value,candidate['network'][key],rtol=0,atol=0)
                for key,values in a['optimizer']['state'].items():
                    for field,value in values.items():amount.v.torch.testing.assert_close(value,candidate['optimizer']['state'][key][field],rtol=0,atol=0)
                self.assertEqual(a['python_rng'],candidate['rng']['python'])
                amount.v.np.testing.assert_equal(a['numpy_rng'],candidate['rng']['numpy'])
                amount.v.torch.testing.assert_close(a['torch_rng'],candidate['rng']['torch'],rtol=0,atol=0)
                amount.v.np.testing.assert_equal(a['multipliers'],candidate['multipliers'])
            self.assertEqual((root/'full/rl/actors/QUEUE_101_2_best.json').read_bytes(),(root/'part/rl/actors/QUEUE_101_2_best.json').read_bytes())
        outer_budget.publish(stage='rl_fixture_completed')

    def test_storage_failure_after_archive_replays_from_previous_complete_state(self):
        cfg=amount.v.fixture_config()
        ours=dict(identities=[('QUEUE',101)],train=cfg['train']*2,validation=cfg['validation'],test=cfg['test'],
            batch=1,validation_period=1,milestones=[1,2],training_reserve_s=300)
        budget=common.Budget()
        with tempfile.TemporaryDirectory() as t,redirect_stdout(io.StringIO()):
            root=Path(t)
            for name in ('full','failed'):self.setup_folder(root/name)
            with patch.object(amount.common,'Budget',return_value=budget):
                full=amount.Session(root/'full',fixture_config=ours);self.assertEqual(full.execute(),'training_completed')
                failing=amount.Session(root/'failed',fixture_config=ours)
                with patch.object(amount.v.q,'save_actor',side_effect=OSError('fixture archive publication failure')):
                    with self.assertRaisesRegex(OSError,'publication'):failing.execute()
                state=common.read(root/'failed/rl/state.json')
                self.assertEqual(state['learners']['QUEUE_101']['update'],0)
                self.assertTrue((root/'failed/rl/learners/QUEUE_101/terminal_update1.pt').exists())
                recovered=amount.Session(root/'failed',resume=True,fixture_config=ours)
                self.assertEqual(recovered.execute(),'training_completed')
            a=amount.v.torch.load(root/'full/rl/learners/QUEUE_101/terminal_update2.pt',weights_only=False)
            b=amount.v.torch.load(root/'failed/rl/learners/QUEUE_101/terminal_update2.pt',weights_only=False)
            for key in ('network','optimizer','rng','multipliers','best_actor','best_update'):
                self.assertTrue(amount.exact_equal(a[key],b[key]),key)
        budget.publish(stage='storage_failure_fixture_completed')


if __name__=='__main__':unittest.main()
