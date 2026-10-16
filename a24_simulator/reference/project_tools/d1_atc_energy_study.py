"""Reward13: exact reused TRAIN/DEV references, fresh paired learners, new FINAL."""
import argparse
import copy
import gzip
import json
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch

from tools import d1_atc_energy_budget as budget
from tools import d1_atc_energy_ppo as learning
from tools import d1_atc_energy_targets as labels
from tools import d1_atc_waitlink_study as parent
from tools import d1_atc_waitlong_study as previous
from tools import d1_atc_waitlong_migration as origins

ROOT = Path(__file__).resolve().parents[1]
SEEDS = (1013, 1019, 1021)
ARMS = learning.ARMS
COST_ARMS = learning.COST_ARMS
BASES = parent.BASES
CONFIRM = tuple(range(923810101, 923810109))
FINAL_RESERVE = 1800
ORIGIN12 = ROOT.parent / "ATC-WAIT1-LONGTRAIN-12"
ORIGIN12_SHA = "d72093953bc07821c417a54a265d9c14abce7ad88c5c9e2b346392c854bd6bcf"
IO_SHA = "ae1e854102e293ff4e87600a30091012888cdb5c682344515d356a5d0cd83168"
SERVICE = labels.SERVICE
NEW_FILES = tuple("tools/d1_atc_energy_" + name + ".py" for name in
                  ("ppo", "targets", "budget", "study", "orchestrator", "report")) + ("tools/test_d1_atc_energy.py",)


def write(path, value):
    budget.write(path, parent.serial(value))


def freeze_write(path, value):
    write(path, value)
    write(path, dict(value, frozen_utc=datetime.now(timezone.utc).isoformat()))


def namespace_check():
    reserved = parent.registry.collect()
    requested = set(CONFIRM)
    if requested & set(reserved["seeds"]) or any(lo <= seed <= hi for seed in requested for lo, hi in reserved["ranges"]):
        raise ValueError("registered FINAL arrival namespace collision")
    receipts = []
    for path in sorted(ROOT.parent.glob("*/inputs.json")):
        raw = path.read_bytes()
        if any(str(seed) in raw.decode("utf-8-sig") for seed in requested):
            raise ValueError("local FINAL input seed collision " + str(path))
        receipts.append(dict(path=str(path), sha256=budget.digest(path)))
    return dict(registry=reserved, local_input_receipts=receipts, confirmation=list(CONFIRM),
                train_development_explicit_reuse=True)


def origin_contract():
    path = ORIGIN12 / "registration.json"
    if budget.digest(path) != ORIGIN12_SHA:
        raise ValueError("registered12 changed")
    reg = budget.read(path)
    for name, sha in reg["sources"].items():
        if budget.digest(ROOT / name) != sha:
            raise ValueError("frozen12 source changed " + name)
    inputs = budget.read(ORIGIN12 / "inputs.json")
    if parent.a.native.digest(inputs) != reg["input_sha"]:
        raise ValueError("frozen12 input changed")
    return reg, inputs


def reference_bindings():
    """Only teacher/DEV/old4096 DEV; never12 final, freeze, latest or selection."""
    _, inputs = origin_contract()
    bindings = {}
    plans = [("teacher", ORIGIN12 / "controls", "teacher_train", "RuleATC", inputs["train"]),
             *[("rule_" + role, ORIGIN12 / "controls", "development", role, inputs["development"]) for role in BASES],
             *[("orig_" + str(seed), ORIGIN12 / f"seed{seed}", "dev4096",
                f"DROP_FLAG_WAIT1_{seed}", inputs["development"]) for seed in SEEDS]]
    for label, folder, phase, role, cases in plans:
        for case in cases:
            identity = f"{phase}_{case['condition']:02d}_{role}"
            receipt_path = folder / "rows" / (identity + ".json")
            raw_path = folder / "items" / (identity + ".json.gz")
            receipt = budget.read(receipt_path)
            if budget.digest(raw_path) != receipt["raw_sha256"]:
                raise ValueError("reused raw SHA changed " + str(raw_path))
            row = receipt["row"]
            if row["condition"] != case["condition"] or row["arrival_seed"] != case["arrival_seed"] or row["policy"] != role:
                raise ValueError("reused reference identity mismatch")
            if label == "teacher":
                raw = json.loads(gzip.decompress(raw_path.read_bytes()))
                if raw["row"] != row or row["completed"] != row["planned"] or row["completed_work_units"] != row["planned_work_units"]:
                    raise ValueError("complete teacher raw/row agreement required")
                labels.ap_suffix(raw, 35e9)  # All AP180 teacher support checked before new consumption.
            bindings[f"{label}:{case['condition']}"] = dict(receipt_path=str(receipt_path),
                receipt_sha256=budget.digest(receipt_path), raw_path=str(raw_path), raw_sha256=receipt["raw_sha256"], row=row)
    if len(bindings) != 4400:
        raise ValueError("exact4400 references required")
    return bindings


def reference_rows(folder, label):
    binding = budget.read(Path(folder) / "references.json")
    return [item["row"] for key, item in binding.items() if key.startswith(label + ":")]


def read_reference(folder, label, case, bindings=None):
    bindings = budget.read(Path(folder) / "references.json") if bindings is None else bindings
    item = bindings[f"{label}:{case['condition']}"]
    if budget.digest(item["raw_path"]) != item["raw_sha256"] or budget.digest(item["receipt_path"]) != item["receipt_sha256"]:
        raise ValueError("reused reference changed")
    raw = json.loads(gzip.decompress(Path(item["raw_path"]).read_bytes()))
    if raw["row"] != item["row"]:
        raise ValueError("reused row/raw mismatch")
    return raw


def source_bindings(origin):
    names = set(origin["sources"]) | set(NEW_FILES)
    return {name: budget.digest(ROOT / name) for name in sorted(names)}


def deps(reg, reward_arm, seed):
    return dict(schema=parent.a.SCHEMA, arm=learning.COUPLING, reward_arm=reward_arm,
                sequencing="ATC", objective=learning.OBJECTIVES[reward_arm],
                multipliers=learning.MULTIPLIERS[reward_arm], seed=seed,
                sources=reg["sources"], input_sha=reg["input_sha"])


def paired_initial_proof(reg):
    receipt = {}
    for seed in SEEDS:
        learners = {arm: learning.Learner(seed, deps(reg, arm, seed)) for arm in ARMS}
        components = {arm: {key: parent.payload_digest(value) for key, value in model.snapshot().items()
                           if key in ("network", "optimizer", "action_rng", "shuffle_rng", "pending", "logs")}
                      for arm, model in learners.items()}
        if any(item != components["CONTROL"] for item in components.values()):
            raise ValueError("same-seed fresh initialization mismatch")
        if any(model.optimizer.state or model.episodes or model.steps or model.pending for model in learners.values()):
            raise ValueError("fresh initialization inherited optimizer/history")
        receipt[str(seed)] = dict(components=components, same_network_Adam_action_shuffle_RNG=True,
                                 episodes=0, native_updates=0, Adam_steps=0, inherited_weights=False)
    return receipt


def preflight():
    old, inputs = origin_contract()
    refs = reference_bindings()
    oldreg, models = origins.read_origins(ROOT.parent / "ATC-WAITLINK-EXPAND-11")
    proposed = dict(sources=source_bindings(old), input_sha=parent.a.native.digest(dict(
        train=inputs["train"], development=inputs["development"], confirmation=parent.cases(CONFIRM))))
    return dict(status="PASS_fresh_reward_preflight", namespace=namespace_check(), references=len(refs),
                references_sha=parent.a.native.digest(refs), origins={str(seed): item["sha256"] for seed, item in models.items()},
                paired_initialization=paired_initial_proof(proposed), new_environments=0, new_learning=0,
                original_objective=oldreg["objectives"][learning.COUPLING])


def learner_path(folder, arm, seed, episode=None):
    return Path(folder) / f"seed{seed}" / "checkpoints" / f"{arm}_{seed}_{'latest' if episode is None else 'ep'+str(episode)}.pt"


def register(folder, hours=6):
    folder = Path(folder)
    if folder.exists():
        raise FileExistsError("never reset a registered/consumed run")
    if hours != 6:
        raise ValueError("immutable six-hour wall budget")
    old, source_inputs = origin_contract()
    namespace = namespace_check()
    refs = reference_bindings()
    oldreg, models = origins.read_origins(ROOT.parent / "ATC-WAITLINK-EXPAND-11")
    io = budget.read(ROOT.parent / "ATC-WAITLINK-EXPAND-11" / "io_transport_binding.json")["supplement"]
    if io["sha256"] != IO_SHA or budget.digest(io["path"]) != IO_SHA:
        raise ValueError("same IO supplement required")
    inputs = dict(train=source_inputs["train"], development=source_inputs["development"], confirmation=parent.cases(CONFIRM))
    began = time.time()
    reg = dict(task=budget.TASK, head=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        schema=parent.a.SCHEMA, coupling=learning.COUPLING, reward_arms=ARMS, seeds=SEEDS, state=226, action=57, padding=32,
        objectives=learning.OBJECTIVES, multipliers=learning.MULTIPLIERS, sources=source_bindings(old),
        input_sha=parent.a.native.digest(inputs), source12_registration_sha=ORIGIN12_SHA, source12_input_sha=old["input_sha"],
        reference_sha=parent.a.native.digest(refs), references=4400, origins={str(seed):dict(path=str(item["path"]),
        sha256=item["sha256"], episodes=4096) for seed, item in models.items()},
        origin_registration_path=str(ROOT.parent / "ATC-WAITLINK-EXPAND-11" / "registration.json"),
        origin_registration_sha=budget.digest(ROOT.parent / "ATC-WAITLINK-EXPAND-11" / "registration.json"),
        started_unix=began, deadline_unix=began + hours * 3600, wall_hours=hours, final_reserve_seconds=FINAL_RESERVE,
        numerical_episode_environment_cap=None, milestones="fresh512 then powers2; common12 completed stages only",
        workers=1, scheduling="seed1013/1019/1021 sequential; CONTROL/ECO5/GATED_ECO5/GATED_ECO5_AP180 round-robin within seed",
        reward_gate="postepisode RuleATC full completion/units+declared/originalU/N+P95 nondegradation; failed gate clips only negativeE/AP suffix cost to0",
        contract="frozen12 226x57x32/DROP52/K8/max29/currentATCrankgap/actualAVAILABLE/nonpreemptive/CG_DC<=2/requiredresourceWAIT; EFT0 and nofuturequeueforecast",
        selection="primary percondition service/P95 vs RuleATC AND same-seed original4096; eligible meanJ/AP/P95/earlystage; noCP0 selection; noneeligible fails; all12 models reported",
        stop_rule="all3costarms each damage increases in2consecutive transitions at>=2seeds OR costarms9 besteligible/risk key all stagnant and no guarded same-stageCONTROL gain>=.005J OR .005C AP over3additionalstages; guard is service/P95/J/AP percondition vsRuleATC+orig4096+CONTROL; first512 excluded; wall/disk boundary stop",
        AP_target_windows=dict(CONTROL=120, ECO5=120, GATED_ECO5=120, GATED_ECO5_AP180=180),
        AP_evaluation_window="35..180 seconds frozen model plant", E_window="120 seconds", weight5_gradient5_guarantee=False,
        final_roles=21, final_environments=3696, reused_references_new_environments=0, oldweights_evaluation_only=True,
        shared_host_timing=True, io_supplement=io, automatic_adoption=False, experiment_ready=False,
        device=0, APK=0, S26=0, fit=0, NPU=0, cooling=0, external_transfer=0)
    proof = paired_initial_proof(reg)
    protocol = ROOT / "docs" / "ATC_ENERGY_GUARD_STUDY_20261012.md"
    if not protocol.exists():
        raise ValueError("reviewed protocol must exist before registration")
    folder.mkdir(parents=True)
    shutil.copy2(protocol, folder / "PROTOCOL_REGISTERED.md")
    reg["protocol_sha256"] = budget.digest(folder / "PROTOCOL_REGISTERED.md")
    write(folder / "registration.json", reg); write(folder / "inputs.json", inputs)
    write(folder / "namespace_receipt.json", namespace); write(folder / "references.json", refs)
    write(folder / "fresh_initialization.json", proof)
    for name, sha in reg["sources"].items():
        target = folder / "REGISTERED_SOURCE_TREE" / name; target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, target)
        if budget.digest(target) != sha:
            raise ValueError("registered source archive mismatch")
    budget.Budget.register(folder / "worker", dict(parent_sha=budget.digest(folder / "registration.json"),
                          deadline_unix=reg["deadline_unix"], final_reserve_seconds=FINAL_RESERVE))
    for seed in SEEDS:
        for arm in ARMS:
            model = learning.Learner(seed, deps(reg, arm, seed))
            model.save(learner_path(folder, arm, seed, 0)); model.save(learner_path(folder, arm, seed))
    write(folder / "orchestration.json", dict(status="registered", phase="not_started", new_environments=0, new_learning=0))
    return dict(registered=True, deadline_unix=reg["deadline_unix"], references_reused=4400, new_environments=0, new_learning=0)


def check(folder):
    folder = Path(folder); reg = budget.read(folder / "registration.json")
    if (reg["task"] != budget.TASK or reg["reward_arms"] != list(ARMS) or reg["objectives"] != learning.OBJECTIVES or
        reg["multipliers"] != learning.MULTIPLIERS or reg["workers"] != 1):
        raise ValueError("registered reward contract changed")
    origin_contract()
    for name, sha in reg["sources"].items():
        if budget.digest(ROOT / name) != sha:
            raise ValueError("registered source changed " + name)
    if parent.a.native.digest(budget.read(folder / "inputs.json")) != reg["input_sha"]:
        raise ValueError("registered input changed")
    if parent.a.native.digest(budget.read(folder / "references.json")) != reg["reference_sha"]:
        raise ValueError("reference binding changed")
    if budget.digest(folder / "PROTOCOL_REGISTERED.md") != reg["protocol_sha256"]:
        raise ValueError("protocol changed")
    if budget.digest(reg["io_supplement"]["path"]) != IO_SHA:
        raise ValueError("IO supplement changed")
    if budget.digest(reg["origin_registration_path"]) != reg["origin_registration_sha"]:
        raise ValueError("old11 registration changed")
    for item in reg["origins"].values():
        if budget.digest(item["path"]) != item["sha256"]:
            raise ValueError("old11 terminal PT changed")
    return reg


def rows(folder, prefix):
    return parent.rows(Path(folder) / "worker", prefix)


def evaluate(folder, b, cases, roles, models, phase):
    worker = Path(folder) / "worker"; frozen, init, _ = parent.a.hybrid.load()
    for case in cases:
        for role in roles:
            identity = f"{phase}_{case['condition']:02d}_{role}"; receipt = worker / "rows" / (identity + ".json")
            if receipt.exists():
                if budget.digest(worker / "items" / (identity + ".json.gz")) != budget.read(receipt)["raw_sha256"]:
                    raise ValueError("saved evaluation raw changed")
                continue
            agent = parent.controller(role, frozen, init["initial"], {}) if role in BASES else models[role].controller(frozen, init["initial"], True)
            raw = parent.collect(b, worker, identity, phase, dict(case, role=role), agent)
            if role not in BASES and raw["row"]["fallbacks"]:
                raise ValueError("learned evaluation fallback; preserve consumed raw")
    return rows(folder, phase + "_")


def atomic_learner_save(model, path, folder):
    began = time.perf_counter(); model.save(path)
    with (Path(folder) / "checkpoint_io.jsonl").open("a", encoding="utf8") as stream:
        stream.write(json.dumps(dict(reward_arm=model.reward_arm, seed=model.seed, episodes=model.episodes,
            bytes=Path(path).stat().st_size, seconds=time.perf_counter() - began)) + "\n")


def stage_path(folder, seed, episode):
    return Path(folder) / f"seed{seed}" / f"stage{episode}.json"


def completed_stages(folder):
    sets = [{int(path.stem[5:]) for path in (Path(folder) / f"seed{seed}").glob("stage*.json")} for seed in SEEDS]
    return sorted(set.intersection(*sets)) if all(sets) else []


def assess(candidate, rule, original):
    return previous.assess(candidate, rule, original)


def stage_receipt(folder, seed, episode):
    reg = check(folder); allrows = rows(folder, f"dev{episode}_")
    rule, original = reference_rows(folder, "rule_RuleATC"), reference_rows(folder, f"orig_{seed}")
    result = {}
    control = [row for row in allrows if row["policy"] == f"CONTROL_{seed}"]
    for arm in ARMS:
        role = f"{arm}_{seed}"; candidate = [row for row in allrows if row["policy"] == role]
        if len(candidate) != 176:
            raise ValueError("complete reward-arm development required")
        model = learning.Learner.load(learner_path(folder, arm, seed, episode), deps(reg, arm, seed))
        mechanics = (model.episodes == episode and len(model.logs) == episode // 8 and not model.pending and
            any(log["sampled_choices"] > 0 for log in model.logs) and
            all(np.isfinite(log["actor_gradient_max"]) and (log["critic_only"] or log["actor_gradient_max"] > 0) for log in model.logs) and
            all(torch.isfinite(value).all() for value in model.network.state_dict().values()) and
            all(torch.isfinite(value["exp_avg"]).all() and torch.isfinite(value["exp_avg_sq"]).all()
                for value in model.optimizer.state_dict()["state"].values()))
        if not mechanics:
            raise ValueError("fresh native learning mechanics failed")
        item = assess(candidate, rule, original)
        control_assessment = assess(candidate, rule, control)
        bycontrol = {row["condition"]: row for row in control}
        byoriginal = {row["condition"]: row for row in original}
        primary = parent.primary(candidate)
        gain_AP_control = float(np.mean([bycontrol[row["condition"]]["peak_ap_c"] - row["peak_ap_c"] for row in primary])) if all(row["peak_ap_c"] is not None and bycontrol[row["condition"]]["peak_ap_c"] is not None for row in primary) else None
        gain_AP_original = float(np.mean([byoriginal[row["condition"]]["peak_ap_c"] - row["peak_ap_c"] for row in primary])) if all(row["peak_ap_c"] is not None and byoriginal[row["condition"]]["peak_ap_c"] is not None for row in primary) else None
        guarded_control_gain = (item["conditionwise_nondegrading_cost"] and control_assessment["conditionwise_nondegrading_cost"] and
            ((control_assessment["mean_J_gain_vs_inherited"] is not None and control_assessment["mean_J_gain_vs_inherited"] >= .005) or
             (gain_AP_control is not None and gain_AP_control >= .005)))
        item.update(mean_J_gain_vs_same_stage_CONTROL=control_assessment["mean_J_gain_vs_inherited"],
            mean_AP_gain_vs_same_stage_CONTROL=gain_AP_control, mean_AP_gain_vs_original4096=gain_AP_original,
            same_stage_CONTROL_damage_conditions=control_assessment["inherited_damage_conditions"],
            same_stage_CONTROL_conditionwise_nondegrading_cost=control_assessment["conditionwise_nondegrading_cost"],
            original4096_meaningful_J_gain=item["meaningful_cost_gain"], meaningful_cost_gain=bool(guarded_control_gain))
        item.update(episode=episode, new_episodes=episode, model_sha=budget.digest(learner_path(folder, arm, seed, episode)),
            native_updates=len(model.logs), Adam_steps=model.steps, new_native_updates=len(model.logs), new_Adam_steps=model.steps,
            new_actor_updates=sum(log["actor_changed"] for log in model.logs), new_critic_only_updates=sum(log["critic_only"] for log in model.logs),
            new_sampled_choices=sum(log["sampled_choices"] for log in model.logs), fresh_mechanics_pass=bool(mechanics),
            gate_failed_episodes=sum(not row.get("energy_gate", True) for row in model.episode_logs), exact_pending0=True)
        result[arm] = item
    write(stage_path(folder, seed, episode), result)
    return result


def train(folder, seed, through, stop_after=None):
    if seed not in SEEDS or through < 512 or through & (through - 1):
        raise ValueError("fresh power2 milestone >=512 and registered seed")
    folder = Path(folder); reg = check(folder)
    if (folder / "freeze.json").exists():
        raise ValueError("never train after final freeze")
    worker = folder / "worker"; b = budget.Budget(worker)
    models = {arm: learning.Learner.load(learner_path(folder, arm, seed), deps(reg, arm, seed)) for arm in ARMS}
    if any(len(model.pending) >= 8 for model in models.values()):
        raise ValueError("failed native update requires explicit audit")
    inputs = budget.read(folder / "inputs.json"); frozen, init, _ = parent.a.hybrid.load(); accepted = 0
    references = budget.read(folder / "references.json")
    with b.session():
        try:
            for index in range(through):
                for arm, model in models.items():
                    if model.episodes > index:
                        continue
                    if model.episodes != index:
                        raise ValueError("round-robin reward cursor mismatch")
                    ready, reason = b.can_begin("train")
                    if not ready:
                        raise budget.ControlledStop(reason)
                    case = inputs["train"][index % len(inputs["train"])]
                    identity = f"train_{arm}_{seed}_{index:06d}"
                    if (worker / "rows" / (identity + ".json")).exists():
                        raise ValueError("unadopted consumed rollout; explicit audit required")
                    agent = model.controller(frozen, init["initial"], False)
                    raw = parent.collect(b, worker, identity, "train", dict(case, role=f"{arm}_{seed}"), agent, True)
                    if raw["row"]["fallbacks"]:
                        raise ValueError("training fallback; preserve rollout")
                    reference = read_reference(folder, "teacher", case, references)
                    frames, costs, valid, _ = learning.targets(agent, raw, init["initial"]["preload_power_w"] * 120, arm, reference)
                    model.add(frames, costs, valid, raw["row"], agent)
                    model.episode_logs[-1]["energy_gate"] = labels.service_gate(raw, reference)
                    model.episode_logs[-1]["energy_label_receipt"] = copy.deepcopy(agent.energy_label_receipt)
                    model.cursor = dict(episode=model.episodes, reward_arm=arm, seed=seed)
                    model.consumption = b.used()
                    atomic_learner_save(model, learner_path(folder, arm, seed), folder)
                    accepted += 1
                    write(worker / "cursor.json", dict(stage="train", seed=seed, through=through,
                          episodes={key: value.episodes for key, value in models.items()}, learning_accepted=b.used()["learning"]))
                    if stop_after is not None and accepted >= stop_after:
                        raise budget.ControlledStop("test_partial_boundary_stop")
                if (index + 1) % 32 == 0:
                    print(json.dumps(dict(seed=seed, episodes=index+1, reward_arms=4)), flush=True)
            for arm, model in models.items():
                if model.pending:
                    raise ValueError("milestone pending batch")
                atomic_learner_save(model, learner_path(folder, arm, seed, through), folder)
            evaluate(folder, b, inputs["development"], [f"{arm}_{seed}" for arm in ARMS],
                     {f"{arm}_{seed}": model for arm, model in models.items()}, f"dev{through}")
        except budget.ControlledStop as reason:
            saved = {arm: dict(episodes=model.episodes, pending=len(model.pending),
                     sha256=budget.digest(learner_path(folder, arm, seed))) for arm, model in models.items()}
            write(folder / f"seed{seed}" / "boundary_stop.json", dict(reason=str(reason), models=saved, consumption=b.used()))
            return dict(stopped=True, reason=str(reason), models=saved)
        except BaseException as error:
            errors = {}
            for arm, model in models.items():
                try:
                    atomic_learner_save(model, learner_path(folder, arm, seed), folder)
                except BaseException as secondary:
                    errors[arm] = repr(secondary)
            write(folder / f"seed{seed}" / "failure_receipt.json", dict(error=repr(error), checkpoint_errors=errors,
                  models={arm: dict(episodes=model.episodes, pending=len(model.pending)) for arm, model in models.items()}, consumption=b.used()))
            raise
    return dict(completed=True, seed=seed, stage=through, receipt=stage_receipt(folder, seed, through))


def audit_partial59(folder, seed):
    """Saved-only actual59 boundary proof; originals and live RNG states unmodified."""
    folder = Path(folder); reg = check(folder); snapshots = {}
    for arm in ARMS:
        path = learner_path(folder, arm, seed); sha = budget.digest(path)
        model = learning.Learner.load(path, deps(reg, arm, seed)); snapshot = model.snapshot()
        restored = learning.Learner.from_snapshot(snapshot, deps(reg, arm, seed))
        if parent.payload_digest(snapshot) != parent.payload_digest(restored.snapshot()):
            raise ValueError("partial learner full restore mismatch")
        action = torch.Generator(); action.set_state(snapshot["action_rng"].clone())
        shuffle = torch.Generator(); shuffle.set_state(snapshot["shuffle_rng"].clone())
        if not torch.equal(torch.rand(5, generator=action), torch.rand(5, generator=restored.action_rng)) or not torch.equal(torch.randperm(17, generator=shuffle), torch.randperm(17, generator=restored.shuffle_rng)):
            raise ValueError("partial learner next action/shuffle RNG mismatch")
        if model.episodes != len(model.episode_logs) or len(model.pending) != model.episodes % 8 or len(model.logs) != model.episodes // 8:
            raise ValueError("partial learner history/pending mechanics")
        if not all(np.isfinite(log["actor_gradient_max"]) and (log["critic_only"] or log["actor_gradient_max"] > 0) for log in model.logs):
            raise ValueError("partial native gradient mechanics")
        archive = folder / "partial59_checkpoints" / path.name
        archive.parent.mkdir(exist_ok=True)
        if archive.exists() and budget.digest(archive) != sha:
            raise ValueError("never overwrite a different partial proof")
        if not archive.exists():
            shutil.copy2(path, archive)
        if budget.digest(path) != sha or budget.digest(archive) != sha:
            raise ValueError("partial proof file changed")
        snapshots[arm] = dict(episodes=model.episodes, pending=len(model.pending), native_updates=len(model.logs),
                             Adam_steps=model.steps, sha256=sha, full_restore_exact=True, next_RNG_exact=True)
    used = budget.Budget(folder / "worker").used()
    if sum(item["episodes"] for item in snapshots.values()) != 59 or used["learning"] != 59 or used["environments"] != 59 or used["failed"]:
        raise ValueError("actual59 partial proof requires exactly59 starts and no environment failures")
    receipt = dict(status="PASS_actual59_partial_restore", seed=seed, models=snapshots,
                   actual_learning_starts=59, actual_environment_starts=59, audit_new_environments=0, audit_new_learning=0)
    write(folder / "partial59_audit.json", receipt)
    return receipt


def continuation_stop(histories):
    if len(histories) != 12 or len({len(value) for value in histories.values()}) != 1:
        raise ValueError("stop requires12 common completed-stage histories")
    n = len(next(iter(histories.values())))
    if n >= 3:
        arm_damage = []
        for arm in COST_ARMS:
            damage = sum(histories[f"{arm}_{seed}"][-3]["damage_conditions"] < histories[f"{arm}_{seed}"][-2]["damage_conditions"] < histories[f"{arm}_{seed}"][-1]["damage_conditions"] for seed in SEEDS)
            arm_damage.append(damage >= 2)
        if all(arm_damage):
            return "all3costarms_two_transition_damage_at_two_seeds"
    cost_histories = [histories[f"{arm}_{seed}"] for arm in COST_ARMS for seed in SEEDS]
    if n >= 4 and all(expansion_best_keys(history) == expansion_best_keys(history[:-3]) and
                     not any(item["meaningful_cost_gain"] for item in history[-3:]) for history in cost_histories):
        return "three_additional_stage_stagnation_all3costarms9seeds"
    return None


def expansion_best_keys(history):
    # A service/risk improvement prevents stagnation even while the eligible
    # energy-preferred model stays fixed. Selection itself still uses eligible costs.
    return previous.best_key(history), min(previous.numeric_key(item["risk_key"]) for item in history)


def continuation_receipt(histories):
    n = len(next(iter(histories.values())))
    damage = {arm: {str(seed): bool(n >= 3 and histories[f"{arm}_{seed}"][-3]["damage_conditions"] <
               histories[f"{arm}_{seed}"][-2]["damage_conditions"] < histories[f"{arm}_{seed}"][-1]["damage_conditions"])
               for seed in SEEDS} for arm in COST_ARMS}
    stagnant = {f"{arm}_{seed}": bool(n >= 4 and expansion_best_keys(histories[f"{arm}_{seed}"]) ==
                expansion_best_keys(histories[f"{arm}_{seed}"][:-3]) and not any(item["meaningful_cost_gain"]
                for item in histories[f"{arm}_{seed}"][-3:])) for arm in COST_ARMS for seed in SEEDS}
    return dict(stop=continuation_stop(histories), common_stages=n, initial512_excluded_from_additional_stages=True,
                damage_increases=damage, per_arm_at_least2seed_damage={arm: sum(values.values()) >= 2 for arm, values in damage.items()},
                three_additional_stage_stagnation_by_cost_arm_seed=stagnant,
                meaningful_gain_reference="same-seed CONTROL at same stage, J>=.005 or AP>=.005; conditionwise service/P95/J/AP vsRuleATC+orig4096+CONTROL")


def histories(folder, stages):
    return {f"{arm}_{seed}": [budget.read(stage_path(folder, seed, episode))[arm] for episode in stages] for seed in SEEDS for arm in ARMS}


def select_and_freeze(folder):
    folder = Path(folder); reg = check(folder); stages = completed_stages(folder)
    if not stages or stages[0] != 512:
        raise ValueError("all12 completed trained512 required; CP0 selection forbidden")
    if (folder / "freeze.json").exists() or any((folder / "worker" / "rows").glob("confirmation_*.json")):
        raise ValueError("freeze once before FINAL")
    selections = {}
    for role, history in histories(folder, stages).items():
        eligible = [item for item in history if item["eligible_guard"]]
        chosen = min(eligible or history, key=lambda item: (previous.numeric_key(item["cost_key"] if eligible else item["risk_key"]), item["episode"]))
        arm, seed_text = role.rsplit("_", 1); seed = int(seed_text); episode = chosen["episode"]
        path = learner_path(folder, arm, seed, episode)
        if budget.digest(path) != chosen["model_sha"]:
            raise ValueError("completed checkpoint changed")
        selections[role] = dict(episodes=episode, sha256=chosen["model_sha"], development_guard_pass=bool(eligible),
            eligible_checkpoints=[item["episode"] for item in eligible], failed_checkpoint=not bool(eligible),
            development_key=chosen["risk_key"], development_cost_key=chosen["cost_key"])
    old = {f"ORIGINAL4096_{seed}": dict(reg["origins"][str(seed)], new_learning=0, evaluation_only=True) for seed in SEEDS}
    freeze_write(folder / "freeze.json", dict(selections=selections, original_selections=old, completed_by_all12=stages,
        registration_sha=budget.digest(folder / "registration.json"), input_sha=reg["input_sha"],
        sources_sha=parent.a.native.digest(reg["sources"]), confirmation_not_read=True, all12_reported=True))
    return dict(frozen=True, selections=selections)


def confirm(folder):
    folder = Path(folder); reg = check(folder); freeze = budget.read(folder / "freeze.json")
    if not freeze.get("frozen_utc"):
        raise ValueError("complete before-FINAL freeze required")
    models = {}
    for role, item in freeze["selections"].items():
        arm, seed_text = role.rsplit("_", 1); seed = int(seed_text); path = learner_path(folder, arm, seed, item["episodes"])
        if budget.digest(path) != item["sha256"]:
            raise ValueError("selected PT changed")
        models[role] = learning.Learner.load(path, deps(reg, arm, seed))
        # Deterministic evaluation retains only inference state in RAM.
        models[role].logs = []; models[role].episode_logs = []; models[role].pending = []
        models[role].last_controller = None
    oldreg = budget.read(reg["origin_registration_path"])
    for role, item in freeze["original_selections"].items():
        if budget.digest(item["path"]) != item["sha256"]:
            raise ValueError("old fixed PT changed")
        models[role] = origins.learning.Learner.load(item["path"], parent.deps(oldreg, learning.COUPLING))
        models[role].logs = []; models[role].episode_logs = []; models[role].pending = []
        models[role].last_controller = None
    b = budget.Budget(folder / "worker")
    with b.session():
        try:
            rr = evaluate(folder, b, budget.read(folder / "inputs.json")["confirmation"],
                          [*BASES, *freeze["selections"], *freeze["original_selections"]], models, "confirmation")
        except budget.ControlledStop as reason:
            write(folder / "final_incomplete.json", dict(reason=str(reason), consumption=b.used()))
            raise RuntimeError("FINAL incomplete; preserve consumed rows") from reason
        write(folder / "worker" / "cursor.json", dict(completed=True, stage="confirmation", rows=len(rr)))
    return dict(completed=True, rows=len(rr))


def merge(folder):
    folder = Path(folder); check(folder); freeze = budget.read(folder / "freeze.json"); rr = rows(folder, "confirmation_")
    roles = [*BASES, *freeze["selections"], *freeze["original_selections"]]
    expected = {(case["condition"], role) for case in budget.read(folder / "inputs.json")["confirmation"] for role in roles}
    if len(rr) != 3696 or len({(row["condition"], row["policy"]) for row in rr}) != len(rr) or {(row["condition"], row["policy"]) for row in rr} != expected:
        raise ValueError("exact FINAL176x21 required")
    cons = budget.Budget(folder / "worker").used()
    cons.update(reused_reference_rows=4400, reused_reference_new_environments=0, inherited_learning=0, fresh_models=12)
    write(folder / "consumption.json", cons); write(folder / "final_rows.json", rr)
    return dict(completed=True, rows=len(rr), consumption=cons)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("preflight", "register", "check", "train", "audit-partial59", "freeze", "confirm", "merge"))
    parser.add_argument("--run-root", type=Path); parser.add_argument("--seed", type=int)
    parser.add_argument("--through", type=int, default=512); parser.add_argument("--stop-after", type=int)
    args = parser.parse_args()
    if args.command == "preflight": result = preflight()
    elif args.command == "register": result = register(args.run_root)
    elif args.command == "check": result = check(args.run_root)
    elif args.command == "train": result = train(args.run_root, args.seed, args.through, args.stop_after)
    elif args.command == "audit-partial59": result = audit_partial59(args.run_root, args.seed)
    elif args.command == "freeze": result = select_and_freeze(args.run_root)
    elif args.command == "confirm": result = confirm(args.run_root)
    else: result = merge(args.run_root)
    print(json.dumps(parent.serial(result), ensure_ascii=False, allow_nan=False), flush=True)


if __name__ == "__main__":
    main()
