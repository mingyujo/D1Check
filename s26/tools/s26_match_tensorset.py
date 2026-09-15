#!/usr/bin/env python3
"""Find why our container hash differs from the reference, without rebuilding.

The core three hashes already match the A24 reference:

    representative_tensor_set_sha256    bcd9fad7...cf2c   payload, identical
    preprocessing_configuration_sha256  ad6f76b1...2260   identical
    label_mapping_file_sha256           70002b0f...3d15   identical

so the 40 preprocessed tensors are bit-identical. Only the whole-container
hash differs, which means something in the JSON header differs. The header is
fully deterministic; every field is derived from the payload, the label map,
Pillow, or one of three free-text CLI arguments:

    --dataset-version   --dataset-source-url   --dataset-license

This script rewrites only that dataset block, re-serialises the header exactly
as the builder does, and checks whether any candidate reproduces the reference
container hash. Nothing is written unless --write is given.

Usage
-----
    python s26_match_tensorset.py                     search and report
    python s26_match_tensorset.py --show              print our dataset block
    python s26_match_tensorset.py --write out.d1tset  write the matching one
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys

MAGIC = b"D1TSET01"
DEFAULT_CONTAINER = r"C:\datasets\d1-imagenette-val40.d1tset"
REFERENCE_CONTAINER_SHA256 = (
    "cf1b9232516a25a3fa081af8a7d19da1ff91091d72a5d0fe7431bb3980dd1128"
)

VERSIONS = [
    "imagenette2-320",
    "imagenette2-320.tgz",
    "imagenette2",
    "imagenette-2-320",
    "320",
    "v2-320",
]
SOURCE_URLS = [
    "https://s3.amazonaws.com/fast-ai-imageclas/imagenette2-320.tgz",
    "https://s3.amazonaws.com/fast-ai-imageclas/imagenette2-320.tgz ",
    "https://github.com/fastai/imagenette",
    "https://docs.fast.ai/data.external.html",
    "s3://fast-ai-imageclas/imagenette2-320.tgz",
]
LICENSES = [
    "Imagenette distribution terms; verify upstream dataset/source-image licenses",
    "Imagenette distribution terms; verify upstream dataset/source image licenses",
    "Imagenette distribution terms",
    "Apache-2.0",
    "see upstream",
    "unknown",
]


def canonical_json_bytes(value: dict) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")


def load(path: Path) -> tuple[dict, bytes, str]:
    raw = path.read_bytes()
    if raw[:8] != MAGIC:
        raise SystemExit(f"[X] not a d1tset container: {path}")
    length = struct.unpack("<I", raw[8:12])[0]
    header = json.loads(raw[12:12 + length].decode("utf-8"))
    payload = raw[12 + length:]
    return header, payload, hashlib.sha256(raw).hexdigest()


def container_hash(header: dict, payload: bytes) -> str:
    body = canonical_json_bytes(header)
    digest = hashlib.sha256()
    digest.update(MAGIC)
    digest.update(struct.pack("<I", len(body)))
    digest.update(body)
    digest.update(payload)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--container", default=DEFAULT_CONTAINER)
    parser.add_argument("--target", default=REFERENCE_CONTAINER_SHA256)
    parser.add_argument("--show", action="store_true")
    parser.add_argument("--write")
    args = parser.parse_args()

    path = Path(args.container)
    if not path.is_file():
        raise SystemExit(f"[X] container not found: {path}")

    header, payload, actual = load(path)
    target = args.target.lower()

    print(f"container : {path}")
    print(f"ours      : {actual}")
    print(f"reference : {target}")
    print()

    recomputed = container_hash(header, payload)
    if recomputed != actual:
        print("[!] Re-serialising our own header does not reproduce our own hash.")
        print("    The difference is NOT in the dataset block. Ask for the full")
        print("    header instead of guessing.")
        return 1
    print("  self-check OK: re-serialising our header reproduces our hash,")
    print("  so the search below is valid.")
    print()

    print("our dataset block:")
    for key, value in sorted(header["dataset"].items()):
        print(f"  {key:12s} {value!r}")
    print()
    print(f"  payload sha256      {header['tensor_set_sha256']}")
    print(f"  preprocessing sha   {header['preprocessing']['configuration_sha256']}")
    print(f"  label map sha       {header['label_mapping']['file_sha256']}")
    print(f"  Pillow              {header['preprocessing']['implementation_version']}")
    print(f"  seed / count        {header['selection']['seed']} / "
          f"{header['selection']['sample_count']}")
    print(f"  first sample        {header['selection']['selected_sample_ids'][0]}")

    if args.show:
        return 0

    if actual == target:
        print()
        print("  Already identical. Nothing to search.")
        return 0

    print()
    total = len(VERSIONS) * len(SOURCE_URLS) * len(LICENSES)
    print(f"searching {total} dataset-block candidates ...")
    for version in VERSIONS:
        for url in SOURCE_URLS:
            for license_text in LICENSES:
                trial = json.loads(json.dumps(header))
                trial["dataset"]["version"] = version
                trial["dataset"]["source_url"] = url
                trial["dataset"]["license"] = license_text
                if container_hash(trial, payload) != target:
                    continue
                print()
                print("  MATCH FOUND")
                print(f"    --dataset-version     {version!r}")
                print(f"    --dataset-source-url  {url!r}")
                print(f"    --dataset-license     {license_text!r}")
                if args.write:
                    out = Path(args.write)
                    body = canonical_json_bytes(trial)
                    out.write_bytes(
                        MAGIC + struct.pack("<I", len(body)) + body + payload
                    )
                    print(f"    wrote {out}")
                    print(f"    sha256 {hashlib.sha256(out.read_bytes()).hexdigest()}")
                return 0

    print()
    print("  No candidate matched.")
    print()
    print("  The difference is somewhere else in the header. Ask 조민규 to run")
    print("  this on his container and send the dataset block:")
    print()
    print("      python -c \"import json,struct,sys;"
          "d=open(sys.argv[1],'rb').read();"
          "n=struct.unpack('<I',d[8:12])[0];"
          "print(json.dumps(json.loads(d[12:12+n])['dataset'],"
          "ensure_ascii=False,indent=2))\" <his .d1tset>")
    print()
    print("  The tensors are already proven identical, so this is a metadata")
    print("  question, not a data question.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
