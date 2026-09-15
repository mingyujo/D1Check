"""s26_verify_exports.py -- verify exports-v2 files against dataset_manifest.json.

dataset_manifest.json pins the sha256 of each exported CSV. If a copy, a line
ending conversion or an edit changes a single byte, this catches it.

Usage:
    python s26_verify_exports.py <exports directory>

Exit code:
    0  all files match
    1  mismatch, or a file is missing
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: python s26_verify_exports.py <exports directory>")
        return 1

    root = Path(argv[1])
    manifest_path = root / "dataset_manifest.json"
    if not manifest_path.is_file():
        print("[X] dataset_manifest.json not found: %s" % manifest_path)
        return 1

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    outputs = manifest.get("outputs", {})
    if not outputs:
        print("[X] manifest has no outputs block.")
        return 1

    failed = 0
    for name, meta in outputs.items():
        target = root / name
        expected = meta.get("sha256", "")
        if not target.is_file():
            print("   [X] %s  -- file missing" % name)
            failed += 1
            continue
        actual = sha256_of(target)
        if actual == expected:
            rows = meta.get("row_count")
            suffix = "  (%s rows)" % format(rows, ",") if isinstance(rows, int) else ""
            print("   [OK] %s%s" % (name, suffix))
        else:
            print("   [X] %s" % name)
            print("        expected %s" % expected)
            print("        actual   %s" % actual)
            failed += 1

    if failed:
        print("")
        print("[X] %d file(s) differ from the manifest." % failed)
        return 1

    print("")
    print("[OK] all %d file(s) match the manifest byte for byte." % len(outputs))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
