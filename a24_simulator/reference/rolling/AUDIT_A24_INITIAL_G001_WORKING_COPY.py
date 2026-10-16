"""Independent saved A24 result, public-input and optional NN/cost audits.

Import executes no environment, neural network, CostState or optimizer. The
main audit uses saved raw records plus a fixed DEV-only profile; it never calls
the event engine or its metrics helper. Optional numeric/NN functions must be
called only after their cost/inference work is registered by the parent runner.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path

import numpy as np

NS = 1_000_000_000
PHASE_EVENT = {
    "EXECUTION_START": "execution_start_ns", "HOST_INFERENCE_START": "host_inference_start_ns",
    "HOST_INFERENCE_RETURN": "host_inference_return_ns", "OUTPUT_READY": "output_ready_ns",
    "PERSIST_COMPLETE": "persist_complete_ns", "READBACK_START": "readback_start_ns",
    "READBACK_COMPLETE": "readback_end_ns", "RESPONSE": "response_ns",
    "WORKER_RELEASE": "worker_release_ns", "AVAILABLE": "lane_available_ns",
}
UNKNOWN = ("host_inference_start_ns", "host_inference_return_ns", "readback_start_ns", "readback_end_ns")
CHAIN = ("dispatch_ns", "execution_start_ns", "output_ready_ns", "persist_complete_ns", "worker_release_ns", "lane_available_ns")
COHORTS = ("ALL", "U", "N", "C", "D", "CU", "CN", "DU", "DN")
PUBLIC_QUEUE = {"request_id", "ordinal", "task", "priority", "scheduled_arrival_ns", "deadline_ns", "burst_index"}
PUBLIC_OWNER = {"request_id", "task", "priority", "dispatch_ns", "phase_index"}
PUBLIC_ESTIMATE = {"occupancy_ns", "response_ns", "energy_proxy_j"}
INPUTS = ("requests", "resources", "global_state", "features", "request_index", "backend_index", "mask")


class AuditError(ValueError):
    pass


def _require(ok, message):
    if not bool(ok):
        raise AuditError(message)


def _digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _unwire(value, key=""):
    if isinstance(value, dict):
        return {k: _unwire(v, k) for k, v in value.items()}
    if isinstance(value, list):
        return [_unwire(v, key) for v in value]
    if key.endswith("_ns") and isinstance(value, str):
        _require(value.isdecimal(), "nonexact nonnegative ns string: " + key)
        return int(value)
    return value


def _wire(value, key=""):
    if isinstance(value, dict):
        return {k: _wire(v, k) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [_wire(v, key) for v in value]
    if type(value) is int and key.endswith("_ns"):
        return str(value)
    return value


def _median_ns(values):
    a = sorted(int(v) for v in values)
    _require(bool(a), "empty nominal distribution")
    return a[len(a) // 2] if len(a) % 2 else (a[len(a) // 2 - 1] + a[len(a) // 2]) // 2


def independent_metrics(rows, service, drain):
    out = {}
    for name in COHORTS:
        group = [r for r in rows if name in ("ALL", r["task"], r["priority"], r["task"] + r["priority"])]
        responded = [r for r in group if r.get("response_ns") is not None and r["response_ns"] <= drain]
        available = [r for r in group if r.get("lane_available_ns") is not None and r["lane_available_ns"] <= drain]
        failed = [r for r in group if r["terminal_status"] == "FAILED" and r not in available]
        times = sorted(r["response_ns"] - r["scheduled_arrival_ns"] for r in responded)
        out[name] = dict(planned=len(group), responded=len(responded), available=len(available),
            deadline_met=sum(r["response_ns"] <= r["deadline_ns"] for r in responded),
            in_service_window=sum(r["response_ns"] <= service for r in responded),
            service_success=sum(r["response_ns"] <= min(service, r["deadline_ns"]) for r in responded),
            failed=len(failed), incomplete=len(group) - len(available) - len(failed),
            response_p95_ns=times[math.ceil(.95 * len(times)) - 1] if times else None)
    return {**out["ALL"], "by_cohort": out}


def _profile_samples(profile):
    _require(profile.get("device") == "A24" and profile.get("schema") == "A24-INTEGRATED-TIMING-BRIDGE-v1", "normalized A24 DEV profile required")
    idx = {}
    pools = {}
    for pool in profile["pools"]:
        key = pool["key"]
        _require(key.get("device") == "A24" and key.get("priority") == "POOLED_NOT_CONDITIONED", "profile device/priority pooling")
        task = {"classification": "C", "detection": "D"}[key["task"]]
        route = key["backend"]
        _require((task, route) in (("C", "CPU"), ("C", "GPU"), ("D", "CPU")), "unsupported A24 profile route")
        pk = key["bank"], key["prep"], key["protocol"], task, route
        _require(pk not in pools, "duplicate exact pool")
        pools[pk] = pool
        for sample in pool["samples"]:
            _require(sample["sample_id"] not in idx and sample["key"] == key, "profile sample uniqueness/key")
            _require(all(sample["offsets_ns"].get(k) is None for k in UNKNOWN), "unknown A24 stage invented in profile")
            _require(sample["source"]["profile_sha256"] == profile["source_profile_sha256"] and sample["source"]["split"] == "DEV", "DEV profile source binding")
            idx[sample["sample_id"]] = sample
    return idx, pools


def _selected(pool, scenario, request, seed, mode="SAMPLED"):
    samples = pool["samples"]
    if mode == "MEDOID":
        median = _median_ns(s["offsets_ns"]["lane_available_ns"] for s in samples)
        return min(samples, key=lambda s: (abs(s["offsets_ns"]["lane_available_ns"] - median), s["sample_id"]))
    _require(mode == "SAMPLED", "unregistered sample mode")
    k = [int(seed), scenario["bank"], scenario.get("prep", "NONE"), request["ordinal"], request["task"], pool["key"]["backend"], pool["key"]["protocol"], request.get("input_sha256"), request.get("tensor_sha256")]
    return samples[int(_digest(k), 16) % len(samples)]


def _nominal_cache(pools, bank, increments):
    out = {}
    for (pool_bank, prep, protocol, task, route), pool in pools.items():
        if (pool_bank, prep, protocol) != (bank, "NONE", "SERIAL"):
            continue
        offsets = [s["offsets_ns"] for s in pool["samples"]]
        occ = _median_ns(x["lane_available_ns"] for x in offsets)
        response = "output_ready_ns" if task == "C" else "persist_complete_ns"
        key = ("classification" if task == "C" else "detection") + "_" + route
        out[task, route] = dict(occupancy_ns=occ, response_ns=_median_ns(x[response] for x in offsets), energy_proxy_j=float(increments[key]) * (occ / NS))
    return out


def _public_only(obs):
    _require(set(obs) <= {"now_ns", "queue", "owners", "estimates", "sensor", "history", "alpha", "initial_AP_c", "wait_used_ns", "waited_request_ids", "waited_burst_ids", "device", "horizon_ns", "heat_weight", "last_release_ns"}, "unexpected observation field: possible future/sample leak")
    _require(obs.get("device") == "A24", "public device")
    for q in obs["queue"]:
        _require(set(q) <= PUBLIC_QUEUE, "nonpublic queue field")
    for owner in obs.get("owners", {}).values():
        _require(set(owner) <= PUBLIC_OWNER, "future owner/sample/finish field")
    for routes in obs.get("estimates", {}).values():
        for e in routes.values():
            _require(set(e) == PUBLIC_ESTIMATE, "nonpublic nominal field")
    _require(set(obs["sensor"]) <= {"AP_c", "SKIN_c", "power_w", "age_s", "recent_activity", "ap_slope_c_s", "power_slope_w_s"}, "nonpublic sensor field")
    _require(obs["sensor"].get("SKIN_c") is None, "A24 SKIN unmodeled must stay null")
    _require(set(obs["history"]) <= {f"{event}_{p}" for event in ("planned", "failed", "responded") for p in ("U", "N")}, "future history field")


def inspect_result(result, profile, models=None):
    """Audit saved raw, without environment, CostState or NN execution.

    The caller separately verifies the durable START/prepared/raw/row chain and
    registered file SHA. Public nominal values are recomputed independently of
    per-request draws and checked before mask/candidate reconstruction.
    """
    import policy_bridge
    import a24_cost_adapter

    r = _unwire(copy.deepcopy(result))
    _require(r["schema"] == "A24-ROLLING-ATC-RL-RESULT-v1" and r["device"] == "A24", "result schema/device")
    _require(r["clock_axis"] == "common_relative_ns", "clock contract")
    models = models if models is not None else a24_cost_adapter.modelsload()
    _require(r["model"] in models["names"], "fixed A24 cost model")
    sample_index, pools = _profile_samples(profile)
    sc = r["scenario"]
    _require(sc.get("device") == "A24" and sc.get("prep") == "NONE", "scenario context")
    rows = {q["request_id"]: q for q in r["requests"]}
    roster = {q["request_id"]: q for q in sc["requests"]}
    _require(len(rows) == len(r["requests"]) == len(roster) == len(sc["requests"]) > 0 and set(rows) == set(roster), "request total coverage/unique identity")
    _require(len({q["ordinal"] for q in roster.values()}) == len(roster), "ordinal uniqueness")
    stop, drain, end = (sc[k] for k in ("service_stop_ns", "drain_stop_ns", "observation_end_ns"))
    _require(stop == 120 * NS and drain == 210 * NS and end == 210 * NS, "registered A24 service/drain/observation windows")
    mode = r.get("timing_mode", "SAMPLED")
    seed = r["seed"]
    nominal = _nominal_cache(pools, sc["bank"], models["profile"]["cost_anchor"]["energy_increment_w"])
    owner_ns = 0
    for rid, row in rows.items():
        _require(all(row.get(k) == v for k, v in roster[rid].items()), "planned input mutated: " + rid)
        _require(row["task"] in ("C", "D") and row["priority"] in ("U", "N"), "task/priority")
        _require(row["deadline_ns"] == row["scheduled_arrival_ns"] + row["relative_deadline_ns"], "absolute/relative deadline")
        _require(row.get("input_sha256") is not None and row.get("tensor_sha256") is not None, "input/tensor binding must be explicit")
        _require(all(row.get(k) is None for k in UNKNOWN) and row.get("readback_complete_ns") is None, "unobserved A24 host/readback stage invented")
        canonical = "GPU" if row["task"] == "C" else "CPU"
        pk = sc["bank"], "NONE", "SERIAL", row["task"], canonical
        _require(pk in pools, "canonical admission pool")
        admission = _selected(pools[pk], sc, roster[rid], seed, mode)["admission_lags_ns"]
        aa = row["scheduled_arrival_ns"] + int(admission["scheduled_to_actual"])
        qe = aa + int(admission["actual_to_queue"])
        _require(row.get("actual_arrival_ns") == (aa if aa <= end else None), "same canonical actual-admission draw")
        _require(row.get("queue_entry_ns") == (qe if qe <= end else None), "same canonical queue-admission draw")
        dispatch = row.get("dispatch_ns")
        if dispatch is None:
            _require(row["terminal_status"] == "INCOMPLETE" and all(row.get(k) is None for k in CHAIN[1:]) and row.get("response_ns") is None, "undispatched phase/status")
            continue
        _require(qe <= dispatch < stop, "dispatch before admission/after service stop")
        route = row["backend"]
        _require((row["task"], route) in (("C", "CPU"), ("C", "GPU"), ("D", "CPU")) and row["owner"] == route, "unsupported A24 route/owner")
        pk = sc["bank"], "NONE", "SERIAL", row["task"], route
        _require(pk in pools, "route absent from exact measured bank")
        expected = _selected(pools[pk], sc, roster[rid], seed, mode)
        timing = row["timing"]
        _require(timing["sample_id"] == expected["sample_id"] and timing["sample_id"] in sample_index, "hidden CRN whole-vector identity")
        _require(timing["pool_key"] == expected["key"] and timing["source_ref"] == expected["source"] and timing["offsets_ns"] == expected["offsets_ns"], "hidden vector/source binding")
        _require(row["model_sha256"] == expected["model_sha256"], "source model SHA")
        for key in ("input_sha256", "tensor_sha256"):
            _require(row[key] == expected[key], "source exact input/tensor SHA: " + key)
        _require(timing["admission_lags_ns"] == admission and int(timing["redispatch_delay_ns"]) == 0 and timing["redispatch_evidence"] == "UNIDENTIFIED_IDEAL_CONTROLLER_ASSUMPTION", "admission/ideal-controller scope")
        for field in PHASE_EVENT.values():
            offset = expected["offsets_ns"].get(field)
            wanted = dispatch + int(offset) if offset is not None else None
            if wanted is not None and wanted > end:
                wanted = None
            _require(row.get(field) == wanted, "whole-vector timestamp: " + field)
        for a, b in zip(CHAIN, CHAIN[1:]):
            if row.get(b) is not None:
                _require(row.get(a) is not None and row[a] <= row[b], "five-phase DAG")
        response_field = "output_ready_ns" if row["task"] == "C" else "persist_complete_ns"
        _require(row.get("response_ns") == row.get(response_field), "A24 task-specific response boundary")
        _require(row.get("execution_ns") == row.get("execution_start_ns"), "execution alias")
        av = row.get("lane_available_ns")
        _require((row["terminal_status"] == "AVAILABLE") == (av is not None), "terminal AVAILABLE")
        owner_ns += (av if av is not None else end) - dispatch
    owners, queued, seen, responded, missed = {}, set(), set(), set(), set()
    phase_seen, dispatched = set(), set()
    deadlines_seen = set()
    wait_until = wait_actual = wait_nominal = 0
    waited_ids, waited_bursts = set(), set()
    last_release = {"CPU": 0, "GPU": 0}
    initial_aps, decision_count, nominal_checks = set(), 0, 0
    last_time, last_sensor = -1, None
    pending_action = None
    policy, decisions = r["policy"], r["decisions"]
    family = policy.get("rule") or policy["family"]
    curve = {round(float(x["time_s"]) * NS): x for x in r["curve"]}
    _require(len(curve) == len(r["curve"]) == end // 500_000_000 + 1, "complete unique model sensor grid")
    _require(set(curve) == set(range(0, end + 1, 500_000_000)), "sensor grid coverage")
    for seq, e in enumerate(r["events"]):
        time, kind, rid = e["logical_time_ns"], e["kind"], e.get("request_id")
        _require(e["sequence"] == seq and last_time <= time <= end, "event sequence/window")
        if time != last_time and pending_action is not None:
            _require(pending_action["kind"] == "RESOURCE_WAIT", "chosen action missing physical execution")
            pending_action = None
        last_time = time
        if rid is not None:
            _require(rid in rows, "unknown event request")
        if kind == "ACTUAL_ARRIVAL":
            _require(rid not in seen and rows[rid]["actual_arrival_ns"] == time, "actual arrival replay")
            seen.add(rid)
        elif kind == "ENQUEUE":
            _require(rid in seen and rid not in queued and rows[rid]["queue_entry_ns"] == time, "enqueue replay")
            queued.add(rid)
        elif kind == "DEADLINE":
            _require(rid not in deadlines_seen and rows[rid]["deadline_ns"] == time, "deadline event")
            deadlines_seen.add(rid)
            if rid not in responded:
                missed.add(rid)
        elif kind == "DISPATCH":
            lane = e["owner"]
            _require(pending_action is not None and pending_action["kind"] == "DISPATCH" and pending_action["request_id"] == rid and pending_action["route"] == lane, "chosen/actual DISPATCH mismatch")
            pending_action = None
            _require(rid in queued and rid not in dispatched and lane not in owners and rows[rid]["dispatch_ns"] == time and time >= wait_until, "dispatch queue/owner/WAIT")
            queued.remove(rid)
            dispatched.add(rid)
            owners[lane] = rid
            labels = {(rows[q]["task"], b) for b, q in owners.items()}
            _require(len(owners) <= 2 and (len(owners) <= 1 or labels == {("C", "GPU"), ("D", "CPU")}), "actual supported A24 overlap")
        elif kind in PHASE_EVENT:
            field = PHASE_EVENT[kind]
            _require((rid, kind) not in phase_seen and rows[rid].get(field) == time, "phase event identity/time")
            phase_seen.add((rid, kind))
            lane = rows[rid]["backend"]
            _require(e["owner"] == lane and owners.get(lane) == rid, "phase after ownership ended")
            if kind == "AVAILABLE":
                del owners[lane]
                last_release[lane] = time
            elif kind == "RESPONSE":
                responded.add(rid)
        elif kind == "WAIT_START":
            p = e["payload"]
            dose, nominal_dose, head = int(p["duration_ns"]), int(p["nominal_ns"]), p["head_request_id"]
            _require(pending_action is not None and pending_action["kind"] == "WAIT" and int(pending_action["wait_ns"]) == nominal_dose, "chosen/actual WAIT mismatch")
            pending_action = None
            _require(head in queued and head not in waited_ids and dose == min(nominal_dose, stop - time) > 0 and time >= wait_until, "WAIT head/dose/repeat")
            wait_until = time + dose
            wait_actual += dose
            wait_nominal += nominal_dose
            waited_ids.add(head)
            burst = rows[head]["burst_index"]
            if policy.get("rule") == "FIFO_WAIT_CG":
                _require(nominal_dose == 200_000_000 and burst < 16 and burst not in waited_bursts and not owners, "fixed WAIT200x16 scope")
            waited_bursts.add(burst)
            _require(wait_nominal <= 12 * NS and wait_actual <= 12 * NS, "WAIT budget")
        elif kind == "SENSOR":
            _require(time in curve, "sensor grid event")
            last_sensor = time
        elif kind == "WAIT_END":
            _require(time == wait_until and int(e["payload"]["wait_until_ns"]) == wait_until, "actual WAIT end boundary")
        elif kind == "POLICY_DECISION":
            _require(pending_action is None or pending_action["kind"] == "RESOURCE_WAIT", "prior choice not executed")
            _require(decision_count < len(decisions), "extra decision event")
            d = decisions[decision_count]
            _require(d == e["payload"] and d["time_ns"] == time < stop and time >= wait_until, "decision payload/time")
            if policy["decision_mode"] == "TICK200":
                _require(time % 200_000_000 == 0, "fixed tick decision off grid")
            obs = d["observation"]
            _public_only(obs)
            _require(obs["now_ns"] == time and d["input_sha256"] == _digest(_wire(obs)), "observation digest/time")
            _require(len(obs["queue"]) == len(queued) and {q["request_id"] for q in obs["queue"]} == queued, "actual public queue")
            for q in obs["queue"]:
                _require(all(rows[q["request_id"]][k] == v for k, v in q.items()), "public queue metadata")
            _require(set(obs["owners"]) == set(owners), "actual owner lanes")
            for lane, owner in obs["owners"].items():
                actual = rows[owners[lane]]
                _require(all(owner[k] == actual[k] for k in ("request_id", "task", "priority", "dispatch_ns")), "actual public owner")
            _require(set(obs["estimates"]) == queued | set(owners.values()), "absent/future request nominal leak")
            for qid, routes in obs["estimates"].items():
                task = rows[qid]["task"]
                expected_routes = {route for t, route in nominal if t == task}
                _require(set(routes) == expected_routes, "nominal exact measured route coverage")
                for route, values in routes.items():
                    wanted = nominal[task, route]
                    _require(values["occupancy_ns"] == wanted["occupancy_ns"] and values["response_ns"] == wanted["response_ns"], "hidden sample substituted as nominal timing")
                    _require(math.isfinite(values["energy_proxy_j"]) and abs(values["energy_proxy_j"] - wanted["energy_proxy_j"]) <= 1e-12, "nominal fixed A24 cost proxy")
                    nominal_checks += 1
            for p in ("U", "N"):
                counts = {"planned": sum(rows[q]["priority"] == p for q in seen), "failed": sum(rows[q]["priority"] == p for q in (missed & seen)), "responded": sum(rows[q]["priority"] == p for q in responded)}
                _require(all(obs["history"][k + "_" + p] == v for k, v in counts.items()), "arrived-only history denominator")
            _require(obs["wait_used_ns"] in (wait_actual, wait_nominal) and set(obs["waited_request_ids"]) == waited_ids, "public WAIT history")
            _require(set(obs.get("waited_burst_ids", ())) == waited_bursts, "public WAIT burst history")
            if "last_release_ns" in obs:
                _require(all(obs["last_release_ns"].get(k) == v for k, v in last_release.items()), "public release history")
            _require(last_sensor is not None and float(obs["sensor"]["age_s"]) == (time - last_sensor) / NS, "last completed public sensor age")
            cp = curve[last_sensor]
            _require(obs["sensor"]["AP_c"] == cp["AP_c"] and obs["sensor"]["power_w"] == cp["power_w"], "held public sensor not same completed sample")
            initial_aps.add(float(obs["initial_AP_c"]))
            bank = policy_bridge.build_bank(obs, family, allow_wait=policy["allow_wait"])
            idx = d["chosen_index"]
            _require(d["mask"] == bank["mask"].tolist(), "candidate hierarchy mask replay")
            _require(type(idx) is int and 0 <= idx < len(bank["actions"]) and bank["mask"][idx] and bank["physical_mask"][idx], "chosen physical/hierarchy mask")
            _require(d["action"] == bank["actions"][idx], "candidate/action replay")
            _require(d["diagnostic"] == _unwire(copy.deepcopy(bank["diagnostic"])), "candidate diagnostic replay")
            if policy.get("rule"):
                _require(idx == policy_bridge.select_rule(bank, policy["rule"]), "rule choice replay")
            pending_action = d["action"]
            decision_count += 1
    _require(decision_count == len(decisions) > 0 and len(initial_aps) == 1, "complete decisions/fixed initial AP")
    _require(pending_action is None or pending_action["kind"] == "RESOURCE_WAIT", "last chosen action not executed")
    for rid, row in rows.items():
        _require((rid in seen) == (row.get("actual_arrival_ns") is not None), "arrival event coverage")
        _require((rid in dispatched) == (row.get("dispatch_ns") is not None), "dispatch event coverage")
        _require((rid in deadlines_seen) == (row["deadline_ns"] <= end), "deadline event coverage")
        for kind, field in PHASE_EVENT.items():
            _require(((rid, kind) in phase_seen) == (row.get(field) is not None), "phase event total coverage")
    expected_metrics = independent_metrics(list(rows.values()), stop, drain)
    _require(r["metrics"] == expected_metrics, "cohort/full denominator/P95 arithmetic")
    cost = r["cost"]
    cm = cost.get("metrics", cost)
    _require(cm["new_measurement_energy_unit_resolved"] is False and cm["physical_or_independent_policy_delta_accuracy_confirmed"] is False, "conditional cost evidence boundary")
    _require(cm["SKIN_c"] is None and cm["thermal_to_timing_feedback"] is False, "unsupported skin/thermal feedback")
    _require(cm["model_name"] == r["model"] and cm["model_binding_sha256"] == models["binding_sha256"], "cost source model binding")
    _require(cm["energy_baseline_mode"] == a24_cost_adapter.BASELINE_MODE, "historical baseline mode")
    _require(abs(cm["baseline_w"] - models["baseline_w"]) <= 1e-15, "fixed baseline changed")
    initial_ap = next(iter(initial_aps))
    _require(cm["initial_AP_c"] == initial_ap, "cost/public initial AP binding")
    predicted = [(cm["continuous_J0_180"] - cm["baseline_w"] * 180) / 20, (cm["AP35_180_mean_c"] - initial_ap) * 145 / 72.5]
    for p in ("U", "N"):
        group = [x for x in rows.values() if x["priority"] == p]
        predicted.append(sum(x.get("response_ns") is None or x["response_ns"] > x["deadline_ns"] for x in group) / max(1, len(group)))
    predicted.append(expected_metrics["incomplete"] / len(rows))
    _require(np.allclose(cm["cost_cumulative2"], predicted[:2], atol=1e-8, rtol=0), "fixed-window J/AP label arithmetic")
    if "cost_cumulative" in cost:
        _require(np.allclose(cost["cost_cumulative"], predicted[:2], atol=1e-8, rtol=0), "outer cost cumulative binding")
    _require(np.allclose(r["cost_labels"]["total"], predicted, atol=1e-8, rtol=0) and r["cost_labels"]["telescope_error"] <= 1e-8, "all five total costs/telescope")
    _require(abs(cm["continuous_J35_180"] - (cm["continuous_J0_180"] - curve[35 * NS]["J"])) <= 1e-8, "J35-180 window subtraction")
    _require(abs(cm["continuous_J0_120"] - curve[120 * NS]["J"]) <= 1e-8 and abs(cm["continuous_J0_180"] - curve[180 * NS]["J"]) <= 1e-8, "cumulative curve energy boundaries")
    _require(abs(cm["AP180_c"] - curve[180 * NS]["AP_c"]) <= 1e-10 and abs(cm["AP180_residual_from_initial_c"] - (cm["AP180_c"] - initial_ap)) <= 1e-10, "AP180 residual")
    _require(cm["AP0_180_peak_c"] >= max(float(x["AP_c"]) for t, x in curve.items() if t <= 180 * NS) - 1e-10, "sampled peak cannot miss public grid peak")
    _require(cm["all_owner_released"] == (not owners), "cost final owner state")
    return dict(status="PASS", schema="A24-SAVED-RESULT-AUDIT-v1", requests=len(rows), events=len(r["events"]), decisions=decision_count,
        selected_whole_vectors_checked=len(dispatched), public_nominal_route_values_checked=nominal_checks,
        physical_hierarchy_masks_replayed=decision_count, original_rule_choices_replayed=decision_count if policy.get("rule") else 0,
        all_cohort_metrics_recomputed=True, input_model_tensor_bindings_checked=True, unknown_inner_stages_retained_null=True,
        all_actual_owner_time_ns=str(owner_ns), wait_actual_ns=str(wait_actual), wait_nominal_ns=str(wait_nominal),
        final_cost=predicted, result_sha256=_digest(result), no_future_sample_as_public_estimate=True,
        no_environment_execution=True, no_CostState_integration=True, no_NN_inference=True, optimizer_steps=0,
        external_binding_required="Parent must verify durable START/prepared/raw/row/terminal and source/initial/model SHA.")


def verify_saved_frames(frames, net, decisions=None, costs=None, alpha=None, counts=None, atol=1e-5, allow_wait=True):
    """Registered NN/RNG replay of saved inputs; no environment/Adam update."""
    import torch
    import learner
    import policy_bridge

    _require(bool(frames), "empty saved frames")
    network_sha = learner.network_digest(net)
    if decisions is not None:
        _require(len(decisions) == len(frames), "decision/frame total coverage")
    for i, frame in enumerate(frames):
        _require(frame["network_sha256"] == network_sha, "saved checkpoint network differs")
        if i:
            _require(torch.equal(frames[i - 1]["action_rng_after"], frame["action_rng_before"]), "action RNG continuity")
        replay = learner.replay_frame(net, frame)
        _require(abs(replay["logprob"] - frame["old_logp"]) <= atol, "saved logprob")
        _require(np.allclose(replay["critic"], frame["value"], atol=atol, rtol=0), "saved five critic values")
        index = frame["index"]
        _require(frame["mask"][index] and frame["physical_mask"][index] and np.all(~frame["mask"] | frame["physical_mask"]), "saved NN mask legality")
        if frame["collect"]:
            rng = torch.Generator()
            rng.set_state(frame["action_rng_before"])
            with torch.no_grad():
                residual, _ = net(*learner.tensors(frame))
                logits = (residual + torch.from_numpy(frame["prior_logits"])[None, :]).masked_fill(~torch.from_numpy(frame["mask"])[None, :], -1e9)
                chosen = int(torch.multinomial(logits.softmax(-1)[0], 1, generator=rng))
            _require(chosen == index and torch.equal(rng.get_state(), frame["action_rng_after"]), "saved action RNG exact replay")
        else:
            _require(replay["argmax"] == index and torch.equal(frame["action_rng_before"], frame["action_rng_after"]), "saved argmax/no RNG consumption")
        if decisions is not None:
            d = _unwire(decisions[i])
            _require(d["time_ns"] == frame["time_ns"] and d["chosen_index"] == index, "NN frame/public decision binding")
            family = d["diagnostic"]["family"]
            bank = policy_bridge.build_bank(d["observation"], family, allow_wait=allow_wait)
            for key in INPUTS:
                _require(np.array_equal(bank[key], frame[key]) and bank[key].dtype == frame[key].dtype, "original saved input bytes/dtype: " + key)
            _require(np.array_equal(bank["physical_mask"], frame["physical_mask"]), "saved physical mask bytes")
            prior = bank["prior_logits"] if family == "ATC_RESIDUAL_RL" else np.zeros(80, np.float32)
            _require(np.array_equal(prior, frame["prior_logits"]), "saved residual prior")
    labels = False
    if costs is not None:
        _require(alpha is not None and counts is not None, "label audit alpha/counts required")
        labelled, meta = learner.label_episode(frames, costs, alpha, counts, learner.Settings())
        if all("target" in f for f in frames):
            for old, expected in zip(frames, labelled):
                for key in ("cost", "target", "adv"):
                    _require(np.allclose(old[key], expected[key], atol=atol, rtol=0), "five-cost label replay: " + key)
        labels = True
    return dict(status="PASS", frames=len(frames), network_sha256=network_sha, saved_input_digests_checked=len(frames),
        saved_logprob_critic_checked=len(frames), action_rng_replayed=sum(bool(f["collect"]) for f in frames), argmax_replayed=sum(not f["collect"] for f in frames),
        public_NN_input_arrays_checked=len(frames) * len(INPUTS) if decisions is not None else 0, five_cost_labels_recomputed=labels,
        no_environment_execution=True, new_optimizer_steps=0)


verify_frames = verify_saved_frames


def run_numeric_tests(initial, models):
    """Registered cost-only original-code comparison and .001 s quadrature.

    Do not invoke before parent registration. Four wrappers per model are
    avoided: one adapter, one original direct replay and one independent fine
    original replay are constructed per model. There is no scheduler episode,
    new physical fit, NN inference or optimizer operation.
    """
    import a24_cost_adapter as adapter

    operations = [
        (35_000_000_000, "DISPATCH", "G", "C", "GPU"),
        (35_250_000_000, "DISPATCH", "D", "D", "CPU"),
        (38_000_000_000, "AVAILABLE", "G", None, "GPU"),
        (40_000_000_000, "AVAILABLE", "D", None, "CPU"),
        (70_000_000_000, "DISPATCH", "C", "C", "CPU"),
        (71_500_000_000, "AVAILABLE", "C", None, "CPU"),
        (179_500_000_000, "DISPATCH", "L", "D", "CPU"),
        (200_000_000_000, "AVAILABLE", "L", None, "CPU"),
    ]
    results = []
    def original(name):
        profile = copy.deepcopy(models["profile"])
        public = copy.deepcopy(profile["trend27_anchor"]["public_boundary"])
        public["pre"] = copy.deepcopy(initial["pre"])
        public["pre_w"] = models["baseline_w"]
        base = models["A24Cost"](profile["cost_anchor"], profile["trend27_anchor"]["thermal"]["AP"], public)
        return base if name == "TREND27" else models["CompactCost"](base, profile)
    def apply(state, operation, is_adapter):
        t, kind, rid, task, route = operation
        if kind == "DISPATCH":
            state.dispatch(rid, task if is_adapter else {"C": "classification", "D": "detection"}[task], route)
        else:
            state.available(rid, route)
    for name in models["names"]:
        state = adapter.OnlineCost(models, initial, name)
        direct = original(name)
        max_j = max_ap = 0.0
        op = 0
        for t in sorted({0, 35 * NS, 120 * NS, 180 * NS, 210 * NS, *[x[0] for x in operations]}):
            state.advance(t)
            direct.advance(t / NS)
            a, b = state.snapshot(), direct.snapshot()
            max_j = max(max_j, abs(a["continuous_energy_j"] - b["energy_window_j"]))
            max_ap = max(max_ap, abs(a["AP_c"] - b["temperature_c"]["AP"]))
            while op < len(operations) and operations[op][0] == t:
                apply(state, operations[op], True)
                apply(direct, operations[op], False)
                op += 1
        _require(max_j <= 1e-8 and max_ap <= 1e-9, "adapter/original cost-state numerical equivalence")
        totals = state.totals()
        _require(abs(totals["cost_cumulative2"][0] - (totals["continuous_J0_180"] - models["baseline_w"] * 180) / 20) <= 1e-10, "late-drain energy reward cap")
        fine = original(name)
        op, last_t, last_ap, area = 0, 0, fine.snapshot()["temperature_c"]["AP"], 0.0
        # Trapezoidal oracle uses the original frozen state.advance, not the
        # adapter's analytic area function or its internal integration steps.
        for t in range(1_000_000, 210 * NS + 1, 1_000_000):
            fine.advance(t / NS)
            ap = fine.snapshot()["temperature_c"]["AP"]
            if last_t >= 35 * NS and t <= 180 * NS:
                area += (last_ap + ap) * .5 * ((t - last_t) / NS)
            while op < len(operations) and operations[op][0] == t:
                apply(fine, operations[op], False)
                op += 1
            last_t, last_ap = t, ap
        mean_difference = abs(area / 145 - totals["AP35_180_mean_c"])
        _require(mean_difference <= 1e-4, "analytic AP area versus .001s original-code quadrature")
        results.append(dict(model=name, max_original_J_difference=max_j, max_original_AP_difference_c=max_ap,
            analytic_APmean_vs_001s_trapezoid_difference_c=mean_difference, late_drain_reward_cap_PASS=True,
            original_cost_wrappers=3, quadrature_steps=210000, no_environment_execution=True))
    return dict(status="PASS", tests=results, new_environment=0, new_physical_coefficient_fits=0, new_NN_inference=0, optimizer_steps=0,
        cost_only_model_wrapper_instances=3 * len(models["names"]), energy_is_historical_gauge_conditional=True)

