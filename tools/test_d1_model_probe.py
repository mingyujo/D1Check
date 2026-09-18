import hashlib
import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
import uuid
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock


MODULE_PATH = Path(__file__).with_name("d1_model_probe.py")
SPEC = importlib.util.spec_from_file_location("d1_model_probe", MODULE_PATH)
assert SPEC and SPEC.loader
probe = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = probe
SPEC.loader.exec_module(probe)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def tensor(index, name, shape):
    return {
        "index": index,
        "name": name,
        "shape": shape,
        "dtype": "FLOAT32",
        "quantization": "none",
    }


def manifest(*, detection=False, device_id="a24-primary", serial="serial-a24"):
    model_id = (
        "efficientdet-lite0-float32-v1"
        if detection
        else "efficientnet-lite0-float32-v1"
    )
    pinned = probe.PINNED_MODELS[model_id]
    task = "detection" if detection else "classification"
    return {
        "identity": {
            "schema_version": 1,
            "protocol_version": "model-probe-v1",
            "session_id": "71d5f7df-356f-4b3e-9ea7-a4be9d887801",
            "created_utc": "2026-09-18T12:00:00Z",
        },
        "target": {
            "device_id": device_id,
            "package_name": probe.PACKAGE_NAME,
            "apk_sha256": "a" * 64,
            "adb_serial": serial,
            "manufacturer": "vendor",
            "model": "model",
            "soc": "soc",
            "abi": "arm64-v8a",
            "ram_bytes": 8_000_000_000,
            "android_release": "16",
            "api_level": 36,
            "build_fingerprint": "vendor/product/device:16/build:user/release-keys",
            "cpu_abi": "arm64-v8a",
            "cpu_features": "asimd",
            "gpu_vendor": "vendor",
            "gpu_renderer": "renderer",
            "gpu_driver": "driver",
            "thermal_capability": "android-thermal-status",
        },
        "model": {
            "task_id": task,
            "model_id": model_id,
            "url": pinned.url,
            "filename": pinned.filename,
            "byte_count": pinned.byte_count,
            "sha256": pinned.sha256,
            "distribution_policy": (
                "external_research_only_no_redistribution"
                if detection
                else "external_verified_apache_2_0"
            ),
            "metadata_license_status": "null" if detection else "apache-2.0",
            "label_filename": "labels.txt" if detection else "labels_without_background.txt",
            "label_rows": 90 if detection else 1000,
            "label_sha256": (
                "f8803ef7900160c629d570848dfda4175e21667bf7b71f73f8ece4938c9f2bf2"
                if detection
                else "e697a491aa735cc6c2aaf982f8e86e8fc7b0a1ea7750a2cc6a2bdfc1e109012f"
            ),
        },
        "tensor": {
            "input_count": 1,
            "inputs": [
                tensor(
                    0,
                    "serving_default_images:0" if detection else "images",
                    [1, 320, 320, 3] if detection else [1, 224, 224, 3],
                )
            ],
            "output_count": 2 if detection else 1,
            "outputs": (
                [
                    tensor(0, "StatefulPartitionedCall:1", [1, 19206, 90]),
                    tensor(1, "StatefulPartitionedCall:0", [1, 19206, 4]),
                ]
                if detection
                else [tensor(0, "Softmax", [1, 1000])]
            ),
            "normalization": "(RGB-127.5)/127.5" if detection else "(RGB-127.0)/128.0",
            "raw_output_semantics": "anchor_scores_and_locations" if detection else "class_probabilities",
        },
        "runtime": {
            "litert_version": "1.4.2",
            "cpu_threads": 1,
            "xnnpack": True,
            "gpu_profile_id": "gpu-fp32-strict-v1",
            "gpu_configuration_sha256": "b" * 64,
            "tasks_vision_version": "1.0.0" if detection else "not_used",
        },
        "input": {
            "input_id": "raw-seed-0",
            "kind": "deterministic_rgb",
            "generation_rule": "coordinate-rgb-v1",
            "seed": 0,
            "url": None,
            "filename": None,
            "byte_count": 0,
            "sha256": None,
            "decode_contract": "not_used",
        },
        "comparator": {
            "comparator_id": "combined-tolerance-v1",
            "atol": 1e-4,
            "rtol": 1e-3,
            "relative_epsilon": 1e-6,
            "decoded_box_atol_px": 2.0,
            "decoded_score_atol": 1e-3,
            "decoded_order": "score_desc_label_box",
        },
        "execution": {
            "backend": "CPU",
            "cold_repetitions": 3,
            "warm_repetitions": 10,
            "maximum_duration_ms": 120_000,
            "timeout_policy": "bounded-host-and-device-v1",
            "cleanup_policy": "bounded-delete-and-confirm-v1",
        },
    }


class ManifestContractTest(unittest.TestCase):
    def test_accepts_both_approved_models_without_device_model_branching(self):
        first = probe.validate_manifest_data(manifest())
        second = probe.validate_manifest_data(
            manifest(detection=True, device_id="replication-device-01", serial="wifi-serial")
        )
        self.assertEqual(first["target"]["device_id"], "a24-primary")
        self.assertEqual(second["target"]["device_id"], "replication-device-01")

    def test_rejects_unknown_key_latest_url_and_noncanonical_uuid(self):
        cases = []
        unknown = manifest()
        unknown["target"]["unexpected"] = True
        cases.append(unknown)
        latest = manifest()
        latest["model"]["url"] = latest["model"]["url"].replace("/1/", "/latest/")
        cases.append(latest)
        bad_uuid = manifest()
        bad_uuid["identity"]["session_id"] = str(uuid.uuid4()).upper()
        cases.append(bad_uuid)
        bad_serial = manifest()
        bad_serial["target"]["adb_serial"] = "--transport-id"
        cases.append(bad_serial)
        for case in cases:
            with self.subTest(case=case):
                with self.assertRaises(probe.ProbeContractError):
                    probe.validate_manifest_data(case)

    def test_rejects_model_hash_tensor_and_distribution_policy_drift(self):
        for mutate in (
            lambda item: item["model"].__setitem__("sha256", "0" * 64),
            lambda item: item["tensor"]["inputs"][0].__setitem__("shape", [1, 225, 225, 3]),
            lambda item: item["model"].__setitem__("distribution_policy", "redistributable"),
        ):
            value = manifest()
            mutate(value)
            with self.assertRaises(probe.ProbeContractError):
                probe.validate_manifest_data(value)

    def test_detection_external_sample_must_match_pinned_contract(self):
        value = manifest(detection=True)
        value["input"] = {
            "input_id": "cat-and-dog-v1",
            "kind": "external_image",
            "generation_rule": "not_used",
            "seed": None,
            "url": probe.PINNED_SAMPLE.url,
            "filename": probe.PINNED_SAMPLE.filename,
            "byte_count": probe.PINNED_SAMPLE.byte_count,
            "sha256": probe.PINNED_SAMPLE.sha256,
            "decode_contract": "android-bitmap-argb8888-v1",
        }
        probe.validate_manifest_data(value)
        value["input"]["sha256"] = "0" * 64
        with self.assertRaises(probe.ProbeContractError):
            probe.validate_manifest_data(value)


class FileAndPlanTest(unittest.TestCase):
    def test_local_file_validation_checks_hash_size_and_fixed_set(self):
        model_bytes = b"model-fixture"
        apk_bytes = b"apk-fixture"
        pinned = probe.PinnedFile(
            "efficientnet-lite0-float32-v1",
            probe.PINNED_MODELS["efficientnet-lite0-float32-v1"].url,
            "efficientnet_lite0.tflite",
            len(model_bytes),
            sha256(model_bytes),
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            model_path = root / pinned.filename
            manifest_path = root / "model_probe_manifest.json"
            apk = root.parent / f"runner-{root.name}.apk"
            model_path.write_bytes(model_bytes)
            apk.write_bytes(apk_bytes)
            value = manifest()
            value["model"].update(
                byte_count=pinned.byte_count,
                sha256=pinned.sha256,
            )
            value["target"]["apk_sha256"] = sha256(apk_bytes)
            manifest_path.write_text(json.dumps(value), encoding="utf-8")
            with mock.patch.dict(probe.PINNED_MODELS, {pinned.identifier: pinned}):
                files = probe.validate_local_inputs(value, manifest_path, root, apk)
                self.assertEqual(files["model"], model_path.resolve())
                (root / "extra.bin").write_bytes(b"extra")
                with self.assertRaisesRegex(probe.ProbeContractError, "fixed file set"):
                    probe.validate_local_inputs(value, manifest_path, root, apk)

    def test_symlink_model_is_rejected(self):
        if not hasattr(os, "symlink"):
            self.skipTest("symlink unavailable")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            outside = root.parent / f"outside-{root.name}"
            outside.write_bytes(b"x")
            link = root / "model.tflite"
            try:
                link.symlink_to(outside)
            except OSError as error:
                self.skipTest(f"symlink unavailable: {error}")
            expected = probe.PinnedFile("x", "https://example.test/v1/model", "model.tflite", 1, sha256(b"x"))
            with self.assertRaises(probe.ProbeContractError):
                probe.verify_file(link, root, expected, "model")

    def test_dry_run_only_constructs_argv_and_separates_devices(self):
        a24 = probe.validate_manifest_data(manifest())
        other = probe.validate_manifest_data(
            manifest(device_id="replication-device-01", serial="serial-other")
        )
        root = Path("C:/inputs")
        manifest_path = root / "model_probe_manifest.json"
        first = probe.build_dry_run_plan(a24, manifest_path, root, Path("adb.exe"), Path("runner.apk"))
        second = probe.build_dry_run_plan(other, manifest_path, root, Path("adb.exe"), Path("runner.apk"))
        self.assertEqual(first["network_calls"], 0)
        self.assertEqual(first["adb_calls"], 0)
        self.assertEqual(first["writes"], 0)
        self.assertNotEqual(first["device_id"], second["device_id"])
        self.assertTrue(all(command[:3] == ["adb.exe", "-s", "serial-a24"] for command in first["commands"]))
        self.assertTrue(all(command[:3] == ["adb.exe", "-s", "serial-other"] for command in second["commands"]))
        flattened = "\n".join("\0".join(command) for command in first["commands"])
        self.assertNotIn("SM-A245N", flattened)
        self.assertNotIn("R59", flattened)

    def test_cli_plan_does_not_validate_or_touch_payload_files(self):
        value = manifest()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest_path = root / "model_probe_manifest.json"
            manifest_path.write_text(json.dumps(value), encoding="utf-8")
            with mock.patch.object(probe, "validate_local_inputs") as verify:
                with redirect_stdout(io.StringIO()):
                    exit_code = probe.main(
                        [
                            "plan", "--manifest", str(manifest_path), "--input-root", str(root),
                            "--apk", str(root / "missing.apk"), "--adb", "adb.exe",
                            "--serial", value["target"]["adb_serial"], "--dry-run",
                        ]
                    )
            self.assertEqual(exit_code, 0)
            verify.assert_not_called()




class HostExecutorTest(unittest.TestCase):
    def _fixture(self, base: Path):
        input_root = base / "input"
        output_root = base / "output"
        input_root.mkdir()
        output_root.mkdir()
        model_bytes = b"model-fixture"
        apk_bytes = b"apk-fixture"
        pinned = probe.PinnedFile(
            "efficientnet-lite0-float32-v1",
            probe.PINNED_MODELS["efficientnet-lite0-float32-v1"].url,
            "efficientnet_lite0.tflite",
            len(model_bytes),
            sha256(model_bytes),
        )
        value = manifest()
        value["model"].update(byte_count=pinned.byte_count, sha256=pinned.sha256)
        value["target"]["apk_sha256"] = sha256(apk_bytes)
        manifest_path = input_root / "model_probe_manifest.json"
        model_path = input_root / pinned.filename
        apk = base / "runner.apk"
        adb = base / "adb.exe"
        manifest_path.write_text(json.dumps(value), encoding="utf-8")
        model_path.write_bytes(model_bytes)
        apk.write_bytes(apk_bytes)
        adb.write_bytes(b"adb")
        return value, pinned, manifest_path, input_root, output_root, apk, adb

    def test_execute_seam_stages_waits_pulls_and_cleans_without_finalizing(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            value, pinned, manifest_path, input_root, output_root, apk, adb = (
                self._fixture(base)
            )
            session = value["identity"]["session_id"]
            device_id = value["target"]["device_id"]
            summary = {
                "schema_version": 1,
                "protocol_version": "model-probe-v1",
                "session_id": session,
                "device_id": device_id,
                "model_id": value["model"]["model_id"],
                "backend": value["execution"]["backend"],
                "status": "seam_smoke_only_unfinalized",
                "finalized": False,
                "elapsed_ns": 123,
                "details": {},
            }
            summary_bytes = json.dumps(summary).encode("utf-8")
            calls = []
            poll_count = 0

            def runner(argv, timeout_seconds, allowed_returncodes):
                nonlocal poll_count
                command = list(argv)
                calls.append((command, timeout_seconds, allowed_returncodes))
                tail = command[3:]
                if tail == ["get-state"]:
                    return probe.ProcessResult(0, b"device\n", b"")
                if "sha256sum" in tail:
                    remote = tail[-1]
                    name = Path(remote).name
                    if name.endswith(".part"):
                        name = name[:-5]
                    local = (
                        manifest_path
                        if name == "model_probe_manifest.json"
                        else input_root / name
                    )
                    digest = probe.sha256_file(local)
                    return probe.ProcessResult(
                        0, f"{digest}  {remote}\n".encode("utf-8"), b""
                    )
                if tail[:2] == ["shell", "am"]:
                    return probe.ProcessResult(0, b"Status: ok\n", b"")
                if "test" in tail and "-s" in tail:
                    poll_count += 1
                    return probe.ProcessResult(1 if poll_count == 1 else 0, b"", b"")
                if tail[:3] == ["exec-out", "run-as", probe.PACKAGE_NAME]:
                    return probe.ProcessResult(0, summary_bytes, b"")
                return probe.ProcessResult(0, b"", b"")

            with mock.patch.dict(probe.PINNED_MODELS, {pinned.identifier: pinned}):
                result = probe.execute_seam(
                    value,
                    manifest_path,
                    input_root,
                    adb,
                    apk,
                    output_root,
                    value["target"]["adb_serial"],
                    poll_interval_seconds=0.001,
                    process_runner=runner,
                    sleep=lambda _: None,
                )

            self.assertEqual(result["status"], "completed_unfinalized")
            self.assertFalse(result["finalized"])
            session_output = output_root / session
            self.assertEqual(
                json.loads((session_output / "summary.json").read_text("utf-8")),
                summary,
            )
            host = json.loads(
                (session_output / "host_execution.json").read_text("utf-8")
            )
            self.assertEqual(host["status"], "completed_unfinalized")
            self.assertTrue(host["activity_dispatched"])
            self.assertTrue(host["summary_pulled"])
            self.assertTrue(host["input_cleanup_confirmed"])
            flattened = [part for command, _, _ in calls for part in command]
            self.assertNotIn("uninstall", flattened)
            self.assertNotIn("clear", flattened)
            self.assertGreaterEqual(poll_count, 2)
            self.assertTrue(
                any(
                    command[3:8]
                    == ["shell", "run-as", probe.PACKAGE_NAME, "rm", "-rf"]
                    for command, _, _ in calls
                )
            )

    def test_execute_seam_hash_mismatch_fails_closed_and_still_cleans(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            value, pinned, manifest_path, input_root, output_root, apk, adb = (
                self._fixture(base)
            )
            calls = []

            def runner(argv, timeout_seconds, allowed_returncodes):
                command = list(argv)
                calls.append(command)
                tail = command[3:]
                if tail == ["get-state"]:
                    return probe.ProcessResult(0, b"device\n", b"")
                if "sha256sum" in tail:
                    return probe.ProcessResult(
                        0, f"{'0' * 64}  {tail[-1]}\n".encode("utf-8"), b""
                    )
                return probe.ProcessResult(0, b"", b"")

            with mock.patch.dict(probe.PINNED_MODELS, {pinned.identifier: pinned}):
                with self.assertRaisesRegex(
                    probe.ProbeContractError, "shared staging SHA-256 mismatch"
                ):
                    probe.execute_seam(
                        value,
                        manifest_path,
                        input_root,
                        adb,
                        apk,
                        output_root,
                        value["target"]["adb_serial"],
                        process_runner=runner,
                    )

            session_output = output_root / value["identity"]["session_id"]
            host = json.loads(
                (session_output / "host_execution.json").read_text("utf-8")
            )
            self.assertEqual(host["status"], "failed")
            self.assertFalse(host["activity_dispatched"])
            self.assertFalse(host["summary_pulled"])
            flattened = [part for command in calls for part in command]
            self.assertIn("rm", flattened)

    def test_execute_seam_summary_timeout_is_bounded_and_cleans(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            value, pinned, manifest_path, input_root, output_root, apk, adb = (
                self._fixture(base)
            )
            value["execution"]["maximum_duration_ms"] = 1
            manifest_path.write_text(json.dumps(value), encoding="utf-8")
            calls = []

            def runner(argv, timeout_seconds, allowed_returncodes):
                command = list(argv)
                calls.append((command, timeout_seconds))
                tail = command[3:]
                if tail == ["get-state"]:
                    return probe.ProcessResult(0, b"device\n", b"")
                if "sha256sum" in tail:
                    remote = tail[-1]
                    name = Path(remote).name
                    if name.endswith(".part"):
                        name = name[:-5]
                    local = (
                        manifest_path
                        if name == "model_probe_manifest.json"
                        else input_root / name
                    )
                    digest = probe.sha256_file(local)
                    return probe.ProcessResult(
                        0, f"{digest}  {remote}\n".encode("utf-8"), b""
                    )
                if tail[:2] == ["shell", "am"]:
                    return probe.ProcessResult(0, b"Status: ok\n", b"")
                if "test" in tail and "-s" in tail:
                    return probe.ProcessResult(1, b"", b"")
                return probe.ProcessResult(0, b"", b"")

            ticks = iter([0.0, 1.0])
            with mock.patch.dict(probe.PINNED_MODELS, {pinned.identifier: pinned}):
                with self.assertRaisesRegex(
                    probe.ProbeContractError, "timed out waiting for device summary"
                ):
                    probe.execute_seam(
                        value,
                        manifest_path,
                        input_root,
                        adb,
                        apk,
                        output_root,
                        value["target"]["adb_serial"],
                        host_grace_seconds=0.0,
                        process_runner=runner,
                        monotonic=lambda: next(ticks),
                        sleep=lambda _: None,
                    )

            host = json.loads(
                (
                    output_root
                    / value["identity"]["session_id"]
                    / "host_execution.json"
                ).read_text("utf-8")
            )
            self.assertEqual(host["status"], "failed")
            self.assertTrue(host["activity_dispatched"])
            self.assertFalse(host["summary_pulled"])
            self.assertTrue(
                any(
                    command[3:8]
                    == ["shell", "run-as", probe.PACKAGE_NAME, "rm", "-rf"]
                    for command, _ in calls
                )
            )

    def test_default_process_runner_uses_fixed_argv_without_shell(self):
        completed = mock.Mock(returncode=0, stdout=b"ok", stderr=b"")
        with mock.patch.object(probe.subprocess, "run", return_value=completed) as run:
            result = probe._default_process_runner(
                ["adb.exe", "-s", "serial", "get-state"],
                5.0,
                frozenset({0}),
            )
        self.assertEqual(result.stdout, b"ok")
        kwargs = run.call_args.kwargs
        self.assertIs(kwargs["shell"], False)
        self.assertIs(kwargs["stdin"], probe.subprocess.DEVNULL)
        self.assertEqual(kwargs["timeout"], 5.0)


class ArtifactValidationTest(unittest.TestCase):
    def _write_artifacts(self, root: Path, session_id: str, device_id: str):
        identity = {"session_id": session_id, "device_id": device_id}
        for filename in probe.ARTIFACT_FILES - {"provenance.json", "events.jsonl"}:
            (root / filename).write_text(json.dumps(identity), encoding="utf-8")
        (root / "events.jsonl").write_text(
            json.dumps({**identity, "event": "probe_started"}) + "\n", encoding="utf-8"
        )
        artifact_set = []
        for filename in sorted(probe.ARTIFACT_FILES - {"provenance.json"}):
            path = root / filename
            artifact_set.append(
                {"path": filename, "byte_count": path.stat().st_size, "sha256": probe.sha256_file(path)}
            )
        (root / "provenance.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "protocol_version": "model-probe-v1",
                    **identity,
                    "artifact_set": artifact_set,
                }
            ),
            encoding="utf-8",
        )

    def test_exact_artifact_set_and_hashes_pass(self):
        session = "71d5f7df-356f-4b3e-9ea7-a4be9d887801"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._write_artifacts(root, session, "a24-primary")
            result = probe.validate_artifacts(root, session, "a24-primary")
            self.assertEqual(result["file_count"], 8)

    def test_nested_provenance_replaced_artifact_and_event_identity_fail_closed(self):
        session = "71d5f7df-356f-4b3e-9ea7-a4be9d887801"
        for mutation in ("nested", "replace", "event_identity"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                self._write_artifacts(root, session, "a24-primary")
                if mutation == "nested":
                    nested = root / "results"
                    nested.mkdir()
                    (nested / "provenance.json").write_text("{}", encoding="utf-8")
                else:
                    if mutation == "replace":
                        (root / "summary.json").write_text("{}", encoding="utf-8")
                    else:
                        (root / "events.jsonl").write_text(
                            json.dumps(
                                {
                                    "session_id": session,
                                    "device_id": "wrong-device",
                                    "event": "probe_started",
                                }
                            )
                            + "\n",
                            encoding="utf-8",
                        )
                with self.assertRaises(probe.ProbeContractError):
                    probe.validate_artifacts(root, session, "a24-primary")


if __name__ == "__main__":
    unittest.main()
