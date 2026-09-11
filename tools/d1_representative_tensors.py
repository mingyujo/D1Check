#!/usr/bin/env python3
"""Build and validate deterministic host-preprocessed MobileNet tensor sets.

This tool never downloads images. Imagenette is a ten-class diagnostic subset and
must not be reported as full ImageNet accuracy.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import struct
import sys
from typing import Any, Iterable


MAGIC = b"D1TSET01"
FORMAT_VERSION = "d1-representative-tensor-set-v1"
SCHEMA_VERSION = 1
PREPROCESSING_VERSION = "tf-slim-mobilenet-v1-eval-pillow-v1"
INPUT_SHAPE = [1, 224, 224, 3]
INPUT_DTYPE = "FLOAT32"
INPUT_ENDIAN = "LITTLE"
CENTRAL_CROP_FRACTION = 0.875
IMAGENETTE_WNIDS = (
    "n01440764", "n02102040", "n02979186", "n03000684", "n03028079",
    "n03394916", "n03417042", "n03425413", "n03445777", "n03888257",
)
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}


class TensorSetError(RuntimeError):
    pass


def canonical_json_bytes(value: dict[str, Any]) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")


def preprocessing_canonical_bytes(value: dict[str, Any]) -> bytes:
    """Canonical v1 bytes shared with Android; excludes the declared hash field."""
    unhashed = dict(value)
    unhashed.pop("configuration_sha256", None)
    return canonical_json_bytes(unhashed)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def gpu_profile_payload(profile_id: str) -> dict[str, Any]:
    if profile_id == "gpu-compat-default-v1":
        precision = True
    elif profile_id == "gpu-fp32-strict-v1":
        precision = False
    else:
        raise TensorSetError(f"unsupported GPU profile: {profile_id}")
    canonical = "|".join((
        f"profile_id={profile_id}",
        f"precision_loss_allowed={str(precision).lower()}",
        "quantized_models_allowed=true",
        "inference_preference=FAST_SINGLE_ANSWER",
        "force_backend=UNSET",
    ))
    return {
        "profile_id": profile_id,
        "configuration_sha256": sha256_bytes(canonical.encode("utf-8")),
        "precision_loss_allowed": precision,
        "quantized_models_allowed": True,
        "inference_preference": "FAST_SINGLE_ANSWER",
        "force_backend": "UNSET",
        "actual_fp16_execution": "unknown_not_exposed_by_litert_api",
    }


def read_tf_slim_wnid_map(path: Path) -> tuple[dict[str, int], str]:
    raw = path.read_bytes()
    lines = [line.strip() for line in raw.decode("utf-8-sig").splitlines() if line.strip()]
    if len(lines) != 1000 or len(set(lines)) != 1000:
        raise TensorSetError("TF-Slim WNID mapping must contain 1000 unique non-empty lines")
    if any(not line.startswith("n") for line in lines):
        raise TensorSetError("TF-Slim WNID mapping contains an invalid WNID")
    return {wnid: index + 1 for index, wnid in enumerate(lines)}, sha256_bytes(raw)


def stratified_selection(
    split_dir: Path, sample_count: int, seed: int,
) -> list[tuple[str, Path]]:
    if sample_count < len(IMAGENETTE_WNIDS) or sample_count % len(IMAGENETTE_WNIDS):
        raise TensorSetError("Imagenette sample count must be a positive multiple of 10")
    per_class = sample_count // len(IMAGENETTE_WNIDS)
    selected: list[tuple[str, Path]] = []
    for class_index, wnid in enumerate(IMAGENETTE_WNIDS):
        directory = split_dir / wnid
        if not directory.is_dir():
            raise TensorSetError(f"missing Imagenette class directory: {directory}")
        candidates = sorted(
            path for path in directory.iterdir()
            if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
        )
        if len(candidates) < per_class:
            raise TensorSetError(
                f"Imagenette class {wnid} has {len(candidates)} images; need {per_class}"
            )
        class_rng = random.Random(f"{seed}:{class_index}:{wnid}")
        class_rng.shuffle(candidates)
        selected.extend((wnid, path) for path in sorted(candidates[:per_class]))
    return sorted(selected, key=lambda item: (item[0], item[1].name.casefold()))


def preprocessing_configuration(pillow_version: str) -> dict[str, Any]:
    return {
        "version": PREPROCESSING_VERSION,
        "implementation": "Pillow",
        "implementation_version": pillow_version,
        "rgb_order": "RGB",
        "exif_orientation_policy": "ImageOps.exif_transpose_before_RGB_conversion",
        "central_crop_fraction": CENTRAL_CROP_FRACTION,
        "central_crop_rounding": "symmetric_floor_offset_keep_remainder",
        "resize": {
            "width": 224,
            "height": 224,
            "algorithm": "Pillow.Image.Resampling.BILINEAR",
            "tf_slim_reference": "tf.image.resize_bilinear_align_corners_false",
            "implementation_equivalence_claimed": False,
            "limitation": "Pillow and TensorFlow bilinear sampling kernels are not byte-identical",
        },
        "normalization": "(pixel/255.0 - 0.5) * 2.0",
        "normalization_range": [-1.0, 1.0],
        "shape": INPUT_SHAPE,
        "dtype": INPUT_DTYPE,
        "endian": INPUT_ENDIAN,
    }


def preprocess_image(path: Path, output_size: int = 224) -> bytes:
    try:
        from PIL import Image, ImageOps
    except ImportError as error:
        raise TensorSetError("Pillow is required; install it explicitly before preparing images") from error
    with Image.open(path) as source:
        image = ImageOps.exif_transpose(source).convert("RGB")
        width, height = image.size
        x_offset = int((width - width * CENTRAL_CROP_FRACTION) / 2.0)
        y_offset = int((height - height * CENTRAL_CROP_FRACTION) / 2.0)
        image = image.crop((x_offset, y_offset, width - x_offset, height - y_offset))
        image = image.resize((output_size, output_size), Image.Resampling.BILINEAR)
        pixels = image.tobytes()
    output = bytearray(len(pixels) * 4)
    for index, channel in enumerate(pixels):
        struct.pack_into("<f", output, index * 4, (channel / 255.0 - 0.5) * 2.0)
    return bytes(output)


def build_tensor_set(
    dataset_dir: Path,
    output: Path,
    label_map: Path,
    sample_count: int,
    seed: int,
    dataset_version: str,
    dataset_source_url: str,
    dataset_license: str,
) -> dict[str, Any]:
    if output.exists():
        raise TensorSetError(f"refusing to overwrite existing tensor-set: {output}")
    split_dir = dataset_dir / "val" if (dataset_dir / "val").is_dir() else dataset_dir
    wnid_map, label_hash = read_tf_slim_wnid_map(label_map)
    missing = sorted(set(IMAGENETTE_WNIDS) - set(wnid_map))
    if missing:
        raise TensorSetError(f"Imagenette WNIDs missing from label map: {missing}")
    selected = stratified_selection(split_dir, sample_count, seed)
    try:
        import PIL
    except ImportError as error:
        raise TensorSetError("Pillow is required; no dependency is downloaded automatically") from error
    preprocessing = preprocessing_configuration(PIL.__version__)
    preprocessing["configuration_sha256"] = sha256_bytes(
        preprocessing_canonical_bytes(preprocessing)
    )
    payload_parts: list[bytes] = []
    samples: list[dict[str, Any]] = []
    offset = 0
    for tensor_index, (wnid, path) in enumerate(selected):
        tensor = preprocess_image(path)
        relative = path.relative_to(split_dir).as_posix()
        samples.append({
            "tensor_index": tensor_index,
            "sample_id": relative,
            "source_image_sha256": sha256_file(path),
            "ground_truth_wnid": wnid,
            "mapped_output_index": wnid_map[wnid],
            "tensor_sha256": sha256_bytes(tensor),
            "byte_offset": offset,
            "byte_length": len(tensor),
        })
        payload_parts.append(tensor)
        offset += len(tensor)
    payload = b"".join(payload_parts)
    header: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "format_version": FORMAT_VERSION,
        "dataset": {
            "name": "Imagenette",
            "version": dataset_version,
            "split": "validation",
            "scope": "ten_class_imagenet_subset_not_full_imagenet_accuracy",
            "source_url": dataset_source_url,
            "license": dataset_license,
        },
        "selection": {
            "seed": seed,
            "stratification": "equal_count_per_wnid",
            "sample_count": sample_count,
            "selected_sample_ids": [sample["sample_id"] for sample in samples],
        },
        "label_mapping": {
            "format": "tf_slim_imagenet_1000_wnids_one_per_line",
            "file_sha256": label_hash,
            "background_index": 0,
            "class_index_rule": "wnid_line_zero_based_plus_one",
        },
        "preprocessing": preprocessing,
        "tensor": {
            "shape": INPUT_SHAPE,
            "dtype": INPUT_DTYPE,
            "endian": INPUT_ENDIAN,
            "count": sample_count,
            "bytes_per_tensor": 224 * 224 * 3 * 4,
        },
        "samples": samples,
        "tensor_set_sha256": sha256_bytes(payload),
    }
    header_bytes = canonical_json_bytes(header)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("xb") as stream:
            stream.write(MAGIC)
            stream.write(struct.pack("<I", len(header_bytes)))
            stream.write(header_bytes)
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)
    return validate_tensor_set(output)


def validate_tensor_set(
    path: Path, expected_container_sha256: str | None = None,
) -> dict[str, Any]:
    container_hash = sha256_file(path)
    if expected_container_sha256 is not None:
        normalized_expected = expected_container_sha256.lower()
        if container_hash != normalized_expected:
            raise TensorSetError(
                "tensor-set container SHA-256 mismatch: "
                f"expected={normalized_expected} recomputed={container_hash}"
            )
    with path.open("rb") as stream:
        if stream.read(8) != MAGIC:
            raise TensorSetError("tensor-set magic is invalid")
        length_bytes = stream.read(4)
        if len(length_bytes) != 4:
            raise TensorSetError("tensor-set header length is truncated")
        header_length = struct.unpack("<I", length_bytes)[0]
        if not 2 <= header_length <= 8 * 1024 * 1024:
            raise TensorSetError("tensor-set header length is invalid")
        raw_header = stream.read(header_length)
        if len(raw_header) != header_length:
            raise TensorSetError("tensor-set header is truncated")
        try:
            header = json.loads(raw_header.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise TensorSetError(f"tensor-set header JSON is invalid: {error}") from error
        payload = stream.read()
    if header.get("schema_version") != SCHEMA_VERSION or header.get("format_version") != FORMAT_VERSION:
        raise TensorSetError("unsupported tensor-set schema or format")
    tensor = header.get("tensor")
    samples = header.get("samples")
    if not isinstance(tensor, dict) or not isinstance(samples, list):
        raise TensorSetError("tensor-set metadata is incomplete")
    if tensor.get("shape") != INPUT_SHAPE or tensor.get("dtype") != INPUT_DTYPE or tensor.get("endian") != INPUT_ENDIAN:
        raise TensorSetError("tensor-set shape/dtype/endian mismatch")
    count = tensor.get("count")
    bytes_per_tensor = tensor.get("bytes_per_tensor")
    if not isinstance(count, int) or count <= 0 or len(samples) != count:
        raise TensorSetError("tensor-set sample count mismatch")
    if bytes_per_tensor != 224 * 224 * 3 * 4 or len(payload) != count * bytes_per_tensor:
        raise TensorSetError("tensor-set payload is truncated or has trailing bytes")
    if sha256_bytes(payload) != header.get("tensor_set_sha256"):
        raise TensorSetError("tensor-set payload SHA-256 mismatch")
    selection = header.get("selection")
    label_mapping = header.get("label_mapping")
    dataset = header.get("dataset")
    if not isinstance(selection, dict) or not isinstance(label_mapping, dict):
        raise TensorSetError("selection or label mapping metadata is missing")
    if not isinstance(dataset, dict) or dataset.get("scope") != (
        "ten_class_imagenet_subset_not_full_imagenet_accuracy"
    ):
        raise TensorSetError("dataset scope is missing or overclaims Imagenette")
    if label_mapping.get("background_index") != 0:
        raise TensorSetError("label mapping must reserve output index 0 for background")
    selected_ids = selection.get("selected_sample_ids")
    if not isinstance(selected_ids, list) or len(selected_ids) != count:
        raise TensorSetError("selected sample ID inventory does not match tensor count")
    if len(set(selected_ids)) != count:
        raise TensorSetError("selected sample IDs contain duplicates")
    for index, sample in enumerate(samples):
        start = index * bytes_per_tensor
        data = payload[start:start + bytes_per_tensor]
        if sample.get("tensor_index") != index or sample.get("byte_offset") != start:
            raise TensorSetError(f"tensor-set index/offset mismatch at {index}")
        if sample.get("byte_length") != bytes_per_tensor or sha256_bytes(data) != sample.get("tensor_sha256"):
            raise TensorSetError(f"tensor SHA-256 mismatch at {index}")
        if not 1 <= int(sample.get("mapped_output_index", 0)) <= 1000:
            raise TensorSetError(f"invalid background-offset output index at {index}")
        if sample.get("sample_id") != selected_ids[index]:
            raise TensorSetError(f"selected sample ID mismatch at {index}")
        source_hash = str(sample.get("source_image_sha256", "")).lower()
        if len(source_hash) != 64 or any(char not in "0123456789abcdef" for char in source_hash):
            raise TensorSetError(f"invalid source image SHA-256 at {index}")
    preprocessing = header.get("preprocessing", {})
    configuration_hash = preprocessing.get("configuration_sha256")
    recomputed_configuration_hash = sha256_bytes(
        preprocessing_canonical_bytes(preprocessing)
    )
    if configuration_hash != recomputed_configuration_hash:
        raise TensorSetError(
            "preprocessing configuration SHA-256 mismatch: "
            f"declared={configuration_hash} expected=not_provided "
            f"recomputed={recomputed_configuration_hash}"
        )
    return {
        "path": str(path.resolve()),
        "container_sha256": container_hash,
        "header": header,
        "tensor_set_sha256": header["tensor_set_sha256"],
        "label_mapping_file_sha256": header["label_mapping"]["file_sha256"],
        "preprocessing_configuration_sha256": configuration_hash,
        "input_count": count,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-dir", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--label-map", type=Path)
    parser.add_argument("--sample-count", type=int, default=40)
    parser.add_argument("--seed", type=int, default=0x12345678)
    parser.add_argument("--dataset-version")
    parser.add_argument(
        "--dataset-source-url",
        default="https://s3.amazonaws.com/fast-ai-imageclas/imagenette2-320.tgz",
    )
    parser.add_argument("--dataset-license")
    parser.add_argument("--validate", type=Path)
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.validate is not None:
        result = validate_tensor_set(args.validate)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    missing = [
        name for name, value in (
            ("--dataset-dir", args.dataset_dir), ("--output", args.output),
            ("--label-map", args.label_map), ("--dataset-version", args.dataset_version),
            ("--dataset-license", args.dataset_license),
        ) if value is None
    ]
    if missing:
        raise TensorSetError("build mode requires " + ", ".join(missing))
    result = build_tensor_set(
        args.dataset_dir, args.output, args.label_map, args.sample_count, args.seed,
        args.dataset_version, args.dataset_source_url, args.dataset_license,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (TensorSetError, OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1)
