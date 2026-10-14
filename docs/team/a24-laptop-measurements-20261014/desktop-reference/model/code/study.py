"""Registered, resumable bounded runner; DEV improvements precede sealed FINAL."""
import os
for _key in ("OMP_NUM_THREADS","MKL_NUM_THREADS","OPENBLAS_NUM_THREADS"):os.environ[_key]="1"
import argparse,copy,gzip,hashlib,json,random,shutil,sys,time,traceback,functools
from pathlib import Path
import numpy as np
import torch
from common import *
import candidates as candidate
import cases
import plant
import audit
import ppo
import recovery_io

RULES=("FIFO_READY","RR_READY","GREEDY_READY_V17","SPT","WSPT","EDD","LST","ATC","ENERGY_EDD","THERMAL_EDD")
WAIT_RULES=("FIFO_READY","ATC","THERMAL_EDD")
LAYERS=("M0_frozen35","M1_coupled","thermal_strong_Wscaled")
ARMS=dict(GATE=("ATC",False,"GATE"),NONDELAY=("ATC",False,"DENSE"),ATC_WAIT=("ATC",True,"DENSE"),
          EDD_WAIT=("EDD",True,"DENSE"),DIRECT_WAIT=("FULL",True,"DENSE"))
DEV_CASES=(1,3,6,9)
@functools.lru_cache(maxsize=16)
def profile(device,layer):
    return read(VENDOR/"profiles"/f"{device}_G36_{layer}.json")
def load_gz(path):
    with gzip.open(path,"rt",encoding="utf-8") as f:return json.load(f)
def netsha(net):
    h=hashlib.sha256()
    for k,v in net.state_dict().items():h.update(k.encode());h.update(v.detach().numpy().tobytes())
    return h.hexdigest()

def register():
    path=OUT/"REGISTRATION.json"
    if path.exists():return read(path)
    protected={str(p):sha(p) for p in (ROOT/"outputs/GROUNDED-EXPLORATION-36-runtime.zip",
        ROOT/"outputs/EXISTING-DATA-DYNAMICS-35-runtime.zip",ROOT/"work/repo/docs/ROLLING_ATC_RL_COMPLETION_PLAN_20261014.md")}
    sources={str(p.relative_to(WORK)):sha(p) for p in sorted((WORK/"code").glob("*.py"))}
    sources.update({str(p.relative_to(WORK)):sha(p) for p in sorted((VENDOR/"tools").glob("*.py"))})
    profiles={f"{d}/{m}":sha(VENDOR/"profiles"/f"{d}_G36_{m}.json") for d in ("A24","S26") for m in LAYERS}
    # Materialize every split before policy outcomes, and test arrival/content disjointness.
    sets={};input_hashes={};roster=[]
    for split,count in (("P0",16),("P1",2),("TRAIN",4096),("DEV",2),("FINAL",5)):
        sets[split]=set()
        for index in range(count):
            for d in ("A24","S26"):
                p=profile(d,"M1_coupled")
                indices=range(12) if split!="TRAIN" else [index%12]
                for ci in indices:
                    qs=cases.requests(p,ci,split,index)
                    h=digest(qs);sets[split].add(h)
                    roster.append(dict(split=split,index=index,device=d,case=ci,arrival_seed=cases.arrival_seed(split,index),request_sha=h))
        input_hashes[split]=digest(sorted(sets[split]))
    for s in sets:
        for t in sets:
            if s!=t and sets[s]&sets[t]:raise ValueError("cross-split request leakage")
    save(OUT/"INPUT_ROSTER_HASHES.json",roster)
    reg=dict(id="ROLLING-ATC-RL-37-V2",registered_unix=stamp(),goal=dict(energy_reduction=.10,mean_AP_reduction_c=.5),
      alphas=list(ALPHAS),alpha_contract="urgent and normal separately; all requests completed at actual AVAILABLE<=120",
      main_energy="0..180s",secondary_energy="0..120s",mean_AP="35..180s",input_schema=candidate.SCHEMA,
      candidate_spec=candidate.SPEC,training_seeds=list(SEEDS),settings=asdict_settings(),cases=list(cases.SPECS),
      layers=list(LAYERS),physical_fits=0,source_sha=sources,profile_sha=profiles,protected=protected,
      input_split_sha=input_hashes,source_legacy37_preserved=True,environment_cap=137712,training_cap=99840,
      stage_checkpoints=[256,1024,4096],worker_cap_own=1,total_heavy_workers_cap=2,storage_reserve_bytes=8*1024**3,
      gate="DEV improvement and feasibility; no FINAL tuning",hardware_validated=False,new_APK=0,new_device=0,
      goal_is_not_physics_fit_objective=True)
    save(path,reg);return reg
def asdict_settings():
    from dataclasses import asdict
    return asdict(ppo.Settings())

class Store:
    def __init__(self):
        self.reg=register();self.progress_path=OUT/"PROGRESS.json";self.n=0;self.failures=0;self.rows=[]
        self.recovery=recovery_io.reconcile(OUT)
        self.receipts=self.recovery["receipts"];self.rows=self.recovery["rows"]
        self.n=sum(r["event"]=="START" for r in self.receipts)
        self.failures=sum(r["event"]=="FAIL" for r in self.receipts)
        self.byid={r["identity"]:r for r in self.rows}
        self.consumed={r["identity"] for r in self.receipts if r["event"]=="START"}
        self.receipts_byid={}
        for receipt in self.receipts:self.receipts_byid.setdefault(receipt["identity"],[]).append(receipt)
    def status(self,phase,**kw):
        save(self.progress_path,dict(phase=phase,unix=stamp(),pid=os.getpid(),environments_started=self.n,failures=self.failures,**kw))
    def check_sources(self):
        for name,h in self.reg["source_sha"].items():
            if sha(WORK/name)!=h:raise ValueError("source changed after registration: "+name)
        for name,h in self.reg["protected"].items():
            if name.endswith("ROLLING_ATC_RL_COMPLETION_PLAN_20261014.md"):continue
            if sha(name)!=h:raise ValueError("protected original changed")
    def run(self,identity,d,layer,ci,split,index,controller,training=False):
        if identity in self.byid:
            row=self.byid[identity]
            return load_gz(row["raw_path"]),row,True
        if identity in self.consumed:raise recovery_io.RecoveryError("identity already consumed; inspect preserved failure: "+identity)
        if self.n>=self.reg["environment_cap"]:raise ValueError("environment cap")
        if shutil.disk_usage(OUT).free<self.reg["storage_reserve_bytes"]:raise ValueError("disk reserve")
        p=profile(d,layer);qs=cases.requests(p,ci,split,index);proxy=profile(d,"M1_coupled")
        self.n+=1;tick=time.perf_counter()
        start=dict(event="START",identity=identity,unix=stamp(),number=self.n,training=training,request_sha=digest(qs),
                   source_generation=getattr(self,"generation",{}).get("generation"))
        recovery_io.append_jsonl(OUT/"receipts.jsonl",start);self.receipts.append(start);self.consumed.add(identity)
        self.receipts_byid.setdefault(identity,[]).append(start)
        self.run_progress(identity,"START")
        try:
            if split=="FINAL" and isinstance(controller,ppo.Controller):controller.capture_inputs=True
            raw=plant.simulate(p,qs,controller,proxy,cases.environment_seed(split,index),split="train" if training else "dev" if split=="DEV" else "confirm")
            raw["nominal_resident_w"]=proxy["grounded36"]["baseline_w"]
            proof=audit.physical(raw,qs);raw["request_sha"]=digest(qs);raw["physical_audit"]=proof
            artifacts=[];archive=None
            if training and isinstance(controller,ppo.Controller):
                ppo.labels(controller,raw,controller.settings,controller.family)
                from orchestrator import save_rollout
                archive=save_rollout(self,identity,controller);artifacts.append(archive)
            elif split=="FINAL" and isinstance(controller,ppo.Controller):
                from completion_audit import persist_eval
                archive=persist_eval(controller,identity,getattr(self,"generation",{}).get("generation"));artifacts.append(archive)
            path=OUT/"raw"/d/(identity+".json.gz")
            row=dict(identity=identity,device=d,layer=layer,case=cases.SPECS[ci][0],case_index=ci,split=split,index=index,
                environment_seed=cases.environment_seed(split,index),arrival_seed=cases.arrival_seed(split,index),
                policy=getattr(controller,"name",getattr(controller,"kind","PPO")),alpha=getattr(controller,"alpha",None),
                metrics=raw["metrics"],raw_path=str(path),wall_s=time.perf_counter()-tick,
                queue_max=max((x["queue"] for x in controller.decisions),default=0),wait_used_ns=raw["wait_used_ns"],
                decisions=len(controller.decisions),physical_PASS=True,source_generation=start["source_generation"])
            if archive:row["training_archive" if training else "evaluation_archive"]=archive
            row=recovery_io.commit_environment(OUT,row,raw,artifacts,rows=self.byid,receipts=self.receipts,receipt_index=self.receipts_byid)
            self.rows.append(row);self.byid[identity]=row
            self.run_progress(identity,"COMPLETE")
            return raw,row,False
        except Exception:
            prepared=(OUT/"commits"/(identity+".json")).exists()
            failure=dict(event="ERROR" if prepared else "FAIL",identity=identity,unix=stamp(),traceback=traceback.format_exc())
            recovery_io.append_jsonl(OUT/"receipts.jsonl",failure);self.receipts.append(failure)
            self.receipts_byid.setdefault(identity,[]).append(failure)
            self.failures+=not prepared;self.run_progress(identity,failure["event"])
            raise
    def run_progress(self,identity,event):
        previous=read(self.progress_path) if self.progress_path.exists() else dict(phase="RECOVERY")
        previous.update(unix=stamp(),pid=os.getpid(),environments_started=self.n,failures=self.failures,last_identity=identity,last_event=event)
        save(self.progress_path,previous)
    def rollout(self,identity,controller):
        data,frames=ppo.pack([controller.frames])
        path=OUT/"rollouts"/(identity+".npz");path.parent.mkdir(parents=True,exist_ok=True)
        if path.exists():return dict(path=str(path),sha=sha(path),bytes=path.stat().st_size)
        np.savez_compressed(path,**{k:v.numpy() for k,v in data.items()},
          time_ns=np.array([f["time_ns"] for f in frames],np.int64),
          original_sizes=np.array([[len(f["requests"]),len(f["features"])] for f in frames],np.int32),
          input_sha=np.array([f["input_sha"] for f in frames]))
        return dict(path=str(path),sha=sha(path),bytes=path.stat().st_size)

def p0(store):
    completed=OUT/"P0_COMPLETE.json"
    if completed.exists():return read(completed)
    store.status("P0")
    # Numerically meaningful tests: dispatch/AVAILABLE, reward telescope, native update, exact pending resume.
    learner=ppo.Learner(SEEDS[0],"S26");proofs=[];walls=[]
    for i in range(8):
        d="S26";layer="M1_coupled";controller=learner.controller(ALPHAS[i%5],collect=True)
        raw,row,cached=store.run(f"P0_NATIVE_{i}",d,layer,3,"P0",i,controller,True)
        if cached:raise ValueError("P0 partial collection must resume from its saved native state, not duplicate labels")
        meta=learner.add(controller,raw);archive=store.rollout(row["identity"],controller);proofs.append(meta);walls.append(row["wall_s"])
        learner.save(OUT/"P0_latest.pt")
        if i==2:
            before=netsha(learner.net);l2=ppo.Learner.load(OUT/"P0_latest.pt")
            if netsha(l2.net)!=before or not torch.equal(learner.action_rng.get_state(),l2.action_rng.get_state()) or len(l2.pending)!=3:
                raise ValueError("partial replay/Adam/RNG mismatch")
            learner=l2
    if learner.steps==0:raise ValueError("no Adam update")
    # Representative policies keep the measured phase/response/availability contract.
    for d in ("A24","S26"):
        for layer in ("M0_frozen35","M1_coupled"):
            r,row,_=store.run(f"P0_RULE_{d}_{layer}",d,layer,0,"P0",9,candidate.Rule("FIFO_READY"))
            walls.append(row["wall_s"])
    # Feature padding ABI and future-hidden test before actual execution.
    p=profile("S26","M1_coupled");dev=plant.g.Device(p,split="confirm",environment_seed=1,npu=True);dev.advance(35_000_000_000)
    view=plant.PublicView(dev,p);qs=cases.requests(p,3,"P0",10);nowqs=[q for q in qs if q["arrival_ns"]<=dev.now]
    a=candidate.build(view,nowqs);dev.seed=999999;b=candidate.build(view,nowqs)
    if ppo.input_digest(a)!=ppo.input_digest(b):raise ValueError("future realization leaked into input")
    if a["requests"].shape!=(24,24) or a["features"].shape!=(80,16) or len(a["global_state"])!=24:raise ValueError("ABI dimensions")
    result=dict(status="PASS",environments=12,native_updates=learner.updates,adam_steps=learner.steps,partial3_resume=True,
        reward_telescope_max=max(p["telescope_error"] for p in proofs),future_realization_invariance=True,
        phase_AVAILABLE_audit=True,wall_mean_s=float(np.mean(walls)),wall_p95_s=float(np.quantile(walls,.95)))
    save(completed,result);store.status("P0_COMPLETE",result=result);return result

def p1(store):
    if (OUT/"P1_COMPLETE.json").exists():return read(OUT/"P1_COMPLETE.json")
    store.check_sources();store.status("P1")
    for d in ("A24","S26"):
        for layer in LAYERS:
            for ci in range(12):
                for rep in range(2):
                    for name in RULES:
                        identity=f"P1_{d}_{layer}_C{ci}_R{rep}_{name}"
                        store.run(identity,d,layer,ci,"P1",rep,candidate.Rule(name))
                    for name in WAIT_RULES:
                        identity=f"P1_{d}_{layer}_C{ci}_R{rep}_{name}_WAIT"
                        store.run(identity,d,layer,ci,"P1",rep,candidate.Rule(name,True))
                    store.status("P1",device=d,layer=layer,case=ci,replicate=rep)
    # Opportunities are reported per registered cell, including infeasible/negative cells.
    rows=[r for r in store.rows if r["split"]=="P1"]
    opportunities=[]
    for d in ("A24","S26"):
        for layer in LAYERS:
            for ci in range(12):
                for rep in range(2):
                    cell=[r for r in rows if (r["device"],r["layer"],r["case_index"],r["index"])==(d,layer,ci,rep)]
                    b=next(r for r in cell if r["policy"]=="FIFO_READY" and r["identity"].endswith("FIFO_READY"))
                    for alpha in ALPHAS:
                        qualified=[r for r in cell if cases.qualifies(r["metrics"],alpha)]
                        costs=[dict(policy=r["policy"],identity=r["identity"],**cases.goal(r["metrics"],b["metrics"])) for r in qualified if cases.goal(r["metrics"],b["metrics"])]
                        opportunities.append(dict(device=d,layer=layer,case=cases.SPECS[ci][0],replicate=rep,alpha=alpha,
                           baseline_qualified=cases.qualifies(b["metrics"],alpha),feasible=len(qualified),pairs=costs))
    result=dict(status="COMPLETE",environments=len(rows),opportunities=opportunities,all_registered_conditions_retained=True,
                physical_profile_changes=0,fit=0)
    save(OUT/"P1_COMPLETE.json",result);store.status("P1_COMPLETE");return result

def dev_score(rows,alpha):
    relevant=[r for r in rows if abs((r["alpha"] or 0)-alpha)<1e-6]
    missing=sum(not cases.qualifies(r["metrics"],alpha) for r in relevant)
    service=sum(max(0,alpha-(r["metrics"][p+"_success_pct"] or 100)/100) for r in relevant for p in ("urgent","normal"))
    cost=[]
    for r in relevant:
        m=r["metrics"]
        if m["energy_180_j"] is not None and m["mean_ap_c"] is not None:
            cost.append(m["energy_180_j"]/20+m["mean_ap_c"]/.5)
        else:cost.append(1e5)
    return [missing,service,float(np.mean(cost))]
def dev(store,learner,arm,stage):
    rows=[]
    for layer in ("M0_frozen35","M1_coupled"):
        for ci in DEV_CASES:
            for rep in range(2):
                for alpha in ALPHAS:
                    identity=f"DEV_{learner.device}_{arm}_{learner.seed}_EP{stage}_{layer}_C{ci}_R{rep}_A{int(alpha*100)}"
                    ctl=learner.controller(alpha,collect=False)
                    raw,row,_=store.run(identity,learner.device,layer,ci,"DEV",rep,ctl)
                    row=dict(row,arm=arm,stage=stage,learner_seed=learner.seed);rows.append(row)
    return {str(a):dev_score(rows,a) for a in ALPHAS},rows

def train(store,device,arm,seed,target):
    folder=OUT/"learners"/device/arm/str(seed);folder.mkdir(parents=True,exist_ok=True)
    latest=folder/"latest.pt"
    learner=ppo.Learner.load(latest) if latest.exists() else ppo.Learner(seed,device,*ARMS[arm])
    if learner.episodes>=target and (folder/f"dev_{target}.json").exists():return read(folder/f"dev_{target}.json")
    store.check_sources()
    while learner.episodes<target:
        i=learner.episodes;alpha=ALPHAS[i%5];heat=(.25,.5,.75)[(i//5)%3];ci=i%12
        layer=LAYERS[(i//12)%3]
        identity=f"TRAIN_{device}_{arm}_{seed}_EP{i+1}"
        store.status("TRAIN",device=device,arm=arm,learner_seed=seed,episode=i,target=target,adam_steps=learner.steps)
        controller=learner.controller(alpha,heat,True)
        raw,row,cached=store.run(identity,device,layer,ci,"TRAIN",i,controller,True)
        if cached:raise ValueError("uncommitted training episode exists; recover exact pre-episode RNG and collected archive, never re-simulate")
        meta=learner.add(controller,raw)
        arc=store.rollout(identity,controller)
        append(folder/"learning.jsonl",dict(episode=learner.episodes,metrics=raw["metrics"],cost=meta,archive=arc,
               net_sha=netsha(learner.net),updates=learner.updates,adam_steps=learner.steps))
        learner.save(latest)
        if learner.episodes%8==0:learner.save(folder/f"update_{learner.updates}.pt")
    cp=folder/f"ep_{target}.pt";learner.save(cp)
    scores,rows=dev(store,learner,arm,target)
    result=dict(device=device,arm=arm,seed=seed,episodes=learner.episodes,updates=learner.updates,adam_steps=learner.steps,
       checkpoint=str(cp),sha=sha(cp),network_sha=netsha(learner.net),scores=scores,rows=rows)
    save(folder/f"dev_{target}.json",result);return result

def main():
    parser=argparse.ArgumentParser();parser.add_argument("command",choices=("register","p0","p1","train","run"))
    parser.add_argument("--device",default="S26");parser.add_argument("--arm",default="ATC_WAIT")
    parser.add_argument("--seed",type=int,default=37001);parser.add_argument("--target",type=int,default=256)
    args=parser.parse_args();OUT.mkdir(parents=True,exist_ok=True)
    store=Store()
    if args.command=="register":print(json.dumps(store.reg,ensure_ascii=False));return
    if args.command=="p0":print(json.dumps(p0(store)));return
    if args.command=="p1":p1(store);return
    if args.command=="train":print(json.dumps(train(store,args.device,args.arm,args.seed,args.target),ensure_ascii=False)[:1000]);return
    raise NotImplementedError("autonomous runner assembled after P0 and calibrated budget; no premature long launch")
if __name__=="__main__":
    try:main()
    except Exception:
        OUT.mkdir(parents=True,exist_ok=True);save(OUT/f"FAILURE_{time.time_ns()}.json",dict(traceback=traceback.format_exc(),unix=stamp()))
        raise
