import copy
import unittest
from tools import d1_arrival_explore as e
from tools.test_d1_cal03_connection import fixture, request

def settings(**kw):
    return dict(dict(mode='explore',decision_ns=0,record_ns=0,dispatch_ns=0,aging_ns=1000,
        interference=1.,predicted_interference=1.5,estimate_factor=1.,static_parallel=True,
        static_map={'classification':'CPU','detection':'GPU'}),**kw)

class ExploreTest(unittest.TestCase):
    def run_case(self,qs,policy='CPU_URGENT',cfg=None,vec=None,horizon=10000,**kw):
        c,v=fixture()
        return e.simulate(cfg or c,vec or v,qs,policy=policy,settings=settings(**kw),seed=7,horizon_ns=horizon)

    def test_priority_boundaries_and_cost_not_double(self):
        x=self.run_case([request()],decision_ns=2,record_ns=3,dispatch_ns=5)['ledger'][0]
        self.assertEqual([x[k] for k in ('dispatch_ns','execution_start_ns','output_ready_ns','persist_complete_ns','worker_release_ns','lane_available_ns')],[10,20,40,70,74,80])
        self.assertEqual(x['response_ns'],40)
        self.assertEqual(self.run_case([request(priority='normal')])['ledger'][0]['response_ns'],60)

    def test_release_not_output_or_worker(self):
        r=self.run_case([request(),request('b',arrival=31,ordinal=1)])['ledger']
        self.assertEqual(r[1]['dispatch_ns'],70)

    def test_overrun_busy_and_no_future(self):
        c,v=fixture();v['cells']['classification_CPU_urgent'][e.keyed_index(7,'a','CPU')]['durations_ns'][1]=100
        r=self.run_case([request(),request('b',arrival=80,ordinal=1)],vec=v)
        d=next(d for d in r['decisions'] if d['now_ns']==80)
        self.assertEqual(d['residuals']['CPU']['state'],'UNKNOWN_OVERRUN');self.assertIsNone(d['selected'])
        self.assertEqual(r['ledger'][1]['dispatch_ns'],150)

    def test_strict_is_global_not_per_lane(self):
        qs=[request(priority='normal'),request('b',ordinal=1)]
        r=self.run_case(qs,'FIXED_SPLIT',mode='strict')['ledger']
        self.assertEqual(sorted(x['dispatch_ns'] for x in r),[0,70])

    def test_parallel_service_work_and_release(self):
        r=self.run_case([request(priority='normal'),request('b',ordinal=1)],'FIXED_SPLIT',interference=2)['ledger']
        self.assertEqual([x['output_ready_ns'] for x in r],[50,50])
        self.assertEqual([x['lane_available_ns'] for x in r],[90,90])

    def test_same_time_release_before_arrival(self):
        r=self.run_case([request(),request('b',arrival=70,ordinal=1)])['ledger']
        self.assertEqual(r[1]['dispatch_ns'],70)

    def test_arrival_during_decision_and_no_future_selection(self):
        x=self.run_case([request(priority='normal'),request('b',arrival=5,ordinal=1)],decision_ns=10)
        self.assertEqual(x['decisions'][0]['selected']['request_id'],'a')
        self.assertEqual(x['ledger'][1]['queue_entry_ns'],5)
        self.assertEqual([q['id'] for q in x['decisions'][0]['queue']],['a'])

    def test_horizon_preserves_full_denominator(self):
        x=self.run_case([request(),request('b',arrival=200,ordinal=1)],horizon=50)
        self.assertEqual((x['metrics']['planned'],x['metrics']['arrived'],x['metrics']['unfinished'],x['metrics']['not_arrived']),(2,1,1,1))
        self.assertIsNone(x['metrics']['makespan_s'])

    def test_realizations_do_not_leak_first_decision(self):
        c,v=fixture();w=copy.deepcopy(v)
        for vs in w['cells'].values():
            for r in vs:r['durations_ns']=[x*3 for x in r['durations_ns']]
        a=self.run_case([request()],'B3_SOLO_EFT_PC',vec=v)
        b=self.run_case([request()],'B3_SOLO_EFT_PC',vec=w)
        self.assertEqual(a['decisions'][0],b['decisions'][0])

    def test_unknown_fields_rejected(self):
        c,_=fixture();lanes={b:dict(request=None,phase='AVAILABLE',since=0,dispatch=None) for b in ('CPU','GPU')}
        with self.assertRaises(ValueError):e.choose(c,[dict(request(),future_completion=3)],lanes,0,'B3_SOLO_EFT_PC',settings())

    def test_p_unknown_pair_harm_not_zero(self):
        c,_=fixture();lanes={'CPU':dict(request=request('old'),phase='EXECUTING',since=10,dispatch=0),
            'GPU':dict(request=None,phase='AVAILABLE',since=0,dispatch=None)}
        r=e.choose(c,[request('new')],lanes,80,'P_PAIR_COST_PC',settings())
        self.assertIsNone(r['selected']);self.assertEqual(r['reason'],'wait_unknown_overrun_pair_cost')

    def test_keyed_draw_policy_order_independent(self):
        self.assertEqual(e.keyed_index(5,'q','GPU'),e.keyed_index(5,'q','GPU'))
        a=self.run_case([request()],'CPU_URGENT')['ledger'][0]
        b=self.run_case([request()],'B2_PC')['ledger'][0]
        self.assertEqual(a['source_request_id'],b['source_request_id'])

    def test_aging_prevents_finite_burst_starvation(self):
        qs=[request('normal',priority='normal',ordinal=0)]+[request(str(i),ordinal=i+1) for i in range(20)]
        r=self.run_case(qs,'P_NO_PARALLEL_PC',aging_ns=100)['ledger'][0]
        self.assertLessEqual(r['dispatch_ns'],140)

    def test_legacy_urgent_baseline_does_not_gain_aging(self):
        qs=[request('normal',priority='normal',ordinal=0)]+[request(str(i),ordinal=i+1) for i in range(3)]
        r=self.run_case(qs,aging_ns=1)['ledger'][0]
        self.assertEqual(r['dispatch_ns'],210)

    def test_p_ablation_and_concrete_different_choice(self):
        c,_=fixture()
        # GPU occupied, CPU idle: B3 runs CPU now. P counts slowdown+harm and waits for GPU.
        q=request();running=request('run',priority='normal')
        lanes={'CPU':dict(request=None,phase='AVAILABLE',since=0,dispatch=None),
               'GPU':dict(request=running,phase='EXECUTING',since=10,dispatch=0)}
        # GPU response 10, CPU30; GPU residual20 at now50 => tie -> CPU in B3.
        c['cells']['classification_GPU_urgent']['joint']['dispatch_to_response_ns']['median_ns']=10
        b=e.choose(c,[q],lanes,50,'B3_SOLO_EFT_PC',settings())
        p=e.choose(c,[q],lanes,50,'P_PAIR_COST_PC',settings(predicted_interference=2))
        self.assertEqual(b['selected']['backend'],'CPU');self.assertIsNone(p['selected'])
        zero=e.choose(c,[q],lanes,50,'P_PAIR_COST_PC',settings(predicted_interference=1))
        self.assertEqual(b['selected'],zero['selected'])

if __name__=='__main__':unittest.main()
