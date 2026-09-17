import base64
import contextlib
import hashlib
import io
import json
import re
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest import mock

import d1_calibration_cli as calibration


PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


class CalibrationCliTest(unittest.TestCase):
    def bundle(self, root: Path, calibration_mode: str = "baseline_pilot"):
        input_root = root / "input"
        images = input_root / "images"
        images.mkdir(parents=True)
        image = images / "fixture.png"
        image.write_bytes(PNG_BYTES)
        labels = input_root / "label_mapping.txt"
        labels.write_text(
            "".join(f"label-{index}\n" for index in range(1001)), encoding="utf-8"
        )
        apk = root / "runner.apk"
        apk.write_bytes(b"apk-fixture")
        policy = None
        if calibration_mode == "baseline_formal":
            policy = {
                "policy_id": "a24-baseline-v1",
                "maximum_start_battery_temperature_deci_c": 300,
                "stability_window_ms": 60_000,
                "maximum_stability_delta_deci_c": 5,
            }
            policy["sha256"] = calibration._temperature_policy_sha256(policy)
        payload = {
            "schema_version": calibration.SCHEMA_VERSION,
            "protocol_version": "calibration-v1",
            "session_id": str(uuid.uuid4()),
            "calibration_mode": calibration_mode,
            "mode": "fixed",
            "fixed_backend": "CPU",
            "cpu_threads": 1,
            "queue_capacity": 8,
            "warmup_count": 3,
            "model_sha256": calibration.MODEL_SHA256,
            "label_mapping_sha256": hashlib.sha256(labels.read_bytes()).hexdigest(),
            "preprocessing_sha256": calibration.PREPROCESSING_SHA256,
            "preprocessing_contract_id": calibration.PREPROCESSING_CONTRACT_ID,
            "expected_apk_sha256": hashlib.sha256(apk.read_bytes()).hexdigest(),
            "deadline_state": "calibration_pending",
            "temperature_policy": policy,
            "environment": {
                "physical_position": "flat desk",
                "ambient_temperature_c": 23.0,
                "expected_charging": False,
                "expected_screen_on": True,
            },
            "images": [{
                "image_id": "fixture-1",
                "relative_path": "images/fixture.png",
                "sha256": hashlib.sha256(PNG_BYTES).hexdigest(),
                "byte_count": len(PNG_BYTES),
                "label_index": 0,
                "label": "label-0",
                "raw_width": 1,
                "raw_height": 1,
                "exif_orientation": 1,
                "transformed_width": 1,
                "transformed_height": 1,
                "mime_type": "image/png",
            }],
        }
        manifest = input_root / "input_manifest.json"
        manifest.write_text(json.dumps(payload), encoding="utf-8")
        return input_root, manifest, labels, apk

    @staticmethod
    def snapshot(root: Path):
        return {
            path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in root.rglob("*") if path.is_file()
        }

    def test_validate_input_and_dry_run_have_no_filesystem_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_root, manifest, labels, apk = self.bundle(root)
            before = self.snapshot(root)
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout), \
                    mock.patch("subprocess.run", side_effect=AssertionError("ADB/subprocess forbidden")), \
                    mock.patch("subprocess.Popen", side_effect=AssertionError("ADB/subprocess forbidden")):
                rc = calibration.main([
                    "plan", "--manifest", str(manifest), "--labels", str(labels),
                    "--input-root", str(input_root), "--apk", str(apk), "--dry-run",
                ])
            self.assertEqual(0, rc)
            self.assertEqual(before, self.snapshot(root))
            self.assertIn("no ADB command was executed", stdout.getvalue())
            self.assertIn(calibration.MAIN_ACTIVITY, stdout.getvalue())

    def test_actual_jpeg_exif_orientations_validate_transformed_dimensions(self):
        from PIL import Image

        for orientation in range(1, 9):
            with self.subTest(orientation=orientation), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                input_root, manifest, labels, apk = self.bundle(root)
                (input_root / "images" / "fixture.png").unlink()
                image_path = input_root / "images" / "fixture.jpg"
                exif = Image.Exif()
                exif[274] = orientation
                with Image.new("RGB", (2, 3), (12, 34, 56)) as image:
                    image.save(image_path, format="JPEG", exif=exif)
                payload = json.loads(manifest.read_text(encoding="utf-8"))
                image_spec = payload["images"][0]
                image_spec.update({
                    "relative_path": "images/fixture.jpg",
                    "sha256": hashlib.sha256(image_path.read_bytes()).hexdigest(),
                    "byte_count": image_path.stat().st_size,
                    "mime_type": "image/jpeg",
                    "raw_width": 2,
                    "raw_height": 3,
                    "exif_orientation": orientation,
                    "transformed_width": 3 if orientation >= 5 else 2,
                    "transformed_height": 2 if orientation >= 5 else 3,
                })
                manifest.write_text(json.dumps(payload), encoding="utf-8")
                calibration.validate_input_manifest(manifest, labels, apk, input_root)

    def test_input_bundle_reads_image_and_rejects_replacement_missing_and_extra(self):
        for mutation in ("replacement", "missing", "extra"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                input_root, manifest, labels, apk = self.bundle(root)
                calibration.validate_input_manifest(manifest, labels, apk, input_root)
                image = input_root / "images" / "fixture.png"
                if mutation == "replacement":
                    image.write_bytes(PNG_BYTES + b"replaced")
                elif mutation == "missing":
                    image.unlink()
                else:
                    (input_root / "unexpected.txt").write_text("unexpected", encoding="utf-8")
                with self.assertRaises((calibration.CalibrationValidationError, OSError)):
                    calibration.validate_input_manifest(manifest, labels, apk, input_root)

    def test_label_mapping_and_formal_policy_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_root, manifest, labels, apk = self.bundle(root)
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            payload["images"][0]["label"] = "label-1"
            manifest.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(calibration.CalibrationValidationError):
                calibration.validate_input_manifest(manifest, labels, apk, input_root)

        for mutation in ("missing", "hash"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                input_root, manifest, labels, apk = self.bundle(root, "baseline_formal")
                payload = json.loads(manifest.read_text(encoding="utf-8"))
                if mutation == "missing":
                    payload["temperature_policy"] = None
                else:
                    payload["temperature_policy"]["sha256"] = "0" * 64
                manifest.write_text(json.dumps(payload), encoding="utf-8")
                with self.assertRaises(calibration.CalibrationValidationError):
                    calibration.validate_input_manifest(manifest, labels, apk, input_root)

    def test_duplicate_identity_magic_dimensions_and_apk_replacement_fail_closed(self):
        for mutation in ("duplicate_id", "duplicate_path", "duplicate_hash",
                         "magic", "dimensions", "apk"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                input_root, manifest, labels, apk = self.bundle(root)
                payload = json.loads(manifest.read_text(encoding="utf-8"))
                if mutation.startswith("duplicate"):
                    second = dict(payload["images"][0])
                    second["image_id"] = "fixture-2"
                    second["relative_path"] = "images/fixture-2.png"
                    second["sha256"] = "4" * 64
                    if mutation == "duplicate_id":
                        second["image_id"] = payload["images"][0]["image_id"]
                    elif mutation == "duplicate_path":
                        second["relative_path"] = payload["images"][0]["relative_path"]
                    else:
                        second["sha256"] = payload["images"][0]["sha256"]
                    payload["images"].append(second)
                    manifest.write_text(json.dumps(payload), encoding="utf-8")
                elif mutation == "magic":
                    image = input_root / "images" / "fixture.png"
                    image.write_bytes(b"not-an-image")
                    payload["images"][0]["byte_count"] = image.stat().st_size
                    payload["images"][0]["sha256"] = hashlib.sha256(
                        image.read_bytes()
                    ).hexdigest()
                    manifest.write_text(json.dumps(payload), encoding="utf-8")
                elif mutation == "dimensions":
                    payload["images"][0]["raw_width"] = 2
                    payload["images"][0]["transformed_width"] = 2
                    manifest.write_text(json.dumps(payload), encoding="utf-8")
                else:
                    apk.write_bytes(b"replacement")
                with self.assertRaises((calibration.CalibrationValidationError, OSError)):
                    calibration.validate_input_manifest(manifest, labels, apk, input_root)

    def test_invalid_deadline_state_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_root, manifest, labels, apk = self.bundle(root)
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            payload["deadline_state"] = "100ms"
            manifest.write_text(json.dumps(payload), encoding="utf-8")
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                rc = calibration.main([
                    "validate-input", "--manifest", str(manifest),
                    "--labels", str(labels), "--input-root", str(input_root),
                    "--apk", str(apk),
                ])
            self.assertEqual(1, rc)
            self.assertIn("calibration_pending", stderr.getvalue())

    def test_result_validation_rejects_partial_and_hash_replacement(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            _, source_manifest, source_labels, _ = self.bundle(base / "source")
            manifest_value = json.loads(source_manifest.read_text(encoding="utf-8"))
            root = base / "result"
            root.mkdir()
            input_manifest = root / "input_manifest.json"
            input_manifest.write_bytes(source_manifest.read_bytes())
            label_mapping = root / "label_mapping.txt"
            label_mapping.write_bytes(source_labels.read_bytes())
            session = manifest_value["session_id"]
            identity = {
                "schema_version": calibration.SCHEMA_VERSION,
                "protocol_version": "calibration-v1",
                "session_id": session,
            }
            metadata = root / "metadata.json"
            metadata_value = {
                **identity,
                "calibration_mode": "baseline_pilot",
                "manifest_sha256": hashlib.sha256(input_manifest.read_bytes()).hexdigest(),
                "label_mapping_sha256": manifest_value["label_mapping_sha256"],
                "preprocessing_sha256": manifest_value["preprocessing_sha256"],
                "preprocessing_contract_id": manifest_value["preprocessing_contract_id"],
                "preprocessing_configuration": calibration.PREPROCESSING_CONFIGURATION,
                "temperature_policy_sha256": None,
                "start_thermal_sample_ns": 1,
                "apk_sha256": manifest_value["expected_apk_sha256"],
                "model_sha256": manifest_value["model_sha256"],
            }
            metadata.write_text(json.dumps(metadata_value), encoding="utf-8")
            request_id = str(uuid.uuid4())
            requests = root / "requests.jsonl"
            requests.write_text(json.dumps({
                **identity,
                "calibration_mode": "baseline_pilot",
                "request_id": request_id,
                "request_type": "urgent",
                "terminal_status": "succeeded",
                "deadline_outcome": "not_set",
                "deadline_met": None,
                "output_sha256": "5" * 64,
                "persisted_relative_path": None,
            }) + "\n", encoding="utf-8")
            thermal = root / "thermal_samples.jsonl"
            thermal.write_text(json.dumps({
                **identity,
                "calibration_mode": "baseline_pilot",
                "timestamp_ns": 1,
                "thermal_status": 1,
                "battery_temperature_deci_c": 250,
            }) + "\n", encoding="utf-8")
            summary = root / "summary.json"
            summary.write_text(json.dumps({
                **identity,
                "calibration_mode": "baseline_pilot",
                "start_mono_ns": 1,
                "end_mono_ns": 2,
                "counts": {"succeeded": 1, "failed": 0, "rejected": 0, "expired": 0},
                "deadline_counts": {
                    "not_set": 1, "on_time": 0, "late": 0, "not_completed": 0,
                },
                "arrived_count": 1,
                "completed_count": 1,
                "deadline_set_count": 0,
                "overall_completion_rate": 1.0,
                "on_time_completion_rate": None,
                "deadline_violation_rate": None,
                "thermal_sample_count": 1,
            }), encoding="utf-8")
            artifact_files = (
                input_manifest, label_mapping, metadata, requests, thermal, summary,
            )
            artifact_set = [{
                "relative_path": path.name,
                "byte_count": path.stat().st_size,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            } for path in artifact_files]
            provenance = {
                **identity,
                "manifest_sha256": hashlib.sha256(input_manifest.read_bytes()).hexdigest(),
                "apk_sha256": manifest_value["expected_apk_sha256"],
                "model_sha256": manifest_value["model_sha256"],
                "artifact_set": artifact_set,
            }
            (root / "provenance.json").write_text(json.dumps(provenance), encoding="utf-8")
            self.assertEqual(6, len(calibration.validate_result(root)))
            self.assertTrue((root / "provenance.json").is_file())
            self.assertNotIn("provenance.json", [item["relative_path"] for item in artifact_set])

            for relative in ("results/provenance.json", "nested/path/provenance.json"):
                with self.subTest(relative=relative):
                    extra = root / relative
                    extra.parent.mkdir(parents=True, exist_ok=True)
                    extra.write_text("unexpected nested provenance", encoding="utf-8")
                    with self.assertRaisesRegex(
                        calibration.CalibrationValidationError, re.escape(relative)
                    ):
                        calibration.validate_result(root)
                    provenance["artifact_set"] = artifact_set + [{
                        "relative_path": relative,
                        "byte_count": extra.stat().st_size,
                        "sha256": hashlib.sha256(extra.read_bytes()).hexdigest(),
                    }]
                    (root / "provenance.json").write_text(json.dumps(provenance), encoding="utf-8")
                    with self.assertRaisesRegex(
                        calibration.CalibrationValidationError, re.escape(relative)
                    ):
                        calibration.validate_result(root)
                    extra.unlink()
                    provenance["artifact_set"] = artifact_set
                    (root / "provenance.json").write_text(json.dumps(provenance), encoding="utf-8")
                    self.assertEqual(6, len(calibration.validate_result(root)))

            metadata.write_bytes(b"replaced")
            with self.assertRaises(calibration.CalibrationValidationError):
                calibration.validate_result(root)

            metadata.write_text(json.dumps(metadata_value), encoding="utf-8")
            partial = root / "results" / ".partial.part"
            partial.parent.mkdir(exist_ok=True)
            partial.write_text("partial", encoding="utf-8")
            provenance["artifact_set"] = artifact_set + [{
                "relative_path": "results/.partial.part",
                "byte_count": partial.stat().st_size,
                "sha256": hashlib.sha256(partial.read_bytes()).hexdigest(),
            }]
            (root / "provenance.json").write_text(json.dumps(provenance), encoding="utf-8")
            with self.assertRaises(calibration.CalibrationValidationError):
                calibration.validate_result(root)


if __name__ == "__main__":
    unittest.main()
