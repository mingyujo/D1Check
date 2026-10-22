"""S26 all-known, raw-activity AP/API-power model. No import-time computation.

The CLI performs retrospective grouped OOF model selection, then fits each
family on all its eligible known development sessions. It is not an external
test and it does not run policies, a physical simulator, NN, or CostState.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import time

import numpy as np
from scipy.optimize import lsq_linear

SCHEMA = "S26_INTEGRATED_ACTIVITY_MODEL_v1"
DATA_SCHEMA = "S26_INTEGRATED_MEASUREMENTS_v1"
RESULT_SCHEMA = "S26_INTEGRATED_MODEL_RESULTS_v1"
ACTIVITY = ("classification_CPU", "detection_CPU", "classification_GPU", "classification_NPU",
            "shared_admission", "shared_persist_release", "owner_union",
            "unallocated_owner_phase", "owner_overlap")
HISTORY = ("anchor_AP_c", "anchor_SKIN_c", "anchor_BAT_c", "pre20_AP_slope_c_s")
FAMILIES = ("old_only", "M8_only", "pooled", "shared_domain")
TARGETS = ("AP", "POWER_API")
BETAS = (.02, .06, .15)
WINDOWS = (0., .5, 2.)
RIDGES = (.1, 1.)
SCOPE = "ALL_SEEN_DEVELOPMENT_NO_EXTERNAL_TEST"


def require(ok, message):
    if not ok:
        raise ValueError(message)


def number(value):
    return type(value) in (float, int) and math.isfinite(value)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def save_new(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    require(not path.exists(), "immutable output exists: " + str(path))
    temporary = path.with_name(path.name + ".part")
    with temporary.open("xb") as handle:
        handle.write((canonical(value) + "\n").encode("utf-8"))
        handle.flush()
        os.fsync(handle.fileno())
    require(not path.exists(), "immutable output appeared")
    temporary.rename(path)


def append(path, value):
    with Path(path).open("ab") as handle:
        handle.write((canonical(value) + "\n").encode("utf-8"))
        handle.flush()
        os.fsync(handle.fileno())


def uid(session):
    value = session.get("session_uid", session.get("id"))
    require(isinstance(value, str) and value, "session UID absent")
    return value


def pool(session):
    value = session.get("source_pool")
    require(value in ("OLD", "M8"), "source_pool must explicitly be OLD or M8")
    return value


def cohort(session):
    value = session.get("cohort")
    require(isinstance(value, str) and value, "cohort absent")
    return value


def group(session):
    value = session.get("cv_group", cohort(session))
    require(isinstance(value, str) and value, "CV group absent")
    return value


def get_number(mapping, names, label):
    for name in names:
        if number(mapping.get(name)):
            return float(mapping[name])
    raise ValueError("missing observed " + label)


def prepare_session(session, target, times_s=None):
    """Prepare actual target rows, or prefix-only prediction with explicit times.

    No hard 180/210/780 limit. Actual input observation windows and unknown
    feature flags govern inclusion. The default is every actual t>=0 row.
    """
    require(target in TARGETS, "target ABI")
    require(isinstance(session.get("domain"), str) and session["domain"], "domain absent")
    activity = session.get("activity9", {})
    require(tuple(activity.get("names", ())) == ACTIVITY, "activity9 names/order")
    known = activity.get("known_features")
    require(isinstance(known, list) and len(known) == 9 and all(type(x) is bool for x in known), "activity known flags")
    segments = activity.get("intervals")
    require(isinstance(segments, list) and len(segments) == 9, "activity9 interval ABI")
    segments = [[[float(x) for x in item] for item in field] for field in segments]
    for field, intervals in enumerate(segments):
        for item in intervals:
            require(len(item) == 3 and all(number(x) for x in item) and item[1] >= item[0] and item[2] >= 0,
                    "invalid actual activity interval")
    start = float(session.get("history_start_s", -30.))
    require(number(start) and start <= -20., "observed history boundary missing")
    contract = session.get("targets", {}).get(target, {})
    if times_s is None:
        require(contract.get("eligible") is True, "target ineligible: " + canonical(contract.get("reasons", [])))
        window = contract.get("fit_window_s", session.get("fit_window_s"))
        require(window is None or (len(window) == 2 and all(number(x) for x in window) and window[1] >= window[0]), "target fit window")
        rows = contract.get("observations", [])
        key = "value_c" if target == "AP" else "value_api_w"
        rows = [row for row in rows if number(row.get("t_s")) and number(row.get(key)) and row["t_s"] >= 0
                and (window is None or window[0] <= row["t_s"] <= window[1])]
        require(len(rows) >= 3, "less than three actual nonnegative target samples")
        original_target_rows = len(rows)
        known_until = activity.get("known_until_s")
        if isinstance(known_until, list):
            require(len(known_until) == 9, "known_until vector ABI")
            finite_core = [float(x) for x in known_until[:7] if number(x)]
            core_limit = min(finite_core) if finite_core else None
        else:
            core_limit = float(known_until) if number(known_until) else None
        if core_limit is not None and all(known[:7]):
            rows = [row for row in rows if row["t_s"] <= core_limit]
        require(len(rows) >= 3, "target samples beyond known core activity window; no inferred AVAILABLE")
        times = np.asarray([row["t_s"] for row in rows], dtype=float)
        observed = np.asarray([row[key] for row in rows], dtype=float)
        require(np.all(np.diff(times) > 0), "target timestamps must be strictly increasing")
        require(times[-1] > times[0], "target span missing")
    else:
        times = np.asarray(times_s, dtype=float)
        require(times.ndim == 1 and len(times) > 0 and np.isfinite(times).all() and np.all(times >= 0), "prediction query grid")
        require(np.all(np.diff(times) >= 0), "prediction times nondecreasing")
        observed = None
        rows = []
        original_target_rows = 0
        core_limit = None
    result = dict(id=uid(session), cohort=cohort(session), cv_group=group(session), domain=session["domain"],
        source_pool=pool(session), segments=segments, known=known, history_start_s=start,
        times=times, observed=observed, clock_contract=session.get("clock_contract"),
        actual_window_s=[float(times[0]), float(times[-1])], source_rows=rows,
        raw_refs=session.get("raw_refs", []), required_activity_known_until_s=core_limit,
        activity_known_until_s=activity.get("known_until_s"),
        activity_known_until_by_feature_s=activity.get("known_until_by_feature_s"),
        source_contract_metadata={key:session.get(key) for key in ("timing_contract", "selected_source", "source_copies", "provenance", "metadata", "compatibility", "prior_role")},
        excluded_after_known_until_rows=original_target_rows-len(rows), _cache={})
    if target == "AP":
        anchor = contract.get("anchor")
        require(isinstance(anchor, dict), "observed joint HAL anchor absent")
        a = get_number(anchor, ("time_s", "t_s"), "anchor time")
        upper = get_number(anchor, ("available_upper_s", "completion_upper_s"), "HAL completion upper")
        require(start <= a <= upper <= 0, "anchor must be completed precommon with retained nominal time")
        ap = get_number(anchor, ("AP_c", "AP", "value_c"), "HAL AP anchor")
        skin = get_number(anchor, ("SKIN_c", "SKIN"), "HAL SKIN anchor")
        bat = get_number(anchor, ("BAT_c", "BAT"), "HAL BAT anchor; sampler battery cannot substitute")
        slope = get_number(anchor, ("pre20_AP_slope_c_s", "pre20_AP_slope"), "actual pre-anchor AP slope")
        result.update(anchor=anchor, anchor_s=a, anchor_AP_c=ap, history=np.asarray([ap, skin, bat, slope]))
    else:
        baseline = contract.get("baseline")
        require(isinstance(baseline, dict), "actual precommon idle baseline absent")
        value = get_number(baseline, ("median_api_w", "api_scale_idle_median_w"), "API power baseline")
        require(value > 0, "nonpositive precommon baseline; no replacement constant")
        result.update(baseline=baseline, baseline_api_w=value)
    return result


def activity_at(segments, times, history_start):
    result = np.zeros((len(times), 9))
    for field, intervals in enumerate(segments):
        for left, right, weight in intervals:
            left = max(history_start, left)
            result[:, field] += weight * ((times >= left) & (times < right))
    return result


def filtered_activity(segments, times, beta, history_start):
    """Direct dimensionless unit-gain exponential duty, not Watt-weighted."""
    t = np.asarray(times, dtype=float)
    result = np.zeros((len(t), 9))
    for field, intervals in enumerate(segments):
        for left, right, weight in intervals:
            left = max(history_start, left)
            right = max(left, right)
            mask = t > left
            effective = np.minimum(t[mask], right)
            result[mask, field] += weight * (np.exp(-beta * (t[mask] - effective)) - np.exp(-beta * (t[mask] - left)))
    return result


def windowed_activity(segments, times, width, history_start):
    t = np.asarray(times, dtype=float)
    if width == 0:
        return activity_at(segments, t, history_start)
    result = np.zeros((len(t), 9))
    for field, intervals in enumerate(segments):
        for left, right, weight in intervals:
            left = max(history_start, left)
            result[:, field] += weight * np.maximum(0., np.minimum(t, right) - np.maximum(t - width, left)) / width
    return result


def activity_matrix(prepared, target, parameter, use_cache=True):
    # Cache belongs to immutable prepared rows. The grid/anchor/hash are in the
    # key, so even a caller's shallow copy with a different grid cannot reuse it.
    t = prepared["times"]
    key = (target, float(parameter), t.dtype.str, t.shape, t.tobytes(), prepared.get("anchor_s"), prepared["history_start_s"])
    cache = prepared["_cache"] if use_cache else {}
    if key in cache:
        return cache[key]
    if target == "AP":
        value = filtered_activity(prepared["segments"], t, parameter, prepared["history_start_s"])
        value -= filtered_activity(prepared["segments"], [prepared["anchor_s"]], parameter, prepared["history_start_s"])[0]
    else:
        value = windowed_activity(prepared["segments"], t, parameter, prepared["history_start_s"])
    value.flags.writeable = False
    if use_cache:
        cache[key] = value
    return value


def candidates(target):
    result = [dict(target=target, feature_set="null", beta=None, window_s=0., ridge=r) for r in RIDGES]
    for kind in ("additive7", "additive9"):
        for parameter in BETAS if target == "AP" else WINDOWS:
            for ridge in RIDGES:
                result.append(dict(target=target, feature_set=kind, beta=parameter if target == "AP" else None,
                    window_s=parameter if target == "POWER_API" else None, ridge=ridge))
    return result


def session_weights(prepared):
    counts = {}
    for ep in prepared:
        counts[ep["cohort"]] = counts.get(ep["cohort"], 0) + 1
    return np.asarray([1. / (len(counts) * counts[ep["cohort"]]) for ep in prepared])


def history_norm(prepared):
    weight = session_weights(prepared)
    values = np.stack([ep["history"] for ep in prepared])
    mean = np.sum(weight[:, None] * values, axis=0)
    variance = np.sum(weight[:, None] * (values - mean) ** 2, axis=0)
    return dict(mean=mean.tolist(), scale=np.maximum(np.sqrt(variance), 1e-8).tolist(),
                fit_session_ids=[ep["id"] for ep in prepared], weighting="equal cohort, equal session within cohort")


def activity_available(prepared, size):
    if not all(prepared["known"][:size]):
        return False
    if size == 0:
        return True
    bounds = prepared.get("activity_known_until_by_feature_s")
    if isinstance(bounds, list) and len(bounds) == 9:
        return all(number(value) for value in bounds[:size]) and float(prepared["times"][-1]) <= min(bounds[:size]) + 1e-12
    end = prepared.get("activity_known_until_s")
    return size <= 7 and number(end) and float(prepared["times"][-1]) <= end + 1e-12


def raw_design(prepared, spec, normalization, domains, domain_enabled):
    t = prepared["times"]
    size = 0 if spec["feature_set"] == "null" else 7 if spec["feature_set"] == "additive7" else 9
    require(activity_available(prepared, size), "required activity/horizon unknown; no zero fill or unknown future query")
    if spec["target"] == "AP":
        activity = activity_matrix(prepared, "AP", spec["beta"])[:, :size] if size else np.empty((len(t), 0))
        z = (prepared["history"] - np.asarray(normalization["mean"])) / np.asarray(normalization["scale"])
        cov = np.r_[1., z]
        elapsed = t - prepared["anchor_s"]
        kernels = [-np.expm1(-elapsed / tau) for tau in (20., 120.)]
        drift = np.column_stack([kernel[:, None] * cov for kernel in kernels])
        labels = list(ACTIVITY[:size]) + [name + "_drift_" + str(int(tau)) + "s" for tau in (20., 120.) for name in ("intercept",) + HISTORY]
        matrix = np.column_stack((activity, drift))
        lower = np.r_[np.zeros(size), np.full(10, -np.inf)]
        if domain_enabled:
            nuisance = np.column_stack([kernel * float(prepared["domain"] == domain) for domain in domains for kernel in kernels])
            matrix = np.column_stack((matrix, nuisance))
            labels += ["contract_domain:" + domain + "_drift_" + str(int(tau)) + "s" for domain in domains for tau in (20., 120.)]
            lower = np.r_[lower, np.full(2 * len(domains), -np.inf)]
    else:
        activity = activity_matrix(prepared, "POWER_API", spec["window_s"])[:, :size] if size else np.empty((len(t), 0))
        matrix = np.column_stack((np.ones(len(t)), np.full(len(t), prepared["baseline_api_w"]), activity))
        labels = ["shared_background_intercept", "past_idle_API_power"] + list(ACTIVITY[:size])
        lower = np.zeros(size + 2)
        if domain_enabled:
            nuisance = np.column_stack([np.full(len(t), float(prepared["domain"] == domain)) for domain in domains])
            matrix = np.column_stack((matrix, nuisance))
            labels += ["contract_domain:" + domain + "_background" for domain in domains]
            lower = np.r_[lower, np.zeros(len(domains))]
    require(np.isfinite(matrix).all(), "nonfinite model design")
    return matrix, labels, lower


def fit_model(prepared, spec, family, fit_id=None, output=None, counters=None, max_fits=None):
    """New bounded ridge, not old frozen parameter reuse. All train IDs saved."""
    require(prepared and family in FAMILIES, "empty/unknown fitting family")
    if counters is not None:
        require(counters["fit_attempts"] < max_fits, "registered fit cap")
        counters["fit_attempts"] += 1
        append(Path(output) / "FIT_RECEIPTS.jsonl", dict(event="START", fit_id=fit_id, family=family,
            spec=spec, training_session_ids=[ep["id"] for ep in prepared], created_unix=time.time()))
    try:
        normalization = history_norm(prepared) if spec["target"] == "AP" else None
        domains = sorted({ep["domain"] for ep in prepared})
        domain_enabled = family == "shared_domain"
        matrices, responses, weights = [], [], []
        sw = session_weights(prepared)
        for i, ep in enumerate(prepared):
            matrix, labels, lower = raw_design(ep, spec, normalization, domains, domain_enabled)
            response = ep["observed"] - ep["anchor_AP_c"] if spec["target"] == "AP" else ep["observed"]
            matrices.append(matrix)
            responses.append(response)
            weights.append(np.full(len(response), sw[i] / len(response)))
        x, y, w = np.vstack(matrices), np.concatenate(responses), np.concatenate(weights)
        rms = np.maximum(np.sqrt(np.sum(w[:, None] * x * x, axis=0)), 1e-8)
        weighted = (x / rms) * np.sqrt(w[:, None])
        penalty = spec["ridge"] / len(labels)
        augmented = np.vstack((weighted, math.sqrt(penalty) * np.eye(len(labels))))
        target = np.r_[y * np.sqrt(w), np.zeros(len(labels))]
        solution = lsq_linear(augmented, target, bounds=(lower, np.full(len(labels), np.inf)),
                              method="bvls", tol=1e-10, max_iter=10000)
        require(solution.success and np.isfinite(solution.x).all(), "bounded ridge did not converge")
        singular = np.linalg.svd(weighted, compute_uv=False)
        gram = weighted.T @ weighted
        condition = float(singular[0] / singular[-1]) if singular[-1] > 1e-12 else None
        model = dict(schema=SCHEMA, family=family, target=spec["target"], spec=dict(spec),
            scope=SCOPE, unit="degC_HAL_AP" if spec["target"] == "AP" else "API_scale_W_unverified",
            feature_labels=labels, feature_rms=rms.tolist(), standardized_coefficients=solution.x.tolist(),
            raw_basis_coefficients=(solution.x / rms).tolist(), history_normalization=normalization,
            domains=domains, domain_enabled=domain_enabled,
            unseen_domain_rule="shared terms only; unseen contract nuisance unavailable, not an observed zero",
            training_session_ids=[ep["id"] for ep in prepared], normalization_fit_ids=[ep["id"] for ep in prepared],
            training_cohorts=sorted({ep["cohort"] for ep in prepared}), training_cv_groups=sorted({ep["cv_group"] for ep in prepared}),
            training_source_pools=sorted({ep["source_pool"] for ep in prepared}),
            source_pool_session_counts={key:sum(ep["source_pool"] == key for ep in prepared) for key in ("OLD", "M8")},
            training_contracts={ep["id"]:dict(source_pool=ep["source_pool"],domain=ep["domain"],cohort=ep["cohort"],
                clock_contract=ep["clock_contract"],source_contract_metadata=ep["source_contract_metadata"]) for ep in prepared},
            independent_session_units=len(prepared), observed_points=len(y),
            weighting="equal cohort totals, equal sessions within cohort, equal actual samples within session",
            actual_training_windows_s={ep["id"]: ep["actual_window_s"] for ep in prepared},
            session_loss_weights={ep["id"]: float(sw[i]) for i, ep in enumerate(prepared)},
            design=dict(rank=int(np.linalg.matrix_rank(weighted)), columns=len(labels), singular_values=singular.tolist(),
                condition_number=condition, condition_infinite=condition is None,
                ridge_effective_parameters_unconstrained_reference=float(np.trace(np.linalg.solve(gram + penalty * np.eye(len(labels)), gram))),
                effective_parameter_boundary="linear-ridge reference only; constrained degrees of freedom not claimed",
                zero_columns=[labels[i] for i in range(len(labels)) if np.all(x[:, i] == 0)],
                zero_coefficients=[labels[i] for i, value in enumerate(solution.x) if abs(value) <= 1e-12],
                active_lower_bounds=[labels[i] for i, value in enumerate(solution.active_mask) if value == -1]),
            exposure={name:dict(nonzero_sessions=sum(any(max(0., min(ep["times"][-1], r) - max(0., l)) * v > 0 for l, r, v in ep["segments"][j]) for ep in prepared),
                per_session_s={ep["id"]: float(sum(max(0., min(ep["times"][-1], r) - max(0., l)) * v for l, r, v in ep["segments"][j])) for ep in prepared})
                for j, name in enumerate(ACTIVITY)},
            fit=dict(solver="scipy.optimize.lsq_linear BVLS", iterations=solution.nit, success=bool(solution.success),
                optimality=float(solution.optimality), ridge="lambda/p on all train-RMS standardized coefficients"),
            no_policy_id_coefficients=True, AP_independent_of_Watts=True, external_meter_calibrated=False,
            hardware_core_coefficients_identified=False, policy_causal_effect_identified=False)
        if counters is not None:
            model_path = Path(output) / "FIT_MODELS" / (fit_id + ".json")
            save_new(model_path, model)
            counters["fits_completed"] += 1
            append(Path(output) / "FIT_RECEIPTS.jsonl", dict(event="COMPLETE", fit_id=fit_id,
                model_path=str(model_path.resolve()), model_sha256=sha(model_path), model_parameter_sha256=digest(model), created_unix=time.time()))
        return model
    except Exception as error:
        if counters is not None:
            append(Path(output) / "FIT_RECEIPTS.jsonl", dict(event="FAIL", fit_id=fit_id,
                error=type(error).__name__ + ": " + str(error), created_unix=time.time()))
        raise


def predict_prepared(model, prepared):
    matrix, labels, _ = raw_design(prepared, model["spec"], model["history_normalization"], model["domains"], model["domain_enabled"])
    require(labels == model["feature_labels"], "fixed model feature ABI")
    value = matrix @ np.asarray(model["raw_basis_coefficients"])
    if model["target"] == "AP":
        value += prepared["anchor_AP_c"]
    require(np.isfinite(value).all(), "nonfinite prediction")
    return value


def predict_session(model, session, times_s=None):
    ep = prepare_session(session, model["target"], times_s)
    return dict(target=model["target"], unit=model["unit"], times_s=ep["times"].tolist(),
        prediction=predict_prepared(model, ep).tolist(), parameter_sha256=digest(model),
        anchor=ep.get("anchor"), baseline=ep.get("baseline"),
        source_pool=ep["source_pool"], clock_contract=ep["clock_contract"],
        source_contract_metadata=ep["source_contract_metadata"],
        domain_seen_in_training=ep["domain"] in model["domains"], scope=SCOPE,
        new_fit=0, new_environment=0, new_NN=0, new_CostState=0)


def predict_trace(model, initial_context, activity9, times_s):
    """Fixed parameters + completed precommon inputs + saved/known activity.

    initial_context: {domain,source_pool,anchor(AP) or baseline(POWER_API),
    history_start_s,clock_contract}. activity9 includes explicit known horizon.
    No future sensors, outcomes or policy/model selection are read here.
    """
    require(initial_context.get("source_pool") in ("OLD", "M8"), "prediction source pool contract required")
    session = dict(id="FIXED_TRACE_QUERY", cohort="FIXED_TRACE_QUERY", source_pool=initial_context["source_pool"],
        domain=initial_context["domain"], history_start_s=initial_context.get("history_start_s", -30.),
        clock_contract=initial_context.get("clock_contract"),
        activity9=activity9, targets={model["target"]:dict(anchor=initial_context.get("anchor"), baseline=initial_context.get("baseline"))})
    return predict_session(model, session, times_s)


def predict_bundle(bundle, initial_context, activity9, times_s):
    """Both integrated targets from one immutable bundle; no fit or disk I/O."""
    require(bundle.get("schema") == "S26_INTEGRATED_PREDICTION_BUNDLE_v1", "bundle schema")
    result = {}
    for target, binding in bundle["targets"].items():
        require(digest(binding["model"]) == binding["parameter_sha256"], "bundle parameter SHA")
        context = dict(initial_context)
        if isinstance(initial_context.get("targets"), dict):
            context.update(initial_context["targets"].get(target, {}))
        result[target] = predict_trace(binding["model"], context, activity9, times_s)
    return result


def metric_values(observed, predicted):
    if len(observed) == 0:
        return None
    error = predicted - observed
    return dict(observations=len(error), MAE=float(np.mean(np.abs(error))), RMSE=float(np.sqrt(np.mean(error ** 2))),
                bias=float(np.mean(error)), max_absolute_error=float(np.max(np.abs(error))),
                negative_predictions=int(np.sum(predicted < 0)))


def score(model, ep, curve=False):
    predicted = predict_prepared(model, ep)
    result = dict(session_uid=ep["id"], cohort=ep["cohort"], cv_group=ep["cv_group"], domain=ep["domain"],
        source_pool=ep["source_pool"], **metric_values(ep["observed"], predicted),
        actual_window_s=ep["actual_window_s"], anchor=ep.get("anchor"), baseline=ep.get("baseline"),
        required_activity_known_until_s=ep.get("required_activity_known_until_s"),
        excluded_after_known_until_rows=ep.get("excluded_after_known_until_rows", 0),
        parameter_sha256=digest(model), domain_seen_in_training=ep["domain"] in model["domains"])
    mask = (ep["times"] >= 35) & (ep["times"] <= 180)
    result["common35_180_metrics"] = metric_values(ep["observed"][mask], predicted[mask]) if mask.sum() >= 3 else None
    if curve:
        result.update(times_s=ep["times"].tolist(), observed=ep["observed"].tolist(), predicted=predicted.tolist())
    return result


def aggregate(rows):
    if not rows:
        return None
    by = {}
    for row in rows:
        by.setdefault(row["cohort"], []).append(row)
    cohort_metrics = {key:{metric:float(np.mean([row[metric] for row in values])) for metric in ("MAE", "RMSE", "bias")}
                      for key, values in by.items()}
    return dict(sessions=len(rows), cohorts=len(by), observations=sum(row["observations"] for row in rows),
        mean_cohort_MAE=float(np.mean([value["MAE"] for value in cohort_metrics.values()])),
        mean_cohort_RMSE=float(np.mean([value["RMSE"] for value in cohort_metrics.values()])),
        mean_cohort_bias=float(np.mean([value["bias"] for value in cohort_metrics.values()])),
        mean_session_MAE=float(np.mean([row["MAE"] for row in rows])),
        worst_session_MAE=max(row["MAE"] for row in rows), by_cohort=cohort_metrics)


def family_training(prepared, family, excluded_group=None):
    return [ep for ep in prepared if ep["cv_group"] != excluded_group and
            (family not in ("old_only", "M8_only") or ep["source_pool"] == ("OLD" if family == "old_only" else "M8"))]


def evaluate_target(prepared, target, output, counters, max_fits):
    groups = sorted({ep["cv_group"] for ep in prepared})
    require(len(groups) >= 2, "need at least two physical collection CV groups")
    models, candidate_reports, folds = [], [], []
    for family in FAMILIES:
        reports = []
        for ci, spec in enumerate(candidates(target)):
            required = 9 if spec["feature_set"] == "additive9" else 7  # common core7 scoring population for fair null/activity selection
            unavailable = [ep["id"] for ep in prepared if not activity_available(ep, required)]
            if unavailable:
                reports.append(dict(candidate_index=ci, spec=spec, status="UNAVAILABLE_UNKNOWN_REQUIRED_ACTIVITY", excluded_session_ids=unavailable))
                continue
            scores, local_folds = [], []
            unavailable_folds = []
            for fi, held_group in enumerate(groups):
                held = [ep for ep in prepared if ep["cv_group"] == held_group]
                train = family_training(prepared, family, held_group)
                if not train:
                    unavailable_folds.append(held_group)
                    continue
                fit_id = target + "_" + family + "_C" + str(ci).zfill(2) + "_F" + str(fi).zfill(3)
                fitted = fit_model(train, spec, family, fit_id, output, counters, max_fits)
                rows = [score(fitted, ep) for ep in held]
                for row in rows:
                    row.update(fold_id=fit_id, role="GROUP_OOF_SELECTION")
                scores.extend(rows)
                local_folds.append(dict(fold_id=fit_id, family=family, target=target, candidate_index=ci,
                    test_cohort=held_group, train_session_ids=[ep["id"] for ep in train], test_session_ids=[ep["id"] for ep in held],
                    normalization_fit_ids=[ep["id"] for ep in train],
                    selection_ids=[], selection_note="This fit does not select parameters. Later aggregate OOF selection uses all scored heldout groups and is selection-biased.",
                    model_file=str((Path(output) / "FIT_MODELS" / (fit_id + ".json")).resolve()), parameter_sha256=digest(fitted)))
            status = "PASS" if len(scores) == len(prepared) else "INCOMPLETE_GROUP_COVERAGE"
            reports.append(dict(candidate_index=ci, spec=spec, status=status, metrics=aggregate(scores),
                unavailable_fold_groups=unavailable_folds, session_scores=scores, folds=local_folds))
        usable = [row for row in reports if row["status"] == "PASS"]
        for row in reports:
            folds.extend(row.get("folds", []))
        if not usable:
            models.append(dict(model_id=target + "_" + family, target=target, family=family, status="UNAVAILABLE_COMPLETE_OOF_COVERAGE", candidate_reports=reports))
            candidate_reports.extend(dict(family=family, target=target, **row) for row in reports)
            continue
        key = lambda row:(row["metrics"]["mean_cohort_MAE"], row["metrics"]["mean_cohort_RMSE"], row["candidate_index"])
        chosen = min(usable, key=key)
        null = min((row for row in usable if row["spec"]["feature_set"] == "null"), key=key)
        full_train = family_training(prepared, family)
        full_id = target + "_" + family + "_FULL_SELECTED"
        fitted = fit_model(full_train, chosen["spec"], family, full_id, output, counters, max_fits)
        predictions = []
        for fold in chosen["folds"]:
            fold_model = read(fold["model_file"])
            require(digest(fold_model) == fold["parameter_sha256"], "fold model digest")
            for ep in prepared:
                if ep["id"] in fold["test_session_ids"]:
                    predictions.append(dict(**score(fold_model, ep, curve=True), fold_id=fold["fold_id"], role="GROUP_OOF_SELECTION",
                        training_session_ids=fold["train_session_ids"], model_file=fold["model_file"]))
        metrics = aggregate(predictions)
        null_scores = {row["session_uid"]:row for row in null["session_scores"]}
        null_harms = [dict(session_uid=row["session_uid"], delta_MAE=row["MAE"] - null_scores[row["session_uid"]]["MAE"])
                      for row in predictions if row["MAE"] > null_scores[row["session_uid"]]["MAE"] + 1e-12]
        model_row = dict(model_id=target + "_" + family, family=family, target=target, unit=fitted["unit"], status="PASS",
            selected_spec=chosen["spec"], selected_candidate_index=chosen["candidate_index"],
            selection_role="RETROSPECTIVE_GROUP_OOF_SELECTION", selection_session_ids=[ep["id"] for ep in prepared],
            selection_bias=True, independent_external_confirmation=False, nested_validation=False,
            metrics=metrics, by_cohort=metrics["by_cohort"], predictions=predictions,
            model_folds=[dict(model_id=target + "_" + family, target=target, fold_id=fold["fold_id"],
                train_ids=fold["train_session_ids"], test_ids=fold["test_session_ids"],
                normalization_fit_ids=fold["normalization_fit_ids"], selection_role="RETROSPECTIVE_GROUP_OOF_SELECTION",
                selection_ids_used_for_final_spec=[ep["id"] for ep in prepared],
                model_file=fold["model_file"], parameter_sha256=fold["parameter_sha256"]) for fold in chosen["folds"]],
            selected_null_spec=null["spec"], selected_null_OOF_metrics=null["metrics"], null_session_scores=null["session_scores"],
            harm_vs_selected_null=null_harms, stable_better_than_null=not null_harms and metrics["mean_cohort_MAE"] < null["metrics"]["mean_cohort_MAE"],
            fullfit_train_ids=[ep["id"] for ep in full_train], fullfit_role="ALL_KNOWN_DEVELOPMENT_NOT_VALIDATION",
            parameter_sha256=digest(fitted), model_file=str((Path(output) / "FIT_MODELS" / (full_id + ".json")).resolve()),
            fullfit_observed_points=fitted["observed_points"], fullfit_design=fitted["design"], fullfit_exposure=fitted["exposure"])
        models.append(model_row)
        candidate_reports.extend(dict(family=family, target=target, **row) for row in reports)
    return models, candidate_reports, folds


def paired_comparisons(models):
    result = []
    for target in TARGETS:
        good = {row["family"]:row for row in models if row["target"] == target and row["status"] == "PASS"}
        for candidate in ("pooled", "shared_domain"):
            if candidate not in good:
                continue
            for reference in FAMILIES:
                if reference == candidate or reference not in good:
                    continue
                left = {row["session_uid"]:row for row in good[candidate]["predictions"]}
                right = {row["session_uid"]:row for row in good[reference]["predictions"]}
                ids = sorted(set(left) & set(right))
                require(all(left[i]["times_s"] == right[i]["times_s"] and left[i]["observed"] == right[i]["observed"] for i in ids), "comparison common actual target rows")
                rows = [dict(session_uid=i, cohort=left[i]["cohort"], candidate_MAE=left[i]["MAE"], reference_MAE=right[i]["MAE"],
                    delta_MAE=left[i]["MAE"] - right[i]["MAE"], delta_RMSE=left[i]["RMSE"] - right[i]["RMSE"]) for i in ids]
                by = {}
                for row in rows:
                    by.setdefault(row["cohort"], []).append(row)
                means = {key:float(np.mean([row["delta_MAE"] for row in values])) for key, values in by.items()}
                result.append(dict(target=target, candidate=candidate, reference=reference, common_session_ids=ids,
                    per_session_delta_MAE=rows, mean_cohort_delta_MAE=float(np.mean(list(means.values()))) if means else None,
                    by_cohort_delta_MAE=means, improved=sum(row["delta_MAE"] < -1e-12 for row in rows),
                    harmed=sum(row["delta_MAE"] > 1e-12 for row in rows), tied=sum(abs(row["delta_MAE"]) <= 1e-12 for row in rows),
                    uncertainty_scope="retrospective development comparison; OOF used in specification selection; no independent CI claimed"))
    return result


def null_observer_diagnostics(prepared, output, counters, max_fits):
    """Target-valid but incomplete activity: a separately named observer arm.

    Fixed null ridge=1, no tuning; within-domain leave-one-session-out. Its
    target rows never masquerade as identified route/owner activity training.
    """
    result = []
    for target in TARGETS:
        domains = sorted({ep["domain"] for ep in prepared[target]})
        for di, domain in enumerate(domains):
            values = [ep for ep in prepared[target] if ep["domain"] == domain]
            if len(values) < 2:
                result.append(dict(target=target, domain=domain, status="UNAVAILABLE_LESS_THAN_TWO_OBSERVER_SESSIONS",
                    session_ids=[ep["id"] for ep in values], role="TARGET_ONLY_DIAGNOSTIC_NOT_PRIMARY_ACTIVITY_FIT"))
                continue
            spec = dict(target=target, feature_set="null", beta=None, window_s=0., ridge=1.)
            rows, split_rows = [], []
            for hi, held in enumerate(values):
                train = [ep for ep in values if ep["id"] != held["id"]]
                fit_id = target + "_OBSERVER_D" + str(di).zfill(3) + "_LOSO" + str(hi).zfill(3)
                model = fit_model(train, spec, "pooled", fit_id, output, counters, max_fits)
                rows.append(dict(**score(model, held, curve=True), fold_id=fit_id, role="OBSERVER_ONLY_FIXED_NULL_LOSO"))
                split_rows.append(dict(fold_id=fit_id, train_ids=[ep["id"] for ep in train], test_ids=[held["id"]],
                    normalization_fit_ids=[ep["id"] for ep in train], model_file=str((Path(output)/"FIT_MODELS"/(fit_id+".json")).resolve()),
                    parameter_sha256=digest(model)))
            fit_id = target + "_OBSERVER_D" + str(di).zfill(3) + "_FULL"
            model = fit_model(values, spec, "pooled", fit_id, output, counters, max_fits)
            result.append(dict(target=target, domain=domain, status="PASS", role="TARGET_ONLY_DIAGNOSTIC_NOT_PRIMARY_ACTIVITY_FIT",
                fixed_spec=spec, predictions=rows, folds=split_rows, metrics=aggregate(rows),
                fullfit_train_ids=[ep["id"] for ep in values], parameter_sha256=digest(model),
                model_file=str((Path(output)/"FIT_MODELS"/(fit_id+".json")).resolve()),
                route_owner_learning_sessions=0, independent_external_confirmation=False,
                scope="Separate observer/baseline diagnostic. Unknown owner/admission/persist are not observed zero; these sessions do not enter the core7 integrated policy-physics fit."))
    return result


def pure_checks():
    segments = [[] for _ in ACTIVITY]
    segments[0] = [(-2., 1., 1.)]
    segments[2] = [(2., 4., 1.)]
    ep = dict(segments=segments, times=np.asarray([0., .1, 1., 2., 3., 4., 5., 700.]), anchor_s=-.5, history_start_s=-30., _cache={})
    count = 0
    for target, params in (("AP", BETAS), ("POWER_API", WINDOWS)):
        for parameter in params:
            require(np.array_equal(activity_matrix(ep, target, parameter, False), activity_matrix(ep, target, parameter)), "same-values cache")
            count += 1
    shallow = {**ep, "times":np.asarray([-.5])}
    require(np.array_equal(activity_matrix(shallow, "AP", .06), np.zeros((1, 9))), "different-grid anchor/cache")
    count += 1
    x = filtered_activity(segments, [1.], .06, -30.)[0, 0]
    require(abs(x - (1 - math.exp(-.18))) < 1e-12, "direct unit-gain kernel")
    count += 1
    require(len(candidates("AP")) == len(candidates("POWER_API")) == 14, "fixed candidate grid")
    count += 1
    activity = dict(names=list(ACTIVITY), intervals=segments, known_features=[True] * 9,
        known_until_s=800., known_until_by_feature_s=[800.] * 9)
    anchor = dict(time_s=0., available_upper_s=0., AP=30., SKIN=29., BAT=28., pre20_AP_slope_c_s=0.)
    session = dict(id="SYNTHETIC_API_FIXTURE", cohort="TEST", domain="TEST", source_pool="OLD", history_start_s=-30.,
        clock_contract="synthetic exact sample; no physical claim", activity9=activity,
        targets={"AP":dict(eligible=True, anchor=anchor, observations=[dict(t_s=t, value_c=30.) for t in (0., 100., 700.)])})
    prepared = prepare_session(session, "AP")
    require(prepared["times"][-1] == 700. and len(prepared["times"]) == 3, "actual long observations retained, no 180 clip")
    count += 1
    spec = dict(target="AP", feature_set="additive7", beta=.06, window_s=None, ridge=1.)
    norm = dict(mean=[0.] * 4, scale=[1.] * 4)
    _, labels, _ = raw_design(prepared, spec, norm, ["TEST"], False)
    model = dict(target="AP", unit="degC_HAL_AP", spec=spec, history_normalization=norm, domains=["TEST"],
        domain_enabled=False, feature_labels=labels, raw_basis_coefficients=[1.] * 7 + [0.] * 10)
    context = dict(domain="TEST", source_pool="OLD", anchor=anchor, history_start_s=-30., clock_contract="fixture")
    with_targets = predict_session(model, session, [0., 3., 700.])
    no_targets = predict_trace(model, context, activity, [0., 3., 700.])
    require(with_targets["prediction"] == no_targets["prediction"], "future target removal must not change prediction")
    require(no_targets["prediction"][0] == 30., "fixed model anchor exact")
    count += 1
    rejected = False
    try:
        predict_trace(model, context, activity, [801.])
    except ValueError:
        rejected = True
    require(rejected, "unknown future activity horizon must reject")
    count += 1
    missing = dict(activity, known_features=[False] + [True] * 8)
    rejected = False
    try:
        predict_trace(model, context, missing, [3.])
    except ValueError:
        rejected = True
    require(rejected, "missing activity is not observed zero")
    count += 1
    bundle = dict(schema="S26_INTEGRATED_PREDICTION_BUNDLE_v1", targets={"AP":dict(model=model, parameter_sha256=digest(model))})
    require(predict_bundle(bundle, context, activity, [3.])["AP"]["prediction"] == predict_trace(model, context, activity, [3.])["prediction"], "bundle fixed API")
    count += 1
    return dict(status="PASS", checks=count, new_fit=0, new_environment=0, new_NN=0, new_CostState=0)


def verify_operation(args):
    operation = read(args.operation)
    for category in ("source_hashes", "input_hashes", "protected_hashes"):
        for path, expected in operation.get(category, {}).items():
            require(sha(path) == expected, category + " SHA: " + path)
    require(any(os.path.normcase(str(Path(path).resolve())) == os.path.normcase(str(Path(__file__).resolve()))
                and expected == sha(__file__) for path, expected in operation.get("source_hashes", {}).items()), "source not frozen in operation")
    require(any(os.path.normcase(str(Path(path).resolve())) == os.path.normcase(str(Path(args.input).resolve()))
                and expected == sha(args.input) for path, expected in operation.get("input_hashes", {}).items()), "input not bound in operation")
    require(os.path.normcase(str(Path(args.output).resolve())) == os.path.normcase(str(Path(operation["execution_output"]).resolve())), "registered output path")
    return operation


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--operation", required=True)
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--max-fits", type=int, default=3000)
    args = parser.parse_args()
    operation = verify_operation(args)
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    require(not (output / "FIT_RECEIPTS.jsonl").exists() and not (output / "INTEGRATED_MODEL_RESULTS.json").exists(), "new immutable fit output required; no automatic consumed fit retry")
    data = read(args.input)
    require(data.get("schema") == DATA_SCHEMA, "integrated extractor schema")
    sessions = data["sessions"]
    require(len({uid(session) for session in sessions}) == len(sessions), "duplicate UID")
    physical = [session.get("physical_session_key", uid(session)) for session in sessions]
    require(len(set(physical)) == len(physical), "duplicate physical session keys must be source copies, not independent fit units")
    inventory, prepared_by_target = [], {target:[] for target in TARGETS}
    observer_only = {target:[] for target in TARGETS}
    for session in sessions:
        item = dict(session_uid=uid(session), physical_session_key=session.get("physical_session_key"), cohort=cohort(session),
            cv_group=group(session), domain=session["domain"], source_pool=pool(session),
            role=session.get("data_role"), target_eligibility={}, exclusions={}, raw_refs=session.get("raw_refs", []),
            clock_contract=session.get("clock_contract"), activity_known=session.get("activity9", {}).get("known_features"),
            activity_known_until_s=session.get("activity9", {}).get("known_until_s"),
            source_contract_metadata={key:session.get(key) for key in ("timing_contract", "selected_source", "source_copies", "provenance", "metadata", "compatibility", "prior_role")})
        for target in TARGETS:
            try:
                ep = prepare_session(session, target)
                if not activity_available(ep, 7):
                    observer_only[target].append(ep)
                    item["target_eligibility"][target] = dict(eligible=False, observed_target_eligible=True,
                        observer_only=True, actual_window_s=ep["actual_window_s"], observations=len(ep["times"]))
                    item["exclusions"][target] = "Primary core7 unknown; target retained in separately fitted fixed-null observer diagnostic, not zero-filled"
                    continue
                prepared_by_target[target].append(ep)
                item["target_eligibility"][target] = dict(eligible=True, actual_window_s=ep["actual_window_s"], observations=len(ep["times"]))
            except (ValueError, KeyError, TypeError) as error:
                item["target_eligibility"][target] = dict(eligible=False)
                item["exclusions"][target] = type(error).__name__ + ": " + str(error)
        inventory.append(item)
    counts = {target:dict(sessions=len(values), groups=len({ep["cv_group"] for ep in values}),
        cohorts=len({ep["cohort"] for ep in values}), actual_points=sum(len(ep["times"]) for ep in values),
        no_forced_end_180=True) for target, values in prepared_by_target.items()}
    observer_cap = sum(len(values) + len({ep["domain"] for ep in values}) for values in observer_only.values())
    upper = sum(56 * counts[target]["groups"] + 4 for target in TARGETS) + observer_cap
    require(args.max_fits >= upper, "fit cap below exact pre-fit grid upper bound: " + str(upper))
    cap = operation.get("max_fits", args.max_fits)
    require(args.max_fits <= cap, "CLI fit cap exceeds operation")
    save_new(output / "MODEL_RUN_PLAN.json", dict(schema=SCHEMA, input_sha256=sha(args.input), source_sha256=sha(__file__),
        operation_sha256=sha(args.operation), inventory=inventory, target_counts=counts,
        families=list(FAMILIES), candidates={target:candidates(target) for target in TARGETS},
        observer_only_session_ids={target:[ep["id"] for ep in values] for target,values in observer_only.items()},
        observer_only_max_fits=observer_cap,
        exact_upper_fit_count=upper, registered_max_fits=args.max_fits,
        CV="leave one collection cv_group out, then select specification using mean-cohort OOF MAE/RMSE/grid order",
        selection_bias=True, independent_external_confirmation=False, no_new_policy_environments=True,
        full_window_policy="all actual nonnegative samples in explicit target window; absent window means through final actual sample; no 180 clipping",
        weights="cohort equal, within cohort session equal, within session actual sample equal", created_unix=time.time()))
    save_new(output / "PURE_CHECKS.json", pure_checks())
    counters = dict(fit_attempts=0, fits_completed=0)
    models, reports, folds = [], [], []
    for target in TARGETS:
        if counts[target]["groups"] < 2:
            continue
        target_models, target_reports, target_folds = evaluate_target(prepared_by_target[target], target, output, counters, args.max_fits)
        models.extend(target_models)
        reports.extend(target_reports)
        folds.extend(target_folds)
    observer_diagnostics = null_observer_diagnostics(observer_only, output, counters, args.max_fits)
    final, bundle_targets = {}, {}
    for target in TARGETS:
        choices = [row for row in models if row["target"] == target and row["family"] in ("pooled", "shared_domain") and row["status"] == "PASS"]
        if not choices:
            final[target] = dict(status="UNAVAILABLE_NO_VALID_INTEGRATED_MODEL")
            continue
        chosen = min(choices, key=lambda row:(row["metrics"]["mean_cohort_MAE"], row["metrics"]["mean_cohort_RMSE"], FAMILIES.index(row["family"])))
        require({ep["source_pool"] for ep in prepared_by_target[target]} == {"OLD", "M8"}, "final integrated target lacks both source pools")
        final[target] = dict(status="EXPERIMENTAL_ALL_KNOWN_DEVELOPMENT", model_id=chosen["model_id"], family=chosen["family"],
            model_file=chosen["model_file"], parameter_sha256=chosen["parameter_sha256"],
            fullfit_train_ids=chosen["fullfit_train_ids"], independent_confirmation=False,
            stable_better_than_null=chosen["stable_better_than_null"], caution="retrospective OOF selection and all-known refit; route/physical causal effect unidentified")
        bundle_targets[target] = dict(model=read(chosen["model_file"]), parameter_sha256=chosen["parameter_sha256"],
            model_id=chosen["model_id"], model_file=chosen["model_file"], fullfit_train_ids=chosen["fullfit_train_ids"])
    save_new(output / "FINAL_MODEL_BUNDLE.json", dict(schema="S26_INTEGRATED_PREDICTION_BUNDLE_v1", scope=SCOPE,
        targets=bundle_targets, API="predict_bundle(bundle, initial_context, activity9, times_s)",
        causal_inputs="completed precommon actual HAL anchor/history or idle API background; known saved activity intervals; no future target sensors",
        experimental=True, independent_external_confirmation=False, external_meter_calibrated=False))
    save_new(output / "CANDIDATE_OOF_SCORES.json", dict(schema=SCHEMA, reports=reports))
    results = dict(schema=RESULT_SCHEMA, scope=SCOPE, inventory=dict(sessions=inventory, counts=counts), folds=folds,
        models=models, comparisons=paired_comparisons(models), final_integrated=final, fit_counts=counters,
        observer_only_diagnostics=observer_diagnostics,
        source_bindings=dict(input_path=str(Path(args.input).resolve()), input_sha256=sha(args.input),
            source_path=str(Path(__file__).resolve()), source_sha256=sha(__file__), operation_sha256=sha(args.operation)),
        validation=dict(nested=False, independent_external_confirmation=False, selection_bias=True,
            train_test_intersection_zero=True, selection_ids_include_OOF_test_ids=True,
            bootstrap_independent_sensor_claim=False, API_scale_external_calibration=False,
            physical_policy_causal_effect_identified=False),
        new_environment=0, new_NN=0, new_CostState=0, new_NN_optimizer=0, new_Adam=0,
        bounded_regression_fits=counters["fits_completed"], created_unix=time.time())
    save_new(output / "INTEGRATED_MODEL_RESULTS.json", results)
    save_new(output / "INTEGRATED_MODEL_SEAL.json", dict(schema=SCHEMA, results_sha256=sha(output / "INTEGRATED_MODEL_RESULTS.json"),
        candidate_scores_sha256=sha(output / "CANDIDATE_OOF_SCORES.json"), fit_receipts_sha256=sha(output / "FIT_RECEIPTS.jsonl"),
        final_model_bundle_sha256=sha(output / "FINAL_MODEL_BUNDLE.json"),
        final_integrated=final, fit_counts=counters, created_unix=time.time(), status="FIT_COMPLETE_PENDING_INDEPENDENT_AUDIT"))


if __name__ == "__main__":
    main()
