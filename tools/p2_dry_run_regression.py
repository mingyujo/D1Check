"""P2 step 0 / step 5: capture orchestrator dry-run payloads for byte comparison.

Usage (from the D1Check_v4 repo root):
    py -3 <this> capture <out_dir>
    py -3 <this> compare <baseline_dir> <candidate_dir>

Two capture paths:
  legacy_*  : the 2026-09-26 dry.py method (dry_run_payload() + json.dumps sort_keys),
              comparable with that session's dry_before/ files.
  cli_*     : the real CLI (`py -3 tools/d1_experiment_orchestrator.py ... --dry-run`),
              stdout bytes exactly as the operator sees them (validate_cli included).
Nothing here touches a device: --dry-run never calls adb and never writes a manifest.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

REPO = Path.cwd()
ORCH = REPO / "tools" / "d1_experiment_orchestrator.py"
TSET = r"C:\datasets\d1-imagenette-val40.d1tset"
SER = "<IP:PORT>"
OUT = r"C:\Users\rhoyo\AndroidStudioProjects\D1Check_v4\results\P2_DRYRUN_PLACEHOLDER"

LEGACY = {
    "cpu_gpu_formal": ["--mode", "formal", "--seed", "20260910", "--duty-cycles", "25", "50", "75", "100",
                       "--duration", "60", "--warmup", "20", "--repeat", "5", "--dry-run"],
    "npu_formal": ["--resources", "NPU", "--mode", "formal", "--seed", "20260910", "--duty-cycles", "25", "50",
                   "75", "100", "--duration", "60", "--warmup", "20", "--repeat", "5", "--dry-run"],
    "mixed_pilot": ["--resources", "CPU", "GPU", "NPU", "--mode", "pilot", "--seed", "7", "--duration", "60",
                    "--dry-run"],
}

FORMAL_COMMON = ["--duty-cycles", "25", "50", "75", "100", "--duration", "60", "--warmup", "20", "--repeat", "5",
                 "--seed", "20260910", "--accuracy-preflight", "required",
                 "--accuracy-validation-scope", "backend-performance-formal",
                 "--representative-tensor-set", TSET, "--gpu-profile", "gpu-fp32-strict-v1",
                 "--accuracy-input-count", "32", "--accuracy-seed", "305419896", "--accuracy-atol", "0.0001",
                 "--accuracy-rtol", "0.001", "--start-policy", "stable", "--cooling-policy", "stable"]

CLI = {
    # s26\tools\s26_formal.bat (9/14 CPU/GPU formal 80 slots)
    "cli_formal80_cpu_gpu": ["--serial", SER, "--mode", "formal", "--resources", "CPU", "GPU",
                             "--cpu-thread-levels", "1", "2", "4", *FORMAL_COMMON, "--output-dir", OUT],
    # CLAUDE.md §4: the 9/25 NPU formal 20-run command
    "cli_formal20_npu": ["--serial", SER, "--mode", "formal", "--resources", "NPU", *FORMAL_COMMON,
                         "--output-dir", OUT],
    # 0928 C2 (EfficientNet NPU formal)
    "cli_formal20_npu_c2_efficientnet": [
        "--serial", SER, "--mode", "formal", "--resources", "NPU",
        "--npu-model-asset", "models/efficientnet_lite0_Samsung_E9965.tflite",
        "--npu-timed-input-spec", "lcg-rgb-127-128", "--npu-input-spec", "lcg-rgb-127-128",
        "--npu-reference-path", "/data/local/tmp/efficientnet_lite0.tflite", *FORMAL_COMMON,
        "--stability-timeout-seconds", "1800", "--cooling-timeout-seconds", "1800",
        "--emergency-check-interval-seconds", "10", "--emergency-max-android-thermal-status", "3",
        "--output-dir", OUT],
    # 0926 procedure C4 (NPU run-only formal)
    "cli_formal_npu_c4_runonly": ["--serial", SER, "--mode", "formal", "--resources", "NPU",
                                  "--npu-run-only-span", "--duty-cycles", "100", "--duration", "60",
                                  "--warmup", "20", "--repeat", "5", "--seed", "20260910",
                                  "--accuracy-preflight", "required",
                                  "--accuracy-validation-scope", "backend-performance-formal",
                                  "--representative-tensor-set", TSET, "--gpu-profile", "gpu-fp32-strict-v1",
                                  "--accuracy-input-count", "32", "--accuracy-seed", "305419896",
                                  "--accuracy-atol", "0.0001", "--accuracy-rtol", "0.001",
                                  "--start-policy", "stable", "--cooling-policy", "stable", "--output-dir", OUT],
    # 0928 night pilots (exact flags from that session's cmd_*.txt)
    "cli_pilot_c1a_gpu1300": ["--serial", SER, "--mode", "pilot", "--resources", "GPU",
                              "--gpu-profile", "gpu-fp32-strict-v1", "--accuracy-preflight", "off",
                              "--duty-cycles", "100", "--duration", "1300", "--warmup", "20", "--repeat", "1",
                              "--seed", "20260928", "--start-policy", "stable", "--cooling-policy", "stable",
                              "--stability-timeout-seconds", "2400", "--cooling-timeout-seconds", "3600",
                              "--cooling-min-seconds", "600", "--emergency-check-interval-seconds", "10",
                              "--emergency-max-android-thermal-status", "3", "--output-dir", OUT],
    "cli_pilot_n165_npu": ["--serial", SER, "--mode", "pilot", "--resources", "NPU", "--npu-run-only-span",
                           "--duty-cycles", "100", "--duration", "165", "--warmup", "20", "--repeat", "1",
                           "--seed", "20260910", "--accuracy-preflight", "off",
                           "--accuracy-validation-scope", "backend-performance-formal",
                           "--representative-tensor-set", TSET, "--gpu-profile", "gpu-fp32-strict-v1",
                           "--accuracy-input-count", "32", "--accuracy-seed", "305419896",
                           "--accuracy-atol", "0.0001", "--accuracy-rtol", "0.001",
                           "--start-policy", "stable", "--cooling-policy", "stable",
                           "--stability-timeout-seconds", "1800", "--cooling-timeout-seconds", "1800",
                           "--cooling-min-seconds", "450", "--emergency-check-interval-seconds", "10",
                           "--emergency-max-android-thermal-status", "3", "--output-dir", OUT],
    "cli_pilot_c600_cpu4": ["--serial", SER, "--mode", "pilot", "--resources", "CPU", "--cpu-thread-levels", "4",
                            "--accuracy-preflight", "off", "--duty-cycles", "100", "--duration", "600",
                            "--warmup", "20", "--repeat", "1", "--seed", "20260928", "--start-policy", "stable",
                            "--cooling-policy", "stable", "--stability-timeout-seconds", "1800",
                            "--cooling-timeout-seconds", "2400", "--cooling-min-seconds", "450",
                            "--emergency-check-interval-seconds", "10",
                            "--emergency-max-android-thermal-status", "3", "--output-dir", OUT],
    "cli_pilot_m3_gpud50": ["--serial", SER, "--mode", "pilot", "--resources", "GPU",
                            "--gpu-profile", "gpu-fp32-strict-v1", "--accuracy-preflight", "off",
                            "--duty-cycles", "50", "--duration", "600", "--warmup", "20", "--repeat", "1",
                            "--seed", "20260928", "--start-policy", "stable", "--cooling-policy", "stable",
                            "--stability-timeout-seconds", "1800", "--cooling-timeout-seconds", "2400",
                            "--cooling-min-seconds", "240", "--emergency-check-interval-seconds", "10",
                            "--emergency-max-android-thermal-status", "3", "--output-dir", OUT],
    # 0926 procedure pilots
    "cli_pilot_c5_npu_cpu_compiled": ["--serial", SER, "--mode", "pilot", "--resources", "NPU",
                                      "--npu-accelerator", "CPU",
                                      "--npu-model-asset", "models/mobilenet_v1_1.0_224.tflite",
                                      "--npu-run-only-span", "--accuracy-preflight", "off",
                                      "--duty-cycles", "25", "50", "75", "100", "--duration", "60",
                                      "--warmup", "20", "--repeat", "5", "--seed", "20260910",
                                      "--start-policy", "stable", "--cooling-policy", "stable",
                                      "--output-dir", OUT],
    "cli_pilot_c6_npu_diag": ["--serial", SER, "--mode", "pilot", "--resources", "NPU", "--duty-cycles", "100",
                              "--duration", "60", "--warmup", "20", "--repeat", "1", "--seed", "20260926",
                              "--npu-diagnostic-logcat", "--start-policy", "stable", "--cooling-policy", "stable",
                              "--output-dir", OUT],
    "cli_pilot_c9_gpu_strict": ["--serial", SER, "--mode", "pilot", "--resources", "GPU",
                                "--gpu-profile", "gpu-fp32-strict-v1", "--accuracy-preflight", "optional",
                                "--duty-cycles", "100", "--duration", "60", "--warmup", "20", "--repeat", "3",
                                "--seed", "20260926", "--start-policy", "stable", "--cooling-policy", "stable",
                                "--output-dir", OUT],
    "cli_pilot_c9_gpu_compat": ["--serial", SER, "--mode", "pilot", "--resources", "GPU",
                                "--gpu-profile", "gpu-compat-default-v1", "--accuracy-preflight", "optional",
                                "--duty-cycles", "100", "--duration", "60", "--warmup", "20", "--repeat", "3",
                                "--seed", "20260926", "--start-policy", "stable", "--cooling-policy", "stable",
                                "--output-dir", OUT],
    # 9/25 NPU pilot duty 4 and a mixed-resource pilot
    "cli_pilot_npu_duty4": ["--serial", SER, "--mode", "pilot", "--resources", "NPU", "--duty-cycles", "25", "50",
                            "75", "100", "--duration", "60", "--start-policy", "stable", "--cooling-policy",
                            "stable", "--output-dir", OUT],
    "cli_pilot_mixed_cpu_gpu_npu": ["--resources", "CPU", "GPU", "NPU", "--mode", "pilot", "--seed", "7",
                                    "--duration", "60"],
    # bare defaults (CPU GPU pilot, 600 s)
    "cli_pilot_defaults": [],
}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def capture(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=False)
    spec = importlib.util.spec_from_file_location("orch", ORCH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["orch"] = module
    spec.loader.exec_module(module)
    rows = []
    for name, argv in LEGACY.items():
        args = module.build_parser().parse_args(argv)
        text = json.dumps(module.dry_run_payload(args), sort_keys=True, ensure_ascii=False, default=str)
        data = text.encode("utf-8")
        (out / f"legacy_{name}.json").write_bytes(data)
        rows.append((f"legacy_{name}.json", sha(data), len(data), "-"))
    for name, argv in CLI.items():
        proc = subprocess.run([sys.executable, str(ORCH), *argv, "--dry-run"], cwd=REPO,
                              capture_output=True)
        if proc.returncode != 0:
            raise SystemExit(f"{name}: rc={proc.returncode}\n{proc.stderr.decode('utf-8', 'replace')}")
        (out / f"{name}.json").write_bytes(proc.stdout)
        slots = len(json.loads(proc.stdout.decode("utf-8"))["commands"])
        rows.append((f"{name}.json", sha(proc.stdout), len(proc.stdout), str(slots)))
    lines = [f"{digest}  {fname}  bytes={size}  slots={slots}" for fname, digest, size, slots in rows]
    (out / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


def compare(base: Path, cand: Path) -> int:
    names = sorted(p.name for p in base.glob("*.json"))
    other = sorted(p.name for p in cand.glob("*.json"))
    failures = 0
    if names != other:
        print(f"FILE SET DIFFERS: only-base={sorted(set(names) - set(other))} only-cand={sorted(set(other) - set(names))}")
        failures += 1
    for name in names:
        if name not in other:
            continue
        a, b = (base / name).read_bytes(), (cand / name).read_bytes()
        same = a == b
        failures += 0 if same else 1
        print(f"{'IDENTICAL' if same else 'DIFFERENT'}  {name}  {sha(a)[:16]}  {sha(b)[:16]}  {len(a)}  {len(b)}")
    print(f"RESULT: {'PASS' if failures == 0 else 'FAIL'} - {len(names)} files, {failures} differences")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    if sys.argv[1] == "capture":
        capture(Path(sys.argv[2]))
    elif sys.argv[1] == "compare":
        raise SystemExit(compare(Path(sys.argv[2]), Path(sys.argv[3])))
    else:
        raise SystemExit(__doc__)
