"""Same eight seen05 diagnostic inputs for RR/Greedy, within07 immutable160 cap."""
import argparse
import json
from pathlib import Path
from tools import d1_simple_mobile_study as s
from tools import d1_service_equal_diagnostic as olddiagnosis
from tools import d1_atc_repair_study as previous


def register(folder):
    s.check(folder)
    path = folder / "diagnostic_registration.json"
    if path.exists():
        raise FileExistsError("diagnosis already registered")
    src = Path(__file__)
    s.budget.write(path, dict(scope="posthoc same already seen05 inputs, not independentfinal/selection",
                             conditions=olddiagnosis.CONDITIONS, roles=s.policy.ROLES, old_realization=previous.REALIZATION,
                             new_environments=16, parent_original_cap=160, before128=True, expected_after144=True,
                             extra_per_worker=4, child_original_cap=40, learning=0,
                             source=src.relative_to(s.ROOT).as_posix(), sha256=s.budget.digest(src),
                             old05_inputs_sha=s.budget.digest(olddiagnosis.s.REPAIR / "inputs.json"),
                             original_registration_sha=s.budget.digest(folder / "registration.json")))
    return dict(registered=True, new_environments=16, originalcap160=True)


def run(folder, shard):
    reg = s.check(folder)
    diag = s.budget.read(folder / "diagnostic_registration.json")
    if s.budget.digest(s.ROOT / diag["source"]) != diag["sha256"]:
        raise ValueError("diagnostic source changed")
    inputs = previous.budget.read(olddiagnosis.s.REPAIR / "inputs.json")["confirmation"]
    previous.REALIZATION = diag["old_realization"]
    child = folder / f"shard{shard}"
    target = child / "diagnostics"
    target.mkdir(exist_ok=True)
    b = s.budget.Budget(child)
    f, initial, _ = s.previous.a.hybrid.load()
    with b.session():
        for index in diag["conditions"][2*shard:2*(shard+1)]:
            for role in s.policy.ROLES:
                identity = f"oldloadprobe_{index:02d}_{role}"
                if (target / "rows" / (identity+".json")).exists():
                    continue
                previous.collect(b, target, identity, "posthoc_oldload_diagnostic",
                                 dict(inputs[index], role=role), s.policy.Controller(f, initial["initial"], role, reg["affinities"]["preferred"]))
    return dict(shard=shard, consumption=b.used())


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("command", choices=("register", "run"))
    p.add_argument("--run-root", type=Path, required=True)
    p.add_argument("--shard", type=int)
    x = p.parse_args()
    print(json.dumps(register(x.run_root) if x.command == "register" else run(x.run_root, x.shard)), flush=True)
