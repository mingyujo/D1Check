"""A24 AP activity-history candidates. SOURCE ONLY; no import-time fitting.

AP is fitted directly to measured activity and actual past AP. No electrical
input, invented ambient, thermal->timing, or thermal->power connection exists.
Time constants are statistical basis choices, not identified hardware constants.
Different compatibility domains get different activity/equilibrium coefficients.
"""
from __future__ import annotations

import copy
import hashlib
import itertools
import json
import math

import numpy as np

VERSION = "A24_AP_ACTIVITY_HISTORY_CANDIDATE_V1"
STATES = ("classification_CPU", "detection_CPU", "classification_GPU",
          "classification_GPU+detection_CPU")
LOCAL_FEATURES = ("unknown_equilibrium", "known_ambient_offset", "past_AP_slope_memory") + STATES
MODES = ("old-only", "m8-only", "combined")


def _sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def _finite(value):
    return value is not None and not isinstance(value, bool) and math.isfinite(float(value))


def candidate_grid():
    return [dict(cooling_tau_s=float(a), activity_tau_s=float(b), ridge=float(c),
                 pre_slope_tau_s=30., maximum_iterations=20000, tolerance=1e-9)
            for a, b, c in itertools.product((60., 180., 600.), (10., 30., 120.), (.1, 1., 10.))]


def _config(config):
    c = dict(config)
    for name in ("cooling_tau_s", "activity_tau_s", "pre_slope_tau_s"):
        if not _finite(c.get(name)) or float(c[name]) <= 0:
            raise ValueError("positive registered thermal basis time required: " + name)
    if not _finite(c.get("ridge")) or float(c["ridge"]) <= 0:
        raise ValueError("strictly positive registered ridge required")
    c.setdefault("maximum_iterations", 20000)
    c.setdefault("tolerance", 1e-9)
    return c


def _domain(session):
    compatibility = session.get("compatibility", {})
    domain = compatibility.get("ap_activity_domain")
    if domain:
        return str(domain)
    # A missing compatibility assertion never silently pools old and M8.
    return "UNVERIFIED:" + ":".join(str(session.get(k, "UNKNOWN")) for k in
                                    ("source_family", "source_generation", "protocol", "cohort_id"))


def _state(labels):
    labels = sorted(labels)
    key = "+".join(labels)
    if not key:
        return "idle"
    if key not in STATES:
        raise ValueError("unsupported A24 activity combination: " + key)
    return key


def activity_segments(session):
    """Exact DISPATCH->AVAILABLE ownership or original aggregate state intervals."""
    aggregate = session.get("state_intervals", [])
    owners = session.get("owner_intervals", [])
    if aggregate and owners:
        raise ValueError("choose one original activity representation, not both")
    if aggregate:
        output, last = [], -math.inf
        for row in aggregate:
            start, end = float(row["start_s"]), float(row["end_s"])
            state = "+".join(sorted(row["state"].replace(":", "_").split("+")))
            state = "idle" if state in ("idle", "resident_idle") else state
            if not all(map(math.isfinite, (start, end))) or end <= start or start < last:
                raise ValueError("aggregate activity clock/order/overlap")
            if state != "idle" and state not in STATES:
                raise ValueError("unsupported aggregate A24 activity: " + state)
            if last != -math.inf and start > last + 1e-8:
                raise ValueError("activity gap cannot be filled with invented idle")
            output.append(dict(start_s=start, end_s=end, state=state))
            last = end
        return output
    coverage = session.get("activity_coverage_s")
    if not coverage or len(coverage) != 2:
        raise ValueError("explicit activity coverage required even for idle")
    lo, hi = map(float, coverage)
    if not math.isfinite(lo + hi) or hi <= lo:
        raise ValueError("activity coverage order")
    events = []
    seen = set()
    tasks = {"C": "classification", "D": "detection", "classification": "classification", "detection": "detection"}
    for row in owners:
        rid = str(row["request_id"])
        if rid in seen:
            raise ValueError("duplicate request owner")
        seen.add(rid)
        a, b = float(row["start_s"]), float(row["end_s"])
        if not lo <= a < b <= hi:
            raise ValueError("owner outside actual activity coverage")
        label = tasks[row["task"]] + "_" + row["route"]
        events.extend(((a, 1, rid, label), (b, 0, rid, label)))
    current, cursor, output = {}, lo, []
    for t, on, rid, label in sorted(events):
        if t > cursor:
            output.append(dict(start_s=cursor, end_s=t, state=_state(current.values())))
            cursor = t
        if on:
            current[rid] = label
            if len(current) > 2 or len(set(current.values())) != len(current):
                raise ValueError("unsupported same-lane or >2 ownership")
            _state(current.values())
        else:
            if rid not in current:
                raise ValueError("AVAILABLE without owner")
            del current[rid]
    if cursor < hi:
        output.append(dict(start_s=cursor, end_s=hi, state=_state(current.values())))
    return output


def _initial(session):
    origin = float(session.get("forecast_origin_s", 0.))
    ap, time = session.get("initial_ap_c"), session.get("initial_ap_time_s")
    if not _finite(ap) or not _finite(time):
        raise ValueError("UNKNOWN_INITIAL_AP")
    time = float(time)
    hi = session.get("initial_ap_hi_s", time)
    if not _finite(hi) or not time <= float(hi) <= origin:
        raise ValueError("future or unfinished initial AP read")
    # Only explicit past AP rows may contribute to the initial slope. Post-origin
    # labels are never consulted even if the caller accidentally passes them.
    past = []
    for row in session.get("observations", []):
        end = row.get("hi_s")
        if (row.get("channel") == "AP" and row.get("initial_eligible", False) and
                _finite(end) and float(end) <= float(hi) and _finite(row.get("ap_c")) and
                float(row["t_s"]) <= time):
            past.append((float(row["t_s"]), float(row["ap_c"])))
    past.sort()
    slope = 0.
    slope_known = False
    use = [(t, value) for t, value in past if time - 30. <= t <= time]
    if len(use) >= 2 and use[-1][0] - use[0][0] >= 5.:
        t = np.asarray([p[0] for p in use]); y = np.asarray([p[1] for p in use])
        centered = t - t.mean()
        slope = float(centered @ (y - y.mean()) / (centered @ centered))
        slope_known = True
    return float(ap), time, float(hi), slope, slope_known


def _convolution(segments, times, tau, start_at):
    """Normalized exponential convolution, analytic on every original interval."""
    x = np.zeros((len(times), len(STATES)), dtype=float)
    times = np.asarray(times, dtype=float)
    for row in segments:
        if row["state"] == "idle":
            continue
        a, b = max(start_at, row["start_s"]), row["end_s"]
        if b <= a:
            continue
        # Integral_a^min(t,b) exp(-(t-s)/tau)/tau ds, exactly zero t<=a.
        u = np.maximum(0., times - a)
        v = np.maximum(0., times - b)
        x[:, STATES.index(row["state"])] += np.exp(-v / tau) - np.exp(-u / tau)
    return x


def features(session, times, config):
    """Pure prediction design: no future AP values, current, energy, or policy ID."""
    config = _config(config)
    if session.get("device") != "A24":
        raise ValueError("A24 only; no S26 transfer")
    times = np.asarray(times, dtype=float)
    if times.ndim != 1 or not np.isfinite(times).all() or np.any(np.diff(times) < 0):
        raise ValueError("ordered finite query times required")
    initial, anchor, hi, slope, slope_known = _initial(session)
    if len(times) and np.min(times) < max(anchor, hi):
        raise ValueError("queries before completed actual initial AP")
    segments = activity_segments(session)
    origin = float(session.get("forecast_origin_s", 0.))
    if not segments or segments[0]["start_s"] > origin or (len(times) and
            (segments[-1]["end_s"] < max(times) or min(times) < segments[0]["start_s"])):
        raise ValueError("UNKNOWN_ACTIVITY_COVERAGE")
    elapsed = times - anchor
    decay = np.exp(-elapsed / config["cooling_tau_s"])
    equil = 1. - decay
    ambient = session.get("ambient_c")
    known_ambient = _finite(ambient)
    baseline = initial * decay
    if known_ambient:
        baseline += float(ambient) * equil
    # Real recorded prehistory can contribute to the activity state at anchor.
    # State before the first recorded interval remains unidentified and is not
    # called a zero-temperature/zero-heat initial state.
    history_start = float(segments[0]["start_s"])
    z = _convolution(segments, times, config["activity_tau_s"], history_start)
    z0 = _convolution(segments, [anchor], config["activity_tau_s"], history_start)[0]
    anchored_activity = z - decay[:, None] * z0[None, :]
    momentum = slope * config["pre_slope_tau_s"] * (-np.expm1(-elapsed / config["pre_slope_tau_s"])) * decay
    x = np.column_stack((np.zeros(len(times)) if known_ambient else equil,
                         equil if known_ambient else np.zeros(len(times)), momentum, anchored_activity))
    return dict(matrix=x, baseline=baseline, domain=_domain(session),
                initial_ap_c=initial, anchor_s=anchor, input_latest_hi_s=hi,
                pre_slope_c_per_s=slope if slope_known else None,
                real_activity_state_at_anchor=z0.tolist(),
                activity_history_start_s=history_start,
                activity_gap_after_initial_anchor=history_start > anchor,
                prehistory_before_recorded_start="UNKNOWN_ABSORBED_ONLY_PARTLY_BY_AP_ANCHOR",
                ambient_c=float(ambient) if known_ambient else None,
                states_present=sorted({r["state"] for r in segments if r["state"] != "idle"}))


def _targets(session):
    origin = float(session.get("forecast_origin_s", 0.))
    rows = [r for r in session.get("observations", []) if r.get("channel") == "AP" and
            _finite(r.get("ap_c")) and float(r["t_s"]) > origin]
    rows.sort(key=lambda r: float(r["t_s"]))
    if len({float(r["t_s"]) for r in rows}) != len(rows):
        raise ValueError("duplicate AP time; resolve raw conflict before fitting")
    return rows


def _activity_signature(session, end_s):
    start = float(session.get("forecast_origin_s", 0.))
    duration = max(0., float(end_s) - start)
    segments = activity_segments(session)
    fractions = {}
    for state in ("idle",) + STATES:
        exposure = sum(max(0., min(float(end_s), r["end_s"]) - max(start, r["start_s"]))
                       for r in segments if r["state"] == state)
        fractions[state] = exposure / duration if duration > 0 else 0.
    return fractions


def _eligible(session):
    eligibility = session.get("target_eligibility", {})
    return bool(eligibility.get("ap_fit", eligibility.get("AP", False)))


def fit(sessions, config, on_fit=None):
    """One bounded deterministic linear fit; callback runs before the solve."""
    config = _config(config)
    training, excluded = [], []
    for session in sessions:
        if not _eligible(session):
            excluded.append(dict(session_id=session["session_id"], reason="AP target not explicitly eligible"))
            continue
        target = _targets(session)
        if len(target) < 2:
            excluded.append(dict(session_id=session["session_id"], reason="fewer than two actual AP target samples"))
            continue
        try:
            f = features(session, [r["t_s"] for r in target], config)
        except ValueError as error:
            excluded.append(dict(session_id=session["session_id"], reason=str(error)))
            continue
        training.append((session, target, f))
    if not training:
        return dict(version=VERSION, status="UNAVAILABLE_NO_ELIGIBLE_TRAINING", exclusions=excluded)
    domains = sorted({f["domain"] for _, _, f in training})
    names = [domain + "::" + name for domain in domains for name in LOCAL_FEATURES]
    xrows, yrows, weights = [], [], []
    # Equal total mass per session, then equal mass per actual sample. Long
    # trajectories retain all rows without becoming thousands of independent sessions.
    for session, target, f in training:
        x = np.zeros((len(target), len(names)))
        start = domains.index(f["domain"]) * len(LOCAL_FEATURES)
        x[:, start:start + len(LOCAL_FEATURES)] = f["matrix"]
        xrows.append(x)
        yrows.append(np.asarray([r["ap_c"] for r in target]) - f["baseline"])
        weights.extend([1. / (len(training) * len(target))] * len(target))
    x, y, weights = np.vstack(xrows), np.concatenate(yrows), np.asarray(weights)
    scale = np.sqrt(np.sum(weights[:, None] * x * x, axis=0))
    active = scale > 1e-12
    safe = np.where(active, scale, 1.)
    z = x / safe
    prior = np.zeros(len(names))
    lower, upper = np.full(len(names), -np.inf), np.full(len(names), np.inf)
    for domain in domains:
        offset = domains.index(domain) * len(LOCAL_FEATURES)
        initial_values = [f["initial_ap_c"] for _, _, f in training if f["domain"] == domain]
        prior[offset] = float(np.median(initial_values))
        lower[offset], upper[offset] = -20., 100.
        lower[offset + 1], upper[offset + 1] = -40., 60.
        lower[offset + 2], upper[offset + 2] = 0., 2.
        lower[offset + 3:offset + len(LOCAL_FEATURES)] = 0.
    # Dimensionless penalty after weighted column scaling, around a training-only
    # AP-derived equilibrium prior. That prior is never called measured ambient.
    alpha = float(config["ridge"])
    target_prior = prior * safe
    lo, hi = lower * safe, upper * safe
    beta = target_prior.copy()
    beta[~active] = 0.
    rootw = np.sqrt(weights)
    zw, yw = z * rootw[:, None], y * rootw
    gram, rhs = zw.T @ zw + alpha * np.eye(len(names)), zw.T @ yw + alpha * target_prior
    if on_fit is not None:
        on_fit("A24_AP_RIDGE:" + _sha(config) + ":" + _sha(sorted(s["session_id"] for s, _, _ in training)))
    converged = False
    iterations = 0
    for iterations in range(1, int(config["maximum_iterations"]) + 1):
        old = beta.copy()
        for index in np.flatnonzero(active):
            value = (rhs[index] - gram[index] @ beta + gram[index, index] * beta[index]) / gram[index, index]
            beta[index] = min(hi[index], max(lo[index], value))
        if np.max(np.abs(beta - old)) <= float(config["tolerance"]) * (1. + np.max(np.abs(beta))):
            converged = True
            break
    coefficients = beta / safe
    singular = np.linalg.svd(zw[:, active], compute_uv=False) if active.any() else np.asarray([])
    rank = int(np.linalg.matrix_rank(zw[:, active])) if active.any() else 0
    support = {domain: sorted({state for _, _, f in training if f["domain"] == domain for state in f["states_present"]}) for domain in domains}
    signatures = [_activity_signature(s, t[-1]["t_s"]) for s, t, _ in training]
    artifacts = dict(version=VERSION, status="EXPERIMENTAL_FIT" if converged else "UNAVAILABLE_SOLVER_NOT_CONVERGED",
                     config=config, domains=domains, feature_names=names,
                     coefficients=coefficients.tolist(),
                     coefficient_units=[unit for _ in domains for unit in ("degree_C", "degree_C", "dimensionless", "degree_C", "degree_C", "degree_C", "degree_C")],
                     feature_units="dimensionless except past_AP_slope_memory in degree_C",
                     coefficient_constraints=dict(activity_nonnegative=True, initial_slope_gain=[0., 2.]),
                     domains_share_activity_coefficients=False, domain_activity_support=support,
                     domain_sources={domain: sorted({s["source_family"] for s, _, f in training if f["domain"] == domain}) for domain in domains},
                     domain_session_counts={domain: sum(f["domain"] == domain for _, _, f in training) for domain in domains},
                     training_envelope=dict(initial_AP_c=[min(f["initial_ap_c"] for _, _, f in training), max(f["initial_ap_c"] for _, _, f in training)],
                                            duration_s=[min(float(t[-1]["t_s"]) - f["anchor_s"] for _, t, f in training), max(float(t[-1]["t_s"]) - f["anchor_s"] for _, t, f in training)],
                                            activity_fractions={state: [min(row[state] for row in signatures), max(row[state] for row in signatures)]
                                                                for state in ("idle",) + STATES}),
                     active_columns=active.tolist(), column_scale=safe.tolist(), prior=prior.tolist(),
                     prior_role="training_AP_median_statistical_equilibrium_not_ambient",
                     rank=rank, active_dimension=int(active.sum()),
                     scaled_singular_values=singular.tolist(),
                     scaled_condition=float(singular[0] / singular[-1]) if len(singular) and singular[-1] > 1e-12 else None,
                     unregularized_identifiable=bool(rank == int(active.sum())),
                     converged=converged, iterations=iterations,
                     training_sessions=[s["session_id"] for s, _, _ in training],
                     training_cohorts=sorted({s["cohort_id"] for s, _, _ in training}),
                     training_sources=sorted({s["source_family"] for s, _, _ in training}),
                     training_bindings=[dict(session_id=s["session_id"], provenance=s.get("provenance", {}),
                                             target_rows=len(t), target_window_s=[t[0]["t_s"], t[-1]["t_s"]])
                                        for s, t, _ in training], exclusions=excluded,
                     assumptions=["statistical_basis_not_identified_physical_constants", "unknown_prerecording_heat_remains_unidentified",
                                  "observational_activity_confounding_no_causal_hardware_claim"],
                     thermal_to_timing=False, thermal_to_power=False, electrical_inputs_used=False,
                     measured_energy_j=None, fresh_confirmation=False, physical_goal_pass=False)
    artifacts["model_sha256"] = _sha(artifacts)
    return artifacts


def predict(model, session, times=None, include_features=False, reference_domain=None, allow_extrapolation=True):
    times = list(times) if times is not None else [row["t_s"] for row in _targets(session)]
    result = dict(session_id=session["session_id"], t_s=times, ap_c=[None] * len(times),
                  model_sha256=model.get("model_sha256"), status="UNKNOWN", reason=None)
    if model.get("status") != "EXPERIMENTAL_FIT":
        result["reason"] = "model unavailable or solver did not converge"
        return result
    domain = _domain(session)
    flags = []
    if not session.get("compatibility", {}).get("activity_pool_qualified", False):
        flags.append("SOURCE_CONTRACT_ASSERTION_NOT_INDEPENDENTLY_VERIFIED")
    if not session.get("compatibility", {}).get("ap_sensor_contract_qualified", False):
        flags.append("SENSOR_CONTRACT_ASSERTION_NOT_INDEPENDENTLY_VERIFIED")
    if domain not in model["domains"]:
        if not allow_extrapolation:
            result["reason"] = "UNSUPPORTED_COMPATIBILITY_DOMAIN"
            return result
        if reference_domain is None:
            same_source = [d for d in model["domains"] if session.get("source_family") in model.get("domain_sources", {}).get(d, [])]
            pool = same_source or model["domains"]
            reference_domain = min(pool, key=lambda d: (-model.get("domain_session_counts", {}).get(d, 0), d))
            flags.append("UNSEEN_DOMAIN_PUBLIC_RULE_MOST_TRAINING_SESSIONS_REFERENCE")
        if reference_domain not in model["domains"]:
            raise ValueError("unknown explicit coefficient reference domain")
        flags.append("CONTRACT_EQUIVALENCE_UNVERIFIED_REFERENCE_ASSUMPTION")
    else:
        reference_domain = domain
    try:
        f = features(session, times, model["config"])
        if f["activity_gap_after_initial_anchor"]:
            flags.append("ACTIVITY_GAP_AFTER_INITIAL_AP_ANCHOR_UNIDENTIFIED")
        missing = sorted(set(f["states_present"]) - set(model["domain_activity_support"][reference_domain]))
        offset = model["domains"].index(reference_domain) * len(LOCAL_FEATURES)
        coef = np.asarray(model["coefficients"][offset:offset + len(LOCAL_FEATURES)]).copy()
        for state in missing:
            if not allow_extrapolation:
                raise ValueError("UNIDENTIFIED_ACTIVITY_STATE:" + state)
            if state == STATES[3] and all(s in model["domain_activity_support"][reference_domain] for s in (STATES[1], STATES[2])):
                coef[3 + STATES.index(state)] = coef[3 + STATES.index(STATES[1])] + coef[3 + STATES.index(STATES[2])]
                flags.append("UNMEASURED_OVERLAP_ADDITIVE_SOLO_GAIN_ASSUMPTION")
            else:
                supported = []
                for other in model["domains"]:
                    if state in model["domain_activity_support"][other]:
                        k = model["domains"].index(other) * len(LOCAL_FEATURES) + 3 + STATES.index(state)
                        supported.append(model["coefficients"][k])
                if not supported:
                    raise ValueError("UNKNOWN_ACTIVITY_GAIN_NO_SUPPORTED_REFERENCE:" + state)
                coef[3 + STATES.index(state)] = float(np.median(supported))
                flags.append("UNMEASURED_STATE_OTHER_DOMAIN_GAIN_ASSUMPTION:" + state)
        envelope = model.get("training_envelope", {})
        if envelope and not envelope["initial_AP_c"][0] <= f["initial_ap_c"] <= envelope["initial_AP_c"][1]:
            flags.append("INITIAL_AP_OUTSIDE_TRAINING_RANGE")
        if len(times) and envelope and times[-1] - f["anchor_s"] > envelope["duration_s"][1]:
            flags.append("DURATION_BEYOND_TRAINING_RANGE")
        signature = _activity_signature(session, times[-1]) if len(times) else None
        for state, limits in envelope.get("activity_fractions", {}).items():
            if signature is not None and not limits[0] - 1e-10 <= signature[state] <= limits[1] + 1e-10:
                flags.append("ACTIVITY_FRACTION_OUTSIDE_TRAINING_RANGE:" + state)
        values = f["baseline"] + f["matrix"] @ coef
        if not np.isfinite(values).all():
            raise ValueError("nonfinite AP prediction")
    except ValueError as error:
        result["reason"] = str(error)
        return result
    result.update(status="CONDITIONAL_AP_PREDICTION", ap_c=values.tolist(),
                  initial_ap_c=f["initial_ap_c"], anchor_s=f["anchor_s"],
                  activity_domain=f["domain"], ambient_c=f["ambient_c"],
                  coefficient_reference_domain=reference_domain,
                  extrapolation_flags=flags, contract_equivalence_verified=not any("CONTRACT_" in flag for flag in flags),
                  counterfactual_schedule=bool(session.get("counterfactual", False)), activity_fractions=signature,
                  real_activity_state_at_anchor=f["real_activity_state_at_anchor"])
    if include_features:
        result.update(feature_matrix=f["matrix"].tolist(), baseline=f["baseline"].tolist(),
                      local_coefficients=coef.tolist(), local_feature_names=list(LOCAL_FEATURES),
                      initial_input_latest_hi_s=f["input_latest_hi_s"])
    return result


def grouped_folds(sessions, maximum_folds=4):
    """Union cohorts and identical native/session identities before any folding.

    A shared input/archive file SHA is not a session identity: many independent
    sessions inhabit one file. Only explicit native member/session IDs or exact
    projection content hashes join different cohorts.
    """
    ids = [s["session_id"] for s in sessions]
    if len(ids) != len(set(ids)):
        raise ValueError("deduplicate session roster before CV")
    parent = {sid: sid for sid in ids}
    def find(sid):
        while parent[sid] != sid:
            parent[sid] = parent[parent[sid]]
            sid = parent[sid]
        return sid
    def union(a, b):
        a, b = find(a), find(b)
        parent[max(a, b)] = min(a, b)
    seen = {}
    for session in sessions:
        p = session.get("provenance", {})
        keys = [("cohort", session["cohort_id"])]
        for name in ("native_session_id", "projection_content_sha256", "raw_session_sha256"):
            if p.get(name):
                keys.append((name, p[name]))
        for key in keys:
            if key in seen:
                union(session["session_id"], seen[key])
            else:
                seen[key] = session["session_id"]
    groups = {}
    for session in sessions:
        groups.setdefault(find(session["session_id"]), []).append(session["session_id"])
    keys = sorted(groups)
    if len(keys) < 2:
        return dict(status="UNAVAILABLE_FEWER_THAN_TWO_WHOLE_COHORTS", folds=[], groups=groups)
    count = min(int(maximum_folds), len(keys))
    folds = []
    for index in range(count):
        held = sorted(sid for k in keys[index::count] for sid in groups[k])
        folds.append(dict(fold_id=index, heldout_session_ids=held,
                          training_session_ids=sorted(set(ids) - set(held))))
    return dict(status="WHOLE_COHORT_POSTHOC_DEVELOPMENT", folds=folds, groups=groups,
                fold_sha256=_sha(folds), fresh_confirmation=False)


def score_session(session, prediction):
    rows = _targets(session)
    basic = dict(session_id=session["session_id"], cohort_id=session["cohort_id"],
                 source_family=session["source_family"], source_generation=session.get("source_generation"),
                 protocol=session.get("protocol"), arm=session.get("arm"),
                 activity_domain=_domain(session),
                 predicted=prediction["status"] == "CONDITIONAL_AP_PREDICTION" and _eligible(session),
                 reason=prediction.get("reason") if _eligible(session) else "AP_TARGET_INELIGIBLE_DIAGNOSTIC_ONLY",
                 samples=len(rows), initial_AP_band="UNKNOWN" if not _finite(session.get("initial_ap_c")) else
                 ("below30C" if session["initial_ap_c"] < 30 else "30to35C" if session["initial_ap_c"] < 35 else "atleast35C"),
                 extrapolation_flags=prediction.get("extrapolation_flags", []),
                 contract_equivalence_verified=prediction.get("contract_equivalence_verified", False),
                 window_s=[rows[0]["t_s"], rows[-1]["t_s"]] if rows else None)
    if not basic["predicted"] or not rows:
        return dict(basic, mae_c=None, peak_error_c=None, endpoint_residual_error_c=None, strata={})
    t = np.asarray([r["t_s"] for r in rows]); actual = np.asarray([r["ap_c"] for r in rows])
    if t.tolist() != prediction["t_s"]:
        raise ValueError("score must use exact same saved query timestamps")
    pred = np.asarray(prediction["ap_c"]); error = pred - actual
    segments = activity_segments(session)
    busy = np.asarray([any(r["state"] != "idle" and r["start_s"] <= at < r["end_s"] for r in segments) for at in t])
    available = max((r["end_s"] for r in segments if r["state"] != "idle"), default=-math.inf)
    rising = np.r_[False, np.diff(actual) > .05]
    strata = {}
    for name, mask in (("all", np.ones(len(t), dtype=bool)), ("busy", busy),
                       ("idle", ~busy), ("cooling_after_available", t > available), ("rising", rising)):
        strata[name] = dict(samples=int(mask.sum()), mae_c=float(np.mean(abs(error[mask]))) if mask.any() else None,
                            signed_bias_c=float(np.mean(error[mask])) if mask.any() else None)
    return dict(basic, mae_c=float(np.mean(abs(error))), rmse_c=float(np.sqrt(np.mean(error ** 2))),
                max_abs_error_c=float(np.max(abs(error))), signed_bias_c=float(np.mean(error)),
                peak_error_c=float(pred.max() - actual.max()),
                endpoint_residual_error_c=float(error[-1]),
                actual_AP_change_c=float(actual[-1] - actual[0]), predicted_AP_change_c=float(pred[-1] - pred[0]),
                direction_reversal=bool((actual[-1] - actual[0]) * (pred[-1] - pred[0]) < 0),
                initial_ap_c=session.get("initial_ap_c"), strata=strata)


def summarize(rows):
    valid = [r for r in rows if r.get("mae_c") is not None]
    cohorts = sorted({r["cohort_id"] for r in valid})
    means = [float(np.mean([r["mae_c"] for r in valid if r["cohort_id"] == cohort])) for cohort in cohorts]
    ci = None
    if len(means) >= 2:
        rng = np.random.default_rng(1601024)
        boot = np.mean(rng.choice(np.asarray(means), (2000, len(means)), replace=True), axis=1)
        ci = np.quantile(boot, [.025, .975]).tolist()
    by = {}
    for field in ("source_family", "source_generation", "cohort_id", "protocol", "arm", "initial_AP_band", "activity_domain"):
        by[field] = {str(value): dict(sessions=sum(r.get(field) == value for r in rows),
                                       predicted_sessions=sum(r.get(field) == value for r in valid),
                                       mean_session_mae_c=float(np.mean([r["mae_c"] for r in valid if r.get(field) == value]))
                                       if any(r.get(field) == value for r in valid) else None)
                     for value in sorted({r.get(field) for r in rows}, key=str)}
    return dict(sessions=len(rows), predicted_sessions=len(valid), unknown_sessions=len(rows) - len(valid),
                whole_cohorts=len(cohorts), cohort_balanced_mae_c=float(np.mean(means)) if means else None,
                contract_assumption_sessions=sum(not r.get("contract_equivalence_verified", False) for r in valid),
                extrapolation_sessions=sum(bool(r.get("extrapolation_flags")) for r in valid),
                session_balanced_mae_c=float(np.mean([r["mae_c"] for r in valid])) if valid else None,
                worst_session_mae_c=max((r["mae_c"] for r in valid), default=None),
                peak_mae_c=float(np.mean([abs(r["peak_error_c"]) for r in valid])) if valid else None,
                endpoint_residual_mae_c=float(np.mean([abs(r["endpoint_residual_error_c"]) for r in valid])) if valid else None,
                direction_reversals=sum(r["direction_reversal"] for r in valid),
                cohort_resample_mae_ci95=ci, CI_unit="whole_cohort_not_rows",
                strata={name: dict(predicted_sessions=sum(r["strata"][name]["mae_c"] is not None for r in valid),
                                   mean_session_mae_c=float(np.mean([r["strata"][name]["mae_c"] for r in valid if r["strata"][name]["mae_c"] is not None]))
                                   if any(r["strata"][name]["mae_c"] is not None for r in valid) else None)
                        for name in ("all", "busy", "idle", "cooling_after_available", "rising")},
                by=by, fresh_confirmation=False, accuracy_pass=None)


def _mode_training(sessions, mode):
    allowed = {"old"} if mode == "old-only" else {"m8"} if mode == "m8-only" else {"old", "m8"}
    return [s for s in sessions if s["source_family"] in allowed]


def cross_validate(sessions, candidates=None, folds=None, on_fit=None):
    """Same whole-cohort heldouts for every candidate and every training source.

    All curves are saved in the returned dict. No final-fit or policy selection
    occurs here. Coverage-changing candidates cannot win by hiding hard sessions.
    """
    candidates = candidate_grid() if candidates is None else candidates
    folds = grouped_folds(sessions) if folds is None else copy.deepcopy(folds)
    if not folds.get("folds"):
        return dict(version=VERSION, status="UNAVAILABLE_GROUPED_CV", folds=folds,
                    candidates=[], selection={}, final_models={}, final_predictions=[], fresh_confirmation=False)
    byid = {s["session_id"]: s for s in sessions}
    roster = set(byid)
    for fold in folds["folds"]:
        held, train = set(fold["heldout_session_ids"]), set(fold["training_session_ids"])
        if held & train or held | train != roster:
            raise ValueError("heldout/training membership leakage or roster mismatch")
        # Independently regenerate grouping constraints even for caller-provided folds.
        for group in grouped_folds(sessions)["groups"].values():
            if set(group) & held and set(group) & train:
                raise ValueError("cohort or exact raw session split across train/heldout")
    result = []
    for index, config in enumerate(candidates):
        modes = {}
        for mode in MODES:
            rows, predictions, fit_artifacts = [], [], []
            for fold in folds["folds"]:
                train = _mode_training([byid[sid] for sid in fold["training_session_ids"]], mode)
                model = fit(train, config, on_fit=on_fit)
                fit_artifacts.append(dict(fold_id=fold["fold_id"], model=model))
                for sid in fold["heldout_session_ids"]:
                    prediction = predict(model, byid[sid], include_features=True)
                    predictions.append(dict(fold_id=fold["fold_id"], **prediction))
                    rows.append(dict(fold_id=fold["fold_id"], **score_session(byid[sid], prediction)))
            modes[mode] = dict(rows=rows, predictions=predictions, summary=summarize(rows), fold_models=fit_artifacts)
        result.append(dict(candidate_index=index, config=_config(config), modes=modes))
    selection = {}
    for mode in MODES:
        counts = [r["modes"][mode]["summary"]["predicted_sessions"] for r in result]
        max_coverage = max(counts, default=0)
        choices = [r for r in result if r["modes"][mode]["summary"]["predicted_sessions"] == max_coverage and
                   r["modes"][mode]["summary"]["cohort_balanced_mae_c"] is not None]
        if not choices:
            selection[mode] = dict(status="UNAVAILABLE_NO_COMMON_SUPPORTED_HELDOUTS")
            continue
        winner = min(choices, key=lambda r: (r["modes"][mode]["summary"]["cohort_balanced_mae_c"],
                                            r["modes"][mode]["summary"]["worst_session_mae_c"],
                                            r["candidate_index"]))
        selection[mode] = dict(status="POSTHOC_DEVELOPMENT_SELECTED", candidate_index=winner["candidate_index"],
                               config=winner["config"], summary=winner["modes"][mode]["summary"],
                               coverage_first=True, policy_gap_used=False)
    return dict(version=VERSION, status="POSTHOC_GROUPED_CV_NOT_FRESH_CONFIRMATION", folds=folds,
                candidates=result, selection=selection, final_models={}, final_predictions=[],
                source_mode_cross_domain_unknowns_preserved=True, fresh_confirmation=False,
                measured_energy_j=None, physical_goal_pass=False)


def fit_selected(sessions, cv_result, on_fit=None):
    """Separate explicit final-fit operation after the selection has been frozen."""
    models, predictions = {}, []
    for mode, choice in cv_result["selection"].items():
        if choice.get("status") != "POSTHOC_DEVELOPMENT_SELECTED":
            models[mode] = dict(status="UNAVAILABLE", reason=choice.get("status"))
            continue
        model = fit(_mode_training(sessions, mode), choice["config"], on_fit=on_fit)
        models[mode] = model
        for session in sessions:
            predictions.append(dict(training_mode=mode, evaluation_role="IN_SAMPLE_DESCRIPTIVE_NOT_CV",
                                    **predict(model, session, include_features=True)))
    return dict(version=VERSION, final_models=models, final_predictions=predictions,
                CV_selection_sha256=_sha(cv_result["selection"]),
                status="FINAL_DEVELOPMENT_MODELS_NOT_INDEPENDENT_VALIDATION",
                measured_energy_j=None, accuracy_pass=None, fresh_confirmation=False,
                physical_goal_pass=False)
