"""Phone smoke S1 + S2 in one command (등록 §11-1 · prompt 6부). Re-runnable by R2 before its first session when R1 had no phone.

  set ANDROID_SERIAL=<ip:port>
  py -3 s26/tools/mixreq/mixreq_smoke.py --plan s26/results/mixreq_1008/plan_v1 --results results\\S26_MIXREQ_SMOKE_1009
      [--reference-pc local_inputs/reference_pc/reference_pc.json] [--dry-run] [--skip-gate] [--only S1|S2]

S1 (quality smoke, block N configuration, warmup only = 10 calls): 5 runtimes created · classification tensor SHA 603328d0… ·
decoded RGB SHA ca6c2e2b… · S26 CPU top-5 == A24 PC reference (label+index; |ds| recorded) · S26 CPU detection warmup decode vs the
PC reference decode (A24 tolerance; stand-in for the A24 phone baseline which is still awaited) · GPU vs CPU (§4-6) · detection_GPU
created? · GPU / NPU delegation evidence lines · §4-N NPU contract first values (recorded only) · observed thread count (top -H).
S2 (short sessions, first 24 requests): CPU · PAR (block A config) · PAR-NPU (block N config) → validity (short) · overlap ·
arrival delay · parallel verification (§3-3): (a) no error (b) overlap > 0 (c) evidence PASS for the used accelerated runtime
(d) actual runtime == assignment. PAR fail -> "block A: do not run"; PAR-NPU fail -> "block N: do not run".
No KPI comparison and no conclusion sentence are printed (smoke numbers must not change the design).
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import mixreq_common as C  # noqa: E402
import mixreq_validate as V  # noqa: E402
import policy_ref  # noqa: E402


def run_session(args, smoke_name: str) -> int:
    cmd = [sys.executable, "-X", "utf8", str(HERE / "mixreq_session.py"), "--plan", str(args.plan), "--smoke", smoke_name, "--results", str(args.results)]
    if args.dry_run:
        cmd.append("--dry-run")
    if args.skip_gate:
        cmd.append("--skip-gate")
    print("RUN", " ".join(cmd[3:]), flush=True)
    return subprocess.call(cmd)


def folder_of(args, smoke_name: str) -> Path:
    return args.results / f"S26_MIXREQ_SMOKE_{smoke_name}_a1"


def s1_checks(folder: Path, reference_pc: dict | None) -> dict:
    out = dict(name="S1", folder=str(folder), checks={}, record={})
    device = folder / "device"
    if not (device / "warmup.json").is_file():
        out["checks"]["artifacts"] = False
        out["record"]["error"] = "warmup.json missing"
        return out
    data = V.load_session(folder, device)
    warm = data["warmup"] or []
    by_key: dict[str, list] = {}
    for w in warm:
        by_key.setdefault(w["key"], []).append(w)
    for k in by_key:
        by_key[k].sort(key=lambda w: w["index"])
    created = {e["key"] for e in data["events"] if e.get("kind") == "runtime_return"}
    out["checks"]["five_runtimes_created"] = created == set(policy_ref.BLOCK_KEYS["N"])
    out["record"]["created"] = sorted(created)
    out["checks"]["ten_warmups"] = len(warm) == 10
    cpu = by_key.get("classification_CPU", [])
    if cpu:
        r0 = cpu[0]["result"]
        out["checks"]["classification_tensor_sha_603328d0"] = r0.get("input_tensor_sha256") == C.CLS_INPUT_TENSOR_SHA256
        out["checks"]["decoded_rgb_sha_ca6c2e2b"] = r0.get("decoded_rgb_sha256") == C.RGB_SHA256
        out["record"]["cpu_top5"] = r0["results"]
        if reference_pc:
            ref = reference_pc["classification"]["results"]
            cmp = V.compare_classification(ref, r0["results"])
            out["checks"]["cpu_top5_label_index_equals_pc_reference"] = all(p["label"] and p["index"] for p in cmp["pairs"]) and len(r0["results"]) == 5
            out["record"]["cpu_top5_vs_pc_reference_score_deltas"] = [p["score_delta"] for p in cmp["pairs"]]
            out["record"]["cpu_top5_within_1e-3_of_pc_reference"] = cmp["passed"]
            out["record"]["cpu_raw_output_sha_equals_pc_reference"] = (r0.get("raw_output_sha256") or [None])[0] == reference_pc["classification"]["raw_output_sha256"]
    det = by_key.get("detection_CPU", [])
    if det:
        d0 = det[0]["result"]
        out["record"]["det_cpu_decoded"] = d0["results"]
        out["record"]["det_input_tensor_sha256"] = d0.get("input_tensor_sha256")
        if reference_pc:
            cmp = V.compare_detection(reference_pc["detection"]["decoded"], d0["results"])
            out["checks"]["det_cpu_equals_pc_reference_decode_a24_tolerance"] = cmp["passed"]
            out["record"]["det_cpu_vs_pc_reference"] = cmp
            out["record"]["det_input_tensor_equals_pc_reference"] = d0.get("input_tensor_sha256") == reference_pc["detection"]["input_tensor_sha256"]
            out["record"]["a24_phone_detection_baseline"] = "awaiting 조민규 zip — PC reference (ai-edge-litert CPU) used as the stand-in"
    for key in ("classification_GPU", "detection_GPU"):
        entries = by_key.get(key, [])
        task = key.rsplit("_", 1)[0]
        ref = by_key.get(f"{task}_CPU", [])
        if entries and ref:
            cmps = [V.compare_results(task, ref[0]["result"]["results"], e["result"]["results"]) for e in entries]
            out["checks"][f"{key}_vs_cpu_4_6"] = all(c["passed"] for c in cmps)
            out["record"][f"{key}_vs_cpu"] = cmps
    summary = data.get("summary") or {}
    out["checks"]["detection_gpu_created"] = summary.get("detection_gpu_created", "detection_GPU" in created)
    # evidence
    logcat = folder / "host" / "logcat_threadtime.txt"
    if logcat.is_file():
        rows = V.parse_logcat(logcat)
        pid, marks, err = V.marks_for(rows, data["manifest"]["session_id"])
        out["record"]["runner_pid"] = pid
        if err:
            out["record"]["marks_error"] = err
        else:
            for key in ("classification_GPU", "detection_GPU"):
                out["record"][f"evidence_{key}"] = V.gpu_evidence(rows, pid, marks, key)
                out["checks"][f"evidence_{key}"] = out["record"][f"evidence_{key}"].get("verdict") == "PASS"
            spec = next(r for r in data["manifest"]["runtimes"] if r["key"] == "classification_NPU")
            out["record"]["evidence_classification_NPU"] = V.npu_evidence(rows, pid, marks, "classification_NPU", spec["model_sha256"])
            out["checks"]["evidence_classification_NPU"] = out["record"]["evidence_classification_NPU"].get("verdict") == "PASS"
    out["record"]["npu_contract_first_values"] = V.npu_contract(data)
    top = folder / "host" / "top_h.txt"
    if top.is_file():
        counts = [len([l for l in block.splitlines() if re.match(r"^\s*\d+\s+\d+\s", l)]) for block in top.read_text(encoding="utf-8", errors="replace").split("### ")[1:]]
        out["record"]["observed_thread_rows_top_h_max"] = max(counts) if counts else None
        out["record"]["cpu_threads_configured"] = 1
    return out


def s2_checks(folder: Path, policy: str) -> dict:
    out = dict(name=f"S2_{policy}", folder=str(folder), checks={}, record={})
    validated_path = folder / "validated.json"
    if not validated_path.is_file():
        out["checks"]["validated"] = False
        return out
    v = C.read_json(validated_path)
    out["record"]["validated_reasons"] = v.get("reasons")
    out["record"]["eligible_short"] = v.get("eligible")
    rules = v.get("rules", {})
    out["checks"]["a_no_error"] = rules.get("0_artifacts", {}).get("passed") is True and rules.get("9_watch_stop", {}).get("passed") is True
    overlap = rules.get("5_overlap", {}).get("detail", {}).get("overlap_s")
    out["record"]["overlap_s"] = overlap
    out["checks"]["b_overlap"] = (overlap == 0) if policy == policy_ref.POLICY_CPU else (overlap is not None and overlap > 0)
    out["checks"]["c_evidence"] = rules.get("7_delegation_evidence", {}).get("passed") is True
    out["checks"]["d_assignment"] = rules.get("4_assignment_residents", {}).get("passed") is True
    out["record"]["time_order"] = rules.get("2_time_order", {}).get("passed")
    out["record"]["window"] = rules.get("3_window", {}).get("passed")
    out["record"]["requests"] = rules.get("1_requests_succeeded_quality", {}).get("detail", {})
    if (folder / "npu_contract.json").is_file():
        out["record"]["npu_contract_first_values"] = C.read_json(folder / "npu_contract.json")
    out["parallel_verification_passed"] = all(out["checks"].get(k) for k in ("a_no_error", "b_overlap", "c_evidence", "d_assignment"))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--plan", required=True, type=Path)
    ap.add_argument("--results", required=True, type=Path)
    ap.add_argument("--reference-pc", type=Path)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--skip-gate", action="store_true")
    ap.add_argument("--only", choices=("S1", "S2"))
    args = ap.parse_args()
    reference = C.read_json(args.reference_pc) if args.reference_pc and args.reference_pc.is_file() else None
    report = dict(schema="s26-mixreq-smoke-report-v1", dry_run=args.dry_run, S1=None, S2=[], decisions=[])
    if args.only != "S2":
        rc = run_session(args, "S1_warmup_only_blockN")
        report["S1_rc"] = rc
        if not args.dry_run:
            report["S1"] = s1_checks(folder_of(args, "S1_warmup_only_blockN"), reference)
            s1 = report["S1"]["checks"]
            if s1.get("cpu_top5_label_index_equals_pc_reference") is False or s1.get("det_cpu_equals_pc_reference_decode_a24_tolerance") is False:
                report["decisions"].append("R2 를 시작하지 말 것 — S26 CPU 출력이 PC 참조와 다름 (이식 오류 의심, 등록 §11-1 ①②)")
    if args.only != "S1":
        for name, policy in (("S2_CPU_URGENT_ONLINE_V1", policy_ref.POLICY_CPU), ("S2_B2_PARALLEL_ONLINE_V1", policy_ref.POLICY_PAR),
                             ("S2_S26_NPU_PARALLEL_V1", policy_ref.POLICY_PAR_NPU)):
            rc = run_session(args, name)
            entry = dict(name=name, rc=rc)
            if not args.dry_run:
                entry.update(s2_checks(folder_of(args, name), policy))
                if policy == policy_ref.POLICY_PAR and not entry.get("parallel_verification_passed"):
                    report["decisions"].append("블록 A 미실행 — PAR 병행 검증 실패 (등록 §3-3)")
                if policy == policy_ref.POLICY_PAR_NPU and not entry.get("parallel_verification_passed"):
                    report["decisions"].append("블록 N 미실행 — PAR-NPU 병행 검증 실패 (등록 §3-3)")
            report["S2"].append(entry)
    report["note"] = "스모크 = 동작 확인용. KPI 비교 · 결론 문장 없음. NPU 계약 첫 값은 기록만 (기준 · 설계 · 블록 N 실행 여부를 바꾸지 않는다)."
    args.results.mkdir(parents=True, exist_ok=True)
    C.write_json(args.results / "smoke_report.json", report)
    print(json.dumps({k: v for k, v in report.items() if k != "S1" or v is None} | {"S1_checks": (report["S1"] or {}).get("checks")}, ensure_ascii=False, indent=1)[:5000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
