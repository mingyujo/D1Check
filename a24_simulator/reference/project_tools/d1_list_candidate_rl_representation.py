"""Pure necessary-condition certificates for recorded ListV2 schedules.

No policy, simulator, torch or learner is imported.  A negative certificate
proves that the exact recorded dispatch schedule needs more discretionary
delay than the new bank permits between actual dispatches.  The absence of
such a certificate is UNKNOWN, never a chronological replay PASS.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from fractions import Fraction
import gzip
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "output/list_candidate_rl_implementation_20261010_v1"
CONTEXTS = ("mean", "short_context", "long_context")
NS = 1_000_000_000
ROUNDING_RADIUS_NS = Fraction(1, 2)
CREDIT_NS = 250_000_000
SUPPORTED = {("classification", "CPU"), ("classification", "GPU"), ("detection", "CPU")}


class SourceIntegrityError(ValueError):
    pass


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def exact(value: Fraction) -> dict:
    value = Fraction(value)
    return {"numerator": value.numerator, "denominator": value.denominator}


def as_ns(value: Fraction) -> int | float:
    return value.numerator if value.denominator == 1 else float(value)


def compatible(left: tuple[str, str], right: tuple[str, str]) -> bool:
    return left[1] != right[1] and {left, right} == {
        ("classification", "GPU"), ("detection", "CPU")
    }


def validate_ledger(ledger: list[dict]) -> None:
    if not 0 < len(ledger) <= 192:
        raise SourceIntegrityError("source request count outside existing bound")
    ids = [row.get("id") for row in ledger]
    if any(not isinstance(rid, str) for rid in ids) or len(ids) != len(set(ids)):
        raise SourceIntegrityError("missing/duplicate source request ID")
    for row in ledger:
        for key in ("arrival_ns", "dispatch_ns", "lane_available_ns", "ordinal", "deadline_offset_ns"):
            if type(row.get(key)) is not int:
                raise SourceIntegrityError("source ledger must retain integer ns/ordinal: " + key)
        if row.get("status") != "succeeded":
            raise SourceIntegrityError("partial source ledger cannot certify complete chronology")
        pair = (row.get("task"), row.get("backend"))
        if pair not in SUPPORTED:
            raise SourceIntegrityError("unsupported source task/backend")
        priority, deadline = ("urgent", 1_500_000_000) if pair[0] == "classification" else ("normal", 6 * NS)
        if row.get("priority") != priority or row["deadline_offset_ns"] != deadline:
            raise SourceIntegrityError("source task/priority/deadline contract changed")
        if not row["arrival_ns"] <= row["dispatch_ns"] < row["lane_available_ns"]:
            raise SourceIntegrityError("invalid source arrival/dispatch/full-lane ordering")
        phase_keys = ("execution_start_ns", "output_ready_ns", "persist_complete_ns", "worker_release_ns")
        present = [row[key] for key in phase_keys if key in row]
        sequence = [row["dispatch_ns"], *present, row["lane_available_ns"]]
        if any(type(value) is not int for value in present) or sequence != sorted(sequence):
            raise SourceIntegrityError("invalid source public phase ordering")

    # These are recorded integer-ns intervals.  A valid serial handoff records
    # the same rounded timestamp for old AVAILABLE and new dispatch.
    points = sorted({row[key] for row in ledger for key in ("dispatch_ns", "lane_available_ns")})
    for left, right in zip(points, points[1:]):
        middle = Fraction(left + right, 2)
        owned = [row for row in ledger if row["dispatch_ns"] <= middle < row["lane_available_ns"]]
        if len(owned) > 2 or any(
            not compatible((a["task"], a["backend"]), (b["task"], b["backend"]))
            for i, a in enumerate(owned) for b in owned[i + 1:]
        ):
            raise SourceIntegrityError("unsupported recorded ownership overlap")


def fifo_witness(ledger: list[dict]) -> dict | None:
    """Only certify a violation outside dispatch rounding ambiguity."""
    for selected in sorted(ledger, key=lambda row: (row["dispatch_ns"], row["ordinal"], row["id"])):
        selected_earliest = Fraction(selected["dispatch_ns"]) - ROUNDING_RADIUS_NS
        selected_latest = Fraction(selected["dispatch_ns"]) + ROUNDING_RADIUS_NS
        selected_key = (selected["arrival_ns"], selected["ordinal"], selected["id"])
        earlier = [row for row in ledger if row["task"] == selected["task"]
                   and (row["arrival_ns"], row["ordinal"], row["id"]) < selected_key
                   and row["arrival_ns"] <= selected_earliest
                   and Fraction(row["dispatch_ns"]) - ROUNDING_RADIUS_NS > selected_latest]
        if earlier:
            oldest = min(earlier, key=lambda row: (row["arrival_ns"], row["ordinal"], row["id"]))
            return {"selected_request": selected["id"], "selected_backend": selected["backend"],
                    "selected_dispatch_ns": selected["dispatch_ns"], "queued_earlier_request": oldest["id"],
                    "queued_earlier_dispatch_ns": oldest["dispatch_ns"]}
    return None


def qualifying_intervals(ledger: list[dict]) -> list[dict]:
    """Conservative public ownership/head intervals under round(now) +-0.5ns.

    A possible owner blocks a lane until its latest possible AVAILABLE.  A
    chosen head must certainly be queued and be earliest even among possibly
    queued requests.  Thus ambiguity can only REMOVE counted delay.
    """
    points = {Fraction(row["arrival_ns"]) for row in ledger}
    for row in ledger:
        for key in ("dispatch_ns", "lane_available_ns"):
            points.update((Fraction(row[key]) - ROUNDING_RADIUS_NS, Fraction(row[key]) + ROUNDING_RADIUS_NS))
    points = sorted(points)
    result = []
    for start, end in zip(points, points[1:]):
        middle = (start + end) / 2
        possible_owners = [row for row in ledger
                           if Fraction(row["dispatch_ns"]) - ROUNDING_RADIUS_NS <= middle
                           < Fraction(row["lane_available_ns"]) + ROUNDING_RADIUS_NS]
        possible_queued = [row for row in ledger if row["arrival_ns"] <= middle
                           < Fraction(row["dispatch_ns"]) + ROUNDING_RADIUS_NS]
        heads = {}
        for task in ("classification", "detection"):
            ordered = sorted((row for row in possible_queued if row["task"] == task),
                             key=lambda row: (row["arrival_ns"], row["ordinal"], row["id"]))
            if ordered and middle < Fraction(ordered[0]["dispatch_ns"]) - ROUNDING_RADIUS_NS:
                heads[task] = ordered[0]
        jobs = []
        for task, head in heads.items():
            for backend in (("CPU", "GPU") if task == "classification" else ("CPU",)):
                pair = (task, backend)
                if all(compatible(pair, (owned["task"], owned["backend"])) for owned in possible_owners):
                    jobs.append({"request_id": head["id"], "task": task, "backend": backend})
        if jobs:
            result.append({"start": start, "end": end, "jobs": jobs,
                           "head_ids": {task: row["id"] for task, row in heads.items()},
                           "possible_owned": [{"request_id": row["id"], "task": row["task"],
                                               "backend": row["backend"]} for row in possible_owners]})
    return result


def certificate_from_ledger(ledger: list[dict]) -> dict:
    validate_ledger(ledger)
    fifo = fifo_witness(ledger)
    intervals = qualifying_intervals(ledger)
    dispatches = defaultdict(list)
    for row in ledger:
        dispatches[row["dispatch_ns"]].append(row["id"])
    points = sorted(dispatches)
    spells = []
    # Initial credit has the same .25 upper bound.  No requests precede the
    # exact first arrival, so omitting pre-arrival time cannot hide debit.
    windows = [(None, points[0])] + list(zip(points, points[1:]))
    for reset, following in windows:
        start = (Fraction(min(row["arrival_ns"] for row in ledger)) if reset is None
                 else Fraction(reset) + ROUNDING_RADIUS_NS)
        end = Fraction(following) - ROUNDING_RADIUS_NS
        counted = []
        for interval in intervals:
            lo, hi = max(start, interval["start"]), min(end, interval["end"])
            if hi > lo:
                counted.append({**interval, "start": lo, "end": hi})
        required = sum((part["end"] - part["start"] for part in counted), Fraction(0))
        spells.append({"reset": reset, "following": following, "required": required, "parts": counted})
    worst = max(spells, key=lambda spell: spell["required"])
    exclusions = [spell for spell in spells if spell["required"] > CREDIT_NS]

    def describe(spell: dict) -> dict:
        debit = Fraction(0)
        exhausted_at = None
        for part in spell["parts"]:
            length = part["end"] - part["start"]
            if exhausted_at is None and debit + length >= CREDIT_NS:
                exhausted_at = part["start"] + CREDIT_NS - debit
            debit += length
        reset, following = spell["reset"], spell["following"]
        return {"reset_dispatch_ns": reset,
                "reset_request_ids": sorted(dispatches[reset]) if reset is not None else [],
                "next_dispatch_ns": following, "next_request_ids": sorted(dispatches[following]),
                "same_rounded_dispatch_group_count": len(dispatches[reset]) if reset is not None else 0,
                "safe_interval_start_ns": as_ns(Fraction(reset) + ROUNDING_RADIUS_NS) if reset is not None
                                          else min(row["arrival_ns"] for row in ledger),
                "safe_interval_end_ns": as_ns(Fraction(following) - ROUNDING_RADIUS_NS),
                "intermediate_actual_dispatch_count": 0,
                "required_discretionary_ns_exact": exact(spell["required"]),
                "required_discretionary_s_lower_bound": float(spell["required"]) / NS,
                "credit_upper_bound_s": CREDIT_NS / NS,
                "certificate_margin_ns_exact": exact(spell["required"] - CREDIT_NS),
                "certificate_margin_s": float(spell["required"] - CREDIT_NS) / NS,
                "first_certified_feasible_ns": as_ns(spell["parts"][0]["start"]) if spell["parts"] else None,
                "credit_exhaustion_boundary_ns": as_ns(exhausted_at) if exhausted_at is not None else None,
                "parts": [{"start_ns": as_ns(part["start"]), "end_ns": as_ns(part["end"]),
                           "duration_ns_exact": exact(part["end"] - part["start"]),
                           "head_ids": part["head_ids"], "physically_feasible_jobs": part["jobs"],
                           "possible_owned_jobs": part["possible_owned"]} for part in spell["parts"]]}

    excluded = fifo is not None or bool(exclusions)
    return {"exact_schedule_outcome": "excluded" if excluded else "unknown",
            "exclusion_reasons": (["head_restriction"] if fifo else [])
                                 + (["discretionary_credit_lower_bound"] if exclusions else []),
            "planned_and_completed_requests": len(ledger), "same_time_dispatch_groups": len(dispatches),
            "fifo_violation_witness": fifo,
            "credit_exclusion_spells": len(exclusions),
            "maximum_required_discretionary_s_lower_bound": float(worst["required"]) / NS,
            "total_required_discretionary_s_lower_bound": float(sum((s["required"] for s in spells), Fraction(0))) / NS,
            "worst_spell": describe(worst), "credit_witnesses": [describe(spell) for spell in exclusions],
            "unknown_if_not_excluded": ["timer reachability", "phase-only hold versus old redecision",
                                       "same-time bundle commitment", "full actual-credit candidate path"],
            "proof_scope": "necessary-condition exclusion of this exact recorded dispatch schedule; not policy performance or exhaustive path search"}


def expected_artifact_hashes(root: Path) -> dict[str, str]:
    completed = {}
    for line in (root / "execution.jsonl").read_text(encoding="utf8").splitlines():
        row = json.loads(line)
        if row.get("event") == "completion" and row.get("status") == "completed":
            identity = row["identity"]
            if identity in completed:
                raise SourceIntegrityError("duplicate source completion identity")
            completed[identity] = row["artifact_sha256"]
    return completed


def run(source_root: str | Path = DEFAULT_SOURCE) -> dict:
    source_root = Path(source_root)
    pinned = expected_artifact_hashes(source_root)
    registration = json.loads((source_root / "registration.json").read_text(encoding="utf8"))
    cases = []
    for context in CONTEXTS:
        identity = "source_intent_" + context
        path = source_root / "items" / (identity + ".json.gz")
        digest = sha(path)
        if identity not in pinned or digest != pinned[identity]:
            raise SourceIntegrityError("pinned original artifact changed: " + identity)
        item = json.loads(gzip.decompress(path.read_bytes()))
        prior_identity = "prior_success_" + context
        prior_path = source_root / "items" / (prior_identity + ".json.gz")
        prior_digest = sha(prior_path)
        if prior_identity not in pinned or prior_digest != pinned[prior_identity]:
            raise SourceIntegrityError("pinned original success changed: " + prior_identity)
        prior = json.loads(gzip.decompress(prior_path.read_bytes()))
        for field in ("ledger", "transitions", "metrics", "decisions"):
            if item["result"][field] != prior["result"][field]:
                raise SourceIntegrityError("passive source tap changed original success: " + context + "/" + field)
        result, row = item["result"], item["row"]
        if row["completed"] != row["planned"] or result["metrics"]["planned"] != len(result["ledger"]):
            raise SourceIntegrityError("source completion denominator changed")
        outcome = certificate_from_ledger(result["ledger"])
        outcome.update(context=context, source_artifact="items/" + path.name, source_sha256=digest,
                       pinned_completion_hash_verified=True, source_row_preserved=row,
                       prior_success_artifact="items/" + prior_path.name, prior_success_sha256=prior_digest,
                       original_ledger_transitions_metrics_decisions_exact=True,
                       source_decision_count=len(result["decisions"]),
                       source_transition_count=len(result["transitions"]))
        cases.append(outcome)
    return {"status": "completed", "scope": "read-only pure chronological necessary-condition certificates",
            "source_task": registration["task"], "source_head": registration["head"],
            "source_registration_sha256": sha(source_root / "registration.json"),
            "source_execution_ledger_sha256": sha(source_root / "execution.jsonl"),
            "certificate_source_sha256": sha(Path(__file__)),
            "frozen_model_sha256": registration["frozen_model_sha256"],
            "frozen_initial_sha256": registration["frozen_initial_sha256"],
            "rounding_assumption": "original native round(now) integer timestamps have at most0.5ns error; arrival timestamps are exact registered integers",
            "rounding_radius_ns_exact": exact(ROUNDING_RADIUS_NS),
            "numeric_credit_epsilon": 0, "credit_upper_bound_s": CREDIT_NS / NS,
            "no_credit_reset_on_phase_or_release_or_arrival": True,
            "credit_exclusion_uses_actual_feasible_alternative_time_not_declared_old_timer": True,
            "same_time_dispatches_grouped_before_counting_delay": True,
            "absence_of_negative_certificate_is_replay_PASS": False,
            "no_automatic_bank_credit_objective_change": True,
            "cases": cases, "all_three_exact_schedules_excluded": all(case["exact_schedule_outcome"] == "excluded" for case in cases),
            "consumption": {"native_environment_starts": 0, "learning_starts": 0, "device_commands": 0}}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output-json", type=Path)
    args = parser.parse_args()
    value = run(args.source_root)
    text = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if args.output_json is not None:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(text, encoding="utf8", newline="\n")
    print(text, end="")


if __name__ == "__main__":
    main()
