"""Semantic checks without starting simulator environments."""
import copy
from types import SimpleNamespace
import unittest
import torch
from tools import d1_ie_candidates_v2 as x
from tools.test_d1_ie_dispatch import ticket,lanes,controller as hand


def controller(policy=x.LIST):
    frozen,case=x.core.p.inputs(x.core.p.BUNDLE);c=x.Controller(frozen,case['initial'],policy)
    c.estimates=hand().estimates;c.profiles={ctx:copy.deepcopy(c.estimates) for ctx in x.core.CONTEXTS};c.observe(35e9,lanes())
    return c


class Candidates(unittest.TestCase):
    def test_uniform_prior_and_alternative_can_win(self):
        x.old.current.seed_all(11);net=x.UnbiasedPPO()
        state=torch.zeros((1,109));cand=torch.zeros((1,32,68));mask=torch.zeros((1,32),dtype=torch.bool);mask[0,:3]=True;base=torch.zeros_like(mask);base[0,0]=True
        dist,_=net(state,cand,mask,base)
        self.assertTrue(torch.allclose(dist.probs[0,:3],torch.full((3,),1/3)))
        alt_base=torch.zeros_like(base);alt_base[0,2]=True
        alt,_=net(state,cand,mask,alt_base)
        self.assertTrue(torch.equal(dist.probs,alt.probs)) # no fixed baseline bonus

    def test_double_q_uses_online_selection_target_evaluation(self):
        class Mock:
            def __init__(self,values):self.values=values
            def __call__(self,s,c):
                result=torch.zeros((1,2,6));result[0,:,0]=torch.tensor(self.values);return result
        online=Mock([5.,1.]);target=Mock([2.,9.]);mask=torch.ones((1,2),dtype=torch.bool)
        result=x.double_targets(online,target,None,None,mask,[0.]*5,torch.zeros((1,6)),torch.tensor([False]))
        self.assertEqual(float(result[0,0]),2.) # ordinary DQN target-max would incorrectly return 9
        end=x.double_targets(online,target,None,None,mask,[0.]*5,torch.ones((1,6)),torch.tensor([True]))
        self.assertTrue(torch.equal(end,torch.ones((1,6))))

    def test_service_guard_rejects_energy_saving_with_worse_p95(self):
        base=dict(base=True,jobs=[],forecasts={c:dict(valid=True,deadline_misses=0,lane_end_s=50.,delta_ap=0.,delta_j=0.,urgent_p95_ms=100.) for c in x.core.CONTEXTS})
        alt=copy.deepcopy(base);alt['base']=False
        for f in alt['forecasts'].values():f.update(delta_ap=-.1,delta_j=-1.,urgent_p95_ms=101.)
        self.assertEqual(x.guarded([base,alt]),[base])

    def test_cpsat_assigns_supported_nonglobal_plan(self):
        c=controller(x.ROLL);qs=[ticket('c',0),ticket('d',1,'detection',35.,6.)]
        plan,meta=x.cp_schedule(c,qs,lanes(),35e9)
        self.assertIn(meta['status'],('OPTIMAL','FEASIBLE'));self.assertEqual(len(plan),2)
        self.assertEqual(next(r for r in plan if r['request_id']=='d')['backend'],'CPU')
        jobs=[]
        for j in plan:
            q=next(q for q in qs if q['id']==j['request_id']);start=35+j['start_ms']/1000;end=start+sum(c.estimates[x.core.p.key(q,j['backend'])])/1e9
            jobs.append(dict(id=q['id'],state=q['task']+'_'+j['backend'],backend=j['backend'],start=start,end=end))
        for a,b in [(jobs[0],jobs[1])]:
            if min(a['end'],b['end'])>max(a['start'],b['start'])+1e-9:
                self.assertEqual(x.core.p.state([a['state'],b['state']]),'classification_GPU+detection_CPU')

    def test_private_future_and_capacity_are_rejected(self):
        c=controller()
        with self.assertRaisesRegex(ValueError,'future'):c.decide(None,[ticket('future',0,arrival=36.)],lanes(),35e9,{},None,None)
        ls=lanes();ls['CPU']=dict(request=ticket('active',1),phase='WORKER_RELEASED',since=35.9e9,dispatch=35e9)
        q=ticket('q',0);base=x.core.ie.Controller.decide(c,None,[q],ls,35.9e9,{},None,None)
        self.assertFalse(any(a['jobs'] for a in c.physical([q],ls,35.9e9,base)))

    def test_unknown_running_residual_never_becomes_zero(self):
        c=controller(x.ROLL);ls=lanes();ls['CPU']=dict(request=ticket('active',1,'detection',35.,6.),phase='WORKER_RELEASED',since=40e9,dispatch=35e9)
        plan,meta=x.cp_schedule(c,[ticket('q',0)],ls,40e9)
        self.assertIsNone(plan);self.assertEqual(meta['status'],'UNAVAILABLE_PUBLIC_RESIDUAL')

    def test_common_terminal_targets_full_denominator(self):
        row=dict(planned=10,completed=10,energy_j=9.,peak_ap_c=30.1,urgent_service_failure=0,normal_service_failure=0,urgent_p95_ms=100.)
        refs=[dict(row,energy_j=10.,peak_ap_c=30.) for _ in range(2)]
        c=SimpleNamespace(trajectory=[{}]);data,costs,valid=x.targets(c,row,refs)
        self.assertAlmostEqual(float(data[0]['target'][0]),1.);self.assertAlmostEqual(costs[0],.1)
        row['completed']=9;row['peak_ap_c']=None
        data,costs,valid=x.targets(c,row,refs)
        self.assertFalse(valid[0]);self.assertFalse(valid[1]);self.assertEqual(costs[1],1.)


if __name__=='__main__':unittest.main()
