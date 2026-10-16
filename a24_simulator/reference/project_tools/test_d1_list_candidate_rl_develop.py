"""Postencoding selection contract; no native simulation or optimizer."""
import unittest
import numpy as np
import torch
from tools import d1_list_candidate_rl as c
from tools import d1_list_candidate_rl_develop as d

class FixedNetwork(torch.nn.Module):
    def forward(self,state,candidates,mask):
        scores=torch.arange(8,dtype=torch.float32)[None].expand(len(state),-1)
        return torch.distributions.Categorical(logits=scores.masked_fill(~mask,-torch.inf)),torch.zeros(len(state),6)

class Contract(unittest.TestCase):
    def fixture(self):
        frozen,case=c.p.inputs(c.p.BUNDLE);model=FixedNetwork()
        controllers=[cls(frozen,case['initial'],c.PPO,network=model,deterministic=True,feature_variant='head2+C_next') for cls in (c.Controller,d.EncodedNoWait)]
        queue=[dict(id='C',task='classification',priority='urgent',ordinal=0,arrival_ns=35e9,deadline_offset_ns=1.5e9),dict(id='D',task='detection',priority='normal',ordinal=1,arrival_ns=35e9,deadline_offset_ns=6e9)]
        lanes={b:dict(request=None,phase='AVAILABLE',since=35e9,dispatch=None) for b in ('CPU','GPU')}
        for x in controllers:
            for i,q in enumerate(queue):x.on_public_event(dict(at_ns=35e9,event_seq=i+1,request_id=q['id'],backend=None,event='arrived',ticket=q))
            x.observe(35e9,lanes)
        return controllers,queue,lanes
    def test_original_bank_and_all_input_bytes_preserved(self):
        (a,b),q,l=self.fixture();aa=a.bank(q,l,35e9);bb=b.bank(q,l,35e9)
        self.assertEqual(aa,bb)
        ea=a.encode(q,l,35e9,aa);eb=b.encode(q,l,35e9,bb)
        for name in ('state','candidates','mask'):self.assertEqual(ea[name].tobytes(),eb[name].tobytes())
        before=[eb[k].tobytes() for k in ('state','candidates','mask')]
        original=a.choose(ea,aa,q);changed=b.choose(eb,bb,q)
        self.assertGreater(aa[original]['wait'],0);self.assertEqual(bb[changed]['wait'],0)
        self.assertEqual(before,[eb[k].tobytes() for k in ('state','candidates','mask')])
        self.assertEqual(eb['state'][7],len(bb)/8)
    def test_forced_immediate_still_uses_full_encoding(self):
        (_,b),q,l=self.fixture();b.credit=0
        q=q[:1];actions=b.bank(q,l,35e9);encoded=b.encode(q,l,35e9,actions)
        idx=b.choose(encoded,actions,q)
        self.assertTrue(encoded['mask'][idx]);self.assertEqual(actions[idx]['wait'],0)
        self.assertEqual(encoded['mask'].sum(),len(actions))
    def test_diagnosis_never_authorizes_learning(self):
        budget=d.Budget.__new__(d.Budget)
        with self.assertRaisesRegex(ValueError,'does not authorize training'):budget.guard(learning=True)

if __name__=='__main__':unittest.main()
