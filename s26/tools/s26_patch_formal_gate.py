#!/usr/bin/env python3
"""Generalise the formal GPU validity gate to cover validated devices.

What the gate does today
------------------------
tools/d1_logger_v4.py decides `formal_gpu_valid` from nine conditions. Eight of
them are evidence about the run. The ninth is a hardcoded device model:

    galaxy_a24 = capture_metadata["device_model"].upper().startswith("SM-A245")

That is not a bug. It is a deliberate scope marker: "I only certify GPU results
from the device whose GPU path I validated." Refusing to certify untested
hardware is correct.

Why it changes
--------------
The S26 has now produced the same evidence the A24 has:

    gpu_delegate_created        true
    gpu_delegate_type           TfLiteGpuDelegateV2
    replaced_nodes/total_nodes  31 / 31
    full_delegate               true
    verification                verified
    failure_or_fallback         []
    CPU-GPU equivalence         passed, argmax 32/32, cosine 0.99993

So the marker is widened to a named list of validated devices. The other eight
conditions are NOT touched. This patch does not make anything easier to pass.

The one honest asymmetry
------------------------
On the A24, LiteRT's compatibility list answered "supported". On the S26 it
answers "not supported" and we proceeded anyway (see patch 1). The S26 GPU path
is therefore not provenance-identical to the A24's.

That deviation must never be silent, so this patch also records it per run:

    gpu_compatibility_list_supported    what LiteRT's list said
    formal_gpu_compat_list_override     true when the run passed despite false

Any report using S26 GPU numbers has to disclose that flag.

Usage
-----
    python s26_patch_formal_gate.py            apply
    python s26_patch_formal_gate.py --revert   undo
    python s26_patch_formal_gate.py --check    report status only

Every edit must match exactly once. If any does not, nothing is written.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[2]
LOGGER = REPO / "tools/d1_logger_v4.py"

EDITS = [
    (
        "validated-device list",
        'RUNNER_PACKAGE = "com.example.d1check.benchmarkrunner"\n',

        'RUNNER_PACKAGE = "com.example.d1check.benchmarkrunner"\n'
        "\n"
        "# Devices whose GPU measurement path has been validated end to end: the\n"
        "# delegate is created, takes every node, leaves no fallback evidence, and\n"
        "# produces outputs numerically equivalent to CPU. Adding a prefix here is a\n"
        "# claim that this evidence exists; see s26/patches/README.md patch 2.\n"
        "#   SM-A245  Galaxy A24  the device the v4 stack was built and validated on\n"
        "#   SM-S942  Galaxy S26  validated 2026-09-13, s26/results/PILOT_RESULTS.md\n"
        "#            its LiteRT compatibility-list verdict is false, so its runs\n"
        "#            carry formal_gpu_compat_list_override=True\n"
        'FORMAL_GPU_VALIDATED_DEVICE_PREFIXES = ("SM-A245", "SM-S942")\n',
    ),
    (
        "device condition",
        '    galaxy_a24 = str(capture_metadata.get("device_model", "")).upper().startswith("SM-A245")\n'
        "    formal_gpu_valid = (\n"
        "        is_gpu\n"
        '        and mode == "basic"\n'
        "        and galaxy_a24\n",

        '    device_model = str(capture_metadata.get("device_model", "")).upper()\n'
        "    gpu_validated_device = device_model.startswith(\n"
        "        FORMAL_GPU_VALIDATED_DEVICE_PREFIXES\n"
        "    )\n"
        "    formal_gpu_valid = (\n"
        "        is_gpu\n"
        '        and mode == "basic"\n'
        "        and gpu_validated_device\n",
    ),
    (
        "override disclosure",
        '        "formal_gpu_valid": formal_gpu_valid if is_gpu else None,\n',

        '        "formal_gpu_valid": formal_gpu_valid if is_gpu else None,\n'
        '        "gpu_compatibility_list_supported": (\n'
        '            metadata_event.get("gpu_compatibility_list_supported")\n'
        "            if is_gpu else None\n"
        "        ),\n"
        '        "formal_gpu_compat_list_override": (\n'
        '            metadata_event.get("gpu_compatibility_list_supported") is False\n'
        "            if is_gpu else None\n"
        "        ),\n",
    ),
]


def read(path: Path) -> tuple[str, str]:
    raw = path.read_bytes()
    newline = "\r\n" if b"\r\n" in raw else "\n"
    return raw.replace(b"\r\n", b"\n").decode("utf-8"), newline


def write(path: Path, text: str, newline: str) -> None:
    data = text.encode("utf-8")
    if newline == "\r\n":
        data = data.replace(b"\n", b"\r\n")
    path.write_bytes(data)


def status() -> str:
    if not LOGGER.exists():
        return "missing"
    text, _ = read(LOGGER)
    applied = "FORMAL_GPU_VALIDATED_DEVICE_PREFIXES" in text
    original = "galaxy_a24" in text
    if applied and not original:
        return "applied"
    if original and not applied:
        return "original"
    return "mixed"


def run(revert: bool) -> int:
    text, newline = read(LOGGER)
    for label, before, after in EDITS:
        old, new = (after, before) if revert else (before, after)
        count = text.count(old)
        if count != 1:
            print(f"[X] {LOGGER.name} :: {label} -> matched {count} times, expected 1")
            print("    Nothing was written. Run with --check first.")
            return 1
        text = text.replace(old, new, 1)
    write(LOGGER, text, newline)
    print(f"[ok] patched {LOGGER.relative_to(REPO)}")
    print()
    print("Reverted." if revert else
          "Applied. No rebuild needed - this is a host-side Python tool.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--revert", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    state = status()
    print(f"repo   : {REPO}")
    print(f"file   : tools/d1_logger_v4.py")
    print(f"status : {state}")
    print()
    if args.check:
        return 0
    if state == "missing":
        print("[X] tools/d1_logger_v4.py not found. Wrong folder?")
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
