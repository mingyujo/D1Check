"""Retrospective CC_DG energy-error accounting and bounded PC choice preview.

No device commands, model refit, arrival scheduling, or guaranteed thresholds.
"""
from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path

from tools.d1_energy_operational_sim import (
    COUNTS, VERSION as PROFILE_VERSION, digest, folder_for, identity, predict, read,
    require, write_new,
)

VERSION = "energy-operational-ccdg-decision-pc-v1"
METRICS = ("work_completion_s", "common_window_energy_j_conditional", "load_ap_peak_c")
SEGMENTS = ("load", "post_work_wait")


def check_lineage(profile_path, evaluation_path):
    profile, evaluation = read(profile_path), read(evaluation_path)
    require(profile["version"] == PROFILE_VERSION and
            evaluation["profile_sha256"] == digest(profile_path) and
            evaluation["accuracy_pass"] is None and
            evaluation["pass_thresholds"] is None,
            "frozen profile / descriptive evaluation mismatch")
    return profile, evaluation


def decompose(profile_path, evaluation_path, plan_path, run_root):
    """Accounting identity; explanation of recorded terms, not causal attribution."""
    profile, evaluation = check_lineage(profile_path, evaluation_path)
    plan, _ = identity(plan_path, run_root)
    require(profile["plan_sha256"] == digest(plan_path), "plan mismatch")
    rows = []
    for entry in plan["entries"][2:]:
        mode = entry["mode"]
        require(entry["phase"] == "confirmation", "unexpected development row")
        observed = read(folder_for(run_root, entry) / "validated.json")
        require(observed["status"] == "eligible_descriptive_only" and
                observed["work_requests"] == 870 and
                observed["condition"] == f"CC_DG_{mode}", "ineligible record")
        model = profile["conditions"][mode]
        prediction = evaluation["outcomes"][mode]["prediction"]
        require(prediction["condition"] == f"CC_DG_{mode}", "prediction mismatch")
        row = dict(mode=mode, block="confirmation", session_id=entry["session_id"],
            development_resident_baseline_w=model["phases"]["resident_baseline"]["whole_device_power_w"],
            confirmation_resident_baseline_w=observed["phases"]["resident_baseline"]["energy"]["mean_power_w"],
            development_initial_ap_c=model["observed_initial_ap_c"],
            confirmation_initial_ap_c=observed["phases"]["temperature_preparation"]["ap_start_c"],
            predicted_common_j=prediction["common_window_energy_j_conditional"],
            observed_common_j=observed["metrics"]["common_window"]["full_energy_j"],
            observed_common_duration_s=observed["metrics"]["common_window"]["duration_s"])
        require(row["observed_common_j"] is not None, "incomplete common energy")
        phase_error_total = 0.0
        for name in SEGMENTS:
            dev_phase = model["phases"][name]
            actual_phase = observed["phases"][name]["energy"]
            pred_phase = next(p for p in prediction["phase_trace"] if p["phase"] == name)
            p_dev, p_obs = dev_phase["whole_device_power_w"], actual_phase["mean_power_w"]
            t_dev = pred_phase["end_s"] - pred_phase["start_s"]
            t_obs = actual_phase["duration_s"]
            measured_j = actual_phase["full_energy_j"]
            require(p_dev is not None and p_obs is not None and measured_j is not None,
                    f"incomplete {name} energy")
            duration_term = (t_dev - t_obs) * p_dev
            power_term = t_obs * (p_dev - p_obs)
            phase_error = pred_phase["whole_device_energy_j_conditional"] - measured_j
            require(math.isclose(phase_error, duration_term + power_term,
                                 rel_tol=0, abs_tol=1e-7), f"{name} identity mismatch")
            prefix = "work" if name == "load" else "post_work_idle"
            row.update({f"{prefix}_predicted_duration_s": t_dev,
                        f"{prefix}_observed_duration_s": t_obs,
                        f"{prefix}_development_power_w": p_dev,
                        f"{prefix}_confirmation_power_w": p_obs,
                        f"{prefix}_predicted_j": pred_phase["whole_device_energy_j_conditional"],
                        f"{prefix}_observed_j": measured_j,
                        f"{prefix}_duration_error_j": duration_term,
                        f"{prefix}_power_error_j": power_term,
                        f"{prefix}_total_error_j": phase_error})
            phase_error_total += phase_error
        # The raw common-window integral and the two named phases differ slightly
        # at their monotonic boundaries. Preserve that term, including its sign.
        row["window_boundary_residual_j"] = (
            row["work_observed_j"] + row["post_work_idle_observed_j"] -
            row["observed_common_j"])
        row["predicted_minus_observed_j"] = (
            row["predicted_common_j"] - row["observed_common_j"])
        require(math.isclose(row["predicted_minus_observed_j"],
                             phase_error_total + row["window_boundary_residual_j"],
                             rel_tol=0, abs_tol=1e-7), "common-window identity mismatch")
        rows.append(row)
    by_mode = {row["mode"]: row for row in rows}
    contrast = {field: by_mode["parallel"][field] - by_mode["serial"][field]
                for field in rows[0] if isinstance(rows[0][field], (float, int))}
    require(math.isclose(contrast["predicted_minus_observed_j"],
                         evaluation["contrasts"]["common_window_energy_j_conditional"][
                             "predicted_parallel_minus_serial"] -
                         evaluation["contrasts"]["common_window_energy_j_conditional"][
                             "observed_parallel_minus_serial"],
                         abs_tol=1e-7), "contrast identity mismatch")
    return dict(version=VERSION, profile_sha256=digest(profile_path),
                evaluation_sha256=digest(evaluation_path),
                meaning="retrospective_accounting_not_causal_or_independent_validation",
                rows=rows, parallel_minus_serial=contrast)


DECOMPOSITION_FIELDS = (
    ("development_resident_baseline_w", "W"),
    ("confirmation_resident_baseline_w", "W"),
    ("work_predicted_duration_s", "s"),
    ("work_observed_duration_s", "s"),
    ("work_development_power_w", "W"),
    ("work_confirmation_power_w", "W"),
    ("work_duration_error_j", "conditional J"),
    ("work_power_error_j", "conditional J"),
    ("post_work_idle_predicted_duration_s", "s"),
    ("post_work_idle_observed_duration_s", "s"),
    ("post_work_idle_development_power_w", "W"),
    ("post_work_idle_confirmation_power_w", "W"),
    ("post_work_idle_duration_error_j", "conditional J"),
    ("post_work_idle_power_error_j", "conditional J"),
    ("window_boundary_residual_j", "conditional J"),
    ("predicted_common_j", "conditional J"),
    ("observed_common_j", "conditional J"),
    ("predicted_minus_observed_j", "conditional J"),
)


def write_decomposition_csv(decomposition, path):
    by_mode = {row["mode"]: row for row in decomposition["rows"]}
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream,
            fieldnames=("measure", "unit", "parallel", "serial", "parallel_minus_serial"))
        writer.writeheader()
        for field, unit in DECOMPOSITION_FIELDS:
            writer.writerow(dict(measure=field, unit=unit,
                parallel=by_mode["parallel"][field], serial=by_mode["serial"][field],
                parallel_minus_serial=decomposition["parallel_minus_serial"][field]))


def query_from_recorded_profile(profile, initial_ap_c):
    """A no-threshold demo; its AP start must be an already observed episode value."""
    return dict(profile_sha256=None, fingerprint=profile["fingerprint"],
        model_sha256=profile["model_sha256"], input_sha256=profile["input_sha256"],
        work_counts=profile["work_counts"], resident_runtimes=4,
        cpu_threads=1, sensor="AP", pair="CC_DG",
        initial_ap_c=initial_ap_c,
        initial_ap_source="observed_same_episode_preload",
        work_completion_boundary="load_start_to_all_870_complete",
        energy_metric="common_480s_whole_device_conditional_j",
        max_work_completion_s=None, max_load_ap_peak_c=None)


def _optional_cap(value, name):
    require(value is None or (type(value) in (float, int) and
            math.isfinite(value) and value > 0), f"invalid {name}")
    return value


def decide(profile_path, evaluation_path, query):
    try:
        profile, evaluation = check_lineage(profile_path, evaluation_path)
    except ValueError as exc:
        return dict(version=VERSION, status="OUT_OF_SUPPORT", reason=str(exc))
    if not isinstance(query, dict):
        return dict(version=VERSION, status="OUT_OF_SUPPORT", reason="query must be an object")
    required = ("profile_sha256", "fingerprint", "model_sha256", "input_sha256",
                "work_counts", "resident_runtimes", "cpu_threads", "sensor", "pair",
                "initial_ap_c", "initial_ap_source", "work_completion_boundary",
                "energy_metric", "max_work_completion_s", "max_load_ap_peak_c")
    missing = [key for key in required if key not in query]
    if missing:
        return dict(version=VERSION, status="OUT_OF_SUPPORT", reason=f"missing input: {missing}")
    extra = sorted(set(query) - set(required))
    if extra:
        return dict(version=VERSION, status="OUT_OF_SUPPORT",
                    reason=f"unrecognized condition or requested metric: {extra}")
    expected = dict(profile_sha256=digest(profile_path),
        fingerprint=profile["fingerprint"], model_sha256=profile["model_sha256"],
        input_sha256=profile["input_sha256"], work_counts=COUNTS,
        resident_runtimes=4, cpu_threads=1, sensor="AP", pair="CC_DG",
        initial_ap_source="observed_same_episode_preload",
        work_completion_boundary="load_start_to_all_870_complete",
        energy_metric="common_480s_whole_device_conditional_j")
    mismatch = [key for key, value in expected.items() if query[key] != value]
    if mismatch:
        return dict(version=VERSION, status="OUT_OF_SUPPORT",
                    reason=f"unsupported identity/boundary: {mismatch}")
    try:
        deadline = _optional_cap(query["max_work_completion_s"], "deadline")
        ap_cap = _optional_cap(query["max_load_ap_peak_c"], "AP cap")
        require(type(query["initial_ap_c"]) in (float, int) and
                math.isfinite(query["initial_ap_c"]), "invalid initial AP")
        require(all(math.isclose(query["initial_ap_c"],
                    evaluation["outcomes"][mode]["initial_ap_c"], abs_tol=1e-9)
                    for mode in ("serial", "parallel")),
                "OUT_OF_SUPPORT: no matched confirmation AP start for both arms")
        nominal = {mode: predict(profile, mode=mode,
                     initial_ap_c=query["initial_ap_c"],
                     initial_ap_source=query["initial_ap_source"],
                     fingerprint=query["fingerprint"],
                     model_sha256=query["model_sha256"],
                     input_sha256=query["input_sha256"],
                     work_counts=query["work_counts"],
                     resident_runtimes=query["resident_runtimes"],
                     cpu_threads=query["cpu_threads"], sensor="AP")
                   for mode in ("serial", "parallel")}
    except (ValueError, KeyError) as exc:
        return dict(version=VERSION, status="OUT_OF_SUPPORT", reason=str(exc))
    # One confirmation session per arm supplies only a retrospective sensitivity
    # scenario. These differences are neither bounds nor confidence intervals.
    records = {}
    for mode, predicted in nominal.items():
        nominal_values = {metric: predicted[metric] for metric in METRICS}
        single_error = evaluation["outcomes"][mode]["errors"]
        shifted = {metric: nominal_values[metric] - single_error[metric]
                   for metric in METRICS}
        records[mode] = dict(nominal=nominal_values,
                             one_confirmation_error_scenario=shifted)
    def feasible(values):
        return ((deadline is None or values["work_completion_s"] <= deadline) and
                (ap_cap is None or values["load_ap_peak_c"] <= ap_cap))
    feasibility = {mode: {scenario: feasible(values) for scenario, values in record.items()}
                   for mode, record in records.items()}
    consistent = {mode: len(set(feasibility[mode].values())) == 1
                  for mode in records}
    if not all(consistent.values()):
        status, candidate, reason = ("INDETERMINATE", None,
            "a constraint crosses the single-confirmation-error sensitivity scenario")
    else:
        eligible = [mode for mode in records if feasibility[mode]["nominal"]]
        if len(eligible) == 1:
            status, candidate, reason = ("MODEL_CANDIDATE", eligible[0],
                "only this arm satisfies the supplied work/AP limits in both descriptive scenarios")
        elif not eligible:
            status, candidate, reason = ("INDETERMINATE", None,
                "neither arm satisfies the supplied limits in these descriptive scenarios")
        else:
            status, candidate, reason = ("TRADEOFF", None,
                "both arms meet supplied limits; parallel is faster but hotter and common-energy ranking changes")
    return dict(version=VERSION, status=status, model_candidate=candidate,
        reason=reason, profile_sha256=digest(profile_path),
        evaluation_sha256=digest(evaluation_path),
        constraints=dict(max_work_completion_s=deadline, max_load_ap_peak_c=ap_cap),
        fixed_energy_metric="common_480s_whole_device_conditional_j",
        measurements_not_guarantees=True, nominal_and_sensitivity=records,
        feasibility=feasibility, policy_or_device_validation=False,
        note="one confirmation error per arm is a retrospective scenario, not a bound or confidence interval")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    decomp = sub.add_parser("decompose")
    decomp.add_argument("--profile", required=True)
    decomp.add_argument("--evaluation", required=True)
    decomp.add_argument("--plan", required=True)
    decomp.add_argument("--run", required=True)
    decomp.add_argument("--output", required=True)
    decomp.add_argument("--csv", required=True)
    choice = sub.add_parser("decide")
    choice.add_argument("--profile", required=True)
    choice.add_argument("--evaluation", required=True)
    choice.add_argument("--query", required=True)
    choice.add_argument("--output", required=True)
    args = parser.parse_args()
    if args.action == "decompose":
        result = decompose(args.profile, args.evaluation, args.plan, args.run)
        write_new(args.output, result)
        write_decomposition_csv(result, args.csv)
    else:
        write_new(args.output, decide(args.profile, args.evaluation, read(args.query)))


if __name__ == "__main__":
    main()
