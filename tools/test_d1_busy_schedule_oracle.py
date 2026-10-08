"""Hand cases for occupied-prefix and conditional queue semantics; no environments."""
import itertools,unittest
from tools import d1_busy_schedule_oracle as x

def ticket(i,task,arrival=35e9):return dict(id=str(i),task=task,priority='urgent' if task=='classification' else 'normal',arrival_ns=arrival,deadline_offset_ns=1.5e9 if task=='classification' else 6e9,ordinal=i)

class BusyTests(unittest.TestCase):
    def test_first_busy_boundary_keeps_prefix_and_two_per_task(self):
        ts=[ticket(0,'detection')]+[ticket(i,'classification' if i<3 else 'detection',35e9+i*1e6) for i in range(1,5)]+[ticket(5,'classification',40e9)]
        ls=[dict(q,dispatch_ns=35e9 if i==0 else 36e9+i*1e6,decision_start_ns=35e9 if i==0 else 36e9+i*1e6,lane_available_ns=36e9 if i==0 else 37e9+i*1e6,backend='CPU') for i,q in enumerate(ts)]
        s=x.snapshot(ts,ls);self.assertEqual(s['snapshot_ns'],35e9+4e6);self.assertEqual(s['variable_ids'],['1','2','3','4']);self.assertEqual(s['active_ids'],['0']);self.assertEqual(s['omitted_ids'],['5'])

    def test_equal_time_dispatch_is_tail_not_prefix(self):
        ts=[ticket(0,'detection')]+[ticket(i,'classification' if i<3 else 'detection',35e9+i*1e6) for i in range(1,5)]
        ls=[dict(q,dispatch_ns=35e9 if i==0 else 35e9+4e6+i*1e6,decision_start_ns=35e9 if i==0 else 35e9+4e6+i*1e6,lane_available_ns=36e9,backend='CPU') for i,q in enumerate(ts)]
        ls[1]['dispatch_ns']=ls[1]['decision_start_ns']=35e9+4e6
        s=x.snapshot(ts,ls);self.assertEqual(len(s['prefix_calendar']),1);self.assertIn('1',s['variable_ids'])

    def test_inadequate_backlog_is_not_fabricated(self):
        ts=[ticket(0,'detection'),ticket(1,'classification')];ls=[dict(q,dispatch_ns=q['arrival_ns'],decision_start_ns=q['arrival_ns'],lane_available_ns=q['arrival_ns']+1e9,backend='CPU') for q in ts]
        self.assertIsNone(x.snapshot(ts,ls))

    def test_capacity_includes_running_release_not_response(self):
        import numpy as np
        starts=np.array([[0.,1.],[0.,3.]]);ends=np.array([[3.,2.],[3.,4.]])
        self.assertEqual(x.micro.capacity(starts,ends,['detection_CPU','classification_CPU']).tolist(),[False,True])

    def test_future_input_rejected_before_prefix_or_tail(self):
        frozen,initial=x.p.inputs(x.p.BUNDLE);initial=x.external.old.json.loads((x.p.ROOT/'docs/results/external_rules_02/inputs.json').read_text())['initial']
        case=dict(prefix_calendar=[],snapshot_ns=36e9);tail=x.make_tail(frozen,initial,x.external.BAND);c=x.PrefixController(frozen,initial,case,tail)
        lanes={b:dict(request=None,phase='AVAILABLE',since=35e9,dispatch=None) for b in ('CPU','GPU')}
        with self.assertRaises(ValueError):c.decide({},[ticket(1,'classification',36e9)],lanes,35e9,{},None,None)

    def test_exact_minima_match_independent_scalar_with_fixed_history(self):
        frozen,data=x.p.inputs(x.p.BUNDLE);initial=data['initial'];profile=x.p.profile(frozen);model=x.micro.PulseModel(frozen,initial)
        qs=[ticket(0,'detection'),ticket(1,'classification',35.1e9),ticket(2,'detection',35.1e9)]
        fixed=[dict(request_id='0',backend='CPU',start_ns=35e9)]
        reference=[dict(request_id='1',backend='CPU',start_ns=36e9),dict(request_id='2',backend='CPU',start_ns=36.2e9)]
        case=dict(tickets=qs,variable_ids=['1','2'],prefix_calendar=fixed,snapshot_ns=35.1e9)
        caps=dict(energy_j=1000.,peak_ap_c=100.,urgent_p95_ms=10000.,normal_mean_ms=10000.,urgent_service_failure=0,normal_service_failure=0)
        answer=x.enumerate_calendars(case,profile,model,[caps,caps],[reference],grid_ns=100000000,delay_ns=100000000)
        candidates=[];raw=0
        for backends in itertools.product(('CPU','GPU'),('CPU',)):
            for times in itertools.product(*answer['domains_ns']):
                raw+=1;jobs=[];responses=[]
                for q,b,start in zip(qs,['CPU',*backends],[35e9,*times]):
                    now=float(start);point=None
                    for phase,d in enumerate(profile[x.p.key(q,b)]):
                        now+=d
                        if phase==(1 if q['priority']=='urgent' else 2):point=round(now-q['arrival_ns'])
                    jobs.append(dict(state=q['task']+'_'+b,start=round(start)/1e9,end=round(now)/1e9));responses.append(point)
                if any(min(a['end'],b['end'])>max(a['start'],b['start']) and (a['state'].split('_')[-1]==b['state'].split('_')[-1] or '+'.join(sorted((a['state'],b['state']))) not in x.p.STATES) for a,b in itertools.combinations(jobs,2)):continue
                if any(r>q['deadline_offset_ns'] for r,q in zip(responses,qs)):continue
                cost=x.p.model.costs(x.p.segments(jobs,0.,180.),initial,list(range(35,181)),frozen,180.)
                candidates.append((cost['whole_120s_j'],max(cost['ap_path'])))
        self.assertEqual(raw,answer['counts']['raw']);self.assertTrue(candidates)
        self.assertAlmostEqual(min(j for j,t in candidates),answer['witnesses']['min_J']['energy_j'],places=10)
        self.assertAlmostEqual(min(t for j,t in candidates),answer['witnesses']['min_AP']['peak_ap_c'],places=10)

    def test_triton_does_not_release_external_cpu_classification(self):
        frozen,data=x.p.inputs(x.p.BUNDLE);initial=data['initial'];tail=x.make_tail(frozen,initial,'TRITON_RATE_OFF_FIXED_REQUEST_ADAPT_V1')
        case=dict(prefix_calendar=[],snapshot_ns=35e9);c=x.PrefixController(frozen,initial,case,tail)
        lanes={b:dict(request=None,phase='AVAILABLE',since=35e9,dispatch=None) for b in ('CPU','GPU')}
        lanes['CPU']=dict(request=ticket(0,'classification'),phase='WORKER_RELEASED',since=35.1e9,dispatch=35e9)
        c.observe(35.1e9,lanes);out=c.decide({},[ticket(1,'classification')],lanes,35.1e9,{},None,None)
        self.assertIsNone(out['selected']);self.assertEqual(out['reason'],'conditional_actual_capacity_wait')
        lanes['CPU']=dict(request=None,phase='AVAILABLE',since=35.2e9,dispatch=None);c.observe(35.2e9,lanes)
        out=c.decide({},[ticket(1,'classification')],lanes,35.2e9,{},None,None)
        self.assertEqual(out['selected'],dict(request_id='1',backend='GPU'));self.assertEqual(tail.rate.executions,dict(classification=0,detection=0))

    def test_triton_allocation_waits_for_external_cpu_release(self):
        frozen,data=x.p.inputs(x.p.BUNDLE);tail=x.make_tail(frozen,data['initial'],'TRITON_RATE_OFF_FIXED_REQUEST_ADAPT_V1')
        case=dict(prefix_calendar=[],snapshot_ns=35e9);c=x.PrefixController(frozen,data['initial'],case,tail);c.prefix_ids={'0'}
        lanes={b:dict(request=None,phase='AVAILABLE',since=35e9,dispatch=None) for b in ('CPU','GPU')}
        lanes['CPU']=dict(request=ticket(0,'detection'),phase='WORKER_RELEASED',since=35.1e9,dispatch=35e9)
        c.observe(35.1e9,lanes);out=c.decide({},[ticket(1,'detection')],lanes,35.1e9,{},None,None)
        self.assertIsNone(out['selected']);self.assertEqual(tail.rate.allocated['detection'],'1')
        lanes['CPU']=dict(request=None,phase='AVAILABLE',since=35.2e9,dispatch=None);c.observe(35.2e9,lanes)
        out=c.decide({},[ticket(1,'detection')],lanes,35.2e9,{},None,None);self.assertEqual(out['selected'],dict(request_id='1',backend='CPU'))

if __name__=='__main__':unittest.main()
