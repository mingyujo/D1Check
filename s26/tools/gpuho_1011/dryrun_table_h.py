"""GPU holdout (GH 1011, 3단계-3) copy of energy_1008/dryrun_table_c.py — changed only: the cell table (GAh · GBh · smoke G) with the
'기한 인자' rows of 밤1005e_체인기록.md §2 (GAe · GBe row for GAh · GBh · 스모크 G row for smoke) — no prediction file.
orchestrator --dry-run with a fake serial (0.0.0.0:0), seed 20261005, output dir in the scratchpad (--dry-run writes no manifest).
usage: py -X utf8 dryrun_table_h.py <scratch_out_dir> [<serial>]
"""
import json, subprocess, sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\Users\rhoyo\AndroidStudioProjects\D1Check_v4")

COMMON = ("--logger-keep-files-open --mode pilot --resources NPU --warmup 20 --repeat 1 --seed 20261005 "
          "--accuracy-preflight off --start-policy stable --cooling-policy stable --stability-timeout-seconds 1800 "
          "--cooling-timeout-seconds 3600 --emergency-check-interval-seconds 10 --emergency-max-android-thermal-status 3")
T900 = "--runner-timeout-seconds 2700 --logger-exit-timeout-seconds 1800 --analyze-timeout-seconds 600 --cooling-min-seconds 600"
T60 = "--runner-timeout-seconds 900 --logger-exit-timeout-seconds 600 --analyze-timeout-seconds 300 --cooling-min-seconds 60"
CELLS = [("GAh", "gpu_eff_work100_v1", 900, 400000, T900),
         ("GBh", "gpu_eff_work50eq_v1", 900, 400000, T900),
         ("smokeG", "smoke_gpu_eff_v1", 60, 50000, T60)]


def args_for(chain, dur, spans, timeouts):
    return f"--npu-chain tools\\chains\\{chain}.json --duration {dur} --npu-max-inference-spans {spans} {timeouts} {COMMON}"


if __name__ == "__main__":
    scratch = Path(sys.argv[1])
    scratch.mkdir(parents=True, exist_ok=True)
    serial = sys.argv[2] if len(sys.argv) > 2 else "0.0.0.0:0"
    for cell, chain, dur, spans, tmo in CELLS:
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
