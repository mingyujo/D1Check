import copy
import json
import shutil
import tempfile
import unittest
import gzip
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch
from tools import d1_reserved_thermal as rule
from tools import d1_reserved_thermal_study as study


class ReservationBookTests(unittest.TestCase):
    def job(self, rid, response=36., deadline=40., ready=False):
        return dict(id=rid, response=response, deadline=deadline, already_responded=ready)

    def test_caps_are_initial_completion_reservations_not_reissued_deadlines(self):
        b = rule.ReservationBook()
        b.admit(35., [self.job('a')], {'a'}, 180., 1.)
        self.assertEqual(b.caps['a'],36.)
        self.assertEqual(b.violations([self.job('a',37.)]),['a'])
        b.admit(35.2,[self.job('a',38.),self.job('b',37.)],{'b'},199.,.3)
        self.assertEqual(b.caps['a'],36.)
        self.assertAlmostEqual(b.budget_j,180.3)

    def test_same_request_cannot_receive_arrival_credit_twice(self):
        b = rule.ReservationBook()
        b.admit(35.,[self.job('a')],{'a'},10.,1.)
        with self.assertRaisesRegex(ValueError,'twice'):
            b.admit(35.1,[self.job('a')],{'a'},100.,10.)
        self.assertEqual(b.budget_j,10.)

    def test_negative_arrival_credit_is_not_clamped_and_prefix_spend_cannot_reset(self):
        b = rule.ReservationBook()
        b.admit(35.,[self.job('a')],{'a'},10.,1.)
        b.admit(35.1,[self.job('a'),self.job('b')],{'b'},999.,-.5)
        self.assertEqual(b.budget_j,9.5)
        self.assertFalse(b.accepts_energy(9.6))
        self.assertTrue(b.accepts_energy(9.5))

    def test_observed_response_and_breaks_preserve_original_caps(self):
        b = rule.ReservationBook(); b.admit(35.,[self.job('a')],{'a'},10.,0.)
        self.assertEqual(b.violations([self.job('a',45.,ready=True)]),[])
        b.broken(36.,'overrun',['a']); b.broken(37.,'overrun',['a'])
        self.assertEqual(len(b.breaks),1)
        self.assertEqual(b.caps['a'],36.)

    def test_unavailable_budget_disables_energy_admission(self):
        b = rule.ReservationBook(); b.admit(35.,[self.job('a')],{'a'},None,None)
        self.assertFalse(b.accepts_energy(0.))


class ControllerBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.frozen, case = rule.P.inputs(rule.P.BUNDLE)
        cls.initial = {k:case['initial'][k] for k in ('preload','preload_power_w')}
        cls.lanes = {b:dict(request=None,phase='AVAILABLE',since=0,dispatch=None) for b in ('CPU','GPU')}
        cls.q = study.fixture_tickets()[0][1][0]

    def controller(self):
        c = rule.Controller(self.frozen,self.initial)
        c.observe(35e9,self.lanes)
        return c

    def test_future_ticket_private_lane_and_observed_future_ap_are_blocked(self):
        c = self.controller()
        with self.assertRaisesRegex(ValueError,'future ticket'):
            c(None,[dict(self.q,arrival_ns=36e9)],self.lanes,35e9,rule.X.settings(),None,None)
        lanes=copy.deepcopy(self.lanes);lanes['CPU']['future_cost']=1
        with self.assertRaisesRegex(ValueError,'private lane'):
            c(None,[self.q],lanes,35e9,rule.X.settings(),None,None)
        a=self.controller();b=self.controller()
        first=a(None,[self.q],self.lanes,35e9,rule.X.settings(),None,None)
        second=b(None,[self.q],self.lanes,35e9,rule.X.settings(),None,999.)
        self.assertEqual(first,second)

    def test_budget_and_caps_do_not_reset_on_repeated_callback(self):
        c=self.controller()
        c(None,[self.q],self.lanes,35e9,rule.X.settings(),None,None)
        caps=copy.deepcopy(c.book.caps);budget=c.book.budget_j;n=len(c.book.transactions)
        c(None,[self.q],self.lanes,35e9,rule.X.settings(),None,None)
        self.assertEqual(c.book.caps,caps);self.assertEqual(c.book.budget_j,budget)
        self.assertEqual(len(c.book.transactions),n)
        self.assertTrue(all(r['expanded']<=64 and r['completed_calendar_before_veto'] for r in c.records))

    def test_busy_lane_is_not_released_at_predicted_completion(self):
        c=self.controller(); lanes=copy.deepcopy(self.lanes)
        lanes['GPU']=dict(request=self.q,phase='EXECUTING',since=35e9,dispatch=35e9)
        q=dict(self.q,id='new',ordinal=1,arrival_ns=35.8e9)
        c.observe(36e9,lanes)
        result=c(None,[q],lanes,36e9,rule.X.settings(),None,None)
        self.assertIsNone(result['selected'])
        self.assertTrue(c.book.breaks)

    def test_expansion_keeps_rejected_prefix_for_completed_descendant(self):
        c=self.controller()
        q2=dict(self.q,id='second',ordinal=1,task='detection',priority='normal',deadline_offset_ns=6e9)
        original=c._evaluate
        def evaluator(sequence,*args):
            item=original(sequence,*args)
            if len(sequence)==1:item['reasons']=['energy_budget_rejection']
            else:item['reasons']=[]
            return item
        c._evaluate=evaluator
        c(None,[self.q,q2],self.lanes,35e9,rule.X.settings(),None,None)
        self.assertTrue(any(len(x['sequence'])==2 for x in c.records[-1]['candidates']))
        self.assertGreater(c.records[-1]['admitted'],0)

    def test_no_unregistered_environment(self):
        with self.assertRaisesRegex(ValueError,'budget'):
            rule.simulate(self.frozen,self.initial,[self.q],'mean',None)

    def test_observed_response_breach_is_recorded_without_relaxing_cap(self):
        c=self.controller()
        job=dict(id=self.q['id'],response=36.,deadline=36.5,already_responded=False)
        c.book.admit(35.,[job],{self.q['id']},200.,0.)
        lanes=copy.deepcopy(self.lanes)
        lanes['GPU']=dict(request=self.q,phase='OUTPUT_READY',since=37e9,dispatch=35e9)
        c.observe(37e9,lanes)
        self.assertEqual(c.book.caps[self.q['id']],36.)
        self.assertIn('reservation_observed_violation',[e['reason'] for e in c.book.breaks])

    def test_running_energy_is_observed_prefix_not_a_new_remaining_budget(self):
        c=self.controller()
        lanes=copy.deepcopy(self.lanes)
        lanes['GPU']=dict(request=self.q,phase='EXECUTING',since=35e9,dispatch=35e9)
        c.observe(35e9,lanes);c.observe(35.1e9,lanes)
        expected=35.1*self.initial['preload_power_w']+.1*self.frozen['energy_increment_w']['classification_GPU']
        self.assertAlmostEqual(c.observed_j,expected,places=9)

    def saved_jobs(self):
        c=self.controller()
        q0=dict(self.q,id='saved/a',task='detection',priority='normal',deadline_offset_ns=6e9)
        q1=dict(q0,id='saved/b',ordinal=1)
        a=c.place(q0,'CPU',35.1,[])
        b=c.place(q1,'CPU',a['end']+.25,[a])
        c.book.calendar=[a,b]
        return c,[q0,q1],[a,b]

    def test_retained_all_absolute_starts_and_cost_survive_repeated_callbacks(self):
        c,queue,saved=self.saved_jobs()
        for now in (35.,35.05,35.08):
            c.observe(now*1e9,self.lanes)
            seq=c._retained_sequence(queue,now)
            jobs,first,changes=c.finish_retained(seq,queue,[],now,c)
            self.assertEqual([j['start'] for j in jobs],[j['start'] for j in saved])
            self.assertEqual(changes,[])
            cost=c.plan_score(jobs,now)['predicted_total_j']
            if now==35.: first_cost=cost
            self.assertAlmostEqual(cost,first_cost,places=9)

    def test_retained_gap_survives_earlier_actual_release(self):
        c,queue,saved=self.saved_jobs()
        blocker=dict(saved[0],id='active',start=35.,end=35.05,response=35.04,already_responded=True)
        seq=c._retained_sequence(queue,35.)
        jobs,_,_=c.finish_retained(seq,queue,[blocker],35.,c)
        self.assertEqual([j['start'] for j in jobs if j['id']!='active'],[j['start'] for j in saved])
        c.observe(35.05e9,self.lanes)
        jobs,_,_=c.finish_retained(c._retained_sequence(queue,35.05),queue,[],35.05,c)
        self.assertEqual([j['start'] for j in jobs],[j['start'] for j in saved])

    def test_late_release_shifts_retained_and_long_guard_keeps_original_caps(self):
        c,queue,saved=self.saved_jobs()
        seq=c._retained_sequence(queue,35.)
        blocker=dict(saved[0],id='active',start=35.,end=35.2,response=35.1,already_responded=True)
        c.book.admit(35.,saved,{q['id'] for q in queue},1000.,0.)
        before=copy.deepcopy(c.book.caps)
        item=c._evaluate(seq,queue,[blocker],[blocker],35.,{queue[0]['id']},True)
        self.assertIn('retained_conflict_shift',item['calendar_changes'])
        self.assertIn('reservation_predicted_violation',item['reasons'])
        self.assertEqual(c.book.caps,before)

    def test_new_arrival_is_added_without_erasing_saved_bounds(self):
        c,queue,saved=self.saved_jobs()
        new=dict(self.q,id='new',ordinal=2)
        jobs,_,_=c.finish_retained(c._retained_sequence(queue+[new],35.),queue+[new],[],35.,c)
        self.assertEqual({j['id'] for j in jobs},{q['id'] for q in queue+[new]})
        self.assertTrue(all(j['start']>=old['start'] for j,old in zip(jobs,saved)))

    def test_expired_retained_plan_is_logged_instead_of_silently_retimed(self):
        c,queue,_=self.saved_jobs()
        self.assertIsNone(c._retained_sequence(queue,35.2))
        self.assertEqual(c.book.breaks[-1]['reason'],'retained_calendar_expired')

    def test_retained_intentional_wait_limit_is_not_extended(self):
        c,queue,saved=self.saved_jobs()
        saved[0]['start']=38.;saved[1]['start']=39.
        jobs,_,errors=c.finish_retained(c._retained_sequence(queue,35.),queue,[],35.,c)
        self.assertIn('retained_wait_limit',errors)

    def test_output_ready_active_lane_still_blocks_retained_calendar(self):
        c,queue,_=self.saved_jobs()
        lanes=copy.deepcopy(self.lanes)
        lanes['CPU']=dict(request=queue[0],phase='PERSISTED',since=35.05e9,dispatch=35e9)
        active=c.active_jobs(lanes,35.05)
        self.assertTrue(active[0]['already_responded'])
        jobs,_,_=c.finish_retained(c._retained_sequence(queue[1:],35.05),queue[1:],active,35.05,c)
        self.assertGreaterEqual(jobs[-1]['start'],active[0]['end'])

    def test_no_arrival_fixed_calendar_prefix_plus_tail_energy_is_conserved(self):
        c=self.controller()
        q=dict(self.q,task='detection',priority='normal',deadline_offset_ns=6e9)
        job=c.place(q,'CPU',35.2,[])
        expected=c.plan_score([job],35.)['predicted_total_j']
        c.observe(35.2e9,self.lanes)
        lanes=copy.deepcopy(self.lanes)
        lanes['CPU']=dict(request=q,phase='EXECUTING',since=35.2e9,dispatch=35.2e9)
        c.observe(35.2e9,lanes);c.observe(35.4e9,lanes)
        remaining=c.active_jobs(lanes,35.4)
        self.assertAlmostEqual(c.plan_score(remaining,35.4)['predicted_total_j'],expected,places=8)
        c.observe(job['end']*1e9,self.lanes)
        self.assertAlmostEqual(c.plan_score([],job['end'])['predicted_total_j'],expected,places=8)

    def test_pending_arrival_first_seen_is_preserved_until_unknown_overrun_ends(self):
        c=self.controller();lanes=copy.deepcopy(self.lanes)
        lanes['GPU']=dict(request=self.q,phase='EXECUTING',since=35e9,dispatch=35e9)
        q=dict(self.q,id='new',ordinal=1,arrival_ns=36e9)
        c.observe(36e9,lanes)
        c(None,[q],lanes,36e9,rule.X.settings(),None,None)
        self.assertEqual(c.book.pending[q['id']],36.)
        self.assertNotIn(q['id'],c.book.issued)
        c.observe(36.1e9,self.lanes)
        c(None,[q],self.lanes,36.1e9,rule.X.settings(),None,None)
        self.assertEqual(c.book.transactions[-1]['first_seen_s'][q['id']],36.)
        self.assertEqual(c.book.transactions[-1]['now_s'],36.1)
        self.assertNotIn(q['id'],c.book.pending)

    def test_signed_arrival_credit_uses_same_snapshot_and_does_not_reset_spend(self):
        # Instrumented cost values test the book equation, not physical gains.
        for delta in (1.,-.5):
            c=self.controller();q0=self.q;q1=dict(q0,id='credit/new',ordinal=1)
            c.book.admit(35.,[dict(id=q0['id'],deadline=36.5,response=36.)],{q0['id']},180.,0.)
            scores=[dict(predicted_total_j=999.,remaining_energy_j=100.+delta),
                    dict(predicted_total_j=998.,remaining_energy_j=100.)]
            with (patch.object(c,'plan_score',side_effect=scores) as scorer,
                  patch.object(c,'search',return_value=(None,dict(candidates=[])))):
                c(None,[q0,q1],self.lanes,35e9,rule.X.settings(),None,None)
            self.assertEqual([call.args[1] for call in scorer.call_args_list],[35.,35.])
            self.assertEqual(c.book.budget_j,180.+delta)
            self.assertEqual(c.book.transactions[-1]['signed_arrival_credit_j'],delta)

    def test_empty_queue_overrun_and_terminal_energy_debt_remain_visible(self):
        c=self.controller();c.book.budget_j=1.
        lanes=copy.deepcopy(self.lanes)
        lanes['GPU']=dict(request=self.q,phase='EXECUTING',since=35e9,dispatch=35e9)
        c.observe(36e9,lanes)
        self.assertIn('observed_overrun',[e['reason'] for e in c.book.breaks])
        row=dict(energy_j=2.,completed=0,planned=1)
        c.terminal_audit(row,dict(ledger=[]))
        self.assertEqual(row['final_budget_j'],1.)
        self.assertEqual(row['final_budget_margin_j'],-1.)
        self.assertFalse(row['final_budget_satisfied'])
        self.assertTrue(row['final_energy_partial_work'])

    def test_realized_cap_failure_and_service_deadline_failure_are_distinct(self):
        c=self.controller();c.book.admit(35.,[dict(id='a',deadline=36.5,response=35.1)],{'a'},200.,0.)
        result=dict(ledger=[dict(id='a',arrival_ns=35e9,response_ns=.2e9)])
        row=dict(energy_j=100.,planned=1,completed=1,deadline_met=1)
        c.terminal_audit(row,result)
        self.assertEqual(row['observed_cap_violation_requests'],1)
        self.assertEqual(row['deadline_met'],1)
        self.assertTrue(row['final_budget_satisfied'])


class RegistrationAndPilotTests(unittest.TestCase):
    def test_missing_local_state_does_not_recreate_existing_campaign_budget(self):
        with tempfile.TemporaryDirectory() as folder:
            local=Path(folder)/'local';bundle=Path(folder)/'bundle';bundle.mkdir()
            shutil.copyfile(study.LOCAL/'campaign.json',bundle/'campaign.json')
            with patch.object(study,'LOCAL',local),patch.object(study,'BUNDLE',bundle):
                with self.assertRaisesRegex(RuntimeError,'cannot be recreated'):
                    study.prepare()
                self.assertFalse((local/'campaign.json').exists())

    def test_registration_cannot_change_an_owned_campaign(self):
        with tempfile.TemporaryDirectory() as folder:
            local=Path(folder);(local/'owner.json').write_text('{"pid":123}',encoding='utf8')
            with patch.object(study,'LOCAL',local):
                with self.assertRaisesRegex(RuntimeError,'owner'):
                    study.prepare()
                self.assertTrue((local/'owner.json').exists())

    def test_gate_missing_revise_hash_drift_and_matching_permit_are_isolated(self):
        before=study.consumption()
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'review.json';sources={'test':'hash'};design={'test':'design'}
            with self.assertRaisesRegex(RuntimeError,'review missing'):
                study.require_review(path,sources,design)
            def put(decision,hashes=sources):
                path.write_text(json.dumps(dict(decision=decision,source_hashes=hashes,design=design)),encoding='utf8')
            put('REVISE_BEFORE_RUN')
            with self.assertRaisesRegex(RuntimeError,'does not permit'):
                study.require_review(path,sources,design)
            put('PROCEED_PILOT',{'wrong':'hash'})
            with self.assertRaisesRegex(RuntimeError,'does not match'):
                study.require_review(path,sources,design)
            put('PROCEED_PILOT')
            self.assertEqual(study.require_review(path,sources,design)['decision'],'PROCEED_PILOT')
        self.assertEqual(study.consumption(),before)

    def test_authorized_design_revision_keeps_campaign_bytes_consumption_and_rejects_rollback(self):
        with tempfile.TemporaryDirectory() as folder:
            local=Path(folder)/'local';bundle=Path(folder)/'bundle'
            local.mkdir();bundle.mkdir()
            for name in ('campaign.json','executions.jsonl'):
                shutil.copyfile(study.LOCAL/name,local/name)
            (local/'registrations').mkdir()
            for number in (1,2,3):
                shutil.copyfile(study.LOCAL/f'registrations/{number:03d}.json',local/f'registrations/{number:03d}.json')
            shutil.copyfile(local/'registrations/003.json',local/'active_registration.json')
            for name in ('astra_review.json','ASTRA_REVIEW.md'):
                shutil.copyfile(study.BUNDLE/name,bundle/name)
            original=(local/'campaign.json').read_bytes()
            with patch.object(study,'LOCAL',local),patch.object(study,'BUNDLE',bundle):
                before=study.consumption();prepared=study.prepare()
                self.assertEqual(prepared['consumption'],before)
                self.assertEqual((local/'campaign.json').read_bytes(),original)
                self.assertEqual(prepared['registration']['design_revision'],2)
                prepared_again=study.prepare()
                self.assertEqual(prepared_again['registration'],prepared['registration'])
                shutil.copyfile(local/'registrations/003.json',local/'active_registration.json')
                with self.assertRaisesRegex(ValueError,'rollback|drift'):
                    study.check()

    def test_core_equation_change_is_not_an_authorized_repair(self):
        old=study.read(study.LOCAL/'campaign.json')['design']
        changed=dict(rule.specification(),energy_arrival='reset budget to latest EFT')
        with self.assertRaisesRegex(ValueError,'outside reviewed'):
            study.validate_repair_design(old,changed)

    def test_completed_reference_432_rows_cover_same_48_conditions(self):
        before=study.consumption()
        inputs,jobs,rows,evidence=study.reference_rows()
        self.assertEqual(len(jobs),48);self.assertEqual(len(rows),432)
        self.assertEqual(len(evidence['policies']),9)
        self.assertTrue(all('reuse_file_sha256' in row for row in rows))
        self.assertEqual(study.consumption(),before)

    def test_pilot_entry_with_rejected_review_never_starts_environment(self):
        with (patch.object(study,'check'),patch.object(study,'require_review',side_effect=RuntimeError('rejected')),
              patch.object(study,'begin_environment') as begin):
            with self.assertRaisesRegex(RuntimeError,'rejected'):
                study.run_pilot()
            begin.assert_not_called()

    def test_pilot_source_revision_before_results_is_preserved_and_frozen_after_start(self):
        with tempfile.TemporaryDirectory() as folder:
            local=Path(folder)/'local';bundle=Path(folder)/'bundle';local.mkdir();bundle.mkdir()
            with (patch.object(study,'LOCAL',local),patch.object(study,'BUNDLE',bundle),
                  patch.object(study,'check'),patch.object(study,'source_hashes',return_value={'source':'A'}) as hashes):
                first=study.prepare_pilot()
                hashes.return_value={'source':'B'}
                second=study.prepare_pilot()
                self.assertNotEqual(first['source_hashes'],second['source_hashes'])
                self.assertEqual(study.read(local/'pilot_registrations/001.json')['manifest'],first)
                self.assertEqual(study.read(local/'pilot_registrations/002.json')['manifest'],second)
                (local/'executions.jsonl').write_text(json.dumps(dict(event='start',kind='pilot'))+'\n',encoding='utf8')
                hashes.return_value={'source':'C'}
                with self.assertRaisesRegex(ValueError,'cannot change'):
                    study.prepare_pilot()
                self.assertEqual(study.read(local/'pilot_manifest.json'),second)

    def test_pilot_driver_saves_48_items_resumes_without_execution_and_rejects_changed_cache(self):
        # Mock engine/accounting here: verifies I/O and reuse, not policy performance.
        with tempfile.TemporaryDirectory() as folder:
            local=Path(folder)/'local';bundle=Path(folder)/'bundle'
            local.mkdir();bundle.mkdir();(local/'pilot_manifest.json').write_text('{}',encoding='utf8')
            jobs=[(dict(seed=100+i,family='fixture',tickets=[]),'mean') for i in range(48)]
            inputs=dict(initial={});reused=[dict(policy='fixture_reuse',planned=0) for _ in range(432)]
            fake=SimpleNamespace(records=[],book=study.rule.ReservationBook())
            returned=lambda *args:(dict(policy=rule.PUBLIC_POLICY,planned=0),dict(ledger=[],decisions=[]),fake,None)
            with (patch.object(study,'LOCAL',local),patch.object(study,'BUNDLE',bundle),
                  patch.object(study,'check'),patch.object(study,'require_review'),
                  patch.object(study,'prepare_pilot',return_value={}),
                  patch.object(study,'reference_rows',return_value=(inputs,jobs,reused,{})),
                  patch.object(study,'source_hashes',return_value={'fixture':'unchanged'}),
                  patch.object(rule.P,'inputs',return_value=({},{})),
                  patch.object(rule,'simulate',side_effect=returned) as simulated,
                  patch.object(study,'begin_environment',side_effect=range(1,49)) as started,
                  patch.object(study.existing,'metrics',return_value=({},{}))):
                result=study.run_pilot()
                self.assertEqual(result['rows'],480)
                self.assertEqual(simulated.call_count,48);self.assertEqual(started.call_count,48)
                simulated.reset_mock();started.reset_mock()
                self.assertEqual(study.run_pilot()['rows'],480)
                simulated.assert_not_called();started.assert_not_called()
                path=local/'pilot_items/0000.json.gz'
                item=json.loads(gzip.open(path,'rt',encoding='utf8').read())
                item['row']['planned']=1
                path.write_bytes(gzip.compress(json.dumps(item).encode('utf8')))
                with self.assertRaisesRegex(ValueError,'receipt mismatch'):
                    study.run_pilot()
                simulated.assert_not_called();started.assert_not_called()


class EngineFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixtures=study.run_fixtures()

    def test_every_planned_request_completes_and_lanes_release_without_collision(self):
        for item in self.fixtures.values():
            result=item['result'];tickets=item['tickets'];rows=result['ledger']
            self.assertEqual({q['id'] for q in tickets},{r['id'] for r in rows})
            self.assertEqual(item['row']['completed'],len(tickets))
            for r in rows:
                self.assertLessEqual(r['response_ns'],r['deadline_offset_ns'])
                self.assertLessEqual(r['lane_available_ns'],120e9)
                self.assertLessEqual(r['output_ready_ns'],r['lane_available_ns'])
            for backend in ('CPU','GPU'):
                intervals=sorted((r['dispatch_ns'],r['lane_available_ns']) for r in rows if r['backend']==backend)
                self.assertTrue(all(a[1]<=b[0]+1 for a,b in zip(intervals,intervals[1:])))

    def test_future_suffix_does_not_change_first_decision(self):
        a=[d for d in self.fixtures['suffix_a']['result']['decisions'] if d['now_ns']<36e9]
        b=[d for d in self.fixtures['suffix_b']['result']['decisions'] if d['now_ns']<36e9]
        self.assertEqual(a,b)
        self.assertGreater(len(a),1)

    def test_selected_predictions_respect_persistent_budget_and_caps(self):
        for item in self.fixtures.values():
            for record in item['records']:
                if record['selected']!='EFT_fallback':
                    self.assertLessEqual(record['selected_total_j'],record['budget_j']+rule.EPS)
            initial_caps={}
            for transaction in item['transactions']:
                for rid,cap in transaction['issued_caps'].items():
                    self.assertNotIn(rid,initial_caps)
                    initial_caps[rid]=cap

    def test_observed_energy_reconciles_with_public_state_history(self):
        frozen,_=rule.P.inputs(rule.P.BUNDLE)
        for item in self.fixtures.values():
            expected=min(120.,item['observed_at_s'])*ControllerBoundaryTests.initial['preload_power_w']
            expected+=sum(max(0.,min(120.,s['end_s'])-s['start_s'])*
                (0. if s['state']=='idle' else frozen['energy_increment_w'][s['state']])
                for s in item['history'])
            self.assertAlmostEqual(item['observed_j'],expected,places=8)

    def test_terminal_full_window_cost_and_overrun_debt_are_reported(self):
        for item in self.fixtures.values():
            row=item['row']
            self.assertEqual(row['final_common_window_j'],row['energy_j'])
            self.assertAlmostEqual(row['final_budget_margin_j'],row['final_budget_j']-row['energy_j'])
            self.assertTrue(row['final_full_work'])
            self.assertFalse(row['final_energy_partial_work'])
        row=self.fixtures['overrun']['row']
        self.assertFalse(row['final_budget_satisfied'])
        self.assertGreater(row['terminal_energy_budget_exceeded_events'],0)


if __name__=='__main__':
    unittest.main()
