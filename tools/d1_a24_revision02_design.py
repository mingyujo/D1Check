"""REV02 PC-only design checks. This module cannot control or execute a device."""
from __future__ import annotations

import argparse
import collections
import json
import math
import statistics
from pathlib import Path

NS = 1_000_000_000
REVISION = "A24-BLOCKED-INITIAL-STATE-REV02-20261015"


def validate_contract(contract: dict) -> None:
    """Reject execution authorization, recycled identities, and budget inflation."""
    if contract.get("revision_id") != REVISION:
        raise ValueError("wrong revision")
    if contract.get("execution_authorized") is not False or contract.get("experiment_ready") is not False:
        raise ValueError("this design is not an execution authorization")
    if contract.get("materialized_session_ids") != []:
        raise ValueError("session registration is outside the design-only task")
    budget = contract["budget"]
    if budget["authorized_new_measurement_sessions"] != 0 or budget["automatic_transfer_of_old_budget"] is not False:
        raise ValueError("no new measurement budget or automatic transfer")
    if budget["old_attempts_preserved"] + budget["old_unattempted_slots_preserved"] != budget["old_cap"]:
        raise ValueError("old budget accounting mismatch")
    if budget["proposed_sessions"] > budget["old_unattempted_slots_preserved"]:
        raise ValueError("proposal exceeds the recorded unused slots")
    if budget["proposed_sessions"] != budget["proposed_repetitions"] * len(contract["arms"]):
        raise ValueError("proposal arithmetic mismatch")
    initial = contract["initial_state"]
    if initial["rules"] != {"history_ns": 60 * NS, "maximum_wait_ns": 600 * NS,
                            "maximum_gap_ns": 10 * NS, "tolerance_c": .5,
                            "maximum_abs_slope_c_per_min": .1}:
        raise ValueError("provisional matching rules changed without a new design version")
    if initial["global_absolute_Tref_c"] is not None or initial["reanchor_per_arm"] is not False:
        raise ValueError("one reference per recipe/comparison block, never per arm")
    if initial["freeze_reference_before_first_main_request"] is not True:
        raise ValueError("a reference cannot use treatment outcomes")
    if contract["pool_with_old_revision"] is not False or contract["energy_J_supported"] is not False:
        raise ValueError("unsupported pooling or energy claim")
    if contract["ready"]["revised_executor_implemented"] is not False:
        raise ValueError("this file verifies design fixtures, not a revised executor")
    policy_ids = [arm["policy_id"] for arm in contract["arms"]]
    if len(policy_ids) != 8 or len(set(policy_ids)) != 8 or any(not value.startswith("R02_") for value in policy_ids):
        raise ValueError("revised policy IDs must be distinct and preserve all eight arms")
    orders = contract["order_and_data"]["M128_proposed_orders"]
    labels = {"BASE", "ORDER", "PAIR_G", "WAIT200"}
    if len(orders) != 4 or any(len(row) != 4 or set(row) != labels for row in orders):
        raise ValueError("incomplete mixed-workload order proposal")
    if any(set(column) != labels for column in zip(*orders)):
        raise ValueError("mixed-workload positions are not balanced")
    adjacent = collections.Counter(pair for row in orders for pair in zip(row, row[1:]))
    if len(adjacent) != 12 or any(value != 1 for value in adjacent.values()):
        raise ValueError("mixed-workload adjacent orders are not balanced")


def _window(samples: list[dict], index: int, ready_ns: int, rules: dict) -> list[dict] | None:
    current = samples[index]["before_ns"]
    if current < ready_ns or current - ready_ns > rules["maximum_wait_ns"]:
        return None
    eligible = [s for s in samples[:index + 1] if s["before_ns"] >= ready_ns]
    cutoff = current - rules["history_ns"]
    starts = [i for i, s in enumerate(eligible) if s["before_ns"] <= cutoff]
    if not starts:
        return None
    # Include one earlier boundary point, so jitter does not make a 60s history impossible.
    window = eligible[starts[-1]:]
    if len(window) < 2:
        return None
    if any(b["before_ns"] - a["before_ns"] > rules["maximum_gap_ns"] for a, b in zip(window, window[1:])):
        return None
    if any(not isinstance(s.get("AP_c"), (int, float)) or isinstance(s.get("AP_c"), bool)
           or not math.isfinite(s["AP_c"]) for s in window):
        return None
    return window


def _validate_times(samples: list[dict]) -> None:
    previous = -1
    for sample in samples:
        before, after = sample["before_ns"], sample["after_ns"]
        if type(before) is not int or type(after) is not int or before <= previous or after < before:
            raise ValueError("invalid or reordered observable clock brackets")
        previous = before


def _slope(window: list[dict]) -> float:
    xs = [(s["before_ns"] - window[0]["before_ns"]) / (60 * NS) for s in window]
    mx, my = statistics.mean(xs), statistics.mean(s["AP_c"] for s in window)
    return sum((x - mx) * (s["AP_c"] - my) for x, s in zip(xs, window)) / sum((x - mx) ** 2 for x in xs)


def first_reference(samples: list[dict], ready_ns: int, rules: dict) -> dict | None:
    """Synthetic/offline rule check; no files, clocks, sensors, or device calls."""
    _validate_times(samples)
    for index in range(len(samples)):
        window = _window(samples, index, ready_ns, rules)
        if not window:
            continue
        reference = statistics.median(s["AP_c"] for s in window)
        slope = _slope(window)
        if abs(slope) > rules["maximum_abs_slope_c_per_min"]:
            continue
        if any(abs(s["AP_c"] - reference) > rules["tolerance_c"] for s in window):
            continue
        return {"Tref_c": reference, "history_start_ns": window[0]["before_ns"],
                "read_before_ns": window[-1]["before_ns"], "read_after_ns": window[-1]["after_ns"],
                "slope_c_per_min": slope, "independent_sensor_updates_verified": False,
                "outcome_inputs_used": False}
    return None


def matches_fixed_reference(samples: list[dict], ready_ns: int, reference: dict, rules: dict) -> bool:
    """Every later arm must match the same reference; never calculate its own."""
    _validate_times(samples)
    for index in range(len(samples)):
        window = _window(samples, index, ready_ns, rules)
        if window and abs(_slope(window)) <= rules["maximum_abs_slope_c_per_min"] and all(
                abs(s["AP_c"] - reference["Tref_c"]) <= rules["tolerance_c"] for s in window):
            return True
    return False


def require_same_revision(revision_ids: list[str]) -> None:
    if not revision_ids or any(value != REVISION for value in revision_ids):
        raise ValueError("old and revised measurement results must not be pooled")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("contract", type=Path)
    args = parser.parse_args()
    validate_contract(json.loads(args.contract.read_text(encoding="utf-8")))
    print(json.dumps({"contract_check": "PASS", "revision_id": REVISION,
                      "execution_authorized": False, "device_commands": 0, "NN_calls": 0,
                      "sessions_registered": 0, "device_validation": False}))
