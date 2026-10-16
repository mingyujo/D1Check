"""New data/ledgers and exact warm continuation, frozen V8 inference/physics/loss."""
import argparse
import copy
import gzip
import hashlib
import json
import math
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch

from tools import d1_atc_waitlink_study as parent
from tools import d1_atc_waitlink_ppo as learning
from tools import d1_atc_waitlong_budget as budget
from tools import d1_atc_waitlong_migration as migration

ROOT = Path(__file__).resolve().parents[1]
SEEDS = migration.SEEDS
ARM = migration.ARM
ARMS = (ARM,)
BASE_EPISODES = migration.BASE_EPISODES
BASES = parent.BASES
TRAIN = tuple(range(923510101, 923510229))
DEV = tuple(range(923610101, 923610109))
CONFIRM = tuple(range(923710101, 923710109))
FINAL_RESERVE = 1800
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


def cases(seeds):
    values = parent.cases(seeds)
    for value in values:
        value["context"] = "longtrain12_newdata_same_n1_currentowner_contract"
    return values


def namespace_check():
    reserved = parent.registry.collect()
    requested = set(TRAIN + DEV + CONFIRM)
    if requested & set(reserved["seeds"]) or any(lo <= seed <= hi for seed in requested for lo, hi in reserved["ranges"]):
        raise ValueError("registered arrival namespace collision")
    receipts = []
    for path in sorted(ROOT.parent.glob("*/inputs.json")):
        # Seed reservation metadata scan only; no old final results are evaluated.
        raw = path.read_bytes(); text = raw.decode("utf-8-sig")
        if any(str(seed) in text for seed in requested):
            raise ValueError("local input seed collision " + str(path))
        receipts.append(dict(path=str(path), sha256=hashlib.sha256(raw).hexdigest()))
    return dict(registry=reserved, local_input_receipts=receipts,
                train=list(TRAIN), development=list(DEV), confirmation=list(CONFIRM))


def source_bindings(origin_reg):
    paths = set(origin_reg["sources"])
    paths |= {"tools/test_d1_atc_waitlink.py", "tools/test_d1_atc_waitlong.py"}
    paths |= {"tools/d1_atc_waitlong_" + name + ".py" for name in
              ("migration", "budget", "study", "orchestrator", "report")}
    return {name: budget.digest(ROOT/name) for name in sorted(paths)}


def deps(reg):
    return dict(schema=parent.a.SCHEMA, arm=ARM, sequencing="ATC",
                objective=learning.OBJECTIVES[ARM], sources=reg["sources"], input_sha=reg["input_sha"])


def preflight():
    origin_root = ROOT.parent / "ATC-WAITLINK-EXPAND-11"
    reg, origins = migration.read_origins(origin_root)
    namespace = namespace_check()
    inputs = dict(train=cases(TRAIN), development=cases(DEV), confirmation=cases(CONFIRM))
    proposed = dict(sources=source_bindings(reg), input_sha=parent.a.native.digest(inputs))
    receipts = {}
    for seed, item in origins.items():
        _, receipt = migration.rebind(item["snapshot"], parent.deps(reg, ARM), deps(proposed), seed)
        receipts[str(seed)] = dict(receipt, origin_sha256=item["sha256"])
    return dict(status="PASS_exact_warm_preflight", counts={k:len(v) for k,v in inputs.items()},
                receipts=receipts, namespace_checked=True, new_environments=0, new_learning=0)


def register(folder, hours=6):
    began = time.time()
    if hours != 6:
        raise ValueError("registered wall budget is six hours")
    folder = Path(folder)
    if folder.exists():
        raise FileExistsError("never reset a consumed or registered run")
    origin_root = ROOT.parent / "ATC-WAITLINK-EXPAND-11"
    old, origins = migration.read_origins(origin_root)
    namespace = namespace_check()
    inputs = dict(train=cases(TRAIN), development=cases(DEV), confirmation=cases(CONFIRM))
    io_binding = budget.read(origin_root / "io_transport_binding.json")
    if budget.digest(io_binding["supplement"]["path"]) != io_binding["supplement"]["sha256"]:
        raise ValueError("old IO supplement changed")
    reg = dict(task=budget.TASK, head=subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip(), schema=parent.a.SCHEMA, arm=ARM, seeds=SEEDS,
               state=226, action=57, padding=32, objective=learning.OBJECTIVES[ARM],
               sources=source_bindings(old), input_sha=parent.a.native.digest(inputs),
               origin_registration_sha=budget.digest(origin_root/"registration.json"),
               origin_registration_path=str(origin_root/"registration.json"),
               origins={str(seed):dict(path=str(item["path"]),sha256=item["sha256"],episodes=4096)
                        for seed,item in origins.items()},
               source_inputs_migration="only dependencies.sources/input_sha; all learner state exact; original PT unchanged",
               counts=dict(train_cases=2816,dev_cases=176,confirm_cases=176,final_roles=12,final_environments=2112,old_reference_copy=0),
               total_episode_origin=4096, new_episode_count="total minus4096; only new environments enter ledger",
               started_unix=began, deadline_unix=began+hours*3600, wall_hours=hours,
               final_reserve_seconds=FINAL_RESERVE, numerical_episode_environment_cap=None,
               milestones="4096 inherited baseline, 8192/16384/32768/65536 then powers2 if time permits",
               stop_rule="primary RuleATC and same-seed inherited service/P95 damage; >=2seeds increase over2consecutive transitions, or no best eligible/risk improvement and no .005J conditionwise nondegrading gain over3additional stages; reserve checks before every environment",
               data="new2816/176/176 arrival namespaces, all11families x2factors; previous final results not used",
               contract="same frozen11 DROP_FLAG_WAIT1/URGENT_HOLD/226x57x32/physicalmask/currentphase/AVAILABLE/CG_DC; noEFT/Greedy inside; nofuturequeueforecast; noNPU/cooling",
               selection="only stages completed by all3seeds; RuleATC AND same-seed inherited4096 percondition service/P95 eligible guard; costs separate meanJ/AP/P95 key; inherited4096 allowed; allseed reported; one newfinal176x12 rules6 selected3 inherited3 after parentfreeze; nofinalguided retuning",
               io_supplement=io_binding["supplement"], automatic_adoption=False, experiment_ready=False,
               device=0, APK=0, S26=0, fit=0)
    folder.mkdir(parents=True)
    protocol=ROOT/"docs/ATC_WAIT_LONGTRAIN_STUDY_20261012.md"
    if protocol.exists():
        shutil.copy2(protocol,folder/"PROTOCOL_REGISTERED.md")
        reg["protocol_sha256"]=budget.digest(folder/"PROTOCOL_REGISTERED.md")
    write(folder/"registration.json",reg); write(folder/"inputs.json",inputs); write(folder/"namespace_receipt.json",namespace)
    for name,sha in reg["sources"].items():
        target=folder/"REGISTERED_SOURCE_TREE"/name;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(ROOT/name,target)
        if budget.digest(target)!=sha:raise ValueError("source archive mismatch "+name)
    budget.Budget.register(folder/"controls","control",dict(parent_sha=budget.digest(folder/"registration.json"),deadline_unix=reg["deadline_unix"],final_reserve_seconds=FINAL_RESERVE))
    migration_receipts = {}
    for seed,item in origins.items():
        child=folder/f"seed{seed}"
        budget.Budget.register(child,"model",dict(parent_sha=budget.digest(folder/"registration.json"),seed=seed,deadline_unix=reg["deadline_unix"],final_reserve_seconds=FINAL_RESERVE))
        (child/"checkpoints").mkdir(); (child/"origin").mkdir()
        shutil.copy2(item["path"],child/"origin"/item["path"].name)
        if budget.digest(child/"origin"/item["path"].name)!=item["sha256"]:
            raise ValueError("origin copy mismatch")
        learner,receipt=migration.rebind(item["snapshot"],parent.deps(old,ARM),deps(reg),seed)
        learner.save(learner_path(child,seed,4096)); shutil.copy2(learner_path(child,seed,4096),learner_path(child,seed))
        receipt.update(origin_file=str(item["path"]),origin_sha256=item["sha256"],
                       new_initial_sha256=budget.digest(learner_path(child,seed,4096)),
                       old_registration_sha=reg["origin_registration_sha"],new_registration_sha=budget.digest(folder/"registration.json"))
        write(child/"migration_receipt.json",receipt); migration_receipts[str(seed)]=receipt
        write(child/"cursor.json",dict(completed=False,stage="inherited",total_episodes=4096,new_learning_accepted=0))
    write(folder/"migration_receipt.json",dict(status="PASS_exact_three_terminal_origins",models=migration_receipts,new_environments=0,new_learning=0))
    write(folder/"orchestration.json",dict(status="registered",phase="not_started",deadline_unix=reg["deadline_unix"],new_environments=0,new_learning=0))
    return dict(registered=True,deadline_unix=reg["deadline_unix"],new_environments=0,new_learning=0)


def check(folder):
    reg=budget.read(Path(folder)/"registration.json")
    if reg["task"]!=budget.TASK or reg["schema"]!=parent.a.SCHEMA or reg["objective"]!=learning.OBJECTIVES[ARM]:
        raise ValueError("immutable registered contract")
    for path,sha in reg["sources"].items():
        if budget.digest(ROOT/path)!=sha:raise ValueError("registered source changed "+path)
    if parent.a.native.digest(budget.read(Path(folder)/"inputs.json"))!=reg["input_sha"]:
        raise ValueError("registered input changed")
    if budget.digest(reg["origin_registration_path"])!=reg["origin_registration_sha"]:
        raise ValueError("origin registration changed")
    for item in reg["origins"].values():
        if budget.digest(item["path"])!=item["sha256"]:raise ValueError("origin PT changed")
    if budget.digest(reg["io_supplement"]["path"])!=reg["io_supplement"]["sha256"]:
        raise ValueError("IO supplement changed")
    return reg


def learner_path(child,seed,episode=None):
    return Path(child)/"checkpoints"/f"{ARM}_{seed}_{'latest' if episode is None else 'ep'+str(episode)}.pt"


def rows(folder,prefix):
    return parent.rows(folder,prefix)


def evaluate(child,b,cases_,roles,learners,phase):
    f, initial, _ = parent.a.hybrid.load()
    for case in cases_:
        for role in roles:
            identity=f"{phase}_{case['condition']:02d}_{role}";path=Path(child)/"rows"/(identity+".json")
            if path.exists():
                if budget.digest(Path(child)/"items"/(identity+".json.gz"))!=budget.read(path)["raw_sha256"]:
                    raise ValueError("saved raw changed")
                continue
            if role.startswith("INHERITED4096_"):
                seed=int(role.rsplit("_",1)[1]);agent=learners[(ARM,seed,"inherited")].controller(f,initial["initial"],True)
            else:agent=parent.controller(role,f,initial["initial"],learners)
            raw=parent.collect(b,child,identity,phase,dict(case,role=role),agent)
            if role not in BASES and raw["row"]["fallbacks"]:
                raise ValueError("learned-model fallback is an invalid evaluation, preserved for audit")
        if case["condition"]%32==0:print(json.dumps(dict(phase=phase,case=case["condition"],worker=Path(child).name)),flush=True)
    return rows(child,phase+"_")


def controls(folder,phase):
    reg=check(folder);folder=Path(folder);child=folder/"controls";b=budget.Budget(child)
    inputs=budget.read(folder/"inputs.json")
    if phase=="confirmation" and not(folder/"freeze.json").exists():raise ValueError("parentfreeze required")
    if phase=="confirmation" and not budget.read(folder/"freeze.json").get("frozen_utc"):raise ValueError("parent freeze metadata incomplete")
    with b.session():
        try:
            if phase=="development":evaluate(child,b,inputs["train"],["RuleATC"],{},"teacher_train")
            rr=evaluate(child,b,inputs["development" if phase=="development" else "confirmation"],BASES,{},phase)
        except budget.ControlledStop as reason:
            write(child/"cursor.json",dict(completed=False,stage=phase,controlled_stop=str(reason)))
            return dict(stopped=True,reason=str(reason),consumption=b.used())
        write(child/"cursor.json",dict(completed=phase=="confirmation",stage=phase,rows=len(rr)))
    return dict(completed=True,phase=phase,consumption=b.used())


def atomic_learner_save(learner,path,child):
    began=time.perf_counter();learner.save(path)
    metric=dict(total_episode=learner.episodes,new_episode=learner.episodes-4096,
                bytes=Path(path).stat().st_size,seconds=time.perf_counter()-began)
    with (Path(child)/"checkpoint_io.jsonl").open("a",encoding="utf8") as stream:
        stream.write(json.dumps(metric)+"\n")


def assess(candidate,rule,inherited):
    q=parent.primary(candidate);byrule={r["condition"]:r for r in rule};bybase={r["condition"]:r for r in inherited}
    if len(q)!=len(parent.primary(rule)) or len(q)!=len(parent.primary(inherited)):
        raise ValueError("development grid incomplete")
    def damaged(r,ref):
        return (r["completed"]!=r["planned"] or r["completed_work_units"]!=r["planned_work_units"] or
                any(r[k] is None or ref[r["condition"]][k] is None or r[k]>ref[r["condition"]][k] for k in SERVICE))
    def damage(ref):
        return sum(damaged(r,ref) for r in q)
    rdamage,bdamage=damage(byrule),damage(bybase)
    costs_good=not(rdamage or bdamage)
    for r in q:
        for ref in (byrule,bybase):
            for key in ("energy_j","peak_ap_c"):
                costs_good=costs_good and r[key] is not None and ref[r["condition"]][key] is not None and r[key]<=ref[r["condition"]][key]
    gain=np.mean([bybase[r["condition"]]["energy_j"]-r["energy_j"] for r in q]) if all(r["energy_j"] is not None and bybase[r["condition"]]["energy_j"] is not None for r in q) else None
    worst={name:{key:max([r[key]-ref[r["condition"]][key] for r in q if r[key] is not None and ref[r["condition"]][key] is not None],default=None)
                 for key in (*SERVICE,"energy_j","peak_ap_c")} for name,ref in (("RuleATC",byrule),("inherited_same_seed",bybase))}
    return dict(rule_guard=parent.eligible(candidate,rule),eligible_guard=bool(parent.eligible(candidate,rule) and bdamage==0),rule_damage_conditions=int(rdamage),
                inherited_damage_conditions=int(bdamage),damage_conditions=int(sum(damaged(r,byrule) or damaged(r,bybase) for r in q)),
                worst_deltas=worst,risk_key=parent.key(candidate),cost_key=parent.cost_key(candidate),
                conditionwise_nondegrading_cost=bool(costs_good),mean_J_gain_vs_inherited=gain,
                meaningful_cost_gain=bool(costs_good and gain is not None and gain>=.005))


def completed_stages(folder):
    sets=[{int(path.stem[5:]) for path in (Path(folder)/f"seed{seed}").glob("stage*.json")} for seed in SEEDS]
    return sorted(set.intersection(*sets)) if all(sets) else []


def stage_receipt(folder,seed,episode):
    child=Path(folder)/f"seed{seed}";role=f"{ARM}_{seed}";candidate=rows(child,f"dev{episode}_")
    rule=[r for r in rows(Path(folder)/"controls","development_") if r["policy"]=="RuleATC"]
    inherited=rows(child,"dev4096_");snapshot=learning.Learner.load(learner_path(child,seed,episode),deps(check(folder)))
    result=assess(candidate,rule,inherited)
    origin_steps=budget.read(child/"migration_receipt.json")["origin_Adam_steps"]
    newlogs=snapshot.logs[512:]
    mechanics=(len(newlogs)==(episode-4096)//8 and snapshot.steps>=origin_steps and not snapshot.pending
               and all(np.isfinite(log["actor_gradient_max"]) and (log["critic_only"] or log["actor_gradient_max"]>0) for log in newlogs)
               and all(torch_finite_parameter(value) for value in snapshot.network.state_dict().values())
               and all(torch_finite_parameter(value["exp_avg"]) and torch_finite_parameter(value["exp_avg_sq"])
                       for value in snapshot.optimizer.state_dict()["state"].values()))
    if episode>4096:
        mechanics=mechanics and any(log["sampled_choices"]>0 for log in newlogs)
    if not mechanics:raise ValueError("new native update mechanics invalid; do not count inherited logs as new learning")
    result.update(episode=episode,new_episodes=episode-4096,model_sha=budget.digest(learner_path(child,seed,episode)),
                  new_environments=budget.Budget(child).used()["environments"],new_learning=budget.Budget(child).used()["learning"],
                  native_updates=len(snapshot.logs),Adam_steps=snapshot.steps,
                  inherited_native_updates=512,inherited_Adam_steps=origin_steps,
                  new_native_updates=len(newlogs),new_Adam_steps=snapshot.steps-origin_steps,
                  new_actor_updates=sum(log["actor_changed"] for log in newlogs),
                  new_critic_only_updates=sum(log["critic_only"] for log in newlogs),
                  new_sampled_choices=sum(log["sampled_choices"] for log in newlogs),
                  new_mechanics_pass=bool(mechanics),
                  exact_pending0=not snapshot.pending,
                  actor_updates=sum(log["actor_changed"] for log in snapshot.logs))
    write(child/f"stage{episode}.json",result)
    return result


def baseline(folder,seed):
    folder=Path(folder);reg=check(folder);child=folder/f"seed{seed}";b=budget.Budget(child)
    if (child/"stage4096.json").exists():return dict(completed=True,stage=4096)
    model=learning.Learner.load(learner_path(child,seed,4096),deps(reg))
    with b.session():
        try:evaluate(child,b,budget.read(folder/"inputs.json")["development"],[f"{ARM}_{seed}"],{(ARM,seed):model},"dev4096")
        except budget.ControlledStop as reason:return dict(stopped=True,reason=str(reason))
    return dict(completed=True,stage=4096,receipt=stage_receipt(folder,seed,4096))


def train(folder,seed,through):
    if through<8192 or through&(through-1):raise ValueError("total power2 milestone >=8192")
    folder=Path(folder);reg=check(folder);child=folder/f"seed{seed}";b=budget.Budget(child)
    if (folder/"freeze.json").exists():raise ValueError("never train after freeze")
    if not(child/"stage4096.json").exists():raise ValueError("inherited development must be locked first")
    model=learning.Learner.load(learner_path(child,seed),deps(reg));inputs=budget.read(folder/"inputs.json")
    if len(model.pending)>=8:raise ValueError("failed native update pending batch requires explicit audit, not automatic continuation")
    f,initial,_=parent.a.hybrid.load()
    with b.session():
        try:
            for global_index in range(4096,through):
                if model.episodes>global_index:continue
                if model.episodes!=global_index:raise ValueError("learner local/global cursor")
                case=inputs["train"][(global_index-4096)%len(inputs["train"])]
                identity=f"train_{ARM}_{seed}_{global_index:06d}"
                if (child/"rows"/(identity+".json")).exists():raise ValueError("unadopted consumed rollout; audit before resume")
                ready,reason=b.can_begin("train")
                if not ready:raise budget.ControlledStop(reason)
                agent=model.controller(f,initial["initial"],False)
                raw=parent.collect(b,child,identity,"train",dict(case,role=f"{ARM}_{seed}"),agent,True)
                if raw["row"]["fallbacks"]:raise ValueError("learned-model fallback in training, preserve rollout")
                refpath=folder/"controls/items"/f"teacher_train_{case['condition']:02d}_RuleATC.json.gz"
                receipt=budget.read(folder/"controls/rows"/(refpath.name[:-8]+".json"))
                if budget.digest(refpath)!=receipt["raw_sha256"]:raise ValueError("teacher raw changed")
                reference=json.loads(gzip.decompress(refpath.read_bytes()))
                if (reference["row"]["arrival_seed"]!=case["arrival_seed"] or reference["row"]["condition"]!=case["condition"]
                        or raw["row"]["arrival_seed"]!=reference["row"]["arrival_seed"]):
                    raise ValueError("new teacher exogenous realization/case differs")
                frames,costs,valid,_=learning.targets(agent,raw,initial["initial"]["preload_power_w"]*120,ARM,reference)
                model.add(frames,costs,valid,raw["row"])
                model.cursor=dict(episode=model.episodes,new_episode=model.episodes-4096)
                model.consumption=b.used();atomic_learner_save(model,learner_path(child,seed),child)
                write(child/"cursor.json",dict(completed=False,stage="train",total_episodes=model.episodes,new_learning_accepted=model.episodes-4096))
                if (global_index+1)%32==0:print(json.dumps(dict(seed=seed,total_episode=global_index+1,new_episode=global_index+1-4096)),flush=True)
            if model.pending:raise ValueError("milestone pending not zero")
            atomic_learner_save(model,learner_path(child,seed,through),child)
            evaluate(child,b,inputs["development"],[f"{ARM}_{seed}"],{(ARM,seed):model},f"dev{through}")
        except budget.ControlledStop as reason:
            write(child/"boundary_stop.json",dict(reason=str(reason),total_episode=model.episodes,new_episode=model.episodes-4096,pending=len(model.pending),latest_sha=budget.digest(learner_path(child,seed))))
            return dict(stopped=True,reason=str(reason),total_episode=model.episodes)
        except BaseException as error:
            # Preserve the in-memory action RNG/pending after a consumed rollout,
            # even if validation/update failed. Never resimulate an identity.
            model.cursor=dict(episode=model.episodes,new_episode=model.episodes-4096)
            model.consumption=b.used()
            checkpoint_error=None
            try:atomic_learner_save(model,learner_path(child,seed),child)
            except BaseException as secondary:checkpoint_error=repr(secondary)
            write(child/"failure_receipt.json",dict(error=repr(error),checkpoint_error=checkpoint_error,
                total_episode=model.episodes,new_episode=model.episodes-4096,pending=len(model.pending),consumption=b.used()))
            raise
    return dict(completed=True,stage=through,receipt=stage_receipt(folder,seed,through))


def numeric_key(values):
    return tuple(float("inf") if x is None or x=="UNAVAILABLE" else float(x) for x in values)


def best_key(history):
    eligible=[x for x in history if x["eligible_guard"]]
    item=min(eligible or history,key=lambda x:(numeric_key(x["cost_key"] if eligible else x["risk_key"]),x["episode"]))
    return (0 if eligible else 1,numeric_key(item["cost_key"] if eligible else item["risk_key"]))


def continuation_stop(histories):
    """Only all-seed completed stages; deterministic development-only criteria."""
    lengths={len(value) for value in histories.values()}
    if len(lengths)!=1:raise ValueError("stage stop requires all seeds completed")
    n=lengths.pop()
    damage=0
    if n>=3:
        for history in histories.values():
            if history[-3]["damage_conditions"]<history[-2]["damage_conditions"]<history[-1]["damage_conditions"]:damage+=1
    if damage>=2:return "two_transition_service_P95_damage_at_two_seeds"
    if n>=4:
        stalled=all(best_key(history)==best_key(history[:-3]) and not any(item["meaningful_cost_gain"] for item in history[-3:]) for history in histories.values())
        if stalled:return "three_additional_stage_stagnation"
    return None


def select_and_freeze(folder):
    folder=Path(folder);reg=check(folder);available=completed_stages(folder)
    if not available or available[0]!=4096:raise ValueError("allseed inherited baseline not complete")
    if (folder/"freeze.json").exists() or any(folder.glob("*/rows/confirmation_*.json")):raise ValueError("freeze once before confirmation")
    selections={};inherited_selections={}
    for seed in SEEDS:
        child=folder/f"seed{seed}";history=[budget.read(child/f"stage{episode}.json") for episode in available]
        eligible=[item for item in history if item["eligible_guard"]]
        chosen=min(eligible or history,key=lambda x:(numeric_key(x["cost_key"] if eligible else x["risk_key"]),x["episode"]))
        episode=chosen["episode"];path=learner_path(child,seed,episode)
        if budget.digest(path)!=chosen["model_sha"]:raise ValueError("completed model changed")
        role=f"{ARM}_{seed}";item=dict(episodes=episode,new_episodes=episode-4096,sha256=budget.digest(path),
            development_guard_pass=bool(eligible),eligible_checkpoints=[v["episode"] for v in eligible],
            inherited_selected=episode==4096,selected_has_new_updates=episode>4096,
            development_key=chosen["risk_key"],development_cost_key=chosen["cost_key"])
        inherited_role=f"INHERITED4096_{ARM}_{seed}"
        inherited_item=dict(episodes=4096,new_episodes=0,sha256=budget.digest(learner_path(child,seed,4096)),
                            origin_sha256=reg["origins"][str(seed)]["sha256"],inherited_baseline=True)
        freeze_write(child/"freeze.json",dict(selections={role:item},inherited_selections={inherited_role:inherited_item},
              registration_sha=budget.digest(folder/"registration.json"),input_sha=reg["input_sha"],
              sources_sha=parent.a.native.digest(reg["sources"]),confirmation_not_read=True))
        selections[role]=item;inherited_selections[inherited_role]=inherited_item
    def selection_key(role):
        item=selections[role]
        return (not item["development_guard_pass"],numeric_key(item["development_cost_key"] if item["development_guard_pass"] else item["development_key"]),item["episodes"],role)
    selected=min(selections,key=selection_key)
    freeze_write(folder/"freeze.json",dict(selected=selected,selections=selections,inherited_selections=inherited_selections,completed_by_all_seeds=available,
        registration_sha=budget.digest(folder/"registration.json"),input_sha=reg["input_sha"],
        sources_sha=parent.a.native.digest(reg["sources"]),confirmation_not_read=True,all_three_seeds=True))
    return dict(frozen=True,selections=selections,selected=selected)


def confirm(folder,seed):
    folder=Path(folder);reg=check(folder);child=folder/f"seed{seed}";b=budget.Budget(child)
    if not(folder/"freeze.json").exists():raise ValueError("parent freeze required")
    if not budget.read(folder/"freeze.json").get("frozen_utc"):raise ValueError("parent freeze metadata incomplete")
    item=budget.read(child/"freeze.json")["selections"][f"{ARM}_{seed}"]
    path=learner_path(child,seed,item["episodes"])
    if budget.digest(path)!=item["sha256"]:raise ValueError("selected weights changed")
    model=learning.Learner.load(path,deps(reg))
    inherited_role=f"INHERITED4096_{ARM}_{seed}"
    inherited_item=budget.read(child/"freeze.json")["inherited_selections"][inherited_role]
    inherited_path=learner_path(child,seed,4096)
    if budget.digest(inherited_path)!=inherited_item["sha256"]:raise ValueError("inherited weights changed")
    inherited=learning.Learner.load(inherited_path,deps(reg))
    with b.session():
        try:evaluate(child,b,budget.read(folder/"inputs.json")["confirmation"],[f"{ARM}_{seed}",inherited_role],
                     {(ARM,seed):model,(ARM,seed,"inherited"):inherited},"confirmation")
        except budget.ControlledStop as reason:raise RuntimeError("final incomplete: "+str(reason)) from reason
        write(child/"cursor.json",dict(completed=True,stage="confirmation"))
    return dict(completed=True)


def merge(folder):
    folder=Path(folder);check(folder);children=[folder/"controls",*[folder/f"seed{s}" for s in SEEDS]]
    if not all(budget.read(child/"cursor.json")["completed"] for child in children):raise ValueError("final workers incomplete")
    rr=[r for child in children for r in rows(child,"confirmation_")]
    roles=(*BASES,*(f"{ARM}_{seed}" for seed in SEEDS),*(f"INHERITED4096_{ARM}_{seed}" for seed in SEEDS));count=176
    actual={(r["condition"],r["policy"]) for r in rr}
    expected={(case["condition"],role) for case in budget.read(folder/"inputs.json")["confirmation"] for role in roles}
    if len(rr)!=count*len(roles) or len(actual)!=len(rr) or actual!=expected:raise ValueError("final exact grid")
    used=[budget.Budget(child).used() for child in children]
    consumption=dict(environments=sum(x["environments"] for x in used),learning=sum(x["learning"] for x in used),
        failed=sum(x["failed"] for x in used),worker_active_seconds_sum=sum(x["active_seconds"] for x in used),
        workers=used,inherited_episode_history=3*4096,old_reference_copy_new_environments=0,device=0,S26=0)
    write(folder/"consumption.json",consumption);write(folder/"final_rows.json",rr)
    return dict(completed=True,rows=len(rr),consumption=consumption)


def main():
    p=argparse.ArgumentParser();p.add_argument("command",choices=("preflight","register","check","controls","baseline","train","freeze","confirm","merge"));p.add_argument("--run-root",type=Path);p.add_argument("--seed",type=int);p.add_argument("--through",type=int,default=8192);p.add_argument("--phase",choices=("development","confirmation"));x=p.parse_args()
    if x.command=="preflight":result=preflight()
    elif x.command=="register":result=register(x.run_root)
    elif x.command=="check":result=check(x.run_root)
    elif x.command=="controls":result=controls(x.run_root,x.phase)
    elif x.command=="baseline":result=baseline(x.run_root,x.seed)
    elif x.command=="train":result=train(x.run_root,x.seed,x.through)
    elif x.command=="freeze":result=select_and_freeze(x.run_root)
    elif x.command=="confirm":result=confirm(x.run_root,x.seed)
    else:result=merge(x.run_root)
    print(json.dumps(parent.serial(result),ensure_ascii=False),flush=True)


if __name__=="__main__":main()
