#!/usr/bin/env python3
"""Offline preservation of files already recovered from a future phone session.

No ADB connection/pull is performed here. A supplied local transport manifest
must bind every byte before a new destination is created. Existing data is
never overwritten. Claim/START and measurements are not implemented.
"""

from __future__ import annotations

import argparse
import json
import shutil
import stat
import sys
from pathlib import Path
from typing import Any

from d1_a24_laptop_validator import SHA, ValidationError, contained_file, load_json, sha256


def verify_local_delivery(source: Path, manifest: dict[str, Any]) -> list[tuple[str, Path, str, int]]:
    if manifest.get("schema") != "a24-laptop-transport-v1":
        raise ValidationError("wrong transport manifest schema")
    files = manifest.get("files", [])
    if not isinstance(files, list) or not files:
        raise ValidationError("transport manifest has no files")
    verified: list[tuple[str, Path, str, int]] = []
    paths: set[str] = set()
    for item in files:
        name, expected, size = item.get("path"), item.get("sha256"), item.get("bytes")
        if not isinstance(name, str) or name.casefold() in paths:
            raise ValidationError("missing/duplicate case-insensitive path")
        paths.add(name.casefold())
        if not isinstance(expected, str) or not SHA.fullmatch(expected) or not isinstance(size, int) or isinstance(size, bool) or size < 0:
            raise ValidationError("transport exact SHA/byte count missing")
        path = contained_file(source, name)
        if path.stat().st_size != size or sha256(path) != expected:
            raise ValidationError(f"delivery original byte/SHA mismatch: {name}")
        verified.append((name, path, expected, size))
    actual_files: set[str] = set()
    directories = [source]
    while directories:
        for path in directories.pop().iterdir():
            attributes = getattr(path.lstat(), "st_file_attributes", 0)
            if path.is_symlink() or attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0):
                raise ValidationError("symlink/reparse point in recovered directory")
            if path.is_dir():
                directories.append(path)
            elif path.is_file():
                relative = path.relative_to(source).as_posix()
                # A checksum manifest cannot include its own byte digest recursively.
                if relative == "transport_manifest.json":
                    continue
                contained_file(source, relative)
                actual_files.add(relative.casefold())
    if actual_files != paths:
        raise ValidationError("recovery manifest must cover every original file; missing or extra paths")
    return verified


def recover_local(source: Path, manifest: dict[str, Any], destination: Path | None = None) -> dict[str, Any]:
    files = verify_local_delivery(source, manifest)
    if destination is not None:
        source = source.resolve()
        destination = destination.resolve()
        if destination.exists() or destination == source or source in destination.parents:
            raise ValidationError("destination must be a new directory outside source")
        destination.mkdir(parents=True, exist_ok=False)
        for name, original, expected, size in files:
            target = destination / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(original, target)
            if target.stat().st_size != size or sha256(target) != expected:
                raise ValidationError(f"copied file SHA mismatch: {name}; keep partial delivery for investigation")
    return {"schema": "a24-laptop-recovery-receipt-v1", "status": "OFFLINE_BYTES_VERIFIED_DEVICE_UNVERIFIED",
            "file_count": len(files), "logical_bytes": sum(row[3] for row in files), "copied": destination is not None,
            "files": [{"path": name, "sha256": digest, "bytes": size} for name, _, digest, size in files],
            "actual_device_commands": 0, "adb_pull_calls": 0, "NN_calls": 0, "registry_claims": 0, "sessions_consumed": 0}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--destination", type=Path, default=None)
    args = parser.parse_args(argv)
    try:
        result = recover_local(args.source, load_json(args.manifest), args.destination)
    except (ValidationError, OSError, TypeError) as error:
        print(json.dumps({"status": "BLOCKED", "reason": str(error), "actual_device_commands": 0}))
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
