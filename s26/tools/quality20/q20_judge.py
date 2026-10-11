"""Q20 judge — 등록 d1sim/docs/품질20장_사전등록_v1.md §3 applied verbatim. COMMITTED BEFORE THE PHONE RUN; nothing below is changed after
results are seen (허용식 · 지표 · 판정 문구 고정).

  py -3 -X utf8 s26/tools/quality20/q20_judge.py --run <results root> [--reference <extracted zip dir>] [--evidence <evidence.json>]
      [--apk-sha <sha>] [--out-dir <dir>]
  py -3 -X utf8 s26/tools/quality20/q20_judge.py --selftest

Reference (등록 §1, received as-is): references/<id>/output_0.f32le (LE float32 [1,1000] Softmax, 0-based labels) — the file SHA must equal
tensor_manifest.reference_sha256 AND quality_reference.samples[i].reference.raw_output_sha256, the file must equal output_float32 bit for bit,
decoder.class_index_offset must be 0 and label_sha256 the registered labels file (e697a491…). Any mismatch = stop (no new hash is accepted).

Candidate = the app's <idx>_<id>.run0.f32le (run 1 is compared only for the "2회 비트 동일" column; metrics use run 0 — fixed here).

필수 (every backend; any failure = that image "실패", preserved): all 1000 finite · exactly 1000 elements (= shape [1,1000]) · float32 (the app
writes readFloat() as LE float32; file is 4,000 B) · label order = reference (same 0-based index space: CPU/GPU open the model the reference
was produced with, 6c7ab0a6…; NPU opens its AOT artifact 311e4aac… compiled from that model — aot_manifest input_sha256).

이미지별 (20 rows per backend): top-1 equal · top-5 same order · top-5 set overlap |∩|/5 · cosine · max |diff| · mean |diff| ·
FP32 tolerance violations (|cand − ref| ≤ 1e-4 + 1e-3·|ref|, count of 1000) · run0 == run1 bit identical.
Tie rule for top-k: score descending, then class index ascending (A24 decoder; == quality_reference decoder.ordering).
cosine with a zero-norm or non-finite vector = null, shown "계산 불가" (recorded; not a 필수 failure by itself — non-finite is already 필수).

집계: top-1 n/20 · top-5 order n/20 · overlap mean/min · cosine min/median · max of max|diff| · images with 0 violations n/20.

판정 (등록 §3 table):
  CPU : 20 images all 필수 pass + violations 0 everywhere → "참조와 일치 (FP32 기존 경로 기준)" ; any violation → "불일치" + image list ;
        any 필수 failure → "실패" (+ image list) — never "일치".
  GPU : 필수 failure → "실패" ; actual precision read as FP32 (evidence.json gpu_precision.observed == "FP32") → CPU rule ;
        "미확인" → "지표만 · PASS 보류 (GPU 실제 정밀도 미확인)".
  NPU : 필수 failure → "실패" ; otherwise "지표만 · 품질 PASS 보류 (FP16 합격선 미등록)" — the FP32 tolerance is NEVER applied to NPU
        (its violation count is printed as a record only).
  Runtime not created / no summary → "실패 (runtime 생성 실패)" ; execution-evidence FAIL (evidence.json) is appended as a tag
        "실행 증거 FAIL — 실행 장치 미확인" (the quality verdict text itself does not change; 2부 5 treats it as a backend failure → retry once).
  CPU not "일치" → GPU · NPU rows get the tag "CPU 기준 미달 — 품질로 해석하지 않음" (등록 §2).
Result sentence (등록 §3 template, numbers only):
  "대표 입력 20장에서 {backend} 출력은 조민규 CPU 참조와 top-1 {n}/20 · top-5 순서 {n}/20 · cosine 최소 {x} 로 일치했다 (참조 일치 — 정답 정확도
   아님 · NPU 품질 PASS 보류: FP16 합격선 미등록)."
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import q20_common as C  # noqa: E402

SCHEMA = "s26-q20-judgement-v1"
V_MATCH = "참조와 일치 (FP32 기존 경로 기준)"
V_MISMATCH = "불일치"
V_FAIL = "실패"
V_GPU_HOLD = "지표만 · PASS 보류 (GPU 실제 정밀도 미확인)"
V_NPU_HOLD = "지표만 · 품질 PASS 보류 (FP16 합격선 미등록)"
TAG_CPU_BELOW = "CPU 기준 미달 — 품질로 해석하지 않음"
TAG_EVIDENCE_FAIL = "실행 증거 FAIL — 실행 장치 미확인"
NOT_COMPUTABLE = "계산 불가"


# ----------------------------------------------------------------------------------------------- reference
def load_reference(inputs_dir: Path) -> dict:
    m = C.load_tensor_manifest(inputs_dir)
    qr_path = inputs_dir / "quality_reference.json"
    qr_sha = C.sha256_file(qr_path)
    if qr_sha != m["quality_reference_sha256"] or qr_sha != C.QUALITY_REFERENCE_SHA256:
        raise SystemExit(f"quality_reference.json sha {qr_sha} != manifest/registered")
    qr = C.read_json(qr_path)
    by_id = {s["image"]["sample_id"]: s for s in qr["samples"]}
    refs = []
    for i, s in enumerate(m["samples"]):
        q = by_id.get(s["sample_id"])
        if q is None:
            raise SystemExit(f"reference JSON lacks {s['sample_id']}")
        p = inputs_dir / s["reference_file"]
        sha = C.sha256_file(p)
        r = q["reference"]
        if sha != s["reference_sha256"] or sha != r["raw_output_sha256"]:
            raise SystemExit(f"reference raw {s['sample_id']} sha {sha} != manifest {s['reference_sha256']} / json {r['raw_output_sha256']}")
        values = C.read_f32le(p, C.OUTPUT_ELEMENTS)
        if len(q["output_float32"]) != C.OUTPUT_ELEMENTS or any(a != b for a, b in zip(values, q["output_float32"])):
            raise SystemExit(f"reference raw {s['sample_id']} != output_float32")
        if r["decoder"]["class_index_offset"] != 0 or s["label_sha256"] != C.LABELS_SHA256 or r["label_sha256"] != C.LABELS_SHA256:
            raise SystemExit(f"reference {s['sample_id']} label space is not the registered 0-based labels")
        if r["model_sha256"] != C.ORIGINAL_MODEL_SHA256 or s["model_sha256"] != C.ORIGINAL_MODEL_SHA256 or r["input_tensor_sha256"] != s["input_sha256"]:
            raise SystemExit(f"reference {s['sample_id']} model/input provenance mismatch")
        out_meta = r["tensor_metadata"]["outputs"][0]
        if list(out_meta.get("shape", [])) != [1, 1000] or "float32" not in str(out_meta.get("dtype")):
            raise SystemExit(f"reference {s['sample_id']} output metadata is not float32 [1,1000]")
        refs.append(dict(index=i, sample_id=s["sample_id"], values=values, sha256=sha, selection_class=q.get("selection_class"),
                         input_sha256=s["input_sha256"], decoder_ordering=r["decoder"].get("ordering")))
    return dict(manifest=m, quality_reference_sha256=qr_sha, refs=refs, runtime=qr["samples"][0]["reference"].get("runtime"),
                runtime_version=qr["samples"][0]["reference"].get("runtime_version"), cpu_threads=qr["samples"][0]["reference"].get("cpu_threads"))


# ----------------------------------------------------------------------------------------------- one image
def judge_image(ref: dict, device_dir: Path, backend: str) -> dict:
    prefix = "%02d_%s" % (ref["index"], ref["sample_id"])
    row = dict(index=ref["index"], sample_id=ref["sample_id"], selection_class=ref.get("selection_class"), required_pass=False, required_failures=[],
               top1_ref=None, top1_cand=None, top1_equal=None, top5_ref=None, top5_cand=None, top5_order_equal=None, top5_overlap=None,
               cosine=None, max_abs_diff=None, mean_abs_diff=None, violations=None, bit_identical_runs=None, run1_max_abs_diff=None,
               status="실패", note="")
    result_path = device_dir / f"{prefix}.result.json"
    failure_path = device_dir / f"{prefix}.failure.json"
    if not result_path.is_file():
        err = C.read_json(failure_path).get("error") if failure_path.is_file() else "result.json missing"
        row["required_failures"].append(f"app: {err}")
        row["note"] = str(err)[:200]
        return row
    res = C.read_json(result_path)
    if res.get("input_sha256_actual") != ref["input_sha256"] or res.get("input_sha256_expected") != ref["input_sha256"]:
        row["required_failures"].append("input sha256 != reference input")
    runs = res.get("runs") or []
    if len(runs) != C.RUNS_PER_IMAGE:
        row["required_failures"].append(f"runs {len(runs)} != {C.RUNS_PER_IMAGE}")
        return row
    raw_paths = [device_dir / r["output_file"] for r in runs]
    raws = []
    for k, p in enumerate(raw_paths):
        if not p.is_file():
            row["required_failures"].append(f"run{k} raw file missing")
            return row
        b = p.read_bytes()
        if C.sha256_bytes(b) != runs[k].get("output_sha256"):
            row["required_failures"].append(f"run{k} raw sha != result.json")
        raws.append(b)
    row["bit_identical_runs"] = raws[0] == raws[1]
    if len(raws[0]) != C.OUTPUT_ELEMENTS * 4:
        row["required_failures"].append(f"run0 bytes {len(raws[0])} != 4000 (shape != [1,1000])")
        return row
    cand = C.read_f32le(raw_paths[0], C.OUTPUT_ELEMENTS)
    if not all(math.isfinite(x) for x in cand):
        row["required_failures"].append("non-finite output (run0)")
    if runs[0].get("output_elements") != C.OUTPUT_ELEMENTS:
        row["required_failures"].append(f"output_elements {runs[0].get('output_elements')} != 1000")
    if res.get("backend") != backend:
        row["required_failures"].append(f"result backend {res.get('backend')} != {backend}")
    ref_v = ref["values"]
    # metrics (computed even when 필수 fails, for the record; NaN-aware)
    finite = all(math.isfinite(x) for x in cand)
    if finite:
        t_ref, t_cand = C.topk(ref_v), C.topk(cand)
        row["top1_ref"], row["top1_cand"] = t_ref[0][0], t_cand[0][0]
        row["top1_equal"] = t_ref[0][0] == t_cand[0][0]
        row["top5_ref"] = [i for i, _ in t_ref]
        row["top5_cand"] = [i for i, _ in t_cand]
        row["top5_order_equal"] = row["top5_ref"] == row["top5_cand"]
        row["top5_overlap"] = len(set(row["top5_ref"]) & set(row["top5_cand"]))
        diffs = [abs(c - r) for c, r in zip(cand, ref_v)]
        row["max_abs_diff"] = max(diffs)
        row["mean_abs_diff"] = sum(diffs) / len(diffs)
        row["violations"] = C.tolerance_violations(cand, ref_v)
        row["cosine"] = C.cosine(cand, ref_v)
        if row["cosine"] is None:
            row["note"] = NOT_COMPUTABLE + " (0-norm)"
        if not row["bit_identical_runs"] and len(raws[1]) == C.OUTPUT_ELEMENTS * 4:
            cand1 = C.read_f32le(raw_paths[1], C.OUTPUT_ELEMENTS)
            if all(math.isfinite(x) for x in cand1):
                row["run1_max_abs_diff"] = max(abs(c - r) for c, r in zip(cand1, ref_v))
    row["required_pass"] = not row["required_failures"]
    row["status"] = "ok" if row["required_pass"] else "실패"
    return row


# ----------------------------------------------------------------------------------------------- one backend
def aggregate(rows: list[dict]) -> dict:
    ok = [r for r in rows if r["required_pass"]]
    cos = [r["cosine"] for r in ok if r["cosine"] is not None]
    ov = [r["top5_overlap"] for r in ok if r["top5_overlap"] is not None]
    return dict(images=len(rows), required_pass=len(ok), required_fail=[r["index"] for r in rows if not r["required_pass"]],
                top1_equal=sum(1 for r in ok if r["top1_equal"]), top5_order_equal=sum(1 for r in ok if r["top5_order_equal"]),
                top5_overlap_mean=(sum(ov) / len(ov) / 5) if ov else None, top5_overlap_min=(min(ov) / 5) if ov else None,
                cosine_min=min(cos) if cos else None, cosine_median=statistics.median(cos) if cos else None,
                cosine_not_computable=[r["index"] for r in ok if r["cosine"] is None],
                max_abs_diff_max=max((r["max_abs_diff"] for r in ok), default=None),
                mean_abs_diff_mean=(sum(r["mean_abs_diff"] for r in ok) / len(ok)) if ok else None,
                violations_total=sum(r["violations"] or 0 for r in ok), zero_violation_images=sum(1 for r in ok if r["violations"] == 0),
                violation_images=[r["index"] for r in ok if (r["violations"] or 0) > 0],
                bit_identical_images=sum(1 for r in rows if r["bit_identical_runs"]), bit_identical_known=sum(1 for r in rows if r["bit_identical_runs"] is not None))


def verdict_for(backend: str, agg: dict, summary: dict | None, gpu_precision_observed: str | None) -> tuple[str, list[str]]:
    reasons = []
    if summary is None or not summary.get("runtime_created"):
        return f"{V_FAIL} (runtime 생성 실패)", ["summary 없음" if summary is None else str(summary.get("runtime_create_error") or summary.get("status"))]
    if agg["required_fail"]:
        return f"{V_FAIL} (필수 항목: 이미지 {agg['required_fail']})", ["필수 항목 실패"]
    if backend == "CPU":
        return (V_MATCH, []) if agg["violations_total"] == 0 else (f"{V_MISMATCH} (허용식 위반 이미지 {agg['violation_images']})", ["FP32 허용식 위반"])
    if backend == "GPU":
        if gpu_precision_observed == "FP32":
            return (V_MATCH, ["GPU 실제 정밀도 FP32 로 로그에서 읽음 → CPU 기준"]) if agg["violations_total"] == 0 \
                else (f"{V_MISMATCH} (허용식 위반 이미지 {agg['violation_images']})", ["GPU 실제 정밀도 FP32 로 로그에서 읽음 → CPU 기준", "FP32 허용식 위반"])
        return V_GPU_HOLD, [f"gpu_precision.observed={gpu_precision_observed}"]
    return V_NPU_HOLD, ["FP32 허용식 미적용 (등록 §3)"]


def sentence(backend: str, agg: dict, verdict: str) -> str:
    cos = "계산 불가" if agg["cosine_min"] is None else f"{agg['cosine_min']:.7f}"
    tail = " · NPU 품질 PASS 보류: FP16 합격선 미등록" if backend == "NPU" else ""
    return (f"대표 입력 20장에서 {backend} 출력은 조민규 CPU 참조와 top-1 {agg['top1_equal']}/20 · top-5 순서 {agg['top5_order_equal']}/20 · "
            f"cosine 최소 {cos} 로 일치했다 (참조 일치 — 정답 정확도 아님{tail}). 판정: {verdict}")


def judge_backend(backend: str, ref: dict, device_dir: Path, evidence: dict | None) -> dict:
    summary = C.read_json(device_dir / "summary.json") if (device_dir / "summary.json").is_file() else None
    rows = [judge_image(r, device_dir, backend) for r in ref["refs"]] if (summary and summary.get("runtime_created")) else \
           [dict(index=r["index"], sample_id=r["sample_id"], required_pass=False, required_failures=["runtime not created"], status="실패",
                 top1_equal=None, top5_order_equal=None, top5_overlap=None, cosine=None, max_abs_diff=None, mean_abs_diff=None, violations=None,
                 bit_identical_runs=None, note="") for r in ref["refs"]]
    agg = aggregate(rows)
    ev = (evidence or {}).get("backends", {}).get(backend)
    gpu_prec = ((ev or {}).get("gpu_precision") or {}).get("observed") if backend == "GPU" else None
    verdict, reasons = verdict_for(backend, agg, summary, gpu_prec)
    tags = []
    if ev is not None and ev.get("verdict") != "PASS":
        tags.append(TAG_EVIDENCE_FAIL)
    out = dict(backend=backend, verdict=verdict, verdict_reasons=reasons, tags=tags, aggregate=agg, rows=rows,
               evidence_verdict=(ev or {}).get("verdict"), evidence_failed_conditions=((ev or {}).get("evidence") or {}).get("failed_conditions"),
               gpu_precision_requested=(ev or {}).get("gpu_precision_requested"), gpu_precision_observed=gpu_prec,
               summary_status=(summary or {}).get("status"), runtime_created=(summary or {}).get("runtime_created"),
               model_sha256=(summary or {}).get("model_sha256_actual"), compiled_model_options=(summary or {}).get("compiled_model_options"),
               runtime_init=(summary or {}).get("runtime_init"), run_id=(summary or {}).get("run_id"),
               sentence=sentence(backend, agg, verdict), fp32_tolerance_applied=(backend == "CPU" or (backend == "GPU" and gpu_prec == "FP32")))
    return out


def judge_run(ref: dict, run_root: Path, evidence: dict | None, apk_sha: str | None, backends=C.BACKENDS) -> dict:
    result = dict(schema=SCHEMA, judged_at=C.now_iso(), run_root=str(run_root), apk_sha256=apk_sha, registration=C.REGISTRATION,
                  reference=dict(zip_sha256=C.ZIP_SHA256, quality_reference_sha256=ref["quality_reference_sha256"], runtime=ref.get("runtime"),
                                 runtime_version=ref.get("runtime_version"), cpu_threads=ref.get("cpu_threads"), images=len(ref["refs"])),
                  tolerance=dict(abs=C.TOL_ABS, rel=C.TOL_REL, rule="|cand − ref| ≤ 1e-4 + 1e-3·|ref|", applied_to=["CPU", "GPU only if actual precision read as FP32"]),
                  tie_rule="score descending, then class index ascending", candidate_run="run0 (run1 only for bit-identical column)",
                  backends={})
    for b in backends:
        d = run_root / b / "device"
        if not d.is_dir() and not (run_root / b).is_dir():
            continue
        result["backends"][b] = judge_backend(b, ref, d, evidence)
    cpu = result["backends"].get("CPU")
    cpu_match = bool(cpu and cpu["verdict"] == V_MATCH)
    for b in ("GPU", "NPU"):
        if b in result["backends"] and not cpu_match:
            result["backends"][b]["tags"].append(TAG_CPU_BELOW)
    result["cpu_match"] = cpu_match
    return result


# ----------------------------------------------------------------------------------------------- markdown
def _f(x, nd=7):
    if x is None:
        return "—"
    if isinstance(x, bool):
        return "✔" if x else "✘"
    if isinstance(x, float):
        return f"{x:.{nd}g}" if abs(x) < 1e-3 and x != 0 else f"{x:.{nd}f}".rstrip("0").rstrip(".")
    return str(x)


def markdown(result: dict) -> str:
    L = [f"# Q20 판정 — run `{(next(iter(result['backends'].values()), {}) or {}).get('run_id', '?')}` (판정기 = 등록 §3 그대로 · 결과 전 커밋)", "",
         f"- 참조: zip `{C.ZIP_SHA256[:8]}…` · quality_reference `{result['reference']['quality_reference_sha256'][:8]}…` · 그의 엔진 {result['reference']['runtime']} {result['reference']['runtime_version']} (cpu_threads {result['reference']['cpu_threads']}) · 20장",
         f"- APK SHA-256 `{result.get('apk_sha256')}` · 허용식 {result['tolerance']['rule']} (적용: CPU · GPU 는 실제 정밀도 FP32 확인 시) · 동률 = {result['tie_rule']} · 후보 = {result['candidate_run']}",
         "- 참조 일치 — 정답 정확도 아님 (등록 §0). NPU 는 허용식 미적용 · PASS 보류. 실행 장치는 증거 (evidence.json) 로 따로 판단.", "",
         "## backend 별 판정", "", "| backend | 판정 | 꼬리표 | 실행 증거 | runtime | top-1 | top-5 순서 | 집합 겹침 평균/최소 | cosine 최소/중앙 | 최대\\|차\\| 최댓값 | 위반 0 이미지 | 2회 비트 동일 |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for b, r in result["backends"].items():
        a = r["aggregate"]
        viol = f"{a['zero_violation_images']}/{a['required_pass']}" + ("" if r["fp32_tolerance_applied"] else " (기록만)")
        L.append(f"| {b} | **{r['verdict']}** | {' · '.join(r['tags']) or '—'} | {r['evidence_verdict'] or '—'} | {'생성' if r['runtime_created'] else '실패'} | "
                 f"{a['top1_equal']}/20 | {a['top5_order_equal']}/20 | {_f(a['top5_overlap_mean'], 3)}/{_f(a['top5_overlap_min'], 3)} | "
                 f"{_f(a['cosine_min'])}/{_f(a['cosine_median'])} | {_f(a['max_abs_diff_max'], 4)} | {viol} | {a['bit_identical_images']}/{a['bit_identical_known']} |")
    L += ["", "## 결과 문장 (등록 §3 틀 · 숫자만)", ""]
    for b, r in result["backends"].items():
        L.append(f"- {r['sentence']}" + (f" [{' · '.join(r['tags'])}]" if r["tags"] else ""))
    for b, r in result["backends"].items():
        L += ["", f"## {b} 이미지별 ({'허용식 적용' if r['fp32_tolerance_applied'] else '허용식 미적용 — 위반 수는 기록만'})", "",
              "| # | sample | 클래스 | 필수 | top-1 참조→후보 | top-1 | top-5 순서 | 겹침 | cosine | 최대\\|차\\| | 평균\\|차\\| | 위반 수 | 2회 동일 | 비고 |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for w in r["rows"]:
            ov = f"{w['top5_overlap']}/5" if w.get("top5_overlap") is not None else "—"
            cos = NOT_COMPUTABLE if (w.get("required_pass") and w.get("cosine") is None) else _f(w.get("cosine"))
            L.append(f"| {w['index']} | `{w['sample_id']}` | {w.get('selection_class') or ''} | {'✔' if w['required_pass'] else '✘ ' + '; '.join(w['required_failures'])[:80]} | "
                     f"{_f(w.get('top1_ref'))}→{_f(w.get('top1_cand'))} | {_f(w.get('top1_equal'))} | {_f(w.get('top5_order_equal'))} | {ov} | {cos} | "
                     f"{_f(w.get('max_abs_diff'), 4)} | {_f(w.get('mean_abs_diff'), 4)} | {_f(w.get('violations'))} | {_f(w.get('bit_identical_runs'))} | {w.get('note', '')} |")
    L.append("")
    return "\n".join(L)


# ----------------------------------------------------------------------------------------------- selftest (synthetic reference, never the real one)
def _synthetic_softmax(seed: int) -> list[float]:
    raw = [((i * 7919 + seed * 104729) % 1000) / 1000.0 for i in range(1000)]
    raw[seed % 1000] = 5.0
    raw[(seed * 3 + 1) % 1000] = 4.0
    raw[(seed * 5 + 2) % 1000] = 3.5
    raw[(seed * 7 + 3) % 1000] = 3.0
    raw[(seed * 11 + 4) % 1000] = 2.5
    e = [math.exp(x) for x in raw]
    s = sum(e)
    return [float(struct_f32(x / s)) for x in e]


def struct_f32(x: float) -> float:
    import struct
    return struct.unpack("<f", struct.pack("<f", x))[0]


def _write_reference(root: Path) -> dict:
    inputs = root / "ref"
    samples, qsamples = [], []
    for i in range(20):
        sid = "%016x" % (0x2000_0000_0000_0000 + i * 7919)
        values = _synthetic_softmax(i + 1)
        raw = C.f32le_bytes(values)
        (inputs / "references" / sid).mkdir(parents=True, exist_ok=True)
        (inputs / "references" / sid / "output_0.f32le").write_bytes(raw)
        (inputs / "inputs" / sid).mkdir(parents=True, exist_ok=True)
        in_bytes = bytes((j * 31 + i) & 0xFF for j in range(C.INPUT_BYTES))
        (inputs / "inputs" / sid / "input.f32le").write_bytes(in_bytes)
        in_sha = C.sha256_bytes(in_bytes)
        samples.append(dict(sample_id=sid, input_file=f"inputs/{sid}/input.f32le", input_bytes=C.INPUT_BYTES, input_sha256=in_sha,
                            reference_file=f"references/{sid}/output_0.f32le", reference_sha256=C.sha256_bytes(raw), model_sha256=C.ORIGINAL_MODEL_SHA256,
                            label_sha256=C.LABELS_SHA256))
        qsamples.append(dict(image=dict(sample_id=sid), selection_class="Synthetic", output_float32=values,
                             reference=dict(raw_output_sha256=C.sha256_bytes(raw), decoder=dict(class_index_offset=0, ordering="score descending then class index ascending", top_k=5),
                                            label_sha256=C.LABELS_SHA256, model_sha256=C.ORIGINAL_MODEL_SHA256, input_tensor_sha256=in_sha,
                                            tensor_metadata=dict(outputs=[dict(dtype="<class 'numpy.float32'>", shape=[1, 1000])]),
                                            runtime="synthetic", runtime_version="0", cpu_threads=1)))
    qr = dict(schema="s26-quality-handoff-v1", samples=qsamples)
    C.write_json(inputs / "quality_reference.json", qr)
    qr_sha = C.sha256_file(inputs / "quality_reference.json")
    m = dict(schema="s26-tensor-transfer-v1", shape=[1, 224, 224, 3], dtype="float32", endianness="little", layout="NHWC_RGB",
             quality_reference_sha256=qr_sha, samples=samples)
    C.write_json(inputs / "tensor_manifest.json", m)
    return dict(dir=inputs, manifest=m, qr_sha=qr_sha)


def _write_candidate(root: Path, backend: str, refs: list[dict], mutate, runtime_created=True, run_id="selftest"):
    d = root / backend / "device"
    d.mkdir(parents=True, exist_ok=True)
    C.write_json(d / "summary.json", dict(schema="s26-q20-summary-v1", run_id=run_id, backend=backend, runtime_key=f"classification_{backend}",
                                          status="completed" if runtime_created else "runtime_create_failed", runtime_created=runtime_created,
                                          runtime_create_error=None if runtime_created else "fake", model_sha256_actual="x",
                                          compiled_model_options=dict(gpu_options=dict(precision="FP32") if backend == "GPU" else None), runtime_init={}))
    if not runtime_created:
        return
    for r in refs:
        prefix = "%02d_%s" % (r["index"], r["sample_id"])
        v0, v1 = mutate(r["index"], list(r["values"]))
        raw0, raw1 = C.f32le_bytes(v0), C.f32le_bytes(v1)
        (d / f"{prefix}.run0.f32le").write_bytes(raw0)
        (d / f"{prefix}.run1.f32le").write_bytes(raw1)
        C.write_json(d / f"{prefix}.result.json", dict(index=r["index"], sample_id=r["sample_id"], backend=backend,
                                                       input_sha256_expected=r["input_sha256"], input_sha256_actual=r["input_sha256"],
                                                       runs=[dict(run=0, output_file=f"{prefix}.run0.f32le", output_elements=len(v0), output_sha256=C.sha256_bytes(raw0)),
                                                             dict(run=1, output_file=f"{prefix}.run1.f32le", output_elements=len(v1), output_sha256=C.sha256_bytes(raw1))]))


def selftest() -> int:
    failures = []

    def expect(label, cond):
        print(("ok   " if cond else "FAIL ") + label)
        if not cond:
            failures.append(label)

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        synth = _write_reference(root)
        # registered-hash checks are bypassed for the synthetic reference by monkeypatching the constants locally
        saved = (C.QUALITY_REFERENCE_SHA256,)
        C.QUALITY_REFERENCE_SHA256 = synth["qr_sha"]
        try:
            ref = load_reference(synth["dir"])
            refs = ref["refs"]
            ident = lambda i, v: (v, list(v))  # noqa: E731
            ev_hold = dict(backends=dict(CPU=dict(verdict="PASS"), GPU=dict(verdict="PASS", gpu_precision=dict(observed="미확인"), gpu_precision_requested="FP32"), NPU=dict(verdict="PASS")))
            ev_fp32 = dict(backends=dict(CPU=dict(verdict="PASS"), GPU=dict(verdict="PASS", gpu_precision=dict(observed="FP32"), gpu_precision_requested="FP32"), NPU=dict(verdict="FAIL", evidence=dict(failed_conditions=["enn_loaded_in_runner_pid"]))))

            # case A: reference as candidate everywhere → CPU 일치 · GPU 보류 (미확인) · NPU 보류
            a = root / "A"
            for b in C.BACKENDS:
                _write_candidate(a, b, refs, ident)
            ra = judge_run(ref, a, ev_hold, "apk")
            expect("A CPU 일치", ra["backends"]["CPU"]["verdict"] == V_MATCH)
            expect("A CPU 20/20 top1 · top5 · 위반 0 · 비트 동일 20", ra["backends"]["CPU"]["aggregate"]["top1_equal"] == 20 and ra["backends"]["CPU"]["aggregate"]["top5_order_equal"] == 20
                   and ra["backends"]["CPU"]["aggregate"]["violations_total"] == 0 and ra["backends"]["CPU"]["aggregate"]["bit_identical_images"] == 20)
            expect("A CPU cosine 최소 1", abs(ra["backends"]["CPU"]["aggregate"]["cosine_min"] - 1.0) < 1e-12)
            expect("A GPU 보류 (미확인)", ra["backends"]["GPU"]["verdict"] == V_GPU_HOLD and not ra["backends"]["GPU"]["fp32_tolerance_applied"])
            expect("A NPU 보류", ra["backends"]["NPU"]["verdict"] == V_NPU_HOLD and not ra["backends"]["NPU"]["fp32_tolerance_applied"])
            expect("A 꼬리표 없음", not ra["backends"]["GPU"]["tags"] and not ra["backends"]["NPU"]["tags"])
            expect("A 문장", ra["backends"]["CPU"]["sentence"].startswith("대표 입력 20장에서 CPU 출력은 조민규 CPU 참조와 top-1 20/20 · top-5 순서 20/20 · cosine 최소 1.0000000 로 일치했다"))
            md = markdown(ra)
            expect("A markdown 표", "| CPU | **참조와 일치 (FP32 기존 경로 기준)** |" in md and "(기록만)" in md)

            # case B: CPU one element +1e-3 on image 4 (beyond tolerance) → 위반 1 · 불일치 [4]; GPU precision FP32 → CPU rule → 일치;
            #         NPU with the same +1e-3 → still 보류 (tolerance not applied) but the violation count is recorded; NPU evidence FAIL → tag
            def plus(i, v):
                if i == 4:
                    v[0] += 1e-3
                return v, list(v)
            bdir = root / "B"
            _write_candidate(bdir, "CPU", refs, plus)
            _write_candidate(bdir, "GPU", refs, ident)
            _write_candidate(bdir, "NPU", refs, plus)
            rb = judge_run(ref, bdir, ev_fp32, "apk")
            expect("B CPU 불일치 [4]", rb["backends"]["CPU"]["verdict"].startswith(V_MISMATCH) and rb["backends"]["CPU"]["aggregate"]["violation_images"] == [4])
            expect("B CPU 위반 1", rb["backends"]["CPU"]["rows"][4]["violations"] == 1 and rb["backends"]["CPU"]["aggregate"]["violations_total"] == 1)
            expect("B GPU FP32 → CPU 기준 → 일치", rb["backends"]["GPU"]["verdict"] == V_MATCH and rb["backends"]["GPU"]["fp32_tolerance_applied"])
            expect("B NPU 허용식 미적용 → 보류", rb["backends"]["NPU"]["verdict"] == V_NPU_HOLD and rb["backends"]["NPU"]["rows"][4]["violations"] == 1)
            expect("B CPU 미달 꼬리표 GPU · NPU", TAG_CPU_BELOW in rb["backends"]["GPU"]["tags"] and TAG_CPU_BELOW in rb["backends"]["NPU"]["tags"])
            expect("B NPU 증거 FAIL 꼬리표", TAG_EVIDENCE_FAIL in rb["backends"]["NPU"]["tags"] and TAG_EVIDENCE_FAIL not in rb["backends"]["GPU"]["tags"])

            # case C: NaN (image 2) → 필수 실패 · "실패"; top-1 swapped (image 7); top-5 order swapped only (image 9); run1 differs (image 11);
            #         0-norm (image 13) → cosine 계산 불가 (필수 통과) · tolerance violated
            def mix(i, v):
                if i == 2:
                    v[5] = float("nan")
                if i == 7:
                    t = C.topk(v)
                    v[t[0][0]], v[t[1][0]] = v[t[1][0]], v[t[0][0]]
                if i == 9:
                    t = C.topk(v)
                    v[t[3][0]], v[t[4][0]] = v[t[4][0]], v[t[3][0]]
                if i == 13:
                    v = [0.0] * 1000
                v1 = list(v)
                if i == 11:
                    v1[0] = struct_f32(v1[0] + 1e-7)
                return v, v1
            cdir = root / "C"
            _write_candidate(cdir, "CPU", refs, mix)
            rc = judge_run(ref, cdir, None, "apk")
            cpu = rc["backends"]["CPU"]
            expect("C CPU 실패 (필수)", cpu["verdict"].startswith(V_FAIL) and cpu["aggregate"]["required_fail"] == [2])
            expect("C NaN 행 필수 ✘", not cpu["rows"][2]["required_pass"] and "non-finite" in cpu["rows"][2]["required_failures"][0])
            expect("C top-1 바뀜", cpu["rows"][7]["top1_equal"] is False and cpu["rows"][7]["top5_overlap"] == 5)
            expect("C top-5 순서만", cpu["rows"][9]["top1_equal"] is True and cpu["rows"][9]["top5_order_equal"] is False and cpu["rows"][9]["top5_overlap"] == 5)
            expect("C 2회 비트 다름", cpu["rows"][11]["bit_identical_runs"] is False and cpu["rows"][11]["run1_max_abs_diff"] is not None and cpu["rows"][10]["bit_identical_runs"] is True)
            expect("C 0-norm cosine 계산 불가 · 필수 통과", cpu["rows"][13]["required_pass"] and cpu["rows"][13]["cosine"] is None and NOT_COMPUTABLE in cpu["rows"][13]["note"]
                   and 13 in cpu["aggregate"]["cosine_not_computable"])
            expect("C 증거 없음 → 꼬리표 없음 (CPU 미달 꼬리표는 다른 backend 에만)", cpu["tags"] == [])

            # case D: runtime not created → 실패 (runtime 생성 실패); missing result (image 3) → 실패 preserved
            ddir = root / "D"
            _write_candidate(ddir, "NPU", refs, ident, runtime_created=False)
            _write_candidate(ddir, "GPU", refs, ident)
            (ddir / "GPU" / "device" / ("%02d_%s.result.json" % (3, refs[3]["sample_id"]))).unlink()
            C.write_json(ddir / "GPU" / "device" / ("%02d_%s.failure.json" % (3, refs[3]["sample_id"])), dict(error="java.lang.IllegalStateException: input sha256 mismatch"))
            rd = judge_run(ref, ddir, ev_hold, "apk")
            expect("D NPU runtime 생성 실패", rd["backends"]["NPU"]["verdict"] == f"{V_FAIL} (runtime 생성 실패)")
            expect("D GPU 이미지 3 실패 보존", rd["backends"]["GPU"]["verdict"].startswith(V_FAIL) and rd["backends"]["GPU"]["aggregate"]["required_fail"] == [3]
                   and "sha256 mismatch" in rd["backends"]["GPU"]["rows"][3]["note"])
            expect("D CPU 없음 → 미달 꼬리표", TAG_CPU_BELOW in rd["backends"]["GPU"]["tags"])

            # tie rule: equal scores → lower index first
            v = [0.0] * 1000
            v[10] = v[3] = 0.5
            expect("동률 → index 오름차순", [i for i, _ in C.topk(v)][:2] == [3, 10])
            expect("허용식 경계 (= 허용)", C.tolerance_violations([0.5 + 1e-4 + 5e-4], [0.5]) == 0 and C.tolerance_violations([0.5 + 1e-4 + 5e-4 + 1e-6], [0.5]) == 1)
            json.dumps(ra, ensure_ascii=False)
        finally:
            (C.QUALITY_REFERENCE_SHA256,) = saved
    print("SELFTEST", ("FAIL: " + "; ".join(failures)) if failures else "PASS")
    return 1 if failures else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run")
    ap.add_argument("--reference", default=str(C.DEFAULT_INPUTS_DIR))
    ap.add_argument("--evidence")
    ap.add_argument("--apk-sha")
    ap.add_argument("--out-dir")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if not a.run:
        ap.error("--run or --selftest")
    run_root = Path(a.run)
    ref = load_reference(Path(a.reference))
    evidence = C.read_json(a.evidence) if a.evidence else (C.read_json(run_root / "evidence.json") if (run_root / "evidence.json").is_file() else None)
    result = judge_run(ref, run_root, evidence, a.apk_sha)
    out_dir = Path(a.out_dir) if a.out_dir else run_root
    C.write_json(out_dir / "q20_judgement.json", result)
    (out_dir / "q20_judgement.md").write_text(markdown(result), encoding="utf-8", newline="\n")
    for b, r in result["backends"].items():
        print(b, r["verdict"], r["tags"])
    print("written", out_dir / "q20_judgement.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
