"""Hand-worked sequencing/routing tests; no engine/learning/device executions."""
import copy
import unittest
from tools import d1_ie_dispatch as x


def ticket(name, ordinal, task='classification', arrival=35., due=1.5):
    return dict(id=name, ordinal=ordinal, task=task,
        priority='urgent' if task=='classification' else 'normal',
        arrival_ns=int(arrival*1e9), deadline_offset_ns=int(due*1e9))


def controller(rule='FIFO'):
    # Real Controller logic with a hand-calculated service table, no plant state.
    c = object.__new__(x.Controller)
    c.public_policy = x.POLICIES[('FIFO','SPT','EDD').index(rule)]
    c.rule = rule; c.t = 30.
    c.estimates = {'classification_CPU_urgent':[100e6,100e6,0.,0.,800e6],
                  'classification_GPU_urgent':[200e6,200e6,0.,0.,100e6],
                  'detection_CPU_normal':[200e6,200e6,100e6,0.,100e6]}
    return c


def lanes():
    return {b:dict(request=None, phase='AVAILABLE', since=35e9, dispatch=None) for b in ('CPU','GPU')}


def decide(c, qs, ls=None, now=35.):
    return c.decide(None, qs, ls or lanes(), int(now*1e9), {}, None, None)


class Rules(unittest.TestCase):
    def test_fifo_spt_edd_are_different(self):
        qs=[ticket('old-normal',0,'detection',35.,.3),ticket('new-urgent',1)]
        self.assertEqual(decide(controller('FIFO'),qs)['selected']['request_id'],'old-normal')
        self.assertEqual(decide(controller('SPT'),qs)['selected']['request_id'],'new-urgent')
        self.assertEqual(decide(controller('EDD'),qs)['selected']['request_id'],'old-normal')

    def test_ect_uses_lane_end_not_response(self):
        # CPU response .2s / release1s; GPU response .4s / release.5s => GPU.
        d=decide(controller(),[ticket('q',0)])
        self.assertEqual(d['selected']['backend'],'GPU')
        self.assertEqual(d['predicted_lane_end_s'],35.5)

    def test_wait_includes_resource_occupancy(self):
        c=controller(); ls=lanes()
        ls['GPU']=dict(request=ticket('active',2),phase='EXECUTING',since=35e9,dispatch=35e9)
        d=decide(c,[ticket('q',0)],ls,35.1)
        # GPU remaining.4 + next.5=.9; CPU .1+1.0=1.1 => wait GPU.
        self.assertIsNone(d['selected']);self.assertEqual(d['chosen_backend'],'GPU')
        self.assertAlmostEqual(d['wait_until_ns']/1e9,35.5)
        ls['GPU']=lanes()['GPU']
        self.assertEqual(decide(c,[ticket('q',0)],ls,35.5)['selected']['backend'],'GPU')

    def test_response_does_not_release_lane(self):
        c=controller(); ls=lanes()
        ls['CPU']=dict(request=ticket('active',2),phase='WORKER_RELEASED',since=35.9e9,dispatch=35e9)
        d=decide(c,[ticket('normal',0,'detection',35.,6.)],ls,35.9)
        self.assertIsNone(d['selected']);self.assertAlmostEqual(d['wait_until_ns']/1e9,36.)

    def test_unknown_overrun_waits(self):
        ls=lanes();ls['CPU']=dict(request=ticket('active',2),phase='WORKER_RELEASED',since=36e9,dispatch=35e9)
        d=decide(controller(),[ticket('q',0)],ls,36.01)
        self.assertIsNone(d['selected']);self.assertNotIn('wait_until_ns',d)

    def test_ties_cpu_and_fifo(self):
        c=controller('SPT');c.estimates['classification_GPU_urgent']=copy.deepcopy(c.estimates['classification_CPU_urgent'])
        d=decide(c,[ticket('later',1),ticket('earlier',0)])
        self.assertEqual(d['selected'],dict(request_id='earlier',backend='CPU'))

    def test_causal_public_input(self):
        c=controller()
        with self.assertRaisesRegex(ValueError,'future'): decide(c,[ticket('q',0,arrival=36.)])
        ls=lanes();ls['CPU']['durations']=[]
        with self.assertRaisesRegex(ValueError,'private'): decide(c,[ticket('q',0)],ls)

    def test_no_hidden_deadline_or_aging_override(self):
        # Late request remains eligible and FIFO doesn't silently become EDF.
        qs=[ticket('old-normal',0,'detection',35.,6.),ticket('urgent',1,arrival=39.,due=1.5)]
        self.assertEqual(decide(controller('FIFO'),qs,now=42.)['selected']['request_id'],'old-normal')


if __name__=='__main__': unittest.main()
