"""Hand-calculated source-rule boundaries and actual frozen-engine integration."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest import mock
from tools import d1_external_rules as r
from tools import d1_external_rules_study as s


def ticket(name, task='classification', at=35., ordinal=0):
    return dict(id=name,task=task,priority='urgent' if task=='classification' else 'normal',
                arrival_ns=round(at*1e9),ordinal=ordinal,
                deadline_offset_ns=1500000000 if task=='classification' else 6000000000)


class SourceBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.health=s.environments()[0]['snapshots'][0]
        self.c=ticket('c');self.d=ticket('d','detection',ordinal=1)
        self.expected={'classification_CPU_urgent':4.,'classification_GPU_urgent':8.,'detection_CPU_normal':10.}

    def test_android_default_strict_battery_and_temperature_boundaries(self):
        self.assertEqual(r.health_issues(dict(self.health,battery_percent=20,battery_c=42),120),[])
        self.assertIn('lowBattery',r.health_issues(dict(self.health,battery_percent=19),0))
        self.assertIn('batteryTooHot',r.health_issues(dict(self.health,battery_c=42.001),0))

    def test_observation_freshness_future_and_exact_age(self):
        self.assertEqual(r.health_issues(self.health,120),[])
        self.assertEqual(r.health_issues(self.health,120.001),['staleObservation'])
        self.assertEqual(r.health_issues(dict(self.health,observed_s=1),0),['staleObservation'])

    def test_thermal_state_and_android_unsupported_fallback(self):
        for name in ('nominal','light','moderate'):
            self.assertEqual(r.health_issues(dict(self.health,thermal_state=name),0),[])
        for name in ('serious','critical','emergency','shutdown'):
            self.assertIn('thermalTooHigh',r.health_issues(dict(self.health,thermal_state=name),0))
        self.assertEqual(r.health_issues(dict(self.health,thermal_status='unsupported'),0),[])
        issues=r.health_issues(dict(self.health,thermal_status='unsupported',battery_health='unknown'),0)
        self.assertIn('thermalUnavailable',issues);self.assertIn('batteryHealthUnavailable',issues)

    def test_missing_health_denies_instead_of_substituting_AP(self):
        for change,issue in [(dict(battery_status='unavailable'),'batteryUnavailable'),
                             (dict(battery_c=None),'batteryTemperatureUnavailable'),
                             (dict(battery_health='overheat'),'batteryUnhealthy')]:
            self.assertIn(issue,r.health_issues(dict(self.health,**change),0))

    def test_activity_timer_reset_override_and_health_and(self):
        self.assertFalse(r.allow_compute(self.health,50.999,36)[0])
        self.assertTrue(r.allow_compute(self.health,51.,36)[0])
        self.assertFalse(r.allow_compute(self.health,51.,50)[0])
        self.assertTrue(r.allow_compute(self.health,51.,50,interaction_override=True)[0])
        self.assertFalse(r.allow_compute(dict(self.health,battery_percent=19),51.,50,interaction_override=True)[0])
        self.assertFalse(r.allow_compute(self.health,51.,0,initial_checks=False)[0])
        self.assertFalse(r.allow_compute(self.health,51.,0,blocked=True)[0])

    def test_environment_does_not_return_future_health(self):
        env=r.Environment(next(e for e in s.environments() if e['id']=='battery_recovers'))
        self.assertEqual(env.current(59.999)[0]['battery_percent'],19)
        self.assertEqual(env.current(60)[0]['battery_percent'],20)
        self.assertEqual(env.next_delivery(59),60)

    def test_response_audit_one_ns_rounding_does_not_change_deadline_criterion(self):
        q=ticket('rounded')
        row=dict(q,status='succeeded',backend='CPU',dispatch_ns=35000000000,
                 execution_start_ns=35000000001,output_ready_ns=35000000010,
                 persist_complete_ns=35000000011,worker_release_ns=35000000012,
                 lane_available_ns=35000000013,response_ns=9)
        s.audit(dict(ledger=[row],decisions=[]),[q])
        self.assertEqual(row['response_ns'],9)
        row['response_ns']=8
        with self.assertRaisesRegex(AssertionError,'representation'):
            s.audit(dict(ledger=[row],decisions=[]),[q])

    def test_band_largest_of_shortest_latencies_ignores_urgent_label(self):
        chosen,_,_=r.heft_pick([self.c,self.d],self.expected,{'CPU':0,'GPU':0},{'CPU','GPU'},lambda q,b:True)
        self.assertEqual(chosen,{'request_id':'d','backend':'CPU'})

    def test_band_busy_best_yields_and_recomputes_waiting(self):
        chosen,audit,yielded=r.heft_pick([self.c,self.d],self.expected,{'CPU':1,'GPU':0},{'GPU'},lambda q,b:True)
        self.assertEqual(yielded,['d'])
        self.assertEqual(chosen,{'request_id':'c','backend':'GPU'})
        self.assertEqual(audit[-1]['shortest_ns'],8.)

    def test_band_duplicate_model_and_exact_source_ties(self):
        expected=dict(self.expected,classification_CPU_urgent=10.,classification_GPU_urgent=10.)
        chosen,_,_=r.heft_pick([self.c,self.d,ticket('c2',ordinal=2)],expected,{'CPU':0,'GPU':0},{'CPU','GPU'},lambda q,b:True)
        self.assertEqual(chosen,{'request_id':'c','backend':'GPU'})
        chosen,_,yielded=r.heft_pick([self.c],self.expected,{'CPU':0,'GPU':0},{'CPU','GPU'},lambda q,b:False)
        self.assertIsNone(chosen);self.assertEqual(yielded,['c'])


class EngineIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.frozen,case=r.p.inputs(r.p.BUNDLE);cls.initial=case['initial']
        cls.lanes={b:dict(request=None,phase='AVAILABLE',since=0,dispatch=None) for b in ('CPU','GPU')}

    def test_public_lane_return_updates_EMA_not_output_or_worker_release(self):
        c=r.BandController(self.frozen,self.initial);q=ticket('ema')
        lanes=copy.deepcopy(self.lanes);lanes['CPU']=dict(request=q,phase='OUTPUT_READY',since=35e9,dispatch=35e9)
        before=c.expected[r.p.key(q,'CPU')]
        c.observe(35.1e9,lanes);self.assertEqual(c.expected[r.p.key(q,'CPU')],before)
        lanes['CPU']['phase']='WORKER_RELEASED';c.observe(35.2e9,lanes)
        self.assertEqual(c.ema_records,[])
        c.observe(35.3e9,self.lanes)
        self.assertEqual(c.expected[r.p.key(q,'CPU')],int(.1*300000000+.9*before))

    def test_future_request_private_lane_and_unsupported_task_rejected(self):
        c=r.BandController(self.frozen,self.initial)
        with self.assertRaisesRegex(ValueError,'future'):
            c(None,[ticket('future',at=36)],self.lanes,35e9,r.settings(),None,None)
        bad=copy.deepcopy(self.lanes);bad['CPU']['durations']=[]
        with self.assertRaisesRegex(ValueError,'private'):
            c(None,[ticket('c')],bad,35e9,r.settings(),None,None)
        with self.assertRaisesRegex(ValueError,'unsupported'):
            c(None,[dict(ticket('c'),task='unknown')],self.lanes,35e9,r.settings(),None,None)

    def test_original_EFT_schedule_and_metrics_unchanged(self):
        tickets=[ticket('same-c'),ticket('same-d','detection',at=35.1,ordinal=1)]
        a,_=r.simulate(self.frozen,self.initial,tickets,'long_context','EFT_REFERENCE')
        _,b,_=r.old.simulate(self.frozen,self.initial,tickets,'long_context','EFT_REFERENCE',seed=201)
        keys=['id','status','backend','dispatch_ns','output_ready_ns','persist_complete_ns','worker_release_ns','lane_available_ns','response_ns']
        self.assertEqual([{k:q.get(k) for k in keys} for q in a['ledger']],[{k:q.get(k) for k in keys} for q in b['ledger']])
        s.audit(a,tickets);self.assertEqual(a['metrics'],b['metrics'])

    def test_gate_retains_work_allows_urgent_and_does_not_preempt_running_BG(self):
        tickets=[ticket('early-bg','detection'),ticket('fg',at=36,ordinal=1),ticket('held-bg','detection',at=36,ordinal=2)]
        env=next(e for e in s.environments() if e['id']=='intermittent_activity')
        result,_=r.simulate(self.frozen,self.initial,tickets,'mean',r.ENTE,env)
        by={x['id']:x for x in result['ledger']};s.audit(result,tickets)
        self.assertEqual(by['early-bg']['dispatch_ns'],35e9)
        self.assertLess(by['early-bg']['lane_available_ns'],37e9)
        self.assertLess(by['fg']['dispatch_ns'],51e9)
        self.assertGreaterEqual(by['held-bg']['dispatch_ns'],65e9)
        self.assertEqual(sum(q['status']=='succeeded' for q in by.values()),3)

    def test_gate_unfinished_is_counted_and_full_AP_is_null(self):
        tickets=[ticket('bg','detection'),ticket('fg',at=36,ordinal=1)]
        env=next(e for e in s.environments() if e['id']=='battery_low_persistent')
        result,c=r.simulate(self.frozen,self.initial,tickets,'mean',r.ENTE,env)
        s.audit(result,tickets);metric,_=s.metrics(result,c,self.initial,self.frozen)
        self.assertEqual(metric['planned'],2);self.assertEqual(metric['completed'],1)
        self.assertEqual(metric['normal_service_failure'],1)
        self.assertFalse(metric['energy_full_work_eligible']);self.assertIsNone(metric['peak_ap_c'])
        self.assertIsNone(metric['ap_safety_limit_exceed_s'])


class RunIsolationTests(unittest.TestCase):
    def test_shared_checkout_runs_without_old_local_files_and_cache_is_not_recomputed(self):
        frozen,case=r.p.inputs(r.p.BUNDLE)
        initial={k:case['initial'][k] for k in ('preload','preload_power_w')}
        with tempfile.TemporaryDirectory(prefix='io_fixture_',dir=s.LOCAL) as name:
            root=Path(name).resolve()
            self.assertTrue(root.is_relative_to(s.LOCAL.resolve()))
            bundle=root/'shared';bundle.mkdir()
            out=root/'new_run';absent_local=root/'unavailable_old_output'
            spec=dict(logical_rows=2,base_head='69417fe2433cbc11521aa8399ef72fa55c7b4ab9',
                      contexts=['mean'],resource_policies=['CPU_REFERENCE','EFT_REFERENCE'],gate_policies=[],
                      maximum_batch_wall_s=60,old_sources={})
            s.write(bundle/'contract.json',spec)
            s.write(bundle/'inputs.json',dict(initial=initial,environments=[],workloads=[dict(seed=1,family='fixture',
                    tickets=[ticket('c'),ticket('d','detection',at=35.1,ordinal=1)])]))
            with mock.patch.object(s,'BUNDLE',bundle),mock.patch.object(s,'LOCAL',absent_local),mock.patch.object(s,'check_frozen',return_value=spec):
                first=s.run(out)
                self.assertEqual(len(first),2);self.assertTrue((out/'results.csv').exists())
                self.assertFalse((bundle/'results.csv').exists())
                with mock.patch.object(r,'simulate',side_effect=AssertionError('cached results must not execute')):
                    second=s.run(out)
                self.assertEqual(first,second)
                self.assertEqual(s.read(out/'completion.json')['this_process_runs'],0)


if __name__=='__main__':unittest.main()
