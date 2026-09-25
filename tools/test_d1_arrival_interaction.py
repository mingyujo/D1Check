"""REPLAN-PC-01 functional risks; synthetic ns, not device/native validation."""
import copy
import unittest
from unittest.mock import patch

from tools import d1_arrival_explore as old
from tools import d1_arrival_interaction as new
from tools.test_d1_cal03_connection import fixture, request
from tools.test_d1_arrival_explore import settings


class InteractionTest(unittest.TestCase):
    def run_case(self, requests, events=(), *, obs=200, drain=200, idle=15, enabled=True,
                 restrict=True, vectors=None, **kwargs):
        c,v=fixture()
        return new.simulate(c, vectors or v, requests,
            [dict(id=f'op{i}',at_ns=t) for i,t in enumerate(events)],
            settings=settings(**kwargs),seed=7,observation_end_ns=obs,drain_ns=drain,
            restrict_background=restrict,idle_ns=idle,enabled=enabled)

    def test_disabled_preserves_legacy_full_execution(self):
        qs=[request(priority='normal'),request('u',arrival=5,ordinal=1)]
        c,v=fixture();s=settings(decision_ns=2,record_ns=3,dispatch_ns=5)
        a=old.simulate(c,v,qs,policy='B2_PC',settings=s,seed=7,horizon_ns=400)
        b=self.run_case(qs,[0,30],enabled=False,decision_ns=2,record_ns=3,dispatch_ns=5)
        for k in ('ledger','decisions','transitions','metrics','settings'):
            self.assertEqual(a[k],b[k],k)
        self.assertEqual(a['policy'],b['engine_policy'])
        self.assertEqual(b['interaction_events'],[])

    def test_no_interaction_reuses_execution(self):
        qs=[request(priority='normal'),request('u',arrival=5,ordinal=1)]
        for costs in ({},dict(decision_ns=2,record_ns=3,dispatch_ns=5)):
            a=self.run_case(qs,restrict=False,**costs);b=self.run_case(qs,**costs)
            self.assertEqual(a['ledger'],b['ledger'])
            self.assertEqual(a['metrics'],b['metrics'])

    def test_before_exact_after_expiry(self):
        for arrival,expected in [(14,15),(15,15),(16,16)]:
            with self.subTest(arrival=arrival):
                out=self.run_case([request(priority='normal',arrival=arrival)],[0])
                self.assertEqual(out['ledger'][0]['dispatch_ns'],expected)

    def test_reset_and_stale_expiry_no_new_decision(self):
        out=self.run_case([request(priority='normal')],[0,10])
        self.assertEqual(out['ledger'][0]['dispatch_ns'],25)
        self.assertIn(dict(event='stale_expiry_ignored',at_ns=15,generation=1),out['interaction_events'])
        self.assertFalse(any(d['now_ns']==15 for d in out['decisions']))

    def test_interaction_beats_same_time_expiry(self):
        out=self.run_case([request(priority='normal')],[0,15])
        self.assertEqual(out['ledger'][0]['dispatch_ns'],30)
        at15=[e['event'] for e in out['interaction_events'] if e['at_ns']==15]
        self.assertEqual(at15,['interaction','stale_expiry_ignored'])

    def test_decision_in_flight_cancel_retains_queue_and_spent_cost(self):
        qs=[request('n',priority='normal'),request('u',arrival=5,ordinal=1)]
        out=self.run_case(qs,[5],decision_ns=10,record_ns=2,dispatch_ns=3)
        cancel=out['dispatch_gate_checks'][0]
        self.assertFalse(cancel['allowed']);self.assertEqual(cancel['spent_scheduler_ns'],15)
        self.assertTrue(cancel['queue_retained']);self.assertFalse(cancel['lane_acquired'])
        n,u=out['ledger'];self.assertEqual((n['queue_entry_ns'],n['ordinal']),(0,0))
        # No-selection calculation at P=90 occupies scheduler until102; L=100
        # does not erase the remaining2ns. New15ns decision dispatches at117.
        self.assertEqual(u['dispatch_ns'],30);self.assertEqual(n['dispatch_ns'],117)
        self.assertEqual(out['cancelled_dispatches'],1)

    def test_interaction_at_dispatch_cancels_but_after_dispatch_does_not(self):
        for at,expected in [(9,34),(10,35),(11,10)]:
            with self.subTest(at=at):
                out=self.run_case([request(priority='normal')],[at],decision_ns=10)
                self.assertEqual(out['ledger'][0]['dispatch_ns'],expected)

    def test_running_request_finishes_and_lane_not_released_at_output_or_persist(self):
        out=self.run_case([request('n1',priority='normal'),request('n2',priority='normal',arrival=1,ordinal=1)],[1])
        a,b=out['ledger']
        self.assertEqual([a[k] for k in ('dispatch_ns','output_ready_ns','persist_complete_ns','worker_release_ns','lane_available_ns')],[0,30,60,64,70])
        self.assertEqual(b['dispatch_ns'],70)

    def test_urgent_exempt_task_not_equal_priority(self):
        urgent=request('det',arrival=1,ordinal=1);urgent['task']='detection'
        out=self.run_case([request('cls',priority='normal'),urgent],[0],static_parallel=False)
        n,u=out['ledger'];self.assertEqual(u['dispatch_ns'],1)
        self.assertEqual(u['response_ns'],30);self.assertEqual(n['dispatch_ns'],71)

    def test_expiry_wakes_without_arrival_or_worker_event(self):
        out=self.run_case([request(priority='normal')],[0],idle=100,obs=100,drain=100)
        self.assertEqual(out['ledger'][0]['dispatch_ns'],100)
        self.assertEqual(len(out['decisions']),2)

    def test_no_selection_cost_no_spin_and_change_during_cost_not_lost(self):
        qs=[request('n',priority='normal'),request('u',arrival=5,ordinal=1)]
        out=self.run_case(qs,[0],idle=100,decision_ns=10,record_ns=2)
        n,u=out['ledger'];self.assertEqual(u['dispatch_ns'],24)
        # The no-selection call96..108 spans the timer at100; one new12ns
        # decision starts at108. State change is kept; cost is not refunded.
        self.assertEqual(n['dispatch_ns'],120)
        self.assertLess(len(out['decisions']),10)

    def test_zero_cost_no_selection_is_finite(self):
        out=self.run_case([request(priority='normal')],[0,1,2],idle=100)
        self.assertEqual(out['ledger'][0]['dispatch_ns'],102)
        self.assertEqual(len(out['decisions']),4)

    def test_common_drain_counts_and_null_incomplete_background(self):
        qs=[request('n1',priority='normal'),request('n2',priority='normal',ordinal=1)]
        out=self.run_case(qs,[0],obs=15,drain=70)
        m=out['background_metrics']
        self.assertEqual((out['metrics']['planned'],out['metrics']['arrived']),(2,2))
        self.assertEqual(out['metrics']['unfinished'],1)
        self.assertEqual((m['background_persisted_at_observation_end'],m['background_persisted_at_horizon']),(0,1))
        self.assertIsNone(m['background_completion_time_ns']);self.assertIsNone(m['all_lanes_released_at_ns'])
        self.assertIsNone(out['metrics']['makespan_s'])

    def test_failure_and_unexecuted_denominators_are_not_dropped(self):
        rows=[dict(request('failed',priority='normal'),status='failed'),
              dict(request('future',priority='normal',ordinal=1),status='not_arrived')]
        m=new.metrics(rows,100,200)
        self.assertEqual((m['planned'],m['background_planned'],m['not_dispatched']),(2,2,2))
        self.assertEqual(m['status_counts']['failed'],1)
        self.assertEqual(m['status_counts']['not_arrived'],1)
        self.assertIsNone(m['background_completion_time_ns'])

    def test_both_permission_arms_observe_same_interaction_calendar(self):
        qs=[request(priority='normal')]
        a=self.run_case(qs,[0,10],restrict=False)
        b=self.run_case(qs,[0,10],restrict=True)
        self.assertEqual(a['interaction_events'],b['interaction_events'])
        self.assertEqual(a['ledger'][0]['dispatch_ns'],0)
        self.assertEqual(b['ledger'][0]['dispatch_ns'],25)

    def test_persist_completion_distinct_from_lane_and_cleanup(self):
        out=self.run_case([request(priority='normal')],obs=60,drain=5)
        m=out['background_metrics']
        self.assertEqual(m['background_completion_time_ns'],60)
        self.assertEqual(m['background_persisted_at_observation_end'],1)
        self.assertIsNone(m['all_lanes_released_at_ns']);self.assertEqual(m['cleanup'],'not_modelled')
        self.assertEqual(out['metrics']['unfinished'],1)

    def test_background_batch_origin_not_last_arrival(self):
        out=self.run_case([request('n1',priority='normal',arrival=10),request('n2',priority='normal',arrival=20,ordinal=1)])
        self.assertEqual(out['background_metrics']['background_all_persisted_at_ns'],140)
        self.assertEqual(out['background_metrics']['background_completion_time_ns'],130)

    def test_drain_must_include_last_expiry(self):
        with self.assertRaisesRegex(ValueError,'last timer expiry'):
            self.run_case([request(priority='normal')],[10],obs=10,drain=14)

    def test_unseen_interaction_and_future_requests_not_policy_input(self):
        qs=[request(priority='normal'),request('future',arrival=150,ordinal=1)]
        a=self.run_case(qs);b=self.run_case(qs,[100])
        self.assertEqual(a['decisions'][0],b['decisions'][0])
        self.assertEqual(b['decisions'][0]['admission']['queued_ids'],['a'])
        c,v=fixture()
        for rows in v['cells'].values():
            for row in rows:row['durations_ns']=[x*2 for x in row['durations_ns']]
        self.assertEqual(b['decisions'][0],self.run_case(qs,[100],vectors=v)['decisions'][0])
        calls=[];real=old.choose
        def observe(config,queue,lanes,now,policy,settings):
            calls.append((copy.deepcopy(queue),copy.deepcopy(lanes)))
            return real(config,queue,lanes,now,policy,settings)
        with patch.object(old,'choose',side_effect=observe):self.run_case(qs,[100])
        self.assertTrue(calls)
        self.assertEqual(set(calls[0][0][0]),{'id','task','priority','ordinal','arrival_ns','deadline_offset_ns'})
        self.assertEqual(set(calls[0][1]['CPU']),{'request','phase','since','dispatch'})

    def test_static_cross_matrix_no_evaluation_selection(self):
        a=dict(id='dev_pause',static_map=dict(classification='GPU',detection='CPU'),static_parallel=True,development_freeze_sha256='a'*64)
        b=dict(id='dev_allow',static_map=dict(classification='CPU',detection='GPU'),static_parallel=True,development_freeze_sha256='b'*64)
        matrix=new.comparison_matrix([a,b])
        self.assertEqual(len(matrix),6)
        for ident in ('cpu_fixed','dev_pause','dev_allow'):
            self.assertEqual([x['restrict_background'] for x in matrix if x['assignment']['id']==ident],[False,True])
        self.assertEqual(len(new.comparison_matrix([a,a])),4)
        with self.assertRaises(ValueError):new.comparison_matrix([dict(a,evaluation_score=1)])

    def test_strict_remains_globally_serial_and_explore_parallel_is_assumption(self):
        a=request('normal',priority='normal');b=request('urgent',ordinal=1);b['task']='detection'
        strict=self.run_case([a,b],mode='strict')['ledger']
        self.assertEqual(sorted(r['dispatch_ns'] for r in strict),[0,70])
        explore=self.run_case([a,b],mode='explore')['ledger']
        self.assertEqual([r['dispatch_ns'] for r in explore],[0,0])

    def test_schemas_reject_future_fields(self):
        with self.assertRaises(ValueError):new.InteractionGate([dict(id='x',at_ns=0,future_end=5)])
        with self.assertRaises(ValueError):new.InteractionGate([dict(id='x',at_ns=0)]*2)
        with self.assertRaises(ValueError):new.InteractionGate([],0)

    def test_three_hand_calculated_traces(self):
        out=new.demo()
        self.assertEqual(set(out['scenarios']),{'none','intermittent','finite_burst'})
        self.assertTrue(all(x['actual_seconds']==x['expected_seconds'] for x in out['scenarios'].values()))
        self.assertFalse(out['experiment_ready'])


if __name__=='__main__':unittest.main()
