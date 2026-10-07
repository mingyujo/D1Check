"""PC reference outputs for the S26 mixed-request port (R1, 2026-10-08) — A24 code, unmodified, driven from here.

What it produces (all under --out, git-ignored):
  anchors.json                 19206 x 4 fixed anchors read from the EfficientDet metadata by A24
                               tools/d1_detection_contract.model_contract (mediapipe flatbuffer schemas);
                               written as json.dumps(..., separators=(',',':')) — this reproduces A24's
                               anchors.json SHA-256 e095e869... (ProbeTaskAdapter.ANCHORS_SHA256) byte for byte.
  labels.txt                   90 rows from the detection .tflite zip  (SHA f8803ef7... checked by A24 code)
  labels_without_background.txt 1000 rows from the classification zip (SHA e697a491... checked by A24 code)
  classification/golden.json + input.f32le + output_0.f32le   A24 tools/d1_classification_reference.generate
  detection/golden.json + input.f32le + output_0.f32le + output_1.f32le   A24 tools/d1_detection_contract.generate
  rgb.bin                      decoded RGB8 of the canonical PNG (for the JVM K3 test: resize/normalize -> tensor SHA)
  reference_pc.json            summary: SHAs, versions, top-5 vs quality_reference.json, decoded detections

Both A24 generators run ai-edge-litert CPU with num_threads=1 and check 3 deterministic invocations
(the A24 "PC reference": quality_reference.json was made the same way on 2026-09-20 with ai-edge-litert 2.2.0).

Usage (from the clone root):
  py -3 s26/tools/mixreq/make_reference_pc.py --a24-tools local_inputs/a24_repo
      --cls-model local_models/efficientnet_lite0.tflite --det-model local_inputs/public/efficientdet_lite0.tflite
      --png local_inputs/canonical_v123/00575b9132bb3746.png --out local_inputs/reference_pc
      [--quality-reference local_inputs/a24_repo/docs/team/s26_interface_20261004/quality_reference.json]
The A24 tree is read, never modified or committed. The --out directory must not exist yet (A24 generators refuse to overwrite).
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import importlib.metadata
import io
import json
import sys
import zipfile
from pathlib import Path

EXPECTED = {
    "cls_model_sha256": "6c7ab0a6e5dcbf38a8c33b960996a55a3b4300b36a018c4545801de3a3c8bde0",
    "det_model_sha256": "40338edf5ec70d43e318b0a716a84d4564cd1802759a7a07170c7e43796dbf58",
    "cls_label_sha256": "e697a491aa735cc6c2aaf982f8e86e8fc7b0a1ea7750a2cc6a2bdfc1e109012f",
    "det_label_sha256": "f8803ef7900160c629d570848dfda4175e21667bf7b71f73f8ece4938c9f2bf2",
    "anchors_sha256": "e095e869203d5f5442583712e1546aac8f5112512b1a98925165fe17b455c3bc",
    "png_sha256": "3e8b925feafbfe5fdd4efb9d7911f445a3212100fa73744f6fd855cf6160f1ab",
    "rgb_sha256": "ca6c2e2bf77bfd8c9240404f516a17eb21c24ba34159ce2e3722bf8aaf225455",
    "cls_input_tensor_sha256": "603328d02dfc2b1aa356b26b0f14b9e70f8cdb80609c89fd171bcf4c3ff85462",
    "cls_raw_output_sha256_a24": "0df3d53519e40f8e86e683866a00a1083f7b90c53a6b0625b52fe2b065926103",
}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--a24-tools", required=True, type=Path, help="directory that contains the A24 'tools' package")
    ap.add_argument("--cls-model", required=True, type=Path)
    ap.add_argument("--det-model", required=True, type=Path)
    ap.add_argument("--png", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--quality-reference", type=Path)
    args = ap.parse_args()

    sys.path.insert(0, str(args.a24_tools.resolve()))
    from tools import d1_classification_reference as cls_ref  # noqa: E402  (A24, unmodified)
    from tools import d1_detection_contract as det  # noqa: E402  (A24, unmodified)

    if args.out.exists():
        raise SystemExit(f"--out already exists: {args.out} (A24 generators refuse to overwrite; choose a fresh folder)")
    args.out.mkdir(parents=True)
    checks: dict[str, bool] = {}
    record: dict = {
        "schema": "s26-mixreq-reference-pc-v1",
        "generated_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "generator_sha256": sha(Path(__file__).read_bytes()),
        "a24_tools_root": str(args.a24_tools.resolve()),
        "a24_module_sha256": {
            "d1_classification_reference.py": sha(Path(cls_ref.__file__).read_bytes()),
            "d1_detection_contract.py": sha(Path(det.__file__).read_bytes()),
        },
        "versions": {
            "python": sys.version.split()[0],
            "ai-edge-litert": importlib.metadata.version("ai-edge-litert"),
            "mediapipe": importlib.metadata.version("mediapipe"),
            "numpy": importlib.metadata.version("numpy"),
            "pillow": importlib.metadata.version("pillow"),
        },
        "expected": EXPECTED,
        "command": [sys.executable, *sys.argv],
    }

    # --- models + labels ------------------------------------------------------------------------
    cls_bytes, det_bytes = args.cls_model.read_bytes(), args.det_model.read_bytes()
    record["cls_model_sha256"], record["det_model_sha256"] = sha(cls_bytes), sha(det_bytes)
    record["cls_model_bytes"], record["det_model_bytes"] = len(cls_bytes), len(det_bytes)
    checks["cls_model_sha256"] = record["cls_model_sha256"] == EXPECTED["cls_model_sha256"]
    checks["det_model_sha256"] = record["det_model_sha256"] == EXPECTED["det_model_sha256"]
    with zipfile.ZipFile(io.BytesIO(cls_bytes)) as z:
        cls_labels = z.read("labels_without_background.txt")
    with zipfile.ZipFile(io.BytesIO(det_bytes)) as z:
        det_labels = z.read("labels.txt")
    (args.out / "labels_without_background.txt").write_bytes(cls_labels)
    (args.out / "labels.txt").write_bytes(det_labels)
    record["cls_label_sha256"], record["det_label_sha256"] = sha(cls_labels), sha(det_labels)
    record["cls_label_rows"] = len(cls_labels.decode().splitlines())
    record["det_label_rows"] = len(det_labels.decode().splitlines())
    checks["cls_label_sha256"] = record["cls_label_sha256"] == EXPECTED["cls_label_sha256"]
    checks["det_label_sha256"] = record["det_label_sha256"] == EXPECTED["det_label_sha256"]

    # --- anchors (A24 model_contract: mediapipe metadata; label SHA + 19206 checked inside) ---------
    anchors, labels_from_contract = det.model_contract(args.det_model)
    anchors_json = json.dumps(anchors, separators=(",", ":")).encode()
    (args.out / "anchors.json").write_bytes(anchors_json)
    record["anchors_count"] = len(anchors)
    record["anchors_sha256"] = sha(anchors_json)
    record["anchors_first"], record["anchors_last"] = anchors[0], anchors[-1]
    checks["anchors_sha256_matches_a24_file"] = record["anchors_sha256"] == EXPECTED["anchors_sha256"]
    checks["det_labels_equal_contract"] = labels_from_contract == det_labels.decode().splitlines()

    # --- image --------------------------------------------------------------------------------
    png = args.png.read_bytes()
    record["png_sha256"], record["png_bytes"] = sha(png), len(png)
    checks["png_sha256"] = record["png_sha256"] == EXPECTED["png_sha256"]
    det.require_canonical_png(png)
    from PIL import Image
    with Image.open(io.BytesIO(png)) as im:
        rgb = im.tobytes()
        record["image_size"] = list(im.size)
    (args.out / "rgb.bin").write_bytes(rgb)
    record["rgb_sha256"] = sha(rgb)
    checks["rgb_sha256"] = record["rgb_sha256"] == EXPECTED["rgb_sha256"]

    # --- A24 classification reference (ai-edge-litert CPU, 1 thread, 3 deterministic invocations) --
    cls_rec = cls_ref.generate(args.cls_model, args.png, record["png_sha256"], args.out / "classification")
    record["classification"] = {k: cls_rec[k] for k in ("input_tensor_sha256", "raw_output_sha256", "results",
                                                        "runtime", "runtime_version", "cpu_threads", "image_size")}
    checks["cls_input_tensor_sha256"] = cls_rec["input_tensor_sha256"] == EXPECTED["cls_input_tensor_sha256"]
    record["classification"]["raw_output_sha256_equals_a24_quality_reference"] = (
        cls_rec["raw_output_sha256"] == EXPECTED["cls_raw_output_sha256_a24"])

    # --- A24 detection reference --------------------------------------------------------------
    det_rec = det.generate(args.det_model, args.png, args.out / "detection")
    record["detection"] = {k: det_rec[k] for k in ("input_tensor_sha256", "raw_output_sha256", "decoded",
                                                   "runtime", "runtime_version", "cpu_threads", "image_size",
                                                   "decoder", "decoder_sha256", "preprocessing_sha256")}
    record["detection"]["decoded_count"] = len(det_rec["decoded"])

    # --- top-5 against A24 quality_reference.json (label/index equal, |dscore| <= 0.001) ---------
    if args.quality_reference:
        q = json.loads(args.quality_reference.read_text(encoding="utf-8"))
        sample = next(s for s in q["samples"] if s["image"]["sha256"] == EXPECTED["png_sha256"])
        ref_top5 = sample["reference"]["results"]
        ours = cls_rec["results"]
        pairs = [{"label_matches": a["label"] == b["label"], "index_matches": a["class_index"] == b["class_index"],
                  "score_delta": abs(a["score"] - b["score"])} for a, b in zip(ref_top5, ours)]
        passed = len(ref_top5) == len(ours) == 5 and all(p["label_matches"] and p["index_matches"]
                                                          and p["score_delta"] <= 1e-3 for p in pairs)
        record["classification"]["a24_quality_reference_top5"] = ref_top5
        record["classification"]["top5_vs_a24_quality_reference"] = {"passed": passed, "pairs": pairs,
                                                                     "rule": "same label+index in order, |dscore| <= 0.001 (d1_energy_collection quality rule)"}
        checks["cls_top5_equals_a24_quality_reference"] = passed
        record["classification"]["a24_quality_reference_raw_output_sha256"] = sample["reference"]["raw_output_sha256"]

    record["checks"] = checks
    record["all_checks_passed"] = all(checks.values())
    (args.out / "reference_pc.json").write_text(json.dumps(record, indent=2, ensure_ascii=False, sort_keys=True),
                                               encoding="utf-8")
    print(json.dumps({"checks": checks, "all_checks_passed": record["all_checks_passed"],
                      "cls_top5": [(r["label"], r["class_index"], round(r["score"], 6)) for r in cls_rec["results"]],
                      "det_decoded_count": len(det_rec["decoded"]),
                      "det_input_tensor_sha256": det_rec["input_tensor_sha256"],
                      "det_raw_output_sha256": det_rec["raw_output_sha256"],
                      "cls_raw_output_sha256": cls_rec["raw_output_sha256"]}, indent=2, ensure_ascii=False))
    return 0 if record["all_checks_passed"] else 3


if __name__ == "__main__":
    sys.exit(main())
