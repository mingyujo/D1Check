#!/usr/bin/env python3
"""Resource-execution evidence (MEASUREMENT_DEFINITION.md §11-2 ②) for npu-runner CompiledModel runs,
plus the precision four items (§11-3) read from the model file. Read-only: it never writes into results/.

    py tools/compiled_model_evidence.py evaluate <run_dir> [--rule cpu|gpu|npu|auto]
    py tools/compiled_model_evidence.py precision <model.tflite>
    py tools/compiled_model_evidence.py fingerprint          # SHA-256 of each rule's source

Rules (P2, 2026-09-28):
  cpu  CPU_RULE_VERSION — built from C5 runs 1-5 ONLY (results/S26_C5_cpu_compiled_0927, execution
       order 1-5 = 7d3db25c, 9fd259a0, fbfa1c09, 989cd41d, 03d10131) and frozen before runs 6-20 were
       opened. Registration lines (`XNNPACK CPU accelerator registered`, `NPU accelerator registered`,
       `... GPU accelerator(...) registered`), the dispatch-library load line and the ENN load line all
       appear in CPU-only runs 1-5, so none of them is evidence of anything.
  npu  the existing d1_logger_v4.npu_delegate_evidence (unchanged, imported) + the §11-2 PID condition.
  gpu  CANDIDATE ONLY. No phone GPU CompiledModel log exists yet. Patterns come from format strings in
       litert-2.2.0.aar jni/arm64-v8a (libLiteRt.so, libLiteRtClGlAccelerator.so). Pre-registered text:
       "스모크 로그로 패턴을 확정하고, 본 측정 전에 동결한다." Its verdict is reported as CANDIDATE_*.

Verdict PASS = "② resource evidence sufficient". FAIL = "② insufficient" — per §11-2 that means
"실행 성공, 자원 판정 증거 부족" when ① passed, not a failed run. Absence claims are limited to the
captured filter (D1CHECK_EVENT, D1GPU, tflite, TfLite, litert:I).
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import inspect
import json
from pathlib import Path
import re
import struct
import sys
from typing import Any

TOOLS = Path(__file__).resolve().parent

# logcat -v threadtime: "09-27 03:49:39.869 16827 16853 I tflite  : message"
THREADTIME_RE = re.compile(
    r"^\d\d-\d\d\s+\d\d:\d\d:\d\d\.\d+\s+(?P<pid>\d+)\s+(?P<tid>\d+)\s+(?P<level>[VDIWEF])\s+"
    r"(?P<tag>[^:]*?)\s*:\s?(?P<msg>.*)$"
)
REPLACE_RE = re.compile(
    r"Replacing\s+(?P<x>\d+)\s+out of\s+(?P<y>\d+)\s+node(?:\(s\)|s)?\s+with\s+delegate\s+\((?P<name>[^)]*)\)"
)
FAILURE_RE = re.compile(
    r"(?:failed\s+to\s+apply|restored\s+original\s+execution\s+plan|unsupported\s+op|"
    r"remaining\s+nodes?\s+run\s+on\s+CPU|fall(?:ing)?\s+back\s+to\s+CPU|CPU\s+fallback|"
    r"No\s+dispatch\s+library\s+found|Failed\s+to\s+initialize\s+Dispatch\s+API|"
    r"No\s+usable\s+Dispatch\s+runtime\s+found|Failed\s+to\s+create\s+a\s+dispatch\s+delegate\s+kernel|"
    r"Failed\s+to\s+load\s+enn\s+runtime|Found\s+Dispatch\s+API\s+with\s+an\s+unsupported\s+version|"
    r"Failed\s+to\s+allocate\s+tensors|\(DELEGATE\)\s+failed\s+to\s+prepare|"
    r"Failed\s+to\s+modify\s+graph\s+with\s+delegate)",
    re.IGNORECASE,
)
RUNNER_TAGS = ("D1GPU", "D1NPU")   # timed run / smoke path of npu-runner

# ---------------------------------------------------------------- CPU rule (frozen, see docstring)
CPU_RULE_VERSION = "cpu-compiled-model-evidence-v1"
CPU_DELEGATE = "TfLiteXNNPackDelegate"
CPU_CREATED = "Created TensorFlow Lite XNNPACK delegate for CPU."


def parse_log(text: str) -> list[dict[str, Any]]:
    rows = []
    for number, line in enumerate(text.splitlines(), 1):
        match = THREADTIME_RE.match(line)
        if match:
            rows.append({"line": number, **match.groupdict(), "tag": match.group("tag").strip()})
    return rows


def runner_pids(rows: list[dict[str, Any]]) -> set[str]:
    timed = {row["pid"] for row in rows if row["tag"] == "D1GPU"}
    return timed or {row["pid"] for row in rows if row["tag"] == "D1NPU"}


def evaluate_cpu(log_text: str, metadata: dict[str, Any] | None) -> dict[str, Any]:
    """CPU ② for a CompiledModel CPU run. Every condition must hold."""
    rows = parse_log(log_text)
    pids = runner_pids(rows)
    mine = [row for row in rows if row["pid"] in pids]
    replacements = [(row, REPLACE_RE.search(row["msg"])) for row in mine]
    replacements = [(row, match) for row, match in replacements if match]
    xnn = [(r, m) for r, m in replacements if m.group("name") == CPU_DELEGATE]
    other = [(r, m) for r, m in replacements if m.group("name") != CPU_DELEGATE]
    failures = [row for row in mine if FAILURE_RE.search(row["msg"])]
    conditions = {
        "single_runner_process": len(pids) == 1,
        "xnnpack_full_replacement_in_runner_pid": bool(xnn) and all(
            int(m.group("x")) == int(m.group("y")) > 0 for _, m in xnn
        ),
        "xnnpack_delegate_created_in_runner_pid": any(row["msg"].strip() == CPU_CREATED for row in mine),
        "no_other_delegate_replacement": not other,
        "no_failure_or_fallback_line": not failures,
        "requested_accelerator_cpu": (metadata or {}).get("npu_accelerator_requested") == "CPU",
    }
    return _verdict(CPU_RULE_VERSION, conditions, {
        "runner_pids": sorted(pids),
        "replacement_lines": [row["line"] for row, _ in replacements],
        "failure_lines": [row["line"] for row in failures],
        "ignored_as_non_evidence": "accelerator registration, dispatch library load and ENN load lines "
                                   "(all present in CPU-only C5 runs 1-5)",
    })


# ---------------------------------------------------------------- NPU rule (existing + PID)
NPU_RULE_VERSION = "npu-dispatch-evidence-v1+pid"


def _logger():
    spec = importlib.util.spec_from_file_location("d1_logger_v4_evidence", TOOLS / "d1_logger_v4.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def evaluate_npu(log_text: str, metadata: dict[str, Any] | None) -> dict[str, Any]:
    """The formal_npu_valid evidence (d1_logger_v4.npu_delegate_evidence, unchanged) + PID match."""
    logger = _logger()
    model_sha = str((metadata or {}).get("model_sha256") or "").lower()
    existing = logger.npu_delegate_evidence(log_text, model_sha)
    rows = parse_log(log_text)
    pids = runner_pids(rows)
    dispatch = [row for row in rows if logger.NPU_DISPATCH_REPLACE_RE.search(row["msg"])]
    enn = [row for row in rows if logger.NPU_ENN_LOADED_RE.search(row["msg"])]
    conditions = {
        "existing_npu_delegate_evidence_verified": existing["verification"] == "verified",
        "dispatch_and_enn_lines_in_runner_pid": bool(pids) and bool(dispatch) and bool(enn)
        and all(row["pid"] in pids for row in dispatch + enn),
    }
    return _verdict(NPU_RULE_VERSION, conditions, {
        "runner_pids": sorted(pids),
        "existing_evidence": existing,
        "note": "ENN load alone is not NPU evidence: C5 CPU-only runs 1-5 print it too",
    })


# ---------------------------------------------------------------- GPU candidate (NOT frozen)
GPU_RULE_VERSION = "gpu-compiled-model-evidence-candidate-0"
NON_GPU_DELEGATES = ("TfLiteXNNPackDelegate", "DispatchDelegate", "TfLiteNnapiDelegate", "YNNPackDelegate")
# Supporting lines: format strings found in litert-2.2.0.aar jni/arm64-v8a binaries (not seen on device)
GPU_SUPPORT_RE = re.compile(
    r"(?:ops are delegated to ML Drift|Created LiteRT GpuEnvironment|LiteRT GPU environment initialized)"
)
GPU_FAILURE_RE = re.compile(
    r"(?:Following operations are not supported by GPU delegate|Not supported by ML Drift|"
    r"Delegate kernel initialization failed|Failed to create litert::ml_drift|Failed to load OpenCL|"
    r"is not supported by TFLite GPU Delegate|falling back to CPU)",
    re.IGNORECASE,
)


def evaluate_gpu_candidate(log_text: str, metadata: dict[str, Any] | None) -> dict[str, Any]:
    rows = parse_log(log_text)
    pids = runner_pids(rows)
    mine = [row for row in rows if row["pid"] in pids]
    replacements = [(row, REPLACE_RE.search(row["msg"])) for row in mine]
    replacements = [(row, match) for row, match in replacements if match]
    gpu = [(r, m) for r, m in replacements if m.group("name") not in NON_GPU_DELEGATES]
    non_gpu = [(r, m) for r, m in replacements if m.group("name") in NON_GPU_DELEGATES]
    failures = [row for row in mine if FAILURE_RE.search(row["msg"]) or GPU_FAILURE_RE.search(row["msg"])]
    conditions = {
        "single_runner_process": len(pids) == 1,
        "gpu_full_replacement_in_runner_pid": bool(gpu) and all(
            int(m.group("x")) == int(m.group("y")) > 0 for _, m in gpu
        ),
        "gpu_runtime_support_line_in_runner_pid": any(GPU_SUPPORT_RE.search(row["msg"]) for row in mine),
        "no_cpu_or_npu_delegate_replacement": not non_gpu,
        "no_failure_or_fallback_line": not failures,
        "requested_accelerator_gpu": (metadata or {}).get("npu_accelerator_requested") == "GPU",
    }
    result = _verdict(GPU_RULE_VERSION, conditions, {
        "runner_pids": sorted(pids),
        "gpu_delegate_names": sorted({m.group("name") for _, m in gpu}),
        "failure_lines": [row["line"] for row in failures],
        "status": "candidate — confirm with the smoke log, then freeze before the main measurement",
    })
    result["verdict"] = "CANDIDATE_" + result["verdict"]
    return result


def _verdict(version: str, conditions: dict[str, bool], details: dict[str, Any]) -> dict[str, Any]:
    failed = [name for name, value in conditions.items() if not value]
    return {"rule": version, "verdict": "PASS" if not failed else "FAIL", "conditions": conditions,
            "failed_conditions": failed, "details": details}


def rule_fingerprints() -> dict[str, str]:
    """SHA-256 of each rule's source text (function + the constants it reads), for freezing."""
    module = sys.modules[__name__]
    parts = {
        "cpu": [evaluate_cpu, parse_log, runner_pids, _verdict],
        "npu": [evaluate_npu, parse_log, runner_pids, _verdict],
        "gpu_candidate": [evaluate_gpu_candidate, parse_log, runner_pids, _verdict],
    }
    constants = {
        "cpu": [THREADTIME_RE.pattern, REPLACE_RE.pattern, FAILURE_RE.pattern, repr(RUNNER_TAGS),
                CPU_RULE_VERSION, CPU_DELEGATE, CPU_CREATED],
        "npu": [THREADTIME_RE.pattern, repr(RUNNER_TAGS), NPU_RULE_VERSION],
        "gpu_candidate": [THREADTIME_RE.pattern, REPLACE_RE.pattern, FAILURE_RE.pattern, repr(RUNNER_TAGS),
                          GPU_RULE_VERSION, repr(NON_GPU_DELEGATES), GPU_SUPPORT_RE.pattern,
                          GPU_FAILURE_RE.pattern],
    }
    del module
    return {
        name: hashlib.sha256(
            ("\n".join(inspect.getsource(f) for f in funcs) + "\n".join(constants[name])).encode("utf-8")
        ).hexdigest()
        for name, funcs in parts.items()
    }


# ---------------------------------------------------------------- run directory

def load_run(run_dir: Path) -> tuple[str, dict[str, Any] | None]:
    log_path = run_dir / "raw" / "logcat.txt"
    text = log_path.read_text(encoding="utf-8", errors="replace") if log_path.is_file() else ""
    runner = sorted((run_dir / "gpu").glob("gpu-events-*.jsonl")) if (run_dir / "gpu").is_dir() else []
    metadata = None
    if runner:
        with runner[0].open(encoding="utf-8") as stream:
            first = stream.readline()
        metadata = json.loads(first) if first.strip() else None
    return text, metadata


def evaluate_run(run_dir: Path, rule: str = "auto") -> dict[str, Any]:
    text, metadata = load_run(run_dir)
    if rule == "auto":
        requested = (metadata or {}).get("npu_accelerator_requested", "NPU")
        rule = {"CPU": "cpu", "GPU": "gpu"}.get(str(requested), "npu")
    evaluate = {"cpu": evaluate_cpu, "npu": evaluate_npu, "gpu": evaluate_gpu_candidate}[rule]
    result = evaluate(text, metadata)
    result["run_dir"] = run_dir.name
    return result


# ---------------------------------------------------------------- precision four items (§11-3)
# Minimal TFLite flatbuffer reader (identifier TFL3). Field indices follow tensorflow/lite/schema/schema.fbs;
# the reader is checked against facts recorded earlier from the same files (작업결과_0926_2차.md 2단계:
# original MobileNet 88 FLOAT32 + 1 INT32 tensors, I/O FLOAT32 [1,224,224,3] -> [1,1001]; AOT = 2 tensors).
TENSOR_TYPES = {0: "FLOAT32", 1: "FLOAT16", 2: "INT32", 3: "UINT8", 4: "INT64", 5: "STRING", 6: "BOOL",
                7: "INT16", 8: "COMPLEX64", 9: "INT8", 10: "FLOAT64"}


class _Table:
    def __init__(self, data: bytes, position: int):
        self.data, self.position = data, position
        vtable = position - struct.unpack_from("<i", data, position)[0]
        self.vtable, self.vtable_size = vtable, struct.unpack_from("<H", data, vtable)[0]

    def _field(self, index: int) -> int | None:
        entry = 4 + 2 * index
        if entry >= self.vtable_size:
            return None
        offset = struct.unpack_from("<H", self.data, self.vtable + entry)[0]
        return None if offset == 0 else self.position + offset

    def scalar(self, index: int, fmt: str, default: Any) -> Any:
        at = self._field(index)
        return default if at is None else struct.unpack_from("<" + fmt, self.data, at)[0]

    def _vector(self, index: int) -> tuple[int, int] | None:
        at = self._field(index)
        if at is None:
            return None
        start = at + struct.unpack_from("<I", self.data, at)[0]
        return start + 4, struct.unpack_from("<I", self.data, start)[0]

    def tables(self, index: int) -> list["_Table"]:
        vector = self._vector(index)
        if vector is None:
            return []
        start, length = vector
        return [_Table(self.data, start + 4 * i + struct.unpack_from("<I", self.data, start + 4 * i)[0])
                for i in range(length)]

    def ints(self, index: int) -> list[int]:
        vector = self._vector(index)
        return [] if vector is None else list(struct.unpack_from(f"<{vector[1]}i", self.data, vector[0]))

    def string(self, index: int) -> str | None:
        vector = self._vector(index)
        return None if vector is None else self.data[vector[0]:vector[0] + vector[1]].decode("utf-8", "replace")

    def byte_length(self, index: int) -> int:
        vector = self._vector(index)
        return 0 if vector is None else vector[1]


def read_tflite(path: Path) -> dict[str, Any]:
    data = Path(path).read_bytes()
    if data[4:8] != b"TFL3":
        raise ValueError(f"not a TFLite flatbuffer (identifier {data[4:8]!r})")
    model = _Table(data, struct.unpack_from("<I", data, 0)[0])
    buffers = [buffer.byte_length(0) for buffer in model.tables(4)]          # Buffer.data
    opcodes = [code.string(1) for code in model.tables(1)]                   # OperatorCode.custom_code
    subgraph = model.tables(2)[0]                                            # first SubGraph
    tensors = subgraph.tables(0)                                             # SubGraph.tensors
    described = []
    for tensor in tensors:
        buffer_index = tensor.scalar(2, "I", 0)                              # Tensor.buffer
        described.append({
            "name": tensor.string(3),                                        # Tensor.name
            "type": TENSOR_TYPES.get(tensor.scalar(1, "b", 0), "UNKNOWN"),   # Tensor.type
            "shape": tensor.ints(0),                                         # Tensor.shape
            "constant_bytes": buffers[buffer_index] if 0 < buffer_index < len(buffers) else 0,
        })
    inputs, outputs = subgraph.ints(1), subgraph.ints(2)
    return {
        "sha256": hashlib.sha256(data).hexdigest(),
        "size_bytes": len(data),
        "tensor_count": len(described),
        "tensor_types": _count(t["type"] for t in described),
        "constant_tensor_types": _count(t["type"] for t in described if t["constant_bytes"] > 0),
        "inputs": [{"type": described[i]["type"], "shape": described[i]["shape"]} for i in inputs],
        "outputs": [{"type": described[i]["type"], "shape": described[i]["shape"]} for i in outputs],
        "custom_ops": sorted({code for code in opcodes if code}),
        "operator_count": len(subgraph.tables(3)),
    }


def _count(values) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def precision_four(model_path: Path, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    """§11-3: ① storage (from the file) ② I/O dtype (from the file) ③ options (from run metadata)
    ④ internal compute (unknown unless evidence exists). Nothing estimated is written as a fact."""
    facts = read_tflite(model_path)
    aot = "DISPATCH_OP" in facts["custom_ops"]
    storage = (
        {"value": "unknown [E: FP16 by size]", "basis": "AOT flatbuffer: weights live inside the vendor "
         "bytecode of DISPATCH_OP; only the I/O tensors are readable", "file_tensor_types": facts["tensor_types"]}
        if aot else
        {"value": "+".join(f"{k}x{v}" for k, v in facts["constant_tensor_types"].items()),
         "basis": "constant (weight) tensors in the flatbuffer", "file_tensor_types": facts["tensor_types"]}
    )
    options = (metadata or {}).get("compiled_model_options")
    if options is None and metadata is not None:
        options = {
            "accelerator_requested": metadata.get("npu_accelerator_requested", "NPU"),
            "basis": "run metadata of a pre-2026-09-28 runner: no compiled_model_options key; the runner "
                     "passed CompiledModel.Options(<that accelerator>) and no CPU/GPU options",
        }
    return {
        "model_sha256": facts["sha256"],
        "storage": storage,
        "io_dtype": {"inputs": facts["inputs"], "outputs": facts["outputs"], "basis": "flatbuffer I/O tensors"},
        "options": options if options is not None else "unknown (no run metadata given)",
        "internal_compute": {"value": "unknown",
                             "reason": "LiteRT 2.2.0 does not expose executed/accumulation precision"},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    evaluate = sub.add_parser("evaluate")
    evaluate.add_argument("run_dir", type=Path, nargs="+")
    evaluate.add_argument("--rule", choices=("auto", "cpu", "gpu", "npu"), default="auto")
    precision = sub.add_parser("precision")
    precision.add_argument("model", type=Path)
    sub.add_parser("fingerprint")
    args = parser.parse_args(argv)
    if args.command == "fingerprint":
        output: Any = rule_fingerprints()
    elif args.command == "precision":
        output = precision_four(args.model)
    else:
        output = [evaluate_run(path, args.rule) for path in args.run_dir]
    # UTF-8 bytes: a Windows console codepage (cp949) cannot print every note
    sys.stdout.buffer.write((json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
