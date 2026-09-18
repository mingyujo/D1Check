#!/usr/bin/env python3
"""Host-side validation, planning, and bounded ADB execution for MODEL-02B.

This tool deliberately does not download or redistribute model binaries. An operator
must obtain each pinned artifact from its original URL. The executable path validates
the exact local bytes before ADB, stages only a canonical UUID-scoped input directory,
pulls the debug seam summary, and always attempts bounded input cleanup. It never
promotes a seam result to finalized provenance or verified GPU delegation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Iterable, Mapping, Sequence
from urllib.parse import urlparse


PROTOCOL_VERSION = "model-probe-v1"
SCHEMA_VERSION = 1
PACKAGE_NAME = "com.example.d1check.benchmarkrunner"
ENTRY_COMPONENT = f"{PACKAGE_NAME}/.ModelProbeEntryActivity"
REMOTE_STAGING_ROOT = "/data/local/tmp/d1check-model-probe"
APP_INPUT_ROOT = "files/model-probe-inputs"
ARTIFACT_ROOT = "files/model-probe-v1"
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
FILENAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,126}\Z")
DEVICE_ID_RE = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}\Z")


@dataclass(frozen=True)
class PinnedFile:
    identifier: str
    url: str
    filename: str
    byte_count: int
    sha256: str


PINNED_MODELS: dict[str, PinnedFile] = {
    "efficientnet-lite0-float32-v1": PinnedFile(
        identifier="efficientnet-lite0-float32-v1",
        url=(
            "https://storage.googleapis.com/mediapipe-models/image_classifier/"
            "efficientnet_lite0/float32/1/efficientnet_lite0.tflite"
        ),
        filename="efficientnet_lite0.tflite",
        byte_count=18_582_189,
        sha256="6c7ab0a6e5dcbf38a8c33b960996a55a3b4300b36a018c4545801de3a3c8bde0",
    ),
    "efficientdet-lite0-float32-v1": PinnedFile(
        identifier="efficientdet-lite0-float32-v1",
        url=(
            "https://storage.googleapis.com/mediapipe-models/object_detector/"
            "efficientdet_lite0/float32/1/efficientdet_lite0.tflite"
        ),
        filename="efficientdet_lite0.tflite",
        byte_count=13_836_895,
        sha256="40338edf5ec70d43e318b0a716a84d4564cd1802759a7a07170c7e43796dbf58",
    ),
}

PINNED_SAMPLE = PinnedFile(
    identifier="cat-and-dog-v1",
    url=(
        "https://storage.googleapis.com/mediapipe-assets/"
        "cat_and_dog.jpg"
    ),
    filename="cat_and_dog.jpg",
    byte_count=69_041,
    sha256="cfa90c34bb93021165e48bd22cfc20dbbb0440ff638a54878939bf30d362e824",
)

ARTIFACT_FILES = frozenset(
    {
        "metadata.json",
        "events.jsonl",
        "raw_equivalence.json",
        "decoded_results.json",
        "memory.json",
        "delegate_evidence.json",
        "summary.json",
        "provenance.json",
    }
)


class ProbeContractError(ValueError):
    pass


@dataclass(frozen=True)
class ProcessResult:
    returncode: int
    stdout: bytes
    stderr: bytes


ProcessRunner = Callable[[Sequence[str], float, frozenset[int]], ProcessResult]


def _output_tail(value: bytes | str | None, limit: int = 4096) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        text = value.decode("utf-8", errors="replace")
    else:
        text = value
    return text[-limit:]


def _default_process_runner(
    argv: Sequence[str],
    timeout_seconds: float,
    allowed_returncodes: frozenset[int],
) -> ProcessResult:
    command = [str(part) for part in argv]
    if not command or timeout_seconds <= 0:
        raise ProbeContractError("invalid subprocess command or timeout")
    try:
        completed = subprocess.run(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            shell=False,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as error:
        raise ProbeContractError(
            "command timed out: "
            f"argv={command!r}; stdout={_output_tail(error.stdout)!r}; "
            f"stderr={_output_tail(error.stderr)!r}"
        ) from error
    except OSError as error:
        raise ProbeContractError(f"cannot start command: argv={command!r}; error={error}") from error
    result = ProcessResult(completed.returncode, completed.stdout, completed.stderr)
    if result.returncode not in allowed_returncodes:
        raise ProbeContractError(
            "command failed: "
            f"argv={command!r}; returncode={result.returncode}; "
            f"stdout={_output_tail(result.stdout)!r}; stderr={_output_tail(result.stderr)!r}"
        )
    return result


def _expect_object(value: Any, location: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ProbeContractError(f"{location} must be an object")
    if not all(isinstance(key, str) for key in value):
        raise ProbeContractError(f"{location} keys must be strings")
    return value


def _exact_keys(value: Mapping[str, Any], required: Iterable[str], location: str) -> None:
    expected = set(required)
    actual = set(value)
    missing = sorted(expected - actual)
    unknown = sorted(actual - expected)
    if missing or unknown:
        raise ProbeContractError(
            f"{location} keys mismatch: missing={missing}, unknown={unknown}"
        )


def _string(value: Any, location: str, *, nonempty: bool = True) -> str:
    if not isinstance(value, str) or (nonempty and not value):
        raise ProbeContractError(f"{location} must be a non-empty string")
    return value


def _integer(value: Any, location: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ProbeContractError(f"{location} must be an integer >= {minimum}")
    return value


def _number(value: Any, location: str, *, minimum: float = 0.0) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ProbeContractError(f"{location} must be numeric")
    result = float(value)
    if not result >= minimum or result in (float("inf"), float("-inf")):
        raise ProbeContractError(f"{location} must be finite and >= {minimum}")
    return result


def _sha256(value: Any, location: str) -> str:
    result = _string(value, location)
    if SHA256_RE.fullmatch(result) is None:
        raise ProbeContractError(f"{location} must be lowercase SHA-256")
    return result


def _filename(value: Any, location: str) -> str:
    result = _string(value, location)
    if FILENAME_RE.fullmatch(result) is None or result in {".", ".."}:
        raise ProbeContractError(f"{location} must be a simple filename")
    return result


def _canonical_uuid(value: Any, location: str) -> str:
    result = _string(value, location)
    try:
        parsed = uuid.UUID(result)
    except ValueError as error:
        raise ProbeContractError(f"{location} must be a UUID") from error
    if str(parsed) != result:
        raise ProbeContractError(f"{location} must be a canonical lowercase UUID")
    return result


def _pinned_https_url(value: Any, location: str) -> str:
    result = _string(value, location)
    parsed = urlparse(result)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
        raise ProbeContractError(f"{location} must be an absolute HTTPS URL")
    if parsed.query or parsed.fragment or "/latest/" in parsed.path:
        raise ProbeContractError(f"{location} must be version-pinned without query/fragment")
    return result


def _shape(value: Any, location: str) -> list[int]:
    if not isinstance(value, list) or not value:
        raise ProbeContractError(f"{location} must be a non-empty integer array")
    return [_integer(item, f"{location}[{index}]", minimum=1) for index, item in enumerate(value)]


def _validate_target(value: Any) -> dict[str, Any]:
    target = _expect_object(value, "target")
    keys = {
        "device_id", "package_name", "apk_sha256", "adb_serial", "manufacturer",
        "model", "soc", "abi", "ram_bytes", "android_release", "api_level",
        "build_fingerprint", "cpu_abi", "cpu_features", "gpu_vendor",
        "gpu_renderer", "gpu_driver", "thermal_capability",
    }
    _exact_keys(target, keys, "target")
    device_id = _string(target["device_id"], "target.device_id")
    if DEVICE_ID_RE.fullmatch(device_id) is None:
        raise ProbeContractError("target.device_id has invalid characters")
    if target["package_name"] != PACKAGE_NAME:
        raise ProbeContractError("target.package_name is not the debug runner package")
    _sha256(target["apk_sha256"], "target.apk_sha256")
    for key in (
        "adb_serial", "manufacturer", "model", "soc", "abi", "android_release",
        "build_fingerprint", "cpu_abi", "cpu_features", "gpu_vendor",
        "gpu_renderer", "gpu_driver", "thermal_capability",
    ):
        _string(target[key], f"target.{key}")
    _integer(target["ram_bytes"], "target.ram_bytes", minimum=1)
    _integer(target["api_level"], "target.api_level", minimum=24)
    return target


def _validate_model(value: Any) -> dict[str, Any]:
    model = _expect_object(value, "model")
    keys = {
        "task_id", "model_id", "url", "filename", "byte_count", "sha256",
        "distribution_policy", "metadata_license_status", "label_filename",
        "label_rows", "label_sha256",
    }
    _exact_keys(model, keys, "model")
    task_id = _string(model["task_id"], "model.task_id")
    if task_id not in {"classification", "detection"}:
        raise ProbeContractError("model.task_id must be classification or detection")
    model_id = _string(model["model_id"], "model.model_id")
    pinned = PINNED_MODELS.get(model_id)
    if pinned is None:
        raise ProbeContractError(f"model.model_id is not approved: {model_id}")
    expected_task = "classification" if model_id.startswith("efficientnet") else "detection"
    if task_id != expected_task:
        raise ProbeContractError("model.task_id does not match model.model_id")
    actual = (
        _pinned_https_url(model["url"], "model.url"),
        _filename(model["filename"], "model.filename"),
        _integer(model["byte_count"], "model.byte_count", minimum=1),
        _sha256(model["sha256"], "model.sha256"),
    )
    expected = (pinned.url, pinned.filename, pinned.byte_count, pinned.sha256)
    if actual != expected:
        raise ProbeContractError("model URL/filename/bytes/SHA-256 do not match pinned contract")
    policy = _string(model["distribution_policy"], "model.distribution_policy")
    expected_policy = (
        "external_verified_apache_2_0" if task_id == "classification"
        else "external_research_only_no_redistribution"
    )
    if policy != expected_policy:
        raise ProbeContractError("model.distribution_policy does not match approved model")
    _string(model["metadata_license_status"], "model.metadata_license_status")
    label_filename = _filename(model["label_filename"], "model.label_filename")
    label_rows = _integer(model["label_rows"], "model.label_rows", minimum=1)
    label_sha = _sha256(model["label_sha256"], "model.label_sha256")
    expected_label = (
        ("labels_without_background.txt", 1000, "e697a491aa735cc6c2aaf982f8e86e8fc7b0a1ea7750a2cc6a2bdfc1e109012f")
        if task_id == "classification"
        else ("labels.txt", 90, "f8803ef7900160c629d570848dfda4175e21667bf7b71f73f8ece4938c9f2bf2")
    )
    if (label_filename, label_rows, label_sha) != expected_label:
        raise ProbeContractError("model associated-label contract mismatch")
    return model


def _validate_tensor(value: Any, task_id: str) -> dict[str, Any]:
    tensor = _expect_object(value, "tensor")
    keys = {"input_count", "inputs", "output_count", "outputs", "normalization", "raw_output_semantics"}
    _exact_keys(tensor, keys, "tensor")
    input_count = _integer(tensor["input_count"], "tensor.input_count", minimum=1)
    output_count = _integer(tensor["output_count"], "tensor.output_count", minimum=1)
    inputs = tensor["inputs"]
    outputs = tensor["outputs"]
    if not isinstance(inputs, list) or len(inputs) != input_count:
        raise ProbeContractError("tensor.inputs count mismatch")
    if not isinstance(outputs, list) or len(outputs) != output_count:
        raise ProbeContractError("tensor.outputs count mismatch")
    for area, entries in (("inputs", inputs), ("outputs", outputs)):
        for index, raw in enumerate(entries):
            item = _expect_object(raw, f"tensor.{area}[{index}]")
            _exact_keys(item, {"index", "name", "shape", "dtype", "quantization"}, f"tensor.{area}[{index}]")
            if _integer(item["index"], f"tensor.{area}[{index}].index") != index:
                raise ProbeContractError(f"tensor.{area} indexes must be contiguous")
            _string(item["name"], f"tensor.{area}[{index}].name")
            _shape(item["shape"], f"tensor.{area}[{index}].shape")
            if item["dtype"] != "FLOAT32" or item["quantization"] != "none":
                raise ProbeContractError(f"tensor.{area}[{index}] must be unquantized FLOAT32")
    expected_input = [1, 224, 224, 3] if task_id == "classification" else [1, 320, 320, 3]
    if input_count != 1 or inputs[0]["shape"] != expected_input:
        raise ProbeContractError("tensor input shape does not match approved model")
    expected_outputs = [[1, 1000]] if task_id == "classification" else [[1, 19206, 90], [1, 19206, 4]]
    if [item["shape"] for item in outputs] != expected_outputs:
        raise ProbeContractError("tensor output shapes do not match approved model")
    expected_normalization = (
        "(RGB-127.0)/128.0" if task_id == "classification" else "(RGB-127.5)/127.5"
    )
    if tensor["normalization"] != expected_normalization:
        raise ProbeContractError("tensor.normalization mismatch")
    _string(tensor["raw_output_semantics"], "tensor.raw_output_semantics")
    return tensor


def _validate_runtime(value: Any, task_id: str) -> dict[str, Any]:
    runtime = _expect_object(value, "runtime")
    keys = {"litert_version", "cpu_threads", "xnnpack", "gpu_profile_id", "gpu_configuration_sha256", "tasks_vision_version"}
    _exact_keys(runtime, keys, "runtime")
    _string(runtime["litert_version"], "runtime.litert_version")
    _integer(runtime["cpu_threads"], "runtime.cpu_threads", minimum=1)
    if not isinstance(runtime["xnnpack"], bool):
        raise ProbeContractError("runtime.xnnpack must be boolean")
    _string(runtime["gpu_profile_id"], "runtime.gpu_profile_id")
    _sha256(runtime["gpu_configuration_sha256"], "runtime.gpu_configuration_sha256")
    tasks = _string(runtime["tasks_vision_version"], "runtime.tasks_vision_version")
    if task_id == "classification" and tasks != "not_used":
        raise ProbeContractError("classification runtime must set tasks_vision_version=not_used")
    if task_id == "detection" and tasks != "1.0.0":
        raise ProbeContractError("detection runtime must pin Tasks Vision 1.0.0")
    return runtime


def _validate_input(value: Any, task_id: str) -> dict[str, Any]:
    input_value = _expect_object(value, "input")
    keys = {"input_id", "kind", "generation_rule", "seed", "url", "filename", "byte_count", "sha256", "decode_contract"}
    _exact_keys(input_value, keys, "input")
    _string(input_value["input_id"], "input.input_id")
    kind = _string(input_value["kind"], "input.kind")
    if kind not in {"deterministic_rgb", "external_image"}:
        raise ProbeContractError("input.kind is unsupported")
    if kind == "deterministic_rgb":
        if input_value["generation_rule"] != "coordinate-rgb-v1":
            raise ProbeContractError("input.generation_rule mismatch")
        _integer(input_value["seed"], "input.seed", minimum=0)
        for key in ("url", "filename", "sha256"):
            if input_value[key] is not None:
                raise ProbeContractError(f"input.{key} must be null for deterministic input")
        if input_value["byte_count"] != 0 or input_value["decode_contract"] != "not_used":
            raise ProbeContractError("deterministic input external fields must be empty")
    else:
        if task_id != "detection":
            raise ProbeContractError("external image is only approved for decoded detection")
        if input_value["generation_rule"] != "not_used" or input_value["seed"] is not None:
            raise ProbeContractError("external image generation fields must be empty")
        actual = (
            _pinned_https_url(input_value["url"], "input.url"),
            _filename(input_value["filename"], "input.filename"),
            _integer(input_value["byte_count"], "input.byte_count", minimum=1),
            _sha256(input_value["sha256"], "input.sha256"),
        )
        expected = (PINNED_SAMPLE.url, PINNED_SAMPLE.filename, PINNED_SAMPLE.byte_count, PINNED_SAMPLE.sha256)
        if actual != expected:
            raise ProbeContractError("input external sample does not match pinned contract")
        if input_value["decode_contract"] != "android-bitmap-argb8888-v1":
            raise ProbeContractError("input.decode_contract mismatch")
    return input_value


def _validate_comparator(value: Any) -> dict[str, Any]:
    comparator = _expect_object(value, "comparator")
    keys = {"comparator_id", "atol", "rtol", "relative_epsilon", "decoded_box_atol_px", "decoded_score_atol", "decoded_order"}
    _exact_keys(comparator, keys, "comparator")
    if comparator["comparator_id"] != "combined-tolerance-v1":
        raise ProbeContractError("comparator.comparator_id mismatch")
    if _number(comparator["atol"], "comparator.atol") != 1e-4:
        raise ProbeContractError("comparator.atol mismatch")
    if _number(comparator["rtol"], "comparator.rtol") != 1e-3:
        raise ProbeContractError("comparator.rtol mismatch")
    if _number(comparator["relative_epsilon"], "comparator.relative_epsilon") != 1e-6:
        raise ProbeContractError("comparator.relative_epsilon mismatch")
    if _number(comparator["decoded_box_atol_px"], "comparator.decoded_box_atol_px") != 2.0:
        raise ProbeContractError("comparator.decoded_box_atol_px mismatch")
    if _number(comparator["decoded_score_atol"], "comparator.decoded_score_atol") != 1e-3:
        raise ProbeContractError("comparator.decoded_score_atol mismatch")
    if comparator["decoded_order"] != "score_desc_label_box":
        raise ProbeContractError("comparator.decoded_order mismatch")
    return comparator


def _validate_execution(value: Any) -> dict[str, Any]:
    execution = _expect_object(value, "execution")
    keys = {"backend", "cold_repetitions", "warm_repetitions", "maximum_duration_ms", "timeout_policy", "cleanup_policy"}
    _exact_keys(execution, keys, "execution")
    if execution["backend"] not in {"CPU", "GPU"}:
        raise ProbeContractError("execution.backend must be CPU or GPU")
    if _integer(execution["cold_repetitions"], "execution.cold_repetitions", minimum=1) != 3:
        raise ProbeContractError("execution.cold_repetitions must be 3")
    if _integer(execution["warm_repetitions"], "execution.warm_repetitions", minimum=1) != 10:
        raise ProbeContractError("execution.warm_repetitions must be 10")
    maximum_duration_ms = _integer(
        execution["maximum_duration_ms"], "execution.maximum_duration_ms", minimum=1
    )
    if maximum_duration_ms > 300_000:
        raise ProbeContractError("execution.maximum_duration_ms must be <= 300000")
    if execution["timeout_policy"] != "bounded-host-and-device-v1":
        raise ProbeContractError("execution.timeout_policy mismatch")
    if execution["cleanup_policy"] != "bounded-delete-and-confirm-v1":
        raise ProbeContractError("execution.cleanup_policy mismatch")
    return execution


def validate_manifest_data(data: Any) -> dict[str, Any]:
    root = _expect_object(data, "manifest")
    _exact_keys(root, {"identity", "target", "model", "tensor", "runtime", "input", "comparator", "execution"}, "manifest")
    identity = _expect_object(root["identity"], "identity")
    _exact_keys(identity, {"schema_version", "protocol_version", "session_id", "created_utc"}, "identity")
    if identity["schema_version"] != SCHEMA_VERSION or identity["protocol_version"] != PROTOCOL_VERSION:
        raise ProbeContractError("identity protocol/schema mismatch")
    _canonical_uuid(identity["session_id"], "identity.session_id")
    created = _string(identity["created_utc"], "identity.created_utc")
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z", created) is None:
        raise ProbeContractError("identity.created_utc must be canonical UTC text")
    target = _validate_target(root["target"])
    model = _validate_model(root["model"])
    task_id = model["task_id"]
    _validate_tensor(root["tensor"], task_id)
    _validate_runtime(root["runtime"], task_id)
    _validate_input(root["input"], task_id)
    _validate_comparator(root["comparator"])
    _validate_execution(root["execution"])
    return root


def read_json(path: Path) -> Any:
    try:
        raw = path.read_bytes()
    except OSError as error:
        raise ProbeContractError(f"cannot read {path}: {error}") from error
    if raw.startswith(b"\xef\xbb\xbf"):
        raise ProbeContractError(f"UTF-8 BOM is not allowed: {path}")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ProbeContractError(f"file is not UTF-8: {path}") from error
    try:
        def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
            result: dict[str, Any] = {}
            for key, value in pairs:
                if key in result:
                    raise ProbeContractError(f"duplicate JSON key in {path}: {key}")
                result[key] = value
            return result

        return json.loads(text, object_pairs_hook=reject_duplicates)
    except json.JSONDecodeError as error:
        raise ProbeContractError(f"invalid JSON in {path}: {error}") from error


def _ensure_regular_file(path: Path, root: Path, location: str) -> Path:
    try:
        root_resolved = root.resolve(strict=True)
        path_resolved = path.resolve(strict=True)
    except OSError as error:
        raise ProbeContractError(f"{location} cannot be resolved: {error}") from error
    try:
        path_resolved.relative_to(root_resolved)
    except ValueError as error:
        raise ProbeContractError(f"{location} escapes input root") from error
    if path.is_symlink() or not path_resolved.is_file():
        raise ProbeContractError(f"{location} must be a regular non-symlink file")
    return path_resolved


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def verify_file(path: Path, root: Path, expected: PinnedFile, location: str) -> Path:
    resolved = _ensure_regular_file(path, root, location)
    stat = resolved.stat()
    if stat.st_size != expected.byte_count:
        raise ProbeContractError(f"{location} byte count mismatch")
    if sha256_file(resolved) != expected.sha256:
        raise ProbeContractError(f"{location} SHA-256 mismatch")
    return resolved


def validate_local_inputs(
    manifest: Mapping[str, Any],
    manifest_path: Path,
    input_root: Path,
    apk: Path,
) -> dict[str, Path]:
    root = input_root.resolve(strict=True)
    if not root.is_dir() or input_root.is_symlink():
        raise ProbeContractError("input root must be a regular directory, not a symlink")
    model = manifest["model"]
    pinned_model = PINNED_MODELS[model["model_id"]]
    model_file = verify_file(root / model["filename"], root, pinned_model, "model file")
    apk_file = _ensure_regular_file(apk, apk.parent, "APK")
    if sha256_file(apk_file) != manifest["target"]["apk_sha256"]:
        raise ProbeContractError("APK SHA-256 mismatch")
    result = {"model": model_file, "apk": apk_file}
    input_value = manifest["input"]
    if input_value["kind"] == "external_image":
        result["input"] = verify_file(root / input_value["filename"], root, PINNED_SAMPLE, "input file")
    manifest_file = _ensure_regular_file(manifest_path, root, "manifest")
    if manifest_file.parent != root or manifest_file.name != "model_probe_manifest.json":
        raise ProbeContractError("manifest must be input-root/model_probe_manifest.json")
    result["manifest"] = manifest_file
    expected_names = {model["filename"], "model_probe_manifest.json"}
    if input_value["kind"] == "external_image":
        expected_names.add(input_value["filename"])
    actual_names = {
        item.name
        for item in root.iterdir()
        if item.name != Path(apk_file).name
    }
    if actual_names != expected_names:
        raise ProbeContractError(
            f"input root fixed file set mismatch: expected={sorted(expected_names)}, actual={sorted(actual_names)}"
        )
    return result


def build_dry_run_plan(
    manifest: Mapping[str, Any],
    manifest_path: Path,
    input_root: Path,
    adb: Path,
    apk: Path,
) -> dict[str, Any]:
    identity = manifest["identity"]
    target = manifest["target"]
    model = manifest["model"]
    input_value = manifest["input"]
    session = identity["session_id"]
    serial = target["adb_serial"]
    package = target["package_name"]
    shared_root = f"{REMOTE_STAGING_ROOT}/{session}"
    app_root = f"{APP_INPUT_ROOT}/{session}"
    host_manifest = manifest_path
    payloads: list[tuple[Path, str]] = [(host_manifest, "model_probe_manifest.json"), (input_root / model["filename"], model["filename"])]
    if input_value["kind"] == "external_image":
        payloads.append((input_root / input_value["filename"], input_value["filename"]))
    adb_prefix = [str(adb), "-s", serial]
    commands: list[list[str]] = []
    commands.append(adb_prefix + ["shell", "mkdir", "-p", shared_root])
    commands.append(adb_prefix + ["shell", "run-as", package, "mkdir", "-p", app_root])
    for host_file, filename in payloads:
        shared_part = f"{shared_root}/{filename}.part"
        app_part = f"{app_root}/{filename}.part"
        app_final = f"{app_root}/{filename}"
        commands.extend(
            [
                adb_prefix + ["push", str(host_file), shared_part],
                adb_prefix + ["shell", "run-as", package, "cp", shared_part, app_part],
                adb_prefix + ["shell", "run-as", package, "sha256sum", app_part],
                adb_prefix + ["shell", "run-as", package, "mv", app_part, app_final],
                adb_prefix + ["shell", "rm", "-f", shared_part],
            ]
        )
    commands.append(
        adb_prefix
        + [
            "shell", "am", "start", "-W", "-n", ENTRY_COMPONENT,
            "-a", f"{PACKAGE_NAME}.action.MODEL_PROBE",
            "--es", "session_id", session,
        ]
    )
    commands.append(adb_prefix + ["shell", "run-as", package, "ls", f"{ARTIFACT_ROOT}/{session}"])
    commands.append(adb_prefix + ["shell", "run-as", package, "rm", "-rf", app_root])
    commands.append(adb_prefix + ["shell", "rm", "-rf", shared_root])
    return {
        "schema_version": SCHEMA_VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "dry_run": True,
        "session_id": session,
        "device_id": target["device_id"],
        "backend": manifest["execution"]["backend"],
        "model_id": model["model_id"],
        "apk": str(apk),
        "commands": commands,
        "network_calls": 0,
        "adb_calls": 0,
        "writes": 0,
    }



def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_json_bytes(raw: bytes, location: str) -> dict[str, Any]:
    if not raw or len(raw) > 4 * 1024 * 1024:
        raise ProbeContractError(f"{location} byte count is invalid")
    if raw.startswith(b"\xef\xbb\xbf"):
        raise ProbeContractError(f"{location} UTF-8 BOM is not allowed")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ProbeContractError(f"{location} is not UTF-8") from error

    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ProbeContractError(f"duplicate JSON key in {location}: {key}")
            result[key] = value
        return result

    try:
        return _expect_object(
            json.loads(text, object_pairs_hook=reject_duplicates),
            location,
        )
    except json.JSONDecodeError as error:
        raise ProbeContractError(f"invalid JSON in {location}: {error}") from error


def _write_atomic_bytes(path: Path, payload: bytes) -> None:
    temporary = path.with_name(path.name + ".part")
    if path.exists() or temporary.exists():
        raise ProbeContractError(f"refusing to replace existing output: {path}")
    try:
        with temporary.open("xb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def _write_atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    payload = (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")
    _write_atomic_bytes(path, payload)


def _remote_sha256(stdout: bytes, location: str) -> str:
    first = _output_tail(stdout).strip().split()
    if not first or SHA256_RE.fullmatch(first[0]) is None:
        raise ProbeContractError(f"{location} did not return a canonical SHA-256")
    return first[0]


def validate_unfinalized_summary(
    summary: Mapping[str, Any],
    manifest: Mapping[str, Any],
) -> dict[str, Any]:
    status = _string(summary.get("status"), "summary.status")
    if status == "failed":
        error_type = _string(summary.get("error_type"), "summary.error_type")
        error = _string(summary.get("error"), "summary.error")
        raise ProbeContractError(f"device probe failed: {error_type}: {error}")
    expected_keys = {
        "schema_version", "protocol_version", "session_id", "device_id", "model_id",
        "backend", "status", "finalized", "elapsed_ns", "details",
    }
    _exact_keys(summary, expected_keys, "summary")
    if summary["schema_version"] != SCHEMA_VERSION or summary["protocol_version"] != PROTOCOL_VERSION:
        raise ProbeContractError("summary protocol/schema mismatch")
    if summary["session_id"] != manifest["identity"]["session_id"]:
        raise ProbeContractError("summary session identity mismatch")
    if summary["device_id"] != manifest["target"]["device_id"]:
        raise ProbeContractError("summary device identity mismatch")
    if summary["model_id"] != manifest["model"]["model_id"]:
        raise ProbeContractError("summary model identity mismatch")
    if summary["backend"] != manifest["execution"]["backend"]:
        raise ProbeContractError("summary backend identity mismatch")
    if status != "seam_smoke_only_unfinalized" or summary["finalized"] is not False:
        raise ProbeContractError("summary must remain seam_smoke_only_unfinalized")
    _integer(summary["elapsed_ns"], "summary.elapsed_ns", minimum=0)
    _expect_object(summary["details"], "summary.details")
    return dict(summary)


def execute_seam(
    manifest: Mapping[str, Any],
    manifest_path: Path,
    input_root: Path,
    adb: Path,
    apk: Path,
    output_root: Path,
    serial: str,
    *,
    poll_interval_seconds: float = 0.25,
    host_grace_seconds: float = 15.0,
    process_runner: ProcessRunner = _default_process_runner,
    monotonic: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    if serial != manifest["target"]["adb_serial"]:
        raise ProbeContractError("--serial does not match target.adb_serial")
    if poll_interval_seconds <= 0 or not 0 <= host_grace_seconds <= 60:
        raise ProbeContractError("invalid host poll/grace interval")
    files = validate_local_inputs(manifest, manifest_path, input_root, apk)
    adb_root = adb.parent if str(adb.parent) else Path.cwd()
    adb_file = _ensure_regular_file(adb, adb_root, "ADB executable")

    output_base = output_root.resolve(strict=True)
    if not output_base.is_dir() or output_root.is_symlink():
        raise ProbeContractError("output root must be an existing non-symlink directory")
    session = manifest["identity"]["session_id"]
    device_id = manifest["target"]["device_id"]
    package = manifest["target"]["package_name"]
    session_output = output_base / session
    if session_output.exists():
        raise ProbeContractError("host session output already exists")
    session_output.mkdir()

    shared_root = f"{REMOTE_STAGING_ROOT}/{session}"
    app_root = f"{APP_INPUT_ROOT}/{session}"
    device_output_root = f"{ARTIFACT_ROOT}/{session}"
    device_summary = f"{device_output_root}/summary.json"
    adb_prefix = [str(adb_file), "-s", serial]
    started_utc = _utc_now()
    command_count = 0
    activity_dispatched = False
    summary_pulled = False
    summary_sha256: str | None = None
    cleanup_errors: list[str] = []
    primary_error: Exception | None = None
    result: dict[str, Any] | None = None

    def run(
        arguments: Sequence[str],
        timeout_seconds: float,
        allowed_returncodes: frozenset[int] = frozenset({0}),
    ) -> ProcessResult:
        nonlocal command_count
        command_count += 1
        return process_runner(
            adb_prefix + [str(part) for part in arguments],
            timeout_seconds,
            allowed_returncodes,
        )

    try:
        state = run(["get-state"], 10.0)
        if _output_tail(state.stdout).strip() != "device":
            raise ProbeContractError("ADB target is not in device state")
        run(["shell", "test", "!", "-e", shared_root], 10.0)
        run(["shell", "run-as", package, "test", "!", "-e", app_root], 10.0)
        run(["shell", "run-as", package, "test", "!", "-e", device_output_root], 10.0)
        run(["shell", "mkdir", "-p", shared_root], 10.0)
        run(["shell", "run-as", package, "mkdir", "-p", app_root], 10.0)

        payloads: list[tuple[Path, str]] = [
            (files["manifest"], "model_probe_manifest.json"),
            (files["model"], manifest["model"]["filename"]),
        ]
        if "input" in files:
            payloads.append((files["input"], manifest["input"]["filename"]))
        for host_file, filename in payloads:
            expected_sha = sha256_file(host_file)
            shared_part = f"{shared_root}/{filename}.part"
            app_part = f"{app_root}/{filename}.part"
            app_final = f"{app_root}/{filename}"
            run(["push", str(host_file), shared_part], 120.0)
            shared_hash = run(["shell", "sha256sum", shared_part], 15.0)
            if _remote_sha256(shared_hash.stdout, f"shared staging {filename}") != expected_sha:
                raise ProbeContractError(f"shared staging SHA-256 mismatch: {filename}")
            run(["shell", "run-as", package, "cp", shared_part, app_part], 30.0)
            app_hash = run(["shell", "run-as", package, "sha256sum", app_part], 15.0)
            if _remote_sha256(app_hash.stdout, f"app staging {filename}") != expected_sha:
                raise ProbeContractError(f"app staging SHA-256 mismatch: {filename}")
            run(["shell", "run-as", package, "mv", app_part, app_final], 15.0)
            final_hash = run(["shell", "run-as", package, "sha256sum", app_final], 15.0)
            if _remote_sha256(final_hash.stdout, f"app final {filename}") != expected_sha:
                raise ProbeContractError(f"app final SHA-256 mismatch: {filename}")
            run(["shell", "rm", "-f", shared_part], 10.0)

        dispatch = run(
            [
                "shell", "am", "start", "-W", "-n", ENTRY_COMPONENT,
                "-a", f"{PACKAGE_NAME}.action.MODEL_PROBE",
                "--es", "session_id", session,
            ],
            30.0,
        )
        dispatch_text = _output_tail(dispatch.stdout) + "\n" + _output_tail(dispatch.stderr)
        if "Error:" in dispatch_text or "Status: error" in dispatch_text:
            raise ProbeContractError(f"Activity dispatch failed: {dispatch_text.strip()}")
        activity_dispatched = True

        deadline = (
            monotonic()
            + manifest["execution"]["maximum_duration_ms"] / 1000.0
            + host_grace_seconds
        )
        while True:
            ready = run(
                ["shell", "run-as", package, "test", "-s", device_summary],
                10.0,
                frozenset({0, 1}),
            )
            if ready.returncode == 0:
                break
            remaining = deadline - monotonic()
            if remaining <= 0:
                raise ProbeContractError("timed out waiting for device summary")
            sleep(min(poll_interval_seconds, remaining))

        pulled = run(
            ["exec-out", "run-as", package, "cat", device_summary],
            30.0,
        )
        summary_bytes = pulled.stdout
        summary = _parse_json_bytes(summary_bytes, "device summary")
        _write_atomic_bytes(session_output / "summary.json", summary_bytes)
        summary_pulled = True
        summary_sha256 = hashlib.sha256(summary_bytes).hexdigest()
        validate_unfinalized_summary(summary, manifest)
        result = {
            "status": "completed_unfinalized",
            "schema_version": SCHEMA_VERSION,
            "protocol_version": PROTOCOL_VERSION,
            "session_id": session,
            "device_id": device_id,
            "model_id": manifest["model"]["model_id"],
            "backend": manifest["execution"]["backend"],
            "finalized": False,
            "device_summary": str(session_output / "summary.json"),
            "device_summary_sha256": summary_sha256,
        }
    except Exception as error:
        primary_error = error
    finally:
        cleanup_commands = [
            (["shell", "run-as", package, "rm", "-rf", app_root], 20.0),
            (["shell", "rm", "-rf", shared_root], 20.0),
            (["shell", "run-as", package, "test", "!", "-e", app_root], 10.0),
            (["shell", "test", "!", "-e", shared_root], 10.0),
        ]
        for arguments, timeout_seconds in cleanup_commands:
            try:
                run(arguments, timeout_seconds)
            except Exception as cleanup_error:
                cleanup_errors.append(str(cleanup_error))

        host_status = (
            "failed"
            if primary_error is not None
            else ("cleanup_failed" if cleanup_errors else "completed_unfinalized")
        )
        host_record = {
            "schema_version": SCHEMA_VERSION,
            "protocol_version": PROTOCOL_VERSION,
            "session_id": session,
            "device_id": device_id,
            "model_id": manifest["model"]["model_id"],
            "backend": manifest["execution"]["backend"],
            "status": host_status,
            "finalized": False,
            "started_utc": started_utc,
            "finished_utc": _utc_now(),
            "command_count": command_count,
            "activity_dispatched": activity_dispatched,
            "summary_pulled": summary_pulled,
            "device_summary_sha256": summary_sha256,
            "input_cleanup_confirmed": not cleanup_errors,
            "error": None if primary_error is None else str(primary_error),
            "suppressed_cleanup_errors": cleanup_errors,
        }
        try:
            _write_atomic_json(session_output / "host_execution.json", host_record)
        except Exception as record_error:
            if primary_error is None:
                primary_error = record_error
            else:
                cleanup_errors.append(f"host record write failed: {record_error}")

    if primary_error is not None:
        suffix = (
            f"; suppressed cleanup errors={cleanup_errors!r}" if cleanup_errors else ""
        )
        raise ProbeContractError(f"{primary_error}{suffix}") from primary_error
    if cleanup_errors:
        raise ProbeContractError(f"probe completed but cleanup failed: {cleanup_errors!r}")
    if result is None:
        raise ProbeContractError("probe completed without a result")
    result["host_execution"] = str(session_output / "host_execution.json")
    return result


def validate_artifacts(root: Path, session_id: str, device_id: str) -> dict[str, Any]:
    session_id = _canonical_uuid(session_id, "session_id")
    if DEVICE_ID_RE.fullmatch(device_id) is None:
        raise ProbeContractError("device_id has invalid characters")
    resolved_root = root.resolve(strict=True)
    if not resolved_root.is_dir() or root.is_symlink():
        raise ProbeContractError("artifact root must be a regular directory")
    actual: set[str] = set()
    for path in resolved_root.rglob("*"):
        if path.is_symlink():
            relative = path.relative_to(resolved_root).as_posix()
            raise ProbeContractError(f"artifact path must not be a symlink: {relative}")
        if path.is_dir():
            continue
        relative = path.relative_to(resolved_root).as_posix()
        if not path.is_file():
            raise ProbeContractError(f"artifact must be a regular file: {relative}")
        actual.add(relative)
    if actual != ARTIFACT_FILES:
        raise ProbeContractError(
            f"artifact fixed set mismatch: missing={sorted(ARTIFACT_FILES-actual)}, extra={sorted(actual-ARTIFACT_FILES)}"
        )
    provenance = _expect_object(read_json(resolved_root / "provenance.json"), "provenance")
    _exact_keys(provenance, {"schema_version", "protocol_version", "session_id", "device_id", "artifact_set"}, "provenance")
    if provenance["schema_version"] != SCHEMA_VERSION or provenance["protocol_version"] != PROTOCOL_VERSION:
        raise ProbeContractError("provenance protocol/schema mismatch")
    if provenance["session_id"] != session_id or provenance["device_id"] != device_id:
        raise ProbeContractError("provenance identity mismatch")
    artifact_set = provenance["artifact_set"]
    if not isinstance(artifact_set, list):
        raise ProbeContractError("provenance.artifact_set must be an array")
    expected_entries = ARTIFACT_FILES - {"provenance.json"}
    seen: set[str] = set()
    for index, raw in enumerate(artifact_set):
        entry = _expect_object(raw, f"provenance.artifact_set[{index}]")
        _exact_keys(entry, {"path", "byte_count", "sha256"}, f"provenance.artifact_set[{index}]")
        relative = _string(entry["path"], f"provenance.artifact_set[{index}].path")
        if PurePosixPath(relative).is_absolute() or relative not in expected_entries or relative in seen:
            raise ProbeContractError(f"invalid provenance path: {relative}")
        seen.add(relative)
        file_path = resolved_root / relative
        if file_path.stat().st_size != _integer(entry["byte_count"], f"provenance.artifact_set[{index}].byte_count"):
            raise ProbeContractError(f"artifact byte count mismatch: {relative}")
        if sha256_file(file_path) != _sha256(entry["sha256"], f"provenance.artifact_set[{index}].sha256"):
            raise ProbeContractError(f"artifact SHA-256 mismatch: {relative}")
    if seen != expected_entries:
        raise ProbeContractError("provenance artifact set is incomplete")
    for filename in ("metadata.json", "raw_equivalence.json", "decoded_results.json", "memory.json", "delegate_evidence.json", "summary.json"):
        value = _expect_object(read_json(resolved_root / filename), filename)
        if value.get("session_id") != session_id or value.get("device_id") != device_id:
            raise ProbeContractError(f"artifact identity mismatch: {filename}")
    event_bytes = (resolved_root / "events.jsonl").read_bytes()
    if event_bytes.startswith(b"\xef\xbb\xbf"):
        raise ProbeContractError("events.jsonl UTF-8 BOM is not allowed")
    try:
        event_text = event_bytes.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ProbeContractError("events.jsonl is not UTF-8") from error
    event_lines = event_text.splitlines()
    if not event_lines or any(not line for line in event_lines):
        raise ProbeContractError("events.jsonl must contain nonblank records")
    for index, line in enumerate(event_lines):
        try:
            event = _expect_object(json.loads(line), f"events.jsonl line {index + 1}")
        except json.JSONDecodeError as error:
            raise ProbeContractError(f"invalid events.jsonl line {index + 1}") from error
        if event.get("session_id") != session_id or event.get("device_id") != device_id:
            raise ProbeContractError(f"events.jsonl identity mismatch at line {index + 1}")
    return {"status": "valid", "session_id": session_id, "device_id": device_id, "file_count": len(actual)}


def _load_manifest(path: Path) -> dict[str, Any]:
    return validate_manifest_data(read_json(path))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate-input", help="validate manifest and exact local bytes")
    validate.add_argument("--manifest", type=Path, required=True)
    validate.add_argument("--input-root", type=Path, required=True)
    validate.add_argument("--apk", type=Path, required=True)
    plan = sub.add_parser("plan", help="print fixed argv without network, ADB, or writes")
    plan.add_argument("--manifest", type=Path, required=True)
    plan.add_argument("--input-root", type=Path, required=True)
    plan.add_argument("--apk", type=Path, required=True)
    plan.add_argument("--adb", type=Path, required=True)
    plan.add_argument("--serial", required=True)
    plan.add_argument("--dry-run", action="store_true", required=True)
    execute = sub.add_parser(
        "execute-seam",
        help="run one bounded ADB seam probe and preserve unfinalized host evidence",
    )
    execute.add_argument("--manifest", type=Path, required=True)
    execute.add_argument("--input-root", type=Path, required=True)
    execute.add_argument("--apk", type=Path, required=True)
    execute.add_argument("--adb", type=Path, required=True)
    execute.add_argument("--serial", required=True)
    execute.add_argument("--output-root", type=Path, required=True)
    execute.add_argument("--poll-interval-ms", type=int, default=250)
    execute.add_argument("--host-grace-ms", type=int, default=15_000)
    artifacts = sub.add_parser("validate-artifacts", help="validate exact finalized artifact set")
    artifacts.add_argument("--root", type=Path, required=True)
    artifacts.add_argument("--session-id", required=True)
    artifacts.add_argument("--device-id", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "validate-artifacts":
            result = validate_artifacts(args.root, args.session_id, args.device_id)
        else:
            manifest = _load_manifest(args.manifest)
            if args.command == "validate-input":
                files = validate_local_inputs(manifest, args.manifest, args.input_root, args.apk)
                result = {
                    "status": "valid",
                    "session_id": manifest["identity"]["session_id"],
                    "device_id": manifest["target"]["device_id"],
                    "verified_files": {key: str(value) for key, value in files.items()},
                }
            elif args.command == "plan":
                if args.serial != manifest["target"]["adb_serial"]:
                    raise ProbeContractError("--serial does not match target.adb_serial")
                result = build_dry_run_plan(
                    manifest, args.manifest, args.input_root, args.adb, args.apk
                )
            else:
                result = execute_seam(
                    manifest,
                    args.manifest,
                    args.input_root,
                    args.adb,
                    args.apk,
                    args.output_root,
                    args.serial,
                    poll_interval_seconds=args.poll_interval_ms / 1000.0,
                    host_grace_seconds=args.host_grace_ms / 1000.0,
                )
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
        return 0
    except (ProbeContractError, OSError) as error:
        print(f"error: {error}", file=sys.stderr, flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
