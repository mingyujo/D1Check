"""Autonomous staged learning, DEV-only improvement and one sealed comparison."""
import os
for _key in ("OMP_NUM_THREADS","MKL_NUM_THREADS","OPENBLAS_NUM_THREADS"):os.environ[_key]="1"
import csv,gzip,json,sys,time,traceback,shutil,math
from pathlib import Path
import numpy as np
from common import *
import study
import cases
import candidates
import ppo
# Pre-training counterfactual: thermal slowdown may reduce W or leave W unchanged.
# Both are old registered36 assumptions, never coefficients chosen to favor PPO.
study.LAYERS=("M0_frozen35","M1_coupled","thermal_strong_Wscaled","thermal_strong_Wfixed")
FINAL_REPLICATES=4
ENVIRONMENT_CAP=137712
FINAL_ARMS=("ATC_WAIT","EDD_WAIT","DIRECT_WAIT","NONDELAY")
BASELINES=(*study.RULES,*(name+"_WAIT" for name in study.WAIT_RULES))
EVIDENCE_GRADES={"M0_frozen35":"M0: frozen measured35 reproduction",
                 "M1_coupled":"M1: coupled existing-data model",
                 "thermal_strong_Wscaled":"M2: unmeasured slowdown with scaled power",
                 "thermal_strong_Wfixed":"M2: unmeasured slowdown with fixed power"}

def planned_identities(generation,B=4096):
    """The full registered schedule, excluding already completed identities at accounting time."""
    groups={k:set() for k in ("P0_current","P1","DEV_rules","TRAIN","DEV_learned","FINAL")}
    gen=generation["generation"]
    for i in range(8):groups["P0_current"].add(f"P0_TIMERFIX_G{gen}_NATIVE_{i}")
    for d in ("A24","S26"):
        for layer in ("M0_frozen35","M1_coupled"):
            groups["P0_current"].add(f"P0_TIMERFIX_G{gen}_{d}_{layer}_EXACT50MS")
        for layer in study.LAYERS:
            for ci in range(12):
                for rep in range(2):
                    for name in BASELINES:
                        original=f"P1_{d}_{layer}_C{ci}_R{rep}_{name}"
                        groups["P1"].add(original)
                        if layer!="thermal_strong_Wfixed":
                            if name.endswith("_WAIT"):groups["P1"].add(original+f"_TIMERFIX_G{gen}")
                            elif name=="LST":groups["P1"].add(original+"_PRIORITYFIX")
        for layer in ("M0_frozen35","M1_coupled"):
            for ci in study.DEV_CASES:
                for rep in range(2):
                    for name in BASELINES:groups["DEV_rules"].add(f"DEV_RULE_{d}_{layer}_C{ci}_R{rep}_{name}")
        for arm in ("GATE",*FINAL_ARMS):
            maximum=256 if arm=="GATE" else B
            targets=(256,) if arm=="GATE" else tuple(dict.fromkeys((256,1024,B)))
            for seed in SEEDS:
                for i in range(1,maximum+1):groups["TRAIN"].add(f"TRAIN_{d}_{arm}_{seed}_EP{i}")
                for target in targets:
                    for layer in ("M0_frozen35","M1_coupled"):
                        for ci in study.DEV_CASES:
                            for rep in range(2):
                                for alpha in ALPHAS:
                                    groups["DEV_learned"].add(f"DEV_{d}_{arm}_{seed}_EP{target}_{layer}_C{ci}_R{rep}_A{int(alpha*100)}")
        for layer in study.LAYERS:
            for ci in range(12):
                for rep in range(FINAL_REPLICATES):
                    for name in BASELINES:groups["FINAL"].add(f"FINAL_{d}_{layer}_C{ci}_R{rep}_{name}")
                    for arm in FINAL_ARMS:
                        for seed in SEEDS:
                            for alpha in ALPHAS:
                                groups["FINAL"].add(f"FINAL_{d}_{layer}_C{ci}_R{rep}_{arm}_S{seed}_A{int(alpha*100)}")
    return groups

def register_budget(store,B=4096,require_fit=True):
    groups=planned_identities(store.generation,B)
    missing={k:len(ids-set(store.byid)) for k,ids in groups.items()}
    projected=store.n+sum(missing.values())
    item=dict(unix=stamp(),environment_cap=ENVIRONMENT_CAP,source_generation=store.generation["generation"],
        worst_case_exposure=B,environments_already_started=store.n,completed=len(store.rows),
        failures=store.failures,remaining_environments_by_stage=missing,projected_total_started=projected,
        failure_start_reserve=ENVIRONMENT_CAP-projected,within_original_cap=projected<=ENVIRONMENT_CAP,
        historical_starts_never_reset=True,scope="All seeds/cases/arms/corrections; no second full endpoint FINAL")
    save(OUT/f"BUDGET_PLAN_G{store.generation['generation']}_B{B}.json",item)
    if require_fit and not item["within_original_cap"]:raise ValueError("registered remaining schedule exceeds137712 environment cap")
    return item

def source_generation(reason):
    files={str(p.relative_to(WORK)):sha(p) for p in sorted((WORK/"code").glob("*.py"))}
    files.update({str(p.relative_to(WORK)):sha(p) for p in sorted((VENDOR/"tools").glob("*.py"))})
    folder=OUT/"source_generations";folder.mkdir(parents=True,exist_ok=True)
    matches=sorted(folder.glob("GEN*.json"))
    if matches and read(matches[-1])["source_sha"]==files:return read(matches[-1])
    # Source bytes are preserved before a new stage. Physics/coefficient files are unchanged.
    gen=len(matches)+1
    target=folder/f"GEN{gen:03d}"
    target.mkdir()
    for p in (WORK/"code").glob("*.py"):shutil.copy2(p,target/p.name)
    item=dict(generation=gen,unix=stamp(),reason=reason,source_sha=files,
              previous_registration_sha=sha(OUT/"REGISTRATION.json"),learned_weights_compatible=False,
              input_schema=candidates.SCHEMA,input_spec=candidates.SPEC,main_learning_fresh=True,
              physical_fits=0,physical_profile_changes=0,layers=list(study.LAYERS),
              final_replicates=FINAL_REPLICATES,
              profile_sha={f"{d}/{m}":sha(VENDOR/"profiles"/f"{d}_G36_{m}.json") for d in ("A24","S26") for m in study.LAYERS},
              environment_cap=ENVIRONMENT_CAP,
              design_delta="Before main learning: causal credit and WAIT/deadline repair; fresh weights for miss-history and immediate-partner observations; durable prepared environment commits and indexed replay logs; complete FINAL inputs/network/mask audit; four FINAL repeats, Wfixed sensitivity, strict137712 resource gate; no physics fit")
    save(folder/f"GEN{gen:03d}.json",item)
    return item

class FrozenStore(study.Store):
    def __init__(self,generation):
        super().__init__();self.generation=generation
        self.reg["environment_cap"]=ENVIRONMENT_CAP
    def check_sources(self):
        for name,h in self.generation["source_sha"].items():
            if sha(WORK/name)!=h:raise ValueError("stage source changed: "+name)
        for name,h in self.reg["protected"].items():
            if name.endswith("ROLLING_ATC_RL_COMPLETION_PLAN_20261014.md"):continue
            if sha(name)!=h:raise ValueError("protected artifact changed")
        for name,h in self.generation["profile_sha"].items():
            d,layer=name.split("/")
            if sha(VENDOR/"profiles"/f"{d}_G36_{layer}.json")!=h:raise ValueError("physical profile changed")

def recover_frames(path):
    z=np.load(path,allow_pickle=False);frames=[]
    for i in range(len(z["index"])):
        nq,na=z["original_sizes"][i]
        f={k:z[k][i].copy() for k in ppo.INPUTS}
        if "physical_mask" in z.files:f["physical_mask"]=z["physical_mask"][i].copy()[:na]
        f["requests"]=f["requests"][:nq]
        for k in ("features","mask","request_index","backend_index"):f[k]=f[k][:na]
        f.update(time_ns=int(z["time_ns"][i]),index=int(z["index"][i]),old_logp=float(z["old_logp"][i]),
                 value=z["value"][i].copy(),target=z["target"][i].copy(),adv=z["adv"][i].copy(),
                 learn_actor=bool(z["actor_valid"][i]),alpha=float(z["global_state"][i,20]),
                 heat=float(z["global_state"][i,22]),input_sha=str(z["input_sha"][i]))
        if "cost" in z.files:f["cost"]=z["cost"][i].copy()
        # Conditioning came from a float32 input; map back to registered exact alpha.
        f["alpha"]=min(ALPHAS,key=lambda a:abs(a-f["alpha"]))
        if ppo.input_digest(f)!=f["input_sha"]:raise ValueError("recovered input bytes changed")
        frames.append(f)
    rng=z["action_rng_after"].copy() if "action_rng_after" in z.files else None
    return frames,rng

def save_rollout(store,identity,controller):
    data,frames=ppo.pack([controller.frames]);path=OUT/"rollouts"/(identity+".npz");path.parent.mkdir(exist_ok=True)
    if path.exists():return dict(path=str(path),sha=sha(path),bytes=path.stat().st_size)
    temp=path.with_suffix(".tmp.npz")
    extra={}
    if all("physical_mask" in f for f in frames):
        masks=np.zeros(data["mask"].shape,bool)
        for i,f in enumerate(frames):masks[i,:len(f["physical_mask"])]=f["physical_mask"]
        extra["physical_mask"]=masks
    if all("cost" in f for f in frames):extra["cost"]=np.stack([f["cost"] for f in frames])
    np.savez_compressed(temp,**{k:v.numpy() for k,v in data.items()},**extra,
         time_ns=np.array([f["time_ns"] for f in frames],np.int64),
         original_sizes=np.array([[len(f["requests"]),len(f["features"])] for f in frames],np.int32),
         input_sha=np.array([f["input_sha"] for f in frames]),action_rng_after=controller.rng.get_state().numpy())
    with temp.open("r+b") as stream:stream.flush();os.fsync(stream.fileno())
    os.replace(temp,path)
    return dict(path=str(path),sha=sha(path),bytes=path.stat().st_size)

def train(store,device,arm,seed,target):
    import recovery_io
    folder=OUT/"learners"/device/arm/str(seed);folder.mkdir(parents=True,exist_ok=True)
    learning_log=recovery_io.IdempotentLog(folder/"learning.jsonl")
    optimizer_log=recovery_io.IdempotentLog(folder/"optimizer.jsonl",key_fields=("update",))
    latest=folder/"latest.pt"
    learner=ppo.Learner.load(latest) if latest.exists() else ppo.Learner(seed,device,*study.ARMS[arm])
    # latest is committed before the small network archive. A crash in that
    # window is repaired from the exact checkpoint, never by retraining.
    if latest.exists():torchsave_network(learner,folder/f"network_update{learner.updates}.pt")
    for log in learner.logs:optimizer_log.append(log)
    # A crash can occur after latest.pt rename but before the lightweight network archive.
    # The full native checkpoint is authoritative for that exact completed update.
    if latest.exists():torchsave_network(learner,folder/f"network_update{learner.updates}.pt")
    if learner.episodes>=target and (folder/f"dev_{target}.json").exists():return read(folder/f"dev_{target}.json")
    store.check_sources()
    if not latest.exists():
        learner.save(latest);torchsave_network(learner,folder/"network_update0.pt")
    while learner.episodes<target:
        i=learner.episodes;alpha=ALPHAS[i%5];heat=(.25,.5,.75)[(i//5)%3];ci=i%12
        layer=study.LAYERS[(i//12)%3];identity=f"TRAIN_{device}_{arm}_{seed}_EP{i+1}"
        store.status("TRAIN",device=device,arm=arm,learner_seed=seed,episode=i,target=target,adam_steps=learner.steps)
        ctl=learner.controller(alpha,heat,True)
        if identity in store.byid:
            row=store.byid[identity];raw=study.load_gz(row["raw_path"]);arc=OUT/"rollouts"/(identity+".npz")
            if not arc.exists():
                raise ValueError("uncommitted experience needs registered causal action replay; never relabel a missing rollout as fresh training")
            if row.get("training_archive",{}).get("sha") and sha(arc)!=row["training_archive"]["sha"]:
                raise ValueError("recovered training archive SHA differs from committed row")
            ctl.frames,rng=recover_frames(arc)
            if rng is None:raise ValueError("missing action RNG for resume")
            ctl.rng.set_state(__import__("torch").from_numpy(rng))
            archive=dict(path=str(arc),sha=sha(arc),bytes=arc.stat().st_size,recovered=True)
        else:
            raw,row,cached=store.run(identity,device,layer,ci,"TRAIN",i,ctl,True)
            ppo.labels(ctl,raw,learner.settings,learner.family)
            archive=save_rollout(store,identity,ctl)
        meta=learner.add(ctl,raw)
        learning_log.append(dict(episode=learner.episodes,metrics=raw["metrics"],cost=meta,archive=archive,
            network_sha=study.netsha(learner.net),updates=learner.updates,adam_steps=learner.steps,
            source_generation=store.generation["generation"]))
        if learner.episodes%8==0:
            learner.save(latest);torchsave_network(learner,folder/f"network_update{learner.updates}.pt")
            optimizer_log.append(learner.logs[-1])
    cp=folder/f"ep_{target}.pt";learner.save(cp);learner.save(latest)
    scores,rows=study.dev(store,learner,arm,target)
    result=dict(device=device,arm=arm,seed=seed,episodes=target,updates=learner.updates,adam_steps=learner.steps,
        checkpoint=str(cp),sha=sha(cp),network_sha=study.netsha(learner.net),scores=scores,rows=rows)
    save(folder/f"dev_{target}.json",result);return result

def torchsave_network(learner,path):
    import torch
    if path.exists():
        archived=torch.load(path,map_location="cpu",weights_only=True)
        current=learner.net.state_dict()
        if set(archived)!=set(current) or any(not torch.equal(archived[k],current[k]) for k in current):
            raise ValueError("network archive differs from exact checkpoint: "+str(path))
        return
    temp=str(path)+".tmp";torch.save(learner.net.state_dict(),temp)
    with open(temp,"r+b") as stream:os.fsync(stream.fileno())
    os.replace(temp,path)

def dev_rules(store):
    if (OUT/"DEV_RULES_COMPLETE.json").exists():return
    for d in ("A24","S26"):
        for layer in ("M0_frozen35","M1_coupled"):
            for ci in study.DEV_CASES:
                for rep in range(2):
                    for name in study.RULES:
                        identity=f"DEV_RULE_{d}_{layer}_C{ci}_R{rep}_{name}"
                        store.run(identity,d,layer,ci,"DEV",rep,candidates.Rule(name))
                    for name in study.WAIT_RULES:
                        identity=f"DEV_RULE_{d}_{layer}_C{ci}_R{rep}_{name}_WAIT"
                        store.run(identity,d,layer,ci,"DEV",rep,candidates.Rule(name,True))
    save(OUT/"DEV_RULES_COMPLETE.json",dict(status="COMPLETE",new_environments=416))

def fixed_power_control(store):
    if (OUT/"P1_WFIXED_COMPLETE.json").exists():return
    for d in ("A24","S26"):
        for ci in range(12):
            for rep in range(2):
                for name in study.RULES:
                    ident=f"P1_{d}_thermal_strong_Wfixed_C{ci}_R{rep}_{name}"
                    store.run(ident,d,"thermal_strong_Wfixed",ci,"P1",rep,candidates.Rule(name))
                for name in study.WAIT_RULES:
                    ident=f"P1_{d}_thermal_strong_Wfixed_C{ci}_R{rep}_{name}_WAIT"
                    store.run(ident,d,"thermal_strong_Wfixed",ci,"P1",rep,candidates.Rule(name,True))
    save(OUT/"P1_WFIXED_COMPLETE.json",dict(status="COMPLETE",environments=624,
        reason="Compare reduced power and constant power under the same slowdown before RL training"))

def priority_contract_controls(store):
    if (OUT/"PRIORITY_CONTRACT_CORRECTION.json").exists():return
    import priority_check
    equivalent=priority_check.run()
    old=[]
    for d in ("A24","S26"):
        for layer in ("M0_frozen35","M1_coupled","thermal_strong_Wscaled"):
            for ci in range(12):
                for rep in range(2):
                    for name in ("LST",):
                        previous=f"P1_{d}_{layer}_C{ci}_R{rep}_{name}"
                        old.append(previous)
                        store.run(previous+"_PRIORITYFIX",d,layer,ci,"P1",rep,candidates.Rule(name))
    save(OUT/"PRIORITY_CONTRACT_CORRECTION.json",dict(reason="Request priority uses a common representative path; resource choice stays response/occupancy/backend",
        corrected_rules=["LST"],SPT_WSPT_equivalence=equivalent,old_identities_superseded_for_priority_comparison=old,
        corrected_environments=144,physical_changes=0))

def timer_fix_verification(store):
    gen=store.generation["generation"]
    marker=OUT/f"P0_TIMERFIX_G{gen}_COMPLETE.json"
    correction=OUT/f"WAIT_CONTRACT_CORRECTION_G{gen}.json"
    if correction.exists():return
    if marker.exists():
        correct_timer_controls(store);return
    # Original P0 proved numerical/physical invariants, but missed the idle timer-expiry callback.
    # Fresh validation and all old optional-WAIT controls are accounted under new identities.
    partial=OUT/f"P0_TIMERFIX_G{gen}_LATEST.pt"
    learner=ppo.Learner.load(partial) if partial.exists() else ppo.Learner(SEEDS[0],"S26")
    metas=[]
    for i in range(learner.episodes,8):
        ctl=learner.controller(ALPHAS[i%5],collect=True)
        identity=f"P0_TIMERFIX_G{gen}_NATIVE_{i}"
        r,row,cached=store.run(identity,"S26","M1_coupled",3,"P0FIX",i,ctl,True)
        if cached:
            ctl.frames,rng=recover_frames(OUT/"rollouts"/(identity+".npz"))
            if rng is None:raise ValueError("timer validation resume action RNG absent")
            ctl.rng.set_state(__import__("torch").from_numpy(rng))
        else:
            ppo.labels(ctl,r,learner.settings,learner.family)
            save_rollout(store,identity,ctl)
        learner.add(ctl,r);metas.append(dict(episode=i+1,frames=len(ctl.frames)))
        learner.save(partial)
    class OneTimer(candidates.Rule):
        def __init__(self):
            super().__init__("FIFO_READY",False);self.first=True
        def choose(self,view,waiting):
            if not self.first:return super().choose(view,waiting)
            self.first=False
            self.decisions.append(dict(time_ns=view.now,queue=len(waiting),legal_count=1,atc_edd_order_same=True,wait_ns=50_000_000))
            self.audit.append(dict(time_ns=view.now,physical=True,future_input=False))
            return dict(request=None,backend=None,wait_ns=50_000_000)
    tests=[]
    for d in ("A24","S26"):
        for layer in ("M0_frozen35","M1_coupled"):
            identity=f"P0_TIMERFIX_G{gen}_{d}_{layer}_EXACT50MS"
            r,row,_=store.run(identity,d,layer,0,"P0FIX",10,OneTimer())
            first=min(q["dispatch_ns"] for q in r["ledger"])
            if first!=35_050_000_000:raise ValueError("timer expiry did not dispatch at exact50ms")
            if r["wait_used_ns"]!=50_000_000:raise ValueError("WAIT elapsed accounting")
            tests.append(dict(device=d,layer=layer,first_dispatch_ns=first,actual_WAIT_ns=r["wait_used_ns"]))
    learner.save(OUT/f"P0_TIMERFIX_G{gen}_NATIVE.pt")
    save(marker,dict(status="PASS",environments=12,new_validation_experiences=8,source_generation=gen,
        native_updates=learner.updates,adam_steps=learner.steps,exact_timer_tests=tests,
        old_P0_scope="retained as numerical proof; not timer contract proof"))
    correct_timer_controls(store)

def correct_timer_controls(store):
    gen=store.generation["generation"]
    old_wait=[]
    for d in ("A24","S26"):
        for layer in ("M0_frozen35","M1_coupled","thermal_strong_Wscaled"):
            for ci in range(12):
                for rep in range(2):
                    for name in study.WAIT_RULES:
                        original=f"P1_{d}_{layer}_C{ci}_R{rep}_{name}_WAIT"
                        old_wait.append(original)
                        fixed=original+f"_TIMERFIX_G{gen}"
                        store.run(fixed,d,layer,ci,"P1",rep,candidates.Rule(name,True))
    save(OUT/f"WAIT_CONTRACT_CORRECTION_G{gen}.json",dict(reason="Timer/deadline redecision corrected before main learning; current source generation",
        old_identities_superseded_for_wait_comparison=old_wait,corrected_environments=432,
        raw_originals_preserved=True,non_delay_controls_unchanged=True,physical_coefficient_changes=0))

def current_p1_comparison(store):
    """Read corrected identities; retain the original P1 report as historical evidence."""
    gen=store.generation["generation"];cells=[]
    for d in ("A24","S26"):
        for layer in study.LAYERS:
            for ci in range(12):
                for rep in range(2):
                    selected=[]
                    for name in BASELINES:
                        identity=f"P1_{d}_{layer}_C{ci}_R{rep}_{name}"
                        if layer!="thermal_strong_Wfixed":
                            if name.endswith("_WAIT"):identity+=f"_TIMERFIX_G{gen}"
                            elif name=="LST":identity+="_PRIORITYFIX"
                        selected.append((name,store.byid[identity]))
                    baseline=store.byid[f"P1_{d}_{layer}_C{ci}_R{rep}_FIFO_READY"]
                    for alpha in ALPHAS:
                        options=[]
                        for name,row in selected:
                            options.append(dict(rule=name,identity=row["identity"],qualified=cases.qualifies(row["metrics"],alpha),
                                metrics=row["metrics"],effect_vs_FIFO=cases.goal(row["metrics"],baseline["metrics"])))
                        feasible=[o for o in options if o["qualified"]]
                        pareto=[o["rule"] for o in feasible if not any(
                            b["metrics"]["energy_180_j"]<=o["metrics"]["energy_180_j"] and b["metrics"]["mean_ap_c"]<=o["metrics"]["mean_ap_c"]
                            and (b["metrics"]["energy_180_j"]<o["metrics"]["energy_180_j"] or b["metrics"]["mean_ap_c"]<o["metrics"]["mean_ap_c"])
                            for b in feasible)]
                        cells.append(dict(device=d,layer=layer,evidence_grade=EVIDENCE_GRADES[layer],case_index=ci,replicate=rep,
                            alpha=alpha,baseline_qualified=cases.qualifies(baseline["metrics"],alpha),feasible=len(feasible),
                            pareto_rules=pareto,options=options))
    result=dict(source_generation=gen,status="CURRENT_CONTRACT_COMPARISON",cells=cells,new_environments=0,
        original_report_preserved=True,physical_profile_changes=0)
    gzsave(OUT/f"P1_CURRENT_COMPARISON_G{gen}.json.gz",result)
    return result

def corrected_dev_score(rows,alpha):
    rs=[r for r in rows if r["alpha"] is not None and abs(r["alpha"]-alpha)<1e-6]
    if not rs:raise ValueError("empty DEV alpha")
    missing=sum(not cases.qualifies(r["metrics"],alpha) for r in rs)
    service=sum(max(0,alpha-(r["metrics"][p+"_success_pct"] if r["metrics"][p+"_success_pct"] is not None else 100)/100)
                for r in rs for p in ("urgent","normal"))
    cost=[r["metrics"]["energy_180_j"]/20+r["metrics"]["mean_ap_c"]/.5
          if r["metrics"]["energy_180_j"] is not None and r["metrics"]["mean_ap_c"] is not None else 1e5 for r in rs]
    return [missing,service,float(np.mean(cost))]
study.dev_score=corrected_dev_score

def summarize_dev(results):
    grouped={}
    for r in results:
        key=(r["device"],r["arm"]);grouped.setdefault(key,[]).append(r)
    rows=[]
    for (device,arm),rs in grouped.items():
        eligible=total=0;energy=[];ap=[]
        for r in rs:
            for row in r["rows"]:
                total+=1;m=row["metrics"]
                eligible+=cases.qualifies(m,row["alpha"])
                if m["energy_180_j"] is not None:energy.append(m["energy_180_j"])
                if m["mean_ap_c"] is not None:ap.append(m["mean_ap_c"])
        rows.append(dict(device=device,arm=arm,eligible=eligible,total=total,
                         mean_energy_180_j=float(np.mean(energy)) if energy else None,
                         mean_AP_c=float(np.mean(ap)) if ap else None))
    return rows

def aggregate_score(result):
    scores=list(result["scores"].values())
    return [sum(x[j] for x in scores) for j in range(3)]

def stage(store,arms,target,devices=("A24","S26")):
    results=[]
    for d in devices:
        for arm in arms:
            for seed in SEEDS:
                results.append(train(store,d,arm,seed,target))
    record=dict(stage=target,arms=list(arms),results=results,summary=summarize_dev(results),source_generation=store.generation)
    save(OUT/f"STAGE_{target}_{'_'.join(arms)}.json",record)
    return record

def expansion_evidence(stage2,stage3):
    """Repeated paired DEV evidence; incomplete or ineligible rows cannot imply cost improvement."""
    old={(r["device"],r["arm"],r["seed"]):r for r in stage2["results"]}
    evidence=[]
    for new in stage3["results"]:
        previous=old[new["device"],new["arm"],new["seed"]]
        bykey={(r["layer"],r["case_index"],r["index"],r["alpha"]):r for r in previous["rows"]}
        for alpha in ALPHAS:
            paired=[];winning=set();old_ok=new_ok=0
            for row in new["rows"]:
                if abs(row["alpha"]-alpha)>1e-6:continue
                key=(row["layer"],row["case_index"],row["index"],row["alpha"])
                before=bykey[key];m,b=row["metrics"],before["metrics"]
                q,qb=cases.qualifies(m,alpha),cases.qualifies(b,alpha);new_ok+=q;old_ok+=qb
                if not(q and qb):continue
                e=b["energy_180_j"]-m["energy_180_j"];a=b["mean_ap_c"]-m["mean_ap_c"]
                paired.append((e,a))
                if e>1e-9 and a>1e-9:winning.add((row["layer"],row["case_index"]))
            joint=bool(paired and np.mean([p[0] for p in paired])>1e-9 and np.mean([p[1] for p in paired])>1e-9)
            evidence.append(dict(device=new["device"],arm=new["arm"],seed=new["seed"],alpha=alpha,
                common_eligible=len(paired),old_eligible=old_ok,new_eligible=new_ok,
                energy_improvement_j_mean=float(np.mean([p[0] for p in paired])) if paired else None,
                AP_improvement_c_mean=float(np.mean([p[1] for p in paired])) if paired else None,
                jointly_improved_conditions=len(winning),joint_DEV_improvement=joint,
                repeatable_seed_signal=joint and new_ok>=old_ok and len(winning)>=2))
    groups=[]
    for d in ("A24","S26"):
        for arm in ("ATC_WAIT","NONDELAY"):
            for alpha in ALPHAS:
                rs=[r for r in evidence if(r["device"],r["arm"],r["alpha"])==(d,arm,alpha)]
                groups.append(dict(device=d,arm=arm,alpha=alpha,
                    improved_seeds=sum(r["repeatable_seed_signal"] for r in rs),required_seeds=2))
    # The main WAIT policy's own evidence controls its expansion; another arm cannot justify it.
    grow=any(r["arm"]=="ATC_WAIT" and r["improved_seeds"]>=2 for r in groups)
    return evidence,groups,grow

def final_roster(frozen):
    roster=[]
    for d in ("A24","S26"):
        for layer in frozen["layers"]:
            p=study.profile(d,layer)
            for ci in range(12):
                for rep in range(frozen["final_replicates"]):
                    roster.append(dict(device=d,layer=layer,case=ci,replicate=rep,
                        request_sha=digest(cases.requests(p,ci,"FINAL",rep)),
                        environment_seed=cases.environment_seed("FINAL",rep)))
    return roster

def verify_freeze(store,frozen):
    store.check_sources()
    if frozen["source_generation"]!=store.generation:raise ValueError("FINAL source generation changed")
    if digest(final_roster(frozen))!=frozen["actual_FINAL_roster_sha"]:raise ValueError("FINAL roster changed")
    for m in frozen["models"]:
        if sha(m["selected"])!=m["sha"]:raise ValueError("frozen selected checkpoint changed")
        if sha(m["endpoint"])!=m["endpoint_sha"]:raise ValueError("exposure endpoint checkpoint changed")
        learner=ppo.Learner.load(m["selected"])
        if (learner.device,learner.seed,learner.episodes)!=(m["device"],m["seed"],m["episodes"]):
            raise ValueError("selected checkpoint identity")
        if study.netsha(learner.net)!=m["network_sha"]:raise ValueError("selected network SHA")
    return True

def freeze(store,B):
    path=OUT/"FINAL_FREEZE.json"
    if path.exists():
        frozen=read(path);verify_freeze(store,frozen)
        if frozen["B"]!=B:raise ValueError("sealed exposure budget changed")
        return frozen
    if any(r["split"]=="FINAL" for r in store.rows):raise ValueError("FINAL outcomes exist before freeze")
    arms=("ATC_WAIT","EDD_WAIT","DIRECT_WAIT","NONDELAY");selected=[]
    for d in ("A24","S26"):
        for arm in arms:
            for seed in SEEDS:
                folder=OUT/"learners"/d/arm/str(seed)
                alternatives=[read(p) for p in folder.glob("dev_*.json") if read(p)["episodes"]<=B]
                endpoint=read(folder/f"dev_{B}.json")
                if endpoint["episodes"]!=B:raise ValueError("same-budget endpoint absent")
                if not alternatives:raise ValueError("same-budget ablation absent")
                choice=min(alternatives,key=lambda r:(aggregate_score(r),r["episodes"]))
                selected.append(dict(device=d,arm=arm,seed=seed,selected=choice["checkpoint"],
                    sha=choice["sha"],network_sha=choice["network_sha"],episodes=choice["episodes"],exposure=B,
                    dev_score=aggregate_score(choice),endpoint=endpoint["checkpoint"],endpoint_sha=endpoint["sha"],
                    endpoint_network_sha=endpoint["network_sha"],endpoint_DEV_scores=endpoint["scores"],
                    selected_updates=choice["updates"],selected_adam_steps=choice["adam_steps"],
                    exposure_updates=endpoint["updates"],exposure_adam_steps=endpoint["adam_steps"],
                    note="Equal total TRAIN exposure and common checkpoint selection protocol; selected episode counts may differ. Endpoint DEV is preserved; endpoint FINAL is not evaluated."))
    # One fixed strong rule per device from DEV, separately from the worst baseline.
    strong={}
    for d in ("A24","S26"):
        rule_options=[]
        for name in BASELINES:
            rows=[store.byid[f"DEV_RULE_{d}_{layer}_C{ci}_R{rep}_{name}"]
                  for layer in ("M0_frozen35","M1_coupled") for ci in study.DEV_CASES for rep in range(2)]
            if len(rows)!=16:raise ValueError("complete strong DEV rule comparison absent")
            key=(sum(not cases.qualifies(r["metrics"],.95) for r in rows),
                 float(np.mean([r["metrics"]["energy_180_j"]/20+r["metrics"]["mean_ap_c"]/.5
                     if r["metrics"]["energy_180_j"] is not None and r["metrics"]["mean_ap_c"] is not None else 1e5 for r in rows])))
            rule_options.append((key,name))
        strong[d]=min(rule_options)[1]
    frozen=dict(unix=stamp(),source_generation=store.generation,models=selected,strong_DEV_baseline=strong,
                FINAL_inputs_sha=store.reg["input_split_sha"]["FINAL"],final_argmax=True,FINAL_reselection=False,
                final_replicates=FINAL_REPLICATES,arms=list(FINAL_ARMS),baselines=list(BASELINES),
                training_layers=list(study.LAYERS[:3]),
                evidence_grades=EVIDENCE_GRADES,strong_baseline_selection_alpha=.95,
                alphas=list(ALPHAS),layers=list(study.LAYERS),cases=list(cases.SPECS),B=B,excluded_legacy="No compatible new-ABI original weights; original artifacts remain preserved")
    frozen["actual_FINAL_roster_sha"]=digest(final_roster(frozen))
    frozen["registered_FINAL_superset_replicates"]=5
    save(path,frozen);verify_freeze(store,frozen);return frozen

def final(store,frozen):
    verify_freeze(store,frozen)
    # Load fixed weights once. No training, dropout or live multiplier adaptation.
    learners={(m["device"],m["arm"],m["seed"]):ppo.Learner.load(m["selected"]) for m in frozen["models"]}
    for d in ("A24","S26"):
        for layer in frozen["layers"]:
            for ci in range(12):
                for rep in range(frozen["final_replicates"]):
                    store.status("FINAL",device=d,layer=layer,case=ci,replicate=rep)
                    for name in study.RULES:
                        ident=f"FINAL_{d}_{layer}_C{ci}_R{rep}_{name}"
                        store.run(ident,d,layer,ci,"FINAL",rep,candidates.Rule(name))
                    for name in study.WAIT_RULES:
                        ident=f"FINAL_{d}_{layer}_C{ci}_R{rep}_{name}_WAIT"
                        store.run(ident,d,layer,ci,"FINAL",rep,candidates.Rule(name,True))
                    for arm in frozen["arms"]:
                        for seed in SEEDS:
                            learner=learners[d,arm,seed]
                            for alpha in ALPHAS:
                                ident=f"FINAL_{d}_{layer}_C{ci}_R{rep}_{arm}_S{seed}_A{int(alpha*100)}"
                                store.run(ident,d,layer,ci,"FINAL",rep,learner.controller(alpha))
    expected=planned_identities(store.generation,frozen["B"])["FINAL"]
    actual={r["identity"] for r in store.rows if r["split"]=="FINAL"}
    if actual!=expected:raise ValueError("FINAL identity coverage differs from sealed plan")
    verify_freeze(store,frozen)
    out=dict(status="EXECUTION_COMPLETE_PENDING_AUDIT",environments=len(actual),new_learning=0,freeze_sha=sha(OUT/"FINAL_FREEZE.json"))
    save(OUT/"FINAL_COMPLETE.json",out);return out

def report(store,frozen,audit_result=None):
    if audit_result and audit_result.get("status")=="PASS":return publish_report(frozen,audit_result)
    rows=[r for r in store.rows if r["split"]=="FINAL"]
    pairs=[];summary=[]
    for d in ("A24","S26"):
        for layer in frozen["layers"]:
            for alpha in ALPHAS:
                for baseline in frozen["baselines"]:
                    chosen=[r for r in rows if r["device"]==d and r["layer"]==layer and r["alpha"] is not None
                            and abs(r["alpha"]-alpha)<1e-6 and "_ATC_WAIT_S" in r["identity"]]
                    costs=[];eligible=valid=success=dominant=service_worse=incomplete=baseline_eligible=0
                    for r in chosen:
                        bid=f"FINAL_{d}_{layer}_C{r['case_index']}_R{r['index']}_{baseline}"
                        b=store.byid[bid];m=r["metrics"]
                        q=cases.qualifies(m,alpha);qb=cases.qualifies(b["metrics"],alpha);eligible+=q;valid+=q and qb
                        incomplete+=m["incomplete"]>0;baseline_eligible+=qb
                        effect=cases.goal(m,b["metrics"])
                        service_worse+=any(m[p+"_on_time"]<b["metrics"][p+"_on_time"] for p in ("urgent","normal"))
                        if effect and q and qb:
                            costs.append(effect);success+=effect["joint_target"];dominant+=effect["joint_target"] and effect["service_not_worse"]
                        pairs.append(dict(device=d,layer=layer,evidence_grade=frozen["evidence_grades"][layer],
                            case_index=r["case_index"],case=r["case"],replicate=r["index"],alpha=alpha,identity=r["identity"],baseline=baseline,
                            policy_qualified=q,baseline_qualified=qb,effect=effect,policy_metrics=m,baseline_metrics=b["metrics"]))
                    energy_mean=float(np.mean([x["energy_reduction_pct"] for x in costs])) if costs else None
                    ap_mean=float(np.mean([x["mean_AP_reduction_c"] for x in costs])) if costs else None
                    met=bool(costs and energy_mean>=10 and ap_mean>=.5)
                    outcome=("evaluation_ineligible" if not costs else "conditional_mean_target" if met else
                             "joint_improvement_below_target" if energy_mean>0 and ap_mean>0 else
                             "cost_tradeoff" if energy_mean>0 or ap_mean>0 else "no_joint_improvement")
                    summary.append(dict(device=d,layer=layer,evidence_grade=frozen["evidence_grades"][layer],alpha=alpha,baseline=baseline,
                        total=len(chosen),policy_eligible=eligible,baseline_eligible=baseline_eligible,
                        common_eligible=valid,policy_incomplete_pairs=incomplete,service_worse_pairs=service_worse,joint_target_pairs=success,
                        target_with_service_not_worse=dominant,
                        energy_reduction_pct_mean=energy_mean,mean_AP_reduction_c=ap_mean,
                        energy_worst_pct=min((x["energy_reduction_pct"] for x in costs),default=None),
                        AP_worst_c=min((x["mean_AP_reduction_c"] for x in costs),default=None),
                        mean_joint_target=met,all_pairs_qualified=valid==len(chosen) and bool(chosen),outcome=outcome))
    save(OUT/"FINAL_SUMMARY.json",summary);gzsave(OUT/"FINAL_PAIRS.json.gz",pairs)
    fields=list(summary[0]) if summary else []
    with (OUT/"FINAL_SUMMARY.csv").open("w",encoding="utf-8-sig",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(summary)
    training=[r for r in store.rows if r["split"]=="TRAIN"]
    receipts=[json.loads(s) for s in (OUT/"receipts.jsonl").read_text(encoding="utf-8").splitlines()]
    validation_training={r["identity"] for r in receipts if r["event"]=="START" and r.get("training") and r["identity"].startswith("P0")}
    p0training=len(validation_training&set(store.byid))
    consumption=dict(environments_started=store.n,completed=len(store.rows),failures=store.failures,
       training_completed=len(training),validation_training_completed=p0training,
       environment_cap=ENVIRONMENT_CAP,remaining_environment_starts=ENVIRONMENT_CAP-store.n,
       hardware=0,APK=0,physical_fits=0,protected_unchanged=True,goal_met_rows=sum(r["mean_joint_target"] for r in summary))
    save(OUT/"CONSUMPTION.json",consumption)
    # Numeric files are audit inputs. Publish the human result only after the independent gate passes.
    if not audit_result or audit_result.get("status")!="PASS":return summary

def publish_report(frozen,audit_result):
    if audit_result.get("status")!="PASS":raise ValueError("cannot publish unaudited results")
    # Do not rewrite audited gzip artifacts: even unchanged content can acquire different container bytes.
    summary=read(OUT/"FINAL_SUMMARY.json");consumption=read(OUT/"CONSUMPTION.json")
    confidence=read(OUT/"ALL_ARMS_CONFIDENCE.json")
    supported=sum(r.get("strict_mean_target_lower_bounds",False) for r in confidence if r["arm"]=="ATC_WAIT")
    text=["# 롤링＋ATC＋RL V2 최종 비교", "",
       "독립 원장·SHA·입력/추론 재생·지표 검산을 통과한 고정 모형 비교다. 실제 휴대폰 효과를 검증한 결과는 아니다.",
       f"주군의 공통 적격 평균에서 정량 공동목표를 만족한 표 행은 {consumption['goal_met_rows']}개, 모형 내 신뢰구간 하한까지 만족한 행은 {supported}개다. 동일 조건 전체의 달성 여부는 적격률·최악값·서비스 손해와 함께 판정한다.",
       "M0는 동결35 재현, M1은 기존 자료 연결 모형, 두 thermal_strong 층은 미측정 M2 가정이다. M2의 달성을 M0 또는 실기기 달성으로 옮기지 않는다.",
       "모든 조건·실패·서비스 손해를 남겼다. 표의 비용 평균은 두 정책 모두 적격인 쌍에 한정된다. 선택된 쌍만의 조건부 평균이며 전체 효익 보장이 아니다.",
       "주4군은 같은 TRAIN 노출량 B와 같은 DEV checkpoint 선정 기회를 사용했다. 선택된 checkpoint의 episode/Adam 수는 다를 수 있으며 동일 B endpoint의 DEV 성능을 별도로 공개했다. FINAL endpoint 비교는 추가 실행하지 않았다.",
       "", "|기기|층|납기%|기준|공통적격/전체|J 감소%|AP 감소℃|공동목표 쌍|",
       "|---|---|---:|---|---:|---:|---:|---:|"]
    for r in summary:
        if r["baseline"] not in ("FIFO_READY","GREEDY_READY_V17",frozen["strong_DEV_baseline"][r["device"]]):continue
        j="null" if r["energy_reduction_pct_mean"] is None else f"{r['energy_reduction_pct_mean']:.3f}"
        t="null" if r["mean_AP_reduction_c"] is None else f"{r['mean_AP_reduction_c']:.4f}"
        text.append(f"|{r['device']}|{r['layer']}|{int(r['alpha']*100)}|{r['baseline']}|{r['common_eligible']}/{r['total']}|{j}|{t}|{r['joint_target_pairs']}|")
    text += ["","구현과 비교의 완료, 정량 목표의 달성, 실기기 효과는 구분한다.",
              "전체 CSV와 FINAL_PAIRS.json.gz에 조건·seed·긴급/일반 성공률·미완료·반전을 공개했다.",
              "ALL_ARMS_CONFIDENCE.csv는 모든13비학습 비교군·학습4군·개별 seed 결과와 모형 내 case 변동 신뢰구간을 제공한다. 계수 불확실성과 실제 기기 모집단의 신뢰구간은 아니다.",
              "원24/35/36/SLO70/중지27 및 이전37파일럿은 보존했다.","",json.dumps(consumption,ensure_ascii=False)]
    (OUT/"RESULTS.md").write_text("\n".join(text)+"\n",encoding="utf-8")
    return summary

def run():
    generation=source_generation("Recover stopped source-contract generation before main learning; preserve previous receipts/raw/P0 proofs, register durable recovery, independent FINAL replay audit and strict137712 resource gate")
    store=FrozenStore(generation);store.check_sources()
    maximum_plan=register_budget(store,4096,require_fit=False)
    register_budget(store,1024)
    import credit_check
    credit_check.run()
    # A previously launched P1 worker must finish before this sole worker proceeds.
    if not (OUT/"P1_COMPLETE.json").exists():study.p1(store)
    timer_fix_verification(store)
    priority_contract_controls(store)
    fixed_power_control(store)
    current_p1_comparison(store)
    dev_rules(store)
    stage2=stage(store,("GATE","NONDELAY","ATC_WAIT"),256)
    stage3=stage(store,("NONDELAY","ATC_WAIT"),1024)
    evidence,groups,grow=expansion_evidence(stage2,stage3)
    maximum_plan=register_budget(store,4096,require_fit=False)
    resource_supported=maximum_plan["within_original_cap"]
    B=4096 if grow and resource_supported else 1024
    decision=dict(unix=stamp(),evidence=evidence,seed_groups=groups,B=B,
        scientific_expansion_signal=grow,resource_expansion_supported=resource_supported,
        denied_environment_starts=max(0,maximum_plan["projected_total_started"]-ENVIRONMENT_CAP),
        rule="ATC_WAIT same device/alpha: joint common-eligible improvement, no eligible-count loss, >=2 DEV conditions in >=2 seeds",
        decision="DEV only; no physical fit or FINAL read")
    decision_path=OUT/"EXPANSION_DECISION.json"
    if decision_path.exists():
        prior=read(decision_path)
        if prior["B"]!=B or prior["evidence"]!=evidence:raise ValueError("registered DEV expansion decision changed on resume")
    else:save(decision_path,decision)
    if B==4096:stage(store,("ATC_WAIT",),4096)
    # Equal exposure ablations; lower B is chosen before FINAL and applied to all arms.
    for target in dict.fromkeys((256,1024,B)):
        stage(store,("EDD_WAIT","DIRECT_WAIT"),target)
    if B>1024:stage(store,("NONDELAY",),B)
    register_budget(store,B)
    frozen=freeze(store,B);final(store,frozen);summary=report(store,frozen)
    import analysis
    analysis.run()
    import completion_audit
    checked=completion_audit.run(store,frozen)
    if checked.get("status")!="PASS":raise ValueError("independent completion audit did not pass")
    report(store,frozen,checked)
    store.check_sources();store.status("COMPLETE",B=B,goal_met_rows=sum(r["mean_joint_target"] for r in summary))
    save(OUT/"COMPLETE.json",dict(unix=stamp(),B=B,freeze_sha=sha(OUT/"FINAL_FREEZE.json"),
        summary_sha=sha(OUT/"FINAL_SUMMARY.json"),consumption=read(OUT/"CONSUMPTION.json"),
        independent_audit=checked,
        outcome="Goal attainment is shown per cell/alpha/evidence grade, including negative results"))
if __name__=="__main__":
    try:run()
    except Exception:
        save(OUT/f"ORCHESTRATOR_FAILURE_{time.time_ns()}.json",dict(unix=stamp(),traceback=traceback.format_exc()))
        raise
