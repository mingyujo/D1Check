#!/usr/bin/env python3
"""Run repeatable D1Check CPU/GPU duration experiments without extra packages."""

from __future__ import annotations

import argparse
from collections import deque
from dataclasses import asdict, dataclass
import datetime as dt
import functools
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import queue
import random
import re
import subprocess
import struct
import sys
import threading
import time
from typing import Any, Callable, Iterable
import uuid


VERSION = "0.8"
BLOCK_DESIGN_NAME = "randomized_complete_block"
BLOCK_DESIGN_VERSION = 1
MATCHED_MATRIX_WARNING_CODE = "matched_global_reference_long_matrix"
DEFAULT_CPU_THREADS = 4
DEFAULT_DUTY_CYCLE_PERCENT = 100
D1_PACKAGE = "com.example.d1check"
D1_ACTIVITY = f"{D1_PACKAGE}/.MainActivity"
D1_SERVICE = f"{D1_PACKAGE}/.TelemetryForegroundService"
D1_STOP_ACTION = f"{D1_PACKAGE}.action.STOP"
RUNNER_PACKAGE = "com.example.d1check.benchmarkrunner"
RUNNER_ACTIVITY = f"{RUNNER_PACKAGE}/.MainActivity"
REMOTE_RUNNER_DIRECTORY = f"/sdcard/Android/data/{RUNNER_PACKAGE}/files/runs"
# npu-runner (S26 NPU, LiteRT Next CompiledModel) is a separate app. CPU/GPU slots never touch it;
# NPU slots never touch benchmark-runner. Spec: s26/npu/runner/NPU_RUNNER_SPEC.md §5.
NPU_RUNNER_PACKAGE = "com.example.d1check.npurunner"
NPU_RUNNER_ACTIVITY = f"{NPU_RUNNER_PACKAGE}/.NpuRunnerActivity"
NPU_REMOTE_RUNNER_DIRECTORY = f"/sdcard/Android/data/{NPU_RUNNER_PACKAGE}/files/runs"
# litert (lowercase) carries the dispatch/ENN evidence d1_logger_v4 needs for formal_npu_valid.
NPU_LOGGER_EXTRA_LOGCAT_TAGS = ("litert:I",)
RESOURCE_CHOICES = ("CPU", "GPU", "NPU")
DEFAULT_NPU_MODEL_ASSET = "models/mobilenet_v1_1.0_224_Samsung_E9965.tflite"
DEFAULT_NPU_REFERENCE_ASSET = "models/mobilenet_v1_1.0_224.tflite"
DEFAULT_NPU_INPUT_SPEC = "lcg-unit"
NPU_INPUT_SPECS = ("lcg-unit", "lcg-rgb-127-128", "lcg-rgb-127.5-127.5")
NPU_QUALITY_GATE_VERSION = "npu-quality-gate-v1"
NPU_QUALITY_GATE_N = 32
NPU_QUALITY_COSINE_MIN = 0.99
NPU_QUALITY_TIMEOUT_SECONDS = 180
NPU_QUALITY_POLL_SECONDS = 3.0
NPU_LITERT_RUNTIME_VERSION = "2.2.0"
NPU_DISPATCH_LIB_SHA256 = "f08656a642c46e7b06b64fbe1e0800de9e73b0b69c1641b87995562b4a16840f"
ACCURACY_SCHEMA_VERSION = 2
LEGACY_ACCURACY_SCHEMA_VERSION = 1
ACCURACY_COMPARATOR_VERSION = "output-equivalence-v3"
ACCURACY_INPUT_SET_VERSION = "lcg-float32-unit-v1"
ACCURACY_MODEL_ID = "mobilenet_v1_1.0_224_float"
ACCURACY_MODEL_SHA256 = "D95B3C5EA86750CEF882FA867CA357DFE4D265D0B80B67E83277A0BDA310CFBB"
ACCURACY_LITERT_VERSION = "1.4.2"
DEFAULT_GPU_PROFILE = "gpu-compat-default-v1"
GPU_PROFILE_IDS = (DEFAULT_GPU_PROFILE, "gpu-fp32-strict-v1")
REPRESENTATIVE_POLICY_ID = "representative-equivalence-v2"
TASK_ACCURACY_POLICY_ID = "task-accuracy-no-regression-v1"
ACCURACY_VALIDATION_SCOPES = (
    "thermal-only-pilot", "backend-performance-formal", "accuracy-preserving-formal",
)
ACCURACY_INPUT_SHAPE = [1, 224, 224, 3]
ACCURACY_OUTPUT_SHAPE = [1, 1001]
ACCURACY_INPUT_DTYPE = "FLOAT32"
ACCURACY_OUTPUT_DTYPE = "FLOAT32"
DEFAULT_ACCURACY_INPUT_COUNT = 32
DEFAULT_ACCURACY_SEED = 0x12345678
DEFAULT_ACCURACY_ATOL = 1e-4
DEFAULT_ACCURACY_RTOL = 1e-3
DEFAULT_ACCURACY_RELATIVE_EPSILON = 1e-6
MANIFEST_NAME = "experiment_manifest.json"
RUNNER_SCHEMA_VERSION = 2
BASELINE_SECONDS = 60
REMOTE_FALLBACK_GRACE_SECONDS = 30
REMOTE_POLL_INTERVAL_SECONDS = 15
REMOTE_TAIL_LINES = 128
THERMAL_STATUS_RE = re.compile(r"Thermal Status:\s*(-?\d+)", re.IGNORECASE)
HAL_TEMPERATURE_RE = re.compile(
    r"Temperature\{(?P<body>[^}]*)\}", re.IGNORECASE
)
HAL_FIELD_RE = re.compile(r"(?:^|,)\s*(m[A-Za-z]+)\s*=\s*([^,}]*)")
THERMAL_SENSOR_NAMES = ("AP", "BAT", "PA", "SKIN")
THERMAL_SENSOR_ALIASES = {
    "AP": "AP",
    "BAT": "BAT",
    "PA": "PA",
    "PATHM": "PA",
    "PA1THM": "PA",
    "SKIN": "SKIN",
}
RUNNER_FAILURE_EVENTS = {
    "buffer_limit",
    "pilot_safety_rejected",
    "run_context_mismatch",
    "run_error",
}


class OrchestratorError(RuntimeError):
    pass


def export_thermal_dataset(experiment_dir: Path) -> dict[str, Any]:
    module_path = Path(__file__).with_name("d1_thermal_dataset.py")
    spec = importlib.util.spec_from_file_location("d1_thermal_dataset", module_path)
    if spec is None or spec.loader is None:
        raise OrchestratorError(f"cannot load thermal dataset exporter: {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.export_experiment(experiment_dir)


class WaitTimeout(OrchestratorError):
    pass


class RemoteRunnerAdbError(OrchestratorError):
    pass


class RemoteRunnerAmbiguityError(OrchestratorError):
    pass


class RemoteRunnerValidationError(OrchestratorError):
    pass


class EmergencyAbort(OrchestratorError):
    def __init__(self, source: str, stage: str, reasons: Iterable[str], sample: dict[str, Any]):
        self.source = source
        self.stage = stage
        self.reasons = tuple(reasons)
        self.sample = sample
        super().__init__(
            f"emergency safety abort during {stage} from {source}: "
            + ",".join(self.reasons)
        )


class CoolingTimeout(WaitTimeout):
    pass


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def extract_json(line: str) -> dict[str, Any] | None:
    start = line.find("{")
    if start < 0:
        return None
    try:
        value = json.loads(line[start:])
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4()}.tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def atomic_write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4()}.tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as stream:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_sha256(value: dict[str, Any]) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@functools.lru_cache(maxsize=8)
def _cached_deterministic_accuracy_input_hashes(
    seed: int, input_count: int, element_count: int
) -> tuple[tuple[str, ...], str]:
    state = seed & 0xFFFFFFFF
    hashes: list[str] = []
    complete = hashlib.sha256()
    for _ in range(input_count):
        digest = hashlib.sha256()
        for _ in range(element_count):
            state = (state * 1664525 + 1013904223) & 0xFFFFFFFF
            encoded = struct.pack("<f", ((state >> 8) & 0xFFFFFF) / 16777215.0)
            digest.update(encoded)
            complete.update(encoded)
        hashes.append(digest.hexdigest())
    return tuple(hashes), complete.hexdigest()


def deterministic_accuracy_input_hashes(
    seed: int, input_count: int, element_count: int
) -> tuple[list[str], str]:
    hashes, complete = _cached_deterministic_accuracy_input_hashes(
        seed, input_count, element_count
    )
    return list(hashes), complete


def gpu_profile(profile_id: str) -> dict[str, Any]:
    if profile_id not in GPU_PROFILE_IDS:
        raise OrchestratorError(f"unsupported GPU delegate profile: {profile_id}")
    precision_loss_allowed = profile_id == DEFAULT_GPU_PROFILE
    canonical = "|".join((
        f"profile_id={profile_id}",
        f"precision_loss_allowed={str(precision_loss_allowed).lower()}",
        "quantized_models_allowed=true",
        "inference_preference=FAST_SINGLE_ANSWER",
        "force_backend=UNSET",
    ))
    return {
        "profile_id": profile_id,
        "configuration_sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        "precision_loss_allowed": precision_loss_allowed,
        "quantized_models_allowed": True,
        "inference_preference": "FAST_SINGLE_ANSWER",
        "force_backend": "UNSET",
        "actual_fp16_execution": "unknown_not_exposed_by_litert_api",
    }


def representative_acceptance_policy() -> dict[str, Any]:
    return {
        "policy_id": REPRESENTATIVE_POLICY_ID,
        "minimum_sample_count": 40,
        "maximum_top1_mismatch_count": 0,
        "minimum_top5_overlap_per_input": 4,
        "top5_boundary_tie_policy": "exclude_exact_5th_6th_ties_from_overlap_minimum",
        "maximum_total_variation_distance": 0.02,
        "minimum_cosine_similarity": 0.999,
        "tie_break_rule": "score_descending_then_index_ascending",
        "threshold_origin": "pre_registered_methodology_default_not_fitted_to_A24_observation",
    }


def task_accuracy_acceptance_policy() -> dict[str, Any]:
    return {
        "policy_id": TASK_ACCURACY_POLICY_ID,
        "minimum_labeled_sample_count": 40,
        "maximum_top1_accuracy_drop": 0.0,
        "maximum_top5_accuracy_drop": 0.0,
        "dataset_scope_required": "labeled_representative_subset",
        "threshold_origin": "no_regression_policy_not_full_ImageNet_accuracy_claim",
    }


def _representative_module() -> Any:
    module_path = Path(__file__).with_name("d1_representative_tensors.py")
    spec = importlib.util.spec_from_file_location("d1_representative_tensors_runtime", module_path)
    if spec is None or spec.loader is None:
        raise OrchestratorError(f"cannot load representative tensor module: {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_representative_tensor_set(path: Path) -> dict[str, Any]:
    try:
        return _representative_module().validate_tensor_set(path)
    except Exception as error:
        raise OrchestratorError(f"invalid representative tensor-set: {error}") from error


def parse_adb_devices(text: str) -> dict[str, str]:
    devices: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("List of devices") or line.startswith("*"):
            continue
        fields = line.split()
        if len(fields) >= 2:
            devices[fields[0]] = fields[1]
    return devices


def select_device(devices: dict[str, str], requested_serial: str | None) -> str:
    if requested_serial:
        state = devices.get(requested_serial)
        if state != "device":
            raise OrchestratorError(
                f"requested ADB device is not ready: serial={requested_serial!r}, state={state!r}"
            )
        return requested_serial
    if len(devices) != 1:
        raise OrchestratorError(
            "exactly one ADB target is required when --serial is omitted; "
            f"found={devices}"
        )
    serial, state = next(iter(devices.items()))
    if state != "device":
        raise OrchestratorError(f"ADB target is not ready: serial={serial!r}, state={state!r}")
    return serial


@dataclass(frozen=True)
class SafetySnapshot:
    battery_percent: float
    battery_status: int
    battery_temperature_c: float
    ac_powered: bool
    usb_powered: bool
    wireless_powered: bool
    android_thermal_status: int

    @property
    def unplugged(self) -> bool:
        return not (self.ac_powered or self.usb_powered or self.wireless_powered)


@dataclass(frozen=True)
class SafetyEvaluation:
    mode: str
    pilot_safety_pass: bool
    formal_energy_eligible: bool
    mode_safety_pass: bool
    reasons: tuple[str, ...]

    def to_dict(self, snapshot: SafetySnapshot) -> dict[str, Any]:
        return {
            "checked_utc": utc_now(),
            "mode": self.mode,
            "snapshot": asdict(snapshot) | {"unplugged": snapshot.unplugged},
            "limits": {
                "pilot_battery_percent": [30, 100],
                "formal_battery_percent": [30, 90],
                "required_battery_status": 3,
                "max_battery_temperature_c": 35.0,
                "max_android_thermal_status": 1,
                "require_unplugged": True,
            },
            "pilot_safety_pass": self.pilot_safety_pass,
            "formal_energy_eligible": self.formal_energy_eligible,
            "mode_safety_pass": self.mode_safety_pass,
            "reasons": list(self.reasons),
        }


def _parse_bool(value: str, name: str) -> bool:
    lowered = value.strip().lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    raise ValueError(f"{name}: expected true/false, got {value!r}")


def parse_safety_snapshot(battery_text: str, thermal_text: str) -> SafetySnapshot:
    values: dict[str, str] = {}
    for line in battery_text.splitlines():
        match = re.match(r"^\s*([^:]+):\s*(.*?)\s*$", line)
        if match:
            values[match.group(1).strip().lower()] = match.group(2).strip()

    def required(name: str) -> str:
        value = values.get(name.lower())
        if value is None or value == "":
            raise ValueError(f"dumpsys battery missing {name!r}")
        return value

    try:
        level = int(required("level"))
        scale = int(required("scale"))
        status = int(required("status"))
        temperature_c = int(required("temperature")) / 10.0
    except ValueError as error:
        raise ValueError(f"malformed dumpsys battery: {error}") from error
    if scale <= 0:
        raise ValueError(f"malformed dumpsys battery: scale must be positive, got {scale}")
    thermal_match = THERMAL_STATUS_RE.search(thermal_text)
    if thermal_match is None:
        raise ValueError("dumpsys thermalservice missing Thermal Status")
    return SafetySnapshot(
        battery_percent=level * 100.0 / scale,
        battery_status=status,
        battery_temperature_c=temperature_c,
        ac_powered=_parse_bool(required("AC powered"), "AC powered"),
        usb_powered=_parse_bool(required("USB powered"), "USB powered"),
        wireless_powered=_parse_bool(required("Wireless powered"), "Wireless powered"),
        android_thermal_status=int(thermal_match.group(1)),
    )


def evaluate_safety(snapshot: SafetySnapshot, mode: str) -> SafetyEvaluation:
    reasons: list[str] = []
    if not snapshot.unplugged:
        reasons.append("device_plugged")
    if snapshot.battery_status != 3:
        reasons.append("not_discharging")
    if not 30.0 <= snapshot.battery_percent <= 100.0:
        reasons.append("pilot_battery_level")
    if not math.isfinite(snapshot.battery_temperature_c) or not (
        0.0 <= snapshot.battery_temperature_c <= 35.0
    ):
        reasons.append("battery_temperature")
    if not 0 <= snapshot.android_thermal_status <= 1:
        reasons.append("android_thermal_status")
    pilot_pass = not reasons
    formal_energy_eligible = pilot_pass and 30.0 <= snapshot.battery_percent <= 90.0
    if mode == "formal" and pilot_pass and not formal_energy_eligible:
        reasons.append("formal_battery_level")
    mode_pass = pilot_pass and (mode == "pilot" or formal_energy_eligible)
    return SafetyEvaluation(mode, pilot_pass, formal_energy_eligible, mode_pass, tuple(reasons))


def parse_hal_temperature_vector(text: str) -> dict[str, float]:
    """Parse exactly one AP/BAT/PA/SKIN vector from the HAL temperature section."""
    section_match = re.search(
        r"Current temperatures from HAL:?\s*(.*?)(?:\n\s*(?:Current cooling devices|"
        r"Temperature static|Temperature headroom|HAL Ready|$))",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if section_match is None:
        raise ValueError("thermalservice missing Current temperatures from HAL section")
    values: dict[str, float] = {}
    recognized_records = 0
    for record in HAL_TEMPERATURE_RE.finditer(section_match.group(1)):
        fields = {
            key.lower(): value.strip()
            for key, value in HAL_FIELD_RE.findall(record.group("body"))
        }
        raw_name = fields.get("mname", "").upper()
        canonical = THERMAL_SENSOR_ALIASES.get(raw_name)
        if canonical is None:
            continue
        recognized_records += 1
        if canonical in values:
            raise ValueError(
                f"duplicate HAL thermal sensor {canonical}: alias={raw_name!r}"
            )
        raw_value = fields.get("mvalue")
        if raw_value is None or raw_value == "":
            raise ValueError(f"HAL thermal sensor {raw_name!r} missing mValue")
        try:
            value = float(raw_value)
        except ValueError as error:
            raise ValueError(
                f"HAL thermal sensor {raw_name!r} malformed mValue={raw_value!r}"
            ) from error
        if not math.isfinite(value):
            raise ValueError(
                f"HAL thermal sensor {raw_name!r} non-finite mValue={raw_value!r}"
            )
        values[canonical] = value
    missing = [name for name in THERMAL_SENSOR_NAMES if name not in values]
    if missing:
        raise ValueError(
            "HAL thermal sensor set incomplete: "
            f"missing={missing}, recognized_records={recognized_records}"
        )
    return {name: values[name] for name in THERMAL_SENSOR_NAMES}


def _linear_slope_per_minute(points: list[tuple[float, float]]) -> float:
    if len(points) < 2:
        return math.inf
    origin = points[0][0]
    xs = [point[0] - origin for point in points]
    ys = [point[1] for point in points]
    mean_x = sum(xs) / len(xs)
    mean_y = sum(ys) / len(ys)
    denominator = sum((value - mean_x) ** 2 for value in xs)
    if denominator <= 0:
        return math.inf
    slope_per_second = sum(
        (x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)
    ) / denominator
    return slope_per_second * 60.0


def evaluate_thermal_stability(
    samples: list[dict[str, Any]],
    window_seconds: float,
    max_range_c: float,
    max_abs_slope_c_per_minute: float,
) -> dict[str, Any]:
    if not samples:
        return {
            "stable": False,
            "reason": "no_samples",
            "window_coverage_seconds": 0.0,
            "sensor_evidence": {},
        }
    latest = float(samples[-1]["host_monotonic_s"])
    cutoff = latest - window_seconds
    first_inside = next(
        (
            index for index, sample in enumerate(samples)
            if float(sample["host_monotonic_s"]) >= cutoff
        ),
        len(samples) - 1,
    )
    # Include one bracketing sample before the cutoff. Real ADB sampling has jitter;
    # without this point a nominal 5 s cadence can retain only ~25 s forever.
    window = samples[max(0, first_inside - 1):]
    coverage = float(window[-1]["host_monotonic_s"]) - float(
        window[0]["host_monotonic_s"]
    )
    sensor_evidence: dict[str, Any] = {}
    for sensor in THERMAL_SENSOR_NAMES:
        points = [
            (float(sample["host_monotonic_s"]), float(sample["temperatures_c"][sensor]))
            for sample in window
        ]
        values = [value for _, value in points]
        value_range = max(values) - min(values)
        slope = _linear_slope_per_minute(points)
        sensor_evidence[sensor] = {
            "min_c": min(values),
            "max_c": max(values),
            "range_c": value_range,
            "slope_c_per_minute": slope,
            "range_pass": value_range <= max_range_c,
            "slope_pass": abs(slope) <= max_abs_slope_c_per_minute,
        }
    coverage_pass = coverage >= window_seconds
    stable = coverage_pass and all(
        evidence["range_pass"] and evidence["slope_pass"]
        for evidence in sensor_evidence.values()
    )
    return {
        "stable": stable,
        "reason": "stable" if stable else "criteria_not_met",
        "window_coverage_seconds": coverage,
        "window_sample_count": len(window),
        "coverage_pass": coverage_pass,
        "limits": {
            "window_seconds": window_seconds,
            "max_range_c": max_range_c,
            "max_abs_slope_c_per_minute": max_abs_slope_c_per_minute,
        },
        "sensor_evidence": sensor_evidence,
    }


def evaluate_reference_match(
    actual: dict[str, float], reference: dict[str, float], tolerance_c: float
) -> dict[str, Any]:
    missing = [name for name in THERMAL_SENSOR_NAMES if name not in reference]
    if missing:
        raise ValueError(f"matched-start reference missing sensors: {missing}")
    deltas = {name: actual[name] - float(reference[name]) for name in THERMAL_SENSOR_NAMES}
    passes = {name: abs(delta) <= tolerance_c for name, delta in deltas.items()}
    return {
        "matched": all(passes.values()),
        "tolerance_c": tolerance_c,
        "reference_c": {name: float(reference[name]) for name in THERMAL_SENSOR_NAMES},
        "actual_c": dict(actual),
        "delta_c": deltas,
        "sensor_pass": passes,
        "claim": "tolerance_based_control_not_statistical_equivalence",
    }


def validated_reference_vector(manifest: dict[str, Any]) -> dict[str, float] | None:
    record = manifest.get("thermal_conditioning_reference")
    if record is None:
        return None
    if not isinstance(record, dict) or not isinstance(record.get("temperatures_c"), dict):
        raise OrchestratorError("thermal_conditioning_reference is malformed")
    temperatures = record["temperatures_c"]
    if set(temperatures) != set(THERMAL_SENSOR_NAMES):
        raise OrchestratorError(
            "thermal_conditioning_reference must contain exactly AP/BAT/PA/SKIN"
        )
    vector: dict[str, float] = {}
    for sensor in THERMAL_SENSOR_NAMES:
        value = temperatures[sensor]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise OrchestratorError(
                f"thermal_conditioning_reference {sensor} is not numeric"
            )
        parsed = float(value)
        if not math.isfinite(parsed):
            raise OrchestratorError(
                f"thermal_conditioning_reference {sensor} is not finite"
            )
        vector[sensor] = parsed
    return vector


def emergency_reasons(
    sample: dict[str, Any],
    max_battery_temperature_c: float,
    max_android_thermal_status: int,
    *,
    require_all: bool,
) -> list[str]:
    reasons: list[str] = []
    required = ("plugged", "battery_status", "battery_temperature_c", "thermal_status")
    if require_all:
        missing = [name for name in required if sample.get(name) is None]
        if missing:
            return ["monitor_sample_missing:" + ",".join(missing)]
    plugged = sample.get("plugged")
    if plugged is not None:
        lowered = str(plugged).strip().lower()
        try:
            numeric_plugged = float(plugged)
            if numeric_plugged < 0:
                reasons.append("plugged_state_malformed")
                is_plugged = False
            else:
                is_plugged = numeric_plugged > 0
        except (TypeError, ValueError):
            if lowered in {"true", "yes"}:
                is_plugged = True
            elif lowered in {"false", "no"}:
                is_plugged = False
            else:
                reasons.append("plugged_state_malformed")
                is_plugged = False
        if is_plugged:
            reasons.append("device_plugged")
    battery_status = sample.get("battery_status")
    if battery_status is not None:
        try:
            if int(battery_status) != 3:
                reasons.append("not_discharging")
        except (TypeError, ValueError):
            reasons.append("battery_status_malformed")
    battery_temperature = sample.get("battery_temperature_c")
    if battery_temperature is not None:
        try:
            value = float(battery_temperature)
            if not math.isfinite(value) or value > max_battery_temperature_c:
                reasons.append("battery_temperature_emergency")
        except (TypeError, ValueError):
            reasons.append("battery_temperature_malformed")
    thermal_status = sample.get("thermal_status")
    if thermal_status is not None:
        try:
            parsed_status = int(thermal_status)
            if parsed_status < 0:
                reasons.append("android_thermal_status_malformed")
            elif parsed_status > max_android_thermal_status:
                reasons.append("android_thermal_status_emergency")
        except (TypeError, ValueError):
            reasons.append("android_thermal_status_malformed")
    return reasons


class RuntimeSafetyMonitor:
    def __init__(
        self,
        max_battery_temperature_c: float,
        max_android_thermal_status: int,
        *,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self.max_battery_temperature_c = max_battery_temperature_c
        self.max_android_thermal_status = max_android_thermal_status
        self.monotonic = monotonic
        self.stage = "load"
        self.observations: list[dict[str, Any]] = []

    def _check(self, source: str, sample: dict[str, Any], require_all: bool) -> None:
        record = {
            "source": source,
            "stage": self.stage,
            "host_monotonic_s": self.monotonic(),
            "sample": sample,
        }
        self.observations.append(record)
        reasons = emergency_reasons(
            sample,
            self.max_battery_temperature_c,
            self.max_android_thermal_status,
            require_all=require_all,
        )
        record["reasons"] = reasons
        if reasons:
            raise EmergencyAbort(source, self.stage, reasons, sample)

    def observe_event(self, event: dict[str, Any]) -> None:
        if event.get("source") != "d1check" or event.get("event") != "sample":
            return
        self._check(
            "logcat_telemetry",
            {
                "android_mono_ns": event.get("mono_ns"),
                "plugged": event.get("plugged"),
                "battery_status": event.get("battery_status"),
                "battery_temperature_c": event.get("battery_temp_C"),
                "thermal_status": event.get("thermal_status"),
            },
            False,
        )

    def check_snapshot(self, snapshot: SafetySnapshot) -> None:
        self._check(
            "sparse_dumpsys",
            {
                "android_mono_ns": None,
                "plugged": not snapshot.unplugged,
                "battery_status": snapshot.battery_status,
                "battery_temperature_c": snapshot.battery_temperature_c,
                "thermal_status": snapshot.android_thermal_status,
            },
            True,
        )


def normalize_axis_values(
    single_value: int | None,
    multiple_values: Iterable[int] | None,
    default_value: int,
    single_option: str,
    multiple_option: str,
) -> list[int]:
    if single_value is not None and multiple_values is not None:
        raise OrchestratorError(
            f"{single_option} and {multiple_option} cannot be used together"
        )
    values = list(multiple_values) if multiple_values is not None else [
        single_value if single_value is not None else default_value
    ]
    if len(set(values)) != len(values):
        raise OrchestratorError(f"{multiple_option} contains duplicate values: {values}")
    return values


def normalized_axes(args: argparse.Namespace) -> tuple[list[int], list[int]]:
    cpu_threads = normalize_axis_values(
        args.cpu_threads,
        args.cpu_thread_levels,
        DEFAULT_CPU_THREADS,
        "--cpu-threads",
        "--cpu-thread-levels",
    )
    duty_cycles = normalize_axis_values(
        args.duty_cycle_percent,
        args.duty_cycles,
        DEFAULT_DUTY_CYCLE_PERCENT,
        "--duty-cycle-percent",
        "--duty-cycles",
    )
    return cpu_threads, duty_cycles


def build_conditions(
    resources: Iterable[str],
    cpu_thread_levels: Iterable[int],
    duty_cycles: Iterable[int],
) -> list[dict[str, Any]]:
    normalized = [value.upper() for value in resources]
    if not normalized or any(value not in RESOURCE_CHOICES for value in normalized):
        raise ValueError("resources must contain CPU, GPU and/or NPU")
    if len(set(normalized)) != len(normalized):
        raise ValueError("resources must not contain duplicates")
    threads = list(cpu_thread_levels)
    duties = list(duty_cycles)
    conditions: list[dict[str, Any]] = []
    for resource in normalized:
        if resource == "CPU":
            conditions.extend(
                {
                    "condition_id": f"cpu-t{threads_value:02d}-d{duty:03d}",
                    "resource": "CPU",
                    "cpu_threads": threads_value,
                    "duty_cycle_percent": duty,
                }
                for threads_value in threads
                for duty in duties
            )
        elif resource == "NPU":
            conditions.extend(
                {
                    "condition_id": f"npu-d{duty:03d}",
                    "resource": "NPU",
                    "cpu_threads": None,
                    "duty_cycle_percent": duty,
                }
                for duty in duties
            )
        else:
            conditions.extend(
                {
                    "condition_id": f"gpu-d{duty:03d}",
                    "resource": "GPU",
                    "cpu_threads": None,
                    "duty_cycle_percent": duty,
                }
                for duty in duties
            )
    return conditions


def build_plan(
    resources: Iterable[str],
    repeat: int,
    seed: int | None,
    cpu_thread_levels: Iterable[int] = (DEFAULT_CPU_THREADS,),
    duty_cycles: Iterable[int] = (DEFAULT_DUTY_CYCLE_PERCENT,),
) -> list[dict[str, Any]]:
    if repeat < 1:
        raise ValueError("repeat must be at least 1")
    conditions = build_conditions(resources, cpu_thread_levels, duty_cycles)
    randomizer = random.Random(seed) if seed is not None else None
    entries: list[dict[str, Any]] = []
    for repetition in range(1, repeat + 1):
        block = [dict(condition) for condition in conditions]
        if randomizer is not None:
            randomizer.shuffle(block)
        for condition in block:
            condition.update(
                {
                    "slot_id": f"{condition['condition_id']}-r{repetition:03d}",
                    "block_index": repetition,
                    "repetition": repetition,
                    "order_index": len(entries) + 1,
                    "status": "pending",
                    "attempts": 0,
                    "failures": [],
                    "steps": [],
                }
            )
            entries.append(condition)
    return entries


def runnable_slots(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    """Resume checkpoint rule: a completed slot is immutable and never scheduled again."""
    return [slot for slot in manifest["runs"] if slot.get("status") != "completed"]


def plan_summary(plan: list[dict[str, Any]], repeat: int) -> dict[str, Any]:
    return {
        "design": {"name": BLOCK_DESIGN_NAME, "version": BLOCK_DESIGN_VERSION},
        "slot_count": len(plan),
        "block_count": repeat,
        "condition_count": len(plan) // repeat if repeat else 0,
        "slots_per_block": [
            sum(slot.get("block_index") == block for slot in plan)
            for block in range(1, repeat + 1)
        ],
    }


def matrix_methodology_warnings(
    start_policy: str, condition_count: int
) -> list[dict[str, Any]]:
    if start_policy != "matched" or condition_count <= 2:
        return []
    return [{
        "code": MATCHED_MATRIX_WARNING_CODE,
        "scope": "experiment_plan",
        "condition_count": condition_count,
        "message": (
            "Returning a long-running matrix to one global thermal reference may be "
            "unachievable because of ambient-temperature drift and delayed heat transfer."
        ),
        "recommendation": (
            "Use start-policy=stable for formal thermal-model collection and include "
            "the measured load_start temperatures as model state variables or covariates."
        ),
        "blocking": False,
    }]


def sync_matrix_methodology_warnings(
    record: dict[str, Any], start_policy: str, condition_count: int
) -> bool:
    existing = record.get("methodology_warnings", [])
    if not isinstance(existing, list):
        raise OrchestratorError("manifest methodology_warnings must be a list")
    preserved = [
        warning for warning in existing
        if not (
            isinstance(warning, dict)
            and warning.get("code") == MATCHED_MATRIX_WARNING_CODE
        )
    ]
    updated = preserved + matrix_methodology_warnings(start_policy, condition_count)
    if existing == updated:
        return False
    record["methodology_warnings"] = updated
    return True


def upgrade_and_validate_manifest_plan(
    manifest: dict[str, Any], config: dict[str, Any]
) -> bool:
    runs = manifest.get("runs")
    if not isinstance(runs, list):
        raise OrchestratorError("manifest runs must be a list")
    upgraded = False
    default_threads = config["cpu_thread_levels"][0]
    default_duty = config["duty_cycles"][0]
    for slot in runs:
        resource = str(slot.get("resource", "")).upper()
        repetition = slot.get("repetition")
        if resource not in RESOURCE_CHOICES or not isinstance(repetition, int):
            raise OrchestratorError(f"invalid legacy plan slot: {slot}")
        cpu_threads = default_threads if resource == "CPU" else None
        duty = default_duty
        expected_condition_id = (
            f"cpu-t{cpu_threads:02d}-d{duty:03d}"
            if resource == "CPU"
            else f"npu-d{duty:03d}" if resource == "NPU"
            else f"gpu-d{duty:03d}"
        )
        additions = {
            "block_index": repetition,
            "condition_id": expected_condition_id,
            "cpu_threads": cpu_threads,
            "duty_cycle_percent": duty,
        }
        for key, value in additions.items():
            if key not in slot:
                slot[key] = value
                upgraded = True

    expected = {
        (
            condition["condition_id"],
            condition["resource"],
            condition["cpu_threads"],
            condition["duty_cycle_percent"],
        )
        for condition in build_conditions(
            config["resources"], config["cpu_thread_levels"], config["duty_cycles"]
        )
    }
    repeat = config["repeat"]
    for block_index in range(1, repeat + 1):
        block = [slot for slot in runs if slot.get("block_index") == block_index]
        actual = {
            (
                slot.get("condition_id"),
                slot.get("resource"),
                slot.get("cpu_threads"),
                slot.get("duty_cycle_percent"),
            )
            for slot in block
        }
        if len(block) != len(expected) or actual != expected:
            raise OrchestratorError(
                f"manifest block {block_index} does not match configured condition matrix"
            )
    if len(runs) != len(expected) * repeat:
        raise OrchestratorError("manifest slot count does not match configured block design")
    order = [slot.get("order_index") for slot in runs]
    if order != list(range(1, len(runs) + 1)):
        raise OrchestratorError("manifest order_index sequence is invalid")
    summary = plan_summary(runs, repeat)
    if upgraded:
        summary["design"] = {
            "name": "legacy_order_preserved",
            "version": 0,
            "target_design": BLOCK_DESIGN_NAME,
        }
    manifest["plan_summary"] = summary
    return upgraded


def runner_intent_arguments(
    resource: str,
    cpu_threads: int | None,
    duration_s: int,
    warmup: int,
    run_id: str,
    command_id: str,
    duty_cycle_percent: int = 100,
    duty_cycle_period_seconds: float = 10.0,
    gpu_profile_id: str = DEFAULT_GPU_PROFILE,
    npu_model_asset: str = DEFAULT_NPU_MODEL_ASSET,
) -> list[str]:
    # NPU goes to npu-runner with the same d1_* timed-run extras; CPU/GPU are unchanged.
    activity = NPU_RUNNER_ACTIVITY if resource == "NPU" else RUNNER_ACTIVITY
    arguments = [
        "shell", "am", "start", "-W", "-n", activity,
        "--ez", "d1_auto_start", "true",
        "--es", "d1_resource", resource,
    ]
    if resource == "CPU":
        if cpu_threads is None:
            raise ValueError("CPU runner Intent requires cpu_threads")
        arguments += ["--ei", "d1_cpu_threads", str(cpu_threads)]
    elif resource == "NPU":
        arguments += ["--es", "d1_npu_model_asset", npu_model_asset]
    else:
        arguments += ["--es", "d1_gpu_profile", gpu_profile_id]
    arguments += [
        "--es", "d1_limit_mode", "DURATION",
        "--el", "d1_duration_s", str(duration_s),
        "--ei", "d1_warmup_count", str(warmup),
        "--es", "d1_run_id", run_id,
        "--es", "d1_command_id", command_id,
        "--es", "d1_experiment_mode", "BASIC",
        "--ei", "d1_duty_cycle_percent", str(duty_cycle_percent),
        "--ef", "d1_duty_cycle_period_s", str(duty_cycle_period_seconds),
    ]
    return arguments


def runner_package_for(resource: Any) -> str:
    return NPU_RUNNER_PACKAGE if str(resource or "").upper() == "NPU" else RUNNER_PACKAGE


def remote_runner_directory_for(resource: Any) -> str:
    return (
        NPU_REMOTE_RUNNER_DIRECTORY if str(resource or "").upper() == "NPU"
        else REMOTE_RUNNER_DIRECTORY
    )


def npu_logger_capture_arguments(resource: Any) -> list[str]:
    """Extra d1_logger_v4 capture flags for NPU slots; empty for CPU/GPU (command unchanged)."""
    if str(resource or "").upper() != "NPU":
        return []
    arguments = ["--runner-package", NPU_RUNNER_PACKAGE]
    for tag in NPU_LOGGER_EXTRA_LOGCAT_TAGS:
        arguments += ["--extra-logcat-tag", tag]
    return arguments


def npu_runner_intent_kwargs(resource: Any, args: argparse.Namespace) -> dict[str, Any]:
    if str(resource or "").upper() != "NPU":
        return {}
    return {"npu_model_asset": getattr(args, "npu_model_asset", DEFAULT_NPU_MODEL_ASSET)}


def npu_config(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "runner_package": NPU_RUNNER_PACKAGE,
        "engine": "litert-compiled-model",
        "litert_runtime_version": NPU_LITERT_RUNTIME_VERSION,
        "dispatch_lib_sha256": NPU_DISPATCH_LIB_SHA256,
        "model_asset": getattr(args, "npu_model_asset", DEFAULT_NPU_MODEL_ASSET),
        "quality_gate": {
            "version": NPU_QUALITY_GATE_VERSION,
            "n": NPU_QUALITY_GATE_N,
            "reference": "CPU:" + getattr(args, "npu_reference_asset", DEFAULT_NPU_REFERENCE_ASSET),
            "input_spec": getattr(args, "npu_input_spec", DEFAULT_NPU_INPUT_SPEC),
            "criteria": "bit_identical_to_cpu==false && argmax_agreement==n/n && cosine_min>=0.99",
        },
    }


def npu_quality_intent_arguments(
    run_id: str, model_asset: str, reference_asset: str, input_spec: str,
    count: int = NPU_QUALITY_GATE_N,
) -> list[str]:
    """npu-runner smoke/gate Intent (s26_npu_go.bat protocol): 1 timed inference, then the gate."""
    return [
        "shell", "am", "start", "-W", "-n", NPU_RUNNER_ACTIVITY,
        "--es", "accelerator", "NPU",
        "--es", "dtype", "float",
        "--ei", "iterations", "1",
        "--ei", "warmup", "0",
        "--ei", "quality_n", str(count),
        "--es", "model_asset", model_asset,
        "--es", "ref_model_asset", reference_asset,
        "--es", "input_spec", input_spec,
        "--es", "run_id", run_id,
        "--ez", "autofinish", "true",
    ]


def npu_quality_summary_arguments(run_id: str) -> list[str]:
    return [
        "exec-out", "run-as", NPU_RUNNER_PACKAGE, "cat",
        f"files/npu-runner-v1/summary-{run_id}.json",
    ]


def evaluate_npu_quality_summary(
    summary: Any, run_id: str, model_asset: str, count: int = NPU_QUALITY_GATE_N,
) -> dict[str, Any]:
    """Apply the fixed NPU criteria (CLAUDE.md §5) to an npu-runner summary. bit_identical_to_cpu
    True means the candidate ran on CPU, so it fails even if argmax and cosine pass."""
    failures: list[str] = []
    summary = summary if isinstance(summary, dict) else {}
    gate = summary.get("quality_gate")
    gate = gate if isinstance(gate, dict) else {}
    model_sha = str(summary.get("model_sha256") or "").lower()
    if summary.get("schema") != "npu-runner-smoke-v1":
        failures.append("schema_mismatch")
    if summary.get("run_id") != run_id:
        failures.append("run_id_mismatch")
    if summary.get("status") != "OK":
        failures.append("runner_status_not_ok")
    if summary.get("accelerator_requested") != "NPU":
        failures.append("accelerator_not_npu")
    if summary.get("model") != model_asset:
        failures.append("model_asset_mismatch")
    if re.fullmatch(r"[0-9a-f]{64}", model_sha) is None:
        failures.append("model_sha256_missing")
    if not gate:
        failures.append("quality_gate_missing")
    else:
        cosine_min = gate.get("cosine_min")
        if gate.get("version") != NPU_QUALITY_GATE_VERSION:
            failures.append("quality_gate_version_mismatch")
        if gate.get("n") != count:
            failures.append("quality_gate_n_mismatch")
        if gate.get("bit_identical_to_cpu") is not False:
            failures.append("bit_identical_to_cpu")
        if gate.get("argmax_agreement") != f"{count}/{count}":
            failures.append("argmax_disagreement")
        if (
            not isinstance(cosine_min, (int, float)) or isinstance(cosine_min, bool)
            or cosine_min < NPU_QUALITY_COSINE_MIN
        ):
            failures.append("cosine_below_threshold")
        if gate.get("verdict") != "PASS":
            failures.append("runner_verdict_not_pass")
    return {
        "status": "passed" if not failures else "failed",
        "failure_reasons": failures,
        "run_id": run_id,
        "candidate_model": model_asset,
        "candidate_model_sha256": model_sha or None,
        "input_spec": summary.get("input_spec"),
        "input_generator": summary.get("input_generator"),
        "input_normalization": summary.get("input_normalization"),
        "device_model": summary.get("device_model"),
        "build_fingerprint": summary.get("build_fingerprint"),
        "engine": summary.get("engine"),
        "quality_gate": gate or None,
        "evaluated_utc": utc_now(),
    }


def effective_accuracy_policy(args: argparse.Namespace) -> str:
    if args.accuracy_preflight is not None:
        return args.accuracy_preflight
    return "required" if args.mode == "formal" else "optional"


def effective_validation_scope(args: argparse.Namespace) -> str:
    if getattr(args, "accuracy_validation_scope", None) is not None:
        return args.accuracy_validation_scope
    return "backend-performance-formal" if args.mode == "formal" else "thermal-only-pilot"


def accuracy_preflight_intent_arguments(
    command_id: str,
    input_count: int,
    seed: int,
    cpu_threads: int,
    atol: float,
    rtol: float,
    relative_epsilon: float,
    check_type: str = "synthetic",
    gpu_profile_id: str = DEFAULT_GPU_PROFILE,
    tensor_set_path: str | None = None,
    tensor_set_sha256: str | None = None,
    preprocessing_configuration_sha256: str | None = None,
) -> list[str]:
    arguments = [
        "shell", "am", "start", "-W", "-n", RUNNER_ACTIVITY,
        "--ez", "d1_accuracy_preflight", "true",
        "--es", "d1_command_id", command_id,
        "--ei", "d1_accuracy_input_count", str(input_count),
        "--el", "d1_accuracy_seed", str(seed),
        "--ei", "d1_accuracy_cpu_threads", str(cpu_threads),
        "--es", "d1_accuracy_atol", repr(atol),
        "--es", "d1_accuracy_rtol", repr(rtol),
        "--es", "d1_accuracy_relative_epsilon", repr(relative_epsilon),
        "--es", "d1_accuracy_check_type", check_type,
        "--es", "d1_gpu_profile", gpu_profile_id,
    ]
    if tensor_set_path is not None:
        arguments += ["--es", "d1_accuracy_tensor_set_path", tensor_set_path]
    if tensor_set_sha256 is not None:
        arguments += ["--es", "d1_accuracy_tensor_set_sha256", tensor_set_sha256]
    if preprocessing_configuration_sha256 is not None:
        arguments += [
            "--es", "d1_accuracy_preprocessing_sha256",
            preprocessing_configuration_sha256,
        ]
    return arguments


def accuracy_expected_provenance(
    args: argparse.Namespace,
    device_fingerprint: str,
    check_type: str = "synthetic",
    representative: dict[str, Any] | None = None,
) -> dict[str, Any]:
    value = {
        "schema_version": ACCURACY_SCHEMA_VERSION,
        "validation_scope": check_type,
        "equivalence_scope": "CPU_GPU_numerical_output_equivalence_not_task_accuracy",
        "device_fingerprint": device_fingerprint,
        "model_id": ACCURACY_MODEL_ID,
        "model_sha256": ACCURACY_MODEL_SHA256,
        "litert_version": ACCURACY_LITERT_VERSION,
        "gpu_delegate_profile": gpu_profile(getattr(args, "gpu_profile", DEFAULT_GPU_PROFILE)),
        "delegate_configuration": "TfLiteGpuDelegateV2_CompatibilityList_bestOptions",
        "comparator_version": ACCURACY_COMPARATOR_VERSION,
        "input_set_version": ACCURACY_INPUT_SET_VERSION,
        "seed": args.accuracy_seed,
        "input_count": args.accuracy_input_count,
        "input_shape": list(ACCURACY_INPUT_SHAPE),
        "input_dtype": ACCURACY_INPUT_DTYPE,
        "normalization": "synthetic_[0,1]_float32_no_additional_normalization",
        "reference_cpu_threads": args.accuracy_cpu_threads,
        "tolerance": {
            "atol": args.accuracy_atol,
            "rtol": args.accuracy_rtol,
            "relative_error_epsilon": args.accuracy_relative_epsilon,
        },
    }
    if representative is not None:
        value.update({
            "input_set_version": representative["header"]["format_version"],
            "seed": representative["header"]["selection"]["seed"],
            "input_count": representative["input_count"],
            "normalization": "host_preprocessed_rgb_central_crop_0.875_bilinear_float32_minus1_to_1",
            "tensor_set_sha256": representative["tensor_set_sha256"],
            "tensor_set_container_sha256": representative["container_sha256"],
            "label_mapping_file_sha256": representative["label_mapping_file_sha256"],
            "preprocessing_configuration_sha256": representative[
                "preprocessing_configuration_sha256"
            ],
            "representative_acceptance_policy": representative_acceptance_policy(),
            "task_accuracy_acceptance_policy": task_accuracy_acceptance_policy(),
        })
    return value


def can_reuse_accuracy_preflight(
    result: Any, expected_provenance: dict[str, Any], experiment_dir: Path
) -> bool:
    if not isinstance(result, dict) or result.get("status") != "passed":
        return False
    if result.get("provenance") != expected_provenance:
        return False
    relative_path = result.get("artifact_path")
    expected_hash = result.get("artifact_sha256")
    if not isinstance(relative_path, str) or not isinstance(expected_hash, str):
        return False
    artifact = experiment_dir / Path(relative_path)
    return artifact.is_file() and sha256_file(artifact) == expected_hash


def can_reuse_accuracy_validation(
    result: Any, cache_key: str, experiment_dir: Path
) -> bool:
    """Reuse only a completed schema-v2 result whose immutable artifacts still match."""
    if not isinstance(result, dict) or result.get("schema_version") != ACCURACY_SCHEMA_VERSION:
        return False
    if result.get("status") != "passed" or result.get("cache_key_sha256") != cache_key:
        return False
    checks = [result.get("synthetic_numerical_check")]
    representative = result.get("representative_input_equivalence")
    if isinstance(representative, dict) and representative.get("status") != "not_run":
        checks.append(representative)
    for check in checks:
        if not isinstance(check, dict) or check.get("status") != "passed":
            return False
        for path_key, hash_key in (
            ("artifact_path", "artifact_sha256"),
            ("runner_artifact_path", "runner_artifact_sha256"),
            ("binary_artifact_path", "binary_artifact_sha256"),
            ("delegate_log_path", "delegate_log_sha256"),
        ):
            relative_path = check.get(path_key)
            expected_hash = check.get(hash_key)
            if not isinstance(relative_path, str) or not isinstance(expected_hash, str):
                return False
            artifact = experiment_dir / Path(relative_path)
            if not artifact.is_file() or sha256_file(artifact) != expected_hash:
                return False
    return True


def accuracy_cache_provenance(
    args: argparse.Namespace,
    device_fingerprint: str,
    representative: dict[str, Any] | None,
) -> dict[str, Any]:
    """Fields which invalidate a prior preflight when any value changes."""
    return {
        "schema_version": ACCURACY_SCHEMA_VERSION,
        "validation_scope": effective_validation_scope(args),
        "device_fingerprint": device_fingerprint,
        "model_sha256": ACCURACY_MODEL_SHA256,
        "litert_version": ACCURACY_LITERT_VERSION,
        "gpu_delegate_profile": gpu_profile(args.gpu_profile),
        "comparator_version": ACCURACY_COMPARATOR_VERSION,
        "synthetic_input_set_version": ACCURACY_INPUT_SET_VERSION,
        "synthetic_seed": args.accuracy_seed,
        "synthetic_input_count": args.accuracy_input_count,
        "tolerance": {
            "atol": args.accuracy_atol,
            "rtol": args.accuracy_rtol,
            "relative_error_epsilon": args.accuracy_relative_epsilon,
        },
        "representative_tensor_set_sha256": (
            representative.get("tensor_set_sha256") if representative else None
        ),
        "representative_container_sha256": (
            representative.get("container_sha256") if representative else None
        ),
        "label_mapping_file_sha256": (
            representative.get("label_mapping_file_sha256") if representative else None
        ),
        "preprocessing_configuration_sha256": (
            representative.get("preprocessing_configuration_sha256")
            if representative else None
        ),
        "representative_policy_sha256": canonical_sha256(
            representative_acceptance_policy()
        ),
        "task_accuracy_policy_sha256": canonical_sha256(
            task_accuracy_acceptance_policy()
        ),
    }


def load_accuracy_runner_artifact(path: Path) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            try:
                value = json.loads(line)
            except json.JSONDecodeError as error:
                raise OrchestratorError(
                    f"invalid accuracy JSONL line {line_number}: {error}"
                ) from error
            if not isinstance(value, dict):
                raise OrchestratorError(f"accuracy JSONL line {line_number} is not an object")
            records.append(value)
    if len(records) < 2:
        raise OrchestratorError("accuracy JSONL lacks metadata or summary")
    sequences = [record.get("sequence") for record in records]
    if sequences != list(range(len(records))):
        raise OrchestratorError("accuracy JSONL sequence is not contiguous")
    schema_versions = {record.get("schema_version") for record in records}
    if len(schema_versions) != 1 or next(iter(schema_versions)) not in {
        LEGACY_ACCURACY_SCHEMA_VERSION, ACCURACY_SCHEMA_VERSION,
    }:
        raise OrchestratorError("accuracy JSONL schema version is inconsistent")
    command_ids = {record.get("command_id") for record in records}
    if len(command_ids) != 1 or None in command_ids:
        raise OrchestratorError("accuracy JSONL command_id is inconsistent")
    metadata = records[0]
    summary = records[-1]
    inputs = records[1:-1]
    if metadata.get("event") != "accuracy_preflight_metadata":
        raise OrchestratorError("accuracy JSONL first event is not metadata")
    if summary.get("event") != "accuracy_preflight_summary":
        raise OrchestratorError("accuracy JSONL final event is not summary")
    if any(record.get("event") != "accuracy_preflight_input" for record in inputs):
        raise OrchestratorError("accuracy JSONL contains an invalid per-input event")
    if any(record.get("input_index") != index for index, record in enumerate(inputs)):
        raise OrchestratorError("accuracy JSONL input indexes are not contiguous")
    return {
        "schema_version": metadata["schema_version"],
        "metadata": metadata,
        "inputs": inputs,
        "summary": summary,
    }


def validate_accuracy_binary(
    path: Path,
    expected_sha256: str,
    input_count: int,
    output_element_count: int,
    tolerance: dict[str, float] | None = None,
) -> dict[str, Any]:
    if sha256_file(path) != expected_sha256:
        raise OrchestratorError("accuracy binary SHA-256 mismatch")
    with path.open("rb") as stream:
        header = stream.read(16)
    if len(header) != 16 or header[:8] != b"D1EQV001":
        raise OrchestratorError("accuracy binary header is invalid")
    stored_inputs, stored_elements = struct.unpack("<II", header[8:])
    expected_size = 16 + input_count * output_element_count * 2 * 4
    if stored_inputs != input_count or stored_elements != output_element_count:
        raise OrchestratorError("accuracy binary dimensions do not match JSONL")
    if path.stat().st_size != expected_size:
        raise OrchestratorError("accuracy binary size does not match declared dimensions")
    result: dict[str, Any] = {
        "format_version": "d1eq-interleaved-float32-le-v1",
        "input_count": stored_inputs,
        "output_element_count": stored_elements,
        "size_bytes": expected_size,
        "sha256": expected_sha256,
    }
    if tolerance is None:
        return result
    atol = float(tolerance["atol"])
    rtol = float(tolerance["rtol"])
    epsilon = float(tolerance["relative_error_epsilon"])
    mismatch_count = 0
    non_finite_count = 0
    argmax_match_count = 0
    argmax_mismatch_count = 0
    max_absolute_error = 0.0
    max_relative_error = 0.0
    absolute_sum = 0.0
    squared_sum = 0.0
    finite_count = 0
    reference_output_hashes: list[str] = []
    candidate_output_hashes: list[str] = []
    per_input: list[dict[str, Any]] = []
    record_size = output_element_count * 4
    unpack_format = f"<{output_element_count}f"
    with path.open("rb") as stream:
        stream.seek(16)
        for _ in range(input_count):
            reference_bytes = stream.read(record_size)
            candidate_bytes = stream.read(record_size)
            reference_output_hashes.append(hashlib.sha256(reference_bytes).hexdigest())
            candidate_output_hashes.append(hashlib.sha256(candidate_bytes).hexdigest())
            reference = struct.unpack(unpack_format, reference_bytes)
            candidate = struct.unpack(unpack_format, candidate_bytes)
            finite_pair = all(math.isfinite(value) for value in reference + candidate)
            reference_top6 = sorted(
                range(output_element_count), key=lambda index: (-reference[index], index)
            )[:6] if finite_pair else []
            candidate_top6 = sorted(
                range(output_element_count), key=lambda index: (-candidate[index], index)
            )[:6] if finite_pair else []
            if finite_pair:
                if max(range(output_element_count), key=reference.__getitem__) == max(
                    range(output_element_count), key=candidate.__getitem__
                ):
                    argmax_match_count += 1
                else:
                    argmax_mismatch_count += 1
            else:
                argmax_mismatch_count += 1
            input_absolute_sum = 0.0
            dot = 0.0
            reference_squared = 0.0
            candidate_squared = 0.0
            for reference_value, candidate_value in zip(reference, candidate):
                if not math.isfinite(reference_value) or not math.isfinite(candidate_value):
                    non_finite_count += 1
                    mismatch_count += 1
                    continue
                error = abs(candidate_value - reference_value)
                relative_error = error / max(abs(reference_value), epsilon)
                max_absolute_error = max(max_absolute_error, error)
                max_relative_error = max(max_relative_error, relative_error)
                absolute_sum += error
                input_absolute_sum += error
                squared_sum += error * error
                dot += reference_value * candidate_value
                reference_squared += reference_value * reference_value
                candidate_squared += candidate_value * candidate_value
                finite_count += 1
                if error > atol + rtol * abs(reference_value):
                    mismatch_count += 1
            denominator = math.sqrt(reference_squared) * math.sqrt(candidate_squared)
            reference_boundary_margin = (
                reference[reference_top6[4]] - reference[reference_top6[5]]
                if len(reference_top6) >= 6 else None
            )
            candidate_boundary_margin = (
                candidate[candidate_top6[4]] - candidate[candidate_top6[5]]
                if len(candidate_top6) >= 6 else None
            )
            reference_boundary_tie = reference_boundary_margin == 0.0
            candidate_boundary_tie = candidate_boundary_margin == 0.0
            top5_overlap_applicable = (
                len(reference_top6) >= 6 and len(candidate_top6) >= 6
                and not reference_boundary_tie and not candidate_boundary_tie
            )
            top5_not_applicable_reason = (
                "reference_and_candidate_top5_boundary_tie"
                if reference_boundary_tie and candidate_boundary_tie else
                "reference_top5_boundary_tie" if reference_boundary_tie else
                "candidate_top5_boundary_tie" if candidate_boundary_tie else
                "top5_ranking_unavailable" if not top5_overlap_applicable else None
            )
            per_input.append({
                "input_index": len(per_input),
                "reference_minimum": min(reference) if finite_pair else None,
                "reference_maximum": max(reference) if finite_pair else None,
                "reference_probability_sum": sum(reference) if finite_pair else None,
                "candidate_minimum": min(candidate) if finite_pair else None,
                "candidate_maximum": max(candidate) if finite_pair else None,
                "candidate_probability_sum": sum(candidate) if finite_pair else None,
                "cosine_similarity": dot / denominator if finite_pair and denominator > 0 else None,
                "total_variation_distance": input_absolute_sum / 2.0 if finite_pair else None,
                "reference_argmax": reference_top6[0] if reference_top6 else None,
                "candidate_argmax": candidate_top6[0] if candidate_top6 else None,
                "reference_top5": reference_top6[:5],
                "candidate_top5": candidate_top6[:5],
                "top5_overlap_count": len(set(reference_top6[:5]) & set(candidate_top6[:5])),
                "top5_overlap_applicable": top5_overlap_applicable,
                "top5_overlap_not_applicable_reason": top5_not_applicable_reason,
                "top5_set_agreement": set(reference_top6[:5]) == set(candidate_top6[:5]),
                "ordered_top5_agreement": reference_top6[:5] == candidate_top6[:5],
                "reference_top1_margin": (
                    reference[reference_top6[0]] - reference[reference_top6[1]]
                    if len(reference_top6) >= 2 else None
                ),
                "candidate_top1_margin": (
                    candidate[candidate_top6[0]] - candidate[candidate_top6[1]]
                    if len(candidate_top6) >= 2 else None
                ),
                "reference_top5_boundary_margin": reference_boundary_margin,
                "candidate_top5_boundary_margin": candidate_boundary_margin,
            })
    cosine_values = [item["cosine_similarity"] for item in per_input
                     if item["cosine_similarity"] is not None]
    tv_values = [item["total_variation_distance"] for item in per_input
                 if item["total_variation_distance"] is not None]
    reference_sums = [item["reference_probability_sum"] for item in per_input
                      if item["reference_probability_sum"] is not None]
    candidate_sums = [item["candidate_probability_sum"] for item in per_input
                      if item["candidate_probability_sum"] is not None]
    applicable_overlap = [
        item["top5_overlap_count"] for item in per_input
        if item["top5_overlap_applicable"]
    ]
    result["host_recomputed"] = {
        "mismatch_count": mismatch_count,
        "non_finite_count": non_finite_count,
        "argmax_match_count": argmax_match_count,
        "argmax_mismatch_count": argmax_mismatch_count,
        "aggregate": {
            "output_element_count": input_count * output_element_count,
            "max_absolute_error": max_absolute_error,
            "mean_absolute_error": absolute_sum / finite_count if finite_count else 0.0,
            "rmse": math.sqrt(squared_sum / finite_count) if finite_count else 0.0,
            "max_relative_error": max_relative_error,
        },
        "reference_output_sha256": reference_output_hashes,
        "candidate_output_sha256": candidate_output_hashes,
        "per_input": per_input,
        "top5_set_match_count": sum(bool(item["top5_set_agreement"]) for item in per_input),
        "ordered_top5_match_count": sum(
            bool(item["ordered_top5_agreement"]) for item in per_input
        ),
        "minimum_top5_overlap_count": min(
            applicable_overlap, default=None
        ),
        "top5_overlap_applicable_count": len(applicable_overlap),
        "top5_overlap_not_applicable_count": len(per_input) - len(applicable_overlap),
        "minimum_cosine_similarity": min(cosine_values, default=None),
        "mean_cosine_similarity": (
            sum(cosine_values) / len(cosine_values) if cosine_values else None
        ),
        "maximum_total_variation_distance": max(tv_values, default=None),
        "mean_total_variation_distance": (
            sum(tv_values) / len(tv_values) if tv_values else None
        ),
        "reference_probability_sum_minimum": min(reference_sums, default=None),
        "reference_probability_sum_maximum": max(reference_sums, default=None),
        "candidate_probability_sum_minimum": min(candidate_sums, default=None),
        "candidate_probability_sum_maximum": max(candidate_sums, default=None),
    }
    return result


def load_delegate_evidence(raw_log: str) -> dict[str, Any]:
    module_path = Path(__file__).with_name("d1_logger_v4.py")
    spec = importlib.util.spec_from_file_location("d1_logger_v4_delegate", module_path)
    if spec is None or spec.loader is None:
        raise OrchestratorError(f"cannot load delegate parser: {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.delegate_evidence(raw_log)


def _finalize_legacy_accuracy_preflight(
    runner: dict[str, Any],
    delegate: dict[str, Any],
    expected_provenance: dict[str, Any],
    command_id: str,
    binary_validation: dict[str, Any],
) -> dict[str, Any]:
    metadata = runner["metadata"]
    inputs = runner["inputs"]
    summary = runner["summary"]
    failures: list[str] = []
    expected_metadata = {
        "command_id": command_id,
        "equivalence_scope": expected_provenance["equivalence_scope"],
        "comparator_version": expected_provenance["comparator_version"],
        "model_id": expected_provenance["model_id"],
        "model_sha256": expected_provenance["model_sha256"],
        "litert_version": expected_provenance["litert_version"],
        "delegate_configuration": expected_provenance["delegate_configuration"],
        "input_set_version": expected_provenance["input_set_version"],
        "seed": expected_provenance["seed"],
        "input_count": expected_provenance["input_count"],
        "input_shape": expected_provenance["input_shape"],
        "input_dtype": expected_provenance["input_dtype"],
        "normalization": expected_provenance["normalization"],
        "reference_cpu_threads": expected_provenance["reference_cpu_threads"],
        "tolerance": expected_provenance["tolerance"],
    }
    for key, expected in expected_metadata.items():
        if metadata.get(key) != expected:
            failures.append(f"provenance_mismatch:{key}")
    if metadata.get("schema_version") != LEGACY_ACCURACY_SCHEMA_VERSION:
        failures.append("schema_version_mismatch")
    if metadata.get("reference_resource") != "CPU" or metadata.get("candidate_resource") != "GPU":
        failures.append("resource_role_mismatch")
    if metadata.get("output_tensor_count") != 1:
        failures.append("output_tensor_count_mismatch")
    if metadata.get("output_shape") != ACCURACY_OUTPUT_SHAPE:
        failures.append("output_shape_mismatch")
    if metadata.get("output_dtype") != ACCURACY_OUTPUT_DTYPE:
        failures.append("output_dtype_mismatch")
    if (
        metadata.get("reference_model_sha256") != expected_provenance["model_sha256"]
        or metadata.get("candidate_model_sha256") != expected_provenance["model_sha256"]
    ):
        failures.append("cpu_gpu_model_sha256_mismatch")
    if len(inputs) != expected_provenance["input_count"]:
        failures.append("input_count_mismatch")
    if expected_provenance["input_count"] < 32:
        failures.append("insufficient_input_count")
    if any(not isinstance(record.get("input_sha256"), str) for record in inputs):
        failures.append("input_hash_missing")
    expected_input_hashes, expected_input_set_hash = deterministic_accuracy_input_hashes(
        expected_provenance["seed"],
        expected_provenance["input_count"],
        math.prod(expected_provenance["input_shape"]),
    )
    if [record.get("input_sha256") for record in inputs] != expected_input_hashes:
        failures.append("deterministic_input_hash_mismatch")
    if metadata.get("input_set_sha256") != expected_input_set_hash:
        failures.append("deterministic_input_set_hash_mismatch")
    if summary.get("numeric_equivalence_passed") is not True:
        failures.append("numeric_equivalence_failed")
    mismatch_count = summary.get("mismatch_count")
    non_finite_count = summary.get("non_finite_count")
    argmax_mismatch_count = summary.get("argmax_mismatch_count")
    if mismatch_count != 0:
        failures.append("elementwise_mismatch")
    if non_finite_count != 0:
        failures.append("non_finite_output")
    if argmax_mismatch_count != 0:
        failures.append("argmax_mismatch")
    if summary.get("argmax_match_count") != expected_provenance["input_count"]:
        failures.append("argmax_match_count_mismatch")
    host_recomputed = binary_validation.get("host_recomputed")
    if not isinstance(host_recomputed, dict):
        failures.append("host_binary_comparison_missing")
    else:
        for key in (
            "mismatch_count", "non_finite_count", "argmax_match_count",
            "argmax_mismatch_count",
        ):
            if host_recomputed.get(key) != summary.get(key):
                failures.append(f"host_binary_{key}_mismatch")
        if host_recomputed.get("mismatch_count") != 0:
            failures.append("host_binary_elementwise_mismatch")
        if host_recomputed.get("non_finite_count") != 0:
            failures.append("host_binary_non_finite_output")
        if host_recomputed.get("argmax_mismatch_count") != 0:
            failures.append("host_binary_argmax_mismatch")
        if host_recomputed.get("reference_output_sha256") != [
            record.get("reference_output_sha256") for record in inputs
        ]:
            failures.append("host_binary_reference_output_hash_mismatch")
        if host_recomputed.get("candidate_output_sha256") != [
            record.get("candidate_output_sha256") for record in inputs
        ]:
            failures.append("host_binary_candidate_output_hash_mismatch")
    if delegate.get("verification") != "verified" or delegate.get("full_delegate") is not True:
        failures.append("gpu_full_delegation_unverified")
    failures = list(dict.fromkeys(failures))
    return {
        "schema_version": LEGACY_ACCURACY_SCHEMA_VERSION,
        "legacy_semantics_preserved": True,
        "comparator_version": "combined-tolerance-v1",
        "status": "passed" if not failures else "failed",
        "reference_resource": "CPU",
        "candidate_resource": "GPU",
        "deterministic_input_count": expected_provenance["input_count"],
        "tolerance": expected_provenance["tolerance"],
        "mismatch_count": mismatch_count,
        "non_finite_count": non_finite_count,
        "argmax_match_count": summary.get("argmax_match_count"),
        "argmax_mismatch_count": argmax_mismatch_count,
        "aggregate": summary.get("aggregate"),
        "delegate_evidence": delegate,
        "model_input_provenance": metadata,
        "binary_validation": binary_validation,
        "failure_reasons": failures,
        "provenance": expected_provenance,
        "provenance_sha256": canonical_sha256(expected_provenance),
        "note": "CPU-GPU numerical output equivalence; not task accuracy",
    }


def _task_accuracy_from_host(
    inputs: list[dict[str, Any]], host: dict[str, Any], policy: dict[str, Any]
) -> dict[str, Any]:
    ground_truth: list[int] = []
    for record in inputs:
        value = record.get("ground_truth")
        if not isinstance(value, dict) or not isinstance(value.get("mapped_output_index"), int):
            return {
                "status": "not_run",
                "failure_reasons": [],
                "note": "ground-truth labels are absent",
                "acceptance_policy": policy,
            }
        ground_truth.append(value["mapped_output_index"])
    per_input = host.get("per_input")
    if not isinstance(per_input, list) or len(per_input) != len(ground_truth):
        return {
            "status": "error",
            "failure_reasons": ["host_per_input_metrics_missing"],
            "acceptance_policy": policy,
        }
    reference_top1 = sum(
        item.get("reference_argmax") == target for item, target in zip(per_input, ground_truth)
    )
    candidate_top1 = sum(
        item.get("candidate_argmax") == target for item, target in zip(per_input, ground_truth)
    )
    reference_top5 = sum(
        target in item.get("reference_top5", []) for item, target in zip(per_input, ground_truth)
    )
    candidate_top5 = sum(
        target in item.get("candidate_top5", []) for item, target in zip(per_input, ground_truth)
    )
    count = len(ground_truth)
    reference_top1_accuracy = reference_top1 / count if count else 0.0
    candidate_top1_accuracy = candidate_top1 / count if count else 0.0
    reference_top5_accuracy = reference_top5 / count if count else 0.0
    candidate_top5_accuracy = candidate_top5 / count if count else 0.0
    top1_delta = candidate_top1_accuracy - reference_top1_accuracy
    top5_delta = candidate_top5_accuracy - reference_top5_accuracy
    failures = []
    if count < policy["minimum_labeled_sample_count"]:
        failures.append("insufficient_labeled_sample_count")
    if top1_delta < -policy["maximum_top1_accuracy_drop"]:
        failures.append("top1_accuracy_drop_exceeded")
    if top5_delta < -policy["maximum_top5_accuracy_drop"]:
        failures.append("top5_accuracy_drop_exceeded")
    return {
        "status": "passed" if not failures else "failed",
        "labeled_input_count": count,
        "reference_top1_correct_count": reference_top1,
        "candidate_top1_correct_count": candidate_top1,
        "reference_top5_correct_count": reference_top5,
        "candidate_top5_correct_count": candidate_top5,
        "reference_top1_accuracy": reference_top1_accuracy,
        "candidate_top1_accuracy": candidate_top1_accuracy,
        "reference_top5_accuracy": reference_top5_accuracy,
        "candidate_top5_accuracy": candidate_top5_accuracy,
        "top1_accuracy_delta": top1_delta,
        "top5_accuracy_delta": top5_delta,
        "acceptance_policy": policy,
        "failure_reasons": failures,
        "note": "ground-truth task accuracy; separate from CPU-GPU output equivalence",
    }


def representative_acceptance_failures(
    host: dict[str, Any], policy: dict[str, Any]
) -> tuple[list[str], list[str]]:
    failures: list[str] = []
    integrity_failures: list[str] = []
    if host.get("argmax_mismatch_count", math.inf) > policy["maximum_top1_mismatch_count"]:
        failures.append("representative_top1_mismatch_limit_exceeded")
    applicable_overlap_count = host.get("top5_overlap_applicable_count")
    minimum_overlap = host.get("minimum_top5_overlap_count")
    if not isinstance(applicable_overlap_count, int):
        integrity_failures.append("host_top5_applicability_missing")
    elif applicable_overlap_count > 0 and (
        not isinstance(minimum_overlap, int)
        or minimum_overlap < policy["minimum_top5_overlap_per_input"]
    ):
        failures.append("representative_top5_overlap_below_minimum")
    maximum_tv = host.get("maximum_total_variation_distance")
    if maximum_tv is None or maximum_tv > policy["maximum_total_variation_distance"]:
        failures.append("representative_total_variation_limit_exceeded")
    minimum_cosine = host.get("minimum_cosine_similarity")
    if minimum_cosine is None or minimum_cosine < policy["minimum_cosine_similarity"]:
        failures.append("representative_cosine_below_minimum")
    return failures, integrity_failures


def finalize_accuracy_preflight(
    runner: dict[str, Any],
    delegate: dict[str, Any],
    expected_provenance: dict[str, Any],
    command_id: str,
    binary_validation: dict[str, Any],
) -> dict[str, Any]:
    runner_schema = runner.get("schema_version") or runner.get("metadata", {}).get(
        "schema_version"
    )
    if runner_schema == LEGACY_ACCURACY_SCHEMA_VERSION:
        legacy_expected = dict(expected_provenance)
        legacy_expected.update({
            "equivalence_scope": "CPU_GPU_numerical_output_equivalence_not_task_accuracy",
            "comparator_version": "combined-tolerance-v1",
            "delegate_configuration": "TfLiteGpuDelegateV2_CompatibilityList_bestOptions",
        })
        legacy_expected.pop("schema_version", None)
        legacy_expected.pop("validation_scope", None)
        legacy_expected.pop("gpu_delegate_profile", None)
        return _finalize_legacy_accuracy_preflight(
            runner, delegate, legacy_expected, command_id, binary_validation
        )

    metadata = runner["metadata"]
    inputs = runner["inputs"]
    summary = runner["summary"]
    check_type = expected_provenance["validation_scope"]
    failures: list[str] = []
    if metadata.get("command_id") != command_id:
        failures.append("provenance_mismatch:command_id")
    for key in (
        "comparator_version", "model_id", "model_sha256", "litert_version", "input_shape",
        "input_dtype", "reference_cpu_threads", "tolerance",
    ):
        if metadata.get(key) != expected_provenance.get(key):
            failures.append(f"provenance_mismatch:{key}")
    if metadata.get("schema_version") != ACCURACY_SCHEMA_VERSION:
        failures.append("schema_version_mismatch")
    if metadata.get("validation_scope") != check_type:
        failures.append("validation_scope_mismatch")
    if metadata.get("gpu_delegate_profile") != expected_provenance["gpu_delegate_profile"]:
        failures.append("gpu_delegate_profile_mismatch")
    if metadata.get("reference_model_sha256") != metadata.get("candidate_model_sha256"):
        failures.append("cpu_gpu_model_sha256_mismatch")
    if metadata.get("output_shape") != ACCURACY_OUTPUT_SHAPE:
        failures.append("output_shape_mismatch")
    if metadata.get("output_dtype") != ACCURACY_OUTPUT_DTYPE:
        failures.append("output_dtype_mismatch")
    if len(inputs) != expected_provenance["input_count"]:
        failures.append("input_count_mismatch")
    minimum_input_count = 32 if check_type == "synthetic" else int(
        expected_provenance["representative_acceptance_policy"]["minimum_sample_count"]
    )
    if expected_provenance["input_count"] < minimum_input_count:
        failures.append("insufficient_input_count")
    if summary.get("non_finite_count") != 0:
        failures.append("non_finite_output")
    host = binary_validation.get("host_recomputed")
    if not isinstance(host, dict):
        failures.append("host_binary_comparison_missing")
        host = {}
    else:
        for key in ("mismatch_count", "non_finite_count", "argmax_match_count", "argmax_mismatch_count"):
            if host.get(key) != summary.get(key):
                failures.append(f"host_binary_{key}_mismatch")
        if host.get("reference_output_sha256") != [record.get("reference_output_sha256") for record in inputs]:
            failures.append("host_binary_reference_output_hash_mismatch")
        if host.get("candidate_output_sha256") != [record.get("candidate_output_sha256") for record in inputs]:
            failures.append("host_binary_candidate_output_hash_mismatch")
    if delegate.get("verification") != "verified" or delegate.get("full_delegate") is not True:
        failures.append("gpu_full_delegation_unverified")

    acceptance_failures: list[str] = []
    if check_type == "synthetic":
        expected_hashes, expected_set_hash = deterministic_accuracy_input_hashes(
            expected_provenance["seed"], expected_provenance["input_count"],
            math.prod(expected_provenance["input_shape"]),
        )
        if [record.get("input_sha256") for record in inputs] != expected_hashes:
            failures.append("deterministic_input_hash_mismatch")
        if metadata.get("input_set_sha256") != expected_set_hash:
            failures.append("deterministic_input_set_hash_mismatch")
    else:
        representative = metadata.get("representative_tensor_set")
        if not isinstance(representative, dict):
            failures.append("representative_tensor_set_metadata_missing")
        else:
            for key in (
                "tensor_set_sha256", "tensor_set_container_sha256",
                "label_mapping_file_sha256",
                "preprocessing_configuration_sha256",
            ):
                if representative.get(key) != expected_provenance.get(key):
                    failures.append(f"representative_{key}_mismatch")
        policy = expected_provenance["representative_acceptance_policy"]
        acceptance, additional_integrity = representative_acceptance_failures(
            host, policy
        )
        acceptance_failures.extend(acceptance)
        failures.extend(additional_integrity)

    integrity_failures = list(dict.fromkeys(failures))
    acceptance_failures = list(dict.fromkeys(acceptance_failures))
    failures = integrity_failures + [
        reason for reason in acceptance_failures if reason not in integrity_failures
    ]
    result = {
        "schema_version": ACCURACY_SCHEMA_VERSION,
        "validation_scope": check_type,
        "status": "passed" if not failures else "failed",
        "execution_integrity_status": (
            "passed" if not integrity_failures else "failed"
        ),
        "execution_integrity_failure_reasons": integrity_failures,
        "equivalence_acceptance_status": (
            "passed" if not failures else "failed"
        ),
        "equivalence_acceptance_failure_reasons": acceptance_failures,
        "numerical_tolerance_result": (
            "within" if summary.get("mismatch_count") == 0 else "outside"
        ),
        "combined_tolerance_is_diagnostic": True,
        "tolerance": expected_provenance["tolerance"],
        "mismatch_count": summary.get("mismatch_count"),
        "non_finite_count": summary.get("non_finite_count"),
        "argmax_match_count": summary.get("argmax_match_count"),
        "argmax_mismatch_count": summary.get("argmax_mismatch_count"),
        "aggregate": summary.get("aggregate"),
        "host_binary_metrics": host,
        "delegate_evidence": delegate,
        "model_input_provenance": metadata,
        "binary_validation": binary_validation,
        "failure_reasons": failures,
        "provenance": expected_provenance,
        "provenance_sha256": canonical_sha256(expected_provenance),
        "note": "CPU-GPU output equivalence; not automatically task accuracy",
    }
    if check_type == "representative":
        result["acceptance_policy"] = expected_provenance["representative_acceptance_policy"]
        result["task_accuracy_check"] = _task_accuracy_from_host(
            inputs, host, expected_provenance["task_accuracy_acceptance_policy"]
        )
    return result


def accuracy_policy_allows_slots(policy: str, status: str) -> bool:
    return policy != "required" or status == "passed"


def compose_accuracy_validation(
    scope: str,
    policy: str,
    synthetic: dict[str, Any],
    representative: dict[str, Any] | None = None,
    task_accuracy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    representative = representative or {
        "status": "not_run", "failure_reasons": [],
        "note": "no representative tensor-set was executed",
    }
    task_accuracy = task_accuracy or {
        "status": "not_run", "failure_reasons": [],
        "note": "ground-truth task accuracy was not executed",
    }
    gate_failures: list[str] = []
    if scope in {"backend-performance-formal", "accuracy-preserving-formal"}:
        if synthetic.get("status") != "passed":
            gate_failures.append("synthetic_numerical_check_not_passed")
    elif synthetic.get("status") in {"failed", "error"}:
        gate_failures.append("synthetic_execution_integrity_failed")
    if scope in {"backend-performance-formal", "accuracy-preserving-formal"} and (
        representative.get("status") != "passed"
    ):
        gate_failures.append("representative_input_equivalence_not_passed")
    if scope == "accuracy-preserving-formal" and task_accuracy.get("status") != "passed":
        gate_failures.append("task_accuracy_check_not_passed")
    gate_status = "passed" if not gate_failures else "failed"
    overall_status = gate_status if policy == "required" else (
        "passed" if synthetic.get("status") == "passed" else synthetic.get("status", "not_run")
    )
    return {
        "schema_version": ACCURACY_SCHEMA_VERSION,
        "validation_scope": scope,
        "status": overall_status,
        "policy": policy,
        "synthetic_numerical_check": synthetic,
        "representative_input_equivalence": representative,
        "task_accuracy_check": task_accuracy,
        "formal_gate_result": {
            "status": gate_status,
            "failure_reasons": gate_failures,
            "representative_is_blocking": scope in {
                "backend-performance-formal", "accuracy-preserving-formal",
            },
            "task_accuracy_is_blocking": scope == "accuracy-preserving-formal",
        },
        "failure_reasons": gate_failures,
        "limitations": [
            "synthetic numerical tolerance is diagnostic and is not task accuracy",
            "precision_loss_allowed does not reveal actual driver FP16 execution",
            "Imagenette is a ten-class subset and is not full ImageNet accuracy",
        ],
    }


def accuracy_config(args: argparse.Namespace) -> dict[str, Any]:
    synthetic = {
        "status": "not_run",
        "purpose": "runtime_tensor_delegate_and_catastrophic_numerical_smoke",
        "numerical_tolerance_result": "not_run",
        "deterministic_input_count": args.accuracy_input_count,
        "input_set_version": ACCURACY_INPUT_SET_VERSION,
        "seed": args.accuracy_seed,
        "tolerance": {
            "atol": args.accuracy_atol,
            "rtol": args.accuracy_rtol,
            "relative_error_epsilon": args.accuracy_relative_epsilon,
        },
        "blocking_gate": False,
    }
    representative = {
        "status": "not_run",
        "purpose": "CPU_GPU_output_equivalence_on_host_preprocessed_real_images",
        "tensor_set_path": str(args.representative_tensor_set)
        if getattr(args, "representative_tensor_set", None) else None,
        "acceptance_policy": representative_acceptance_policy(),
        "blocking_gate": effective_validation_scope(args) in {
            "backend-performance-formal", "accuracy-preserving-formal",
        },
    }
    task = {
        "status": "not_run",
        "purpose": "ground_truth_task_accuracy_separate_from_backend_equivalence",
        "acceptance_policy": task_accuracy_acceptance_policy(),
        "blocking_gate": effective_validation_scope(args) == "accuracy-preserving-formal",
    }
    return {
        "schema_version": ACCURACY_SCHEMA_VERSION,
        "validation_scope": effective_validation_scope(args),
        "policy": effective_accuracy_policy(args),
        "status": "not_run",
        "equivalence_scope": "CPU_GPU_numerical_output_equivalence_not_task_accuracy",
        "deterministic_input_count": args.accuracy_input_count,
        "reference_resource": "CPU",
        "candidate_resource": "GPU",
        "reference_cpu_threads": args.accuracy_cpu_threads,
        "comparator_version": ACCURACY_COMPARATOR_VERSION,
        "input_set_version": ACCURACY_INPUT_SET_VERSION,
        "seed": args.accuracy_seed,
        "tolerance": {
            "atol": args.accuracy_atol,
            "rtol": args.accuracy_rtol,
            "relative_error_epsilon": args.accuracy_relative_epsilon,
        },
        "timeout_seconds": args.accuracy_timeout_seconds,
        "mismatch_count": None,
        "gpu_delegate_profile": gpu_profile(getattr(args, "gpu_profile", DEFAULT_GPU_PROFILE)),
        "synthetic_numerical_check": synthetic,
        "representative_input_equivalence": representative,
        "task_accuracy_check": task,
        "formal_gate_result": {"status": "not_run", "failure_reasons": []},
        "failure_reasons": [],
        "limitations": [
            "synthetic numerical smoke is not task accuracy",
            "precision_loss_allowed does not prove actual FP16 execution",
            "Imagenette covers ten ImageNet classes and not full ImageNet accuracy",
        ],
        "note": "three-scope CPU-GPU validation; task accuracy remains separate",
    }


def start_run_arguments() -> list[str]:
    return [
        "shell", "am", "start", "-W", "-n", D1_ACTIVITY,
        "--es", "d1_automation_command", "START_RUN",
    ]


def stop_run_arguments() -> list[str]:
    return [
        "shell", "am", "start", "-W", "-n", D1_ACTIVITY,
        "--es", "d1_automation_command", "STOP_RUN",
    ]


def direct_stop_arguments() -> list[str]:
    return [
        "shell", "run-as", D1_PACKAGE,
        "am", "start-foreground-service", "--user", "0",
        "-a", D1_STOP_ACTION, "-n", D1_SERVICE,
    ]


class AdbClient:
    def __init__(self, adb: str, serial: str | None = None) -> None:
        self.adb = adb
        self.serial = serial

    @property
    def base(self) -> list[str]:
        return [self.adb] + (["-s", self.serial] if self.serial else [])

    def run(
        self,
        arguments: list[str],
        *,
        timeout: float = 30,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        try:
            result = subprocess.run(
                self.base + arguments,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as error:
            raise OrchestratorError(
                f"ADB command timed out after {timeout}s: {self.base + arguments}"
            ) from error
        if check and result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip() or "no output"
            raise OrchestratorError(
                f"ADB command failed rc={result.returncode}: {arguments}; {detail[:800]}"
            )
        return result

    def popen(self, arguments: list[str]) -> subprocess.Popen[str]:
        return subprocess.Popen(
            self.base + arguments,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )


class ProcessLines:
    _END = object()

    def __init__(self, process: subprocess.Popen[str], name: str) -> None:
        self.process = process
        self.name = name
        self.lines: deque[str] = deque(maxlen=20_000)
        self.queue: queue.Queue[str | object] = queue.Queue()
        self.thread = threading.Thread(target=self._pump, name=f"{name}-output", daemon=True)
        self.thread.start()

    def _pump(self) -> None:
        assert self.process.stdout is not None
        try:
            for line in self.process.stdout:
                value = line.rstrip("\r\n")
                self.lines.append(value)
                self.queue.put(value)
        finally:
            self.queue.put(self._END)

    def wait_for_line(
        self,
        predicate: Callable[[str], bool],
        timeout: float,
        description: str,
        companions: Iterable["ProcessLines"] = (),
    ) -> str:
        deadline = time.monotonic() + timeout
        while True:
            for companion in companions:
                code = companion.process.poll()
                if code is not None:
                    raise OrchestratorError(
                        f"{companion.name} exited unexpectedly rc={code}; "
                        f"tail={list(companion.lines)[-10:]}"
                    )
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise WaitTimeout(f"timeout waiting for {description} after {timeout:.1f}s")
            try:
                item = self.queue.get(timeout=min(0.25, remaining))
            except queue.Empty:
                continue
            if item is self._END:
                code = self.process.poll()
                raise OrchestratorError(
                    f"{self.name} stdout EOF while waiting for {description}; rc={code}; "
                    f"tail={list(self.lines)[-10:]}"
                )
            line = str(item)
            if predicate(line):
                return line

    def wait_for_event(
        self,
        predicate: Callable[[dict[str, Any]], bool],
        timeout: float,
        description: str,
        companions: Iterable["ProcessLines"] = (),
    ) -> dict[str, Any]:
        matched: dict[str, Any] = {}

        def matches(line: str) -> bool:
            event = extract_json(line)
            if event is not None and predicate(event):
                matched.update(event)
                return True
            return False

        self.wait_for_line(matches, timeout, description, companions)
        return matched

    def terminate(self) -> None:
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
        self.thread.join(timeout=2)


def stop_d1_run(
    adb: AdbClient,
    wait_for_stop: Callable[[float], dict[str, Any]],
    timeout: float,
) -> dict[str, Any]:
    activity_result = adb.run(stop_run_arguments(), timeout=20, check=False)
    activity_error: str | None = None
    if activity_result.returncode == 0:
        try:
            event = wait_for_stop(timeout)
            return {
                "event": event,
                "recovery_used": False,
                "activity_stop_error": None,
            }
        except WaitTimeout as error:
            activity_error = str(error)
    else:
        activity_error = (
            activity_result.stderr.strip()
            or activity_result.stdout.strip()
            or f"returncode={activity_result.returncode}"
        )
    recovery = adb.run(direct_stop_arguments(), timeout=20, check=False)
    if recovery.returncode != 0:
        detail = recovery.stderr.strip() or recovery.stdout.strip() or "no output"
        raise OrchestratorError(
            "STOP_RUN and direct service STOP both failed; "
            f"activity_error={activity_error!r}; direct_rc={recovery.returncode}; {detail[:800]}"
        )
    event = wait_for_stop(timeout)
    return {
        "event": event,
        "recovery_used": True,
        "activity_stop_error": activity_error,
    }


def classify_runner_terminal(event: dict[str, Any], run_id: str) -> str | None:
    if event.get("source") != "gpu" or event.get("run_id") != run_id:
        return None
    name = event.get("event")
    if name == "file_summary":
        return "success" if event.get("status") == "ok" else "failure"
    if name in RUNNER_FAILURE_EVENTS:
        return "failure"
    if name == "run_metadata" and event.get("experiment_valid") is False:
        return "failure"
    return None


@dataclass(frozen=True)
class RemoteRunnerProbe:
    state: str
    remote_path: str | None = None
    event: dict[str, Any] | None = None
    detail: str | None = None


@dataclass(frozen=True)
class RunnerTerminalDetection:
    kind: str
    event: dict[str, Any]
    source: str
    fallback_used: bool
    remote_runner_path: str | None
    logcat_terminal_missing: bool
    remote_probe_count: int
    final_remote_probe_used: bool


def _adb_failure_detail(result: subprocess.CompletedProcess[str]) -> str:
    return result.stderr.strip() or result.stdout.strip() or "no output"


def _is_remote_missing(result: subprocess.CompletedProcess[str]) -> bool:
    detail = f"{result.stdout}\n{result.stderr}".lower()
    return "no such file or directory" in detail


def probe_remote_runner(
    adb: AdbClient, run_id: str, remote_directory: str = REMOTE_RUNNER_DIRECTORY
) -> RemoteRunnerProbe:
    listing = adb.run(
        ["shell", "ls", "-1", remote_directory],
        timeout=20,
        check=False,
    )
    if listing.returncode != 0:
        if _is_remote_missing(listing):
            return RemoteRunnerProbe("not_found", detail=_adb_failure_detail(listing))
        raise RemoteRunnerAdbError(
            f"remote runner ls failed rc={listing.returncode}: "
            f"{_adb_failure_detail(listing)[:800]}"
        )
    pattern = re.compile(
        rf"^gpu-events-{re.escape(run_id)}-([A-Za-z0-9-]+)\.jsonl$"
    )
    matches: list[tuple[str, str]] = []
    for raw_line in listing.stdout.splitlines():
        filename = Path(raw_line.strip()).name
        match = pattern.fullmatch(filename)
        if match:
            matches.append((filename, match.group(1)))
    if not matches:
        return RemoteRunnerProbe("not_found")
    if len(matches) != 1:
        paths = [f"{remote_directory}/{filename}" for filename, _ in matches]
        raise RemoteRunnerAmbiguityError(
            f"multiple remote runner files for run_id={run_id}: {paths}"
        )
    filename, expected_session_id = matches[0]
    remote_path = f"{remote_directory}/{filename}"
    tail = adb.run(
        ["shell", "tail", "-n", str(REMOTE_TAIL_LINES), remote_path],
        timeout=20,
        check=False,
    )
    if tail.returncode != 0:
        raise RemoteRunnerAdbError(
            f"remote runner tail failed rc={tail.returncode} path={remote_path}: "
            f"{_adb_failure_detail(tail)[:800]}"
        )
    raw_lines = [line for line in tail.stdout.splitlines() if line.strip()]
    if not raw_lines:
        return RemoteRunnerProbe("incomplete", remote_path, detail="empty remote tail")
    events: list[dict[str, Any]] = []
    for index, line in enumerate(raw_lines):
        event = extract_json(line)
        if event is None:
            if index == len(raw_lines) - 1:
                return RemoteRunnerProbe(
                    "incomplete", remote_path, detail="partial final JSONL record"
                )
            raise RemoteRunnerValidationError(
                f"invalid JSON in remote runner tail path={remote_path} line={index + 1}"
            )
        events.append(event)
    previous_sequence: int | None = None
    for event in events:
        if event.get("run_id") != run_id:
            raise RemoteRunnerValidationError(
                f"remote runner run_id mismatch path={remote_path}: {event.get('run_id')!r}"
            )
        if event.get("source") != "gpu":
            raise RemoteRunnerValidationError(
                f"remote runner source mismatch path={remote_path}: {event.get('source')!r}"
            )
        if event.get("schema_version") != RUNNER_SCHEMA_VERSION:
            raise RemoteRunnerValidationError(
                f"remote runner schema mismatch path={remote_path}: "
                f"{event.get('schema_version')!r}"
            )
        if event.get("runner_session_id") != expected_session_id:
            raise RemoteRunnerValidationError(
                f"remote runner session mismatch path={remote_path}: "
                f"{event.get('runner_session_id')!r}"
            )
        sequence = event.get("sequence")
        if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence < 0:
            raise RemoteRunnerValidationError(
                f"remote runner invalid sequence path={remote_path}: {sequence!r}"
            )
        if previous_sequence is not None and sequence != previous_sequence + 1:
            raise RemoteRunnerValidationError(
                f"remote runner non-contiguous tail sequence path={remote_path}: "
                f"{previous_sequence}->{sequence}"
            )
        previous_sequence = sequence
    failure = next(
        (
            event for event in reversed(events)
            if event.get("event") in RUNNER_FAILURE_EVENTS or event.get("status") == "error"
        ),
        None,
    )
    if failure is not None:
        return RemoteRunnerProbe("failure", remote_path, failure)
    final = events[-1]
    if final.get("event") != "file_summary":
        return RemoteRunnerProbe(
            "incomplete",
            remote_path,
            final,
            f"last event is {final.get('event')!r}, not file_summary",
        )
    if final.get("status") != "ok":
        return RemoteRunnerProbe("failure", remote_path, final)
    sequence = final["sequence"]
    if (
        final.get("sequence_first") != 0
        or final.get("sequence_last") != sequence
        or final.get("file_event_count") != sequence + 1
    ):
        raise RemoteRunnerValidationError(
            f"remote file_summary sequence metadata mismatch path={remote_path}"
        )
    return RemoteRunnerProbe("success", remote_path, final)


def wait_for_runner_terminal(
    run_id: str,
    wait_for_logcat: Callable[[float], dict[str, Any]],
    probe_remote: Callable[[bool], RemoteRunnerProbe],
    expected_completion_delay_s: float,
    hard_timeout_s: float,
    *,
    sparse_poll_interval_s: float = REMOTE_POLL_INTERVAL_SECONDS,
    monotonic: Callable[[], float] = time.monotonic,
    periodic_interval_s: float = 0.0,
    periodic_check: Callable[[], None] | None = None,
) -> RunnerTerminalDetection:
    started = monotonic()
    fallback_at = started + expected_completion_delay_s
    deadline = started + hard_timeout_s
    next_probe = fallback_at
    next_periodic = (
        started + periodic_interval_s
        if periodic_check is not None and periodic_interval_s > 0
        else math.inf
    )
    probe_count = 0
    while True:
        now = monotonic()
        if now >= next_periodic:
            assert periodic_check is not None
            periodic_check()
            next_periodic = monotonic() + periodic_interval_s
            now = monotonic()
        if now >= deadline:
            probe_count += 1
            final_probe = probe_remote(True)
            if final_probe.state in {"success", "failure"}:
                assert final_probe.event is not None
                return RunnerTerminalDetection(
                    final_probe.state,
                    final_probe.event,
                    "remote_runner_jsonl",
                    True,
                    final_probe.remote_path,
                    True,
                    probe_count,
                    True,
                )
            raise WaitTimeout(
                f"runner hard timeout after {hard_timeout_s:.1f}s; final remote state="
                f"{final_probe.state}; path={final_probe.remote_path}; "
                f"detail={final_probe.detail}"
            )
        wait_until = min(deadline, next_probe, next_periodic)
        if now < wait_until:
            try:
                event = wait_for_logcat(wait_until - now)
            except WaitTimeout:
                continue
            kind = classify_runner_terminal(event, run_id)
            if kind is None:
                continue
            return RunnerTerminalDetection(
                kind,
                event,
                "logcat",
                False,
                None,
                False,
                probe_count,
                False,
            )
        probe_count += 1
        current_probe = probe_remote(False)
        if current_probe.state in {"success", "failure"}:
            assert current_probe.event is not None
            return RunnerTerminalDetection(
                current_probe.state,
                current_probe.event,
                "remote_runner_jsonl",
                True,
                current_probe.remote_path,
                True,
                probe_count,
                False,
            )
        next_probe = monotonic() + sparse_poll_interval_s


def wait_for_idle_interval(
    duration_s: float,
    wait_for_log_line: Callable[[float], None],
    *,
    periodic_interval_s: float = 0.0,
    periodic_check: Callable[[], None] | None = None,
    monotonic: Callable[[], float] = time.monotonic,
) -> dict[str, float]:
    started = monotonic()
    deadline = started + duration_s
    next_periodic = (
        started + periodic_interval_s
        if periodic_check is not None and periodic_interval_s > 0
        else math.inf
    )
    while True:
        now = monotonic()
        if now >= deadline:
            return {
                "host_start_monotonic_s": started,
                "host_end_monotonic_s": now,
                "actual_duration_s": now - started,
            }
        if now >= next_periodic:
            assert periodic_check is not None
            periodic_check()
            next_periodic = monotonic() + periodic_interval_s
            continue
        wait_until = min(deadline, next_periodic)
        try:
            wait_for_log_line(wait_until - now)
        except WaitTimeout:
            continue


def wait_for_thermal_cooling(
    record: dict[str, Any],
    policy: str,
    minimum_seconds: float,
    timeout_seconds: float,
    sample_interval_seconds: float,
    stability_window_seconds: float,
    max_range_c: float,
    max_slope_c_per_minute: float,
    matched_tolerance_c: float,
    reference: dict[str, float] | None,
    get_temperature_vector: Callable[[], dict[str, float]],
    wait_for_log_line: Callable[[float], None],
    *,
    periodic_interval_s: float = 0.0,
    periodic_check: Callable[[], None] | None = None,
    monotonic: Callable[[], float] = time.monotonic,
    on_update: Callable[[], None] | None = None,
) -> dict[str, Any]:
    if policy not in {"stable", "matched"}:
        raise ValueError(f"conditioned cooling requires stable or matched, got {policy!r}")
    started = monotonic()
    record.update({
        "policy": policy,
        "status": "collecting",
        "completion_reason": None,
        "started_utc": utc_now(),
        "host_start_monotonic_s": started,
        "raw_temperature_samples": [],
        "stability_evaluations": [],
        "reference_evaluation": None,
        "emergency_result": {"status": "not_triggered"},
    })
    if policy == "matched" and reference is None:
        record.update({
            "status": "failed",
            "completion_reason": "missing_thermal_conditioning_reference",
            "completed_utc": utc_now(),
            "host_end_monotonic_s": started,
            "actual_duration_s": 0.0,
        })
        if on_update is not None:
            on_update()
        raise OrchestratorError(
            "matched cooling requires thermal_conditioning_reference"
        )
    deadline = started + timeout_seconds
    next_sample = started
    next_periodic = (
        started + periodic_interval_s
        if periodic_check is not None and periodic_interval_s > 0
        else math.inf
    )

    def complete(now: float, status: str, reason: str) -> None:
        record.update({
            "status": status,
            "completion_reason": reason,
            "completed_utc": utc_now(),
            "host_end_monotonic_s": now,
            "actual_duration_s": now - started,
        })
        if on_update is not None:
            on_update()

    while True:
        now = monotonic()
        if now >= next_periodic:
            assert periodic_check is not None
            periodic_check()
            next_periodic = monotonic() + periodic_interval_s
            continue
        if now >= next_sample:
            try:
                vector = get_temperature_vector()
            except Exception as error:
                complete(monotonic(), "failed", "thermal_sensor_error")
                record["error"] = f"{error.__class__.__name__}: {error}"
                if on_update is not None:
                    on_update()
                raise
            sample = {
                "captured_utc": utc_now(),
                "host_monotonic_s": now,
                "android_mono_ns": None,
                "temperatures_c": dict(vector),
            }
            record["raw_temperature_samples"].append(sample)
            stability = evaluate_thermal_stability(
                record["raw_temperature_samples"],
                stability_window_seconds,
                max_range_c,
                max_slope_c_per_minute,
            )
            stability["evaluated_host_monotonic_s"] = monotonic()
            record["stability_evaluations"].append(stability)
            match_pass = policy == "stable"
            if policy == "matched" and stability["stable"]:
                match = evaluate_reference_match(
                    vector, reference, matched_tolerance_c
                )
                record["reference_evaluation"] = match
                match_pass = match["matched"]
            evaluated_now = monotonic()
            if (
                evaluated_now - started >= minimum_seconds
                and stability["stable"]
                and match_pass
            ):
                complete(evaluated_now, "completed", f"{policy}_condition_met")
                return record
            next_sample = evaluated_now + sample_interval_seconds
            if on_update is not None:
                on_update()
            now = evaluated_now
        if now >= deadline:
            record["failure_classification"] = "thermal_conditioning_timeout"
            complete(now, "timeout", "cooling_timeout")
            raise CoolingTimeout(
                f"{policy} cooling timed out after {timeout_seconds:.1f}s"
            )
        wait_until = min(deadline, next_sample, next_periodic)
        try:
            wait_for_log_line(max(0.0, wait_until - now))
        except WaitTimeout:
            continue


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise OrchestratorError(f"expected JSON object: {path}")
    return value


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            event = extract_json(line)
            if event is None:
                raise OrchestratorError(f"invalid JSONL at {path}:{line_number}")
            events.append(event)
    return events


def planned_metadata_checks(
    metadata: dict[str, Any],
    resource: str,
    cpu_threads: int | None,
    duty_cycle_percent: int,
    duty_cycle_period_seconds: float,
    gpu_profile_expected: dict[str, Any] | None = None,
) -> dict[str, bool]:
    requested_period_ns = duty_cycle_period_seconds * 1_000_000_000
    actual_period_ns = metadata.get("duty_cycle_period_ns")
    checks = {
        "planned_resource": metadata.get("resource") == resource,
        "planned_cpu_threads": (
            metadata.get("cpu_threads") == cpu_threads
            if resource == "CPU" else metadata.get("cpu_threads") is None
        ),
        "planned_duty_cycle": (
            metadata.get("requested_duty_cycle_percent") == duty_cycle_percent
        ),
        "planned_duty_period": (
            isinstance(actual_period_ns, int)
            and actual_period_ns > 0
            and abs(actual_period_ns - requested_period_ns)
            <= max(1.0, requested_period_ns * 1e-6)
        ),
    }
    if resource == "GPU" and gpu_profile_expected is not None:
        checks["planned_gpu_delegate_profile"] = (
            metadata.get("gpu_delegate_profile") == gpu_profile_expected
        )
    return checks


def validate_result(
    run_dir: Path,
    resource: str,
    cpu_threads: int | None,
    duration_s: int,
    warmup: int,
    run_id: str,
    command_id: str,
    mode: str,
    duty_cycle_percent: int = 100,
    duty_cycle_period_seconds: float = 10.0,
    expected_accuracy_preflight: dict[str, Any] | None = None,
    expected_gpu_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    summary = load_json(run_dir / "merged" / "summary.json")
    capture = load_json(run_dir / "metadata.json")
    runner_paths = sorted((run_dir / "gpu").glob(f"gpu-events-{run_id}-*.jsonl"))
    if len(runner_paths) != 1:
        raise OrchestratorError(
            f"expected exactly one runner session for {run_id}, found {len(runner_paths)}"
        )
    events = load_jsonl(runner_paths[0])
    metadata = next((event for event in events if event.get("event") == "run_metadata"), None)
    footer = next((event for event in reversed(events) if event.get("event") == "file_summary"), None)
    if metadata is None or footer is None:
        raise OrchestratorError("runner file lacks run_metadata or file_summary")
    coverage = summary.get("thermal_coverage")
    coverage_pass = isinstance(coverage, dict) and coverage.get("passes_formal_requirement") is True
    actual_load_ns = metadata.get("actual_load_duration_ns")
    actual_active_ns = metadata.get("actual_active_duration_ns")
    actual_idle_ns = metadata.get("actual_idle_duration_ns")
    duty_time_explained = (
        isinstance(actual_load_ns, int)
        and isinstance(actual_active_ns, int)
        and isinstance(actual_idle_ns, int)
        and actual_active_ns >= 0
        and actual_idle_ns >= 0
        and actual_active_ns + actual_idle_ns == actual_load_ns
    )
    achieved = metadata.get("achieved_duty_cycle_percent")
    achieved_explained = (
        duty_time_explained
        and isinstance(achieved, (int, float))
        and abs(
            float(achieved) - (
                float(actual_active_ns) * 100.0 / float(actual_load_ns)
                if actual_load_ns else 0.0
            )
        ) <= 1e-9
    )
    accuracy = metadata.get("accuracy_preflight")
    energy = metadata.get("energy_measurement")
    requested_period_ns = duty_cycle_period_seconds * 1_000_000_000
    period_value = metadata.get("duty_cycle_period_ns")
    planned_checks = planned_metadata_checks(
        metadata, resource, cpu_threads, duty_cycle_percent, duty_cycle_period_seconds,
        expected_gpu_profile,
    )
    duty_period_matches = planned_checks["planned_duty_period"]
    expected_period_ns = period_value if duty_period_matches else max(
        1, int(requested_period_ns + 0.5)
    )
    active_window_ns = (
        expected_period_ns
        if duty_cycle_percent == 100
        else max(1, expected_period_ns * duty_cycle_percent // 100)
    )
    target_duration_ns = duration_s * 1_000_000_000
    expected_target_active_ns = (
        target_duration_ns
        if duty_cycle_percent == 100
        else (
            (target_duration_ns // expected_period_ns) * active_window_ns
            + min(target_duration_ns % expected_period_ns, active_window_ns)
        )
    )
    checks = {
        "capture_clean": capture.get("capture_error") is None,
        "run_id": metadata.get("run_id") == run_id == summary.get("run_id"),
        "command_id": metadata.get("command_id") == command_id,
        "expected_run_id": metadata.get("expected_run_id") == run_id,
        "resource": planned_checks["planned_resource"] and summary.get("resource") == resource,
        "cpu_threads": planned_checks["planned_cpu_threads"],
        "cpu_affinity_none": metadata.get("cpu_affinity") == "NONE",
        "auto_start": metadata.get("auto_start") is True,
        "basic_capture": str(metadata.get("experiment_mode", "")).upper() == "BASIC",
        "duration_mode": metadata.get("limit_mode") == "DURATION",
        "requested_duration": metadata.get("requested_duration_s") == duration_s,
        "target_duration": metadata.get("target_duration_ns") == duration_s * 1_000_000_000,
        "warmup": metadata.get("warmup_count") == warmup,
        "duration_complete": metadata.get("termination_reason") == "duration_complete",
        "runner_valid": metadata.get("experiment_valid") is True,
        "pilot_safety": metadata.get("pilot_safety_pass") is True,
        "file_summary": footer.get("status") == "ok",
        "run_envelope": summary.get("run_envelope_validation") == "pass",
        "single_runner_session": summary.get("runner_session_count") == 1,
        "thermal_coverage": coverage_pass,
        "inference_present": int(metadata.get("completed_inference_count") or 0) > 0,
        "duty_request": planned_checks["planned_duty_cycle"],
        "duty_period": duty_period_matches,
        "duty_target_active": (
            metadata.get("target_active_duration_ns") == expected_target_active_ns
        ),
        "duty_time_explained": duty_time_explained,
        "duty_achieved_explained": achieved_explained,
        "duty_idle_semantics": (
            actual_idle_ns == 0
            if duty_cycle_percent == 100
            else isinstance(actual_idle_ns, int) and actual_idle_ns > 0
        ),
        "duty_footer_matches": all(
            footer.get(key) == metadata.get(key)
            for key in (
                "requested_duty_cycle_percent",
                "duty_cycle_period_ns",
                "target_active_duration_ns",
                "actual_active_duration_ns",
                "actual_idle_duration_ns",
                "achieved_duty_cycle_percent",
                "completed_duty_cycle_count",
                "duty_cycle_active_overrun_ns",
                "completed_inference_count",
                "termination_reason",
            )
        ),
        "runner_accuracy_not_misrepresented": (
            isinstance(accuracy, dict)
            and accuracy.get("status") == "not_run"
            and (
                accuracy.get("validation_scope") == "timed_run_does_not_execute_preflight"
                or accuracy.get("deterministic_input_count") == 0
            )
        ),
        "experiment_accuracy_attached": (
            summary.get("accuracy_preflight") == expected_accuracy_preflight
            if expected_accuracy_preflight is not None else True
        ),
        "preflight_timed_gpu_profile_match": (
            expected_accuracy_preflight.get("cache_provenance", {}).get(
                "gpu_delegate_profile"
            ) == expected_gpu_profile
            if resource == "GPU"
            and isinstance(expected_accuracy_preflight, dict)
            and expected_gpu_profile is not None
            else True
        ),
        "gpu_profile_consistency": (
            isinstance(summary.get("profile_consistency_validation"), dict)
            and summary["profile_consistency_validation"].get("valid") is True
            if resource == "GPU"
            else summary.get("gpu_delegate_profile") is None
            and (
                not isinstance(summary.get("profile_consistency_validation"), dict)
                or summary["profile_consistency_validation"].get("status")
                == "not_applicable"
            )
        ),
        "energy_not_misrepresented": (
            isinstance(energy, dict)
            and energy.get("status") == "raw_unverified"
            and energy.get("current_unit_verified") is False
            and energy.get("charge_counter_unit_verified") is False
            and energy.get("calculation_performed") is False
        ),
    }
    if mode == "formal":
        checks["formal_energy_eligible"] = metadata.get("formal_energy_eligible") is True
        if resource == "GPU":
            checks["formal_gpu_valid"] = summary.get("formal_gpu_valid") is True
        if resource == "NPU":
            checks["formal_npu_valid"] = summary.get("formal_npu_valid") is True
    failed = [name for name, passed in checks.items() if not passed]
    return {
        "valid": not failed,
        "checks": checks,
        "failed_checks": failed,
        "summary_path": str(run_dir / "merged" / "summary.json"),
        "runner_file": str(runner_paths[0]),
        "summary": summary,
    }


def attach_accuracy_to_analyzer_summary(
    run_dir: Path, accuracy_preflight: dict[str, Any]
) -> None:
    summary_path = run_dir / "merged" / "summary.json"
    summary = load_json(summary_path)
    summary["accuracy_preflight"] = accuracy_preflight
    summary["accuracy_scope"] = "experiment_level_preflight_not_task_accuracy"
    atomic_write_json(summary_path, summary)


class ExperimentOrchestrator:
    def __init__(self, args: argparse.Namespace, manifest: dict[str, Any], path: Path) -> None:
        self.args = args
        self.manifest = manifest
        self.manifest_path = path
        self.logger_path = Path(args.logger).resolve()
        self.runs_root = path.parent / "runs"
        self.adb: AdbClient | None = None

    def save(self) -> None:
        self.manifest["updated_utc"] = utc_now()
        atomic_write_json(self.manifest_path, self.manifest)

    def step(self, slot: dict[str, Any], name: str, **details: Any) -> None:
        slot["steps"].append({"utc": utc_now(), "name": name, **details})
        self.save()

    def _logger_command(self, command: str, *extra: str) -> list[str]:
        assert self.adb is not None and self.adb.serial is not None
        return [
            sys.executable, str(self.logger_path),
            "--adb", self.adb.adb, "--serial", self.adb.serial,
            command, *extra,
        ]

    @staticmethod
    def _run_host(command: list[str], timeout: float) -> subprocess.CompletedProcess[str]:
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as error:
            raise OrchestratorError(f"host command timed out: {command}") from error
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip() or "no output"
            raise OrchestratorError(
                f"host command failed rc={result.returncode}: {command}; {detail[:1200]}"
            )
        return result

    def connect(self) -> None:
        probe = AdbClient(self.args.adb)
        result = probe.run(["devices", "-l"], timeout=15)
        devices = parse_adb_devices(result.stdout)
        serial = select_device(devices, self.args.serial)
        self.adb = AdbClient(self.args.adb, serial)
        model = self.adb.run(["shell", "getprop", "ro.product.model"], timeout=10).stdout.strip()
        fingerprint = self.adb.run(
            ["shell", "getprop", "ro.build.fingerprint"], timeout=10
        ).stdout.strip()
        self.manifest["device"] = {
            "serial": serial,
            "model": model,
            "fingerprint": fingerprint,
        }
        self.save()

    def safety_check(self) -> tuple[SafetySnapshot, SafetyEvaluation]:
        assert self.adb is not None
        battery = self.adb.run(["shell", "dumpsys", "battery"], timeout=15).stdout
        thermal = self.adb.run(["shell", "dumpsys", "thermalservice"], timeout=15).stdout
        snapshot = parse_safety_snapshot(battery, thermal)
        return snapshot, evaluate_safety(snapshot, self.args.mode)

    @staticmethod
    def _validate_accuracy_remote_path(path: Any, command_id: str, binary: bool) -> str:
        if not isinstance(path, str):
            raise OrchestratorError("accuracy terminal event lacks artifact path")
        normalized = path.replace("\\", "/")
        expected_name = (
            f"accuracy-outputs-{command_id}-v1.bin"
            if binary else f"accuracy-preflight-{command_id}.jsonl"
        )
        expected_suffix = (
            f"/Android/data/{RUNNER_PACKAGE}/files/accuracy-preflight/{expected_name}"
        )
        if not normalized.endswith(expected_suffix):
            raise OrchestratorError(f"unexpected accuracy artifact path: {path}")
        return path

    def _pull_accuracy_artifact(self, remote: str, final_path: Path) -> None:
        assert self.adb is not None
        if final_path.exists():
            raise OrchestratorError(f"accuracy artifact already exists: {final_path}")
        final_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = final_path.with_name(f".{final_path.name}.{uuid.uuid4()}.tmp")
        try:
            result = self.adb.run(["pull", remote, str(temporary)], timeout=120, check=False)
            if result.returncode != 0:
                raise OrchestratorError(
                    f"accuracy artifact pull failed rc={result.returncode}: "
                    f"{_adb_failure_detail(result)}; remote={remote}"
                )
            if not temporary.is_file() or temporary.stat().st_size <= 0:
                raise OrchestratorError(
                    f"accuracy artifact pull produced no non-empty file; remote={remote}"
                )
            os.replace(temporary, final_path)
        finally:
            temporary.unlink(missing_ok=True)

    def _run_accuracy_check(
        self,
        check_type: str,
        representative: dict[str, Any] | None = None,
        remote_tensor_set_path: str | None = None,
    ) -> dict[str, Any]:
        assert self.adb is not None
        policy = effective_accuracy_policy(self.args)
        device = self.manifest.get("device") or {}
        expected = accuracy_expected_provenance(
            self.args, str(device.get("fingerprint") or ""), check_type, representative
        )
        command_id = str(uuid.uuid4())
        artifact_dir = self.manifest_path.parent / "accuracy_preflight"
        log_path = artifact_dir / f"delegate-log-{command_id}.txt"
        jsonl_path = artifact_dir / f"accuracy-preflight-{command_id}.jsonl"
        binary_path = artifact_dir / f"accuracy-outputs-{command_id}-v1.bin"
        monitor: ProcessLines | None = None
        self.manifest["accuracy_preflight_active"] = {
            "status": "running",
            "validation_scope": check_type,
            "command_id": command_id,
            "started_utc": utc_now(),
            "provenance": expected,
            "provenance_sha256": canonical_sha256(expected),
        }
        self.save()
        try:
            snapshot, safety = self.safety_check()
            self.manifest["accuracy_preflight_active"]["preflight_safety"] = {
                "snapshot": asdict(snapshot), "evaluation": asdict(safety)
            }
            if not safety.pilot_safety_pass:
                raise OrchestratorError(
                    "accuracy preflight safety rejected: " + ",".join(safety.reasons)
                )
            self.adb.run(["shell", "am", "force-stop", RUNNER_PACKAGE], timeout=20)
            if representative is not None:
                assert remote_tensor_set_path is not None
                self.adb.run([
                    "shell", "mkdir", "-p",
                    f"/sdcard/Android/data/{RUNNER_PACKAGE}/files/accuracy-preflight",
                ], timeout=20)
                push = self.adb.run([
                    "push", str(Path(representative["path"])), remote_tensor_set_path,
                ], timeout=180, check=False)
                if push.returncode != 0:
                    raise OrchestratorError(
                        f"representative tensor-set push failed rc={push.returncode}: "
                        f"{_adb_failure_detail(push)}"
                    )
            self.adb.run(["logcat", "-c"], timeout=15)
            monitor = ProcessLines(
                self.adb.popen([
                    "logcat", "-v", "raw", "D1ACC:I", "tflite:I", "TfLite:I", "*:S"
                ]),
                "accuracy_preflight_logcat",
            )
            self.adb.run(
                accuracy_preflight_intent_arguments(
                    command_id,
                    expected["input_count"],
                    self.args.accuracy_seed,
                    self.args.accuracy_cpu_threads,
                    self.args.accuracy_atol,
                    self.args.accuracy_rtol,
                    self.args.accuracy_relative_epsilon,
                    check_type,
                    self.args.gpu_profile,
                    remote_tensor_set_path,
                    representative["container_sha256"] if representative else None,
                    representative["preprocessing_configuration_sha256"]
                    if representative else None,
                ),
                timeout=30,
            )
            terminal = monitor.wait_for_event(
                lambda event: (
                    event.get("command_id") == command_id
                    and event.get("event") in {
                        "accuracy_preflight_complete", "accuracy_preflight_error"
                    }
                ),
                self.args.accuracy_timeout_seconds,
                "accuracy preflight terminal event",
            )
            raw_log = "\n".join(monitor.lines) + "\n"
            atomic_write_text(log_path, raw_log)
            if terminal.get("event") == "accuracy_preflight_error":
                raise OrchestratorError(
                    f"runner accuracy preflight failed: {terminal.get('error') or terminal}"
                )
            remote_jsonl = self._validate_accuracy_remote_path(
                terminal.get("artifact_path"), command_id, False
            )
            remote_binary = self._validate_accuracy_remote_path(
                terminal.get("binary_artifact_path"), command_id, True
            )
            self._pull_accuracy_artifact(remote_jsonl, jsonl_path)
            self._pull_accuracy_artifact(remote_binary, binary_path)
            runner = load_accuracy_runner_artifact(jsonl_path)
            binary_record = runner["metadata"].get("binary_artifact")
            if not isinstance(binary_record, dict):
                raise OrchestratorError("accuracy JSONL lacks binary artifact metadata")
            binary_validation = validate_accuracy_binary(
                binary_path,
                str(binary_record.get("sha256") or ""),
                expected["input_count"],
                ACCURACY_OUTPUT_SHAPE[1],
                expected["tolerance"],
            )
            result = finalize_accuracy_preflight(
                runner, load_delegate_evidence(raw_log), expected, command_id,
                binary_validation,
            )
            result.update({
                "policy": policy,
                "command_id": command_id,
                "completed_utc": utc_now(),
                "runner_artifact_path": str(jsonl_path.relative_to(self.manifest_path.parent)),
                "runner_artifact_sha256": sha256_file(jsonl_path),
                "binary_artifact_path": str(binary_path.relative_to(self.manifest_path.parent)),
                "binary_artifact_sha256": sha256_file(binary_path),
                "delegate_log_path": str(log_path.relative_to(self.manifest_path.parent)),
                "delegate_log_sha256": sha256_file(log_path),
                "remote_tensor_set_path": remote_tensor_set_path,
            })
            detail_path = artifact_dir / f"accuracy-result-{command_id}.json"
            if detail_path.exists():
                raise OrchestratorError(f"accuracy result already exists: {detail_path}")
            atomic_write_json(detail_path, result)
            result["artifact_path"] = str(detail_path.relative_to(self.manifest_path.parent))
            result["artifact_sha256"] = sha256_file(detail_path)
            self.manifest.pop("accuracy_preflight_active", None)
            self.save()
            return result
        except Exception as error:
            if monitor is not None and not log_path.exists():
                atomic_write_text(log_path, "\n".join(monitor.lines) + "\n")
            result = {
                "validation_scope": check_type,
                "status": "error",
                "command_id": command_id,
                "completed_utc": utc_now(),
                "provenance": expected,
                "provenance_sha256": canonical_sha256(expected),
                "failure_reasons": [f"{error.__class__.__name__}: {error}"],
                "delegate_log_path": (
                    str(log_path.relative_to(self.manifest_path.parent))
                    if log_path.exists() else None
                ),
            }
            self.manifest.pop("accuracy_preflight_active", None)
            self.save()
            return result
        finally:
            if monitor is not None:
                monitor.terminate()
            try:
                self.adb.run(
                    ["shell", "am", "force-stop", RUNNER_PACKAGE],
                    timeout=20,
                    check=False,
                )
            except Exception as cleanup_error:
                self.manifest.setdefault("accuracy_preflight_cleanup_errors", []).append({
                    "utc": utc_now(), "error": str(cleanup_error)
                })
                self.save()

    def ensure_accuracy_preflight(self) -> dict[str, Any]:
        """Run/cache the three explicitly separated methodology checks."""
        policy = effective_accuracy_policy(self.args)
        scope = effective_validation_scope(self.args)
        device = self.manifest.get("device") or {}
        fingerprint = str(device.get("fingerprint") or "")
        representative: dict[str, Any] | None = None
        tensor_path = getattr(self.args, "representative_tensor_set", None)
        if tensor_path is not None:
            representative = validate_representative_tensor_set(Path(tensor_path))
            representative["path"] = str(Path(tensor_path).resolve())

        cache_provenance = accuracy_cache_provenance(
            self.args, fingerprint, representative
        )
        cache_key = canonical_sha256(cache_provenance)
        previous = self.manifest.get("accuracy_preflight")
        if can_reuse_accuracy_validation(
            previous, cache_key, self.manifest_path.parent
        ):
            reused = dict(previous)
            reused["resume_reused"] = True
            reused["reuse_verified_utc"] = utc_now()
            self.manifest["accuracy_preflight"] = reused
            self.manifest.setdefault("provenance", {})["accuracy_preflight"] = reused
            self.save()
            return reused

        if isinstance(previous, dict) and previous.get("status") != "not_run":
            self.manifest.setdefault("accuracy_preflight_history", []).append(previous)

        not_run_synthetic = {
            "status": "not_run",
            "failure_reasons": [],
            "note": "synthetic numerical check explicitly disabled",
        }
        if policy == "off":
            result = compose_accuracy_validation(scope, policy, not_run_synthetic)
        else:
            synthetic = self._run_accuracy_check("synthetic")
            representative_result: dict[str, Any] | None = None
            task_result: dict[str, Any] | None = None
            if representative is not None and synthetic.get("status") == "passed":
                remote_path = (
                    f"/sdcard/Android/data/{RUNNER_PACKAGE}/files/accuracy-preflight/"
                    f"representative-{representative['container_sha256']}.d1tset"
                )
                representative_result = self._run_accuracy_check(
                    "representative", representative, remote_path
                )
                task = representative_result.pop("task_accuracy_check", None)
                if isinstance(task, dict):
                    task_result = task
            result = compose_accuracy_validation(
                scope, policy, synthetic, representative_result, task_result
            )

        result.update({
            "cache_key_sha256": cache_key,
            "cache_provenance": cache_provenance,
            "completed_utc": utc_now(),
            "resume_reused": False,
        })
        self.manifest["accuracy_preflight"] = result
        self.manifest.setdefault("provenance", {})["accuracy_preflight"] = result
        self.save()
        return result

    def ensure_npu_quality_preflight(self) -> dict[str, Any]:
        """Run the npu-runner quality gate once per experiment (mirror of ensure_accuracy_preflight)."""
        config = self.manifest["config"].get("npu") or npu_config(self.args)
        gate_config = config["quality_gate"]
        existing = self.manifest.get("npu_quality_preflight")
        if (
            isinstance(existing, dict)
            and existing.get("status") == "passed"
            and existing.get("candidate_model") == config["model_asset"]
            and existing.get("input_spec") == gate_config["input_spec"]
        ):
            return existing
        policy = effective_accuracy_policy(self.args)
        if policy == "off":
            result = {"status": "not_run", "policy": "off", "failure_reasons": []}
            self.manifest["npu_quality_preflight"] = result
            self.save()
            return result
        assert self.adb is not None
        run_id = f"npuq-{uuid.uuid4()}"
        reference_asset = gate_config["reference"].split(":", 1)[1]
        self.adb.run(["shell", "am", "force-stop", NPU_RUNNER_PACKAGE], timeout=20, check=False)
        self.adb.run(
            npu_quality_intent_arguments(
                run_id, config["model_asset"], reference_asset, gate_config["input_spec"],
                gate_config["n"],
            ),
            timeout=30,
        )
        summary: dict[str, Any] | None = None
        deadline = time.monotonic() + NPU_QUALITY_TIMEOUT_SECONDS
        while summary is None and time.monotonic() < deadline:
            time.sleep(NPU_QUALITY_POLL_SECONDS)
            fetched = self.adb.run(
                npu_quality_summary_arguments(run_id), timeout=20, check=False
            )
            if fetched.returncode == 0 and fetched.stdout.strip():
                try:
                    value = json.loads(fetched.stdout)
                except json.JSONDecodeError:
                    continue
                summary = value if isinstance(value, dict) else None
        self.adb.run(["shell", "am", "force-stop", NPU_RUNNER_PACKAGE], timeout=20, check=False)
        if summary is None:
            result = {
                "status": "failed", "failure_reasons": ["summary_timeout"], "run_id": run_id,
                "candidate_model": config["model_asset"], "input_spec": gate_config["input_spec"],
                "evaluated_utc": utc_now(),
            }
        else:
            result = evaluate_npu_quality_summary(
                summary, run_id, config["model_asset"], gate_config["n"],
            )
        result["policy"] = policy
        self.manifest["npu_quality_preflight"] = result
        self.save()
        return result

    def thermal_conditioning(
        self,
        slot: dict[str, Any],
        *,
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> dict[str, Any]:
        assert self.adb is not None
        policy = self.args.start_policy
        result: dict[str, Any] = {
            "policy": policy,
            "status": "not_required" if policy == "safety" else "sampling",
            "clock_domain": "host_monotonic_s",
            "android_mono_ns_available": False,
            "raw_samples": [],
            "evaluations": [],
            "limits": {
                "window_seconds": self.args.stability_window_seconds,
                "sample_interval_seconds": self.args.stability_sample_interval_seconds,
                "timeout_seconds": self.args.stability_timeout_seconds,
                "max_range_c": self.args.stability_max_range_c,
                "max_abs_slope_c_per_minute": (
                    self.args.stability_max_slope_c_per_minute
                ),
                "matched_tolerance_c": self.args.matched_tolerance_c,
            },
        }
        slot["thermal_conditioning"] = result
        if policy == "safety":
            return result
        started = monotonic()
        deadline = started + self.args.stability_timeout_seconds
        while True:
            sample_started = monotonic()
            response = self.adb.run(
                ["shell", "dumpsys", "thermalservice"], timeout=15
            )
            try:
                vector = parse_hal_temperature_vector(response.stdout)
            except ValueError as error:
                result["status"] = "sensor_error"
                result["error"] = str(error)
                result["failed_host_monotonic_s"] = monotonic()
                self.save()
                raise OrchestratorError(f"thermal conditioning sensor error: {error}") from error
            sample = {
                "captured_utc": utc_now(),
                "host_monotonic_s": sample_started,
                "android_mono_ns": None,
                "temperatures_c": vector,
            }
            result["raw_samples"].append(sample)
            evaluation = evaluate_thermal_stability(
                result["raw_samples"],
                self.args.stability_window_seconds,
                self.args.stability_max_range_c,
                self.args.stability_max_slope_c_per_minute,
            )
            evaluation["evaluated_host_monotonic_s"] = monotonic()
            result["evaluations"].append(evaluation)
            if evaluation["stable"]:
                match: dict[str, Any] | None = None
                if policy == "matched":
                    reference_vector = validated_reference_vector(self.manifest)
                    reference_created = reference_vector is None
                    if reference_vector is None:
                        earlier_attempt_exists = any(
                            candidate.get("slot_id") != slot.get("slot_id")
                            and int(candidate.get("attempts") or 0) > 0
                            for candidate in self.manifest.get("runs", [])
                        )
                        if earlier_attempt_exists:
                            raise OrchestratorError(
                                "shared thermal_conditioning_reference is missing after "
                                "an earlier slot; refusing to recreate it"
                            )
                        reference_record = {
                            "created_utc": utc_now(),
                            "source_slot_id": slot.get("slot_id"),
                            "temperatures_c": dict(vector),
                            "definition": (
                                "first stable matched-start vector; tolerance control only"
                            ),
                        }
                        self.manifest["thermal_conditioning_reference"] = reference_record
                        reference_vector = dict(vector)
                    match = evaluate_reference_match(
                        vector,
                        reference_vector,
                        self.args.matched_tolerance_c,
                    )
                    result["reference_evaluation"] = match
                    if not match["matched"]:
                        self.save()
                    else:
                        result["reference_created"] = reference_created
                if policy == "stable" or (match is not None and match["matched"]):
                    result["status"] = "passed"
                    result["actual_start_vector_c"] = dict(vector)
                    result["completed_host_monotonic_s"] = monotonic()
                    self.save()
                    return result
            self.save()
            now = monotonic()
            if now >= deadline:
                result["status"] = "timeout"
                result["timeout_host_monotonic_s"] = now
                result["last_evaluation"] = evaluation
                self.save()
                raise WaitTimeout(
                    f"thermal conditioning {policy} timed out after "
                    f"{self.args.stability_timeout_seconds:.1f}s"
                )
            sleep(min(self.args.stability_sample_interval_seconds, deadline - now))

    def runtime_safety_snapshot(self) -> SafetySnapshot:
        snapshot, _ = self.safety_check()
        return snapshot

    def _wait_run_stop(
        self,
        monitor: ProcessLines,
        logger: ProcessLines,
        run_id: str,
        timeout: float,
    ) -> dict[str, Any]:
        try:
            return monitor.wait_for_event(
                lambda event: (
                    event.get("source") == "d1check"
                    and event.get("event") == "run_stop"
                    and event.get("run_id") == run_id
                    and event.get("status") == "ok"
                ),
                timeout,
                f"run_stop for {run_id}",
            )
        except WaitTimeout as error:
            logger_code = logger.process.poll()
            if logger_code not in (None, 0):
                raise OrchestratorError(
                    f"d1_logger exited abnormally rc={logger_code} before run_stop; "
                    f"tail={list(logger.lines)[-20:]}"
                ) from error
            raise

    def _record_emergency_abort(
        self, slot: dict[str, Any], error: EmergencyAbort
    ) -> None:
        assert self.adb is not None
        slot["runtime_safety"]["abort"] = {
            "source": error.source,
            "stage": error.stage,
            "reasons": list(error.reasons),
            "sample": error.sample,
        }
        try:
            emergency_stop = self.adb.run(
                ["shell", "am", "force-stop", RUNNER_PACKAGE],
                timeout=20,
                check=False,
            )
            self.step(
                slot,
                "emergency_runner_force_stop",
                status="ok" if emergency_stop.returncode == 0 else "error",
                returncode=emergency_stop.returncode,
                error=(
                    None if emergency_stop.returncode == 0
                    else _adb_failure_detail(emergency_stop)
                ),
            )
        except Exception as stop_error:
            slot["runtime_safety"]["runner_force_stop_error"] = str(stop_error)
            try:
                self.step(
                    slot,
                    "emergency_runner_force_stop",
                    status="error",
                    error=str(stop_error),
                )
            except Exception:
                pass

    def _failure_cleanup(
        self,
        slot: dict[str, Any],
        run_id: str | None,
        run_stopped: bool,
        monitor: ProcessLines | None,
        logger: ProcessLines | None,
    ) -> list[str]:
        assert self.adb is not None
        cleanup_errors: list[str] = []

        def record(name: str, **details: Any) -> None:
            try:
                self.step(slot, name, **details)
            except Exception as error:
                cleanup_errors.append(f"manifest step {name}: {error}")

        confirmed = run_stopped
        stop_event = slot.get("run_stop_event")
        activity_error: str | None = None
        if run_id is None:
            record(
                "failure_cleanup_activity_stop",
                status="skipped",
                attempted=False,
                reason="run_not_started",
            )
        elif confirmed:
            record(
                "failure_cleanup_activity_stop",
                status="skipped",
                attempted=False,
                reason="run_already_stopped",
            )
        else:
            try:
                activity = self.adb.run(stop_run_arguments(), timeout=20, check=False)
                activity_error = None if activity.returncode == 0 else _adb_failure_detail(activity)
                record(
                    "failure_cleanup_activity_stop",
                    status="ok" if activity.returncode == 0 else "error",
                    attempted=True,
                    returncode=activity.returncode,
                    error=activity_error,
                )
                if activity.returncode == 0 and monitor is not None and logger is not None:
                    try:
                        stop_event = self._wait_run_stop(monitor, logger, run_id, 5)
                        confirmed = True
                    except Exception as error:
                        activity_error = str(error)
            except Exception as error:
                activity_error = str(error)
                cleanup_errors.append(f"Activity STOP: {error}")
                record(
                    "failure_cleanup_activity_stop",
                    status="error",
                    attempted=True,
                    error=str(error),
                )

        direct_used = run_id is not None and not confirmed
        if not direct_used:
            record(
                "failure_cleanup_direct_service_stop",
                status="skipped",
                used=False,
                reason="run_not_started_or_already_stopped",
            )
        else:
            try:
                direct = self.adb.run(direct_stop_arguments(), timeout=20, check=False)
                record(
                    "failure_cleanup_direct_service_stop",
                    status="ok" if direct.returncode == 0 else "error",
                    used=True,
                    returncode=direct.returncode,
                    error=None if direct.returncode == 0 else _adb_failure_detail(direct),
                )
                if direct.returncode != 0:
                    cleanup_errors.append(
                        f"direct service STOP rc={direct.returncode}: {_adb_failure_detail(direct)}"
                    )
                elif monitor is not None and logger is not None:
                    try:
                        stop_event = self._wait_run_stop(monitor, logger, run_id, 5)
                        confirmed = True
                    except Exception as error:
                        cleanup_errors.append(f"run_stop after direct STOP: {error}")
            except Exception as error:
                cleanup_errors.append(f"direct service STOP: {error}")
                record(
                    "failure_cleanup_direct_service_stop",
                    status="error",
                    used=True,
                    error=str(error),
                )

        slot["stop_recovery_used"] = bool(slot.get("stop_recovery_used") or direct_used)
        slot["activity_stop_error"] = activity_error or slot.get("activity_stop_error")
        if stop_event is not None:
            slot["run_stop_event"] = stop_event
        record(
            "failure_cleanup_run_stop_confirmation",
            status="ok" if confirmed else "unconfirmed",
            confirmed=confirmed,
            run_id=run_id,
        )

        if logger is None:
            record(
                "failure_cleanup_logger",
                status="skipped",
                action="not_started",
            )
        else:
            initial_code = logger.process.poll()
            forced = initial_code is None
            try:
                if initial_code is None and confirmed:
                    try:
                        initial_code = logger.process.wait(timeout=10)
                        forced = False
                    except subprocess.TimeoutExpired:
                        pass
                if logger.process.poll() is None:
                    logger.terminate()
                final_code = logger.process.poll()
                slot["logger_cleanup_action"] = "forced_termination" if forced else "exited"
                if not forced and final_code != 0:
                    cleanup_errors.append(f"logger exited abnormally rc={final_code}")
                record(
                    "failure_cleanup_logger",
                    status=(
                        "forced" if forced else "ok" if final_code == 0 else "error"
                    ),
                    action=slot["logger_cleanup_action"],
                    initial_returncode=initial_code,
                    final_returncode=final_code,
                )
            except Exception as error:
                cleanup_errors.append(f"logger cleanup: {error}")
                record(
                    "failure_cleanup_logger",
                    status="error",
                    action="termination_failed",
                    error=str(error),
                )

        try:
            runner_stop = self.adb.run(
                ["shell", "am", "force-stop", runner_package_for(slot.get("resource"))],
                timeout=20, check=False,
            )
            if runner_stop.returncode != 0:
                cleanup_errors.append(
                    f"runner force-stop rc={runner_stop.returncode}: "
                    f"{_adb_failure_detail(runner_stop)}"
                )
            record(
                "failure_cleanup_runner_force_stop",
                status="ok" if runner_stop.returncode == 0 else "error",
                returncode=runner_stop.returncode,
                error=None if runner_stop.returncode == 0 else _adb_failure_detail(runner_stop),
            )
        except Exception as error:
            cleanup_errors.append(f"runner force-stop: {error}")
            record(
                "failure_cleanup_runner_force_stop",
                status="error",
                error=str(error),
            )

        local_run_dir = self.runs_root / run_id if run_id else None
        local_runner_files = (
            [str(path) for path in sorted((local_run_dir / "gpu").glob("*.jsonl"))]
            if local_run_dir is not None and (local_run_dir / "gpu").is_dir()
            else []
        )
        remote_artifact = slot.get("remote_runner_path") or (
            f"{remote_runner_directory_for(slot.get('resource'))}/gpu-events-{run_id}-*.jsonl"
            if run_id else None
        )
        slot["failure_artifacts"] = {
            "manifest": str(self.manifest_path),
            "local_run_dir": str(local_run_dir) if local_run_dir else None,
            "local_run_dir_exists": local_run_dir.is_dir() if local_run_dir else False,
            "local_runner_files": local_runner_files,
            "remote_runner_path_or_pattern": remote_artifact,
        }
        record(
            "failure_cleanup_artifacts",
            status="recorded",
            **slot["failure_artifacts"],
        )
        return cleanup_errors

    def run_slot(self, slot: dict[str, Any]) -> None:
        assert self.adb is not None
        slot["status"] = "running"
        slot["attempts"] += 1
        slot["attempt_started_utc"] = utc_now()
        slot["error"] = None
        slot["terminal_event_source"] = None
        slot["terminal_fallback_used"] = False
        slot["remote_runner_path"] = None
        slot["logcat_terminal_missing"] = False
        slot["remote_probe_count"] = 0
        slot["final_remote_probe_used"] = False
        slot["stop_recovery_used"] = None
        cooling_minimum = (
            self.args.post_load_idle_seconds
            if self.args.cooling_policy == "fixed"
            else max(self.args.post_load_idle_seconds, self.args.cooling_min_seconds)
        )
        slot["cooling"] = {
            "policy": self.args.cooling_policy,
            "requested_seconds": self.args.post_load_idle_seconds,
            "requested_minimum_seconds": cooling_minimum,
            "timeout_seconds": self.args.cooling_timeout_seconds,
            "status": (
                "disabled"
                if self.args.cooling_policy == "fixed" and cooling_minimum == 0
                else "pending"
            ),
            "completion_reason": (
                "fixed_zero_seconds"
                if self.args.cooling_policy == "fixed" and cooling_minimum == 0
                else None
            ),
            "started_utc": None,
            "completed_utc": None,
            "host_start_monotonic_s": None,
            "host_end_monotonic_s": None,
            "actual_duration_s": 0.0 if (
                self.args.cooling_policy == "fixed" and cooling_minimum == 0
            ) else None,
            "load_end_android_mono_ns": None,
            "run_stop_android_mono_ns": None,
            "host_clock_domain": "host_monotonic_s",
            "android_clock_domain": "android_elapsed_realtime_mono_ns",
            "raw_temperature_samples": [],
            "stability_evaluations": [],
            "reference_evaluation": None,
            "emergency_result": {"status": "not_triggered"},
        }
        slot["runtime_safety"] = {
            "enabled": self.args.emergency_check_interval_seconds > 0,
            "limits": {
                "check_interval_seconds": self.args.emergency_check_interval_seconds,
                "max_battery_temperature_c": (
                    self.args.emergency_max_battery_temperature_c
                ),
                "max_android_thermal_status": (
                    self.args.emergency_max_android_thermal_status
                ),
                "require_unplugged": True,
                "required_battery_status": 3,
            },
            "telemetry_first": True,
            "observations": [],
        }
        self.save()
        logger: ProcessLines | None = None
        monitor: ProcessLines | None = None
        run_id: str | None = None
        run_stopped = False
        safety_monitor: RuntimeSafetyMonitor | None = None
        try:
            self.adb.run(
                ["shell", "am", "force-stop", runner_package_for(slot["resource"])], timeout=20
            )
            self.step(slot, "runner_force_stop", status="ok")

            initial_activity_stop = self.adb.run(
                stop_run_arguments(), timeout=20, check=False
            )
            initial_direct_stop = self.adb.run(
                direct_stop_arguments(), timeout=20, check=False
            )
            self.step(
                slot,
                "pre_capture_d1_quiesce",
                status="ok" if initial_direct_stop.returncode == 0 else "error",
                activity_returncode=initial_activity_stop.returncode,
                direct_returncode=initial_direct_stop.returncode,
            )
            if initial_direct_stop.returncode != 0:
                detail = (
                    initial_direct_stop.stderr.strip()
                    or initial_direct_stop.stdout.strip()
                    or "no output"
                )
                raise OrchestratorError(f"cannot quiesce D1Check before capture: {detail[:800]}")
            time.sleep(1.0)

            snapshot, safety = self.safety_check()
            slot["safety_preflight"] = safety.to_dict(snapshot)
            self.step(slot, "safety_preflight", status="ok" if safety.mode_safety_pass else "rejected")
            if not safety.mode_safety_pass:
                raise OrchestratorError(
                    "safety preflight rejected: " + ",".join(safety.reasons)
                )

            conditioning = self.thermal_conditioning(slot)
            self.step(
                slot,
                "thermal_conditioning",
                status=conditioning["status"],
                policy=self.args.start_policy,
            )
            if self.args.start_policy != "safety":
                snapshot, safety = self.safety_check()
                slot["safety_after_conditioning"] = safety.to_dict(snapshot)
                self.step(
                    slot,
                    "safety_after_conditioning",
                    status="ok" if safety.mode_safety_pass else "rejected",
                )
                if not safety.mode_safety_pass:
                    raise OrchestratorError(
                        "safety after conditioning rejected: " + ",".join(safety.reasons)
                    )

            self._run_host(self._logger_command("clear"), timeout=30)
            self.step(slot, "logger_clear", status="ok")

            capture_process = subprocess.Popen(
                self._logger_command(
                    "capture", str(self.runs_root),
                    *npu_logger_capture_arguments(slot["resource"]),
                ),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            logger = ProcessLines(capture_process, "d1_logger")
            logger.wait_for_line(
                lambda line: "capture started" in line.lower(),
                20,
                "d1_logger capture started",
            )
            self.step(slot, "logger_capture_started", status="ok")

            monitor = ProcessLines(
                self.adb.popen([
                    "logcat", "-v", "raw", "D1CHECK_EVENT:I", "D1GPU:I", "*:S",
                ]),
                "orchestrator_logcat",
            )
            self.step(slot, "event_monitor_started", status="ok")

            self.adb.run(start_run_arguments(), timeout=20)
            previous_ids = {
                item.get("run_id") for item in self.manifest["runs"] if item.get("run_id")
            }
            run_start = monitor.wait_for_event(
                lambda event: (
                    event.get("source") == "d1check"
                    and event.get("event") == "run_start"
                    and event.get("status") == "ok"
                    and event.get("run_id") not in previous_ids
                ),
                20,
                "new D1Check run_start",
                [logger],
            )
            run_id = str(run_start.get("run_id"))
            try:
                run_id = str(uuid.UUID(run_id))
            except ValueError as error:
                raise OrchestratorError(f"run_start contains invalid UUID: {run_id!r}") from error
            command_id = str(uuid.uuid4())
            slot["run_id"] = run_id
            slot["command_id"] = command_id
            slot["run_start_event"] = run_start
            self.step(slot, "d1_run_started", status="ok", run_id=run_id)

            self.adb.run(
                runner_intent_arguments(
                    slot["resource"], slot["cpu_threads"], self.args.duration,
                    self.args.warmup, run_id, command_id,
                    slot["duty_cycle_percent"],
                    self.args.duty_cycle_period_seconds,
                    self.args.gpu_profile,
                    **npu_runner_intent_kwargs(slot["resource"], self.args),
                ),
                timeout=30,
            )
            self.step(slot, "runner_auto_start_sent", status="ok", command_id=command_id)

            if self.args.emergency_check_interval_seconds > 0:
                safety_monitor = RuntimeSafetyMonitor(
                    self.args.emergency_max_battery_temperature_c,
                    self.args.emergency_max_android_thermal_status,
                )

            def observe_runtime_event(event: dict[str, Any]) -> None:
                if safety_monitor is not None:
                    safety_monitor.observe_event(event)

            def periodic_runtime_check() -> None:
                if safety_monitor is None:
                    return
                try:
                    safety_monitor.check_snapshot(self.runtime_safety_snapshot())
                finally:
                    slot["runtime_safety"]["observations"] = safety_monitor.observations
                    self.save()

            runner_timeout = self.args.duration + 180 + min(self.args.warmup * 2, 3600)
            def remote_probe(final: bool) -> RemoteRunnerProbe:
                slot["terminal_fallback_used"] = True
                slot["logcat_terminal_missing"] = True
                slot["remote_probe_count"] += 1
                slot["final_remote_probe_used"] = final
                result = (
                    probe_remote_runner(self.adb, run_id)
                    if slot["resource"] != "NPU"
                    else probe_remote_runner(self.adb, run_id, NPU_REMOTE_RUNNER_DIRECTORY)
                )
                slot["remote_runner_path"] = result.remote_path
                slot["last_remote_probe_state"] = result.state
                slot["last_remote_probe_detail"] = result.detail
                return result

            terminal = wait_for_runner_terminal(
                run_id,
                lambda timeout: monitor.wait_for_event(
                    lambda event: (
                        observe_runtime_event(event) is None
                        and classify_runner_terminal(event, run_id) is not None
                    ),
                    timeout,
                    f"runner terminal event for {run_id}",
                    [logger],
                ),
                remote_probe,
                BASELINE_SECONDS + self.args.duration + REMOTE_FALLBACK_GRACE_SECONDS,
                runner_timeout,
                periodic_interval_s=self.args.emergency_check_interval_seconds,
                periodic_check=(
                    periodic_runtime_check if safety_monitor is not None else None
                ),
            )
            terminal_kind = terminal.kind
            slot["runner_terminal_event"] = terminal.event
            slot["terminal_event_source"] = terminal.source
            slot["terminal_fallback_used"] = terminal.fallback_used
            slot["remote_runner_path"] = terminal.remote_runner_path
            slot["logcat_terminal_missing"] = terminal.logcat_terminal_missing
            slot["remote_probe_count"] = terminal.remote_probe_count
            slot["final_remote_probe_used"] = terminal.final_remote_probe_used
            self.step(
                slot,
                "runner_terminal_event",
                status=terminal_kind,
                source=terminal.source,
                fallback_used=terminal.fallback_used,
                remote_runner_path=terminal.remote_runner_path,
            )

            cooling_required = (
                self.args.cooling_policy != "fixed" or cooling_minimum > 0
            )
            if terminal_kind == "success" and cooling_required:
                runner_stop = self.adb.run(
                    ["shell", "am", "force-stop", runner_package_for(slot["resource"])],
                    timeout=20,
                    check=False,
                )
                if runner_stop.returncode != 0:
                    raise OrchestratorError(
                        "runner force-stop before cooling failed: "
                        f"{_adb_failure_detail(runner_stop)}"
                    )
                self.step(slot, "runner_stopped_before_cooling", status="ok")
                if safety_monitor is not None:
                    safety_monitor.stage = "cooling"
                cooling = slot["cooling"]
                cooling["status"] = "collecting"
                cooling["started_utc"] = utc_now()
                cooling["host_start_monotonic_s"] = time.monotonic()

                def wait_cooling_log(timeout: float) -> None:
                    monitor.wait_for_line(
                        lambda line: (
                            observe_runtime_event(extract_json(line) or {}) is not None
                        ),
                        timeout,
                        "post-load cooling interval",
                        [logger],
                    )

                if self.args.cooling_policy == "fixed":
                    cooling.update(
                        wait_for_idle_interval(
                            cooling_minimum,
                            wait_cooling_log,
                            periodic_interval_s=self.args.emergency_check_interval_seconds,
                            periodic_check=(
                                periodic_runtime_check if safety_monitor is not None else None
                            ),
                        )
                    )
                    cooling["status"] = "completed"
                    cooling["completion_reason"] = "fixed_duration_elapsed"
                    cooling["completed_utc"] = utc_now()
                else:
                    reference = validated_reference_vector(self.manifest)

                    def get_cooling_vector() -> dict[str, float]:
                        response = self.adb.run(
                            ["shell", "dumpsys", "thermalservice"], timeout=15
                        )
                        return parse_hal_temperature_vector(response.stdout)

                    wait_for_thermal_cooling(
                        cooling,
                        self.args.cooling_policy,
                        cooling_minimum,
                        self.args.cooling_timeout_seconds,
                        self.args.stability_sample_interval_seconds,
                        self.args.stability_window_seconds,
                        self.args.stability_max_range_c,
                        self.args.stability_max_slope_c_per_minute,
                        self.args.matched_tolerance_c,
                        reference,
                        get_cooling_vector,
                        wait_cooling_log,
                        periodic_interval_s=self.args.emergency_check_interval_seconds,
                        periodic_check=(
                            periodic_runtime_check if safety_monitor is not None else None
                        ),
                        on_update=self.save,
                    )
                self.step(
                    slot,
                    "post_load_cooling",
                    status="ok",
                    policy=self.args.cooling_policy,
                    completion_reason=cooling["completion_reason"],
                )

            stop_result = stop_d1_run(
                self.adb,
                lambda timeout: self._wait_run_stop(monitor, logger, run_id, timeout),
                15,
            )
            run_stopped = True
            slot["run_stop_event"] = stop_result["event"]
            slot["stop_recovery_used"] = stop_result["recovery_used"]
            slot["activity_stop_error"] = stop_result["activity_stop_error"]
            self.step(
                slot,
                "d1_run_stopped",
                status="ok",
                recovery_used=stop_result["recovery_used"],
            )

            try:
                logger_code = logger.process.wait(timeout=30)
            except subprocess.TimeoutExpired as error:
                raise OrchestratorError("d1_logger did not exit after run_stop") from error
            if logger_code != 0:
                raise OrchestratorError(
                    f"d1_logger exited abnormally rc={logger_code}; tail={list(logger.lines)[-20:]}"
                )
            self.step(slot, "logger_exited", status="ok", returncode=logger_code)

            if terminal_kind == "failure":
                raise OrchestratorError(
                    f"runner emitted failure event from {terminal.source}: {terminal.event}"
                )

            run_dir = self.runs_root / run_id
            if not run_dir.is_dir():
                raise OrchestratorError(f"logger run directory not found: {run_dir}")
            slot["run_dir"] = str(run_dir)
            self.step(slot, "run_directory_identified", status="ok", path=str(run_dir))

            analysis = self._run_host(
                [sys.executable, str(self.logger_path), "analyze", str(run_dir)],
                timeout=120,
            )
            slot["analyze_stdout"] = analysis.stdout[-4000:]
            self.step(slot, "analysis_completed", status="ok")

            experiment_accuracy = self.manifest.get("accuracy_preflight")
            if not isinstance(experiment_accuracy, dict):
                experiment_accuracy = dict(self.manifest["config"]["accuracy_preflight"])
            attach_accuracy_to_analyzer_summary(run_dir, experiment_accuracy)
            self.step(slot, "accuracy_provenance_attached", status="ok")

            validation = validate_result(
                run_dir, slot["resource"], slot["cpu_threads"],
                self.args.duration, self.args.warmup, run_id, command_id, self.args.mode,
                slot["duty_cycle_percent"], self.args.duty_cycle_period_seconds,
                experiment_accuracy,
                gpu_profile(self.args.gpu_profile),
            )
            slot["validation"] = validation
            summary = validation["summary"]
            slot["cooling"]["load_end_android_mono_ns"] = summary.get(
                "load_end_mono_ns"
            )
            slot["cooling"]["run_stop_android_mono_ns"] = summary.get(
                "run_stop_mono_ns"
            )
            load_end_ns = summary.get("load_end_mono_ns")
            run_stop_ns = summary.get("run_stop_mono_ns")
            if isinstance(load_end_ns, int) and isinstance(run_stop_ns, int):
                slot["cooling"]["android_interval_duration_s"] = (
                    run_stop_ns - load_end_ns
                ) / 1e9
            if not validation["valid"]:
                raise OrchestratorError(
                    "result validation failed: " + ",".join(validation["failed_checks"])
                )
            slot["status"] = "completed"
            slot["completed_utc"] = utc_now()
            self.save()
        except Exception as error:
            if safety_monitor is not None:
                slot["runtime_safety"]["observations"] = safety_monitor.observations
            cooling = slot.get("cooling", {})
            if isinstance(error, EmergencyAbort):
                if cooling.get("status") == "collecting":
                    now = time.monotonic()
                    cooling.update({
                        "status": "emergency_aborted",
                        "completion_reason": "emergency_abort",
                        "completed_utc": utc_now(),
                        "host_end_monotonic_s": now,
                        "actual_duration_s": (
                            now - cooling["host_start_monotonic_s"]
                            if isinstance(
                                cooling.get("host_start_monotonic_s"), (int, float)
                            ) else None
                        ),
                        "emergency_result": {
                            "status": "aborted",
                            "source": error.source,
                            "reasons": list(error.reasons),
                            "sample": error.sample,
                        },
                    })
                self._record_emergency_abort(slot, error)
            elif cooling.get("status") == "collecting":
                now = time.monotonic()
                cooling.update({
                    "status": "failed",
                    "completion_reason": "cooling_error",
                    "completed_utc": utc_now(),
                    "host_end_monotonic_s": now,
                    "actual_duration_s": (
                        now - cooling["host_start_monotonic_s"]
                        if isinstance(
                            cooling.get("host_start_monotonic_s"), (int, float)
                        ) else None
                    ),
                    "error": f"{error.__class__.__name__}: {error}",
                })
            slot["status"] = "failed"
            slot["error"] = f"{error.__class__.__name__}: {error}"
            slot["failed_utc"] = utc_now()
            cleanup_errors: list[str] = []
            try:
                self.step(slot, "failure_detected", status="error", error=slot["error"])
            except Exception as step_error:
                cleanup_errors.append(f"record failure_detected: {step_error}")
            try:
                cleanup_errors.extend(
                    self._failure_cleanup(slot, run_id, run_stopped, monitor, logger)
                )
            except Exception as cleanup_error:
                cleanup_errors.append(f"unexpected cleanup failure: {cleanup_error}")
            slot.setdefault("failures", []).append(
                {
                    "attempt": slot["attempts"],
                    "utc": utc_now(),
                    "run_id": slot.get("run_id"),
                    "command_id": slot.get("command_id"),
                    "run_dir": slot.get("run_dir"),
                    "error": slot["error"],
                    "cleanup_errors": cleanup_errors,
                }
            )
            try:
                self.save()
            except Exception as save_error:
                cleanup_errors.append(f"final failure manifest save: {save_error}")
            raise
        finally:
            if monitor is not None:
                monitor.terminate()
            if logger is not None:
                logger.terminate()

    def run(self) -> int:
        try:
            self.connect()
        except Exception as error:
            self.manifest["status"] = "failed"
            self.manifest["halt_reason"] = f"{error.__class__.__name__}: {error}"
            self.save()
            print(f"experiment halted safely: {error}", file=sys.stderr)
            return 1
        self.manifest["status"] = "running"
        self.manifest["halt_reason"] = None
        self.manifest["started_utc"] = self.manifest.get("started_utc") or utc_now()
        self.save()
        pending_slots = runnable_slots(self.manifest)
        if pending_slots:
            accuracy = self.ensure_accuracy_preflight()
            if not accuracy_policy_allows_slots(
                effective_accuracy_policy(self.args), str(accuracy.get("status"))
            ):
                self.manifest["status"] = "failed"
                self.manifest["halt_reason"] = (
                    "required CPU-GPU output equivalence preflight did not pass: "
                    f"status={accuracy.get('status')} "
                    f"reasons={accuracy.get('failure_reasons')}"
                )
                self.save()
                print(f"experiment halted safely: {self.manifest['halt_reason']}", file=sys.stderr)
                return 1
        if any(str(slot.get("resource", "")).upper() == "NPU" for slot in pending_slots):
            npu_quality = self.ensure_npu_quality_preflight()
            if not accuracy_policy_allows_slots(
                effective_accuracy_policy(self.args), str(npu_quality.get("status"))
            ):
                self.manifest["status"] = "failed"
                self.manifest["halt_reason"] = (
                    "required NPU quality preflight did not pass: "
                    f"status={npu_quality.get('status')} "
                    f"reasons={npu_quality.get('failure_reasons')}"
                )
                self.save()
                print(f"experiment halted safely: {self.manifest['halt_reason']}", file=sys.stderr)
                return 1
        for slot in pending_slots:
            try:
                self.run_slot(slot)
            except Exception as error:
                self.manifest["status"] = "failed"
                self.manifest["halt_reason"] = str(error)
                self.save()
                print(f"experiment halted safely: {error}", file=sys.stderr)
                return 1
        self.manifest["status"] = "completed"
        self.manifest["completed_utc"] = utc_now()
        self.manifest["halt_reason"] = None
        self.save()
        previous_postprocessing = self.manifest.pop("postprocessing", None)
        if isinstance(previous_postprocessing, dict):
            self.manifest.setdefault("postprocessing_history", []).append(
                previous_postprocessing
            )
            self.save()
        try:
            export_thermal_dataset(self.manifest_path.parent)
        except Exception as error:
            self.manifest["postprocessing"] = {
                "kind": "thermal_dataset_export",
                "status": "failed",
                "failed_utc": utc_now(),
                "error": f"{error.__class__.__name__}: {error}",
                "sources_preserved": True,
                "regeneration_command": [
                    sys.executable,
                    str(Path(__file__).with_name("d1_thermal_dataset.py")),
                    "--experiment-dir",
                    str(self.manifest_path.parent),
                ],
            }
            self.save()
            print(
                "experiment completed but thermal dataset export failed; "
                "raw results were preserved. Re-run: "
                + subprocess.list2cmdline(
                    self.manifest["postprocessing"]["regeneration_command"]
                ),
                file=sys.stderr,
            )
            return 1
        return 0


def experiment_config(args: argparse.Namespace) -> dict[str, Any]:
    cpu_thread_levels, duty_cycles = normalized_axes(args)
    config = {
        "mode": args.mode,
        "resources": [resource.upper() for resource in args.resources],
        "cpu_thread_levels": cpu_thread_levels,
        "duty_cycles": duty_cycles,
        "cpu_threads": cpu_thread_levels[0] if len(cpu_thread_levels) == 1 else None,
        "limit_mode": "DURATION",
        "duration_s": args.duration,
        "warmup_count": args.warmup,
        "repeat_per_resource": args.repeat,
        "repeat": args.repeat,
        "seed": args.seed,
        "block_design": {
            "name": BLOCK_DESIGN_NAME,
            "version": BLOCK_DESIGN_VERSION,
            "block_axis": "repetition",
            "randomization": "within_block_seeded_shuffle",
        },
        "runner_experiment_mode": "BASIC",
        "energy_calculation": False,
        "current_raw_policy": "raw_unscaled_unit_unverified",
        "duty_cycle_percent": duty_cycles[0] if len(duty_cycles) == 1 else None,
        "duty_cycle_period_seconds": args.duty_cycle_period_seconds,
        "gpu_delegate_profile": gpu_profile(args.gpu_profile),
        "accuracy_preflight": accuracy_config(args),
        "energy_measurement": {
            "status": "raw_unverified",
            "current_raw_policy": "raw_unscaled_unit_unverified",
            "voltage_available": None,
            "current_unit_verified": False,
            "charge_counter_unit_verified": False,
            "calculation_performed": False,
            "note": "no J or mWh result is produced before unit calibration",
        },
        "thermal_conditioning": {
            "start_policy": args.start_policy,
            "window_seconds": args.stability_window_seconds,
            "sample_interval_seconds": args.stability_sample_interval_seconds,
            "timeout_seconds": args.stability_timeout_seconds,
            "max_range_c": args.stability_max_range_c,
            "max_abs_slope_c_per_minute": args.stability_max_slope_c_per_minute,
            "matched_tolerance_c": args.matched_tolerance_c,
            "source": "dumpsys thermalservice Current temperatures from HAL",
            "sensors": list(THERMAL_SENSOR_NAMES),
            "matched_claim": "tolerance_based_control_not_statistical_equivalence",
        },
        "post_load_idle_seconds": args.post_load_idle_seconds,
        "cooling_policy": {
            "mode": args.cooling_policy,
            "minimum_seconds": args.cooling_min_seconds,
            "timeout_seconds": args.cooling_timeout_seconds,
            "stable_criteria_reused": args.cooling_policy in {"stable", "matched"},
        },
        "emergency_monitor": {
            "enabled": args.emergency_check_interval_seconds > 0,
            "check_interval_seconds": args.emergency_check_interval_seconds,
            "max_battery_temperature_c": args.emergency_max_battery_temperature_c,
            "max_android_thermal_status": args.emergency_max_android_thermal_status,
            "require_unplugged": True,
            "required_battery_status": 3,
            "strategy": "logcat_telemetry_first_with_sparse_dumpsys",
        },
    }
    # Only NPU experiments carry the NPU block, so CPU/GPU configs (and resume checks) are unchanged.
    if "NPU" in config["resources"]:
        config["npu"] = npu_config(args)
    return config


def _legacy_compatible_config(config: dict[str, Any]) -> dict[str, Any]:
    value = dict(config)
    value.setdefault("cpu_thread_levels", [value.get("cpu_threads", DEFAULT_CPU_THREADS)])
    value.setdefault(
        "duty_cycles",
        [value.get("duty_cycle_percent", DEFAULT_DUTY_CYCLE_PERCENT)],
    )
    value.setdefault("repeat", value.get("repeat_per_resource", 1))
    value.setdefault(
        "block_design",
        {
            "name": BLOCK_DESIGN_NAME,
            "version": BLOCK_DESIGN_VERSION,
            "block_axis": "repetition",
            "randomization": "within_block_seeded_shuffle",
        },
    )
    value.setdefault("duty_cycle_percent", 100)
    value.setdefault("duty_cycle_period_seconds", 10.0)
    value.setdefault("gpu_delegate_profile", gpu_profile(DEFAULT_GPU_PROFILE))
    legacy_accuracy = value.get("accuracy_preflight")
    if (
        not isinstance(legacy_accuracy, dict)
        or legacy_accuracy.get("schema_version") != ACCURACY_SCHEMA_VERSION
    ):
        legacy_args = build_parser().parse_args(["--mode", str(value.get("mode", "pilot"))])
        if isinstance(legacy_accuracy, dict):
            legacy_args.accuracy_preflight = legacy_accuracy.get("policy")
            legacy_args.accuracy_input_count = int(
                legacy_accuracy.get("deterministic_input_count")
                or DEFAULT_ACCURACY_INPUT_COUNT
            )
            legacy_args.accuracy_cpu_threads = int(
                legacy_accuracy.get("reference_cpu_threads") or DEFAULT_CPU_THREADS
            )
            tolerance = legacy_accuracy.get("tolerance")
            if isinstance(tolerance, dict):
                legacy_args.accuracy_atol = float(
                    tolerance.get("atol", DEFAULT_ACCURACY_ATOL)
                )
                legacy_args.accuracy_rtol = float(
                    tolerance.get("rtol", DEFAULT_ACCURACY_RTOL)
                )
                legacy_args.accuracy_relative_epsilon = float(
                    tolerance.get(
                        "relative_error_epsilon", DEFAULT_ACCURACY_RELATIVE_EPSILON
                    )
                )
        value["accuracy_preflight"] = accuracy_config(legacy_args)
    value.setdefault(
        "energy_measurement",
        {
            "status": "raw_unverified",
            "current_raw_policy": "raw_unscaled_unit_unverified",
            "voltage_available": None,
            "current_unit_verified": False,
            "charge_counter_unit_verified": False,
            "calculation_performed": False,
            "note": "no J or mWh result is produced before unit calibration",
        },
    )
    value.setdefault(
        "thermal_conditioning",
        {
            "start_policy": "safety",
            "window_seconds": 60.0,
            "sample_interval_seconds": 5.0,
            "timeout_seconds": 900.0,
            "max_range_c": 0.5,
            "max_abs_slope_c_per_minute": 0.2,
            "matched_tolerance_c": 0.5,
            "source": "dumpsys thermalservice Current temperatures from HAL",
            "sensors": list(THERMAL_SENSOR_NAMES),
            "matched_claim": "tolerance_based_control_not_statistical_equivalence",
        },
    )
    value.setdefault("post_load_idle_seconds", 0.0)
    value.setdefault(
        "cooling_policy",
        {
            "mode": "fixed",
            "minimum_seconds": 0.0,
            "timeout_seconds": 900.0,
            "stable_criteria_reused": False,
        },
    )
    value.setdefault(
        "emergency_monitor",
        {
            "enabled": False,
            "check_interval_seconds": 0.0,
            "max_battery_temperature_c": 42.0,
            "max_android_thermal_status": 1,
            "require_unplugged": True,
            "required_battery_status": 3,
            "strategy": "logcat_telemetry_first_with_sparse_dumpsys",
        },
    )
    return value


def new_manifest(args: argparse.Namespace) -> dict[str, Any]:
    now = utc_now()
    config = experiment_config(args)
    runs = build_plan(
        args.resources,
        args.repeat,
        args.seed,
        config["cpu_thread_levels"],
        config["duty_cycles"],
    )
    summary = plan_summary(runs, args.repeat)
    return {
        "schema_version": 1,
        "orchestrator_version": VERSION,
        "experiment_id": str(uuid.uuid4()),
        "created_utc": now,
        "updated_utc": now,
        "status": "planned",
        "config": config,
        "accuracy_preflight": dict(config["accuracy_preflight"]),
        "provenance": {
            "accuracy_preflight": dict(config["accuracy_preflight"]),
            "energy_measurement": dict(config["energy_measurement"]),
        },
        "device": None,
        "runs": runs,
        "plan_summary": summary,
        "methodology_warnings": matrix_methodology_warnings(
            args.start_policy, summary["condition_count"]
        ),
        "limitations": {
            "energy_calculated": False,
            "current_raw_unit_verified": False,
            "duty_cycle_implemented": True,
            "accuracy_comparator_implemented": True,
            "task_accuracy_measured": False,
        },
    }


def default_output_dir() -> Path:
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    return Path("results") / f"D1Check_repeat_{stamp}"


def resolve_adb(value: str | None) -> str:
    candidates = [
        value,
        os.environ.get("D1_ADB"),
        str(Path.home() / "AppData/Local/Android/Sdk/platform-tools/adb.exe"),
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return str(Path(candidate).resolve())
    raise OrchestratorError("adb not found; pass --adb or set D1_ADB")


def dry_run_payload(args: argparse.Namespace) -> dict[str, Any]:
    placeholder_adb = args.adb or "adb"
    serial_prefix = [placeholder_adb, "-s", args.serial or "<selected-serial>"]
    config = experiment_config(args)
    plan = build_plan(
        args.resources,
        args.repeat,
        args.seed,
        config["cpu_thread_levels"],
        config["duty_cycles"],
    )
    commands = []
    for slot in plan:
        commands.append(
            {
                "slot_id": slot["slot_id"],
                "condition_id": slot["condition_id"],
                "block_index": slot["block_index"],
                "resource": slot["resource"],
                "force_stop": serial_prefix + [
                    "shell", "am", "force-stop", runner_package_for(slot["resource"]),
                ],
                "start_run": serial_prefix + start_run_arguments(),
                "runner": serial_prefix + runner_intent_arguments(
                    slot["resource"], slot["cpu_threads"], args.duration, args.warmup,
                    "<run-id>", "<command-id>", slot["duty_cycle_percent"],
                    args.duty_cycle_period_seconds,
                    args.gpu_profile,
                    **npu_runner_intent_kwargs(slot["resource"], args),
                ),
                **(
                    {"logger_capture_extra": npu_logger_capture_arguments(slot["resource"])}
                    if slot["resource"] == "NPU" else {}
                ),
                "stop_run": serial_prefix + stop_run_arguments(),
                "direct_stop_recovery": serial_prefix + direct_stop_arguments(),
            }
        )
    summary = plan_summary(plan, args.repeat)
    representative = None
    if args.representative_tensor_set is not None:
        representative = validate_representative_tensor_set(args.representative_tensor_set)
    return {
        "dry_run": True,
        "config": config,
        "plan": plan,
        "plan_summary": summary,
        "methodology_warnings": matrix_methodology_warnings(
            args.start_policy, summary["condition_count"]
        ),
        "commands": commands,
        "accuracy_preflight": {
            "policy": effective_accuracy_policy(args),
            "validation_scope": effective_validation_scope(args),
            "gpu_delegate_profile": gpu_profile(args.gpu_profile),
            "runs_before_start_run_and_thermal_conditioning": True,
            "synthetic_intent": serial_prefix + accuracy_preflight_intent_arguments(
                "<accuracy-command-id>", args.accuracy_input_count,
                args.accuracy_seed, args.accuracy_cpu_threads,
                args.accuracy_atol, args.accuracy_rtol,
                args.accuracy_relative_epsilon,
                "synthetic",
                args.gpu_profile,
            ),
            "intent": serial_prefix + accuracy_preflight_intent_arguments(
                "<accuracy-command-id>", args.accuracy_input_count,
                args.accuracy_seed, args.accuracy_cpu_threads,
                args.accuracy_atol, args.accuracy_rtol,
                args.accuracy_relative_epsilon, "synthetic", args.gpu_profile,
            ),
            "representative_intent": (
                serial_prefix + accuracy_preflight_intent_arguments(
                    "<representative-command-id>", representative["input_count"],
                    representative["header"]["selection"]["seed"],
                    args.accuracy_cpu_threads, args.accuracy_atol, args.accuracy_rtol,
                    args.accuracy_relative_epsilon, "representative", args.gpu_profile,
                    f"<remote>/{representative['container_sha256']}.d1tset",
                    representative["container_sha256"],
                    representative["preprocessing_configuration_sha256"],
                ) if representative is not None else None
            ),
            "representative_tensor_set": (
                {
                    "container_sha256": representative["container_sha256"],
                    "tensor_set_sha256": representative["tensor_set_sha256"],
                    "input_count": representative["input_count"],
                    "label_mapping_file_sha256": representative[
                        "label_mapping_file_sha256"
                    ],
                    "preprocessing_configuration_sha256": representative[
                        "preprocessing_configuration_sha256"
                    ],
                } if representative is not None else None
            ),
            "formal_gate_would_require_representative": effective_validation_scope(args)
                in {"backend-performance-formal", "accuracy-preserving-formal"},
            "note": "synthetic smoke, representative equivalence, and task accuracy are separate",
        },
        "thermal_conditioning": {
            "policy": args.start_policy,
            "note": "dry-run does not query thermalservice or wait",
        },
        "cooling": {
            "policy": args.cooling_policy,
            "post_load_idle_seconds": args.post_load_idle_seconds,
            "minimum_seconds": args.cooling_min_seconds,
            "timeout_seconds": args.cooling_timeout_seconds,
            "runner_force_stop_before_interval": (
                args.cooling_policy != "fixed" or args.post_load_idle_seconds > 0
            ),
        },
        "performs_adb_calls": False,
        "writes_manifest": False,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adb")
    parser.add_argument("--serial")
    parser.add_argument("--mode", choices=("pilot", "formal"), default="pilot")
    parser.add_argument(
        "--resources", nargs="+", choices=RESOURCE_CHOICES, default=["CPU", "GPU"]
    )
    parser.add_argument("--cpu-threads", type=int)
    parser.add_argument("--cpu-thread-levels", type=int, nargs="+")
    parser.add_argument("--duration", type=int, default=600)
    parser.add_argument("--warmup", type=int, default=20)
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--duty-cycle-percent", type=int)
    parser.add_argument("--duty-cycles", type=int, nargs="+")
    parser.add_argument("--duty-cycle-period-seconds", type=float, default=10.0)
    parser.add_argument(
        "--accuracy-preflight", choices=("off", "optional", "required")
    )
    parser.add_argument(
        "--accuracy-validation-scope",
        choices=ACCURACY_VALIDATION_SCOPES,
    )
    parser.add_argument("--representative-tensor-set", type=Path)
    parser.add_argument(
        "--gpu-profile", choices=GPU_PROFILE_IDS, default=DEFAULT_GPU_PROFILE
    )
    parser.add_argument(
        "--npu-model-asset", default=DEFAULT_NPU_MODEL_ASSET,
        help="npu-runner asset for NPU slots (AOT-compiled *_Samsung_E9965.tflite)",
    )
    parser.add_argument(
        "--npu-reference-asset", default=DEFAULT_NPU_REFERENCE_ASSET,
        help="CPU reference model for the NPU quality gate",
    )
    parser.add_argument(
        "--npu-input-spec", choices=NPU_INPUT_SPECS, default=DEFAULT_NPU_INPUT_SPEC,
        help="npu-runner input_spec for the NPU quality gate (32 inputs)",
    )
    parser.add_argument(
        "--accuracy-input-count", type=int, default=DEFAULT_ACCURACY_INPUT_COUNT
    )
    parser.add_argument("--accuracy-seed", type=int, default=DEFAULT_ACCURACY_SEED)
    parser.add_argument("--accuracy-cpu-threads", type=int, default=DEFAULT_CPU_THREADS)
    parser.add_argument("--accuracy-atol", type=float, default=DEFAULT_ACCURACY_ATOL)
    parser.add_argument("--accuracy-rtol", type=float, default=DEFAULT_ACCURACY_RTOL)
    parser.add_argument(
        "--accuracy-relative-epsilon", type=float,
        default=DEFAULT_ACCURACY_RELATIVE_EPSILON,
    )
    parser.add_argument("--accuracy-timeout-seconds", type=float, default=600.0)
    parser.add_argument(
        "--start-policy", choices=("safety", "stable", "matched"), default="safety"
    )
    parser.add_argument("--stability-window-seconds", type=float, default=60.0)
    parser.add_argument(
        "--stability-sample-interval-seconds", type=float, default=5.0
    )
    parser.add_argument("--stability-timeout-seconds", type=float, default=900.0)
    parser.add_argument("--stability-max-range-c", type=float, default=0.5)
    parser.add_argument(
        "--stability-max-slope-c-per-minute", type=float, default=0.2
    )
    parser.add_argument("--matched-tolerance-c", type=float, default=0.5)
    parser.add_argument("--post-load-idle-seconds", type=float, default=0.0)
    parser.add_argument(
        "--cooling-policy", choices=("fixed", "stable", "matched"), default="fixed"
    )
    parser.add_argument("--cooling-timeout-seconds", type=float, default=900.0)
    parser.add_argument("--cooling-min-seconds", type=float, default=0.0)
    parser.add_argument(
        "--emergency-check-interval-seconds", type=float, default=0.0
    )
    parser.add_argument(
        "--emergency-max-battery-temperature-c", type=float, default=42.0
    )
    parser.add_argument(
        "--emergency-max-android-thermal-status", type=int, default=1
    )
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument(
        "--logger",
        type=Path,
        default=Path(__file__).with_name("d1_logger_v4.py"),
    )
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def validate_cli(args: argparse.Namespace) -> None:
    cpu_thread_levels, duty_cycles = normalized_axes(args)
    if any(not 1 <= value <= 16 for value in cpu_thread_levels):
        raise OrchestratorError("CPU thread levels must each be in 1..16")
    if not 1 <= args.duration <= 3600:
        raise OrchestratorError("--duration must be in 1..3600")
    if not 0 <= args.warmup <= 10_000:
        raise OrchestratorError("--warmup must be in 0..10000")
    if args.repeat < 1:
        raise OrchestratorError("--repeat must be at least 1")
    if len(set(args.resources)) != len(args.resources):
        raise OrchestratorError("--resources must not contain duplicates")
    if any(not 1 <= value <= 100 for value in duty_cycles):
        raise OrchestratorError("duty cycles must each be in 1..100")
    if not math.isfinite(args.duty_cycle_period_seconds) or (
        args.duty_cycle_period_seconds <= 0
    ):
        raise OrchestratorError(
            "--duty-cycle-period-seconds must be finite and positive"
        )
    if args.mode == "formal" and effective_accuracy_policy(args) == "off":
        raise OrchestratorError("formal experiments require accuracy preflight")
    if not 1 <= args.accuracy_input_count <= 256:
        raise OrchestratorError("--accuracy-input-count must be in 1..256")
    if (
        effective_accuracy_policy(args) == "required"
        and args.accuracy_input_count < 32
    ):
        raise OrchestratorError("required accuracy preflight needs at least 32 inputs")
    if not 1 <= args.accuracy_cpu_threads <= 16:
        raise OrchestratorError("--accuracy-cpu-threads must be in 1..16")
    if not math.isfinite(args.accuracy_atol) or args.accuracy_atol < 0:
        raise OrchestratorError("--accuracy-atol must be finite and non-negative")
    if not math.isfinite(args.accuracy_rtol) or args.accuracy_rtol < 0:
        raise OrchestratorError("--accuracy-rtol must be finite and non-negative")
    if (
        not math.isfinite(args.accuracy_relative_epsilon)
        or args.accuracy_relative_epsilon <= 0
    ):
        raise OrchestratorError(
            "--accuracy-relative-epsilon must be finite and positive"
        )
    if (
        not math.isfinite(args.accuracy_timeout_seconds)
        or args.accuracy_timeout_seconds <= 0
    ):
        raise OrchestratorError("--accuracy-timeout-seconds must be finite and positive")
    scope = effective_validation_scope(args)
    if args.mode == "formal" and scope == "thermal-only-pilot":
        raise OrchestratorError(
            "formal mode requires backend-performance-formal or accuracy-preserving-formal"
        )
    if (
        scope in {"backend-performance-formal", "accuracy-preserving-formal"}
        and args.representative_tensor_set is None
        and not args.dry_run
        and not args.resume
    ):
        raise OrchestratorError(
            f"{scope} requires --representative-tensor-set; synthetic inputs are not "
            "representative samples"
        )
    if args.representative_tensor_set is not None:
        if not Path(args.representative_tensor_set).is_file():
            raise OrchestratorError(
                f"representative tensor-set not found: {args.representative_tensor_set}"
            )
        validate_representative_tensor_set(Path(args.representative_tensor_set))
    if args.stability_window_seconds <= 0:
        raise OrchestratorError("--stability-window-seconds must be positive")
    if args.stability_sample_interval_seconds <= 0:
        raise OrchestratorError("--stability-sample-interval-seconds must be positive")
    if args.stability_timeout_seconds < args.stability_window_seconds:
        raise OrchestratorError(
            "--stability-timeout-seconds must be at least the stability window"
        )
    if args.stability_max_range_c < 0:
        raise OrchestratorError("--stability-max-range-c must be non-negative")
    if args.stability_max_slope_c_per_minute < 0:
        raise OrchestratorError(
            "--stability-max-slope-c-per-minute must be non-negative"
        )
    if args.matched_tolerance_c < 0:
        raise OrchestratorError("--matched-tolerance-c must be non-negative")
    if args.post_load_idle_seconds < 0:
        raise OrchestratorError("--post-load-idle-seconds must be non-negative")
    if args.cooling_min_seconds < 0:
        raise OrchestratorError("--cooling-min-seconds must be non-negative")
    if not math.isfinite(args.cooling_timeout_seconds) or (
        args.cooling_timeout_seconds <= 0
    ):
        raise OrchestratorError("--cooling-timeout-seconds must be finite and positive")
    if args.cooling_policy != "fixed" and args.cooling_timeout_seconds < max(
        args.cooling_min_seconds,
        args.post_load_idle_seconds,
        args.stability_window_seconds,
    ):
        raise OrchestratorError(
            "conditioned cooling timeout must cover minimum and stability window"
        )
    if args.emergency_check_interval_seconds < 0:
        raise OrchestratorError(
            "--emergency-check-interval-seconds must be non-negative"
        )
    if not math.isfinite(args.emergency_max_battery_temperature_c):
        raise OrchestratorError(
            "--emergency-max-battery-temperature-c must be finite"
        )
    if not 0 <= args.emergency_max_android_thermal_status <= 6:
        raise OrchestratorError(
            "--emergency-max-android-thermal-status must be in 0..6"
        )


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    validate_cli(args)
    if args.dry_run:
        print(json.dumps(dry_run_payload(args), ensure_ascii=False, indent=2))
        return 0
    args.adb = resolve_adb(args.adb)
    if not Path(args.logger).is_file():
        raise OrchestratorError(f"d1_logger_v4.py not found: {args.logger}")
    output_dir = (args.output_dir or default_output_dir()).resolve()
    manifest_path = output_dir / MANIFEST_NAME
    if args.resume:
        if not manifest_path.is_file():
            raise OrchestratorError(f"resume manifest not found: {manifest_path}")
        manifest = load_json(manifest_path)
        requested_config = experiment_config(args)
        if _legacy_compatible_config(manifest.get("config", {})) != requested_config:
            raise OrchestratorError("resume options do not match experiment manifest config")
        if manifest.get("config") != requested_config:
            manifest["config"] = requested_config
        plan_upgraded = upgrade_and_validate_manifest_plan(manifest, requested_config)
        warnings_updated = sync_matrix_methodology_warnings(
            manifest,
            args.start_policy,
            manifest["plan_summary"]["condition_count"],
        )
        reference = validated_reference_vector(manifest)
        matched_requested = (
            args.start_policy == "matched" or args.cooling_policy == "matched"
        )
        attempted = any(int(slot.get("attempts") or 0) > 0 for slot in manifest["runs"])
        if matched_requested and attempted and reference is None:
            raise OrchestratorError(
                "resume manifest is missing shared thermal_conditioning_reference; "
                "refusing to recreate it"
            )
        manifest.setdefault(
            "provenance",
            {
                "accuracy_preflight": dict(requested_config["accuracy_preflight"]),
                "energy_measurement": dict(requested_config["energy_measurement"]),
            },
        )
        previous_version = manifest.get("orchestrator_version")
        if previous_version != VERSION:
            manifest.setdefault("orchestrator_upgrades", []).append(
                {"utc": utc_now(), "from": previous_version, "to": VERSION}
            )
            manifest["orchestrator_version"] = VERSION
        if plan_upgraded:
            manifest.setdefault("plan_migrations", []).append({
                "utc": utc_now(),
                "kind": "legacy_single_axis_metadata_added",
                "order_preserved": True,
                "slot_ids_preserved": True,
            })
        if previous_version != VERSION or plan_upgraded or warnings_updated:
            atomic_write_json(manifest_path, manifest)
    else:
        if manifest_path.exists():
            raise OrchestratorError(
                f"manifest already exists; use --resume or a new --output-dir: {manifest_path}"
            )
        manifest = new_manifest(args)
        upgrade_and_validate_manifest_plan(manifest, manifest["config"])
        atomic_write_json(manifest_path, manifest)
    return ExperimentOrchestrator(args, manifest, manifest_path).run()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OrchestratorError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1)
