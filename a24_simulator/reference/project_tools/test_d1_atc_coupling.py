import copy,unittest
from unittest.mock import patch
import numpy as np
import torch
from tools import d1_atc_coupling_policy as a
from tools import d1_atc_coupling_ppo as rl
from tools import d1_atc_coupling_study as s
from tools import d1_atc_coupling_controls as controls
from tools import d1_atc_repair_policy as old

def q(i,task="classification",units=1):
    return dict(id=str(i),ordinal=i,task=task,priority="urgent" if task=="classification" else "normal",arrival_ns=35e9,deadline_offset_ns=1.5e9 if task=="classification" else 6e9,work_units=units)
def lanes():return {b:dict(request=None,phase="AVAILABLE",since=35e9,dispatch=None) for b in ("CPU","GPU")}

class Coupling(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.f,i,_=a.hybrid.load();cls.initial=i["initial"]
    def encoded(self,arm="JNONE",qs=None,ls=None,now=35e9):
        c=a.Controller(self.f,self.initial,coupling=arm);qs=qs or [q(0),q(1,"detection")];ls=ls or lanes()
        e=a.bank(qs,ls,now,c.estimates,coupling=arm)
        return c,e,c.encode(qs,ls,now,e)
    def test_distinct_priors_samephysical_and_initialteacher(self):
        for arm in a.ARMS:
            c,e,x=self.encoded(arm)
            self.assertEqual(x["state"].shape,(218,));self.assertEqual(x["candidates"].shape,(32,57))
            full=a.bank([q(0),q(1,"detection")],lanes(),35e9,c.estimates,coupling="JP09")
            np.testing.assert_array_equal(e["physical_mask"],full["mask"])
            self.assertTrue(e["mask"][e["base"]]);self.assertFalse(np.any(e["mask"] & ~e["physical_mask"]))
            net=rl.ActorCritic(arm);dist,_=net(torch.from_numpy(x["state"])[None],torch.from_numpy(x["candidates"])[None],torch.from_numpy(x["mask"])[None])
            self.assertAlmostEqual(float(dist.logits[0,e["base"]].detach()),float(dist.logits.max().detach()),places=6)
            if arm in ("JP09","JP05"):self.assertAlmostEqual(float(dist.probs[0,e["base"]].detach()),a.PRIORS[arm],places=6)
            if arm=="JNONE":self.assertAlmostEqual(float(dist.probs[0,e["base"]].detach()),1/sum(e["mask"]),places=6)
    def test_route_envelope_preserveslogicalprimary(self):
        c,e,x=self.encoded("ATC_ROUTE")
        primary=e["actions"][e["base"]]["jobs"][0]["request_id"]
        for action,allowed in zip(e["actions"],e["mask"]):
            if allowed:self.assertTrue(any(j["request_id"]==primary for j in action["jobs"]))
        self.assertLess(sum(e["mask"]),sum(e["physical_mask"]))
    def test_score_min_job_prior_wait_and_logprob(self):
        ls=lanes();ls["CPU"].update(request=q(8,"detection"),phase="EXECUTING",dispatch=35e9)
        c,e,x=self.encoded("ATC_SCORE_RESIDUAL",[q(0)],ls,35.1e9)
        net=rl.ActorCritic("ATC_SCORE_RESIDUAL");dist,_=net(torch.from_numpy(x["state"])[None],torch.from_numpy(x["candidates"])[None],torch.from_numpy(x["mask"])[None])
        wait=next(i for i,z in enumerate(e["actions"]) if z and z["kind"]=="resource_wait")
        start=e["base"]
        self.assertAlmostEqual(float((dist.logits[0,start]-dist.logits[0,wait]).detach()),1.,places=6)
        sample=torch.multinomial(dist.probs[0],1,generator=torch.Generator().manual_seed(23))
        self.assertAlmostEqual(float(dist.log_prob(sample).detach()),float(torch.log(dist.probs[0,sample]).detach()),places=6)
        c,e,x=self.encoded("ATC_SCORE_RESIDUAL",[q(0,"detection")],ls,35.1e9)
        self.assertEqual(sum(e["mask"]),1)
        dist,_=net(torch.from_numpy(x["state"])[None],torch.from_numpy(x["candidates"])[None],torch.from_numpy(x["mask"])[None]);self.assertTrue(torch.isfinite(dist.logits[e["mask"][None]]).all())
    def test_reference_and_teacher_do_not_minimizefinish(self):
        c,e,x=self.encoded();c.estimates["classification_CPU_urgent"]=[.4e9]*5;c.estimates["classification_GPU_urgent"]=[.01e9]*5
        ds,backend=a.representative(c.estimates,q(0));self.assertEqual(backend,"CPU")
        e=a.bank([q(0)],lanes(),35e9,c.estimates,coupling="JNONE")
        self.assertEqual(e["actions"][e["base"]]["jobs"][0]["backend"],"CPU")
    def test_proposal_never_calls_benchmark_or_EFT(self):
        with patch.object(controls,"greedy_action",side_effect=AssertionError("benchmark inproposal")),patch.object(s.oldstudy.mobile,"eft",side_effect=AssertionError("EFT")),patch.object(a.p.Controller,"__call__",side_effect=AssertionError("legacy")):
            for arm in a.ARMS:
                net=rl.ActorCritic(arm);c=a.Controller(self.f,self.initial,net,True,coupling=arm)
                out=c({},[q(0),q(1,"detection")],lanes(),35e9,{},None,None)
                self.assertIsNotNone(out["selected"]);self.assertEqual(c.stats["fallback"],0)
    def test_all_masks_unknown_and_rank_job_binding(self):
        c,e,x=self.encoded(qs=[q(0,"detection",3),q(1,"classification",1)])
        order={r:i for i,r in enumerate(e["ranked_ids"])}
        for i,act in enumerate(e["actions"]):
            if not act:continue
            for slot,job in enumerate(act.get("jobs",[act.get("target")])):
                self.assertEqual(x["candidates"][i,53+slot*2],order[job["request_id"]])
        e["mask"][:]=False
        with self.assertRaises(ValueError):rl.ActorCritic("JNONE")(torch.from_numpy(x["state"])[None],torch.from_numpy(x["candidates"])[None],torch.from_numpy(e["mask"])[None])
        e=a.bank([q(0)],lanes(),35e9,{})
        self.assertIsNone(e["scores"]["0"])
        self.assertEqual(c.encode([q(0)],lanes(),35e9,e)["candidates"][e["base"],54],10.)
    def frame(self,l,x,action,informative,target):
        with torch.no_grad():dist,val=l.network(torch.from_numpy(x["state"])[None],torch.from_numpy(x["candidates"])[None],torch.from_numpy(x["mask"])[None])
        return dict(state=x["state"].copy(),candidates=x["candidates"].copy(),mask=x["mask"].copy(),action=action,informative=informative,
                    old_value=val[0].numpy() if informative else None,logprob=float(dist.log_prob(torch.tensor([action]))) if informative else None,
                    target=np.array([target,.1,.01,0,0,0,0,0,0,.1],dtype=np.float32),valid=np.ones(10,dtype=bool))
    def test_native_update_partial_restore_and_schema(self):
        c,e,x=self.encoded();deps=dict(schema=a.SCHEMA,arm="JNONE",sequencing="ATC")
        l=rl.Learner(41,deps);options=list(np.flatnonzero(e["mask"]))
        for i in range(9):l.add([self.frame(l,x,int(options[i%len(options)]),True,1+i*.2)],np.zeros(9,np.float32),np.ones(10,bool),dict(fallbacks=0))
        self.assertEqual(len(l.logs),1);self.assertGreater(l.logs[0]["actor_gradient_max"],0);self.assertEqual(len(l.pending),1)
        restored=rl.Learner.from_snapshot(l.snapshot(),deps)
        self.assertEqual(s.payload_digest(l.snapshot()),s.payload_digest(restored.snapshot()))
        self.assertTrue(torch.equal(torch.randperm(19,generator=l.shuffle_rng),torch.randperm(19,generator=restored.shuffle_rng)))
        self.assertTrue(torch.equal(torch.multinomial(torch.tensor([.2,.8]),7,True,generator=l.action_rng),torch.multinomial(torch.tensor([.2,.8]),7,True,generator=restored.action_rng)))
        with self.assertRaises(ValueError):rl.Learner.from_snapshot(dict(l.snapshot(),schema=old.SCHEMA),deps)
    def test_all_forced_batch_critic_only_no_fakechoice(self):
        c,e,x=self.encoded("ATC_ROUTE",[q(0,"detection")]);deps=dict(schema=a.SCHEMA,arm="ATC_ROUTE",sequencing="ATC")
        l=rl.Learner(47,deps);before=copy.deepcopy(l.network.actor.state_dict())
        for i in range(8):l.add([self.frame(l,x,e["base"],False,1.)],np.zeros(9,np.float32),np.ones(10,bool),dict(fallbacks=0))
        self.assertTrue(l.logs[0]["critic_only"]);self.assertEqual(l.logs[0]["sampled_choices"],0)
        self.assertTrue(all(torch.equal(v,l.network.actor.state_dict()[k]) for k,v in before.items()));self.assertGreater(l.steps,0)
    def test_frozen_domain_counts_caps_and_no_old_data_rewrite(self):
        self.assertEqual([len(s.cases(v)) for v in (s.TRAIN,s.DEV,s.CONFIRM)],[256,32,64])
        self.assertEqual(3*s.budget.PROFILES["model"]["environments"]+s.budget.PROFILES["control"]["environments"],7500)
        self.assertFalse(any("EFT" in role for role in s.BASES));self.assertEqual(len(s.BASES),6)
        for case in s.cases(s.DEV):
            self.assertLess(max(q["arrival_ns"] for q in case["requests"]),120e9)
            self.assertEqual(sum(q["work_units"] for q in case["requests"]),len(case["requests"])*(2 if case["factor"] in ("uniform2","variable123") else 1))

if __name__=="__main__":unittest.main()
