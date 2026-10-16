import copy
import math
import unittest
from tools import d1_scheduler_alternatives as a
from tools import d1_request_ppo as rl
from tools.test_d1_empirical_request_policy import empty


class AlternativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.frozen,case=a.p.inputs(a.p.BUNDLE);cls.initial=case['initial']
        cls.tickets=a.old.workload('queue',812)[:6]
        cls.config=dict(protocol=a.p.VERSION,cells=a.p.profile(cls.frozen));cls.settings=rl.settings()

    def c(self,policy='PARETO_MPC_V1'):return a.Controller(self.frozen,self.initial,policy)

    def test_specification_counts_split(self):
        s=a.specification();self.assertFalse(set(s['development_seeds'])&set(s['test_seeds']))
        self.assertEqual(s['development_runs'],4*4*3*8);self.assertEqual(s['final_runs'],8*4*3*11)
        self.assertEqual(s['device_commands'],0)

    def test_actual_entry_all_five_and_lane_release(self):
        for policy in a.p.ALTERNATIVE_POLICIES:
            row,r,c,_=a.simulate(self.frozen,self.initial,self.tickets,'mean',policy)
            self.assertEqual(row['completed'],6)
            self.assertEqual([x['arrival_ns'] for x in r['ledger']],[q['arrival_ns'] for q in self.tickets])
            self.assertGreater(len(c.callback_wall_seconds),0)
            for backend in ('CPU','GPU'):
                jobs=sorted((x for x in r['ledger'] if x['backend']==backend),key=lambda x:x['dispatch_ns'])
                self.assertTrue(all(x['lane_available_ns']<=y['dispatch_ns'] for x,y in zip(jobs,jobs[1:])))
            for q in r['ledger']:
                times=[q[k] for k in ('dispatch_ns',*a.old.engine.FIELDS)];self.assertEqual(times,sorted(times))

    def test_future_tickets_and_private_fields_blocked(self):
        c=self.c()
        with self.assertRaises(ValueError):c(self.config,self.tickets,empty(),34e9,self.settings,None,None)
        lanes=empty();lanes['CPU']['left']=1
        with self.assertRaises(ValueError):c(self.config,self.tickets[:1],lanes,35e9,self.settings,None,None)

    def test_future_arrival_mutation_prefix(self):
        x=copy.deepcopy(self.tickets);x[-1]['arrival_ns']+=10e9
        for policy in ('RESERVED_BACKFILL_V1','PARETO_MPC_V1','THERMAL_MPC_V1'):
            _,ra,_,_=a.simulate(self.frozen,self.initial,self.tickets,'mean',policy)
            _,rb,_,_=a.simulate(self.frozen,self.initial,x,'mean',policy)
            cut=self.tickets[-1]['arrival_ns']
            self.assertEqual([d for d in ra['decisions'] if d['now_ns']<cut],[d for d in rb['decisions'] if d['now_ns']<cut])

    def test_unknown_overrun_not_zero(self):
        lanes=empty();q=self.tickets[0];lanes['CPU']=dict(request=q,phase='EXECUTING',since=35e9,dispatch=35e9)
        c=self.c();c.observe(40e9,lanes)
        d=c(self.config,[self.tickets[1]],lanes,40e9,self.settings,None,None)
        self.assertIsNone(d['selected']);self.assertEqual(d['reason'],'unknown_overrun_wait_for_event')

    def test_backfill_does_not_delay_reservations(self):
        c=self.c('RESERVED_BACKFILL_V1');q=copy.deepcopy(self.tickets[0]);q.update(task='classification',priority='urgent',deadline_offset_ns=1.5e9)
        head=dict(q,id='head',ordinal=1);normal=dict(q,id='normal',ordinal=2,task='detection',priority='normal',deadline_offset_ns=6e9)
        lanes=empty();lanes['GPU']=dict(request=q,phase='EXECUTING',since=35e9,dispatch=35e9);c.observe(35e9,lanes)
        d=c(self.config,[head,normal],lanes,35e9,self.settings,None,None)
        self.assertEqual(d['selected'],dict(request_id='normal',backend='CPU'))
        active=c.active_jobs(lanes,35)
        ref,_,_=c.project(c,[head,normal],active,('head','GPU',0),35,{},False)
        candidate,_,_=c.project(c,[head,normal],active,('normal','CPU',0),35,{},False)
        reserved={j['id']:j['start'] for j in ref}
        self.assertTrue(all(j['start']<=reserved[j['id']]+1e-9 for j in candidate))

    def test_mpc_chosen_local_guard_all_contexts(self):
        c=self.c();q=copy.deepcopy(self.tickets[0]);q.update(task='classification',priority='urgent',deadline_offset_ns=1.5e9)
        other=dict(q,id='other',task='detection',priority='normal',ordinal=1,deadline_offset_ns=6e9)
        queue=[q,other];c.observe(35e9,empty())
        d=c(self.config,queue,empty(),35e9,self.settings,None,None)
        chosen=(d['chosen_request_id'],d['chosen_backend'],d['chosen_explicit_delay_s'])
        priorities={x['id']:x['priority'] for x in queue}
        for fc in c.forecasters:
            _,_,ref=c.project(fc,queue,[],(q['id'],'CPU',0.),35,priorities)
            _,_,score=c.project(fc,queue,[],chosen,35,priorities)
            self.assertTrue(all(x<=y+1e-9 for x,y in zip(score['service'],ref['service'])))
            self.assertTrue(all(score[k]<=ref[k]+1e-9 for k in ('energy','peak','area')))

    def test_lower_bound_not_policy_and_no_unknown_backend(self):
        for scenario in a.old.SCENARIOS:
            bound=a.energy_lower_bound(self.tickets,self.frozen,self.initial,scenario)
            for policy in ('CPU_REFERENCE','SPLIT_REFERENCE','EFT_REFERENCE'):
                row,*_=a.simulate(self.frozen,self.initial,self.tickets,scenario,policy)
                self.assertGreaterEqual(row['energy_j']+1e-8,bound['lower_bound_j'])
        q=dict(self.tickets[0],task='unknown')
        with self.assertRaises(ValueError):a.energy_lower_bound([q],self.frozen,self.initial,'mean')

    def test_missing_response_not_service_success(self):
        jobs=[dict(id='a',response=41,deadline=40,already_responded=False),dict(id='b',response=50,deadline=40,already_responded=True)]
        self.assertEqual(a.service_vector(jobs,{'a':'urgent','b':'normal'}),(1,0,1,0))

    def test_frozen_physics_unchanged(self):
        self.assertEqual(a.p.digest(a.p.BUNDLE/'model.json'),a.p.MODEL_SHA)
        self.assertEqual(a.p.digest(a.p.BUNDLE/'initial_inputs.json'),a.p.INITIAL_SHA)
        self.assertEqual(a.p.POLICIES,('CPU_REFERENCE','SPLIT_SERIAL_REFERENCE','SPLIT_REFERENCE','EFT_REFERENCE','ENERGY_AP_REQUEST_V1'))


if __name__=='__main__':unittest.main()
