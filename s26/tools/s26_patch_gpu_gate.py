#!/usr/bin/env python3
"""Apply (or revert) the S26 GPU compatibility-gate patch.

Why this exists
---------------
LiteRT 1.4.2 ships a binary device allow list ("compatibility list") that was
built before the Exynos 2600 existed. On the Galaxy S26 it answers "not
supported", and the runner treated that as fatal:

    check(CompatibilityList().isDelegateSupportedOnThisDevice) { ... }

so every GPU run died in the setup phase before GpuDelegate() was ever
constructed. The device does expose libOpenCL.so and libOpenCL_samsung.so, so
the list's verdict is a stale heuristic, not a hardware fact.

This patch records the list verdict in the run metadata and lets the delegate
constructor be the real test. Actual GPU execution is still proven downstream
by delegate_evidence (logcat proof of TfLiteGpuDelegateV2, kernel count and
replaced-node count) and by the CPU/GPU output equivalence preflight.

Devices that ARE in the list (Galaxy A24 / Mali-G57) answer true, so their
behaviour is unchanged; only one metadata field is added.

Usage
-----
    python s26_patch_gpu_gate.py            apply
    python s26_patch_gpu_gate.py --revert   undo
    python s26_patch_gpu_gate.py --check    report status only

Every edit must match exactly once. If any does not, nothing is written.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[2]
PKG = REPO / "benchmark-runner/src/main/java/com/example/d1check/benchmarkrunner"
ENGINE = PKG / "GpuBenchmarkEngine.kt"
PREFLIGHT = PKG / "AccuracyPreflightEngine.kt"
POLICY = PKG / "s26/GpuCompatibilityPolicy.kt"

POLICY_SOURCE = '''package com.example.d1check.benchmarkrunner.s26

import android.util.Log
import org.tensorflow.lite.gpu.CompatibilityList

/**
 * S26 measurement policy for the LiteRT GPU device compatibility list.
 *
 * LiteRT 1.4.2 embeds a binary allow list of GPU-capable devices that predates
 * the Exynos 2600, so on the Galaxy S26 it reports "not supported" even though
 * the device exposes libOpenCL.so and libOpenCL_samsung.so. The list is a
 * heuristic for app developers, not a statement of hardware capability.
 *
 * The original runner treated a negative verdict as fatal, which made every GPU
 * run fail in the setup phase before GpuDelegate() was constructed. This policy
 * records the verdict instead and lets the delegate constructor decide.
 *
 * Actual GPU execution remains verified downstream by delegate_evidence
 * (TfLiteGpuDelegateV2 creation, kernel count, replaced-node count in logcat)
 * and by the CPU/GPU output equivalence preflight. Those checks are stronger
 * than the allow list, not weaker.
 *
 * On devices present in the list (e.g. Galaxy A24 / Mali-G57) the verdict is
 * true and behaviour is identical to before; only metadata is added.
 */
internal object GpuCompatibilityPolicy {

    const val TAG = "D1GPUCOMPAT"
    const val POLICY_ID = "s26-compat-list-advisory-v1"

    data class Verdict(
        val listSupported: Boolean?,
        val queryError: String?,
    ) {
        fun metadata(): Map<String, Any?> = linkedMapOf(
            "gpu_compatibility_policy_id" to POLICY_ID,
            "gpu_compatibility_list_supported" to listSupported,
            "gpu_compatibility_list_query_error" to queryError,
            "gpu_compatibility_list_enforced" to false,
        )
    }

    fun notEvaluatedMetadata(): Map<String, Any?> = linkedMapOf(
        "gpu_compatibility_policy_id" to POLICY_ID,
        "gpu_compatibility_list_supported" to null,
        "gpu_compatibility_list_query_error" to null,
        "gpu_compatibility_list_enforced" to false,
    )

    fun evaluate(): Verdict {
        val verdict = try {
            val list = CompatibilityList()
            Verdict(list.isDelegateSupportedOnThisDevice, null)
        } catch (error: Throwable) {
            Verdict(null, "${error.javaClass.simpleName}: ${error.message ?: ""}")
        }
        Log.i(
            TAG,
            "policy=" + POLICY_ID +
                " list_supported=" + verdict.listSupported +
                " query_error=" + verdict.queryError +
                " enforced=false",
        )
        return verdict
    }
}
'''

EDITS = [
    (
        ENGINE, "import",
        "import org.tensorflow.lite.gpu.CompatibilityList\n"
        "import org.tensorflow.lite.gpu.GpuDelegate\n",

        "import org.tensorflow.lite.gpu.GpuDelegate\n"
        "import com.example.d1check.benchmarkrunner.s26.GpuCompatibilityPolicy\n",
    ),
    (
        ENGINE, "verdict variable",
        "        var pilotSafety: PilotSafetyCheck? = null\n",

        "        var pilotSafety: PilotSafetyCheck? = null\n"
        "        var gpuCompatibility: GpuCompatibilityPolicy.Verdict? = null\n",
    ),
    (
        ENGINE, "delegate gate",
        "                        val compatibility = CompatibilityList()\n"
        "                        check(compatibility.isDelegateSupportedOnThisDevice) {\n"
        '                            "GPU delegate is not supported; GPU experiment cannot start"\n'
        "                        }\n",

        "                        // S26: LiteRT 1.4.2's compatibility list predates this SoC.\n"
        "                        // Record its verdict; let GpuDelegate() be the real test.\n"
        "                        gpuCompatibility = GpuCompatibilityPolicy.evaluate()\n",
    ),
    (
        ENGINE, "metadata",
        "        outputConfig.putAll(\n"
        "            pilotSafety?.metadata() ?: mapOf(\n",

        "        outputConfig.putAll(\n"
        "            gpuCompatibility?.metadata()\n"
        "                ?: GpuCompatibilityPolicy.notEvaluatedMetadata()\n"
        "        )\n"
        "        outputConfig.putAll(\n"
        "            pilotSafety?.metadata() ?: mapOf(\n",
    ),
    (
        PREFLIGHT, "import",
        "import org.tensorflow.lite.gpu.CompatibilityList\n"
        "import org.tensorflow.lite.gpu.GpuDelegate\n",

        "import org.tensorflow.lite.gpu.GpuDelegate\n"
        "import com.example.d1check.benchmarkrunner.s26.GpuCompatibilityPolicy\n",
    ),
    (
        PREFLIGHT, "preflight gate",
        "        val compatibility = CompatibilityList()\n"
        "        check(compatibility.isDelegateSupportedOnThisDevice) {\n"
        '            "GPU delegate is not supported; output equivalence preflight cannot run"\n'
        "        }\n",

        "        // S26: record the compatibility-list verdict instead of aborting on it.\n"
        "        GpuCompatibilityPolicy.evaluate()\n",
    ),
]


def read(path: Path) -> tuple[str, str]:
    """Return (text with LF endings, the original newline sequence)."""
    raw = path.read_bytes()
    newline = "\r\n" if b"\r\n" in raw else "\n"
    return raw.replace(b"\r\n", b"\n").decode("utf-8"), newline


def write(path: Path, text: str, newline: str) -> None:
    data = text.encode("utf-8")
    if newline == "\r\n":
        data = data.replace(b"\n", b"\r\n")
    path.write_bytes(data)


def status() -> str:
    if not ENGINE.exists():
        return "missing"
    text, _ = read(ENGINE)
    applied = "GpuCompatibilityPolicy.evaluate()" in text
    original = "check(compatibility.isDelegateSupportedOnThisDevice)" in text
    if applied and not original:
        return "applied"
    if original and not applied:
        return "original"
    return "mixed"


def run(revert: bool) -> int:
    for path in (ENGINE, PREFLIGHT):
        if not path.exists():
            print(f"[X] not found: {path}")
            print("    Run this from s26/tools inside the D1Check_v4 clone.")
            return 1

    # ---- dry pass: every edit must match exactly once before anything is written
    staged: dict[Path, tuple[str, str]] = {}
    for path, label, before, after in EDITS:
        old, new = (after, before) if revert else (before, after)
        if path not in staged:
            staged[path] = read(path)
        text, newline = staged[path]
        count = text.count(old)
        if count != 1:
            print(f"[X] {path.name} :: {label} -> matched {count} times, expected 1")
            print("    Nothing was written. The file may already be in the target")
            print("    state, or it changed upstream. Run with --check first.")
            return 1
        staged[path] = (text.replace(old, new, 1), newline)

    # ---- commit
    for path, (text, newline) in staged.items():
        write(path, text, newline)
        print(f"[ok] patched {path.relative_to(REPO)}")

    if revert:
        if POLICY.exists():
            POLICY.unlink()
            print(f"[ok] removed  {POLICY.relative_to(REPO)}")
        try:
            POLICY.parent.rmdir()
        except OSError:
            pass
    else:
        POLICY.parent.mkdir(parents=True, exist_ok=True)
        write(POLICY, POLICY_SOURCE, "\r\n")
        print(f"[ok] created  {POLICY.relative_to(REPO)}")

    print()
    print("Reverted." if revert else "Applied. Now rebuild benchmark-runner in Android Studio.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--revert", action="store_true", help="undo the patch")
    parser.add_argument("--check", action="store_true", help="report status only")
    args = parser.parse_args()

    state = status()
    print(f"repo   : {REPO}")
    print(f"status : {state}")
    print()

    if args.check:
        return 0
    if state == "missing":
        print("[X] GpuBenchmarkEngine.kt not found. Wrong folder?")
        return 1
    if state == "applied" and not args.revert:
        print("Already applied. Nothing to do.")
        return 0
    if state == "original" and args.revert:
        print("Not applied. Nothing to revert.")
        return 0
    return run(args.revert)


if __name__ == "__main__":
    sys.exit(main())
