#!/usr/bin/env python3
"""Build the small, filtered log excerpts used by tools/test_compiled_model_evidence.py (P2, 2026-09-28).

Raw logcat is never committed (it can hold SIM identifiers). An excerpt keeps only:
  * every line from the runner process except D1GPU / D1CHECK_EVENT events,
  * every line (any process) that any rule regex matches (replacement, failure, ENN, XNNPACK, GPU),
  * the first two and the last D1GPU / D1NPU line (runner PID evidence),
and drops any line matching iccid|Euicc|imsi|msisdn|phone. For each excerpt the generator re-runs all
three rules on the full log and on the excerpt and refuses to write if any verdict differs.

    py tools/fixtures/compiled_model_evidence/make_fixtures.py   (needs the git-ignored results/ tree
                                                                  and the 산공학회 diagnostic logs)
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
spec = importlib.util.spec_from_file_location("compiled_model_evidence_fixtures", REPO / "tools" / "compiled_model_evidence.py")
EVIDENCE = importlib.util.module_from_spec(spec)
spec.loader.exec_module(EVIDENCE)

SENSITIVE = re.compile(r"iccid|euicc|imsi|msisdn|phone", re.IGNORECASE)
LOGGER = EVIDENCE._logger()
ANY_RULE = re.compile("|".join([
    EVIDENCE.REPLACE_RE.pattern, EVIDENCE.FAILURE_RE.pattern, EVIDENCE.GPU_SUPPORT_RE.pattern,
    EVIDENCE.GPU_FAILURE_RE.pattern, LOGGER.NPU_ENN_LOADED_RE.pattern, re.escape(EVIDENCE.CPU_CREATED),
    LOGGER.NPU_DISPATCH_FAILURE_RE.pattern,
]), re.IGNORECASE)
DIAG = Path("C:/Users/rhoyo/OneDrive/문서/Mine/26-2/산공학회/D1_ondevice/measure/s26/npu/results")
C5 = REPO / "results" / "S26_C5_cpu_compiled_0927"
NPU_FORMAL = REPO / "results" / "S26_NPU_formal_0925b"


def excerpt(text: str) -> list[str]:
    lines = text.splitlines()
    rows = {row["line"]: row for row in EVIDENCE.parse_log(text)}
    pids = EVIDENCE.runner_pids(list(rows.values()))
    runner_event = [n for n, row in rows.items() if row["pid"] in pids and row["tag"] in EVIDENCE.RUNNER_TAGS]
    keep = set(runner_event[:2] + runner_event[-1:])
    for number, row in rows.items():
        if row["pid"] in pids and row["tag"] not in ("D1GPU", "D1CHECK_EVENT"):
            keep.add(number)
        if ANY_RULE.search(row["msg"]):
            keep.add(number)
    return [lines[n - 1] for n in sorted(keep) if not SENSITIVE.search(lines[n - 1])]


def verdicts(text: str, metadata: dict) -> dict:
    return {rule: fn(text, dict(metadata, npu_accelerator_requested=claim))["verdict"]
            for rule, fn, claim in (("cpu", EVIDENCE.evaluate_cpu, "CPU"),
                                    ("npu", EVIDENCE.evaluate_npu, "NPU"),
                                    ("gpu", EVIDENCE.evaluate_gpu_candidate, "GPU"))}


def run_metadata(run_dir: Path) -> dict:
    runner = sorted((run_dir / "gpu").glob("gpu-events-*.jsonl"))[0]
    with runner.open(encoding="utf-8") as stream:
        first = json.loads(stream.readline())
    return {key: first.get(key) for key in ("npu_accelerator_requested", "model_sha256", "resource")}


def main() -> int:
    sources: list[tuple[str, Path, dict, str]] = []
    order = sorted(json.loads((C5 / "experiment_manifest.json").read_text("utf-8"))["runs"],
                   key=lambda r: r["attempt_started_utc"])
    for index, slot in enumerate(order, 1):
        role = "rule_building" if index <= 5 else "holdout"
        run_dir = C5 / "runs" / slot["run_id"]
        sources.append((f"c5_run{index:02d}_{slot['slot_id']}", run_dir / "raw" / "logcat.txt",
                        run_metadata(run_dir), f"C5 CPU CompiledModel, execution order {index} ({role})"))
    formal = json.loads((NPU_FORMAL / "experiment_manifest.json").read_text("utf-8"))["runs"]
    for slot in sorted(formal, key=lambda r: r.get("attempt_started_utc") or ""):
        if slot.get("status") != "completed":
            continue
        run_dir = NPU_FORMAL / "runs" / slot["run_id"]
        summary = json.loads((run_dir / "merged" / "summary.json").read_text("utf-8"))
        metadata = dict(run_metadata(run_dir),
                        existing_formal_npu_valid=summary.get("formal_npu_valid"),
                        existing_npu_evidence=summary.get("npu_delegate_evidence", {}).get("verification"))
        sources.append((f"npu_formal_0925b_{slot['slot_id']}", run_dir / "raw" / "logcat.txt",
                        metadata, "9/25 NPU formal (existing verdicts recorded from merged/summary.json)"))
    for name, file in (("g4_diag_0924_0414_npu", "G4_DIAG_NPU_2026-09-24414_3202.txt"),
                       ("g4_diag_0924_0455_npu", "G4_DIAG_NPU_2026-09-24455_1519_WIRELESS_ACPLUGGED.txt")):
        sources.append((name, DIAG / file, {"model_sha256": "1415b2c87d01b67a9380b8f912e2b4ef4561502105b06f313332c97c1c8cb5cf"},
                        "9/24 NPU smoke diagnostic dump: DispatchDelegate line then dispatch kernel failure"))
    manifest = {}
    for name, path, metadata, note in sources:
        text = path.read_text(encoding="utf-8", errors="replace")
        lines = excerpt(text)
        small = "\n".join(lines) + "\n"
        full_verdicts, small_verdicts = verdicts(text, metadata), verdicts(small, metadata)
        if full_verdicts != small_verdicts:
            print(f"REFUSED {name}: full {full_verdicts} != excerpt {small_verdicts}", file=sys.stderr)
            return 1
        (HERE / f"{name}.log").write_text(small, encoding="utf-8", newline="\n")
        manifest[name] = {
            "note": note, "source": str(path.relative_to(REPO)) if REPO in path.parents else path.name,
            "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "source_lines": len(text.splitlines()), "excerpt_lines": len(lines),
            "metadata": metadata, "verdicts_full_equals_excerpt": full_verdicts,
        }
    (HERE / "MANIFEST.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                                        encoding="utf-8", newline="\n")
    print(f"wrote {len(manifest)} excerpts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
