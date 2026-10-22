"""Registered A24 counterfactual simulator; no import-time execution.

Fixed measured-protocol trace arithmetic and generalized rolling simulation are
separate entry points. This candidate commits an atomic ready pair before either
service draw, and never changes a duration when a second owner later arrives.
Original G002 source, model, checkpoints, results and HTML remain untouched.
"""
from __future__ import annotations

import copy
import heapq
import math
import statistics
from collections import defaultdict

from timing_model import (BASELINES, BOUNDARIES, NS, PAIR, ROUTES, SCHEMA,
                          UnsupportedContext, context_of, context_for_route, digest, ns,
                          observed_ready_idle_gaps, protocol_name, public_snapshot,
                          reserve_dispatch, route_of, _whole_vector)

SIM_SCHEMA = "A24-PROTOCOL-SIMULATOR-v1"
POLICIES = (*BASELINES, "FIFO", "EDD", "ATC", "MOBILE_DEADLINE_ENERGY", "FROZEN_RL_REPLAY")


def _time(session, key):
    value = ns(session, key)
    if value is None:
        windows = session.get("planned_windows", {})
        declared = windows.get("service_cutoff_s") if key == "service_stop" else windows.get("sensor_end_s")
        if key in ("service_stop", "drain_stop", "observation_end") and declared is not None:
            value = ns({"declared_s": declared}, "declared")
    if value is None:
        raise ValueError("explicit " + key + " clock/window required")
    return value


def _metrics(rows, service_stop_ns, drain_stop_ns):
    n = len(rows)
    completed = [r for r in rows if r.get("response_ns") is not None and r["response_ns"] <= drain_stop_ns]
    available = [r for r in rows if r.get("available_ns") is not None and r["available_ns"] <= drain_stop_ns]
    ontime = [r for r in completed if r["response_ns"] <= r["deadline_ns"]]
    intervals = [(r["dispatch_ns"], r["available_ns"], r["task"], r["route"])
                 for r in rows if r.get("dispatch_ns") is not None and r.get("available_ns") is not None]
    overlap = sum(max(0, min(a[1], b[1], drain_stop_ns) - max(a[0], b[0]))
                  for i, a in enumerate(intervals) for b in intervals[i + 1:])
    return {"planned": n, "response_completed": len(completed), "AVAILABLE_by_drain": len(available),
            "on_time": len(ontime), "on_time_rate_planned": len(ontime) / n if n else None,
            "late_completed": len(completed) - len(ontime), "response_missing": n - len(completed),
            "incomplete_by_drain": n - len(available), "overlap_ns": overlap,
            "conditional_mean_response_ns": statistics.mean(r["response_ns"] - r["scheduled_arrival_ns"] for r in completed) if completed else None,
            "conditional_mean_queue_ns": statistics.mean(r["dispatch_ns"] - r["queue_entry_ns"] for r in rows
                                                         if r.get("dispatch_ns") is not None) if any(r.get("dispatch_ns") is not None for r in rows) else None,
            "response_boundary": {"C": "output_ready", "D": "persist_complete"},
            "service_stop_ns": service_stop_ns, "drain_stop_ns": drain_stop_ns,
            "missing_is_failure_in_planned_on_time_denominator": True,
            "missing_tardiness_imputed": False}


def replay_measured_protocol(session, baseline=None):
    """Audit original measured arithmetic; this is not a prediction experiment."""
    baseline = baseline or session.get("arm")
    if baseline not in BASELINES:
        raise UnsupportedContext("exact measured baseline arm required")
    if session.get("arm") is not None and session["arm"] != baseline:
        raise ValueError("cannot relabel an observed arm")
    rows, issues = [], []
    for q in session.get("requests", []):
        r = {"request_id": q.get("request_id"), "task": q.get("task"), "route": route_of(q),
             "ordinal": q.get("ordinal"), "scheduled_arrival_ns": ns(q, "scheduled_arrival"),
             "queue_entry_ns": ns(q, "queue_entry"), "dispatch_ns": ns(q, "dispatch"),
             "deadline_ns": ns(q, "deadline"), "response_ns": None,
             "available_ns": ns(q, "available") if ns(q, "available") is not None else ns(q, "lane_available")}
        try:
            vector = _whole_vector(q)
            if r["dispatch_ns"] is None:
                raise ValueError("missing exact dispatch")
            response_i = 1 if r["task"] == "C" else 2
            r["response_ns"] = r["dispatch_ns"] + sum(vector[:response_i + 1])
            r["available_ns"] = r["dispatch_ns"] + sum(vector)
            r["stages_ns"] = vector
        except (ValueError, TypeError) as exc:
            issues.append({"request_id": r["request_id"], "target": "whole_timing", "reason": str(exc)})
        expected = "CPU" if r["task"] == "D" or baseline == "FIFO_SERIAL_CPU" else "GPU"
        if r["route"] != expected:
            issues.append({"request_id": r["request_id"], "target": "route_contract", "reason": "declared baseline route mismatch"})
        rows.append(r)
    events = []
    for r in rows:
        if r["dispatch_ns"] is not None and r["available_ns"] is not None:
            events.extend([(r["dispatch_ns"], 1, r), (r["available_ns"], 0, r)])
    active = {}
    for t, kind, row in sorted(events, key=lambda e: (e[0], e[1], str(e[2]["request_id"]))):
        rid = row["request_id"]
        if kind == 0:
            active.pop(rid, None)
        else:
            labels = {(r["task"], r["route"]) for r in active.values()} | {(row["task"], row["route"])}
            if ((baseline != "FIFO_PAIR_CG" and active) or len(active) >= 2 or
                    any(r["route"] == row["route"] for r in active.values()) or
                    (active and frozenset(labels) != PAIR)):
                issues.append({"request_id": rid, "target": "occupancy", "time_ns": t,
                               "reason": "observed owner trace contradicts baseline/nonpreemptive/max2 contract"})
            active[rid] = row
    gaps, gap_unknown = observed_ready_idle_gaps(session)
    if baseline == "FIFO_WAIT_CG":
        issues.append({"target": "WAIT_contract", "reason": "exact WAIT intent/event audit required; service timings alone do not prove 200ms per eligible group"})
    service, drain = _time(session, "service_stop"), _time(session, "drain_stop")
    metrics = None
    if rows and all(r["deadline_ns"] is not None and r["scheduled_arrival_ns"] is not None for r in rows):
        metrics = _metrics(rows, service, drain)
    else:
        issues.append({"target": "deadline_metrics", "reason": "missing planned arrival/deadline"})
    return {"schema": SIM_SCHEMA, "status": "OBSERVED_ARITHMETIC_ONLY", "arm": baseline,
            "session_id": session.get("session_id"), "requests": rows, "metrics": metrics,
            "ready_idle_gaps": gaps, "redispatch_unknown": gap_unknown, "issues": issues,
            "predictive_accuracy_PASS": None, "new_predictions": 0, "new_environment_STARTs": 0,
            "content_quality_verified": session.get("content_quality_verified", False),
            "causal_or_policy_winner_claim": False}


def _public_row(row):
    return {k: row.get(k) for k in ("request_id", "ordinal", "task", "priority", "group",
                                   "scheduled_arrival_ns", "queue_entry_ns", "deadline_ns")}


def _rule_action(policy, snapshot, rows, model, pair_scope, mobile_energy, allow_busy=False):
    """All ordering and action support are derived from the public queue now."""
    queue = list(snapshot["queue"])
    if not queue or (snapshot["owners"] and (not allow_busy or policy in ("FIFO_SERIAL_CPU", "FIFO_SERIAL_CG", "FIFO_WAIT_CG"))):
        return {"kind": "RESOURCE_WAIT"}
    candidates = []
    for q in queue:
        r = rows[q["request_id"]]
        routes = ("CPU",) if q["task"] == "D" or policy == "FIFO_SERIAL_CPU" else ("GPU",) if policy in BASELINES else ("CPU", "GPU")
        for route in routes:
            active = snapshot["owners"]
            if len(active) >= 2 or any(o["route"] == route for o in active):
                continue
            if active and frozenset({(q["task"], route)} | {(o["task"], o["route"]) for o in active}) != PAIR:
                continue
            if policy in BASELINES and q["request_id"] != min(queue, key=lambda x: (x["scheduled_arrival_ns"], x["ordinal"], x["request_id"]))["request_id"]:
                continue
            try:
                nominal = model.nominal(context_for_route(r["context"], q["task"], route), q["task"], route, state=snapshot)
            except UnsupportedContext:
                continue
            candidates.append((q, route, nominal))
    if not candidates:
        if snapshot["owners"]:
            return {"kind": "RESOURCE_WAIT"}
        raise UnsupportedContext("no supported public nominal route; missing is not zero cost")
    tie = lambda q: (q["scheduled_arrival_ns"], q["ordinal"], q["request_id"])
    mean_occ = statistics.mean(x[2]["occupancy_ns"] for x in candidates)
    def key(item):
        q, route, estimate = item
        route_key = (estimate["response_ns"], estimate["occupancy_ns"], route)
        if policy in ("EDD", "MOBILE_DEADLINE_ENERGY"):
            return (q["deadline_ns"], *tie(q), *route_key)
        if policy == "ATC":
            weight = 2 if q.get("priority") in ("U", "urgent") else 1
            score = math.log(weight / max(estimate["occupancy_ns"] / NS, 1e-12)) - max(q["deadline_ns"] - snapshot["now_ns"] - estimate["response_ns"], 0) / (2 * mean_occ)
            return (-score, *tie(q), *route_key)
        return (*tie(q), *route_key)
    q, route, _ = min(candidates, key=key)
    if policy == "MOBILE_DEADLINE_ENERGY":
        if mobile_energy is None:
            raise UnsupportedContext("MOBILE requires explicitly qualified public energy comparator; timing does not identify Joules")
        safe = [x for x in candidates if x[0]["request_id"] == q["request_id"] and
                snapshot["now_ns"] + x[2]["response_ns"] <= q["deadline_ns"]]
        if safe:
            values = [(mobile_energy(x[0], x[1], x[2], snapshot), x) for x in safe]
            if any(not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0 for v, _ in values):
                raise UnsupportedContext("unknown/nonfinite qualified mobile comparator")
            _, (q, route, _) = min(values, key=lambda x: (x[0], x[1][2]["response_ns"], x[1][1]))
    action = {"kind": "DISPATCH", "request_id": q["request_id"], "route": route}
    if policy == "FIFO_PAIR_CG":
        companion = [x for x in queue if x["request_id"] != q["request_id"] and x["task"] != q["task"]
                     and (pair_scope == "READY_QUEUE" or x.get("group") == q.get("group"))]
        if companion:
            other = min(companion, key=tie)
            action["pair_with"] = other["request_id"]
    return action


def simulate_protocol(template, model, policy="ATC", *, execution_guard=None,
                      scenario_key=None, admission_protocol="SERIAL", redispatch_mode="MEASURED",
                      zero_baseline_id=None, pair_scope="SAME_GROUP", frozen_policy=None,
                      frozen_policy_binding=None, mobile_energy=None, decision_cap=4096,
                      concurrency_mode="ATOMIC_PROTOCOL", unidentified_overlap="ERROR"):
    """One registered environment START; no fitting or NN retraining.

    Required guard is a caller-durable, already-consumed START identity. This
    function cannot enroll experiments or amend global budget ledgers. Exact
    observed replay is the other entry point. This generalized simulator uses
    serial owners or simultaneous ready C_GPU+D_CPU pairs; later joins are an
    unmeasured protocol and are deliberately excluded from its hypothesis.
    """
    if concurrency_mode in ("DATA_DERIVED_PROGRESS", "SERIAL_INDEPENDENT"):
        return simulate_rolling_progress(template, model, policy=policy, execution_guard=execution_guard,
                    scenario_key=scenario_key, admission_protocol=admission_protocol,
                    redispatch_mode=redispatch_mode, zero_baseline_id=zero_baseline_id,
                    pair_scope=pair_scope, frozen_policy=frozen_policy,
                    frozen_policy_binding=frozen_policy_binding, mobile_energy=mobile_energy,
                    decision_cap=decision_cap, concurrency_mode=concurrency_mode,
                    unidentified_overlap=unidentified_overlap)
    if concurrency_mode != "ATOMIC_PROTOCOL":
        raise ValueError("unregistered concurrency mode")
    if (not isinstance(execution_guard, dict) or execution_guard.get("durable_START_consumed") is not True
            or not execution_guard.get("start_id") or not execution_guard.get("registration_sha256")):
        raise RuntimeError("registered durable START must be consumed before simulator execution")
    if policy not in POLICIES or pair_scope not in ("SAME_GROUP", "READY_QUEUE"):
        raise ValueError("unregistered policy/pair scope")
    if policy == "FROZEN_RL_REPLAY":
        binding = frozen_policy_binding or {}
        if (frozen_policy is None or binding.get("replay_only") is not True or
                not binding.get("checkpoint_sha256") or not binding.get("input_contract_sha256")):
            raise UnsupportedContext("frozen checkpoint and exact public input-contract binding required")
    stop, drain, end = (_time(template, k) for k in ("service_stop", "drain_stop", "observation_end"))
    if not 0 < stop <= drain <= end:
        raise ValueError("explicit service/drain/observation windows are inconsistent")
    scenario_key = scenario_key or template.get("session_id")
    if not scenario_key:
        raise ValueError("policy-independent scenario key required")
    calendar, rows, queue, owners, events, decisions = [], {}, set(), {}, [], []
    sequence, now, waited_groups, wait_used, wait_until = 0, 0, set(), 0, 0
    unsupported = []
    def push(t, kind, rid=None, field=None):
        nonlocal sequence
        sequence += 1
        priority = 0 if kind == "AVAILABLE" else 1 if kind == "PHASE" else 2
        heapq.heappush(calendar, (t, priority, sequence, kind, rid, field))
    for q in template.get("requests", []):
        rid = q["request_id"]
        if rid in rows:
            raise ValueError("duplicate planned request")
        arrival, deadline = ns(q, "scheduled_arrival"), ns(q, "deadline")
        if arrival is None or deadline is None or deadline < arrival:
            raise ValueError("exact planned arrival and deadline required")
        context, _ = context_of(template, q, model.strict)
        potential = [scenario_key, q.get("ordinal"), rid]
        admission = model.admission(context, q["task"], potential, protocol=admission_protocol)
        actual = arrival + admission["scheduled_to_actual_ns"]
        entry = actual + admission["actual_to_queue_ns"]
        rows[rid] = {"request_id": rid, "ordinal": q.get("ordinal", len(rows)), "task": q["task"],
                     "priority": q.get("priority"), "group": q.get("group"), "context": context,
                     "scheduled_arrival_ns": arrival, "actual_arrival_ns": actual,
                     "queue_entry_ns": entry, "deadline_ns": deadline, "dispatch_ns": None,
                     "available_ns": None, "response_ns": None, "route": None,
                     "terminal_status": "NOT_DISPATCHED", "admission": admission,
                     "potential_key": potential}
        push(entry, "ENQUEUE", rid)
    push(stop, "SERVICE_STOP")
    push(drain, "DRAIN_STOP")
    push(end, "END")
    while calendar:
        now = calendar[0][0]
        if now > end:
            break
        while calendar and calendar[0][0] == now:
            _, _, _, kind, rid, field = heapq.heappop(calendar)
            if kind == "ENQUEUE":
                queue.add(rid)
            elif kind == "DISPATCH":
                rows[rid]["terminal_status"] = "IN_FLIGHT"
            elif kind == "PHASE":
                rows[rid][field + "_ns"] = now
                boundary = "output_ready" if rows[rid]["task"] == "C" else "persist_complete"
                if field == boundary:
                    rows[rid]["response_ns"] = now
            elif kind == "AVAILABLE":
                route = rows[rid]["route"]
                if owners.get(route, {}).get("request_id") != rid:
                    raise RuntimeError("nonpreemptive owner release mismatch")
                owners.pop(route)
                rows[rid]["available_ns"] = now
                rows[rid]["terminal_status"] = "AVAILABLE"
            events.append({"time_ns": now, "kind": kind, "request_id": rid, "field": field})
        if now >= stop or now < wait_until or owners or not queue:
            continue
        snapshot = public_snapshot({"now_ns": now, "queue": [_public_row(rows[rid]) for rid in queue],
                                    "owners": list(owners.values()), "initial_ap_c": template.get("initial_ap_c"),
                                    "history": {"arrived": sum(r["queue_entry_ns"] <= now for r in rows.values()),
                                                "responded": sum(r.get("response_ns") is not None for r in rows.values())}})
        if len(decisions) >= decision_cap:
            raise RuntimeError("registered decision cap exceeded")
        action = frozen_policy(copy.deepcopy(snapshot)) if policy == "FROZEN_RL_REPLAY" else _rule_action(policy, snapshot, rows, model, pair_scope, mobile_energy)
        decisions.append({"time_ns": now, "public_state": snapshot, "public_state_sha256": digest(snapshot),
                          "action": copy.deepcopy(action)})
        if action.get("kind") == "WAIT":
            dose = action.get("wait_ns")
            if type(dose) is not int or dose <= 0 or wait_used + dose > 12 * NS:
                raise ValueError("WAIT exceeds registered 12s cumulative cap")
            wait_used += dose
            wait_until = min(stop, now + dose)
            push(wait_until, "WAIT_END")
            continue
        if action.get("kind") != "DISPATCH":
            raise UnsupportedContext("no dispatch while idle with a supported queue")
        rid = action.get("request_id")
        if rid not in queue:
            raise ValueError("policy chose future, unavailable or already-owned request")
        head = rows[rid]
        if policy == "FIFO_WAIT_CG" and type(head.get("group")) is int and head["group"] < 16 and head["group"] not in waited_groups and wait_used + 200_000_000 <= 12 * NS:
            waited_groups.add(head["group"])
            wait_used += 200_000_000
            decisions[-1]["applied_control"] = {"kind": "WAIT", "wait_ns": 200_000_000, "group": head["group"]}
            wait_until = min(stop, now + 200_000_000)
            push(wait_until, "WAIT_END")
            continue
        selected = [{"request_id": rid, "task": head["task"], "route": action["route"],
                     "context": context_for_route(head["context"], head["task"], action["route"])}]
        if action.get("pair_with") is not None:
            other = action["pair_with"]
            if other not in queue or other == rid:
                raise ValueError("pair must contain two distinct currently ready requests")
            companion = rows[other]
            selected.append({"request_id": other, "task": companion["task"],
                             "route": "GPU" if companion["task"] == "C" else "CPU",
                             "context": context_for_route(companion["context"], companion["task"], "GPU" if companion["task"] == "C" else "CPU")})
        protocol = "CG_DC" if len(selected) == 2 else "SERIAL"
        reservation = reserve_dispatch(selected, snapshot, protocol)
        overheads = [model.redispatch({**a, "protocol": protocol}, snapshot,
                                     rows[a["request_id"]]["potential_key"], mode=redispatch_mode,
                                     zero_baseline_id=zero_baseline_id) for a in selected]
        if any(g["delay_ns"] is None for g in overheads):
            unsupported.append({"time_ns": now, "reservation_id": reservation.reservation_id,
                                "reason": "redispatch UNKNOWN; no silent zero substitution", "overheads": overheads})
            break
        delay = max(g["delay_ns"] for g in overheads)
        dispatch = now + delay
        if dispatch >= stop:
            unsupported.append({"time_ns": now, "reason": "reserved controller gap reaches service cutoff"})
            break
        # All members use the SAME pre-draw snapshot and prior reservation.
        draws = [model.draw(a, snapshot, protocol, reservation, rows[a["request_id"]]["potential_key"])
                 for a in selected]
        for a, draw, overhead in zip(selected, draws, overheads):
            rid, route = a["request_id"], a["route"]
            r = rows[rid]
            if route in owners or (r["task"], route) not in ROUTES:
                raise RuntimeError("illegal route/owner reservation")
            queue.remove(rid)
            owners[route] = {"request_id": rid, "task": r["task"], "route": route,
                             "dispatch_ns": now, "protocol": protocol, "reservation_id": reservation.reservation_id}
            r.update(route=route, dispatch_ns=dispatch, timing=draw, redispatch=overhead,
                     reserved_at_ns=now, protocol=protocol, reservation_id=reservation.reservation_id,
                     terminal_status="RESERVED")
            push(dispatch, "DISPATCH", rid)
            for boundary in BOUNDARIES:
                t = dispatch + draw["offsets_ns"][boundary]
                push(t, "AVAILABLE" if boundary == "lane_available" else "PHASE", rid,
                     None if boundary == "lane_available" else boundary)
        if len(owners) > 2 or (len(owners) == 2 and frozenset((o["task"], lane) for lane, o in owners.items()) != PAIR):
            raise RuntimeError("max2/CG_DC occupancy invariant")
    result_rows = sorted(rows.values(), key=lambda r: (r["ordinal"], r["request_id"]))
    for r in result_rows:
        if r["terminal_status"] != "AVAILABLE":
            r["terminal_status"] = "INCOMPLETE"
        r.pop("potential_key", None)
    return {"schema": SIM_SCHEMA, "status": "HOLD_UNSUPPORTED_CONTEXT" if unsupported else "COUNTERFACTUAL_COMPLETE_UNVALIDATED",
            "mode": "GENERALIZED_ROLLING_COUNTERFACTUAL_ATOMIC_RESERVATIONS", "policy": policy,
            "start_id": execution_guard["start_id"], "registration_sha256": execution_guard["registration_sha256"],
            "requests": result_rows, "events": events, "decisions": decisions, "unsupported": unsupported,
            "metrics": _metrics(result_rows, stop, drain), "model": copy.deepcopy(model.metadata),
            "frozen_policy_binding": copy.deepcopy(frozen_policy_binding), "new_environment_STARTs": 1,
            "parameter_fits": 0, "NN_training": 0, "predictive_accuracy_PASS": None,
            "pair_scope": pair_scope, "wait_used_ns": wait_used,
            "admission_protocol": protocol_name(admission_protocol), "redispatch_mode": redispatch_mode,
            "hypothesis_limits": ["atomic ready pairs only; midexecution joins require a separately measured protocol",
                                  "a pair and two serial services are different supported timing pools",
                                  "same latent potential across policies only yields the same sample for the same support pool",
                                  "paired members preserve each whole vector; cross-member latent correlation is not identified",
                                  "no thermal feedback, device Joules, policy winner, or physical goal PASS"]}


def simulate_rolling_progress(template, model, policy="ATC", *, execution_guard=None,
                              scenario_key=None, admission_protocol="SERIAL", redispatch_mode="MEASURED",
                              zero_baseline_id=None, pair_scope="READY_QUEUE", frozen_policy=None,
                              frozen_policy_binding=None, mobile_energy=None, decision_cap=4096,
                              concurrency_mode="DATA_DERIVED_PROGRESS", unidentified_overlap="ERROR"):
    """Predict unmeasured arrival/order/route/overlap/WAIT combinations causally.

    A whole SERIAL vector supplies five latent work thresholds. Public current
    occupancy determines the next progress rate. Midexecution joins and leaves
    change only remaining work; no completed phase timestamp is rewritten.
    Observed stage ratios are a diagnostic association, with explicit independent
    baseline/fallback choices. No already-realized overlap selects a latent pool.
    """
    if (not isinstance(execution_guard, dict) or execution_guard.get("durable_START_consumed") is not True
            or not execution_guard.get("start_id") or not execution_guard.get("registration_sha256")):
        raise RuntimeError("registered durable START required")
    if policy not in POLICIES or concurrency_mode not in ("DATA_DERIVED_PROGRESS", "SERIAL_INDEPENDENT"):
        raise ValueError("unregistered policy/progress mode")
    if policy == "FROZEN_RL_REPLAY":
        binding = frozen_policy_binding or {}
        if frozen_policy is None or binding.get("replay_only") is not True or not binding.get("checkpoint_sha256") or not binding.get("input_contract_sha256"):
            raise UnsupportedContext("pinned frozen RL checkpoint/public contract required; NN retraining disabled")
    stop, drain, end = (_time(template, k) for k in ("service_stop", "drain_stop", "observation_end"))
    if not 0 < stop <= drain <= end:
        raise ValueError("inconsistent explicit windows")
    scenario_key = scenario_key or template.get("session_id")
    if not scenario_key:
        raise ValueError("policy-independent scenario key required")
    rows, queue, owners, events, decisions, unknown, rate_log = {}, set(), {}, [], [], [], []
    external, sequence = [], 0
    def push(t, kind, rid=None):
        nonlocal sequence
        sequence += 1
        heapq.heappush(external, (t, sequence, kind, rid))
    for q in template.get("requests", []):
        rid, arrival, deadline = q["request_id"], ns(q, "scheduled_arrival"), ns(q, "deadline")
        if rid in rows or arrival is None or deadline is None or deadline < arrival:
            raise ValueError("unique requests with exact public arrival/deadline required")
        context, _ = context_of(template, q, model.strict)
        potential = [scenario_key, q.get("ordinal"), rid]
        admission = model.admission(context, q["task"], potential, protocol=admission_protocol)
        actual = arrival + admission["scheduled_to_actual_ns"]
        entry = actual + admission["actual_to_queue_ns"]
        rows[rid] = {"request_id": rid, "ordinal": q.get("ordinal", len(rows)), "task": q["task"],
                     "priority": q.get("priority"), "group": q.get("group"), "context": context,
                     "scheduled_arrival_ns": arrival, "actual_arrival_ns": actual, "queue_entry_ns": entry,
                     "deadline_ns": deadline, "dispatch_ns": None, "response_ns": None,
                     "available_ns": None, "route": None, "terminal_status": "NOT_DISPATCHED",
                     "admission": admission, "potential_key": potential}
        push(entry, "ENQUEUE", rid)
    for t, kind in ((stop, "SERVICE_STOP"), (drain, "DRAIN_STOP"), (end, "END")):
        push(t, kind)
    now, wait_until, wait_used, waited_groups = 0, 0, 0, set()
    def snapshot():
        return public_snapshot({"now_ns": now, "queue": [_public_row(rows[x]) for x in queue],
                "owners": [{"request_id": o["request_id"], "task": o["task"], "route": route,
                            "dispatch_ns": min(now, o["start_ns"]) if now >= o["start_ns"] else o["reserved_at_ns"],
                            "reservation_id": o["commitment"], "protocol": "ROLLING_PROGRESS"}
                           for route, o in owners.items()], "initial_ap_c": template.get("initial_ap_c"),
                "history": {"arrived": sum(r["queue_entry_ns"] <= now for r in rows.values()),
                            "responded": sum(r["response_ns"] is not None for r in rows.values())}})
    def settle():
        # Complete all zero/finished stages at this event before changing rates.
        for route, o in list(owners.items()):
            if o["start_ns"] > now:
                continue
            r = rows[o["request_id"]]
            while o["remaining_work_ns"] <= 1e-7:
                boundary = BOUNDARIES[o["stage"]]
                r[boundary + "_ns"] = now
                events.append({"time_ns": now, "kind": boundary.upper(), "request_id": o["request_id"]})
                if boundary == ("output_ready" if r["task"] == "C" else "persist_complete"):
                    r["response_ns"] = now
                o["stage"] += 1
                if o["stage"] == 5:
                    r["available_ns"] = now
                    r["terminal_status"] = "AVAILABLE"
                    owners.pop(route)
                    break
                o["remaining_work_ns"] = float(r["timing"]["stages_ns"][o["stage"]])
    while now <= end:
        while external and external[0][0] == now:
            _, _, kind, rid = heapq.heappop(external)
            if kind == "ENQUEUE":
                queue.add(rid)
            elif kind == "DISPATCH":
                rows[rid]["terminal_status"] = "IN_FLIGHT"
            events.append({"time_ns": now, "kind": kind, "request_id": rid})
        settle()
        micro = 0
        while now < stop and now >= wait_until and queue:
            micro += 1
            if micro > len(rows) + 4 or len(decisions) >= decision_cap:
                raise RuntimeError("registered decision/microstep cap exceeded")
            public = snapshot()
            action = frozen_policy(copy.deepcopy(public)) if policy == "FROZEN_RL_REPLAY" else _rule_action(policy, public, rows, model, pair_scope, mobile_energy, allow_busy=True)
            if action.get("kind") == "RESOURCE_WAIT":
                break
            decisions.append({"time_ns": now, "public_state": public, "public_state_sha256": digest(public), "action": copy.deepcopy(action)})
            if action.get("kind") == "WAIT":
                dose = action.get("wait_ns")
                if type(dose) is not int or dose <= 0 or wait_used + dose > 12 * NS:
                    raise ValueError("illegal WAIT")
                wait_used += dose
                wait_until = min(stop, now + dose)
                push(wait_until, "WAIT_END")
                break
            if action.get("kind") != "DISPATCH" or action.get("request_id") not in queue:
                raise ValueError("invalid/future action")
            rid, route = action["request_id"], action["route"]
            r = rows[rid]
            if policy == "FIFO_WAIT_CG" and type(r.get("group")) is int and r["group"] < 16 and r["group"] not in waited_groups and wait_used + 200_000_000 <= 12 * NS:
                waited_groups.add(r["group"])
                wait_used += 200_000_000
                wait_until = min(stop, now + 200_000_000)
                decisions[-1]["applied_control"] = {"kind": "WAIT", "wait_ns": 200_000_000}
                push(wait_until, "WAIT_END")
                break
            labels = {(o["task"], lane) for lane, o in owners.items()} | {(r["task"], route)}
            if (r["task"], route) not in ROUTES or route in owners or len(owners) >= 2 or (owners and frozenset(labels) != PAIR):
                raise ValueError("nonpreemptive/max2/CG_DC action violation")
            selected = {"request_id": rid, "task": r["task"], "route": route,
                        "context": context_for_route(r["context"], r["task"], route)}
            commitment = digest(["ROLLING_PROGRESS", public, selected])
            # Commitment exists before selecting overhead and latent work.
            overhead = model.redispatch({**selected, "protocol": "CG_DC" if owners else "SERIAL"}, public,
                                       r["potential_key"], mode=redispatch_mode, zero_baseline_id=zero_baseline_id)
            if overhead["delay_ns"] is None:
                unknown.append({"time_ns": now, "request_id": rid, "evidence": overhead["evidence"]})
                break
            start = now + overhead["delay_ns"]
            if start >= stop:
                unknown.append({"time_ns": now, "request_id": rid, "evidence": "redispatch reaches service stop"})
                break
            draw = model.draw_latent_serial(selected, public, r["potential_key"])
            queue.remove(rid)
            r.update(route=route, dispatch_ns=start, reserved_at_ns=now, timing=draw, redispatch=overhead,
                     execution_context=selected["context"], commitment_sha256=commitment, terminal_status="RESERVED")
            owners[route] = {"request_id": rid, "task": r["task"], "start_ns": start,
                             "reserved_at_ns": now, "commitment": commitment,
                             "stage": 0, "remaining_work_ns": float(draw["stages_ns"][0]), "rate": 1.}
            if start == now:
                r["terminal_status"] = "IN_FLIGHT"
                events.append({"time_ns": now, "kind": "DISPATCH", "request_id": rid})
            else:
                push(start, "DISPATCH", rid)
            settle()
        if unknown:
            break
        if now == end:
            break
        public = snapshot()
        executing = {(o["task"], lane) for lane, o in owners.items() if o["start_ns"] <= now}
        overlap = frozenset(executing) == PAIR
        for route, o in owners.items():
            r = rows[o["request_id"]]
            if overlap and o["start_ns"] <= now:
                rates = model.progress_rates({"task": r["task"], "route": route, "context": r["execution_context"]}, public,
                                             mode=concurrency_mode, unidentified=unidentified_overlap)
            else:
                rates = {"rates": [1.] * 5, "evidence": "PUBLIC_SERIAL_OCCUPANCY"}
            o["rate"] = rates["rates"][o["stage"]]
            if not math.isfinite(o["rate"]) or o["rate"] <= 0:
                raise UnsupportedContext("invalid observed progress rate")
            rate_log.append({"time_ns": now, "request_id": o["request_id"], "stage": o["stage"],
                             "rate": o["rate"], "public_overlap": overlap, "evidence": rates})
        next_times = [external[0][0]] if external else [end]
        for o in owners.values():
            if o["start_ns"] > now:
                next_times.append(o["start_ns"])
            else:
                next_times.append(now + max(1, math.ceil(o["remaining_work_ns"] / o["rate"] - 1e-9)))
        next_time = min(t for t in next_times if t > now)
        next_time = min(next_time, end)
        for o in owners.values():
            if o["start_ns"] <= now:
                o["remaining_work_ns"] = max(0., o["remaining_work_ns"] - (next_time - now) * o["rate"])
        now = next_time
    allrows = sorted(rows.values(), key=lambda r: (r["ordinal"], r["request_id"]))
    for r in allrows:
        r.pop("potential_key", None)
        if r["terminal_status"] != "AVAILABLE":
            r["terminal_status"] = "INCOMPLETE"
    return {"schema": SIM_SCHEMA, "status": "HOLD_UNKNOWN_REDISPATCH" if unknown else "COUNTERFACTUAL_COMPLETE_UNVALIDATED",
            "mode": concurrency_mode, "policy": policy, "start_id": execution_guard["start_id"],
            "registration_sha256": execution_guard["registration_sha256"], "requests": allrows,
            "metrics": _metrics(allrows, stop, drain), "events": events, "decisions": decisions,
            "rate_history": rate_log, "unknown": unknown, "wait_used_ns": wait_used,
            "model": copy.deepcopy(model.metadata), "frozen_policy_binding": copy.deepcopy(frozen_policy_binding),
            "new_environment_STARTs": 1, "parameter_fits": 0, "NN_training": 0,
            "predictive_accuracy_PASS": None, "causal_interference_identified": False,
            "unidentified_overlap": unidentified_overlap,
            "hypothesis_limits": ["unmeasured action combinations are predictions, not measured protocol reproduction",
                                  "whole SERIAL vector is a latent work coordinate; realized stages are progress-integrated",
                                  "stage-rate transfer is observational and requires grouped out-of-session validation",
                                  "integer event ceiling contributes at most one ns per completed stage",
                                  "new arrival/order/deadline/WAIT combinations are allowed with public-state causal dispatch",
                                  "bank transfer only under explicit TASK_BINDING_TRANSFER and same nonbank bindings",
                                  "no invented thermal feedback or identified device energy"]}


def score_heldout_simulation(prediction, measured_session):
    """Compare independently simulated full template; keep every missing row."""
    observed = {q["request_id"]: q for q in measured_session.get("requests", [])}
    arm_matches = measured_session.get("arm") == prediction.get("policy")
    rows = []
    for predicted in prediction["requests"]:
        actual = observed.get(predicted["request_id"])
        row = {"request_id": predicted["request_id"], "status": "UNVALIDATED",
               "queue_error_ns": None, "response_error_ns": None, "on_time_disagreement": None}
        if actual is not None and arm_matches:
            dispatch, queue = ns(actual, "dispatch"), ns(actual, "queue_entry")
            response = ns(actual, "output_ready" if actual["task"] == "C" else "persist_complete")
            deadline = ns(actual, "deadline")
            if dispatch is not None and queue is not None and predicted.get("dispatch_ns") is not None:
                row["queue_error_ns"] = (predicted["dispatch_ns"] - predicted["queue_entry_ns"]) - (dispatch - queue)
            if response is not None and predicted.get("response_ns") is not None:
                row["response_error_ns"] = predicted["response_ns"] - response
            if deadline is not None and response is not None and predicted.get("response_ns") is not None:
                row["on_time_disagreement"] = int((predicted["response_ns"] <= predicted["deadline_ns"]) != (response <= deadline))
            if all(row[k] is not None for k in ("queue_error_ns", "response_error_ns", "on_time_disagreement")):
                row["status"] = "POSTHOC_DEVELOPMENT_PREDICTION"
        rows.append(row)
    actual_intervals = [(ns(q, "dispatch"), ns(q, "available") if ns(q, "available") is not None else ns(q, "lane_available"))
                        for q in observed.values()]
    overlap = None
    if arm_matches and all(a is not None and b is not None and a <= b for a, b in actual_intervals):
        drain = _time(measured_session, "drain_stop")
        overlap = sum(max(0, min(a[1], b[1], drain) - max(a[0], b[0]))
                      for i, a in enumerate(actual_intervals) for b in actual_intervals[i + 1:])
    valid_queue = [r["queue_error_ns"] for r in rows if r["queue_error_ns"] is not None]
    valid_response = [r["response_error_ns"] for r in rows if r["response_error_ns"] is not None]
    valid_ontime = [r["on_time_disagreement"] for r in rows if r["on_time_disagreement"] is not None]
    return {"schema": SIM_SCHEMA + "-HELDOUT", "session_id": measured_session.get("session_id"),
            "cohort_id": measured_session.get("cohort_id"), "bank": measured_session.get("bank"),
            "matching_measured_policy_arm": arm_matches,
            "unsupported_target": None if arm_matches else "COUNTERFACTUAL_POLICY_HAS_NO_MATCHING_MEASURED_ARM",
            "source_generation": measured_session.get("source_generation"),
            "queue_mae_ns": statistics.mean(abs(x) for x in valid_queue) if valid_queue else None,
            "response_mae_ns": statistics.mean(abs(x) for x in valid_response) if valid_response else None,
            "on_time_disagreement_count": sum(valid_ontime), "on_time_eligible": len(valid_ontime),
            "overlap_error_ns": prediction["metrics"]["overlap_ns"] - overlap if overlap is not None else None,
            "rows": rows, "missing_observed_requests": sorted(set(observed) - {r["request_id"] for r in prediction["requests"]}),
            "independent_simulation_start_id": prediction["start_id"],
            "predictive_accuracy_PASS": None, "causal_claim": False}


def paired_validation_summary(candidate_scores, baseline_scores):
    """Same whole heldout sessions, paired signs and every adverse stratum.

    Missing predictions remain UNKNOWN; they never disappear from denominators.
    This reports development evidence and cannot select a model or policy winner.
    """
    baseline = {r["session_id"]: r for r in baseline_scores}
    pairs, strata = [], defaultdict(list)
    for candidate in candidate_scores:
        old = baseline.get(candidate["session_id"])
        row = {"session_id": candidate["session_id"], "cohort_id": candidate.get("cohort_id"),
               "stratum": (candidate.get("bank"), candidate.get("source_generation")),
               "status": "UNVALIDATED", "response_mae_change_ns": None, "queue_mae_change_ns": None}
        if old is not None:
            for target in ("response_mae", "queue_mae"):
                a, b = candidate.get(target + "_ns"), old.get(target + "_ns")
                if a is not None and b is not None:
                    row[target + "_change_ns"] = a - b
            if row["response_mae_change_ns"] is not None and row["queue_mae_change_ns"] is not None:
                row["status"] = "POSTHOC_PAIRED_DEVELOPMENT"
        pairs.append(row)
        strata[row["stratum"]].append(row)
    summaries = []
    for key, values in strata.items():
        errors = [r["response_mae_change_ns"] for r in values if r["response_mae_change_ns"] is not None]
        summaries.append({"stratum": key, "whole_sessions": len(values), "eligible_pairs": len(errors),
                          "unknown_pairs": len(values) - len(errors),
                          "mean_response_mae_change_ns": statistics.mean(errors) if errors else None,
                          "worse_signs": sum(x > 0 for x in errors), "better_signs": sum(x < 0 for x in errors),
                          "ties": sum(x == 0 for x in errors), "worst_harm_ns": max(errors) if errors else None})
    return {"schema": SIM_SCHEMA + "-PAIRED-CV", "pairs": pairs, "strata": summaries,
            "baseline_only_missing_candidate_sessions": sorted(set(baseline) - {r["session_id"] for r in candidate_scores}),
            "worst_stratum_change_ns": max((s["mean_response_mae_change_ns"] for s in summaries
                                             if s["mean_response_mae_change_ns"] is not None), default=None),
            "confidence_interval": None, "model_or_policy_selection": None,
            "predictive_accuracy_PASS": None, "independence_unit": "whole cohort; summaries descriptive"}
