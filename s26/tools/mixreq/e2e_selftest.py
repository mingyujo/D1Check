"""End-to-end PC self-test: K6 round-trip artifacts (request-runner/build/mixreq-roundtrip) → synthetic logcat → mixreq_validate →
mixreq_readout, one command. Exit 0 only when every expectation holds.

  py -3 s26/tools/mixreq/e2e_selftest.py [--roundtrip request-runner/build/mixreq-roundtrip] [--plan s26/results/mixreq_1008/plan_v1/plan.json]
      [--out <dir, default build/mixreq-e2e>]

Expectations: blockA_cpu · blockA_par · blockN_cpu · blockN_parnpu → eligible (all 9 rules incl. evidence from the synthetic logcat);
blockN_npu_create_fails → ineligible (0_artifacts, 4_assignment); blockA_plugged → ineligible (0/8/9 stop_reason); NPU contract computed
for block N (PASS on the fake outputs); readout: block A = "쌍 부족 — 기술만" (1 pair), block N likewise; A24 formula cross-check = match;
negative evidence variants (no ENN line / 0 of 1 replacement / failure line / other delegate) → rule 7 FAIL.
v2 (R3): a PAR session with overlap 0 stays eligible under the v2 id and fails rule 5 under the v1 id; readout over {CPU, PAR-no-overlap}
→ block A "병행 겹침 없음 — 기술만"; --a24-compare FAIL → Q1 · Q3 · Q2 "이식 대조 FAIL — 기술만"; v2 Q2 title.
v3 (R4): K6 cases blockA_par_02C (-02C, 192) and blockN_parnpu_03 (-03, 3,000 · 720 s, time_scale 10) → eligible under their own
experiment ids (rule 3 window 72 s for -03); readout per v3 plan (plan_v3c / plan_v3s) → "쌍 부족 — 기술만" (one session each), the
(C) readout with a synthetic --reference-readout carries `confirmation` (differs → "확인 안 됨"), the (S) readout carries `sustained`
per session (degradation lanes present; 38 ℃ time None without hal.csv); a v2 session is skipped by a v3 plan (never mixed).
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


def serialise_par_rows(device: Path, out: Path) -> None:
    """Copy a PAR round-trip device folder and push every GPU row after the CPU lane went idle (overlap -> 0). Time order and the
    [35 s, 120 s) window are kept by shifting the rows into the tail of the common window (same mutation as test_rule5_overlap)."""
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(device, out)
    rows = C.read_json(out / "requests.json")
    m = C.read_json(out / "manifest.json")
    scale = int(m.get("time_scale", 1))
    origin = C.read_json(out / "common_boundary.json")["start_ns"]
    cpu_end = max(int(r["lane_available_ns"]) for r in rows if r["selected_backend"] == "CPU")
    t = max(cpu_end + 1, origin + int(100e9 / scale))
    hi = origin + int(C.COMMON_S * 1e9 / scale)
    keys = ("dispatch_ns", "execution_start_ns", "host_inference_start_ns", "host_inference_return_ns", "output_ready_ns", "persist_complete_ns",
            "worker_release_ns", "lane_available_ns")
    gpu_rows = sorted((r for r in rows if r["selected_backend"] == "GPU"), key=lambda r: int(r["dispatch_ns"]))
    for r in gpu_rows:
        shift = t - int(r["dispatch_ns"])
        for k in keys:
            r[k] = int(r[k]) + shift
        t = int(r["lane_available_ns"]) + 1
    if t >= hi:  # keep the window rule: squeeze if the tail would spill past 120 s (fake latencies are tiny, so this is defensive)
        raise RuntimeError("serialised GPU rows spill past the common window")
    C.write_json(out / "requests.json", rows)


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
    ap.add_argument("--plan", type=Path, default=REPO / "s26" / "results" / "mixreq_1008" / "plan_v2" / "plan.json")
    ap.add_argument("--out", type=Path, default=REPO / "request-runner" / "build" / "mixreq-e2e")
    ap.add_argument("--plan-v3c", type=Path, default=REPO / "s26" / "results" / "mixreq_1008" / "plan_v3c" / "plan.json")
    ap.add_argument("--plan-v3s", type=Path, default=REPO / "s26" / "results" / "mixreq_1008" / "plan_v3s" / "plan.json")
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
        if ro.get("registration_version") == 2 and ro["q2_table"]["title"] != "간격이 다른 이식 (S26 200 ms · A24 400 ms) — 나란히 기술만":
            failures.append(f"v2 Q2 title {ro['q2_table']['title']!r}")
    # v2 (등록 v2 #3 · #4): a PAR session whose two lanes never overlap is NOT invalid — it is eligible with overlap 0 and the readout tags
    # the block "병행 겹침 없음 — 기술만" (before "쌍 부족"). Built from blockA_par by serialising the GPU rows after the CPU lane (same trick
    # as test_rule5_overlap); under the v1 rule the same artifacts fail rule 5 (checked here too, so the v1 path stays frozen).
    par_device = args.roundtrip / "blockA_par" / "a1"
    cpu_device = args.roundtrip / "blockA_cpu" / "a1"
    if (par_device / "manifest.json").is_file() and (cpu_device / "manifest.json").is_file():
        v2_results = args.out / "v2_no_overlap" / "results"
        v2_results.mkdir(parents=True, exist_ok=True)
        no_ov = args.out / "v2_no_overlap" / "device_par_no_overlap"
        serialise_par_rows(par_device, no_ov)
        validated_v2, _ = run_validate(args.roundtrip / "blockA_par", no_ov, synthetic_logcat(no_ov), v2_results / "blockA_par_no_overlap")
        report["v2:blockA_par_no_overlap"] = dict(eligible=validated_v2["eligible"], reasons=validated_v2["reasons"],
                                                  overlap_s=validated_v2["rules"]["5_overlap"]["detail"]["overlap_s"])
        if C.registration_version(C.read_json(no_ov / "manifest.json")["experiment_id"]) != 2:
            failures.append("v2 no-overlap case: round-trip manifest is not a v2 experiment id (rebuild with gradlew :request-runner:testDebugUnitTest)")
        elif not validated_v2["eligible"] or validated_v2["rules"]["5_overlap"]["detail"]["overlap_s"] != 0:
            failures.append(f"v2 no-overlap PAR session must stay eligible with overlap 0: eligible={validated_v2['eligible']} reasons={validated_v2['reasons']}")
        # same artifacts, v1 id -> rule 5 fails (v1 path frozen)
        v1_dev = args.out / "v2_no_overlap" / "device_par_no_overlap_v1id"
        shutil.copytree(no_ov, v1_dev)
        m1 = C.read_json(v1_dev / "manifest.json")
        m1["experiment_id"] = C.V1_EXPERIMENT_ID
        (v1_dev / "manifest.json").write_bytes(C.canonical_json(m1))
        validated_v1, _ = V.validate(args.out / "v2_no_overlap", v1_dev, args.out / "v2_no_overlap" / "results" / "blockA_par_no_overlap" / "host" / "logcat_threadtime.txt", None, None, True)
        report["v1:blockA_par_no_overlap"] = dict(eligible=validated_v1["eligible"], reasons=validated_v1["reasons"])
        if validated_v1["eligible"] or "5_overlap" not in validated_v1["reasons"]:
            failures.append(f"v1 rule 5 must still fail a no-overlap PAR session: {validated_v1['reasons']}")
        # readout over {CPU, PAR-no-overlap}: block A tag "병행 겹침 없음 — 기술만"; with a FAIL a24 compare json -> "이식 대조 FAIL — 기술만"
        shutil.copytree(results / "blockA_cpu", v2_results / "blockA_cpu")
        v2_readout = args.out / "v2_no_overlap" / "readout"
        r2 = subprocess.run([sys.executable, "-X", "utf8", str(HERE / "mixreq_readout.py"), "--plan", str(args.plan), "--results", str(v2_results), "--out", str(v2_readout), "--selftest"],
                            capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r2.returncode != 0:
            failures.append(f"v2 readout rc={r2.returncode}: {r2.stderr.strip()[-600:]}")
        else:
            ro2 = C.read_json(v2_readout / "readout.json")
            report["v2:readout_block_A"] = dict(judgment=ro2["blocks"]["A"].get("judgment"), tags=ro2["blocks"]["A"].get("tags"), n=ro2["blocks"]["A"]["n"])
            if ro2["blocks"]["A"].get("judgment") != "병행 겹침 없음 — 기술만" or ro2["blocks"]["A"]["n"] != 1:
                failures.append(f"v2 block A judgment {ro2['blocks']['A'].get('judgment')!r} (n={ro2['blocks']['A']['n']}) != '병행 겹침 없음 — 기술만'")
        fail_json = args.out / "v2_no_overlap" / "a24_compare_fail.json"
        C.write_json(fail_json, dict(schema="s26-mixreq-a24-compare-v1", a24_detection="FAIL", classification="PASS", verdict="FAIL", note="synthetic e2e"))
        r3 = subprocess.run([sys.executable, "-X", "utf8", str(HERE / "mixreq_readout.py"), "--plan", str(args.plan), "--results", str(v2_results), "--out", str(args.out / "v2_no_overlap" / "readout_a24fail"),
                             "--selftest", "--a24-compare", str(fail_json)], capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r3.returncode != 0:
            failures.append(f"v2 readout (a24 FAIL) rc={r3.returncode}: {r3.stderr.strip()[-600:]}")
        else:
            ro3 = C.read_json(args.out / "v2_no_overlap" / "readout_a24fail" / "readout.json")
            report["v2:readout_a24_fail"] = dict(A=ro3["blocks"]["A"].get("judgment"), N=ro3["blocks"]["N"].get("judgment"), q2=ro3["q2_table"]["judgment"])
            if not (ro3["blocks"]["A"].get("judgment") == ro3["blocks"]["N"].get("judgment") == ro3["q2_table"]["judgment"] == "이식 대조 FAIL — 기술만"):
                failures.append(f"a24 compare FAIL must tag Q1 · Q3 · Q2: {report['v2:readout_a24_fail']}")
        if any(s.get("a24_service_cross_check") != "match" for s in ro["per_session"] if s.get("eligible")):
            failures.append("A24 service formula cross-check did not report match for an eligible session")
        inv = (readout_dir / "inventory.csv").read_text(encoding="utf-8").splitlines()
        if len(inv) < 1 + 16:
            failures.append(f"inventory rows {len(inv) - 1} < 16 (planned sessions must all appear)")
        attempted = len({c for c in expect if (args.roundtrip / c / "a1" / "manifest.json").is_file()})
        if sum(1 for l in inv if ",not_attempted," in l) != 16 - attempted:
            failures.append(f"inventory not_attempted count != {16 - attempted}")
    # ---------------------------------------------------------------------------------------------------- v3 (R4): -02C · -03
    for case, plan_path, exp_id, kind in (("blockA_par_02C", args.plan_v3c, "S26-MIXREQ-02C", "confirm"), ("blockN_parnpu_03", args.plan_v3s, "S26-MIXREQ-03", "sustained")):
        device = args.roundtrip / case / "a1"
        if not (device / "manifest.json").is_file():
            failures.append(f"{case}: round-trip artifacts missing ({device}) — run gradlew :request-runner:testDebugUnitTest first")
            continue
        if not plan_path.is_file():
            failures.append(f"{case}: plan {plan_path} missing — run mixreq_plan.py --experiment first")
            continue
        if C.read_json(device / "manifest.json")["experiment_id"] != exp_id:
            failures.append(f"{case}: round-trip manifest experiment_id != {exp_id}")
            continue
        v3_results = args.out / "v3" / case / "results"
        v3_results.mkdir(parents=True, exist_ok=True)
        validated, contract = run_validate(args.roundtrip / case, device, synthetic_logcat(device), v3_results / case)
        report[f"v3:{case}"] = dict(eligible=validated["eligible"], reasons=validated["reasons"], registration_version=validated["registration_version"],
                                   window=validated["rules"]["3_window"]["detail"]["bounds_s"], npu_contract=None if contract is None else contract.get("passed"))
        if not validated["eligible"] or validated["registration_version"] != 3:
            failures.append(f"v3 {case}: eligible={validated['eligible']} reasons={validated['reasons']} version={validated['registration_version']}")
        if kind == "sustained" and validated["rules"]["3_window"]["detail"]["bounds_s"] != [35.0 / 10, 720.0 / 10]:
            failures.append(f"v3 {case}: window bounds {validated['rules']['3_window']['detail']['bounds_s']} != [3.5, 72.0] (720 s / time_scale 10)")
        # a v2 session dropped into the v3 results must be skipped, never paired
        shutil.copytree(results / ("blockA_cpu" if kind == "confirm" else "blockN_cpu"), v3_results / "v2_session_should_be_skipped")
        ro_dir = args.out / "v3" / case / "readout"
        cmd3 = [sys.executable, "-X", "utf8", str(HERE / "mixreq_readout.py"), "--plan", str(plan_path), "--results", str(v3_results), "--out", str(ro_dir), "--selftest"]
        if kind == "confirm":
            ref = args.out / "v3" / case / "reference_readout.json"
            C.write_json(ref, dict(blocks={"A": dict(judgment="병행이 긴급 응답을 줄였다", urgent_judgment="병행이 긴급 응답을 줄였다", normal_judgment="엇갈림",
                                                      thermal_skin_judgment="열 차이 기준 안 (1.0 ℃)", thermal_ap_judgment="엇갈림", service_judgment="두 정책 모두 기한 충족", tags=[], n=4),
                                           "N": dict(judgment="NPU 병행이 긴급 응답을 줄였다", tags=[], n=4)}))
            cmd3 += ["--reference-readout", str(ref)]
        r3 = subprocess.run(cmd3, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r3.returncode != 0:
            failures.append(f"v3 {case} readout rc={r3.returncode}: {r3.stderr.strip()[-800:]}")
            continue
        ro3 = C.read_json(ro_dir / "readout.json")
        block = "A" if kind == "confirm" else "N"
        report[f"v3:{case}:readout"] = dict(judgment=ro3["blocks"][block].get("judgment"), skipped=ro3["skipped"], kind=ro3.get("experiment_kind"), sessions=ro3["sessions"])
        if ro3["sessions"] != 1 or not any("experiment_id" in s for s in ro3["skipped"]):
            failures.append(f"v3 {case}: readout must use 1 session and skip the v2 one (sessions={ro3['sessions']} skipped={ro3['skipped']})")
        if ro3["blocks"][block].get("judgment") != "쌍 부족 — 기술만" or ro3.get("registration_version") != 3 or ro3.get("experiment_kind") != kind:
            failures.append(f"v3 {case}: judgment {ro3['blocks'][block].get('judgment')!r} version {ro3.get('registration_version')} kind {ro3.get('experiment_kind')}")
        if kind == "confirm":
            conf = ro3.get("confirmation", {}).get("blocks", {})
            report[f"v3:{case}:confirmation"] = {b: v.get("verdict") for b, v in conf.items()}
            if conf.get("A", {}).get("verdict") != "확인 안 됨 — 개발 · 확인 판정 다름" or conf.get("N", {}).get("verdict") != "확인 안 됨 — 개발 · 확인 판정 다름":
                failures.append(f"v3 {case}: confirmation verdicts {report[f'v3:{case}:confirmation']} (1 session → 쌍 부족 ≠ development judgment)")
            if ro3.get("conclusion_suffix") != "(개발 R3 · 확인 R4 — 2블록, 순서 뒤집음, 재보정 없음)":
                failures.append(f"v3 {case}: conclusion suffix {ro3.get('conclusion_suffix')!r}")
        else:
            ps = [s for s in ro3["per_session"] if s.get("eligible")]
            sus = (ps[0].get("sustained") or {}) if ps else {}
            report[f"v3:{case}:sustained"] = dict(keys=sorted(sus), lanes=sorted(((sus.get("degradation") or {}).get("lanes") or {})))
            if not ps or "degradation" not in sus or "time_above_38" not in sus or "detection_CPU" not in ((sus.get("degradation") or {}).get("lanes") or {}):
                failures.append(f"v3 {case}: sustained fields missing: {report[f'v3:{case}:sustained']}")
            if "sustained_definitions" not in ro3 or "conclusion_template" not in ro3:
                failures.append(f"v3 {case}: sustained definitions / conclusion template missing")
            if ro3["blocks"]["N"].get("degradation_by_session") is None:
                failures.append(f"v3 {case}: degradation_by_session missing on block N")
    C.write_json(args.out / "e2e_report.json", dict(report=report, failures=failures))
    print(json.dumps(dict(cases=report, failures=failures), ensure_ascii=False, indent=1)[:6000])
    print("E2E", "PASS" if not failures else f"FAIL ({len(failures)})")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
