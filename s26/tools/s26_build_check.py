#!/usr/bin/env python3
"""Warn if the APK installed on the phone is older than the patched sources.

Editing a .kt file does not change the app on the device. Running a pilot
against a stale APK silently reproduces the old behaviour, which is expensive
to debug because the logs look identical.

Exit codes: 0 = APK looks current, 2 = APK looks stale, 1 = could not tell.
"""

from __future__ import annotations

import datetime as dt
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PKG_DIR = REPO / "benchmark-runner/src/main/java/com/example/d1check/benchmarkrunner"
PACKAGE = "com.example.d1check.benchmarkrunner"
WATCHED = [
    PKG_DIR / "s26/GpuCompatibilityPolicy.kt",
    PKG_DIR / "GpuBenchmarkEngine.kt",
    PKG_DIR / "AccuracyPreflightEngine.kt",
]
STAMP = re.compile(r"lastUpdateTime=(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})")


def newest_source() -> tuple[Path, dt.datetime] | None:
    found = [(p, dt.datetime.fromtimestamp(p.stat().st_mtime)) for p in WATCHED if p.exists()]
    return max(found, key=lambda item: item[1]) if found else None


def installed_at(adb: str, serial: str | None) -> dt.datetime | None:
    command = [adb]
    if serial:
        command += ["-s", serial]
    command += ["shell", "dumpsys", "package", PACKAGE]
    try:
        out = subprocess.run(command, capture_output=True, text=True, timeout=30).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    stamps = [dt.datetime.strptime(m, "%Y-%m-%d %H:%M:%S") for m in STAMP.findall(out)]
    return max(stamps) if stamps else None


def main() -> int:
    adb = sys.argv[1] if len(sys.argv) > 1 else "adb"
    serial = sys.argv[2] if len(sys.argv) > 2 else None

    source = newest_source()
    if source is None:
        print("  [?] no watched source files found")
        return 1
    source_path, source_time = source

    apk_time = installed_at(adb, serial)
    if apk_time is None:
        print("  [?] could not read the installed app's update time")
        return 1

    print(f"  newest source : {source_time:%Y-%m-%d %H:%M:%S}  ({source_path.name})")
    print(f"  installed APK : {apk_time:%Y-%m-%d %H:%M:%S}")

    if apk_time >= source_time:
        print("  [OK] the installed app is newer than the patched sources.")
        return 0

    behind = source_time - apk_time
    print()
    print(f"  [X] STALE APK - the app is {behind} older than the source.")
    print("      The patch is on disk but NOT on the phone.")
    print("      In Android Studio: pick the 'benchmark-runner' module, press Run,")
    print("      wait for it to install, then run this again.")
    return 2


if __name__ == "__main__":
    sys.exit(main())
