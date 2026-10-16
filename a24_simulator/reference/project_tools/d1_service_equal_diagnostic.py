"""Post-hoc old-load diagnosis, eight extra starts inside the existing600 cap."""
import argparse
from pathlib import Path
from tools import d1_service_equal_study as s
from tools import d1_service_equal_budget as b
from tools import d1_service_equal_mobile as ready
from tools import d1_atc_repair_study as previous

CONDITIONS = (0, 12, 16, 28, 32, 44, 48, 60)


def register(folder):
    s.check(folder)
    if (folder / "diagnostic_registration.json").exists():
        raise FileExistsError("supplement already registered")
    source = Path(__file__)
    oldinputs = previous.budget.read(s.REPAIR / "inputs.json")
    cases = [oldinputs["confirmation"][i] for i in CONDITIONS]
    if any(q["factor"] != "single_fixed" or q["family"] not in ("low", "sustained") for q in cases):
        raise ValueError("unchanged old load diagnosis")
    b.write(folder / "diagnostic_registration.json", dict(
        scope="post-hoc diagnosis on already seen05 inputs, not new confirmation/selection",
        source=source.relative_to(s.ROOT).as_posix(), sha256=b.digest(source),
        original_parent_registration_sha=b.digest(folder / "registration.json"),
        old05_inputs_sha=b.digest(s.REPAIR / "inputs.json"), conditions=CONDITIONS,
        requested_new_environments=8, learning=0, before_environments=576, final_expected=584,
        original_parent_cap=600, original_child_cap=150, child_extra=2,
        old_fifo_eft_reused_saved_reference_no_new_environments=True,
        realization=previous.REALIZATION, source_policy_sha=b.digest(s.ROOT / "tools/d1_service_equal_mobile.py")))
    return dict(registered=True, planned_new_environments=8, aggregate_cap=600)


def run(folder, shard):
    s.check(folder)
    reg = b.read(folder / "diagnostic_registration.json")
    if b.digest(s.ROOT / reg["source"]) != reg["sha256"] or b.digest(s.REPAIR / "inputs.json") != reg["old05_inputs_sha"]:
        raise ValueError("diagnostic immutable source/inputs")
    child = folder / f"shard{shard}"
    diagnostic = child / "diagnostics"
    diagnostic.mkdir(exist_ok=True)
    budget = b.Budget(child)
    inputs = previous.budget.read(s.REPAIR / "inputs.json")["confirmation"]
    f, init, _ = s.a.hybrid.load()
    with budget.session():
        for index in CONDITIONS[shard*2:(shard+1)*2]:
            case = inputs[index]
            identity = f"oldloadprobe_{index:02d}_FIFO_READY_EFT"
            if (diagnostic / "rows" / (identity + ".json")).exists():
                continue
            previous.collect(budget, diagnostic, identity, "posthoc_oldload_diagnostic",
                             dict(case, role=ready.ROLE), ready.Controller(f, init["initial"]))
    return dict(shard=shard, consumption=budget.used())


def main():
    import json
    p = argparse.ArgumentParser()
    p.add_argument("command", choices=("register", "run"))
    p.add_argument("--run-root", type=Path, required=True)
    p.add_argument("--shard", type=int)
    x = p.parse_args()
    print(json.dumps(register(x.run_root) if x.command == "register" else run(x.run_root, x.shard)), flush=True)


if __name__ == "__main__":
    main()
