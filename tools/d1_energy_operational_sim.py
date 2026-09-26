"""Bounded CC_DG operational episode replay and development-only template.

This is not an arrival scheduler, a GPU-rail meter, or an identified thermal law.
No device commands. The legacy energy/account() scope and policies stay unchanged.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from tools import d1_energy_collection as collection

VERSION = "energy-operational-ccdg-pc-v1"
PHASES = ("temperature_preparation", "resident_baseline", "load",
          "post_work_wait", "resident_cooling")
MODE_ORDER = ("serial", "parallel")
COUNTS = {"classification_CPU": 678, "detection_GPU": 192}
PAIR = "CC_DG"
SENSOR = "AP"


def require(value, message):
    if not value:
        raise ValueError(message)


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_new(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        stream.write("\n")


def identity(plan_path, run_root):
    plan = read(plan_path)
    receipt = read(Path(run_root) / "FINAL_RECEIPT.json")
    require(plan["experiment_id"] == "ENERGY-OPERATIONAL-PAIR-01" and
            plan["operational_only"] is True and plan["budget"]["sessions"] == 4,
            "unsupported plan")
    require(receipt["status"] == "completed_descriptive_only" and receipt["sessions"] == 4,
            "incomplete original denominator")
    require([(e["phase"], e["mode"], e["pair"]) for e in plan["entries"]] ==
            [("development", "serial", PAIR), ("development", "parallel", PAIR),
             ("confirmation", "parallel", PAIR), ("confirmation", "serial", PAIR)],
            "unexpected order/conditions")
    for entry in plan["entries"]:
        manifest_path = Path(plan_path).parent / entry["manifest"]
        manifest = read(manifest_path)
        require(digest(manifest_path) == entry["manifest_sha256"] and
                manifest["session_id"] == entry["session_id"] and
                manifest["mode"] == entry["mode"] and manifest["pair"] == PAIR and
                manifest["cpu_threads"] == 1 and
                manifest["counts"] == {"classification": 678, "detection": 192} and
                manifest["device_fingerprint"] == plan["device_fingerprint"] and
                manifest["apk_sha256"] == plan["apk_sha256"],
                "plan/manifest/runtime condition mismatch")
    freeze_path = Path(run_root) / "development_freeze.json"
    require(digest(freeze_path) == read(Path(run_root) / "freeze_receipt.json")["sha256"],
            "development freeze hash")
    freeze = read(freeze_path)
    require(freeze["plan_sha256"] == digest(plan_path) and freeze["source"] == "development_only",
            "development freeze identity")
    return plan, freeze


def folder_for(run_root, entry):
    return Path(run_root) / f"{entry['index']:02d}_{entry['session_id']}"


def thermal_knots(thermal_path, phase):
    rows = [r for r in (json.loads(line) for line in Path(thermal_path).read_text(
        encoding="utf-8").splitlines()) if phase["start_ns"] <= r["mono_ns"] <= phase["end_ns"]]
    require(len(rows) >= 2 and all(r.get(SENSOR) not in (None, "") and
            r.get("thermal_status") == "0" for r in rows), "AP trace coverage")
    times = [r["mono_ns"] for r in rows]
    require(all(0 < b-a <= 10_000_000_000 for a, b in zip(times, times[1:])),
            "AP trace gap")
    first, last = times[0], times[-1]
    base = float(rows[0][SENSOR])
    # Empirical path shape only. No tau, ambient, or power-to-heat coefficient.
    return [[(r["mono_ns"]-first)/(last-first), float(r[SENSOR])-base] for r in rows]


def build_profile(plan_path, run_root):
    """Reads the frozen DEVELOPMENT conditions; never opens confirmation files."""
    plan, freeze = identity(plan_path, run_root)
    conditions = {}
    source = {}
    for entry in plan["entries"][:2]:
        mode = entry["mode"]
        folder = folder_for(run_root, entry)
        stats_path = folder / "validated.json"
        stats = read(stats_path)
        require(stats == freeze["conditions"][f"{PAIR}_{mode}"] and
                stats["status"] == "eligible_descriptive_only" and
                stats["work_requests"] == 870 and stats["independent_sessions"] == 1,
                "development-only validated identity")
        require(stats["metrics"]["equal_work"]["full_energy_j"] is not None and
                stats["metrics"]["common_window"]["full_energy_j"] is not None,
                "development energy coverage")
        phase_model = {}
        transition_s = {}
        for name in PHASES:
            phase = stats["phases"][name]
            power = phase["energy"]["mean_power_w"]
            require(power is not None and math.isfinite(power) and power >= 0,
                    "development phase power")
            phase_model[name] = dict(duration_s=phase["energy"]["duration_s"],
                                     whole_device_power_w=(power if phase["energy"]["full_energy_j"] is not None else None),
                                     covered_mean_power_w=power,
                                     missing_energy_s=phase["energy"]["missing_s"],
                                     ap_knots=thermal_knots(folder / "thermal.jsonl", phase))
        for before, after in zip(PHASES, PHASES[1:]):
            gap = (stats["phases"][after]["start_ns"] -
                   stats["phases"][before]["end_ns"]) / 1e9
            require(0 <= gap < 10, "unaccounted phase boundary")
            transition_s[after] = gap
        require(0 < stats["metrics"]["equal_work"]["duration_s"] <=
                phase_model["load"]["duration_s"] < 480,
                "development work/common boundary")
        conditions[mode] = dict(phases=phase_model, transition_s=transition_s,
            work_completion_s=stats["metrics"]["equal_work"]["duration_s"],
            observed_initial_ap_c=stats["phases"]["temperature_preparation"]["ap_start_c"],
            source_session_id=entry["session_id"])
        source[mode] = dict(validated_sha256=digest(stats_path),
                            thermal_sha256=digest(folder / "thermal.jsonl"))
    return dict(version=VERSION, evidence="development_episode_template",
        role="fixed_episode_conditional_prediction_not_dynamics_or_policy_validation",
        plan_sha256=digest(plan_path), development_freeze_sha256=digest(
            Path(run_root) / "development_freeze.json"),
        apk_sha256=plan["apk_sha256"], fingerprint=plan["device_fingerprint"],
        model_sha256={key: plan["source_files"][key]["sha256"] for key in
                      ("efficientnet_lite0.tflite", "efficientdet_lite0.tflite")},
        input_sha256={key: plan["source_files"][key]["sha256"] for key in
                      ("00575b9132bb3746.png", "anchors.json")},
        pair=PAIR, work_counts=COUNTS, cpu_threads=1, resident_runtimes=4,
        source_sha256={key: value["sha256"] for key, value in plan["source_files"].items()},
        temperature_preparation=plan["temperature_preparation"],
        fixed_common_window_s=480, sensor=SENSOR, battery_temperature_model=None,
        current_ua_per_raw_hypothesis=1000, absolute_energy_certified=False,
        thermal_law_identified=False, stage_order=list(PHASES), conditions=conditions,
        development_sources=source, confirmation_sources=None)


def evaluation_spec(profile_path):
    return dict(version=VERSION, profile_sha256=digest(profile_path),
        confirmation_role="post_summary_seen_limited_holdout_not_preregistered_independent_validation",
        phase_alignment="AP path compared at actual monotonic timestamps from first preparation AP sample; no future phase boundary is a model input",
        initial_condition="observed first AP in same confirmation preparation; shifted development AP template is an unvalidated assumption",
        metrics=["work_completion_s_signed_error", "work_energy_j_signed_error",
                 "common_window_energy_j_signed_error", "ap_path_mae_c",
                 "ap_path_max_abs_error_c", "load_ap_peak_c_signed_error",
                 "parallel_minus_serial_direction_by_block"],
        pass_thresholds=None, retune_on_confirmation=False,
        energy_unit="conditional_J_A24_raw_mA_hypothesis_whole_device",
        thermal_sensor="AP_only_BAT_unsupported")


def _interpolate(knots, fraction):
    if fraction <= 0:
        return knots[0][1]
    if fraction >= 1:
        return knots[-1][1]
    for a, b in zip(knots, knots[1:]):
        if a[0] <= fraction <= b[0]:
            return a[1] + (b[1]-a[1])*(fraction-a[0])/(b[0]-a[0])
    raise ValueError("invalid AP knots")


def predict(profile, *, mode, initial_ap_c, fingerprint, model_sha256,
            input_sha256, work_counts, initial_ap_source,
            resident_runtimes=4, cpu_threads=1, sensor="AP"):
    """Only the measured fixed episode, not arbitrary arrivals/offsets/duty."""
    require(profile["version"] == VERSION and profile["pair"] == PAIR and
            profile["sensor"] == "AP" and profile["battery_temperature_model"] is None,
            "profile/sensor mismatch")
    require(mode in MODE_ORDER and fingerprint == profile["fingerprint"] and
            model_sha256 == profile["model_sha256"] and
            input_sha256 == profile["input_sha256"] and
            work_counts == profile["work_counts"] and resident_runtimes == 4 and
            cpu_threads == profile["cpu_threads"] == 1 and sensor == "AP",
            "OUT_OF_SUPPORT: condition, model, input, workload, or sensor")
    require(isinstance(initial_ap_c, (int, float)) and math.isfinite(initial_ap_c),
            "invalid initial AP")
    require(initial_ap_source == "observed_same_episode_preload",
            "OUT_OF_SUPPORT: synthetic initial AP sweep")
    require(mode in profile["conditions"], "OUT_OF_SUPPORT: mode has no measured template")
    condition = profile["conditions"][mode]
    # This is only a measured-start alignment, not an identified temperature
    # response to a changed initial state. Callers must not sweep this input.
    phases = condition["phases"]
    load_duration = phases["load"]["duration_s"]
    require(load_duration < profile["fixed_common_window_s"], "unfinished common work")
    durations = {name: phases[name]["duration_s"] for name in PHASES}
    durations["post_work_wait"] = profile["fixed_common_window_s"]-load_duration
    trace = []
    now = 0.0
    ap = float(initial_ap_c)
    known_phase_energy = 0.0
    transition_time = 0.0
    for name in PHASES:
        if trace:
            gap = condition["transition_s"][name]
            require(0 <= gap < 10, "invalid transition")
            now += gap
            transition_time += gap
        state = phases[name]
        duration = durations[name]
        power = state["whole_device_power_w"]
        require(duration > 0 and math.isfinite(duration) and
                (power is None or (power >= 0 and math.isfinite(power))), "invalid state")
        knots = state["ap_knots"]
        require(knots[0][0] == 0 and knots[-1][0] == 1, "invalid AP template")
        path = [[now+duration*u, ap+delta] for u, delta in knots]
        phase_energy = duration*power if power is not None else None
        trace.append(dict(phase=name, start_s=now, end_s=now+duration,
                          ap_start_c=ap, ap_end_c=path[-1][1],
                          ap_peak_c=max(x[1] for x in path),
                          whole_device_energy_j_conditional=phase_energy,
                          path=path))
        now += duration
        ap = path[-1][1]
        if phase_energy is not None:
            known_phase_energy += phase_energy
    load = trace[2]
    post = trace[3]
    require(load["whole_device_energy_j_conditional"] is not None and
            post["whole_device_energy_j_conditional"] is not None,
            "OUT_OF_SUPPORT: incomplete work/common energy")
    common_energy = load["whole_device_energy_j_conditional"] + post[
        "whole_device_energy_j_conditional"]
    work_s = condition["work_completion_s"]
    return dict(version=VERSION, mode="conditional_episode_prediction",
        condition=f"{PAIR}_{mode}", work_counts=work_counts,
        work_completion_s=work_s,
        work_energy_j_conditional=phases["load"]["whole_device_power_w"]*work_s,
        common_window_s=profile["fixed_common_window_s"],
        common_window_energy_j_conditional=common_energy,
        preparation_to_cooling_s=now,
        known_phase_energy_j_conditional=known_phase_energy,
        known_phase_energy_is_full_episode=False,
        unmeasured_transition_s=transition_time,
        unmeasured_transition_energy_j_conditional=None,
        preparation_to_cooling_energy_j_conditional=None,
        load_ap_peak_c=load["ap_peak_c"], ap_end_c=ap,
        thermal_sensor="AP", battery_temperature_prediction=None,
        initial_ap_source=initial_ap_source,
        initial_ap_offset_assumption_unvalidated=True,
        phase_trace=trace, absolute_energy_certified=False,
        inferred_thermal_tau=None, experiment_ready=False)


def at_time(prediction, time_s):
    for phase in prediction["phase_trace"]:
        if phase["start_s"] <= time_s <= phase["end_s"]:
            fraction = ((time_s-phase["start_s"])/
                        (phase["end_s"]-phase["start_s"]))
            knots = [[(t-phase["start_s"])/(phase["end_s"]-phase["start_s"]), v]
                     for t, v in phase["path"]]
            return _interpolate(knots, fraction)
    return None


def measured_initial_ap(folder, stats):
    start = stats["phases"]["temperature_preparation"]["start_ns"]
    end = stats["phases"]["temperature_preparation"]["end_ns"]
    rows = [json.loads(line) for line in (folder / "thermal.jsonl").read_text(
        encoding="utf-8").splitlines()]
    selected = [r for r in rows if start <= r["mono_ns"] <= end and r.get(SENSOR) not in (None, "")]
    require(selected and selected[0]["mono_ns"]-start <= 10_000_000_000,
            "initial AP not available")
    return float(selected[0][SENSOR]), rows


def evaluate(profile_path, spec_path, plan_path, run_root):
    profile, spec = read(profile_path), read(spec_path)
    require(spec == evaluation_spec(profile_path), "evaluation metrics/spec changed")
    plan, _ = identity(plan_path, run_root)
    require(profile["plan_sha256"] == digest(plan_path) and
            profile["development_freeze_sha256"] == digest(Path(run_root) / "development_freeze.json"),
            "profile lineage")
    outcomes = {}
    for entry in plan["entries"][2:]:
        folder = folder_for(run_root, entry)
        stats = read(folder / "validated.json")
        require(stats["status"] == "eligible_descriptive_only" and
                stats["work_requests"] == 870 and stats["phase"] == "confirmation" and
                stats["condition"] == f"{PAIR}_{entry['mode']}", "confirmation eligibility")
        initial, thermal = measured_initial_ap(folder, stats)
        pred = predict(profile, mode=entry["mode"], initial_ap_c=initial,
                       fingerprint=plan["device_fingerprint"],
                       model_sha256=profile["model_sha256"],
                       input_sha256=profile["input_sha256"], work_counts=COUNTS,
                       initial_ap_source="observed_same_episode_preload")
        prep_start = stats["phases"]["temperature_preparation"]["start_ns"]
        cool_end = stats["phases"]["resident_cooling"]["end_ns"]
        errors = []
        for sample in thermal:
            if prep_start <= sample["mono_ns"] <= cool_end and sample.get("AP") not in (None, ""):
                estimate = at_time(pred, (sample["mono_ns"]-prep_start)/1e9)
                if estimate is not None:
                    errors.append(estimate-float(sample["AP"]))
        require(len(errors) >= 100, "insufficient AP path comparison")
        measured = stats["metrics"]
        require(measured["equal_work"]["full_energy_j"] is not None and
                measured["common_window"]["full_energy_j"] is not None,
                "confirmation energy incomplete")
        outcomes[entry["mode"]] = dict(session_id=entry["session_id"],
            initial_ap_c=initial, prediction=pred,
            measured=dict(work_completion_s=measured["equal_work"]["duration_s"],
                work_energy_j_conditional=measured["equal_work"]["full_energy_j"],
                common_window_energy_j_conditional=measured["common_window"]["full_energy_j"],
                load_ap_peak_c=stats["phases"]["load"]["ap_peak_c"]),
            errors=dict(work_completion_s=pred["work_completion_s"]-measured["equal_work"]["duration_s"],
                work_energy_j_conditional=pred["work_energy_j_conditional"]-measured["equal_work"]["full_energy_j"],
                common_window_energy_j_conditional=pred["common_window_energy_j_conditional"]-measured["common_window"]["full_energy_j"],
                load_ap_peak_c=pred["load_ap_peak_c"]-stats["phases"]["load"]["ap_peak_c"],
                ap_path_mae_c=sum(map(abs, errors))/len(errors),
                ap_path_max_abs_error_c=max(map(abs, errors)),
                ap_path_correlated_samples=len(errors)))
    contrasts = {}
    for metric in ("work_completion_s", "work_energy_j_conditional",
                   "common_window_energy_j_conditional", "load_ap_peak_c"):
        predicted = outcomes["parallel"]["prediction"][metric]-outcomes["serial"]["prediction"][metric]
        observed = outcomes["parallel"]["measured"][metric]-outcomes["serial"]["measured"][metric]
        contrasts[metric] = dict(predicted_parallel_minus_serial=predicted,
                                 observed_parallel_minus_serial=observed,
                                 direction_reproduced=(predicted == 0 and observed == 0 or
                                                       predicted*observed > 0))
    return dict(version=VERSION, role=spec["confirmation_role"],
                profile_sha256=digest(profile_path), spec_sha256=digest(spec_path),
                outcomes=outcomes, contrasts=contrasts, pass_thresholds=None,
                accuracy_pass=None, experiment_ready=False)


def replay_original(plan_path, run_root):
    """Recompute the stored metrics from existing raw logs; not an independent prediction."""
    plan, _ = identity(plan_path, run_root)
    rows = []
    for entry in plan["entries"]:
        folder = folder_for(run_root, entry)
        manifest = Path(plan_path).parent / entry["manifest"]
        computed = collection.summarize_session(folder / "artifacts", manifest, plan)
        stored = read(folder / "validated.json")
        for key in ("condition", "validation", "phases", "metrics", "warmup",
                    "eligibility_requests", "work_requests", "unit_hypothesis_ua_per_raw"):
            require(computed[key] == stored[key], f"raw replay mismatch: {entry['index']} {key}")
        rows.append(dict(index=entry["index"], phase=entry["phase"], mode=entry["mode"],
                         status="raw_replay_matches_stored_not_predictive_validation"))
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    for action in ("freeze", "replay", "evaluate"):
        item = sub.add_parser(action)
        item.add_argument("--plan", required=True)
        item.add_argument("--run", required=True)
        item.add_argument("--output", required=True)
        if action == "evaluate":
            item.add_argument("--profile", required=True)
            item.add_argument("--spec", required=True)
    args = parser.parse_args()
    if args.action == "freeze":
        output = Path(args.output)
        output.mkdir(parents=True, exist_ok=False)
        profile_path = output / "frozen_profile.json"
        write_new(profile_path, build_profile(args.plan, args.run))
        write_new(output / "evaluation_spec.json", evaluation_spec(profile_path))
        print(json.dumps(dict(status="DEVELOPMENT_ONLY_FROZEN", profile_sha256=digest(profile_path),
                              spec_sha256=digest(output / "evaluation_spec.json"))))
    elif args.action == "replay":
        write_new(args.output, dict(version=VERSION, role="recorded_trace_replay_only",
                                    rows=replay_original(args.plan, args.run)))
        print("RAW_REPLAY_MATCHED_NOT_PREDICTIVE_VALIDATION")
    else:
        write_new(args.output, evaluate(args.profile, args.spec, args.plan, args.run))
        print("CONFIRMATION_ERRORS_RECORDED_NO_PASS")


if __name__ == "__main__":
    main()
