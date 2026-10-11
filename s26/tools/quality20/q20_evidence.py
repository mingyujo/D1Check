"""Q20 delegation evidence from the per-backend logcat (committed before the phone run).

  py -3 -X utf8 s26/tools/quality20/q20_evidence.py --run <results root> [--out <results root>/evidence.json]
  py -3 -X utf8 s26/tools/quality20/q20_evidence.py --selftest

Evidence functions are IMPORTED from s26/tools/mixreq/mixreq_validate.py (R2, frozen): gpu_evidence (GPU rule v1 regexes:
compiled_model_evidence REPLACE_RE · GPU_DELEGATE "LITERT_CL" · GPU_ENVIRONMENT_RE · FAILURE_RE · GPU_FAILURE_RE) and npu_evidence
(npu-dispatch-evidence-v1 conditions: DispatchDelegate x == y == AOT partition (1/1) · ENN loaded line (necessary only) · dispatch failure 0 ·
no other delegate replacement). They are called unchanged; only the window marks are translated:

  D1Q20 mark (this app, one process per backend)          → D1MIX-shaped mark that key_windows()/npu_evidence() expect
  activity_start run_id=<id> backend=<b> pid=<p>           → session_start
  runtime create_start key=<k> / runtime create_end key=<k> → the same (creation window)
  image_start idx=0 / image_end idx=0                      → warmup_start key=<k> index=0 / warmup_end key=<k> index=1 (first-image window)
  image_start idx=1 / last image_end                       → common_start / drain_end (the remaining 19 images: dispatch-failure-free window)

So the evidence window is [runtime create_start, first image end] (prompt 1-4) as the union of two sub-windows; the only lines between
create_end and image_start 0 are the app's own file read/SHA check (no runtime lines).

CPU (no imported function exists for a windowed CPU runtime — mixreq_validate deliberately skips the CPU key): the same conditions as
compiled_model_evidence.evaluate_cpu applied inside the window and to the runner PID: XNNPACK full replacement (x == y > 0, every
replacement line), "Created TensorFlow Lite XNNPACK delegate for CPU." present, no other delegate replacement, no failure/fallback line.
Dispatch-library load and the ENN "SetGenAiPerfConfigFromSoc" line appear in CPU-only runs too (C5 runs 1-5) and are NOT evidence.

GPU actual precision (등록 §2: "로그에서 읽을 수 있으면 적고, 못 읽으면 미확인"): lines of the runner PID inside the window matching
PRECISION_HINT_RE are recorded; observed = "FP32" only if some line matches PRECISION_FP32_RE and no line matches PRECISION_FP16_RE,
else "미확인". The S1 smoke log of 2026-10-09 (request-runner, same engine) printed no such line, so "미확인" is the expected outcome.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import q20_common as C  # noqa: E402

V = C.load_mixreq_validate()
EVIDENCE = V.EVIDENCE
LOGGER = V.LOGGER
SCHEMA = "s26-q20-evidence-v1"
Q20_MARK_RE = re.compile(r"^(?P<what>activity_start|runtime create_start|runtime create_end|runtime create_skipped|image_start|image_end|image_failure|activity_end)\b(?P<rest>.*)$")
KV_RE = re.compile(r"(\w+)=(\S+)")
PRECISION_HINT_RE = re.compile(r"\b(?:fp16|fp32|f16|f32|float16|float32|half|precision)\b", re.IGNORECASE)
PRECISION_FP32_RE = re.compile(r"precision[^\n]*\b(?:fp32|f32|float32)\b", re.IGNORECASE)
PRECISION_FP16_RE = re.compile(r"\b(?:fp16|f16|float16|half)\b", re.IGNORECASE)
CPU_RULE = "cpu-compiled-model-evidence-v1 (conditions, windowed by D1Q20 marks)"


# ----------------------------------------------------------------------------------------------- marks
def q20_marks(rows: list[dict], run_id: str, backend: str):
    """Runner PID = the one D1Q20 activity_start line for this run_id/backend; returns (pid, raw marks, error)."""
    starts = [r for r in rows if r["tag"] == C.LOG_TAG and r["msg"].startswith("activity_start")
              and f"run_id={run_id}" in r["msg"] and f"backend={backend}" in r["msg"]]
    if len(starts) != 1:
        return None, [], f"activity_start marks for run_id/backend: {len(starts)}"
    pid = starts[0]["pid"]
    marks = []
    for r in rows:
        if r["pid"] != pid or r["tag"] != C.LOG_TAG:
            continue
        m = Q20_MARK_RE.match(r["msg"].strip())
        if m:
            marks.append((r["line"], m.group("what"), dict(KV_RE.findall(m.group("rest")))))
    return pid, marks, None


def translate_marks(marks, key: str):
    """D1Q20 → D1MIX-shaped marks (see module docstring). Returns the list and the [create_start, first image end] window or None."""
    out = []
    image_ends = [(l, kv) for l, w, kv in marks if w == "image_end"]
    for line, what, kv in marks:
        if what == "activity_start":
            out.append((line, "session_start", kv))
        elif what in ("runtime create_start", "runtime create_end"):
            out.append((line, what, {"key": kv.get("key", key)}))
        elif what == "image_start" and kv.get("idx") == "0":
            out.append((line, "warmup_start", {"key": key, "index": "0"}))
        elif what == "image_end" and kv.get("idx") == "0":
            out.append((line, "warmup_end", {"key": key, "index": "1"}))
        elif what == "image_start" and kv.get("idx") == "1":
            out.append((line, "common_start", {}))
    if image_ends:
        out.append((image_ends[-1][0], "drain_end", {}))
    out.sort(key=lambda t: t[0])
    cs = [l for l, w, kv in marks if w == "runtime create_start"]
    e0 = [l for l, w, kv in marks if w == "image_end" and kv.get("idx") == "0"]
    window = (cs[0], e0[0]) if len(cs) == 1 and len(e0) == 1 and e0[0] > cs[0] else None
    return out, window


# ----------------------------------------------------------------------------------------------- CPU (windowed evaluate_cpu conditions)
def cpu_evidence(rows, pid, marks, key: str) -> dict:
    win = V.key_windows(marks, key)
    if win is None:
        return dict(rule=CPU_RULE, verdict="FAIL", reason="window marks missing", key=key)
    mine = [r for r in rows if r["pid"] == pid and V.in_windows(r["line"], win)]
    replacements = [(r, m) for r in mine for m in [EVIDENCE.REPLACE_RE.search(r["msg"])] if m]
    xnn = [(r, m) for r, m in replacements if m.group("name") == EVIDENCE.CPU_DELEGATE]
    other = [(r, m) for r, m in replacements if m.group("name") != EVIDENCE.CPU_DELEGATE]
    failures = [r for r in mine if EVIDENCE.FAILURE_RE.search(r["msg"])]
    conditions = {
        "xnnpack_full_replacement": bool(xnn) and all(int(m.group("x")) == int(m.group("y")) > 0 for _, m in xnn),
        "xnnpack_delegate_created": any(r["msg"].strip() == EVIDENCE.CPU_CREATED for r in mine),
        "no_other_delegate_replacement": not other,
        "no_failure_or_fallback_line": not failures,
    }
    failed = [k for k, v in conditions.items() if not v]
    return dict(rule=CPU_RULE, key=key, verdict="PASS" if not failed else "FAIL", conditions=conditions, failed_conditions=failed,
                window_lines=[list(w) for w in win], replacement_lines=[r["line"] for r, _ in replacements],
                replacements=[f"{m.group('x')}/{m.group('y')} {m.group('name')}" for _, m in replacements],
                failure_lines=[r["line"] for r in failures],
                ignored_as_non_evidence="dispatch library load and ENN SetGenAiPerfConfigFromSoc lines (present in CPU-only C5 runs 1-5)")


def gpu_precision(rows, pid, window) -> dict:
    if window is None:
        return dict(observed="미확인", lines=[], reason="window missing")
    mine = [r for r in rows if r["pid"] == pid and window[0] <= r["line"] <= window[1] and PRECISION_HINT_RE.search(r["msg"])]
    fp32 = any(PRECISION_FP32_RE.search(r["msg"]) for r in mine)
    fp16 = any(PRECISION_FP16_RE.search(r["msg"]) for r in mine)
    observed = "FP32" if (fp32 and not fp16) else "미확인"
    return dict(observed=observed, lines=[dict(line=r["line"], msg=r["msg"][:160]) for r in mine][:20], fp32_match=fp32, fp16_match=fp16,
                rule="FP32 only if a runner-PID line in the window matches /precision.*(fp32|f32|float32)/i and none matches /(fp16|f16|float16|half)/i")


# ----------------------------------------------------------------------------------------------- one backend
def evaluate_backend(log_path: Path, run_id: str, backend: str, summary: dict | None) -> dict:
    key = f"classification_{backend}"
    out = dict(backend=backend, key=key, run_id=run_id, logcat=str(log_path), verdict="FAIL", summary_status=(summary or {}).get("status"),
               runtime_created=(summary or {}).get("runtime_created"))
    if not log_path.is_file():
        out["reason"] = "logcat file missing"
        return out
    rows = V.parse_logcat(log_path)
    pid, marks, err = q20_marks(rows, run_id, backend)
    if err:
        out["reason"] = err
        return out
    translated, window = translate_marks(marks, key)
    out.update(pid=pid, window_lines=list(window) if window else None, mark_count=len(marks),
               images_logged=sum(1 for _, w, _ in marks if w == "image_end"),
               images_ok_logged=sum(1 for _, w, kv in marks if w == "image_end" and kv.get("ok") == "true"))
    if backend == "CPU":
        ev = cpu_evidence(rows, pid, translated, key)
    elif backend == "GPU":
        ev = V.gpu_evidence(rows, pid, translated, key)
        out["gpu_precision_requested"] = (((summary or {}).get("compiled_model_options") or {}).get("gpu_options") or {}).get("precision")
        out["gpu_precision"] = gpu_precision(rows, pid, window)
    else:
        model_sha = (summary or {}).get("model_sha256_expected") or C.AOT_MODEL_SHA256
        ev = V.npu_evidence(rows, pid, translated, key, model_sha)
    out["evidence"] = ev
    out["verdict"] = ev.get("verdict", "FAIL")
    if summary is not None:
        init = summary.get("runtime_init") or {}
        out["available_accelerators"] = init.get("available_accelerators")
        out["dispatch_so_present"] = init.get("dispatch_so_present")
        out["accelerators_passed_to_native"] = ((summary.get("compiled_model_options") or {}).get("accelerators_passed_to_native"))
    return out


def evaluate_run(root: Path, run_id: str | None = None, backends=C.BACKENDS) -> dict:
    record = C.read_json(root / "host" / "run_record.json") if (root / "host" / "run_record.json").is_file() else {}
    run_id = run_id or record.get("run_id") or root.name.replace("S26_Q20_", "")
    result = dict(schema=SCHEMA, run_id=run_id, root=str(root), backends={})
    for b in backends:
        folder = root / b
        if not folder.is_dir():
            continue
        summary_path = folder / "device" / "summary.json"
        summary = C.read_json(summary_path) if summary_path.is_file() else None
        result["backends"][b] = evaluate_backend(folder / "host" / "logcat_threadtime.txt", run_id, b, summary)
    return result


def markdown(result: dict) -> str:
    lines = [f"# Q20 실행 증거 — run `{result['run_id']}`", "",
             "| backend | 증거 판정 | 규칙 | 교체 줄 | 실패 조건 | 창 (logcat 줄) | GPU 정밀도 (요청 / 로그) | available_accelerators |",
             "|---|---|---|---|---|---|---|---|"]
    for b, r in result["backends"].items():
        ev = r.get("evidence", {})
        reps = ev.get("replacements") or ev.get("dispatch_replacements") or []
        prec = "—"
        if b == "GPU":
            prec = f"{r.get('gpu_precision_requested')} / {(r.get('gpu_precision') or {}).get('observed')}"
        lines.append(f"| {b} | **{r['verdict']}** | {ev.get('rule', r.get('reason', ''))} | {', '.join(reps)} | "
                     f"{', '.join(ev.get('failed_conditions', [])) or (r.get('reason') or '없음')} | {r.get('window_lines')} | {prec} | {r.get('available_accelerators')} |")
    lines += ["", "창 = `D1Q20 runtime create_start` ~ 첫 이미지 `image_end idx=0` (생성 창 ∪ 첫 이미지 창). 증거 함수 = `s26/tools/mixreq/mixreq_validate.py` "
              "`gpu_evidence` · `npu_evidence` (import · 무변경) · CPU 는 `compiled_model_evidence.evaluate_cpu` 조건을 같은 창에 적용. "
              "ENN 로드 줄은 NPU 실행 증명이 아니라 필요조건이다 (CPU 실행에서도 찍힌다). NPU 코어 실행은 앱에서 관측할 수 없다.", ""]
    return "\n".join(lines)


# ----------------------------------------------------------------------------------------------- selftest (synthetic logs)
def _log(pid: int, lines: list[tuple[str, str]]) -> str:
    out = []
    for i, (tag, msg) in enumerate(lines):
        out.append(f"10-09 20:00:{i % 60:02d}.{i:03d} {pid:5d} {pid + 1:5d} I {tag:<8}: {msg}")
    return "\n".join(out) + "\n"


def _case(backend: str, variant: str = "ok") -> tuple[str, int]:
    pid = 4242
    key = f"classification_{backend}"
    L = [("D1Q20", f"activity_start run_id=selftest backend={backend} pid={pid} apk_sha256=x out=/x")]
    L.append(("D1Q20", f"runtime create_start key={key} backend={backend}"))
    L.append(("litert", "[litert_dispatch.cc:159] Loading shared library: /x/libLiteRtDispatch_Samsung.so"))
    if variant != "no_enn":
        L.append(("litert", "[enn_manager.cc:124] SetGenAiPerfConfigFromSoc: SOC=s5e9965, mode=7, configId=0"))
    if backend == "CPU":
        L.append(("tflite", "Created TensorFlow Lite XNNPACK delegate for CPU."))
        n = "60" if variant == "partial" else "62"
        L.append(("tflite", f"Replacing {n} out of 62 node(s) with delegate (TfLiteXNNPackDelegate) node, yielding 1 partitions for subgraph 0 (main)."))
        if variant == "other_delegate":
            L.append(("tflite", "Replacing 62 out of 62 node(s) with delegate (LITERT_CL) node, yielding 1 partitions for subgraph 0 (main)."))
    elif backend == "GPU":
        if variant != "no_env":
            L.append(("litert", "[gpu_environment.h:155] Created LiteRT GpuEnvironment."))
        n = "60" if variant == "partial" else "62"
        L.append(("tflite", f"Replacing {n} out of 62 node(s) with delegate (LITERT_CL) node, yielding 1 partitions for subgraph 0 (main)."))
        if variant == "other_delegate":
            L.append(("tflite", "Replacing 62 out of 62 node(s) with delegate (TfLiteXNNPackDelegate) node, yielding 1 partitions for subgraph 0 (main)."))
        if variant == "precision_fp32":
            L.append(("litert", "[gpu_options.cc:10] precision=FP32 (requested)"))
        if variant == "precision_fp16":
            L.append(("litert", "[gpu_options.cc:10] precision=FP32 requested, inference in FP16"))
    else:
        n = "0" if variant == "zero" else "1"
        L.append(("tflite", f"Replacing {n} out of 1 node(s) with delegate (DispatchDelegate) node, yielding 1 partitions for subgraph 0 (main)."))
        L.append(("litert", "[litert_dispatch_invocation_context.cc:132] Header verification failed - using old format"))
        if variant == "other_delegate":
            L.append(("tflite", "Replacing 62 out of 62 node(s) with delegate (TfLiteXNNPackDelegate) node, yielding 1 partitions for subgraph 0 (main)."))
    if variant == "failure":
        L.append(("litert", "Failed to load enn runtime" if backend == "NPU" else "falling back to CPU"))
    L.append(("D1Q20", f"runtime create_end key={key} ok=true"))
    for i in range(20):
        L.append(("D1Q20", f"image_start idx={i} sample_id=00000000000000{i:02d}"))
        if variant == "failure_common" and backend == "NPU" and i == 5:
            L.append(("litert", "Failed to allocate tensors"))
        L.append(("D1Q20", f"image_end idx={i} ok=true"))
    L.append(("D1Q20", "activity_end outcome=completed"))
    if variant == "no_marks":
        L = [l for l in L if not l[1].startswith("image_end idx=0")]
    return _log(pid, L), pid


def selftest() -> int:
    expectations = [
        ("CPU", "ok", "PASS"), ("CPU", "partial", "FAIL"), ("CPU", "other_delegate", "FAIL"), ("CPU", "failure", "FAIL"), ("CPU", "no_marks", "FAIL"),
        ("GPU", "ok", "PASS"), ("GPU", "partial", "FAIL"), ("GPU", "other_delegate", "FAIL"), ("GPU", "no_env", "FAIL"), ("GPU", "failure", "FAIL"),
        ("GPU", "precision_fp32", "PASS"), ("GPU", "precision_fp16", "PASS"),
        ("NPU", "ok", "PASS"), ("NPU", "zero", "FAIL"), ("NPU", "no_enn", "FAIL"), ("NPU", "other_delegate", "FAIL"), ("NPU", "failure", "FAIL"),
        ("NPU", "failure_common", "FAIL"), ("NPU", "no_marks", "FAIL"),
    ]
    failed = []
    with tempfile.TemporaryDirectory() as tmp:
        for backend, variant, expected in expectations:
            text, pid = _case(backend, variant)
            p = Path(tmp) / f"{backend}_{variant}.txt"
            p.write_text(text, encoding="utf-8")
            summary = dict(status="completed", runtime_created=True, model_sha256_expected=C.AOT_MODEL_SHA256,
                           compiled_model_options=dict(gpu_options=dict(precision="FP32") if backend == "GPU" else None, accelerators_passed_to_native=[backend]),
                           runtime_init=dict(available_accelerators=["CPU", "GPU", "NPU"], dispatch_so_present=True))
            r = evaluate_backend(p, "selftest", backend, summary)
            got = r["verdict"]
            extra = ""
            if backend == "GPU":
                obs = r["gpu_precision"]["observed"]
                want = "FP32" if variant == "precision_fp32" else "미확인"
                extra = f" precision={obs}"
                if obs != want:
                    failed.append(f"{backend}/{variant}: precision {obs} != {want}")
            print(f"{backend:3s} {variant:16s} expected {expected:4s} got {got}{extra}")
            if got != expected:
                failed.append(f"{backend}/{variant}: {got} != {expected}")
    # wrong run_id / backend must not match another process's marks
    text, _ = _case("CPU", "ok")
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "x.txt"
        p.write_text(text, encoding="utf-8")
        if evaluate_backend(p, "other_run", "CPU", None)["verdict"] != "FAIL":
            failed.append("other run_id matched")
        if evaluate_backend(p, "selftest", "GPU", None)["verdict"] != "FAIL":
            failed.append("other backend matched")
    print("SELFTEST", "FAIL: " + "; ".join(failed) if failed else "PASS (%d cases)" % (len(expectations) + 2))
    return 1 if failed else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run")
    ap.add_argument("--run-id")
    ap.add_argument("--out")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if not a.run:
        ap.error("--run or --selftest")
    root = Path(a.run)
    result = evaluate_run(root, a.run_id)
    out = Path(a.out) if a.out else root / "evidence.json"
    C.write_json(out, result)
    out.with_suffix(".md").write_text(markdown(result), encoding="utf-8", newline="\n")
    for b, r in result["backends"].items():
        print(b, r["verdict"], r.get("reason", ""), (r.get("evidence") or {}).get("failed_conditions", []))
    print("written", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
