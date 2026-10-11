"""Shared constants and helpers for the S26 Q20 (대표 입력 20장 품질) host tools.

Registration: d1sim/docs/품질20장_사전등록_v1.md (blob 48b59382…, commit a56ebbf; OneDrive 원본과 바이트 동일) — §1 inputs as received,
§2 three backends (CPU CompiledModel XNNPACK · GPU OpenCL FP32 requested · NPU DispatchDelegate AOT) · 2 runs per image, §3 metrics/verdicts.
Nothing here opens a reference output value; q20_judge.py reads them only when it judges (committed before the phone run).

Tie rule (등록 §3 top-k, written before results): score descending, then class index ascending — identical to the A24 decoder
(tools/d1_classification_reference 64~65, request-runner ClassificationDecoder.top5) and to the reference JSON's decoder.ordering.
Cosine with a zero-norm vector (or any non-finite element) = None and is reported as "계산 불가" (not a 필수 failure).
"""
from __future__ import annotations

import datetime as dt
import hashlib
import importlib.util
import json
import math
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
MIXREQ_DIR = REPO / "s26" / "tools" / "mixreq"

# --- app (quality-runner) -----------------------------------------------------------------------------------------------------
APP_PACKAGE = "com.example.d1check.qualityrunner"
APP_ACTIVITY = f"{APP_PACKAGE}/.QualityActivity"
APP_OUTPUT_DIR = f"/storage/emulated/0/Android/data/{APP_PACKAGE}/files/quality20"
MEASURE_APP_PACKAGE = "com.example.d1check.npurunner"     # never installed / stopped / reinstalled by these tools
MIXREQ_APP_PACKAGE = "com.example.d1check.requestrunner"  # idem
DEVICE_ROOT = "/data/local/tmp/quality20"
LOG_TAG = "D1Q20"
PROTOCOL = "s26-q20-manifest-v1"
EXPECTED_MODEL = "SM-S942N"
BACKENDS = ("CPU", "GPU", "NPU")      # 등록 §2 order: CPU first
RUNS_PER_IMAGE = 2
SAMPLE_COUNT = 20
INPUT_BYTES = 1 * 224 * 224 * 3 * 4   # 602,112
OUTPUT_ELEMENTS = 1000

# --- registered inputs / models (SHA-256) -------------------------------------------------------------------------------------
ZIP_SHA256 = "3bf4659997c2ccd188563d4ee0cdf42c174ebaf175ad58eaab3d28128dd8dcdd"
ZIP_BYTES = 3_807_484
QUALITY_REFERENCE_SHA256 = "148e3be8065659b2d305d03a10924ac657a1ee8b4a5a17b14613c584e2cc66f4"
ORIGINAL_MODEL_SHA256 = "6c7ab0a6e5dcbf38a8c33b960996a55a3b4300b36a018c4545801de3a3c8bde0"   # efficientnet_lite0.tflite (CPU · GPU)
AOT_MODEL_SHA256 = "311e4aac8fa1d8def4e13359c731ddc1c92f4c9ff7074e0d3860b036df8b2a31"        # efficientnet_lite0_Samsung_E9965.tflite (NPU)
LABELS_SHA256 = "e697a491aa735cc6c2aaf982f8e86e8fc7b0a1ea7750a2cc6a2bdfc1e109012f"           # labels_without_background.txt (0-based, 1000)
DISPATCH_SO_SHA256 = "f08656a642c46e7b06b64fbe1e0800de9e73b0b69c1641b87995562b4a16840f"
REGISTRATION = dict(file="d1sim/docs/품질20장_사전등록_v1.md", blob_sha256="48b593828af36a1b98830dde9d8da0224ce5b881185f69cdaa5d9ede8317d670",
                    commit="a56ebbf", onedrive=r"D1_ondevice\sim\품질20장_사전등록_v1.md")

# --- 등록 §3 FP32 tolerance: |cand − ref| ≤ 1e-4 + 1e-3·|ref| ---------------------------------------------------------------
TOL_ABS = 1e-4
TOL_REL = 1e-3
TOP_K = 5

DEFAULT_INPUTS_DIR = Path(r"C:\Users\rhoyo\OneDrive\문서\Mine\26-2\산공학회\D1_ondevice\quality_inputs_1006\extracted")
DEFAULT_ORIGINAL_MODEL = REPO / "local_models" / "efficientnet_lite0.tflite"
DEFAULT_AOT_MODEL = REPO / "npu-runner" / "src" / "main" / "assets" / "models" / "efficientnet_lite0_Samsung_E9965.tflite"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path | str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path | str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path | str, value, indent: int | None = 2) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(value, f, ensure_ascii=False, indent=indent, allow_nan=True)
        f.write("\n")


def now_iso() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def read_f32le(path: Path | str, expected_elements: int | None = None) -> list[float]:
    raw = Path(path).read_bytes()
    if len(raw) % 4:
        raise ValueError(f"{path}: {len(raw)} bytes is not a multiple of 4")
    values = list(struct.unpack("<%df" % (len(raw) // 4), raw))
    if expected_elements is not None and len(values) != expected_elements:
        raise ValueError(f"{path}: {len(values)} elements != {expected_elements}")
    return values


def f32le_bytes(values: list[float]) -> bytes:
    return struct.pack("<%df" % len(values), *values)


def topk(values: list[float], k: int = TOP_K) -> list[tuple[int, float]]:
    """Score descending, then class index ascending (tie rule, fixed before results). NaN compares false, so a NaN vector is
    judged by the 필수 finite check before this is ever used for a verdict."""
    order = sorted(range(len(values)), key=lambda i: (-values[i], i))[:k]
    return [(i, values[i]) for i in order]


def cosine(a: list[float], b: list[float]) -> float | None:
    if len(a) != len(b) or not a or not all(math.isfinite(x) for x in a) or not all(math.isfinite(y) for y in b):
        return None
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return None
    return dot / (na * nb)


def tolerance_violations(cand: list[float], ref: list[float]) -> int:
    return sum(1 for c, r in zip(cand, ref) if not (abs(c - r) <= TOL_ABS + TOL_REL * abs(r)))


def load_mixreq_validate():
    """Import s26/tools/mixreq/mixreq_validate.py (R2, frozen) so the evidence condition functions are reused, never re-typed."""
    if str(MIXREQ_DIR) not in sys.path:
        sys.path.insert(0, str(MIXREQ_DIR))
    spec = importlib.util.spec_from_file_location("mixreq_validate", MIXREQ_DIR / "mixreq_validate.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("mixreq_validate", module)
    spec.loader.exec_module(module)
    return module


# --- tensor manifest (조민규 zip) --------------------------------------------------------------------------------------------
def load_tensor_manifest(inputs_dir: Path) -> dict:
    m = read_json(inputs_dir / "tensor_manifest.json")
    if m.get("schema") != "s26-tensor-transfer-v1" or m.get("dtype") != "float32" or m.get("endianness") != "little" \
            or m.get("layout") != "NHWC_RGB" or list(m.get("shape", [])) != [1, 224, 224, 3]:
        raise SystemExit("tensor_manifest.json is not the registered format (schema/dtype/endianness/layout/shape)")
    if len(m["samples"]) != SAMPLE_COUNT:
        raise SystemExit(f"tensor_manifest.json has {len(m['samples'])} samples, not {SAMPLE_COUNT}")
    return m


def verify_inputs(inputs_dir: Path, manifest: dict) -> list[dict]:
    """등록 §1 ②④⑤ for the inputs (reference files are checked by the judge): bytes · SHA recomputed from the file · 602,112 B."""
    rows = []
    for s in manifest["samples"]:
        p = inputs_dir / s["input_file"]
        size = p.stat().st_size
        sha = sha256_file(p)
        ok = size == s["input_bytes"] == INPUT_BYTES and sha == s["input_sha256"]
        rows.append(dict(sample_id=s["sample_id"], path=str(p), bytes=size, sha256=sha, ok=ok))
        if not ok:
            raise SystemExit(f"input {s['sample_id']} failed verification (bytes {size}, sha {sha})")
    return rows


def build_app_manifest(manifest: dict, run_id: str, original_sha: str, aot_sha: str, device_root: str = DEVICE_ROOT,
                       source: dict | None = None) -> dict:
    """The JSON the app validates (QualityManifest.validate): runtimes CPU/GPU/NPU (one accelerator each, no fallback list) + 20 samples."""
    models = f"{device_root}/models"
    runtimes = {
        "CPU": dict(key="classification_CPU", task="classification", backend="CPU", model_path=f"{models}/efficientnet_lite0.tflite",
                    model_sha256=original_sha, cpu_threads=1),
        "GPU": dict(key="classification_GPU", task="classification", backend="GPU", model_path=f"{models}/efficientnet_lite0.tflite",
                    model_sha256=original_sha, gpu_precision="FP32"),
        "NPU": dict(key="classification_NPU", task="classification", backend="NPU",
                    model_path=f"{models}/efficientnet_lite0_Samsung_E9965.tflite", model_sha256=aot_sha),
    }
    samples = [dict(index=i, sample_id=s["sample_id"], input_path=f"{device_root}/inputs/{s['sample_id']}/input.f32le",
                    input_bytes=s["input_bytes"], input_sha256=s["input_sha256"]) for i, s in enumerate(manifest["samples"])]
    return dict(protocol=PROTOCOL, run_id=run_id, input_shape=[1, 224, 224, 3], input_elements=INPUT_BYTES // 4, input_bytes=INPUT_BYTES,
                output_elements=OUTPUT_ELEMENTS, runs_per_image=RUNS_PER_IMAGE, runtimes=runtimes, samples=samples,
                source=source or dict(zip_sha256=ZIP_SHA256, quality_reference_sha256=manifest.get("quality_reference_sha256"),
                                      preprocessing=manifest.get("preprocessing"), registration=REGISTRATION))


def device_files(manifest: dict, inputs_dir: Path, original_model: Path, aot_model: Path, device_root: str = DEVICE_ROOT) -> list[dict]:
    files = [dict(name="original_model", host=str(original_model), device=f"{device_root}/models/efficientnet_lite0.tflite", sha256=ORIGINAL_MODEL_SHA256),
             dict(name="aot_model", host=str(aot_model), device=f"{device_root}/models/efficientnet_lite0_Samsung_E9965.tflite", sha256=AOT_MODEL_SHA256)]
    for s in manifest["samples"]:
        files.append(dict(name=f"input_{s['sample_id']}", host=str(inputs_dir / s["input_file"]),
                          device=f"{device_root}/inputs/{s['sample_id']}/input.f32le", sha256=s["input_sha256"]))
    return files
