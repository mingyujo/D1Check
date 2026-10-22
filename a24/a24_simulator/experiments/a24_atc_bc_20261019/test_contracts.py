"""Synthetic contract checks only; no environment or scientific model fit."""
import copy
import json
import math
from pathlib import Path
import sys
import unittest

H = Path(__file__).resolve().parent
sys.path.insert(0,str(H.parent))
from a24_atc_bc_20261019 import load_components, VERSION
C = load_components()
from a24_atc_bc_20261019.candidates import atc_index, build, compatible_targets
from a24_atc_bc_20261019.learner import Learner, Net
from common_transfer import np, torch, loadpt


def job(i=0, task='D', priority='N', due=10):
    return dict(request_id=str(i),ordinal=i,task=task,priority=priority,
                scheduled_arrival_ns=i*1000,deadline_ns=round(due*1e9))


def state(jobs, owners=None):
    return dict(queue=jobs,owners=owners or [],now_ns=1_000_000_000,
                wait_used_ns=0,sensor=dict(temperature_c=27.,shared_z=0.,increment_so_far=0.))


class Nominal:
    def vector(self,j,route,s):
        return [0.,.01 if j['request_id']=='20' else .1,0.,0.,0.]


class Physics:
    cpu_slots=3
    profile='ORIGINAL'
    c=type('Config',(),dict(idle_c=26.))()
    solo={k+'_'+r:1. for k in ('classification','detection') for r in ('CPU','GPU')}
    def speed(self,*args):return 1.
    def rates(self,T,active):return {a['request_id']:1. for a in active}
    def transition(self,s,active,dt):
        return copy.deepcopy(s),dict(increment=len(active)*dt,
            temperature_area=s['temperature_c']*dt,peak=s['temperature_c'],speeds=self.rates(27,active))


class Contracts(unittest.TestCase):
    def test_s26_urgency_weight_is_log_two(self):
        n=atc_index('N',1,.5,5,1,2)
        u=atc_index('U',1,.5,5,1,2)
        self.assertAlmostEqual(u-n,math.log(2))

    def test_slack_priority_and_zero_duration_guards(self):
        self.assertGreater(atc_index('N',1,.5,2,1,1),atc_index('N',1,.5,8,1,1))
        self.assertAlmostEqual(atc_index('U',2,1,0,1,1),0.)
        self.assertTrue(math.isfinite(atc_index('N',0,0,1,1,0)))

    def test_atc_can_add_middle_request_outside_edf_prefix(self):
        s=state([job(i,due=100) for i in range(40)])
        c=build(s,Nominal(),Physics())
        ids=[q['request_id'] for q in c['chosen']]
        self.assertIn('20',ids)
        self.assertIn('0',ids)
        self.assertIn('39',ids)
        self.assertEqual(len(ids),8)
        self.assertEqual(len(c['visible']),32)
        self.assertTrue(set(ids)<=set(c['visible']))

    def test_candidate_set_is_input_order_independent(self):
        jobs=[job(i,due=10+i%3) for i in range(40)]
        a=build(state(jobs),Nominal(),Physics())
        b=build(state(jobs[::-1]),Nominal(),Physics())
        self.assertEqual([q['request_id'] for q in a['chosen']],[q['request_id'] for q in b['chosen']])
        self.assertEqual(a['atc'],b['atc'])

    def test_capacity_masks_only_physical_routes(self):
        owners=[dict(**job(i+50),route='CPU') for i in range(3)]
        c=build(state([job()],owners),Nominal(),Physics())
        self.assertEqual(c['free'],['GPU'])
        self.assertTrue(all(route=='GPU' for rid,route in c['atc']))

    def test_compatible_ties_respect_task_priority_and_route(self):
        jobs=[job(0),job(1),job(2,task='C'),job(3,priority='U'),job(4,due=11)]
        actions=[dict(kind='DISPATCH',request_id=j['request_id'],route='CPU') for j in jobs]
        actions.append(dict(kind='DISPATCH',request_id='0',route='GPU'))
        self.assertEqual(compatible_targets(state(jobs),actions,0),[True,True,False,False,False,False])

    def test_wait_targets_preserve_duration_and_event_semantics(self):
        actions=[dict(kind='WAIT',wait_ns=20_000_000),dict(kind='WAIT',wait_ns=50_000_000),dict(kind='WAIT_EVENT')]
        self.assertEqual(compatible_targets(state([job()]),actions,0),[True,False,False])

    def test_feature_abi_is_fifty_and_state_is_immutable(self):
        s=state([job(),job(1)])
        before=copy.deepcopy(s)
        p=C.Policy(Nominal(),Physics(),dict(n=2,service_stop_s=12,supply_stop_s=10),'TEACHER')
        bank,actions=p.encode(s)
        self.assertEqual(s,before)
        self.assertEqual(bank['x'].shape,(36,50))
        self.assertEqual(bank['version'],VERSION)
        self.assertEqual(int(bank['mask'].sum()),len(actions))
        self.assertTrue(np.isfinite(bank['x']).all())
        self.assertEqual(len({f['H_s'] for f in bank['forecasts']}),1)
        self.assertTrue(all(f['no_future_arrivals'] and f['no_future_latents'] for f in bank['forecasts']))

    def test_atc_feature_uses_public_formula(self):
        s=state([job(priority='U')])
        p=C.Policy(Nominal(),Physics(),dict(n=1,service_stop_s=12,supply_stop_s=10),'TEACHER')
        bank,actions=p.encode(s)
        expected=(math.log(2/.1)-(10-1-.1)/(2*.1))/5
        compressed=expected if abs(expected)<=5 else math.copysign(5+math.log1p(abs(expected)-5),expected)
        self.assertAlmostEqual(float(bank['x'][0,48]),compressed,places=6)

    def test_network_choice_has_no_atc_or_teacher_override(self):
        s=state([job()])
        class Fixed:
            def choose(self,bank,collect):return 2,{}
        p=C.Policy(Nominal(),Physics(),dict(n=1,service_stop_s=12,supply_stop_s=10),'BC',Fixed(),False)
        bank,actions=p.encode(s)
        self.assertEqual(p(s),actions[2])
        self.assertFalse(p.calls[-1]['fixed_ATC_prior'])
        self.assertFalse(p.calls[-1]['post_NN_override'])

    def test_masked_compatible_bc_gradient_is_finite(self):
        net=Net()
        x=torch.arange(36*50,dtype=torch.float32).reshape(1,36,50)/1000
        mask=torch.zeros((1,36),dtype=torch.bool);mask[0,:3]=True
        teacher=torch.zeros_like(mask);teacher[0,:2]=True
        logits,_=net(x,mask)
        loss=(logits.logsumexp(-1)-logits.masked_fill(~teacher,-1e9).logsumexp(-1)).mean()
        loss.backward()  # No optimizer step or scientific fit.
        gradients=[p.grad for p in net.parameters() if p.grad is not None]
        self.assertTrue(torch.isfinite(loss))
        self.assertTrue(all(torch.isfinite(g).all() for g in gradients))
        self.assertGreater(sum(float(g.abs().sum()) for g in gradients),0)

    def test_old_48_feature_checkpoint_is_rejected(self):
        old=loadpt(H.parents[1]/'results/A24_S26_METHOD_20261019_01/ORIGINAL.BC.FINAL.pt.gz')
        with self.assertRaises(AssertionError):Learner(state=old)


if __name__=='__main__':unittest.main(verbosity=2)
