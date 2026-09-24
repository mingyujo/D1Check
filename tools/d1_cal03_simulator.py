"""Bounded PC engine check, not an arrival-policy evaluation or frozen simulation run.

Solo only. Realized per-request vectors belong to the engine, never the policy.
Decision cost, zero arrival lag and transfer to queued/mixed traffic are explicit
unvalidated assumptions. No fitted probability distribution, CI or success claim.
"""
from __future__ import annotations

import argparse
import heapq
import json
import time
from pathlib import Path

from tools import d1_arrival_plan as common
from tools import d1_cal03_connection as policy

VERSION = "cal03-solo-event-engine-dev-v1"
PHASES = ("EXECUTING", "OUTPUT_READY", "PERSISTED", "WORKER_RELEASED", "AVAILABLE")
TIMES = policy.STEPS[1:]


def simulate(config, realizations, requests, *, decision_cost_ns, horizon_ns,
             assumption_ranking=False, maximum_concurrency=1):
    policy.validate_config(config)
    policy.require(maximum_concurrency == 1, "OUT_OF_SUPPORT: overlap not measured")
    policy.require(type(decision_cost_ns) is int and 0 <= decision_cost_ns <= 1_000_000_000,
                   "explicit decision-cost assumption in [0, 1s] required")
    policy.require(type(horizon_ns) is int and 0 < horizon_ns <= 120_000_000_000, "bounded horizon required")
    policy.require(0 < len(requests) <= 32, "PC check limited to 1..32 planned requests")
    policy.require(realizations["protocol"] == policy.VERSION and set(realizations["cells"]) == policy.CELLS, "realization identity")
    for vectors in realizations["cells"].values():
        policy.require(len(vectors) == 4, "four correlated vectors/cell; not a distribution")
        for vector in vectors:
            ds = vector["durations_ns"]
            policy.require(len(ds) == 5 and all(type(d) is int and 0 <= d <= 20_000_000_000 for d in ds), "realization intervals")
    ids = set()
    events, sequence = [], 0

    def schedule(at, kind, value):
        nonlocal sequence
        heapq.heappush(events, (at, sequence, kind, value))
        sequence += 1

    ledger = {}
    for r in requests:
        policy.require(set(r) == {"id", "task", "priority", "ordinal", "arrival_ns", "deadline_offset_ns"}, "request schema")
        policy.require(r["id"] not in ids and type(r["arrival_ns"]) is int and r["arrival_ns"] >= 0 and
                       type(r["deadline_offset_ns"]) is int and r["deadline_offset_ns"] > 0 and
                       r["task"] in ("classification", "detection") and r["priority"] in ("urgent", "normal"), "request validity")
        ids.add(r["id"])
        ledger[r["id"]] = dict(r, terminal_status="not_arrived", response_ns=None)
        schedule(r["arrival_ns"], "arrival", r["id"])
    waiting, lanes, decisions = [], {b: policy.available() for b in ("CPU", "GPU")}, []
    used = {key: 0 for key in policy.CELLS}
    pending = None
    transitions = []
    # A deterministic tie rule: process all already scheduled events at t in
    # insertion order before a new decision. Release+arrival at t are both seen.
    while events and events[0][0] <= horizon_ns:
        now = events[0][0]
        while events and events[0][0] == now:
            _, _, kind, value = heapq.heappop(events)
            if kind == "arrival":
                row = ledger[value]
                row.update(actual_arrival_ns=now, queue_entry_ns=now, terminal_status="queued")
                waiting.append({k: row[k] for k in ("id", "task", "priority", "ordinal", "arrival_ns")})
            elif kind == "dispatch":
                rid, backend = value
                row = ledger[rid]
                policy.require(pending == value and all(l["phase"] == "AVAILABLE" for l in lanes.values()), "reservation/lane conflict")
                pending = None
                row.update(dispatch_ns=now, backend=backend, terminal_status="executing")
                lanes[backend] = dict(phase="ASSIGNED", request_id=rid, task=row["task"], priority=row["priority"],
                                      phase_since_ns=now, persist_since_ns=None)
                transitions.append(dict(at_ns=now, request_id=rid, backend=backend, phase="ASSIGNED"))
                key = f"{row['task']}_{backend}_{row['priority']}"
                # Explicit ordinal cycling, not independent resampling. Only engine sees this vector.
                index = used[key] % 4
                vector = realizations["cells"][key][index]
                used[key] += 1
                row["realization_source_request_id"] = vector["source_request_id"]
                at = now
                for phase, field, duration in zip(PHASES, TIMES, vector["durations_ns"]):
                    at += duration
                    schedule(at, "phase", (rid, backend, phase, field))
            else:
                rid, backend, phase, field = value
                row = ledger[rid]
                policy.require(lanes[backend]["request_id"] == rid, "stale callback must not release another request")
                row[field] = now
                transitions.append(dict(at_ns=now, request_id=rid, backend=backend, phase=phase))
                lanes[backend]["phase"] = phase
                lanes[backend]["phase_since_ns"] = now
                if phase == "PERSISTED":
                    lanes[backend]["persist_since_ns"] = now
                if (phase == "OUTPUT_READY" and row["priority"] == "urgent" or
                        phase == "PERSISTED" and row["priority"] == "normal"):
                    row.update(completion_ns=now, response_ns=now - row["arrival_ns"],
                               late_success=now > row["arrival_ns"] + row["deadline_offset_ns"])
                if phase == "AVAILABLE":
                    row["terminal_status"] = "succeeded"
                    lanes[backend] = policy.available(now)
        if pending is not None:
            continue  # Arrivals still occur while the scheduler executes its assumed decision cost.
        begin = time.perf_counter_ns()
        decision = policy.decide(config, waiting, lanes, now,
            assumed_common_decision_ns=decision_cost_ns if assumption_ranking else None)
        decision["pc_compute_ns"] = time.perf_counter_ns() - begin
        # PC wall time is reported, not silently substituted for Android D->A.
        decisions.append(decision)
        if decision["selected"]:
            selected = decision["selected"]
            rid, backend = selected["request_id"], selected["backend"]
            waiting = [t for t in waiting if t["id"] != rid]
            ledger[rid].update(decision_ns=now, terminal_status="reserved")
            pending = (rid, backend)
            schedule(now + decision_cost_ns, "dispatch", pending)
    for row in ledger.values():
        if row["terminal_status"] not in ("succeeded", "not_arrived"):
            row["terminal_status"] = "unfinished_at_horizon"
        if "execution_start_ns" in row:
            row["queue_wait_ns"] = row["execution_start_ns"] - row["queue_entry_ns"]
            row["dispatch_to_start_ns"] = row["execution_start_ns"] - row["dispatch_ns"]
        if "output_ready_ns" in row:
            row["service_ns"] = row["output_ready_ns"] - row["execution_start_ns"]
    counts = {s: sum(r["terminal_status"] == s for r in ledger.values())
              for s in ("succeeded", "unfinished_at_horizon", "not_arrived")}
    complete = counts["succeeded"] == len(requests)
    start = min(r["arrival_ns"] for r in requests)
    makespan = max(r["lane_available_ns"] for r in ledger.values()) - start if complete else None
    return dict(protocol=VERSION, policy=policy.POLICY, experiment_ready=False, performance_pass=None,
        evidence_role="PC engine scenario, not measured or independent predictive validation",
        assumptions=dict(decision_cost_ns=decision_cost_ns, decision_cost_role="unmeasured user-supplied sensitivity constant",
            ranking_mode="explicit_common_cost_assumption" if assumption_ranking else "strict_missing_cost_CPU_fallback",
            no_selection_decision_cost_ns="assumed_zero; PC compute recorded, Android cost unmeasured",
            decision_triggers="each event batch; abstract engine, not exact Activity callback scheduling",
            arrival_lag_ns="assumed_zero", concurrency="solo_only_overlap_rejected",
            transfer="same-cell development vectors reused under new queue/order; load dependence unvalidated",
            vector_selection="ordinal cycle preserving all five within-request durations; no fitted distribution",
            failures="success-only realization model; native failures/rejection/expiry not modeled",
            timing="PC policy cost reported separately; simulated D->A constant included in response and lane makespan"),
        denominator_planned=len(requests), denominator_arrived=sum("actual_arrival_ns" in r for r in ledger.values()),
        terminal_counts=counts, response_ready_count=sum(r["response_ns"] is not None for r in ledger.values()),
        late_success_count=sum(r.get("late_success", False) for r in ledger.values()),
        horizon_ns=horizon_ns, complete_drain=complete, makespan_arrival_to_lane_ns=makespan,
        throughput_per_s=len(requests) * 1e9 / makespan if makespan else None,
        ledger=list(ledger.values()), transitions=transitions, decisions=decisions)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--scenario", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    policy.require(not args.output.exists(), "output exists")
    receipt = common.read(args.bundle / "receipt.json")
    for name in ("estimates.json", "realizations.json"):
        policy.require(common.digest(args.bundle / name) == receipt["files"][name], "bundle hash mismatch")
    scenario = common.read(args.scenario)
    result = simulate(common.read(args.bundle / "estimates.json"), common.read(args.bundle / "realizations.json"), **scenario)
    result["input_hashes"] = {str(p): common.digest(p) for p in
                             (args.scenario, args.bundle / "estimates.json", args.bundle / "realizations.json")}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(common.canonical(result))
    print(json.dumps({k: result[k] for k in ("protocol", "denominator_planned", "denominator_arrived",
        "terminal_counts", "complete_drain", "experiment_ready", "performance_pass")}, indent=2))


if __name__ == "__main__":
    main()
