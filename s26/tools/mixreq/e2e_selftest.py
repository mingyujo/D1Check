"""End-to-end PC self-test: K6 round-trip artifacts (request-runner/build/mixreq-roundtrip) → synthetic logcat → mixreq_validate →
mixreq_readout, one command. Exit 0 only when every expectation holds.

  py -3 s26/tools/mixreq/e2e_selftest.py [--roundtrip request-runner/build/mixreq-roundtrip] [--plan s26/results/mixreq_1008/plan_v1/plan.json]
      [--out <dir, default build/mixreq-e2e>]

Expectations: blockA_cpu · blockA_par · blockN_cpu · blockN_parnpu → eligible (all 9 rules incl. evidence from the synthetic logcat);
blockN_npu_create_fails → ineligible (0_artifacts, 4_assignment); blockA_plugged → ineligible (0/8/9 stop_reason); NPU contract computed
for block N (PASS on the fake outputs); readout: block A = "쌍 부족 — 기술만" (1 pair), block N likewise; A24 formula cross-check = match;
negative evidence variants (no ENN line / 0 of 1 replacement / failure line / other delegate) → rule 7 FAIL.
The synthetic logcat only exercises the *parsing* of the frozen regexes; it is not device evidence.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE))
import mixreq_common as C  # noqa: E402
import mixreq_validate as V  # noqa: E402

PID = 24680


def logcat_line(n: int, pid: int, tag: str, msg: str, level: str = "I") -> str:
    sec = n // 1000
    return f"10-09 01:{(sec // 60) % 60:02d}:{sec % 60:02d}.{n % 1000:03d} {pid:5d} {pid + 7:5d} {level} {tag:<8}: {msg}"


def synthetic_logcat(device: Path, variant: str = "good") -> str:
    """Rebuild the D1MIX mark sequence from progress.jsonl and insert evidence lines inside the right windows."""
    events = [json.loads(l) for l in (device / "progress.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    manifest = C.read_json(device / "manifest.json")
    sid = manifest["session_id"]
    lines, n = [], 0

    def add(tag, msg, pid=PID, level="I"):
        nonlocal n
        n += 1
        lines.append(logcat_line(n * 7, pid, tag, msg, level))
    add("D1MIX", f"session_start sid={sid} attempt={manifest['attempt']} block={manifest['block']} policy={manifest['policy']} manifest_sha256=x time_scale=1")
    add("litert", "[enn_manager.cc:124] SetGenAiPerfConfigFromSoc: SOC=s5e9965, mode=7" if variant != "no_enn" else "[enn_manager.cc:124] something else")
    add("D1OTHER", "Replacing 31 out of 31 node(s) with delegate (LITERT_CL) node, yielding 1 partitions", pid=999)  # other process: ignored
    for e in events:
        k = e.get("kind")
        if k == "runtime_submit":
            key = e["key"]
            lane = key.rsplit("_", 1)[1]
            add("D1MIX", f"runtime create_start key={key} backend={lane} model=m")
            if lane == "CPU":
                add("tflite", "Replacing 253 out of 253 node(s) with delegate (TfLiteXNNPackDelegate) node, yielding 1 partitions")
                add("tflite", "Created TensorFlow Lite XNNPACK delegate for CPU.")
            elif lane == "GPU":
                add("litert", "[gpu_environment.h:155] Created LiteRT GpuEnvironment.")
                add("tflite", "Replacing 253 out of 253 node(s) with delegate (LITERT_CL) node, yielding 1 partitions" if variant != "gpu_partial"
                    else "Replacing 250 out of 253 node(s) with delegate (LITERT_CL) node, yielding 2 partitions")
                if variant == "gpu_other_delegate":
                    add("tflite", "Replacing 3 out of 3 node(s) with delegate (TfLiteXNNPackDelegate) node, yielding 1 partitions")
            elif lane == "NPU":
                add("tflite", "Replacing 1 out of 1 node(s) with delegate (DispatchDelegate) node, yielding 1 partitions" if variant != "npu_zero"
                    else "Replacing 0 out of 1 node(s) with delegate (DispatchDelegate) node, yielding 1 partitions")
                if variant == "npu_failure":
                    add("litert", "[dispatch_delegate.cc:131] Failed to create a dispatch delegate kernel: No usable Dispatch runtime found", level="E")
        elif k == "runtime_return":
            add("D1MIX", f"runtime create_end key={e['key']} ok")
        elif k == "runtime_create_failed":
            add("D1MIX", f"runtime create_end key={e['key']} error=Fake")
        elif k == "warmup_submit":
            add("D1MIX", f"warmup_start key={e['key']} index={e['index']}")
        elif k == "warmup_return":
            add("D1MIX", f"warmup_end key={e['key']} index={e['index']} ok")
        elif k == "common_start":
            add("D1MIX", f"common_start origin_ns={e['scheduled_origin_ns']}")
        elif k == "common_end":
            add("D1MIX", f"common_end end_ns={e['common_end_ns']}")
        elif k == "phase_end" and e.get("phase") == "post_window_drain":
            add("D1MIX", "drain_end")
        elif k == "app_cleanup":
            add("D1MIX", "session_end status=x")
    return "\n".join(lines) + "\n"


def run_validate(case_dir: Path, device: Path, logcat_text: str, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "host").mkdir(exist_ok=True)
    log = out_dir / "host" / "logcat_threadtime.txt"
    log.write_text(logcat_text, encoding="utf-8")
    validated, contract = V.validate(out_dir, device, log, None, None, True)
    C.write_json(out_dir / "validated.json", validated)
    if contract is not None:
        C.write_json(out_dir / "npu_contract.json", contract)
    return validated, contract


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--roundtrip", type=Path, default=REPO / "request-runner" / "build" / "mixreq-roundtrip")
    ap.add_argument("--plan", type=Path, default=REPO / "s26" / "results" / "mixreq_1008" / "plan_v1" / "plan.json")
    ap.add_argument("--out", type=Path, default=REPO / "request-runner" / "build" / "mixreq-e2e")
    args = ap.parse_args()
    if args.out.exists():
        shutil.rmtree(args.out)
    results = args.out / "results"
    results.mkdir(parents=True)
    failures: list[str] = []
    expect = {"blockA_cpu": True, "blockA_par": True, "blockN_cpu": True, "blockN_parnpu": True, "blockN_npu_create_fails": False, "blockA_plugged": False}
    report = {}
    for case, want in expect.items():
        device = args.roundtrip / case / "a1"
        if not (device / "manifest.json").is_file():
            failures.append(f"{case}: round-trip artifacts missing ({device}) — run gradlew :request-runner:testDebugUnitTest first")
            continue
        validated, contract = run_validate(args.roundtrip / case, device, synthetic_logcat(device), results / case)
        report[case] = dict(eligible=validated["eligible"], reasons=validated["reasons"], npu_contract=None if contract is None else contract.get("passed"))
        if validated["eligible"] != want:
            failures.append(f"{case}: eligible={validated['eligible']} expected {want} reasons={validated['reasons']}")
        if case.startswith("blockN") and want and (contract is None or contract.get("passed") is not True):
            failures.append(f"{case}: NPU contract expected PASS got {contract}")
        if case == "blockN_npu_create_fails" and "4_assignment_residents" not in validated["reasons"]:
            failures.append(f"{case}: rule 4 should fail (NPU runtime missing): {validated['reasons']}")
        if case == "blockA_plugged" and "9_watch_stop" not in validated["reasons"]:
            failures.append(f"{case}: rule 9 should record the in-app stop: {validated['reasons']}")
    # negative evidence variants on the good PAR / PAR-NPU sessions (rule 7 must FAIL, nothing else changes)
    neg = {"blockA_par": ["gpu_partial", "gpu_other_delegate"], "blockN_parnpu": ["no_enn", "npu_zero", "npu_failure"]}
    for case, variants in neg.items():
        device = args.roundtrip / case / "a1"
        if not (device / "manifest.json").is_file():
            continue
        for variant in variants:
            validated, _ = run_validate(args.roundtrip / case, device, synthetic_logcat(device, variant), args.out / "negative" / f"{case}_{variant}")
            report[f"{case}:{variant}"] = dict(eligible=validated["eligible"], reasons=validated["reasons"])
            if validated["eligible"] or validated["reasons"] != ["7_delegation_evidence"]:
                failures.append(f"{case}:{variant}: expected only rule 7 to fail, got eligible={validated['eligible']} reasons={validated['reasons']}")
    # readout over the positive cases
    readout_dir = args.out / "readout"
    cmd = [sys.executable, "-X", "utf8", str(HERE / "mixreq_readout.py"), "--plan", str(args.plan), "--results", str(results), "--out", str(readout_dir), "--selftest"]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    report["readout_stdout"] = r.stdout.strip()[-800:]
    if r.returncode != 0:
        failures.append(f"readout rc={r.returncode}: {r.stderr.strip()[-800:]}")
    else:
        ro = C.read_json(readout_dir / "readout.json")
        for b in ("A", "N"):
            if ro["blocks"][b].get("judgment") != "쌍 부족 — 기술만":
                failures.append(f"block {b} judgment {ro['blocks'][b].get('judgment')!r} != '쌍 부족 — 기술만' (1 pair each)")
            if ro["blocks"][b]["n"] != 1:
                failures.append(f"block {b} pairs {ro['blocks'][b]['n']} != 1")
        if any(s.get("a24_service_cross_check") != "match" for s in ro["per_session"] if s.get("eligible")):
            failures.append("A24 service formula cross-check did not report match for an eligible session")
        inv = (readout_dir / "inventory.csv").read_text(encoding="utf-8").splitlines()
        if len(inv) < 1 + 16:
            failures.append(f"inventory rows {len(inv) - 1} < 16 (planned sessions must all appear)")
        attempted = len({c for c in expect if (args.roundtrip / c / "a1" / "manifest.json").is_file()})
        if sum(1 for l in inv if ",not_attempted," in l) != 16 - attempted:
            failures.append(f"inventory not_attempted count != {16 - attempted}")
    C.write_json(args.out / "e2e_report.json", dict(report=report, failures=failures))
    print(json.dumps(dict(cases=report, failures=failures), ensure_ascii=False, indent=1)[:6000])
    print("E2E", "PASS" if not failures else f"FAIL ({len(failures)})")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
