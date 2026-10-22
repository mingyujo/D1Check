"""Pure decision contracts; no engine trajectory, fit or NN execution."""
import copy
import math
import unittest
from dynamic_policy import DynamicPolicy, route_tie
class Nominal:
    def __init__(self, cpu=.1, gpu=.2, tail=1.):self.cpu,self.gpu,self.tail=cpu,gpu,tail
    def vector(self,q,r,s):return [.01,self.cpu if r=='CPU' else self.gpu,.03,.02,self.tail]
class Physics:
    cpu_slots=3;beta=.25
    def speed(self,T,r,stage,task):return 1. if T<35 else (.5 if r=='CPU' else 1.)
def q(i,task='C',due=100):
    return dict(request_id='q'+str(i),ordinal=i,task=task,priority='N',scheduled_arrival_ns=i,queue_entry_ns=i,deadline_ns=due)
def s(queue,owners=(),T=26):
    return dict(now_ns=20,queue=queue,owners=[dict(request_id='o'+str(i),route=r,stage=k) for i,(r,k) in enumerate(owners)],sensor=dict(temperature_c=T))
def actor(mode='FIFO_DYN',nom=None):return DynamicPolicy(nom or Nominal(),Physics(),mode)
class Checks(unittest.TestCase):
    def test_FIFO_request_first(self):self.assertEqual(actor()(s([q(2,due=1),q(1)]))['request_id'],'q1')
    def test_EDF_request_first(self):self.assertEqual(actor('EDF_DYN')(s([q(1),q(2,due=1)]))['request_id'],'q2')
    def test_EDF_tie_FIFO(self):self.assertEqual(actor('EDF_DYN')(s([q(2),q(1)]))['request_id'],'q1')
    def test_RR_can_differ_FIFO(self):self.assertEqual(actor('RR_DYN')(s([q(1,'D'),q(2,'C')]))['request_id'],'q2')
    def test_RR_alternates(self):
        a=actor('RR_DYN');self.assertEqual(a(s([q(1,'C'),q(2,'D')]))['request_id'],'q1');self.assertEqual(a(s([q(1,'C'),q(2,'D')]))['request_id'],'q2')
    def test_RR_skip_and_advance(self):
        a=actor('RR_DYN');a(s([q(1,'D')]));self.assertEqual(a.rr.turn,'C')
    def test_RR_busy_preserves_turn(self):
        a=actor('RR_DYN');self.assertEqual(a(s([q(1)],[('CPU',1)]*3+[('GPU',1)]))['kind'],'RESOURCE_WAIT');self.assertEqual(a.rr.turn,'C')
    def test_faster_GPU(self):self.assertEqual(actor(nom=Nominal(.3,.1))(s([q(1)]))['route'],'GPU')
    def test_faster_CPU(self):self.assertEqual(actor()(s([q(1)]))['route'],'CPU')
    def test_contention_changes_choice(self):
        a=actor(nom=Nominal(.1,.12));self.assertEqual(a(s([q(1)],[('CPU',1)]))['route'],'GPU')
    def test_nonexecution_owner_not_contention(self):self.assertEqual(actor(nom=Nominal(.1,.12))(s([q(1)],[('CPU',2)]))['route'],'CPU')
    def test_temperature_changes_choice(self):self.assertEqual(actor(nom=Nominal(.1,.15))(s([q(1)],T=36))['route'],'GPU')
    def test_CPU_partial_capacity(self):self.assertEqual(actor()(s([q(1)],[('CPU',2)]*2))['route'],'CPU')
    def test_CPU_full_GPU_only(self):self.assertEqual(actor()(s([q(1)],[('CPU',2)]*3))['route'],'GPU')
    def test_GPU_full_CPU_only(self):self.assertEqual(actor(nom=Nominal(.3,.1))(s([q(1)],[('GPU',1)]))['route'],'CPU')
    def test_hash_tie_no_device_priority(self):
        for i in range(1,10):
            x=q(i);a=actor(nom=Nominal(.1,.1));r=a(s([x]))['route'];self.assertEqual(r,min(('CPU','GPU'),key=lambda r:route_tie(x['request_id'],r)))
    def test_C_response_excludes_later_stages(self):
        a=actor(nom=Nominal(tail=99));a(s([q(1)]));self.assertAlmostEqual(a.calls[-1]['estimates'][0]['response_after_dispatch_s'],.11)
    def test_D_response_includes_persist(self):
        a=actor();a(s([q(1,'D')]));self.assertAlmostEqual(a.calls[-1]['estimates'][0]['response_after_dispatch_s'],.14)
    def test_empty_is_resource_wait(self):self.assertEqual(actor()(s([]))['kind'],'RESOURCE_WAIT')
    def test_immutable_state(self):
        st=s([q(1)],[('CPU',1)]);old=copy.deepcopy(st);actor()(st);self.assertEqual(st,old)
    def test_future_rejected(self):
        st=s([q(21)]);
        with self.assertRaises(ValueError):actor()(st)
    def test_invalid_nominal_rejected(self):
        with self.assertRaises(ValueError):actor(nom=Nominal(float('nan')))(s([q(1)]))
    def test_unknown_route_rejected(self):
        with self.assertRaises(ValueError):actor()(s([q(1)],[('NPU',1)]))
    def test_capacity_violation_rejected(self):
        with self.assertRaises(ValueError):actor()(s([q(1)],[('CPU',1)]*4))
if __name__=='__main__':unittest.main(verbosity=2)
