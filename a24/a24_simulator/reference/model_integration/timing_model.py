"""A24 protocol timing candidate. SOURCE ONLY until registered execution.

Standard-library-only, no import-time reads, fitting, inference or simulation.
Five consecutive intervals remain one observed vector. Protocol and reservation
are public commitments made before a latent sample is selected. No thermal
feedback, queue-wait-as-service, S26 transfer, or silently zero controller cost.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass

NS = 1_000_000_000
SCHEMA = "A24-PROTOCOL-TIMING-v1"
STAGES = ("dispatch_to_execution", "execution_to_output", "output_to_persist",
          "persist_to_worker_release", "worker_release_to_available")
BOUNDARIES = ("execution_start", "output_ready", "persist_complete",
              "worker_release", "lane_available")
ROUTES = {("C", "CPU"), ("C", "GPU"), ("D", "CPU")}
PAIR = frozenset({("C", "GPU"), ("D", "CPU")})
BASELINES = ("FIFO_SERIAL_CPU", "FIFO_SERIAL_CG", "FIFO_PAIR_CG", "FIFO_WAIT_CG")
FEATURE_MODES = ("exact_public", "queue_ap")
BINDINGS = ("input_sha256", "tensor_sha256", "model_sha256")


class UnsupportedContext(ValueError):
    """Unknown support must be reported, never repaired by cross-pool filling."""


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _number(value):
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value))


def ns(request, name):
    """Normalize the declared common relative clock; never infer an origin."""
    value = request.get(name + "_ns")
    if value is not None:
        if type(value) is not int or value < 0:
            raise ValueError(name + "_ns must be a nonnegative exact integer")
        return value
    value = request.get(name + "_s")
    if value is None:
        return None
    if not _number(value) or value < 0:
        raise ValueError(name + "_s must be finite and nonnegative")
    return round(value * NS)


def protocol_name(value):
    # A baseline name is a public protocol declaration, never realized overlap.
    names = {"SERIAL": "SERIAL", "CG_DC": "CG_DC", "PAIR_CG": "CG_DC",
             "FIFO_SERIAL_CPU": "SERIAL", "FIFO_SERIAL_CG": "SERIAL",
             "FIFO_WAIT_CG": "SERIAL", "FIFO_PAIR_CG": "CG_DC"}
    if value not in names:
        raise UnsupportedContext("undeclared/unsupported protocol: " + repr(value))
    return names[value]


def route_of(request):
    return request.get("route", request.get("backend", request.get("requested_backend")))


def context_of(session, request, strict=True):
    """Exact binding prevents accidental mixing across builds or inputs.

    An explicit compatibility mapping can record a reviewed equivalence decision;
    its complete digest is part of the key. Equal version labels alone do not
    establish compatibility. Missing evidence remains visible even in diagnostic
    non-strict mode, whose results are marked UNQUALIFIED throughout.
    """
    compatibility = session.get("compatibility_id", session.get("compatibility"))
    if isinstance(compatibility, dict) and "public_models" in compatibility:
        # Timing source/build semantics are distinct from AP sensor eligibility,
        # provenance generation and workload-bank identity. Preserve original
        # mapping in the session; explicitly project only timing-relevant keys.
        compatibility = {k: compatibility.get(k) for k in (
            "public_apk_sha256", "public_models", "source_commit_declared",
            "source_manifest_sha256", "installed_APK_verified", "signer_verified",
            "source_clock_authority", "quality_binding_verified", "automatic_cross_version_pooling")}
    context = {"device": session.get("device", "A24"), "bank": request.get("bank", session.get("bank")),
               "compatibility": compatibility,
               **{k: request.get(k, session.get(k)) for k in BINDINGS}}
    unknown = [k for k, value in context.items() if value is None or value == "" or value == {}]
    if context["device"] != "A24":
        raise UnsupportedContext("not A24")
    if strict and unknown:
        raise UnsupportedContext("unknown binding: " + ",".join(unknown))
    return context, unknown


def context_for_route(context, task, route):
    """Bind a proposed route to its pre-existing public model registry.

    CPU/GPU models may have different hashes. A policy's target route must not
    inherit the model hash of the route observed in the heldout trace. Every
    source request still has to verify its own measured route/model binding.
    """
    result = copy.deepcopy(context)
    compatibility = result.get("compatibility")
    registry = compatibility.get("public_models") if isinstance(compatibility, dict) else None
    if isinstance(registry, dict):
        item = registry.get(task + "_" + route)
        model = item.get("model") if isinstance(item, dict) else None
        model_sha = model.get("sha256") if isinstance(model, dict) else None
        if not model_sha:
            raise UnsupportedContext("target route model identity is absent from the public registry")
        result["model_sha256"] = model_sha
    return result


def _queue_bin(n):
    if type(n) is not int or n < 0:
        return "UNKNOWN"
    return str(n) if n < 2 else "2-3" if n < 4 else "4-7" if n < 8 else "8+"


def feature_stratum(state, mode):
    if mode not in FEATURE_MODES:
        raise ValueError("unregistered feature mode")
    if mode == "exact_public":
        return ()
    ap = state.get("initial_ap_c")
    return (_queue_bin(state.get("queue_count")),
            math.floor(ap / 5) * 5 if _number(ap) else "UNKNOWN")


def public_snapshot(state):
    """Whitelist only public information, excluding sampled finish/durations.

    The policy and timing selector never receive actual future overlap, owner
    remaining duration, latent index, heldout outcome, or future arrivals.
    """
    now = state["now_ns"]
    if type(now) is not int or now < 0:
        raise ValueError("public now_ns required")
    queue = []
    for q in state.get("queue", []):
        arrival = q.get("queue_entry_ns", q.get("scheduled_arrival_ns"))
        if type(arrival) is not int or arrival > now:
            raise ValueError("future or unknown queue admission")
        queue.append({k: q.get(k) for k in ("request_id", "ordinal", "task", "priority", "group",
                      "scheduled_arrival_ns", "queue_entry_ns", "deadline_ns")})
    owners = []
    for o in state.get("owners", []):
        if type(o.get("dispatch_ns")) is not int or o["dispatch_ns"] > now:
            raise ValueError("future or unknown owner")
        owners.append({k: o.get(k) for k in ("request_id", "task", "route", "dispatch_ns",
                                           "reservation_id", "protocol")})
    return {"now_ns": now, "queue": sorted(queue, key=lambda q: q["request_id"]),
            "owners": sorted(owners, key=lambda o: o["request_id"]),
            "queue_count": len(queue), "initial_ap_c": state.get("initial_ap_c"),
            "history": copy.deepcopy(state.get("history", {}))}


@dataclass(frozen=True)
class Reservation:
    """Immutable dispatch intent created from the current public state."""
    protocol: str
    members: tuple
    now_ns: int
    public_state_sha256: str
    reservation_id: str


def reserve_dispatch(actions, state, protocol):
    snapshot = public_snapshot(state)
    protocol = protocol_name(protocol)
    members = tuple(sorted((a["request_id"], a["task"], a["route"]) for a in actions))
    if not members or len(members) > 2 or len({m[0] for m in members}) != len(members):
        raise ValueError("one or two unique reservation members required")
    if any((t, r) not in ROUTES for _, t, r in members):
        raise UnsupportedContext("unsupported task/route")
    public_ids = {q["request_id"] for q in snapshot["queue"]}
    if any(rid not in public_ids for rid, _, _ in members):
        raise ValueError("reservation contains an unadmitted request")
    if snapshot["owners"]:
        # A SERIAL vector cannot retroactively become a CG_DC vector. This
        # candidate supports atomic pairs only, not an unmeasured mid-owner join.
        raise UnsupportedContext("midexecution join needs separately measured precommitted protocol")
    if protocol == "CG_DC" and (len(members) != 2 or frozenset((t, r) for _, t, r in members) != PAIR):
        raise UnsupportedContext("CG_DC must reserve ready C_GPU and D_CPU atomically")
    if protocol == "SERIAL" and len(members) != 1:
        raise ValueError("SERIAL reservation has exactly one member")
    state_sha = digest(snapshot)
    body = [protocol, members, snapshot["now_ns"], state_sha]
    return Reservation(protocol, members, snapshot["now_ns"], state_sha, digest(body))


def _whole_vector(request):
    durations = request.get("phases_ns")
    if durations is None:
        durations = request.get("phases_s")
        if durations is not None:
            if isinstance(durations, dict):
                durations = [durations.get(k) for k in STAGES]
            durations = [round(x * NS) if _number(x) else None for x in durations]
    if isinstance(durations, dict):
        durations = [durations.get(k) for k in STAGES]
    points = [ns(request, "dispatch"), *[ns(request, b) for b in BOUNDARIES]]
    if points[-1] is None:
        points[-1] = ns(request, "available")
    if all(x is not None for x in points):
        derived = [b - a for a, b in zip(points, points[1:])]
        if durations is not None and list(durations) != derived:
            raise ValueError("stages do not conserve source timestamps")
        durations = derived
    if (durations is None or len(durations) != 5 or
            any(type(x) is not int or x < 0 for x in durations) or sum(durations) <= 0):
        raise ValueError("five measured conserving intervals required")
    if request.get("complete_vector") is False:
        raise ValueError("source marks vector incomplete")
    return tuple(durations)


def _training_public_state(session, request):
    dispatch = ns(request, "dispatch")
    count = None
    if dispatch is not None:
        known = [(ns(q, "queue_entry"), ns(q, "dispatch")) for q in session.get("requests", [])]
        if all(a is not None for a, _ in known):
            count = sum(a <= dispatch and (b is None or b >= dispatch) for a, b in known)
    return {"queue_count": count, "initial_ap_c": session.get("initial_ap_c")}


def observed_ready_idle_gaps(session):
    """Reconstruct eligible-time gaps only with a complete event census.

    Queue residence is not service. WAIT and unobserved admission/failure events
    make the controller gap unidentified. Gaps contain the policy/controller and
    event-handler delay; they do not establish NN computation cost.
    """
    requests = session.get("requests", [])
    if session.get("request_event_coverage") != "COMPLETE":
        return [], ["request/event census not explicitly COMPLETE"]
    arm = session.get("arm", session.get("protocol"))
    if arm == "FIFO_WAIT_CG" or session.get("contains_voluntary_wait"):
        return [], ["voluntary WAIT is not identified as controller overhead"]
    ordered = sorted(requests, key=lambda q: (ns(q, "dispatch") if ns(q, "dispatch") is not None else math.inf,
                                               q.get("ordinal", 0)))
    if any(ns(q, "queue_entry") is None or ns(q, "dispatch") is None or
           (ns(q, "available") is None and ns(q, "lane_available") is None) for q in ordered):
        return [], ["missing exact queue/dispatch/AVAILABLE event"]
    out = []
    prior = []
    for q in ordered:
        dispatch = ns(q, "dispatch")
        queue = ns(q, "queue_entry")
        protocol = protocol_name(q.get("protocol", session.get("protocol", arm)))
        route = route_of(q)
        blockers = [p for p in prior if protocol == "SERIAL" or route_of(p) == route or
                    frozenset({(q["task"], route), (p["task"], route_of(p))}) != PAIR]
        ready = max([queue] + [ns(p, "available") if ns(p, "available") is not None
                              else ns(p, "lane_available") for p in blockers])
        if ready > dispatch:
            return [], ["observed overlap contradicts declared protocol/owner occupancy"]
        out.append({"request_id": q["request_id"], "ready_ns": ready,
                    "dispatch_ns": dispatch, "gap_ns": dispatch - ready,
                    "task": q["task"], "route": route, "protocol": protocol,
                    "evidence": "COMPLETE_QUEUE_OWNER_EVENT_CENSUS",
                    "public_state": _training_public_state(session, q)})
        prior.append(q)
    return out, []


def _quantile(values, p):
    values = sorted(values)
    if not values:
        return None
    return values[round((len(values) - 1) * p)]


class ProtocolTimingModel:
    def __init__(self, samples, admissions, gaps, ledger, *, family, estimator, feature_mode, seed, strict, bank_mode):
        self.samples = tuple(samples)
        self.admissions = tuple(admissions)
        self.gaps = tuple(gaps)
        self.ledger = copy.deepcopy(ledger)
        self.family, self.estimator, self.feature_mode, self.seed, self.strict = family, estimator, feature_mode, seed, strict
        self.bank_mode = bank_mode
        self.metadata = {"schema": SCHEMA, "family": family, "estimator": estimator,
                         "feature_mode": feature_mode, "seed": seed, "strict_binding": strict,
                         "bank_mode": bank_mode,
                         "timing_qualified": strict, "model_builds": 1, "parameter_fits": 0,
                         "optimizer_steps": 0, "NN_training": 0,
                         "source_samples": len(samples), "admission_samples": len(admissions),
                         "redispatch_samples": len(gaps), "thermal_feedback": "UNIDENTIFIED_NOT_MODELED",
                         "roles": "OBSERVED_DEVELOPMENT_ONLY", "model_digest": digest(samples)}

    def _pool(self, samples, context, task, route, protocol, state=None):
        key = digest(context)
        stratum = feature_stratum(state or {}, self.feature_mode)
        pool = [s for s in samples if self._context_matches(s, context, key) and s["task"] == task
                and s["route"] == route and s["protocol"] == protocol and
                (self.feature_mode == "exact_public" or tuple(s["stratum"]) == stratum)]
        exact = [s for s in pool if s["context_sha256"] == key]
        if exact:
            pool = exact
        if not pool:
            raise UnsupportedContext("no exact measured context/protocol/public-feature pool")
        return sorted(pool, key=lambda s: s["sample_id"])

    def _context_matches(self, sample, context, exact_digest=None):
        if sample["context_sha256"] == (exact_digest or digest(context)):
            return True
        if self.bank_mode != "TASK_BINDING_TRANSFER":
            return False
        return {k: v for k, v in sample["context"].items() if k != "bank"} == {k: v for k, v in context.items() if k != "bank"}

    def _select(self, pool, potential_key, label, target):
        # Uniform potential is shared across policies. Exact source index agrees
        # only when the eligible pool agrees; changed support is disclosed.
        latent = digest([SCHEMA, self.seed, potential_key, label])
        if self.estimator == "empirical":
            index = int(latent, 16) % len(pool)
        else:
            median = statistics.median(target(s) for s in pool)
            index = min(range(len(pool)), key=lambda i: (abs(target(pool[i]) - median), pool[i]["sample_id"]))
        return pool[index], {"potential_sha256": latent, "sample_index": index,
                             "pool_sha256": digest([s["sample_id"] for s in pool]),
                             "support_requests": len(pool),
                             "support_sessions": len({s["session_id"] for s in pool}),
                             "support_cohorts": len({s["cohort_id"] for s in pool}),
                             "uncertainty_unit": "whole_session/cohort; quantiles are descriptive",
                             "validation_status": "UNVALIDATED"}

    def draw(self, action, public_state, protocol_intent, reservation, potential_key):
        snapshot = public_snapshot(public_state)
        if not isinstance(reservation, Reservation) or digest(snapshot) != reservation.public_state_sha256:
            raise ValueError("reservation must be locked against the current public state before draw")
        protocol = protocol_name(protocol_intent)
        member = (action["request_id"], action["task"], action["route"])
        if member not in reservation.members or protocol != reservation.protocol:
            raise ValueError("draw does not match prior immutable reservation")
        pool = self._pool(self.samples, action["context"], action["task"], action["route"], protocol, snapshot)
        sample, selection = self._select(pool, potential_key, "service", lambda s: sum(s["stages_ns"]))
        offsets = dict(zip(BOUNDARIES, _cumsum(sample["stages_ns"])))
        offsets["response"] = offsets["output_ready" if action["task"] == "C" else "persist_complete"]
        return {"schema": SCHEMA, "sample_id": sample["sample_id"], "stages_ns": sample["stages_ns"],
                "offsets_ns": offsets, "context": copy.deepcopy(action["context"]),
                "protocol": protocol, "reservation_id": reservation.reservation_id,
                "bank_extrapolation": sample["context"].get("bank") != action["context"].get("bank"),
                "selection": selection, "source": copy.deepcopy(sample["source"]),
                "descriptive_intervals_ns": {b: [_quantile([_cumsum(s["stages_ns"])[i] for s in pool], .05),
                                                   _quantile([_cumsum(s["stages_ns"])[i] for s in pool], .95)]
                                              for i, b in enumerate(BOUNDARIES)},
                "causal_limits": ["protocol is precommitted, not selected by future realized overlap",
                                  "empirical source association is not an interference causal estimate",
                                  "whole-vector individual source preserved; no phase surgery"]}

    def admission(self, context, task, potential_key, *, protocol="SERIAL"):
        """Canonical route is explicit and independent of chosen policy route."""
        route = "GPU" if task == "C" else "CPU"
        context = context_for_route(context, task, route)
        # Admission strata cannot depend on queue at later dispatch.
        key = digest(context)
        pool = sorted([s for s in self.admissions if self._context_matches(s, context, key) and
                       s["task"] == task and s["route"] == route and s["protocol"] == protocol_name(protocol)],
                      key=lambda s: s["sample_id"])
        exact = [s for s in pool if s["context_sha256"] == key]
        if exact:
            pool = exact
        if not pool:
            raise UnsupportedContext("canonical predecision admission support UNKNOWN")
        selected, selection = self._select(pool, potential_key, "admission", lambda s: sum(s["admission_ns"]))
        return {"scheduled_to_actual_ns": selected["admission_ns"][0],
                "actual_to_queue_ns": selected["admission_ns"][1], "canonical_route": route,
                "protocol": protocol_name(protocol), "sample_id": selected["sample_id"], "selection": selection}

    def redispatch(self, action, public_state, potential_key, *, mode="MEASURED", zero_baseline_id=None):
        if mode == "ZERO_EXPLICIT_BASELINE":
            if not isinstance(zero_baseline_id, str) or not zero_baseline_id:
                raise ValueError("explicit registered ideal-zero baseline identifier required")
            return {"delay_ns": 0, "evidence": "REGISTERED_IDEAL_ZERO_ASSUMPTION",
                    "baseline_id": zero_baseline_id, "physical_latency_claim": False}
        if mode != "MEASURED":
            raise ValueError("redispatch mode must be MEASURED or ZERO_EXPLICIT_BASELINE")
        try:
            pool = self._pool(self.gaps, action["context"], action["task"], action["route"],
                              action["protocol"], public_snapshot(public_state))
        except UnsupportedContext:
            return {"delay_ns": None, "evidence": "UNKNOWN_NO_EXACT_READY_IDLE_GAP_SUPPORT"}
        selected, selection = self._select(pool, potential_key, "redispatch", lambda s: s["gap_ns"])
        return {"delay_ns": selected["gap_ns"], "evidence": selected["evidence"],
                "sample_id": selected["sample_id"], "selection": selection,
                "physical_latency_claim": False}

    def nominal(self, context, task, route, protocol="SERIAL", state=None):
        pool = self._pool(self.samples, context, task, route, protocol_name(protocol), state)
        response_index = 1 if task == "C" else 2
        return {"occupancy_ns": round(statistics.median(sum(s["stages_ns"]) for s in pool)),
                "response_ns": round(statistics.median(sum(s["stages_ns"][:response_index + 1]) for s in pool)),
                "support_requests": len(pool), "energy_proxy_j": None,
                "thermal_feedback": None, "validation_status": "UNVALIDATED"}

    def draw_latent_serial(self, action, public_state, potential_key):
        """Whole observed SERIAL work vector for a rolling progress candidate.

        Unlike exact protocol replay, this is a declared modeling coordinate.
        Later concurrency changes future progress rates, never past work or a
        completed phase. Latent vector selection uses only present public input.
        """
        snapshot = public_snapshot(public_state)
        pool = self._pool(self.samples, action["context"], action["task"], action["route"], "SERIAL", snapshot)
        selected, selection = self._select(pool, potential_key, "service", lambda s: sum(s["stages_ns"]))
        return {"sample_id": selected["sample_id"], "stages_ns": selected["stages_ns"],
                "selection": selection, "source": copy.deepcopy(selected["source"]),
                "bank_extrapolation": selected["context"].get("bank") != action["context"].get("bank"),
                "latent_boundary_descriptive_intervals_ns": {
                    b: [_quantile([_cumsum(s["stages_ns"])[i] for s in pool], .05),
                        _quantile([_cumsum(s["stages_ns"])[i] for s in pool], .95)]
                    for i, b in enumerate(BOUNDARIES)},
                "response_prediction_interval_ns": None,
                "uncertainty": "rolling occupancy/rate uncertainty requires registered joint simulation; marginal support ranges are not a response CI",
                "latent_work_coordinate": "OBSERVED_SERIAL_NS_NOT_PHYSICAL_WORK"}

    def progress_rates(self, action, public_state, *, mode="DATA_DERIVED_PROGRESS", unidentified="ERROR"):
        """SERIAL/CG_DC same-stage medians define a diagnostic future rate.

        These observational ratios are a modeling assumption, not identified
        causal slowdown. Stage-specific ratios are used where both medians are
        positive. A zero-width stage inherits the whole-occupancy ratio with an
        explicit flag. No ratio is selected from future realized overlap.
        """
        if mode == "SERIAL_INDEPENDENT":
            return {"rates": [1.] * 5, "evidence": "EXPLICIT_SERIAL_INDEPENDENT_BASELINE",
                    "causal_interference_identified": False, "parameter_fits": 0}
        if mode != "DATA_DERIVED_PROGRESS" or unidentified not in ("ERROR", "SERIAL_INDEPENDENT"):
            raise ValueError("unregistered progress/fallback mode")
        snapshot = public_snapshot(public_state)
        try:
            serial = self._pool(self.samples, action["context"], action["task"], action["route"], "SERIAL", snapshot)
            paired = self._pool(self.samples, action["context"], action["task"], action["route"], "CG_DC", snapshot)
        except UnsupportedContext:
            if unidentified == "ERROR":
                raise UnsupportedContext("CG_DC progress ratio UNIDENTIFIED")
            return {"rates": [1.] * 5, "evidence": "UNIDENTIFIED_EXPLICIT_SERIAL_INDEPENDENT_FALLBACK",
                    "causal_interference_identified": False, "parameter_fits": 0}
        whole = statistics.median(sum(s["stages_ns"]) for s in serial) / statistics.median(sum(s["stages_ns"]) for s in paired)
        rates, flags, ranges = [], [], []
        for i in range(5):
            a = statistics.median(s["stages_ns"][i] for s in serial)
            b = statistics.median(s["stages_ns"][i] for s in paired)
            rates.append(a / b if a > 0 and b > 0 else whole)
            lower_a = _quantile([s["stages_ns"][i] for s in serial], .05)
            upper_a = _quantile([s["stages_ns"][i] for s in serial], .95)
            lower_b = _quantile([s["stages_ns"][i] for s in paired], .05)
            upper_b = _quantile([s["stages_ns"][i] for s in paired], .95)
            ranges.append([lower_a / upper_b, upper_a / lower_b] if lower_b > 0 and upper_b > 0 else None)
            if a <= 0 or b <= 0:
                flags.append({"stage": STAGES[i], "assumption": "WHOLE_OCCUPANCY_UNIFORM_RATIO_FOR_ZERO_MEDIAN_STAGE"})
        return {"rates": rates, "evidence": "OBSERVED_SAME_CONTRACT_SERIAL_CG_DC_STAGE_MEDIAN_RATIO",
                "serial_sessions": len({s["session_id"] for s in serial}),
                "paired_sessions": len({s["session_id"] for s in paired}),
                "support_cohorts": sorted({s["cohort_id"] for s in serial + paired}),
                "support_bank_ids": sorted({str(s["context"]["bank"]) for s in serial + paired}),
                "stage_ratio_assumptions": flags, "causal_interference_identified": False,
                "descriptive_stage_rate_ranges": ranges,
                "uncertainty": "UNVALIDATED_OBSERVATIONAL_PROTOCOL_ASSOCIATION",
                "parameter_fits": 0}


def _cumsum(values):
    result, running = [], 0
    for x in values:
        running += x
        result.append(running)
    return result


def build_timing_candidate(sessions, family="combined", estimator="empirical",
                           feature_mode="exact_public", seed=0, strict=True, bank_mode="EXACT"):
    """Build empirical support; one model build, zero parameter/optimizer fits.

    This is a development operation requiring root registration before invocation.
    Each candidate/fold build is independently counted even though it optimizes
    no parameters. Failed/missing/unknown rows remain in the exclusion ledger.
    """
    if family not in ("old", "m8", "combined") or estimator not in ("empirical", "median"):
        raise ValueError("unknown candidate family/estimator")
    if feature_mode not in FEATURE_MODES or type(seed) is not int or seed < 0:
        raise ValueError("invalid public feature mode/seed")
    if bank_mode not in ("EXACT", "TASK_BINDING_TRANSFER"):
        raise ValueError("unregistered bank transfer mode")
    samples, admissions, gaps, ledger = [], [], [], []
    seen = set()
    for session in sessions:
        sid, cohort = session.get("session_id"), session.get("cohort_id")
        if not sid or not cohort:
            ledger.append({"session_id": sid, "target": "all", "reason": "missing whole-session/cohort identity"})
            continue
        if family != "combined" and session.get("source_family") != family:
            ledger.append({"session_id": sid, "target": "all", "reason": "candidate family exclusion"})
            continue
        extracted_gaps, gap_unknown = observed_ready_idle_gaps(session)
        gap_by_id = {x["request_id"]: x for x in extracted_gaps}
        if gap_unknown:
            ledger.append({"session_id": sid, "target": "redispatch", "reason": gap_unknown})
        for q in session.get("requests", []):
            rid = q.get("request_id")
            identity = (sid, rid)
            if identity in seen:
                ledger.append({"session_id": sid, "request_id": rid, "target": "all", "reason": "duplicate identity"})
                continue
            seen.add(identity)
            try:
                if not rid or (q.get("task"), route_of(q)) not in ROUTES:
                    raise UnsupportedContext("missing identity/unsupported route")
                context, unknown = context_of(session, q, strict)
                protocol = protocol_name(q.get("protocol", session.get("protocol", session.get("arm"))))
                if protocol == "CG_DC" and (q["task"], route_of(q)) not in PAIR:
                    raise UnsupportedContext("not a measured CG_DC member")
                common = {"sample_id": str(sid) + ":" + rid, "session_id": sid, "cohort_id": cohort,
                          "task": q["task"], "route": route_of(q), "protocol": protocol,
                          "context_sha256": digest(context), "context": context,
                          "stratum": feature_stratum(_training_public_state(session, q), feature_mode),
                          "source": {"session_id": sid, "cohort_id": cohort,
                                     "generation": session.get("source_generation"),
                                     "source_family": session.get("source_family"),
                                     "provenance": copy.deepcopy(session.get("provenance")),
                                     "request_provenance": copy.deepcopy(q.get("provenance")),
                                     "unknown_bindings": unknown, "role": "OBSERVED_DEVELOPMENT"}}
            except (ValueError, KeyError, TypeError) as exc:
                ledger.append({"session_id": sid, "request_id": rid, "target": "all", "reason": str(exc)})
                continue
            try:
                samples.append({**common, "stages_ns": _whole_vector(q)})
            except (ValueError, TypeError, KeyError) as exc:
                ledger.append({"session_id": sid, "request_id": rid, "target": "timing", "reason": str(exc)})
            a, b, c = ns(q, "scheduled_arrival"), ns(q, "actual_arrival"), ns(q, "queue_entry")
            if a is not None and b is not None and c is not None and a <= b <= c:
                admissions.append({**common, "admission_ns": (b - a, c - b)})
            else:
                ledger.append({"session_id": sid, "request_id": rid, "target": "admission", "reason": "missing/invalid scheduled-actual-queue chain"})
            if rid in gap_by_id:
                gaps.append({**common, **{k: gap_by_id[rid][k] for k in ("gap_ns", "evidence")}})
    return ProtocolTimingModel(samples, admissions, gaps, ledger, family=family, estimator=estimator,
                               feature_mode=feature_mode, seed=seed, strict=strict, bank_mode=bank_mode)


def grouped_validate_timing(sessions, candidate_grid, *, build_cap, baseline_model=None):
    """Whole-cohort posthoc CV. No row bootstrap, winner selection, or PASS.

    Descriptive 5/95 support intervals are not confidence intervals. Queue,
    overlap, deadline and on-time *counterfactual* validation belongs to a
    separately registered simulator call; it is never computed by borrowing
    measured dispatch/response times here. Baseline comparisons must use the
    same heldout requests via the explicit frozen baseline callback.
    """
    cohorts = sorted({s["cohort_id"] for s in sessions})
    needed = len(candidate_grid) * len(cohorts)
    if type(build_cap) is not int or needed > build_cap:
        raise RuntimeError("registered timing model-build budget exceeded before execution")
    rows, builds = [], 0
    for configuration in candidate_grid:
        for cohort in cohorts:
            train = [s for s in sessions if s["cohort_id"] != cohort]
            held = [s for s in sessions if s["cohort_id"] == cohort]
            model = build_timing_candidate(train, **configuration)
            builds += 1
            for session in held:
                actual_gaps, gap_unknown = observed_ready_idle_gaps(session)
                heldout_gaps = {g["request_id"]: g for g in actual_gaps}
                for q in session.get("requests", []):
                    row = {"candidate": digest(configuration), "configuration": configuration,
                           "session_id": session["session_id"], "cohort_id": cohort,
                           "request_id": q.get("request_id"), "task": q.get("task"),
                           "bank": session.get("bank"), "protocol": q.get("protocol", session.get("protocol")),
                           "source_generation": session.get("source_generation"),
                           "status": "UNVALIDATED", "prediction_error_ns": None}
                    row["redispatch_error_ns"] = None
                    row["redispatch_unknown"] = gap_unknown or None
                    try:
                        context, _ = context_of(session, q, model.strict)
                        protocol = protocol_name(q.get("protocol", session.get("protocol", session.get("arm"))))
                        pool = model._pool(model.samples, context, q["task"], route_of(q), protocol,
                                           _training_public_state(session, q))
                        if len({x["session_id"] for x in pool}) < 2 or len({x["cohort_id"] for x in pool}) < 2:
                            raise UnsupportedContext("fewer than two independent training sessions/cohorts")
                        observed = _whole_vector(q)
                        response_i = 1 if q["task"] == "C" else 2
                        # Medoid selection remains one whole observed vector.
                        chosen, selected = model._select(pool, [session["session_id"], q.get("ordinal"), q.get("request_id")],
                                                         "service", lambda x: sum(x["stages_ns"]))
                        predicted = chosen["stages_ns"]
                        row.update(status="POSTHOC_DEVELOPMENT_PREDICTION", selection=selected,
                                   stage_error_ns=[p - a for p, a in zip(predicted, observed)],
                                   occupancy_error_ns=sum(predicted) - sum(observed),
                                   prediction_error_ns=sum(predicted[:response_i + 1]) - sum(observed[:response_i + 1]))
                        if baseline_model is not None:
                            baseline = baseline_model(session, q, excluded_cohort=cohort)
                            row["baseline_response_error_ns"] = baseline["response_ns"] - sum(observed[:response_i + 1])
                            row["paired_absolute_error_change_ns"] = abs(row["prediction_error_ns"]) - abs(row["baseline_response_error_ns"])
                        if q.get("request_id") in heldout_gaps:
                            try:
                                gap_pool = model._pool(model.gaps, context, q["task"], route_of(q), protocol,
                                                       _training_public_state(session, q))
                                if len({x["cohort_id"] for x in gap_pool}) < 2:
                                    raise UnsupportedContext("sparse independent redispatch support")
                                gap, _ = model._select(gap_pool, [session["session_id"], q.get("ordinal"), q.get("request_id")],
                                                       "redispatch", lambda x: x["gap_ns"])
                                row["redispatch_error_ns"] = gap["gap_ns"] - heldout_gaps[q["request_id"]]["gap_ns"]
                            except UnsupportedContext as exc:
                                row["redispatch_unknown"] = str(exc)
                    except (ValueError, KeyError, TypeError) as exc:
                        row["unknown_reason"] = str(exc)
                    rows.append(row)
    strata = defaultdict(list)
    for row in rows:
        if row["prediction_error_ns"] is not None:
            strata[(row["candidate"], row["bank"], row["task"], row["protocol"], row["source_generation"])].append(row)
    scores = [{"stratum": key, "n_requests": len(value),
               "n_sessions": len({x["session_id"] for x in value}),
               "mean_absolute_response_error_ns": statistics.mean(abs(x["prediction_error_ns"]) for x in value),
               "worst_absolute_response_error_ns": max(abs(x["prediction_error_ns"]) for x in value),
               "paired_signs": dict(Counter("worse" if x.get("paired_absolute_error_change_ns", 0) > 0 else
                                           "better" if x.get("paired_absolute_error_change_ns", 0) < 0 else "tie_or_unavailable"
                                           for x in value))} for key, value in strata.items()]
    return {"schema": SCHEMA + "-CV", "role": "POSTHOC_MODEL_DEVELOPMENT",
            "rows": rows, "strata": scores, "all_heldout_retained": True,
            "worst_stratum_mae_ns": max((x["mean_absolute_response_error_ns"] for x in scores), default=None),
            "model_builds": builds, "parameter_fits": 0, "optimizer_steps": 0,
            "predictive_accuracy_PASS": None, "selection": None,
            "queue_overlap_deadline_validation": "REQUIRES_SEPARATELY_REGISTERED_SIMULATOR",
            "confidence_interval": None}
