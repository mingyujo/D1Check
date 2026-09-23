"""Read-only PC replay of arrival-timing-dev-v1; NOT a device or experiment gate."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

PROTOCOL = "arrival-timing-dev-v1"
POLICY = "CONDITIONAL_TIMING_DEV_1"
CONTRACT = "arrival-phase-budgets-v1"
CAL_PROTOCOL = "arrival-timing-calibration-v1"
CAL_POLICY = "CALIBRATION_FIXED_BACKEND_1"
FIELDS = ("dispatch_to_start_ns", "start_to_output_ready_ns", "output_ready_to_persist_ns",
          "persist_to_lane_available_ns")
DECISION_FIELD = "decision_to_dispatch_ns"
ALL_FIELDS = (DECISION_FIELD,) + FIELDS
KEYS = {f"{task}_{backend}" for task in ("classification", "detection") for backend in ("CPU", "GPU")}
PHASES = ("AVAILABLE", "ASSIGNED", "EXECUTING", "OUTPUT_READY", "PERSISTED", "WORKER_RELEASED")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def integer(value):
    return type(value) is int and value >= 0


def check_budgets(budgets):
    require(set(budgets) == KEYS, "exact four task/backend budget keys required")
    for key, value in budgets.items():
        require(set(value) == set(ALL_FIELDS), f"unexpected phase/future field: {key}")
        require(all(x is None or integer(x) and x <= 20_000_000_000 for x in value.values()), "invalid budget")
    return [f"{k}.{f}" for k in sorted(KEYS) for f in ALL_FIELDS if budgets[k][f] is None]


def check_estimates(config):
    require(set(config) == {"contract", "version", "provenance", "budgets"}, "estimate fields")
    require(config["contract"] == CONTRACT and bool(config["version"]) and bool(config["provenance"]), "estimate identity")
    return {"configuration_valid": True, "missing_budgets": check_budgets(config["budgets"]),
            "experiment_ready": False, "reason": "development_only; calibration and device verification required"}


def nullable_sum(values):
    return None if any(x is None for x in values) else sum(values)


def remaining(lane, now, budgets, backend):
    require(lane["phase_since_ns"] <= now, "future phase observation")
    if lane["phase"] == "AVAILABLE":
        return 0, "AVAILABLE"
    index = {"ASSIGNED": 0, "EXECUTING": 1, "OUTPUT_READY": 2, "PERSISTED": 3, "WORKER_RELEASED": 3}[lane["phase"]]
    budget = budgets.get(f'{lane["task"]}_{backend}')
    origin = lane["persist_since_ns"] if index == 3 else lane["phase_since_ns"]
    if budget is None or origin is None or budget[FIELDS[index]] is None:
        return None, "UNKNOWN_MISSING_BUDGET"
    require(origin <= now, "future persistence observation")
    left = budget[FIELDS[index]] - (now - origin)
    if left <= 0:
        return None, "UNKNOWN_OVERRUN"
    total = nullable_sum([left] + [budget[f] for f in FIELDS[index + 1:]])
    return total, "UNKNOWN_MISSING_BUDGET" if total is None else "ESTIMATED"


def replay(queue, lanes, now, budgets, calibration_backend=None):
    """Inputs contain observations and development budgets only, never actual future outcomes."""
    free_cpu, free_gpu = (lanes[b]["phase"] == "AVAILABLE" for b in ("CPU", "GPU"))
    if calibration_backend is not None:
        require(calibration_backend in ("CPU", "GPU"), "calibration backend")
        reason = "wait_empty" if not queue else "wait_calibration_solo_busy" if not (free_cpu and free_gpu) else "calibration_fixed_backend"
        return {"selected": {"request_id": queue[0]["id"], "backend": calibration_backend} if reason == "calibration_fixed_backend" else None,
                "reason": reason, "candidates": []}
    residual = remaining(lanes["CPU"], now, budgets, "CPU")[0]
    ahead, selected, selected_reason, candidates = 0, None, None, []
    for ticket in queue:
        cb, gb = (budgets[f'{ticket["task"]}_{b}'] for b in ("CPU", "GPU"))
        stop = 2 if ticket["priority"] == "urgent" else 3
        c = nullable_sum([residual, ahead, cb[DECISION_FIELD], nullable_sum([cb[f] for f in FIELDS[:stop]])])
        g = nullable_sum([gb[DECISION_FIELD]] + [gb[f] for f in FIELDS[:stop]]) if free_gpu else None
        if not free_cpu and not free_gpu:
            reason = "wait_both_busy"
        elif c is None or free_gpu and g is None:
            reason = "fallback_cpu_unknown" if free_cpu else "wait_unknown"
        elif free_cpu and (not free_gpu or c <= g):
            reason = "estimated_cpu_reply"
        elif free_gpu and g < c:
            reason = "estimated_gpu_reply"
        else:
            reason = "wait_estimated_cpu"
        if selected is None and reason in ("fallback_cpu_unknown", "estimated_cpu_reply", "estimated_gpu_reply"):
            selected = {"request_id": ticket["id"], "backend": "GPU" if reason == "estimated_gpu_reply" else "CPU"}
            selected_reason = reason
        candidates.append({"request_id": ticket["id"], "cpu_reply_ns": c, "gpu_reply_ns": g, "reason": reason})
        ahead = nullable_sum([ahead, nullable_sum([cb[f] for f in ALL_FIELDS])])
    return {"selected": selected, "reason": selected_reason or (candidates[0]["reason"] if candidates else "wait_empty"),
            "candidates": candidates}


def validate_trace(trace):
    calibration = trace["protocol"] == CAL_PROTOCOL
    extra = {"calibration_backend"} if calibration else set()
    require(set(trace) == {"protocol", "policy", "estimate_contract", "estimate_version", "estimate_provenance",
                          "budgets", "capacity", "clock", "overflow", "dropped_records", "complete", "records", "experiment_ready"} | extra, "trace fields")
    require((trace["protocol"], trace["policy"]) in ((PROTOCOL, POLICY), (CAL_PROTOCOL, CAL_POLICY)), "not timing-dev; retain legacy validator for v1")
    if calibration:
        require(trace["calibration_backend"] in ("CPU", "GPU") and all(x is None for b in trace["budgets"].values() for x in b.values()), "calibration must not use estimates")
    require(trace["clock"] == "elapsedRealtimeNanos" and trace["experiment_ready"] is False, "clock/readiness contract")
    check_estimates({"contract": trace["estimate_contract"], "version": trace["estimate_version"],
                     "provenance": trace["estimate_provenance"], "budgets": trace["budgets"]})
    require(trace["complete"] is True and trace["overflow"] is False and trace["dropped_records"] == 0, "incomplete/lost trace")
    require(integer(trace["capacity"]) and 0 < trace["capacity"] <= 512 and 0 < len(trace["records"]) <= trace["capacity"], "trace capacity")
    lanes = {b: {"phase": "AVAILABLE", "request_id": None, "task": None, "phase_since_ns": 0, "persist_since_ns": None}
             for b in ("CPU", "GPU")}
    tickets, dispatched, phases, assignments, selections = {}, set(), {}, {}, {}
    last, pending, decisions, waits = 0, None, 0, 0
    for seq, record in enumerate(trace["records"]):
        time = record["mono_ns"]
        require(record["seq"] == seq and integer(time) and time >= last, "record sequence/time")
        last = time
        if record["kind"] == "phase":
            require(set(record) == {"seq", "kind", "mono_ns", "backend", "request_id", "phase"}, "phase fields")
            backend, rid, phase = record["backend"], record["request_id"], record["phase"]
            require(backend in lanes and phase in PHASES, "phase/lane")
            old = lanes[backend]
            if phase == "ASSIGNED":
                require(pending == {"request_id": rid, "backend": backend} and old["phase"] == "AVAILABLE", "unlogged/double dispatch")
                require(rid not in dispatched, "duplicate dispatch")
                dispatched.add(rid)
                assignments[rid] = backend
                pending = None
            else:
                require(old["request_id"] == rid and old["phase"] != "AVAILABLE", "stale release/phase")
                require(phase == "WORKER_RELEASED" or phase == "AVAILABLE" and old["phase"] == "WORKER_RELEASED"
                        or PHASES.index(phase) == PHASES.index(old["phase"]) + 1, "illegal phase order")
            require((rid, phase) not in phases, "duplicate phase")
            phases[rid, phase] = time
            lanes[backend] = {"phase": phase, "request_id": None if phase == "AVAILABLE" else rid,
                              "task": None if phase == "AVAILABLE" else tickets[rid]["task"], "phase_since_ns": time,
                              "persist_since_ns": time if phase == "PERSISTED" else None if phase in ("ASSIGNED", "AVAILABLE") else old["persist_since_ns"]}
        else:
            require(record["kind"] == "decision" and set(record) == {"seq", "kind", "mono_ns", "decision_end_ns", "queue", "estimate_version", "lanes", "candidates", "reason", "selected"}, "decision fields/future input")
            require(pending is None and integer(record["decision_end_ns"]) and record["decision_end_ns"] >= time, "decision/dispatch order")
            last = record["decision_end_ns"]
            require(record["estimate_version"] == trace["estimate_version"] and set(record["lanes"]) == set(lanes), "snapshot identity")
            queue = record["queue"]
            require(len({t["id"] for t in queue}) == len(queue), "duplicate queue entry")
            for ticket in queue:
                require(set(ticket) == {"id", "task", "priority", "ordinal"} and integer(ticket["ordinal"]), "queue fields")
                require(ticket["task"] in ("classification", "detection") and ticket["priority"] in ("urgent", "normal"), "ticket type")
                require(ticket["id"] not in dispatched and tickets.get(ticket["id"], ticket) == ticket, "ticket mutation/already dispatched")
                tickets[ticket["id"]] = ticket
            require(queue == sorted(queue, key=lambda t: (t["priority"] != "urgent", t["ordinal"], t["id"])), "queue order")
            for backend, lane in lanes.items():
                residual, state = remaining(lane, time, trace["budgets"], backend)
                require(record["lanes"][backend] == dict(lane, remaining_ns=residual, remaining_state=state), "lane snapshot/residual mismatch")
            expected = replay(queue, lanes, time, trace["budgets"], trace.get("calibration_backend"))
            require(all(record[k] == v for k, v in expected.items()), "decision replay mismatch")
            pending = expected["selected"]
            if pending is not None:
                selections[pending["request_id"]] = record
            decisions += 1
            waits += pending is None
    require(pending is None and all(l["phase"] == "AVAILABLE" for l in lanes.values())
            and set(tickets) == dispatched, "trace not drained")
    return {"decisions": decisions, "no_selection": waits, "dispatched": len(dispatched), "phases": phases,
            "tickets": tickets, "assignments": assignments, "selections": selections}


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def validate_artifacts(root):
    root = Path(root)
    trace, manifest, rows = (read(root / name) for name in ("decision_trace.json", "manifest.json", "requests.json"))
    result = validate_trace(trace)
    require(manifest["protocol"] == trace["protocol"] and manifest["policy"] == trace["policy"] and manifest["development_only"] is True
            and manifest["experiment_ready"] is False, "manifest namespace")
    if trace["protocol"] == CAL_PROTOCOL:
        require(manifest["calibration_backend"] == trace["calibration_backend"] and manifest["maximum_concurrency"] == 1
                and manifest["execution_purpose"] == "boundary_calibration_only" and manifest["storage_mode"] == "persist_all"
                and manifest["observation_contract"] == "arrival-phase-observations-v2", "calibration mode")
    config = manifest["timing_estimates"]
    check_estimates(config)
    require(config == {"contract": trace["estimate_contract"], "version": trace["estimate_version"],
                       "provenance": trace["estimate_provenance"], "budgets": trace["budgets"]}, "estimate manifest mismatch")
    planned = {q["request_id"]: q for q in manifest["requests"]}
    require(len(planned) == len(manifest["requests"]) == len(rows) == result["dispatched"], "request denominator")
    # Current Activity pumps once per enqueue and lane-available callback; each selection adds one loop.
    require(result["decisions"] == 3 * len(rows) and result["no_selection"] == 2 * len(rows), "missing policy call records")
    require({r["request_id"] for r in rows} == set(planned), "request identity")
    counts = {}
    phase_fields = dict(zip(PHASES[1:] + ("AVAILABLE",),
                           ("dispatch_ns", "execution_start_ns", "output_ready_ns", "persist_complete_ns", "worker_release_ns", "lane_available_ns")))
    for row in rows:
        rid = row["request_id"]
        q = planned[rid]
        require(result["tickets"][rid] == {"id": rid, "task": q["task_id"], "priority": q["priority"], "ordinal": q["ordinal"]}, "planned ticket identity")
        require(row["protocol"] == trace["protocol"] and row["session_id"] == manifest["session_id"], "ledger namespace")
        require(row["selected_backend"] == result["assignments"][rid], "selected lane identity")
        decision = result["selections"][rid]
        evaluation_ns = decision["decision_end_ns"] - decision["mono_ns"]
        require(row["decision_reason"] == decision["reason"] and row["policy_evaluation_ns"] == evaluation_ns
                and integer(row["policy_compute_ns"]) and row["policy_compute_ns"] >= evaluation_ns, "policy reason/cost boundary")
        require(all(row[k] == q[k] for k in ("task_id", "priority", "ordinal", "sample_id")), "ledger identity")
        for phase, field in phase_fields.items():
            require(row.get(field) == result["phases"].get((rid, phase)), f"phase boundary: {rid}/{field}")
        status = row["terminal_status"]
        require(status in ("succeeded", "failed", "rejected", "expired"), "unfinished denominator")
        counts[status] = counts.get(status, 0) + 1
        fields = ["actual_arrival_ns", "queue_entry_ns", "dispatch_ns", "execution_start_ns", "inference_start_ns",
                  "inference_end_ns", "output_ready_ns", "persist_complete_ns", "worker_release_ns", "lane_available_ns"]
        if status == "succeeded":
            require(all(f in row for f in fields), "missing successful boundary")
            require(row["inference_ns"] == row["inference_end_ns"] - row["inference_start_ns"], "host API interval")
            completion = row["output_ready_ns" if row["priority"] == "urgent" else "persist_complete_ns"]
            require(row["completion_ns"] == completion and row["response_ns"] == completion - row["scheduled_arrival_ns"], "response boundary")
        require(("inference_start_ns" in row) == ("inference_end_ns" in row), "incomplete host interval")
        times = [row[f] for f in fields if f in row]
        require(all(integer(t) for t in times) and times == sorted(times), "timestamp order")
        event = read(root / f"{rid}.event.json")
        require(event == {k: v for k, v in row.items() if k != "lane_available_ns"}, "worker event vs final ledger")
    by_id = {r["request_id"]: r for r in rows}
    for record in trace["records"]:
        if record["kind"] != "decision":
            continue
        now = record["mono_ns"]
        observed = {t["id"] for t in record["queue"]}
        for rid, row in by_id.items():
            # Equal clock ticks cannot order separate events; the serialized snapshot resolves ties.
            if row["queue_entry_ns"] < now < row["dispatch_ns"]:
                require(rid in observed, "missing queued input")
            if rid in observed:
                require(row["queue_entry_ns"] <= now <= row["dispatch_ns"], "future/already dispatched request")
    summary, cleanup = (read(root / name) for name in ("summary.json", "cleanup.json"))
    require(summary["protocol"] == trace["protocol"] and summary["session_id"] == manifest["session_id"]
            and summary["request_count"] == len(rows) and summary["terminal_count"] == len(rows), "summary denominator")
    return {k: result[k] for k in ("decisions", "no_selection", "dispatched")} | {
        "trace_replay": "PASS", "terminal_counts": counts, "session_status": summary["status"],
        "cleanup_status": cleanup["status"], "experiment_ready": False,
        "scope": "timing/replay only; not model quality, GPU delegate, memory or thermal validation"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check-estimates", type=Path)
    group.add_argument("--artifacts", type=Path)
    args = parser.parse_args()
    result = check_estimates(read(args.check_estimates)) if args.check_estimates else validate_artifacts(args.artifacts)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
