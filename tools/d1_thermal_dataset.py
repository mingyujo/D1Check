#!/usr/bin/env python3
"""Export D1Check experiment thermal data without modifying source artifacts."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import io
import json
import math
import os
from pathlib import Path
import shutil
import sys
from typing import Any, Iterable
import uuid


DATASET_SCHEMA = "d1check_thermal_dataset"
DATASET_VERSION = 1
MANIFEST_NAME = "experiment_manifest.json"
EXPORT_DIRECTORY = "exports"
DEFAULT_MAXIMUM_OFFSET_MS = 2_000.0
SENSORS = ("AP", "BAT", "PA", "SKIN")
ENDPOINTS = (
    ("run_start", "run_start_mono_ns", True),
    ("load_start", "load_start_mono_ns", False),
    ("load_end", "load_end_mono_ns", False),
    ("cooling_end", "run_stop_mono_ns", False),
)
BASE_COLUMNS = [
    "experiment_id", "run_id", "slot_id", "condition_id", "block", "repetition",
    "order", "resource", "cpu_threads", "requested_duty_cycle_percent",
]
RUN_SUMMARY_COLUMNS = BASE_COLUMNS + [
    "slot_status", "attempts", "slot_error", "achieved_duty_cycle_percent",
    "requested_duration_s", "actual_load_duration_s",
    "completed_inference_count", "latency_mean_ms", "latency_median_ms",
    "latency_p95_ms", "validation_status", "termination_reason", "cooling_status",
    "accuracy_preflight_status", "energy_measurement_status", "formal_gpu_valid",
    "model_eligible", "exclusion_reasons", "thermal_raw_record_count",
    "thermal_valid_sample_count", "thermal_source_issues",
] + [
    f"{sensor.lower()}_{name}"
    for sensor in SENSORS
    for name in (
        "run_start_temperature_c", "load_start_temperature_c",
        "load_end_temperature_c", "cooling_end_temperature_c",
        "baseline_change_c", "load_change_c", "cooling_change_c",
        "residual_vs_load_start_c",
    )
]
PHASE_TEMPERATURE_COLUMNS = BASE_COLUMNS + [
    "sensor", "run_start_temperature_c", "load_start_temperature_c",
    "load_end_temperature_c", "cooling_end_temperature_c", "baseline_change_c",
    "load_change_c", "cooling_change_c", "residual_vs_load_start_c",
    "load_min_temperature_c", "load_max_temperature_c", "load_peak_temperature_c",
    "load_peak_mono_ns", "load_peak_elapsed_s", "cooling_min_temperature_c",
    "cooling_max_temperature_c",
] + [
    f"{endpoint}_{name}"
    for endpoint, _, _ in ENDPOINTS
    for name in (
        "selection_method", "quality", "quality_reason", "sample_mono_ns",
        "signed_offset_ms", "absolute_offset_ms", "sampling_uncertainty_ms",
    )
]
THERMAL_TIMESERIES_COLUMNS = BASE_COLUMNS + [
    "achieved_duty_cycle_percent", "mono_ns", "run_elapsed_s", "load_relative_s",
    "phase", "phase_elapsed_s", "AP", "BAT", "PA", "SKIN", "thermal_status",
    "sampling_uncertainty_ns", "parse_status",
]


class DatasetError(RuntimeError):
    pass


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise DatasetError(f"cannot read JSON object {path}: {error}") from error
    if not isinstance(value, dict):
        raise DatasetError(f"expected JSON object: {path}")
    return value


def _finite_number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def load_thermal_samples(
    path: Path, expected_run_id: str | None
) -> tuple[list[dict[str, Any]], list[str], int]:
    samples: list[dict[str, Any]] = []
    issues: list[str] = []
    raw_count = 0
    if not path.is_file():
        return samples, ["thermal_file_missing"], raw_count
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            raw_count += 1
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                issues.append(f"line_{line_number}:malformed_json")
                continue
            if not isinstance(record, dict):
                issues.append(f"line_{line_number}:not_object")
                continue
            if record.get("parse_status") != "ok":
                issues.append(
                    f"line_{line_number}:parse_status_{record.get('parse_status', 'missing')}"
                )
                continue
            if expected_run_id and record.get("run_id") not in {None, expected_run_id}:
                issues.append(f"line_{line_number}:run_id_mismatch")
                continue
            mono_ns = record.get("mono_ns")
            if isinstance(mono_ns, bool) or not isinstance(mono_ns, int):
                issues.append(f"line_{line_number}:invalid_mono_ns")
                continue
            temperatures: dict[str, float] = {}
            invalid_sensors: list[str] = []
            for sensor in SENSORS:
                parsed = _finite_number(record.get(sensor))
                if parsed is None:
                    invalid_sensors.append(sensor)
                else:
                    temperatures[sensor] = parsed
            if invalid_sensors:
                issues.append(
                    f"line_{line_number}:missing_or_invalid_sensor_{'-'.join(invalid_sensors)}"
                )
                continue
            uncertainty = record.get("sampling_uncertainty_ns")
            if uncertainty is not None and (
                isinstance(uncertainty, bool)
                or not isinstance(uncertainty, int)
                or uncertainty < 0
            ):
                issues.append(f"line_{line_number}:invalid_sampling_uncertainty_ns")
                continue
            thermal_status = record.get("thermal_status")
            try:
                thermal_status_value = (
                    int(thermal_status) if thermal_status is not None else None
                )
            except (TypeError, ValueError):
                thermal_status_value = None
            samples.append({
                "mono_ns": mono_ns,
                "sampling_uncertainty_ns": uncertainty,
                "thermal_status": thermal_status_value,
                "temperatures_c": temperatures,
                "parse_status": "ok",
                "source_line": line_number,
            })
    samples.sort(key=lambda sample: (sample["mono_ns"], sample["source_line"]))
    deduplicated: list[dict[str, Any]] = []
    seen: set[int] = set()
    for sample in samples:
        mono_ns = sample["mono_ns"]
        if mono_ns in seen:
            issues.append(f"duplicate_mono_ns:{mono_ns}")
            continue
        seen.add(mono_ns)
        deduplicated.append(sample)
    return deduplicated, issues, raw_count


def select_endpoint_sample(
    samples: list[dict[str, Any]],
    target_mono_ns: Any,
    *,
    allow_after_fallback: bool,
    maximum_offset_ms: float,
) -> dict[str, Any]:
    if isinstance(target_mono_ns, bool) or not isinstance(target_mono_ns, int):
        return {
            "quality": "invalid",
            "quality_reason": "missing_target_timestamp",
            "selection_method": None,
            "sample": None,
            "sample_mono_ns": None,
            "signed_offset_ms": None,
            "absolute_offset_ms": None,
            "sampling_uncertainty_ms": None,
        }
    before = [sample for sample in samples if sample["mono_ns"] <= target_mono_ns]
    sample = before[-1] if before else None
    method = "before_or_equal" if sample is not None else None
    if sample is None and allow_after_fallback:
        after = [sample for sample in samples if sample["mono_ns"] > target_mono_ns]
        sample = after[0] if after else None
        method = "after_fallback" if sample is not None else None
    if sample is None:
        return {
            "quality": "invalid",
            "quality_reason": "no_valid_sample_before_target",
            "selection_method": None,
            "sample": None,
            "sample_mono_ns": None,
            "signed_offset_ms": None,
            "absolute_offset_ms": None,
            "sampling_uncertainty_ms": None,
        }
    signed_offset_ms = (sample["mono_ns"] - target_mono_ns) / 1_000_000.0
    absolute_offset_ms = abs(signed_offset_ms)
    accepted = absolute_offset_ms <= maximum_offset_ms
    uncertainty = sample.get("sampling_uncertainty_ns")
    return {
        "quality": "ok" if accepted else "too_far",
        "quality_reason": None if accepted else "maximum_offset_exceeded",
        "selection_method": method,
        "sample": sample if accepted else None,
        "sample_mono_ns": sample["mono_ns"],
        "signed_offset_ms": signed_offset_ms,
        "absolute_offset_ms": absolute_offset_ms,
        "sampling_uncertainty_ms": (
            uncertainty / 1_000_000.0 if isinstance(uncertainty, int) else None
        ),
    }


def classify_phase(mono_ns: int, timestamps: dict[str, int]) -> tuple[str, int] | None:
    run_start = timestamps["run_start_mono_ns"]
    load_start = timestamps["load_start_mono_ns"]
    load_end = timestamps["load_end_mono_ns"]
    run_stop = timestamps["run_stop_mono_ns"]
    if run_start <= mono_ns < load_start:
        return "baseline", run_start
    if load_start <= mono_ns < load_end:
        return "load", load_start
    if load_end <= mono_ns < run_stop:
        return "cooling", load_end
    return None


def _valid_timestamps(summary: dict[str, Any]) -> dict[str, int] | None:
    names = (
        "run_start_mono_ns", "load_start_mono_ns", "load_end_mono_ns",
        "run_stop_mono_ns",
    )
    values = [summary.get(name) for name in names]
    if any(isinstance(value, bool) or not isinstance(value, int) for value in values):
        return None
    timestamps = dict(zip(names, values))
    if not (
        timestamps["run_start_mono_ns"] <= timestamps["load_start_mono_ns"]
        <= timestamps["load_end_mono_ns"] <= timestamps["run_stop_mono_ns"]
    ):
        return None
    return timestamps


def _difference(end: float | None, start: float | None) -> float | None:
    return end - start if end is not None and start is not None else None


def sensor_phase_row(
    base: dict[str, Any],
    sensor: str,
    endpoints: dict[str, dict[str, Any]],
    load_samples: list[dict[str, Any]],
    cooling_samples: list[dict[str, Any]],
    load_start_mono_ns: int | None,
) -> dict[str, Any]:
    temperatures: dict[str, float | None] = {}
    for endpoint, _, _ in ENDPOINTS:
        sample = endpoints[endpoint].get("sample")
        temperatures[endpoint] = (
            sample["temperatures_c"][sensor] if sample is not None else None
        )
    load_values = [(sample["temperatures_c"][sensor], sample["mono_ns"]) for sample in load_samples]
    cooling_values = [sample["temperatures_c"][sensor] for sample in cooling_samples]
    peak_value: float | None = None
    peak_mono_ns: int | None = None
    if load_values:
        peak_value = max(value for value, _ in load_values)
        peak_mono_ns = min(mono for value, mono in load_values if value == peak_value)
    row = dict(base)
    row.update({
        "sensor": sensor,
        "run_start_temperature_c": temperatures["run_start"],
        "load_start_temperature_c": temperatures["load_start"],
        "load_end_temperature_c": temperatures["load_end"],
        "cooling_end_temperature_c": temperatures["cooling_end"],
        "baseline_change_c": _difference(
            temperatures["load_start"], temperatures["run_start"]
        ),
        "load_change_c": _difference(
            temperatures["load_end"], temperatures["load_start"]
        ),
        "cooling_change_c": _difference(
            temperatures["cooling_end"], temperatures["load_end"]
        ),
        "residual_vs_load_start_c": _difference(
            temperatures["cooling_end"], temperatures["load_start"]
        ),
        "load_min_temperature_c": min((value for value, _ in load_values), default=None),
        "load_max_temperature_c": max((value for value, _ in load_values), default=None),
        "load_peak_temperature_c": peak_value,
        "load_peak_mono_ns": peak_mono_ns,
        "load_peak_elapsed_s": (
            (peak_mono_ns - load_start_mono_ns) / 1e9
            if peak_mono_ns is not None and load_start_mono_ns is not None else None
        ),
        "cooling_min_temperature_c": min(cooling_values, default=None),
        "cooling_max_temperature_c": max(cooling_values, default=None),
    })
    for endpoint, _, _ in ENDPOINTS:
        selection = endpoints[endpoint]
        row.update({
            f"{endpoint}_selection_method": selection["selection_method"],
            f"{endpoint}_quality": selection["quality"],
            f"{endpoint}_quality_reason": selection["quality_reason"],
            f"{endpoint}_sample_mono_ns": selection["sample_mono_ns"],
            f"{endpoint}_signed_offset_ms": selection["signed_offset_ms"],
            f"{endpoint}_absolute_offset_ms": selection["absolute_offset_ms"],
            f"{endpoint}_sampling_uncertainty_ms": selection["sampling_uncertainty_ms"],
        })
    return row


def _run_directory(root: Path, slot: dict[str, Any]) -> Path | None:
    configured = slot.get("run_dir")
    if isinstance(configured, str) and configured:
        candidate = Path(configured)
        if candidate.is_dir():
            return candidate
    run_id = slot.get("run_id")
    if isinstance(run_id, str) and run_id:
        candidate = root / "runs" / run_id
        if candidate.is_dir():
            return candidate
    return None


def _slot_base(experiment_id: Any, slot: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": experiment_id,
        "run_id": slot.get("run_id"),
        "slot_id": slot.get("slot_id"),
        "condition_id": slot.get("condition_id"),
        "block": slot.get("block_index"),
        "repetition": slot.get("repetition"),
        "order": slot.get("order_index"),
        "resource": slot.get("resource"),
        "cpu_threads": slot.get("cpu_threads"),
        "requested_duty_cycle_percent": slot.get("duty_cycle_percent"),
    }


def build_dataset(
    experiment_dir: Path, maximum_offset_ms: float = DEFAULT_MAXIMUM_OFFSET_MS
) -> dict[str, Any]:
    root = experiment_dir.resolve()
    manifest_path = root / MANIFEST_NAME
    manifest = load_object(manifest_path)
    runs = manifest.get("runs")
    if not isinstance(runs, list):
        raise DatasetError("experiment manifest runs must be a list")
    sorted_slots = sorted(
        runs,
        key=lambda slot: (
            slot.get("order_index") if isinstance(slot.get("order_index"), int) else sys.maxsize,
            str(slot.get("slot_id", "")),
        ),
    )
    experiment_id = manifest.get("experiment_id")
    run_rows: list[dict[str, Any]] = []
    phase_rows: list[dict[str, Any]] = []
    timeseries_rows: list[dict[str, Any]] = []
    exclusion_counts: dict[str, int] = {}
    thermal_raw_record_count = 0
    thermal_valid_unique_sample_count = 0
    thermal_outside_or_unassignable_count = 0

    for slot in sorted_slots:
        base = _slot_base(experiment_id, slot)
        run_dir = _run_directory(root, slot)
        summary_path = run_dir / "merged" / "summary.json" if run_dir else None
        thermal_path = run_dir / "raw" / "thermalservice.jsonl" if run_dir else None
        summary: dict[str, Any] = {}
        source_issues: list[str] = []
        if summary_path is not None and summary_path.is_file():
            try:
                summary = load_object(summary_path)
            except DatasetError as error:
                source_issues.append(f"summary_invalid:{error}")
        else:
            source_issues.append("summary_missing")
        if thermal_path is not None:
            samples, thermal_issues, thermal_raw_count = load_thermal_samples(
                thermal_path, slot.get("run_id")
            )
        else:
            samples, thermal_issues, thermal_raw_count = [], ["thermal_file_missing"], 0
        thermal_raw_record_count += thermal_raw_count
        thermal_valid_unique_sample_count += len(samples)
        source_issues.extend(thermal_issues)
        endpoints = {
            endpoint: select_endpoint_sample(
                samples,
                summary.get(timestamp_name),
                allow_after_fallback=allow_after,
                maximum_offset_ms=maximum_offset_ms,
            )
            for endpoint, timestamp_name, allow_after in ENDPOINTS
        }
        timestamps = _valid_timestamps(summary)
        load_samples: list[dict[str, Any]] = []
        cooling_samples: list[dict[str, Any]] = []
        if timestamps is not None:
            for sample in samples:
                classified = classify_phase(sample["mono_ns"], timestamps)
                if classified is None:
                    thermal_outside_or_unassignable_count += 1
                    continue
                phase, phase_start_ns = classified
                if phase == "load":
                    load_samples.append(sample)
                elif phase == "cooling":
                    cooling_samples.append(sample)
                timeseries = dict(base)
                timeseries.update({
                    "achieved_duty_cycle_percent": (
                        summary.get("duty_cycle", {}).get("achieved_duty_cycle_percent")
                    ),
                    "mono_ns": sample["mono_ns"],
                    "run_elapsed_s": (
                        sample["mono_ns"] - timestamps["run_start_mono_ns"]
                    ) / 1e9,
                    "load_relative_s": (
                        sample["mono_ns"] - timestamps["load_start_mono_ns"]
                    ) / 1e9,
                    "phase": phase,
                    "phase_elapsed_s": (sample["mono_ns"] - phase_start_ns) / 1e9,
                    **sample["temperatures_c"],
                    "thermal_status": sample["thermal_status"],
                    "sampling_uncertainty_ns": sample["sampling_uncertainty_ns"],
                    "parse_status": "ok",
                })
                timeseries_rows.append(timeseries)
        else:
            thermal_outside_or_unassignable_count += len(samples)

        per_sensor = [
            sensor_phase_row(
                base, sensor, endpoints, load_samples, cooling_samples,
                summary.get("load_start_mono_ns")
                if isinstance(summary.get("load_start_mono_ns"), int) else None,
            )
            for sensor in SENSORS
        ]
        phase_rows.extend(per_sensor)

        exclusions: list[str] = []
        if slot.get("status") != "completed":
            exclusions.append("run_status_not_completed")
        slot_error = slot.get("error")
        if isinstance(slot_error, str) and slot_error:
            exclusions.append(f"slot_failure:{slot_error.split(':', 1)[0]}")
        validation = slot.get("validation")
        if not isinstance(validation, dict) or validation.get("valid") is not True:
            exclusions.append("validation_not_valid")
        coverage = summary.get("thermal_coverage")
        if not isinstance(coverage, dict) or coverage.get("passes_formal_requirement") is not True:
            exclusions.append("thermal_coverage_not_passed")
        if summary.get("run_envelope_validation") != "pass":
            exclusions.append("run_envelope_not_passed")
        if timestamps is None:
            exclusions.append("phase_timestamps_missing_or_invalid")
        for endpoint, selection in endpoints.items():
            if selection["quality"] != "ok":
                exclusions.append(
                    f"endpoint_{endpoint}_{selection['quality']}:"
                    f"{selection['quality_reason']}"
                )
        checks = validation.get("checks", {}) if isinstance(validation, dict) else {}
        required_config_checks = ("resource", "cpu_threads", "duty_request", "duty_period")
        if any(checks.get(name) is not True for name in required_config_checks):
            exclusions.append("resource_config_metadata_mismatch")
        resource = str(slot.get("resource", "")).upper()
        formal_gpu_valid = summary.get("formal_gpu_valid")
        if resource == "GPU" and formal_gpu_valid is not True:
            exclusions.append("gpu_delegate_not_formally_valid")
        if any(issue.startswith("duplicate_mono_ns:") for issue in thermal_issues):
            exclusions.append("duplicate_thermal_sample_mono_ns")
        exclusions = list(dict.fromkeys(exclusions))
        for reason in exclusions:
            exclusion_counts[reason] = exclusion_counts.get(reason, 0) + 1

        duty = summary.get("duty_cycle", {})
        latency = summary.get("inference_latency", {})
        accuracy = summary.get("accuracy_preflight") or manifest.get("provenance", {}).get(
            "accuracy_preflight", {}
        )
        energy = summary.get("energy_measurement") or manifest.get("provenance", {}).get(
            "energy_measurement", {}
        )
        run_row = dict(base)
        run_row.update({
            "slot_status": slot.get("status"),
            "attempts": slot.get("attempts"),
            "slot_error": slot_error,
            "achieved_duty_cycle_percent": duty.get("achieved_duty_cycle_percent"),
            "requested_duration_s": manifest.get("config", {}).get("duration_s"),
            "actual_load_duration_s": (
                (duty.get("actual_active_duration_ns") + duty.get("actual_idle_duration_ns")) / 1e9
                if isinstance(duty.get("actual_active_duration_ns"), int)
                and isinstance(duty.get("actual_idle_duration_ns"), int) else None
            ),
            "completed_inference_count": duty.get("completed_inference_count"),
            "latency_mean_ms": latency.get("mean_ms"),
            "latency_median_ms": latency.get("median_ms"),
            "latency_p95_ms": latency.get("p95_ms"),
            "validation_status": (
                "valid" if isinstance(validation, dict) and validation.get("valid") is True
                else "invalid"
            ),
            "termination_reason": duty.get("termination_reason"),
            "cooling_status": (
                slot.get("cooling", {}).get("status")
                if isinstance(slot.get("cooling"), dict) else None
            ),
            "accuracy_preflight_status": (
                accuracy.get("status") if isinstance(accuracy, dict) else None
            ),
            "energy_measurement_status": (
                energy.get("status") if isinstance(energy, dict) else None
            ),
            "formal_gpu_valid": formal_gpu_valid,
            "model_eligible": not exclusions,
            "exclusion_reasons": json.dumps(exclusions, ensure_ascii=False, separators=(",", ":")),
            "thermal_raw_record_count": thermal_raw_count,
            "thermal_valid_sample_count": len(samples),
            "thermal_source_issues": json.dumps(
                source_issues, ensure_ascii=False, separators=(",", ":")
            ),
        })
        for sensor_row in per_sensor:
            prefix = sensor_row["sensor"].lower()
            for name in (
                "run_start_temperature_c", "load_start_temperature_c",
                "load_end_temperature_c", "cooling_end_temperature_c",
                "baseline_change_c", "load_change_c", "cooling_change_c",
                "residual_vs_load_start_c",
            ):
                run_row[f"{prefix}_{name}"] = sensor_row[name]
        run_rows.append(run_row)

    timeseries_rows.sort(key=lambda row: (
        row["order"] if isinstance(row["order"], int) else sys.maxsize,
        row["mono_ns"],
    ))
    phase_rows.sort(key=lambda row: (
        row["order"] if isinstance(row["order"], int) else sys.maxsize,
        SENSORS.index(row["sensor"]),
    ))
    return {
        "root": root,
        "source_manifest_path": manifest_path,
        "source_manifest_sha256": sha256_file(manifest_path),
        "run_summary": run_rows,
        "phase_temperature_summary": phase_rows,
        "thermal_timeseries": timeseries_rows,
        "source_run_count": len(run_rows),
        "included_run_count": sum(row["model_eligible"] for row in run_rows),
        "excluded_run_count": sum(not row["model_eligible"] for row in run_rows),
        "exclusion_reason_counts": dict(sorted(exclusion_counts.items())),
        "thermal_sample_inventory": {
            "raw_record_count": thermal_raw_record_count,
            "valid_unique_sample_count": thermal_valid_unique_sample_count,
            "phase_assigned_valid_sample_count": len(timeseries_rows),
            "outside_or_unassignable_valid_sample_count": (
                thermal_outside_or_unassignable_count
            ),
        },
        "maximum_offset_ms": maximum_offset_ms,
    }


def _csv_text(rows: list[dict[str, Any]], fieldnames: list[str]) -> str:
    expected = set(fieldnames)
    if any(set(row) != expected for row in rows):
        raise DatasetError("CSV rows have inconsistent schemas")
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def _write_text(path: Path, text: str) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        stream.write(text)
        stream.flush()
        os.fsync(stream.fileno())


def _replace_export_directory(staging: Path, destination: Path) -> None:
    backup = destination.parent / f".{destination.name}.backup-{uuid.uuid4()}"
    moved_existing = False
    try:
        if destination.exists():
            os.replace(destination, backup)
            moved_existing = True
        os.replace(staging, destination)
    except Exception:
        if moved_existing and backup.exists() and not destination.exists():
            os.replace(backup, destination)
        raise
    finally:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
    if backup.exists():
        shutil.rmtree(backup, ignore_errors=True)


def export_experiment(
    experiment_dir: Path, maximum_offset_ms: float = DEFAULT_MAXIMUM_OFFSET_MS
) -> dict[str, Any]:
    dataset = build_dataset(experiment_dir, maximum_offset_ms)
    root: Path = dataset["root"]
    staging = root / f".{EXPORT_DIRECTORY}.tmp-{uuid.uuid4()}"
    destination = root / EXPORT_DIRECTORY
    staging.mkdir(parents=False, exist_ok=False)
    try:
        csv_files = {
            "run_summary.csv": _csv_text(dataset["run_summary"], RUN_SUMMARY_COLUMNS),
            "phase_temperature_summary.csv": _csv_text(
                dataset["phase_temperature_summary"], PHASE_TEMPERATURE_COLUMNS
            ),
            "thermal_timeseries.csv": _csv_text(
                dataset["thermal_timeseries"], THERMAL_TIMESERIES_COLUMNS
            ),
        }
        for filename, content in csv_files.items():
            _write_text(staging / filename, content)
        outputs = {
            filename: {
                "sha256": sha256_file(staging / filename),
                "row_count": len(dataset[key]),
            }
            for filename, key in (
                ("run_summary.csv", "run_summary"),
                ("phase_temperature_summary.csv", "phase_temperature_summary"),
                ("thermal_timeseries.csv", "thermal_timeseries"),
            )
        }
        dataset_manifest = {
            "dataset_schema": DATASET_SCHEMA,
            "dataset_version": DATASET_VERSION,
            "generated_utc": utc_now(),
            "source_experiment_manifest": MANIFEST_NAME,
            "source_experiment_manifest_sha256": dataset["source_manifest_sha256"],
            "source_run_count": dataset["source_run_count"],
            "included_run_count": dataset["included_run_count"],
            "excluded_run_count": dataset["excluded_run_count"],
            "exclusion_reason_counts": dataset["exclusion_reason_counts"],
            "thermal_sample_inventory": dataset["thermal_sample_inventory"],
            "row_counts": {
                key: len(dataset[key]) for key in (
                    "run_summary", "phase_temperature_summary", "thermal_timeseries"
                )
            },
            "clock_domain": {
                "name": "android_elapsed_realtime_mono_ns",
                "source": "thermalservice mono_ns and merged summary phase timestamps",
                "utc_or_host_monotonic_used_for_alignment": False,
            },
            "phase_intervals": {
                "baseline": "[run_start_mono_ns, load_start_mono_ns)",
                "load": "[load_start_mono_ns, load_end_mono_ns)",
                "cooling": "[load_end_mono_ns, run_stop_mono_ns)",
            },
            "endpoint_selection": {
                "default": "latest valid sample at or before target",
                "run_start_fallback": "earliest valid sample after target only when no prior sample exists",
                "future_fallback_for_other_endpoints": False,
                "maximum_absolute_offset_ms": maximum_offset_ms,
                "sampling_uncertainty": "per-sample half-width from ADB uptime bracketing",
            },
            "temperature_unit": "degrees_Celsius",
            "limitations": {
                "accuracy": "accuracy_preflight provenance only; no statistical claim",
                "energy": "current units remain unverified; no J or mWh calculation",
                "statistics": "a pilot run does not establish statistical significance",
            },
            "outputs": outputs,
        }
        _write_text(
            staging / "dataset_manifest.json",
            json.dumps(dataset_manifest, ensure_ascii=False, indent=2) + "\n",
        )
        for filename, metadata in outputs.items():
            if sha256_file(staging / filename) != metadata["sha256"]:
                raise DatasetError(f"staged output hash mismatch: {filename}")
        _replace_export_directory(staging, destination)
        return dataset_manifest
    except Exception:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
        raise


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment-dir", required=True, type=Path)
    parser.add_argument(
        "--maximum-offset-ms", type=float, default=DEFAULT_MAXIMUM_OFFSET_MS
    )
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not math.isfinite(args.maximum_offset_ms) or args.maximum_offset_ms < 0:
        raise DatasetError("--maximum-offset-ms must be finite and non-negative")
    result = export_experiment(args.experiment_dir, args.maximum_offset_ms)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except DatasetError as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1)
