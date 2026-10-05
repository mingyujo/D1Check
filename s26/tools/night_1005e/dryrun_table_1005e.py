"""NIGHT 1005e (P1e 1-1): orchestrator --dry-run for the 8 new chains with a fake serial (0.0.0.0:0), seed 20261005,
output dir in the scratchpad (no manifest is written by --dry-run). Prints one table row per chain:
exit, config.duration_s, npu.chain (chain_id, total, sha256, source_file_sha256), npu.max_inference_spans, segment_models.
Arguments = prereg 밤1005e s1 '기한 인자' (N2 cells: 밤1005_체인기록 s2; NIe/GIe: 밤1004_체인기록 s2 values; smoke: s1).
usage: py -X utf8 dryrun_table_1005e.py <scratch_out_dir> [<serial>]
"""
import json, subprocess, sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\Users\rhoyo\AndroidStudioProjects\D1Check_v4")
scratch = Path(sys.argv[1])
serial = sys.argv[2] if len(sys.argv) > 2 else "0.0.0.0:0"

COMMON = ("--logger-keep-files-open --mode pilot --resources NPU --warmup 20 --repeat 1 --seed 20261005 "
          "--accuracy-preflight off --start-policy stable --cooling-policy stable --stability-timeout-seconds 1800 "
          "--cooling-timeout-seconds 3600 --emergency-check-interval-seconds 10 --emergency-max-android-thermal-status 3")
N2T = "--runner-timeout-seconds 2700 --logger-exit-timeout-seconds 1800 --analyze-timeout-seconds 600 --cooling-min-seconds 600"
SMT = "--cooling-min-seconds 60 --runner-timeout-seconds 900 --logger-exit-timeout-seconds 600 --analyze-timeout-seconds 300"
CELLS = [
    ("NAe", "npu_eff_work100_v1", 900, 1000000, N2T),
    ("NBe", "npu_eff_work50_v1", 900, 1000000, N2T),
    ("GAe", "gpu_eff_work100_v1", 900, 400000, N2T),
    ("GBe", "gpu_eff_work50_v1", 900, 400000, N2T),
    ("NIe", "npu_eff_idle300_v1", 840, 1200000, N2T),
    ("GIe", "gpu_eff_idle300_v1", 1260, 400000, N2T),
    ("smokeN", "smoke_npu_eff_v1", 60, 100000, SMT),
    ("smokeG", "smoke_gpu_eff_v1", 60, 50000, SMT),
]

def args_for(chain, dur, spans, timeouts):
    return f"--npu-chain tools\\chains\\{chain}.json --duration {dur} --npu-max-inference-spans {spans} {timeouts} {COMMON}"

if __name__ == "__main__":
    for cell, chain, dur, spans, tmo in CELLS:
        a = ["py", "-X", "utf8", "tools\\d1_experiment_orchestrator.py", "--serial", serial] + args_for(chain, dur, spans, tmo).split() + [
            "--output-dir", str(scratch / f"S26_{cell}_dry"), "--dry-run"]
        p = subprocess.run(a, cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
        (scratch / f"dryrun_{cell}.txt").write_text(p.stdout.replace(serial, "<SERIAL>"), encoding="utf-8")
        row = {"cell": cell, "exit": p.returncode, "stderr_bytes": len(p.stderr)}
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
