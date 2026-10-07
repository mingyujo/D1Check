"""V3 v2 (P1h 1-2) copy of dryrun_table_v3.py — changed only: PRED = d1sim/out/v3_prediction_v2.json and CHAINS = base v2 + ours v1.
Original docstring: V3 (P1g 1-3): orchestrator --dry-run for the 4 V3 chains with a fake serial (0.0.0.0:0), seed 20261005, output dir in the
scratchpad (--dry-run writes no manifest). Copy of night_1005e/dryrun_table_1005e.py — only the cell table and timeouts changed.
Arguments = 1-3 '기한 인자': --duration = Σ · --npu-max-inference-spans = predicted n (d1sim/out/v3_prediction_1006.json, max over
models · columns, incl. d1 estimate) × 1.3 rounded up to 100,000 · --runner-timeout-seconds = Σ + 1800 · --logger-exit-timeout-seconds 1800 ·
--analyze-timeout-seconds 600 · --cooling-min-seconds 600 · the rest = 명령 틀 (밤1005e_체인기록.md §2).
usage: py -X utf8 dryrun_table_v3.py <scratch_out_dir> [<serial>]
"""
import json, subprocess, sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\Users\rhoyo\AndroidStudioProjects\D1Check_v4")

COMMON = ("--logger-keep-files-open --mode pilot --resources NPU --warmup 20 --repeat 1 --seed 20261005 "
          "--accuracy-preflight off --start-policy stable --cooling-policy stable --stability-timeout-seconds 1800 "
          "--cooling-timeout-seconds 3600 --emergency-check-interval-seconds 10 --emergency-max-android-thermal-status 3")
PRED = ROOT / "d1sim" / "out" / "v3_prediction_v2.json"
CHAINS = ["v3_A_base_v2", "v3_A_ours_v1", "v3_B_base_v2", "v3_B_ours_v1"]


def cells():
    pr = json.loads(PRED.read_text(encoding="utf-8"))
    out = []
    for c in CHAINS:
        sig = pr["chains"][c]["sigma_s"]
        spans = pr["span_ceiling"][c]["ceiling"]
        tmo = f"--runner-timeout-seconds {sig + 1800} --logger-exit-timeout-seconds 1800 --analyze-timeout-seconds 600 --cooling-min-seconds 600"
        out.append((c, c, sig, spans, tmo))
    return out


def args_for(chain, dur, spans, timeouts):
    return f"--npu-chain tools\\chains\\{chain}.json --duration {dur} --npu-max-inference-spans {spans} {timeouts} {COMMON}"


if __name__ == "__main__":
    scratch = Path(sys.argv[1])
    serial = sys.argv[2] if len(sys.argv) > 2 else "0.0.0.0:0"
    for cell, chain, dur, spans, tmo in cells():
        a = ["py", "-X", "utf8", "tools\\d1_experiment_orchestrator.py", "--serial", serial] + args_for(chain, dur, spans, tmo).split() + [
            "--output-dir", str(scratch / f"S26_{cell}_dry"), "--dry-run"]
        p = subprocess.run(a, cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
        (scratch / f"dryrun_{cell}.txt").write_text(p.stdout.replace(serial, "<SERIAL>"), encoding="utf-8")
        row = {"cell": cell, "exit": p.returncode, "stderr_bytes": len(p.stderr), "args": args_for(chain, dur, spans, tmo)}
        try:
            j = json.loads(p.stdout[p.stdout.index("{"):])
            m = j.get("manifest", j)
            cfg = m["config"]
            npu = cfg["npu"]
            ch = npu.get("chain", {})
            row.update({
                "duration_s": cfg.get("duration_s"),
                "chain_id": ch.get("chain_id"), "total": ch.get("total_duration_s"), "sha256": ch.get("sha256"),
                "file_sha256": ch.get("source_file_sha256"),
                "max_spans": npu.get("max_inference_spans"),
                "segment_models": ch.get("segment_models"),
            })
        except Exception as e:  # noqa
            row["parse_error"] = repr(e)[:300]
            row["stderr_head"] = p.stderr[:600].replace(serial, "<SERIAL>")
        print(json.dumps(row, ensure_ascii=False))
