"""Fresh four-objective learners, SHA-reused data and immutable V8 inference/physics."""
import argparse
import copy
import gzip
import hashlib
import json
import math
import os
from unittest.mock import patch
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch

from tools import d1_atc_waitlink_study as parent
from tools import d1_atc_deadline_ppo as learning
from tools import d1_atc_waitlong_study as prior
from tools import d1_atc_costguard_study as source13
from tools import d1_atc_deadline_targets as objectives
from tools import d1_atc_deadline_budget as budget


ROOT = Path(__file__).resolve().parents[1]
SEEDS=(1201,1213,1217)
ARMS=learning.ARMS
ARM="DROP_FLAG_WAIT1"
ORIGIN_MAP=dict(zip(SEEDS,(1013,1019,1021)))
CONFIRM=tuple(range(923910101,923910109))
BASES=parent.BASES
FINAL_RESERVE = 3600
FAMILY = parent.FAMILIES
SERVICE = ("incomplete", "urgent_failure", "urgent_original_cap_failure",
           "normal_failure", "normal_original_cap_failure", "urgent_p95_ms")


def torch_finite_parameter(value):
    return bool(torch.isfinite(value).all())


def write(path, value):
    budget.write(path, parent.serial(value))


def freeze_write(path,value):
    """Sample UTC after an atomic payload commit; final metadata commit precedes final calls."""
    write(path,value)
    value=dict(value,frozen_utc=datetime.now(timezone.utc).isoformat())
    write(path,value)


def cases(seeds):return parent.cases(seeds)

def namespace_check():
    reserved=parent.registry.collect();new=set(CONFIRM)
    if new&set(reserved["seeds"]) or any(lo<=v<=hi for v in new for lo,hi in reserved["ranges"]):raise ValueError("final arrival namespace collision")
    receipts=[]
    for path in sorted(ROOT.parent.glob("*/inputs.json")):
        raw=path.read_bytes()
        if any(str(v) in raw.decode("utf-8-sig") for v in new):raise ValueError("local final collision "+str(path))
        receipts.append(dict(path=str(path),sha256=hashlib.sha256(raw).hexdigest()))
    for path in ROOT.parent.glob("*/registration.json"):
        if set(SEEDS)&set(budget.read(path).get("seeds",[])):raise ValueError("fresh init seed collision "+str(path))
    return dict(final_seeds=CONFIRM,registry=reserved,local_receipts=receipts,fresh_initialization_seeds=SEEDS)

def source_bindings(origin_reg):
    names=set(origin_reg["sources"])
    names|={"tools/d1_atc_deadline_"+v+".py" for v in ("ppo","targets","budget","study","orchestrator","report")}
    names.add("tools/test_d1_atc_deadline.py")
    return {name:budget.digest(ROOT/name) for name in sorted(names)}

def deps(reg,reward_arm):
    return dict(schema=parent.a.SCHEMA,arm=ARM,reward_arm=reward_arm,sequencing="ATC",
                objective=learning.OBJECTIVES[reward_arm],sources=reg["sources"],input_sha=reg["input_sha"])

def preflight():
    parent_root=ROOT.parent/"ATC-COST-GUARD-13";reg=source13.check(parent_root)
    bindings=reusable_bindings(parent_root)
    namespace_check()
    return dict(status="PASS_fresh_reward_preflight",references=len(bindings),counts=dict(train=2816,development=176,confirmation=176),new_environments=0,new_learning=0)


def reusable_bindings(parent_root):
    bindings=[]
    folders=[("controls",parent_root/"controls",("teacher_train_","development_"))]
    folders += [(f"origin{old}",parent_root/f"origin{old}",("dev4096_",)) for old in ORIGIN_MAP.values()]
    for target,folder,prefixes in folders:
        for path in sorted((folder/"rows").glob("*.json")):
            if not path.name.startswith(prefixes):continue
            receipt=budget.read(path);raw=folder/"items"/(path.stem+".json.gz")
            if budget.digest(raw)!=receipt["raw_sha256"]:raise ValueError("parent raw changed")
            # Decompress only reused teacher/DEV; parent12 final is never read.
            data=json.loads(gzip.decompress(raw.read_bytes()))
            if data["row"]!=receipt["row"]:raise ValueError("parent raw/row mismatch")
            parent.audit_ledger(data["result"])
            for snap in data["snapshots"]:
                if snap["online_forecast_calls"]!=0 or not snap["physical_mask"][snap["chosen"]]:raise ValueError("parent mask/forecast")
            bindings.append(dict(target=target,identity=path.stem,row_path=str(path),raw_path=str(raw),row_sha=budget.digest(path),raw_sha=receipt["raw_sha256"]))
    if len(bindings)!=4400:raise ValueError("all4400 reused references must be complete")
    return bindings

def register(folder,hours=8):
    began=time.time();folder=Path(folder)
    if hours!=8 or folder.exists():raise ValueError("eight-hour new run only; never reset")
    parent_root=ROOT.parent/"ATC-COST-GUARD-13";old=source13.check(parent_root);bindings=reusable_bindings(parent_root)
    namespaces=namespace_check();source_inputs=budget.read(parent_root/"inputs.json")
    inputs=dict(train=source_inputs["train"],development=source_inputs["development"],confirmation=cases(CONFIRM))
    reg=dict(task=budget.TASK,head=subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip(),
        schema=parent.a.SCHEMA,state=226,action=57,padding=32,seeds=SEEDS,reward_arms=ARMS,
        objectives=learning.OBJECTIVES,multipliers={arm:learning.WEIGHTS[arm].tolist() for arm in ARMS},
        sources=source_bindings(old),input_sha=parent.a.native.digest(inputs),old_learned_weights_reused=False,
        parent_registration_path=str(parent_root/"registration.json"),parent_registration_sha=budget.digest(parent_root/"registration.json"),
        reference_bindings_sha=parent.a.native.digest(bindings),origin_map=ORIGIN_MAP,
        origin_checkpoints={str(new):dict(path=old["origin_checkpoints"][str((1103,1109,1117)[(1013,1019,1021).index(oldseed)])]["path"],sha256=old["origin_checkpoints"][str((1103,1109,1117)[(1013,1019,1021).index(oldseed)])]["sha256"]) for new,oldseed in ORIGIN_MAP.items()},
        counts=dict(reused_reference_environments=4400,reuse_new_environment=0,train_cases=2816,dev_cases=176,confirm_cases=176,final_roles=21,final_environments=3696),
        time_objective="CURRENT_COST5 same13 COST5; DEADLINE arms target/reward0 andvalid0false, P95target/cost0valid9false; sixabsservice100; meanfixed85/145seconds signed trapezoid suffix; noholding/completionbonus/P95gate",
        init="fresh paired1201/1213/1217 actor/critic/Adam/action+10000/shuffle+20000 acrossrewardarms; learned origin reference only",
        physical="frozen DROP_FLAG_WAIT1/state226/actions57x32/AVAILABLE/nonpreempt/CG_DC/resourceWAIT; futurequeue/EFT0/Greedyindependent",
        concurrency=1,shared_host_with_12_13=True,started_unix=began,deadline_unix=began+28800,final_reserve_seconds=3600,
        selection="trained512 powers2; only all12 completed DEV; absolute allrequests/units and declared/original U/Nzero ONLY; noP95 guard/key/stop; costJ thenmeanAP180 thenpeak180 earlier; noCP0replacement; final176x21once",
        io_supplement=old["io_supplement"],numerical_episode_environment_cap=None,automatic_adoption=False,experiment_ready=False,device=0,fit=0,S26=0,APK=0)
    folder.mkdir(parents=True)
    protocol=ROOT/"docs/ATC_DEADLINE_MEANAP_STUDY_20261012.md"
    if protocol.exists():shutil.copy2(protocol,folder/"PROTOCOL_REGISTERED.md");reg["protocol_sha256"]=budget.digest(folder/"PROTOCOL_REGISTERED.md")
    write(folder/"registration.json",reg);write(folder/"inputs.json",inputs);write(folder/"namespace_receipt.json",namespaces);write(folder/"reused_reference_bindings.json",bindings)
    for name,sha in reg["sources"].items():
        target=folder/"REGISTERED_SOURCE_TREE"/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/name,target)
        if budget.digest(target)!=sha:raise ValueError("source archive")
    for name,kind in (("controls","control"),("models","model")):
        budget.Budget.register(folder/name,kind,dict(parent_sha=budget.digest(folder/"registration.json"),deadline_unix=reg["deadline_unix"],final_reserve_seconds=3600))
    for binding in bindings:
        for sub,suffix,field in (("rows",".json","row_path"),("items",".json.gz","raw_path")):
            target=folder/binding["target"]/sub/(binding["identity"]+suffix);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(binding[field],target)
            if budget.digest(target)!=binding["row_sha" if sub=="rows" else "raw_sha"]:raise ValueError("reference copy")
    for seed in SEEDS:
        item=reg["origin_checkpoints"][str(seed)];target=folder/"origin_weights"/Path(item["path"]).name;target.parent.mkdir(exist_ok=True);shutil.copy2(item["path"],target)
        if budget.digest(target)!=item["sha256"]:raise ValueError("origin baseline copy")
        for arm in ARMS:
            learner=learning.Learner(seed,deps(reg,arm));learner_path(folder/"models",seed,0,arm).parent.mkdir(exist_ok=True)
            learner.save(learner_path(folder/"models",seed,0,arm));shutil.copy2(learner_path(folder/"models",seed,0,arm),learner_path(folder/"models",seed,None,arm))
    write(folder/"orchestration.json",dict(status="registered",phase="not_started",deadline_unix=reg["deadline_unix"],training_concurrency=1,new_environments=0,new_learning=0))
    return dict(registered=True,reused_references=4400,new_environments=0,new_learning=0)

def check(folder):
    reg=budget.read(Path(folder)/"registration.json")
    if reg["task"]!=budget.TASK or reg["schema"]!=parent.a.SCHEMA or reg["objectives"]!=learning.OBJECTIVES:raise ValueError("registered14 contract")
    for path,sha in reg["sources"].items():
        if budget.digest(ROOT/path)!=sha:raise ValueError("registered source changed "+path)
    if parent.a.native.digest(budget.read(Path(folder)/"inputs.json"))!=reg["input_sha"]:raise ValueError("input changed")
    if budget.digest(reg["parent_registration_path"])!=reg["parent_registration_sha"]:raise ValueError("parent13 registration changed")
    if budget.digest(reg["io_supplement"]["path"])!=reg["io_supplement"]["sha256"]:raise ValueError("IO supplement")
    for item in reg["origin_checkpoints"].values():
        if budget.digest(item["path"])!=item["sha256"]:raise ValueError("fixed origin4096 changed")
    return reg

def learner_path(child,seed,episode=None,reward_arm="CURRENT_COST5"):
    return Path(child)/"checkpoints"/f"{reward_arm}_{seed}_{'latest' if episode is None else 'ep'+str(episode)}.pt"

def collect(b,folder,identity,phase,case,agent,learning_episode=False,zero=False):
    f,init,_=parent.a.hybrid.load();initial=init["initial"]
    qs=case["requests"]
    vectors=parent.realizations(qs,case["arrival_seed"])
    proxy=parent.Proxy(agent);t=time.perf_counter();cpu=time.process_time()
    with b.environment(identity,phase,learning_episode):
        with patch.object(parent.engine,"choose",side_effect=AssertionError("legacyenginechoose forbidden")),patch.object(parent.a.p.Controller,"__call__",side_effect=AssertionError("legacy/EFT decision forbidden")),patch.object(parent.oldstudy.mobile,"eft",side_effect=AssertionError("EFT forbidden")),patch.object(parent.a.p.Controller,"rollout",side_effect=AssertionError("online queue forecast")),patch.object(parent.a.p.Controller,"place",side_effect=AssertionError("online placement")),patch.object(parent.a.hybrid,"costs",side_effect=AssertionError("online AP/J forecast")):
            result=parent.engine.simulate(dict(protocol=parent.a.VERSION,cells=parent.a.p.profile(f)),vectors,qs,policy=agent.policy,settings=parent.a.external.settings(),seed=parent.REALIZATION,decision_provider=proxy)
        audit=parent.audit_ledger(result)
        segments,costs,end=parent.a.hybrid.account(result,initial,f)
        rows=result["ledger"];full=all(r["status"]=="succeeded" for r in rows)
        row=dict(identity=identity,phase=phase,policy=case.get("role") or getattr(agent,"public_policy",getattr(agent,"policy","unknown")),
            **{k:v for k,v in case.items() if k!="requests" and k!="role"},planned=len(qs),
            completed=sum(r["status"]=="succeeded" for r in rows),
            incomplete=sum(r["status"]!="succeeded" for r in rows),
            urgent_planned=sum(r["priority"]=="urgent" for r in rows),
            normal_planned=sum(r["priority"]=="normal" for r in rows),
            urgent_failure=sum(r["priority"]=="urgent" and ("response_ns" not in r or r.get("late_success",False)) for r in rows),
            normal_failure=sum(r["priority"]=="normal" and ("response_ns" not in r or r.get("late_success",False)) for r in rows),
            urgent_p95_ms=result["metrics"]["urgent_p95_ms"],normal_mean_ms=result["metrics"]["normal_mean_ms"],
            energy_j=costs["whole_120s_j"] if full else None,
            peak_ap_c=max(costs["ap_path"]) if full else None,
            native_seconds=time.perf_counter()-t,cpu_seconds=time.process_time()-cpu,
            callbacks=len(proxy.callbacks),controller_observation_seconds=proxy.observation_seconds,controller_event_seconds=proxy.event_seconds,
            modeled_temperature_channel="AP model-plant observation; not surface",experiment_ready=False)
        row["normal_p95_ms"]=parent.a.native.rank95([r["response_ns"]/1e6 for r in rows if r["priority"]=="normal" and "response_ns" in r]) if any(r["priority"]=="normal" and "response_ns" in r for r in rows) else None
        row["max_wait_ms"]=max([(r["dispatch_ns"]-r["arrival_ns"])/1e6 for r in rows if "dispatch_ns" in r] or [0.])
        row["fallbacks"]=getattr(agent,"stats",{}).get("fallback",0)
        row["nonhead_decisions"]=sum(s.get("nonhead_selected",False) for s in getattr(agent,"snapshots",[]))
        row["planned_work_units"]=sum(q["work_units"] for q in qs)
        row["completed_work_units"]=sum(q["work_units"] for q in rows if q["status"]=="succeeded")
        for priority,cap in (("urgent",1.5e9),("normal",6e9)):
            row[priority+"_original_cap_failure"]=sum(q["priority"]==priority and ("response_ns" not in q or q["response_ns"]>cap) for q in rows)
        row["rank_different"]=sum(not x["raw_rank_same"] for x in agent.snapshots)
        row["bank_different"]=sum(not x["ATC_EDD_same"] for x in agent.snapshots)
        row["legal_different"]=sum(not x["ATC_EDD_legal_actions_same"] for x in agent.snapshots)
        curve=list(zip(range(35,end+1),costs["ap_path"]))
        raw=dict(row=row,result=result,curve=curve,segments=segments,
            snapshots=getattr(agent,"snapshots",[]),events=getattr(agent,"events",[]),
            stats=getattr(agent,"stats",{}),stage_times=getattr(agent,"times",[]),
            callbacks=proxy.callbacks,audit=audit)
        observed120=objectives.ap_mean_suffix(raw,35e9,120);observed180=objectives.ap_mean_suffix(raw,35e9,180)
        equalwork=row["completed"]==row["planned"] and row["completed_work_units"]==row["planned_work_units"]
        row.update(observed_mean_ap_120_c=observed120,observed_mean_ap_180_c=observed180,
                   mean_ap_120_c=observed120 if equalwork else None,mean_ap_180_c=observed180 if equalwork else None,
                   mean_ap_equal_work_valid=equalwork)
        path=folder/"items"/(identity+".json.gz");path.parent.mkdir(exist_ok=True)
        if path.exists():raise FileExistsError("raw item already exists")
        tmp=path.with_suffix(path.suffix+".tmp")
        with tmp.open("wb") as stream:
            stream.write(gzip.compress(json.dumps(parent.serial(raw),ensure_ascii=False,allow_nan=False).encode("utf8")));stream.flush();os.fsync(stream.fileno())
        os.replace(tmp,path)
        write(folder/"rows"/(identity+".json"),dict(row=row,raw_sha256=budget.digest(path)))
    return raw


def rows(folder,prefix):
    values=parent.rows(folder,prefix)
    for row in values:
        path=Path(folder)/"items"/(row["identity"]+".json.gz")
        receipt=budget.read(Path(folder)/"rows"/(row["identity"]+".json"))
        if budget.digest(path)!=receipt["raw_sha256"]:raise ValueError("row meanAP raw binding changed")
        if "mean_ap_180_c" not in row:
            raw=json.loads(gzip.decompress(path.read_bytes()))
            observed120=objectives.ap_mean_suffix(raw,35e9,120);observed180=objectives.ap_mean_suffix(raw,35e9,180)
            complete=row["completed"]==row["planned"] and row["completed_work_units"]==row["planned_work_units"]
            row.update(observed_mean_ap_120_c=observed120,observed_mean_ap_180_c=observed180,mean_ap_120_c=observed120 if complete else None,
                       mean_ap_180_c=observed180 if complete else None,mean_ap_equal_work_valid=complete)
    return values

def origin_role(seed):return f"ORIGIN4096_FOR_{seed}_FROM_{ORIGIN_MAP[seed]}"


def origin_model(folder,seed):
    reg=check(folder);oldreg=budget.read(reg["parent_registration_path"])
    longreg=budget.read(oldreg["parent_registration_path"])
    path=Path(folder)/"origin_weights"/Path(reg["origin_checkpoints"][str(seed)]["path"]).name
    if budget.digest(path)!=reg["origin_checkpoints"][str(seed)]["sha256"]:raise ValueError("origin copied weights")
    return prior.learning.Learner.load(path,prior.deps(longreg))


def evaluate(child,b,cases_,roles,learners,phase):
    f,initial,_=parent.a.hybrid.load()
    for case in cases_:
        for role in roles:
            identity=f"{phase}_{case['condition']:02d}_{role}";path=Path(child)/"rows"/(identity+".json")
            if path.exists():
                if budget.digest(Path(child)/"items"/(identity+".json.gz"))!=budget.read(path)["raw_sha256"]:raise ValueError("saved raw changed")
                continue
            if role in BASES:agent=parent.controller(role,f,initial["initial"],{})
            else:agent=learners[role].controller(f,initial["initial"],True)
            raw=collect(b,child,identity,phase,dict(case,role=role),agent)
            if role not in BASES and raw["row"]["fallbacks"]:raise ValueError("invalid model fallback")
    return rows(child,phase+"_")

def controls(folder,phase):
    folder=Path(folder);reg=check(folder);child=folder/"controls";b=budget.Budget(child)
    if phase!="confirmation" or not (folder/"freeze.json").exists():raise ValueError("only frozen fresh control confirmation")
    with b.session():
        rr=evaluate(child,b,budget.read(folder/"inputs.json")["confirmation"],BASES,{},phase)
        write(child/"cursor.json",dict(completed=True,stage="confirmation",rows=len(rr)))
    return dict(completed=True)

def atomic_learner_save(learner,path,child):
    began=time.perf_counter();learner.save(path)
    metric=dict(total_episode=learner.episodes,new_episode=learner.episodes,
                bytes=Path(path).stat().st_size,seconds=time.perf_counter()-began)
    with (Path(child)/"checkpoint_io.jsonl").open("a",encoding="utf8") as stream:
        stream.write(json.dumps(metric)+"\n")


def row_costs(candidate):
    q=parent.primary(candidate)
    for row in q:
        for key in ("energy_j","mean_ap_180_c","peak_ap_c"):
            if key not in row or row[key] is None or not np.isfinite(float(row[key])):return [float("inf")]*3
    return [float(np.mean([row[key] for row in q])) for key in ("energy_j","mean_ap_180_c","peak_ap_c")]


def assess(candidate,rule,inherited):
    q=parent.primary(candidate)
    if len(q)!=160:raise ValueError("primary160 grid incomplete")
    failure_keys=tuple(key for key in SERVICE if key!="urgent_p95_ms")
    bad=[]
    for row in q:
        if any(key not in row or row[key] is None or not np.isfinite(float(row[key])) for key in ("completed","planned","completed_work_units","planned_work_units")):raise ValueError("invalid completion selection metric")
        if any(key not in row or row[key] is None or not np.isfinite(float(row[key])) for key in failure_keys):raise ValueError("invalid service selection metric")
        if row["completed"]!=row["planned"] or row["completed_work_units"]!=row["planned_work_units"] or any(row[key] for key in failure_keys):bad.append(row["condition"])
    costs=row_costs(candidate)
    totals=[sum(row[key] for row in q) for key in failure_keys]
    return dict(eligible_guard=not bad and np.isfinite(costs).all(),absolute_failed_conditions=bad,damage_conditions=len(bad),
        service_risk=totals,risk_key=[len(bad),*totals,*costs],cost_key=costs,
        p95_used_in_selection_or_stop=False)


def completed_stages(folder):return sorted(int(p.stem[5:]) for p in (Path(folder)/"models").glob("stage*.json"))

def stage_receipt(folder,episode,models):
    folder=Path(folder);child=folder/"models";rule=[r for r in rows(folder/"controls","development_") if r["policy"]=="RuleATC"]
    receipts={}
    for seed in SEEDS:
        inherited=rows(folder/f"origin{ORIGIN_MAP[seed]}","dev4096_")
        for arm in ARMS:
            role=f"{arm}_{seed}";candidate=[r for r in rows(child,f"dev{episode}_") if r["policy"]==role];model=models[role]
            receipt=assess(candidate,rule,inherited)
            if model.pending or model.episodes!=episode or len(model.logs)!=episode//8:raise ValueError("new stage model cursor")
            if not any(log["sampled_choices"] for log in model.logs) or any(not np.isfinite(log["actor_gradient_max"]) for log in model.logs):raise ValueError("native mechanics invalid")
            receipt.update(episode=episode,model_sha=budget.digest(learner_path(child,seed,episode,arm)),native_updates=len(model.logs),Adam_steps=model.steps,pending=0)
            receipts[role]=receipt
    write(child/f"stage{episode}.json",dict(episode=episode,models=receipts,all_twelve_completed=True))
    return receipts

def initial_proof(folder,b,models):
    folder=Path(folder);child=folder/"models";path=child/"initial_teacher_proof.json"
    if path.exists():return
    inputs=budget.read(folder/"inputs.json")["development"];proofs=[]
    for arm in ARMS:
        role=f"{arm}_{SEEDS[0]}"
        for index in (0,2,12,17):
            identity=f"initialproof_{index:02d}_{role}"
            raw=collect(b,child,identity,"initialproof",dict(inputs[index],role=role),models[role].controller(*parent._initial(),True))
            ref=json.loads(gzip.decompress((folder/"controls/items"/f"development_{index:02d}_RuleATC.json.gz").read_bytes()))
            if raw["result"]["ledger"]!=ref["result"]["ledger"] or raw["result"]["transitions"]!=ref["result"]["transitions"]:raise ValueError("native CP0 teacher differs")
            proofs.append(dict(role=role,condition=index,exact=True))
    write(path,dict(status="PASS16_native_teacher_exact",proofs=proofs,new_environments=16,learning=0))

def train(folder,through,stop_after=None,first_seed_only=False):
    if through<512 or through&(through-1):raise ValueError("fresh power2 >=512")
    folder=Path(folder);reg=check(folder);child=folder/"models";b=budget.Budget(child);inputs=budget.read(folder/"inputs.json")
    if (folder/"freeze.json").exists():raise ValueError("never train after freeze")
    models={f"{arm}_{seed}":learning.Learner.load(learner_path(child,seed,None,arm),deps(reg,arm)) for seed in SEEDS for arm in ARMS}
    if any(len(model.pending)>=8 for model in models.values()):raise ValueError("failed batch needs audit")
    active=[f"{arm}_{seed}" for seed in (SEEDS[:1] if first_seed_only else SEEDS) for arm in ARMS]
    f,initial,_=parent.a.hybrid.load();accepted=0
    with b.session():
        initial_proof(folder,b,models)
        try:
            for n in range(through):
                for role in active:
                    model=models[role];arm,ss=role.rsplit("_",1);seed=int(ss)
                    if model.episodes>n:continue
                    if model.episodes!=n:raise ValueError("learner cursor")
                    case=inputs["train"][n%len(inputs["train"])];identity=f"train_{role}_{n:06d}"
                    if (child/"rows"/(identity+".json")).exists():raise ValueError("consumed unadopted rollout")
                    ready,reason=b.can_begin("train")
                    if not ready:raise budget.ControlledStop(reason)
                    agent=model.controller(f,initial["initial"],False)
                    raw=collect(b,child,identity,"train",dict(case,role=role),agent,True)
                    if raw["row"]["fallbacks"]:raise ValueError("invalid learned model fallback")
                    rp=folder/"controls/items"/f"teacher_train_{case['condition']:02d}_RuleATC.json.gz";receipt=budget.read(folder/"controls/rows"/(rp.name[:-8]+".json"))
                    if budget.digest(rp)!=receipt["raw_sha256"]:raise ValueError("teacher changed")
                    ref=json.loads(gzip.decompress(rp.read_bytes()))
                    if ref["row"]["arrival_seed"]!=case["arrival_seed"] or ref["row"]["condition"]!=case["condition"]:raise ValueError("teacher exogenous mismatch")
                    frames,costs,valid,_=learning.targets(agent,raw,initial["initial"]["preload_power_w"]*120,arm,ref)
                    model.add(frames,costs,valid,raw["row"]);model.cursor=dict(episode=model.episodes);model.consumption=b.used()
                    atomic_learner_save(model,learner_path(child,seed,None,arm),child)
                    accepted+=1
                    if stop_after and accepted>=stop_after:
                        proof={}
                        for rr in active:
                            aa,ss=rr.rsplit("_",1);m=models[rr];target=child/"paused_checkpoints"/(rr+".pt");target.parent.mkdir(exist_ok=True);m.save(target)
                            proof[rr]=dict(digest=parent.payload_digest(m.snapshot()),episodes=m.episodes,pending=len(m.pending),Adam_steps=m.steps)
                        write(child/"pause_receipt.json",dict(accepted=accepted,models=proof));return dict(paused=True,accepted=accepted)
                if (n+1)%32==0:print(json.dumps(dict(episode_per_model=n+1,active_models=len(active))),flush=True)
            for role,model in models.items():
                arm,ss=role.rsplit("_",1)
                if model.episodes!=through or model.pending:raise ValueError("all12 milestone incomplete")
                atomic_learner_save(model,learner_path(child,int(ss),through,arm),child)
            evaluate(child,b,inputs["development"],list(models),models,f"dev{through}")
        except budget.ControlledStop as reason:
            write(child/"boundary_stop.json",dict(reason=str(reason),resources=getattr(b,"last_resources",{}),episodes={role:m.episodes for role,m in models.items()},pending={role:len(m.pending) for role,m in models.items()}));return dict(stopped=True,reason=str(reason))
        except BaseException as error:
            for role,model in models.items():
                aa,ss=role.rsplit("_",1);atomic_learner_save(model,learner_path(child,int(ss),None,aa),child)
            write(child/"failure_receipt.json",dict(error=repr(error),consumption=b.used()));raise
    return dict(completed=True,stage=through,receipt=stage_receipt(folder,through,models))

def numeric_key(values):
    return tuple(float("inf") if x is None or x=="UNAVAILABLE" else float(x) for x in values)


def best_key(history):
    eligible=[x for x in history if x["eligible_guard"]]
    item=min(eligible or history,key=lambda x:(numeric_key(x["cost_key"] if eligible else x["risk_key"]),x["episode"]))
    return (0 if eligible else 1,numeric_key(item["cost_key"] if eligible else item["risk_key"]))


def continuation_stop(histories):
    n=len(next(iter(histories.values())))
    if any(len(value)!=n for value in histories.values()):raise ValueError("allseed common completedstage only")
    if n>=3 and sum(history[-3]["damage_conditions"]<history[-2]["damage_conditions"]<history[-1]["damage_conditions"] for history in histories.values())>=2:
        return "two_transition_service_damage_at_two_seeds"
    if n>=4:
        def improved(history):
            earlier=history[:-3];current=history
            if min(item["damage_conditions"] for item in current)<min(item["damage_conditions"] for item in earlier):return True
            oldservice=min(tuple(item["service_risk"]) for item in earlier)
            newservice=min(tuple(item["service_risk"]) for item in current)
            if newservice<oldservice:return True
            old=[item for item in earlier if item["eligible_guard"]];new=[item for item in current if item["eligible_guard"]]
            if new and not old:return True
            if not old or not new:return False
            before=min(old,key=lambda x:numeric_key(x["cost_key"]));after=min(new,key=lambda x:numeric_key(x["cost_key"]))
            b,a=numeric_key(before["cost_key"]),numeric_key(after["cost_key"])
            return all(x<=y for x,y in zip(a,b)) and (b[0]-a[0]>=.005 or b[1]-a[1]>=.0005)
        if not any(improved(history) for history in histories.values()):return "three_additional_stage_cost_stagnation"
    return None


def select_and_freeze(folder):
    folder=Path(folder);reg=check(folder);available=completed_stages(folder)
    if not available or (folder/"freeze.json").exists():raise ValueError("all12 trained stage required; freeze once")
    selections={};origins={}
    for seed in SEEDS:
        for arm in ARMS:
            role=f"{arm}_{seed}";history=[budget.read(folder/"models"/f"stage{episode}.json")["models"][role] for episode in available]
            eligible=[item for item in history if item["eligible_guard"]]
            chosen=min(eligible or history,key=lambda x:(numeric_key(x["cost_key"] if eligible else x["risk_key"]),x["episode"]))
            ep=chosen["episode"];path=learner_path(folder/"models",seed,ep,arm)
            if budget.digest(path)!=chosen["model_sha"]:raise ValueError("trained model changed")
            selections[role]=dict(episodes=ep,sha256=budget.digest(path),reward_arm=arm,seed=seed,development_guard_pass=bool(eligible),eligible_checkpoints=[x['episode'] for x in eligible],trained_candidate=True,development_key=chosen['risk_key'],development_cost_key=chosen['cost_key'])
        origins[origin_role(seed)]=dict(episodes=4096,sha256=reg['origin_checkpoints'][str(seed)]['sha256'],new_seed=seed,origin_seed=ORIGIN_MAP[seed],reference_only=True)
    selected=min(selections,key=lambda role:(not selections[role]['development_guard_pass'],numeric_key(selections[role]['development_cost_key'] if selections[role]['development_guard_pass'] else selections[role]['development_key']),selections[role]['episodes'],role))
    freeze_write(folder/'models/freeze.json',dict(selections=selections,origin_selections=origins,registration_sha=budget.digest(folder/'registration.json'),input_sha=reg['input_sha'],sources_sha=parent.a.native.digest(reg['sources']),confirmation_not_read=True))
    freeze_write(folder/'freeze.json',dict(selected=selected,selections=selections,origin_selections=origins,completed_by_all_models=available,registration_sha=budget.digest(folder/'registration.json'),input_sha=reg['input_sha'],sources_sha=parent.a.native.digest(reg['sources']),confirmation_not_read=True,all_twelve_fresh=True))
    return dict(frozen=True,selected=selected)

def confirm(folder):
    folder=Path(folder);reg=check(folder);frozen=budget.read(folder/'freeze.json');child=folder/'models';b=budget.Budget(child)
    if not frozen.get('frozen_utc'):raise ValueError('freeze metadata incomplete')
    models={}
    for role,item in frozen['selections'].items():
        arm,ss=role.rsplit('_',1);path=learner_path(child,int(ss),item['episodes'],arm)
        if budget.digest(path)!=item['sha256']:raise ValueError('frozen weights')
        models[role]=learning.Learner.load(path,deps(reg,arm))
    for seed in SEEDS:models[origin_role(seed)]=origin_model(folder,seed)
    with b.session():
        evaluate(child,b,budget.read(folder/'inputs.json')['confirmation'],list(models),models,'confirmation')
        write(child/'cursor.json',dict(completed=True,stage='confirmation'))
    return dict(completed=True)

def merge(folder):
    folder=Path(folder);check(folder)
    if not all(budget.read(folder/child/'cursor.json')['completed'] for child in ('models','controls')):raise ValueError('final incomplete')
    rr=rows(folder/'controls','confirmation_')+rows(folder/'models','confirmation_')
    roles=(*BASES,*(f'{arm}_{seed}' for seed in SEEDS for arm in ARMS),*(origin_role(seed) for seed in SEEDS))
    expected={(case['condition'],role) for case in budget.read(folder/'inputs.json')['confirmation'] for role in roles}
    if len(rr)!=3696 or {(r['condition'],r['policy']) for r in rr}!=expected:raise ValueError('exact final176x21 grid')
    used=[budget.Budget(folder/child).used() for child in ('controls','models')]
    cons=dict(environments=sum(x['environments'] for x in used),learning=sum(x['learning'] for x in used),failed=sum(x['failed'] for x in used),workers=used,worker_active_seconds_sum=sum(x['active_seconds'] for x in used),reused_reference_raw=4400,reused_reference_new_environments=0,device=0,S26=0)
    write(folder/'consumption.json',cons);write(folder/'final_rows.json',rr);return dict(completed=True,rows=len(rr),consumption=cons)

def main():
    p=argparse.ArgumentParser();p.add_argument('command',choices=('preflight','register','check','train','freeze','confirm','controls','merge'));p.add_argument('--run-root',type=Path);p.add_argument('--through',type=int,default=512);p.add_argument('--phase',choices=('confirmation',));p.add_argument('--stop-after',type=int);p.add_argument('--first-seed-only',action='store_true');x=p.parse_args()
    if x.command=='preflight':result=preflight()
    elif x.command=='register':result=register(x.run_root)
    elif x.command=='check':result=check(x.run_root)
    elif x.command=='train':result=train(x.run_root,x.through,x.stop_after,x.first_seed_only)
    elif x.command=='freeze':result=select_and_freeze(x.run_root)
    elif x.command=='confirm':result=confirm(x.run_root)
    elif x.command=='controls':result=controls(x.run_root,x.phase)
    else:result=merge(x.run_root)
    print(json.dumps(parent.serial(result),ensure_ascii=False),flush=True)

if __name__=="__main__":main()
