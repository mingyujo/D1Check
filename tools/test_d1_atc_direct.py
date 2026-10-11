"""Public frozen fixtures and pure PPO equivalence; no environment runner here."""
import copy
import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import torch

from tools import d1_atc_direct_policy as a
from tools import d1_atc_direct_ppo as rl
from tools import d1_list_candidate_rl_training as native


def ticket(name,task,at=35.,ordinal=0):
    return dict(id=name,task=task,priority="urgent" if task=="classification" else "normal",
        arrival_ns=round(at*1e9),deadline_offset_ns=1500000000 if task=="classification" else 6000000000,ordinal=ordinal)


def lanes():
    return {b:dict(request=None,phase="AVAILABLE",since=35e9,dispatch=None) for b in ("CPU","GPU")}


class Fixed(torch.nn.Module):
    schema_id=a.SCHEMA
    def __init__(self,slot):
        super().__init__();self.slot=slot
    def forward(self,state,vectors,mask):
        x=torch.zeros((len(state),7));x[:,self.slot]=100.
        return torch.distributions.Categorical(logits=x.masked_fill(~mask,-torch.inf)),torch.zeros((len(state),6))


class Contracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.f,initial,_=a.hybrid.load();cls.initial=initial["initial"];cls.means=a.p.profile(cls.f)
    def controller(self,**kw):return a.Controller(self.f,self.initial,**kw)

    def test_atc_formula_and_parameter_mean(self):
        qs=[ticket("C","classification"),ticket("D","detection",ordinal=1)]
        scores=a.atc_scores(qs,self.means,35e9)
        reps=[a.representative(self.means,q)[0] for q in qs];mean=sum(x[0] for x in reps)/2
        for q,(occ,reply) in zip(qs,reps):
            w=2 if q["priority"]=="urgent" else 1
            index=w/occ*math.exp(-max(0,q["deadline_offset_ns"]/1e9-reply)/(2*mean))
            self.assertAlmostEqual(scores[q["id"]],-math.log(index))
        changed=a.atc_scores(qs,self.means,35e9,a.Settings(urgent_weight=.000001))
        self.assertNotEqual(min(scores,key=scores.get),min(changed,key=changed.get))

    def test_coverage_fifo_pair_and_padding(self):
        c,c2,d=ticket("C","classification"),ticket("C2","classification",35.1,2),ticket("D","detection",ordinal=1)
        e=a.bank([c,c2,d],lanes(),35.2e9,self.means)
        self.assertEqual([q["id"] for q in e["slots"]],["C","D"])
        self.assertTrue(e["mask"][3]);self.assertFalse(e["mask"][4:].any())
        self.assertFalse(a.legal(dict(request_id="C2",backend="CPU"),[c,c2,d],lanes()))
        small=a.bank([d],lanes(),35e9,self.means)
        self.assertEqual(list(np.flatnonzero(small["mask"])),[2])

    def test_unavailable_after_response_and_unsupported_pairs(self):
        c,d=ticket("C","classification"),ticket("D","detection",ordinal=1)
        busy=lanes();busy["CPU"].update(request=d,phase="WORKER_RELEASED",dispatch=35e9)
        e=a.bank([c],busy,35.1e9,self.means)
        self.assertFalse(e["mask"][0]);self.assertTrue(e["mask"][1]);self.assertTrue(e["mask"][4])
        self.assertFalse(a.physical(dict(kind="bundle",jobs=[dict(request_id="C",backend="CPU"),dict(request_id="D",backend="CPU")]),[c,d],lanes()))
        self.assertFalse(a.legal(dict(request_id="D",backend="GPU"),[c,d],lanes()))

    def test_no_forecast_and_hidden_state_inputs(self):
        qs=[ticket("C","classification"),ticket("D","detection",ordinal=1)]
        c=self.controller(mode=a.RULE);e=a.bank(qs,lanes(),35e9,c.estimates)
        before=c.encode(qs,lanes(),35e9,e)
        c.h=1234.;c.hybrid_state["h"]=4321.;c.hybrid_state["slow"]=999.
        after=c.encode(qs,lanes(),35e9,e)
        np.testing.assert_array_equal(before["state"],after["state"])
        with patch.object(a.p.Controller,"place",side_effect=AssertionError("future placement")), \
             patch.object(a.p.Controller,"rollout",side_effect=AssertionError("queue rollout")), \
             patch.object(a.hybrid,"costs",side_effect=AssertionError("future costs")):
            out=c(None,qs,lanes(),35e9,{},None,None)
        self.assertIsNotNone(out["selected"]);self.assertEqual(c.online_forecast_calls,0)

    def test_public_tail_and_unknown_estimates(self):
        c=self.controller(mode=a.RULE);q=ticket("C","classification")
        qa=[q,ticket("C2","classification",35.1,1)];qb=[q,ticket("C2","classification",35.2,1)]
        ea=a.bank(qa,lanes(),35.3e9,c.estimates);eb=a.bank(qb,lanes(),35.3e9,c.estimates)
        self.assertNotEqual(c.encode(qa,lanes(),35.3e9,ea)["state"][5],c.encode(qb,lanes(),35.3e9,eb)["state"][5])
        c.estimates[a.p.key(q,"CPU")]=[float("nan")]*5
        e=a.bank([q],lanes(),35e9,c.estimates)
        self.assertTrue(e["mask"][0]);self.assertTrue(e["mask"][1])
        self.assertIsNotNone(c(None,[q],lanes(),35e9,{},None,None)["selected"])

    def test_resource_hold_phase_and_arrival_cancel(self):
        c=self.controller(network=Fixed(4));q=ticket("C","classification");d=ticket("D","detection")
        busy=lanes();busy["CPU"].update(request=d,phase="EXECUTING",dispatch=35e9)
        out=c(None,[q],busy,35.01e9,{},None,None)
        self.assertEqual(out["action_kind"],"resource_wait");self.assertGreater(out["wait_until_ns"],35.01e9)
        busy["CPU"]["phase"]="OUTPUT_READY"
        self.assertEqual(c(None,[q],busy,35.02e9,{},None,None)["reason"],"resource_hold")
        q2=ticket("C2","classification",35.03,1)
        c.on_public_event(dict(event_seq=1,at_ns=35.03e9,event="arrived",request_id="C2",backend=None,ticket=q2))
        self.assertIsNone(c.hold)
        self.assertFalse(a.physical(dict(kind="resource_wait",target=dict(request_id="C",backend="CPU")),[q],lanes()))

    def test_pair_second_failure_preserves_queue(self):
        c=self.controller(network=Fixed(3));q,d=ticket("C","classification"),ticket("D","detection",ordinal=1)
        for i,x in enumerate((q,d),1):
            c.on_public_event(dict(event_seq=i,at_ns=35e9,event="arrived",request_id=x["id"],backend=None,ticket=x))
        out=c(None,[q,d],lanes(),35e9,{},None,None);self.assertEqual(out["action_kind"],"bundle")
        c.on_public_event(dict(event_seq=3,at_ns=35e9,event="dispatch_ns",request_id="C",backend="GPU"))
        current=lanes();current["GPU"].update(request=q,phase="ASSIGNED",dispatch=35e9)
        current["CPU"].update(request=ticket("other","detection"),phase="ASSIGNED",dispatch=35e9)
        queue=[d];c(None,queue,current,35e9,{},None,None)
        self.assertEqual(queue,[d]);self.assertEqual(c.stats["pair_cancelled"],1)

    def test_duplicate_revision_and_abi_fallback(self):
        q=ticket("C","classification");c=self.controller(mode=a.RULE)
        c(None,[q],lanes(),35e9,{},None,None)
        self.assertIsNone(c(None,[q],lanes(),35e9,{},None,None)["selected"])
        c=self.controller(network=Fixed(0));c.network.schema_id="wrong"
        out=c(None,[q],lanes(),35e9,{},None,None)
        self.assertIsNotNone(out["selected"]);self.assertEqual(c.stats["fallback"],1)
        with self.assertRaises(ValueError):c(None,[dict(q,hidden_duration=123)],lanes(),36e9,{},None,None)
        with self.assertRaises(ValueError):self.controller()(None,[ticket("future","classification",36)],lanes(),35e9,{},None,None)

    def test_response_and_available_are_separate(self):
        c=self.controller();q=ticket("C","classification")
        events=[("arrived",35e9),("dispatch_ns",35e9)]+[(v,(35+(i+1)*.01)*1e9) for i,v in enumerate(a.FIELDS)]
        for seq,(kind,t) in enumerate(events,1):
            e=dict(event_seq=seq,at_ns=t,event=kind,request_id="C",backend=None if kind=="arrived" else "CPU")
            if kind=="arrived":e["ticket"]=q
            c.on_public_event(e)
            if kind=="output_ready_ns":
                self.assertIn("C",c.responses);self.assertNotIn(a.p.key(q,"CPU"),c.observations)
        self.assertEqual(c.observations[a.p.key(q,"CPU")]["n"],1)
        with self.assertRaises(ValueError):c.on_public_event(dict(e,event_seq=seq))


def fake_frames(network):
    fs=[]
    state=torch.zeros((1,90));vectors=torch.zeros((1,7,23));vectors[0,0,4]=1;vectors[0,1,7]=1
    mask=torch.tensor([[True,True,False,False,False,False,False]])
    with torch.no_grad():dist,value=network(state,vectors,mask)
    for i in range(4):
        action=i%2
        fs.append(dict(state=state[0].numpy().copy(),candidates=vectors[0].numpy().copy(),mask=mask[0].numpy().copy(),
            action=action,informative=True,logprob=float(dist.log_prob(torch.tensor([action]))),
            old_value=value[0].numpy().copy(),target=np.array([1. if action==0 else -1.,1.,0.,.1,0.,.2],dtype=np.float32),
            valid=np.ones(6,dtype=bool)))
    return fs


class PPO(unittest.TestCase):
    def test_native_loss_equivalence_gradient_and_resume(self):
        l=rl.Learner(11,{"fixture":"synthetic no environment"})
        frames=fake_frames(l.network);episodes=[copy.deepcopy(frames) for _ in range(8)]
        prep=rl.prepare(l.network,episodes,l.multipliers)
        ref=a.native.ppo_losses(l.network,episodes,l.multipliers)
        parts=native.minibatch_losses(l.network,prep,torch.arange(prep["n"]))
        self.assertAlmostEqual(float(parts["loss"].detach()),float(ref["loss"].detach()),places=5)
        costs=np.array([1.,0.,.1,0.,.2],dtype=np.float32);valid=np.ones(6,dtype=bool)
        for _ in range(3):l.add(frames,costs,valid,{})
        with tempfile.TemporaryDirectory() as tmp:
            file=Path(tmp)/"fixture.pt";l.save(file);r=rl.Learner.load(file,l.dependencies)
            self.assertEqual(native.state_digest(l.snapshot()),native.state_digest(r.snapshot()))
            for _ in range(5):
                l.add(frames,costs,valid,{});r.add(frames,costs,valid,{})
        self.assertEqual(native.state_digest(l.snapshot()),native.state_digest(r.snapshot()))
        self.assertTrue(l.optimizer.state);self.assertTrue(l.logs[-1]["actor_changed"])
        self.assertGreater(l.logs[-1]["actor_gradient_max"],0.)
        self.assertEqual(l.multipliers[0],1.);self.assertEqual(l.multipliers[4],1.)

    def test_independent_rng_and_model_input_errors(self):
        l=rl.Learner(11,{})
        before=l.action_rng.get_state().clone();other=rl.Learner(23,{})
        torch.randperm(10,generator=other.shuffle_rng)
        torch.multinomial(torch.ones(7),1,generator=other.action_rng)
        self.assertTrue(torch.equal(before,l.action_rng.get_state()))
        with self.assertRaises(ValueError):
            l.network(torch.zeros(1,56),torch.zeros(1,7,23),torch.ones(1,7,dtype=torch.bool))
        with self.assertRaises(ValueError):
            l.network(torch.zeros(1,90),torch.zeros(1,7,23),torch.zeros(1,7,dtype=torch.bool))


if __name__=="__main__":
    unittest.main()
