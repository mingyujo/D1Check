"""Frozen-model parallel A24 service envelope comparison, no training/device work."""
import argparse
import gzip
import json
import random
import subprocess
import time
from pathlib import Path
import torch
from tools import d1_atc_repair_study as previous
from tools import d1_atc_repair_policy as a
from tools import d1_atc_repair_mobile as historical
from tools import d1_atc_repair_ppo as learning
from tools import d1_service_equal_mobile as ready
from tools import d1_service_equal_budget as budget

ROOT = previous.ROOT
TASK = "SERVICE-EQUAL-COMPARE-06"
ROLES = ("FIFO_FIXED", "FIFO_EFT", "FIFO_READY", "FIFO_READY_EFT", "RuleEDD", "RuleATC",
         "ANCHOR_211", "CAUSAL_211", "LEGACY_101")
SEEDS = (887310101, 887310102, 887310103, 887310104)
REALIZATION = 887000201
REPAIR = ROOT.parent / "ATC-RESIDUAL-REPAIR-05"


def workload(family, level, seed):
    rng = random.Random(previous.keyed(seed, family, level, "arrivals"))
    times = []
    if family == "low":
        times = [(35+i*(1.5-.15*level), i % 2) for i in range(24)]
    elif family == "variable":
        now = 35.
        for i in range(48):
            times.append((now, i % 2))
            now += rng.uniform(.75, 1.05-.04*level)
    elif family == "paired":
        # D first, then C: same time or 0.50s later, by predeclared level.
        group = (1.2, 1.15, 1.2, 1.15)[level]
        tail = (0., 0., .50, .50)[level]
        times = [(35+i*group+offset, kind) for i in range(24) for offset, kind in ((0., 1), (tail, 0))]
    elif family == "sustained":
        gap = .7+.05*level
        times = [(35+i*gap, i % 2) for i in range(96)]
    else:
        raise ValueError("unknown preregistered family")
    qs = []
    for i, (at, kind) in enumerate(times):
        qs.append(dict(id=f"S06_{i:03d}", ordinal=i, task="classification" if kind == 0 else "detection",
                       priority="urgent" if kind == 0 else "normal", arrival_ns=round(at*1e9),
                       deadline_offset_ns=round((1.5 if kind == 0 else 6.)*1e9), work_units=1))
    if any(q["arrival_ns"] >= 119e9 for q in qs):
        raise ValueError("common 120s window exceeded")
    return qs


def cases():
    out = []
    for seed in SEEDS:
        for family in ("low", "variable", "paired", "sustained"):
            for level in range(4):
                out.append(dict(condition=len(out), arrival_seed=seed, family=family, factor=f"level_{level}",
                                level=level, context="n1_actual_donor_original_deadlines_service_envelope",
                                requests=workload(family, level, seed)))
    return out


def check(folder):
    reg = budget.read(folder / "registration.json")
    for name, sha in reg["sources"].items():
        if budget.digest(ROOT / name) != sha:
            raise ValueError("registered source changed: " + name)
    if a.native.digest(budget.read(folder / "inputs.json")) != reg["input_sha"]:
        raise ValueError("immutable input changed")
    for m in reg["models"].values():
        if budget.digest(m["path"]) != m["sha256"]:
            raise ValueError("frozen model changed")
    return reg


def register(folder):
    if folder.exists():
        raise FileExistsError("never reset experiment")
    previous.check(REPAIR)
    old = previous.budget.read(REPAIR / "freeze.json")
    inputs = cases()
    reserved = previous.registry.collect()
    new = set(SEEDS + (REALIZATION,))
    if new & set(reserved["seeds"]) or any(lo <= s <= hi for s in new for lo, hi in reserved["ranges"]):
        raise ValueError("seed collision")
    for path in folder.parent.glob("*/inputs.json"):
        text = path.read_text("utf-8")
        if any(str(s) in text for s in new):
            raise ValueError("local input seed collision")
    models = {}
    for role in ("ANCHOR_211", "CAUSAL_211"):
        arm, seed = role.split("_")
        meta = old["selections"][role]
        path = previous.learner_path(REPAIR, arm, int(seed), meta["episodes"])
        models[role] = dict(path=path.resolve().as_posix(), sha256=meta["sha256"], episodes=meta["episodes"],
                            learned_gain_demonstrated=meta["learned_gain_demonstrated"])
    models["LEGACY_101"] = previous.budget.read(REPAIR / "registration.json")["legacy_models"]["LEGACY_101"]
    if any(budget.digest(m["path"]) != m["sha256"] for m in models.values()):
        raise ValueError("weights not fixed")
    folder.mkdir(parents=True)
    sources = previous.sources()
    for path in (Path(__file__), ROOT / "tools/d1_service_equal_mobile.py", ROOT / "tools/d1_service_equal_budget.py", ROOT / "tools/test_d1_service_equal.py"):
        sources[path.relative_to(ROOT).as_posix()] = budget.digest(path)
    reg = dict(task=TASK, head=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
               sources=sources, input_sha=a.native.digest(inputs), models=models, roles=ROLES,
               seeds=SEEDS, realization=REALIZATION, schema=a.SCHEMA, workers=4,
               aggregate_cap=600, child_environment_cap=150, planned_environments=576, learning=0,
               scheduling="event-based online rolling rejudgment; no future horizon optimization",
               study="same n1 measured bootstrap, original U1.5/N6, 120s horizon/cooling180; 64 common inputs, all rows kept",
               new_control="FIFO_READY_EFT oldest current legal request then minimum available-route occupancy; old FIFO/EFT untouched",
               service_set="all nine policies complete every request and U/N requested/original misses zero in SAME condition; intersection reported, not hidden exclusion",
               adoption="original strict completion/service/P95/J/AP epsilon0 and paired percondition protection retained; service equivalence alone not adoption",
               parallel="4 disjoint reserved shards of16cases*9roles; immutable inputs/weights/sources; 150*4=600 aggregate cap",
               timing="shared PC wall time/worker CPU time; concurrent host load, not phone timing or energy",
               old_stress="05 full 64 and old batch/tighter failures preserved, no old verdict reclassified",
               device=0, S26=0, fit=0, NPU=0, experiment_ready=False, automatic_adoption=False)
    budget.write(folder / "registration.json", reg)
    budget.write(folder / "inputs.json", inputs)
    for shard in range(4):
        child = folder / f"shard{shard}"
        budget.Budget.register(child, dict(parent=TASK, parent_sha256=budget.digest(folder / "registration.json"),
                                         cases=list(range(shard*16, (shard+1)*16)), reserved_environments=144))
        budget.write(child / "cursor.json", dict(completed=False))
    return dict(task=TASK, registered=True, environments=576, aggregate_cap=600, learning=0)


def run(folder, shard):
    if not 0 <= shard < 4:
        raise ValueError("unknown shard")
    reg = check(folder)
    # Isolated process only: same function, separate preregistered realization namespace.
    previous.REALIZATION = REALIZATION
    child = folder / f"shard{shard}"
    b = budget.Budget(child)
    if budget.read(child / "cursor.json")["completed"]:
        return dict(status="already_completed", shard=shard, consumption=b.used())
    fixed = {}
    repairreg = previous.budget.read(REPAIR / "registration.json")
    for role in ("ANCHOR_211", "CAUSAL_211"):
        arm, seed = role.split("_")
        fixed[arm, int(seed)] = learning.Learner.load(Path(reg["models"][role]["path"]), previous.deps(repairreg, arm))
    legacy = {}
    net = previous.legacy_learning.ActorCritic()
    net.load_state_dict(torch.load(reg["models"]["LEGACY_101"]["path"], map_location="cpu", weights_only=False)["network"])
    net.eval()
    legacy["LEGACY_101"] = net
    f, init, _ = a.hybrid.load()
    start = time.perf_counter()
    with b.session():
        for case in budget.read(folder / "inputs.json")[shard*16:(shard+1)*16]:
            for role in ROLES:
                identity = f"comparison_{case['condition']:02d}_{role}"
                path = child / "rows" / (identity + ".json")
                if path.exists():
                    receipt = budget.read(path)
                    if budget.digest(child / "items" / (identity + ".json.gz")) != receipt["raw_sha256"]:
                        raise ValueError("saved raw changed")
                    continue
                agent = ready.Controller(f, init["initial"]) if role == ready.ROLE else previous.controller(role, f, init["initial"], fixed, legacy)
                previous.collect(b, child, identity, "comparison", dict(case, role=role), agent)
        budget.write(child / "cursor.json", dict(completed=True, rows=144, shard=shard))
    return dict(status="completed", shard=shard, elapsed_seconds=time.perf_counter()-start, consumption=b.used())


def merge(folder):
    reg = check(folder)
    rows, counts = [], []
    for shard in range(4):
        child = folder / f"shard{shard}"
        if not budget.read(child / "cursor.json")["completed"]:
            raise ValueError("incomplete shard")
        counts.append(budget.Budget(child).used())
        for path in sorted((child / "rows").glob("*.json")):
            receipt = budget.read(path)
            if budget.digest(child / "items" / (path.stem + ".json.gz")) != receipt["raw_sha256"]:
                raise ValueError("raw matrix changed")
            rows.append(receipt["row"])
    expected = {(i, role) for i in range(64) for role in ROLES}
    if len(rows) != 576 or {(r["condition"], r["policy"]) for r in rows} != expected:
        raise ValueError("matrix gap/duplicate")
    if sum(x["environments"] for x in counts) > reg["aggregate_cap"] or any(x["learning"] for x in counts):
        raise ValueError("aggregate budget")
    common = []
    for i in range(64):
        q = [r for r in rows if r["condition"] == i]
        if all(r["incomplete"] == r["urgent_failure"] == r["normal_failure"] == r["urgent_original_cap_failure"] == r["normal_original_cap_failure"] == 0 for r in q):
            common.append(i)
    budget.write(folder / "merged_rows.json", rows)
    budget.write(folder / "consumption.json", dict(environments=sum(x["environments"] for x in counts), learning=0,
                                                 failed=sum(x["failed"] for x in counts), worker_active_seconds_sum=sum(x["active_seconds"] for x in counts),
                                                 aggregate_cap=600, workers=counts, device_commands=0))
    budget.write(folder / "service_intersection.json", dict(common_service_conditions=common, total_conditions=64,
                                                           all_rows_retained=True, original_strict_not_replaced=True))
    return dict(completed=True, rows=len(rows), common_service_conditions=len(common))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("command", choices=("register", "check", "run", "merge"))
    p.add_argument("--run-root", type=Path, required=True)
    p.add_argument("--shard", type=int)
    x = p.parse_args()
    result = register(x.run_root) if x.command == "register" else check(x.run_root) if x.command == "check" else run(x.run_root, x.shard) if x.command == "run" else merge(x.run_root)
    print(json.dumps(previous.serial(result), ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
