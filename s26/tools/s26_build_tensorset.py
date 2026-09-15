#!/usr/bin/env python3
"""Fetch Imagenette + the TF-Slim label map and build the representative tensor set.

d1_representative_tensors.py deliberately never downloads anything, so this
script does the fetching around it and then calls it with the exact parameters
V4_INTEGRATION.md documents:

    --sample-count 40 --seed 305419896
    --dataset-version "imagenette2-320"
    --label-map imagenet_lsvrc_2015_synsets.txt

Reproducibility note
--------------------
The container header embeds Pillow's version:

    preprocessing = preprocessing_configuration(PIL.__version__)

so the preprocessing hash - and therefore the whole container hash - depends on
which Pillow built it. Two people get byte-identical containers only with the
same images, the same label map, the same sample-count/seed AND the same Pillow.
This script prints every one of those so they can be compared.

Usage
-----
    python s26_build_tensorset.py                     build into C:\\datasets
    python s26_build_tensorset.py --datasets-dir D:\\x
    python s26_build_tensorset.py --check             report what is present
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import urllib.request

REPO = Path(__file__).resolve().parents[2]
BUILDER = REPO / "tools/d1_representative_tensors.py"

LABEL_MAP_URL = (
    "https://raw.githubusercontent.com/tensorflow/models/master/"
    "research/slim/datasets/imagenet_lsvrc_2015_synsets.txt"
)
LABEL_MAP_SHA256 = (
    "70002b0ff5de60a3a17a82dbfcff291931f96225ddf941ad2e182fc39e183d15"
)
DATASET_URL = "https://s3.amazonaws.com/fast-ai-imageclas/imagenette2-320.tgz"

SAMPLE_COUNT = 40
SEED = 305419896
DATASET_VERSION = "imagenette2-320"
DATASET_LICENSE = (
    "Imagenette distribution terms; verify upstream dataset/source-image licenses"
)
IMAGENETTE_WNIDS = (
    "n01440764", "n02102040", "n02979186", "n03000684", "n03028079",
    "n03394916", "n03417042", "n03425413", "n03445777", "n03888257",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(url: str, target: Path, label: str) -> None:
    print(f"  downloading {label}")
    print(f"    {url}")
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_suffix(target.suffix + ".part")
    last = [-1]

    def report(block_count: int, block_size: int, total: int) -> None:
        if total <= 0:
            return
        done = min(block_count * block_size, total)
        percent = int(done * 100 / total)
        if percent != last[0] and percent % 5 == 0:
            last[0] = percent
            print(f"    {percent:3d}%  {done/1048576:.0f} / {total/1048576:.0f} MB")

    urllib.request.urlretrieve(url, partial, reporthook=report)
    partial.replace(target)
    print(f"    saved {target}  ({target.stat().st_size:,} bytes)")


def ensure_label_map(datasets: Path) -> Path:
    path = datasets / "imagenet_lsvrc_2015_synsets.txt"
    if not path.is_file():
        download(LABEL_MAP_URL, path, "TF-Slim label map")
    digest = sha256_file(path)
    if digest != LABEL_MAP_SHA256:
        raise SystemExit(
            f"[X] label map hash mismatch\n"
            f"    expected {LABEL_MAP_SHA256}\n"
            f"    got      {digest}\n"
            f"    Delete {path} and run again."
        )
    lines = [
        line.strip()
        for line in path.read_bytes().decode("utf-8-sig").splitlines()
        if line.strip()
    ]
    if len(lines) != 1000 or len(set(lines)) != 1000:
        raise SystemExit("[X] label map must hold 1000 unique WNIDs")
    print(f"  label map OK   sha256 {digest}")
    return path


def ensure_dataset(datasets: Path) -> Path:
    root = datasets / "imagenette2-320"
    split = root / "val"
    if all((split / wnid).is_dir() for wnid in IMAGENETTE_WNIDS):
        print(f"  dataset OK     {root}")
        return root

    archive = datasets / "imagenette2-320.tgz"
    if not archive.is_file():
        download(DATASET_URL, archive, "Imagenette 320px (about 325 MB)")

    print(f"  extracting {archive.name}")
    with tarfile.open(archive, "r:gz") as tar:
        for member in tar.getmembers():
            destination = (datasets / member.name).resolve()
            if not str(destination).startswith(str(datasets.resolve())):
                raise SystemExit(f"[X] unsafe path in archive: {member.name}")
        tar.extractall(datasets)

    missing = [wnid for wnid in IMAGENETTE_WNIDS if not (split / wnid).is_dir()]
    if missing:
        raise SystemExit(
            "[X] extracted tree is missing Imagenette classes: " + ", ".join(missing)
        )
    print(f"  dataset OK     {root}")
    return root


def pillow_version() -> str:
    try:
        import PIL
    except ImportError:
        raise SystemExit(
            "[X] Pillow is not installed. It does the image preprocessing.\n"
            "    pip install Pillow"
        )
    return PIL.__version__


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--datasets-dir", default=r"C:\datasets")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    datasets = Path(args.datasets_dir)
    container = datasets / "d1-imagenette-val40.d1tset"

    print(f"repo      : {REPO}")
    print(f"datasets  : {datasets}")
    print(f"container : {container}")
    print(f"Pillow    : {pillow_version()}   <- part of the container hash")
    print()

    if not BUILDER.is_file():
        raise SystemExit(f"[X] builder not found: {BUILDER}")

    if args.check:
        for label, path in (
            ("label map", datasets / "imagenet_lsvrc_2015_synsets.txt"),
            ("dataset  ", datasets / "imagenette2-320"),
            ("container", container),
        ):
            mark = "present" if path.exists() else "MISSING"
            print(f"  {label} : {mark}  {path}")
        return 0

    if container.is_file():
        print("Container already exists. Validating it instead of rebuilding.")
    else:
        print("[1/3] Inputs")
        label_map = ensure_label_map(datasets)
        ensure_dataset(datasets)

        print()
        print("[2/3] Building the tensor set")
        build = subprocess.run(
            [
                sys.executable, str(BUILDER),
                "--dataset-dir", str(datasets / "imagenette2-320"),
                "--label-map", str(label_map),
                "--sample-count", str(SAMPLE_COUNT),
                "--seed", str(SEED),
                "--dataset-version", DATASET_VERSION,
                "--dataset-license", DATASET_LICENSE,
                "--output", str(container),
            ],
            capture_output=True, text=True,
        )
        sys.stdout.write(build.stdout)
        if build.returncode != 0:
            sys.stderr.write(build.stderr)
            return build.returncode

    print()
    print("[3/3] Validating")
    check = subprocess.run(
        [sys.executable, str(BUILDER), "--validate", str(container)],
        capture_output=True, text=True,
    )
    sys.stdout.write(check.stdout)
    if check.returncode != 0:
        sys.stderr.write(check.stderr)
        return check.returncode

    try:
        report = json.loads(check.stdout)
    except json.JSONDecodeError:
        report = {}

    print()
    print("=" * 64)
    print(" Compare these with 조민규's container to prove you used the")
    print(" same representative sample. If they match, no file transfer")
    print(" is needed at all.")
    print("=" * 64)
    for key in (
        "representative_tensor_set_sha256",
        "preprocessing_configuration_sha256",
        "label_mapping_file_sha256",
        "input_count",
    ):
        if key in report:
            print(f"  {key:38s} {report[key]}")
    print(f"  {'pillow_version':38s} {pillow_version()}")
    print(f"  {'sample_count / seed':38s} {SAMPLE_COUNT} / {SEED}")
    print()
    print(f"Container ready: {container}")
    print("Next: s26_formal.bat")
    return 0


if __name__ == "__main__":
    sys.exit(main())
