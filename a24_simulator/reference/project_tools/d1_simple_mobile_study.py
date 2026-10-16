"""Add two fixed mobile controls to the immutable06 paired inputs, zero learning."""
import argparse
import json
from pathlib import Path
import torch
from tools import d1_service_equal_study as equal
from tools import d1_atc_repair_study as previous
from tools import d1_simple_mobile_policy as policy
from tools import d1_simple_mobile_budget as budget

ROOT = previous.ROOT
PARENT = ROOT.parent / "SERVICE-EQUAL-COMPARE-06"
TASK = "MOBILE-BASELINES-COMPARE-07"


def register(folder):
    equal.check(PARENT)
    if folder.exists():
        raise FileExistsError("never reset run")
    inputs = budget.read(PARENT / "inputs.json")
    sources = previous.sources()
    for name in ("d1_simple_mobile_policy.py", "d1_simple_mobile_study.py", "d1_simple_mobile_budget.py", "test_d1_simple_mobile.py"):
        sources["tools/"+name] = budget.digest(ROOT / "tools" / name)
    folder.mkdir(parents=True)
    reg = dict(task=TASK, parent_registration_sha=budget.digest(PARENT / "registration.json"),
               parent_inputs_sha=budget.digest(PARENT / "inputs.json"), parent_rows_sha=budget.digest(PARENT / "merged_rows.json"),
               sources=sources, input_sha=previous.a.native.digest(inputs), roles=policy.ROLES,
               affinities=policy.preferences(), realization=equal.REALIZATION, workers=4,
               planned_environments=128, aggregate_environment_cap=160, child_cap=40,
               learning=0, fitted_physics=0, device=0, S26=0, NPU=0,
               comparison="64same06inputs/draws,9oldroles576savedrows reused+2newroles128=11roles704pairedrows; no retuning/selection",
               RR="oldest current ready request,CPU-first global cyclic legal supported resource; pointer advances only actualdispatch; skip unsupported/busy/jointillegal; not forced50:50 nor timeslice preemption",
               Greedy="fixed measured medianwholeoccupancy supported preferred backend,CPU tie; perresourceFIFO heads,otherresourcecanprogress; preference never updatesonline;CPUclassification4weak",
               literature={"COSREL": "https://par.nsf.gov/servlets/purl/10303786", "Niagara": "https://xumengwei.github.io/files/ICSOC23-Niagara.pdf"},
               evidence="COSREL4.1 primary indexed original: Pixel2XLAndroid10 CPU/GPU roundrobin; Niagara4.1 primaryPDF: Android10SnapdragonedgeSoCs affinityprocessor waits; not smartphone claim for Niagara",
               adaptation="D1Check support/AVAILABLE/nonpreemptive/CG_DCmax2/whole request, not exact paperreproduction or energyoptimality",
               strict="alloriginal completion/request+cap/P95/J/AP protection, percondition losses, sharedSLAintersection reported",
               experiment_ready=False, automatic_adoption=False)
    budget.write(folder / "registration.json", reg)
    budget.write(folder / "inputs.json", inputs)
    for shard in range(4):
        budget.Budget.register(folder / f"shard{shard}", dict(parent=TASK, parent_sha=budget.digest(folder / "registration.json"),
                                                           cases=list(range(16*shard, 16*(shard+1))), planned=32))
        budget.write(folder / f"shard{shard}/cursor.json", dict(completed=False))
    return dict(registered=True, environments=128, aggregate_cap=160, learning=0, affinities=reg["affinities"])


def check(folder):
    equal.check(PARENT)
    reg = budget.read(folder / "registration.json")
    for p, sha in reg["sources"].items():
        if budget.digest(ROOT / p) != sha:
            raise ValueError("fixedsource changed: "+p)
    for filename, key in (("registration.json", "parent_registration_sha"), ("inputs.json", "parent_inputs_sha"), ("merged_rows.json", "parent_rows_sha")):
        if budget.digest(PARENT / filename) != reg[key]:
            raise ValueError("fixed paired reference changed")
    if previous.a.native.digest(budget.read(folder / "inputs.json")) != reg["input_sha"] or policy.preferences() != reg["affinities"]:
        raise ValueError("fixedinput/affinity changed")
    return reg


def run(folder, shard):
    if not 0 <= shard < 4:
        raise ValueError("unknownshard")
    reg = check(folder)
    previous.REALIZATION = reg["realization"]
    torch.set_num_threads(1)
    child = folder / f"shard{shard}"
    b = budget.Budget(child)
    if budget.read(child / "cursor.json")["completed"]:
        return dict(completed=True, consumption=b.used())
    f, init, _ = previous.a.hybrid.load()
    with b.session():
        for case in budget.read(folder / "inputs.json")[16*shard:16*(shard+1)]:
            for role in policy.ROLES:
                identity = f"comparison_{case['condition']:02d}_{role}"
                if (child / "rows" / (identity+".json")).exists():
                    continue
                controller = policy.Controller(f, init["initial"], role, reg["affinities"]["preferred"])
                previous.collect(b, child, identity, "comparison", dict(case, role=role), controller)
        budget.write(child / "cursor.json", dict(completed=True, rows=32))
    return dict(completed=True, shard=shard, consumption=b.used())


def merge(folder):
    reg = check(folder)
    newrows, counts = [], []
    for shard in range(4):
        child = folder / f"shard{shard}"
        if not budget.read(child / "cursor.json")["completed"]:
            raise ValueError("incomplete shard")
        counts.append(budget.Budget(child).used())
        for path in sorted((child / "rows").glob("*.json")):
            receipt = budget.read(path)
            if budget.digest(child / "items" / (path.stem+".json.gz")) != receipt["raw_sha256"]:
                raise ValueError("raw changed")
            newrows.append(receipt["row"])
    if len(newrows) != 128 or {(r["condition"], r["policy"]) for r in newrows} != {(i, role) for i in range(64) for role in policy.ROLES}:
        raise ValueError("newmatrix mismatch")
    if sum(c["environments"] for c in counts) > reg["aggregate_environment_cap"] or any(c["learning"] for c in counts):
        raise ValueError("aggregatecap")
    rows = budget.read(PARENT / "merged_rows.json")+newrows
    if len(rows) != 704 or len({(r["condition"], r["policy"]) for r in rows}) != 704:
        raise ValueError("11role paired matrix mismatch")
    budget.write(folder / "new_rows.json", newrows)
    budget.write(folder / "merged_rows.json", rows)
    budget.write(folder / "consumption.json", dict(environments=sum(c["environments"] for c in counts), learning=0,
                                                 failed=sum(c["failed"] for c in counts), worker_active_seconds_sum=sum(c["active_seconds"] for c in counts),
                                                 aggregate_cap=160, workers=counts, reused_rows=576, device_commands=0))
    return dict(completed=True, rows=704, new_environment_rows=128, reused_rows=576)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("command", choices=("register", "run", "merge", "check"))
    p.add_argument("--run-root", type=Path, required=True)
    p.add_argument("--shard", type=int)
    x = p.parse_args()
    result = register(x.run_root) if x.command == "register" else run(x.run_root, x.shard) if x.command == "run" else merge(x.run_root) if x.command == "merge" else check(x.run_root)
    print(json.dumps(previous.serial(result), ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
