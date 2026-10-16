"""Causal public-state ATC candidate bridge for new A24 PPO training.

This is a fresh input contract with the old tensor SHAPES, not an ABI promise
for old checkpoint semantics. No environment, cost integrator or NN imports.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
from collections.abc import Mapping

import numpy as np

BACKENDS = ("CPU", "GPU", "NPU")
FAMILIES = ("JOINT_ATC_RL", "ATC_ROUTE_RL", "ATC_RESIDUAL_RL", "NO_ATC_RL")
FIXED_RULES = ("FIFO_SERIAL_CPU", "FIFO_SERIAL_CG", "FIFO_SERIAL_CN", "EDD_SERIAL_CG", "FIFO_PAIR_CG", "FIFO_PAIR_CN", "FIFO_WAIT_CG")
RULES = ("FIFO", "FIFO_READY", "EDD", "ATC", "MOBILE_DEADLINE_ENERGY", *FIXED_RULES)
INPUTS = ("requests", "resources", "global_state", "features", "request_index", "backend_index", "mask")
WAIT_DURATIONS_NS = (50_000_000, 200_000_000, 1_000_000_000)
NS = 1_000_000_000
SCHEMA_SPEC = {
    "version": "A24-ROLLING-ATC-RL-TRAIN-policy-v1",
    "shapes": {"requests": [24, 24], "resources": [3, 12], "global_state": [24], "features": [80, 16]},
    "actions": "slot*3+route for 24 requests; WAIT72..74; RESOURCE_WAIT75; PAD76..79",
    "atc": "log(w/p_occ)-max(deadline-now-p_response,0)/(2*mean_p_occ); w(U/N)=2/1",
    "shortlist": "ATC top12 + per-route ready/cheap + per-priority oldest + ready EDD + minslack; <=24; NO_ATC_RL=FIFO24, not full queue",
    "physical": "actualfree, nonpreemptive; max2 only D_CPU + C_GPU/NPU; sequential same-time dispatch",
    "wait": "legal dispatch, allow_wait, consumed actual wait + proposed nominal <=12s, per ATC-head once, now<horizon; no slack guard",
    "resource_wait": "busy owner exists and no family-legal dispatch",
    "residual_prior": "dispatch clip(ATC-score minus max-selected-score,-10,0); WAIT=-1; resource=0",
    "inputs": "arrived queue and public nominal estimates only; no sampled durations/finish/offset vectors",
    "old_checkpoint_abi_compatible": False,
}
SCHEMA = hashlib.sha256(json.dumps(SCHEMA_SPEC, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class ContractError(ValueError):
    pass


def _int(value, name, minimum=0):
    if isinstance(value, bool) or not isinstance(value, (int, np.integer)) or value < minimum:
        raise ContractError(f"{name}: integer >= {minimum} required")
    return int(value)


def _number(value, name, minimum=None):
    if isinstance(value, bool) or not isinstance(value, (int, float, np.integer, np.floating)):
        raise ContractError(f"{name}: finite number required")
    value = float(value)
    if not math.isfinite(value) or (minimum is not None and value < minimum):
        raise ContractError(f"{name}: finite number out of range")
    return value


def _clip(value):
    return max(-10., min(10., float(value)))


def _tie(q):
    return q["scheduled_arrival_ns"], q["ordinal"], q["request_id"]


def _routes(q):
    return BACKENDS if q["task"] == "C" else ("CPU",)


def _validated(obs):
    if not isinstance(obs, Mapping):
        raise ContractError("observation must be a mapping")
    now = _int(obs.get("now_ns"), "now_ns")
    queue = obs.get("queue")
    if not isinstance(queue, (list, tuple)) or len(queue) > 512:
        raise ContractError("queue list/tuple <=512 required")
    seen = set()
    for q in queue:
        if not isinstance(q, Mapping) or not isinstance(q.get("request_id"), str) or not q["request_id"]:
            raise ContractError("request id required")
        rid = q["request_id"]
        if rid in seen:
            raise ContractError("duplicate queued request")
        seen.add(rid)
        if q.get("task") not in ("C", "D") or q.get("priority") not in ("U", "N"):
            raise ContractError("task C/D and priority U/N required")
        arrival = _int(q.get("scheduled_arrival_ns"), "scheduled_arrival_ns")
        _int(q.get("ordinal"), "ordinal")
        _int(q.get("deadline_ns"), "deadline_ns", arrival)
        if arrival > now:
            raise ContractError("future request leaked to public queue")
        if "queue_entry_ns" in q and _int(q["queue_entry_ns"], "queue_entry_ns") > now:
            raise ContractError("request has not entered queue")
    owners = obs.get("owners", {})
    if not isinstance(owners, Mapping) or any(b not in BACKENDS for b in owners):
        raise ContractError("owners must contain CPU/GPU/NPU only")
    active = {}
    for lane, owner in owners.items():
        if owner is None:
            continue
        if not isinstance(owner, Mapping) or owner.get("task") not in ("C", "D"):
            raise ContractError("active owner must have task")
        rid = owner.get("request_id")
        if not isinstance(rid, str) or not rid or rid in seen or rid in {x["request_id"] for x in active.values()}:
            raise ContractError("duplicate/nonexistent active identity")
        if _int(owner.get("dispatch_ns"), "owner.dispatch_ns") > now:
            raise ContractError("future owner dispatch")
        if owner["task"] == "D" and lane != "CPU":
            raise ContractError("detection only CPU")
        active[lane] = owner
    labels = {(x["task"], b) for b, x in active.items()}
    if len(active) > 2 or (len(active) == 2 and labels not in ({("D", "CPU"), ("C", "GPU")}, {("D", "CPU"), ("C", "NPU")})):
        raise ContractError("unsupported active combination")
    estimates = obs.get("estimates", {})
    if not isinstance(estimates, Mapping):
        raise ContractError("estimates mapping required")
    paths = {}
    for q in queue:
        rid = q["request_id"]
        source = estimates.get(rid, {})
        if not isinstance(source, Mapping):
            raise ContractError("nominal request estimates required")
        available_routes = [b for b in BACKENDS if b in source and b in _routes(q)]
        if not available_routes or (q["task"] == "D" and available_routes != ["CPU"]):
            raise ContractError(f"missing usable profile route for {rid}; missing data != hardware unsupported")
        if any(b not in _routes(q) for b in source):
            raise ContractError(f"unsupported nominal route for {rid}")
        for b in available_routes:
            e = source.get(b)
            if not isinstance(e, Mapping):
                raise ContractError(f"missing nominal estimate {rid}/{b}")
            occ = _int(e.get("occupancy_ns"), "occupancy_ns", 1)
            response = _int(e.get("response_ns"), "response_ns")
            if response > occ:
                raise ContractError("nominal response must not exceed occupancy")
            energy = _number(e.get("energy_proxy_j"), "energy_proxy_j", 0)
            paths[rid, b] = (occ, response, energy)
    return now, sorted(queue, key=_tie), active, paths


def _physical(q, route, owners):
    if route in owners or len(owners) >= 2:
        return False
    if not owners:
        return True
    labels = {(o["task"], b) for b, o in owners.items()} | {(q["task"], route)}
    return labels in ({("D", "CPU"), ("C", "GPU")}, {("D", "CPU"), ("C", "NPU")})


def build_bank(obs, family="JOINT_ATC_RL", allow_wait=True):
    """Build fixed PPO tensors and auditable actions from current public state.

    Mutates no inputs. Empty queues are valid only if a RESOURCE_WAIT is legal;
    the engine should normally avoid calling the controller on an empty queue.
    `history.planned_U/N` mean already-arrived totals, not future roster totals.
    """
    if family not in (*FAMILIES, *RULES):
        raise ContractError(f"unsupported family {family!r}")
    if type(allow_wait) is not bool:
        raise ContractError("allow_wait bool required")
    now, ordered, owners, paths = _validated(obs)
    routes = lambda q: tuple(b for b in BACKENDS if (q["request_id"], b) in paths)
    reps = {}
    for q in ordered:
        rid = q["request_id"]
        best = min(routes(q), key=lambda b: (paths[rid, b][1], paths[rid, b][0], BACKENDS.index(b)))
        reps[rid] = (*paths[rid, best][:2], best)
    mean_occ_s = sum(v[0] / NS for v in reps.values()) / max(1, len(reps))
    scores = {q["request_id"]: math.log((2. if q["priority"] == "U" else 1.) / (reps[q["request_id"]][0] / NS))
              - max((q["deadline_ns"] - now - reps[q["request_id"]][1]) / NS, 0.) / (2 * mean_occ_s)
              for q in ordered}
    sorts = {
        "ATC": sorted(ordered, key=lambda q: (-scores[q["request_id"]], *_tie(q))),
        "EDD": sorted(ordered, key=lambda q: (q["deadline_ns"], *_tie(q))),
        "SPT": sorted(ordered, key=lambda q: (min(paths[q["request_id"], b][0] for b in routes(q)), *_tie(q))),
    }
    ranks = {name: {q["request_id"]: i for i, q in enumerate(values)} for name, values in sorts.items()}
    legal_all = [(q, b) for q in ordered for b in routes(q) if _physical(q, b, owners)]
    supplements = []
    def add(q):
        if q["request_id"] not in {x["request_id"] for x in supplements}:
            supplements.append(q)
    # <=6 per-route, <=2 per-priority, ready EDD, minslack: <=10 supplements.
    for b in BACKENDS:
        qs = [q for q, lane in legal_all if lane == b]
        if qs:
            add(min(qs, key=lambda q: (-scores[q["request_id"]], *_tie(q))))
            add(min(qs, key=lambda q: (paths[q["request_id"], b][2], *_tie(q))))
    for p in ("U", "N"):
        qs = [q for q in ordered if q["priority"] == p]
        if qs:
            add(qs[0])
    if legal_all:
        add(min(legal_all, key=lambda qb: (ranks["EDD"][qb[0]["request_id"]], paths[qb[0]["request_id"], qb[1]][1], BACKENDS.index(qb[1])))[0])
    if ordered:
        add(min(ordered, key=lambda q: (q["deadline_ns"] - now - reps[q["request_id"]][1], *_tie(q))))
    if family == "NO_ATC_RL":
        selected = list(ordered[:24])
    else:
        selected = list(supplements)
        for q in sorts["ATC"][:12]:
            if q["request_id"] not in {x["request_id"] for x in selected}:
                selected.append(q)
        selected.sort(key=lambda q: (ranks["ATC"][q["request_id"]], *_tie(q)))
    if len(selected) > 24:
        raise ContractError("ATC supplement bound")
    sensor = obs.get("sensor", {})
    if not isinstance(sensor, Mapping):
        raise ContractError("sensor mapping required")
    ap = _number(sensor.get("AP_c"), "sensor.AP_c")
    power = _number(sensor.get("power_w"), "sensor.power_w", 0.)
    age = sensor.get("age_s", 0.)
    thermal_age = _number(age.get("thermal", 0.) if isinstance(age, Mapping) else age, "thermal age", 0.)
    power_age = _number(age.get("power", 0.) if isinstance(age, Mapping) else age, "power age", 0.)
    unknown = []
    def optional(mapping, key, default=0.):
        if key not in mapping:
            unknown.append(key)
            return default
        return _number(mapping[key], key)
    activity = sensor.get("recent_activity", {})
    if not isinstance(activity, Mapping):
        raise ContractError("recent_activity mapping required")
    recent = [optional(activity, b) for b in BACKENDS]
    requests = np.zeros((24, 24), np.float32)
    for j, q in enumerate(selected):
        rid = q["request_id"]
        row = [q["task"] == "C", q["task"] == "D", q["priority"] == "U",
               (now - q["scheduled_arrival_ns"]) / (6 * NS), (q["deadline_ns"] - now) / (6 * NS),
               (q["deadline_ns"] - now - reps[rid][1]) / (6 * NS), 1 / 3,
               *[b in routes(q) for b in BACKENDS]]
        for b in BACKENDS:
            row += [paths[rid, b][0] / (6 * NS), paths[rid, b][1] / (6 * NS)] if (rid, b) in paths else [0., 0.]
        row += [scores[rid] / 10, *[ranks[k][rid] / 64 for k in ("EDD", "ATC", "SPT")], .05 / 6,
                (.5 if q["priority"] == "U" else .25), q["priority"] == "N", 1.]
        requests[j] = [_clip(v) for v in row]
        if family == "NO_ATC_RL":
            requests[j, 16] = requests[j, 18] = 0.
    resources = np.zeros((3, 12), np.float32)
    for j, b in enumerate(BACKENDS):
        owner = owners.get(b)
        if owner:
            elapsed = now - owner["dispatch_ns"]
            e = obs.get("estimates", {}).get(owner["request_id"], {}).get(b)
            if e is not None:
                remaining_occ = max(_int(e["occupancy_ns"], "owner nominal occupancy") - elapsed, 0)
                remaining_resp = max(_int(e["response_ns"], "owner nominal response") - elapsed, 0)
            else:
                remaining_occ = remaining_resp = 0
                unknown.append(f"owner_nominal_{b}")
            phase = owner.get("phase_index")
            if phase is None:
                phase = 0
                unknown.append(f"owner_phase_{b}")
            resources[j] = [_clip(v) for v in [1, 1, owner["task"] == "C", owner["task"] == "D", owner.get("priority") == "U",
                                               _number(phase, "phase_index", 0) / 5, elapsed / (6 * NS), remaining_occ / (6 * NS), remaining_resp / (6 * NS), 0, recent[j], 1]]
        else:
            last = _int(obs.get("last_release_ns", {}).get(b, 0), "last release")
            if last > now:
                raise ContractError("future last release")
            resources[j] = [_clip(v) for v in [1, 0, 0, 0, 0, 0, 0, 0, 0, (now - last) / (6 * NS), recent[j], 1]]
    history = obs.get("history", {})
    if not isinstance(history, Mapping):
        raise ContractError("history mapping required")
    history_counts = {k: _int(history.get(k, 0), f"history.{k}") for k in ("planned_U", "planned_N", "failed_U", "failed_N", "responded_U", "responded_N")}
    for p in ("U", "N"):
        if history_counts[f"failed_{p}"] > history_counts[f"planned_{p}"] or history_counts[f"responded_{p}"] > history_counts[f"planned_{p}"]:
            raise ContractError("observed history exceeds arrived denominator")
    su = [(q["deadline_ns"] - now) / (6 * NS) for q in ordered if q["priority"] == "U"]
    sn = [(q["deadline_ns"] - now) / (6 * NS) for q in ordered if q["priority"] == "N"]
    wait_used = _int(obs.get("wait_used_ns", 0), "wait_used_ns")
    if wait_used > 12 * NS:
        raise ContractError("actual WAIT exceeds registered 12s cap")
    global_state = np.asarray([_clip(v) for v in [now / (120 * NS), len(ordered) / 64, len(su) / 64, len(sn) / 64,
                    sum(q["task"] == "C" for q in ordered) / 64, sum(q["task"] == "D" for q in ordered) / 64,
                    min(su, default=0), min(sn, default=0), history_counts["failed_U"] / max(1, history_counts["planned_U"]),
                    (ap - 30) / 10, power / 10, thermal_age / 6, power_age / 6,
                    optional(sensor, "ap_slope_c_s"), optional(sensor, "power_slope_w_s") / 10, *recent,
                    wait_used / (12 * NS), history_counts["failed_N"] / max(1, history_counts["planned_N"]),
                    _number(obs.get("alpha", 1.), "alpha", 0.), _number(obs.get("alpha", 1.), "alpha", 0.),
                    _number(obs.get("heat_weight", .5), "heat_weight", 0.), 1]], np.float32)
    features = np.zeros((80, 16), np.float32)
    request_index = np.zeros(80, np.int64)
    backend_index = np.zeros(80, np.int64)
    physical_mask = np.zeros(80, bool)
    mask = np.zeros(80, bool)
    actions = [{"kind": "PAD"} for _ in range(80)]
    prior_logits = np.zeros(80, np.float32)
    head_id = sorts["ATC"][0]["request_id"] if ordered else None
    if family == "NO_ATC_RL" or family in FIXED_RULES:
        fixed_order = sorts["EDD"] if family == "EDD_SERIAL_CG" else ordered
        head_id = fixed_order[0]["request_id"] if ordered else None
    max_score = max((scores[q["request_id"]] for q in selected), default=0.)
    for slot, q in enumerate(selected):
        rid = q["request_id"]
        for b in routes(q):
            j = slot * 3 + BACKENDS.index(b)
            occ, resp, energy = paths[rid, b]
            legal = _physical(q, b, owners)
            physical_mask[j] = legal
            mask[j] = legal and (family != "ATC_ROUTE_RL" or rid == head_id)
            if family in FIXED_RULES:
                required_route = ("CPU" if family=="FIFO_SERIAL_CPU" else "NPU" if family in ("FIFO_PAIR_CN", "FIFO_SERIAL_CN") else "GPU") if q["task"] == "C" else "CPU"
                serial = family in ("FIFO_SERIAL_CPU", "FIFO_SERIAL_CG", "FIFO_SERIAL_CN", "EDD_SERIAL_CG", "FIFO_WAIT_CG")
                mask[j] = bool(legal and rid == head_id and b == required_route and (not serial or not owners))
            request_index[j] = slot
            backend_index[j] = BACKENDS.index(b)
            actions[j] = {"kind": "DISPATCH", "request_id": rid, "route": b}
            can_pair_now = legal and not owners and any(other["request_id"] != rid and
                              {(q["task"], b), (other["task"], rb)} in ({("D", "CPU"), ("C", "GPU")}, {("D", "CPU"), ("C", "NPU")})
                              for other in ordered for rb in routes(other))
            concurrency = 1 if owners else 2 if can_pair_now else 0
            features[j] = [_clip(v) for v in [*[b == x for x in BACKENDS], 0, occ / (6 * NS), resp / (6 * NS),
                            (q["deadline_ns"] - now - resp) / (6 * NS), energy,
                            energy / max(occ / NS, 1e-9) / 10, concurrency, 0, power_age / 6, legal, .5,
                            ranks["ATC"][rid] / 64, 1]]
            prior_logits[j] = max(-10., min(0., scores[rid] - max_score))
            if family == "NO_ATC_RL":
                features[j, 14] = 0.
    has_dispatch = bool(mask[:72].any())
    consumed = obs.get("waited_request_ids", ())
    if not isinstance(consumed, (list, tuple, set, frozenset)) or any(not isinstance(x, str) for x in consumed):
        raise ContractError("waited_request_ids must be string collection")
    horizon = _int(obs.get("horizon_ns", 120 * NS), "horizon_ns", 1)
    for j, duration in enumerate(WAIT_DURATIONS_NS, 72):
        actions[j] = {"kind": "WAIT", "wait_ns": duration, "head_request_id": head_id}
        physical_mask[j] = True
        mask[j] = bool(allow_wait and has_dispatch and now < horizon and head_id not in consumed and wait_used + duration <= 12 * NS)
        features[j, 3] = features[j, 12] = features[j, 15] = 1
        features[j, 10] = duration / NS
        prior_logits[j] = -1.
        if family in FIXED_RULES:
            head = next((q for q in ordered if q["request_id"] == head_id), None)
            waited_bursts = obs.get("waited_burst_ids", ())
            mask[j] = bool(family == "FIFO_WAIT_CG" and duration == 200_000_000 and allow_wait and has_dispatch
                           and not owners and now < horizon and wait_used + duration <= 12 * NS and head is not None
                           and _int(head.get("burst_index"), "burst_index") < 16 and head["burst_index"] not in waited_bursts)
    actions[75] = {"kind": "RESOURCE_WAIT", "wait_ns": 0}
    physical_mask[75] = bool(owners)
    mask[75] = bool(owners) and not has_dispatch
    features[75, 3] = features[75, 12] = features[75, 15] = 1
    if not mask.any():
        raise ContractError("no legal action; engine must advance events without idle busy-wait")
    if family == "NO_ATC_RL":
        prior_logits.fill(0.)
    diagnostic = {
        "schema": SCHEMA, "family": family, "time_ns": now, "queue": len(ordered),
        "candidate_count": len(selected), "legal_count": int(mask.sum()), "head_request_id": head_id,
        "selected_ids": [q["request_id"] for q in selected], "atc_top12": [q["request_id"] for q in sorts["ATC"][:12]],
        "supplement_ids": [q["request_id"] for q in supplements], "scores": scores,
        "atc_edd_order_same": [q["request_id"] for q in sorts["ATC"]] == [q["request_id"] for q in sorts["EDD"]],
        "unknown_zero_filled": sorted(set(unknown)), "future_input": False,
        "wait_slack_guard": False, "wait_cumulative_actual_ns": wait_used,
        "history_denominator": "already_arrived_only", "rule_mobile": "MOBILE_DEADLINE_ENERGY adaptation, not original static batching scheduler",
        "missing_route_scope": "unmeasured profile route omitted; not a hardware capability exclusion",
        "atc_features_zeroed": family == "NO_ATC_RL", "candidate_scope": "FIFO24" if family == "NO_ATC_RL" else "ATC12_PLUS_SUPPLEMENTS",
    }
    return {"requests": requests, "resources": resources, "global_state": global_state, "features": features,
            "request_index": request_index, "backend_index": backend_index, "mask": mask,
            "physical_mask": physical_mask, "actions": actions, "prior_logits": prior_logits,
            "diagnostic": diagnostic, "selected": copy.deepcopy(selected), "paths": paths,
            "ranks": ranks, "scores": scores, "now_ns": now}


def select_rule(bank, kind="ATC"):
    """Return a legal action index; rules never introduce voluntary WAIT.

    FIFO/EDD/ATC select among ready candidates and fastest nominal response route.
    MOBILE_DEADLINE_ENERGY takes ready EDD head, then minimum proxy energy among
    nominal deadline-feasible routes; otherwise fastest response. It preserves
    deadline-energy mapping intent, not the cited paper's static batching search.
    """
    if kind not in RULES:
        raise ContractError(f"unsupported rule {kind!r}")
    mask = bank["mask"]
    if kind in FIXED_RULES and bank["diagnostic"]["family"] != kind:
        raise ContractError("fixed baseline must build_bank(family=its policy id) to apply its separate physical/control contract")
    if kind == "FIFO_WAIT_CG" and mask[73]:
        return 73
    legal = [int(i) for i in np.flatnonzero(mask[:72])]
    if not legal:
        if mask[75]:
            return 75
        raise ContractError("rule has no legal dispatch/resource wait")
    lookup = {q["request_id"]: q for q in bank["selected"]}
    paths = bank["paths"]
    def key(i):
        a = bank["actions"][i]
        q = lookup[a["request_id"]]
        occ, resp, _ = paths[q["request_id"], a["route"]]
        route_key = resp, occ, BACKENDS.index(a["route"])
        if kind in ("FIFO", "FIFO_READY", *FIXED_RULES) and kind != "EDD_SERIAL_CG":
            return (*_tie(q), *route_key)
        if kind in ("EDD", "EDD_SERIAL_CG", "MOBILE_DEADLINE_ENERGY"):
            return (q["deadline_ns"], *_tie(q), *route_key)
        return (-bank["scores"][q["request_id"]], *_tie(q), *route_key)
    chosen = min(legal, key=key)
    if kind == "MOBILE_DEADLINE_ENERGY":
        rid = bank["actions"][chosen]["request_id"]
        q = lookup[rid]
        safe = [i for i in legal if bank["actions"][i]["request_id"] == rid and
                bank["now_ns"] + paths[rid, bank["actions"][i]["route"]][1] <= q["deadline_ns"]]
        if safe:
            chosen = min(safe, key=lambda i: (paths[rid, bank["actions"][i]["route"]][2],
                                             paths[rid, bank["actions"][i]["route"]][1],
                                             paths[rid, bank["actions"][i]["route"]][0],
                                             BACKENDS.index(bank["actions"][i]["route"])))
    return int(chosen)


def input_digest(bank):
    """Same tensor-byte digest construction as V2, new schema separately bound."""
    digest = hashlib.sha256()
    for name in INPUTS:
        a = bank[name]
        digest.update(name.encode())
        digest.update(a.tobytes())
        digest.update(str(a.shape).encode())
    return digest.hexdigest()
