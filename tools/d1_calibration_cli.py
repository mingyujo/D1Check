#!/usr/bin/env python3
"""Fail-closed host preparation and artifact validation for calibration-v1.

The CLI never selects representative images. ``plan --dry-run`` is intentionally
side-effect free and only prints the production entry and required user actions.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import stat
import sys
import uuid
from pathlib import Path
from typing import Any

PROTOCOL_VERSION = "calibration-v1"
SCHEMA_VERSION = 2
APK_PACKAGE = "com.example.d1check.benchmarkrunner"
MAIN_ACTIVITY = f"{APK_PACKAGE}/.MainActivity"
CALIBRATION_DIRECTORY = "calibration-v1"
MODEL_SHA256 = "d95b3c5ea86750cef882fa867ca357dfe4d265d0b80b67e83277a0bda310cfbb"
PREPROCESSING_CONTRACT_ID = "android-mobilenet-v1-image-v3"
PREPROCESSING_CONFIGURATION = (
    '{"contract_id":"android-mobilenet-v1-image-v3",'
    '"exif_policy":"androidx-exifinterface-1.4.2-tag-absent-normal-explicit-1-to-8-before-crop",'
    '"crop_policy":"center-square-floor-min-times-0.875",'
    '"resize_method":"android-bitmap-bilinear",'
    '"width":224,"height":224,"channels":"RGB",'
    '"dtype":"FLOAT32","normalization":"(value/127.5)-1"}'
)
PREPROCESSING_SHA256 = hashlib.sha256(PREPROCESSING_CONFIGURATION.encode("utf-8")).hexdigest()
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
IMAGE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
ROOT_KEYS = {
    "schema_version", "protocol_version", "session_id", "calibration_mode", "mode", "fixed_backend",
    "cpu_threads", "queue_capacity", "warmup_count", "model_sha256",
    "label_mapping_sha256", "preprocessing_sha256", "preprocessing_contract_id",
    "expected_apk_sha256", "deadline_state", "temperature_policy", "environment", "images",
}
ENV_KEYS = {
    "physical_position", "ambient_temperature_c", "expected_charging",
    "expected_screen_on",
}
IMAGE_KEYS = {
    "image_id", "relative_path", "sha256", "byte_count", "label_index", "label",
    "raw_width", "raw_height", "exif_orientation", "transformed_width",
    "transformed_height", "mime_type",
}
TEMPERATURE_POLICY_KEYS = {
    "policy_id", "maximum_start_battery_temperature_deci_c", "stability_window_ms",
    "maximum_stability_delta_deci_c", "sha256",
}


class CalibrationValidationError(ValueError):
    pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_reparse_or_symlink(path: Path) -> bool:
    if path.is_symlink():
        return True
    try:
        attributes = path.lstat().st_file_attributes
    except AttributeError:
        return False
    return bool(attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)


def _magic_mime(path: Path) -> str:
    with path.open("rb") as stream:
        header = stream.read(12)
    if header.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if len(header) >= 12 and header[:4] == b"RIFF" and header[8:12] == b"WEBP":
        return "image/webp"
    raise CalibrationValidationError(f"unsupported image magic bytes: {path}")


def _image_metadata(path: Path) -> tuple[int, int, int, int, int]:
    try:
        from PIL import Image
    except ImportError as error:
        raise CalibrationValidationError(
            "Pillow is required to validate calibration image dimensions and EXIF"
        ) from error
    try:
        with Image.open(path) as image:
            image.verify()
        with Image.open(path) as image:
            image.load()
            raw_width, raw_height = image.size
            orientation = int(image.getexif().get(274, 1))
    except (OSError, ValueError, TypeError) as error:
        raise CalibrationValidationError(f"image decode/EXIF validation failed: {path}") from error
    if raw_width <= 0 or raw_height <= 0 or orientation not in range(1, 9):
        raise CalibrationValidationError(f"invalid image dimensions or EXIF orientation: {path}")
    if orientation in {5, 6, 7, 8}:
        transformed_width, transformed_height = raw_height, raw_width
    else:
        transformed_width, transformed_height = raw_width, raw_height
    return raw_width, raw_height, orientation, transformed_width, transformed_height


def _temperature_policy_sha256(policy: dict[str, Any]) -> str:
    canonical = "|".join((
        f"policy_id={policy['policy_id']}",
        "maximum_start_battery_temperature_deci_c="
        f"{policy['maximum_start_battery_temperature_deci_c']}",
        f"stability_window_ms={policy['stability_window_ms']}",
        f"maximum_stability_delta_deci_c={policy['maximum_stability_delta_deci_c']}",
    ))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _canonical_uuid(value: Any, label: str) -> str:
    if not isinstance(value, str):
        raise CalibrationValidationError(f"{label} must be a canonical UUID")
    try:
        parsed = uuid.UUID(value)
    except (ValueError, AttributeError) as error:
        raise CalibrationValidationError(f"{label} must be a canonical UUID") from error
    if str(parsed) != value:
        raise CalibrationValidationError(f"{label} must be a canonical UUID")
    return value


def _canonical_sha(value: Any, label: str) -> str:
    if not isinstance(value, str) or SHA256_RE.fullmatch(value) is None:
        raise CalibrationValidationError(f"{label} must be lowercase SHA-256")
    return value


def _exact_keys(value: dict[str, Any], expected: set[str], label: str) -> None:
    if set(value) != expected:
        raise CalibrationValidationError(
            f"{label} keys differ: missing={sorted(expected - set(value))} "
            f"extra={sorted(set(value) - expected)}"
        )


def validate_input_manifest(path: Path, labels: Path | None = None,
                            apk: Path | None = None,
                            input_root: Path | None = None) -> dict[str, Any]:
    if not path.is_file() or _is_reparse_or_symlink(path):
        raise CalibrationValidationError("manifest must be a regular non-symlink file")
    raw = path.read_bytes()
    try:
        root = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CalibrationValidationError(f"manifest JSON is invalid: {error}") from error
    if not isinstance(root, dict):
        raise CalibrationValidationError("manifest root must be an object")
    _exact_keys(root, ROOT_KEYS, "manifest")
    if root["schema_version"] != SCHEMA_VERSION or root["protocol_version"] != PROTOCOL_VERSION:
        raise CalibrationValidationError("unsupported calibration protocol/schema")
    _canonical_uuid(root["session_id"], "session_id")
    if root["calibration_mode"] not in {
        "baseline_pilot", "baseline_formal", "thermal_stress"
    }:
        raise CalibrationValidationError("unsupported calibration_mode")
    if root["mode"] not in {"fixed", "transition_probe"}:
        raise CalibrationValidationError("unsupported mode")
    fixed = root["fixed_backend"]
    if (root["mode"] == "fixed") != (fixed is not None):
        raise CalibrationValidationError("fixed_backend is required only in fixed mode")
    if fixed is not None and fixed not in {"CPU", "GPU"}:
        raise CalibrationValidationError("unsupported fixed_backend")
    if type(root["cpu_threads"]) is not int or not 1 <= root["cpu_threads"] <= 64:
        raise CalibrationValidationError("cpu_threads is invalid")
    if type(root["queue_capacity"]) is not int or not 1 <= root["queue_capacity"] <= 64:
        raise CalibrationValidationError("queue_capacity is invalid")
    if type(root["warmup_count"]) is not int or not 0 <= root["warmup_count"] <= 20:
        raise CalibrationValidationError("warmup_count is invalid")
    for key in ("model_sha256", "label_mapping_sha256", "preprocessing_sha256",
                "expected_apk_sha256"):
        _canonical_sha(root[key], key)
    if root["model_sha256"] != MODEL_SHA256:
        raise CalibrationValidationError("manifest does not identify the packaged model")
    if root["preprocessing_sha256"] != PREPROCESSING_SHA256:
        raise CalibrationValidationError("preprocessing configuration SHA-256 mismatch")
    if root["preprocessing_contract_id"] != PREPROCESSING_CONTRACT_ID:
        raise CalibrationValidationError("preprocessing contract ID mismatch")
    if root["deadline_state"] != "calibration_pending":
        raise CalibrationValidationError("deadline_state must be calibration_pending")
    policy = root["temperature_policy"]
    if (root["calibration_mode"] == "baseline_formal") != (policy is not None):
        raise CalibrationValidationError(
            "temperature_policy is required only for baseline_formal"
        )
    if policy is not None:
        if not isinstance(policy, dict):
            raise CalibrationValidationError("temperature_policy must be an object")
        _exact_keys(policy, TEMPERATURE_POLICY_KEYS, "temperature_policy")
        if not isinstance(policy["policy_id"], str) or IMAGE_ID_RE.fullmatch(
            policy["policy_id"]
        ) is None:
            raise CalibrationValidationError("temperature policy_id is invalid")
        if type(policy["maximum_start_battery_temperature_deci_c"]) is not int or not (
            -500 <= policy["maximum_start_battery_temperature_deci_c"] <= 1000
        ):
            raise CalibrationValidationError("temperature policy start limit is invalid")
        if type(policy["stability_window_ms"]) is not int or not (
            1_000 <= policy["stability_window_ms"] <= 3_600_000
        ):
            raise CalibrationValidationError("temperature stability window is invalid")
        if type(policy["maximum_stability_delta_deci_c"]) is not int or not (
            0 <= policy["maximum_stability_delta_deci_c"] <= 100
        ):
            raise CalibrationValidationError("temperature stability delta is invalid")
        _canonical_sha(policy["sha256"], "temperature policy sha256")
        if policy["sha256"] != _temperature_policy_sha256(policy):
            raise CalibrationValidationError("temperature policy SHA-256 mismatch")
    environment = root["environment"]
    if not isinstance(environment, dict):
        raise CalibrationValidationError("environment must be an object")
    _exact_keys(environment, ENV_KEYS, "environment")
    if not isinstance(environment["physical_position"], str) or not environment["physical_position"]:
        raise CalibrationValidationError("physical_position is required")
    ambient = environment["ambient_temperature_c"]
    if ambient is not None and (
        type(ambient) not in (int, float) or not math.isfinite(float(ambient))
    ):
        raise CalibrationValidationError("ambient_temperature_c is invalid")
    if type(environment["expected_charging"]) is not bool or type(environment["expected_screen_on"]) is not bool:
        raise CalibrationValidationError("expected charging/screen state must be Boolean")
    images = root["images"]
    if not isinstance(images, list) or not images:
        raise CalibrationValidationError("images must be a non-empty array")
    ids: set[str] = set()
    hashes: set[str] = set()
    relative_paths: set[str] = set()
    for image in images:
        if not isinstance(image, dict):
            raise CalibrationValidationError("image entry must be an object")
        _exact_keys(image, IMAGE_KEYS, "image")
        if not isinstance(image["image_id"], str) or IMAGE_ID_RE.fullmatch(image["image_id"]) is None:
            raise CalibrationValidationError("image_id is invalid")
        relative = image["relative_path"]
        if (not isinstance(relative, str) or
                re.fullmatch(r"images/[A-Za-z0-9][A-Za-z0-9._-]{0,127}", relative) is None):
            raise CalibrationValidationError("image relative_path is invalid")
        image_hash = _canonical_sha(image["sha256"], "image sha256")
        if (image["image_id"] in ids or image_hash in hashes or
                relative in relative_paths):
            raise CalibrationValidationError("duplicate image identity")
        ids.add(image["image_id"])
        hashes.add(image_hash)
        relative_paths.add(relative)
        if type(image["byte_count"]) is not int or image["byte_count"] <= 0:
            raise CalibrationValidationError("image byte_count is invalid")
        if type(image["label_index"]) is not int or not 0 <= image["label_index"] <= 1000:
            raise CalibrationValidationError("image label_index is invalid")
        if not isinstance(image["label"], str) or not image["label"]:
            raise CalibrationValidationError("image label is required")
        dimension_keys = ("raw_width", "raw_height", "transformed_width", "transformed_height")
        if any(type(image[key]) is not int or image[key] <= 0 for key in dimension_keys):
            raise CalibrationValidationError("image dimensions are invalid")
        if type(image["exif_orientation"]) is not int or not 1 <= image["exif_orientation"] <= 8:
            raise CalibrationValidationError("image EXIF orientation is invalid")
        if image["mime_type"] not in {"image/jpeg", "image/png", "image/webp"}:
            raise CalibrationValidationError("unsupported image mime_type")
    label_lines: list[str] | None = None
    if labels is not None:
        if not labels.is_file() or _is_reparse_or_symlink(labels) or _sha256(labels) != root["label_mapping_sha256"]:
            raise CalibrationValidationError("label mapping artifact/hash mismatch")
        label_lines = labels.read_text(encoding="utf-8").splitlines()
        if len(label_lines) != 1001 or any(not line.strip() for line in label_lines) or \
                label_lines[0].startswith("\ufeff"):
            raise CalibrationValidationError(
                "label mapping must contain exactly 1001 non-empty UTF-8 labels without BOM"
            )
        for image in images:
            if label_lines[image["label_index"]] != image["label"]:
                raise CalibrationValidationError(
                    f"image label_index/label mismatch: {image['image_id']}"
                )
    if apk is not None:
        if not apk.is_file() or _is_reparse_or_symlink(apk) or _sha256(apk) != root["expected_apk_sha256"]:
            raise CalibrationValidationError("APK artifact/hash mismatch")
    if input_root is not None:
        if not input_root.is_dir() or _is_reparse_or_symlink(input_root):
            raise CalibrationValidationError("input root must be a regular non-reparse directory")
        resolved_root = input_root.resolve(strict=True)
        expected_manifest = (resolved_root / "input_manifest.json").resolve(strict=True)
        expected_labels = (resolved_root / "label_mapping.txt").resolve(strict=True)
        if path.resolve(strict=True) != expected_manifest or labels is None or \
                labels.resolve(strict=True) != expected_labels:
            raise CalibrationValidationError(
                "manifest and label mapping must use fixed input bundle paths"
            )
        expected_files = {"input_manifest.json", "label_mapping.txt", *relative_paths}
        actual_files: set[str] = set()
        for candidate in input_root.rglob("*"):
            if _is_reparse_or_symlink(candidate):
                raise CalibrationValidationError(f"reparse/symlink input rejected: {candidate}")
            if candidate.is_file():
                resolved = candidate.resolve(strict=True)
                if resolved_root not in resolved.parents:
                    raise CalibrationValidationError("input path escapes input root")
                actual_files.add(candidate.relative_to(input_root).as_posix())
            elif not candidate.is_dir():
                raise CalibrationValidationError(f"non-regular input rejected: {candidate}")
        if actual_files != expected_files:
            raise CalibrationValidationError(
                f"input bundle file set mismatch: missing={sorted(expected_files - actual_files)} "
                f"extra={sorted(actual_files - expected_files)}"
            )
        for image in images:
            image_path = input_root / image["relative_path"]
            resolved = image_path.resolve(strict=True)
            if resolved_root not in resolved.parents or not image_path.is_file() or \
                    _is_reparse_or_symlink(image_path):
                raise CalibrationValidationError("unsafe image path")
            if image_path.stat().st_size != image["byte_count"] or \
                    _sha256(image_path) != image["sha256"]:
                raise CalibrationValidationError(
                    f"image byte count/SHA-256 mismatch: {image['image_id']}"
                )
            if _magic_mime(image_path) != image["mime_type"]:
                raise CalibrationValidationError(f"image MIME mismatch: {image['image_id']}")
            metadata = _image_metadata(image_path)
            declared = (
                image["raw_width"], image["raw_height"], image["exif_orientation"],
                image["transformed_width"], image["transformed_height"],
            )
            if metadata != declared:
                raise CalibrationValidationError(
                    f"image dimension/EXIF mismatch: {image['image_id']}"
                )
    return root


def validate_result(root: Path) -> list[dict[str, Any]]:
    if not root.is_dir() or root.is_symlink():
        raise CalibrationValidationError("result root must be a regular directory")
    provenance_path = root / "provenance.json"
    if not provenance_path.is_file() or provenance_path.is_symlink():
        raise CalibrationValidationError("provenance.json is missing")
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    _exact_keys(provenance, {
        "schema_version", "protocol_version", "session_id", "manifest_sha256",
        "apk_sha256", "model_sha256", "artifact_set",
    }, "provenance")
    if provenance.get("schema_version") != SCHEMA_VERSION or provenance.get("protocol_version") != PROTOCOL_VERSION:
        raise CalibrationValidationError("result protocol/schema mismatch")
    session_id = _canonical_uuid(provenance.get("session_id"), "result session_id")
    for key in ("manifest_sha256", "apk_sha256", "model_sha256"):
        _canonical_sha(provenance.get(key), key)
    artifacts = provenance.get("artifact_set")
    if not isinstance(artifacts, list):
        raise CalibrationValidationError("artifact_set must be an array")
    expected: dict[str, dict[str, Any]] = {}
    for item in artifacts:
        if not isinstance(item, dict) or set(item) != {"relative_path", "byte_count", "sha256"}:
            raise CalibrationValidationError("invalid artifact entry")
        relative = item["relative_path"]
        if (not isinstance(relative, str) or not relative or "\\" in relative or
                Path(relative).is_absolute() or ".." in Path(relative).parts):
            raise CalibrationValidationError("unsafe artifact relative_path")
        if relative in expected:
            raise CalibrationValidationError("duplicate artifact relative_path")
        if type(item["byte_count"]) is not int or item["byte_count"] < 0:
            raise CalibrationValidationError("invalid artifact byte_count")
        _canonical_sha(item["sha256"], "artifact sha256")
        expected[relative] = item
    actual: dict[str, Path] = {}
    for path in root.rglob("*"):
        if path.is_symlink():
            raise CalibrationValidationError("symlink in result tree")
        relative = path.relative_to(root).as_posix()
        if path.is_file() and relative != "provenance.json":
            actual[relative] = path
    if set(actual) != set(expected):
        raise CalibrationValidationError(
            f"artifact set mismatch: unexpected={sorted(set(actual) - set(expected))}, "
            f"missing={sorted(set(expected) - set(actual))}"
        )
    required = {
        "input_manifest.json", "label_mapping.txt", "metadata.json",
        "requests.jsonl", "thermal_samples.jsonl", "summary.json",
    }
    if not required.issubset(actual):
        raise CalibrationValidationError("required calibration artifact is missing")
    resolved_root = root.resolve(strict=True)
    for relative, path in actual.items():
        resolved = path.resolve(strict=True)
        if resolved.parent != resolved_root and resolved_root not in resolved.parents:
            raise CalibrationValidationError("artifact containment failure")
        item = expected[relative]
        if path.stat().st_size != item["byte_count"] or _sha256(path) != item["sha256"]:
            raise CalibrationValidationError(f"artifact size/hash mismatch: {relative}")
    for name in ("metadata.json", "summary.json"):
        value = json.loads(actual[name].read_text(encoding="utf-8"))
        if (value.get("schema_version") != SCHEMA_VERSION or
                value.get("protocol_version") != PROTOCOL_VERSION or
                value.get("session_id") != session_id):
            raise CalibrationValidationError(f"{name} identity mismatch")
    input_manifest = validate_input_manifest(
        actual["input_manifest.json"], actual["label_mapping.txt"]
    )
    if input_manifest["session_id"] != session_id:
        raise CalibrationValidationError("input manifest session mismatch")
    if _sha256(actual["input_manifest.json"]) != provenance["manifest_sha256"]:
        raise CalibrationValidationError("input manifest provenance mismatch")
    metadata_value = json.loads(actual["metadata.json"].read_text(encoding="utf-8"))
    expected_metadata = {
        "manifest_sha256": provenance["manifest_sha256"],
        "label_mapping_sha256": input_manifest["label_mapping_sha256"],
        "preprocessing_sha256": input_manifest["preprocessing_sha256"],
        "preprocessing_contract_id": input_manifest["preprocessing_contract_id"],
        "preprocessing_configuration": PREPROCESSING_CONFIGURATION,
        "apk_sha256": input_manifest["expected_apk_sha256"],
        "model_sha256": input_manifest["model_sha256"],
    }
    for key, value in expected_metadata.items():
        if metadata_value.get(key) != value:
            raise CalibrationValidationError(f"metadata {key} mismatch")
    if metadata_value.get("calibration_mode") != input_manifest["calibration_mode"]:
        raise CalibrationValidationError("metadata calibration_mode mismatch")
    policy = input_manifest["temperature_policy"]
    if metadata_value.get("temperature_policy_sha256") != (
        None if policy is None else policy["sha256"]
    ):
        raise CalibrationValidationError("metadata temperature policy mismatch")
    if provenance["apk_sha256"] != input_manifest["expected_apk_sha256"] or \
            provenance["model_sha256"] != input_manifest["model_sha256"]:
        raise CalibrationValidationError("APK/model provenance mismatch")
    request_ids: set[str] = set()
    contract_paths = set(required)
    counts = {status: 0 for status in ("succeeded", "failed", "rejected", "expired")}
    deadline_counts = {outcome: 0 for outcome in (
        "not_set", "on_time", "late", "not_completed"
    )}
    request_lines = actual["requests.jsonl"].read_text(encoding="utf-8").splitlines()
    if not request_lines:
        raise CalibrationValidationError("request telemetry is empty")
    for line in request_lines:
        request = json.loads(line)
        if (request.get("schema_version") != SCHEMA_VERSION or
                request.get("protocol_version") != PROTOCOL_VERSION or
                request.get("session_id") != session_id or
                request.get("calibration_mode") != input_manifest["calibration_mode"]):
            raise CalibrationValidationError("request telemetry identity mismatch")
        request_id = _canonical_uuid(request.get("request_id"), "request_id")
        if request_id in request_ids:
            raise CalibrationValidationError("duplicate request_id")
        request_ids.add(request_id)
        status = request.get("terminal_status")
        if status not in counts:
            raise CalibrationValidationError("invalid terminal status")
        counts[status] += 1
        deadline_outcome = request.get("deadline_outcome")
        if deadline_outcome not in deadline_counts:
            raise CalibrationValidationError("invalid deadline outcome")
        deadline_counts[deadline_outcome] += 1
        deadline_ns = request.get("deadline_ns")
        completion_ns = request.get(
            "output_ready_ns" if request.get("request_type") == "urgent"
            else "persistence_completed_ns"
        )
        if deadline_ns is None:
            expected_outcome = "not_set"
        elif status != "succeeded":
            expected_outcome = "not_completed"
        else:
            if type(deadline_ns) is not int or type(completion_ns) is not int:
                raise CalibrationValidationError("deadline/completion timestamp is invalid")
            expected_outcome = "on_time" if completion_ns < deadline_ns else "late"
        if deadline_outcome != expected_outcome:
            raise CalibrationValidationError("terminal/deadline outcome mismatch")
        expected_met = {
            "not_set": None, "on_time": True, "late": False, "not_completed": False,
        }[deadline_outcome]
        if request.get("deadline_met") is not expected_met:
            raise CalibrationValidationError("deadline_met/outcome mismatch")
        if status == "succeeded":
            if request.get("output_sha256") is None:
                raise CalibrationValidationError("succeeded request output is missing")
        elif request.get("output_sha256") is not None or \
                request.get("persisted_relative_path") is not None:
            raise CalibrationValidationError("non-succeeded request contains output/persistence")
        if request.get("request_type") == "normal" and status == "succeeded":
            relative = request.get("persisted_relative_path")
            expected_relative = f"results/{request_id}.json"
            if relative != expected_relative or relative not in actual:
                raise CalibrationValidationError("normal persistence artifact missing")
            contract_paths.add(relative)
            stored = json.loads(actual[relative].read_text(encoding="utf-8"))
            if stored.get("request_id") != request_id or stored.get("protocol_version") != PROTOCOL_VERSION:
                raise CalibrationValidationError("persisted result identity mismatch")
        elif request.get("persisted_relative_path") is not None:
            raise CalibrationValidationError("non-success result references a persistence artifact")
    if set(actual) != contract_paths:
        raise CalibrationValidationError(
            "artifact set violates the fixed contract: "
            f"unexpected={sorted(set(actual) - contract_paths)}, "
            f"missing={sorted(contract_paths - set(actual))}"
        )
    summary = json.loads(actual["summary.json"].read_text(encoding="utf-8"))
    if summary.get("counts") != counts:
        raise CalibrationValidationError("summary terminal counts mismatch")
    if summary.get("deadline_counts") != deadline_counts:
        raise CalibrationValidationError("summary deadline counts mismatch")
    if summary.get("calibration_mode") != input_manifest["calibration_mode"]:
        raise CalibrationValidationError("summary calibration_mode mismatch")
    arrived = sum(counts.values())
    completed = counts["succeeded"]
    deadline_set = arrived - deadline_counts["not_set"]
    expected_rates = {
        "overall_completion_rate": None if arrived == 0 else completed / arrived,
        "on_time_completion_rate": (
            None if deadline_set == 0 else deadline_counts["on_time"] / deadline_set
        ),
        "deadline_violation_rate": (
            None if deadline_set == 0 else
            (deadline_counts["late"] + deadline_counts["not_completed"]) / deadline_set
        ),
    }
    if summary.get("arrived_count") != arrived or summary.get("completed_count") != completed or \
            summary.get("deadline_set_count") != deadline_set:
        raise CalibrationValidationError("summary completion counts mismatch")
    for key, expected_rate in expected_rates.items():
        actual_rate = summary.get(key)
        if expected_rate is None:
            if actual_rate is not None:
                raise CalibrationValidationError(f"summary {key} must be null")
        elif type(actual_rate) not in (int, float) or not math.isclose(
            float(actual_rate), expected_rate, rel_tol=0.0, abs_tol=1e-12
        ):
            raise CalibrationValidationError(f"summary {key} mismatch")
    thermal_lines = actual["thermal_samples.jsonl"].read_text(encoding="utf-8").splitlines()
    if not thermal_lines:
        raise CalibrationValidationError("thermal sample telemetry is empty")
    thermal_start = metadata_value.get("start_thermal_sample_ns")
    thermal_end = summary.get("end_mono_ns")
    if type(thermal_start) is not int or type(thermal_end) is not int or \
            thermal_start < 0 or thermal_end < thermal_start or \
            summary.get("start_mono_ns") != thermal_start:
        raise CalibrationValidationError("thermal session bounds mismatch")
    previous_timestamp: int | None = None
    for line in thermal_lines:
        sample = json.loads(line)
        if set(sample) != {
            "schema_version", "protocol_version", "session_id", "calibration_mode",
            "timestamp_ns", "thermal_status", "battery_temperature_deci_c",
        }:
            raise CalibrationValidationError("thermal sample field set mismatch")
        if (sample["schema_version"] != SCHEMA_VERSION or
                sample["protocol_version"] != PROTOCOL_VERSION or
                sample["session_id"] != session_id or
                sample["calibration_mode"] != input_manifest["calibration_mode"]):
            raise CalibrationValidationError("thermal sample identity/mode mismatch")
        timestamp = sample["timestamp_ns"]
        if type(timestamp) is not int or not thermal_start <= timestamp <= thermal_end or (
            previous_timestamp is not None and timestamp < previous_timestamp
        ):
            raise CalibrationValidationError("thermal sample timestamp is invalid")
        if previous_timestamp is None and timestamp != thermal_start:
            raise CalibrationValidationError("initial thermal timestamp mismatch")
        if sample["thermal_status"] is not None and (
            type(sample["thermal_status"]) is not int or not 0 <= sample["thermal_status"] <= 6
        ):
            raise CalibrationValidationError("Android thermal status is out of range")
        previous_timestamp = timestamp
    if summary.get("thermal_sample_count") != len(thermal_lines):
        raise CalibrationValidationError("summary thermal sample count mismatch")
    return [expected[key] for key in sorted(expected)]


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="D1Check calibration-v1 host helper")
    sub = parser.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate-input", help="validate the complete input bundle and APK")
    validate.add_argument("--manifest", type=Path, required=True)
    validate.add_argument("--labels", type=Path, required=True)
    validate.add_argument("--input-root", type=Path, required=True)
    validate.add_argument("--apk", type=Path, required=True)
    plan = sub.add_parser("plan", help="print the repeatable production calibration entry plan")
    plan.add_argument("--manifest", type=Path, required=True)
    plan.add_argument("--labels", type=Path, required=True)
    plan.add_argument("--input-root", type=Path, required=True)
    plan.add_argument("--apk", type=Path, required=True)
    plan.add_argument("--dry-run", action="store_true", required=True)
    result = sub.add_parser("validate-result", help="validate finalized device artifacts")
    result.add_argument("--root", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "validate-input":
            root = validate_input_manifest(
                args.manifest, args.labels, args.apk, args.input_root
            )
            print(f"input valid session={root['session_id']} manifest_sha256={_sha256(args.manifest)}")
        elif args.command == "plan":
            root = validate_input_manifest(
                args.manifest, args.labels, args.apk, args.input_root
            )
            print("DRY-RUN: no ADB command was executed and no manifest/result was written")
            print(f"install separately if approved: adb install --no-streaming {args.apk}")
            print(f"launch manually after installation: adb shell am start -n {MAIN_ACTIVITY}")
            print("in Benchmark Runner tap 'Open image calibration', then select the validated "
                  "manifest, label mapping, and manifest-ordered images")
            print(f"expected device subtree: Android/data/{APK_PACKAGE}/files/"
                  f"{CALIBRATION_DIRECTORY}/{root['session_id']}")
        else:
            entries = validate_result(args.root)
            print(f"result valid artifacts={len(entries)} root={args.root.resolve()}")
        return 0
    except (OSError, CalibrationValidationError, json.JSONDecodeError) as error:
        print(f"ERROR: {error}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
