"""canonical-srgb-png-v2 generator for the S26 mixed-request port (2026-10-08, R1).

The A24 repository ships no converter: tools/d1_classification_reference.py only *checks* a PNG.
Rule source (verbatim, feature/arrival-scheduling-20260923 @ d588323):
  docs/team/s26_interface_20261004/quality_reference.json  samples[0].image.transformation =
    "Pillow JPEG decode; embedded ICC -> sRGB using LittleCMS perceptual intent 0 if present,
     otherwise assume sRGB; strip all metadata; no geometry change"
  docs/DECODE_RESOLUTION_20260920.md line 51 (same rule; IHDR/IDAT/IEND only).

Primary acceptance (혼합요청_사전등록_v1.md §1-4): decoded RGB SHA-256 must equal the registered value.
The PNG byte SHA depends on the zlib encoder; a difference is RECORDED ("A24 와 다름 — 입력 PNG 바이트"),
not fatal. Every zlib compress level 0..9 is tried and the level that reproduces the expected PNG SHA is
used when one exists (then the bytes are identical to the A24 file); otherwise Pillow's default (6).

Usage:
  py -3 s26/tools/mixreq/make_canonical_png.py --jpeg <in.jpg> --expected-jpeg-sha256 <hex> --out <out.png>
      [--expected-rgb-sha256 <hex>] [--expected-png-sha256 <hex>] [--record <record.json>]
Exit 0 = RGB SHA matched (or no expectation given); 3 = RGB SHA mismatch; 2 = input SHA mismatch.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import io
import json
import struct
import sys
from pathlib import Path


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def require_canonical_png(data: bytes) -> list[str]:
    """Same chunk rule as A24 tools/d1_detection_contract.require_canonical_png (IHDR/IDAT/IEND only)."""
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not canonical PNG")
    offset, kinds = 8, []
    while offset + 12 <= len(data):
        size = struct.unpack(">I", data[offset:offset + 4])[0]
        kind = data[offset + 4:offset + 8]
        if kind not in (b"IHDR", b"IDAT", b"IEND") or offset + 12 + size > len(data):
            raise ValueError("color/orientation/ancillary or malformed PNG chunk: %r" % kind)
        kinds.append(kind.decode())
        offset += 12 + size
        if kind == b"IEND":
            break
    if not kinds or kinds[0] != "IHDR" or kinds[-1] != "IEND" or "IDAT" not in kinds or offset != len(data):
        raise ValueError("incomplete canonical PNG")
    return kinds


def decode_jpeg_to_srgb_rgb(data: bytes) -> tuple[bytes, tuple[int, int], dict]:
    from PIL import Image, ImageCms, features

    with Image.open(io.BytesIO(data)) as im:
        if im.format != "JPEG":
            raise ValueError("source must be a JPEG (format=%r)" % im.format)
        orientation = im.getexif().get(274)
        icc = im.info.get("icc_profile")
        info = {
            "source_mode": im.mode,
            "exif_orientation": orientation,  # recorded only; the rule applies no geometry change
            "icc_present": bool(icc),
            "icc_sha256": sha(icc) if icc else None,
            "pillow_version": Image.__version__,
            "littlecms_version": features.version("littlecms2"),
        }
        if icc:
            # "embedded ICC -> sRGB using LittleCMS perceptual intent 0"
            src = ImageCms.ImageCmsProfile(io.BytesIO(icc))
            dst = ImageCms.createProfile("sRGB")
            converted = ImageCms.profileToProfile(im, src, dst, renderingIntent=0, outputMode="RGB")
            info["transform"] = "ICC->sRGB perceptual(0)"
        else:
            # "otherwise assume sRGB": pixel values are taken as sRGB as decoded
            converted = im if im.mode == "RGB" else im.convert("RGB")
            info["transform"] = "assume sRGB (no ICC)"
        rgb = converted.tobytes()
        size = converted.size
        if len(rgb) != size[0] * size[1] * 3:
            raise ValueError("RGB byte count mismatch")
    return rgb, size, info


def encode_png(rgb: bytes, size: tuple[int, int], compress_level: int) -> bytes:
    from PIL import Image

    # A fresh image carries no info dict -> Pillow writes IHDR/IDAT/IEND only (verified by require_canonical_png).
    out = Image.frombytes("RGB", size, rgb)
    buf = io.BytesIO()
    out.save(buf, format="PNG", compress_level=compress_level)
    data = buf.getvalue()
    require_canonical_png(data)
    return data


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--jpeg", required=True, type=Path)
    ap.add_argument("--expected-jpeg-sha256", required=True)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--expected-rgb-sha256")
    ap.add_argument("--expected-png-sha256")
    ap.add_argument("--record", type=Path)
    args = ap.parse_args()

    data = args.jpeg.read_bytes()
    jpeg_sha = sha(data)
    if jpeg_sha != args.expected_jpeg_sha256.lower():
        print(json.dumps({"status": "input_sha_mismatch", "jpeg_sha256": jpeg_sha}), flush=True)
        return 2
    rgb, size, info = decode_jpeg_to_srgb_rgb(data)
    rgb_sha = sha(rgb)
    rgb_match = None if not args.expected_rgb_sha256 else rgb_sha == args.expected_rgb_sha256.lower()

    levels = {}
    chosen_level = 6
    for level in range(10):
        png = encode_png(rgb, size, level)
        levels[str(level)] = {"sha256": sha(png), "bytes": len(png)}
        if args.expected_png_sha256 and levels[str(level)]["sha256"] == args.expected_png_sha256.lower():
            chosen_level = level
    png = encode_png(rgb, size, chosen_level)
    png_sha = sha(png)
    png_match = None if not args.expected_png_sha256 else png_sha == args.expected_png_sha256.lower()

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(png)
    record = {
        "schema": "s26-canonical-png-v2-record-v1",
        "generated_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "generator_sha256": sha(Path(__file__).read_bytes()),
        "rule": "Pillow JPEG decode; embedded ICC -> sRGB using LittleCMS perceptual intent 0 if present, "
                "otherwise assume sRGB; strip all metadata; no geometry change",
        "rule_source": "quality_reference.json samples[0].image.transformation @ d588323; DECODE_RESOLUTION_20260920.md:51",
        "jpeg_sha256": jpeg_sha,
        "jpeg_bytes": len(data),
        "width": size[0],
        "height": size[1],
        "rgb_sha256": rgb_sha,
        "expected_rgb_sha256": args.expected_rgb_sha256,
        "rgb_match": rgb_match,
        "png_sha256": png_sha,
        "png_bytes": len(png),
        "png_chunks": require_canonical_png(png),
        "png_compress_level": chosen_level,
        "png_sha256_by_compress_level": levels,
        "expected_png_sha256": args.expected_png_sha256,
        "png_match": png_match,
        "a24_difference": None if png_match else "A24 와 다름 — 입력 PNG 바이트 (RGB SHA 기준으로 판정)",
        "command": [sys.executable, *sys.argv],
        **info,
    }
    if args.record:
        args.record.parent.mkdir(parents=True, exist_ok=True)
        args.record.write_text(json.dumps(record, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    print(json.dumps(record, indent=2, ensure_ascii=False, sort_keys=True), flush=True)
    return 0 if rgb_match in (None, True) else 3


if __name__ == "__main__":
    sys.exit(main())
